"""Optional test against the local Compose Fuseki; it never selects production URLs."""
import json
import os
from pathlib import Path
import pytest
from rdflib import Graph, Literal
from rdflib.namespace import XSD
from oireachtas_etl.competency import verify_houses_competency
from oireachtas_etl.config import HOUSES_GRAPH
from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.serialization import turtle
from oireachtas_etl.transforms.houses import transform_houses

GSP = os.getenv("OIR_TEST_FUSEKI_GSP_URL")
SPARQL = os.getenv("OIR_TEST_FUSEKI_SPARQL_URL")
pytestmark = pytest.mark.skipif(not (GSP and SPARQL), reason="set OIR_TEST_FUSEKI_GSP_URL and OIR_TEST_FUSEKI_SPARQL_URL for local Fuseki integration")

def _count(client, graph):
    rows = client.query(f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")
    return int(rows[0]["count"]["value"])

def _graph_from_gsp(endpoint, graph):
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    result = Graph()
    request = Request(endpoint + "?" + urlencode({"graph": graph}), headers={"Accept": "text/turtle"})
    with urlopen(request) as response:
        result.parse(data=response.read().decode("utf-8"), format="turtle")
    return result

def _canonical_triples(graph):
    for subject, predicate, object_ in graph:
        if isinstance(object_, Literal) and object_.language is None and object_.datatype in (None, XSD.string):
            object_ = Literal(str(object_))
        yield subject, predicate, object_

def test_gsp_replacement_is_idempotent_isolated_and_removes_stale_content():
    root = Path(__file__).resolve().parents[1]
    records = json.loads((root / "data/api_examples/houses.json").read_text())
    graph = transform_houses(records)
    loader, client = FusekiGraphStoreLoader(GSP), FusekiSparqlClient(SPARQL)
    other = "https://data.oireachtas.ie/graph/fuseki-integration-other"
    loader.replace(other, "<https://example.test/other> <https://example.test/p> <https://example.test/o> .", content_type="application/n-triples")
    # Add arbitrary stale data, then replace the Houses graph twice with the exact same graph.
    loader.replace(HOUSES_GRAPH, turtle(graph) + "\n<https://example.test/stale> <https://example.test/p> <https://example.test/o> .", content_type="text/turtle")
    loader.replace(HOUSES_GRAPH, turtle(graph), content_type="text/turtle")
    expected_count = len(graph)
    assert _count(client, HOUSES_GRAPH) == expected_count
    assert set(_canonical_triples(_graph_from_gsp(GSP, HOUSES_GRAPH))) == set(_canonical_triples(graph))
    loader.replace(HOUSES_GRAPH, turtle(graph), content_type="text/turtle")
    assert _count(client, HOUSES_GRAPH) == expected_count
    assert set(_canonical_triples(_graph_from_gsp(GSP, HOUSES_GRAPH))) == set(_canonical_triples(graph))
    verify_houses_competency(client)
    smaller = transform_houses(records[:1])
    loader.replace(HOUSES_GRAPH, turtle(smaller), content_type="text/turtle")
    assert _count(client, HOUSES_GRAPH) == len(smaller)
    assert _count(client, other) == 1
