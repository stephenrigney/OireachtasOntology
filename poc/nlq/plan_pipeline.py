"""Browser-facing Phase 2 structured planning and query execution path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .errors import NLQError
from .plan_sparql import GenerationResult, PlanSparqlGenerator
from .results import QueryResult, format_debug_payload
from .structured_planner import PlannerResult, StructuredPlanner


_UNSUPPORTED_INTENT_DIAGNOSTIC = (
    "requested information is not represented by the available semantic facts"
)


@dataclass(frozen=True)
class PlannedQueryOutcome:
    """Inspectable terminal outcome of the Phase 2 browser interaction."""

    status: str
    planner_result: PlannerResult | None = None
    generation: GenerationResult | None = None
    result: QueryResult | None = None
    diagnostic: str | None = None
    debug_output: str | None = None
    debug_source: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "success" and self.result is not None


def _planner_failure_outcome(
    planner_result: PlannerResult,
    status: str,
    *,
    debug_source: str = "Structured planner",
) -> PlannedQueryOutcome:
    payload = planner_result.as_dict()
    return PlannedQueryOutcome(
        status=status,
        planner_result=planner_result,
        diagnostic=planner_result.diagnostic,
        debug_output=(planner_result.debug_output or format_debug_payload(payload)),
        debug_source=debug_source,
    )


def process_planned_question(
    question: str,
    *,
    planner_generator_factory: Callable[[], object],
    plan_sparql_generator: PlanSparqlGenerator,
    fuseki_factory: Callable[[], object],
    supported_predicates,
    on_phase: Callable[[str], None] | None = None,
) -> PlannedQueryOutcome:
    """Plan, resolve, compile, safety-check and execute one local question.

    The model only produces a draft semantic plan. Entity resolution, plan
    validation, query generation, SPARQL validation, and Fuseki execution use
    the existing deterministic Phase 2 components. No failed or non-resolved
    plan is sent to Fuseki as an answer query.
    """

    def set_phase(value: str) -> None:
        if on_phase is not None:
            on_phase(value)

    generator = None
    try:
        set_phase("structured planner")
        generator = planner_generator_factory()
        fuseki = fuseki_factory()
        planner_result = StructuredPlanner(
            generator, fuseki, supported_predicates=supported_predicates,
        ).plan(question)
    except Exception as error:
        return PlannedQueryOutcome(
            status="planner_failure",
            diagnostic=f"{type(error).__name__}: {error}",
            debug_output=format_debug_payload({
                "stage": "structured planner",
                "error_type": type(error).__name__,
                "diagnostic": str(error),
            }),
            debug_source="Structured planner",
        )
    finally:
        if generator is not None:
            close = getattr(generator, "close", None)
            if callable(close):
                close()

    if planner_result.status == "clarification_required":
        return _planner_failure_outcome(planner_result, "ambiguous_entity")
    if planner_result.status == "unresolved_entity":
        return _planner_failure_outcome(planner_result, "unresolved_entity")
    if (
        planner_result.status in {"unsupported_vocabulary", "set_valued_member_identity"}
        or (
            planner_result.status == "invalid_draft_semantics"
            and _UNSUPPORTED_INTENT_DIAGNOSTIC in (planner_result.diagnostic or "").lower()
        )
    ):
        return _planner_failure_outcome(planner_result, "unsupported_request")
    if planner_result.status == "final_plan_validation_failure":
        return _planner_failure_outcome(
            planner_result, "validation_failure", debug_source="Plan validation",
        )
    if planner_result.status != "validated_plan" or planner_result.plan is None:
        return _planner_failure_outcome(planner_result, "planner_failure")

    set_phase("query-plan compilation and SPARQL safety validation")
    generation = plan_sparql_generator.generate(planner_result)
    if not generation.generated:
        if (
            generation.status == "unsupported_generation"
            and generation.failure_class != "generation_compiler_failure"
        ):
            status = "unsupported_request"
            source = "Query-plan generation"
        elif generation.failure_class == "generation_compiler_failure":
            status = "planner_failure"
            source = "Query-plan generation"
        elif generation.status in {"invalid_plan", "safety_failure"}:
            status = "validation_failure"
            source = "SPARQL validation"
        else:
            status = "planner_failure"
            source = "Query-plan generation"
        return PlannedQueryOutcome(
            status=status,
            planner_result=planner_result,
            generation=generation,
            diagnostic=generation.failure_reason,
            debug_output=format_debug_payload(generation.as_dict()),
            debug_source=source,
        )

    try:
        set_phase("Fuseki query")
        result = fuseki.query(generation.sparql)
    except NLQError as error:
        return PlannedQueryOutcome(
            status="execution_failure",
            planner_result=planner_result,
            generation=generation,
            diagnostic=str(error),
            debug_output=error.debug_output or format_debug_payload({"error": str(error)}),
            debug_source=error.debug_source or "Fuseki",
        )
    except Exception as error:
        return PlannedQueryOutcome(
            status="execution_failure",
            planner_result=planner_result,
            generation=generation,
            diagnostic=f"{type(error).__name__}: {error}",
            debug_output=format_debug_payload({
                "error_type": type(error).__name__, "diagnostic": str(error),
            }),
            debug_source="Fuseki",
        )

    return PlannedQueryOutcome(
        status="success",
        planner_result=planner_result,
        generation=generation,
        result=result,
        debug_output=result.raw_json,
        debug_source="Fuseki",
    )
