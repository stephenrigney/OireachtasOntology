from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from argparse import Namespace

import pytest

from oireachtas_etl.state import CoreStateError, CoreStateStore
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
                                 parameters={"from": "2026-09-30T09:00:00Z",
                                             "to": "2026-09-30T10:00:00Z"})
        store.finish_run(failed, success=False, error="source timeout")
        good_incremental = store.start_run("legislation", "incremental_refresh", is_complete=False,
                                           parameters={"from": "2026-09-30T09:00:00Z"})
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


def test_core_state_cli_status_reports_database_without_reconciliation_state(tmp_path, capsys):
    from oireachtas_etl.cli import main

    database = tmp_path / "core.sqlite"
    assert main(["state", "status", "--state-db", str(database)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == 1 and output["database"] == str(database)
    assert output["endpoints"] == [] and output["recent_runs"] == []


def test_json_legacy_path_is_never_silently_opened_as_sqlite(tmp_path):
    legacy = _manifest(tmp_path / "legacy.json", "members", {})
    with pytest.raises(CoreStateError, match="not SQLite.*legacy-state-file"):
        CoreStateStore(legacy)


@pytest.mark.parametrize("endpoint,graph", [
    ("houses", "https://data.oireachtas.ie/graph/houses"),
    ("parties", "https://data.oireachtas.ie/graph/parties"),
    ("constituencies", "https://data.oireachtas.ie/graph/constituencies"),
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
        with pytest.raises(CoreStateError, match="does not match pending"):
            store.complete_endpoint_publication(endpoint, graph, "bad")
        store.complete_endpoint_publication(endpoint, graph, digest)
        success = store.start_run(endpoint, "full_refresh", is_complete=True,
                                  parameters={"source": "fixture"})
        store.finish_run(success, success=True)
        status = store.status()["endpoints"][0]
        assert status["last_successful_complete_run_id"] == success
        assert status["publication"]["published_payload_hash"] == digest
        assert status["publication"]["publication_state"] == "clean"


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
    def verify(client):
        if check["fail"]:
            raise RuntimeError("post-PUT check failed")

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_" + endpoint + "_competency", verify)
    if endpoint != "houses":
        graph_iri, url_attr, transform, validator, _, mapping = cli.REFERENCE_ENDPOINTS[endpoint]
        monkeypatch.setitem(cli.REFERENCE_ENDPOINTS, endpoint,
                            (graph_iri, url_attr, transform, validator, verify, mapping))
    database = tmp_path / "core.sqlite"
    args = Namespace(endpoint=endpoint, fixture=str(ROOT / "data/api_examples" / fixture),
                     offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(database),
                     output_ttl=None, output_nq=None, fuseki_gsp_url="http://local.test/data",
                     fuseki_sparql_url="http://local.test/query")
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
    assert len(published) == 2
