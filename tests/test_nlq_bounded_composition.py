"""Bounded operator acceptance using real SPARQL over controlled named graphs."""

import copy
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from poc.nlq.composable_plan import (
    PlanError, _common_interval_intersection, compile_member_relationship_composition_query,
    execute_question, validate_plan,
)
from poc.nlq.composable_semantic_planner import (
    complete_v2_plan, load_composable_draft_schema, validate_composable_plan_draft,
)
from poc.nlq.vocabulary import supported_predicates
from test_nlq_composable_party_temporal import (
    PartyRepresentationFixture, FixedPlanGenerator, _temporal_draft, _current_term_fixture,
    CURRENT_TERM, CURRENT_CONSTITUENCY, MEMBER,
)
from test_nlq_interpretation_clarification import client
from test_nlq_composable_semantic_capability_discovery import _selection


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 2)
PREDICATES = supported_predicates(ROOT / "ontology")
BASE = "https://data.oireachtas.ie/"
A = Namespace(BASE + "ontology#")
M = Namespace(BASE + "ontology/members#")
F = Namespace("http://xmlns.com/foaf/0.1/")
S = Namespace("http://www.w3.org/2004/02/skos/core#")
FF = URIRef(BASE + "ie/oireachtas/political-affiliation/fianna-fail")
FG = URIRef(BASE + "ie/oireachtas/political-affiliation/fine-gael")
OFFICE = URIRef(BASE + "ie/oireachtas/office/taoiseach")
Q15 = "Who are the Fine Gael TDs in Galway East and Galway West?"
Q3 = "Who were the other Fianna Fáil TDs in the same constituency as Bertie Ahern while he was Taoiseach?"


def set_draft(names=("Galway East", "Galway West"), party="Fine Gael"):
    draft = _temporal_draft(answer_referent="member", affiliation_mention=party,
                            constituency=names[0], term_selector={"kind": "currentTerm"})
    draft["referents"]["constituency"] = {"type": "DailConstituency", "members": [
        {"type": "DailConstituency", "mention": name} for name in names]}
    return draft


def anchor_draft(anchor="Bertie Ahern", party="Fianna Fáil", office="Taoiseach"):
    draft = _temporal_draft(answer_referent="member", affiliation_mention=party)
    refs = draft["referents"]
    refs["term"] = {"type": "DailTerm", "mention": None}
    refs["constituency"] = {"type": "DailConstituency", "mention": None}
    refs.update(anchor={"type": "Member", "mention": anchor},
                anchor_membership={"type": "DailMembership", "mention": None},
                holding={"type": "OfficeHolding", "mention": None},
                office={"type": "NamedOffice", "mention": office})
    for fact, source, target in [
        ("member_has_membership", "anchor", "anchor_membership"),
        ("membership_in_term", "anchor_membership", "term"),
        ("membership_represents", "anchor_membership", "constituency"),
        ("member_has_office_holding", "anchor", "holding"),
        ("office_holding_of_office", "holding", "office"),
    ]:
        draft["relations"].append({"id": source + fact, "fact": fact, "from": source, "to": target})
    draft["constraints"] += [
        {"referent": "member", "field": "identity", "operator": "distinctFrom", "value": "anchor"},
        {"referent": "holding", "field": "interval", "operator": "commonIntersection",
         "value": ["holding", "anchor_membership", "membership", "episode"]},
    ]
    draft["answer"]["details"] += [
        {"referent": "holding", "display": ["start", "end"]},
        {"referent": "anchor_membership", "display": ["start", "end"]},
        {"referent": "constituency", "display": ["label"]},
    ]
    return draft


def add_interval(graph, resource, start, end, *, office=False, key="dates"):
    period = URIRef(str(resource) + "#" + key)
    graph.add((resource, M.hasMembershipDateRange, period))
    graph.add((period, RDF.type, M.DateRange))
    if start is not None:
        graph.add((period, M.StartDate, Literal(start, datatype=XSD.dateTime, normalize=False)))
    if end is not None:
        graph.add((period, M.EndDate, Literal(end, datatype=XSD.dateTime, normalize=False)))
    return period


def add_constituency(fixture, name, *, key=None, term=CURRENT_TERM):
    iri = URIRef(BASE + "ie/oireachtas/constituency/dail/" + (key or name.replace(" ", "-")) + "-34")
    graph = fixture.dataset.graph(URIRef(BASE + "graph/constituencies"))
    for triple in ((iri, RDF.type, M.DailConstituency), (iri, S.prefLabel, Literal(name, lang="en")),
                   (iri, M.constituencyInHouseTerm, URIRef(term))):
        graph.add(triple)
    return iri


def add_person(fixture, name, constituencies, *, identity=FG, party_label="Fine Gael",
               membership=("2025-01-01T00:00:00", None), party_interval=None):
    key = name.replace(" ", "-")
    person = URIRef(BASE + "ie/oireachtas/member/id/" + key)
    graph = fixture.dataset.graph(URIRef(BASE + "graph/member/" + key))
    graph.add((person, RDF.type, A.Member)); graph.add((person, F.name, Literal(name)))
    for n, constituency in enumerate(constituencies):
        membership_iri = URIRef(str(person) + f"#membership-{n}")
        episode = URIRef(str(person) + f"#party-{n}")
        party = URIRef(BASE + "ie/oireachtas/party/dail/34/" + party_label.replace(" ", "-"))
        for triple in ((person, M.hasMembersMembership, membership_iri), (membership_iri, RDF.type, M.DailMembership),
                       (membership_iri, M.inHouseTerm, URIRef(CURRENT_TERM)), (membership_iri, M.isRepresentativeFrom, constituency),
                       (person, M.hasMembersMembership, episode), (episode, RDF.type, M.PartyMembership),
                       (episode, M.inOireachtasMembership, membership_iri), (episode, M.isPartyMembershipOf, party)):
            graph.add(triple)
        add_interval(graph, membership_iri, *membership)
        add_interval(graph, episode, *(party_interval or membership))
        parties = fixture.dataset.graph(URIRef(BASE + "graph/parties"))
        for triple in ((party, RDF.type, M.ParliamentaryParty), (party, M.activeDuringTerm, URIRef(CURRENT_TERM)),
                       (party, S.prefLabel, Literal(party_label + ", 34th Dáil", lang="en"))):
            parties.add(triple)
        identities = fixture.dataset.graph(URIRef(BASE + "graph/political-affiliations/identities"))
        for triple in ((party, M.hasPoliticalAffiliationIdentity, identity), (identity, RDF.type, M.PoliticalAffiliationIdentity),
                       (identity, S.prefLabel, Literal(party_label, lang="en"))):
            identities.add(triple)
    return person, graph


def set_fixture():
    fixture = _current_term_fixture()
    west = URIRef(CURRENT_CONSTITUENCY)
    east = add_constituency(fixture, "Galway East")
    add_person(fixture, "Recorded East", [east])
    add_person(fixture, "Recorded West", [west])
    add_person(fixture, "Recorded Both", [east, west])
    add_person(fixture, "Former Party", [east], party_interval=("2020-01-01T00:00:00", "2021-01-01T00:00:00"))
    return fixture


def anchor_fixture(*, anchor_interval=("2007-01-01T00:00:00", "2008-12-31T00:00:00"),
                   holding_interval=("2007-06-14T00:00:00", "2008-05-07T00:00:00"), anchor_name="Bertie Ahern"):
    fixture = _current_term_fixture()
    shared = add_constituency(fixture, "Dublin Central")
    anchor, graph = add_person(fixture, anchor_name, [shared], identity=FF, party_label="Fianna Fáil", membership=anchor_interval)
    holding = URIRef(str(anchor) + "#accepted-holding")
    graph.add((anchor, M.hasOfficeHolding, holding)); graph.add((holding, RDF.type, M.OfficeHolding)); graph.add((holding, M.heldOffice, OFFICE))
    add_interval(graph, holding, *holding_interval, office=True)
    offices = fixture.dataset.graph(URIRef(BASE + "graph/offices"))
    offices.add((OFFICE, RDF.type, M.NamedOffice)); offices.add((OFFICE, S.prefLabel, Literal("Taoiseach", lang="en")))
    add_person(fixture, "Recorded Colleague", [shared], identity=FF, party_label="Fianna Fáil",
               membership=("2007-01-01T00:00:00", "2008-12-31T00:00:00"))
    add_person(fixture, "Later Colleague", [shared], identity=FF, party_label="Fianna Fáil",
               membership=("2009-01-01T00:00:00", None))
    # Same display label is NOT the same occurrence identity.
    other = add_constituency(fixture, "Dublin Central", key="different-identity")
    add_person(fixture, "Label Only", [other], identity=FF, party_label="Fianna Fáil", membership=anchor_interval)
    return fixture, anchor, graph, holding


def execute(fixture, draft, question):
    return execute_question(question, as_of=AS_OF, fuseki=fixture, supported_predicates=PREDICATES,
                            semantic_plan_generator_factory=lambda: FixedPlanGenerator(draft))


@pytest.mark.parametrize(("draft", "question"), [(set_draft(), Q15), (anchor_draft(), Q3)])
def test_operator_schemas_and_deterministic_validation(draft, question):
    Draft202012Validator(load_composable_draft_schema()).validate(draft)
    plan, _ = validate_composable_plan_draft(draft, question=question)
    final = complete_v2_plan(plan, as_of=AS_OF)
    validate_plan(final)
    Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())).validate(final)


def test_q15_one_identity_union_query_and_member_deduplication(monkeypatch):
    fixture = set_fixture()
    c, generator = client(monkeypatch, fixture, set_draft())
    response = c.post("/ask", data={"question": Q15})
    assert 'data-outcome="answer"' in response.text, response.text
    assert generator.calls == [Q15]
    outcome = execute(set_fixture(), set_draft(), Q15)
    assert outcome.status == "success", outcome.diagnostic
    assert {row[0] for row in outcome.result.rows} == {"Recorded East", "Recorded West", "Recorded Both"}
    assert len(outcome.result.rows) == 3
    assert "VALUES ?constituency" in outcome.sparql
    assert outcome.sparql == compile_member_relationship_composition_query(outcome.plan, supported_predicates=PREDICATES)
    # Independent single-constituency queries use the SAME compiler/evaluator.
    union = set()
    for name in ("Galway East", "Galway West"):
        single = _temporal_draft(answer_referent="member", affiliation_mention="Fine Gael", constituency=name,
                                 term_selector={"kind": "currentTerm"})
        one = execute(set_fixture(), single, f"Who are the Fine Gael TDs in {name}?")
        assert one.status == "success", one.diagnostic
        union.update(row[1] for row in one.result.rows)
    assert union == {row[1] for row in outcome.result.rows}


def test_q3_independent_paths_common_intersection_and_partial_coverage(monkeypatch):
    fixture, anchor, _, _ = anchor_fixture()
    c, generator = client(monkeypatch, fixture, anchor_draft())
    response = c.post("/ask", data={"question": Q3})
    assert 'data-outcome="answer"' in response.text, response.text
    assert generator.calls == [Q3]
    assert "Partial accepted-evidence coverage" in response.text
    outcome = execute(anchor_fixture()[0], anchor_draft(), Q3)
    assert outcome.status == "success", outcome.diagnostic
    assert [row[0] for row in outcome.result.rows] == ["Recorded Colleague"]
    assert "2007-06-14" in outcome.result.rows[0][2] and "2008-05-07" in outcome.result.rows[0][2]
    assert "shared constituency" in outcome.result.rows[0][2]
    assert "GRAPH ?anchorGraph" in outcome.sparql and "FILTER(?member != ?anchor)" in outcome.sparql
    assert outcome.sparql == compile_member_relationship_composition_query(outcome.plan, supported_predicates=PREDICATES)


@pytest.mark.parametrize("fault", ["missing_start", "malformed_start", "conflicting_range", "unaccepted", "missing_party_link"])
def test_q3_uncertain_or_unaccepted_evidence_never_answers(fault):
    fixture, anchor, graph, holding = anchor_fixture()
    period = URIRef(str(holding) + "#dates")
    if fault == "missing_start":
        graph.remove((period, M.StartDate, None))
    elif fault == "malformed_start":
        graph.set((period, M.StartDate, Literal("not-a-date", datatype=XSD.dateTime, normalize=False)))
    elif fault == "conflicting_range":
        add_interval(graph, holding, "2006-01-01T00:00:00", None, office=True, key="conflict")
    elif fault == "unaccepted":
        graph.remove((holding, RDF.type, M.OfficeHolding))
    else:
        identities = fixture.dataset.graph(URIRef(BASE + "graph/political-affiliations/identities"))
        identities.remove((None, M.hasPoliticalAffiliationIdentity, FF))
    outcome = execute(fixture, anchor_draft(), Q3)
    assert outcome.status != "success", outcome


def test_common_intersection_is_not_only_each_interval_overlapping_office():
    fixture, _, _, _ = anchor_fixture(anchor_interval=("2007-01-01T00:00:00", "2007-09-01T00:00:00"))
    graph = fixture.dataset.graph(URIRef(BASE + "graph/member/Recorded-Colleague"))
    episode = URIRef(BASE + "ie/oireachtas/member/id/Recorded-Colleague#party-0#dates")
    graph.set((episode, M.StartDate, Literal("2007-10-01T00:00:00", datatype=XSD.dateTime)))
    assert execute(fixture, anchor_draft(), Q3).status != "success"
    d = lambda s: datetime.fromisoformat(s)
    assert _common_interval_intersection([(d("2007-01-01"), None), (d("2008-01-01"), d("2008-01-01"))]) == (d("2008-01-01"), d("2008-01-01"))


@pytest.mark.parametrize("question", [
    Q15[:-1] + " and when were they first elected?",
    Q3[:-1] + " and give their first-election dates?",
    "How many Fine Gael TDs are in Galway East and Galway West?",
])
def test_whole_intent_rejected_before_resolution_or_execution(question):
    fixture = set_fixture()
    outcome = execute(fixture, set_draft(), question)
    assert outcome.status == "unsupported_request"
    assert not fixture.queries and outcome.sparql is None


@pytest.mark.parametrize("question", ["Who are the Fine Gael TDs in the two Galway constituencies?", Q15])
def test_model_may_not_invent_constituency_set_or_omit_an_alternative(question):
    draft = set_draft(names=("Galway East", "Galway West"))
    if question == Q15:
        draft["referents"]["constituency"] = {"type": "DailConstituency", "mention": "Galway East"}
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question=question)


@pytest.mark.parametrize("mutation", ["edge", "shared", "distinct", "intersection", "answer"])
def test_graph_or_operator_weakening_is_rejected(mutation):
    draft = anchor_draft()
    if mutation == "edge":
        draft["relations"].pop()
    elif mutation == "shared":
        draft["relations"][-3]["to"] = "other_constituency"
    elif mutation == "distinct":
        draft["constraints"].pop(1)
    elif mutation == "intersection":
        draft["constraints"][-1]["value"].remove("anchor_membership")
    else:
        draft["answer"]["details"].pop()
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question=Q3)


def test_calendar_month_selection_reuses_existing_office_plan_and_compiler(monkeypatch):
    fixture, _, _, _ = anchor_fixture(holding_interval=("1994-01-01T00:00:00", "1994-12-31T00:00:00"), anchor_name="Albert Reynolds")
    question = "Who held the office of Taoiseach during June 1994?"
    draft = _selection("office_holding_window", {"office": "Taoiseach", "startMonth": 6, "startYear": 1994, "endMonth": 6, "endYear": 1994})
    c, _ = client(monkeypatch, fixture, draft)
    response = c.post("/ask", data={"question": question})
    assert 'data-outcome="answer"' in response.text, response.text
    assert "Albert Reynolds" in response.text and "1994-06-30" in response.text
    outcome = execute(fixture, draft, question)
    assert outcome.plan["constraints"][0]["value"] == {"start": "1994-06-01", "end": "1994-06-30", "inclusive": True}


def test_implicit_geographic_set_clarifies_all_grounded_occurrences(monkeypatch):
    fixture = set_fixture()
    add_constituency(fixture, "Roscommon-Galway")
    c, generator = client(monkeypatch, fixture, set_draft())
    response = c.post("/ask", data={"question": "Who are the Fine Gael TDs in the two Galway constituencies?"})
    assert 'data-outcome="clarification_required"' in response.text
    assert "Roscommon-Galway" in response.text
    assert not generator.calls
    assert not any("?episode" in query for query in fixture.queries)


@pytest.mark.parametrize("role", ["anchor", "office", "constituency"])
def test_ambiguous_local_identities_never_run_an_answer_query(role):
    if role == "constituency":
        fixture = set_fixture()
        add_constituency(fixture, "Galway East", key="duplicate")
        draft, question = set_draft(), Q15
    else:
        fixture, _, _, _ = anchor_fixture()
        draft, question = anchor_draft(), Q3
        if role == "anchor":
            graph = fixture.dataset.graph(URIRef(BASE + "graph/member/Another-Ahern"))
            iri = URIRef(BASE + "ie/oireachtas/member/id/Another-Ahern")
            graph.add((iri, RDF.type, A.Member)); graph.add((iri, F.name, Literal("Bertie Ahern")))
        else:
            graph = fixture.dataset.graph(URIRef(BASE + "graph/offices"))
            iri = URIRef(BASE + "ie/oireachtas/office/another")
            graph.add((iri, RDF.type, M.NamedOffice)); graph.add((iri, S.prefLabel, Literal("Taoiseach", lang="en")))
    outcome = execute(fixture, draft, question)
    assert outcome.status == "ambiguous", outcome.diagnostic
    assert outcome.result is None and outcome.sparql is None


@pytest.mark.parametrize("role", ["holding", "anchor_membership", "membership", "episode"])
def test_every_independently_owned_interval_requires_start_and_no_conflicts(role):
    fixture, anchor, graph, holding = anchor_fixture()
    if role == "holding":
        period = URIRef(str(holding) + "#dates")
    elif role == "anchor_membership":
        period = URIRef(str(anchor) + "#membership-0#dates")
    else:
        graph = fixture.dataset.graph(URIRef(BASE + "graph/member/Recorded-Colleague"))
        period = URIRef(BASE + "ie/oireachtas/member/id/Recorded-Colleague#" + ("membership-0" if role == "membership" else "party-0") + "#dates")
    graph.remove((period, M.StartDate, None))
    assert execute(fixture, anchor_draft(), Q3).status != "success"


def test_missing_alternative_or_additional_unrepresented_clause_is_not_silently_dropped():
    for question in (Q15[:-1] + " or Mayo?", Q15[:-1] + " who were born in Dublin?"):
        with pytest.raises(ValueError):
            validate_composable_plan_draft(set_draft(), question=question)


def test_unknown_date_or_extra_current_scope_does_not_replace_office_anchor():
    for suffix in (" on 31 February 2008?", " in the current Dáil?"):
        outcome = execute(anchor_fixture()[0], anchor_draft(), Q3[:-1] + suffix)
        assert outcome.status != "success" and outcome.sparql is None


def test_inclusive_endpoint_and_open_office_end():
    fixture, _, _, _ = anchor_fixture(anchor_interval=("2008-05-07T00:00:00", None))
    outcome = execute(fixture, anchor_draft(), Q3)
    assert outcome.status == "success", outcome.diagnostic
    assert "common temporal intersection 2008-05-07T00:00:00 – 2008-05-07T00:00:00" in outcome.result.rows[0][2]
    fixture, _, _, _ = anchor_fixture(holding_interval=("2007-06-14T00:00:00", None))
    outcome = execute(fixture, anchor_draft(), Q3)
    assert outcome.status == "success", outcome.diagnostic
    assert "open-ended" in outcome.result.rows[0][2]


def test_party_resolution_is_scoped_to_terms_intersecting_accepted_office_evidence():
    fixture, anchor, graph, _ = anchor_fixture()
    term = URIRef(BASE + "ie/oireachtas/houseTerm/dail/33")
    houses = fixture.dataset.graph(URIRef(BASE + "graph/houses"))
    houses.add((term, RDF.type, A.DailTerm))
    old_constituency = add_constituency(fixture, "Earlier Constituency", term=str(term))
    old_membership = URIRef(str(anchor) + "#earlier-membership")
    for triple in ((anchor, M.hasMembersMembership, old_membership), (old_membership, RDF.type, M.DailMembership),
                   (old_membership, M.inHouseTerm, term), (old_membership, M.isRepresentativeFrom, old_constituency)):
        graph.add(triple)
    add_interval(graph, old_membership, "1990-01-01T00:00:00", "1994-01-01T00:00:00")
    other, other_graph = add_person(fixture, "Earlier Other Party", [old_constituency],
                                     membership=("1990-01-01T00:00:00", "1994-01-01T00:00:00"))
    other_graph.set((URIRef(str(other) + "#membership-0"), M.inHouseTerm, term))
    party = URIRef(BASE + "ie/oireachtas/party/dail/34/Fine-Gael")
    fixture.dataset.graph(URIRef(BASE + "graph/parties")).set((party, M.activeDuringTerm, term))
    outcome = execute(fixture, anchor_draft(), Q3)
    assert outcome.status == "success", outcome.diagnostic
    assert [row[0] for row in outcome.result.rows] == ["Recorded Colleague"]


@pytest.mark.parametrize("anchored", [False, True])
def test_bounded_evidence_cap_is_fail_closed(anchored):
    from poc.nlq.results import QueryResult
    fixture = anchor_fixture()[0] if anchored else set_fixture()
    query = fixture.query
    def capped(text):
        result = query(text)
        if "?anchorMembershipStart" in text or (not anchored and "?membershipRange" in text):
            return QueryResult("select", result.columns, tuple(result.rows[0] for _ in range(100)))
        return result
    fixture.query = capped
    outcome = execute(fixture, anchor_draft() if anchored else set_draft(), Q3 if anchored else Q15)
    assert outcome.status != "success" and outcome.result is None
    assert "cap" in outcome.diagnostic


def test_office_registry_pattern_drift_is_not_misreported_as_absent_source(monkeypatch):
    from poc.nlq import composable_plan
    monkeypatch.setitem(composable_plan._PLAN_CONTRACT["entityTypeRdfTypes"], "OfficeHolding", "agents:Member")
    fixture = anchor_fixture()[0]
    outcome = execute(fixture, anchor_draft(), Q3)
    assert outcome.status == "unsupported_mapping"
    assert not fixture.queries and outcome.result is None
