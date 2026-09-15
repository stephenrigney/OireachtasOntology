from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCAT, DCTERMS, OWL, RDF, SKOS
from .common import ELIDL, OIR, english, integer, iri, midnight, string

HOUSES = {
    "dail": (OIR.DailTerm, URIRef("https://data.oireachtas.ie/house/dail")),
    "seanad": (OIR.SeanadTerm, URIRef("https://data.oireachtas.ie/house/seanad")),
}
PERSISTENT_HOUSES = {
    "dail": (URIRef("https://data.oireachtas.ie/house/dail"), "Dáil Éireann"),
    "seanad": (URIRef("https://data.oireachtas.ie/house/seanad"), "Seanad Éireann"),
}

def transform_houses_with_report(records: list[dict]) -> tuple[Graph, list[dict]]:
    graph = Graph()
    graph.bind("", OIR); graph.bind("eli-dl", ELIDL); graph.bind("dcat", DCAT); graph.bind("dct", DCTERMS); graph.bind("skos", SKOS)
    exclusions = []
    for _, (persistent_house, label) in PERSISTENT_HOUSES.items():
        graph.add((persistent_house, RDF.type, OIR.House)); graph.add((persistent_house, RDF.type, OWL.NamedIndividual))
        graph.add((persistent_house, DCTERMS.title, Literal(label, lang="ga")))
        graph.add((persistent_house, SKOS.prefLabel, Literal(label, lang="ga")))
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("house"), dict):
            raise ValueError("each Houses record must contain a house object")
        house = wrapper["house"]
        code = house.get("houseCode")
        if code == "dail & seanad":
            exclusions.append({"uri": house.get("uri"), "houseCode": code, "reason": "combined-house record"})
            continue
        if code not in HOUSES: raise ValueError(f"unsupported houseCode: {code!r}")
        term, persistent_house = HOUSES[code]
        subject = iri(house.get("uri"))
        period = URIRef(str(subject) + "#term-period")
        dates = house.get("dateRange")
        if not isinstance(dates, dict): raise ValueError("house.dateRange is required")
        graph.add((subject, RDF.type, term)); graph.add((subject, RDF.type, ELIDL.ParliamentaryTerm))
        graph.add((subject, OIR.termOf, persistent_house)); graph.add((subject, SKOS.prefLabel, english(house.get("showAs"))))
        graph.add((subject, OIR.termNo, integer(house.get("houseNo")))); graph.add((subject, OIR.houseCode, string(code)))
        graph.add((subject, OIR.seats, integer(house.get("seats")))); graph.add((subject, DCTERMS.temporal, period))
        graph.add((period, RDF.type, DCTERMS.PeriodOfTime)); graph.add((period, DCAT.startDate, midnight(dates.get("start"))))
        if dates.get("end") is not None: graph.add((period, DCAT.endDate, midnight(dates["end"])))
    return graph, exclusions

def transform_houses(records: list[dict]) -> Graph:
    return transform_houses_with_report(records)[0]
