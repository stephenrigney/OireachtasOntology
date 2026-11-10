"""Narrow, shared intent defaults; no entity or relation recognition."""

import re
from datetime import date


POLICY = "present_constituency_as_of"
SEANAD_PARTY_POLICY = "present_seanad_party_as_of"
RELATIONSHIP_POLICY = "present_relationship_as_of"


def current_relationship_scope(question: str, *mentions: str) -> str | None:
    """Classify time only AFTER a handler has accounted for the whole intent.

    This is not relationship recognition or completeness validation. A caller
    must retain its closed capability guards and independently dated execution.
    None means no current default may be inferred (including conflicting scope).
    """
    text = question
    for mention in sorted((m for m in mentions if isinstance(m, str) and m), key=len, reverse=True):
        text = re.sub(re.escape(mention), " ", text, flags=re.I)
    text = re.sub(r"\bas\s+of\s+(?:now|today|the\s+(?:current|query|reference)\s+date)\b", " currently ", text, flags=re.I)
    if re.search(
        r"[0-9]|\b(?:was|were|did|had|served|held|represented|belonged|joined|career|lifetime|past|formerly|former|historical|history|ever|"
        r"previous|previously|last|latest|recently|before|after|since|until|between|during|throughout|"
        r"as\s+of|will|would|should|could|might|may|shall|future|next|tomorrow|"
        r"not|never|no|except|excluding|without|unless|if)\b", text, re.I,
    ):
        return None
    if re.search(r"\b(?:current|currently|now|today|present|this)\b", text, re.I):
        return "explicit"
    if re.search(r"\b(?:is|are|does|do|represent|represents|representing|serve|serving|list|show|name)\b", text, re.I):
        return "inferred"
    return None


def present_party_default(question: str, party: str, house: str) -> bool:
    """One scoped party default for either House; no new relationship shape."""
    if not isinstance(party, str) or not party or current_relationship_scope(question, party) != "inferred":
        return False
    text = re.sub(re.escape(party), "party", question, flags=re.I)
    members = r"senators" if house == "Seanad" else r"(?:TDs|deputies)" if house == "Dail" else r"(?!)"
    return bool(re.fullmatch(
        rf"\s*(?:who\s+are\s+(?:the\s+)?party\s+{members}|"
        rf"(?:which|what)\s+party\s+{members}\s+are\s+there|"
        rf"how\s+many\s+party\s+{members}\s+are\s+there)\s*[?.!]?\s*", text, re.I,
    ))


def prior_service_present_default(question: str) -> bool:
    """Scope current to Senators, never to the separate prior-Dáil path.

    The historical clause is already executable in Q20, but may not be removed
    generally: fully consume this bounded clause before classifying its head.
    The original question still goes through every Q20 compatibility guard.
    """
    match = re.fullmatch(
        r"\s*(?P<head>(?:who\s+are\s+(?:the\s+)?|(?:which|what|how\s+many)\s+)senators)\s+"
        r"(?:(?:who\s+)?(?:have\s+)?previously\s+served\s+(?:in\s+(?:the\s+)?d[áa]il|as\s+(?:TDs|deputies))|"
        r"who\s+were\s+previously\s+(?:TDs|deputies))\s*[?.!]?\s*",
        question, re.I,
    )
    return bool(match and current_relationship_scope(match['head'] + ' are there') == 'inferred')


def present_seanad_party_default(question: str, party: str) -> bool:
    """Default only a grounded, unqualified present-tense Senator-party request."""
    return present_party_default(question, party, "Seanad")


def validate_seanad_party_scope(question: str, party: str, selector: dict) -> None:
    validate_party_scope(question, party, selector, "Seanad")


def validate_party_scope(question: str, party: str, selector: dict, house: str) -> None:
    """Account for the whole bounded party/House request, not just its term."""
    text = re.sub(re.escape(party), " ", question, flags=re.I) if party else question
    house_word = "seanad" if house == "Seanad" else r"d[áa]il"
    numbered = re.findall(rf"\b([0-9]{{1,3}})(?:st|nd|rd|th)\s+{house_word}\b", text, re.I)
    explicit_words = bool(re.search(r"\b(?:current|this|currently|now|today|present)\b", text, re.I))
    current = current_relationship_scope(question, party) == "explicit"
    if selector.get("kind") == "termNumber":
        if numbered != [str(selector.get("number"))] or explicit_words:
            raise ValueError(f"Preserve exactly one explicitly numbered {house}, without a conflicting current scope.")
    elif selector.get("kind") == "currentTerm":
        if numbered or not (current or present_party_default(question, party, house)):
            raise ValueError(f"Current {house} party selection requires a current request or the scoped present-time default.")
    else:
        raise ValueError(f"{house} party selection supports only currentTerm or one numbered term.")
    text = re.sub(rf"\b[0-9]{{1,3}}(?:st|nd|rd|th)\s+{house_word}\b", f" {house.casefold()} ", text, flags=re.I)
    # A closed vocabulary here is deliberately limited to this existing graph.
    # Any residual date, relationship, negation or other condition fails closed.
    allowed = set("who which what how many count number of total list name show give me please are were was is the a an senator senators seanad in during for current this currently now today present serving served members party there recorded local evidence".split())
    if house == "Dail":
        allowed -= {"senator", "senators", "seanad"}
        allowed |= {"td", "tds", "deputy", "deputies", "dail", "dáil"}
    words = set(re.findall(r"[^\W\d_]+", text.casefold()))
    if re.search(r"\d", text) or words - allowed:
        raise ValueError(f"{house} party selection cannot drop an additional temporal, party or relationship condition.")
    if selector.get("kind") == "currentTerm" and re.search(r"\b(?:during|served)\b", text, re.I):
        raise ValueError("Current Seanad party selection cannot replace historical service scope.")


def validate_seanad_party_default(plan: dict) -> None:
    validate_party_default(plan, "Seanad")


def validate_party_default(plan: dict, house: str) -> None:
    evidence = plan.get("interpretation")
    if evidence is None:
        return
    refs = plan["referents"]
    if (not isinstance(evidence, dict) or set(evidence) != {"policy", "question", "date"}
            or evidence.get("policy") not in ({RELATIONSHIP_POLICY, SEANAD_PARTY_POLICY} if house == "Seanad" else {RELATIONSHIP_POLICY})
            or evidence.get("date") != plan["asOf"]
            or not isinstance(evidence.get("question"), str)
            or refs["term"].get("selector") != {"kind": "currentTerm", "house": house}
            or not present_party_default(evidence["question"], refs["affiliation"].get("mention", ""), house)):
        raise ValueError(f"Current {house} party default lacks approved scoped interpretation evidence.")


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
    ordinary_composition = (
        re.search(r"\b(?:constituenc(?:y|ies)|TDs?|represent(?:ed|s|ing)?)\b", question, re.I)
        and re.search(r"\b(?:and|or|while|same|shared)\b", question, re.I)
    )
    cross_house = (
        re.search(r"\b(?:seanad|senators?)\b", question, re.I)
        and re.search(r"\b(?:d[áa]il|deput(?:y|ies)|tds?)\b", question, re.I)
    )
    current_seanad_party = (
        re.search(r"\b(?:seanad|senators?)\b", question, re.I)
        and re.search(r"\b(?:current|currently|this|now|today)\b", question, re.I)
        and re.search(r"\b(?:who|which|what|how\s+many|count|number\s+of)\b", question, re.I)
    )
    return bool(ordinary_composition or cross_house or current_seanad_party)


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
    mention = current_office_point_mention(question)
    return mention is not None and current_relationship_scope(question) is not None


def current_scope_explanation(question: str, plan: dict, as_of: date) -> str | None:
    """Explain only established, validated current-point shapes; never select one."""
    family = plan.get("family")
    refs = plan.get("referents", {})
    selector = refs.get("term", {}).get("selector")
    current_term = isinstance(selector, dict) and selector.get("kind") == "currentTerm"
    constraints = plan.get("constraints", [])
    eligible = family in {"current_committee_members", "current_office_constituency", "government_party_members", "current_collection"}
    eligible |= family == "constituency_representation" and current_term
    eligible |= family == "member_relationship_composition" and current_term and (
        "episode" in refs or any(c.get("field") == "membershipInterval" and c.get("value") == as_of.isoformat() for c in constraints)
    )
    eligible |= "family" not in plan and refs.get("holding", {}).get("type") == "OfficeHolding" and any(
        isinstance(c.get("value"), dict) and c["value"].get("scope") == "calendarDate"
        and c["value"].get("start") == c["value"].get("end") == as_of.isoformat() for c in constraints
    )
    prior_service = (family == 'member_relationship_composition'
                     and refs.get('seanad_term', {}).get('selector') == {'kind': 'currentTerm', 'house': 'Seanad'}
                     and refs.get('dail_term') == {'type': 'DailTerm'})
    if prior_service and prior_service_present_default(question):
        return (f"Present-time default applied: Senator membership is current at configured asOf {as_of.isoformat()}; "
                "the separate Dáil service remains strictly prior to that Seanad membership, not current.")
    if prior_service:
        return (f"Explicit current-time request for Seanad membership at configured asOf {as_of.isoformat()}; "
                "the separate Dáil service remains strictly prior, not current.")
    if not eligible:
        return None
    scope = current_relationship_scope(question, *(ref.get("mention", "") for ref in refs.values()))
    if scope == "inferred":
        return f"Present-time default applied: no time was specified; interpreted as current at configured asOf {as_of.isoformat()}."
    if scope == "explicit":
        return f"Explicit current-time request: evaluated at configured asOf {as_of.isoformat()}; no present-time default was inferred."
    return None


def present_constituency_default(question: str, constituency: str) -> bool:
    """Only unqualified present-tense constituency representation is defaulted.

    Callers must already have validated the supported representation graph and
    grounded its constituency mention. Explicit scope always wins.
    """
    text = re.sub(re.escape(constituency), " ", question, flags=re.I) if constituency else question
    if current_relationship_scope(question, constituency) is None:
        return False
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


def office_holding_boundary(parameters, *, fuseki, supported_predicates, as_of: date | None = None):
    """Return bounded accepted office episodes for one exact Member and office.

    These local episodes are not treated as a complete career timeline. Raw
    ministerial observations and parliamentary-membership dates are deliberately
    not consulted.
    """
    from .composable_plan import (
        AmbiguousMember,
        PlanError,
        PlanOutcome,
        _compile_office_evidence,
        _reviewed_office_mapping,
        member_resolution_query,
        readable_member_office_evidence_result,
        resolve_member,
    )
    from .member_resolution import resolve_local_entity_label
    from .errors import NLQError, IdentityNotFound, QueryLimitError
    latest_recorded = parameters.get("selection") == "latestRecorded"
    request_family = "office_holding_latest_recorded" if latest_recorded else "office_holding_evidence"
    try:
        member_iri, member_label = resolve_member(
            fuseki.query(member_resolution_query(parameters["member"], supported_predicates=supported_predicates)),
            parameters["member"],
        )
        office = resolve_local_entity_label("NamedOffice", parameters["office"], fuseki,
                                            supported_predicates=supported_predicates)
    except AmbiguousMember as error:
        return PlanOutcome("ambiguous", diagnostic=str(error), candidates=error.candidates,
                           request_family=request_family)
    except NLQError as error:
        status = "not_found" if isinstance(error, IdentityNotFound) else "validation_failure" if isinstance(error, QueryLimitError) else "source_data_unavailable"
        return PlanOutcome(status, diagnostic=str(error), request_family=request_family)
    if office.state == "unresolved":
        return PlanOutcome("source_data_unavailable", request_family=request_family,
                           diagnostic=f"No accepted local NamedOffice identity is available for {parameters['office']}; accepted OfficeHolding evidence cannot establish this tenure. Unreviewed ministerial observations are not accepted holdings.")
    if office.state == "ambiguous":
        return PlanOutcome("ambiguous", request_family=request_family,
                           candidates=tuple({"iri": c.iri, "label": c.label} for c in office.candidates),
                           diagnostic="Several accepted office identities match; none was selected.")
    if office.state != "resolved" or len(office.candidates) != 1:
        return PlanOutcome("source_data_unavailable", request_family=request_family,
                           diagnostic="The local office resolver did not return one usable reviewed identity.")

    office_candidate = office.candidates[0]
    evidence_query = None
    try:
        from .pagination import select_pages

        mapping = _reviewed_office_mapping()
        mapping["member_iri"] = member_iri
        mapping["office_iri"] = office_candidate.iri
        evidence_query = _compile_office_evidence(mapping, supported_predicates=supported_predicates)
        evidence = select_pages(
            evidence_query, fuseki=fuseki, supported_predicates=supported_predicates,
        )
        if not evidence.rows:
            return PlanOutcome(
                "source_data_unavailable", sparql=evidence_query,
                request_family=request_family,
                diagnostic=(f"No accepted local OfficeHolding episode for {member_label} as "
                            f"{office_candidate.label} is recorded; tenure cannot be determined from local evidence."),
            )
        result = readable_member_office_evidence_result(
            evidence,
            member_iri=member_iri,
            member_label=member_label,
            office_label=office_candidate.label,
            latest_recorded=latest_recorded,
            office_iri=office_candidate.iri,
            as_of=as_of,
        )
    except PlanError as error:
        return PlanOutcome("unsupported_mapping", request_family=request_family,
                           diagnostic=f"The reviewed office-holding mapping could not be used safely: {error}")
    except NLQError as error:
        return PlanOutcome(
            "source_data_unavailable", sparql=evidence_query,
            request_family=request_family,
            diagnostic=("Accepted local OfficeHolding episodes could not be read completely or their intervals "
                        f"are missing, conflicting, or uncertain ({error}); no partial episode list was returned."),
        )

    return PlanOutcome(
        "success", sparql=evidence_query, result=result,
        request_family=request_family,
        diagnostic=(("LATEST RECORDED EPISODE — not a proven historically last tenure. "
                     "Selected by the unique greatest validated StartDate after reading all accepted local episodes; "
                     "earlier intervals end strictly before it. A missing end date is not proof of a completed tenure. "
                     if latest_recorded else "")
                    + f"INCOMPLETE LOCAL-RECORDED EPISODES for {member_label} as {office_candidate.label}. "
                    "Each row is a separate locally recorded accepted OfficeHolding with its mapped interval. "
                    "This is not a complete career or tenure history; gaps in local records do not mean the "
                    "Member was not in office."),
    )
