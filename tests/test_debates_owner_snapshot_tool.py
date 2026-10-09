from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import member_graph_iri, source_hash, transform_member
from oireachtas_etl.validation.committees import validate_committees
from oireachtas_etl.validation.houses import validate_houses
from oireachtas_etl.validation.members import validate_member
from tools.debates_owner_snapshot import inspect_owner_snapshot


ROOT = Path(__file__).resolve().parents[1]


def _seed_owner_state(path: Path) -> None:
    member_source = json.loads((ROOT / "data/api_examples/member.json").read_text())
    houses_source = json.loads((ROOT / "data/api_examples/houses.json").read_text())
    committee_source = json.loads((ROOT / "tests/fixtures/committee-owner.json").read_text())
    member_graph = transform_member(member_source)
    houses_graph = transform_houses(houses_source)
    committee_graph = transform_committees(committee_source)
    validate_member(member_source, member_graph)
    validate_houses(houses_source, houses_graph)
    validate_committees(committee_source, committee_graph)

    with CoreStateStore(path) as store:
        for endpoint, graph_iri, graph in (
            ("houses", HOUSES_GRAPH, houses_graph),
            ("committees", COMMITTEES_GRAPH, committee_graph),
        ):
            payload = ntriples(graph)
            digest = store.mark_endpoint_dirty(endpoint, graph_iri, payload)
            store.complete_endpoint_publication(endpoint, graph_iri, digest)

        member = member_source["member"]
        run_id = store.start_run(
            "members", "full_refresh", is_complete=False,
            parameters={"source": "test-fixture"},
        )
        resource_iri = member["uri"]
        graph_iri = member_graph_iri(member)
        digest_source = source_hash(member)
        store.observe_resource("members", resource_iri, graph_iri,
                               digest_source, run_id)
        payload = ntriples(member_graph)
        digest = store.mark_publication_dirty(
            "members", resource_iri, source_hash=digest_source,
            graph_iri=graph_iri, payload=payload, contract_version=3,
        )
        store.complete_publication(
            "members", resource_iri, source_hash=digest_source,
            graph_iri=graph_iri, payload_hash=digest, contract_version=3,
        )
        store.finish_run(run_id, success=True)


def test_owner_snapshot_inspection_is_read_only_and_matches_publisher_identity(tmp_path):
    state_db = tmp_path / "core.sqlite"
    _seed_owner_state(state_db)
    before = hashlib.sha256(state_db.read_bytes()).hexdigest()

    result = inspect_owner_snapshot(state_db)

    after = hashlib.sha256(state_db.read_bytes()).hexdigest()
    assert before == after
    assert result["owner_counts"] == {
        "members": 1, "house_terms": 4, "committees": 1,
    }
    assert result["owner_publications"]["member_clean_graph_count"] == 1
    assert result["owner_publications"]["member_payload_count"] == 1
    assert result["owner_publications"]["member_publication_run_ids"]
    assert result["operational_health"]["dirty_resources_by_endpoint"] == {}
    assert result["operational_health"]["unresolved_debates_quarantines"] == []
    assert result["operational_health"]["pending_provenance_incomplete"]
    assert result["remote_owner_graphs_verified"] is False
    assert result["expected_match"] is None

    pinned = inspect_owner_snapshot(
        state_db, expected_sha256=result["owner_snapshot_sha256"])
    assert pinned["expected_match"] is True
    mismatch = inspect_owner_snapshot(state_db, expected_sha256="0" * 64)
    assert mismatch["expected_match"] is False


def test_owner_snapshot_inspection_fails_closed_on_dirty_shared_graph(tmp_path):
    state_db = tmp_path / "core.sqlite"
    _seed_owner_state(state_db)
    with CoreStateStore(state_db) as store:
        metadata = store.endpoint_publication("houses")
        store.mark_endpoint_dirty(
            "houses", HOUSES_GRAPH, metadata["published_payload"] + "\n")

    with pytest.raises(ValueError, match="not in clean verified Core State"):
        inspect_owner_snapshot(state_db)
