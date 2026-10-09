"""Focused safety and resolver tests for the non-production linking PoC."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql.parser import parseQuery

ROOT = Path(__file__).resolve().parents[1]
POC_DIR = ROOT / "poc" / "entity-linking"
sys.path.insert(0, str(POC_DIR))

import entity_linking as el

RUN_SPEC = importlib.util.spec_from_file_location("entity_linking_run", POC_DIR / "run.py")
assert RUN_SPEC and RUN_SPEC.loader
poc_run = importlib.util.module_from_spec(RUN_SPEC)
RUN_SPEC.loader.exec_module(poc_run)


MEMBER = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
BILL = "https://data.oireachtas.ie/ie/oireachtas/bill/2025/60"
OFFICE = "https://data.oireachtas.ie/office/o-000001"
UNIT = "https://data.oireachtas.ie/administrative-unit/u-000001"


def candidates() -> list[el.Identity]:
    return [
        el.Identity(
            MEMBER, "Member", (el.Alias("Timmy Dooley"),), "urn:graph:members",
            validity=(("dail", "2020-01-01", None, "34", 34),),
        ),
        el.Identity(
            BILL, "Bill", (el.Alias("Finance Bill 2025"), el.Alias("Bill 2025/60", "identifier")),
            "urn:graph:bills", bill_first_event="2025-01-01",
        ),
        el.Identity(
            OFFICE, "NamedOffice", (el.Alias("Taoiseach", valid_from="1937-12-29"),),
            "urn:graph:offices",
        ),
        el.Identity(UNIT, "AdministrativeUnit", (el.Alias("Department of Finance"),), "urn:graph:units"),
    ]


def record(text: str, *, date: str = "2025-02-27") -> dict:
    return {
        "contribution_iri": "https://example.test/speech/1",
        "text": text,
        "date": date,
        "speaker_targets": [],
        "structured_bill_targets": [],
    }


def test_exact_detection_is_whole_token_and_preserves_source_offsets():
    source = record("Timmy Dooley mentioned Finance Bill 2025 and Department of Finance.")
    found = el.detect_mentions(source, candidates())
    known = {(item.category, item.surface) for item in found if item.candidates}
    assert known == {
        ("Member", "Timmy Dooley"),
        ("Bill", "Finance Bill 2025"),
        ("AdministrativeUnit", "Department of Finance"),
    }
    for mention in found:
        assert source["text"][mention.start:mention.end] == mention.surface
    assert el.detect_mentions(record("Timmy Dooleyson spoke."), candidates()) == []


def test_generic_and_out_of_registry_mentions_never_get_invented_targets():
    generic_record = record(
        "The Deputy spoke about the Bill and the Department. "
        "The Minister of State answered."
    )
    generic = el.detect_mentions(generic_record, candidates())
    assert {item.category for item in generic if item.generic} == {
        "Member", "Bill", "AdministrativeUnit", "NamedOffice"
    }
    assert not any(
        item.surface in {"Minister of State", "Minister of State answered"} and not item.generic
        for item in generic
    )
    generic_text = record("This Bill is pending. The Deputy Leader spoke after the Deputy Speaker.")
    generic_mentions = el.detect_mentions(generic_text, [])
    assert ("Bill", "This Bill", True) in {
        (item.category, item.surface, item.generic) for item in generic_mentions
    }
    assert not any(
        item.category == "Bill" and not item.generic and item.surface == "This Bill"
        for item in generic_mentions
    )
    by_iri = {item.iri: item for item in candidates()}
    for mention in generic:
        decision = el.resolve_detection(mention, generic_record, by_iri, el.CONTEXT_METHOD)
        assert decision.status == "abstained"
        assert decision.target_iri is None

    unknown_record = record(
        "Deputy Jane Citizen discussed the Housing Support Bill 2026, "
        "the Minister for Public Expenditure and Reform, and the Department of Housing."
    )
    unknown = el.detect_mentions(unknown_record, candidates())
    expected = {
        ("Member", "Deputy Jane Citizen"),
        ("Bill", "Housing Support Bill 2026"),
        ("NamedOffice", "Minister for Public Expenditure and Reform"),
        ("AdministrativeUnit", "Department of Housing"),
    }
    assert expected <= {(item.category, item.surface) for item in unknown}
    for mention in unknown:
        if mention.surface in {surface for _, surface in expected}:
            assert not mention.candidates
            assert el.resolve_detection(
                mention, unknown_record, by_iri, el.CONTEXT_METHOD
            ).status == "out-of-registry"

    unknown_office = record("The Minister of State for Agriculture spoke.")
    named_office = next(
        item for item in el.detect_mentions(unknown_office, candidates())
        if item.category == "NamedOffice" and not item.generic
    )
    assert named_office.surface == "Minister of State for Agriculture"


def test_office_resolution_requires_nearby_same_sentence_institutional_context():
    by_iri = {item.iri: item for item in candidates()}
    explicit = record("The office of Taoiseach was discussed.")
    mention = next(item for item in el.detect_mentions(explicit, candidates()) if item.category == "NamedOffice")
    assert el.resolve_detection(mention, explicit, by_iri, el.CONTEXT_METHOD).target_iri == OFFICE

    unrelated = record("The office was discussed. The Taoiseach spoke to the House.")
    mention = next(item for item in el.detect_mentions(unrelated, candidates()) if item.category == "NamedOffice")
    decision = el.resolve_detection(mention, unrelated, by_iri, el.CONTEXT_METHOD)
    assert decision.status == "ambiguous"
    assert decision.target_iri is None


def test_contextual_member_resolution_obeys_membership_period_and_keeps_speaker_overlap_visible():
    member_candidate = candidates()[0]
    by_iri = {member_candidate.iri: member_candidate}
    source = record("Timmy Dooley spoke on this issue.", date="2025-02-27")
    mention = el.detect_mentions(source, [member_candidate])[0]
    assert el.resolve_detection(mention, source, by_iri, el.CONTEXT_METHOD).target_iri == MEMBER

    outside = record("Timmy Dooley was mentioned.", date="2000-01-01")
    mention = el.detect_mentions(outside, [member_candidate])[0]
    decision = el.resolve_detection(mention, outside, by_iri, el.CONTEXT_METHOD)
    assert decision.status == "abstained"
    assert decision.reason == "outside_valid_member_membership"

    speaker = record("Timmy Dooley spoke.")
    speaker["speaker_targets"] = [MEMBER]
    mention = el.detect_mentions(speaker, [member_candidate])[0]
    decision = el.resolve_detection(mention, speaker, by_iri, el.CONTEXT_METHOD)
    assert decision.target_iri == MEMBER
    assert decision.speaker_overlap


def test_reference_scoring_separates_detection_from_resolution_and_counts_false_links():
    reference = {
        "blind_to_method_outputs": True,
        "reviewer_type": "agent-provisional",
        "independent_human_review": False,
        "contributions": [{
            "contribution_iri": "speech-1",
            "mentions": [
                {
                    "category": "AdministrativeUnit", "label": "explicit-identity-mention",
                    "start_offset": 0, "end_offset": 25, "target_iri": UNIT,
                },
                {
                    "category": "Bill", "label": "generic-unresolved-reference",
                    "start_offset": 26, "end_offset": 34,
                },
            ],
        }],
    }
    predictions = {
        "method": [
            {
                "contribution_iri": "speech-1", "category": "AdministrativeUnit",
                "start_offset": 4, "end_offset": 25, "generic_reference": False,
                "status": "resolved", "target_iri": UNIT,
            },
            {
                "contribution_iri": "speech-1", "category": "Bill",
                "start_offset": 26, "end_offset": 34, "generic_reference": True,
                "status": "abstained", "target_iri": None,
            },
            {
                "contribution_iri": "speech-1", "category": "Member",
                "start_offset": 40, "end_offset": 52, "generic_reference": False,
                "status": "resolved", "target_iri": MEMBER,
            },
        ]
    }
    scored = el.score_reference(reference, predictions, methods=("method",))
    judgments = scored["judgments"]["method"]
    assert judgments["AdministrativeUnit"]["detection"]["true_positive"] == 0
    assert judgments["AdministrativeUnit"]["detection"]["false_positive"] == 1
    assert judgments["AdministrativeUnit"]["resolution"]["boundary_mismatch_alignment"] == 1
    assert judgments["AdministrativeUnit"]["resolution"]["correct_target"] == 1
    assert judgments["Bill"]["detection"]["true_positive"] == 1
    assert judgments["Member"]["resolution"]["unsupported_resolved_prediction"] == 1
    assert judgments["Member"]["resolution"]["precision_on_accepted_links"] == 0


def test_reference_scoring_excludes_predictions_overlapping_uncertain_spans():
    reference = {
        "blind_to_method_outputs": True,
        "contributions": [{
            "contribution_iri": "speech-1",
            "mentions": [
                {
                    "category": "AdministrativeUnit", "label": "explicit-identity-mention",
                    "start_offset": 0, "end_offset": 10, "target_iri": UNIT,
                },
                {
                    "category": "AdministrativeUnit", "label": "uncertain",
                    "start_offset": 40, "end_offset": 55,
                },
            ],
        }],
    }
    predictions = {
        "method": [
            {
                "contribution_iri": "speech-1", "category": "AdministrativeUnit",
                "start_offset": 0, "end_offset": 10, "status": "resolved", "target_iri": UNIT,
            },
            {
                "contribution_iri": "speech-1", "category": "AdministrativeUnit",
                "start_offset": 42, "end_offset": 52, "status": "resolved", "target_iri": "other-unit",
            },
            {
                "contribution_iri": "speech-1", "category": "AdministrativeUnit",
                "start_offset": 60, "end_offset": 70, "status": "resolved", "target_iri": "other-unit",
            },
        ]
    }

    scored = el.score_reference(reference, predictions, methods=("method",))
    judgment = scored["judgments"]["method"]["AdministrativeUnit"]
    assert judgment["detection"] == {
        "reference_spans": 1,
        "uncertain_reference_spans": 1,
        "predictions_excluded_by_uncertainty": 1,
        "predicted_spans": 2,
        "true_positive": 1,
        "false_positive": 1,
        "missed_reference_spans": 0,
        "precision": 0.5,
        "recall": 1.0,
        "by_reference_label": {
            "ambiguous-office-or-holder": {"reference_spans": 0, "detected_spans": 0, "missed_spans": 0},
            "explicit-identity-mention": {"reference_spans": 1, "detected_spans": 1, "missed_spans": 0},
            "generic-unresolved-reference": {"reference_spans": 0, "detected_spans": 0, "missed_spans": 0},
            "out-of-registry-named-entity": {"reference_spans": 0, "detected_spans": 0, "missed_spans": 0},
        },
    }
    assert judgment["resolution"]["correct_target"] == 1
    assert judgment["resolution"]["unsupported_resolved_prediction"] == 1
    assert judgment["resolution"]["resolved_predictions_in_reviewed_contributions"] == 2
    assert judgment["resolution"]["precision_on_accepted_links"] == 0.5


def test_graph_leak_check_rejects_even_short_complete_transcripts():
    transcript = "Short source text."
    graph = Graph(identifier=URIRef("urn:graph:test"))
    graph.add((URIRef("urn:mention:1"), URIRef("urn:surface"), Literal(transcript)))
    with pytest.raises(ValueError, match="full contribution transcript leaked"):
        poc_run._graph_leak_check(
            [{"text": transcript}], {"urn:graph:test": graph}
        )


def test_canonical_graph_hash_normalizes_rdf11_plain_and_xsd_string_literals():
    typed = Graph()
    simple = Graph()
    triple = (URIRef("urn:s"), URIRef("urn:p"), Literal("value", datatype=XSD.string))
    typed.add(triple)
    simple.add((triple[0], triple[1], Literal("value")))
    assert el.canonical_graph_bytes(typed) == el.canonical_graph_bytes(simple)


def test_reference_validation_binds_review_spans_to_evaluation_source_only():
    source = {
        "contribution_iri": "speech-1", "source_id": "work-1", "work_iri": "work-1",
        "source_pointer": "/speech[1]", "source_sha256": "a" * 64,
        "text_sha256": "b" * 64, "date": "2025-02-27", "split": "evaluation",
        "text": "The Department of Finance replied.",
    }
    reference = {
        "blind_to_method_outputs": True, "reviewed_contributions": 1,
        "contributions": [{
            "contribution_iri": "speech-1", "source_id": "work-1", "work_iri": "work-1",
            "source_pointer": "/speech[1]", "source_sha256": "a" * 64,
            "text_sha256": "b" * 64, "date": "2025-02-27",
            "mentions": [{
                "category": "AdministrativeUnit", "label": "explicit-identity-mention",
                "start_offset": 4, "end_offset": 25, "surface": "Department of Finance",
                "target_iri": UNIT,
            }],
        }],
    }
    poc_run.validate_reference(reference, [source])

    bad_span = {**reference, "contributions": [dict(reference["contributions"][0]) ]}
    bad_span["contributions"][0]["mentions"] = [dict(reference["contributions"][0]["mentions"][0])]
    bad_span["contributions"][0]["mentions"][0]["surface"] = "Finance Department"
    with pytest.raises(ValueError, match="span does not match"):
        poc_run.validate_reference(bad_span, [source])

    text_bearing = {**reference, "text": "complete transcript"}
    with pytest.raises(ValueError, match="must not contain transcript text"):
        poc_run.validate_reference(text_bearing, [source])


def test_retrieval_query_filters_the_exact_mention_surface_and_reports_abstentions():
    question = {
        "category": "AdministrativeUnit", "target_iri": UNIT,
        "full_text_query": "the Department",
    }
    source = {"source_id": "source-1", "graph_iri": "urn:graph:debate"}
    records = [{"source_id": "source-1", "contribution_iri": "speech-1"}]
    mention_graph = "urn:graph:mentions"
    link_graph = "urn:graph:links"
    query = poc_run.build_retrieval_query(
        question, source, records, method=el.CONTEXT_METHOD,
        mention_graph_iri=mention_graph, link_graph_iri=link_graph, owners={},
    )
    parseQuery(query)
    assert 'FILTER(LCASE(STR(?surface)) = LCASE("the Department"))' in query

    rows = {
        "contribution_iri": "speech-1", "category": "AdministrativeUnit",
        "status": "abstained", "surface": "the Department",
    }
    unrelated_explicit = dict(rows, surface="Department of Finance", status="resolved")
    outcomes = poc_run.mention_outcomes_for_question(
        question,
        {method: [rows, unrelated_explicit] for method in poc_run.METHODS},
        records,
    )
    assert outcomes[el.CONTEXT_METHOD]["mention_occurrences"] == 1
    assert outcomes[el.CONTEXT_METHOD]["status_counts"] == {"abstained": 1}
