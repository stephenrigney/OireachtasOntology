"""Integrity-checked loading of complete immutable API captures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .transforms.common import iri
from .transforms.members import member_graph_iri, source_hash
from .state import AUTHORITATIVE_COMPLETE_SOURCES


COUNT_FIELDS = {
    "houses": "housesCount",
    "members": "memberCount",
    "parties": "partyCount",
    "constituencies": "constituencyCount",
}


def load_complete_capture(directory: Path, endpoint: str) -> tuple[list[dict], int]:
    """Load and verify one complete API run from the immutable raw store."""
    if endpoint not in COUNT_FIELDS:
        raise ValueError(f"unsupported raw API capture endpoint: {endpoint}")
    directory = directory.expanduser().resolve()
    if not directory.is_dir() or not re.fullmatch(r"run-[0-9a-f-]{36}", directory.name):
        raise ValueError(f"{endpoint} capture must be a run-<uuid> directory: {directory}")
    run_id = directory.name.removeprefix("run-")
    raw_pages = sorted(path for path in directory.glob("skip-*.json")
                       if not path.name.endswith(".meta.json"))
    if not raw_pages:
        raise ValueError(f"{endpoint} capture has no raw pages: {directory}")

    records: list[dict] = []
    advertised: int | None = None
    expected_skip = 0
    for page_index, raw_path in enumerate(raw_pages):
        filename_match = re.fullmatch(r"skip-([0-9]{6,})\.json", raw_path.name)
        if filename_match is None or int(filename_match.group(1)) != expected_skip:
            raise ValueError(f"{endpoint} raw page filename does not match pagination order: {raw_path}")
        meta_path = raw_path.with_name(raw_path.name.removesuffix(".json") + ".meta.json")
        if not meta_path.is_file():
            raise ValueError(f"{endpoint} raw page has no metadata: {raw_path}")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            body = raw_path.read_bytes()
            page = json.loads(body)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid {endpoint} raw page {raw_path}: {error}") from error
        if (meta.get("run_id") != run_id or meta.get("status") != 200
                or meta.get("sha256") != hashlib.sha256(body).hexdigest()):
            raise ValueError(f"{endpoint} raw page metadata/run/hash is not authoritative: {raw_path}")
        params = meta.get("params")
        if (not isinstance(params, dict) or type(params.get("skip")) is not int
                or type(params.get("limit")) is not int or params["limit"] < 1
                or params["skip"] != expected_skip):
            raise ValueError(f"{endpoint} raw pages do not form a contiguous complete scan: {raw_path}")
        if not isinstance(page, dict) or not isinstance(page.get("results"), list):
            raise ValueError(f"{endpoint} raw page must contain a results array: {raw_path}")
        head, results = page.get("head"), page["results"]
        counts = head.get("counts") if isinstance(head, dict) else None
        count = counts.get(COUNT_FIELDS[endpoint]) if isinstance(counts, dict) else None
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{endpoint} page has no valid {COUNT_FIELDS[endpoint]} total")
        if advertised is None:
            advertised = count
        elif count != advertised:
            raise ValueError(f"{endpoint} advertised total changed during capture")
        if len(results) > params["limit"]:
            raise ValueError(f"{endpoint} page exceeds its requested limit")
        if page_index < len(raw_pages) - 1 and len(results) != params["limit"]:
            raise ValueError(f"{endpoint} capture stopped before its final page: {raw_path}")
        if page_index == len(raw_pages) - 1 and len(results) == params["limit"]:
            raise ValueError(f"{endpoint} capture is missing the terminal pagination page")
        records.extend(results)
        expected_skip += params["limit"]

    if advertised is None:
        raise ValueError(f"{endpoint} capture has no advertised total")
    if endpoint == "members":
        unique: dict[str, dict] = {}
        fingerprints: dict[str, str] = {}
        member_codes: dict[str, str] = {}
        member_graphs: dict[str, str] = {}
        for wrapper in records:
            if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
                raise ValueError("every Members capture result must contain a member object")
            member = wrapper["member"]
            identity = str(iri(member.get("uri")))
            code = member.get("memberCode")
            graph_iri = member_graph_iri(member)
            if code in member_codes and member_codes[code] != identity:
                raise ValueError(
                    f"Member memberCode collision (including URI aliases): {code}")
            if graph_iri in member_graphs and member_graphs[graph_iri] != identity:
                raise ValueError(
                    f"Member graph IRI collision (including URI aliases): {graph_iri}")
            member_codes[code] = identity
            member_graphs[graph_iri] = identity
            fingerprint = source_hash(member)
            if identity in fingerprints and fingerprints[identity] != fingerprint:
                raise ValueError(f"conflicting duplicate Member source identity: {identity}")
            fingerprints[identity] = fingerprint
            unique[identity] = wrapper
        records = [unique[identity] for identity in sorted(unique)]
    if len(records) != advertised:
        raise ValueError(
            f"{endpoint} capture contains {len(records)} unique records, not its advertised {advertised}")
    return records, advertised


def load_authoritative_capture(directory: Path, endpoint: str, store) -> tuple[list[dict], dict]:
    """Require immutable raw evidence to match a successful authoritative run."""
    directory = directory.expanduser().resolve()
    if not directory.is_dir() or not re.fullmatch(r"run-[0-9a-f-]{36}", directory.name):
        raise ValueError(f"{endpoint} capture must be a run-<uuid> directory: {directory}")
    run_id = directory.name.removeprefix("run-")
    run = store.successful_complete_run(endpoint, run_id)
    if (run is None or run.get("status") != "succeeded"
            or run.get("is_complete") not in (1, True)
            or run.get("parameters", {}).get("source")
            != AUTHORITATIVE_COMPLETE_SOURCES.get(endpoint)):
        raise ValueError(
            f"raw {endpoint} capture {run_id} is not a successful complete authoritative run")
    records, advertised = load_complete_capture(directory, endpoint)
    expected_endpoint = run["parameters"].get("api_url")
    if endpoint in COUNT_FIELDS and not isinstance(expected_endpoint, str):
        raise ValueError(f"authoritative {endpoint} state lacks its API source URL")
    raw_pages = [path for path in directory.glob("skip-*.meta.json")]
    page_files = [path for path in directory.glob("skip-*.json")
                  if not path.name.endswith(".meta.json")]
    expected_metadata = {
        path.with_name(path.name.removesuffix(".json") + ".meta.json")
        for path in page_files
    }
    if set(raw_pages) != expected_metadata:
        raise ValueError(f"{endpoint} capture has missing or orphan page metadata")
    expected_limit = run["parameters"].get("limit")
    for meta_path in raw_pages:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        params = metadata.get("params")
        if not isinstance(params, dict):
            raise ValueError(f"{endpoint} raw capture page has invalid request parameters")
        if expected_endpoint is not None and metadata.get("endpoint") != expected_endpoint:
            raise ValueError(f"{endpoint} raw capture source URL differs from core run state")
        if expected_limit is not None and params.get("limit") != expected_limit:
            raise ValueError(f"{endpoint} raw capture page limit differs from core run state")
    return records, {"run_id": run_id, "advertised_count": advertised,
                     "capture_directory": str(directory),
                     "parameters": run["parameters"]}


def load_latest_complete_capture(raw_root: Path, store, endpoint: str) -> tuple[list[dict], dict] | None:
    """Load the exact successful complete API run recorded by CoreStateStore."""
    run = store.last_successful_complete_run(endpoint)
    if run is None:
        return None
    run_id = run["run_id"]
    matches = sorted(Path(raw_root).expanduser().glob(
        f"{endpoint}/*/run-{run_id}"))
    if len(matches) != 1:
        raise ValueError(
            f"expected one immutable {endpoint} raw capture for successful run {run_id}; found {len(matches)}")
    return load_authoritative_capture(matches[0], endpoint, store)


class _ReadOnlyCoreCaptureIndex:
    """Minimal, query-only view used by the explicitly non-authoritative path."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def successful_complete_run(self, endpoint: str, run_id: str) -> dict | None:
        from .state import AUTHORITATIVE_COMPLETE_SOURCES

        row = self.connection.execute(
            "SELECT * FROM etl_run WHERE run_id=? AND endpoint=? "
            "AND status='succeeded' AND is_complete=1", (run_id, endpoint),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["parameters"] = json.loads(result.pop("parameters_json"))
        if result["parameters"].get("source") != AUTHORITATIVE_COMPLETE_SOURCES.get(endpoint):
            return None
        return result

    def last_successful_complete_run(self, endpoint: str) -> dict | None:
        row = self.connection.execute(
            "SELECT last_successful_complete_run_id FROM endpoint_state WHERE endpoint=?",
            (endpoint,),
        ).fetchone()
        if row is None or not row[0]:
            return None
        return self.successful_complete_run(endpoint, row[0])


def load_latest_development_capture(raw_root: Path, state_db: Path,
                                    endpoint: str) -> tuple[list[dict], dict]:
    """Read a preserved complete API capture without opening state for writes.

    This selector is intentionally separate from ETL execution. It reads the
    Core State pointer only to identify the already-recorded successful
    complete API run, then verifies that immutable capture's pages and hashes.
    It cannot create state, advance source evidence, or select fixtures/partial
    captures as authoritative input.
    """
    from .state import AUTHORITATIVE_COMPLETE_SOURCES

    if endpoint not in COUNT_FIELDS:
        raise ValueError(f"unsupported development capture endpoint: {endpoint}")
    state_path = Path(state_db).expanduser().resolve()
    try:
        connection = sqlite3.connect(state_path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as error:
        raise ValueError(
            f"cannot read existing Core State for the local development capture: {error}") from error
    try:
        index = _ReadOnlyCoreCaptureIndex(connection)
        run = index.last_successful_complete_run(endpoint)
        if run is None or run.get("parameters", {}).get("source") != \
                AUTHORITATIVE_COMPLETE_SOURCES[endpoint]:
            raise ValueError(
                f"no successful complete API {endpoint} capture is recorded; "
                "local development bootstrap uses preserved API captures and never fetches source data")
        run_id = run["run_id"]
        matches = sorted(Path(raw_root).expanduser().glob(
            f"{endpoint}/*/run-{run_id}"))
        if len(matches) != 1:
            raise ValueError(
                f"expected one preserved {endpoint} capture for run {run_id}; found {len(matches)}")
        return load_authoritative_capture(matches[0], endpoint, index)
    except sqlite3.Error as error:
        raise ValueError(f"cannot read existing Core State capture index: {error}") from error
    finally:
        connection.close()
