"""General-path controls: real compiler over existing fixtures, not live/model claims."""
import json
from datetime import date

import pytest

from poc.nlq.composable_plan import PlanOutcome
from poc.nlq.research_assertions import facts_from
from poc.nlq.research_collaborator import ResearchRun, PLAN_INSTRUCTIONS
from poc.nlq.research_evidence import accept_query_evidence
from poc.nlq.research_tools import ResearchTools, ToolTask, discovery_context
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates
from test_nlq_composable_q06 import Q06Fixture, ROOT
from test_research_v05 import InjectedModel, plan, AcceptedAdapter
from tools.diagnose_retrieval_satisfaction import load_bundle, Replay, SPONSOR

AS_OF = date(2026, 11, 13)


def query(question="What parties was Stephen Donnelly a member of?", **changes):
    return {"id": "investigation", "question": question, "relevance": "Investigate the requested parliamentary records.",
            "role": "direct", "tool": "query", "member": None, "sourceTask": None} | changes


def adapter(client, **kwargs):
    return ResearchTools(client, supported_predicates(ROOT / "ontology"), context_id="test",
                         endpoint_id="synthetic", **kwargs)


def test_general_party_history_reaches_existing_compiler_but_cannot_promote_rendered_rows():
    env = adapter(Q06Fixture(missing_affiliation_dates=True)).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["compilerStatus"] == "success" and env["queryServiceOutcome"] == "answer"
    assert env["outcome"] == "missing_or_unaccepted_evidence"
    assert env["validation"]["planValidated"] and env["validation"]["executionCompleted"]
    assert env["queryServiceResult"]["columns"] == ["Political affiliation", "Supporting membership episodes"]
    assert "dates not recorded" in str(env["queryServiceResult"])
    assert env["data"] is None and facts_from(env) == []
    assert len(env["execution"]["queries"]) == 2
    assert not env["resolvedScope"]["parentRequirementSatisfied"]


@pytest.mark.parametrize("fixture, expected", [
    (Q06Fixture(ambiguous=True), "clarification_required"),
    (Q06Fixture(missing_memberships=True), "missing_or_unaccepted_evidence"),
    (Q06Fixture(missing_identity=True), "missing_or_unaccepted_evidence"),
])
def test_general_outcomes_keep_candidates_and_missing_evidence(fixture, expected):
    env = adapter(fixture).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == expected and facts_from(env) == []
    if expected == "clarification_required":
        assert len(env["error"]["candidates"]) == 2
        assert len(env["execution"]["queries"]) == 1


def test_general_sponsorship_reuses_existing_accepted_compiler_witnesses():
    bundle = load_bundle()
    record = next(r for r in bundle["live"] if r["controlledProposal"] is None and r["question"] == SPONSOR)
    replay = Replay(record["queries"])
    env = adapter(replay).execute(query(SPONSOR) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer", env
    facts = facts_from(env)
    assert {f["proposition"][0] for f in facts} == {"sponsorship", "distinct_bill_count"}
    assert all("Malcolm Byrne" in f["text"] for f in facts if f["level"] == 1)
    assert env["data"]["memberName"] == "Malcolm Byrne"


def test_generic_query_uses_existing_semantic_selector_and_retains_proposal():
    # Unsupported whole intent: no answer/identity reads and no weaker query.
    fixture = Q06Fixture()
    env = adapter(fixture).execute(query("When was Stephen Donnelly elected?") | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "unsupported_capability" and not fixture.queries
    proposal = {"version": 2, "supported": False, "family": None, "unsupportedReason": "No transcript analysis.",
                "intent": "Investigate speeches", "referents": None, "relations": [], "constraints": [], "answer": None}

    class Fixed:
        def generate(self, prompt):
            return json.dumps(proposal)

    env = adapter(fixture, semantic_plan_generator_factory=Fixed).execute(
        query("Explain the speeches delivered by the Member") | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] != "answer" and not fixture.queries
    assert env["execution"]["plannerProposals"][0]["output"] == json.dumps(proposal)


def test_discovery_is_derived_from_service_not_three_research_tools():
    context = discovery_context()
    assert "member_party_history" in str(context)
    assert "current_committee_members" in str(context)
    assert "Use query" in PLAN_INSTRUCTIONS
    assert ToolTask.model_validate(query()).question == query()["question"]


def test_after_a_limitation_model_can_publish_another_relevant_question_before_dispatch():
    class Model(InjectedModel):
        def generate(self, phase, payload):
            if phase == "investigate":
                assert payload["originalBrief"] == "Party history and constituency background"
                assert payload["operationOutcomes"][0]["outcome"] == "missing_or_unaccepted_evidence"
                self.calls.append(phase)
                return {"tasks": [query("Which constituencies did Stephen Donnelly represent?", id="background", role="supporting")],
                        "explanation": "Investigate the independently requested constituency background, not party dates."}
            if phase == "report":
                return {"response": "The retrieved response cannot yet be promoted to research facts.", "responseNarrative": None,
                        "sections": [], "unanswered": [{"requirementRef": "r0-q0", "question": "What party dates can be established?"}],
                        "resolvedQuestions": []}
            return super().generate(phase, payload)

    env = adapter(Q06Fixture()).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    evidence = AcceptedAdapter(env)
    model = Model([plan([query()])])
    run = ResearchRun("Party history and constituency background", AS_OF, evidence, lambda: model)
    run.step(run.version)  # query
    run.step(run.version)  # report limitation without invented facts
    run.step(run.version)  # publish the new plan, no query
    assert evidence.calls == 1 and len(run.tasks) == 2
    assert run.tasks[1]["state"] == "Pending" and run.tasks[1]["role"] == "supporting"
    assert run.view()["unanswered"] and run.facts == {}
    assert run.evidence and "queryServiceResult" in run.markdown()


def test_unknown_accepted_evidence_shape_and_unvalidated_results_never_become_facts():
    outcome = PlanOutcome("success", plan={"referents": {}}, result=QueryResult("select", ("x",), (("y",),)),
                          accepted_evidence={"futureShape": [{"claim": "do not trust me"}]})
    data, limitation = accept_query_evidence(outcome, [])
    assert data is None and "not supported" in limitation


def test_general_transport_failure_retains_failed_read():
    class Broken:
        def query(self, sparql):
            raise RuntimeError("transport failure")

    env = adapter(Broken()).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "execution_failure" and facts_from(env) == []
    assert env["execution"]["queries"][0]["outcome"] == "execution_failure"


def test_existing_current_party_witness_authority_survives_general_discovery_and_normalisation():
    from test_research_workspace import fixture
    from poc.nlq.research_adapter import current_party_draft

    class Fixed:
        def generate(self, prompt):
            return json.dumps(current_party_draft("Fine Gael"))

    env = adapter(fixture(), semantic_plan_generator_factory=Fixed).execute(
        query("Who are the Fine Gael Deputies in the current Dáil?") | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer", env
    assert len(env["data"]["members"]) == 1
    assert len(env["data"]["members"][0]["witnesses"]) == 2
    facts = facts_from(env)
    assert len(facts) == 2  # separate accepted episodes, no invented count/calculation
    assert {f["level"] for f in facts} == {1}
    assert all(f["proposition"][0] == "dated_party_membership" for f in facts)
    assert all("2026-11-13" in f["text"] and "complete roster" in f["text"] for f in facts)
    assert all(f["proposition"][3]["queryRefs"] for f in facts)


def test_cache_does_not_confuse_legacy_parameter_changes_with_identical_questions():
    from test_research_v05 import sponsor_task
    model = InjectedModel([plan([sponsor_task()]), plan([sponsor_task() | {"member": "Ivana Bacik"}])])
    run = ResearchRun("Bills", AS_OF, None, lambda: model)
    run.message("Also investigate Ivana Bacik")
    assert [t["member"] for t in run.tasks] == ["Malcolm Byrne", "Ivana Bacik"]


def test_continuation_is_bounded_and_same_query_is_not_reexecuted():
    class Repeating(InjectedModel):
        def generate(self, phase, payload):
            if phase == "investigate":
                return {"tasks": [query()], "explanation": "Repeat the same query (injected negative control)."}
            if phase == "report":
                return {"response": "The evidence is unavailable for factual promotion.", "responseNarrative": None,
                        "sections": [], "unanswered": [], "resolvedQuestions": []}
            return super().generate(phase, payload)

    env = adapter(Q06Fixture()).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    evidence = AcceptedAdapter(env)
    model = Repeating([plan([query()])])
    run = ResearchRun("Party history", AS_OF, evidence, lambda: model)
    for _ in range(10):
        if not run.has_work():
            break
        run.step(run.version)
    assert evidence.calls == 1 and len(run.tasks) == 1 and not run.has_work()
    assert run.investigation_rounds == 1 and run.view()["unanswered"]


def test_current_party_result_mismatch_cannot_be_accepted():
    from test_research_workspace import fixture
    from poc.nlq.research_adapter import current_party_draft
    from poc.nlq.composable_plan import execute_question

    class Fixed:
        def generate(self, prompt):
            return json.dumps(current_party_draft("Fine Gael"))

    outcome = execute_question("Who are the Fine Gael Deputies in the current Dáil?", as_of=AS_OF,
        fuseki=fixture(), supported_predicates=supported_predicates(ROOT / "ontology"), semantic_plan_generator_factory=Fixed)
    from dataclasses import replace
    wrong = replace(outcome, result=QueryResult("select", ("TD", "Member identity"), (("Wrong name", "wrong-identity"),)))
    data, limitation = accept_query_evidence(wrong, [{"queryId": "q-test"}])
    assert data is None and "did not agree" in limitation


def test_general_http_evidence_inspection_archive_and_qualified_export():
    from fastapi.testclient import TestClient
    from poc.nlq.research_app import create_app

    fixture = Q06Fixture()
    model = InjectedModel([plan([query()])])
    with TestClient(create_app(planner_factory=lambda: model, client_factory=lambda: fixture, reporting_date=AS_OF)) as client:
        prepared = client.post("/runs", json={"brief": "Party history"}).json()
        assert prepared["tasks"][0]["tool"] == "query" and not fixture.queries
        run_id = prepared["id"]
        state = client.post(f"/runs/{run_id}/step", json={"version": prepared["version"]}).json()
        ref = next(iter(state["evidence"]))
        env = client.get(f"/runs/{run_id}/evidence/{ref}").json()
        assert env["queryServiceOutcome"] == "answer" and env["outcome"] == "missing_or_unaccepted_evidence"
        assert env["queryServiceResult"]["rows"] and state["facts"] == {}
        assert client.get(f"/runs/{run_id}/archive").json()["modelCalls"]
        exported = client.get(f"/runs/{run_id}/report.md").text
        assert "Draft — for review" in exported and "queryServiceResult" in exported
        assert "no research fact was promoted" in exported


def test_generic_fact_table_preserves_exact_wording_without_capability_mapping():
    from poc.nlq.research_presentation import project_table
    facts = {"f1": {"level": 1, "text": "Exact compiler-supported statement with qualifications.",
                     "proposition": ["any_accepted_proposition", "exact-identity"]}}
    table = project_table({"kind": "facts", "caption": "Recorded findings", "factRefs": ["f1"], "activityRefs": []}, facts)
    assert table["columns"] == ["Recorded finding"]
    assert table["rows"] == [{"cells": [{"text": facts["f1"]["text"], "refs": ["f1"]}], "assertionRefs": ["f1"]}]
    with pytest.raises(ValueError):
        project_table({"kind": "representation", "caption": "Not constituency evidence", "factRefs": ["f1"], "activityRefs": []}, facts)
    facts["f1"]["level"] = 3
    with pytest.raises(ValueError):
        project_table({"kind": "facts", "caption": "Not established", "factRefs": ["f1"], "activityRefs": []}, facts)
