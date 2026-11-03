"""Narrow, shared intent defaults; no entity or relation recognition."""

import re
from datetime import date


POLICY = "present_constituency_as_of"


def unsupported_whole_intent(question):
    """Unsupported projections invalidate the whole request before recognition."""
    if re.search(r"\b(?:elected|election|elections|re-elected)\b", question, re.I):
        return "Election-event evidence is not queryable; no membership start or partial compound answer was substituted."
    if (re.search(r"\b(?:constituenc(?:y|ies)|represent(?:ed|s|ing)?|TDs?)\b", question, re.I)
            and re.search(r"\b(?:how many|count|average|rank|most|fewest|percentage)\b", question, re.I)
            and re.search(r"\bseats?\b", question, re.I)):
        return "Seat allocations are not derived from recorded Member identities; no seat or election-event count was run."
    if (re.search(r"\b(?:which|what) d[áa]il\b", question, re.I)
            and re.search(r"\b(?:actual\s+)?sittings?\b", question, re.I)):
        return "House-term dates do not establish an actual sitting; no term was substituted for sitting evidence."
    if (re.search(r"\b(?:office\s+of|taoiseach|minister|president|secretary|chair)\b", question, re.I)
            and re.search(r"\b(?:throughout|the whole of|all of|the entire|for the full)\b", question, re.I)):
        return "Accepted OfficeHolding evidence supports interval overlap, not uninterrupted service throughout the requested period."
    return None


def semantic_composition_scope(question):
    """Keep compound representation requests out of singular-name recognizers.

    This only selects the existing semantic path; it never constructs a plan.
    """
    return bool(re.search(r"\b(?:constituenc(?:y|ies)|TDs?|represent(?:ed|s|ing)?)\b", question, re.I)
                and re.search(r"\b(?:and|or|while|same|shared)\b", question, re.I))


def present_constituency_default(question: str, constituency: str) -> bool:
    """Only unqualified present-tense constituency representation is defaulted.

    Callers must already have validated the supported representation graph and
    grounded its constituency mention. Explicit scope always wins.
    """
    text = re.sub(re.escape(constituency), " ", question, flags=re.I) if constituency else question
    if re.search(r"\b(?:did|were|was|had|will|would|should|could|might|may|can|shall|planned|planning|expected|future|next|tomorrow|historical|history|ever|previous|last|elected|election|during|throughout|before|after|since|until|between|as of|on|senators?|seanad|panels?)\b|[0-9]", text, re.I):
        return False
    return bool(re.search(r"\b(?:are|is|represent|represents|representing)\b", text, re.I))


def default_evidence(question: str, as_of: date) -> dict:
    return {"policy": POLICY, "question": question, "date": as_of.isoformat()}


def validate_default(plan: dict, *, constituency: str, current: bool) -> None:
    evidence = plan.get("interpretation")
    if evidence is None:
        return
    if (not current or not isinstance(evidence, dict)
            or set(evidence) != {"policy", "question", "date"}
            or evidence["policy"] != POLICY or evidence["date"] != plan["asOf"]
            or not isinstance(evidence["question"], str)
            or not constituency or not re.search(re.escape(constituency), evidence["question"], re.I)
            or not present_constituency_default(evidence["question"], constituency)):
        raise ValueError("Current representation default lacks approved scoped interpretation evidence.")


def office_holding_boundary(parameters, *, fuseki, supported_predicates):
    """Diagnose accepted-registry absence without inventing a tenure operation.

    Only the existing exact Member/NamedOffice resolver is used. Raw ministerial
    observations and membership starts are deliberately not consulted.
    """
    from .composable_plan import PlanOutcome, member_resolution_query, resolve_member, AmbiguousMember
    from .member_resolution import resolve_local_entity_label
    from .errors import NLQError, IdentityNotFound, QueryLimitError
    try:
        resolve_member(fuseki.query(member_resolution_query(parameters["member"], supported_predicates=supported_predicates)), parameters["member"])
        office = resolve_local_entity_label("NamedOffice", parameters["office"], fuseki,
                                           supported_predicates=supported_predicates)
    except AmbiguousMember as error:
        return PlanOutcome("ambiguous", diagnostic=str(error), candidates=error.candidates, request_family="composable_semantic")
    except NLQError as error:
        status = "not_found" if isinstance(error, IdentityNotFound) else "validation_failure" if isinstance(error, QueryLimitError) else "source_data_unavailable"
        return PlanOutcome(status, diagnostic=str(error), request_family="composable_semantic")
    if office.state == "unresolved":
        return PlanOutcome("source_data_unavailable", request_family="composable_semantic",
                           diagnostic=f"No accepted local NamedOffice identity is available for {parameters['office']}; accepted OfficeHolding evidence cannot establish this tenure. Unreviewed ministerial observations are not accepted holdings.")
    if office.state == "ambiguous":
        return PlanOutcome("ambiguous", request_family="composable_semantic",
                           candidates=tuple({"iri": c.iri, "label": c.label} for c in office.candidates),
                           diagnostic="Several accepted office identities match; none was selected.")
    return PlanOutcome("unsupported_request", request_family="composable_semantic",
                       diagnostic="The office identity is recorded, but this service has no complete-career Member/office tenure projection. Accepted dated office-overlap queries remain available; no tenure answer was inferred.")
