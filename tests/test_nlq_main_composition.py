"""/ask composition with synthetic typed RDF; model omissions are adversarial inputs."""

from copy import deepcopy
from datetime import date
import json
import re

import pytest
from fastapi.testclient import TestClient
from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from poc.nlq.app import create_app
from poc.nlq.composition_admission import FAMILY, make_request, validate_requirements
from poc.nlq.composition_kernel import graph, iri, Budget
from poc.nlq.composition_workflow import execute_request
from poc.nlq.composable_semantic_planner import validate_composable_plan_draft, UnsupportedComposableRequest
from test_nlq_composition_integration import synthetic_dataset, DatasetTransport, BASE


FIANNA = BASE + "ie/oireachtas/political-affiliation/fianna-fail"
VARIATIONS = [
    ("Which Fianna Fáil TDs represent Kildare North?", "RP", "list"),
    ("How many Fianna Fáil TDs currently represent Kildare North?", "RP", "count"),
    ("Please identify the TDs for Kildare North with membership of Fianna Fáil.", "RP", "list"),
    ("Who represents Kildare North and belongs to Fianna Fáil?", "RP", "list"),
    ("Which representatives of Kildare North belong to Fianna Fáil?", "RP", "list"),
    ("Who on the Committee of Public Accounts belongs to Fianna Fáil?", "KP", "list"),
    ("Which Fianna Fáil members serve on Public Accounts?", "KP", "list"),
    ("Show me members belonging to Fianna Fáil who sit on Public Accounts.", "KP", "list"),
    ("Public Accounts members affiliated with Fianna Fáil: who are they?", "KP", "list"),
    ("Which members of Public Accounts represent Kildare North?", "KR", "list"),
    ("For Kildare North, name the TDs serving on Public Accounts.", "KR", "list"),
    ("Please show the representatives for Kildare North who also sit on PAC.", "KR", "list"),
]


def proposal(question, pair, shape="list"):
    committee = next((s for s in ("Committee of Public Accounts", "Public Accounts", "PAC") if s in question), "Public Accounts")
    mentions = {"R": "Kildare North", "P": "Fianna Fáil", "K": committee}
    return {"version": 2, "supported": True, "family": FAMILY, "unsupportedReason": None,
            "intent": "untrusted model interpretation", "referents": {
                "selections": [{"role": role, "mention": mentions[role]} for role in pair],
                "shape": shape, "temporal": "current"}, "relations": [], "constraints": [], "answer": None}


def party_dataset():
    ds = synthetic_dataset()
    party = URIRef(BASE + "test/party")
    term = URIRef(BASE + "test/dail")
    parties, identities = ds.graph(graph("parties")), ds.graph(graph("political-affiliations"))
    parties.add((party, iri("rdf:type"), iri("members:ParliamentaryParty")))
    parties.add((party, iri("skos:prefLabel"), Literal("Fianna Fáil", lang="en")))
    parties.add((party, iri("members:activeDuringTerm"), term))
    identities.add((party, iri("members:hasPoliticalAffiliationIdentity"), URIRef(FIANNA)))
    identities.add((URIRef(FIANNA), iri("rdf:type"), iri("members:PoliticalAffiliationIdentity")))
    identities.add((URIRef(FIANNA), iri("skos:prefLabel"), Literal("Fianna Fáil", lang="en")))
    for code in ("Alice", "Bob"):
        owner = ds.graph(URIRef(BASE + "graph/member/" + code))
        member = URIRef(BASE + "test/member/" + code)
        episode = URIRef(str(member) + "/P")
        range_ = URIRef(str(episode) + "#range")
        for s, p, o in (
            (member, "members:hasMembersMembership", episode),
            (episode, "rdf:type", iri("members:PartyMembership")),
            (episode, "members:inOireachtasMembership", URIRef(str(member) + "/R")),
            (episode, "members:isPartyMembershipOf", party),
            (episode, "members:hasMembershipDateRange", range_),
            (range_, "rdf:type", iri("members:DateRange")),
            (range_, "members:StartDate", Literal("2024-01-01T00:00:00", datatype=XSD.dateTime, normalize=False)),
        ):
            owner.add((s, iri(p), o))
        if code == "Bob":
            owner.add((range_, iri("members:EndDate"), Literal("2026-04-01T00:00:00", datatype=XSD.dateTime, normalize=False)))
    return ds


class MainTransport(DatasetTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(dataset=party_dataset())


def make_app(monkeypatch, tmp_path, draft, *, transport=MainTransport):
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-05-01")
    class Planner:
        calls = 0
        def generate(self, question):
            type(self).calls += 1
            return json.dumps(draft)
        def close(self): pass
    app = create_app(feedback_directory=tmp_path, semantic_plan_generator_factory=Planner,
                     composition_transport_factory=transport)
    return app, Planner


@pytest.mark.parametrize("question,pair,shape", VARIATIONS)
def test_varied_semantic_questions_direct_through_ask(monkeypatch, tmp_path, question, pair, shape):
    app, planner = make_app(monkeypatch, tmp_path, proposal(question, pair, shape))
    client = TestClient(app)
    response = client.post("/ask", data={"question": question})
    assert 'id="query-results"' in response.text, response.text
    assert 'data-outcome="answer"' not in response.text
    assert 'class="query-outcome"' not in response.text and "Outcome: answer" not in response.text
    assert "Confirm interpretation and execute" not in response.text
    assert "available records may not be complete" in response.text and "2026-05-01" in response.text
    assert planner.calls == 1
    link = re.search(r'href="(/composition/evidence/[^"]+)"', response.text)[1]
    report = client.get(link).json()["report"]
    assert report["status"] == "answer" and len(report["ledger"]) == 6
    assert report["names"] == {BASE + "test/member/Alice": "Alice Example"}
    assert {w["role"] for w in report["answer"]["witnesses"][0]} == set(pair)
    if shape == "count":
        assert report["answer"]["distinctCount"] == 1
        assert "1 matching TD" in response.text
    else:
        assert "Alice Example" in response.text


@pytest.mark.parametrize("extra", [
    " and are women", " and not Senators", " and do not belong to Fine Gael", " before 2025",
    " as of 2026-02-30", " during the 33rd Dáil", " who voted for a Bill", " and their parties",
    " and their first election dates", " or represent Dublin Central", " except Alice", " only",
    " and are members of the Joint Committee on Health", " with at least two terms", " with no party membership",
])
def test_willing_model_cannot_omit_extra_condition(monkeypatch, tmp_path, extra):
    base = VARIATIONS[1][0]
    class NoExecution:
        def __init__(self, *args, **kwargs): pytest.fail("Unsafe plan must not execute")
    app, _ = make_app(monkeypatch, tmp_path, proposal(base, "RP", "count"), transport=NoExecution)
    response = TestClient(app).post("/ask", data={"question": base.rstrip("?") + extra + "?"})
    assert 'id="query-results"' not in response.text
    assert 'role="alert"' in response.text


@pytest.mark.parametrize("question,pair,shape", [
    ("Are there TDs representing Kildare North who serve on Public Accounts?", "KR", "list"),
    ("How many Fianna Fáil members serve on Public Accounts?", "KP", "count"),
    ("Which Fianna Fáil TDs represent Kildare North?", "RP", "count"),
    ("How many Fianna Fáil TDs represent Kildare North?", "RP", "list"),
])
def test_projection_changes_rejected_before_retrieval(monkeypatch, tmp_path, question, pair, shape):
    class NoExecution:
        def __init__(self, *args, **kwargs): pytest.fail("Projection must not be changed")
    app, _ = make_app(monkeypatch, tmp_path, proposal(question, pair, shape), transport=NoExecution)
    response = TestClient(app).post("/ask", data={"question": question})
    assert 'id="query-results"' not in response.text


def test_rp_requires_exact_same_containing_membership():
    q = VARIATIONS[0][0]
    draft = proposal(q, "RP")
    plan, _ = validate_composable_plan_draft(draft, question=q)
    request = make_request(plan, q, date(2026, 5, 1))
    assert "R.parliamentaryMembership=P.containingMembership" in request["exactSharedBindings"]
    ds = party_dataset()
    owner = ds.graph(URIRef(BASE + "graph/member/Alice"))
    original = URIRef(BASE + "test/member/Alice/R")
    other = URIRef(str(original) + "-other")
    for _, p, o in list(owner.triples((original, None, None))): owner.add((other, p, o))
    owner.add((URIRef(BASE + "test/member/Alice"), iri("members:hasMembersMembership"), other))
    owner.set((URIRef(BASE + "test/member/Alice/P"), iri("members:inOireachtasMembership"), other))
    # Different representation target avoids creating an additional qualifying R
    # witness; the P containing membership still has its own accepted interval.
    owner.set((other, iri("members:isRepresentativeFrom"), URIRef(BASE + "test/other-constituency")))
    report, result = execute_request(request, DatasetTransport(dataset=ds))
    assert result is None and "No qualifying" in report["error"]


def test_party_resolution_and_display_share_request_budget():
    q = VARIATIONS[0][0]
    plan, _ = validate_composable_plan_draft(proposal(q, "RP"), question=q)
    budget = Budget()
    for _ in range(3): budget.request("SELECT ?s WHERE { VALUES ?s { <https://data.oireachtas.ie/test> } } LIMIT 100", 15)
    report, result = execute_request(make_request(plan, q, date(2026, 5, 1)), MainTransport(), budget=budget)
    assert result is None and len(report["ledger"]) == 8 and "budget" in report["error"]


def test_short_name_matches_multiple_distinct_committees_as_ambiguity(monkeypatch, tmp_path):
    ds = party_dataset()
    owner = ds.graph(graph("committees"))
    source = URIRef(BASE + "test/committee")
    owner.set((source, iri("skos:prefLabel"), Literal("Joint Committee on Health", lang="en")))
    for _, p, o in list(owner.triples((source, None, None))):
        owner.add((URIRef(str(source) + "-other"), p, Literal("Select Committee on Health", lang="en") if p == iri("skos:prefLabel") else o))
    q = "Which Fianna Fáil members serve on Health?"
    draft = proposal(q, "KP")
    draft["referents"]["selections"][0]["mention"] = "Health"
    class Ambiguous(MainTransport):
        def __init__(self, *args, **kwargs): self.dataset, self.calls = ds, []
    app, _ = make_app(monkeypatch, tmp_path, draft, transport=Ambiguous)
    response = TestClient(app).post("/ask", data={"question": q})
    assert 'data-outcome="clarification_required"' not in response.text
    assert 'class="query-outcome"' not in response.text
    assert 'id="query-results"' not in response.text and "none was selected" in response.text


def test_historical_alias_ambiguity_is_term_scoped_not_globally_chosen(monkeypatch, tmp_path):
    ds = party_dataset()
    ids = ds.graph(graph("political-affiliations"))
    party = URIRef(BASE + "test/party")
    modern = URIRef(BASE + "ie/oireachtas/political-affiliation/sinn-fein")
    ids.set((party, iri("members:hasPoliticalAffiliationIdentity"), modern))
    ids.add((modern, iri("rdf:type"), iri("members:PoliticalAffiliationIdentity")))
    ids.add((modern, iri("skos:prefLabel"), Literal("Sinn Féin", lang="en")))
    historic = URIRef(BASE + "ie/oireachtas/political-affiliation/sinn-fein-1957")
    other = URIRef(BASE + "test/party-other")
    parties = ds.graph(graph("parties"))
    parties.add((other, iri("rdf:type"), iri("members:ParliamentaryParty")))
    parties.add((other, iri("members:activeDuringTerm"), URIRef(BASE + "test/dail")))
    parties.add((other, iri("skos:prefLabel"), Literal("Sinn Féin", lang="en")))
    ids.add((other, iri("members:hasPoliticalAffiliationIdentity"), historic))
    ids.add((historic, iri("rdf:type"), iri("members:PoliticalAffiliationIdentity")))
    ids.add((historic, iri("skos:prefLabel"), Literal("Sinn Féin (1957)", lang="en")))
    q = "Which Sinn Féin TDs represent Kildare North?"
    draft = proposal(q, "RP")
    draft["referents"]["selections"][1]["mention"] = "Sinn Féin"
    class Ambiguous(MainTransport):
        def __init__(self, *args, **kwargs): self.dataset, self.calls = ds, []
    app, _ = make_app(monkeypatch, tmp_path, draft, transport=Ambiguous)
    response = TestClient(app).post("/ask", data={"question": q})
    assert 'data-outcome="clarification_required"' not in response.text
    assert 'class="query-outcome"' not in response.text and 'id="query-results"' not in response.text


@pytest.mark.parametrize("question,pair,shape", [
    ("Tell me, are there Fianna Fáil members serving on Public Accounts?", "KP", "list"),
    ("Who could represent Kildare North and belong to Fianna Fáil?", "RP", "list"),
    ("Which members represent Public Accounts and Kildare North?", "KR", "list"),
    ("Which party do Fianna Fáil TDs representing Kildare North belong to?", "RP", "list"),
    ("Which Fianna Fáil TDs count members representing Kildare North?", "RP", "count"),
    ("Which Fianna Fáil Senators represent Kildare North?", "RP", "list"),
    ("Which Seanad members represent Kildare North and serve on Public Accounts?", "KR", "list"),
])
def test_semantic_operator_and_answer_head_cannot_be_changed(question, pair, shape):
    with pytest.raises((ValueError, UnsupportedComposableRequest)):
        validate_composable_plan_draft(proposal(question, pair, shape), question=question)


@pytest.mark.parametrize("dropped", ["K", "P", "R"])
def test_no_pair_can_drop_third_named_requirement(dropped):
    q = "Which Fianna Fáil TDs representing Kildare North serve on Public Accounts?"
    pair = "".join(role for role in "KPR" if role != dropped)
    with pytest.raises(UnsupportedComposableRequest):
        validate_composable_plan_draft(proposal(q, pair), question=q)


def test_condition_consumed_inside_mention_cannot_ground_or_produce_partial_answer(monkeypatch, tmp_path):
    q = "Which Fianna Fáil TDs represent Kildare North in 2024?"
    draft = proposal(q, "RP")
    draft["referents"]["selections"][0]["mention"] = "Kildare North in 2024"
    app, _ = make_app(monkeypatch, tmp_path, draft)
    response = TestClient(app).post("/ask", data={"question": q})
    assert 'id="query-results"' not in response.text


@pytest.mark.parametrize("date_value", ["2026-02-30", "20260501", "2026-W01-1", "not-a-date"])
def test_invalid_backend_date_precedes_planner(monkeypatch, tmp_path, date_value):
    q = VARIATIONS[0][0]
    app, planner = make_app(monkeypatch, tmp_path, proposal(q, "RP"))
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", date_value)
    response = TestClient(app).post("/ask", data={"question": q})
    assert "must be an ISO calendar date" in response.text and planner.calls == 0


def test_affiliation_wrong_owner_graph_is_not_used_as_evidence():
    ds = party_dataset()
    party = URIRef(BASE + "test/party")
    triple = (party, iri("members:hasPoliticalAffiliationIdentity"), URIRef(FIANNA))
    ds.graph(graph("political-affiliations")).remove(triple)
    ds.graph(graph("parties")).add(triple)
    q = VARIATIONS[0][0]
    plan, _ = validate_composable_plan_draft(proposal(q, "RP"), question=q)
    report, result = execute_request(make_request(plan, q, date(2026, 5, 1)), DatasetTransport(dataset=ds))
    assert result is None and "Wrong owner graph" in report["error"] and "answer" not in report


def test_article_pac_and_polite_give_are_not_sentence_templates(monkeypatch, tmp_path):
    q = "Can you give me the Fianna Fáil members on the PAC?"
    draft = proposal(q, "KP")
    draft["referents"]["selections"][0]["mention"] = "the PAC"
    app, _ = make_app(monkeypatch, tmp_path, draft)
    response = TestClient(app).post("/ask", data={"question": q})
    assert 'id="query-results"' in response.text and "Alice Example" in response.text


def test_house_only_routing_and_registry_isolation(monkeypatch):
    from poc.nlq import composition_admission
    from poc.nlq.errors import NLQError
    assert not composition_admission.routing_hint("Which members of the Dáil represent Cork currently?")
    def unavailable(): raise NLQError("register unavailable")
    monkeypatch.setattr(composition_admission, "_reviewed_affiliation_labels", unavailable)
    assert not composition_admission.routing_hint("Who is the Taoiseach?")
    assert composition_admission.routing_hint("Which members of Public Accounts represent Kildare North?")


def test_routing_recognizes_only_reviewed_terminal_party_omission(monkeypatch):
    from poc.nlq import composition_admission
    monkeypatch.setattr(composition_admission, "_reviewed_affiliation_labels", lambda: {"local-labour": frozenset({"Labour Party"})})
    assert composition_admission.routing_hint("Which Labour TDs represent Kildare North?")
    monkeypatch.setattr(composition_admission, "_reviewed_affiliation_labels", lambda: {"local-national-labour": frozenset({"National Labour Party"})})
    assert not composition_admission.routing_hint("Which Labour TDs represent Kildare North?")


@pytest.mark.parametrize("scope", ["current Dáil", "current Dáil term"])
def test_approved_legacy_current_dail_scope_not_narrowed(scope):
    from test_nlq_composable_party_temporal import _temporal_draft
    q = f"Which Sinn Féin TDs represented Galway West in the {scope}?"
    draft = _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", term_selector={"kind": "currentTerm"})
    plan, reason = validate_composable_plan_draft(draft, question=q)
    assert plan is not None and reason is None
    with pytest.raises((UnsupportedComposableRequest, ValueError)):
        validate_composable_plan_draft(draft, question=q.rstrip("?") + " who are women?")


def test_legacy_single_representation_cannot_hide_committee():
    q = "Which members of Public Accounts currently represent Kildare North?"
    draft = {"version": 2, "supported": True, "family": "member_relationship_composition", "unsupportedReason": None,
             "intent": "model omitted committee", "referents": {
                 "member": {"type": "Member", "mention": None},
                 "membership": {"type": "DailMembership", "mention": None},
                 "term": {"type": "DailTerm", "mention": None, "selector": {"kind": "currentTerm"}},
                 "constituency": {"type": "DailConstituency", "mention": "Kildare North"}},
             "relations": [{"id": fact, "fact": fact, "from": source, "to": target} for fact, source, target in [
                 ("member_has_membership", "member", "membership"), ("membership_in_term", "membership", "term"),
                 ("membership_represents", "membership", "constituency"), ("constituency_in_term", "constituency", "term")]],
             "constraints": [], "answer": {"kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"], "details": [], "preserveEvidence": False}}
    with pytest.raises(UnsupportedComposableRequest):
        validate_composable_plan_draft(draft, question=q)
    draft["family"] = "constituency_representation"
    draft["referents"]["term"]["selector"] = "currentTerm"
    with pytest.raises(UnsupportedComposableRequest):
        validate_composable_plan_draft(draft, question=q)
