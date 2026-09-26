"""Read predicates supported by ontology declarations and active mappings."""

from __future__ import annotations

import csv
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import FOAF, OWL, RDF, RDFS


PROPERTY_TYPES = (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty)


def supported_predicates(ontology_dir: str | Path) -> frozenset[URIRef]:
    """Return declared properties plus mapped or locally annotated properties.

    The mapping term list intentionally supplements ontology declarations for
    reused external vocabularies (e.g. ELI and FOAF) whose property axioms are
    not copied into local modules. External properties specifically annotated
    by local ontology modules are also supported.
    """
    directory = Path(ontology_dir)
    repository_root = directory.parent
    graph = Graph()
    prefixes: dict[str, str] = {}
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

    supported = {
        term
        for property_type in PROPERTY_TYPES
        for term in graph.subjects(RDF.type, property_type)
        if (isinstance(term, URIRef) and str(term).startswith((
            "https://data.oireachtas.ie/ontology#",
            "https://data.oireachtas.ie/ontology/members#",
        )))
    }
    # rdf:type is foundational and rdfs:label is used by the Bills ETL even
    # though mapping rows describe that use as implicit. Reconciliation emits
    # these additional predicates only in separately owned external-link graphs.
    supported.update((RDF.type, RDFS.label, OWL.sameAs, FOAF.isPrimaryTopicOf))
    for module_path in modules:
        module = Graph().parse(module_path, format="turtle")
        for term in module.subjects(RDFS.comment):
            if (isinstance(term, URIRef) and (term, RDF.type, OWL.ObjectProperty) in graph
                    or isinstance(term, URIRef) and (term, RDF.type, OWL.DatatypeProperty) in graph
                    or isinstance(term, URIRef) and (term, RDF.type, OWL.AnnotationProperty) in graph):
                if not str(term).startswith((
                    "https://data.oireachtas.ie/ontology#",
                    "https://data.oireachtas.ie/ontology/members#",
                )):
                    supported.add(term)
    mapping_dir = repository_root / "mappings"
    for path in sorted(mapping_dir.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if (row.get("mapping_status") not in {"mapped", "new"}
                        or row.get("term_type") not in {"ObjectProperty", "DatatypeProperty", "AnnotationProperty"}):
                    continue
                term = (row.get("ontology_term") or "").strip()
                if ":" not in term:
                    continue
                prefix, local_name = term.split(":", 1)
                namespace = prefixes.get(prefix)
                if namespace and local_name and not any(char.isspace() for char in local_name):
                    supported.add(URIRef(namespace + local_name))
    return frozenset(supported)
