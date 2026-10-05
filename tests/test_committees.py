from __future__ import annotations

import json
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from oireachtas_etl.reference_coverage import build_reference_census
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.transforms.common import MEMBERS, OIR
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.validation.committees import validate_committees, validate_shacl


ROOT = Path(__file__).resolve().parents[1]
RECORDS = json.loads((ROOT / "tests/fixtures/committee-owner.json").read_text())
COMMITTEE = URIRef(RECORDS[0]["uri"])


def test_committee_owner_graph_matches_golden_and_is_deterministic():
    graph = transform_committees(RECORDS)
    expected = Graph().parse(ROOT / "tests/expected/committees.ttl", format="turtle")
    assert set(graph) == set(expected)
    assert ntriples(graph) == ntriples(transform_committees(RECORDS))
    validate_committees(RECORDS, graph)
    assert (COMMITTEE, RDF.type, MEMBERS.Committee) in graph
    assert (COMMITTEE, MEMBERS.committeeInHouseTerm,
            URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/33")) in graph


def test_committee_competency_query_runs_against_the_named_owner_graph():
    from oireachtas_etl.competency import COMMITTEES_EXPECTED, QUERIES
    from oireachtas_etl.config import COMMITTEES_GRAPH

    dataset = Dataset()
    target = dataset.graph(URIRef(COMMITTEES_GRAPH))
    for triple in transform_committees(RECORDS):
        target.add(triple)
    actual = {}
    for filename in COMMITTEES_EXPECTED:
        actual[filename] = [
            {str(key): str(value) for key, value in row.asdict().items()}
            for row in dataset.query(QUERIES.joinpath(filename).read_text())
        ]
    assert actual == COMMITTEES_EXPECTED


def test_committee_source_iri_controls_term_not_member_house_context():
    member_record = {
        "member": {"uri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Example",
                   "memberships": [{"membership": {
                       "uri": "https://data.oireachtas.ie/ie/oireachtas/membership/example",
                       "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26",
                                 "houseCode": "seanad", "houseNo": "26"},
                       "committees": [{**RECORDS[0],
                                       "memberDateRange": {"start": "2023-01-01", "end": None},
                                       "role": [{"role": "Chair"}]}],
                   }}]},
    }
    census = build_reference_census(
        member_records=[member_record], member_capture_complete=True)
    committee = census["records"]["committees"][0]
    graph = transform_committees([committee])
    dail_term = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/33")
    seanad_term = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/seanad/26")
    assert (COMMITTEE, MEMBERS.committeeInHouseTerm, dail_term) in graph
    assert (COMMITTEE, MEMBERS.committeeInHouseTerm, seanad_term) not in graph
    assert not list(graph.triples((COMMITTEE, MEMBERS.hasMembershipDateRange, None)))
    assert not list(graph.triples((COMMITTEE, MEMBERS.hasCommitteeRole, None)))
    assert not list(graph.triples((COMMITTEE, MEMBERS.memberDateRange, None)))


@pytest.mark.parametrize(("field", "value"), [
    ("houseCode", "seanad"), ("houseNo", "34"),
])
def test_committee_owner_rejects_supplied_house_context_that_disagrees_with_iri(field, value):
    record = {**RECORDS[0], field: value}
    with pytest.raises(ValueError, match=f"committee\\.{field} must agree"):
        transform_committees([record])


def test_committee_owner_never_infers_missing_classification_from_slug_or_label():
    record = {
        "uri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_committee_on_finance",
        "committeeName": [{"nameEn": "Select Committee on Finance"}],
    }
    graph = transform_committees([record])
    assert not list(graph.objects(COMMITTEE, OIR.hasCommitteeType))
    assert not list(graph.objects(COMMITTEE, OIR.hasCommitteePurpose))
    assert (COMMITTEE, SKOS.prefLabel, None) in graph
    validate_committees([record], graph)


def test_committee_owner_rejects_reverse_operational_range_and_duplicate_language_labels():
    reverse = {**RECORDS[0],
               "committeeDateRange": {"start": "2024-01-01", "end": "2020-01-01"}}
    with pytest.raises(ValueError, match="reverse dates"):
        transform_committees([reverse])

    graph = transform_committees(RECORDS)
    graph.add((COMMITTEE, SKOS.prefLabel, Literal("Duplicate", lang="en")))
    with pytest.raises(ValueError, match="SHACL validation failed"):
        validate_shacl(graph)
