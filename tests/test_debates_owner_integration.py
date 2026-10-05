"""Integration of Debates references with validated owner RDF graphs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH
from oireachtas_etl.debates_owners import build_debate_reference_resolver
from oireachtas_etl.transforms.common import MEMBERS, OIR
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.debates import transform_debate
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import member_graph_iri, transform_member
from oireachtas_etl.validation.committees import validate_committees
from oireachtas_etl.validation.debates_integration import validate_debates_integration
from oireachtas_etl.validation.houses import validate_houses
from oireachtas_etl.validation.members import validate_member


ROOT = Path(__file__).resolve().parents[1]
DEBATES_DIR = ROOT / "data" / "debates_examples"
AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
MEMBER_HREF = "/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
MEMBER_IRI = URIRef("https://data.oireachtas.ie" + MEMBER_HREF)
DAIL_34_HREF = "/ie/oireachtas/house/dail/34"
DAIL_34_TERM = URIRef("https://data.oireachtas.ie" + DAIL_34_HREF)
DAIL_HOUSE = URIRef("https://data.oireachtas.ie/house/dail")
COMMITTEE_HREF = "/ie/oireachtas/committee/dail/33/select_committee_on_finance"
COMMITTEE_IRI = URIRef("https://data.oireachtas.ie" + COMMITTEE_HREF)
OLD_COMMITTEE_HREF = "/ie/oireachtas/committee/select_committee_on_finance/33"


@pytest.fixture(scope="module")
def validated_owner_graphs():
    """Build and source-validate the checked-in owner examples independently."""

    member_source = json.loads(
        (ROOT / "data/api_examples/member.json").read_text(encoding="utf-8")
    )
    house_source = json.loads(
        (ROOT / "data/api_examples/houses.json").read_text(encoding="utf-8")
    )
    committee_source = json.loads(
        (ROOT / "tests/fixtures/committee-owner.json").read_text(encoding="utf-8")
    )

    member_graph = transform_member(member_source)
    validate_member(member_source, member_graph)
    house_graph = transform_houses(house_source)
    validate_houses(house_source, house_graph)
    committee_graph = transform_committees(committee_source)
    validate_committees(committee_source, committee_graph)

    return {
        "member_graph": member_graph,
        "house_graph": house_graph,
        "committee_graph": committee_graph,
        "member_source": member_source,
        "house_source": house_source,
        "committee_source": committee_source,
    }


def _resolver(validated_owner_graphs, *, committee_graph=None):
    return build_debate_reference_resolver(
        member_graph=validated_owner_graphs["member_graph"],
        house_graph=validated_owner_graphs["house_graph"],
        committee_graph=(
            validated_owner_graphs["committee_graph"]
            if committee_graph is None
            else committee_graph
        ),
    )


def _rows(result, slot: str) -> list[dict]:
    return [
        row for row in result.reference_report["reference_outcomes"]
        if row["slot"] == slot
    ]


def _assert_hash_linked_report(result, source: bytes) -> None:
    expected = hashlib.sha256(source).hexdigest()
    assert result.source_sha256 == expected
    assert result.reference_report["source_sha256"] == expected
    assert result.reference_report["resolver_version"].startswith(
        "owner-rdf-registry-v1:"
    )
    assert result.reference_report["reference_outcomes"]
    assert all(
        row["source_sha256"] == expected
        and row["status"] in {"resolved", "unresolved", "malformed", "absent"}
        for row in result.reference_report["reference_outcomes"]
    )


def _assert_no_owner_descriptions(graph: Graph, *owners: URIRef) -> None:
    for owner in owners:
        assert not list(graph.triples((owner, None, None)))


def _integration_dataset(result, validated_owner_graphs) -> Dataset:
    dataset = Dataset()
    contexts = {
        URIRef(HOUSES_GRAPH): validated_owner_graphs["house_graph"],
        URIRef(COMMITTEES_GRAPH): validated_owner_graphs["committee_graph"],
        URIRef(member_graph_iri(validated_owner_graphs["member_source"]["member"])):
            validated_owner_graphs["member_graph"],
    }
    contexts[URIRef(result.graph_iri)] = result.graph
    for graph_iri, source_graph in contexts.items():
        target = dataset.graph(graph_iri)
        for triple in source_graph:
            target.add(triple)
    return dataset


def test_resolver_indexes_only_exact_typed_owner_identities(validated_owner_graphs):
    resolver = _resolver(validated_owner_graphs)

    assert resolver.resolve_member(MEMBER_HREF) == MEMBER_IRI
    assert resolver.resolve_member(str(MEMBER_IRI)) == MEMBER_IRI
    assert resolver.resolve_member("Timmy Dooley") is None
    assert resolver.resolve_house_term(DAIL_34_HREF) == DAIL_34_TERM
    assert resolver.house_for_term(str(DAIL_34_TERM)) == DAIL_HOUSE

    committee_record = validated_owner_graphs["committee_source"][0]
    committee_iri = URIRef(committee_record["uri"])
    exact_committee_href = "/ie/oireachtas/committee/dail/33/select_committee_on_finance"
    old_committee_href = "/ie/oireachtas/committee/select_committee_on_finance/33"
    assert resolver.resolve_committee(exact_committee_href) == committee_iri
    assert resolver.resolve_committee(old_committee_href) is None
    assert resolver.resolve_committee("Select Committee on Finance") is None

    # Resolver identity is deterministic over the exact owner lookup contents.
    rebuilt = _resolver(validated_owner_graphs)
    assert rebuilt.version == resolver.version


def test_resolver_fails_closed_on_invalid_owner_identity_graphs(validated_owner_graphs):
    member_graph = Graph()
    for triple in validated_owner_graphs["member_graph"]:
        member_graph.add(triple)
    member_graph.remove((MEMBER_IRI, OIR.memberCode, None))
    member_graph.add((MEMBER_IRI, OIR.memberCode, Literal("different", datatype=XSD.string)))

    with pytest.raises(ValueError, match="memberCode"):
        build_debate_reference_resolver(
            member_graph=member_graph,
            house_graph=validated_owner_graphs["house_graph"],
            committee_graph=validated_owner_graphs["committee_graph"],
        )

    # A structurally Committee-shaped graph using the obsolete URI form is not
    # accepted as an owner identity. It cannot be indexed just because it has
    # Committee typing and a HouseTerm edge.
    obsolete_iri = URIRef("https://data.oireachtas.ie" + OLD_COMMITTEE_HREF)
    invalid_committee_graph = Graph()
    invalid_committee_graph.add((obsolete_iri, RDF.type, MEMBERS.Committee))
    invalid_committee_graph.add((
        obsolete_iri,
        MEMBERS.committeeInHouseTerm,
        URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34"),
    ))
    with pytest.raises(ValueError, match="approved source IRI"):
        build_debate_reference_resolver(
            member_graph=validated_owner_graphs["member_graph"],
            house_graph=validated_owner_graphs["house_graph"],
            committee_graph=invalid_committee_graph,
        )


@pytest.mark.parametrize(
    "bad_iri",
    [
        str(MEMBER_IRI) + "/",
        str(MEMBER_IRI).replace("/member/id/", "/member//id/"),
    ],
    ids=["trailing-slash", "double-slash"],
)
def test_member_owner_uri_path_is_not_normalized(bad_iri, validated_owner_graphs):
    bad_subject = URIRef(bad_iri)
    bad_graph = Graph()
    for subject, predicate, obj in validated_owner_graphs["member_graph"]:
        if subject == MEMBER_IRI:
            subject = bad_subject
        if obj == MEMBER_IRI:
            obj = bad_subject
        bad_graph.add((subject, predicate, obj))

    with pytest.raises(ValueError, match="Member owner IRI does not match"):
        build_debate_reference_resolver(
            member_graph=bad_graph,
            house_graph=validated_owner_graphs["house_graph"],
            committee_graph=validated_owner_graphs["committee_graph"],
        )


def test_member_and_house_links_come_from_owner_graphs_without_description_leaks(
    validated_owner_graphs,
):
    source = (DEBATES_DIR / "dail_2026-02-26.akn.xml").read_bytes()
    resolver = _resolver(validated_owner_graphs)
    result = transform_debate(source, resolver=resolver)
    work = URIRef(result.work_iri)

    assert set(result.graph.objects(None, OIR.votedFor)) | set(
        result.graph.objects(None, OIR.votedAgainst)
    ) == {MEMBER_IRI}
    assert (work, OIR.recordOfHouseTerm, DAIL_34_TERM) in result.graph
    assert (work, OIR.recordOfBody, DAIL_HOUSE) in result.graph

    member_rows = [
        row for row in result.reference_report["reference_outcomes"]
        if row["raw_reference"] == "#TimDooley"
        and row["slot"].startswith("division/")
    ]
    assert member_rows and all(row["status"] == "resolved" for row in member_rows)
    assert {row["target_iri"] for row in member_rows} == {str(MEMBER_IRI)}
    term_rows = _rows(result, "FRBRWork/FRBRauthor/@href->recordOfHouseTerm")
    assert len(term_rows) == 1
    assert term_rows[0]["status"] == "resolved"
    assert term_rows[0]["target_iri"] == str(DAIL_34_TERM)
    body_rows = _rows(result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(body_rows) == 1
    assert body_rows[0]["status"] == "resolved"
    assert body_rows[0]["target_iri"] == str(DAIL_HOUSE)

    _assert_hash_linked_report(result, source)
    _assert_no_owner_descriptions(result.graph, MEMBER_IRI, DAIL_34_TERM, DAIL_HOUSE)
    assert (MEMBER_IRI, RDF.type, OIR.Member) in validated_owner_graphs["member_graph"]
    assert (DAIL_34_TERM, RDF.type, OIR.DailTerm) in validated_owner_graphs["house_graph"]
    assert (DAIL_HOUSE, RDF.type, OIR.House) in validated_owner_graphs["house_graph"]


def test_exact_committee_author_resolves_but_old_uri_form_does_not(
    validated_owner_graphs,
):
    # The target is independently present in the checked-in, source-validated
    # Dáil 33 Committee owner fixture. Never construct an owner from the AKN
    # reference being tested.
    resolver = _resolver(validated_owner_graphs)

    assert resolver.resolve_committee(COMMITTEE_HREF) == COMMITTEE_IRI
    assert resolver.resolve_committee(OLD_COMMITTEE_HREF) is None

    # Test-local AKN source uses the exact href already in the checked-in owner
    # graph, with a Member reference resolved from its independently validated
    # owner graph. This gives the integration validator positive joins for both
    # cross-dataset owner types.
    references = f'<references><TLCPerson eId="known" href="{MEMBER_HREF}"/></references>'
    body = '<debateSection eId="section"><speech eId="speech" by="#known"/></debateSection>'
    source = _minimal_source(
        author_href=COMMITTEE_HREF,
        references=references,
        body=body,
    )
    result = transform_debate(source, resolver=resolver)
    work = URIRef(result.work_iri)
    assert set(result.graph.objects(work, OIR.recordOfBody)) == {COMMITTEE_IRI}
    assert set(result.graph.objects(None, OIR.speaker)) == {MEMBER_IRI}
    body_rows = _rows(result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(body_rows) == 1
    assert body_rows[0]["status"] == "resolved"
    assert body_rows[0]["target_iri"] == str(COMMITTEE_IRI)
    assert body_rows[0]["resolution_evidence"]["resolution_method"] == (
        "exact-official-Committee-author-href"
    )
    term_rows = _rows(result, "FRBRWork/FRBRauthor/@href->recordOfHouseTerm")
    assert len(term_rows) == 1 and term_rows[0]["status"] == "unresolved"
    _assert_hash_linked_report(result, source)
    _assert_no_owner_descriptions(result.graph, COMMITTEE_IRI)
    assert (COMMITTEE_IRI, RDF.type, MEMBERS.Committee) in validated_owner_graphs["committee_graph"]
    validate_debates_integration(result, _integration_dataset(result, validated_owner_graphs))

    # The former /committee/{slug}/{term-no} spelling is not an alias for the
    # exact Committee owner IRI, even if its slug and term resemble the owner.
    old_source = _minimal_source(author_href=OLD_COMMITTEE_HREF)
    old_result = transform_debate(old_source, resolver=resolver)
    old_work = URIRef(old_result.work_iri)
    assert not list(old_result.graph.objects(old_work, OIR.recordOfBody))
    old_body_rows = _rows(old_result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(old_body_rows) == 1
    assert old_body_rows[0]["status"] == "unresolved"
    assert old_body_rows[0]["reason"] == "no-existing-Committee-owner-match"
    _assert_hash_linked_report(old_result, old_source)
    validate_debates_integration(
        old_result, _integration_dataset(old_result, validated_owner_graphs)
    )

    # The preserved Dáil 34 Public Accounts source is not inferred from its
    # author URI: it remains unresolved because that exact owner is absent from
    # the checked-in, validated Dáil 33 owner graph.
    original_committee_source = (
        DEBATES_DIR / "committee_public_accounts_2026-09-24.akn.xml"
    ).read_bytes()
    original_result = transform_debate(original_committee_source, resolver=resolver)
    original_work = URIRef(original_result.work_iri)
    assert not list(original_result.graph.objects(original_work, OIR.recordOfBody))
    original_body_rows = _rows(
        original_result, "FRBRWork/FRBRauthor/@href->recordOfBody"
    )
    assert len(original_body_rows) == 1
    assert original_body_rows[0]["status"] == "unresolved"
    assert "target_iri" not in original_body_rows[0]
    _assert_hash_linked_report(original_result, original_committee_source)
    validate_debates_integration(
        original_result,
        _integration_dataset(original_result, validated_owner_graphs),
    )


def _minimal_source(*, author_href: str, references: str = "", body: str = "") -> bytes:
    work_path = "/akn/ie/debateRecord/dail/2026-01-01/debate"
    expression_path = work_path + "/eng@"
    xml = (
        f'<akomaNtoso xmlns="{AKN}"><debate><meta><identification>'
        f"<FRBRWork><FRBRuri value=\"{work_path}\"/>"
        '<FRBRdate name="#generation" date="2026-01-01"/>'
        '<FRBRname value="debate"/>'
        f'<FRBRauthor href="{author_href}"/></FRBRWork>'
        f'<FRBRExpression><FRBRuri value="{expression_path}"/>'
        '<FRBRlanguage language="eng"/></FRBRExpression>'
        f"</identification></meta>{references}<debateBody>{body}</debateBody>"
        "</debate></akomaNtoso>"
    )
    return xml.encode("utf-8")


def test_reference_report_outcomes_match_emitted_links(validated_owner_graphs):
    resolver = _resolver(validated_owner_graphs)
    references = (
        "<references>"
        f'<TLCPerson eId="known" href="{MEMBER_HREF}"/>'
        '<TLCPerson eId="unowned" href="/ie/oireachtas/member/id/Unknown.Member"/>'
        "</references>"
    )
    body = (
        '<debateSection eId="section">'
        '<speech eId="resolved" by="#known"/>'
        '<speech eId="unresolved" by="#unowned"/>'
        '<speech eId="malformed" by="not-a-fragment"/>'
        '<speech eId="absent"/>'
        "</debateSection>"
    )
    source = _minimal_source(
        author_href="#oireachtas", references=references, body=body
    )
    result = transform_debate(source, resolver=resolver)
    rows = _rows(result, "speech/@by")
    by_status = {row["source_node_iri"]: row["status"] for row in rows}

    assert set(by_status.values()) == {"resolved", "unresolved", "malformed", "absent"}
    for row in rows:
        speech = URIRef(row["source_node_iri"])
        speakers = set(result.graph.objects(speech, OIR.speaker))
        if row["status"] == "resolved":
            assert speakers == {MEMBER_IRI}
            participation = set(result.graph.objects(speech, OIR.hasSpeechParticipation))
            assert len(participation) == 1
            assert (next(iter(participation)),
                    URIRef("http://data.europa.eu/eli/eli-draft-legislation-ontology#had_participant_person"),
                    MEMBER_IRI) in result.graph
        else:
            assert speakers == set()
            assert not list(result.graph.objects(speech, OIR.hasSpeechParticipation))

    assert (URIRef(result.work_iri), OIR.recordOfBody, DAIL_HOUSE) in result.graph
    _assert_hash_linked_report(result, source)
    _assert_no_owner_descriptions(result.graph, MEMBER_IRI, DAIL_HOUSE)
