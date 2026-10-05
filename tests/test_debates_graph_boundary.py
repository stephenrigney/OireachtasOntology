"""Debates graph-boundary acceptance against disposable owner datasets.

Owner descriptions below come from the checked-in owner examples and their
normal endpoint transformers.  The Dataset and graph replacement helper are
test-local only: this file exercises RDF graph isolation, not Tranche 4
ingestion, state, or publication machinery.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.config import (
    ADMINISTRATIVE_UNITS_GRAPH,
    COMMITTEES_GRAPH,
    HOUSES_GRAPH,
    OFFICES_GRAPH,
)
from oireachtas_etl.transforms.bills import bill_graph_iri, transform_bill
from oireachtas_etl.transforms.common import ELIDL, MEMBERS, OIR
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.debates import DebateReferenceRegistry, transform_debate
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import member_graph_iri, transform_member
from oireachtas_etl.transforms.offices import (
    transform_administrative_units,
    transform_offices,
)
from oireachtas_etl.validation.debates import validate_debates
from oireachtas_etl.validation.debates_integration import validate_debates_integration


ROOT = Path(__file__).resolve().parents[1]
DEBATES_DIR = ROOT / "data" / "debates_examples"
AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
NS = {"akn": AKN}

MEMBER_SOURCE_HREF = "/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
DAIL_34_AUTHOR_HREF = "/ie/oireachtas/house/dail/34"
DAIL_34_TERM = URIRef(
    "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
)


@pytest.fixture(scope="module")
def owner_dataset():
    """Load genuine fixture-transformed owner graphs into a disposable Dataset."""

    member_source = json.loads(
        (ROOT / "data" / "api_examples" / "member.json").read_text(
            encoding="utf-8"
        )
    )
    house_source = json.loads(
        (ROOT / "data" / "api_examples" / "houses.json").read_text(
            encoding="utf-8"
        )
    )
    committee_source = json.loads(
        (ROOT / "tests" / "fixtures" / "committee-owner.json").read_text(
            encoding="utf-8"
        )
    )
    bill_source = json.loads(
        (ROOT / "data" / "api_examples" / "bill.json").read_text(
            encoding="utf-8"
        )
    )
    office_registry = json.loads(
        (ROOT / "registries" / "ministerial-office-registry.json").read_text(
            encoding="utf-8"
        )
    )

    member_graph = transform_member(member_source)
    house_graph = transform_houses(house_source)
    committee_graph = transform_committees(committee_source)
    bill = bill_source["results"][0]
    bill_graph = transform_bill(bill)
    office_graph = transform_offices(office_registry)
    administrative_unit_graph = transform_administrative_units(office_registry)

    # Treat these as loaded owner datasets, not as triples merged into a union
    # graph.  The names are the established endpoint/per-resource graph IRIs.
    graph_iris = {
        "members": member_graph_iri(member_source["member"]),
        "houses": HOUSES_GRAPH,
        "committees": COMMITTEES_GRAPH,
        "bill": bill_graph_iri(bill["bill"]),
        "offices": OFFICES_GRAPH,
        "administrative_units": ADMINISTRATIVE_UNITS_GRAPH,
    }
    source_graphs = {
        "members": member_graph,
        "houses": house_graph,
        "committees": committee_graph,
        "bill": bill_graph,
        "offices": office_graph,
        "administrative_units": administrative_unit_graph,
    }

    dataset = Dataset()
    for name, source_graph in source_graphs.items():
        target = dataset.graph(URIRef(graph_iris[name]))
        for triple in source_graph:
            target.add(triple)

    return {
        "dataset": dataset,
        "graph_iris": graph_iris,
        "source_graphs": source_graphs,
        "member_source": member_source,
        "house_source": house_source,
        "committee_source": committee_source,
        "office_registry": office_registry,
    }


@pytest.fixture(scope="module")
def resolved_debate(owner_dataset):
    """Dáil fixture resolved only through exact identities in owner examples."""

    member = URIRef(owner_dataset["member_source"]["member"]["uri"])
    house_graph = owner_dataset["source_graphs"]["houses"]
    assert (member, RDF.type, OIR.Member) in owner_dataset["source_graphs"]["members"]
    assert (DAIL_34_TERM, RDF.type, OIR.DailTerm) in house_graph
    term_houses = set(house_graph.objects(DAIL_34_TERM, OIR.termOf))
    assert len(term_houses) == 1
    house = next(iter(term_houses))
    assert (house, RDF.type, OIR.House) in house_graph

    resolver = DebateReferenceRegistry(
        members_by_tlc_href={MEMBER_SOURCE_HREF: member},
        house_terms_by_author_href={DAIL_34_AUTHOR_HREF: DAIL_34_TERM},
        # Derive House identity from the actual owner graph's termOf assertion.
        houses_by_term_iri={str(DAIL_34_TERM): house},
        version="checked-in-owner-datasets-v1",
    )
    result = transform_debate(
        (DEBATES_DIR / "dail_2026-02-26.akn.xml").read_bytes(),
        resolver=resolver,
    )
    validate_debates(result)
    return {"result": result, "member": member, "term": DAIL_34_TERM, "house": house}


def _snapshot_owner_graphs(owner_dataset) -> dict[str, frozenset[tuple]]:
    dataset = owner_dataset["dataset"]
    return {
        name: frozenset(dataset.graph(URIRef(graph_iri)))
        for name, graph_iri in owner_dataset["graph_iris"].items()
    }


def _copy_with_triple(result, triple):
    graph = Graph(identifier=URIRef(result.graph_iri))
    for existing in result.graph:
        graph.add(existing)
    graph.add(triple)
    return replace(result, graph=graph)


def _work_owned_iri(subject, result) -> bool:
    """Independent check of the approved Work/Expression-owned IRI routes."""

    if not isinstance(subject, URIRef):
        return False
    value = str(subject)
    work = result.work_iri
    expression = result.expression_iri
    if value in {work, expression, work + "#sitting"}:
        return True
    if value.startswith(expression + "/eid/e-"):
        return True
    if value.startswith(expression + "/fallback/fb-"):
        return True
    if value.endswith("#participation"):
        parent = value[: -len("#participation")]
        return parent.startswith(expression + "/eid/e-") or parent.startswith(
            expression + "/fallback/fb-"
        )
    return False


def _replace_debate_graph_in_test_dataset(dataset: Dataset, result) -> None:
    """Test-local validated whole-context replacement; not a publication path."""

    validate_debates(result)
    identifier = URIRef(result.graph_iri)
    dataset.remove_graph(identifier)
    target = dataset.graph(identifier)
    for triple in result.graph:
        target.add(triple)


def test_debate_graph_links_to_owner_iris_but_describes_only_work_resources(
    owner_dataset, resolved_debate
):
    result = resolved_debate["result"]
    graph = result.graph
    owner_subjects = set().union(
        *(set(source.subjects()) for source in owner_dataset["source_graphs"].values())
    )
    debate_subjects = set(graph.subjects())

    # This assertion is test-local and uses the approved Work/Expression route,
    # not a transformer ownership helper or a type-derived subject whitelist.
    assert all(_work_owned_iri(subject, result) for subject in debate_subjects)
    assert not debate_subjects & owner_subjects

    member, term, house = (
        resolved_debate["member"],
        resolved_debate["term"],
        resolved_debate["house"],
    )
    assert (None, OIR.votedFor, member) in graph or (None, OIR.votedAgainst, member) in graph
    assert (URIRef(result.work_iri), OIR.recordOfHouseTerm, term) in graph
    assert (URIRef(result.work_iri), OIR.recordOfBody, house) in graph

    reference_predicates = (
        OIR.speaker,
        OIR.askedBy,
        OIR.votedFor,
        OIR.votedAgainst,
        OIR.abstained,
        OIR.recordOfBody,
        OIR.recordOfHouseTerm,
        ELIDL.had_participant_person,
        ELIDL.participation_role,
    )
    referenced_owner_subjects = {
        target
        for predicate in reference_predicates
        for target in graph.objects(None, predicate)
        if target in owner_subjects
    }
    assert referenced_owner_subjects == {member, term, house}
    for target in referenced_owner_subjects:
        assert not list(graph.triples((target, None, None)))

    # Each linked target is actually described in its established owner graph.
    assert (member, RDF.type, OIR.Member) in owner_dataset["source_graphs"]["members"]
    assert (term, RDF.type, OIR.DailTerm) in owner_dataset["source_graphs"]["houses"]
    assert (house, RDF.type, OIR.House) in owner_dataset["source_graphs"]["houses"]


@pytest.mark.parametrize(
    "owner_name",
    ("members", "houses", "committees", "bill", "offices", "administrative_units"),
)
def test_validator_rejects_descriptions_copied_from_each_loaded_owner_graph(
    owner_dataset, resolved_debate, owner_name
):
    owner_graph = owner_dataset["source_graphs"][owner_name]
    typed_subjects = sorted(
        (
            (str(subject), str(class_iri))
            for subject, class_iri in owner_graph.subject_objects(RDF.type)
            if isinstance(subject, URIRef) and isinstance(class_iri, URIRef)
        )
    )
    assert typed_subjects, f"{owner_name} owner fixture should contain a typed resource"
    foreign_subject, foreign_class = map(URIRef, typed_subjects[0])
    corrupted = _copy_with_triple(
        resolved_debate["result"], (foreign_subject, RDF.type, foreign_class)
    )

    # The copied type is a deliberate foreign description.  Validation must
    # reject it even though that subject is valid in its real owner graph.
    with pytest.raises(ValueError, match="RDF types may describe only|unowned subject"):
        validate_debates(corrupted)


def test_validated_replacement_is_context_local_and_invalid_replacement_is_rejected(
    owner_dataset, resolved_debate
):
    dataset = owner_dataset["dataset"]
    result = resolved_debate["result"]
    owner_before = _snapshot_owner_graphs(owner_dataset)
    debate_context = dataset.graph(URIRef(result.graph_iri))
    stale = (
        URIRef(result.work_iri),
        URIRef("https://example.test/obsoleteDebateAssertion"),
        URIRef("https://example.test/obsoleteTarget"),
    )
    debate_context.add(stale)
    old_debate_graph = frozenset(debate_context)
    assert stale in old_debate_graph

    # A foreign-owner description fails validation before the test-local
    # replacement touches the previously loaded Debate context.
    member = resolved_debate["member"]
    corrupted = _copy_with_triple(result, (member, RDF.type, OIR.Member))
    with pytest.raises(ValueError, match="RDF types may describe only|unowned subject"):
        _replace_debate_graph_in_test_dataset(dataset, corrupted)
    assert frozenset(dataset.graph(URIRef(result.graph_iri))) == old_debate_graph
    assert _snapshot_owner_graphs(owner_dataset) == owner_before

    # A valid complete graph replacement removes obsolete Debate content and
    # changes no separately named owner context.
    _replace_debate_graph_in_test_dataset(dataset, result)
    assert frozenset(dataset.graph(URIRef(result.graph_iri))) == frozenset(result.graph)
    assert stale not in set(dataset.graph(URIRef(result.graph_iri)))
    validate_debates_integration(result, dataset)
    assert _snapshot_owner_graphs(owner_dataset) == owner_before


def test_unresolved_member_target_is_audited_without_link_or_invented_resource(
    owner_dataset
):
    member = URIRef(owner_dataset["member_source"]["member"]["uri"])
    house_graph = owner_dataset["source_graphs"]["houses"]
    assert (member, RDF.type, OIR.Member) in owner_dataset["source_graphs"]["members"]
    assert (DAIL_34_TERM, RDF.type, OIR.DailTerm) in house_graph
    house = next(iter(set(house_graph.objects(DAIL_34_TERM, OIR.termOf))))
    resolver = DebateReferenceRegistry(
        members_by_tlc_href={},
        house_terms_by_author_href={DAIL_34_AUTHOR_HREF: DAIL_34_TERM},
        houses_by_term_iri={str(DAIL_34_TERM): house},
        version="owner-graphs-without-member-match-v1",
    )
    before = _snapshot_owner_graphs(owner_dataset)
    result = transform_debate(
        (DEBATES_DIR / "dail_2026-02-26.akn.xml").read_bytes(),
        resolver=resolver,
    )
    validate_debates(result)

    missing_member_rows = [
        row
        for row in result.reference_report["reference_outcomes"]
        if row["raw_reference"] == "#TimDooley" and row["slot"].startswith("division/")
    ]
    assert missing_member_rows
    assert all(row["status"] == "unresolved" for row in missing_member_rows)
    assert all("target_iri" not in row for row in missing_member_rows)
    assert not any(member in triple for triple in result.graph)
    assert all(_work_owned_iri(subject, result) for subject in result.graph.subjects())
    assert _snapshot_owner_graphs(owner_dataset) == before


def test_unresolved_committee_author_does_not_guess_loaded_committee_identity(
    owner_dataset
):
    committee_graph = owner_dataset["source_graphs"]["committees"]
    committee_subject = next(committee_graph.subjects(RDF.type, MEMBERS.Committee))
    assert committee_subject is not None

    source = (DEBATES_DIR / "committee_public_accounts_2026-09-24.akn.xml").read_bytes()
    root = ET.fromstring(source)
    author_href = root.find(".//akn:FRBRWork/akn:FRBRauthor", NS).get("href")
    source_author_iri = URIRef("https://data.oireachtas.ie" + author_href)
    # The checked-in Committee owner example and this AKN author are distinct
    # exact identities.  No slug/path alias is introduced by this test.
    assert source_author_iri != committee_subject

    before = _snapshot_owner_graphs(owner_dataset)
    result = transform_debate(
        source,
        resolver=DebateReferenceRegistry(version="committee-owner-example-only-v1"),
    )
    validate_debates(result)
    work = URIRef(result.work_iri)
    body_rows = [
        row
        for row in result.reference_report["reference_outcomes"]
        if row["slot"] == "FRBRWork/FRBRauthor/@href->recordOfBody"
    ]
    assert len(body_rows) == 1
    assert body_rows[0]["status"] == "unresolved"
    assert "target_iri" not in body_rows[0]
    assert not list(result.graph.objects(work, OIR.recordOfBody))
    assert not any(source_author_iri in triple for triple in result.graph)
    assert not any(committee_subject in triple for triple in result.graph)
    assert _snapshot_owner_graphs(owner_dataset) == before


def test_unresolved_question_recipient_does_not_create_named_office_rdf(owner_dataset):
    member_source = owner_dataset["member_source"]
    member = URIRef(member_source["member"]["uri"])
    house_graph = owner_dataset["source_graphs"]["houses"]
    term_houses = set(house_graph.objects(DAIL_34_TERM, OIR.termOf))
    assert len(term_houses) == 1
    house = next(iter(term_houses))
    resolver = DebateReferenceRegistry(
        members_by_tlc_href={MEMBER_SOURCE_HREF: member},
        house_terms_by_author_href={DAIL_34_AUTHOR_HREF: DAIL_34_TERM},
        houses_by_term_iri={str(DAIL_34_TERM): house},
        version="checked-in-owner-datasets-v1",
    )
    before = _snapshot_owner_graphs(owner_dataset)
    result = transform_debate(
        (DEBATES_DIR / "dail_2015-07-02.akn.xml").read_bytes(),
        resolver=resolver,
    )
    validate_debates(result)

    recipients = [
        row
        for row in result.reference_report["reference_outcomes"]
        if row["slot"] == "question/@to->directedTo/directedToOffice"
    ]
    assert recipients
    assert all(row["status"] == "unresolved" for row in recipients)
    assert all("target_iri" not in row for row in recipients)
    assert not list(result.graph.triples((None, OIR.directedTo, None)))
    assert not list(result.graph.triples((None, OIR.directedToOffice, None)))

    known_offices = set(
        owner_dataset["source_graphs"]["offices"].subjects(RDF.type, MEMBERS.NamedOffice)
    )
    assert known_offices
    assert not known_offices & set(result.graph.subjects())
    assert not known_offices & set(result.graph.objects())
    assert not list(result.graph.subjects(RDF.type, MEMBERS.NamedOffice))
    assert _snapshot_owner_graphs(owner_dataset) == before
