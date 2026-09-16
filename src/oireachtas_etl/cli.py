from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from .api import ApiClient, HousesApiClient
from .config import CONSTITUENCIES_GRAPH, HOUSES_GRAPH, PARTIES_GRAPH, REFERENCE_ONTOLOGY_VERSION, Settings
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_constituencies_competency, verify_houses_competency, verify_parties_competency
from .raw import persist_raw
from .serialization import nquads, ntriples, turtle
from .transforms.houses import transform_houses_with_report
from .transforms.parties import transform_parties
from .transforms.constituencies import transform_constituencies
from .validation import validate_constituencies, validate_houses, validate_parties

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



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oir-etl")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses", "parties", "constituencies"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
    run.add_argument("--output-ttl"); run.add_argument("--output-nq"); run.add_argument("--fuseki-gsp-url"); run.add_argument("--fuseki-sparql-url")
    args = parser.parse_args(argv)
    if args.endpoint == "houses": return run_houses(args)
    return run_reference(args)

if __name__ == "__main__": raise SystemExit(main())
