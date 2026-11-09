"""Helper-level acceptance for fail-closed membership-intent preservation."""

import pytest

from poc.nlq.membership_intent import (
    unsupported_current_cross_house_membership_intent,
    unsupported_current_seanad_party_membership_intent,
    unsupported_current_seanad_prior_dail_intent,
)


@pytest.mark.parametrize(
    "question,count",
    [
        ("What current Senators previously served in the Dáil?", False),
        ("How many current Senators previously served in the Dáil?", True),
        ("Which present Senators have a recorded earlier Dáil membership?", False),
        ("How many present Senators have a recorded earlier Dáil membership?", True),
        (
            "Which Senators in the current Seanad have a Dáil membership that ended before "
            "their Seanad membership began?",
            False,
        ),
        (
            "How many Senators in the current Seanad have a Dáil membership that ended before "
            "their Seanad membership began?",
            True,
        ),
        ("How many currently serving Senators have prior recorded Dáil service?", True),
        ("Which currently serving Senators have prior recorded Dáil service?", False),
    ],
)
def test_prior_dail_guard_preserves_existing_positive_synonyms_and_count_list_pairing(question, count):
    assert unsupported_current_seanad_prior_dail_intent(question, count=count) is None


@pytest.mark.parametrize(
    "question",
    [
        "Which current Senators never previously served in the Dáil?",
        "Which female current Senators previously served in the Dáil?",
        "Which current Senators previously served in the Dáil and list their ages?",
        "Which current Senators previously served in the Dáil for more than ten years?",
        "Which current Senators born in 1980 previously served in the Dáil?",
        "Which current Senators married before 2020 previously served in the Dáil?",
        "Which current Senators previously served in the Dáil or Seanad?",
        "Which current Senators previously served in the Dáil during 2020?",
        "Which current Senators were elected in 2025 and previously served in the Dáil?",
        "Which current Senators previously served in the current Dáil?",
        "How many prior Dáil terms did current Senators serve?",
    ],
)
def test_prior_dail_guard_rejects_negation_and_unconsumed_filters_or_outputs(question):
    assert unsupported_current_seanad_prior_dail_intent(question, count=question.startswith("How many"))


def test_prior_dail_guard_rejects_count_list_polarity_mismatch():
    assert "count/list" in unsupported_current_seanad_prior_dail_intent(
        "Which current Senators previously served in the Dáil?", count=True,
    )
    assert "count/list" in unsupported_current_seanad_prior_dail_intent(
        "How many current Senators previously served in the Dáil?", count=False,
    )


@pytest.mark.parametrize(
    "question,count",
    [
        ("How many Fine Gael Senators are in the current Seanad?", True),
        ("Which Fine Gael Senators are in the current Seanad?", False),
        ("How many Fine Gael Senators in the current Seanad?", True),
        ("Which Fine Gael Senators in the current Seanad?", False),
    ],
)
def test_named_party_guard_preserves_current_seanad_count_and_list_wording(question, count):
    assert unsupported_current_seanad_party_membership_intent(
        question, party_mention="Fine Gael", count=count,
    ) is None


@pytest.mark.parametrize(
    "question,count",
    [
        ("How many Fine Gael Senators are not members of the current Seanad?", True),
        ("Which Fine Gael Senators never belonged to the current Seanad?", False),
        ("Which female Fine Gael Senators are in the current Seanad?", False),
        ("Which Fine Gael Senators are in the current Seanad and list their ages?", False),
        ("How many Fine Gael Senators elected in 2025 are in the current Seanad?", True),
        ("Which Fine Gael Senators in current Seanad or Dáil?", False),
    ],
)
def test_named_party_guard_rejects_negative_or_extra_membership_intent(question, count):
    assert unsupported_current_seanad_party_membership_intent(
        question, party_mention="Fine Gael", count=count,
    )


def test_named_party_guard_requires_exact_grounded_party_and_matching_count_list_mode():
    assert "exact mention" in unsupported_current_seanad_party_membership_intent(
        "How many Fianna Fáil Senators are in the current Seanad?",
        party_mention="Fine Gael",
        count=True,
    )
    assert "count/list" in unsupported_current_seanad_party_membership_intent(
        "Which Fine Gael Senators are in the current Seanad?",
        party_mention="Fine Gael",
        count=True,
    )
    assert "count/list" in unsupported_current_seanad_party_membership_intent(
        "How many Fine Gael Senators are in the current Seanad?",
        party_mention="Fine Gael",
        count=False,
    )


@pytest.mark.parametrize(
    "question",
    [
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil?",
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil, "
        "even if the periods did not overlap?",
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil; the periods need not overlap.",
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil, "
        "even if their membership periods don't overlap?",
    ],
)
def test_current_cross_house_guard_accepts_term_wide_membership_and_optional_nonoverlap_disclaimers(question):
    assert unsupported_current_cross_house_membership_intent(question, count=False) is None


@pytest.mark.parametrize(
    "question",
    [
        "Who simultaneously served as a Senator in the current Seanad and a Deputy in the current Dáil?",
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil whose periods did not overlap?",
        "Which current female Senators were Deputies in the current Dáil?",
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil during 2020?",
        "Which current Senators were elected in 2025 and are Deputies in the current Dáil?",
        "Who was a Senator in the current Seanad or a Deputy in the current Dáil?",
        "Which former Senators were in the current Seanad and are Deputies in the current Dáil?",
    ],
)
def test_current_cross_house_guard_rejects_conditions_outputs_and_negation(question):
    assert unsupported_current_cross_house_membership_intent(question, count=False)


def test_current_cross_house_guard_keeps_count_and_list_polarity_symmetric():
    assert "count/list" in unsupported_current_cross_house_membership_intent(
        "Who was a Senator in the current Seanad and a Deputy in the current Dáil?", count=True,
    )
    assert "count/list" in unsupported_current_cross_house_membership_intent(
        "How many Senators were in both current Houses?", count=False,
    )
