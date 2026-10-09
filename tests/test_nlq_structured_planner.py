from __future__ import annotations

import copy
import json
import unicodedata
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator

from poc.nlq.errors import NLQError
from poc.nlq.member_resolution import (
    UnsupportedLocalEntityType,
    is_set_valued_member_reference,
    resolve_local_entity_label,
)
from poc.nlq.plan_contract import QueryPlanContractError, load_query_plan_contract, validate_query_plan
from poc.nlq.planner_benchmark import (
    _semantic_mismatches,
    load_planner_benchmark,
    run_planner_cases,
    summarize_planner_results,
)
from poc.nlq.benchmark import CoverageAssessment
from poc.nlq.results import QueryResult
from poc.nlq.structured_planner import (
    DRAFT_SCHEMA_PATH,
    DraftStructureError,
    ResponsesPlanGenerator,
    StructuredPlanner,
    _response_schema,
    build_planner_instructions,
    normalise_draft_output,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_CONTRACT = load_query_plan_contract()


def _output_draft(
    *,
    question: str = "What is the full name of Timmy Dooley?",
    entity_type: str = "Member",
    label: str = "Timmy Dooley",
    fact: str = "member_full_name",
) -> dict:
    return {
        "draftSchemaVersion": 1,
        "intent": "Return the requested semantic fact.",
        "entities": [{"id": "member", "type": entity_type, "label": label}],
        "requirements": [{
            "id": "requested-fact",
            "fact": fact,
            "subject": {"entity": "member", "type": None},
            "object": None,
        }],
        "filters": [],
        "temporalConstraints": [],
        "aggregation": None,
        "answerShape": {"kind": "fact", "target": "requested-fact", "entityType": None},
    }


class FakeGenerator:
    def __init__(self, output: str | dict):
        self.output = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        self.calls = 0

    def generate(self, _question: str) -> str:
        self.calls += 1
        return self.output

    def close(self):
        pass


class LocalResolverFuseki:
    def __init__(
        self,
        rows: tuple[tuple[str, str], ...] = (),
        *,
        contexts: dict[str, tuple[tuple[str, str], ...]] | None = None,
    ):
        self.rows = rows
        self.contexts = contexts or {}
        self.queries: list[str] = []
        self.fail = False

    def query(self, sparql: str) -> QueryResult:
        self.queries.append(sparql)
        if self.fail:
            raise NLQError("Fuseki query timed out.")
        if "VALUES ?member" in sparql:
            iri = next((candidate for candidate, _label in self.rows if f"<{candidate}>" in sparql), None)
            return QueryResult(
                kind="select", columns=("contextType", "contextLabel"),
                rows=self.contexts.get(iri, ()),
            )
        assert "SELECT DISTINCT ?entity ?label" in sparql
        return QueryResult(
            kind="select", columns=("entity", "label"), rows=self.rows,
        )


def _planner(output: str | dict, fuseki: LocalResolverFuseki):
    generator = FakeGenerator(output)
    planner = StructuredPlanner(generator, fuseki)
    return planner, generator


def _assert_strict_schema_objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            properties = set(schema.get("properties", {}))
            assert schema.get("additionalProperties") is False
            assert set(schema.get("required", [])) == properties
        for child in schema.values():
            _assert_strict_schema_objects(child)
    elif isinstance(schema, list):
        for child in schema:
            _assert_strict_schema_objects(child)


def test_draft_schema_is_valid_closed_and_vocabularies_match_phase_2a():
    schema = json.loads(DRAFT_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    response_schema = _response_schema()
    assert response_schema["additionalProperties"] is False
    assert set(response_schema["required"]) == set(response_schema["properties"])
    assert "anyOf" not in response_schema  # Responses strict output requires an object root.
    _assert_strict_schema_objects(response_schema)
    vocabulary = PLAN_CONTRACT["semanticVocabulary"]
    assert set(schema["$defs"]["entityType"]["enum"]) == set(vocabulary["entityTypes"])
    assert set(schema["$defs"]["factId"]["enum"]) == {
        fact["id"] for fact in vocabulary["facts"]
    }
    assert set(schema["$defs"]["filterFieldId"]["enum"]) == {
        field["id"] for field in vocabulary["filterFields"]
    }
    schema_filter_shapes = {}
    for name, definition in schema["$defs"].items():
        if not name.endswith("Filter"):
            continue
        properties = definition["properties"]
        field_id = properties["field"]["const"]
        operator_schema = properties["operator"]
        operators = {
            operator_schema["const"]
            if "const" in operator_schema else operator
            for operator in operator_schema.get("enum", [operator_schema.get("const")])
        }
        value_schema = properties["value"]
        value_kind = (
            "null" if value_schema.get("type") == "null"
            else "entity" if value_schema.get("$ref") == "#/$defs/filterEntityReference"
            else value_schema.get("type")
        )
        schema_filter_shapes.setdefault(field_id, []).append((operators, value_kind))
    for field in vocabulary["filterFields"]:
        branches = schema_filter_shapes[field["id"]]
        actual_operators = set().union(*(operators for operators, _kind in branches))
        assert actual_operators == set(field["operators"])
        assert all(
            kind == ("null" if operators == {"exists"} else field["valueKind"])
            for operators, kind in branches
        )
    assert set(schema_filter_shapes) == {
        field["id"] for field in vocabulary["filterFields"]
    }
    assert set(schema["$defs"]["temporalKind"]["enum"]) == {
        "on", "before", "after", "during", "interval", "current",
    }
    assert set(schema["$defs"]["answerKind"]["enum"]) == {
        "boolean", "entity", "entities", "label", "fact", "list", "count", "grouped_result",
    }

    draft = _output_draft()
    errors = list(Draft202012Validator(schema).iter_errors(draft))
    assert errors == []
    draft["entities"][0]["iri"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/guess"
    assert list(Draft202012Validator(schema).iter_errors(draft))

    validator = Draft202012Validator(schema)
    for case_id in (
        "plan.collection.timmy-dail-34",
        "plan.representation.timmy-seanad-26-panel",
        "plan.temporal.aengus-dail-33",
        "plan.aggregate.dail-term-count",
    ):
        assert list(validator.iter_errors(_expected_case_draft(case_id))) == [], case_id


def _assert_provider_draft_valid(draft):
    errors = list(Draft202012Validator(_response_schema()).iter_errors(draft))
    assert errors == []
    return normalise_draft_output(draft)


def _assert_provider_draft_invalid(draft):
    assert list(Draft202012Validator(_response_schema()).iter_errors(draft))
    with pytest.raises(DraftStructureError):
        normalise_draft_output(draft)


@pytest.mark.parametrize(
    "participant",
    [
        {"entity": "member", "type": None},
        {"entity": None, "type": "Member"},
    ],
)
def test_provider_and_local_participant_xor_accept_both_valid_forms(participant):
    draft = _output_draft()
    draft["requirements"][0]["subject"] = participant

    normalized = _assert_provider_draft_valid(draft)

    assert normalized["requirements"][0]["subject"] == {
        key: value for key, value in participant.items() if value is not None
    }


@pytest.mark.parametrize(
    "participant",
    [
        {"entity": "member", "type": "Member"},
        {"entity": None, "type": None},
    ],
)
def test_provider_and_local_participant_xor_reject_both_invalid_forms(participant):
    draft = _output_draft()
    draft["requirements"][0]["subject"] = participant

    _assert_provider_draft_invalid(draft)


def test_provider_and_local_require_at_least_one_requirement():
    draft = _output_draft()
    draft["requirements"] = []

    _assert_provider_draft_invalid(draft)


@pytest.mark.parametrize(
    ("shape", "aggregation"),
    [
        ({"kind": "boolean", "target": None, "entityType": None}, None),
        ({"kind": "entity", "target": None, "entityType": "Member"}, None),
        ({"kind": "entities", "target": None, "entityType": "Member"}, None),
        ({"kind": "label", "target": "requested-fact", "entityType": None}, None),
        ({"kind": "fact", "target": "requested-fact", "entityType": None}, None),
        ({"kind": "list", "target": "requested-fact", "entityType": None}, None),
        (
            {"kind": "count", "target": "aggregation", "entityType": None},
            {"operation": "count", "target": {"requirement": "requested-fact", "participant": "subject"}, "groupBy": []},
        ),
        (
            {"kind": "grouped_result", "target": "aggregation", "entityType": None},
            {"operation": "count", "target": {"requirement": "requested-fact", "participant": "subject"}, "groupBy": [{"requirement": "requested-fact", "participant": "subject"}]},
        ),
    ],
)
def test_provider_and_local_accept_each_answer_shape_with_matching_fields(shape, aggregation):
    draft = _output_draft()
    draft["answerShape"] = shape
    draft["aggregation"] = aggregation

    normalized = _assert_provider_draft_valid(draft)

    assert normalized["answerShape"] == {
        key: value for key, value in shape.items() if value is not None
    }
    assert normalized["aggregation"] == aggregation


@pytest.mark.parametrize(
    ("shape", "aggregation"),
    [
        ({"kind": "boolean", "target": "requested-fact", "entityType": None}, None),
        ({"kind": "entity", "target": None, "entityType": None}, None),
        ({"kind": "fact", "target": None, "entityType": None}, None),
        ({"kind": "count", "target": "requested-fact", "entityType": None}, None),
    ],
)
def test_provider_and_local_reject_answer_shape_field_and_aggregation_mismatches(shape, aggregation):
    draft = _output_draft()
    draft["answerShape"] = shape
    draft["aggregation"] = aggregation

    _assert_provider_draft_invalid(draft)


@pytest.mark.parametrize(
    ("shape", "aggregation"),
    [
        ({"kind": "count", "target": "aggregation", "entityType": None}, None),
        ({"kind": "grouped_result", "target": "aggregation", "entityType": None}, {
            "operation": "count", "target": {"requirement": "requested-fact", "participant": "subject"}, "groupBy": [],
        }),
        ({"kind": "count", "target": "aggregation", "entityType": None}, {
            "operation": "count", "target": {"requirement": "requested-fact", "participant": "subject"}, "groupBy": [{"requirement": "requested-fact", "participant": "subject"}],
        }),
    ],
)
def test_provider_schema_defers_cross_root_aggregation_consistency_to_local_validation(shape, aggregation):
    draft = _output_draft()
    draft["answerShape"] = shape
    draft["aggregation"] = aggregation

    assert list(Draft202012Validator(_response_schema()).iter_errors(draft)) == []
    with pytest.raises(DraftStructureError):
        normalise_draft_output(draft)


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("member_name", "exists", None),
        ("member_name", "equals", "Micheál Martin"),
        ("parliamentary_term_number", "greater_than", 34),
        ("parliamentary_term_number", "exists", None),
        ("parliamentary_collection", "equals", {"entity": "collection"}),
        ("parliamentary_collection", "exists", None),
        ("committee_code", "not_equals", "JTC"),
        ("committee_code", "exists", None),
    ],
)
def test_provider_and_local_accept_filter_operator_value_shapes(field, operator, value):
    draft = _output_draft()
    draft["filters"] = [{
        "requirement": "requested-fact", "field": field,
        "operator": operator, "value": value,
    }]

    normalized = _assert_provider_draft_valid(draft)

    if operator == "exists":
        assert "value" not in normalized["filters"][0]
    else:
        assert normalized["filters"][0]["value"] == value


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("member_name", "exists", "Timmy Dooley"),
        ("member_name", "equals", None),
        ("member_name", "greater_than", "Timmy Dooley"),
        ("parliamentary_term_number", "equals", True),
        ("parliamentary_term_number", "equals", None),
        ("parliamentary_collection", "equals", "collection"),
        ("parliamentary_collection", "exists", {"entity": "collection"}),
        ("committee_code", "equals", {"entity": "committee"}),
    ],
)
def test_provider_and_local_reject_filter_value_null_and_type_mismatches(field, operator, value):
    draft = _output_draft()
    draft["filters"] = [{
        "requirement": "requested-fact", "field": field,
        "operator": operator, "value": value,
    }]

    _assert_provider_draft_invalid(draft)


def _temporal_output_draft(kind, *, date=None, period=None, start=None, end=None):
    draft = _output_draft()
    draft["requirements"] = [{
        "id": "membership", "fact": "member_house_term_membership",
        "subject": {"entity": "member", "type": None},
        "object": {"entity": None, "type": "DailTerm"},
    }]
    draft["answerShape"] = {"kind": "boolean", "target": None, "entityType": None}
    draft["temporalConstraints"] = [{
        "target": "membership", "kind": kind, "date": date,
        "period": period, "start": start, "end": end,
    }]
    return draft


@pytest.mark.parametrize(
    "draft",
    [
        _temporal_output_draft("on", date="2020-01-01"),
        _temporal_output_draft("before", date="2020-01-01"),
        _temporal_output_draft("after", date="2020-01-01"),
        _temporal_output_draft("during", period={"entity": "term", "start": None, "end": None}),
        _temporal_output_draft("during", period={"entity": None, "start": "2020-01-01", "end": "2021-01-01"}),
        _temporal_output_draft("interval", start="2020-01-01", end="2021-01-01"),
        _temporal_output_draft("current"),
    ],
)
def test_provider_and_local_accept_each_temporal_structure(draft):
    _assert_provider_draft_valid(draft)


@pytest.mark.parametrize(
    "draft",
    [
        _temporal_output_draft("on"),
        _temporal_output_draft("on", date="2020-01-01", start="2020-01-02"),
        _temporal_output_draft("during"),
        _temporal_output_draft("during", period={"entity": "term", "start": "2020-01-01", "end": "2021-01-01"}),
        _temporal_output_draft("during", period={"entity": None, "start": "2020-01-01", "end": None}),
        _temporal_output_draft("interval", start="2020-01-01"),
        _temporal_output_draft("current", date="2020-01-01"),
    ],
)
def test_provider_and_local_reject_temporal_variant_mismatches(draft):
    _assert_provider_draft_invalid(draft)


@pytest.mark.parametrize(
    "aggregation",
    [
        {"operation": "sum", "target": {"requirement": "requested-fact", "participant": "subject"}, "groupBy": []},
        {"operation": "count", "target": {"requirement": "requested-fact", "participant": "other"}, "groupBy": []},
        {"operation": "count", "target": {"requirement": "requested-fact", "participant": "subject"}, "groupBy": "not-an-array"},
    ],
)
def test_provider_and_local_reject_invalid_aggregation_structures(aggregation):
    draft = _output_draft()
    draft["aggregation"] = aggregation
    draft["answerShape"] = {"kind": "count", "target": "aggregation", "entityType": None}

    _assert_provider_draft_invalid(draft)


@pytest.mark.parametrize(
    ("fact", "object_value"),
    [
        ("member_full_name", {"entity": None, "type": "DailTerm"}),
        ("member_house_term_membership", None),
    ],
)
def test_fact_specific_object_semantics_remain_authoritative_in_phase_2a(fact, object_value):
    draft = _output_draft()
    draft["requirements"][0]["fact"] = fact
    draft["requirements"][0]["object"] = object_value

    normalized = _assert_provider_draft_valid(draft)
    if object_value is None:
        assert "object" not in normalized["requirements"][0]
    else:
        assert normalized["requirements"][0]["object"] == {"type": "DailTerm"}

    fuseki = LocalResolverFuseki()
    planner, _ = _planner(draft, fuseki)
    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "invalid_draft_semantics"
    assert result.failure_stage == "draft_validation"
    assert fuseki.queries == []


def test_responses_plan_generator_uses_strict_schema_and_makes_one_call():
    output = json.dumps(_output_draft(), ensure_ascii=False)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["strict"] is True
        assert body["text"]["format"]["schema"]["additionalProperties"] is False
        assert "member_full_name" in body["instructions"]
        assert "graph/houses" not in body["instructions"]
        assert "foaf:name" not in body["instructions"]
        assert body["input"] == "What is the full name of Timmy Dooley?"
        return httpx.Response(200, json={"status": "completed", "output_text": output})

    generator = ResponsesPlanGenerator(
        "test-key", "https://llm.example/v1", "test-model",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert generator.generate("What is the full name of Timmy Dooley?") == output
        assert len(requests) == 1
    finally:
        generator.close()


def test_planner_prompt_is_limited_to_semantic_vocabulary_and_no_rdf_mapping_detail():
    prompt = build_planner_instructions()
    assert "member_collection_membership" in prompt
    assert "committee_code" in prompt
    assert "DailTerm" in prompt
    assert "SPARQL" in prompt  # explicit prohibition, not an implementation recipe
    assert "https://data.oireachtas.ie/graph/" not in prompt
    assert "foaf:name" not in prompt
    assert "members:hasMembersMembership" not in prompt


def test_planner_answer_shape_and_query_grounding_is_rendered_from_contract_metadata():
    default_prompt = build_planner_instructions()
    shape_descriptions = {
        shape["kind"]: shape["description"]
        for shape in PLAN_CONTRACT["planSemantics"]["answerShapes"]
    }
    assert all(description in default_prompt for description in shape_descriptions.values())
    assert "Member's full name" in shape_descriptions["fact"]
    assert "Committee's code" in shape_descriptions["fact"]
    assert "which panel or which parliamentary collection" in shape_descriptions["entities"]
    assert "resource occupying the requested semantic participant role" in shape_descriptions["entity"]
    assert "label/name property" in shape_descriptions["label"]
    assert "in the 34th Dáil" in default_prompt
    assert "during the 26th Seanad" in default_prompt
    assert "attach the temporal constraint to the requirement" in default_prompt
    assert "does not scope another fact" in default_prompt
    assert "do not restate the same name as a name/label filter" in default_prompt

    contract = copy.deepcopy(PLAN_CONTRACT)
    shapes = contract["planSemantics"]["answerShapes"]
    fact_shape = next(shape for shape in shapes if shape["kind"] == "fact")
    fact_shape["description"] = "CONTRACT-OWNED fact answer guidance."
    contract["planSemantics"]["entityMentionMeaning"] = "CONTRACT-OWNED entity mention guidance."
    contract["planSemantics"]["temporalScoping"] = "CONTRACT-OWNED temporal scoping guidance."

    prompt = build_planner_instructions(contract)

    assert "CONTRACT-OWNED fact answer guidance." in prompt
    assert "CONTRACT-OWNED entity mention guidance." in prompt
    assert "CONTRACT-OWNED temporal scoping guidance." in prompt


def test_valid_draft_resolves_locally_and_is_validated_as_a_final_phase_2a_plan():
    member_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
    fuseki = LocalResolverFuseki(((member_iri, "Timmy Dooley"),))
    planner, generator = _planner(_output_draft(), fuseki)

    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "validated_plan"
    assert result.accepted
    assert result.plan["entities"] == [{
        "id": "member", "type": "Member", "label": "Timmy Dooley",
        "resolution": "resolved", "iri": member_iri,
    }]
    assert validate_query_plan(result.plan) == result.plan
    assert len(fuseki.queries) == 1
    assert generator.calls == 1
    assert "sparql" not in result.as_dict()


def test_ambiguous_entity_becomes_valid_clarification_plan_with_distinct_actual_iris():
    records = tuple(
        (f"https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.{year}-01-21",
         "Michael Collins")
        for year in ("1919", "1997", "2016")
    )
    fuseki = LocalResolverFuseki(records)
    draft = _output_draft(label="Michael Collins")
    planner, _ = _planner(draft, fuseki)

    result = planner.plan("Who is Michael Collins?")

    assert result.status == "clarification_required"
    assert result.draft_plan["filters"] == []
    assert validate_query_plan(result.plan) == result.plan
    member = result.plan["entities"][0]
    assert member["resolution"] == "ambiguous"
    assert "iri" not in member
    assert len({candidate["iri"] for candidate in member["candidates"]}) == 3
    assert {candidate["label"] for candidate in member["candidates"]} == {"Michael Collins"}


def test_unresolved_entity_becomes_valid_unresolved_plan_without_iri_or_candidates():
    fuseki = LocalResolverFuseki()
    planner, _ = _planner(_output_draft(), fuseki)

    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "unresolved_entity"
    assert validate_query_plan(result.plan) == result.plan
    assert result.plan["entities"][0] == {
        "id": "member", "type": "Member", "label": "Timmy Dooley",
        "resolution": "unresolved",
    }


def test_model_supplied_iri_is_rejected_before_local_resolution():
    draft = _output_draft()
    draft["entities"][0]["iri"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/guess"
    fuseki = LocalResolverFuseki((("https://data.oireachtas.ie/ie/oireachtas/member/id/guess", "Timmy Dooley"),))
    planner, _ = _planner(draft, fuseki)

    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "invalid_draft_structure"
    assert result.failure_class == "invalid_draft_structure"
    assert "entity-resolution field 'iri'" in result.diagnostic
    assert fuseki.queries == []


def test_model_supplied_iri_or_url_text_is_rejected_even_when_shape_schema_allows_text():
    draft = _output_draft()
    draft["intent"] = "Use https://data.oireachtas.ie/ie/oireachtas/member/id/guess"
    assert list(Draft202012Validator(_response_schema()).iter_errors(draft)) == []
    with pytest.raises(DraftStructureError, match="IRI/URL text"):
        normalise_draft_output(draft)

    fuseki = LocalResolverFuseki()
    planner, _ = _planner(draft, fuseki)
    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "invalid_draft_structure"
    assert fuseki.queries == []


@pytest.mark.parametrize(
    "mutate, phrase",
    [
        (lambda draft: draft["requirements"][0].update(fact="member_favourite_colour"), "unsupported"),
        (lambda draft: draft["entities"][0].update(type="Bill"), "unsupported"),
        (lambda draft: draft["filters"].append({
            "requirement": "requested-fact", "field": "party_name", "operator": "equals",
            "value": "Fine Gael",
        }), "unsupported"),
    ],
)
def test_unsupported_semantic_vocabulary_fails_before_entity_lookup(mutate, phrase):
    draft = _output_draft()
    mutate(draft)
    assert list(Draft202012Validator(_response_schema()).iter_errors(draft))
    fuseki = LocalResolverFuseki()
    planner, _ = _planner(draft, fuseki)

    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "unsupported_vocabulary"
    assert result.failure_stage == "draft_validation"
    assert phrase in result.diagnostic.lower()
    assert fuseki.queries == []


def test_malformed_json_and_duplicate_keys_are_classified_without_retry():
    for output in ('{"draftSchemaVersion":1', '{"x":1,"x":2}'):
        fuseki = LocalResolverFuseki()
        planner, generator = _planner(output, fuseki)

        result = planner.plan("What is the full name of Timmy Dooley?")

        assert result.status == "invalid_model_output"
        assert result.failure_class == "invalid_model_json"
        assert generator.calls == 1
        assert fuseki.queries == []


@pytest.mark.parametrize("invalid_kind", ["temporal", "aggregation"])
def test_invalid_temporal_or_aggregation_semantics_fail_before_resolution(invalid_kind):
    question = "Was Timmy Dooley a Member during the 34th Dáil?"
    draft = _output_draft(question=question)
    draft["entities"].append({"id": "term", "type": "DailTerm", "label": "34th Dáil"})
    draft["requirements"] = [{
        "id": "membership", "fact": "member_house_term_membership",
        "subject": {"entity": "member", "type": None},
        "object": {"entity": None, "type": "DailTerm"},
    }]
    if invalid_kind == "temporal":
        draft["temporalConstraints"] = [{
            "target": "membership", "kind": "interval",
            "date": None, "period": None,
            "start": "2021-02-01", "end": "2020-01-01",
        }]
        draft["answerShape"] = {"kind": "boolean", "target": None, "entityType": None}
        assert list(Draft202012Validator(_response_schema()).iter_errors(draft)) == []
    else:
        draft["aggregation"] = {
            "operation": "count",
            "target": {"requirement": "membership", "participant": "subject"},
            "groupBy": [{"requirement": "membership", "participant": "object"}],
        }
        draft["answerShape"] = {"kind": "count", "target": "aggregation", "entityType": None}
    fuseki = LocalResolverFuseki()
    planner, _ = _planner(draft, fuseki)

    result = planner.plan(question)

    expected_status = (
        "invalid_draft_semantics" if invalid_kind == "temporal"
        else "invalid_draft_structure"
    )
    assert result.status == expected_status
    assert result.failure_stage == "draft_validation"
    assert fuseki.queries == []


def test_resolver_reuses_nfc_casefold_matching_without_accent_folding_or_fuzzy_match():
    decomposed = unicodedata.normalize("NFD", "Micheál Martin")
    iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Micheal-Martin.D.1989-06-29"
    fuseki = LocalResolverFuseki(((iri, "Micheál Martin@en"),))

    exact = resolve_local_entity_label("Member", decomposed, fuseki)
    no_accent = resolve_local_entity_label(
        "Member", "Micheal Martin", LocalResolverFuseki(((iri, "Micheál Martin"),)),
    )
    partial = resolve_local_entity_label(
        "Member", "Micheál", LocalResolverFuseki(((iri, "Micheál Martin"),)),
    )

    assert exact.state == "resolved"
    assert exact.candidates[0].label == "Micheál Martin"
    assert no_accent.state == "unresolved"
    assert partial.state == "unresolved"


@pytest.mark.parametrize(
    "entity_type, class_name, graph",
    [
        ("House", "agents:House", "https://data.oireachtas.ie/graph/houses"),
        ("DailTerm", "agents:DailTerm", "https://data.oireachtas.ie/graph/houses"),
        ("SeanadTerm", "agents:SeanadTerm", "https://data.oireachtas.ie/graph/houses"),
        ("ParliamentaryMemberCollection", "members:ParliamentaryMemberCollection", "https://data.oireachtas.ie/graph/parties"),
        ("DailConstituency", "members:DailConstituency", "https://data.oireachtas.ie/graph/constituencies"),
        ("SeanadPanel", "members:SeanadPanel", "https://data.oireachtas.ie/graph/constituencies"),
        ("Committee", "members:Committee", "https://data.oireachtas.ie/graph/committees"),
    ],
)
def test_generalised_resolver_uses_supported_type_and_owner_graph(entity_type, class_name, graph):
    iri = "https://data.oireachtas.ie/ie/oireachtas/reference/one"
    fuseki = LocalResolverFuseki(((iri, "Sample Local Label@en"),))

    result = resolve_local_entity_label(entity_type, "sample local label", fuseki)

    assert result.state == "resolved"
    assert result.candidates == (type(result.candidates[0])(iri, "Sample Local Label"),)
    assert class_name in fuseki.queries[0]
    assert graph in fuseki.queries[0]


def test_unimplemented_local_resolver_type_is_reported_explicitly():
    with pytest.raises(UnsupportedLocalEntityType, match="No deterministic local resolver"):
        resolve_local_entity_label("Bill", "Finance Bill", LocalResolverFuseki())


def test_local_resolver_deduplicates_same_iri_but_preserves_distinct_resources():
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2020-02-01"
    result = resolve_local_entity_label(
        "Member", "Timmy Dooley", LocalResolverFuseki((
            (first, "Timmy Dooley@en"), (first, "Timmy Dooley"), (second, "Timmy Dooley"),
        )),
    )
    assert result.state == "ambiguous"
    assert {candidate.iri for candidate in result.candidates} == {first, second}


def test_member_resolver_uses_exact_local_house_term_context_to_narrow_duplicates():
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1919-01-21"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26"
    third = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03"
    fuseki = LocalResolverFuseki(
        ((first, "Michael Collins"), (second, "Michael Collins"), (third, "Michael Collins")),
        contexts={
            first: (("house_term", "1st Dáil@en"),),
            second: (("house_term", "28th Dáil@en"),),
            third: (("house_term", "34th Dáil@en"),),
        },
    )

    result = resolve_local_entity_label(
        "Member", "Michael Collins", fuseki,
        question_context="What did Michael Collins do in the 28th Dáil?",
    )

    assert result.state == "resolved"
    assert result.candidates == (type(result.candidates[0])(second, "Michael Collins"),)
    assert len(fuseki.queries) == 4  # name lookup followed by all local context checks
    evidence = result.contextual_evidence.as_dict(entity_id="member")
    assert evidence["decision"] == "resolved_by_unique_context_match"
    assert evidence["rule"] == "select_only_if_exact_context_matches_one_candidate"
    assert evidence["selectedIri"] == second
    assert [candidate["iri"] for candidate in evidence["initialCandidates"]] == [
        first, second, third,
    ]
    assert evidence["contextMatches"] == [
        {"iri": first, "matchedLabels": []},
        {"iri": second, "matchedLabels": ["28th Dáil"]},
        {"iri": third, "matchedLabels": []},
    ]


def test_member_resolver_keeps_all_context_matches_ambiguous():
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03"
    fuseki = LocalResolverFuseki(
        ((first, "Michael Collins"), (second, "Michael Collins")),
        contexts={
            first: (("house_term", "28th Dáil@en"),),
            second: (("house_term", "28th Dáil@en"),),
        },
    )

    result = resolve_local_entity_label(
        "Member", "Michael Collins", fuseki,
        question_context="What did Michael Collins do in the 28th Dáil?",
    )

    assert result.state == "ambiguous"
    assert {candidate.iri for candidate in result.candidates} == {first, second}
    assert result.contextual_evidence.decision == "ambiguous_multiple_context_matches"
    assert result.contextual_evidence.selected_iri is None


@pytest.mark.parametrize(
    ("question", "set_valued"),
    [
        ("Who is Michael Collins?", False),
        ("Which Members are named Michael Collins?", True),
        ("How many Members named Michael Collins are there?", True),
        ("What terms did Michael Collins serve in?", False),
    ],
)
def test_phase1_member_set_valued_intent_is_shared_with_structured_planner(question, set_valued):
    assert is_set_valued_member_reference(question, "Michael Collins") is set_valued


def test_singular_member_questions_remain_ordinary_duplicate_name_ambiguity():
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03"
    cases = [
        ("Who is Michael Collins?", _output_draft(label="Michael Collins")),
        ("Which terms did Michael Collins serve in?", {
            **_output_draft(
                question="Which terms did Michael Collins serve in?",
                label="Michael Collins",
            ),
            "requirements": [{
                "id": "membership", "fact": "member_house_term_membership",
                "subject": {"entity": "member", "type": None},
                "object": {"entity": None, "type": "DailTerm"},
            }],
            "answerShape": {
                "kind": "entities", "target": None, "entityType": "DailTerm",
            },
        }),
    ]
    for question, draft in cases:
        fuseki = LocalResolverFuseki(
            ((first, "Michael Collins"), (second, "Michael Collins")),
        )
        planner, _ = _planner(draft, fuseki)

        result = planner.plan(question)

        assert result.status == "clarification_required"
        assert result.plan["entities"][0]["resolution"] == "ambiguous"
        assert len(result.plan["entities"][0]["candidates"]) == 2


def test_set_valued_member_context_does_not_narrow_even_inside_local_resolver():
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03"
    fuseki = LocalResolverFuseki(
        ((first, "Michael Collins"), (second, "Michael Collins")),
        contexts={
            first: (("house_term", "28th Dáil@en"),),
            second: (("house_term", "34th Dáil@en"),),
        },
    )

    result = resolve_local_entity_label(
        "Member", "Michael Collins", fuseki,
        question_context="Which Members named Michael Collins served in the 28th Dáil?",
    )

    assert result.state == "ambiguous"
    assert {candidate.iri for candidate in result.candidates} == {first, second}
    assert len(fuseki.queries) == 1  # explicit set intent skips contextual narrowing
    assert result.contextual_evidence is None


@pytest.mark.parametrize(
    ("contextual_rows", "expected_decision", "expected_context_matches"),
    [
        (
            {"first": (("house_term", "1st Dáil@en"),),
             "second": (("representation", "Limerick West@en"),)},
            "ambiguous_no_context_match",
            {"first": [], "second": []},
        ),
        (
            {"first": (("house_term", "28th Dáil@en"),),
             "second": (("house_term", "28th Dáil@en"),)},
            "ambiguous_multiple_context_matches",
            {"first": ["28th Dáil"], "second": ["28th Dáil"]},
        ),
    ],
)
def test_planner_retains_context_evidence_when_duplicates_remain_ambiguous(
    contextual_rows, expected_decision, expected_context_matches,
):
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03"
    question = "What did Michael Collins do in the 28th Dáil?"
    fuseki = LocalResolverFuseki(
        ((first, "Michael Collins"), (second, "Michael Collins")),
        contexts={
            first: contextual_rows["first"],
            second: contextual_rows["second"],
        },
    )
    planner, _ = _planner(_output_draft(question=question, label="Michael Collins"), fuseki)

    result = planner.plan(question)

    assert result.status == "clarification_required"
    assert result.plan["entities"][0]["resolution"] == "ambiguous"
    assert [candidate["iri"] for candidate in result.plan["entities"][0]["candidates"]] == [
        first, second,
    ]
    [evidence] = result.as_dict()["binding_evidence"]
    assert evidence["entityId"] == "member"
    assert evidence["inputLabel"] == "Michael Collins"
    assert evidence["decision"] == expected_decision
    assert "selectedIri" not in evidence
    assert [candidate["iri"] for candidate in evidence["initialCandidates"]] == [
        first, second,
    ]
    assert {
        item["iri"]: item["matchedLabels"] for item in evidence["contextMatches"]
    } == {
        first: expected_context_matches["first"],
        second: expected_context_matches["second"],
    }


def test_planner_exposes_deterministic_evidence_for_unique_context_binding():
    first = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1919-01-21"
    second = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26"
    third = "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03"
    question = "What did Michael Collins do in the 28th Dáil from Limerick West?"
    rows = ((first, "Michael Collins"), (second, "Michael Collins"), (third, "Michael Collins"))
    contexts = {
        first: (("house_term", "1st Dáil@en"),),
        second: (
            ("house_term", "28th Dáil@en"),
            ("representation", "Limerick West@en"),
        ),
        third: (("house_term", "34th Dáil@en"),),
    }

    def run(candidate_rows, candidate_contexts):
        fuseki = LocalResolverFuseki(candidate_rows, contexts=candidate_contexts)
        planner, _ = _planner(
            _output_draft(question=question, label="Michael Collins"), fuseki,
        )
        return planner.plan(question)

    result = run(rows, contexts)
    reordered = run(tuple(reversed(rows)), dict(reversed(tuple(contexts.items()))))

    assert result.status == "validated_plan"
    member = result.plan["entities"][0]
    assert member["resolution"] == "resolved"
    assert member["iri"] == second
    assert "binding_evidence" not in result.plan
    [evidence] = result.as_dict()["binding_evidence"]
    assert set(evidence) == {
        "entityId", "entityType", "inputLabel", "initialCandidates",
        "contextMatches", "decision", "rule", "selectedIri",
    }
    assert evidence["entityType"] == "Member"
    assert evidence["decision"] == "resolved_by_unique_context_match"
    assert evidence["rule"] == "select_only_if_exact_context_matches_one_candidate"
    assert evidence["selectedIri"] == member["iri"]
    assert [candidate["iri"] for candidate in evidence["initialCandidates"]] == [
        first, second, third,
    ]
    assert [match["matchedLabels"] for match in evidence["contextMatches"]] == [
        [], ["28th Dáil", "Limerick West"], [],
    ]
    assert result.as_dict()["binding_evidence"] == reordered.as_dict()["binding_evidence"]


@pytest.mark.parametrize(
    ("question", "answer_kind"),
    [
        ("Which Members are named Michael Collins?", "entities"),
        ("How many Members named Michael Collins are there?", "count"),
        (
            "Which Members named Michael Collins served in the 28th Dáil?",
            "entities",
        ),
    ],
)
def test_set_valued_named_member_request_is_non_executable(question, answer_kind):
    draft = _output_draft(question=question, label="Michael Collins")
    if answer_kind == "count":
        draft["requirements"][0]["fact"] = "member_identity"
        draft["aggregation"] = {
            "operation": "count",
            "target": {"requirement": "requested-fact", "participant": "subject"},
            "groupBy": [],
        }
        draft["answerShape"] = {
            "kind": "count", "target": "aggregation", "entityType": None,
        }
    fuseki = LocalResolverFuseki(
        (
            ("https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26", "Michael Collins"),
            ("https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03", "Michael Collins"),
        ),
        contexts={
            "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26": (
                ("house_term", "28th Dáil@en"),
            ),
            "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03": (
                ("house_term", "34th Dáil@en"),
            ),
        },
    )
    planner, _ = _planner(draft, fuseki)

    result = planner.plan(question)

    assert result.status == "set_valued_member_identity"
    assert result.failure_stage == "entity_resolution"
    assert result.failure_class == "set_valued_member_identity"
    assert not result.accepted
    assert result.plan is None
    assert result.draft_plan["entities"] == [
        {"id": "member", "type": "Member", "label": "Michael Collins"},
    ]
    assert "no singular local Member IRI was selected" in result.diagnostic
    assert result.as_dict()["binding_evidence"] == []
    assert fuseki.queries == []


def test_final_phase_2a_validation_runs_for_accepted_plans_and_failure_is_visible(monkeypatch):
    import poc.nlq.structured_planner as planner_module

    original = planner_module.validate_query_plan
    calls = []

    def counted(plan, *, contract=None):
        calls.append(plan)
        return original(plan, contract=contract)

    monkeypatch.setattr(planner_module, "validate_query_plan", counted)
    fuseki = LocalResolverFuseki((
        ("https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12", "Timmy Dooley"),
    ))
    planner, _ = _planner(_output_draft(), fuseki)
    result = planner.plan("What is the full name of Timmy Dooley?")
    assert result.accepted
    assert len(calls) == 2  # provisional semantic check, then final accepted plan

    def reject_final(plan, *, contract=None):
        if plan["entities"] and plan["entities"][0].get("resolution") == "resolved":
            raise QueryPlanContractError("injected final-contract failure")
        return original(plan, contract=contract)

    monkeypatch.setattr(planner_module, "validate_query_plan", reject_final)
    planner, _ = _planner(_output_draft(), fuseki)
    rejected = planner.plan("What is the full name of Timmy Dooley?")
    assert rejected.status == "final_plan_validation_failure"
    assert rejected.failure_class == "final_plan_validation_failure"
    assert not rejected.accepted


def test_fuseki_prerequisite_failure_is_not_collapsed_into_unresolved_entity():
    fuseki = LocalResolverFuseki()
    fuseki.fail = True
    planner, _ = _planner(_output_draft(), fuseki)

    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "source_data_prerequisite_unavailable"
    assert result.failure_class == "source_data_prerequisite_unavailable"


def test_unmentioned_model_entity_label_is_invalid_draft_semantics():
    fuseki = LocalResolverFuseki()
    planner, _ = _planner(_output_draft(label="Aengus Ó Snodaigh"), fuseki)

    result = planner.plan("What is the full name of Timmy Dooley?")

    assert result.status == "invalid_draft_semantics"
    assert "not an exact user-supplied label mention" in result.diagnostic
    assert fuseki.queries == []


def test_planner_benchmark_separates_coverage_and_never_executes_a_plan_query():
    benchmark = load_planner_benchmark()
    source_path = ROOT / "poc/nlq/benchmarks/benchmark-v3.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    selected = copy.deepcopy(next(
        case for case in benchmark["cases"] if case["id"] == "plan.lookup.aengus-name"
    ))
    one_case = {**benchmark, "cases": [selected]}

    class EvaluationFuseki(LocalResolverFuseki):
        def query(self, sparql):
            if "ASK {" in sparql:
                self.queries.append(sparql)
                return QueryResult(kind="ask", boolean=True)
            return super().query(sparql)

    iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aengus-Ó-Snodaigh.D.2002-06-06"
    fuseki = EvaluationFuseki(((iri, "Aengus Ó Snodaigh"),))
    baseline = {
        "schema_version": 1,
        "dataset": {"id": "sha256:" + "a" * 64},
        "rdf_resource_counts": {"members": 1},
        "graph_families_loaded": [{"name": "members"}],
        "quarantined_conflicted_identities": [],
        "unresolved_references": [],
    }

    class PlannerFactory:
        def __call__(self, _case, local_fuseki):
            draft = _output_draft(label="Aengus Ó Snodaigh")
            draft["requirements"][0]["fact"] = "member_full_name"
            return StructuredPlanner(FakeGenerator(draft), local_fuseki)

    outcomes = run_planner_cases(
        one_case, source, baseline, fuseki=fuseki, supported_predicates=None,
        planner_factory=PlannerFactory(),
    )

    assert outcomes[0]["evaluation"] == "passed"
    assert outcomes[0]["planner_result"]["status"] == "validated_plan"
    assert "execution_result" not in outcomes[0]
    assert all("sparql" not in outcome["planner_result"] for outcome in outcomes)
    assert any("ASK {" in query for query in fuseki.queries)  # coverage only
    assert all("SELECT DISTINCT ?entity ?label" in query or "ASK {" in query
               for query in fuseki.queries)
    assert summarize_planner_results(outcomes) == {
        "total_cases": 1, "passed": 1, "failed": 0, "not_scored": 0,
        "by_failure_class": {},
    }


def test_planner_benchmark_has_required_supported_and_boundary_cases():
    benchmark = load_planner_benchmark()
    assert benchmark["benchmark_version"] == "0.2.1"
    case_ids = {case["id"] for case in benchmark["cases"]}
    assert {
        "plan.lookup.aengus-name",
        "plan.term.aengus-dail-33",
        "plan.collection.timmy-dail-34",
        "plan.representation.timmy-seanad-26-panel",
        "plan.committee.transport-code",
        "plan.temporal.aengus-dail-33",
        "plan.aggregate.dail-term-count",
        "plan.ambiguous.duplicate-michael-collins",
        "plan.unresolved.local-member-label",
        "plan.unsupported.member-favourite-colour",
        "plan.coverage.unavailable-bill",
    } <= case_ids


def _expected_case_draft(case_id: str) -> dict:
    def entity(entity_id, entity_type, label):
        return {"id": entity_id, "type": entity_type, "label": label}

    def ref(entity_id):
        return {"entity": entity_id, "type": None}

    def role(entity_type):
        return {"entity": None, "type": entity_type}

    def requirement(requirement_id, fact, subject, object_value=None):
        return {
            "id": requirement_id, "fact": fact, "subject": subject,
            "object": object_value,
        }

    result = _output_draft()
    if case_id == "plan.lookup.aengus-name":
        result["entities"] = [entity("member", "Member", "Aengus Ó Snodaigh")]
    elif case_id == "plan.term.aengus-dail-33":
        result["entities"] = [entity("member", "Member", "Aengus Ó Snodaigh")]
        result["requirements"] = [requirement(
            "membership", "member_house_term_membership", ref("member"), role("DailTerm"),
        )]
        result["answerShape"] = {"kind": "entities", "target": None, "entityType": "DailTerm"}
    elif case_id == "plan.collection.timmy-dail-34":
        result["entities"] = [
            entity("member", "Member", "Timmy Dooley"),
            entity("term", "DailTerm", "34th Dáil"),
        ]
        result["requirements"] = [requirement(
            "collection-membership", "member_collection_membership", ref("member"), role("ParliamentaryMemberCollection"),
        )]
        result["temporalConstraints"] = [{
            "target": "collection-membership", "kind": "during", "date": None,
            "period": {"entity": "term", "start": None, "end": None},
            "start": None, "end": None,
        }]
        result["answerShape"] = {
            "kind": "entities", "target": None, "entityType": "ParliamentaryMemberCollection",
        }
    elif case_id == "plan.representation.timmy-seanad-26-panel":
        result["entities"] = [
            entity("member", "Member", "Timmy Dooley"),
            entity("term", "SeanadTerm", "26th Seanad"),
        ]
        result["requirements"] = [requirement(
            "representation", "member_constituency_representation", ref("member"), role("SeanadPanel"),
        )]
        result["temporalConstraints"] = [{
            "target": "representation", "kind": "during", "date": None,
            "period": {"entity": "term", "start": None, "end": None},
            "start": None, "end": None,
        }]
        result["answerShape"] = {"kind": "entities", "target": None, "entityType": "SeanadPanel"}
    elif case_id == "plan.committee.transport-code":
        result["entities"] = [entity(
            "committee", "Committee", "Joint Committee on Transport and Communications",
        )]
        result["requirements"] = [requirement(
            "committee-code", "committee_code", ref("committee"), None,
        )]
        result["answerShape"] = {"kind": "fact", "target": "committee-code", "entityType": None}
    elif case_id == "plan.temporal.aengus-dail-33":
        result["entities"] = [
            entity("member", "Member", "Aengus Ó Snodaigh"),
            entity("term", "DailTerm", "33rd Dáil"),
        ]
        result["requirements"] = [requirement(
            "membership", "member_house_term_membership", ref("member"), ref("term"),
        )]
        result["answerShape"] = {"kind": "boolean", "target": None, "entityType": None}
    elif case_id == "plan.aggregate.dail-term-count":
        result["entities"] = []
        result["requirements"] = [requirement(
            "term-label", "parliamentary_term_label", role("DailTerm"), None,
        )]
        result["aggregation"] = {
            "operation": "count",
            "target": {"requirement": "term-label", "participant": "subject"},
            "groupBy": [],
        }
        result["answerShape"] = {"kind": "count", "target": "aggregation", "entityType": None}
    elif case_id == "plan.ambiguous.duplicate-michael-collins":
        result["entities"] = [entity("member", "Member", "Michael Collins")]
    elif case_id == "plan.unresolved.local-member-label":
        result["entities"] = [entity("member", "Member", "Ada Never-Matched Example")]
    elif case_id == "plan.unsupported.member-favourite-colour":
        result["entities"] = [entity("member", "Member", "Aengus Ó Snodaigh")]
    else:
        raise AssertionError(f"no deterministic plan fixture for {case_id}")
    return result


def test_corrected_aengus_term_membership_benchmark_requires_direct_entity_link_not_temporal_scope():
    benchmark = load_planner_benchmark()
    case = next(
        case for case in benchmark["cases"]
        if case["id"] == "plan.temporal.aengus-dail-33"
    )
    assert "Was Aengus Ó Snodaigh a Member" in case["question"]
    assert case.get("required_temporal_constraints", []) == []
    expectation = case["required_requirements"][0]
    assert expectation["fact"] == "member_house_term_membership"
    assert expectation["subject_entity_label"] == "Aengus Ó Snodaigh"
    assert expectation["object_entity_label"] == "33rd Dáil"
    draft = _expected_case_draft("plan.temporal.aengus-dail-33")
    assert draft["temporalConstraints"] == []
    assert draft["filters"] == []
    assert draft["requirements"][0]["subject"] == {"entity": "member", "type": None}
    assert draft["requirements"][0]["object"] == {"entity": "term", "type": None}

    plan = {
        "entities": [
            {"id": "member", "type": "Member", "label": "Aengus Ó Snodaigh", "resolution": "resolved"},
            {"id": "term", "type": "DailTerm", "label": "33rd Dáil", "resolution": "resolved"},
        ],
        "requirements": [{
            "id": "membership",
            "fact": "member_house_term_membership",
            "subject": {"entity": "member"},
            "object": {"entity": "term"},
        }],
        "temporalConstraints": [],
        "answerShape": {"kind": "boolean"},
    }
    assert _semantic_mismatches(plan, case) == []

    # A type-only term role does not prove membership in the referenced 33rd Dáil.
    plan["requirements"][0]["object"] = {"type": "DailTerm"}
    assert any(
        "entity-linked participant labels" in mismatch
        for mismatch in _semantic_mismatches(plan, case)
    )


def _minimal_term_scoped_plan(case: dict) -> dict:
    entities = []
    participant_by_type = {}
    for expected in case["required_entities"]:
        entity_id = "member" if expected["type"] == "Member" else "term"
        participant_by_type[expected["type"]] = entity_id
        entities.append({
            "id": entity_id,
            "type": expected["type"],
            "label": expected["label"],
            "resolution": expected["resolution"],
        })
    requirement_expectation = case["required_requirements"][0]
    requirement_id = "requested-fact"
    temporal_expectation = case["required_temporal_constraints"][0]
    return {
        "entities": entities,
        "requirements": [{
            "id": requirement_id,
            "fact": requirement_expectation["fact"],
            "subject": {"entity": participant_by_type[requirement_expectation["subject_type"]]},
            "object": {"type": requirement_expectation["object_type"]},
        }],
        "temporalConstraints": [{
            "target": requirement_id,
            "kind": temporal_expectation["kind"],
            "period": {"entity": participant_by_type[temporal_expectation["period_entity_type"]]},
        }],
        "answerShape": copy.deepcopy(case["answer_shape"]),
    }


def test_collection_and_representation_need_only_requested_fact_scoped_to_the_term():
    benchmark = load_planner_benchmark()
    expected = {
        "plan.collection.timmy-dail-34": (
            "member_collection_membership", "DailTerm", "34th Dáil",
            "ParliamentaryMemberCollection",
        ),
        "plan.representation.timmy-seanad-26-panel": (
            "member_constituency_representation", "SeanadTerm", "26th Seanad", "SeanadPanel",
        ),
    }
    cases = {case["id"]: case for case in benchmark["cases"]}
    for case_id, (requested_fact, period_type, period_label, answer_type) in expected.items():
        case = cases[case_id]
        assert [item["fact"] for item in case["required_requirements"]] == [requested_fact]
        assert not any(
            item["fact"] == "member_house_term_membership"
            for item in case["required_requirements"]
        )
        assert case["answer_shape"] == {"kind": "entities", "entityType": answer_type}
        temporal = case["required_temporal_constraints"]
        assert temporal == [{
            "kind": "during", "target_fact": requested_fact,
            "period_entity_type": period_type, "period_entity_label": period_label,
        }]

        draft = _expected_case_draft(case_id)
        assert [item["fact"] for item in draft["requirements"]] == [requested_fact]
        constraint = draft["temporalConstraints"][0]
        target = next(
            requirement for requirement in draft["requirements"]
            if requirement["id"] == constraint["target"]
        )
        assert target["fact"] == requested_fact
        assert constraint["period"]["entity"] == "term"

        plan = _minimal_term_scoped_plan(case)
        assert _semantic_mismatches(plan, case) == []

        missing_fact = copy.deepcopy(plan)
        missing_fact["requirements"] = []
        mismatches = _semantic_mismatches(missing_fact, case)
        assert any(f"missing requirement {requested_fact}" in mismatch for mismatch in mismatches)

        missing_temporal = copy.deepcopy(plan)
        missing_temporal["temporalConstraints"] = []
        assert any(
            f"missing during temporal constraint on {requested_fact}" in mismatch
            for mismatch in _semantic_mismatches(missing_temporal, case)
        )

        wrong_answer_shape = copy.deepcopy(plan)
        wrong_answer_shape["answerShape"] = {"kind": "fact", "target": "requested-fact"}
        assert any("answer shape did not match" in mismatch
                   for mismatch in _semantic_mismatches(wrong_answer_shape, case))


def test_deterministic_planner_benchmark_cases_are_scored_without_sparql_generation(monkeypatch):
    import poc.nlq.planner_benchmark as planner_benchmark_module

    benchmark = load_planner_benchmark()
    source = json.loads((ROOT / "poc/nlq/benchmarks/benchmark-v3.json").read_text())

    class FixtureFuseki:
        def __init__(self):
            self.queries = []
            self.labels = {
                "Aengus Ó Snodaigh": (
                    ("https://data.oireachtas.ie/ie/oireachtas/member/id/Aengus-Ó-Snodaigh.D.2002-06-06", "Aengus Ó Snodaigh"),
                ),
                "Timmy Dooley": (
                    ("https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12", "Timmy Dooley"),
                ),
                "34th Dáil": (
                    ("https://data.oireachtas.ie/ie/oireachtas/house/dail/34", "34th Dáil@en"),
                ),
                "33rd Dáil": (
                    ("https://data.oireachtas.ie/ie/oireachtas/house/dail/33", "33rd Dáil@en"),
                ),
                "26th Seanad": (
                    ("https://data.oireachtas.ie/ie/oireachtas/house/seanad/26", "26th Seanad@en"),
                ),
                "Joint Committee on Transport and Communications": (
                    ("https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/joint_committee_on_transport_and_communications", "Joint Committee on Transport and Communications@en"),
                ),
                "Michael Collins": tuple(
                    (f"https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.{year}-01-21", "Michael Collins")
                    for year in ("1919", "1997", "2016")
                ),
            }

        def query(self, sparql):
            self.queries.append(sparql)
            if "VALUES ?member" in sparql:
                return QueryResult(kind="select", columns=("contextType", "contextLabel"), rows=())
            for label, rows in self.labels.items():
                if f'STR("{label}")' in sparql:
                    return QueryResult(
                        kind="select", columns=("entity", "label"), rows=rows,
                    )
            return QueryResult(kind="select", columns=("entity", "label"), rows=())

    def coverage(case, _baseline, **_kwargs):
        if case["id"] == "unavailable.bill-status":
            return CoverageAssessment("unavailable", "Bill graph unavailable", "source_data_coverage")
        return CoverageAssessment("available")

    monkeypatch.setattr(planner_benchmark_module, "assess_dataset_prerequisites", coverage)
    fuseki = FixtureFuseki()

    def planner_factory(case, local_fuseki):
        return StructuredPlanner(
            FakeGenerator(_expected_case_draft(case["id"])), local_fuseki,
        )

    results = run_planner_cases(
        benchmark, source,
        {"schema_version": 1, "dataset": {"id": "sha256:" + "b" * 64}},
        fuseki=fuseki, supported_predicates=None, planner_factory=planner_factory,
    )

    unexpected_failures = [item for item in results if item["passed"] is False]
    assert not unexpected_failures, [
        (item["case_id"], item["failure_reason"], item["planner_result"])
        for item in unexpected_failures
    ]
    summary = summarize_planner_results(results)
    assert summary == {
        "total_cases": 11, "passed": 9, "failed": 0, "not_scored": 2,
        "by_failure_class": {"source_data_coverage": 1},
    }
    unsupported = next(item for item in results if item["case_id"] == "plan.unsupported.member-favourite-colour")
    # This supported fake draft exercises only the manual-review/not-scored
    # accounting path; it is not evidence that a model recognizes unsupported wording.
    assert unsupported["evaluation"] == "not_scored"
    assert unsupported["planner_result"]["status"] == "validated_plan"
    unavailable = next(item for item in results if item["case_id"] == "plan.coverage.unavailable-bill")
    assert unavailable["planner_result"] is None
    assert unavailable["failure_class"] == "source_data_coverage"
    assert all("sparql" not in item["planner_result"] for item in results if item["planner_result"])
    assert all(
        "SELECT DISTINCT ?entity ?label" in query
        or "SELECT DISTINCT ?contextType ?contextLabel" in query
        for query in fuseki.queries
    )


def test_phase_1_benchmark_is_not_changed_by_planner_cases():
    assert PLAN_CONTRACT["contractVersion"] == "1.0.1"
    assert "Bill" not in PLAN_CONTRACT["semanticVocabulary"]["entityTypes"]
