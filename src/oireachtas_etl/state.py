"""Durable SQLite state for authoritative Oireachtas ETL runs.

This store is deliberately separate from the external-identity
``ReconciliationStore``.  Its transactions end before remote graph mutations;
publication is clean only after the caller has completed its post-PUT checks.
"""
from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Mapping
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid
from urllib.parse import quote, unquote, urlsplit


SCHEMA_VERSION = 8
# Phase 6 extends run and provenance tables without changing the resource
# publication columns used by the read-only development bootstrap. Version 4
# is the legacy resource schema; versions 5-8 retain that resource shape.
RESOURCE_READ_SCHEMA_VERSIONS = frozenset(range(4, SCHEMA_VERSION + 1))
RESOURCE_READ_COLUMNS = frozenset({
    "resource_iri", "graph_iri", "observed_source_hash", "published_source_hash",
    "published_payload_hash", "published_payload", "last_seen_run_id",
    "publication_state", "source_presence", "contract_version",
})
PROVENANCE_GRAPH_IRI = "https://data.oireachtas.ie/graph/provenance"
PROVENANCE_NAMESPACE = "https://data.oireachtas.ie/etl/"
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


def read_resource_state(state_db: Path | str,
                        endpoints: tuple[str, ...] | list[str]) -> dict[str, list[dict]]:
    """Read resource publication rows from Core State without opening it for writes.

    Development tooling uses this narrow reader to reuse already-validated
    resource payloads. It deliberately does not initialize, migrate, lock, or
    otherwise mutate Core State.
    """
    requested = tuple(endpoints)
    if (not requested or len(requested) != len(set(requested))
            or any(endpoint not in RESOURCE_ENDPOINTS for endpoint in requested)):
        raise CoreStateError("read-only resource selection requires unique resource endpoints")
    path = Path(state_db).expanduser().resolve()
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
    except sqlite3.Error as error:
        raise CoreStateError(f"cannot open Core State read-only: {error}") from error
    try:
        connection.execute("BEGIN")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in RESOURCE_READ_SCHEMA_VERSIONS:
            raise CoreStateError(
                f"unsupported Core State schema version {version}; supported versions are "
                f"{', '.join(map(str, sorted(RESOURCE_READ_SCHEMA_VERSIONS)))}")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "resource_state" not in tables:
            raise CoreStateError("Core State resource table is unavailable")
        columns = {row[1] for row in connection.execute(
            "PRAGMA table_info(resource_state)")}
        if not RESOURCE_READ_COLUMNS <= columns:
            raise CoreStateError("Core State resource publication schema is incomplete")
        result = {
            endpoint: [dict(row) for row in connection.execute(
                "SELECT * FROM resource_state WHERE endpoint=? ORDER BY resource_iri",
                (endpoint,),
            )]
            for endpoint in requested
        }
        connection.commit()
        return result
    except sqlite3.Error as error:
        connection.rollback()
        raise CoreStateError(f"cannot read Core State resource rows: {error}") from error
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


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
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _assert_safe_provenance_metadata(value: object, label: str) -> None:
    """Reject credential-bearing values before they enter durable Core State.

    The projection applies this check when building RDF, but Core State is the
    durable boundary and must not wait until a later projection to discover a
    secret that has already been written.  Import lazily to avoid the normal
    state/provenance module import cycle and use the same policy at both
    boundaries.
    """
    from .provenance import ProvenanceCatalogError, _check_no_secret_fields

    try:
        _check_no_secret_fields(value, label)
        def check_embedded_urls(item: object) -> None:
            if isinstance(item, Mapping):
                for key, child in item.items():
                    check_embedded_urls(key)
                    check_embedded_urls(child)
            elif isinstance(item, (list, tuple)):
                for child in item:
                    check_embedded_urls(child)
            elif isinstance(item, str):
                from .provenance import _safe_url

                for match in re.finditer(r"(?i)https?://[^\s<>\"']+", item):
                    url = match.group(0).rstrip(".,);]")
                    _safe_url(url, label)

        check_embedded_urls(value)
    except ProvenanceCatalogError as error:
        raise CoreStateError(f"{label} contains credential-like metadata") from error


def _safe_source_url(value: object) -> str | None:
    if value is None:
        return None
    from .provenance import ProvenanceCatalogError, _safe_url

    try:
        return _safe_url(value, "source URL")
    except ProvenanceCatalogError as error:
        raise CoreStateError("source URL must be a credential-free HTTP(S) URL") from error


def run_resource_iri(run_id: str) -> str:
    """Return the stable provenance resource IRI for an ETL run."""
    if not isinstance(run_id, str) or not run_id:
        raise CoreStateError("run identity must be a non-empty string")
    return PROVENANCE_NAMESPACE + "run/" + quote(run_id, safe="-._~")


def _versions(value: object, *, label: str = "versions") -> dict[str, str | None]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise CoreStateError(f"{label} must be an object")
    allowed = {"etl_version", "ontology_version", "mapping_version"}
    if value.keys() - allowed:
        raise CoreStateError(f"{label} contains unsupported keys")
    result: dict[str, str | None] = {
        "etl_version": None, "ontology_version": None, "mapping_version": None,
    }
    for key, item in value.items():
        if item is not None and (not isinstance(item, str) or not item.strip()):
            raise CoreStateError(f"{label}.{key} must be a non-empty string")
        result[key] = item
    _assert_safe_provenance_metadata(result, label)
    return result


def _run_summary(value: object, *, current: dict | None = None) -> dict:
    if value is None:
        value = {}
    if not isinstance(value, dict) or value.keys() - {"counters", "timings"}:
        raise CoreStateError("run summary must contain only counters and timings")
    result = {"counters": dict((current or {}).get("counters", {})),
              "timings": dict((current or {}).get("timings", {}))}
    for section in ("counters", "timings"):
        values = value.get(section, {})
        if not isinstance(values, dict):
            raise CoreStateError(f"run summary {section} must be an object")
        for key, item in values.items():
            if not isinstance(key, str) or not key:
                raise CoreStateError(f"run summary {section} keys must be non-empty strings")
            if section == "counters":
                if type(item) is not int or item < 0:
                    raise CoreStateError("run summary counters must be non-negative integers")
            elif (type(item) not in {int, float} or item < 0
                  or item != item or item in {float("inf"), float("-inf")}):
                raise CoreStateError("run summary timings must be finite non-negative numbers")
            result[section][key] = item
    _assert_safe_provenance_metadata(result, "run summary")
    return result


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
            if version not in (0, 1, 2, 3, 4, 5, 6, 7, SCHEMA_VERSION):
                raise CoreStateError(f"unsupported core ETL state schema version: {version}")
            migrated_v5 = False
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
            if version == 5:
                # Keep the Phase 5 endpoint/resource tables byte-for-byte in
                # place: in particular, their cursor and dirty Debates replay
                # payloads are authoritative recovery state. Only the run
                # registry is rebuilt to add outcomes and summaries.
                connection.execute("DROP INDEX IF EXISTS etl_run_endpoint_started")
                connection.execute("ALTER TABLE etl_run RENAME TO etl_run_v5")
                connection.execute(_ETL_RUN_V6)
                connection.execute("""INSERT INTO etl_run (
                  run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,
                  outcome,error,parameters_json,summary_json)
                  SELECT run_id,endpoint,run_kind,is_complete,started_at,completed_at,
                    status,CASE status WHEN 'running' THEN 'running'
                      WHEN 'succeeded' THEN 'success' ELSE 'failed' END,
                    error,parameters_json,'{}' FROM etl_run_v5""")
                connection.execute("DROP TABLE etl_run_v5")
                connection.execute("CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at)")
                connection.execute("PRAGMA user_version=6")
                version = 6
                migrated_v5 = True
            self._ensure_v6_tables()
            self._ensure_v7_tables()
            self._ensure_v8_tables()
            if version in (6, 7):
                # Catalog-run finalization and immutable failed-publication
                # attempts are additive recovery state layered over schema 6;
                # entity lineage is additive over schema 7. Neither migration
                # rewrites a staged shared-graph payload or its dirty marker.
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                version = SCHEMA_VERSION
            if migrated_v5:
                self._record_legacy_run_events()
            if version == SCHEMA_VERSION:
                tables = {row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"core_metadata", "etl_run", "endpoint_state", "resource_state",
                        "quarantine_record", "quarantine_history", "source_observation",
                         "graph_version", "provenance_event", "catalog_publication_state",
                         "catalog_run_finalization", "catalog_publication_attempt",
                         "provenance_incomplete", "entity_version",
                         "entity_version_source"} <= tables:
                    raise CoreStateError("core ETL SQLite schema is incomplete")
                columns = {table: {row[1] for row in connection.execute(
                    f"PRAGMA table_info({table})")} for table in
                    ("etl_run", "endpoint_state", "resource_state")}
                required = {
                    "etl_run": {"outcome", "failure_scope", "failure_classification", "summary_json",
                                "etl_version", "ontology_version", "mapping_version"},
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
            self._backfill_legacy_clean_graphs()
            self._inventory_legacy_shared_entity_gaps()
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def _ensure_v6_tables(self) -> None:
        for statement in _V6_TABLE_DDL.split(";"):
            if statement.strip():
                self.connection.execute(statement)
        for statement in _V6_TRIGGERS:
            self.connection.execute(statement)

    def _ensure_v7_tables(self) -> None:
        for statement in _V7_TABLE_DDL.split(";"):
            if statement.strip():
                self.connection.execute(statement)
        for statement in _V7_TRIGGERS:
            self.connection.execute(statement)

    def _ensure_v8_tables(self) -> None:
        for statement in _V8_TABLE_DDL.split(";"):
            if statement.strip():
                self.connection.execute(statement)
        for statement in _V8_TRIGGERS:
            self.connection.execute(statement)

    def _record_legacy_run_events(self) -> None:
        """Project only facts present in pre-v6 run rows into the event log."""
        rows = self.connection.execute("SELECT * FROM etl_run ORDER BY started_at,run_id").fetchall()
        for row in rows:
            self._append_provenance_event(
                "run_started", run_id=row["run_id"], endpoint=row["endpoint"],
                created_at=row["started_at"], versions={},
                details={"migrated_from_schema": 5},
            )
            if row["status"] != "running":
                self._append_provenance_event(
                    "run_finished", run_id=row["run_id"], endpoint=row["endpoint"],
                    created_at=row["completed_at"] or row["started_at"], versions={},
                    details={"migrated_from_schema": 5, "outcome": row["outcome"],
                             "error": row["error"], "summary": json.loads(row["summary_json"])},
                )

    def _legacy_clean_graph_evidence(self, resource: sqlite3.Row) -> tuple[dict | None, str]:
        """Return only fully verifiable pre-catalog graph evidence.

        Old resource state has a last-seen run, payload, and sometimes raw
        source objects, but none alone proves a catalogable publication.  Do
        not substitute current defaults or infer missing request/version
        metadata: incomplete rows are inventoried for a validated replay.
        """
        endpoint, resource_iri = resource["endpoint"], resource["resource_iri"]
        try:
            graph_iri = expected_graph_iri(endpoint, resource_iri)
        except CoreStateError:
            return None, "invalid_legacy_graph_identity"
        if resource["graph_iri"] != graph_iri:
            return None, "legacy_graph_identity_mismatch"

        payload = resource["published_payload"]
        payload_hash = resource["published_payload_hash"]
        if (not isinstance(payload, str) or not isinstance(payload_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", payload_hash) is None
                or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash):
            return None, "legacy_published_payload_unavailable_or_invalid"
        source_hash = resource["published_source_hash"]
        if (not isinstance(source_hash, str)
                or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None
                or resource["observed_source_hash"] != source_hash):
            return None, "legacy_source_identity_unavailable_or_mismatched"

        run_id = resource["last_seen_run_id"]
        observed_at = resource["last_seen_at"]
        published_at = resource["last_published_at"]
        if not isinstance(run_id, str) or not run_id:
            return None, "legacy_publication_run_unavailable"
        run = self.connection.execute("SELECT * FROM etl_run WHERE run_id=?", (run_id,)).fetchone()
        if run is None or run["endpoint"] != endpoint:
            return None, "legacy_publication_run_unverifiable"
        if not isinstance(observed_at, str) or not isinstance(published_at, str):
            return None, "legacy_observation_or_publication_time_unavailable"
        try:
            observed = _utc_timestamp(observed_at, "legacy source observation time")
            published = _utc_timestamp(published_at, "legacy graph publication time")
            started = _utc_timestamp(run["started_at"], "legacy run start time")
            if run["completed_at"] is None:
                return None, "legacy_publication_run_incomplete"
            completed = _utc_timestamp(run["completed_at"], "legacy run completion time")
        except CoreStateError:
            return None, "legacy_run_or_evidence_time_invalid"
        if not (started <= observed <= completed and started <= published <= completed):
            return None, "legacy_run_does_not_bound_observation_and_publication"

        raw_source_path = resource["raw_source_path"]
        if not isinstance(raw_source_path, str) or not raw_source_path:
            return None, "legacy_raw_source_evidence_unavailable"
        try:
            _assert_safe_provenance_metadata(raw_source_path, "legacy raw evidence pointer")
            raw_path = Path(raw_source_path).expanduser()
            if not raw_path.is_absolute():
                return None, "legacy_raw_source_evidence_unverifiable"
            raw_bytes = raw_path.read_bytes()
        except (CoreStateError, OSError, ValueError):
            return None, "legacy_raw_source_evidence_unverifiable"
        if hashlib.sha256(raw_bytes).hexdigest() != source_hash:
            return None, "legacy_raw_source_hash_mismatch"

        source_url = resource["source_url"]
        try:
            source_url = _safe_source_url(source_url)
            request_metadata = json.loads(run["parameters_json"])
        except (CoreStateError, TypeError, json.JSONDecodeError):
            return None, "legacy_source_metadata_unverifiable"
        if not isinstance(request_metadata, dict):
            return None, "legacy_source_metadata_unverifiable"
        request_parameters = request_metadata.get("request_parameters")
        if not isinstance(request_parameters, dict):
            return None, "legacy_request_parameters_unavailable"

        # Schema 5 did not have version columns.  Use only explicitly retained
        # version fields; contract_version is not interchangeable with ETL,
        # ontology, or mapping versions.
        versions = {key: run[key] for key in
                    ("etl_version", "ontology_version", "mapping_version")
                    if key in run.keys()}
        parameter_versions = request_metadata.get("versions")
        if isinstance(parameter_versions, dict):
            for key in ("etl_version", "ontology_version", "mapping_version"):
                if versions.get(key) is None:
                    versions[key] = parameter_versions.get(key)
        try:
            version_values = _versions(versions, label="legacy run versions")
            _assert_safe_provenance_metadata(request_parameters,
                                             "legacy source request parameters")
            json.dumps(request_parameters, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False)
        except CoreStateError:
            return None, "legacy_source_or_version_metadata_unverifiable"
        except (TypeError, ValueError):
            return None, "legacy_request_parameters_unverifiable"
        if any(version_values[key] is None for key in
               ("etl_version", "ontology_version", "mapping_version")):
            return None, "legacy_version_metadata_unavailable"

        if endpoint == "debates":
            try:
                _validate_debate_source_evidence(
                    source_hash, raw_source_path, source_url,
                    resource["expression_iri"])
            except CoreStateError:
                return None, "legacy_debate_source_evidence_unverifiable"

        return {
            "endpoint": endpoint, "resource_iri": resource_iri,
            "graph_iri": graph_iri, "payload": payload,
            "payload_hash": payload_hash, "source_hash": source_hash,
            "run_id": run_id, "observed_at": observed,
            "published_at": published,
            "evidence_pointer": raw_path.resolve().as_uri(),
            "source_url": source_url,
            "request_parameters": request_parameters,
            "versions": version_values,
        }, ""

    def _record_incomplete_graph(self, endpoint: str, graph_iri: str, *,
                                 resource_iri: str | None, run_id: str | None,
                                 source_hash: str | None, payload_hash: str | None,
                                 reason: str) -> None:
        if endpoint not in ENDPOINTS:
            raise CoreStateError("provenance inventory endpoint is unsupported")
        if resource_iri is not None:
            expected = expected_graph_iri(endpoint, resource_iri)
        else:
            expected = SHARED_GRAPHS.get(endpoint)
        if expected is None or graph_iri != expected:
            # Keep migration fail-closed if the inventory cannot identify the
            # same graph identity that legacy state claims to own.
            raise CoreStateError("legacy clean graph has an invalid graph identity")
        if isinstance(run_id, str):
            try:
                _assert_safe_provenance_metadata(run_id, "legacy provenance run identity")
            except CoreStateError:
                run_id = None
        self.connection.execute("""INSERT INTO provenance_incomplete (
          endpoint,resource_iri,graph_iri,run_id,source_hash,payload_hash,reason,
          required_action,status,detected_at)
          VALUES (?,?,?,?,?,?,?,'validated_reobservation_and_republish','pending',?)
          ON CONFLICT(endpoint,graph_iri) DO UPDATE SET
            resource_iri=excluded.resource_iri,
            graph_iri=excluded.graph_iri,run_id=excluded.run_id,
            source_hash=excluded.source_hash,payload_hash=excluded.payload_hash,
            reason=excluded.reason,required_action=excluded.required_action,
            status='pending',resolved_at=NULL,resolution_run_id=NULL""",
          (endpoint, resource_iri, expected,
           run_id if isinstance(run_id, str) else None,
           source_hash if isinstance(source_hash, str)
           and re.fullmatch(r"[0-9a-f]{64}", source_hash) else None,
           payload_hash if isinstance(payload_hash, str)
           and re.fullmatch(r"[0-9a-f]{64}", payload_hash) else None,
           reason, _now()))

    def _record_provenance_incomplete(self, resource: sqlite3.Row, reason: str) -> None:
        self._record_incomplete_graph(
            resource["endpoint"], resource["graph_iri"],
            resource_iri=resource["resource_iri"],
            run_id=resource["last_seen_run_id"],
            source_hash=resource["published_source_hash"],
            payload_hash=resource["published_payload_hash"], reason=reason,
        )

    def _backfill_legacy_clean_graphs(self) -> None:
        """Backfill only verifiable clean graph evidence; inventory every gap."""
        resources = self.connection.execute(
            "SELECT * FROM resource_state WHERE publication_state='clean' "
            "ORDER BY endpoint,resource_iri").fetchall()
        for resource in resources:
            payload_hash = resource["published_payload_hash"]
            graph_iri = resource["graph_iri"]
            if (isinstance(payload_hash, str)
                    and self.connection.execute(
                        "SELECT 1 FROM graph_version WHERE graph_iri=? AND payload_hash=?",
                        (graph_iri, payload_hash)).fetchone() is not None):
                continue
            evidence, reason = self._legacy_clean_graph_evidence(resource)
            if evidence is None:
                self._record_provenance_incomplete(resource, reason)
                continue

            self.connection.execute("SAVEPOINT legacy_graph_backfill")
            try:
                self._source_observation_locked(
                    evidence["endpoint"], evidence["source_hash"], evidence["observed_at"],
                    run_id=evidence["run_id"],
                    evidence_pointer=evidence["evidence_pointer"],
                    source_url=evidence["source_url"],
                    request_parameters=evidence["request_parameters"],
                    versions=evidence["versions"],
                )
                self._store_graph_version(
                    evidence["endpoint"], evidence["graph_iri"], evidence["payload"],
                    evidence["payload_hash"], run_id=evidence["run_id"],
                    entity_iri=evidence["resource_iri"],
                    source_hash=evidence["source_hash"],
                    versions=evidence["versions"], created_at=evidence["published_at"],
                )
                self.connection.execute("RELEASE SAVEPOINT legacy_graph_backfill")
            except (CoreStateError, sqlite3.Error):
                self.connection.execute("ROLLBACK TO SAVEPOINT legacy_graph_backfill")
                self.connection.execute("RELEASE SAVEPOINT legacy_graph_backfill")
                self._record_provenance_incomplete(
                    resource, "legacy_graph_evidence_conflicts_with_immutable_provenance")
                continue
            self.connection.execute("""UPDATE provenance_incomplete SET status='resolved',
              resolved_at=?,resolution_run_id=? WHERE endpoint=? AND graph_iri=?""",
              (_now(), evidence["run_id"], evidence["endpoint"], evidence["graph_iri"]))

        # Shared graph state has no resource/source identity or immutable raw
        # pointer in schema 5.  Preserve the exact clean graph snapshot as an
        # explicit gate item rather than attributing it to the most recent
        # endpoint run and inventing source history.
        shared_rows = self.connection.execute(
            "SELECT endpoint,last_successful_run_id,publication_metadata_json "
            "FROM endpoint_state WHERE publication_metadata_json IS NOT NULL "
            "ORDER BY endpoint").fetchall()
        for endpoint_row in shared_rows:
            metadata = json.loads(endpoint_row["publication_metadata_json"])
            if metadata.get("publication_state") != "clean":
                continue
            graph_iri = metadata.get("graph_iri")
            payload_hash = metadata.get("published_payload_hash")
            if (isinstance(graph_iri, str) and isinstance(payload_hash, str)
                    and self.connection.execute(
                        "SELECT 1 FROM graph_version WHERE graph_iri=? AND payload_hash=?",
                        (graph_iri, payload_hash)).fetchone() is not None):
                continue
            reason = "legacy_shared_publication_evidence_unavailable"
            payload = metadata.get("published_payload")
            if (not isinstance(payload, str) or not isinstance(payload_hash, str)
                    or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash):
                reason = "legacy_shared_published_payload_unavailable_or_invalid"
            self._record_incomplete_graph(
                endpoint_row["endpoint"], graph_iri,
                resource_iri=None, run_id=endpoint_row["last_successful_run_id"],
                source_hash=None, payload_hash=payload_hash if isinstance(payload_hash, str) else None,
                reason=reason,
            )

    def _inventory_legacy_shared_entity_gaps(self) -> None:
        """Inventory clean shared snapshots that predate entity-level evidence.

        Schema migration deliberately does not infer an entity's source record
        from a graph payload or rewrite any existing publication metadata. A
        current, validated publication can resolve the inventory later.
        """
        for endpoint in ("houses", "parties", "constituencies", "committees"):
            metadata = self.endpoint_publication(endpoint)
            if not metadata or metadata.get("publication_state") != "clean":
                continue
            graph_iri = SHARED_GRAPHS[endpoint]
            payload = metadata.get("published_payload")
            payload_hash = metadata.get("published_payload_hash")
            if (not isinstance(payload, str) or not isinstance(payload_hash, str)
                    or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash):
                reason = "legacy_shared_published_payload_unavailable_or_invalid"
            else:
                if self._shared_entity_lineage_complete_locked(
                        endpoint, graph_iri, payload_hash, payload):
                    continue
                reason = "legacy_shared_entity_lineage_unavailable"
            existing = self.connection.execute(
                "SELECT status,reason,payload_hash FROM provenance_incomplete "
                "WHERE endpoint=? AND graph_iri=?",
                (endpoint, graph_iri),
            ).fetchone()
            if (existing is not None and existing["status"] == "pending"
                    and existing["reason"] == reason
                    and existing["payload_hash"] == payload_hash):
                continue
            version = self.connection.execute(
                "SELECT first_run_id FROM graph_version WHERE graph_iri=? AND payload_hash=?",
                (graph_iri, payload_hash),
            ).fetchone() if isinstance(payload_hash, str) else None
            endpoint_row = self.connection.execute(
                "SELECT last_successful_run_id FROM endpoint_state WHERE endpoint=?",
                (endpoint,),
            ).fetchone()
            run_id = (version[0] if version and version[0] else
                      endpoint_row[0] if endpoint_row else None)
            self._record_incomplete_graph(
                endpoint, graph_iri, resource_iri=None, run_id=run_id,
                source_hash=None,
                payload_hash=payload_hash if isinstance(payload_hash, str) else None,
                reason=reason,
            )

    def _append_provenance_event(self, event_type: str, *, run_id: str | None = None,
                                 endpoint: str | None = None, graph_iri: str | None = None,
                                 payload_hash: str | None = None, entity_iri: str | None = None,
                                 source_hash: str | None = None,
                                 observed_at: str | None = None,
                                 evidence_pointer: str | None = None,
                                 versions: dict | None = None, details: dict | None = None,
                                 created_at: str | None = None) -> str:
        if event_type not in {"run_started", "run_finished", "source_observed",
                              "graph_published", "entity_published"}:
            raise CoreStateError(f"unsupported provenance event type: {event_type!r}")
        if details is None:
            details = {}
        if not isinstance(details, dict):
            raise CoreStateError("provenance event details must be an object")
        _assert_safe_provenance_metadata(details, "provenance event details")
        if versions is None and run_id is not None:
            run = self.connection.execute(
                "SELECT etl_version,ontology_version,mapping_version FROM etl_run WHERE run_id=?",
                (run_id,),
            ).fetchone()
            versions = ({key: run[key] for key in
                         ("etl_version", "ontology_version", "mapping_version")}
                        if run is not None else {})
        version_values = _versions(versions)
        _assert_safe_provenance_metadata(version_values, "provenance event versions")
        versions_json = _json(version_values)
        details_json = _json(details)
        semantic = {
            "event_type": event_type, "run_id": run_id, "endpoint": endpoint,
            "graph_iri": graph_iri, "payload_hash": payload_hash,
            "entity_iri": entity_iri, "source_hash": source_hash,
            "observed_at": observed_at, "evidence_pointer": evidence_pointer,
            "versions_json": versions_json, "details_json": details_json,
        }
        _assert_safe_provenance_metadata(semantic, "provenance event")
        event_id = hashlib.sha256(_json(semantic).encode("utf-8")).hexdigest()
        when = created_at or _now()
        self.connection.execute("""INSERT OR IGNORE INTO provenance_event (
          event_id,event_type,run_id,endpoint,graph_iri,payload_hash,entity_iri,
          source_hash,observed_at,evidence_pointer,versions_json,details_json,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (event_id, event_type, run_id, endpoint, graph_iri, payload_hash, entity_iri,
           source_hash, observed_at, evidence_pointer, versions_json, details_json, when))
        existing = self.connection.execute(
            "SELECT * FROM provenance_event WHERE event_id=?", (event_id,)
        ).fetchone()
        if existing is None or any(existing[key] != value for key, value in semantic.items()):
            raise CoreStateError("immutable provenance event identity conflicts with stored evidence")
        return event_id

    def _source_observation_locked(self, endpoint: str, source_hash: str, observed_at: str,
                                   *, run_id: str, evidence_pointer: str | None = None,
                                   source_url: str | None = None,
                                   request_parameters: dict | None = None,
                                   versions: dict | None = None) -> dict:
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported source observation endpoint: {endpoint}")
        if not isinstance(source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
            raise CoreStateError("source observation identity requires a lowercase SHA-256 hash")
        observed = _utc_timestamp(observed_at, "source observation time")
        for value, label in ((evidence_pointer, "evidence pointer"), (source_url, "source URL")):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise CoreStateError(f"{label} must be a non-empty string")
        _assert_safe_provenance_metadata(evidence_pointer, "source evidence pointer")
        source_url = _safe_source_url(source_url)
        request_parameters = {} if request_parameters is None else request_parameters
        if not isinstance(request_parameters, dict):
            raise CoreStateError("source request parameters must be an object")
        _assert_safe_provenance_metadata(request_parameters, "source request parameters")
        run = self.connection.execute("SELECT * FROM etl_run WHERE run_id=?", (run_id,)).fetchone()
        if run is None or run["endpoint"] != endpoint:
            raise CoreStateError(f"source observation run does not match endpoint {endpoint}: {run_id}")
        version_values = {key: run[key] for key in
                          ("etl_version", "ontology_version", "mapping_version")}
        version_values.update({key: value for key, value in _versions(versions).items()
                               if value is not None})
        versions_json = _json(version_values)
        parameters_json = _json(request_parameters)
        fields = {
            "endpoint": endpoint, "run_id": run_id, "evidence_pointer": evidence_pointer,
            "source_url": source_url, "request_parameters_json": parameters_json,
            "versions_json": versions_json,
        }
        existing = self.connection.execute(
            "SELECT * FROM source_observation WHERE source_hash=? AND observed_at=?",
            (source_hash, observed),
        ).fetchone()
        if existing is not None:
            if any(existing[key] != value for key, value in fields.items()):
                raise CoreStateError("source hash/observation identity conflicts with immutable evidence")
        else:
            self.connection.execute("""INSERT INTO source_observation (
              source_hash,observed_at,endpoint,run_id,evidence_pointer,source_url,
              request_parameters_json,versions_json,recorded_at)
              VALUES (?,?,?,?,?,?,?,?,?)""",
              (source_hash, observed, endpoint, run_id, evidence_pointer, source_url,
               parameters_json, versions_json, _now()))
        self._append_provenance_event(
            "source_observed", run_id=run_id, endpoint=endpoint, source_hash=source_hash,
            observed_at=observed, evidence_pointer=evidence_pointer, versions=version_values,
            details={"source_url": source_url, "request_parameters": request_parameters},
        )
        return dict(self.connection.execute(
            "SELECT * FROM source_observation WHERE source_hash=? AND observed_at=?",
            (source_hash, observed),
        ).fetchone())

    def record_source_observation(self, endpoint: str, source_hash: str, observed_at: str,
                                  *, run_id: str, evidence_pointer: str | None = None,
                                  source_url: str | None = None,
                                  request_parameters: dict | None = None,
                                  versions: dict | None = None) -> dict:
        """Persist immutable hash+observation evidence and its provenance event."""
        with self._transaction():
            return self._source_observation_locked(
                endpoint, source_hash, observed_at, run_id=run_id,
                evidence_pointer=evidence_pointer, source_url=source_url,
                request_parameters=request_parameters, versions=versions)

    def _store_graph_version(self, endpoint: str, graph_iri: str, payload: str,
                             payload_hash: str, *, run_id: str | None,
                             entity_iri: str | None = None,
                             source_hash: str | None = None,
                             member_source_run_id: str | None = None,
                             versions: dict | None = None,
                             created_at: str | None = None) -> None:
        actual_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if actual_hash != payload_hash:
            raise CoreStateError("graph version payload does not match its SHA-256 identity")
        self.connection.execute("""INSERT OR IGNORE INTO graph_version (
          graph_iri,payload_hash,payload,endpoint,entity_iri,source_hash,first_run_id,created_at)
          VALUES (?,?,?,?,?,?,?,?)""",
          (graph_iri, payload_hash, payload, endpoint, entity_iri, source_hash, run_id,
           created_at or _now()))
        version = self.connection.execute(
            "SELECT payload FROM graph_version WHERE graph_iri=? AND payload_hash=?",
            (graph_iri, payload_hash),
        ).fetchone()
        if version is None or version["payload"] != payload:
            raise CoreStateError("graph IRI/payload-hash identity conflicts with immutable payload")
        self._append_provenance_event(
            "entity_published" if entity_iri is not None else "graph_published",
            run_id=run_id, endpoint=endpoint, graph_iri=graph_iri,
            payload_hash=payload_hash, entity_iri=entity_iri, source_hash=source_hash,
            versions=versions,
            details={"graph_version": graph_iri + "#sha256=" + payload_hash,
                     **({"member_source_run_id": member_source_run_id}
                        if member_source_run_id is not None else {})},
            created_at=created_at,
        )

    def _normalize_shared_entity_lineage_locked(
            self, endpoint: str, graph_iri: str, payload: str, run_id: str,
            lineage: object, *, old_metadata: dict) -> dict[str, dict]:
        """Validate a complete, immutable lineage plan before remote PUT."""
        from .provenance import (ProvenanceCatalogError,
                                 shared_graph_entity_iris)

        try:
            expected = shared_graph_entity_iris(endpoint, payload)
        except ProvenanceCatalogError as error:
            raise CoreStateError(str(error)) from error
        if not isinstance(lineage, Mapping) or set(lineage) != expected:
            missing = expected - set(lineage) if isinstance(lineage, Mapping) else expected
            extra = set(lineage) - expected if isinstance(lineage, Mapping) else set()
            raise CoreStateError(
                f"shared {endpoint} entity lineage does not exactly cover its payload "
                f"(missing={sorted(missing)}, extra={sorted(extra)})")
        if (self.connection.execute(
                "SELECT 1 FROM etl_run WHERE run_id=? AND status='running'", (run_id,)
        ).fetchone() is None):
            raise CoreStateError("shared graph lineage publisher is not an active Core State run")

        normalized: dict[str, dict] = {}
        prior_graph_hash = old_metadata.get("published_payload_hash")
        for entity_iri in sorted(expected):
            raw = lineage[entity_iri]
            if not isinstance(raw, Mapping) or set(raw) - {"sources", "prior_payload_hash"}:
                raise CoreStateError(f"invalid lineage record for shared entity {entity_iri}")
            prior_hash = raw.get("prior_payload_hash")
            if prior_hash is not None:
                if (not isinstance(prior_hash, str)
                        or re.fullmatch(r"[0-9a-f]{64}", prior_hash) is None
                        or prior_hash != prior_graph_hash
                        or prior_hash == hashlib.sha256(payload.encode("utf-8")).hexdigest()):
                    raise CoreStateError(
                        f"retained shared entity {entity_iri} does not identify the prior clean graph version")
                prior = self.connection.execute(
                    "SELECT 1 FROM entity_version WHERE graph_iri=? AND payload_hash=? AND entity_iri=?",
                    (graph_iri, prior_hash, entity_iri),
                ).fetchone()
                if prior is None:
                    raise CoreStateError(
                        f"cannot safely attribute retained shared entity {entity_iri}: "
                        "the prior immutable entity version is unavailable")
            sources_value = raw.get("sources", [])
            if not isinstance(sources_value, list):
                raise CoreStateError(f"lineage sources for {entity_iri} must be an array")
            sources: list[dict] = []
            seen_sources: set[tuple[str, str, str]] = set()
            for item in sources_value:
                if (not isinstance(item, Mapping)
                        or set(item) != {"source_hash", "observed_at", "evidence_pointer"}):
                    raise CoreStateError(f"invalid source evidence for shared entity {entity_iri}")
                source_hash = item["source_hash"]
                if (not isinstance(source_hash, str)
                        or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None):
                    raise CoreStateError("entity source identity must be a SHA-256 hash")
                observed_at = _utc_timestamp(item["observed_at"], "entity source observation time")
                pointer = item["evidence_pointer"]
                if not isinstance(pointer, str) or not pointer.strip():
                    raise CoreStateError("entity source evidence requires a record JSON pointer")
                _assert_safe_provenance_metadata(pointer, "entity source evidence pointer")
                page = self.connection.execute(
                    "SELECT evidence_pointer,versions_json FROM source_observation "
                    "WHERE source_hash=? AND observed_at=?",
                    (source_hash, observed_at),
                ).fetchone()
                if page is None:
                    raise CoreStateError(
                        f"entity source observation is absent from Core State: {source_hash}")
                page_pointer = page["evidence_pointer"]
                page_base, marker, fragment = pointer.partition("#")
                if (not isinstance(page_pointer, str) or not page_pointer
                        or not marker or page_base != page_pointer
                        or not fragment.startswith("/")
                        or re.search(r"~(?![01])", fragment)):
                    raise CoreStateError(
                        f"entity source pointer for {entity_iri} does not identify a record "
                        "within its exact observed page")
                versions = _versions(json.loads(page["versions_json"]))
                if any(versions[key] is None for key in
                       ("etl_version", "ontology_version", "mapping_version")):
                    raise CoreStateError(
                        f"entity source page for {entity_iri} lacks complete version metadata")
                key = (source_hash, observed_at, pointer)
                if key not in seen_sources:
                    seen_sources.add(key)
                    sources.append({"source_hash": source_hash,
                                    "observed_at": observed_at,
                                    "evidence_pointer": pointer})
            if not sources and prior_hash is None:
                raise CoreStateError(
                    f"cannot safely establish source attribution for shared entity {entity_iri}: "
                    "no exact source record or prior immutable entity version")
            normalized[entity_iri] = {
                "sources": sorted(sources, key=lambda source: (
                    source["source_hash"], source["observed_at"],
                    source["evidence_pointer"])),
                "prior_payload_hash": prior_hash,
            }
        return normalized

    def _store_entity_version_locked(self, graph_iri: str, payload_hash: str,
                                     endpoint: str, entity_iri: str, run_id: str,
                                     lineage: dict, *, created_at: str | None = None) -> None:
        existing = self.connection.execute(
            "SELECT endpoint FROM entity_version WHERE graph_iri=? AND payload_hash=? AND entity_iri=?",
            (graph_iri, payload_hash, entity_iri),
        ).fetchone()
        if existing is not None:
            if existing["endpoint"] != endpoint:
                raise CoreStateError("immutable entity-version identity changed owner endpoint")
            return
        prior_hash = lineage.get("prior_payload_hash")
        self.connection.execute("""INSERT INTO entity_version (
          graph_iri,payload_hash,entity_iri,endpoint,run_id,prior_payload_hash,created_at)
          VALUES (?,?,?,?,?,?,?)""",
          (graph_iri, payload_hash, entity_iri, endpoint, run_id, prior_hash,
           created_at or _now()))
        for source in lineage.get("sources", []):
            self.connection.execute("""INSERT INTO entity_version_source (
              graph_iri,payload_hash,entity_iri,source_hash,observed_at,evidence_pointer)
              VALUES (?,?,?,?,?,?)""",
              (graph_iri, payload_hash, entity_iri, source["source_hash"],
               source["observed_at"], source["evidence_pointer"]))

    def entity_versions(self, graph_iri: str | None = None) -> list[dict]:
        if graph_iri is None:
            rows = self.connection.execute(
                "SELECT * FROM entity_version ORDER BY created_at,graph_iri,payload_hash,entity_iri"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM entity_version WHERE graph_iri=? "
                "ORDER BY created_at,payload_hash,entity_iri", (graph_iri,),
            ).fetchall()
        return [dict(row) for row in rows]

    def entity_version_sources(self, graph_iri: str | None = None) -> list[dict]:
        query = "SELECT * FROM entity_version_source"
        parameters: tuple = ()
        if graph_iri is not None:
            query += " WHERE graph_iri=?"
            parameters = (graph_iri,)
        query += " ORDER BY graph_iri,payload_hash,entity_iri,source_hash,observed_at,evidence_pointer"
        return [dict(row) for row in self.connection.execute(query, parameters)]

    def graph_versions(self, graph_iri: str | None = None) -> list[dict]:
        if graph_iri is None:
            rows = self.connection.execute(
                "SELECT * FROM graph_version ORDER BY created_at,graph_iri,payload_hash").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM graph_version WHERE graph_iri=? ORDER BY created_at,payload_hash",
                (graph_iri,),
            ).fetchall()
        return [dict(row) for row in rows]

    def provenance_events(self, *, event_type: str | None = None,
                          run_id: str | None = None) -> list[dict]:
        clauses: list[str] = []
        parameters: list[str] = []
        if event_type is not None:
            clauses.append("event_type=?")
            parameters.append(event_type)
        if run_id is not None:
            clauses.append("run_id=?")
            parameters.append(run_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            "SELECT * FROM provenance_event" + where + " ORDER BY created_at,event_id", parameters
        ).fetchall()
        result = []
        for raw in rows:
            row = dict(raw)
            row["versions"] = json.loads(row.pop("versions_json"))
            row["details"] = json.loads(row.pop("details_json"))
            row["run_iri"] = run_resource_iri(row["run_id"]) if row["run_id"] else None
            result.append(row)
        return result

    def _quarantine_history(self, quarantine_id: str, action: str, *, run_id: str | None = None,
                            actor: str | None = None, details: dict | None = None) -> None:
        when = _now()
        details = details or {}
        _assert_safe_provenance_metadata(details, "quarantine history details")
        _assert_safe_provenance_metadata(actor, "quarantine history actor")
        _assert_safe_provenance_metadata(run_id, "quarantine history run identity")
        details_json = _json(details)
        self.connection.execute("""INSERT INTO quarantine_history
          (history_id,quarantine_id,action,run_id,actor,details_json,created_at)
          VALUES (?,?,?,?,?,?,?)""",
          (str(uuid.uuid4()), quarantine_id, action, run_id, actor, details_json, when))

    def record_quarantine(self, endpoint: str, *, run_id: str, source_hash: str,
                          observed_at: str, evidence_pointer: str, stage: str, error: str,
                          resource_iri: str | None = None,
                          failure_classification: str = "record_transform_failure",
                          etl_version: str | None = None,
                          ontology_version: str | None = None,
                          mapping_version: str | None = None) -> str:
        """Persist one immutable record-failure snapshot and its retry history."""
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported quarantine endpoint: {endpoint}")
        if re.fullmatch(r"[0-9a-f]{64}", source_hash or "") is None:
            raise CoreStateError("quarantine source identity must be a lowercase SHA-256 hash")
        observed = _utc_timestamp(observed_at, "quarantine observation time")
        for value, label in ((evidence_pointer, "evidence pointer"), (stage, "processing stage"),
                             (error, "quarantine error"),
                             (failure_classification, "failure classification")):
            if not isinstance(value, str) or not value.strip():
                raise CoreStateError(f"quarantine {label} must be non-empty")
            _assert_safe_provenance_metadata(value, f"quarantine {label}")
        if resource_iri is not None and (not isinstance(resource_iri, str) or not resource_iri):
            raise CoreStateError("quarantine resource IRI must be non-empty when provided")
        _assert_safe_provenance_metadata(resource_iri, "quarantine resource identity")
        with self._transaction():
            run = self.connection.execute("SELECT * FROM etl_run WHERE run_id=?", (run_id,)).fetchone()
            if run is None or run["endpoint"] != endpoint or run["status"] != "running":
                raise CoreStateError("quarantine must reference its active endpoint run")
            version_values = {
                "etl_version": etl_version or run["etl_version"],
                "ontology_version": ontology_version or run["ontology_version"],
                "mapping_version": mapping_version or run["mapping_version"],
            }
            if any(not isinstance(value, str) or not value.strip()
                   for value in version_values.values()):
                raise CoreStateError("quarantine requires ETL, ontology, and mapping versions")
            _assert_safe_provenance_metadata(version_values, "quarantine versions")
            _assert_safe_provenance_metadata(run_id, "quarantine run identity")
            identity = {"endpoint": endpoint, "resource_iri": resource_iri,
                        "source_hash": source_hash, "observed_at": observed,
                        "stage": stage, "versions": version_values}
            quarantine_id = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()
            existing = self.connection.execute(
                "SELECT * FROM quarantine_record WHERE quarantine_id=?", (quarantine_id,)
            ).fetchone()
            if existing is None:
                self.connection.execute("""INSERT INTO quarantine_record (
                  quarantine_id,endpoint,resource_iri,source_hash,observed_at,evidence_pointer,
                  stage,error,run_id,failure_classification,etl_version,ontology_version,
                  mapping_version,status,retry_state,retry_attempts,created_at,updated_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'quarantined','not_requested',0,?,?)""",
                  (quarantine_id, endpoint, resource_iri, source_hash, observed,
                   evidence_pointer, stage, error, run_id, failure_classification,
                   version_values["etl_version"], version_values["ontology_version"],
                   version_values["mapping_version"], _now(), _now()))
                self._quarantine_history(
                    quarantine_id, "quarantined", run_id=run_id,
                    details={"stage": stage, "error": error,
                             "failure_classification": failure_classification},
                )
            else:
                immutable = (existing["endpoint"] == endpoint
                             and existing["resource_iri"] == resource_iri
                             and existing["source_hash"] == source_hash
                             and existing["observed_at"] == observed
                             and existing["evidence_pointer"] == evidence_pointer
                             and existing["stage"] == stage
                             and existing["failure_classification"] == failure_classification
                             and all(existing[key] == value for key, value in version_values.items()))
                if not immutable:
                    raise CoreStateError("quarantine evidence identity conflicts with immutable snapshot")
                self._quarantine_history(
                    quarantine_id, "failure_reobserved", run_id=run_id,
                    details={"error": error},
                )
            return quarantine_id

    def quarantine_records(self, *, endpoint: str | None = None,
                           status: str | None = None) -> list[dict]:
        if endpoint is not None and endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported quarantine endpoint: {endpoint}")
        if status is not None and status not in {"quarantined", "resolved"}:
            raise CoreStateError(f"unsupported quarantine status: {status}")
        clauses, parameters = [], []
        if endpoint is not None:
            clauses.append("endpoint=?")
            parameters.append(endpoint)
        if status is not None:
            clauses.append("status=?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM quarantine_record" + where +
            " ORDER BY created_at,quarantine_id", parameters)]

    def quarantine_history(self, quarantine_id: str) -> list[dict]:
        if self.connection.execute(
                "SELECT 1 FROM quarantine_record WHERE quarantine_id=?", (quarantine_id,)
        ).fetchone() is None:
            raise CoreStateError(f"unknown quarantine record: {quarantine_id}")
        result = []
        for raw in self.connection.execute(
                "SELECT * FROM quarantine_history WHERE quarantine_id=? ORDER BY created_at,history_id",
                (quarantine_id,)):
            row = dict(raw)
            row["details"] = json.loads(row.pop("details_json"))
            result.append(row)
        return result

    def request_quarantine_retry(self, quarantine_id: str, *, requested_by: str,
                                 reason: str | None = None) -> None:
        if not isinstance(requested_by, str) or not requested_by.strip():
            raise CoreStateError("quarantine retry requester must be non-empty")
        _assert_safe_provenance_metadata(requested_by, "quarantine retry requester")
        _assert_safe_provenance_metadata(reason, "quarantine retry reason")
        with self._transaction():
            row = self.connection.execute(
                "SELECT status,retry_state FROM quarantine_record WHERE quarantine_id=?",
                (quarantine_id,),
            ).fetchone()
            if row is None or row["status"] != "quarantined":
                raise CoreStateError(f"quarantine is not unresolved: {quarantine_id}")
            if row["retry_state"] == "in_progress":
                raise CoreStateError("quarantine retry is already in progress")
            self.connection.execute("""UPDATE quarantine_record SET retry_state='requested',
              updated_at=? WHERE quarantine_id=?""", (_now(), quarantine_id))
            self._quarantine_history(quarantine_id, "retry_requested", actor=requested_by,
                                     details={"reason": reason})

    def quarantines_for_retry(self, endpoint: str | None = None) -> list[dict]:
        if endpoint is not None and endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported quarantine endpoint: {endpoint}")
        where = " AND endpoint=?" if endpoint else ""
        parameters = (endpoint,) if endpoint else ()
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM quarantine_record WHERE status='quarantined' "
            "AND retry_state IN ('requested','failed','not_requested')" + where +
            " ORDER BY created_at,quarantine_id", parameters)]

    def start_quarantine_retry(self, quarantine_id: str, *, run_id: str) -> None:
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM quarantine_record WHERE quarantine_id=?", (quarantine_id,)
            ).fetchone()
            run = self.connection.execute("SELECT endpoint,status FROM etl_run WHERE run_id=?",
                                          (run_id,)).fetchone()
            if row is None or row["status"] != "quarantined":
                raise CoreStateError(f"quarantine is not unresolved: {quarantine_id}")
            if run is None or run["endpoint"] != row["endpoint"] or run["status"] != "running":
                raise CoreStateError("quarantine retry must use an active run for the same endpoint")
            if row["retry_state"] == "in_progress":
                raise CoreStateError("quarantine retry is already in progress")
            self.connection.execute("""UPDATE quarantine_record SET retry_state='in_progress',
              retry_attempts=retry_attempts+1,retry_run_id=?,retry_error=NULL,updated_at=?
              WHERE quarantine_id=?""", (run_id, _now(), quarantine_id))
            self._quarantine_history(quarantine_id, "retry_started", run_id=run_id)

    def finish_quarantine_retry(self, quarantine_id: str, *, run_id: str,
                                success: bool, error: str | None = None) -> None:
        if type(success) is not bool:
            raise CoreStateError("quarantine retry outcome must be explicit")
        if error is not None:
            if not isinstance(error, str):
                raise CoreStateError("quarantine retry error must be text")
            _assert_safe_provenance_metadata(error, "quarantine retry error")
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM quarantine_record WHERE quarantine_id=?", (quarantine_id,)
            ).fetchone()
            if (row is None or row["retry_state"] != "in_progress"
                    or row["retry_run_id"] != run_id):
                raise CoreStateError("quarantine retry does not match in-progress state")
            if success:
                self.connection.execute("""UPDATE quarantine_record SET status='resolved',
                  retry_state='succeeded',resolution='automatic retry succeeded',resolved_by='etl',
                  resolved_at=?,updated_at=? WHERE quarantine_id=?""",
                  (_now(), _now(), quarantine_id))
            else:
                self.connection.execute("""UPDATE quarantine_record SET status='quarantined',
                  retry_state='failed',retry_error=?,updated_at=? WHERE quarantine_id=?""",
                  (error, _now(), quarantine_id))
            self._quarantine_history(
                quarantine_id, "retry_succeeded" if success else "retry_failed",
                run_id=run_id, details={"error": None if success else error},
            )

    def resolve_quarantine(self, quarantine_id: str, *, resolution: str,
                           resolved_by: str) -> None:
        for value, label in ((resolution, "resolution"), (resolved_by, "resolver")):
            if not isinstance(value, str) or not value.strip():
                raise CoreStateError(f"quarantine {label} must be non-empty")
            _assert_safe_provenance_metadata(value, f"quarantine {label}")
        with self._transaction():
            row = self.connection.execute(
                "SELECT status,retry_state FROM quarantine_record WHERE quarantine_id=?",
                (quarantine_id,),
            ).fetchone()
            if row is None or row["status"] != "quarantined":
                raise CoreStateError(f"quarantine is not unresolved: {quarantine_id}")
            if row["retry_state"] == "in_progress":
                raise CoreStateError("cannot resolve quarantine while retry is in progress")
            self.connection.execute("""UPDATE quarantine_record SET status='resolved',
              resolution=?,resolved_by=?,resolved_at=?,updated_at=? WHERE quarantine_id=?""",
              (resolution, resolved_by, _now(), _now(), quarantine_id))
            self._quarantine_history(quarantine_id, "resolved", actor=resolved_by,
                                     details={"resolution": resolution})

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
                  parameters: dict, started_at: str | None = None,
                  versions: dict | None = None) -> str:
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported core ETL endpoint: {endpoint}")
        if run_kind not in {"full_refresh", "incremental_refresh", "complete_source_reconciliation"}:
            raise CoreStateError(f"unsupported core ETL run kind: {run_kind}")
        if type(is_complete) is not bool or not isinstance(parameters, dict):
            raise CoreStateError("run completeness and source parameters must be explicit")
        _assert_safe_provenance_metadata(parameters, "run parameters")
        if endpoint == "debates" and (is_complete or run_kind != "incremental_refresh"):
            raise CoreStateError(
                "Debates accepts only incomplete explicit-batch incremental runs")
        version_values = _versions(versions)
        run_id = str(uuid.uuid4())
        when = _utc_timestamp(started_at or _now(), "run start time")
        with self._transaction():
            # Online callers hold the database's advisory scan lock. Any old
            # running row for this endpoint survived a process interruption;
            # it must not remain indefinitely indistinguishable from live work.
            interrupted = self.connection.execute(
                "SELECT run.* FROM etl_run run WHERE run.endpoint=? AND run.status='running' "
                "AND NOT EXISTS (SELECT 1 FROM catalog_run_finalization pending "
                "WHERE pending.run_id=run.run_id)", (endpoint,)
            ).fetchall()
            self.connection.execute("""UPDATE etl_run SET status='failed',completed_at=?,
                outcome='failed',failure_scope='system',
                failure_classification='process_interruption',
                error='interrupted before completion; retry started'
                WHERE endpoint=? AND status='running' AND run_id NOT IN (
                  SELECT run_id FROM catalog_run_finalization)""", (_now(), endpoint))
            for old in interrupted:
                self._append_provenance_event(
                    "run_finished", run_id=old["run_id"], endpoint=endpoint,
                    versions={key: old[key] for key in
                              ("etl_version", "ontology_version", "mapping_version")},
                    details={"outcome": "failed", "failure_scope": "system",
                             "failure_classification": "process_interruption",
                             "error": "interrupted before completion; retry started"},
                )
            self.connection.execute("""INSERT INTO etl_run
              (run_id,endpoint,run_kind,is_complete,started_at,status,outcome,parameters_json,
               etl_version,ontology_version,mapping_version)
              VALUES (?,?,?,?,?,'running','running',?,?,?,?)""",
              (run_id, endpoint, run_kind, int(is_complete), when, _json(parameters),
               version_values["etl_version"], version_values["ontology_version"],
               version_values["mapping_version"]))
            self._append_provenance_event(
                "run_started", run_id=run_id, endpoint=endpoint, created_at=when,
                versions=version_values,
                details={"run_kind": run_kind, "is_complete": is_complete,
                         "parameters": parameters},
            )
        return run_id

    def record_run_summary(self, run_id: str, *, counters: dict | None = None,
                           timings: dict | None = None) -> dict:
        """Merge counters/timings into an active run's durable summary."""
        incoming = _run_summary({"counters": counters or {}, "timings": timings or {}})
        with self._transaction():
            row = self.connection.execute(
                "SELECT status,summary_json FROM etl_run WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None or row["status"] != "running":
                raise CoreStateError(f"run is not active: {run_id}")
            current = _run_summary(json.loads(row["summary_json"]))
            merged = _run_summary(incoming, current=current)
            self.connection.execute("UPDATE etl_run SET summary_json=? WHERE run_id=?",
                                    (_json(merged), run_id))
        return merged

    def _prepare_run_completion_locked(self, row, run_id: str, *, outcome: str,
                                       incremental_cursor: str | None,
                                       complete_scan: bool, summary: dict | None,
                                       completed_at: str | None) -> tuple[str, dict]:
        """Validate authority constraints and compute the durable terminal summary."""
        unresolved_quarantine = self.connection.execute(
            "SELECT 1 FROM quarantine_record WHERE endpoint=? AND status='quarantined' LIMIT 1",
            (row["endpoint"],),
        ).fetchone()
        current_run_quarantine = self.connection.execute(
            "SELECT 1 FROM quarantine_record WHERE run_id=? AND status='quarantined' LIMIT 1",
            (run_id,),
        ).fetchone()
        if outcome == "success" and current_run_quarantine is not None:
            raise CoreStateError("a run with unresolved record quarantine cannot succeed")
        authoritative_complete = (
            row["is_complete"] and json.loads(row["parameters_json"]).get("source")
            == AUTHORITATIVE_COMPLETE_SOURCES[row["endpoint"]]
        )
        if (outcome == "success" and unresolved_quarantine is not None
                and (incremental_cursor is not None or complete_scan or authoritative_complete)):
            raise CoreStateError(
                "unresolved endpoint quarantine prevents cursor/complete-source authority")
        if incremental_cursor is not None and (
                row["endpoint"] != "legislation"
                or row["run_kind"] not in {"incremental_refresh", "complete_source_reconciliation"}):
            raise CoreStateError("only a successful legislation refresh can advance its cursor")
        if complete_scan and (
                not row["is_complete"] or row["endpoint"] != "legislation"
                or row["run_kind"] != "complete_source_reconciliation"):
            raise CoreStateError(
                "missing-resource evidence requires a complete legislation reconciliation")
        parameters = json.loads(row["parameters_json"])
        if ((incremental_cursor is not None or complete_scan)
                and parameters.get("source") != "api"):
            raise CoreStateError("only an API source run can advance a cursor or establish absence")
        if incremental_cursor is not None:
            cursor_row = self.connection.execute(
                "SELECT incremental_cursor FROM endpoint_state WHERE endpoint='legislation'"
            ).fetchone()
            previous_cursor = cursor_row[0] if cursor_row else None
            if (previous_cursor is not None
                    and datetime.fromisoformat(incremental_cursor)
                    < datetime.fromisoformat(_utc_timestamp(
                        previous_cursor, "stored legislation cursor"))):
                raise CoreStateError("legislation cursor cannot move backwards")
        when = _utc_timestamp(completed_at or _now(), "run completion time")
        combined_summary = _run_summary(summary, current=json.loads(row["summary_json"]))
        elapsed = (datetime.fromisoformat(when) -
                   datetime.fromisoformat(_utc_timestamp(row["started_at"], "run start time")))
        combined_summary["timings"]["run_seconds"] = max(0.0, elapsed.total_seconds())
        return when, combined_summary

    def _apply_successful_run_authority_locked(self, row, run_id: str, *,
                                               completed_at: str,
                                               incremental_cursor: str | None,
                                               complete_scan: bool) -> None:
        """Apply cursor, completeness, and endpoint-success facts after publication."""
        if incremental_cursor is not None:
            cursor_row = self.connection.execute(
                "SELECT incremental_cursor FROM endpoint_state WHERE endpoint='legislation'"
            ).fetchone()
            previous_cursor = cursor_row[0] if cursor_row else None
            if (previous_cursor is not None
                    and datetime.fromisoformat(incremental_cursor)
                    < datetime.fromisoformat(_utc_timestamp(
                        previous_cursor, "stored legislation cursor"))):
                raise CoreStateError("legislation cursor cannot move backwards")
        source = json.loads(row["parameters_json"]).get("source")
        complete_run_id = (
            run_id if row["is_complete"]
            and source == AUTHORITATIVE_COMPLETE_SOURCES[row["endpoint"]] else None)
        self.connection.execute("""INSERT INTO endpoint_state
          (endpoint,last_successful_run_id,last_successful_complete_run_id,incremental_cursor,updated_at)
          VALUES (?,?,?,?,?) ON CONFLICT(endpoint) DO UPDATE SET
          last_successful_run_id=excluded.last_successful_run_id,
          last_successful_complete_run_id=COALESCE(excluded.last_successful_complete_run_id,
            endpoint_state.last_successful_complete_run_id),
          incremental_cursor=COALESCE(excluded.incremental_cursor,endpoint_state.incremental_cursor),
          updated_at=excluded.updated_at""",
          (row["endpoint"], run_id, complete_run_id, incremental_cursor, completed_at))
        if complete_scan:
            resources = self.connection.execute(
                "SELECT resource_iri,source_presence,missing_scan_count FROM resource_state "
                "WHERE endpoint='legislation' AND COALESCE(last_seen_run_id,'')<>?",
                (run_id,),
            ).fetchall()
            for resource in resources:
                count = resource["missing_scan_count"] + 1
                presence = ("missing" if resource["source_presence"] == "present"
                            else "confirmed_missing")
                self.connection.execute("""UPDATE resource_state SET source_presence=?,
                  last_missing_run_id=?,last_missing_at=?,missing_scan_count=?
                  WHERE endpoint='legislation' AND resource_iri=?""",
                  (presence, run_id, completed_at, count, resource["resource_iri"]))

    def finish_run(self, run_id: str, *, success: bool | None = None,
                   outcome: str | None = None, error: str | None = None,
                   completed_at: str | None = None, incremental_cursor: str | None = None,
                   complete_scan: bool = False, failure_scope: str | None = None,
                   failure_classification: str | None = None,
                   summary: dict | None = None) -> None:
        if success is None and outcome is None:
            raise CoreStateError("run outcome/success must be explicit")
        if success is not None and type(success) is not bool:
            raise CoreStateError("run success must be explicit")
        if outcome is not None and outcome not in {"success", "degraded", "failed"}:
            raise CoreStateError(f"unsupported run outcome: {outcome!r}")
        if success is not None:
            compatible_outcome = "success" if success else "failed"
            if outcome is not None and outcome != compatible_outcome:
                raise CoreStateError("success and outcome arguments disagree")
            outcome = compatible_outcome
        assert outcome is not None
        if error is not None:
            if not isinstance(error, str):
                raise CoreStateError("run error must be text")
            if outcome != "success":
                _assert_safe_provenance_metadata(error, "run error")
        if type(complete_scan) is not bool:
            raise CoreStateError("complete-scan finalization must be explicit")
        if incremental_cursor is not None:
            incremental_cursor = _utc_timestamp(incremental_cursor, "incremental cursor")
            if outcome != "success":
                raise CoreStateError("a degraded or failed run cannot advance the legislation cursor")
        if complete_scan and outcome != "success":
            raise CoreStateError("a degraded or failed run cannot establish missing-resource evidence")
        status = {"success": "succeeded", "degraded": "degraded", "failed": "failed"}[outcome]
        if outcome == "success":
            if failure_scope is not None or failure_classification is not None:
                raise CoreStateError("a successful run cannot have a failure classification")
        else:
            if failure_scope is None:
                failure_scope = "record" if outcome == "degraded" else "run"
            if failure_scope not in {"record", "source", "run", "system"}:
                raise CoreStateError(f"unsupported failure scope: {failure_scope!r}")
            if failure_classification is None:
                failure_classification = f"{failure_scope}_failure"
            if not isinstance(failure_classification, str) or not failure_classification.strip():
                raise CoreStateError("failure classification must be a non-empty string")
            _assert_safe_provenance_metadata(failure_classification,
                                             "run failure classification")
        with self._transaction():
            row = self.connection.execute("SELECT * FROM etl_run WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["status"] != "running":
                raise CoreStateError(f"run is not active: {run_id}")
            if self.connection.execute(
                    "SELECT 1 FROM catalog_run_finalization WHERE run_id=?", (run_id,)
            ).fetchone() is not None:
                raise CoreStateError(
                    "run has a pending catalog finalization; recover or fail it through the catalog boundary")
            when, combined_summary = self._prepare_run_completion_locked(
                row, run_id, outcome=outcome, incremental_cursor=incremental_cursor,
                complete_scan=complete_scan, summary=summary, completed_at=completed_at)
            self.connection.execute("""UPDATE etl_run SET completed_at=?,status=?,outcome=?,error=?,
                failure_scope=?,failure_classification=?,summary_json=? WHERE run_id=?""",
                (when, status, outcome, None if outcome == "success" else error,
                 failure_scope, failure_classification, _json(combined_summary), run_id))
            if outcome == "success":
                self._apply_successful_run_authority_locked(
                    row, run_id, completed_at=when,
                    incremental_cursor=incremental_cursor, complete_scan=complete_scan)
            self._append_provenance_event(
                "run_finished", run_id=run_id, endpoint=row["endpoint"], created_at=when,
                versions={key: row[key] for key in
                          ("etl_version", "ontology_version", "mapping_version")},
                details={"outcome": outcome, "failure_scope": failure_scope,
                         "failure_classification": failure_classification,
                         "error": None if outcome == "success" else error,
                         "summary": combined_summary},
            )

    def finish_failed_run_with_catalog(self, run_id: str, *, error: str,
                                       failure_scope: str,
                                       failure_classification: str,
                                       summary: dict, catalog_payload: str,
                                       completed_at: str | None = None) -> str:
        """Atomically fail a run and stage its exact failed catalog projection.

        Unlike the success/degraded finalization protocol, a fatal run has no
        authority to apply after catalog publication. Its terminal state can
        therefore be committed together with a dirty, hash-identified catalog
        candidate; a remote failure leaves that exact candidate replayable.
        """
        if not isinstance(error, str) or not error.strip():
            raise CoreStateError("failed run requires a non-empty error")
        _assert_safe_provenance_metadata(error, "run error")
        if failure_scope not in {"record", "source", "run", "system"}:
            raise CoreStateError(f"unsupported failure scope: {failure_scope!r}")
        if (not isinstance(failure_classification, str)
                or not failure_classification.strip()):
            raise CoreStateError("failure classification must be a non-empty string")
        _assert_safe_provenance_metadata(failure_classification,
                                         "run failure classification")
        if not isinstance(catalog_payload, str):
            raise CoreStateError("failed catalog candidate must be text")
        _assert_safe_provenance_metadata(catalog_payload, "failed catalog candidate")
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM etl_run WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None or row["status"] != "running":
                raise CoreStateError(f"run is not active: {run_id}")
            if self.connection.execute(
                    "SELECT 1 FROM catalog_run_finalization WHERE run_id=?", (run_id,)
            ).fetchone() is not None:
                raise CoreStateError(
                    "run has a pending catalog finalization; recover it through the catalog boundary")
            when, combined_summary = self._prepare_run_completion_locked(
                row, run_id, outcome="failed", incremental_cursor=None,
                complete_scan=False, summary=summary, completed_at=completed_at)
            digest = self._mark_catalog_dirty_locked(PROVENANCE_GRAPH_IRI, catalog_payload)
            self.connection.execute("""UPDATE etl_run SET completed_at=?,status='failed',
              outcome='failed',error=?,failure_scope=?,failure_classification=?,summary_json=?
              WHERE run_id=?""",
              (when, error, failure_scope, failure_classification,
               _json(combined_summary), run_id))
            self._append_provenance_event(
                "run_finished", run_id=run_id, endpoint=row["endpoint"], created_at=when,
                versions={key: row[key] for key in
                          ("etl_version", "ontology_version", "mapping_version")},
                details={"outcome": "failed", "failure_scope": failure_scope,
                         "failure_classification": failure_classification,
                         "error": error, "summary": combined_summary},
            )
            return digest

    def stage_run_catalog_finalization(
            self, run_id: str, *, outcome: str, error: str | None,
            completed_at: str, incremental_cursor: str | None = None,
            complete_scan: bool = False, failure_scope: str | None = None,
            failure_classification: str | None = None, summary: dict | None = None,
            catalog_payload: str, failure_payload: str) -> str:
        """Stage a terminal catalog candidate while keeping the run nonterminal.

        The exact planned candidate is durably dirty before remote replacement.
        A verified whole-graph catalog PUT finalizes the local run and applies
        cursor/absence authority. The separately validated failure candidate
        lets a failed PUT become a durable failed run without losing the payload
        that was attempted.
        """
        if outcome not in {"success", "degraded"}:
            raise CoreStateError("catalog finalization can stage only success or degraded outcomes")
        if error is not None:
            if not isinstance(error, str):
                raise CoreStateError("catalog finalization error must be text")
            _assert_safe_provenance_metadata(error, "catalog finalization error")
        if type(complete_scan) is not bool:
            raise CoreStateError("complete-scan finalization must be explicit")
        if not isinstance(catalog_payload, str) or not isinstance(failure_payload, str):
            raise CoreStateError("catalog candidates must be text")
        _assert_safe_provenance_metadata(catalog_payload, "catalog candidate")
        _assert_safe_provenance_metadata(failure_payload, "failed catalog candidate")
        planned_hash = hashlib.sha256(catalog_payload.encode("utf-8")).hexdigest()
        failure_hash = hashlib.sha256(failure_payload.encode("utf-8")).hexdigest()
        if planned_hash == failure_hash:
            raise CoreStateError("planned and failed catalog candidates must differ")
        if incremental_cursor is not None:
            incremental_cursor = _utc_timestamp(incremental_cursor, "incremental cursor")
            if outcome != "success":
                raise CoreStateError("a degraded run cannot advance the legislation cursor")
        if complete_scan and outcome != "success":
            raise CoreStateError("a degraded run cannot establish missing-resource evidence")
        if outcome == "success":
            if failure_scope is not None or failure_classification is not None:
                raise CoreStateError("a successful run cannot have a failure classification")
        else:
            if failure_scope is None:
                failure_scope = "record"
            if failure_scope not in {"record", "source", "run", "system"}:
                raise CoreStateError(f"unsupported failure scope: {failure_scope!r}")
            if failure_classification is None:
                failure_classification = f"{failure_scope}_failure"
            if not isinstance(failure_classification, str) or not failure_classification.strip():
                raise CoreStateError("failure classification must be a non-empty string")
            _assert_safe_provenance_metadata(failure_classification,
                                             "run failure classification")
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM etl_run WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None or row["status"] != "running":
                raise CoreStateError(f"run is not active: {run_id}")
            when, combined_summary = self._prepare_run_completion_locked(
                row, run_id, outcome=outcome, incremental_cursor=incremental_cursor,
                complete_scan=complete_scan, summary=summary, completed_at=completed_at)
            # A failed catalog publication must remain non-authoritative. Keep
            # the complete summary durable while the run is still `running`.
            self.connection.execute("UPDATE etl_run SET summary_json=? WHERE run_id=?",
                                    (_json(combined_summary), run_id))
            digest = self._mark_catalog_dirty_locked(PROVENANCE_GRAPH_IRI, catalog_payload)
            if digest != planned_hash:
                raise CoreStateError("staged catalog payload hash changed unexpectedly")
            self.connection.execute("""INSERT INTO catalog_run_finalization (
              graph_iri,run_id,planned_payload_hash,planned_outcome,error,failure_scope,
              failure_classification,completed_at,summary_json,incremental_cursor,
              complete_scan,failure_payload_hash,failure_payload,created_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (PROVENANCE_GRAPH_IRI, run_id, planned_hash, outcome, error,
               failure_scope, failure_classification, when, _json(combined_summary),
               incremental_cursor, int(complete_scan), failure_hash, failure_payload, _now()))
            return planned_hash

    def fail_pending_catalog_finalization(self, run_id: str, *, error: str) -> str:
        """Finalize a catalog-publication failure and stage its failed projection."""
        if not isinstance(error, str) or not error.strip():
            raise CoreStateError("catalog publication failure requires a non-empty error")
        _assert_safe_provenance_metadata(error, "catalog publication failure")
        with self._transaction():
            pending = self.connection.execute(
                "SELECT * FROM catalog_run_finalization WHERE run_id=?", (run_id,)
            ).fetchone()
            state = self.catalog_publication()
            run = self.connection.execute(
                "SELECT * FROM etl_run WHERE run_id=?", (run_id,)
            ).fetchone()
            if (pending is None or state is None or state["publication_state"] != "dirty"
                    or state["pending_payload_hash"] != pending["planned_payload_hash"]
                    or not isinstance(state["pending_payload"], str)
                    or hashlib.sha256(state["pending_payload"].encode("utf-8")).hexdigest()
                       != pending["planned_payload_hash"]):
                raise CoreStateError("pending catalog failure does not match its exact staged payload")
            if run is None or run["status"] != "running":
                raise CoreStateError("catalog failure run is not active")
            failure_error = f"catalog publication failed: {error}"
            when = pending["completed_at"]
            summary = json.loads(pending["summary_json"])
            failure_payload = pending["failure_payload"]
            failure_hash = pending["failure_payload_hash"]
            if hashlib.sha256(failure_payload.encode("utf-8")).hexdigest() != failure_hash:
                raise CoreStateError("failed catalog candidate does not match its durable hash")
            self.connection.execute("""INSERT INTO catalog_publication_attempt (
              attempt_id,graph_iri,run_id,payload_hash,payload,error,attempted_at)
              VALUES (?,?,?,?,?,?,?)""",
              (str(uuid.uuid4()), PROVENANCE_GRAPH_IRI, run_id,
               pending["planned_payload_hash"], state["pending_payload"],
               failure_error, _now()))
            self.connection.execute("""UPDATE etl_run SET completed_at=?,status='failed',
              outcome='failed',error=?,failure_scope='system',
              failure_classification='catalog_publication_failure',summary_json=?
              WHERE run_id=?""",
              (when, failure_error, _json(summary), run_id))
            self._append_provenance_event(
                "run_finished", run_id=run_id, endpoint=run["endpoint"],
                created_at=_now(),
                versions={key: run[key] for key in
                          ("etl_version", "ontology_version", "mapping_version")},
                details={"outcome": "failed", "failure_scope": "system",
                         "failure_classification": "catalog_publication_failure",
                         "error": failure_error, "planned_outcome": pending["planned_outcome"],
                         "planned_failure_scope": pending["failure_scope"],
                         "planned_failure_classification": pending["failure_classification"],
                         "planned_error": pending["error"],
                         "attempted_catalog_hash": pending["planned_payload_hash"],
                         "summary": summary},
            )
            self.connection.execute("""UPDATE catalog_publication_state SET
              pending_payload_hash=?,pending_payload=?,updated_at=? WHERE graph_iri=?""",
              (failure_hash, failure_payload, _now(), PROVENANCE_GRAPH_IRI))
            self.connection.execute(
                "DELETE FROM catalog_run_finalization WHERE graph_iri=?", (PROVENANCE_GRAPH_IRI,))
            return failure_hash

    def endpoint_publication(self, endpoint: str) -> dict | None:
        if endpoint not in SHARED_GRAPHS:
            raise CoreStateError(f"endpoint does not own a shared graph: {endpoint}")
        row = self.connection.execute(
            "SELECT publication_metadata_json FROM endpoint_state WHERE endpoint=?", (endpoint,)
        ).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def catalog_publication(self) -> dict | None:
        """Return the dedicated provenance-catalog dirty/clean publication state."""
        row = self.connection.execute(
            "SELECT * FROM catalog_publication_state WHERE graph_iri=?",
            (PROVENANCE_GRAPH_IRI,),
        ).fetchone()
        return dict(row) if row is not None else None

    def provenance_incomplete_records(self, *, include_resolved: bool = False) -> list[dict]:
        """Return legacy clean publications that still need verified evidence."""
        if type(include_resolved) is not bool:
            raise CoreStateError("provenance inventory resolution filter must be explicit")
        where = "" if include_resolved else " WHERE status='pending'"
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM provenance_incomplete" + where +
            " ORDER BY endpoint,resource_iri")]

    def mark_catalog_dirty(self, graph_iri: str, payload: str) -> str:
        """Durably stage an exact catalog payload before any remote replacement.

        Unlike ordinary graph/entity publication, catalog state is deliberately
        not written to ``provenance_event`` or ``graph_version``: doing so would
        make the catalog recursively depend on its own current publication.
        An outstanding dirty payload must be replayed before a different
        candidate can replace it.
        """
        if graph_iri != PROVENANCE_GRAPH_IRI:
            raise CoreStateError("catalog graph identity does not match the approved provenance graph")
        if not isinstance(payload, str):
            raise CoreStateError("catalog publication payload must be text")
        _assert_safe_provenance_metadata(payload, "catalog publication payload")
        with self._transaction():
            return self._mark_catalog_dirty_locked(graph_iri, payload)

    def _mark_catalog_dirty_locked(self, graph_iri: str, payload: str) -> str:
        """Stage a catalog payload inside an existing Core State transaction."""
        if graph_iri != PROVENANCE_GRAPH_IRI:
            raise CoreStateError("catalog graph identity does not match the approved provenance graph")
        if not isinstance(payload, str):
            raise CoreStateError("catalog publication payload must be text")
        _assert_safe_provenance_metadata(payload, "catalog publication payload")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        old = self.catalog_publication()
        if old is not None and old["publication_state"] == "dirty":
            if (old["pending_payload_hash"] != digest
                    or old["pending_payload"] != payload
                    or hashlib.sha256(old["pending_payload"].encode("utf-8")).hexdigest() != digest):
                raise CoreStateError(
                    "catalog has a different durable dirty payload; replay it before staging a new candidate")
            return digest
        self.connection.execute("""INSERT INTO catalog_publication_state (
          graph_iri,publication_state,published_payload_hash,published_payload,
          pending_payload_hash,pending_payload,last_published_at,updated_at)
          VALUES (?,'dirty',?,?,?, ?,NULL,?)
          ON CONFLICT(graph_iri) DO UPDATE SET
            publication_state='dirty',pending_payload_hash=excluded.pending_payload_hash,
            pending_payload=excluded.pending_payload,updated_at=excluded.updated_at""",
          (graph_iri, old["published_payload_hash"] if old else None,
           old["published_payload"] if old else None, digest, payload, _now()))
        return digest

    def mark_catalog_clean(self, graph_iri: str, payload_hash: str) -> None:
        """Complete catalog state only after the caller verifies the whole graph."""
        if graph_iri != PROVENANCE_GRAPH_IRI:
            raise CoreStateError("catalog graph identity does not match the approved provenance graph")
        if not isinstance(payload_hash, str) or re.fullmatch(r"[0-9a-f]{64}", payload_hash) is None:
            raise CoreStateError("catalog payload hash must be a lowercase SHA-256 digest")
        with self._transaction():
            state = self.catalog_publication()
            if (state is None or state["publication_state"] != "dirty"
                    or state["pending_payload_hash"] != payload_hash
                    or not isinstance(state["pending_payload"], str)
                    or hashlib.sha256(state["pending_payload"].encode("utf-8")).hexdigest()
                       != payload_hash):
                raise CoreStateError("catalog clean marker does not match durable pending payload")
            now = _now()
            finalization = self.connection.execute(
                "SELECT * FROM catalog_run_finalization WHERE graph_iri=?", (graph_iri,)
            ).fetchone()
            if finalization is not None:
                if finalization["planned_payload_hash"] != payload_hash:
                    raise CoreStateError("catalog candidate does not match pending run finalization")
                run = self.connection.execute(
                    "SELECT * FROM etl_run WHERE run_id=?", (finalization["run_id"],)
                ).fetchone()
                if run is None or run["status"] != "running":
                    raise CoreStateError("catalog finalization run is not active")
                outcome = finalization["planned_outcome"]
                status = {"success": "succeeded", "degraded": "degraded"}[outcome]
                summary = json.loads(finalization["summary_json"])
                failure_scope = finalization["failure_scope"]
                failure_classification = finalization["failure_classification"]
                error = finalization["error"]
                self.connection.execute("""UPDATE etl_run SET completed_at=?,status=?,outcome=?,
                  error=?,failure_scope=?,failure_classification=?,summary_json=? WHERE run_id=?""",
                  (finalization["completed_at"], status, outcome,
                   None if outcome == "success" else error, failure_scope,
                   failure_classification, _json(summary), finalization["run_id"]))
                if outcome == "success":
                    self._apply_successful_run_authority_locked(
                        run, finalization["run_id"],
                        completed_at=finalization["completed_at"],
                        incremental_cursor=finalization["incremental_cursor"],
                        complete_scan=bool(finalization["complete_scan"]))
                self._append_provenance_event(
                    "run_finished", run_id=finalization["run_id"],
                    endpoint=run["endpoint"], created_at=finalization["completed_at"],
                    versions={key: run[key] for key in
                              ("etl_version", "ontology_version", "mapping_version")},
                    details={"outcome": outcome, "failure_scope": failure_scope,
                             "failure_classification": failure_classification,
                             "error": None if outcome == "success" else error,
                             "summary": summary},
                )
                self.connection.execute(
                    "DELETE FROM catalog_run_finalization WHERE graph_iri=?", (graph_iri,))
            self.connection.execute("""UPDATE catalog_publication_state SET
              publication_state='clean',published_payload_hash=pending_payload_hash,
              published_payload=pending_payload,pending_payload_hash=NULL,pending_payload=NULL,
              last_published_at=?,updated_at=? WHERE graph_iri=?""",
              (now, now, graph_iri))

    def last_successful_complete_run(self, endpoint: str) -> dict | None:
        """Return only a successful complete run from the endpoint's authority."""
        if endpoint not in ENDPOINTS:
            raise CoreStateError(f"unsupported core ETL endpoint: {endpoint}")
        row = self.connection.execute("""SELECT run.* FROM endpoint_state state
          JOIN etl_run run ON run.run_id=state.last_successful_complete_run_id
          WHERE state.endpoint=? AND run.status='succeeded' AND run.outcome='success'
            AND run.is_complete=1""",
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
            "AND status='succeeded' AND outcome='success' AND is_complete=1", (run_id, endpoint),
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
                            member_source_run_id: str | None = None,
                            run_id: str | None = None,
                            entity_lineage: Mapping | None = None) -> str:
        if SHARED_GRAPHS.get(endpoint) != graph_iri:
            raise CoreStateError(f"shared graph identity does not match {endpoint}")
        _assert_safe_provenance_metadata(run_id, "shared graph run identity")
        _assert_safe_provenance_metadata(member_source_run_id,
                                         "shared graph source run identity")
        _assert_safe_provenance_metadata(entity_lineage, "shared graph entity lineage")
        if endpoint == "committees" and entity_lineage is None:
            from .provenance import ProvenanceCatalogError, shared_graph_entity_iris
            try:
                expected_entities = shared_graph_entity_iris(endpoint, payload)
            except ProvenanceCatalogError as error:
                raise CoreStateError(str(error)) from error
            if not expected_entities:
                raise CoreStateError(
                    "empty Committee graph requires explicit source lineage before staging")
        if member_source_run_id is not None:
            self.member_source_run_started_at(member_source_run_id)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self._transaction():
            if run_id is None:
                active = self.connection.execute(
                    "SELECT run_id FROM etl_run WHERE endpoint=? AND status='running' "
                    "ORDER BY started_at DESC LIMIT 1", (endpoint,),
                ).fetchone()
                run_id = active[0] if active else None
            elif (self.connection.execute(
                    "SELECT 1 FROM etl_run WHERE run_id=? AND status='running'",
                    (run_id,)).fetchone() is None):
                raise CoreStateError("shared graph publisher is not an active Core State run")
            old = self.endpoint_publication(endpoint) or {}
            if old.get("publication_state") == "dirty":
                raise CoreStateError(
                    f"shared {endpoint} graph has a durable dirty candidate; replay it before staging another")
            normalized_lineage = None
            if entity_lineage is not None:
                if run_id is None:
                    raise CoreStateError("shared entity lineage requires a publishing run")
                normalized_lineage = self._normalize_shared_entity_lineage_locked(
                    endpoint, graph_iri, payload, run_id, entity_lineage,
                    old_metadata=old)
                if endpoint == "committees" and not normalized_lineage:
                    self._validate_empty_committee_members_capture_locked(
                        member_source_run_id, run_id)
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
                        "pending_run_id": run_id,
                        "pending_coverage_authoritative": (
                            old.get("coverage_authoritative", False)
                            if coverage_authoritative is None
                            else bool(coverage_authoritative))}
            if normalized_lineage is not None:
                metadata["pending_entity_lineage"] = normalized_lineage
            self.connection.execute("""INSERT INTO endpoint_state
                (endpoint,publication_metadata_json,updated_at) VALUES (?,?,?)
                ON CONFLICT(endpoint) DO UPDATE SET
                publication_metadata_json=excluded.publication_metadata_json,
                updated_at=excluded.updated_at""", (endpoint, _json(metadata), _now()))
        return digest

    def complete_endpoint_publication(self, endpoint: str, graph_iri: str, payload_hash: str,
                                      *, coverage_authoritative: bool | None = None,
                                      publishing_run_id: str | None = None) -> None:
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
            pending_run_id = publishing_run_id or metadata.get("pending_run_id")
            member_source_run_id = metadata.get(
                "pending_member_source_run_id", metadata.get("member_source_run_id"))
            pending_lineage = metadata.get("pending_entity_lineage")
            if publishing_run_id is not None and self.connection.execute(
                    "SELECT 1 FROM etl_run WHERE run_id=? AND status='running'",
                    (publishing_run_id,)).fetchone() is None:
                raise CoreStateError("shared graph publication verifier is not an active Core State run")
            self.connection.execute("""UPDATE endpoint_state SET
                publication_metadata_json=?,updated_at=? WHERE endpoint=?""",
                (_json({"graph_iri": graph_iri, "publication_state": "clean",
                        "published_payload_hash": payload_hash,
                         "published_payload": published_payload,
                         "coverage_authoritative": authoritative,
                         "member_source_run_id": member_source_run_id,
                         "last_published_at": _now()}),
                 _now(), endpoint))
            self._store_graph_version(
                endpoint, graph_iri, published_payload, payload_hash,
                run_id=pending_run_id,
                member_source_run_id=(member_source_run_id
                                      if endpoint == "committees" and pending_lineage == {}
                                      else None),
            )
            if pending_lineage is not None:
                if not isinstance(pending_lineage, dict) or pending_run_id is None:
                    raise CoreStateError("dirty shared entity lineage is malformed or has no publisher")
                for entity_iri, lineage in sorted(pending_lineage.items()):
                    self._store_entity_version_locked(
                        graph_iri, payload_hash, endpoint, entity_iri,
                        pending_run_id, lineage)
            if endpoint in {"houses", "parties", "constituencies", "committees"}:
                self._inventory_legacy_shared_entity_gaps()
            observations = self.connection.execute(
                "SELECT evidence_pointer,versions_json FROM source_observation "
                "WHERE endpoint=? AND run_id=?",
                (endpoint, pending_run_id),
            ).fetchall() if pending_run_id is not None else []
            complete_lineage = (self._shared_entity_lineage_complete_locked(
                endpoint, graph_iri, payload_hash, published_payload)
                if endpoint in {"houses", "parties", "constituencies", "committees"}
                else any(isinstance(observation["evidence_pointer"], str)
                         and observation["evidence_pointer"].strip()
                         and all(_versions(json.loads(observation["versions_json"])).values())
                         for observation in observations))
            if complete_lineage:
                self.connection.execute("""UPDATE provenance_incomplete SET status='resolved',
                  resolved_at=?,resolution_run_id=? WHERE endpoint=? AND graph_iri=?
                  AND status='pending'""",
                  (_now(), pending_run_id, endpoint, graph_iri))

    def _entity_version_has_trace_locked(self, graph_iri: str, payload_hash: str,
                                         entity_iri: str, visited: set[str]) -> bool:
        key = payload_hash + "\0" + entity_iri
        if key in visited:
            return False
        visited.add(key)
        row = self.connection.execute(
            "SELECT prior_payload_hash FROM entity_version WHERE graph_iri=? "
            "AND payload_hash=? AND entity_iri=?",
            (graph_iri, payload_hash, entity_iri),
        ).fetchone()
        if row is None:
            return False
        sources = self.connection.execute(
            "SELECT source_hash,observed_at,evidence_pointer FROM entity_version_source "
            "WHERE graph_iri=? AND payload_hash=? AND entity_iri=?",
            (graph_iri, payload_hash, entity_iri),
        ).fetchall()
        for source in sources:
            page = self.connection.execute(
                "SELECT evidence_pointer,versions_json FROM source_observation "
                "WHERE source_hash=? AND observed_at=?",
                (source["source_hash"], source["observed_at"]),
            ).fetchone()
            if (page is not None and page["evidence_pointer"]
                    and all(_versions(json.loads(page["versions_json"])).values())
                    and source["evidence_pointer"].startswith(page["evidence_pointer"] + "#/")):
                return True
        prior_hash = row["prior_payload_hash"]
        return (prior_hash is not None and self._entity_version_has_trace_locked(
            graph_iri, prior_hash, entity_iri, visited))

    def _shared_entity_lineage_complete_locked(self, endpoint: str, graph_iri: str,
                                               payload_hash: str, payload: str) -> bool:
        from .provenance import (ProvenanceCatalogError,
                                 shared_graph_entity_iris)

        try:
            expected = shared_graph_entity_iris(endpoint, payload)
        except ProvenanceCatalogError:
            return False
        rows = self.connection.execute(
            "SELECT entity_iri FROM entity_version WHERE graph_iri=? AND payload_hash=?",
            (graph_iri, payload_hash),
        ).fetchall()
        entities = {row[0] for row in rows}
        return (entities == expected and all(
            self._entity_version_has_trace_locked(graph_iri, payload_hash,
                                                  entity_iri, set())
            for entity_iri in expected))

    def _validate_empty_committee_members_capture_locked(
            self, member_source_run_id: str | None, publishing_run_id: str) -> None:
        """Require persisted Members page evidence before an empty owner PUT."""
        if not isinstance(member_source_run_id, str) or not member_source_run_id:
            raise CoreStateError(
                "empty Committee graph requires its exact complete Members capture")
        publisher = self.connection.execute(
            "SELECT endpoint,parameters_json FROM etl_run WHERE run_id=?",
            (publishing_run_id,),
        ).fetchone()
        if publisher is None:
            raise CoreStateError("empty Committee graph publisher run is unavailable")
        publisher_parameters = json.loads(publisher["parameters_json"])
        if (publisher["endpoint"] == "members"
                and member_source_run_id != publishing_run_id):
            raise CoreStateError(
                "empty Committee graph Members publisher must identify its own capture")
        if (publisher["endpoint"] == "committees"
                and publisher_parameters.get("source_run_id") != member_source_run_id):
            raise CoreStateError(
                "empty Committee graph source differs from its Members capture run")
        if publisher["endpoint"] not in {"members", "committees", "parties", "constituencies"}:
            raise CoreStateError(
                "empty Committee graph publisher is not a reference-source run")
        self.member_source_run_started_at(member_source_run_id)
        if member_source_run_id != publishing_run_id and self.successful_complete_run(
                "members", member_source_run_id) is None:
            raise CoreStateError(
                "empty Committee graph source is not a successful complete Members API run")
        observations = self.connection.execute(
            "SELECT evidence_pointer,versions_json FROM source_observation "
            "WHERE endpoint='members' AND run_id=? ORDER BY observed_at,source_hash",
            (member_source_run_id,),
        ).fetchall()
        if not observations:
            raise CoreStateError(
                "empty Committee graph requires preserved Members capture source observations")
        for observation in observations:
            pointer = observation["evidence_pointer"]
            if (not isinstance(pointer, str) or not pointer.strip()
                    or "#" in pointer):
                raise CoreStateError(
                    "empty Committee graph requires preserved Members raw page pointers")
            try:
                versions = _versions(json.loads(observation["versions_json"]))
            except (TypeError, json.JSONDecodeError) as error:
                raise CoreStateError(
                    "empty Committee graph Members source metadata is invalid") from error
            if any(versions[key] is None for key in
                   ("etl_version", "ontology_version", "mapping_version")):
                raise CoreStateError(
                    "empty Committee graph Members capture lacks complete version metadata")

    def record_endpoint_member_source_run(self, endpoint: str, run_id: str) -> None:
        """Advance source provenance after an identical clean graph verifies."""
        if endpoint not in SHARED_GRAPHS:
            raise CoreStateError(f"endpoint does not own a shared graph: {endpoint}")
        _assert_safe_provenance_metadata(run_id, "shared graph source run identity")
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
                         expression_iri: str | None = None,
                         evidence_pointer: str | None = None,
                         request_parameters: dict | None = None,
                         versions: dict | None = None) -> dict:
        expected = expected_graph_iri(endpoint, resource_iri)
        if graph_iri != expected:
            raise CoreStateError(f"graph IRI does not match {endpoint} resource identity: {resource_iri}")
        if not isinstance(source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
            raise CoreStateError("observed source hash must be a lowercase SHA-256 digest")
        _assert_safe_provenance_metadata(run_id, "resource observation run identity")
        if endpoint == "debates":
            source_url = _safe_source_url(source_url)
            _assert_safe_provenance_metadata(raw_source_path, "Debates raw evidence path")
            _assert_safe_provenance_metadata(expression_iri, "Debates Expression identity")
            raw_source_path = _validate_debate_source_evidence(
                source_hash, raw_source_path, source_url, expression_iri)
        elif any(value is not None for value in (raw_source_path, source_url, expression_iri)):
            raise CoreStateError("raw AKN evidence fields are only defined for Debates resources")
        when = _utc_timestamp(observed_at or _now(), "resource observation time")
        pointer = evidence_pointer or raw_source_path
        _assert_safe_provenance_metadata(pointer, "resource evidence pointer")
        if source_url is not None:
            source_url = _safe_source_url(source_url)
        _assert_safe_provenance_metadata(expression_iri, "resource expression identity")
        if request_parameters is not None:
            if not isinstance(request_parameters, dict):
                raise CoreStateError("source request parameters must be an object")
            _assert_safe_provenance_metadata(request_parameters, "source request parameters")
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
            run = self.connection.execute(
                "SELECT endpoint,parameters_json FROM etl_run WHERE run_id=?", (run_id,)
            ).fetchone()
            # Some isolated transformation/publication test harnesses use an
            # opaque run token without creating Core State's run row. Preserve
            # that historical API behavior; production runs record observations
            # only when their durable run identity is available and matches.
            if run is not None and run["endpoint"] == endpoint:
                parameters = json.loads(run["parameters_json"])
                self._source_observation_locked(
                    endpoint, source_hash, when, run_id=run_id, evidence_pointer=pointer,
                    source_url=source_url,
                    request_parameters=(request_parameters if request_parameters is not None
                                        else parameters),
                    versions=versions,
                )
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
        for value, label in (
                (resolver_version, "resolver version"),
                (owner_snapshot_hash, "owner snapshot hash"),
                (reference_report_path, "reference report path"),
                (reference_report_hash, "reference report hash"),
                (run_id, "publication run identity")):
            _assert_safe_provenance_metadata(value, label)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        debate_raw_path = None
        if endpoint == "debates":
            source_url = _safe_source_url(source_url)
            _assert_safe_provenance_metadata(raw_source_path, "Debates raw evidence path")
            _assert_safe_provenance_metadata(expression_iri, "Debates Expression identity")
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
              pending_reference_report_hash,last_seen_run_id,last_seen_at FROM resource_state
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
            self._store_graph_version(
                endpoint, graph_iri, row["pending_payload"], payload_hash,
                run_id=row["last_seen_run_id"], entity_iri=resource_iri,
                source_hash=source_hash,
            )
            observed = self.connection.execute(
                "SELECT evidence_pointer,versions_json FROM source_observation "
                "WHERE source_hash=? AND observed_at=? "
                "AND run_id=? AND endpoint=?",
                (source_hash, _utc_timestamp(row["last_seen_at"], "resource observation time"),
                 row["last_seen_run_id"], endpoint),
            ).fetchone()
            if observed is not None and isinstance(observed["evidence_pointer"], str) \
                    and observed["evidence_pointer"].strip() \
                    and all(_versions(json.loads(observed["versions_json"])).values()):
                self.connection.execute("""UPDATE provenance_incomplete SET status='resolved',
                  resolved_at=?,resolution_run_id=? WHERE endpoint=? AND resource_iri=?
                  AND status='pending'""",
                  (_now(), row["last_seen_run_id"], endpoint, resource_iri))

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
            "SELECT run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,outcome,error,"
            "failure_scope,failure_classification,summary_json,etl_version,ontology_version,mapping_version,"
            "parameters_json "
            "FROM etl_run ORDER BY started_at DESC LIMIT 20")]
        for run in runs:
            run["is_complete"] = bool(run["is_complete"])
            run["parameters"] = json.loads(run.pop("parameters_json"))
            run["summary"] = json.loads(run.pop("summary_json"))
        quarantines = self.quarantine_records(status="quarantined")
        catalog = self.catalog_publication()
        catalog_status = None
        if catalog is not None:
            pending_finalization = self.connection.execute(
                "SELECT run_id FROM catalog_run_finalization WHERE graph_iri=?",
                (PROVENANCE_GRAPH_IRI,),
            ).fetchone()
            catalog_status = {
                "graph_iri": PROVENANCE_GRAPH_IRI,
                "publication_state": catalog["publication_state"],
                "published_payload_hash": catalog["published_payload_hash"],
                "pending_payload_hash": catalog["pending_payload_hash"],
                "pending_run_id": pending_finalization[0] if pending_finalization else None,
            }
        return {"schema_version": SCHEMA_VERSION, "database": str(self.path),
                "endpoints": endpoints, "dirty_resources": dirty_resources,
                "missing_resources": missing_resources,
                "recent_runs": runs, "quarantines": quarantines,
                "catalog_publication": catalog_status,
                "provenance_incomplete": self.provenance_incomplete_records()}

    @contextmanager
    def _transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise


class _CatalogPublicationBoundary:
    """Adapter matching ``provenance.ProvenancePublicationBoundary``."""

    def __init__(self, store: CoreStateStore):
        self._store = store

    def mark_dirty(self, graph_iri: str, payload: str) -> str:
        return self._store.mark_catalog_dirty(graph_iri, payload)

    def mark_clean(self, graph_iri: str, payload_hash: str) -> None:
        self._store.mark_catalog_clean(graph_iri, payload_hash)


def catalog_publication_boundary(store: CoreStateStore) -> _CatalogPublicationBoundary:
    """Adapt Core State to the catalog publisher's verified dirty/clean protocol."""
    if not isinstance(store, CoreStateStore):
        raise CoreStateError("catalog publication boundary requires CoreStateStore")
    return _CatalogPublicationBoundary(store)


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
  status TEXT NOT NULL CHECK(status IN ('running','succeeded','degraded','failed')),
  outcome TEXT NOT NULL CHECK(outcome IN ('running','success','degraded','failed')),
  error TEXT,
  parameters_json TEXT NOT NULL,
  failure_scope TEXT CHECK(failure_scope IS NULL OR failure_scope IN ('record','source','run','system')),
  failure_classification TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}',
  etl_version TEXT,
  ontology_version TEXT,
  mapping_version TEXT,
  CHECK((status='running' AND outcome='running') OR
        (status='succeeded' AND outcome='success') OR
        (status='degraded' AND outcome='degraded') OR
        (status='failed' AND outcome='failed'))
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


_ETL_RUN_V6 = """CREATE TABLE etl_run (
  run_id TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
  is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)),
  started_at TEXT NOT NULL,
  completed_at TEXT,
  status TEXT NOT NULL CHECK(status IN ('running','succeeded','degraded','failed')),
  outcome TEXT NOT NULL CHECK(outcome IN ('running','success','degraded','failed')),
  error TEXT,
  parameters_json TEXT NOT NULL,
  failure_scope TEXT CHECK(failure_scope IS NULL OR failure_scope IN ('record','source','run','system')),
  failure_classification TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}',
  etl_version TEXT,
  ontology_version TEXT,
  mapping_version TEXT,
  CHECK((status='running' AND outcome='running') OR
        (status='succeeded' AND outcome='success') OR
        (status='degraded' AND outcome='degraded') OR
        (status='failed' AND outcome='failed'))
)"""


_V6_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS source_observation (
  source_hash TEXT NOT NULL CHECK(length(source_hash)=64 AND source_hash NOT GLOB '*[^0-9a-f]*'),
  observed_at TEXT NOT NULL,
  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  run_id TEXT NOT NULL,
  evidence_pointer TEXT,
  source_url TEXT,
  request_parameters_json TEXT NOT NULL,
  versions_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  PRIMARY KEY(source_hash,observed_at)
);
CREATE INDEX IF NOT EXISTS source_observation_run ON source_observation(run_id,observed_at);
CREATE TABLE IF NOT EXISTS graph_version (
  graph_iri TEXT NOT NULL,
  payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64 AND payload_hash NOT GLOB '*[^0-9a-f]*'),
  payload TEXT NOT NULL,
  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  entity_iri TEXT,
  source_hash TEXT,
  first_run_id TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY(graph_iri,payload_hash)
);
CREATE INDEX IF NOT EXISTS graph_version_entity ON graph_version(endpoint,entity_iri,created_at);
CREATE TABLE IF NOT EXISTS provenance_event (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL CHECK(event_type IN ('run_started','run_finished','source_observed','graph_published','entity_published')),
  run_id TEXT,
  endpoint TEXT,
  graph_iri TEXT,
  payload_hash TEXT,
  entity_iri TEXT,
  source_hash TEXT,
  observed_at TEXT,
  evidence_pointer TEXT,
  versions_json TEXT NOT NULL,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS provenance_event_run ON provenance_event(run_id,created_at,event_id);
CREATE INDEX IF NOT EXISTS provenance_event_graph ON provenance_event(graph_iri,payload_hash);
CREATE TABLE IF NOT EXISTS catalog_publication_state (
  graph_iri TEXT PRIMARY KEY CHECK(graph_iri='https://data.oireachtas.ie/graph/provenance'),
  publication_state TEXT NOT NULL CHECK(publication_state IN ('clean','dirty')),
  published_payload_hash TEXT,
  published_payload TEXT,
  pending_payload_hash TEXT,
  pending_payload TEXT,
  last_published_at TEXT,
  updated_at TEXT NOT NULL,
  CHECK((published_payload_hash IS NULL) = (published_payload IS NULL)),
  CHECK((pending_payload_hash IS NULL) = (pending_payload IS NULL)),
  CHECK((publication_state='dirty' AND pending_payload_hash IS NOT NULL) OR
        (publication_state='clean' AND pending_payload_hash IS NULL))
);
CREATE TABLE IF NOT EXISTS quarantine_record (
  quarantine_id TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  resource_iri TEXT,
  source_hash TEXT NOT NULL CHECK(length(source_hash)=64 AND source_hash NOT GLOB '*[^0-9a-f]*'),
  observed_at TEXT NOT NULL,
  evidence_pointer TEXT NOT NULL,
  stage TEXT NOT NULL,
  error TEXT NOT NULL,
  run_id TEXT NOT NULL,
  failure_classification TEXT NOT NULL,
  etl_version TEXT NOT NULL,
  ontology_version TEXT NOT NULL,
  mapping_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('quarantined','resolved')),
  retry_state TEXT NOT NULL CHECK(retry_state IN ('not_requested','requested','in_progress','succeeded','failed')),
  retry_attempts INTEGER NOT NULL DEFAULT 0 CHECK(retry_attempts>=0),
  retry_run_id TEXT,
  retry_error TEXT,
  resolution TEXT,
  resolved_by TEXT,
  resolved_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS quarantine_endpoint_state ON quarantine_record(endpoint,status,retry_state,created_at);
CREATE TABLE IF NOT EXISTS quarantine_history (
  history_id TEXT PRIMARY KEY,
  quarantine_id TEXT NOT NULL REFERENCES quarantine_record(quarantine_id),
  action TEXT NOT NULL,
  run_id TEXT,
  actor TEXT,
  details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS quarantine_history_record ON quarantine_history(quarantine_id,created_at,history_id);
"""


_V6_TRIGGERS = (
    """CREATE TRIGGER IF NOT EXISTS provenance_event_no_update BEFORE UPDATE ON provenance_event
       BEGIN SELECT RAISE(ABORT,'provenance events are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS provenance_event_no_delete BEFORE DELETE ON provenance_event
       BEGIN SELECT RAISE(ABORT,'provenance events are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS source_observation_no_update BEFORE UPDATE ON source_observation
       BEGIN SELECT RAISE(ABORT,'source observations are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS source_observation_no_delete BEFORE DELETE ON source_observation
       BEGIN SELECT RAISE(ABORT,'source observations are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS graph_version_no_update BEFORE UPDATE ON graph_version
       BEGIN SELECT RAISE(ABORT,'graph versions are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS graph_version_no_delete BEFORE DELETE ON graph_version
       BEGIN SELECT RAISE(ABORT,'graph versions are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS quarantine_history_no_update BEFORE UPDATE ON quarantine_history
       BEGIN SELECT RAISE(ABORT,'quarantine history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS quarantine_history_no_delete BEFORE DELETE ON quarantine_history
       BEGIN SELECT RAISE(ABORT,'quarantine history is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS quarantine_record_evidence_immutable
       BEFORE UPDATE OF endpoint,resource_iri,source_hash,observed_at,evidence_pointer,stage,error,
         run_id,failure_classification,etl_version,ontology_version,mapping_version
       ON quarantine_record
       BEGIN SELECT RAISE(ABORT,'quarantine evidence is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS quarantine_record_no_delete BEFORE DELETE ON quarantine_record
       BEGIN SELECT RAISE(ABORT,'quarantine records are retained'); END""",
 )


_V7_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS catalog_run_finalization (
  graph_iri TEXT PRIMARY KEY CHECK(graph_iri='https://data.oireachtas.ie/graph/provenance'),
  run_id TEXT NOT NULL UNIQUE REFERENCES etl_run(run_id),
  planned_payload_hash TEXT NOT NULL CHECK(length(planned_payload_hash)=64
    AND planned_payload_hash NOT GLOB '*[^0-9a-f]*'),
  planned_outcome TEXT NOT NULL CHECK(planned_outcome IN ('success','degraded')),
  error TEXT,
  failure_scope TEXT,
  failure_classification TEXT,
  completed_at TEXT NOT NULL,
  summary_json TEXT NOT NULL,
  incremental_cursor TEXT,
  complete_scan INTEGER NOT NULL CHECK(complete_scan IN (0,1)),
  failure_payload_hash TEXT NOT NULL CHECK(length(failure_payload_hash)=64
    AND failure_payload_hash NOT GLOB '*[^0-9a-f]*'),
  failure_payload TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog_publication_attempt (
  attempt_id TEXT PRIMARY KEY,
  graph_iri TEXT NOT NULL CHECK(graph_iri='https://data.oireachtas.ie/graph/provenance'),
  run_id TEXT NOT NULL REFERENCES etl_run(run_id),
  payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64
    AND payload_hash NOT GLOB '*[^0-9a-f]*'),
  payload TEXT NOT NULL,
  error TEXT NOT NULL,
  attempted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS catalog_publication_attempt_run
  ON catalog_publication_attempt(run_id,attempted_at,attempt_id);
CREATE TABLE IF NOT EXISTS provenance_incomplete (
  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','debates','administrative-units','offices')),
  resource_iri TEXT,
  graph_iri TEXT NOT NULL,
  run_id TEXT,
  source_hash TEXT CHECK(source_hash IS NULL OR
    (length(source_hash)=64 AND source_hash NOT GLOB '*[^0-9a-f]*')),
  payload_hash TEXT CHECK(payload_hash IS NULL OR
    (length(payload_hash)=64 AND payload_hash NOT GLOB '*[^0-9a-f]*')),
  reason TEXT NOT NULL,
  required_action TEXT NOT NULL CHECK(required_action='validated_reobservation_and_republish'),
  status TEXT NOT NULL CHECK(status IN ('pending','resolved')),
  detected_at TEXT NOT NULL,
  resolved_at TEXT,
  resolution_run_id TEXT,
  PRIMARY KEY(endpoint,graph_iri),
  CHECK((status='pending' AND resolved_at IS NULL) OR
        (status='resolved' AND resolved_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS provenance_incomplete_status
  ON provenance_incomplete(status,endpoint,resource_iri);
"""

_V7_TRIGGERS = (
    """CREATE TRIGGER IF NOT EXISTS catalog_publication_attempt_no_update
       BEFORE UPDATE ON catalog_publication_attempt
       BEGIN SELECT RAISE(ABORT,'catalog publication attempts are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS catalog_publication_attempt_no_delete
       BEFORE DELETE ON catalog_publication_attempt
       BEGIN SELECT RAISE(ABORT,'catalog publication attempts are immutable'); END""",
)


_V8_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS entity_version (
  graph_iri TEXT NOT NULL,
  payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64
    AND payload_hash NOT GLOB '*[^0-9a-f]*'),
  entity_iri TEXT NOT NULL,
  endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees')),
  run_id TEXT NOT NULL REFERENCES etl_run(run_id),
  prior_payload_hash TEXT CHECK(prior_payload_hash IS NULL OR
    (length(prior_payload_hash)=64 AND prior_payload_hash NOT GLOB '*[^0-9a-f]*')),
  created_at TEXT NOT NULL,
  PRIMARY KEY(graph_iri,payload_hash,entity_iri),
  FOREIGN KEY(graph_iri,payload_hash) REFERENCES graph_version(graph_iri,payload_hash),
  FOREIGN KEY(graph_iri,prior_payload_hash,entity_iri)
    REFERENCES entity_version(graph_iri,payload_hash,entity_iri),
  CHECK(prior_payload_hash IS NULL OR prior_payload_hash != payload_hash)
);
CREATE INDEX IF NOT EXISTS entity_version_run ON entity_version(run_id,created_at);
CREATE TABLE IF NOT EXISTS entity_version_source (
  graph_iri TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  entity_iri TEXT NOT NULL,
  source_hash TEXT NOT NULL CHECK(length(source_hash)=64
    AND source_hash NOT GLOB '*[^0-9a-f]*'),
  observed_at TEXT NOT NULL,
  evidence_pointer TEXT NOT NULL,
  PRIMARY KEY(graph_iri,payload_hash,entity_iri,source_hash,observed_at,evidence_pointer),
  FOREIGN KEY(graph_iri,payload_hash,entity_iri)
    REFERENCES entity_version(graph_iri,payload_hash,entity_iri),
  FOREIGN KEY(source_hash,observed_at)
    REFERENCES source_observation(source_hash,observed_at)
);
CREATE INDEX IF NOT EXISTS entity_version_source_observation
  ON entity_version_source(source_hash,observed_at);
"""

_V8_TRIGGERS = (
    """CREATE TRIGGER IF NOT EXISTS entity_version_no_update BEFORE UPDATE ON entity_version
       BEGIN SELECT RAISE(ABORT,'entity versions are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS entity_version_no_delete BEFORE DELETE ON entity_version
       BEGIN SELECT RAISE(ABORT,'entity versions are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS entity_version_source_no_update
       BEFORE UPDATE ON entity_version_source
       BEGIN SELECT RAISE(ABORT,'entity version source evidence is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS entity_version_source_no_delete
       BEFORE DELETE ON entity_version_source
       BEGIN SELECT RAISE(ABORT,'entity version source evidence is immutable'); END""",
)
