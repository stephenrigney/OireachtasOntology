"""Controlled end-to-end evaluation for validated-plan SPARQL generation."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .benchmark import (
    SemanticScore,
    assess_dataset_prerequisites,
    run_cases as run_phase1_cases,
    score_semantic_result,
)
from .plan_sparql import (
    PlanSparqlGenerator,
    build_label_lookup_query,
)
from .planner_benchmark import _semantic_mismatches
from .results import QueryResult


class PlanBenchmarkError(ValueError):
    """The Phase 2C evaluation artifacts are inconsistent."""


class _ResultDataCoverageError(ValueError):
    """The returned resource has no reviewed local label for benchmark scoring."""


_STAGES = (
    "source_data_coverage",
    "planner_model",
    "plan_validation",
    "entity_binding",
    "generation",
    "sparql_safety",
    "execution",
    "result_scoring",
)


def _failure(record: dict[str, Any], *, stage: str, failure_class: str,
             reason: str, outcome: str) -> None:
    record["stage_status"][stage] = "failed"
    record.update(
        evaluation="failed",
        passed=False,
        observed_outcome=outcome,
        failure_stage=stage,
        failure_class=failure_class,
        failure_reason=reason,
    )


def _serialize_query_result(result: QueryResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    raw = None
    if result.raw_json:
        try:
            raw = json.loads(result.raw_json)
        except json.JSONDecodeError:
            raw = result.raw_json
    return {
        "kind": result.kind,
        "columns": list(result.columns),
        "rows": [list(row) for row in result.rows],
        "boolean": result.boolean,
        "raw_response": raw,
    }


def _result_lexical_values(result: QueryResult) -> tuple[tuple[str, ...], ...]:
    if result.raw_json:
        try:
            payload = json.loads(result.raw_json)
            bindings = payload.get("results", {}).get("bindings")
            if isinstance(bindings, list):
                return tuple(
                    tuple(
                        binding["value"]
                        for binding in row.values()
                        if isinstance(binding, dict) and isinstance(binding.get("value"), str)
                    )
                    for row in bindings if isinstance(row, dict)
                )
        except (json.JSONDecodeError, AttributeError):
            pass
    return tuple(tuple(row) for row in result.rows)


def _score_resource_result(
    expected: dict[str, Any],
    actual: QueryResult,
    *,
    entity_type: str,
    fuseki,
    supported_predicates,
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """Score entity IRIs against reviewed labels without changing the answer query."""
    if actual.kind != "select":
        return score_semantic_result(expected, actual), ()
    labels_by_resource: list[tuple[str, ...]] = []
    lookup_audit: list[dict[str, Any]] = []
    for row in _result_lexical_values(actual):
        if len(row) != 1 or not row[0].startswith("https://data.oireachtas.ie/"):
            return (
                SemanticScore(False, "entity answer did not return one local resource IRI per row"),
                tuple(lookup_audit),
            )
        iri = row[0]
        query = build_label_lookup_query(
            entity_type, iri, supported_predicates=supported_predicates,
        )
        label_result = fuseki.query(query)
        if label_result.kind != "select":
            return (
                SemanticScore(False, "reviewed label lookup did not return a SELECT result"),
                tuple(lookup_audit),
            )
        labels = sorted({item[0] for item in _result_lexical_values(label_result) if item})
        if not labels:
            raise _ResultDataCoverageError(
                f"resource {iri} has no label in its reviewed {entity_type} label graph"
            )
        labels_by_resource.append(tuple(labels))
        lookup_audit.append({"resource_iri": iri, "labels": labels})

    normalized = QueryResult(
        kind="select",
        columns=("reviewed_label",),
        rows=tuple(labels_by_resource),
    )
    return score_semantic_result(expected, normalized), tuple(lookup_audit)


def _planner_failure_stage(result) -> tuple[str, str]:
    if result.failure_stage in {"model_response", "model_json"}:
        return "planner_model", result.failure_class or "planner_model_failure"
    if result.failure_stage in {"draft_validation", "final_validation"}:
        return "plan_validation", result.failure_class or "plan_validation_failure"
    if result.failure_stage == "entity_resolution" or result.status in {
        "clarification_required", "unresolved_entity", "set_valued_member_identity",
        "entity_resolution_failure", "source_data_prerequisite_unavailable",
    }:
        return "entity_binding", result.failure_class or "entity_binding_failure"
    return "planner_model", result.failure_class or "planner_failure"


def run_plan_cases(
    planner_benchmark: dict[str, Any],
    source_benchmark: dict[str, Any],
    dataset_baseline: dict[str, Any],
    *,
    fuseki,
    supported_predicates,
    planner_factory: Callable[[dict[str, Any], Any], Any],
) -> list[dict[str, Any]]:
    """Run planner → validated plan → deterministic SPARQL → Fuseki → scoring.

    Source-data prerequisite checks run first.  Expected ambiguous/unresolved
    cases are scored as non-executable planning outcomes; no SPARQL is sent for
    them.  A resource answer stays an IRI in the generated query; the evaluator
    resolves its reviewed label separately only to compare Phase 1's existing
    label-valued benchmark invariants.
    """
    declared = planner_benchmark["source_benchmark"]
    if declared["benchmark_version"] != source_benchmark.get("benchmark_version"):
        raise PlanBenchmarkError(
            "planner benchmark requires source benchmark version "
            f"{declared['benchmark_version']!r}, received "
            f"{source_benchmark.get('benchmark_version')!r}"
        )
    dataset = dataset_baseline.get("dataset")
    if (
        dataset_baseline.get("schema_version") != 1
        or not isinstance(dataset, dict)
        or not isinstance(dataset.get("id"), str)
        or not dataset["id"].startswith("sha256:")
    ):
        raise PlanBenchmarkError("Phase 2C evaluation requires a valid Phase 0A dataset baseline")

    source_cases = {case["id"]: case for case in source_benchmark["cases"]}
    plan_generator = PlanSparqlGenerator(supported_predicates=supported_predicates)
    outcomes: list[dict[str, Any]] = []
    for case in planner_benchmark["cases"]:
        source_case = source_cases.get(case["source_case_id"])
        if source_case is None:
            raise PlanBenchmarkError(
                f"planner case {case['id']!r} refers to unknown source case "
                f"{case['source_case_id']!r}"
            )
        record: dict[str, Any] = {
            "case_id": case["id"],
            "source_case_id": case["source_case_id"],
            "question": case.get("question", source_case["question"]),
            "expectation": case["expectation"],
            "evaluation": "not_scored",
            "passed": None,
            "observed_outcome": "not_run",
            "failure_stage": None,
            "failure_class": None,
            "failure_reason": None,
            "coverage": None,
            "stage_status": {stage: "not_run" for stage in _STAGES},
            "planner_result": None,
            "generation_result": None,
            "execution_result": None,
            "result_oracle": None,
            "label_scoring_lookups": [],
            "score_reason": None,
        }
        try:
            coverage = assess_dataset_prerequisites(
                source_case, dataset_baseline,
                fuseki=fuseki,
                supported_predicates=supported_predicates,
            )
        except Exception as error:
            record["coverage"] = {"state": "unverified", "reason": str(error)}
            record["stage_status"]["source_data_coverage"] = "unverified"
            record.update(
                observed_outcome="source_data_coverage_unverified",
                failure_stage="source_data_coverage",
                failure_class="source_data_coverage",
                failure_reason=f"coverage prerequisite could not be verified: {error}",
            )
            outcomes.append(record)
            continue
        record["coverage"] = {"state": coverage.state, "reason": coverage.reason}
        record["stage_status"]["source_data_coverage"] = coverage.state
        if coverage.state != "available":
            record.update(
                observed_outcome=("source_data_coverage_unavailable"
                                  if coverage.state == "unavailable"
                                  else "source_data_coverage_condition_changed"),
                failure_stage="source_data_coverage",
                failure_class="source_data_coverage",
                failure_reason=coverage.reason,
            )
            outcomes.append(record)
            continue
        if case["expectation"] == "source_data_coverage":
            record.update(
                observed_outcome="source_data_prerequisite_available",
                failure_stage="source_data_coverage",
                failure_class="source_data_coverage",
                failure_reason="the documented unavailable-data prerequisite is no longer absent",
            )
            outcomes.append(record)
            continue
        if case["expectation"] == "manual_review":
            record.update(
                observed_outcome="manual_review_not_scored",
                failure_reason=case.get("not_scored_reason"),
            )
            outcomes.append(record)
            continue

        planner = None
        try:
            planner = planner_factory(case, fuseki)
            planner_result = planner.plan(record["question"])
        except Exception as error:
            _failure(
                record, stage="planner_model", failure_class="planner_model_failure",
                reason=str(error), outcome="planner_model_failure",
            )
            outcomes.append(record)
            continue
        finally:
            generator = getattr(planner, "generator", None) if planner is not None else None
            if generator is not None and hasattr(generator, "close"):
                generator.close()
        record["planner_result"] = planner_result.as_dict()
        record["stage_status"]["planner_model"] = "passed"

        if planner_result.plan is None:
            stage, failure_class = _planner_failure_stage(planner_result)
            record["stage_status"][stage] = "failed"
            record.update(
                evaluation="failed" if case["expectation"] not in {"manual_review", "source_data_coverage"}
                else "not_scored",
                passed=False if case["expectation"] not in {"manual_review", "source_data_coverage"}
                else None,
                observed_outcome=planner_result.status,
                failure_stage=stage,
                failure_class=failure_class,
                failure_reason=planner_result.diagnostic or planner_result.status,
            )
            outcomes.append(record)
            continue

        record["stage_status"]["plan_validation"] = "passed"
        if planner_result.status in {"clarification_required", "unresolved_entity"}:
            record["stage_status"]["entity_binding"] = (
                "blocked_expected" if planner_result.status == case["expectation"] else "failed"
            )
            mismatches = (
                [f"planner status was {planner_result.status!r}, expected {case['expectation']!r}"]
                if planner_result.status != case["expectation"] else []
            )
            if not mismatches:
                mismatches = _semantic_mismatches(planner_result.plan, case)
            if mismatches:
                record.update(
                    evaluation="failed", passed=False,
                    observed_outcome=planner_result.status,
                    failure_stage="planner_model",
                    failure_class="semantic_plan_mismatch",
                    failure_reason="; ".join(mismatches),
                )
            else:
                record.update(
                    evaluation="passed", passed=True,
                    observed_outcome=planner_result.status,
                    score_reason="expected non-executable identity outcome matched",
                )
            outcomes.append(record)
            continue
        if planner_result.status != "validated_plan":
            stage, failure_class = _planner_failure_stage(planner_result)
            record["stage_status"][stage] = "failed"
            record.update(
                evaluation="failed", passed=False,
                observed_outcome=planner_result.status,
                failure_stage=stage,
                failure_class=failure_class,
                failure_reason=planner_result.diagnostic or planner_result.status,
            )
            outcomes.append(record)
            continue

        record["stage_status"]["entity_binding"] = "passed"
        mismatches = _semantic_mismatches(planner_result.plan, case)
        if mismatches:
            record.update(
                evaluation="failed", passed=False,
                observed_outcome="semantic_plan_mismatch",
                failure_stage="planner_model",
                failure_class="semantic_plan_mismatch",
                failure_reason="; ".join(mismatches),
            )
            outcomes.append(record)
            continue

        generation = plan_generator.generate(planner_result)
        record["generation_result"] = generation.as_dict()
        if not generation.generated:
            if generation.status == "invalid_plan":
                stage = "plan_validation"
            elif generation.status == "rejected_plan":
                stage = "entity_binding"
            elif generation.status == "safety_failure":
                stage = "sparql_safety"
            else:
                stage = "generation"
            record["stage_status"][stage] = "failed"
            record.update(
                evaluation="failed", passed=False,
                observed_outcome=generation.status,
                failure_stage=stage,
                failure_class=generation.failure_class or stage,
                failure_reason=generation.failure_reason,
            )
            outcomes.append(record)
            continue
        record["stage_status"]["generation"] = "passed"
        record["stage_status"]["sparql_safety"] = "passed"
        record["generated_sparql"] = generation.sparql
        expected_result = case.get("expected_result")
        if expected_result is not None:
            if expected_result["kind"] != generation.query_form.lower():
                raise PlanBenchmarkError(
                    f"planner case {case['id']!r} result oracle expects "
                    f"{expected_result['kind']!r}, but generation produced "
                    f"{generation.query_form!r}"
                )
            record["result_oracle"] = "planner_case.expected_result"
        elif source_case.get("evaluation_mode") == "semantic_invariants":
            source_oracle = source_case.get("expected_result")
            if source_oracle is not None and source_oracle.get("kind") == generation.query_form.lower():
                expected_result = source_oracle
                record["result_oracle"] = "source_case.expected_result"

        try:
            query_result = fuseki.query(generation.sparql)
        except Exception as error:
            _failure(
                record, stage="execution", failure_class="execution",
                reason=str(error), outcome="query_execution_failure",
            )
            outcomes.append(record)
            continue
        record["stage_status"]["execution"] = "passed"
        record["execution_result"] = _serialize_query_result(query_result)

        if source_case.get("evaluation_mode") != "semantic_invariants":
            record.update(
                evaluation="not_scored", passed=None,
                observed_outcome="query_result_not_scored",
            )
            outcomes.append(record)
            continue
        if expected_result is None:
            record.update(
                evaluation="not_scored", passed=None,
                observed_outcome="no_result_oracle_for_answer_shape",
                failure_reason=(
                    "the planner case and source case have no explicit result oracle "
                    "for this answer shape; coverage probes are not borrowed for scoring"
                ),
            )
            outcomes.append(record)
            continue
        try:
            if generation.generation_trace.get("answer_value_kind") == "resource":
                score, label_lookups = _score_resource_result(
                    expected_result, query_result,
                    entity_type=generation.semantic_answer_shape["entityType"],
                    fuseki=fuseki,
                    supported_predicates=supported_predicates,
                )
                record["label_scoring_lookups"] = list(label_lookups)
            else:
                score = score_semantic_result(expected_result, query_result)
        except _ResultDataCoverageError as error:
            record["stage_status"]["source_data_coverage"] = "unavailable"
            record.update(
                evaluation="not_scored", passed=None,
                observed_outcome="source_data_coverage_unavailable",
                failure_stage="source_data_coverage",
                failure_class="source_data_coverage",
                failure_reason=str(error),
            )
            outcomes.append(record)
            continue
        except Exception as error:
            _failure(
                record, stage="execution", failure_class="execution",
                reason=f"semantic result scoring lookup failed: {error}",
                outcome="result_scoring_execution_failure",
            )
            outcomes.append(record)
            continue
        record["stage_status"]["result_scoring"] = "passed" if score.passed else "failed"
        record["score_reason"] = score.reason
        record["passed"] = score.passed
        record["evaluation"] = "passed" if score.passed else "failed"
        record["observed_outcome"] = "query_result_scored"
        if not score.passed:
            record.update(
                failure_stage="result_scoring",
                failure_class="semantic_result_mismatch",
                failure_reason=score.reason,
            )
        outcomes.append(record)
    return outcomes


def summarize_plan_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    failures = Counter(
        result["failure_class"] for result in case_results if result.get("passed") is False
    )
    stage_counts = {
        stage: dict(sorted(Counter(
            result.get("stage_status", {}).get(stage, "not_run")
            for result in case_results
        ).items()))
        for stage in _STAGES
    }
    return {
        "total_cases": len(case_results),
        "passed": sum(result.get("passed") is True for result in case_results),
        "failed": sum(result.get("passed") is False for result in case_results),
        "not_scored": sum(result.get("passed") is None for result in case_results),
        "by_failure_class": dict(sorted(failures.items())),
        "stage_outcomes": stage_counts,
    }


def run_phase1_comparison(
    planner_benchmark: dict[str, Any],
    source_benchmark: dict[str, Any],
    dataset_baseline: dict[str, Any],
    *,
    fuseki,
    repository_root: Path,
    translator_factory: Callable[[dict[str, Any]], object],
) -> dict[str, Any]:
    """Run Phase 1 direct generation for exactly comparable controlled cases.

    Cases with a planner-benchmark question override are excluded when the
    source benchmark's expected result belongs to its original question; those
    variants need their own result oracle before a fair side-by-side score.
    """
    source_cases = {case["id"]: case for case in source_benchmark["cases"]}
    comparable_cases = []
    case_map: dict[str, str] = {}
    not_compared = []
    for planner_case in planner_benchmark["cases"]:
        if planner_case["expectation"] not in {"validated_plan", "clarification_required"}:
            continue
        source_case = source_cases[planner_case["source_case_id"]]
        question = planner_case.get("question", source_case["question"])
        if question != source_case["question"]:
            not_compared.append({
                "case_id": planner_case["id"],
                "reason": "question override has no matching Phase 1 result oracle",
            })
            continue
        case_id = f"phase1-comparison-{planner_case['id']}"
        selected = dict(source_case)
        selected["id"] = case_id
        selected["question"] = question
        comparable_cases.append(selected)
        case_map[case_id] = planner_case["id"]

    if not comparable_cases:
        return {
            "method": "phase1_direct_generation",
            "comparable_case_ids": [],
            "not_compared": not_compared,
            "case_results": [],
            "summary": {"total_cases": 0, "passed": 0, "failed": 0, "not_scored": 0},
        }
    subset = {
        "benchmark_id": source_benchmark["benchmark_id"],
        "benchmark_version": source_benchmark["benchmark_version"],
        "cases": comparable_cases,
    }
    phase1_results = run_phase1_cases(
        subset, dataset_baseline,
        fuseki=fuseki,
        tier="measured",
        repository_root=repository_root,
        translator_factory=translator_factory,
    )
    for outcome in phase1_results:
        outcome["planner_case_id"] = case_map.get(outcome["case_id"])
    failures = Counter(
        result["failure_class"] for result in phase1_results if result.get("passed") is False
    )
    return {
        "method": "phase1_direct_generation",
        "comparable_case_ids": [case_map[item["case_id"]] for item in phase1_results],
        "not_compared": not_compared,
        "case_results": phase1_results,
        "summary": {
            "total_cases": len(phase1_results),
            "passed": sum(result.get("passed") is True for result in phase1_results),
            "failed": sum(result.get("passed") is False for result in phase1_results),
            "not_scored": sum(result.get("passed") is None for result in phase1_results),
            "by_failure_class": dict(sorted(failures.items())),
        },
    }
