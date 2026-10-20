from __future__ import annotations

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD

from oireachtas_etl.serialization import nquads, ntriples


SUBJECT = URIRef("https://example.test/resource")
PREDICATE = URIRef("https://example.test/value")
GRAPH_IRI = "https://example.test/graph"


def literal_graph(*, reverse: bool = False) -> Graph:
    values = [
        Literal('line one\nline two\rquoted "text" and \\ slash — Gaeilge 日本語'),
        Literal('teanga\n"athfhriotail" \\', lang="ga"),
        Literal('first line\nsecond line "quoted" \\', datatype=XSD.string),
        Literal("42", datatype=XSD.integer),
    ]
    if reverse:
        values.reverse()
    graph = Graph()
    for value in values:
        graph.add((SUBJECT, PREDICATE, value))
    return graph


def test_ntriples_uses_valid_escaped_lexical_forms_and_is_deterministic():
    graph = literal_graph()
    first = ntriples(graph)
    second = ntriples(literal_graph(reverse=True))

    assert first == second
    assert '"""' not in first
    parsed = Graph().parse(data=first, format="nt")
    assert set(parsed) == set(graph)
    assert ntriples(parsed) == first


def test_nquads_uses_valid_escaped_lexical_forms_and_is_deterministic():
    graph = literal_graph()
    first = nquads(graph, GRAPH_IRI)
    second = nquads(literal_graph(reverse=True), GRAPH_IRI)

    assert first == second
    assert '"""' not in first
    parsed = Dataset().parse(data=first, format="nquads")
    quads = set(parsed.quads())
    assert {(subject, predicate, obj) for subject, predicate, obj, context in quads} == set(graph)
    assert {str(context) for _, _, _, context in quads} == {GRAPH_IRI}
    assert nquads(parsed.graph(URIRef(GRAPH_IRI)), GRAPH_IRI) == first
