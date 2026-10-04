"""RDF acceptance for the five preserved Debates AKN source records.

Expected counts and key RDF triples below were fixed from the Tranche 1 source
audit and approved mapping/identity contract, not sampled from the transformer.
The small Turtle files are hand-written structural golden subsets.  Additional
source-order and containment expectations are independently calculated from
the immutable XML tree and compared with the emitted RDF.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from oireachtas_etl.serialization import nquads
from oireachtas_etl.transforms.common import ELIDL, OIR
from oireachtas_etl.transforms.debates import transform_debate


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "debates_examples"
EXPECTED_DIR = ROOT / "tests" / "fixtures" / "debates_expected"
AKN = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
NS = {"akn": AKN}
AKN_NS = f"{{{AKN}}}"
ADDRESSABLE = {
    AKN_NS + local
    for local in ("debateSection", "speech", "summary", "question")
}

# Manually fixed source and RDF cardinalities. Committee rollCall's sum_2 is
# excluded entirely from RDF, including its sourceOrdinal.
CASES = {
    "dail_2015": {
        "filename": "dail_2015-07-02.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/eng%40",
        "graph": "https://data.oireachtas.ie/graph/debate/dail/2015-07-02",
        "date": "2015-07-02",
        "type": None,
        "counts": {
            "sections": 54, "speeches": 1020, "summaries": 79,
            "questions": 10, "divisions": 8, "roots": 16,
            "subsections": 30, "has_division": 8, "has_speech": 1020,
            "has_summary": 79, "has_question": 10,
            "ordinals": 1163, "recorded_times": 0,
            "outcomes": 8, "ta_counts": 8, "nil_counts": 8,
            "staon_counts": 0,
        },
    },
    "dail_2026": {
        "filename": "dail_2026-02-26.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-02-25/debate",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-02-25/debate/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/dail/2026-02-25/debate",
        "date": "2026-02-25",
        "type": "debate",
        "counts": {
            "sections": 54, "speeches": 428, "summaries": 158,
            "questions": 0, "divisions": 9, "roots": 14,
            "subsections": 31, "has_division": 9, "has_speech": 428,
            "has_summary": 158, "has_question": 0,
            "ordinals": 640, "recorded_times": 428,
            "outcomes": 9, "ta_counts": 9, "nil_counts": 9,
            "staon_counts": 9,
        },
    },
    "seanad": {
        "filename": "seanad_2015-07-02.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/seanad/2015-07-02/debate",
        "date": "2015-07-02",
        "type": "debate",
        "counts": {
            "sections": 17, "speeches": 205, "summaries": 38,
            "questions": 0, "divisions": 2, "roots": 7,
            "subsections": 8, "has_division": 2, "has_speech": 205,
            "has_summary": 38, "has_question": 0,
            "ordinals": 260, "recorded_times": 205,
            "outcomes": 1, "ta_counts": 2, "nil_counts": 2,
            "staon_counts": 0,
        },
    },
    "committee": {
        "filename": "committee_public_accounts_2026-09-24.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/committee_of_public_accounts/2026-09-24/debate",
        "date": "2026-09-24",
        "type": "debate",
        "counts": {
            "sections": 3, "speeches": 929, "summaries": 13,
            "questions": 0, "divisions": 0, "roots": 3,
            "subsections": 0, "has_division": 0, "has_speech": 929,
            "has_summary": 13, "has_question": 0,
            "ordinals": 945, "recorded_times": 929,
            "outcomes": 0, "ta_counts": 0, "nil_counts": 0,
            "staon_counts": 0,
        },
    },
    "written": {
        "filename": "dail_written_answers_2015-07-02.akn.xml",
        "work": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens",
        "expression": "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/writtens/mul%40",
        "graph": "https://data.oireachtas.ie/graph/debate/dail/2015-07-02/writtens",
        "date": "2015-07-02",
        "type": "writtens",
        "counts": {
            "sections": 217, "speeches": 197, "summaries": 18,
            "questions": 229, "divisions": 0, "roots": 20,
            "subsections": 197, "has_division": 0, "has_speech": 197,
            "has_summary": 18, "has_question": 229,
            "ordinals": 661, "recorded_times": 197,
            "outcomes": 0, "ta_counts": 0, "nil_counts": 0,
            "staon_counts": 0,
        },
    },
}

# Independently inspected @href -> result-Summary -> containing-Division joins.
# Values are source counts; absent Staon entries are not made into zero, while
# explicit 2026 Staon zeroes are part of the golden.
VOTE_GOLDENS = {
    "dail_2015": {
        "dbsect_19": (65, 39, None, "carried"),
        "dbsect_22": (64, 37, None, "carried"),
        "dbsect_25": (64, 39, None, "carried"),
        "dbsect_30": (64, 35, None, "carried"),
        "dbsect_35": (59, 26, None, "carried"),
        "dbsect_38": (60, 27, None, "carried"),
        "dbsect_41": (58, 29, None, "carried"),
        "dbsect_44": (63, 34, None, "carried"),
    },
    "dail_2026": {
        "dbsect_17": (53, 88, 0, "lost"),
        "dbsect_21": (46, 98, 0, "lost"),
        "dbsect_25": (67, 79, 0, "lost"),
        "dbsect_29": (61, 78, 0, "lost"),
        "dbsect_33": (63, 75, 0, "lost"),
        "dbsect_37": (74, 65, 0, "carried"),
        "dbsect_42": (74, 64, 0, "carried"),
        "dbsect_46": (75, 65, 0, "carried"),
        "dbsect_51": (65, 76, 0, "lost"),
    },
    "seanad": {
        "dbsect_9": (21, 22, None, None),  # #declared: no RDF outcome
        "dbsect_12": (21, 18, None, "carried"),
    },
    "committee": {},
    "written": {},
}


@pytest.fixture(scope="module")
def transformed():
    """Use the public Tranche 2 API; no production helper is used as oracle."""

    results = {}
    for key, case in CASES.items():
        source = (SOURCE_DIR / case["filename"]).read_bytes()
        results[key] = transform_debate(source, resolver=None)
    return results


def _source_root(case: dict) -> ET.Element:
    return ET.fromstring((SOURCE_DIR / case["filename"]).read_bytes())


def _eid_resource(expression: str, element: ET.Element) -> URIRef:
    eid = element.get("eId")
    assert eid, f"preserved representative element lacks eId: {element.tag}"
    # A test-local RFC 3986 component encoding, independent of production code.
    return URIRef(f"{expression}/eid/e-{quote(eid, safe='-._~', encoding='utf-8')}")


def _structural_expectations(case: dict, root: ET.Element) -> set[tuple]:
    """Build expected containment/type triples directly from AKN children."""

    graph = set()
    body = root.find(".//akn:debateBody", NS)
    assert body is not None
    expression = case["expression"]
    work = URIRef(case["work"])
    expression_ref = URIRef(expression)

    top_sections = body.findall("akn:debateSection", NS)
    for section in top_sections:
        child_ref = _eid_resource(expression, section)
        graph.add((work, OIR.hasSection, child_ref))
        graph.add((expression_ref, OIR.expressionHasSection, child_ref))

    for section in body.iter(AKN_NS + "debateSection"):
        section_ref = _eid_resource(expression, section)
        graph.add((section_ref, RDF.type, OIR.DebateSection))
        if section.get("name") is not None:
            graph.add((section_ref, OIR.sectionName,
                       Literal(section.get("name"), datatype=XSD.string)))

        for child in section:
            child_ref = None
            if child.tag == AKN_NS + "debateSection":
                child_ref = _eid_resource(expression, child)
                if child.get("name") == "division":
                    graph.add((section_ref, OIR.hasDivision, child_ref))
                    graph.add((child_ref, RDF.type, OIR.Division))
                else:
                    graph.add((section_ref, OIR.hasSubSection, child_ref))
            elif child.tag == AKN_NS + "speech":
                child_ref = _eid_resource(expression, child)
                graph.add((section_ref, OIR.hasSpeech, child_ref))
                graph.add((child_ref, RDF.type, OIR.Speech))
            elif child.tag == AKN_NS + "summary":
                child_ref = _eid_resource(expression, child)
                graph.add((section_ref, OIR.hasSummary, child_ref))
                graph.add((child_ref, RDF.type, OIR.Summary))
            elif child.tag == AKN_NS + "question":
                child_ref = _eid_resource(expression, child)
                graph.add((section_ref, OIR.hasQuestion, child_ref))
                graph.add((child_ref, RDF.type, OIR.ParliamentaryQuestion))
    return graph


def _ordinal_expectations(case: dict, root: ET.Element) -> set[tuple]:
    """Apply the approved immediate-child rule independently to the XML tree."""

    body = root.find(".//akn:debateBody", NS)
    assert body is not None
    expression = case["expression"]
    expected = set()
    # The RDF containing resources are the Expression/debateBody and each
    # DebateSection. A source-only rollCall wrapper is intentionally not treated
    # as an addressable RDF parent.
    for container in (body, *body.iter(AKN_NS + "debateSection")):
        ordinal = 0
        for child in container:
            if child.tag in ADDRESSABLE:
                ordinal += 1
                expected.add(
                    (_eid_resource(expression, child), OIR.sourceOrdinal,
                     Literal(ordinal, datatype=XSD.integer))
                )
    return expected


def _class_count(graph: Graph, class_iri: URIRef) -> int:
    return len(set(graph.subjects(RDF.type, class_iri)))


def _assert_vote_golden(key: str, graph: Graph, expression: str) -> None:
    expected_ta = set()
    expected_nil = set()
    expected_staon = set()
    expected_outcomes = set()
    for eid, (ta, nil, staon, outcome) in VOTE_GOLDENS[key].items():
        division = URIRef(f"{expression}/eid/e-{eid}")
        expected_ta.add((division, OIR.taCount, Literal(ta, datatype=XSD.integer)))
        expected_nil.add((division, OIR.nilCount, Literal(nil, datatype=XSD.integer)))
        if staon is not None:
            expected_staon.add(
                (division, OIR.staonCount, Literal(staon, datatype=XSD.integer))
            )
        if outcome is not None:
            expected_outcomes.add(
                (division, OIR.divisionOutcome,
                 OIR.DeclaredCarried if outcome == "carried" else OIR.DeclaredLost)
            )

    assert set(graph.triples((None, OIR.taCount, None))) == expected_ta
    assert set(graph.triples((None, OIR.nilCount, None))) == expected_nil
    assert set(graph.triples((None, OIR.staonCount, None))) == expected_staon
    assert set(graph.triples((None, OIR.divisionOutcome, None))) == expected_outcomes


@pytest.mark.parametrize("key", CASES)
def test_each_full_fixture_matches_fixed_counts_and_independent_structural_rdf(
    key, transformed
):
    case = CASES[key]
    result = transformed[key]
    graph = result.graph
    root = _source_root(case)
    counts = case["counts"]

    assert result.work_iri == case["work"]
    assert result.expression_iri == case["expression"]
    assert result.graph_iri == case["graph"]
    work = URIRef(case["work"])
    expression = URIRef(case["expression"])
    expected_date = Literal(case["date"] + "T00:00:00", datatype=XSD.dateTime)
    assert set(graph.objects(work, OIR.debateDate)) == {expected_date}
    assert set(graph.objects(work, OIR.hasExpression)) == {expression}
    assert set(graph.objects(expression, OIR.expressionLanguageCode)) == {
        Literal("eng", datatype=XSD.string)
    }
    if case["type"] is None:
        assert not list(graph.objects(work, OIR.debateType))
    else:
        assert set(graph.objects(work, OIR.debateType)) == {
            Literal(case["type"], datatype=XSD.string)
        }

    sitting = URIRef(case["work"] + "#sitting")
    expected_sittings = set() if key == "written" else {sitting}
    assert set(graph.subjects(RDF.type, OIR.DebateSitting)) == expected_sittings
    if key != "written":
        assert set(graph.objects(sitting, OIR.producedRecord)) == {work}
        assert set(graph.objects(sitting, ELIDL.activity_date)) == {
            Literal(case["date"], datatype=XSD.date)
        }

    assert _class_count(graph, OIR.DebateRecord) == 1
    assert _class_count(graph, OIR.DebateExpression) == 1
    assert _class_count(graph, OIR.DebateSitting) == (0 if key == "written" else 1)
    assert _class_count(graph, OIR.DebateSection) == counts["sections"]
    assert _class_count(graph, OIR.Speech) == counts["speeches"]
    assert _class_count(graph, OIR.ParliamentaryQuestion) == counts["questions"]
    assert _class_count(graph, OIR.Division) == counts["divisions"]
    structural = _structural_expectations(case, root)
    expected_section_summaries = {
        subject for subject, predicate, object_ in structural
        if predicate == RDF.type and object_ == OIR.Summary
    }
    assert _class_count(graph, OIR.Summary) == counts["summaries"]
    assert set(graph.subjects(RDF.type, OIR.Summary)) == expected_section_summaries
    if key == "committee":
        roll_call_summary_node = root.find(
            ".//akn:rollCall/akn:summary[@eId='sum_2']", NS
        )
        assert roll_call_summary_node is not None
        roll_call_summary = _eid_resource(case["expression"], roll_call_summary_node)
        assert not any(roll_call_summary in triple for triple in graph), (
            "rollCall sum_2 must be absent from RDF, including sourceOrdinal"
        )

    # Identity, structural containment, and dates are checked against hand-fixed
    # Turtle triples; broader containment and ordinals are source-derived in a
    # test-local calculation, never read back from the transformer.
    golden = Graph().parse(EXPECTED_DIR / f"{key}.ttl", format="turtle")
    if key == "committee":
        assert not any(roll_call_summary in triple for triple in golden)
    assert set(golden) <= set(graph)
    assert structural <= set(graph)
    expected_ordinals = _ordinal_expectations(case, root)
    actual_ordinals = set(graph.triples((None, OIR.sourceOrdinal, None)))
    assert len(expected_ordinals) == counts["ordinals"]
    assert actual_ordinals == expected_ordinals

    assert len(set(graph.triples((None, OIR.hasSection, None)))) == counts["roots"]
    assert len(set(graph.triples((None, OIR.expressionHasSection, None)))) == counts["roots"]
    assert len(set(graph.triples((None, OIR.hasSubSection, None)))) == counts["subsections"]
    assert len(set(graph.triples((None, OIR.hasDivision, None)))) == counts["has_division"]
    assert len(set(graph.triples((None, OIR.hasSpeech, None)))) == counts["has_speech"]
    assert len(set(graph.triples((None, OIR.hasSummary, None)))) == counts["has_summary"]
    assert len(set(graph.triples((None, OIR.hasQuestion, None)))) == counts["has_question"]
    assert len(set(graph.triples((None, OIR.sectionName, None)))) == counts["sections"]
    assert len(set(graph.triples((None, OIR.recordedTime, None)))) == counts["recorded_times"]

    _assert_vote_golden(key, graph, case["expression"])


def test_written_answers_are_a_dated_record_without_sitting_and_keep_question_containment(
    transformed,
):
    case = CASES["written"]
    result = transformed["written"]
    graph = result.graph
    work = URIRef(case["work"])
    expression = URIRef(case["expression"])
    sitting = URIRef(case["work"] + "#sitting")

    assert (work, OIR.debateDate, Literal("2015-07-02T00:00:00", datatype=XSD.dateTime)) in graph
    assert (work, OIR.debateType, Literal("writtens", datatype=XSD.string)) in graph
    assert (work, OIR.hasExpression, expression) in graph
    assert (sitting, RDF.type, OIR.DebateSitting) not in graph
    assert not list(graph.triples((sitting, None, None)))
    assert not list(graph.triples((None, OIR.producedRecord, work)))
    assert not list(graph.triples((None, ELIDL.activity_date, None)))

    parent = URIRef(case["expression"] + "/eid/e-dbsect_69")
    written_answer = URIRef(case["expression"] + "/eid/e-dbsect_83")
    question_a = URIRef(case["expression"] + "/eid/e-pq_38")
    question_b = URIRef(case["expression"] + "/eid/e-pq_57")
    response = URIRef(case["expression"] + "/eid/e-spk_1033")
    assert (parent, OIR.hasSubSection, written_answer) in graph
    assert (written_answer, OIR.hasQuestion, question_a) in graph
    assert (written_answer, OIR.hasQuestion, question_b) in graph
    assert (written_answer, OIR.hasSpeech, response) in graph
    assert (question_a, OIR.sourceOrdinal, Literal(1, datatype=XSD.integer)) in graph
    assert (question_b, OIR.sourceOrdinal, Literal(2, datatype=XSD.integer)) in graph
    assert (response, OIR.sourceOrdinal, Literal(3, datatype=XSD.integer)) in graph
    # No direct question-to-response predicate is approved; no office/holder
    # recipient identity is assumed by this golden.
    assert not list(graph.triples((question_a, None, response)))
    assert not list(graph.triples((question_b, None, response)))


def test_declared_seanad_outcome_is_audited_by_source_but_never_guessed_in_rdf(
    transformed,
):
    case = CASES["seanad"]
    graph = transformed["seanad"].graph
    declared_division = URIRef(case["expression"] + "/eid/e-dbsect_9")
    assert (declared_division, RDF.type, OIR.Division) in graph
    assert (declared_division, OIR.taCount, Literal(21, datatype=XSD.integer)) in graph
    assert (declared_division, OIR.nilCount, Literal(22, datatype=XSD.integer)) in graph
    assert not list(graph.triples((declared_division, OIR.divisionOutcome, None)))
    assert (declared_division, OIR.divisionOutcome, OIR.DeclaredCarried) not in graph
    assert (declared_division, OIR.divisionOutcome, OIR.DeclaredLost) not in graph


def test_unresolved_placeholders_do_not_gain_a_speaker_or_participation_target(
    transformed,
):
    for key, case in CASES.items():
        root = _source_root(case)
        graph = transformed[key].graph
        for speech in root.findall(".//akn:debateBody//akn:speech[@by='#']", NS):
            resource = _eid_resource(case["expression"], speech)
            participation = URIRef(str(resource) + "#participation")
            assert (resource, RDF.type, OIR.Speech) in graph
            assert not list(graph.triples((resource, OIR.speaker, None)))
            assert not list(graph.triples((resource, OIR.hasSpeechParticipation, None)))
            assert not list(graph.triples((participation, None, None)))

    # No owner registry or separately reviewed role crosswalk is passed to any
    # of these runs.  Therefore source person/role labels alone cannot resolve
    # member shortcuts or ELI participation targets.
    for result in transformed.values():
        graph = result.graph
        for predicate in (OIR.speaker, OIR.askedBy, OIR.hasSpeechParticipation,
                          ELIDL.had_participant_person, ELIDL.participation_role):
            assert not list(graph.triples((None, predicate, None)))

    # question/@to stays deferred: no role or NamedOffice is asserted based on
    # an AKN label, and this test deliberately supplies no recipient mapping.
    for result in transformed.values():
        assert not list(result.graph.triples((None, OIR.directedTo, None)))
        assert not list(result.graph.triples((None, OIR.directedToOffice, None)))


def test_committee_roll_call_people_do_not_become_votes_or_descriptions(transformed):
    case = CASES["committee"]
    root = _source_root(case)
    graph = transformed["committee"].graph
    roll_call_people = root.findall(".//akn:rollCall//akn:person[@refersTo]", NS)
    assert len(roll_call_people) == 11
    assert _class_count(graph, OIR.Division) == 0
    for predicate in (OIR.votedFor, OIR.votedAgainst, OIR.abstained):
        assert not list(graph.triples((None, predicate, None)))
    assert not list(graph.triples((None, OIR.hasSpeechParticipation, None)))
    assert not list(graph.triples((None, ELIDL.had_participant_person, None)))
    assert not list(graph.triples((None, ELIDL.participation_role, None)))
    assert _class_count(graph, ELIDL.Participation) == 0

    # All eleven people also occur as speech/@by values in this source, so a
    # blanket ban on those Member references would wrongly test attendance as
    # the source of legitimate speech metadata.  With no external resolver or
    # reviewed @as crosswalk supplied, none can become a Participation; this
    # also prevents accidentally resolving them through the table alone.
    for person in roll_call_people:
        assert person.get("refersTo")


def test_rdf_boundary_excludes_non_active_predicates_foreign_descriptions_and_prose(
    transformed,
):
    forbidden = {
        OIR.directedTo,
        OIR.directedToOffice,
        OIR.refersToEvent,
        OIR.refersToProposal,
        OIR.inHouse,
        ELIDL.had_participation,
    }
    literal_predicates = {
        OIR.debateDate,
        OIR.debateType,
        OIR.expressionLanguageCode,
        OIR.sectionName,
        OIR.recordedTime,
        OIR.sourceOrdinal,
        OIR.taCount,
        OIR.nilCount,
        OIR.staonCount,
        ELIDL.activity_date,
    }

    for key, case in CASES.items():
        graph = transformed[key].graph
        for predicate in forbidden:
            assert not list(graph.triples((None, predicate, None)))
        speech_resources = set(graph.subjects(RDF.type, OIR.Speech))
        activity_resources = set(graph.subjects(RDF.type, ELIDL.Activity))
        assert not (speech_resources & activity_resources)

        work = case["work"]
        expression = case["expression"]
        sitting = work + "#sitting"

        def owned(subject) -> bool:
            iri = str(subject)
            return (
                iri in {work, expression, sitting}
                or iri.startswith(expression + "/eid/")
                or iri.startswith(expression + "/fallback/")
            )

        # This named graph may describe only resources derived from this AKN
        # Work/Expression.  Foreign owners can occur as URI objects, never as
        # subjects with copied class/label/description triples.
        assert all(owned(subject) for subject in graph.subjects())
        assert all(not isinstance(subject, URIRef) or owned(subject) for subject in graph.subjects())
        subject_set = set(graph.subjects())
        for target in set(graph.objects()):
            if isinstance(target, URIRef) and target not in subject_set:
                assert not list(graph.triples((target, None, None)))

        # Any literal must come from an explicitly approved structural/metadata
        # predicate; transcript text has no RDF property in the active mapping.
        assert {
            predicate for _, predicate, value in graph if isinstance(value, Literal)
        } <= literal_predicates

        root = _source_root(case)
        source_prose = set()
        for element in root.iter():
            local = element.tag.rsplit("}", 1)[-1]
            if local in {"p", "summary", "heading", "from"}:
                text = " ".join("".join(element.itertext()).split())
                if len(text) >= 12:
                    source_prose.add(text)
        literal_values = [str(value) for value in graph.objects() if isinstance(value, Literal)]
        for prose in source_prose:
            assert all(prose not in " ".join(value.split()) for value in literal_values)


def test_transform_repeats_to_identical_named_graph_quads(transformed):
    for key, case in CASES.items():
        source = (SOURCE_DIR / case["filename"]).read_bytes()
        first = transformed[key]
        repeated = transform_debate(source, resolver=None)
        assert repeated.graph_iri == first.graph_iri == case["graph"]
        assert nquads(first.graph, first.graph_iri) == nquads(
            repeated.graph, repeated.graph_iri
        )
