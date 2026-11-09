"""Latest-recorded projection reuses the complete accepted office episode reader."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from poc.nlq.composable_plan import execute_question
from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft, UnsupportedComposableRequest,
    validate_composable_plan_draft, load_composable_draft_schema,
)
from poc.nlq.vocabulary import supported_predicates
from test_nlq_composable_office_evidence import (
    OfficeEvidenceFixture, FixedPlanGenerator, _selection, ROOT, TAOISEACH, FINANCE_MINISTER,
)

AS_OF = date(2026, 11, 9)
QUESTION = 'When was Simon Harris last Taoiseach?'
OLD = {'start': '2024-04-09T00:00:00', 'end': '2024-11-08T00:00:00'}
LATEST = {'start': '2024-11-29T00:00:00', 'end': '2025-01-22T00:00:00'}


def _draft(*, latest=True, member='Simon Harris', office='Taoiseach'):
    draft = _selection(member, office)
    if latest:
        draft['referents']['parameters']['selection'] = 'latestRecorded'
    return draft


def _run(fixture, question=QUESTION, **kwargs):
    return execute_question(question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / 'ontology'),
        semantic_plan_generator_factory=lambda: FixedPlanGenerator(_draft(**kwargs)))


@pytest.mark.parametrize('question', [
    QUESTION,
    'When did Simon Harris last serve as Taoiseach?',
    'When was Simon Harris most recently Taoiseach?',
    'When did Simon Harris most recently serve as the Taoiseach?',
    'During what period was Simon Harris last Taoiseach?',
])
def test_latest_recorded_selects_one_episode_not_a_merged_tenure(question):
    fixture = OfficeEvidenceFixture()
    member = fixture.add_member('harris', 'Simon Harris', [LATEST, OLD])
    fixture.add_member('other', 'Other Member', [{'start': '2026-01-01T00:00:00', 'end': None}])
    outcome = _run(fixture, question)
    assert outcome.status == 'success', outcome.diagnostic
    assert len(outcome.result.rows) == 1
    row = outcome.result.rows[0]
    assert row[:2] == ('Simon Harris', 'Taoiseach')
    assert row[2].endswith('office-holding-0000')
    assert row[3:5] == ('2024-11-29', '2025-01-22')
    assert row[5:] == (member, str(TAOISEACH), row[2] + '#date-range')
    assert 'not a proven historically last tenure' in outcome.diagnostic
    assert 'not a complete career or tenure history' in outcome.diagnostic
    assert '2024-04-09' not in str(outcome.result.rows)
    assert 'LIMIT 100' in outcome.sparql  # not a premature LIMIT 1


def test_existing_unqualified_period_question_still_returns_all_separate_episodes():
    fixture = OfficeEvidenceFixture()
    fixture.add_member('harris', 'Simon Harris', [LATEST, OLD])
    outcome = _run(fixture, 'When was Simon Harris the Taoiseach?', latest=False)
    assert outcome.status == 'success', outcome.diagnostic
    assert len(outcome.result.rows) == 2
    assert outcome.result.rows[0][3] == '2024-04-09'
    assert 'LATEST RECORDED' not in outcome.diagnostic


def test_latest_open_end_is_not_reported_as_completed_tenure():
    fixture = OfficeEvidenceFixture()
    fixture.add_member('finance', 'Finance Holder', [
        {'start': '2022-01-01T00:00:00', 'end': None},
        {'start': '2018-01-01T00:00:00', 'end': '2020-01-01T00:00:00'},
    ], office=FINANCE_MINISTER)
    outcome = _run(fixture, 'When was Finance Holder last Minister for Finance?',
                   member='Finance Holder', office='Minister for Finance')
    assert outcome.status == 'success', outcome.diagnostic
    assert outcome.result.rows[0][4] == 'Open-ended (no end date recorded)'
    assert 'not proof of a completed tenure' in outcome.diagnostic


@pytest.mark.parametrize('earlier,latest', [
    ({'start': LATEST['start'], 'end': LATEST['end']}, LATEST),  # different IRIs, same interval
    ({'start': OLD['start'], 'end': None}, LATEST),
    ({'start': OLD['start'], 'end': LATEST['start']}, LATEST),  # inclusive endpoints
    ({'start': OLD['start'], 'end': '2025-02-01T00:00:00'}, LATEST),
    ({'missing_range': True}, LATEST),
    ({'start': None, 'end': OLD['end']}, LATEST),
    ({'start': 'not-a-date', 'end': OLD['end']}, LATEST),
    ({'start': OLD['start'], 'end': 'not-a-date'}, LATEST),
    ({'start': OLD['start'], 'end': '2023-01-01T00:00:00'}, LATEST),
    ({**OLD, 'conflicting_ranges': [('2024-05-01T00:00:00', OLD['end'])]}, LATEST),
    (OLD, {'start': '2027-01-01T00:00:00', 'end': None}),
])
def test_ambiguous_chronology_or_uncertain_episode_prevents_any_latest_answer(earlier, latest):
    fixture = OfficeEvidenceFixture()
    fixture.add_member('harris', 'Simon Harris', [earlier, latest])
    outcome = _run(fixture)
    assert outcome.status == 'source_data_unavailable', outcome.diagnostic
    assert outcome.result is None


def test_equal_normalized_starts_cannot_be_broken_by_timezone_spelling_or_iri():
    fixture = OfficeEvidenceFixture()
    fixture.add_member('harris', 'Simon Harris', [
        {'start': '2024-11-29T01:00:00+01:00', 'end': '2025-01-22T00:00:00Z'},
        {'start': '2024-11-29T00:00:00Z', 'end': '2025-01-22T00:00:00Z'},
    ])
    outcome = _run(fixture)
    assert outcome.status == 'source_data_unavailable' and outcome.result is None
    assert 'tie at the latest StartDate' in outcome.diagnostic


def test_latest_requires_valid_xsd_datetime_lexical_evidence_not_truncated_iso():
    from poc.nlq.composable_plan import readable_member_office_evidence_result
    from poc.nlq.errors import NLQError
    from poc.nlq.results import QueryResult
    # Raw endpoint bindings: constructing a default rdflib Literal here would
    # normalize this invalid xsd:dateTime into a valid one before the test.
    member = 'https://data.oireachtas.ie/ie/oireachtas/member/id/harris'
    raw = QueryResult('select', ('member_member', 'memberName', 'holding_holding',
        'holdingDateRange', 'holdingStart', 'holdingEnd'), ((member, 'Simon Harris',
        member + '#holding', member + '#range',
        '2024-11-29T00:00^^<http://www.w3.org/2001/XMLSchema#dateTime>', '—'),))
    with pytest.raises(NLQError, match='valid xsd:dateTime lexical form'):
        readable_member_office_evidence_result(raw, member_iri=member,
            member_label='Simon Harris', office_label='Taoiseach',
            office_iri=str(TAOISEACH), latest_recorded=True, as_of=AS_OF)


def test_latest_validates_every_page_before_selection():
    fixture = OfficeEvidenceFixture()
    episodes = [{'start': f'{1800+i}-01-01T00:00:00', 'end': f'{1800+i}-12-31T00:00:00'}
                for i in range(105)]
    fixture.add_member('harris', 'Simon Harris', episodes)
    outcome = _run(fixture)
    assert outcome.status == 'success', outcome.diagnostic
    assert outcome.result.rows[0][3] == '1904-01-01'
    assert any('OFFSET 100' in q for q in fixture.queries)
    fixture.add_member('harris', 'Simon Harris', [*episodes, {'missing_range': True}])
    outcome = _run(fixture)
    assert outcome.status == 'source_data_unavailable' and outcome.result is None


@pytest.mark.parametrize('question', [
    'When was Simon Harris last Taoiseach in 2024?',
    'When was Simon Harris last Taoiseach on 2024-04-09?',
    'When was Simon Harris last Taoiseach while in Fine Gael?',
    'When was Simon Harris last Taoiseach and a Senator?',
    'When was Simon Harris last elected Taoiseach?',
    'How long was Simon Harris last Taoiseach?',
    'When was Simon Harris first Taoiseach?',
])
def test_latest_does_not_drop_other_constraints(question):
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(_draft(), question=question)


def test_all_episodes_and_latest_projection_cannot_be_silently_interchanged():
    for draft, question in [(_draft(latest=False), QUESTION),
                             (_draft(), 'When was Simon Harris the Taoiseach?')]:
        with pytest.raises(InvalidComposableDraft, match='projection'):
            validate_composable_plan_draft(draft, question=question)
    draft = _draft()
    Draft202012Validator(load_composable_draft_schema()).validate(draft)
    final, _ = validate_composable_plan_draft(draft, question=QUESTION)
    assert final['parameters']['selection'] == 'latestRecorded'


def test_actual_ask_route_displays_latest_and_evidence_qualification(monkeypatch):
    from poc.nlq import app as app_module
    fixture = OfficeEvidenceFixture()
    fixture.add_member('harris', 'Simon Harris', [OLD, LATEST])
    monkeypatch.setenv('OIR_NLQ_AS_OF_DATE', AS_OF.isoformat())
    monkeypatch.setattr(app_module, 'FusekiQueryClient', lambda *args, **kwargs: fixture)
    client = TestClient(app_module.create_app(repository_root=ROOT,
        semantic_plan_generator_factory=lambda: FixedPlanGenerator(_draft())))
    response = client.post('/ask', data={'question': QUESTION, 'mode': 'phase2'})
    assert response.status_code == 200
    assert 'data-outcome="answer"' in response.text
    assert 'LATEST RECORDED EPISODE' in response.text
    assert 'not a proven historically last tenure' in response.text
    assert '2024-11-29' in response.text and '2025-01-22' in response.text
    assert 'One uniquely latest recorded accepted OfficeHolding' in response.text
    assert 'DateRange identity' in response.text and 'NamedOffice identity' in response.text
    assert '2024-04-09' not in response.text
