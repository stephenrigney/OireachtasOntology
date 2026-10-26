#!/usr/bin/env python3
"""Validate and replace the dedicated political-affiliation enrichment graph."""
import argparse
import os

from oireachtas_etl.political_affiliations import publish


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gsp-endpoint", default=os.getenv("FUSEKI_GSP_URL"))
    parser.add_argument("--sparql-endpoint", default=os.getenv("FUSEKI_SPARQL_URL"))
    parser.add_argument("--user", default=os.getenv("FUSEKI_USER"))
    parser.add_argument("--password", default=os.getenv("FUSEKI_PASSWORD"))
    args = parser.parse_args()
    if not args.gsp_endpoint or not args.sparql_endpoint:
        parser.error("both GSP and SPARQL endpoints are required")
    publish(args.gsp_endpoint, args.sparql_endpoint, user=args.user, password=args.password)
    print("Political-affiliation identity graph replaced and verified.")


if __name__ == "__main__":
    main()
