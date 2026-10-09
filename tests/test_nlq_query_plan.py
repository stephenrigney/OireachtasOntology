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
    assert contract["contractVersion"] == "1.0.1"
    assert contract["contractSchema"] == "poc/specs/query-plan-contract.schema.json"
    assert contract["planSchema"] == "poc/specs/query-plan.schema.json"
    assert "conjunctively" in contract["planSemantics"]["conjunction"]
    assert "not executable identity bindings" in contract["planSemantics"]["resolutionReadiness"]
    answer_shape_guidance = {
        item["kind"]: item["description"]
        for item in contract["planSemantics"]["answerShapes"]
    }
    assert set(answer_shape_guidance) == {
        "boolean", "entity", "entities", "label", "fact", "list", "count",
        "grouped_result",
    }
    assert "Member's full name" in answer_shape_guidance["fact"]
    assert "Committee's code" in answer_shape_guidance["fact"]
    assert "which panel" in answer_shape_guidance["entities"]
    assert "label fact" in answer_shape_guidance["entities"]
    assert "label or name property" in answer_shape_guidance["label"]
    assert "entity resolution" in contract["planSemantics"]["entityMentionMeaning"]
    assert "time-dependent fact" in contract["planSemantics"]["temporalScoping"]
    vocabulary = contract["semanticVocabulary"]
    assert set(vocabulary["entityTypes"]) == set(plan_schema["$defs"]["entityType"]["enum"])
    assert {fact["id"] for fact in vocabulary["facts"]} == set(plan_schema["$defs"]["factId"]["enum"])
    assert {field["id"] for field in vocabulary["filterFields"]} == set(plan_schema["$defs"]["filterFieldId"]["enum"])
    filter_rules = {}
    for rule in plan_schema["$defs"]["filter"]["allOf"]:
        field_condition = rule.get("if", {}).get("properties", {}).get("field", {})
        if "const" in field_condition:
            filter_rules[field_condition["const"]] = rule["then"]["properties"]
    assert set(filter_rules) == {field["id"] for field in vocabulary["filterFields"]}
    for field in vocabulary["filterFields"]:
        rule = filter_rules[field["id"]]
        assert set(rule["operator"]["enum"]) == set(field["operators"])
        if field["valueKind"] == "entity":
            assert rule["value"] == {"$ref": "#/$defs/filterEntityReference"}
        else:
            assert rule["value"]["type"] == field["valueKind"]

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


def test_contract_documents_reviewed_entity_type_extensions_within_major_one():
    manifest = _read_json(CONTRACT_PATH)
    compatibility = manifest["compatibility"]
    assert "reviewed supported entity types" in compatibility["compatibleChanges"]
    assert "contract major version 1" in compatibility["compatibleChanges"]
    assert "and semantic vocabulary values" in compatibility["consumerSupport"]

    readme = (ROOT / "poc/nlq/README.md").read_text(encoding="utf-8")
    assert "reviewed, supported** entity" in readme
    assert "major version `1`" in readme


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
        (lambda manifest: manifest["planSemantics"]["answerShapes"].pop(), "must describe every supported answer shape"),
        (lambda manifest: manifest["planSemantics"]["answerShapes"][0].update(kind="unknown"), "unsupported value"),
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
                "fact": "member_collection_membership",
                "subject": {"type": "Member"},
                "object": {"type": "ParliamentaryMemberCollection"},
            }],
            filters=[{
                "requirement": "membership",
                "field": "parliamentary_collection",
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
            requirements=[{
                "id": "membership", "fact": "member_house_term_membership",
                "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
            }],
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
            requirements=[{
                "id": "membership", "fact": "member_house_term_membership",
                "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
            }],
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
        ), "requires an object participant"),
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
        (lambda plan: plan.update(filters=[{"requirement": "member-name", "field": "member_name", "operator": "fuzzy", "value": "Micheál Martin"}]), "unsupported value"),
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
        ([{"requirement": "missing", "field": "member_name", "operator": "equals", "value": "x"}], "unknown requirement"),
        ([{"requirement": "member-name", "field": "member_name", "operator": "equals"}], "value is required"),
        ([{"requirement": "member-name", "field": "member_name", "operator": "exists", "value": True}], "must not provide a value"),
    ],
)
def test_filter_shape_and_reference_invariants(filters, message):
    plan = _mutated_plan(lambda value: value.update(filters=filters))
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


def test_filter_entity_reference_must_resolve_to_a_supported_entity():
    plan = _mutated_plan(
        lambda value: value.update(
            requirements=[{
                "id": "membership",
                "fact": "member_collection_membership",
                "subject": {"type": "Member"},
                "object": {"type": "ParliamentaryMemberCollection"},
            }],
            filters=[{
                "requirement": "membership",
                "field": "parliamentary_collection",
                "operator": "equals",
                "value": {"entity": "missing"},
            }],
            answerShape={"kind": "boolean"},
        )
    )
    with pytest.raises(QueryPlanContractError, match="unknown entity"):
        validate_query_plan(plan)


def test_supported_facts_have_stable_identifiers_and_coherent_participant_types():
    manifest = load_query_plan_contract()
    for fact in manifest["semanticVocabulary"]["facts"]:
        plan = _example()
        requirement = {
            "id": "known-fact",
            "fact": fact["id"],
            "subject": {"type": fact["subjectTypes"][0]},
        }
        if fact["objectTypes"]:
            requirement["object"] = {"type": fact["objectTypes"][0]}
        plan.update(
            entities=[],
            requirements=[requirement],
            filters=[],
            temporalConstraints=[],
            aggregation=None,
            answerShape={"kind": "boolean"},
        )
        validate_query_plan(plan)
        _assert_schema_valid(plan)


def test_every_supported_filter_field_validates_with_its_declared_fact_and_value_kind():
    vocabulary = load_query_plan_contract()["semanticVocabulary"]
    facts = {fact["id"]: fact for fact in vocabulary["facts"]}
    for filter_field in vocabulary["filterFields"]:
        fact = facts[filter_field["facts"][0]]
        requirement = {
            "id": "supported-filter",
            "fact": fact["id"],
            "subject": {"type": fact["subjectTypes"][0]},
        }
        if fact["objectTypes"]:
            requirement["object"] = {"type": fact["objectTypes"][0]}
        plan = _example()
        plan["entities"] = []
        filter_value = {
            "requirement": requirement["id"],
            "field": filter_field["id"],
            "operator": "equals",
        }
        if filter_field["valueKind"] == "string":
            filter_value["value"] = "sample"
        elif filter_field["valueKind"] == "number":
            filter_value["value"] = 1
        else:
            entity_type = filter_field["entityTypes"][0]
            plan["entities"] = [{
                "id": "filter-entity",
                "type": entity_type,
                "label": "Filter target",
                "resolution": "unresolved",
            }]
            filter_value["value"] = {"entity": "filter-entity"}
        plan.update(
            requirements=[requirement],
            filters=[filter_value],
            temporalConstraints=[],
            aggregation=None,
            answerShape={"kind": "boolean"},
        )
        validate_query_plan(plan)
        _assert_schema_valid(plan)


@pytest.mark.parametrize("fact", ["Member full name", "unreviewed_future_fact"])
def test_arbitrary_or_unknown_fact_identifiers_fail_validation(fact):
    plan = _mutated_plan(lambda value: value["requirements"][0].update(fact=fact))
    _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match="unsupported value"):
        validate_query_plan(plan)


def test_filter_fields_are_controlled_and_coherent_with_the_requirement_fact():
    known = _example("multi-constraint-local.json")
    validate_query_plan(known)
    _assert_schema_valid(known)

    incompatible = _mutated_plan(
        lambda value: value.update(
            entities=[{
                "id": "collection",
                "type": "ParliamentaryMemberCollection",
                "label": "Fianna Fáil",
                "resolution": "unresolved",
            }],
            requirements=[{
                "id": "membership",
                "fact": "member_house_term_membership",
                "subject": {"type": "Member"},
                "object": {"type": "DailTerm"},
            }],
            filters=[{
                "requirement": "membership",
                "field": "parliamentary_collection",
                "operator": "equals",
                "value": {"entity": "collection"},
            }],
            answerShape={"kind": "boolean"},
        )
    )
    _assert_schema_valid(incompatible)
    with pytest.raises(QueryPlanContractError, match="not supported for fact"):
        validate_query_plan(incompatible)

    arbitrary = _mutated_plan(
        lambda value: value.update(filters=[{
            "requirement": "member-name",
            "field": "arbitrary English field",
            "operator": "equals",
            "value": "Micheál Martin",
        }])
    )
    _assert_schema_invalid(arbitrary)
    with pytest.raises(QueryPlanContractError, match="unsupported value"):
        validate_query_plan(arbitrary)


@pytest.mark.parametrize(
    "fact, subject_type, field, operator, value",
    [
        ("member_full_name", "Member", "member_name", "equals", "Timmy Dooley"),
        ("member_full_name", "Member", "member_name", "not_equals", "Unknown"),
        ("member_full_name", "Member", "member_name", "exists", None),
        ("parliamentary_term_number", "DailTerm", "parliamentary_term_number", "greater_than", 1),
        ("parliamentary_term_number", "DailTerm", "parliamentary_term_number", "greater_than_or_equal", 1),
        ("parliamentary_term_number", "DailTerm", "parliamentary_term_number", "less_than", 10),
        ("parliamentary_term_number", "DailTerm", "parliamentary_term_number", "less_than_or_equal", 10),
        ("parliamentary_term_number", "DailTerm", "parliamentary_term_number", "exists", None),
    ],
)
def test_supported_filter_identifiers_operators_and_typed_values_validate(
    fact, subject_type, field, operator, value,
):
    filter_value = {"requirement": "attribute", "field": field, "operator": operator}
    if operator != "exists":
        filter_value["value"] = value
    plan = _mutated_plan(
        lambda document: document.update(
            requirements=[{"id": "attribute", "fact": fact, "subject": {"type": subject_type}}],
            filters=[filter_value],
            answerShape={"kind": "boolean"},
        )
    )

    validate_query_plan(plan)
    _assert_schema_valid(plan)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("member_name", 42, "must be a string"),
        ("parliamentary_term_number", True, "must be a finite number"),
        ("parliamentary_term_number", float("inf"), "must be a finite number"),
        ("parliamentary_collection", "Fianna Fáil", "must be an entity reference"),
    ],
)
def test_filter_values_must_match_the_semantic_field_type(field, value, message):
    fact = "member_full_name" if field == "member_name" else (
        "parliamentary_term_number" if field == "parliamentary_term_number" else "member_collection_membership"
    )
    subject = {"type": "Member" if fact != "parliamentary_term_number" else "DailTerm"}
    requirement = {"id": "attribute", "fact": fact, "subject": subject}
    if fact == "member_collection_membership":
        requirement["object"] = {"type": "ParliamentaryMemberCollection"}
    plan = _mutated_plan(
        lambda document: document.update(
            requirements=[requirement],
            filters=[{"requirement": "attribute", "field": field, "operator": "equals", "value": value}],
            answerShape={"kind": "boolean"},
        )
    )
    if value != float("inf"):
        _assert_schema_invalid(plan)
    with pytest.raises(QueryPlanContractError, match=message):
        validate_query_plan(plan)


def test_current_supported_entity_types_validate_and_unknown_type_fails_closed():
    entity_types = load_query_plan_contract()["semanticVocabulary"]["entityTypes"]
    assert entity_types == [
        "Member", "House", "DailTerm", "SeanadTerm", "ParliamentaryMemberCollection",
        "DailConstituency", "SeanadPanel", "Committee",
    ]
    for entity_type in entity_types:
        plan = _mutated_plan(
            lambda value: value.update(
                entities=[{
                    "id": "surface-entity",
                    "type": entity_type,
                    "label": "Supported entity",
                    "resolution": "resolved",
                    "iri": "https://data.oireachtas.ie/resource/supported-entity",
                }],
                requirements=[{"id": "identity", "fact": "member_identity", "subject": {"type": "Member"}}],
                answerShape={"kind": "boolean"},
            )
        )
        validate_query_plan(plan)
        _assert_schema_valid(plan)

    unknown = _mutated_plan(lambda value: value["entities"][0].update(type="Bill"))
    _assert_schema_invalid(unknown)
    with pytest.raises(QueryPlanContractError, match="unsupported value"):
        validate_query_plan(unknown)


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
