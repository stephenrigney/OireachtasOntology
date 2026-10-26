"""Deterministic RDF enrichment from the reviewed affiliation decision register."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

MEMBERS = Namespace("https://data.oireachtas.ie/ontology/members#")
IDENTITY_BASE = "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/"
GRAPH_IRI = "https://data.oireachtas.ie/graph/political-affiliations/identities"
DECISIONS = Path(__file__).resolve().parents[2] / "reports/party-identity-decisions.json"


class PoliticalAffiliationError(ValueError):
    pass


def build_graph(decisions_path: str | Path = DECISIONS) -> Dataset:
    """Validate the complete reviewed register and return its publication dataset."""
    try:
        data = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
        identities = data["identities"]
        records = data["records"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PoliticalAffiliationError("invalid political-affiliation decision register") from exc
    by_id: dict[str, dict] = {}
    for identity in identities:
        key = identity.get("id")
        if not isinstance(key, str) or not key or key in by_id or identity.get("iri") != IDENTITY_BASE + key:
            raise PoliticalAffiliationError("duplicate or malformed identity in decision register")
        if not isinstance(identity.get("label"), str) or not identity["label"] or not isinstance(identity.get("aliases"), list):
            raise PoliticalAffiliationError(f"malformed identity definition: {key}")
        by_id[key] = identity
    seen: set[str] = set()
    accepted: list[tuple[str, str]] = []
    excluded = 0
    for row in records:
        source = row.get("source_iri")
        if not isinstance(source, str) or source in seen:
            raise PoliticalAffiliationError(f"duplicate or missing source IRI: {source!r}")
        parts = urlsplit(source)
        if parts.scheme != "https" or parts.netloc != "data.oireachtas.ie" or not parts.path.startswith("/ie/oireachtas/party/"):
            raise PoliticalAffiliationError(f"unknown source party IRI: {source!r}")
        seen.add(source)
        outcome = row.get("outcome")
        if outcome == "accepted":
            identity = row.get("identity")
            if identity not in by_id:
                raise PoliticalAffiliationError(f"unknown identity for {source}")
            accepted.append((source, identity))
        elif outcome == "excluded":
            excluded += 1
        else:
            raise PoliticalAffiliationError(f"unresolved or unknown outcome for {source}")
    if (len(by_id), len(records), len(accepted), excluded, len(seen)) != (33, 315, 314, 1, 315):
        raise PoliticalAffiliationError("decision register accounting does not match 33 identities / 314 accepted / 1 excluded")
    ds = Dataset()
    graph = ds.graph(URIRef(GRAPH_IRI))
    for key, identity in sorted(by_id.items()):
        iri = URIRef(identity["iri"])
        graph.add((iri, RDF.type, MEMBERS.PoliticalAffiliationIdentity))
        graph.add((iri, SKOS.prefLabel, Literal(identity["label"], lang="en")))
        for alias in sorted(set(identity["aliases"])):
            if not isinstance(alias, str) or not alias:
                raise PoliticalAffiliationError(f"invalid alias for {key}")
            graph.add((iri, SKOS.altLabel, Literal(alias, lang="en")))
    for source, key in sorted(accepted):
        graph.add((URIRef(source), MEMBERS.hasPoliticalAffiliationIdentity, URIRef(by_id[key]["iri"])))
    return ds


def serialize() -> str:
    """Canonical stable N-Quads suitable for validation and graph replacement."""
    dataset = build_graph()
    rows = sorted(dataset.quads((None, None, None, None)), key=lambda q: tuple(term.n3() for term in q))
    return "".join(f"{s.n3()} {p.n3()} {o.n3()} <{g}> .\n" for s, p, o, g in rows)


def publish(gsp_endpoint: str, sparql_endpoint: str, *, user: str | None = None, password: str | None = None) -> None:
    """Replace only the dedicated enrichment graph, then verify its exact contents."""
    from .loader import FusekiGraphStoreLoader, FusekiSparqlClient
    payload = serialize()
    expected = build_graph().graph(URIRef(GRAPH_IRI))
    FusekiGraphStoreLoader(gsp_endpoint, user=user, password=password).replace(
        GRAPH_IRI, payload, content_type="application/n-quads")
    actual = FusekiSparqlClient(sparql_endpoint, user=user, password=password).construct_graph(GRAPH_IRI)
    if set(actual) != set(expected):
        raise RuntimeError("political-affiliation graph whole-graph verification failed")
