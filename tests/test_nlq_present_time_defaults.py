"""Shared time classification never replaces family completeness/evidence guards."""

import copy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from poc.nlq.interpretation import current_relationship_scope, current_scope_explanation
from poc.nlq.composable_plan import validate_plan, PlanError
from poc.nlq.composable_semantic_planner import validate_composable_plan_draft, complete_v2_plan
from test_nlq_seanad_party_periods import (
    ROOT, AS_OF, _dail_party_fixture, _dail_draft, _run_dail, FixedPlanGenerator,
)


@pytest.mark.parametrize("question,mentions,expected", [
    ("Who are the Fianna Fáil TDs?", ("Fianna Fáil",), "inferred"),
    ("Who are the Labour Senators?", ("Labour",), "inferred"),
    ("Who are the TDs representing Dublin Central?", ("Dublin Central",), "inferred"),
    ("Which members serve on the Committee of Public Accounts?", ("Committee of Public Accounts",), "inferred"),
    ("List the members of the Committee of Public Accounts.", ("Committee of Public Accounts",), "inferred"),
    ("Who is the Tánaiste?", ("Tánaiste",), "inferred"),
    ("What constituency does the Tánaiste represent?", ("Tánaiste",), "inferred"),
    ("Who are the current Fianna Fáil TDs?", ("Fianna Fáil",), "explicit"),
    ("Who is the Tánaiste as of today?", ("Tánaiste",), "explicit"),
    ("Who were the Fine Gael TDs in the 33rd Dáil?", ("Fine Gael",), None),
    ("Who served on the Committee of Public Accounts in 2022?", ("Committee of Public Accounts",), None),
    ("Who are the Fine Gael TDs on 2026-01-01?", ("Fine Gael",), None),
    ("Who are not Fine Gael TDs?", ("Fine Gael",), None),
    ("Who are the Fine Gael TDs, excluding former ministers?", ("Fine Gael",), None),
    ("Who are the Fine Gael TDs who were previously Senators?", ("Fine Gael",), None),
    ("Who are the current Fine Gael TDs before 2020?", ("Fine Gael",), None),
    ("Who is the latest recorded Taoiseach?", ("Taoiseach",), None),
    ("Who will be the Taoiseach?", ("Taoiseach",), None),
])
def test_shared_time_scope(question, mentions, expected):
    assert current_relationship_scope(question, *mentions) == expected


@pytest.mark.parametrize("party", ["Fine Gael", "Fianna Fáil"])
def test_inferred_dail_selection_equals_explicit_and_preserves_both_intervals(party):
    fixture, _ = _dail_party_fixture()
    inferred = _run_dail(f"Who are the {party} TDs?", fixture, party=party)
    explicit = _run_dail(f"Who are the current {party} TDs?", fixture, party=party)
    assert inferred.status == explicit.status == "success"
    assert inferred.result.rows == explicit.result.rows
    assert len(inferred.result.rows) == 1
    count = _run_dail(f"How many {party} Deputies are there?", fixture, party=party, count=True)
    assert count.status == "success"
    assert count.result.rows == (("1",),)
    assert inferred.plan["interpretation"]["question"] == f"Who are the {party} TDs?"
    assert inferred.plan["interpretation"]["date"] == AS_OF.isoformat()
    assert "interpretation" not in explicit.plan


@pytest.mark.parametrize("question", [
    "Who were the Fine Gael TDs?",
    "Who are not the Fine Gael TDs?",
    "Who are the Fine Gael TDs on 2020-01-01?",
    "Who are the Fine Gael TDs who sit on a committee?",
    "Who are the Fine Gael TDs and their ages?",
    "Who are the Fine Gael TDs except former ministers?",
    "Who are the Fine Gael TDs who will serve next year?",
    "Who are the Fine Gael TDs in the 33rd Dáil?",
])
def test_forced_current_draft_cannot_default_away_other_scope(question):
    with pytest.raises(ValueError):
        validate_composable_plan_draft(_dail_draft(), question=question)


def test_default_evidence_is_revalidated_not_a_model_assertion():
    question = "Who are the Fine Gael TDs?"
    draft, _ = validate_composable_plan_draft(_dail_draft(), question=question)
    plan = complete_v2_plan(draft, as_of=AS_OF)
    validate_plan(plan)
    for key, value in (("date", "2020-01-01"), ("question", "Who were the Fine Gael TDs?"), ("policy", "made_up")):
        altered = copy.deepcopy(plan)
        altered["interpretation"][key] = value
        with pytest.raises(PlanError):
            validate_plan(altered)


@pytest.mark.parametrize("explicit", [False, True])
def test_ask_explains_inferred_vs_explicit_time(monkeypatch, explicit):
    from poc.nlq import app as app_module
    fixture, _ = _dail_party_fixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **k: fixture)
    question = "Who are the current Fine Gael TDs?" if explicit else "Who are the Fine Gael TDs?"
    response = TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: FixedPlanGenerator(_dail_draft()),
    )).post("/ask", data={"question": question})
    assert 'data-outcome="answer"' in response.text
    assert ("Explicit current-time request" if explicit else "Present-time default applied") in response.text


def test_term_wide_and_latest_are_not_explained_as_current_point():
    for family, selector in (("constituency_representation", {"kind": "latestRecorded"}),
                             ("member_relationship_composition", {"kind": "currentTerm", "house": "Dail"})):
        assert current_scope_explanation("Who are the TDs?", {"family": family, "referents": {"term": {"selector": selector}}}, date(2026, 11, 10)) is None


@pytest.mark.parametrize("place", ["Dublin Central", "Mayo"])
def test_representation_connector_is_not_captured_as_part_of_identity(place):
    from poc.nlq.representation import plan_representation_question
    plain = plan_representation_question(f"Who are the TDs for {place}?", as_of=AS_OF)
    representing = plan_representation_question(f"Who are the TDs representing {place}?", as_of=AS_OF)
    assert representing["referents"] == plain["referents"]
    assert representing["referents"]["constituency"]["mention"] == place
    assert representing["interpretation"]["date"] == AS_OF.isoformat()
    explicit = plan_representation_question(f"Who are the current TDs for {place}?", as_of=AS_OF)
    assert 'interpretation' not in explicit


def test_current_office_scope_cannot_consume_negation_as_an_office_name():
    from poc.nlq.interpretation import current_office_point_request
    assert not current_office_point_request("Who is not the Tánaiste?")


def test_named_member_present_party_uses_existing_current_status_not_career_history():
    from poc.nlq.stage_a import parse_stage_a_question
    from test_nlq_question_failures import draft_for
    for question in ("What party does Stephen Donnelly belong to?", "Which party does Stephen Donnelly belong to now?"):
        request = parse_stage_a_question(question)
        assert request.family == "current_collection"
        assert request.mention == "Stephen Donnelly"
    draft = draft_for("What parties was Stephen Donnelly a member of?", "member_party_history")
    with pytest.raises(ValueError, match="career-wide party history"):
        validate_composable_plan_draft(draft, question="What party does Stephen Donnelly belong to?")
    admitted, error = validate_composable_plan_draft(draft, question="List the political parties Stephen Donnelly belonged to.")
    assert admitted is not None and error is None


@pytest.mark.parametrize('question', [
    'Who are the Senators who previously served as TDs?',
    'Which Senators previously served in the Dáil?',
    'Who are the Senators who were previously Deputies?',
])
def test_scoped_prior_service_keeps_past_dail_path_and_current_senator_default(question):
    from test_nlq_composable_current_house_membership import CurrentHouseFixture, _q20_draft, _run, Q20, DAIL_TERM_33
    fixture = CurrentHouseFixture(members=[])
    fixture.add_member({'slug': 'Prior-Service-Default', 'name': 'Prior Service Default',
                        'seanad': ('2025-06-12T00:00:00', None),
                        'dail_paths': [(DAIL_TERM_33, ('2020-02-08T00:00:00', '2024-11-08T23:59:59'))]})
    inferred, _ = _run(question, _q20_draft(), fixture)
    explicit, _ = _run(Q20, _q20_draft(), fixture)
    assert inferred.status == explicit.status == 'success'
    assert inferred.result.rows == explicit.result.rows
    assert inferred.plan['referents']['dail_term'] == {'type': 'DailTerm'}
    counted, _ = _run('How many Senators previously served in the Dáil?', _q20_draft(count=True), fixture)
    assert counted.status == 'success' and counted.result.rows == (('1',),)
    assert 'Present-time default applied' in current_scope_explanation(question, inferred.plan, AS_OF)
    assert 'Explicit current-time request' in current_scope_explanation(Q20, explicit.plan, AS_OF)


@pytest.mark.parametrize('question', [
    'Who were the Senators who previously served as TDs?',
    'Which Senators previously served in the Dáil in 2022?',
    'Which Senators never previously served in the Dáil?',
    'Which Senators previously served in the Dáil and sat on a committee?',
    'Which Senators previously served in the Dáil and how old are they?',
    'Which Senators previously served in the Dáil except former ministers?',
])
def test_prior_service_default_cannot_erase_temporal_paths_or_extra_conditions(question):
    from test_nlq_composable_current_house_membership import _q20_draft
    with pytest.raises(ValueError):
        validate_composable_plan_draft(_q20_draft(), question=question)
