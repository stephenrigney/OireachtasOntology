"""Focused synthetic and source-backed checks for the composable Q09 slice."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from poc.nlq.composable_plan import (
    AmbiguousConstituency,
    PlanError,
    compile_answer_query,
    execute_question,
    plan_question,
    previous_dail_term_query,
    resolve_constituency,
    resolve_previous_dail,
    validate_plan,
)
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates
from poc.nlq.fuseki import FusekiReadiness


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 25)
TERM_33 = "https://data.oireachtas.ie/ie/oireachtas/house/dail/33"
TERM_34 = "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
CONSTITUENCY_33 = "https://data.oireachtas.ie/ie/oireachtas/house/dail/33/constituency/Dublin-Mid-West"


class SyntheticFuseki:
    """Execute generated SPARQL over a tiny RDF dataset with explicit synthetic Q09 facts."""

    def __init__(self):
        self.queries: list[str] = []
        self.dataset = Dataset()
        source_houses = Graph().parse(ROOT / "tests/expected/houses.ttl", format="turtle")
        houses = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
        for triple in source_houses:
            houses.add(triple)
        constituencies = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/constituencies"))
        members_ns = "https://data.oireachtas.ie/ontology/members#"
        constituency = URIRef(CONSTITUENCY_33)
        constituencies.add((constituency, RDF.type, URIRef(members_ns + "Constituencies")))
        constituencies.add((constituency, RDF.type, URIRef(members_ns + "DailConstituency")))
        constituencies.add((constituency, SKOS.prefLabel, Literal("Dublin Mid-West", lang="en")))
        constituencies.add((constituency, URIRef(members_ns + "constituencyInHouseTerm"), URIRef(TERM_33)))
        self._add_member("synthetic-a", "Member A", "episode-a")
        self._add_member("synthetic-b", "Member B", "episode-b1")
        self._add_member("synthetic-b", "Member B", "episode-b2")

    def _add_member(self, code: str, name: str, episode: str):
        members_ns = "https://data.oireachtas.ie/ontology/members#"
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{code}"))
        member = URIRef(f"https://data.oireachtas.ie/member/id/{code}")
        membership = URIRef(f"https://data.oireachtas.ie/membership/{episode}")
        graph.add((member, RDF.type, URIRef("https://data.oireachtas.ie/ontology#Member")))
        graph.add((member, URIRef("http://xmlns.com/foaf/0.1/name"), Literal(name)))
        graph.add((member, URIRef(members_ns + "hasMembersMembership"), membership))
        graph.add((membership, RDF.type, URIRef(members_ns + "DailMembership")))
        graph.add((membership, URIRef(members_ns + "inHouseTerm"), URIRef(TERM_33)))
        graph.add((membership, URIRef(members_ns + "isRepresentativeFrom"), URIRef(CONSTITUENCY_33)))

    def readiness(self):
        return FusekiReadiness("ready", True, tuple((name, True) for name in
            ("Houses", "Parties", "Constituencies", "Members", "Bills")), "Fixture dataset")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type != "SELECT":
            raise AssertionError(f"unexpected query form: {result.type}")
        columns = tuple(str(variable) for variable in result.vars)
        rows = tuple(tuple(str(value) if value is not None else "—" for value in row) for row in result)
        return QueryResult("select", columns, rows)


def test_as_of_previous_term_uses_dates_not_term_labels_or_ordinals():
    supported = supported_predicates(ROOT / "ontology")
    query = previous_dail_term_query(AS_OF, supported_predicates=supported)
    assert "dct:temporal" in query and "dcat:startDate" in query and "dcat:endDate" in query
    assert "termNo" not in query and "prefLabel" not in query
    result = SyntheticFuseki().query(query)
    assert resolve_previous_dail(result, AS_OF) == (TERM_33, TERM_34)


def test_plan_keeps_independent_same_type_referents_and_joins_by_id():
    plan = plan_question("Who were the TDs for Dublin Mid-West in the last Dáil?", as_of=AS_OF)
    plan["referents"]["other_member"] = {"type": "Member"}
    plan["referents"]["other_membership"] = {"type": "DailMembership"}
    plan["relations"].append({
        "id": "other-member-membership", "fact": "member_has_membership",
        "from": "other_member", "to": "other_membership",
    })
    assert validate_plan(plan)["referents"]["other_member"] is not plan["referents"]["member"]


def test_approved_q09_wording_becomes_term_scoped_plan_without_series_identity():
    plan = plan_question(
        "Who were the TDs for Dublin South Central in the last Dáil?", as_of=AS_OF,
    )
    assert plan["referents"]["constituency"]["mention"] == "Dublin South Central"
    assert plan["referents"]["constituency"]["type"] == "DailConstituency"
    assert "DailConstituencySeries" not in repr(plan)
    assert plan["referents"]["term"]["selector"] == {"kind": "previousTerm", "house": "Dail"}


@pytest.mark.parametrize("mutation,match", [
    ("wrong_type", "Invalid referent types"),
    ("unsupported", "Unsupported semantic mapping"),
])
def test_invalid_relation_types_and_unreviewed_mappings_fail_closed(mutation, match):
    plan = plan_question("Who were the TDs for Dublin Mid-West in the last Dáil?", as_of=AS_OF)
    if mutation == "wrong_type":
        plan["relations"][0]["from"] = "member"
    else:
        plan["relations"][0]["fact"] = "invented_relation"
    with pytest.raises(PlanError, match=match):
        validate_plan(plan)


def test_term_scoped_constituency_ambiguity_and_not_found_are_distinct():
    ambiguous = QueryResult("select", ("iri", "label"), (
        ("https://data.oireachtas.ie/ie/a", "Dublin Mid-West@en"),
        ("https://data.oireachtas.ie/ie/b", "Dublin Mid-West@en"),
    ))
    with pytest.raises(AmbiguousConstituency):
        resolve_constituency(ambiguous, "Dublin Mid West")
    with pytest.raises(Exception, match="No matching constituency"):
        resolve_constituency(QueryResult("select", ("iri", "label"), ()), "Unknown")


def test_compile_requires_all_reviewed_relation_edges_and_passes_safety():
    supported = supported_predicates(ROOT / "ontology")
    plan = plan_question("Who represented Dublin Mid-West in the previous Dáil?", as_of=AS_OF)
    generated = compile_answer_query(plan, TERM_33, CONSTITUENCY_33, supported_predicates=supported)
    assert "SELECT DISTINCT ?member_member ?memberName" in generated
    assert "members:hasMembersMembership" in generated
    assert "members:inHouseTerm" in generated
    assert "members:isRepresentativeFrom" in generated
    assert "SERVICE" not in generated and "FROM NAMED" not in generated
    plan["relations"] = plan["relations"][:-1]
    with pytest.raises(PlanError, match="disconnected"):
        compile_answer_query(plan, TERM_33, CONSTITUENCY_33, supported_predicates=supported)


def test_end_to_end_synthetic_replacement_deduplication_and_readable_answer():
    outcome = execute_question(
        "Who were the TDs for Dublin Mid West in the last Dáil?", as_of=AS_OF,
        fuseki=SyntheticFuseki(), supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "success"
    assert outcome.result.columns == ("Member",)
    assert outcome.result.rows == (("Member A",), ("Member B",))
    assert "synthetic-" not in repr(outcome.result.rows)
    assert outcome.plan["referents"]["term"]["iri"] == TERM_33


def test_unavailable_term_evidence_and_constituency_resolution_outcomes_are_distinct():
    class NoTermEvidence(SyntheticFuseki):
        def query(self, query):
            self.queries.append(query)
            if "dct:temporal" in query:
                return QueryResult("select", ("term", "start", "end"), ())
            raise AssertionError("no constituency or answer query follows missing term evidence")

    outcome = execute_question(
        "Who were the TDs for Dublin Mid-West in the last Dáil?", as_of=AS_OF,
        fuseki=NoTermEvidence(), supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "source_data_unavailable"

    class AmbiguousSource(SyntheticFuseki):
        def query(self, query):
            self.queries.append(query)
            if "dct:temporal" in query:
                return QueryResult("select", ("term", "start", "end"), (
                    (TERM_33, "2020-02-08T00:00:00", "2024-11-08T00:00:00"),
                    (TERM_34, "2024-11-29T00:00:00", "—"),
                ))
            if "constituencyInHouseTerm" in query:
                return QueryResult("select", ("constituency", "label"), (
                    (CONSTITUENCY_33, "Dublin Mid-West@en"),
                    ("https://data.oireachtas.ie/ie/other/occurrence", "Dublin Mid-West@en"),
                ))
            raise AssertionError("ambiguous entity must block answer compilation")

    outcome = execute_question(
        "Who were the TDs for Dublin Mid-West in the last Dáil?", as_of=AS_OF,
        fuseki=AmbiguousSource(), supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "ambiguous"
    assert len(outcome.candidates) == 2


def test_source_backed_constituency_fixture_is_term_scoped_and_not_a_previous_term_fixture():
    houses = Graph().parse(ROOT / "tests/expected/houses.ttl", format="turtle")
    agents = "https://data.oireachtas.ie/ontology#"
    dct = "http://purl.org/dc/terms/"
    dcat = "http://www.w3.org/ns/dcat#"
    rows = []
    for term in houses.subjects(URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), URIRef(agents + "DailTerm")):
        for period in houses.objects(term, URIRef(dct + "temporal")):
            start = next(iter(houses.objects(period, URIRef(dcat + "startDate"))), None)
            end = next(iter(houses.objects(period, URIRef(dcat + "endDate"))), None)
            if start is not None:
                rows.append((str(term), str(start), str(end) if end is not None else "—"))
    assert resolve_previous_dail(QueryResult("select", ("term", "start", "end"), tuple(rows)), AS_OF) == (TERM_33, TERM_34)

    graph = Graph().parse(ROOT / "tests/expected/constituencies.ttl", format="turtle")
    term_34 = URIRef(TERM_34)
    term_links = {
        str(subject): str(obj) for subject, obj in graph.subject_objects(
            URIRef("https://data.oireachtas.ie/ontology/members#constituencyInHouseTerm"),
        )
    }
    mid_west = [iri for iri, term in term_links.items() if term == str(term_34)]
    assert len(mid_west) == 1
    assert "Dublin-Mid-West" in mid_west[0]
    assert not any(term == TERM_33 for term in term_links.values())


def test_unsupported_question_does_not_fall_through_to_answer_query():
    fake = SyntheticFuseki()
    outcome = execute_question(
        "Which Members voted for the Bill?", as_of=AS_OF, fuseki=fake,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "unsupported_capability"
    assert not fake.queries


def test_existing_ui_runs_composable_plan_and_hides_member_iris(monkeypatch):
    from poc.nlq import app as app_module

    fake = SyntheticFuseki()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-10-25")
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fake)
    application = app_module.create_app(repository_root=ROOT)
    response = TestClient(application).post("/ask", data={
        "question": "Who were the TDs for Dublin Mid-West in the last Dáil?",
        "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Member A" in response.text and "Member B" in response.text
    assert "synthetic-a" not in response.text and "synthetic-b" not in response.text
    assert "Validated composable query plan" in response.text
