from rdflib import Graph
from rdflib.namespace import RDF, SKOS

from .common import MEMBERS, english, iri, string


def transform_parties(records: list[dict]) -> Graph:
    """Map term-scoped party records without describing their HouseTerms."""
    graph = Graph()
    graph.bind("members", MEMBERS)
    graph.bind("skos", SKOS)
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("party"), dict) or not isinstance(wrapper.get("house"), dict):
            raise ValueError("each Parties record must contain party and house objects")
        party, house = wrapper["party"], wrapper["house"]
        subject, term = iri(party.get("uri")), iri(house.get("uri"))
        code = party.get("partyCode")
        graph.add((subject, RDF.type, MEMBERS.PartyGrouping))
        if code != "Independent":
            graph.add((subject, RDF.type, MEMBERS.Party))
        graph.add((subject, MEMBERS.partyCode, string(code)))
        graph.add((subject, SKOS.prefLabel, english(party.get("showAs"))))
        graph.add((subject, MEMBERS.activeDuringTerm, term))
    return graph
