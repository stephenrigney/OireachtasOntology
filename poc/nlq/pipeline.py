"""Shared translation, validation, and local-query boundary for the NLQ POC."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .errors import NLQError
from .llm import Translation
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

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.result is not None


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
    """Run the existing direct-translation pipeline without changing its policy.

    The Fuseki client is created lazily, after translation and local validation,
    matching the browser's current behaviour.  ``on_phase`` is intentionally a
    small observation hook so the browser can preserve its existing unexpected
    error diagnostics while non-UI callers can use the same boundary.
    """

    def set_phase(value: str) -> None:
        if on_phase is not None:
            on_phase(value)

    translation = None
    safe_sparql = None
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
        fuseki = fuseki_factory()
        result = fuseki.query(safe_sparql)
    except NLQError as error:
        return PipelineOutcome(translation, safe_sparql, None, error, "Fuseki query")

    return PipelineOutcome(translation, safe_sparql, result, None, None)
