"""One reviewed bounded chain: current NamedOffice holder to current Dáil representation."""

from datetime import date
import re

from .composable_plan import (
    PlanOutcome, PlanError, _office_interval_plan, compile_office_evidence_query,
    inspect_office_holding_evidence, _mapped_member_interval, _require_local_iri,
)
from .errors import NLQError
from .member_resolution import resolve_local_entity_label
from .pagination import select_pages
from .representation import representation_plan, execute_representation, EDGES as REPRESENTATION_EDGES
from .results import QueryResult, format_debug_payload


FAMILY = "current_office_constituency"
EDGES = {**REPRESENTATION_EDGES,
         "member_has_office_holding": ("member", "holding"),
         "office_holding_of_office": ("holding", "office")}


def validate_request(question, mention):
    text = re.sub(re.escape(mention), "office", question, flags=re.I)
    if text == question or not re.fullmatch(
        r"\s*(?:(?:what|which)\s+(?:d[áa]il\s+)?constituency\s+does\s+(?:the\s+)?(?:current\s+)?office\s+"
        r"(?:currently\s+)?represent|which\s+(?:d[áa]il\s+)?constituency\s+is\s+(?:the\s+)?(?:current\s+)?office\s+"
        r"(?:currently\s+)?(?:a\s+)?(?:TD|deputy)\s+for)(?:\s+(?:now|today|currently))?\s*[?.!]?\s*", text, re.I,
    ):
        raise ValueError("Officeholder constituency supports only the current office-to-Member-to-current-Dáil path; no historical scope, additional condition or answer field can be dropped.")
    from .interpretation import current_relationship_scope
    if current_relationship_scope(question, mention) is None:
        raise ValueError("Officeholder constituency requires a present-time or explicit-current request.")


def make_plan(mention, as_of):
    refs = {"office": {"type": "NamedOffice", "mention": mention}, "holding": {"type": "OfficeHolding"},
            "member": {"type": "Member"}, "membership": {"type": "DailMembership"},
            "term": {"type": "DailTerm", "selector": {"kind": "currentTerm", "house": "Dail"}},
            "constituency": {"type": "DailConstituency"}}
    return {"version": 2, "asOf": as_of.isoformat(), "family": FAMILY, "referents": refs,
            "relations": [{"id": fact, "fact": fact, "from": source, "to": target}
                          for fact, (source, target) in EDGES.items()],
            "constraints": [{"referent": key, "field": "interval", "operator": "currentAt", "value": as_of.isoformat()}
                            for key in ("holding", "membership")],
            "answer": {"kind": "entities", "referent": "constituency", "distinctBy": "identity", "display": ["label"],
                       "preserveEvidence": True}}


def validate_office_representation_plan(plan):
    try:
        mention = plan["referents"]["office"]["mention"]
        if not isinstance(mention, str) or not mention.strip() or plan != make_plan(mention, date.fromisoformat(plan["asOf"])):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise PlanError("Officeholder constituency requires the complete closed current-office/current-Dáil chain.") from None
    return plan


def execute_office_representation(mention, *, as_of, fuseki, supported_predicates):
    plan = make_plan(mention, as_of)
    validate_office_representation_plan(plan)
    query = None
    try:
        office = resolve_local_entity_label("NamedOffice", mention, fuseki, supported_predicates=supported_predicates)
        if office.state == "ambiguous":
            return PlanOutcome("ambiguous", plan=plan, candidates=tuple({"iri": c.iri, "label": c.label} for c in office.candidates),
                               diagnostic="Several reviewed NamedOffice identities match; none was selected.", request_family=FAMILY)
        if office.state != "resolved" or len(office.candidates) != 1:
            raise NLQError("No unambiguous reviewed NamedOffice identity is locally evidenced; no Member was guessed.")
        candidate = office.candidates[0]
        office_plan = _office_interval_plan(as_of=as_of, office=mention, start=as_of, end=as_of, scope="calendarDate")
        office_plan["referents"]["office"].update(resolution="resolved", iri=candidate.iri, label=candidate.label)
        query = compile_office_evidence_query(office_plan, supported_predicates=supported_predicates, preserve_unlabelled=True)
        evidence = select_pages(query, fuseki=fuseki, supported_predicates=supported_predicates)
        _, active_ids, issues = inspect_office_holding_evidence(evidence, office_plan)
        if issues:
            raise NLQError("Accepted OfficeHolding evidence is missing, conflicting or uncertain: " + "; ".join(issues))
        # Validate the whole accepted evidence set before selecting one relationship.
        holdings = {}
        for row in evidence.rows:
            record = dict(zip(evidence.columns, row))
            holding = _require_local_iri(record["holding_holding"], "OfficeHolding")
            member = _require_local_iri(record["member_member"], "Member")
            interval = _mapped_member_interval({(record["holdingDateRange"], record["holdingStart"], record["holdingEnd"])}, label="OfficeHolding")
            item = (member, record["memberName"].removesuffix("@en"), record["holdingDateRange"], interval)
            if holding in holdings and holdings[holding] != item:
                raise NLQError("Conflicting accepted OfficeHolding relationship evidence.")
            holdings[holding] = item
        if not active_ids:
            raise NLQError(f"No accepted current OfficeHolding for {candidate.label} ({candidate.iri}) is locally evidenced at {as_of.isoformat()}. "
                           "No officeholder or constituency was substituted. Local current-office coverage is not certified; this does not establish a vacancy.")
        if len(active_ids) != 1:
            raise NLQError("More than one accepted current OfficeHolding relationship is locally recorded; no officeholder was selected.")
        holding = next(iter(active_ids))
        member, name, range_iri, (start, end) = holdings[holding]
        if name == "—" or not name.strip():
            raise NLQError("The accepted officeholder has no usable local Member name.")
        # Exact identity is supplied by code, never re-resolved from its display name.
        child = execute_representation(representation_plan(as_of=as_of, member=name), fuseki=fuseki,
                                       supported_predicates=supported_predicates, resolved_member=(member, name),
                                       preserve_membership_evidence=True)
        if child.status != "success" or child.result is None:
            return PlanOutcome("source_data_unavailable", plan=plan, sparql=child.sparql,
                               diagnostic=f"Locally evidenced {candidate.label} officeholder: {name} ({member}), holding {holding}, "
                                          f"range {range_iri}, {start.isoformat()} – {end.isoformat() if end else 'open-ended'}. "
                                          f"No current Dáil constituency can be established at {as_of.isoformat()}: {child.diagnostic} "
                                          "The officeholder is not assumed to be a TD; no historical constituency was substituted. Current-office roster completeness is not certified.",
                               request_family=FAMILY)
        result = child.result
        constituency_index = result.columns.index("Constituency identity")
        if len({row[constituency_index] for row in result.rows}) != 1:
            raise NLQError("Conflicting current Dáil constituency identities for the exact accepted officeholder.")
        office_columns = ("Named office", "Office identity", "Holding identity", "Holding date range", "Holding start", "Holding end")
        office_values = (candidate.label, candidate.iri, holding, range_iri, start.isoformat(), end.isoformat() if end else "open-ended")
        return PlanOutcome("success", plan=plan, sparql=child.sparql,
                           result=QueryResult("select", result.columns + office_columns, tuple(row + office_values for row in result.rows),
                                              raw_json=format_debug_payload({"officeEvidence": {"query": query, "columns": evidence.columns, "rows": evidence.rows},
                                                                    "representationEvidence": {"query": child.sparql, "columns": result.columns, "rows": result.rows},
                                                                    "exactMemberIdentity": member})),
                           diagnostic=f"Locally evidenced accepted officeholder and independently dated Dáil representation at {as_of.isoformat()}. "
                                      "Exact Member identity joins the two relationships; not a certified complete current-office or government roster. Missing ends remain open-ended.", request_family=FAMILY)
    except (NLQError, PlanError) as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, diagnostic=str(error), request_family=FAMILY)
