"""Explicit-batch Debates transform, validation, Core State and publication."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import xml.etree.ElementTree as ET

from rdflib import Dataset, Graph, URIRef

from .config import COMMITTEES_GRAPH, HOUSES_GRAPH
from .debates_owners import build_debate_reference_resolver
from .debates_raw import (
    DebateRawSource,
    DebateSourceError,
    persist_reference_report,
    verify_reference_report,
    validate_source_expression_url,
)
from .serialization import ntriples
from .state import CoreStateError, CoreStateStore, expected_graph_iri
from .transforms.debates import (
    inspect_debate_source_identity,
    transform_debate,
)
from .validation.debates_integration import validate_debates_integration


DEBATES_PUBLICATION_CONTRACT = 1


@dataclass(frozen=True)
class DebateBatchOutcome:
    work_iri: str
    graph_iri: str
    source_sha256: str
    status: str
    triples: int
    graph: Graph


@dataclass(frozen=True)
class DebateOwnerSnapshot:
    resolver: object
    graphs: dict[str, Graph]
    snapshot_hash: str


def _payload_graph(payload: object, digest: object, graph_iri: str, label: str) -> Graph:
    if not isinstance(payload, str) or not isinstance(digest, str):
        raise CoreStateError(f"{label} Core State lacks a published owner payload")
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != digest:
        raise CoreStateError(f"{label} Core State published owner payload hash is corrupt")
    graph = Graph(identifier=URIRef(graph_iri))
    try:
        if payload:
            graph.parse(data=payload, format="nt")
    except Exception as error:
        raise CoreStateError(f"{label} Core State published owner payload is invalid N-Triples") from error
    return graph


def load_debate_owner_snapshot(store: CoreStateStore) -> DebateOwnerSnapshot:
    """Use only clean, previously verified owner payloads already in Core State."""
    graphs: dict[str, Graph] = {}
    owner_payload_hashes: list[tuple[str, str]] = []

    for endpoint, graph_iri in (("houses", HOUSES_GRAPH),
                                ("committees", COMMITTEES_GRAPH)):
        metadata = store.endpoint_publication(endpoint)
        if metadata is None:
            continue
        if (metadata.get("graph_iri") != graph_iri
                or metadata.get("publication_state") != "clean"):
            raise CoreStateError(f"{endpoint} owner graph is not in clean verified Core State")
        graph = _payload_graph(metadata.get("published_payload"),
                               metadata.get("published_payload_hash"), graph_iri, endpoint)
        graphs[graph_iri] = graph
        owner_payload_hashes.append((graph_iri, metadata["published_payload_hash"]))

    member_union = Graph()
    for row in store.resources("members"):
        if row["publication_state"] != "clean":
            raise CoreStateError(
                f"Member owner publication is dirty; Debates cannot resolve against an uncertain owner: {row['resource_iri']}")
        payload = row.get("published_payload")
        digest = row.get("published_payload_hash")
        if payload is None and digest is None:
            # Legacy Core State can contain a clean manifest entry without the
            # RDF payload needed for a source-validated resolver. It contributes
            # no owner candidate until a normal verified publication exists.
            owner_payload_hashes.append((row["graph_iri"], "unavailable"))
            continue
        graph = _payload_graph(payload, digest, row["graph_iri"], "Member")
        graphs[row["graph_iri"]] = graph
        member_union += graph
        owner_payload_hashes.append((row["graph_iri"], digest))

    house_graph = graphs.get(HOUSES_GRAPH)
    committee_graph = graphs.get(COMMITTEES_GRAPH)
    resolver = build_debate_reference_resolver(
        member_graph=member_union if len(member_union) else None,
        house_graph=house_graph,
        committee_graph=committee_graph,
    )
    canonical_owners = json.dumps(sorted(owner_payload_hashes), separators=(",", ":"))
    owner_snapshot_hash = hashlib.sha256(canonical_owners.encode("utf-8")).hexdigest()
    return DebateOwnerSnapshot(resolver, graphs, owner_snapshot_hash)


def _integration_dataset(result, owner_graphs: dict[str, Graph]) -> Dataset:
    dataset = Dataset()
    for graph_iri, source in sorted(owner_graphs.items()):
        target = dataset.graph(URIRef(graph_iri))
        for triple in source:
            target.add(triple)
    debate = dataset.graph(URIRef(result.graph_iri))
    for triple in result.graph:
        debate.add(triple)
    return dataset


def _checked_inputs(sources: list[DebateRawSource]) -> list[dict]:
    if not sources:
        raise DebateSourceError("supply at least one explicit AKN main.xml URL or preserved SHA-256 replay key")
    by_digest: dict[str, dict] = {}
    for source in sources:
        actual = hashlib.sha256(source.body).hexdigest()
        if actual != source.source_sha256:
            raise DebateSourceError("Debates raw source object does not match its declared SHA-256")
        try:
            stored = source.raw_path.read_bytes()
        except OSError as error:
            raise DebateSourceError(f"Debates raw source object is unavailable: {source.raw_path}") from error
        if stored != source.body or hashlib.sha256(stored).hexdigest() != actual:
            raise DebateSourceError("Debates raw source path is not the exact immutable input")
        current = by_digest.setdefault(actual, {
            "source_sha256": actual,
            "raw_path": source.raw_path,
            "body": source.body,
            "raw_source": source,
            "source_urls": set(),
        })
        if current["raw_path"] != source.raw_path and current["body"] != source.body:
            raise DebateSourceError("conflicting bytes share one Debates raw content hash")
        current["source_urls"].update(source.source_urls)
    return [by_digest[key] for key in sorted(by_digest)]


def _plan_records(sources: list[DebateRawSource], resolver, *,
                  owner_graphs: dict[str, Graph], store: CoreStateStore | None,
                  run_id: str | None, client, publish: bool,
                  owner_snapshot_hash: str) -> tuple[list[dict], list[DebateBatchOutcome]]:
    planned: list[dict] = []
    expressions_by_work: dict[str, dict[str, str]] = {}
    for item in _checked_inputs(sources):
        try:
            identity = inspect_debate_source_identity(item["body"])
        except (ValueError, TypeError, ET.ParseError):
            # The full transform owns diagnostic evidence and will fail closed
            # below; this fast identity pass only exists for known-good hashes.
            identity = None
        if identity is None:
            result = transform_debate(item["body"], resolver=resolver)
            identity = {
                "work_iri": result.work_iri,
                "expression_iri": result.expression_iri,
                "source_work_uri": result.reference_report["source_identity"]["work_frbruri"],
                "source_expression_uri": result.reference_report["source_identity"]["expression_frbruri"],
            }
            item["pretransformed"] = result
        try:
            matching_urls = []
            for source_url in sorted(item["source_urls"]):
                try:
                    validate_source_expression_url(source_url, identity["expression_iri"])
                except DebateSourceError:
                    continue
                matching_urls.append(source_url)
            if not matching_urls:
                raise DebateSourceError(
                    "preserved source evidence is not the main.xml object for its exact FRBRExpression")
        except (KeyError, TypeError) as error:
            raise DebateSourceError("Debates source identity lacks an exact Expression IRI") from error
        item.update(identity)
        item["source_url"] = matching_urls[0]
        item["run_id"] = run_id
        work_expressions = expressions_by_work.setdefault(item["work_iri"], {})
        prior_source_uri = work_expressions.get(item["expression_iri"])
        if prior_source_uri is not None and prior_source_uri != item["source_expression_uri"]:
            raise DebateSourceError("conflicting source FRBR Expression evidence has one canonical identity")
        work_expressions[item["expression_iri"]] = item["source_expression_uri"]
        planned.append(item)

    for work_iri, expression_values in sorted(expressions_by_work.items()):
        if len(expression_values) > 1:
            # Reuse the approved transformer failure for a known incomplete
            # Work bundle. The single-file case remains explicitly incomplete.
            first = next(item for item in planned if item["work_iri"] == work_iri)
            transform_debate(
                first["body"], resolver=resolver,
                known_expression_source_uris=tuple(expression_values.values()),
            )
            raise AssertionError("multiple Expression transform unexpectedly succeeded")

    by_resource: dict[tuple[str, str], dict] = {}
    for item in planned:
        key = (item["work_iri"], item["expression_iri"])
        prior = by_resource.get(key)
        if prior is not None:
            if prior["source_sha256"] != item["source_sha256"]:
                raise DebateSourceError(
                    "conflicting exact source bytes share one Debate Work/Expression identity")
            prior["source_urls"].update(item["source_urls"])
            continue
        by_resource[key] = item

    outcomes: list[DebateBatchOutcome] = []
    work_items: list[dict] = []
    resolver_version = getattr(resolver, "version", None)
    if not isinstance(resolver_version, str) or not resolver_version:
        raise CoreStateError("Debates owner resolver must expose its deterministic version")

    for item in sorted(by_resource.values(), key=lambda entry: entry["work_iri"]):
        graph_iri = expected_graph_iri("debates", item["work_iri"])
        item["graph_iri"] = graph_iri
        old = store.get_resource("debates", item["work_iri"]) if store is not None else None
        item["old"] = old
        if (old is not None and old.get("expression_iri")
                and old["expression_iri"] != item["expression_iri"]):
            raise DebateSourceError(
                "multiple known Expressions for one Debate Work; refusing to publish or replace its Work graph")
        if (publish and old is not None
                and old.get("publication_state") == "clean"
                and old.get("published_source_hash") == item["source_sha256"]
                and old.get("contract_version") == DEBATES_PUBLICATION_CONTRACT
                and old.get("graph_iri") == graph_iri
                and old.get("published_resolver_version") == resolver_version
                and old.get("published_owner_snapshot_hash") == owner_snapshot_hash
                and isinstance(old.get("published_reference_report_path"), str)
                and isinstance(old.get("published_reference_report_hash"), str)
                and isinstance(old.get("published_payload"), str)):
            payload = old["published_payload"]
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != old.get("published_payload_hash"):
                raise CoreStateError(f"stored Debate graph payload hash is corrupt: {item['work_iri']}")
            try:
                verify_reference_report(
                    old["published_reference_report_path"],
                    old["published_reference_report_hash"],
                    source_sha256=item["source_sha256"],
                    resolver_version=resolver_version,
                    owner_snapshot_hash=owner_snapshot_hash,
                )
            except DebateSourceError as error:
                raise CoreStateError(
                    f"stored Debate reference report is corrupt: {item['work_iri']}: {error}") from error
            try:
                # A clean source is skippable only while the complete remote
                # graph still equals its verified Core State payload.
                from .competency import verify_core_graph
                verify_core_graph(client, graph_iri, payload)
            except ValueError:
                pass
            else:
                stored_graph = Graph(identifier=URIRef(graph_iri))
                stored_graph.parse(data=payload, format="nt")
                store.observe_resource(
                    "debates", item["work_iri"], graph_iri, item["source_sha256"],
                    item["run_id"], raw_source_path=str(item["raw_path"].resolve()),
                    source_url=item["source_url"], expression_iri=item["expression_iri"],
                )
                outcomes.append(DebateBatchOutcome(
                    item["work_iri"], graph_iri, item["source_sha256"], "skipped",
                    len(stored_graph), stored_graph,
                ))
                continue

        result = item.get("pretransformed") or transform_debate(
            item["body"], resolver=resolver,
            known_expression_source_uris=(item["source_expression_uri"],),
        )
        if (result.work_iri != item["work_iri"]
                or result.expression_iri != item["expression_iri"]
                or result.source_sha256 != item["source_sha256"]
                or result.graph_iri != graph_iri):
            raise CoreStateError("Debates transformer result differs from source identity preflight")
        validate_debates_integration(
            result, _integration_dataset(result, owner_graphs),
            source_xml=item["body"],
        )
        report_path, report_hash = persist_reference_report(
            item["raw_source"], result.reference_report_json,
            resolver_version=resolver_version,
            owner_snapshot_hash=owner_snapshot_hash,
        )
        item["result"] = result
        item["payload"] = ntriples(result.graph)
        item["resolver_version"] = resolver_version
        item["owner_snapshot_hash"] = owner_snapshot_hash
        item["reference_report_path"] = report_path
        item["reference_report_hash"] = report_hash
        work_items.append(item)
        outcomes.append(DebateBatchOutcome(
            item["work_iri"], graph_iri, item["source_sha256"],
            "changed" if old is not None else "new", len(result.graph), result.graph,
        ))
    return work_items, outcomes


def run_debate_batch(sources: list[DebateRawSource], *,
                     store: CoreStateStore | None = None, run_id: str | None = None,
                     publish: bool = False, loader=None, client=None) -> list[DebateBatchOutcome]:
    """Validate and optionally publish only the explicitly supplied AKN objects.

    Every source is preserved before this function. All source/RDF/integration
    validation completes before the first graph mutation. A publish run uses
    the existing Core State dirty -> PUT -> exact-graph-verify -> clean order.
    """
    if publish and (store is None or not run_id or loader is None or client is None):
        raise ValueError("Debates publication requires Core State, an active run, GSP loader and SPARQL verifier")
    if not sources:
        raise DebateSourceError("supply at least one explicit AKN main.xml URL or preserved SHA-256 replay key")
    if store is not None:
        owner_snapshot = load_debate_owner_snapshot(store)
    else:
        owner_snapshot = DebateOwnerSnapshot(
            build_debate_reference_resolver(), {},
            hashlib.sha256(b"[]").hexdigest(),
        )
    work_items, outcomes = _plan_records(
        sources, owner_snapshot.resolver, owner_graphs=owner_snapshot.graphs,
        store=store, run_id=run_id,
        client=client, publish=publish,
        owner_snapshot_hash=owner_snapshot.snapshot_hash,
    )
    if publish:
        for item in work_items:
            digest = store.mark_publication_dirty(
                "debates", item["work_iri"], source_hash=item["source_sha256"],
                graph_iri=item["graph_iri"], payload=item["payload"],
                contract_version=DEBATES_PUBLICATION_CONTRACT,
                resolver_version=item["resolver_version"],
                owner_snapshot_hash=item["owner_snapshot_hash"],
                reference_report_path=item["reference_report_path"],
                reference_report_hash=item["reference_report_hash"],
                raw_source_path=str(item["raw_path"].resolve()),
                source_url=item["source_url"],
                expression_iri=item["expression_iri"],
                run_id=run_id,
            )
            loader.replace(item["graph_iri"], item["payload"],
                           content_type="application/n-triples")
            from .competency import verify_core_graph
            verify_core_graph(client, item["graph_iri"], item["payload"])
            store.complete_publication(
                "debates", item["work_iri"], source_hash=item["source_sha256"],
                graph_iri=item["graph_iri"], payload_hash=digest,
                contract_version=DEBATES_PUBLICATION_CONTRACT,
            )
    return outcomes
