"""Rebuild the replaceable Fuseki projection from durable canonical state."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3

from rdflib import Graph, URIRef

from .config import (ADMINISTRATIVE_UNITS_GRAPH, COMMITTEES_GRAPH,
                     CONSTITUENCIES_GRAPH, HOUSES_GRAPH, OFFICES_GRAPH,
                     PARTIES_GRAPH)
from .provenance import validate_provenance_catalog
from .reconciliation import (ReconciliationError, ReconciliationStore,
                             _ENTITY_POLICIES, _replay_pending,
                             _validate_party_graph, links_graph)
from .serialization import ntriples
from .state import (PROVENANCE_GRAPH_IRI, RESOURCE_ENDPOINTS, SCHEMA_VERSION,
                    expected_graph_iri)
from .transforms.common import MEMBERS
from .validation.offices import validate_registry_source


class ProjectionError(RuntimeError):
    """Durable publication state cannot be rebuilt safely."""


@dataclass(frozen=True)
class GraphPayload:
    graph_iri: str
    payload: str
    owner: str


_SHARED_GRAPH_IRIS = {
    "houses": HOUSES_GRAPH,
    "parties": PARTIES_GRAPH,
    "constituencies": CONSTITUENCIES_GRAPH,
    "committees": COMMITTEES_GRAPH,
    "offices": OFFICES_GRAPH,
    "administrative-units": ADMINISTRATIVE_UNITS_GRAPH,
}


def _payload_graph(graph_iri: str, payload: str, expected_hash: str,
                   owner: str) -> GraphPayload:
    if not isinstance(payload, str) or not isinstance(expected_hash, str):
        raise ProjectionError(f"{owner} graph lacks its durable payload or SHA-256")
    actual = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if actual != expected_hash:
        raise ProjectionError(f"{owner} graph payload does not match its durable SHA-256")
    try:
        graph = Graph().parse(data=payload, format="nt")
    except Exception as error:
        raise ProjectionError(f"{owner} graph payload is not valid N-Triples") from error
    if graph_iri == PROVENANCE_GRAPH_IRI:
        try:
            validate_provenance_catalog(graph)
        except Exception as error:
            raise ProjectionError("persisted provenance catalog failed validation") from error
    return GraphPayload(graph_iri, payload, owner)


def authoritative_graph_payloads(state_db: str | Path) -> list[GraphPayload]:
    """Read exact current Core State payloads, including dirty replay payloads.

    When a graph is dirty, its pending payload is the deterministic recovery
    boundary and is selected ahead of the prior clean payload. A subsequent ETL
    invocation replays that same payload and completes the existing dirty marker.
    """
    path = Path(state_db).expanduser().resolve()
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("BEGIN")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version != SCHEMA_VERSION:
            raise ProjectionError(
                f"Core State schema {version} is not supported by this rebuild tool "
                f"(expected {SCHEMA_VERSION}); use the matching release")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"resource_state", "catalog_publication_state"} <= tables:
            raise ProjectionError("Core State is missing publication payload tables")

        rows = connection.execute("""SELECT endpoint,resource_iri,graph_iri,
          publication_state,published_payload,published_payload_hash,
          pending_payload,pending_payload_hash,pending_graph_iri
          FROM resource_state ORDER BY endpoint,resource_iri""").fetchall()
        selected: list[GraphPayload] = []
        seen: set[str] = set()
        for row in rows:
            endpoint = row["endpoint"]
            if row["publication_state"] == "dirty":
                graph_iri, payload, payload_hash = (
                    row["pending_graph_iri"], row["pending_payload"],
                    row["pending_payload_hash"])
            elif row["publication_state"] == "clean":
                graph_iri, payload, payload_hash = (
                    row["graph_iri"], row["published_payload"],
                    row["published_payload_hash"])
            else:
                raise ProjectionError("Core State contains an unknown publication state")

            if payload is None and payload_hash is None and graph_iri is None:
                continue
            if payload is None or payload_hash is None or graph_iri is None:
                raise ProjectionError("Core State has an incomplete persisted graph payload")

            if endpoint in RESOURCE_ENDPOINTS:
                expected = expected_graph_iri(endpoint, row["resource_iri"])
            else:
                try:
                    expected = _SHARED_GRAPH_IRIS[endpoint]
                except KeyError as error:
                    raise ProjectionError(
                        f"Core State contains an unsupported graph owner: {endpoint}") from error
            if graph_iri != expected:
                raise ProjectionError(
                    f"Core State graph IRI does not match {endpoint} ownership")
            if graph_iri in seen:
                raise ProjectionError("Core State contains duplicate current graph identities")
            seen.add(graph_iri)
            selected.append(_payload_graph(graph_iri, payload, payload_hash, endpoint))

        shared_rows = connection.execute(
            "SELECT endpoint,publication_metadata_json FROM endpoint_state "
            "WHERE publication_metadata_json IS NOT NULL ORDER BY endpoint").fetchall()
        for row in shared_rows:
            endpoint = row["endpoint"]
            if endpoint not in _SHARED_GRAPH_IRIS:
                raise ProjectionError(
                    f"Core State contains unsupported shared graph metadata: {endpoint}")
            try:
                metadata = json.loads(row["publication_metadata_json"])
            except (TypeError, json.JSONDecodeError) as error:
                raise ProjectionError("Core State shared graph metadata is malformed") from error
            if not isinstance(metadata, dict):
                raise ProjectionError("Core State shared graph metadata is malformed")
            publication_state = metadata.get("publication_state")
            if publication_state == "dirty":
                payload = metadata.get("pending_payload")
                payload_hash = metadata.get("pending_payload_hash")
            elif publication_state == "clean":
                payload = metadata.get("published_payload")
                payload_hash = metadata.get("published_payload_hash")
            else:
                raise ProjectionError("Core State shared graph has an unknown publication state")
            graph_iri = metadata.get("graph_iri")
            if graph_iri != _SHARED_GRAPH_IRIS[endpoint]:
                raise ProjectionError(
                    f"Core State graph IRI does not match {endpoint} ownership")
            if graph_iri in seen:
                raise ProjectionError("Core State contains duplicate current graph identities")
            seen.add(graph_iri)
            selected.append(_payload_graph(graph_iri, payload, payload_hash, endpoint))

        catalog = connection.execute(
            "SELECT * FROM catalog_publication_state WHERE graph_iri=?",
            (PROVENANCE_GRAPH_IRI,),
        ).fetchone()
        if catalog is not None:
            if catalog["publication_state"] == "dirty":
                payload, payload_hash = catalog["pending_payload"], catalog["pending_payload_hash"]
            elif catalog["publication_state"] == "clean":
                payload, payload_hash = catalog["published_payload"], catalog["published_payload_hash"]
            else:
                raise ProjectionError("provenance catalog has an unknown publication state")
            if payload is not None or payload_hash is not None:
                if PROVENANCE_GRAPH_IRI in seen:
                    raise ProjectionError("provenance graph is duplicated in Core State")
                selected.append(_payload_graph(
                    PROVENANCE_GRAPH_IRI, payload, payload_hash, "provenance"))

        connection.commit()
        return selected
    except ProjectionError:
        raise
    except (sqlite3.Error, OSError, TypeError, ValueError) as error:
        raise ProjectionError("could not read a consistent Core State publication snapshot") from error
    finally:
        if connection is not None:
            connection.close()


def _resolution_from_attempt(row) -> object:
    try:
        evidence = json.loads(row["evidence_json"])
    except (TypeError, json.JSONDecodeError) as error:
        raise ProjectionError("external reconciliation attempt evidence is malformed") from error
    if not isinstance(evidence, dict) or row["state"] not in {
            "accepted", "rejected", "ambiguous", "pending"}:
        raise ProjectionError("external reconciliation attempt outcome is malformed")
    from .reconciliation import Resolution
    return Resolution(row["state"], row["method"], evidence, row["wikidata_iri"],
                      row["wikipedia_iri"], row["dbpedia_iri"],
                      bool(row["review_applied"]))


def _reconstructed_reconciliation_graph(policy, entity_kind: str, local_iri: str,
                                        entity_key: str, resolution, registry) -> Graph:
    if entity_kind == "member":
        entity = {"uri": local_iri, "memberCode": entity_key}
        graph = links_graph(entity, resolution)
    elif entity_kind == "party":
        graph = Graph()
        if resolution.state == "accepted":
            if not resolution.review_applied or not resolution.wikidata:
                raise ProjectionError("accepted Party link has no persisted human review")
            graph.add((URIRef(local_iri), MEMBERS.recognisedAsParty,
                       URIRef(resolution.wikidata)))
        _validate_party_graph(local_iri, graph)
    elif entity_kind == "institution":
        graph = policy.links_graph({"uri": local_iri}, resolution)
    elif entity_kind == "office":
        entity = policy.extract({"uri": local_iri, "_registry": registry})
        graph = policy.links_graph(entity, resolution)
    else:
        raise ProjectionError("unsupported external reconciliation graph owner")
    policy.validate_stored_graph(local_iri, entity_key, graph, resolution)
    return graph


def reconciliation_graph_payloads(reconciliation_db: str | Path, *,
                                   office_registry: object | None = None
                                   ) -> list[GraphPayload]:
    """Rebuild external-link graphs from reconciliation state/history only.

    This function makes no network calls. For clean state whose latest lookup
    became unresolved, it finds the append-only attempt that produced the exact
    hash still recorded as published; a newer unresolved observation never
    silently removes a previously accepted external graph.
    """
    registry = (validate_registry_source(office_registry)
                if office_registry is not None else None)
    try:
        store = ReconciliationStore(Path(reconciliation_db).expanduser())
    except Exception as error:
        raise ProjectionError("cannot validate the reconciliation SQLite store") from error
    result: list[GraphPayload] = []
    try:
        rows = store.connection.execute(
            "SELECT * FROM reconciliation_record ORDER BY entity_kind,local_iri").fetchall()
        for row in rows:
            kind = row["entity_kind"]
            if kind not in _ENTITY_POLICIES:
                raise ProjectionError("reconciliation store contains an unsupported entity kind")
            if kind == "office":
                if registry is None:
                    raise ProjectionError("office external graphs require the saved office registry")
                policy = _ENTITY_POLICIES[kind](registry)
            else:
                policy = _ENTITY_POLICIES[kind]()

            if row["publication_state"] == "dirty":
                graph_iri, payload, graph, _resolution = _replay_pending(
                    row, policy, None, None, store)
                expected_hash = row["pending_payload_hash"]
            elif row["publication_state"] == "clean":
                expected_hash = row["published_links_hash"]
                if expected_hash is None:
                    continue
                successes = {item[0] for item in store.connection.execute(
                    "SELECT DISTINCT payload_hash FROM publication_attempt "
                    "WHERE entity_kind=? AND local_iri=? AND result='success'",
                    (kind, row["local_iri"]))}
                if expected_hash not in successes:
                    raise ProjectionError(
                        "clean reconciliation graph has no successful publication evidence")
                graph_iri = policy.stored_graph_iri(row["local_iri"], row["entity_key"])
                attempts = store.connection.execute(
                    "SELECT * FROM reconciliation_attempt WHERE entity_kind=? AND local_iri=? "
                    "ORDER BY attempt_id DESC", (kind, row["local_iri"]))
                match = None
                for attempt in attempts:
                    resolution = _resolution_from_attempt(attempt)
                    candidate = _reconstructed_reconciliation_graph(
                        policy, kind, row["local_iri"], row["entity_key"],
                        resolution, registry)
                    candidate_payload = ntriples(candidate)
                    digest = hashlib.sha256(candidate_payload.encode("utf-8")).hexdigest()
                    if digest == expected_hash:
                        match = (candidate_payload, candidate)
                        break
                if match is None:
                    raise ProjectionError(
                        "published external graph cannot be reconstructed from attempt history")
                payload, graph = match
            else:
                raise ProjectionError("reconciliation store has an unknown publication state")

            actual_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if actual_hash != expected_hash:
                raise ProjectionError("external graph payload does not match its persisted hash")
            result.append(GraphPayload(graph_iri, payload, f"external:{kind}"))
        if len({item.graph_iri for item in result}) != len(result):
            raise ProjectionError("external reconciliation records collide on graph ownership")
        return result
    except ProjectionError:
        raise
    except Exception as error:
        raise ProjectionError("could not reconstruct external links from reconciliation state") from error
    finally:
        store.close()


def rebuildable_graph_payloads(state_db: str | Path, *,
                               reconciliation_db: str | Path | None = None,
                               office_registry: object | None = None
                               ) -> list[GraphPayload]:
    """Assemble every authoritative and persisted external graph before PUTs."""
    graphs = authoritative_graph_payloads(state_db)
    if reconciliation_db is not None and Path(reconciliation_db).is_file():
        graphs.extend(reconciliation_graph_payloads(
            reconciliation_db, office_registry=office_registry))
    identities = [item.graph_iri for item in graphs]
    if len(identities) != len(set(identities)):
        raise ProjectionError("authoritative and external graph owners collide")
    return graphs


def rebuild_empty_dataset(graphs: list[GraphPayload], loader, client) -> dict:
    """PUT and whole-graph-verify a complete candidate set into an empty store."""
    if not graphs:
        raise ProjectionError("no persisted graphs are available for reconstruction")
    for query in (
            "SELECT (COUNT(*) AS ?triples) WHERE { GRAPH ?graph { ?s ?p ?o } }",
            "SELECT (COUNT(*) AS ?triples) WHERE { ?s ?p ?o }",
    ):
        rows = client.query(query)
        if (len(rows) != 1 or not isinstance(rows[0].get("triples"), dict)
                or int(rows[0]["triples"].get("value", "-1")) != 0):
            raise ProjectionError("rebuild target is not an empty Fuseki dataset")

    from .competency import verify_core_graph
    for item in graphs:
        loader.replace(item.graph_iri, item.payload, content_type="application/n-triples")
        verify_core_graph(client, item.graph_iri, item.payload)

    rows = client.query("SELECT DISTINCT ?graph WHERE { GRAPH ?graph { ?s ?p ?o } }")
    actual_graphs = {row.get("graph", {}).get("value") for row in rows
                     if isinstance(row.get("graph"), dict)}
    expected_nonempty = {item.graph_iri for item in graphs
                         if len(Graph().parse(data=item.payload, format="nt")) > 0}
    if actual_graphs != expected_nonempty:
        raise ProjectionError("rebuilt Fuseki graph inventory does not match durable state")
    return {
        "graphs_verified": len(graphs),
        "authoritative_graphs": sum(not item.owner.startswith("external:") for item in graphs),
        "external_graphs": sum(item.owner.startswith("external:") for item in graphs),
        "triples_verified": sum(len(Graph().parse(data=item.payload, format="nt"))
                                 for item in graphs),
        "provenance_present": any(item.graph_iri == PROVENANCE_GRAPH_IRI for item in graphs),
    }
