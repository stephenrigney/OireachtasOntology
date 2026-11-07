"""Conservative wording equivalences for existing closed query projections.

These helpers do not authorize a plan. Callers still validate the original
entity mentions, every requested constraint and the complete typed graph.
Unknown text is retained, never discarded as a bag of harmless tokens.
"""

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class MeasureScope:
    positive_text: str
    excluded: frozenset[str]


@dataclass(frozen=True)
class NumberedDailTerm:
    number: int
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class MonthYearMention:
    month: int
    year: int
    start: int
    end: int


@dataclass(frozen=True)
class RequestedMeasures:
    requested: frozenset[str]
    excluded: frozenset[str]
    conflicts: frozenset[str]
    unclassified: frozenset[str]
    has_count_operator: bool


_DAIL_PREFIX_NUMBER = re.compile(
    r"(?<!\w)d[áa]il(?:\s+term)?\s+(?:(?:number|no\.?|#)\s*)?(?P<number>[0-9]+)(?![\w])",
    re.IGNORECASE,
)
_DAIL_PREFIX_MALFORMED_NUMBER = re.compile(
    r"(?<!\w)d[áa]il(?:\s+term)?\s+(?:number|no\.?|#)\s*(?P<number>[^\s,;.!?]+)",
    re.IGNORECASE,
)
_DAIL_ORDINAL = re.compile(
    r"(?<!\w)(?P<number>[0-9]+)(?P<suffix>[a-z]+)\s+d[áa]il(?:\s+terms?)?\b",
    re.IGNORECASE,
)
_ORDINAL = re.compile(r"(?<!\w)(?P<number>[0-9]+)(?P<suffix>[a-z]+)(?!\w)", re.IGNORECASE)
_COUNT_OPERATOR = re.compile(
    r"\bhow\s+many\b|\bcount(?:\s+of)?\b|\bnumber\s+of\b|\btotal\s+(?:(?:number|count)\s+of|of)\b",
    re.IGNORECASE,
)
_SEAT_COMPLEMENT = re.compile(
    r"\bseat\s+(?:complement|total|count|allocation)\b|\b(?:number|total|count)\s+of\s+seats?\b",
    re.IGNORECASE,
)
MEMBER_SEAT_ALIAS = re.compile(
    r"\bhow\s+many\s+members?\s+(?:were|are)\s+(?:there\s+)?in\b|"
    r"\bwhat\s+is\s+the\s+(?:total\s+)?number\s+of\s+members?\s+in\b",
    re.IGNORECASE,
)
_REQUESTED_GROUPS = re.compile(
    r"\b(?:part(?:y|ies)\s+(?:and|&)\s+(?:parliamentary\s+)?groups?|"
    r"(?:parliamentary\s+)?groups?\s+(?:and|&)\s+(?:political\s+)?part(?:y|ies)|"
    r"(?:include|including|plus|along\s+with|as\s+well\s+as|also)\s+"
    r"(?:the\s+)?(?:parliamentary\s+)?groups?)\b",
    re.IGNORECASE,
)
_EXCLUDED_MEASURE = {
    "seats": re.compile(
        r"\b(?:i\s+am|i'm|we\s+are|we're)?\s*not\s+(?:asking|requesting|looking)\s+for\s+"
        r"(?:the\s+)?seats?\b|\b(?:rather\s+than|instead\s+of|excluding|exclude|without|not)\s+(?:the\s+)?seats?\b",
        re.IGNORECASE,
    ),
    "groups": re.compile(
        r"\b(?:(?:i\s+am|i'm|we\s+are|we're)\s+)?not\s+(?:asking|requesting|looking)\s+for\s+"
        r"(?:the\s+)?(?:parliamentary\s+)?groups?\b|"
        r"\b(?:rather\s+than|instead\s+of|excluding|exclude|without|not)\s+"
        r"(?:the\s+)?(?:parliamentary\s+)?groups?\b",
        re.IGNORECASE,
    ),
    "parties": re.compile(
        r"\b(?:(?:i\s+am|i'm|we\s+are|we're)\s+)?not\s+(?:asking|requesting|looking)\s+for\s+"
        r"(?:the\s+)?(?:political\s+)?parties\b|"
        r"\b(?:rather\s+than|instead\s+of|excluding|exclude|without|not)\s+"
        r"(?:the\s+)?(?:political\s+)?parties\b",
        re.IGNORECASE,
    ),
    "members": re.compile(
        r"\b(?:rather\s+than|instead\s+of|excluding|exclude|without|not)\s+"
        r"(?:the\s+)?(?:distinct\s+)?(?:members?|people|persons?|tds?|deput(?:y|ies))\b",
        re.IGNORECASE,
    ),
}
_GRAMMAR_WORDS = frozenset({
    "a", "an", "the", "of", "for", "in", "on", "during", "at", "to", "by", "with", "from", "as",
    "what", "which", "who", "how", "many", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "has", "have", "had", "can", "could", "you", "me", "please", "there", "that",
    "i", "am", "we",
})


def _calendar_date_spans(question: str) -> tuple[tuple[int, int], ...]:
    # Share the existing accepted textual/ISO date grammar without making the
    # semantic helper authoritative for date validity.
    from .composable_plan import _ISO_DATE, _TEXT_DATE

    return tuple(sorted(
        {(match.start(), match.end()) for pattern in (_ISO_DATE, _TEXT_DATE)
         for match in pattern.finditer(question)},
    ))


def calendar_date_spans(question: str) -> tuple[tuple[int, int], ...]:
    """Return spans for the same explicit date forms accepted by query planning."""
    return _calendar_date_spans(question)


def month_year_mentions(question: str) -> tuple[MonthYearMention, ...]:
    """Extract named complete-month slots, preserving their source spans."""
    from .composable_plan import _MONTHS

    names = "|".join(re.escape(name) for name in sorted(_MONTHS, key=len, reverse=True))
    pattern = re.compile(
        r"(?<!\w)(?P<month>" + names + r")\s+(?P<year>[0-9]{4})(?![0-9])", re.I,
    )
    return tuple(
        MonthYearMention(_MONTHS[match["month"].casefold()], int(match["year"]), match.start(), match.end())
        for match in pattern.finditer(question)
    )


def numbered_dail_terms(question: str) -> tuple[NumberedDailTerm, ...]:
    """Extract numeric Dáil selectors in the supported cardinal and ordinal forms.

    Ordinal numbers in calendar dates are not term selectors. Older question
    forms that say e.g. “32nd and 33rd terms” remain understood when the
    surrounding question identifies Dáil service/terms.
    """
    spans: dict[tuple[int, int], NumberedDailTerm] = {}

    for match in _DAIL_PREFIX_MALFORMED_NUMBER.finditer(question):
        raw = match["number"]
        if not raw.isdecimal():
            raise ValueError("A numbered Dáil selector must use one numeric term number.")

    for match in _DAIL_PREFIX_NUMBER.finditer(question):
        number = int(match["number"])
        _validate_dail_number(number)
        spans[(match.start(), match.end())] = NumberedDailTerm(
            number, match.start(), match.end(), match.group(0),
        )

    for match in _DAIL_ORDINAL.finditer(question):
        number = int(match["number"])
        _validate_ordinal(number, match["suffix"])
        spans[(match.start(), match.end())] = NumberedDailTerm(
            number, match.start(), match.end(), match.group(0),
        )

    date_spans = _calendar_date_spans(question)
    direct_ordinal_spans = tuple(spans)
    has_dail_context = bool(re.search(r"\bd[áa]il\b", question, re.IGNORECASE))
    has_term_context = bool(re.search(r"\bterms?\b", question, re.IGNORECASE))
    for match in _ORDINAL.finditer(question):
        span = (match.start(), match.end())
        if any(start <= match.start() and match.end() <= end for start, end in spans):
            continue
        if any(start <= match.start() and match.end() <= end for start, end in date_spans):
            continue
        coordinated = False
        for direct_start, _direct_end in direct_ordinal_spans:
            if match.end() >= direct_start or direct_start - match.end() > 80:
                continue
            between = question[match.end():direct_start]
            between = _ORDINAL.sub(" ", between)
            between = re.sub(r"\b(?:the|and|or)\b|[,/&]", " ", between, flags=re.I)
            if not between.strip():
                coordinated = True
                break
        start, end = max(0, match.start() - 64), min(len(question), match.end() + 64)
        context = question[start:end]
        local_dail_context = bool(re.search(r"\bd[áa]il\b", context, re.I))
        if not (coordinated or has_dail_context and has_term_context and local_dail_context
                or local_dail_context and re.search(r"\bterms?\b", context, re.I)):
            continue
        number = int(match["number"])
        _validate_ordinal(number, match["suffix"])
        spans[span] = NumberedDailTerm(number, match.start(), match.end(), match.group(0))

    for match in re.finditer(r"(?<!\w)d[áa]il(?:\s+term)?\s+(?P<number>[0-9]+)[a-z]+\b", question, re.I):
        raise ValueError("A Dáil term ordinal must use the standard suffix before ‘Dáil’.")

    return tuple(sorted(spans.values(), key=lambda item: (item.start, item.end)))


def _validate_dail_number(number: int) -> None:
    if not 1 <= number <= 999:
        raise ValueError("A numbered Dáil selector must be between 1 and 999.")


def _validate_ordinal(number: int, suffix: str) -> None:
    expected = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    if suffix.casefold() != expected:
        raise ValueError("A Dáil term ordinal in the question is malformed.")
    _validate_dail_number(number)


def requested_measures(question: str) -> RequestedMeasures:
    """Extract requested numeric/list measures separately from explicit exclusions."""
    excluded_spans: dict[str, tuple[tuple[int, int], ...]] = {
        measure: tuple((match.start(), match.end()) for match in pattern.finditer(question))
        for measure, pattern in _EXCLUDED_MEASURE.items()
    }

    def positive_word(pattern: re.Pattern[str], measure: str) -> bool:
        exclusions = excluded_spans.get(measure, ())
        return any(not any(start <= match.start() and match.end() <= end for start, end in exclusions)
                   for match in pattern.finditer(question))

    requested: set[str] = set()
    excluded = {measure for measure, spans in excluded_spans.items() if spans}
    if positive_word(re.compile(r"\bpart(?:y|ies)\b", re.I), "parties"):
        requested.add("parties")
    positive_group = bool(_REQUESTED_GROUPS.search(question))
    group_exclusions = excluded_spans.get("groups", ())
    unclassified_groups = bool(re.search(r"\b(?:parliamentary\s+)?groups?\b", question, re.I)) and not positive_group and not group_exclusions
    if positive_group:
        requested.add("groups")
    member_seat_alias = bool(MEMBER_SEAT_ALIAS.search(question)) and not re.search(r"\bseats?\b", question, re.I)
    seat_word = positive_word(re.compile(r"\bseats?\b", re.I), "seats")
    seat_requested = bool(_SEAT_COMPLEMENT.search(question)) or (seat_word and (bool(_COUNT_OPERATOR.search(question)) or member_seat_alias))
    if seat_requested or member_seat_alias:
        requested.add("seats")
    person_terms = re.compile(
        r"\b(?:members?|people|persons?|representatives?|senators?|tds?|deput(?:y|ies))\b", re.I,
    )
    if positive_word(person_terms, "members") and not member_seat_alias:
        requested.add("members")
    if re.search(r"\bd[áa]il\s+terms?\b", question, re.I):
        requested.add("dail_terms")

    conflicts = requested & excluded
    return RequestedMeasures(
        frozenset(requested), frozenset(excluded), frozenset(conflicts),
        frozenset({"groups"} if unclassified_groups else ()),
        bool(_COUNT_OPERATOR.search(question)),
    )


def count_operator_matches(question: str) -> tuple[tuple[int, int], ...]:
    return tuple((match.start(), match.end()) for match in _COUNT_OPERATOR.finditer(question))


def member_seat_alias(question: str) -> bool:
    return bool(MEMBER_SEAT_ALIAS.search(question)) and not re.search(r"\bseats?\b", question, re.I)


def excluded_measure_spans(question: str, measure: str) -> tuple[tuple[int, int], ...]:
    pattern = _EXCLUDED_MEASURE.get(measure)
    if pattern is None:
        raise ValueError(f"No reviewed exclusion pattern for measure {measure!r}.")
    return tuple((match.start(), match.end()) for match in pattern.finditer(question))


def is_numeric_measure_request(question: str) -> bool:
    measures = requested_measures(question)
    return measures.has_count_operator or "seats" in measures.requested


def semantic_residual(
    question: str,
    *,
    consumed_patterns=(),
    mentions=(),
    consume_dail_terms: bool = False,
    consume_dates: bool = False,
    consume_months: bool = False,
    consume_group_exclusions: bool = False,
    consume_seat_exclusions: bool = False,
    consume_member_exclusions: bool = False,
) -> tuple[str, ...]:
    """Return unconsumed semantic tokens after exact supported slots/phrases.

    Only closed grammatical function words are ignored. Names, numbers,
    modifiers, and domain terms remain and therefore fail closed.
    """
    text = unicodedata.normalize("NFC", question)
    spans: set[tuple[int, int]] = set()
    for mention in sorted(set(mentions), key=len, reverse=True):
        spans.update(
            (match.start(), match.end())
            for match in re.finditer(
                r"(?<!\w)" + re.escape(mention) + r"(?!\w)(?:['’]s\b)?",
                text, flags=re.IGNORECASE,
            )
        )
    if consume_dail_terms:
        spans.update((item.start, item.end) for item in numbered_dail_terms(text))
    if consume_dates:
        spans.update(_calendar_date_spans(text))
    if consume_months:
        from .composable_plan import _MONTHS

        names = "|".join(re.escape(name) for name in sorted(_MONTHS, key=len, reverse=True))
        pattern = re.compile(r"(?<!\w)(?:" + names + r")\s+[0-9]{4}(?![0-9])", re.I)
        spans.update((match.start(), match.end()) for match in pattern.finditer(text))
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " * (end - start) + text[end:]
    if consume_group_exclusions:
        text = _EXCLUDED_MEASURE["groups"].sub(" ", text)
    if consume_seat_exclusions:
        text = _EXCLUDED_MEASURE["seats"].sub(" ", text)
    if consume_member_exclusions:
        text = _EXCLUDED_MEASURE["members"].sub(" ", text)
    for pattern in consumed_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    tokens = re.findall(r"[^\W_]+(?:['’][^\W_]+)*", unicodedata.normalize("NFC", text).casefold())
    return tuple(token for token in tokens if token not in _GRAMMAR_WORDS)


def member_measure_scope(question: str) -> MeasureScope:
    """Separate an explicit excluded measure from a requested people count.

    Removing an exclusion cannot erase another condition: only a terminal or
    punctuation-delimited ``rather than seats`` clause is recognized. Any
    affirmative seat request elsewhere remains visible to the normal guard.
    """
    if not (re.search(r"\b(?:how\s+many|count|number\s+of|total\s+of)\b", question, re.I)
            and re.search(r"\b(?:members?|people|persons?|TDs?|deput(?:y|ies))\b", question, re.I)):
        return MeasureScope(question, frozenset())
    positive, count = re.subn(
        r"\brather\s+than\s+(?:the\s+)?seats?\b(?=\s*(?:[,;.!?]|$))",
        " ", question, flags=re.I,
    )
    return MeasureScope(positive, frozenset({"seats"}) if count else frozenset())


def without_optional_overlap_clause(question: str) -> str:
    """Remove only disclaimers that explicitly *do not require* overlap.

    A request for non-overlap is still a constraint and must remain untouched.
    So is an affirmative simultaneous-service condition elsewhere in the text.
    This helper is intended only for the existing term-wide cross-house shape.
    """
    return re.sub(
        r"\b(?:even\s+if\s+(?:the\s+|their\s+)?(?:membership\s+)?periods?\s+"
        r"(?:did\s+not|do\s+not|didn't|don't)\s+overlap|"
        r"(?:the\s+|their\s+)?(?:membership\s+)?periods?\s+need\s+not\s+overlap)"
        r"(?=\s*(?:[,;.!?]|$))",
        " ", question, flags=re.I,
    )


def relationship_wording(question: str, *, mentions=()) -> str:
    """Canonicalize role words and grounded possessives, not entity identities.

    Exact source spans are masked before transformations, then restored. Only
    possessive suffixes attached to supplied grounded mentions are consumed.
    The caller must separately check that each mention occurs in the original.
    """
    mentions = tuple(mentions)
    if any(not isinstance(mention, str) or not mention.strip() for mention in mentions):
        raise ValueError("Relationship wording requires nonempty original entity mentions.")
    text = question
    protected = {}
    for index, mention in enumerate(sorted(set(mentions), key=len, reverse=True)):
        token = f"ENTITYMARKER{index}END"
        while token.casefold() in text.casefold():
            token += "X"
        protected[token] = mention
        text = re.sub(r"(?<!\w)" + re.escape(mention) + r"(?!\w)(?:['’]s\b)?", lambda _: token, text, flags=re.I)
    text = re.sub(r"\bwho\s+else\b", "who other", text, flags=re.I)
    text = re.sub(r"\brepresentatives\b", "members", text, flags=re.I)
    for token, mention in protected.items():
        text = text.replace(token, mention)
    return text
