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
    AGENTS, MEMBERS, HOUSE_GRAPH, SEANAD_TERM, DAIL_TERM, DAIL_TERM_33,
    PARTY_GRAPH, IDENTITY_GRAPH, FG_IDENTITY, SKOS,
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


def _current_dail_party_draft(*, count=False):
    draft = _draft(count=count)
    refs = draft['referents']
    refs['membership']['type'] = 'DailMembership'
    refs['term'].update(type='DailTerm', selector={'kind': 'currentTerm'})
    draft['relations'] = [
        {'id': 'member-membership', 'fact': 'member_has_membership', 'from': 'member', 'to': 'membership'},
        {'id': 'membership-term', 'fact': 'membership_in_term', 'from': 'membership', 'to': 'term'},
        {'id': 'member-episode', 'fact': 'member_party_membership', 'from': 'member', 'to': 'episode'},
        {'id': 'episode-membership', 'fact': 'party_episode_in_membership', 'from': 'episode', 'to': 'membership'},
        {'id': 'episode-party', 'fact': 'episode_in_parliamentary_party', 'from': 'episode', 'to': 'party'},
        {'id': 'party-term', 'fact': 'party_active_during_term', 'from': 'party', 'to': 'term'},
        {'id': 'party-affiliation', 'fact': 'parliamentary_party_has_affiliation_identity', 'from': 'party', 'to': 'affiliation'},
    ]
    draft['constraints'][0]['field'] = 'partyEpisodeInterval'
    return draft


def test_explicit_and_approved_inferred_current_dail_party_scope():
    question = 'Who are the Fine Gael Deputies in the current Dáil?'
    draft = _current_dail_party_draft()
    validated, error = validate_composable_plan_draft(draft, question=question)
    assert error is None
    assert validated['referents']['term']['selector'] == {'kind': 'currentTerm', 'house': 'Dail'}
    assert 'interpretation' not in validated
    inferred, error = validate_composable_plan_draft(draft, question='Who are the Fine Gael Deputies?')
    assert error is None
    assert inferred['referents']['term']['selector'] == validated['referents']['term']['selector']
    assert inferred['interpretation'] == {'policy': 'present_relationship_as_of', 'question': 'Who are the Fine Gael Deputies?'}


def _dail_party_fixture():
    fixture = CurrentHouseFixture(members=[])
    fixture.dataset.graph(URIRef(HOUSE_GRAPH)).add(
        (URIRef(DAIL_TERM_33), URIRef(AGENTS + 'termNo'), Literal(33, datatype=XSD.integer)))
    records = [
        ('Current-FG', 'Current Fine Gael', 'Fine Gael', FG_IDENTITY,
         ('2025-01-01T00:00:00', None), ('2025-01-01T00:00:00', None), DAIL_TERM),
        ('Current-FF', 'Current Fianna Fáil', 'Fianna Fáil',
         'https://data.oireachtas.ie/ie/oireachtas/political-affiliation/fianna-fail',
         ('2025-01-01T00:00:00', None), ('2025-01-01T00:00:00', None), DAIL_TERM),
        ('Ended-Membership', 'Ended Membership', 'Fine Gael', FG_IDENTITY,
         ('2025-01-01T00:00:00', '2026-11-08T23:59:59'), ('2025-01-01T00:00:00', None), DAIL_TERM),
        ('Ended-Party', 'Ended Party', 'Fine Gael', FG_IDENTITY,
         ('2025-01-01T00:00:00', None), ('2025-01-01T00:00:00', '2026-11-08T23:59:59'), DAIL_TERM),
        ('Historical-FG', 'Historical Fine Gael', 'Fine Gael', FG_IDENTITY,
         ('2020-02-08T00:00:00', '2024-11-08T00:00:00'), ('2020-02-08T00:00:00', '2024-11-08T00:00:00'), DAIL_TERM_33),
    ]
    for slug, name, party_name, identity, member_range, party_range, term in records:
        item = {'slug': slug, 'name': name,
                'dail_paths': [(term, member_range)]}
        fixture.add_member(item, omit_dail_range=True)
        member = URIRef(f'https://data.oireachtas.ie/ie/oireachtas/member/id/{slug}')
        graph = fixture.dataset.graph(URIRef(f'https://data.oireachtas.ie/graph/member/{slug}'))
        membership = URIRef(f'{member}#dail-membership')
        episode = URIRef(f'{member}#party-episode')
        party = URIRef(f'https://data.oireachtas.ie/ie/oireachtas/party/dail/{term.rsplit("/", 1)[-1]}/{slug}')
        graph.add((member, URIRef(MEMBERS + 'hasMembersMembership'), episode))
        graph.add((episode, RDF.type, URIRef(MEMBERS + 'PartyMembership')))
        graph.add((episode, URIRef(MEMBERS + 'inOireachtasMembership'), membership))
        graph.add((episode, URIRef(MEMBERS + 'isPartyMembershipOf'), party))
        for resource, dates in ((membership, member_range), (episode, party_range)):
            date_range = URIRef(f'{resource}#date-range')
            graph.add((resource, URIRef(MEMBERS + 'hasMembershipDateRange'), date_range))
            graph.add((date_range, RDF.type, URIRef(MEMBERS + 'DateRange')))
            graph.add((date_range, URIRef(MEMBERS + 'StartDate'), Literal(dates[0], datatype=XSD.dateTime)))
            if dates[1]:
                graph.add((date_range, URIRef(MEMBERS + 'EndDate'), Literal(dates[1], datatype=XSD.dateTime)))
        party_graph = fixture.dataset.graph(URIRef(PARTY_GRAPH))
        party_graph.add((party, RDF.type, URIRef(MEMBERS + 'ParliamentaryParty')))
        party_graph.add((party, URIRef(SKOS + 'prefLabel'), Literal(f'{party_name}, {term.rsplit("/", 1)[-1]}', lang='en')))
        party_graph.add((party, URIRef(MEMBERS + 'activeDuringTerm'), URIRef(term)))
        identity_graph = fixture.dataset.graph(URIRef(IDENTITY_GRAPH))
        identity_graph.add((party, URIRef(MEMBERS + 'hasPoliticalAffiliationIdentity'), URIRef(identity)))
        identity_graph.add((URIRef(identity), RDF.type, URIRef(MEMBERS + 'PoliticalAffiliationIdentity')))
        identity_graph.add((URIRef(identity), URIRef(SKOS + 'prefLabel'), Literal(party_name, lang='en')))
    # Same Member, membership and reviewed identity through a second party
    # occurrence: entity lists/counts must remain distinct by Member identity.
    member = URIRef('https://data.oireachtas.ie/ie/oireachtas/member/id/Current-FG')
    graph = fixture.dataset.graph(URIRef('https://data.oireachtas.ie/graph/member/Current-FG'))
    membership = URIRef(f'{member}#dail-membership')
    episode = URIRef(f'{member}#second-party-episode')
    party = URIRef('https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Current-FG-second')
    graph.add((member, URIRef(MEMBERS + 'hasMembersMembership'), episode))
    graph.add((episode, RDF.type, URIRef(MEMBERS + 'PartyMembership')))
    graph.add((episode, URIRef(MEMBERS + 'inOireachtasMembership'), membership))
    graph.add((episode, URIRef(MEMBERS + 'isPartyMembershipOf'), party))
    date_range = URIRef(f'{episode}#date-range')
    graph.add((episode, URIRef(MEMBERS + 'hasMembershipDateRange'), date_range))
    graph.add((date_range, RDF.type, URIRef(MEMBERS + 'DateRange')))
    graph.add((date_range, URIRef(MEMBERS + 'StartDate'), Literal('2025-01-01T00:00:00', datatype=XSD.dateTime)))
    party_graph = fixture.dataset.graph(URIRef(PARTY_GRAPH))
    party_graph.add((party, RDF.type, URIRef(MEMBERS + 'ParliamentaryParty')))
    party_graph.add((party, URIRef(SKOS + 'prefLabel'), Literal('Fine Gael, 34 (second occurrence)', lang='en')))
    party_graph.add((party, URIRef(MEMBERS + 'activeDuringTerm'), URIRef(DAIL_TERM)))
    identity_graph = fixture.dataset.graph(URIRef(IDENTITY_GRAPH))
    identity_graph.add((party, URIRef(MEMBERS + 'hasPoliticalAffiliationIdentity'), URIRef(FG_IDENTITY)))
    return fixture, records


def _dail_draft(*, party='Fine Gael', count=False, historical=False):
    draft = _current_dail_party_draft(count=count)
    draft['referents']['affiliation']['mention'] = party
    if historical:
        draft['referents']['term']['selector'] = {'kind': 'termNumber', 'number': 33}
    return draft


def _run_dail(question, fixture, *, party='Fine Gael', count=False, historical=False):
    return execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / 'ontology'),
        semantic_plan_generator_factory=lambda: FixedPlanGenerator(
            _dail_draft(party=party, count=count, historical=historical)),
    )


def test_explicit_current_dail_party_lists_and_counts_match_independent_rdf_evidence():
    fixture, records = _dail_party_fixture()
    # Independent hand-written RDF selection (not the capability compiler).
    query = f'''SELECT ?member ?memberStart ?memberEnd ?partyStart ?partyEnd ?identity WHERE {{
      GRAPH ?mg {{ ?member a <{AGENTS}Member>; <http://xmlns.com/foaf/0.1/name> ?name;
          <{MEMBERS}hasMembersMembership> ?membership, ?episode .
        ?membership a <{MEMBERS}DailMembership>; <{MEMBERS}inHouseTerm> <{DAIL_TERM}>;
          <{MEMBERS}hasMembershipDateRange> ?mr .
        ?mr a <{MEMBERS}DateRange>; <{MEMBERS}StartDate> ?memberStart . OPTIONAL {{ ?mr <{MEMBERS}EndDate> ?memberEnd }}
        ?episode a <{MEMBERS}PartyMembership>; <{MEMBERS}inOireachtasMembership> ?membership;
          <{MEMBERS}isPartyMembershipOf> ?party; <{MEMBERS}hasMembershipDateRange> ?pr .
        ?pr a <{MEMBERS}DateRange>; <{MEMBERS}StartDate> ?partyStart . OPTIONAL {{ ?pr <{MEMBERS}EndDate> ?partyEnd }}
      }}
      GRAPH <{PARTY_GRAPH}> {{ ?party <{MEMBERS}activeDuringTerm> <{DAIL_TERM}> }}
      GRAPH <{IDENTITY_GRAPH}> {{ ?party <{MEMBERS}hasPoliticalAffiliationIdentity> ?identity }}
    }}'''
    raw = fixture.dataset.query(query)
    expected = set()
    for row in raw:
        member_start = date.fromisoformat(str(row.memberStart)[:10])
        member_end = date.fromisoformat(str(row.memberEnd)[:10]) if row.memberEnd else None
        party_start = date.fromisoformat(str(row.partyStart)[:10])
        party_end = date.fromisoformat(str(row.partyEnd)[:10]) if row.partyEnd else None
        if (row.identity == URIRef(FG_IDENTITY) and member_start <= AS_OF
                and (member_end is None or AS_OF <= member_end)
                and party_start <= AS_OF and (party_end is None or AS_OF <= party_end)):
            expected.add(str(row.member))

    result = _run_dail('Who are the Fine Gael Deputies in the current Dáil?', fixture)
    assert result.status == 'success', result.diagnostic
    actual = {row[1] for row in result.result.rows}
    assert actual == expected
    assert len(actual) == 1
    assert len(result.result.rows) == 1
    assert DAIL_TERM in result.result.rows[0][2]
    assert '2026-11-08T23:59:59' not in result.result.rows[0][2]
    paraphrase = _run_dail('Which Fine Gael TDs are currently serving?', fixture)
    assert paraphrase.status == 'success', paraphrase.diagnostic
    assert {row[1] for row in paraphrase.result.rows} == actual

    count = _run_dail('How many Fine Gael Deputies are in the current Dáil?', fixture, count=True)
    assert count.status == 'success', count.diagnostic
    assert count.result.rows == ((str(len(expected)),),)

    fianna = _run_dail('Which Fianna Fáil Deputies are currently serving?', fixture, party='Fianna Fáil')
    assert fianna.status == 'success', fianna.diagnostic
    assert len(fianna.result.rows) == 1
    assert 'Current-FF' in fianna.result.rows[0][1]

    historical = _run_dail('Who were the Fine Gael TDs in the 33rd Dáil?', fixture, historical=True)
    assert historical.status == 'success', historical.diagnostic
    assert len(historical.result.rows) == 1
    assert DAIL_TERM_33 in historical.result.rows[0][2]

    for unsupported in (
        'Who are the Fine Gael Deputies in the current Dáil on 2026-01-01?',
        'Who are the Fine Gael Deputies in the current Dáil who serve on a committee?',
        'Who are the Fine Gael and Fianna Fáil Deputies in the current Dáil?',
    ):
        rejected = _run_dail(unsupported, fixture)
        assert rejected.status != 'success', (unsupported, rejected.result)


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
        assert actual.plan['interpretation']['policy'] == 'present_relationship_as_of'
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
