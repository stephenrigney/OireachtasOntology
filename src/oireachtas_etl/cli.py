from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from .api import HousesApiClient
from .config import HOUSES_GRAPH, Settings
from .loader import FusekiGraphStoreLoader
from .loader import FusekiSparqlClient
from .competency import verify_houses_competency
from .raw import persist_raw
from .serialization import nquads, ntriples, turtle
from .transforms.houses import transform_houses_with_report
from .validation import validate_houses

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
    endpoint = args.fuseki_gsp_url or settings.fuseki_gsp_url
    query_endpoint = args.fuseki_sparql_url or settings.fuseki_sparql_url
    if endpoint:
        if not query_endpoint: raise ValueError("Fuseki SPARQL endpoint is required for post-load competency verification")
        FusekiGraphStoreLoader(endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout).replace(HOUSES_GRAPH, ntriples(graph), content_type="application/n-triples")
        verify_houses_competency(FusekiSparqlClient(query_endpoint, user=settings.fuseki_user, password=settings.fuseki_password, timeout=settings.timeout))
    elif not args.offline:
        raise ValueError("no Fuseki GSP endpoint configured; use --offline for fixture/developer runs")
    print(json.dumps({"records": len(records), "excluded": exclusions, "published": bool(endpoint)}, sort_keys=True))
    return 0

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="oir-etl")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run"); run.add_argument("endpoint", choices=["houses"])
    run.add_argument("--fixture"); run.add_argument("--offline", action="store_true"); run.add_argument("--raw-dir")
    run.add_argument("--output-ttl"); run.add_argument("--output-nq"); run.add_argument("--fuseki-gsp-url"); run.add_argument("--fuseki-sparql-url")
    args = parser.parse_args(argv)
    return run_houses(args)

if __name__ == "__main__": raise SystemExit(main())
