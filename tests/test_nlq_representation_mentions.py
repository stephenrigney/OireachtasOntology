"""Current-point modifiers are scope, never part of an exact entity label."""

from datetime import date

import pytest

from poc.nlq.representation import plan_representation_question


@pytest.mark.parametrize("constituency", ["Louth", "Kerry North", "Dún Laoghaire"])
@pytest.mark.parametrize("scope", ["today", "right now", "currently", "as of today", "as of now"])
def test_current_point_is_outside_constituency_mention(constituency, scope):
    as_of = date(2026, 11, 6)
    plan = plan_representation_question(f"Who are the TDs for {constituency} {scope}?", as_of=as_of)
    assert plan["referents"]["constituency"]["mention"] == constituency
    assert plan["referents"]["constituency"]["resolution"] == "unresolved"
    assert plan["referents"]["term"]["selector"] == {"kind": "currentTerm", "house": "Dail"}
    assert plan["asOf"] == as_of.isoformat()


@pytest.mark.parametrize("tail", ["today in the current Dáil", "in the present Dáil today"])
def test_current_term_and_point_are_not_entity_text(tail):
    plan = plan_representation_question(f"Who are the TDs for Clare {tail}?", as_of=date(2026, 11, 6))
    assert plan["referents"]["constituency"]["mention"] == "Clare"


@pytest.mark.parametrize("extra", ["today and their ages", "before 2020", "excluding women", "tomorrow"])
def test_extraction_does_not_discard_unsupported_qualifiers(extra):
    plan = plan_representation_question(f"Who are the TDs for Clare {extra}?", as_of=date(2026, 11, 6))
    # Unknown text is retained for exact resolution, not silently removed to
    # produce an easier Clare query. Whole-intent gates may refuse it earlier.
    assert plan["referents"]["constituency"]["mention"] == f"Clare {extra}"


def test_today_executes_same_active_selection_and_retains_identity_failures():
    from test_nlq_question_failures import SourceFixture, WATERFORD, run

    fixture = SourceFixture()
    fixture.add_representation("Synthetic-Ended", "Synthetic Ended", 34,
                               "2024-11-29", "2026-01-01", "Waterford")
    actual = run(fixture, "Who are the TDs for Waterford today?")
    assert actual.status == "success", actual.diagnostic
    assert {row[0] for row in actual.result.rows} == WATERFORD
    assert actual.plan["referents"]["constituency"]["mention"] == "Waterford"
    unknown = run(fixture, "Who are the TDs for Invented Constituency today?")
    assert unknown.result is None
    assert unknown.status == "not_found"
