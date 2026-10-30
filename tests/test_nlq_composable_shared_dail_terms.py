"""Synthetic acceptance for semantic composition of two Member term histories."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, XSD

from poc.nlq.composable_plan import (
    PlanError,
    compile_shared_dail_terms_answer_query,
    execute_question,
    validate_plan,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.structured_planner import ResponsesPlanGenerator
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
MEMBER_A = "https://data.oireachtas.ie/ie/oireachtas/member/id/Micheal-Martin"
MEMBER_B = "https://data.oireachtas.ie/ie/oireachtas/member/id/Mary-Lou-McDonald"
QUESTION = "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?"


def _binding(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Literal):
        if value.language:
            return f"{value}@{value.language}"
        if value.datatype:
            return f"{value}^^<{value.datatype}>"
    return str(value)


class SharedDailTermsFixture:
    def __init__(
        self,
        *,
        missing_b_memberships: bool = False,
        duplicate_members: bool = False,
        member_b_aliases_member_a: bool = False,
    ):
        self.dataset = Dataset()
        self.queries: list[str] = []
        self._members: dict[str, tuple[str, str]] = {}
        for ordinal in (31, 32, 33, 34):
            term = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/{ordinal}")
            graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
            graph.add((term, RDF.type, URIRef(AGENTS + "DailTerm")))
            graph.add((term, URIRef(SKOS + "prefLabel"), Literal(f"{ordinal}{_ordinal_suffix(ordinal)} Dáil", lang="en")))
            graph.add((term, URIRef(AGENTS + "termNo"), Literal(ordinal, datatype=XSD.integer)))

        self.add_member(MEMBER_A, "Micheál Martin", "Micheal-Martin", (31, 32, 33))
        if member_b_aliases_member_a:
            self.add_member(MEMBER_A, "Michael Martin", "Micheal-Martin", ())
            self.add_member(MEMBER_A, "Mary Lou McDonald", "Micheal-Martin", ())
        else:
            self.add_member(
                MEMBER_B, "Mary Lou McDonald", "Mary-Lou-McDonald",
                () if missing_b_memberships else (32, 33, 34),
            )
        if duplicate_members:
            self.add_member(
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Micheal-Martin-duplicate",
                "Micheál Martin", "Micheal-Martin-duplicate", (32, 33),
            )
            self.add_member(
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Mary-Lou-McDonald-duplicate",
                "Mary Lou McDonald", "Mary-Lou-McDonald-duplicate", (32, 33),
            )

    def add_member(
        self,
        owner_member_iri: str,
        label: str,
        graph_key: str,
        ordinals: tuple[int, ...],
    ) -> None:
        resource = URIRef(owner_member_iri)
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{graph_key}"))
        graph.add((resource, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((resource, URIRef(FOAF + "name"), Literal(label)))
        self._members[label] = (str(resource), graph_key)
        for ordinal in ordinals:
            term = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/houseTerm/dail/{ordinal}")
            membership = URIRef(f"{resource}#dail-membership-{ordinal}")
            graph.add((resource, URIRef(MEMBERS + "hasMembersMembership"), membership))
            graph.add((membership, RDF.type, URIRef(MEMBERS + "OireachtasMembership")))
            graph.add((membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
            graph.add((membership, URIRef(MEMBERS + "inHouseTerm"), term))

    def readiness(self):
        sources = ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")
        return FusekiReadiness("ready", True, tuple((name, True) for name in sources), "synthetic shared-term fixture")

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


def _ordinal_suffix(value: int) -> str:
    if value % 100 in (11, 12, 13):
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")


def _draft(member_a="Micheál Martin", member_b="Mary Lou McDonald"):
    return {
        "version": 2,
        "supported": True,
        "family": "shared_dail_terms",
        "unsupportedReason": None,
        "intent": "Find Dáil term identities both Members served in.",
        "referents": {
            "member_a": {"type": "Member", "mention": member_a},
            "membership_a": {"type": "DailMembership", "mention": None},
            "member_b": {"type": "Member", "mention": member_b},
            "membership_b": {"type": "DailMembership", "mention": None},
            "shared_term": {"type": "DailTerm", "mention": None},
        },
        "relations": [
            {"id": "a_membership", "fact": "member_has_membership", "from": "member_a", "to": "membership_a"},
            {"id": "a_term", "fact": "membership_in_term", "from": "membership_a", "to": "shared_term"},
            {"id": "b_membership", "fact": "member_has_membership", "from": "member_b", "to": "membership_b"},
            {"id": "b_term", "fact": "membership_in_term", "from": "membership_b", "to": "shared_term"},
        ],
        "answer": {
            "kind": "entities", "referent": "shared_term",
            "distinctBy": "identity", "display": ["label"],
        },
    }


class FixedPlanGenerator:
    def __init__(self, draft=None, error: Exception | None = None, raw_output: str | None = None):
        self.draft = _draft() if draft is None else draft
        self.error = error
        self.raw_output = raw_output
        self.calls: list[str] = []
        self.closed = False

    def generate(self, question: str) -> str:
        self.calls.append(question)
        if self.error:
            raise self.error
        if self.raw_output is not None:
            return self.raw_output
        return json.dumps(self.draft, ensure_ascii=False)

    def close(self):
        self.closed = True


def _run(fixture: SharedDailTermsFixture, question=QUESTION, draft=None, error=None, raw_output=None):
    generator = FixedPlanGenerator(draft=draft, error=error, raw_output=raw_output)
    outcome = execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
        semantic_plan_generator_factory=lambda: generator,
    )
    return outcome, generator


def test_v2_shared_dail_term_contract_and_draft_schema_are_synchronized():
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    plan_schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    draft_schema = json.loads((ROOT / "poc/specs/composable-query-plan-draft.schema.json").read_text())
    Draft202012Validator.check_schema(plan_schema)
    Draft202012Validator.check_schema(draft_schema)
    assert contract["contractVersion"] == "2.11.0"
    assert contract["planVersion"] == plan_schema["properties"]["version"]["const"] == 2
    assert "shared_dail_terms" in plan_schema["properties"]["family"]["enum"]
    assert any(item["id"] == "shared_dail_terms" for item in contract["questionFamilies"])
    assert Draft202012Validator(draft_schema).is_valid(_draft())


def test_existing_responses_transport_uses_the_iri_free_v2_draft_schema_once():
    requests = []

    def response(request: httpx.Request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"status": "completed", "output_text": json.dumps(_draft())})

    generator = ResponsesPlanGenerator(
        "test-key", "https://planner.example/v1", "test-model",
        output_schema=load_composable_draft_schema(),
        schema_name="composable_query_plan_v2_draft",
        instructions=build_composable_planner_instructions(),
        transport=httpx.MockTransport(response),
    )
    try:
        result = generator.generate(QUESTION)
    finally:
        generator.close()

    assert json.loads(result)["version"] == 2
    assert len(requests) == 1
    request = requests[0]
    assert request["text"]["format"]["name"] == "composable_query_plan_v2_draft"
    assert request["text"]["format"]["strict"] is True
    assert request["text"]["format"]["schema"]["properties"]["version"]["const"] == 2
    assert "Never output SPARQL" in request["instructions"]


@pytest.mark.parametrize("question", [
    "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?",
    "Name the Dáil terms common to Micheál Martin and Mary Lou McDonald.",
    "Where do Micheál Martin's and Mary Lou McDonald's recorded Dáil service histories overlap?",
])
def test_unseen_phrasings_compose_two_independent_member_paths_through_the_shared_term(question):
    fixture = SharedDailTermsFixture()
    outcome, generator = _run(fixture, question)

    assert outcome.status == "success"
    assert outcome.result.columns == ("Shared Dáil term",)
    assert set(outcome.result.rows) == {("32nd Dáil",), ("33rd Dáil",)}
    assert outcome.plan["family"] == "shared_dail_terms"
    member_refs = [ref for ref in outcome.plan["referents"].values() if ref["type"] == "Member"]
    assert {ref["iri"] for ref in member_refs} == {MEMBER_A, MEMBER_B}
    assert len(generator.calls) == 1
    assert generator.closed
    assert len(fixture.queries) == 4  # two independent resolutions, source-evidence probe, answer
    answer_query = fixture.queries[-1]
    assert answer_query == outcome.sparql
    assert "SELECT DISTINCT ?term ?termLabel ?termNo" in answer_query
    assert answer_query.count("?term") >= 6
    assert "?membershipA" in answer_query and "?membershipB" in answer_query
    assert "VALUES ?memberA" in answer_query and "VALUES ?memberB" in answer_query
    assert "UNION" not in answer_query and "OPTIONAL" not in answer_query


@pytest.mark.parametrize("broken", [
    "one_member", "missing_membership_edge", "different_term", "extra_constraint", "wrong_answer",
])
def test_incomplete_or_weakened_drafts_fail_before_resolution_or_answer_execution(broken):
    fixture = SharedDailTermsFixture()
    draft = _draft()
    if broken == "one_member":
        draft["referents"].pop("member_b")
        draft["relations"] = [item for item in draft["relations"] if item["from"] != "member_b"]
    elif broken == "missing_membership_edge":
        draft["relations"] = [item for item in draft["relations"] if item["id"] != "b_membership"]
    elif broken == "different_term":
        draft["referents"]["other_term"] = {"type": "DailTerm", "mention": None}
        draft["relations"][-1]["to"] = "other_term"
    elif broken == "extra_constraint":
        draft["constraints"] = []
    elif broken == "wrong_answer":
        draft["answer"]["referent"] = "member_a"

    outcome, _generator = _run(fixture, draft=draft)
    assert outcome.status == "validation_failure"
    assert not fixture.queries
    assert outcome.sparql is None


def test_unsupported_semantics_and_unsupported_relationships_fail_closed():
    fixture = SharedDailTermsFixture()
    unsupported = {
        "version": 2, "supported": False,
        "family": None,
        "unsupportedReason": "Bill voting is not represented by this query capability.",
        "intent": "The requested vote relationship is unavailable.",
        "referents": None, "relations": [], "answer": None,
    }
    assert Draft202012Validator(load_composable_draft_schema()).is_valid(unsupported)
    outcome, _ = _run(fixture, question="Which Bills did these Members vote for?", draft=unsupported)
    assert outcome.status == "unsupported_request"
    assert "voting" in outcome.diagnostic.lower()
    assert not fixture.queries

    bad_relation = _draft()
    bad_relation["relations"][0]["fact"] = "member_votes_for_bill"
    outcome, _ = _run(fixture, draft=bad_relation)
    assert outcome.status == "unsupported_request"
    assert not fixture.queries


def test_ambiguous_members_are_resolved_independently_and_never_compiled():
    fixture = SharedDailTermsFixture(duplicate_members=True)
    outcome, _ = _run(fixture)
    assert outcome.status == "ambiguous"
    assert len(fixture.queries) == 2
    assert outcome.sparql is None
    ambiguous = [
        ref for ref in outcome.plan["referents"].values()
        if ref["type"] == "Member" and ref["resolution"] == "ambiguous"
    ]
    assert len(ambiguous) == 2
    assert all(len(ref["candidates"]) == 2 for ref in ambiguous)


def test_missing_member_or_membership_evidence_is_not_reported_as_an_empty_intersection():
    missing_member_fixture = SharedDailTermsFixture()
    missing_member, _ = _run(
        missing_member_fixture,
        question="Which Dáil terms did Micheál Martin and An Unrecorded Member both serve in?",
        draft=_draft(member_b="An Unrecorded Member"),
    )
    assert missing_member.status == "not_found"
    assert len(missing_member_fixture.queries) == 2
    assert missing_member.sparql is None

    missing_membership_fixture = SharedDailTermsFixture(missing_b_memberships=True)
    missing_membership, _ = _run(missing_membership_fixture)
    assert missing_membership.status == "source_data_unavailable"
    assert "Mary Lou McDonald" in missing_membership.diagnostic
    assert len(missing_membership_fixture.queries) == 3  # no answer query
    assert missing_membership.sparql is not None


def test_two_aliases_resolving_to_one_member_iri_are_not_treated_as_two_people():
    fixture = SharedDailTermsFixture(member_b_aliases_member_a=True)
    draft = _draft(member_b="Michael Martin")
    question = "Which Dáil terms did Micheál Martin and Michael Martin both serve in?"
    outcome, _ = _run(fixture, question, draft=draft)
    assert outcome.status == "identity_collision"
    assert len(fixture.queries) == 2
    assert outcome.sparql is None


def test_planner_failures_are_separate_from_unsupported_semantics():
    fixture = SharedDailTermsFixture()
    outcome, _ = _run(fixture, error=RuntimeError("controlled planner failure"))
    assert outcome.status == "planner_failure"
    assert "planner" in outcome.diagnostic.lower()
    assert not fixture.queries

    malformed = SharedDailTermsFixture()
    outcome, _ = _run(malformed, raw_output="not json")
    assert outcome.status == "planner_failure"
    assert not malformed.queries


def test_final_plan_validator_and_compiler_reject_a_dropped_intersection_edge():
    fixture = SharedDailTermsFixture()
    outcome, _ = _run(fixture)
    assert outcome.status == "success"
    broken = copy.deepcopy(outcome.plan)
    broken["relations"] = [item for item in broken["relations"] if item["id"] != "b_term"]
    with pytest.raises(PlanError):
        validate_plan(broken)
    with pytest.raises(PlanError):
        compile_shared_dail_terms_answer_query(
            broken, supported_predicates=supported_predicates(ROOT / "ontology"),
        )


def test_integrated_ask_route_shows_validated_plan_query_and_result(monkeypatch):
    from poc.nlq import app as app_module

    fixture = SharedDailTermsFixture()
    generator = FixedPlanGenerator()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": QUESTION, "mode": "phase2"})

    assert response.status_code == 200
    assert "Validated composable query plan" in response.text
    assert 'summary>Generated SPARQL' in response.text
    assert "SELECT DISTINCT ?term ?termLabel ?termNo" in response.text
    assert "32nd Dáil" in response.text and "33rd Dáil" in response.text
    assert "same DailTerm RDF identity" in response.text
    assert generator.calls == [QUESTION]


def test_integrated_ask_route_explains_member_ambiguity_without_querying(monkeypatch):
    from poc.nlq import app as app_module

    fixture = SharedDailTermsFixture(duplicate_members=True)
    generator = FixedPlanGenerator()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT,
        semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": QUESTION, "mode": "phase2"})

    assert response.status_code == 200
    assert "Ambiguous entity" in response.text
    assert "none was selected" in response.text
    assert "Possible local matches" in response.text
    assert "Generated SPARQL" not in response.text
    assert len(fixture.queries) == 2
