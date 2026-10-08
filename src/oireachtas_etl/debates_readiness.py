"""Manifest-locked selection and bounded batches for the initial Debates load."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
import hashlib
import json
from pathlib import Path
import re

from .debates_raw import DebateRawSource, load_main_xml, validate_main_xml_url

_SCHEMA = "debates-initial-production-inventory-v1"
_START = "2011-01-01"
_CATEGORIES = {"dail", "seanad", "committee"}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class DebateReadinessError(ValueError):
    """A frozen initial-selection manifest or its evidence is invalid."""


@dataclass(frozen=True)
class ManifestRecord:
    url: str
    work_iri: str
    category: str
    date: str
    sha256: str
    source_bytes: int
    status: str
    failure_stage: str | None
    failure_classification: str | None
    metadata_evidence_path: str
    metadata_sha256: str


@dataclass(frozen=True)
class ManifestBatch:
    index: int
    records: tuple[ManifestRecord, ...]
    source_bytes: int


@dataclass(frozen=True)
class DebateManifest:
    path: Path
    sha256: str
    records: tuple[ManifestRecord, ...]


def load_manifest(path: str | Path) -> DebateManifest:
    """Validate the exact inventory selection and its assessed evidence rows."""
    manifest_path = Path(path).expanduser().resolve()
    try:
        raw = manifest_path.read_bytes()
        document = json.loads(raw.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DebateReadinessError(f"cannot read Debates inventory: {manifest_path}") from error
    if not isinstance(document, dict) or document.get("schema") != _SCHEMA:
        raise DebateReadinessError(f"unsupported Debates inventory schema: {manifest_path}")
    selection = document.get("selection")
    selection_records = selection.get("records") if isinstance(selection, dict) else None
    contract = selection.get("contract") if isinstance(selection, dict) else None
    results = document.get("records")
    if not isinstance(selection_records, list) or not selection_records:
        raise DebateReadinessError("Debates inventory selection.records must be a non-empty array")
    if not isinstance(results, list) or len(results) != len(selection_records):
        raise DebateReadinessError("Debates inventory assessment rows do not cover selection rows")
    if (not isinstance(contract, dict)
            or contract.get("census_window_start_inclusive") != _START
            or contract.get("categories") != ["committee", "dail", "seanad"]
            or contract.get("written_answers") != "excluded"
            or contract.get("bill_linkage_filter") != "none"
            or contract.get("selection_key") != "unique official main.xml URL"):
        raise DebateReadinessError("Debates inventory selection contract differs from the approved scope")
    assessed: dict[str, dict] = {}
    for row in results:
        if not isinstance(row, dict) or not isinstance(row.get("source_url"), str):
            raise DebateReadinessError("Debates inventory contains an invalid assessment row")
        if row["source_url"] in assessed:
            raise DebateReadinessError("Debates inventory contains duplicate source URLs")
        assessed[row["source_url"]] = row
    if set(assessed) != {row.get("url") for row in selection_records if isinstance(row, dict)}:
        raise DebateReadinessError("inventory assessment URLs differ from frozen selection URLs")
    records: list[ManifestRecord] = []
    seen_urls: set[str] = set()
    seen_work: set[str] = set()
    for row in selection_records:
        if not isinstance(row, dict):
            raise DebateReadinessError("Debates selection contains a non-object row")
        url = validate_main_xml_url(row.get("url"))
        row_date, category, digest = row.get("date"), row.get("category"), row.get("source_sha256")
        work_uri, byte_length = row.get("api_work_uri"), row.get("source_bytes")
        try:
            parsed_date = date_type.fromisoformat(row_date) if isinstance(row_date, str) else None
        except ValueError:
            parsed_date = None
        if (parsed_date is None or parsed_date.isoformat() != row_date or row_date < _START
                or category not in _CATEGORIES or "/writtens/" in url
                or not isinstance(work_uri, str) or not work_uri
                or not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length <= 0
                or not isinstance(digest, str) or _SHA256.fullmatch(digest) is None):
            raise DebateReadinessError(f"Debates selection row is outside or invalid for scope: {url}")
        if url in seen_urls:
            raise DebateReadinessError(f"duplicate Debates selection URL: {url}")
        if work_uri in seen_work:
            raise DebateReadinessError(f"multiple listing sources for one API Work: {work_uri}")
        seen_urls.add(url)
        seen_work.add(work_uri)
        result = assessed[url]
        if (result.get("source_sha256") != digest or result.get("source_bytes") != byte_length
                or result.get("category") != category or result.get("date") != row_date):
            raise DebateReadinessError(f"assessment identity differs from selection row: {url}")
        status = result.get("status")
        if status not in {"eligible", "quarantined"}:
            raise DebateReadinessError(f"unknown Debates inventory disposition for {url}: {status!r}")
        if status == "quarantined" and not result.get("failure_stage"):
            raise DebateReadinessError(f"quarantine inventory row lacks failure stage: {url}")
        metadata_path = result.get("metadata_evidence_path")
        metadata_hash = result.get("metadata_sha256")
        if (not isinstance(metadata_path, str) or Path(metadata_path).is_absolute()
                or ".." in Path(metadata_path).parts or not isinstance(metadata_hash, str)
                or _SHA256.fullmatch(metadata_hash) is None):
            raise DebateReadinessError(f"inventory metadata evidence identity is invalid: {url}")
        records.append(ManifestRecord(
            url, result.get("work_iri") or "", category, row_date, digest,
            byte_length, status, result.get("failure_stage"),
            result.get("failure_classification"), metadata_path, metadata_hash,
        ))
    return DebateManifest(manifest_path, hashlib.sha256(raw).hexdigest(),
                          tuple(sorted(records, key=lambda record: record.url)))


def make_batches(manifest: DebateManifest, *, max_works: int = 25,
                 max_source_bytes: int = 64 * 1024 * 1024) -> tuple[ManifestBatch, ...]:
    """Build deterministic batches; surface any individually oversized source."""
    if max_works < 1 or max_source_bytes < 1:
        raise DebateReadinessError("Debates batch ceilings must be positive")
    batches: list[ManifestBatch] = []
    current: list[ManifestRecord] = []
    current_bytes = 0
    for record in manifest.records:
        if record.source_bytes > max_source_bytes:
            raise DebateReadinessError(
                f"source exceeds batch byte ceiling ({record.source_bytes} > {max_source_bytes}); "
                f"explicit operator disposition required: {record.url}")
        if current and (len(current) >= max_works
                        or current_bytes + record.source_bytes > max_source_bytes):
            batches.append(ManifestBatch(len(batches), tuple(current), current_bytes))
            current, current_bytes = [], 0
        current.append(record)
        current_bytes += record.source_bytes
    if current:
        batches.append(ManifestBatch(len(batches), tuple(current), current_bytes))
    return tuple(batches)


def load_batch_sources(batch: ManifestBatch, raw_root: str | Path) -> list[DebateRawSource]:
    """Load and verify exact content-addressed objects in a selected batch."""
    loaded: list[DebateRawSource] = []
    for record in batch.records:
        metadata_path = Path(raw_root).expanduser() / record.metadata_evidence_path
        try:
            metadata = metadata_path.read_bytes()
        except OSError as error:
            raise DebateReadinessError(
                f"inventory metadata evidence is unavailable: {metadata_path}") from error
        if hashlib.sha256(metadata).hexdigest() != record.metadata_sha256:
            raise DebateReadinessError(
                f"inventory metadata evidence hash differs: {metadata_path}")
        source = load_main_xml(raw_root, record.sha256)
        if (source.source_sha256 != record.sha256 or len(source.body) != record.source_bytes
                or record.url not in source.source_urls):
            raise DebateReadinessError(
                f"preserved source evidence differs from the versioned inventory: {record.url}")
        loaded.append(source)
    return loaded
