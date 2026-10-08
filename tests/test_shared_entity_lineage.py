from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, PROV, SKOS

from oireachtas_etl.provenance import (
    ETL, build_provenance_catalog, entity_version_iri,
    graph_version_iri, source_observation_iri, source_record_evidence_iri,
)
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import (
    CoreStateError, CoreStateStore, PROVENANCE_NAMESPACE, SHARED_GRAPHS,
    run_resource_iri,
)
from oireachtas_etl.transforms.common import MEMBERS


PARTIES_GRAPH = SHARED_GRAPHS["parties"]
COMMITTEES_GRAPH = SHARED_GRAPHS["committees"]
VERSIONS = {
    "etl_version": "0.1.0",
    "ontology_version": "members.owl.ttl@test-lineage",
    "mapping_version": "party_mapping.csv@test-lineage",
}


def _party_graph(*labels: tuple[str, str]) -> Graph:
    graph = Graph()
    for entity_iri, label in labels:
        entity = URIRef(entity_iri)
        graph.add((entity, RDF.type, MEMBERS.ParliamentaryMemberCollection))
        graph.add((entity, SKOS.prefLabel, Literal(label)))
    return graph


def _start_members_run(store: CoreStateStore, when: str) -> str:
    return store.start_run(
        "members", "full_refresh", is_complete=True,
        parameters={"source": "api", "api_url": "https://api.oireachtas.ie/v1/members"},
        versions=VERSIONS, started_at=when)


def _record_page(store: CoreStateStore, run_id: str, body: bytes, *,
                 observed_at: str, skip: int) -> dict:
    source_hash = hashlib.sha256(body).hexdigest()
    page_uri = f"file:///raw/members/page-{skip}.json"
    store.record_source_observation(
        "members", source_hash, observed_at, run_id=run_id,
        evidence_pointer=page_uri,
        source_url="https://api.oireachtas.ie/v1/members",
        request_parameters={"limit": 100, "skip": skip}, versions=VERSIONS)
    return {"source_hash": source_hash, "observed_at": observed_at,
            "evidence_pointer": page_uri + "#/results/0"}


def _publish_shared(store: CoreStateStore, run_id: str, graph: Graph,
                    lineages: dict[str, dict]) -> tuple[str, str]:
    payload = ntriples(graph)
    digest = store.mark_endpoint_dirty(
        "parties", PARTIES_GRAPH, payload, run_id=run_id,
        coverage_authoritative=True, entity_lineage=lineages)
    store.complete_endpoint_publication(
        "parties", PARTIES_GRAPH, digest, publishing_run_id=run_id)
    return payload, digest


def test_multi_page_entity_versions_and_retained_descriptions_keep_exact_lineage(tmp_path):
    database = tmp_path / "core.sqlite"
    party_a = "https://data.oireachtas.ie/ie/oireachtas/party/dail/1/Party-A"
    party_b = "https://data.oireachtas.ie/ie/oireachtas/party/dail/1/Party-B"
    page_one = json.dumps({"results": [{"party": {"uri": party_a, "partyCode": "A"}}]},
                          sort_keys=True).encode()
    page_two = json.dumps({"results": [
        {"party": {"uri": party_a, "partyCode": "A"}},
        {"party": {"uri": party_b, "partyCode": "B"}},
    ]}, sort_keys=True).encode()
    page_three = json.dumps({"results": [{"party": {"uri": party_a, "partyCode": "A"}}]},
                            sort_keys=True).encode()

    with CoreStateStore(database) as store:
        first_run = _start_members_run(store, "2026-10-07T10:00:00Z")
        evidence_a_1 = _record_page(
            store, first_run, page_one, observed_at="2026-10-07T10:00:01Z", skip=0)
        evidence_a_2 = _record_page(
            store, first_run, page_two, observed_at="2026-10-07T10:00:02Z", skip=100)
        evidence_b_2 = {**evidence_a_2,
                        "evidence_pointer": "file:///raw/members/page-100.json#/results/1"}
        graph_v1 = _party_graph((party_a, "Party A"), (party_b, "Party B"))
        payload_v1, hash_v1 = _publish_shared(store, first_run, graph_v1, {
            party_a: {"sources": [evidence_a_1, evidence_a_2],
                     "prior_payload_hash": None},
            party_b: {"sources": [evidence_b_2], "prior_payload_hash": None},
        })
        store.finish_run(first_run, success=True,
                         completed_at="2026-10-07T10:00:03Z")

        second_run = _start_members_run(store, "2026-10-07T11:00:00Z")
        evidence_a_3 = _record_page(
            store, second_run, page_three, observed_at="2026-10-07T11:00:01Z", skip=0)
        # Party B is carried forward from the verified prior graph, not sourced
        # from the unrelated current page that only describes Party A.
        graph_v2 = _party_graph((party_a, "Party A Updated"), (party_b, "Party B"))
        payload_v2, hash_v2 = _publish_shared(store, second_run, graph_v2, {
            party_a: {"sources": [evidence_a_3], "prior_payload_hash": None},
            party_b: {"sources": [], "prior_payload_hash": hash_v1},
        })
        assert hash_v2 != hash_v1
        store.finish_run(second_run, success=True,
                         completed_at="2026-10-07T11:00:02Z")

        catalog = build_provenance_catalog(
            store, require_source_run_ids=(first_run, second_run))
        run2_iri = URIRef(run_resource_iri(second_run))
        graph_v2_iri = URIRef(graph_version_iri(PARTIES_GRAPH, hash_v2))
        entity_a_v2 = URIRef(entity_version_iri(PARTIES_GRAPH, hash_v2, party_a))
        entity_b_v2 = URIRef(entity_version_iri(PARTIES_GRAPH, hash_v2, party_b))
        entity_b_v1 = URIRef(entity_version_iri(PARTIES_GRAPH, hash_v1, party_b))

        # The owner graph belongs to Parties, but the actual publisher is the
        # active Members run. Both graph and entity snapshots retain that fact.
        assert (graph_v2_iri, PROV.wasGeneratedBy, run2_iri) in catalog
        assert (entity_a_v2, PROV.wasGeneratedBy, run2_iri) in catalog
        assert (entity_b_v2, PROV.wasGeneratedBy, run2_iri) in catalog
        assert (run2_iri, ETL.endpoint, Literal("members")) in catalog
        assert (graph_v2_iri, ETL.endpoint, Literal("parties")) in catalog

        page1_iri = URIRef(source_observation_iri(
            evidence_a_1["source_hash"], evidence_a_1["observed_at"]))
        page2_iri = URIRef(source_observation_iri(
            evidence_a_2["source_hash"], evidence_a_2["observed_at"]))
        page3_iri = URIRef(source_observation_iri(
            evidence_a_3["source_hash"], evidence_a_3["observed_at"]))
        assert (entity_a_v2, PROV.wasDerivedFrom, page3_iri) in catalog
        assert (graph_v2_iri, PROV.wasDerivedFrom, page3_iri) in catalog
        assert (entity_b_v2, PROV.wasDerivedFrom, entity_b_v1) in catalog
        assert (entity_b_v2, PROV.wasDerivedFrom, page3_iri) not in catalog
        assert (graph_v2_iri, PROV.wasDerivedFrom, entity_b_v1) in catalog

        page1_record = URIRef(source_record_evidence_iri(
            evidence_a_1["source_hash"], evidence_a_1["observed_at"],
            evidence_a_1["evidence_pointer"]))
        page2_record = URIRef(source_record_evidence_iri(
            evidence_a_2["source_hash"], evidence_a_2["observed_at"],
            "file:///raw/members/page-100.json#/results/0"))
        assert (page1_record, ETL.evidencePointer,
                Literal(evidence_a_1["evidence_pointer"])) in catalog
        assert (page2_record, ETL.evidencePointer,
                Literal("file:///raw/members/page-100.json#/results/0")) in catalog
        assert (entity_b_v2, PROV.wasDerivedFrom, page1_iri) not in catalog
        # Page 2 contains a duplicate A followed by B, so the association keeps
        # the exact second-page pointer as well as the first-page observation.
        entity_a_v1 = URIRef(entity_version_iri(PARTIES_GRAPH, hash_v1, party_a))
        assert (entity_a_v1, PROV.wasDerivedFrom, page1_iri) in catalog
        assert (entity_a_v1, PROV.wasDerivedFrom, page2_iri) in catalog


def test_v7_to_v8_keeps_dirty_candidate_and_legacy_gap_without_fabricating_lineage(tmp_path):
    database = tmp_path / "core-v7.sqlite"
    party = "https://data.oireachtas.ie/ie/oireachtas/party/dail/1/Legacy"
    payload = ntriples(_party_graph((party, "Legacy")))
    with CoreStateStore(database) as store:
        digest = store.mark_endpoint_dirty("parties", PARTIES_GRAPH, payload)
        before = store.connection.execute(
            "SELECT publication_metadata_json FROM endpoint_state WHERE endpoint='parties'"
        ).fetchone()[0]

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE entity_version_source")
        connection.execute("DROP TABLE entity_version")
        connection.execute("PRAGMA user_version=7")

    with CoreStateStore(database) as migrated:
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        after = migrated.connection.execute(
            "SELECT publication_metadata_json FROM endpoint_state WHERE endpoint='parties'"
        ).fetchone()[0]
        assert after == before
        dirty = migrated.endpoint_publication("parties")
        assert dirty["publication_state"] == "dirty"
        assert dirty["pending_payload"] == payload
        assert dirty["pending_payload_hash"] == digest
        assert dirty.get("pending_entity_lineage") is None
        assert migrated.entity_versions() == []
        assert migrated.provenance_incomplete_records() == []

        # Resolve only the already durable graph candidate as a legacy replay;
        # migration must report, not invent, missing source/entity evidence.
        migrated.complete_endpoint_publication("parties", PARTIES_GRAPH, digest)
        gaps = migrated.provenance_incomplete_records()
        assert len(gaps) == 1
        assert gaps[0]["reason"] == "legacy_shared_entity_lineage_unavailable"
        assert migrated.entity_versions() == []
        assert migrated.entity_version_sources() == []
        assert migrated.connection.execute(
            "SELECT COUNT(*) FROM source_observation").fetchone()[0] == 0


def test_v7_migration_reopens_resolved_gap_when_clean_shared_lineage_is_missing(tmp_path):
    database = tmp_path / "core-v7-resolved.sqlite"
    party = "https://data.oireachtas.ie/ie/oireachtas/party/dail/1/PreviouslyResolved"
    payload = ntriples(_party_graph((party, "Previously resolved")))
    with CoreStateStore(database) as store:
        digest = store.mark_endpoint_dirty("parties", PARTIES_GRAPH, payload)
        store.complete_endpoint_publication("parties", PARTIES_GRAPH, digest)
        gaps = store.provenance_incomplete_records()
        assert len(gaps) == 1 and gaps[0]["status"] == "pending"
        store.connection.execute(
            "UPDATE provenance_incomplete SET status='resolved',resolved_at=? "
            "WHERE endpoint='parties' AND graph_iri=?",
            ("2026-10-07T12:00:00+00:00", PARTIES_GRAPH))
        resolved = store.provenance_incomplete_records(include_resolved=True)
        assert len(resolved) == 1 and resolved[0]["status"] == "resolved"

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE entity_version_source")
        connection.execute("DROP TABLE entity_version")
        connection.execute("PRAGMA user_version=7")

    with CoreStateStore(database) as migrated:
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        gaps = migrated.provenance_incomplete_records(include_resolved=True)
        assert len(gaps) == 1
        assert gaps[0]["status"] == "pending"
        assert gaps[0]["reason"] == "legacy_shared_entity_lineage_unavailable"
        assert gaps[0]["resolved_at"] is None
        assert gaps[0]["resolution_run_id"] is None
        assert migrated.entity_versions() == []
        assert migrated.entity_version_sources() == []
        assert migrated.connection.execute(
            "SELECT COUNT(*) FROM source_observation").fetchone()[0] == 0


def test_shared_entity_publication_rejects_missing_exact_record_attribution(tmp_path):
    database = tmp_path / "core.sqlite"
    party = "https://data.oireachtas.ie/ie/oireachtas/party/dail/1/Unproven"
    graph = _party_graph((party, "Unproven"))
    with CoreStateStore(database) as store:
        run_id = _start_members_run(store, "2026-10-07T12:00:00Z")
        with pytest.raises(CoreStateError, match="no exact source record"):
            store.mark_endpoint_dirty(
                "parties", PARTIES_GRAPH, ntriples(graph), run_id=run_id,
                entity_lineage={party: {"sources": [], "prior_payload_hash": None}})
        assert store.endpoint_publication("parties") is None
        assert store.provenance_events(event_type="graph_published") == []


def test_empty_committee_publication_requires_preserved_members_page_before_staging(tmp_path):
    with CoreStateStore(tmp_path / "core.sqlite") as store:
        members_run = _start_members_run(store, "2026-10-07T13:00:00Z")
        with pytest.raises(CoreStateError, match="explicit source lineage"):
            store.mark_endpoint_dirty(
                "committees", COMMITTEES_GRAPH, "",
                run_id=members_run, member_source_run_id=members_run)
        with pytest.raises(CoreStateError, match="preserved Members capture source observations"):
            store.mark_endpoint_dirty(
                "committees", COMMITTEES_GRAPH, "",
                run_id=members_run, member_source_run_id=members_run,
                entity_lineage={})
        assert store.endpoint_publication("committees") is None
        assert store.provenance_events(event_type="graph_published") == []
