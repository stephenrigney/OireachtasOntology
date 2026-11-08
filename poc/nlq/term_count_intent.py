"""Independent, bounded intent admission for the existing term-count operation.

This is an interpretation adapter, NOT an executable plan. Noun phrases and
directed relationship clauses compose; there is no approved-question list and
no bag-of-words fallback. Full consumption is required. Unknown modifiers,
conjunctions, dates, negation and projections therefore remain refusals.
"""

from dataclasses import asdict, dataclass
import re
import unicodedata


@dataclass(frozen=True)
class TermCountIntent:
    countTarget: str
    member: str | None
    scope: str
    answer: str
    exclusions: tuple[str, ...] = ()

    def proposal(self) -> dict:
        result = asdict(self)
        result["exclusions"] = list(self.exclusions)
        return result

    def execution_parameters(self) -> dict:
        return {"member": self.member} if self.member is not None else {}


# Closed phrase vocabulary, composed below by semantic role. Do not add bare
# words to a residual-token allowlist: that loses attachment and direction.
_TERM = r"(?:d[áa]il\s+terms?|terms?\s+of\s+(?:the\s+)?d[áa]il)"
_TARGET = rf"(?:(?:distinct|different|unique|separate|recorded)\s+)*{_TERM}"
_COUNT = r"(?:how\s+many|(?:(?:a|the)\s+)?(?:number|count|tally|total(?:\s+(?:number|count))?)\s+of)"
_RECORD = r"(?:(?:recorded\s+)?memberships?|(?:recorded\s+)?(?:membership|service|member)\s+(?:records?|paths?))"
_CATALOGUE = r"(?:the\s+)?houses?\s+(?:data|dataset|graph|catalogue|catalog)"
_REQUEST = (
    r"(?:(?:please\s+)?(?:give|report|show|tell)(?:\s+me)?\s+|"
    r"(?:could|can|would)\s+you\s+(?:please\s+)?(?:give|report|show|tell)(?:\s+me)?\s+|"
    r"what\s+is\s+)?"
)
_EXCLUDED = {
    "membership_records": r"(?:membership|member|service)\s+(?:rows?|records?|episodes?)",
    "members": r"(?:members?|people|persons?|tds?|deputies)",
    "seats": r"seats?",
}


def analyse_term_count(question: str, *, member: str | None) -> TermCountIntent:
    """Derive the full admitted intent without trusting model semantic claims.

    The model supplies only a grounded entity boundary. Exact RDF resolution
    still belongs to Stage A. Every other role is independently established
    by a complete directed-clause parse. No unrecognised text is discarded.
    """
    text = unicodedata.normalize("NFC", question).strip()
    if member is not None:
        if not isinstance(member, str) or not member.strip():
            raise ValueError("Term count requires a nonempty exact Member mention.")
        member = unicodedata.normalize("NFC", member.strip())
        matches = list(re.finditer(r"(?<!\w)" + re.escape(member) + r"(?!\w)", text, re.I))
        if len(matches) != 1:
            raise ValueError("Term count requires exactly one grounded Member mention.")
        match = matches[0]
        # Use the original span, never model-created spelling or a guessed IRI.
        member = match.group()
        text = text[:match.start()] + " PERSON " + text[match.end():]
    if re.search(r"\bPERSON\b", question, re.I):
        raise ValueError("Reserved interpretation marker in question.")

    text = text.rstrip("?.! ")
    exclusions = []
    # Excluded *measures* do not filter the selected term identities. Only a
    # terminal explicit contrast is supported; named/temporal exclusions are
    # never removed, nor is a positive request elsewhere for that same measure.
    for measure, phrase in _EXCLUDED.items():
        exclusion = re.search(
            rf"(?:[,;]\s*|\s+)(?:rather\s+than|not|instead\s+of)\s+(?:the\s+)?{phrase}$",
            text, re.I,
        )
        if exclusion:
            exclusions.append(measure)
            text = text[:exclusion.start()].strip()
            break

    counted = rf"{_COUNT}\s+{_TARGET}"
    if member is None:
        # Catalogue is a source scope, not an unqualified historical total.
        clauses = (
            rf"{counted}\s+(?:(?:are|were)\s+)?(?:recorded|listed)\s+(?:in|by)\s+{_CATALOGUE}",
            rf"{counted}\s+in\s+{_CATALOGUE}",
            rf"in\s+{_CATALOGUE}\s*,?\s*{_REQUEST}{counted}",
        )
        scope = "houses_catalogue"
    else:
        # Owner attachment is part of the record NP; 'Member record for X'
        # and 'X's membership record' denote the same existing service path.
        record = rf"(?:PERSON\s*['’]s\s+{_RECORD}|(?:the\s+)?{_RECORD}\s+(?:for|of)\s+PERSON)"
        clauses = (
            rf"(?:in\s+)?{counted}\s+(?:has|have|had|did|does)\s+PERSON\s+serv(?:e|ed|es)(?:\s+in)?",
            rf"{counted}\s+(?:do|does|did)\s+{record}\s+(?:(?:link|refer)\s+to|cover|include|reference)",
            rf"{counted}\s+(?:appear|appears|appeared|occur|occurs|occurred)\s+in\s+{record}",
            rf"{counted}\s+(?:are|were)\s+(?:linked|associated)\s+(?:to|with)\s+{record}",
            rf"{counted}\s+(?:are|were)\s+(?:recorded|listed)\s+in\s+{record}",
            rf"{counted}\s+(?:are|were)\s+(?:referenced|covered|included)\s+by\s+{record}",
            rf"in\s+{counted}\s+(?:do|does|did)\s+{record}\s+(?:appear|occur)",
            rf"{counted}\s+in\s+{record}",
            rf"(?:in|from)\s+{record}\s*,\s*{_REQUEST}{counted}",
        )
        scope = "member_service"
    if not any(re.fullmatch(_REQUEST + clause, text, re.I) for clause in clauses):
        raise ValueError(
            "The complete term-count intent is not representable: expected distinct Dáil terms "
            "through one Member's unfiltered recorded service or the Houses catalogue; "
            "no additional condition, relationship, count target or answer projection was dropped."
        )
    return TermCountIntent("DailTerm", member, scope, "count_distinct", tuple(exclusions))


def validate_term_count_parameters(question: str, parameters: dict) -> dict:
    """Compare proposed roles to independent source analysis, then lower slots.

    Legacy slot-only drafts remain admissible for existing clients, but use
    exactly the same complete-intent check; they cannot bypass the pilot.
    """
    if not isinstance(parameters, dict):
        raise ValueError("Term-count parameters must be an object.")
    typed = {"countTarget", "member", "scope", "answer", "exclusions"}
    if set(parameters) not in ({"member"}, set(), typed):
        raise ValueError("Term-count draft has missing or unreviewed semantic inputs.")
    if set(parameters) == {"member"} and not isinstance(parameters["member"], str):
        raise ValueError("Legacy Member term-count selection requires a name string.")
    intent = analyse_term_count(question, member=parameters.get("member"))
    if set(parameters) == typed and parameters != intent.proposal():
        raise ValueError("Proposed term-count roles disagree with the complete original-question intent.")
    return intent.execution_parameters()
