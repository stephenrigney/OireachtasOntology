"""Shared translation, validation, and local-query boundary for the NLQ POC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .errors import NLQError
from .llm import Translation
from .member_resolution import MemberAmbiguity, resolve_member_ambiguity
from .results import QueryResult
from .safety import complete_known_prefixes, validate_sparql


@dataclass(frozen=True)
class PipelineOutcome:
    """Inspectable outcome of processing one question through the current POC."""

    translation: Translation | None
    validated_sparql: str | None
    result: QueryResult | None
    error: NLQError | None
    error_phase: str | None
    ambiguity: MemberAmbiguity | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and (self.result is not None or self.ambiguity is not None)


def process_question(
    question: str,
    *,
    translator,
    fuseki_factory: Callable[[], object],
    schema_context: str,
    supported_predicates,
    on_phase: Callable[[str], None] | None = None,
    on_translation: Callable[[Translation], None] | None = None,
) -> PipelineOutcome:
    """Run direct translation behind the bounded local Member-resolution gate.

    A bounded read-only Member-label lookup runs before translation. If an exact
    local name remains ambiguous, the pipeline returns that outcome without
    producing or executing answer SPARQL. Otherwise the existing direct
    translation, validation and query flow continues. ``on_phase`` lets the
    browser preserve actionable diagnostics while non-UI callers use the same
    boundary.
    """

    def set_phase(value: str) -> None:
        if on_phase is not None:
            on_phase(value)

    translation = None
    safe_sparql = None
    fuseki = None
    set_phase("Member name resolution")
    try:
        # This bounded local lookup is deliberately tied to complete Member
        # foaf:name labels in the question, not to answer-row cardinality.
        fuseki = fuseki_factory()
        ambiguity = resolve_member_ambiguity(
            question, fuseki, supported_predicates=supported_predicates,
        )
        if ambiguity is not None:
            return PipelineOutcome(None, None, None, None, None, ambiguity)
    except NLQError as error:
        return PipelineOutcome(translation, safe_sparql, None, error, "Member name resolution")

    set_phase("LLM translation")
    try:
        translation = translator.translate(question, schema_context)
    except NLQError as error:
        return PipelineOutcome(translation, safe_sparql, None, error, "LLM translation")
    if on_translation is not None:
        on_translation(translation)

    set_phase("SPARQL validation")
    try:
        safe_sparql = validate_sparql(
            complete_known_prefixes(translation.sparql),
            supported_predicates=supported_predicates,
        )
    except NLQError as error:
        return PipelineOutcome(translation, safe_sparql, None, error, "SPARQL validation")

    set_phase("Fuseki query")
    try:
        result = fuseki.query(safe_sparql)
    except NLQError as error:
        return PipelineOutcome(translation, safe_sparql, None, error, "Fuseki query")

    return PipelineOutcome(translation, safe_sparql, result, None, None)
