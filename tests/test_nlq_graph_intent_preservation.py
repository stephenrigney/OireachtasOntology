"""Whole-original-question guards for existing composable graph families."""

from __future__ import annotations

from datetime import date
import copy

import pytest

from poc.nlq.composable_semantic_planner import (
    validate_composable_plan_draft,
)
from poc.nlq.graph_intent import (
    validate_constituency_representation_intent,
    validate_shared_dail_terms_intent,
)
from poc.nlq.representation import representation_plan
from poc.nlq.semantic_graphs import (
    build_anchored_shared_constituency_draft,
    build_constituency_representation_draft,
    build_shared_dail_terms_draft,
)


AS_OF = date(2026, 10, 28)
MEMBER_A = "Micheál Martin"
MEMBER_B = "Mary Lou McDonald"


def _representation_draft(*, member=None, constituency=None, selector):
    if member is not None:
        return build_constituency_representation_draft(member, selector)
    canonical = representation_plan(as_of=AS_OF, constituency=constituency)
    referents = {
        key: {"type": ref["type"], "mention": ref.get("mention")}
        for key, ref in canonical["referents"].items()
    }
    referents["term"]["selector"] = selector
    return {
        "version": 2,
        "supported": True,
        "family": "constituency_representation",
        "unsupportedReason": None,
        "intent": "Return current TDs for the exact named constituency.",
        "referents": referents,
        "relations": copy.deepcopy(canonical["relations"]),
        "constraints": [],
        "answer": copy.deepcopy(canonical["answer"]),
    }


def _legacy_validator_accepts(draft, question):
    plan, unsupported = validate_composable_plan_draft(draft, question=question)
    assert plan is not None
    assert unsupported is None


def _legacy_validator_rejects(draft, question):
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question=question)


@pytest.mark.parametrize(("question", "first", "second"), [
    (
        "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?",
        MEMBER_A, MEMBER_B,
    ),
    (
        "Name the Dáil terms common to Micheál Martin and Mary Lou McDonald.",
        MEMBER_A, MEMBER_B,
    ),
    (
        "Where do Micheál Martin's and Mary Lou McDonald's recorded Dáil service histories overlap?",
        MEMBER_A, MEMBER_B,
    ),
    (
        "List the Dáil terms shared by Mary Lou McDonald and Micheál Martin.",
        MEMBER_A, MEMBER_B,
    ),
    (
        "Which Dáil terms have Micheál Martin and Mary Lou McDonald both served in?",
        MEMBER_A, MEMBER_B,
    ),
    (
        "Show the Dáil terms common to the service records of Dick Spring and Brendan Howlin.",
        "Dick Spring", "Brendan Howlin",
    ),
    (
        "What Dáil terms were shared by Jack Lynch and John Bruton?",
        "Jack Lynch", "John Bruton",
    ),
])
def test_supported_shared_term_variants_are_preserved_without_mutating_inputs(question, first, second):
    original_question = question
    mentions = (first, second)
    validate_shared_dail_terms_intent(question, *mentions)
    assert question == original_question
    assert mentions == (first, second)


@pytest.mark.parametrize("question", [
    "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in, and did Leo Varadkar serve in them too?",
    "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in while representing Dublin Central?",
    "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in on 1 January 2020?",
    "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in when both were women?",
    "Which Seanad terms did Micheál Martin and Mary Lou McDonald both serve in?",
    "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in at the same time?",
])
def test_shared_term_guard_rejects_the_legacy_validators_accepted_extra_intent(question):
    draft = build_shared_dail_terms_draft(MEMBER_A, MEMBER_B)
    _legacy_validator_rejects(draft, question)

    with pytest.raises(ValueError, match="shared_dail_terms intent"):
        validate_shared_dail_terms_intent(question, MEMBER_A, MEMBER_B)


def test_shared_term_guard_does_not_convert_a_count_into_a_term_set():
    question = "How many Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?"
    _legacy_validator_rejects(build_shared_dail_terms_draft(MEMBER_A, MEMBER_B), question)
    with pytest.raises(ValueError, match="shared_dail_terms intent"):
        validate_shared_dail_terms_intent(
            question,
            MEMBER_A, MEMBER_B,
        )


@pytest.mark.parametrize(("question", "selector"), [
    ("Which constituency does Mary Lou McDonald represent currently?", "currentTerm"),
    ("What constituency does Micheál Martin represent?", "currentTerm"),
    ("What constituencies did Bertie Ahern represent?", None),
    ("List Bertie Ahern's historical constituencies.", None),
    ("Which constituencies has Mary Lou McDonald represented?", None),
    ("Which constituency did Micheál Martin represent in his latest recorded Dáil term?", "latestRecorded"),
    ("Which constituency did Bertie Ahern represent in his last term in the Dáil?", "latestRecorded"),
    ("What was the latest recorded Dáil term and constituency for Bertie Ahern?", "latestRecorded"),
    ("What constituencies did Bertie Ahern represent in each Dáil term?", None),
])
def test_supported_named_member_representation_and_evidence_scopes_are_preserved(question, selector):
    member = "Mary Lou McDonald" if "Mary Lou McDonald" in question else (
        "Micheál Martin" if "Micheál Martin" in question else "Bertie Ahern"
    )
    original_question = question
    draft = build_constituency_representation_draft(member, selector)
    _legacy_validator_accepts(draft, question)

    validate_constituency_representation_intent(
        question, member=member, selector=selector,
    )
    assert question == original_question
    assert draft["referents"]["member"]["mention"] == member


@pytest.mark.parametrize(("question", "member", "selector"), [
    (
        "In Eamon Gilmore's latest recorded Dáil term, what was his constituency?",
        "Eamon Gilmore", "latestRecorded",
    ),
    (
        "In Mary Lou McDonald's latest recorded Dáil term, what was her constituency?",
        "Mary Lou McDonald", "latestRecorded",
    ),
    (
        "In Bertie Ahern's latest recorded Dáil term, what was their constituency?",
        "Bertie Ahern", "latestRecorded",
    ),
    (
        "List every constituency Frances Fitzgerald has represented in the Dáil, keeping the terms separate.",
        "Frances Fitzgerald", None,
    ),
    (
        "List every constituency Mary Lou McDonald has represented in the Dáil, keeping the terms separate.",
        "Mary Lou McDonald", None,
    ),
])
def test_existing_possessive_latest_and_preserved_career_wordings_validate_as_complete_graphs(
    question, member, selector,
):
    draft = build_constituency_representation_draft(member, selector)
    _legacy_validator_accepts(draft, question)
    assert draft["answer"]["preserveEvidence"] is True
    assert {detail["referent"] for detail in draft["answer"]["details"]} == {"term"}
    validate_constituency_representation_intent(question, member=member, selector=selector)


@pytest.mark.parametrize(("question", "member", "selector"), [
    (
        "In Eamon Gilmore's latest recorded Dáil term, what were his and Mary Lou McDonald's constituencies?",
        "Eamon Gilmore", "latestRecorded",
    ),
    (
        "In Eamon Gilmore's latest recorded Dáil term, what was his constituency and what office did he hold?",
        "Eamon Gilmore", "latestRecorded",
    ),
    (
        "In Eamon Gilmore's latest recorded Dáil term, what was his constituency, and was he a man?",
        "Eamon Gilmore", "latestRecorded",
    ),
    (
        "In Eamon Gilmore's latest recorded Dáil term, what was his constituency on 1 January 2014?",
        "Eamon Gilmore", "latestRecorded",
    ),
    (
        "List every constituency Frances Fitzgerald has represented in the Dáil, keeping the terms separate and listing the member names.",
        "Frances Fitzgerald", None,
    ),
    (
        "List every constituency Frances Fitzgerald has represented in the Dáil during 2014, keeping the terms separate.",
        "Frances Fitzgerald", None,
    ),
    (
        "List every constituency Frances Fitzgerald has represented in the Dáil, keeping the terms separate, and was she a woman?",
        "Frances Fitzgerald", None,
    ),
])
def test_added_person_output_gender_and_calendar_conditions_remain_unconsumed(
    question, member, selector,
):
    with pytest.raises(ValueError):
        validate_composable_plan_draft(
            build_constituency_representation_draft(member, selector), question=question,
        )


@pytest.mark.parametrize("question", [
    "Which constituency did Micheál Martin represent in his latest recorded Dáil term, and what office did he hold?",
    "Which constituency did Micheál Martin represent in his latest recorded Dáil term, and was he a man?",
    "Which constituency did Micheál Martin represent in his latest recorded Dáil term, and what was his age?",
])
def test_representation_guard_rejects_legacy_accepted_office_gender_and_biography_clauses(question):
    draft = build_constituency_representation_draft(MEMBER_A, "latestRecorded")
    _legacy_validator_rejects(draft, question)

    with pytest.raises(ValueError, match="constituency_representation intent"):
        validate_constituency_representation_intent(
            question, member=MEMBER_A, selector="latestRecorded",
        )


@pytest.mark.parametrize("question", [
    "Which constituency did Micheál Martin represent in his latest recorded Dáil term on 1 January 2020?",
    "Which constituency did Micheál Martin represent in his latest recorded Dáil term for Fine Gael?",
    "Which constituency did Micheál Martin represent in his latest recorded Dáil term, and which Bills did he sponsor?",
])
def test_representation_guard_rejects_date_party_and_second_projection(question):
    # These are outside the representation contract even when the proposed
    # graph keeps its complete four-edge evidence path and answer declaration.
    _legacy_validator_rejects(build_constituency_representation_draft(MEMBER_A, "latestRecorded"), question)
    with pytest.raises(ValueError, match="constituency_representation intent"):
        validate_constituency_representation_intent(
            question, member=MEMBER_A, selector="latestRecorded",
        )


@pytest.mark.parametrize(("question", "selector"), [
    ("Who are the TDs for Waterford?", "currentTerm"),
    ("Which deputies represent Waterford?", "currentTerm"),
    ("Name Waterford's current deputies.", "currentTerm"),
])
def test_legacy_current_named_constituency_roster_remains_supported(question, selector):
    draft = _representation_draft(constituency="Waterford", selector=selector)
    _legacy_validator_accepts(draft, question)
    validate_constituency_representation_intent(
        question, constituency="Waterford", selector=selector,
    )


def test_named_constituency_past_roster_cannot_be_reinterpreted_as_current():
    with pytest.raises(ValueError, match="explicitly current or present-tense"):
        validate_constituency_representation_intent(
            "Who were the TDs for Waterford?",
            constituency="Waterford", selector="currentTerm",
        )


@pytest.mark.parametrize("question", [
    "Who are the TDs for Waterford, and who is the Taoiseach?",
    "Who are the TDs for Waterford, excluding women?",
    "Who are the TDs for Waterford on 1 January 2020?",
])
def test_named_constituency_guard_rejects_added_office_gender_and_date_clauses(question):
    _legacy_validator_rejects(
        _representation_draft(constituency="Waterford", selector="currentTerm"), question,
    )
    with pytest.raises(ValueError, match="constituency_representation intent"):
        validate_constituency_representation_intent(
            question, constituency="Waterford", selector="currentTerm",
        )


@pytest.mark.parametrize(("question", "selector"), [
    ("What constituencies did Bertie Ahern represent?", "currentTerm"),
    ("What constituency does Bertie Ahern represent?", None),
    ("Which constituency did Bertie Ahern represent in his latest recorded Dáil term?", None),
    ("Which constituency did Bertie Ahern represent in his latest recorded Dáil term?", "currentTerm"),
    ("What constituency did Bertie Ahern represent in the 32nd Dáil?", None),
])
def test_representation_guard_requires_selector_and_original_scope_to_agree(question, selector):
    with pytest.raises(ValueError, match="constituency_representation intent"):
        validate_constituency_representation_intent(
            question, member="Bertie Ahern", selector=selector,
        )


def test_guards_require_grounded_distinct_mentions_and_leave_no_normalized_text_for_resolution():
    with pytest.raises(ValueError, match="exact member_b mention"):
        validate_shared_dail_terms_intent(
            "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?",
            "Micheál Martin", "Absent Member",
        )
    with pytest.raises(ValueError, match="distinct people"):
        validate_shared_dail_terms_intent(
            "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?",
            "Micheál Martin", "Micheál Martin",
        )
    with pytest.raises(ValueError, match="exactly one Member or constituency"):
        validate_constituency_representation_intent(
            "What constituencies did Bertie Ahern represent?",
            member="Bertie Ahern", constituency="Waterford", selector=None,
        )
    with pytest.raises(ValueError, match="one Member or constituency"):
        validate_constituency_representation_intent(
            "What constituencies did Bertie Ahern represent?",
            selector=None,
        )
    with pytest.raises(ValueError, match="reserved structural marker"):
        validate_shared_dail_terms_intent(
            "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in with a targetcomponent note?",
            MEMBER_A, MEMBER_B,
        )


def test_intent_guards_are_independent_of_planner_instructions_or_graph_metadata():
    # Guard inputs are only the original text and already-validated semantic
    # slots; no draft content or normalized question is accepted as authority.
    question = "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?"
    draft = build_shared_dail_terms_draft(MEMBER_A, MEMBER_B)
    before = copy.deepcopy(draft)
    before_question = question
    validate_shared_dail_terms_intent(question, MEMBER_A, MEMBER_B)
    assert draft == before
    assert question == before_question


def _selection(capability, parameters):
    return {
        "version": 2, "supported": True, "family": "capability_selection",
        "unsupportedReason": None, "intent": "Select an existing graph capability.",
        "referents": {"capability": capability, "parameters": parameters},
        "relations": [], "constraints": [], "answer": None,
    }


def test_constructed_graph_capabilities_match_legacy_graph_validation_for_real_wording():
    shared_question = "Show the Dáil terms common to the service records of Dick Spring and Brendan Howlin."
    shared, unsupported = validate_composable_plan_draft(
        _selection("shared_dail_terms_graph", {"memberA": "Dick Spring", "memberB": "Brendan Howlin"}),
        question=shared_question,
    )
    legacy_shared, legacy_unsupported = validate_composable_plan_draft(
        build_shared_dail_terms_draft("Dick Spring", "Brendan Howlin"), question=shared_question,
    )
    assert unsupported is legacy_unsupported is None
    assert shared == legacy_shared

    anchor_question = "Count the other deputies who shared Róisín Shortall’s constituency in Dáil 31."
    anchored, unsupported = validate_composable_plan_draft(
        _selection("anchored_shared_constituency_graph", {"anchor": "Róisín Shortall"}),
        question=anchor_question,
    )
    legacy_anchored, legacy_unsupported = validate_composable_plan_draft(
        build_anchored_shared_constituency_draft(
            "Róisín Shortall", {"kind": "termNumber", "number": 31}, count=True,
        ),
        question=anchor_question,
    )
    assert unsupported is legacy_unsupported is None
    assert anchored == legacy_anchored
    assert anchored["answer"]["kind"] == "count"
    assert anchored["referents"]["term"]["selector"] == {"kind": "termNumber", "number": 31}


def test_same_constituency_capability_passes_the_early_gate_for_exact_r24_wording():
    question = (
        "How many other TDs were in the same constituency as Mary Lou McDonald "
        "during the last Dáil?"
    )
    selected, unsupported = validate_composable_plan_draft(
        _selection(
            "anchored_shared_constituency_graph", {"anchor": "Mary Lou McDonald"},
        ),
        question=question,
    )

    assert unsupported is None
    assert selected["answer"]["kind"] == "count"
    assert selected["referents"]["anchorMember"]["mention"] == "Mary Lou McDonald"
    assert selected["referents"]["term"]["selector"] == {
        "kind": "previousTerm", "house": "Dail",
    }


def test_same_constituency_early_gate_still_rejects_unrelated_capabilities():
    question = "Who were the other TDs in the same constituency as Aoife Byrne during the last Dáil?"
    with pytest.raises(ValueError, match="independent Member/shared-constituency operator is absent"):
        validate_composable_plan_draft(
            _selection("member_lookup", {"member": "Aoife Byrne", "house": "Dail"}),
            question=question,
        )


def test_who_else_possessive_anchor_and_previous_term_are_consumed_without_name_rewriting():
    question = "Who else shared Willie O'Dea’s constituency in the previous Dáil?"
    selected, unsupported = validate_composable_plan_draft(
        _selection("anchored_shared_constituency_graph", {"anchor": "Willie O'Dea"}),
        question=question,
    )
    assert unsupported is None
    assert selected["referents"]["anchorMember"]["mention"] == "Willie O'Dea"
    assert selected["referents"]["term"]["selector"] == {"kind": "previousTerm", "house": "Dail"}


def test_constructed_anchored_graph_capability_matches_legacy_fixture_execution():
    from test_nlq_bounded_composition import anchor_fixture, execute

    question = "Who else shared Bertie Ahern’s constituency in Dáil 34?"
    selection = _selection(
        "anchored_shared_constituency_graph", {"anchor": "Bertie Ahern"},
    )
    constructed = execute(anchor_fixture()[0], selection, question)
    legacy = execute(
        anchor_fixture()[0],
        build_anchored_shared_constituency_draft(
            "Bertie Ahern", {"kind": "termNumber", "number": 34},
        ),
        question,
    )

    assert constructed.status == legacy.status == "success"
    assert constructed.result == legacy.result
    assert constructed.sparql == legacy.sparql
    assert {row[0] for row in constructed.result.rows} == {"Recorded Colleague", "Later Colleague"}


def test_rejected_constructed_graph_capabilities_do_not_resolve_or_execute_a_replacement():
    from test_nlq_bounded_composition import anchor_fixture, execute
    from test_nlq_composable_shared_dail_terms import SharedDailTermsFixture, _run

    shared_fixture = SharedDailTermsFixture()
    shared_question = (
        "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in, "
        "and how many Members served in them?"
    )
    shared_outcome, shared_generator = _run(
        shared_fixture,
        question=shared_question,
        draft=_selection(
            "shared_dail_terms_graph",
            {"memberA": "Micheál Martin", "memberB": "Mary Lou McDonald"},
        ),
    )
    assert shared_outcome.status == "unsupported_request"
    assert shared_outcome.result is None and shared_outcome.sparql is None
    assert not shared_fixture.queries
    assert shared_generator.closed

    anchor_question = "Who else shared Bertie Ahern’s constituency in Dáil 34 and list their ages?"
    anchor_fixture_data = anchor_fixture()[0]
    anchor_outcome = execute(
        anchor_fixture_data,
        _selection("anchored_shared_constituency_graph", {"anchor": "Bertie Ahern"}),
        anchor_question,
    )
    assert anchor_outcome.status == "unsupported_request"
    assert anchor_outcome.result is None and anchor_outcome.sparql is None
    assert not anchor_fixture_data.queries


@pytest.mark.parametrize(("question", "capability", "parameters"), [
    (
        "Show the Dáil terms common to Dick Spring and Brendan Howlin while in office.",
        "shared_dail_terms_graph", {"memberA": "Dick Spring", "memberB": "Brendan Howlin"},
    ),
    (
        "Show the Dáil terms common to Dick Spring and Brendan Howlin.",
        "shared_dail_terms_graph", {"memberA": "Dick Spring", "memberB": "Missing Member"},
    ),
    (
        "Count the other deputies who shared Róisín Shortall’s constituency in Dáil 31 and list their ages.",
        "anchored_shared_constituency_graph", {"anchor": "Róisín Shortall"},
    ),
    (
        "Who else shared Róisín Shortall’s constituency in Dáil 31 and during 2020?",
        "anchored_shared_constituency_graph", {"anchor": "Róisín Shortall"},
    ),
    (
        "Who else shared Róisín Shortall’s constituency in Dáil 31?",
        "anchored_shared_constituency_graph", {"anchor": "Absent person"},
    ),
    (
        "Who else shared Bertie Ahern’s constituency in Dáil 34 while he was Taoiseach?",
        "anchored_shared_constituency_graph", {"anchor": "Bertie Ahern"},
    ),
    (
        "Who else shared Bertie Ahern’s constituency on 14 June 2007?",
        "anchored_shared_constituency_graph", {"anchor": "Bertie Ahern"},
    ),
])
def test_constructed_graph_capabilities_reject_dropped_intent_or_ungrounded_slots(question, capability, parameters):
    with pytest.raises(ValueError):
        validate_composable_plan_draft(_selection(capability, parameters), question=question)
