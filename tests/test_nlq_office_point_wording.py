"""Present office-holding verbs select the same bounded current-point scope."""

import pytest

from poc.nlq.interpretation import current_office_point_mention


@pytest.mark.parametrize("office", ["Taoiseach", "Tánaiste", "Minister for Finance"])
@pytest.mark.parametrize("form", ["Who holds the office of {} now?", "Who currently holds the office of {}?", "Who holds {} today?", "Who is the {}?"])
def test_present_office_mention_is_exact(office, form):
    assert current_office_point_mention(form.format(office)) == office


@pytest.mark.parametrize("question", [
    "Who held the office of Taoiseach?",
    "Who holds the office of Taoiseach during 2022?",
    "Who holds the office of Minister for Finance and belongs to Fine Gael?",
    "Who holds the office of Tánaiste while representing Clare?",
    "Who holds the office of Taoiseach in 2028?",
])
def test_present_verb_never_erases_other_scope(question):
    assert current_office_point_mention(question) is None
    from poc.nlq.composable_semantic_planner import InvalidComposableDraft, UnsupportedComposableRequest, validate_composable_plan_draft
    from test_nlq_bounded_composition import _selection

    office = "Minister for Finance" if "Minister for Finance" in question else "Tánaiste" if "Tánaiste" in question else "Taoiseach"
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(_selection("office_holding_window", {"office": office}), question=question)


def test_holds_uses_local_asof_not_planner_date_or_past_holding():
    from test_nlq_bounded_composition import AS_OF, _selection, anchor_fixture, execute

    fixture, *_ = anchor_fixture(holding_interval=("2025-01-23T00:00:00", None), anchor_name="Micheál Martin")
    draft = _selection("office_holding_window", {"office": "Taoiseach"})
    actual = execute(fixture, draft, "Who holds the office of Taoiseach now?")
    assert actual.status == "success", actual.diagnostic
    assert actual.plan["constraints"][0]["value"]["start"] == AS_OF.isoformat()
    assert actual.plan["constraints"][0]["value"]["end"] == AS_OF.isoformat()
    assert actual.result.rows == (("Micheál Martin", "2025-01-23", "Open-ended (no end date recorded)"),)
    ended, *_ = anchor_fixture(holding_interval=("2021-01-01T00:00:00", "2022-01-01T00:00:00"), anchor_name="Micheál Martin")
    no_holder = execute(ended, draft, "Who holds the office of Taoiseach now?")
    assert no_holder.result is None
    assert "no conclusion that the office has no holder" in no_holder.diagnostic
