from importlib.resources import files
from rdflib import Graph
from rdflib.namespace import Namespace
from pyshacl import validate
from .reference import validate_constituencies_correspondence
from .houses import validate_rdf

RESOURCES = files("oireachtas_etl.validation.resources")

# This is the validation contract, not an import of the transform's dispatch
# table.  Keeping the expected vocabulary here means a class-selection bug in
# the production transformer cannot make its own output validate.
MEMBERS = Namespace("https://data.oireachtas.ie/ontology/members#")
EXPECTED_REPRESENT_TYPES = {
    "constituency": (MEMBERS.DailConstituency, "dail"),
    "panel": (MEMBERS.SeanadPanel, "seanad"),
}


def validate_source(records: list[dict]) -> None:
    if not isinstance(records, list) or not records:
        raise ValueError("Constituencies reference dataset must be a non-empty list")
    validate_constituencies_correspondence(records, None, EXPECTED_REPRESENT_TYPES)


def validate_shacl(graph: Graph) -> None:
    conforms, _, report = validate(graph, shacl_graph=RESOURCES.joinpath("constituencies.ttl").read_text(), shacl_graph_format="turtle", inference="none", abort_on_first=False)
    if not conforms:
        raise ValueError("SHACL validation failed:\n" + str(report))


def validate_quality(graph: Graph) -> None:
    failures = list(graph.query(RESOURCES.joinpath("constituencies-quality.rq").read_text()))
    if failures:
        raise ValueError("quality checks failed: " + "; ".join(str(row) for row in failures))


def validate_constituencies(records: list[dict], graph: Graph) -> None:
    validate_source(records)
    validate_constituencies_correspondence(records, graph, EXPECTED_REPRESENT_TYPES)
    validate_rdf(graph)
    validate_shacl(graph)
    validate_quality(graph)
