"""Generic reporting over real compiler operations plus labelled injected controls."""
from dataclasses import replace
import json

import pytest

from poc.nlq import research_tools
from poc.nlq.composable_plan import PlanOutcome, execute_question
from poc.nlq.research_collaborator import ResearchRun
from poc.nlq.research_results import result_record, present_result
from poc.nlq.results import QueryResult
from test_research_general_queries import adapter, query, AS_OF
from test_research_v05 import InjectedModel, AcceptedAdapter, plan
from test_research_evidence_handoff import drain, CHRONOLOGY
from test_nlq_composable_stage_a import StageAFixture
from test_nlq_main_composition import proposal, MainTransport
from test_nlq_committee_members import Generator


class NoAuthor(InjectedModel):
    def generate(self, phase, payload):
        if phase == "report":
            raise RuntimeError("Injected report outage, not a query failure")
        if phase == "investigate":
            return {"tasks": [], "explanation": "No further searches needed."}
        return super().generate(phase, payload)


def without_projector(monkeypatch):
    """Disable only the OPTIONAL evidence handoff; service validation still runs."""
    from poc.nlq import query_evidence
    monkeypatch.setattr(query_evidence, "finalize_evidence", lambda out: replace(
        out, factual_evidence=None, factual_evidence_status="unavailable"))


def test_real_chronology_is_reportable_even_without_projector_or_author(monkeypatch):
    without_projector(monkeypatch)
    env = adapter(StageAFixture()).execute(query(CHRONOLOGY) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer" and env["data"]["queryResult"]["result"] == env["queryServiceResult"]
    assert "evidence" not in env["data"]
    model = NoAuthor([plan([query(CHRONOLOGY)])])
    run = ResearchRun(CHRONOLOGY, AS_OF, AcceptedAdapter(env), lambda: model)
    drain(run)
    assert run.results and not run.facts
    assert run.view()["sections"][0]["results"][0]["rows"]
    assert run.report_failure and "Findings available" in run.status
    exported = run.markdown()
    for column in env["queryServiceResult"]["columns"]:
        assert column in exported
    assert CHRONOLOGY in exported and "queryRefs" in exported
    assert "couldn't be safely included" not in exported


def test_real_current_composition_uses_service_typed_transport_and_same_reporting_path():
    question = "Which Fianna Fáil TDs represent Kildare North?"
    env = adapter(MainTransport(), semantic_plan_generator_factory=lambda: Generator(proposal(question, "RP"))).execute(
        query(question) | {"requirementId": "r0"}, "2026-05-01")
    assert env["outcome"] == "answer", env
    assert env["routeId"] == "current_member_composition"
    assert env["compositionReport"]["status"] == "answer"
    assert env["data"]["queryResult"]["compositionRequest"] == env["compositionRequest"]
    assert len(env["execution"]["queries"]) == 6
    assert all(q["stage"] == "typed_composition_select" and q["outcome"] == "returned" for q in env["execution"]["queries"])
    json.dumps(env)  # Typed RDF terms are retained as JSON, not leaked objects.
    table = present_result(env["data"]["queryResult"], env["evidenceId"])
    assert table["rows"][0]["cells"][0]["text"] == "Alice Example"


@pytest.mark.parametrize("question", [
    "When did each Dáil start and finish?",
    "How many Dáil terms are listed in the Houses data?",
    "Was Timmy Dooley a member of the Select Committee on Transport and Communications?",
    "Find Deputy Ó Snodaigh's full name for me.",
])
def test_real_compiler_shapes_without_factual_projection(monkeypatch, question):
    without_projector(monkeypatch)
    env = adapter(StageAFixture()).execute(query(question) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer", env
    assert "evidence" not in env["data"]
    record = env["data"]["queryResult"]
    assert record["result"] == env["queryServiceResult"]
    assert present_result(record, env["evidenceId"])["rows"]


@pytest.mark.parametrize("result", [
    QueryResult("select", ("Member", "Member identity"), (("Example", "https://data.oireachtas.ie/member/example"),)),
    QueryResult("select", ("Party", "Term", "Qualification"), (("Labour", "31st Dáil", "recorded episode only"),)),
    QueryResult("select", ("Start date",), (("2020-02-08^^<http://www.w3.org/2001/XMLSchema#date>",),)),
    QueryResult("select", ("Distinct recorded Members",), (("0",),)),
    QueryResult("ask", boolean=True), QueryResult("ask", boolean=False),
    QueryResult("select", ("Member",), ()),
])
def test_injected_future_result_shapes_need_no_adapter(monkeypatch, result):
    # Inject ONLY a future successful service return after a real validated plan
    # and completed compiler reads, not a claim of live semantic capability.
    real = execute_question
    def future(question, **kwargs):
        out = real(CHRONOLOGY, **kwargs)
        return replace(out, result=result, factual_evidence=None, validated_facts=(),
                       factual_evidence_status="unavailable", selection_outcome=None,
                       diagnostic="Qualified local records only.")
    monkeypatch.setattr(research_tools, "execute_question", future)
    env = adapter(StageAFixture()).execute(query("Injected future family question") | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer"
    record = env["data"]["queryResult"]
    assert record["question"] == "Injected future family question"
    assert record["qualifications"] == ["Qualified local records only."]
    assert record["plan"] and record["queryRefs"]
    table = present_result(record, env["evidenceId"])
    if result.kind == "ask":
        assert table["rows"][0]["cells"][0]["text"] == str(result.boolean).lower()
    else:
        assert table["columns"] == list(result.columns)
        assert [[c["text"] for c in row["cells"]] for row in table["rows"]] == [list(r) for r in result.rows]


@pytest.mark.parametrize("status", ["execution_failure", "validation_failure", "unsupported_request", "ambiguous", "source_data_unavailable"])
def test_failed_service_result_cannot_masquerade_as_success(status):
    out = PlanOutcome(status, result=QueryResult("select", ("Member",), (("Do not report",),)))
    with pytest.raises(ValueError, match="successful"):
        result_record(out, question="Question", reporting_date=AS_OF.isoformat(), queries=[{"outcome": "returned"}])


def test_incomplete_execution_never_reports_success():
    out = PlanOutcome("success", result=QueryResult("ask", boolean=False))
    for trace in ([], [{"outcome": "execution_failure"}]):
        with pytest.raises(ValueError, match="did not complete"):
            result_record(out, question="Question", reporting_date=AS_OF.isoformat(), queries=trace)


def test_generic_results_survive_partial_failure_followups_and_author_revisions(monkeypatch):
    without_projector(monkeypatch)
    env = adapter(StageAFixture()).execute(query(CHRONOLOGY) | {"requirementId": "r0"}, AS_OF.isoformat())
    class Mixed:
        calls = 0
        def execute(self, task, *args, **kwargs):
            self.calls += 1
            if task["question"] == CHRONOLOGY:
                return env
            return {**env, "evidenceId": "e-failed", "outcome": "execution_failure", "data": None,
                "validation": {"accepted": False}, "error": {"message": "Search failed"},
                "researchOutcome": {"kind": "execution_failure", "label": "Search could not be completed", "description": "Search failed"}}
    class Author(InjectedModel):
        def generate(self, phase, payload):
            if phase == "investigate":
                return {"tasks": [], "explanation": "No further searches."}
            if phase == "report":
                return {"response": "The draft has been updated.", "responseNarrative": None,
                    "sections": [{"id": "chronology", "title": "Dáil chronology", "kind": "findings",
                        "factRefs": [], "narrative": [], "tables": [], "resultRefs": ["result1"],
                        "summaries": [{"text": "The returned dates describe recorded Dáil terms, not continuous individual service.", "resultRefs": ["result1"]}]}],
                    "unanswered": [], "resolvedQuestions": []}
            return super().generate(phase, payload)
    model = Author([plan([query(CHRONOLOGY), query("Injected failing subsidiary", id="failed")]), plan([])])
    tools = Mixed()
    run = ResearchRun("Chronology and another question", AS_OF, tools, lambda: model)
    drain(run)
    assert tools.calls == 2 and run.results and run.view()["unanswered"]
    assert "some questions unanswered" in run.status
    assert len(run.sections) == 1 and run.sections[0]["resultRefs"] == [env["evidenceId"]]
    original_result = json.dumps(run.results, sort_keys=True)
    run.message("Revise the explanation without new queries")
    drain(run)
    assert tools.calls == 2 and json.dumps(run.results, sort_keys=True) == original_result
    assert run.view()["sections"][0]["results"][0]["rows"]
    assert "AI-generated draft summary" in run.markdown()


def test_generic_result_refs_cannot_cite_failure_or_invented_answer(monkeypatch):
    without_projector(monkeypatch)
    env = adapter(StageAFixture()).execute(query(CHRONOLOGY) | {"requirementId": "r0"}, AS_OF.isoformat())
    model = NoAuthor([plan([query(CHRONOLOGY)])])
    run = ResearchRun(CHRONOLOGY, AS_OF, AcceptedAdapter(env), lambda: model)
    run.step(run.version)
    with pytest.raises(ValueError, match="successful result"):
        run._canonical_result_refs(["result999"])


def test_unexpected_optional_evidence_error_cannot_veto_original_answer(monkeypatch):
    from poc.nlq import research_evidence
    class BrokenEvidence:
        @classmethod
        def model_validate(cls, value):
            raise RuntimeError("Injected optional record error")
    monkeypatch.setattr(research_evidence, "AcceptedEvidence", BrokenEvidence)
    env = adapter(StageAFixture()).execute(query(CHRONOLOGY) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer" and env["queryServiceResult"]["rows"]
    assert env["data"]["queryResult"]["result"] == env["queryServiceResult"]
    assert "RuntimeError" in env["optionalEvidenceIssue"]


def test_http_composition_reuses_configured_lazy_typed_transport(monkeypatch):
    from fastapi.testclient import TestClient
    from poc.nlq import research_app
    from poc.nlq.research_tools import ResearchTools
    from datetime import date
    question = "Which Fianna Fáil TDs represent Kildare North?"
    class Tools(ResearchTools):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs, semantic_plan_generator_factory=lambda: Generator(proposal(question, "RP")))
    monkeypatch.setattr(research_app, "ResearchTools", Tools)
    model = NoAuthor([plan([query(question)])])
    clients = []
    def client_factory():
        transport = MainTransport()
        clients.append(transport)
        return transport
    with TestClient(research_app.create_app(planner_factory=lambda: model, client_factory=client_factory,
                                          reporting_date=date(2026, 5, 1))) as client:
        state = client.post('/runs', json={"brief": question}).json()
        url = f"/runs/{state['id']}"
        state = client.post(url + '/step', json={"version": state['version']}).json()
        assert not clients  # Planning does not instantiate either transport.
        state = client.post(url + '/step', json={"version": state['version']}).json()
        assert len(clients) == 1 and len(clients[0].calls) == 6
        eid = next(iter(state['queryResults']))
        env = client.get(url + '/evidence/' + eid).json()
        assert env['validation']['compositionValidated'] and env['validation']['serviceValidated']
        assert env['compositionReport']['status'] == 'answer' and env['outcome'] == 'answer'
        assert 'Alice Example' in client.get(url + '/report.md').text
