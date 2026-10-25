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


_TYPE_LABELS = {"Member": "Members", "DailTerm": "Dáil terms", "SeanadTerm": "Seanad terms",
                "DailConstituency": "Dáil constituencies", "SeanadPanel": "Seanad panels",
                "Committee": "Committees", "Bill": "Bills", "NamedOffice": "offices",
                "DebateRecord": "debates", "House": "Houses",
                "ParliamentaryMemberCollection": "parliamentary collections"}


def explain_plan(plan: dict, *, validated: bool, blocked_reason: str | None = None,
                 outcome_status: str | None = None) -> dict:
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
        row["plain"] = _filter_sentence(item, definition, entities)
        described_filters.append(row)
    sentences = _coherent_statement(plan, entities)
    failure = _plain_failure(blocked_reason, outcome_status, entities)
    return {"entities": described_entities, "requirements": described_requirements,
            "filters": described_filters, "temporal": plan.get("temporalConstraints", []),
            "aggregation": plan.get("aggregation"), "answer_shape": plan.get("answerShape", {}),
            "validated": validated, "blocked_reason": blocked_reason,
            "summary": sentences, "failure": failure,
            "answer_text": _answer_text(plan.get("answerShape", {}), plan.get("aggregation"))}


def _type_name(entity_type: str) -> str:
    return _TYPE_LABELS.get(entity_type, entity_type.replace("_", " ").lower())


def _coherent_statement(plan: dict, entities: dict) -> str:
    reqs = plan.get("requirements", [])
    # Say "same ... as" only where two explicit requirements share the same
    # result role and one names an entity while the other leaves that role open.
    for left in reqs:
        for right in reqs:
            if left is right or left.get("fact") != right.get("fact"):
                continue
            obj1, obj2 = left.get("object", {}), right.get("object", {})
            sub1, sub2 = left.get("subject", {}), right.get("subject", {})
            if obj1 == obj2 and obj1.get("type") and "entity" in sub1 and "entity" not in sub2:
                name = entities.get(sub1["entity"], {}).get("label", "the named Member")
                target = {"DailConstituency": "Dáil constituency"}.get(
                    obj1["type"], _type_name(obj1["type"]).rstrip("s"))
                if left["fact"] == "member_constituency_representation":
                    exclusions = [f.get("value") for f in plan.get("filters", [])
                                  if f.get("operator") == "not_equals"]
                    if name in exclusions:
                        return f"Find other Members who represented the same {target} as {name}, excluding {name}."
                    return f"Find other Members who represented the same {target} as {name}."
    answer = plan.get("answerShape", {})
    target = _type_name(answer.get("entityType", "results"))
    if len(reqs) == 1 and reqs[0].get("fact") == "member_identity":
        mention = next((e.get("label") for e in plan.get("entities", []) if e.get("type") == "Member"), None)
        return f"Find the Member {mention}." if mention else "Find Members."
    return f"Find {target} matching the relationships and conditions listed below."


def _answer_text(shape: dict, aggregation: dict | None) -> str:
    kind, entity_type = shape.get("kind"), shape.get("entityType")
    if kind == "entities": return f"Return a list of {_type_name(entity_type or 'results')}."
    if kind == "entity": return f"Return one {_type_name(entity_type or 'result').rstrip('s')} .".replace(" .", ".")
    if kind == "boolean": return "Return a yes-or-no answer."
    if kind == "count" or aggregation and aggregation.get("operation") == "count": return "Return a count."
    if kind == "label": return "Return a name or label."
    if kind in {"fact", "list"}: return "Return the requested fact value(s)."
    return "Return the requested result."


def _filter_sentence(item: dict, definition: dict, entities: dict) -> str:
    field = definition.get("description")
    operator = item.get("operator")
    value = item.get("value", "")
    value = entities.get(value.get("entity"), {}).get("label", "the referenced entity") if isinstance(value, dict) else value
    if not field:
        label = "name condition" if "name" in item.get("field", "") else "condition"
        if operator == "not_equals": return f"Exclude results matching the {label} {value}."
        if operator == "equals": return f"Keep results matching the {label} {value}."
        return f"Apply a {label} to the results."
    if operator == "not_equals": return f"Exclude results where {field.lower()} is {value}."
    if operator == "equals": return f"Keep results where {field.lower()} is {value}."
    if operator == "exists": return f"Only include results with {field.lower()} recorded."
    return f"Restrict results by {field.lower()} ({operator or 'condition'} {value})."


def _plain_failure(reason: str | None, status: str | None, entities: dict) -> str | None:
    if not reason and not status: return None
    if status == "validation_failure" and reason and "not supported for fact" in reason:
        filt = "Bertie Ahern" if any(e.get("label") == "Bertie Ahern" for e in entities.values()) else "the named entity"
        return f"The planner tried to exclude {filt} using a name condition that isn't supported for this type of query."
    if status == "ambiguous_entity": return "The entity reference matches more than one local record, so no record was selected."
    if status == "unresolved_entity": return "The referenced entity could not be matched to a local record."
    if status == "unsupported_request": return "This kind of query is not supported by the service."
    if status == "execution_failure": return "The plan passed validation, but the query could not be completed."
    if status == "validation_failure": return "The proposed plan is invalid and was not executed."
    return reason


def _participant(participant: dict | None, entities: dict) -> str:
    if not participant:
        return ""
    if "entity" in participant:
        entity = entities.get(participant["entity"], {})
        return f'{entity.get("label", participant["entity"])} ({entity.get("type", "entity")})'
    raw_type = participant.get("type", "")
    return {"DailConstituency": "Dáil constituency", "SeanadPanel": "Seanad panel",
            "Member": "Member", "DailTerm": "Dáil term", "SeanadTerm": "Seanad term",
            "Committee": "Committee", "Bill": "Bill", "NamedOffice": "office",
            "ParliamentaryMemberCollection": "parliamentary collection"}.get(
                raw_type, raw_type.replace("_", " ").lower())
