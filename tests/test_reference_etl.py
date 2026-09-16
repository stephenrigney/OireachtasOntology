import json
from argparse import Namespace
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from oireachtas_etl.competency import CONSTITUENCIES_EXPECTED, PARTIES_EXPECTED, QUERIES
from oireachtas_etl.config import CONSTITUENCIES_GRAPH, PARTIES_GRAPH
from oireachtas_etl.serialization import nquads
from oireachtas_etl.transforms.common import MEMBERS, OIR
from oireachtas_etl.transforms.constituencies import transform_constituencies
from oireachtas_etl.transforms.parties import transform_parties
from oireachtas_etl.validation import validate_constituencies, validate_parties

ROOT = Path(__file__).resolve().parents[1]
PARTIES = json.loads((ROOT / "data/api_examples/parties.json").read_text())["results"]
CONSTITUENCIES = json.loads((ROOT / "data/api_examples/constituencies.json").read_text())


def test_parties_are_deterministic_and_preserve_term_scoped_independent_iri():
    graph = transform_parties(PARTIES)
    independent = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent")
    assert len(graph) == 54
    assert set(graph) == set(Graph().parse(ROOT / "tests/expected/parties.ttl"))
    assert (independent, RDF.type, MEMBERS.PartyGrouping) in graph
    assert (independent, RDF.type, MEMBERS.Party) not in graph
    assert not list(graph.triples((MEMBERS.Independent, None, None)))
    assert nquads(graph, PARTIES_GRAPH) == nquads(transform_parties(PARTIES), PARTIES_GRAPH)
    validate_parties(PARTIES, graph)


def test_constituencies_match_golden_and_are_deterministic():
    graph = transform_constituencies(CONSTITUENCIES)
    assert set(graph) == set(Graph().parse(ROOT / "tests/expected/constituencies.ttl"))
    assert nquads(graph, CONSTITUENCIES_GRAPH) == nquads(transform_constituencies(CONSTITUENCIES), CONSTITUENCIES_GRAPH)
    validate_constituencies(CONSTITUENCIES, graph)


@pytest.mark.parametrize(("records", "transform", "validator", "term"), [
    (PARTIES, transform_parties, validate_parties, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/31")),
    (CONSTITUENCIES, transform_constituencies, validate_constituencies, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34")),
])
def test_reference_graphs_only_link_to_houseterms(records, transform, validator, term):
    graph = transform(records)
    assert not list(graph.triples((term, None, None)))
    graph.add((term, SKOS.prefLabel, Literal("A HouseTerm label", lang="en")))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validator(records, graph)


@pytest.mark.parametrize(("records", "validator"), [
    (PARTIES, validate_parties), (CONSTITUENCIES, validate_constituencies),
])
def test_nonempty_source_rejects_empty_or_incomplete_output(records, validator):
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: missing"):
        validator(records, Graph())


@pytest.mark.parametrize(("records", "transform", "validator", "subject", "predicate"), [
    (PARTIES, transform_parties, validate_parties, URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael"), MEMBERS.partyCode),
    (CONSTITUENCIES, transform_constituencies, validate_constituencies, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Mid-West"), MEMBERS.representCode),
])
def test_source_records_require_every_expected_output_value(records, transform, validator, subject, predicate):
    graph = transform(records); graph.remove((subject, predicate, None))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: missing"):
        validator(records, graph)


def test_parties_reject_a_complete_but_unsourced_party_resource():
    graph = transform_parties(PARTIES)
    extra = {
        "party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Unsourced", "partyCode": "Unsourced", "showAs": "Unsourced"},
        "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/31", "houseNo": "31", "houseCode": "dail"},
    }
    for triple in transform_parties([extra]):
        graph.add(triple)
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_parties(PARTIES, graph)


@pytest.mark.parametrize(("records", "transform", "validator", "subject"), [
    (PARTIES, transform_parties, validate_parties, URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael")),
    (CONSTITUENCIES, transform_constituencies, validate_constituencies, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Mid-West")),
])
def test_reference_graphs_reject_unexpected_predicates_on_valid_subjects(records, transform, validator, subject):
    graph = transform(records)
    graph.add((subject, URIRef("https://example.test/unexpected"), Literal("unexpected")))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validator(records, graph)


@pytest.mark.parametrize(("records", "transform", "validator"), [
    (PARTIES, transform_parties, validate_parties), (CONSTITUENCIES, transform_constituencies, validate_constituencies),
])
def test_reference_graphs_reject_unsourced_resource_with_houses_owned_predicate(records, transform, validator):
    graph = transform(records)
    graph.add((URIRef("https://example.test/unsourced"), OIR.termNo, Literal(1, datatype=XSD.integer)))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validator(records, graph)


@pytest.mark.parametrize(("records", "transform", "validator", "term"), [
    (PARTIES, transform_parties, validate_parties, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/31")),
    (CONSTITUENCIES, transform_constituencies, validate_constituencies, URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34")),
])
def test_reference_graphs_reject_all_linked_and_standalone_house_descriptions(records, transform, validator, term):
    for predicate, value in [
        (RDF.type, OIR.DailTerm), (OIR.termNo, Literal(31, datatype=XSD.integer)),
        (OIR.houseCode, Literal("dail", datatype=XSD.string)), (OIR.seats, Literal(160, datatype=XSD.integer)),
        (OIR.termOf, URIRef("https://data.oireachtas.ie/house/dail")), (DCTERMS.temporal, URIRef(str(term) + "#period")), (SKOS.prefLabel, Literal("Term", lang="en")),
        (URIRef("https://example.test/arbitrary"), Literal("description")),
    ]:
        graph = transform(records); graph.add((term, predicate, value))
        with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
            validator(records, graph)
    graph = transform(records); graph.add((URIRef("https://data.oireachtas.ie/house/dail"), SKOS.prefLabel, Literal("Dáil", lang="ga")))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validator(records, graph)


def test_reference_source_requires_consistent_houseterm_iri_and_constituency_type():
    bad = json.loads(json.dumps(CONSTITUENCIES)); bad[0]["house"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/house/dail/10"
    with pytest.raises(ValueError, match="house.uri must be the direct IRI"):
        validate_constituencies(bad, Graph())
    synthetic = json.loads(json.dumps(CONSTITUENCIES[:1]))
    synthetic.append({"constituencyOrPanel": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35/constituency/Test", "showAs": "Test", "representCode": "Test", "representType": "constituency"}, "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35", "houseNo": "35", "houseCode": "dail"}})
    graph = transform_constituencies(synthetic)
    assert URIRef(synthetic[0]["constituencyOrPanel"]["uri"]) != URIRef(synthetic[1]["constituencyOrPanel"]["uri"])
    validate_constituencies(synthetic, graph)


def test_primary_source_iris_must_match_associated_terms_types_and_slugs():
    party = json.loads(json.dumps(PARTIES[:1]))
    party[0]["party"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/party/seanad/31/Anti-Austerity_Alliance_People_Before_Profit"
    with pytest.raises(ValueError, match="party.uri must embed"):
        validate_parties(party, Graph())
    party = json.loads(json.dumps(PARTIES[:1]))
    party[0]["party"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/not-the-code"
    with pytest.raises(ValueError, match="party.uri must embed"):
        validate_parties(party, Graph())
    representation = json.loads(json.dumps(CONSTITUENCIES[:1]))
    representation[0]["constituencyOrPanel"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/house/dail/9/panel/Cork-South-East"
    with pytest.raises(ValueError, match="constituencyOrPanel.uri must match"):
        validate_constituencies(representation, Graph())
    representation = json.loads(json.dumps(CONSTITUENCIES[:1]))
    representation[0]["constituencyOrPanel"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/house/dail/8/constituency/Cork-South-East"
    with pytest.raises(ValueError, match="constituencyOrPanel.uri must embed"):
        validate_constituencies(representation, Graph())


def test_unicode_party_code_accepts_literal_and_percent_encoded_source_slug():
    party = json.loads(json.dumps(PARTIES[1]))
    validate_parties([party], transform_parties([party]))
    party["party"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Sinn_F%C3%A9in"
    validate_parties([party], transform_parties([party]))


@pytest.mark.parametrize(("records", "validator"), [( [], validate_parties), ([], validate_constituencies)])
def test_empty_reference_source_cannot_validate(records, validator):
    with pytest.raises(ValueError, match="reference dataset must be a non-empty list"):
        validator(records, Graph())


def test_unknown_representation_and_incompatible_house_fail_closed():
    unknown = json.loads(json.dumps(CONSTITUENCIES)); unknown[0]["constituencyOrPanel"]["representType"] = "region"
    with pytest.raises(ValueError, match="unsupported representType"):
        transform_constituencies(unknown)
    incompatible = json.loads(json.dumps(CONSTITUENCIES)); incompatible[0]["house"]["houseCode"] = "seanad"
    with pytest.raises(ValueError, match="requires houseCode"):
        transform_constituencies(incompatible)


@pytest.mark.parametrize(("records", "transform", "validator", "mutation"), [
    (PARTIES, transform_parties, validate_parties, lambda graph: graph.remove((URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael"), MEMBERS.partyCode, None))),
    (CONSTITUENCIES, transform_constituencies, validate_constituencies, lambda graph: graph.remove((URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Dublin-Mid-West"), SKOS.prefLabel, None))),
])
def test_reference_shacl_rejects_mapping_mutations(records, transform, validator, mutation):
    graph = transform(records); mutation(graph)
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: missing"):
        validator(records, graph)


def test_independent_cannot_be_party_or_linked_to_ontology_independent():
    graph = transform_parties(PARTIES)
    independent = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent")
    graph.add((independent, RDF.type, MEMBERS.Party))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_parties(PARTIES, graph)
    graph = transform_parties(PARTIES)
    graph.add((independent, URIRef("http://www.w3.org/2002/07/owl#sameAs"), MEMBERS.Independent))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_parties(PARTIES, graph)


@pytest.mark.parametrize(("records", "transform", "validator"), [
    (PARTIES, transform_parties, validate_parties), (CONSTITUENCIES, transform_constituencies, validate_constituencies),
])
def test_rogue_nonconventional_house_type_is_rejected(records, transform, validator):
    graph = transform(records)
    graph.add((URIRef("https://example.test/not-a-house-path"), RDF.type, OIR.HouseTerm))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validator(records, graph)


def test_reference_competency_queries_execute_against_named_graphs():
    dataset = Dataset()
    for graph_iri, records, transform, expected in [
        (PARTIES_GRAPH, PARTIES, transform_parties, PARTIES_EXPECTED),
        (CONSTITUENCIES_GRAPH, CONSTITUENCIES, transform_constituencies, CONSTITUENCIES_EXPECTED),
    ]:
        target = dataset.graph(URIRef(graph_iri))
        for triple in transform(records): target.add(triple)
        for filename, rows in expected.items():
            actual = [{str(name): str(value) for name, value in row.asdict().items()} for row in dataset.query(QUERIES.joinpath(filename).read_text())]
            assert actual == rows


@pytest.mark.parametrize(("endpoint", "fixture"), [
    ("parties", "parties.json"), ("constituencies", "constituencies.json"),
])
def test_reference_cli_offline_persists_and_serializes(tmp_path, endpoint, fixture):
    from oireachtas_etl.cli import main
    output = tmp_path / "output.nq"
    result = main(["run", endpoint, "--fixture", str(ROOT / "data/api_examples" / fixture), "--offline", "--raw-dir", str(tmp_path / "raw"), "--output-nq", str(output)])
    assert result == 0 and output.exists()
    assert (tmp_path / "raw" / endpoint).exists()


def test_reference_cli_never_constructs_loader_after_validation_failure(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    bad = json.loads(json.dumps(CONSTITUENCIES)); bad[0]["constituencyOrPanel"]["representType"] = "bad"
    fixture = tmp_path / "bad.json"; fixture.write_text(json.dumps(bad))
    called = []
    class Loader:
        def __init__(self, *args, **kwargs): called.append("constructed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    args = Namespace(endpoint="constituencies", fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None, fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query")
    with pytest.raises(ValueError, match="unsupported representType"):
        cli.run_reference(args)
    assert called == []


@pytest.mark.parametrize(("endpoint", "source"), [("parties", {"results": []}), ("constituencies", [])])
def test_empty_reference_cli_never_constructs_loader(tmp_path, monkeypatch, endpoint, source):
    from oireachtas_etl import cli
    fixture = tmp_path / f"{endpoint}.json"; fixture.write_text(json.dumps(source))
    called = []
    class Loader:
        def __init__(self, *args, **kwargs): called.append("constructed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    args = Namespace(endpoint=endpoint, fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None, fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query")
    with pytest.raises(ValueError, match="reference dataset must be a non-empty list"):
        cli.run_reference(args)
    assert called == []


def test_raw_metadata_versions_are_endpoint_specific_and_houses_remain_phase_one(tmp_path):
    from oireachtas_etl.cli import main
    assert main(["run", "houses", "--fixture", str(ROOT / "data/api_examples/houses.json"), "--offline", "--raw-dir", str(tmp_path)]) == 0
    assert main(["run", "parties", "--fixture", str(ROOT / "data/api_examples/parties.json"), "--offline", "--raw-dir", str(tmp_path)]) == 0
    assert main(["run", "constituencies", "--fixture", str(ROOT / "data/api_examples/constituencies.json"), "--offline", "--raw-dir", str(tmp_path)]) == 0
    metadata = {endpoint: json.loads(next((tmp_path / endpoint).rglob("*.meta.json")).read_text()) for endpoint in ("houses", "parties", "constituencies")}
    assert metadata["houses"]["ontology_version"] == "agents.owl.ttl@phase-1-houses-2026"
    assert metadata["houses"]["mapping_version"] == "houses_mapping.csv@phase-1-houses-2026"
    for endpoint, mapping in (("parties", "party_mapping.csv@phase-2-reference-data-2026"), ("constituencies", "constituencies_mapping.csv@phase-2-reference-data-2026")):
        assert metadata[endpoint]["ontology_version"] == "agents.owl.ttl+members.owl.ttl@phase-2-reference-data-2026"
        assert metadata[endpoint]["mapping_version"] == mapping


@pytest.mark.parametrize("endpoint_fixture", [("parties", "parties.json"), ("constituencies", "constituencies.json")])
def test_reference_cli_offline_ignores_configured_fuseki_endpoints(tmp_path, monkeypatch, endpoint_fixture):
    from argparse import Namespace
    from oireachtas_etl import cli
    endpoint, fixture_name = endpoint_fixture
    called = []
    class Loader:
        def __init__(self, *args, **kwargs): called.append("constructed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, f"verify_{endpoint}_competency", lambda client: called.append("competency"))
    monkeypatch.setenv("OIR_FUSEKI_GSP_URL", "http://local.test/data")
    monkeypatch.setenv("OIR_FUSEKI_SPARQL_URL", "http://local.test/query")
    args = Namespace(endpoint=endpoint, fixture=str(ROOT / "data/api_examples" / fixture_name), offline=True,
                     raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None,
                     fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert cli.run_reference(args) == 0
    assert called == []
