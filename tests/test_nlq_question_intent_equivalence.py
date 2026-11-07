import pytest

from poc.nlq.question_intent import (
    is_numeric_measure_request,
    member_measure_scope,
    numbered_dail_terms,
    relationship_wording,
    requested_measures,
    semantic_residual,
    without_optional_overlap_clause,
)


def test_excluded_seat_measure_is_not_an_affirmative_seat_request():
    scope = member_measure_scope("Count distinct Labour Party Members in Dáil 31, rather than seats.")
    assert scope.excluded == {"seats"}
    assert "seats" not in scope.positive_text
    assert "Dáil 31" in scope.positive_text


@pytest.mark.parametrize("question", [
    "Count seats rather than Members.",
    "Count Labour Party Members rather than seats for women.",
    "List seats rather than people.",
])
def test_measure_equivalence_does_not_erase_other_intent(question):
    assert member_measure_scope(question).positive_text == question


def test_affirmative_seat_request_is_retained_alongside_exclusion():
    scope = member_measure_scope("Count Members and seats, rather than seats.")
    assert "and seats" in scope.positive_text


def test_whole_intent_guard_distinguishes_requested_and_excluded_seats():
    from poc.nlq.interpretation import unsupported_whole_intent

    assert unsupported_whole_intent("Count distinct Labour Party Members in Dáil 31, rather than seats.") is None
    assert "Seat allocations" in unsupported_whole_intent("How many seats did TDs hold in Dáil 31?")
    assert "Seat allocations" in unsupported_whole_intent("Count TDs and seats, rather than seats.")


@pytest.mark.parametrize("clause", ["even if the periods did not overlap", "the periods need not overlap", "even if their membership periods don't overlap"])
def test_optional_overlap_disclaimer_is_not_a_nonoverlap_filter(clause):
    text = without_optional_overlap_clause(f"Members in both current terms, {clause}.")
    assert "overlap" not in text
    assert "both current terms" in text


@pytest.mark.parametrize("question", [
    "Members whose periods did not overlap.",
    "Members only if their periods did not overlap.",
    "Members whose periods must overlap.",
    "Members even if their periods did not overlap before 2020.",
])
def test_actual_temporal_conditions_are_not_disclaimers(question):
    assert without_optional_overlap_clause(question) == question


def test_simultaneity_elsewhere_remains_a_constraint():
    text = without_optional_overlap_clause("Members serving simultaneously, even if the periods did not overlap.")
    assert "simultaneously" in text


def test_grounded_name_is_preserved_and_only_its_possessive_consumed():
    question = "Who else shared Willie O'Dea’s constituency in Dáil 31?"
    text = relationship_wording(question, mentions=["Willie O'Dea"])
    assert text == "who other shared Willie O'Dea constituency in Dáil 31?"
    assert "Someone’s" in relationship_wording("Someone’s constituency", mentions=[])


def test_role_normalization_does_not_touch_mentioned_entity_text():
    assert relationship_wording("List representatives for Representatives Bay.", mentions=["Representatives Bay"]) == "List members for Representatives Bay."


@pytest.mark.parametrize(("question", "expected"), [
    ("Dáil number 24", [24]),
    ("Dáil 24", [24]),
    ("24th Dáil", [24]),
    ("What was the seat complement of the 28th Dáil term?", [28]),
    ("Which Members served in both the 32nd and 33rd Dáil?", [32, 33]),
    ("Which Members served in both the 32nd and 33rd Dáil terms?", [32, 33]),
    ("Which Members served in both the 32nd and 33rd terms of Dáil service?", [32, 33]),
    ("Which Dáil term or terms were in existence on 1 September 1997?", []),
])
def test_numbered_dail_slots_are_shared_without_date_or_nested_ordinal_noise(question, expected):
    assert [item.number for item in numbered_dail_terms(question)] == expected


@pytest.mark.parametrize("question", [
    "Dáil 24rd",
    "Dáil number 1000",
    "Dáil number twenty-four",
])
def test_malformed_numbered_dail_scopes_fail_closed(question):
    with pytest.raises(ValueError):
        numbered_dail_terms(question)


def test_conflicting_numbered_dail_scopes_remain_two_explicit_slots():
    assert [item.number for item in numbered_dail_terms("List parties for Dáil 30 and the 31st Dáil.")] == [30, 31]


def test_requested_measure_extraction_distinguishes_groups_exclusion_and_member_counts():
    excluded_groups = requested_measures(
        "List the parliamentary parties recorded for Dáil 30; I am not asking for groups."
    )
    assert excluded_groups.requested == {"parties"}
    assert excluded_groups.excluded == {"groups"}
    assert "groups" not in excluded_groups.requested

    included_groups = requested_measures("List the parties and groups in the 34th Dáil.")
    assert included_groups.requested == {"parties", "groups"}

    people = requested_measures("How many distinct Members served in the 33rd Dáil?")
    assert "members" in people.requested and "seats" not in people.requested
    assert is_numeric_measure_request("What was the seat complement of the 28th Dáil?")

    mixed = requested_measures("Give the seats and distinct Members for Clare in Dáil 33.")
    assert mixed.requested == {"members", "seats"}
    assert mixed.conflicts == frozenset()


@pytest.mark.parametrize(("question", "consumed", "expected"), [
    ("What is not the seat complement?", (r"\bwhat\b", r"\bis\b", r"\bseat\s+complement\b"), ("not",)),
    ("List parties and people", (r"\blist\b", r"\bparties\b", r"\bpeople\b"), ("and",)),
    ("List parties or groups", (r"\blist\b", r"\bparties\b", r"\bgroups\b"), ("or",)),
])
def test_semantic_residual_does_not_ignore_polarity_or_unapproved_composition(question, consumed, expected):
    assert semantic_residual(question, consumed_patterns=consumed) == expected


def test_empty_mention_cannot_mask_unrelated_question_text():
    with pytest.raises(ValueError):
        relationship_wording("Only the women", mentions=[""])
