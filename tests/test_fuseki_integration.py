"""Optional test against the local Compose Fuseki; it never selects production URLs."""
import json
import os
from argparse import Namespace
from pathlib import Path
import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD
from oireachtas_etl.competency import verify_constituencies_competency, verify_houses_competency, verify_parties_competency, verify_members_competency
from oireachtas_etl.cli import run_members
from oireachtas_etl.config import CONSTITUENCIES_GRAPH, HOUSES_GRAPH, PARTIES_GRAPH
from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.serialization import ntriples, turtle
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.parties import transform_parties
from oireachtas_etl.transforms.constituencies import transform_constituencies
from oireachtas_etl.transforms.members import member_graph_iri, source_hash, transform_member

GSP = os.getenv("OIR_TEST_FUSEKI_GSP_URL")
SPARQL = os.getenv("OIR_TEST_FUSEKI_SPARQL_URL")
FUSEKI_USER = os.getenv("OIR_TEST_FUSEKI_USER")
FUSEKI_PASSWORD = os.getenv("OIR_TEST_FUSEKI_PASSWORD")
if FUSEKI_USER is not None and FUSEKI_PASSWORD is None:
    raise RuntimeError("OIR_TEST_FUSEKI_PASSWORD is required when OIR_TEST_FUSEKI_USER is set")
pytestmark = pytest.mark.skipif(not (GSP and SPARQL), reason="set OIR_TEST_FUSEKI_GSP_URL and OIR_TEST_FUSEKI_SPARQL_URL for local Fuseki integration")

def _count(client, graph):
    rows = client.query(f"SELECT (COUNT(*) AS ?count) WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")
    return int(rows[0]["count"]["value"])

def _graph_from_gsp(endpoint, graph):
    import base64
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    result = Graph()
    headers = {"Accept": "text/turtle"}
    if FUSEKI_USER is not None:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{FUSEKI_USER}:{FUSEKI_PASSWORD}".encode()).decode()
    request = Request(endpoint + "?" + urlencode({"graph": graph}), headers=headers)
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
    loader, client = FusekiGraphStoreLoader(GSP, user=FUSEKI_USER, password=FUSEKI_PASSWORD), FusekiSparqlClient(SPARQL, user=FUSEKI_USER, password=FUSEKI_PASSWORD)
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


@pytest.mark.parametrize(("graph_iri", "fixture", "transform", "competency"), [
    (PARTIES_GRAPH, "parties.json", lambda value: transform_parties(value["results"]), verify_parties_competency),
    (CONSTITUENCIES_GRAPH, "constituencies.json", transform_constituencies, verify_constituencies_competency),
])
def test_reference_gsp_replacement_is_idempotent_and_removes_stale_content(graph_iri, fixture, transform, competency):
    root = Path(__file__).resolve().parents[1]
    graph = transform(json.loads((root / "data/api_examples" / fixture).read_text()))
    loader, client = FusekiGraphStoreLoader(GSP, user=FUSEKI_USER, password=FUSEKI_PASSWORD), FusekiSparqlClient(SPARQL, user=FUSEKI_USER, password=FUSEKI_PASSWORD)
    loader.replace(graph_iri, turtle(graph) + "\n<https://example.test/stale> <https://example.test/p> <https://example.test/o> .", content_type="text/turtle")
    loader.replace(graph_iri, turtle(graph), content_type="text/turtle")
    assert _count(client, graph_iri) == len(graph)
    assert set(_canonical_triples(_graph_from_gsp(GSP, graph_iri))) == set(_canonical_triples(graph))
    competency(client)
    smaller = transform(json.loads((root / "data/api_examples" / fixture).read_text()))
    for triple in list(smaller)[1:]:
        smaller.remove(triple)
    loader.replace(graph_iri, turtle(smaller), content_type="text/turtle")
    assert _count(client, graph_iri) == len(smaller)


def test_members_workflow_gsp_replacement_removes_stale_content_and_retains_absent_member(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    wrapper = json.loads((root / "data/api_examples/member.json").read_text())
    fixture = tmp_path / "member.json"; fixture.write_text(json.dumps(wrapper))
    state = tmp_path / "members-state.json"
    absent = "https://data.oireachtas.ie/ie/oireachtas/member/id/Absent"
    state.write_text(json.dumps({"version": 1, "members": {absent: {"published_hash": "retained", "graph_iri": "https://data.oireachtas.ie/graph/member/Absent", "contract_version": 1}}}))
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_file=str(state), output_nq=None,
                     output_ttl=None, fuseki_gsp_url=GSP, fuseki_sparql_url=SPARQL)
    graph_iri = member_graph_iri(wrapper["member"])
    loader = FusekiGraphStoreLoader(GSP, user=FUSEKI_USER, password=FUSEKI_PASSWORD)
    client = FusekiSparqlClient(SPARQL, user=FUSEKI_USER, password=FUSEKI_PASSWORD)
    assert run_members(args) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["new"] == [wrapper["member"]["uri"]] and first["missing_retained"] == [absent]
    first_state = json.loads(state.read_text())
    assert first_state["members"][wrapper["member"]["uri"]]["published_hash"] == source_hash(wrapper["member"])
    verify_members_competency(client)

    published = _graph_from_gsp(GSP, graph_iri)
    published.add((URIRef("https://example.test/stale"), URIRef("https://example.test/p"), URIRef("https://example.test/o")))
    loader.replace(graph_iri, ntriples(published), content_type="application/n-triples")
    assert _count(client, graph_iri) == len(published)

    changed = json.loads(json.dumps(wrapper)); changed["member"]["fullName"] = "Timmy Dooley changed"
    changed_fixture = tmp_path / "member-changed.json"; changed_fixture.write_text(json.dumps(changed))
    args.fixture = str(changed_fixture)
    args.raw_dir = str(tmp_path / "raw-changed")
    assert run_members(args) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["changed"] == [wrapper["member"]["uri"]] and second["new"] == [] and second["skipped_identities"] == []
    assert not list(_graph_from_gsp(GSP, graph_iri).triples((URIRef("https://example.test/stale"), None, None)))
    second_state = json.loads(state.read_text())
    assert second_state["members"][wrapper["member"]["uri"]]["published_hash"] == source_hash(changed["member"])
    assert second_state["members"][wrapper["member"]["uri"]]["published_hash"] != first_state["members"][wrapper["member"]["uri"]]["published_hash"]
    assert absent in second_state["members"]
    verify_members_competency(client)

    assert run_members(args) == 0
    third = json.loads(capsys.readouterr().out)
    assert third["new"] == [] and third["changed"] == [] and third["skipped_identities"] == [wrapper["member"]["uri"]]
    assert _count(client, graph_iri) == len(transform_member(changed))
    verify_members_competency(client)
