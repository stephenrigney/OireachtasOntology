from rdflib import Graph
from rdflib.namespace import RDF, SKOS

from .common import MEMBERS, english, iri, string

REPRESENT_TYPES = {
    "constituency": (MEMBERS.DailConstituency, "dail"),
    "panel": (MEMBERS.SeanadPanel, "seanad"),
}


def transform_constituencies(records: list[dict]) -> Graph:
    """Map term-scoped constituencies and panels without describing HouseTerms."""
    graph = Graph()
    graph.bind("members", MEMBERS)
    graph.bind("skos", SKOS)
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("constituencyOrPanel"), dict) or not isinstance(wrapper.get("house"), dict):
            raise ValueError("each Constituencies record must contain constituencyOrPanel and house objects")
        representation, house = wrapper["constituencyOrPanel"], wrapper["house"]
        represent_type = representation.get("representType")
        if represent_type not in REPRESENT_TYPES:
            raise ValueError(f"unsupported representType: {represent_type!r}")
        class_, expected_house = REPRESENT_TYPES[represent_type]
        if house.get("houseCode") != expected_house:
            raise ValueError(f"representType {represent_type!r} requires houseCode {expected_house!r}")
        subject, term = iri(representation.get("uri")), iri(house.get("uri"))
        graph.add((subject, RDF.type, MEMBERS.Constituencies))
        graph.add((subject, RDF.type, class_))
        graph.add((subject, MEMBERS.representCode, string(representation.get("representCode"))))
        graph.add((subject, SKOS.prefLabel, english(representation.get("showAs"))))
        graph.add((subject, MEMBERS.constituencyInHouseTerm, term))
    return graph
