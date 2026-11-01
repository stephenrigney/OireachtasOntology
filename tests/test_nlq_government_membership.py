"""Q3 /ask acceptance: constitutional Cabinet evidence, not executive proxies."""

import copy
import json
from datetime import date

import pytest
from jsonschema import Draft202012Validator
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from tests.test_nlq_question_failures import (
    A, M, BASE, ROOT, SourceFixture, FixedGenerator, ask, run, term,
)
from oireachtas_etl.transforms.members import transform_member_with_report
from oireachtas_etl.validation.members import validate_member
from poc.nlq.government import government_plan
from poc.nlq.composable_plan import validate_plan
from poc.nlq.composable_semantic_planner import load_composable_draft_schema


QUESTION = "Who are the Fianna Fáil Members of the Government?"
MARTIN = BASE + "ie/oireachtas/member/id/Micheál-Martin.D.1989-06-29"
GOVERNMENT = URIRef(BASE + "government")
PARTY = URIRef(BASE + "ie/oireachtas/party/dail/34/Fianna_Fáil")


def martin_excerpt():
    """Exact current-term source excerpt; no source office decision is invented.

    Preserved Member page skip-001100.json, /results/98/member/memberships/8,
    sha256 aa591dff3ae205238f5a2731e9922f6ec08f42721f159795b073d9e55918b60c.
    The existing office-decisions.json accepts this Taoiseach occurrence as
    occ-9862f2b2e99387a510d0c032f9d072d794408121d9135b9b132372ccc87c2aef.
    Historical terms are not needed to reproduce this current positive match.
    """
    return {"member": {
        "uri": MARTIN, "memberCode": "Micheál-Martin.D.1989-06-29", "image": False,
        "fullName": "Micheál Martin", "showAs": "Micheál Martin", "firstName": "Micheál", "lastName": "Martin",
        "memberships": [{"membership": {
            "uri": MARTIN + "/house/dail/34", "dateRange": {"start": "2024-11-29", "end": None},
            "house": {"showAs": "34th Dáil", "houseNo": "34", "chamberType": "house", "houseCode": "dail", "uri": str(term(34))},
            "parties": [{"party": {"dateRange": {"start": "2024-11-29", "end": None}, "partyCode": "Fianna_Fáil", "showAs": "Fianna Fáil", "uri": str(PARTY)}}],
            "represents": [{"represent": {"uri": str(term(34)) + "/constituency/Cork-South-Central", "representType": "constituency", "representCode": "Cork-South-Central", "showAs": "Cork South-Central"}}],
            "committees": [],
            "offices": [{"office": {"dateRange": {"start": "2025-01-23", "end": None}, "officeName": {"showAs": "Taoiseach", "uri": None}}}],
        }}],
    }}


class GovernmentFixture(SourceFixture):
    def __init__(self):
        super().__init__()
        wrapper = martin_excerpt()
        occurrence = "occ-9862f2b2e99387a510d0c032f9d072d794408121d9135b9b132372ccc87c2aef"
        decision = json.loads((ROOT / "reconciliation/office-decisions.json").read_text())["decisions"][occurrence]
        assert decision["status"] == "accepted"
        resolutions = [{"occurrence_key": occurrence, "member_iri": MARTIN,
                        "membership_iri": MARTIN + "/house/dail/34", "office_iri": decision["office_iris"][0],
                        "date_range": {"start": "2025-01-23", "end": None}}]
        office_types = {BASE + "office/" + row["key"]: row["office_type"]
                        for row in json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())["offices"]}
        graph, report = transform_member_with_report(wrapper, office_resolutions=resolutions, office_types=office_types)
        assert validate_member(wrapper, graph, office_resolutions=resolutions, office_types=office_types) == report
        self.martin = self.member_graph(MARTIN)
        for triple in graph:
            self.martin.add(triple)
        self.cabinet = next(graph.subjects(RDF.type, M.CabinetMembership))
        self.episode = next(graph.subjects(RDF.type, M.PartyMembership))
        self.parliamentary_membership = URIRef(MARTIN + "/house/dail/34")
        parties = self.dataset.graph(URIRef(BASE + "graph/parties"))
        parties.add((PARTY, RDF.type, M.ParliamentaryParty))
        parties.add((PARTY, M.activeDuringTerm, term(34)))

    def dates(self, subject, start, end):
        self.martin.remove((subject, M.hasMembershipDateRange, None))
        self.add_interval(self.martin, subject, start, end)


def test_q3_actual_ask_uses_source_backed_transform_and_qualifies_roster(monkeypatch):
    fixture = GovernmentFixture()
    outcome = run(fixture, QUESTION)
    assert outcome.status == "success", outcome.diagnostic
    assert validate_plan(outcome.plan) == outcome.plan
    Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())).validate(outcome.plan)
    assert len(outcome.result.rows) == 1
    row = outcome.result.rows[0]
    assert row[:2] == ("Micheál Martin", "Fianna Fáil")
    assert row[4] == MARTIN and row[5] == str(fixture.cabinet) and row[6] == str(fixture.episode)
    assert "2025-01-23" in row[2] and "2024-11-29" in row[3]
    assert "isCabinetMembershipOf" in outcome.sparql and "GovernmentExecutive" not in outcome.sparql
    response = ask(monkeypatch, fixture, QUESTION)
    assert "Micheál Martin" in response.text and "Fianna Fáil" in response.text
    assert "Government membership" in response.text and "Party membership" in response.text
    assert "not a complete Government roster" in response.text
    assert "2026-11-01" in response.text
    assert "Validated composable query plan" in response.text


def test_minister_of_state_only_and_wider_executive_do_not_count(monkeypatch):
    fixture = GovernmentFixture()
    # Existing source-backed Minister-of-State fixture. Its accepted office
    # coverage is deliberately absent; no Cabinet membership may be inferred.
    timmy = json.loads((ROOT / "data/api_examples/member.json").read_text())
    graph, _report = transform_member_with_report(timmy)
    member = URIRef(timmy["member"]["uri"])
    target = fixture.member_graph(str(member))
    for triple in graph:
        target.add(triple)
    assert not list(target.subjects(RDF.type, M.CabinetMembership))
    # Explicit synthetic wider-executive and Minister-of-State holding evidence
    # is not a constitutional CabinetMembership, even for a Fianna Fáil Member.
    holding = URIRef(str(member) + "#synthetic-mos-holding")
    target.add((member, M.hasOfficeHolding, holding))
    target.add((holding, RDF.type, M.OfficeHolding))
    target.add((member, RDF.type, M.GovernmentExecutive))
    fake = URIRef(str(member) + "#synthetic-executive-membership")
    target.add((member, M.hasMembersMembership, fake))
    target.add((fake, RDF.type, M.MinisterOfStateMembership))
    outcome = run(fixture, QUESTION)
    assert {row[0] for row in outcome.result.rows} == {"Micheál Martin"}
    response = ask(monkeypatch, fixture, QUESTION)
    assert "Timmy Dooley</td>" not in response.text
    assert "Minister-of-State-only" in response.text


def test_multiple_supporting_holdings_do_not_duplicate_a_member(monkeypatch):
    fixture = GovernmentFixture()
    holding = URIRef(MARTIN + "#synthetic-second-support")
    fixture.martin.add((fixture.cabinet, M.supportedByOfficeHolding, holding))
    outcome = run(fixture, QUESTION)
    assert outcome.status == "success" and len(outcome.result.rows) == 1
    assert str(holding) in outcome.result.rows[0][-1]
    assert str(holding) in ask(monkeypatch, fixture, QUESTION).text


@pytest.mark.parametrize("resource", ["cabinet", "episode", "parliamentary_membership"])
@pytest.mark.parametrize("dates", [("2024-11-29", "2025-01-01"), ("2027-01-01", None)])
def test_expired_and_future_memberships_are_not_contemporaneous(monkeypatch, resource, dates):
    fixture = GovernmentFixture()
    fixture.dates(getattr(fixture, resource), *dates)
    outcome = run(fixture, QUESTION)
    assert outcome.status == "source_data_unavailable" and outcome.result is None
    response = ask(monkeypatch, fixture, QUESTION)
    assert "Incomplete current-office/party coverage" in response.text
    assert "Micheál Martin</td>" not in response.text


@pytest.mark.parametrize("resource", ["cabinet", "episode", "parliamentary_membership"])
def test_unknown_or_conflicting_dates_fail_closed(monkeypatch, resource):
    fixture = GovernmentFixture()
    subject = getattr(fixture, resource)
    fixture.martin.remove((subject, M.hasMembershipDateRange, None))
    outcome = run(fixture, QUESTION)
    assert outcome.status == "source_data_unavailable" and outcome.result is None
    assert "interval" in ask(monkeypatch, fixture, QUESTION).text
    fixture.add_interval(fixture.martin, subject, "2025-01-01", None)
    interval = next(fixture.martin.objects(subject, M.hasMembershipDateRange))
    fixture.martin.add((interval, M.StartDate, Literal("2025-02-01T00:00:00", datatype=XSD.dateTime)))
    assert run(fixture, QUESTION).result is None


def test_reference_date_and_inclusive_boundaries_are_used(monkeypatch):
    fixture = GovernmentFixture()
    assert run(fixture, QUESTION, as_of=date(2025, 1, 22)).result is None
    assert run(fixture, QUESTION, as_of=date(2025, 1, 23)).status == "success"
    fixture.dates(fixture.cabinet, "2025-01-23", "2026-11-01")
    assert run(fixture, QUESTION).status == "success"
    assert run(fixture, QUESTION, as_of=date(2026, 11, 2)).result is None
    assert "2025-01-23" in ask(monkeypatch, fixture, QUESTION, as_of=date(2025, 1, 23)).text


def test_same_day_but_disjoint_cabinet_and_party_intervals_do_not_count(monkeypatch):
    fixture = GovernmentFixture()
    cabinet_range = next(fixture.martin.objects(fixture.cabinet, M.hasMembershipDateRange))
    party_range = next(fixture.martin.objects(fixture.episode, M.hasMembershipDateRange))
    fixture.martin.set((cabinet_range, M.StartDate, Literal("2026-11-01T12:00:00", datatype=XSD.dateTime)))
    fixture.martin.set((party_range, M.EndDate, Literal("2026-11-01T11:00:00", datatype=XSD.dateTime)))
    outcome = run(fixture, QUESTION)
    assert outcome.status == "source_data_unavailable" and outcome.result is None
    assert "Incomplete current-office/party coverage" in ask(monkeypatch, fixture, QUESTION).text


def test_party_in_an_expired_house_term_cannot_supply_current_affiliation(monkeypatch):
    fixture = GovernmentFixture()
    fixture.martin.set((fixture.parliamentary_membership, M.inHouseTerm, term(33)))
    parties = fixture.dataset.graph(URIRef(BASE + "graph/parties"))
    parties.set((PARTY, M.activeDuringTerm, term(33)))
    assert run(fixture, QUESTION).result is None
    assert "Incomplete current-office/party coverage" in ask(monkeypatch, fixture, QUESTION).text


def test_missing_current_cabinet_coverage_is_not_an_empty_roster(monkeypatch):
    fixture = SourceFixture()
    outcome = run(fixture, QUESTION)
    assert outcome.status == "source_data_unavailable" and outcome.result is None
    response = ask(monkeypatch, fixture, QUESTION)
    assert "Incomplete current-office/party coverage" in response.text
    assert "Unsupported request" not in response.text
    assert "No results" not in response.text


def test_duplicate_affiliation_identity_is_ambiguous_before_roster_query(monkeypatch):
    from oireachtas_etl.political_affiliations import GRAPH_IRI
    fixture = GovernmentFixture()
    graph = fixture.dataset.graph(URIRef(GRAPH_IRI))
    other = URIRef(BASE + "political-affiliation/synthetic-duplicate")
    graph.add((other, RDF.type, M.PoliticalAffiliationIdentity))
    graph.add((other, SKOS.prefLabel, Literal("Fianna Fáil", lang="en")))
    outcome = run(fixture, QUESTION)
    assert outcome.status == "ambiguous" and len(outcome.candidates) == 2
    assert len(fixture.queries) == 1
    assert "Ambiguous entity" in ask(monkeypatch, fixture, QUESTION).text


@pytest.mark.parametrize("question", [
    "Which Fianna Fáil members are in Government?",
    "List the Fianna Fáil Government members.",
    "Who are the current Fianna Fáil members of the constitutional Government?",
])
def test_government_paraphrases_preserve_the_constitutional_boundary(monkeypatch, question):
    fixture = GovernmentFixture()
    assert run(fixture, question).result.rows == run(fixture, QUESTION).result.rows
    assert "not a complete Government roster" in ask(monkeypatch, fixture, question).text


def test_government_semantic_fallback_is_grounded_closed_and_executable(monkeypatch):
    fixture = GovernmentFixture()
    plan = government_plan("Fianna Fáil", as_of=date(2026, 11, 1))
    draft = {"version": 2, "supported": True, "family": "government_party_members", "unsupportedReason": None,
             "intent": "Find party members in the constitutional Government at the reference date.",
             "referents": {key: {"type": value["type"], "mention": value.get("mention")} for key, value in plan["referents"].items()},
             "relations": plan["relations"], "constraints": [], "answer": plan["answer"]}
    Draft202012Validator(load_composable_draft_schema()).validate(draft)
    question = "Name politicians affiliated with Fianna Fáil serving in the constitutional Government."
    generator = FixedGenerator(draft)
    outcome = run(fixture, question, generator=generator)
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.rows == run(fixture, QUESTION).result.rows
    assert "not a complete Government roster" in ask(monkeypatch, fixture, question, generator=generator).text
    bad = copy.deepcopy(draft)
    bad["relations"].pop()
    assert run(fixture, question, generator=FixedGenerator(bad)).status == "validation_failure"
    assert run(fixture, "Name Fianna Fáil members of the wider Government Executive.", generator=generator).status == "unsupported_request"
