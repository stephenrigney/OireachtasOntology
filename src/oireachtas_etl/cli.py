from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from .api import ApiClient, HousesApiClient
from .config import CONSTITUENCIES_GRAPH, HOUSES_GRAPH, PARTIES_GRAPH, REFERENCE_ONTOLOGY_VERSION, Settings
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_constituencies_competency, verify_houses_competency, verify_parties_competency, verify_member_competency
from .raw import persist_raw
from .serialization import nquads, ntriples, turtle
from .transforms.houses import transform_houses_with_report
from .transforms.parties import transform_parties
from .transforms.constituencies import transform_constituencies
from .validation import validate_constituencies, validate_houses, validate_parties
from .validation import validate_member
from .validation.members import validate_member_source
from .transforms.members import member_graph_iri, source_hash, transform_member_with_report
from .state import load_manifest, write_manifest, manifest_lock

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
        if not args.offline and old.get("status", "clean") == "clean" and old.get("contract_version") == 1 and old.get("published_hash") == digest and old.get("graph_iri") == graph_iri:
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
                                               "graph_iri": old.get("graph_iri", graph_iri), "contract_version": 1}
            write_manifest(settings.members_state_file, manifest)
            loader.replace(graph_iri, ntriples(graph), content_type="application/n-triples")
            verify_member_competency(client, graph_iri, identity, len(graph))
            manifest["members"][identity] = {"source_hash": digest, "published_hash": digest, "graph_iri": graph_iri,
                                                "last_seen": datetime.now(timezone.utc).isoformat(), "last_published": datetime.now(timezone.utc).isoformat(), "contract_version": 1, "status": "clean"}
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

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oir-etl")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses", "parties", "constituencies", "members"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
    run.add_argument("--state-file")
    run.add_argument("--output-ttl"); run.add_argument("--output-nq"); run.add_argument("--fuseki-gsp-url"); run.add_argument("--fuseki-sparql-url")
    args = parser.parse_args(argv)
    if args.endpoint == "houses": return run_houses(args)
    if args.endpoint == "members": return run_members(args)
    return run_reference(args)

if __name__ == "__main__": raise SystemExit(main())
