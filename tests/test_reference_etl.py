import json
from argparse import Namespace
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from oireachtas_etl.competency import CONSTITUENCIES_EXPECTED, PARTIES_EXPECTED, QUERIES
from oireachtas_etl.config import CONSTITUENCIES_GRAPH, PARTIES_GRAPH
from oireachtas_etl.serialization import nquads, ntriples
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
    assert len(graph) == 55
    assert set(graph) == set(Graph().parse(ROOT / "tests/expected/parties.ttl"))
    assert (independent, RDF.type, MEMBERS.ParliamentaryMemberCollection) in graph
    assert (independent, RDF.type, MEMBERS.IndependentMemberCollection) in graph
    assert (independent, RDF.type, MEMBERS.ParliamentaryParty) not in graph
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


def test_independent_cannot_be_party_or_same_as_enduring_external_party():
    graph = transform_parties(PARTIES)
    independent = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent")
    graph.add((independent, RDF.type, MEMBERS.ParliamentaryParty))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_parties(PARTIES, graph)
    graph = transform_parties(PARTIES)
    graph.add((independent, URIRef("http://www.w3.org/2002/07/owl#sameAs"), URIRef("https://example.test/enduring-party")))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_parties(PARTIES, graph)


def test_authoritative_party_graph_forbids_prov_specialization_of():
    from rdflib import Namespace
    from oireachtas_etl.validation.parties import validate_quality, validate_shacl

    party = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Fine_Gael")
    graph = transform_parties(PARTIES)
    graph.add((party, Namespace("http://www.w3.org/ns/prov#").specializationOf,
               URIRef("https://example.test/enduring-party")))

    with pytest.raises(ValueError, match="SHACL validation failed"):
        validate_shacl(graph)
    with pytest.raises(ValueError, match="quality checks failed"):
        validate_quality(graph)


def test_synthetic_independent_party_uses_term_scoped_collection_and_fails_closed():
    record = {
        "party": {
            "uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/Independent",
            "partyCode": "Independent",
            "showAs": "Independent",
        },
        "house": {
            "uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35",
            "houseNo": "35",
            "houseCode": "dail",
        },
    }
    subject = URIRef(record["party"]["uri"])
    graph = transform_parties([record])
    validate_parties([record], graph)
    assert (subject, RDF.type, MEMBERS.ParliamentaryMemberCollection) in graph
    assert (subject, RDF.type, MEMBERS.IndependentMemberCollection) in graph
    assert (subject, MEMBERS.activeDuringTerm, URIRef(record["house"]["uri"])) in graph

    graph.add((subject, RDF.type, MEMBERS.ParliamentaryParty))
    with pytest.raises(ValueError, match="source-to-RDF correspondence failed: unexpected"):
        validate_parties([record], graph)


def test_parliamentary_collection_ontology_replaces_legacy_party_model():
    from rdflib import Namespace, RDFS
    from rdflib.namespace import FOAF

    ontology = Graph().parse(ROOT / "ontology/members.owl.ttl", format="turtle")
    members = Namespace("https://data.oireachtas.ie/ontology/members#")
    assert (members.ParliamentaryMemberCollection, RDFS.subClassOf, FOAF.Group) in ontology
    assert (members.ParliamentaryParty, RDFS.subClassOf, members.ParliamentaryMemberCollection) in ontology
    assert (members.IndependentMemberCollection, RDFS.subClassOf, members.ParliamentaryMemberCollection) in ontology
    assert (members.ParliamentaryGroup, RDFS.subClassOf, members.ParliamentaryMemberCollection) in ontology
    assert (members.TechnicalGroup, RDFS.subClassOf, members.ParliamentaryGroup) in ontology
    assert (members.ParliamentaryParty, RDFS.subClassOf, members.ParliamentaryGroup) not in ontology
    assert (members.recognisedAsParty, RDFS.domain, members.ParliamentaryParty) in ontology
    assert not list(ontology.objects(members.recognisedAsParty, RDFS.range))
    assert (members.isPartyMembershipOf, RDFS.range, members.ParliamentaryParty) in ontology
    assert (members.isPartyMembershipOf, RDFS.subPropertyOf, members.memberOfCollection) in ontology
    assert (members.PartyMembership, RDFS.subClassOf, members.ParliamentaryCollectionMembership) in ontology
    assert (members.ParliamentaryCollectionMembership, RDFS.subClassOf, members.MembersMembership) in ontology
    assert not list(ontology.subjects(RDF.type, members.ParliamentaryGroup))
    assert not list(ontology.subjects(RDF.type, members.TechnicalGroup))

    retired = (
        members.PartyGrouping, members.Party, members.Independent,
        members.PartyInGovernment, members.PartyInOpposition, members.PartiesMembership,
        members.hasPartiesMembership, members.isPartyIn, members.isWhipFor,
    )
    for term in retired:
        assert not list(ontology.triples((term, None, None)))
        assert not list(ontology.triples((None, None, term)))


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
    args = Namespace(endpoint="constituencies", fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(tmp_path / "state.sqlite"), output_ttl=None, output_nq=None, fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query", reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"))
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
    args = Namespace(endpoint=endpoint, fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(tmp_path / "state.sqlite"), output_ttl=None, output_nq=None, fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query", reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"))
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
        assert metadata[endpoint]["ontology_version"] == "agents.owl.ttl+members.owl.ttl@reference-coverage-2026"
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
    monkeypatch.setattr(cli, "verify_core_graph", lambda client, graph_iri, payload: called.append("verified"))
    monkeypatch.setenv("OIR_FUSEKI_GSP_URL", "http://local.test/data")
    monkeypatch.setenv("OIR_FUSEKI_SPARQL_URL", "http://local.test/query")
    args = Namespace(endpoint=endpoint, fixture=str(ROOT / "data/api_examples" / fixture_name), offline=True,
                     raw_dir=str(tmp_path / "raw"), output_ttl=None, output_nq=None,
                     fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert cli.run_reference(args) == 0
    assert called == []


def test_online_fixture_owner_run_cannot_replace_authoritative_shared_graph(
        tmp_path, monkeypatch):
    from argparse import Namespace
    from oireachtas_etl import cli
    from oireachtas_etl.state import CoreStateStore, PROVENANCE_GRAPH_IRI
    from tests._in_memory_fuseki import InMemoryFuseki

    fuseki = InMemoryFuseki()
    authoritative_payload = ntriples(transform_parties(PARTIES))
    fuseki.replace(PARTIES_GRAPH, authoritative_payload,
                   content_type="application/n-triples")
    fuseki.replacements.clear()

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", lambda *args, **kwargs: fuseki)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: fuseki)
    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        digest = store.mark_endpoint_dirty(
            "parties", PARTIES_GRAPH, authoritative_payload,
            coverage_authoritative=True)
        store.complete_endpoint_publication(
            "parties", PARTIES_GRAPH, digest, coverage_authoritative=True)
    args = Namespace(
        endpoint="parties", fixture=str(ROOT / "data/api_examples/parties.json"),
        offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(database),
        output_ttl=None, output_nq=None, coverage_report=None,
        fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query",
        reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"),
        registry_file=None,
    )
    assert cli.run_reference(args) == 0
    assert [graph_iri for graph_iri, _payload, _content_type
            in fuseki.replacements] == [PROVENANCE_GRAPH_IRI]
    assert set(fuseki.construct_graph(PARTIES_GRAPH)) == set(transform_parties(PARTIES))
    assert len(fuseki.construct_graph(PROVENANCE_GRAPH_IRI)) > 0
    assert any(f"GRAPH <{PROVENANCE_GRAPH_IRI}>" in query for query in fuseki.queries)
    with CoreStateStore(database) as store:
        publication = store.endpoint_publication("parties")
        assert publication["coverage_authoritative"] is True
        assert publication["publication_state"] == "clean"
        assert publication["published_payload"] == authoritative_payload
        assert store.last_successful_complete_run("parties") is None


def test_committee_fixture_run_is_recorded_as_non_authoritative(tmp_path):
    from oireachtas_etl.cli import main
    from oireachtas_etl.state import CoreStateStore

    database = tmp_path / "core.sqlite"
    assert main([
        "run", "committees", "--fixture",
        str(ROOT / "tests/fixtures/committee-owner.json"),
        "--state-db", str(database), "--raw-dir", str(tmp_path / "raw"),
    ]) == 0
    with CoreStateStore(database) as store:
        assert store.last_successful_complete_run("committees") is None
        recent = store.connection.execute(
            "SELECT parameters_json FROM etl_run WHERE endpoint='committees'").fetchone()
        assert json.loads(recent[0])["source"] == "fixture"


def test_committee_authoritative_run_records_its_exact_member_capture(tmp_path):
    from argparse import Namespace
    from oireachtas_etl import cli
    from oireachtas_etl.state import CoreStateStore

    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        members_run = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api", "api_url": "https://api.oireachtas.ie/v1/members"})
        store.finish_run(members_run, success=True)

    args = Namespace(endpoint="committees", fixture=None, offline=False,
                      state_db=str(database), registry_file=None)
    assert cli._run_shared(args, "committees",
                           lambda _args, _store, _run_id: 0) == 0
    with CoreStateStore(database) as store:
        committee_run = store.last_successful_complete_run("committees")
        assert committee_run["parameters"]["source"] == "members"
        assert committee_run["parameters"]["source_run_id"] == members_run


@pytest.mark.parametrize("empty_committees", [False, True])
def test_online_committee_path_publishes_and_verifies_shared_owner_graphs(
        tmp_path, monkeypatch, capsys, empty_committees):
    import hashlib
    from datetime import datetime
    from argparse import Namespace
    from oireachtas_etl import cli
    from oireachtas_etl.config import COMMITTEES_GRAPH
    from oireachtas_etl.state import CoreStateStore
    from oireachtas_etl.raw import persist_raw
    from tests._in_memory_fuseki import InMemoryFuseki

    member_record = json.loads((ROOT / "data/api_examples/member.json").read_text())
    if empty_committees:
        for wrapper in member_record["member"]["memberships"]:
            wrapper["membership"]["committees"] = []
    closure_queries = []
    fuseki = InMemoryFuseki()

    class Client:
        def query(self, query):
            if "SELECT DISTINCT ?kind ?source ?target" in query:
                closure_queries.append(query)
            return fuseki.query(query)

        def construct_graph(self, graph_iri):
            return fuseki.construct_graph(graph_iri)

    class Loader:
        def replace(self, graph_iri, payload, **kwargs):
            fuseki.replace(graph_iri, payload, **kwargs)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader",
                        lambda *args, **kwargs: Loader())
    monkeypatch.setattr(cli, "FusekiSparqlClient",
                        lambda *args, **kwargs: Client())
    database = tmp_path / "core.sqlite"
    raw_root = tmp_path / "raw"
    api_url = "https://api.oireachtas.ie/v1/members"
    versions = {"etl_version": "0.1.0", "ontology_version": "agents.owl.ttl@test",
                "mapping_version": "member_mapping.csv@test"}
    with CoreStateStore(database) as store:
        member_run = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api", "api_url": api_url, "limit": 100},
            versions=versions, started_at="2026-10-01T00:00:00+00:00")
        body = json.dumps({"head": {"counts": {"memberCount": 1}},
                           "results": [member_record]}, sort_keys=True).encode()
        retrieved_at = datetime.fromisoformat("2026-10-01T00:00:00+00:00")
        page_path, _meta_path = persist_raw(
            root=raw_root, endpoint=api_url, params={"skip": 0, "limit": 100},
            body=body, status=200, retrieved_at=retrieved_at,
            ontology_version=versions["ontology_version"],
            mapping_version=versions["mapping_version"], endpoint_name="members",
            extraction_id=member_run)
        store.record_source_observation(
            "members", hashlib.sha256(body).hexdigest(), retrieved_at.isoformat(),
            run_id=member_run, evidence_pointer=page_path.resolve().as_uri(),
            source_url=api_url, request_parameters={"skip": 0, "limit": 100},
            versions=versions)
        store.finish_run(member_run, success=True)
        committee_run = store.start_run(
            "committees", "full_refresh", is_complete=True,
            parameters={"source": "members", "source_run_id": member_run},
            versions=versions, started_at="2026-10-01T00:01:00+00:00")
        args = Namespace(
            fixture=None, offline=False, raw_dir=str(raw_root),
            output_ttl=None, output_nq=None, coverage_report=None,
            fuseki_gsp_url="http://local.test/data",
            fuseki_sparql_url="http://local.test/query",
        )
        assert cli._run_committees_impl(args, store, committee_run) == 0
        publication = store.endpoint_publication("committees")
        assert publication["publication_state"] == "clean"
        assert publication["coverage_authoritative"] is True
        assert publication["member_source_run_id"] == member_run
        from oireachtas_etl.provenance import build_provenance_catalog
        from oireachtas_etl.provenance import source_observation_iri
        from oireachtas_etl.state import run_resource_iri
        from rdflib import URIRef
        from rdflib.namespace import PROV
        catalog = build_provenance_catalog(
            store, require_source_run_ids=(committee_run,))
        committee_graph_version = URIRef(
            "https://data.oireachtas.ie/graph/committees#sha256="
            + publication["published_payload_hash"])
        assert (committee_graph_version, PROV.wasGeneratedBy,
                URIRef(run_resource_iri(committee_run))) in catalog
        if empty_committees:
            assert publication["published_payload"] == ""
            committee_event = next(
                event for event in store.provenance_events(
                    event_type="graph_published", run_id=committee_run)
                if event["endpoint"] == "committees")
            assert committee_event["details"]["member_source_run_id"] == member_run
            member_sources = store.connection.execute(
                "SELECT source_hash,observed_at FROM source_observation "
                "WHERE endpoint='members' AND run_id=? ORDER BY observed_at,source_hash",
                (member_run,),
            ).fetchall()
            expected_sources = {
                source_observation_iri(row["source_hash"], row["observed_at"])
                for row in member_sources
            }
            assert expected_sources
            assert set(catalog.objects(
                committee_graph_version, PROV.wasDerivedFrom)) == expected_sources
            assert store.connection.execute(
                "SELECT COUNT(*) FROM source_observation "
                "WHERE endpoint='committees' AND run_id=?", (committee_run,)
            ).fetchone()[0] == 0
    assert any(graph_iri == COMMITTEES_GRAPH for graph_iri, _payload, _content_type
               in fuseki.replacements)
    if empty_committees:
        assert [(graph_iri, payload) for graph_iri, payload, _content_type
                in fuseki.replacements if graph_iri == COMMITTEES_GRAPH] == [
                    (COMMITTEES_GRAPH, "")]
    assert len(closure_queries) == 5
    report = json.loads(capsys.readouterr().out)
    assert report["published_graphs"] == 3
