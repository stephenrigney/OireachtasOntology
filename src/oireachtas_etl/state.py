"""Durable SQLite state for authoritative Oireachtas ETL runs.

This store is deliberately separate from the external-identity
``ReconciliationStore``.  Its transactions end before remote graph mutations;
publication is clean only after the caller has completed its post-PUT checks.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid
from urllib.parse import quote, unquote, urlsplit


SCHEMA_VERSION = 5
ENDPOINTS = ("houses", "parties", "constituencies", "committees", "members", "legislation",
             "debates",
             "administrative-units", "offices")
RESOURCE_ENDPOINTS = ("members", "legislation", "debates")
AUTHORITATIVE_COMPLETE_SOURCES = {
    "houses": "api", "parties": "api", "constituencies": "api",
    "members": "api", "legislation": "api", "committees": "members",
    "administrative-units": "registry", "offices": "registry",
}
SHARED_GRAPHS = {
    "houses": "https://data.oireachtas.ie/graph/houses",
    "parties": "https://data.oireachtas.ie/graph/parties",
    "constituencies": "https://data.oireachtas.ie/graph/constituencies",
    "committees": "https://data.oireachtas.ie/graph/committees",
    "administrative-units": "https://data.oireachtas.ie/graph/administrative-units",
    "offices": "https://data.oireachtas.ie/graph/offices",
}


class CoreStateError(ValueError):
    """Invalid or internally inconsistent authoritative ETL state."""


def _validate_debate_source_evidence(source_hash: str, raw_source_path: object,
                                    source_url: object,
                                    expression_iri: object) -> str:
    if (not isinstance(raw_source_path, str) or not raw_source_path
            or not isinstance(source_url, str) or not source_url
            or not isinstance(expression_iri, str) or not expression_iri):
        raise CoreStateError(
            "Debates observations require raw evidence path, source URL, and Expression IRI")
    raw_path = Path(raw_source_path).expanduser()
    if (not raw_path.is_absolute() or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None
            or raw_path.name != f"{source_hash}.xml"):
        raise CoreStateError(
            "Debates raw evidence path must be an absolute SHA-256-addressed XML object")
    try:
        raw_bytes = raw_path.read_bytes()
    except OSError as error:
        raise CoreStateError(f"Debates raw evidence object is unavailable: {raw_path}") from error
    if hashlib.sha256(raw_bytes).hexdigest() != source_hash:
        raise CoreStateError("Debates raw evidence object does not match its source hash")
    from .debates_raw import DebateSourceError, validate_source_expression_url

    try:
        validate_source_expression_url(source_url, expression_iri)
    except DebateSourceError as error:
        raise CoreStateError(
            "Debates source evidence URL must identify the exact official AKN main.xml") from error
    return str(raw_path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_timestamp(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise CoreStateError(f"{label} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CoreStateError(f"invalid {label}: {value!r}") from error
    if parsed.tzinfo is None:
        raise CoreStateError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _verify_debates_report(path: object, digest: object, *, source_hash: str,
                           resolver_version: object,
                           owner_snapshot_hash: object) -> None:
    """Require the exact canonical report before recording or completing publication."""
    from .debates_raw import DebateSourceError, verify_reference_report

    if not isinstance(path, str) or not isinstance(digest, str):
        raise CoreStateError("Debates publication requires a reference report path and hash")
    if (not isinstance(resolver_version, str) or not resolver_version
            or not isinstance(owner_snapshot_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", owner_snapshot_hash) is None):
        raise CoreStateError("Debates reference report requires resolver/owner-snapshot evidence")
    try:
        verify_reference_report(path, digest, source_sha256=source_hash,
                                resolver_version=resolver_version,
                                owner_snapshot_hash=owner_snapshot_hash)
    except DebateSourceError as error:
        raise CoreStateError(f"Debates reference report verification failed: {error}") from error


def _manifest(path: Path, endpoint: str) -> dict:
    key = "members" if endpoint == "members" else "bills"
    label = "Members" if endpoint == "members" else "Bills"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CoreStateError(f"cannot import legacy {label} manifest {path}: {error}") from error
    if (not isinstance(value, dict) or type(value.get("version")) is not int
            or value["version"] != 1 or not isinstance(value.get(key), dict)):
        raise CoreStateError(f"invalid legacy {label} state manifest: {path}")
    return value[key]


def expected_graph_iri(endpoint: str, resource_iri: str) -> str:
    """Validate a resource IRI and derive its already-settled graph identity."""
    if endpoint not in RESOURCE_ENDPOINTS or not isinstance(resource_iri, str):
        raise CoreStateError(f"invalid core resource identity for {endpoint!r}: {resource_iri!r}")
    try:
        parsed = urlsplit(resource_iri)
        port = parsed.port
    except ValueError as error:
        raise CoreStateError(f"invalid {endpoint} resource IRI: {resource_iri!r}") from error
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or port):
        raise CoreStateError(f"invalid {endpoint} resource IRI: {resource_iri!r}")
    path = [part for part in parsed.path.split("/") if part]
    try:
        if endpoint == "members":
            if len(path) != 5 or path[:4] != ["ie", "oireachtas", "member", "id"]:
                raise ValueError
            code = unquote(path[4])
            if not code:
                raise ValueError
            return "https://data.oireachtas.ie/graph/member/" + quote(code, safe="")
        if endpoint == "legislation":
            if len(path) != 5 or path[:3] != ["ie", "oireachtas", "bill"]:
                raise ValueError
            year, number = path[3], unquote(path[4])
            if not year.isdigit() or int(year) < 1 or not number:
                raise ValueError
            return ("https://data.oireachtas.ie/graph/bill/" + quote(year, safe="")
                    + "/" + quote(number, safe=""))
        if len(path) < 4 or path[:3] != ["akn", "ie", "debateRecord"]:
            raise ValueError
        # The Work IRI has already been component-encoded by the approved
        # Debates identity contract.  Do not decode or encode it a second time.
        raw_segments = parsed.path[1:].split("/")
        if (any(not segment or segment in {".", ".."} for segment in raw_segments)
                or any(quote(unquote(segment), safe="-._~") != segment
                       for segment in raw_segments)):
            raise ValueError
        return "https://data.oireachtas.ie/graph/debate/" + parsed.path[len("/akn/ie/debateRecord/"):]
    except (TypeError, ValueError) as error:
        raise CoreStateError(f"invalid {endpoint} resource IRI: {resource_iri!r}") from error


def _validate_legacy_row(endpoint: str, identity: object, row: object) -> dict:
    label = "Member" if endpoint == "members" else "Bill"
    if not isinstance(identity, str) or not isinstance(row, dict):
        raise CoreStateError(f"invalid legacy {label} state entry")
    expected_graph = expected_graph_iri(endpoint, identity)
    graph = row.get("graph_iri")
    pending_graph = row.get("pending_graph_iri")
    if graph is None and row.get("status") in {"dirty", "in_progress"}:
        graph = pending_graph
    if not isinstance(graph, str) or graph != expected_graph:
        raise CoreStateError(f"legacy {label} graph IRI does not match resource identity: {identity}")
    state = row.get("status", "clean")
    if state == "in_progress":
        state = "dirty"
    if not isinstance(state, str) or state not in {"clean", "dirty"}:
        raise CoreStateError(f"invalid legacy {label} publication status for {identity}: {state!r}")
    for field in ("source_hash", "published_hash", "pending_hash"):
        value = row.get(field)
        if value is not None and (not isinstance(value, str) or not value):
            raise CoreStateError(f"invalid legacy {label} {field} for {identity}")
    if state == "dirty":
        if not isinstance(row.get("pending_hash"), str) or not row["pending_hash"]:
            raise CoreStateError(f"dirty legacy {label} state lacks pending_hash for {identity}")
        if pending_graph != expected_graph:
            raise CoreStateError(f"dirty legacy {label} pending graph IRI does not match identity: {identity}")
    contract = row.get("contract_version")
    if contract is not None and (type(contract) is not int or contract < 1):
        raise CoreStateError(f"invalid legacy {label} contract version for {identity}")
    return {
        "endpoint": endpoint,
        "resource_iri": identity,
        "graph_iri": graph,
        "observed_source_hash": row.get("source_hash"),
        "published_source_hash": row.get("published_hash"),
        "published_payload_hash": None,
        "last_seen_at": row.get("last_seen"),
        "last_seen_run_id": None,
        "last_published_at": row.get("last_published"),
        "publication_state": state,
        "pending_source_hash": row.get("pending_hash") if state == "dirty" else None,
        "pending_graph_iri": pending_graph if state == "dirty" else None,
        # The legacy JSON stored neither an RDF payload nor its digest. Dirty
        # entries are consequently re-transformed from the next observed source.
        "pending_payload": None,
        "pending_payload_hash": None,
        "source_presence": "present",
        "contract_version": contract,
    }


@contextmanager
def state_lock(path: Path):
    """Serialize an endpoint's scan/publication sequence across processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class CoreStateStore:
    """SQLite operational state for authoritative resource publication and runs."""

    def __init__(self, path: Path, *, legacy_members: Path | None = None,
                 legacy_bills: Path | None = None):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size:
            with self.path.open("rb") as handle:
                signature = handle.read(16)
            if signature != b"SQLite format 3\x00":
                raise CoreStateError(
                    f"core state path is not SQLite: {self.path}; pass a legacy JSON manifest "
                    "with --legacy-state-file (or the deprecated --state-file alias)"
                )
        self.connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=30000")
        try:
            self._initialize(legacy_members, legacy_bills)
        except BaseException:
            self.connection.close()
            raise

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "CoreStateStore":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def _initialize(self, legacy_members: Path | None, legacy_bills: Path | None) -> None:
        connection = self.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3, 4, SCHEMA_VERSION):
                raise CoreStateError(f"unsupported core ETL state schema version: {version}")
            if version == 0:
                # ``executescript`` implicitly commits an open transaction.
                # Execute each DDL statement separately so schema creation and
                # both one-time manifest imports share the same rollback.
                for statement in _SCHEMA.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                version = SCHEMA_VERSION
            elif version == 1:
                # Tranche 2 adds the legislation cursor, complete-scan absence
                # evidence and the last successfully published graph payload
                # needed for exact graph/state verification and safe repair.
                for statement in (
                    "ALTER TABLE endpoint_state ADD COLUMN incremental_cursor TEXT",
                    "ALTER TABLE resource_state ADD COLUMN published_payload TEXT",
                    "ALTER TABLE resource_state ADD COLUMN last_missing_run_id TEXT",
                    "ALTER TABLE resource_state ADD COLUMN last_missing_at TEXT",
                    "ALTER TABLE resource_state ADD COLUMN missing_scan_count INTEGER NOT NULL DEFAULT 0",
                ):
                    connection.execute(statement)
                connection.execute("PRAGMA user_version=2")
                version = 2
            if version == 2:
                # Tranche 1 adds two reference registries as independently
                # owned shared-graph endpoints. Rebuild just the constrained
                # run/publication tables; preserve their complete histories.
                connection.execute("DROP INDEX IF EXISTS etl_run_endpoint_started")
                connection.execute("ALTER TABLE etl_run RENAME TO etl_run_v2")
                connection.execute("ALTER TABLE endpoint_state RENAME TO endpoint_state_v2")
                connection.execute("""CREATE TABLE etl_run (
                  run_id TEXT PRIMARY KEY,
                  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','members','legislation','administrative-units','offices')),
                  run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
                  is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)),
                  started_at TEXT NOT NULL, completed_at TEXT,
                  status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
                  error TEXT, parameters_json TEXT NOT NULL)""")
                connection.execute("""CREATE TABLE endpoint_state (
                  endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','members','legislation','administrative-units','offices')),
                  last_successful_run_id TEXT, last_successful_complete_run_id TEXT,
                  incremental_cursor TEXT, publication_metadata_json TEXT, updated_at TEXT NOT NULL)""")
                connection.execute("""INSERT INTO etl_run
                  SELECT run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,error,parameters_json
                  FROM etl_run_v2""")
                connection.execute("""INSERT INTO endpoint_state
                  SELECT endpoint,last_successful_run_id,last_successful_complete_run_id,
                    incremental_cursor,publication_metadata_json,updated_at FROM endpoint_state_v2""")
                connection.execute("DROP TABLE etl_run_v2")
                connection.execute("DROP TABLE endpoint_state_v2")
                connection.execute("CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at)")
                connection.execute("PRAGMA user_version=3")
                version = 3
            if version == 3:
                # Add the shared Committee owner graph to the existing core
                # run/publication registry without creating another state DB.
                connection.execute("DROP INDEX IF EXISTS etl_run_endpoint_started")
                connection.execute("ALTER TABLE etl_run RENAME TO etl_run_v3")
                connection.execute("ALTER TABLE endpoint_state RENAME TO endpoint_state_v3")
                connection.execute("""CREATE TABLE etl_run (
                  run_id TEXT PRIMARY KEY,
                  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','administrative-units','offices')),
                  run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
                  is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)),
                  started_at TEXT NOT NULL, completed_at TEXT,
                  status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
                  error TEXT, parameters_json TEXT NOT NULL)""")
                connection.execute("""CREATE TABLE endpoint_state (
                  endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','administrative-units','offices')),
                  last_successful_run_id TEXT, last_successful_complete_run_id TEXT,
                  incremental_cursor TEXT, publication_metadata_json TEXT, updated_at TEXT NOT NULL)""")
                connection.execute("""INSERT INTO etl_run
                  SELECT run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,error,parameters_json
                  FROM etl_run_v3""")
                connection.execute("""INSERT INTO endpoint_state
                  SELECT endpoint,last_successful_run_id,last_successful_complete_run_id,
                    incremental_cursor,publication_metadata_json,updated_at FROM endpoint_state_v3""")
                connection.execute("DROP TABLE etl_run_v3")
                connection.execute("DROP TABLE endpoint_state_v3")
                connection.execute("CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at)")
                connection.execute("PRAGMA user_version=4")
                version = 4
            if version == 4:
                # Debates use the same authoritative resource-publication
                # machinery as Members/Bills, with a content-addressed raw
                # evidence reference.  Rebuild the constrained tables in one
                # transaction so existing histories and publication payloads
                # remain intact while adding the endpoint and evidence fields.
                for index in ("etl_run_endpoint_started", "resource_state_publication"):
                    connection.execute(f"DROP INDEX IF EXISTS {index}")
                connection.execute("ALTER TABLE etl_run RENAME TO etl_run_v4")
                connection.execute("ALTER TABLE endpoint_state RENAME TO endpoint_state_v4")
                connection.execute("ALTER TABLE resource_state RENAME TO resource_state_v4")
                connection.execute("""CREATE TABLE etl_run (
                  run_id TEXT PRIMARY KEY,
                  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
                  run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
                  is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)),
                  started_at TEXT NOT NULL, completed_at TEXT,
                  status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
                  error TEXT, parameters_json TEXT NOT NULL)""")
                connection.execute("""CREATE TABLE endpoint_state (
                  endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
                  last_successful_run_id TEXT, last_successful_complete_run_id TEXT,
                  incremental_cursor TEXT, publication_metadata_json TEXT, updated_at TEXT NOT NULL)""")
                connection.execute("""CREATE TABLE resource_state (
                  endpoint TEXT NOT NULL CHECK(endpoint IN ('members','legislation','debates')),
                  resource_iri TEXT NOT NULL, graph_iri TEXT NOT NULL,
                  observed_source_hash TEXT, published_source_hash TEXT,
                  published_payload_hash TEXT, published_payload TEXT,
                  last_seen_at TEXT, last_seen_run_id TEXT, last_published_at TEXT,
                  last_missing_run_id TEXT, last_missing_at TEXT,
                  missing_scan_count INTEGER NOT NULL DEFAULT 0 CHECK(missing_scan_count >= 0),
                  publication_state TEXT NOT NULL CHECK(publication_state IN ('clean','dirty')),
                  pending_source_hash TEXT, pending_graph_iri TEXT, pending_payload TEXT,
                  pending_payload_hash TEXT,
                  source_presence TEXT NOT NULL DEFAULT 'present' CHECK(source_presence IN ('present','missing','confirmed_missing')),
                  contract_version INTEGER,
                  raw_source_path TEXT, source_url TEXT, expression_iri TEXT,
                  published_resolver_version TEXT, pending_resolver_version TEXT,
                  published_owner_snapshot_hash TEXT, pending_owner_snapshot_hash TEXT,
                  published_reference_report_path TEXT, published_reference_report_hash TEXT,
                  pending_reference_report_path TEXT, pending_reference_report_hash TEXT,
                  PRIMARY KEY(endpoint,resource_iri),
                   CHECK(publication_state='dirty' OR
                         (pending_source_hash IS NULL AND pending_graph_iri IS NULL AND pending_payload_hash IS NULL
                          AND pending_resolver_version IS NULL AND pending_owner_snapshot_hash IS NULL
                          AND pending_reference_report_path IS NULL AND pending_reference_report_hash IS NULL)),
                   CHECK((published_reference_report_path IS NULL) = (published_reference_report_hash IS NULL)),
                   CHECK((pending_reference_report_path IS NULL) = (pending_reference_report_hash IS NULL)))""")
                connection.execute("INSERT INTO etl_run SELECT * FROM etl_run_v4")
                connection.execute("INSERT INTO endpoint_state SELECT * FROM endpoint_state_v4")
                connection.execute("""INSERT INTO resource_state (
                  endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
                  published_payload_hash,published_payload,last_seen_at,last_seen_run_id,
                  last_published_at,last_missing_run_id,last_missing_at,missing_scan_count,
                  publication_state,pending_source_hash,pending_graph_iri,pending_payload,
                  pending_payload_hash,source_presence,contract_version)
                  SELECT endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
                  published_payload_hash,published_payload,last_seen_at,last_seen_run_id,
                  last_published_at,last_missing_run_id,last_missing_at,missing_scan_count,
                  publication_state,pending_source_hash,pending_graph_iri,pending_payload,
                  pending_payload_hash,source_presence,contract_version FROM resource_state_v4""")
                connection.execute("DROP TABLE resource_state_v4")
                connection.execute("DROP TABLE endpoint_state_v4")
                connection.execute("DROP TABLE etl_run_v4")
                connection.execute("CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at)")
                connection.execute("CREATE INDEX resource_state_publication ON resource_state(endpoint,publication_state)")
                connection.execute("PRAGMA user_version=5")
                version = 5
            if version == SCHEMA_VERSION:
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"core_metadata", "etl_run", "endpoint_state", "resource_state"} <= tables:
                    raise CoreStateError("core ETL SQLite schema is incomplete")
                columns = {table: {row[1] for row in connection.execute(
                    f"PRAGMA table_info({table})")} for table in ("endpoint_state", "resource_state")}
                required = {
                    "endpoint_state": {"incremental_cursor"},
                    "resource_state": {"published_payload", "last_missing_run_id",
                                       "last_missing_at", "missing_scan_count",
                                        "raw_source_path", "source_url", "expression_iri",
                                        "published_resolver_version", "pending_resolver_version",
                                        "published_owner_snapshot_hash", "pending_owner_snapshot_hash",
                                        "published_reference_report_path", "published_reference_report_hash",
                                        "pending_reference_report_path", "pending_reference_report_hash"},
                }
                if any(not names <= columns[table] for table, names in required.items()):
                    raise CoreStateError("core ETL SQLite schema is incomplete")
            migrations = (("members", legacy_members), ("legislation", legacy_bills))
            for endpoint, legacy_path in migrations:
                marker = "legacy_import:" + endpoint
                imported = connection.execute(
                    "SELECT value FROM core_metadata WHERE key=?", (marker,)).fetchone()
                if imported is not None:
                    continue
                # An absent manifest has not been imported. In particular a
                # read-only `state status` must not consume the one-time import
                # opportunity before a legacy file is supplied.
                if legacy_path is None or not Path(legacy_path).exists():
                    continue
                established = connection.execute(
                    "SELECT 1 FROM resource_state WHERE endpoint=? LIMIT 1", (endpoint,)
                ).fetchone()
                if established is not None:
                    raise CoreStateError(
                        f"legacy {endpoint} manifest appeared after SQLite resource state was established; "
                        "resolve the conflict explicitly rather than discarding or overwriting state"
                    )
                manifest = _manifest(Path(legacy_path), endpoint)
                rows = [_validate_legacy_row(endpoint, identity, row)
                        for identity, row in manifest.items()]
                for row in rows:
                    self._insert_legacy_row(row)
                count = len(rows)
                connection.execute("INSERT INTO core_metadata(key,value) VALUES (?,?)",
                                   (marker, _json({"source": str(legacy_path) if legacy_path else None,
                                                   "rows": count, "imported_at": _now()})))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _insert_legacy_row(self, row: dict) -> None:
        self.connection.execute("""INSERT INTO resource_state (
          endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
          published_payload_hash,last_seen_at,last_seen_run_id,last_published_at,
          publication_state,pending_source_hash,pending_graph_iri,pending_payload,
          pending_payload_hash,source_presence,contract_version)
          VALUES (:endpoint,:resource_iri,:graph_iri,:observed_source_hash,:published_source_hash,
          :published_payload_hash,:last_seen_at,:last_seen_run_id,:last_published_at,
          :publication_state,:pending_source_hash,:pending_graph_iri,:pending_payload,
           :pending_payload_hash,:source_presence,:contract_version)""", row)

    def incremental_cursor(self, endpoint: str = "legislation") -> str | None:
        if endpoint != "legislation":
            raise CoreStateError(f"incremental cursors are not defined for {endpoint}")
        row = self.connection.execute(
            "SELECT incremental_cursor FROM endpoint_state WHERE endpoint=?", (endpoint,)
        ).fetchone()
        return row[0] if row else None

    def start_run(self, endpoint: str, run_kind: str, *, is_complete: bool,
                  parameters: dict, started_at: str | None = None) -> str:
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported core ETL endpoint: {endpoint}")
        if run_kind not in {"full_refresh", "incremental_refresh", "complete_source_reconciliation"}:
            raise CoreStateError(f"unsupported core ETL run kind: {run_kind}")
        if type(is_complete) is not bool or not isinstance(parameters, dict):
            raise CoreStateError("run completeness and source parameters must be explicit")
        if endpoint == "debates" and (is_complete or run_kind != "incremental_refresh"):
            raise CoreStateError(
                "Debates accepts only incomplete explicit-batch incremental runs")
        run_id = str(uuid.uuid4())
        with self._transaction():
            # Online callers hold the database's advisory scan lock. Any old
            # running row for this endpoint survived a process interruption;
            # it must not remain indefinitely indistinguishable from live work.
            self.connection.execute("""UPDATE etl_run SET status='failed',completed_at=?,
                error='interrupted before completion; retry started'
                WHERE endpoint=? AND status='running'""", (_now(), endpoint))
            self.connection.execute("""INSERT INTO etl_run
              (run_id,endpoint,run_kind,is_complete,started_at,status,parameters_json)
              VALUES (?,?,?,?,?,'running',?)""",
              (run_id, endpoint, run_kind, int(is_complete), started_at or _now(), _json(parameters)))
        return run_id

    def finish_run(self, run_id: str, *, success: bool, error: str | None = None,
                   completed_at: str | None = None, incremental_cursor: str | None = None,
                   complete_scan: bool = False) -> None:
        if type(success) is not bool:
            raise CoreStateError("run success must be explicit")
        if type(complete_scan) is not bool:
            raise CoreStateError("complete-scan finalization must be explicit")
        if incremental_cursor is not None:
            incremental_cursor = _utc_timestamp(incremental_cursor, "incremental cursor")
            if not success:
                raise CoreStateError("a failed run cannot advance the legislation cursor")
        if complete_scan and not success:
            raise CoreStateError("a failed run cannot establish missing-resource evidence")
        status = "succeeded" if success else "failed"
        with self._transaction():
            row = self.connection.execute("SELECT * FROM etl_run WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] != "running":
                raise CoreStateError(f"run is not active: {run_id}")
            if incremental_cursor is not None and (
                    row["endpoint"] != "legislation"
                    or row["run_kind"] not in {"incremental_refresh", "complete_source_reconciliation"}):
                raise CoreStateError("only a successful legislation refresh can advance its cursor")
            if complete_scan and (
                    not row["is_complete"] or row["endpoint"] != "legislation"
                    or row["run_kind"] != "complete_source_reconciliation"):
                raise CoreStateError("missing-resource evidence requires a complete legislation reconciliation")
            if (incremental_cursor is not None or complete_scan) and json.loads(row["parameters_json"]).get("source") != "api":
                raise CoreStateError("only an API source run can advance a cursor or establish absence")
            previous_cursor = None
            if incremental_cursor is not None:
                cursor_row = self.connection.execute(
                    "SELECT incremental_cursor FROM endpoint_state WHERE endpoint='legislation'").fetchone()
                previous_cursor = cursor_row[0] if cursor_row else None
                if (previous_cursor is not None
                        and datetime.fromisoformat(incremental_cursor)
                        < datetime.fromisoformat(_utc_timestamp(previous_cursor, "stored legislation cursor"))):
                    raise CoreStateError("legislation cursor cannot move backwards")
            when = completed_at or _now()
            self.connection.execute("UPDATE etl_run SET completed_at=?,status=?,error=? WHERE run_id=?",
                                    (when, status, None if success else error, run_id))
            if success:
                source = json.loads(row["parameters_json"]).get("source")
                complete_run_id = (
                    run_id if row["is_complete"] and
                    source == AUTHORITATIVE_COMPLETE_SOURCES[row["endpoint"]]
                    else None)
                self.connection.execute("""INSERT INTO endpoint_state
                  (endpoint,last_successful_run_id,last_successful_complete_run_id,incremental_cursor,updated_at)
                  VALUES (?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET
                  last_successful_run_id=excluded.last_successful_run_id,
                  last_successful_complete_run_id=COALESCE(excluded.last_successful_complete_run_id,
                    endpoint_state.last_successful_complete_run_id),
                  incremental_cursor=COALESCE(excluded.incremental_cursor,endpoint_state.incremental_cursor),
                  updated_at=excluded.updated_at""",
                    (row["endpoint"], run_id, complete_run_id, incremental_cursor, when))
                if complete_scan:
                    resources = self.connection.execute(
                        "SELECT resource_iri,source_presence,missing_scan_count FROM resource_state "
                        "WHERE endpoint='legislation' AND COALESCE(last_seen_run_id,'')<>?",
                        (run_id,)).fetchall()
                    for resource in resources:
                        count = resource["missing_scan_count"] + 1
                        presence = "missing" if resource["source_presence"] == "present" else "confirmed_missing"
                        self.connection.execute("""UPDATE resource_state SET source_presence=?,
                          last_missing_run_id=?,last_missing_at=?,missing_scan_count=?
                          WHERE endpoint='legislation' AND resource_iri=?""",
                          (presence, run_id, when, count, resource["resource_iri"]))

    def endpoint_publication(self, endpoint: str) -> dict | None:
        if endpoint not in SHARED_GRAPHS:
            raise CoreStateError(f"endpoint does not own a shared graph: {endpoint}")
        row = self.connection.execute(
            "SELECT publication_metadata_json FROM endpoint_state WHERE endpoint=?", (endpoint,)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def last_successful_complete_run(self, endpoint: str) -> dict | None:
        """Return only a successful complete run from the endpoint's authority."""
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported core ETL endpoint: {endpoint}")
        row = self.connection.execute("""SELECT run.* FROM endpoint_state state
          JOIN etl_run run ON run.run_id=state.last_successful_complete_run_id
          WHERE state.endpoint=? AND run.status='succeeded' AND run.is_complete=1""",
                                     (endpoint,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["parameters"] = json.loads(result.pop("parameters_json"))
        if result["parameters"].get("source") != AUTHORITATIVE_COMPLETE_SOURCES[endpoint]:
            return None
        return result

    def successful_complete_run(self, endpoint: str, run_id: str) -> dict | None:
        """Look up one exact successful complete run from its authority."""
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported core ETL endpoint: {endpoint}")
        row = self.connection.execute(
            "SELECT * FROM etl_run WHERE run_id=? AND endpoint=? "
            "AND status='succeeded' AND is_complete=1", (run_id, endpoint),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["parameters"] = json.loads(result.pop("parameters_json"))
        if result["parameters"].get("source") != AUTHORITATIVE_COMPLETE_SOURCES[endpoint]:
            return None
        return result

    def member_source_run_started_at(self, run_id: str) -> str:
        """Return the timestamp for one complete API Members source run.

        A reference owner graph may be published before its enclosing ETL run
        is finalized, so running and subsequently failed runs remain valid
        provenance evidence here. This does not make them authoritative input
        for a later scan; it only orders evidence already used for publication.
        """
        row = self.connection.execute(
            "SELECT endpoint,is_complete,started_at,parameters_json FROM etl_run WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise CoreStateError(f"reference owner source Members run is unknown: {run_id}")
        parameters = json.loads(row["parameters_json"])
        if (row["endpoint"] != "members" or row["is_complete"] != 1
                or parameters.get("source") != "api"):
            raise CoreStateError(
                f"reference owner source is not a complete Members API run: {run_id}")
        return row["started_at"]

    def mark_endpoint_dirty(self, endpoint: str, graph_iri: str, payload: str,
                            *, coverage_authoritative: bool | None = None,
                            member_source_run_id: str | None = None) -> str:
        if SHARED_GRAPHS.get(endpoint) != graph_iri:
            raise CoreStateError(f"shared graph identity does not match {endpoint}")
        if member_source_run_id is not None:
            self.member_source_run_started_at(member_source_run_id)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._transaction():
            old = self.endpoint_publication(endpoint) or {}
            metadata = {"graph_iri": graph_iri, "publication_state": "dirty",
                        "published_payload_hash": old.get("published_payload_hash"),
                        "published_payload": old.get("published_payload"),
                        "coverage_authoritative": old.get("coverage_authoritative", False),
                        "last_published_at": old.get("last_published_at"),
                        "member_source_run_id": old.get("member_source_run_id"),
                        "pending_payload_hash": digest,
                        "pending_payload": payload,
                        "pending_member_source_run_id": (
                            member_source_run_id or old.get("member_source_run_id")),
                        "pending_coverage_authoritative": (
                            old.get("coverage_authoritative", False)
                            if coverage_authoritative is None
                            else bool(coverage_authoritative))}
            self.connection.execute("""INSERT INTO endpoint_state
                (endpoint,publication_metadata_json,updated_at) VALUES (?,?,?)
                ON CONFLICT(endpoint) DO UPDATE SET
                publication_metadata_json=excluded.publication_metadata_json,
                updated_at=excluded.updated_at""", (endpoint, _json(metadata), _now()))
        return digest

    def complete_endpoint_publication(self, endpoint: str, graph_iri: str, payload_hash: str,
                                      *, coverage_authoritative: bool | None = None) -> None:
        with self._transaction():
            metadata = self.endpoint_publication(endpoint)
            if (metadata is None or metadata.get("graph_iri") != SHARED_GRAPHS.get(endpoint)
                    or metadata["graph_iri"] != graph_iri
                    or metadata.get("publication_state") != "dirty"
                    or metadata.get("pending_payload_hash") != payload_hash):
                raise CoreStateError(f"shared graph publication does not match pending state: {endpoint}")
            published_payload = metadata.get("pending_payload")
            if (not isinstance(published_payload, str)
                    or hashlib.sha256(published_payload.encode("utf-8")).hexdigest() != payload_hash):
                raise CoreStateError(f"shared graph pending payload is missing or corrupt: {endpoint}")
            authoritative = (metadata.get("pending_coverage_authoritative",
                                           metadata.get("coverage_authoritative", False))
                             if coverage_authoritative is None
                             else bool(coverage_authoritative))
            self.connection.execute("""UPDATE endpoint_state SET
                publication_metadata_json=?,updated_at=? WHERE endpoint=?""",
                (_json({"graph_iri": graph_iri, "publication_state": "clean",
                        "published_payload_hash": payload_hash,
                        "published_payload": published_payload,
                        "coverage_authoritative": authoritative,
                        "member_source_run_id": metadata.get(
                            "pending_member_source_run_id",
                            metadata.get("member_source_run_id")),
                        "last_published_at": _now()}),
                 _now(), endpoint))

    def record_endpoint_member_source_run(self, endpoint: str, run_id: str) -> None:
        """Advance source provenance after an identical clean graph verifies."""
        if endpoint not in SHARED_GRAPHS:
            raise CoreStateError(f"endpoint does not own a shared graph: {endpoint}")
        self.member_source_run_started_at(run_id)
        with self._transaction():
            metadata = self.endpoint_publication(endpoint)
            if (metadata is None or metadata.get("graph_iri") != SHARED_GRAPHS[endpoint]
                    or metadata.get("publication_state") != "clean"):
                raise CoreStateError(
                    f"cannot advance Member source provenance for a non-clean graph: {endpoint}")
            metadata["member_source_run_id"] = run_id
            self.connection.execute(
                "UPDATE endpoint_state SET publication_metadata_json=?,updated_at=? WHERE endpoint=?",
                (_json(metadata), _now(), endpoint),
            )

    def observe_resource(self, endpoint: str, resource_iri: str, graph_iri: str,
                         source_hash: str, run_id: str, *, observed_at: str | None = None,
                         raw_source_path: str | None = None,
                         source_url: str | None = None,
                         expression_iri: str | None = None) -> dict:
        expected = expected_graph_iri(endpoint, resource_iri)
        if graph_iri != expected:
            raise CoreStateError(f"graph IRI does not match {endpoint} resource identity: {resource_iri}")
        if not isinstance(source_hash, str) or not source_hash:
            raise CoreStateError("observed source hash must be non-empty")
        if endpoint == "debates":
            raw_source_path = _validate_debate_source_evidence(
                source_hash, raw_source_path, source_url, expression_iri)
        elif any(value is not None for value in (raw_source_path, source_url, expression_iri)):
            raise CoreStateError("raw AKN evidence fields are only defined for Debates resources")
        when = observed_at or _now()
        with self._transaction():
            existing = self.connection.execute("""SELECT graph_iri FROM resource_state
              WHERE endpoint=? AND resource_iri=?""", (endpoint, resource_iri)).fetchone()
            if existing is not None and existing["graph_iri"] != graph_iri:
                raise CoreStateError(f"stored graph IRI changed for {endpoint} resource {resource_iri}")
            self.connection.execute("""INSERT INTO resource_state
              (endpoint,resource_iri,graph_iri,observed_source_hash,last_seen_at,last_seen_run_id,
               publication_state,source_presence,raw_source_path,source_url,expression_iri)
              VALUES (?,?,?,?,?,?, 'clean','present',?,?,?) ON CONFLICT(endpoint,resource_iri) DO UPDATE SET
              observed_source_hash=excluded.observed_source_hash,last_seen_at=excluded.last_seen_at,
              last_seen_run_id=excluded.last_seen_run_id,source_presence='present',
              raw_source_path=COALESCE(excluded.raw_source_path,resource_state.raw_source_path),
              source_url=COALESCE(excluded.source_url,resource_state.source_url),
              expression_iri=COALESCE(excluded.expression_iri,resource_state.expression_iri),
              last_missing_run_id=NULL,last_missing_at=NULL,missing_scan_count=0""",
              (endpoint, resource_iri, graph_iri, source_hash, when, run_id,
               raw_source_path, source_url, expression_iri))
        return self.get_resource(endpoint, resource_iri)  # type: ignore[return-value]

    def mark_publication_dirty(self, endpoint: str, resource_iri: str, *, source_hash: str,
                               graph_iri: str, payload: str, contract_version: int,
                               resolver_version: str | None = None,
                               owner_snapshot_hash: str | None = None,
                               reference_report_path: str | None = None,
                               reference_report_hash: str | None = None,
                               raw_source_path: str | None = None,
                               source_url: str | None = None,
                               expression_iri: str | None = None,
                               run_id: str | None = None) -> str:
        if graph_iri != expected_graph_iri(endpoint, resource_iri):
            raise CoreStateError(f"pending graph IRI does not match resource identity: {resource_iri}")
        if type(contract_version) is not int or contract_version < 1:
            raise CoreStateError("publication contract version must be a positive integer")
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        debate_raw_path = None
        if endpoint == "debates":
            debate_raw_path = _validate_debate_source_evidence(
                source_hash, raw_source_path, source_url, expression_iri)
            if not isinstance(run_id, str) or not run_id:
                raise CoreStateError("Debates publication requires its active observation run")
        elif any(value is not None for value in
                 (reference_report_path, reference_report_hash, raw_source_path,
                  source_url, expression_iri, run_id)):
            raise CoreStateError(
                "Debates report/source evidence is only defined for Debates publication")
        with self._transaction():
            row = self.connection.execute("SELECT graph_iri,observed_source_hash,expression_iri FROM resource_state WHERE endpoint=? AND resource_iri=?",
                                          (endpoint, resource_iri)).fetchone()
            if row is None and endpoint != "debates":
                raise CoreStateError(f"resource must be observed before publication: {resource_iri}")
            if row is not None and row["graph_iri"] != graph_iri:
                raise CoreStateError(f"pending graph differs from stored graph identity: {resource_iri}")
            if endpoint != "debates" and row["observed_source_hash"] != source_hash:
                raise CoreStateError(f"publication source hash differs from the most recently observed source: {resource_iri}")
            if (endpoint == "debates" and row is not None
                    and row["expression_iri"] is not None
                    and row["expression_iri"] != expression_iri):
                raise CoreStateError(
                    f"stored Debate Expression identity changed for Work {resource_iri}")
            if endpoint == "debates" and (
                    not isinstance(resolver_version, str) or not resolver_version
                    or not isinstance(owner_snapshot_hash, str) or not owner_snapshot_hash):
                raise CoreStateError("Debates publication requires resolver and owner snapshot evidence")
            if endpoint == "debates":
                _verify_debates_report(
                    reference_report_path, reference_report_hash,
                    source_hash=source_hash, resolver_version=resolver_version,
                    owner_snapshot_hash=owner_snapshot_hash)
            elif reference_report_path is not None or reference_report_hash is not None:
                raise CoreStateError("reference report state is only defined for Debates publication")
            if endpoint == "debates":
                active_run = self.connection.execute(
                    "SELECT endpoint,status FROM etl_run WHERE run_id=?", (run_id,)).fetchone()
                if (active_run is None or active_run["endpoint"] != "debates"
                        or active_run["status"] != "running"):
                    raise CoreStateError("Debates publication run is not active in Core State")
                self.connection.execute("""INSERT INTO resource_state (
                  endpoint,resource_iri,graph_iri,observed_source_hash,last_seen_at,last_seen_run_id,
                  publication_state,pending_source_hash,pending_graph_iri,pending_payload,
                  pending_payload_hash,source_presence,contract_version,raw_source_path,
                  source_url,expression_iri,pending_resolver_version,pending_owner_snapshot_hash,
                  pending_reference_report_path,pending_reference_report_hash)
                  VALUES ('debates',?,?,?,?,?,'dirty',?,?,?,?, 'present',?,?,?,?,?,?,?,?)
                  ON CONFLICT(endpoint,resource_iri) DO UPDATE SET
                    graph_iri=excluded.graph_iri,
                    observed_source_hash=excluded.observed_source_hash,
                    last_seen_at=excluded.last_seen_at,last_seen_run_id=excluded.last_seen_run_id,
                    publication_state='dirty',pending_source_hash=excluded.pending_source_hash,
                    pending_graph_iri=excluded.pending_graph_iri,pending_payload=excluded.pending_payload,
                    pending_payload_hash=excluded.pending_payload_hash,
                    source_presence='present',contract_version=excluded.contract_version,
                    raw_source_path=excluded.raw_source_path,source_url=excluded.source_url,
                    expression_iri=excluded.expression_iri,
                    pending_resolver_version=excluded.pending_resolver_version,
                    pending_owner_snapshot_hash=excluded.pending_owner_snapshot_hash,
                    pending_reference_report_path=excluded.pending_reference_report_path,
                    pending_reference_report_hash=excluded.pending_reference_report_hash,
                    last_missing_run_id=NULL,last_missing_at=NULL,missing_scan_count=0""",
                  (resource_iri, graph_iri, source_hash, _now(), run_id,
                   source_hash, graph_iri, payload, payload_hash, contract_version,
                   debate_raw_path, source_url, expression_iri, resolver_version,
                   owner_snapshot_hash, reference_report_path, reference_report_hash))
                return payload_hash
            self.connection.execute("""UPDATE resource_state SET graph_iri=?,observed_source_hash=?,
              publication_state='dirty',pending_source_hash=?,pending_graph_iri=?,pending_payload=?,
              pending_payload_hash=?,contract_version=?,pending_resolver_version=?,
              pending_owner_snapshot_hash=?,pending_reference_report_path=?,pending_reference_report_hash=?
              WHERE endpoint=? AND resource_iri=?""",
              (graph_iri, source_hash, source_hash, graph_iri, payload, payload_hash,
               contract_version, resolver_version, owner_snapshot_hash,
               reference_report_path, reference_report_hash, endpoint, resource_iri))
        return payload_hash

    def complete_publication(self, endpoint: str, resource_iri: str, *, source_hash: str,
                             graph_iri: str, payload_hash: str, contract_version: int,
                             published_at: str | None = None) -> None:
        if graph_iri != expected_graph_iri(endpoint, resource_iri):
            raise CoreStateError(f"published graph IRI does not match resource identity: {resource_iri}")
        if type(contract_version) is not int or contract_version < 1:
            raise CoreStateError("publication contract version must be a positive integer")
        with self._transaction():
            row = self.connection.execute("""SELECT publication_state,pending_source_hash,
              pending_graph_iri,pending_payload_hash,pending_payload,pending_resolver_version,
              pending_owner_snapshot_hash,pending_reference_report_path,
              pending_reference_report_hash FROM resource_state
              WHERE endpoint=? AND resource_iri=?""", (endpoint, resource_iri)).fetchone()
            if (row is None or row["publication_state"] != "dirty"
                    or row["pending_source_hash"] != source_hash
                    or row["pending_graph_iri"] != graph_iri
                    or row["pending_payload_hash"] != payload_hash
                    or not isinstance(row["pending_payload"], str)
                    or hashlib.sha256(row["pending_payload"].encode("utf-8")).hexdigest() != payload_hash):
                raise CoreStateError(f"publication completion does not match durable pending state: {resource_iri}")
            if endpoint == "debates":
                _verify_debates_report(
                    row["pending_reference_report_path"],
                    row["pending_reference_report_hash"], source_hash=source_hash,
                    resolver_version=row["pending_resolver_version"],
                    owner_snapshot_hash=row["pending_owner_snapshot_hash"])
            self.connection.execute("""UPDATE resource_state SET graph_iri=?,observed_source_hash=?,
              published_source_hash=?,published_payload_hash=?,published_payload=?,last_published_at=?,
              published_resolver_version=?,published_owner_snapshot_hash=?,
              published_reference_report_path=?,published_reference_report_hash=?,
              publication_state='clean',pending_source_hash=NULL,pending_graph_iri=NULL,
              pending_payload=NULL,pending_payload_hash=NULL,pending_resolver_version=NULL,
              pending_owner_snapshot_hash=NULL,pending_reference_report_path=NULL,
              pending_reference_report_hash=NULL,contract_version=?
              WHERE endpoint=? AND resource_iri=?""",
              (graph_iri, source_hash, source_hash, payload_hash, row["pending_payload"], published_at or _now(),
               row["pending_resolver_version"], row["pending_owner_snapshot_hash"],
               row["pending_reference_report_path"], row["pending_reference_report_hash"],
               contract_version, endpoint, resource_iri))

    def get_resource(self, endpoint: str, resource_iri: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM resource_state WHERE endpoint=? AND resource_iri=?",
                                      (endpoint, resource_iri)).fetchone()
        return dict(row) if row is not None else None

    def resources(self, endpoint: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM resource_state WHERE endpoint=? ORDER BY resource_iri", (endpoint,))]

    def resource_for_observed_hash(self, endpoint: str, source_hash: str) -> dict | None:
        """Return a unique resource identity observed with an exact source hash."""
        rows = self.connection.execute(
            "SELECT * FROM resource_state WHERE endpoint=? AND observed_source_hash=? ORDER BY resource_iri",
            (endpoint, source_hash),
        ).fetchall()
        if len(rows) > 1:
            raise CoreStateError(
                f"source hash is associated with multiple {endpoint} resources: {source_hash}")
        return dict(rows[0]) if rows else None

    def status(self) -> dict:
        endpoints = []
        names = {row[0] for row in self.connection.execute(
            "SELECT endpoint FROM endpoint_state UNION SELECT endpoint FROM resource_state "
            "UNION SELECT endpoint FROM etl_run")}
        for endpoint in sorted(names):
            state = self.connection.execute(
                "SELECT * FROM endpoint_state WHERE endpoint=?", (endpoint,)).fetchone()
            resources = self.connection.execute("""SELECT
              SUM(CASE WHEN publication_state='dirty' THEN 1 ELSE 0 END),COUNT(*)
              FROM resource_state WHERE endpoint=?""", (endpoint,)).fetchone()
            presence = {row[0]: row[1] for row in self.connection.execute(
                "SELECT source_presence,COUNT(*) FROM resource_state WHERE endpoint=? GROUP BY source_presence",
                (endpoint,))}
            endpoints.append({"endpoint": endpoint,
                              "last_successful_run_id": state["last_successful_run_id"] if state else None,
                              "last_successful_complete_run_id": state["last_successful_complete_run_id"] if state else None,
                              "incremental_cursor": state["incremental_cursor"] if state else None,
                               "updated_at": state["updated_at"] if state else None,
                               "publication": (json.loads(state["publication_metadata_json"])
                                               if state and state["publication_metadata_json"] else None),
                              "dirty_resources": resources[0] or 0,
                              "resources": resources[1],
                              "missing_resources": presence.get("missing", 0),
                              "confirmed_missing_resources": presence.get("confirmed_missing", 0)})
        dirty_resources = [dict(row) for row in self.connection.execute("""SELECT
            endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
            pending_source_hash,pending_graph_iri,pending_payload_hash,last_seen_at,
            source_presence,last_missing_run_id,last_missing_at,missing_scan_count,
            raw_source_path,source_url,expression_iri,published_resolver_version,
            pending_resolver_version,published_owner_snapshot_hash,pending_owner_snapshot_hash,
            published_reference_report_path,published_reference_report_hash,
            pending_reference_report_path,pending_reference_report_hash
           FROM resource_state WHERE publication_state='dirty' ORDER BY endpoint,resource_iri""")]
        missing_resources = [dict(row) for row in self.connection.execute("""SELECT
            endpoint,resource_iri,graph_iri,source_presence,last_missing_run_id,last_missing_at,missing_scan_count
            FROM resource_state WHERE source_presence IN ('missing','confirmed_missing')
            ORDER BY endpoint,resource_iri""")]
        runs = [dict(row) for row in self.connection.execute(
            "SELECT run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,error,parameters_json "
            "FROM etl_run ORDER BY started_at DESC LIMIT 20")]
        for run in runs:
            run["is_complete"] = bool(run["is_complete"])
            run["parameters"] = json.loads(run.pop("parameters_json"))
        return {"schema_version": SCHEMA_VERSION, "database": str(self.path),
                "endpoints": endpoints, "dirty_resources": dirty_resources,
                "missing_resources": missing_resources,
                "recent_runs": runs}

    @contextmanager
    def _transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise


_SCHEMA = """
CREATE TABLE core_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE etl_run (
  run_id TEXT PRIMARY KEY,
   endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
  is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
  error TEXT,
  parameters_json TEXT NOT NULL
);
CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at);
CREATE TABLE endpoint_state (
    endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  last_successful_run_id TEXT,
  last_successful_complete_run_id TEXT,
  incremental_cursor TEXT,
  publication_metadata_json TEXT,
  updated_at TEXT NOT NULL
);
CREATE TABLE resource_state (
  endpoint TEXT NOT NULL CHECK(endpoint IN ('members','legislation','debates')),
  resource_iri TEXT NOT NULL,
  graph_iri TEXT NOT NULL,
  observed_source_hash TEXT,
  published_source_hash TEXT,
  published_payload_hash TEXT,
  published_payload TEXT,
  last_seen_at TEXT,
  last_seen_run_id TEXT,
  last_published_at TEXT,
  last_missing_run_id TEXT,
  last_missing_at TEXT,
  missing_scan_count INTEGER NOT NULL DEFAULT 0 CHECK(missing_scan_count >= 0),
  publication_state TEXT NOT NULL CHECK(publication_state IN ('clean','dirty')),
  pending_source_hash TEXT,
  pending_graph_iri TEXT,
  pending_payload TEXT,
  pending_payload_hash TEXT,
  source_presence TEXT NOT NULL DEFAULT 'present' CHECK(source_presence IN ('present','missing','confirmed_missing')),
  contract_version INTEGER,
  raw_source_path TEXT,
  source_url TEXT,
  expression_iri TEXT,
  published_resolver_version TEXT,
  pending_resolver_version TEXT,
  published_owner_snapshot_hash TEXT,
  pending_owner_snapshot_hash TEXT,
  published_reference_report_path TEXT,
  published_reference_report_hash TEXT,
  pending_reference_report_path TEXT,
  pending_reference_report_hash TEXT,
  PRIMARY KEY(endpoint,resource_iri),
  CHECK(publication_state='dirty' OR
        (pending_source_hash IS NULL AND pending_graph_iri IS NULL AND pending_payload_hash IS NULL
         AND pending_resolver_version IS NULL AND pending_owner_snapshot_hash IS NULL
         AND pending_reference_report_path IS NULL AND pending_reference_report_hash IS NULL)),
  CHECK((published_reference_report_path IS NULL) = (published_reference_report_hash IS NULL)),
  CHECK((pending_reference_report_path IS NULL) = (pending_reference_report_hash IS NULL))
);
CREATE INDEX resource_state_publication ON resource_state(endpoint,publication_state);
"""
