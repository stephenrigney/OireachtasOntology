#!/usr/bin/env python3
"""Run a measured NLQ benchmark against an isolated, capture-bootstrapped Fuseki."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.benchmark import (  # noqa: E402
    DEFAULT_BENCHMARK_PATH,
    dataset_association,
    load_benchmark,
    run_cases,
    summarize_results,
)
from poc.nlq.benchmark_isolation import DisposableFuseki  # noqa: E402
from poc.nlq.config import load_local_environment, resolved_llm_configuration  # noqa: E402
from poc.nlq.fuseki import FusekiQueryClient  # noqa: E402


def _args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=("regression", "measured"), default="regression")
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK_PATH)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--fuseki-image", default="stain/jena-fuseki:5.1.0")
    parser.add_argument("--uv", default="uv")
    return parser.parse_args(argv)


def _write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _run_bootstrap(args, instance: DisposableFuseki, baseline_path: Path) -> dict:
    command = [args.uv, "run", "--locked", "oir-etl", "dev", "bootstrap"]
    if args.raw_dir:
        command.extend(["--raw-dir", str(args.raw_dir.expanduser().resolve())])
    if args.state_db:
        command.extend(["--state-db", str(args.state_db.expanduser().resolve())])
    command.extend([
        "--fuseki-gsp-url", instance.gsp_url,
        "--fuseki-sparql-url", instance.query_url,
        "--dataset-baseline-output", str(baseline_path),
    ])
    environment = os.environ.copy()
    environment.update({
        "OIR_FUSEKI_GSP_URL": instance.gsp_url,
        "OIR_FUSEKI_SPARQL_URL": instance.query_url,
        "OIR_FUSEKI_USER": "admin",
        "OIR_FUSEKI_PASSWORD": instance.password,
    })
    process = subprocess.run(command, cwd=ROOT, env=environment,
                             capture_output=True, text=True)
    if process.returncode:
        detail = process.stdout + process.stderr
        raise RuntimeError(
            "Phase 0A capture bootstrap failed; no benchmark was run.\n" + detail[-12000:]
        )
    if not baseline_path.is_file():
        raise RuntimeError("Phase 0A bootstrap did not write its requested dataset baseline JSON")
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Phase 0A dataset baseline JSON is unreadable: {error}") from error
    if baseline.get("schema_version") != 1 or not baseline.get("dataset", {}).get("id"):
        raise RuntimeError("Phase 0A bootstrap wrote an invalid dataset baseline")
    return baseline


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    process_environment = os.environ.copy()
    load_local_environment(ROOT)
    llm_configuration = resolved_llm_configuration(
        ROOT, process_environment=process_environment,
    )
    benchmark = load_benchmark(args.benchmark)
    if args.tier == "measured" and not os.getenv("NLQ_LLM_API_KEY"):
        raise SystemExit("NLQ_LLM_API_KEY is required for the measured LLM benchmark")

    run_id = str(uuid.uuid4())
    result_path = args.results or ROOT / "var" / "nlq-benchmark" / "runs" / f"{run_id}.json"
    scratch_root = Path(tempfile.gettempdir()) / "oireachtasontology" / "nlq-benchmark-phase-0b"
    scratch_root.mkdir(parents=True, exist_ok=True)

    try:
        with DisposableFuseki(
            docker=args.docker, image=args.fuseki_image,
        ) as instance, tempfile.TemporaryDirectory(
            prefix="run-", dir=scratch_root,
        ) as work_dir:
            baseline_path = Path(work_dir) / "phase-0a-dataset-baseline.json"
            baseline = _run_bootstrap(args, instance, baseline_path)
            client = FusekiQueryClient(
                instance.query_url, username="admin", password=instance.password,
            )
            try:
                case_results = run_cases(
                    benchmark, baseline, fuseki=client, tier=args.tier,
                    repository_root=ROOT,
                )
            finally:
                client.close()
            result = {
                "result_schema_version": 1,
                "run_id": run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_id": benchmark["benchmark_id"],
                "benchmark_version": benchmark["benchmark_version"],
                "benchmark_artifact": {
                    "path": str(args.benchmark.resolve()),
                    "sha256": hashlib.sha256(args.benchmark.read_bytes()).hexdigest(),
                },
                "tier": args.tier,
                "translator_configuration": (
                    llm_configuration if args.tier == "measured" else None
                ),
                "dataset_association": dataset_association(
                    baseline, instance.isolation_metadata(),
                ),
                "case_results": case_results,
                "summary": summarize_results(case_results),
            }
            _write_result(result_path, result)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "run_id": run_id,
        "tier": args.tier,
        "dataset_id": result["dataset_association"]["dataset_id"],
        "dataset_instance": result["dataset_association"]["isolation"]["container_id"],
        "summary": result["summary"],
        "results": str(result_path),
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
