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
DAIL_TERM = "https://data.oireachtas.ie/ie/oireachtas/house/dail/33"
PARTY = "https://data.oireachtas.ie/ie/oireachtas/party/dail/33/fianna-fail"
MICHEAL = "https://data.oireachtas.ie/ie/oireachtas/member/id/Micheal-Martin"
AENGUS = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aengus-OSnodaigh"


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
        if "COUNT(DISTINCT ?term)" in query:
            return QueryResult("select", ("count",), (("5^^<http://www.w3.org/2001/XMLSchema#integer>",),))
        if "periodType" in query:
            return QueryResult("select", ("term", "label", "number", "period", "periodType", "start", "end"), ((
                DAIL_TERM, "33rd Dáil@en", "33^^<http://www.w3.org/2001/XMLSchema#integer>",
                DAIL_TERM + "#period", "http://purl.org/dc/terms/PeriodOfTime",
                "2020-02-08^^<http://www.w3.org/2001/XMLSchema#date>",
                "2024-11-08^^<http://www.w3.org/2001/XMLSchema#date>",
            ),))
        if "?seats" in query:
            return QueryResult("select", ("term", "seats"), ((
                DAIL_TERM, "160^^<http://www.w3.org/2001/XMLSchema#integer>",
            ),))
        if "SELECT DISTINCT ?party ?label" in query:
            return QueryResult("select", ("party", "label"), ((PARTY, "Fianna Fáil@en"),))
        if "agents:termNo" in query and "SELECT DISTINCT ?term WHERE" in query:
            return QueryResult("select", ("term",), ((DAIL_TERM,),))
        if "SELECT DISTINCT ?term WHERE" in query:
            return QueryResult("select", ("term",), ((DAIL_TERM,), (DAIL_TERM + "/replacement")))
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
        if "SELECT DISTINCT ?member ?name" in query and "Micheál Martin" in query:
            return QueryResult("select", ("member", "name"), ((MICHEAL, "Micheál Martin"),))
        if "SELECT DISTINCT ?member ?name" in query and "Aengus Ó Snodaigh" in query:
            return QueryResult("select", ("member", "name"), ((AENGUS, "Aengus Ó Snodaigh"),))
        if "SELECT DISTINCT ?member ?name" in query:
            return QueryResult("select", ("member", "name"), ((MEMBER, "Timmy Dooley"),))
        raise AssertionError(f"Unexpected query in semantic capability fixture: {query}")


def test_dispatch_capabilities_are_contract_grounded_and_part_of_planner_context():
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    capabilities = {item["id"]: item for item in contract["semanticDispatch"]["capabilities"]}
    from poc.nlq.composable_semantic_planner import CAPABILITY_SELECTION_HANDLER_INPUTS
    draft_schema = json.loads((ROOT / "poc/specs/composable-query-plan-draft.schema.json").read_text())
    selector_schema = next(
        item for item in draft_schema["properties"]["referents"]["anyOf"]
        if isinstance(item, dict) and "capability" in item.get("required", [])
    )
    selector_ids = set(selector_schema["properties"]["capability"]["enum"])
    assert selector_ids == set(CAPABILITY_SELECTION_HANDLER_INPUTS)
    assert selector_ids <= set(capabilities)
    assert {key: (capabilities[key]["handler"], capabilities[key]["input"])
            for key in selector_ids} == CAPABILITY_SELECTION_HANDLER_INPUTS
    # Q23 remains an existing composable family, not a capability_selection adapter.
    assert set(capabilities) - selector_ids == {"member_bill_sponsorship"}
    assert set(capabilities) == {
        "bill_lookup", "seanad_entry", "member_lookup", "dail_parties_and_groups",
        "term_count", "house_terms", "dail_seats", "office_holding_evidence",
        "office_holding_window", "shared_dail_terms_graph",
        "anchored_shared_constituency_graph", "member_bill_sponsorship",
    }
    assert capabilities["office_holding_evidence"]["handler"] == "composable_office_evidence"
    assert capabilities["office_holding_evidence"]["input"] == "member_and_office"
    assert capabilities["office_holding_window"]["handler"] == "composable_office"
    assert capabilities["seanad_entry"]["handler"] == "stage_a"
    assert capabilities["bill_lookup"]["handler"] == "stage_b"
    assert capabilities["member_bill_sponsorship"]["handler"] == "composable_bill_sponsorship"
    assert capabilities["term_count"]["handler"] == "stage_a"
    assert capabilities["house_terms"]["handler"] == "stage_a"
    assert capabilities["dail_seats"]["handler"] == "stage_c"
    from jsonschema import Draft202012Validator
    schema_validator = Draft202012Validator(draft_schema)
    for capability, parameters in (
        ("term_count", {"member": "Micheál Martin"}),
        ("term_count", {}),
        ("house_terms", {"date": "2022-04-18"}),
        ("house_terms", {"month": 3, "year": 2023}),
        ("dail_seats", {"termNumber": 34}),
        ("dail_parties_and_groups", {"termNumber": 12, "includeGroups": False}),
        ("shared_dail_terms_graph", {"memberA": "Micheál Martin", "memberB": "Mary Lou McDonald"}),
        ("anchored_shared_constituency_graph", {"anchor": "Róisín Shortall"}),
    ):
        schema_validator.validate(_selection(capability, parameters))
    from poc.nlq.composable_semantic_planner import build_composable_planner_instructions
    instructions = build_composable_planner_instructions()
    assert 'family "capability_selection"' in instructions
    assert "every locally recorded typed dated activity" in instructions
    assert "earliest evidenced Seanad membership start date" in instructions
    assert "publishedDate" in instructions
    assert "Member term count" in instructions or "recorded Dáil terms" in instructions
    assert "complete named month" in instructions
    assert "recorded seat complement" in instructions


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
        "In how many distinct Dáil terms has Micheál Martin served?",
        "term_count", {"member": "Micheál Martin"}, "stage_a",
    ),
    (
        "How many Dáil terms did Aengus Ó Snodaigh serve?",
        "term_count", {"member": "Aengus Ó Snodaigh"}, "stage_a",
    ),
    (
        "How many Dáil terms are recorded in the Houses dataset?",
        "term_count", {}, "stage_a",
    ),
    (
        "Could you tell me which Dáil was in force on 18 April 2022?",
        "house_terms", {"date": "2022-04-18"}, "stage_a",
    ),
    (
        "Please tell me which Dáil term was active during March 2023.",
        "house_terms", {"month": 3, "year": 2023}, "stage_a",
    ),
    (
        "How many seats were in the 34th Dáil?",
        "dail_seats", {"termNumber": 34}, "stage_c",
    ),
    (
        "How many seats were there in the 32nd Dáil?",
        "dail_seats", {"termNumber": 32}, "stage_c",
    ),
    (
        "What were the parties during the 12th Dáil?",
        "dail_parties_and_groups", {"termNumber": 12, "includeGroups": False}, "stage_c",
    ),
    (
        "Please list the parties and groups in the 34th Dáil.",
        "dail_parties_and_groups", {"termNumber": 34, "includeGroups": True}, "stage_c",
    ),
    (
        "Which parliamentary groups were in the 32nd Dáil?",
        "dail_parties_and_groups", {"termNumber": 32, "includeGroups": True}, "stage_c",
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
    from poc.nlq.stage_c import stage_c_request_family

    assert parse_stage_a_question(question) is None
    assert plan_stage_b(question, as_of=AS_OF) is None
    assert stage_c_request_family(question) is None
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
    expected_queries = {
        "seanad_entry": 2, "term_count": 2 if parameters.get("member") else 1,
        "dail_parties_and_groups": 2,
    }
    assert len(fixture.queries) == expected_queries.get(capability, 1)
    if capability == "seanad_entry":
        assert "First Seanad entry" in response.text
        assert "2002-09-12" in response.text
        assert "27th Seanad" in response.text
        assert "members:SeanadMembership" in fixture.queries[-1]
        assert "members:DailMembership" not in fixture.queries[-1]
    elif capability == "bill_lookup":
        assert "Pregnancy Loss (Miscellaneous Provisions) Bill 2025" in response.text
        assert "First Stage: 2025-02-20" in response.text
        assert "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23" in response.text
        assert "BillDelivery" in fixture.queries[-1]
        assert "eli:has_part" in fixture.queries[-1]
        assert "SERVICE" not in fixture.queries[-1].upper()
        assert "FROM NAMED" not in fixture.queries[-1].upper()
    elif capability == "term_count":
        assert "Distinct Dáil terms" in response.text
        assert ("2" if parameters.get("member") else "5") in response.text
        if parameters.get("member"):
            assert "SELECT DISTINCT ?term" in fixture.queries[-1]
        else:
            assert "COUNT(DISTINCT ?term)" in fixture.queries[-1]
    elif capability == "house_terms":
        assert "33rd Dáil" in response.text
        assert "term-date match does not establish" in response.text
        assert "dcat:startDate" in fixture.queries[-1]
    elif capability == "dail_seats":
        assert "Seats" in response.text and "160" in response.text
        assert "agents:seats" in fixture.queries[-1]
    elif capability == "dail_parties_and_groups":
        assert "Fianna Fáil" in response.text
        if parameters["includeGroups"]:
            assert "ParliamentaryGroup data is missing" in response.text
            assert "Term-scoped ParliamentaryParty records" in response.text
            assert "ParliamentaryGroup" not in fixture.queries[-1]
        else:
            assert "ParliamentaryGroup" not in response.text
        assert "members:activeDuringTerm" in fixture.queries[-1]
    assert deterministic in {"stage_a", "stage_b", "stage_c"}


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
    (
        "How many Dáil terms has Micheál Martin served in as a Fianna Fáil TD?",
        _selection("term_count", {"member": "Micheál Martin"}),
    ),
    (
        "How many Dáil terms are recorded in the Houses data for the 33rd Dáil?",
        _selection("term_count", {}),
    ),
    (
        "Could you tell me which Dáil was active during March 2023 while Micheál Martin was serving?",
        _selection("house_terms", {"month": 3, "year": 2023}),
    ),
    (
        "How many seats were in the 34th Dáil during 2020?",
        _selection("dail_seats", {"termNumber": 34}),
    ),
    (
        "What parties were in the 34th Dáil excluding Labour?",
        _selection("dail_parties_and_groups", {"termNumber": 34, "includeGroups": False}),
    ),
    (
        "How many members served in the 33rd Dáil?",
        _selection("dail_seats", {"termNumber": 33}),
    ),
])
def test_capability_selector_cannot_drop_requested_relationships_or_hallucinate_inputs(question, draft):
    with pytest.raises((InvalidComposableDraft, ValueError)):
        validate_composable_plan_draft(draft, question=question)


@pytest.mark.parametrize(("question", "capability", "parameters"), [
    (
        "How many distinct Dáil terms appear in Brendan Howlin's membership record?",
        "term_count", {"member": "Brendan Howlin"},
    ),
    (
        "How many distinct Dáil terms appear in Catherine Connolly's membership record?",
        "term_count", {"member": "Catherine Connolly"},
    ),
    (
        "How many Dáil terms are linked to Mary Lou McDonald's recorded memberships?",
        "term_count", {"member": "Mary Lou McDonald"},
    ),
    (
        "Which Dáil term or terms were in existence on 1 September 1997?",
        "house_terms", {"date": "1997-09-01"},
    ),
    (
        "Which Dáil term or terms were in existence during November 2024?",
        "house_terms", {"month": 11, "year": 2024},
    ),
    (
        "Which Dáil term or terms were in existence during February 2020?",
        "house_terms", {"month": 2, "year": 2020},
    ),
    (
        "Identify the Dáil terms that existed in July 2002.",
        "house_terms", {"month": 7, "year": 2002},
    ),
    (
        "What was the seat complement of the 28th Dáil?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "Give the House-owned seat total for Dáil number 33.",
        "dail_seats", {"termNumber": 33},
    ),
    (
        "How many members were in the 34th Dáil?",
        "dail_seats", {"termNumber": 34},
    ),
    (
        "List the parliamentary parties recorded for Dáil 30; I am not asking for groups.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "Give the recorded parties for Dáil number 29, excluding parliamentary groups.",
        "dail_parties_and_groups", {"termNumber": 29, "includeGroups": False},
    ),
    (
        "Which parliamentary groups were in the 32nd Dáil?",
        "dail_parties_and_groups", {"termNumber": 32, "includeGroups": True},
    ),
])
def test_phase1_capability_slots_accept_published_and_independent_wording(question, capability, parameters):
    selected, unsupported = validate_composable_plan_draft(
        _selection(capability, parameters), question=question,
    )
    assert unsupported is None
    assert selected == {
        "family": "capability_selection", "capability": capability, "parameters": parameters,
    }


@pytest.mark.parametrize(("question", "capability", "parameters"), [
    (
        "How many Dáil terms appear in Brendan Howlin's membership record on 14 June 1994?",
        "term_count", {"member": "Brendan Howlin"},
    ),
    (
        "How many Dáil terms did Brendan Howlin serve as a Labour Party TD?",
        "term_count", {"member": "Brendan Howlin"},
    ),
    (
        "How many Dáil terms appear in Brendan Howlin's membership record for Wexford?",
        "term_count", {"member": "Brendan Howlin"},
    ),
    (
        "How many Dáil terms did Brendan Howlin serve as a woman?",
        "term_count", {"member": "Brendan Howlin"},
    ),
    (
        "How many Dáil terms appear in Brendan Howlin's membership record in Dáil 31 and Dáil 32?",
        "term_count", {"member": "Brendan Howlin"},
    ),
    (
        "Which Dáil term was active during March 2023 while a Labour TD was serving?",
        "house_terms", {"month": 3, "year": 2023},
    ),
    (
        "Which Dáil term was active during March 2023 for Wexford?",
        "house_terms", {"month": 3, "year": 2023},
    ),
    (
        "Which Dáil terms existed in March 2023 for women?",
        "house_terms", {"month": 3, "year": 2023},
    ),
    (
        "Which Dáil term existed on 1 September 1997 and 2 September 1997?",
        "house_terms", {"date": "1997-09-01"},
    ),
    (
        "Which Dáil term was active on 1997-09-01 during September 1997?",
        "house_terms", {"date": "1997-09-01"},
    ),
    (
        "What was the seat complement of the 28th Dáil during 2020?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "What was the seat complement of the 28th Dáil for Labour?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "What was the seat complement of the 28th Dáil in Wexford?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "What was the seat complement of the 28th Dáil for women?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "How many distinct Members served in the 32nd Dáil?",
        "dail_seats", {"termNumber": 32},
    ),
    (
        "What was not the seat complement of the 28th Dáil?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "What was the seat complement of the 28th and 29th Dáil?",
        "dail_seats", {"termNumber": 28},
    ),
    (
        "List parliamentary parties recorded for Dáil 30 during March 2020.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "List parties in Dáil 30 excluding Labour.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "List parliamentary parties in Dáil 30 whose Members represented Wexford.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "List parliamentary parties in Dáil 30 with women TDs.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "List parliamentary parties recorded for Dáil 30 and the 31st Dáil.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "List parties and groups recorded for Dáil 30.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": False},
    ),
    (
        "Which parliamentary groups were in the 32nd Dáil?",
        "dail_parties_and_groups", {"termNumber": 32, "includeGroups": False},
    ),
    (
        "List the parties and groups in Dáil 30, but exclude groups.",
        "dail_parties_and_groups", {"termNumber": 30, "includeGroups": True},
    ),
])
def test_phase1_capability_slot_extras_never_reach_answer_execution(
    question, capability, parameters, monkeypatch,
):
    from poc.nlq import app as app_module

    fixture = CapabilityFixture()
    generator = FixedPlanGenerator(_selection(capability, parameters))
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})

    assert response.status_code == 200
    assert 'data-outcome="answer"' not in response.text
    assert "Validated composable query plan" not in response.text
    assert not fixture.queries


@pytest.mark.parametrize(("question", "draft"), [
    (
        "How many Dáil terms has Micheál Martin served in?",
        {**_selection("term_count", {"member": "Micheál Martin"}), "answer": {"kind": "count", "referent": "term", "distinctBy": "identity"}},
    ),
    (
        "How many seats were in the 34th Dáil?",
        {**_selection("dail_seats", {"termNumber": 34}), "answer": {"kind": "entities", "referent": "term"}},
    ),
    (
        "How many people represented Dublin in the 34th Dáil?",
        _selection("member_lookup", {"member": "Dublin", "house": "Dail"}),
    ),
    (
        "How many parties were in the 34th Dáil?",
        _selection("dail_parties_and_groups", {"termNumber": 34, "includeGroups": False}),
    ),
])
def test_count_gate_only_admits_validated_capability_aggregates(question, draft):
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question=question)
