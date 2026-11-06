#!/usr/bin/env python3
"""Score development replays against unchanged published evidence.

Table checks are necessary, not sufficient: full-intent and qualification review
is recorded separately in the campaign report. Never promote a safe nonanswer
to a factual pass. This tool does not execute queries or change frozen oracles.
"""

import argparse
from collections import Counter
import gzip
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "docs/reports/query-service/independent-generalisation"
CAVEATS = {"H21", "H22", "H44"}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records(path):
    raw = gzip.decompress(path.read_bytes()).decode() if path.suffix == ".gz" else path.read_text()
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def check_holdout(case, actual):
    """Extend the old run-specific scorer for capabilities it never answered."""
    old = load_module("published_score", ROOT / "tools/score-query-generalisation.py")
    id = case["id"]
    columns, *rows = actual["tables"][0]
    expected = case.get("expected_rows", [])
    if id in {"H32", "H33", "H34", "H35"}:
        assert {tuple(r) for r in rows} == {
            (r["name"], r["start"][:10], r["end"][:10] if r.get("end") else "Open-ended (no end date recorded)") for r in expected
        }
    elif id in {"H38", "H39", "H40"}:
        assert {tuple(r) for r in rows} == {
            (r["label"], r["start"][:10], r.get("end", "")[:10] or "Open-ended (no end date recorded)", r["term"])
            for r in expected
        }
    elif id == "H41":
        assert len(rows) == 1
        assert rows[0][columns.index("Seats")] == expected[0]["seats"]
        assert "28th Dáil" in rows[0]
    elif id == "H42":
        assert {r[0] for r in rows} == {r["label"] for r in expected}
        assert {r[columns.index("Identity")] for r in rows} == {r["party"] for r in expected}
    else:
        old.assert_facts(case, actual)


def check_control(case, actual, holdout):
    columns, *rows = actual["tables"][0]
    if "expected_names" in case:
        assert {r[0] for r in rows} == set(case["expected_names"])
    if "expected_count" in case:
        assert len(rows) == 1 and int(rows[0][0]) == case["expected_count"]
    if case["id"] == "R06":
        assert len(rows) == 9
        assert {r[3] for r in rows} == {"https://data.oireachtas.ie/ie/oireachtas/member/id/John-Lynch.D.1948-02-18"}
        assert {r[2] for r in rows} == {f'{n}{"st" if n == 21 else "th"} Dáil' for n in range(13, 22)}
        assert {(r[2], r[1]) for r in rows} == {
            (f'{n}{"st" if n == 21 else "th"} Dáil', "Cork Borough" if n <= 18 else "Cork City North-West" if n <= 20 else "Cork City")
            for n in range(13, 22)
        }
    if case["id"] == "R18":
        assert len(rows) == 1 and rows[0][1:4] == ["Dublin Central", "30th Dáil", "2007-06-14"]
    if case["id"] == "R20":
        assert {r[1] for r in rows} == {r["person"] for r in holdout["H47"]["expected_rows"]}


def score(actuals):
    cases = {c["id"]: c for c in json.loads((FROZEN / "holdout.json").read_text())["cases"]}
    controls = {c["id"]: c for c in json.loads((FROZEN / "regression-cases.json").read_text())}
    published = {r["id"]: r["score_against_frozen_expectation"] for r in json.loads((FROZEN / "assessment.json").read_text())["ledger"]}
    ledger = []
    for actual in actuals:
        id, outcome = actual["id"], actual.get("outcome")
        baseline = published[id] if id in cases else "PASS" if id in controls else "PARTIAL" if id in {"R02", "R07", "R12"} else "FAIL"
        result, facts, detail = "FAIL", False, "No factual answer"
        try:
            assert actual.get("http_status") == 200, "HTTP/transport failure"
            if id in cases:
                c = cases[id]
                if c["expected_outcome"] == "answer":
                    if outcome == "answer":
                        check_holdout(c, actual)
                        result, facts, detail = "PASS", True, "Complete frozen factual table matches; intent/qualification review required"
                elif c["expected_outcome"] == "missing_or_unaccepted_evidence":
                    assert outcome == c["expected_outcome"], "Evidence boundary changed"
                    result, detail = "BLOCKED", "Predeclared evidence blocker; not factual credit"
                elif outcome == c["expected_outcome"]:
                    result, detail = "PASS", "Expected fail-closed/clarification outcome; candidate/intent review required"
                elif id == "H56" and outcome == "unsupported_capability":
                    result, detail = "PARTIAL", "Safe nonanswer but no requested clarification"
                else:
                    raise AssertionError("Unexpected boundary outcome")
            elif id in controls:
                if outcome == "answer":
                    check_control(controls[id], actual, cases)
                    result, facts, detail = "PASS", True, "Published control table matches; intent/qualification review required"
            elif id in {"R02", "R21a"}:
                assert outcome == "clarification_required", "Expected unresolved identity/set clarification"
                result, detail = baseline, "Original factual expectation remains unmet; safe clarification, not factual credit"
            elif id in {"R07", "R12"}:
                assert outcome == "answer", "Expected qualified incomplete evidence answer"
                columns, *rows = actual["tables"][0]
                if id == "R07":
                    assert len(rows) == 1 and rows[0][0] == "Bertie Ahern"
                    assert rows[0][-2:] == ["2007-06-14", "2008-05-07"]
                    assert "incomplete" in actual["rendered_answer"].lower()
                else:
                    assert rows == [["Albert Reynolds", "1992-12-14", "1994-12-15"]]
                    assert "complete" in actual["rendered_answer"].lower()
                result, detail = "PARTIAL", "Published partial evidence only; no complete-career/roster credit"
            else:
                assert id in {"R04", "R05", "R08", "R14", "R15", "R17"}
                assert outcome == "unsupported_capability", "Unsupported original request changed outcome"
                detail = "Original factual request still unsupported; safe refusal, not factual credit"
        except (AssertionError, KeyError, ValueError, IndexError, TypeError) as error:
            detail = f"Mismatch requiring review: {type(error).__name__}: {error}"
        ledger.append({"id": id, "run": actual.get("run", 1), "question": actual["question"],
                       "baseline": baseline, "score": result, "outcome": outcome,
                       "factual_match": facts, "returned_answer_mismatch": outcome == "answer" and result == "FAIL",
                       "scope_caveat": id in CAVEATS, "detail": detail})
    h = [r for r in ledger if r["id"] in cases]
    factual = [r for r in h if cases[r["id"]]["expected_outcome"] == "answer"]
    strict = [r for r in factual if r["id"] not in CAVEATS]
    original = [r for r in ledger if r["id"].startswith("R")]
    return {"summary": {
        "holdout": dict(Counter(r["score"] for r in h)),
        "factual": {"correct": sum(r["factual_match"] for r in factual), "eligible": len(factual)},
        "sensitivity": {"correct": sum(r["factual_match"] for r in strict), "eligible": len(strict)},
        "original26": dict(Counter(r["score"] for r in original)),
        "original16_matches": sum(r["factual_match"] for r in original if r["id"] in controls),
        "returned_answer_mismatches": [r["id"] for r in ledger if r["returned_answer_mismatch"]]},
        "ledger": ledger,
        "limitations": "Machine table/outcome checks only. Review full intent, exact constraints, candidate sets and coverage qualifications independently; matches alone are not semantic acceptance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = score(records(args.responses))
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
