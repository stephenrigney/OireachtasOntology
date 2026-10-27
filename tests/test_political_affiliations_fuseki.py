"""Disposable Fuseki acceptance; set POLITICAL_AFFILIATION_FUSEKI_* to run."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from rdflib import URIRef
from rdflib.namespace import RDF

from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.political_affiliations import (
    GRAPH_IRI, MEMBERS, build_graph, publish,
)
from oireachtas_etl.political_affiliations import require_disposable_dataset

GSP = os.getenv("POLITICAL_AFFILIATION_FUSEKI_GSP")
SPARQL = os.getenv("POLITICAL_AFFILIATION_FUSEKI_SPARQL")
USER = os.getenv("POLITICAL_AFFILIATION_FUSEKI_USER")
PASSWORD = os.getenv("POLITICAL_AFFILIATION_FUSEKI_PASSWORD")
CONFIRMATION = os.getenv("POLITICAL_AFFILIATION_FUSEKI_DISPOSABLE")
pytestmark = pytest.mark.skipif(not (GSP and SPARQL), reason="disposable Fuseki not configured")


def test_real_fuseki_publication_replacement_recovery_and_competencies():
    client = FusekiSparqlClient(SPARQL, user=USER, password=PASSWORD)
    # This is deliberately the first operation that can contact or mutate the
    # test dataset. A populated endpoint is rejected before any graph writes.
    require_disposable_dataset(client, CONFIRMATION)
    loader = FusekiGraphStoreLoader(GSP, user=USER, password=PASSWORD)
    for owner_graph in (
        "https://data.oireachtas.ie/graph/parties",
        "https://data.oireachtas.ie/graph/member/safeguard-sentinel",
        "https://example.test/other-owner-graph",
    ):
        sentinel = f"<{owner_graph}/subject> <https://example.test/preserved> \"sentinel\" .\n"
        loader.replace(owner_graph, sentinel, content_type="application/n-triples")
        with pytest.raises(RuntimeError, match="must be empty"):
            require_disposable_dataset(client, CONFIRMATION)
        assert len(client.construct_graph(owner_graph)) == 1
        loader.delete(owner_graph)
    party_graph = "https://data.oireachtas.ie/graph/parties"
    member_graph = "https://data.oireachtas.ie/graph/member/political-affiliation-test"
    party_records = [
        ("https://data.oireachtas.ie/ie/oireachtas/party/dail/1/Sinn_Féin", "sinn-fein-pre-independence"),
        ("https://data.oireachtas.ie/ie/oireachtas/party/dail/4/Sinn_Féin", "sinn-fein-anti-treaty"),
        ("https://data.oireachtas.ie/ie/oireachtas/party/dail/16/Sinn_Féin", "sinn-fein-1957"),
        ("https://data.oireachtas.ie/ie/oireachtas/party/dail/28/Sinn_Féin", "sinn-fein"),
    ]
    terms = [URIRef(f"https://data.oireachtas.ie/ie/oireachtas/house/dail/{n}") for n in (1, 4, 16, 28)]
    party_triples = []
    for (party, _), term in zip(party_records, terms):
        party_triples.extend([
            f"<{party}> <{RDF.type}> <{MEMBERS.ParliamentaryParty}> .",
            f"<{party}> <{MEMBERS.activeDuringTerm}> <{term}> .",
        ])
    party_payload = "\n".join(party_triples) + "\n"
    member_payload = "<https://data.oireachtas.ie/member/test> <https://example.test/preserved> \"yes\" .\n"
    loader.replace(party_graph, party_payload, content_type="application/n-triples")
    loader.replace(member_graph, member_payload, content_type="application/n-triples")
    parties_before = set(client.construct_graph(party_graph))
    member_before = set(client.construct_graph(member_graph))

    loader.replace(GRAPH_IRI, "<https://example.test/stale> <https://example.test/p> \"stale\" .\n",
                   content_type="application/n-triples")
    publish(GSP, SPARQL, user=USER, password=PASSWORD)
    expected = set(build_graph().graph(URIRef(GRAPH_IRI)))
    assert set(client.construct_graph(GRAPH_IRI)) == expected
    assert set(client.construct_graph(party_graph)) == parties_before
    assert set(client.construct_graph(member_graph)) == member_before

    # A verification endpoint failure is surfaced after the GSP PUT; rerunning
    # with healthy endpoints repeats the same atomic replacement and verifies it.
    with pytest.raises(Exception):
        publish(GSP, "http://127.0.0.1:1/unavailable", user=USER, password=PASSWORD)
    publish(GSP, SPARQL, user=USER, password=PASSWORD)
    assert set(client.construct_graph(GRAPH_IRI)) == expected

    query_dir = Path(__file__).parent / "competency"
    for filename, expected_count in (("political-affiliation-identities.rq", 4),
                                     ("historically-distinct-sinn-fein.rq", 4)):
        result = client.query((query_dir / filename).read_text(encoding="utf-8"))
        assert len(result) == expected_count
        assert len({row["identity"]["value"] for row in result}) == 4


def test_disposable_safeguard_refuses_missing_confirmation_before_query_or_write():
    class MustNotQuery:
        def query(self, sparql):
            raise AssertionError("dataset was queried without explicit disposable confirmation")

    with pytest.raises(RuntimeError, match="explicit disposable-dataset confirmation"):
        require_disposable_dataset(MustNotQuery(), None)


@pytest.mark.parametrize("graphs", [
    [{"g": {"value": "https://data.oireachtas.ie/graph/parties"}}],
    [{"g": {"value": "https://data.oireachtas.ie/graph/member/x"}}],
    [{"g": {"value": "https://example.test/other-owner-graph"}}],
])
def test_disposable_safeguard_refuses_any_existing_owner_graph(graphs):
    class ExistingGraphs:
        def query(self, sparql):
            assert "GRAPH ?g" in sparql
            return graphs

    with pytest.raises(RuntimeError, match="must be empty"):
        require_disposable_dataset(ExistingGraphs(), "I_CONFIRM_DISPOSABLE_FUSEKI")


def test_disposable_safeguard_refuses_default_graph_data():
    class DefaultGraphData:
        def query(self, sparql):
            return [] if "GRAPH ?g" in sparql else [{"s": {"value": "https://example.test/s"}}]

    with pytest.raises(RuntimeError, match="default graph contains triples"):
        require_disposable_dataset(DefaultGraphData(), "I_CONFIRM_DISPOSABLE_FUSEKI")


def test_publisher_requires_explicit_endpoint_arguments():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[1] / "tools/publish_political_affiliations.py")],
        text=True, capture_output=True,
    )
    assert result.returncode == 2
    assert "--gsp-endpoint" in result.stderr and "--sparql-endpoint" in result.stderr
