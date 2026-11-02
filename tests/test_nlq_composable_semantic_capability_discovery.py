"""Integrated selection and reuse of existing Stage A/B query handlers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft,
    validate_composable_plan_draft,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 1)
MEMBER = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley"
SEANAD = "https://data.oireachtas.ie/ie/oireachtas/houseTerm/seanad/26"
BILL = "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23"


def _selection(capability: str, parameters: dict) -> dict:
    return {
        "version": 2,
        "supported": True,
        "family": "capability_selection",
        "unsupportedReason": None,
        "intent": f"Use the existing {capability} capability.",
        "referents": {"capability": capability, "parameters": parameters},
        "relations": [],
        "constraints": [],
        "answer": None,
    }


class FixedPlanGenerator:
    def __init__(self, draft):
        self.draft = draft
        self.calls: list[str] = []
        self.closed = False

    def generate(self, question: str) -> str:
        self.calls.append(question)
        return json.dumps(self.draft, ensure_ascii=False)

    def close(self):
        self.closed = True


class CapabilityFixture:
    """Answer the exact local query shapes emitted by the existing handlers."""

    def __init__(self):
        self.queries: list[str] = []

    def readiness(self):
        return FusekiReadiness(
            "ready", True,
            tuple((name, True) for name in ("Houses", "Parties", "Constituencies", "Members", "Bills")),
            "synthetic semantic-capability fixture",
        )

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        if "?membership a members:SeanadMembership" in query:
            columns = (
                "member", "name", "membership", "term", "termLabel", "termStart", "termEnd",
                "membershipStart", "membershipEnd", "representation", "representationLabel",
            )
            return QueryResult("select", columns, (
                (MEMBER, "Timmy Dooley", MEMBER + "#seanad-26", SEANAD, "26th Seanad@en",
                 '2002-09-12^^<http://www.w3.org/2001/XMLSchema#date>',
                 '2007-07-05^^<http://www.w3.org/2001/XMLSchema#date>',
                 '2002-09-12T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>',
                 '2007-07-05T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>', "—", "—"),
                (MEMBER, "Timmy Dooley", MEMBER + "#seanad-27", SEANAD + "-27", "27th Seanad@en",
                 '2007-07-23^^<http://www.w3.org/2001/XMLSchema#date>',
                 '2011-02-01^^<http://www.w3.org/2001/XMLSchema#date>',
                 '2007-07-23T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>',
                 '2011-02-01T00:00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>', "—", "—"),
            ))
        if "eli:has_part" in query and "eli-dl:DraftLegislationWork" in query:
            columns = (
                "bill", "title", "year", "process", "number", "status", "eventDate", "eventType",
                "memoWork", "memo",
            )
            return QueryResult("select", columns, ((
                BILL, "Pregnancy Loss (Miscellaneous Provisions) Bill 2025@en", "2025",
                BILL + "/process", "23", "https://data.oireachtas.ie/ontology#CurrentBill",
                '2025-02-20^^<http://www.w3.org/2001/XMLSchema#date>',
                "https://data.oireachtas.ie/ontology#FirstStage", "—", "—",
            ),))
        if "SELECT DISTINCT ?member ?name" in query:
            return QueryResult("select", ("member", "name"), ((MEMBER, "Timmy Dooley"),))
        raise AssertionError(f"Unexpected query in semantic capability fixture: {query}")


def test_dispatch_capabilities_are_contract_grounded_and_part_of_planner_context():
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    capabilities = {item["id"]: item for item in contract["semanticDispatch"]["capabilities"]}
    assert set(capabilities) == {"bill_lookup", "seanad_entry"}
    assert capabilities["seanad_entry"]["handler"] == "stage_a"
    assert capabilities["bill_lookup"]["handler"] == "stage_b"
    from poc.nlq.composable_semantic_planner import build_composable_planner_instructions
    instructions = build_composable_planner_instructions()
    assert 'family "capability_selection"' in instructions
    assert "every locally recorded typed dated activity" in instructions
    assert "earliest evidenced Seanad membership start date" in instructions


@pytest.mark.parametrize(("question", "capability", "parameters", "deterministic"), [
    (
        "What is the official title of the Bill numbered 23 in 2025?",
        "bill_lookup", {"billNumber": "23", "billYear": 2025}, "stage_b",
    ),
    (
        "What happened most recently in the legislative process for Bill 23/2025?",
        "bill_lookup", {"billNumber": "23", "billYear": 2025}, "stage_b",
    ),
    (
        "When did Timmy Dooley first take a seat in the Seanad?",
        "seanad_entry", {"member": "Timmy Dooley"}, "stage_a",
    ),
    (
        "Could you give me the recorded entry date for Senator Timmy Dooley's earliest Seanad service?",
        "seanad_entry", {"member": "Timmy Dooley"}, "stage_a",
    ),
    (
        "Has any dated step been recorded recently for Bill No. 23 from 2025?",
        "bill_lookup", {"billNumber": "23", "billYear": 2025}, "stage_b",
    ),
])
def test_integrated_ask_selects_existing_validated_capability(
    question, capability, parameters, deterministic, monkeypatch,
):
    from poc.nlq import app as app_module
    from poc.nlq.stage_a import parse_stage_a_question
    from poc.nlq.stage_b import plan_stage_b

    assert parse_stage_a_question(question) is None
    assert plan_stage_b(question, as_of=AS_OF) is None
    fixture = CapabilityFixture()
    generator = FixedPlanGenerator(_selection(capability, parameters))
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert generator.calls == [question]
    assert generator.closed
    assert len(fixture.queries) == (2 if capability == "seanad_entry" else 1)
    if capability == "seanad_entry":
        assert "First Seanad entry" in response.text
        assert "2002-09-12" in response.text
        assert "27th Seanad" in response.text
        assert "members:SeanadMembership" in fixture.queries[-1]
        assert "members:DailMembership" not in fixture.queries[-1]
    else:
        assert "Pregnancy Loss (Miscellaneous Provisions) Bill 2025" in response.text
        assert "First Stage: 2025-02-20" in response.text
        assert "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23" in response.text
        assert "BillDelivery" in fixture.queries[-1]
        assert "eli:has_part" in fixture.queries[-1]
        assert "SERVICE" not in fixture.queries[-1].upper()
        assert "FROM NAMED" not in fixture.queries[-1].upper()
    assert deterministic in {"stage_a", "stage_b"}


@pytest.mark.parametrize(("question", "draft"), [
    (
        "Who sponsored Bill 23/2025?",
        _selection("bill_lookup", {"billNumber": "23", "billYear": 2025}),
    ),
    (
        "When did Timmy Dooley enter the Seanad and which panel did he represent?",
        _selection("seanad_entry", {"member": "Timmy Dooley"}),
    ),
    (
        "What is the official title of Bill 23/2025?",
        _selection("bill_lookup", {"billNumber": "24", "billYear": 2025}),
    ),
])
def test_capability_selector_cannot_drop_requested_relationships_or_hallucinate_inputs(question, draft):
    with pytest.raises((InvalidComposableDraft, ValueError)):
        validate_composable_plan_draft(draft, question=question)
