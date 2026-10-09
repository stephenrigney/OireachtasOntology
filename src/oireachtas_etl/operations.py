"""Restic-backed operational backups and staged, operator-invoked restores.

The engine snapshots each configured SQLite database with SQLite's online
backup API.  Other inputs are explicit, immutable file roots.  The caller must
provide an exclusive operation-lock context that coordinates *all* writers to
the selected inputs for the duration of :meth:`BackupEngine.backup`; this
module does not create or change ETL locking semantics.

Fuseki/TDB data, secret-bearing files, and SQLite files encountered inside
ordinary file roots are never copied.  Restore always validates a complete
staged snapshot before creating a previously nonexistent destination.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit


MANIFEST_NAME = ".oir-backup-manifest-v1.json"
MANIFEST_FORMAT = "oireachtas-etl-backup"
MANIFEST_VERSION = 1
DEFAULT_BACKUP_TAG = "oireachtas-etl"

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?(?:key|token)|private[_-]?key|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature|^auth$)",
    re.IGNORECASE,
)
_SECRET_LITERAL = re.compile(
    r"(?i)(?:[\"']?(?:api[_-]?key|access[_-]?(?:key|token)|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature)"
    r"[\"']?)\s*[:=]\s*(?:"
    r"\"(?P<double>[^\"\r\n]{1,})\"|"
    r"'(?P<single>[^'\r\n]{1,})'|"
    r"(?P<bare>[A-Za-z0-9][A-Za-z0-9+/=_-]*)(?=\s*(?:[,;#}\]]|$)))"
)
_CONFIG_TEXT_SUFFIXES = frozenset({".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
                                   ".properties", ".sh", ".service", ".timer", ".txt"})
_URL_CREDENTIAL = re.compile(r"(?i)https?://[^\s/@:]+:[^\s/@]+@")
_SECRET_QUERY = re.compile(
    r"(?i)[?&](?:api[_-]?key|access[_-]?(?:key|token)|private[_-]?key|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature)=([^&#\s\"']+)"
)
_AUTH_TOKEN = re.compile(
    r"(?i:\b(?:bearer|basic))\s+"
    r"(?=[A-Za-z0-9+/=_-]{12,}\b)"
    r"(?=[A-Za-z0-9+/=_-]*[A-Z])(?=[A-Za-z0-9+/=_-]*[a-z])"
    r"[A-Za-z0-9+/=_-]{12,}\b"
)
_ENV_REFERENCE = re.compile(
    r"(?i)^(?:bearer\s+)?(?:\$\{[A-Z_][A-Z0-9_]*(?::[^}]*)?\}|\$[A-Z_][A-Z0-9_]*)$"
)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
_AWS_ACCESS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

_SECRET_FILE_NAMES = frozenset({
    ".netrc", "credentials", "credentials.json", "id_rsa", "id_ed25519",
    "id_ecdsa", "known_hosts", "restic-password", "restic-password.txt",
})
_SECRET_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".p8", ".keystore"})
_EXCLUDED_DIR_NAMES = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "dist",
})


class BackupError(RuntimeError):
    """Base class for backup, integrity, and restore failures."""


class BackupConfigurationError(BackupError):
    """The explicit backup inputs or policy are invalid."""


class BackupIntegrityError(BackupError):
    """A backup manifest, file hash, or SQLite database failed validation."""


class BackupSafetyError(BackupError):
    """An operation would use or overwrite an unsafe path."""


class ResticCommandError(BackupError):
    """Restic failed; its output is deliberately not copied into the error."""

    def __init__(self, operation: str, returncode: int | None):
        self.operation = operation
        self.returncode = returncode
        code = "could not be started" if returncode is None else f"exited with status {returncode}"
        super().__init__(f"restic {operation} {code}")


@dataclass(frozen=True)
class RetentionPolicy:
    daily: int = 30
    monthly: int = 12

    def __post_init__(self) -> None:
        if (isinstance(self.daily, bool) or isinstance(self.monthly, bool)
                or not isinstance(self.daily, int) or not isinstance(self.monthly, int)
                or self.daily < 0 or self.monthly < 0 or self.daily + self.monthly == 0):
            raise BackupConfigurationError(
                "retention must keep at least one non-negative daily or monthly point")


@dataclass(frozen=True)
class BackupConfig:
    """Explicit repository and source configuration for one backup authority.

    ``sqlite_stores`` should include Core State, ReconciliationStore, and each
    other durable SQLite store configured by the application.  ``file_roots``
    should include immutable raw evidence, review/registry inputs, and the
    required non-secret code/configuration.  Paths are never inferred from a
    broad application root.
    """

    repository: str | Path
    sqlite_stores: Mapping[str, str | Path] = field(default_factory=dict)
    file_roots: Mapping[str, str | Path] = field(default_factory=dict)
    password_file: str | Path | None = None
    restic_binary: str = "restic"
    retention: RetentionPolicy = field(default_factory=RetentionPolicy)
    rpo_hours: float = 24.0
    tag: str = DEFAULT_BACKUP_TAG
    host: str = "oireachtas-etl"
    additional_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.repository, (str, Path)) or not str(self.repository).strip():
            raise BackupConfigurationError("a non-empty restic repository is required")
        if not isinstance(self.retention, RetentionPolicy):
            raise BackupConfigurationError("retention must be a RetentionPolicy")
        if not isinstance(self.additional_tags, tuple):
            raise BackupConfigurationError("additional_tags must be a tuple of restic tags")
        if not self.restic_binary or not isinstance(self.restic_binary, str):
            raise BackupConfigurationError("restic_binary must be a non-empty executable name")
        if (isinstance(self.rpo_hours, bool) or not isinstance(self.rpo_hours, (int, float))
                or not math.isfinite(self.rpo_hours) or self.rpo_hours <= 0):
            raise BackupConfigurationError("RPO must be a positive number of hours")
        if not _valid_tag(self.tag):
            raise BackupConfigurationError("backup tag must be a non-empty simple tag")
        if not isinstance(self.host, str) or _HOST.fullmatch(self.host) is None:
            raise BackupConfigurationError("backup host must be a stable non-secret identifier")
        if any(not _valid_tag(tag) for tag in self.additional_tags):
            raise BackupConfigurationError("additional backup tags must be non-empty simple tags")
        _validate_named_paths(self.sqlite_stores, "SQLite store")
        _validate_named_paths(self.file_roots, "file root")
        if not self.sqlite_stores and not self.file_roots:
            raise BackupConfigurationError("at least one SQLite store or file root is required")


@dataclass(frozen=True)
class BackupResult:
    snapshot_id: str
    created_at: str
    manifest_sha256: str
    files: int
    sqlite_stores: int
    tags: tuple[str, ...]


@dataclass(frozen=True)
class BackupStatus:
    snapshot_count: int
    latest_snapshot_id: str | None
    latest_snapshot_time: datetime | None
    age_seconds: float | None
    rpo_seconds: float
    rpo_healthy: bool
    repository_integrity: bool | None
    latest_snapshot_integrity: bool | None
    integrity_error: str | None = None

    @property
    def healthy(self) -> bool:
        return (self.rpo_healthy and self.repository_integrity is True
                and self.latest_snapshot_integrity is True)


def configured_sqlite_stores(settings: object | None = None) -> dict[str, Path]:
    """Return the SQLite paths currently configured by this repository.

    This deliberately lists the four durable stores explicitly, so adding a
    future SQLite authority requires an intentional backup review.
    """
    from .config import (BILL_SPONSOR_STATE_DB_FILE, OFFICE_OCCURRENCE_STATE_DB_FILE,
                         Settings)

    effective = settings if settings is not None else Settings.from_environment()
    return {
        "core-state": Path(effective.core_state_db_file),
        "reconciliation": Path(effective.reconciliation_state_db_file),
        "office-occurrences": Path(getattr(
            effective, "office_occurrence_state_db_file", OFFICE_OCCURRENCE_STATE_DB_FILE)),
        "bill-sponsors": Path(getattr(
            effective, "bill_sponsor_state_db_file", BILL_SPONSOR_STATE_DB_FILE)),
    }


def configured_file_roots(project_root: str | Path,
                          settings: object | None = None) -> dict[str, Path]:
    """Build a reviewable set of raw, review, registry, code and config roots.

    The returned paths remain explicit inputs to ``BackupConfig``.  Runtime
    secrets such as ``.env`` files and credentials are excluded by the engine.
    Human documentation is intentionally excluded: it is version-controlled
    release material, not canonical data required to restore durable ETL state,
    and its runnable examples may contain intentionally disposable credentials.
    """
    from .config import Settings

    effective = settings if settings is not None else Settings.from_environment()
    root = Path(project_root).expanduser().resolve()
    raw_root = Path(effective.raw_dir).expanduser()
    if not raw_root.is_absolute():
        raw_root = root / raw_root
    roots = {
        "raw-evidence": raw_root,
        "source-code": root / "src",
        "tools": root / "tools",
        "ontology": root / "ontology",
        "mappings": root / "mappings",
        "reconciliation-reviews": root / "reconciliation",
        "registries": root / "registries",
        "production-compose-script": root / "scripts" / "production-compose.sh",
        "deployment": root / "deployment",
        "project-readme": root / "README.md",
        "agent-guidance": root / "AGENTS.md",
        "pyproject": root / "pyproject.toml",
        "uv-lock": root / "uv.lock",
        "mise-config": root / "mise.toml",
        "compose-config": root / "compose.production.yml",
        "dockerfile": root / "Dockerfile",
        "build-info": root / "BUILD_INFO",
    }
    # The review/registry directory roots contain their configured individual
    # files; listing both levels would duplicate archive contents.
    return roots


@contextmanager
def exclusive_operation_lock(path: str | Path):
    """Serialize ETL/reconciliation writers with coordinated backup snapshots.

    Production must set the same mounted lock path for every ETL invocation
    and every backup command. This is an advisory host-local POSIX lock, not a
    second state store or cross-host coordination mechanism.
    """
    lock_path = Path(path).expanduser()
    if not lock_path.is_absolute():
        raise BackupConfigurationError("operation lock path must be absolute")
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    except OSError as error:
        raise BackupSafetyError("cannot open the configured ETL operation lock") from error
    try:
        os.fchmod(descriptor, 0o600)
        try:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        except OSError as error:
            raise BackupSafetyError("cannot acquire the configured ETL operation lock") from error
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(descriptor)


def default_backup_config(repository: str | Path, project_root: str | Path, *,
                          settings: object | None = None,
                          password_file: str | Path | None = None,
                          retention: RetentionPolicy | None = None,
                          rpo_hours: float = 24.0) -> BackupConfig:
    """Create a default explicit plan without initializing a repository or running it."""
    return BackupConfig(
        repository=repository,
        sqlite_stores=configured_sqlite_stores(settings),
        file_roots=configured_file_roots(project_root, settings),
        password_file=password_file,
        retention=retention or RetentionPolicy(),
        rpo_hours=rpo_hours,
    )


class BackupEngine:
    """Create, inspect, retain, and stage-restore encrypted restic snapshots."""

    def __init__(self, config: BackupConfig, *,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 environment: Mapping[str, str] | None = None):
        self.config = config
        self._runner = runner
        self._environment = dict(os.environ if environment is None else environment)
        self._repository = _repository_string(config.repository)
        self._password_file = _optional_path(config.password_file)
        if self._password_file is not None:
            if not self._password_file.is_file():
                raise BackupConfigurationError("restic password file is not a regular file")
            self._password_file = self._password_file.resolve()
        if self._password_file is None and not self._environment.get("RESTIC_PASSWORD"):
            raise BackupConfigurationError(
                "provide a restic password file or RESTIC_PASSWORD in the process environment")
        self._validate_tags()

    def initialize_repository(self) -> None:
        """Explicitly initialize an encrypted repository; never called implicitly."""
        self._run("init", ["init"])

    def backup(self, *, operation_lock: AbstractContextManager,
               apply_retention: bool = True) -> BackupResult:
        """Snapshot all configured inputs while the caller's exclusive lock is held.

        The lock must coordinate all writers to these sources.  It is acquired
        before any source read and released only after the repository snapshot
        and requested retention operation have completed.
        """
        if operation_lock is None or not hasattr(operation_lock, "__enter__"):
            raise BackupConfigurationError("backup requires a caller-provided operation lock")
        with operation_lock:
            roots = self._resolve_inputs()
            with tempfile.TemporaryDirectory(prefix="oireachtas-backup-") as temporary:
                payload = Path(temporary) / "payload"
                data = payload / "data"
                data.mkdir(parents=True)
                entries, exclusions = self._stage_inputs(roots, data)
                if not entries:
                    raise BackupConfigurationError("backup inputs contain no durable files")
                created_at = _timestamp(datetime.now(timezone.utc))
                manifest = {
                    "format": MANIFEST_FORMAT,
                    "format_version": MANIFEST_VERSION,
                    "created_at": created_at,
                    "files": sorted(entries, key=lambda item: item["path"]),
                    "excluded": exclusions,
                }
                manifest_bytes = _canonical_json(manifest)
                manifest_hash = _sha256(manifest_bytes)
                (payload / MANIFEST_NAME).write_bytes(manifest_bytes)
                tags = self._snapshot_tags(manifest_hash)
                args = ["backup", "--json", "--host", self.config.host]
                for tag in tags:
                    args.extend(("--tag", tag))
                args.append(str(payload))
                completed = self._run("backup", args)
                snapshot_id = _snapshot_id_from_backup(completed.stdout)
                if snapshot_id is None:
                    snapshot_id = self._find_snapshot_for_manifest(manifest_hash)
                if snapshot_id is None:
                    raise BackupIntegrityError(
                        "restic completed backup without returning its snapshot identifier")
                if apply_retention:
                    self.apply_retention()
                return BackupResult(
                    snapshot_id=snapshot_id,
                    created_at=created_at,
                    manifest_sha256=manifest_hash,
                    files=len(entries),
                    sqlite_stores=sum(item["kind"] == "sqlite" for item in entries),
                    tags=tags,
                )

    def apply_retention(self) -> None:
        """Apply the configured daily/monthly policy only to this backup tag."""
        policy = self.config.retention
        args = ["forget", "--tag", self.config.tag, "--host", self.config.host,
                # Backup paths are temporary and therefore vary by run.  Use
                # one host-scoped retention group rather than restic's default
                # host+path grouping, which would retain every temp path.
                "--group-by", "host",
                "--keep-daily", str(policy.daily),
                "--keep-monthly", str(policy.monthly), "--prune"]
        self._run("forget", args)

    def list_snapshots(self) -> list[dict[str, Any]]:
        """List this deployment's retained recovery-point identifiers only."""
        snapshots = sorted(self._snapshots(), key=lambda item: _snapshot_time(item["time"]))
        return [{"snapshot_id": item["id"], "created_at": _timestamp(_snapshot_time(item["time"]))}
                for item in snapshots]

    def check_repository(self, *, read_data: bool = True) -> None:
        """Run restic's repository integrity check, optionally reading all pack data."""
        args = ["check"]
        if read_data:
            args.append("--read-data")
        self._run("check", args)

    def status(self, *, now: datetime | None = None,
               check_integrity: bool = True,
               verify_latest_snapshot: bool = True) -> BackupStatus:
        """Report latest snapshot age/RPO and integrity-check results.

        The default integrity check reads repository pack data and separately
        restores/verifies the latest snapshot's manifest, hashes, and SQLite
        databases.  Set either check flag to false only for a deliberately
        lighter-weight status probe.
        """
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise BackupConfigurationError("status timestamp must include a timezone")
        instant = instant.astimezone(timezone.utc)
        snapshots = self._snapshots()
        snapshots = sorted(snapshots, key=lambda item: _snapshot_time(item["time"]))
        threshold = float(self.config.rpo_hours) * 3600.0
        if not snapshots:
            repository_integrity: bool | None = None
            error_text = None
            if check_integrity:
                try:
                    self.check_repository(read_data=True)
                    repository_integrity = True
                except ResticCommandError as error:
                    repository_integrity = False
                    error_text = str(error)
            return BackupStatus(
                snapshot_count=0, latest_snapshot_id=None, latest_snapshot_time=None,
                age_seconds=None, rpo_seconds=threshold, rpo_healthy=False,
                repository_integrity=repository_integrity,
                latest_snapshot_integrity=None, integrity_error=error_text)

        latest = snapshots[-1]
        latest_time = _snapshot_time(latest["time"])
        age = (instant - latest_time).total_seconds()
        rpo_healthy = 0.0 <= age <= threshold
        repo_ok: bool | None = None
        snapshot_ok: bool | None = None
        error_text = None
        if check_integrity:
            try:
                self.check_repository(read_data=True)
                repo_ok = True
            except ResticCommandError as error:
                repo_ok = False
                error_text = str(error)
        if verify_latest_snapshot and (repo_ok is not False):
            try:
                with tempfile.TemporaryDirectory(prefix="oireachtas-restore-check-") as temporary:
                    self._restore_and_validate(latest, Path(temporary))
                snapshot_ok = True
            except (ResticCommandError, BackupIntegrityError, BackupSafetyError) as error:
                snapshot_ok = False
                error_text = str(error)
        return BackupStatus(
            snapshot_count=len(snapshots),
            latest_snapshot_id=str(latest["id"]),
            latest_snapshot_time=latest_time,
            age_seconds=age,
            rpo_seconds=threshold,
            rpo_healthy=rpo_healthy,
            repository_integrity=repo_ok,
            latest_snapshot_integrity=snapshot_ok,
            integrity_error=error_text,
        )

    def restore(self, snapshot_id: str, destination: str | Path) -> Path:
        """Restore one explicitly selected snapshot into a new destination directory.

        The destination must not exist.  Restic writes to a private temporary
        staging directory first; manifest, file hashes, and SQLite integrity are
        validated before the destination is created.  This method has no
        automatic production-root detection or overwrite mode by design.
        """
        if not isinstance(snapshot_id, str) or not re.fullmatch(r"[0-9a-fA-F]{8,64}", snapshot_id):
            raise BackupConfigurationError("restore requires an explicit restic snapshot ID")
        target = Path(destination).expanduser()
        if target.exists() or target.is_symlink():
            raise BackupSafetyError("restore destination must not already exist")
        target_abs = target.resolve(strict=False)
        roots = self._resolve_inputs()
        self._check_destination(target_abs, roots)
        snapshots = self._snapshots()
        selected_matches = [item for item in snapshots
                            if str(item.get("id", "")).lower().startswith(snapshot_id.lower())]
        if not selected_matches:
            raise BackupConfigurationError("snapshot ID is not present in this backup repository")
        if len(selected_matches) != 1:
            raise BackupConfigurationError("snapshot ID prefix is ambiguous; provide a longer ID")
        selected = selected_matches[0]
        with tempfile.TemporaryDirectory(prefix="oireachtas-restore-") as temporary:
            manifest, data_dir = self._restore_and_validate(selected, Path(temporary))
            # Verify again immediately before installation.  Restic snapshot
            # metadata carries the manifest digest as a tag, anchoring the
            # content-level file manifest to the encrypted repository snapshot.
            manifest_bytes = (data_dir.parent / MANIFEST_NAME).read_bytes()
            _validate_manifest_anchor(selected, manifest_bytes)
            try:
                target_abs.parent.mkdir(parents=True, exist_ok=True)
                target_abs.mkdir(mode=0o700)
            except FileExistsError as error:
                raise BackupSafetyError(
                    "restore destination appeared during validation; refusing to overwrite") from error
            try:
                for entry in manifest["files"]:
                    relative = _manifest_relative_path(entry["path"])
                    source = data_dir.joinpath(*relative.parts)
                    output = target_abs.joinpath(*relative.parts)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    if output.exists() or output.is_symlink():
                        raise BackupSafetyError("restore output path collision")
                    shutil.copy2(source, output)
                manifest_output = target_abs / MANIFEST_NAME
                with manifest_output.open("xb") as handle:
                    handle.write(manifest_bytes)
            except BaseException:
                # Remove only the fresh directory created above; never touch a
                # destination that existed before the restore request.
                shutil.rmtree(target_abs, ignore_errors=True)
                raise
        return target_abs

    def _validate_tags(self) -> None:
        tags = self._snapshot_tags("0" * 64)
        if len(tags) != len(set(tags)):
            raise BackupConfigurationError("backup tags must be unique")

    def _snapshot_tags(self, manifest_hash: str) -> tuple[str, ...]:
        return (self.config.tag, *self.config.additional_tags,
                f"manifest-sha256:{manifest_hash}")

    def _resolve_inputs(self) -> dict[str, dict[str, Path]]:
        sqlite_paths = _resolved_named_paths(self.config.sqlite_stores, "SQLite store")
        file_paths = _resolved_named_paths(self.config.file_roots, "file root")
        for label, path in sqlite_paths.items():
            if not path.is_file():
                raise BackupConfigurationError(f"SQLite store {label!r} is not an existing file")
            if _contains_tdb_component(path):
                raise BackupSafetyError("Fuseki/TDB paths cannot be backup inputs")
        for label, path in file_paths.items():
            if not path.exists() or path.is_symlink():
                raise BackupConfigurationError(f"file root {label!r} is missing or is a symlink")
            if not (path.is_file() or path.is_dir()):
                raise BackupConfigurationError(f"file root {label!r} must be a regular file or directory")
            if _contains_tdb_component(path):
                raise BackupSafetyError("Fuseki/TDB paths cannot be backup inputs")
            if path.name.lower() in _EXCLUDED_DIR_NAMES or _is_secret_filename(path.name):
                raise BackupSafetyError(f"unsafe file-root path for {label!r}")
            if path.is_file() and _is_secret_filename(path.name):
                raise BackupSafetyError(f"secret-bearing file root {label!r} is not permitted")
        self._validate_repository_separation(sqlite_paths, file_paths)
        if self._password_file is not None:
            for path in (*sqlite_paths.values(), *file_paths.values()):
                if _paths_overlap(path, self._password_file):
                    raise BackupSafetyError("restic password file overlaps backup input")
        return {"sqlite": sqlite_paths, "files": file_paths}

    def _validate_repository_separation(self, sqlite_paths: Mapping[str, Path],
                                        file_paths: Mapping[str, Path]) -> None:
        for sqlite_path in sqlite_paths.values():
            for file_root in file_paths.values():
                if file_root.is_dir() and _is_relative_to(sqlite_path, file_root):
                    raise BackupSafetyError(
                        "SQLite stores must not be included in ordinary file roots; use online backup")
                if _paths_overlap(sqlite_path, file_root):
                    raise BackupSafetyError("SQLite store and file-root inputs overlap")
        local_repo = _local_repository_path(self._repository)
        if local_repo is not None:
            for source in (*sqlite_paths.values(), *file_paths.values()):
                if _paths_overlap(local_repo, source):
                    raise BackupSafetyError("restic repository must be outside backup source roots")
            if self._password_file is not None and _paths_overlap(local_repo, self._password_file):
                raise BackupSafetyError("restic password file must be outside the repository")

    def _stage_inputs(self, roots: Mapping[str, Mapping[str, Path]], data: Path
                      ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        entries: list[dict[str, Any]] = []
        exclusions = {"secret_files": 0, "metadata_sidecars": 0,
                      "development_directories": 0,
                      "fuseki_tdb_directories": 0}
        for label, source in sorted(roots["sqlite"].items()):
            target = data / "sqlite" / f"{label}.sqlite"
            target.parent.mkdir(parents=True, exist_ok=True)
            user_version = _sqlite_online_snapshot(source, target)
            entries.append(_manifest_file(target, data, kind="sqlite", label=label,
                                          sqlite_user_version=user_version))
        for label, source in sorted(roots["files"].items()):
            for path, relative, exclusion in _walk_file_root(source):
                if exclusion is not None:
                    if exclusion == "sqlite-file":
                        raise BackupSafetyError(
                            f"SQLite file {path.name!r} must be configured for online backup")
                    exclusions[exclusion] += 1
                    continue
                if path.name == MANIFEST_NAME:
                    raise BackupSafetyError("file root uses the reserved backup manifest filename")
                if _sqlite_file_name(path.name):
                    raise BackupSafetyError(
                        f"SQLite file {path.name!r} must be configured for online backup")
                target = data / "files" / label / Path(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_regular_file(path, target)
                _validate_file_secrets(target, label)
                entries.append(_manifest_file(target, data, kind="file", label=label))
        return entries, exclusions

    def _run(self, operation: str, args: list[str], *,
             cwd: str | Path | None = None) -> subprocess.CompletedProcess:
        command = [self.config.restic_binary, "--repo", self._repository]
        if self._password_file is not None:
            command.extend(("--password-file", str(self._password_file)))
        command.extend(args)
        try:
            completed = self._runner(
                command, capture_output=True, text=True, env=dict(self._environment),
                cwd=None if cwd is None else str(cwd), check=False)
        except (OSError, subprocess.SubprocessError) as error:
            raise ResticCommandError(operation, None) from error
        if completed.returncode != 0:
            raise ResticCommandError(operation, completed.returncode)
        return completed

    def _snapshots(self) -> list[dict[str, Any]]:
        completed = self._run("snapshots", ["snapshots", "--json", "--tag", self.config.tag,
                                             "--host", self.config.host])
        try:
            value = json.loads(completed.stdout or "[]")
        except (TypeError, json.JSONDecodeError) as error:
            raise BackupIntegrityError("restic returned invalid snapshot-list JSON") from error
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise BackupIntegrityError("restic snapshot list has an unexpected structure")
        if any(not _valid_snapshot_record(item) for item in value):
            raise BackupIntegrityError("restic snapshot list contains an invalid snapshot record")
        return [item for item in value if self.config.tag in item["tags"]]

    def _find_snapshot_for_manifest(self, manifest_hash: str) -> str | None:
        tag = f"manifest-sha256:{manifest_hash}"
        matches = [item for item in self._snapshots() if tag in item.get("tags", [])]
        if not matches:
            return None
        latest = max(matches, key=lambda item: _snapshot_time(item["time"]))
        return str(latest["id"])

    def _restore_and_validate(self, snapshot: Mapping[str, Any], target: Path
                              ) -> tuple[dict[str, Any], Path]:
        snapshot_id = str(snapshot.get("id", ""))
        self._run("restore", ["restore", snapshot_id, "--target", str(target)])
        manifests = [path for path in target.rglob(MANIFEST_NAME) if path.is_file()]
        if len(manifests) != 1:
            raise BackupIntegrityError("restored snapshot must contain exactly one backup manifest")
        manifest_path = manifests[0]
        if manifest_path.is_symlink():
            raise BackupIntegrityError("restored backup manifest must not be a symlink")
        manifest_bytes = manifest_path.read_bytes()
        _validate_manifest_anchor(snapshot, manifest_bytes)
        manifest = _parse_manifest(manifest_bytes)
        data = manifest_path.parent / "data"
        if not data.is_dir() or data.is_symlink():
            raise BackupIntegrityError("restored snapshot data directory is unavailable")
        _validate_manifest_files(manifest, data)
        return manifest, data

    def _check_destination(self, destination: Path,
                           roots: Mapping[str, Mapping[str, Path]]) -> None:
        if _contains_tdb_component(destination):
            raise BackupSafetyError("Fuseki/TDB paths are not valid restore destinations")
        for source in (*roots["sqlite"].values(), *roots["files"].values()):
            if _paths_overlap(destination, source):
                raise BackupSafetyError("restore destination overlaps a live backup source")
        local_repo = _local_repository_path(self._repository)
        if local_repo is not None and _paths_overlap(destination, local_repo):
            raise BackupSafetyError("restore destination overlaps the restic repository")
        if self._password_file is not None and _paths_overlap(destination, self._password_file):
            raise BackupSafetyError("restore destination overlaps the restic password file")


def _validate_named_paths(values: Mapping[str, str | Path], label: str) -> None:
    if not isinstance(values, Mapping):
        raise BackupConfigurationError(f"{label} inputs must be a mapping of labels to paths")
    for name, path in values.items():
        if (not isinstance(name, str) or _LABEL.fullmatch(name) is None
                or _SENSITIVE_KEY.search(name)):
            raise BackupConfigurationError(f"invalid {label} label")
        if not isinstance(path, (str, Path)) or not str(path).strip():
            raise BackupConfigurationError(f"{label} {name!r} must have an explicit path")


def _valid_tag(tag: object) -> bool:
    return (isinstance(tag, str) and _TAG.fullmatch(tag) is not None
            and not _SENSITIVE_KEY.search(tag)
            and not tag.startswith("manifest-sha256:"))


def _resolved_named_paths(values: Mapping[str, str | Path], label: str) -> dict[str, Path]:
    _validate_named_paths(values, label)
    result: dict[str, Path] = {}
    for name, path_value in values.items():
        original = Path(path_value).expanduser()
        if original.is_symlink():
            raise BackupSafetyError(f"{label} {name!r} must not be a symlink")
        try:
            resolved = original.resolve(strict=True)
        except OSError as error:
            raise BackupConfigurationError(f"{label} {name!r} does not exist") from error
        if _contains_tdb_component(resolved):
            raise BackupSafetyError("Fuseki/TDB paths cannot be backup inputs")
        result[name] = resolved
    return result


def _optional_path(value: str | Path | None) -> Path | None:
    return None if value is None else Path(value).expanduser()


def _repository_string(value: str | Path) -> str:
    repository = os.fspath(value).strip()
    if not repository or any(ord(character) < 32 or ord(character) == 127
                             for character in repository):
        raise BackupConfigurationError("restic repository must be a non-empty location")
    if _URL_CREDENTIAL.search(repository):
        raise BackupSafetyError("restic repository location must not embed credentials")
    try:
        parsed = urlsplit(repository)
    except ValueError as error:
        raise BackupConfigurationError("restic repository location is invalid") from error
    if (parsed.username is not None or parsed.password is not None
            or any(_SENSITIVE_KEY.search(key.replace(" ", ""))
                   for key, _ in parse_qsl(parsed.query, keep_blank_values=True))):
        raise BackupSafetyError("restic repository location must not embed credentials")
    return repository


def _local_repository_path(repository: str) -> Path | None:
    if re.match(r"(?i)^(?:s3|sftp|rest|rclone|azure|gs|b2):", repository):
        return None
    return Path(repository).expanduser().resolve(strict=False)


def _contains_tdb_component(path: Path) -> bool:
    for component in path.parts:
        lowered = component.lower()
        if "fuseki" in lowered or lowered in {"tdb", "tdb2"} or lowered.startswith("tdb-"):
            return True
    return False


def _is_secret_filename(name: str) -> bool:
    lowered = name.lower()
    if (lowered in _SECRET_FILE_NAMES or lowered.startswith(".env")
            or lowered.endswith(tuple(_SECRET_SUFFIXES))):
        return True
    return any(part in lowered for part in ("secret", "credential", "private-key"))


def _sqlite_file_name(name: str) -> bool:
    lowered = name.lower()
    return (lowered.endswith((".sqlite", ".sqlite3", ".db"))
            or re.search(r"\.(?:sqlite3?|db)-(?:wal|shm|journal)\Z", lowered) is not None)


def _walk_file_root(root: Path):
    if root.is_file():
        yield root, PurePosixPath(root.name), None
        return
    def on_error(error: OSError) -> None:
        raise BackupError("could not enumerate a configured backup file root") from error

    for current, directories, filenames in os.walk(
            root, topdown=True, onerror=on_error, followlinks=False):
        current_path = Path(current)
        retained = []
        for name in sorted(directories):
            path = current_path / name
            if path.is_symlink():
                raise BackupSafetyError("symlink directories are not allowed in backup inputs")
            lowered = name.lower()
            if lowered in _EXCLUDED_DIR_NAMES:
                yield path, PurePosixPath(name), "development_directories"
                continue
            if _is_secret_filename(name):
                yield path, PurePosixPath(name), "secret_files"
                continue
            if "fuseki" in lowered or lowered in {"tdb", "tdb2"} or lowered.startswith("tdb-"):
                yield path, PurePosixPath(name), "fuseki_tdb_directories"
                continue
            retained.append(name)
        directories[:] = retained
        for name in sorted(filenames):
            path = current_path / name
            if path.is_symlink():
                raise BackupSafetyError("symlink files are not allowed in backup inputs")
            if name.lower().endswith(":zone.identifier"):
                yield path, PurePosixPath(name), "metadata_sidecars"
                continue
            if _is_secret_filename(name):
                yield path, PurePosixPath(name), "secret_files"
                continue
            if _sqlite_file_name(name):
                yield path, PurePosixPath(name), "sqlite-file"
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            yield path, relative, None


def _copy_regular_file(source: Path, target: Path) -> None:
    try:
        metadata = source.lstat()
    except OSError as error:
        raise BackupError("backup source changed or became unavailable") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise BackupSafetyError("only regular files may be included in a backup")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target, follow_symlinks=False)
    except OSError as error:
        raise BackupError("could not copy a configured backup file") from error


def _validate_file_secrets(path: Path, label: str) -> None:
    def validate_text(text: str) -> None:
        if (_URL_CREDENTIAL.search(text) or _AUTH_TOKEN.search(text) or _PRIVATE_KEY.search(text)
                or _AWS_ACCESS_KEY.search(text)):
            raise BackupSafetyError(f"configured {label!r} input contains secret-like content")
        for match in _SECRET_QUERY.finditer(text):
            if not _ENV_REFERENCE.fullmatch(match.group(1)):
                raise BackupSafetyError(f"configured {label!r} input contains a secret-like URL")
        for match in _SECRET_LITERAL.finditer(text):
            value = match.group("double") or match.group("single") or match.group("bare")
            if match.group("bare") is not None and path.suffix.lower() not in _CONFIG_TEXT_SUFFIXES:
                continue
            lowered = value.lower()
            if (_ENV_REFERENCE.fullmatch(value.strip())
                    or value.startswith(("$", "{{", "<"))
                    or lowered.startswith(("os.getenv", "settings.", "process.env", "env("))
                    or lowered in {"none", "null", "false", "true", "redacted", "placeholder",
                                   "changeme", "change-me", "example"}
                    or lowered.startswith(("your_", "your-", "replace-me"))):
                continue
            raise BackupSafetyError(
                f"configured {label!r} input contains a secret-like assignment")

    try:
        with path.open("rb") as handle:
            tail = b""
            while chunk := handle.read(1024 * 1024):
                if b"\x00" in chunk:
                    raise BackupSafetyError(
                        f"configured {label!r} input is binary and cannot be secret-validated")
                combined = tail + chunk
                validate_text(combined.decode("utf-8", errors="replace"))
                tail = combined[-4096:]
    except OSError as error:
        raise BackupError(f"could not validate configured {label!r} backup file") from error


def _sqlite_online_snapshot(source: Path, target: Path) -> int:
    source_connection: sqlite3.Connection | None = None
    target_connection: sqlite3.Connection | None = None
    try:
        source_connection = sqlite3.connect(
            source.as_uri() + "?mode=ro", uri=True, timeout=30)
        source_connection.execute("PRAGMA busy_timeout=30000")
        source_check = source_connection.execute("PRAGMA integrity_check").fetchone()
        if source_check is None or source_check[0] != "ok":
            raise BackupIntegrityError("source SQLite integrity_check failed")
        user_version = int(source_connection.execute("PRAGMA user_version").fetchone()[0])
        target.parent.mkdir(parents=True, exist_ok=True)
        target_connection = sqlite3.connect(target, timeout=30)
        source_connection.backup(target_connection, pages=256, sleep=0.01)
        # The online copy inherits the source's WAL-mode header.  Canonicalize
        # the self-contained backup file to rollback-journal mode so read-only
        # verification/restoration cannot create unmanifested -wal/-shm files.
        journal_mode = target_connection.execute("PRAGMA journal_mode=DELETE").fetchone()
        if journal_mode is None or str(journal_mode[0]).lower() != "delete":
            raise BackupIntegrityError("SQLite backup could not be made self-contained")
        target_check = target_connection.execute("PRAGMA integrity_check").fetchone()
        if target_check is None or target_check[0] != "ok":
            raise BackupIntegrityError("online SQLite snapshot integrity_check failed")
        if int(target_connection.execute("PRAGMA user_version").fetchone()[0]) != user_version:
            raise BackupIntegrityError("online SQLite snapshot schema version changed")
        target.chmod(stat.S_IMODE(source.stat().st_mode))
        return user_version
    except sqlite3.Error as error:
        raise BackupError(f"SQLite online backup failed for configured store {source.name!r}") from error
    finally:
        if target_connection is not None:
            target_connection.close()
        if source_connection is not None:
            source_connection.close()


def _manifest_file(path: Path, data_root: Path, *, kind: str, label: str,
                   sqlite_user_version: int | None = None) -> dict[str, Any]:
    metadata = path.stat()
    entry: dict[str, Any] = {
        "path": path.relative_to(data_root).as_posix(),
        "kind": kind,
        "label": label,
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "mtime_ns": metadata.st_mtime_ns,
        "sha256": _file_sha256(path),
    }
    if sqlite_user_version is not None:
        entry["sqlite_user_version"] = sqlite_user_version
    return entry


def _manifest_relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or "\\" in value:
        raise BackupIntegrityError("backup manifest contains an invalid relative file path")
    path = PurePosixPath(value)
    if (path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts)
            or ":" in path.parts[0]):
        raise BackupIntegrityError("backup manifest path escapes its data root")
    return path


def _parse_manifest(payload: bytes) -> dict[str, Any]:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate manifest key")
            result[key] = value
        return result

    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise BackupIntegrityError("backup manifest is invalid JSON") from error
    if (not isinstance(value, dict)
            or set(value) != {"format", "format_version", "created_at", "files", "excluded"}
            or value.get("format") != MANIFEST_FORMAT
            or value.get("format_version") != MANIFEST_VERSION
            or not isinstance(value.get("created_at"), str)
            or not isinstance(value.get("files"), list)
            or not value.get("files")
            or not isinstance(value.get("excluded"), dict)):
        raise BackupIntegrityError("backup manifest has an unsupported structure")
    try:
        _parse_timestamp(value["created_at"])
    except (TypeError, ValueError) as error:
        raise BackupIntegrityError("backup manifest timestamp is invalid") from error
    return value


def _validate_manifest_anchor(snapshot: Mapping[str, Any], payload: bytes) -> None:
    tags = snapshot.get("tags")
    if not isinstance(tags, list):
        raise BackupIntegrityError("restic snapshot has no tag metadata")
    anchors = [tag.partition(":")[2] for tag in tags
               if isinstance(tag, str) and tag.startswith("manifest-sha256:")]
    if len(anchors) != 1 or _SHA256.fullmatch(anchors[0]) is None:
        raise BackupIntegrityError("restic snapshot does not have one valid manifest hash anchor")
    if _sha256(payload) != anchors[0]:
        raise BackupIntegrityError("backup manifest hash does not match its restic snapshot tag")


def _validate_manifest_files(manifest: Mapping[str, Any], data: Path) -> None:
    entries = manifest["files"]
    expected: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise BackupIntegrityError("backup manifest file entry is invalid")
        path = _manifest_relative_path(entry.get("path"))
        relative = path.as_posix()
        if relative in expected:
            raise BackupIntegrityError("backup manifest contains duplicate file paths")
        expected.add(relative)
        kind = entry.get("kind")
        label = entry.get("label")
        if kind not in {"file", "sqlite"} or not isinstance(label, str) or _LABEL.fullmatch(label) is None:
            raise BackupIntegrityError("backup manifest file classification is invalid")
        required_fields = {"path", "kind", "label", "size", "mode", "mtime_ns", "sha256"}
        if kind == "sqlite":
            required_fields.add("sqlite_user_version")
        if set(entry) != required_fields:
            raise BackupIntegrityError("backup manifest file metadata fields are invalid")
        if kind == "sqlite":
            if (path.parts != ("sqlite", f"{label}.sqlite")
                    or isinstance(entry.get("sqlite_user_version"), bool)
                    or not isinstance(entry.get("sqlite_user_version"), int)):
                raise BackupIntegrityError("backup manifest SQLite entry is invalid")
        elif len(path.parts) < 3 or path.parts[:2] != ("files", label):
            raise BackupIntegrityError("backup manifest file entry is outside its labeled root")
        elif _sqlite_file_name(path.name):
            raise BackupIntegrityError("SQLite content must use a manifested online-backup entry")
        if (isinstance(entry.get("size"), bool) or not isinstance(entry.get("size"), int)
                or entry["size"] < 0 or isinstance(entry.get("mode"), bool)
                or not isinstance(entry.get("mode"), int) or entry["mode"] < 0
                or isinstance(entry.get("mtime_ns"), bool)
                or not isinstance(entry.get("mtime_ns"), int)
                or not isinstance(entry.get("sha256"), str)
                or _SHA256.fullmatch(entry["sha256"]) is None):
            raise BackupIntegrityError("backup manifest file metadata is invalid")
        target = data.joinpath(*path.parts)
        try:
            metadata = target.lstat()
        except OSError as error:
            raise BackupIntegrityError("backup snapshot is missing a manifested file") from error
        if not stat.S_ISREG(metadata.st_mode) or target.is_symlink():
            raise BackupIntegrityError("backup snapshot contains a non-regular manifested file")
        if metadata.st_size != entry["size"] or _file_sha256(target) != entry["sha256"]:
            raise BackupIntegrityError(f"backup file hash/size mismatch at {relative}")
        if kind == "sqlite":
            _validate_sqlite_file(target, entry["sqlite_user_version"])
    actual: set[str] = set()
    for current, directories, filenames in os.walk(data, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in directories:
            if (current_path / name).is_symlink():
                raise BackupIntegrityError("backup snapshot contains a symlink directory")
        for name in filenames:
            path = current_path / name
            if path.is_symlink() or not path.is_file():
                raise BackupIntegrityError("backup snapshot contains an unsafe file")
            actual.add(path.relative_to(data).as_posix())
    # A fully restored staged tree also has the manifest at its root; it is
    # anchored by the Restic snapshot tag and is not one of the payload files.
    if (data / MANIFEST_NAME).is_file() and (data / MANIFEST_NAME).is_relative_to(data):
        actual.discard(MANIFEST_NAME)
    if actual != expected:
        raise BackupIntegrityError("backup snapshot file inventory differs from its manifest")
    excluded = manifest["excluded"]
    if (set(excluded) != {"secret_files", "metadata_sidecars", "development_directories",
                          "fuseki_tdb_directories"}
            or any(not isinstance(value, int) or isinstance(value, bool) or value < 0
                   for value in excluded.values())):
        raise BackupIntegrityError("backup manifest exclusion counters are invalid")


def activate_restored_state(staged_root: str | Path, target_root: str | Path, *,
                            settings: object) -> Path | None:
    """Install restored durable SQLite/raw state with a rollback directory.

    The caller must hold the same exclusive operation lock as ETL and backup
    commands and must stop/refrain from starting scheduled ETL while the
    operator performs the restore. Existing state is renamed aside and kept;
    it is never recursively deleted by this routine.
    """
    from .config import Settings
    if not isinstance(settings, Settings):
        raise BackupConfigurationError("restore activation requires validated application settings")
    stage = Path(staged_root).expanduser().resolve(strict=True)
    if stage.is_symlink() or not stage.is_dir():
        raise BackupSafetyError("staged restore root must be a regular directory")
    target_input = Path(target_root).expanduser()
    target = target_input.resolve(strict=False)
    expected_target = Path(settings.core_state_db_file).expanduser().parent.resolve(strict=False)
    if target != expected_target:
        raise BackupSafetyError("restore target must be the configured Core State directory")
    if stage == target or _paths_overlap(stage, target):
        raise BackupSafetyError("staged restore and live durable-state paths must be separate")
    if target.exists() and (target.is_symlink() or not target.is_dir()):
        raise BackupSafetyError("live durable-state target must be a directory, not a symlink")

    manifest_path = stage / MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BackupIntegrityError("staged restore has no regular backup manifest")
    manifest_bytes = manifest_path.read_bytes()
    manifest = _parse_manifest(manifest_bytes)
    _validate_manifest_files(manifest, stage)

    store_paths = configured_sqlite_stores(settings)
    required_labels = {"core-state", "reconciliation", "office-occurrences", "bill-sponsors"}
    entries = {entry["label"]: entry for entry in manifest["files"]
               if entry["kind"] == "sqlite"}
    if set(entries) != required_labels:
        raise BackupIntegrityError("staged restore does not contain all four durable SQLite stores")
    for label, path in store_paths.items():
        if path.parent.resolve(strict=False) != target:
            raise BackupSafetyError("all configured SQLite stores must be under the durable-state root")

    raw_root = Path(settings.raw_dir).expanduser()
    if not raw_root.is_absolute():
        raw_root = Path.cwd() / raw_root
    raw_root = raw_root.resolve(strict=False)
    if not _is_relative_to(raw_root, target) or raw_root == target:
        raise BackupSafetyError("configured raw-evidence directory must be inside durable state")
    if any(entry["label"] == "raw-evidence" for entry in manifest["files"]
           if entry["kind"] == "file"):
        raw_entry_present = True
    else:
        raw_entry_present = False

    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    staged_install = Path(tempfile.mkdtemp(prefix=f".{target.name}.restore-", dir=parent))
    try:
        for label, database in store_paths.items():
            source = stage / "sqlite" / f"{label}.sqlite"
            output = staged_install / database.name
            shutil.copy2(source, output)
        restored_raw = stage / "files" / "raw-evidence"
        raw_target = staged_install / raw_root.relative_to(target)
        if raw_entry_present:
            if not restored_raw.is_dir() or restored_raw.is_symlink():
                raise BackupIntegrityError("staged raw source-evidence root is unavailable")
            shutil.copytree(restored_raw, raw_target)
        else:
            raw_target.mkdir(parents=True, exist_ok=True)

        _verify_restored_application_schemas(staged_install, store_paths)
        backup_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        previous = target.with_name(f"{target.name}.previous-{backup_suffix}")
        if previous.exists() or previous.is_symlink():
            raise BackupSafetyError("preservation path for prior state already exists")
        had_prior = target.exists()
        if had_prior:
            os.replace(target, previous)
        try:
            os.replace(staged_install, target)
        except BaseException:
            if had_prior and previous.exists() and not target.exists():
                os.replace(previous, target)
            raise
        return previous if had_prior else None
    except BaseException:
        if staged_install.exists():
            shutil.rmtree(staged_install, ignore_errors=True)
        raise


def _verify_restored_application_schemas(root: Path,
                                         store_paths: Mapping[str, Path]) -> None:
    from .reconciliation import ReconciliationStore
    from .state import SCHEMA_VERSION

    expected_pragma_versions = {
        "core-state": SCHEMA_VERSION,
        "office-occurrences": 2,
        "bill-sponsors": 1,
    }
    for label, configured in store_paths.items():
        path = root / configured.name
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise BackupIntegrityError(f"restored {label} SQLite integrity_check failed")
            if label in expected_pragma_versions:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version != expected_pragma_versions[label]:
                    raise BackupIntegrityError(f"restored {label} schema version is unsupported")
            elif label == "reconciliation":
                rows = connection.execute(
                    "SELECT version FROM reconciliation_schema").fetchall()
                if len(rows) != 1 or rows[0][0] != ReconciliationStore.VERSION:
                    raise BackupIntegrityError(
                        "restored reconciliation schema version is unsupported")
        except sqlite3.Error as error:
            raise BackupIntegrityError(f"restored {label} SQLite schema is invalid") from error
        finally:
            connection.close()


def _validate_sqlite_file(path: Path, expected_user_version: int) -> None:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        check = connection.execute("PRAGMA integrity_check").fetchone()
        if check is None or check[0] != "ok":
            raise BackupIntegrityError("restored SQLite integrity_check failed")
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != expected_user_version:
            raise BackupIntegrityError("restored SQLite schema version differs from its manifest")
    except sqlite3.Error as error:
        raise BackupIntegrityError("restored backup contains an unreadable SQLite database") from error
    finally:
        if connection is not None:
            connection.close()


def _snapshot_id_from_backup(output: str | None) -> str | None:
    if not output:
        return None
    for line in reversed(output.splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            value = event.get("snapshot_id")
            if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{8,64}", value):
                return value
    return None


def _valid_snapshot_record(value: Mapping[str, Any]) -> bool:
    return (isinstance(value.get("id"), str)
            and re.fullmatch(r"[0-9a-fA-F]{8,64}", value["id"]) is not None
            and isinstance(value.get("time"), str)
            and isinstance(value.get("tags"), list))


def _snapshot_time(value: object) -> datetime:
    return _parse_timestamp(value)


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or _is_relative_to(left, right) or _is_relative_to(right, left)
