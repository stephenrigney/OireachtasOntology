from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from .api import ApiClient, HousesApiClient
from .config import CONSTITUENCIES_GRAPH, HOUSES_GRAPH, PARTIES_GRAPH, REFERENCE_ONTOLOGY_VERSION, Settings
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_constituencies_competency, verify_houses_competency, verify_parties_competency, verify_member_competency, verify_bill_competency
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
from .state import load_manifest, load_bills_manifest, write_manifest, manifest_lock
from .reconciliation import (DbpediaClient, ReconciliationStore, WikidataClient,
                              FixtureResponseError, external_graph_iri, party_external_graph_iri,
                              load_party_review, load_review, normalize_party_candidate,
                              deduplicate_party_records, reconcile_party_records, reconcile_records, valid_qid)

def _records_from_fixture(path: Path) -> tuple[list[dict], bytes]:
    body = path.read_bytes()
    value = json.loads(body)
    if not isinstance(value, list): raise ValueError("fixture must be a JSON array")
    return value, body

def run_houses(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    if args.fixture:
        records, body = _records_from_fixture(Path(args.fixture))
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body,
                    status=200, retrieved_at=datetime.now(timezone.utc), ontology_version=settings.ontology_version, mapping_version=settings.mapping_version)
    else:
        records, pages = [], []
        for page in HousesApiClient(settings.api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=settings.api_url, params=page.params, body=page.body, status=page.status, ontology_version=settings.ontology_version, mapping_version=settings.mapping_version)
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
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout).replace(HOUSES_GRAPH, ntriples(graph), content_type="application/n-triples")
        verify_houses_competency(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout))
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(records), "excluded": exclusions, "published": bool(endpoint)}, sort_keys=True))
    return 0


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


def run_reference(args: argparse.Namespace) -> int:
    endpoint_name = args.endpoint
    graph_iri, url_attr, transform, validator, competency, mapping_version = REFERENCE_ENDPOINTS[endpoint_name]
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir})
    if args.fixture:
        records, body = _reference_fixture_records(Path(args.fixture), endpoint_name)
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body,
                    status=200, retrieved_at=datetime.now(timezone.utc), ontology_version=REFERENCE_ONTOLOGY_VERSION,
                    mapping_version=mapping_version, endpoint_name=endpoint_name)
    else:
        records = []
        api_url = getattr(settings, url_attr)
        for page in ApiClient(api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=api_url, params=page.params, body=page.body, status=page.status,
                        ontology_version=REFERENCE_ONTOLOGY_VERSION, mapping_version=mapping_version, endpoint_name=endpoint_name)
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
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout).replace(graph_iri, ntriples(graph), content_type="application/n-triples")
        competency(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout))
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(records), "published": bool(endpoint)}, sort_keys=True))
    return 0


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


def _run_members(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir,
                           "members_state_file": Path(args.state_file) if args.state_file else settings.members_state_file})
    if args.fixture:
        records, body, advertised = _members_fixture_records(Path(args.fixture))
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=datetime.now(timezone.utc), ontology_version=REFERENCE_ONTOLOGY_VERSION,
                    mapping_version="member_mapping.csv@phase-3-members-2026", endpoint_name="members")
    else:
        records, advertised = [], None
        for page in ApiClient(settings.members_api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=settings.members_api_url, params=page.params, body=page.body, status=page.status,
                        ontology_version=REFERENCE_ONTOLOGY_VERSION, mapping_version="member_mapping.csv@phase-3-members-2026", endpoint_name="members")
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
    manifest = load_manifest(settings.members_state_file)
    graphs: list[tuple[dict, object | None, str, str, list[dict], str]] = []
    for wrapper in records:
        member = wrapper["member"]; identity, digest, graph_iri = str(__import__("oireachtas_etl.transforms.common", fromlist=["iri"]).iri(member["uri"])), source_hash(member), member_graph_iri(member)
        old = manifest["members"].get(identity, {})
        # Hash-first: unchanged published records do not enter transformation.
        omissions = validate_member_source(wrapper)
        if not args.offline and old.get("status", "clean") == "clean" and old.get("contract_version") == 2 and old.get("published_hash") == digest and old.get("graph_iri") == graph_iri:
            graphs.append((wrapper, None, identity, digest, omissions, "skipped")); continue
        graph, exclusions = transform_member_with_report(wrapper); validate_member(wrapper, graph)
        graphs.append((wrapper, graph, identity, digest, exclusions, "changed" if old else "new"))
    if args.output_nq:
        Path(args.output_nq).write_text("".join(nquads(graph, graph_iri) for wrapper, graph, identity, digest, exclusions, _ in graphs if graph is not None for graph_iri in [member_graph_iri(wrapper["member"])]), encoding="utf-8")
    if getattr(args, "output_ttl", None):
        Path(args.output_ttl).write_text("\n".join(turtle(graph) for _, graph, _, _, _, _ in graphs if graph is not None), encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url)
    query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint and not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
    published = skipped = 0
    seen = {identity for _, _, identity, _, _, _ in graphs}
    missing = sorted(identity for identity in manifest["members"] if identity not in seen)
    if endpoint:
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        for wrapper, graph, identity, digest, exclusions, status in graphs:
            old = manifest["members"].get(identity, {})
            if graph is None:
                old["last_seen"] = datetime.now(timezone.utc).isoformat()
                manifest["members"][identity] = old
                write_manifest(settings.members_state_file, manifest)
                skipped += 1
                continue
            graph_iri = member_graph_iri(wrapper["member"])
            # Durable dirty marker means a crash, failed PUT, or failed gate is
            # always retried even when the source later reverts to an old hash.
            manifest["members"][identity] = {**old, "status": "dirty", "pending_hash": digest, "pending_graph_iri": graph_iri,
                                               "graph_iri": old.get("graph_iri", graph_iri), "contract_version": 2}
            write_manifest(settings.members_state_file, manifest)
            loader.replace(graph_iri, ntriples(graph), content_type="application/n-triples")
            verify_member_competency(client, graph_iri, identity, len(graph))
            manifest["members"][identity] = {"source_hash": digest, "published_hash": digest, "graph_iri": graph_iri,
                                                "last_seen": datetime.now(timezone.utc).isoformat(), "last_published": datetime.now(timezone.utc).isoformat(), "contract_version": 2, "status": "clean"}
            write_manifest(settings.members_state_file, manifest); published += 1
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    report = [item for _, _, _, _, exclusions, _ in graphs for item in exclusions]
    identities = {kind: sorted(identity for _, _, identity, _, _, status in graphs if status == kind) for kind in ("new", "changed", "skipped")}
    print(json.dumps({"records": len(records), "published": published, "skipped": skipped, "new": identities["new"], "changed": identities["changed"], "skipped_identities": identities["skipped"], "missing_retained": missing, "future_work_omitted": report}, sort_keys=True))
    return 0


def run_members(args: argparse.Namespace) -> int:
    """Run Members; online refreshes hold the manifest's single-writer lock."""
    if args.offline:
        return _run_members(args)
    settings = Settings.from_environment()
    path = Path(args.state_file) if getattr(args, "state_file", None) else settings.members_state_file
    with manifest_lock(path):
        return _run_members(args)


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


def _deduplicate_bills(records: list[dict], advertised: int | None) -> list[dict]:
    if not records: raise ValueError("Bills harvest must not be empty")
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


def _run_bills(args: argparse.Namespace) -> int:
    settings = Settings.from_environment()
    settings = Settings(**{**settings.__dict__, "raw_dir": Path(args.raw_dir) if args.raw_dir else settings.raw_dir,
                           "bills_state_file": Path(args.state_file) if args.state_file else settings.bills_state_file})
    if args.fixture:
        records, body, advertised = _bills_fixture_records(Path(args.fixture))
        persist_raw(root=settings.raw_dir, endpoint=str(Path(args.fixture)), params={"skip": 0, "limit": len(records)}, body=body, status=200,
                    retrieved_at=datetime.now(timezone.utc), ontology_version="legislation.owl.ttl@phase-4-legislative-lifecycle-2026", mapping_version="bill_mapping.csv@phase-4-legislative-lifecycle-2026", endpoint_name="legislation")
    else:
        records, advertised = [], None
        for page in ApiClient(settings.bills_api_url, retries=settings.retries, timeout=settings.timeout).harvest(limit=settings.limit):
            persist_raw(root=settings.raw_dir, endpoint=settings.bills_api_url, params=page.params, body=page.body, status=page.status, retrieved_at=datetime.now(timezone.utc), ontology_version="legislation.owl.ttl@phase-4-legislative-lifecycle-2026", mapping_version="bill_mapping.csv@phase-4-legislative-lifecycle-2026", endpoint_name="legislation")
            decoded = json.loads(page.body)
            if not isinstance(decoded, dict) or not isinstance(decoded.get("results"), list): raise ValueError("every Legislation API page must be an object envelope with a results list")
            count = decoded.get("head", {}).get("counts", {}).get("billCount") if isinstance(decoded.get("head"), dict) else None
            if isinstance(count, bool) or not isinstance(count, int) or count < 0: raise ValueError("every Legislation API page must contain a nonnegative integer head.counts.billCount")
            if advertised is None: advertised = count
            elif advertised != count: raise ValueError("Bills advertised count changed during scan")
            records.extend(decoded["results"])
    records = _deduplicate_bills(records, advertised)
    manifest = load_bills_manifest(settings.bills_state_file)
    work = []
    for wrapper in records:
        bill = wrapper["bill"]; identity, digest, graph_iri = bill["uri"], bill_source_hash(bill), bill_graph_iri(bill); old = manifest["bills"].get(identity, {})
        # Hash-first source gate; unchanged Bills never construct RDF or invoke a loader.
        omissions = validate_bill_source(wrapper)
        if not args.offline and old.get("status") == "clean" and old.get("contract_version") == 1 and old.get("published_hash") == digest and old.get("graph_iri") == graph_iri:
            work.append((wrapper, None, identity, digest, omissions, "skipped")); continue
        graph, report = transform_bill_with_report(wrapper); validate_bill(wrapper, graph)
        work.append((wrapper, graph, identity, digest, report, "changed" if old else "new"))
    if args.output_nq: Path(args.output_nq).write_text("".join(nquads(graph, bill_graph_iri(wrapper["bill"])) for wrapper, graph, *_ in work if graph is not None), encoding="utf-8")
    if getattr(args, "output_ttl", None): Path(args.output_ttl).write_text("\n".join(turtle(graph) for _, graph, *_ in work if graph is not None), encoding="utf-8")
    endpoint = None if args.offline else (args.fuseki_gsp_url or settings.fuseki_gsp_url); query_endpoint = None if args.offline else (args.fuseki_sparql_url or settings.fuseki_sparql_url)
    if endpoint and not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
    published = skipped = 0
    if endpoint:
        loader = FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout); client = FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout)
        for wrapper, graph, identity, digest, _, status in work:
            old = manifest["bills"].get(identity, {})
            if graph is None:
                old["last_seen"] = datetime.now(timezone.utc).isoformat(); manifest["bills"][identity] = old; write_manifest(settings.bills_state_file, manifest); skipped += 1; continue
            graph_iri = bill_graph_iri(wrapper["bill"])
            manifest["bills"][identity] = {**old, "status": "dirty", "pending_hash": digest, "pending_graph_iri": graph_iri, "graph_iri": old.get("graph_iri", graph_iri), "contract_version": 1}; write_manifest(settings.bills_state_file, manifest)
            loader.replace(graph_iri, ntriples(graph), content_type="application/n-triples"); verify_bill_competency(client, graph_iri, identity, len(graph))
            manifest["bills"][identity] = {"source_hash": digest, "published_hash": digest, "graph_iri": graph_iri, "last_seen": datetime.now(timezone.utc).isoformat(), "last_published": datetime.now(timezone.utc).isoformat(), "contract_version": 1, "status": "clean"}; write_manifest(settings.bills_state_file, manifest); published += 1
    elif not args.offline: raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    identities = {kind: sorted(identity for _, _, identity, _, _, status in work if status == kind) for kind in ("new", "changed", "skipped")}
    print(json.dumps({"records": len(records), "published": published, "skipped": skipped, "new": identities["new"], "changed": identities["changed"], "skipped_identities": identities["skipped"], "omitted": [item for *_, report, _ in work for item in report]}, sort_keys=True))
    return 0


def run_bills(args: argparse.Namespace) -> int:
    if args.offline: return _run_bills(args)
    settings = Settings.from_environment(); path = Path(args.state_file) if getattr(args, "state_file", None) else settings.bills_state_file
    with manifest_lock(path): return _run_bills(args)


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
    wikidata = _FixtureWikidataClient(data).data
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
            if not isinstance(wikidata, dict) or set(wikidata) != {"party_candidates"}:
                raise ValueError
            values = wikidata["party_candidates"]
            if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
                raise ValueError
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid Party reconciliation response fixture schema") from error
        self.data = values

    def lookup_party_candidates(self, wrapper):
        local_iri = wrapper["party"]["uri"]
        if local_iri not in self.data:
            raise FixtureResponseError("response fixture lacks Party candidate entry for " + local_iri)
        return self.data[local_iri]


def _validate_party_fixture_responses(data: object, records: list[dict], decisions: dict[str, dict]) -> None:
    client = _FixturePartyWikidataClient(data)
    eligible = {wrapper["party"]["uri"]: wrapper for wrapper in records if wrapper["party"]["partyCode"] != "Independent"}
    unknown = sorted(set(client.data) - set(eligible))
    if unknown:
        raise ValueError("response fixture contains unknown or Independent Party IRI: " + ", ".join(unknown))
    for local_iri, wrapper in eligible.items():
        decision = decisions.get(local_iri)
        if decision is not None:
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
    store = ReconciliationStore(Path(args.reconciliation_state_file or "~/.local/share/oireachtas-etl/member-reconciliation.sqlite").expanduser())
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
    state_path = args.reconciliation_state_file or "~/.local/share/oireachtas-etl/member-reconciliation.sqlite"
    store = ReconciliationStore(Path(state_path).expanduser())
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

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oir-etl")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses", "parties", "constituencies", "members", "bills"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
    run.add_argument("--state-file")
    run.add_argument("--output-ttl"); run.add_argument("--output-nq"); run.add_argument("--fuseki-gsp-url"); run.add_argument("--fuseki-sparql-url")
    reconcile = sub.add_parser("reconcile"); reconcile.add_argument("endpoint", choices=["members", "parties"])
    reconcile.add_argument("--fixture"); reconcile.add_argument("--responses-file"); reconcile.add_argument("--offline", action="store_true"); reconcile.add_argument("--all", action="store_true"); reconcile.add_argument("--publish", action="store_true"); reconcile.add_argument("--output-nq"); reconcile.add_argument("--fuseki-gsp-url"); reconcile.add_argument("--fuseki-sparql-url")
    reconcile.add_argument("--review-file", help="review JSON (defaults to the endpoint-specific version-controlled review file)")
    reconcile.add_argument("--reconciliation-state-file", help="shared reconciliation SQLite path (defaults to the Phase 3.5 state file)")
    args = parser.parse_args(argv)
    if args.command == "reconcile":
        return run_reconcile_parties(args) if args.endpoint == "parties" else run_reconcile_members(args)
    if args.endpoint == "houses": return run_houses(args)
    if args.endpoint == "members": return run_members(args)
    if args.endpoint == "bills": return run_bills(args)
    return run_reference(args)

if __name__ == "__main__": raise SystemExit(main())
