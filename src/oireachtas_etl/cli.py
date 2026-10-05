from __future__ import annotations
import argparse, json, sys, uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
from .api import ApiClient, HousesApiClient
from .config import (ADMINISTRATIVE_UNITS_GRAPH, COMMITTEES_GRAPH,
                     CONSTITUENCIES_GRAPH, HOUSES_GRAPH,
                     OFFICES_GRAPH, OFFICE_REGISTRY_FILE, OFFICE_DECISIONS_FILE,
                     OFFICE_OCCURRENCE_STATE_DB_FILE, PARTIES_GRAPH,
                     REFERENCE_ONTOLOGY_VERSION, Settings)
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_member_competency, verify_bill_competency
from .competency import verify_core_graph
from .raw import persist_raw
from .serialization import nquads, ntriples, turtle
from .transforms.houses import transform_houses_with_report
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
from .transforms.common import MEMBERS, datetime_literal
from .transforms.offices import office_iri
from .transforms.bills import bill_graph_iri, source_hash as bill_source_hash, transform_bill_with_report
from .validation.bills import validate_bill_source
from .state import CoreStateStore, expected_graph_iri, state_lock
from rdflib import Graph, URIRef
from rdflib.namespace import RDF
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
from .reference_coverage import build_reference_census, summary as reference_census_summary
from .reference_closure import (candidate_member_dataset,
                                verify_reference_closure)
from .reference_publication import build_reference_candidates
from .raw_captures import load_latest_complete_capture


MEMBER_MAPPING_VERSION = "member_mapping.csv@reference-coverage-2026"


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
    if args.fixture:
        records, body = _records_from_fixture(Path(args.fixture))
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body,
                    status=200, retrieved_at=datetime.now(timezone.utc), ontology_version=settings.ontology_version, mapping_version=settings.mapping_version,
                    extraction_id=run_id)
    else:
        records, pages = [], []
        for page in HousesApiClient(settings.api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=settings.api_url, params=page.params, body=page.body, status=page.status, ontology_version=settings.ontology_version, mapping_version=settings.mapping_version, extraction_id=run_id)
            decoded = json.loads(page.body); records.extend(decoded.get("results", decoded) if isinstance(decoded, dict) else decoded)
    graph, exclusions = transform_houses_with_report(records)
    validate_houses(records, graph)  # deliberately before any loader construction/invocation
    if args.output_ttl: Path(args.output_ttl).write_text(turtle(graph), encoding="utf-8")
    payload = nquads(graph, HOUSES_GRAPH)
    if args.output_nq: Path(args.output_nq).write_text(payload, encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint:
        if not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load whole-graph verification")
        payload = ntriples(graph)
        if store is None: raise RuntimeError("online Houses publication requires durable core ETL state")
        digest = store.mark_endpoint_dirty("houses", HOUSES_GRAPH, payload)
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout).replace(HOUSES_GRAPH, payload, content_type="application/n-triples")
        verify_core_graph(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout), HOUSES_GRAPH, payload)
        store.complete_endpoint_publication("houses", HOUSES_GRAPH, digest)
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(records), "excluded": exclusions, "published": bool(endpoint)}, sort_keys=True))
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
                                                  "limit": settings.limit})
            try:
                result = operation(args, store, run_id)
            except Exception as error:
                store.finish_run(run_id, success=False, error=f"{type(error).__name__}: {error}")
                raise
            store.finish_run(run_id, success=True)
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
                      member_is_authoritative: bool) -> tuple[dict, dict]:
    """Assemble current and latest complete source observations deterministically."""
    member_evidence = None
    if member_records is None and store is not None:
        loaded = load_latest_complete_capture(raw_root, store, "members")
        if loaded is not None:
            member_records, member_evidence = loaded
            member_is_authoritative = True
    member_records = member_records or []

    sources: dict[str, tuple[list[dict], bool]] = {}
    for endpoint in ("parties", "constituencies"):
        if endpoint == endpoint_name and endpoint_records is not None:
            sources[endpoint] = (endpoint_records, endpoint_is_authoritative)
            continue
        loaded = (load_latest_complete_capture(raw_root, store, endpoint)
                  if store is not None else None)
        sources[endpoint] = ((loaded[0], True) if loaded is not None else ([], False))
    result = build_reference_census(
        member_records=member_records,
        party_records=sources["parties"][0],
        constituency_records=sources["constituencies"][0],
        member_capture_complete=member_is_authoritative,
        party_capture_complete=sources["parties"][1],
        constituency_capture_complete=sources["constituencies"][1],
    )
    provenance = {
        "members": member_evidence,
        "parties": sources["parties"][1],
        "constituencies": sources["constituencies"][1],
    }
    return result, provenance


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
                               loader: FusekiGraphStoreLoader) -> dict[str, Graph]:
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
                coverage_authoritative=metadata.get("pending_coverage_authoritative"))
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
                              member_source_run_id: str | None = None) -> int:
    _assert_reference_source_not_older(store, endpoints, member_source_run_id)
    published = 0
    for endpoint_name in endpoints:
        graph_iri = REFERENCE_GRAPHS[endpoint_name]
        payload = ntriples(graphs[endpoint_name])
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
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
        if (prior and prior.get("publication_state") == "clean"
                and prior.get("graph_iri") == graph_iri
                and prior.get("published_payload_hash") == payload_hash
                and prior.get("published_payload") == payload
                and authority_already_recorded):
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
            member_source_run_id=member_source_run_id)
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        verify_core_graph(client, graph_iri, payload)
        store.complete_endpoint_publication(
            endpoint_name, graph_iri, digest,
            coverage_authoritative=coverage_authoritative)
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
    if args.fixture:
        records, body = _reference_fixture_records(Path(args.fixture), endpoint_name)
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body,
                    status=200, retrieved_at=datetime.now(timezone.utc), ontology_version=REFERENCE_ONTOLOGY_VERSION,
                    mapping_version=mapping_version, endpoint_name=endpoint_name, extraction_id=run_id)
    else:
        records = []
        api_url = getattr(settings, url_attr)
        count_field = {"parties": "partyCount",
                       "constituencies": "constituencyCount"}[endpoint_name]
        advertised = None
        for page in ApiClient(api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=api_url, params=page.params, body=page.body, status=page.status,
                    ontology_version=REFERENCE_ONTOLOGY_VERSION, mapping_version=mapping_version, endpoint_name=endpoint_name,
                    extraction_id=run_id)
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise ValueError(f"every {endpoint_name} API page must contain a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get(count_field) if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"every {endpoint_name} API page must contain a nonnegative integer {count_field}")
            if advertised is None:
                advertised = count
            elif count != advertised:
                raise ValueError(f"{endpoint_name} advertised count changed during scan")
            page_records = decoded.get("results", decoded) if isinstance(decoded, dict) else decoded
            records.extend(page_records)
        if advertised is None or advertised != len(records):
            raise ValueError(
                f"{endpoint_name} capture contains {len(records)} records, not its advertised {advertised}")
    source_graph = transform(records)
    validator(records, source_graph)  # source gate precedes any loader construction

    census, provenance = _reference_inputs(
        endpoint_name=endpoint_name, endpoint_records=records, member_records=None,
        store=store, raw_root=settings.raw_dir,
        endpoint_is_authoritative=not bool(args.fixture),
        member_is_authoritative=False,
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
        previous = _previous_reference_graphs(store, client, loader)
        candidates = build_reference_candidates(
            census, member_graph=member_graph, previous_graphs=previous)
        publish_all = bool(not args.fixture and provenance["members"] is not None)
        publish_set = (("parties", "constituencies", "committees") if publish_all
                       else (endpoint_name,))
        published_graphs = _publish_reference_graphs(
            candidates["graphs"], store=store, loader=loader, client=client,
            coverage_authoritative=(True if publish_all else
                                    False if args.fixture else None),
            endpoints=publish_set,
            member_source_run_id=member_source_run_id)
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
    else:
        if store is None:
            raise ValueError("Committee owner generation requires a complete Members capture")
        loaded = load_latest_complete_capture(settings.raw_dir, store, "members")
        if loaded is None:
            raise ValueError("Committee owner generation requires a successful complete Members API run")
        member_records = loaded[0]
        member_source_run_id = loaded[1]["run_id"]
        complete_fixture = False

    census, provenance = _reference_inputs(
        endpoint_name="committees", endpoint_records=None,
        member_records=member_records, store=store, raw_root=settings.raw_dir,
        endpoint_is_authoritative=False,
        member_is_authoritative=not bool(args.fixture),
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
        previous = _previous_reference_graphs(store, client, loader)
        candidates = build_reference_candidates(
            census, member_graph=member_graph, previous_graphs=previous)
        published = _publish_reference_graphs(
            candidates["graphs"], store=store, loader=loader, client=client,
            coverage_authoritative=True,
            member_source_run_id=member_source_run_id,
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
    if advertised is not None and (isinstance(advertised, bool) or not isinstance(advertised, int) or advertised != len(unique)):
        raise ValueError(f"Members unique count {len(unique)} does not match advertised count {advertised!r}")
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
    records_with_pointers: list[tuple[dict, dict]] = []
    if args.fixture:
        fixture = Path(args.fixture)
        records, body, advertised, shape = _office_fixture_records(fixture)
        raw_path, _ = persist_raw(root=raw_root, endpoint=str(fixture.resolve()),
                    params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=datetime.now(timezone.utc), ontology_version=REFERENCE_ONTOLOGY_VERSION,
                     mapping_version=MEMBER_MAPPING_VERSION,
                    endpoint_name="members", extraction_id=extraction_id)
        for index, wrapper in enumerate(records):
            pointer = "" if shape == "single" else (
                f"/results/{index}" if shape == "results" else f"/{index}")
            records_with_pointers.append((
                wrapper, _office_raw_pointer(raw_path, raw_root, body, pointer)))
    else:
        records, advertised = [], None
        for page in ApiClient(settings.members_api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            raw_path, _ = persist_raw(root=raw_root, endpoint=settings.members_api_url, params=page.params, body=page.body, status=page.status,
                        ontology_version=REFERENCE_ONTOLOGY_VERSION, mapping_version=MEMBER_MAPPING_VERSION, endpoint_name="members", extraction_id=extraction_id)
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise ValueError("every Members API page must be an object envelope with a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get("memberCount") if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("every Members API page must contain a nonnegative integer head.counts.memberCount")
            page_records = decoded["results"]
            records.extend(page_records)
            for index, wrapper in enumerate(page_records):
                records_with_pointers.append((
                    wrapper, _office_raw_pointer(
                        raw_path, raw_root, page.body, f"/results/{index}")))
            if advertised is None: advertised = count
            elif count != advertised: raise ValueError("Members advertised count changed during scan")
    records = _deduplicate_members(records, advertised)
    complete_scan = (not args.fixture or
                     (advertised is not None and advertised == len(records)))
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
    for wrapper in records:
        member = wrapper["member"]; identity, digest, graph_iri = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member["uri"])), source_hash(member), member_graph_iri(member)
        prior = store.get_resource("members", identity) if store is not None else None
        old = (store.observe_resource("members", identity, graph_iri, digest, run_id)
               if store is not None and run_id is not None else {})
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
        reference_census, _reference_provenance = _reference_inputs(
            endpoint_name="members", endpoint_records=None,
            member_records=records, store=store, raw_root=raw_root,
            endpoint_is_authoritative=False,
            member_is_authoritative=True,
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
        if reference_candidates is not None:
            if store is None:
                raise RuntimeError("authoritative Member reference publication requires durable core ETL state")
            previous = _previous_reference_graphs(store, client, loader)
            reference_candidates = build_reference_candidates(
                reference_census, member_graph=member_candidate_graph,
                previous_graphs=previous)
            _publish_reference_graphs(
                reference_candidates["graphs"], store=store, loader=loader,
                client=client, coverage_authoritative=True,
                member_source_run_id=(extraction_id if store is not None
                                      and complete_scan and not args.fixture else None))
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
    return 0


def _run_members(args: argparse.Namespace, store: CoreStateStore | None = None,
                 reconciliation_store: ReconciliationStore | None = None,
                 office_store: OfficeOccurrenceStore | None = None) -> int:
    if store is None:
        return _run_members_impl(args)
    settings = Settings.from_environment()
    run_id = store.start_run("members", "full_refresh", is_complete=True,
                             parameters={"source": "fixture" if args.fixture else "api",
                                         "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                         "api_url": None if args.fixture else settings.members_api_url,
                                         "limit": settings.limit})
    try:
        result = _run_members_impl(args, store, run_id, reconciliation_store,
                                   office_store)
    except Exception as error:
        store.finish_run(run_id, success=False, error=f"{type(error).__name__}: {error}")
        raise
    store.finish_run(run_id, success=True)
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
    if advertised is not None and (isinstance(advertised, bool) or not isinstance(advertised, int) or advertised != len(unique)):
        raise ValueError(f"Bills unique count {len(unique)} does not match advertised count {advertised!r}")
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


def _run_bills_impl(args: argparse.Namespace, store: CoreStateStore | None = None,
                    run_id: str | None = None, *, window_start: datetime | None = None,
                    upper: datetime | None = None, complete: bool = True) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    if args.fixture:
        records, body, advertised = _bills_fixture_records(Path(args.fixture))
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=datetime.now(timezone.utc), ontology_version="legislation.owl.ttl@phase-4-legislative-lifecycle-2026", mapping_version="bill_mapping.csv@phase-4-legislative-lifecycle-2026", endpoint_name="legislation", extraction_id=run_id)
    else:
        records, advertised = [], None
        query = {"last_updated": window_start.isoformat()} if window_start else None
        client = ApiClient(settings.bills_api_url, retries=settings.retries, timeout=settings.timeout)
        pages = client.harvest(limit=settings.limit, query_params=query) if query else client.harvest(limit=settings.limit)
        for page in pages:
            persist_raw(root=settings.raw_dir, endpoint=settings.bills_api_url, params=page.params, body=page.body, status=page.status, retrieved_at=datetime.now(timezone.utc), ontology_version="legislation.owl.ttl@phase-4-legislative-lifecycle-2026", mapping_version="bill_mapping.csv@phase-4-legislative-lifecycle-2026", endpoint_name="legislation", extraction_id=run_id)
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list): raise ValueError("every Legislation API page must be an object envelope with a results list")
            count = decoded.get("head", {}).get("counts", {}).get("billCount") if isinstance(decoded.get("head"), dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0: raise ValueError("every Legislation API page must contain a nonnegative integer head.counts.billCount")
            if advertised is None: advertised = count
            elif advertised != count: raise ValueError("Bills advertised count changed during scan")
            records.extend(decoded["results"])
    if not complete:
        # The API may interpret last_updated at day granularity and does not
        # guarantee an upper filter. Keep the fixed run boundary locally.
        if advertised is not None and len(records) != advertised:
            raise ValueError("Legislation incremental extraction count changed during scan")
        records = [record for record in records if _bill_source_time(record) <= upper]
        records = _deduplicate_bills(records, None, allow_empty=True)
    else:
        records = _deduplicate_bills(records, advertised,
                                     allow_empty=bool(store is not None and complete and advertised == 0))
    work = []
    for wrapper in records:
        bill = wrapper["bill"]; identity, digest, graph_iri = bill["uri"], bill_source_hash(bill), bill_graph_iri(bill)
        prior = store.get_resource("legislation", identity) if store is not None else None
        old = (store.observe_resource("legislation", identity, graph_iri, digest, run_id)
               if store is not None and run_id is not None else {})
        # Hash-first source gate; unchanged Bills never construct RDF or invoke a loader.
        omissions = validate_bill_source(wrapper)
        if (not args.offline and old.get("publication_state") == "clean"
                and old.get("contract_version") == 1
                and old.get("published_source_hash") == digest and old.get("graph_iri") == graph_iri):
            work.append((wrapper, None, identity, digest, omissions, "skipped")); continue
        graph, report = transform_bill_with_report(wrapper); validate_bill(wrapper, graph)
        work.append((wrapper, graph, identity, digest, report, "changed" if prior else "new"))
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
    print(json.dumps({"records": len(records), "published": published, "skipped": skipped, "new": identities["new"], "changed": identities["changed"], "skipped_identities": identities["skipped"], "omitted": [item for *_, report, _ in work for item in report]}, sort_keys=True))
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
    run_id = store.start_run("legislation", ("complete_source_reconciliation" if authoritative_scan
                                                   else "full_refresh") if complete else "incremental_refresh",
                             is_complete=complete and authoritative_scan,
                             parameters={"source": "fixture" if args.fixture else "api",
                                         "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                         "api_url": None if args.fixture else settings.bills_api_url,
                                         "limit": settings.limit, "cursor_before": previous,
                                         "window_start": window_start.isoformat() if window_start else None,
                                         "upper_boundary": upper.isoformat(), "overlap_seconds": overlap,
                                         "complete": complete})
    try:
        result = _run_bills_impl(args, store, run_id, window_start=window_start,
                                 upper=upper, complete=complete)
    except Exception as error:
        store.finish_run(run_id, success=False, error=f"{type(error).__name__}: {error}")
        raise
    # A developer fixture can exercise publication, but cannot attest to the
    # completeness or source-time boundary of the authoritative API dataset.
    store.finish_run(run_id, success=True,
                     incremental_cursor=upper.isoformat() if authoritative_scan and not complete else None,
                     complete_scan=complete and authoritative_scan)
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
    else:
        settings = Settings.from_environment()
        records, advertised = [], None
        for page in ApiClient(settings.members_api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise ValueError("every Members API page must be an object envelope with a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get("memberCount") if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("every Members API page must contain a nonnegative integer head.counts.memberCount")
            if advertised is None:
                advertised = count
            elif advertised != count:
                raise ValueError("Members advertised count changed during scan")
            records.extend(decoded["results"])
    records = _deduplicate_members(records, advertised)
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
    else:
        settings = Settings.from_environment()
        records, advertised = [], None
        for page in ApiClient(settings.parties_api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise ValueError("every Parties API page must be an object envelope with a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get("partyCount") if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("every Parties API page must contain a nonnegative integer head.counts.partyCount")
            if advertised is None:
                advertised = count
            elif count != advertised:
                raise ValueError("Parties advertised count changed during scan")
            records.extend(decoded["results"])
    records = deduplicate_party_records(records, advertised)
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
            for index, wrapper in enumerate(decoded["results"]):
                records_with_pointers.append((
                    wrapper, _office_raw_pointer(raw_path, raw_root, page.body, f"/results/{index}")))

    # Reuse the established duplicate/collision/count rules without discarding
    # duplicate raw contexts before office observations are extracted.
    _deduplicate_members([wrapper for wrapper, _pointer in records_with_pointers], advertised)
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


def run_state_status(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    state_db = Path(getattr(args, "state_db", None) or settings.core_state_db_file).expanduser()
    with CoreStateStore(state_db, legacy_members=settings.members_legacy_state_file,
                        legacy_bills=settings.bills_legacy_state_file) as store:
        print(json.dumps(store.status(), sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oir-etl")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses", "parties", "constituencies", "committees", "administrative-units", "offices", "members", "bills"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
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
    reconcile = sub.add_parser("reconcile"); reconcile.add_argument("endpoint", choices=["members", "parties", "institutions", "offices", "office-external"])
    reconcile.add_argument("--fixture"); reconcile.add_argument("--responses-file"); reconcile.add_argument("--offline", action="store_true"); reconcile.add_argument("--all", action="store_true"); reconcile.add_argument("--publish", action="store_true"); reconcile.add_argument("--output-nq"); reconcile.add_argument("--fuseki-gsp-url"); reconcile.add_argument("--fuseki-sparql-url")
    reconcile.add_argument("--review-file", help="review JSON (defaults to the endpoint-specific version-controlled review file)")
    reconcile.add_argument("--reconciliation-state-file", help="shared reconciliation SQLite path (defaults to the Phase 3.5 state file)")
    reconcile.add_argument("--registry-file", help="versioned local office/unit registry JSON")
    reconcile.add_argument("--office-state-file", help="durable SQLite office observation/evidence ledger")
    reconcile.add_argument("--raw-dir", help="immutable raw response root for office source scans")
    args = parser.parse_args(argv)
    if args.command == "state": return run_state_status(args)
    if args.command == "reconcile":
        if args.endpoint == "offices": return run_reconcile_offices(args)
        if args.endpoint == "office-external": return run_reconcile_office_external(args)
        if args.endpoint == "parties": return run_reconcile_parties(args)
        if args.endpoint == "institutions": return run_reconcile_institutions(args)
        return run_reconcile_members(args)
    if args.endpoint == "houses": return run_houses(args)
    if args.endpoint == "members": return run_members(args)
    if args.endpoint == "bills": return run_bills(args)
    if args.endpoint in {"administrative-units", "offices"}: return run_office_registry(args)
    return run_reference(args)

if __name__ == "__main__": raise SystemExit(main())
