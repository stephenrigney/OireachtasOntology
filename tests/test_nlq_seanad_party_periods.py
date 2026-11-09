"""Group A: current defaults and exact numbered Seanad/party interval reuse."""

import copy
from datetime import date

import pytest
from jsonschema import Draft202012Validator
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD

from poc.nlq.composable_plan import execute_question, validate_plan, PlanError
from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft, UnsupportedComposableRequest, complete_v2_plan,
    load_composable_draft_schema, validate_composable_plan_draft,
)
from poc.nlq.vocabulary import supported_predicates
from test_nlq_composable_current_house_membership import (
    CurrentHouseFixture, FixedPlanGenerator, _q23_draft, ROOT,
    AGENTS, MEMBERS, HOUSE_GRAPH, SEANAD_TERM,
)

AS_OF = date(2026, 11, 9)
HISTORICAL_TERM = SEANAD_TERM.rsplit('/', 1)[0] + '/25'
LABOUR = 'https://data.oireachtas.ie/ie/oireachtas/political-affiliation/labour-party'


def _draft(*, historical=False, party='Fine Gael', count=False):
    draft = _q23_draft(count=count)
    draft['referents']['affiliation']['mention'] = party
    if historical:
        draft['referents']['term']['selector'] = {'kind': 'termNumber', 'number': 25}
    return draft


def _run(question, fixture, **kwargs):
    draft = _draft(**kwargs)
    return execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / 'ontology'),
        semantic_plan_generator_factory=lambda: FixedPlanGenerator(draft),
    )


def _fixture(*, historical=False, missing=False, conflict=False, size=1):
    fixture = CurrentHouseFixture(members=[])
    for i in range(size):
        fixture.add_member({
            'slug': f'Member-{i:03}', 'name': f'Member {i:03}',
            'seanad': ('2016-04-25T00:00:00' if historical else '2025-01-29T00:00:00', None),
        }, party=True, party_interval=None if missing else (
            '2017-01-01T00:00:00' if historical else '2025-01-29T00:00:00',
            '2018-01-01T00:00:00' if historical else None,
        ), conflicting_membership_range=('2017-01-01T00:00:00', None) if conflict else None)
    if historical:
        # This is synthetic test RDF, not a source/golden fixture.
        replacements = {SEANAD_TERM: HISTORICAL_TERM}
        for s, p, o, graph in list(fixture.dataset.quads((None, None, None, None))):
            for value in (s, o):
                if isinstance(value, URIRef) and '/party/seanad/27/' in str(value):
                    replacements[str(value)] = str(value).replace('/27/', '/25/')
        for s, p, o, graph in list(fixture.dataset.quads((None, None, None, None))):
            target = fixture.dataset.graph(graph)
            target.remove((s, p, o))
            target.add((URIRef(replacements.get(str(s), str(s))) if isinstance(s, URIRef) else s,
                        p, URIRef(replacements.get(str(o), str(o))) if isinstance(o, URIRef) else o))
        houses = fixture.dataset.graph(URIRef(HOUSE_GRAPH))
        houses.add((URIRef(HISTORICAL_TERM), URIRef(AGENTS + 'termNo'), Literal(25, datatype=XSD.integer)))
        # Record the actual end of the synthetic membership, independent of asOf.
        for graph in fixture.dataset.graphs():
            for membership in list(graph.subjects(RDF.type, URIRef(MEMBERS + 'SeanadMembership'))):
                for date_range in graph.objects(membership, URIRef(MEMBERS + 'hasMembershipDateRange')):
                    graph.add((date_range, URIRef(MEMBERS + 'EndDate'), Literal('2020-03-27T00:00:00', datatype=XSD.dateTime)))
    return fixture


@pytest.mark.parametrize('question', [
    'Who are the Fine Gael Senators?',
    'Which Fine Gael Senators are there?',
    'Who are the Fine Gael Senators in the current Seanad?',
    'Which Fine Gael Senators are currently serving?',
])
def test_current_forms_share_exact_selection_and_separate_active_intervals(question):
    fixture = _fixture()
    fixture.add_member({'slug': 'Ended', 'name': 'Ended Senator',
                        'seanad': ('2025-01-29T00:00:00', '2026-11-08T23:59:59')},
                       party=True, party_interval=('2025-01-29T00:00:00', None))
    fixture.add_member({'slug': 'Party-Ended', 'name': 'Party Ended',
                        'seanad': ('2025-01-29T00:00:00', None)},
                       party=True, party_interval=('2025-01-29T00:00:00', '2026-11-08T23:59:59'))
    actual = _run(question, fixture)
    explicit = _run('Who are the Fine Gael Senators in the current Seanad?', fixture)
    assert actual.status == explicit.status == 'success', actual.diagnostic
    assert actual.result.rows == explicit.result.rows
    assert len(actual.result.rows) == 1
    assert SEANAD_TERM in actual.result.rows[0][2]
    if 'current' not in question:
        assert actual.plan['interpretation']['policy'] == 'present_seanad_party_as_of'
        assert actual.plan['interpretation']['date'] == AS_OF.isoformat()


@pytest.mark.parametrize('question', [
    'Who were the Fine Gael Senators in the 25th Seanad?',
    'Which Fine Gael Senators served during the 25th Seanad?',
    'List the Fine Gael Senators in the 25th Seanad.',
])
def test_numbered_term_uses_historical_overlap_not_present_affiliation(question):
    fixture = _fixture(historical=True)
    outcome = _run(question, fixture, historical=True)
    assert outcome.status == 'success', outcome.diagnostic
    assert len(outcome.result.rows) == 1
    evidence = outcome.result.rows[0][2]
    assert HISTORICAL_TERM in evidence
    assert 'membership ' in evidence and 'episode ' in evidence and 'affiliation identity ' in evidence
    assert '2017-01-01T00:00:00 – 2018-01-01T00:00:00' in evidence
    assert '2020-03-27T00:00:00' in evidence
    assert 'interpretation' not in outcome.plan
    assert outcome.plan['referents']['term']['iri'] == HISTORICAL_TERM
    assert any('a agents:SeanadTerm ; agents:termNo "25"' in q for q in fixture.queries)


def test_party_changes_preserve_multiple_qualifying_episodes_and_distinct_people():
    fixture = _fixture(historical=True, size=2)
    for graph in fixture.dataset.graphs():
        for episode in list(graph.subjects(RDF.type, URIRef(MEMBERS + 'PartyMembership'))):
            new_episode = URIRef(str(episode) + '-return')
            for s, p, o in list(graph.triples((episode, None, None))):
                if p != URIRef(MEMBERS + 'hasMembershipDateRange'):
                    graph.add((new_episode, p, o))
            member = next(graph.subjects(URIRef(MEMBERS + 'hasMembersMembership'), episode))
            graph.add((member, URIRef(MEMBERS + 'hasMembersMembership'), new_episode))
            r = URIRef(str(new_episode) + '-range')
            graph.add((new_episode, URIRef(MEMBERS + 'hasMembershipDateRange'), r))
            graph.add((r, RDF.type, URIRef(MEMBERS + 'DateRange')))
            graph.add((r, URIRef(MEMBERS + 'StartDate'), Literal('2019-01-01T00:00:00', datatype=XSD.dateTime)))
            graph.add((r, URIRef(MEMBERS + 'EndDate'), Literal('2019-02-01T00:00:00', datatype=XSD.dateTime)))
    outcome = _run('Who were the Fine Gael Senators in the 25th Seanad?', fixture, historical=True)
    assert outcome.status == 'success', outcome.diagnostic
    assert len(outcome.result.rows) == 2
    assert all('2017-01-01' in row[2] and '2019-01-01' in row[2] for row in outcome.result.rows)


def test_terminal_party_word_omission_resolves_only_whole_reviewed_names():
    from poc.nlq.composable_plan import _resolve_term_scoped_affiliation
    from poc.nlq.results import QueryResult
    columns = ('party', 'partyLabel', 'affiliation', 'affiliationLabel')
    rows = ((HISTORICAL_TERM + '/Labour', 'Labour Party@en', LABOUR, 'Labour Party@en'),
            (HISTORICAL_TERM + '/National-Labour', 'National Labour Party@en',
             LABOUR.replace('/labour-party', '/national-labour-party'), 'National Labour Party@en'))
    assert _resolve_term_scoped_affiliation(QueryResult('select', columns, rows), 'Labour') == (LABOUR, 'Labour Party')
    from poc.nlq.errors import NLQError
    with pytest.raises(NLQError, match='No reviewed'):
        _resolve_term_scoped_affiliation(QueryResult('select', columns, rows[1:]), 'Labour')


@pytest.mark.parametrize('kwargs', [{'missing': True}, {'conflict': True}])
def test_historical_uncertain_evidence_is_not_a_negative_or_partial_roster(kwargs):
    outcome = _run('Who were the Fine Gael Senators in the 25th Seanad?',
                   _fixture(historical=True, **kwargs), historical=True)
    assert outcome.status == 'source_data_unavailable'
    assert outcome.result is None
    assert 'uncertain' in outcome.diagnostic


def test_historical_nonoverlap_is_not_a_certified_negative():
    fixture = _fixture(historical=True)
    for graph in fixture.dataset.graphs():
        for episode in graph.subjects(RDF.type, URIRef(MEMBERS + 'PartyMembership')):
            for r in graph.objects(episode, URIRef(MEMBERS + 'hasMembershipDateRange')):
                graph.set((r, URIRef(MEMBERS + 'StartDate'), Literal('2025-01-01T00:00:00', datatype=XSD.dateTime)))
                graph.remove((r, URIRef(MEMBERS + 'EndDate'), None))
    outcome = _run('Who were the Fine Gael Senators in the 25th Seanad?', fixture, historical=True)
    assert outcome.status == 'source_data_unavailable' and outcome.result is None
    assert 'does not establish a complete historical negative' in outcome.diagnostic


def test_historical_list_and_count_paginate_same_selection():
    fixture = _fixture(historical=True, size=101)
    listed = _run('Who were the Fine Gael Senators in the 25th Seanad?', fixture, historical=True)
    counted = _run('How many Fine Gael Senators were in the 25th Seanad?', fixture, historical=True, count=True)
    assert listed.status == counted.status == 'success', counted.diagnostic
    assert len(listed.result.rows) == 101
    assert counted.result.rows == (('101',),)
    assert any('OFFSET 100' in q for q in fixture.queries)


@pytest.mark.parametrize('question,historical', [
    ('Who were the Fine Gael Senators?', False),
    ('Who are the Fine Gael Senators on 2020-01-01?', False),
    ('Who are the Fine Gael Senators in the 25th Seanad?', False),
    ('Who were the Fine Gael Senators in the current 25th Seanad?', True),
    ('Who were the Fine Gael Senators in the 25th and 26th Seanad?', True),
    ('Who were the Fine Gael Senators in the 25th Seanad on 2018-01-01?', True),
    ('Who were the Fine Gael Senators in the 25th Seanad before 2018?', True),
    ('Who were the Fine Gael Senators in the 25th Seanad and on committees?', True),
    ('Who were the Fine Gael Senators in the 25th Seanad except former ministers?', True),
    ('Who were the Fine Gael and Labour Senators in the 25th Seanad?', True),
    ('Who are the Fine Gael Senators who represent Dublin?', False),
    ('Who are the former Fine Gael Senators in the current Seanad?', False),
])
def test_unrepresented_scopes_and_relationships_fail_closed(question, historical):
    with pytest.raises((InvalidComposableDraft, UnsupportedComposableRequest)):
        validate_composable_plan_draft(_draft(historical=historical), question=question)


def test_default_interpretation_is_revalidated_and_drafts_match_schema():
    for historical, question in [(False, 'Who are the Fine Gael Senators?'),
                                 (True, 'Who were the Fine Gael Senators in the 25th Seanad?')]:
        draft = _draft(historical=historical)
        Draft202012Validator(load_composable_draft_schema()).validate(draft)
        final, _ = validate_composable_plan_draft(draft, question=question)
        plan = complete_v2_plan(final, as_of=AS_OF)
        validate_plan(plan)
        if not historical:
            tampered = copy.deepcopy(plan)
            tampered['interpretation']['question'] = 'Who were the Fine Gael Senators?'
            with pytest.raises(PlanError):
                validate_plan(tampered)


def test_historical_ask_preserves_term_and_does_not_claim_current(monkeypatch):
    from poc.nlq import app as app_module
    from fastapi.testclient import TestClient
    fixture = _fixture(historical=True)
    monkeypatch.setenv('OIR_NLQ_AS_OF_DATE', AS_OF.isoformat())
    monkeypatch.setattr(app_module, 'FusekiQueryClient', lambda *args, **kwargs: fixture)
    client = TestClient(app_module.create_app(repository_root=ROOT,
        semantic_plan_generator_factory=lambda: FixedPlanGenerator(_draft(historical=True))))
    response = client.post('/ask', data={'question': 'Who were the Fine Gael Senators in the 25th Seanad?', 'mode': 'phase2'})
    assert 'data-outcome="answer"' in response.text
    assert 'explicitly numbered Seanad' in response.text
    assert 'for the current Seanad' not in response.text
    assert '2017-01-01' in response.text and HISTORICAL_TERM in response.text
