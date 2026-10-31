"""Approved Bill Work metadata and contract-2 migration acceptance."""
import hashlib
import json
from argparse import Namespace
from pathlib import Path

import pytest
from owlrl import DeductiveClosure, OWLRL_Semantics
from pyshacl import validate
from rdflib import Graph, Literal, Namespace as RDFNamespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

from oireachtas_etl.serialization import nquads, ntriples
from oireachtas_etl.state import CoreStateStore, PROVENANCE_GRAPH_IRI
from oireachtas_etl.transforms.bills import (
    BILLS_PUBLICATION_CONTRACT, bill_graph_iri, source_hash, transform_bill_with_report)
from oireachtas_etl.transforms.common import ELIDL, OIR
from oireachtas_etl.validation.bills import validate_bill
from oireachtas_etl.validation.vocabulary import pinned_vocabulary_graphs
from tests._in_memory_fuseki import InMemoryFuseki

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
BILL = URIRef(RECORD["bill"]["uri"])
ELI = RDFNamespace("http://data.europa.eu/eli/ontology#")
REPLACEMENTS = {ELI.type_document: ELI.work_type, ELI.title: DCTERMS.title,
                ELI.title_alternative: DCTERMS.alternative, ELI.id_local: DCTERMS.identifier}


def legacy_graph(*, delivery_link=True):
    """Reconstruct the pinned Tranche 1 baseline, not a relaxed new golden."""
    graph, _ = transform_bill_with_report(RECORD)
    for old, new in REPLACEMENTS.items():
        for obj in list(graph.objects(BILL, new)):
            graph.remove((BILL, new, obj))
            graph.add((BILL, old, obj))
    graph.add((BILL, RDF.type, ELI.LegalResource))
    if not delivery_link:
        graph.remove((None, ELIDL.created_a_realization_of, BILL))
    return graph


def test_golden_delta_is_only_the_approved_work_metadata_correction():
    old = legacy_graph()
    # Pins the complete preceding golden, including every established identity.
    assert hashlib.sha256(nquads(old, bill_graph_iri(RECORD["bill"])).encode()).hexdigest() == (
        "f2378d0aaca83deda4e383ee815d3bc09312949cc9f044dcfd14841008efeba7")
    new, report = transform_bill_with_report(RECORD)
    removed = {(BILL, RDF.type, ELI.LegalResource)}
    removed.update((BILL, predicate, obj) for predicate in REPLACEMENTS
                   for obj in old.objects(BILL, predicate))
    added = {(BILL, REPLACEMENTS[predicate], obj)
             for _, predicate, obj in removed if predicate in REPLACEMENTS}
    assert set(old) - set(new) == removed
    assert set(new) - set(old) == added
    assert len(removed) == 7 and len(added) == 6
    assert set(old.subjects()) == set(new.subjects())
    assert set(old.objects(BILL, ELI.is_realized_by)) == set(new.objects(BILL, ELI.is_realized_by))
    assert validate_bill(RECORD, new) == report
    assert not list(new.triples((URIRef(RECORD["bill"]["act"]["uri"]), None, None)))


def test_pinned_eli_domains_and_bill_worktype_do_not_reclassify_bill():
    eli, elidl = pinned_vocabulary_graphs()
    assert (ELI.type_document, RDFS.domain, ELI.LegalResource) in eli
    assert (ELI.type_document, RDFS.range, ELI.ResourceType) in eli
    assert (ELI.work_type, RDFS.domain, ELI.Work) in eli
    assert (ELI.work_type, RDFS.range, ELI.WorkType) in eli
    for predicate in (ELI.title, ELI.title_alternative):
        assert (predicate, RDFS.domain, ELI.Expression) in eli
        assert (predicate, RDFS.range, RDFS.Literal) in eli
    domain = eli.value(ELI.id_local, RDFS.domain)
    assert set(eli.items(eli.value(domain, OWL.unionOf))) == {
        ELI.Format, ELI.LegalExpression, ELI.LegalResource}
    range_ = eli.value(ELI.id_local, RDFS.range)
    assert set(eli.items(eli.value(range_, OWL.unionOf))) == {XSD.anyURI, XSD.string}
    ontology = Graph().parse(ROOT / "ontology/legislation.owl.ttl")
    assert (OIR.Bill, RDF.type, ELI.WorkType) in ontology
    assert (OIR.Bill, SKOS.inScheme, ELI.WorkTypeTable) in ontology
    assert (OIR.Bill, SKOS.topConceptOf, ELI.WorkTypeTable) in ontology
    assert (OIR.Bill, RDF.type, ELI.ResourceType) not in ontology
    assert (OIR.Act, RDF.type, ELI.ResourceType) in ontology
    assert (OIR.Act, SKOS.inScheme, ELI.ResourceTypeTable) in ontology
    graph, _ = transform_bill_with_report(RECORD)
    graph += eli
    graph += elidl
    for path in (ROOT / "ontology").glob("*.owl.ttl"):
        graph.parse(path)
    DeductiveClosure(OWLRL_Semantics).expand(graph)
    assert (BILL, RDF.type, ELI.Work) in graph
    for forbidden in (ELI.LegalResource, ELI.Expression, ELI.LegalExpression, ELI.Format):
        assert (BILL, RDF.type, forbidden) not in graph


@pytest.mark.parametrize("predicate", list(REPLACEMENTS))
def test_legacy_metadata_on_bill_fails_python_shacl_and_postload(predicate):
    from oireachtas_etl.competency import verify_bill_competency

    graph, _ = transform_bill_with_report(RECORD)
    value = next(graph.objects(BILL, REPLACEMENTS[predicate]))
    graph.add((BILL, predicate, value))
    with pytest.raises(ValueError, match="obsolete ELI metadata"):
        validate_bill(RECORD, graph)
    shapes = ROOT / "src/oireachtas_etl/validation/resources/bills.ttl"
    assert not validate(graph, shacl_graph=str(shapes), inference="none")[0]
    client = InMemoryFuseki()
    name = bill_graph_iri(RECORD["bill"])
    client.replace(name, ntriples(graph), content_type="application/n-triples")
    with pytest.raises(ValueError, match="post-load Bill competency"):
        verify_bill_competency(client, name, str(BILL))


@pytest.mark.parametrize("rdf_type", [ELI.LegalResource, ELI.Expression, ELI.LegalExpression, ELI.Format])
def test_incompatible_bill_work_classification_fails_validation(rdf_type):
    graph, _ = transform_bill_with_report(RECORD)
    graph.add((BILL, RDF.type, rdf_type))
    with pytest.raises(ValueError, match="Bill Work must not be classified"):
        validate_bill(RECORD, graph)
    shapes = ROOT / "src/oireachtas_etl/validation/resources/bills.ttl"
    assert not validate(graph, shacl_graph=str(shapes), inference="none")[0]


@pytest.mark.parametrize("predicate", [DCTERMS.title, DCTERMS.alternative, DCTERMS.identifier, ELI.work_type])
def test_work_metadata_preserves_exact_values_and_language_tags(predicate):
    graph, _ = transform_bill_with_report(RECORD)
    value = next(graph.objects(BILL, predicate))
    graph.remove((BILL, predicate, value))
    with pytest.raises(ValueError, match="metadata must preserve"):
        validate_bill(RECORD, graph)
    if predicate in (DCTERMS.title, DCTERMS.alternative):
        graph.add((BILL, predicate, Literal(str(value), lang="fr")))
        with pytest.raises(ValueError, match="metadata must preserve"):
            validate_bill(RECORD, graph)


def test_no_bill_metadata_is_invented_on_expressions_and_null_titles_stay_absent():
    wrapper = json.loads(json.dumps(RECORD))
    for field in ("shortTitleEn", "shortTitleGa", "longTitleEn", "longTitleGa"):
        wrapper["bill"][field] = None
    graph, report = transform_bill_with_report(wrapper)
    assert not list(graph.objects(BILL, DCTERMS.title))
    assert not list(graph.objects(BILL, DCTERMS.alternative))
    assert validate_bill(wrapper, graph) == report
    original, _ = transform_bill_with_report(RECORD)
    expression = next(original.objects(BILL, ELI.is_realized_by))
    original.add((expression, DCTERMS.title, next(original.objects(BILL, DCTERMS.title))))
    with pytest.raises(ValueError, match="must not be distributed"):
        validate_bill(RECORD, original)


@pytest.mark.parametrize("delivery_link", [False, True])
@pytest.mark.parametrize("failure", [None, "put", "verification"])
def test_contract_upgrade_republishes_unchanged_source_replaces_old_triples_and_retries(
        tmp_path, monkeypatch, delivery_link, failure):
    from oireachtas_etl import cli

    assert BILLS_PUBLICATION_CONTRACT == 2
    graph_name = bill_graph_iri(RECORD["bill"])
    digest = source_hash(RECORD["bill"])
    database = tmp_path / "state.sqlite"
    old = legacy_graph(delivery_link=delivery_link)
    old_payload = ntriples(old)
    with CoreStateStore(database) as store:
        run = store.start_run("legislation", "full_refresh", is_complete=True, parameters={})
        store.observe_resource("legislation", str(BILL), graph_name, digest, run)
        old_hash = store.mark_publication_dirty(
            "legislation", str(BILL), source_hash=digest, graph_iri=graph_name,
            payload=old_payload, contract_version=1)
        store.complete_publication("legislation", str(BILL), source_hash=digest,
                                   graph_iri=graph_name, payload_hash=old_hash, contract_version=1)
        store.finish_run(run, success=True)
    remote = InMemoryFuseki()
    remote.replace(graph_name, old_payload, content_type="application/n-triples")
    # An unrelated Act owner's graph must not be touched by the Bill replacement.
    act = Graph()
    act.add((URIRef(RECORD["bill"]["act"]["uri"]), RDF.type, ELI.LegalResource))
    act.add((URIRef(RECORD["bill"]["act"]["uri"]), ELI.type_document, OIR.Act))
    act_name = "https://example.test/graph/act-owner"
    remote.replace(act_name, ntriples(act), content_type="application/n-triples")

    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, name, payload, **kwargs):
            if name == graph_name:
                with CoreStateStore(database) as store:
                    row = store.get_resource("legislation", str(BILL))
                assert row["publication_state"] == "dirty"
                assert row["contract_version"] == BILLS_PUBLICATION_CONTRACT
                assert row["pending_payload"] == payload
                if failure == "put":
                    raise RuntimeError("controlled PUT failure")
            remote.replace(name, payload, **kwargs)
            if name == graph_name and failure == "verification":
                remote.dataset.graph(URIRef(name)).add((BILL, RDF.type, ELI.LegalResource))

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: remote)
    fixture = tmp_path / "bill.json"
    fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}}, "results": [RECORD]}))
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"),
                     state_db=str(database), output_nq=None, output_ttl=None,
                     fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query")
    if failure:
        with pytest.raises((ValueError, RuntimeError), match="controlled PUT failure|post-load Bill"):
            cli.run_bills(args)
        with CoreStateStore(database) as store:
            dirty = store.get_resource("legislation", str(BILL))
        assert dirty["publication_state"] == "dirty"
        assert dirty["published_source_hash"] == dirty["pending_source_hash"] == digest
        assert dirty["published_payload"] == old_payload
        assert dirty["pending_payload"] != old_payload
        failure = None
    assert cli.run_bills(args) == 0
    expected, _ = transform_bill_with_report(RECORD)
    assert set(remote.construct_graph(graph_name)) == set(expected)
    assert set(remote.construct_graph(act_name)) == set(act)
    assert len(remote.construct_graph(PROVENANCE_GRAPH_IRI)) > 0
    with CoreStateStore(database) as store:
        clean = store.get_resource("legislation", str(BILL))
    assert clean["publication_state"] == "clean"
    assert clean["contract_version"] == BILLS_PUBLICATION_CONTRACT
    assert clean["observed_source_hash"] == clean["published_source_hash"] == digest
    assert clean["published_payload"] == ntriples(expected)
    assert clean["pending_payload"] is None
    before = len(remote.replacements)
    monkeypatch.setattr(cli, "transform_bill_with_report", lambda *_: pytest.fail("current unchanged Bill transformed"))
    assert cli.run_bills(args) == 0
    assert [name for name, *_ in remote.replacements[before:]] == [PROVENANCE_GRAPH_IRI]
