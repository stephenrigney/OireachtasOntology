"""Controlled evaluation of semantic planning, separate from query execution."""

from __future__ import annotations

import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from .benchmark import assess_dataset_prerequisites


DEFAULT_PLANNER_BENCHMARK_PATH = (
    Path(__file__).resolve().parent / "benchmarks" / "planner-benchmark-v1.json"
)


class PlannerBenchmarkError(ValueError):
    """The planner evaluation benchmark is malformed or inconsistent."""


def load_planner_benchmark(path: str | Path = DEFAULT_PLANNER_BENCHMARK_PATH) -> dict[str, Any]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PlannerBenchmarkError(f"could not read planner benchmark JSON: {error}") from error
    if not isinstance(document, dict) or set(document) != {
        "schema_version", "benchmark_id", "benchmark_version", "source_benchmark", "cases",
    }:
        raise PlannerBenchmarkError("planner benchmark root has missing or unknown fields")
    if document["schema_version"] != 1:
        raise PlannerBenchmarkError(f"unsupported planner benchmark schema {document['schema_version']!r}")
    if not isinstance(document["benchmark_id"], str) or not document["benchmark_id"]:
        raise PlannerBenchmarkError("planner benchmark_id must be non-empty text")
    if not isinstance(document["benchmark_version"], str) or not document["benchmark_version"]:
        raise PlannerBenchmarkError("planner benchmark_version must be non-empty text")
    source = document["source_benchmark"]
    if not isinstance(source, dict) or set(source) != {"path", "benchmark_version"}:
        raise PlannerBenchmarkError("source_benchmark must identify its source artifact and version")
    if not isinstance(source["path"], str) or not isinstance(source["benchmark_version"], str):
        raise PlannerBenchmarkError("source_benchmark fields must be text")
    cases = document["cases"]
    if not isinstance(cases, list) or not cases:
        raise PlannerBenchmarkError("planner benchmark cases must be a non-empty array")
    seen: set[str] = set()
    supported_expectations = {
        "validated_plan", "clarification_required", "unresolved_entity",
        "manual_review", "source_data_coverage",
    }
    for index, case in enumerate(cases):
        where = f"cases[{index}]"
        if not isinstance(case, dict):
            raise PlannerBenchmarkError(f"{where} must be an object")
        allowed = {
            "id", "source_case_id", "question", "expectation", "required_entities",
            "required_requirements", "required_temporal_constraints", "aggregation",
            "answer_shape", "not_scored_reason", "expected_result",
        }
        if not {"id", "source_case_id", "expectation"} <= set(case) or set(case) - allowed:
            raise PlannerBenchmarkError(f"{where} has missing or unknown fields")
        if not all(isinstance(case[key], str) and case[key].strip()
                   for key in ("id", "source_case_id", "expectation")):
            raise PlannerBenchmarkError(f"{where} id/source_case_id/expectation must be non-empty text")
        if case["id"] in seen:
            raise PlannerBenchmarkError(f"duplicate planner case id {case['id']!r}")
        seen.add(case["id"])
        if case["expectation"] not in supported_expectations:
            raise PlannerBenchmarkError(f"{where}.expectation is unsupported")
        if "question" in case and (not isinstance(case["question"], str) or not case["question"].strip()):
            raise PlannerBenchmarkError(f"{where}.question must be non-empty text")
        if case["expectation"] == "manual_review" and not (
            isinstance(case.get("not_scored_reason"), str) and case["not_scored_reason"].strip()
        ):
            raise PlannerBenchmarkError(f"{where} manual_review needs a not_scored_reason")
        if "expected_result" in case:
            expected_result = case["expected_result"]
            if not isinstance(expected_result, dict) or expected_result.get("kind") not in {"ask", "select"}:
                raise PlannerBenchmarkError(f"{where}.expected_result must be an ASK or SELECT oracle")
            if expected_result["kind"] == "ask" and not isinstance(expected_result.get("boolean"), bool):
                raise PlannerBenchmarkError(f"{where}.expected_result ASK oracle needs a boolean")
            if expected_result["kind"] == "select" and not isinstance(expected_result.get("invariants"), dict):
                raise PlannerBenchmarkError(f"{where}.expected_result SELECT oracle needs invariants")
        for field in ("required_entities", "required_requirements", "required_temporal_constraints"):
            if field in case and not isinstance(case[field], list):
                raise PlannerBenchmarkError(f"{where}.{field} must be an array")
    return document


def _normalise_label(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _participant_type(participant: dict[str, Any], entities: dict[str, dict[str, Any]]) -> str | None:
    if "entity" in participant:
        entity = entities.get(participant["entity"])
        return entity["type"] if entity else None
    return participant.get("type")


def _participant_matches_entity_label(
    participant: dict[str, Any] | None,
    expected_label: str,
    entities: dict[str, dict[str, Any]],
) -> bool:
    if not isinstance(participant, dict) or "entity" not in participant:
        return False
    entity = entities.get(participant["entity"])
    return (
        entity is not None
        and _normalise_label(entity["label"]) == _normalise_label(expected_label)
    )


def _semantic_mismatches(plan: dict[str, Any], case: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []
    plan_entities = {entity["id"]: entity for entity in plan["entities"]}
    requirements_by_id = {requirement["id"]: requirement for requirement in plan["requirements"]}
    for expected in case.get("required_entities", []):
        match = next((
            entity for entity in plan["entities"]
            if entity["type"] == expected["type"]
            and _normalise_label(entity["label"]) == _normalise_label(expected["label"])
        ), None)
        if match is None:
            mismatches.append(
                f"missing entity mention {expected['type']} / {expected['label']!r}"
            )
            continue
        if match["resolution"] != expected["resolution"]:
            mismatches.append(
                f"entity {expected['label']!r} resolution was {match['resolution']!r}, "
                f"expected {expected['resolution']!r}"
            )
        if expected["resolution"] == "ambiguous":
            candidate_iris = {
                candidate["iri"] for candidate in match.get("candidates", [])
            }
            minimum = expected.get("minimum_candidates", 2)
            if len(candidate_iris) < minimum or "iri" in match:
                mismatches.append(
                    f"ambiguous entity did not preserve {minimum} distinct candidate IRIs without selection"
                )

    for expected in case.get("required_requirements", []):
        matched = False
        for requirement in plan["requirements"]:
            if requirement["fact"] != expected["fact"]:
                continue
            subject_type = _participant_type(requirement["subject"], plan_entities)
            object_type = (
                _participant_type(requirement["object"], plan_entities)
                if "object" in requirement else None
            )
            if (subject_type == expected["subject_type"]
                    and object_type == expected.get("object_type")):
                matched = all(
                    _participant_matches_entity_label(
                        requirement.get(participant), expected[label_key], plan_entities,
                    )
                    for participant, label_key in (
                        ("subject", "subject_entity_label"),
                        ("object", "object_entity_label"),
                    )
                    if label_key in expected
                )
                if matched:
                    break
        if not matched:
            mismatches.append(
                f"missing requirement {expected['fact']} with participant types "
                f"{expected['subject_type']} -> {expected.get('object_type')}"
            )
            if "subject_entity_label" in expected or "object_entity_label" in expected:
                mismatches[-1] += " and required entity-linked participant labels"

    for expected in case.get("required_temporal_constraints", []):
        matched = False
        for constraint in plan["temporalConstraints"]:
            target = requirements_by_id.get(constraint["target"])
            period = constraint.get("period", {})
            period_entity = plan_entities.get(period.get("entity"))
            if (
                constraint["kind"] == expected["kind"]
                and target is not None
                and target["fact"] == expected["target_fact"]
                and period_entity is not None
                and period_entity["type"] == expected["period_entity_type"]
                and _normalise_label(period_entity["label"])
                == _normalise_label(expected["period_entity_label"])
            ):
                matched = True
                break
        if not matched:
            mismatches.append(
                f"missing {expected['kind']} temporal constraint on {expected['target_fact']} "
                f"for {expected['period_entity_label']}"
            )

    expected_aggregation = case.get("aggregation")
    if expected_aggregation is not None:
        aggregation = plan["aggregation"]
        target_requirement = (
            requirements_by_id.get(aggregation["target"]["requirement"])
            if aggregation is not None else None
        )
        if (
            aggregation is None
            or aggregation["operation"] != expected_aggregation["operation"]
            or target_requirement is None
            or target_requirement["fact"] != expected_aggregation["target_fact"]
            or aggregation["target"]["participant"] != expected_aggregation["target_participant"]
            or len(aggregation["groupBy"]) != expected_aggregation["group_by_count"]
        ):
            mismatches.append("aggregation operation, target, or grouping did not match")

    expected_answer = case.get("answer_shape")
    if expected_answer is not None:
        if any(plan["answerShape"].get(key) != value for key, value in expected_answer.items()):
            mismatches.append(f"answer shape did not match {expected_answer!r}")
    return mismatches


def run_planner_cases(
    planner_benchmark: dict[str, Any],
    source_benchmark: dict[str, Any],
    dataset_baseline: dict[str, Any],
    *,
    fuseki,
    supported_predicates,
    planner_factory: Callable[[dict[str, Any], Any], Any],
) -> list[dict[str, Any]]:
    """Evaluate draft-to-plan outcomes after independent source-coverage checks.

    Coverage probes are the existing curated benchmark probes. No plan is
    translated to SPARQL and no query result is used to score planner output.
    """
    declared_source = planner_benchmark["source_benchmark"]
    if declared_source["benchmark_version"] != source_benchmark.get("benchmark_version"):
        raise PlannerBenchmarkError(
            "planner benchmark requires source benchmark version "
            f"{declared_source['benchmark_version']!r}, received "
            f"{source_benchmark.get('benchmark_version')!r}"
        )
    source_cases = {case["id"]: case for case in source_benchmark["cases"]}
    outcomes = []
    for case in planner_benchmark["cases"]:
        source_case = source_cases.get(case["source_case_id"])
        if source_case is None:
            raise PlannerBenchmarkError(
                f"planner case {case['id']!r} refers to unknown source case {case['source_case_id']!r}"
            )
        record = {
            "case_id": case["id"],
            "source_case_id": case["source_case_id"],
            "question": case.get("question", source_case["question"]),
            "expectation": case["expectation"],
            "evaluation": "not_scored",
            "passed": None,
            "observed_outcome": "not_run",
            "failure_class": None,
            "failure_reason": None,
            "coverage": None,
            "planner_result": None,
        }
        try:
            coverage = assess_dataset_prerequisites(
                source_case, dataset_baseline, fuseki=fuseki,
                supported_predicates=supported_predicates,
            )
        except Exception as error:
            record.update(
                observed_outcome="source_data_coverage_unverified",
                failure_class="source_data_coverage",
                failure_reason=f"coverage prerequisite execution failed: {error}",
                coverage={"state": "unverified"},
            )
            outcomes.append(record)
            continue
        record["coverage"] = {"state": coverage.state, "reason": coverage.reason}
        if coverage.state != "available":
            record.update(
                observed_outcome=("source_data_coverage_unavailable"
                                  if coverage.state == "unavailable"
                                  else "source_data_coverage_condition_changed"),
                failure_class="source_data_coverage",
                failure_reason=coverage.reason,
            )
            outcomes.append(record)
            continue

        if case["expectation"] == "source_data_coverage":
            record.update(
                observed_outcome="source_data_prerequisite_available",
                failure_class="source_data_coverage",
                failure_reason="the documented unavailable-data prerequisite is no longer absent",
            )
            outcomes.append(record)
            continue

        try:
            planner = planner_factory(case, fuseki)
            try:
                result = planner.plan(record["question"])
            finally:
                generator = getattr(planner, "generator", None)
                if generator is not None and hasattr(generator, "close"):
                    generator.close()
        except Exception as error:
            record.update(
                evaluation="failed" if case["expectation"] != "manual_review" else "not_scored",
                passed=False if case["expectation"] != "manual_review" else None,
                observed_outcome="planner_evaluation_error",
                failure_class="planner_evaluation_error",
                failure_reason=str(error),
            )
            outcomes.append(record)
            continue

        serialised = result.as_dict()
        record["planner_result"] = serialised
        record["observed_outcome"] = result.status
        if case["expectation"] == "manual_review":
            record["evaluation"] = "not_scored"
            record["failure_reason"] = case["not_scored_reason"]
            outcomes.append(record)
            continue

        mismatches = []
        if result.status != case["expectation"]:
            mismatches.append(
                f"planner status was {result.status!r}, expected {case['expectation']!r}"
            )
        if result.plan is not None and result.status == case["expectation"]:
            mismatches.extend(_semantic_mismatches(result.plan, case))
        if mismatches:
            record.update(
                evaluation="failed", passed=False,
                failure_class=(result.failure_class or "semantic_plan_mismatch"),
                failure_reason="; ".join(mismatches),
            )
        else:
            record.update(evaluation="passed", passed=True)
        outcomes.append(record)
    return outcomes


def summarize_planner_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    failures = Counter(
        result["failure_class"] for result in case_results if result.get("failure_class")
    )
    return {
        "total_cases": len(case_results),
        "passed": sum(result["passed"] is True for result in case_results),
        "failed": sum(result["passed"] is False for result in case_results),
        "not_scored": sum(result["passed"] is None for result in case_results),
        "by_failure_class": dict(sorted(failures.items())),
    }
