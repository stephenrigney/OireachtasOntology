"""Stage C capability and truthful-coverage acceptance over small owner-scoped RDF."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import copy

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF

from poc.nlq.composable_plan import PlanError, execute_question, validate_plan
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.errors import NLQError
from poc.nlq.results import QueryResult, parse_results
from poc.nlq.stage_c import plan_stage_c
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
ELI_DL = "http://data.europa.eu/eli/eli-draft-legislation-ontology#"
XSD = "http://www.w3.org/2001/XMLSchema#"
AS_OF = date(2026, 10, 28)


class StageCFixture:
    def __init__(self, *, term=33, seats=160, seat_datatype=XSD + "integer",
                 party_count=2, debate=False, written_answer=False, bill_graph=False,
                 houses_graph=True, parties_graph=True, extra_term_without_seats=False,
                 unlabelled_party=False, mixed_seat_assertion=None, debate_count=1):
        self.dataset = Dataset()
        self.queries: list[str] = []
        houses = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses")) if houses_graph else None
        term_iri = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/house/dail/{term}")
        if houses is not None:
            houses.add((term_iri, RDF.type, URIRef(AGENTS + "DailTerm")))
            houses.add((term_iri, URIRef(AGENTS + "termNo"), Literal(term, datatype=URIRef(XSD + "integer"))))
        if seats is not None:
            if houses is not None: houses.add((term_iri, URIRef(AGENTS + "seats"), Literal(seats, datatype=URIRef(seat_datatype))))
        if mixed_seat_assertion is not None and houses is not None:
            houses.add((term_iri, URIRef(AGENTS + "seats"), Literal(mixed_seat_assertion[0], datatype=URIRef(mixed_seat_assertion[1]))))
        if extra_term_without_seats and houses is not None:
            duplicate = URIRef(f"https://data.oireachtas.ie/example/dail/{term}")
            houses.add((duplicate, RDF.type, URIRef(AGENTS + "DailTerm")))
            houses.add((duplicate, URIRef(AGENTS + "termNo"), Literal(term, datatype=URIRef(XSD + "integer"))))
        parties = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties")) if parties_graph else None
        for i in range(party_count):
            party = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/party/dail/{term}/party-{i}")
            if parties is not None:
                parties.add((party, RDF.type, URIRef(MEMBERS + "ParliamentaryParty")))
                parties.add((party, URIRef(MEMBERS + "activeDuringTerm"), term_iri))
                if not unlabelled_party or i != 0:
                    parties.add((party, URIRef(SKOS + "prefLabel"), Literal(f"Example Party {i + 1}", lang="en")))
        if debate:
            self._add_sitting(count=debate_count)
        if written_answer:
            graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/debate/dail/2026-09-24/writtens"))
            graph.add((URIRef("https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-09-24/writtens"),
                       RDF.type, URIRef(AGENTS + "DebateRecord")))
        if bill_graph:
            graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2024/48"))
            graph.add((URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/48"), RDF.type,
                       URIRef(ELI_DL + "DraftLegislationWork")))
            graph.add((URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/48"),
                       URIRef("http://data.europa.eu/eli/ontology#work_type"), URIRef(AGENTS + "Bill")))

    def _add_sitting(self, *, count=1):
        graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/debate/dail/2026-09-24/debate"))
        for i in range(count):
            suffix = "" if i == 0 else f"/extra-{i}"
            record = URIRef("https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-09-24/debate" + suffix)
            sitting = URIRef(str(record) + "#sitting")
            graph.add((record, RDF.type, URIRef(AGENTS + "DebateRecord")))
            graph.add((record, URIRef(AGENTS + "debateDate"), Literal("2026-09-24T00:00:00", datatype=URIRef(XSD + "dateTime"))))
            graph.add((sitting, RDF.type, URIRef(AGENTS + "DebateSitting")))
            graph.add((sitting, URIRef(AGENTS + "producedRecord"), record))
            graph.add((sitting, URIRef(ELI_DL + "activity_date"), Literal("2026-09-24", datatype=URIRef(XSD + "date"))))

    def readiness(self):
        return FusekiReadiness("ready", True, (), "bounded Stage C fixture")

    def close(self):
        pass

    def query(self, query):
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type == "ASK":
            return QueryResult("ask", boolean=bool(result.askAnswer))
        columns = tuple(str(v) for v in result.vars)
        bindings = []
        for row in result:
            binding = {}
            for column, value in zip(columns, row):
                if value is None:
                    continue
                if isinstance(value, URIRef):
                    binding[column] = {"type": "uri", "value": str(value)}
                else:
                    cell = {"type": "literal", "value": str(value)}
                    if getattr(value, "language", None): cell["xml:lang"] = value.language
                    elif getattr(value, "datatype", None): cell["datatype"] = str(value.datatype)
                    binding[column] = cell
            bindings.append(binding)
        return parse_results({"head": {"vars": list(columns)}, "results": {"bindings": bindings}})


def run(question, fixture):
    return execute_question(question, as_of=AS_OF, fuseki=fixture,
                            supported_predicates=supported_predicates(ROOT / "ontology"))


def ask(question, fixture, monkeypatch):
    from poc.nlq import app as app_module
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    return TestClient(app_module.create_app(repository_root=ROOT)).post(
        "/ask", data={"question": question, "mode": "phase2"})


def test_q16_reads_authoritative_seats_from_existing_expected_houses_graph():
    fixture = StageCFixture(party_count=0)
    fixture.dataset.parse(ROOT / "tests/expected/houses.ttl", format="turtle")
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "success"
    assert outcome.result.rows == (("33rd Dáil", "160"),)
    assert "agents:seats" in outcome.sparql and "agents:Member" not in outcome.sparql
    assert "Members" not in outcome.diagnostic


def test_q16_ask_renders_source_backed_seat_answer(monkeypatch):
    fixture = StageCFixture(party_count=0)
    fixture.dataset.parse(ROOT / "tests/expected/houses.ttl", format="turtle")
    response = ask("How many members were in the 33rd Dáil?", fixture, monkeypatch)
    assert response.status_code == 200
    assert "160" in response.text and "33rd Dáil" in response.text
    assert "Validated composable query plan" in response.text
    assert "seat complement" in response.text


@pytest.mark.parametrize("fixture", [
    StageCFixture(seats=None),
    StageCFixture(seats=160, seat_datatype=XSD + "string"),
])
def test_q16_missing_or_invalid_seat_value_is_not_a_member_count(fixture):
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "seat" in outcome.diagnostic.lower()
    assert outcome.result is None


def test_q16_ask_reports_missing_seat_value_without_replacing_it_by_people(monkeypatch):
    response = ask("How many members were in the 33rd Dáil?", StageCFixture(seats=None), monkeypatch)
    assert response.status_code == 200
    assert "seat" in response.text.lower()
    assert "Member records" in response.text or "seat total was inferred" in response.text
    assert "Validated composable query plan" in response.text


def test_q16_conflicting_seat_assertions_fail_closed():
    fixture = StageCFixture()
    term = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/33")
    fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses")).add(
        (term, URIRef(AGENTS + "seats"), Literal(161, datatype=URIRef(XSD + "integer"))))
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "conflicting" in outcome.diagnostic


def test_q16_ambiguous_term_identity_fails_closed():
    fixture = StageCFixture()
    houses = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
    duplicate = URIRef("https://data.oireachtas.ie/example/dail/33")
    houses.add((duplicate, RDF.type, URIRef(AGENTS + "DailTerm")))
    houses.add((duplicate, URIRef(AGENTS + "termNo"), Literal(33, datatype=URIRef(XSD + "integer"))))
    houses.add((duplicate, URIRef(AGENTS + "seats"), Literal(160, datatype=URIRef(XSD + "integer"))))
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "ambiguous" in outcome.diagnostic


def test_q16_second_matching_typed_term_without_seats_does_not_disappear():
    fixture = StageCFixture(extra_term_without_seats=True)
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "More than one typed HouseTerm" in outcome.diagnostic


def test_q16_valid_integer_plus_invalid_typed_assertion_is_not_silently_filtered():
    fixture = StageCFixture(mixed_seat_assertion=("161", XSD + "string"))
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "conflicting seat assertions" in outcome.diagnostic
    assert "FILTER(DATATYPE" not in outcome.sparql


def test_q17_lists_parties_and_clearly_says_groups_are_missing_not_nonexistent():
    fixture = StageCFixture(term=34)
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "success"
    assert {row[0] for row in outcome.result.rows} == {"Example Party 1", "Example Party 2"}
    assert "ParliamentaryGroup data is missing" in outcome.diagnostic
    assert "does not mean no groups existed" in outcome.diagnostic
    assert "ParliamentaryGroup" not in fixture.queries[-1]


def test_q17_ask_shows_party_rows_and_group_data_boundary(monkeypatch):
    fixture = StageCFixture(term=34)
    response = ask("What are the groups and parties in the 34th Dáil?", fixture, monkeypatch)
    assert response.status_code == 200
    assert "Example Party 1" in response.text and "Example Party 2" in response.text
    assert "ParliamentaryGroup data is missing" in response.text
    assert "does not mean no groups existed" in response.text


def test_q17_resolves_exact_house_term_before_join_and_rejects_ambiguous_term():
    fixture = StageCFixture(term=34, extra_term_without_seats=True)
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "More than one typed HouseTerm" in outcome.diagnostic
    assert len(fixture.queries) == 1
    assert "graph/parties" not in fixture.queries[0]


def test_q17_unlabelled_party_identity_is_preserved_and_called_incomplete():
    fixture = StageCFixture(term=34, party_count=2, unlabelled_party=True)
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert len(outcome.result.rows) == 2
    assert any(row[0] == "Label unavailable" for row in outcome.result.rows)
    assert any("party-0" in row[1] for row in outcome.result.rows)
    assert "exact IRIs remain listed" in outcome.diagnostic


@pytest.mark.parametrize("fixture,detail", [
    (StageCFixture(term=33), "No typed HouseTerm"),
    (StageCFixture(term=34, parties_graph=False), "No typed ParliamentaryParty records"),
])
def test_q17_missing_term_or_party_dataset_is_not_an_empty_real_world_list(fixture, detail):
    question = "What are the groups and parties in the 35th Dáil?" if "HouseTerm" in detail else "What are the groups and parties in the 34th Dáil?"
    outcome = run(question, fixture)
    assert outcome.status == "source_data_unavailable"
    assert detail in outcome.diagnostic
    assert "does not prove that no parties existed" in outcome.diagnostic if "ParliamentaryParty" in detail else True


def test_q17_missing_party_graph_is_called_out_in_ask(monkeypatch):
    response = ask("What are the groups and parties in the 34th Dáil?",
                   StageCFixture(term=34, parties_graph=False), monkeypatch)
    assert "No typed ParliamentaryParty records" in response.text
    assert "ParliamentaryGroup data is missing" in response.text


def test_q17_empty_houses_graph_is_not_a_party_list_for_an_unknown_term():
    fixture = StageCFixture(term=34, houses_graph=False, parties_graph=False)
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "No typed HouseTerm with ordinal 34th Dáil" in outcome.diagnostic
    assert "ParliamentaryGroup data is missing" in outcome.diagnostic
    assert len(fixture.queries) == 1


def test_q17_actual_empty_party_graph_with_other_term_rows_is_not_reported_as_none():
    fixture = StageCFixture(term=34, party_count=0)
    other_term = URIRef("https://data.oireachtas.ie/ie/oireachtas/house/dail/33")
    party = URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/33/fg")
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/parties"))
    graph.add((party, RDF.type, URIRef(MEMBERS + "ParliamentaryParty")))
    graph.add((party, URIRef(MEMBERS + "activeDuringTerm"), other_term))
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "No ParliamentaryParty records linked to the exact 34th Dáil" in outcome.diagnostic
    assert "This does not prove that no parties existed" in outcome.diagnostic


@pytest.mark.parametrize("mutation", [
    "houses_owner", "houses_availability", "houses_graph", "houses_kind",
    "parties_owner", "parties_availability", "parties_graph", "parties_kind",
    "dail_class", "party_class", "term_number_predicate",
])
def test_q17_owner_class_and_term_number_gates_fail_before_fuseki(monkeypatch, mutation):
    import poc.nlq.composable_plan as composable
    import poc.nlq.stage_c as stage_c
    from poc.nlq.contract import load_query_contract

    contract = copy.deepcopy(load_query_contract())
    houses = next(item for item in contract["graphFamilies"] if item["id"] == "houses")
    parties = next(item for item in contract["graphFamilies"] if item["id"] == "parties")
    if mutation == "houses_owner": houses["owner"] = "unreviewed"
    elif mutation == "houses_availability": houses["availability"] = "unreviewed"
    elif mutation == "houses_graph": houses["graph"]["iri"] += "/wrong"
    elif mutation == "houses_kind": houses["graph"]["kind"] = "resource-pattern"
    elif mutation == "parties_owner": parties["owner"] = "unreviewed"
    elif mutation == "parties_availability": parties["availability"] = "unreviewed"
    elif mutation == "parties_graph": parties["graph"]["iri"] += "/wrong"
    elif mutation == "parties_kind": parties["graph"]["kind"] = "resource-pattern"
    elif mutation == "dail_class": contract["queryableClasses"].remove("agents:DailTerm")
    elif mutation == "party_class": contract["queryableClasses"].remove("members:ParliamentaryParty")
    elif mutation == "term_number_predicate": contract["queryableProperties"].remove("agents:termNo")
    monkeypatch.setattr(stage_c, "load_query_contract", lambda: contract)
    monkeypatch.setattr(composable, "load_query_contract", lambda: contract)
    fixture = StageCFixture(term=34)
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "unsupported_mapping"
    assert outcome.request_family == "dail_parties_and_groups"
    assert fixture.queries == []


@pytest.mark.parametrize("mutation", ["owner", "term_class", "term_number_predicate"])
def test_q16_house_owner_class_and_term_number_gates_fail_before_fuseki(monkeypatch, mutation):
    import poc.nlq.composable_plan as composable
    import poc.nlq.stage_c as stage_c
    from poc.nlq.contract import load_query_contract
    contract = copy.deepcopy(load_query_contract())
    houses = next(item for item in contract["graphFamilies"] if item["id"] == "houses")
    if mutation == "owner": houses["owner"] = "unreviewed"
    elif mutation == "term_class": contract["queryableClasses"].remove("agents:DailTerm")
    elif mutation == "term_number_predicate": contract["queryableProperties"].remove("agents:termNo")
    monkeypatch.setattr(stage_c, "load_query_contract", lambda: contract)
    monkeypatch.setattr(composable, "load_query_contract", lambda: contract)
    fixture = StageCFixture(party_count=0)
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "unsupported_mapping"
    assert outcome.request_family == "dail_seats"
    assert fixture.queries == []


def test_stage_c_contract_failure_retains_family_in_ask_without_validated_plan(monkeypatch):
    import poc.nlq.stage_c as stage_c
    fixture = StageCFixture(party_count=0)
    monkeypatch.setattr(stage_c, "_reviewed_pattern", lambda *_args: (_ for _ in ()).throw(PlanError("reviewed seat pattern was removed")))
    response = ask("How many members were in the 33rd Dáil?", fixture, monkeypatch)
    assert response.status_code == 200
    assert "reviewed seat pattern was removed" in response.text
    assert "Validated composable query plan" not in response.text
    assert "previous Dáil" not in response.text
    assert fixture.queries == []


def test_stage_c_invalid_date_keeps_family_and_reports_date_error_in_ask(monkeypatch):
    fixture = StageCFixture(party_count=0)
    response = ask("Show me the Dáil debate from 31 February 2026.", fixture, monkeypatch)
    assert response.status_code == 200
    assert "valid calendar date" in response.text
    assert "Validated composable query plan" not in response.text
    assert "previous Dáil" not in response.text
    assert fixture.queries == []


def test_q17_safety_cap_is_incomplete_not_exact_count():
    fixture = StageCFixture(term=34, party_count=100)
    outcome = run("What are the groups and parties in the 34th Dáil?", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "100-row safety cap" in outcome.diagnostic
    assert "exact" not in outcome.diagnostic.lower()


def test_q17_ask_marks_safety_cap_incomplete(monkeypatch):
    response = ask("What are the groups and parties in the 34th Dáil?", StageCFixture(term=34, party_count=100), monkeypatch)
    assert response.status_code == 200
    assert "100-row safety cap" in response.text
    assert "incomplete" in response.text.lower()


def test_q24_known_quarantine_is_distinct_from_ordinary_bill_lookup():
    fixture = StageCFixture(party_count=0)
    outcome = run("Tell me about Bill 48 from 2024.", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "bill-stage/None" in outcome.diagnostic and "does not prove the Bill never existed" in outcome.diagnostic
    assert "title" not in outcome.diagnostic.lower()
    assert plan_stage_c("Tell me about Bill 23 from 2025.", as_of=AS_OF) is None


def test_q24_ask_reports_known_source_problem_and_nonexistence_caveat(monkeypatch):
    fixture = StageCFixture(party_count=0)
    response = ask("Tell me about Bill 48 from 2024.", fixture, monkeypatch)
    assert response.status_code == 200
    assert "bill-stage/None" in response.text
    assert "does not prove the Bill never existed" in response.text
    assert "title-resolution failure" not in response.text


def test_q24_present_graph_reuses_exact_bill_lookup_instead_of_claiming_quarantine():
    fixture = StageCFixture(party_count=0, bill_graph=True)
    outcome = run("Tell me about Bill 48 from 2024.", fixture)
    assert outcome.status != "source_data_unavailable" or "quarantined" not in (outcome.diagnostic or "")
    assert any("graph/bill/2024/48" in query for query in fixture.queries)


def test_q24_present_graph_ask_does_not_report_the_known_absent_graph_problem(monkeypatch):
    response = ask("Tell me about Bill 48 from 2024.", StageCFixture(party_count=0, bill_graph=True), monkeypatch)
    assert response.status_code == 200
    assert "bill-stage/None" not in response.text
    assert "quarantined" not in response.text.lower()


def test_q24_unrelated_typed_bill_in_target_graph_does_not_trigger_known_bill_lookup():
    fixture = StageCFixture(party_count=0, bill_graph=False)
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2024/48"))
    unrelated = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/47")
    graph.add((unrelated, RDF.type, URIRef(ELI_DL + "DraftLegislationWork")))
    graph.add((unrelated, URIRef("http://data.europa.eu/eli/ontology#type_document"), URIRef(AGENTS + "Bill")))
    outcome = run("Tell me about Bill 48 from 2024.", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "exact Bill identity" in outcome.diagnostic
    assert "bill-stage/None" in outcome.diagnostic


def test_q31_local_absence_is_specific_coverage_and_written_answer_is_not_sitting():
    fixture = StageCFixture(party_count=0, written_answer=True)
    outcome = run("Show me the Dáil debate from 24 September 2026.", fixture)
    assert outcome.status == "source_data_unavailable"
    assert "queried local dataset" in outcome.diagnostic
    assert "reviewed pinned development capture also omits" in outcome.diagnostic
    assert "no debate took place" in outcome.diagnostic
    assert "debateDate" not in outcome.sparql


def test_q31_ask_reports_local_gap_not_no_debate(monkeypatch):
    response = ask("Show me the Dáil debate from 24 September 2026.", StageCFixture(party_count=0, written_answer=True), monkeypatch)
    assert response.status_code == 200
    assert "queried local dataset" in response.text
    assert "reviewed pinned development capture also omits" in response.text
    assert "not evidence that no debate took place" in response.text


def test_q31_uses_same_date_parameterized_sitting_path():
    fixture = StageCFixture(party_count=0)
    outcome = run("Show me the Dáil debate from 2 July 2015.", fixture)
    assert outcome.status == "source_data_unavailable"
    assert '"2015-07-02"^^xsd:date' in outcome.sparql


def test_q31_existing_actual_sitting_uses_readable_link_path():
    fixture = StageCFixture(party_count=0, debate=True)
    outcome = run("Show me the Dáil debate from 24 September 2026.", fixture)
    assert outcome.status == "success"
    assert "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-09-24/debate" in outcome.result.rows[0]


def test_q31_cap100_is_incomplete_and_never_exact():
    fixture = StageCFixture(party_count=0, debate=True, debate_count=100)
    outcome = run("Show me the Dáil debate from 24 September 2026.", fixture)
    assert outcome.status == "source_data_unavailable"
    assert len(outcome.result.rows) == 100
    assert "100-row safety cap" in outcome.diagnostic
    assert "incomplete" in outcome.diagnostic


class QueryFailureFixture(StageCFixture):
    def query(self, query):
        self.queries.append(query)
        raise NLQError("test query transport failure")


def test_q31_query_transport_failure_is_not_reported_as_unsupported_mapping():
    outcome = run("Show me the Dáil debate from 24 September 2026.", QueryFailureFixture(party_count=0))
    assert outcome.status == "query_execution_failed"
    assert "query could not be executed" in outcome.diagnostic


def test_q31_unexpected_query_kind_fails_closed_as_execution_failure():
    class WrongKindFixture(StageCFixture):
        def query(self, query):
            self.queries.append(query)
            return QueryResult("ask", boolean=True)
    fixture = WrongKindFixture(party_count=0)
    outcome = run("Show me the Dáil debate from 24 September 2026.", fixture)
    assert outcome.status == "query_execution_failed"
    assert "unexpected response kind" in outcome.diagnostic


@pytest.mark.parametrize(("question", "family", "phrase"), [
    ("When did PAC last examine the HSE?", "committee_topic_latest", "Committee of Public Accounts"),
    ("Which Members voted for the Artificial Intelligence Companion Services Bill?", "bill_votes", "sponsorship records are not evidence"),
    ("What did speakers say in the Dáil debate on 2 July 2015?", "debate_transcript", "no approved transcript retrieval path"),
])
def test_q30_q36_q37_render_specific_unavailability_without_answer_query(question, family, phrase, monkeypatch):
    fixture = StageCFixture(party_count=0)
    response = ask(question, fixture, monkeypatch)
    assert response.status_code == 200
    assert family.replace("_", " ").title() in response.text or "Validated composable query plan" in response.text
    assert phrase.lower() in response.text.lower()
    assert fixture.queries == []
    assert "Validated composable query plan" in response.text
    assert AS_OF.isoformat() in response.text


def test_q36_sponsor_graph_decoy_is_never_queried_as_vote_evidence(monkeypatch):
    fixture = StageCFixture(party_count=0)
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2024/1"))
    bill = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1")
    process = URIRef(str(bill) + "#process")
    participation = URIRef(str(process) + "#participation")
    graph.add((process, RDF.type, URIRef(ELI_DL + "LegislativeProcess")))
    graph.add((process, URIRef(ELI_DL + "had_participation"), participation))
    graph.add((participation, URIRef("http://data.europa.eu/eli/eli-draft-legislation-ontology#had_participant_person"), URIRef("https://data.oireachtas.ie/member/decoy")))
    response = ask("Which Members voted for the Artificial Intelligence Companion Services Bill?", fixture, monkeypatch)
    assert response.status_code == 200
    assert fixture.queries == []
    assert "sponsorship records are not evidence" in response.text


@pytest.mark.parametrize("mutation", ["selector", "answer", "relation", "family"])
def test_stage_c_plans_reject_mutations(mutation):
    plan = plan_stage_c("How many members were in the 33rd Dáil?", as_of=AS_OF)
    if mutation == "selector": plan["referents"]["term"]["selector"]["number"] = 0
    if mutation == "answer": plan["answer"]["referent"] = "party"
    if mutation == "relation": plan["relations"].append({"id": "x", "fact": "invented", "from": "term", "to": "term"})
    if mutation == "family": plan["family"] = "dail_parties_and_groups"
    with pytest.raises(PlanError): validate_plan(plan)


@pytest.mark.parametrize("question", [
    "How many members were in the 33rd Dáil?",
    "What are the groups and parties in the 34th Dáil?",
    "Tell me about Bill 48 from 2024.",
    "Show me the Dáil debate from 24 September 2026.",
    "When did PAC last examine the HSE?",
    "Which Members voted for the Artificial Intelligence Companion Services Bill?",
    "What did speakers say in the Dáil debate on 2 July 2015?",
])
def test_stage_c_plans_conform_to_shared_v2_json_schema(question):
    import json
    from jsonschema import Draft202012Validator
    plan = plan_stage_c(question, as_of=AS_OF)
    schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    Draft202012Validator(schema).validate(plan)


def test_stage_c_missing_reviewed_seat_pattern_fails_before_query(monkeypatch):
    import poc.nlq.stage_c as stage_c
    fixture = StageCFixture(party_count=0)
    monkeypatch.setattr(stage_c, "_reviewed_pattern", lambda *_args: (_ for _ in ()).throw(PlanError("seat pattern unavailable")))
    outcome = run("How many members were in the 33rd Dáil?", fixture)
    assert outcome.status == "unsupported_mapping"
    assert fixture.queries == []


def test_q31_app_renders_actual_result_link_and_not_just_metadata():
    fixture = StageCFixture(party_count=0, debate=True)
    from poc.nlq import app as app_module
    from unittest.mock import patch
    with patch.dict("os.environ", {"OIR_NLQ_AS_OF_DATE": AS_OF.isoformat()}), \
         patch.object(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture):
        response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
            "question": "Show me the Dáil debate from 24 September 2026.", "mode": "phase2"})
    assert response.status_code == 200
    assert "Thursday 24 September 2026" in response.text
    assert 'href="https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-09-24/debate"' in response.text
    assert "Official debate record" in response.text
