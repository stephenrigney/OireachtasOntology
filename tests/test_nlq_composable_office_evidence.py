"""Bounded Q7 projection of incomplete, accepted OfficeHolding episodes."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft,
    UnsupportedComposableRequest,
    validate_composable_plan_draft,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 6)
BASE = "https://data.oireachtas.ie/"
MEMBERS = BASE + "ontology/members#"
AGENTS = BASE + "ontology#"
OFFICE_GRAPH = URIRef(BASE + "graph/offices")
TAOISEACH = URIRef(BASE + "office/taoiseach")
FINANCE_MINISTER = URIRef(BASE + "office/finance-minister")


def _selection(member="Bertie Ahern", office="Taoiseach"):
    return {
        "version": 2,
        "supported": True,
        "family": "capability_selection",
        "unsupportedReason": None,
        "intent": "Return accepted local office-holding episode evidence.",
        "referents": {
            "capability": "office_holding_evidence",
            "parameters": {"member": member, "office": office},
        },
        "relations": [],
        "constraints": [],
        "answer": None,
    }


class FixedPlanGenerator:
    def __init__(self, draft):
        self.draft = draft

    def generate(self, question: str) -> str:
        return json.dumps(self.draft)

    def close(self):
        pass


class OfficeEvidenceFixture:
    def __init__(self):
        self.dataset = Dataset()
        self.queries: list[str] = []
        registry = self.dataset.graph(OFFICE_GRAPH)
        for office, label in ((TAOISEACH, "Taoiseach"), (FINANCE_MINISTER, "Minister for Finance")):
            registry.add((office, RDF.type, URIRef(MEMBERS + "NamedOffice")))
            registry.add((office, SKOS.prefLabel, Literal(label, lang="en")))

    def add_member(self, code: str, name: str, episodes, *, office=TAOISEACH):
        graph = self.dataset.graph(URIRef(f"{BASE}graph/member/{code}"))
        member = URIRef(f"{BASE}ie/oireachtas/member/id/{code}")
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, URIRef("http://xmlns.com/foaf/0.1/name"), Literal(name)))
        for index, episode in enumerate(episodes):
            holding = URIRef(f"{member}#office-holding-{index:04d}")
            episode_office = episode.get("office", office)
            graph.add((member, URIRef(MEMBERS + "hasOfficeHolding"), holding))
            graph.add((holding, RDF.type, URIRef(MEMBERS + "OfficeHolding")))
            graph.add((holding, URIRef(MEMBERS + "heldOffice"), episode_office))
            if episode.get("missing_range"):
                continue
            range_iri = URIRef(f"{holding}#date-range")
            graph.add((holding, URIRef(MEMBERS + "hasMembershipDateRange"), range_iri))
            graph.add((range_iri, RDF.type, URIRef(MEMBERS + "DateRange")))
            if episode.get("start") is not None:
                graph.add((range_iri, URIRef(MEMBERS + "StartDate"), Literal(episode["start"], datatype=XSD.dateTime)))
            if episode.get("end") is not None:
                graph.add((range_iri, URIRef(MEMBERS + "EndDate"), Literal(episode["end"], datatype=XSD.dateTime)))
            for start, end in episode.get("conflicting_ranges", []):
                conflicting = URIRef(f"{holding}#conflicting-range")
                graph.add((holding, URIRef(MEMBERS + "hasMembershipDateRange"), conflicting))
                graph.add((conflicting, RDF.type, URIRef(MEMBERS + "DateRange")))
                graph.add((conflicting, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
                if end is not None:
                    graph.add((conflicting, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))
        return str(member)

    def readiness(self):
        families = ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")
        return FusekiReadiness("ready", True, tuple((name, True) for name in families), "bounded office evidence fixture")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type != "SELECT":
            raise AssertionError(f"unexpected query form: {result.type}")
        columns = tuple(str(variable) for variable in result.vars)
        rows = []
        for result_row in result:
            row = []
            for value in result_row:
                if value is None:
                    row.append("—")
                elif isinstance(value, Literal) and value.datatype:
                    row.append(f"{value}^^<{value.datatype}>")
                elif isinstance(value, Literal) and value.language:
                    row.append(f"{value}@{value.language}")
                else:
                    row.append(str(value))
            rows.append(tuple(row))
        return QueryResult("select", columns, tuple(rows))


def _client(monkeypatch, fixture, question, *, member="Bertie Ahern", office="Taoiseach"):
    from poc.nlq import app as app_module

    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    generator = FixedPlanGenerator(_selection(member, office))
    return TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question})


def test_q7_returns_separate_exact_member_and_office_episodes_with_partial_qualification(monkeypatch):
    fixture = OfficeEvidenceFixture()
    fixture.add_member("bertie", "Bertie Ahern", [
        {"start": "2007-06-14T00:00:00", "end": "2008-05-07T00:00:00"},
        {"start": "1997-06-26T00:00:00", "end": "2002-06-06T00:00:00"},
        {"start": "2001-01-01T00:00:00", "end": "2002-01-01T00:00:00", "office": FINANCE_MINISTER},
    ])
    fixture.add_member("other", "Other Taoiseach", [
        {"start": "2010-01-01T00:00:00", "end": "2011-01-01T00:00:00"},
    ])

    response = _client(monkeypatch, fixture, "When was Bertie Ahern the Taoiseach?")

    assert 'data-outcome="answer"' in response.text
    assert "INCOMPLETE LOCAL-RECORDED EPISODES" in response.text
    assert "not a complete career or tenure history" in response.text
    assert "gaps in local records do not mean the Member was not in office" in response.text
    assert "2007-06-14" in response.text and "2008-05-07" in response.text
    assert "1997-06-26" in response.text and "2002-06-06" in response.text
    assert "Other Taoiseach" not in response.text
    assert "Minister for Finance" not in response.text
    assert response.text.count("office-holding-") >= 2
    assert any("LIMIT 100" in query for query in fixture.queries)


def test_same_projection_is_generic_for_a_different_member_and_reviewed_office(monkeypatch):
    fixture = OfficeEvidenceFixture()
    fixture.add_member("finance-holder", "Finance Holder", [
        {"start": "2012-03-01T00:00:00", "end": None},
    ], office=FINANCE_MINISTER)

    response = _client(
        monkeypatch, fixture, "When was Finance Holder the Minister for Finance?",
        member="Finance Holder", office="Minister for Finance",
    )

    assert 'data-outcome="answer"' in response.text
    assert "Finance Holder" in response.text
    assert "Minister for Finance" in response.text
    assert "2012-03-01" in response.text
    assert "Open-ended (no end date recorded)" in response.text
    assert "INCOMPLETE LOCAL-RECORDED EPISODES" in response.text


@pytest.mark.parametrize("question", [
    "When did Bertie Ahern serve as Taoiseach?",
    "During what period was Bertie Ahern Taoiseach?",
])
def test_q7_additional_unfiltered_period_wordings_preserve_the_same_local_episodes(monkeypatch, question):
    fixture = OfficeEvidenceFixture()
    fixture.add_member("bertie", "Bertie Ahern", [
        {"start": "1997-06-26T00:00:00", "end": "2002-06-06T00:00:00"},
        {"start": "2007-06-14T00:00:00", "end": "2008-05-07T00:00:00"},
    ])

    response = _client(monkeypatch, fixture, question)

    assert 'data-outcome="answer"' in response.text
    assert "1997-06-26" in response.text and "2002-06-06" in response.text
    assert "2007-06-14" in response.text and "2008-05-07" in response.text
    assert "INCOMPLETE LOCAL-RECORDED EPISODES" in response.text


def test_no_recorded_episode_is_missing_evidence_not_a_no_tenure_answer(monkeypatch):
    fixture = OfficeEvidenceFixture()
    fixture.add_member("bertie", "Bertie Ahern", [])

    response = _client(monkeypatch, fixture, "When was Bertie Ahern the Taoiseach?")

    assert 'data-outcome="missing_or_unaccepted_evidence"' in response.text
    assert "No accepted local OfficeHolding episode" in response.text
    assert "<h2>Results</h2>" not in response.text


@pytest.mark.parametrize(("field", "drifted_value"), [
    ("handler", "evidence_boundary"),
    ("input", "member_only"),
])
def test_office_dispatch_metadata_drift_fails_before_fuseki(monkeypatch, field, drifted_value):
    import poc.nlq.composable_semantic_planner as semantic_planner

    fixture = OfficeEvidenceFixture()
    fixture.add_member("bertie", "Bertie Ahern", [
        {"start": "2007-06-14T00:00:00", "end": "2008-05-07T00:00:00"},
    ])
    contract = semantic_planner._plan_contract()
    entry = next(item for item in contract["semanticDispatch"]["capabilities"]
                 if item["id"] == "office_holding_evidence")
    entry[field] = drifted_value
    monkeypatch.setattr(semantic_planner, "_plan_contract", lambda: contract)

    response = _client(monkeypatch, fixture, "When was Bertie Ahern the Taoiseach?")

    assert 'data-outcome="validation_failure"' in response.text
    assert "dispatch metadata" in response.text
    assert not fixture.queries


def test_office_episode_projection_paginates_all_rows(monkeypatch):
    fixture = OfficeEvidenceFixture()
    episodes = [
        {"start": f"{1900 + index:04d}-01-01T00:00:00", "end": f"{1900 + index:04d}-12-31T00:00:00"}
        for index in range(105)
    ]
    fixture.add_member("long-career", "Bertie Ahern", episodes)

    response = _client(monkeypatch, fixture, "When was Bertie Ahern the Taoiseach?")

    assert 'data-outcome="answer"' in response.text
    assert response.text.count("office-holding-") >= 105
    assert "2004-01-01" in response.text
    assert any("OFFSET 100" in query for query in fixture.queries)


def test_invalid_episode_on_later_page_discards_the_entire_projection(monkeypatch):
    fixture = OfficeEvidenceFixture()
    episodes = [
        {"start": f"{1800 + index:04d}-01-01T00:00:00", "end": f"{1800 + index:04d}-12-31T00:00:00"}
        for index in range(100)
    ]
    episodes.append({"missing_range": True})
    fixture.add_member("long-career", "Bertie Ahern", episodes)

    response = _client(monkeypatch, fixture, "When was Bertie Ahern the Taoiseach?")

    assert 'data-outcome="missing_or_unaccepted_evidence"' in response.text
    assert "no partial episode list was returned" in response.text
    assert "<h2>Results</h2>" not in response.text
    assert any("OFFSET 100" in query for query in fixture.queries)


@pytest.mark.parametrize("episode", [
    {"missing_range": True},
    {"start": None, "end": "2008-05-07T00:00:00"},
    {"start": "not-a-date", "end": "2008-05-07T00:00:00"},
    {"start": "2008-05-08T00:00:00", "end": "2008-05-07T00:00:00"},
    {"start": "2007-06-14T00:00:00", "end": "2008-05-07T00:00:00",
     "conflicting_ranges": [("2007-06-15T00:00:00", "2008-05-07T00:00:00")]},
])
def test_uncertain_or_conflicting_episode_fails_closed_without_partial_rows(monkeypatch, episode):
    fixture = OfficeEvidenceFixture()
    fixture.add_member("bertie", "Bertie Ahern", [
        {"start": "1997-06-26T00:00:00", "end": "2002-06-06T00:00:00"},
        episode,
    ])

    response = _client(monkeypatch, fixture, "When was Bertie Ahern the Taoiseach?")

    assert 'data-outcome="missing_or_unaccepted_evidence"' in response.text
    assert "no partial episode list was returned" in response.text
    assert "1997-06-26" not in response.text


@pytest.mark.parametrize("question,member,office", [
    ("How long was Bertie Ahern the Taoiseach?", "Bertie Ahern", "Taoiseach"),
    ("When was Bertie Ahern first elected Taoiseach?", "Bertie Ahern", "Taoiseach"),
    ("When was Bertie Ahern elected Taoiseach?", "Bertie Ahern", "Taoiseach"),
    ("When was Bertie Ahern the Taoiseach in 2007?", "Bertie Ahern", "Taoiseach"),
    ("When was Bertie Ahern the Taoiseach while in Fianna Fáil?", "Bertie Ahern", "Taoiseach"),
    ("When did Bertie Ahern serve as Taoiseach while in Fianna Fáil?", "Bertie Ahern", "Taoiseach"),
    ("During what period was Bertie Ahern Taoiseach in 2007?", "Bertie Ahern", "Taoiseach"),
])
def test_election_duration_and_extra_scope_requests_are_rejected(question, member, office):
    with pytest.raises((UnsupportedComposableRequest, InvalidComposableDraft)):
        validate_composable_plan_draft(_selection(member, office), question=question)


def test_exactly_unaccepted_office_does_not_use_raw_observations(monkeypatch):
    fixture = OfficeEvidenceFixture()
    fixture.add_member("stephen", "Stephen Donnelly", [
        {"start": "2020-06-27T00:00:00", "end": "2024-04-09T00:00:00"},
    ])
    generator = FixedPlanGenerator(_selection("Stephen Donnelly", "Minister for Health"))
    from poc.nlq import app as app_module

    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    client = TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: generator,
    ))

    response = client.post("/ask", data={"question": "When was Stephen Donnelly the Minister for Health?"})

    assert 'data-outcome="missing_or_unaccepted_evidence"' in response.text
    assert "Unreviewed ministerial observations are not accepted holdings" in response.text
    assert not any("SELECT DISTINCT ?member_member" in query for query in fixture.queries)
