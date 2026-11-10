"""Office title resolves to an accepted relationship, never an assumed person's name."""

from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import URIRef, Literal
from rdflib.namespace import RDF, SKOS, XSD

from poc.nlq.composable_plan import execute_question, validate_plan, PlanError
from poc.nlq.composable_semantic_planner import (
    validate_composable_plan_draft, load_composable_draft_schema, InvalidComposableDraft, UnsupportedComposableRequest,
)
from poc.nlq.office_representation import FAMILY, make_plan
from poc.nlq.vocabulary import supported_predicates
from poc.nlq.results import QueryResult
from test_nlq_composable_office_evidence import OfficeEvidenceFixture, FixedPlanGenerator, ROOT, BASE, MEMBERS, AGENTS

AS_OF = date(2026, 11, 9)
QUESTION = "What constituency does the Tánaiste represent?"
OFFICE = URIRef(BASE + "office/test-office")
TERM = URIRef(BASE + "ie/oireachtas/house/dail/34")
CONSTITUENCY = URIRef(str(TERM) + "/constituency/Test")


def draft(office="Tánaiste"):
    return {"version": 2, "supported": True, "family": "capability_selection", "unsupportedReason": None,
            "intent": "Current officeholder constituency", "referents": {"capability": FAMILY, "parameters": {"office": office}},
            "relations": [], "constraints": [], "answer": None}


class Fixture(OfficeEvidenceFixture):
    def __init__(self, office_label="Tánaiste"):
        super().__init__()
        g = self.dataset.graph(URIRef(BASE + "graph/offices"))
        g.add((OFFICE, RDF.type, URIRef(MEMBERS + "NamedOffice")))
        g.add((OFFICE, SKOS.prefLabel, Literal(office_label, lang="en")))
        h = self.dataset.graph(URIRef(BASE + "graph/houses"))
        period = URIRef(str(TERM) + "#period")
        for triple in [(TERM, RDF.type, URIRef(AGENTS + "DailTerm")), (TERM, SKOS.prefLabel, Literal("34th Dáil", lang="en")),
                       (TERM, URIRef("http://purl.org/dc/terms/temporal"), period),
                       (period, RDF.type, URIRef("http://purl.org/dc/terms/PeriodOfTime")),
                       (period, URIRef("http://www.w3.org/ns/dcat#startDate"), Literal("2024-11-29", datatype=XSD.date))]: h.add(triple)
        c = self.dataset.graph(URIRef(BASE + "graph/constituencies"))
        for triple in [(CONSTITUENCY, RDF.type, URIRef(MEMBERS + "DailConstituency")),
                       (CONSTITUENCY, URIRef(MEMBERS + "constituencyInHouseTerm"), TERM),
                       (CONSTITUENCY, SKOS.prefLabel, Literal("Test Constituency", lang="en"))]: c.add(triple)

    def holder(self, code="holder", name="Same Name", episodes=None):
        return self.add_member(code, name, episodes if episodes is not None else [{"start": "2025-01-23T00:00:00", "end": None}], office=OFFICE)

    def representation(self, member, code="holder", *, start="2024-11-29T00:00:00", end=None, constituency=CONSTITUENCY):
        g = self.dataset.graph(URIRef(BASE + "graph/member/" + code))
        membership = URIRef(member + "/house/dail/34")
        r = URIRef(str(membership) + "#range")
        for triple in [(URIRef(member), URIRef(MEMBERS + "hasMembersMembership"), membership),
                       (membership, RDF.type, URIRef(MEMBERS + "DailMembership")),
                       (membership, URIRef(MEMBERS + "inHouseTerm"), TERM),
                       (membership, URIRef(MEMBERS + "isRepresentativeFrom"), constituency),
                       (membership, URIRef(MEMBERS + "hasMembershipDateRange"), r)]: g.add(triple)
        if start: g.add((r, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
        if end: g.add((r, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))
        return str(membership), str(r)


def run(f, question=QUESTION, office="Tánaiste"):
    return execute_question(question, as_of=AS_OF, fuseki=f, supported_predicates=supported_predicates(ROOT / "ontology"),
                            semantic_plan_generator_factory=lambda: FixedPlanGenerator(draft(office)))


@pytest.mark.parametrize("question", [QUESTION, "Which constituency does the current Tánaiste represent?",
    "What Dáil constituency does the Tánaiste currently represent?", "Which constituency is the Tánaiste a TD for?",
    "What constituency does the Tánaiste currently represent?"])
def test_chain_uses_exact_officeholder_identity_even_with_duplicate_member_names(question):
    f = Fixture(); holder = f.holder(); membership, r = f.representation(holder)
    other = f.add_member("other", "Same Name", []); f.representation(other, code="other")
    out = run(f, question)
    assert out.status == "success", out.diagnostic
    assert len(out.result.rows) == 1
    row = dict(zip(out.result.columns, out.result.rows[0]))
    assert row["Member identity"] == holder and row["Constituency identity"] == str(CONSTITUENCY)
    assert row["Membership identity"] == membership and row["Membership date range"] == r
    assert row["Office identity"] == str(OFFICE) and row["Holding identity"].startswith(holder + "#office-holding")
    assert row["Holding date range"].endswith("#date-range") and row["Holding start"] == "2025-01-23T00:00:00"
    assert row["As of"] == AS_OF.isoformat() and row["Membership start"].startswith("2024-11-29T00:00:00")
    assert validate_plan(out.plan) == out.plan
    assert "not a certified complete" in out.diagnostic
    assert not any("LCASE(?name)" in q or "LCASE(?memberName)" in q for q in f.queries)


def test_different_reviewed_named_office_reuses_same_bounded_chain():
    f = Fixture("Minister for Testing"); member = f.holder(); f.representation(member)
    out = run(f, "What constituency does the Minister for Testing represent?", office="Minister for Testing")
    assert out.status == "success", out.diagnostic


@pytest.mark.parametrize("episodes", [[], [{"start": "2024-01-01T00:00:00", "end": "2025-01-22T00:00:00"}],
    [{"start": "2027-01-01T00:00:00", "end": None}], [{"missing_range": True}],
    [{"start": "2025-01-23T00:00:00", "conflicting_ranges": [("2025-02-01T00:00:00", None)]}],
    [{"start": None, "end": None}]])
def test_absent_past_future_or_uncertain_holding_never_substitutes_expected_member(episodes):
    f = Fixture(); holder = f.holder(episodes=episodes); f.representation(holder)
    out = run(f)
    assert out.status == "source_data_unavailable" and out.result is None
    assert not any("SELECT DISTINCT ?member ?name ?membership ?constituency" in q for q in f.queries)


def test_two_current_relationships_fail_closed_even_for_same_member():
    f = Fixture(); f.holder(episodes=[{"start": "2025-01-01T00:00:00"}, {"start": "2025-02-01T00:00:00"}])
    out = run(f)
    assert out.status == "source_data_unavailable" and "More than one" in out.diagnostic and out.result is None
    f = Fixture(); f.holder(); f.holder("second", "Second Holder")
    assert run(f).result is None


@pytest.mark.parametrize("representation", ["none", "past", "future", "missing_start", "conflict"])
def test_officeholder_is_not_assumed_to_be_a_td_or_given_historical_constituency(representation):
    f = Fixture(); member = f.holder()
    if representation != "none":
        f.representation(member, start=None if representation == "missing_start" else "2027-01-01T00:00:00" if representation == "future" else "2024-11-29T00:00:00",
                         end="2025-01-01T00:00:00" if representation == "past" else None)
    if representation == "conflict":
        other = URIRef(str(CONSTITUENCY) + "-other")
        c = f.dataset.graph(URIRef(BASE + "graph/constituencies"))
        for t in [(other, RDF.type, URIRef(MEMBERS + "DailConstituency")), (other, URIRef(MEMBERS + "constituencyInHouseTerm"), TERM),
                  (other, SKOS.prefLabel, Literal("Other", lang="en"))]: c.add(t)
        f.representation(member, constituency=other)
    out = run(f)
    assert out.status == "source_data_unavailable" and out.result is None
    if representation != "conflict":
        assert member in out.diagnostic and "not assumed to be a TD" in out.diagnostic


@pytest.mark.parametrize("question", [
    "What constituency did the Tánaiste represent?", "What constituency does the Tánaiste represent in 2020?",
    "What constituency does the Tánaiste represent on 2025-01-23?", "What constituency does the Tánaiste represent while in Fine Gael?",
    "What constituency does the Tánaiste represent and what is their party?", "What constituency does the Tánaiste represent excluding Wicklow?",
    "What constituency does the former Tánaiste represent?", "What constituency does the Tánaiste represent in the Seanad?",
    "How many constituencies does the Tánaiste represent?",
])
def test_additional_conditions_and_historical_scope_are_not_discarded(question):
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(draft(), question=question)
    f = Fixture(); f.holder()
    out = run(f, question)
    assert out.result is None
    assert not any("holdingDateRange" in q for q in f.queries)


def test_ambiguous_reviewed_office_identity_does_not_query_holdings():
    f = Fixture()
    g = f.dataset.graph(URIRef(BASE + "graph/offices"))
    other = URIRef(BASE + "office/another-test-office")
    g.add((other, RDF.type, URIRef(MEMBERS + "NamedOffice")))
    g.add((other, SKOS.prefLabel, Literal("Tánaiste", lang="en")))
    out = run(f)
    assert out.status == "ambiguous" and len(out.candidates) == 2 and out.result is None
    assert not any("holdingDateRange" in q for q in f.queries)


def test_holding_selection_paginates_all_accepted_episodes_before_unique_current_choice():
    f = Fixture()
    episodes = [{"start": f"{1800+i}-01-01T00:00:00", "end": f"{1800+i}-12-31T00:00:00"} for i in range(101)]
    holder = f.holder(episodes=episodes + [{"start": "2025-01-23T00:00:00"}]); f.representation(holder)
    out = run(f)
    assert out.status == "success", out.diagnostic
    assert any("OFFSET 100" in q for q in f.queries)


@pytest.mark.parametrize("fault", ["truncated", "missing_columns", "escaped_member"])
def test_relationship_bound_representation_rejects_malformed_or_wrong_identity_rows(fault):
    f = Fixture(); holder = f.holder(); f.representation(holder)
    query = f.query
    def malformed(sparql):
        result = query(sparql)
        if "SELECT DISTINCT ?member ?name ?membership ?constituency" not in sparql:
            return result
        if fault == "missing_columns": return QueryResult("select", ("member",), ((holder,),))
        if fault == "truncated": return QueryResult("select", result.columns, (result.rows[0][:-1],))
        row = list(result.rows[0]); row[result.columns.index("member")] = BASE + "ie/oireachtas/member/id/not-the-holder"
        return QueryResult("select", result.columns, (tuple(row),))
    f.query = malformed
    out = run(f)
    assert out.status == "source_data_unavailable" and out.result is None


def test_future_holding_with_invalid_end_cannot_hide_uncertainty():
    f = Fixture(); holder = f.holder(episodes=[{"start": "2025-01-23T00:00:00"},
        {"start": "2027-01-01T00:00:00", "end": "2026-01-01T00:00:00"}]); f.representation(holder)
    out = run(f)
    assert out.status == "source_data_unavailable" and out.result is None


def test_schema_and_canonical_plan_are_closed_and_evidence_preserving():
    Draft202012Validator(load_composable_draft_schema()).validate(draft())
    plan = make_plan("Tánaiste", AS_OF)
    for key in ("relations", "constraints"):
        p = deepcopy(plan); p[key].pop()
        with pytest.raises(PlanError): validate_plan(p)
    p = deepcopy(plan); p["answer"]["preserveEvidence"] = False
    with pytest.raises(PlanError): validate_plan(p)
    p = draft(); p["referents"]["parameters"]["member"] = "Expected Name"
    with pytest.raises(InvalidComposableDraft): validate_composable_plan_draft(p, question=QUESTION)


def test_phase2_returns_source_blocker_instead_of_member_name_failure(monkeypatch, tmp_path):
    from poc.nlq import app as module
    f = Fixture(); member = f.holder(episodes=[{"start": "2020-01-01T00:00:00", "end": "2021-01-01T00:00:00"}]); f.representation(member)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(module, "FusekiQueryClient", lambda *a, **kw: f)
    app = module.create_app(semantic_plan_generator_factory=lambda: FixedPlanGenerator(draft()), feedback_directory=tmp_path)
    response = TestClient(app).post("/ask", data={"question": QUESTION, "mode": "phase2"})
    assert 'data-outcome="missing_or_unaccepted_evidence"' in response.text
    assert "No accepted current OfficeHolding" in response.text and "does not establish a vacancy" in response.text
    assert response.context["result"] is None and "No local Member record" not in response.text
