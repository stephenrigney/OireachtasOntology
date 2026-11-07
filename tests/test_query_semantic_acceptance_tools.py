"""Synthetic-only checks for the independent semantic acceptance utilities."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_tool(filename: str, module_name: str):
    path = ROOT / "tools" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tools():
    return {
        "collector": _load_tool("collect-query-semantic-acceptance.py", "synthetic_acceptance_collector"),
        "scorer": _load_tool("score-query-semantic-acceptance.py", "synthetic_acceptance_scorer"),
    }


def test_html_parser_retains_outcome_rows_and_exact_uri_links(tools):
    collector = tools["collector"]
    html = """<section id="answer" data-outcome="answered">
      <table><tr><th>member</th><th>group</th></tr>
      <tr><td><a href="https://example.test/member/a">Member A</a></td>
      <td><a href="https://example.test/group/x">Group X</a></td></tr></table>
      </section><section id="query-processing">synthetic excluded detail</section>"""

    page = collector.RenderedPage(html)
    assert page.outcome == "answered"
    assert len(page.tables) == 1
    row = page.tables[0][1]
    assert row[0]["links"] == ["https://example.test/member/a"]
    assert row[1]["links"] == ["https://example.test/group/x"]
    assert "synthetic excluded detail" not in " ".join(page.sections)


def test_exact_row_association_rejects_same_marginals_with_wrong_pairs(tools):
    scorer = tools["scorer"]
    expected = [
        {
            "member": {"type": "uri", "value": "https://example.test/member/a"},
            "group": {"type": "uri", "value": "https://example.test/group/x"},
        },
        {
            "member": {"type": "uri", "value": "https://example.test/member/b"},
            "group": {"type": "uri", "value": "https://example.test/group/y"},
        },
    ]
    swapped_pairs = """<table><tr><th>member</th><th>group</th></tr>
      <tr><td><a href="https://example.test/member/a">A</a></td>
      <td><a href="https://example.test/group/y">Y</a></td></tr>
      <tr><td><a href="https://example.test/member/b">B</a></td>
      <td><a href="https://example.test/group/x">X</a></td></tr></table>"""

    result = scorer.compare_rows(expected, scorer.RenderedPage(swapped_pairs).tables)
    assert result["status"] == "fail"
    assert result["matched_full_rows"] == 0


def test_count_mismatch_is_detected_from_a_synthetic_count_column(tools):
    scorer = tools["scorer"]
    case = {"expected": {"answerKind": "count", "countValue": 7}}
    record = {"http_status": 200}
    page = scorer.RenderedPage("<table><tr><th>count</th></tr><tr><td>6</td></tr></table>")

    assert scorer.score_expected(case, record, page)["answer_shape"] == "fail"


def test_collector_writes_outputs_once_and_requires_both_authorization_flags(tools, tmp_path, monkeypatch):
    collector = tools["collector"]
    result_path = tmp_path / "first-response.html"
    collector.write_exclusive(result_path, b"synthetic first response")
    with pytest.raises(FileExistsError):
        collector.write_exclusive(result_path, b"synthetic replacement")
    assert result_path.read_bytes() == b"synthetic first response"

    output = tmp_path / "run"
    monkeypatch.setattr(sys, "argv", [
        "collect-query-semantic-acceptance.py",
        "--base-url", "http://example.test",
        "--out", str(output),
    ])
    monkeypatch.setattr(collector, "verify_freeze", lambda: pytest.fail("authorization gate must run first"))
    with pytest.raises(SystemExit):
        collector.main()
    assert not output.exists()

    class StopBeforeNetwork(Exception):
        pass

    def stop_after_explicit_flags():
        raise StopBeforeNetwork

    monkeypatch.setattr(collector, "verify_freeze", stop_after_explicit_flags)
    monkeypatch.setattr(sys, "argv", [
        "collect-query-semantic-acceptance.py",
        "--base-url", "http://example.test",
        "--out", str(output),
        "--execute-ask",
        "--acknowledge-authorization",
    ])
    with pytest.raises(StopBeforeNetwork):
        collector.main()
    assert not output.exists()


def test_scorer_requires_complete_manual_intent_and_qualification_review(tools):
    scorer = tools["scorer"]
    uri = "https://example.test/member/a"
    synthetic_holdout = {
        "questions": [{
            "id": "SYN-CASE-1",
            "question": "Synthetic question about an invented entity?",
            "class": "factual",
            "capabilityGroup": "synthetic_group",
            "scoring": {"identity": "Use exact synthetic IRIs.", "criteria": ["Keep each invented pair together."]},
            "expected": {
                "answerKind": "entities",
                "identitySet": [{"member": {"type": "uri", "value": uri}}],
                "qualifications": ["Do not infer completeness from synthetic absence."],
            },
        }]
    }
    template = scorer.make_review_template(synthetic_holdout, "synthetic-run")

    incomplete = scorer.validate_review(template, template)["SYN-CASE-1"]
    assert incomplete["complete"] is False
    assert incomplete["passed"] is False

    missing_qualification = copy.deepcopy(template)
    missing_qualification["cases"][0]["qualifications"] = []
    with pytest.raises(ValueError, match="checklist items changed"):
        scorer.validate_review(template, missing_qualification)


@pytest.mark.parametrize("tool_name", ["collector", "scorer"])
def test_freeze_hash_tampering_fails_closed_before_reading_other_artifacts(tools, tmp_path, monkeypatch, tool_name):
    tool = tools[tool_name]
    (tmp_path / "freeze.json").write_text(json.dumps({"synthetic": "tampered"}), encoding="utf-8")
    monkeypatch.setattr(tool, "ARTIFACT_DIR", tmp_path)

    with pytest.raises(ValueError, match="freeze.json differs from the pinned frozen metadata"):
        tool.verify_freeze()
