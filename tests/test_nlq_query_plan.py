from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from poc.nlq.plan_contract import (
    CONTRACT_PATH,
    QueryPlanContractError,
    load_query_plan,
    load_query_plan_contract,
    validate_query_plan,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "poc/specs/query-plan-examples"
CONTRACT_SCHEMA_PATH = ROOT / "poc/specs/query-plan-contract.schema.json"
PLAN_SCHEMA_PATH = ROOT / "poc/specs/query-plan.schema.json"
CONTRACT_ID = "https://data.oireachtas.ie/specs/query-plan-contract"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _example(name: str = "member-lookup.json") -> dict:
    return _read_json(EXAMPLES / name)


def _write_json(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _assert_schema_valid(document: dict, schema_path: Path = PLAN_SCHEMA_PATH) -> None:
    schema = _read_json(schema_path)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    assert not errors, "\n".join(
        f"{list(error.absolute_path)}: {error.message}" for error in errors
    )


def _assert_schema_invalid(document: dict, schema_path: Path = PLAN_SCHEMA_PATH) -> None:
    schema = _read_json(schema_path)
    errors = list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document)
    )
    assert errors


def _mutated_plan(mutate, *, name: str = "member-lookup.json") -> dict:
    plan = copy.deepcopy(_example(name))
    mutate(plan)
    return plan


def test_contract_manifest_plan_schema_and_all_examples_are_valid():
    contract_schema = _read_json(CONTRACT_SCHEMA_PATH)
    plan_schema = _read_json(PLAN_SCHEMA_PATH)
    Draft202012Validator.check_schema(contract_schema)
    Draft202012Validator.check_schema(plan_schema)

    manifest = _read_json(CONTRACT_PATH)
    errors = list(
        Draft202012Validator(
            contract_schema, format_checker=FormatChecker(),
        ).iter_errors(manifest)
    )
    assert errors == []
    contract = load_query_plan_contract()
    assert contract["contractId"] == CONTRACT_ID
    assert contract["schemaVersion"] == 1
    assert contract["contractVersion"] == "1.0.0"
    assert contract["contractSchema"] == "poc/specs/query-plan-contract.schema.json"
    assert contract["planSchema"] == "poc/specs/query-plan.schema.json"
    assert "conjunctively" in contract["planSemantics"]["conjunction"]
    assert "not executable identity bindings" in contract["planSemantics"]["resolutionReadiness"]

    example_paths = sorted(EXAMPLES.glob("*.json"))
    assert len(example_paths) >= 7
    for path in example_paths:
        plan = _read_json(path)
        _assert_schema_valid(plan)
        assert validate_query_plan(plan) == plan
        assert load_query_plan(path) == plan


def test_compatible_minor_and_patch_versions_and_unknown_optional_fields_are_accepted(tmp_path):
    plan = _example()
    plan["contractVersion"] = "1.8.3"
    plan["diagnosticExtension"] = {"origin": "future-compatible-consumer"}

    assert validate_query_plan(plan) == plan
    _assert_schema_valid(plan)

    manifest = _read_json(CONTRACT_PATH)
    manifest["contractVersion"] = "1.3.7"
    manifest_path = _write_json(tmp_path / "query-plan-contract.json", manifest)
    assert load_query_plan_contract(manifest_path)["contractVersion"] == "1.3.7"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda plan: plan.update(schemaVersion=2), "Unsupported query plan schema version 2"),
        (lambda plan: plan.update(contractVersion="2.0.0"), "Unsupported query plan contract major version 2"),
        (lambda plan: plan.update(contractVersion="1.0"), "semantic version"),
        (lambda plan: plan.update(contractId="https://example.test/other-contract"), "contractId"),
        (lambda plan: plan.update(source="wikidata"), "source must be 'oireachtas'"),
        (lambda plan: plan.update(sparql="SELECT * WHERE {}"), "implementation-specific field"),
        (lambda plan: plan.update(namedGraphs=["https://data.oireachtas.ie/graph/houses"]), "implementation-specific field"),
        (lambda plan: plan.update(prefixes={"agents": "https://data.oireachtas.ie/ontology#"}), "implementation-specific field"),
        (lambda plan: plan.update(variables=["member"]), "implementation-specific field"),
        (lambda plan: plan.update(endpoint="https://example.test/sparql"), "implementation-specific field"),
        (lambda plan: plan.update(limit=10), "implementation-specific field"),
    ],
)
def test_plan_versions_scope_and_public_semantic_boundary_fail_closed(mutate, message):
    plan = _mutated_plan(mutate)
    # The JSON Schema checks SemVer shape; the consumer enforces the supported
    # major-version boundary against its loaded contract.
    if "contract major version" not in message:
        _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda manifest: manifest.update(schemaVersion=2), "Unsupported query-plan contract schema version 2"),
        (lambda manifest: manifest.update(contractVersion="2.0.0"), "Unsupported query-plan contract contract major version 2"),
        (lambda manifest: manifest.update(contractVersion="01.0.0"), "semantic version"),
        (lambda manifest: manifest.update(planSchema="poc/specs/other.schema.json"), "planSchema"),
        (lambda manifest: manifest["scope"].update(sourceSelection=True), "must not enable source selection"),
    ],
)
def test_contract_manifest_rejects_unsupported_compatibility_and_scope(tmp_path, mutate, message):
    manifest = _read_json(CONTRACT_PATH)
    mutate(manifest)
    path = _write_json(tmp_path / "query-plan-contract.json", manifest)

    with pytest.raises(QueryPlanContractError, match=message):
        load_query_plan_contract(path)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda entity: entity.pop("iri"), "must be a local Oireachtas IRI"),
        (lambda entity: entity.update(candidates=[]), "must not contain candidates"),
        (lambda entity: entity.update(iri="https://example.test/member/1"), "local Oireachtas IRI"),
        (lambda entity: entity.update(iri="http://data.oireachtas.ie/member/1"), "local Oireachtas IRI"),
        (lambda entity: entity.update(iri="https://data.oireachtas.ie/member/1#fragment"), "local Oireachtas IRI"),
        (lambda entity: entity.update(iri="HTTPS://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"), "local Oireachtas IRI"),
        (lambda entity: entity.update(iri="https://data.oireachtas.ie/"), "local Oireachtas IRI"),
        (lambda entity: entity.update(type="UnknownEntity"), "unsupported value"),
        (lambda entity: entity.update(resolution="pending"), "unsupported value"),
    ],
)
def test_resolved_entity_requires_one_usable_local_iri(mutate, message):
    plan = _mutated_plan(lambda value: mutate(value["entities"][0]))
    _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda entity: entity.update(iri="https://data.oireachtas.ie/ie/oireachtas/member/id/selected"), "must not select a resolved IRI"),
        (lambda entity: entity.update(candidates=[{"iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/one", "label": "Michael Collins"}]), "at least two candidates"),
        (lambda entity: entity.update(candidates=[
            {"iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/one", "label": "Michael Collins"},
            {"iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/one", "label": "Michael Collins"},
        ]), "duplicate candidate IRI"),
        (lambda entity: entity.update(candidates=[
            {"iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/one", "label": "Michael Collins"},
            {"iri": "https://example.test/member/two", "label": "Michael Collins"},
        ]), "local Oireachtas IRI"),
    ],
)
def test_ambiguous_entity_has_multiple_distinct_candidates_and_no_selection(mutate, message):
    plan = _mutated_plan(
        lambda value: mutate(value["entities"][0]), name="ambiguous-member.json",
    )
    _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda entity: entity.update(iri="https://data.oireachtas.ie/ie/oireachtas/member/id/guess"), "must not contain an IRI or candidates"),
        (lambda entity: entity.update(candidates=[]), "must not contain an IRI or candidates"),
        (lambda entity: entity.update(candidates=[{"iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/one", "label": "Unknown Member"}]), "must not contain an IRI or candidates"),
    ],
)
def test_unresolved_entity_carries_no_resolved_iri_or_candidates(mutate, message):
    plan = _mutated_plan(
        lambda value: mutate(value["entities"][0]), name="unresolved-member.json",
    )
    _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


def test_entity_resolution_examples_preserve_duplicate_member_identities():
    ambiguous = _example("ambiguous-member.json")["entities"][0]
    candidate_iris = {candidate["iri"] for candidate in ambiguous["candidates"]}
    assert ambiguous["resolution"] == "ambiguous"
    assert len(candidate_iris) == 2
    assert len({candidate["label"] for candidate in ambiguous["candidates"]}) == 1
    assert "iri" not in ambiguous
    assert _example("unresolved-member.json")["entities"][0]["resolution"] == "unresolved"


def test_valid_unresolved_reference_is_preserved_instead_of_dropped_from_a_filter():
    plan = _mutated_plan(
        lambda value: value.update(
            entities=[{
                "id": "party",
                "type": "ParliamentaryMemberCollection",
                "label": "Unknown local collection",
                "resolution": "unresolved",
            }],
            requirements=[{
                "id": "membership",
                "fact": "Membership in a parliamentary collection",
                "subject": {"type": "Member"},
                "object": {"type": "ParliamentaryMemberCollection"},
            }],
            filters=[{
                "requirement": "membership",
                "field": "collection",
                "operator": "equals",
                "value": {"entity": "party"},
            }],
            answerShape={"kind": "entities", "entityType": "Member"},
        ),
    )

    validate_query_plan(plan)
    _assert_schema_valid(plan)


@pytest.mark.parametrize(
    "constraint",
    [
        {"target": "membership", "kind": "on", "date": "2024-02-29"},
        {"target": "membership", "kind": "before", "date": "2024-02-29"},
        {"target": "membership", "kind": "after", "date": "2024-02-29"},
        {"target": "membership", "kind": "during", "period": {"start": "2020-01-01", "end": "2020-12-31"}},
        {"target": "membership", "kind": "current"},
    ],
)
def test_supported_temporal_constraint_shapes_validate(constraint):
    plan = _mutated_plan(
        lambda value: value.update(
            requirements=[{"id": "membership", "fact": "membership", "subject": {"entity": "member"}}],
            temporalConstraints=[constraint],
            answerShape={"kind": "list", "target": "membership"},
        ),
        name="member-lookup.json",
    )
    validate_query_plan(plan)
    _assert_schema_valid(plan)


@pytest.mark.parametrize(
    "constraint, message",
    [
        ({"target": "membership", "kind": "on"}, "requires only a date value"),
        ({"target": "membership", "kind": "before", "date": "2024-02-30"}, "valid ISO calendar date"),
        ({"target": "membership", "kind": "during", "period": {"entity": "member"}}, "must be a DailTerm or SeanadTerm"),
        ({"target": "membership", "kind": "during", "period": {"start": "2021-01-01", "end": "2020-01-01"}}, "on or before period.end"),
        ({"target": "membership", "kind": "interval", "start": "2021-01-01", "end": "2020-01-01"}, "on or before end"),
        ({"target": "missing", "kind": "current"}, "unknown requirement"),
        ({"target": "membership", "kind": "since"}, "unsupported value"),
        ({"target": "membership", "kind": "current", "date": "2024-01-01"}, "must not contain date or period values"),
    ],
)
def test_invalid_temporal_shapes_and_cross_references_fail(constraint, message):
    plan = _mutated_plan(
        lambda value: value.update(
            requirements=[{"id": "membership", "fact": "membership", "subject": {"entity": "member"}}],
            temporalConstraints=[constraint],
            answerShape={"kind": "list", "target": "membership"},
        ),
    )
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


def test_count_and_grouped_aggregation_shapes_are_coherent():
    count = _example("count-collection-members.json")
    validate_query_plan(count)

    grouped = copy.deepcopy(count)
    grouped["aggregation"]["groupBy"] = [
        {"requirement": "membership", "participant": "object"}
    ]
    grouped["answerShape"] = {"kind": "grouped_result", "target": "aggregation"}
    validate_query_plan(grouped)
    _assert_schema_valid(grouped)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda plan: plan["aggregation"].update(operation="sum"), "unsupported value"),
        (lambda plan: plan["aggregation"].update(target={"requirement": "missing", "participant": "subject"}), "unknown requirement"),
        (lambda plan: (
            plan["requirements"][0].pop("object"),
            plan["aggregation"].update(target={"requirement": "membership", "participant": "object"}),
        ), "missing object participant"),
        (lambda plan: plan["aggregation"].update(groupBy=[{"requirement": "membership", "participant": "object"}]), "without groupBy"),
        (lambda plan: plan.update(answerShape={"kind": "grouped_result", "target": "aggregation"}), "at least one groupBy"),
        (lambda plan: plan.update(answerShape={"kind": "list", "target": "membership"}), "only compatible with count"),
        (lambda plan: plan.update(aggregation=None), "requires an aggregation"),
    ],
)
def test_invalid_aggregation_and_answer_shape_combinations_fail(mutate, message):
    plan = _mutated_plan(mutate, name="count-collection-members.json")
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "shape",
    [
        {"kind": "boolean"},
        {"kind": "entity", "entityType": "Member"},
        {"kind": "entities", "entityType": "Member"},
        {"kind": "fact", "target": "member-name"},
    ],
)
def test_non_aggregate_answer_shapes_validate_when_their_targets_are_coherent(shape):
    plan = _mutated_plan(lambda value: value.update(answerShape=shape))
    validate_query_plan(plan)
    _assert_schema_valid(plan)


@pytest.mark.parametrize(
    "shape, message",
    [
        ({"kind": "table"}, "unsupported value"),
        ({"kind": "entities"}, "requires entityType"),
        ({"kind": "entity", "entityType": "SeanadPanel"}, "not requested by any requirement"),
        ({"kind": "label", "target": "missing"}, "unknown requirement"),
        ({"kind": "boolean", "target": "member-name"}, "must not specify target"),
        ({"kind": "count", "target": "aggregation"}, "requires an aggregation"),
    ],
)
def test_invalid_answer_shapes_fail_closed(shape, message):
    plan = _mutated_plan(lambda value: value.update(answerShape=shape))
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda plan: plan["entities"][0].update(resolution="indeterminate"), "unsupported value"),
        (lambda plan: plan["entities"][0].update(type="LegislativeProcess"), "unsupported value"),
        (lambda plan: plan["requirements"][0].update(subject={"type": "UnknownType"}), "unsupported value"),
        (lambda plan: plan.update(filters=[{"requirement": "member-name", "field": "name", "operator": "fuzzy", "value": "Micheál Martin"}]), "unsupported value"),
        (lambda plan: plan.update(temporalConstraints=[{"target": "member-name", "kind": "eventually"}]), "unsupported value"),
    ],
)
def test_unknown_required_enum_and_state_values_are_rejected(mutate, message):
    plan = _mutated_plan(mutate)
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "filters, message",
    [
        ([{"requirement": "missing", "field": "name", "operator": "equals", "value": "x"}], "unknown requirement"),
        ([{"requirement": "member-name", "field": "name", "operator": "equals"}], "value is required"),
        ([{"requirement": "member-name", "field": "name", "operator": "exists", "value": True}], "must not provide a value"),
        ([{"requirement": "member-name", "field": "name", "operator": "equals", "value": {"entity": "missing"}}], "unknown entity"),
    ],
)
def test_filter_shape_and_reference_invariants(filters, message):
    plan = _mutated_plan(lambda value: value.update(filters=filters))
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


@pytest.mark.parametrize(
    "operator, value",
    [
        ("equals", "Timmy Dooley"),
        ("not_equals", "Unknown"),
        ("greater_than", 1),
        ("greater_than_or_equal", 1),
        ("less_than", 10),
        ("less_than_or_equal", 10),
        ("exists", None),
        ("equals", {"entity": "member"}),
        ("equals", True),
    ],
)
def test_supported_filter_operators_and_value_shapes_validate(operator, value):
    filter_value = {"requirement": "member-name", "field": "name", "operator": operator}
    if operator != "exists":
        filter_value["value"] = value
    plan = _mutated_plan(lambda document: document.update(filters=[filter_value]))

    validate_query_plan(plan)
    _assert_schema_valid(plan)


def test_local_source_requirement_cannot_be_overridden_per_fact():
    plan = _mutated_plan(
        lambda value: value["requirements"][0].update(source="external"),
    )
    _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match="source is unsupported"):
        validate_query_plan(plan)


def test_loader_reports_missing_and_invalid_json_with_stable_errors(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(QueryPlanContractError, match="Could not read the query plan"):
        load_query_plan(missing)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    with pytest.raises(QueryPlanContractError, match="not valid JSON") as first:
        load_query_plan(malformed)
    with pytest.raises(QueryPlanContractError, match="not valid JSON") as second:
        load_query_plan(malformed)
    assert str(first.value) == str(second.value)
