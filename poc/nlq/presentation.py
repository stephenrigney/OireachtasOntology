"""Deterministic human-readable views over the existing query-plan contract."""

from __future__ import annotations

from .plan_contract import load_query_plan_contract
from .plan_sparql import _FACTS, _FILTERS


def capability_catalogue() -> list[dict]:
    vocabulary = load_query_plan_contract()["semanticVocabulary"]
    facts = {fact["id"]: fact for fact in vocabulary["facts"]}
    filters_by_fact: dict[str, list[dict]] = {}
    for item in vocabulary["filterFields"]:
        for fact_id in item["facts"]:
            filters_by_fact.setdefault(fact_id, []).append(item)
    for fact_id, fact in facts.items():
        fact["filters"] = filters_by_fact.get(fact_id, [])
        fact["status"] = "Executable" if fact_id in _FACTS else "Expressible, compiler unsupported"
    return list(facts.values())


def catalogue_metadata() -> dict:
    contract = load_query_plan_contract()
    semantics = contract["planSemantics"]
    return {"answer_shapes": semantics["answerShapes"],
            "temporal_constraints": ["on", "before", "after", "during", "interval", "current"]}


def explain_plan(plan: dict, *, validated: bool, blocked_reason: str | None = None) -> dict:
    vocabulary = load_query_plan_contract()["semanticVocabulary"]
    facts = {fact["id"]: fact["description"] for fact in vocabulary["facts"]}
    fields = {item["id"]: item for item in vocabulary["filterFields"]}
    entities = {item["id"]: item for item in plan.get("entities", [])}
    requirements = {item["id"]: item for item in plan.get("requirements", [])}
    described_entities = []
    for entity in plan.get("entities", []):
        row = dict(entity)
        row["human_resolution"] = {"resolved": "Resolved to a local record", "ambiguous": "Several local matches; none selected", "unresolved": "No exact local match"}.get(entity.get("resolution"), "Not confirmed")
        described_entities.append(row)
    described_requirements = []
    for item in plan.get("requirements", []):
        row = dict(item)
        row["description"] = facts.get(item.get("fact"), item.get("fact", ""))
        row["subject_label"] = _participant(item.get("subject"), entities)
        row["object_label"] = _participant(item.get("object"), entities)
        described_requirements.append(row)
    described_filters = []
    for item in plan.get("filters", []):
        row = dict(item)
        definition = fields.get(item.get("field"), {})
        row["description"] = definition.get("description", item.get("field", ""))
        row["requirement_fact"] = requirements.get(item.get("requirement"), {}).get("fact", "")
        described_filters.append(row)
    return {"entities": described_entities, "requirements": described_requirements,
            "filters": described_filters, "temporal": plan.get("temporalConstraints", []),
            "aggregation": plan.get("aggregation"), "answer_shape": plan.get("answerShape", {}),
            "validated": validated, "blocked_reason": blocked_reason}


def _participant(participant: dict | None, entities: dict) -> str:
    if not participant:
        return ""
    if "entity" in participant:
        entity = entities.get(participant["entity"], {})
        return f'{entity.get("label", participant["entity"])} ({entity.get("type", "entity")})'
    return participant.get("type", "")
