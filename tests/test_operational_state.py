from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from oireachtas_etl.state import (
    PROVENANCE_GRAPH_IRI,
    CoreStateError,
    CoreStateStore,
    catalog_publication_boundary,
    run_resource_iri,
)
from oireachtas_etl.provenance import build_provenance_catalog, validate_provenance_catalog
from oireachtas_etl.transforms.members import member_graph_iri


ROOT = Path(__file__).resolve().parents[1]
MEMBER = json.loads((ROOT / "data/api_examples/member.json").read_text())["member"]
VERSIONS = {
    "etl_version": "0.6.0",
    "ontology_version": "2026-10-07",
    "mapping_version": "2026-10-07",
}


def _v5_database(path: Path) -> tuple[str, str, str]:
    """Create the Phase 5 layout with a dirty Debate and endpoint cursor."""
    debate_iri = "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-01-01"
    debate_graph = "https://data.oireachtas.ie/graph/debate/dail/2026-01-01"
    payload = "<https://example.test/debate> <https://example.test/p> <https://example.test/o> .\n"
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    with sqlite3.connect(path) as connection:
        connection.executescript("""
          CREATE TABLE core_metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE etl_run (
            run_id TEXT PRIMARY KEY,
            endpoint TEXT NOT NULL,
            run_kind TEXT NOT NULL,
            is_complete INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            error TEXT,
            parameters_json TEXT NOT NULL);
          CREATE TABLE endpoint_state (
            endpoint TEXT PRIMARY KEY,last_successful_run_id TEXT,
            last_successful_complete_run_id TEXT,incremental_cursor TEXT,
            publication_metadata_json TEXT,updated_at TEXT NOT NULL);
          CREATE TABLE resource_state (
            endpoint TEXT NOT NULL,resource_iri TEXT NOT NULL,graph_iri TEXT NOT NULL,
            observed_source_hash TEXT,published_source_hash TEXT,published_payload_hash TEXT,
            published_payload TEXT,last_seen_at TEXT,last_seen_run_id TEXT,last_published_at TEXT,
            last_missing_run_id TEXT,last_missing_at TEXT,
            missing_scan_count INTEGER NOT NULL DEFAULT 0,
            publication_state TEXT NOT NULL,pending_source_hash TEXT,pending_graph_iri TEXT,
            pending_payload TEXT,pending_payload_hash TEXT,source_presence TEXT NOT NULL DEFAULT 'present',
            contract_version INTEGER,raw_source_path TEXT,source_url TEXT,expression_iri TEXT,
            published_resolver_version TEXT,pending_resolver_version TEXT,
            published_owner_snapshot_hash TEXT,pending_owner_snapshot_hash TEXT,
            published_reference_report_path TEXT,published_reference_report_hash TEXT,
            pending_reference_report_path TEXT,pending_reference_report_hash TEXT,
            PRIMARY KEY(endpoint,resource_iri));
          PRAGMA user_version=5;
        """)
        connection.execute("""INSERT INTO etl_run VALUES
          ('prior-authoritative','legislation','full_refresh',1,
           '2026-09-01T00:00:00+00:00','2026-09-01T00:00:01+00:00',
           'succeeded',NULL,'{"source":"api"}')""")
        connection.execute("""INSERT INTO endpoint_state VALUES
          ('legislation','prior-authoritative','prior-authoritative',
           '2026-09-01T00:00:00+00:00',NULL,'2026-09-01T00:00:01+00:00')""")
        connection.execute("""INSERT INTO resource_state (
          endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
          published_payload_hash,published_payload,last_seen_at,last_seen_run_id,last_published_at,
          publication_state,pending_source_hash,pending_graph_iri,pending_payload,
          pending_payload_hash,source_presence,contract_version,raw_source_path,source_url,
          expression_iri,pending_resolver_version,pending_owner_snapshot_hash,
          pending_reference_report_path,pending_reference_report_hash)
          VALUES ('debates',?,?,?,?,?,?,?,?,?,'dirty',?,?,?,?, 'present',3,
                  '/immutable/raw/debates.xml','https://source.test/main.xml',
                  'https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-01-01#expression',
                  'resolver-v2','owner-hash','/immutable/report.json','report-hash')""",
          (debate_iri, debate_graph, "a" * 64, "b" * 64, "c" * 64, "published payload",
           "2026-09-01T00:00:00+00:00", "debate-run", "2026-08-31T23:00:00+00:00",
           "d" * 64, debate_graph, payload, payload_hash))
    return debate_iri, debate_graph, payload_hash


def test_schema_v5_migration_preserves_cursor_authority_and_dirty_debates(tmp_path):
    database = tmp_path / "phase5.sqlite"
    debate_iri, debate_graph, payload_hash = _v5_database(database)

    with CoreStateStore(database) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        assert store.catalog_publication() is None
        assert store.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='catalog_publication_state'"
        ).fetchone() is not None
        assert store.incremental_cursor() == "2026-09-01T00:00:00+00:00"
        assert store.last_successful_complete_run("legislation")["run_id"] == "prior-authoritative"
        debate = store.get_resource("debates", debate_iri)
        assert debate["graph_iri"] == debate_graph
        assert debate["publication_state"] == "dirty"
        assert debate["pending_source_hash"] == "d" * 64
        assert debate["pending_graph_iri"] == debate_graph
        assert debate["pending_payload_hash"] == payload_hash
        assert debate["pending_payload"].startswith("<https://example.test/debate>")
        assert debate["raw_source_path"] == "/immutable/raw/debates.xml"
        migrated = store.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id='prior-authoritative'"
        ).fetchone()
        assert (migrated["status"], migrated["outcome"]) == ("succeeded", "success")

    with CoreStateStore(database) as reopened:
        assert reopened.get_resource("debates", debate_iri)["pending_payload_hash"] == payload_hash
        assert reopened.incremental_cursor() == "2026-09-01T00:00:00+00:00"


def test_schema_v5_migration_rolls_back_if_run_registry_copy_fails(tmp_path):
    database = tmp_path / "broken-v5.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
          CREATE TABLE core_metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE etl_run (
            run_id TEXT PRIMARY KEY,endpoint TEXT NOT NULL,run_kind TEXT NOT NULL,
            is_complete INTEGER NOT NULL,started_at TEXT NOT NULL,completed_at TEXT,
            status TEXT NOT NULL,error TEXT);
          PRAGMA user_version=5;
        """)

    with pytest.raises(sqlite3.OperationalError, match="parameters_json"):
        CoreStateStore(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "etl_run" in tables and "etl_run_v5" not in tables
    assert "catalog_publication_state" not in tables


def test_catalog_publication_dirty_payload_reopens_and_retries_without_recursion(tmp_path):
    database = tmp_path / "state.sqlite"
    payload = "<https://example.test/run/1> <https://example.test/p> <https://example.test/o> .\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    other_payload = payload + "# different catalog projection\n"

    with CoreStateStore(database) as store:
        boundary = catalog_publication_boundary(store)
        assert boundary.mark_dirty(PROVENANCE_GRAPH_IRI, payload) == digest
        dirty = store.catalog_publication()
        assert dirty["publication_state"] == "dirty"
        assert dirty["pending_payload_hash"] == digest
        assert dirty["pending_payload"] == payload
        assert dirty["published_payload"] is None
        assert store.provenance_events() == []
        assert store.graph_versions() == []
        with pytest.raises(CoreStateError, match="different durable dirty payload"):
            boundary.mark_dirty(PROVENANCE_GRAPH_IRI, other_payload)
        with pytest.raises(CoreStateError, match="does not match durable pending"):
            boundary.mark_clean(PROVENANCE_GRAPH_IRI, "0" * 64)
        assert store.catalog_publication()["publication_state"] == "dirty"

    with CoreStateStore(database) as reopened:
        boundary = catalog_publication_boundary(reopened)
        assert boundary.mark_dirty(PROVENANCE_GRAPH_IRI, payload) == digest
        boundary.mark_clean(PROVENANCE_GRAPH_IRI, digest)
        clean = reopened.catalog_publication()
        assert clean["publication_state"] == "clean"
        assert clean["published_payload_hash"] == digest
        assert clean["published_payload"] == payload
        assert clean["pending_payload_hash"] is None and clean["pending_payload"] is None

        next_digest = boundary.mark_dirty(PROVENANCE_GRAPH_IRI, other_payload)
        staged = reopened.catalog_publication()
        assert staged["publication_state"] == "dirty"
        assert staged["published_payload_hash"] == digest
        assert staged["pending_payload_hash"] == next_digest
        boundary.mark_clean(PROVENANCE_GRAPH_IRI, next_digest)
        assert reopened.catalog_publication()["published_payload"] == other_payload
        # The replaceable catalog projection never adds events/versions about
        # its own publication, avoiding self-referential catalog growth.
        assert reopened.provenance_events() == []
        assert reopened.graph_versions() == []


def test_finish_run_atomically_stages_exact_catalog_payload(tmp_path):
    payload = "<https://example.test/run> <https://example.test/p> <https://example.test/o> .\n"
    failure_payload = payload + "# failed outcome projection\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        run_id = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "fixture"}, versions=VERSIONS,
        )

        store.stage_run_catalog_finalization(
            run_id, outcome="success", error=None,
            completed_at="2026-10-07T13:00:00+00:00",
            catalog_payload=payload, failure_payload=failure_payload,
        )

        run = store.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id=?", (run_id,)
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("running", "running")
        assert not store.provenance_events(run_id=run_id, event_type="run_finished")
        publication = store.catalog_publication()
        assert publication["publication_state"] == "dirty"
        assert publication["pending_payload_hash"] == digest
        assert publication["pending_payload"] == payload

        store.mark_catalog_clean(PROVENANCE_GRAPH_IRI, digest)
        run = store.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id=?", (run_id,)
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("succeeded", "success")
        assert len(store.provenance_events(run_id=run_id, event_type="run_finished")) == 1


def test_conflicting_catalog_payload_rolls_back_run_finalization(tmp_path):
    old_payload = "<https://example.test/old> <https://example.test/p> <https://example.test/o> .\n"
    new_payload = "<https://example.test/new> <https://example.test/p> <https://example.test/o> .\n"
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        store.mark_catalog_dirty(PROVENANCE_GRAPH_IRI, old_payload)
        run_id = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "fixture"}, versions=VERSIONS,
        )

        with pytest.raises(CoreStateError, match="different durable dirty payload"):
            store.stage_run_catalog_finalization(
                run_id, outcome="success", error=None,
                completed_at="2026-10-07T13:00:00+00:00",
                catalog_payload=new_payload,
                failure_payload=new_payload + "# failed\n",
            )

        run = store.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id=?", (run_id,)
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("running", "running")
        assert not store.provenance_events(run_id=run_id, event_type="run_finished")
        publication = store.catalog_publication()
        assert publication["publication_state"] == "dirty"
        assert publication["pending_payload"] == old_payload


def test_catalog_publication_failure_fails_run_without_advancing_cursor(tmp_path):
    planned = "<https://example.test/planned> <https://example.test/p> <https://example.test/o> .\n"
    failed = "<https://example.test/failed> <https://example.test/p> <https://example.test/o> .\n"
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        run_id = store.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"}, versions=VERSIONS,
        )
        store.stage_run_catalog_finalization(
            run_id, outcome="success", error=None,
            completed_at="2026-10-07T13:00:00+00:00",
            incremental_cursor="2026-10-07T12:59:00Z",
            summary={"counters": {"published_graphs": 1}},
            catalog_payload=planned, failure_payload=failed,
        )
        assert store.incremental_cursor() is None
        assert store.status()["recent_runs"][0]["outcome"] == "running"

        failed_hash = store.fail_pending_catalog_finalization(
            run_id, error="remote whole-graph verification failed",
        )
        run = store.connection.execute(
            "SELECT status,outcome,failure_scope,failure_classification,summary_json "
            "FROM etl_run WHERE run_id=?", (run_id,)
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("failed", "failed")
        assert run["failure_scope"] == "system"
        assert run["failure_classification"] == "catalog_publication_failure"
        assert json.loads(run["summary_json"])["counters"] == {"published_graphs": 1}
        assert store.incremental_cursor() is None
        assert store.last_successful_complete_run("legislation") is None
        publication = store.catalog_publication()
        assert publication["publication_state"] == "dirty"
        assert publication["pending_payload"] == failed
        assert publication["pending_payload_hash"] == failed_hash
        attempts = store.connection.execute(
            "SELECT payload,payload_hash,error FROM catalog_publication_attempt WHERE run_id=?",
            (run_id,),
        ).fetchall()
        assert len(attempts) == 1
        assert attempts[0]["payload"] == planned
        assert attempts[0]["payload_hash"] == hashlib.sha256(planned.encode()).hexdigest()
        assert "verification failed" in attempts[0]["error"]

        store.mark_catalog_clean(PROVENANCE_GRAPH_IRI, failed_hash)
        assert store.incremental_cursor() is None
        assert store.catalog_publication()["publication_state"] == "clean"


def test_interrupted_catalog_finalization_replays_before_marking_run_successful(tmp_path):
    database = tmp_path / "state.sqlite"
    planned = "<https://example.test/recover> <https://example.test/p> <https://example.test/o> .\n"
    failure = "<https://example.test/recover-failed> <https://example.test/p> <https://example.test/o> .\n"
    digest = hashlib.sha256(planned.encode("utf-8")).hexdigest()
    with CoreStateStore(database) as store:
        interrupted = store.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"}, versions=VERSIONS,
        )
        store.stage_run_catalog_finalization(
            interrupted, outcome="success", error=None,
            completed_at="2026-10-07T13:00:00+00:00",
            incremental_cursor="2026-10-07T12:59:00Z",
            catalog_payload=planned, failure_payload=failure,
        )
        assert store.incremental_cursor() is None
        assert store.status()["catalog_publication"]["pending_run_id"] == interrupted

    with CoreStateStore(database) as recovered:
        followup = recovered.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"}, versions=VERSIONS,
        )
        old = recovered.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id=?", (interrupted,)
        ).fetchone()
        assert (old["status"], old["outcome"]) == ("running", "running")
        assert recovered.catalog_publication()["pending_payload"] == planned

        # This is the same clean marker the CLI writes only after the exact
        # pending payload has been replaced and verified remotely.
        recovered.mark_catalog_clean(PROVENANCE_GRAPH_IRI, digest)
        old = recovered.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id=?", (interrupted,)
        ).fetchone()
        assert (old["status"], old["outcome"]) == ("succeeded", "success")
        assert recovered.incremental_cursor() == "2026-10-07T12:59:00+00:00"
        assert recovered.status()["catalog_publication"]["publication_state"] == "clean"
        recovered.finish_run(followup, success=False, error="test cleanup")


def test_run_outcomes_summaries_and_degraded_runs_cannot_advance_cursor_or_absence(tmp_path):
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        successful = store.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"}, versions=VERSIONS,
        )
        store.record_run_summary(successful, counters={"extracted": 12, "changed": 3},
                                 timings={"transform_seconds": 0.25})
        store.finish_run(successful, success=True,
                         incremental_cursor="2026-10-01T00:00:00Z")

        degraded = store.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"}, versions=VERSIONS,
        )
        with pytest.raises(CoreStateError, match="cannot advance"):
            store.finish_run(degraded, outcome="degraded", error="one invalid record",
                             incremental_cursor="2026-10-02T00:00:00Z")
        with pytest.raises(CoreStateError, match="cannot establish missing-resource"):
            store.finish_run(degraded, outcome="degraded", complete_scan=True)
        store.finish_run(
            degraded, outcome="degraded", error="one invalid record",
            failure_scope="record", failure_classification="record_transform_failure",
            summary={"counters": {"quarantined": 1, "validation_failures": 1},
                     "timings": {"validation_seconds": 0.5}},
        )
        state = store.status()
        assert state["endpoints"][0]["incremental_cursor"] == "2026-10-01T00:00:00+00:00"
        assert state["endpoints"][0]["last_successful_run_id"] == successful
        runs = {row["run_id"]: row for row in state["recent_runs"]}
        assert runs[successful]["status"] == "succeeded"  # legacy status API
        assert runs[successful]["outcome"] == "success"
        assert runs[successful]["summary"]["counters"] == {"extracted": 12, "changed": 3}
        assert runs[successful]["summary"]["timings"]["run_seconds"] >= 0
        assert runs[degraded]["status"] == "degraded"
        assert runs[degraded]["outcome"] == "degraded"
        assert runs[degraded]["failure_scope"] == "record"
        assert runs[degraded]["failure_classification"] == "record_transform_failure"
        assert runs[degraded]["summary"]["counters"]["quarantined"] == 1
        assert store.successful_complete_run("legislation", degraded) is None

        failed = store.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"},
        )
        with pytest.raises(CoreStateError, match="cannot advance"):
            store.finish_run(failed, success=False, error="source timeout",
                             incremental_cursor="2026-10-03T00:00:00Z")
        store.finish_run(failed, success=False, error="source timeout")
        failed_row = next(run for run in store.status()["recent_runs"]
                          if run["run_id"] == failed)
        assert failed_row["status"] == "failed" and failed_row["outcome"] == "failed"
        assert failed_row["failure_scope"] == "run"


def test_quarantine_inspection_retry_resolution_and_immutable_evidence(tmp_path):
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        run = store.start_run("members", "full_refresh", is_complete=True,
                              parameters={"source": "api"}, versions=VERSIONS)
        evidence_hash = hashlib.sha256(b"member source record").hexdigest()
        qid = store.record_quarantine(
            "members", run_id=run, source_hash=evidence_hash,
            observed_at="2026-10-01T12:00:00Z",
            evidence_pointer="file:///raw/members/sha256/member.json",
            resource_iri=MEMBER["uri"], stage="member_transform",
            error="invalid membership date",
        )
        row = store.quarantine_records(endpoint="members", status="quarantined")[0]
        assert row["quarantine_id"] == qid
        assert row["evidence_pointer"].endswith("member.json")
        assert row["source_hash"] == evidence_hash and row["observed_at"].endswith("+00:00")
        assert row["stage"] == "member_transform" and row["error"] == "invalid membership date"
        assert row["mapping_version"] == VERSIONS["mapping_version"]
        assert row["ontology_version"] == VERSIONS["ontology_version"]
        assert store.quarantines_for_retry("members")[0]["quarantine_id"] == qid
        store.request_quarantine_retry(qid, requested_by="operator", reason="mapping fix deployed")
        with pytest.raises(CoreStateError, match="unresolved record quarantine"):
            store.finish_run(run, success=True)
        store.finish_run(run, outcome="degraded", error="quarantined member",
                         failure_scope="record", failure_classification="record_transform_failure")

        retry_run = store.start_run("members", "full_refresh", is_complete=True,
                                    parameters={"source": "api"}, versions=VERSIONS)
        store.start_quarantine_retry(qid, run_id=retry_run)
        store.finish_quarantine_retry(qid, run_id=retry_run, success=True)
        resolved = store.quarantine_records(endpoint="members", status="resolved")[0]
        assert resolved["status"] == "resolved" and resolved["retry_state"] == "succeeded"
        assert resolved["retry_attempts"] == 1
        actions = [event["action"] for event in store.quarantine_history(qid)]
        assert actions == ["quarantined", "retry_requested", "retry_started", "retry_succeeded"]
        with pytest.raises(sqlite3.IntegrityError, match="evidence is immutable"):
            store.connection.execute(
                "UPDATE quarantine_record SET evidence_pointer='file:///changed' WHERE quarantine_id=?",
                (qid,),
            )

        second = store.record_quarantine(
            "members", run_id=retry_run, source_hash=hashlib.sha256(b"second").hexdigest(),
            observed_at="2026-10-01T12:01:00Z", evidence_pointer="file:///raw/second.json",
            resource_iri=MEMBER["uri"], stage="member_transform", error="needs review",
        )
        store.resolve_quarantine(second, resolution="confirmed source issue", resolved_by="reviewer")
        store.finish_run(retry_run, success=True)
        manual = next(row for row in store.quarantine_records(status="resolved")
                      if row["quarantine_id"] == second)
        assert manual["resolution"] == "confirmed source issue"
        assert store.quarantine_history(second)[-1]["action"] == "resolved"


def test_provenance_records_runs_sources_graph_versions_and_catalog_identity(tmp_path):
    database = tmp_path / "state.sqlite"
    payload = "<https://example.test/member> <https://example.test/p> <https://example.test/o> .\n"
    source_hash = hashlib.sha256(b"immutable member input").hexdigest()
    graph = member_graph_iri(MEMBER)
    with CoreStateStore(database) as store:
        run = store.start_run("members", "full_refresh", is_complete=True,
                              parameters={"source": "api", "limit": 100}, versions=VERSIONS)
        store.observe_resource(
            "members", MEMBER["uri"], graph, source_hash, run,
            observed_at="2026-10-02T09:30:00Z",
            evidence_pointer="file:///raw/members/sha256/member.json",
            request_parameters={"skip": 0, "limit": 100},
        )
        payload_hash = store.mark_publication_dirty(
            "members", MEMBER["uri"], source_hash=source_hash,
            graph_iri=graph, payload=payload, contract_version=3,
        )
        store.complete_publication(
            "members", MEMBER["uri"], source_hash=source_hash,
            graph_iri=graph, payload_hash=payload_hash, contract_version=3,
        )
        store.finish_run(run, success=True)

        versions = store.graph_versions(graph)
        assert len(versions) == 1
        assert (versions[0]["graph_iri"], versions[0]["payload_hash"]) == (graph, payload_hash)
        assert versions[0]["payload"] == payload
        events = store.provenance_events(run_id=run)
        assert {event["event_type"] for event in events} == {
            "run_started", "source_observed", "entity_published", "run_finished",
        }
        assert all(event["run_iri"] == run_resource_iri(run) for event in events)
        observation = next(event for event in events if event["event_type"] == "source_observed")
        assert observation["source_hash"] == source_hash
        assert observation["observed_at"] == "2026-10-02T09:30:00+00:00"
        assert observation["evidence_pointer"].endswith("member.json")
        assert next(event for event in events if event["event_type"] == "entity_published")["entity_iri"] == MEMBER["uri"]
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.connection.execute("DELETE FROM graph_version WHERE graph_iri=?", (graph,))
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            store.connection.execute("UPDATE provenance_event SET details_json='{}'")

        house_run = store.start_run("houses", "full_refresh", is_complete=True,
                                    parameters={"source": "fixture"})
        house_graph = "https://data.oireachtas.ie/graph/houses"
        shared_payload = "<https://example.test/house> <https://example.test/p> <https://example.test/o> .\n"
        digest = store.mark_endpoint_dirty("houses", house_graph, shared_payload,
                                           run_id=house_run)
        store.complete_endpoint_publication("houses", house_graph, digest)
        store.finish_run(house_run, success=True)
        shared = store.provenance_events(event_type="graph_published", run_id=house_run)
        assert len(shared) == 1 and shared[0]["graph_iri"] == house_graph
        assert shared[0]["payload_hash"] == digest
        assert PROVENANCE_GRAPH_IRI == "https://data.oireachtas.ie/graph/provenance"

    with CoreStateStore(database) as reopened:
        assert len(reopened.provenance_events(run_id=run)) == 4
        assert len(reopened.graph_versions(graph)) == 1


def test_state_rejects_secret_metadata_before_durable_provenance_writes(tmp_path):
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        with pytest.raises(CoreStateError, match="credential-like metadata"):
            store.start_run(
                "members", "full_refresh", is_complete=True,
                parameters={"source": "api",
                            "api_url": "https://api.example.test/members?access_token=topsecret"},
                versions=VERSIONS,
            )
        assert store.connection.execute("SELECT COUNT(*) FROM etl_run").fetchone()[0] == 0
        assert store.provenance_events() == []

        run = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api",
                        "api_url": "https://api.oireachtas.ie/v1/members?limit=100&skip=0"},
            versions=VERSIONS,
        )
        started = store.provenance_events(run_id=run, event_type="run_started")[0]
        assert started["details"]["parameters"]["api_url"].endswith("limit=100&skip=0")

        source_hash = hashlib.sha256(b"source page").hexdigest()
        with pytest.raises(CoreStateError, match=r"credential-free HTTP\(S\)"):
            store.record_source_observation(
                "members", source_hash, "2026-10-03T10:00:00Z", run_id=run,
                source_url="https://user:password@api.example.test/members",
                evidence_pointer="file:///raw/members/source.json",
                request_parameters={"skip": 0, "limit": 100},
            )
        with pytest.raises(CoreStateError, match="credential-like metadata"):
            store.record_source_observation(
                "members", source_hash, "2026-10-03T10:00:00Z", run_id=run,
                source_url="https://api.oireachtas.ie/v1/members?limit=100",
                evidence_pointer="file:///raw/members/source.json",
                request_parameters={"skip": 0, "authorization": "Bearer privatevalue"},
            )
        assert store.connection.execute("SELECT COUNT(*) FROM source_observation").fetchone()[0] == 0
        assert not store.provenance_events(run_id=run, event_type="source_observed")
        observation = store.record_source_observation(
            "members", source_hash, "2026-10-03T10:00:00Z", run_id=run,
            source_url="https://api.oireachtas.ie/v1/members?limit=100&skip=0",
            evidence_pointer="file:///raw/members/source.json",
            request_parameters={"skip": 0, "limit": 100,
                                "reference": "https://example.test/members?q=public"},
        )
        assert observation["source_url"].endswith("limit=100&skip=0")
        assert json.loads(observation["request_parameters_json"])["reference"] == (
            "https://example.test/members?q=public")

        with pytest.raises(CoreStateError, match="credential-like metadata"):
            store.finish_run(
                run, success=False,
                error="request failed at https://user:password@api.example.test/path",
            )
        assert store.connection.execute(
            "SELECT status FROM etl_run WHERE run_id=?", (run,)).fetchone()[0] == "running"
        assert not store.provenance_events(run_id=run, event_type="run_finished")

        with pytest.raises(CoreStateError, match="credential-like metadata"):
            store.record_quarantine(
                "members", run_id=run, source_hash=source_hash,
                observed_at="2026-10-03T10:00:00Z",
                evidence_pointer="file:///raw/members/source.json",
                resource_iri=MEMBER["uri"], stage="member_transform",
                error="decode failed: password=hunter2",
            )
        assert store.connection.execute("SELECT COUNT(*) FROM quarantine_record").fetchone()[0] == 0
        assert store.connection.execute("SELECT COUNT(*) FROM quarantine_history").fetchone()[0] == 0
        store.finish_run(run, success=False, error="request timed out")


def test_v5_clean_publications_backfill_only_with_complete_verifiable_evidence(tmp_path):
    database = tmp_path / "phase5-clean.sqlite"
    _v5_database(database)
    raw_bytes = b"immutable member source captured before provenance schema"
    raw_hash = hashlib.sha256(raw_bytes).hexdigest()
    raw_path = tmp_path / f"{raw_hash}.json"
    raw_path.write_bytes(raw_bytes)
    payload = "<https://example.test/legacy-member> <https://example.test/p> <https://example.test/o> .\n"
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    identity = MEMBER["uri"]
    graph = member_graph_iri(MEMBER)
    missing_identity = "https://data.oireachtas.ie/ie/oireachtas/member/id/legacy-without-raw"
    missing_graph = "https://data.oireachtas.ie/graph/member/legacy-without-raw"
    shared_payload = "<https://example.test/legacy-house> <https://example.test/p> <https://example.test/o> .\n"
    shared_hash = hashlib.sha256(shared_payload.encode("utf-8")).hexdigest()
    versions = {"etl_version": "0.5.0", "ontology_version": "2026-09-01",
                "mapping_version": "2026-09-01"}
    parameters = {"source": "api", "request_parameters": {"skip": 0, "limit": 100},
                  "versions": versions}
    with sqlite3.connect(database) as connection:
        connection.execute("""INSERT INTO etl_run VALUES
          ('legacy-member-run','members','full_refresh',1,
           '2026-10-03T10:00:00+00:00','2026-10-03T10:02:00+00:00',
           'succeeded',NULL,?)""", (json.dumps(parameters),))
        connection.execute("""INSERT INTO endpoint_state (
          endpoint,last_successful_run_id,last_successful_complete_run_id,
          incremental_cursor,publication_metadata_json,updated_at)
          VALUES ('houses',NULL,NULL,NULL,?, '2026-10-03T10:02:00+00:00')""",
          (json.dumps({"graph_iri": "https://data.oireachtas.ie/graph/houses",
                       "publication_state": "clean",
                       "published_payload_hash": shared_hash,
                       "published_payload": shared_payload}),))
        for resource_iri, graph_iri, source_hash, evidence_path in (
                (identity, graph, raw_hash, str(raw_path)),
                (missing_identity, missing_graph, "b" * 64, None)):
            connection.execute("""INSERT INTO resource_state (
              endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
              published_payload_hash,published_payload,last_seen_at,last_seen_run_id,
              last_published_at,publication_state,source_presence,contract_version,
              raw_source_path,source_url)
              VALUES ('members',?,?,?,?,?,?,?,'legacy-member-run',?,'clean','present',3,?,?)""",
              (resource_iri, graph_iri, source_hash, source_hash, payload_hash, payload,
               "2026-10-03T10:00:30+00:00", "2026-10-03T10:01:30+00:00",
               evidence_path, "https://api.oireachtas.ie/v1/members?limit=100"))

    with CoreStateStore(database) as migrated:
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        versions_found = migrated.graph_versions(graph)
        assert len(versions_found) == 1
        assert versions_found[0]["payload"] == payload
        assert versions_found[0]["first_run_id"] == "legacy-member-run"
        observation = migrated.connection.execute(
            "SELECT evidence_pointer,source_url,request_parameters_json,versions_json "
            "FROM source_observation WHERE source_hash=?", (raw_hash,)
        ).fetchone()
        assert observation["evidence_pointer"] == raw_path.resolve().as_uri()
        assert observation["source_url"] == "https://api.oireachtas.ie/v1/members?limit=100"
        assert json.loads(observation["request_parameters_json"]) == {"skip": 0, "limit": 100}
        assert json.loads(observation["versions_json"]) == versions
        validate_provenance_catalog(build_provenance_catalog(migrated))

        incomplete = migrated.status()["provenance_incomplete"]
        by_graph = {entry["graph_iri"]: entry for entry in incomplete}
        assert len(by_graph) == 2
        member_gap = by_graph[missing_graph]
        assert member_gap["resource_iri"] == missing_identity
        assert member_gap["reason"] == "legacy_raw_source_evidence_unavailable"
        assert member_gap["required_action"] == "validated_reobservation_and_republish"
        assert member_gap["status"] == "pending"
        shared_gap = by_graph["https://data.oireachtas.ie/graph/houses"]
        assert shared_gap["resource_iri"] is None
        assert shared_gap["reason"] == "legacy_shared_publication_evidence_unavailable"
        # The unrelated dirty Debate remains a replayable publication and is
        # not reclassified as an incomplete clean publication.
        debates = migrated.get_resource("debates", "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-01-01")
        assert debates["publication_state"] == "dirty"
        assert debates["pending_payload_hash"] == hashlib.sha256(
            b"<https://example.test/debate> <https://example.test/p> <https://example.test/o> .\n"
        ).hexdigest()

        new_raw = b"validated re-observation for legacy member"
        new_source_hash = hashlib.sha256(new_raw).hexdigest()
        new_raw_path = tmp_path / "reobserved-member.json"
        new_raw_path.write_bytes(new_raw)
        replay = migrated.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api"}, versions=VERSIONS,
        )
        migrated.observe_resource(
            "members", missing_identity, missing_graph, new_source_hash, replay,
            evidence_pointer=new_raw_path.resolve().as_uri(),
            request_parameters={"skip": 0, "limit": 100}, versions=VERSIONS,
        )
        replay_payload = "<https://example.test/reobserved-member> <https://example.test/p> <https://example.test/o> .\n"
        replay_hash = migrated.mark_publication_dirty(
            "members", missing_identity, source_hash=new_source_hash,
            graph_iri=missing_graph, payload=replay_payload, contract_version=3,
        )
        migrated.complete_publication(
            "members", missing_identity, source_hash=new_source_hash,
            graph_iri=missing_graph, payload_hash=replay_hash, contract_version=3,
        )
        migrated.finish_run(replay, success=True)
        assert all(entry["graph_iri"] != missing_graph
                   for entry in migrated.status()["provenance_incomplete"])
        resolved = {entry["graph_iri"]: entry
                    for entry in migrated.provenance_incomplete_records(include_resolved=True)}
        assert resolved[missing_graph]["status"] == "resolved"
