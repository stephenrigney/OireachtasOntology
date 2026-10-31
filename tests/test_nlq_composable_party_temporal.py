"""Controlled RDF acceptance for dated party/constituency compositions."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from poc.nlq.composable_plan import (
    PlanError,
    compile_member_relationship_composition_query,
    execute_question,
)
from poc.nlq.composable_semantic_planner import (
    build_composable_planner_instructions,
    load_composable_draft_schema,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 28)
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
FOAF = "http://xmlns.com/foaf/0.1/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
TERM = "https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/33"
CONSTITUENCY = "https://data.oireachtas.ie/ie/oireachtas/constituency/dail/Galway-West-33"
MEMBER = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne"
SF_IDENTITY = "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein"
FF_IDENTITY = "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail"
QUESTION_U06 = "Which political parties were represented by TDs for Galway West during the 33rd Dáil?"
QUESTION_U16 = "Which Sinn Féin TDs represented Galway West during the 33rd Dáil?"


def _binding(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Literal):
        if value.language:
            return f"{value}@{value.language}"
        if value.datatype:
            return f"{value}^^<{value.datatype}>"
    return str(value)


class PartyRepresentationFixture:
    """Small named-graph fixture with independent term, constituency and party owners."""

    def __init__(
        self,
        *,
        membership_interval=("2020-01-01T00:00:00", "2020-12-31T00:00:00"),
        episodes=None,
        omit_membership_range=False,
        omit_membership_start=False,
        conflicting_membership_range=False,
    ):
        if episodes is None:
            episodes = [
                {
                    "key": "sinn-fein-33", "party_label": "Sinn Féin, 33rd Dáil",
                    "identity": SF_IDENTITY, "identity_label": "Sinn Féin",
                    "interval": ("2020-12-31T00:00:00", "2020-12-31T00:00:00"),
                },
                {
                    "key": "fianna-fail-33", "party_label": "Fianna Fáil, 33rd Dáil",
                    "identity": FF_IDENTITY, "identity_label": "Fianna Fáil",
                    "interval": ("2020-06-01T00:00:00", None),
                },
            ]
        self.dataset = Dataset()
        self.queries: list[str] = []
        self._add_shared_occurrences()
        self._add_member(
            membership_interval,
            omit_range=omit_membership_range,
            omit_start=omit_membership_start,
            conflicting_range=conflicting_membership_range,
        )
        for index, episode in enumerate(episodes):
            self._add_party_episode(index, episode)

    def _add_shared_occurrences(self):
        houses = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
        term = URIRef(TERM)
        houses.add((term, RDF.type, URIRef(AGENTS + "DailTerm")))
        houses.add((term, URIRef(AGENTS + "termNo"), Literal(33, datatype=XSD.integer)))

        constituencies = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/constituencies"))
        constituency = URIRef(CONSTITUENCY)
        constituencies.add((constituency, RDF.type, URIRef(MEMBERS + "DailConstituency")))
        constituencies.add((constituency, URIRef(SKOS + "prefLabel"), Literal("Galway West", lang="en")))
        constituencies.add((constituency, URIRef(MEMBERS + "constituencyInHouseTerm"), term))

    def _add_member(self, interval, *, omit_range, omit_start, conflicting_range):
        graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Aoife-Byrne"))
        member = URIRef(MEMBER)
        membership = URIRef(MEMBER + "#dail-membership-33")
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, URIRef(FOAF + "name"), Literal("Aoife Byrne")))
        graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), membership))
        graph.add((membership, RDF.type, URIRef(MEMBERS + "OireachtasMembership")))
        graph.add((membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
        graph.add((membership, URIRef(MEMBERS + "inHouseTerm"), URIRef(TERM)))
        graph.add((membership, URIRef(MEMBERS + "isRepresentativeFrom"), URIRef(CONSTITUENCY)))
        if omit_range:
            return
        for range_index in range(2 if conflicting_range else 1):
            date_range = URIRef(MEMBER + f"#membership-date-range-{range_index}")
            graph.add((membership, URIRef(MEMBERS + "hasMembershipDateRange"), date_range))
            graph.add((date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
            if not omit_start:
                start = interval[0] if range_index == 0 else "2020-02-01T00:00:00"
                graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
            end = interval[1]
            if end is not None:
                graph.add((date_range, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))

    def _add_party_episode(self, index, item):
        graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Aoife-Byrne"))
        member = URIRef(MEMBER)
        membership = URIRef(MEMBER + "#dail-membership-33")
        episode = URIRef(MEMBER + f"#party-membership-{index}")
        party = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/33/" + item["key"])
        graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), episode))
        graph.add((episode, RDF.type, URIRef(MEMBERS + "PartyMembership")))
        graph.add((episode, URIRef(MEMBERS + "inOireachtasMembership"), membership))
        graph.add((episode, URIRef(MEMBERS + "isPartyMembershipOf"), party))

        parties = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
        parties.add((party, RDF.type, URIRef(MEMBERS + "ParliamentaryParty")))
        parties.add((party, URIRef(SKOS + "prefLabel"), Literal(item["party_label"], lang="en")))
        parties.add((party, URIRef(MEMBERS + "activeDuringTerm"), URIRef(TERM)))

        identities = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/political-affiliations/identities"))
        identity = URIRef(item["identity"])
        identities.add((party, URIRef(MEMBERS + "hasPoliticalAffiliationIdentity"), identity))
        identities.add((identity, RDF.type, URIRef(MEMBERS + "PoliticalAffiliationIdentity")))
        identities.add((identity, URIRef(SKOS + "prefLabel"), Literal(item["identity_label"], lang="en")))

        interval = item.get("interval")
        if interval is None:
            return
        date_range = URIRef(MEMBER + f"#party-date-range-{index}")
        graph.add((episode, URIRef(MEMBERS + "hasMembershipDateRange"), date_range))
        graph.add((date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
        if interval[0] is not None:
            graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(interval[0], datatype=XSD.dateTime)))
        if interval[1] is not None:
            graph.add((date_range, URIRef(MEMBERS + "EndDate"), Literal(interval[1], datatype=XSD.dateTime)))
        if item.get("extra_interval"):
            extra = URIRef(MEMBER + f"#party-date-range-extra-{index}")
            graph.add((episode, URIRef(MEMBERS + "hasMembershipDateRange"), extra))
            graph.add((extra, RDF.type, URIRef(MEMBERS + "DateRange")))
            start, end = item["extra_interval"]
            graph.add((extra, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
            if end is not None:
                graph.add((extra, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))
        if item.get("invalid_start"):
            graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(
                item["invalid_start"] if isinstance(item["invalid_start"], str) else "2020-06-01",
                datatype=XSD.dateTime, normalize=False,
            )))

    def readiness(self):
        return FusekiReadiness(
            "ready", True,
            tuple((name, True) for name in ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")),
            "controlled party/representation fixture",
        )

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type != "SELECT":
            raise AssertionError(f"unexpected query form: {result.type}")
        columns = tuple(str(variable) for variable in result.vars)
        rows = tuple(tuple(_binding(value) for value in row) for row in result)
        return QueryResult("select", columns, rows)


class FixedPlanGenerator:
    def __init__(self, draft):
        self.draft = draft
        self.calls: list[str] = []
        self.closed = False

    def generate(self, question: str) -> str:
        self.calls.append(question)
        return json.dumps(self.draft, ensure_ascii=False)

    def close(self):
        self.closed = True


def _temporal_draft(*, answer_referent="affiliation", affiliation_mention=None, constituency="Galway West"):
    party_list = answer_referent == "affiliation"
    return {
        "version": 2,
        "supported": True,
        "family": "member_relationship_composition",
        "unsupportedReason": None,
        "intent": "Join the selected Dáil representation to overlapping typed party-membership evidence.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "membership": {"type": "DailMembership", "mention": None},
            "term": {"type": "DailTerm", "mention": None, "selector": {"kind": "termNumber", "number": 33}},
            "constituency": {"type": "DailConstituency", "mention": constituency},
            "episode": {"type": "PartyMembershipEpisode", "mention": None},
            "party": {"type": "ParliamentaryParty", "mention": None},
            "affiliation": {"type": "PoliticalAffiliationIdentity", "mention": affiliation_mention},
        },
        "relations": [
            {"id": "member-membership", "fact": "member_has_membership", "from": "member", "to": "membership"},
            {"id": "membership-term", "fact": "membership_in_term", "from": "membership", "to": "term"},
            {"id": "membership-constituency", "fact": "membership_represents", "from": "membership", "to": "constituency"},
            {"id": "constituency-term", "fact": "constituency_in_term", "from": "constituency", "to": "term"},
            {"id": "member-episode", "fact": "member_party_membership", "from": "member", "to": "episode"},
            {"id": "episode-membership", "fact": "party_episode_in_membership", "from": "episode", "to": "membership"},
            {"id": "episode-party", "fact": "episode_in_parliamentary_party", "from": "episode", "to": "party"},
            {"id": "party-term", "fact": "party_active_during_term", "from": "party", "to": "term"},
            {"id": "party-affiliation", "fact": "parliamentary_party_has_affiliation_identity", "from": "party", "to": "affiliation"},
        ],
        "constraints": [{
            "referent": "episode", "field": "partyEpisodeInterval", "operator": "overlaps", "value": "membership",
        }],
        "answer": ({
            "kind": "entities", "referent": "affiliation", "distinctBy": "identity", "display": ["label"],
            "details": [
                {"referent": "member", "display": ["name"]},
                {"referent": "episode", "display": ["start", "end"]},
                {"referent": "membership", "display": ["start", "end"]},
            ],
            "preserveEvidence": True,
        } if party_list else {
            "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
            "details": [
                {"referent": "affiliation", "display": ["label"]},
                {"referent": "episode", "display": ["start", "end"]},
                {"referent": "membership", "display": ["start", "end"]},
            ],
            "preserveEvidence": True,
        }),
    }


def _run(fixture: PartyRepresentationFixture, question: str, draft: dict):
    generator = FixedPlanGenerator(draft)
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        semantic_plan_generator_factory=lambda: generator,
    )
    return outcome, generator


def _ask(monkeypatch, fixture, question, draft):
    from poc.nlq import app as app_module

    generator = FixedPlanGenerator(draft)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})
    return response, generator


def test_temporal_draft_schema_contract_and_exact_evidence_constraints():
    draft = _temporal_draft(affiliation_mention="Sinn Féin")
    errors = list(Draft202012Validator(load_composable_draft_schema()).iter_errors(draft))
    assert not errors
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    definition = next(item for item in contract["constraints"] if item["field"] == "partyEpisodeInterval")
    assert definition["dateDatatype"] == "xsd:dateTime"
    assert definition["endAbsentMeans"] == "open-ended"
    assert definition["rangeOrStartAbsentMeans"] == "uncertain"


def test_planner_instructions_include_exact_temporal_answer_and_constraint_shapes():
    instructions = build_composable_planner_instructions()

    assert '"constraints": []' in instructions
    assert '"field":"partyEpisodeInterval","operator":"overlaps","value":"membership"' in instructions
    assert '"referent":"affiliation","distinctBy":"identity"' in instructions
    assert '"referent":"member","distinctBy":"identity"' in instructions
    assert '"referent":"episode","display":["start","end"]' in instructions
    assert '"preserveEvidence":true' in instructions


@pytest.mark.parametrize(("question", "draft"), [
    (QUESTION_U06, _temporal_draft()),
    ("What political parties had Members representing Galway West in the 33rd Dáil?", _temporal_draft()),
    (QUESTION_U16, _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin")),
    (
        "Find Members representing Galway West for Sinn Féin during the 33rd Dáil.",
        _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin"),
    ),
])
def test_integrated_ask_executes_u06_and_u16_paraphrases(question, draft, monkeypatch):
    fixture = PartyRepresentationFixture()
    response, generator = _ask(monkeypatch, fixture, question, draft)

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert "DailMembership" in response.text
    assert "inclusive" in response.text.lower()
    assert "historical source completeness is not certified" in response.text
    assert generator.calls == [question]
    assert generator.closed
    assert fixture.queries
    assert "inOireachtasMembership" in fixture.queries[-1]
    assert "activeDuringTerm" in fixture.queries[-1]
    assert "isRepresentativeFrom" in fixture.queries[-1]
    if draft["answer"]["referent"] == "affiliation":
        assert "Sinn Féin" in response.text and "Fianna Fáil" in response.text
        assert "Aoife Byrne" in response.text
    else:
        assert "Aoife Byrne" in response.text and "Sinn Féin" in response.text


@pytest.mark.parametrize("interval", [
    ("2020-12-31T00:00:00", "2020-12-31T00:00:00"),
    ("2020-12-31T00:00:00", None),
])
def test_inclusive_endpoint_and_open_party_end_are_established_overlaps(interval):
    fixture = PartyRepresentationFixture(episodes=[{
        "key": "sinn-fein-33", "party_label": "Sinn Féin, 33rd Dáil",
        "identity": SF_IDENTITY, "identity_label": "Sinn Féin", "interval": interval,
    }])
    outcome, _ = _run(fixture, QUESTION_U06, _temporal_draft())

    assert outcome.status == "success", outcome.diagnostic
    assert len(outcome.result.rows) == 1
    assert outcome.result.rows[0][0] == "Sinn Féin"
    assert "2020-12-31T00:00:00" in outcome.result.rows[0][2]
    if interval[1] is None:
        assert "open-ended" in outcome.result.rows[0][2]


@pytest.mark.parametrize("fixture", [
    PartyRepresentationFixture(omit_membership_range=True),
    PartyRepresentationFixture(omit_membership_start=True),
    PartyRepresentationFixture(conflicting_membership_range=True),
    PartyRepresentationFixture(episodes=[{
        "key": "sinn-fein-33", "party_label": "Sinn Féin, 33rd Dáil",
        "identity": SF_IDENTITY, "identity_label": "Sinn Féin", "interval": None,
    }]),
    PartyRepresentationFixture(episodes=[{
        "key": "sinn-fein-33", "party_label": "Sinn Féin, 33rd Dáil",
        "identity": SF_IDENTITY, "identity_label": "Sinn Féin",
        "interval": ("2020-06-01T00:00:00", None), "extra_interval": ("2020-07-01T00:00:00", None),
    }]),
    PartyRepresentationFixture(episodes=[{
        "key": "sinn-fein-33", "party_label": "Sinn Féin, 33rd Dáil",
        "identity": SF_IDENTITY, "identity_label": "Sinn Féin",
        "interval": ("2020-06-01T00:00:00", None), "invalid_start": "2020-06-01",
    }]),
])
def test_missing_invalid_or_conflicting_dates_are_uncertain_not_matches(fixture, monkeypatch):
    response, generator = _ask(monkeypatch, fixture, QUESTION_U06, _temporal_draft())

    assert response.status_code == 200
    assert "Temporal overlap is uncertain" in response.text
    assert generator.calls == [QUESTION_U06]
    assert len(fixture.queries) >= 2


def test_historically_nonoverlapping_party_episode_is_not_projected_as_affiliation():
    fixture = PartyRepresentationFixture(episodes=[{
        "key": "sinn-fein-33", "party_label": "Sinn Féin, 33rd Dáil",
        "identity": SF_IDENTITY, "identity_label": "Sinn Féin",
        "interval": ("2021-01-01T00:00:00", None),
    }])
    outcome, _ = _run(fixture, QUESTION_U06, _temporal_draft())

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "No local PartyMembership interval has an established inclusive overlap" in outcome.diagnostic


def test_sinn_fein_alias_resolution_is_limited_to_active_term_party_identities():
    fixture = PartyRepresentationFixture(episodes=[
        {
            "key": "sinn-fein-1957", "party_label": "Historical Sinn Féin A",
            "identity": "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein-1957",
            "identity_label": "Sinn Féin (1957)", "interval": ("2020-06-01T00:00:00", None),
        },
        {
            "key": "sinn-fein-anti-treaty", "party_label": "Historical Sinn Féin B",
            "identity": "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein-anti-treaty",
            "identity_label": "Sinn Féin (Anti-Treaty)", "interval": ("2020-06-01T00:00:00", None),
        },
    ])
    outcome, _ = _run(
        fixture, QUESTION_U16,
        _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin"),
    )

    assert outcome.status == "ambiguous"
    assert len(outcome.candidates) == 2
    assert outcome.result is None
    assert len(fixture.queries) == 3  # term, constituency, term-scoped identity; no answer query
    assert "activeDuringTerm" in fixture.queries[2]


def test_historical_party_alias_is_not_ambiguous_when_only_one_identity_is_active_in_selected_term():
    fixture = PartyRepresentationFixture(episodes=[{
        "key": "sinn-fein-1957", "party_label": "Historical Sinn Féin",
        "identity": "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein-1957",
        "identity_label": "Sinn Féin (1957)", "interval": ("2020-06-01T00:00:00", None),
    }])
    other_party = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/32/sinn-fein-anti-treaty")
    parties = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
    identities = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/political-affiliations/identities"))
    parties.add((other_party, RDF.type, URIRef(MEMBERS + "ParliamentaryParty")))
    parties.add((other_party, URIRef(MEMBERS + "activeDuringTerm"), URIRef(
        "https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/32",
    )))
    identities.add((other_party, URIRef(MEMBERS + "hasPoliticalAffiliationIdentity"), URIRef(
        "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein-anti-treaty",
    )))
    inactive_identity = URIRef("https://data.oireachtas.ie/ie/oireachtas/political-affiliation/sinn-fein-anti-treaty")
    identities.add((inactive_identity, RDF.type, URIRef(MEMBERS + "PoliticalAffiliationIdentity")))
    identities.add((inactive_identity, URIRef(SKOS + "prefLabel"), Literal("Sinn Féin (Anti-Treaty)", lang="en")))
    outcome, _ = _run(
        fixture, QUESTION_U16,
        _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin"),
    )

    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.rows[0][0] == "Aoife Byrne"
    assert len(fixture.queries) == 4
    assert "activeDuringTerm" in fixture.queries[2]


def test_named_party_query_compiler_requires_a_resolved_affiliation_identity():
    fixture = PartyRepresentationFixture()
    outcome, _ = _run(
        fixture, QUESTION_U16,
        _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin"),
    )
    assert outcome.status == "success", outcome.diagnostic
    unresolved = copy.deepcopy(outcome.plan)
    unresolved["referents"]["affiliation"] = {
        "type": "PoliticalAffiliationIdentity",
        "mention": "Sinn Féin",
        "resolution": "unresolved",
    }

    with pytest.raises(PlanError, match="requires the exact resolved affiliation identity"):
        compile_member_relationship_composition_query(
            unresolved, supported_predicates=supported_predicates(ROOT / "ontology"),
        )


@pytest.mark.parametrize(("question", "status", "needle"), [
    (
        "Which Sinn Féin TDs represented Galway West in the 33rd Dáil on 31 February 2024?",
        "clarification_required", "not a valid calendar date",
    ),
    (
        "Which Sinn Féin TDs represented Galway West in the Dáil?",
        "clarification_required", "specify which numbered Dáil term",
    ),
    (
        "Which Sinn Féin TDs represented Galway West in the 33rd Dáil and were also committee members?",
        "unsupported_request", "additional date, temporal, aggregate, or relationship condition",
    ),
    (
        "Which Independent TDs represented Galway West during the 33rd Dáil?",
        "unsupported_request", "not dated ParliamentaryParty affiliation evidence",
    ),
    (
        "Which Sinn Féin TDs represented Galway West in the 33rd Dáil on 1 January 2020?",
        "unsupported_request", "additional calendar-date filter",
    ),
])
def test_preflight_clarifies_or_rejects_extra_scope_before_llm_or_rdf(question, status, needle):
    fixture = PartyRepresentationFixture()
    generator = FixedPlanGenerator(_temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin"))
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        semantic_plan_generator_factory=lambda: generator,
    )

    assert outcome.status == status
    assert needle.lower() in outcome.diagnostic.lower()
    assert generator.calls == []
    assert not fixture.queries


def test_unsupported_relationship_is_not_misreported_as_missing_evidence():
    fixture = PartyRepresentationFixture()
    draft = _temporal_draft()
    draft["relations"].append({
        "id": "unsupported-vote", "fact": "member_votes_for_bill", "from": "member", "to": "membership",
    })
    outcome, _ = _run(fixture, QUESTION_U06, draft)

    assert outcome.status == "unsupported_request"
    assert "outside the exact reviewed party/representation composition" in outcome.diagnostic
    assert not fixture.queries


def test_ask_path_reports_temporal_evidence_and_never_calls_llm_for_bad_dates(monkeypatch):
    fixture = PartyRepresentationFixture()
    response, generator = _ask(
        monkeypatch, fixture,
        "Which political parties were represented by TDs for Galway West in the 33rd Dáil on 31 February 2024?",
        _temporal_draft(),
    )
    assert response.status_code == 200
    assert "not a valid calendar date" in response.text
    assert generator.calls == []
    assert not fixture.queries
