from pathlib import Path

from rdflib import Dataset, Graph, Namespace, OWL, RDF, RDFS, URIRef

import validate
from oireachtas_etl.transforms.houses import transform_houses


ROOT = Path(__file__).resolve().parents[1]
OIR = Namespace("https://data.oireachtas.ie/ontology#")
ORG = Namespace("http://www.w3.org/ns/org#")
MEMBERS = Namespace("https://data.oireachtas.ie/ontology/members#")
OIREACHTAS = URIRef("https://data.oireachtas.ie/oireachtas")
DAIL = URIRef("https://data.oireachtas.ie/house/dail")
SEANAD = URIRef("https://data.oireachtas.ie/house/seanad")
GOVERNMENT = URIRef("https://data.oireachtas.ie/government")
BILL_SOURCE = URIRef("https://data.oireachtas.ie/ie/oireachtas/def/bill-source/government")


def ontology() -> Graph:
    return validate.load_ontology_graph()


def test_institutional_class_and_individual_identities_are_separate() -> None:
    graph = ontology()
    former_class = OIR.Oireachtas
    assert (OIREACHTAS, RDF.type, OWL.NamedIndividual) in graph
    assert (OIREACHTAS, RDF.type, OIR.ParliamentaryBody) in graph
    assert not list(graph.triples((former_class, RDF.type, OWL.Class)))
    assert (OIR.ParliamentaryBody, RDFS.subClassOf, ORG.FormalOrganization) in graph


def test_enduring_houses_are_structured_under_oireachtas_but_terms_are_not() -> None:
    graph = ontology()
    for house in (DAIL, SEANAD):
        assert (house, RDF.type, OIR.House) in graph
        assert (house, ORG.subOrganizationOf, OIREACHTAS) in graph
        assert (OIREACHTAS, ORG.hasSubOrganization, house) in graph
    assert (OIR.House, RDFS.subClassOf, OIR.ParliamentaryBody) in graph
    assert (OIR.HouseTerm, OWL.disjointWith, OIR.ParliamentaryBody) in graph
    assert not list(graph.triples((MEMBERS["Dáil-31"], None, None)))


def test_house_terms_remain_temporal_and_link_to_the_enduring_house() -> None:
    records = __import__("json").loads((ROOT / "data/api_examples/houses.json").read_text())
    graph = transform_houses(records)
    term = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34")
    assert (term, RDF.type, OIR.DailTerm) in graph
    assert (term, OIR.termOf, DAIL) in graph
    assert term != DAIL


def test_government_is_separate_and_accountable_to_enduring_dail() -> None:
    graph = ontology()
    assert (OIR.Government, RDFS.subClassOf, ORG.FormalOrganization) in graph
    assert (OIR.Government, OWL.disjointWith, OIR.ParliamentaryBody) in graph
    assert (GOVERNMENT, RDF.type, OIR.Government) in graph
    assert (GOVERNMENT, OIR.responsibleTo, DAIL) in graph
    assert (OIR.responsibleTo, RDFS.subPropertyOf, ORG.reportsTo) in graph


def test_cabinet_membership_requires_an_oireachtas_membership_and_bill_source_is_not_government() -> None:
    graph = ontology()
    constraints = list(graph.objects(MEMBERS.CabinetMembership, RDFS.subClassOf))
    assert any((constraint, OWL.onProperty, MEMBERS.isMembershipOfMember) in graph for constraint in constraints)
    assert any((constraint, OWL.onProperty, MEMBERS.isCabinetMembershipOf) in graph for constraint in constraints)
    assert (MEMBERS.isMembershipOfMember, OWL.inverseOf, MEMBERS.hasMembersMembership) in graph
    assert (BILL_SOURCE, RDF.type, OIR.GovernmentBillSource) in graph
    assert (BILL_SOURCE, RDF.type, OIR.Government) not in graph
    mapping = (ROOT / "mappings/bill_mapping.csv").read_text()
    assert "GovernmentBillSource" in mapping


def test_executive_and_benches_headship_do_not_infer_constitutional_government() -> None:
    graph = validate.load_local_ontology_graph()
    executive = URIRef("https://example.test/executive")
    benches = URIRef("https://example.test/benches")
    role = URIRef("https://example.test/role")
    graph.add((executive, RDF.type, MEMBERS.GovernmentExecutive))
    graph.add((benches, RDF.type, MEMBERS.GovernmentBenches))
    graph.add((role, RDF.type, MEMBERS.TaoiseachRole))
    graph.add((role, MEMBERS.isHeadOfExecutive, executive))
    graph.add((role, MEMBERS.isHeadOfBenches, benches))
    validate.run_consistency_check(graph)


def test_institutional_competency_queries_preserve_distinct_identities() -> None:
    records = __import__("json").loads((ROOT / "data/api_examples/houses.json").read_text())
    dataset = Dataset()
    graph = dataset.default_graph
    for triple in ontology():
        graph.add(triple)
    for triple in transform_houses(records):
        graph.add(triple)
    resources = ROOT / "src/oireachtas_etl/validation/resources"
    rows = list(dataset.query((resources / "dail-term-institution.rq").read_text()))
    assert (URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"), DAIL, OIREACHTAS) in rows
    accountability = list(dataset.query((resources / "government-accountability.rq").read_text()))
    assert accountability == [(GOVERNMENT, DAIL)]
