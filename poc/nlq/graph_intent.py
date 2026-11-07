"""Original-question guards for two existing composable graph families.

These local guards preserve question intent independently of any proposed RDF
graph. They neither resolve mentions nor construct/execute plans. They consume
only the exact named slots, a supported selector and structural components of
the original question; any unconsumed text is refused rather than silently
discarded. The caller must still run the existing draft and final graph
validators.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .question_intent import (
    count_operator_matches,
    month_year_mentions,
    numbered_dail_terms,
    requested_measures,
    semantic_residual,
)


_SHARED_TERM_TARGET = re.compile(
    r"\b(?:dail\s+terms?|(?:recorded\s+)?dail\s+(?:service\s+)?"
    r"histor(?:y|ies)|(?:recorded\s+)?dail\s+service\s+records?)\b"
)
_REPRESENTATION_TARGET = re.compile(r"\b(?:and\s+)?constituenc(?:y|ies)\b")
_ROSTER_TARGET = re.compile(r"\b(?:tds?|deputies|representatives?)\b")
_PREVIOUS_DAIL_SCOPE = re.compile(r"\b(?:last|previous)\s+d[áa]il(?:\s+term)?\b", re.IGNORECASE)

_QUESTION_OPENING = re.compile(
    r"^(?:please\s+)?(?:(?:can|could)\s+you\s+)?"
    r"(?:(?:tell|show|give)\s+me|which|what|where|who|name|list|show|find|identify)\b"
)
_QUERY_AUXILIARIES = re.compile(r"^(?:(are|were|is|was)\s+)?(?:the\s+)?")

_CURRENT_SCOPE = re.compile(
    r"\b(?:as\s+of\s+(?:now|today)|right\s+now|in\s+(?:the\s+)?"
    r"(?:current|present)\s+dail|currently|current|now|today)\b"
)
_LATEST_SCOPE = re.compile(
    r"\b(?:(?:in|during|for|of)\s+)?(?:(?:his|her|their|the)\s+)*"
    r"(?:latest\s+recorded|most\s+recent|last(?:\s+recorded)?)\s+"
    r"(?:dail\s+)?term(?:\s+in\s+the\s+dail)?\b"
)
_GENERIC_DAIL_CONTEXT = re.compile(r"\bin\s+the\s+dail\b")
_CAREER_TERM_EVIDENCE = re.compile(
    r"\b(?:in|for)\s+each\s+(?:recorded\s+)?dail\s+terms?\b|"
    r"\b(?:by|per)\s+(?:the\s+)?dail\s+terms?\b|"
    r"\bwith\s+(?:its|the)\s+(?:recorded\s+)?dail\s+terms?\b"
)

_PRESENT_WORDS = {"does", "is", "are", "represents", "representing"}
_RESERVED_COMPONENT_TOKENS = {
    "termsetcomponent", "targetcomponent", "scopecomponent", "relationcomponent",
    "housecontextcomponent", "rostertargetcomponent",
}


def _unsupported(family: str, detail: str) -> ValueError:
    return ValueError(f"Unsupported or unpreserved {family} intent: {detail}")


def _normalize_structure(value: str) -> str:
    """Normalize structural wording after exact named spans are protected."""
    decomposed = unicodedata.normalize("NFKD", value).casefold()
    without_marks = "".join(character for character in decomposed
                            if not unicodedata.combining(character))
    return " ".join(re.sub(r"[^a-z0-9_]+", " ", without_marks).split())


def _validated_mentions(question: Any, mentions: tuple[tuple[str, str], ...], family: str):
    if not isinstance(question, str) or not question.strip():
        raise _unsupported(family, "the original question must be non-empty text")

    cleaned: list[tuple[str, str]] = []
    for role, mention in mentions:
        if not isinstance(mention, str) or not mention.strip():
            raise _unsupported(family, f"{role} must be an exact non-empty mention")
        cleaned.append((role, mention.strip()))

    candidates: list[tuple[int, int, int]] = []
    matches_by_slot: list[list[tuple[int, int]]] = []
    for slot, (_role, mention) in enumerate(cleaned):
        pattern = re.compile(
            r"(?<!\w)" + re.escape(mention) + r"(?!\w)(?:['’]s)?",
            re.IGNORECASE,
        )
        matches = [(match.start(), match.end()) for match in pattern.finditer(question)]
        if not matches:
            raise _unsupported(family, f"the exact {cleaned[slot][0]} mention is absent from the original question")
        matches_by_slot.append(matches)
        candidates.extend((start, end, slot) for start, end in matches)

    # A short slot must not be "grounded" only by a substring inside another
    # slot's name. Such slots need independent, non-overlapping source spans.
    for slot, matches in enumerate(matches_by_slot):
        has_independent_span = any(
            not any(
                other_slot != slot and start < other_end and other_start < end
                for other_slot, other_matches in enumerate(matches_by_slot)
                for other_start, other_end in other_matches
            )
            for start, end in matches
        )
        if not has_independent_span:
            raise _unsupported(family, "named slots must have separate original-question spans")

    # Replace source spans from longest/earliest outward so overlapping aliases
    # cannot expose or rewrite another name. No normalized text is returned.
    selected: list[tuple[int, int, int]] = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]), item[2])):
        start, end, slot = candidate
        if not any(start < other_end and other_start < end
                   for other_start, other_end, _other_slot in selected):
            selected.append(candidate)
    selected_slots = {slot for _start, _end, slot in selected}
    if selected_slots != set(range(len(cleaned))):
        raise _unsupported(family, "each named slot must be preserved as a distinct original span")

    markers = []
    for slot in range(len(cleaned)):
        marker = f"entityslot{slot}marker"
        while marker in question.casefold():
            marker += "x"
        markers.append(marker)

    masked = question
    for start, end, slot in sorted(selected, reverse=True):
        masked = masked[:start] + markers[slot] + masked[end:]
    return _normalize_structure(masked), tuple(markers)


def _strip_question_opening(text: str) -> tuple[str, str | None]:
    """Consume only a leading request frame and one fronted copula/article."""
    text = _QUESTION_OPENING.sub("", text, count=1).strip()
    match = _QUERY_AUXILIARIES.match(text)
    if match is not None:
        auxiliary = match.group(1)
        text = text[match.end():].strip()
        return text, auxiliary
    return text, None


def _replace_exactly_one(text: str, pattern: re.Pattern[str], marker: str,
                         *, family: str, component: str) -> str:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise _unsupported(family, f"one unambiguous {component} is required")
    match = matches[0]
    return text[:match.start()] + marker + text[match.end():]


def _reject_reserved_component_tokens(text: str, family: str) -> None:
    if _RESERVED_COMPONENT_TOKENS & set(re.findall(r"[a-z0-9_]+", text)):
        raise _unsupported(family, "the original question contains reserved structural marker wording")


def _shared_relation_patterns(first: str, second: str) -> tuple[re.Pattern[str], ...]:
    pair = rf"(?:{re.escape(first)}\s+and\s+{re.escape(second)}|{re.escape(second)}\s+and\s+{re.escape(first)})"
    term = r"(?:the\s+)?termsetcomponent"
    prefix = rf"(?:{term}\s+)?"
    suffix = rf"(?:\s+{term})?"
    return (
        re.compile(
            prefix + rf"(?:(?:did|do|does|have|has|had)\s+)?(?:both\s+)?{pair}"
            + rf"\s+(?:both\s+)?(?:serve|served|serving)(?:\s+(?:in|within))?" + suffix
        ),
        re.compile(
            prefix + rf"(?:(?:are|were|is|was)\s+)?common\s+to\s+{pair}" + suffix
        ),
        re.compile(
            prefix + rf"(?:(?:are|were|is|was)\s+)?common\s+to\s+"
            rf"(?:the\s+)?(?:recorded\s+)?(?:d[áa]il\s+)?(?:service\s+)?records?\s+of\s+{pair}"
            + suffix
        ),
        re.compile(
            prefix + rf"(?:(?:are|were|is|was)\s+)?shared\s+by\s+{pair}" + suffix
        ),
        re.compile(
            prefix + rf"(?:both\s+)?{pair}\s+(?:(?:have|has|had)\s+)?in\s+common" + suffix
        ),
        re.compile(
            prefix + rf"(?:both\s+)?{pair}\s+(?:both\s+)?(?:share|shares|shared)" + suffix
        ),
        re.compile(
            prefix + rf"(?:(?:do|does|did|have|has|had)\s+)?(?:both\s+)?{pair}"
            + rf"(?:\s+(?:recorded\s+)?{term})?\s+(?:overlap|overlaps|overlapped)" + suffix
        ),
        re.compile(
            rf"(?:(?:do|does|did|have|has|had)\s+)?(?:both\s+)?{pair}"
            + rf"\s+(?:recorded\s+)?{term}\s+(?:overlap|overlaps|overlapped)"
        ),
    )


def validate_shared_dail_terms_intent(question: str, member_a: str, member_b: str) -> None:
    """Require one unfiltered two-Member Dáil-term intersection question.

    Accepts the established common/shared/both-service and recorded-history
    overlap wording. Counts, other Houses, extra people, temporal filters,
    representation filters and other clauses are unsupported.
    """
    if (isinstance(member_a, str) and isinstance(member_b, str)
            and unicodedata.normalize("NFC", member_a.strip()).casefold()
            == unicodedata.normalize("NFC", member_b.strip()).casefold()):
        raise _unsupported("shared_dail_terms", "the two Member slots must name distinct people")

    text, markers = _validated_mentions(
        question,
        (("member_a", member_a), ("member_b", member_b)),
        "shared_dail_terms",
    )
    _reject_reserved_component_tokens(text, "shared_dail_terms")
    if re.search(r"\b(?:how\s+many|count|number\s+of|total\s+of)\b", text):
        raise _unsupported("shared_dail_terms", "this family returns a term set, not a count")

    text, _opening_auxiliary = _strip_question_opening(text)
    text = re.sub(r"^(?:(?:are|were|is|was)\s+)?(?:the\s+)?", "", text, count=1).strip()
    text = _replace_exactly_one(
        text, _SHARED_TERM_TARGET, "termsetcomponent",
        family="shared_dail_terms", component="Dáil-term answer target",
    )
    if not any(pattern.fullmatch(text) for pattern in _shared_relation_patterns(*markers)):
        raise _unsupported(
            "shared_dail_terms",
            "the original question must ask only for the common recorded Dáil terms of these two named Members",
        )


def _consume_scope(text: str, pattern: re.Pattern[str], marker: str, family: str,
                   component: str) -> tuple[str, int]:
    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        raise _unsupported(family, f"multiple {component} selectors are not supported")
    if not matches:
        return text, 0
    match = matches[0]
    return text[:match.start()] + marker + text[match.end():], 1


def _member_representation_patterns(entity: str) -> tuple[re.Pattern[str], ...]:
    entity = re.escape(entity)
    target = r"targetcomponent"
    scope = r"scopecomponent"
    return (
        re.compile(
            rf"(?:(?:did|does|has|have|had|is|are|was|were)\s+)?{entity}\s+"
            r"(?:representing|represented|represents|represent|serving|served|serves|serve)\b"
        ),
        re.compile(
            rf"(?:(?:is|are|was|were)\s+)?(?:represented|served)\s+by\s+{entity}"
        ),
        re.compile(rf"{entity}\s+(?:(?:historical|recorded|{scope})\s+)?{target}"),
        re.compile(rf"{target}\s+(?:of|for)\s+{entity}"),
        re.compile(rf"{target}\s+(?:is\s+)?(?:recorded\s+)?for\s+{entity}"),
    )


def _consume_member_relation(
    text: str, entity: str, *, family: str,
) -> tuple[str, bool, str | None]:
    patterns = _member_representation_patterns(entity)
    for pattern in patterns[:2]:
        matches = list(pattern.finditer(text))
        if len(matches) > 1:
            raise _unsupported(family, "one Member-to-constituency relation is required")
        if matches:
            match = matches[0]
            phrase = match.group(0)
            verb_match = re.search(
                r"\b(did|does|has|have|had|is|are|was|were|represent|represents|represented|"
                r"representing|serve|serves|served|serving)\b", phrase,
            )
            verb = verb_match.group(1) if verb_match else None
            return text[:match.start()] + "relationcomponent" + text[match.end():], True, verb

    # Possessive/member-noun forms (e.g. “List X's historical constituencies”)
    # and the latest-term-and-constituency form still have an explicit typed
    # Member/target relationship; consume only those structural subcomponents.
    noun_matches = list(patterns[2].finditer(text))
    target_of_matches = list(patterns[3].finditer(text))
    target_for_matches = list(patterns[4].finditer(text))
    all_matches = noun_matches + target_of_matches + target_for_matches
    # The final two patterns overlap on “target for entity”; de-duplicate by
    # source span before requiring one association.
    unique = {(match.start(), match.end()): match for match in all_matches}
    if len(unique) != 1:
        raise _unsupported(family, "one explicit Member-to-constituency relationship is required")
    match = next(iter(unique.values()))
    return text[:match.start()] + "relationcomponent" + text[match.end():], False, None


def _constituency_roster_patterns(entity: str) -> tuple[re.Pattern[str], ...]:
    entity = re.escape(entity)
    target = r"rostertargetcomponent"
    scope = r"scopecomponent"
    return (
        re.compile(rf"{target}\s+(?:for|of)\s+{entity}"),
        re.compile(rf"{target}\s+(?:represents|represent)\b\s+{entity}"),
        re.compile(rf"(?:represents|represent)\b\s+{entity}"),
        re.compile(rf"{entity}\s+(?:{scope}\s+)?{target}"),
        re.compile(rf"{scope}\s+{target}\s+(?:for|of)\s+{entity}"),
        re.compile(rf"{scope}\s+{target}\s+(?:represents|represent)\b\s+{entity}"),
    )


def validate_constituency_representation_intent(
    question: str,
    *,
    member: str | None = None,
    constituency: str | None = None,
    selector: str | None,
) -> None:
    """Require one exact supported representation intent and no extra clause.

    ``member`` supports currentTerm, latestRecorded and career-wide/null
    projections. ``constituency`` supports only the existing current roster
    projection (currentTerm). The original mention spans are masked before
    structural normalization and are never returned or used for resolution.
    """
    if bool(member) == bool(constituency):
        raise _unsupported("constituency_representation", "name exactly one Member or constituency")
    if member is not None:
        mentions = (("member", member),)
        family_direction = "member"
        if selector not in ("currentTerm", "latestRecorded", None):
            raise _unsupported("constituency_representation", "unsupported named-Member term selector")
    else:
        mentions = (("constituency", constituency),)
        family_direction = "constituency"
        if selector != "currentTerm":
            raise _unsupported("constituency_representation", "a named constituency supports only the current roster")

    text, markers = _validated_mentions(
        question, mentions, "constituency_representation",
    )
    _reject_reserved_component_tokens(text, "constituency_representation")
    text, opening_auxiliary = _strip_question_opening(text)

    latest_text, latest_count = _consume_scope(
        text, _LATEST_SCOPE, "scopecomponent", "constituency_representation", "latest-term",
    )
    current_text, current_count = _consume_scope(
        latest_text, _CURRENT_SCOPE, "scopecomponent", "constituency_representation", "current-term",
    )
    if latest_count and current_count:
        raise _unsupported("constituency_representation", "current and latest-recorded scopes cannot be combined")

    if selector == "latestRecorded":
        if family_direction != "member" or latest_count != 1 or current_count:
            raise _unsupported("constituency_representation", "latestRecorded requires an explicit latest Dáil-term request for a named Member")
    elif selector == "currentTerm":
        if latest_count:
            raise _unsupported("constituency_representation", "a current-term selection cannot replace latest-recorded scope")
    elif selector is None and (latest_count or current_count):
        raise _unsupported("constituency_representation", "career-wide representation cannot replace a current or latest-term request")

    if family_direction == "member":
        target_count = len(list(_REPRESENTATION_TARGET.finditer(current_text)))
        if target_count != 1:
            raise _unsupported("constituency_representation", "one constituency answer target is required")
        current_text = _replace_exactly_one(
            current_text, _REPRESENTATION_TARGET, "targetcomponent",
            family="constituency_representation", component="constituency answer target",
        )
        if selector is None and _GENERIC_DAIL_CONTEXT.search(current_text):
            current_text = _GENERIC_DAIL_CONTEXT.sub("housecontextcomponent", current_text, count=1)
        if selector is None:
            current_text, _term_evidence_count = _consume_scope(
                current_text, _CAREER_TERM_EVIDENCE, "housecontextcomponent",
                "constituency_representation", "term-by-term historical evidence",
            )
        # An explicitly numbered term or calendar date is not a career-wide,
        # current-term or latest-recorded selector in this representation path.
        if re.search(r"\b[0-9]+(?:st|nd|rd|th)?\b", current_text):
            raise _unsupported("constituency_representation", "explicit date/ordinal scopes are not represented by this family")

        noun_target_pattern = re.compile(
            rf"{re.escape(markers[0])}\s+(?:(?:historical|recorded|scopecomponent)\s+)?targetcomponent"
        )
        noun_target_matches = list(noun_target_pattern.finditer(current_text))
        target_of_pattern = re.compile(
            rf"targetcomponent\s+(?:of|for)\s+{re.escape(markers[0])}"
        )
        target_of_matches = list(target_of_pattern.finditer(current_text))
        # A combined latest-term-and-constituency ask is a supported evidence
        # request: it states the selected House term and projects its constituency.
        latest_term_projection = re.compile(
            rf"scopecomponent\s+and\s+targetcomponent\s+(?:for|of)\s+{re.escape(markers[0])}"
        )
        combined_matches = list(latest_term_projection.finditer(current_text))
        if noun_target_matches or target_of_matches or combined_matches:
            associations = noun_target_matches + target_of_matches + combined_matches
            spans = {(match.start(), match.end()): match for match in associations}
            if len(spans) != 1:
                raise _unsupported("constituency_representation", "one Member-to-constituency evidence path is required")
            match = next(iter(spans.values()))
            current_text = current_text[:match.start()] + "relationcomponent" + current_text[match.end():]
            action_verb = None
        else:
            current_text, has_action, action_verb = _consume_member_relation(
                current_text, markers[0], family="constituency_representation",
            )
            if not has_action:
                raise _unsupported("constituency_representation", "the named Member must be linked to the requested constituency")

        if selector == "currentTerm":
            inferred_current = action_verb in _PRESENT_WORDS
            # Fronted “Who are the current TDs ...” and named-roster questions
            # carry their present-point force in the question frame.
            inferred_current = inferred_current or opening_auxiliary in {"is", "are"}
            if not (current_count or inferred_current):
                raise _unsupported("constituency_representation", "currentTerm requires current-point wording or an approved present-tense request")
        elif selector is None and (opening_auxiliary in {"is", "are"} or action_verb in _PRESENT_WORDS):
            raise _unsupported("constituency_representation", "a present/current request cannot be converted to career-wide history")

        if not _only_components(current_text, {"targetcomponent", "scopecomponent", "relationcomponent", "housecontextcomponent"}):
            raise _unsupported("constituency_representation", "an additional projection, filter, or clause remains")
        return

    # Named-constituency form: the approved legacy family is a present/current
    # TD roster, not a historical roster or a term/date-filtered selection.
    if latest_count or selector != "currentTerm":
        raise _unsupported("constituency_representation", "a named-constituency request must preserve the current-roster scope")
    roster_text = _replace_exactly_one(
        current_text, _ROSTER_TARGET, "rostertargetcomponent",
        family="constituency_representation", component="TD/deputy roster target",
    )
    patterns = _constituency_roster_patterns(markers[0])
    matched_relation = None
    matched_pattern_index = None
    for pattern_index, pattern in enumerate(patterns):
        matches = list(pattern.finditer(roster_text))
        if len(matches) > 1:
            raise _unsupported("constituency_representation", "one constituency-to-current-roster relationship is required")
        if matches:
            match = matches[0]
            matched_relation = (match.start(), match.end())
            matched_pattern_index = pattern_index
            break
    if matched_relation is None:
        raise _unsupported("constituency_representation", "the named constituency must select its current TD/deputy roster")
    start, end = matched_relation
    roster_text = roster_text[:start] + "relationcomponent" + roster_text[end:]
    inferred_current = opening_auxiliary in {"is", "are"} or matched_pattern_index in {1, 2}
    if not (current_count or inferred_current):
        raise _unsupported("constituency_representation", "the roster request must be explicitly current or present-tense")
    if not _only_components(roster_text, {"rostertargetcomponent", "scopecomponent", "relationcomponent"}):
        raise _unsupported("constituency_representation", "an additional projection, filter, or clause remains")


def validate_anchored_shared_constituency_intent(
    question: str,
    *,
    anchor: str,
    selector: dict[str, Any],
    count: bool,
) -> None:
    """Validate one term-wide other-Member constituency intersection.

    The anchor, constituency target, requested Member measure, and one Dáil
    scope are consumed independently. Unrecognized words, polarity, dates,
    second scopes, and added projections remain visible and are refused.
    """
    family = "anchored_shared_constituency"
    if not isinstance(question, str) or not question.strip():
        raise _unsupported(family, "the original question must be non-empty text")
    if not isinstance(anchor, str) or not anchor.strip():
        raise _unsupported(family, "one exact named anchor is required")
    if type(count) is not bool:
        raise _unsupported(family, "the requested list/count mode must be explicit")

    terms = numbered_dail_terms(question)
    if (isinstance(selector, dict) and set(selector) == {"kind", "number"}
            and selector.get("kind") == "termNumber"
            and type(selector.get("number")) is int):
        if (len(terms) != 1 or terms[0].number != selector["number"]
                or _PREVIOUS_DAIL_SCOPE.search(question)):
            raise _unsupported(family, "exactly one matching numbered Dáil scope is required")
        if not re.search(r"\bd[áa]il\b", question, re.IGNORECASE):
            raise _unsupported(family, "the numbered selector must explicitly name the Dáil")
    elif selector in (
        {"kind": "previousTerm"},
        {"kind": "previousTerm", "house": "Dail"},
    ):
        if terms or len(list(_PREVIOUS_DAIL_SCOPE.finditer(question))) != 1:
            raise _unsupported(family, "previousTerm requires one explicit globally previous/last Dáil scope")
    else:
        raise _unsupported(family, "use one numbered Dáil or the explicit globally previous Dáil")

    from .composable_plan import _question_calendar_dates

    dates, invalid_date = _question_calendar_dates(question)
    if dates or invalid_date is not None or month_year_mentions(question):
        raise _unsupported(family, "explicit calendar dates and month scopes are unsupported")

    operators = count_operator_matches(question)
    if len(operators) != int(count):
        raise _unsupported(family, "the requested count/list wording must match the answer projection")
    measures = requested_measures(question)
    who_else_list = bool(re.search(r"\bwho\s+else\b", question, re.IGNORECASE)) and not count
    if (("members" not in measures.requested and not who_else_list)
            or "members" in measures.excluded or "seats" in measures.requested
            or measures.conflicts or measures.unclassified):
        raise _unsupported(family, "the answer must request other Member identities, not seats or another measure")

    if not _REPRESENTATION_TARGET.search(question):
        raise _unsupported(family, "one constituency target is required")
    if not re.search(r"\b(?:same|shared|share|shares|sharing)\b", question, re.IGNORECASE):
        raise _unsupported(family, "the question must ask for a same/shared constituency")
    if not (re.search(r"\b(?:other|another|others|fellow)\b", question, re.IGNORECASE)
            or re.search(r"\bwho\s+else\b", question, re.IGNORECASE)):
        raise _unsupported(family, "the requested answer must exclude the named anchor")

    consumed = (
        r"\b(?:please|could|can|you|tell|show|give|list|find|identify|name|report)\b",
        r"\b(?:other|another|others|fellow)\b|\bwho\s+else\b",
        r"\b(?:tds?|deput(?:y|ies)|members?|people|persons?|representatives?)\b",
        r"\b(?:same|shared|share|shares|sharing)\b",
        r"\bconstituenc(?:y|ies)\b",
        r"\b(?:recorded|service|both)\b",
        r"\b(?:who|were|was|are|is|did|do|does|have|has|had)\b",
        r"\b(?:count|number\s+of|how\s+many|total(?:\s+of)?)\b",
        _PREVIOUS_DAIL_SCOPE.pattern,
    )
    if semantic_residual(
        question, consumed_patterns=consumed, mentions=(anchor,), consume_dail_terms=True,
    ):
        raise _unsupported(family, "an additional filter, projection, condition, or ungrounded mention remains")


def _only_components(text: str, allowed: set[str]) -> bool:
    """Require that component consumption leaves no natural-language residue."""
    tokens = re.findall(r"[a-z0-9_]+", text)
    return bool(tokens) and all(token in allowed for token in tokens)
