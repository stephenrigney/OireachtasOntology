#!/usr/bin/env python3
"""Recheck this frozen evaluation's factual tables and reproduce its score ledger.

This is a run-specific evaluation artifact, not a generic NLQ acceptance test.
Manual contract/constraint review remains documented in the accompanying report.
"""
import collections
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parents[1] / "docs/reports/query-service/independent-generalisation"
SCOPE_CAVEATS = {"H21", "H22", "H44"}


def text(name):
    path = OUT / name
    if path.exists():
        return path.read_text()
    return gzip.decompress(path.with_suffix(path.suffix + ".gz").read_bytes()).decode()


def rows(name):
    return [json.loads(line) for line in text(name).splitlines()]


def assert_facts(case, actual):
    """Compare complete returned sets/values, never HTTP success or substring hits."""
    table = actual["tables"][0]
    columns, returned = table[0], table[1:]
    expected = case.get("expected_rows", [])
    id = case["id"]
    if "expected_count" in case:
        assert len(returned) == 1 and int(returned[0][0]) == case["expected_count"], id
    elif id == "H50":
        assert {(r[3], r[2]) for r in returned} == {tuple(r["bill"].split("/")[-2:]) for r in expected}, id
    elif id in {"H08", "H09"}:
        assert {re.search(r"\d+", r[0]).group() for r in returned} == {r["term"].split("/")[-1] for r in expected}, id
    elif id in {"H01", "H02"}:
        assert {r[0] for r in returned} == {r["name"] for r in expected}, id
    elif id in {"H32", "H33", "H34"}:
        assert {tuple(r) for r in returned} == {(r["name"], r["start"][:10], r["end"][:10]) for r in expected}, id
    elif id in {"H36", "H37"}:
        assert {(r[0], r[2], r[3], r[4]) for r in returned} == {(r["name"], r["holding"], r["start"][:10], r["end"][:10]) for r in expected}, id
    else:
        assert expected, id
        if "person" in expected[0]:
            ix = columns.index("Member identity")
            assert {r[ix] for r in returned} == {r["person"] for r in expected}, id
        if "constituency" in expected[0]:
            ix = columns.index("Constituency identity")
            assert {r[ix] for r in returned} == {r["constituency"] for r in expected}, id
            ix = columns.index("Term identity")
            terms = {r["term"] for r in expected} if "term" in expected[0] else {"https://data.oireachtas.ie/ie/oireachtas/house/dail/34"}
            assert {r[ix] for r in returned} == terms, id
        if id == "H04":
            assert {r[columns.index("Term start")] for r in returned} == {r["start"][:10] for r in expected}, id


def signature(actual):
    """Ignore prose/plan-ID wording; keep complete sorted factual table content."""
    if actual.get("outcome") == "answer":
        return json.dumps([sorted(table[1:]) for table in actual["tables"]], ensure_ascii=False)
    return "NO_FACTUAL_ANSWER"


def main():
    freeze = json.loads(text("freeze.json"))
    assert hashlib.sha256((OUT / "holdout.json").read_bytes()).hexdigest() == freeze["holdout_sha256"]
    cases = {c["id"]: c for c in json.loads(text("holdout.json"))["cases"]}
    baseline = {r["id"]: r for r in rows("main.jsonl")}
    assert set(cases) == set(baseline) and len(baseline) == 60
    ledger = []
    for id, c in cases.items():
        actual = baseline[id]
        assert actual["http_status"] == 200, id
        if c["expected_outcome"] == "answer":
            if actual["outcome"] == "answer":
                assert_facts(c, actual)
                score = "PASS"
            else:
                score = "FAIL"
        elif c["expected_outcome"] == "missing_or_unaccepted_evidence":
            assert actual["outcome"] == "missing_or_unaccepted_evidence", id
            score = "BLOCKED"
        elif id == "H56":
            assert actual["outcome"] == "unsupported_capability"
            score = "PARTIAL"
        else:
            assert actual["outcome"] == c["expected_outcome"], id
            score = "PASS"
        ledger.append({"id": id, "score_against_frozen_expectation": score,
                       "category": c["category"], "actual_outcome": actual["outcome"],
                       "scope_admissibility_caveat": id in SCOPE_CAVEATS,
                       "factual_table_matches": actual["outcome"] == "answer",
                       "constraints": "preserved_in_answer" if actual["outcome"] == "answer" else "safely_no_final_answer"})
    repeat = rows("variability.jsonl")
    selected = json.loads(text("variability-selection.json"))["ids"]
    assert len(repeat) == 60 and {r["id"] for r in repeat} == set(selected)
    variability = []
    for id in selected:
        group = sorted([r for r in repeat if r["id"] == id], key=lambda r: r["run"])
        assert [r["run"] for r in group] == [1, 2, 3]
        for r in group:
            assert r["http_status"] == 200
            if r["outcome"] == "answer":
                assert_facts(cases[id], r)
            if id == "H55":
                context = json.loads(text("oracle-context.json"))
                expected_candidates = {x["person"]["value"] for x in context["ambiguity_murphy"]["response"]["results"]["bindings"]}
                candidates = set(re.findall(r"https://data\.oireachtas\.ie/ie/oireachtas/member/id/\S+?\.[DS]\.\d{4}-\d{2}-\d{2}", r["rendered_answer"]))
                assert candidates == expected_candidates
        outcomes = [r["outcome"] for r in group]
        facts = [signature(r) for r in group]
        keys = list(zip(outcomes, facts))
        all_four = [baseline[id]] + group
        variability.append({"id": id, "outcomes": outcomes, "outcome_consistent": len(set(outcomes)) == 1,
                            "factual_content_and_availability_consistent": len(set(facts)) == 1,
                            "outcome_and_facts_consistent": len(set(keys)) == 1,
                            "agreeing_pairs": sum(a == b for a, b in itertools.combinations(keys, 2)),
                            "all_four_outcomes_consistent": len({r["outcome"] for r in all_four}) == 1,
                            "all_four_facts_consistent": len({signature(r) for r in all_four}) == 1,
                            "factual_answers": sum(r["outcome"] == "answer" for r in group)})
    regression = {r["id"]: r for r in rows("regression.jsonl")}
    controls = json.loads(text("regression-cases.json"))
    assert len(regression) == len(controls) == 16
    for c in controls:
        r = regression[c["id"]]
        assert r["outcome"] == "answer"
        table = r["tables"][0]
        if "expected_names" in c:
            assert {x[0] for x in table[1:]} == set(c["expected_names"]), c["id"]
        if "expected_count" in c:
            assert int(table[1][0]) == c["expected_count"], c["id"]
        if c["id"] == "R06":
            assert len(table) == 10
            assert {x[3] for x in table[1:]} == {"https://data.oireachtas.ie/ie/oireachtas/member/id/John-Lynch.D.1948-02-18"}
            assert {x[2] for x in table[1:]} == {f'{n}{"st" if n == 21 else "th"} Dáil' for n in range(13, 22)}
        if c["id"] == "R18":
            assert table[1][1:4] == ["Dublin Central", "30th Dáil", "2007-06-14"]
        if c["id"] == "R20":
            assert {x[1] for x in table[1:]} == {x["person"] for x in cases["H47"]["expected_rows"]}
    factual = [r for r in ledger if cases[r["id"]]["expected_outcome"] == "answer"]
    strict = [r for r in factual if r["id"] not in SCOPE_CAVEATS]
    summary = {"all60_scores": dict(collections.Counter(r["score_against_frozen_expectation"] for r in ledger)),
               "frozen_factual": {"correct": sum(r["factual_table_matches"] for r in factual), "eligible": len(factual)},
               "contract_admissible_sensitivity": {"correct": sum(r["factual_table_matches"] for r in strict), "eligible": len(strict)},
               "repeated_outcomes": dict(collections.Counter(r["outcome"] for r in repeat)),
               "repeat_all_outcome_and_facts_consistent": sum(r["outcome_and_facts_consistent"] for r in variability),
               "repeat_factual_content_and_availability_consistent": sum(r["factual_content_and_availability_consistent"] for r in variability),
               "repeat_agreeing_pairs": sum(r["agreeing_pairs"] for r in variability),
               "repeat_all_four_outcomes_consistent": sum(r["all_four_outcomes_consistent"] for r in variability),
               "repeat_all_four_facts_consistent": sum(r["all_four_facts_consistent"] for r in variability),
               "regression_controls_matched": len(controls)}
    result = {"summary": summary, "ledger": ledger, "variability": variability,
              "manual_review": "Report documents qualifications, contract admissibility and preservation of requested filters. This script checks factual tables, not arbitrary prose semantics."}
    destination = OUT / "assessment.json"
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if destination.exists():
        assert destination.read_text() == serialized, "Existing assessment differs; investigate rather than overwrite."
    else:
        destination.write_text(serialized)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
