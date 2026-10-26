"""Disposable Fuseki acceptance; set POLITICAL_AFFILIATION_FUSEKI_* to run."""
import os
from pathlib import Path

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.political_affiliations import (
    GRAPH_IRI, MEMBERS, build_graph, publish,
)

GSP = os.getenv("POLITICAL_AFFILIATION_FUSEKI_GSP")
SPARQL = os.getenv("POLITICAL_AFFILIATION_FUSEKI_SPARQL")
USER = os.getenv("POLITICAL_AFFILIATION_FUSEKI_USER")
PASSWORD = os.getenv("POLITICAL_AFFILIATION_FUSEKI_PASSWORD")
pytestmark = pytest.mark.skipif(not (GSP and SPARQL), reason="disposable Fuseki not configured")


def test_real_fuseki_publication_replacement_recovery_and_competencies():
    loader = FusekiGraphStoreLoader(GSP, user=USER, password=PASSWORD)
    client = FusekiSparqlClient(SPARQL, user=USER, password=PASSWORD)
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
