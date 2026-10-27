"""Q06 fixture tests: synthetic membership evidence plus the reviewed identity register."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from poc.nlq.composable_plan import (
    PlanError,
    execute_question,
    plan_question,
    validate_plan,
)
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates
from oireachtas_etl.political_affiliations import GRAPH_IRI, build_graph


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 25)
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
AGENTS = "https://data.oireachtas.ie/ontology#"
FOAF_NAME = URIRef("http://xmlns.com/foaf/0.1/name")
MEMBER = URIRef("https://data.oireachtas.ie/member/id/synthetic-stephen-donnelly")


class Q06Fixture:
    """Minimal synthetic evidence; identity associations and labels are reviewed data."""

    def __init__(self, *, missing_memberships=False, missing_identity=False,
                 missing_affiliation_dates=False, ambiguous=False):
        self.dataset = Dataset()
        self.queries = []
        self.member_graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/synthetic-stephen-donnelly"))
        self.parties = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
        self.houses = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
        self.identities = self.dataset.graph(URIRef(GRAPH_IRI))
        reviewed = build_graph().graph(URIRef(GRAPH_IRI))
        for triple in reviewed:
            self.identities.add(triple)

        self.member_graph.add((MEMBER, RDF.type, URIRef(AGENTS + "Member")))
        self.member_graph.add((MEMBER, FOAF_NAME, Literal("Stephen Donnelly")))
        if ambiguous:
            other = URIRef("https://data.oireachtas.ie/member/id/second-stephen-donnelly")
            graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/second-stephen-donnelly"))
            graph.add((other, RDF.type, URIRef(AGENTS + "Member")))
            graph.add((other, FOAF_NAME, Literal("Stephen Donnelly")))

        if not missing_memberships:
            decisions = json.loads((ROOT / "reports/party-identity-decisions.json").read_text())
            source_by_identity = {}
            for row in decisions["records"]:
                if row["outcome"] == "accepted" and row["identity"] in {"social-democrats", "fianna-fail"}:
                    source_by_identity.setdefault(row["identity"], []).append(row["source_iri"])
            sources = source_by_identity["social-democrats"][:1] + source_by_identity["fianna-fail"][:2]
            member_collection_membership = URIRef("https://data.oireachtas.ie/membership/synthetic-party-membership")
            for index, party_text in enumerate(sources):
                party = URIRef(party_text)
                term_number = party_text.split("/party/dail/", 1)[1].split("/", 1)[0]
                term = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/house/dail/{term_number}")
                episode = URIRef(f"https://data.oireachtas.ie/membership/synthetic-party-episode-{index}")
                parliamentary_membership = URIRef(f"https://data.oireachtas.ie/membership/synthetic-dail-episode-{index}")
                parliamentary_date_range = URIRef(f"https://data.oireachtas.ie/membership/synthetic-parliamentary-date-range-{index}")
                party_date_range = URIRef(f"https://data.oireachtas.ie/membership/synthetic-party-date-range-{index}")
                self.parties.add((party, RDF.type, URIRef(MEMBERS + "ParliamentaryParty")))
                self.parties.add((party, SKOS.prefLabel, Literal("deliberately not the identity label", lang="en")))
                self.parties.add((party, URIRef(MEMBERS + "activeDuringTerm"), term))
                self.houses.add((term, RDF.type, URIRef(AGENTS + "DailTerm")))
                self.member_graph.add((MEMBER, URIRef(MEMBERS + "hasMembersMembership"), episode))
                self.member_graph.add((episode, RDF.type, URIRef(MEMBERS + "PartyMembership")))
                self.member_graph.add((episode, URIRef(MEMBERS + "inOireachtasMembership"), parliamentary_membership))
                self.member_graph.add((episode, URIRef(MEMBERS + "isPartyMembershipOf"), party))
                self.member_graph.add((parliamentary_membership, RDF.type, URIRef(MEMBERS + "DailMembership")))
                self.member_graph.add((parliamentary_membership, URIRef(MEMBERS + "inHouseTerm"), term))
                self.member_graph.add((parliamentary_membership, URIRef(MEMBERS + "hasMembershipDateRange"), parliamentary_date_range))
                self.member_graph.add((parliamentary_date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
                self.member_graph.add((parliamentary_date_range, URIRef(MEMBERS + "StartDate"), Literal(f"{2011 + index}-03-09", datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))))
                self.member_graph.add((parliamentary_date_range, URIRef(MEMBERS + "EndDate"), Literal(f"{2016 + index}-02-03", datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))))
                if not missing_affiliation_dates:
                    self.member_graph.add((episode, URIRef(MEMBERS + "hasMembershipDateRange"), party_date_range))
                    self.member_graph.add((party_date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
                    self.member_graph.add((party_date_range, URIRef(MEMBERS + "StartDate"), Literal(f"{1998 + index}-04-01", datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))))
                    self.member_graph.add((party_date_range, URIRef(MEMBERS + "EndDate"), Literal(f"{2001 + index}-09-30", datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))))
            # An Independent collection is not typed PartyMembership and is not
            # associated with an enduring identity.
            independent = URIRef("https://data.oireachtas.ie/membership/synthetic-independent")
            self.member_graph.add((MEMBER, URIRef(MEMBERS + "hasMembersMembership"), independent))
            self.member_graph.add((independent, RDF.type, URIRef(MEMBERS + "ParliamentaryCollectionMembership")))
            self.member_graph.add((independent, URIRef(MEMBERS + "memberOfCollection"), URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/33/Independent")))
            if missing_identity:
                self.identities.remove((None, URIRef(MEMBERS + "hasPoliticalAffiliationIdentity"), None))

    def readiness(self):
        return FusekiReadiness("ready", True, tuple((name, True) for name in
            ("Houses", "Parties", "Constituencies", "Members", "Bills")), "bounded fixture")

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


def test_q06_plan_is_typed_and_uses_all_three_reviewed_edges():
    plan = plan_question("What parties was Stephen Donnelly a member of?", as_of=AS_OF)
    assert plan["referents"]["affiliation"]["type"] == "PoliticalAffiliationIdentity"
    assert {relation["fact"] for relation in plan["relations"]} == {
        "member_party_membership", "episode_in_parliamentary_party",
        "parliamentary_party_has_affiliation_identity",
    }
    plan["relations"].pop()
    with pytest.raises(PlanError, match="additional or repeated"):
        validate_plan(plan)


def test_q06_end_to_end_deduplicates_by_reviewed_identity_and_preserves_episode_gaps():
    outcome = execute_question(
        "What parties was Stephen Donnelly a member of?", as_of=AS_OF,
        fuseki=Q06Fixture(), supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.columns == ("Political affiliation", "Supporting membership episodes")
    assert len(outcome.result.rows) == 2
    by_label = dict(outcome.result.rows)
    assert set(by_label) == {"Fianna Fáil", "Social Democrats"}
    assert ";" in by_label["Fianna Fáil"]
    assert "1999-04-01" in by_label["Fianna Fáil"]
    assert "2000-04-01" in by_label["Fianna Fáil"]
    assert "2012-03-09" not in by_label["Fianna Fáil"]
    assert "2013-03-09" not in by_label["Fianna Fáil"]
    assert "Independent" not in repr(outcome.result.rows)
    assert "hasPoliticalAffiliationIdentity" in outcome.sparql
    assert "activeDuringTerm" in outcome.sparql and "inHouseTerm" in outcome.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/houses>" in outcome.sparql
    assert "recognisedAsParty" not in outcome.sparql
    assert "deliberately not the identity label" not in repr(outcome.result.rows)


def test_q06_missing_affiliation_dates_keep_identity_and_do_not_fall_back_to_term_dates():
    outcome = execute_question(
        "What parties was Stephen Donnelly a member of?", as_of=AS_OF,
        fuseki=Q06Fixture(missing_affiliation_dates=True),
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == "success", outcome.diagnostic
    by_label = dict(outcome.result.rows)
    assert set(by_label) == {"Fianna Fáil", "Social Democrats"}
    assert by_label["Fianna Fáil"].count("membership episode (dates not recorded)") == 2
    assert by_label["Social Democrats"] == "membership episode (dates not recorded)"
    assert "2011-03-09" not in repr(outcome.result.rows)


@pytest.mark.parametrize(("fixture", "status"), [
    (Q06Fixture(missing_memberships=True), "source_data_unavailable"),
    (Q06Fixture(missing_identity=True), "missing_identity_link"),
])
def test_q06_missing_evidence_outcomes_are_distinct(fixture, status):
    outcome = execute_question(
        "What parties was Stephen Donnelly a member of?", as_of=AS_OF,
        fuseki=fixture, supported_predicates=supported_predicates(ROOT / "ontology"),
    )
    assert outcome.status == status


def test_q06_ambiguous_and_missing_member_resolution_are_distinct():
    supported = supported_predicates(ROOT / "ontology")
    ambiguous_fixture = Q06Fixture(ambiguous=True)
    ambiguous = execute_question(
        "What parties was Stephen Donnelly a member of?", as_of=AS_OF,
        fuseki=ambiguous_fixture, supported_predicates=supported,
    )
    assert ambiguous.status == "ambiguous" and len(ambiguous.candidates) == 2
    assert len(ambiguous_fixture.queries) == 1  # no answer query after ambiguous resolution
    missing = execute_question(
        "What parties was Niamh Example a member of?", as_of=AS_OF,
        fuseki=Q06Fixture(), supported_predicates=supported,
    )
    assert missing.status == "not_found"


def test_q06_ui_explains_ambiguous_member_without_selecting_one(monkeypatch):
    from poc.nlq import app as app_module

    fixture = Q06Fixture(ambiguous=True)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-10-25")
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "What parties was Stephen Donnelly a member of?", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Ambiguous entity" in response.text
    assert response.text.count("Stephen Donnelly") >= 2
    assert "Possible local matches" in response.text
    assert len(fixture.queries) == 1


def test_q06_unsupported_question_does_not_execute_queries():
    fixture = Q06Fixture()
    outcome = execute_question("Which Members voted for the Bill?", as_of=AS_OF,
                                fuseki=fixture, supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "unsupported_capability"
    assert not fixture.queries


def test_existing_ui_runs_q06_composable_path_and_renders_readable_episodes(monkeypatch):
    from poc.nlq import app as app_module

    fixture = Q06Fixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-10-25")
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "What parties was Stephen Donnelly a member of?", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Fianna Fáil" in response.text and "Social Democrats" in response.text
    assert "Supporting membership episodes" in response.text
    assert "synthetic-party" not in response.text
    assert "Validated composable query plan" in response.text
