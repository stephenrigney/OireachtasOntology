"""Bounded Q35 checks over synthetic RDF and reviewed office identity mapping."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from poc.nlq.composable_plan import PlanError, execute_question, plan_question, validate_plan
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 25)
QUESTION = "Who was Minister for Finance from January 2021 to December 2022?"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
AGENTS = "https://data.oireachtas.ie/ontology#"
FOAF_NAME = URIRef("http://xmlns.com/foaf/0.1/name")
OFFICE_GRAPH = URIRef("https://data.oireachtas.ie/graph/offices")
FINANCE_OFFICE = URIRef("https://data.oireachtas.ie/office/o-000003")


class Q35Fixture:
    """Tiny Member-owned evidence fixture; the office resource is reviewed local data."""

    def __init__(self, *, ambiguous_office: bool = False, with_holders: bool = True):
        self.dataset = Dataset()
        self.queries: list[str] = []
        registry = self.dataset.graph(OFFICE_GRAPH)
        registry.add((FINANCE_OFFICE, RDF.type, URIRef(MEMBERS + "NamedOffice")))
        registry.add((FINANCE_OFFICE, SKOS.prefLabel, Literal("Minister for Finance", lang="en")))
        self.decoy_office = URIRef("https://data.oireachtas.ie/office/decoy-finance")
        registry.add((self.decoy_office, RDF.type, URIRef(MEMBERS + "NamedOffice")))
        registry.add((self.decoy_office, SKOS.prefLabel, Literal("Department of Finance", lang="en")))
        if ambiguous_office:
            alternate = URIRef("https://data.oireachtas.ie/office/alternate-finance")
            registry.add((alternate, RDF.type, URIRef(MEMBERS + "NamedOffice")))
            registry.add((alternate, SKOS.prefLabel, Literal("Minister for Finance", lang="en")))

        if with_holders:
            self.add_member("paschal", "Paschal Donohoe", [
                ("2020-06-27T00:00:00", "2022-12-17T00:00:00"),
            ])
            self.add_member("michael", "Michael McGrath", [
                ("2022-12-17T00:00:00", "2024-04-09T00:00:00"),
            ])
            self.add_member("end-boundary", "End Boundary Holder", [
                ("2022-12-31T23:59:59", None),
            ])
            self.add_member("start-boundary", "Start Boundary Holder", [
                ("2019-01-01T00:00:00", "2021-01-01T00:00:00"),
            ])
            self.add_member("open-ended", "Open-ended Holder", [
                ("2022-01-01T00:00:00", None),
            ])
            self.add_member("repeat", "Repeat Holder", [
                ("2021-03-01T00:00:00", "2021-09-01T00:00:00"),
                ("2022-04-01T00:00:00", "2022-10-01T00:00:00"),
            ])
            self.add_member("before", "Before Window Holder", [
                ("2019-01-01T00:00:00", "2020-12-31T23:59:59"),
            ])
            self.add_member("after", "After Window Holder", [
                ("2023-01-01T00:00:00", None),
            ])
            self.add_member("decoy", "Decoy Office Holder", [
                ("2021-01-01T00:00:00", "2022-12-31T00:00:00"),
            ], office=self.decoy_office)

    def add_member(
        self,
        code: str,
        name: str,
        episodes: list[tuple[str | None, str | None]],
        *,
        office: URIRef = FINANCE_OFFICE,
        missing_range: bool = False,
        start_datatype=XSD.dateTime,
    ) -> None:
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{code}"))
        member = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/member/id/{code}")
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, FOAF_NAME, Literal(name)))
        for index, (start, end) in enumerate(episodes):
            holding = URIRef(f"{member}#office-holding-{index}")
            date_range = URIRef(f"{holding}#date-range")
            graph.add((member, URIRef(MEMBERS + "hasOfficeHolding"), holding))
            graph.add((holding, RDF.type, URIRef(MEMBERS + "OfficeHolding")))
            graph.add((holding, URIRef(MEMBERS + "heldOffice"), office))
            if not missing_range:
                graph.add((holding, URIRef(MEMBERS + "hasMembershipDateRange"), date_range))
                graph.add((date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
                if start is not None:
                    graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=start_datatype)))
                if end is not None:
                    graph.add((date_range, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))

    def readiness(self):
        names = ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")
        return FusekiReadiness("ready", True, tuple((name, True) for name in names), "bounded Q35 fixture")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        result = self.dataset.query(query)
        if result.type != "SELECT":
            raise AssertionError(f"unexpected query form: {result.type}")
        columns = tuple(str(variable) for variable in result.vars)
        rows = []
        for result_row in result:
            row = []
            for value in result_row:
                if value is None:
                    row.append("—")
                elif isinstance(value, Literal) and value.datatype:
                    row.append(f"{value}^^<{value.datatype}>")
                elif isinstance(value, Literal) and value.language:
                    row.append(f"{value}@{value.language}")
                else:
                    row.append(str(value))
            rows.append(tuple(row))
        return QueryResult("select", columns, tuple(rows))


def _run(fixture: Q35Fixture, question: str = QUESTION):
    return execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )


def test_q35_plan_is_typed_inclusive_and_uses_the_three_node_office_path():
    plan = plan_question(QUESTION, as_of=AS_OF)
    schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(plan)
    assert set(plan["referents"]) == {"member", "holding", "office"}
    assert [item["fact"] for item in plan["relations"]] == [
        "member_has_office_holding", "office_holding_of_office",
    ]
    assert plan["constraints"] == [{
        "referent": "holding", "field": "interval", "operator": "overlaps",
        "value": {"start": "2021-01-01", "end": "2022-12-31", "inclusive": True},
    }]
    assert plan["answer"]["distinctBy"] == "identity"
    assert plan["answer"]["preserveEpisodes"] is True


@pytest.mark.parametrize("mutation", [
    "unsupported_relation", "malformed_relation", "malformed_resolution",
    "extra_referent_attribute", "exclusive_window", "wrong_constraint",
])
def test_q35_rejects_unsupported_plan_relations_and_attributes(mutation):
    plan = plan_question(QUESTION, as_of=AS_OF)
    if mutation == "unsupported_relation":
        plan["relations"][1]["fact"] = "office_inferred_from_label"
    elif mutation == "malformed_relation":
        plan["relations"][1]["fact"] = ["office_holding_of_office"]
    elif mutation == "malformed_resolution":
        plan["referents"]["office"]["resolution"] = []
    elif mutation == "extra_referent_attribute":
        plan["referents"]["office"]["sourceLabel"] = "Minister for Finance"
    elif mutation == "exclusive_window":
        plan["constraints"][0]["value"]["inclusive"] = False
    else:
        plan["constraints"][0]["operator"] = "during"
    with pytest.raises(PlanError):
        validate_plan(plan)


def test_composable_instance_schema_preserves_q06_q09_and_debate_plan_shapes():
    from poc.nlq.composable_plan import plan_question

    schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    validator = Draft202012Validator(schema)
    plans = (
        plan_question("What parties was Stephen Donnelly a member of?", as_of=AS_OF),
        plan_question("Who were the TDs for Dublin South Central in the last Dáil?", as_of=AS_OF),
        plan_question("Show me the Dáil debate from 2 July 2015.", as_of=AS_OF),
        plan_question("Was there a Seanad debate on 2 July 2015?", as_of=AS_OF),
    )
    assert all(validator.is_valid(plan) for plan in plans)


def test_q35_uses_reviewed_local_office_iri_and_member_graph_patterns_with_safe_overlap_sparql():
    fixture = Q35Fixture()
    outcome = _run(fixture)
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.plan["referents"]["office"]["iri"] == str(FINANCE_OFFICE)
    assert "GRAPH <https://data.oireachtas.ie/graph/offices>" in outcome.sparql
    assert "GRAPH ?memberGraph" in outcome.sparql
    assert "members:hasOfficeHolding" in outcome.sparql
    assert "members:OfficeHolding" in outcome.sparql
    assert "members:heldOffice" in outcome.sparql
    assert f"<{FINANCE_OFFICE}>" in outcome.sparql
    assert "members:hasMembershipDateRange" in outcome.sparql
    assert "members:StartDate" in outcome.sparql and "members:EndDate" in outcome.sparql
    assert 'DATATYPE(?holdingStart) = xsd:dateTime' in outcome.sparql
    assert '"2023-01-01T00:00:00"^^xsd:dateTime' in outcome.sparql
    assert '"2021-01-01T00:00:00"^^xsd:dateTime' in outcome.sparql
    assert "SERVICE" not in outcome.sparql and "FROM NAMED" not in outcome.sparql
    assert outcome.sparql.startswith("PREFIX")


def test_q35_inclusive_overlap_returns_changes_boundaries_open_ends_and_distinct_episodes():
    outcome = _run(Q35Fixture())
    assert outcome.status == "success", outcome.diagnostic
    assert outcome.result.columns == ("Member", "Holding start", "Holding end")
    assert outcome.result.rows == (
        ("Start Boundary Holder", "2019-01-01", "2021-01-01"),
        ("Paschal Donohoe", "2020-06-27", "2022-12-17"),
        ("Repeat Holder", "2021-03-01", "2021-09-01"),
        ("Open-ended Holder", "2022-01-01", "Open-ended (no end date recorded)"),
        ("Repeat Holder", "2022-04-01", "2022-10-01"),
        ("Michael McGrath", "2022-12-17", "2024-04-09"),
        ("End Boundary Holder", "2022-12-31 23:59:59", "Open-ended (no end date recorded)"),
    )
    assert "Before Window Holder" not in repr(outcome.result.rows)
    assert "After Window Holder" not in repr(outcome.result.rows)
    assert "Decoy Office Holder" not in repr(outcome.result.rows)
    assert "historical completeness is not certified" in outcome.diagnostic


def test_q35_missing_or_wrong_start_evidence_is_excluded_and_reported_as_insufficient():
    fixture = Q35Fixture()
    fixture.add_member("missing-start", "Missing Start Holder", [(None, "2022-12-31T00:00:00")])
    fixture.add_member("wrong-start-type", "Wrong Datatype Holder", [("2022-01-01", None)], start_datatype=XSD.date)
    fixture.add_member("missing-range", "Missing Date Range Holder", [("2022-01-01T00:00:00", None)], missing_range=True)
    outcome = _run(fixture)
    assert outcome.status == "insufficient_holding_evidence"
    assert outcome.result is not None
    assert "Paschal Donohoe" in repr(outcome.result.rows)
    assert "Missing Start Holder" not in repr(outcome.result.rows)
    assert "Wrong Datatype Holder" not in repr(outcome.result.rows)
    assert "Missing Date Range Holder" not in repr(outcome.result.rows)
    assert "xsd:dateTime start evidence" in outcome.diagnostic


def test_q35_distinguishes_unresolved_ambiguous_office_and_missing_local_holdings():
    supported = supported_predicates(ROOT / "ontology")
    missing_office_fixture = Q35Fixture()
    missing = execute_question(
        "Who was Unknown Minister from January 2021 to December 2022?", as_of=AS_OF,
        fuseki=missing_office_fixture, supported_predicates=supported,
    )
    assert missing.status == "not_found"
    assert len(missing_office_fixture.queries) == 1

    ambiguous_fixture = Q35Fixture(ambiguous_office=True)
    ambiguous = _run(ambiguous_fixture)
    assert ambiguous.status == "ambiguous"
    assert len(ambiguous.candidates) == 2
    assert len(ambiguous_fixture.queries) == 1

    no_holdings = _run(Q35Fixture(with_holders=False))
    assert no_holdings.status == "source_data_unavailable"
    assert "No accepted Member-owned OfficeHolding" in no_holdings.diagnostic


def test_q35_no_local_overlap_is_not_presented_as_a_confirmed_historical_negative():
    fixture = Q35Fixture(with_holders=False)
    fixture.add_member("past", "Past Holder", [("2019-01-01T00:00:00", "2020-12-31T23:59:59")])
    outcome = _run(fixture)
    assert outcome.status == "source_data_unavailable"
    assert outcome.sparql and "holdingStart" in outcome.sparql
    assert "not a confirmed historical negative" in outcome.diagnostic


def test_q35_ui_renders_readable_episodes_open_ends_coverage_and_missing_evidence(monkeypatch):
    from poc.nlq import app as app_module

    fixture = Q35Fixture()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Paschal Donohoe" in response.text and "Michael McGrath" in response.text
    assert "2020-06-27" in response.text and "2022-12-17" in response.text
    assert "Open-ended (no end date recorded)" in response.text
    assert "does not establish complete historical coverage" in response.text
    assert "Validated composable query plan" in response.text

    incomplete = Q35Fixture()
    incomplete.add_member("missing", "Date Evidence Missing", [(None, None)])
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: incomplete)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert "Office-holding dates incomplete" in response.text
    assert "Date Evidence Missing" not in response.text


def test_q35_ui_distinguishes_office_resolution_mapping_and_absent_holding_outcomes(monkeypatch):
    from poc.nlq import app as app_module
    from poc.nlq import composable_plan as composable_module

    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    fixture = Q35Fixture()
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    missing = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Who was Unknown Minister from January 2021 to December 2022?", "mode": "phase2",
    })
    assert "Entity not found" in missing.text
    assert "reviewed local NamedOffice identity" in missing.text

    ambiguous_fixture = Q35Fixture(ambiguous_office=True)
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: ambiguous_fixture)
    ambiguous = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert "Ambiguous entity" in ambiguous.text
    assert "no office was selected" in ambiguous.text
    assert "Possible local matches for" in ambiguous.text

    no_holding_fixture = Q35Fixture(with_holders=False)
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: no_holding_fixture)
    no_holding = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert "Source evidence unavailable" in no_holding.text
    assert "No accepted local office-holding records are available" in no_holding.text

    original = composable_module._reviewed_predicate

    def reject_office_cross_graph_mapping(fact):
        if fact == "office_holding_of_office":
            raise PlanError("No reviewed member-records to offices join exists.")
        return original(fact)

    monkeypatch.setattr(composable_module, "_reviewed_predicate", reject_office_cross_graph_mapping)
    mapping_fixture = Q35Fixture()
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: mapping_fixture)
    unsupported = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert "Unsupported query mapping" in unsupported.text
    assert "query mapping is unsupported" in unsupported.text


def test_q35_join_contract_matches_accepted_member_mapping_and_office_graph_ownership():
    contract = json.loads((ROOT / "poc/specs/query-schema-contract.json").read_text())
    join = next(item for item in contract["crossGraphJoins"]
                if item["predicate"] == "members:heldOffice")
    assert (join["fromGraphFamily"], join["toGraphFamily"]) == ("member-records", "offices")
    assert join["joinKey"] == "same RDF resource IRI"

    registry = json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())
    finance = next(item for item in registry["offices"] if item["key"] == "o-000003")
    assert finance["label_en"] == "Minister for Finance"
    assert str(FINANCE_OFFICE) == f"https://data.oireachtas.ie/office/{finance['key']}"

    with (ROOT / "mappings/member_mapping.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    office_rows = [row for row in rows if row["json_path"].startswith("member.memberships[].membership.offices[]")]
    assert any(row["ontology_term"] == "members:OfficeHolding" and row["mapping_status"] == "new" for row in office_rows)
    assert any(row["ontology_term"] == "members:heldOffice" and "reviewed local office_iri" in row["notes"] for row in office_rows)
    assert any(row["ontology_term"] == "members:hasMembershipDateRange" for row in office_rows)
    assert any(row["ontology_term"] == "members:StartDate" and "xsd:dateTime" in row["notes"] for row in office_rows)
    assert any(row["ontology_term"] == "members:EndDate" and "null = open-ended" in row["notes"] for row in office_rows)
