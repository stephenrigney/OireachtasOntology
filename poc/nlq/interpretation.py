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


def current_office_point_mention(question: str) -> str | None:
    """Extract a candidate office mention from a date-less current-holder form.

    This is only a lexical scope gate. Callers still require exact local
    NamedOffice identity resolution, the semantic planner must preserve the
    mention, and execution supplies ``asOf``; no identity or date is inferred.
    """
    text = re.sub(r"[?.!]+$", "", question.strip())
    match = re.fullmatch(
        r"who\s+(?:(?:currently|now|today)\s+)?(?:is|are)"
        r"(?:\s+(?:currently|now|today))?\s+(?P<office>.+)",
        text, re.IGNORECASE,
    )
    if match is None:
        return None
    office = match["office"].strip()
    office = re.sub(
        r"^(?:(?:the|a|an)\s+)?(?:(?:current|currently|present|now|today)\s+)?"
        r"(?:(?:the|a|an)\s+)?",
        "", office, flags=re.IGNORECASE,
    )
    office = re.sub(
        r"\s+(?:(?:currently|now|today|present)|as\s+of\s+(?:now|today|the\s+current\s+date))$",
        "", office, flags=re.IGNORECASE,
    ).strip()
    if not office:
        return None
    # No explicit/historical period or additional relationship may be
    # smuggled into the unqualified current-point shape.
    if re.search(
        r"[0-9]|\b(?:on|in|during|before|after|since|until|between|throughout|from|to|"
        r"as\s+of|elected|election|and|while|whose|members?|tds?|constituenc(?:y|ies)|"
        r"party|parties|how\s+many|count)\b|"
        r"\b(?:sponsor|author|chair(?:person|man)?|member|holder)\s+of\b",
        office, re.IGNORECASE,
    ):
        return None
    return office


def current_office_point_request(question: str) -> bool:
    """Whether the question has the surface form of a date-less current lookup."""
    return current_office_point_mention(question) is not None


def present_constituency_default(question: str, constituency: str) -> bool:
    """Only unqualified present-tense constituency representation is defaulted.

    Callers must already have validated the supported representation graph and
    grounded its constituency mention. Explicit scope always wins.
    """
    text = re.sub(re.escape(constituency), " ", question, flags=re.I) if constituency else question
    if re.search(r"\b(?:did|were|was|had|will|would|should|could|might|may|can|shall|planned|planning|expected|future|next|tomorrow|historical|history|ever|previous|last|elected|election|during|throughout|before|after|since|until|between|as of|on|senators?|seanad|panels?)\b|[0-9]", text, re.I):
        return False
    return bool(re.search(r"\b(?:are|is|represent|represents|representing)\b", text, re.I))


def member_relationship_as_of_default(question: str, constituency: str) -> bool:
    """Resolve the one-term Member projection's term-vs-active wording.

    In this bounded projection, an unqualified ``in this Dáil`` explicitly
    selects the House-date-resolved term and is term-wide, regardless of verb
    tense. Explicit current-point qualifiers retain the as-of membership test;
    explicit calendar dates remain governed by their exact date constraint.
    """
    if re.search(r"\bin\s+this\s+d[áa]il\b", question, re.I) and not re.search(
        r"\b(?:current(?:ly)?|now|today)\b|\bas\s+of\b", question, re.I,
    ):
        return False

    text = re.sub(re.escape(constituency), " ", question, flags=re.I) if constituency else question
    explicit_current_point = bool(re.search(
        r"\b(?:current(?:ly)?|now|today)\b|\bas\s+of\s+(?:now|today|the\s+current\s+date|the\s+query\s+date|the\s+reference\s+date)\b",
        text, re.I,
    ))
    if explicit_current_point:
        text = re.sub(
            r"\bas\s+of\s+(?:now|today|the\s+current\s+date|the\s+query\s+date|the\s+reference\s+date)\b",
            " ", text, flags=re.I,
        )
        if re.search(
            r"\b(?:did|were|was|had|will|would|should|could|might|may|can|shall|planned|planning|expected|future|next|tomorrow|historical|history|ever|previous|last|elected|election|during|throughout|before|after|since|until|between|on|senators?|seanad|panels?)\b|[0-9]",
            text, re.I,
        ):
            return False
        return True
    return present_constituency_default(question, constituency)


def default_evidence(question: str, as_of: date) -> dict:
    return {"policy": POLICY, "question": question, "date": as_of.isoformat()}


def validate_default(plan: dict, *, constituency: str, current: bool) -> None:
    evidence = plan.get("interpretation")
    if evidence is None:
        return
    checker = present_constituency_default
    if (plan.get("family") == "member_relationship_composition"
            and not any(
                isinstance(ref, dict) and ref.get("type") == "PartyMembershipEpisode"
                for ref in plan.get("referents", {}).values()
            )):
        checker = member_relationship_as_of_default
    if (not current or not isinstance(evidence, dict)
            or set(evidence) != {"policy", "question", "date"}
            or evidence["policy"] != POLICY or evidence["date"] != plan["asOf"]
            or not isinstance(evidence["question"], str)
            or not constituency or not re.search(re.escape(constituency), evidence["question"], re.I)
            or not checker(evidence["question"], constituency)):
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
