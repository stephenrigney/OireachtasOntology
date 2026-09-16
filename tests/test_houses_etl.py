import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, XSD
from rdflib.namespace import SKOS

from oireachtas_etl.raw import persist_raw
from oireachtas_etl.serialization import nquads
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.validation import validate_houses

ROOT = Path(__file__).resolve().parents[1]
RECORDS = json.loads((ROOT / "data/api_examples/houses.json").read_text())

def test_houses_matches_golden_semantics_and_is_deterministic():
    graph = transform_houses(RECORDS)
    expected = Graph().parse(ROOT / "tests/expected/houses.ttl")
    assert set(graph) == set(expected)
    for house, label in [("dail", "Dáil Éireann"), ("seanad", "Seanad Éireann")]:
        persistent = URIRef(f"https://data.oireachtas.ie/house/{house}")
        assert (persistent, DCTERMS.title, Literal(label, lang="ga")) in graph
        assert (persistent, SKOS.prefLabel, Literal(label, lang="ga")) in graph
    assert nquads(graph, "https://data.oireachtas.ie/graph/houses") == nquads(transform_houses(RECORDS), "https://data.oireachtas.ie/graph/houses")
    current = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34#term-period")
    assert not list(graph.objects(current, DCAT.endDate))
    assert (URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), DCTERMS.temporal, current) in graph

def test_houses_validate_and_answer_competency_queries():
    graph = transform_houses(RECORDS); validate_houses(RECORDS, graph)
    from oireachtas_etl.competency import EXPECTED, verify_houses_competency
    class Client:
        def __init__(self): self.index = 0
        def query(self, query):
            filename = list(EXPECTED)[self.index]; self.index += 1
            return [{key: {"value": value} for key, value in row.items()} for row in EXPECTED[filename]]
    verify_houses_competency(Client())

def test_competency_queries_execute_against_houses_dataset():
    from oireachtas_etl.competency import EXPECTED, QUERIES
    from oireachtas_etl.config import HOUSES_GRAPH

    dataset = Dataset()
    houses = dataset.graph(URIRef(HOUSES_GRAPH))
    for triple in transform_houses(RECORDS):
        houses.add(triple)

    for filename, expected in EXPECTED.items():
        rows = dataset.query(QUERIES.joinpath(filename).read_text())
        actual = [{str(name): str(value) for name, value in row.asdict().items()} for row in rows]
        assert actual == expected

def test_unknown_house_is_rejected():
    bad = json.loads(json.dumps(RECORDS)); bad[0]["house"]["houseCode"] = "committee"
    with pytest.raises(ValueError, match="unsupported houseCode"): transform_houses(bad)

def test_combined_house_is_reported_and_excluded():
    from oireachtas_etl.transforms.houses import transform_houses_with_report
    combined = json.loads(json.dumps(RECORDS[0])); combined["house"]["houseCode"] = "dail & seanad"
    graph, exclusions = transform_houses_with_report([combined])
    assert exclusions == [{"uri": combined["house"]["uri"], "houseCode": "dail & seanad", "reason": "combined-house record"}]
    assert not list(graph.triples((URIRef(combined["house"]["uri"]), None, None)))

@pytest.mark.parametrize("mutate", [
    lambda graph: graph.remove((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), DCTERMS.temporal, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34#term-period"))),
    lambda graph: graph.remove((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), None, Literal("34th Dáil", lang="en"))),
    lambda graph: graph.remove((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), __import__("rdflib").namespace.RDF.type, __import__("oireachtas_etl.transforms.common", fromlist=["ELIDL"]).ELIDL.ParliamentaryTerm)),
    lambda graph: graph.remove((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34#term-period"), __import__("rdflib").namespace.RDF.type, DCTERMS.PeriodOfTime)),
    lambda graph: graph.set((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), __import__("oireachtas_etl.transforms.common", fromlist=["OIR"]).OIR.houseCode, Literal("seanad", datatype=XSD.string))),
    lambda graph: graph.set((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), __import__("oireachtas_etl.transforms.common", fromlist=["OIR"]).OIR.termOf, URIRef("https://data.oireachtas.ie/house/seanad"))),
])
def test_shacl_rejects_mapping_invariant_mutations(mutate):
    graph = transform_houses(RECORDS); mutate(graph)
    with pytest.raises(ValueError, match="SHACL validation failed"): validate_houses(RECORDS, graph)

def test_shacl_requires_persistent_house_descriptions():
    graph = transform_houses(RECORDS)
    persistent = URIRef("https://data.oireachtas.ie/house/dail")
    graph.remove((persistent, DCTERMS.title, None))
    with pytest.raises(ValueError, match="SHACL validation failed"):
        validate_houses(RECORDS, graph)

def test_quality_rejects_reverse_dail_period():
    graph = transform_houses(RECORDS)
    period = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/33#term-period")
    graph.set((period, DCAT.endDate, Literal("2019-01-01T00:00:00", datatype=XSD.dateTime)))
    with pytest.raises(ValueError, match="reverse period"): validate_houses(RECORDS, graph)

def test_raw_preservation_metadata_and_collision(tmp_path):
    when = datetime(2026, 1, 2, tzinfo=timezone.utc)
    raw, metadata = persist_raw(root=tmp_path, endpoint="https://example.test/houses", params={"skip": 0, "limit": 10}, body=b"[ ]", status=200, retrieved_at=when, ontology_version="ontology-v", mapping_version="mapping-v")
    meta = json.loads(metadata.read_text())
    assert raw.read_bytes() == b"[ ]"
    assert set(meta) == {"endpoint", "params", "retrieved_at", "status", "sha256", "etl_version", "ontology_version", "mapping_version"}
    with pytest.raises(FileExistsError):
        persist_raw(root=tmp_path, endpoint="x", params={"skip": 0, "limit": 10}, body=b"[]", status=200, retrieved_at=when, ontology_version="ontology-v", mapping_version="mapping-v")

def test_cli_never_constructs_loader_after_validation_failure(tmp_path, monkeypatch):
    from argparse import Namespace
    from oireachtas_etl import cli
    bad = json.loads(json.dumps(RECORDS)); bad[0]["house"]["houseCode"] = "invalid"
    fixture = tmp_path / "bad.json"; fixture.write_text(json.dumps(bad))
    called = []
    class Loader:
        def __init__(self, *args, **kwargs): called.append("constructed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setenv("OIR_FUSEKI_GSP_URL", "http://local.test/data")
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None, fuseki_gsp_url=None, fuseki_sparql_url=None)
    with pytest.raises(ValueError, match="unsupported houseCode"): cli.run_houses(args)
    assert called == []

def test_cli_never_constructs_loader_without_sparql_endpoint(tmp_path, monkeypatch):
    from argparse import Namespace
    from oireachtas_etl import cli
    fixture = tmp_path / "houses.json"; fixture.write_text(json.dumps(RECORDS))
    called = []
    class Loader:
        def __init__(self, *args, **kwargs): called.append("constructed")
        def replace(self, *args, **kwargs): called.append("invoked")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setenv("OIR_FUSEKI_GSP_URL", "http://local.test/data")
    monkeypatch.delenv("OIR_FUSEKI_SPARQL_URL", raising=False)
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None, fuseki_gsp_url=None, fuseki_sparql_url=None)
    with pytest.raises(ValueError, match="SPARQL endpoint is required"): cli.run_houses(args)
    assert called == []

def test_cli_offline_ignores_configured_fuseki_endpoints(tmp_path, monkeypatch):
    from argparse import Namespace
    from oireachtas_etl import cli
    fixture = tmp_path / "houses.json"; fixture.write_text(json.dumps(RECORDS))
    called = []
    class Loader:
        def __init__(self, *args, **kwargs): called.append("constructed")
    def competency(client): called.append("competency")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "verify_houses_competency", competency)
    monkeypatch.setenv("OIR_FUSEKI_GSP_URL", "http://local.test/data")
    monkeypatch.setenv("OIR_FUSEKI_SPARQL_URL", "http://local.test/query")
    args = Namespace(fixture=str(fixture), offline=True, raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None,
                     fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert cli.run_houses(args) == 0
    assert called == []
