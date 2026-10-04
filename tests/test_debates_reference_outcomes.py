"""Executable acceptance for Debates reference outcomes and owner links.

These tests exercise the public transformation API against the immutable AKN
fixtures and the checked-in Member/Houses owner examples. Expected owner IRIs
come from those owner examples, not from the Debates transformer output.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

import pytest
from rdflib import URIRef
from rdflib.namespace import RDF

from oireachtas_etl.transforms.common import ELIDL, MEMBERS, OIR
from oireachtas_etl.transforms.debates import (
    DebateReferenceRegistry,
    DebateTransformError,
    transform_debate,
)
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import transform_member


ROOT = Path(__file__).resolve().parents[1]
DEBATES_DIR = ROOT / "data" / "debates_examples"
AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
NS = {"akn": AKN}

FIXTURE_HASHES = {
    "dail_2015-07-02.akn.xml": "0ca15d12a7154c460f7459090b2838f25f5a63ef85017a2cce474ddc5f1731c6",
    "dail_2026-02-26.akn.xml": "1e6762bae013b22c37a4167f630530189bbf8f7057214b0676e699d97ed946ad",
    "seanad_2015-07-02.akn.xml": "6e2920af4b97aa0f692162f9fcd94324a18a1c26495399e8600a5ca450d762c0",
    "committee_public_accounts_2026-09-24.akn.xml": "690dada15afa1cb76ece7dd8387b973b00b43804023521b9ffb821d8944ff60e",
    "dail_written_answers_2015-07-02.akn.xml": "0d0a1d49c67772a073cf762017efc56f3e8cab93a47629091b8e10c3fc2c4cab",
}

REFERENCE_CONTRACT = "debates-reference-outcomes-v1"
MEMBER_SOURCE_HREF = "/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
DAIL_34_AUTHOR_HREF = "/ie/oireachtas/house/dail/34"
DAIL_34_TERM = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/34")
DAIL_HOUSE = URIRef("https://data.oireachtas.ie/house/dail")
SEANAD_HOUSE = URIRef("https://data.oireachtas.ie/house/seanad")


@pytest.fixture(scope="module")
def owner_examples():
    member_source = json.loads(
        (ROOT / "data" / "api_examples" / "member.json").read_text(
            encoding="utf-8"
        )
    )
    houses_source = json.loads(
        (ROOT / "data" / "api_examples" / "houses.json").read_text(
            encoding="utf-8"
        )
    )
    member_graph = transform_member(member_source)
    house_graph = transform_houses(houses_source)

    member_iri = URIRef(member_source["member"]["uri"])
    assert (member_iri, RDF.type, OIR.Member) in member_graph
    assert member_source["member"]["pId"] == "TimDooley"

    # The exact AKN author href matches the source HouseTerm IRI. The House is
    # obtained from the checked-in House owner graph's :termOf assertion, not
    # inferred from the HouseTerm IRI spelling.
    term_of_houses = set(house_graph.objects(DAIL_34_TERM, OIR.termOf))
    assert (DAIL_34_TERM, RDF.type, OIR.DailTerm) in house_graph
    assert len(term_of_houses) == 1
    dail_house = next(iter(term_of_houses))
    assert dail_house == DAIL_HOUSE
    assert (dail_house, RDF.type, OIR.House) in house_graph
    assert (SEANAD_HOUSE, RDF.type, OIR.House) in house_graph

    return {
        "member_graph": member_graph,
        "member_iri": member_iri,
        "house_graph": house_graph,
        "dail_34_term": DAIL_34_TERM,
        "dail_house": dail_house,
        "seanad_house": SEANAD_HOUSE,
    }


def _checked_in_owner_resolver(owner_examples, *, house_for_dail_34=None):
    term_house = (
        owner_examples["dail_house"]
        if house_for_dail_34 is None
        else house_for_dail_34
    )
    return DebateReferenceRegistry(
        members_by_tlc_href={MEMBER_SOURCE_HREF: owner_examples["member_iri"]},
        house_terms_by_author_href={
            DAIL_34_AUTHOR_HREF: owner_examples["dail_34_term"]
        },
        houses_by_term_iri={str(owner_examples["dail_34_term"]): term_house},
        version="checked-in-member-and-houses-examples-v1",
    )


def _fixture(filename: str) -> bytes:
    return (DEBATES_DIR / filename).read_bytes()


def _report_rows(result, slot: str | None = None) -> list[dict]:
    rows = result.reference_report["reference_outcomes"]
    if slot is None:
        return rows
    return [row for row in rows if row["slot"] == slot]


def _assert_fixture_report(result, filename: str) -> None:
    expected_hash = FIXTURE_HASHES[filename]
    assert result.source_sha256 == expected_hash
    assert result.reference_report["contract_version"] == REFERENCE_CONTRACT
    assert result.reference_report["source_sha256"] == expected_hash
    assert _report_rows(result)
    for row in _report_rows(result):
        assert row["contract_version"] == REFERENCE_CONTRACT
        assert row["source_sha256"] == expected_hash
        assert row["status"] in {"resolved", "unresolved", "malformed", "absent"}


def _assert_no_owner_descriptions(graph, *owner_iris: URIRef) -> None:
    for owner in owner_iris:
        assert not list(graph.triples((owner, None, None)))


def _minimal_source(
    body_xml: str,
    *,
    author_href: str = "#oireachtas",
    work_path: str = "/akn/ie/debateRecord/dail/2026-01-01/debate",
    expression_suffix: str = "mul@",
) -> bytes:
    """Build a tiny in-memory AKN source for fail-closed edge cases."""

    expression_path = work_path + "/" + expression_suffix
    source = (
        f'<akomaNtoso xmlns={quoteattr(AKN)}><debate><meta><identification>'
        f"<FRBRWork><FRBRuri value={quoteattr(work_path)}/>"
        '<FRBRdate name="#generation" date="2026-01-01"/>'
        '<FRBRname value="debate"/>'
        f"<FRBRauthor href={quoteattr(author_href)}/></FRBRWork>"
        f"<FRBRExpression><FRBRuri value={quoteattr(expression_path)}/>"
        '<FRBRlanguage language="eng"/></FRBRExpression>'
        f"</identification></meta><debateBody>{body_xml}</debateBody>"
        "</debate></akomaNtoso>"
    )
    return source.encode("utf-8")


def test_dail_2026_links_only_to_existing_member_and_houseterm_owner_resources(
    owner_examples,
):
    filename = "dail_2026-02-26.akn.xml"
    source = _fixture(filename)
    result = transform_debate(
        source, resolver=_checked_in_owner_resolver(owner_examples)
    )
    graph = result.graph
    work = URIRef(result.work_iri)
    member = owner_examples["member_iri"]
    house_term = owner_examples["dail_34_term"]
    house = owner_examples["dail_house"]

    # TLCPerson/@href in the AKN source is resolved by its exact parsed source
    # identity to the actual Member subject emitted from data/api_examples/member.json.
    # Tim Dooley appears as an individual vote in this fixture, not as a speaker.
    assert set(graph.objects(None, OIR.votedFor)) | set(
        graph.objects(None, OIR.votedAgainst)
    ) == {member}
    assert (work, OIR.recordOfHouseTerm, house_term) in graph
    assert (work, OIR.recordOfBody, house) in graph
    assert (work, OIR.inHouse, house) not in graph

    member_rows = [
        row for row in _report_rows(result)
        if row["raw_reference"] == "#TimDooley"
        and row["slot"].startswith("division/")
    ]
    assert member_rows
    assert all(row["status"] == "resolved" for row in member_rows)
    assert {row["target_iri"] for row in member_rows} == {str(member)}
    term_rows = _report_rows(result, "FRBRWork/FRBRauthor/@href->recordOfHouseTerm")
    assert len(term_rows) == 1
    assert term_rows[0]["status"] == "resolved"
    assert term_rows[0]["target_iri"] == str(house_term)
    body_rows = _report_rows(result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(body_rows) == 1
    assert body_rows[0]["status"] == "resolved"
    assert body_rows[0]["target_iri"] == str(house)

    _assert_fixture_report(result, filename)
    _assert_no_owner_descriptions(graph, member, house_term, house)
    # Owner descriptions are present in their checked-in owning graph, but the
    # Debates graph contains only the approved reference links to those IRIs.
    assert (member, RDF.type, OIR.Member) in owner_examples["member_graph"]
    assert (house_term, RDF.type, OIR.DailTerm) in owner_examples["house_graph"]
    assert (house, RDF.type, OIR.House) in owner_examples["house_graph"]


def test_generic_dail_2015_work_uses_only_approved_existing_chamber_crosswalk(
    owner_examples,
):
    filename = "dail_2015-07-02.akn.xml"
    result = transform_debate(_fixture(filename), resolver=None)
    work = URIRef(result.work_iri)
    graph = result.graph
    house = owner_examples["dail_house"]

    assert (work, OIR.recordOfBody, house) in graph
    assert not list(graph.objects(work, OIR.recordOfHouseTerm))
    assert not list(graph.triples((work, OIR.inHouse, None)))
    body_rows = _report_rows(result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(body_rows) == 1
    assert body_rows[0]["status"] == "resolved"
    assert body_rows[0]["target_iri"] == str(house)
    assert body_rows[0]["resolution_evidence"]["resolution_method"] == (
        "approved-Work-venue-plus-generic-Oireachtas-author-crosswalk"
    )

    _assert_fixture_report(result, filename)
    _assert_no_owner_descriptions(graph, house)
    assert (house, RDF.type, OIR.House) in owner_examples["house_graph"]


@pytest.mark.parametrize(
    ("filename", "expected_owner_iri"),
    [
        (
            "seanad_2015-07-02.akn.xml",
            "https://data.oireachtas.ie/ie/oireachtas/house/seanad/24",
        ),
        (
            "dail_written_answers_2015-07-02.akn.xml",
            "https://data.oireachtas.ie/ie/oireachtas/house/dail/31",
        ),
        (
            "committee_public_accounts_2026-09-24.akn.xml",
            "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts",
        ),
    ],
)
def test_unknown_houseterm_and_committee_authors_do_not_create_hosts_or_descriptions(
    filename, expected_owner_iri
):
    result = transform_debate(_fixture(filename), resolver=None)
    graph = result.graph
    work = URIRef(result.work_iri)
    guessed_source_owner = URIRef(expected_owner_iri)

    assert not list(graph.objects(work, OIR.recordOfBody))
    assert not list(graph.objects(work, OIR.recordOfHouseTerm))
    assert not list(graph.triples((work, OIR.inHouse, None)))
    _assert_no_owner_descriptions(graph, guessed_source_owner)

    body_rows = _report_rows(result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(body_rows) == 1
    assert body_rows[0]["status"] == "unresolved"
    assert "target_iri" not in body_rows[0]
    if "committee" in filename:
        assert body_rows[0]["reason"] == "no-existing-Committee-owner-match"
    else:
        term_rows = _report_rows(
            result, "FRBRWork/FRBRauthor/@href->recordOfHouseTerm"
        )
        assert len(term_rows) == 1
        assert term_rows[0]["status"] == "unresolved"
        assert "target_iri" not in term_rows[0]

    _assert_fixture_report(result, filename)


def test_missing_member_owner_and_placeholder_references_are_audited_without_links():
    filename = "dail_2026-02-26.akn.xml"
    result = transform_debate(
        _fixture(filename), resolver=DebateReferenceRegistry(version="empty-owner-registry")
    )
    graph = result.graph
    missing_member_rows = [
        row for row in _report_rows(result)
        if row["raw_reference"] == "#TimDooley"
        and row["slot"].startswith("division/")
    ]
    assert missing_member_rows
    assert all(row["status"] == "unresolved" for row in missing_member_rows)
    assert all(
        row["reason"] == "no-existing-Member-owner-match"
        for row in missing_member_rows
    )
    assert not list(graph.triples((None, OIR.votedFor, None)))
    assert not list(graph.triples((None, OIR.votedAgainst, None)))
    assert not list(graph.triples((None, OIR.abstained, None)))

    committee_filename = "committee_public_accounts_2026-09-24.akn.xml"
    committee = transform_debate(_fixture(committee_filename), resolver=None)
    placeholders = [
        row
        for row in _report_rows(committee, "speech/@by")
        if row["raw_reference"] == "#"
    ]
    assert placeholders
    assert all(row["status"] == "unresolved" for row in placeholders)
    assert all(row["reason"] == "source-placeholder" for row in placeholders)
    assert not list(committee.graph.triples((None, OIR.speaker, None)))
    assert not list(committee.graph.triples((None, OIR.hasSpeechParticipation, None)))
    _assert_fixture_report(committee, committee_filename)
    _assert_fixture_report(result, filename)


def test_ambiguous_member_owner_candidates_are_sorted_and_never_linked():
    filename = "dail_2026-02-26.akn.xml"
    candidate_iris = [
        URIRef("https://data.oireachtas.ie/member/other-z"),
        URIRef("https://data.oireachtas.ie/member/other-a"),
    ]
    resolver = DebateReferenceRegistry(
        members_by_tlc_href={MEMBER_SOURCE_HREF: candidate_iris},
        version="ambiguous-test-registry",
    )
    result = transform_debate(_fixture(filename), resolver=resolver)
    rows = [
        row for row in _report_rows(result)
        if row["raw_reference"] == "#TimDooley"
        and row["slot"].startswith("division/")
    ]
    assert rows
    assert all(row["status"] == "unresolved" for row in rows)
    assert all(row["reason"] == "ambiguous-existing-owner-candidates" for row in rows)
    assert all(
        row["candidate_iris"] == sorted(map(str, candidate_iris)) for row in rows
    )
    assert not list(result.graph.triples((None, OIR.votedFor, None)))
    assert not list(result.graph.triples((None, OIR.votedAgainst, None)))
    assert not list(result.graph.triples((None, OIR.abstained, None)))
    _assert_no_owner_descriptions(result.graph, *candidate_iris)
    _assert_fixture_report(result, filename)


def test_house_term_to_house_conflict_keeps_only_resolved_term_link(owner_examples):
    filename = "dail_2026-02-26.akn.xml"
    resolver = _checked_in_owner_resolver(
        owner_examples, house_for_dail_34=owner_examples["seanad_house"]
    )
    result = transform_debate(_fixture(filename), resolver=resolver)
    work = URIRef(result.work_iri)
    graph = result.graph

    assert (work, OIR.recordOfHouseTerm, owner_examples["dail_34_term"]) in graph
    assert not list(graph.objects(work, OIR.recordOfBody))
    conflict_rows = _report_rows(result, "FRBRWork/FRBRauthor/@href->recordOfBody")
    assert len(conflict_rows) == 1
    assert conflict_rows[0]["status"] == "unresolved"
    assert conflict_rows[0]["reason"] == "Work-venue-and-HouseTerm-termOf-target-conflict"
    assert conflict_rows[0]["resolution_evidence"]["term_of_house_iri"] == str(
        owner_examples["seanad_house"]
    )
    assert conflict_rows[0]["resolution_evidence"]["expected_house_iri"] == str(
        owner_examples["dail_house"]
    )

    _assert_fixture_report(result, filename)
    _assert_no_owner_descriptions(
        graph,
        owner_examples["dail_34_term"],
        owner_examples["dail_house"],
        owner_examples["seanad_house"],
    )


def test_question_recipient_stays_deferred_and_does_not_touch_named_office_model(
    owner_examples,
):
    filename = "dail_2015-07-02.akn.xml"
    result = transform_debate(
        _fixture(filename), resolver=_checked_in_owner_resolver(owner_examples)
    )
    graph = result.graph
    recipient_rows = _report_rows(
        result, "question/@to->directedTo/directedToOffice"
    )
    source = ET.fromstring(_fixture(filename))
    questions = source.findall(".//akn:debateBody//akn:question[@to]", NS)
    assert questions and recipient_rows
    assert {row["raw_reference"] for row in recipient_rows} == {
        question.get("to") for question in questions
    }
    assert all(row["status"] == "unresolved" for row in recipient_rows)
    assert all(
        row["reason"] == "question-recipient-resolution-deferred"
        for row in recipient_rows
    )
    assert not list(graph.triples((None, OIR.directedTo, None)))
    assert not list(graph.triples((None, OIR.directedToOffice, None)))
    for owned_office_class in (
        MEMBERS.NamedOffice,
        MEMBERS.OfficeHolding,
        MEMBERS.CabinetMembership,
    ):
        assert not list(graph.triples((None, RDF.type, owned_office_class)))
    assert not any(
        str(subject).startswith("https://data.oireachtas.ie/office/")
        for subject in graph.subjects()
    )
    _assert_fixture_report(result, filename)


def test_declared_seanad_outcome_is_raw_hash_linked_evidence_but_not_an_rdf_outcome():
    filename = "seanad_2015-07-02.akn.xml"
    result = transform_debate(_fixture(filename), resolver=None)
    declared = [
        row
        for row in _report_rows(result, "analysis/voting/@outcome->divisionOutcome")
        if row["raw_reference"] == "#declared"
    ]
    assert len(declared) == 1
    assert declared[0]["status"] == "unresolved"
    assert declared[0]["reason"] == "unsupported-controlled-outcome"
    assert declared[0]["resolution_evidence"]["controlled_value"] == "#declared"
    division = URIRef(declared[0]["source_node_iri"])
    assert not list(result.graph.objects(division, OIR.divisionOutcome))
    _assert_fixture_report(result, filename)


def test_reference_report_is_deterministic_sorted_key_utf8_and_source_exact():
    # Non-ASCII raw source evidence checks UTF-8 serialization without creating
    # an RDF target for an unknown local eId.
    source = _minimal_source('<speech eId="s1" by="#dáil"/>')
    first = transform_debate(source, resolver=None)
    repeated = transform_debate(source, resolver=None)

    expected_hash = hashlib.sha256(source).hexdigest()
    assert first.source_sha256 == expected_hash
    assert first.reference_report["source_sha256"] == expected_hash
    assert first.reference_report_json == repeated.reference_report_json
    assert first.reference_report_json.decode("utf-8") == first.reference_report_text
    decoded = json.loads(first.reference_report_json.decode("utf-8"))
    assert first.reference_report_json == json.dumps(
        decoded, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert b"#d\xc3\xa1il" in first.reference_report_json
    assert b"\\u00e1" not in first.reference_report_json

    rows = _report_rows(first)
    assert rows
    assert all(row["source_sha256"] == expected_hash for row in rows)
    assert all(row["contract_version"] == REFERENCE_CONTRACT for row in rows)
    ordering = [
        (
            row["expression_iri"],
            row["source_node_iri"],
            row["source_attribute_qname"],
            "" if row["raw_reference"] is None else row["raw_reference"],
        )
        for row in rows
    ]
    assert ordering == sorted(ordering)
    by_reference = [row for row in rows if row["slot"] == "speech/@by"]
    assert len(by_reference) == 1
    assert by_reference[0]["raw_reference"] == "#dáil"
    assert by_reference[0]["status"] == "unresolved"
    assert by_reference[0]["reason"] == "unknown-local-eid"
    assert not list(first.graph.triples((None, OIR.speaker, None)))


def test_absent_placeholder_and_malformed_reference_slots_remain_distinct():
    source = _minimal_source(
        '<speech eId="placeholder" by="#"/><speech eId="bad" by="#?"/>'
    )
    result = transform_debate(source, resolver=None)
    by_rows = _report_rows(result, "speech/@by")
    assert {row["raw_reference"] for row in by_rows} == {"#", "#?"}
    statuses = {row["raw_reference"]: row for row in by_rows}
    assert statuses["#"]["status"] == "unresolved"
    assert statuses["#"]["reason"] == "source-placeholder"
    assert statuses["#?"]["status"] == "malformed"
    assert statuses["#?"]["reason"] == "not-a-reviewed-local-NCName-fragment"
    absent_role_rows = _report_rows(result, "speech/@as->eli-dl:participation_role")
    assert len(absent_role_rows) == 2
    assert all(row["status"] == "absent" for row in absent_role_rows)
    assert all(row["raw_reference"] is None for row in absent_role_rows)
    assert not list(result.graph.triples((None, OIR.speaker, None)))
    assert not list(result.graph.triples((None, OIR.hasSpeechParticipation, None)))


def test_known_multiple_expressions_fail_closed_for_the_work_with_exact_hash():
    source = _minimal_source('<debateSection eId="s1"/>')
    work_path = "/akn/ie/debateRecord/dail/2026-01-01/debate"
    expression_a = work_path + "/mul@"
    expression_b = work_path + "/eng@"

    with pytest.raises(DebateTransformError, match="multiple known Expressions") as caught:
        transform_debate(source, known_expression_source_uris=[expression_b])

    expected_hash = hashlib.sha256(source).hexdigest()
    assert caught.value.source_sha256 == expected_hash
    assert caught.value.reference_report["contract_version"] == REFERENCE_CONTRACT
    assert caught.value.reference_report["source_sha256"] == expected_hash
    assert caught.value.reference_report["diagnostics"][0]["code"] == (
        "known-multiple-expressions"
    )
    assert caught.value.reference_report["diagnostics"][0]["evidence"][
        "known_expression_iris"
    ] == sorted(
        [
            "https://data.oireachtas.ie" + expression_a.replace("@", "%40"),
            "https://data.oireachtas.ie" + expression_b.replace("@", "%40"),
        ]
    )


def test_duplicate_eids_and_identical_missing_eid_fallbacks_fail_closed():
    duplicate_eid_source = _minimal_source(
        '<speech eId="same"/><summary eId="same"/>'
    )
    with pytest.raises(DebateTransformError, match="duplicate decoded eId") as duplicate:
        transform_debate(duplicate_eid_source)
    assert duplicate.value.source_sha256 == hashlib.sha256(
        duplicate_eid_source
    ).hexdigest()
    assert duplicate.value.reference_report["diagnostics"][0]["code"] == "duplicate-eid"

    fallback_collision_source = _minimal_source(
        '<debateSection name="identical"/><debateSection name="identical"/>'
    )
    with pytest.raises(
        DebateTransformError, match="duplicate proposed Debate resource IRI"
    ) as fallback:
        transform_debate(fallback_collision_source)
    assert fallback.value.source_sha256 == hashlib.sha256(
        fallback_collision_source
    ).hexdigest()
    assert fallback.value.reference_report["diagnostics"][0]["code"] == (
        "duplicate-proposed-resource-iri"
    )
