"""Model-produced semantic plans with deterministic local entity binding.

This is a distinct Phase 2B callable path. It neither generates nor executes
SPARQL from a plan, and it does not replace the Phase 1 NL-to-SPARQL pipeline.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import LLM_MAX_OUTPUT_TOKENS, LLM_TIMEOUT_SECONDS
from .errors import NLQError
from .member_resolution import (
    LocalEntityResolution,
    UnsupportedLocalEntityType,
    _label_position,
    resolve_local_entity_label,
)
from .plan_contract import QueryPlanContractError, validate_query_plan, load_query_plan_contract
from .results import format_debug_payload, format_debug_text


DRAFT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "specs" / "query-plan-draft.schema.json"
_LOCAL_IRI_TEXT = re.compile(r"https://data\.oireachtas\.ie/", re.IGNORECASE)
_URL_TEXT = re.compile(r"https?://\S+", re.IGNORECASE)
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

PLANNER_SYSTEM_GUIDANCE = """Interpret one natural-language question as a draft semantic query plan for local Oireachtas data.

Your role is semantic interpretation only. Do not produce or discuss SPARQL, RDF predicates, graph names/patterns, variables, endpoints, source selection, or query execution. Do not create, guess, copy, or return any IRI. Entity entries are only user-supplied type-and-label mentions; application code resolves them against local data.

Use only the supplied entity types, fact identifiers, filter identifiers/operators, temporal kinds, aggregation operations, and answer shapes. Interpret in this order: identify semantic entities and requested facts/relations; determine the requested answer role or value; apply actual filters and temporal scope; produce the draft. Do not substitute a nearby supported fact when the request is unsupported. If a fact or relationship is requested, express it with a supported semantic fact and correctly typed participants. Give each referenced user entity a stable semantic id; use an entity reference for that same entity throughout the plan, and use a type-only participant for an unbound result role. Requirements, filters, and temporal constraints are conjunctive.

Use temporal constraints only for temporal meaning actually expressed by the question. A `during` period is either a referenced DailTerm/SeanadTerm entity or a start/end date window. Date values use ISO YYYY-MM-DD. Aggregation currently supports only `count`; its target and optional groupBy refer to participants in requirements. Do not infer local data facts or entity identity from the question.

Return only the JSON object required by the strict response schema. Every optional field in that response shape is present as null when not applicable; nulls mean omission, not a semantic value."""


class PlannerModelError(RuntimeError):
    """The Responses endpoint failed before returning a draft JSON document."""

    def __init__(self, message: str, *, debug_output: str | None = None):
        super().__init__(message)
        self.debug_output = debug_output


class DraftStructureError(ValueError):
    """The model response does not have the closed draft-plan shape."""


class DraftSemanticError(ValueError):
    """The draft is structurally valid but inconsistent with the question."""


@dataclass(frozen=True)
class PlannerResult:
    """Inspectable terminal state of one structured-planner call."""

    status: str
    plan: dict[str, Any] | None = None
    draft_plan: dict[str, Any] | None = None
    failure_stage: str | None = None
    failure_class: str | None = None
    diagnostic: str | None = None
    debug_output: str | None = None

    @property
    def accepted(self) -> bool:
        return self.plan is not None and self.status in {
            "validated_plan", "clarification_required", "unresolved_entity",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "plan": self.plan,
            "draft_plan": self.draft_plan,
            "failure_stage": self.failure_stage,
            "failure_class": self.failure_class,
            "diagnostic": self.diagnostic,
            "debug_output": self.debug_output,
        }


def _read_draft_schema() -> dict[str, Any]:
    try:
        return json.loads(DRAFT_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load the structured planner schema: {error}") from error


def _response_schema() -> dict[str, Any]:
    """Return the closed JSON Schema sent to a Responses-compatible endpoint."""
    schema = _read_draft_schema()
    # These are repository artifact metadata, not keywords needed in the API's
    # strict structured-output subset. The complete local schema remains the
    # deterministic validation source in tests and documentation.
    return {
        key: value for key, value in schema.items()
        if key not in {"$schema", "$id", "title", "description"}
    }


def build_planner_instructions(contract: dict[str, Any] | None = None) -> str:
    """Ground the model only in the controlled semantic vocabulary."""
    active = contract if contract is not None else load_query_plan_contract()
    vocabulary = active["semanticVocabulary"]
    semantics = active["planSemantics"]
    entities = ", ".join(vocabulary["entityTypes"])
    facts = "\n".join(
        f"- {fact['id']}: {fact['description']} "
        f"(subject {', '.join(fact['subjectTypes'])}; "
        f"object {', '.join(fact['objectTypes']) if fact['objectTypes'] else 'none'})"
        for fact in vocabulary["facts"]
    )
    filters = "\n".join(
        f"- {field['id']}: {field['description']} "
        f"(facts {', '.join(field['facts'])}; {field['valueKind']}; "
        f"operators {', '.join(field['operators'])})"
        for field in vocabulary["filterFields"]
    )
    answer_shapes = "\n".join(
        f"- {shape['kind']}: {shape['description']}"
        for shape in semantics.get("answerShapes", [])
    )
    guidance = []
    if semantics.get("entityMentionMeaning"):
        guidance.append("Entity mentions: " + semantics["entityMentionMeaning"])
    if semantics.get("temporalScoping"):
        guidance.append("Temporal scoping: " + semantics["temporalScoping"])
    return (
        PLANNER_SYSTEM_GUIDANCE
        + "\n\nControlled entity types: " + entities
        + "\n\nControlled semantic facts:\n" + facts
        + "\n\nControlled filter fields:\n" + filters
        + "\n\nTemporal kinds: on, before, after, during, interval, current."
        + "\nAggregation operation: count."
        + ("\n\nAnswer shape meanings:\n" + answer_shapes if answer_shapes else "")
        + ("\n\n" + "\n".join(guidance) if guidance else "")
    )


def _response_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise PlannerModelError("The planner endpoint returned an unexpected response format.")
    if payload.get("status") not in (None, "completed"):
        raise PlannerModelError("The planner endpoint did not complete the request.")
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = payload.get("output")
    if isinstance(output, list):
        pieces = []
        for item in output:
            if not isinstance(item, dict) or not isinstance(item.get("content"), list):
                continue
            for content in item["content"]:
                if not isinstance(content, dict):
                    continue
                if content.get("type") == "refusal":
                    raise PlannerModelError("The model declined to produce a semantic plan.")
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    pieces.append(content["text"])
        if pieces:
            return "".join(pieces)
    raise PlannerModelError("The planner response did not contain structured output text.")


class ResponsesPlanGenerator:
    """One-call strict-schema draft generator for Responses-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        *,
        timeout: float = LLM_TIMEOUT_SECONDS,
        max_output_tokens: int = LLM_MAX_OUTPUT_TOKENS,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise PlannerModelError("Set NLQ_LLM_API_KEY before requesting a structured plan.")
        self.url = base_url.rstrip("/") + "/responses"
        self.model = model
        self.api_key = api_key
        self.max_output_tokens = max_output_tokens
        self.client = httpx.Client(timeout=timeout, transport=transport)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "oireachtas-nlq-poc/0.1",
        }

    def generate(self, question: str) -> str:
        """Make exactly one model request; never repair or automatically retry."""
        body = {
            "model": self.model,
            "instructions": build_planner_instructions(),
            "input": question,
            "text": {"format": {
                "type": "json_schema",
                "name": "oireachtas_query_plan_draft",
                "strict": True,
                "schema": _response_schema(),
            }},
            "max_output_tokens": self.max_output_tokens,
        }
        try:
            response = self.client.post(self.url, headers=self.headers, json=body)
        except httpx.TimeoutException as error:
            raise PlannerModelError("The structured planner request timed out.") from error
        except httpx.HTTPError as error:
            raise PlannerModelError("The structured planner endpoint could not be reached.") from error
        if response.is_error:
            try:
                payload = response.json()
                debug = format_debug_payload(payload, secrets=(self.api_key,))
            except ValueError:
                debug = format_debug_text(response.text, secrets=(self.api_key,))
            raise PlannerModelError(
                f"The structured planner endpoint returned HTTP {response.status_code}.",
                debug_output=debug,
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise PlannerModelError(
                "The structured planner endpoint returned a non-JSON response.",
                debug_output=format_debug_text(response.text, secrets=(self.api_key,)),
            ) from error
        try:
            return _response_text(payload)
        except PlannerModelError as error:
            raise PlannerModelError(
                str(error),
                debug_output=format_debug_payload(payload, secrets=(self.api_key,)),
            ) from error

    def close(self) -> None:
        self.client.close()


class _DuplicateJSONKey(ValueError):
    pass


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant {value}")


def parse_draft_json(output: str) -> Any:
    """Parse exactly one JSON draft, rejecting extensions such as NaN/duplicate keys."""
    if not isinstance(output, str):
        raise ValueError("model output is not text")
    try:
        value = json.loads(
            output,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (json.JSONDecodeError, _DuplicateJSONKey, ValueError) as error:
        raise ValueError(f"model output is not valid JSON: {error}") from error
    return value


def _reject_model_ir_is(value: Any, where: str = "draft") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in {
                "iri", "resolvediri", "resolvedentityiri", "selectediri",
                "candidates", "selectedcandidate", "chosencandidate",
            }:
                raise DraftStructureError(
                    f"model-supplied entity-resolution field {key!r} is forbidden at {where}.{key}"
                )
            _reject_model_ir_is(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_model_ir_is(child, f"{where}[{index}]")
    elif isinstance(value, str) and (_LOCAL_IRI_TEXT.search(value) or _URL_TEXT.search(value)):
        raise DraftStructureError(f"model-supplied IRI/URL text is forbidden at {where}")


def _exact_object(value: Any, fields: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DraftStructureError(f"{where} must be an object")
    missing = sorted(fields - value.keys())
    extra = sorted(value.keys() - fields)
    if missing:
        raise DraftStructureError(f"{where} is missing required fields: {', '.join(missing)}")
    if extra:
        raise DraftStructureError(f"{where} contains unsupported field(s): {', '.join(extra)}")
    return value


def _required_text(value: Any, where: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DraftStructureError(f"{where} must be a non-empty string")


def _required_identifier(value: Any, where: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise DraftStructureError(f"{where} must be a semantic identifier")


def _validate_participant_output(value: Any, where: str) -> None:
    participant = _exact_object(value, {"entity", "type"}, where)
    entity, entity_type = participant["entity"], participant["type"]
    if (entity is None) == (entity_type is None):
        raise DraftStructureError(
            f"{where} must set exactly one of entity or type; set the other to null"
        )
    if entity is not None:
        _required_identifier(entity, f"{where}.entity")
    if entity_type is not None:
        _required_text(entity_type, f"{where}.type")


def _validate_reference_output(value: Any, where: str) -> None:
    reference = _exact_object(value, {"requirement", "participant"}, where)
    _required_identifier(reference["requirement"], f"{where}.requirement")
    if reference["participant"] not in ("subject", "object"):
        raise DraftStructureError(f"{where}.participant must be 'subject' or 'object'")


def _validate_filter_output(
    item: dict[str, Any], where: str, filter_fields: dict[str, dict[str, Any]],
) -> None:
    _required_identifier(item["requirement"], f"{where}.requirement")
    field_id, operator, value = item["field"], item["operator"], item["value"]
    _required_text(field_id, f"{where}.field")
    _required_text(operator, f"{where}.operator")

    if operator == "exists":
        if value is not None:
            raise DraftStructureError(f"{where}.value must be null for the exists operator")
        return
    if value is None:
        raise DraftStructureError(f"{where}.value must not be null for operator {operator!r}")

    field = filter_fields.get(field_id)
    if field is None:
        # Keep unsupported semantic identifiers classified by the Phase 2A
        # vocabulary validator rather than treating them as malformed JSON.
        if isinstance(value, dict):
            reference = _exact_object(value, {"entity"}, f"{where}.value")
            _required_identifier(reference["entity"], f"{where}.value.entity")
        elif not isinstance(value, (str, int, float, bool)):
            raise DraftStructureError(f"{where}.value must be a JSON scalar or entity reference")
        return

    if operator not in field["operators"]:
        raise DraftStructureError(
            f"{where}.operator {operator!r} is not valid for field {field_id!r}"
        )
    value_kind = field["valueKind"]
    if value_kind == "string":
        if not isinstance(value, str):
            raise DraftStructureError(f"{where}.value must be a string for field {field_id!r}")
    elif value_kind == "number":
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or (isinstance(value, float) and not math.isfinite(value))
        ):
            raise DraftStructureError(f"{where}.value must be a finite number for field {field_id!r}")
    elif value_kind == "entity":
        reference = _exact_object(value, {"entity"}, f"{where}.value")
        _required_identifier(reference["entity"], f"{where}.value.entity")
    else:
        raise DraftStructureError(f"{where}.field {field_id!r} has an unsupported value kind")


def _validate_draft_output_shape(draft: dict[str, Any]) -> None:
    root = _exact_object(draft, {
        "draftSchemaVersion", "intent", "entities", "requirements", "filters",
        "temporalConstraints", "aggregation", "answerShape",
    }, "draft")
    if type(root["draftSchemaVersion"]) is not int or root["draftSchemaVersion"] != 1:
        raise DraftStructureError("draft.draftSchemaVersion must be 1")
    _required_text(root["intent"], "draft.intent")
    for field in ("entities", "requirements", "filters", "temporalConstraints"):
        if not isinstance(root[field], list):
            raise DraftStructureError(f"draft.{field} must be an array")
    if not root["requirements"]:
        raise DraftStructureError("draft.requirements must contain at least one requirement")

    for index, value in enumerate(root["entities"]):
        where = f"draft.entities[{index}]"
        entity = _exact_object(value, {"id", "type", "label"}, where)
        _required_identifier(entity["id"], f"{where}.id")
        for field in ("type", "label"):
            _required_text(entity[field], f"{where}.{field}")

    for index, value in enumerate(root["requirements"]):
        where = f"draft.requirements[{index}]"
        requirement = _exact_object(value, {"id", "fact", "subject", "object"}, where)
        _required_identifier(requirement["id"], f"{where}.id")
        _required_text(requirement["fact"], f"{where}.fact")
        _validate_participant_output(requirement["subject"], f"{where}.subject")
        if requirement["object"] is not None:
            _validate_participant_output(requirement["object"], f"{where}.object")

    filter_fields = {
        field["id"]: field
        for field in load_query_plan_contract()["semanticVocabulary"]["filterFields"]
    }
    for index, value in enumerate(root["filters"]):
        where = f"draft.filters[{index}]"
        item = _exact_object(value, {"requirement", "field", "operator", "value"}, where)
        _validate_filter_output(item, where, filter_fields)

    for index, value in enumerate(root["temporalConstraints"]):
        where = f"draft.temporalConstraints[{index}]"
        constraint = _exact_object(
            value, {"target", "kind", "date", "period", "start", "end"}, where,
        )
        _required_identifier(constraint["target"], f"{where}.target")
        _required_text(constraint["kind"], f"{where}.kind")
        for field in ("date", "start", "end"):
            if constraint[field] is not None:
                _required_text(constraint[field], f"{where}.{field}")
        period = constraint["period"]
        if constraint["period"] is not None:
            period = _exact_object(period, {"entity", "start", "end"}, f"{where}.period")
            for field in ("entity", "start", "end"):
                if period[field] is not None:
                    if field == "entity":
                        _required_identifier(period[field], f"{where}.period.{field}")
                    else:
                        _required_text(period[field], f"{where}.period.{field}")

        kind = constraint["kind"]
        if kind in {"on", "before", "after"}:
            valid = constraint["date"] is not None and period is None \
                and constraint["start"] is None and constraint["end"] is None
        elif kind == "during":
            valid = constraint["date"] is None and period is not None \
                and constraint["start"] is None and constraint["end"] is None
            if valid:
                entity_period = period["entity"] is not None
                date_period = period["start"] is not None and period["end"] is not None
                valid = (entity_period and period["start"] is None and period["end"] is None) \
                    or (period["entity"] is None and date_period)
        elif kind == "interval":
            valid = constraint["date"] is None and period is None \
                and constraint["start"] is not None and constraint["end"] is not None
        elif kind == "current":
            valid = constraint["date"] is None and period is None \
                and constraint["start"] is None and constraint["end"] is None
        else:
            raise DraftStructureError(f"{where}.kind is unsupported")
        if not valid:
            raise DraftStructureError(f"{where} has values that do not match temporal kind {kind!r}")

    aggregation = None
    if root["aggregation"] is not None:
        aggregation = _exact_object(
            root["aggregation"], {"operation", "target", "groupBy"}, "draft.aggregation",
        )
        _required_text(aggregation["operation"], "draft.aggregation.operation")
        if aggregation["operation"] != "count":
            raise DraftStructureError("draft.aggregation.operation must be 'count'")
        _validate_reference_output(aggregation["target"], "draft.aggregation.target")
        if not isinstance(aggregation["groupBy"], list):
            raise DraftStructureError("draft.aggregation.groupBy must be an array")
        for index, reference in enumerate(aggregation["groupBy"]):
            _validate_reference_output(reference, f"draft.aggregation.groupBy[{index}]")

    answer = _exact_object(root["answerShape"], {"kind", "target", "entityType"}, "draft.answerShape")
    _required_text(answer["kind"], "draft.answerShape.kind")
    for field in ("target", "entityType"):
        if answer[field] is not None:
            _required_text(answer[field], f"draft.answerShape.{field}")
    kind = answer["kind"]
    if kind == "boolean":
        valid_answer = answer["target"] is None and answer["entityType"] is None
    elif kind in {"entity", "entities"}:
        valid_answer = answer["target"] is None and answer["entityType"] is not None
    elif kind in {"label", "fact", "list"}:
        valid_answer = answer["target"] is not None and answer["entityType"] is None
        if valid_answer:
            _required_identifier(answer["target"], "draft.answerShape.target")
    elif kind in {"count", "grouped_result"}:
        valid_answer = answer["target"] == "aggregation" and answer["entityType"] is None
    else:
        raise DraftStructureError(f"draft.answerShape.kind {kind!r} is unsupported")
    if not valid_answer:
        raise DraftStructureError(f"draft.answerShape fields do not match kind {kind!r}")

    if kind in {"count", "grouped_result"}:
        if aggregation is None:
            raise DraftStructureError(f"answer shape {kind!r} requires an aggregation")
        if kind == "count" and aggregation["groupBy"]:
            raise DraftStructureError("count answer shape requires an empty aggregation.groupBy")
        if kind == "grouped_result" and not aggregation["groupBy"]:
            raise DraftStructureError("grouped_result answer shape requires aggregation.groupBy")
    elif aggregation is not None:
        raise DraftStructureError("aggregation is only valid with count or grouped_result answer shapes")


def _normalise_participant(value: dict[str, Any]) -> dict[str, str]:
    if value["entity"] is not None:
        return {"entity": value["entity"]}
    if value["type"] is not None:
        return {"type": value["type"]}
    raise DraftStructureError("participant must name one entity or one entity type")


def _drop_null_fields(value: dict[str, Any]) -> dict[str, Any]:
    return {key: child for key, child in value.items() if child is not None}


def normalise_draft_output(draft: Any) -> dict[str, Any]:
    """Convert strict JSON's required null slots to the canonical draft shape."""
    _reject_model_ir_is(draft)
    _validate_draft_output_shape(draft)
    normalised = {
        "intent": draft["intent"],
        "entities": [dict(entity) for entity in draft["entities"]],
        "requirements": [
            {
                "id": value["id"],
                "fact": value["fact"],
                "subject": _normalise_participant(value["subject"]),
                **({"object": _normalise_participant(value["object"])}
                   if value["object"] is not None else {}),
            }
            for value in draft["requirements"]
        ],
        "filters": [],
        "temporalConstraints": [],
        "aggregation": None,
        "answerShape": _drop_null_fields(dict(draft["answerShape"])),
    }
    for value in draft["filters"]:
        # Model entity filter values use a closed, IRI-free identifier reference.
        normalised_filter = _drop_null_fields(dict(value))
        if isinstance(value["value"], dict):
            normalised_filter["value"] = dict(value["value"])
        normalised["filters"].append(normalised_filter)

    for value in draft["temporalConstraints"]:
        constraint = _drop_null_fields({
            key: child for key, child in value.items() if key != "period"
        })
        if value["period"] is not None:
            constraint["period"] = _drop_null_fields(dict(value["period"]))
        normalised["temporalConstraints"].append(constraint)

    if draft["aggregation"] is not None:
        normalised["aggregation"] = {
            "operation": draft["aggregation"]["operation"],
            "target": dict(draft["aggregation"]["target"]),
            "groupBy": [dict(reference) for reference in draft["aggregation"]["groupBy"]],
        }
    return normalised


def _provisional_plan(draft: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "contractId": contract["contractId"],
        "schemaVersion": contract["schemaVersion"],
        "contractVersion": contract["contractVersion"],
        "intent": draft["intent"],
        "source": "oireachtas",
        "entities": [
            {**entity, "resolution": "unresolved"}
            for entity in draft["entities"]
        ],
        "requirements": draft["requirements"],
        "filters": draft["filters"],
        "temporalConstraints": draft["temporalConstraints"],
        "aggregation": draft["aggregation"],
        "answerShape": draft["answerShape"],
    }


def _unsupported_contract_vocabulary(error: QueryPlanContractError) -> bool:
    return "unsupported value" in str(error).lower()


def _resolution_entity(
    mention: dict[str, Any],
    resolution: LocalEntityResolution,
) -> dict[str, Any]:
    entity = {
        "id": mention["id"],
        "type": mention["type"],
        "label": mention["label"],
        "resolution": resolution.state,
    }
    if resolution.state == "resolved" and len(resolution.candidates) == 1:
        entity["iri"] = resolution.candidates[0].iri
    elif resolution.state == "ambiguous" and len(resolution.candidates) >= 2:
        entity["candidates"] = [
            {"iri": candidate.iri, "label": candidate.label}
            for candidate in resolution.candidates
        ]
    elif resolution.state != "unresolved":
        raise ValueError(f"Resolver returned inconsistent state {resolution.state!r}")
    return entity


class StructuredPlanner:
    """Interpret, locally resolve, and validate one semantic plan."""

    def __init__(self, generator, fuseki, *, supported_predicates=None):
        self.generator = generator
        self.fuseki = fuseki
        self.supported_predicates = supported_predicates
        self.contract = load_query_plan_contract()

    def plan(self, question: str) -> PlannerResult:
        """Run one model call and stop after final Phase 2A contract validation."""
        if not isinstance(question, str) or not question.strip():
            return PlannerResult(
                "invalid_model_output", failure_stage="model_response",
                failure_class="invalid_model_response", diagnostic="Question must be non-empty text.",
            )
        try:
            output = self.generator.generate(question)
        except PlannerModelError as error:
            return PlannerResult(
                "invalid_model_output", failure_stage="model_response",
                failure_class="invalid_model_response", diagnostic=str(error),
                debug_output=error.debug_output,
            )
        except Exception as error:
            return PlannerResult(
                "invalid_model_output", failure_stage="model_response",
                failure_class="invalid_model_response", diagnostic=str(error),
            )

        try:
            parsed = parse_draft_json(output)
        except ValueError as error:
            return PlannerResult(
                "invalid_model_output", failure_stage="model_json",
                failure_class="invalid_model_json", diagnostic=str(error),
                debug_output=format_debug_text(output if isinstance(output, str) else repr(output)),
            )

        try:
            draft = normalise_draft_output(parsed)
            for index, entity in enumerate(draft["entities"]):
                if _label_position(question, entity["label"]) is None:
                    raise DraftSemanticError(
                        f"draft.entities[{index}].label is not an exact user-supplied label mention"
                    )
        except DraftStructureError as error:
            return PlannerResult(
                "invalid_draft_structure", failure_stage="draft_validation",
                failure_class="invalid_draft_structure", diagnostic=str(error),
                debug_output=format_debug_text(output),
            )
        except DraftSemanticError as error:
            return PlannerResult(
                "invalid_draft_semantics", failure_stage="draft_validation",
                failure_class="invalid_draft_semantics", diagnostic=str(error),
                debug_output=format_debug_text(output),
            )

        provisional = _provisional_plan(draft, self.contract)
        try:
            validate_query_plan(provisional, contract=self.contract)
        except QueryPlanContractError as error:
            if _unsupported_contract_vocabulary(error):
                return PlannerResult(
                    "unsupported_vocabulary", draft_plan=draft,
                    failure_stage="draft_validation", failure_class="unsupported_vocabulary",
                    diagnostic=str(error), debug_output=format_debug_text(output),
                )
            return PlannerResult(
                "invalid_draft_semantics", draft_plan=draft,
                failure_stage="draft_validation", failure_class="invalid_draft_semantics",
                diagnostic=str(error), debug_output=format_debug_text(output),
            )

        resolved_entities = []
        for mention in draft["entities"]:
            try:
                resolution = resolve_local_entity_label(
                    mention["type"], mention["label"], self.fuseki,
                    supported_predicates=self.supported_predicates,
                    question_context=question,
                )
                resolved_entities.append(_resolution_entity(mention, resolution))
            except UnsupportedLocalEntityType as error:
                return PlannerResult(
                    "entity_resolution_failure", draft_plan=draft,
                    failure_stage="entity_resolution",
                    failure_class="unsupported_entity_resolution", diagnostic=str(error),
                )
            except NLQError as error:
                return PlannerResult(
                    "source_data_prerequisite_unavailable", draft_plan=draft,
                    failure_stage="entity_resolution",
                    failure_class="source_data_prerequisite_unavailable", diagnostic=str(error),
                )
            except ValueError as error:
                return PlannerResult(
                    "entity_resolution_failure", draft_plan=draft,
                    failure_stage="entity_resolution", failure_class="entity_resolution_failure",
                    diagnostic=str(error),
                )

        final_plan = {
            **provisional,
            "entities": resolved_entities,
        }
        try:
            # The final accepted object always passes the authoritative Phase 2A
            # validator, including ambiguity and unresolved terminal plans.
            accepted_plan = validate_query_plan(final_plan, contract=self.contract)
        except QueryPlanContractError as error:
            return PlannerResult(
                "final_plan_validation_failure", draft_plan=draft,
                failure_stage="final_validation", failure_class="final_plan_validation_failure",
                diagnostic=str(error),
            )

        resolutions = {entity["resolution"] for entity in resolved_entities}
        if "ambiguous" in resolutions:
            status = "clarification_required"
        elif "unresolved" in resolutions:
            status = "unresolved_entity"
        else:
            status = "validated_plan"
        return PlannerResult(status, plan=accepted_plan, draft_plan=draft)
