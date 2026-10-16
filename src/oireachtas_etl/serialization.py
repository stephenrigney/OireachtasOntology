"""Stable developer and publication serializations (no blank-node identifiers)."""
from rdflib import Dataset, Graph, URIRef

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

def trig(graph: Graph, graph_iri: str) -> str:
    dataset = Dataset()
    target = dataset.graph(URIRef(graph_iri))
    for triple in graph: target.add(triple)
    return str(dataset.serialize(format="trig"))
