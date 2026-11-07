"""Fail-closed guards for the existing House-membership projections.

These helpers inspect only the original question. They do not resolve entities,
rewrite mentions, authorize a plan, or imply that absent RDF is negative
evidence. Call them from the matching legacy draft validators before accepting
the closed graph shape.
"""

import re

from .question_intent import (
    count_operator_matches,
    semantic_residual,
    without_optional_overlap_clause,
)


_EXPLICIT_NEGATION = re.compile(
    r"\b(?:not|never|no|neither|nor|without|except|excluding|exclude|"
    r"lack|lacks|lacked|lacking)\b",
    re.IGNORECASE,
)
_CURRENT_SEANAD_SUBJECT = re.compile(
    r"\b(?:"
    r"(?:current|present)\s+(?:seanad\s+)?senators?"
    r"|currently\s+(?:serving\s+)?senators?"
    r"|(?:senators?|members?)\s+(?:in|of)\s+(?:the\s+)?(?:current|present)\s+seanad"
    r"|(?:current|present)\s+seanad\s+(?:senators?|members?)"
    r")\b",
    re.IGNORECASE,
)
_CURRENT_SEANAD_SCOPE = re.compile(
    r"\b(?:the\s+)?(?:current|present)\s+seanad\b",
    re.IGNORECASE,
)
_CURRENT_SEANAD_SERVICE_POINT = re.compile(
    r"\b(?:senators?|members?)\b.{0,48}\b(?:who\s+)?serv(?:e|es|ing)\b"
    r"(?:.{0,24}\b(?:currently|now|today)\b)|"
    r"\b(?:currently|now|today)\b.{0,24}\b(?:serving\s+)?senators?\b",
    re.IGNORECASE,
)
_DAIL_SERVICE_PATH = re.compile(
    r"\b(?:d[áa]il\s+(?:service|membership)|"
    r"serv(?:e|ed|ing)\s+(?:in|as)\s+(?:the\s+)?d[áa]il)\b",
    re.IGNORECASE,
)
_ORDERED_MEMBERSHIP_PATH = re.compile(
    r"\bd[áa]il\s+membership\s+(?:that\s+)?ended\s+before\s+"
    r"(?:their|the)\s+(?:current\s+)?seanad\s+membership\s+(?:began|started)\b",
    re.IGNORECASE,
)
_PRIOR_SERVICE_WORDING = re.compile(
    r"\b(?:previously|previous|prior|earlier|former|formerly|past)\b|\bused\s+to\b",
    re.IGNORECASE,
)
_CURRENT_DAIL_SELECTOR = re.compile(
    r"\b(?:current|this|present)\s+d[áa]il\b",
    re.IGNORECASE,
)
_COUNT_CONSUMPTION = (
    r"\b(?:how\s+many|count(?:\s+of)?|number\s+of|"
    r"total\s+(?:(?:number|count)\s+of|of))\b",
)


def _question_reason(question: str) -> str | None:
    if not isinstance(question, str) or not question.strip():
        return "The original question must be nonempty text."
    return None


def _count_mode_reason(question: str, count: bool) -> str | None:
    if not isinstance(count, bool):
        return "Count/list mode must be an explicit boolean."
    operators = count_operator_matches(question)
    if len(operators) > 1:
        return "The question must contain exactly one unambiguous count/list operator."
    asks_for_count = bool(operators)
    if asks_for_count != count:
        return "The question's count/list wording does not match the proposed answer mode."
    return None


def _has_explicit_negation(question: str) -> bool:
    return bool(_EXPLICIT_NEGATION.search(question))


def _has_residual(question: str, *, consumed_patterns=(), mentions=()) -> bool:
    return bool(semantic_residual(
        question,
        consumed_patterns=consumed_patterns,
        mentions=mentions,
    ))


def unsupported_current_seanad_prior_dail_intent(
    question: str,
    *,
    count: bool,
) -> str | None:
    """Guard the positive current-Seanad plus recorded-prior-Dáil projection.

    The supported semantic components include the existing ``previously
    served``, ``recorded earlier membership``, and explicitly ordered
    membership-interval phrasings. Unknown filters and projections remain in
    the residual and are rejected.
    """
    reason = _question_reason(question)
    if reason:
        return reason
    reason = _count_mode_reason(question, count)
    if reason:
        return reason
    if _has_explicit_negation(question):
        return "Negative or absence-based service requests are unsupported."
    if _CURRENT_DAIL_SELECTOR.search(question):
        return "The prior-service projection does not select a current or numbered Dáil term."

    current_subject = _CURRENT_SEANAD_SUBJECT.search(question)
    dail_path = _DAIL_SERVICE_PATH.search(question)
    ordered_path = bool(_ORDERED_MEMBERSHIP_PATH.search(question))
    prior_markers = tuple(_PRIOR_SERVICE_WORDING.finditer(question))
    prior_wording = bool(
        current_subject
        and dail_path
        and prior_markers
        and all(
            current_subject.end() <= marker.start() and marker.end() <= dail_path.start()
            for marker in prior_markers
        )
    )
    if not current_subject:
        return "The question must positively identify current Seanad members."
    if not dail_path or not (prior_wording or ordered_path):
        return "The question must request a recorded prior Dáil membership or service path."

    consumed = (
        _CURRENT_SEANAD_SUBJECT.pattern,
        _CURRENT_SEANAD_SCOPE.pattern,
        _ORDERED_MEMBERSHIP_PATH.pattern,
        _DAIL_SERVICE_PATH.pattern,
        _PRIOR_SERVICE_WORDING.pattern,
        r"\brecorded\b",
    )
    if count:
        consumed += _COUNT_CONSUMPTION
    if _has_residual(question, consumed_patterns=consumed):
        return "Additional filters, dates, terms, people, or requested outputs are unsupported."
    return None


def unsupported_current_seanad_party_membership_intent(
    question: str,
    *,
    party_mention: str,
    count: bool,
) -> str | None:
    """Guard the positive named-party membership projection in the current Seanad.

    ``party_mention`` must be the exact party span supplied from the original
    question. This helper masks only that exact span for residual checking; it
    does not canonicalize or replace the entity mention.
    """
    reason = _question_reason(question)
    if reason:
        return reason
    reason = _count_mode_reason(question, count)
    if reason:
        return reason
    if not isinstance(party_mention, str) or not party_mention.strip():
        return "The exact original party mention is required."
    party_pattern = re.compile(
        r"(?<!\w)" + re.escape(party_mention) + r"(?!\w)",
        re.IGNORECASE,
    )
    if not party_pattern.search(question):
        return "The named party must occur as an exact mention in the original question."
    if _has_explicit_negation(question):
        return "Negative or absence-based party-membership requests are unsupported."

    has_member_role = bool(re.search(r"\b(?:senators?|members?)\b", question, re.IGNORECASE))
    has_current_seanad = bool(
        _CURRENT_SEANAD_SCOPE.search(question)
        or _CURRENT_SEANAD_SUBJECT.search(question)
        or _CURRENT_SEANAD_SERVICE_POINT.search(question)
    )
    if not has_member_role or not has_current_seanad:
        return "The question must request named-party membership in the current Seanad."

    consumed = (
        _CURRENT_SEANAD_SCOPE.pattern,
        _CURRENT_SEANAD_SUBJECT.pattern,
        _CURRENT_SEANAD_SERVICE_POINT.pattern,
        r"\b(?:current|present)\s+senators?\b",
        r"\b(?:senators?|members?)\b",
        r"\b(?:in|of|who|are|is|was|were|show|list|give|identify|name|the)\b",
    )
    if count:
        consumed += _COUNT_CONSUMPTION
    if _has_residual(question, consumed_patterns=consumed, mentions=(party_mention,)):
        return "Additional filters, dates, terms, people, or requested outputs are unsupported."
    return None


def unsupported_current_cross_house_membership_intent(
    question: str,
    *,
    count: bool,
) -> str | None:
    """Guard the term-wide recorded-member intersection in both current Houses.

    Optional disclaimers that say the membership periods need not overlap are
    removed by the existing narrow helper. Affirmative simultaneity, true
    non-overlap conditions, and any other unconsumed intent remain unsupported.
    This existing projection is list-only.
    """
    reason = _question_reason(question)
    if reason:
        return reason
    reason = _count_mode_reason(question, count)
    if reason:
        return reason
    if count:
        return "The current cross-house intersection supports a Member list, not a count."

    residual_question = without_optional_overlap_clause(question)
    if _has_explicit_negation(residual_question):
        return "Negative membership or non-overlap conditions are unsupported."
    seanad_term_count = len(re.findall(
        r"\b(?:current|this)\s+seanad\b", residual_question, re.IGNORECASE,
    ))
    dail_term_count = len(re.findall(
        r"\b(?:current|this)\s+d[áa]il\b", residual_question, re.IGNORECASE,
    ))
    seanad_role = re.search(
        r"\b(?:senators?|seanad\s+members?)\b.{0,48}\b(?:in|of)\s+"
        r"(?:the\s+)?(?:current|this)\s+seanad\b",
        residual_question,
        re.IGNORECASE,
    )
    dail_role = re.search(
        r"\b(?:deput(?:y|ies)|tds?|d[áa]il\s+members?)\b.{0,48}\b(?:in|of)\s+"
        r"(?:the\s+)?(?:current|this)\s+d[áa]il\b",
        residual_question,
        re.IGNORECASE,
    )
    generic_member_intersection = bool(
        re.search(r"\bmembers?\b", residual_question, re.IGNORECASE)
        and re.search(r"\b(?:recorded\s+)?(?:service|membership|served|serve|serving)\b", residual_question, re.IGNORECASE)
        and re.search(r"\bboth\b", residual_question, re.IGNORECASE)
    )
    if (seanad_term_count != 1 or dail_term_count != 1
            or not (seanad_role and dail_role or generic_member_intersection)):
        return "The question must request recorded membership in both explicitly current House terms."

    consumed = (
        r"\b(?:current|this)\s+seanad\b",
        r"\b(?:current|this)\s+d[áa]il\b",
        r"\b(?:senators?|members?|seanad\s+members?|deput(?:y|ies)|tds?|d[áa]il\s+members?)\b",
        r"\band\b",
        r"\bboth\b",
        r"\b(?:recorded|service|membership|served|serve|serving|periods?)\b",
        r"\b(?:who|what|which|were|was|are|is|have|has|had|show|list|give|identify|name|the)\b",
    )
    if _has_residual(residual_question, consumed_patterns=consumed):
        return "Simultaneity, historical periods, and additional filters or outputs are unsupported."
    return None
