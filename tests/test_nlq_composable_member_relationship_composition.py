"""Integrated acceptance for reusable Member/membership/HouseTerm composition."""

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
    validate_plan,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates
from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft,
    UnsupportedComposableRequest,
    build_composable_planner_instructions,
    complete_v2_plan,
    load_composable_draft_schema,
    validate_composable_plan_draft,
)
from poc.nlq.safety import MAX_RESULT_OFFSET, MAX_RESULT_ROWS
from test_nlq_composable_party_temporal import _current_term_fixture


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 28)
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
FOAF = "http://xmlns.com/foaf/0.1/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCT = "http://purl.org/dc/terms/"
DCAT = "http://www.w3.org/ns/dcat#"
HOUSE_GRAPH = "https://data.oireachtas.ie/graph/houses"
CONSTITUENCY_GRAPH = "https://data.oireachtas.ie/graph/constituencies"
QUESTION_TERMS = "Which Members served in both the 32nd and 33rd Dáil?"
QUESTION_REPRESENTATION = "Who represented Dublin Central during the 31st Dáil?"

MEMBER_ALICE = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne"
MEMBER_BOB = "https://data.oireachtas.ie/ie/oireachtas/member/id/Conor-Daly"
MEMBER_CARA = "https://data.oireachtas.ie/ie/oireachtas/member/id/Eimear-Walsh"
MEMBER_SINGLE_EPISODE = "https://data.oireachtas.ie/ie/oireachtas/member/id/Fiona-SingleEpisode"


def _binding(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Literal):
        if value.language:
            return f"{value}@{value.language}"
        if value.datatype:
            return f"{value}^^<{value.datatype}>"
    return str(value)


class MemberRelationshipFixture:
    def __init__(
        self, *, duplicate_term_31: bool = False,
        duplicate_constituency_31: bool = False, extra_shared_members: int = 0,
    ):
        self.dataset = Dataset()
        self.queries: list[str] = []
        houses = self.dataset.graph(URIRef(HOUSE_GRAPH))
        self.terms: dict[int, str] = {}
        for ordinal in (31, 32, 33):
            iri = f"https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/{ordinal}"
            self.terms[ordinal] = iri
            term = URIRef(iri)
            houses.add((term, RDF.type, URIRef(AGENTS + "DailTerm")))
            houses.add((term, URIRef(SKOS + "prefLabel"), Literal(f"{_ordinal(ordinal)} Dáil", lang="en")))
            houses.add((term, URIRef(AGENTS + "termNo"), Literal(ordinal, datatype=XSD.integer)))
        if duplicate_term_31:
            duplicate = URIRef("https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/31-duplicate")
            houses.add((duplicate, RDF.type, URIRef(AGENTS + "DailTerm")))
            houses.add((duplicate, URIRef(AGENTS + "termNo"), Literal(31, datatype=XSD.integer)))

        self.constituencies: dict[tuple[str, int], str] = {}
        self._add_constituency("Dublin Central", 31, "Dublin-Central-31")
        self._add_constituency("Dublin South", 31, "Dublin-South-31")
        self._add_constituency("Dublin Central", 32, "Dublin-Central-32")
        if duplicate_constituency_31:
            self._add_constituency("Dublin Central", 31, "Dublin-Central-31-duplicate")

        self._add_member(MEMBER_ALICE, "Aoife Byrne", "Aoife-Byrne", {
            31: "Dublin Central", 32: "Dublin Central", 33: None,
        })
        self._add_member(MEMBER_BOB, "Conor Daly", "Conor-Daly", {
            31: "Dublin South", 32: None, 33: "Dublin Central",
        })
        self._add_member(MEMBER_CARA, "Eimear Walsh", "Eimear-Walsh", {
            32: "Dublin Central", 33: None,
        })
        # Adversarial RDF: one evidence resource points at both terms. The
        # two-term projection requires independent membership identities.
        self._add_member(MEMBER_SINGLE_EPISODE, "Fiona SingleEpisode", "Fiona-SingleEpisode", {32: None})
        single_episode_graph = self.dataset.graph(URIRef(
            "https://data.oireachtas.ie/graph/member/Fiona-SingleEpisode",
        ))
        single_episode = URIRef(f"{MEMBER_SINGLE_EPISODE}#dail-membership-32")
        single_episode_graph.add((single_episode, URIRef(MEMBERS + "inHouseTerm"), URIRef(self.terms[33])))

        for index in range(extra_shared_members):
            key = f"Large-Result-Member-{index:03d}"
            self._add_member(
                f"https://data.oireachtas.ie/ie/oireachtas/member/id/{key}",
                f"Large Result Member {index:03d}", key,
                {32: None, 33: None},
            )

    def _add_constituency(self, label: str, ordinal: int, key: str) -> None:
        iri = f"https://data.oireachtas.ie/ie/oireachtas/constituency/dail/{key}"
        self.constituencies[(key, ordinal)] = iri
        graph = self.dataset.graph(URIRef(CONSTITUENCY_GRAPH))
        constituency = URIRef(iri)
        graph.add((constituency, RDF.type, URIRef(MEMBERS + "Constituencies")))
        graph.add((constituency, RDF.type, URIRef(MEMBERS + "DailConstituency")))
        graph.add((constituency, URIRef(SKOS + "prefLabel"), Literal(label, lang="en")))
        graph.add((constituency, URIRef(MEMBERS + "constituencyInHouseTerm"), URIRef(self.terms[ordinal])))

    def _add_member(self, iri: str, name: str, graph_key: str, representations: dict[int, str | None]) -> None:
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{graph_key}"))
        member = URIRef(iri)
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, URIRef(FOAF + "name"), Literal(name)))
        for ordinal, representation in representations.items():
            membership = URIRef(f"{iri}#dail-membership-{ordinal}")
            graph.add((member, URIRef(MEMBERS + "hasMembersMembership"), membership))
            graph.add((membership, RDF.type, URIRef(MEMBERS + "OireachtasMembership")))
            graph.add((membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
            graph.add((membership, URIRef(MEMBERS + "inHouseTerm"), URIRef(self.terms[ordinal])))
            if representation:
                matching = [
                    resource for (key, term), resource in self.constituencies.items()
                    if term == ordinal and key.startswith(representation.replace(" ", "-"))
                ]
                # Choose the ordinary occurrence if an ambiguity fixture adds another identity.
                matching.sort(key=lambda value: ("duplicate" in value, value))
                if matching:
                    graph.add((membership, URIRef(MEMBERS + "isRepresentativeFrom"), URIRef(matching[0])))

    def readiness(self):
        sources = ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")
        return FusekiReadiness("ready", True, tuple((name, True) for name in sources), "synthetic member-composition fixture")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        raw = self.dataset.query(query)
        if raw.type == "ASK":
            return QueryResult("ask", boolean=bool(raw.askAnswer))
        columns = tuple(str(variable) for variable in raw.vars)
        rows = tuple(tuple(_binding(value) for value in row) for row in raw)
        return QueryResult("select", columns, rows)


def _ordinal(number: int) -> str:
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _intersection_draft(first: int = 32, second: int = 33) -> dict:
    return {
        "version": 2,
        "supported": True,
        "family": "member_relationship_composition",
        "unsupportedReason": None,
        "intent": "Find Members with recorded membership in both selected Dáil terms.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "membership_a": {"type": "DailMembership", "mention": None},
            "term_a": {"type": "DailTerm", "mention": None, "selector": {"kind": "termNumber", "number": first}},
            "membership_b": {"type": "DailMembership", "mention": None},
            "term_b": {"type": "DailTerm", "mention": None, "selector": {"kind": "termNumber", "number": second}},
        },
        "relations": [
            {"id": "member-to-first-membership", "fact": "member_has_membership", "from": "member", "to": "membership_a"},
            {"id": "first-membership-to-term", "fact": "membership_in_term", "from": "membership_a", "to": "term_a"},
            {"id": "member-to-second-membership", "fact": "member_has_membership", "from": "member", "to": "membership_b"},
            {"id": "second-membership-to-term", "fact": "membership_in_term", "from": "membership_b", "to": "term_b"},
        ],
        "constraints": [],
        "answer": {
            "kind": "entities", "referent": "member", "distinctBy": "identity",
            "display": ["name"], "details": [], "preserveEvidence": False,
        },
    }


def _representation_draft(ordinal: int = 31, constituency: str = "Dublin Central") -> dict:
    return {
        "version": 2,
        "supported": True,
        "family": "member_relationship_composition",
        "unsupportedReason": None,
        "intent": "Find Members represented by the named constituency in the selected Dáil term.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "membership": {"type": "DailMembership", "mention": None},
            "term": {"type": "DailTerm", "mention": None, "selector": {"kind": "termNumber", "number": ordinal}},
            "constituency": {"type": "DailConstituency", "mention": constituency},
        },
        "relations": [
            {"id": "member-membership", "fact": "member_has_membership", "from": "member", "to": "membership"},
            {"id": "membership-term", "fact": "membership_in_term", "from": "membership", "to": "term"},
            {"id": "membership-constituency", "fact": "membership_represents", "from": "membership", "to": "constituency"},
            {"id": "constituency-term", "fact": "constituency_in_term", "from": "constituency", "to": "term"},
        ],
        "constraints": [],
        "answer": {
            "kind": "entities", "referent": "member", "distinctBy": "identity",
            "display": ["name"], "details": [], "preserveEvidence": False,
        },
    }


def _member_count_draft(ordinal: int = 31, constituency: str = "Dublin Central", *, date_point: str | None = None) -> dict:
    draft = _representation_draft(ordinal, constituency)
    if date_point is not None:
        draft["constraints"] = [{
            "referent": "membership", "field": "membershipInterval",
            "operator": "on", "value": date_point,
        }]
    draft["answer"] = {"kind": "count", "referent": "member", "distinctBy": "identity"}
    return draft


def _anchored_shared_constituency_draft(
    *,
    anchor: str = "Aoife Byrne",
    ordinal: int | None = None,
    previous: bool = False,
    count: bool = False,
) -> dict:
    if previous:
        selector = {"kind": "previousTerm"}
    else:
        selector = {"kind": "termNumber", "number": ordinal or 32}
    return {
        "version": 2,
        "supported": True,
        "family": "member_relationship_composition",
        "unsupportedReason": None,
        "intent": "Find other Members recorded in the anchor's exact constituency and term.",
        "referents": {
            "member": {"type": "Member", "mention": None},
            "membership": {"type": "DailMembership", "mention": None},
            "term": {"type": "DailTerm", "mention": None, "selector": selector},
            "constituency": {"type": "DailConstituency", "mention": None},
            "anchorMember": {"type": "Member", "mention": anchor},
            "anchorMembership": {"type": "DailMembership", "mention": None},
        },
        "relations": [
            {"id": "anchor-member-membership", "fact": "member_has_membership", "from": "anchorMember", "to": "anchorMembership"},
            {"id": "anchor-membership-term", "fact": "membership_in_term", "from": "anchorMembership", "to": "term"},
            {"id": "anchor-membership-constituency", "fact": "membership_represents", "from": "anchorMembership", "to": "constituency"},
            {"id": "answer-member-membership", "fact": "member_has_membership", "from": "member", "to": "membership"},
            {"id": "answer-membership-term", "fact": "membership_in_term", "from": "membership", "to": "term"},
            {"id": "answer-membership-constituency", "fact": "membership_represents", "from": "membership", "to": "constituency"},
            {"id": "constituency-term", "fact": "constituency_in_term", "from": "constituency", "to": "term"},
        ],
        "constraints": [],
        "answer": (
            {"kind": "count", "referent": "member", "distinctBy": "identity"}
            if count else {
                "kind": "entities", "referent": "member", "distinctBy": "identity",
                "display": ["name"], "details": [], "preserveEvidence": False,
            }
        ),
    }


def _add_term_chronology(fixture: MemberRelationshipFixture, ordinal: int, start: str, end: str | None) -> None:
    houses = fixture.dataset.graph(URIRef(HOUSE_GRAPH))
    term = URIRef(fixture.terms[ordinal])
    period = URIRef(f"{fixture.terms[ordinal]}#term-period")
    houses.add((term, URIRef(DCT + "temporal"), period))
    houses.add((period, RDF.type, URIRef(DCT + "PeriodOfTime")))
    houses.add((period, URIRef(DCAT + "startDate"), Literal(start, datatype=XSD.dateTime)))
    if end is not None:
        houses.add((period, URIRef(DCAT + "endDate"), Literal(end, datatype=XSD.dateTime)))


def _add_membership_interval(
    fixture: MemberRelationshipFixture, member_iri: str, graph_key: str, ordinal: int,
    start: str | None, end: str | None, *, extra_key: str = "dates",
) -> None:
    graph = fixture.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{graph_key}"))
    membership = URIRef(f"{member_iri}#dail-membership-{ordinal}")
    period = URIRef(f"{membership}#{extra_key}")
    graph.add((membership, URIRef(MEMBERS + "hasMembershipDateRange"), period))
    graph.add((period, RDF.type, URIRef(MEMBERS + "DateRange")))
    if start is not None:
        graph.add((period, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
    if end is not None:
        graph.add((period, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))


class FixedPlanGenerator:
    def __init__(self, draft: dict | None = None):
        self.draft = draft
        self.calls: list[str] = []
        self.closed = False

    def generate(self, question: str) -> str:
        self.calls.append(question)
        return json.dumps(self.draft, ensure_ascii=False)

    def close(self):
        self.closed = True


def _run(fixture: MemberRelationshipFixture, question: str, draft: dict):
    generator = FixedPlanGenerator(draft)
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        semantic_plan_generator_factory=lambda: generator,
    )
    return outcome, generator


def test_v2_contract_and_strict_draft_schema_cover_both_relationship_projections():
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    plan_schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    draft_schema = load_composable_draft_schema()
    Draft202012Validator.check_schema(plan_schema)
    Draft202012Validator.check_schema(draft_schema)
    assert contract["contractVersion"] == "2.29.0"
    count_contract = contract["memberCountProjections"]["member_relationship_composition"]["semantics"]
    assert "Stage C term-scoped ParliamentaryParty listing" in count_contract
    assert "not seats/election totals" in count_contract
    assert "member_relationship_composition" in plan_schema["properties"]["family"]["enum"]
    assert any(item["id"] == "member_relationship_composition" for item in contract["questionFamilies"])
    validator = Draft202012Validator(draft_schema)
    assert validator.is_valid(_intersection_draft())
    assert validator.is_valid(_representation_draft())
    assert validator.is_valid(_member_count_draft())
    assert validator.is_valid(_member_count_draft(date_point="1994-06-14"))
    assert validator.is_valid(_anchored_shared_constituency_draft(previous=True, count=True))
    assert "oneOf" not in json.dumps(draft_schema)
    assert len(draft_schema["$defs"]["answer"]["anyOf"]) == 2
    assert "Never output SPARQL" in build_composable_planner_instructions()
    instructions = build_composable_planner_instructions()
    assert "describe the missing capability actually requested" in instructions
    assert "do not describe every unsupported question as a member-relationship limitation" in instructions.casefold()
    assert '"latestRecorded"' in instructions
    assert "latest recorded term, the most recent term, or the last term" in instructions
    assert '"last term in the Dáil"' in instructions
    assert "recorded Member RDF identities, not seats or election events" in instructions
    assert "globally previous Dáil" in instructions
    assert "term-wide recorded co-membership, not simultaneous service" in instructions


@pytest.mark.parametrize(("question", "draft", "expected"), [
    (QUESTION_TERMS, _intersection_draft(), (("Aoife Byrne", MEMBER_ALICE),)),
    (
        "Find Members whose recorded Dáil service includes each of the 32nd and 33rd terms.",
        _intersection_draft(),
        (("Aoife Byrne", MEMBER_ALICE),),
    ),
    (QUESTION_REPRESENTATION, _representation_draft(), (("Aoife Byrne", MEMBER_ALICE),)),
    (
        "Which Members held the Dublin Central seat in the 31st Dáil?",
        _representation_draft(),
        (("Aoife Byrne", MEMBER_ALICE),),
    ),
])
def test_integrated_ask_executes_fresh_member_relationship_paraphrases(question, draft, expected, monkeypatch):
    from poc.nlq import app as app_module

    fixture = MemberRelationshipFixture()
    generator = FixedPlanGenerator(draft)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert "Generated SPARQL" in response.text
    assert "Aoife Byrne" in response.text
    assert "Member identity" in response.text
    assert expected[0][1] in response.text
    assert generator.calls == [question]
    assert generator.closed
    assert len(fixture.queries) == 3
    answer_query = fixture.queries[-1]
    assert "SELECT DISTINCT ?member ?memberName" in answer_query
    assert "members:inHouseTerm" in answer_query
    assert "agents:termNo" in answer_query
    if "constituency" in answer_query:
        assert "members:isRepresentativeFrom" in answer_query
        assert "members:constituencyInHouseTerm" in answer_query
    if "membership_a" in answer_query:
        assert "FILTER(?membership_a != ?membership_b)" in answer_query
    assert "SERVICE" not in answer_query.upper()
    assert "FROM NAMED" not in answer_query.upper()


def test_member_count_and_list_share_the_same_term_constituency_selection_and_distinct_identity_set():
    fixture = MemberRelationshipFixture()
    duplicate_label_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne-duplicate"
    future_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/After-Date"
    fourth_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Fourth-Recorded-Member"
    fixture._add_member(duplicate_label_iri, "Aoife Byrne", "Aoife-Byrne-duplicate", {31: "Dublin Central"})
    fixture._add_member(future_iri, "After Date Member", "After-Date", {31: "Dublin Central"})
    fixture._add_member(fourth_iri, "Fourth Recorded Member", "Fourth-Recorded-Member", {31: "Dublin Central"})

    list_question = "Who represented Dublin Central during the 31st Dáil?"
    count_question = "How many TDs represented Dublin Central in the 31st Dáil?"
    listed, _ = _run(fixture, list_question, _representation_draft())
    counted, _ = _run(fixture, count_question, _member_count_draft())

    assert listed.status == counted.status == "success"
    listed_identities = {row[1] for row in listed.result.rows}
    assert listed_identities == {
        MEMBER_ALICE, duplicate_label_iri, future_iri,
        fourth_iri,
    }
    assert counted.result.rows == (("4",),)
    assert counted.result.columns == ("Distinct recorded Members",)
    assert listed.sparql == counted.sparql
    assert counted.plan["referents"] == listed.plan["referents"]
    assert counted.plan["relations"] == listed.plan["relations"]
    assert "not seats or election events" in counted.diagnostic


def test_distinct_member_count_is_rendered_through_integrated_ask(monkeypatch):
    from poc.nlq import app as app_module

    fixture = MemberRelationshipFixture()
    duplicate_label_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne-duplicate"
    fixture._add_member(duplicate_label_iri, "Aoife Byrne", "Aoife-Byrne-duplicate", {31: "Dublin Central"})
    question = "How many TDs represented Dublin Central in the 31st Dáil?"
    generator = FixedPlanGenerator(_member_count_draft())
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert "Distinct recorded Members" in response.text
    assert ">2<" in response.text
    assert "not seats or election events" in response.text
    assert generator.calls == [question]
    assert generator.closed


@pytest.mark.parametrize(("question", "constituency", "expected_scope"), [
    (
        "How many TDs represented the Dublin Central constituency in this Dáil?",
        "Dublin Central",
        "term-wide ‘in this Dáil’ scope does not require a membership interval",
    ),
    (
        "How many TDs currently represent Meath East constituency?",
        "Meath East",
        f"DailMembership interval to contain {AS_OF.isoformat()}",
    ),
])
def test_current_term_composition_explanation_matches_validated_scope(
    monkeypatch, question, constituency, expected_scope,
):
    from poc.nlq import app as app_module

    fixture = _current_term_fixture(constituency_label=constituency)
    # The current-point interval is supplied by the approved local as-of rule;
    # the planner draft must not invent a date absent from the user's wording.
    draft = _member_count_draft(constituency=constituency)
    draft["referents"]["term"]["selector"] = {"kind": "currentTerm"}
    generator = FixedPlanGenerator(draft)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})

    assert response.status_code == 200
    assert 'data-outcome="answer"' in response.text, response.text
    assert "House-date-resolved current Dáil" in response.text
    assert expected_scope in response.text
    assert "previous Dáil" not in response.text
    assert "currentTerm" in response.text
    assert "Query result is shown above." in response.text
    for tab_id in ("tab-compiled", "tab-executed"):
        tab = response.text.split(f'id="{tab_id}"', 1)[1].split("</button>", 1)[0]
        assert "disabled" not in tab
    assert generator.calls == [question]
    assert generator.closed


def test_member_date_point_applies_inclusive_mapped_intervals_to_the_same_list_and_count_selection():
    fixture = MemberRelationshipFixture()
    duplicate_label_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne-duplicate"
    future_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/After-Date"
    fixture._add_member(duplicate_label_iri, "Aoife Byrne", "Aoife-Byrne-duplicate", {31: "Dublin Central"})
    fixture._add_member(future_iri, "After Date Member", "After-Date", {31: "Dublin Central"})
    _add_membership_interval(fixture, MEMBER_ALICE, "Aoife-Byrne", 31,
                             "1990-01-01T00:00:00", "1994-06-14T23:59:59")
    _add_membership_interval(fixture, duplicate_label_iri, "Aoife-Byrne-duplicate", 31,
                             "1994-06-14T00:00:00", "1995-01-01T00:00:00")
    _add_membership_interval(fixture, future_iri, "After-Date", 31,
                             "1994-06-15T00:00:00", None)

    point = "1994-06-14"
    question = "Which Members represented Dublin Central in the 31st Dáil on 14 June 1994?"
    list_draft = _representation_draft()
    list_draft["constraints"] = [{
        "referent": "membership", "field": "membershipInterval", "operator": "on", "value": point,
    }]
    listed, _ = _run(fixture, question, list_draft)
    counted, _ = _run(fixture, "How many Members represented Dublin Central in the 31st Dáil on 14 June 1994?",
                       _member_count_draft(date_point=point))

    assert listed.status == counted.status == "success"
    assert {row[1] for row in listed.result.rows} == {MEMBER_ALICE, duplicate_label_iri}
    assert counted.result.rows == (("2",),)
    assert listed.plan["constraints"] == counted.plan["constraints"] == [{
        "referent": "membership", "field": "membershipInterval", "operator": "on", "value": point,
    }]
    assert listed.sparql == counted.sparql
    assert "evaluated inclusively for 1994-06-14" in counted.diagnostic


def test_date_qualified_count_fails_closed_when_a_matching_membership_interval_is_missing():
    fixture = MemberRelationshipFixture()
    missing_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Missing-Interval"
    fixture._add_member(missing_iri, "Missing Interval Member", "Missing-Interval", {31: "Dublin Central"})
    outcome, _ = _run(
        fixture,
        "How many Members represented Dublin Central in the 31st Dáil on 14 June 1994?",
        _member_count_draft(date_point="1994-06-14"),
    )

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "has no mapped date-range/start" in outcome.diagnostic


@pytest.mark.parametrize("question", [
    "How many TDs were elected for Dublin Central in the 31st Dáil?",
    "How many seats were represented by Dublin Central in the 31st Dáil?",
])
def test_election_event_or_seat_allocation_counts_are_never_substituted_by_member_counts(question):
    fixture = MemberRelationshipFixture()
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        semantic_plan_generator_factory=lambda: FixedPlanGenerator(_member_count_draft()),
    )

    assert outcome.status == "unsupported_request"
    assert outcome.result is None
    assert fixture.queries == []


def test_date_qualified_selection_fails_closed_on_conflicting_membership_intervals():
    fixture = MemberRelationshipFixture()
    _add_membership_interval(fixture, MEMBER_ALICE, "Aoife-Byrne", 31,
                             "1990-01-01T00:00:00", "1994-06-14T23:59:59")
    _add_membership_interval(fixture, MEMBER_ALICE, "Aoife-Byrne", 31,
                             "1994-06-15T00:00:00", None, extra_key="conflicting-dates")
    list_draft = _representation_draft()
    list_draft["constraints"] = [{
        "referent": "membership", "field": "membershipInterval", "operator": "on",
        "value": "1994-06-14",
    }]
    outcome, _ = _run(
        fixture, "Which Members represented Dublin Central in the 31st Dáil on 14 June 1994?",
        list_draft,
    )

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "missing or conflicting date-range evidence" in outcome.diagnostic


def test_empty_date_qualified_count_is_qualified_as_recorded_zero_not_a_complete_negative():
    fixture = MemberRelationshipFixture()
    _add_membership_interval(fixture, MEMBER_ALICE, "Aoife-Byrne", 31,
                             "1990-01-01T00:00:00", "1994-06-14T23:59:59")
    point = "1995-01-01"
    outcome, _ = _run(
        fixture,
        "How many Members represented Dublin Central in the 31st Dáil on 1 January 1995?",
        _member_count_draft(date_point=point),
    )

    assert outcome.status == "success"
    assert outcome.result.rows == (("0",),)
    assert "not proof that no Member served" in outcome.diagnostic
    assert "historical source completeness is not certified" in outcome.diagnostic


def _bertie_latest_term_fixture(*, latest_representation: bool = True, tied_start: bool = False):
    fixture = MemberRelationshipFixture()
    houses = fixture.dataset.graph(URIRef(HOUSE_GRAPH))
    for ordinal in (29, 30):
        term_iri = f"https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/{ordinal}"
        fixture.terms[ordinal] = term_iri
        term = URIRef(term_iri)
        houses.add((term, RDF.type, URIRef(AGENTS + "DailTerm")))
        houses.add((term, URIRef(AGENTS + "termNo"), Literal(ordinal, datatype=XSD.integer)))
        houses.add((term, URIRef(SKOS + "prefLabel"), Literal(f"{_ordinal(ordinal)} Dáil", lang="en")))
        fixture._add_constituency("Dublin Central", ordinal, f"Dublin-Central-{ordinal}")
    _add_term_chronology(fixture, 29, "2002-06-06T00:00:00", "2007-05-23T00:00:00")
    _add_term_chronology(fixture, 30, "2007-06-14T00:00:00", "2011-02-01T00:00:00")
    if tied_start:
        houses.remove((URIRef(fixture.terms[30] + "#term-period"), URIRef(DCAT + "startDate"), None))
        houses.add((URIRef(fixture.terms[30] + "#term-period"), URIRef(DCAT + "startDate"),
                    Literal("2002-06-06T00:00:00", datatype=XSD.dateTime)))
    bertie = "https://data.oireachtas.ie/ie/oireachtas/member/id/Bertie-Ahern"
    representations = {29: "Dublin Central"}
    if latest_representation:
        representations[30] = "Dublin Central"
    fixture._add_member(bertie, "Bertie Ahern", "Bertie-Ahern", representations)
    if not latest_representation:
        graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Bertie-Ahern"))
        bertie_ref = URIRef(bertie)
        latest_membership = URIRef(bertie + "#dail-membership-30")
        graph.add((bertie_ref, URIRef(MEMBERS + "hasMembersMembership"), latest_membership))
        graph.add((latest_membership, RDF.type, URIRef(MEMBERS + "OireachtasMembership")))
        graph.add((latest_membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
        graph.add((latest_membership, URIRef(MEMBERS + "inHouseTerm"), URIRef(fixture.terms[30])))
    return fixture, bertie


def _latest_recorded_draft() -> dict:
    return {
        "version": 2,
        "supported": True,
        "family": "constituency_representation",
        "unsupportedReason": None,
        "intent": "Return the named Member's latest recorded Dáil term and its constituency.",
        "referents": {
            "member": {"type": "Member", "mention": "Bertie Ahern"},
            "membership": {"type": "DailMembership", "mention": None},
            "term": {"type": "DailTerm", "mention": None, "selector": "latestRecorded"},
            "constituency": {"type": "DailConstituency", "mention": None},
        },
        "relations": [
            {"id": "member-membership", "fact": "member_has_membership", "from": "member", "to": "membership"},
            {"id": "membership-term", "fact": "membership_in_term", "from": "membership", "to": "term"},
            {"id": "membership-constituency", "fact": "membership_represents", "from": "membership", "to": "constituency"},
            {"id": "constituency-term", "fact": "constituency_in_term", "from": "constituency", "to": "term"},
        ],
        "constraints": [],
        "answer": {
            "kind": "entities", "referent": "constituency", "distinctBy": "identity",
            "display": ["label"], "details": [{"referent": "term", "display": ["label"]}],
            "preserveEvidence": True,
        },
    }


def test_semantic_latest_recorded_term_and_constituency_selection_runs_through_integrated_ask(monkeypatch):
    from poc.nlq import app as app_module

    fixture, bertie = _bertie_latest_term_fixture()
    question = "What was Bertie Ahern's latest recorded Dáil term and constituency?"
    generator = FixedPlanGenerator(_latest_recorded_draft())
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert "Bertie Ahern" in response.text and "Dublin Central" in response.text
    assert "30th Dáil" in response.text and "2007-06-14" in response.text
    assert bertie in response.text
    assert generator.calls == [question]
    assert generator.closed


def test_career_wide_constituency_lookup_remains_available_without_a_selected_term():
    fixture, _bertie = _bertie_latest_term_fixture()
    outcome = execute_question(
        "What constituencies did Bertie Ahern represent?",
        as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )

    assert outcome.status == "success", outcome.diagnostic
    assert {row[1] for row in outcome.result.rows} == {"Dublin Central"}
    assert {row[2] for row in outcome.result.rows} == {"29th Dáil", "30th Dáil"}
    assert outcome.plan["referents"]["term"] == {"type": "DailTerm"}


def test_latest_recorded_member_term_uses_membership_paths_and_house_dates_then_projects_constituency(monkeypatch):
    from poc.nlq import app as app_module

    fixture, bertie = _bertie_latest_term_fixture()
    question = "Which constituency did Bertie Ahern represent in his latest recorded Dáil term?"
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post(
        "/ask", data={"question": question, "mode": "phase2"},
    )
    outcome = execute_question(question, as_of=AS_OF, fuseki=fixture,
                               supported_predicates=supported_predicates(ROOT / "ontology"))

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert "Bertie Ahern" in response.text and "Dublin Central" in response.text
    assert "30th Dáil" in response.text and "2007-06-14" in response.text
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.rows[0][:4] == ("Bertie Ahern", "Dublin Central", "30th Dáil", "2007-06-14")
    assert outcome.plan["referents"]["term"]["selector"] == {"kind": "latestRecorded"}
    assert outcome.plan["referents"]["term"]["iri"] == fixture.terms[30]
    assert bertie in outcome.sparql
    assert "VALUES ?term" in outcome.sparql
    assert any("members:hasMembersMembership" in query and "members:inHouseTerm" in query
               for query in fixture.queries)


@pytest.mark.parametrize("question", [
    "What constituency did Bertie Ahern represent in his last term in the Dáil?",
    "Which constituency did Bertie Ahern represent in his latest recorded Dáil term?",
    "Which constituency did Bertie Ahern represent in his most recent Dáil term?",
])
def test_latest_recorded_term_scope_accepts_last_and_existing_latest_synonyms(question):
    fixture, _bertie = _bertie_latest_term_fixture()
    outcome, _generator = _run(fixture, question, _latest_recorded_draft())

    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.rows[0][1:3] == ("Dublin Central", "30th Dáil")
    assert outcome.plan["referents"]["term"]["selector"] == {"kind": "latestRecorded"}


def test_last_term_request_cannot_be_converted_to_career_wide_representation():
    fixture, _bertie = _bertie_latest_term_fixture()
    draft = _latest_recorded_draft()
    draft["referents"]["term"].pop("selector")
    question = "What constituency did Bertie Ahern represent in his last term in the Dáil?"

    outcome, _generator = _run(fixture, question, draft)

    assert outcome.status == "validation_failure"
    assert outcome.result is None and outcome.sparql is None
    assert fixture.queries == []


def test_latest_recorded_term_does_not_fall_back_when_newest_membership_lacks_constituency_evidence():
    fixture, _bertie = _bertie_latest_term_fixture(latest_representation=False)
    outcome = execute_question(
        "Which constituency did Bertie Ahern represent in his latest recorded Dáil term?",
        as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "No matching representation evidence" in outcome.diagnostic


def test_latest_recorded_term_tied_house_start_dates_fail_closed():
    fixture, _bertie = _bertie_latest_term_fixture(tied_start=True)
    question = "Which constituency did Bertie Ahern represent in his latest recorded Dáil term?"
    draft = {
        "version": 2, "supported": True, "family": "constituency_representation",
        "unsupportedReason": None, "intent": "Find the latest recorded Dáil constituency.",
        "referents": {"member": {"type": "Member", "mention": "Bertie Ahern"},
                      "membership": {"type": "DailMembership", "mention": None},
                      "term": {"type": "DailTerm", "mention": None, "selector": "latestRecorded"},
                      "constituency": {"type": "DailConstituency", "mention": None}},
        "relations": [{"id": fact, "fact": fact, "from": source, "to": target}
                      for fact, (source, target) in {
                          "member_has_membership": ("member", "membership"),
                          "membership_in_term": ("membership", "term"),
                          "membership_represents": ("membership", "constituency"),
                          "constituency_in_term": ("constituency", "term"),
                      }.items()],
        "constraints": [],
        "answer": {"kind": "entities", "referent": "constituency", "distinctBy": "identity",
                   "display": ["label"], "details": [{"referent": "term", "display": ["label"]}],
                   "preserveEvidence": True},
    }
    outcome, _ = _run(fixture, question, draft)

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "tied House-owned start dates" in outcome.diagnostic


def test_latest_recorded_term_missing_house_date_fails_closed_instead_of_using_labels_or_ordinal_order():
    fixture, _bertie = _bertie_latest_term_fixture()
    houses = fixture.dataset.graph(URIRef(HOUSE_GRAPH))
    latest_period = URIRef(fixture.terms[30] + "#term-period")
    houses.remove((URIRef(fixture.terms[30]), URIRef(DCT + "temporal"), latest_period))
    question = "Which constituency did Bertie Ahern represent in his latest recorded Dáil term?"
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "missing House-owned chronology evidence" in outcome.diagnostic


def test_integrated_ask_paginates_complete_member_results_over_100(monkeypatch):
    from poc.nlq import app as app_module

    fixture = MemberRelationshipFixture(extra_shared_members=125)
    generator = FixedPlanGenerator(_intersection_draft())
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": QUESTION_TERMS, "mode": "phase2"})

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert "Complete matching results were retrieved in 2 bounded pages" in response.text
    assert "&#34;pageSize&#34;: 100" in response.text
    assert "&#34;offsets&#34;" in response.text
    assert "Large Result Member 000" in response.text
    assert "Large Result Member 124" in response.text
    assert generator.calls == [QUESTION_TERMS]
    assert generator.closed
    assert len(fixture.queries) == 4  # two term resolutions and two answer pages
    first_page, second_page = fixture.queries[-2:]
    assert "LIMIT 100 OFFSET 0" in first_page
    assert "LIMIT 100 OFFSET 100" in second_page
    assert "SERVICE" not in first_page.upper()
    assert "FROM NAMED" not in second_page.upper()


def test_resolved_constituency_identity_excludes_other_constituencies_in_the_same_term():
    fixture = MemberRelationshipFixture()
    outcome, _generator = _run(fixture, QUESTION_REPRESENTATION, _representation_draft())

    assert outcome.status == "success"
    assert outcome.result is not None
    assert outcome.result.columns == ("Member", "Member identity")
    assert set(outcome.result.rows) == {("Aoife Byrne", MEMBER_ALICE)}
    selected_constituency = fixture.constituencies[("Dublin-Central-31", 31)]
    assert f"VALUES ?constituency {{ <{selected_constituency}> }}" in outcome.sparql
    assert MEMBER_BOB not in {row[1] for row in outcome.result.rows}


@pytest.mark.parametrize(("question", "draft"), [
    (QUESTION_TERMS, _intersection_draft(first=32, second=32)),
    (QUESTION_TERMS, _intersection_draft(first=31, second=33)),
    (QUESTION_REPRESENTATION, _representation_draft(constituency=None)),
])
def test_omitted_or_hallucinated_essential_constraint_fails_before_any_local_query(question, draft):
    fixture = MemberRelationshipFixture()
    outcome, _generator = _run(fixture, question, draft)

    assert outcome.status == "validation_failure"
    assert outcome.sparql is None
    assert not fixture.queries


def test_disconnected_or_extra_relationships_cannot_be_compiled():
    fixture = MemberRelationshipFixture()
    disconnected = _representation_draft()
    disconnected["relations"][-1]["to"] = "membership"
    outcome, _generator = _run(fixture, QUESTION_REPRESENTATION, disconnected)
    assert outcome.status == "validation_failure"
    assert not fixture.queries

    unsupported = _intersection_draft()
    unsupported["relations"].append({
        "id": "unsupported-party-filter", "fact": "episode_in_parliamentary_party",
        "from": "membership_a", "to": "term_a",
    })
    outcome, _generator = _run(fixture, QUESTION_TERMS, unsupported)
    assert outcome.status == "unsupported_request"
    assert not fixture.queries


def test_unsupported_semantics_are_not_simplified_to_a_member_query():
    fixture = MemberRelationshipFixture()
    unsupported = {
        "version": 2,
        "supported": False,
        "family": None,
        "unsupportedReason": "The requested party and date filters are outside this composition.",
        "intent": "The request contains unsupported filters.",
        "referents": None,
        "relations": [],
        "constraints": [],
        "answer": None,
    }
    assert Draft202012Validator(load_composable_draft_schema()).is_valid(unsupported)
    outcome, _generator = _run(
        fixture,
        "Which Members represented Dublin Central in the 31st Dáil while in a particular party?",
        unsupported,
    )
    assert outcome.status == "unsupported_request"
    assert outcome.plan is None
    assert outcome.sparql is None
    assert not fixture.queries


@pytest.mark.parametrize(("fixture", "question", "draft", "status"), [
    (MemberRelationshipFixture(duplicate_term_31=True), QUESTION_REPRESENTATION, _representation_draft(), "ambiguous"),
    (MemberRelationshipFixture(duplicate_constituency_31=True), QUESTION_REPRESENTATION, _representation_draft(), "ambiguous"),
    (MemberRelationshipFixture(), "Who represented Dublin Central during the 34th Dáil?", _representation_draft(34), "source_data_unavailable"),
])
def test_ambiguous_or_missing_selected_identities_never_run_an_answer_query(fixture, question, draft, status):
    outcome, _generator = _run(fixture, question, draft)
    assert outcome.status == status
    assert outcome.sparql is None
    assert len(fixture.queries) < 3


def test_answer_compiler_revalidates_the_complete_relation_graph():
    fixture = MemberRelationshipFixture()
    outcome, _generator = _run(fixture, QUESTION_REPRESENTATION, _representation_draft())
    assert outcome.status == "success"
    broken = copy.deepcopy(outcome.plan)
    broken["relations"] = [item for item in broken["relations"] if item["fact"] != "constituency_in_term"]
    with pytest.raises(PlanError):
        validate_plan(broken)
    with pytest.raises(PlanError):
        compile_member_relationship_composition_query(
            broken, supported_predicates=supported_predicates(ROOT / "ontology"),
        )


def test_member_relationship_page_offsets_obey_the_existing_safety_contract():
    fixture = MemberRelationshipFixture()
    outcome, _generator = _run(fixture, QUESTION_TERMS, _intersection_draft())
    assert outcome.status == "success"
    assert f"OFFSET {MAX_RESULT_OFFSET}" in compile_member_relationship_composition_query(
        outcome.plan,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        offset=MAX_RESULT_OFFSET,
    )
    with pytest.raises(PlanError, match="page offset"):
        compile_member_relationship_composition_query(
            outcome.plan,
            supported_predicates=supported_predicates(ROOT / "ontology"),
            offset=MAX_RESULT_OFFSET + 1,
        )


def test_member_relationship_pagination_limit_fails_closed_without_partial_answer(monkeypatch):
    import poc.nlq.composable_plan as plan_module

    monkeypatch.setattr(plan_module, "MAX_RESULT_OFFSET", 0)
    fixture = MemberRelationshipFixture(extra_shared_members=125)
    outcome, _generator = _run(fixture, QUESTION_TERMS, _intersection_draft())

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "no partial answer was returned" in outcome.diagnostic
    assert len(fixture.queries) == 3  # resolutions and first page only


def _add_large_constituency_occurrence_members(fixture: MemberRelationshipFixture, ordinal: int) -> int:
    occurrence = URIRef(fixture.constituencies[(f"Dublin-Central-{ordinal}", ordinal)])
    count = 0
    for graph in fixture.dataset.graphs():
        for member, membership in graph.subject_objects(URIRef(MEMBERS + "hasMembersMembership")):
            member_name = str(member).rsplit("/", 1)[-1]
            if not member_name.startswith("Large-Result-Member-"):
                continue
            if (membership, URIRef(MEMBERS + "inHouseTerm"), URIRef(fixture.terms[ordinal])) in graph:
                graph.add((membership, URIRef(MEMBERS + "isRepresentativeFrom"), occurrence))
                count += 1
    return count


def test_distinct_member_count_retrieves_all_bounded_pages_like_the_list_projection():
    fixture = MemberRelationshipFixture(extra_shared_members=MAX_RESULT_ROWS + 5)
    selected_members = _add_large_constituency_occurrence_members(fixture, 32)
    question = "How many Members represented Dublin Central in the 32nd Dáil?"
    listed, _ = _run(fixture, "Who represented Dublin Central during the 32nd Dáil?",
                     _representation_draft(32))
    counted, _ = _run(fixture, question, _member_count_draft(32))

    assert listed.status == counted.status == "success"
    assert len(listed.result.rows) == selected_members + 2
    assert counted.result.rows == ((str(len(listed.result.rows)),),)
    assert "Complete matching results were retrieved in 2 bounded pages" in listed.diagnostic
    assert "Complete matching results were retrieved in 2 bounded pages" in counted.diagnostic
    assert listed.sparql == counted.sparql


def test_distinct_member_count_never_returns_a_number_from_a_truncated_page(monkeypatch):
    import poc.nlq.composable_plan as plan_module

    monkeypatch.setattr(plan_module, "MAX_RESULT_OFFSET", 0)
    fixture = MemberRelationshipFixture(extra_shared_members=MAX_RESULT_ROWS + 5)
    _add_large_constituency_occurrence_members(fixture, 32)
    outcome, _ = _run(
        fixture, "How many Members represented Dublin Central in the 32nd Dáil?",
        _member_count_draft(32),
    )

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "no partial answer was returned" in outcome.diagnostic


def _add_q24_term_chronology(fixture: MemberRelationshipFixture, *, missing: int | None = None) -> None:
    chronology = {
        31: ("2011-03-09T00:00:00", "2016-02-03T00:00:00"),
        32: ("2016-04-06T00:00:00", "2020-01-14T00:00:00"),
        33: ("2020-02-08T00:00:00", None),
    }
    for ordinal, (start, end) in chronology.items():
        if ordinal != missing:
            _add_term_chronology(fixture, ordinal, start, end)


Q24_PREVIOUS = "How many other TDs were in the same constituency as Aoife Byrne during the last Dáil?"
Q24_NUMBERED = "Who were the other TDs sharing the same constituency as Eimear Walsh in the 32nd Dáil?"
Q24_NUMBERED_AOIFE = "Which other TDs shared the same constituency as Aoife Byrne in the 32nd Dáil?"
Q24_NUMBERED_AOIFE_COUNT = "How many other TDs shared the same constituency as Aoife Byrne in the 32nd Dáil?"


def test_anchored_shared_constituency_draft_preserves_previous_and_numbered_term_scopes():
    previous, unsupported = validate_composable_plan_draft(
        _anchored_shared_constituency_draft(previous=True, count=True), question=Q24_PREVIOUS,
    )
    assert unsupported is None
    previous_plan = complete_v2_plan(previous, as_of=AS_OF)
    assert previous_plan["referents"]["term"]["selector"] == {"kind": "previousTerm", "house": "Dail"}
    assert previous_plan["constraints"] == []
    assert len(previous_plan["relations"]) == 7

    numbered, unsupported = validate_composable_plan_draft(
        _anchored_shared_constituency_draft(anchor="Eimear Walsh", ordinal=32), question=Q24_NUMBERED,
    )
    assert unsupported is None
    assert numbered["referents"]["term"]["selector"] == {"kind": "termNumber", "number": 32}


def test_anchored_shared_constituency_previous_term_count_and_list_share_one_complete_selection():
    count_fixture = MemberRelationshipFixture()
    list_fixture = MemberRelationshipFixture()
    _add_q24_term_chronology(count_fixture)
    _add_q24_term_chronology(list_fixture)

    counted, _ = _run(count_fixture, Q24_PREVIOUS, _anchored_shared_constituency_draft(previous=True, count=True))
    listed, _ = _run(
        list_fixture,
        "Which other Members shared a constituency with Aoife Byrne during the previous Dáil?",
        _anchored_shared_constituency_draft(previous=True),
    )

    assert counted.status == listed.status == "success"
    assert counted.result.rows == (("1",),)
    assert listed.result.rows == (("Eimear Walsh", MEMBER_CARA),)
    assert counted.sparql == listed.sparql
    assert counted.plan["referents"]["term"]["iri"] == list_fixture.terms[32]
    assert counted.plan["referents"]["term"]["asOfEvidence"] == AS_OF.isoformat()
    assert counted.plan["referents"]["constituency"]["iri"] == count_fixture.constituencies[("Dublin-Central-32", 32)]
    assert "FILTER(?member != ?anchorMember)" in counted.sparql
    assert "FILTER(?anchorMembership != ?membership)" in counted.sparql
    assert "term-wide recorded co-membership, not evidence of simultaneous service" in counted.diagnostic
    assert "latestRecorded" not in counted.sparql


def test_anchored_shared_constituency_numbered_term_accepts_a_different_anchor_and_returns_other_members():
    fixture = MemberRelationshipFixture()
    outcome, _ = _run(fixture, Q24_NUMBERED, _anchored_shared_constituency_draft(anchor="Eimear Walsh", ordinal=32))

    assert outcome.status == "success"
    assert outcome.result.rows == (("Aoife Byrne", MEMBER_ALICE),)
    assert outcome.plan["referents"]["anchorMember"]["iri"] == MEMBER_CARA
    assert outcome.plan["referents"]["term"]["iri"] == fixture.terms[32]
    assert "agents:termNo \"32\"^^xsd:integer" in outcome.sparql


@pytest.mark.parametrize(("question", "draft"), [
    (
        "How many other Fine Gael TDs shared the same constituency as Aoife Byrne in the 32nd Dáil?",
        _anchored_shared_constituency_draft(ordinal=32, count=True),
    ),
    (
        "Which other TDs were in the same constituency as Aoife Byrne at the same time in the 32nd Dáil?",
        _anchored_shared_constituency_draft(ordinal=32),
    ),
    (
        "Who were the other TDs in the same constituency as Aoife Byrne on 14 June 1994?",
        _anchored_shared_constituency_draft(ordinal=32),
    ),
    (
        "Who were the other TDs in the same constituency as Aoife Byrne during the 32nd Dáil when she was elected?",
        _anchored_shared_constituency_draft(ordinal=32),
    ),
    (
        "Who were the other TDs in the same constituency as Aoife Byrne during the 32nd term?",
        _anchored_shared_constituency_draft(ordinal=32),
    ),
])
def test_anchored_shared_constituency_does_not_drop_party_simultaneity_or_date_filters(question, draft):
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(draft, question=question)


@pytest.mark.parametrize("failure", ["missing", "tied", "conflicting", "overlap"])
def test_previous_term_anchored_composition_fails_closed_on_incomplete_or_tied_global_chronology(failure):
    fixture = MemberRelationshipFixture()
    if failure == "missing":
        _add_q24_term_chronology(fixture, missing=31)
    elif failure == "tied":
        _add_term_chronology(fixture, 31, "2016-04-06T00:00:00", "2019-01-01T00:00:00")
        _add_term_chronology(fixture, 32, "2016-04-06T00:00:00", "2020-01-14T00:00:00")
        _add_term_chronology(fixture, 33, "2020-02-08T00:00:00", None)
    elif failure == "conflicting":
        _add_q24_term_chronology(fixture)
        houses = fixture.dataset.graph(URIRef(HOUSE_GRAPH))
        term_32 = URIRef(fixture.terms[32])
        conflicting_period = URIRef(f"{fixture.terms[32]}#conflicting-term-period")
        houses.add((term_32, URIRef(DCT + "temporal"), conflicting_period))
        houses.add((conflicting_period, URIRef(DCAT + "startDate"), Literal("2016-04-07T00:00:00", datatype=XSD.dateTime)))
        houses.add((conflicting_period, URIRef(DCAT + "endDate"), Literal("2020-01-14T00:00:00", datatype=XSD.dateTime)))
    else:
        _add_term_chronology(fixture, 31, "2011-03-09T00:00:00", "2016-05-06T00:00:00")
        _add_term_chronology(fixture, 32, "2016-04-06T00:00:00", "2020-01-14T00:00:00")
        _add_term_chronology(fixture, 33, "2020-02-08T00:00:00", "2024-11-08T00:00:00")

    outcome, _ = _run(fixture, Q24_PREVIOUS, _anchored_shared_constituency_draft(previous=True, count=True))

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert not any("FILTER(?member != ?anchorMember)" in query for query in fixture.queries)


def test_anchored_shared_constituency_fails_closed_on_ambiguous_anchor_or_representation():
    ambiguous_anchor = MemberRelationshipFixture()
    duplicate_member = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aoife-Byrne-duplicate"
    ambiguous_anchor._add_member(duplicate_member, "Aoife Byrne", "Aoife-Byrne-duplicate", {32: "Dublin Central"})
    anchor_outcome, _ = _run(
        ambiguous_anchor, Q24_NUMBERED_AOIFE, _anchored_shared_constituency_draft(ordinal=32),
    )
    assert anchor_outcome.status == "ambiguous"
    assert not any("FILTER(?member != ?anchorMember)" in query for query in ambiguous_anchor.queries)

    ambiguous_representation = MemberRelationshipFixture()
    other = "https://data.oireachtas.ie/ie/oireachtas/constituency/dail/Dublin-South-32"
    constituency_graph = ambiguous_representation.dataset.graph(URIRef(CONSTITUENCY_GRAPH))
    other_ref = URIRef(other)
    constituency_graph.add((other_ref, RDF.type, URIRef(MEMBERS + "DailConstituency")))
    constituency_graph.add((other_ref, URIRef(SKOS + "prefLabel"), Literal("Dublin South", lang="en")))
    constituency_graph.add((other_ref, URIRef(MEMBERS + "constituencyInHouseTerm"), URIRef(ambiguous_representation.terms[32])))
    anchor_graph = ambiguous_representation.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Aoife-Byrne"))
    anchor_membership = URIRef(f"{MEMBER_ALICE}#dail-membership-32")
    anchor_graph.add((anchor_membership, URIRef(MEMBERS + "isRepresentativeFrom"), other_ref))
    representation_outcome, _ = _run(
        ambiguous_representation, Q24_NUMBERED_AOIFE, _anchored_shared_constituency_draft(ordinal=32),
    )
    assert representation_outcome.status == "ambiguous"
    assert representation_outcome.result is None
    assert not any("FILTER(?member != ?anchorMember)" in query for query in ambiguous_representation.queries)


def test_anchored_shared_constituency_fails_closed_when_an_anchor_membership_has_no_representation():
    fixture = MemberRelationshipFixture()
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Aoife-Byrne"))
    missing_representation = URIRef(f"{MEMBER_ALICE}#unrepresented-dail-membership-32")
    graph.add((URIRef(MEMBER_ALICE), URIRef(MEMBERS + "hasMembersMembership"), missing_representation))
    graph.add((missing_representation, RDF.type, URIRef(MEMBERS + "DailMembership")))
    graph.add((missing_representation, URIRef(MEMBERS + "inHouseTerm"), URIRef(fixture.terms[32])))

    outcome, _ = _run(fixture, Q24_NUMBERED_AOIFE, _anchored_shared_constituency_draft(ordinal=32))

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert not any("FILTER(?member != ?anchorMember)" in query for query in fixture.queries)


def test_anchored_shared_constituency_fails_closed_when_numbered_term_identity_is_ambiguous():
    fixture = MemberRelationshipFixture()
    houses = fixture.dataset.graph(URIRef(HOUSE_GRAPH))
    duplicate = URIRef("https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/32-duplicate")
    houses.add((duplicate, RDF.type, URIRef(AGENTS + "DailTerm")))
    houses.add((duplicate, URIRef(AGENTS + "termNo"), Literal(32, datatype=XSD.integer)))

    outcome, _ = _run(fixture, Q24_NUMBERED_AOIFE, _anchored_shared_constituency_draft(ordinal=32))

    assert outcome.status == "ambiguous"
    assert outcome.result is None
    assert not any("FILTER(?member != ?anchorMember)" in query for query in fixture.queries)


def test_anchored_shared_constituency_pagination_limit_never_returns_a_partial_count(monkeypatch):
    import re
    import poc.nlq.composable_plan as plan_module

    monkeypatch.setattr(plan_module, "MAX_RESULT_OFFSET", 0)

    class OneFullPageFixture(MemberRelationshipFixture):
        def query(self, query: str) -> QueryResult:
            if "FILTER(?member != ?anchorMember)" in query:
                self.queries.append(query)
                rows = tuple(
                    (f"https://data.oireachtas.ie/ie/oireachtas/member/id/Member-{index:03d}", f"Member {index:03d}@en")
                    for index in range(MAX_RESULT_ROWS)
                )
                return QueryResult("select", ("member", "memberName"), rows)
            return super().query(query)

    fixture = OneFullPageFixture()
    outcome, _ = _run(
        fixture, Q24_NUMBERED_AOIFE_COUNT, _anchored_shared_constituency_draft(ordinal=32, count=True),
    )

    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None
    assert "no partial answer was returned" in outcome.diagnostic
    assert sum("FILTER(?member != ?anchorMember)" in query for query in fixture.queries) == 1


def test_anchored_shared_constituency_list_and_count_retrieve_all_bounded_pages():
    count_fixture = MemberRelationshipFixture(extra_shared_members=MAX_RESULT_ROWS + 5)
    list_fixture = MemberRelationshipFixture(extra_shared_members=MAX_RESULT_ROWS + 5)
    _add_q24_term_chronology(count_fixture)
    _add_q24_term_chronology(list_fixture)
    count_extra = _add_large_constituency_occurrence_members(count_fixture, 32)
    list_extra = _add_large_constituency_occurrence_members(list_fixture, 32)

    counted, _ = _run(
        count_fixture, Q24_PREVIOUS, _anchored_shared_constituency_draft(previous=True, count=True),
    )
    listed, _ = _run(
        list_fixture,
        "Who were other Members in the same constituency as Aoife Byrne in the last Dáil?",
        _anchored_shared_constituency_draft(previous=True),
    )

    expected = count_extra + 1  # every large member plus Eimear Walsh, excluding the anchor
    assert counted.status == listed.status == "success"
    assert len(listed.result.rows) == expected
    assert counted.result.rows == ((str(expected),),)
    assert counted.sparql == listed.sparql
    assert "Complete matching results were retrieved in 2 bounded pages" in counted.diagnostic
    assert "Complete matching results were retrieved in 2 bounded pages" in listed.diagnostic
    assert count_extra == list_extra
    answer_queries = [query for query in count_fixture.queries if "FILTER(?member != ?anchorMember)" in query]
    assert len(answer_queries) == 2
    assert "LIMIT 100 OFFSET 0" in answer_queries[0]
    assert "LIMIT 100 OFFSET 100" in answer_queries[1]
