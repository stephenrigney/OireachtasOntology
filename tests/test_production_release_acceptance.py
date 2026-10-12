"""Disposable Restic restore and projection reconstruction acceptance.

This test is deliberately run only by scripts/production-release-gate.sh. It
uses the actual Restic implementation and Fuseki endpoints owned by that gate;
ordinary development tests do not require either service.
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import nullcontext
from pathlib import Path

import pytest
from rdflib import Graph

from oireachtas_etl.bill_sponsor_reconciliation import BillSponsorStore
from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.office_reconciliation import OfficeOccurrenceStore
from oireachtas_etl.operations import BackupConfig, BackupEngine, RetentionPolicy
from oireachtas_etl.projection import rebuild_empty_dataset, rebuildable_graph_payloads
from oireachtas_etl.reconciliation import ReconciliationStore
from oireachtas_etl.state import CoreStateStore


pytestmark = pytest.mark.skipif(
    not os.getenv("OIR_RELEASE_GATE_GSP_URL"),
    reason="requires the explicitly invoked disposable production release gate",
)


def test_real_backup_restore_rebuild_and_failure_injection(tmp_path: Path, monkeypatch):
    required = ("OIR_RELEASE_GATE_GSP_URL", "OIR_RELEASE_GATE_SPARQL_URL",
                "OIR_RELEASE_GATE_DEBATES_GSP_URL", "OIR_RELEASE_GATE_DEBATES_SPARQL_URL")
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, f"release gate requires live disposable services: {missing}"

    live = tmp_path / "live"
    live.mkdir()
    raw = live / "raw"
    raw.mkdir()
    backup_repo = tmp_path / "backup-repository"
    password = tmp_path / "restic-password"
    password.write_text("release-gate-only-restic-password\n", encoding="utf-8")
    source_db = live / "core-state.sqlite"
    reconciliation_db = live / "reconciliation.sqlite"
    office_db = live / "office-occurrences.sqlite"
    sponsor_db = live / "bill-sponsors.sqlite"
    for store in (CoreStateStore(source_db), ReconciliationStore(reconciliation_db),
                  OfficeOccurrenceStore(office_db), BillSponsorStore(sponsor_db)):
        store.close()

    # Publish a representative source-backed graph through the real Core State
    # and Fuseki path before taking a recoverable point.
    from argparse import Namespace
    from oireachtas_etl.cli import run_houses

    root = Path(__file__).resolve().parents[1]
    gsp = os.environ["OIR_RELEASE_GATE_GSP_URL"]
    sparql = os.environ["OIR_RELEASE_GATE_SPARQL_URL"]
    args = Namespace(
        fixture=str(root / "data/api_examples/houses.json"), offline=False,
        raw_dir=str(raw), state_db=str(source_db), output_nq=None, output_ttl=None,
        fuseki_gsp_url=gsp, fuseki_sparql_url=sparql,
        legacy_state_file=str(tmp_path / "missing-legacy-state.json"),
    )
    assert run_houses(args) == 0

    # Inject an interrupted whole-graph PUT after durable dirty staging. The
    # next ordinary run must replay and verify the saved candidate before it can
    # stage a new one; this is a real Core State + Fuseki path.
    from oireachtas_etl import cli as cli_module
    from oireachtas_etl.config import HOUSES_GRAPH
    changed_records = json.loads((root / "data/api_examples/houses.json").read_text())
    changed_records[0]["house"]["showAs"] += " (release replay)"
    changed_fixture = tmp_path / "houses-changed.json"
    changed_fixture.write_text(json.dumps(changed_records), encoding="utf-8")
    changed_args = Namespace(**{**vars(args), "fixture": str(changed_fixture)})
    original_loader = cli_module.FusekiGraphStoreLoader

    class InterruptFirstHousesPut(original_loader):
        def replace(self, graph_iri, payload, *, content_type="application/n-quads"):
            if graph_iri == HOUSES_GRAPH:
                raise OSError("injected disposable Fuseki PUT interruption")
            return super().replace(graph_iri, payload, content_type=content_type)

    monkeypatch.setattr(cli_module, "FusekiGraphStoreLoader", InterruptFirstHousesPut)
    with pytest.raises(OSError, match="injected disposable Fuseki PUT interruption"):
        run_houses(changed_args)
    with CoreStateStore(source_db) as state:
        dirty = state.endpoint_publication("houses")
        assert dirty["publication_state"] == "dirty"
        assert dirty["pending_payload"] and dirty["pending_payload_hash"]
    monkeypatch.setattr(cli_module, "FusekiGraphStoreLoader", original_loader)
    assert run_houses(changed_args) == 0
    with CoreStateStore(source_db) as state:
        recovered = state.endpoint_publication("houses")
        assert recovered["publication_state"] == "clean"
        assert recovered.get("pending_payload") is None

    # Capture exactly the durable application databases and immutable evidence.
    engine = BackupEngine(BackupConfig(
        repository=backup_repo,
        sqlite_stores={"core-state": source_db, "reconciliation": reconciliation_db,
                       "office-occurrences": office_db, "bill-sponsors": sponsor_db},
        file_roots={"raw": raw, "registry": root / "registries/ministerial-office-registry.json"},
        password_file=password,
        retention=RetentionPolicy(daily=2, monthly=1),
        rpo_hours=24,
        host="phase6-release-gate",
        restic_binary="restic",
    ))
    engine.initialize_repository()
    created = engine.backup(operation_lock=nullcontext())
    assert created.snapshot_id
    assert engine.status(check_integrity=True, verify_latest_snapshot=True).healthy

    restored = tmp_path / "independent-restored-state"
    restored_path = engine.restore(created.snapshot_id, restored)
    assert restored_path == restored
    restored_core = restored / "sqlite/core-state.sqlite"
    restored_reconciliation = restored / "sqlite/reconciliation.sqlite"
    assert restored_core.is_file() and restored_reconciliation.is_file()
    with CoreStateStore(restored_core) as state:
        assert state.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert state.connection.execute("SELECT count(*) FROM graph_version").fetchone()[0] > 0

    # Rebuild a distinct clean dataset from the restored durable state, then
    # verify the exact inventory. No API or external authority is contacted.
    registry = json.loads((root / "registries/ministerial-office-registry.json").read_text())
    rebuilt_payloads = rebuildable_graph_payloads(
        restored_core, reconciliation_db=restored_reconciliation,
        office_registry=registry)
    user = os.environ["OIR_RELEASE_GATE_FUSEKI_USER"]
    password_value = os.environ["OIR_RELEASE_GATE_FUSEKI_PASSWORD"]
    destination = FusekiGraphStoreLoader(
        os.environ["OIR_RELEASE_GATE_DEBATES_GSP_URL"], user=user,
        password=password_value, timeout=15)
    query = FusekiSparqlClient(
        os.environ["OIR_RELEASE_GATE_DEBATES_SPARQL_URL"], user=user,
        password=password_value, timeout=15)
    expected = {item.graph_iri: hashlib.sha256(item.payload.encode()).hexdigest()
                for item in rebuilt_payloads}
    rebuilt = rebuild_empty_dataset(rebuilt_payloads, destination, query)
    assert rebuilt["graphs_verified"] == len(rebuilt_payloads)
    assert rebuilt["triples_verified"] > 0
    from oireachtas_etl.projection import verify_existing_dataset
    verified = verify_existing_dataset(rebuilt_payloads, query)
    assert verified["graphs_verified"] == len(rebuilt_payloads)
    for graph in rebuilt_payloads:
        actual = Graph().parse(data=graph.payload, format="nt")
        assert len(actual) > 0
        assert hashlib.sha256(graph.payload.encode()).hexdigest() == expected[graph.graph_iri]

    # Failure injection: rebuilding into the now-populated destination must
    # fail closed before it can replace or expose a partial projection.
    from oireachtas_etl.projection import ProjectionError
    try:
        rebuild_empty_dataset(rebuilt_payloads, destination, query)
    except ProjectionError as error:
        assert "not an empty Fuseki dataset" in str(error)
    else:
        raise AssertionError("rebuild failure injection unexpectedly succeeded")
    assert verify_existing_dataset(rebuilt_payloads, query)["graphs_verified"] == len(rebuilt_payloads)

    evidence = {
        "backup_snapshot_id": created.snapshot_id,
        "backup_created_at": created.created_at,
        "backup_manifest_sha256": created.manifest_sha256,
        "backup_files": created.files,
        "backup_sqlite_stores": created.sqlite_stores,
        "restored_to_independent_storage": True,
        "restored_core_integrity": "ok",
        "fresh_projection_graphs": rebuilt["graphs_verified"],
        "fresh_projection_triples": rebuilt["triples_verified"],
        "exact_graph_payload_sha256": expected,
        "failure_injection": (
            "interrupted graph PUT recovered from exact dirty payload; non-empty rebuild rejected; "
            "verified projection retained"),
    }
    output = os.environ.get("OIR_RELEASE_GATE_EVIDENCE")
    if output:
        Path(output).write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8")
