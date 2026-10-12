from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from oireachtas_etl.config import Settings
from oireachtas_etl.ops_cli import _initialize_state
from oireachtas_etl.operations import (
    MANIFEST_NAME,
    BackupConfig,
    BackupEngine,
    BackupIntegrityError,
    BackupResult,
    BackupSafetyError,
    ResticCommandError,
    activate_restored_state,
    configured_file_roots,
    configured_sqlite_stores,
    exclusive_operation_lock,
)


class FakeRestic:
    """Small restic protocol fake retaining the tree passed to ``backup``."""

    def __init__(self, *, snapshot_time="2026-10-01T00:00:00Z"):
        self.snapshot_time = snapshot_time
        self.commands = []
        self.snapshots = []
        self.archive = None
        self.archived_source = None
        self.fail_operation = None

    def __call__(self, command, **kwargs):
        self.commands.append((list(command), kwargs))
        operations = {"init", "backup", "snapshots", "forget", "check", "restore"}
        operation = next(item for item in command if item in operations)
        if operation == self.fail_operation:
            return subprocess.CompletedProcess(
                command, 23, stdout="", stderr="restic failed: password=VERY_SECRET_VALUE")

        if operation == "backup":
            source = Path(command[-1])
            repository = Path(command[command.index("--repo") + 1])
            archive = repository.parent / "fake-restic-archive"
            if archive.exists():
                shutil.rmtree(archive)
            shutil.copytree(source, archive)
            self.archive = archive
            self.archived_source = source
            snapshot_id = f"{len(self.snapshots) + 1:064x}"
            tags = [command[index + 1] for index, value in enumerate(command[:-1])
                    if value == "--tag"]
            self.snapshots.append({
                "id": snapshot_id,
                "time": self.snapshot_time,
                "paths": [str(source)],
                "tags": tags,
            })
            stdout = json.dumps({"message_type": "summary", "snapshot_id": snapshot_id}) + "\n"
        elif operation == "snapshots":
            stdout = json.dumps(self.snapshots)
        elif operation == "restore":
            target = Path(command[command.index("--target") + 1])
            assert self.archive is not None and self.archived_source is not None
            restored_root = target / self.archived_source.relative_to("/")
            restored_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.archive, restored_root)
            stdout = ""
        else:
            stdout = ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


def make_sqlite(path: Path, *, user_version=7):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(f"PRAGMA user_version={int(user_version)}")
    connection.execute("CREATE TABLE IF NOT EXISTS item(value TEXT NOT NULL)")
    connection.execute("INSERT INTO item(value) VALUES ('committed')")
    connection.commit()
    connection.close()
    return path


def make_engine(tmp_path, *, runner=None, file_roots=None, rpo_hours=24,
                snapshot_time="2026-10-01T00:00:00Z", retention=None):
    source_db = make_sqlite(tmp_path / "core-state.sqlite")
    password_file = tmp_path / "restic-password"
    password_file.write_text("not-for-backup\n", encoding="utf-8")
    fake = runner or FakeRestic(snapshot_time=snapshot_time)
    config_values = dict(
        repository=tmp_path / "restic-repo",
        sqlite_stores={"core-state": source_db},
        file_roots=file_roots or {},
        password_file=password_file,
        rpo_hours=rpo_hours,
    )
    if retention is not None:
        config_values["retention"] = retention
    config = BackupConfig(**config_values)
    return BackupEngine(config, runner=fake), fake, source_db


def test_backup_uses_online_sqlite_snapshot_and_hashed_manifest(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "page.json").write_text('{"source":"official"}\n', encoding="utf-8")
    (raw / ".env.production").write_text("RESTIC_PASSWORD=VERY_SECRET_VALUE\n", encoding="utf-8")
    (raw / "fuseki-data").mkdir()
    (raw / "fuseki-data" / "tdb.dat").write_bytes(b"do not archive")
    (raw / ".venv").mkdir()
    (raw / ".venv" / "cache.bin").write_bytes(b"not durable source")

    fake = FakeRestic()
    engine, _, source_db = make_engine(tmp_path, runner=fake, file_roots={"raw": raw})
    writer = sqlite3.connect(source_db)
    writer.execute("BEGIN")
    writer.execute("INSERT INTO item(value) VALUES ('uncommitted')")

    result = engine.backup(operation_lock=nullcontext(), apply_retention=False)

    writer.commit()
    writer.close()
    assert result.snapshot_id == "0" * 63 + "1"
    assert result.sqlite_stores == 1
    assert result.files == 2
    assert "VERY_SECRET_VALUE" not in fake.archive.joinpath(MANIFEST_NAME).read_text()
    assert not (fake.archive / "data" / "files" / "raw" / ".env.production").exists()
    assert not any("tdb" in path.name.lower() for path in fake.archive.rglob("*"))

    copied_db = fake.archive / "data" / "sqlite" / "core-state.sqlite"
    connection = sqlite3.connect(copied_db)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 7
    assert connection.execute("SELECT value FROM item ORDER BY rowid").fetchall() == [
        ("committed",),
    ]
    connection.close()
    live = sqlite3.connect(source_db)
    assert live.execute("SELECT value FROM item ORDER BY rowid").fetchall() == [
        ("committed",), ("uncommitted",),
    ]
    live.close()

    manifest_bytes = (fake.archive / MANIFEST_NAME).read_bytes()
    manifest = json.loads(manifest_bytes)
    db_entry = next(item for item in manifest["files"] if item["kind"] == "sqlite")
    assert db_entry["sha256"] == hashlib.sha256(copied_db.read_bytes()).hexdigest()
    assert manifest["excluded"]["secret_files"] == 1
    assert manifest["excluded"]["fuseki_tdb_directories"] == 1
    assert manifest["excluded"]["development_directories"] == 1
    assert f"manifest-sha256:{result.manifest_sha256}" in result.tags
    assert "VERY_SECRET_VALUE" not in manifest_bytes.decode("utf-8")
    assert any("backup" in command for command, _ in fake.commands)


def test_restore_latest_stages_the_newest_snapshot_and_returns_its_full_id(tmp_path):
    engine, _fake, _source_db = make_engine(tmp_path)
    engine.backup(operation_lock=nullcontext())
    destination = tmp_path / "restore-latest"

    snapshot_id, restored = engine.restore_latest(destination)

    assert snapshot_id == "0" * 63 + "1"
    assert restored == destination
    assert (restored / MANIFEST_NAME).is_file()


def test_retention_and_status_report_integrity_and_rpo(tmp_path):
    fake = FakeRestic(snapshot_time="2026-10-01T00:00:00Z")
    engine, fake, _ = make_engine(tmp_path, runner=fake)
    result = engine.backup(operation_lock=nullcontext())

    forget_command = next(command for command, _ in fake.commands if "forget" in command)
    assert forget_command[forget_command.index("--host") + 1] == "oireachtas-etl"
    assert "--keep-daily" in forget_command
    assert forget_command[forget_command.index("--keep-daily") + 1] == "30"
    assert forget_command[forget_command.index("--keep-monthly") + 1] == "12"
    assert "--prune" in forget_command
    assert forget_command[forget_command.index("--group-by") + 1] == "host"
    assert forget_command[forget_command.index("--tag") + 1] == "oireachtas-etl"
    backup_command = next(command for command, _ in fake.commands if "backup" in command)
    assert backup_command[backup_command.index("--host") + 1] == "oireachtas-etl"

    fresh_status = engine.status(now=datetime(2026, 10, 1, 12, tzinfo=timezone.utc))
    assert fresh_status.age_seconds == 43_200
    assert fresh_status.rpo_healthy
    assert fresh_status.healthy

    boundary_status = engine.status(now=datetime(2026, 10, 2, 0, tzinfo=timezone.utc))
    assert boundary_status.age_seconds == 86_400
    assert boundary_status.rpo_healthy

    status = engine.status(now=datetime(2026, 10, 2, 1, tzinfo=timezone.utc))
    assert status.snapshot_count == 1
    assert status.latest_snapshot_id == result.snapshot_id
    assert status.age_seconds == 90_000
    assert status.rpo_seconds == 86_400
    assert not status.rpo_healthy
    assert status.repository_integrity is True
    assert status.latest_snapshot_integrity is True
    assert not status.healthy
    assert any("--read-data" in command for command, _ in fake.commands)


def test_restore_validates_snapshot_and_requires_new_destination(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "evidence.json").write_text('{"page":1}', encoding="utf-8")
    engine, fake, _ = make_engine(tmp_path, file_roots={"raw": raw})
    result = engine.backup(operation_lock=nullcontext(), apply_retention=False)

    destination = tmp_path / "restored"
    restored = engine.restore(result.snapshot_id, destination)
    assert restored == destination
    assert (restored / "files" / "raw" / "evidence.json").read_text() == '{"page":1}'
    restored_db = restored / "sqlite" / "core-state.sqlite"
    connection = sqlite3.connect(restored_db)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
    assert (restored / MANIFEST_NAME).is_file()

    marker = destination / "operator-data.txt"
    marker.write_text("must remain untouched", encoding="utf-8")
    command_count = len(fake.commands)
    with pytest.raises(BackupSafetyError, match="must not already exist"):
        engine.restore(result.snapshot_id, destination)
    assert marker.read_text(encoding="utf-8") == "must remain untouched"
    assert len(fake.commands) == command_count


def test_restore_detects_tampering_before_creating_destination(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "source.json").write_text('{"original":true}', encoding="utf-8")
    engine, fake, _ = make_engine(tmp_path, file_roots={"raw": raw})
    result = engine.backup(operation_lock=nullcontext(), apply_retention=False)
    (fake.archive / "data" / "files" / "raw" / "source.json").write_text(
        '{"tampered":true}', encoding="utf-8")

    destination = tmp_path / "must-not-exist"
    with pytest.raises(BackupIntegrityError, match="hash/size mismatch"):
        engine.restore(result.snapshot_id, destination)
    assert not destination.exists()


def test_restic_failure_is_reported_without_leaking_secret_output(tmp_path):
    fake = FakeRestic()
    fake.fail_operation = "backup"
    engine, _, _ = make_engine(tmp_path, runner=fake)

    with pytest.raises(ResticCommandError, match="restic backup exited with status 23") as caught:
        engine.backup(operation_lock=nullcontext(), apply_retention=False)
    assert "VERY_SECRET_VALUE" not in str(caught.value)
    assert "VERY_SECRET_VALUE" not in repr(caught.value)


def test_secret_like_selected_content_fails_closed_before_restic(tmp_path):
    source = tmp_path / "config"
    source.mkdir()
    (source / "runtime.yaml").write_text("password: do-not-archive-this\n", encoding="utf-8")
    fake = FakeRestic()
    engine, _, _ = make_engine(tmp_path, runner=fake, file_roots={"config": source})

    with pytest.raises(BackupSafetyError, match="secret-like assignment"):
        engine.backup(operation_lock=nullcontext(), apply_retention=False)
    assert not fake.commands


def test_backup_runs_restic_only_inside_caller_operation_lock(tmp_path):
    class TrackingLock:
        held = False

        def __enter__(self):
            assert not self.held
            self.held = True
            return self

        def __exit__(self, *_exc):
            self.held = False

    fake = FakeRestic()
    lock = TrackingLock()

    def locked_runner(command, **kwargs):
        assert lock.held
        return fake(command, **kwargs)

    engine, _, _ = make_engine(tmp_path, runner=locked_runner)
    result = engine.backup(operation_lock=lock)

    assert result.snapshot_id
    assert not lock.held
    assert {next(item for item in command if item in {"backup", "forget"})
            for command, _ in fake.commands} == {"backup", "forget"}


def test_config_helpers_cover_all_current_durable_sqlite_and_review_roots(tmp_path):
    settings = SimpleNamespace(
        core_state_db_file=tmp_path / "core.sqlite",
        reconciliation_state_db_file=tmp_path / "reconciliation.sqlite",
        raw_dir=Path("captures/raw"),
    )
    sqlite_stores = configured_sqlite_stores(settings)
    assert set(sqlite_stores) == {
        "core-state", "reconciliation", "office-occurrences", "bill-sponsors",
    }
    roots = configured_file_roots(tmp_path, settings)
    assert roots["raw-evidence"] == tmp_path.resolve() / "captures" / "raw"
    assert roots["reconciliation-reviews"] == tmp_path.resolve() / "reconciliation"
    assert roots["registries"] == tmp_path.resolve() / "registries"
    assert roots["source-code"] == tmp_path.resolve() / "src"
    assert roots["production-compose-script"] == (
        tmp_path.resolve() / "scripts" / "production-compose.sh")
    assert roots["compose-config"].name == "compose.production.yml"
    assert roots["deployment"].name == "deployment"
    assert "scripts" not in roots
    assert "documentation" not in roots


def test_restored_state_activation_reinstalls_four_validated_stores_and_preserves_old_root(
        tmp_path):
    live = tmp_path / "live"
    live.mkdir()
    settings = Settings(
        core_state_db_file=live / "core-state.sqlite",
        reconciliation_state_db_file=live / "reconciliation.sqlite",
        office_occurrence_state_db_file=live / "office-occurrences.sqlite",
        bill_sponsor_state_db_file=live / "bill-sponsors.sqlite",
        raw_dir=live / "raw",
        operation_lock_file=tmp_path / "operations.lock",
    )
    _initialize_state(settings)
    settings.raw_dir.mkdir()
    (settings.raw_dir / "source.json").write_text('{"source":"fixture"}\n', encoding="utf-8")

    password_file = tmp_path / "restic-password"
    password_file.write_text("disposable-only\n", encoding="utf-8")
    fake = FakeRestic()
    engine = BackupEngine(
        BackupConfig(
            repository=tmp_path / "restic-repository",
            sqlite_stores=configured_sqlite_stores(settings),
            file_roots={"raw-evidence": settings.raw_dir},
            password_file=password_file,
        ),
        runner=fake,
    )
    result = engine.backup(
        operation_lock=exclusive_operation_lock(settings.operation_lock_file),
        apply_retention=False,
    )
    staged = engine.restore(result.snapshot_id, tmp_path / "staged-restore")

    previous = activate_restored_state(staged, live, settings=settings)

    assert previous is not None and previous.is_dir()
    assert (previous / "raw" / "source.json").read_text(encoding="utf-8") == (
        '{"source":"fixture"}\n')
    assert (live / "raw" / "source.json").read_text(encoding="utf-8") == (
        '{"source":"fixture"}\n')
    assert {path.name for path in live.glob("*.sqlite")} == {
        "core-state.sqlite", "reconciliation.sqlite",
        "office-occurrences.sqlite", "bill-sponsors.sqlite",
    }
    for database in live.glob("*.sqlite"):
        with sqlite3.connect(database) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_etl_backup_and_restore_cli_paths_use_the_shared_operation_lock(monkeypatch, tmp_path):
    from oireachtas_etl import cli, operations, ops_cli

    lock_path = tmp_path / "operations.lock"
    settings = Settings(
        core_state_db_file=tmp_path / "live" / "core-state.sqlite",
        reconciliation_state_db_file=tmp_path / "live" / "reconciliation.sqlite",
        fuseki_gsp_url="http://fuseki.test/houses/data",
        fuseki_sparql_url="http://fuseki.test/houses/query",
        operation_lock_file=lock_path,
    )
    state = {"held": False, "paths": []}

    @contextmanager
    def tracked_lock(path):
        assert Path(path) == lock_path
        assert not state["held"]
        state["held"] = True
        state["paths"].append(Path(path))
        try:
            yield
        finally:
            state["held"] = False

    monkeypatch.setattr(cli.Settings, "from_environment", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "exclusive_operation_lock", tracked_lock)
    monkeypatch.setattr(ops_cli, "exclusive_operation_lock", tracked_lock)

    def dispatch(_args):
        assert state["held"]
        return 17

    monkeypatch.setattr(cli, "_dispatch_command", dispatch)
    assert cli._dispatch_with_operation_lock(
        SimpleNamespace(command="run", endpoint="houses")) == 17

    class LockedBackup:
        def backup(self, *, operation_lock):
            with operation_lock:
                assert state["held"]
                return BackupResult("a" * 64, "2026-10-01T00:00:00Z", "b" * 64,
                                    files=1, sqlite_stores=4, tags=("oireachtas-etl",))

    monkeypatch.setattr(ops_cli, "_backup_engine", lambda _settings: LockedBackup())
    assert ops_cli._backup_command(SimpleNamespace(backup_command="create"), settings) == 0

    def activate(_stage, _target, *, settings):
        assert state["held"]
        assert settings is not None
        return tmp_path / "previous-live"

    monkeypatch.setattr(operations, "activate_restored_state", activate)
    assert ops_cli._activate_restore(
        SimpleNamespace(
            confirm_replace_existing=True,
            staged_root=tmp_path / "staged",
            target_root=tmp_path / "live",
        ),
        settings,
    ) == 0

    reconciliation_db = settings.reconciliation_state_db_file
    reconciliation_db.parent.mkdir(parents=True, exist_ok=True)
    reconciliation_db.touch()
    registry = tmp_path / "registry.json"
    registry.write_text("{}", encoding="utf-8")

    def rebuildable(*_args, **_kwargs):
        assert state["held"]
        return []

    def rebuild(graphs, loader, client, *, allow_empty=False):
        assert state["held"]
        assert graphs == []
        assert loader == "loader"
        assert client == "client"
        assert allow_empty is True
        return {"graphs_verified": 0}

    monkeypatch.setattr(ops_cli, "validate_registry_source", lambda value: value)
    monkeypatch.setattr(ops_cli, "rebuildable_graph_payloads", rebuildable)
    monkeypatch.setattr(ops_cli, "FusekiGraphStoreLoader", lambda *_a, **_kw: "loader")
    monkeypatch.setattr(ops_cli, "FusekiSparqlClient", lambda *_a, **_kw: "client")
    monkeypatch.setattr(ops_cli, "rebuild_empty_dataset", rebuild)
    assert ops_cli._rebuild(
        SimpleNamespace(
            confirm_empty_target=True,
            state_db=None,
            reconciliation_db=None,
            registry_file=registry,
            gsp_url=None,
            sparql_url=None,
        ),
        settings,
    ) == 0

    assert state["paths"] == [lock_path, lock_path, lock_path, lock_path]
    assert not state["held"]


def test_operation_lock_serializes_writers_across_processes(tmp_path):
    lock_path = tmp_path / "operations.lock"
    child = """
import sys
from oireachtas_etl.operations import exclusive_operation_lock
print('ready', flush=True)
with exclusive_operation_lock(sys.argv[1]):
    print('acquired', flush=True)
"""

    process = None
    try:
        with exclusive_operation_lock(lock_path):
            process = subprocess.Popen(
                [sys.executable, "-c", child, str(lock_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            assert process.stdout.readline().strip() == "ready"
            time.sleep(0.1)
            assert process.poll() is None
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert stdout.strip().splitlines() == ["acquired"]
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
