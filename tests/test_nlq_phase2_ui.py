"""HTTP/browser integration tests for the structured Phase 2 query path."""

from __future__ import annotations

import asyncio
import json
from html import unescape

import httpx

from poc.nlq import app as app_module
from poc.nlq.errors import NLQError
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.plan_sparql import GenerationResult
from poc.nlq.results import QueryResult
from poc.nlq.safety import validate_sparql
from poc.nlq.vocabulary import supported_predicates


ROOT = app_module.ROOT
QUESTION = "What is the full name of Timmy Dooley?"
_MEMBER_IRI = "https://data.oireachtas.ie/ie/oireachtas/member/id/timmy-dooley"


def _draft(*, intent: str = "Return the full name of the requested Member.") -> dict:
    return {
        "draftSchemaVersion": 1,
        "intent": intent,
        "entities": [{"id": "member", "type": "Member", "label": "Timmy Dooley"}],
        "requirements": [{
            "id": "name",
            "fact": "member_full_name",
            "subject": {"entity": "member", "type": None},
            "object": None,
        }],
        "filters": [],
        "temporalConstraints": [],
        "aggregation": None,
        "answerShape": {"kind": "fact", "target": "name", "entityType": None},
    }


class FakePlanGenerator:
    output = json.dumps(_draft(), ensure_ascii=False)
    calls: list[str] = []

    def __init__(self, *_args, **_kwargs):
        pass

    def generate(self, question: str) -> str:
        type(self).calls.append(question)
        return type(self).output

    def close(self):
        pass


class FakeFuseki:
    entity_rows: tuple[tuple[str, str], ...] = ((_MEMBER_IRI, "Timmy Dooley"),)
    answer_error: Exception | None = None
    resolver_queries: list[str] = []
    context_queries: list[str] = []
    answer_queries: list[str] = []

    def __init__(self, *_args, **_kwargs):
        pass

    def readiness(self):
        return FusekiReadiness(
            "ready", True,
            (("Houses", True), ("Parties", True), ("Constituencies", True),
             ("Members", True), ("Bills", False)),
            "Required graph families are present.",
        )

    def query(self, sparql: str) -> QueryResult:
        if "SELECT DISTINCT ?entity ?label" in sparql:
            type(self).resolver_queries.append(sparql)
            return QueryResult(
                "select", ("entity", "label"), type(self).entity_rows,
            )
        if "?contextType ?contextLabel" in sparql:
            type(self).context_queries.append(sparql)
            return QueryResult("select", ("contextType", "contextLabel"), ())
        type(self).answer_queries.append(sparql)
        if type(self).answer_error is not None:
            raise type(self).answer_error
        return QueryResult(
            "select", ("name",), (("Timmy Dooley",),),
            raw_json=json.dumps({
                "head": {"vars": ["name"]},
                "results": {"bindings": [{"name": {"type": "literal", "value": "Timmy Dooley"}}]},
            }),
        )

    def close(self):
        pass


def _reset_fakes(monkeypatch, *, draft: dict | None = None, entity_rows=None):
    FakePlanGenerator.calls = []
    FakePlanGenerator.output = json.dumps(draft if draft is not None else _draft(), ensure_ascii=False)
    FakeFuseki.resolver_queries = []
    FakeFuseki.context_queries = []
    FakeFuseki.answer_queries = []
    FakeFuseki.answer_error = None
    FakeFuseki.entity_rows = (
        ((_MEMBER_IRI, "Timmy Dooley"),) if entity_rows is None else entity_rows
    )
    monkeypatch.setattr(app_module, "ResponsesPlanGenerator", FakePlanGenerator)
    monkeypatch.setattr(app_module, "FusekiQueryClient", FakeFuseki)
    monkeypatch.setenv("NLQ_LLM_API_KEY", "test-key")


def _post(question: str = QUESTION, *, mode: str | None = None):
    async def submit():
        transport = httpx.ASGITransport(app=app_module.create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            data = {"question": question}
            if mode is not None:
                data["mode"] = mode
            return await client.post("/ask", data=data)

    return asyncio.run(submit())


def test_browser_post_defaults_to_structured_pipeline_and_executes_safe_query(monkeypatch):
    _reset_fakes(monkeypatch)
    response = _post()

    assert response.status_code == 200
    assert FakePlanGenerator.calls == [QUESTION]
    assert len(FakeFuseki.resolver_queries) == 1
    assert len(FakeFuseki.answer_queries) == 1
    generated = FakeFuseki.answer_queries[0]
    assert validate_sparql(
        generated, supported_predicates=supported_predicates(ROOT / "ontology"),
    ) == generated
    assert "Validated query plan" in response.text
    assert "Generated SPARQL" in response.text
    assert "Return the full name of the requested Member." in unescape(response.text)
    assert "Timmy Dooley" in response.text
    assert 'value="phase2" selected' in response.text


def test_ambiguous_entity_is_explained_and_no_answer_query_is_run(monkeypatch):
    _reset_fakes(
        monkeypatch,
        entity_rows=(
            (_MEMBER_IRI, "Timmy Dooley"),
            ("https://data.oireachtas.ie/ie/oireachtas/member/id/another-timmy", "Timmy Dooley"),
        ),
    )
    response = _post()

    assert response.status_code == 200
    assert "Ambiguous entity" in response.text
    assert "no record was selected and no answer query was run" in response.text
    assert response.text.count("Timmy Dooley") >= 2
    assert FakeFuseki.context_queries
    assert FakeFuseki.answer_queries == []
    assert "Generated SPARQL" not in response.text


def test_unresolved_entity_is_explained_and_no_answer_query_is_run(monkeypatch):
    _reset_fakes(monkeypatch, entity_rows=())
    response = _post()

    assert response.status_code == 200
    assert "Entity not found" in response.text
    assert "No exact local match was found for Member “Timmy Dooley”" in response.text
    assert "No answer query was run" in response.text
    assert FakeFuseki.answer_queries == []


def test_unsupported_semantic_request_fails_closed_without_exposing_diagnostic_as_message(monkeypatch):
    _reset_fakes(
        monkeypatch,
        draft=_draft(intent=(
            "The requested voting information is not represented by the available semantic facts."
        )),
    )
    response = _post("How did Timmy Dooley vote?")

    assert response.status_code == 200
    assert "Unsupported question" in response.text
    assert "not supported by the current Phase 2 query path" in response.text
    assert FakeFuseki.resolver_queries == []
    assert FakeFuseki.answer_queries == []


def test_planner_failure_is_reported_without_raw_exception_as_primary_message(monkeypatch):
    _reset_fakes(monkeypatch)
    FakePlanGenerator.output = "not valid planner JSON"
    response = _post()

    assert response.status_code == 200
    assert "Planner could not complete" in response.text
    assert "could not produce a usable query plan" in response.text
    assert "Raw Structured planner response payload" in response.text
    assert FakeFuseki.answer_queries == []


def test_sparql_validation_failure_is_clear_and_query_is_not_executed(monkeypatch):
    _reset_fakes(monkeypatch)

    class RejectingGenerator:
        def __init__(self, **_kwargs):
            pass

        def generate(self, _planner_result):
            return GenerationResult(
                "safety_failure", failure_class="sparql_safety_validation",
                failure_reason="deliberate validation-test diagnostic",
                failure_stage="sparql_safety",
            )

    monkeypatch.setattr(app_module, "PlanSparqlGenerator", RejectingGenerator)
    response = _post()

    assert response.status_code == 200
    assert "Query validation failed" in response.text
    assert "did not pass validation" in response.text
    assert "deliberate validation-test diagnostic" in unescape(response.text)
    assert FakeFuseki.answer_queries == []


def test_fuseki_execution_failure_has_safe_message_and_debug_details(monkeypatch):
    _reset_fakes(monkeypatch)
    FakeFuseki.answer_error = NLQError(
        "Fuseki returned HTTP 503 while querying.",
        debug_output='{"error":"temporarily unavailable"}',
    )
    response = _post()

    assert response.status_code == 200
    assert "Query execution failed" in response.text
    assert "validated query could not be completed by Fuseki" in response.text
    assert "Fuseki returned HTTP 503" not in response.text.split("Query execution failed", 1)[0]
    assert "temporarily unavailable" in unescape(response.text)
    assert len(FakeFuseki.answer_queries) == 1
