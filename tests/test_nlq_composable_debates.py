"""Bounded Q28/Q29 tests over reviewed sitting/record RDF patterns."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF

from poc.nlq.composable_plan import (
    PlanError,
    compile_answer_query,
    execute_question,
    plan_question,
    validate_plan,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AGENTS = "https://data.oireachtas.ie/ontology#"
ELI_DL = "http://data.europa.eu/eli/eli-draft-legislation-ontology#"
DATE = date(2026, 10, 25)


class DebateFixture:
    """Small non-authoritative evidence fixture; includes a written-answer record."""

    def __init__(self, *, dail=True, seanad=True, multiple=False):
        self.dataset = Dataset()
        self.queries: list[str] = []
        self._add_sitting("dail", dail, multiple=multiple)
        self._add_sitting("seanad", seanad)
        written_graph = URIRef("https://data.oireachtas.ie/graph/debate/dail/2015-07-02/writtens")
        written = URIRef("https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens")
        graph = self.dataset.graph(written_graph)
        graph.add((written, RDF.type, URIRef(AGENTS + "DebateRecord")))
        graph.add((written, URIRef(AGENTS + "debateDate"), Literal("2015-07-02T00:00:00", datatype=URIRef("http://www.w3.org/2001/XMLSchema#dateTime"))))

    def _add_sitting(self, chamber: str, enabled: bool, *, multiple=False):
        if not enabled:
            return
        graph_iri = URIRef(f"https://data.oireachtas.ie/graph/debate/{chamber}/2015-07-02/debate")
        graph = self.dataset.graph(graph_iri)
        records = [f"https://data.oireachtas.ie/akn/ie/debateRecord/{chamber}/2015-07-02/debate"]
        if multiple:
            records.append(f"https://data.oireachtas.ie/akn/ie/debateRecord/{chamber}/2015-07-02/debate/extra")
        for index, record_text in enumerate(records):
            record = URIRef(record_text)
            sitting = URIRef(record_text + "#sitting")
            graph.add((record, RDF.type, URIRef(AGENTS + "DebateRecord")))
            graph.add((record, URIRef(AGENTS + "debateDate"), Literal("2015-07-02T00:00:00", datatype=URIRef("http://www.w3.org/2001/XMLSchema#dateTime"))))
            graph.add((sitting, RDF.type, URIRef(AGENTS + "DebateSitting")))
            graph.add((sitting, URIRef(AGENTS + "producedRecord"), record))
            graph.add((sitting, URIRef(ELI_DL + "activity_date"), Literal("2015-07-02", datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))))

    def readiness(self):
        return FusekiReadiness("ready", True, (), "bounded Debates fixture")

    def close(self):
        pass

    def query(self, query: str):
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type == "ASK":
            return QueryResult("ask", boolean=bool(result.askAnswer))
        columns = tuple(str(variable) for variable in result.vars)
        rows = tuple(tuple(str(value) if value is not None else "—" for value in row) for row in result)
        return QueryResult("select", columns, rows)


def test_q28_uses_actual_sitting_and_renders_readable_official_link(monkeypatch):
    from poc.nlq import app as app_module

    fixture = DebateFixture(seanad=False)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-10-25")
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Show me the Dáil debate from 2 July 2015.", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Thursday 2 July 2015" in response.text
    assert 'href="https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate"' in response.text
    assert "Official debate record" in response.text
    assert "writtens" not in response.text
    assert "SELECT DISTINCT ?sitting ?date ?record" in fixture.queries[-1]


def test_q29_is_boolean_and_written_answer_record_is_not_a_sitting():
    fixture = DebateFixture(dail=False, seanad=True)
    outcome = execute_question(
        "Was there a Seanad debate on 2 July 2015?", as_of=DATE, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "success"
    assert outcome.result.kind == "ask" and outcome.result.boolean is True
    assert "DebateSitting" in outcome.sparql and "producedRecord" in outcome.sparql
    assert "debateDate" not in outcome.sparql


def test_q29_empty_result_is_unknown_without_coverage_not_a_confirmed_no():
    outcome = execute_question(
        "Was there a Seanad debate on 2 July 2015?", as_of=DATE,
        fuseki=DebateFixture(dail=True, seanad=False),
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "coverage is not certified complete" in outcome.diagnostic


def test_q28_missing_sitting_does_not_promote_written_answer_record():
    outcome = execute_question(
        "Show me the Dáil debate from 2 July 2015.", as_of=DATE,
        fuseki=DebateFixture(dail=False, seanad=False),
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "written-answer records do not establish a sitting" in outcome.diagnostic


def test_multiple_matching_records_are_all_returned_not_arbitrarily_selected():
    outcome = execute_question(
        "Show me the Dáil debate from 2 July 2015.", as_of=DATE,
        fuseki=DebateFixture(seanad=False, multiple=True),
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "success"
    assert len(outcome.result.rows) == 2
    assert len({row[1] for row in outcome.result.rows}) == 2


@pytest.mark.parametrize("mutation", ["unused", "unsupported"])
def test_reusable_relationship_path_rejects_unused_or_unsupported_elements(mutation):
    supported = supported_predicates(ROOT / "ontology")
    plan = plan_question("Was there a Seanad debate on 2 July 2015?", as_of=DATE)
    if mutation == "unused":
        plan["referents"]["orphan"] = {"type": "DebateRecord"}
    else:
        plan["relations"][0]["fact"] = "invented_relationship"
    with pytest.raises(PlanError):
        validate_plan(plan)
    valid = plan_question("Was there a Seanad debate on 2 July 2015?", as_of=DATE)
    produced_record = URIRef(AGENTS + "producedRecord")
    with pytest.raises(PlanError, match="not allowlisted"):
        compile_answer_query(valid, supported_predicates=supported - {produced_record})


@pytest.mark.parametrize(("referent", "attribute", "value"), [
    ("sitting", "selector", {"kind": "invented"}),
    ("sitting", "constraints", []),
    ("record", "selector", {"kind": "invented"}),
    ("record", "answer", True),
    ("record", "mention", "Dáil"),
])
def test_debate_referents_reject_unsupported_attributes(referent, attribute, value):
    plan = plan_question("Was there a Seanad debate on 2 July 2015?", as_of=DATE)
    plan["referents"][referent][attribute] = value
    with pytest.raises(PlanError, match="unsupported or missing attributes"):
        validate_plan(plan)


def test_q28_and_q29_share_the_same_validated_compiled_relationship_path():
    supported = supported_predicates(ROOT / "ontology")
    entity_plan = plan_question("Show me the Dáil debate from 2 July 2015.", as_of=DATE)
    boolean_plan = plan_question("Was there a Dáil debate on 2 July 2015?", as_of=DATE)
    entity_query = compile_answer_query(entity_plan, supported_predicates=supported)
    boolean_query = compile_answer_query(boolean_plan, supported_predicates=supported)
    assert "producedRecord" in entity_query and "producedRecord" in boolean_query
    assert "FILTER(REGEX(STR(?debateGraph)" in entity_query
    assert entity_query.startswith("PREFIX") and "SELECT DISTINCT" in entity_query
    assert "ASK WHERE" in boolean_query


def test_ask_no_match_diagnostic_says_query_ran(monkeypatch):
    from poc.nlq import app as app_module

    fixture = DebateFixture(dail=False, seanad=False)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-10-25")
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Was there a Seanad debate on 2 July 2015?", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "The read-only answer query ran, but returned no matching result." in response.text
    assert "No answer query was executed after this resolution failure." not in response.text
    assert fixture.queries and fixture.queries[-1].startswith("PREFIX")
