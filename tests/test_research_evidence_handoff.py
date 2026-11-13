"""Real compiler fixtures plus explicitly injected handoff/failure controls."""
from dataclasses import replace
import json

import pytest

from poc.nlq.composable_plan import PlanOutcome
from poc.nlq.query_evidence import finalize_evidence
from poc.nlq.research_assertions import facts_from
from poc.nlq.research_collaborator import ResearchRun
from poc.nlq.research_outcomes import classify, require_plain_language
from poc.nlq.results import QueryResult
from test_nlq_committee_members import Fixture, Generator, draft, COMMITTEE
from test_nlq_composable_stage_a import StageAFixture
from test_query_evidence_interoperability import consume, records
from test_research_general_queries import adapter, query, AS_OF
from test_research_v05 import InjectedModel, AcceptedAdapter, plan


CURRENT = "Who are the current members of the Committee of Public Accounts?"
HISTORY = "What is the membership history of the Committee of Public Accounts?"
CHRONOLOGY = "When did each Dáil start and finish?"


def committee_env():
    fixture = Fixture()
    fixture.member("Jane")
    fixture.member("Jane", episode="2", start="2026-10-01T00:00:00")
    fixture.member("Former", end="2026-01-01T00:00:00")
    fixture.member("Future", start="2027-01-01T00:00:00")
    return consume(fixture, CURRENT, semantic_plan_generator_factory=lambda: Generator(draft("Committee of Public Accounts")))


def test_committee_and_independent_chronology_use_same_consumption_and_display():
    env, evidence, facts = committee_env()
    assert env["researchOutcome"]["kind"] == "findings_available"
    assert env["factualEvidenceStatus"] == "available"
    assert len(facts) == 2  # source episodes, not a new count or complete roster
    assert len(env["execution"]["queries"]) == 2
    assert all(f.participants["committee"].iri == COMMITTEE for f in evidence.facts)
    assert all(len(f.intervals) == 3 for f in evidence.facts)
    assert all(f.scope["committeeOwner"]["witnesses"][0]["termStart"].endswith("#date>") for f in evidence.facts)
    assert all(f.witnesses[0]["memberGraph"] and f.witnesses[0]["start"].endswith("#dateTime>") for f in evidence.facts)
    table = records(facts, ["member", "committee", "as_of"])
    assert table["rows"][0]["cells"][0]["text"] == "Jane"
    assert "complete roster" in table["qualification"]
    env, evidence, facts = consume(StageAFixture(), CHRONOLOGY)
    assert env["researchOutcome"]["kind"] == "findings_available"
    assert len(evidence.facts) > 1 and all(f.predicate == "recorded_house_term_dates" for f in evidence.facts)
    assert records(facts, ["term", "start", "end"])["columns"] == ["Dáil term", "House start", "House end"]
    assert all(f.witnesses[0]["term"] == f.participants["term"].iri for f in evidence.facts)
    assert all(f.intervals[0].rangeIri is None for f in evidence.facts)  # not exposed by this operation
    assert not env["resolvedScope"]["parentRequirementSatisfied"]


def test_shared_boundary_never_projects_arbitrary_rows_or_untyped_model_facts():
    outcome = PlanOutcome("success", plan={}, sparql="SELECT", result=QueryResult("select", ("name",), (("Jane",),)))
    assert finalize_evidence(outcome).factual_evidence_status == "unavailable"
    bad = finalize_evidence(replace(outcome, validated_facts=({"kind": "entity", "text": "invented"},)))
    assert bad.factual_evidence is None and bad.factual_evidence_status == "invalid"
    assert "typed accepted facts" in bad.diagnostic


@pytest.mark.parametrize("status,result,accepted,expected", [
    ("success", QueryResult("select", ("name",), (("Jane",),)), True, "findings_available"),
    ("success", QueryResult("select", ("name",), (("Jane",),)), False, "integration_unavailable"),
    ("success", QueryResult("select", ("name",), ()), False, "no_matching_records"),
    ("success", QueryResult("ask", boolean=False), False, "integration_unavailable"),
    ("unsupported_request", None, False, "unsupported_question"),
    ("ambiguous", None, False, "clarification_required"),
    ("not_found", None, False, "identity_unresolved"),
    ("source_data_unavailable", None, False, "evidence_incomplete"),
    ("execution_failure", None, False, "execution_failure"),
    ("validation_failure", None, False, "query_validation_failure"),
])
def test_structured_outcomes_have_distinct_plain_descriptions(status, result, accepted, expected):
    outcome = classify(PlanOutcome(status, result=result, diagnostic="compiler status / SPARQL exploded",
        selection_outcome="no_matches" if expected == "no_matching_records" else None),
        accepted=accepted, plan_validated=True, execution_completed=True)
    assert outcome["kind"] == expected
    require_plain_language(outcome["label"] + outcome["description"])
    assert "exploded" not in outcome["description"]


def test_completed_empty_selection_requires_valid_plan_and_completed_read():
    out = PlanOutcome("success", result=QueryResult("select"))
    assert classify(out, accepted=False, plan_validated=False, execution_completed=True)["kind"] != "no_matching_records"
    assert classify(out, accepted=False, plan_validated=True, execution_completed=False)["kind"] != "no_matching_records"
    assert classify(out, accepted=False, plan_validated=True, execution_completed=True)["kind"] != "no_matching_records"


def test_real_dated_selection_zero_is_not_mislabelled_records_found():
    from test_nlq_composable_party_temporal import _current_term_fixture, _representation_member_draft
    fixture = _current_term_fixture(constituency_label="Meath East",
        membership_interval=("2024-11-29T00:00:00", "2025-12-31T00:00:00"))
    proposal = _representation_member_draft(constituency="Meath East")
    proposal["constraints"] = [{"referent": "membership", "field": "membershipInterval", "operator": "on", "value": "2026-10-28"}]
    env = adapter(fixture, semantic_plan_generator_factory=lambda: Generator(proposal)).execute(
        query("How many TDs represented Meath East in this Dáil on 2026-10-28?") | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["queryServiceResult"]["rows"] == [["0"]]
    assert env["researchOutcome"]["kind"] == "no_matching_records"
    assert env["selectionOutcome"] == "no_matches"
    assert env["outcome"] == "answer" and env["error"] is None
    assert env["data"]["queryResult"]["result"]["rows"] == [["0"]]
    assert "not proof that no Member served" in env["diagnostic"]
    assert not facts_from(env)


def test_unsupported_history_does_not_claim_parliamentary_absence():
    refusal = {"version": 2, "supported": False, "family": None, "unsupportedReason": "Historical committee membership is not available.",
               "intent": HISTORY, "referents": None, "relations": [], "constraints": [], "answer": None}
    env = adapter(Fixture(), semantic_plan_generator_factory=lambda: Generator(refusal)).execute(
        query(HISTORY) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["researchOutcome"]["kind"] == "unsupported_question"
    assert "does not show" in env["error"]["message"]
    assert not facts_from(env)
    assert env["diagnostic"] or env["error"]["technicalMessage"]


class OutcomeAuthor(InjectedModel):
    def generate(self, phase, payload):
        if phase == "investigate":
            return {"tasks": [], "explanation": "No further questions can be checked here."}
        if phase == "report":
            # Inject a misleading explanation: without facts the coordinator's
            # final response must use execution outcomes, not this model claim.
            return {"response": "No parliamentary membership records exist.", "responseNarrative": None,
                    "sections": [], "unanswered": [], "resolvedQuestions": []}
        return super().generate(phase, payload)


def drain(run):
    for _ in range(20):
        if not run.has_work():
            return
        run.step(run.version)
    raise AssertionError("Research did not finish")


def test_missing_optional_handoff_still_presents_original_result(monkeypatch):
    from poc.nlq import query_evidence
    original = query_evidence.finalize_evidence
    monkeypatch.setattr(query_evidence, "finalize_evidence", lambda out: original(replace(out, validated_facts=())))
    env = adapter(StageAFixture()).execute(query(CHRONOLOGY) | {"requirementId": "r0"}, AS_OF.isoformat())
    model = OutcomeAuthor([plan([query(CHRONOLOGY)])])
    run = ResearchRun(CHRONOLOGY, AS_OF, AcceptedAdapter(env), lambda: model)
    drain(run)
    assert not run.facts and run.sections and run.results
    assert run.status == "Findings available — some questions unanswered"
    assert run.view()["sections"][0]["results"][0]["rows"]
    assert "couldn't be safely included" not in run.markdown()
    assert "No parliamentary membership records exist" not in run.messages[-1]["text"]
    assert "structured factual boundary" in json.dumps(run.evidence)  # optional diagnostic only
    assert "structured factual boundary" not in json.dumps(run.view()["limitations"])
    assert "## Unanswered research questions\n\n##" not in run.markdown()


def test_unknown_selection_success_does_not_claim_records_were_found_in_run_status(monkeypatch):
    from poc.nlq import query_evidence
    original = query_evidence.finalize_evidence
    monkeypatch.setattr(query_evidence, "finalize_evidence", lambda out: original(
        replace(out, validated_facts=(), selection_outcome=None)))
    env = adapter(StageAFixture()).execute(query(CHRONOLOGY) | {"requirementId": "r0"}, AS_OF.isoformat())
    model = OutcomeAuthor([plan([query(CHRONOLOGY)])])
    run = ResearchRun(CHRONOLOGY, AS_OF, AcceptedAdapter(env), lambda: model)
    drain(run)
    assert run.status == "Findings available — some questions unanswered"
    assert not run.facts and run.sections and run.results
    assert next(iter(run.results.values()))["selectionOutcome"] is None
    assert run.view()["sections"][0]["results"][0]["columns"] == env["queryServiceResult"]["columns"]


def test_execution_error_plain_message_keeps_exact_developer_diagnostic():
    class Broken:
        def query(self, sparql):
            raise RuntimeError("injected transport detail 457")
    env = adapter(Broken()).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["researchOutcome"]["kind"] == "execution_failure"
    assert "search could not be completed" in env["error"]["message"]
    assert "457" not in env["error"]["message"]
    assert "457" in json.dumps(env["execution"])


def test_partial_research_keeps_findings_first_and_unanswered_separately():
    current, _, _ = committee_env()
    refusal = {"version": 2, "supported": False, "family": None, "unsupportedReason": "No speech content analysis.",
               "intent": "What did these Members say about housing?", "referents": None, "relations": [], "constraints": [], "answer": None}
    speech = query("What did these Members say about housing?", id="speech")
    unsupported = adapter(Fixture(), semantic_plan_generator_factory=lambda: Generator(refusal)).execute(
        speech | {"requirementId": "r0"}, AS_OF.isoformat())
    class Mixed:
        def execute(self, task, *args, **kwargs):
            return current if task["question"] == CURRENT else unsupported
    class Author(OutcomeAuthor):
        def generate(self, phase, payload):
            if phase == "report":
                return {"response": "The findings are shown first; the speech question remains unanswered.", "responseNarrative": None,
                    "sections": [{"id": "members", "title": "Recorded members", "kind": "findings", "factRefs": [], "narrative": [],
                        "tables": [{"caption": "Recorded members", "kind": "records", "columns": ["member", "committee", "as_of"],
                                    "factRefs": list(payload["facts"]), "activityRefs": []}]}],
                    "unanswered": [], "resolvedQuestions": []}
            return super().generate(phase, payload)
    model = Author([plan([query(CURRENT), speech])])
    run = ResearchRun(CURRENT + " Also investigate what Members said about housing.", AS_OF, Mixed(), lambda: model)
    drain(run)
    assert run.facts and run.sections and run.view()["unanswered"]
    assert run.status == "Findings available — some questions unanswered"
    exported = run.markdown()
    assert exported.index("Jane") < exported.index("## Evidence limitations") < exported.index("## Unanswered research questions")
    assert "unsupported capability" not in exported.split("## Assertion evidence and reasoning")[0].lower()
    assert "proposition" in exported and "queryRefs" in exported


def test_unrelated_followup_does_not_mark_validated_section_as_populating():
    current, _, _ = committee_env()

    def committee_plan(task):
        result = plan([task])
        result["requirements"] = [{"kind": "research_question", "wording": CURRENT,
            "conditions": ["committee membership", "reporting date"], "disposition": "partly supported",
            "explanation": "The available records identify committee membership at the reporting date."}]
        return result

    class SectionAuthor(InjectedModel):
        def generate(self, phase, payload):
            if phase == "report":
                refs = list(payload["facts"])
                question_id = payload["requirements"][0]["proposedConditions"][0]["id"]
                return {"response": "The available records identify these members at the reporting date.",
                    "responseNarrative": None,
                    "sections": [{"id": "current-members", "title": "Recorded current members", "kind": "findings",
                        "factRefs": refs, "narrative": [], "tables": []}],
                    "unanswered": [], "resolvedQuestions": [{"requirementRef": question_id,
                        "explanation": "The accepted records identify these members at the stated date.", "factRefs": refs}]}
            return super().generate(phase, payload)

    model = SectionAuthor([committee_plan(query(CURRENT)), committee_plan(query(HISTORY, id="history"))])
    run = ResearchRun(CURRENT, AS_OF, AcceptedAdapter(current), lambda: model)
    run.step(run.version)  # First accepted search.
    run.step(run.version)  # Publish a section backed by the accepted records.
    assert run.view()["sections"][0]["state"] == "Validated"
    run.message("Also investigate a separate historical membership question.")
    state = run.view()
    assert state["hasWork"] and any(task["state"] == "Pending" for task in state["tasks"])
    assert state["sections"] and state["sections"][0]["state"] == "Validated"


@pytest.mark.parametrize("text", ["evidence shape", "factual boundary", "promoted fact", "compiler status",
    "projection", "unsupported capability", "SPARQL", "Member IRIs"])
def test_plain_language_policy_rejects_implementation_language(text):
    with pytest.raises(ValueError):
        require_plain_language(text)


def test_plain_language_policy_does_not_mistake_names_for_technical_abbreviations():
    assert require_plain_language("Iris asked about committee membership.")


def test_author_context_keeps_grounded_clarification_choices_but_not_technical_causes():
    from test_nlq_composable_q06 import Q06Fixture
    env = adapter(Q06Fixture(ambiguous=True)).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    model = OutcomeAuthor([plan([query()])])
    run = ResearchRun("Party history", AS_OF, AcceptedAdapter(env), lambda: model)
    run.step(run.version)
    outcome = run._context()["operationOutcomes"][0]
    assert outcome["clarificationCandidates"] == env["error"]["candidates"]
    assert len(outcome["clarificationCandidates"]) == 2
    assert "diagnostic" not in outcome and "compilerStatus" not in outcome
