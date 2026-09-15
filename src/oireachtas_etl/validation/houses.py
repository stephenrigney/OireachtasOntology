from importlib.resources import files
from rdflib import Graph
from pyshacl import validate
from ..transforms.houses import transform_houses

RESOURCES = files("oireachtas_etl.validation.resources")

def validate_source(records: list[dict]) -> None:
    # Transformation's strict conversion is also the source schema contract.
    transform_houses(records)

def validate_rdf(graph: Graph) -> None:
    reparsed = Graph()
    reparsed.parse(data=graph.serialize(format="nt"), format="nt")
    for _, _, value in reparsed:
        if hasattr(value, "datatype") and value.datatype is not None and str(value.datatype).startswith("http://www.w3.org/2001/XMLSchema#"):
            if value.value is None:
                raise ValueError(f"invalid RDF datatype literal: {value.n3()}")

def validate_shacl(graph: Graph) -> None:
    conforms, _, report = validate(graph, shacl_graph=RESOURCES.joinpath("houses.ttl").read_text(), shacl_graph_format="turtle", inference="none", abort_on_first=False)
    if not conforms: raise ValueError("SHACL validation failed:\n" + str(report))

def validate_quality(graph: Graph) -> None:
    result = graph.query(RESOURCES.joinpath("houses-quality.rq").read_text())
    failures = list(result)
    if failures: raise ValueError("quality checks failed: " + "; ".join(str(row) for row in failures))

def validate_houses(records: list[dict], graph: Graph) -> None:
    validate_source(records); validate_rdf(graph); validate_shacl(graph); validate_quality(graph)
