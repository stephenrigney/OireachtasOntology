"""Transform the reviewed local ministerial office and unit registry."""
from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from .common import MEMBERS


ADMINISTRATIVE_UNIT_BASE = "https://data.oireachtas.ie/administrative-unit/"
OFFICE_BASE = "https://data.oireachtas.ie/office/"

# This table is deliberately independent of the OWL role classes. It is the
# versioned ETL rule used by the later Cabinet-episode tranche; uncategorized
# office types have no inferred Cabinet qualification.
OFFICE_TYPE_POLICY_VERSION = 1
OFFICE_TYPE_CABINET_QUALIFICATION = {
    "TaoiseachOfficeType": True,
    "TanaisteOfficeType": True,
    "MinisterOfficeType": True,
    "MinisterOfStateOfficeType": False,
}


def administrative_unit_iri(key: str) -> URIRef:
    return URIRef(ADMINISTRATIVE_UNIT_BASE + key)


def office_iri(key: str) -> URIRef:
    return URIRef(OFFICE_BASE + key)


def _labels(graph: Graph, subject: URIRef, entry: dict) -> None:
    graph.add((subject, SKOS.prefLabel, Literal(entry["label_en"], lang="en")))
    if "label_ga" in entry:
        graph.add((subject, SKOS.prefLabel, Literal(entry["label_ga"], lang="ga")))
    for alias in entry["aliases"]:
        graph.add((subject, SKOS.altLabel, Literal(alias["label"], lang=alias["language"])))


def transform_administrative_units(registry: dict) -> Graph:
    """Describe only reviewed AdministrativeUnit identities in their graph."""
    graph = Graph()
    graph.bind("members", MEMBERS)
    for unit in registry["administrative_units"]:
        subject = administrative_unit_iri(unit["key"])
        graph.add((subject, RDF.type, MEMBERS.AdministrativeUnit))
        _labels(graph, subject, unit)
    return graph


def transform_offices(registry: dict) -> Graph:
    """Describe only reviewed NamedOffice identities and evidenced unit links."""
    graph = Graph()
    graph.bind("members", MEMBERS)
    for office in registry["offices"]:
        subject = office_iri(office["key"])
        graph.add((subject, RDF.type, MEMBERS.NamedOffice))
        graph.add((subject, MEMBERS.hasRoleType, MEMBERS[office["office_type"]]))
        _labels(graph, subject, office)
        for relationship in office["unit_relationships"]:
            graph.add((subject, MEMBERS[relationship["relationship"]],
                       administrative_unit_iri(relationship["unit_key"])))
    return graph
