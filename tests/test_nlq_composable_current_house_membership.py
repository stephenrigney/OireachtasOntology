"""Synthetic acceptance for Q19, Q20, and Q23 House-membership queries."""

from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from poc.nlq.composable_plan import execute_question, validate_plan
from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft,
    UnsupportedComposableRequest,
    load_composable_draft_schema,
    validate_composable_plan_draft,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 5)
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
FOAF = "http://xmlns.com/foaf/0.1/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
DCAT = "http://www.w3.org/ns/dcat#"
HOUSE_GRAPH = "https://data.oireachtas.ie/graph/houses"
PARTY_GRAPH = "https://data.oireachtas.ie/graph/parties"
IDENTITY_GRAPH = "https://data.oireachtas.ie/graph/political-affiliations/identities"
DAIL_TERM = "https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/34"
DAIL_TERM_33 = "https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/33"
SEANAD_TERM = "https://data.oireachtas.ie/ie/oireachtas/houseTerm/seanad/27"
FG_IDENTITY = "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fine-gael"

Q19 = "Who was a Senator in the current Seanad and a Deputy in the current Dáil?"
Q20 = "What current Senators previously served in the Dáil?"
Q20_COUNT = "How many current Senators previously served in the Dáil?"
Q23_COUNT = "How many Fine Gael Senators are in the current Seanad?"
Q23_LIST = "Which Fine Gael Senators are in the current Seanad?"


def _u(value: str) -> URIRef:
    return URIRef(value)


def _literal_binding(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Literal):
        if value.language:
            return f"{value}@{value.language}"
        if value.datatype:
            return f"{value}^^<{value.datatype}>"
    return str(value)


class CurrentHouseFixture:
    def __init__(self, *, members=None, duplicate_current_seanad=False):
        self.dataset = Dataset()
        self.queries: list[str] = []
        houses = self.dataset.graph(_u(HOUSE_GRAPH))
        self._add_term(houses, DAIL_TERM, AGENTS + "DailTerm", ("2024-11-29", None))
        self._add_term(houses, DAIL_TERM_33, AGENTS + "DailTerm", ("2020-02-08", "2024-11-08"))
        self._add_term(houses, SEANAD_TERM, AGENTS + "SeanadTerm", ("2025-06-12", None))
        if duplicate_current_seanad:
            duplicate = SEANAD_TERM + "-overlap"
            self._add_term(houses, duplicate, AGENTS + "SeanadTerm", ("2026-01-01", None))
        if members is None:
            members = [
                {
                    "slug": "Sean-Kyne", "name": "Seán Kyne",
                    "seanad": ("2025-06-12T00:00:00", "2026-05-24T23:59:59"),
                    "dail": ("2026-05-25T00:00:00", None),
                },
                {
                    "slug": "Both-Overlap", "name": "Overlap Member",
                    "seanad": ("2025-06-12T00:00:00", None),
                    "dail": ("2024-11-29T00:00:00", None),
                },
                {"slug": "Dail-Only", "name": "Dáil Only", "dail": ("2024-11-29T00:00:00", None)},
                {"slug": "Seanad-Only", "name": "Seanad Only", "seanad": ("2025-06-12T00:00:00", None)},
            ]
        for item in members:
            self.add_member(item)

    @staticmethod
    def _add_term(graph, iri, rdf_type, dates):
        term = _u(iri)
        period = _u(iri + "#period")
        graph.add((term, RDF.type, _u(rdf_type)))
        graph.add((term, _u(DCT + "temporal"), period))
        graph.add((period, RDF.type, _u(DCT + "PeriodOfTime")))
        graph.add((period, _u(DCAT + "startDate"), Literal(dates[0], datatype=XSD.date)))
        if dates[1] is not None:
            graph.add((period, _u(DCAT + "endDate"), Literal(dates[1], datatype=XSD.date)))

    def add_member(
        self, item, *, party=None, party_interval=None, party_identity=FG_IDENTITY,
        party_key="fine-gael", party_label="Fine Gael, 27th Seanad", omit_seanad_range=False,
        omit_dail_range=False, conflicting_membership_range=None,
        conflicting_dail_range=None, conflicting_party_range=None,
    ):
        graph_iri = f"https://data.oireachtas.ie/graph/member/{item['slug']}"
        graph = self.dataset.graph(_u(graph_iri))
        member = _u(f"https://data.oireachtas.ie/ie/oireachtas/member/id/{item['slug']}")
        graph.add((member, RDF.type, _u(AGENTS + "Member")))
        graph.add((member, _u(FOAF + "name"), Literal(item["name"])))
        membership = {}
        for house_key, term, specific_type, omit_range in (
            ("seanad", SEANAD_TERM, "SeanadMembership", omit_seanad_range),
            ("dail", DAIL_TERM, "DailMembership", omit_dail_range),
        ):
            interval = item.get(house_key)
            paths = item.get("dail_paths") if house_key == "dail" else None
            if paths is None:
                paths = [] if interval is None else [(term, interval)]
            if not paths:
                continue
            for path_index, path in enumerate(paths):
                path_term, path_interval = path
                key = f"{house_key}-membership"
                if len(paths) > 1:
                    key += f"-{path_index}"
                resource = _u(str(member) + f"#{key}")
                membership.setdefault(house_key, resource)
                graph.add((member, _u(MEMBERS + "hasMembersMembership"), resource))
                graph.add((resource, RDF.type, _u(MEMBERS + "OireachtasMembership")))
                graph.add((resource, RDF.type, _u(MEMBERS + specific_type)))
                graph.add((resource, _u(MEMBERS + "inHouseTerm"), _u(path_term)))
                if not omit_range:
                    ranges = [path_interval]
                    if house_key == "seanad" and conflicting_membership_range is not None:
                        ranges.append(conflicting_membership_range)
                    if house_key == "dail" and conflicting_dail_range is not None:
                        ranges.append(conflicting_dail_range)
                    for range_index, dates in enumerate(ranges):
                        range_iri = _u(str(resource) + f"#range-{range_index}")
                        graph.add((resource, _u(MEMBERS + "hasMembershipDateRange"), range_iri))
                        graph.add((range_iri, RDF.type, _u(MEMBERS + "DateRange")))
                        graph.add((range_iri, _u(MEMBERS + "StartDate"), Literal(dates[0], datatype=XSD.dateTime)))
                        if dates[1] is not None:
                            graph.add((range_iri, _u(MEMBERS + "EndDate"), Literal(dates[1], datatype=XSD.dateTime)))

        if party is not None:
            if "seanad" not in membership:
                raise ValueError("Party episodes in this fixture require a SeanadMembership.")
            episode = _u(str(member) + "#fine-gael-episode")
            party_iri = _u(f"https://data.oireachtas.ie/ie/oireachtas/party/seanad/27/{party_key}")
            graph.add((member, _u(MEMBERS + "hasMembersMembership"), episode))
            graph.add((episode, RDF.type, _u(MEMBERS + "PartyMembership")))
            graph.add((episode, _u(MEMBERS + "inOireachtasMembership"), membership["seanad"]))
            graph.add((episode, _u(MEMBERS + "isPartyMembershipOf"), party_iri))
            parties = self.dataset.graph(_u(PARTY_GRAPH))
            parties.add((party_iri, RDF.type, _u(MEMBERS + "ParliamentaryParty")))
            parties.add((party_iri, _u(SKOS + "prefLabel"), Literal(party_label, lang="en")))
            parties.add((party_iri, _u(MEMBERS + "activeDuringTerm"), _u(SEANAD_TERM)))
            identities = self.dataset.graph(_u(IDENTITY_GRAPH))
            identities.add((party_iri, _u(MEMBERS + "hasPoliticalAffiliationIdentity"), _u(party_identity)))
            identities.add((_u(party_identity), RDF.type, _u(MEMBERS + "PoliticalAffiliationIdentity")))
            identity_label = "Fine Gael" if party_identity == FG_IDENTITY else "Fianna Fáil"
            identities.add((_u(party_identity), _u(SKOS + "prefLabel"), Literal(identity_label, lang="en")))
            if party_interval is not None:
                ranges = [party_interval]
                if conflicting_party_range is not None:
                    ranges.append(conflicting_party_range)
                for index, interval in enumerate(ranges):
                    range_iri = _u(str(episode) + f"#range-{index}")
                    graph.add((episode, _u(MEMBERS + "hasMembershipDateRange"), range_iri))
                    graph.add((range_iri, RDF.type, _u(MEMBERS + "DateRange")))
                    graph.add((range_iri, _u(MEMBERS + "StartDate"), Literal(interval[0], datatype=XSD.dateTime)))
                    if interval[1] is not None:
                        graph.add((range_iri, _u(MEMBERS + "EndDate"), Literal(interval[1], datatype=XSD.dateTime)))

    def readiness(self):
        names = (
            "Houses", "Parties", "Constituencies", "Members", "Bills", "Offices",
            "Committees", "AdministrativeUnits", "CabinetMemberships",
        )
        return FusekiReadiness("ready", True, tuple((name, True) for name in names), "synthetic current House fixture")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type != "SELECT":
            raise AssertionError(f"unexpected query form: {result.type}")
        columns = tuple(str(variable) for variable in result.vars)
        rows = tuple(tuple(_literal_binding(value) for value in row) for row in result)
        return QueryResult("select", columns, rows)


class FixedPlanGenerator:
    def __init__(self, draft):
        self.draft = draft
        self.closed = False

    def generate(self, question: str) -> str:
        return json.dumps(self.draft, ensure_ascii=False)

    def close(self):
        self.closed = True


def _q19_draft():
    return {
        "version": 2, "supported": True, "family": "member_relationship_composition",
        "unsupportedReason": None, "intent": "Find Member identities with recorded membership in both current House terms.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "seanad_membership": {"type": "SeanadMembership", "mention": None},
            "seanad_term": {"type": "SeanadTerm", "mention": None, "selector": {"kind": "currentTerm"}},
            "dail_membership": {"type": "DailMembership", "mention": None},
            "dail_term": {"type": "DailTerm", "mention": None, "selector": {"kind": "currentTerm"}},
        },
        "relations": [
            {"id": "member-seanad", "fact": "member_has_seanad_membership", "from": "member", "to": "seanad_membership"},
            {"id": "seanad-term", "fact": "seanad_membership_in_term", "from": "seanad_membership", "to": "seanad_term"},
            {"id": "member-dail", "fact": "member_has_membership", "from": "member", "to": "dail_membership"},
            {"id": "dail-term", "fact": "membership_in_term", "from": "dail_membership", "to": "dail_term"},
        ],
        "constraints": [],
        "answer": {
            "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
            "details": [], "preserveEvidence": False,
        },
    }


def _q20_draft(*, count=False):
    list_answer = {
        "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
        "details": [
            {"referent": "seanad_membership", "display": ["start", "end"]},
            {"referent": "seanad_term", "display": ["label"]},
            {"referent": "dail_membership", "display": ["start", "end"]},
            {"referent": "dail_term", "display": ["label"]},
        ],
        "preserveEvidence": True,
    }
    return {
        "version": 2, "supported": True, "family": "member_relationship_composition",
        "unsupportedReason": None, "intent": "Find current Senators with a recorded prior Dáil membership path.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "seanad_membership": {"type": "SeanadMembership", "mention": None},
            "seanad_term": {"type": "SeanadTerm", "mention": None, "selector": {"kind": "currentTerm"}},
            "dail_membership": {"type": "DailMembership", "mention": None},
            "dail_term": {"type": "DailTerm", "mention": None},
        },
        "relations": [
            {"id": "member-seanad", "fact": "member_has_seanad_membership", "from": "member", "to": "seanad_membership"},
            {"id": "seanad-term", "fact": "seanad_membership_in_term", "from": "seanad_membership", "to": "seanad_term"},
            {"id": "member-dail", "fact": "member_has_membership", "from": "member", "to": "dail_membership"},
            {"id": "dail-term", "fact": "membership_in_term", "from": "dail_membership", "to": "dail_term"},
        ],
        "constraints": [],
        "answer": ({"kind": "count", "referent": "member", "distinctBy": "identity"}
                   if count else list_answer),
    }


def _q23_draft(*, count=True):
    list_answer = {
        "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
        "details": [
            {"referent": "affiliation", "display": ["label"]},
            {"referent": "episode", "display": ["start", "end"]},
            {"referent": "membership", "display": ["start", "end"]},
        ],
        "preserveEvidence": True,
    }
    return {
        "version": 2, "supported": True, "family": "member_relationship_composition",
        "unsupportedReason": None, "intent": "Count active Fine Gael Members in the current Seanad.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "membership": {"type": "SeanadMembership", "mention": None},
            "term": {"type": "SeanadTerm", "mention": None, "selector": {"kind": "currentTerm"}},
            "episode": {"type": "PartyMembershipEpisode", "mention": None},
            "party": {"type": "ParliamentaryParty", "mention": None},
            "affiliation": {"type": "PoliticalAffiliationIdentity", "mention": "Fine Gael"},
        },
        "relations": [
            {"id": "member-seanad", "fact": "member_has_seanad_membership", "from": "member", "to": "membership"},
            {"id": "membership-term", "fact": "seanad_membership_in_term", "from": "membership", "to": "term"},
            {"id": "member-episode", "fact": "member_party_membership", "from": "member", "to": "episode"},
            {"id": "episode-membership", "fact": "party_episode_in_seanad_membership", "from": "episode", "to": "membership"},
            {"id": "episode-party", "fact": "episode_in_parliamentary_party", "from": "episode", "to": "party"},
            {"id": "party-term", "fact": "party_active_during_seanad_term", "from": "party", "to": "term"},
            {"id": "party-affiliation", "fact": "parliamentary_party_has_affiliation_identity", "from": "party", "to": "affiliation"},
        ],
        "constraints": [{
            "referent": "episode", "field": "partySeanadEpisodeInterval", "operator": "overlaps", "value": "membership",
        }],
        "answer": ({"kind": "count", "referent": "member", "distinctBy": "identity"} if count else list_answer),
    }


def _run(question, draft, fixture):
    generator = FixedPlanGenerator(draft)
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        semantic_plan_generator_factory=lambda: generator,
    )
    return outcome, generator


def _ask_client(monkeypatch, question, draft, fixture):
    from poc.nlq import app as app_module

    generator = FixedPlanGenerator(draft)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    client = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    ))
    return client.post("/ask", data={"question": question, "mode": "phase2"}), generator


def _party_members():
    return [
        {
            "slug": "Active-Senator", "name": "Active Senator",
            "seanad": ("2020-01-01T00:00:00", "2026-11-05T00:00:00"),
        },
        {
            "slug": "Membership-Ended", "name": "Membership Ended",
            "seanad": ("2020-01-01T00:00:00", "2026-11-04T23:59:59"),
        },
        {
            "slug": "Party-Ended", "name": "Party Ended",
            "seanad": ("2020-01-01T00:00:00", None),
        },
    ]


def _add_party_evidence(fixture):
    fixture.add_member(
        _party_members()[0], party=True,
        party_interval=("2026-11-05T00:00:00", None),
    )
    fixture.add_member(
        _party_members()[1], party=True,
        party_interval=("2020-01-01T00:00:00", None),
    )
    fixture.add_member(
        _party_members()[2], party=True,
        party_interval=("2020-01-01T00:00:00", "2026-11-04T23:59:59"),
    )


def test_q19_returns_exact_identity_intersection_and_separate_nonoverlapping_intervals():
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Sean-Kyne", "name": "Seán Kyne",
        "seanad": ("2025-06-12T00:00:00", "2026-05-24T23:59:59"),
        "dail": ("2026-05-25T00:00:00", None),
    })
    fixture.add_member({
        "slug": "Dail-Only", "name": "Dáil Only", "dail": ("2024-11-29T00:00:00", None),
    })
    fixture.add_member({
        "slug": "Seanad-Only", "name": "Seanad Only", "seanad": ("2025-06-12T00:00:00", None),
    })
    outcome, generator = _run(Q19, _q19_draft(), fixture)

    assert outcome.status == "success", outcome.diagnostic
    assert len(outcome.result.rows) == 1
    member, member_iri, seanad_interval, dail_interval = outcome.result.rows[0]
    assert (member, member_iri) == (
        "Seán Kyne", "https://data.oireachtas.ie/ie/oireachtas/member/id/Sean-Kyne",
    )
    assert "2026-05-24T23:59:59" in seanad_interval
    assert "2026-05-25T00:00:00" in dail_interval
    assert "does not assert simultaneous or current service" in outcome.diagnostic
    assert "SELECT DISTINCT ?member" in outcome.sparql
    assert "SeanadMembership" in outcome.sparql and "DailMembership" in outcome.sparql
    assert generator.closed


def test_q19_paginates_complete_cross_house_intersection():
    fixture = CurrentHouseFixture(members=[])
    for index in range(101):
        fixture.add_member({
            "slug": f"Cross-{index:03}", "name": f"Cross Member {index:03}",
            "seanad": ("2025-06-12T00:00:00", None),
            "dail": ("2024-11-29T00:00:00", None),
        })
    outcome, _generator = _run(Q19, _q19_draft(), fixture)
    assert outcome.status == "success", outcome.diagnostic
    assert len(outcome.result.rows) == 101
    assert any("OFFSET 100" in query for query in fixture.queries)


def test_q19_user_facing_interpretation_does_not_claim_a_dail_only_query(monkeypatch):
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Sean-Kyne", "name": "Seán Kyne",
        "seanad": ("2025-06-12T00:00:00", "2026-05-24T23:59:59"),
        "dail": ("2026-05-25T00:00:00", None),
    })
    response, generator = _ask_client(monkeypatch, Q19, _q19_draft(), fixture)
    assert response.status_code == 200
    assert "current Dáil and current Seanad" in response.text
    assert "term-wide co-membership" in response.text
    assert "previous Dáil" not in response.text
    assert generator.closed


def test_q19_does_not_answer_when_current_house_term_dates_are_ambiguous():
    fixture = CurrentHouseFixture(members=[], duplicate_current_seanad=True)
    outcome, _generator = _run(Q19, _q19_draft(), fixture)
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "exactly one current Seanad" in outcome.diagnostic
    assert not any("?seanad_membership" in query for query in fixture.queries)


def test_q19_fails_closed_on_missing_or_conflicting_house_membership_interval():
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Uncertain", "name": "Uncertain Member",
        "seanad": ("2025-06-12T00:00:00", None), "dail": ("2024-11-29T00:00:00", None),
    }, omit_seanad_range=True)
    outcome, _generator = _run(Q19, _q19_draft(), fixture)
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "no mapped date-range/start" in outcome.diagnostic

    conflict = CurrentHouseFixture(members=[])
    conflict.add_member({
        "slug": "Conflicting", "name": "Conflicting Member",
        "seanad": ("2025-06-12T00:00:00", None), "dail": ("2024-11-29T00:00:00", None),
    }, conflicting_membership_range=("2026-01-01T00:00:00", None))
    outcome, _generator = _run(Q19, _q19_draft(), conflict)
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "missing or conflicting date-range evidence" in outcome.diagnostic


def test_q19_refuses_simultaneous_service_and_extra_house_term_filters():
    plan = _q19_draft()
    simultaneous_question = "Who simultaneously served as a Senator in the current Seanad and a Deputy in the current Dáil?"
    with pytest.raises(UnsupportedComposableRequest, match="Simultaneity"):
        validate_composable_plan_draft(plan, question=simultaneous_question)
    ordinal = copy.deepcopy(plan)
    ordinal["referents"]["dail_term"]["selector"] = {"kind": "termNumber", "number": 34}
    with pytest.raises(InvalidComposableDraft):
        validate_composable_plan_draft(ordinal, question=Q19)


def test_q19_accepts_original_past_tense_was_wording():
    final, unsupported = validate_composable_plan_draft(_q19_draft(), question=Q19)
    assert unsupported is None
    assert final["family"] == "member_relationship_composition"


@pytest.mark.parametrize("question", [
    "Which Members used to be Senators in the current Seanad and are Deputies in the current Dáil?",
    "Who are no longer Senators in the current Seanad but are Deputies in the current Dáil?",
    "Which former Senators were in the current Seanad and are Deputies in the current Dáil?",
    "Who was a Senator in the current Seanad in the past and a Deputy in the current Dáil?",
])
def test_q19_refuses_historical_current_contrast_instead_of_dropping_it(question):
    with pytest.raises(UnsupportedComposableRequest):
        validate_composable_plan_draft(_q19_draft(), question=question)


def test_q20_requires_active_seanad_membership_and_strictly_earlier_finite_dail_end():
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Prior-Service", "name": "Prior Service",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
    })
    outcome, _generator = _run(Q20, _q20_draft(), fixture)

    assert outcome.status == "success", outcome.diagnostic
    assert len(outcome.result.rows) == 1
    row = outcome.result.rows[0]
    assert row[:2] == (
        "Prior Service", "https://data.oireachtas.ie/ie/oireachtas/member/id/Prior-Service",
    )
    assert "seanad-membership" in row[2] and SEANAD_TERM in row[2]
    assert "2025-06-12T00:00:00" in row[2]
    assert "dail-membership" in row[3] and DAIL_TERM_33 in row[3]
    assert "2024-11-08T23:59:59" in row[3]
    assert "strictly before" in outcome.diagnostic
    assert "absence does not show" in outcome.diagnostic
    assert "SELECT DISTINCT ?member" in outcome.sparql
    assert "DailMembership" in outcome.sparql and "SeanadMembership" in outcome.sparql
    assert "VALUES ?seanadTerm" in outcome.sparql


def test_q20_inclusive_asof_strict_boundary_open_dail_and_currently_expired_seanad():
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Inclusive-AsOf", "name": "Inclusive AsOf",
        "seanad": ("2025-06-12T00:00:00", "2026-11-05T00:00:00"),
        "dail_paths": [
            (DAIL_TERM, ("2024-11-29T00:00:00", "2025-06-11T23:59:59")),
            (DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59")),
        ],
    })
    fixture.add_member({
        "slug": "Equal-Endpoint", "name": "Equal Endpoint",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM, ("2024-11-29T00:00:00", "2025-06-12T00:00:00"))],
    })
    fixture.add_member({
        "slug": "Open-Dail", "name": "Open Dail",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM, ("2024-11-29T00:00:00", None))],
    })
    fixture.add_member({
        "slug": "Expired-Seanad", "name": "Expired Seanad",
        "seanad": ("2025-06-12T00:00:00", "2026-11-04T23:59:59"),
        "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
    })
    fixture.add_member({
        "slug": "End-After-Start", "name": "End After Start",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM, ("2024-11-29T00:00:00", "2025-06-12T00:00:01"))],
    })

    outcome, _generator = _run(Q20, _q20_draft(), fixture)

    assert outcome.status == "success", outcome.diagnostic
    assert len(outcome.result.rows) == 1
    name, member_iri, seanad_evidence, dail_evidence = outcome.result.rows[0]
    assert name == "Inclusive AsOf"
    assert member_iri.endswith("/Inclusive-AsOf")
    assert "path 1:" in seanad_evidence and "path 2:" in seanad_evidence
    assert "path 1:" in dail_evidence and "path 2:" in dail_evidence
    assert DAIL_TERM in dail_evidence and DAIL_TERM_33 in dail_evidence
    assert "Equal Endpoint" not in str(outcome.result.rows)
    assert "Open Dail" not in str(outcome.result.rows)
    assert "Expired Seanad" not in str(outcome.result.rows)
    assert "End After Start" not in str(outcome.result.rows)


def test_q20_never_cross_joins_different_member_identities():
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Dail-Only-Prior", "name": "Dáil Only Prior",
        "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
    })
    fixture.add_member({
        "slug": "Seanad-Only-Open-Dail", "name": "Seanad With Open Dáil",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM, ("2024-11-29T00:00:00", None))],
    })

    outcome, _generator = _run(Q20, _q20_draft(), fixture)

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "does not establish that nobody else served" in outcome.diagnostic


def test_q20_does_not_answer_when_current_seanad_term_is_not_uniquely_date_resolved():
    fixture = CurrentHouseFixture(members=[], duplicate_current_seanad=True)
    fixture.add_member({
        "slug": "Candidate", "name": "Candidate",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
    })

    outcome, _generator = _run(Q20, _q20_draft(), fixture)

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "exactly one current Seanad" in outcome.diagnostic
    assert not any("?seanad_membership" in query for query in fixture.queries)


@pytest.mark.parametrize("uncertainty", [
    "missing_seanad", "conflicting_seanad", "missing_dail", "conflicting_dail",
])
def test_q20_fails_closed_on_missing_or_conflicting_membership_intervals(uncertainty):
    fixture = CurrentHouseFixture(members=[])
    member = {
        "slug": "Uncertain-Prior-Service", "name": "Uncertain Prior Service",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
    }
    options = {}
    if uncertainty == "missing_seanad":
        options["omit_seanad_range"] = True
    elif uncertainty == "conflicting_seanad":
        options["conflicting_membership_range"] = ("2026-01-01T00:00:00", None)
    elif uncertainty == "missing_dail":
        options["omit_dail_range"] = True
    else:
        options["conflicting_dail_range"] = ("2026-01-01T00:00:00", None)
    fixture.add_member(member, **options)

    outcome, _generator = _run(Q20, _q20_draft(), fixture)

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "missing or conflicting date-range evidence" in outcome.diagnostic or "no mapped date-range/start" in outcome.diagnostic


def test_q20_count_and_list_share_complete_bounded_paginated_selection():
    count_fixture = CurrentHouseFixture(members=[])
    list_fixture = CurrentHouseFixture(members=[])
    for index in range(101):
        item = {
            "slug": f"Prior-Member-{index:03}", "name": f"Prior Member {index:03}",
            "seanad": ("2025-06-12T00:00:00", None),
            "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
        }
        count_fixture.add_member(item)
        list_fixture.add_member(item)

    counted, _generator = _run(Q20_COUNT, _q20_draft(count=True), count_fixture)
    listed, _generator = _run(Q20, _q20_draft(), list_fixture)

    assert counted.status == listed.status == "success", (counted.diagnostic, listed.diagnostic)
    assert counted.result.rows == (("101",),)
    assert len(listed.result.rows) == 101
    assert counted.result.rows[0][0] == str(len(listed.result.rows))
    assert "OFFSET 100" in "\n".join(count_fixture.queries)
    assert "OFFSET 100" in "\n".join(list_fixture.queries)
    assert counted.sparql == listed.sparql
    assert "completeness" in counted.diagnostic


def test_q20_refuses_extra_filters_dates_ordinals_and_simultaneity():
    questions = [
        "How many current Fine Gael Senators previously served in the Dáil?",
        "Which current Senators previously served in the Dáil and sat on a committee?",
        "Which current Senators previously served in the Dáil and held ministerial office?",
        "Which current Senators previously served in the Dáil during 2020?",
        "How many prior Dáil terms did current Senators serve?",
        "Which current Senators simultaneously served in the Dáil?",
        "Which current Senators previously served in the 34th Dáil?",
        "Which current Senators previously served in the current Dáil?",
        "Which current Senators were elected in 2025 and previously served in the Dáil?",
    ]
    for question in questions:
        with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
            validate_composable_plan_draft(_q20_draft(count="How many" in question), question=question)


def test_q20_normalizes_evidence_detail_order_but_rejects_omitted_house_path():
    reordered = _q20_draft()
    reordered["answer"]["details"] = [
        {"referent": "dail_term", "display": ["label"]},
        {"referent": "dail_membership", "display": ["start", "end"]},
        {"referent": "seanad_term", "display": ["label"]},
        {"referent": "seanad_membership", "display": ["start", "end"]},
    ]
    final, unsupported = validate_composable_plan_draft(reordered, question=Q20)
    assert unsupported is None
    assert final["answer"]["details"][0]["referent"] == "seanad_membership"
    assert final["answer"]["details"][-1]["referent"] == "dail_term"

    incomplete = _q20_draft()
    incomplete["answer"]["details"].pop()
    with pytest.raises(InvalidComposableDraft):
        validate_composable_plan_draft(incomplete, question=Q20)


@pytest.mark.parametrize("question", [
    Q20,
    "Which present Senators have a recorded earlier Dáil membership?",
    "Which Senators in the current Seanad have a Dáil membership that ended before their Seanad membership began?",
    "How many currently serving Senators have prior recorded Dáil service?",
])
def test_q20_accepts_unseen_prior_service_wordings_without_changing_the_temporal_rule(question):
    count = bool(re.search(r"\b(?:how many|count|number of)\b", question, re.I))
    final, unsupported = validate_composable_plan_draft(_q20_draft(count=count), question=question)
    assert unsupported is None
    assert final["referents"]["seanad_term"]["selector"] == {"kind": "currentTerm", "house": "Seanad"}
    assert final["referents"]["dail_term"] == {"type": "DailTerm"}


def test_q20_user_facing_interpretation_preserves_positive_local_history_qualification(monkeypatch):
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Prior-Service-UI", "name": "Prior Service UI",
        "seanad": ("2025-06-12T00:00:00", None),
        "dail_paths": [(DAIL_TERM_33, ("2020-02-08T00:00:00", "2024-11-08T23:59:59"))],
    })
    response, generator = _ask_client(monkeypatch, Q20, _q20_draft(), fixture)

    assert response.status_code == 200
    assert "strictly before" in response.text
    assert "not proof that anyone never served" in response.text
    assert DAIL_TERM_33 in response.text and SEANAD_TERM in response.text
    assert generator.closed


def test_q23_active_seanad_party_count_and_list_share_exact_interval_selection():
    count_fixture = CurrentHouseFixture(members=[])
    _add_party_evidence(count_fixture)
    count, _ = _run(Q23_COUNT, _q23_draft(count=True), count_fixture)
    list_fixture = CurrentHouseFixture(members=[])
    _add_party_evidence(list_fixture)
    listed, _ = _run(Q23_LIST, _q23_draft(count=False), list_fixture)

    assert count.status == listed.status == "success", (count.diagnostic, listed.diagnostic)
    assert count.result.rows == (("1",),)
    assert len(listed.result.rows) == 1
    assert listed.result.rows[0][0] == "Active Senator"
    assert "2026-11-05T00:00:00" in listed.result.rows[0][2]
    assert "Seanad membership" in listed.result.rows[0][2]
    assert count.result.rows[0][0] == str(len(listed.result.rows))
    assert "OFFSET 100" not in "\n".join(count_fixture.queries)
    assert "current source completeness is not certified" in count.diagnostic
    assert "SeanadTerm" in count.sparql and "Fine Gael" not in count.sparql


def test_q23_user_facing_interpretation_names_seanad_party_and_two_active_intervals(monkeypatch):
    fixture = CurrentHouseFixture(members=[])
    _add_party_evidence(fixture)
    response, generator = _ask_client(monkeypatch, Q23_COUNT, _q23_draft(count=True), fixture)
    assert response.status_code == 200
    assert "exact Fine Gael identity" in response.text
    assert "SeanadMembership and PartyMembership intervals" in response.text
    assert "previous Dáil" not in response.text
    assert generator.closed


def test_q23_count_paginates_more_than_one_hundred_active_members_before_aggregation():
    fixture = CurrentHouseFixture(members=[])
    for index in range(101):
        fixture.add_member({
            "slug": f"Senator-{index:03}", "name": f"Senator {index:03}",
            "seanad": ("2020-01-01T00:00:00", "2026-11-05T00:00:00"),
        }, party=True, party_interval=("2020-01-01T00:00:00", None))
    outcome, _generator = _run(Q23_COUNT, _q23_draft(count=True), fixture)
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.rows == (("101",),)
    assert any("OFFSET 100" in query for query in fixture.queries)


def test_q23_does_not_join_a_party_label_to_the_wrong_affiliation_identity():
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({
        "slug": "Lookalike", "name": "Lookalike Senator",
        "seanad": ("2020-01-01T00:00:00", None),
    }, party=True, party_interval=("2020-01-01T00:00:00", None),
       party_identity="https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail",
       party_key="fine-gael-label-only", party_label="Fine Gael, 27th Seanad")
    parties = fixture.dataset.graph(_u(PARTY_GRAPH))
    identities = fixture.dataset.graph(_u(IDENTITY_GRAPH))
    actual_fine_gael_party = _u("https://data.oireachtas.ie/ie/oireachtas/party/seanad/27/fine-gael-exact")
    parties.add((actual_fine_gael_party, RDF.type, _u(MEMBERS + "ParliamentaryParty")))
    parties.add((actual_fine_gael_party, _u(SKOS + "prefLabel"), Literal("Fine Gael, 27th Seanad", lang="en")))
    parties.add((actual_fine_gael_party, _u(MEMBERS + "activeDuringTerm"), _u(SEANAD_TERM)))
    identities.add((actual_fine_gael_party, _u(MEMBERS + "hasPoliticalAffiliationIdentity"), _u(FG_IDENTITY)))
    identities.add((_u(FG_IDENTITY), RDF.type, _u(MEMBERS + "PoliticalAffiliationIdentity")))
    identities.add((_u(FG_IDENTITY), _u(SKOS + "prefLabel"), Literal("Fine Gael", lang="en")))
    outcome, _generator = _run(Q23_COUNT, _q23_draft(count=True), fixture)
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "No local PartyMembership episode" in outcome.diagnostic


@pytest.mark.parametrize("uncertainty", ["missing_membership", "conflicting_membership", "conflicting_party"])
def test_q23_fails_closed_on_uncertain_active_interval_evidence(uncertainty):
    fixture = CurrentHouseFixture(members=[])
    member = {
        "slug": "Uncertain-Senator", "name": "Uncertain Senator",
        "seanad": ("2020-01-01T00:00:00", None),
    }
    if uncertainty == "missing_membership":
        fixture.add_member(member, party=True, party_interval=("2020-01-01T00:00:00", None), omit_seanad_range=True)
    elif uncertainty == "conflicting_membership":
        fixture.add_member(member, party=True, party_interval=("2020-01-01T00:00:00", None),
                           conflicting_membership_range=("2026-01-01T00:00:00", None))
    else:
        fixture.add_member(member, party=True, party_interval=("2020-01-01T00:00:00", None),
                           conflicting_party_range=("2026-01-01T00:00:00", None))
    outcome, _ = _run(Q23_COUNT, _q23_draft(count=True), fixture)
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "Temporal overlap is uncertain" in outcome.diagnostic


@pytest.mark.parametrize(
    "question, mutation",
    [
        (Q23_COUNT, "wrong_house"),
        (Q23_COUNT, "numbered_term"),
        ("How many Fine Gael Senators in the current Seanad simultaneously served?", "none"),
        ("How many Fine Gael Senators in committees are in the current Seanad?", "none"),
    ],
)
def test_q23_refuses_wrong_term_or_dropped_temporal_and_relationship_conditions(question, mutation):
    draft = _q23_draft(count=True)
    if mutation == "wrong_house":
        draft["referents"]["term"]["type"] = "DailTerm"
    elif mutation == "numbered_term":
        draft["referents"]["term"]["selector"] = {"kind": "termNumber", "number": 27}
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(draft, question=question)


@pytest.mark.parametrize("question", [
    "How many former Fine Gael Senators are in the current Seanad?",
    "How many Senators who used to belong to Fine Gael are in the current Seanad?",
    "How many Fine Gael Senators are no longer in the current Seanad?",
    "How many Fine Gael Senators from the past are in the current Seanad?",
])
def test_q23_refuses_former_party_or_historical_current_contrast(question):
    with pytest.raises(UnsupportedComposableRequest):
        validate_composable_plan_draft(_q23_draft(count=True), question=question)


def test_current_house_term_resolver_rejects_missing_or_capped_evidence():
    from poc.nlq.representation import resolve_current_house_term
    from poc.nlq.errors import NLQError

    missing = QueryResult("select", ("term", "start", "end"), ((SEANAD_TERM, "—", "—"),))
    with pytest.raises(NLQError, match="no recorded House-owned start date"):
        resolve_current_house_term(missing, AS_OF, term_type="SeanadTerm")
    capped = QueryResult("select", ("term", "start", "end"), tuple(
        (f"https://data.oireachtas.ie/ie/oireachtas/houseTerm/seanad/{index}", "2020-01-01^^<http://www.w3.org/2001/XMLSchema#date>", "—")
        for index in range(100)
    ))
    with pytest.raises(NLQError, match="incomplete"):
        resolve_current_house_term(capped, AS_OF, term_type="SeanadTerm")


def test_q19_q20_and_q23_drafts_match_reviewed_schemas_and_plans():
    draft_schema = load_composable_draft_schema()
    Draft202012Validator.check_schema(draft_schema)
    Draft202012Validator.check_schema(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text()))
    for question, draft in ((Q19, _q19_draft()), (Q20, _q20_draft()), (Q23_COUNT, _q23_draft())):
        Draft202012Validator(draft_schema).validate(draft)
        final, unsupported = validate_composable_plan_draft(draft, question=question)
        assert unsupported is None
        plan = {"version": 2, "asOf": AS_OF.isoformat(), **final}
        validate_plan(plan)
        if question == Q19:
            assert plan["referents"]["seanad_term"]["selector"] == {
                "kind": "currentTerm", "house": "Seanad",
            }
            assert plan["referents"]["dail_term"]["selector"] == {
                "kind": "currentTerm", "house": "Dail",
            }
        elif question == Q20:
            assert plan["referents"]["seanad_term"]["selector"] == {
                "kind": "currentTerm", "house": "Seanad",
            }
            assert plan["referents"]["dail_term"] == {"type": "DailTerm"}
            assert plan["answer"]["preserveEvidence"] is True
        else:
            assert "partySeanadEpisodeInterval" in final["constraints"][0]["field"]
