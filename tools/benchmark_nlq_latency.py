#!/usr/bin/env python3
"""Measure live end-to-end /ask latency; never substitutes mocked timings."""

from __future__ import annotations

import argparse
import html
import json
import statistics
from html.parser import HTMLParser
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "poc/nlq/benchmarks/latency-baseline-v1.json"


class PerformanceReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.performance = None
        self.outcome = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "details" and "performance" in attrs.get("class", "").split():
            self.performance = json.loads(html.unescape(attrs["data-performance"]))
        if "data-outcome" in attrs:
            self.outcome = attrs["data-outcome"]


def median(values):
    return round(statistics.median(values), 3) if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001/ask", help="Live query service /ask URL")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--mode", default="phase2")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    cases = json.loads(FIXTURE.read_text())["cases"]
    report = {"evidence_kind": "live end-to-end HTTP measurements", "url": args.url,
              "runs_per_question": args.runs, "cases": []}
    with httpx.Client(timeout=180) as client:
        for case in cases:
            samples = []
            for _ in range(args.runs):
                response = client.post(args.url, data={"question": case["question"], "mode": args.mode})
                response.raise_for_status()
                reader = PerformanceReader()
                reader.feed(response.text)
                if reader.performance is None:
                    raise RuntimeError("Response did not contain query performance diagnostics; no timing was inferred.")
                samples.append(reader.performance)
            total = [sample["total_elapsed_ms"] for sample in samples]
            stages = sorted({stage for sample in samples for stage in sample["stages"]})
            report["cases"].append({
                "id": case["id"], "category": case["category"], "question": case["question"],
                "outcome": samples[-1]["outcome"], "runs": len(samples),
                "median_total_ms": median(total), "slowest_total_ms": max(total),
                "median_stages_ms": {
                    stage: median([sample["stages"][stage]["elapsed_ms"]
                                   for sample in samples
                                   if sample["stages"][stage]["elapsed_ms"] is not None])
                    for stage in stages
                },
                "llm": {
                    "median_count": median([sample["llm"]["count"] for sample in samples]),
                    "median_cumulative_ms": median([sample["llm"]["cumulative_elapsed_ms"] for sample in samples]),
                },
                "fuseki": {
                    "median_count": median([sample["fuseki"]["count"] for sample in samples]),
                    "median_cumulative_ms": median([sample["fuseki"]["cumulative_elapsed_ms"] for sample in samples]),
                },
            })
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
