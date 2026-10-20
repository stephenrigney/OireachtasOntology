"""Stable developer and publication serializations (no blank-node identifiers)."""
import hashlib

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD

def turtle(graph: Graph) -> str:
    return str(graph.serialize(format="turtle"))

def nquads(graph: Graph, graph_iri: str) -> str:
    context = URIRef(graph_iri)
    dataset = Dataset()
    target = dataset.graph(context)
    for triple in graph:
        target.add(triple)
    serialized = dataset.serialize(format="nquads", encoding="utf-8")
    return "".join(sorted(line + "\n" for line in serialized.decode("utf-8").splitlines()))

def ntriples(graph: Graph) -> str:
    serialized = graph.serialize(format="nt", encoding="utf-8")
    return "".join(sorted(line + "\n" for line in serialized.decode("utf-8").splitlines()))


def rdf11_ntriples_sha256(graph: Graph) -> str:
    """Hash sorted N-Triples after RDF 1.1 simple/xsd:string normalization.

    Fuseki/Jena may serialize an explicit ``xsd:string`` literal as a plain
    literal. RDF 1.1 gives those two forms the same meaning, so semantic graph
    evidence must not treat that serializer choice as a data difference.
    """
    normalized = Graph()
    for subject, predicate, obj in graph:
        if (isinstance(obj, Literal) and obj.language is None
                and obj.datatype == XSD.string):
            obj = Literal(str(obj))
        normalized.add((subject, predicate, obj))
    return hashlib.sha256(ntriples(normalized).encode("utf-8")).hexdigest()

def trig(graph: Graph, graph_iri: str) -> str:
    dataset = Dataset()
    target = dataset.graph(URIRef(graph_iri))
    for triple in graph: target.add(triple)
    return str(dataset.serialize(format="trig"))
