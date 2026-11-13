"""Synthetic/compiler-replay shape tests, not genuine-model research acceptance."""
import copy
import json
from dataclasses import replace

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from poc.nlq.composable_plan import execute_question, plan_question
from poc.nlq.query_evidence import AcceptedEvidence, Interval
from poc.nlq.research_assertions import facts_from
from poc.nlq.research_evidence import accept_query_evidence
from poc.nlq.research_presentation import project_table
from test_research_general_queries import AS_OF, ROOT, adapter, query
from test_nlq_composable_q06 import Q06Fixture, MEMBERS
from test_nlq_composable_stage_a import StageAFixture
from poc.nlq.vocabulary import supported_predicates


def consume(client, question, **kwargs):
    env = adapter(client, **kwargs).execute(query(question) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] == "answer", env
    evidence = AcceptedEvidence.model_validate(env["data"]["evidence"])
    facts = {f["id"]: f for f in facts_from(env)}
    assert all(f["queryRefs"] and f["evidenceRefs"] and f["limitations"] for f in facts.values())
    return env, evidence, facts


def records(facts, keys):
    return project_table({"kind": "records", "caption": "Recorded findings", "factRefs": list(facts),
                          "activityRefs": [], "columns": keys}, facts)


def test_history_and_independent_calendar_holdout_use_identical_consumption_and_table_path():
    env, evidence, facts = consume(Q06Fixture(), "What parties was Stephen Donnelly a member of?")
    assert {f.kind for f in evidence.facts} == {"episode"}
    assert len(evidence.facts) == 3
    assert len({f.intervals[0].resourceIri for f in evidence.facts}) == 3
    table = records(facts, ["affiliation", "start", "end"])
    assert table["columns"] == ["Party", "Recorded start", "Recorded end"]
    assert len(table["rows"]) == 3 and "gaps" in table["qualification"]
    assert all(len(c["text"].split()) < 5 for row in table["rows"] for c in row["cells"])
    fixture = StageAFixture()
    term = fixture.add_term("Dail", 27, "1992-12-14T00:00:00", "1997-06-06T00:00:00")
    env, evidence, facts = consume(fixture, "Which Dáil was in office during June 1994?")
    assert evidence.facts[0].kind == "entity" and evidence.facts[0].entity.iri == str(term)
    assert evidence.facts[0].scope["selector"] == {"kind": "duringMonth", "month": 6, "year": 1994}
    table = records(facts, ["term", "start", "end"])
    assert table["columns"] == ["Dáil term", "House start", "House end"]
    assert "sitting occurred" in table["qualification"]
    assert evidence.facts[0].witnesses[0]["period"]
    assert env["resolvedScope"]["parentRequirementSatisfied"] is False


def test_current_party_list_and_count_preserve_two_intervals_and_exact_identity():
    from test_research_workspace import fixture
    from poc.nlq.research_adapter import current_party_draft
    for count in (False, True):
        class Fixed:
            def generate(self, prompt):
                return json.dumps(current_party_draft("Fine Gael", count=count))
        env, evidence, facts = consume(fixture(),
            "How many Fine Gael Deputies are in the current Dáil?" if count else "Who are the Fine Gael Deputies in the current Dáil?",
            semantic_plan_generator_factory=Fixed)
        episodes = {ref: f for ref, f in facts.items() if f["proposition"]["kind"] == "episode"}
        assert len(episodes) == 2
        assert all(len(f["proposition"]["intervals"]) == 2 for f in episodes.values())
        assert all("T" in f["proposition"]["intervals"][0]["start"] for f in episodes.values())
        assert records(episodes, ["member", "affiliation", "as_of"])["rows"]
        measures = [f for f in facts.values() if f["level"] == 2]
        assert len(measures) == int(count)
        if count:
            assert measures[0]["proposition"]["value"] == 1  # identities, NOT the two episodes


@pytest.mark.parametrize("changes", [
    {"start": "2020-01-01", "end": "2019-01-01", "endMeaning": "recorded"},
    {"start": "bad-date"}, {"end": None, "endMeaning": "recorded"},
    {"end": "2020-01-01", "endMeaning": "open_ended"},
])
def test_invalid_interval_contract_fails_closed(changes):
    with pytest.raises(ValueError):
        Interval.model_validate({"resourceIri": "https://example.test/episode", "rangeIri": None,
            "start": None, "end": None, "endMeaning": "not_recorded", "meaning": "recorded_episode"} | changes)


def test_source_conflicting_episode_dates_cannot_be_selected_by_last_row():
    fixture = Q06Fixture()
    episode = next(fixture.member_graph.subjects(RDF.type, URIRef(MEMBERS + "PartyMembership")))
    period = next(fixture.member_graph.objects(episode, URIRef(MEMBERS + "hasMembershipDateRange")))
    fixture.member_graph.add((period, URIRef(MEMBERS + "StartDate"), Literal("1990-01-01")))
    env = adapter(fixture).execute(query() | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] != "answer" and facts_from(env) == []


def test_unknown_version_shape_display_rows_and_missing_execution_are_not_authority():
    client = Q06Fixture()
    outcome = execute_question(query()["question"], as_of=AS_OF, fuseki=client,
                               supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.factual_evidence
    assert accept_query_evidence(outcome, [])[0] is None
    assert accept_query_evidence(replace(outcome, factual_evidence=None), [])[0] is None
    bad = copy.deepcopy(outcome.factual_evidence)
    bad["version"] = 2
    assert accept_query_evidence(replace(outcome, factual_evidence=bad), [])[0] is None
    bad = copy.deepcopy(outcome.factual_evidence)
    bad["facts"][0]["kind"] = "future_shape"
    assert accept_query_evidence(replace(outcome, factual_evidence=bad), [])[0] is None


def test_successful_unprojected_operation_is_distinct_from_missing_data_or_unsupported_semantics(monkeypatch):
    # Inject a missing executor handoff, independently of current coverage.
    # Successful readable rows must still never be used as factual authority.
    from poc.nlq import query_evidence
    finalize = query_evidence.finalize_evidence
    monkeypatch.setattr(query_evidence, "finalize_evidence", lambda out: finalize(replace(out, validated_facts=())))
    env = adapter(StageAFixture()).execute(query("When did each Dáil start and finish?") |
                                           {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["compilerStatus"] == "success" and env["queryServiceOutcome"] == "answer"
    assert env["queryServiceResult"]["rows"] and env["validation"]["planValidated"]
    assert env["outcome"] == "missing_or_unaccepted_evidence" and env["data"] is None
    assert facts_from(env) == []
    assert env["researchOutcome"]["kind"] == "integration_unavailable"
    assert "records were found" in env["error"]["message"]
    assert "no research fact was promoted" in env["error"]["technicalMessage"]


def test_author_cannot_select_unknown_columns_or_mix_incompatible_field_meanings():
    _, _, facts = consume(Q06Fixture(), query()["question"])
    with pytest.raises(ValueError):
        records(facts, ["affiliation", "invented_joining_event"])
    with pytest.raises(ValueError):
        records(facts, ["affiliation", "affiliation"])
    altered = copy.deepcopy(facts)
    next(iter(altered.values()))["level"] = 3
    with pytest.raises(ValueError):
        records(altered, ["affiliation"])
    with pytest.raises(ValueError):
        project_table({"kind": "facts", "caption": "Invalid column choice", "columns": ["affiliation"],
                       "factRefs": list(facts), "activityRefs": []}, facts)


def test_current_constituency_consumption_keeps_reporting_date_and_open_end_policy():
    from test_nlq_question_failures import SourceFixture, MARY_LOU
    _, evidence, facts = consume(SourceFixture(), "What constituency does Mary Lou McDonald represent?")
    assert len(evidence.facts) == 1
    fact = evidence.facts[0]
    assert fact.kind == "episode" and fact.participants["member"].iri == MARY_LOU
    assert fact.scope["meaning"] == "membership_contains_as_of"
    assert fact.scope["asOf"] == AS_OF.isoformat()
    assert fact.intervals[0].endMeaning == "open_ended" and fact.intervals[0].rangeIri
    assert fact.witnesses[0]["start"].endswith("^^<http://www.w3.org/2001/XMLSchema#dateTime>")
    table = records(facts, ["member", "constituency", "as_of"])
    assert table["rows"][0]["cells"][1]["text"] == "Dublin Central"


def test_execution_binding_allows_only_exact_query_or_pagination_offset():
    outcome = execute_question(query()["question"], as_of=AS_OF, fuseki=Q06Fixture(),
                               supported_predicates=supported_predicates(ROOT / "ontology"))
    def traced(suffix):
        return [{"queryId": "q-test", "sparql": outcome.sparql + suffix, "outcome": "returned"}]
    assert accept_query_evidence(outcome, traced(""))[0]
    assert accept_query_evidence(outcome, traced(" OFFSET 100"))[0]
    assert accept_query_evidence(outcome, traced(" extra operation"))[0] is None


def history_draft():
    p = plan_question(query()["question"], as_of=AS_OF)
    return {"version": 2, "supported": True, "family": "member_party_history", "unsupportedReason": None,
            "intent": "Recorded affiliations and their source dates", "referents": {
                key: {"type": r["type"], "mention": r.get("mention")} for key, r in p["referents"].items()},
            "relations": p["relations"], "constraints": [], "answer": {"kind": "entities", "referent": "affiliation",
            "distinctBy": "identity", "display": ["label"], "details": [], "preserveEvidence": True}}


@pytest.mark.parametrize("question", [
    "What parties was Stephen Donnelly a member of, and when?",
    "Could you trace Stephen Donnelly's recorded political party affiliations, showing the membership dates where available?",
])
def test_semantic_selection_accepts_existing_date_projection_without_new_filters(question):
    class Fixed:
        def generate(self, prompt):
            return json.dumps(history_draft())
    from poc.nlq.composable_semantic_planner import build_composable_planner_instructions
    assert "details=[] does NOT mean dates are unavailable" in build_composable_planner_instructions()
    _, evidence, _ = consume(Q06Fixture(), question, semantic_plan_generator_factory=Fixed)
    assert {f.predicate for f in evidence.facts} == {"party_membership_episode"}


@pytest.mark.parametrize("question", [
    "What parties was Stephen Donnelly a member of before 2010?",
    "What parties was Stephen Donnelly a member of while a minister?",
])
def test_showing_dates_does_not_admit_extra_filters_or_relationships(question):
    class Fixed:
        def generate(self, prompt):
            return json.dumps(history_draft())
    fixture = Q06Fixture()
    env = adapter(fixture, semantic_plan_generator_factory=Fixed).execute(query(question) | {"requirementId": "r0"}, AS_OF.isoformat())
    assert env["outcome"] != "answer" and not facts_from(env) and not fixture.queries
