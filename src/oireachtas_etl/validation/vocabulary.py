"""Pinned Phase 4 ELI/ELI-DL vocabulary coverage checks."""
from __future__ import annotations

import hashlib
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF

ELI = "http://data.europa.eu/eli/ontology#"
ELIDL = "http://data.europa.eu/eli/eli-draft-legislation-ontology#"

ROOT = Path(__file__).resolve().parents[3]
ELI_PATH = ROOT / "ontology/ELI-OWL/eli-1.5.rdf"
ELIDL_PATH = ROOT / "ontology/ELI-DL-OWL/eli-dl.ttl"
PINS = {
    ELI_PATH: "35bba63a0945e089817ddeb25512d31bfa101344282a4dfbce58e92ad756111c",
    ELIDL_PATH: "5ec2d7a0bb176e1432e39fee3e4150c3f651dafaef52976428259be4f9eabb62",
}


def pinned_vocabulary_graphs() -> tuple[Graph, Graph]:
    """Load only local, hash-verified Phase 4 vocabulary sources."""
    for path, expected in PINS.items():
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"pinned vocabulary checksum mismatch: {path}")
    return Graph().parse(ELI_PATH, format="xml"), Graph().parse(ELIDL_PATH, format="turtle")


def assert_phase4_vocabulary(graph: Graph, eli_vendor: Graph, elidl_vendor: Graph) -> None:
    """Reject every emitted ELI/ELI-DL class or predicate outside pinned terms."""
    def declared(vendor: Graph) -> set[URIRef]:
        return set(vendor.subjects(RDF.type, OWL.Class)) | set(vendor.subjects(RDF.type, OWL.ObjectProperty)) | set(vendor.subjects(RDF.type, OWL.DatatypeProperty)) | set(vendor.subjects(RDF.type, OWL.AnnotationProperty))
    eli_declared, elidl_declared = declared(eli_vendor), declared(elidl_vendor)
    for subject, predicate, object_ in graph:
        for term in (predicate, object_ if predicate == RDF.type else None):
            if not isinstance(term, URIRef):
                continue
            value = str(term)
            if value.startswith(ELIDL) and term not in elidl_declared:
                raise ValueError(f"undeclared pinned ELI-DL 3.0 term emitted: {term}")
            if value.startswith(ELI) and term not in eli_declared:
                raise ValueError(f"undeclared pinned ELI 1.5 term emitted: {term}")
