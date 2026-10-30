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
    build_composable_planner_instructions,
    load_composable_draft_schema,
)


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 28)
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
FOAF = "http://xmlns.com/foaf/0.1/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
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
    def __init__(self, *, duplicate_term_31: bool = False, duplicate_constituency_31: bool = False):
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
        "answer": {"kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"]},
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
        "answer": {"kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"]},
    }


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
    assert contract["contractVersion"] == "2.10.0"
    assert "member_relationship_composition" in plan_schema["properties"]["family"]["enum"]
    assert any(item["id"] == "member_relationship_composition" for item in contract["questionFamilies"])
    validator = Draft202012Validator(draft_schema)
    assert validator.is_valid(_intersection_draft())
    assert validator.is_valid(_representation_draft())
    assert "Never output SPARQL" in build_composable_planner_instructions()


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
