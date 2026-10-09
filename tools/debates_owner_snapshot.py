#!/usr/bin/env python3
"""Read-only fingerprint and optional remote check for Debates owner RDF.

This tool never opens Core State for writing. It reports only the exact clean
owner payload inventory consumed by ``load_debate_owner_snapshot`` and can
compare that identity with an operator-pinned SHA-256 before a batch starts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
from urllib.parse import urlsplit

from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH, Settings
from oireachtas_etl.debates_pipeline import load_debate_owner_snapshot
from oireachtas_etl.loader import FusekiSparqlClient
from oireachtas_etl.competency import verify_core_graph
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import SCHEMA_VERSION


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHARED = ("houses", "committees")


class ReadOnlyOwnerState:
    """Minimal read-only view required by the existing owner snapshot loader."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_file():
            raise ValueError(f"Core State file is unavailable: {self.path}")
        try:
            self.connection = sqlite3.connect(
                self.path.as_uri() + "?mode=ro", uri=True, timeout=30)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA query_only=ON")
            self.connection.execute("PRAGMA busy_timeout=30000")
            self.connection.execute("BEGIN")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version != SCHEMA_VERSION:
                raise ValueError(
                    f"Core State schema must be current (expected {SCHEMA_VERSION}, got {version})")
            tables = {row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"endpoint_state", "resource_state"} <= tables:
                raise ValueError("Core State owner publication tables are unavailable")
        except Exception:
            connection = getattr(self, "connection", None)
            if connection is not None:
                connection.close()
            raise

    def close(self) -> None:
        self.connection.rollback()
        self.connection.close()

    def endpoint_publication(self, endpoint: str) -> dict | None:
        if endpoint not in _SHARED:
            raise ValueError(f"unsupported shared Debates owner endpoint: {endpoint}")
        row = self.connection.execute(
            "SELECT publication_metadata_json FROM endpoint_state WHERE endpoint=?",
            (endpoint,),
        ).fetchone()
        if row is None or not row[0]:
            return None
        try:
            value = json.loads(row[0])
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"{endpoint} publication metadata is invalid JSON") from error
        if not isinstance(value, dict):
            raise ValueError(f"{endpoint} publication metadata is not an object")
        return value

    def resources(self, endpoint: str) -> list[dict]:
        if endpoint != "members":
            raise ValueError("Debates owner snapshot resource reads are limited to Members")
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM resource_state WHERE endpoint='members' ORDER BY resource_iri")]

    def member_capture_provenance(self, run_ids: set[str]) -> dict:
        endpoint = self.connection.execute(
            "SELECT last_successful_run_id,last_successful_complete_run_id "
            "FROM endpoint_state WHERE endpoint='members'").fetchone()
        run_rows = {}
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            for row in self.connection.execute(
                "SELECT run_id,endpoint,is_complete,status,outcome,parameters_json "
                f"FROM etl_run WHERE run_id IN ({placeholders}) ORDER BY run_id",
                tuple(sorted(run_ids)),
            ):
                parameters = {}
                try:
                    raw = json.loads(row["parameters_json"] or "{}")
                    if isinstance(raw, dict):
                        parameters = {key: raw[key] for key in ("source", "source_run_id")
                                      if key in raw}
                except (TypeError, json.JSONDecodeError):
                    parameters = {"invalid": True}
                run_rows[row["run_id"]] = {
                    "endpoint": row["endpoint"],
                    "is_complete": bool(row["is_complete"]),
                    "status": row["status"],
                    "outcome": row["outcome"],
                    "parameters": parameters,
                }
        return {
            "last_successful_run_id": endpoint[0] if endpoint else None,
            "last_successful_complete_run_id": endpoint[1] if endpoint else None,
            "member_publication_run_ids": run_rows,
        }

    def operational_health(self) -> dict:
        dirty = {row["endpoint"]: row["count"] for row in self.connection.execute(
            "SELECT endpoint,COUNT(*) AS count FROM resource_state "
            "WHERE publication_state='dirty' GROUP BY endpoint ORDER BY endpoint")}
        quarantines = [dict(row) for row in self.connection.execute(
            "SELECT quarantine_id,resource_iri,source_hash,evidence_pointer,observed_at,"
            "stage,error,run_id,failure_classification,status,retry_state,retry_attempts "
            "FROM quarantine_record "
            "WHERE endpoint='debates' AND status='quarantined' ORDER BY quarantine_id")]
        incomplete = [dict(row) for row in self.connection.execute(
            "SELECT endpoint,reason,COUNT(*) AS count FROM provenance_incomplete "
            "WHERE status='pending' GROUP BY endpoint,reason ORDER BY endpoint,reason")]
        catalog = self.connection.execute(
            "SELECT publication_state,published_payload_hash,pending_payload_hash "
            "FROM catalog_publication_state "
            "WHERE graph_iri='https://data.oireachtas.ie/graph/provenance'").fetchone()
        finalization = self.connection.execute(
            "SELECT run_id FROM catalog_run_finalization "
            "WHERE graph_iri='https://data.oireachtas.ie/graph/provenance'").fetchone()
        return {
            "dirty_resources_by_endpoint": dirty,
            "catalog_publication": ({
                "publication_state": catalog[0],
                "published_payload_hash": catalog[1],
                "pending_payload_hash": catalog[2],
                "pending_run_id": finalization[0] if finalization else None,
            } if catalog else None),
            "unresolved_debates_quarantines": quarantines,
            "pending_provenance_incomplete": incomplete,
        }


def _shared_provenance(metadata: dict | None) -> dict | None:
    if metadata is None:
        return None
    fields = ("graph_iri", "publication_state", "published_payload_hash",
              "coverage_authoritative", "member_source_run_id", "source_run_id")
    return {key: metadata[key] for key in fields if key in metadata}


def inspect_owner_snapshot(state_db: str | Path, *, expected_sha256: str | None = None,
                           sparql_url: str | None = None, user: str | None = None,
                           password: str | None = None) -> dict:
    """Compute the publisher's exact owner fingerprint and optionally verify it remotely."""
    if expected_sha256 is not None and _SHA256.fullmatch(expected_sha256) is None:
        raise ValueError("expected owner snapshot must be a lowercase SHA-256")
    if sparql_url:
        parsed = urlsplit(sparql_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Fuseki SPARQL endpoint must be an HTTP(S) URL without credentials or query")

    state = ReadOnlyOwnerState(state_db)
    try:
        snapshot = load_debate_owner_snapshot(state)
        members = state.resources("members")
        member_run_ids = {row.get("last_seen_run_id") for row in members
                          if row.get("last_seen_run_id")}
        member_capture = state.member_capture_provenance(member_run_ids)
        operational_health = state.operational_health()
        houses = state.endpoint_publication("houses")
        committees = state.endpoint_publication("committees")
    finally:
        state.close()

    graph_payloads = {graph_iri: ntriples(graph)
                      for graph_iri, graph in snapshot.graphs.items()}
    graph_hashes = {graph_iri: hashlib.sha256(payload.encode("utf-8")).hexdigest()
                    for graph_iri, payload in graph_payloads.items()}
    member_inventory = sorted(
        (graph_iri, digest) for graph_iri, digest in graph_hashes.items()
        if graph_iri not in {HOUSES_GRAPH, COMMITTEES_GRAPH})
    member_inventory_sha256 = hashlib.sha256(json.dumps(
        member_inventory, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    result = {
        "schema": "debates-owner-snapshot-inspection-v1",
        "state_db_schema": SCHEMA_VERSION,
        "owner_snapshot_sha256": snapshot.snapshot_hash,
        "resolver_version": snapshot.resolver.version,
        "owner_counts": {
            "members": len(set(snapshot.resolver.members_by_tlc_href.values())),
            "house_terms": len(set(snapshot.resolver.house_terms_by_author_href.values())),
            "committees": len(set(snapshot.resolver.committees_by_author_href.values())),
        },
        "resolver_lookup_keys": {
            "members": len(snapshot.resolver.members_by_tlc_href),
            "house_terms": len(snapshot.resolver.house_terms_by_author_href),
            "committees": len(snapshot.resolver.committees_by_author_href),
        },
        "owner_graph_count": len(graph_hashes),
        "shared_owner_graph_payload_sha256": {
            key: value for key, value in sorted(graph_hashes.items())
            if key in {HOUSES_GRAPH, COMMITTEES_GRAPH}
        },
        "member_graph_inventory_sha256": member_inventory_sha256,
        "owner_publications": {
            "houses": _shared_provenance(houses),
            "committees": _shared_provenance(committees),
            "member_graph_count": len(members),
            "member_clean_graph_count": sum(
                row.get("publication_state") == "clean" for row in members),
            "member_payload_count": sum(
                isinstance(row.get("published_payload"), str) for row in members),
            **member_capture,
        },
        "operational_health": operational_health,
        "expected_sha256": expected_sha256,
        "expected_match": (None if expected_sha256 is None else
                           expected_sha256 == snapshot.snapshot_hash),
        "remote_owner_graphs_verified": False,
        "remote_owner_graph_count": 0,
    }
    if sparql_url:
        client = FusekiSparqlClient(sparql_url, user=user, password=password)
        for graph_iri, payload in sorted(graph_payloads.items()):
            verify_core_graph(client, graph_iri, payload)
        result["remote_owner_graphs_verified"] = True
        result["remote_owner_graph_count"] = len(snapshot.graphs)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-db", required=True,
                        help="current Core State SQLite file; opened strictly read-only")
    parser.add_argument("--expected-sha256",
                        help="fail with exit 2 if the computed owner snapshot differs")
    parser.add_argument("--fuseki-sparql-url",
                        help="optional SPARQL endpoint for exact read-only owner graph verification")
    args = parser.parse_args(argv)
    settings = Settings.from_environment()
    try:
        result = inspect_owner_snapshot(
            args.state_db, expected_sha256=args.expected_sha256,
            sparql_url=args.fuseki_sparql_url,
            user=settings.fuseki_user, password=settings.fuseki_password,
        )
    except Exception as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if result["expected_match"] is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
