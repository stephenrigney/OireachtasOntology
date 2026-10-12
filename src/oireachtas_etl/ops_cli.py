"""Operator-triggered commands for backups and fresh-store reconstruction."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from contextlib import nullcontext
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from .config import Settings
from .alerts import mark_degraded_alert_delivered, prepare_degraded_alert
from .loader import FusekiGraphStoreLoader, FusekiSparqlClient
from .office_reconciliation import OfficeOccurrenceStore
from .bill_sponsor_reconciliation import BillSponsorStore
from .operations import (BackupConfig, BackupEngine, RetentionPolicy,
                         default_backup_config, exclusive_operation_lock)
from .projection import (ProjectionError, rebuild_empty_dataset,
                         rebuildable_graph_payloads, verify_existing_dataset)
from .reconciliation import ReconciliationStore
from .state import CoreStateStore
from .validation.offices import validate_registry_source


def _positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if not value > 0:
        raise ValueError(f"{name} must be positive")
    return value


def _positive_int(name: str, default: int, *, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _backup_engine(settings: Settings) -> BackupEngine:
    repository = os.getenv("OIR_RESTIC_REPOSITORY")
    if not repository:
        raise ValueError("OIR_RESTIC_REPOSITORY must identify the encrypted backup repository")
    password_file = os.getenv("OIR_RESTIC_PASSWORD_FILE")
    if not password_file:
        raise ValueError("OIR_RESTIC_PASSWORD_FILE must point to the protected runtime secret")
    daily = int(os.getenv("OIR_BACKUP_KEEP_DAILY", "30"))
    monthly = int(os.getenv("OIR_BACKUP_KEEP_MONTHLY", "12"))
    rpo_hours = _positive_float("OIR_BACKUP_RPO_HOURS", 24.0)
    project_root = Path(os.getenv("OIR_PROJECT_ROOT", str(Path.cwd()))).expanduser()
    config = default_backup_config(
        repository, project_root, settings=settings, password_file=password_file,
        retention=RetentionPolicy(daily=daily, monthly=monthly), rpo_hours=rpo_hours)
    return BackupEngine(config)


def _json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _lock_path(settings: Settings) -> Path:
    if settings.operation_lock_file is None:
        raise ValueError("OIR_OPERATION_LOCK_FILE is required for coordinated operations")
    return settings.operation_lock_file


def _initialize_state(settings: Settings) -> int:
    with exclusive_operation_lock(_lock_path(settings)):
        with CoreStateStore(settings.core_state_db_file):
            pass
        reconciliation = ReconciliationStore(settings.reconciliation_state_db_file)
        reconciliation.close()
        with OfficeOccurrenceStore(settings.office_occurrence_state_db_file):
            pass
        with BillSponsorStore(settings.bill_sponsor_state_db_file):
            pass
    _json({
        "event": "state_initialized",
        "stores": {
            "core_state": str(settings.core_state_db_file),
            "reconciliation": str(settings.reconciliation_state_db_file),
            "office_occurrences": str(settings.office_occurrence_state_db_file),
            "bill_sponsors": str(settings.bill_sponsor_state_db_file),
        },
    })
    return 0


def _backup_command(args: argparse.Namespace, settings: Settings) -> int:
    engine = _backup_engine(settings)
    # Repository reads also take the shared lock: the scheduled disposable
    # drill copies the local Restic repository under this same coordination
    # boundary, so no Restic command can be active during that copy.
    with exclusive_operation_lock(_lock_path(settings)):
        if args.backup_command == "init":
            engine.initialize_repository()
            _json({"event": "backup_repository_initialized", "repository": engine.config.repository})
            return 0
        if args.backup_command == "create":
            result = engine.backup(operation_lock=nullcontext())
            _json({"event": "backup_created", **asdict(result)})
            return 0
        if args.backup_command == "list":
            _json({"event": "backup_snapshots", "snapshots": engine.list_snapshots()})
            return 0
        if args.backup_command in {"status", "check"}:
            status = engine.status(
                check_integrity=not args.skip_integrity_check,
                verify_latest_snapshot=not args.skip_snapshot_restore_check)
            result = asdict(status)
            if isinstance(result.get("latest_snapshot_time"), datetime):
                result["latest_snapshot_time"] = result["latest_snapshot_time"].isoformat()
            result["healthy"] = status.healthy
            result["event"] = "backup_status"
            _json(result)
            return 0 if status.healthy else 1
        if args.backup_command == "restore":
            destination = engine.restore(args.snapshot_id, args.destination)
            snapshot_id = args.snapshot_id
        elif args.backup_command == "restore-latest":
            snapshot_id, destination = engine.restore_latest(args.destination)
        else:
            raise AssertionError("unknown backup command")
        _json({"event": "backup_restored_to_staging", "snapshot_id": snapshot_id,
               "destination": str(destination),
               "next_action": "inspect and activate with `oir-ops state activate-restore`"})
        return 0


def _activate_restore(args: argparse.Namespace, settings: Settings) -> int:
    from .operations import activate_restored_state

    if not args.confirm_replace_existing:
        raise ValueError("activation requires --confirm-replace-existing after operators stop scheduled ETL")
    if args.target_root is None:
        raise ValueError("activation requires the explicit durable --target-root")
    with exclusive_operation_lock(_lock_path(settings)):
        old_directory = activate_restored_state(
            args.staged_root, args.target_root, settings=settings)
    _json({"event": "durable_state_activated", "target_root": str(args.target_root),
           "previous_state_preserved_at": str(old_directory),
           "next_action": "rebuild and verify a fresh Fuseki dataset before resuming ETL"})
    return 0


def _rebuild(args: argparse.Namespace, settings: Settings) -> int:
    if not args.confirm_empty_target:
        raise ValueError("projection rebuild requires --confirm-empty-target")
    state_db = Path(args.state_db or settings.core_state_db_file).expanduser()
    reconciliation_db = Path(
        args.reconciliation_db or settings.reconciliation_state_db_file).expanduser()
    if not reconciliation_db.is_file():
        raise ValueError("reconciliation SQLite backup is required for complete graph reconstruction")
    registry_path = Path(args.registry_file or
                         Path(os.getenv("OIR_PROJECT_ROOT", Path.cwd())) /
                         "registries/ministerial-office-registry.json")
    try:
        registry = validate_registry_source(json.loads(registry_path.read_text(encoding="utf-8")))
    except Exception as error:
        raise ValueError("the versioned office registry is required to validate external links") from error
    gsp_url = args.gsp_url or settings.fuseki_gsp_url
    query_url = args.sparql_url or settings.fuseki_sparql_url
    if not gsp_url or not query_url:
        raise ValueError("projection rebuild requires Fuseki GSP and SPARQL endpoint URLs")
    operation_lock_held = bool(getattr(args, "operation_lock_held", False))
    if operation_lock_held and os.getenv("OIR_OPERATION_LOCK_HELD") != "1":
        raise ValueError("--operation-lock-held is reserved for the production wrapper")
    # The production wrapper holds the host-mounted operation lock across the
    # private rebuild and filesystem cutover. Other callers lock for this
    # reconstruction only.
    lock = (nullcontext() if operation_lock_held
            else exclusive_operation_lock(_lock_path(settings)))
    with lock:
        graphs = rebuildable_graph_payloads(
            state_db, reconciliation_db=reconciliation_db, office_registry=registry)
        loader = FusekiGraphStoreLoader(
            gsp_url, user=settings.fuseki_user, password=settings.fuseki_password,
            timeout=settings.timeout)
        client = FusekiSparqlClient(
            query_url, user=settings.fuseki_user, password=settings.fuseki_password,
            timeout=settings.timeout)
        # An empty list is accepted only because rebuildable_graph_payloads
        # proves the untouched current Core State has no publication history.
        summary = rebuild_empty_dataset(graphs, loader, client, allow_empty=not graphs)
    _json({"event": "projection_rebuilt", **summary})
    return 0


def _verify_projection(args: argparse.Namespace, settings: Settings) -> int:
    state_db = Path(args.state_db or settings.core_state_db_file).expanduser()
    reconciliation_db = Path(
        args.reconciliation_db or settings.reconciliation_state_db_file).expanduser()
    if not reconciliation_db.is_file():
        raise ValueError("reconciliation SQLite backup is required for complete graph verification")
    registry_path = Path(args.registry_file or
                         Path(os.getenv("OIR_PROJECT_ROOT", Path.cwd())) /
                         "registries/ministerial-office-registry.json")
    try:
        registry = validate_registry_source(json.loads(registry_path.read_text(encoding="utf-8")))
    except Exception as error:
        raise ValueError("the versioned office registry is required to validate external links") from error
    gsp_url = args.gsp_url or settings.fuseki_gsp_url
    query_url = args.sparql_url or settings.fuseki_sparql_url
    if not gsp_url or not query_url:
        raise ValueError("projection verification requires Fuseki GSP and SPARQL endpoint URLs")
    operation_lock_held = bool(getattr(args, "operation_lock_held", False))
    if operation_lock_held and os.getenv("OIR_OPERATION_LOCK_HELD") != "1":
        raise ValueError("--operation-lock-held is reserved for the production wrapper")
    lock = (nullcontext() if operation_lock_held
            else exclusive_operation_lock(_lock_path(settings)))
    with lock:
        graphs = rebuildable_graph_payloads(
            state_db, reconciliation_db=reconciliation_db, office_registry=registry)
        client = FusekiSparqlClient(
            query_url, user=settings.fuseki_user, password=settings.fuseki_password,
            timeout=settings.timeout)
        summary = verify_existing_dataset(graphs, client, allow_empty=not graphs)
    _json({"event": "projection_verified", **summary})
    return 0


def _alerts_command(args: argparse.Namespace, settings: Settings) -> int:
    state_dir = Path(os.getenv(
        "OIR_ALERT_STATE_DIR", str(settings.core_state_db_file.parent / "alerts")))
    with exclusive_operation_lock(_lock_path(settings)):
        if args.alerts_command == "check":
            threshold = _positive_int("OIR_ALERT_DEGRADED_RUN_THRESHOLD", 2, minimum=2)
            reconciliation_threshold = _positive_int(
                "OIR_ALERT_RECONCILIATION_DEGRADED_THRESHOLD", 2, minimum=2)
            pending = prepare_degraded_alert(
                settings.core_state_db_file, state_dir, threshold=threshold,
                reconciliation_db=settings.reconciliation_state_db_file,
                reconciliation_threshold=reconciliation_threshold)
            _json({"event": "degraded_run_alert_check",
                   "pending": pending is not None,
                   "pending_file": str(state_dir / "pending.json") if pending else None,
                   "alert_event_id": pending["event_id"] if pending else None})
            return 0
        if args.alerts_command == "delivered":
            result = mark_degraded_alert_delivered(state_dir)
            _json({"event": "degraded_run_alert_delivered", **result})
            return 0
    raise AssertionError("unknown alerts command")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oir-ops")
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup", help="encrypted backup and restore operations")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)
    backup_sub.add_parser("init", help="explicitly initialize the configured Restic repository")
    backup_sub.add_parser("create", help="create and retain an encrypted recovery point")
    backup_sub.add_parser("list", help="list retained recovery-point IDs and creation times")
    for name, help_text in (("status", "report backup integrity and RPO health"),
                            ("check", "check repository and restore the latest manifest for verification")):
        status = backup_sub.add_parser(name, help=help_text)
        status.add_argument("--skip-integrity-check", action="store_true",
                            help="omit the full restic pack read (not for scheduled monitoring)")
        status.add_argument("--skip-snapshot-restore-check", action="store_true",
                            help="omit the temporary latest-snapshot restore/hash check")
    restore = backup_sub.add_parser("restore", help="stage one explicit snapshot without overwriting live state")
    restore.add_argument("snapshot_id")
    restore.add_argument("--destination", required=True)
    latest = backup_sub.add_parser(
        "restore-latest", help="stage the latest snapshot for an isolated recovery drill")
    latest.add_argument("--destination", required=True)

    state = commands.add_parser("state", help="durable state setup and operator-triggered activation")
    state_sub = state.add_subparsers(dest="state_command", required=True)
    state_sub.add_parser("initialize", help="create/migrate the four durable SQLite stores")
    activate = state_sub.add_parser("activate-restore", help="atomically install a validated staged restore")
    activate.add_argument("--staged-root", required=True)
    activate.add_argument("--target-root", required=True)
    activate.add_argument("--confirm-replace-existing", action="store_true")

    projection = commands.add_parser("projection", help="rebuild the replaceable Fuseki projection")
    projection_sub = projection.add_subparsers(dest="projection_command", required=True)
    rebuild = projection_sub.add_parser("rebuild", help="rebuild all saved graphs into an empty dataset")
    rebuild.add_argument("--state-db")
    rebuild.add_argument("--reconciliation-db")
    rebuild.add_argument("--registry-file")
    rebuild.add_argument("--gsp-url")
    rebuild.add_argument("--sparql-url")
    rebuild.add_argument("--confirm-empty-target", action="store_true")
    rebuild.add_argument("--operation-lock-held", action="store_true",
                         help=argparse.SUPPRESS)
    verify = projection_sub.add_parser(
        "verify", help="whole-graph verify the current Fuseki dataset against durable state")
    verify.add_argument("--state-db")
    verify.add_argument("--reconciliation-db")
    verify.add_argument("--registry-file")
    verify.add_argument("--gsp-url")
    verify.add_argument("--sparql-url")
    verify.add_argument("--operation-lock-held", action="store_true",
                        help=argparse.SUPPRESS)

    alerts = commands.add_parser("alerts", help="evaluate repeated degraded-run alert conditions")
    alerts_sub = alerts.add_subparsers(dest="alerts_command", required=True)
    alerts_sub.add_parser("check", help="prepare a pending alert for repeated degraded runs")
    alerts_sub.add_parser("delivered", help="acknowledge a successfully delivered pending alert")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_environment()
    try:
        if args.command == "backup":
            return _backup_command(args, settings)
        if args.command == "state" and args.state_command == "initialize":
            return _initialize_state(settings)
        if args.command == "state" and args.state_command == "activate-restore":
            return _activate_restore(args, settings)
        if args.command == "projection" and args.projection_command == "rebuild":
            return _rebuild(args, settings)
        if args.command == "projection" and args.projection_command == "verify":
            return _verify_projection(args, settings)
        if args.command == "alerts":
            return _alerts_command(args, settings)
        raise AssertionError("unknown operations command")
    except Exception as error:
        # Avoid dumping subprocess output, passwords, or response URLs into
        # systemd/journal logs on the operator boundary.
        _json({"event": "operations_failed", "error": f"{type(error).__name__}: {error}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
