"""Exact-byte acquisition and content-addressed replay for AKN main.xml.

Debates source objects are deliberately supplied one URL/hash at a time by the
caller.  This module has no listing or pagination client and cannot enumerate
the debates corpus.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote_to_bytes, urlsplit
from urllib.request import Request, urlopen


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_BAD_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_AKN_MAIN_ROUTE = "/akn/ie/debateRecord/"
_REFERENCE_REPORT_CONTRACT = "debates-reference-outcomes-v1"


class DebateSourceError(ValueError):
    """An AKN source URL or preserved object does not meet the source contract."""


@dataclass(frozen=True)
class DebateRawSource:
    source_sha256: str
    raw_path: Path
    source_urls: tuple[str, ...]
    body: bytes


def validate_main_xml_url(value: object) -> str:
    """Require one explicit official AKN ``main.xml`` object URL."""
    if not isinstance(value, str) or not value:
        raise DebateSourceError("Debates source URL must be an explicit HTTPS AKN main.xml URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise DebateSourceError(f"invalid AKN source URL: {value!r}") from error
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.username is not None or parsed.password is not None or port is not None
            or parsed.query or parsed.fragment or not parsed.path.startswith(_AKN_MAIN_ROUTE)
            or not parsed.path.endswith("/main.xml") or _BAD_ESCAPE.search(parsed.path)):
        raise DebateSourceError(
            "Debates acquisition accepts only an official /akn/ie/debateRecord/.../main.xml URL")
    components = parsed.path[1:].split("/")
    if any(not component or component in {".", ".."} for component in components):
        raise DebateSourceError("AKN main.xml URL contains an empty or dot path component")
    return value


def _canonical_url_path(path: str) -> str:
    """Canonicalize URL path components for exact comparison with an Expression IRI."""
    if not path.startswith("/") or _BAD_ESCAPE.search(path):
        raise DebateSourceError("AKN source URL path is not a valid encoded absolute path")
    components = path[1:].split("/")
    if any(not component for component in components):
        raise DebateSourceError("AKN source URL path contains an empty component")
    try:
        decoded = [unquote_to_bytes(component).decode("utf-8", errors="strict")
                   for component in components]
    except UnicodeDecodeError as error:
        raise DebateSourceError("AKN source URL path contains invalid UTF-8 escapes") from error
    return "/" + "/".join(quote(component, safe="-._~") for component in decoded)


def validate_source_expression_url(source_url: str, expression_iri: str) -> None:
    """Reject fragments by requiring the source object path to be Expression/main.xml."""
    validate_main_xml_url(source_url)
    try:
        expression = urlsplit(expression_iri)
    except ValueError as error:
        raise DebateSourceError("invalid canonical Debate Expression IRI") from error
    if (expression.scheme != "https" or expression.netloc != "data.oireachtas.ie"
            or expression.query or expression.fragment
            or not expression.path.startswith(_AKN_MAIN_ROUTE)):
        raise DebateSourceError("Debate Expression IRI is outside the approved AKN route")
    parsed_source = urlsplit(source_url)
    expected_path = expression.path + "/main.xml"
    if _canonical_url_path(parsed_source.path) != expected_path:
        raise DebateSourceError(
            "AKN source URL is not the main.xml object for its exact FRBRExpression identity")


def fetch_main_xml(url: str, *, retries: int = 3, timeout: float = 30) -> tuple[bytes, str]:
    """Fetch only the explicitly supplied main.xml object, with bounded retries."""
    requested_url = validate_main_xml_url(url)
    request = Request(requested_url, headers={"Accept": "application/xml, text/xml"})
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                status = response.status
                final_url = validate_main_xml_url(response.geturl())
                if status != 200:
                    raise DebateSourceError(f"AKN main.xml acquisition failed: HTTP {status}")
                return response.read(), final_url
        except HTTPError as error:
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt == retries:
                raise DebateSourceError(f"AKN main.xml acquisition failed: HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            if attempt == retries:
                raise DebateSourceError(f"AKN main.xml acquisition failed: {error}") from error
        if attempt < retries:
            time.sleep(0.25 * (2 ** attempt))
    raise AssertionError("unreachable")


def _exclusive_bytes(path: Path, payload: bytes, *, description: str) -> None:
    """Create an immutable file without replacing an existing content address."""
    if path.exists():
        if path.read_bytes() != payload:
            raise DebateSourceError(f"immutable {description} collision: {path}")
        return
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise DebateSourceError(f"immutable {description} collision: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def _report_row_order(row: dict) -> tuple[str, str, str, str, str, str]:
    raw_reference = row.get("raw_reference")
    return (
        str(row.get("expression_iri", "")),
        str(row.get("source_node_iri", "")),
        str(row.get("source_attribute_qname", "")),
        "" if raw_reference is None else str(raw_reference),
        str(row.get("slot", "")),
        str(row.get("source_pointer", "")),
    )


def verify_reference_report(path: str | Path, digest: str, *,
                            source_sha256: str,
                            resolver_version: str,
                            owner_snapshot_hash: str | None = None) -> dict:
    """Read and verify one canonical, source/resolver-linked JSON sidecar."""
    if (not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
            or not isinstance(source_sha256, str)
            or _SHA256.fullmatch(source_sha256) is None
            or not isinstance(resolver_version, str) or not resolver_version):
        raise DebateSourceError("Debates reference report identity is invalid")
    if (owner_snapshot_hash is not None
            and (not isinstance(owner_snapshot_hash, str)
                 or _SHA256.fullmatch(owner_snapshot_hash) is None)):
        raise DebateSourceError("Debates reference report owner snapshot hash is invalid")
    report_path = Path(path).expanduser()
    if not report_path.is_absolute():
        raise DebateSourceError("Debates reference report path must be absolute")
    try:
        payload = report_path.read_bytes()
    except OSError as error:
        raise DebateSourceError(
            f"Debates reference report is unavailable: {report_path}") from error
    if hashlib.sha256(payload).hexdigest() != digest:
        raise DebateSourceError(
            f"Debates reference report hash does not match its sidecar: {report_path}")
    try:
        text = payload.decode("utf-8", errors="strict")
        report = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DebateSourceError(
            f"Debates reference report is not valid UTF-8 JSON: {report_path}") from error
    if not isinstance(report, dict):
        raise DebateSourceError("Debates reference report must be a JSON object")
    canonical = json.dumps(report, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    if payload != canonical:
        raise DebateSourceError(
            f"Debates reference report is not canonical sorted UTF-8 JSON: {report_path}")
    if (report.get("contract_version") != _REFERENCE_REPORT_CONTRACT
            or report.get("source_sha256") != source_sha256
            or report.get("resolver_version") != resolver_version):
        raise DebateSourceError(
            f"Debates reference report does not match its source/resolver: {report_path}")
    if owner_snapshot_hash is not None:
        resolution_key = hashlib.sha256(json.dumps(
            [resolver_version, owner_snapshot_hash], ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        expected_name = f"{source_sha256}.{resolution_key}.{digest}.reference-report.json"
        if report_path.name != expected_name:
            raise DebateSourceError(
                f"Debates reference report path does not match its owner snapshot: {report_path}")
    outcomes = report.get("reference_outcomes")
    if not isinstance(outcomes, list) or any(not isinstance(row, dict) for row in outcomes):
        raise DebateSourceError("Debates reference report outcomes must be a JSON array of rows")
    if outcomes != sorted(outcomes, key=_report_row_order):
        raise DebateSourceError("Debates reference report outcomes are not deterministically sorted")
    for row in outcomes:
        if (row.get("contract_version") != _REFERENCE_REPORT_CONTRACT
                or row.get("source_sha256") != source_sha256):
            raise DebateSourceError(
                "Debates reference report outcome is not linked to the exact source")
    return report


def persist_reference_report(raw_source: DebateRawSource, report_bytes: bytes, *,
                             resolver_version: str,
                             owner_snapshot_hash: str) -> tuple[str, str]:
    """Persist a hash-linked immutable report keyed by source and resolution view.

    The filename includes the source hash, a digest of resolver/owner-snapshot
    identity, and the report content digest. A later report therefore creates a
    new immutable sidecar rather than replacing evidence from an earlier run.
    """
    if hashlib.sha256(raw_source.body).hexdigest() != raw_source.source_sha256:
        raise DebateSourceError("Debates reference report source bytes fail their content hash")
    if (not isinstance(resolver_version, str) or not resolver_version
            or not isinstance(owner_snapshot_hash, str)
            or _SHA256.fullmatch(owner_snapshot_hash) is None):
        raise DebateSourceError("Debates reference report resolver/owner snapshot is invalid")
    if not isinstance(report_bytes, bytes):
        raise DebateSourceError("Debates reference report must be exact UTF-8 JSON bytes")
    digest = hashlib.sha256(report_bytes).hexdigest()
    # Validate before writing so malformed or mismatched report data never
    # becomes durable evidence or advances Core State.
    try:
        report = json.loads(report_bytes.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DebateSourceError("Debates reference report is not valid UTF-8 JSON") from error
    if not isinstance(report, dict) or report.get("source_sha256") != raw_source.source_sha256:
        raise DebateSourceError("Debates reference report does not identify its exact raw source")
    if report.get("resolver_version") != resolver_version:
        raise DebateSourceError("Debates reference report does not identify its resolver version")
    owner_resolution_key = hashlib.sha256(json.dumps(
        [resolver_version, owner_snapshot_hash], ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    path = raw_source.raw_path.expanduser().resolve().parent / (
        f"{raw_source.source_sha256}.{owner_resolution_key}.{digest}.reference-report.json")
    _exclusive_bytes(path, report_bytes, description="Debates reference report")
    verify_reference_report(path, digest, source_sha256=raw_source.source_sha256,
                            resolver_version=resolver_version,
                            owner_snapshot_hash=owner_snapshot_hash)
    return str(path.resolve()), digest


def persist_main_xml(root: Path, body: bytes, source_url: str) -> DebateRawSource:
    """Persist exact XML bytes at a SHA-256 address outside the state database."""
    source_url = validate_main_xml_url(source_url)
    if not isinstance(body, bytes) or not body:
        raise DebateSourceError("AKN main.xml body must be non-empty exact bytes")
    digest = hashlib.sha256(body).hexdigest()
    directory = Path(root).expanduser() / "debates" / "sha256" / digest[:2]
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"{digest}.xml"
    metadata_path = directory / f"{digest}.{hashlib.sha256(source_url.encode('utf-8')).hexdigest()}.meta.json"
    metadata = {
        "byte_length": len(body),
        "source_contract": "akn-main-xml-v1",
        "source_sha256": digest,
        "source_url": source_url,
    }
    metadata_bytes = (json.dumps(metadata, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")) + "\n").encode("utf-8")
    _exclusive_bytes(raw_path, body, description="AKN XML object")
    _exclusive_bytes(metadata_path, metadata_bytes, description="AKN XML metadata")
    return DebateRawSource(digest, raw_path, (source_url,), body)


def load_main_xml(root: Path, digest: str) -> DebateRawSource:
    """Load exact preserved bytes and all verified official source references."""
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise DebateSourceError("Debates replay key must be a lowercase SHA-256 digest")
    directory = Path(root).expanduser() / "debates" / "sha256" / digest[:2]
    raw_path = directory / f"{digest}.xml"
    try:
        body = raw_path.read_bytes()
    except OSError as error:
        raise DebateSourceError(f"preserved AKN XML object is unavailable: {digest}") from error
    if hashlib.sha256(body).hexdigest() != digest:
        raise DebateSourceError(f"preserved AKN XML object failed its content hash: {digest}")
    source_urls: set[str] = set()
    metadata_paths = sorted(directory.glob(f"{digest}.*.meta.json"))
    if not metadata_paths:
        raise DebateSourceError(f"preserved AKN XML object has no source evidence metadata: {digest}")
    for path in metadata_paths:
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise DebateSourceError(f"invalid AKN XML source metadata: {path}") from error
        if (metadata.get("source_contract") != "akn-main-xml-v1"
                or metadata.get("source_sha256") != digest
                or metadata.get("byte_length") != len(body)):
            raise DebateSourceError(f"AKN XML source metadata does not match its object: {path}")
        source_url = validate_main_xml_url(metadata.get("source_url"))
        expected_name = (f"{digest}."
                         f"{hashlib.sha256(source_url.encode('utf-8')).hexdigest()}.meta.json")
        if path.name != expected_name:
            raise DebateSourceError(f"AKN XML metadata path does not match its source URL: {path}")
        source_urls.add(source_url)
    return DebateRawSource(digest, raw_path, tuple(sorted(source_urls)), body)
