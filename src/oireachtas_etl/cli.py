from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
from .api import ApiClient, HousesApiClient
from .config import CONSTITUENCIES_GRAPH, HOUSES_GRAPH, PARTIES_GRAPH, REFERENCE_ONTOLOGY_VERSION, Settings
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_constituencies_competency, verify_houses_competency, verify_parties_competency, verify_member_competency, verify_bill_competency
from .competency import verify_core_graph
from .raw import persist_raw
from .serialization import nquads, ntriples, turtle
from .transforms.houses import transform_houses_with_report
from .transforms.parties import transform_parties
from .transforms.constituencies import transform_constituencies
from .validation import validate_constituencies, validate_houses, validate_parties
from .validation import validate_member, validate_bill
from .validation.members import validate_member_source
from .transforms.members import member_graph_iri, source_hash, transform_member_with_report
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
                              reconcile_institution_records, reconciliation_identity)


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
        if not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
        payload = ntriples(graph)
        if store is None: raise RuntimeError("online Houses publication requires durable core ETL state")
        digest = store.mark_endpoint_dirty("houses", HOUSES_GRAPH, payload)
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout).replace(HOUSES_GRAPH, payload, content_type="application/n-triples")
        verify_houses_competency(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout))
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
            run_id = store.start_run(endpoint_name, "full_refresh", is_complete=True,
                                     parameters={"source": "fixture" if args.fixture else "api",
                                                 "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                                 "api_url": None if args.fixture else getattr(settings, {
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
    "parties": (PARTIES_GRAPH, "parties_api_url", transform_parties, validate_parties, verify_parties_competency, "party_mapping.csv@phase-2-reference-data-2026"),
    "constituencies": (CONSTITUENCIES_GRAPH, "constituencies_api_url", transform_constituencies, validate_constituencies, verify_constituencies_competency, "constituencies_mapping.csv@phase-2-reference-data-2026"),
}


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
    graph_iri, url_attr, transform, validator, competency, mapping_version = REFERENCE_ENDPOINTS[endpoint_name]
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
        for page in ApiClient(api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=api_url, params=page.params, body=page.body, status=page.status,
                    ontology_version=REFERENCE_ONTOLOGY_VERSION, mapping_version=mapping_version, endpoint_name=endpoint_name,
                    extraction_id=run_id)
            decoded = json.loads(page.body)
            page_records = decoded.get("results", decoded) if isinstance(decoded, dict) else decoded
            records.extend(page_records)
    graph = transform(records)
    validator(records, graph)  # deliberately before any loader construction/invocation
    if args.output_ttl:
        Path(args.output_ttl).write_text(turtle(graph), encoding="utf-8")
    payload = nquads(graph, graph_iri)
    if args.output_nq:
        Path(args.output_nq).write_text(payload, encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint:
        if not query_endpoint:
            raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
        payload = ntriples(graph)
        if store is None: raise RuntimeError("online reference publication requires durable core ETL state")
        digest = store.mark_endpoint_dirty(endpoint_name, graph_iri, payload)
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout).replace(graph_iri, payload, content_type="application/n-triples")
        competency(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout))
        store.complete_endpoint_publication(endpoint_name, graph_iri, digest)
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
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(records), "published": bool(endpoint)}, sort_keys=True))
    return 0


def run_reference(args: argparse.Namespace) -> int:
    return _run_shared(args, args.endpoint, _run_reference_impl)


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
                      reconciliation_store: ReconciliationStore | None = None) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    if args.fixture:
        records, body, advertised = _members_fixture_records(Path(args.fixture))
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=datetime.now(timezone.utc), ontology_version=REFERENCE_ONTOLOGY_VERSION,
                    mapping_version="member_mapping.csv@phase-3-members-2026", endpoint_name="members", extraction_id=run_id)
    else:
        records, advertised = [], None
        for page in ApiClient(settings.members_api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=settings.members_api_url, params=page.params, body=page.body, status=page.status,
                        ontology_version=REFERENCE_ONTOLOGY_VERSION, mapping_version="member_mapping.csv@phase-3-members-2026", endpoint_name="members", extraction_id=run_id)
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list):
                raise ValueError("every Members API page must be an object envelope with a results list")
            counts = decoded.get("head", {}).get("counts") if isinstance(decoded.get("head"), dict) else None
            count = counts.get("memberCount") if isinstance(counts, dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("every Members API page must contain a nonnegative integer head.counts.memberCount")
            page_records = decoded["results"]
            records.extend(page_records)
            if advertised is None: advertised = count
            elif count != advertised: raise ValueError("Members advertised count changed during scan")
    records = _deduplicate_members(records, advertised)
    graphs: list[tuple[dict, object | None, str, str, list[dict], str]] = []
    for wrapper in records:
        member = wrapper["member"]; identity, digest, graph_iri = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member["uri"])), source_hash(member), member_graph_iri(member)
        prior = store.get_resource("members", identity) if store is not None else None
        old = (store.observe_resource("members", identity, graph_iri, digest, run_id)
               if store is not None and run_id is not None else {})
        # Hash-first: unchanged published records do not enter transformation.
        omissions = validate_member_source(wrapper)
        if (not args.offline and old.get("publication_state", "clean") == "clean"
                and old.get("contract_version") == 2
                and old.get("published_source_hash") == digest and old.get("graph_iri") == graph_iri):
            graphs.append((wrapper, None, identity, digest, omissions, "skipped")); continue
        graph, exclusions = transform_member_with_report(wrapper); validate_member(wrapper, graph)
        graphs.append((wrapper, graph, identity, digest, exclusions, "changed" if prior else "new"))
    if args.output_nq:
        Path(args.output_nq).write_text("".join(nquads(graph, graph_iri) for wrapper, graph, identity, digest, exclusions, _ in graphs if graph is not None for graph_iri in [member_graph_iri(wrapper["member"])]), encoding="utf-8")
    if getattr(args, "output_ttl", None):
        Path(args.output_ttl).write_text("\n".join(turtle(graph) for _, graph, _, _, _, _ in graphs if graph is not None), encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint and not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
    published = skipped = 0
    repaired: list[str] = []
    seen = {identity for _, _, identity, _, _, _ in graphs}
    known = store.resources("members") if store is not None else []
    missing = sorted(row["resource_iri"] for row in known if row["resource_iri"] not in seen)
    if endpoint:
        if store is None:
            raise RuntimeError("online Member publication requires durable core ETL state")
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        for wrapper, graph, identity, digest, exclusions, status in graphs:
            if graph is None:
                prior = store.get_resource("members", identity)
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
                graph, exclusions = transform_member_with_report(wrapper); validate_member(wrapper, graph)
                repaired.append(identity)
            graph_iri = member_graph_iri(wrapper["member"])
            payload = ntriples(graph)
            payload_hash = store.mark_publication_dirty("members", identity, source_hash=digest,
                                                        graph_iri=graph_iri, payload=payload,
                                                        contract_version=2)
            loader.replace(graph_iri, payload, content_type="application/n-triples")
            verify_member_competency(client, graph_iri, identity, len(graph))
            verify_core_graph(client, graph_iri, payload)
            store.complete_publication("members", identity, source_hash=digest, graph_iri=graph_iri,
                                       payload_hash=payload_hash, contract_version=2)
            _try_mark_due(reconciliation_store, "member", wrapper, force=status == "new")
            published += 1
        for row in known:
            if row["resource_iri"] in seen or row["publication_state"] != "dirty":
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
    print(json.dumps({"records": len(records), "published": published, "skipped": skipped, "new": identities["new"], "changed": identities["changed"], "skipped_identities": identities["skipped"], "missing_retained": missing, "future_work_omitted": report}, sort_keys=True))
    return 0


def _run_members(args: argparse.Namespace, store: CoreStateStore | None = None,
                 reconciliation_store: ReconciliationStore | None = None) -> int:
    if store is None:
        return _run_members_impl(args)
    settings = Settings.from_environment()
    run_id = store.start_run("members", "full_refresh", is_complete=True,
                             parameters={"source": "fixture" if args.fixture else "api",
                                         "fixture": str(Path(args.fixture).resolve()) if args.fixture else None,
                                         "api_url": None if args.fixture else settings.members_api_url,
                                         "limit": settings.limit})
    try:
        result = _run_members_impl(args, store, run_id, reconciliation_store)
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
    with state_lock(state_db):
        with CoreStateStore(state_db, legacy_members=legacy_members,
                            legacy_bills=settings.bills_legacy_state_file) as store:
            endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
            if not endpoint:
                return _run_members(args, store)
            try:
                reconciliation_store = ReconciliationStore(_reconciliation_state_path(args, settings))
            except Exception as error:
                _handoff_warning("member", error)
                return _run_members(args, store)
            try:
                return _run_members(args, store, reconciliation_store)
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
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses", "parties", "constituencies", "members", "bills"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
    run.add_argument("--state-db", help="shared authoritative core ETL SQLite database")
    run.add_argument("--reconciliation-state-file",
                     help="existing external-reconciliation SQLite database (shared with reconcile commands)")
    run.add_argument("--full", action="store_true", help="complete Bills source reconciliation")
    run.add_argument("--overlap-seconds", type=int, help="Bills cursor overlap (default: 3600)")
    run.add_argument("--legacy-state-file", "--state-file", dest="legacy_state_file",
                     help="read-only legacy Member/Bill JSON manifest to import once")
    run.add_argument("--output-ttl"); run.add_argument("--output-nq"); run.add_argument("--fuseki-gsp-url"); run.add_argument("--fuseki-sparql-url")
    state = sub.add_parser("state"); state_sub = state.add_subparsers(dest="state_command", required=True)
    state_status = state_sub.add_parser("status"); state_status.add_argument("--state-db")
    reconcile = sub.add_parser("reconcile"); reconcile.add_argument("endpoint", choices=["members", "parties", "institutions"])
    reconcile.add_argument("--fixture"); reconcile.add_argument("--responses-file"); reconcile.add_argument("--offline", action="store_true"); reconcile.add_argument("--all", action="store_true"); reconcile.add_argument("--publish", action="store_true"); reconcile.add_argument("--output-nq"); reconcile.add_argument("--fuseki-gsp-url"); reconcile.add_argument("--fuseki-sparql-url")
    reconcile.add_argument("--review-file", help="review JSON (defaults to the endpoint-specific version-controlled review file)")
    reconcile.add_argument("--reconciliation-state-file", help="shared reconciliation SQLite path (defaults to the Phase 3.5 state file)")
    args = parser.parse_args(argv)
    if args.command == "state": return run_state_status(args)
    if args.command == "reconcile":
        if args.endpoint == "parties": return run_reconcile_parties(args)
        if args.endpoint == "institutions": return run_reconcile_institutions(args)
        return run_reconcile_members(args)
    if args.endpoint == "houses": return run_houses(args)
    if args.endpoint == "members": return run_members(args)
    if args.endpoint == "bills": return run_bills(args)
    return run_reference(args)

if __name__ == "__main__": raise SystemExit(main())
