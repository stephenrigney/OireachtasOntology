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
