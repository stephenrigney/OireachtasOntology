from importlib.resources import files
from rdflib import Graph
from pyshacl import validate
from .reference import validate_parties_correspondence
from .houses import validate_rdf

RESOURCES = files("oireachtas_etl.validation.resources")


def validate_source(records: list[dict]) -> None:
    if not isinstance(records, list) or not records:
        raise ValueError("Parties reference dataset must be a non-empty list")
    validate_parties_correspondence(records, None)


def validate_shacl(graph: Graph) -> None:
    conforms, _, report = validate(graph, shacl_graph=RESOURCES.joinpath("parties.ttl").read_text(), shacl_graph_format="turtle", inference="none", abort_on_first=False)
    if not conforms:
        raise ValueError("SHACL validation failed:\n" + str(report))


def validate_quality(graph: Graph) -> None:
    failures = list(graph.query(RESOURCES.joinpath("parties-quality.rq").read_text()))
    if failures:
        raise ValueError("quality checks failed: " + "; ".join(str(row) for row in failures))


def validate_parties(records: list[dict], graph: Graph) -> None:
    validate_source(records)
    validate_parties_correspondence(records, graph)
    validate_rdf(graph)
    validate_shacl(graph)
    validate_quality(graph)
