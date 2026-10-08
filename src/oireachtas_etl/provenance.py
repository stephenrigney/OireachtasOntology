"""Core-state provenance and deterministic PROV-O catalog projection.

The SQLite Core State tables remain canonical.  This module reads those tables
and builds a replaceable Fuseki projection; it never writes operational state
directly.  The caller supplies the existing Core State dirty/complete callbacks
when publishing because the provenance catalog is not an ordinary endpoint or
resource graph.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
from typing import Iterable, Mapping, Protocol
from urllib.parse import parse_qsl, quote, urlsplit

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV
from rdflib.namespace import RDF, XSD

from .state import ENDPOINTS, PROVENANCE_GRAPH_IRI, PROVENANCE_NAMESPACE, run_resource_iri
from .serialization import ntriples
from .transforms.common import ELIDL, MEMBERS, OIR


ETL = Namespace(PROVENANCE_NAMESPACE)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret|"
    r"secret|password|passwd|token|authorization|credential|cookie|signature|^auth$|"
    r"(?:^|[_-])key$)",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|secret|password|passwd|token|"
    r"authorization|credential|bearer)\s*[:=]\s*[^\s&;,]{4,}"
)


class ProvenanceCatalogError(ValueError):
    """Core provenance cannot be projected without losing or inventing facts."""


class ProvenancePublicationBoundary(Protocol):
    """Callbacks backed by the Core State dirty -> verify -> clean boundary.

    ``mark_dirty`` must durably retain the exact payload before the remote PUT.
    ``mark_clean`` may be called only after exact whole-graph verification.
    CoreStateStore does not yet expose catalog-specific callbacks; the owning
    session must provide them rather than bypassing state with direct SQL.
    """

    def mark_dirty(self, graph_iri: str, payload: str) -> str: ...

    def mark_clean(self, graph_iri: str, payload_hash: str) -> None: ...


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_version() -> str:
    try:
        return version("oireachtas-ontology")
    except PackageNotFoundError:
        return "0.1.0"


def file_version(path: Path) -> str:
    return sha256(path.read_bytes())


def source_observation_iri(source_hash: str, observed_at: str) -> URIRef:
    """Stable source evidence identity: SHA-256 plus its observation time."""
    _require_hash(source_hash, "source hash")
    when = _timestamp(observed_at, "source observation time")
    suffix = quote(when, safe="-._~")
    return URIRef(f"{PROVENANCE_NAMESPACE}source/{source_hash}/observed/{suffix}")


def graph_version_iri(graph_iri: str, payload_hash: str) -> URIRef:
    """Stable version identity: the named graph IRI plus its payload digest."""
    if not isinstance(graph_iri, str) or not _absolute_iri(graph_iri):
        raise ProvenanceCatalogError(f"invalid published graph IRI: {graph_iri!r}")
    _require_hash(payload_hash, "graph payload hash")
    return URIRef(f"{graph_iri}#sha256={payload_hash}")


def entity_version_iri(graph_iri: str, payload_hash: str,
                       entity_iri: str) -> URIRef:
    """Return the immutable identity for one entity in one graph snapshot."""
    graph_version_iri(graph_iri, payload_hash)
    if not isinstance(entity_iri, str) or not _absolute_iri(entity_iri):
        raise ProvenanceCatalogError(f"invalid published entity IRI: {entity_iri!r}")
    key = json.dumps([graph_iri, payload_hash, entity_iri], ensure_ascii=False,
                     separators=(",", ":"))
    return URIRef(f"{PROVENANCE_NAMESPACE}entity-version/" + sha256(key.encode("utf-8")))


def source_record_evidence_iri(source_hash: str, observed_at: str,
                               evidence_pointer: str) -> URIRef:
    """Identify one immutable JSON record pointer within one page observation."""
    _require_hash(source_hash, "record evidence source hash")
    when = _timestamp(observed_at, "record evidence observation time")
    if not isinstance(evidence_pointer, str) or not evidence_pointer.strip():
        raise ProvenanceCatalogError("record evidence pointer must be non-empty")
    key = json.dumps([source_hash, when, evidence_pointer], ensure_ascii=False,
                     separators=(",", ":"))
    return URIRef(f"{PROVENANCE_NAMESPACE}source-record/" + sha256(key.encode("utf-8")))


_SHARED_ENTITY_TYPES = {
    "houses": (OIR.House, ELIDL.ParliamentaryTerm),
    "parties": (MEMBERS.ParliamentaryMemberCollection,),
    "constituencies": (MEMBERS.Constituencies,),
    "committees": (MEMBERS.Committee,),
}


def shared_graph_entity_iris(endpoint: str, payload: str | Graph) -> set[str]:
    """Return owned House/term/reference entities represented in a shared graph.

    This is an operational provenance inventory, not a semantic transformation:
    it selects the owner classes already emitted by the existing transformers.
    """
    types = _SHARED_ENTITY_TYPES.get(endpoint)
    if types is None:
        raise ProvenanceCatalogError(
            f"entity-version lineage is not defined for shared endpoint {endpoint!r}")
    graph = payload if isinstance(payload, Graph) else Graph()
    if not isinstance(payload, Graph):
        try:
            graph.parse(data=payload, format="nt")
        except Exception as error:
            raise ProvenanceCatalogError(
                f"shared {endpoint} payload is not valid N-Triples") from error
    return {str(subject) for type_ in types
            for subject in graph.subjects(RDF.type, type_)
            if isinstance(subject, URIRef)}


def _require_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ProvenanceCatalogError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _absolute_iri(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme and not any(ch.isspace() for ch in value))
    except (TypeError, ValueError):
        return False


def _timestamp(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ProvenanceCatalogError(f"{label} must be a timezone-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ProvenanceCatalogError(f"invalid {label}: {value!r}") from error
    if parsed.tzinfo is None:
        raise ProvenanceCatalogError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _json_object(value: object, label: str) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError) as error:
            raise ProvenanceCatalogError(f"invalid {label} JSON") from error
    if not isinstance(value, dict):
        raise ProvenanceCatalogError(f"{label} must be a JSON object")
    return value


def _run_parameters(row: Mapping) -> dict:
    value = row.get("parameters")
    if value is None:
        value = row.get("parameters_json")
    if value is None:
        return {}
    return _json_object(value, "run parameters")


def _check_no_secret_fields(value: object, label: str) -> None:
    """Reject secret-bearing metadata rather than silently publishing it."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or _SENSITIVE_KEY.search(key.replace(" ", "")):
                raise ProvenanceCatalogError(f"{label} contains a secret-bearing field")
            _check_no_secret_fields(item, label)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_no_secret_fields(item, label)
    elif isinstance(value, str):
        if (_SECRET_VALUE.search(value)
                or re.search(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/=_-]{8,}", value)):
            raise ProvenanceCatalogError(f"{label} appears to contain an authentication secret")
        if "://" in value:
            try:
                parsed = urlsplit(value)
            except ValueError as error:
                raise ProvenanceCatalogError(f"{label} contains an invalid URL") from error
            if parsed.scheme in {"http", "https"}:
                _safe_url(value, label)
            elif (parsed.username is not None or parsed.password is not None
                  or any(_SENSITIVE_KEY.search(key.replace(" ", ""))
                         for key, _item in parse_qsl(parsed.query, keep_blank_values=True))):
                raise ProvenanceCatalogError(f"{label} contains a secret-bearing location")


def _safe_url(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceCatalogError(f"{label} must be a non-empty absolute URL")
    try:
        parsed = urlsplit(value)
        has_credentials = parsed.username is not None or parsed.password is not None
    except ValueError as error:
        raise ProvenanceCatalogError(f"invalid {label}") from error
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or has_credentials:
        raise ProvenanceCatalogError(f"{label} must not contain credentials or use a non-HTTP scheme")
    if any(_SENSITIVE_KEY.search(key.replace(" ", ""))
           for key, _value in parse_qsl(parsed.query, keep_blank_values=True)):
        raise ProvenanceCatalogError(f"{label} query contains a secret-bearing parameter")
    return value


def _versions(row: Mapping, *, from_json: str | None = None) -> dict[str, str | None]:
    raw = row.get(from_json) if from_json else row.get("versions", {})
    versions = _json_object(raw, "version metadata")
    allowed = {"etl_version", "ontology_version", "mapping_version"}
    if versions.keys() - allowed:
        raise ProvenanceCatalogError("version metadata contains unsupported fields")
    result: dict[str, str | None] = {}
    for key in sorted(allowed):
        value = versions.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ProvenanceCatalogError(f"{key} must be a non-empty version string")
        result[key] = value
    return result


def _input_rows(store) -> tuple[list[dict], list[dict], list[dict], list[dict],
                                list[dict], list[dict]]:
    """Read one projection's canonical state tables without changing them."""
    try:
        events = store.provenance_events()
        versions = store.graph_versions()
        entity_versions = store.entity_versions()
        entity_version_sources = store.entity_version_sources()
        connection = store.connection
        runs = [dict(row) for row in connection.execute(
            "SELECT run_id,endpoint,run_kind,is_complete,started_at,completed_at,status,outcome,"
            "etl_version,ontology_version,mapping_version,parameters_json "
            "FROM etl_run ORDER BY started_at,run_id")]
        sources = [dict(row) for row in connection.execute(
            "SELECT source_hash,observed_at,endpoint,run_id,evidence_pointer,source_url,"
            "request_parameters_json,versions_json FROM source_observation "
            "ORDER BY observed_at,source_hash")]
    except (AttributeError, TypeError) as error:
        raise ProvenanceCatalogError("Core State does not expose required provenance records") from error
    return events, versions, runs, sources, entity_versions, entity_version_sources


def build_provenance_catalog_from_records(
    provenance_events: Iterable[Mapping],
    graph_versions: Iterable[Mapping],
    runs: Iterable[Mapping],
    source_observations: Iterable[Mapping],
    entity_versions: Iterable[Mapping] = (),
    entity_version_sources: Iterable[Mapping] = (),
    *,
    require_source_run_ids: Iterable[str] = (),
) -> Graph:
    """Purely project canonical Core State records into deterministic PROV-O RDF.

    Historical records without raw pointers remain projectable but receive no
    fabricated pointer; links are emitted only for source identities present
    in canonical Core State. Run IDs supplied in ``require_source_run_ids``
    identify the current publication work: every graph version published by
    those runs must resolve to immutable observations with non-empty read-only
    raw evidence pointers.
    """
    required_runs = set(require_source_run_ids)
    if any(not isinstance(run_id, str) or not run_id for run_id in required_runs):
        raise ProvenanceCatalogError("required source run IDs must be non-empty strings")

    event_rows = [dict(row) for row in provenance_events]
    version_rows = [dict(row) for row in graph_versions
                    if row.get("graph_iri") != PROVENANCE_GRAPH_IRI]
    run_rows = [dict(row) for row in runs]
    source_rows = [dict(row) for row in source_observations]
    entity_version_rows = [dict(row) for row in entity_versions]
    entity_source_rows = [dict(row) for row in entity_version_sources]

    runs_by_id: dict[str, dict] = {}
    run_iris: dict[str, URIRef] = {}
    graph = Graph()
    graph.bind("prov", PROV)
    graph.bind("etl", ETL)
    graph.bind("rdf", RDF)

    for row in run_rows:
        run_id, endpoint = row.get("run_id"), row.get("endpoint")
        if not isinstance(run_id, str) or not run_id or run_id in runs_by_id:
            raise ProvenanceCatalogError("run records must have unique, non-empty IDs")
        if endpoint not in ENDPOINTS:
            raise ProvenanceCatalogError(f"run {run_id!r} has an unsupported endpoint")
        run = run_resource_iri(run_id)
        runs_by_id[run_id] = row
        run_iris[run_id] = URIRef(run)
        graph.add((run_iris[run_id], RDF.type, PROV.Activity))
        graph.add((run_iris[run_id], ETL.endpoint, Literal(endpoint)))
        if isinstance(row.get("run_kind"), str):
            graph.add((run_iris[run_id], ETL.runKind, Literal(row["run_kind"])))
        if row.get("is_complete") in (0, 1, False, True):
            graph.add((run_iris[run_id], ETL.isComplete,
                       Literal(bool(row["is_complete"]), datatype=XSD.boolean)))
        if isinstance(row.get("status"), str):
            graph.add((run_iris[run_id], ETL.runStatus, Literal(row["status"])))
        if isinstance(row.get("outcome"), str):
            graph.add((run_iris[run_id], ETL.runOutcome, Literal(row["outcome"])))
        started_at = row.get("started_at")
        if started_at:
            graph.add((run_iris[run_id], PROV.startedAtTime,
                       Literal(_timestamp(started_at, "run start time"), datatype=XSD.dateTime)))
        completed_at = row.get("completed_at")
        if completed_at:
            graph.add((run_iris[run_id], PROV.endedAtTime,
                       Literal(_timestamp(completed_at, "run completion time"), datatype=XSD.dateTime)))
        for field, predicate in (("etl_version", ETL.etlVersion),
                                 ("ontology_version", ETL.ontologyVersion),
                                 ("mapping_version", ETL.mappingVersion)):
            value = row.get(field)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ProvenanceCatalogError(f"run {run_id!r} has an invalid {field}")
                _check_no_secret_fields(value, f"run {field}")
                graph.add((run_iris[run_id], predicate, Literal(value)))

    unknown_required_runs = required_runs - runs_by_id.keys()
    if unknown_required_runs:
        raise ProvenanceCatalogError("required source run ID is absent from Core State")

    sources_by_key: dict[tuple[str, str], dict] = {}
    sources_by_run_endpoint: dict[tuple[str, str], list[dict]] = defaultdict(list)
    sources_by_run_hash_endpoint: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    source_iris: dict[tuple[str, str], URIRef] = {}
    for row in source_rows:
        source_hash = _require_hash(row.get("source_hash"), "source observation hash")
        observed_at = _timestamp(row.get("observed_at"), "source observation time")
        key = (source_hash, observed_at)
        if key in sources_by_key:
            raise ProvenanceCatalogError("duplicate source hash/observation identity")
        endpoint, run_id = row.get("endpoint"), row.get("run_id")
        if endpoint not in ENDPOINTS or run_id not in runs_by_id:
            raise ProvenanceCatalogError("source observation has no matching Core State run")
        if runs_by_id[run_id].get("endpoint") != endpoint:
            raise ProvenanceCatalogError("source observation endpoint differs from its run")
        request = row.get("request_parameters")
        if request is None:
            request = row.get("request_parameters_json", {})
        request = _json_object(request, "source request parameters")
        _check_no_secret_fields(request, "source request parameters")
        source_url = row.get("source_url")
        if source_url is not None:
            source_url = _safe_url(source_url, "source URL")
        pointer = row.get("evidence_pointer")
        if pointer is not None:
            if not isinstance(pointer, str) or not pointer.strip():
                raise ProvenanceCatalogError("source evidence pointer must be a non-empty string")
            _check_no_secret_fields(pointer, "source evidence pointer")
        versions = _versions(row, from_json="versions_json" if "versions_json" in row else None)

        iri = source_observation_iri(source_hash, observed_at)
        source_iris[key] = iri
        sources_by_key[key] = row
        sources_by_run_endpoint[(run_id, endpoint)].append(row)
        sources_by_run_hash_endpoint[(run_id, endpoint, source_hash)].append(row)
        graph.add((iri, RDF.type, PROV.Entity))
        graph.add((iri, ETL.sourceHash, Literal(source_hash)))
        graph.add((iri, ETL.observedAt,
                   Literal(observed_at, datatype=XSD.dateTime)))
        graph.add((iri, ETL.endpoint, Literal(endpoint)))
        try:
            request_json = json.dumps(request, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ProvenanceCatalogError("source request parameters are not canonical JSON") from error
        graph.add((iri, ETL.requestParameters, Literal(request_json)))
        if source_url is not None:
            graph.add((iri, ETL.sourceURL, URIRef(source_url)))
        if pointer is not None:
            graph.add((iri, ETL.evidencePointer, Literal(pointer)))
        for field, predicate in (("etl_version", ETL.etlVersion),
                                 ("ontology_version", ETL.ontologyVersion),
                                 ("mapping_version", ETL.mappingVersion)):
            if versions[field] is not None:
                _check_no_secret_fields(versions[field], f"source {field}")
                graph.add((iri, predicate, Literal(versions[field])))
        graph.add((run_iris[run_id], PROV.used, iri))

    def committee_member_capture_observations(publisher_run_id: str, *,
                                               member_source_run_id: object,
                                               required: bool) -> list[dict]:
        """Resolve an empty Committee graph to its preserved Members capture.

        Committee descriptions are derived from Members, not from a Committee
        API observation. When the owner graph has no Committee entities, the
        graph version itself therefore derives from the exact page observations
        for the complete Members capture named by the publishing run.
        """
        publisher = runs_by_id.get(publisher_run_id)
        if publisher is None:
            if required:
                raise ProvenanceCatalogError(
                    "empty Committee publication has no Core State publisher run")
            return []
        publisher_parameters = _run_parameters(publisher)
        explicit_member_run_id = member_source_run_id is not None
        if explicit_member_run_id:
            member_run_id = member_source_run_id
        elif publisher.get("endpoint") == "members":
            member_run_id = publisher_run_id
        elif publisher.get("endpoint") == "committees":
            member_run_id = publisher_parameters.get("source_run_id")
        else:
            member_run_id = None

        member_run = runs_by_id.get(member_run_id) if isinstance(member_run_id, str) else None
        member_parameters = _run_parameters(member_run) if member_run is not None else {}
        publisher_source_matches = (
            publisher.get("endpoint") != "members"
            or member_run_id == publisher_run_id)
        if (publisher.get("endpoint") == "committees"
                and publisher_parameters.get("source_run_id") is not None):
            publisher_source_matches = (
                publisher_source_matches
                and publisher_parameters.get("source_run_id") == member_run_id)
        valid_member_capture = (
            member_run is not None
            and publisher.get("endpoint") in
            {"members", "committees", "parties", "constituencies"}
            and member_run.get("endpoint") == "members"
            and member_run.get("is_complete") in (1, True)
            and member_parameters.get("source") == "api"
            and publisher_source_matches
            and (member_run_id == publisher_run_id or (
                member_run.get("status") == "succeeded"
                and member_run.get("outcome") == "success"))
        )
        if not valid_member_capture:
            if required:
                raise ProvenanceCatalogError(
                    "empty Committee publication does not identify a successful complete "
                    "Members API capture")
            return []

        observations = sources_by_run_endpoint.get((member_run_id, "members"), [])
        if required and not observations:
            raise ProvenanceCatalogError(
                "empty Committee publication has no immutable Members capture source observations")
        preserved: list[dict] = []
        for observation in observations:
            pointer = observation.get("evidence_pointer")
            if not isinstance(pointer, str) or not pointer.strip():
                if required:
                    raise ProvenanceCatalogError(
                        "empty Committee publication lacks a preserved Members raw page pointer")
                continue
            versions = _versions(
                observation,
                from_json="versions_json" if "versions_json" in observation else None)
            if any(versions[field] is None for field in
                   ("etl_version", "ontology_version", "mapping_version")):
                if required:
                    raise ProvenanceCatalogError(
                        "empty Committee publication Members capture lacks complete version metadata")
                continue
            preserved.append(observation)
        if required and not preserved:
            raise ProvenanceCatalogError(
                "empty Committee publication has no preserved Members capture source observations")
        return preserved

    events_by_version: dict[tuple[str, str], list[dict]] = defaultdict(list)
    source_event_keys: set[tuple[str, str]] = set()
    for row in event_rows:
        event_type = row.get("event_type")
        if event_type == "source_observed":
            key = (row.get("source_hash"), row.get("observed_at"))
            if not all(isinstance(item, str) for item in key):
                raise ProvenanceCatalogError("source-observed event lacks its immutable identity")
            normalized = (key[0], _timestamp(key[1], "source observation event time"))
            source = sources_by_key.get(normalized)
            if source is None or source.get("run_id") != row.get("run_id"):
                raise ProvenanceCatalogError("source-observed event has no matching immutable observation")
            if normalized in source_event_keys:
                raise ProvenanceCatalogError("duplicate source-observed event for one immutable identity")
            source_event_keys.add(normalized)
            if row.get("endpoint") != source.get("endpoint"):
                raise ProvenanceCatalogError("source event endpoint differs from immutable source observation")
            if row.get("evidence_pointer") != source.get("evidence_pointer"):
                raise ProvenanceCatalogError("source event pointer differs from immutable source observation")
            details = row.get("details")
            if isinstance(details, Mapping):
                if ("source_url" in details
                        and details["source_url"] != source.get("source_url")):
                    raise ProvenanceCatalogError(
                        "source event URL differs from immutable source observation")
                if "request_parameters" in details:
                    event_request = _json_object(
                        details["request_parameters"], "source event request parameters")
                    source_request = source.get("request_parameters")
                    if source_request is None:
                        source_request = source.get("request_parameters_json", {})
                    source_request = _json_object(source_request, "source request parameters")
                    if event_request != source_request:
                        raise ProvenanceCatalogError(
                            "source event request differs from immutable source observation")
        elif event_type in {"graph_published", "entity_published"}:
            graph_iri = row.get("graph_iri")
            if graph_iri == PROVENANCE_GRAPH_IRI:
                # A catalog cannot list its own current version without making
                # each replacement recursively depend on its previous payload.
                continue
            payload_hash = _require_hash(row.get("payload_hash"), "published payload hash")
            graph_version_iri(graph_iri, payload_hash)
            version_key = (graph_iri, payload_hash)
            events_by_version[version_key].append(row)
        elif event_type in {"run_started", "run_finished"}:
            # Run records, not mutable event details, are canonical for the
            # activity's facts and version metadata.
            continue
        else:
            raise ProvenanceCatalogError(f"unsupported provenance event type: {event_type!r}")

    if source_event_keys != set(sources_by_key):
        raise ProvenanceCatalogError("source observations and immutable source events do not agree")

    versions_by_key: dict[tuple[str, str], dict] = {}
    for row in version_rows:
        graph_iri = row.get("graph_iri")
        payload_hash = _require_hash(row.get("payload_hash"), "graph version payload hash")
        version_iri = graph_version_iri(graph_iri, payload_hash)
        version_key = (graph_iri, payload_hash)
        if version_key in versions_by_key:
            raise ProvenanceCatalogError("duplicate graph IRI/payload-hash identity")
        payload = row.get("payload")
        if not isinstance(payload, str) or hashlib.sha256(payload.encode("utf-8")).hexdigest() != payload_hash:
            raise ProvenanceCatalogError(f"stored graph version payload is corrupt: {graph_iri}")
        if row.get("endpoint") not in ENDPOINTS:
            raise ProvenanceCatalogError("graph version has an unsupported endpoint")
        versions_by_key[version_key] = row
        graph.add((version_iri, RDF.type, PROV.Entity))
        graph.add((version_iri, PROV.specializationOf, URIRef(graph_iri)))
        graph.add((version_iri, ETL.payloadHash, Literal(payload_hash)))
        graph.add((version_iri, ETL.endpoint, Literal(row["endpoint"])))
        if row.get("entity_iri") is not None:
            if not isinstance(row["entity_iri"], str) or not _absolute_iri(row["entity_iri"]):
                raise ProvenanceCatalogError("graph version has an invalid entity IRI")
            graph.add((version_iri, ETL.publishedEntity, URIRef(row["entity_iri"])))
        created_at = row.get("created_at")
        if created_at:
            graph.add((version_iri, PROV.generatedAtTime,
                       Literal(_timestamp(created_at, "graph version creation time"),
                               datatype=XSD.dateTime)))

    if set(events_by_version) != set(versions_by_key):
        missing_events = set(versions_by_key) - set(events_by_version)
        missing_versions = set(events_by_version) - set(versions_by_key)
        if missing_events or missing_versions:
            raise ProvenanceCatalogError(
                "graph-version records and immutable publication events do not agree")

    entity_versions_by_key: dict[tuple[str, str, str], dict] = {}
    entity_sources_by_key: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for source in entity_source_rows:
        graph_iri = source.get("graph_iri")
        payload_hash = _require_hash(source.get("payload_hash"),
                                     "entity source payload hash")
        entity_iri = source.get("entity_iri")
        if not isinstance(entity_iri, str) or not _absolute_iri(entity_iri):
            raise ProvenanceCatalogError("entity source has an invalid entity IRI")
        key = (graph_iri, payload_hash, entity_iri)
        if key not in entity_versions_by_key and not any(
                (row.get("graph_iri"), row.get("payload_hash"), row.get("entity_iri")) == key
                for row in entity_version_rows):
            raise ProvenanceCatalogError("entity source evidence has no entity-version association")
        source_hash = _require_hash(source.get("source_hash"), "entity source hash")
        observed_at = _timestamp(source.get("observed_at"),
                                 "entity source observation time")
        pointer = source.get("evidence_pointer")
        if not isinstance(pointer, str) or not pointer.strip():
            raise ProvenanceCatalogError("entity source requires an exact record JSON pointer")
        _check_no_secret_fields(pointer, "entity record evidence pointer")
        observation = sources_by_key.get((source_hash, observed_at))
        if observation is None:
            raise ProvenanceCatalogError("entity source refers to an unknown source observation")
        page_pointer = observation.get("evidence_pointer")
        page, marker, fragment = pointer.partition("#")
        if (not isinstance(page_pointer, str) or not marker or page != page_pointer
                or not fragment.startswith("/") or re.search(r"~(?![01])", fragment)):
            raise ProvenanceCatalogError(
                "entity record JSON pointer does not identify a record in its exact source page")
        source_versions = _versions(
            observation, from_json="versions_json" if "versions_json" in observation else None)
        if any(source_versions[field] is None for field in
               ("etl_version", "ontology_version", "mapping_version")):
            raise ProvenanceCatalogError("new entity source observation lacks complete version metadata")
        if source not in entity_sources_by_key[key]:
            entity_sources_by_key[key].append({
                "source_hash": source_hash, "observed_at": observed_at,
                "evidence_pointer": pointer,
            })

    for row in entity_version_rows:
        graph_iri = row.get("graph_iri")
        payload_hash = _require_hash(row.get("payload_hash"),
                                     "entity-version payload hash")
        entity_iri = row.get("entity_iri")
        if not isinstance(entity_iri, str) or not _absolute_iri(entity_iri):
            raise ProvenanceCatalogError("entity-version association has an invalid entity IRI")
        key = (graph_iri, payload_hash, entity_iri)
        if key in entity_versions_by_key:
            raise ProvenanceCatalogError("duplicate immutable entity-version identity")
        graph_row = versions_by_key.get((graph_iri, payload_hash))
        if graph_row is None:
            raise ProvenanceCatalogError("entity version has no matching published graph version")
        endpoint = row.get("endpoint")
        if endpoint != graph_row.get("endpoint") or endpoint not in _SHARED_ENTITY_TYPES:
            raise ProvenanceCatalogError("entity-version owner differs from its shared graph")
        expected_entities = shared_graph_entity_iris(endpoint, graph_row["payload"])
        if entity_iri not in expected_entities:
            raise ProvenanceCatalogError(
                "entity-version association is not an owner entity in its graph payload")
        run_id = row.get("run_id")
        if run_id not in runs_by_id:
            raise ProvenanceCatalogError("entity-version association has no publishing run")
        prior_hash = row.get("prior_payload_hash")
        if prior_hash is not None:
            prior_hash = _require_hash(prior_hash, "prior entity-version payload hash")
            if prior_hash == payload_hash:
                raise ProvenanceCatalogError("entity version cannot derive from itself")
        entity_versions_by_key[key] = row

    shared_entities_by_graph_version: dict[tuple[str, str], set[str]] = defaultdict(set)
    entity_version_iris: dict[tuple[str, str, str], URIRef] = {}
    graph_derivations: dict[tuple[str, str], set[URIRef]] = defaultdict(set)
    source_record_entities: set[URIRef] = set()
    for key, row in entity_versions_by_key.items():
        graph_iri, payload_hash, entity_iri = key
        version_key = (graph_iri, payload_hash)
        subject = entity_version_iri(graph_iri, payload_hash, entity_iri)
        entity_version_iris[key] = subject
        shared_entities_by_graph_version[version_key].add(entity_iri)
        graph.add((subject, RDF.type, PROV.Entity))
        graph.add((subject, PROV.specializationOf, URIRef(entity_iri)))
        graph.add((subject, ETL.graphIRI, URIRef(graph_iri)))
        graph.add((subject, ETL.payloadHash, Literal(payload_hash)))
        graph.add((subject, ETL.endpoint, Literal(row["endpoint"])))
        graph.add((subject, ETL.publishedEntity, URIRef(entity_iri)))
        graph.add((subject, PROV.wasGeneratedBy, run_iris[row["run_id"]]))
        if row.get("created_at"):
            graph.add((subject, PROV.generatedAtTime,
                       Literal(_timestamp(row["created_at"],
                                          "entity-version creation time"),
                               datatype=XSD.dateTime)))
        event_runs = {event.get("run_id") for event in events_by_version[version_key]}
        if row["run_id"] not in event_runs:
            raise ProvenanceCatalogError(
                "entity-version publishing run has no matching graph publication event")

        direct_sources = entity_sources_by_key.get(key, [])
        prior_hash = row.get("prior_payload_hash")
        if not direct_sources and prior_hash is None:
            raise ProvenanceCatalogError(
                "entity version has neither exact source-record evidence nor a prior entity version")
        for source in direct_sources:
            source_key = (source["source_hash"], source["observed_at"])
            source_iri = source_iris.get(source_key)
            if source_iri is None:
                raise ProvenanceCatalogError("entity source observation is not projectable")
            evidence_iri = source_record_evidence_iri(
                source["source_hash"], source["observed_at"], source["evidence_pointer"])
            source_record_entities.add(evidence_iri)
            graph.add((evidence_iri, RDF.type, PROV.Entity))
            graph.add((evidence_iri, ETL.sourceObservation, source_iri))
            graph.add((evidence_iri, ETL.evidencePointer,
                       Literal(source["evidence_pointer"])))
            graph.add((evidence_iri, PROV.wasDerivedFrom, source_iri))
            graph.add((subject, PROV.wasDerivedFrom, source_iri))
            graph.add((subject, PROV.wasDerivedFrom, evidence_iri))
            graph_derivations[version_key].add(source_iri)
        if prior_hash is not None:
            prior_key = (graph_iri, prior_hash, entity_iri)
            prior_row = entity_versions_by_key.get(prior_key)
            if prior_row is None:
                raise ProvenanceCatalogError(
                    "retained entity version refers to an unavailable prior immutable version")
            prior_iri = entity_version_iri(*prior_key)
            graph.add((subject, PROV.wasDerivedFrom, prior_iri))
            graph_derivations[version_key].add(prior_iri)

    # A shared payload gets entity-level PROV only when the complete owner set
    # is present. Legacy graph versions without associations remain projectable
    # as historical graph-only facts, but a new required publication cannot
    # omit any entity lineage.
    for version_key, version_row in versions_by_key.items():
        endpoint = version_row["endpoint"]
        if endpoint not in _SHARED_ENTITY_TYPES:
            continue
        expected_entities = shared_graph_entity_iris(endpoint, version_row["payload"])
        actual_entities = shared_entities_by_graph_version.get(version_key, set())
        if actual_entities and actual_entities != expected_entities:
            raise ProvenanceCatalogError(
                "shared graph entity-version records do not cover the complete owner payload")
        if (expected_entities and not actual_entities and any(
                event.get("run_id") in required_runs
                for event in events_by_version[version_key])):
            raise ProvenanceCatalogError(
                "new shared graph publication lacks immutable entity-version lineage")

    for key, rows in events_by_version.items():
        version_row = versions_by_key[key]
        subject = graph_version_iri(*key)
        derived: set[URIRef] = set()
        expected_entities = (
            shared_graph_entity_iris(version_row["endpoint"], version_row["payload"])
            if version_row.get("endpoint") in _SHARED_ENTITY_TYPES else set())
        actual_entities = shared_entities_by_graph_version.get(key, set())
        has_complete_entities = bool(expected_entities) and actual_entities == expected_entities
        empty_committee_graph = (
            version_row.get("endpoint") == "committees"
            and not expected_entities and not actual_entities)
        for event in rows:
            run_id, endpoint = event.get("run_id"), event.get("endpoint")
            if endpoint != version_row.get("endpoint"):
                raise ProvenanceCatalogError("publication event endpoint differs from graph version")
            if event.get("event_type") == "entity_published":
                if event.get("entity_iri") != version_row.get("entity_iri"):
                    raise ProvenanceCatalogError("published entity differs from graph-version record")
            elif event.get("entity_iri") is not None or version_row.get("entity_iri") is not None:
                raise ProvenanceCatalogError("shared graph publication has an unexpected entity identity")
            if run_id is not None:
                if run_id not in runs_by_id:
                    raise ProvenanceCatalogError("publication event references an unknown run")
                graph.add((subject, PROV.wasGeneratedBy, run_iris[run_id]))
                if empty_committee_graph:
                    event_details = event.get("details")
                    event_member_source_run_id = (
                        event_details.get("member_source_run_id")
                        if isinstance(event_details, Mapping) else None)
                    observations = committee_member_capture_observations(
                        run_id,
                        member_source_run_id=event_member_source_run_id,
                        required=run_id in required_runs)
                    if run_id in required_runs and not observations:
                        raise ProvenanceCatalogError(
                            "empty Committee publication has no immutable Members capture source observations")
                    for observation in observations:
                        source_key = (
                            _require_hash(observation.get("source_hash"), "source hash"),
                            _timestamp(observation.get("observed_at"),
                                       "source observation time"),
                        )
                        source_iri = source_iris.get(source_key)
                        if source_iri is None:
                            raise ProvenanceCatalogError(
                                "Committee source capture observation is not projectable")
                        derived.add(source_iri)
                elif not has_complete_entities:
                    source_hash = event.get("source_hash")
                    if source_hash is not None:
                        _require_hash(source_hash, "publication source hash")
                        observations = sources_by_run_hash_endpoint.get(
                            (run_id, endpoint, source_hash), [])
                    else:
                        observations = sources_by_run_endpoint.get((run_id, endpoint), [])
                    if run_id in required_runs:
                        if not observations:
                            raise ProvenanceCatalogError(
                                f"new publication in run {run_id} has no immutable source observation")
                        if any(not isinstance(item.get("evidence_pointer"), str)
                               or not item["evidence_pointer"].strip() for item in observations):
                            raise ProvenanceCatalogError(
                                f"new publication in run {run_id} lacks an immutable raw source pointer")
                    for observation in observations:
                        source_key = (_require_hash(observation.get("source_hash"), "source hash"),
                                      _timestamp(observation.get("observed_at"), "source observation time"))
                        source_iri = source_iris.get(source_key)
                        if source_iri is None:
                            raise ProvenanceCatalogError("publication source observation is not projectable")
                        derived.add(source_iri)
        if has_complete_entities:
            derived.update(graph_derivations.get(key, set()))
        for source_iri in derived:
            graph.add((subject, PROV.wasDerivedFrom, source_iri))

    for key, version_row in versions_by_key.items():
        first_run_id = version_row.get("first_run_id")
        if first_run_id is not None:
            if first_run_id not in runs_by_id or not any(
                    row.get("run_id") == first_run_id for row in events_by_version[key]):
                raise ProvenanceCatalogError("graph-version first publisher has no matching run event")

    validate_provenance_catalog(graph)
    return graph


def build_provenance_catalog(store, *, require_source_run_ids: Iterable[str] = ()) -> Graph:
    """Read Core State and build its validated, deterministic RDF projection."""
    records = _input_rows(store)
    return build_provenance_catalog_from_records(*records,
                                                  require_source_run_ids=require_source_run_ids)


def validate_provenance_catalog(graph: Graph) -> None:
    """Fail closed on malformed or incomplete catalog RDF before publication."""
    if not isinstance(graph, Graph):
        raise ProvenanceCatalogError("catalog candidate must be an RDFLib Graph")
    for subject, predicate, obj in graph:
        if any(isinstance(term, BNode) for term in (subject, predicate, obj)):
            raise ProvenanceCatalogError("PROV catalog must not contain blank nodes")
        if not isinstance(subject, URIRef) or not isinstance(predicate, URIRef):
            raise ProvenanceCatalogError("PROV catalog subjects and predicates must be IRIs")
        for term in (subject, predicate, obj):
            if isinstance(term, URIRef) and not _absolute_iri(str(term)):
                raise ProvenanceCatalogError("PROV catalog contains an invalid IRI")

    activities = set(graph.subjects(RDF.type, PROV.Activity))
    entities = set(graph.subjects(RDF.type, PROV.Entity))
    for subject in activities:
        if not isinstance(subject, URIRef) or not str(subject).startswith(PROVENANCE_NAMESPACE + "run/"):
            raise ProvenanceCatalogError("run activities must use approved run identities")
        endpoints = list(graph.objects(subject, ETL.endpoint))
        if len(endpoints) != 1 or not isinstance(endpoints[0], Literal) or str(endpoints[0]) not in ENDPOINTS:
            raise ProvenanceCatalogError("run activity must identify exactly one known endpoint")
        for predicate in (ETL.etlVersion, ETL.ontologyVersion, ETL.mappingVersion):
            for value in graph.objects(subject, predicate):
                _check_no_secret_fields(str(value), "run version metadata")

    versions: set[URIRef] = set()
    sources: set[URIRef] = set()
    entity_versions: set[URIRef] = set()
    source_records: set[URIRef] = set()
    entity_graph_refs: list[URIRef] = []
    source_record_observations: list[URIRef] = []
    for subject in entities:
        if not isinstance(subject, URIRef):
            raise ProvenanceCatalogError("PROV entities must have IRI identities")
        subject_text = str(subject)
        fragment = urlsplit(subject_text).fragment
        if fragment.startswith("sha256="):
            payload_hash = _require_hash(fragment.removeprefix("sha256="), "catalog graph payload hash")
            base_graph = urlsplit(subject_text)._replace(fragment="").geturl()
            if graph_version_iri(base_graph, payload_hash) != subject:
                raise ProvenanceCatalogError("catalog graph version identity is not canonical")
            hashes = list(graph.objects(subject, ETL.payloadHash))
            endpoints = list(graph.objects(subject, ETL.endpoint))
            originals = list(graph.objects(subject, PROV.specializationOf))
            if (len(hashes) != 1 or str(hashes[0]) != payload_hash
                    or len(endpoints) != 1 or str(endpoints[0]) not in ENDPOINTS
                    or len(originals) != 1 or originals[0] != URIRef(base_graph)):
                raise ProvenanceCatalogError("published graph version lacks its canonical identity metadata")
            versions.add(subject)
        elif subject_text.startswith(PROVENANCE_NAMESPACE + "entity-version/"):
            graphs = list(graph.objects(subject, ETL.graphIRI))
            hashes = list(graph.objects(subject, ETL.payloadHash))
            endpoints = list(graph.objects(subject, ETL.endpoint))
            entities_iris = list(graph.objects(subject, ETL.publishedEntity))
            originals = list(graph.objects(subject, PROV.specializationOf))
            if (len(graphs) != 1 or len(hashes) != 1 or len(endpoints) != 1
                    or len(entities_iris) != 1 or len(originals) != 1
                    or str(endpoints[0]) not in _SHARED_ENTITY_TYPES
                    or not isinstance(graphs[0], URIRef)
                    or not isinstance(entities_iris[0], URIRef)
                    or originals[0] != entities_iris[0]):
                raise ProvenanceCatalogError(
                    "entity version lacks canonical graph/entity identity metadata")
            payload_hash = _require_hash(str(hashes[0]), "entity-version payload hash")
            graph_iri = str(graphs[0])
            entity_iri = str(entities_iris[0])
            if entity_version_iri(graph_iri, payload_hash, entity_iri) != subject:
                raise ProvenanceCatalogError("entity-version identity is not canonical")
            graph_ref = graph_version_iri(graph_iri, payload_hash)
            graph_endpoints = list(graph.objects(graph_ref, ETL.endpoint))
            if (len(graph_endpoints) != 1
                    or str(graph_endpoints[0]) != str(endpoints[0])):
                raise ProvenanceCatalogError("entity version graph has no owner endpoint metadata")
            entity_graph_refs.append(graph_ref)
            entity_versions.add(subject)
        elif subject_text.startswith(PROVENANCE_NAMESPACE + "source-record/"):
            observations = list(graph.objects(subject, ETL.sourceObservation))
            pointers = list(graph.objects(subject, ETL.evidencePointer))
            if (len(observations) != 1
                    or not str(observations[0]).startswith(PROVENANCE_NAMESPACE + "source/")
                    or len(pointers) != 1 or not isinstance(pointers[0], Literal)):
                raise ProvenanceCatalogError("source record evidence lacks its exact page and pointer")
            pointer = str(pointers[0])
            page_pointers = list(graph.objects(observations[0], ETL.evidencePointer))
            page, marker, fragment = pointer.partition("#")
            if (len(page_pointers) != 1 or page != str(page_pointers[0])
                    or not marker or not fragment.startswith("/")
                    or re.search(r"~(?![01])", fragment)):
                raise ProvenanceCatalogError(
                    "source record JSON pointer does not identify a record within its page")
            hashes = list(graph.objects(observations[0], ETL.sourceHash))
            observed = list(graph.objects(observations[0], ETL.observedAt))
            if (len(hashes) != 1 or len(observed) != 1
                    or source_record_evidence_iri(
                        str(hashes[0]), str(observed[0]), pointer) != subject):
                raise ProvenanceCatalogError("source record evidence identity is not canonical")
            source_record_observations.append(observations[0])
            source_records.add(subject)
        elif subject_text.startswith(PROVENANCE_NAMESPACE + "source/"):
            hashes = list(graph.objects(subject, ETL.sourceHash))
            observed = list(graph.objects(subject, ETL.observedAt))
            endpoints = list(graph.objects(subject, ETL.endpoint))
            requests = list(graph.objects(subject, ETL.requestParameters))
            if (len(hashes) != 1 or len(observed) != 1 or len(endpoints) != 1
                    or len(requests) != 1 or str(endpoints[0]) not in ENDPOINTS):
                raise ProvenanceCatalogError("source entity lacks its immutable observation metadata")
            source_hash = _require_hash(str(hashes[0]), "catalog source hash")
            observed_at = _timestamp(str(observed[0]), "catalog source observation time")
            if source_observation_iri(source_hash, observed_at) != subject:
                raise ProvenanceCatalogError("source entity identity is not keyed by hash and observation")
            if observed[0].datatype != XSD.dateTime:
                raise ProvenanceCatalogError("source observation time must be an xsd:dateTime")
            request = _json_object(str(requests[0]), "catalog request parameters")
            _check_no_secret_fields(request, "catalog request parameters")
            for pointer in graph.objects(subject, ETL.evidencePointer):
                _check_no_secret_fields(str(pointer), "catalog source evidence pointer")
            for source_url in graph.objects(subject, ETL.sourceURL):
                _safe_url(str(source_url), "catalog source URL")
            sources.add(subject)
        else:
            raise ProvenanceCatalogError(
                "PROV entity is neither a source observation, source record, graph version, nor entity version")

    if any(ref not in versions for ref in entity_graph_refs):
        raise ProvenanceCatalogError("entity version has no matching graph version entity")
    if any(ref not in sources for ref in source_record_observations):
        raise ProvenanceCatalogError("source record evidence refers to an unknown page observation")
    for subject in entity_versions:
        if not list(graph.objects(subject, PROV.wasGeneratedBy)):
            raise ProvenanceCatalogError("entity version has no publishing run")
        if not list(graph.objects(subject, PROV.wasDerivedFrom)):
            raise ProvenanceCatalogError("entity version has no source or prior-version derivation")
    for subject in source_records:
        observation = next(iter(graph.objects(subject, ETL.sourceObservation)))
        if set(graph.objects(subject, PROV.wasDerivedFrom)) != {observation}:
            raise ProvenanceCatalogError("source record evidence must derive from its exact page observation")

    for version in graph.subjects(PROV.wasGeneratedBy, None):
        if version not in versions | entity_versions:
            raise ProvenanceCatalogError(
                "only published graph or entity versions can be generated by a run")
        for run in graph.objects(version, PROV.wasGeneratedBy):
            if run not in activities:
                raise ProvenanceCatalogError("published version refers to an unknown run activity")
    for version in graph.subjects(PROV.wasDerivedFrom, None):
        if version not in versions | entity_versions | source_records:
            raise ProvenanceCatalogError(
                "only published versions and record evidence can have derivations")
        for source in graph.objects(version, PROV.wasDerivedFrom):
            if source not in sources | entity_versions | source_records:
                raise ProvenanceCatalogError("version derives from an unknown provenance entity")
    for activity in graph.subjects(PROV.used, None):
        if activity not in activities:
            raise ProvenanceCatalogError("only run activities may use source observations")
        for source in graph.objects(activity, PROV.used):
            if source not in sources:
                raise ProvenanceCatalogError("run activity uses an unknown source observation")


def publish_provenance_catalog(
    graph: Graph,
    *,
    publication_boundary: ProvenancePublicationBoundary,
    loader,
    client,
) -> str:
    """Replace the catalog only through dirty -> whole-graph verify -> clean.

    The boundary is intentionally injected: the existing CoreStateStore APIs
    do not own the fixed provenance graph, so the parent session must provide
    callbacks implemented within Core State rather than introducing ad-hoc SQL
    here.  A failed PUT/verification leaves its durable dirty state untouched.
    """
    validate_provenance_catalog(graph)
    payload = ntriples(graph)
    payload_hash = sha256(payload.encode("utf-8"))
    marked_hash = publication_boundary.mark_dirty(PROVENANCE_GRAPH_IRI, payload)
    if marked_hash != payload_hash:
        raise ProvenanceCatalogError("Core State dirty marker returned the wrong catalog payload hash")
    loader.replace(PROVENANCE_GRAPH_IRI, payload, content_type="application/n-triples")
    from .competency import verify_core_graph

    verify_core_graph(client, PROVENANCE_GRAPH_IRI, payload)
    publication_boundary.mark_clean(PROVENANCE_GRAPH_IRI, payload_hash)
    return payload_hash


def build_and_publish_provenance_catalog(
    store,
    *,
    publication_boundary: ProvenancePublicationBoundary,
    loader,
    client,
    require_source_run_ids: Iterable[str],
) -> str:
    """Build and validate before publication, requiring evidence for new runs.

    The caller must identify the core ETL run(s) whose new publications are
    being projected. Historical projection/replay should use
    :func:`build_provenance_catalog` directly and does not invent missing raw
    pointers.
    """
    graph = build_provenance_catalog(
        store, require_source_run_ids=require_source_run_ids)
    return publish_provenance_catalog(
        graph, publication_boundary=publication_boundary, loader=loader, client=client)


__all__ = [
    "ETL", "ProvenanceCatalogError", "ProvenancePublicationBoundary",
    "build_and_publish_provenance_catalog", "build_provenance_catalog",
    "build_provenance_catalog_from_records", "entity_version_iri", "file_version",
    "graph_version_iri", "package_version", "publish_provenance_catalog", "sha256",
    "shared_graph_entity_iris", "source_observation_iri",
    "source_record_evidence_iri", "validate_provenance_catalog",
]
