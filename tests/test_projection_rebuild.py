from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF

from oireachtas_etl.config import HOUSES_GRAPH
from oireachtas_etl.projection import (
    GraphPayload,
    ProjectionError,
    authoritative_graph_payloads,
    rebuild_empty_dataset,
    reconciliation_graph_payloads,
)
from oireachtas_etl.reconciliation import (
    WIKIDATA,
    ReconciliationStore,
    Resolution,
    external_graph_iri,
    links_graph,
)
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore, expected_graph_iri


def make_core_state(path: Path, *, dirty: bool = False) -> tuple[str, str, str]:
    local_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/restore-test"
    graph_iri = expected_graph_iri("members", local_iri)
    graph = Graph()
    graph.add((URIRef(local_iri), OWL.sameAs, URIRef("https://www.wikidata.org/entity/Q42")))
    clean_payload = ntriples(graph)
    with CoreStateStore(path) as store:
        run_id = store.start_run("members", "full_refresh", is_complete=True,
                                 parameters={"fixture": "restore-test"})
        first_hash = hashlib.sha256(b"source-v1").hexdigest()
        store.observe_resource("members", local_iri, graph_iri, first_hash, run_id)
        clean_hash = store.mark_publication_dirty(
            "members", local_iri, source_hash=first_hash, graph_iri=graph_iri,
            payload=clean_payload, contract_version=2)
        store.complete_publication(
            "members", local_iri, source_hash=first_hash, graph_iri=graph_iri,
            payload_hash=clean_hash, contract_version=2)
        store.finish_run(run_id, success=True)

        payload = clean_payload
        if dirty:
            dirty_run = store.start_run("members", "full_refresh", is_complete=True,
                                        parameters={"fixture": "interrupted-publication"})
            second_hash = hashlib.sha256(b"source-v2").hexdigest()
            store.observe_resource("members", local_iri, graph_iri, second_hash, dirty_run)
            changed = Graph()
            changed.add((URIRef(local_iri), OWL.sameAs,
                         URIRef("https://www.wikidata.org/entity/Q43")))
            payload = ntriples(changed)
            store.mark_publication_dirty(
                "members", local_iri, source_hash=second_hash, graph_iri=graph_iri,
                payload=payload, contract_version=2)
            store.finish_run(dirty_run, success=False, error="simulated PUT interruption")
    return local_iri, graph_iri, payload


def test_projection_uses_exact_clean_payload_from_core_state(tmp_path):
    state = tmp_path / "core.sqlite"
    local_iri, graph_iri, payload = make_core_state(state)

    graphs = authoritative_graph_payloads(state)

    assert len(graphs) == 1
    assert graphs[0].graph_iri == graph_iri
    assert graphs[0].payload == payload
    assert graphs[0].owner == "members"


def test_interrupted_publication_rebuilds_exact_pending_candidate(tmp_path):
    state = tmp_path / "core.sqlite"
    _local_iri, graph_iri, pending_payload = make_core_state(state, dirty=True)

    graphs = authoritative_graph_payloads(state)

    assert len(graphs) == 1
    assert graphs[0].graph_iri == graph_iri
    assert graphs[0].payload == pending_payload
    assert "Q43" in graphs[0].payload


def test_projection_includes_shared_graph_and_exact_dirty_shared_payload(tmp_path):
    state = tmp_path / "core.sqlite"
    house_iri = URIRef("https://data.oireachtas.ie/house/dail")
    house_class = URIRef("https://data.oireachtas.ie/ontology#House")
    title_predicate = URIRef("http://purl.org/dc/terms/title")

    def house_payload(title: str) -> str:
        graph = Graph()
        graph.add((house_iri, RDF.type, house_class))
        graph.add((house_iri, title_predicate, Literal(title)))
        return ntriples(graph)

    clean_payload = house_payload("Dáil Éireann")
    with CoreStateStore(state) as store:
        run_id = store.start_run("houses", "full_refresh", is_complete=True,
                                 parameters={"fixture": "shared-graph"})
        payload_hash = store.mark_endpoint_dirty(
            "houses", HOUSES_GRAPH, clean_payload, run_id=run_id)
        store.complete_endpoint_publication(
            "houses", HOUSES_GRAPH, payload_hash, publishing_run_id=run_id)
        store.finish_run(run_id, success=True)

    graphs = authoritative_graph_payloads(state)
    assert len(graphs) == 1
    assert graphs[0].graph_iri == HOUSES_GRAPH
    assert graphs[0].payload == clean_payload
    assert graphs[0].owner == "houses"

    pending_payload = house_payload("Dáil Éireann — pending")
    with CoreStateStore(state) as store:
        run_id = store.start_run("houses", "full_refresh", is_complete=True,
                                 parameters={"fixture": "interrupted-shared-graph"})
        store.mark_endpoint_dirty("houses", HOUSES_GRAPH, pending_payload, run_id=run_id)
        store.finish_run(run_id, success=False, error="simulated PUT interruption")

    graphs = authoritative_graph_payloads(state)
    assert len(graphs) == 1
    assert graphs[0].graph_iri == HOUSES_GRAPH
    assert graphs[0].payload == pending_payload
    assert "pending" in graphs[0].payload


def test_projection_fails_closed_on_corrupt_core_payload_hash(tmp_path):
    state = tmp_path / "core.sqlite"
    local_iri, _graph_iri, _payload = make_core_state(state)
    import sqlite3

    connection = sqlite3.connect(state)
    connection.execute(
        "UPDATE resource_state SET published_payload='not the saved payload' "
        "WHERE endpoint='members' AND resource_iri=?", (local_iri,))
    connection.commit()
    connection.close()

    with pytest.raises(ProjectionError, match="SHA-256"):
        authoritative_graph_payloads(state)


def test_projection_rebuild_rejects_nonempty_target_before_any_put():
    class NonemptyClient:
        def query(self, _query):
            return [{"triples": {"value": "1"}}]

    class RecordingLoader:
        def __init__(self):
            self.replacements = []

        def replace(self, *args, **kwargs):
            self.replacements.append((args, kwargs))

    loader = RecordingLoader()
    with pytest.raises(ProjectionError, match="not an empty Fuseki dataset"):
        rebuild_empty_dataset(
            [GraphPayload("https://example.test/graph", "", "fixture")],
            loader,
            NonemptyClient(),
        )
    assert loader.replacements == []


def test_external_graph_rebuild_uses_last_published_attempt_after_outage(tmp_path):
    root = Path(__file__).resolve().parents[1]
    member = json.loads((root / "data/api_examples/member.json").read_text())["member"]
    review = {"status": "accepted", "wikidata": "Q42"}
    resolution = Resolution(
        "accepted", "manual-review", {"decision": review, "memberCode": member["memberCode"]},
        wikidata=WIKIDATA + "Q42", wikipedia=None, dbpedia=None, review_applied=True)
    payload = ntriples(links_graph(member, resolution))
    external_db = tmp_path / "reconciliation.sqlite"
    store = ReconciliationStore(external_db)
    try:
        graph_iri = external_graph_iri(member)
        store.save_record(
            "member", member["uri"], member["memberCode"], "a" * 64, resolution,
            "review-v1", review, payload, graph_iri, dirty=True)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        store.record_publication_result(
            "member", member["uri"], payload_hash, "success")
        store.mark_record_published("member", member["uri"], payload_hash)

        # A later external lookup failure is recorded without clearing the
        # previously accepted external graph. Rebuild must find its exact
        # producing attempt, not infer a replacement or erase the graph.
        outage = Resolution("pending", "wikidata-p4690-outage",
                            {"reason": "lookup-error", "errors": ["offline"]},
                            enrichment_status="unresolved", enrichment_reason="lookup-error")
        store.save_record(
            "member", member["uri"], member["memberCode"], "a" * 64, outage,
            "review-v1", None, ntriples(Graph()), graph_iri, dirty=False)
        assert store.get_record("member", member["uri"])["state"] == "pending"
    finally:
        store.close()

    graphs = reconciliation_graph_payloads(external_db)

    assert len(graphs) == 1
    assert graphs[0].owner == "external:member"
    assert graphs[0].graph_iri == graph_iri
    assert graphs[0].payload == payload
    assert "owl#sameAs" in graphs[0].payload
    assert WIKIDATA + "Q42" in graphs[0].payload
