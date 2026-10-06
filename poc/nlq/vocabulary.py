"""Read predicates supported by ontology declarations and active mappings."""

from __future__ import annotations

import csv
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .contract import load_query_contract


PROPERTY_TYPES = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)


def supported_predicates(ontology_dir: str | Path) -> frozenset[URIRef]:
    """Return the contract's configured allowlist, resolved from ontology/mappings.

    The contract owns the allowlist policy. Repository ontology and active
    mapping files remain authoritative for the actual predicate IRIs.
    """
    contract = load_query_contract()
    policy = contract["localSafety"]["predicateAllowlist"]
    directory = Path(ontology_dir)
    repository_root = directory.parent
    graph = Graph()
    prefixes: dict[str, str] = dict(contract["namespaces"])
    modules = sorted(directory.glob("*.owl.ttl"))
    if not modules:
        raise FileNotFoundError(f"No Turtle ontology modules found in {directory}")
    for path in modules:
        module = Graph().parse(path, format="turtle")
        for prefix, namespace in module.namespaces():
            if prefix:
                prefixes.setdefault(str(prefix), str(namespace))
        graph += module
    for path, format_ in (
        (directory / "ELI-OWL" / "eli-1.5.rdf", "xml"),
        (directory / "ELI-DL-OWL" / "eli-dl.ttl", "turtle"),
    ):
        if path.is_file():
            vocabulary = Graph().parse(path, format=format_)
            for prefix, namespace in vocabulary.namespaces():
                if prefix:
                    prefixes.setdefault(str(prefix), str(namespace))
            graph += vocabulary

    local_namespaces = tuple(prefixes[prefix] for prefix in policy["localOntologyPrefixes"])
    supported: set[URIRef] = set()
    if policy["includeLocalOntologyDeclarations"]:
        supported.update(
            term
            for property_type in PROPERTY_TYPES
            for term in graph.subjects(RDF.type, property_type)
            if isinstance(term, URIRef) and str(term).startswith(local_namespaces)
        )

    if policy["includeLocallyAnnotatedExternalProperties"]:
        for module_path in modules:
            module = Graph().parse(module_path, format="turtle")
            for term in module.subjects(RDFS.comment):
                if (isinstance(term, URIRef)
                        and any((term, RDF.type, property_type) in graph
                                for property_type in PROPERTY_TYPES)
                        and not str(term).startswith(local_namespaces)):
                    supported.add(term)

    for term in policy["unconditionalPredicates"]:
        prefix, local_name = term.split(":", 1)
        supported.add(URIRef(prefixes[prefix] + local_name))

    mapping_dir = repository_root / "mappings"
    if mapping_dir.is_dir():
        for path in sorted(mapping_dir.glob("*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    if row.get("mapping_status") not in policy["activeMappingStatuses"]:
                        continue
                    if row.get("term_type") not in policy["activeMappingTermTypes"]:
                        continue
                    term = (row.get("ontology_term") or "").strip()
                    if ":" not in term:
                        continue
                    prefix, local_name = term.split(":", 1)
                    namespace = prefixes.get(prefix)
                    if namespace and local_name and not any(char.isspace() for char in local_name):
                        supported.add(URIRef(namespace + local_name))
    return frozenset(supported)
