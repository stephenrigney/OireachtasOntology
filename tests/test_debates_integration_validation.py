"""Focused Tranche 3 validation using real transformer result/owner RDF."""
from __future__ import annotations

import json
from pathlib import Path
import warnings
from xml.sax.saxutils import quoteattr

import pytest
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, RDFS

from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH
from oireachtas_etl.transforms.common import ELIDL, MEMBERS, OIR
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.debates import DebateReferenceRegistry, transform_debate
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import member_graph_iri, transform_member_with_report
from oireachtas_etl.validation.committees import validate_committees
from oireachtas_etl.validation.debates_integration import (
    RDF_ONLY_LIMITATIONS,
    SOURCE_AWARE_LIMITATIONS,
    validate_debates_integration,
)
from oireachtas_etl.validation.houses import validate_houses
from oireachtas_etl.validation.members import validate_member


ROOT = Path(__file__).resolve().parents[1]
DEBATE_DIR = ROOT / "data" / "debates_examples"
MEMBER_HREF = "/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
DAIL_34_HREF = "/ie/oireachtas/house/dail/34"
DAIL_34_TERM = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34")
DAIL_HOUSE = URIRef("https://data.oireachtas.ie/house/dail")
COMMITTEE = URIRef(
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_committee_on_finance"
)
COMMITTEE_HREF = "/ie/oireachtas/committee/dail/33/select_committee_on_finance"


@pytest.fixture(scope="module")
def validated_owner_graphs():
    """Genuine API/owner fixtures transformed and passed to owner validators."""
    houses_source = json.loads((ROOT / "data/api_examples/houses.json").read_text())
    houses = transform_houses(houses_source)

    member_source = json.loads((ROOT / "data/api_examples/member.json").read_text())
    member, _ = transform_member_with_report(member_source)

    committee_source = json.loads((ROOT / "tests/fixtures/committee-owner.json").read_text())
    committees = transform_committees(committee_source)
    # The installed RDFLib/pySHACL pair emits Dataset compatibility deprecations
    # during validation; keep this focused acceptance suite readable.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Dataset.default_context is deprecated",
                                category=DeprecationWarning)
        warnings.filterwarnings("ignore", message="Dataset.identifier is deprecated",
                                category=DeprecationWarning)
        validate_houses(houses_source, houses)
        validate_member(member_source, member)
        validate_committees(committee_source, committees)

    return {
        URIRef(HOUSES_GRAPH): houses,
        URIRef(COMMITTEES_GRAPH): committees,
        URIRef(member_graph_iri(member_source["member"])): member,
    }


def _dataset(result, owners):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Dataset.default_context is deprecated",
                                category=DeprecationWarning)
        warnings.filterwarnings("ignore", message="Dataset.identifier is deprecated",
                                category=DeprecationWarning)
        dataset = Dataset()
        debate_context = dataset.graph(URIRef(result.graph_iri))
        for triple in result.graph:
            debate_context.add(triple)
        for graph_iri, graph in owners.items():
            context = dataset.graph(graph_iri)
            for triple in graph:
                context.add(triple)
    return dataset


def _dail_resolver(owners):
    member_graph = owners[next(name for name in owners if str(name).startswith(
        "https://data.oireachtas.ie/graph/member/"))]
    member = next(member_graph.subjects(RDF.type, OIR.Member))
    houses = owners[URIRef(HOUSES_GRAPH)]
    return DebateReferenceRegistry(
        members_by_tlc_href={MEMBER_HREF: member},
        house_terms_by_author_href={DAIL_34_HREF: DAIL_34_TERM},
        houses_by_term_iri={str(DAIL_34_TERM): next(houses.objects(DAIL_34_TERM, OIR.termOf))},
        version="validated-fixture-owner-graphs-v1",
    )


def _debate(filename, *, resolver=None):
    return transform_debate((DEBATE_DIR / filename).read_bytes(), resolver=resolver)


def test_valid_result_joins_member_house_and_term_to_named_owner_graphs(validated_owner_graphs):
    result = _debate("dail_2026-02-26.akn.xml",
                     resolver=_dail_resolver(validated_owner_graphs))

    validate_debates_integration(result, _dataset(result, validated_owner_graphs))

    work = URIRef(result.work_iri)
    assert (work, OIR.recordOfHouseTerm, DAIL_34_TERM) in result.graph
    assert (work, OIR.recordOfBody, DAIL_HOUSE) in result.graph
    member = next(iter(result.graph.objects(None, OIR.votedFor)))
    assert set(result.graph.objects(None, OIR.votedFor)) | set(
        result.graph.objects(None, OIR.votedAgainst)
    ) == {member}


def test_exact_committee_reference_joins_real_committee_and_house_term_owners(
    validated_owner_graphs,
):
    work_path = "/akn/ie/debateRecord/dail/2026-01-01/debate"
    source = (
        '<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13">'
        "<debate><meta><identification>"
        f"<FRBRWork><FRBRuri value={quoteattr(work_path)}/>"
        '<FRBRdate name="#generation" date="2026-01-01"/>'
        '<FRBRname value="debate"/>'
        f"<FRBRauthor href={quoteattr(COMMITTEE_HREF)}/></FRBRWork>"
        f"<FRBRExpression><FRBRuri value={quoteattr(work_path + '/eng@')}/>"
        '<FRBRlanguage language="eng"/></FRBRExpression>'
        "</identification></meta><debateBody/></debate></akomaNtoso>"
    ).encode()
    result = transform_debate(
        source,
        resolver=DebateReferenceRegistry(
            committees_by_author_href={COMMITTEE_HREF: COMMITTEE},
            version="exact-validated-committee-owner-v1",
        ),
    )

    validate_debates_integration(result, _dataset(result, validated_owner_graphs))

    assert (URIRef(result.work_iri), OIR.recordOfBody, COMMITTEE) in result.graph
    assert not list(result.graph.objects(URIRef(result.work_iri), OIR.recordOfHouseTerm))


def test_representative_reports_cover_four_statuses_without_placeholder_rdf(
    validated_owner_graphs,
):
    statuses = set()
    observed_slots = set()
    for filename in (
        "dail_2015-07-02.akn.xml",
        "dail_2026-02-26.akn.xml",
        "seanad_2015-07-02.akn.xml",
        "committee_public_accounts_2026-09-24.akn.xml",
        "dail_written_answers_2015-07-02.akn.xml",
    ):
        source_xml = (DEBATE_DIR / filename).read_bytes()
        result = transform_debate(source_xml, resolver=None)
        reference_rows = result.reference_report["reference_outcomes"]
        statuses.update(row["status"] for row in reference_rows)
        observed_slots.update(row["slot"] for row in reference_rows)
        validate_debates_integration(
            result, _dataset(result, validated_owner_graphs), source_xml=source_xml,
        )
        assert not any(
            isinstance(value, URIRef) and str(value) in {"#", "", "#?"}
            for _, _, value in result.graph
        )

    assert statuses == {"resolved", "unresolved", "malformed", "absent"}
    assert observed_slots == {
        "speech/@by",
        "speech/@as->eli-dl:participation_role",
        "question/@by",
        "question/@to->directedTo/directedToOffice",
        "FRBRWork/FRBRauthor/@href->recordOfBody",
        "FRBRWork/FRBRauthor/@href->recordOfHouseTerm",
        "debateSection/@refersTo->refersToEvent",
        "analysis/voting/@href->result-Summary-Division-join",
        "analysis/voting/@outcome->divisionOutcome",
        "analysis/voting/@refersTo->refersToProposal",
        "analysis/voting/count/@refersTo->aggregate-count-category",
        "division/ta/person/@refersTo->votedFor",
        "division/nil/person/@refersTo->votedAgainst",
        "division/staon/person/@refersTo->abstained",
    }
    assert any("source-aware" in limitation and "transcript" in limitation
               for limitation in RDF_ONLY_LIMITATIONS)
    assert any("source-aware" in limitation and "rollCall" in limitation
               for limitation in RDF_ONLY_LIMITATIONS)
    assert any("does not claim completeness" in limitation
               for limitation in SOURCE_AWARE_LIMITATIONS)


def test_source_aware_inventory_detects_missing_unresolved_speaker_row(
    validated_owner_graphs,
):
    source_xml = (DEBATE_DIR / "dail_2015-07-02.akn.xml").read_bytes()
    result = transform_debate(source_xml)
    rows = result.reference_report["reference_outcomes"]
    missing = next(row for row in rows
                   if row["slot"] == "speech/@by" and row["status"] == "unresolved")
    rows.remove(missing)
    dataset = _dataset(result, validated_owner_graphs)

    # The no-source mode deliberately checks only self-consistency/coherence;
    # an omitted unresolved row has no corresponding RDF edge to expose it.
    validate_debates_integration(result, dataset)
    with pytest.raises(ValueError, match="source inventory/reference report mismatch"):
        validate_debates_integration(result, dataset, source_xml=source_xml)


def test_source_aware_validation_recomputes_exact_source_hash(validated_owner_graphs):
    source_xml = (DEBATE_DIR / "dail_2015-07-02.akn.xml").read_bytes()
    result = transform_debate(source_xml)
    changed_source = source_xml + b"\n"

    with pytest.raises(ValueError, match="exact source XML bytes SHA-256"):
        validate_debates_integration(
            result, _dataset(result, validated_owner_graphs), source_xml=changed_source,
        )


def test_source_aware_inventory_rejects_duplicate_report_row(validated_owner_graphs):
    source_xml = (DEBATE_DIR / "dail_2015-07-02.akn.xml").read_bytes()
    result = transform_debate(source_xml)
    row = next(row for row in result.reference_report["reference_outcomes"]
               if row["slot"] == "speech/@by")
    result.reference_report["reference_outcomes"].append(dict(row))

    with pytest.raises(ValueError, match="source inventory/reference report mismatch"):
        validate_debates_integration(
            result, _dataset(result, validated_owner_graphs), source_xml=source_xml,
        )


def test_source_aware_inventory_rejects_source_inconsistent_status(validated_owner_graphs):
    source_xml = (DEBATE_DIR / "dail_2015-07-02.akn.xml").read_bytes()
    result = transform_debate(source_xml)
    row = next(row for row in result.reference_report["reference_outcomes"]
               if row["slot"] == "question/@to->directedTo/directedToOffice"
               and row["status"] == "unresolved"
               and row["raw_reference"] not in (None, "#"))
    row["status"] = "malformed"

    with pytest.raises(ValueError, match="status .* is inconsistent with its source slot"):
        validate_debates_integration(
            result, _dataset(result, validated_owner_graphs), source_xml=source_xml,
        )


def test_unresolved_question_recipient_and_section_event_never_become_rdf_links(
    validated_owner_graphs,
):
    result = _debate("dail_2015-07-02.akn.xml")
    graph = result.graph

    validate_debates_integration(result, _dataset(result, validated_owner_graphs))

    for predicate in (OIR.directedTo, OIR.directedToOffice, OIR.refersToEvent,
                      OIR.refersToProposal):
        assert not list(graph.triples((None, predicate, None)))
    rows = result.reference_report["reference_outcomes"]
    assert any(row["slot"] == "question/@to->directedTo/directedToOffice"
               and row["status"] == "unresolved" for row in rows)
    assert any(row["slot"] == "debateSection/@refersTo->refersToEvent"
               and row["status"] == "unresolved" for row in rows)


def test_missing_member_type_in_named_owner_graph_fails_shacl(validated_owner_graphs):
    result = _debate("dail_2026-02-26.akn.xml",
                     resolver=_dail_resolver(validated_owner_graphs))
    dataset = _dataset(result, validated_owner_graphs)
    member_graph_iri = next(
        name for name in validated_owner_graphs
        if str(name).startswith("https://data.oireachtas.ie/graph/member/")
    )
    member_context = dataset.graph(member_graph_iri)
    member = next(member_context.subjects(RDF.type, OIR.Member))
    member_context.remove((member, RDF.type, OIR.Member))

    with pytest.raises(ValueError, match="SHACL validation failed"):
        validate_debates_integration(result, dataset)


def test_wrong_house_term_owner_relationship_fails_semantic_quality(validated_owner_graphs):
    result = _debate("dail_2026-02-26.akn.xml",
                     resolver=_dail_resolver(validated_owner_graphs))
    dataset = _dataset(result, validated_owner_graphs)
    houses = dataset.graph(URIRef(HOUSES_GRAPH))
    houses.remove((DAIL_34_TERM, OIR.termOf, DAIL_HOUSE))
    seanad = URIRef("https://data.oireachtas.ie/house/seanad")
    houses.add((DAIL_34_TERM, OIR.termOf, seanad))

    with pytest.raises(ValueError, match="termOf must resolve to the matching enduring House"):
        validate_debates_integration(result, dataset)


def test_missing_committee_type_in_named_owner_graph_fails_shacl(validated_owner_graphs):
    work_path = "/akn/ie/debateRecord/dail/2026-01-01/debate"
    source = (
        '<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13">'
        "<debate><meta><identification>"
        f"<FRBRWork><FRBRuri value={quoteattr(work_path)}/>"
        '<FRBRdate name="#generation" date="2026-01-01"/>'
        '<FRBRname value="debate"/>'
        f"<FRBRauthor href={quoteattr(COMMITTEE_HREF)}/></FRBRWork>"
        f"<FRBRExpression><FRBRuri value={quoteattr(work_path + '/eng@')}/>"
        '<FRBRlanguage language="eng"/></FRBRExpression>'
        "</identification></meta><debateBody/></debate></akomaNtoso>"
    ).encode()
    result = transform_debate(
        source,
        resolver=DebateReferenceRegistry(
            committees_by_author_href={COMMITTEE_HREF: COMMITTEE},
            version="exact-validated-committee-owner-v1",
        ),
    )
    dataset = _dataset(result, validated_owner_graphs)
    dataset.graph(URIRef(COMMITTEES_GRAPH)).remove((COMMITTEE, RDF.type, MEMBERS.Committee))

    with pytest.raises(ValueError, match="SHACL validation failed"):
        validate_debates_integration(result, dataset)


def test_named_debate_graph_must_match_result_graph(validated_owner_graphs):
    result = _debate("dail_2015-07-02.akn.xml")
    dataset = _dataset(result, validated_owner_graphs)
    debate_context = dataset.graph(URIRef(result.graph_iri))
    debate_context.remove((URIRef(result.work_iri), OIR.debateDate, None))

    with pytest.raises(ValueError, match="must exactly equal the actual transform result"):
        validate_debates_integration(result, dataset)


def test_nonconsecutive_source_ordinal_fails_the_integration_gate(validated_owner_graphs):
    result = _debate("dail_2015-07-02.akn.xml")
    section = next(result.graph.subjects(RDF.type, OIR.DebateSection))
    old = next(result.graph.objects(section, OIR.sourceOrdinal))
    result.graph.remove((section, OIR.sourceOrdinal, old))
    result.graph.add((section, OIR.sourceOrdinal, Literal(999, datatype=old.datatype)))

    with pytest.raises(ValueError, match="consecutive 1-based ordinals"):
        validate_debates_integration(result, _dataset(result, validated_owner_graphs))


def test_unreported_vote_link_is_rejected_even_when_member_is_a_real_owner(
    validated_owner_graphs,
):
    result = _debate("dail_2026-02-26.akn.xml",
                     resolver=_dail_resolver(validated_owner_graphs))
    dataset = _dataset(result, validated_owner_graphs)
    member_graph = validated_owner_graphs[
        next(name for name in validated_owner_graphs
             if str(name).startswith("https://data.oireachtas.ie/graph/member/"))
    ]
    member = next(member_graph.subjects(RDF.type, OIR.Member))
    division = next(result.graph.subjects(RDF.type, OIR.Division))
    triple = (division, OIR.abstained, member)
    result.graph.add(triple)
    dataset.graph(URIRef(result.graph_iri)).add(triple)

    with pytest.raises(ValueError, match="RDF/reference report mismatch"):
        validate_debates_integration(result, dataset)


@pytest.mark.parametrize("predicate", [OIR.taCount, OIR.divisionOutcome])
def test_aggregate_count_and_outcome_must_match_source_hash_report(
    predicate, validated_owner_graphs,
):
    result = _debate("dail_2026-02-26.akn.xml",
                     resolver=_dail_resolver(validated_owner_graphs))
    dataset = _dataset(result, validated_owner_graphs)
    division = next(result.graph.subjects(RDF.type, OIR.Division))
    old_value = next(result.graph.objects(division, predicate))
    result.graph.remove((division, predicate, old_value))
    if predicate == OIR.taCount:
        result.graph.add((division, predicate,
                          Literal(int(str(old_value)) + 1, datatype=old_value.datatype)))
    else:
        replacement = (OIR.DeclaredLost if old_value == OIR.DeclaredCarried
                       else OIR.DeclaredCarried)
        result.graph.add((division, predicate, replacement))
    changed = dataset.graph(URIRef(result.graph_iri))
    changed.remove((division, predicate, old_value))
    changed.add(next(result.graph.triples((division, predicate, None))))

    with pytest.raises(ValueError, match="RDF/reference report mismatch"):
        validate_debates_integration(result, dataset)


def test_report_cannot_mark_an_unresolved_placeholder_as_a_resolved_member(
    validated_owner_graphs,
):
    result = _debate("committee_public_accounts_2026-09-24.akn.xml")
    row = next(
        row for row in result.reference_report["reference_outcomes"]
        if row["slot"] == "speech/@by" and row["status"] == "unresolved"
        and row["raw_reference"] == "#"
    )
    member_graph = validated_owner_graphs[
        next(name for name in validated_owner_graphs
             if str(name).startswith("https://data.oireachtas.ie/graph/member/"))
    ]
    row["status"] = "resolved"
    row["target_iri"] = str(next(member_graph.subjects(RDF.type, OIR.Member)))

    with pytest.raises(ValueError, match="RDF/reference report mismatch"):
        validate_debates_integration(result, _dataset(result, validated_owner_graphs))


def test_extra_unowned_transcript_description_fails_rdf_boundary(validated_owner_graphs):
    result = _debate("dail_2015-07-02.akn.xml")
    summary = next(result.graph.subjects(RDF.type, OIR.Summary))
    result.graph.add((summary, RDFS.label, Literal("copied transcript prose")))
    dataset = _dataset(result, validated_owner_graphs)
    # Keep the named graph identical to the actual transformed graph, including
    # the deliberately corrupted triple.
    with pytest.raises(ValueError, match="prose/description predicate"):
        validate_debates_integration(result, dataset)
