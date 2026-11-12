"""v0.5 deterministic tests: injected model controls and exact compiler replay.

These are not actual model-generated research or independent editorial acceptance.
"""
import copy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from poc.nlq.research_app import create_app
from poc.nlq.research_assertions import Narrative, accept_narrative, facts_from
from poc.nlq.research_collaborator import ResearchRun
from poc.nlq.research_tools import ResearchTools
from poc.nlq.vocabulary import supported_predicates
from tools.diagnose_retrieval_satisfaction import load_bundle, Replay, ROOT, SPONSOR, CAREER

AS_OF = date(2026, 11, 12)


@pytest.fixture(scope="module")
def compiler_evidence():
    bundle = load_bundle()
    records = {r["question"]: r for r in bundle["live"] if r["controlledProposal"] is None}
    predicates = supported_predicates(ROOT / "ontology")
    result = {}
    for tool, name, question in [("sponsorship", "Malcolm Byrne", SPONSOR), ("career", "Mary Lou McDonald", CAREER),
                                 ("lifecycle", None, "Tell me about Bill 11 from 2020")]:
        client = Replay(records[question]["queries"])
        adapter = ResearchTools(client, predicates, context_id="test", endpoint_id="frozen-replay")
        task = {"tool": tool, "member": name, "requirementId": "r0"}
        bill = {"billIri": "https://data.oireachtas.ie/ie/oireachtas/bill/2020/11", "numbers": ["11"], "years": ["2020"]} if tool == "lifecycle" else None
        env = adapter.execute(task, AS_OF.isoformat(), bill=bill)
        assert client.position == len(client.queries)
        assert env["outcome"] == "answer", env
        result[tool] = env
    return result


def test_real_compiler_replay_exposes_exact_identity_roles_and_history(compiler_evidence):
    sponsor = compiler_evidence["sponsorship"]
    bills = sponsor["data"]["bills"]
    assert len(bills) == len({b["billIri"] for b in bills})
    assert all(b["ownerGraph"] and b["participations"] for b in bills)
    assert {p["primaryStatus"][0] for b in bills for p in b["participations"]} == {"Primary", "Supporting"}
    lifecycle = compiler_evidence["lifecycle"]["data"]["lifecycle"][0]
    assert lifecycle["recordedStatus"] == "Current"
    assert {e["date"] for e in lifecycle["events"]} >= {"2025-01-29", "2025-03-27"}
    career = compiler_evidence["career"]["data"]["representation"]
    assert len({r["constituency"] for r in career}) == len({r["term"] for r in career}) == 4
    assert all("start" not in r and "office" not in r for r in career)


def test_authority_projection_has_no_stronger_predicates_and_reproducible_count(compiler_evidence):
    facts = [a for e in compiler_evidence.values() for a in facts_from(e)]
    assert {a["level"] for a in facts} == {1, 2}
    assert all(a["confidence"] is None and a["reviewStatus"] == "provisional" for a in facts)
    assert all(a["evidenceRefs"] and a["limitations"] for a in facts)
    assert {a["proposition"][0] for a in facts} == {"sponsorship", "distinct_bill_count", "recorded_status", "recorded_activity", "representation"}
    count = next(a for a in facts if a["level"] == 2)
    assert len(count["proposition"][1]) == len(compiler_evidence["sponsorship"]["data"]["bills"])
    assert "cardinality" in count["reasoning"]
    failed = copy.deepcopy(compiler_evidence["sponsorship"])
    failed["outcome"] = "execution_failure"
    assert facts_from(failed) == []


def paragraph(facts, **changes):
    return {"key": "reading", "text": "A cautious reading suggests the available records need further review; they do not establish final outcomes.",
            "level": 3, "factRefs": [next(iter(facts))], "reasoning": "A recorded observation supports only this bounded reading.",
            "assumptions": [], "conflicts": [], "limitations": ["Incomplete coverage"], "confidence": "moderate",
            "confidenceRationale": "Relevant but sparse evidence, no independent corroboration; missing history and competing explanations remain."} | changes


@pytest.mark.parametrize("change", [{"level": 1}, {"level": 2}, {"confidence": "97%"},
    {"text": "I am 99% confident"}, {"factRefs": ["invented"]}, {"confidenceRationale": None}, {"confidence": None},
    {"factRefs": []}, {"reviewStatus": "reviewed by the researcher"}])
def test_injected_promotion_and_confidence_controls(compiler_evidence, change):
    facts = {a["id"]: a for a in facts_from(compiler_evidence["sponsorship"])}
    with pytest.raises(ValueError):
        accept_narrative(paragraph(facts, **change), facts, "findings")


def test_provisional_interpretation_and_segregated_hypothesis(compiler_evidence):
    facts = {a["id"]: a for a in facts_from(compiler_evidence["sponsorship"])}
    a = accept_narrative(paragraph(facts), facts, "findings")
    assert a["level"] == 3 and a["reviewStatus"] == "provisional"
    revised = accept_narrative(paragraph(facts, text="The evidence suggests further checking is needed."), facts, "findings", a)
    assert revised["id"] == a["id"]
    hypothesis = paragraph(facts, level=4, text="What factors might explain differences in progress?", confidence=None, confidenceRationale=None)
    with pytest.raises(ValueError):
        accept_narrative(hypothesis, facts, "findings")
    assert accept_narrative(hypothesis, facts, "further_questions")["confidence"] is None


def plan(tasks=None, revision="Write a useful bounded briefing"):
    return {"title": "Research draft", "interpretation": "Investigate sponsorship and recorded progress, not definitive outcomes.",
            "response": "I will identify recorded Bills and look for their recorded developments.", "responseNarrative": None, "clarification": None,
            "requirements": [{"wording": "Bills and outcomes", "conditions": ["recorded sponsorship", "progress", "final outcomes"],
                              "disposition": "partly supported", "explanation": "Final outcomes remain unestablished."}],
            "tasks": tasks or [], "revisionInstructions": revision}


def sponsor_task():
    return {"id": "sponsors", "question": "Which Bills have recorded sponsorship?", "relevance": "Identify candidates for progress research.",
            "role": "supporting", "tool": "sponsorship", "member": "Malcolm Byrne", "sourceTask": None}


class InjectedModel:
    def __init__(self, plans=None):
        self.plans = plans or [plan([sponsor_task()]), plan(revision="Shorten the explanation without changing facts")]
        self.calls = []

    def generate(self, phase, payload):
        self.calls.append(phase)
        if phase == "plan":
            return self.plans.pop(0)
        facts = payload["facts"]
        text = "A cautious reading suggests these sponsorship records are a starting point; final outcomes remain unestablished."
        if payload["revisionInstructions"].startswith("Shorten"):
            text = "The records suggest a starting point, not final outcomes."
        return {"response": "I have updated the draft and retained the source facts.", "responseNarrative": None, "sections": [
            {"id": "findings", "title": "What the records establish", "kind": "findings", "factRefs": [next(iter(facts))],
             "narrative": [paragraph(facts, text=text)]}], "unanswered": ["Definitive outcomes remain unanswered."]}


class AcceptedAdapter:
    def __init__(self, env):
        self.env, self.calls = env, 0

    def execute(self, *args, **kwargs):
        self.calls += 1
        return copy.deepcopy(self.env)


def test_plan_before_dispatch_and_genuine_editorial_revision_reuses_facts(compiler_evidence):
    model = InjectedModel()
    adapter = AcceptedAdapter(compiler_evidence["sponsorship"])
    r = ResearchRun("Investigate Bills and progress", AS_OF, adapter, lambda: model)
    assert r.status == "Plan published" and adapter.calls == 0
    assert r.tasks[0]["toolMeaning"] and r.requirements[0]["originalWording"] == r.brief
    r.step(0)
    assert adapter.calls == 1 and r.facts
    r.step(r.version)
    before = copy.deepcopy(r.facts)
    assertion_id = r.sections[0]["assertionRefs"][0]
    r.message("Shorten the explanation")
    r.step(r.version)
    assert adapter.calls == 1 and before == r.facts
    assert r.sections[0]["assertionRefs"] == [assertion_id]
    assert r.assertions[assertion_id]["text"] == "The records suggest a starting point, not final outcomes."
    assert r.brief == "Investigate Bills and progress" and len(r.requirements) == 2
    exported = r.markdown()
    assert "Draft — for review" in exported and "Provisional interpretation" in exported
    assert "moderate qualitative confidence" in exported and "Definitive outcomes remain unanswered" in exported
    assert assertion_id in exported and next(iter(r.evidence)) in exported


def test_failures_and_invalid_report_preserve_previous_findings(compiler_evidence):
    model = InjectedModel()
    adapter = AcceptedAdapter(compiler_evidence["sponsorship"])
    r = ResearchRun("Bills", AS_OF, adapter, lambda: model)
    r.step(0); r.step(r.version)
    before = copy.deepcopy(r.sections)
    model.generate = lambda phase, payload: {"invalid": "report"}
    r.author_pending = True
    r.step(r.version)
    assert r.sections == before and r.facts


def test_unrelated_or_guessed_lifecycle_is_not_dispatched():
    p = sponsor_task() | {"id": "guess", "tool": "lifecycle", "member": None, "sourceTask": "invented"}
    model = InjectedModel([plan([p])])
    r = ResearchRun("Bills", AS_OF, None, lambda: model)
    assert not r.tasks and not r.evidence


def test_http_plan_is_query_free_and_multiturn_endpoint(compiler_evidence):
    model = InjectedModel()
    with TestClient(create_app(planner_factory=lambda: model, client_factory=lambda: pytest.fail("No query during planning"), reporting_date=AS_OF)) as c:
        initial = c.post("/runs", json={"brief": "Bills and progress"}).json()
        assert initial["status"] == "Plan published" and initial["evidence"] == {}
        response = c.post(f"/runs/{initial['id']}/messages", json={"text": "Shorten the report", "sectionId": None})
        assert response.status_code == 200
        assert len(response.json()["messages"]) == 4
        assert c.get(f"/runs/{initial['id']}/archive").json()["modelCalls"]
        assert c.post("/runs", json={"brief": "Bills"}, headers={"origin": "https://untrusted.test"}).status_code == 403


def test_no_iri_or_extra_tool_fields():
    from poc.nlq.research_tools import ToolTask
    for changes in ({"member": "https://data.oireachtas.ie/member/guess"}, {"sparql": "SELECT * {}"}, {"tool": "web"}):
        with pytest.raises(ValueError):
            ToolTask.model_validate(sponsor_task() | changes)


def test_transport_failure_produces_no_established_facts():
    class Broken:
        def query(self, sparql):
            raise RuntimeError("injected transport failure")

    predicates = supported_predicates(ROOT / "ontology")
    env = ResearchTools(Broken(), predicates, context_id="test", endpoint_id="injected").execute(
        {"tool": "sponsorship", "member": "Malcolm Byrne", "requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] != "answer" and env["data"] is None
    assert env["execution"]["queries"][0]["outcome"] == "execution_failure"
    assert facts_from(env) == []


def test_changed_member_parameters_use_existing_resolver_not_demonstration_name():
    from poc.nlq.research_tools import draft_for
    for name in ("Ivana Bacik", "Lynn Ruane", "Joe O'Brien"):
        question, draft = draft_for("sponsorship", name, AS_OF)
        assert name in question and draft["referents"]["member"]["mention"] == name
        assert "Malcolm Byrne" not in str(draft)
        assert not any("iri" in r for r in draft["referents"].values())


def test_failed_lifecycle_lookup_does_not_invalidate_sponsorship(compiler_evidence):
    sponsor = sponsor_task()
    lifecycle = sponsor | {"id": "progress", "tool": "lifecycle", "member": None, "sourceTask": "sponsors"}
    model = InjectedModel([plan([sponsor, lifecycle])])
    adapter = AcceptedAdapter(compiler_evidence["sponsorship"])
    r = ResearchRun("Bills and progress", AS_OF, adapter, lambda: model)
    r.step(0); r.step(r.version)
    original = copy.deepcopy(r.facts)
    failed = copy.deepcopy(compiler_evidence["lifecycle"])
    failed.update(outcome="execution_failure", data=None, error={"message": "Injected read failure"})
    failed["validation"]["accepted"] = False
    adapter.env = failed
    r.step(r.version)
    assert r.facts == original and r.sections
    assert r.tasks[1]["billResults"][0]["outcome"] == "execution_failure"
    assert r.unanswered


def test_stale_step_is_idempotent_and_session_has_bounded_turns(compiler_evidence):
    model = InjectedModel()
    adapter = AcceptedAdapter(compiler_evidence["sponsorship"])
    r = ResearchRun("Bills", AS_OF, adapter, lambda: model)
    r.step(0)
    before = r.view()
    assert r.step(0) == before and adapter.calls == 1
    r.turn = 12
    with pytest.raises(ValueError):
        r.message("More research")


def test_duplicate_section_ids_are_repaired_not_silently_overwritten(compiler_evidence):
    model = InjectedModel()
    original_generate = model.generate
    outputs = []

    def generate(phase, payload):
        draft = original_generate(phase, payload)
        if phase == "report":
            outputs.append(payload)
            if len(outputs) == 1:
                draft["sections"].append(copy.deepcopy(draft["sections"][0]))
        return draft

    model.generate = generate
    r = ResearchRun("Bills", AS_OF, AcceptedAdapter(compiler_evidence["sponsorship"]), lambda: model)
    r.step(0); r.step(r.version)
    assert len(outputs) == 2 and "structuralCorrection" in outputs[1]
    assert len(r.sections) == 1 and r.sections[0]["assertionRefs"]


def test_editorial_title_and_unrelated_sections_survive(compiler_evidence):
    model = InjectedModel()
    r = ResearchRun("Bills", AS_OF, AcceptedAdapter(compiler_evidence["sponsorship"]), lambda: model)
    r.step(0); r.step(r.version)
    title = r.title
    r.sections.append({"id": "unrelated", "title": "Earlier research", "kind": "findings", "state": "Draft — for review",
                       "factRefs": [], "assertionRefs": [], "evidenceRefs": []})
    r.message("Shorten overview")
    r.step(r.version)
    assert r.title == title and r.sections[-1]["id"] == "unrelated"


def test_model_fact_handles_are_exact_and_stable_not_fuzzy_ids(compiler_evidence):
    model = InjectedModel()
    r = ResearchRun("Bills", AS_OF, AcceptedAdapter(compiler_evidence["sponsorship"]), lambda: model)
    r.step(0)
    aliases = r._aliases()
    assert aliases["f1"] == next(iter(r.facts))
    assert set(r._context()["facts"]) == set(aliases)
    r.step(r.version)
    assert r.sections[0]["factRefs"] == [aliases["f1"]]
    assert all(ref in r.facts for a in r.assertions.values() for ref in a["factRefs"])
    assert r.modelCalls[-1]["factReferenceMap"] == aliases
    assert r._aliases() == aliases


def test_partly_supported_gaps_are_visible_without_author_repeating_them(compiler_evidence):
    model = InjectedModel()
    original = model.generate

    def no_repeated_gap(phase, payload):
        draft = original(phase, payload)
        if phase == "report":
            draft["unanswered"] = []
        return draft

    model.generate = no_repeated_gap
    r = ResearchRun("Bills", AS_OF, AcceptedAdapter(compiler_evidence["sponsorship"]), lambda: model)
    r.step(0); r.step(r.version)
    assert "Final outcomes remain unestablished." in r.markdown()
    assert any(u["reason"] == "Final outcomes remain unestablished." for u in r.view()["unanswered"])


def test_substantive_conversation_has_its_own_exact_provisional_assertion(compiler_evidence):
    model = InjectedModel()
    original = model.generate

    def explain(phase, payload):
        draft = original(phase, payload)
        if phase == "report":
            a = paragraph(payload["facts"])
            draft.update(response=a["text"], responseNarrative=a)
        return draft

    model.generate = explain
    r = ResearchRun("Bills", AS_OF, AcceptedAdapter(compiler_evidence["sponsorship"]), lambda: model)
    r.step(0); r.step(r.version)
    message = r.messages[-1]
    a = r.assertions[message["assertionRef"]]
    assert a["text"] == message["text"] and a["level"] == 3 and a["confidence"] == "moderate"
    assert all(ref in r.facts for ref in a["factRefs"])
    narrative = paragraph(r.facts, text="A different companion statement.")
    with pytest.raises(ValueError):
        r._response_assertion("Unsupported stronger conversational assertion", Narrative.model_validate(narrative))


def test_new_factual_domain_cannot_rewrite_unrelated_existing_sections(compiler_evidence):
    career = sponsor_task() | {"id": "career", "tool": "career", "member": "Mary Lou McDonald"}
    model = InjectedModel([plan([sponsor_task()]), plan([career])])
    adapter = AcceptedAdapter(compiler_evidence["sponsorship"])
    r = ResearchRun("Bills", AS_OF, adapter, lambda: model)
    r.step(0); r.step(r.version)
    before = copy.deepcopy(r.sections)
    title = r.title
    r.message("Add a career section, retain the Bill research")
    adapter.env = compiler_evidence["career"]
    r.step(r.version); r.step(r.version)
    # Injected author tries to rewrite the old findings section; coordinator
    # preserves it because it belongs to the earlier factual requirement.
    assert r.sections == before and r.title == title
    assert any(a["proposition"][0] == "representation" for a in r.facts.values())
