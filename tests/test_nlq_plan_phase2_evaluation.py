"""Deterministic Phase 2 query cases stay within the reviewed local contract."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from poc.nlq.plan_contract import validate_query_plan
from poc.nlq.plan_sparql import PlanSparqlGenerator, build_label_lookup_query
from poc.nlq.structured_planner import PlannerResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
EVALUATION_PATH = ROOT / "poc/nlq/benchmarks/query-service-phase-2-v1.json"
PLAN_SCHEMA = json.loads((ROOT / "poc/specs/query-plan.schema.json").read_text(encoding="utf-8"))
PLAN_SCHEMA_VALIDATOR = Draft202012Validator(PLAN_SCHEMA)


def _evaluation_cases():
    document = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["dataset_evidence"]["dataset_id"] == (
        "sha256:9da63abc5878387f991e4d4717f35cca67606850db34be589e0a8fc0cc1504e2"
    )
    cases = document["cases"]
    assert 8 <= len(cases) <= 12
    assert len({case["id"] for case in cases}) == len(cases)
    return cases


CASES = _evaluation_cases()
GENERATOR = PlanSparqlGenerator(
    supported_predicates=supported_predicates(ROOT / "ontology"),
)


def test_evaluation_fixtures_are_pinned_to_non_authoritative_development_data():
    document = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    assert document["dataset_evidence"]["status"] == "non-authoritative-development-bootstrap"
    assert len(document["constraints"]) >= 3
    assert sum("bill_sponsor" in json.dumps(case["plan"]) for case in CASES) == 1


def test_each_phase2_case_is_a_valid_deterministic_safe_plan():
    for case in CASES:
        assert list(PLAN_SCHEMA_VALIDATOR.iter_errors(case["plan"])) == [], case["id"]
        plan = validate_query_plan(case["plan"])
        first = GENERATOR.generate(PlannerResult("validated_plan", plan=plan))
        second = GENERATOR.generate(PlannerResult("validated_plan", plan=plan))

        assert first.generated, (case["id"], first.as_dict())
        assert first.query_form.lower() == case["expected_result"]["kind"]
        assert first.as_dict() == second.as_dict()


def test_bill_sponsor_is_the_only_cross_family_evaluation_case():
    case = next(case for case in CASES if case["id"] == "bill.sponsor-member-join")
    result = GENERATOR.generate(PlannerResult(
        "validated_plan", plan=validate_query_plan(case["plan"]),
    ))
    assert result.generated
    [trace] = result.generation_trace["requirements"]
    assert set(trace["graph_families"]) == {"bill-records", "member-records"}
    assert "eli-dl:had_participant_person" in result.sparql
    assert "SERVICE" not in result.sparql


def test_officeholding_date_query_is_inclusive_and_open_ended():
    case = next(case for case in CASES if case["id"] == "officeholding.open-ended-taoiseach")
    result = GENERATOR.generate(PlannerResult(
        "validated_plan", plan=validate_query_plan(case["plan"]),
    ))
    assert result.generated
    assert "members:StartDate ?officeStart0" in result.sparql
    assert "OPTIONAL {" in result.sparql
    assert "members:EndDate ?officeEnd0" in result.sparql
    assert "!BOUND(?officeEnd0) || ?officeEnd0 >=" in result.sparql
    assert "FILTER(?heldOffice0 = ?entity1)" in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/offices>" not in result.sparql


def test_debate_date_and_chamber_use_source_date_and_canonical_graph_route():
    case = next(case for case in CASES if case["id"] == "debate.dail-date-identity")
    result = GENERATOR.generate(PlannerResult(
        "validated_plan", plan=validate_query_plan(case["plan"]),
    ))
    assert result.generated
    assert "agents:debateDate" in result.sparql
    assert "agents:DebateRecord" in result.sparql
    assert "graph/debate/dail/[0-9]{4}-[0-9]{2}-[0-9]{2}/debate" in result.sparql
    assert "members:inHouseTerm" not in result.sparql
    assert "SERVICE" not in result.sparql


def test_bill_status_uses_reviewed_process_status_iris_and_english_labels():
    case = next(case for case in CASES if case["id"] == "bill.status-label")
    result = GENERATOR.generate(PlannerResult(
        "validated_plan", plan=validate_query_plan(case["plan"]),
    ))
    assert result.generated
    assert "eli-dl:process_status" in result.sparql
    assert "https://data.oireachtas.ie/ontology#CurrentBill" in result.sparql
    assert '"Current"' in result.sparql
    assert "GRAPH <https://data.oireachtas.ie/graph/" not in result.sparql


def test_explicit_bill_status_filter_is_distinct_from_temporal_currentness():
    case = next(case for case in CASES if case["id"] == "bill.status-current-filter")
    result = GENERATOR.generate(PlannerResult(
        "validated_plan", plan=validate_query_plan(case["plan"]),
    ))
    assert result.generated
    assert result.query_form == "ASK"
    assert "FILTER(?billStatus0 = <https://data.oireachtas.ie/ontology#CurrentBill>)" in result.sparql


def test_bill_and_named_office_label_lookups_are_scoped_to_their_owner_graphs():
    bill_query = build_label_lookup_query(
        "Bill", "https://data.oireachtas.ie/ie/oireachtas/bill/2026/93",
        supported_predicates=GENERATOR.supported_predicates,
    )
    office_query = build_label_lookup_query(
        "NamedOffice", "https://data.oireachtas.ie/office/o-000001",
        supported_predicates=GENERATOR.supported_predicates,
    )

    assert "eli:title" in bill_query
    assert "eli:type_document agents:Bill" in bill_query
    assert "/graph/bill/[^/]+/[^/]+" in bill_query
    assert "GRAPH <https://data.oireachtas.ie/graph/offices>" in office_query
    assert "members:NamedOffice" in office_query
