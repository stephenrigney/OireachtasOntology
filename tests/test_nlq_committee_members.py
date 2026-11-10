"""Current named-Committee listing preserves evidence and refuses partial intent."""

from copy import deepcopy
from datetime import date
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Namespace, URIRef, Literal
from rdflib.namespace import RDF, SKOS, FOAF, XSD

from poc.nlq.committee_members import (
    FAMILY, make_plan, resolve_committee, project_members, execute_committee_members,
)
from poc.nlq.composable_plan import execute_question, validate_plan, PlanError
from poc.nlq.composable_semantic_planner import (
    validate_composable_plan_draft, load_composable_draft_schema,
    InvalidComposableDraft, UnsupportedComposableRequest,
)
from poc.nlq.errors import NLQError
from poc.nlq.results import parse_results, QueryResult
from poc.nlq.vocabulary import supported_predicates

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 9)
QUESTION = "Who are the members of the Committee on Public Accounts?"
M = Namespace("https://data.oireachtas.ie/ontology/members#")
A = Namespace("https://data.oireachtas.ie/ontology#")
DCT = Namespace("http://purl.org/dc/terms/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
BASE = "https://data.oireachtas.ie/"
COMMITTEE = BASE + "ie/oireachtas/committee/dail/34/committee_of_public_accounts"
TERM = BASE + "ie/oireachtas/house/dail/34"


def draft(mention="Committee on Public Accounts"):
    return {"version": 2, "supported": True, "family": "capability_selection", "unsupportedReason": None,
            "intent": "List current named committee members", "referents": {
                "capability": FAMILY, "parameters": {"committee": mention}},
            "relations": [], "constraints": [], "answer": None}


class Generator:
    def __init__(self, value): self.value = value
    def generate(self, question): return json.dumps(self.value)


class Fixture:
    def __init__(self):
        self.dataset = Dataset()
        self.queries = []
        self.owner()

    def owner(self, iri=COMMITTEE, term=TERM, label="Committee of Public Accounts", start="2024-12-18T00:00:00", end=None):
        g = self.dataset.graph(URIRef(BASE + "graph/committees"))
        committee, term, r = URIRef(iri), URIRef(term), URIRef(iri + "#range")
        for triple in [(committee, RDF.type, M.Committee), (committee, SKOS.prefLabel, Literal(label, lang="en")),
                       (committee, M.committeeInHouseTerm, term), (committee, M.hasCommitteeDateRange, r), (r, RDF.type, M.DateRange)]: g.add(triple)
        if start: g.add((r, M.StartDate, Literal(start, datatype=XSD.dateTime)))
        if end: g.add((r, M.EndDate, Literal(end, datatype=XSD.dateTime)))
        h = self.dataset.graph(URIRef(BASE + "graph/houses"))
        p = URIRef(str(term) + "#period")
        for triple in [(term, RDF.type, A.DailTerm), (term, DCT.temporal, p), (p, RDF.type, DCT.PeriodOfTime),
                       (p, DCAT.startDate, Literal("2024-11-29", datatype=XSD.date))]: h.add(triple)

    def member(self, key="one", *, start="2025-05-07T00:00:00", end=None, episode="1", committee=COMMITTEE):
        member = URIRef(BASE + "ie/oireachtas/member/id/" + key)
        g = self.dataset.graph(URIRef(BASE + "graph/member/" + key))
        membership = URIRef(str(member) + "#committee-membership-" + episode)
        r = URIRef(str(membership) + "#range")
        for triple in [(member, RDF.type, A.Member), (member, FOAF.name, Literal(key)), (member, M.hasMembersMembership, membership),
                       (membership, RDF.type, M.CommitteeMembership), (membership, M.isCommitteeMembershipOf, URIRef(committee)),
                       (membership, M.hasMembershipDateRange, r), (r, RDF.type, M.DateRange)]: g.add(triple)
        if start: g.add((r, M.StartDate, Literal(start, datatype=XSD.dateTime)))
        if end: g.add((r, M.EndDate, Literal(end, datatype=XSD.dateTime)))
        return str(member), str(membership)

    def query(self, query):
        self.queries.append(query)
        return parse_results(json.loads(self.dataset.query(query).serialize(format="json")))


def run(fixture, question=QUESTION, mention="Committee on Public Accounts"):
    return execute_question(question, as_of=AS_OF, fuseki=fixture,
                            supported_predicates=supported_predicates(ROOT / "ontology"),
                            semantic_plan_generator_factory=lambda: Generator(draft(mention)))


@pytest.mark.parametrize("question", [QUESTION, "Which members serve on the Committee on Public Accounts?",
    "List the current members of the Committee on Public Accounts.", "Show me the members of the Committee on Public Accounts today."])
def test_complete_route_filters_dates_and_deduplicates_people_not_episodes(question):
    f = Fixture()
    member, episode = f.member()
    f.member(episode="2", start="2026-10-01T00:00:00")
    f.member("former", end="2026-05-28T00:00:00")
    f.member("future", start="2027-01-01T00:00:00")
    out = run(f, question)
    assert out.status == "success", out.diagnostic
    assert len(out.result.rows) == 1
    row = dict(zip(out.result.columns, out.result.rows[0]))
    assert row["Member identity"] == member and row["Committee identity"] == COMMITTEE
    assert episode in row["Membership evidence"] and "committee-membership-2" in row["Membership evidence"]
    assert "2025-05-07T00:00:00" in row["Membership evidence"] and "open-ended" in row["Membership evidence"]
    assert row["HouseTerm identity"] == TERM and row["As of"] == AS_OF.isoformat()
    assert "not a certified complete current roster" in out.diagnostic
    assert validate_plan(out.plan) == out.plan
    assert all("LIMIT 100" in q for q in f.queries)


def test_only_whole_source_name_matches_no_substring_or_accent_folding():
    f = Fixture(); f.member()
    assert run(f, "Who are the members of the Public Accounts?", "Public Accounts").result is None
    assert run(f, "Who are the members of the Committee of Public Accounts?", "Committee of Public Accounts").status == "success"


@pytest.mark.parametrize("question", [
    "Who were the members of the Committee on Public Accounts?",
    "Who are the members of the Committee on Public Accounts in 2020?",
    "Who are the members of the Committee on Public Accounts on 2025-05-07?",
    "Who are the Fianna Fáil members of the Committee on Public Accounts?",
    "Who are the members of the Committee on Public Accounts and their parties?",
    "Who are the members of the Committee on Public Accounts except Paul Murphy?",
    "Who are the members of the Committee on Public Accounts who attended yesterday?",
    "Who chairs the Committee on Public Accounts?",
    "How many members are on the Committee on Public Accounts?",
    "Who will be the members of the Committee on Public Accounts?",
])
def test_unsupported_constraints_not_discarded(question):
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(draft(), question=question)
    f = Fixture(); f.member()
    out = run(f, question)
    assert out.result is None
    assert not any("?memberGraph" in q for q in f.queries)


def test_schema_and_canonical_plan_require_complete_closed_projection():
    Draft202012Validator(load_composable_draft_schema()).validate(draft())
    plan = make_plan("Committee on Public Accounts", AS_OF)
    for key in ("relations", "constraints"):
        changed = deepcopy(plan); changed[key].pop()
        with pytest.raises(PlanError): validate_plan(changed)
    changed = deepcopy(plan); changed["answer"]["kind"] = "count"
    with pytest.raises(PlanError): validate_plan(changed)
    changed = draft(); changed["referents"]["parameters"]["date"] = "2020-01-01"
    with pytest.raises(InvalidComposableDraft): validate_composable_plan_draft(changed, question=QUESTION)


def test_ambiguous_current_incarnations_never_choose_a_matching_label():
    f = Fixture(); f.member(); f.owner(iri=COMMITTEE + "-other")
    out = run(f)
    assert out.status == "ambiguous" and len(out.candidates) == 2 and out.result is None
    assert not any("?memberGraph" in q for q in f.queries)


@pytest.mark.parametrize("fault", ["missing_start", "bad_end", "multiple_ranges", "missing_term_dates", "conflicting_term", "old_owner"])
def test_uncertain_or_historical_owner_prevents_member_query(fault):
    f = Fixture(); f.member()
    g = f.dataset.graph(URIRef(BASE + "graph/committees"))
    if fault == "missing_start": g.remove((URIRef(COMMITTEE + "#range"), M.StartDate, None))
    if fault == "bad_end": g.add((URIRef(COMMITTEE + "#range"), M.EndDate, Literal("2020-01-01T00:00:00", datatype=XSD.dateTime)))
    if fault == "multiple_ranges": g.add((URIRef(COMMITTEE), M.hasCommitteeDateRange, URIRef(COMMITTEE + "#other"))); g.add((URIRef(COMMITTEE + "#other"), RDF.type, M.DateRange))
    if fault == "missing_term_dates": f.dataset.graph(URIRef(BASE + "graph/houses")).remove((None, DCAT.startDate, None))
    if fault == "conflicting_term": g.add((URIRef(COMMITTEE), M.committeeInHouseTerm, URIRef(TERM + "-other")))
    if fault == "old_owner": g.add((URIRef(COMMITTEE + "#range"), M.EndDate, Literal("2025-01-01T00:00:00", datatype=XSD.dateTime)))
    out = run(f)
    assert out.status == "source_data_unavailable" and out.result is None
    assert not any("?memberGraph" in q for q in f.queries)


@pytest.mark.parametrize("fault", ["missing_start", "missing_range", "end_before_start", "conflicting_start", "missing_name", "conflicting_committee"])
def test_any_uncertain_member_evidence_blocks_whole_roster(fault):
    f = Fixture(); member, episode = f.member()
    g = f.dataset.graph(URIRef(BASE + "graph/member/one"))
    r = URIRef(episode + "#range")
    if fault == "missing_start": g.remove((r, M.StartDate, None))
    if fault == "missing_range": g.remove((URIRef(episode), M.hasMembershipDateRange, None))
    if fault == "end_before_start": g.add((r, M.EndDate, Literal("2020-01-01T00:00:00", datatype=XSD.dateTime)))
    if fault == "conflicting_start": g.add((r, M.StartDate, Literal("2025-05-08T00:00:00", datatype=XSD.dateTime)))
    if fault == "missing_name": g.remove((URIRef(member), FOAF.name, None))
    if fault == "conflicting_committee": g.add((URIRef(episode), M.isCommitteeMembershipOf, URIRef(COMMITTEE + "-other")))
    out = run(f)
    assert out.status == "source_data_unavailable" and out.result is None


def test_empty_roster_is_unavailable_not_zero_or_no_members():
    out = run(Fixture())
    assert out.status == "source_data_unavailable" and out.result is None


def test_all_pages_of_owner_and_membership_evidence_are_read():
    f = Fixture()
    for i in range(101):
        f.owner(iri=COMMITTEE + str(i), label=f"Other Committee {i}")
        f.member(str(i))
    out = run(f)
    assert out.status == "success", out.diagnostic
    assert len(out.result.rows) == 101
    assert sum("OFFSET 100" in q for q in f.queries) == 2


def test_phase2_projection_includes_coverage_qualification_and_all_identities(monkeypatch, tmp_path):
    import poc.nlq.app as module
    f = Fixture(); member, episode = f.member()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(module, "FusekiQueryClient", lambda *a, **kw: f)
    f.close = lambda: None
    from poc.nlq.fuseki import FusekiReadiness
    f.readiness = lambda: FusekiReadiness("ready", True, (), "Fixture")
    app = module.create_app(semantic_plan_generator_factory=lambda: Generator(draft()), feedback_directory=tmp_path)
    response = TestClient(app).post("/ask", data={"question": QUESTION, "mode": "phase2"})
    assert response.status_code == 200 and 'data-outcome="answer"' in response.text
    assert "not a certified complete current roster" in response.text
    assert member in response.text and episode in response.text and "2025-05-07T00:00:00" in response.text
    assert response.context["result_notice"] and "Committee" in response.context["interpretation"]
