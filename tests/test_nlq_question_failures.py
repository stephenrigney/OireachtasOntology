"""Integrated /ask regressions using small, source-backed relationship excerpts.

Member facts below are excerpts of the preserved 2026-10-04 capture
run-d2c089d0-5203-40f1-97b8-ae0d8285e74d, not an invented current roster.
Pages: 0 (Ahern), 200 (Butler), 400 (Cullinane/Cummins), 500 (Donnelly),
1200 (McDonald/McGuinness). Houses reuse the existing golden source fixture;
party identities reuse the reviewed register. Bill 2017/9's title and supporting
sponsor are from legislation run-dbaf2d97-deab-477a-b359-972c769fb3e5,
skip-001100.json (sha256 04a6f9f1a16dd3e30d18e12a5eb064ce9645da4ae9eb460db755f65d9d909628).
Adversarial additions are explicitly synthetic and never change source/goldens.
"""

import copy
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from poc.nlq.composable_plan import execute_question, plan_question, validate_plan
from poc.nlq.composable_semantic_planner import load_composable_draft_schema
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates
from oireachtas_etl.political_affiliations import GRAPH_IRI, build_graph

ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 1)
A = Namespace("https://data.oireachtas.ie/ontology#")
M = Namespace("https://data.oireachtas.ie/ontology/members#")
F = Namespace("http://xmlns.com/foaf/0.1/")
DL = Namespace("http://data.europa.eu/eli/eli-draft-legislation-ontology#")
ELI = Namespace("http://data.europa.eu/eli/ontology#")
BASE = "https://data.oireachtas.ie/"
HOUSES = BASE + "graph/houses"
CONSTITUENCIES = BASE + "graph/constituencies"
STEPHEN = BASE + "ie/oireachtas/member/id/Stephen-Donnelly.D.2011-03-09"
MARY_LOU = BASE + "ie/oireachtas/member/id/Mary-Lou-McDonald.D.2011-03-09"
WATERFORD = {"Mary Butler", "David Cullinane", "John Cummins", "Conor D. McGuinness"}
QUESTIONS = [
    "Who are the TDs for Waterford?",
    "Who are the TDs for Waterford in the current Dáil?",
    "What constituency does Mary Lou McDonald represent?",
    "What constituencies did Bertie Ahern represent?",
    "What parties did Stephen Donnelly join?",
    "What parties was Stephen Donnelly a member of?",
    "What Bills did Stephen Donnelly sponsor?",
]


def term(number):
    return URIRef(BASE + f"ie/oireachtas/house/dail/{number}")


def binding(value):
    if value is None:
        return "—"
    if isinstance(value, Literal):
        if value.language:
            return f"{value}@{value.language}"
        if value.datatype:
            return f"{value}^^<{value.datatype}>"
    return str(value)


class SourceFixture:
    def __init__(self):
        self.dataset = Dataset()
        self.queries = []
        houses = self.dataset.graph(URIRef(HOUSES))
        for triple in Graph().parse(ROOT / "tests/expected/houses.ttl"):
            houses.add(triple)
        for triple in build_graph().graph(URIRef(GRAPH_IRI)):
            self.dataset.graph(URIRef(GRAPH_IRI)).add(triple)
        current = (34, "2024-11-29", None)
        for code, name in [
            ("Mary-Butler.D.2016-10-03", "Mary Butler"),
            ("David-Cullinane.S.2011-05-25", "David Cullinane"),
            ("John-Cummins.S.2020-03-30", "John Cummins"),
            ("Conor-D-McGuinness.D.2024-11-29", "Conor D. McGuinness"),
        ]:
            self.add_representation(code, name, *current, "Waterford")
        self.add_representation("Mary-Lou-McDonald.D.2011-03-09", "Mary Lou McDonald", *current, "Dublin Central")
        self.add_representation("Mary-Lou-McDonald.D.2011-03-09", "Mary Lou McDonald", 33, "2020-02-08", "2024-11-08", "Dublin Central")
        # Exact historical term/representation/date excerpts, newest first in source.
        episodes = [
            (21, "1977-07-05", "1981-05-21"), (22, "1981-06-30", "1982-02-27"),
            (23, "1982-03-09", "1982-11-04"), (24, "1982-12-14", "1987-01-21"),
            (25, "1987-03-10", "1989-05-25"), (26, "1989-06-29", "1992-11-05"),
            (27, "1992-12-14", "1997-05-15"), (28, "1997-06-26", "2002-04-25"),
            (29, "2002-06-06", "2007-04-30"), (30, "2007-06-14", "2011-02-01"),
        ]
        for number, start, end in episodes:
            self.add_representation("Bertie-Ahern.D.1977-07-05", "Bertie Ahern", number, start, end,
                                    "Dublin Finglas" if number == 21 else "Dublin Central")
        self.add_member(STEPHEN, "Stephen Donnelly")
        for index, (number, code, start, end) in enumerate([
            (31, "Independent", "2011-02-25", "2015-07-15"),
            (31, "Social_Democrats", "2015-07-15", "2016-03-09"),
            (32, "Social_Democrats", "2016-03-10", "2016-09-04"),
            (32, "Independent", "2016-09-05", "2017-02-01"),
            (32, "Fianna_Fáil", "2017-02-02", "2020-01-14"),
            (33, "Fianna_Fáil", "2020-02-08", "2024-11-08"),
        ]):
            graph = self.member_graph(STEPHEN)
            episode = URIRef(STEPHEN + f"#source-party-{index}")
            membership = URIRef(STEPHEN + f"#source-membership-{number}")
            party = URIRef(BASE + f"ie/oireachtas/party/dail/{number}/{code}")
            graph.add((URIRef(STEPHEN), M.hasMembersMembership, episode))
            graph.add((episode, RDF.type, M.ParliamentaryCollectionMembership if code == "Independent" else M.PartyMembership))
            graph.add((episode, M.isPartyMembershipOf, party))
            graph.add((episode, M.inOireachtasMembership, membership))
            graph.add((membership, M.inHouseTerm, term(number)))
            self.add_interval(graph, episode, start, end)
            parties = self.dataset.graph(URIRef(BASE + "graph/parties"))
            parties.add((party, RDF.type, M.ParliamentaryParty))
            parties.add((party, M.activeDuringTerm, term(number)))
            self.dataset.graph(URIRef(HOUSES)).add((term(number), RDF.type, A.DailTerm))
        self.add_bill(2017, "9", "Prohibition of Above-cost Ticket Touting Bill 2017", False)

    def member_graph(self, iri):
        return self.dataset.graph(URIRef(BASE + "graph/member/" + iri.rsplit("/", 1)[-1]))

    def add_member(self, iri, name):
        graph = self.member_graph(iri)
        graph.add((URIRef(iri), RDF.type, A.Member))
        graph.add((URIRef(iri), F.name, Literal(name)))
        return graph

    def add_interval(self, graph, subject, start, end):
        interval = URIRef(str(subject) + "-date-range")
        graph.add((subject, M.hasMembershipDateRange, interval))
        graph.add((interval, RDF.type, M.DateRange))
        graph.add((interval, M.StartDate, Literal(start + "T00:00:00", datatype=XSD.dateTime)))
        if end:
            graph.add((interval, M.EndDate, Literal(end + "T00:00:00", datatype=XSD.dateTime)))

    def add_representation(self, code, name, number, start, end, label):
        iri = BASE + "ie/oireachtas/member/id/" + code
        graph = self.add_member(iri, name)
        membership = URIRef(iri + f"#source-dail-{number}")
        constituency = URIRef(str(term(number)) + "/constituency/" + label.replace(" ", "-"))
        graph.add((URIRef(iri), M.hasMembersMembership, membership))
        graph.add((membership, RDF.type, M.DailMembership))
        graph.add((membership, M.inHouseTerm, term(number)))
        graph.add((membership, M.isRepresentativeFrom, constituency))
        self.add_interval(graph, membership, start, end)
        owner = self.dataset.graph(URIRef(CONSTITUENCIES))
        owner.add((constituency, RDF.type, M.DailConstituency))
        owner.add((constituency, SKOS.prefLabel, Literal(label, lang="en")))
        owner.add((constituency, M.constituencyInHouseTerm, term(number)))
        houses = self.dataset.graph(URIRef(HOUSES))
        houses.add((term(number), RDF.type, A.DailTerm))
        suffix = {21: "st", 22: "nd", 23: "rd"}.get(number, "th")
        houses.add((term(number), SKOS.prefLabel, Literal(f"{number}{suffix} Dáil", lang="en")))

    def add_bill(self, year, number, title, primary):
        bill = URIRef(BASE + f"ie/oireachtas/bill/{year}/{number}")
        graph = self.dataset.graph(URIRef(BASE + f"graph/bill/{year}/{number}"))
        process, delivery, participation = (URIRef(str(bill) + suffix) for suffix in ("#process", "#delivery", "#sponsor"))
        graph.add((bill, RDF.type, DL.DraftLegislationWork))
        graph.add((bill, ELI.work_type, A.Bill))
        graph.add((bill, A.legislativeYear, Literal(year, datatype=XSD.integer)))
        graph.add((bill, URIRef("http://purl.org/dc/terms/title"), Literal(title, lang="en")))
        graph.add((delivery, RDF.type, A.BillDelivery))
        graph.add((delivery, DL.created_a_realization_of, bill))
        graph.add((delivery, DL.forms_part_of, process))
        graph.add((process, RDF.type, DL.LegislativeProcess))
        graph.add((process, DL.process_number, Literal(number, datatype=XSD.string)))
        graph.add((process, DL.had_participation, participation))
        graph.add((participation, RDF.type, DL.Participation))
        graph.add((participation, DL.had_participant_person, URIRef(STEPHEN)))
        if primary is not None:
            graph.add((participation, A.isPrimarySponsor, Literal(primary, datatype=XSD.boolean)))

    def query(self, query):
        self.queries.append(query)
        raw = self.dataset.query(query)
        return QueryResult("select", tuple(str(v) for v in raw.vars), tuple(tuple(binding(v) for v in row) for row in raw))

    def readiness(self):
        return FusekiReadiness("ready", True, (("Members", True),), "source-backed excerpt, not complete")

    def close(self):
        pass


def run(fixture, question, as_of=AS_OF, generator=None):
    return execute_question(question, as_of=as_of, fuseki=fixture,
                            supported_predicates=supported_predicates(ROOT / "ontology"),
                            semantic_plan_generator_factory=(lambda: generator) if generator else None)


def ask(monkeypatch, fixture, question, *, generator=None, as_of=AS_OF):
    from poc.nlq import app as app_module
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", as_of.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **kw: fixture)
    app = app_module.create_app(repository_root=ROOT, semantic_plan_generator_factory=(lambda: generator) if generator else None)
    response = TestClient(app).post("/ask", data={"question": question, "mode": "phase2"})
    assert response.status_code == 200
    return response


@pytest.mark.parametrize("question", QUESTIONS)
def test_seven_questions_actual_ask_answers_identities_and_evidence(monkeypatch, question):
    fixture = SourceFixture()
    outcome = run(fixture, question)
    assert outcome.status == "success", outcome.diagnostic
    assert validate_plan(outcome.plan) == outcome.plan
    schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    Draft202012Validator(schema).validate(outcome.plan)
    response = ask(monkeypatch, fixture, question)
    assert "Validated composable query plan" in response.text
    assert "Unsupported request" not in response.text
    if "Waterford" in question:
        assert {row[0] for row in outcome.result.rows} == WATERFORD
        assert all(row[1:3] == ("Waterford", "34th Dáil") for row in outcome.result.rows)
        for name in WATERFORD:
            assert name in response.text
        assert "2026-11-01" in response.text
    elif "McDonald" in question:
        assert len(outcome.result.rows) == 1
        assert outcome.result.rows[0][:3] == ("Mary Lou McDonald", "Dublin Central", "34th Dáil")
        assert outcome.result.rows[0][3] == MARY_LOU
        assert "Dublin Central" in response.text
    elif "Ahern" in question:
        assert len(outcome.result.rows) == 10
        pairs = {(row[1], row[2]) for row in outcome.result.rows}
        assert ("Dublin Finglas", "21st Dáil") in pairs
        assert len([pair for pair in pairs if pair[0] == "Dublin Central"]) == 9
        assert "Dublin Finglas" in response.text and "30th Dáil" in response.text
    elif "parties" in question:
        assert {row[0] for row in outcome.result.rows} == {"Social Democrats", "Fianna Fáil"}
        assert outcome.plan["referents"]["member"]["iri"] == STEPHEN
        assert "Independent" not in repr(outcome.result.rows)
        assert "2015-07-15" in response.text and "2017-02-02" in response.text
        assert "Supporting membership episodes" in response.text
    else:
        assert outcome.plan["referents"]["member"]["iri"] == STEPHEN
        assert "2017/9" in repr(outcome.result.rows)
        assert "Supporting" in response.text and "Prohibition of Above-cost Ticket Touting" in response.text


@pytest.mark.parametrize("question", [QUESTIONS[4], QUESTIONS[5], QUESTIONS[6], QUESTIONS[2]])
def test_name_after_catalogue_boundary_and_late_duplicate_are_not_missed(monkeypatch, question):
    fixture = SourceFixture()
    for index in range(105):
        fixture.add_member(BASE + f"ie/oireachtas/member/id/AAA-{index:03}", f"AAA Person {index:03}")
    assert run(fixture, question).status == "success"
    name = "Mary Lou McDonald" if "McDonald" in question else "Stephen Donnelly"
    fixture.add_member(BASE + "ie/oireachtas/member/id/ZZZ-duplicate", name)
    outcome = run(fixture, question)
    assert outcome.status == "ambiguous" and len(outcome.candidates) == 2
    assert outcome.result is None
    response = ask(monkeypatch, fixture, question)
    assert "Ambiguous entity" in response.text


@pytest.mark.parametrize("question", ["What parties did Absent Person join?", "What Bills did Absent Person sponsor?", "What constituency does Absent Person represent?"])
def test_absent_name_does_not_become_a_false_answer(monkeypatch, question):
    fixture = SourceFixture()
    assert run(fixture, question).status == "not_found"
    assert "No local Member" in ask(monkeypatch, fixture, question).text or "No matching local Member" in ask(monkeypatch, fixture, question).text


def test_identity_cap_fails_closed_even_if_one_exact_candidate_is_present(monkeypatch):
    fixture = SourceFixture()
    for index in range(100):
        fixture.add_member(BASE + f"ie/oireachtas/member/id/ZZZ-{index}", f"Stephen Donnelly Extra {index}")
    outcome = run(fixture, QUESTIONS[5])
    assert outcome.status == "source_data_unavailable"
    assert outcome.result is None and "safety cap" in outcome.diagnostic
    assert len(fixture.queries) == 1
    response = ask(monkeypatch, fixture, QUESTIONS[5])
    assert "Validated composable query plan" in response.text
    assert "Political affiliation</th>" not in response.text


def test_current_membership_dates_exclude_expired_and_future_members(monkeypatch):
    fixture = SourceFixture()
    fixture.add_representation("Synthetic-Expired", "Synthetic Expired", 34, "2024-11-29", "2026-01-01", "Waterford")
    fixture.add_representation("Synthetic-Future", "Synthetic Future", 34, "2027-01-01", None, "Waterford")
    outcome = run(fixture, QUESTIONS[0])
    assert {row[0] for row in outcome.result.rows} == WATERFORD
    assert "Synthetic Expired</td>" not in ask(monkeypatch, fixture, QUESTIONS[0]).text
    graph = fixture.member_graph(MARY_LOU)
    membership = URIRef(MARY_LOU + "#source-dail-34")
    graph.remove((membership, M.hasMembershipDateRange, None))
    assert run(fixture, QUESTIONS[2]).status == "source_data_unavailable"


def test_current_term_is_date_relative_and_unknown_or_overlapping_terms_fail_closed(monkeypatch):
    fixture = SourceFixture()
    old = run(fixture, QUESTIONS[2], as_of=date(2023, 1, 1))
    assert old.status == "success" and old.result.rows[0][2] == "33rd Dáil"
    houses = fixture.dataset.graph(URIRef(HOUSES))
    dcat = Namespace("http://www.w3.org/ns/dcat#")
    period = URIRef(str(term(34)) + "#term-period")
    houses.set((period, dcat.startDate, Literal("2020-01-01T00:00:00", datatype=XSD.dateTime)))
    assert run(fixture, QUESTIONS[0], as_of=date(2023, 1, 1)).status == "source_data_unavailable"
    response = ask(monkeypatch, fixture, QUESTIONS[0], as_of=date(2023, 1, 1))
    assert "exactly one current Dáil" in response.text


@pytest.mark.parametrize("extra_bills", [98, 99, 102])
def test_answer_pagination_includes_all_sponsors_and_unknown_primary(monkeypatch, extra_bills):
    fixture = SourceFixture()
    for number in range(1, extra_bills + 1):
        fixture.add_bill(2025, str(number), f"Synthetic Pagination Bill {number}", None if number == extra_bills else True)
    outcome = run(fixture, QUESTIONS[6])
    assert outcome.status == "incomplete_primary_status_evidence"
    assert len(outcome.result.rows) == extra_bills + 1
    assert any("OFFSET 100" in query for query in fixture.queries) == (extra_bills >= 99)
    response = ask(monkeypatch, fixture, QUESTIONS[6])
    assert f"Synthetic Pagination Bill {extra_bills}" in response.text and "Unknown" in response.text
    assert "additional sponsorship evidence may be omitted" not in response.text


def test_current_term_does_not_require_a_previous_term(monkeypatch):
    fixture = SourceFixture()
    houses = fixture.dataset.graph(URIRef(HOUSES))
    dct = Namespace("http://purl.org/dc/terms/")
    for subject in list(houses.subjects(dct.temporal, None)):
        if subject != term(34):
            houses.remove((subject, dct.temporal, None))
    assert run(fixture, QUESTIONS[0]).status == "success"
    assert "Mary Butler" in ask(monkeypatch, fixture, QUESTIONS[0]).text


def test_pagination_limit_cannot_produce_a_partial_complete_answer(monkeypatch):
    from poc.nlq import pagination
    fixture = SourceFixture()
    for number in range(1, 101):
        fixture.add_bill(2025, str(number), f"Synthetic Limit Bill {number}", True)
    monkeypatch.setattr(pagination, "MAX_RESULT_OFFSET", 0)
    outcome = run(fixture, QUESTIONS[6])
    assert outcome.status == "source_data_unavailable" and outcome.result is None
    assert "no partial answer" in outcome.diagnostic
    response = ask(monkeypatch, fixture, QUESTIONS[6])
    assert "Synthetic Limit Bill 1</td>" not in response.text
    assert "no partial answer was returned" in response.text


@pytest.mark.parametrize(("question", "canonical"), [
    ("Which political parties did Stephen Donnelly belong to?", QUESTIONS[5]),
    ("Which Bills has Stephen Donnelly sponsored?", QUESTIONS[6]),
    ("Which deputies represent Waterford?", QUESTIONS[0]),
    ("Which constituency does Mary Lou McDonald represent currently?", QUESTIONS[2]),
    ("Which constituencies has Bertie Ahern represented?", QUESTIONS[3]),
])
def test_natural_paraphrases_use_the_same_answers(monkeypatch, question, canonical):
    fixture = SourceFixture()
    expected = run(fixture, canonical)
    actual = run(fixture, question)
    assert actual.status == "success", actual.diagnostic
    assert actual.result.rows == expected.result.rows
    assert "Validated composable query plan" in ask(monkeypatch, fixture, question).text


class FixedGenerator:
    def __init__(self, draft):
        self.draft = draft
        self.calls = 0

    def generate(self, question):
        self.calls += 1
        return json.dumps(self.draft)

    def close(self):
        pass


def draft_for(question, family):
    if family == "constituency_representation":
        from poc.nlq.representation import plan_representation_question
        plan = plan_representation_question(question, as_of=AS_OF)
    else:
        plan = plan_question(question, as_of=AS_OF)
    refs = {key: {"type": ref["type"], "mention": ref.get("mention")} for key, ref in plan["referents"].items()}
    if "term" in refs:
        refs["term"]["selector"] = "currentTerm" if "selector" in plan["referents"]["term"] else None
    answer = plan["answer"] if family == "constituency_representation" else {
        "kind": "entities", "referent": "affiliation" if family == "member_party_history" else "bill",
        "distinctBy": "identity", "display": ["label"], "details": [], "preserveEvidence": True}
    return {"version": 2, "supported": True, "family": family, "unsupportedReason": None,
            "intent": "Retrieve the supported recorded relationship and its source evidence.",
            "referents": refs, "relations": plan["relations"], "constraints": [], "answer": answer}


@pytest.mark.parametrize(("canonical", "question", "family"), [
    (QUESTIONS[5], "Tell me the political parties Stephen Donnelly belonged to.", "member_party_history"),
    (QUESTIONS[6], "List Bills with sponsorship recorded for Stephen Donnelly.", "member_bill_sponsorship"),
    (QUESTIONS[0], "Name Waterford's current deputies.", "constituency_representation"),
    (QUESTIONS[3], "List Bertie Ahern's historical constituencies.", "constituency_representation"),
])
def test_semantic_fallback_reaches_existing_capabilities(monkeypatch, canonical, question, family):
    fixture = SourceFixture()
    draft = draft_for(canonical, family)
    Draft202012Validator(load_composable_draft_schema()).validate(draft)
    generator = FixedGenerator(draft)
    outcome = run(fixture, question, generator=generator)
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.rows == run(fixture, canonical).result.rows
    assert generator.calls == 1
    response = ask(monkeypatch, fixture, question, generator=generator)
    assert "Validated composable query plan" in response.text
    bad = copy.deepcopy(draft)
    bad["relations"].pop()
    rejected = run(fixture, question, generator=FixedGenerator(bad))
    assert rejected.status == "validation_failure" and rejected.result is None


@pytest.mark.parametrize("question", [
    "List only primary Bills sponsored by Stephen Donnelly.",
    "List Bills Stephen Donnelly sponsored after 2017.",
    "List Bills Stephen Donnelly did not sponsor.",
])
def test_semantic_fallback_never_drops_an_additional_condition(monkeypatch, question):
    fixture = SourceFixture()
    generator = FixedGenerator(draft_for(QUESTIONS[6], "member_bill_sponsorship"))
    outcome = run(fixture, question, generator=generator)
    assert outcome.status == "unsupported_request" and outcome.result is None
    assert not fixture.queries
    assert "additional constraint" in ask(monkeypatch, fixture, question, generator=generator).text


def test_preserved_bill_2017_9_transformer_output_answers_ask_when_available(monkeypatch):
    """One pinned raw page, not a corpus scan or a source-fixture rewrite."""
    from oireachtas_etl.transforms.bills import transform_bill_with_report
    from oireachtas_etl.validation.bills import validate_bill
    page = ROOT / "data/raw/legislation/2026-10-09/run-dbaf2d97-deab-477a-b359-972c769fb3e5/skip-001100.json"
    if not page.exists():
        pytest.skip("optional preserved source capture is not installed")
    data = page.read_bytes()
    assert hashlib.sha256(data).hexdigest() == "04a6f9f1a16dd3e30d18e12a5eb064ce9645da4ae9eb460db755f65d9d909628"
    record = next(row for row in json.loads(data)["results"] if row["bill"]["uri"] == BASE + "ie/oireachtas/bill/2017/9")
    emitted, _report = transform_bill_with_report(record)
    validate_bill(record, emitted)
    fixture = SourceFixture()
    owner = fixture.dataset.graph(URIRef(BASE + "graph/bill/2017/9"))
    owner.remove((None, None, None))
    for triple in emitted:
        owner.add(triple)
    outcome = run(fixture, QUESTIONS[6])
    assert outcome.status == "success", outcome.diagnostic
    assert len(outcome.result.rows) == 1
    assert "2017/9" in repr(outcome.result.rows)
    response = ask(monkeypatch, fixture, QUESTIONS[6])
    assert "Supporting" in response.text and "Prohibition of Above-cost Ticket Touting Bill 2017" in response.text
