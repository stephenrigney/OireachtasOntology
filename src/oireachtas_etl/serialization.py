"""Stable developer and publication serializations (no blank-node identifiers)."""
from rdflib import Dataset, Graph, URIRef

def turtle(graph: Graph) -> str:
    return str(graph.serialize(format="turtle"))

def nquads(graph: Graph, graph_iri: str) -> str:
    context = URIRef(graph_iri)
    lines = [f"{s.n3()} {p.n3()} {o.n3()} {context.n3()} .\n" for s, p, o in graph]
    return "".join(sorted(lines))

def ntriples(graph: Graph) -> str:
    return "".join(sorted(f"{s.n3()} {p.n3()} {o.n3()} .\n" for s, p, o in graph))

def trig(graph: Graph, graph_iri: str) -> str:
    dataset = Dataset()
    target = dataset.graph(URIRef(graph_iri))
    for triple in graph: target.add(triple)
    return str(dataset.serialize(format="trig"))
