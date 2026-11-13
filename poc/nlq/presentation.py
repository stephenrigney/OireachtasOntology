"""Deterministic human-readable views over the existing query-plan contract.

Browser adapters publish a QueryPresentation with actual route identity,
independent interpretation/compilation/execution states, and one answer string
shared with feedback. Capability-specific plans and evidence remain native to
their existing executors; this is a presentation boundary, not a plan format.
"""

from __future__ import annotations

from dataclasses import dataclass

from .plan_contract import load_query_plan_contract
from .plan_sparql import _FACTS, _FILTERS


@dataclass(frozen=True)
class QueryPresentation:
    """Shared browser/feedback contract; adapters retain capability-specific plans.

    Route and stage states come only from dispatch/execution evidence. Result
    content is the same user-facing text used for feedback; technical evidence
    remains separately expandable in the browser.
    """

    query_method: dict
    interpretation: dict
    compilation: dict
    execution: dict
    answer: dict


_ROUTE_NAMES = {
    "current_member_composition": ("Relationship composition", "Combined parliamentary relationships to find Members satisfying both validated conditions."),
    "current_committee_members": ("Committee membership", "Checked recorded membership of the selected current Committee."),
    "member_lookup": ("Member identity lookup", "Resolved the requested Member against local identity records."),
    "previous_service": ("Previous Dáil service", "Checked recorded membership in the date-resolved previous Dáil."),
    "dail_duration": ("Dáil service-duration query", "Calculated duration from recorded dated membership episodes."),
    "term_count": ("Dáil-term count query", "Counted distinct recorded Dáil terms."),
    "seanad_entry": ("Seanad entry query", "Retrieved the earliest recorded dated Seanad membership evidence."),
    "seanad_representation": ("Seanad representation query", "Retrieved the recorded Seanad representation designation."),
    "current_collection": ("Current parliamentary collection query", "Checked recorded collection membership at the configured reference date."),
    "house_terms": ("House-term query", "Retrieved recorded House-term date evidence."),
    "dail_all": ("Dáil Member list", "Retrieved distinct Member identities with recorded Dáil membership."),
    "bill_lookup": ("Bill lookup", "Looked up the requested Bill in local Bill records."),
    "bills_published": ("Published Bills query", "Selected Bills with recorded Published activity in the requested year."),
    "non_enacted_bills": ("Bill status query", "Classified Bills using their recorded process status."),
    "committee_chair": ("Committee chair evidence query", "Checked the available chair evidence for the selected Committee."),
    "committee_conflict": ("Committee evidence query", "Reported the reviewed source-coverage conflict for the Committee."),
    "office_current_coverage": ("Current officeholder query", "Applied the accepted current-office coverage guard."),
    "office_overlap": ("Dated office query", "Checked accepted office-holding evidence for the requested period."),
    "office_point": ("Dated office query", "Checked accepted office-holding evidence for the requested date."),
    "dail_seats": ("Dáil seat-allocation query", "Retrieved the exact recorded Dáil HouseTerm seat complement."),
    "bill_quarantine": ("Bill source-availability query", "Checked the reviewed source-availability evidence for the Bill."),
    "member_relationship_composition": ("Relationship composition", "Combined parliamentary relationships to find Members satisfying the requested conditions."),
    "shared_dail_terms": ("Shared Dáil-term query", "Compared two Members’ recorded membership paths for the same Dáil term."),
    "constituency_representation": ("Constituency representation", "Looked up recorded Member and constituency representation."),
    "government_party_members": ("Government and party membership", "Matched recorded Cabinet and party-membership relationships."),
    "bill_lookup": ("Bill lookup", "Looked up the requested Bill in local Bill records."),
    "bill_sponsors": ("Bill sponsorship query", "Matched recorded Bill sponsorship and Member identities."),
    "current_office_constituency": ("Officeholder constituency query", "Joined the selected officeholder to recorded Dáil representation."),
    "office_holding_evidence": ("Office-holding evidence query", "Retrieved accepted local office-holding evidence."),
    "office_holding_window": ("Dated office query", "Checked accepted office-holding evidence for the requested date or period."),
    "debate_lookup": ("Debate record query", "Looked for a matching sitting and official debate record."),
    "member_party_history": ("Party history query", "Retrieved recorded political-affiliation episodes."),
    "capability_selection": ("Validated capability query", "Dispatched to an existing validated query capability."),
}


def query_method(*, family=None, capability=None, route=None, selected=False):
    """Readable method labels for the actual dispatch route, never answer inference."""
    if not selected:
        return {"name": "No query method selected", "description": "The question was rejected or stopped before an execution route was selected.", "identifier": None}
    key = capability or family or route
    if key == "phase1":
        return {"name": "Direct SPARQL translation", "description": "Translated the question to SPARQL and applied the existing local safety checks.", "identifier": "phase1_direct_sparql"}
    name, description = _ROUTE_NAMES.get(key, ("Validated query capability", "Used the selected existing query capability."))
    if capability:
        description += f" Selected capability: {capability.replace('_', ' ')}."
    return {"name": name, "description": description, "identifier": key}


def result_presentation(result, *, error=None, notice=None, context=None, answer_kind=None):
    """Build the common user answer and exact feedback text from returned values."""
    if error and result is None:
        actual = str(error)
        return {"kind": "refusal", "heading": "Unable to answer", "summary": actual,
                "columns": (), "rows": (), "actual": actual}
    if result is None:
        actual = "No answer was established from the available evidence."
        return {"kind": "refusal", "heading": "Unable to answer", "summary": actual,
                "columns": (), "rows": (), "actual": actual}
    if result.kind == "ask":
        answer = "Yes" if result.boolean else "No"
        actual = answer + (f"\n{notice}" if notice else "")
        return {"kind": "boolean", "heading": "Answer", "summary": answer,
                "columns": (), "rows": (), "actual": actual}
    columns = tuple(result.columns)
    rows = tuple(tuple(_readable_cell(value, columns[index] if index < len(columns) else "")
                       for index, value in enumerate(row)) for row in result.rows)
    is_count = (answer_kind == "count" or len(columns) == 1
                and columns[0].casefold() in {"count", "total", "number"})
    if rows:
        if is_count and len(rows) == 1 and len(rows[0]) == 1:
            summary = f"{rows[0][0]} matching records."
            columns, rows = (), ()
        elif len(columns) == 1 and columns[0].casefold() in {"member", "name", "td", "senator"}:
            noun = {"member": "Members", "name": "Results", "td": "TDs", "senator": "Senators"}[columns[0].casefold()]
            summary = f"{len(rows)} matching {noun.lower()}."
        else:
            summary = f"{len(rows)} matching result{'s' if len(rows) != 1 else ''}."
        heading = "Answer"
        lines = [" | ".join(f"{column}: {_feedback_cell(column, cell)}" for column, cell in zip(columns, row)) for row in rows]
        actual = "\n".join([summary, *([str(context)] if context else []), *lines,
                             *([str(error)] if error else []), *([str(notice)] if notice else [])])
    else:
        summary = "No matching records were found in the local dataset. This result does not establish historical completeness."
        heading = "Answer"
        actual = summary + (f"\n{context}" if context else "") + (f"\n{error}" if error else "") + (f"\n{notice}" if notice else "")
    return {"kind": "table" if len(columns) > 1 else "list", "heading": heading,
            "summary": summary, "context": context, "error": error, "notice": notice,
            "columns": columns, "rows": rows, "actual": actual}


def _readable_cell(value, column=""):
    # Raw RDF identifiers belong in technical evidence, not the answer view.
    if column == "Official debate" and isinstance(value, str) and value.startswith("https://data.oireachtas.ie/akn/ie/debateRecord/"):
        return value
    if column == "Official Bill" and isinstance(value, str) and value.startswith("https://data.oireachtas.ie/ie/oireachtas/bill/"):
        return value
    if isinstance(value, str) and value.startswith(("http://", "https://", "urn:")):
        return "Linked record (identifier in evidence)"
    return str(value)


def _feedback_cell(column, value):
    if column == "Official debate" and str(value).startswith("https://data.oireachtas.ie/akn/ie/debateRecord/"):
        return "Official debate record"
    if column == "Official Bill" and str(value).startswith("https://data.oireachtas.ie/ie/oireachtas/bill/"):
        return "Official Bill"
    return str(value)


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
