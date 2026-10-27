#!/usr/bin/env python3
"""Validate and replace the dedicated political-affiliation enrichment graph."""
import argparse
import os

from oireachtas_etl.political_affiliations import publish


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gsp-endpoint", required=True,
                        help="explicit Graph Store Protocol endpoint for the target dataset")
    parser.add_argument("--sparql-endpoint", required=True,
                        help="explicit SPARQL endpoint for the same target dataset")
    parser.add_argument("--user", default=os.getenv("FUSEKI_USER"))
    parser.add_argument("--password", default=os.getenv("FUSEKI_PASSWORD"))
    args = parser.parse_args()
    publish(args.gsp_endpoint, args.sparql_endpoint, user=args.user, password=args.password)
    print("Political-affiliation identity graph replaced and verified.")


if __name__ == "__main__":
    main()
