"""Dependency-light loader and validator for semantic query plans.

This module validates the Phase 2A contract only. It is deliberately not wired
into the live NLQ pipeline and has no LLM, RDF, or Fuseki dependency.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


CONTRACT_PATH = Path(__file__).resolve().parents[1] / "specs" / "query-plan-contract.json"
SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_CONTRACT_MAJOR = 1
CONTRACT_ID = "https://data.oireachtas.ie/specs/query-plan-contract"
CONTRACT_SCHEMA_PATH = "poc/specs/query-plan-contract.schema.json"
PLAN_SCHEMA_PATH = "poc/specs/query-plan.schema.json"
_JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_LOCAL_IRI = re.compile(r"^https://data\.oireachtas\.ie/[^\s?#]+$")

ENTITY_TYPES = frozenset({
    "Member",
    "House",
    "DailTerm",
    "SeanadTerm",
    "ParliamentaryMemberCollection",
    "DailConstituency",
    "SeanadPanel",
    "Committee",
})
RESOLUTION_STATES = frozenset({"resolved", "ambiguous", "unresolved"})
FILTER_OPERATORS = frozenset({
    "equals", "not_equals", "greater_than", "greater_than_or_equal",
    "less_than", "less_than_or_equal", "exists",
})
TEMPORAL_KINDS = frozenset({"on", "before", "after", "during", "interval", "current"})
AGGREGATION_OPERATIONS = frozenset({"count"})
ANSWER_SHAPES = frozenset({
    "boolean", "entity", "entities", "label", "fact", "list", "count", "grouped_result",
})
_TERM_TYPES = frozenset({"DailTerm", "SeanadTerm"})
_RESERVED_IMPLEMENTATION_FIELDS = frozenset({
    "sparql", "query", "queryText", "queryFragment", "graph", "graphs", "graphIri",
    "graphIris", "namedGraph", "namedGraphs", "graphPattern", "triplePatterns",
    "variable", "variables", "variableName", "prefix", "prefixes", "endpoint",
    "endpoints", "dataset", "datasetId", "sourceSelection", "sources", "orderBy",
    "limit", "offset", "select", "ask", "where",
})
_RESOLUTION_SELECTION_FIELDS = frozenset({
    "selected", "selectedIri", "resolvedIri", "resolvedEntityIri", "selectedCandidate", "chosenCandidate",
})


class QueryPlanContractError(ValueError):
    """A plan is malformed, internally inconsistent, or not supported."""


def _error(message: str) -> None:
    raise QueryPlanContractError(message)


def _semver(value: Any, where: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not (match := _SEMVER.fullmatch(value)):
        _error(f"Query-plan {where} must be a semantic version (major.minor.patch).")
    return tuple(int(component) for component in match.groups())


def _check_supported_versions(document: dict[str, Any], where: str) -> None:
    schema_version = document.get("schemaVersion")
    if type(schema_version) is not int or schema_version != SUPPORTED_SCHEMA_VERSION:
        _error(
            f"Unsupported {where} schema version {schema_version!r}; "
            f"this consumer supports schema version {SUPPORTED_SCHEMA_VERSION}."
        )
    contract_major, _, _ = _semver(document.get("contractVersion"), "contractVersion")
    if contract_major != SUPPORTED_CONTRACT_MAJOR:
        _error(
            f"Unsupported {where} contract major version {contract_major}; "
            f"this consumer supports major version {SUPPORTED_CONTRACT_MAJOR}."
        )


def _nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(f"Query plan {where} must be a non-empty string.")
    return value


def _enum(value: Any, supported: frozenset[str], where: str) -> str:
    if not isinstance(value, str) or value not in supported:
        _error(f"Query plan {where} uses unsupported value {value!r}.")
    return value


def _identifier(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        _error(f"Query plan {where} must be a semantic identifier (letters, digits, '_' or '-').")
    return value


def _local_iri(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _LOCAL_IRI.fullmatch(value):
        _error(f"Query plan {where} must be a local Oireachtas IRI.")
    try:
        parsed = urlsplit(value)
    except ValueError:
        _error(f"Query plan {where} must be a local Oireachtas IRI.")
    if (
        parsed.scheme != "https"
        or parsed.hostname != "data.oireachtas.ie"
        or parsed.netloc != "data.oireachtas.ie"
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in value)
    ):
        _error(f"Query plan {where} must be a local Oireachtas IRI under https://data.oireachtas.ie/.")
    return value


def _date_value(value: Any, where: str) -> date:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        _error(f"Query plan {where} must be an ISO calendar date (YYYY-MM-DD).")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _error(f"Query plan {where} must be a valid ISO calendar date (YYYY-MM-DD).")


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _error(f"Query plan {where} must be an object.")
    return value


def _array(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        _error(f"Query plan {where} must be an array.")
    return value


def _required_fields(value: dict[str, Any], fields: tuple[str, ...], where: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        _error(f"Query plan {where} is missing required fields: {', '.join(missing)}.")


def _reject_reserved_fields(value: dict[str, Any], where: str) -> None:
    present = sorted(_RESERVED_IMPLEMENTATION_FIELDS.intersection(value))
    if present:
        _error(f"Query plan {where} contains implementation-specific field(s): {', '.join(present)}.")


def _validate_contract_manifest(document: Any) -> dict[str, Any]:
    manifest = _object(document, "contract root")
    if manifest.get("$schema") != _JSON_SCHEMA_DIALECT:
        _error(f"Query-plan contract $schema must be {_JSON_SCHEMA_DIALECT!r}.")
    _check_supported_versions(manifest, "query-plan contract")
    if manifest.get("contractId") != CONTRACT_ID:
        _error(f"Query-plan contract contractId must be {CONTRACT_ID!r}.")
    if manifest.get("contractSchema") != CONTRACT_SCHEMA_PATH:
        _error(f"Query-plan contract contractSchema must be {CONTRACT_SCHEMA_PATH!r}.")
    if manifest.get("planSchema") != PLAN_SCHEMA_PATH:
        _error(f"Query-plan contract planSchema must be {PLAN_SCHEMA_PATH!r}.")
    _nonempty_string(manifest.get("description"), "contract description")

    compatibility = _object(manifest.get("compatibility"), "contract compatibility")
    for field in ("schemaVersion", "compatibleChanges", "breakingChanges", "consumerSupport"):
        _nonempty_string(compatibility.get(field), f"contract compatibility.{field}")

    scope = _object(manifest.get("scope"), "contract scope")
    if scope.get("source") != "oireachtas" or scope.get("localOnly") is not True:
        _error("Query-plan contract scope must require local Oireachtas data.")
    if scope.get("sourceSelection") is not False or scope.get("federation") is not False:
        _error("Query-plan contract must not enable source selection or federation.")
    _nonempty_string(scope.get("purpose"), "contract scope.purpose")
    excluded = _array(scope.get("notIncluded"), "contract scope.notIncluded")
    if not excluded or any(not isinstance(item, str) or not item.strip() for item in excluded):
        _error("Query-plan contract scope.notIncluded must contain non-empty strings.")
    semantics = _object(manifest.get("planSemantics"), "contract planSemantics")
    for field in (
        "conjunction", "participantIdentity", "resolutionReadiness", "filterMeaning",
        "unknownExtensions", "iriValidation",
    ):
        _nonempty_string(semantics.get(field), f"contract planSemantics.{field}")
    return manifest


@lru_cache(maxsize=8)
def _load_contract_cached(path: str) -> dict[str, Any]:
    contract_path = Path(path)
    try:
        document = json.loads(contract_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise QueryPlanContractError(f"Could not read the query-plan contract at {contract_path}.") from error
    except json.JSONDecodeError as error:
        raise QueryPlanContractError(
            f"The query-plan contract at {contract_path} is not valid JSON: {error.msg}."
        ) from error
    return _validate_contract_manifest(document)


def load_query_plan_contract(path: str | Path | None = None) -> dict[str, Any]:
    """Load the versioned contract manifest and reject unsupported versions."""
    contract_path = Path(path) if path is not None else CONTRACT_PATH
    return _load_contract_cached(str(contract_path.resolve()))


def _participant_type(participant: Any, entities: dict[str, dict[str, Any]], where: str) -> str:
    participant = _object(participant, where)
    _reject_reserved_fields(participant, where)
    has_entity = "entity" in participant
    has_type = "type" in participant
    if has_entity == has_type:
        _error(f"Query plan {where} must identify exactly one entity or entity type.")
    if has_entity:
        entity_id = _identifier(participant["entity"], f"{where}.entity")
        if entity_id not in entities:
            _error(f"Query plan {where} refers to unknown entity {entity_id!r}.")
        return entities[entity_id]["type"]
    return _enum(participant["type"], ENTITY_TYPES, f"{where}.type")


def _validate_entities(raw_entities: Any) -> dict[str, dict[str, Any]]:
    values = _array(raw_entities, "entities")
    entities: dict[str, dict[str, Any]] = {}
    for index, raw_entity in enumerate(values):
        where = f"entities[{index}]"
        entity = _object(raw_entity, where)
        _reject_reserved_fields(entity, where)
        selected_fields = sorted(_RESOLUTION_SELECTION_FIELDS.intersection(entity))
        if selected_fields:
            _error(
                f"Query plan {where} must not use alternate entity-selection field(s): "
                f"{', '.join(selected_fields)}."
            )
        _required_fields(entity, ("id", "type", "label", "resolution"), where)
        entity_id = _identifier(entity["id"], f"{where}.id")
        if entity_id in entities:
            _error(f"Query plan entities contains duplicate id {entity_id!r}.")
        _enum(entity["type"], ENTITY_TYPES, f"{where}.type")
        _nonempty_string(entity["label"], f"{where}.label")
        resolution = _enum(entity["resolution"], RESOLUTION_STATES, f"{where}.resolution")

        if resolution == "resolved":
            if "candidates" in entity:
                _error(f"Resolved query-plan entity {entity_id!r} must not contain candidates.")
            _local_iri(entity.get("iri"), f"{where}.iri")
        elif resolution == "ambiguous":
            if "iri" in entity:
                _error(f"Ambiguous query-plan entity {entity_id!r} must not select a resolved IRI.")
            candidates = _array(entity.get("candidates"), f"{where}.candidates")
            if len(candidates) < 2:
                _error(f"Ambiguous query-plan entity {entity_id!r} requires at least two candidates.")
            candidate_iris: set[str] = set()
            for candidate_index, raw_candidate in enumerate(candidates):
                candidate_where = f"{where}.candidates[{candidate_index}]"
                candidate = _object(raw_candidate, candidate_where)
                _reject_reserved_fields(candidate, candidate_where)
                _required_fields(candidate, ("iri", "label"), candidate_where)
                iri = _local_iri(candidate["iri"], f"{candidate_where}.iri")
                _nonempty_string(candidate["label"], f"{candidate_where}.label")
                if iri in candidate_iris:
                    _error(f"Ambiguous query-plan entity {entity_id!r} contains duplicate candidate IRI {iri!r}.")
                candidate_iris.add(iri)
        else:
            if "iri" in entity or "candidates" in entity:
                _error(f"Unresolved query-plan entity {entity_id!r} must not contain an IRI or candidates.")
        entities[entity_id] = entity
    return entities


def _validate_requirements(raw_requirements: Any, entities: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    values = _array(raw_requirements, "requirements")
    if not values:
        _error("Query plan requirements must contain at least one requested fact or relation.")
    requirements: dict[str, dict[str, Any]] = {}
    for index, raw_requirement in enumerate(values):
        where = f"requirements[{index}]"
        requirement = _object(raw_requirement, where)
        _reject_reserved_fields(requirement, where)
        if "source" in requirement:
            _error(f"Query plan {where}.source is unsupported; source scope is local Oireachtas data only.")
        _required_fields(requirement, ("id", "fact", "subject"), where)
        requirement_id = _identifier(requirement["id"], f"{where}.id")
        if requirement_id in requirements:
            _error(f"Query plan requirements contains duplicate id {requirement_id!r}.")
        _nonempty_string(requirement["fact"], f"{where}.fact")
        _participant_type(requirement["subject"], entities, f"{where}.subject")
        if "object" in requirement:
            _participant_type(requirement["object"], entities, f"{where}.object")
        requirements[requirement_id] = requirement
    return requirements


def _validate_filters(raw_filters: Any, requirements: dict[str, dict[str, Any]], entities: dict[str, dict[str, Any]]) -> None:
    for index, raw_filter in enumerate(_array(raw_filters, "filters")):
        where = f"filters[{index}]"
        value = _object(raw_filter, where)
        _reject_reserved_fields(value, where)
        _required_fields(value, ("requirement", "field", "operator"), where)
        requirement_id = _identifier(value["requirement"], f"{where}.requirement")
        if requirement_id not in requirements:
            _error(f"Query plan {where} refers to unknown requirement {requirement_id!r}.")
        _nonempty_string(value["field"], f"{where}.field")
        operator = _enum(value["operator"], FILTER_OPERATORS, f"{where}.operator")
        if operator == "exists":
            if "value" in value:
                _error(f"Query plan {where} must not provide a value for the exists operator.")
            continue
        if "value" not in value:
            _error(f"Query plan {where}.value is required for operator {operator!r}.")
        filter_value = value["value"]
        if isinstance(filter_value, dict):
            _reject_reserved_fields(filter_value, f"{where}.value")
            _required_fields(filter_value, ("entity",), f"{where}.value")
            if "type" in filter_value:
                _error(f"Query plan {where}.value must not mix entity and entity-type references.")
            entity_id = _identifier(filter_value["entity"], f"{where}.value.entity")
            if entity_id not in entities:
                _error(f"Query plan {where}.value refers to unknown entity {entity_id!r}.")
        elif isinstance(filter_value, str):
            pass
        elif isinstance(filter_value, bool):
            pass
        elif isinstance(filter_value, int):
            pass
        elif isinstance(filter_value, float) and math.isfinite(filter_value):
            pass
        else:
            _error(f"Query plan {where}.value must be a string, number, boolean, or entity reference.")


def _validate_temporal_constraints(
    raw_constraints: Any,
    requirements: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
) -> None:
    for index, raw_constraint in enumerate(_array(raw_constraints, "temporalConstraints")):
        where = f"temporalConstraints[{index}]"
        constraint = _object(raw_constraint, where)
        _reject_reserved_fields(constraint, where)
        _required_fields(constraint, ("target", "kind"), where)
        target = _identifier(constraint["target"], f"{where}.target")
        if target not in requirements:
            _error(f"Query plan {where} refers to unknown requirement {target!r}.")
        kind = _enum(constraint["kind"], TEMPORAL_KINDS, f"{where}.kind")

        date_fields = {"date", "period", "start", "end"}
        present = date_fields.intersection(constraint)
        if kind in {"on", "before", "after"}:
            if "date" not in constraint or present != {"date"}:
                _error(f"Query plan {where} kind {kind!r} requires only a date value.")
            _date_value(constraint["date"], f"{where}.date")
        elif kind == "during":
            if "period" not in constraint or present != {"period"}:
                _error(f"Query plan {where} kind 'during' requires only a period.")
            period = _object(constraint["period"], f"{where}.period")
            _reject_reserved_fields(period, f"{where}.period")
            if "entity" in period:
                if "start" in period or "end" in period:
                    _error(f"Query plan {where}.period must contain either a term entity or a date window.")
                entity_id = _identifier(period["entity"], f"{where}.period.entity")
                if entity_id not in entities:
                    _error(f"Query plan {where}.period refers to unknown entity {entity_id!r}.")
                if entities[entity_id]["type"] not in _TERM_TYPES:
                    _error(f"Query plan {where}.period entity must be a DailTerm or SeanadTerm.")
            else:
                _required_fields(period, ("start", "end"), f"{where}.period")
                start = _date_value(period["start"], f"{where}.period.start")
                end = _date_value(period["end"], f"{where}.period.end")
                if start > end:
                    _error(f"Query plan {where}.period.start must be on or before period.end.")
        elif kind == "interval":
            if present != {"start", "end"}:
                _error(f"Query plan {where} kind 'interval' requires start and end dates only.")
            start = _date_value(constraint["start"], f"{where}.start")
            end = _date_value(constraint["end"], f"{where}.end")
            if start > end:
                _error(f"Query plan {where}.start must be on or before end.")
        elif present:
            _error(f"Query plan {where} kind 'current' must not contain date or period values.")


def _aggregation_reference_type(
    raw_reference: Any,
    where: str,
    requirements: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
) -> str:
    reference = _object(raw_reference, where)
    _reject_reserved_fields(reference, where)
    _required_fields(reference, ("requirement", "participant"), where)
    requirement_id = _identifier(reference["requirement"], f"{where}.requirement")
    if requirement_id not in requirements:
        _error(f"Query plan {where} refers to unknown requirement {requirement_id!r}.")
    position = _enum(reference["participant"], frozenset({"subject", "object"}), f"{where}.participant")
    requirement = requirements[requirement_id]
    if position not in requirement:
        _error(f"Query plan {where} refers to a missing {position} participant.")
    return _participant_type(requirement[position], entities, f"{where}.{position}")


def _validate_aggregation(
    raw_aggregation: Any,
    requirements: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if raw_aggregation is None:
        return None
    aggregation = _object(raw_aggregation, "aggregation")
    _reject_reserved_fields(aggregation, "aggregation")
    _required_fields(aggregation, ("operation", "target", "groupBy"), "aggregation")
    _enum(aggregation["operation"], AGGREGATION_OPERATIONS, "aggregation.operation")
    _aggregation_reference_type(aggregation["target"], "aggregation.target", requirements, entities)
    group_by = _array(aggregation["groupBy"], "aggregation.groupBy")
    normalized: set[tuple[str, str]] = set()
    for index, raw_reference in enumerate(group_by):
        where = f"aggregation.groupBy[{index}]"
        _aggregation_reference_type(raw_reference, where, requirements, entities)
        reference = _object(raw_reference, where)
        key = (reference["requirement"], reference["participant"])
        if key in normalized:
            _error(f"Query plan aggregation.groupBy contains duplicate reference {key!r}.")
        normalized.add(key)
    return aggregation


def _validate_answer_shape(
    raw_shape: Any,
    aggregation: dict[str, Any] | None,
    requirements: dict[str, dict[str, Any]],
    entities: dict[str, dict[str, Any]],
) -> None:
    shape = _object(raw_shape, "answerShape")
    _reject_reserved_fields(shape, "answerShape")
    _required_fields(shape, ("kind",), "answerShape")
    kind = _enum(shape["kind"], ANSWER_SHAPES, "answerShape.kind")

    if kind == "boolean":
        if "target" in shape or "entityType" in shape:
            _error("Boolean query-plan answerShape must not specify target or entityType.")
    elif kind in {"entity", "entities"}:
        if "entityType" not in shape or "target" in shape:
            _error(f"Query plan answerShape kind {kind!r} requires entityType and no target.")
        entity_type = _enum(shape["entityType"], ENTITY_TYPES, "answerShape.entityType")
        participant_types = {
            _participant_type(requirement[position], entities, f"requirements.{requirement_id}.{position}")
            for requirement_id, requirement in requirements.items()
            for position in ("subject", "object")
            if position in requirement
        }
        if entity_type not in participant_types:
            _error(f"Query plan answerShape entityType {entity_type!r} is not requested by any requirement.")
    elif kind in {"label", "fact", "list"}:
        if "target" not in shape or "entityType" in shape:
            _error(f"Query plan answerShape kind {kind!r} requires a requirement target and no entityType.")
        target = _identifier(shape["target"], "answerShape.target")
        if target not in requirements:
            _error(f"Query plan answerShape refers to unknown requirement {target!r}.")
    else:
        if shape.get("target") != "aggregation" or "entityType" in shape:
            _error(f"Query plan answerShape kind {kind!r} requires target 'aggregation'.")
        if aggregation is None:
            _error(f"Query plan answerShape kind {kind!r} requires an aggregation.")
        if kind == "count" and aggregation["groupBy"]:
            _error("Count answer shape requires an aggregation without groupBy fields.")
        if kind == "grouped_result" and not aggregation["groupBy"]:
            _error("Grouped-result answer shape requires at least one groupBy field.")

    if aggregation is not None and kind not in {"count", "grouped_result"}:
        _error("Query plan aggregation is only compatible with count or grouped_result answer shapes.")


def validate_query_plan(document: Any, *, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a semantic query plan and return it unchanged.

    Unknown optional fields are ignored for compatible major-version
    extensions, but unsupported semantic states and known SPARQL/graph/source
    implementation fields fail closed.
    """
    active_contract = contract if contract is not None else load_query_plan_contract()
    plan = _object(document, "root")
    _reject_reserved_fields(plan, "root")
    if plan.get("contractId") != active_contract.get("contractId"):
        _error(f"Query plan contractId must be {active_contract.get('contractId')!r}.")
    _check_supported_versions(plan, "query plan")
    _required_fields(
        plan,
        (
            "contractId", "schemaVersion", "contractVersion", "intent", "source", "entities",
            "requirements", "filters", "temporalConstraints", "aggregation", "answerShape",
        ),
        "root",
    )
    if plan["source"] != "oireachtas":
        _error("Query plan source must be 'oireachtas'; only local Oireachtas data is supported.")
    _nonempty_string(plan["intent"], "intent")

    entities = _validate_entities(plan["entities"])
    requirements = _validate_requirements(plan["requirements"], entities)
    _validate_filters(plan["filters"], requirements, entities)
    _validate_temporal_constraints(plan["temporalConstraints"], requirements, entities)
    aggregation = _validate_aggregation(plan["aggregation"], requirements, entities)
    _validate_answer_shape(plan["answerShape"], aggregation, requirements, entities)
    return plan


def load_query_plan(
    path: str | Path,
    *,
    contract_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load and validate one versioned query-plan JSON document."""
    plan_path = Path(path)
    try:
        document = json.loads(plan_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise QueryPlanContractError(f"Could not read the query plan at {plan_path}.") from error
    except json.JSONDecodeError as error:
        raise QueryPlanContractError(f"The query plan at {plan_path} is not valid JSON: {error.msg}.") from error
    return validate_query_plan(document, contract=load_query_plan_contract(contract_path))
