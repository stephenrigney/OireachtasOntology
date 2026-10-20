from poc.nlq.presentation import capability_catalogue, explain_plan
from fastapi.testclient import TestClient
from poc.nlq.app import create_app
from pathlib import Path


def test_catalogue_is_contract_backed_and_marks_compiler_coverage():
    entries = {item["id"]: item for item in capability_catalogue()}
    assert "member_full_name" in entries
    assert entries["member_full_name"]["status"] == "Executable"
    assert entries["member_full_name"]["filters"][0]["id"] == "member_name"
    assert entries["debate_date"]["subjectTypes"] == ["DebateRecord"]


def test_explanation_preserves_resolution_and_does_not_upgrade_draft():
    plan = {
        "entities": [
            {"id": "m", "type": "Member", "label": "Alex Example", "resolution": "ambiguous",
             "candidates": [{"iri": "https://data.oireachtas.ie/member/1", "label": "Alex Example"},
                            {"iri": "https://data.oireachtas.ie/member/2", "label": "Alex Example"}]},
            {"id": "t", "type": "DailTerm", "label": "34th Dáil", "resolution": "unresolved"},
        ],
        "requirements": [{"id": "r", "fact": "member_house_term_membership",
                          "subject": {"entity": "m"}, "object": {"entity": "t"}}],
        "filters": [], "temporalConstraints": [{"target": "r", "kind": "during", "period": {"entity": "t"}}],
        "aggregation": None, "answerShape": {"kind": "entities", "entityType": "Member"},
    }
    view = explain_plan(plan, validated=False, blocked_reason="unresolved entity")
    assert view["entities"][0]["human_resolution"].startswith("Several")
    assert view["entities"][1]["human_resolution"] == "No exact local match"
    assert view["requirements"][0]["description"] == "A Member's service in a Dáil or Seanad term."
    assert view["validated"] is False
    assert view["blocked_reason"] == "unresolved entity"


def test_explanation_accepts_resolved_plan_and_exposes_compiler_block():
    plan = {"entities": [{"id": "m", "type": "Member", "label": "Alex Example",
                          "resolution": "resolved", "iri": "https://data.oireachtas.ie/member/1"}],
            "requirements": [{"id": "r", "fact": "member_identity", "subject": {"entity": "m"}}],
            "filters": [], "temporalConstraints": [], "aggregation": None,
            "answerShape": {"kind": "entity", "entityType": "Member"}}
    view = explain_plan(plan, validated=True, blocked_reason="No reviewed compiler mapping")
    assert view["validated"] is True
    assert view["entities"][0]["human_resolution"] == "Resolved to a local record"
    assert view["blocked_reason"] == "No reviewed compiler mapping"


def test_capability_page_renders_from_catalogue():
    client = TestClient(create_app(repository_root=Path.cwd()))
    response = client.get("/capabilities")
    assert response.status_code == 200
    assert "What can this query service answer?" in response.text
    assert "member_full_name" in response.text
    assert "Temporal constraints" in response.text
