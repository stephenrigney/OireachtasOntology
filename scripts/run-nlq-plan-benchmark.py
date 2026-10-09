#!/usr/bin/env python3
"""Run measured Phase 2C plan generation against disposable capture-backed Fuseki."""

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

from poc.nlq.benchmark import dataset_association, load_benchmark  # noqa: E402
from poc.nlq.benchmark_isolation import DisposableFuseki  # noqa: E402
from poc.nlq.config import load_local_environment, resolved_llm_configuration  # noqa: E402
from poc.nlq.fuseki import FusekiQueryClient  # noqa: E402
from poc.nlq.plan_benchmark import (  # noqa: E402
    run_phase1_comparison,
    run_plan_cases,
    summarize_plan_results,
)
from poc.nlq.planner_benchmark import (  # noqa: E402
    DEFAULT_PLANNER_BENCHMARK_PATH,
    load_planner_benchmark,
)
from poc.nlq.structured_planner import (  # noqa: E402
    ResponsesPlanGenerator,
    StructuredPlanner,
)
from poc.nlq.llm import ResponsesTranslator  # noqa: E402
from poc.nlq.vocabulary import supported_predicates  # noqa: E402


DEFAULT_SOURCE_BENCHMARK = ROOT / "poc/nlq/benchmarks/benchmark-v3.json"


def _args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_PLANNER_BENCHMARK_PATH)
    parser.add_argument("--source-benchmark", type=Path, default=DEFAULT_SOURCE_BENCHMARK)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--state-db", type=Path)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--fuseki-image", default="stain/jena-fuseki:5.1.0")
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--compare-phase1", action="store_true",
        help="also run Phase 1 direct generation for comparable source cases",
    )
    return parser.parse_args(argv)


def _write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _bootstrap(args, instance: DisposableFuseki, baseline_path: Path) -> dict:
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
    process = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    if process.returncode:
        raise RuntimeError(
            "Phase 0A capture bootstrap failed; no plan benchmark was run.\n"
            + (process.stdout + process.stderr)[-12000:]
        )
    if not baseline_path.is_file():
        raise RuntimeError("Phase 0A bootstrap did not write its dataset baseline")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("schema_version") != 1 or not baseline.get("dataset", {}).get("id"):
        raise RuntimeError("Phase 0A bootstrap wrote an invalid dataset baseline")
    return baseline


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    process_environment = os.environ.copy()
    load_local_environment(ROOT)
    planner_configuration = resolved_llm_configuration(
        ROOT, process_environment=process_environment,
    )
    planner_benchmark = load_planner_benchmark(args.benchmark)
    source_benchmark = load_benchmark(args.source_benchmark)
    if not os.getenv("NLQ_LLM_API_KEY"):
        raise SystemExit("NLQ_LLM_API_KEY is required for the measured plan benchmark")

    run_id = str(uuid.uuid4())
    result_path = args.results or ROOT / "var" / "nlq-plan-benchmark" / "runs" / f"{run_id}.json"
    scratch_root = Path("/tmp/opencode/oireachtasontology/nlq-plan-benchmark")
    scratch_root.mkdir(parents=True, exist_ok=True)

    try:
        with DisposableFuseki(
            docker=args.docker, image=args.fuseki_image,
        ) as instance, tempfile.TemporaryDirectory(
            prefix="run-", dir=scratch_root,
        ) as work_dir:
            baseline = _bootstrap(
                args, instance, Path(work_dir) / "phase-0a-dataset-baseline.json",
            )
            client = FusekiQueryClient(
                instance.query_url, username="admin", password=instance.password,
            )
            predicates = supported_predicates(ROOT / "ontology")
            api_key = os.getenv("NLQ_LLM_API_KEY", "")
            base_url = planner_configuration["base_endpoint"]["value"]
            model = planner_configuration["model"]["value"]

            def planner_factory(_case, fuseki):
                draft_generator = ResponsesPlanGenerator(
                    api_key, base_url, model,
                )
                return StructuredPlanner(
                    draft_generator, fuseki, supported_predicates=predicates,
                )

            try:
                case_results = run_plan_cases(
                    planner_benchmark, source_benchmark, baseline,
                    fuseki=client,
                    supported_predicates=predicates,
                    planner_factory=planner_factory,
                )
                phase1_comparison = None
                if args.compare_phase1:
                    phase1_comparison = run_phase1_comparison(
                        planner_benchmark, source_benchmark, baseline,
                        fuseki=client,
                        repository_root=ROOT,
                        translator_factory=lambda _case: ResponsesTranslator(
                            api_key, base_url, model,
                        ),
                    )
            finally:
                client.close()

            result = {
                "result_schema_version": 1,
                "run_id": run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "benchmark_id": planner_benchmark["benchmark_id"],
                "benchmark_version": planner_benchmark["benchmark_version"],
                "benchmark_artifact": {
                    "path": str(args.benchmark.resolve()),
                    "sha256": hashlib.sha256(args.benchmark.read_bytes()).hexdigest(),
                },
                "source_benchmark": {
                    "benchmark_id": source_benchmark["benchmark_id"],
                    "benchmark_version": source_benchmark["benchmark_version"],
                    "path": str(args.source_benchmark.resolve()),
                    "sha256": hashlib.sha256(args.source_benchmark.read_bytes()).hexdigest(),
                },
                "tier": "measured",
                "planner_configuration": planner_configuration,
                "dataset_association": dataset_association(
                    baseline, instance.isolation_metadata(),
                ),
                "case_results": case_results,
                "summary": summarize_plan_results(case_results),
                "phase1_comparison": phase1_comparison,
            }
            _write_result(result_path, result)
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "run_id": run_id,
        "tier": "measured",
        "benchmark": f"{planner_benchmark['benchmark_id']}@{planner_benchmark['benchmark_version']}",
        "dataset_id": result["dataset_association"]["dataset_id"],
        "dataset_instance": result["dataset_association"]["isolation"]["container_id"],
        "summary": result["summary"],
        "phase1_comparison": (
            result["phase1_comparison"]["summary"] if result["phase1_comparison"] else None
        ),
        "results": str(result_path),
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
