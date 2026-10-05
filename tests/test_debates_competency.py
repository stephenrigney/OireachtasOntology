"""Parameterized public Debates SPARQL acceptance on joined owner graphs.

Query results are checked against fixed identifiers and independently inspected
AKN/owner inputs. Debate RDF always comes from the public transformer; no query
test uses transformer output to define its expected result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

import pytest
from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.competency import render_debate_competency_query
from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH, OFFICES_GRAPH
from oireachtas_etl.office_observations import extract_office_observations
from oireachtas_etl.office_reconciliation import OfficeOccurrenceStore
from oireachtas_etl.transforms.bills import bill_graph_iri, transform_bill_with_report
from oireachtas_etl.transforms.common import MEMBERS, OIR
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.debates import DebateReferenceRegistry, transform_debate
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import (
    member_graph_iri,
    transform_member_with_report,
)
from oireachtas_etl.transforms.offices import office_iri, transform_offices


ROOT = Path(__file__).resolve().parents[1]
DEBATE_DIR = ROOT / "data" / "debates_examples"
AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
NS = {"akn": AKN}

MEMBER_SOURCE_HREF = "/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
MEMBER = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
MEMBER_GRAPH = "https://data.oireachtas.ie/graph/member/Timmy-Dooley.S.2002-09-12"
DAIL_HOUSE = "https://data.oireachtas.ie/house/dail"
DAIL_34_TERM = "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
COMMITTEE_SOURCE_OWNER = (
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/"
    "committee_of_public_accounts"
)

OFFICE_SAMPLE_MEMBER = (
    "https://data.oireachtas.ie/ie/oireachtas/member/id/"
    "Micheál-Martin.D.1989-06-29"
)
OFFICE_SAMPLE_OCCURRENCE = (
    "occ-9862f2b2e99387a510d0c032f9d072d794408121d9135b9b132372ccc87c2aef"
)
OFFICE_SAMPLE_REVIEWED_RESPONSE_SHA256 = (
    "aa591dff3ae205238f5a2731e9922f6ec08f42721f159795b073d9e55918b60c"
)


def _accepted_office_member_source() -> dict:
    """Reconstruct the Member fields needed for the reviewed-owner query.

    This is not a raw API capture or a complete Member response. It contains
    only reconstructed identity/membership fields and the reviewed office
    observation, so the test can execute the owner transform/query offline.
    The checked-in review fingerprint and evidence are asserted separately;
    they provide provenance for the office observation, not for this
    reconstructed payload as a whole.
    """
    membership_contexts = [
        ("32", "2016-03-10", "2020-01-14"),
        ("31", "2011-03-09", "2016-03-09"),
        ("30", "2007-06-14", "2011-02-01"),
        ("29", "2002-06-06", "2007-04-30"),
        ("28", "1997-06-26", "2002-04-25"),
        ("27", "1992-12-14", "1997-05-15"),
        ("26", "1989-06-29", "1992-11-05"),
        ("33", "2020-02-08", "2024-11-08"),
        ("34", "2024-11-29", None),
    ]
    member_iri = OFFICE_SAMPLE_MEMBER
    memberships = []
    for number, start, end in membership_contexts:
        membership = {
            "uri": f"{member_iri}/house/dail/{number}",
            "dateRange": {"start": start, "end": end},
            "house": {
                "houseNo": number,
                "houseCode": "dail",
                "uri": f"https://data.oireachtas.ie/ie/oireachtas/house/dail/{number}",
            },
        }
        if number == "34":
            membership["offices"] = [{"office": {
                "dateRange": {"end": None, "start": "2025-01-23"},
                "officeName": {"uri": None, "showAs": "Taoiseach"},
            }}]
        memberships.append({"membership": membership})

    return {"member": {
        "memberCode": "Micheál-Martin.D.1989-06-29",
        "uri": member_iri,
        "image": False,
        "firstName": "Micheál",
        "lastName": "Martin",
        "fullName": "Micheál Martin",
        "showAs": "Micheál Martin",
        "memberships": memberships,
    }}

WORKS = {
    "dail_2015": {
        "file": "dail_2015-07-02.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/eng%40",
        "graph": "https://data.oireachtas.ie/graph/debate/dail/2015-07-02",
    },
    "dail_2026": {
        "file": "dail_2026-02-26.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-02-25/debate",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-02-25/debate/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/dail/2026-02-25/debate",
    },
    "seanad": {
        "file": "seanad_2015-07-02.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/seanad/2015-07-02/debate",
    },
    "committee": {
        "file": "committee_public_accounts_2026-09-24.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/committee_of_public_accounts/2026-09-24/debate",
    },
    "written": {
        "file": "dail_written_answers_2015-07-02.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/dail/2015-07-02/writtens",
    },
}


def _add_graph(dataset: Dataset, graph_iri: str, source_graph) -> None:
    target = dataset.graph(URIRef(graph_iri))
    for triple in source_graph:
        target.add(triple)


def _member_resolver() -> DebateReferenceRegistry:
    return DebateReferenceRegistry(
        members_by_tlc_href={MEMBER_SOURCE_HREF: URIRef(MEMBER)},
        house_terms_by_author_href={
            "/ie/oireachtas/house/dail/34": URIRef(DAIL_34_TERM)
        },
        houses_by_term_iri={DAIL_34_TERM: URIRef(DAIL_HOUSE)},
        version="competency-fixture-owner-graphs-v1",
    )


def _question_source() -> bytes:
    """A small AKN case that exercises already-approved Member resolution.

    The question's TLCRole remains intentionally unresolved; supplying an
    existing Member resolver is not a recipient/office crosswalk.
    """
    return (
        f'<akomaNtoso xmlns={quoteattr(AKN)}><debate><meta><identification>'
        '<FRBRWork><FRBRuri value="/akn/ie/debateRecord/dail/2026-01-01/debate"/>'
        '<FRBRdate name="#generation" date="2026-01-01"/>'
        '<FRBRname value="debate"/><FRBRauthor href="#oireachtas"/></FRBRWork>'
        '<FRBRExpression><FRBRuri value="/akn/ie/debateRecord/dail/2026-01-01/debate/mul@"/>'
        '<FRBRlanguage language="eng"/></FRBRExpression>'
        '</identification></meta><references>'
        f'<TLCPerson eId="TimDooley" href={quoteattr(MEMBER_SOURCE_HREF)} showAs="Timmy Dooley"/>'
        '<TLCRole eId="minister" href="/ie/oireachtas/role/dail/minister" showAs="Minister"/>'
        '</references><debateBody><debateSection eId="section">'
        '<speech by="#TimDooley" eId="speech"/>'
        '<question by="#TimDooley" to="#minister" eId="question"/>'
        '</debateSection></debateBody></debate></akomaNtoso>'
    ).encode("utf-8")


@pytest.fixture(scope="module")
def joined_dataset():
    """Build disposable named graphs from the checked-in owner/source records."""
    dataset = Dataset()

    member_source = json.loads((ROOT / "data/api_examples/member.json").read_text())
    member_graph, member_report = transform_member_with_report(member_source)
    member_iri = URIRef(member_source["member"]["uri"])
    member_graph_name = member_graph_iri(member_source["member"])
    _add_graph(dataset, member_graph_name, member_graph)

    houses_source = json.loads((ROOT / "data/api_examples/houses.json").read_text())
    houses_graph = transform_houses(houses_source)
    _add_graph(dataset, HOUSES_GRAPH, houses_graph)

    committee_source = json.loads(
        (ROOT / "tests/fixtures/committee-owner.json").read_text()
    )
    committee_graph = transform_committees(committee_source)
    _add_graph(dataset, COMMITTEES_GRAPH, committee_graph)

    office_registry = json.loads(
        (ROOT / "registries/ministerial-office-registry.json").read_text()
    )
    offices_graph = transform_offices(office_registry)
    _add_graph(dataset, OFFICES_GRAPH, offices_graph)

    bill_source = json.loads((ROOT / "data/api_examples/bill.json").read_text())[
        "results"
    ][0]
    bill_graph, _bill_report = transform_bill_with_report(bill_source)
    bill_graph_name = bill_graph_iri(bill_source["bill"])
    _add_graph(dataset, bill_graph_name, bill_graph)

    debate_results = {}
    for key, case in WORKS.items():
        source = (DEBATE_DIR / case["file"]).read_bytes()
        resolver = _member_resolver() if key == "dail_2026" else None
        result = transform_debate(source, resolver=resolver)
        assert result.work_iri == case["work"]
        assert result.expression_iri == case["expression"]
        assert result.graph_iri == case["graph"]
        _add_graph(dataset, case["graph"], result.graph)
        debate_results[key] = result

    # This in-memory AKN probe is transformed with the actual Member owner
    # graph. It tests a positive question/speech Member reference without
    # changing any preserved source fixture or recipient semantics.
    question_result = transform_debate(
        _question_source(), resolver=_member_resolver()
    )
    _add_graph(dataset, question_result.graph_iri, question_result.graph)

    return {
        "dataset": dataset,
        "member_graph": member_graph,
        "member_graph_name": member_graph_name,
        "member_iri": member_iri,
        "member_report": member_report,
        "houses_graph": houses_graph,
        "committee_graph": committee_graph,
        "offices_graph": offices_graph,
        "bill_graph": bill_graph,
        "bill_graph_name": bill_graph_name,
        "bill_iri": str(bill_source["bill"]["uri"]),
        "debates": debate_results,
        "question_result": question_result,
    }


def _rows(dataset: Dataset, filename: str, **parameters: str) -> list[dict[str, str]]:
    query = render_debate_competency_query(filename, parameters)
    return [
        {str(name): str(value) for name, value in row.asdict().items()}
        for row in dataset.query(query)
    ]


@pytest.mark.parametrize(
    ("record_key", "date", "expected_sitting"),
    [
        (
            "dail_2015",
            "2015-07-02T00:00:00",
            WORKS["dail_2015"]["work"] + "#sitting",
        ),
        (
            "dail_2026",
            "2026-02-25T00:00:00",
            WORKS["dail_2026"]["work"] + "#sitting",
        ),
    ],
)
def test_house_date_query_returns_owner_resolved_records_and_sittings(
    joined_dataset, record_key, date, expected_sitting
):
    case = WORKS[record_key]
    actual = _rows(
        joined_dataset["dataset"],
        "debate-records-by-body-date.rq",
        body=DAIL_HOUSE,
        body_graph=HOUSES_GRAPH,
        body_type=str(OIR.House),
        date=date,
    )
    assert actual == [
        {
            "record": case["work"],
            "sitting": expected_sitting,
            "recordDate": date,
            "sittingDate": date[:10],
            "graph": case["graph"],
        }
    ]


def test_written_work_query_keeps_record_date_but_no_body_or_sitting(joined_dataset):
    case = WORKS["written"]
    actual = _rows(
        joined_dataset["dataset"],
        "debate-record-sittings.rq",
        record=case["work"],
    )
    assert actual == [
        {
            "record": case["work"],
            "recordDate": "2015-07-02T00:00:00",
            "graph": case["graph"],
        }
    ]
    # The source names a Dáil HouseTerm that is not present in the checked-in
    # House owner graph; do not infer a host from the path or date.
    assert not list(joined_dataset["debates"]["written"].graph.objects(
        URIRef(case["work"]), OIR.recordOfBody
    ))


def test_committee_date_query_requires_the_exact_existing_committee_owner(joined_dataset):
    # The AKN author is the Public Accounts Committee in Dáil 34. The supplied
    # owner fixture is a different Finance Committee in Dáil 33, so there is
    # no authoritative identity match and no debate host link.
    source = ET.fromstring(
        (DEBATE_DIR / WORKS["committee"]["file"]).read_bytes()
    )
    author = source.find(".//akn:FRBRWork/akn:FRBRauthor", NS)
    assert author is not None
    assert "https://data.oireachtas.ie" + author.get("href", "") == COMMITTEE_SOURCE_OWNER
    actual = _rows(
        joined_dataset["dataset"],
        "debate-records-by-body-date.rq",
        body=COMMITTEE_SOURCE_OWNER,
        body_graph=COMMITTEES_GRAPH,
        body_type=str(MEMBERS.Committee),
        date="2026-09-24T00:00:00",
    )
    assert actual == []
    assert not list(joined_dataset["debates"]["committee"].graph.objects(
        URIRef(WORKS["committee"]["work"]), OIR.recordOfBody
    ))


def test_expression_and_nested_section_components_are_ordered_from_source_ordinals(
    joined_dataset,
):
    case = WORKS["written"]
    source_root = ET.fromstring((DEBATE_DIR / case["file"]).read_bytes())
    body = source_root.find(".//akn:debateBody", NS)
    assert body is not None
    expression_rows = _rows(
        joined_dataset["dataset"],
        "debate-ordered-components.rq",
        record=case["work"],
        container=case["expression"],
    )
    expected_roots = [
        {
            "container": case["expression"],
            "component": f'{case["expression"]}/eid/e-{section.get("eId")}',
            "ordinal": str(index),
        }
        for index, section in enumerate(body.findall("akn:debateSection", NS), 1)
    ]
    assert len(expected_roots) == 20
    assert expression_rows == expected_roots

    # Independently pinned AKN sequence: two questions precede their response
    # speech under this writtenAnswer DebateSection (no guessed one-to-one link).
    section = f'{case["expression"]}/eid/e-dbsect_83'
    actual = _rows(
        joined_dataset["dataset"],
        "debate-ordered-components.rq",
        record=case["work"],
        container=section,
    )
    assert actual == [
        {"container": section, "component": f'{case["expression"]}/eid/e-pq_38', "ordinal": "1"},
        {"container": section, "component": f'{case["expression"]}/eid/e-pq_57', "ordinal": "2"},
        {"container": section, "component": f'{case["expression"]}/eid/e-spk_1033', "ordinal": "3"},
    ]


def test_member_query_finds_question_and_speech_contributions_without_member_redescription(
    joined_dataset,
):
    expression = "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-01-01/debate/mul%40"
    actual = _rows(
        joined_dataset["dataset"],
        "debate-member-contributions.rq",
        member=MEMBER,
        member_graph=joined_dataset["member_graph_name"],
    )
    assert actual == [
        {"member": MEMBER, "contribution": f"{expression}/eid/e-question", "kind": "question"},
        {"member": MEMBER, "contribution": f"{expression}/eid/e-speech", "kind": "speech"},
    ]
    # The owner describes the Member in its own graph; the Debate graph only
    # references that IRI through approved contribution predicates.
    question_graph = joined_dataset["question_result"].graph
    assert not list(question_graph.triples((URIRef(MEMBER), None, None)))


def test_question_query_keeps_deferred_recipient_absent_and_does_not_guess_office(
    joined_dataset,
):
    question = "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-01-01/debate/mul%40/eid/e-question"
    result = joined_dataset["question_result"]
    actual = _rows(
        joined_dataset["dataset"],
        "debate-question-recipients.rq",
        member=MEMBER,
        member_graph=joined_dataset["member_graph_name"],
    )
    assert actual == [{"question": question, "member": MEMBER}]

    recipient_rows = [
        row for row in result.reference_report["reference_outcomes"]
        if row["slot"] == "question/@to->directedTo/directedToOffice"
    ]
    assert len(recipient_rows) == 1
    assert recipient_rows[0]["raw_reference"] == "#minister"
    assert recipient_rows[0]["status"] == "unresolved"
    assert recipient_rows[0]["reason"] == "question-recipient-resolution-deferred"
    assert not list(result.graph.triples((URIRef(question), OIR.directedTo, None)))
    assert not list(result.graph.triples((URIRef(question), OIR.directedToOffice, None)))
    assert not list(result.graph.subjects(RDF.type, MEMBERS.NamedOffice))


def test_member_office_boundary_uses_owner_holding_and_registry_graphs_only(joined_dataset):
    # The named-office registry contains three genuine enduring identities,
    # but this checked-in Member source has two unresolved Minister-of-State
    # observations and no accepted OfficeHolding. Keep those facts separate
    # from question recipient semantics.
    registered_offices = set(
        joined_dataset["offices_graph"].subjects(RDF.type, MEMBERS.NamedOffice)
    )
    assert registered_offices == {
        URIRef("https://data.oireachtas.ie/office/o-000001"),
        URIRef("https://data.oireachtas.ie/office/o-000002"),
        URIRef("https://data.oireachtas.ie/office/o-000003"),
    }
    assert not list(joined_dataset["member_graph"].subjects(RDF.type, MEMBERS.OfficeHolding))
    pending = [
        row for row in joined_dataset["member_report"]
        if row["category"] == "reconciliation_pending"
    ]
    assert len(pending) == 2

    actual = _rows(
        joined_dataset["dataset"],
        "debate-owner-office-holdings.rq",
        member=MEMBER,
        member_graph=joined_dataset["member_graph_name"],
        office_graph=OFFICES_GRAPH,
    )
    assert actual == []


def test_ministerial_office_query_returns_reviewed_official_owner_holding(
    joined_dataset,
):
    from oireachtas_etl.cli import _resolution_records

    source = _accepted_office_member_source()
    reconstructed_bytes = json.dumps(
        source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    source_pointer = {
        # Logical, test-local provenance only; neither this path nor its hash
        # claims to identify the official response bytes.
        "path": "test-reconstruction/office-owner-member.json",
        "sha256": hashlib.sha256(reconstructed_bytes).hexdigest(),
        "json_pointer": "",
    }
    assert source_pointer["sha256"] != OFFICE_SAMPLE_REVIEWED_RESPONSE_SHA256
    observations = extract_office_observations([(source, source_pointer)])
    assert len(observations) == 1
    assert observations[0]["raw_pointers"] == [{
        **source_pointer,
        "json_pointer": (
            "/member/memberships/8/membership/offices/0/office"
        ),
    }]

    decision_bytes = (ROOT / "reconciliation/office-decisions.json").read_bytes()
    decisions = json.loads(decision_bytes)["decisions"]
    decision = decisions[OFFICE_SAMPLE_OCCURRENCE]
    assert decision["status"] == "accepted"
    assert decision["office_iris"] == ["https://data.oireachtas.ie/office/o-000001"]
    assert observations[0]["fingerprint"] == decision["observation_fingerprint"]
    assert decision["evidence"][0] == (
        "https://api.oireachtas.ie/v1/members?skip=1100&limit=100 "
        "(retrieved 2026-10-02; response SHA-256 "
        f"{OFFICE_SAMPLE_REVIEWED_RESPONSE_SHA256}; JSON pointer "
        "/results/98/member/memberships/8/membership/offices/0/office)"
    )

    office_registry = json.loads(
        (ROOT / "registries/ministerial-office-registry.json").read_text()
    )
    with OfficeOccurrenceStore(":memory:") as store:
        reconciled = store.reconcile(
            observations,
            office_registry,
            decisions,
            hashlib.sha256(decision_bytes).hexdigest(),
            run_id="debate-competency-reviewed-office-owner",
        )
    accepted = next(
        row for row in reconciled["records"]
        if row.get("member_iri") == OFFICE_SAMPLE_MEMBER
    )
    assert accepted["occurrence_key"] == OFFICE_SAMPLE_OCCURRENCE
    assert accepted["status"] == "accepted"
    assert accepted["current_fingerprint"] == decision["observation_fingerprint"]
    assert accepted["last_accepted_resolution"]["decision"] == decision

    office_resolutions = _resolution_records(
        accepted["occurrence_key"],
        accepted["last_accepted_resolution"],
        retained=False,
    )
    office_types = {
        str(office_iri(office["key"])): office["office_type"]
        for office in office_registry["offices"]
    }
    member_graph, _report = transform_member_with_report(
        source,
        office_resolutions=office_resolutions,
        office_types=office_types,
    )
    member_graph_name = member_graph_iri(source["member"])
    owner_dataset = Dataset()
    source_dataset = joined_dataset["dataset"]
    for graph in source_dataset.graphs():
        if graph.identifier != source_dataset.default_graph.identifier:
            _add_graph(owner_dataset, str(graph.identifier), graph)
    _add_graph(owner_dataset, member_graph_name, member_graph)

    # Fixed independently from the owner/query output. The reviewed source
    # observation is accepted, but the graph under test comes from reconstructed
    # fields, not a claim of possessing the complete official response bytes.
    assert _rows(
        owner_dataset,
        "debate-owner-office-holdings.rq",
        member=OFFICE_SAMPLE_MEMBER,
        member_graph=member_graph_name,
        office_graph=OFFICES_GRAPH,
    ) == [{
        "member": OFFICE_SAMPLE_MEMBER,
        "holding": (
            OFFICE_SAMPLE_MEMBER
            + "#office-holding-d5f24e6ce5feff7034e8dc16e1d029b3f56794647543ba7d254ecc578c9a45a6"
        ),
        "office": "https://data.oireachtas.ie/office/o-000001",
        "officeType": (
            "https://data.oireachtas.ie/ontology/members#TaoiseachOfficeType"
        ),
        "start": "2025-01-23T00:00:00",
    }]


@pytest.mark.parametrize(
    ("record_key", "expected"),
    [
        (
            "dail_2026",
            [
                ("dbsect_17", "lost", 53, 88, 0, "nil"),
                ("dbsect_21", "lost", 46, 98, 0, "nil"),
                ("dbsect_25", "lost", 67, 79, 0, "nil"),
                ("dbsect_29", "lost", 61, 78, 0, "nil"),
                ("dbsect_33", "lost", 63, 75, 0, "nil"),
                ("dbsect_37", "carried", 74, 65, 0, "ta"),
                ("dbsect_42", "carried", 74, 64, 0, "ta"),
                ("dbsect_46", "carried", 75, 65, 0, "ta"),
                ("dbsect_51", "lost", 65, 76, 0, "nil"),
            ],
        ),
        (
            "seanad",
            [
                ("dbsect_12", "carried", 21, 18, None, None),
                ("dbsect_9", None, 21, 22, None, None),
            ],
        ),
    ],
)
def test_division_query_returns_supported_outcomes_counts_and_only_recorded_member_votes(
    joined_dataset, record_key, expected
):
    case = WORKS[record_key]
    actual = _rows(
        joined_dataset["dataset"],
        "debate-divisions-and-votes.rq",
        record=case["work"],
        member=MEMBER,
        member_graph=joined_dataset["member_graph_name"],
    )
    expected_rows = []
    for eid, outcome, ta, nil, staon, vote_group in expected:
        row = {
            "division": f'{case["expression"]}/eid/e-{eid}',
            "ta": str(ta),
            "nil": str(nil),
        }
        if outcome is not None:
            row["outcome"] = f"https://data.oireachtas.ie/ontology#Declared{outcome.title()}"
        if staon is not None:
            row["staon"] = str(staon)
        if vote_group is not None:
            row["voteGroup"] = vote_group
        expected_rows.append(row)
    assert actual == expected_rows

    if record_key == "seanad":
        declared_division = f'{case["expression"]}/eid/e-dbsect_9'
        assert "outcome" not in next(row for row in actual if row["division"] == declared_division)


def test_bill_event_section_empty_result_remains_an_explicit_competency_gap(
    joined_dataset,
):
    actual = _rows(
        joined_dataset["dataset"],
        "debate-bill-event-sections.rq",
        bill=joined_dataset["bill_iri"],
        bill_graph=joined_dataset["bill_graph_name"],
    )
    # Rendering and executing the query with no rows does not fulfill the
    # competency: the active AKN evidence includes resolved section targets,
    # but the link mapping remains inactive and emits no cross-graph rows.
    assert actual == []
    bill_events = set(joined_dataset["bill_graph"].subjects(RDF.type, OIR.BillEvent))
    assert len(bill_events) >= 10

    # Independently count preserved AKN evidence, not transformer triples. The
    # checked-in sources contain 16 section @refersTo values: eight resolve to
    # local TLCEvent eIds and eight 2026 Dáil fragments do not name an eId.
    referenced_sections = []
    resolved_tlc_events = []
    unresolved_fragments = []
    for case in WORKS.values():
        root = ET.fromstring((DEBATE_DIR / case["file"]).read_bytes())
        eids = {node.get("eId"): node for node in root.iter() if node.get("eId")}
        for section in root.findall(".//akn:debateBody//akn:debateSection[@refersTo]", NS):
            referenced_sections.append(section)
            fragment = section.get("refersTo", "").removeprefix("#")
            target = eids.get(fragment)
            if target is not None and target.tag.rsplit("}", 1)[-1] == "TLCEvent":
                resolved_tlc_events.append(target)
            elif target is None:
                unresolved_fragments.append(fragment)
    assert len(referenced_sections) == 16
    assert len(resolved_tlc_events) == 8
    assert len(unresolved_fragments) == 8

    for result in joined_dataset["debates"].values():
        assert not list(result.graph.triples((None, OIR.refersToEvent, None)))


def test_query_renderer_rejects_unknown_or_unfilled_query_parameters():
    with pytest.raises(ValueError, match="unknown Debates competency query"):
        render_debate_competency_query("other.rq", {})
    with pytest.raises(ValueError, match="must be"):
        render_debate_competency_query("debate-record-sittings.rq", {})
