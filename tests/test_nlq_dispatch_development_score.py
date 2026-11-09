"""Development scoring never upgrades nonanswers or incomplete source evidence."""

import importlib.util
import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dispatch_score", ROOT / "tools/score-query-dispatch-development.py")
SCORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCORE)


def test_published_holdout_reproduces_baseline():
    rows = SCORE.records(SCORE.FROZEN / "main.jsonl.gz")
    result = SCORE.score(rows)
    assert result["summary"]["holdout"] == {"PASS": 31, "FAIL": 26, "PARTIAL": 1, "BLOCKED": 2}
    assert result["summary"]["factual"] == {"correct": 22, "eligible": 48}
    assert result["summary"]["returned_answer_mismatches"] == []


def test_published_original16_reproduce_baseline():
    rows = SCORE.records(SCORE.FROZEN / "regression.jsonl.gz")
    assert SCORE.score(rows)["summary"]["original16_matches"] == 16


@pytest.mark.parametrize("id", ["H38", "H39", "H40", "H41", "H42"])
def test_previously_unanswered_capabilities_require_actual_facts(id):
    cases = json.loads((SCORE.FROZEN / "holdout.json").read_text())["cases"]
    case = next(c for c in cases if c["id"] == id)
    with pytest.raises((AssertionError, ValueError)):
        SCORE.check_holdout(case, {"tables": [[["Unrelated"], ["Invented value"]]]})


def test_original_safe_refusal_is_not_factual_credit():
    r = {"id": "R15", "question": "Original sitting request", "outcome": "unsupported_capability", "http_status": 200}
    result = SCORE.score([r])
    assert result["ledger"][0]["score"] == "FAIL"
    assert result["ledger"][0]["returned_answer_mismatch"] is False


def test_equal_marginal_sets_do_not_hide_wrong_term_place_associations():
    actual = copy.deepcopy(next(r for r in SCORE.records(SCORE.FROZEN / "main.jsonl.gz") if r["id"] == "H05"))
    table = actual["tables"][0]
    index = table[0].index("Term identity")
    table[1][index], table[2][index] = table[2][index], table[1][index]
    result = SCORE.score([actual])
    assert result["ledger"][0]["returned_answer_mismatch"] is True
    assert result["ledger"][0]["score"] == "FAIL"


@pytest.mark.parametrize("column", ["Member identity", "Constituency identity", "Term identity"])
def test_original_latest_term_control_requires_exact_grounded_identities(column):
    actual = copy.deepcopy(next(r for r in SCORE.records(SCORE.FROZEN / "regression.jsonl.gz") if r["id"] == "R18"))
    table = actual["tables"][0]
    table[1][table[0].index(column)] = "https://example.invalid/wrong-identity"
    result = SCORE.score([actual])
    assert result["ledger"][0]["score"] == "FAIL"
    assert result["ledger"][0]["returned_answer_mismatch"] is True


def test_repeats_never_inflate_primary_factual_credit_and_duplicates_are_rejected():
    actual = copy.deepcopy(next(r for r in SCORE.records(SCORE.FROZEN / "main.jsonl.gz") if r["id"] == "H05"))
    repeat = copy.deepcopy(actual)
    repeat["run"] = 2
    result = SCORE.score([actual, repeat])
    assert result["summary"]["factual"] == {"correct": 1, "eligible": 48}
    assert result["summary"]["population"]["cases_scored"] == 1
    assert len(result["summary"]["population"]["missing_ids"]) == 85
    assert result["variability"]["additional_records"] == 1
    with pytest.raises(ValueError, match="Duplicate case/run"):
        SCORE.score([actual, copy.deepcopy(actual)])


def test_party_catalogue_requires_label_identity_associations():
    case = next(c for c in json.loads((SCORE.FROZEN / "holdout.json").read_text())["cases"] if c["id"] == "H42")
    expected = case["expected_rows"]
    actual = {"tables": [[["Name", "Identity"], *[[r["label"], r["party"]] for r in expected]]]}
    SCORE.check_holdout(case, actual)
    table = actual["tables"][0]
    table[1][1], table[2][1] = table[2][1], table[1][1]
    with pytest.raises(AssertionError):
        SCORE.check_holdout(case, actual)


def test_original_prior_service_control_rejects_duplicate_rows():
    actual = copy.deepcopy(next(r for r in SCORE.records(SCORE.FROZEN / "regression.jsonl.gz") if r["id"] == "R20"))
    actual["tables"][0].append(copy.deepcopy(actual["tables"][0][1]))
    assert SCORE.score([actual])["ledger"][0]["score"] == "FAIL"


def test_malformed_numeric_answer_is_a_per_case_failure_not_scoring_crash():
    actual = copy.deepcopy(next(r for r in SCORE.records(SCORE.FROZEN / "main.jsonl.gz") if r["id"] == "H08"))
    actual.update({"outcome": "answer", "tables": [[["Term"], ["Not a term number"]]]})
    assert SCORE.score([actual])["ledger"][0]["score"] == "FAIL"
