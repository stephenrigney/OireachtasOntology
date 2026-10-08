from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from argparse import Namespace

import pytest

from oireachtas_etl.state import (CoreStateError, CoreStateStore,
                                  PROVENANCE_GRAPH_IRI, SHARED_GRAPHS)
from oireachtas_etl.transforms.bills import bill_graph_iri
from oireachtas_etl.transforms.members import member_graph_iri


ROOT = Path(__file__).resolve().parents[1]
MEMBER = json.loads((ROOT / "data/api_examples/member.json").read_text())
BILL = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]


def _manifest(path: Path, collection: str, entries: dict) -> Path:
    path.write_text(json.dumps({"version": 1, collection: entries}))
    return path


def _member_row(*, state="clean", contract=2):
    member = MEMBER["member"]
    row = {"source_hash": "a" * 64, "published_hash": "b" * 64,
           "graph_iri": member_graph_iri(member), "last_seen": "2026-09-30T10:00:00+00:00",
           "last_published": "2026-09-30T10:00:01+00:00", "contract_version": contract,
           "status": state}
    if state == "dirty":
        row.update(pending_hash="c" * 64, pending_graph_iri=member_graph_iri(member))
    return row


def test_legacy_manifests_import_atomically_and_are_not_dual_written(tmp_path):
    member_identity = MEMBER["member"]["uri"]
    bill_identity = BILL["bill"]["uri"]
    members = _manifest(tmp_path / "members.json", "members", {
        member_identity: _member_row(),
    })
    bills = _manifest(tmp_path / "bills.json", "bills", {
        bill_identity: {
            "source_hash": "d" * 64, "published_hash": "e" * 64,
            "graph_iri": bill_graph_iri(BILL["bill"]), "contract_version": 1,
            "status": "dirty", "pending_hash": "f" * 64,
            "pending_graph_iri": bill_graph_iri(BILL["bill"]),
        },
    })
    before = (members.read_bytes(), bills.read_bytes())
    database = tmp_path / "core.sqlite"

    with CoreStateStore(database, legacy_members=members, legacy_bills=bills) as store:
        imported_member = store.get_resource("members", member_identity)
        imported_bill = store.get_resource("legislation", bill_identity)
        assert imported_member["publication_state"] == "clean"
        assert imported_member["published_source_hash"] == "b" * 64
        assert imported_member["contract_version"] == 2
        assert imported_bill["publication_state"] == "dirty"
        assert imported_bill["published_source_hash"] == "e" * 64
        assert imported_bill["pending_source_hash"] == "f" * 64
        assert imported_bill["pending_graph_iri"] == bill_graph_iri(BILL["bill"])
        # Old manifests did not preserve a replayable RDF payload; dirty state
        # remains dirty and requires transformation from a later source scan.
        assert imported_bill["pending_payload"] is None

    assert (members.read_bytes(), bills.read_bytes()) == before
    # Migration markers make the import a one-time operation: legacy files are
    # no longer consulted once SQLite owns the state.
    members.write_text("not JSON after SQLite took authority")
    with CoreStateStore(database, legacy_members=members, legacy_bills=bills) as store:
        assert store.get_resource("members", member_identity)["published_source_hash"] == "b" * 64


def test_invalid_second_manifest_rolls_back_schema_and_first_manifest_import(tmp_path):
    member_identity = MEMBER["member"]["uri"]
    members = _manifest(tmp_path / "members.json", "members", {member_identity: _member_row()})
    bills = _manifest(tmp_path / "bills.json", "bills", {
        "https://data.oireachtas.ie/ie/oireachtas/bill/2024/5": {
            "published_hash": "a" * 64,
            # Correct syntax, wrong graph boundary.
            "graph_iri": "https://data.oireachtas.ie/graph/bill/2024/6",
        },
    })
    database = tmp_path / "uninitialized.sqlite"

    with pytest.raises(CoreStateError, match="graph IRI does not match"):
        CoreStateStore(database, legacy_members=members, legacy_bills=bills)

    # Schema DDL, schema version, migration markers and the valid Member row
    # share one SQLite transaction with both imports.
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert not tables


def test_core_schema_v1_upgrades_resources_and_reopens(tmp_path):
    database = tmp_path / "core-v1.sqlite"
    member_identity = MEMBER["member"]["uri"]
    member_graph = member_graph_iri(MEMBER["member"])
    bill_identity = BILL["bill"]["uri"]
    bill_graph = bill_graph_iri(BILL["bill"])

    # The v1 layout is the current core schema before the cursor, published
    # payload, and complete-scan absence columns were added.
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            CREATE TABLE core_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE etl_run (
              run_id TEXT PRIMARY KEY,
              endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','members','legislation')),
              run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
              is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)), started_at TEXT NOT NULL,
              completed_at TEXT, status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
              error TEXT, parameters_json TEXT NOT NULL);
            CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at);
            CREATE TABLE endpoint_state (
              endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','members','legislation')),
              last_successful_run_id TEXT, last_successful_complete_run_id TEXT,
              publication_metadata_json TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE resource_state (
              endpoint TEXT NOT NULL CHECK(endpoint IN ('members','legislation')),
              resource_iri TEXT NOT NULL, graph_iri TEXT NOT NULL, observed_source_hash TEXT,
              published_source_hash TEXT, published_payload_hash TEXT, last_seen_at TEXT,
              last_seen_run_id TEXT, last_published_at TEXT,
              publication_state TEXT NOT NULL CHECK(publication_state IN ('clean','dirty')),
              pending_source_hash TEXT, pending_graph_iri TEXT, pending_payload TEXT,
              pending_payload_hash TEXT,
              source_presence TEXT NOT NULL DEFAULT 'present' CHECK(source_presence IN ('present','missing','confirmed_missing')),
              contract_version INTEGER, PRIMARY KEY(endpoint,resource_iri),
              CHECK(publication_state='dirty' OR
                    (pending_source_hash IS NULL AND pending_graph_iri IS NULL AND pending_payload_hash IS NULL)));
            CREATE INDEX resource_state_publication ON resource_state(endpoint,publication_state);
            PRAGMA user_version=1;
        """)
        connection.execute("""INSERT INTO resource_state (
          endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
          published_payload_hash,last_seen_at,last_published_at,publication_state,contract_version)
          VALUES (?,?,?,?,?,?,?,?,?,?)""",
          ("members", member_identity, member_graph, "a" * 64, "b" * 64, "d" * 64,
           "2026-09-30T10:00:00+00:00", "2026-09-30T10:00:01+00:00", "clean", 2))
        pending_payload = "<https://example.test/s> <https://example.test/p> <https://example.test/o> .\n"
        connection.execute("""INSERT INTO resource_state (
           endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
           published_payload_hash,last_seen_at,last_published_at,publication_state,
           pending_source_hash,pending_graph_iri,pending_payload,pending_payload_hash,contract_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
           ("legislation", bill_identity, bill_graph, "e" * 64, "f" * 64, "a" * 64,
            "2026-09-30T11:00:00+00:00", "2026-09-30T11:00:01+00:00", "dirty",
            "e" * 64, bill_graph, pending_payload,
            hashlib.sha256(pending_payload.encode()).hexdigest(), 1))

    with CoreStateStore(database) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        clean = store.get_resource("members", member_identity)
        dirty = store.get_resource("legislation", bill_identity)
        assert clean["publication_state"] == "clean"
        assert clean["published_source_hash"] == "b" * 64
        assert clean["pending_source_hash"] is None
        assert dirty["publication_state"] == "dirty"
        assert dirty["published_source_hash"] == "f" * 64
        assert dirty["pending_source_hash"] == "e" * 64
        assert dirty["pending_graph_iri"] == bill_graph
        assert dirty["pending_payload"] == pending_payload
        assert dirty["pending_payload_hash"] == hashlib.sha256(pending_payload.encode()).hexdigest()
        for row in (clean, dirty):
            assert row["published_payload"] is None
            assert row["last_missing_run_id"] is None
            assert row["last_missing_at"] is None
            assert row["missing_scan_count"] == 0
            assert row["source_presence"] == "present"
        assert store.incremental_cursor() is None

    with CoreStateStore(database) as reopened:
        assert reopened.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        assert reopened.get_resource("members", member_identity)["published_source_hash"] == "b" * 64
        assert reopened.get_resource("legislation", bill_identity)["pending_source_hash"] == "e" * 64


def test_core_schema_v6_adds_catalog_failure_recovery_state_without_losing_dirty_payload(tmp_path):
    database = tmp_path / "core-v6.sqlite"
    payload = "<https://example.test/pending> <https://example.test/p> <https://example.test/o> .\n"
    with CoreStateStore(database) as store:
        store.mark_catalog_dirty(PROVENANCE_GRAPH_IRI, payload)
        store.connection.execute("DROP TRIGGER IF EXISTS catalog_publication_attempt_no_update")
        store.connection.execute("DROP TRIGGER IF EXISTS catalog_publication_attempt_no_delete")
        store.connection.execute("DROP TABLE catalog_publication_attempt")
        store.connection.execute("DROP TABLE catalog_run_finalization")
        store.connection.execute("DROP INDEX IF EXISTS provenance_incomplete_status")
        store.connection.execute("DROP TABLE provenance_incomplete")
        store.connection.execute("PRAGMA user_version=6")

    with CoreStateStore(database) as migrated:
        assert migrated.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        tables = {row[0] for row in migrated.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"catalog_run_finalization", "catalog_publication_attempt",
                "provenance_incomplete"} <= tables
        pending = migrated.catalog_publication()
        assert pending["publication_state"] == "dirty"
        assert pending["pending_payload"] == payload
        assert pending["pending_payload_hash"] == hashlib.sha256(payload.encode()).hexdigest()


def test_core_schema_v2_migration_preserves_runs_and_adds_registry_endpoints(tmp_path):
    database = tmp_path / "core-v2.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            CREATE TABLE core_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE etl_run (
              run_id TEXT PRIMARY KEY,
              endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','members','legislation')),
              run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
              is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)), started_at TEXT NOT NULL,
              completed_at TEXT, status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
              error TEXT, parameters_json TEXT NOT NULL);
            CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at);
            CREATE TABLE endpoint_state (
              endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','members','legislation')),
              last_successful_run_id TEXT, last_successful_complete_run_id TEXT,
              incremental_cursor TEXT, publication_metadata_json TEXT, updated_at TEXT NOT NULL);
            CREATE TABLE resource_state (
              endpoint TEXT NOT NULL CHECK(endpoint IN ('members','legislation')),
              resource_iri TEXT NOT NULL, graph_iri TEXT NOT NULL, observed_source_hash TEXT,
              published_source_hash TEXT, published_payload_hash TEXT, published_payload TEXT,
              last_seen_at TEXT, last_seen_run_id TEXT, last_published_at TEXT,
              last_missing_run_id TEXT, last_missing_at TEXT,
              missing_scan_count INTEGER NOT NULL DEFAULT 0 CHECK(missing_scan_count >= 0),
              publication_state TEXT NOT NULL CHECK(publication_state IN ('clean','dirty')),
              pending_source_hash TEXT, pending_graph_iri TEXT, pending_payload TEXT,
              pending_payload_hash TEXT,
              source_presence TEXT NOT NULL DEFAULT 'present' CHECK(source_presence IN ('present','missing','confirmed_missing')),
              contract_version INTEGER, PRIMARY KEY(endpoint,resource_iri),
              CHECK(publication_state='dirty' OR
                    (pending_source_hash IS NULL AND pending_graph_iri IS NULL AND pending_payload_hash IS NULL)));
            CREATE INDEX resource_state_publication ON resource_state(endpoint,publication_state);
            PRAGMA user_version=2;
        """)
        connection.execute("""INSERT INTO etl_run
          (run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,error,parameters_json)
          VALUES ('prior-run','houses','full_refresh',1,'2026-01-01T00:00:00+00:00',
                  '2026-01-01T00:00:01+00:00','succeeded',NULL,'{"source":"fixture"}')""")
        connection.execute("""INSERT INTO endpoint_state
          (endpoint,last_successful_run_id,last_successful_complete_run_id,incremental_cursor,
           publication_metadata_json,updated_at)
          VALUES ('houses','prior-run','prior-run',NULL,NULL,'2026-01-01T00:00:01+00:00')""")

    with CoreStateStore(database) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        prior = store.connection.execute("SELECT endpoint,status FROM etl_run WHERE run_id='prior-run'").fetchone()
        assert (prior["endpoint"], prior["status"]) == ("houses", "succeeded")
        assert store.endpoint_publication("houses") is None
        run = store.start_run("administrative-units", "full_refresh", is_complete=True,
                              parameters={"source": "registry"})
        store.finish_run(run, success=True)
        office_run = store.start_run("offices", "full_refresh", is_complete=True,
                                     parameters={"source": "registry"})
        store.finish_run(office_run, success=True)


def test_status_first_does_not_forfeit_later_legacy_import(tmp_path, monkeypatch):
    from oireachtas_etl.cli import main
    database = tmp_path / "core.sqlite"
    member_manifest = tmp_path / "members.json"
    monkeypatch.setenv("OIR_MEMBERS_STATE_FILE", str(member_manifest))
    monkeypatch.setenv("OIR_BILLS_STATE_FILE", str(tmp_path / "bills.json"))
    assert main(["state", "status", "--state-db", str(database)]) == 0
    identity = MEMBER["member"]["uri"]
    _manifest(member_manifest, "members", {identity: _member_row(state="dirty")})
    with CoreStateStore(database, legacy_members=member_manifest) as store:
        row = store.get_resource("members", identity)
        assert row["publication_state"] == "dirty"
        assert row["pending_source_hash"] == "c" * 64


def test_late_manifest_cannot_override_established_sqlite_resource_state(tmp_path):
    database = tmp_path / "core.sqlite"
    identity = MEMBER["member"]["uri"]
    graph_iri = member_graph_iri(MEMBER["member"])
    with CoreStateStore(database) as store:
        run = store.start_run("members", "full_refresh", is_complete=True,
                              parameters={"source": "fixture"})
        store.observe_resource("members", identity, graph_iri, "1" * 64, run)
        store.finish_run(run, success=True)
    manifest = _manifest(tmp_path / "members.json", "members",
                         {identity: _member_row()})
    with pytest.raises(CoreStateError, match="resolve the conflict explicitly"):
        CoreStateStore(database, legacy_members=manifest)
    with CoreStateStore(database) as store:
        assert store.get_resource("members", identity)["observed_source_hash"] == "1" * 64


@pytest.mark.parametrize("collection,identity,row", [
    ("members", "https://elsewhere.test/member/1", {"graph_iri": "https://data.oireachtas.ie/graph/member/1"}),
    ("bills", "https://data.oireachtas.ie/ie/oireachtas/bill/2024/5", {
        "graph_iri": "https://data.oireachtas.ie/graph/bill/2024/6"}),
])
def test_legacy_identity_and_graph_validation_is_fail_closed(tmp_path, collection, identity, row):
    source = _manifest(tmp_path / "legacy.json", collection, {identity: row})
    with pytest.raises(CoreStateError, match="IRI"):
        CoreStateStore(tmp_path / "core.sqlite",
                       legacy_members=source if collection == "members" else None,
                       legacy_bills=source if collection == "bills" else None)


def test_dirty_payload_is_durable_before_put_and_clean_only_after_matching_verification(tmp_path):
    identity = MEMBER["member"]["uri"]
    graph_iri = member_graph_iri(MEMBER["member"])
    source_hash = "1" * 64
    payload = "<https://example.test/s> <https://example.test/p> <https://example.test/o> .\n"
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    database = tmp_path / "core.sqlite"

    with CoreStateStore(database) as store:
        run_id = store.start_run("members", "full_refresh", is_complete=True,
                                 parameters={"fixture": "member.json", "limit": 100})
        store.observe_resource("members", identity, graph_iri, source_hash, run_id)
        assert store.mark_publication_dirty("members", identity, source_hash=source_hash,
                                             graph_iri=graph_iri, payload=payload,
                                             contract_version=2) == payload_hash
        dirty = store.get_resource("members", identity)
        assert dirty["publication_state"] == "dirty"
        assert dirty["published_source_hash"] is None
        assert dirty["pending_source_hash"] == source_hash
        assert dirty["pending_payload"] == payload
        assert dirty["pending_payload_hash"] == payload_hash
        store.finish_run(run_id, success=False, error="simulated post-PUT verification failure")
        inspection = store.status()
        assert inspection["endpoints"][0]["dirty_resources"] == 1
        assert inspection["dirty_resources"][0]["pending_payload_hash"] == payload_hash
        assert inspection["recent_runs"][0]["status"] == "failed"

    with CoreStateStore(database) as recovered:
        dirty = recovered.get_resource("members", identity)
        assert dirty["publication_state"] == "dirty" and dirty["pending_payload"] == payload
        with pytest.raises(CoreStateError, match="does not match durable pending"):
            recovered.complete_publication("members", identity, source_hash=source_hash,
                                           graph_iri=graph_iri, payload_hash="0" * 64,
                                           contract_version=2)
        assert recovered.get_resource("members", identity)["publication_state"] == "dirty"
        recovered.complete_publication("members", identity, source_hash=source_hash,
                                       graph_iri=graph_iri, payload_hash=payload_hash,
                                       contract_version=2)
        clean = recovered.get_resource("members", identity)
        assert clean["publication_state"] == "clean"
        assert clean["published_source_hash"] == source_hash
        assert clean["published_payload_hash"] == payload_hash
        assert clean["pending_payload"] is None and clean["pending_payload_hash"] is None


def test_run_and_endpoint_state_distinguish_complete_scan_and_incremental_success(tmp_path):
    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        full = store.start_run("legislation", "full_refresh", is_complete=True,
                               parameters={"source": "api", "limit": 100})
        store.finish_run(full, success=True)
        failed = store.start_run("legislation", "incremental_refresh", is_complete=False,
                                 parameters={"source": "api", "from": "2026-09-30T09:00:00Z",
                                              "to": "2026-09-30T10:00:00Z"})
        store.finish_run(failed, success=False, error="source timeout")
        good_incremental = store.start_run("legislation", "incremental_refresh", is_complete=False,
                                           parameters={"source": "api", "from": "2026-09-30T09:00:00Z"})
        store.finish_run(good_incremental, success=True)
        status = store.status()
        endpoint = status["endpoints"][0]
        assert endpoint["endpoint"] == "legislation"
        assert endpoint["last_successful_run_id"] == good_incremental
        assert endpoint["last_successful_complete_run_id"] == full
        runs = {row["run_id"]: row for row in status["recent_runs"]}
        assert runs[failed]["status"] == "failed" and runs[failed]["error"] == "source timeout"
        assert runs[good_incremental]["status"] == "succeeded"
        assert runs[good_incremental]["is_complete"] is False


def test_interrupted_run_is_recorded_failed_on_next_locked_run(tmp_path):
    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        interrupted = store.start_run("legislation", "incremental_refresh", is_complete=False,
                                      parameters={"upper": "2026-09-30T10:00:00Z"})
    with CoreStateStore(database) as store:
        resumed = store.start_run("legislation", "incremental_refresh", is_complete=False,
                                  parameters={"retry": True})
        runs = {run["run_id"]: run for run in store.status()["recent_runs"]}
        assert runs[interrupted]["status"] == "failed"
        assert "interrupted" in runs[interrupted]["error"]
        assert runs[resumed]["status"] == "running"


def test_core_state_cli_status_reports_database_without_reconciliation_state(tmp_path, capsys):
    from oireachtas_etl.cli import main

    database = tmp_path / "core.sqlite"
    assert main(["state", "status", "--state-db", str(database)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == 8 and output["database"] == str(database)
    assert output["endpoints"] == [] and output["recent_runs"] == []


def test_fresh_v6_schema_has_reference_report_columns_and_pair_checks(tmp_path):
    with CoreStateStore(tmp_path / "fresh.sqlite") as store:
        columns = {row[1] for row in store.connection.execute(
            "PRAGMA table_info(resource_state)")}
        assert {
            "published_reference_report_path", "published_reference_report_hash",
            "pending_reference_report_path", "pending_reference_report_hash",
        } <= columns
        schema = store.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='resource_state'").fetchone()[0]
        assert "published_reference_report_path IS NULL) = (published_reference_report_hash IS NULL" in schema
        assert "pending_reference_report_path IS NULL) = (pending_reference_report_hash IS NULL" in schema


def test_json_legacy_path_is_never_silently_opened_as_sqlite(tmp_path):
    legacy = _manifest(tmp_path / "legacy.json", "members", {})
    with pytest.raises(CoreStateError, match="not SQLite.*legacy-state-file"):
        CoreStateStore(legacy)


@pytest.mark.parametrize("endpoint,graph", [
    ("houses", "https://data.oireachtas.ie/graph/houses"),
    ("parties", "https://data.oireachtas.ie/graph/parties"),
    ("constituencies", "https://data.oireachtas.ie/graph/constituencies"),
    ("administrative-units", "https://data.oireachtas.ie/graph/administrative-units"),
    ("offices", "https://data.oireachtas.ie/graph/offices"),
])
def test_shared_graph_run_and_durable_publication_state(tmp_path, endpoint, graph):
    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        run = store.start_run(endpoint, "full_refresh", is_complete=True,
                              parameters={"source": "fixture"})
        with pytest.raises(CoreStateError, match="shared graph identity"):
            store.mark_endpoint_dirty(endpoint, graph + "/wrong", "payload")
        digest = store.mark_endpoint_dirty(endpoint, graph, "validated payload")
        store.finish_run(run, success=False, error="post-PUT verification failed")
    with CoreStateStore(database) as store:
        assert store.endpoint_publication(endpoint)["publication_state"] == "dirty"
        assert store.endpoint_publication(endpoint)["pending_payload_hash"] == digest
        assert store.endpoint_publication(endpoint)["pending_payload"] == "validated payload"
        with pytest.raises(CoreStateError, match="does not match pending"):
            store.complete_endpoint_publication(endpoint, graph, "bad")
        store.complete_endpoint_publication(endpoint, graph, digest)
        success = store.start_run(endpoint, "full_refresh", is_complete=True,
                                  parameters={"source": "fixture"})
        store.finish_run(success, success=True)
        status = store.status()["endpoints"][0]
        assert status["last_successful_complete_run_id"] is None
        assert status["publication"]["published_payload_hash"] == digest
        assert status["publication"]["published_payload"] == "validated payload"
        assert status["publication"]["publication_state"] == "clean"
        assert status["publication"]["coverage_authoritative"] is False


@pytest.mark.parametrize(("endpoint", "source"), [
    ("houses", "api"), ("parties", "api"), ("constituencies", "api"),
    ("members", "api"), ("legislation", "api"),
    ("committees", "members"),
    ("administrative-units", "registry"), ("offices", "registry"),
])
def test_only_endpoint_authoritative_complete_runs_are_selectable(tmp_path, endpoint, source):
    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        fixture = store.start_run(endpoint, "full_refresh", is_complete=True,
                                  parameters={"source": "fixture"})
        store.finish_run(fixture, success=True)
        assert store.successful_complete_run(endpoint, fixture) is None

        authoritative = store.start_run(endpoint, "full_refresh", is_complete=True,
                                         parameters={"source": source,
                                                     "api_url": "https://api.oireachtas.ie/v1/" + endpoint})
        store.finish_run(authoritative, success=True)
        assert store.last_successful_complete_run(endpoint)["run_id"] == authoritative
        assert store.successful_complete_run(endpoint, authoritative)["run_id"] == authoritative


@pytest.mark.parametrize("endpoint,fixture", [
    ("houses", "houses.json"), ("parties", "parties.json"),
    ("constituencies", "constituencies.json"),
])
def test_shared_graph_cli_verification_failure_recovers_without_clean_state(
        tmp_path, monkeypatch, endpoint, fixture):
    from oireachtas_etl import cli

    published = []
    class Loader:
        def __init__(self, *args, **kwargs):
            pass
        def replace(self, graph_iri, payload, **kwargs):
            published.append(graph_iri)

    class Client:
        def __init__(self, *args, **kwargs):
            pass

    check = {"fail": True}
    def verify(client, graph_iri, payload):
        if check["fail"]:
            raise RuntimeError("post-PUT check failed")

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_core_graph", verify)
    fixture_path = ROOT / "data/api_examples" / fixture
    use_fixture = endpoint == "houses"
    if not use_fixture:
        from oireachtas_etl.api import ApiPage

        envelope = json.loads(fixture_path.read_text(encoding="utf-8"))
        if isinstance(envelope, list):
            count_field = ("partyCount" if endpoint == "parties"
                           else "constituencyCount")
            envelope = {"head": {"counts": {count_field: len(envelope)}},
                        "results": envelope}

        class Api:
            def __init__(self, *args, **kwargs):
                pass

            def harvest(self, *, limit):
                yield ApiPage(json.dumps(envelope).encode("utf-8"), 200,
                              {"skip": 0, "limit": limit})

        monkeypatch.setattr(cli, "ApiClient", Api)
    database = tmp_path / "core.sqlite"
    args = Namespace(endpoint=endpoint,
                     fixture=str(fixture_path) if use_fixture else None,
                     offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(database),
                     output_ttl=None, output_nq=None, fuseki_gsp_url="http://local.test/data",
                     fuseki_sparql_url="http://local.test/query",
                     reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"))
    run = cli.run_houses if endpoint == "houses" else cli.run_reference
    with pytest.raises(RuntimeError, match="post-PUT check failed"):
        run(args)
    with CoreStateStore(database) as store:
        assert store.endpoint_publication(endpoint)["publication_state"] == "dirty"
        assert store.status()["recent_runs"][0]["status"] == "failed"
    check["fail"] = False
    assert run(args) == 0
    with CoreStateStore(database) as store:
        assert store.endpoint_publication(endpoint)["publication_state"] == "clean"
        assert store.status()["recent_runs"][0]["status"] == "succeeded"
    assert published.count(SHARED_GRAPHS[endpoint]) == 2
    # The failed run's exact catalog projection is staged first, then replayed
    # before the recovery run publishes its refreshed catalog.
    assert published.count(PROVENANCE_GRAPH_IRI) == 3
