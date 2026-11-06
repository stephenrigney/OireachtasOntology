#!/usr/bin/env python3
"""Collect read-only /ask evidence for the frozen holdout and original 26 questions."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/reports/query-service/independent-generalisation"
REPORT = ROOT / "docs/reports/query-service/user-question-regression.md"
COLLECTOR = ROOT / "tools/evaluate-query-generalisation.py"


def _collector():
    spec = importlib.util.spec_from_file_location("query_generalisation_collector", COLLECTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_manifest():
    frozen_bytes = (EVIDENCE / "holdout.json").read_bytes()
    freeze = json.loads((EVIDENCE / "freeze.json").read_text())
    if hashlib.sha256(frozen_bytes).hexdigest() != freeze["holdout_sha256"]:
        raise ValueError("Frozen holdout hash mismatch")
    holdout = json.loads(frozen_bytes)["cases"]

    originals = []
    for line in REPORT.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"\d+(?:[ab])?", cells[0]):
            continue
        match = re.fullmatch(r"`(.+)`", cells[1])
        if not match:
            continue
        number = int(re.match(r"\d+", cells[0]).group())
        suffix = cells[0][len(str(number)):]
        originals.append({"id": f"R{number:02d}{suffix}", "question": match.group(1), "source": "original26"})
    if len(originals) != 26:
        raise ValueError(f"Expected exactly 26 original table questions; found {len(originals)}")

    regression = json.loads((EVIDENCE / "regression-cases.json").read_text())
    if len(regression) != 16:
        raise ValueError(f"Expected exactly 16 frozen regression questions; found {len(regression)}")
    original_questions = {entry["question"] for entry in originals}
    for case in regression:
        if case["question"] not in original_questions:
            raise ValueError(f"Regression question absent from original-26 report table: {case['id']}")
    return ([{"id": case["id"], "question": case["question"], "source": "holdout60"} for case in holdout]
            + originals)


def collect(manifest, output, url, runs=1, workers=2, ids=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    if not 1 <= workers <= 2:
        raise ValueError("workers must be 1 or 2")
    selected = manifest
    if ids:
        wanted = set(ids)
        known = {case["id"] for case in manifest}
        unknown = wanted - known
        if unknown:
            raise ValueError(f"Unknown case IDs: {', '.join(sorted(unknown))}")
        selected = [case for case in manifest if case["id"] in wanted]
    output.mkdir(parents=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    provenance = {"collected_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "source_commit": commit,
                  "service_url": url, "runs": runs, "workers": workers}
    (output / "question-manifest.json").write_text(json.dumps(
        {"provenance": provenance, "cases": selected}, ensure_ascii=False, indent=2) + "\n")
    ask = _collector().ask
    jobs = [(case, run) for run in range(1, runs + 1) for case in selected]
    with (output / "responses.jsonl").open("x", encoding="utf-8") as stream:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(ask, case, run, url.rstrip("/")) for case, run in jobs]
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                row.update({"source": next(c["source"] for c in selected if c["id"] == row["id"]),
                            "source_commit": commit})
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(row["id"], row["run"], row.get("outcome", row.get("transport_error")), flush=True)
    (output / "collection-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--ids", default="", help="Comma-separated H01..H60 and R01..R25/R21a/R21b IDs")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    collect(load_manifest(), args.output, args.url, args.runs, args.workers,
            [value.strip() for value in args.ids.split(",") if value.strip()] or None)


if __name__ == "__main__":
    main()
