"""Small Graph Store/SPARQL stand-in for whole-graph publication tests."""

from __future__ import annotations

from rdflib import BNode, Dataset, Graph, Literal, URIRef


def _binding(term) -> dict[str, str]:
    if isinstance(term, URIRef):
        return {"type": "uri", "value": str(term)}
    if isinstance(term, BNode):
        return {"type": "bnode", "value": str(term)}
    result = {"type": "literal", "value": str(term)}
    if term.datatype:
        result["datatype"] = str(term.datatype)
    if term.language:
        result["xml:lang"] = term.language
    return result


class InMemoryFuseki:
    """Persist named graph replacements and execute verification queries."""

    def __init__(self) -> None:
        self.dataset = Dataset()
        self.replacements: list[tuple[str, str, str]] = []
        self.queries: list[str] = []

    def replace(self, graph_iri: str, payload: str, *, content_type: str) -> None:
        if content_type != "application/n-triples":
            raise AssertionError(f"unexpected Graph Store content type: {content_type}")
        self.replacements.append((graph_iri, payload, content_type))
        identifier = URIRef(graph_iri)
        self.dataset.remove_graph(identifier)
        target = self.dataset.graph(identifier)
        if payload:
            for triple in Graph().parse(data=payload, format="nt"):
                target.add(triple)

    def query(self, sparql: str) -> list[dict]:
        self.queries.append(sparql)
        result = self.dataset.query(sparql)
        return [
            {str(name): _binding(row[name]) for name in result.vars
             if row[name] is not None}
            for row in result
        ]

    def construct_graph(self, graph_iri: str) -> Graph:
        identifier = URIRef(graph_iri)
        result = Graph()
        for triple in self.dataset.graph(identifier):
            result.add(triple)
        return result
