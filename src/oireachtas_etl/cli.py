from __future__ import annotations
import argparse, json, os, re, sys, time, uuid
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
from .api import ApiClient, HousesApiClient
from .config import (ADMINISTRATIVE_UNITS_GRAPH, COMMITTEES_GRAPH,
                     CONSTITUENCIES_GRAPH, HOUSES_GRAPH,
                     OFFICES_GRAPH, OFFICE_REGISTRY_FILE, OFFICE_DECISIONS_FILE,
                     BILL_SPONSOR_DECISIONS_FILE, BILL_SPONSOR_STATE_DB_FILE,
                     OFFICE_OCCURRENCE_STATE_DB_FILE, PARTIES_GRAPH,
                     REFERENCE_ONTOLOGY_VERSION, Settings)
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_member_competency, verify_bill_competency
from .competency import verify_core_graph
from .raw import persist_raw
from .debates_raw import (DebateSourceError, fetch_main_xml, load_main_xml,
                          persist_main_xml)
from .debates_pipeline import run_debate_batch
from .serialization import nquads, ntriples, turtle
from .transforms.houses import PERSISTENT_HOUSES, transform_houses_with_report
from .transforms.parties import transform_parties
from .transforms.constituencies import transform_constituencies
from .transforms.committees import transform_committees
from .transforms.offices import transform_administrative_units, transform_offices
from .validation import validate_constituencies, validate_houses, validate_parties
from .validation import validate_administrative_units, validate_offices, validate_registry_source
from .validation import validate_member, validate_bill
from .validation.committees import validate_committees
from .validation.members import validate_member_source
from .transforms.members import (member_graph_iri, prior_party_membership_evidence,
                                 source_hash, transform_member_with_report)
from .transforms.common import MEMBERS, datetime_literal, iri
from .transforms.offices import office_iri
from .transforms.bills import bill_graph_iri, source_hash as bill_source_hash, transform_bill_with_report
from .validation.bills import validate_bill_source
from .state import (CoreStateStore, expected_graph_iri, read_resource_state,
                    state_lock)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, PROV, XSD
from .transforms.common import ELIDL, OIR
from .reconciliation import (DbpediaClient, ReconciliationStore, WikidataClient,
                              FixtureResponseError, external_graph_iri, party_external_graph_iri,
                               load_party_review, load_review, normalize_party_candidate,
                               deduplicate_party_records, reconcile_party_records, reconcile_records, valid_qid,
                               _enwiki, _fetch_wikidata_target,
                               _institution_candidate_negative_evidence,
                               _normalize_institution_candidate_for, deduplicate_institution_records,
                               institution_external_graph_iri, institution_records,
                               load_institution_review,
                               reconcile_institution_records, reconciliation_identity,
                               _office_candidate_negative_evidence,
                               _normalize_office_candidate_for,
                               deduplicate_external_office_records,
                               load_external_office_review,
                               office_external_graph_iri, office_external_records,
                               reconcile_external_office_records)
from .office_observations import canonical_json, extract_office_observations, json_hash
from .office_reconciliation import OfficeOccurrenceStore, load_office_review
from .bill_sponsor_reconciliation import (BillSponsorStore, bill_sponsor_graph_iri,
                                          extract_bill_sponsor_observations,
                                          load_bill_sponsor_review, json_hash as sponsor_json_hash)
from .bill_sponsor_publication import BillSponsorPublication
from .transforms.bill_sponsors import build_bill_sponsor_graph
from .validation.bill_sponsors import validate_bill_sponsor_graph
from .reference_coverage import build_reference_census, summary as reference_census_summary
from .reference_closure import (candidate_member_dataset,
                                verify_reference_closure)
from .reference_publication import (build_development_reference_candidates,
                                    build_reference_candidates)
from .raw_captures import (capture_record_pointers, load_latest_complete_capture,
                           load_latest_development_capture)
from .provenance import (ETL, build_provenance_catalog,
                          package_version as etl_package_version,
                          shared_graph_entity_iris,
                          validate_provenance_catalog)
from .source_contract import classify_source_contract, classify_source_envelope
from .state import (PROVENANCE_GRAPH_IRI, catalog_publication_boundary,
                    run_resource_iri)


MEMBER_MAPPING_VERSION = "member_mapping.csv@reference-coverage-2026"
DEBATES_ONTOLOGY_VERSION = (
    "debates.owl.ttl@sha256:f85566827205594c4b51b0eda05516d2bff34e41d211d00adf04b450f5c9bf21")
DEBATES_MAPPING_VERSION = (
    "debates_mapping.csv@sha256:7f8fb1db6e8d6878463de2f09f3e67227f4868aedc208d18d09138c165ddcf5d")

_SENSITIVE_LOG_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature|^auth$|"
    r"(?:^|[_-])key$)", re.IGNORECASE)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)([\"']?(?:api[_-]?key|access[_-]?(?:key|token)|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature)"
    r"[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^&\s,;}]+)")
_SECRET_QUERY_PARAMETER = re.compile(
    r"(?i)([?&](?:api[_-]?key|access[_-]?(?:key|token)|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature)=)[^&#\s]*")
_URL_CREDENTIALS = re.compile(r"(?i)\b(https?://)[^\s/@]+(?::[^\s/@]*)?@")
_AUTH_SCHEME = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9+/=_-]{4,}")


def _redact_text(value: str) -> str:
    value = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)
    value = _SECRET_QUERY_PARAMETER.sub(r"\1[REDACTED]", value)
    value = _SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", value)
    return _AUTH_SCHEME.sub(r"\1 [REDACTED]", value)


def _redact_sensitive(value: object, *, key: str | None = None) -> object:
    """Redact credential-like values before structured output or JSON reports."""
    if key is not None and _SENSITIVE_LOG_KEY.search(key.replace(" ", "")):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(name): _redact_sensitive(item, key=str(name))
                for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, (str, Path)):
        return _redact_text(str(value))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value))


def _safe_error_message(error: BaseException) -> str:
    value = _redact_text(f"{type(error).__name__}: {error}")
    # Core State rejects credential-shaped assignments and unsafe URLs rather
    # than accepting a placeholder value under the original secret key.
    value = _SECRET_ASSIGNMENT.sub("[REDACTED]", value)
    value = _SECRET_QUERY_PARAMETER.sub("[REDACTED]", value)

    def redact_unsafe_url(match: re.Match) -> str:
        candidate = match.group(0).rstrip(".,);]")
        try:
            parsed = urlsplit(candidate)
        except ValueError:
            return "[REDACTED URL]"
        if (parsed.username is not None or parsed.password is not None
                or _SECRET_QUERY_PARAMETER.search(candidate)):
            return "[REDACTED URL]"
        return match.group(0)

    return re.sub(r"(?i)https?://[^\s<>\"']+", redact_unsafe_url, value)

LEGISLATION_ONTOLOGY_VERSION = "legislation.owl.ttl@phase-4-legislative-lifecycle-2026"
LEGISLATION_MAPPING_VERSION = "bill_mapping.csv@phase-4-legislative-lifecycle-2026"


class _RunFailure(ValueError):
    """A source/run failure whose scope is safe to expose in run history."""

    def __init__(self, message: str, *, scope: str = "source",
                 classification: str = "source_contract_failure"):
        super().__init__(message)
        self.scope = scope
        self.classification = classification


class _AdvertisedCountMismatch(ValueError):
    def __init__(self, endpoint: str, observed: int, advertised: int):
        super().__init__(
            f"{endpoint} unique count {observed} does not match advertised count")
        self.endpoint = endpoint
        self.observed = observed
        self.advertised = advertised


def _run_versions(endpoint: str, settings: Settings) -> dict[str, str | None]:
    ontology, mapping = {
        "houses": (settings.ontology_version, settings.mapping_version),
        "parties": (REFERENCE_ONTOLOGY_VERSION,
                    "party_mapping.csv@phase-2-reference-data-2026"),
        "constituencies": (REFERENCE_ONTOLOGY_VERSION,
                           "constituencies_mapping.csv@phase-2-reference-data-2026"),
        "members": (REFERENCE_ONTOLOGY_VERSION, MEMBER_MAPPING_VERSION),
        "legislation": (LEGISLATION_ONTOLOGY_VERSION, LEGISLATION_MAPPING_VERSION),
        # Debates are an explicit AKN batch, not a broad API mapping. Identify
        # the approved local vocabulary and mapping by exact content hashes.
        "debates": (DEBATES_ONTOLOGY_VERSION, DEBATES_MAPPING_VERSION),
    }.get(endpoint, (settings.ontology_version, settings.mapping_version))
    return {"etl_version": etl_package_version(),
            "ontology_version": ontology, "mapping_version": mapping}


def _json_log(event: str, **fields) -> None:
    """Emit one secret-conscious JSON Lines operational event to stderr."""
    record = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(),
              **_redact_sensitive(fields)}
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str), file=sys.stderr)


def _run_context(args: argparse.Namespace, *, run_id: str | None = None) -> dict | None:
    context = getattr(args, "_etl_run_context", None)
    if context is not None and (run_id is None or context.get("run_id") == run_id):
        return context
    return None


def _begin_run_context(args: argparse.Namespace, run_id: str, endpoint: str,
                       versions: dict[str, str | None]) -> dict:
    context = {"run_id": run_id, "versions": versions, "outcome": "success",
               "failure_scope": None, "failure_classification": None,
               "error": None, "safe_publication": False,
               "started_monotonic": time.perf_counter(),
               "summary": {"counters": {}, "timings": {}}}
    args._etl_run_context = context
    _json_log("run_started", run_id=run_id, endpoint=endpoint,
              versions=versions)
    return context


def _set_run_metrics(args: argparse.Namespace, *, counters: dict | None = None,
                     timings: dict | None = None) -> None:
    context = _run_context(args)
    if context is None:
        return
    context["summary"]["counters"].update(counters or {})
    context["summary"]["timings"].update(timings or {})


def _failure_summary(args: argparse.Namespace, run_id: str,
                     store: CoreStateStore | None = None) -> dict:
    """Persist a stable operational summary even when a stage aborts."""
    context = _run_context(args, run_id=run_id)
    summary = (context.get("summary") if context is not None else None) or {
        "counters": {}, "timings": {}}
    counters = summary.setdefault("counters", {})
    timings = summary.setdefault("timings", {})
    published_events = 0
    if store is not None:
        published_events = sum(
            event["event_type"] in {"graph_published", "entity_published"}
            for event in store.provenance_events(run_id=run_id))
        quarantined = store.connection.execute(
            "SELECT COUNT(*) FROM quarantine_record WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        counters["quarantined"] = max(counters.get("quarantined", 0), quarantined)
    for name, default in {
            "extracted": 0,
            "changed": 0,
            "unchanged": 0,
            "published_graphs": published_events,
            "quarantined": 0,
            "validation_failures": 0,
            "api_requests": 0,
            "api_failures": 0,
            "external_requests": 0,
            "external_failures": 0,
            "publication_succeeded": 0,
    }.items():
        counters.setdefault(name, default)
    counters["published_graphs"] = max(counters["published_graphs"], published_events)
    # A fatal run is not a successful whole-run publication, even if earlier
    # graph-level replacements in the batch completed and remain durable.
    counters["publication_succeeded"] = 0
    started = context.get("started_monotonic") if context is not None else None
    elapsed = (max(0.0, time.perf_counter() - started)
               if isinstance(started, (int, float)) else 0.0)
    timings.setdefault("etl_stage_seconds", elapsed)
    return summary


def _record_fatal_run(store: CoreStateStore, args: argparse.Namespace, *,
                      run_id: str, endpoint: str, error: Exception,
                      failure_scope: str = "system",
                      failure_classification: str = "system_failure") -> None:
    """Persist a terminal failure and keep any published catalog projection recoverable."""
    context = _run_context(args, run_id=run_id)
    message = _safe_error_message(error)
    _finish_retries(store, (context or {}).get("retry_attempts", []), run_id,
                    success=False, error=message, args=args)
    if failure_scope not in {"record", "source", "run", "system"}:
        failure_scope = "system"
    if not isinstance(failure_classification, str) or not failure_classification.strip():
        failure_classification = "system_failure"
    failure_classification = _redact_text(failure_classification)
    summary = _failure_summary(args, run_id, store)
    if context is not None:
        context.update(outcome="failed", error=message,
                       failure_scope=failure_scope,
                       failure_classification=failure_classification)

    catalog_pending = False
    if context is not None and context.get("safe_publication"):
        loader, client = context.get("loader"), context.get("client")
        if loader is not None and client is not None:
            try:
                store.record_run_summary(
                    run_id, counters=summary["counters"], timings=summary["timings"])
                # Do not replace a previous exact dirty candidate. Replay it
                # first; an unavailable older candidate remains detectable.
                _replay_pending_catalog(store, loader=loader, client=client)
                completed_at = datetime.now(timezone.utc).isoformat()
                failed_payload = _catalog_payload_for_final_outcome(
                    store, run_id, outcome="failed", completed_at=completed_at)
                store.finish_failed_run_with_catalog(
                    run_id, error=message, failure_scope=failure_scope,
                    failure_classification=failure_classification, summary=summary,
                    catalog_payload=failed_payload, completed_at=completed_at)
                if context is not None:
                    context["finished"] = True
                try:
                    _publish_staged_catalog(store, loader=loader, client=client)
                except Exception as catalog_error:
                    catalog_pending = bool(
                        (store.catalog_publication() or {}).get("publication_state") == "dirty")
                    safe_catalog_error = _safe_error_message(catalog_error)
                    _json_log("catalog_publication_failed", run_id=run_id,
                              endpoint=endpoint, outcome="failed",
                              error=safe_catalog_error, pending_catalog=catalog_pending)
                    if hasattr(error, "add_note"):
                        error.add_note(
                            "failed-run catalog publication remains pending: "
                            + safe_catalog_error)
            except Exception as catalog_error:
                # Preserve the fatal local outcome even if constructing or
                # staging its projection encounters an integrity failure. The
                # integrity error is also surfaced in logs/traceback, never
                # converted into a successful catalog claim.
                run = store.connection.execute(
                    "SELECT status FROM etl_run WHERE run_id=?", (run_id,)
                ).fetchone()
                if run is not None and run["status"] == "running":
                    store.finish_run(
                        run_id, outcome="failed", error=message,
                        failure_scope=failure_scope,
                        failure_classification=failure_classification,
                        summary=summary)
                if context is not None:
                    context["finished"] = True
                catalog_pending = bool(
                    (store.catalog_publication() or {}).get("publication_state") == "dirty")
                safe_catalog_error = _safe_error_message(catalog_error)
                _json_log("failed_run_catalog_finalization_failed", run_id=run_id,
                          endpoint=endpoint, error=safe_catalog_error,
                          pending_catalog=catalog_pending)
                if hasattr(error, "add_note"):
                    error.add_note(
                        "failed-run catalog finalization failed: " + safe_catalog_error)
        else:
            store.finish_run(
                run_id, outcome="failed", error=message,
                failure_scope=failure_scope,
                failure_classification=failure_classification, summary=summary)
            if context is not None:
                context["finished"] = True
    else:
        store.finish_run(
            run_id, outcome="failed", error=message,
            failure_scope=failure_scope,
            failure_classification=failure_classification, summary=summary)
        if context is not None:
            context["finished"] = True

    catalog_pending = catalog_pending or bool(
        (store.catalog_publication() or {}).get("publication_state") == "dirty")
    _json_log("run_finished", run_id=run_id, endpoint=endpoint,
              outcome="failed", failure_scope=failure_scope,
              failure_classification=failure_classification, error=message,
              summary=summary, pending_catalog=catalog_pending)


def _degrade_run(args: argparse.Namespace, *, error: str,
                 classification: str = "record_transform_failure") -> None:
    context = _run_context(args)
    if context is None:
        return
    context["outcome"] = "degraded"
    context["failure_scope"] = "record"
    context["failure_classification"] = classification
    context["error"] = error


def _record_raw_page(args: argparse.Namespace, store: CoreStateStore | None, *,
                     endpoint: str, run_id: str | None,
                     raw_path: Path, raw_root: Path, body: bytes, source_url: str | None,
                     parameters: dict, observed_at: datetime,
                     versions: dict[str, str | None]) -> dict[str, str]:
    """Record immutable page-level source evidence and return contract evidence."""
    digest = hashlib.sha256(body).hexdigest()
    pointer = {"path": raw_path.resolve().as_uri(), "sha256": digest,
               "json_pointer": ""}
    context = _run_context(args, run_id=run_id)
    if store is not None and run_id is not None and context is not None:
        store.record_source_observation(
            endpoint, digest, observed_at.isoformat(), run_id=run_id,
            evidence_pointer=pointer["path"], source_url=source_url,
            request_parameters=parameters, versions=versions,
        )
    if source_url is not None:
        if context is not None:
            counters = context["summary"]["counters"]
            counters["api_requests"] = counters.get("api_requests", 0) + 1
    _json_log("source_page_observed", endpoint=endpoint, run_id=run_id,
              source_sha256=digest, evidence_pointer=pointer["path"],
              request_parameters=parameters)
    return _raw_contract_pointer(raw_path, raw_root, body, "")


def _safe_harvest(args: argparse.Namespace, client, *, limit: int,
                  query_params: dict | None = None):
    """Yield raw pages before decoding so even malformed responses are retained.

    ``ApiClient.harvest`` decodes each page to decide when pagination ends. The
    operational path uses ``page`` directly when available so the caller can
    persist immutable bytes before parsing; harvest-only adapters remain
    supported for existing endpoint tests and injected clients.
    """
    try:
        page_method = getattr(client, "page", None)
        if callable(page_method):
            skip = 0
            while True:
                if query_params:
                    page = page_method(skip=skip, limit=limit,
                                       query_params=query_params)
                else:
                    page = page_method(skip=skip, limit=limit)
                yield page
                # This executes after the caller has persisted and consumed the
                # raw page. A malformed page therefore fails closed without
                # losing the response bytes that explain the failure.
                decoded = json.loads(page.body)
                records = decoded.get("results", decoded) if isinstance(decoded, dict) else decoded
                if not isinstance(records, list):
                    raise ValueError("API page must be an array or an object with results")
                if len(records) < limit:
                    return
                skip += limit
        else:
            pages = (client.harvest(limit=limit, query_params=query_params)
                     if query_params else client.harvest(limit=limit))
            yield from pages
    except Exception as error:
        _set_run_metrics(args, counters={
            "api_failures": (_run_context(args) or {}).get(
                "summary", {}).get("counters", {}).get("api_failures", 0) + 1})
        raise _RunFailure(
            f"API extraction failed: {type(error).__name__}: {error}",
            scope="source", classification="api_extraction_failure") from error


def _decode_api_page(body: bytes, endpoint: str, args: argparse.Namespace | None = None):
    try:
        return json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as error:
        if args is not None:
            context = _run_context(args) or {}
            current = context.get("summary", {}).get("counters", {}).get("api_failures", 0)
            _set_run_metrics(args, counters={"api_failures": current + 1})
        raise _RunFailure(f"{endpoint} API page is not valid JSON: {error}",
                          scope="source",
                          classification="api_response_failure") from error


def _raw_contract_pointer(raw_path: Path, raw_root: Path, body: bytes,
                          json_pointer: str) -> dict[str, str]:
    return {"path": raw_path.resolve().relative_to(raw_root.resolve()).as_posix(),
            "sha256": hashlib.sha256(body).hexdigest(),
            "json_pointer": json_pointer}


def _raw_resource_pointer(raw_path: Path, json_pointer: str) -> str:
    return raw_path.resolve().as_uri() + ("#" + json_pointer if json_pointer else "")


def _persist_immutable_json(path: Path, value: object) -> None:
    """Create a canonical JSON report without ever overwriting prior evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_value = _redact_sensitive(value)
    payload = (json.dumps(safe_value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise FileExistsError(f"immutable JSON evidence collision: {path}")
        return
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _source_contract(args: argparse.Namespace, endpoint: str, records: list[dict], *,
                     run_id: str | None, evidence: list[dict[str, str]],
                     report_path: Path | None) -> dict:
    """Classify consumed-field drift and retain an immutable run report."""
    if run_id is None:
        return {"findings": [], "failed_record_indices": [], "source_failed": False}
    report = classify_source_contract(endpoint, records, run_id=run_id,
                                      source_evidence=evidence)
    value = report.as_dict()
    if report_path is not None:
        _persist_immutable_json(report_path, value)
    _set_run_metrics(args, counters={
        "schema_drift_warnings": len(report.warnings),
        "source_contract_record_failures": len(report.record_failures),
        "source_contract_failures": len(report.source_failures),
    })
    for finding in report.findings:
        logged = finding.as_dict()
        logged.pop("observed", None)
        _json_log("source_drift", run_id=run_id, endpoint=endpoint,
                  finding=logged)
    context = _run_context(args, run_id=run_id)
    if context is not None:
        context["summary"]["counters"]["source_drift_report_count"] = len(report.findings)
        context["source_drift_report"] = str(report_path) if report_path else None
    return value


def _api_envelope_contract(args: argparse.Namespace, endpoint: str, envelope: object, *,
                           run_id: str, raw_path: Path, raw_root: Path, body: bytes,
                           count_field: str | None = None,
                           expected_count: int | None = None,
                           observed_record_count: int | None = None,
                           allow_array: bool = False):
    """Classify API envelope drift against the exact preserved page bytes."""
    evidence = _raw_contract_pointer(raw_path, raw_root, body, "")
    report = classify_source_envelope(
        endpoint, envelope, run_id=run_id, source_evidence=evidence,
        count_field=count_field, expected_count=expected_count,
        observed_record_count=observed_record_count, allow_array=allow_array,
    )
    if report.findings:
        report_path = raw_path.with_name(
            raw_path.name.removesuffix(".json") + ".source-envelope-drift.json")
        _persist_immutable_json(report_path, report.as_dict())
        context = _run_context(args, run_id=run_id)
        if context is not None:
            counters = context["summary"]["counters"]
            failures = len(report.source_failures)
            counters["source_contract_failures"] = (
                counters.get("source_contract_failures", 0) + failures)
            counters["api_envelope_contract_failures"] = (
                counters.get("api_envelope_contract_failures", 0) + failures)
            context["source_envelope_report"] = str(report_path)
        for finding in report.findings:
            logged = finding.as_dict()
            logged.pop("observed", None)
            _json_log("source_envelope_drift", endpoint=endpoint,
                      run_id=run_id, finding=logged)
    return report


def _raise_on_envelope_failure(report, endpoint: str) -> None:
    if report.source_failed:
        finding = report.source_failures[0]
        if finding.change == "advertised_count_changed":
            detail = "advertised count changed during scan"
        elif finding.change in {"advertised_count_mismatch", "result_count_mismatch"}:
            detail = "advertised count does not match observed records"
        elif finding.json_pointer == "/results" or finding.change == "invalid_source_container":
            detail = "API page must contain an object envelope with a results array"
        elif finding.json_pointer.startswith("/head"):
            detail = "API page must contain a nonnegative integer advertised count"
        else:
            detail = "API envelope violates consumed source contract"
        raise _RunFailure(
            f"{endpoint} {detail}",
            scope="source", classification="api_envelope_contract_failure")


def _capture_api_pages(args: argparse.Namespace, endpoint: str, api_url: str,
                       settings: Settings, *, count_field: str):
    """Preserve API pages and classify their consumed count envelope fields."""
    raw_root = Path(getattr(args, "raw_dir", None) or settings.raw_dir).expanduser().resolve()
    extraction_id = str(uuid.uuid4())
    versions = _run_versions(endpoint, settings)
    records: list[dict] = []
    advertised: int | None = None
    last_page: tuple[Path, bytes, object] | None = None
    for page_index, page in enumerate(_safe_harvest(
            args, ApiClient(api_url, retries=settings.retries, timeout=settings.timeout),
            limit=settings.limit)):
        observed_at = datetime.now(timezone.utc)
        # Harvest-only test adapters predate ApiPage request metadata. The
        # actual client always supplies exact params; retain the known requested
        # pagination boundary for adapters rather than failing raw persistence.
        page_params = page.params or {"skip": page_index * settings.limit,
                                      "limit": settings.limit}
        raw_path, _ = persist_raw(
            root=raw_root, endpoint=api_url, params=page_params, body=page.body,
            status=page.status, retrieved_at=observed_at,
            ontology_version=versions["ontology_version"],
            mapping_version=versions["mapping_version"],
            endpoint_name=endpoint, extraction_id=extraction_id)
        decoded = _decode_api_page(page.body, endpoint, args)
        report = _api_envelope_contract(
            args, endpoint, decoded, run_id=extraction_id,
            raw_path=raw_path, raw_root=raw_root, body=page.body,
            count_field=count_field, expected_count=advertised)
        _raise_on_envelope_failure(report, endpoint)
        # The classifier above validates the nested count as a nonnegative int.
        count = decoded["head"]["counts"][count_field]
        if advertised is None:
            advertised = count
        records.extend(decoded["results"])
        last_page = (raw_path, page.body, decoded)
    return records, advertised, last_page, raw_root, extraction_id


def _contract_failure_detail(report: dict) -> str:
    """Return a concise, non-value-bearing detail for consumed-field failures."""
    failures = [item for item in report.get("findings", [])
                if item.get("severity") in {"record", "source"}]
    if not failures:
        return "incompatible source contract"
    first = failures[0]
    pointer = str(first.get("json_pointer", ""))
    segment = pointer.rsplit("/", 1)[-1]
    known = {"representType": "unsupported representType",
             "houseCode": "unsupported houseCode",
             "representCode": "invalid representCode"}
    detail = known.get(segment, f"{first.get('change', 'contract failure')} at {pointer}")
    if len(failures) > 1:
        detail += f" (+{len(failures) - 1} additional contract finding(s))"
    return detail


def _record_quarantine(store: CoreStateStore | None, *, endpoint: str,
                       run_id: str | None, source_hash: str,
                       observed_at: str, evidence_pointer: str,
                       stage: str, error: str, resource_iri: str | None,
                       classification: str, versions: dict[str, str | None]) -> str | None:
    if store is None or run_id is None:
        return None
    quarantine_id = store.record_quarantine(
        endpoint, run_id=run_id, source_hash=source_hash,
        observed_at=observed_at, evidence_pointer=evidence_pointer,
        stage=stage, error=error, resource_iri=resource_iri,
        failure_classification=classification,
        etl_version=versions.get("etl_version"),
        ontology_version=versions.get("ontology_version"),
        mapping_version=versions.get("mapping_version"),
    )
    _json_log("record_quarantined", run_id=run_id, endpoint=endpoint,
              quarantine_id=quarantine_id, resource_iri=resource_iri,
              stage=stage, classification=classification)
    return quarantine_id


def _retry_candidates(store: CoreStateStore | None, endpoint: str) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    if store is not None:
        for row in store.quarantines_for_retry(endpoint):
            identity = row.get("resource_iri")
            if isinstance(identity, str):
                result.setdefault(identity, []).append(row)
    return result


def _retry_candidates_by_hash(store: CoreStateStore | None,
                             endpoint: str) -> dict[str, list[dict]]:
    """Index unidentified quarantines by their immutable record source hash."""
    result: dict[str, list[dict]] = {}
    if store is not None:
        for row in store.quarantines_for_retry(endpoint):
            if row.get("resource_iri") is None:
                result.setdefault(row["source_hash"], []).append(row)
    return result


def _retry_rows_for_record(by_identity: dict[str, list[dict]],
                           by_hash: dict[str, list[dict]], identity: str | None,
                           source_hash: str, *, include_unidentified: bool) -> list[dict]:
    """Select retries only when the current source record is reobserved.

    Hash-only matching is limited to null-identity quarantines and callers must
    opt in only for an applicable complete live scan. Consuming the hash entry
    prevents duplicate copies of one source record from starting the same
    quarantine twice in a run.
    """
    rows = list(by_identity.get(identity, [])) if isinstance(identity, str) else []
    if include_unidentified:
        rows.extend(by_hash.pop(source_hash, []))
    unique: dict[str, dict] = {}
    for row in rows:
        unique.setdefault(row["quarantine_id"], row)
    return list(unique.values())


def _start_retries(store: CoreStateStore | None, rows: list[dict], run_id: str | None) -> list[str]:
    started = []
    if store is None or run_id is None:
        return started
    for row in rows:
        store.start_quarantine_retry(row["quarantine_id"], run_id=run_id)
        started.append(row["quarantine_id"])
    return started


def _finish_retries(store: CoreStateStore | None, ids: list[str], run_id: str | None,
                    *, success: bool, error: str | None = None,
                    args: argparse.Namespace | None = None) -> None:
    if store is None or run_id is None:
        return
    for quarantine_id in ids:
        store.finish_quarantine_retry(quarantine_id, run_id=run_id,
                                      success=success, error=error)
    context = _run_context(args, run_id=run_id) if args is not None else None
    if context is not None:
        done = set(ids)
        context["retry_attempts"] = [item for item in context.get("retry_attempts", [])
                                     if item not in done]


def _catalog_payload_for_final_outcome(store: CoreStateStore, run_id: str, *,
                                       outcome: str, completed_at: str) -> str:
    """Build the exact validated catalog candidate for a prospective run outcome."""
    graph = build_provenance_catalog(store, require_source_run_ids=(run_id,))
    activity = URIRef(run_resource_iri(run_id))
    graph.remove((activity, ETL.runStatus, None))
    graph.remove((activity, ETL.runOutcome, None))
    graph.remove((activity, PROV.endedAtTime, None))
    graph.add((activity, ETL.runStatus,
               Literal({"success": "succeeded", "degraded": "degraded",
                        "failed": "failed"}[outcome])))
    graph.add((activity, ETL.runOutcome, Literal(outcome)))
    graph.add((activity, PROV.endedAtTime,
               Literal(completed_at, datatype=XSD.dateTime)))
    validate_provenance_catalog(graph)
    return ntriples(graph)


def _replay_pending_catalog(store: CoreStateStore, *, loader, client) -> bool:
    """Replay an older exact catalog payload before staging a new projection."""
    pending = store.catalog_publication()
    if pending and pending.get("publication_state") == "dirty":
        payload = pending.get("pending_payload")
        digest = pending.get("pending_payload_hash")
        if (not isinstance(payload, str)
                or hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest):
            raise ValueError("dirty provenance catalog has no hash-verified replay payload")
        loader.replace(PROVENANCE_GRAPH_IRI, payload,
                       content_type="application/n-triples")
        verify_core_graph(client, PROVENANCE_GRAPH_IRI, payload)
        catalog_publication_boundary(store).mark_clean(PROVENANCE_GRAPH_IRI, digest)
        return True
    return False


def _publish_staged_catalog(store: CoreStateStore, *, loader, client) -> str:
    """Publish only the exact payload atomically staged with the finished run."""
    pending = store.catalog_publication()
    if not pending or pending.get("publication_state") != "dirty":
        raise ValueError("finished run has no dirty provenance catalog payload")
    payload = pending.get("pending_payload")
    digest = pending.get("pending_payload_hash")
    if (not isinstance(payload, str)
            or hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest):
        raise ValueError("dirty provenance catalog has no hash-verified publication payload")
    loader.replace(PROVENANCE_GRAPH_IRI, payload,
                   content_type="application/n-triples")
    verify_core_graph(client, PROVENANCE_GRAPH_IRI, payload)
    catalog_publication_boundary(store).mark_clean(PROVENANCE_GRAPH_IRI, digest)
    return digest


def _finalize_run(store: CoreStateStore, args: argparse.Namespace, *,
                  run_id: str, endpoint: str, versions: dict[str, str | None],
                  loader=None, client=None) -> None:
    context = _run_context(args, run_id=run_id) or {
        "outcome": "success", "summary": {"counters": {}, "timings": {}},
        "safe_publication": False,
    }
    unresolved = store.quarantine_records(endpoint=endpoint, status="quarantined")
    if unresolved and context.get("outcome") == "success":
        context["outcome"] = "degraded"
        context["failure_scope"] = "record"
        context["failure_classification"] = "unresolved_record_quarantine"
        context["error"] = f"{len(unresolved)} unresolved record quarantine(s) remain"
    summary = context["summary"]
    summary["counters"].setdefault("quarantined", len(unresolved))
    page_observations = store.connection.execute(
        "SELECT COUNT(*) FROM source_observation WHERE run_id=? AND endpoint=? "
        "AND evidence_pointer IS NOT NULL AND instr(evidence_pointer,'#')=0 "
        "AND source_url IS NOT NULL",
        (run_id, endpoint),
    ).fetchone()[0]
    summary["counters"].setdefault("api_requests", page_observations)
    summary["counters"].setdefault("api_failures", 0)
    started_monotonic = context.get("started_monotonic")
    if isinstance(started_monotonic, (int, float)):
        summary["timings"].setdefault(
            "etl_stage_seconds", max(0.0, time.perf_counter() - started_monotonic))
    store.record_run_summary(run_id, counters=summary["counters"],
                             timings=summary["timings"])
    outcome = context.get("outcome", "success")
    completed_at = datetime.now(timezone.utc).isoformat()
    finish_facts = {
        "error": context.get("error") if outcome != "success" else None,
        "failure_scope": context.get("failure_scope") if outcome != "success" else None,
        "failure_classification": (context.get("failure_classification")
                                   if outcome != "success" else None),
        "incremental_cursor": (context.get("incremental_cursor")
                               if outcome == "success" else None),
        "complete_scan": bool(context.get("complete_scan", False)
                              and outcome == "success"),
        "summary": summary,
        "completed_at": completed_at,
    }

    def log_finished(final_outcome: str, *, error: str | None = None,
                     failure_scope: str | None = None,
                     failure_classification: str | None = None) -> None:
        context.update(finished=True, outcome=final_outcome,
                       error=error, failure_scope=failure_scope,
                       failure_classification=failure_classification)
        _json_log("run_finished", run_id=run_id, endpoint=endpoint,
                  outcome=final_outcome, failure_scope=failure_scope,
                  failure_classification=failure_classification,
                  error=error, summary=summary)

    def finish_without_catalog_failure(error: Exception) -> None:
        message = _safe_error_message(error)
        store.finish_run(
            run_id, outcome="failed", error=message,
            failure_scope="system", failure_classification="catalog_publication_failure",
            summary=summary, completed_at=completed_at,
        )
        log_finished("failed", error=message, failure_scope="system",
                     failure_classification="catalog_publication_failure")
        _json_log("catalog_publication_failed", run_id=run_id,
                  endpoint=endpoint, error=message,
                  pending_catalog=bool(
                      (store.catalog_publication() or {}).get("publication_state") == "dirty"))

    def finish_without_catalog() -> None:
        if outcome == "success":
            store.finish_run(run_id, success=True, **finish_facts)
        else:
            store.finish_run(run_id, outcome=outcome, **finish_facts)
        log_finished(outcome, error=finish_facts["error"],
                     failure_scope=finish_facts["failure_scope"],
                     failure_classification=finish_facts["failure_classification"])

    if not context.get("safe_publication"):
        finish_without_catalog()
        return

    if loader is None or client is None:
        error = RuntimeError("safe graph publication requires a configured catalog publisher/verifier")
        finish_without_catalog_failure(error)
        raise error

    try:
        # Recover any older exact candidate first. If it remains unavailable,
        # fail this run but leave that pending evidence untouched.
        _replay_pending_catalog(store, loader=loader, client=client)
        catalog_payload = _catalog_payload_for_final_outcome(
            store, run_id, outcome=outcome, completed_at=completed_at)
        failure_payload = _catalog_payload_for_final_outcome(
            store, run_id, outcome="failed", completed_at=completed_at)
        store.stage_run_catalog_finalization(
            run_id, outcome=outcome,
            error=finish_facts["error"], completed_at=completed_at,
            incremental_cursor=finish_facts["incremental_cursor"],
            complete_scan=finish_facts["complete_scan"],
            failure_scope=finish_facts["failure_scope"],
            failure_classification=finish_facts["failure_classification"],
            summary=summary, catalog_payload=catalog_payload,
            failure_payload=failure_payload,
        )
    except Exception as error:
        finish_without_catalog_failure(error)
        raise

    try:
        _publish_staged_catalog(store, loader=loader, client=client)
    except Exception as error:
        message = _safe_error_message(error)
        try:
            store.fail_pending_catalog_finalization(run_id, error=message)
        except Exception as state_error:
            # Do not let a wrapper mark the still-pending run successful or
            # overwrite its durable candidate if failure correction itself
            # cannot be committed. The dirty state remains the recovery signal.
            context["catalog_state_unresolved"] = True
            safe_state_error = _safe_error_message(state_error)
            _json_log("catalog_failure_state_update_failed", run_id=run_id,
                      endpoint=endpoint, publication_error=message,
                      state_error=safe_state_error)
            raise RuntimeError(
                f"catalog publication failed ({message}); failed-run state update also failed: "
                f"{safe_state_error}") from state_error
        log_finished("failed", error=f"catalog publication failed: {message}",
                     failure_scope="system",
                     failure_classification="catalog_publication_failure")
        _json_log("catalog_publication_failed", run_id=run_id,
                  endpoint=endpoint, outcome="failed", error=message,
                  pending_catalog=True)
        raise

    log_finished(outcome, error=finish_facts["error"],
                 failure_scope=finish_facts["failure_scope"],
                 failure_classification=finish_facts["failure_classification"])


def _reconciliation_state_path(args: argparse.Namespace, settings: Settings) -> Path:
    return Path(getattr(args, "reconciliation_state_file", None)
                or settings.reconciliation_state_db_file).expanduser()


def _mark_reconciliation_due(store: ReconciliationStore, entity_kind: str,
                             wrapper: dict, *, force: bool = False) -> bool:
    identity = reconciliation_identity(entity_kind, wrapper)
    if identity is None:
        return False
    local_iri, entity_key, fingerprint = identity
    return store.mark_due(entity_kind, local_iri, entity_key, fingerprint, force=force)


def _handoff_warning(entity_kind: str, error: Exception) -> None:
    # Reconciliation still performs complete-source selection against its own
    # durable fingerprint/next_recheck_at state. A failed eager handoff cannot
    # undo a verified authoritative graph or make it dirty again.
    print(f"external reconciliation handoff deferred for {entity_kind}: "
          f"{type(error).__name__}: {error}; retry via reconcile {entity_kind}", file=sys.stderr)


def _try_mark_due(store: ReconciliationStore | None, entity_kind: str,
                  wrapper: dict, *, force: bool = False) -> None:
    if store is None:
        return
    try:
        _mark_reconciliation_due(store, entity_kind, wrapper, force=force)
    except Exception as error:
        _handoff_warning(entity_kind, error)

def _records_from_fixture(path: Path) -> tuple[list[dict], bytes]:
    body = path.read_bytes()
    value = json.loads(body)
    if not isinstance(value, list): raise ValueError("fixture must be a JSON array")
    return value, body

def _run_houses_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                     run_id: str | None = None) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    raw_root = settings.raw_dir.expanduser().resolve()
    versions = (_run_context(args, run_id=run_id) or {}).get(
        "versions", _run_versions("houses", settings))
    extraction_id = run_id or str(uuid.uuid4())
    source_run_id = run_id or extraction_id
    evidence: list[dict[str, str]] = []
    record_pointers: list[str] = []
    report_path: Path | None = None
    if args.fixture:
        records, body = _records_from_fixture(Path(args.fixture))
        observed_at = datetime.now(timezone.utc)
        raw_path, _ = persist_raw(root=raw_root, endpoint=str(Path(args.fixture).resolve()),
                    params={"skip": 0, "limit": len(records)}, body=body,
                    status=200, retrieved_at=observed_at,
                    ontology_version=versions["ontology_version"] or settings.ontology_version,
                    mapping_version=versions["mapping_version"] or settings.mapping_version,
                    extraction_id=extraction_id)
        _record_raw_page(args, store, endpoint="houses", run_id=run_id, raw_path=raw_path,
                         raw_root=raw_root, body=body, source_url=None,
                         parameters={"skip": 0, "limit": len(records)},
                         observed_at=observed_at, versions=versions)
        evidence.extend(_raw_contract_pointer(raw_path, raw_root, body, f"/{index}")
                        for index, _ in enumerate(records))
        record_pointers.extend(_raw_resource_pointer(raw_path, f"/{index}")
                               for index, _ in enumerate(records))
        report_path = raw_path.parent / "source-drift.json"
    else:
        records = []
        for page in _safe_harvest(
                args, HousesApiClient(settings.api_url, retries=settings.retries,
                                      timeout=settings.timeout), limit=settings.limit):
            observed_at = datetime.now(timezone.utc)
            raw_path, _ = persist_raw(root=raw_root, endpoint=settings.api_url,
                params=page.params, body=page.body, status=page.status,
                retrieved_at=observed_at, ontology_version=versions["ontology_version"],
                mapping_version=versions["mapping_version"], extraction_id=extraction_id)
            _record_raw_page(args, store, endpoint="houses", run_id=run_id,
                             raw_path=raw_path, raw_root=raw_root, body=page.body,
                             source_url=settings.api_url, parameters=page.params,
                             observed_at=observed_at, versions=versions)
            decoded = _decode_api_page(page.body, "Houses", args)
            envelope_report = _api_envelope_contract(
                args, "houses", decoded, run_id=source_run_id,
                raw_path=raw_path, raw_root=raw_root, body=page.body,
                allow_array=True)
            _raise_on_envelope_failure(envelope_report, "Houses")
            page_records = decoded.get("results", decoded) if isinstance(decoded, dict) else decoded
            if not isinstance(page_records, list):
                raise _RunFailure("every Houses API page must contain a results array")
            records.extend(page_records)
            evidence.extend(_raw_contract_pointer(
                raw_path, raw_root, page.body,
                f"/results/{index}" if isinstance(decoded, dict) else f"/{index}")
                for index in range(len(page_records)))
            record_pointers.extend(_raw_resource_pointer(
                raw_path, f"/results/{index}" if isinstance(decoded, dict) else f"/{index}")
                for index in range(len(page_records)))
            report_path = raw_path.parent / "source-drift.json"
    report = _source_contract(args, "houses", records, run_id=source_run_id,
                              evidence=evidence, report_path=report_path)
    if report["source_failed"] or report["failed_record_indices"]:
        unsupported_house_code = any(
            item.get("change") == "incompatible_value"
            and item.get("json_pointer", "").endswith("/house/houseCode")
            for item in report.get("findings", []))
        detail = "unsupported houseCode; " if unsupported_house_code else ""
        raise _RunFailure(
            f"{detail}Houses source contract contains incompatible records")
    try:
        graph, exclusions = transform_houses_with_report(records)
        validate_houses(records, graph)  # before any loader construction/invocation
    except Exception as error:
        raise _RunFailure(f"Houses source cannot be transformed safely: {error}") from error
    if args.output_ttl: Path(args.output_ttl).write_text(turtle(graph), encoding="utf-8")
    payload = nquads(graph, HOUSES_GRAPH)
    if args.output_nq: Path(args.output_nq).write_text(payload, encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint:
        if not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load whole-graph verification")
        payload = ntriples(graph)
        if store is None: raise RuntimeError("online Houses publication requires durable core ETL state")
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        context = _run_context(args, run_id=run_id)
        if context is not None:
            context.update(loader=loader, client=client)
            context["safe_publication"] = True
        prior_publication = store.endpoint_publication("houses")
        replayed_pending_hash = None
        replayed_had_entity_lineage = False
        if prior_publication and prior_publication.get("publication_state") == "dirty":
            pending = prior_publication.get("pending_payload")
            pending_hash = prior_publication.get("pending_payload_hash")
            if (not isinstance(pending, str)
                    or hashlib.sha256(pending.encode("utf-8")).hexdigest() != pending_hash):
                raise ValueError(
                    "dirty Houses graph has no hash-verified pending payload; refusing to replace it")
            loader.replace(HOUSES_GRAPH, pending, content_type="application/n-triples")
            verify_core_graph(client, HOUSES_GRAPH, pending)
            replayed_pending_hash = pending_hash
            replayed_had_entity_lineage = isinstance(
                prior_publication.get("pending_entity_lineage"), dict)
            store.complete_endpoint_publication(
                "houses", HOUSES_GRAPH, pending_hash,
                publishing_run_id=run_id)
        entity_lineage = _build_houses_entity_lineage(
            records, evidence, graph=graph, raw_root=raw_root)
        current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if not (replayed_pending_hash == current_hash and replayed_had_entity_lineage):
            digest = store.mark_endpoint_dirty(
                "houses", HOUSES_GRAPH, payload, run_id=run_id,
                entity_lineage=entity_lineage)
            loader.replace(HOUSES_GRAPH, payload, content_type="application/n-triples")
            verify_core_graph(client, HOUSES_GRAPH, payload)
            store.complete_endpoint_publication(
                "houses", HOUSES_GRAPH, digest, publishing_run_id=run_id)
        if context is not None:
            context["safe_publication"] = True
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(records), "excluded": exclusions, "published": bool(endpoint)}, sort_keys=True))
    _set_run_metrics(args, counters={"extracted": len(records),
                                     "changed": len(records), "unchanged": 0,
                                     "published_graphs": int(bool(endpoint)),
                                     "quarantined": 0, "validation_failures": 0,
                                     "api_failures": 0,
                                     "publication_succeeded": int(bool(endpoint))})
    return 0


def _run_shared(args: argparse.Namespace, endpoint_name: str, operation) -> int:
    if args.offline:
        return operation(args)
    settings = Settings.from_environment()
    database = Path(getattr(args, "state_db", None) or settings.core_state_db_file).expanduser()
    with state_lock(database):
        with CoreStateStore(database, legacy_members=settings.members_legacy_state_file,
                            legacy_bills=settings.bills_legacy_state_file) as store:
            registry_run = endpoint_name in {"administrative-units", "offices"}
            derived_run = endpoint_name == "committees"
            fixture_run = bool(args.fixture)
            versions = _run_versions(endpoint_name, settings)
            member_source_run = (
                store.last_successful_complete_run("members")
                if derived_run and not fixture_run else None)
            run_id = store.start_run(endpoint_name, "full_refresh", is_complete=True,
                                     parameters={"source": "fixture" if fixture_run else
                                                 "registry" if registry_run else
                                                 "members" if derived_run else "api",
                                                  "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                                  "source_run_id": (member_source_run["run_id"]
                                                                    if member_source_run else None),
                                                  "registry_file": str(Path(args.registry_file or OFFICE_REGISTRY_FILE).resolve()) if registry_run else None,
                                                  "api_url": None if registry_run or derived_run or args.fixture else getattr(settings, {
                                                    "houses": "api_url", "parties": "parties_api_url",
                                                        "constituencies": "constituencies_api_url"}[endpoint_name]),
                                                   "limit": settings.limit},
                                      versions=versions)
            args.endpoint = endpoint_name
            _begin_run_context(args, run_id, endpoint_name, versions)
            try:
                result = operation(args, store, run_id)
                context = _run_context(args, run_id=run_id)
                _finalize_run(store, args, run_id=run_id, endpoint=endpoint_name,
                              versions=versions,
                              loader=context.get("loader") if context else None,
                              client=context.get("client") if context else None)
            except Exception as error:
                context = _run_context(args, run_id=run_id)
                if not (context and (context.get("finished")
                                     or context.get("catalog_state_unresolved"))):
                    scope = getattr(error, "scope", "system")
                    classification = getattr(error, "classification", "system_failure")
                    _record_fatal_run(
                        store, args, run_id=run_id, endpoint=endpoint_name,
                        error=error, failure_scope=scope,
                        failure_classification=classification)
                raise
            return result


def run_houses(args: argparse.Namespace) -> int:
    return _run_shared(args, "houses", _run_houses_impl)


REFERENCE_ENDPOINTS = {
    "parties": (PARTIES_GRAPH, "parties_api_url", transform_parties, validate_parties, "party_mapping.csv@phase-2-reference-data-2026"),
    "constituencies": (CONSTITUENCIES_GRAPH, "constituencies_api_url", transform_constituencies, validate_constituencies, "constituencies_mapping.csv@phase-2-reference-data-2026"),
}
REFERENCE_GRAPHS = {
    "parties": PARTIES_GRAPH,
    "constituencies": CONSTITUENCIES_GRAPH,
    "committees": COMMITTEES_GRAPH,
}


def _assert_reference_source_not_older(store: CoreStateStore,
                                       endpoints: tuple[str, ...],
                                       source_run_id: str | None) -> None:
    """Prevent older Members captures from rolling back owner descriptions."""
    if source_run_id is None:
        return
    candidate_started = datetime.fromisoformat(
        store.member_source_run_started_at(source_run_id))
    for endpoint_name in endpoints:
        metadata = store.endpoint_publication(endpoint_name) or {}
        prior_run_id = (
            metadata.get("pending_member_source_run_id")
            if metadata.get("publication_state") == "dirty"
            else metadata.get("member_source_run_id"))
        if not prior_run_id or prior_run_id == source_run_id:
            continue
        prior_started = datetime.fromisoformat(
            store.member_source_run_started_at(prior_run_id))
        if candidate_started <= prior_started:
            raise ValueError(
                f"refusing to replace {endpoint_name} owner graph from older Members run "
                f"{source_run_id}; graph already contains evidence from {prior_run_id}")


def _write_reference_report(args: argparse.Namespace, report: dict) -> None:
    destination = getattr(args, "coverage_report", None)
    if destination:
        path = Path(destination).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                   indent=2) + "\n", encoding="utf-8")


def _reference_inputs(*, endpoint_name: str, endpoint_records: list[dict] | None,
                      member_records: list[dict] | None, store: CoreStateStore | None,
                      raw_root: Path, endpoint_is_authoritative: bool,
                      member_is_authoritative: bool,
                      member_record_pointers: dict[str, list[dict]] | None = None,
                      endpoint_record_pointers: dict[str, dict[str, list[dict]]] | None = None
                      ) -> tuple[dict, dict]:
    """Assemble current and latest complete source observations deterministically."""
    member_evidence = None
    if member_records is None and store is not None:
        loaded = load_latest_complete_capture(raw_root, store, "members")
        if loaded is not None:
            member_records, member_evidence = loaded
            member_is_authoritative = True
            capture_directory = member_evidence.get("capture_directory")
            member_record_pointers = (capture_record_pointers(
                Path(capture_directory), raw_root, "members")
                if isinstance(capture_directory, str) else {})
    member_records = member_records or []
    member_record_pointers = member_record_pointers or {}

    sources: dict[str, tuple[list[dict], bool]] = {}
    endpoint_record_pointers = endpoint_record_pointers or {}
    for endpoint in ("parties", "constituencies"):
        if endpoint == endpoint_name and endpoint_records is not None:
            sources[endpoint] = (endpoint_records, endpoint_is_authoritative)
            continue
        loaded = (load_latest_complete_capture(raw_root, store, endpoint)
                  if store is not None else None)
        if loaded is None:
            sources[endpoint] = ([], False)
        else:
            sources[endpoint] = (loaded[0], True)
            capture_directory = loaded[1].get("capture_directory")
            endpoint_record_pointers[endpoint] = (capture_record_pointers(
                Path(capture_directory), raw_root, endpoint)
                if isinstance(capture_directory, str) else {})

    result = build_reference_census(
        member_records=member_records,
        party_records=sources["parties"][0],
        constituency_records=sources["constituencies"][0],
        member_capture_complete=member_is_authoritative,
        party_capture_complete=sources["parties"][1],
        constituency_capture_complete=sources["constituencies"][1],
    )
    entity_source_pointers: dict[str, dict[str, list[dict]]] = {
        endpoint: {} for endpoint in ("parties", "constituencies", "committees")}
    for observation in result["report"]["observations"]:
        if (not observation.get("canonical_iri")
                or observation.get("consolidation_result") != "resolved"
                or any(item.get("category") == "malformed_observation"
                       for item in observation.get("diagnostics", []))):
            continue
        kind = observation["reference_kind"]
        owner_endpoint = {"party": "parties", "representation": "constituencies",
                          "committee": "committees"}[kind]
        identity = observation["canonical_iri"]
        if observation["observation_source"] == "members":
            base_pointers = member_record_pointers.get(
                observation.get("member_iri"), [])
            source_path = observation.get("json_pointer")
            match = re.match(r"^/results/[0-9]+(/.*)$", source_path or "")
            if match is None:
                raise ValueError(
                    f"cannot resolve nested Members source pointer for {identity}")
            pointers = [{**pointer, "json_pointer":
                         pointer["json_pointer"].rstrip("/") + match.group(1)}
                        for pointer in base_pointers]
        else:
            pointers = endpoint_record_pointers.get(
                observation["observation_source"], {}).get(identity, [])
        if not pointers:
            continue
        bucket = entity_source_pointers[owner_endpoint].setdefault(identity, [])
        bucket.extend(pointers)
    for owners in entity_source_pointers.values():
        for identity, pointers in list(owners.items()):
            unique = {(pointer["path"], pointer["sha256"], pointer["json_pointer"]): pointer
                      for pointer in pointers}
            owners[identity] = [unique[key] for key in sorted(unique)]
    provenance = {
        "members": member_evidence,
        "parties": sources["parties"][1],
        "constituencies": sources["constituencies"][1],
        "entity_source_pointers": entity_source_pointers,
    }
    return result, provenance


def _record_pointers_by_identity(records: list[dict], endpoint: str,
                                 pointers: list[dict]) -> dict[str, list[dict]]:
    """Associate API result records with their original page/array pointers."""
    key = {"parties": "party", "constituencies": "constituencyOrPanel",
           "members": "member"}.get(endpoint)
    if key is None or len(records) != len(pointers):
        return {}
    result: dict[str, list[dict]] = {}
    for wrapper, pointer in zip(records, pointers):
        if not isinstance(pointer, dict):
            continue
        value = wrapper.get(key) if isinstance(wrapper, dict) else None
        if isinstance(value, dict) and isinstance(value.get("uri"), str):
            result.setdefault(str(iri(value["uri"])), []).append(pointer)
    return result


def _json_pointer_value(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("source record evidence is not an RFC 6901 JSON pointer")
    current = document
    for encoded in pointer[1:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if re.search(r"~(?![01])", encoded):
            raise ValueError("source record evidence contains an invalid JSON pointer escape")
        if isinstance(current, list):
            if not token.isdigit() or (len(token) > 1 and token.startswith("0")):
                raise ValueError("source record evidence has an invalid array index")
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise ValueError("source record evidence pointer does not resolve in its page")
    return current


def _source_evidence_for_record(raw_root: Path, pointer: dict, *,
                                entity_iri: str | None = None,
                                house_code: str | None = None) -> dict:
    """Verify a raw-page pointer and attach its exact durable observation key."""
    raw_root = Path(raw_root).expanduser().resolve()
    raw_path = (raw_root / pointer["path"]).resolve()
    try:
        raw_path.relative_to(raw_root)
    except ValueError as error:
        raise ValueError("source record pointer escapes the immutable raw root") from error
    body = raw_path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    metadata = _raw_page_metadata(raw_root, pointer)
    if digest != pointer.get("sha256") or metadata.get("sha256") != digest:
        raise ValueError("source record pointer does not match its immutable page hash")
    try:
        document = json.loads(body)
        record = _json_pointer_value(document, pointer["json_pointer"])
    except (UnicodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
        raise ValueError("source record JSON pointer does not resolve in its immutable page") from error

    def contains(value: object, key: str, expected: str) -> bool:
        if isinstance(value, dict):
            if value.get(key) == expected:
                return True
            return any(contains(child, key, expected) for child in value.values())
        if isinstance(value, list):
            return any(contains(child, key, expected) for child in value)
        return False

    if entity_iri is not None and not contains(record, "uri", entity_iri):
        raise ValueError(
            f"source record pointer does not contain the described entity {entity_iri}")
    if house_code is not None and not contains(record, "houseCode", house_code):
        raise ValueError(
            f"source record pointer does not establish persistent House code {house_code}")
    return {
        "source_hash": digest,
        "observed_at": metadata["retrieved_at"],
        "evidence_pointer": _raw_resource_pointer(raw_path, pointer["json_pointer"]),
    }


def _build_shared_entity_lineage(endpoint: str, graph: Graph, *, raw_root: Path,
                                 source_pointers: dict[str, list[dict]],
                                 store: CoreStateStore,
                                 retained_graph: Graph | None = None) -> dict[str, dict]:
    """Build complete entity lineage before staging or replacing a shared graph."""
    entities = shared_graph_entity_iris(endpoint, graph)
    retained = (shared_graph_entity_iris(endpoint, retained_graph)
                if retained_graph is not None else set())
    prior = store.endpoint_publication(endpoint) or {}
    prior_hash = prior.get("published_payload_hash")
    lineage: dict[str, dict] = {}
    for entity_iri in sorted(entities):
        if entity_iri in retained:
            if not isinstance(prior_hash, str):
                raise ValueError(
                    f"cannot safely attribute retained {endpoint} entity {entity_iri}: "
                    "the previous clean graph version is unavailable")
            lineage[entity_iri] = {"sources": [], "prior_payload_hash": prior_hash}
            continue
        pointers = source_pointers.get(entity_iri, [])
        if not pointers:
            raise ValueError(
                f"cannot safely establish source attribution for shared {endpoint} entity "
                f"{entity_iri}: no exact source record pointer is available")
        sources = [_source_evidence_for_record(raw_root, pointer,
                                               entity_iri=entity_iri)
                   for pointer in pointers]
        lineage[entity_iri] = {"sources": sources, "prior_payload_hash": None}
    return lineage


def _build_houses_entity_lineage(records: list[dict], pointers: list[dict], *,
                                 graph: Graph, raw_root: Path) -> dict[str, dict]:
    """Link each HouseTerm and persistent House to its matching source record."""
    sources: dict[str, list[dict]] = {}
    for wrapper, pointer in zip(records, pointers):
        house = wrapper.get("house") if isinstance(wrapper, dict) else None
        if not isinstance(house, dict):
            continue
        code = house.get("houseCode")
        if code not in PERSISTENT_HOUSES:
            continue
        term_iri = str(iri(house["uri"]))
        persistent_house = str(PERSISTENT_HOUSES[code][0])
        sources.setdefault(term_iri, []).append(
            _source_evidence_for_record(raw_root, pointer, entity_iri=term_iri))
        sources.setdefault(persistent_house, []).append(
            _source_evidence_for_record(raw_root, pointer, house_code=code))
    entities = shared_graph_entity_iris("houses", graph)
    lineage = {}
    for entity_iri in sorted(entities):
        entity_sources = sources.get(entity_iri, [])
        if not entity_sources:
            raise ValueError(
                f"cannot safely establish source attribution for shared Houses entity "
                f"{entity_iri}: no exact source record pointer is available")
        lineage[entity_iri] = {"sources": entity_sources,
                               "prior_payload_hash": None}
    return lineage


def _shared_graph_from_payload(payload: str, expected_hash: str | None,
                               endpoint: str) -> Graph:
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != expected_hash:
        raise ValueError(f"stored {endpoint} graph payload hash is invalid")
    graph = Graph()
    try:
        graph.parse(data=payload, format="nt")
    except Exception as error:
        raise ValueError(f"stored {endpoint} graph payload is invalid N-Triples") from error
    return graph


def _previous_reference_graphs(store: CoreStateStore, client,
                               loader: FusekiGraphStoreLoader,
                               publishing_run_id: str | None = None) -> dict[str, Graph]:
    """Recover dirty shared graphs and load their exact last accepted payloads."""
    previous = {}
    for endpoint_name, graph_iri in REFERENCE_GRAPHS.items():
        metadata = store.endpoint_publication(endpoint_name)
        if metadata and metadata.get("publication_state") == "dirty":
            pending = metadata.get("pending_payload")
            pending_hash = metadata.get("pending_payload_hash")
            if (not isinstance(pending, str)
                    or hashlib.sha256(pending.encode("utf-8")).hexdigest() != pending_hash):
                raise ValueError(
                    f"dirty {endpoint_name} graph has no hash-verified pending payload; "
                    "refusing to replace it")
            loader.replace(graph_iri, pending, content_type="application/n-triples")
            verify_core_graph(client, graph_iri, pending)
            store.complete_endpoint_publication(
                endpoint_name, graph_iri, pending_hash,
                coverage_authoritative=metadata.get("pending_coverage_authoritative"),
                publishing_run_id=publishing_run_id)
            metadata = store.endpoint_publication(endpoint_name)

        if metadata and metadata.get("publication_state") not in {"clean", None}:
            raise ValueError(f"shared {endpoint_name} graph is not clean")
        payload = metadata.get("published_payload") if metadata else None
        payload_hash = metadata.get("published_payload_hash") if metadata else None
        if isinstance(payload, str):
            previous[endpoint_name] = _shared_graph_from_payload(
                payload, payload_hash, endpoint_name)
            continue

        construct = getattr(client, "construct_graph", None)
        if construct is None:
            if payload_hash:
                raise ValueError(
                    f"the last {endpoint_name} graph payload is unavailable and the SPARQL client "
                    "cannot recover it safely")
            previous[endpoint_name] = Graph()
            continue
        graph = construct(graph_iri)
        if payload_hash and hashlib.sha256(ntriples(graph).encode("utf-8")).hexdigest() != payload_hash:
            raise ValueError(
                f"remote {endpoint_name} graph differs from its last clean state payload hash")
        previous[endpoint_name] = graph
    return previous


def _publish_reference_graphs(graphs: dict[str, Graph], *, store: CoreStateStore,
                              loader: FusekiGraphStoreLoader, client,
                              coverage_authoritative: bool | None,
                              endpoints: tuple[str, ...] = ("parties", "constituencies", "committees"),
                              member_source_run_id: str | None = None,
                              publishing_run_id: str | None = None,
                              entity_lineage_by_endpoint: dict[str, dict[str, dict]] | None = None
                              ) -> int:
    _assert_reference_source_not_older(store, endpoints, member_source_run_id)
    published = 0
    for endpoint_name in endpoints:
        graph_iri = REFERENCE_GRAPHS[endpoint_name]
        payload = ntriples(graphs[endpoint_name])
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        entity_lineage = (entity_lineage_by_endpoint or {}).get(endpoint_name)
        if entity_lineage is None:
            raise ValueError(
                f"cannot publish shared {endpoint_name} graph without complete entity lineage")
        prior = store.endpoint_publication(endpoint_name)
        if (coverage_authoritative is False and prior
                and prior.get("graph_iri") == graph_iri
                and prior.get("coverage_authoritative") is True):
            # A fixture may exercise publication against an empty/non-authoritative
            # graph, but it must not replace a graph established by a complete
            # authoritative scan.
            continue
        authority_already_recorded = (
            coverage_authoritative is not True
            or bool(prior and prior.get("coverage_authoritative") is True))
        legacy_gap = any(
            item["endpoint"] == endpoint_name and item["graph_iri"] == graph_iri
            and item["status"] == "pending"
            for item in store.provenance_incomplete_records())
        if (prior and prior.get("publication_state") == "clean"
                and prior.get("graph_iri") == graph_iri
                and prior.get("published_payload_hash") == payload_hash
                and prior.get("published_payload") == payload
                and authority_already_recorded and not legacy_gap):
            try:
                verify_core_graph(client, graph_iri, payload)
            except ValueError:
                # Exact verification found a mismatch; persist and replay the
                # same validated candidate through the normal dirty boundary.
                pass
            else:
                if member_source_run_id is not None:
                    store.record_endpoint_member_source_run(
                        endpoint_name, member_source_run_id)
                continue
        digest = store.mark_endpoint_dirty(
            endpoint_name, graph_iri, payload,
            coverage_authoritative=coverage_authoritative,
            member_source_run_id=member_source_run_id,
            run_id=publishing_run_id,
            entity_lineage=entity_lineage)
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        verify_core_graph(client, graph_iri, payload)
        store.complete_endpoint_publication(
            endpoint_name, graph_iri, digest,
            coverage_authoritative=coverage_authoritative,
            publishing_run_id=publishing_run_id)
        published += 1
    return published


def _reference_fixture_records(path: Path, endpoint: str) -> tuple[list[dict], bytes]:
    body = path.read_bytes()
    value = json.loads(body)
    records = value.get("results") if endpoint == "parties" and isinstance(value, dict) else value
    if not isinstance(records, list):
        raise ValueError("fixture must be a JSON array or a Parties object with results")
    return records, body


def _run_reference_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                        run_id: str | None = None) -> int:
    endpoint_name = args.endpoint
    if endpoint_name == "committees":
        return _run_committees_impl(args, store, run_id)
    graph_iri, url_attr, transform, validator, mapping_version = REFERENCE_ENDPOINTS[endpoint_name]
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    raw_root = settings.raw_dir.expanduser().resolve()
    versions = (_run_context(args, run_id=run_id) or {}).get(
        "versions", _run_versions(endpoint_name, settings))
    extraction_id = run_id or str(uuid.uuid4())
    source_run_id = run_id or extraction_id
    evidence: list[dict[str, str]] = []
    report_path: Path | None = None
    if args.fixture:
        records, body = _reference_fixture_records(Path(args.fixture), endpoint_name)
        observed_at = datetime.now(timezone.utc)
        raw_path, _ = persist_raw(
            root=raw_root, endpoint=str(Path(args.fixture).resolve()),
            params={"skip": 0, "limit": len(records)}, body=body, status=200,
            retrieved_at=observed_at,
            ontology_version=versions["ontology_version"] or REFERENCE_ONTOLOGY_VERSION,
            mapping_version=versions["mapping_version"] or mapping_version,
            endpoint_name=endpoint_name, extraction_id=extraction_id)
        _record_raw_page(args, store, endpoint=endpoint_name, run_id=run_id,
                         raw_path=raw_path, raw_root=raw_root, body=body,
                         source_url=None, parameters={"skip": 0, "limit": len(records)},
                         observed_at=observed_at, versions=versions)
        fixture_value = json.loads(body)
        base_pointer = "/results" if isinstance(fixture_value, dict) else ""
        evidence.extend(_raw_contract_pointer(
            raw_path, raw_root, body,
            f"{base_pointer}/{index}" if base_pointer else f"/{index}")
            for index, _ in enumerate(records))
        report_path = raw_path.parent / "source-drift.json"
    else:
        records = []
        api_url = getattr(settings, url_attr)
        count_field = {"parties": "partyCount",
                       "constituencies": "constituencyCount"}[endpoint_name]
        advertised = None
        last_page: tuple[Path, bytes, object] | None = None
        for page in _safe_harvest(
                args, ApiClient(api_url, retries=settings.retries,
                                timeout=settings.timeout), limit=settings.limit):
            observed_at = datetime.now(timezone.utc)
            raw_path, _ = persist_raw(
                root=raw_root, endpoint=api_url, params=page.params, body=page.body,
                status=page.status, retrieved_at=observed_at,
                ontology_version=versions["ontology_version"],
                mapping_version=versions["mapping_version"],
                endpoint_name=endpoint_name, extraction_id=extraction_id)
            _record_raw_page(args, store, endpoint=endpoint_name, run_id=run_id,
                             raw_path=raw_path, raw_root=raw_root, body=page.body,
                              source_url=api_url, parameters=page.params,
                              observed_at=observed_at, versions=versions)
            decoded = _decode_api_page(page.body, endpoint_name, args)
            envelope_report = _api_envelope_contract(
                args, endpoint_name, decoded, run_id=source_run_id,
                raw_path=raw_path, raw_root=raw_root, body=page.body,
                count_field=count_field, expected_count=advertised)
            _raise_on_envelope_failure(envelope_report, endpoint_name)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise _RunFailure(f"every {endpoint_name} API page must contain a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get(count_field) if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise _RunFailure(f"every {endpoint_name} API page must contain a nonnegative integer {count_field}")
            if advertised is None:
                advertised = count
            elif count != advertised:
                raise _RunFailure(f"{endpoint_name} advertised count changed during scan")
            page_records = decoded.get("results", decoded) if isinstance(decoded, dict) else decoded
            records.extend(page_records)
            evidence.extend(_raw_contract_pointer(
                raw_path, raw_root, page.body, f"/results/{index}")
            for index in range(len(page_records)))
            report_path = raw_path.parent / "source-drift.json"
            last_page = (raw_path, page.body, decoded)
        if advertised is None or advertised != len(records):
            if last_page is not None and advertised is not None:
                last_path, last_body, last_decoded = last_page
                envelope_report = _api_envelope_contract(
                    args, endpoint_name, last_decoded, run_id=source_run_id,
                    raw_path=last_path, raw_root=raw_root, body=last_body,
                    count_field=count_field,
                    observed_record_count=len(records))
                _raise_on_envelope_failure(envelope_report, endpoint_name)
            raise _RunFailure(
                f"{endpoint_name} capture contains {len(records)} records, not its advertised {advertised}")
    source_report = _source_contract(args, endpoint_name, records,
                                     run_id=source_run_id, evidence=evidence,
                                     report_path=report_path)
    if source_report["source_failed"] or source_report["failed_record_indices"]:
        raise _RunFailure(
            f"{endpoint_name} source contract contains incompatible records: "
            f"{_contract_failure_detail(source_report)}")
    try:
        source_graph = transform(records)
        validator(records, source_graph)  # source gate precedes any loader construction
    except Exception as error:
        raise _RunFailure(
            f"{endpoint_name} shared source graph cannot be transformed safely: {error}") from error

    census, provenance = _reference_inputs(
        endpoint_name=endpoint_name, endpoint_records=records, member_records=None,
        store=store, raw_root=settings.raw_dir,
        endpoint_is_authoritative=not bool(args.fixture),
        member_is_authoritative=False,
        endpoint_record_pointers={endpoint_name: _record_pointers_by_identity(
            records, endpoint_name, evidence)},
    )
    member_source_run_id = (provenance["members"]["run_id"]
                            if provenance["members"] is not None else None)
    member_records = []
    if provenance["members"] is not None:
        loaded = load_latest_complete_capture(settings.raw_dir, store, "members") if store else None
        member_records = loaded[0] if loaded is not None else []
    member_graph = candidate_member_dataset(member_records) if member_records else Graph()
    # Preflight all newly observed source graphs and conflict/closure gates
    # before constructing a publisher or changing a shared graph.
    _write_reference_report(args, census["report"])
    candidates = build_reference_candidates(census, member_graph=member_graph)

    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    published_graphs = 0
    if endpoint:
        if not query_endpoint:
            raise ValueError("Fuseki SPARQL endpoint is required for post-load whole-graph verification")
        if store is None: raise RuntimeError("online reference publication requires durable core ETL state")
        client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user,
                                    password=settings.fuseki_password,
                                    timeout=settings.timeout)
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user,
                                       password=settings.fuseki_password,
                                       timeout=settings.timeout)
        context = _run_context(args, run_id=run_id)
        if context is not None:
            context.update(loader=loader, client=client)
            context["safe_publication"] = True
        previous = _previous_reference_graphs(
            store, client, loader, publishing_run_id=run_id)
        candidates = build_reference_candidates(
            census, member_graph=member_graph, previous_graphs=previous)
        publish_all = bool(not args.fixture and provenance["members"] is not None)
        publish_set = (("parties", "constituencies", "committees") if publish_all
                       else (endpoint_name,))
        entity_lineages = {
            name: _build_shared_entity_lineage(
                name, candidates["graphs"][name], raw_root=raw_root,
                source_pointers=provenance["entity_source_pointers"].get(name, {}),
                store=store, retained_graph=candidates["retained_graphs"][name])
            for name in publish_set
        }
        published_graphs = _publish_reference_graphs(
            candidates["graphs"], store=store, loader=loader, client=client,
            coverage_authoritative=(True if publish_all else
                                    False if args.fixture else None),
            endpoints=publish_set,
            member_source_run_id=member_source_run_id,
            publishing_run_id=run_id,
            entity_lineage_by_endpoint=entity_lineages)
        if hasattr(client, "query"):
            verify_reference_closure(client)
        if endpoint_name == "parties":
            # Core state is already clean. The existing reconciliation store is
            # the sole due authority; if it is unavailable, the next complete
            # reconcile scan still detects new/identity-changed source records.
            try:
                reconciliation_store = ReconciliationStore(_reconciliation_state_path(args, settings))
            except Exception as error:
                _handoff_warning("party", error)
            else:
                try:
                    for wrapper in records:
                        _try_mark_due(reconciliation_store, "party", wrapper)
                finally:
                    try:
                        reconciliation_store.close()
                    except Exception as error:
                        _handoff_warning("party", error)
    elif not args.offline and not args.fixture:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    context = _run_context(args, run_id=run_id)
    if context is not None and endpoint:
        context["safe_publication"] = True
    if args.output_ttl:
        Path(args.output_ttl).write_text(
            turtle(candidates["graphs"][endpoint_name]), encoding="utf-8")
    if args.output_nq:
        Path(args.output_nq).write_text("".join(
            nquads(candidates["graphs"][name], REFERENCE_GRAPHS[name])
            for name in ("parties", "constituencies", "committees")
            if len(candidates["graphs"][name])), encoding="utf-8")
    print(json.dumps({"records": len(records), "published": bool(endpoint),
                      "published_graphs": published_graphs,
                      "reference_census": reference_census_summary(census["report"]),
                      "reference_closure": candidates["closure"]}, sort_keys=True))
    _set_run_metrics(args, counters={"extracted": len(records),
                                     "changed": len(records), "unchanged": 0,
                                     "published_graphs": published_graphs,
                                     "quarantined": 0, "validation_failures": 0,
                                     "api_failures": 0,
                                     "publication_succeeded": int(bool(endpoint))})
    return 0


def _run_committees_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                         run_id: str | None = None) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__,
                            "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    if args.fixture:
        body = Path(args.fixture).read_bytes()
        value = json.loads(body)
        if (isinstance(value, list) and value
                and all(isinstance(item, dict) and isinstance(item.get("uri"), str)
                        for item in value)):
            records = value
            graph = transform_committees(records)
            validate_committees(records, graph)
            if args.output_ttl:
                Path(args.output_ttl).write_text(turtle(graph), encoding="utf-8")
            if args.output_nq:
                Path(args.output_nq).write_text(nquads(graph, COMMITTEES_GRAPH),
                                                encoding="utf-8")
            print(json.dumps({"records": len(records), "published": False,
                              "fixture": True}, sort_keys=True))
            return 0
        member_records, _, advertised = _members_fixture_records(Path(args.fixture))
        complete_fixture = advertised is not None and advertised == len(member_records)
        member_source_run_id = None
        member_record_pointers = {}
    else:
        if store is None:
            raise ValueError("Committee owner generation requires a complete Members capture")
        loaded = load_latest_complete_capture(settings.raw_dir, store, "members")
        if loaded is None:
            raise ValueError("Committee owner generation requires a successful complete Members API run")
        member_records = loaded[0]
        member_source_run_id = loaded[1]["run_id"]
        capture_directory = loaded[1].get("capture_directory")
        member_record_pointers = (capture_record_pointers(
            Path(capture_directory), settings.raw_dir, "members")
            if isinstance(capture_directory, str) else {})
        complete_fixture = False

    census, provenance = _reference_inputs(
        endpoint_name="committees", endpoint_records=None,
        member_records=member_records, store=store, raw_root=settings.raw_dir,
        endpoint_is_authoritative=False,
        member_is_authoritative=not bool(args.fixture),
        member_record_pointers=member_record_pointers,
    )
    member_graph = candidate_member_dataset(member_records)
    _write_reference_report(args, census["report"])
    candidates = build_reference_candidates(census, member_graph=member_graph)
    graph = candidates["graphs"]["committees"]
    if args.output_ttl:
        Path(args.output_ttl).write_text(turtle(graph), encoding="utf-8")
    if args.output_nq:
        Path(args.output_nq).write_text(nquads(graph, COMMITTEES_GRAPH),
                                        encoding="utf-8")

    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    published = 0
    if endpoint and not args.fixture:
        if not query_endpoint:
            raise ValueError("Fuseki SPARQL endpoint is required for post-load whole-graph verification")
        if store is None:
            raise RuntimeError("online Committee publication requires durable core ETL state")
        client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user,
                                    password=settings.fuseki_password,
                                    timeout=settings.timeout)
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user,
                                       password=settings.fuseki_password,
                                       timeout=settings.timeout)
        context = _run_context(args, run_id=run_id)
        if context is not None:
            context.update(loader=loader, client=client)
            context["safe_publication"] = True
        previous = _previous_reference_graphs(
            store, client, loader, publishing_run_id=run_id)
        candidates = build_reference_candidates(
            census, member_graph=member_graph, previous_graphs=previous)
        entity_lineages = {
            name: _build_shared_entity_lineage(
                name, candidates["graphs"][name], raw_root=settings.raw_dir,
                source_pointers=provenance["entity_source_pointers"].get(name, {}),
                store=store, retained_graph=candidates["retained_graphs"][name])
            for name in ("parties", "constituencies", "committees")
        }
        published = _publish_reference_graphs(
            candidates["graphs"], store=store, loader=loader, client=client,
            coverage_authoritative=True,
            member_source_run_id=member_source_run_id,
            publishing_run_id=run_id,
            entity_lineage_by_endpoint=entity_lineages,
        )
        verify_reference_closure(client)
    elif endpoint and args.fixture:
        # Fixture observations can validate and serialize candidate RDF, but
        # they never become authoritative shared owner-graph publication.
        published = 0
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(census["records"]["committees"]),
                      "published": bool(published), "published_graphs": published,
                      "fixture_complete": complete_fixture,
                      "reference_census": reference_census_summary(census["report"]),
                      "reference_closure": candidates["closure"]}, sort_keys=True))
    return 0


def run_reference(args: argparse.Namespace) -> int:
    return _run_shared(args, args.endpoint, _run_reference_impl)


def _run_office_registry_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                              run_id: str | None = None) -> int:
    endpoint_name = args.endpoint
    if getattr(args, "fixture", None):
        raise ValueError("office registry commands use --registry-file, not an API --fixture")
    registry_path = Path(getattr(args, "registry_file", None) or OFFICE_REGISTRY_FILE)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    validate_registry_source(registry)
    units_graph = transform_administrative_units(registry)
    offices_graph = transform_offices(registry)
    validate_administrative_units(registry, units_graph)
    validate_offices(registry, offices_graph)

    if endpoint_name == "administrative-units":
        graph, graph_iri = units_graph, ADMINISTRATIVE_UNITS_GRAPH
    elif endpoint_name == "offices":
        graph, graph_iri = offices_graph, OFFICES_GRAPH
    else:
        raise ValueError(f"unsupported office registry graph endpoint: {endpoint_name}")

    if args.output_ttl:
        Path(args.output_ttl).write_text(turtle(graph), encoding="utf-8")
    payload = nquads(graph, graph_iri)
    if args.output_nq:
        Path(args.output_nq).write_text(payload, encoding="utf-8")

    settings = Settings.from_environment()
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint:
        if not query_endpoint:
            raise ValueError("Fuseki SPARQL endpoint is required for post-load whole-graph verification")
        if store is None:
            raise RuntimeError("online registry publication requires durable core ETL state")
        if endpoint_name == "offices":
            units_state = store.endpoint_publication("administrative-units")
            expected_units_hash = hashlib.sha256(ntriples(units_graph).encode("utf-8")).hexdigest()
            if (not units_state or units_state.get("publication_state") != "clean"
                    or units_state.get("published_payload_hash") != expected_units_hash):
                raise ValueError("publish the current validated AdministrativeUnit graph before the office graph")
        serialized = ntriples(graph)
        digest = store.mark_endpoint_dirty(endpoint_name, graph_iri, serialized)
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password,
                               timeout=settings.timeout).replace(graph_iri, serialized,
                                                                  content_type="application/n-triples")
        verify_core_graph(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user,
                                             password=settings.fuseki_password,
                                             timeout=settings.timeout), graph_iri, serialized)
        store.complete_endpoint_publication(endpoint_name, graph_iri, digest)
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for registry/developer runs")
    records = registry["administrative_units"] if endpoint_name == "administrative-units" else registry["offices"]
    print(json.dumps({"records": len(records), "published": bool(endpoint),
                      "graph": graph_iri, "registry_file": str(registry_path)}, sort_keys=True))
    return 0


def run_office_registry(args: argparse.Namespace) -> int:
    return _run_shared(args, args.endpoint, _run_office_registry_impl)


def _members_fixture_records(path: Path) -> tuple[list[dict], bytes, int | None]:
    body = path.read_bytes(); value = json.loads(body)
    if isinstance(value, dict) and isinstance(value.get("member"), dict):
        return [value], body, None
    if isinstance(value, dict):
        records, counts = value.get("results"), value.get("head", {}).get("counts", {})
        advertised = counts.get("memberCount") if isinstance(counts, dict) else None
    else:
        records, advertised = value, None
    if not isinstance(records, list): raise ValueError("Members fixture must be a member wrapper, array, or results envelope")
    return records, body, advertised


def _verified_previous_member_graph(prior: dict | None, graph_iri: str) -> Graph:
    """Load only the hash-verified last accepted Member payload from state."""
    if not isinstance(prior, dict) or prior.get("graph_iri") != graph_iri:
        raise ValueError("previous accepted Member graph identity is invalid")
    payload = prior.get("published_payload")
    if not isinstance(payload, str):
        raise ValueError("previous accepted Member payload is unavailable")
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if payload_hash != prior.get("published_payload_hash"):
        raise ValueError("previous accepted Member payload hash is invalid")
    graph = Graph()
    try:
        graph.parse(data=payload, format="nt")
    except Exception as error:
        raise ValueError("previous accepted Member payload cannot be parsed") from error
    return graph


def _member_migration_inventory(store: CoreStateStore,
                                office_rows: list[dict],
                                run_id: str) -> tuple[dict | None, dict[str, str]]:
    """Inventory locally verified legacy Member payloads before contract-3 PUTs.

    This deliberately uses only the last validated payloads kept in core state
    and the local office occurrence ledger. It never reads a live triple store.
    Missing payloads are reported as inventory gaps; payloads that are present
    but fail integrity checks block only their Member's migration.
    """
    legacy_types = {
        "MinisterOfStateMembership": MEMBERS.MinisterOfStateMembership,
        "MinisterOfStateRole": MEMBERS.MinisterOfStateRole,
    }
    legacy_predicates = {
        "hasMinisterOfStateRole": MEMBERS.hasMinisterOfStateRole,
        "officeNameUri": MEMBERS.officeNameUri,
    }

    def describe_payload(payload: object, expected_hash: object, graph_iri: str,
                         identity: str) -> tuple[dict | None, str]:
        if not isinstance(payload, str) or not isinstance(expected_hash, str):
            return None, "unavailable"
        if graph_iri != expected_graph_iri("members", identity):
            return None, "wrong_graph_identity"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if digest != expected_hash:
            return None, "hash_mismatch"
        graph = Graph()
        try:
            graph.parse(data=payload, format="nt")
        except Exception:
            return None, "invalid_ntriples"
        if (URIRef(identity), RDF.type, OIR.Member) not in graph:
            return None, "wrong_member_subject"
        legacy_memberships = set(graph.subjects(
            RDF.type, MEMBERS.MinisterOfStateMembership))
        legacy_roles_found = set(graph.subjects(RDF.type, MEMBERS.MinisterOfStateRole))
        legacy_roles_found.update(
            role for membership in legacy_memberships
            for role in graph.objects(membership, MEMBERS.hasMinisterOfStateRole))
        legacy_subjects = legacy_memberships | legacy_roles_found
        legacy_subjects.update(
            period for subject in legacy_memberships
            for period in graph.objects(subject, MEMBERS.hasMembershipDateRange))
        legacy_triples = {
            triple for subject in legacy_subjects
            for triple in graph.triples((subject, None, None))
        }
        legacy_triples.update(
            triple for subject in legacy_subjects
            for triple in graph.triples((None, None, subject)))
        legacy_triples.update(graph.triples((None, MEMBERS.hasMinisterOfStateRole, None)))
        legacy_triples.update(graph.triples((None, MEMBERS.officeNameUri, None)))
        return {
            "payload_hash": digest,
            "legacy_triples": {
                **{name: len(list(graph.triples((None, RDF.type, term))))
                   for name, term in legacy_types.items()},
                **{name: len(list(graph.triples((None, term, None))))
                   for name, term in legacy_predicates.items()},
            },
            "legacy_office_triple_count": len(legacy_triples),
            "legacy_office_resource_iris": sorted(map(str, legacy_subjects)),
            "office_holding_count": len(set(graph.subjects(RDF.type, MEMBERS.OfficeHolding))),
            "office_holding_iris": sorted(map(str, set(
                graph.subjects(RDF.type, MEMBERS.OfficeHolding)))),
            "verified": True,
        }, "verified"

    resources = store.resources("members")
    resources_by_iri = {row["resource_iri"]: row for row in resources}
    migration_resources = []
    blocked: dict[str, str] = {}
    for prior in resources:
        identity = prior["resource_iri"]
        contract = prior.get("contract_version")
        legacy_contract = type(contract) is not int or contract < 3
        has_publication = bool(
            prior.get("published_source_hash") or prior.get("published_payload") is not None
            or prior.get("last_published_at") or prior.get("publication_state") == "dirty")
        if not legacy_contract or not has_publication:
            continue

        published, published_status = describe_payload(
            prior.get("published_payload"), prior.get("published_payload_hash"),
            prior["graph_iri"], identity)
        pending = None
        pending_status = "not_present"
        if prior.get("pending_payload") is not None:
            pending, pending_status = describe_payload(
                prior.get("pending_payload"), prior.get("pending_payload_hash"),
                prior["graph_iri"], identity)
            if (pending is not None and prior.get("pending_graph_iri") != prior["graph_iri"]):
                pending, pending_status = None, "wrong_graph_identity"

        item = {
            "member_iri": identity,
            "graph_iri": prior["graph_iri"],
            "contract_version": contract,
            "publication_state": prior.get("publication_state"),
            "published_payload": published or {"verified": False, "status": published_status},
            "pending_payload": pending or {"verified": False, "status": pending_status},
        }
        # Old manifest imports did not retain an RDF payload. Report that gap
        # explicitly in the inventory, but keep the approved contract-bump
        # republish path; a corrupt payload that is present is different and
        # fails closed because its inventory cannot be trusted.
        if prior.get("published_payload") is not None and published is None:
            blocked[identity] = (
                "legacy Member payload is present but cannot be verified for inventory; "
                "no live triple-store query was attempted")
        if prior.get("pending_payload") is not None and pending is None:
            blocked[identity] = (
                "dirty legacy Member pending payload is present but cannot be verified for inventory; "
                "no live triple-store query was attempted")
        migration_resources.append(item)

    # Record disappeared source observations and whether a contract-3 prior
    # graph contains the exact ledger-derived holding. Contract-2 payloads did
    # not publish OfficeHolding records, but their absent reports are inventoried.
    missing_observations = []
    for row in office_rows:
        if row.get("source_presence") not in {"missing", "confirmed_missing"}:
            continue
        identity = row.get("member_iri")
        prior = resources_by_iri.get(identity)
        contract = prior.get("contract_version") if prior else None
        payload_graph = None
        if prior and prior.get("published_payload") is not None:
            try:
                payload_graph = _verified_previous_member_graph(prior, prior["graph_iri"])
            except ValueError:
                payload_graph = None
        resolution = row.get("last_accepted_resolution")
        matched = []
        if isinstance(resolution, dict) and isinstance(resolution.get("snapshot"), dict):
            snapshot = resolution["snapshot"]
            for office in resolution.get("office_iris", []):
                holding = _office_holding_iri(identity, row["occurrence_key"], office)
                if (payload_graph is not None and holding in set(
                        payload_graph.subjects(RDF.type, MEMBERS.OfficeHolding))
                        and _prior_office_holding_matches(
                            payload_graph, identity, holding, office,
                            snapshot.get("date_range", {}))):
                    matched.append(str(holding))
        if type(contract) is int and contract >= 3:
            inventory_status = "matched_prior_holding" if matched else "no_exact_prior_holding_match"
        else:
            inventory_status = "contract_predates_office_holding_publication"
        missing_observations.append({
            "member_iri": identity,
            "occurrence_key": row["occurrence_key"],
            "source_presence": row.get("source_presence"),
            "has_last_accepted_resolution": isinstance(resolution, dict),
            "matched_published_holding_iris": sorted(matched),
            "inventory_status": inventory_status,
        })

    if not migration_resources:
        return None, blocked
    inventory = {
        "version": 1,
        "run_id": run_id,
        "basis": "verified local CoreStateStore Member payloads and OfficeOccurrenceStore ledger; no live triple-store access",
        "member_graphs": sorted(migration_resources, key=lambda item: item["member_iri"]),
        "missing_observations": sorted(
            missing_observations,
            key=lambda item: (item["member_iri"], item["occurrence_key"])),
    }
    return inventory, blocked


def _write_member_migration_inventory(inventory: dict, path: Path) -> str:
    """Atomically persist the pre-publication migration inventory evidence."""
    payload = json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)
    return digest


def _member_office_policy(args: argparse.Namespace) -> tuple[dict, dict, str, dict[str, str]]:
    """Load the reviewed local office authority used by Member transformation."""
    registry_path = Path(getattr(args, "registry_file", None) or OFFICE_REGISTRY_FILE)
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid office registry: {error}") from error
    validate_registry_source(registry)
    decisions, review_hash = load_office_review(
        Path(getattr(args, "review_file", None) or OFFICE_DECISIONS_FILE), registry)
    office_types = {
        str(office_iri(office["key"])): office["office_type"]
        for office in registry["offices"]
    }
    return registry, decisions, review_hash, office_types


def _resolution_records(occurrence_key: str, resolution: dict, *, retained: bool,
                        retention_status: str | None = None) -> list[dict]:
    """Adapt one ledger acceptance to the transform/validator public contract."""
    snapshot = resolution.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError(f"accepted office resolution {occurrence_key} has no source snapshot")
    member_iri = snapshot.get("member_iri")
    membership_iri = snapshot.get("membership_iri")
    date_range = snapshot.get("date_range")
    office_iris = resolution.get("office_iris")
    if not isinstance(office_iris, list) or not office_iris:
        raise ValueError(f"accepted office resolution {occurrence_key} has no office targets")
    record = {
        "occurrence_key": occurrence_key,
        "member_iri": member_iri,
        "membership_iri": membership_iri,
        "date_range": date_range,
        "retained": retained,
    }
    if retention_status is not None:
        record["retention_status"] = retention_status
    return [{**record, "office_iri": office} for office in sorted(office_iris)]


def _accepted_office_ledger_rows(rows: list[dict], current_observations: list[dict],
                                 decisions: dict[str, dict], *,
                                 allow_revocation: bool) -> tuple[dict[str, list[dict]],
                                                                  dict[str, list[dict]],
                                                                  dict[str, list[dict]]]:
    """Partition ledger evidence into current, retainable and reviewed-revoke rows."""
    present = {}
    for observation in current_observations:
        present.setdefault(observation["member_iri"], set()).add(
            (observation["identity_key"], observation["fingerprint"]))

    current: dict[str, list[dict]] = {}
    retained: dict[str, list[dict]] = {}
    revoked: dict[str, list[dict]] = {}
    for row in rows:
        resolution = row.get("last_accepted_resolution")
        if not isinstance(resolution, dict):
            continue
        member_iri = row["member_iri"]
        key = row["occurrence_key"]
        decision = decisions.get(key)
        is_current_source = (
            row.get("source_presence") == "present"
            and (row.get("identity_key"), row.get("current_fingerprint"))
            in present.get(member_iri, set())
        )
        explicitly_revoked = bool(
            allow_revocation and is_current_source
            and row.get("status") == "rejected"
            and isinstance(decision, dict)
            and decision.get("action") == "revoke"
            and decision.get("observation_fingerprint") == row.get("current_fingerprint")
        )
        if explicitly_revoked:
            revoked.setdefault(member_iri, []).append(row)
            continue

        acceptance_is_current = bool(
            is_current_source and row.get("status") == "accepted"
            and resolution.get("fingerprint") == row.get("current_fingerprint")
        )
        if acceptance_is_current:
            current.setdefault(member_iri, []).extend(
                _resolution_records(key, resolution, retained=False))
        else:
            retained.setdefault(member_iri, []).append(row)
    return current, retained, revoked


def _office_holding_iri(member_iri: str, occurrence_key: str, office_iri_value: str) -> URIRef:
    digest = hashlib.sha256(canonical_json({
        "kind": "office-holding-occurrence-v1",
        "occurrence_key": occurrence_key,
        "office_iri": office_iri_value,
    }).encode("utf-8")).hexdigest()
    return URIRef(f"{member_iri}#office-holding-{digest}")


def _prior_office_holding_matches(graph: Graph, member_iri: str, holding: URIRef,
                                 office: str, date_range: dict) -> bool:
    """Verify the prior accepted holding is exactly the ledger snapshot we reuse."""
    member = URIRef(member_iri)
    periods = list(graph.objects(holding, MEMBERS.hasMembershipDateRange))
    if ((holding, RDF.type, MEMBERS.OfficeHolding) not in graph
            or list(graph.objects(holding, MEMBERS.heldOffice)) != [URIRef(office)]
            or list(graph.objects(holding, MEMBERS.officeHolder)) != [member]
            or (member, MEMBERS.hasOfficeHolding, holding) not in graph
            or (member, MEMBERS.hasMembersMembership, holding) not in graph
            or len(periods) != 1):
        return False
    period = periods[0]
    starts = list(graph.objects(period, MEMBERS.StartDate))
    ends = list(graph.objects(period, MEMBERS.EndDate))
    expected_start = datetime_literal(date_range["start"])
    expected_ends = ([datetime_literal(date_range["end"])]
                     if date_range.get("end") is not None else [])
    return (len(starts) == 1 and starts[0] == expected_start
            and ends == expected_ends)


def _office_acceptance_history(office_store: OfficeOccurrenceStore,
                               row: dict) -> list[dict]:
    history = [attempt.get("last_accepted_resolution")
               for attempt in office_store.attempts(row["occurrence_key"])]
    history.append(row.get("last_accepted_resolution"))
    unique = {}
    for resolution in history:
        if isinstance(resolution, dict):
            unique[canonical_json(resolution)] = resolution
    return list(unique.values())


def _prepare_member_office_resolutions(
        member_iri: str, prior: dict | None, office_store: OfficeOccurrenceStore,
        member_ledger_rows: list[dict], accepted_records: list[dict],
        retained_rows: list[dict], revoked_rows: list[dict]
        ) -> tuple[list[dict], Graph | None, str | None]:
    """Compose retained holdings only from the verified last accepted Member graph."""
    output = list(accepted_records)
    contract_version = prior.get("contract_version") if isinstance(prior, dict) else None
    has_publication = bool(prior and (
        prior.get("published_source_hash") or prior.get("published_payload") is not None
        or prior.get("last_published_at")))

    # Contract-2 Member graphs predate OfficeHolding. Their old nested office
    # role assertions are intentionally retired by the contract-version bump;
    # a ledger-only acceptance was not yet published as a holding.
    if not (type(contract_version) is int and contract_version >= 3 and has_publication):
        return output, None, None

    has_accepted_evidence = bool(
        accepted_records or retained_rows or revoked_rows
        or any(isinstance(row.get("last_accepted_resolution"), dict)
               for row in member_ledger_rows))
    if not has_accepted_evidence:
        # No office assertion for this Member has been accepted by the local
        # occurrence ledger. Unrelated Member/party changes do not need office
        # payload recovery.
        return output, None, None

    graph_iri = prior.get("graph_iri")
    try:
        previous = _verified_previous_member_graph(prior, graph_iri)
    except Exception as error:
        return output, None, (
            f"{type(error).__name__}: {error}; prior OfficeHolding state cannot be verified")

    prior_holding_ids = set(previous.subjects(RDF.type, MEMBERS.OfficeHolding))
    active_ids = {
        _office_holding_iri(member_iri, item["occurrence_key"], str(item["office_iri"]))
        for item in output
    }
    authorized_replacements: set[URIRef] = set()

    for row in retained_rows:
        key = row["occurrence_key"]
        retention_status = ("missing_retained" if row.get("source_presence") == "missing"
                            else "conflict_retained")
        matched_by_holding: dict[URIRef, dict] = {}
        for resolution in reversed(_office_acceptance_history(office_store, row)):
            snapshot = resolution.get("snapshot")
            if not isinstance(snapshot, dict):
                continue
            for office in resolution.get("office_iris", []):
                holding = _office_holding_iri(member_iri, key, office)
                if (holding not in matched_by_holding and holding in prior_holding_ids
                        and _prior_office_holding_matches(
                            previous, member_iri, holding, office,
                            snapshot.get("date_range", {}))):
                    matched_by_holding[holding] = _resolution_records(
                        key, {**resolution, "office_iris": [office]}, retained=True,
                        retention_status=retention_status)[0]
        # The stored acceptance is not enough to publish a holding which was
        # never in the last accepted Member graph.
        output.extend(matched_by_holding.values())
        active_ids.update(matched_by_holding)

    # A newly reviewed accepted target or explicit revocation is the only
    # evidence that can authorize retiring a previous target for that source
    # occurrence. Ordinary rejection, absence and conflict never do so.
    current_keys = {item["occurrence_key"] for item in accepted_records}
    current_keys.update(row["occurrence_key"] for row in revoked_rows)
    for row in [*retained_rows, *revoked_rows]:
        if row["occurrence_key"] not in current_keys:
            continue
        for resolution in _office_acceptance_history(office_store, row):
            for office in resolution.get("office_iris", []):
                authorized_replacements.add(
                    _office_holding_iri(member_iri, row["occurrence_key"], office))
    # Current accepted rows can supersede an older reviewed target as well.
    accepted_keys = {item["occurrence_key"] for item in accepted_records}
    for row in member_ledger_rows:
        if row.get("occurrence_key") not in accepted_keys:
            continue
        for resolution in _office_acceptance_history(office_store, row):
            for office in resolution.get("office_iris", []):
                authorized_replacements.add(
                    _office_holding_iri(member_iri, row["occurrence_key"], office))

    unaccounted = prior_holding_ids - active_ids - authorized_replacements
    if unaccounted:
        return output, previous, (
            "verified prior Member graph contains OfficeHolding resources without "
            "current accepted, retained, or explicitly reviewed revocation evidence: "
            + ", ".join(sorted(map(str, unaccounted))))
    return output, previous, None


def _missing_office_membership_context(wrapper: dict,
                                       resolutions: list[dict]) -> list[str]:
    """Find accepted records whose containing House membership is no longer in source."""
    member = wrapper.get("member", {}) if isinstance(wrapper, dict) else {}
    memberships = member.get("memberships", []) if isinstance(member, dict) else []
    current = {
        wrapped.get("membership", {}).get("uri")
        for wrapped in memberships
        if isinstance(wrapped, dict) and isinstance(wrapped.get("membership"), dict)
    }
    return sorted({
        str(item.get("membership_iri"))
        for item in resolutions
        if isinstance(item, dict)
        and item.get("membership_iri") not in current
    })


def _unregistered_office_targets(resolutions: list[dict],
                                 office_types: dict[str, str]) -> list[str]:
    """Return accepted or retained office targets absent from the active registry."""
    return sorted({
        str(item.get("office_iri"))
        for item in resolutions
        if isinstance(item, dict)
        and item.get("office_iri") not in office_types
    })


def _deduplicate_members(records: list[dict], advertised: int | None) -> list[dict]:
    if not records: raise ValueError("Members harvest must not be empty")
    unique: dict[str, dict] = {}
    codes: dict[str, str] = {}
    graphs: dict[str, str] = {}
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict): raise ValueError("each Members record must contain a member object")
        member = wrapper["member"]; identity = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member.get("uri")))
        code, graph_iri = member.get("memberCode"), member_graph_iri(member)
        if code in codes and codes[code] != identity:
            raise ValueError(f"Member memberCode collision (including URI aliases): {code}")
        if graph_iri in graphs and graphs[graph_iri] != identity:
            raise ValueError(f"Member graph IRI collision (including URI aliases): {graph_iri}")
        codes[code], graphs[graph_iri] = identity, identity
        if identity in unique:
            if source_hash(unique[identity]["member"]) != source_hash(member): raise ValueError(f"conflicting duplicate Member identity: {identity}")
            continue
        unique[identity] = wrapper
    if advertised is not None and (
            isinstance(advertised, bool) or not isinstance(advertised, int)
            or advertised != len(unique)):
        raise _AdvertisedCountMismatch("Members", len(unique), advertised)
    return [unique[key] for key in sorted(unique)]


def _legacy_override(args: argparse.Namespace) -> Path | None:
    # ``--state-file`` remains an explicit, read-only legacy JSON import path.
    # New operational state is always selected with ``--state-db``.
    value = getattr(args, "legacy_state_file", None) or getattr(args, "state_file", None)
    return Path(value).expanduser() if value else None


def _replay_missing_dirty(endpoint: str, resource: dict, store: CoreStateStore,
                          loader: FusekiGraphStoreLoader, client: FusekiSparqlClient,
                          verifier) -> None:
    """Replay a durable validated payload for a dirty resource omitted today."""
    identity = resource["resource_iri"]
    graph_iri = resource["graph_iri"]
    payload = resource["pending_payload"]
    payload_hash = resource["pending_payload_hash"]
    source_hash = resource["pending_source_hash"]
    if (not isinstance(payload, str) or not isinstance(payload_hash, str)
            or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash
            or resource["pending_graph_iri"] != graph_iri
            or expected_graph_iri(endpoint, identity) != graph_iri
            or not isinstance(source_hash, str) or not source_hash
            or type(resource["contract_version"]) is not int):
        raise ValueError(
            f"dirty {endpoint} resource {identity} has no intact replayable payload; "
            "it must reappear in a source scan before publication can be retried"
        )
    try:
        graph = Graph().parse(data=payload, format="nt")
    except Exception as error:
        raise ValueError(f"dirty {endpoint} payload is not valid N-Triples for {identity}") from error
    root_type = OIR.Member if endpoint == "members" else ELIDL.DraftLegislationWork
    if (URIRef(identity), RDF.type, root_type) not in graph:
        raise ValueError(f"dirty {endpoint} payload has the wrong resource subject: {identity}")
    # The row was made durable before its original PUT. A disappeared source
    # record is not grounds for deleting it or for skipping recovery.
    loader.replace(graph_iri, payload, content_type="application/n-triples")
    verifier(client, graph_iri, identity, len(graph))
    verify_core_graph(client, graph_iri, payload)
    store.complete_publication(endpoint, identity, source_hash=source_hash,
                                graph_iri=graph_iri, payload_hash=payload_hash,
                                contract_version=resource["contract_version"])


def _run_members_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                      run_id: str | None = None,
                      reconciliation_store: ReconciliationStore | None = None,
                      office_store: OfficeOccurrenceStore | None = None) -> int:
    ephemeral = OfficeOccurrenceStore(":memory:") if args.offline or office_store is None else None
    try:
        return _run_members_impl_body(
            args, store, run_id, reconciliation_store, office_store, ephemeral)
    finally:
        if ephemeral is not None:
            ephemeral.close()


def _run_members_impl_body(args: argparse.Namespace, store: CoreStateStore | None,
                           run_id: str | None,
                           reconciliation_store: ReconciliationStore | None,
                           office_store: OfficeOccurrenceStore | None,
                           ephemeral_office_store: OfficeOccurrenceStore | None) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    raw_root = settings.raw_dir.expanduser().resolve()
    extraction_id = run_id or str(uuid.uuid4())
    source_run_id = run_id or extraction_id
    versions = (_run_context(args, run_id=run_id) or {}).get(
        "versions", _run_versions("members", settings))
    records_with_pointers: list[tuple[dict, dict]] = []
    report_path: Path | None = None
    last_api_page: tuple[Path, bytes, object] | None = None
    if args.fixture:
        fixture = Path(args.fixture)
        records, body, advertised, shape = _office_fixture_records(fixture)
        observed_at = datetime.now(timezone.utc)
        raw_path, _ = persist_raw(root=raw_root, endpoint=str(fixture.resolve()),
                    params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=observed_at,
                    ontology_version=versions["ontology_version"] or REFERENCE_ONTOLOGY_VERSION,
                    mapping_version=versions["mapping_version"] or MEMBER_MAPPING_VERSION,
                    endpoint_name="members", extraction_id=extraction_id)
        _record_raw_page(args, store, endpoint="members", run_id=run_id,
                         raw_path=raw_path, raw_root=raw_root, body=body,
                         source_url=None, parameters={"skip": 0, "limit": len(records)},
                         observed_at=observed_at, versions=versions)
        report_path = raw_path.parent / "source-drift.json"
        for index, wrapper in enumerate(records):
            pointer = "" if shape == "single" else (
                f"/results/{index}" if shape == "results" else f"/{index}")
            records_with_pointers.append((
                wrapper, _office_raw_pointer(raw_path, raw_root, body, pointer)))
    else:
        records, advertised = [], None
        for page in _safe_harvest(
                args, ApiClient(settings.members_api_url, retries=settings.retries,
                                timeout=settings.timeout), limit=settings.limit):
            observed_at = datetime.now(timezone.utc)
            raw_path, _ = persist_raw(root=raw_root, endpoint=settings.members_api_url,
                        params=page.params, body=page.body, status=page.status,
                        retrieved_at=observed_at,
                        ontology_version=versions["ontology_version"],
                        mapping_version=versions["mapping_version"],
                        endpoint_name="members", extraction_id=extraction_id)
            _record_raw_page(args, store, endpoint="members", run_id=run_id,
                             raw_path=raw_path, raw_root=raw_root, body=page.body,
                              source_url=settings.members_api_url, parameters=page.params,
                              observed_at=observed_at, versions=versions)
            decoded = _decode_api_page(page.body, "Members", args)
            envelope_report = _api_envelope_contract(
                args, "members", decoded, run_id=source_run_id,
                raw_path=raw_path, raw_root=raw_root, body=page.body,
                count_field="memberCount", expected_count=advertised)
            _raise_on_envelope_failure(envelope_report, "Members")
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise _RunFailure("every Members API page must be an object envelope with a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get("memberCount") if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise _RunFailure("every Members API page must contain a nonnegative integer head.counts.memberCount")
            page_records = decoded["results"]
            records.extend(page_records)
            for index, wrapper in enumerate(page_records):
                records_with_pointers.append((
                    wrapper, _office_raw_pointer(
                        raw_path, raw_root, page.body, f"/results/{index}")))
            if advertised is None: advertised = count
            elif count != advertised: raise _RunFailure("Members advertised count changed during scan")
            last_api_page = (raw_path, page.body, decoded)
            report_path = raw_path.parent / "source-drift.json"
    contract_report = _source_contract(
        args, "members", [wrapper for wrapper, _pointer in records_with_pointers],
        run_id=source_run_id,
        evidence=[pointer for _wrapper, pointer in records_with_pointers],
        report_path=report_path)
    failed_indices = set(contract_report["failed_record_indices"])
    if contract_report["source_failed"]:
        raise _RunFailure("Members source container violates the source contract")
    retry_candidates = _retry_candidates(store, "members")
    retry_candidates_by_hash = _retry_candidates_by_hash(
        store, "members") if not args.fixture and not args.offline else {}
    allow_unidentified_retry = not args.fixture and not args.offline
    for index in sorted(failed_indices):
        wrapper, pointer = records_with_pointers[index]
        member = wrapper.get("member") if isinstance(wrapper, dict) else None
        identity = member.get("uri") if isinstance(member, dict) else None
        source_digest = (source_hash(member) if isinstance(member, dict)
                         else hashlib.sha256(json.dumps(
                             wrapper, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), default=str).encode()).hexdigest())
        metadata = _raw_page_metadata(raw_root, pointer)
        error = "; ".join(
            item["change"] + " at " + item["json_pointer"]
            for item in contract_report["findings"]
            if item.get("severity") == "record" and item.get("record_index") == index)
        _record_quarantine(
            store, endpoint="members", run_id=run_id, source_hash=source_digest,
            observed_at=metadata["retrieved_at"],
            evidence_pointer=_raw_resource_pointer(
                raw_root / pointer["path"], pointer["json_pointer"]),
            stage="source_contract", error=error or "record violates source contract",
            resource_iri=identity if isinstance(identity, str) else None,
            classification="record_source_contract_failure", versions=versions)
        started = _start_retries(
            store, _retry_rows_for_record(
                retry_candidates, retry_candidates_by_hash,
                identity if isinstance(identity, str) else None, source_digest,
                include_unidentified=allow_unidentified_retry), run_id)
        _finish_retries(store, started, run_id, success=False,
                        error="record still violates the source contract", args=args)
    valid_with_pointers = [item for index, item in enumerate(records_with_pointers)
                           if index not in failed_indices]
    # Cheap source validation is also a per-record gate. Run it before any
    # complete-scan office reconciliation so an invalid record cannot assert
    # source absence in that independent ledger.
    preflight_valid = []
    preflight_failure_count = 0
    for wrapper, pointer in valid_with_pointers:
        try:
            validate_member_source(wrapper)
        except Exception as error:
            member = wrapper.get("member") if isinstance(wrapper, dict) else None
            identity = member.get("uri") if isinstance(member, dict) else None
            digest = (source_hash(member) if isinstance(member, dict)
                      else hashlib.sha256(json.dumps(
                          wrapper, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str).encode()).hexdigest())
            metadata = _raw_page_metadata(raw_root, pointer)
            _record_quarantine(
                store, endpoint="members", run_id=run_id, source_hash=digest,
                observed_at=metadata["retrieved_at"],
                evidence_pointer=_raw_resource_pointer(
                    raw_root / pointer["path"], pointer["json_pointer"]),
                stage="member_source_validation", error=f"{type(error).__name__}: {error}",
                resource_iri=identity if isinstance(identity, str) else None,
                classification="record_source_validation_failure", versions=versions)
            preflight_failure_count += 1
            _degrade_run(args, error=f"Member source record failed preflight: {error}",
                         classification="record_source_validation_failure")
            started = _start_retries(
                store, _retry_rows_for_record(
                    retry_candidates, retry_candidates_by_hash,
                    identity if isinstance(identity, str) else None, digest,
                    include_unidentified=allow_unidentified_retry), run_id)
            _finish_retries(store, started, run_id, success=False,
                            error=f"{type(error).__name__}: {error}", args=args)
            continue
        preflight_valid.append((wrapper, pointer))
    valid_records = [wrapper for wrapper, _pointer in preflight_valid]
    if failed_indices:
        _degrade_run(args, error=f"{len(failed_indices)} Member record(s) failed source contract",
                     classification="record_source_contract_failure")
    contract_failure_count = len(failed_indices)
    record_failure_count = contract_failure_count + preflight_failure_count
    try:
        records = (_deduplicate_members(
            valid_records, advertised if record_failure_count == 0 else None)
            if valid_records else [])
    except _AdvertisedCountMismatch as error:
        if last_api_page is not None:
            last_path, last_body, last_envelope = last_api_page
            envelope_report = _api_envelope_contract(
                args, "members", last_envelope, run_id=source_run_id,
                raw_path=last_path, raw_root=raw_root, body=last_body,
                count_field="memberCount", observed_record_count=error.observed)
            _raise_on_envelope_failure(envelope_report, "Members")
        raise _RunFailure(
            "Members advertised memberCount does not match unique observed records",
            scope="source", classification="api_envelope_contract_failure") from error
    if (last_api_page is not None and record_failure_count == 0
            and advertised not in (None, 0) and not valid_records):
        last_path, last_body, last_envelope = last_api_page
        envelope_report = _api_envelope_contract(
            args, "members", last_envelope, run_id=source_run_id,
            raw_path=last_path, raw_root=raw_root, body=last_body,
            count_field="memberCount", observed_record_count=0)
        _raise_on_envelope_failure(envelope_report, "Members")
    pointers_by_identity = {}
    for wrapper, pointer in preflight_valid:
        member = wrapper.get("member") if isinstance(wrapper, dict) else None
        if isinstance(member, dict) and isinstance(member.get("uri"), str):
            identity = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member["uri"]))
            pointers_by_identity.setdefault(identity, pointer)
    for wrapper in records:
        member = wrapper["member"]
        identity = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member["uri"]))
    records_with_pointers = [(wrapper, pointers_by_identity.get(
        str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(wrapper["member"]["uri"]))))
        for wrapper in records]
    complete_scan = (not args.fixture or
                     (advertised is not None and advertised == len(records)))
    if record_failure_count:
        complete_scan = False
    observations = extract_office_observations(records_with_pointers)
    registry, decisions, review_hash, office_types = _member_office_policy(args)

    # An offline run is reproducible from only its supplied source and reviewed
    # files. Incomplete online fixtures may inspect durable accepted evidence,
    # but only a complete live/fixture scan is allowed to update that ledger.
    reconcile_persistent = bool(
        office_store is not None and complete_scan and not args.offline)
    prior_office_rows = office_store.occurrences() if reconcile_persistent else []
    active_office_store = office_store
    if not reconcile_persistent and (args.offline or office_store is None):
        active_office_store = ephemeral_office_store
    if active_office_store is None:
        raise RuntimeError("Member office reconciliation requires an occurrence store")
    if reconcile_persistent or ephemeral_office_store is not None:
        office_result = active_office_store.reconcile(
            observations, registry, decisions, review_hash, run_id=extraction_id)
        ledger_rows = office_result["records"]
    else:
        office_result = None
        ledger_rows = active_office_store.occurrences()

    current_office, retained_office, revoked_office = _accepted_office_ledger_rows(
        ledger_rows, observations, decisions,
        allow_revocation=bool(args.offline or complete_scan))
    office_rows_by_member: dict[str, list[dict]] = {}
    for row in ledger_rows:
        if isinstance(row.get("member_iri"), str):
            office_rows_by_member.setdefault(row["member_iri"], []).append(row)
    # Only accepted/current or previously accepted outcomes can change RDF.
    # Unresolved observations remain report-only and preserve the hash skip.
    office_related_members = set(current_office) | set(retained_office) | set(revoked_office)
    office_related_members.update(
        row["member_iri"] for row in ledger_rows
        if isinstance(row.get("member_iri"), str)
        and isinstance(row.get("last_accepted_resolution"), dict))
    office_config_changed_members: set[str] = set()
    if reconcile_persistent:
        prior_by_key = {row["occurrence_key"]: row for row in prior_office_rows}
        current_registry_hash = json_hash(registry)
        for row in ledger_rows:
            previous = prior_by_key.get(row["occurrence_key"])
            if (previous is None or previous.get("registry_hash") != current_registry_hash
                    or previous.get("review_hash") != review_hash):
                if isinstance(row.get("member_iri"), str):
                    office_config_changed_members.add(row["member_iri"])

    known = store.resources("members") if store is not None else []
    migration_inventory = None
    migration_inventory_summary = None
    migration_inventory_blocked: dict[str, str] = {}
    if store is not None and not args.offline:
        migration_inventory, migration_inventory_blocked = _member_migration_inventory(
            store, ledger_rows, extraction_id)
        if migration_inventory is not None:
            inventory_path = Path(
                getattr(args, "migration_inventory_file", None)
                or store.path.with_name(
                    f"{store.path.name}.member-migration-{extraction_id}.json"))
            inventory_digest = _write_member_migration_inventory(
                migration_inventory, inventory_path)
            migration_inventory_summary = {
                "path": str(inventory_path),
                "sha256": inventory_digest,
                "legacy_member_graphs": len(migration_inventory["member_graphs"]),
                "missing_observations": len(migration_inventory["missing_observations"]),
                "blocked_members": sorted(migration_inventory_blocked),
                "inventory_gaps": sorted(
                    item["member_iri"] for item in migration_inventory["member_graphs"]
                    if not item["published_payload"].get("verified", False)),
            }

    graphs: list[tuple[dict, object | None, str, str, list[dict], str]] = []
    retry_started_by_identity: dict[str, list[str]] = {}
    for wrapper in records:
        member = wrapper["member"]; identity, digest, graph_iri = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member["uri"])), source_hash(member), member_graph_iri(member)
        prior = store.get_resource("members", identity) if store is not None else None
        pointer = pointers_by_identity.get(identity)
        if store is not None and run_id is not None:
            if pointer is None:
                raise RuntimeError(f"Member {identity} has no immutable raw source pointer")
            page_metadata = _raw_page_metadata(raw_root, pointer)
            old = store.observe_resource(
                "members", identity, graph_iri, digest, run_id,
                observed_at=page_metadata["retrieved_at"],
                evidence_pointer=_raw_resource_pointer(
                    raw_root / pointer["path"], pointer["json_pointer"]),
                request_parameters=page_metadata["params"], versions=versions,
            )
        else:
            old = {}
        retry_ids = _start_retries(
            store, _retry_rows_for_record(
                retry_candidates, retry_candidates_by_hash, identity, digest,
                include_unidentified=allow_unidentified_retry), run_id)
        if retry_ids:
            retry_started_by_identity[identity] = retry_ids
            context = _run_context(args, run_id=run_id)
            if context is not None:
                context.setdefault("retry_attempts", []).extend(retry_ids)
        # Hash-first: unchanged published records do not enter transformation.
        office_resolutions = list(current_office.get(identity, []))
        omissions = validate_member_source(
            wrapper, office_resolutions=office_resolutions, office_types=office_types)
        if identity in migration_inventory_blocked:
            omissions.append({
                "path": "member",
                "context": identity,
                "reason": migration_inventory_blocked[identity],
                "category": "migration_inventory_blocked",
                "preservation_status": "previous_member_graph_retained",
            })
            graphs.append((wrapper, None, identity, digest, omissions, "skipped"))
            continue
        if (not args.offline and old.get("publication_state", "clean") == "clean"
                and old.get("contract_version") == 3
                and old.get("published_source_hash") == digest and old.get("graph_iri") == graph_iri
                and identity not in office_config_changed_members
                and identity not in office_related_members):
            for item in omissions:
                if (item.get("category") == "source_quarantine"
                        and ".parties[" in item.get("path", "")):
                    item["preservation_status"] = "unchanged_published_graph_retained"
            graphs.append((wrapper, None, identity, digest, omissions, "skipped")); continue
        office_resolutions, _previous_office_graph, office_preservation_error = (
            _prepare_member_office_resolutions(
                identity, prior, active_office_store,
                office_rows_by_member.get(identity, []), office_resolutions,
                retained_office.get(identity, []), revoked_office.get(identity, [])))
        missing_memberships = _missing_office_membership_context(
            wrapper, office_resolutions)
        if missing_memberships and office_preservation_error is None:
            office_preservation_error = (
                "accepted or retained OfficeHolding requires a containing House membership "
                "that is absent from the current Member source; preserving the prior Member "
                "graph rather than dropping the holding: "
                + ", ".join(missing_memberships))
        unregistered_targets = _unregistered_office_targets(
            office_resolutions, office_types)
        if unregistered_targets and office_preservation_error is None:
            office_preservation_error = (
                "accepted or retained office target is absent from the currently registered "
                "office_types; preserving the prior Member graph: "
                + ", ".join(unregistered_targets))
        status = "changed" if prior else "new"
        if office_preservation_error is not None:
            omissions.append({
                "path": "member.memberships[].membership.offices[]",
                "context": identity,
                "reason": office_preservation_error,
                "category": "office_preservation_blocked",
                "preservation_status": "previous_member_graph_retained",
            })
            graphs.append((wrapper, None, identity, digest, omissions, "skipped"))
            continue
        # Run the source gate with the complete effective accepted set before
        # transformation; retained records are checked again by the independent
        # RDF acceptance builder below.
        omissions = validate_member_source(
            wrapper, office_resolutions=office_resolutions, office_types=office_types)
        graph, exclusions = transform_member_with_report(
            wrapper, office_resolutions=office_resolutions, office_types=office_types)
        validate_member(wrapper, graph, office_resolutions=office_resolutions,
                        office_types=office_types)
        malformed_parties = [item for item in exclusions
                             if item.get("category") == "source_quarantine"
                             and ".parties[" in item.get("path", "")]
        if graph is not None and malformed_parties and not args.offline:
            affected_memberships = {item["context"] for item in malformed_parties}
            previous_payload = prior.get("published_payload") if prior else None
            has_published_state = bool(prior and (
                prior.get("published_source_hash")
                or prior.get("published_payload") is not None
                or prior.get("last_published_at")
            ))
            preserved = Graph()
            preserved_by_membership = {}
            preservation_error = None
            if has_published_state:
                try:
                    previous_graph = _verified_previous_member_graph(prior, graph_iri)
                    preserved_by_membership = {
                        membership: prior_party_membership_evidence(
                            previous_graph, URIRef(member["uri"]), {membership})
                        for membership in affected_memberships
                    }
                    for evidence in preserved_by_membership.values():
                        preserved += evidence
                except Exception as error:
                    preservation_error = f"{type(error).__name__}: {error}"
            if has_published_state and preservation_error is not None:
                # Without the last accepted payload there is no safe way to
                # distinguish previously accepted party evidence from a
                # deletion. Leave the existing Member graph untouched.
                for item in malformed_parties:
                    item["preservation_status"] = "blocked_previous_graph_retained"
                    item["preservation_reason"] = preservation_error
                graph = None
                status = "skipped"
            else:
                if preserved:
                    graph += preserved
                    validate_member(
                        wrapper, graph, preserved_party_graph=preserved,
                        office_resolutions=office_resolutions,
                        office_types=office_types)
                for item in malformed_parties:
                    has_old_party_data = bool(preserved_by_membership.get(item["context"]))
                    item["preservation_status"] = (
                        "previous_accepted_party_evidence_composed"
                        if has_old_party_data else
                        "no_previous_party_evidence_for_membership"
                        if has_published_state else
                        "no_previous_accepted_member_graph"
                    )
        elif graph is not None and malformed_parties:
            for item in malformed_parties:
                item["preservation_status"] = "not_applicable_offline"
        if (graph is not None and not args.offline
                and not malformed_parties
                and old.get("publication_state", "clean") == "clean"
                and old.get("contract_version") == 3
                and old.get("published_source_hash") == digest
                and old.get("graph_iri") == graph_iri
                and identity in office_related_members):
            try:
                previous_graph = _verified_previous_member_graph(prior, graph_iri)
            except Exception:
                # No trustworthy prior RDF means equality cannot authorize a
                # hash skip; the validated current graph is published instead.
                pass
            else:
                if set(graph) == set(previous_graph):
                    graph = None
                    status = "skipped"
        graphs.append((wrapper, graph, identity, digest, exclusions, status))

    reference_census = None
    reference_candidates = None
    member_candidate_graph = None
    if not args.fixture and complete_scan:
        member_pointer_map = _record_pointers_by_identity(
            [wrapper for wrapper, _pointer in records_with_pointers], "members",
            [pointer for _wrapper, pointer in records_with_pointers])
        reference_census, _reference_provenance = _reference_inputs(
            endpoint_name="members", endpoint_records=None,
            member_records=records, store=store, raw_root=raw_root,
            endpoint_is_authoritative=False,
            member_is_authoritative=True,
            member_record_pointers=member_pointer_map,
        )
        _write_reference_report(args, reference_census["report"])
        member_candidate_graph = candidate_member_dataset(records)
        # Fail closed on census conflicts and candidate closure before any
        # owner or Member graph is mutated.
        reference_candidates = build_reference_candidates(
            reference_census, member_graph=member_candidate_graph)

    if args.output_nq:
        Path(args.output_nq).write_text("".join(nquads(graph, graph_iri) for wrapper, graph, identity, digest, exclusions, _ in graphs if graph is not None for graph_iri in [member_graph_iri(wrapper["member"])]), encoding="utf-8")
    if getattr(args, "output_ttl", None):
        Path(args.output_ttl).write_text("\n".join(turtle(graph) for _, graph, _, _, _, _ in graphs if graph is not None), encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint and not query_endpoint:
        raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
    published = skipped = 0
    deferred_dirty: list[dict] = []
    repaired: list[str] = []
    seen = {identity for _, _, identity, _, _, _ in graphs}
    missing = sorted(row["resource_iri"] for row in known if row["resource_iri"] not in seen)
    if endpoint:
        if store is None:
            raise RuntimeError("online Member publication requires durable core ETL state")
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        context = _run_context(args, run_id=run_id)
        if context is not None:
            context.update(loader=loader, client=client)
            context["safe_publication"] = True
        if reference_candidates is not None:
            if store is None:
                raise RuntimeError("authoritative Member reference publication requires durable core ETL state")
            previous = _previous_reference_graphs(
                store, client, loader, publishing_run_id=run_id)
            reference_candidates = build_reference_candidates(
                reference_census, member_graph=member_candidate_graph,
                previous_graphs=previous)
            entity_lineages = {
                name: _build_shared_entity_lineage(
                    name, reference_candidates["graphs"][name], raw_root=raw_root,
                    source_pointers=_reference_provenance[
                        "entity_source_pointers"].get(name, {}),
                    store=store,
                    retained_graph=reference_candidates["retained_graphs"][name])
                for name in ("parties", "constituencies", "committees")
            }
            _publish_reference_graphs(
                reference_candidates["graphs"], store=store, loader=loader,
                client=client, coverage_authoritative=True,
                member_source_run_id=(extraction_id if store is not None
                                      and complete_scan and not args.fixture else None),
                publishing_run_id=run_id,
                entity_lineage_by_endpoint=entity_lineages)
            if hasattr(client, "query"):
                verify_reference_closure(client)
        for wrapper, graph, identity, digest, exclusions, status in graphs:
            if graph is None:
                prior = store.get_resource("members", identity)
                if any(item.get("category") == "office_preservation_blocked"
                       or item.get("category") == "migration_inventory_blocked"
                       for item in exclusions):
                    # The office-preservation or migration-inventory gate says
                    # this Member must keep its prior graph untouched.
                    skipped += 1
                    continue
                if any(item.get("preservation_status") == "blocked_previous_graph_retained"
                       for item in exclusions):
                    # Current evidence cannot safely replace the accepted graph
                    # because its party payload is unavailable or unverifiable.
                    skipped += 1
                    continue
                effective_offices, _prior_offices, office_error = (
                    _prepare_member_office_resolutions(
                        identity, prior, active_office_store,
                        office_rows_by_member.get(identity, []),
                        current_office.get(identity, []),
                        retained_office.get(identity, []),
                        revoked_office.get(identity, [])))
                if office_error is not None:
                    exclusions.append({
                        "path": "member.memberships[].membership.offices[]",
                        "context": identity,
                        "reason": office_error,
                        "category": "office_preservation_blocked",
                        "preservation_status": "previous_member_graph_retained",
                    })
                    skipped += 1
                    continue
                malformed_parties = [item for item in exclusions
                                     if item.get("category") == "source_quarantine"
                                     and ".parties[" in item.get("path", "")]
                if (malformed_parties
                        and any(item.get("preservation_status") == "unchanged_published_graph_retained"
                                for item in malformed_parties)):
                    try:
                        previous_graph = _verified_previous_member_graph(
                            prior, member_graph_iri(wrapper["member"]))
                    except ValueError as error:
                        for item in malformed_parties:
                            item["preservation_status"] = "blocked_previous_graph_retained"
                            item["preservation_reason"] = str(error)
                        skipped += 1
                        continue
                    preserved = prior_party_membership_evidence(
                        previous_graph, URIRef(wrapper["member"]["uri"]),
                        {item["context"] for item in malformed_parties})
                    validate_member(wrapper, previous_graph,
                                    preserved_party_graph=preserved,
                                    office_resolutions=effective_offices,
                                    office_types=office_types)
                    try:
                        verify_core_graph(client, prior["graph_iri"], prior["published_payload"])
                    except ValueError:
                        # Repair from the last accepted graph, not a fresh
                        # transform that would omit its retained party evidence.
                        graph = previous_graph
                        for item in malformed_parties:
                            item["preservation_status"] = "unchanged_published_graph_replayed"
                        repaired.append(identity)
                    else:
                        _try_mark_due(reconciliation_store, "member", wrapper,
                                      force=status == "new")
                        skipped += 1
                        continue
                if graph is None:
                    if prior["published_payload"] is not None:
                        try:
                            verify_core_graph(client, prior["graph_iri"], prior["published_payload"])
                        except ValueError:
                            pass  # verified whole-graph replacement below repairs mismatch
                        else:
                            _try_mark_due(reconciliation_store, "member", wrapper,
                                          force=status == "new")
                            skipped += 1
                            continue
                    # The malformed-party branch can reach this repair only for
                    # the legacy unchanged-graph check above. Recreate the
                    # current graph with the same office resolution contract.
                    graph, exclusions = transform_member_with_report(
                        wrapper, office_resolutions=effective_offices,
                        office_types=office_types)
                    validate_member(wrapper, graph,
                                    office_resolutions=effective_offices,
                                    office_types=office_types)
                    repaired.append(identity)
            graph_iri = member_graph_iri(wrapper["member"])
            payload = ntriples(graph)
            payload_hash = store.mark_publication_dirty("members", identity, source_hash=digest,
                                                        graph_iri=graph_iri, payload=payload,
                                                        contract_version=3)
            loader.replace(graph_iri, payload, content_type="application/n-triples")
            verify_member_competency(client, graph_iri, identity, len(graph))
            verify_core_graph(client, graph_iri, payload)
            store.complete_publication("members", identity, source_hash=digest, graph_iri=graph_iri,
                                       payload_hash=payload_hash, contract_version=3)
            _try_mark_due(reconciliation_store, "member", wrapper, force=status == "new")
            published += 1
        if reference_candidates is not None and hasattr(client, "query"):
            verify_reference_closure(client)
        for row in known:
            if row["resource_iri"] in seen or row["publication_state"] != "dirty":
                continue
            if row.get("contract_version") != 3:
                skipped += 1
                deferred_dirty.append({
                    "resource_iri": row["resource_iri"],
                    "contract_version": row.get("contract_version"),
                    "reason": "legacy dirty Member payload is not replayed while absent from the source scan; "
                             "retain its current graph and retry after the Member reappears for contract-3 validation",
                })
                continue
            _replay_missing_dirty("members", row, store, loader, client,
                                  verify_member_competency)
            published += 1
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    report = [item for _, _, _, _, exclusions, _ in graphs for item in exclusions]
    for retry_ids in retry_started_by_identity.values():
        _finish_retries(store, retry_ids, run_id, success=True, args=args)
    identities = {kind: sorted(identity for _, _, identity, _, _, status in graphs if status == kind) for kind in ("new", "changed", "skipped")}
    identities["skipped"] = sorted(set(identities["skipped"]) - set(repaired))
    identities["changed"] = sorted(set(identities["changed"]) | set(repaired))
    print(json.dumps({"records": len(records), "published": published, "skipped": skipped,
                      "new": identities["new"], "changed": identities["changed"],
                      "skipped_identities": identities["skipped"], "missing_retained": missing,
                       "future_work_omitted": [item for item in report
                                               if item["category"] not in {
                                                   "source_quarantine",
                                                    "office_preservation_blocked",
                                                    "migration_inventory_blocked"}],
                      "malformed_offices": [item for item in report
                                            if item["category"] == "source_quarantine"
                                            and ".offices[" in item.get("path", "")],
                        "malformed_parties": [item for item in report
                                              if item["category"] == "source_quarantine"
                                              and ".parties[" in item.get("path", "")],
                       "office_reconciliation": {
                           "complete_scan": complete_scan,
                           "observations": len(observations),
                           "ledger_updated": reconcile_persistent,
                           "accepted": (office_result["accepted"]
                                        if office_result is not None else None),
                           "rejected": (office_result["rejected"]
                                        if office_result is not None else None),
                           "unresolved": (office_result["unresolved"]
                                          if office_result is not None else None),
                           "review_required": (office_result["review_required"]
                                               if office_result is not None else None),
                           "revocations_applied": sum(len(rows) for rows in revoked_office.values()),
                           "retained_holding_records": sum(len(rows) for rows in retained_office.values()),
                       },
                        "office_preservation_blocked": [item for item in report
                                                         if item["category"] == "office_preservation_blocked"],
                        "migration_inventory": migration_inventory_summary,
                        "migration_inventory_blocked": [item for item in report
                                                         if item["category"] == "migration_inventory_blocked"],
                         "legacy_dirty_deferred": deferred_dirty,
                         }, sort_keys=True))
    context = _run_context(args, run_id=run_id)
    if context is not None and endpoint:
        context["safe_publication"] = True
    _set_run_metrics(args, counters={
        "extracted": len(records) + record_failure_count,
        "changed": len(identities["changed"]), "unchanged": len(identities["skipped"]),
        "published_graphs": published, "quarantined": record_failure_count,
        "validation_failures": record_failure_count,
        "api_requests": (0 if args.fixture else
                         len({pointer["path"] for _wrapper, pointer in records_with_pointers})),
        "api_failures": 0, "publication_succeeded": int(bool(endpoint)),
    })
    return 0


def _run_members(args: argparse.Namespace, store: CoreStateStore | None = None,
                 reconciliation_store: ReconciliationStore | None = None,
                 office_store: OfficeOccurrenceStore | None = None) -> int:
    if store is None:
        return _run_members_impl(args)
    settings = Settings.from_environment()
    versions = _run_versions("members", settings)
    run_id = store.start_run("members", "full_refresh", is_complete=True,
                             parameters={"source": "fixture" if args.fixture else "api",
                                          "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                          "api_url": None if args.fixture else settings.members_api_url,
                                          "limit": settings.limit}, versions=versions)
    _begin_run_context(args, run_id, "members", versions)
    try:
        result = _run_members_impl(args, store, run_id, reconciliation_store,
                                   office_store)
        context = _run_context(args, run_id=run_id)
        _finalize_run(store, args, run_id=run_id, endpoint="members",
                      versions=versions,
                      loader=context.get("loader") if context else None,
                      client=context.get("client") if context else None)
    except Exception as error:
        context = _run_context(args, run_id=run_id)
        if (context is not None and not context.get("finished")
                and not context.get("catalog_state_unresolved")):
            scope = getattr(error, "scope", "system")
            classification = getattr(error, "classification", "system_failure")
            _record_fatal_run(
                store, args, run_id=run_id, endpoint="members", error=error,
                failure_scope=scope, failure_classification=classification)
        raise
    return result


def run_members(args: argparse.Namespace) -> int:
    """Run Members; online refreshes serialize against the shared SQLite state."""
    if args.offline:
        return _run_members_impl(args)
    settings = Settings.from_environment()
    state_db = Path(getattr(args, "state_db", None) or settings.core_state_db_file).expanduser()
    legacy_members = _legacy_override(args) or settings.members_legacy_state_file
    office_state = Path(getattr(args, "office_state_file", None)
                        or OFFICE_OCCURRENCE_STATE_DB_FILE).expanduser()
    with state_lock(state_db):
        with CoreStateStore(state_db, legacy_members=legacy_members,
                            legacy_bills=settings.bills_legacy_state_file) as store:
            with OfficeOccurrenceStore(office_state) as office_occurrences:
                endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
                if not endpoint:
                    return _run_members(args, store, office_store=office_occurrences)
                try:
                    reconciliation_store = ReconciliationStore(_reconciliation_state_path(args, settings))
                except Exception as error:
                    _handoff_warning("member", error)
                    return _run_members(args, store, office_store=office_occurrences)
                try:
                    return _run_members(args, store, reconciliation_store,
                                        office_occurrences)
                finally:
                    try:
                        reconciliation_store.close()
                    except Exception as error:
                        _handoff_warning("member", error)


def _bills_fixture_records(path: Path) -> tuple[list[dict], bytes, int | None]:
    body = path.read_bytes(); value = json.loads(body)
    if isinstance(value, dict):
        records = value.get("results")
        counts = value.get("head", {}).get("counts", {}) if isinstance(value.get("head"), dict) else {}
        advertised = counts.get("billCount") if isinstance(counts, dict) else None
    else:
        records, advertised = value, None
    if not isinstance(records, list):
        raise ValueError("Bills fixture must be an array or Legislation results envelope")
    return records, body, advertised


def _local_sponsor_source(args: argparse.Namespace, settings: Settings) -> tuple[list[dict], bool]:
    """Preserve a complete live Bill scan or a deliberately scoped test fixture."""
    raw_root = Path(args.raw_dir).expanduser() if args.raw_dir else settings.raw_dir
    extraction_id = str(uuid.uuid4())
    if args.fixture:
        path = Path(args.fixture)
        records, body, advertised = _bills_fixture_records(path)
        persist_raw(root=raw_root, endpoint=str(path.resolve()),
                    params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=datetime.now(timezone.utc),
                    ontology_version="legislation.owl.ttl@phase-4-legislative-lifecycle-2026",
                    mapping_version="bill_mapping.csv@phase-4-legislative-lifecycle-2026",
                    endpoint_name="legislation", extraction_id=extraction_id)
        # A fixture never establishes absence for any Bill outside its scope.
        return _deduplicate_bills(records, advertised), False
    records, advertised, last_page, raw_root, extraction_id = _capture_api_pages(
        args, "legislation", settings.bills_api_url, settings, count_field="billCount")
    try:
        unique = _deduplicate_bills(records, advertised, allow_empty=advertised == 0)
    except _AdvertisedCountMismatch as error:
        if last_page is not None:
            raw_path, body, decoded = last_page
            report = _api_envelope_contract(
                args, "legislation", decoded, run_id=extraction_id,
                raw_path=raw_path, raw_root=raw_root, body=body,
                count_field="billCount", observed_record_count=error.observed)
            _raise_on_envelope_failure(report, "Legislation")
        raise ValueError(
            "Bills advertised count does not match unique records during local reconciliation scan") from error
    return unique, True


def _deduplicate_bills(records: list[dict], advertised: int | None, *, allow_empty=False) -> list[dict]:
    if not records and not allow_empty: raise ValueError("Bills harvest must not be empty")
    unique, graphs = {}, {}
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict): raise ValueError("each Legislation result must contain a bill object")
        bill = wrapper["bill"]; identity, graph = bill["uri"], bill_graph_iri(bill)
        if graph in graphs and graphs[graph] != identity: raise ValueError("Bill graph IRI collision")
        graphs[graph] = identity
        if identity in unique:
            if bill_source_hash(unique[identity]["bill"]) != bill_source_hash(bill): raise ValueError(f"conflicting duplicate Bill identity: {identity}")
            continue
        unique[identity] = wrapper
    if advertised is not None and (
            isinstance(advertised, bool) or not isinstance(advertised, int)
            or advertised != len(unique)):
        raise _AdvertisedCountMismatch("Bills", len(unique), advertised)
    return [unique[key] for key in sorted(unique)]


def _bill_source_time(wrapper: dict) -> datetime:
    try:
        value = wrapper["bill"]["lastUpdated"]
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone is required")
        return parsed.astimezone(timezone.utc)
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise ValueError("Bill lastUpdated must be a timezone-aware ISO timestamp") from error


def _published_sponsor_member_graphs(core: CoreStateStore, persons: set[str],
                                     client: FusekiSparqlClient | None = None) -> Graph:
    """Only clean, intact published Member payloads may supply holding evidence.

    A Member observation/ledger decision is not a published OfficeHolding. A
    dirty or pre-migration Member row supplies no tenure for a Bill assertion.
    """
    result = Graph()
    for person in sorted(persons):
        row = core.get_resource("members", person)
        if (row is None or row["publication_state"] != "clean"
                or row["contract_version"] != 3):
            continue
        payload = row["published_payload"]
        expected_hash = row["published_payload_hash"]
        if (not isinstance(payload, str) or not isinstance(expected_hash, str)
                or hashlib.sha256(payload.encode("utf-8")).hexdigest() != expected_hash
                or row["graph_iri"] != expected_graph_iri("members", person)):
            raise ValueError(f"published Member holding evidence cannot be verified: {person}")
        graph = Graph().parse(data=payload, format="nt")
        if client is not None:
            verify_core_graph(client, row["graph_iri"], payload)
        for triple in graph:
            result.add(triple)
    return result


def _accepted_published_sponsor_holdings(core: CoreStateStore,
                                         office_store: OfficeOccurrenceStore,
                                         persons: set[str], registry: dict,
                                         client: FusekiSparqlClient | None = None) -> list[dict]:
    """Corroborate reviewed source-date precision against published Member RDF.

    Member RDF stores xsd:dateTime; a midnight value alone cannot establish
    whether the source reported a date or an instant. The occurrence ledger
    supplies the original precision, but it is never an RDF authority by
    itself: every selected holding, office, person and interval must match the
    intact, clean and (online) remotely verified Member graph exactly.
    """
    from .bill_sponsor_reconciliation import normalize_accepted_member_holdings

    graph = _published_sponsor_member_graphs(core, persons, client)
    rows = office_store.occurrences()
    records: dict[str, dict] = {}
    for row in rows:
        member = row.get("member_iri")
        if member not in persons:
            continue
        key = row["occurrence_key"]
        for resolution in _office_acceptance_history(office_store, row):
            snapshot = resolution.get("snapshot")
            dates = snapshot.get("date_range") if isinstance(snapshot, dict) else None
            if not isinstance(dates, dict):
                continue
            for office in resolution.get("office_iris", []):
                holding = _office_holding_iri(member, key, office)
                if not _prior_office_holding_matches(graph, member, holding, office, dates):
                    continue
                candidate = {"status": "accepted", "member_iri": member,
                             "holding_iri": str(holding), "office_iri": office,
                             "date_range": dates, "occurrence_key": key}
                previous = records.get(str(holding))
                if previous is not None and previous != candidate:
                    raise ValueError(f"conflicting source precision for published holding {holding}")
                records[str(holding)] = candidate
    # No publication-only holding may silently become a Bill reconciliation
    # authority without its reviewed source-date correspondence.
    published = set(graph.subjects(RDF.type, MEMBERS.OfficeHolding))
    if published != {URIRef(value) for value in records}:
        raise ValueError("published OfficeHolding is missing verified source correspondence")
    return normalize_accepted_member_holdings(list(records.values()), registry)


def _published_bill_sponsor_graph(core: CoreStateStore, wrapper: dict,
                                  client: FusekiSparqlClient) -> Graph:
    """Require the exact current source Participation to exist in verified core RDF."""
    bill = wrapper["bill"]
    identity, graph_iri = bill["uri"], bill_graph_iri(bill)
    row = core.get_resource("legislation", identity)
    if (row is None or row["publication_state"] != "clean"
            or row["source_presence"] != "present"
            or row["graph_iri"] != graph_iri or row["contract_version"] != 1
            or row["published_source_hash"] != bill_source_hash(bill)):
        raise ValueError(f"Bill core graph is not published from current source: {identity}")
    payload = row["published_payload"]
    if (not isinstance(payload, str) or not isinstance(row["published_payload_hash"], str)
            or hashlib.sha256(payload.encode("utf-8")).hexdigest() != row["published_payload_hash"]):
        raise ValueError(f"Bill core publication evidence cannot be verified: {identity}")
    graph = Graph().parse(data=payload, format="nt")
    validate_bill(wrapper, graph)
    verify_core_graph(client, graph_iri, payload)
    return graph


def _require_published_sponsor_offices(core: CoreStateStore, registry: dict,
                                       client: FusekiSparqlClient) -> None:
    """Do not link to a reviewed office before its current local owner publishes it."""
    graph = transform_offices(registry)
    validate_offices(registry, graph)
    payload = ntriples(graph)
    row = core.endpoint_publication("offices")
    if (not row or row.get("graph_iri") != OFFICES_GRAPH
            or row.get("publication_state") != "clean"
            or row.get("published_payload_hash") != hashlib.sha256(payload.encode()).hexdigest()
            or row.get("published_payload") != payload):
        raise ValueError("current reviewed office registry must be published before Bill local links")
    verify_core_graph(client, OFFICES_GRAPH, payload)


def _run_bills_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                    run_id: str | None = None, *, window_start: datetime | None = None,
                    upper: datetime | None = None, complete: bool = True) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    raw_root = settings.raw_dir.expanduser().resolve()
    versions = (_run_context(args, run_id=run_id) or {}).get(
        "versions", _run_versions("legislation", settings))
    extraction_id = run_id or str(uuid.uuid4())
    source_run_id = run_id or extraction_id
    evidence: list[dict[str, str]] = []
    report_path: Path | None = None
    last_api_page: tuple[Path, bytes, object] | None = None
    if args.fixture:
        records, body, advertised = _bills_fixture_records(Path(args.fixture))
        observed_at = datetime.now(timezone.utc)
        raw_path, _ = persist_raw(
            root=raw_root, endpoint=str(Path(args.fixture).resolve()),
            params={"skip": 0, "limit": len(records)}, body=body, status=200,
            retrieved_at=observed_at, ontology_version=versions["ontology_version"],
            mapping_version=versions["mapping_version"],
            endpoint_name="legislation", extraction_id=extraction_id)
        _record_raw_page(args, store, endpoint="legislation", run_id=run_id,
                         raw_path=raw_path, raw_root=raw_root, body=body,
                         source_url=None, parameters={"skip": 0, "limit": len(records)},
                         observed_at=observed_at, versions=versions)
        fixture_value = json.loads(body)
        base_pointer = "/results" if isinstance(fixture_value, dict) else ""
        evidence.extend(_raw_contract_pointer(
            raw_path, raw_root, body,
            f"{base_pointer}/{index}" if base_pointer else f"/{index}")
            for index, _ in enumerate(records))
        report_path = raw_path.parent / "source-drift.json"
    else:
        records, advertised = [], None
        query = {"last_updated": window_start.isoformat()} if window_start else None
        client = ApiClient(settings.bills_api_url, retries=settings.retries, timeout=settings.timeout)
        pages = _safe_harvest(args, client, limit=settings.limit,
                              query_params=query)
        for page in pages:
            observed_at = datetime.now(timezone.utc)
            raw_path, _ = persist_raw(
                root=raw_root, endpoint=settings.bills_api_url, params=page.params,
                body=page.body, status=page.status, retrieved_at=observed_at,
                ontology_version=versions["ontology_version"],
                mapping_version=versions["mapping_version"],
                endpoint_name="legislation", extraction_id=extraction_id)
            _record_raw_page(args, store, endpoint="legislation", run_id=run_id,
                             raw_path=raw_path, raw_root=raw_root, body=page.body,
                             source_url=settings.bills_api_url, parameters=page.params,
                             observed_at=observed_at, versions=versions)
            decoded = _decode_api_page(page.body, "Legislation", args)
            envelope_report = _api_envelope_contract(
                args, "legislation", decoded, run_id=source_run_id,
                raw_path=raw_path, raw_root=raw_root, body=page.body,
                count_field="billCount", expected_count=advertised)
            _raise_on_envelope_failure(envelope_report, "Legislation")
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list): raise _RunFailure("every Legislation API page must be an object envelope with a results list")
            count = decoded.get("head", {}).get("counts", {}).get("billCount") if isinstance(decoded.get("head"), dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0: raise _RunFailure("every Legislation API page must contain a nonnegative integer head.counts.billCount")
            if advertised is None: advertised = count
            elif advertised != count: raise _RunFailure("Bills advertised count changed during scan")
            evidence.extend(_raw_contract_pointer(
                raw_path, raw_root, page.body, f"/results/{index}")
                for index in range(len(decoded["results"])))
            report_path = raw_path.parent / "source-drift.json"
            last_api_page = (raw_path, page.body, decoded)
            records.extend(decoded["results"])
    contract_report = _source_contract(
        args, "legislation", records, run_id=source_run_id,
        evidence=evidence, report_path=report_path)
    failed_indices = set(contract_report["failed_record_indices"])
    if contract_report["source_failed"]:
        raise _RunFailure("Legislation source container violates the source contract")
    source_pointers_by_identity = {}
    for index, wrapper in enumerate(records):
        bill = wrapper.get("bill") if isinstance(wrapper, dict) else None
        identity = bill.get("uri") if isinstance(bill, dict) else None
        if isinstance(identity, str):
            source_pointers_by_identity.setdefault(identity, evidence[index])
    retry_candidates = _retry_candidates(store, "legislation")
    retry_candidates_by_hash = _retry_candidates_by_hash(
        store, "legislation") if complete and not args.fixture and not args.offline else {}
    allow_unidentified_retry = complete and not args.fixture and not args.offline
    if failed_indices:
        for index in sorted(failed_indices):
            wrapper = records[index]
            pointer = evidence[index]
            bill = wrapper.get("bill") if isinstance(wrapper, dict) else None
            identity = bill.get("uri") if isinstance(bill, dict) else None
            digest = (bill_source_hash(bill) if isinstance(bill, dict)
                      else hashlib.sha256(json.dumps(
                          wrapper, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), default=str).encode()).hexdigest())
            source_error = "; ".join(
                item["change"] + " at " + item["json_pointer"]
                for item in contract_report["findings"]
                if item.get("severity") == "record" and item.get("record_index") == index)
            page_metadata = json.loads(
                (raw_root / pointer["path"]).with_name(
                    Path(pointer["path"]).name.removesuffix(".json") + ".meta.json")
                .read_text(encoding="utf-8"))
            resource_path = raw_root / pointer["path"]
            _record_quarantine(
                store, endpoint="legislation", run_id=run_id, source_hash=digest,
                observed_at=page_metadata["retrieved_at"],
                evidence_pointer=_raw_resource_pointer(resource_path, pointer["json_pointer"]),
                stage="source_contract", error=source_error or "record violates source contract",
                resource_iri=identity if isinstance(identity, str) else None,
                classification="record_source_contract_failure", versions=versions)
            started = _start_retries(
                store, _retry_rows_for_record(
                    retry_candidates, retry_candidates_by_hash,
                    identity if isinstance(identity, str) else None, digest,
                    include_unidentified=allow_unidentified_retry), run_id)
            _finish_retries(store, started, run_id, success=False,
                            error="record still violates the source contract", args=args)
        _degrade_run(args, error=f"{len(failed_indices)} Bill record(s) failed source contract",
                     classification="record_source_contract_failure")
        records = [record for index, record in enumerate(records) if index not in failed_indices]
    if not complete:
        # The API may interpret last_updated at day granularity and does not
        # guarantee an upper filter. Keep the fixed run boundary locally.
        if advertised is not None and not failed_indices and len(records) != advertised:
            if last_api_page is not None:
                last_path, last_body, last_envelope = last_api_page
                envelope_report = _api_envelope_contract(
                    args, "legislation", last_envelope, run_id=source_run_id,
                    raw_path=last_path, raw_root=raw_root, body=last_body,
                    count_field="billCount", observed_record_count=len(records))
                _raise_on_envelope_failure(envelope_report, "Legislation")
            raise _RunFailure("Legislation incremental extraction count changed during scan")
        records = [record for record in records if _bill_source_time(record) <= upper]
        records = _deduplicate_bills(records, None, allow_empty=True)
    else:
        try:
            records = _deduplicate_bills(
                records, None if failed_indices else advertised,
                allow_empty=bool(
                    (store is not None and complete and advertised == 0)
                    or (failed_indices and not records)))
        except _AdvertisedCountMismatch as error:
            if last_api_page is not None:
                last_path, last_body, last_envelope = last_api_page
                envelope_report = _api_envelope_contract(
                    args, "legislation", last_envelope, run_id=source_run_id,
                    raw_path=last_path, raw_root=raw_root, body=last_body,
                    count_field="billCount", observed_record_count=error.observed)
                _raise_on_envelope_failure(envelope_report, "Legislation")
            raise _RunFailure(
                "Legislation advertised billCount does not match unique observed records",
                scope="source", classification="api_envelope_contract_failure") from error
    work = []
    record_transform_failures = 0
    retry_started_by_identity: dict[str, list[str]] = {}
    for wrapper in records:
        bill = wrapper["bill"]; identity, digest, graph_iri = bill["uri"], bill_source_hash(bill), bill_graph_iri(bill)
        prior = store.get_resource("legislation", identity) if store is not None else None
        pointer = source_pointers_by_identity.get(identity)
        if store is not None and run_id is not None:
            if pointer is None:
                raise RuntimeError(f"Bill {identity} has no immutable raw source pointer")
            metadata = json.loads(
                (raw_root / pointer["path"]).with_name(
                    Path(pointer["path"]).name.removesuffix(".json") + ".meta.json")
                .read_text(encoding="utf-8"))
            old = store.observe_resource(
                "legislation", identity, graph_iri, digest, run_id,
                observed_at=metadata["retrieved_at"],
                evidence_pointer=_raw_resource_pointer(
                    raw_root / pointer["path"], pointer["json_pointer"]),
                request_parameters=metadata["params"], versions=versions,
            )
        else:
            old = {}
        retry_ids = _start_retries(
            store, _retry_rows_for_record(
                retry_candidates, retry_candidates_by_hash, identity, digest,
                include_unidentified=allow_unidentified_retry), run_id)
        if retry_ids:
            retry_started_by_identity[identity] = retry_ids
            context = _run_context(args, run_id=run_id)
            if context is not None:
                context.setdefault("retry_attempts", []).extend(retry_ids)
        # Hash-first source gate; unchanged Bills never construct RDF or invoke a loader.
        try:
            omissions = validate_bill_source(wrapper)
            if (not args.offline and old.get("publication_state") == "clean"
                    and old.get("contract_version") == 1
                    and old.get("published_source_hash") == digest
                    and old.get("graph_iri") == graph_iri):
                work.append((wrapper, None, identity, digest, omissions, "skipped"))
                continue
            graph, report = transform_bill_with_report(wrapper)
            validate_bill(wrapper, graph)
        except Exception as error:
            record_transform_failures += 1
            metadata = (_raw_page_metadata(raw_root, pointer) if pointer is not None else {})
            _record_quarantine(
                store, endpoint="legislation", run_id=run_id, source_hash=digest,
                observed_at=metadata.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
                evidence_pointer=(_raw_resource_pointer(
                    raw_root / pointer["path"], pointer["json_pointer"])
                    if pointer is not None else "unknown-source-pointer"),
                stage="bill_transform", error=f"{type(error).__name__}: {error}",
                resource_iri=identity, classification="record_transform_failure",
                versions=versions)
            _finish_retries(store, retry_ids, run_id, success=False,
                            error=f"{type(error).__name__}: {error}", args=args)
            _degrade_run(args, error=f"Bill {identity} failed transformation: {error}")
            continue
        work.append((wrapper, graph, identity, digest, report,
                     "changed" if prior else "new"))
    if args.output_nq: Path(args.output_nq).write_text("".join(nquads(graph, bill_graph_iri(wrapper["bill"])) for wrapper, graph, *_ in work if graph is not None), encoding="utf-8")
    if getattr(args, "output_ttl", None): Path(args.output_ttl).write_text("\n".join(turtle(graph) for _, graph, *_ in work if graph is not None), encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url); query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint and not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
    published = skipped = 0
    repaired: list[str] = []
    known = store.resources("legislation") if store is not None else []
    seen = {identity for _, _, identity, _, _, _ in work}
    if endpoint:
        if store is None:
            raise RuntimeError("online Bill publication requires durable core ETL state")
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout); client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        context = _run_context(args, run_id=run_id)
        if context is not None:
            context.update(loader=loader, client=client)
            context["safe_publication"] = True
        for wrapper, graph, identity, digest, _, status in work:
            if graph is None:
                prior = store.get_resource("legislation", identity)
                if prior["published_payload"] is not None:
                    try:
                        verify_core_graph(client, prior["graph_iri"], prior["published_payload"])
                    except ValueError:
                        pass
                    else:
                        skipped += 1
                        continue
                graph, _ = transform_bill_with_report(wrapper); validate_bill(wrapper, graph)
                repaired.append(identity)
            graph_iri = bill_graph_iri(wrapper["bill"])
            payload = ntriples(graph)
            payload_hash = store.mark_publication_dirty("legislation", identity, source_hash=digest,
                                                        graph_iri=graph_iri, payload=payload,
                                                        contract_version=1)
            loader.replace(graph_iri, payload, content_type="application/n-triples")
            verify_bill_competency(client, graph_iri, identity, len(graph))
            verify_core_graph(client, graph_iri, payload)
            store.complete_publication("legislation", identity, source_hash=digest,
                                       graph_iri=graph_iri, payload_hash=payload_hash,
                                       contract_version=1)
            published += 1
        for row in known:
            if row["resource_iri"] in seen or row["publication_state"] != "dirty":
                continue
            _replay_missing_dirty("legislation", row, store, loader, client,
                                  verify_bill_competency)
            published += 1
    elif not args.offline: raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    identities = {kind: sorted(identity for _, _, identity, _, _, status in work if status == kind) for kind in ("new", "changed", "skipped")}
    identities["skipped"] = sorted(set(identities["skipped"]) - set(repaired))
    identities["changed"] = sorted(set(identities["changed"]) | set(repaired))
    successful_identities = {identity for _, _, identity, _, _, _status in work}
    for identity, retry_ids in retry_started_by_identity.items():
        if identity in successful_identities:
            _finish_retries(store, retry_ids, run_id, success=True, args=args)
    print(json.dumps({"records": len(records), "published": published, "skipped": skipped, "new": identities["new"], "changed": identities["changed"], "skipped_identities": identities["skipped"], "omitted": [item for *_, report, _ in work for item in report]}, sort_keys=True))
    context = _run_context(args, run_id=run_id)
    if context is not None and endpoint:
        context["safe_publication"] = True
    _set_run_metrics(args, counters={
        "extracted": len(records) + len(failed_indices),
        "changed": len(identities["changed"]),
        "unchanged": len(identities["skipped"]),
        "published_graphs": published,
        "quarantined": len(failed_indices) + record_transform_failures,
        "validation_failures": len(failed_indices) + record_transform_failures,
        "api_requests": 0 if args.fixture else len({pointer["path"] for pointer in evidence}),
        "api_failures": 0, "publication_succeeded": int(bool(endpoint)),
    })
    return 0


def _run_bills(args: argparse.Namespace, store: CoreStateStore | None = None) -> int:
    if store is None:
        return _run_bills_impl(args)
    settings = Settings.from_environment()
    complete = bool(getattr(args, "full", False))
    overlap = int(getattr(args, "overlap_seconds", None) if getattr(args, "overlap_seconds", None) is not None
                  else settings.bills_cursor_overlap_seconds)
    if overlap < 0:
        raise ValueError("Bills cursor overlap must not be negative")
    upper = datetime.now(timezone.utc)
    previous = store.incremental_cursor()
    window_start = (datetime.fromisoformat(previous) - timedelta(seconds=overlap)) if previous and not complete else None
    authoritative_scan = not bool(args.fixture)
    versions = _run_versions("legislation", settings)
    run_id = store.start_run("legislation", ("complete_source_reconciliation" if authoritative_scan
                                                   else "full_refresh") if complete else "incremental_refresh",
                             is_complete=complete and authoritative_scan,
                             parameters={"source": "fixture" if args.fixture else "api",
                                         "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                         "api_url": None if args.fixture else settings.bills_api_url,
                                          "limit": settings.limit, "cursor_before": previous,
                                          "window_start": window_start.isoformat() if window_start else None,
                                          "upper_boundary": upper.isoformat(), "overlap_seconds": overlap,
                                          "complete": complete}, versions=versions)
    _begin_run_context(args, run_id, "legislation", versions)
    context = _run_context(args, run_id=run_id)
    context["incremental_cursor"] = (
        upper.isoformat() if authoritative_scan and not complete else None)
    context["complete_scan"] = complete and authoritative_scan
    try:
        result = _run_bills_impl(args, store, run_id, window_start=window_start,
                                 upper=upper, complete=complete)
        context = _run_context(args, run_id=run_id)
        _finalize_run(store, args, run_id=run_id, endpoint="legislation",
                      versions=versions,
                      loader=context.get("loader") if context else None,
                      client=context.get("client") if context else None)
    except Exception as error:
        context = _run_context(args, run_id=run_id)
        if (context is not None and not context.get("finished")
                and not context.get("catalog_state_unresolved")):
            scope = getattr(error, "scope", "system")
            classification = getattr(error, "classification", "system_failure")
            _record_fatal_run(
                store, args, run_id=run_id, endpoint="legislation", error=error,
                failure_scope=scope, failure_classification=classification)
        raise
    return result


def run_bills(args: argparse.Namespace) -> int:
    if args.offline:
        return _run_bills_impl(args)
    settings = Settings.from_environment()
    state_db = Path(getattr(args, "state_db", None) or settings.core_state_db_file).expanduser()
    legacy_bills = _legacy_override(args) or settings.bills_legacy_state_file
    with state_lock(state_db):
        with CoreStateStore(state_db, legacy_members=settings.members_legacy_state_file,
                            legacy_bills=legacy_bills) as store:
            return _run_bills(args, store)


def _load_debate_sources(raw_root: Path, source_urls: list[str],
                         replay_hashes: list[str], settings: Settings, *,
                         on_source=None, on_api_failure=None):
    sources = []
    for digest in replay_hashes:
        source = load_main_xml(raw_root, digest)
        sources.append(source)
        if on_source is not None:
            on_source(source)
    for source_url in source_urls:
        try:
            body, final_url = fetch_main_xml(
                source_url, retries=settings.retries, timeout=settings.timeout)
            source = persist_main_xml(raw_root, body, final_url)
        except DebateSourceError:
            if on_api_failure is not None:
                on_api_failure()
            raise
        sources.append(source)
        if on_source is not None:
            on_source(source)
    return sources


def _write_debate_outputs(outcomes, args: argparse.Namespace) -> None:
    publishable = [item for item in outcomes if item.status != "quarantined"]
    if args.output_nq:
        Path(args.output_nq).write_text(
            "".join(nquads(item.graph, item.graph_iri) for item in publishable),
            encoding="utf-8")
    if args.output_ttl:
        Path(args.output_ttl).write_text(
            "\n".join(turtle(item.graph) for item in publishable),
            encoding="utf-8")


def _debate_result(outcomes, *, run_id: str | None, published: bool,
                   outcome: str | None = None,
                   failure_scope: str | None = None,
                   failure_classification: str | None = None) -> int:
    quarantined = [item for item in outcomes if item.status == "quarantined"]
    published_items = [item for item in outcomes if item.status != "quarantined"]
    outcome = outcome or ("degraded" if quarantined else "success")
    summary = {
        "batch_size": len(published_items) + len(quarantined),
        "changed": sum(item.status == "changed" for item in published_items),
        "new": sum(item.status == "new" for item in published_items),
        "published": published,
        "quarantined": len(quarantined),
        "outcome": outcome,
        "failure_scope": failure_scope or ("record" if quarantined else None),
        "failure_classification": (failure_classification
                                    or ("record_processing_failure" if quarantined else None)),
        "run_id": run_id,
        "skipped": sum(item.status == "skipped" for item in published_items),
        "work_records": [
            {"graph_iri": item.graph_iri, "source_sha256": item.source_sha256,
             "status": item.status, "triples": item.triples,
             "work_iri": item.work_iri,
             **({"failure_stage": item.failure_stage,
                 "failure_classification": item.failure_classification,
                 "error": item.error} if item.status == "quarantined" else {})}
            for item in outcomes
        ],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


def run_debates(args: argparse.Namespace) -> int:
    """Transform a finite caller-supplied AKN batch; publication is opt-in."""
    settings = Settings.from_environment()
    raw_root = Path(args.raw_dir or settings.raw_dir).expanduser()
    source_urls = list(dict.fromkeys(getattr(args, "source_url", None) or []))
    replay_hashes = list(dict.fromkeys(getattr(args, "replay", None) or []))
    if getattr(args, "fixture", None):
        raise ValueError("Debates use explicit --source-url acquisition or exact --replay hashes, not generic JSON fixtures")
    if not source_urls and not replay_hashes:
        raise ValueError("run debates requires at least one --source-url or --replay SHA-256")
    if args.offline and source_urls:
        raise ValueError("--offline Debates runs can replay preserved hashes but cannot acquire source URLs")
    if args.offline and getattr(args, "publish", False):
        raise ValueError("--offline and --publish are mutually exclusive")

    if not getattr(args, "publish", False):
        # Default behavior has no access to a GSP loader and does not open Core
        # State for writing. Both online acquisition and exact offline replay
        # preserve/validate sources and emit local RDF only.
        sources = _load_debate_sources(raw_root, source_urls, replay_hashes, settings)
        outcomes = run_debate_batch(sources)
        _write_debate_outputs(outcomes, args)
        return _debate_result(outcomes, run_id=None, published=False)

    database = Path(getattr(args, "state_db", None) or settings.core_state_db_file).expanduser()
    gsp_endpoint = getattr(args, "fuseki_gsp_url", None) or settings.fuseki_gsp_url
    sparql_endpoint = getattr(args, "fuseki_sparql_url", None) or settings.fuseki_sparql_url
    if not gsp_endpoint or not sparql_endpoint:
        raise ValueError("--publish requires both Fuseki GSP and SPARQL verification endpoints")
    versions = _run_versions("debates", settings)
    with state_lock(database):
        with CoreStateStore(database, legacy_members=settings.members_legacy_state_file,
                            legacy_bills=settings.bills_legacy_state_file) as store:
            run_id = store.start_run(
                "debates", "incremental_refresh", is_complete=False,
                parameters={
                    "source": "explicit-akn-main-xml-batch",
                    "source_urls": source_urls,
                    "replay_sha256": replay_hashes,
                    "raw_root": str(raw_root.resolve()),
                    "supplied_count": len(source_urls) + len(replay_hashes),
                }, versions=versions,
            )
            _begin_run_context(args, run_id, "debates", versions)
            try:
                # Evidence is persisted before source validation or RDF work.
                _set_run_metrics(args, counters={
                    "api_requests": len(source_urls), "api_failures": 0})
                extracted = 0
                api_failures = 0

                def record_observation(source) -> None:
                    nonlocal extracted
                    observed_at = datetime.now(timezone.utc).isoformat()
                    store.record_source_observation(
                        "debates", source.source_sha256, observed_at,
                        run_id=run_id,
                        evidence_pointer=source.raw_path.resolve().as_uri(),
                        source_url=(source.source_urls[0] if source.source_urls else None),
                        request_parameters={
                            "source": "explicit-akn-main-xml-batch",
                            "source_sha256": source.source_sha256,
                        },
                        versions=versions,
                    )
                    extracted += 1
                    _set_run_metrics(args, counters={"extracted": extracted})

                def record_api_failure() -> None:
                    nonlocal api_failures
                    api_failures += 1
                    _set_run_metrics(args, counters={"api_failures": api_failures})

                sources = _load_debate_sources(
                    raw_root, source_urls, replay_hashes, settings,
                    on_source=record_observation, on_api_failure=record_api_failure)
                _set_run_metrics(args, counters={
                    "changed": 0, "unchanged": 0,
                    "quarantined": 0, "validation_failures": 0,
                })
                loader = FusekiGraphStoreLoader(
                    gsp_endpoint, user=settings.fuseki_user,
                    password=settings.fuseki_password, timeout=settings.timeout)
                client = FusekiSparqlClient(
                    sparql_endpoint, user=settings.fuseki_user,
                    password=settings.fuseki_password, timeout=settings.timeout)
                context = _run_context(args, run_id=run_id)
                if context is not None:
                    context.update(loader=loader, client=client, safe_publication=True)
                retry_candidates = _retry_candidates(store, "debates")
                retry_candidates_by_hash = _retry_candidates_by_hash(store, "debates")
                sources_by_hash = {source.source_sha256: source for source in sources}
                quarantined_count = 0
                started_retry_ids: set[str] = set()

                def start_debate_retries(rows: list[dict]) -> list[str]:
                    eligible = [row for row in rows
                                if row["quarantine_id"] not in started_retry_ids]
                    retry_ids = _start_retries(store, eligible, run_id)
                    started_retry_ids.update(retry_ids)
                    return retry_ids

                def persist_debate_failure(item) -> None:
                    nonlocal quarantined_count
                    source = sources_by_hash[item.source_sha256]
                    retry_rows = _retry_rows_for_record(
                        retry_candidates, retry_candidates_by_hash,
                        item.work_iri, item.source_sha256,
                        include_unidentified=True)
                    retry_ids = start_debate_retries(retry_rows)
                    if retry_ids:
                        active_context = _run_context(args, run_id=run_id)
                        if active_context is not None:
                            active_context.setdefault("retry_attempts", []).extend(retry_ids)
                    store.record_quarantine(
                        "debates", run_id=run_id,
                        source_hash=item.source_sha256,
                        observed_at=datetime.now(timezone.utc).isoformat(),
                        evidence_pointer=source.raw_path.resolve().as_uri(),
                        stage=item.failure_stage or "debate_record_processing",
                        error=item.error or "Debate source failed processing",
                        resource_iri=item.work_iri,
                        failure_classification=(item.failure_classification
                                                 or "record_transform_failure"),
                        etl_version=versions.get("etl_version"),
                        ontology_version=versions.get("ontology_version"),
                        mapping_version=versions.get("mapping_version"),
                    )
                    _json_log(
                        "record_quarantined", run_id=run_id, endpoint="debates",
                        resource_iri=item.work_iri,
                        source_sha256=item.source_sha256,
                        stage=item.failure_stage,
                        classification=item.failure_classification)
                    _finish_retries(
                        store, retry_ids, run_id, success=False,
                        error=item.error, args=args)
                    quarantined_count += 1
                    _set_run_metrics(args, counters={
                        "quarantined": quarantined_count,
                        "validation_failures": quarantined_count,
                    })
                    _degrade_run(
                        args, error=f"{quarantined_count} Debate record(s) quarantined",
                        classification="record_processing_failure")

                outcomes = run_debate_batch(
                    sources, store=store, run_id=run_id, publish=True,
                    loader=loader, client=client,
                    on_record_failure=persist_debate_failure,
                )
                _write_debate_outputs(outcomes, args)
                for item in outcomes:
                    if item.status == "quarantined":
                        continue
                    retry_rows = _retry_rows_for_record(
                        retry_candidates, retry_candidates_by_hash,
                        item.work_iri, item.source_sha256,
                        include_unidentified=True)
                    retry_ids = start_debate_retries(retry_rows)
                    if retry_ids:
                        context = _run_context(args, run_id=run_id)
                        if context is not None:
                            context.setdefault("retry_attempts", []).extend(retry_ids)
                    _finish_retries(store, retry_ids, run_id, success=True, args=args)
                context = _run_context(args, run_id=run_id)
                _set_run_metrics(args, counters={
                    "extracted": len(sources),
                    "changed": sum(item.status == "changed" for item in outcomes),
                    "unchanged": sum(item.status == "skipped" for item in outcomes),
                    "published_graphs": sum(
                        item.status not in {"skipped", "quarantined"} for item in outcomes),
                    "quarantined": quarantined_count,
                    "validation_failures": quarantined_count,
                    "api_requests": len(source_urls), "api_failures": api_failures,
                    "publication_succeeded": 1})
                _finalize_run(store, args, run_id=run_id, endpoint="debates",
                              versions=versions, loader=loader, client=client)
            except Exception as error:
                context = _run_context(args, run_id=run_id)
                if (context is not None and not context.get("finished")
                        and not context.get("catalog_state_unresolved")):
                    scope = "source" if isinstance(error, DebateSourceError) else "system"
                    classification = ("debate_source_failure" if scope == "source"
                                      else "system_failure")
                    _record_fatal_run(
                        store, args, run_id=run_id, endpoint="debates", error=error,
                        failure_scope=scope,
                        failure_classification=classification)
                raise
    context = _run_context(args, run_id=run_id) or {}
    return _debate_result(
        outcomes, run_id=run_id, published=True,
        outcome=context.get("outcome"),
        failure_scope=context.get("failure_scope"),
        failure_classification=context.get("failure_classification"))


class _FixtureWikidataClient:
    """Offline, deterministic response adapter for reconciliation tests/runs."""
    def __init__(self, data):
        try:
            wikidata = data["wikidata"]
            if not isinstance(wikidata, dict) or not isinstance(wikidata["p4690"], dict) or not isinstance(wikidata["entities"], dict):
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid reconciliation response fixture Wikidata schema") from error
        self.data = wikidata
    def lookup_member_code(self, code):
        if code not in self.data["p4690"]: raise FixtureResponseError("response fixture lacks Wikidata P4690 entry for " + code)
        return self.data["p4690"][code]
    def entity(self, qid):
        if qid not in self.data["entities"]: raise FixtureResponseError("response fixture lacks Wikidata entity for " + qid)
        return self.data["entities"][qid]

class _FixtureDbpediaClient:
    def __init__(self, data):
        try:
            values = data["dbpedia"]["by_wikidata"]
            if not isinstance(values, dict): raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid reconciliation response fixture DBpedia schema") from error
        self.data = values
    def resolve_wikidata(self, qid):
        if qid not in self.data: raise FixtureResponseError("response fixture lacks DBpedia entry for " + qid)
        return self.data[qid]


def _validate_fixture_responses(data: object, records: list[dict], decisions: dict[str, dict]) -> None:
    """Reject incomplete offline evidence before state is opened or changed."""
    wikidata_client = _FixtureWikidataClient(data)
    wikidata = wikidata_client.data
    dbpedia = _FixtureDbpediaClient(data).data
    for wrapper in records:
        code = wrapper["member"]["memberCode"]
        decision = decisions.get(code)
        if decision and decision["status"] == "rejected":
            continue
        if decision and decision["status"] == "accepted":
            qids = [decision["wikidata"]]
            for qid in qids:
                if qid not in wikidata["entities"] or qid not in dbpedia:
                    raise ValueError("response fixture lacks downstream entry for " + qid)
                entity, target_error = _fetch_wikidata_target(wikidata_client, qid)
                if target_error is not None:
                    raise ValueError("response fixture has invalid Wikidata entity for reviewed QID " + qid)
                _enwiki(entity)
            continue
        if code not in wikidata["p4690"] or not isinstance(wikidata["p4690"][code], list):
            raise ValueError("response fixture lacks valid Wikidata P4690 entry for " + code)
        candidates = wikidata["p4690"][code]
        if any(not valid_qid(value) for value in candidates):
            raise ValueError("response fixture has invalid Wikidata QID for " + code)
        for qid in candidates:
            if qid not in wikidata["entities"] or qid not in dbpedia:
                raise ValueError("response fixture lacks downstream entry for " + qid)


def _party_fixture_records(path: Path) -> tuple[list[dict], bytes, int | None]:
    body = path.read_bytes()
    value = json.loads(body)
    if isinstance(value, dict) and isinstance(value.get("party"), dict):
        return [value], body, None
    if isinstance(value, dict):
        records = value.get("results")
        counts = value.get("head", {}).get("counts", {}) if isinstance(value.get("head"), dict) else {}
        advertised = counts.get("partyCount") if isinstance(counts, dict) else None
    else:
        records, advertised = value, None
    if not isinstance(records, list):
        raise ValueError("Parties fixture must be a Party wrapper, array, or results envelope")
    return records, body, advertised


class _FixturePartyWikidataClient:
    """Offline fixture adapter keyed by complete term-scoped Party source IRI."""
    def __init__(self, data):
        try:
            if not isinstance(data, dict) or set(data) != {"wikidata"}:
                raise ValueError
            wikidata = data["wikidata"]
            if (not isinstance(wikidata, dict)
                    or set(wikidata) not in ({"party_candidates"}, {"party_candidates", "entities"})):
                raise ValueError
            values = wikidata["party_candidates"]
            if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
                raise ValueError
            entities = wikidata.get("entities", {})
            if not isinstance(entities, dict) or any(not valid_qid(qid) for qid in entities):
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid Party reconciliation response fixture schema") from error
        self.data = values
        self.entities = entities

    def lookup_party_candidates(self, wrapper):
        local_iri = wrapper["party"]["uri"]
        if local_iri not in self.data:
            raise FixtureResponseError("response fixture lacks Party candidate entry for " + local_iri)
        return self.data[local_iri]

    def entity(self, qid):
        if qid not in self.entities:
            raise FixtureResponseError("response fixture lacks Wikidata entity for reviewed QID " + qid)
        return self.entities[qid]


def _validate_party_fixture_responses(data: object, records: list[dict], decisions: dict[str, dict]) -> None:
    client = _FixturePartyWikidataClient(data)
    eligible = {wrapper["party"]["uri"]: wrapper for wrapper in records if wrapper["party"]["partyCode"] != "Independent"}
    unknown = sorted(set(client.data) - set(eligible))
    if unknown:
        raise ValueError("response fixture contains unknown or Independent Party IRI: " + ", ".join(unknown))
    entities_required = set()
    for local_iri, wrapper in eligible.items():
        decision = decisions.get(local_iri)
        if decision is not None:
            if decision["status"] == "accepted":
                qid = decision["wikidata"]
                entities_required.add(qid)
                if qid not in client.entities:
                    raise ValueError("response fixture lacks Wikidata entity for reviewed QID " + qid)
                entity, target_error = _fetch_wikidata_target(client, qid)
                if target_error is not None:
                    raise ValueError("response fixture has invalid Wikidata entity for reviewed QID " + qid)
                _enwiki(entity)  # validates any supplied sitelink
            continue
        if local_iri not in client.data or not isinstance(client.data[local_iri], list):
            raise ValueError("response fixture lacks valid Party candidate entry for " + local_iri)
        party = wrapper["party"]
        query_terms = {party["partyCode"], party["partyCode"].replace("_", " "), party["showAs"]}
        seen = set()
        for raw in client.data[local_iri]:
            candidate = normalize_party_candidate(raw)
            if candidate["qid"] in seen:
                raise ValueError("response fixture contains duplicate Party candidate QID for " + local_iri)
            if not set(candidate["matched_on"]) <= query_terms:
                raise ValueError("response fixture candidate matched an unknown Party label for " + local_iri)
            labels = {label.casefold() for label in candidate["labels"]}
            if any(label.casefold() not in labels for label in candidate["matched_on"]):
                raise ValueError("response fixture candidate lacks its matched label for " + local_iri)
            seen.add(candidate["qid"])
    unknown_entities = sorted(set(client.entities) - entities_required)
    if unknown_entities:
        raise ValueError("response fixture contains unrequested Wikidata entities: " + ", ".join(unknown_entities))


def _institution_fixture_records(path: Path) -> list[dict]:
    """Read an optional v1 list of local institution IRIs for scoped runs."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid institution identity fixture: " + str(error)) from error
    if (not isinstance(value, dict) or set(value) != {"version", "institutions"}
            or type(value.get("version")) is not int or value["version"] != 1
            or not isinstance(value.get("institutions"), list)):
        raise ValueError("institution identity fixture must contain only version 1 and an institutions array")
    if any(not isinstance(local_iri, str) for local_iri in value["institutions"]):
        raise ValueError("institution identity fixture entries must be full local IRIs")
    return deduplicate_institution_records([{"institution": {"uri": local_iri}}
                                            for local_iri in value["institutions"]])


class _FixtureInstitutionWikidataClient:
    """Offline institution candidate and reviewed-sitelink fixture seam."""
    def __init__(self, data):
        try:
            if not isinstance(data, dict) or set(data) != {"wikidata"}:
                raise ValueError
            wikidata = data["wikidata"]
            if (not isinstance(wikidata, dict)
                    or set(wikidata) != {"institution_candidates", "entities"}
                    or not isinstance(wikidata["institution_candidates"], dict)
                    or not isinstance(wikidata["entities"], dict)):
                raise ValueError
            if any(not isinstance(local_iri, str) for local_iri in wikidata["institution_candidates"]):
                raise ValueError
            if any(not valid_qid(qid) for qid in wikidata["entities"]):
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid institutional reconciliation response fixture schema") from error
        self.candidates = wikidata["institution_candidates"]
        self.entities = wikidata["entities"]

    def lookup_institution_candidates(self, entity):
        local_iri = entity["uri"]
        if local_iri not in self.candidates:
            raise FixtureResponseError("response fixture lacks institutional candidate entry for " + local_iri)
        return self.candidates[local_iri]

    def entity(self, qid):
        if qid not in self.entities:
            raise FixtureResponseError("response fixture lacks Wikidata entity for reviewed QID " + qid)
        return self.entities[qid]


def _validate_institution_fixture_responses(data: object, records: list[dict], decisions: dict[str, dict]) -> None:
    """Validate all offline evidence before opening the shared SQLite store."""
    client = _FixtureInstitutionWikidataClient(data)
    local_iris = {record["institution"]["uri"] for record in records}
    unknown = sorted(set(client.candidates) - local_iris)
    if unknown:
        raise ValueError("response fixture contains unknown institutional IRI: " + ", ".join(unknown))
    stale = sorted(set(decisions) - local_iris)
    if stale:
        raise ValueError("institutional review decisions do not match current input: " + ", ".join(stale))
    entities_required = set()
    for local_iri in sorted(local_iris):
        decision = decisions.get(local_iri)
        if decision is not None:
            if decision["status"] == "accepted":
                qid = decision["wikidata"]
                entities_required.add(qid)
                if qid not in client.entities:
                    raise ValueError("response fixture lacks Wikidata entity for reviewed QID " + qid)
                entity, target_error = _fetch_wikidata_target(client, qid)
                if target_error is not None:
                    raise ValueError("response fixture has invalid Wikidata entity for reviewed QID " + qid)
                if "wikipedia" in decision:
                    _enwiki(entity)
            continue
        if local_iri not in client.candidates or not isinstance(client.candidates[local_iri], list):
            raise ValueError("response fixture lacks valid institutional candidate entry for " + local_iri)
        seen = set()
        for raw in client.candidates[local_iri]:
            candidate = _normalize_institution_candidate_for(local_iri, raw)
            if candidate["qid"] in seen:
                raise ValueError("response fixture contains duplicate institutional candidate QID for " + local_iri)
            _institution_candidate_negative_evidence(local_iri, candidate)
            seen.add(candidate["qid"])
    unknown_entities = sorted(set(client.entities) - entities_required)
    if unknown_entities:
        raise ValueError("response fixture contains unrequested Wikidata entities: " + ", ".join(unknown_entities))


def run_reconcile_members(args: argparse.Namespace) -> int:
    if args.offline:
        if not args.fixture or not args.responses_file:
            raise ValueError("--offline reconciliation requires --fixture and --responses-file")
        if args.publish:
            raise ValueError("--offline reconciliation forbids --publish")
    if args.fixture:
        records, _, advertised = _members_fixture_records(Path(args.fixture))
        last_api_page = None
    else:
        settings = Settings.from_environment()
        records, advertised, last_api_page, raw_root, source_run_id = _capture_api_pages(
            args, "members", settings.members_api_url, settings,
            count_field="memberCount")
    try:
        records = _deduplicate_members(records, advertised)
    except _AdvertisedCountMismatch as error:
        if last_api_page is not None:
            raw_path, body, decoded = last_api_page
            report = _api_envelope_contract(
                args, "members", decoded, run_id=source_run_id,
                raw_path=raw_path, raw_root=raw_root, body=body,
                count_field="memberCount", observed_record_count=error.observed)
            _raise_on_envelope_failure(report, "Members")
        raise
    decisions, review_hash = load_review(Path(args.review_file or "reconciliation/member-decisions.json"))
    if args.responses_file:
        data = json.loads(Path(args.responses_file).read_text(encoding="utf-8"))
        _validate_fixture_responses(data, records, decisions)
        wikidata, dbpedia = _FixtureWikidataClient(data), _FixtureDbpediaClient(data)
    else:
        wikidata, dbpedia = WikidataClient(timeout=Settings.from_environment().timeout), DbpediaClient(timeout=Settings.from_environment().timeout)
    settings = Settings.from_environment()
    store = ReconciliationStore(_reconciliation_state_path(args, settings))
    try:
        loader = None
        publication_count = 0
        competency_client = None
        if args.publish:
            settings = Settings.from_environment(); endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
            if not endpoint: raise ValueError("--publish requires a Fuseki GSP endpoint")
            query_endpoint = args.fuseki_sparql_url or settings.fuseki_sparql_url
            if not query_endpoint: raise ValueError("--publish requires a Fuseki SPARQL endpoint for competency verification")
            upstream_loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
            class CountingLoader:
                def replace(self, *replace_args, **replace_kwargs):
                    nonlocal publication_count
                    publication_count += 1
                    return upstream_loader.replace(*replace_args, **replace_kwargs)
            loader = CountingLoader()
            competency_client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        results = reconcile_records(records, store, decisions, review_hash, wikidata, dbpedia, all_records=args.all, publish=loader, competency_client=competency_client)
        if args.output_nq:
            Path(args.output_nq).write_text("".join(nquads(graph, external_graph_iri(member)) for member, _, graph in results), encoding="utf-8")
        summary = {state: sum(r.state == state for _, r, _ in results) for state in ("accepted", "rejected", "ambiguous", "pending")}
        enrichment = {status: sum(r.enrichment_status == status for _, r, _ in results) for status in ("complete", "retry", "ambiguous", "unresolved")}
        unresolved = sum(result.state in {"pending", "ambiguous"} or result.enrichment_status in {"retry", "ambiguous", "unresolved"} for _, result, _ in results)
        unresolved_members = sorted(member["memberCode"] for member, result, _ in results
                                    if result.state in {"pending", "ambiguous"}
                                    or result.enrichment_status in {"retry", "ambiguous", "unresolved"})
        print(json.dumps({"processed":len(results), "published":publication_count,
                          "unresolved":unresolved, "unresolved_members":unresolved_members,
                          "enrichment":enrichment, **summary}, sort_keys=True))
        return 1 if unresolved else 0
    finally: store.close()


def run_reconcile_parties(args: argparse.Namespace) -> int:
    """Candidate-generate and publish only reviewed Party relationships."""
    if args.offline:
        if not args.fixture or not args.responses_file:
            raise ValueError("--offline Party reconciliation requires --fixture and --responses-file")
        if args.publish:
            raise ValueError("--offline Party reconciliation forbids --publish")
    if args.fixture:
        records, _, advertised = _party_fixture_records(Path(args.fixture))
        last_api_page = None
    else:
        settings = Settings.from_environment()
        records, advertised, last_api_page, raw_root, source_run_id = _capture_api_pages(
            args, "parties", settings.parties_api_url, settings,
            count_field="partyCount")
    try:
        records = deduplicate_party_records(records, advertised)
    except ValueError as error:
        count_mismatch = ("unique count" in str(error)
                          and "does not match advertised count" in str(error))
        if last_api_page is not None and count_mismatch:
            unique_count = len({wrapper["party"]["uri"] for wrapper in records})
            raw_path, body, decoded = last_api_page
            report = _api_envelope_contract(
                args, "parties", decoded, run_id=source_run_id,
                raw_path=raw_path, raw_root=raw_root, body=body,
                count_field="partyCount", observed_record_count=unique_count)
            _raise_on_envelope_failure(report, "Parties")
        raise
    decisions, review_hash = load_party_review(Path(args.review_file or "reconciliation/party-decisions.json"))
    if args.responses_file:
        data = json.loads(Path(args.responses_file).read_text(encoding="utf-8"))
        _validate_party_fixture_responses(data, records, decisions)
        wikidata = _FixturePartyWikidataClient(data)
    elif args.offline:
        raise ValueError("--offline Party reconciliation requires --responses-file")
    else:
        wikidata = WikidataClient(timeout=Settings.from_environment().timeout)
    settings = Settings.from_environment()
    store = ReconciliationStore(_reconciliation_state_path(args, settings))
    try:
        loader = None
        publication_count = 0
        competency_client = None
        if args.publish:
            settings = Settings.from_environment()
            endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
            if not endpoint:
                raise ValueError("--publish requires a Fuseki GSP endpoint")
            query_endpoint = args.fuseki_sparql_url or settings.fuseki_sparql_url
            if not query_endpoint:
                raise ValueError("--publish requires a Fuseki SPARQL endpoint for whole-graph verification")
            upstream_loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
            class CountingLoader:
                def replace(self, *replace_args, **replace_kwargs):
                    nonlocal publication_count
                    publication_count += 1
                    return upstream_loader.replace(*replace_args, **replace_kwargs)
            loader = CountingLoader()
            competency_client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        results = reconcile_party_records(records, store, decisions, review_hash, wikidata,
                                          all_records=args.all, publish=loader,
                                          competency_client=competency_client)
        if args.output_nq:
            Path(args.output_nq).write_text("".join(nquads(graph, party_external_graph_iri(wrapper)) for wrapper, _, graph in results), encoding="utf-8")
        summary = {state: sum(result.state == state for _, result, _ in results) for state in ("accepted", "rejected", "ambiguous", "pending")}
        unresolved_records = sorted(wrapper["party"]["uri"] for wrapper, result, _ in results
                                   if result.state in {"pending", "ambiguous"}
                                   or result.enrichment_status in {"retry", "ambiguous", "unresolved"})
        print(json.dumps({"processed": len(results), "excluded_independent": sum(wrapper["party"]["partyCode"] == "Independent" for wrapper in records),
                          "published": publication_count, "unresolved": len(unresolved_records),
                          "unresolved_parties": unresolved_records, **summary}, sort_keys=True))
        return 1 if unresolved_records else 0
    finally:
        store.close()


def run_reconcile_institutions(args: argparse.Namespace) -> int:
    """Reconcile the three fixed enduring institutions through generic state."""
    if args.offline:
        if not args.responses_file:
            raise ValueError("--offline institutional reconciliation requires --responses-file")
        if args.publish:
            raise ValueError("--offline institutional reconciliation forbids --publish")
    records = _institution_fixture_records(Path(args.fixture)) if args.fixture else institution_records()
    records = deduplicate_institution_records(records)
    decisions, review_hash = load_institution_review(Path(args.review_file or "reconciliation/institution-decisions.json"))
    stale = sorted(set(decisions) - {record["institution"]["uri"] for record in records})
    if stale:
        raise ValueError("institutional review decisions do not match current input: " + ", ".join(stale))
    if args.responses_file:
        data = json.loads(Path(args.responses_file).read_text(encoding="utf-8"))
        _validate_institution_fixture_responses(data, records, decisions)
        wikidata = _FixtureInstitutionWikidataClient(data)
    elif args.offline:
        raise ValueError("--offline institutional reconciliation requires --responses-file")
    else:
        wikidata = WikidataClient(timeout=Settings.from_environment().timeout)

    settings = Settings.from_environment()
    store = ReconciliationStore(_reconciliation_state_path(args, settings))
    try:
        loader = None
        publication_count = 0
        competency_client = None
        if args.publish:
            settings = Settings.from_environment()
            endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
            if not endpoint:
                raise ValueError("--publish requires a Fuseki GSP endpoint")
            query_endpoint = args.fuseki_sparql_url or settings.fuseki_sparql_url
            if not query_endpoint:
                raise ValueError("--publish requires a Fuseki SPARQL endpoint for whole-graph verification")
            upstream_loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user,
                                                     password=settings.fuseki_password, timeout=settings.timeout)
            class CountingLoader:
                def replace(self, *replace_args, **replace_kwargs):
                    nonlocal publication_count
                    publication_count += 1
                    return upstream_loader.replace(*replace_args, **replace_kwargs)
            loader = CountingLoader()
            competency_client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user,
                                                   password=settings.fuseki_password, timeout=settings.timeout)
        results = reconcile_institution_records(records, store, decisions, review_hash, wikidata,
                                                all_records=args.all, publish=loader,
                                                competency_client=competency_client)
        if args.output_nq:
            Path(args.output_nq).write_text("".join(
                nquads(graph, institution_external_graph_iri(entity))
                for entity, _, graph in results), encoding="utf-8")
        summary = {state: sum(result.state == state for _, result, _ in results)
                   for state in ("accepted", "rejected", "ambiguous", "pending")}
        unresolved = sorted(entity["uri"] for entity, result, _ in results
                            if result.state in {"pending", "ambiguous"}
                            or result.enrichment_status in {"retry", "ambiguous", "unresolved"})
        excluded_candidates = sum(len(result.evidence.get("excluded_candidates", []))
                                  for _, result, _ in results if isinstance(result.evidence, dict))
        print(json.dumps({"processed": len(results), "published": publication_count,
                          "unresolved": len(unresolved), "unresolved_institutions": unresolved,
                          "excluded_candidates": excluded_candidates, **summary}, sort_keys=True))
        return 1 if unresolved else 0
    finally:
        store.close()


def _external_office_local_iri(record: dict) -> str:
    """Read a policy record's registered local identity without using its label."""
    containers = [record]
    containers.extend(record.get(name) for name in ("office", "named_office", "entity")
                      if isinstance(record.get(name), dict))
    for value in containers:
        for name in ("uri", "local_iri", "office_iri"):
            iri = value.get(name)
            if isinstance(iri, str):
                return iri
        key = value.get("key")
        if isinstance(key, str):
            return str(office_iri(key))
    raise ValueError("external office record has no registered local office identity")


def _unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _office_external_fixture_scope(path: Path, registry: dict) -> tuple[dict, list[dict]]:
    """Select registered offices from a strict v1 local-identity fixture."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"),
                           object_pairs_hook=_unique_json_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid external office identity fixture: " + str(error)) from error
    if (not isinstance(value, dict) or set(value) != {"version", "offices"}
            or type(value.get("version")) is not int or value["version"] != 1
            or not isinstance(value.get("offices"), list)
            or not value["offices"]
            or any(not isinstance(iri, str) for iri in value["offices"])):
        raise ValueError("external office identity fixture must contain only version 1 and a non-empty offices array of full local IRIs")

    by_iri = {str(office_iri(office["key"])): office
              for office in registry["offices"]}
    requested = value["offices"]
    if len(requested) != len(set(requested)):
        raise ValueError("external office identity fixture contains duplicate local IRIs")
    unknown = sorted(set(requested) - set(by_iri))
    if unknown:
        raise ValueError("external office identity fixture contains unregistered local IRI: "
                         + ", ".join(unknown))

    selected = {**registry,
                "offices": [office for office in registry["offices"]
                            if str(office_iri(office["key"])) in set(requested)]}
    return selected, deduplicate_external_office_records(
        office_external_records(selected))


class _FixtureExternalOfficeWikidataClient:
    """Strict offline candidate/accepted-target fixtures for registered offices."""
    def __init__(self, data):
        try:
            if (not isinstance(data, dict) or set(data) != {"wikidata"}
                    or not isinstance(data["wikidata"], dict)
                    or set(data["wikidata"]) != {"office_candidates", "entities"}
                    or not isinstance(data["wikidata"]["office_candidates"], dict)
                    or not isinstance(data["wikidata"]["entities"], dict)):
                raise ValueError
            candidates = data["wikidata"]["office_candidates"]
            entities = data["wikidata"]["entities"]
            if (any(not isinstance(local_iri, str) for local_iri in candidates)
                    or any(not valid_qid(qid) for qid in entities)):
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid external office reconciliation response fixture schema") from error
        self.candidates = candidates
        self.entities = entities

    def lookup_office_candidates(self, record, registry):
        del registry  # records were validated against the same scoped registry before use
        local_iri = _external_office_local_iri(record)
        if local_iri not in self.candidates:
            raise FixtureResponseError(
                "response fixture lacks office candidate entry for " + local_iri)
        return self.candidates[local_iri]

    def entity(self, qid):
        if qid not in self.entities:
            raise FixtureResponseError(
                "response fixture lacks Wikidata entity for reviewed office QID " + qid)
        return self.entities[qid]


def _validate_external_office_fixture_responses(
        data: object, records: list[dict], decisions: dict[str, dict],
        registered_office_iris: set[str], registry: dict) -> None:
    """Fail closed on incomplete, out-of-scope or malformed offline evidence."""
    client = _FixtureExternalOfficeWikidataClient(data)
    local_iris = {_external_office_local_iri(record) for record in records}
    stale = sorted(set(decisions) - registered_office_iris)
    if stale:
        raise ValueError("external office review decisions do not match the current registry: "
                         + ", ".join(stale))
    candidate_scope = {local_iri for local_iri in local_iris
                       if local_iri not in decisions}
    unrequested = sorted(set(client.candidates) - candidate_scope)
    if unrequested:
        raise ValueError("response fixture contains unknown, out-of-scope or unrequested office candidate IRI: "
                         + ", ".join(unrequested))

    entities_required: set[str] = set()
    for local_iri in sorted(local_iris):
        decision = decisions.get(local_iri)
        if decision is not None:
            if decision["status"] == "accepted":
                external_iri = decision["external_iri"]
                qid = external_iri.removeprefix("https://www.wikidata.org/entity/")
                if not valid_qid(qid):
                    raise ValueError("reviewed external office identity is not a Wikidata entity IRI")
                entities_required.add(qid)
                if qid not in client.entities:
                    raise ValueError("response fixture lacks Wikidata entity for reviewed office QID " + qid)
                _entity, target_error = _fetch_wikidata_target(client, qid)
                if target_error is not None:
                    raise ValueError("response fixture has invalid Wikidata entity for reviewed office QID " + qid)
            continue

        candidates = client.candidates.get(local_iri)
        if not isinstance(candidates, list):
            raise ValueError("response fixture lacks valid office candidate entry for " + local_iri)
        seen: set[str] = set()
        for raw in candidates:
            candidate = _normalize_office_candidate_for(local_iri, raw, registry)
            if candidate["qid"] in seen:
                raise ValueError("response fixture contains duplicate office candidate QID for " + local_iri)
            _office_candidate_negative_evidence(candidate)
            seen.add(candidate["qid"])

    unknown_entities = sorted(set(client.entities) - entities_required)
    if unknown_entities:
        raise ValueError("response fixture contains unrequested Wikidata entities: "
                         + ", ".join(unknown_entities))


def run_reconcile_office_external(args: argparse.Namespace) -> int:
    """Reconcile only registry-owned enduring offices to reviewed external identities."""
    if args.offline:
        if not args.fixture or not args.responses_file:
            raise ValueError("--offline external office reconciliation requires --fixture and --responses-file")
        if args.publish:
            raise ValueError("--offline external office reconciliation forbids --publish")

    registry_path = Path(args.registry_file or OFFICE_REGISTRY_FILE)
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid office registry: {error}") from error
    validate_registry_source(registry)
    registered_office_iris = {
        str(office_iri(office["key"])) for office in registry["offices"]
    }

    if args.fixture:
        scoped_registry, records = _office_external_fixture_scope(
            Path(args.fixture), registry)
    else:
        scoped_registry = registry
        records = deduplicate_external_office_records(
            office_external_records(scoped_registry))
    scoped_iris = {_external_office_local_iri(record) for record in records}
    if not scoped_iris <= registered_office_iris:
        raise ValueError("external office policy returned an identity outside the reviewed registry")

    decisions, review_hash = load_external_office_review(
        Path(args.review_file or "reconciliation/office-external-decisions.json"), registry)
    stale = sorted(set(decisions) - registered_office_iris)
    if stale:
        raise ValueError("external office review decisions do not match the current registry: "
                         + ", ".join(stale))
    if args.responses_file:
        data = json.loads(Path(args.responses_file).read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_json_object)
        _validate_external_office_fixture_responses(
            data, records, decisions, registered_office_iris, registry)
        wikidata = _FixtureExternalOfficeWikidataClient(data)
    elif args.offline:
        raise ValueError("--offline external office reconciliation requires --responses-file")
    else:
        wikidata = WikidataClient(timeout=Settings.from_environment().timeout)

    settings = Settings.from_environment()
    store = ReconciliationStore(_reconciliation_state_path(args, settings))
    try:
        loader = None
        publication_count = 0
        competency_client = None
        if args.publish:
            endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
            if not endpoint:
                raise ValueError("--publish requires a Fuseki GSP endpoint")
            query_endpoint = args.fuseki_sparql_url or settings.fuseki_sparql_url
            if not query_endpoint:
                raise ValueError("--publish requires a Fuseki SPARQL endpoint for whole-graph verification")
            upstream_loader = FusekiGraphStoreLoader(
                endpoint, user=settings.fuseki_user, password=settings.fuseki_password,
                timeout=settings.timeout)

            class CountingLoader:
                def replace(self, *replace_args, **replace_kwargs):
                    nonlocal publication_count
                    publication_count += 1
                    return upstream_loader.replace(*replace_args, **replace_kwargs)

            loader = CountingLoader()
            competency_client = FusekiSparqlClient(
                query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password,
                timeout=settings.timeout)

        results = reconcile_external_office_records(
            records, store, {iri: decision for iri, decision in decisions.items()
                             if iri in scoped_iris}, review_hash, wikidata,
            all_records=args.all, publish=loader,
            competency_client=competency_client)
        if args.output_nq:
            Path(args.output_nq).write_text("".join(
                nquads(graph, office_external_graph_iri(record, registry))
                for record, _result, graph in results), encoding="utf-8")
        summary = {state: sum(result.state == state for _, result, _ in results)
                   for state in ("accepted", "rejected", "ambiguous", "pending")}
        unresolved = sorted(
            _external_office_local_iri(record)
            for record, result, _ in results
            if result.state in {"pending", "ambiguous"}
            or result.enrichment_status in {"retry", "ambiguous", "unresolved"})
        excluded_candidates = sum(
            len(result.evidence.get("excluded_candidates", []))
            for _, result, _ in results if isinstance(result.evidence, dict))
        print(json.dumps({"processed": len(results), "published": publication_count,
                          "unresolved": len(unresolved),
                          "unresolved_offices": unresolved,
                          "excluded_candidates": excluded_candidates,
                          "scope": sorted(scoped_iris), **summary}, sort_keys=True))
        return 1 if unresolved else 0
    finally:
        store.close()


def _office_fixture_records(path: Path) -> tuple[list[dict], bytes, int | None, str]:
    """Read one fixture page and identify the wrapper-level JSON pointers."""
    body = path.read_bytes()
    value = json.loads(body)
    if isinstance(value, dict) and isinstance(value.get("member"), dict):
        return [value], body, None, "single"
    if isinstance(value, dict):
        records = value.get("results")
        counts = value.get("head", {}).get("counts", {}) if isinstance(value.get("head"), dict) else {}
        advertised = counts.get("memberCount") if isinstance(counts, dict) else None
        if not isinstance(records, list):
            raise ValueError("Members fixture must be a member wrapper, array, or results envelope")
        return records, body, advertised, "results"
    if isinstance(value, list):
        return value, body, None, "array"
    raise ValueError("Members fixture must be a member wrapper, array, or results envelope")


def _office_raw_pointer(raw_path: Path, raw_root: Path, body: bytes, json_pointer: str) -> dict:
    return {"path": raw_path.resolve().relative_to(raw_root.resolve()).as_posix(),
            "sha256": hashlib.sha256(body).hexdigest(), "json_pointer": json_pointer}


def _raw_page_metadata(raw_root: Path, pointer: dict) -> dict:
    raw_path = raw_root / pointer["path"]
    meta_path = raw_path.with_name(raw_path.name.removesuffix(".json") + ".meta.json")
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if metadata.get("sha256") != pointer.get("sha256"):
        raise ValueError("raw source pointer does not match its immutable page metadata")
    return metadata


def run_reconcile_offices(args: argparse.Namespace) -> int:
    """Extract every Member office report and reconcile only against local review data."""
    if args.offline and not args.fixture:
        raise ValueError("--offline office reconciliation requires --fixture")
    if (args.publish or args.responses_file or args.all or args.output_nq
            or args.fuseki_gsp_url or args.fuseki_sparql_url):
        raise ValueError("office occurrence reconciliation is local-only and does not accept external reconciliation options")

    registry_path = Path(args.registry_file or OFFICE_REGISTRY_FILE)
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid office registry: {error}") from error
    validate_registry_source(registry)
    decisions, review_hash = load_office_review(
        Path(args.review_file or OFFICE_DECISIONS_FILE), registry)

    settings = Settings.from_environment()
    raw_root = Path(args.raw_dir).expanduser() if args.raw_dir else settings.raw_dir
    raw_root = raw_root.resolve()
    run_id = str(uuid.uuid4())
    records_with_pointers: list[tuple[dict, dict]] = []
    advertised: int | None = None
    last_api_page: tuple[Path, bytes, object] | None = None

    if args.fixture:
        fixture = Path(args.fixture)
        records, body, advertised, shape = _office_fixture_records(fixture)
        raw_path, _ = persist_raw(
            root=raw_root, endpoint=str(fixture.resolve()),
            params={"skip": 0, "limit": len(records)}, body=body, status=200,
            retrieved_at=datetime.now(timezone.utc), ontology_version=REFERENCE_ONTOLOGY_VERSION,
            mapping_version=MEMBER_MAPPING_VERSION, endpoint_name="members",
            extraction_id=run_id)
        for index, wrapper in enumerate(records):
            if shape == "single":
                json_pointer = ""
            elif shape == "results":
                json_pointer = f"/results/{index}"
            else:
                json_pointer = f"/{index}"
            records_with_pointers.append((wrapper, _office_raw_pointer(raw_path, raw_root, body, json_pointer)))
    else:
        for page in ApiClient(settings.members_api_url, retries=settings.retries,
                              timeout=settings.timeout).harvest(limit=settings.limit):
            raw_path, _ = persist_raw(
                root=raw_root, endpoint=settings.members_api_url, params=page.params,
                body=page.body, status=page.status, ontology_version=REFERENCE_ONTOLOGY_VERSION,
                mapping_version=MEMBER_MAPPING_VERSION, endpoint_name="members",
                extraction_id=run_id)
            decoded = json.loads(page.body)
            envelope_report = _api_envelope_contract(
                args, "members", decoded, run_id=run_id,
                raw_path=raw_path, raw_root=raw_root, body=page.body,
                count_field="memberCount", expected_count=advertised)
            _raise_on_envelope_failure(envelope_report, "Members")
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise ValueError("every Members API page must be an object envelope with a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get("memberCount") if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("every Members API page must contain a nonnegative integer head.counts.memberCount")
            if advertised is None:
                advertised = count
            elif count != advertised:
                raise ValueError("Members advertised count changed during office scan")
            last_api_page = (raw_path, page.body, decoded)
            for index, wrapper in enumerate(decoded["results"]):
                records_with_pointers.append((
                    wrapper, _office_raw_pointer(raw_path, raw_root, page.body, f"/results/{index}")))

    # Reuse the established duplicate/collision/count rules without discarding
    # duplicate raw contexts before office observations are extracted.
    try:
        _deduplicate_members([wrapper for wrapper, _pointer in records_with_pointers],
                             advertised)
    except _AdvertisedCountMismatch as error:
        if last_api_page is not None:
            raw_path, body, decoded = last_api_page
            envelope_report = _api_envelope_contract(
                args, "members", decoded, run_id=run_id,
                raw_path=raw_path, raw_root=raw_root, body=body,
                count_field="memberCount", observed_record_count=error.observed)
            _raise_on_envelope_failure(envelope_report, "Members")
        raise
    observations = extract_office_observations(records_with_pointers)
    state_path = Path(args.office_state_file or OFFICE_OCCURRENCE_STATE_DB_FILE).expanduser()
    with OfficeOccurrenceStore(state_path) as store:
        result = store.reconcile(observations, registry, decisions, review_hash, run_id=run_id)

    report = []
    for item in result["records"]:
        report.append({key: item.get(key) for key in (
            "occurrence_key", "status", "resolution_method", "label", "date_range",
            "current_fingerprint", "office_iris", "candidate_iris", "current_candidates", "current_raw_pointers",
            "conflicts", "pattern_hints", "malformed_reason", "source_presence") if key in item})
    print(json.dumps({"processed": result["processed"], "accepted": result["accepted"],
                      "rejected": result["rejected"], "unresolved": result["unresolved"],
                      "review_required": result["review_required"],
                      "stale_decisions": result["stale_decisions"],
                      "state_db": str(state_path), "records": report}, sort_keys=True))
    return 1 if result["review_required"] or result["unresolved"] else 0


def run_reconcile_bills_local(args: argparse.Namespace) -> int:
    """Rebuild only independently owned per-Bill local sponsor-link graphs."""
    if args.offline and not args.fixture:
        raise ValueError("--offline Bill local reconciliation requires --fixture")
    if args.offline and args.publish:
        raise ValueError("--offline Bill local reconciliation forbids --publish")
    if args.responses_file:
        raise ValueError("Bill local reconciliation never consumes external response fixtures")
    settings = Settings.from_environment()
    registry = json.loads(Path(args.registry_file or OFFICE_REGISTRY_FILE).read_text(encoding="utf-8"))
    validate_registry_source(registry)
    decisions, review_hash = load_bill_sponsor_review(
        Path(args.review_file or BILL_SPONSOR_DECISIONS_FILE))
    records, complete = _local_sponsor_source(args, settings)
    # Source and review errors must fail before any remote graph replacement.
    for wrapper in records:
        validate_bill_source(wrapper)
    state_path = Path(args.bill_state_file or BILL_SPONSOR_STATE_DB_FILE).expanduser()
    core_path = Path(args.state_db or settings.core_state_db_file).expanduser()
    office_path = Path(args.office_state_file or OFFICE_OCCURRENCE_STATE_DB_FILE).expanduser()
    query_url = args.fuseki_sparql_url or settings.fuseki_sparql_url
    gsp_url = args.fuseki_gsp_url or settings.fuseki_gsp_url
    if args.publish and (not query_url or not gsp_url):
        raise ValueError("Bill local --publish requires Fuseki GSP and SPARQL endpoints")
    client = (FusekiSparqlClient(query_url, user=settings.fuseki_user,
                                password=settings.fuseki_password, timeout=settings.timeout)
              if args.publish else None)
    loader = (FusekiGraphStoreLoader(gsp_url, user=settings.fuseki_user,
                                    password=settings.fuseki_password, timeout=settings.timeout)
              if args.publish else None)
    # Keep the same ordering as the authoritative and office occurrence paths:
    # a core refresh cannot change a Bill or Member graph during local PUT.
    from contextlib import ExitStack
    with ExitStack() as stack:
        if args.publish:
            stack.enter_context(state_lock(core_path))
            core = stack.enter_context(CoreStateStore(core_path))
            stack.enter_context(state_lock(office_path))
            office_store = stack.enter_context(OfficeOccurrenceStore(office_path))
            _require_published_sponsor_offices(core, registry, client)
        else:
            core = office_store = None
        stack.enter_context(state_lock(state_path))
        local_store = stack.enter_context(BillSponsorStore(state_path))
        publication = BillSponsorPublication(local_store)
        seen = set()
        graphs, summary = [], []
        for wrapper in records:
            bill = wrapper["bill"]
            bill_iri, local_iri = bill["uri"], bill_sponsor_graph_iri(bill)
            seen.add(bill_iri)
            source_graph = (_published_bill_sponsor_graph(core, wrapper, client)
                            if args.publish else transform_bill_with_report(wrapper)[0])
            validate_bill(wrapper, source_graph)
            observations = extract_bill_sponsor_observations(wrapper)
            observed_by_key = {item["observation_key"]: item for item in observations}
            persons = {item["person_iri"] for item in observations if item["person_iri"]}
            holdings = (_accepted_published_sponsor_holdings(
                core, office_store, persons, registry, client) if args.publish else [])
            known_keys = {row["observation_key"] for row in local_store.observations(bill_iri)}
            known_keys.update(item["observation_key"] for item in observations)
            reviewed = {key: value for key, value in decisions.items() if key in known_keys}
            result = local_store.reconcile(wrapper, registry, holdings, reviewed, review_hash)
            graph = build_bill_sponsor_graph(wrapper, result["records"], registry, holdings)
            validate_bill_sponsor_graph(wrapper, graph, result["records"], registry, holdings)
            # The local graph's subjects must all be present in the unchanged
            # current Bill owner graph; its original label remains there.
            for subject in graph.subjects():
                if (subject, RDF.type, ELIDL.Participation) not in source_graph:
                    raise ValueError("local link has no Participation in current Bill core graph")
            graphs.append((graph, local_iri))
            evidence_hash = sponsor_json_hash([
                {key: item.get(key) for key in ("observation_key", "input_fingerprint",
                                               "status", "office_iri", "holding_iri",
                                               "participation_iri", "review_hash")}
                for item in result["records"]])
            published = publication.publish(bill_iri, local_iri, graph, evidence_hash,
                                            loader, client) if args.publish else False
            summary.append({"bill_iri": bill_iri, "graph": local_iri,
                            "triples": len(graph), "published": published,
                            "counts": result["counts"],
                            "stale_decisions": result["stale_decisions"],
                            "records": [{key: item.get(key) for key in (
                                "observation_key", "participation_iri", "input_fingerprint",
                                "status", "resolution_method", "office_iri", "holding_iri",
                                "time_context", "office_candidates", "holding_candidates", "conflicts")}
                                | {"bill_time_contexts": observed_by_key.get(
                                    item["observation_key"], {}).get("bill_time_contexts", [])}
                                for item in result["records"]]})
        absent = publication.complete_source_presence(seen) if complete else []
        replayed = publication.replay_missing(seen, loader, client) if args.publish else []
        if args.output_nq:
            Path(args.output_nq).write_text("".join(nquads(graph, iri) for graph, iri in graphs),
                                            encoding="utf-8")
        print(json.dumps({"processed": len(records), "published": sum(item["published"] for item in summary),
                          "replayed": replayed, "missing_retained_review_required": absent,
                          "state_db": str(state_path), "bills": summary}, sort_keys=True))
        pending = bool(absent or any(item["counts"]["review_required"]
                                     or item["counts"]["unresolved"]
                                     or item["stale_decisions"] for item in summary))
        return 1 if pending else 0


def run_state_status(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    state_db = Path(getattr(args, "state_db", None) or settings.core_state_db_file).expanduser()
    with CoreStateStore(state_db, legacy_members=settings.members_legacy_state_file,
                        legacy_bills=settings.bills_legacy_state_file) as store:
        print(json.dumps(store.status(), sort_keys=True))
    return 0


def run_quarantine(args: argparse.Namespace) -> int:
    """Inspect unresolved record evidence or enqueue an explicit retry."""
    settings = Settings.from_environment()
    database = Path(getattr(args, "state_db", None)
                    or settings.core_state_db_file).expanduser()
    with state_lock(database):
        with CoreStateStore(database, legacy_members=settings.members_legacy_state_file,
                            legacy_bills=settings.bills_legacy_state_file) as store:
            if args.quarantine_action == "list":
                result = store.quarantine_records(
                    endpoint=getattr(args, "endpoint", None),
                    status=getattr(args, "status", None))
            elif args.quarantine_action == "show":
                rows = [row for row in store.quarantine_records()
                        if row["quarantine_id"] == args.quarantine_id]
                if not rows:
                    raise ValueError(f"unknown quarantine record: {args.quarantine_id}")
                result = {"record": rows[0],
                          "history": store.quarantine_history(args.quarantine_id)}
            elif args.quarantine_action == "retry":
                store.request_quarantine_retry(
                    args.quarantine_id, requested_by=args.requested_by,
                    reason=args.reason)
                result = {"quarantine_id": args.quarantine_id,
                          "retry_state": "requested",
                          "message": "will retry automatically on the next applicable endpoint run"}
                _json_log("quarantine_retry_requested",
                          quarantine_id=args.quarantine_id,
                          requested_by=args.requested_by)
            else:
                raise ValueError(f"unsupported quarantine action: {args.quarantine_action}")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


LOCAL_DEVELOPMENT_GRAPH_ORDER = (
    ("houses", HOUSES_GRAPH),
    ("parties", PARTIES_GRAPH),
    ("constituencies", CONSTITUENCIES_GRAPH),
    ("committees", COMMITTEES_GRAPH),
    ("administrative-units", ADMINISTRATIVE_UNITS_GRAPH),
    ("offices", OFFICES_GRAPH),
)


def _development_dataset_baseline(captures: dict, counts: dict,
                                  development_status: dict,
                                  source_evidence: dict) -> dict:
    """Describe the capture-backed dataset written by the local bootstrap.

    The stable identity is based on source run IDs and URLs, not local paths,
    timestamps, or the Fuseki endpoint. The bootstrap has already
    integrity-checked each preserved capture before this summary is built.
    """
    source_captures = {}
    identity_captures = {}
    for endpoint in sorted(captures):
        _records, capture = captures[endpoint]
        parameters = capture["parameters"]
        source_url = parameters["api_url"]
        run_id = capture["run_id"]
        source_captures[endpoint] = {
            "run_id": run_id,
            "source": parameters["source"],
            "source_url": source_url,
            "record_count": capture["advertised_count"],
        }
        identity_captures[endpoint] = {
            "run_id": run_id,
            "source_url": source_url,
        }

    identity_material = {
        "identity_version": 2,
        "source_captures": identity_captures,
        "development_source_evidence": source_evidence,
    }
    identity_json = json.dumps(
        identity_material, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    )
    dataset_id = "sha256:" + hashlib.sha256(identity_json.encode("utf-8")).hexdigest()
    graph_families_loaded = [
        {"name": "houses", "graph_iri": HOUSES_GRAPH, "graph_count": 1},
        {"name": "parties", "graph_iri": PARTIES_GRAPH, "graph_count": 1},
        {"name": "constituencies", "graph_iri": CONSTITUENCIES_GRAPH,
         "graph_count": 1},
        {"name": "committees", "graph_iri": COMMITTEES_GRAPH,
         "graph_count": 1},
        {"name": "administrative-units",
         "graph_iri": ADMINISTRATIVE_UNITS_GRAPH, "graph_count": 1},
        {"name": "offices", "graph_iri": OFFICES_GRAPH, "graph_count": 1},
        {"name": "members",
         "graph_iri_pattern": "https://data.oireachtas.ie/graph/member/{memberCode}",
         "graph_count": counts["members"]},
    ]
    if counts["bills"]:
        graph_families_loaded.append({
            "name": "bills",
            "graph_iri_pattern": "https://data.oireachtas.ie/graph/bill/{year}/{number}",
            "graph_count": counts["bills"],
        })

    return {
        "schema_version": 1,
        "dataset": {
            "id": dataset_id,
            "identity_method": (
                "SHA-256 of canonical JSON containing selected complete capture "
                "identities plus the exact Core State publication payload inventories "
                "and configured office/unit registry digest"
            ),
            "authority": "non-authoritative development dataset",
            "authoritative_reference_closure_complete": False,
        },
        "source_captures": source_captures,
        "graph_families_loaded": graph_families_loaded,
        "optional_graph_families": [
            {"name": "bills",
             "graph_iri_pattern": "https://data.oireachtas.ie/graph/bill/{year}/{number}",
             "graph_count": counts["bills"],
             "status": ("loaded" if counts["bills"] else
                        "no-eligible-published-resources")},
        ],
        "source_record_counts": {
            endpoint: capture["advertised_count"]
            for endpoint, (_records, capture) in sorted(captures.items())
        },
        "rdf_resource_counts": {
            "house_terms": counts["houses_terms"],
            "members": counts["members"],
            "party_owner_identities": counts["parties"],
            "constituency_panel_owner_identities": counts["constituencies"],
            "committee_owner_identities": counts["committees"],
            "administrative_units": counts["administrative_units"],
            "named_offices": counts["offices"],
            "office_holdings": counts["office_holdings"],
            "cabinet_memberships": counts["cabinet_memberships"],
            "bills": counts["bills"],
        },
        "source_evidence": source_evidence,
        "quarantined_conflict_count": development_status[
            "quarantined_conflict_count"],
        "quarantined_conflicted_identities": development_status[
            "quarantined_conflicts"],
        "unresolved_reference_count": development_status[
            "unresolved_reference_count"],
        "unresolved_references": development_status["unresolved_references"],
        "reference_closure": development_status["reference_closure"],
        "scope_note": (
            "Counts describe the graph payloads written by this bootstrap. "
            "This is not a live census of other or stale graphs already present "
            "in a persistent Fuseki dataset."
        ),
    }


def _read_development_registry(registry_path: Path) -> tuple[dict, Graph, Graph, str]:
    """Load and independently validate the reviewed local office registries."""
    try:
        raw = registry_path.read_bytes()
        registry = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid office registry: {error}") from error
    validate_registry_source(registry)
    units_graph = transform_administrative_units(registry)
    offices_graph = transform_offices(registry)
    validate_administrative_units(registry, units_graph)
    validate_offices(registry, offices_graph)
    return registry, units_graph, offices_graph, hashlib.sha256(raw).hexdigest()


def _development_bills(rows: list[dict]) -> tuple[list[tuple[str, Graph, dict]], dict]:
    """Select only intact, clean Bill graphs already published in Core State."""
    selected: list[tuple[str, Graph, dict]] = []
    skipped: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    for row in rows:
        if row.get("source_presence") != "present":
            skip("not-present")
            continue
        if row.get("publication_state") != "clean":
            skip("not-clean")
            continue
        if row.get("contract_version") != 1:
            skip("unsupported-contract-version")
            continue
        observed_hash = row.get("observed_source_hash")
        published_source_hash = row.get("published_source_hash")
        if (not isinstance(observed_hash, str) or not observed_hash
                or not isinstance(published_source_hash, str) or not published_source_hash
                or observed_hash != published_source_hash):
            skip("published-source-not-current")
            continue
        resource_iri = row.get("resource_iri")
        try:
            expected_graph = expected_graph_iri("legislation", resource_iri)
        except (TypeError, ValueError) as error:
            raise ValueError(f"invalid published Bill resource identity: {resource_iri!r}") from error
        if row.get("graph_iri") != expected_graph:
            raise ValueError(f"published Bill graph identity does not match resource: {resource_iri}")
        payload = row.get("published_payload")
        if not isinstance(payload, str) or not payload:
            skip("missing-published-payload")
            continue
        payload_hash = row.get("published_payload_hash")
        if (not isinstance(payload_hash, str)
                or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash):
            raise ValueError(f"published Bill payload hash does not verify: {resource_iri}")
        graph = Graph()
        try:
            graph.parse(data=payload, format="nt")
        except Exception as error:
            raise ValueError(f"published Bill RDF payload cannot be parsed: {resource_iri}") from error
        if (URIRef(resource_iri), RDF.type, ELIDL.DraftLegislationWork) not in graph:
            raise ValueError(f"published Bill RDF payload does not describe its Bill: {resource_iri}")
        selected.append((expected_graph, graph, row))
    selected.sort(key=lambda item: item[0])
    inventory = [{
        "resource_iri": row["resource_iri"],
        "graph_iri": graph_iri,
        "observed_source_hash": row["observed_source_hash"],
        "published_source_hash": row["published_source_hash"],
        "published_payload_hash": row["published_payload_hash"],
        "source_run_id": row.get("last_seen_run_id"),
    } for graph_iri, _graph, row in selected]
    evidence = {
        "source": "read-only Core State legislation resource publications",
        "resource_rows_examined": len(rows),
        "eligible_resource_count": len(selected),
        "skipped_resource_counts": dict(sorted(skipped.items())),
        "source_run_ids": sorted({item["source_run_id"] for item in inventory
                                   if item["source_run_id"]}),
        "payload_inventory_sha256": hashlib.sha256(json.dumps(
            inventory, ensure_ascii=False, sort_keys=True,
            separators=(",", ":")).encode("utf-8")).hexdigest(),
    }
    return selected, evidence


def _development_member_graph(wrapper: dict, state_row: dict | None) -> tuple[Graph, bool, str | None]:
    """Reuse exact current validated Member output when Core State proves it.

    In particular, office observations are never resolved here. OfficeHolding
    and CabinetMembership enter development only through a clean, current,
    contract-3 Member publication produced by the existing ETL path.
    """
    member = wrapper["member"]
    identity = member["uri"]
    graph_iri = member_graph_iri(member)
    source_digest = source_hash(member)
    validate_member_source(wrapper)
    if (state_row is not None
            and state_row.get("source_presence") == "present"
            and state_row.get("publication_state") == "clean"
            and state_row.get("contract_version") == 3
            and state_row.get("observed_source_hash")
                == state_row.get("published_source_hash")
            and state_row.get("published_source_hash") == source_digest):
        if state_row.get("graph_iri") != graph_iri:
            raise ValueError(f"published Member graph identity does not match source: {identity}")
        payload = state_row.get("published_payload")
        payload_hash = state_row.get("published_payload_hash")
        if (not isinstance(payload, str) or not payload
                or not isinstance(payload_hash, str)
                or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash):
            raise ValueError(f"published Member payload hash does not verify: {identity}")
        graph = Graph()
        try:
            graph.parse(data=payload, format="nt")
        except Exception as error:
            raise ValueError(f"published Member RDF payload cannot be parsed: {identity}") from error
        if (URIRef(identity), RDF.type, OIR.Member) not in graph:
            raise ValueError(f"published Member RDF payload does not describe its Member: {identity}")
        return graph, True, payload_hash

    graph, _diagnostics = transform_member_with_report(wrapper)
    validate_member(wrapper, graph)
    return graph, False, None


def _validate_development_office_references(
        member_graphs: list[tuple[str, Graph]], offices_graph: Graph,
        units_graph: Graph) -> dict:
    """Require reused holdings to resolve in the reviewed registries we load.

    Core State records the validated Member graph payload but not the office
    registry snapshot used to produce it. Do not silently combine an accepted
    historical holding with a different current registry that omits its office.
    """
    registered_offices = set(offices_graph.subjects(RDF.type, MEMBERS.NamedOffice))
    registered_units = set(units_graph.subjects(RDF.type, MEMBERS.AdministrativeUnit))
    missing_offices: set[URIRef] = set()
    for _graph_iri, graph in member_graphs:
        missing_offices.update(
            set(graph.objects(None, MEMBERS.heldOffice)) - registered_offices)
    missing_units: set[URIRef] = set()
    unit_links = set()
    for predicate in (MEMBERS.headsAdministrativeUnit,
                      MEMBERS.assignedToAdministrativeUnit):
        targets = set(offices_graph.objects(None, predicate))
        unit_links.update(targets)
        missing_units.update(targets - registered_units)
    if missing_offices or missing_units:
        details = []
        if missing_offices:
            details.append("unregistered heldOffice targets: "
                           + ", ".join(sorted(map(str, missing_offices))))
        if missing_units:
            details.append("unregistered office administrative-unit targets: "
                           + ", ".join(sorted(map(str, missing_units))))
        raise ValueError("development office registry references do not close: "
                         + "; ".join(details))
    return {
        "status": "verified",
        "member_graph_count": len(member_graphs),
        "office_holding_count": sum(
            len(set(graph.subjects(RDF.type, MEMBERS.OfficeHolding)))
            for _graph_iri, graph in member_graphs),
        "distinct_held_office_count": len(set().union(*(
            set(graph.objects(None, MEMBERS.heldOffice))
            for _graph_iri, graph in member_graphs))) if member_graphs else 0,
        "registered_office_count": len(registered_offices),
        "office_administrative_unit_link_count": len(unit_links),
        "registered_administrative_unit_count": len(registered_units),
    }


def _development_baseline_output_path(output: str | None, *, raw_root: Path,
                                      state_db: Path,
                                      reconciliation_db: Path) -> Path | None:
    """Keep a requested report from overwriting preserved or authority state."""
    if not output:
        return None
    output_path = Path(output).expanduser().resolve()
    raw_path = raw_root.resolve()
    protected_files = set()
    for database in (state_db, reconciliation_db):
        resolved_database = database.resolve()
        protected_files.update({
            resolved_database,
            Path(str(resolved_database) + ".lock"),
            Path(str(resolved_database) + "-wal"),
            Path(str(resolved_database) + "-shm"),
        })
    if (output_path == raw_path or raw_path in output_path.parents
            or output_path in protected_files):
        raise ValueError(
            "dataset baseline output must be outside preserved raw captures, "
            "Core State, and external-reconciliation state"
        )
    return output_path


def _require_loopback_fuseki_endpoint(label: str, endpoint: str | None) -> str:
    if not isinstance(endpoint, str) or not endpoint:
        raise ValueError(f"local development bootstrap requires a {label} Fuseki endpoint")
    try:
        parsed = urlsplit(endpoint)
        hostname = parsed.hostname
        _port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid {label} Fuseki endpoint: {endpoint!r}") from error
    if (parsed.scheme not in {"http", "https"}
            or hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError(
            f"the non-authoritative development bootstrap may write only to a loopback "
            f"{label} endpoint, not {endpoint!r}")
    return endpoint


def _run_development_bootstrap(args: argparse.Namespace) -> int:
    """Load validated, explicitly non-authoritative data into local Fuseki.

    This path reads existing complete API captures and clean resource
    publications from Core State in read-only mode. It neither opens
    ETL/reconciliation stores for writing nor calls the authoritative
    publication helper.
    """
    settings = Settings.from_environment()
    raw_root = Path(getattr(args, "raw_dir", None) or settings.raw_dir).expanduser()
    state_db = Path(getattr(args, "state_db", None)
                    or settings.core_state_db_file).expanduser()
    baseline_output_path = _development_baseline_output_path(
        getattr(args, "dataset_baseline_output", None),
        raw_root=raw_root,
        state_db=state_db,
        reconciliation_db=settings.reconciliation_state_db_file,
    )
    gsp_url = _require_loopback_fuseki_endpoint(
        "Graph Store Protocol", getattr(args, "fuseki_gsp_url", None)
        or settings.fuseki_gsp_url)
    sparql_url = _require_loopback_fuseki_endpoint(
        "SPARQL", getattr(args, "fuseki_sparql_url", None)
        or settings.fuseki_sparql_url)

    # Only successful complete API captures already registered in Core State
    # are eligible input. The selector opens that database read-only; the
    # development census below explicitly marks every source incomplete for
    # authority/coverage purposes.
    captures = {
        endpoint: load_latest_development_capture(raw_root, state_db, endpoint)
        for endpoint in ("houses", "parties", "constituencies", "members")
    }
    houses, _houses_capture = captures["houses"]
    parties, _parties_capture = captures["parties"]
    constituencies, _constituencies_capture = captures["constituencies"]
    members, _members_capture = captures["members"]
    state_resources = read_resource_state(state_db, ("members", "legislation"))
    member_state = {row["resource_iri"]: row
                    for row in state_resources["members"]}
    bill_graphs, bills_evidence = _development_bills(state_resources["legislation"])

    registry_path = Path(getattr(args, "registry_file", None) or OFFICE_REGISTRY_FILE)
    registry, units_graph, offices_graph, registry_hash = _read_development_registry(
        registry_path)

    houses_graph, _house_exclusions = transform_houses_with_report(houses)
    validate_houses(houses, houses_graph)

    # Reuse exact current clean contract-3 Member output from Core State where
    # available. That is the validated result of the existing reviewed-office
    # transformation, including its retention and Cabinet-episode semantics.
    # For every other Member, use the normal transform with no office
    # resolutions: source observations alone can never create holdings.
    member_graphs: list[tuple[str, Graph]] = []
    member_graph = Graph()
    member_publication_inventory = []
    members_from_published_state = 0
    for wrapper in members:
        identity = wrapper["member"]["uri"]
        graph, reused_publication, payload_hash = _development_member_graph(
            wrapper, member_state.get(identity))
        member_graph += graph
        member_graphs.append((member_graph_iri(wrapper["member"]), graph))
        if reused_publication:
            members_from_published_state += 1
            row = member_state[identity]
            member_publication_inventory.append({
                "resource_iri": identity,
                "published_source_hash": row["published_source_hash"],
                "published_payload_hash": payload_hash,
                "source_run_id": row.get("last_seen_run_id"),
            })
    member_graphs.sort(key=lambda item: item[0])
    office_reference_evidence = _validate_development_office_references(
        member_graphs, offices_graph, units_graph)
    member_publication_inventory.sort(key=lambda item: item["resource_iri"])
    member_publication_digest = hashlib.sha256(json.dumps(
        member_publication_inventory, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()

    census = build_reference_census(
        member_records=members,
        party_records=parties,
        constituency_records=constituencies,
        member_capture_complete=False,
        party_capture_complete=False,
        constituency_capture_complete=False,
    )
    candidates = build_development_reference_candidates(
        census, member_graph=member_graph)
    development_status = candidates["development_status"]

    # All source and RDF validation finishes before the first local graph PUT.
    client = FusekiSparqlClient(
        sparql_url, user=settings.fuseki_user, password=settings.fuseki_password,
        timeout=settings.timeout)
    loader = FusekiGraphStoreLoader(
        gsp_url, user=settings.fuseki_user, password=settings.fuseki_password,
        timeout=settings.timeout)
    graphs = {
        "houses": houses_graph,
        "administrative-units": units_graph,
        "offices": offices_graph,
        **candidates["graphs"],
    }
    for endpoint, graph_iri in LOCAL_DEVELOPMENT_GRAPH_ORDER:
        payload = ntriples(graphs[endpoint])
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        verify_core_graph(client, graph_iri, payload)
    for graph_iri, graph, _row in bill_graphs:
        payload = ntriples(graph)
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        verify_core_graph(client, graph_iri, payload)
    for graph_iri, graph in member_graphs:
        payload = ntriples(graph)
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        verify_core_graph(client, graph_iri, payload)

    counts = {
        "houses_terms": len(
            set(houses_graph.subjects(RDF.type, OIR.DailTerm))
            | set(houses_graph.subjects(RDF.type, OIR.SeanadTerm))),
        "parties": len(census["records"]["parties"]),
        "constituencies": len(census["records"]["constituencies"]),
        "committees": len(census["records"]["committees"]),
        "members": len(member_graphs),
        "administrative_units": len(registry["administrative_units"]),
        "offices": len(registry["offices"]),
        "office_holdings": sum(len(set(graph.subjects(RDF.type, MEMBERS.OfficeHolding)))
                                for _iri, graph in member_graphs),
        "cabinet_memberships": sum(len(set(graph.subjects(RDF.type, MEMBERS.CabinetMembership)))
                                    for _iri, graph in member_graphs),
        "bills": len(bill_graphs),
    }
    source_evidence = {
        "office_registry": {
            "source": "configured office/unit registry file",
            "sha256": registry_hash,
            "administrative_unit_count": counts["administrative_units"],
            "office_count": counts["offices"],
        },
        "member_office_registry_references": office_reference_evidence,
        "member_publications": {
            "source": "read-only Core State clean contract-3 publications matching the selected Member source",
            "resource_rows_examined": len(state_resources["members"]),
            "exact_current_graph_count": members_from_published_state,
            "payload_inventory_sha256": member_publication_digest,
            "source_run_ids": sorted({item["source_run_id"]
                                       for item in member_publication_inventory
                                       if item["source_run_id"]}),
        },
        "bill_publications": bills_evidence,
    }
    print("Local development reference bootstrap:")
    print(f"  Houses/HouseTerms: {len(houses)} source records; "
          f"{counts['houses_terms']} HouseTerms")
    print(f"  Members: {counts['members']} validated Member graphs")
    print(f"  Parties: {counts['parties']} owner identities")
    print(f"  Constituencies/panels: {counts['constituencies']} owner identities")
    print(f"  Committees: {counts['committees']} owner identities")
    print(f"  Administrative units: {counts['administrative_units']} reviewed identities")
    print(f"  Named offices: {counts['offices']} reviewed identities")
    print(f"  Office holdings: {counts['office_holdings']} from validated current Member publications")
    print(f"  Cabinet memberships: {counts['cabinet_memberships']} from validated current Member publications")
    print(f"  Bills: {counts['bills']} clean published Bill graphs"
          + (" (optional; none available)" if not counts["bills"] else ""))
    print(f"  Quarantined conflicts: {development_status['quarantined_conflict_count']}")
    for conflict in development_status["quarantined_conflicts"]:
        print(f"    {conflict['reference_kind']} {conflict['canonical_iri']}: "
              f"{conflict['reason']}")
    print("  Unresolved development references: "
          f"{development_status['unresolved_reference_count']}")
    for reference in development_status["unresolved_references"]:
        print(f"    {reference['reference_kind']} {reference['canonical_iri']}: "
              f"{reference['reason']}")
    print(f"  Reference closure: {development_status['reference_closure']}")
    baseline = _development_dataset_baseline(
        captures, counts, development_status, source_evidence)
    print(f"  Dataset identity: {baseline['dataset']['id']}")
    if baseline_output_path:
        baseline_output_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_output_path.write_text(
            json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  Dataset baseline JSON: {baseline_output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oir-etl")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses", "parties", "constituencies", "committees", "administrative-units", "offices", "members", "bills", "debates"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
    run.add_argument("--source-url", action="append", default=[],
                     help="explicit official AKN main.xml URL (repeat for a supplied batch)")
    run.add_argument("--replay", action="append", default=[],
                     help="exact preserved Debates XML SHA-256 (repeat for a supplied batch)")
    run.add_argument("--publish", action="store_true",
                     help="explicitly opt in to validated Debates graph replacement")
    run.add_argument("--registry-file", help="version-controlled office/unit registry JSON")
    run.add_argument("--review-file", help="version-controlled local office observation decisions JSON")
    run.add_argument("--office-state-file", help="durable local office observation/evidence ledger")
    run.add_argument("--migration-inventory-file",
                     help="write the pre-publication Member office migration inventory (default: next to core state)")
    run.add_argument("--state-db", help="shared authoritative core ETL SQLite database")
    run.add_argument("--reconciliation-state-file",
                     help="existing external-reconciliation SQLite database (shared with reconcile commands)")
    run.add_argument("--full", action="store_true", help="complete Bills source reconciliation")
    run.add_argument("--overlap-seconds", type=int, help="Bills cursor overlap (default: 3600)")
    run.add_argument("--legacy-state-file", "--state-file", dest="legacy_state_file",
                     help="read-only legacy Member/Bill JSON manifest to import once")
    run.add_argument("--output-ttl"); run.add_argument("--output-nq"); run.add_argument("--fuseki-gsp-url"); run.add_argument("--fuseki-sparql-url")
    run.add_argument("--coverage-report", help="write deterministic reference census JSON")
    state = sub.add_parser("state"); state_sub = state.add_subparsers(dest="state_command", required=True)
    state_status = state_sub.add_parser("status"); state_status.add_argument("--state-db")
    quarantine = sub.add_parser("quarantine", help="inspect or retry quarantined ETL records")
    quarantine_sub = quarantine.add_subparsers(dest="quarantine_action", required=True)
    quarantine_list = quarantine_sub.add_parser("list")
    quarantine_list.add_argument("--state-db")
    quarantine_list.add_argument("--endpoint", choices=["houses", "parties", "constituencies",
                                                         "members", "legislation", "debates"])
    quarantine_list.add_argument("--status", choices=["quarantined", "resolved"])
    quarantine_show = quarantine_sub.add_parser("show")
    quarantine_show.add_argument("quarantine_id")
    quarantine_show.add_argument("--state-db")
    quarantine_retry = quarantine_sub.add_parser("retry")
    quarantine_retry.add_argument("quarantine_id")
    quarantine_retry.add_argument("--requested-by", required=True)
    quarantine_retry.add_argument("--reason")
    quarantine_retry.add_argument("--state-db")
    dev = sub.add_parser(
        "dev", help="explicitly non-authoritative local-development commands")
    dev_sub = dev.add_subparsers(dest="dev_command", required=True)
    dev_bootstrap = dev_sub.add_parser(
        "bootstrap", help="load preserved API captures into loopback Fuseki for local PoC use")
    dev_bootstrap.add_argument("--raw-dir", help="preserved immutable API capture root")
    dev_bootstrap.add_argument("--state-db", help="read-only Core State capture index")
    dev_bootstrap.add_argument("--registry-file",
                               help="configured office/unit registry JSON")
    dev_bootstrap.add_argument("--fuseki-gsp-url", help="loopback Fuseki Graph Store endpoint")
    dev_bootstrap.add_argument("--fuseki-sparql-url", help="loopback Fuseki SPARQL endpoint")
    dev_bootstrap.add_argument(
        "--dataset-baseline-output",
        help="write deterministic JSON describing the capture-backed development dataset",
    )
    reconcile = sub.add_parser("reconcile"); reconcile.add_argument("endpoint", choices=["members", "parties", "institutions", "offices", "office-external", "bills-local"])
    reconcile.add_argument("--fixture"); reconcile.add_argument("--responses-file"); reconcile.add_argument("--offline", action="store_true"); reconcile.add_argument("--all", action="store_true"); reconcile.add_argument("--publish", action="store_true"); reconcile.add_argument("--output-nq"); reconcile.add_argument("--fuseki-gsp-url"); reconcile.add_argument("--fuseki-sparql-url")
    reconcile.add_argument("--review-file", help="review JSON (defaults to the endpoint-specific version-controlled review file)")
    reconcile.add_argument("--reconciliation-state-file", help="shared reconciliation SQLite path (defaults to the Phase 3.5 state file)")
    reconcile.add_argument("--registry-file", help="versioned local office/unit registry JSON")
    reconcile.add_argument("--office-state-file", help="durable SQLite office observation/evidence ledger")
    reconcile.add_argument("--bill-state-file", help="durable local Bill sponsor reconciliation ledger")
    reconcile.add_argument("--state-db", help="authoritative core ETL SQLite state for published Bills and Members")
    reconcile.add_argument("--raw-dir", help="immutable raw response root for office source scans")
    args = parser.parse_args(argv)
    if (args.command == "run" and args.endpoint != "debates"
            and (args.source_url or args.replay or args.publish)):
        parser.error("--source-url, --replay, and --publish are only available for run debates")
    # Library callers supply argv and retain exceptions for diagnosis. The
    # installed command calls main() without argv: never let a source-supplied
    # exception message escape in a Python traceback on that process boundary.
    if argv is None:
        try:
            return _dispatch_command(args)
        except Exception as error:
            _json_log("command_failed", error=_safe_error_message(error))
            return 1
    return _dispatch_command(args)


def _dispatch_command(args: argparse.Namespace) -> int:
    if args.command == "state": return run_state_status(args)
    if args.command == "quarantine": return run_quarantine(args)
    if args.command == "dev": return _run_development_bootstrap(args)
    if args.command == "reconcile":
        if args.endpoint == "offices": return run_reconcile_offices(args)
        if args.endpoint == "bills-local": return run_reconcile_bills_local(args)
        if args.endpoint == "office-external": return run_reconcile_office_external(args)
        if args.endpoint == "parties": return run_reconcile_parties(args)
        if args.endpoint == "institutions": return run_reconcile_institutions(args)
        return run_reconcile_members(args)
    if args.endpoint == "houses": return run_houses(args)
    if args.endpoint == "members": return run_members(args)
    if args.endpoint == "bills": return run_bills(args)
    if args.endpoint == "debates": return run_debates(args)
    if args.endpoint in {"administrative-units", "offices"}: return run_office_registry(args)
    return run_reference(args)

if __name__ == "__main__": raise SystemExit(main())
