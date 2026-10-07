"""Versioned semantic benchmark loading, coverage checks, and scoring."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .errors import NLQError
from .pipeline import process_question
from .results import QueryResult
from .safety import validate_sparql


BENCHMARK_SCHEMA_VERSION = 1
DEFAULT_BENCHMARK_PATH = (
    Path(__file__).resolve().parent / "benchmarks" / "benchmark-v3.json"
)
GRAPH_FAMILIES = {
    "houses", "parties", "constituencies", "committees", "members", "bills", "debates",
}
CATEGORIES = {
    "simple_lookup",
    "house_term_membership",
    "parliamentary_collections",
    "constituencies_panels",
    "committees",
    "dates_temporal",
    "counts_aggregates",
    "joins",
    "ambiguous_names",
    "unsupported_requests",
}
SUPPORT_EXPECTATIONS = {"supported", "ambiguous", "unsupported", "unavailable"}
FAILURE_CLASSES = {
    "question_interpretation",
    "schema_grounding",
    "entity_resolution",
    "temporal_interpretation",
    "query_planning",
    "source_selection",
    "sparql_generation",
    "query_safety_validation",
    "execution",
    "source_data_coverage",
    "external_reconciliation_join",
    "remote_source_failure",
    "result_provenance_composition",
    "semantic_result_mismatch",
}
_INTEGER = re.compile(r"^[+-]?\d+$")


class BenchmarkFormatError(ValueError):
    """The versioned benchmark document does not conform to its format."""


@dataclass(frozen=True)
class SemanticScore:
    passed: bool
    reason: str


@dataclass(frozen=True)
class CoverageAssessment:
    state: str
    reason: str | None = None
    failed_prerequisite: str | None = None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchmarkFormatError(message)


def _validate_result_invariant(value: Any, where: str) -> None:
    _require(isinstance(value, dict), f"{where} must be an object")
    kind = value.get("kind")
    _require(kind in {"select", "ask"}, f"{where}.kind must be 'select' or 'ask'")
    if kind == "ask":
        _require(isinstance(value.get("boolean"), bool), f"{where}.boolean must be boolean")
        _require(set(value) == {"kind", "boolean"}, f"{where} has unsupported ASK fields")
        return

    _require(set(value) == {"kind", "invariants"}, f"{where} requires kind and invariants")
    invariants = value["invariants"]
    _require(isinstance(invariants, dict), f"{where}.invariants must be an object")
    allowed = {
        "row_count", "min_rows", "max_rows", "contains_values", "contains_text",
        "required_rows", "positive_integer_each_row", "integer_scalar", "empty",
    }
    _require(not (set(invariants) - allowed), f"{where}.invariants has unknown keys")
    for field in ("row_count", "min_rows", "max_rows"):
        if field in invariants:
            _require(type(invariants[field]) is int and invariants[field] >= 0,
                     f"{where}.invariants.{field} must be a non-negative integer")
    for field in ("contains_values", "contains_text"):
        if field in invariants:
            _require(isinstance(invariants[field], list)
                     and all(isinstance(item, str) and item for item in invariants[field]),
                     f"{where}.invariants.{field} must be a list of non-empty strings")
    if "required_rows" in invariants:
        _require(isinstance(invariants["required_rows"], list)
                 and all(isinstance(row, list) and row
                         and all(isinstance(item, str) and item for item in row)
                         for row in invariants["required_rows"]),
                 f"{where}.invariants.required_rows must be non-empty string rows")
    for field in ("positive_integer_each_row", "integer_scalar", "empty"):
        if field in invariants:
            _require(type(invariants[field]) is bool,
                     f"{where}.invariants.{field} must be boolean")


def _validate_case(case: Any, index: int) -> None:
    where = f"cases[{index}]"
    _require(isinstance(case, dict), f"{where} must be an object")
    required = {
        "id", "question", "category", "tiers", "support_expectation",
        "expected_interpretation", "expected_result", "evaluation_mode",
        "dataset_prerequisites",
    }
    allowed = required | {"failure_classes_on_mismatch", "regression_translation"}
    _require(required <= set(case), f"{where} is missing required fields")
    _require(not (set(case) - allowed), f"{where} has unknown fields")
    for field in ("id", "question", "category", "expected_interpretation"):
        _require(isinstance(case[field], str) and case[field].strip(),
                 f"{where}.{field} must be a non-empty string")
    _require(case["category"] in CATEGORIES, f"{where}.category is invalid")
    _require(isinstance(case["tiers"], list) and case["tiers"]
             and all(tier in {"regression", "measured"} for tier in case["tiers"])
             and len(set(case["tiers"])) == len(case["tiers"]),
             f"{where}.tiers must contain unique regression/measured values")
    _require(case["support_expectation"] in SUPPORT_EXPECTATIONS,
             f"{where}.support_expectation is invalid")
    expectation = case["support_expectation"]
    _require(case["evaluation_mode"] in {
        "semantic_invariants", "manual_review", "ambiguity_handling",
    },
             f"{where}.evaluation_mode is invalid")
    if expectation == "supported":
        if case["evaluation_mode"] == "semantic_invariants":
            _require(case["expected_result"] is not None,
                     f"{where} scored supported cases need an expected_result")
            _validate_result_invariant(case["expected_result"], f"{where}.expected_result")
        else:
            _require(case["evaluation_mode"] == "manual_review"
                     and case["expected_result"] is None,
                     f"{where} supported manual-review cases cannot assert result facts")
    elif expectation == "ambiguous":
        _require(case["expected_result"] is None,
                 f"{where} ambiguous cases cannot assert answer-result facts")
        if case["evaluation_mode"] == "ambiguity_handling":
            prerequisites = case.get("dataset_prerequisites", {})
            _require(isinstance(prerequisites, dict)
                     and case["category"] == "ambiguous_names"
                     and isinstance(prerequisites.get("required_graph_families"), list)
                     and "members" in prerequisites.get("required_graph_families", [])
                     and isinstance(prerequisites.get("coverage_probes"), list)
                     and any(
                         isinstance(probe, dict)
                         and isinstance(probe.get("sparql"), str)
                         and re.search(
                             r"\bSELECT\s+DISTINCT\s+\?member\b",
                             probe["sparql"], re.IGNORECASE,
                         )
                         for probe in prerequisites.get("coverage_probes", [])
                     ),
                     f"{where} ambiguity-handling cases need capture-backed Member coverage")
        else:
            _require(case["evaluation_mode"] == "manual_review",
                     f"{where} ambiguous cases need ambiguity_handling or manual_review")
    else:
        _require(case["evaluation_mode"] == "manual_review",
                 f"{where} non-supported cases must use manual_review")
        _require(case["expected_result"] is None,
                 f"{where} manual-review cases cannot assert result facts")

    prerequisites = case["dataset_prerequisites"]
    _require(isinstance(prerequisites, dict), f"{where}.dataset_prerequisites must be an object")
    _require(set(prerequisites) == {
        "required_graph_families", "required_resources", "coverage_probes", "unavailable_if",
    }, f"{where}.dataset_prerequisites has missing or unknown fields")
    families = prerequisites["required_graph_families"]
    _require(isinstance(families, list) and all(item in GRAPH_FAMILIES for item in families)
             and len(set(families)) == len(families),
             f"{where}.dataset_prerequisites.required_graph_families is invalid")
    resources = prerequisites["required_resources"]
    _require(isinstance(resources, list), f"{where}.dataset_prerequisites.required_resources must be a list")
    for resource in resources:
        _require(isinstance(resource, dict) and set(resource) == {"iri", "graph_family"}
                 and isinstance(resource["iri"], str) and resource["iri"].startswith("https://")
                 and resource["graph_family"] in GRAPH_FAMILIES,
                 f"{where} has an invalid required resource")
    probes = prerequisites["coverage_probes"]
    _require(isinstance(probes, list), f"{where}.dataset_prerequisites.coverage_probes must be a list")
    for probe_index, probe in enumerate(probes):
        _require(isinstance(probe, dict) and set(probe) == {"sparql", "expected_result"}
                 and isinstance(probe["sparql"], str) and probe["sparql"].strip(),
                 f"{where} coverage_probes[{probe_index}] is invalid")
        _validate_result_invariant(probe["expected_result"],
                                   f"{where}.coverage_probes[{probe_index}].expected_result")

    unavailable_if = prerequisites["unavailable_if"]
    if unavailable_if is not None:
        _require(isinstance(unavailable_if, dict), f"{where}.unavailable_if must be an object or null")
        if unavailable_if.get("kind") == "quarantined_resource":
            _require(set(unavailable_if) == {"kind", "iri"}
                     and isinstance(unavailable_if["iri"], str),
                     f"{where}.unavailable_if quarantined_resource is invalid")
        elif unavailable_if.get("kind") == "missing_graph_family":
            _require(set(unavailable_if) == {"kind", "graph_family"}
                     and unavailable_if["graph_family"] in GRAPH_FAMILIES,
                     f"{where}.unavailable_if missing_graph_family is invalid")
        else:
            raise BenchmarkFormatError(f"{where}.unavailable_if.kind is invalid")
    if expectation == "unavailable":
        _require(unavailable_if is not None,
                 f"{where} unavailable cases need an unavailable_if condition")

    if "failure_classes_on_mismatch" in case:
        classes = case["failure_classes_on_mismatch"]
        _require(isinstance(classes, list) and all(item in FAILURE_CLASSES for item in classes),
                 f"{where}.failure_classes_on_mismatch is invalid")
    if "regression" in case["tiers"]:
        translation = case.get("regression_translation")
        _require(isinstance(translation, dict)
                 and set(translation) == {"interpretation", "sparql"}
                 and all(isinstance(translation[key], str) and translation[key].strip()
                         for key in ("interpretation", "sparql")),
                 f"{where} regression cases need a deterministic regression_translation")
    else:
        _require("regression_translation" not in case,
                 f"{where} measured-only cases cannot include regression_translation")


def load_benchmark(path: str | Path = DEFAULT_BENCHMARK_PATH) -> dict:
    """Load and validate one supported version of the benchmark JSON."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkFormatError(f"could not read benchmark JSON: {error}") from error
    _require(isinstance(document, dict), "benchmark document must be an object")
    _require(set(document) == {"schema_version", "benchmark_id", "benchmark_version", "cases"},
             "benchmark document has missing or unknown top-level fields")
    _require(document["schema_version"] == BENCHMARK_SCHEMA_VERSION,
             f"unsupported benchmark schema_version {document['schema_version']!r}")
    _require(isinstance(document["benchmark_id"], str) and document["benchmark_id"],
             "benchmark_id must be a non-empty string")
    _require(isinstance(document["benchmark_version"], str) and document["benchmark_version"],
             "benchmark_version must be a non-empty string")
    _require(isinstance(document["cases"], list) and document["cases"],
             "benchmark cases must be a non-empty list")
    _require(30 <= len(document["cases"]) <= 50,
             "benchmark must contain between 30 and 50 cases")
    seen = set()
    for index, case in enumerate(document["cases"]):
        _validate_case(case, index)
        _require(case["id"] not in seen, f"duplicate benchmark case id {case['id']!r}")
        seen.add(case["id"])
    return document


def _lexical_rows(result: QueryResult) -> tuple[tuple[str, ...], ...]:
    """Return RDF lexical values, ignoring binding variable names and RDF hints."""
    if result.raw_json:
        try:
            payload = json.loads(result.raw_json)
            bindings = payload.get("results", {}).get("bindings")
            if isinstance(bindings, list):
                rows = []
                for binding_row in bindings:
                    if isinstance(binding_row, dict):
                        rows.append(tuple(
                            str(binding["value"])
                            for binding in binding_row.values()
                            if isinstance(binding, dict) and isinstance(binding.get("value"), str)
                        ))
                return tuple(rows)
        except (json.JSONDecodeError, AttributeError):
            pass
    return tuple(tuple(row) for row in result.rows)


def score_semantic_result(expected: dict, actual: QueryResult) -> SemanticScore:
    """Compare result meaning/invariants, never generated SPARQL text."""
    if expected.get("kind") != actual.kind:
        return SemanticScore(False, f"expected {expected.get('kind')} result, received {actual.kind}")
    if actual.kind == "ask":
        passed = actual.boolean is expected["boolean"]
        return SemanticScore(passed, "ASK boolean matched" if passed else
                             f"expected ASK {expected['boolean']}, received {actual.boolean}")

    rows = _lexical_rows(actual)
    invariants = expected["invariants"]
    count = len(actual.rows)
    if "row_count" in invariants and count != invariants["row_count"]:
        return SemanticScore(False, f"expected {invariants['row_count']} rows, received {count}")
    if "min_rows" in invariants and count < invariants["min_rows"]:
        return SemanticScore(False, f"expected at least {invariants['min_rows']} rows, received {count}")
    if "max_rows" in invariants and count > invariants["max_rows"]:
        return SemanticScore(False, f"expected at most {invariants['max_rows']} rows, received {count}")
    if "empty" in invariants and bool(rows) is not invariants["empty"]:
        expected_text = "empty" if invariants["empty"] else "non-empty"
        return SemanticScore(False, f"expected a {expected_text} result")

    flat_values = {value for row in rows for value in row}
    missing_values = [value for value in invariants.get("contains_values", [])
                      if value not in flat_values]
    if missing_values:
        return SemanticScore(False, f"required semantic values were absent: {missing_values}")
    missing_text = [fragment for fragment in invariants.get("contains_text", [])
                    if not any(fragment in value for value in flat_values)]
    if missing_text:
        return SemanticScore(False, f"required semantic text was absent: {missing_text}")
    for required_row in invariants.get("required_rows", []):
        if not any(set(required_row) <= set(row) for row in rows):
            return SemanticScore(False, f"required row values were not co-present: {required_row}")
    if invariants.get("positive_integer_each_row"):
        if not rows or any(not any(_INTEGER.fullmatch(value) and int(value) > 0 for value in row)
                           for row in rows):
            return SemanticScore(False, "every result row must contain a positive integer")
    if invariants.get("integer_scalar"):
        scalar_values = [value for row in rows for value in row
                         if _INTEGER.fullmatch(value)]
        if len(rows) != 1 or len(rows[0]) != 1 or len(scalar_values) != 1:
            return SemanticScore(False, "expected one row containing one integer scalar")
    return SemanticScore(True, "all semantic result invariants matched")


def _baseline_family_counts(baseline: dict) -> dict[str, int]:
    counts = baseline.get("rdf_resource_counts", {})
    return {
        "houses": int(counts.get("house_terms", 0)),
        "parties": int(counts.get("party_owner_identities", 0)),
        "constituencies": int(counts.get("constituency_panel_owner_identities", 0)),
        "committees": int(counts.get("committee_owner_identities", 0)),
        "members": int(counts.get("members", 0)),
        # Phase 0A's development bootstrap deliberately does not load Bills.
        "bills": 0,
        # Debates are likewise outside the Phase 0A NLQ bootstrap dataset.
        "debates": 0,
    }


def _baseline_quarantined_iris(baseline: dict) -> set[str]:
    return {
        item.get("canonical_iri")
        for item in baseline.get("quarantined_conflicted_identities", [])
        if isinstance(item, dict) and isinstance(item.get("canonical_iri"), str)
    }


def _baseline_unresolved_iris(baseline: dict) -> set[str]:
    return {
        item.get("canonical_iri")
        for item in baseline.get("unresolved_references", [])
        if isinstance(item, dict) and isinstance(item.get("canonical_iri"), str)
    }


def _unavailable_condition(case: dict, baseline: dict) -> tuple[bool, str | None]:
    condition = case["dataset_prerequisites"]["unavailable_if"]
    if condition is None:
        return False, None
    kind = condition["kind"]
    if kind == "missing_graph_family":
        family = condition["graph_family"]
        unavailable = _baseline_family_counts(baseline).get(family, 0) == 0
        return unavailable, f"required graph family '{family}' is absent from the Phase 0A dataset baseline"
    iri = condition["iri"]
    unavailable = iri in (_baseline_quarantined_iris(baseline) | _baseline_unresolved_iris(baseline))
    return unavailable, f"required resource is quarantined or unresolved: {iri}"


def assess_dataset_prerequisites(
    case: dict,
    baseline: dict,
    *,
    fuseki,
    supported_predicates,
) -> CoverageAssessment:
    """Use Phase 0A baseline metadata and curated probes before NLQ scoring."""
    condition_met, condition_reason = _unavailable_condition(case, baseline)
    if condition_met:
        return CoverageAssessment("unavailable", condition_reason, "source_data_coverage")

    if case["support_expectation"] == "unavailable":
        return CoverageAssessment(
            "condition_changed",
            "the benchmark's documented missing/quarantined-data condition is no longer present",
            "source_data_coverage",
        )

    family_counts = _baseline_family_counts(baseline)
    loaded_families = {
        item.get("name") for item in baseline.get("graph_families_loaded", [])
        if isinstance(item, dict)
    }
    for family in case["dataset_prerequisites"]["required_graph_families"]:
        if family not in loaded_families or family_counts.get(family, 0) == 0:
            return CoverageAssessment(
                "unavailable", f"required graph family '{family}' has no loaded resources",
                "source_data_coverage",
            )

    missing_iris = (_baseline_quarantined_iris(baseline)
                    | _baseline_unresolved_iris(baseline))
    for resource in case["dataset_prerequisites"]["required_resources"]:
        if resource["iri"] in missing_iris:
            return CoverageAssessment(
                "unavailable", f"required resource is quarantined or unresolved: {resource['iri']}",
                "source_data_coverage",
            )

    for probe_index, probe in enumerate(case["dataset_prerequisites"]["coverage_probes"]):
        checked_probe = validate_sparql(
            probe["sparql"], supported_predicates=supported_predicates
        )
        actual = fuseki.query(checked_probe)
        score = score_semantic_result(probe["expected_result"], actual)
        if not score.passed:
            return CoverageAssessment(
                "unavailable",
                f"source-data coverage probe {probe_index + 1} was not satisfied: {score.reason}",
                "source_data_coverage",
            )
    return CoverageAssessment("available")


def _failure_for_phase(phase: str | None, error: NLQError | Exception) -> str:
    if phase == "LLM translation":
        message = str(error).lower()
        if any(fragment in message for fragment in (
                "timed out", "could not be reached", "http 401", "http 429", "http 5")):
            return "execution"
        return "question_interpretation"
    if phase == "SPARQL validation":
        message = str(error).lower()
        return "sparql_generation" if "malformed" in message else "query_safety_validation"
    if phase == "Fuseki query":
        return "execution"
    return "execution"


def _serialize_result(result: QueryResult | None) -> dict | None:
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


def _serialize_ambiguity(ambiguity) -> dict | None:
    return ambiguity.as_dict() if ambiguity is not None else None


def _fixture_translator(case: dict):
    from .llm import Translation

    class FixtureTranslator:
        def translate(self, _question: str, _schema: str) -> Translation:
            fixture = case["regression_translation"]
            return Translation(fixture["interpretation"], fixture["sparql"])

        def close(self) -> None:
            pass

    return FixtureTranslator()


def run_cases(
    benchmark: dict,
    dataset_baseline: dict,
    *,
    fuseki,
    tier: str,
    repository_root: Path,
    translator_factory: Callable[[dict], object] | None = None,
) -> list[dict]:
    """Evaluate selected cases using the same query-processing boundary as UI."""
    if tier not in {"regression", "measured"}:
        raise ValueError("tier must be 'regression' or 'measured'")
    dataset = dataset_baseline.get("dataset")
    if (dataset_baseline.get("schema_version") != 1 or not isinstance(dataset, dict)
            or not isinstance(dataset.get("id"), str) or not dataset["id"].startswith("sha256:")):
        raise ValueError("benchmark requires a valid Phase 0A dataset baseline JSON")

    from .schema import build_schema_context
    from .vocabulary import supported_predicates as load_supported_predicates

    schema_context = build_schema_context(repository_root / "ontology")
    predicate_vocabulary = load_supported_predicates(repository_root / "ontology")
    outcomes: list[dict] = []
    for case in benchmark["cases"]:
        if tier == "regression" and "regression" not in case["tiers"]:
            continue
        if tier == "measured" and "measured" not in case["tiers"]:
            continue

        record = {
            "case_id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "support_expectation": case["support_expectation"],
            "expected_interpretation": case["expected_interpretation"],
            "expected_result": case["expected_result"],
            "evaluation_mode": case["evaluation_mode"],
            "observed_outcome": "not_run",
            "model_interpretation": None,
            "generated_sparql": None,
            "validated_sparql": None,
            "execution_result": None,
            "ambiguity_outcome": None,
            "evaluation": "not_scored",
            "passed": None,
            "failure_class": None,
            "diagnostic_candidates": [],
            "failure_reason": None,
            "coverage": None,
        }
        try:
            coverage = assess_dataset_prerequisites(
                case, dataset_baseline, fuseki=fuseki,
                supported_predicates=predicate_vocabulary,
            )
        except Exception as error:
            record.update(
                evaluation="coverage_unverified",
                observed_outcome="coverage_unverified",
                failure_class="execution",
                failure_reason=f"coverage prerequisite execution failed: {error}",
                coverage={"state": "unverified"},
            )
            outcomes.append(record)
            continue
        record["coverage"] = {"state": coverage.state, "reason": coverage.reason}
        if coverage.state == "unavailable":
            record.update(
                evaluation="coverage_unavailable",
                observed_outcome="unavailable",
                failure_class="source_data_coverage",
                failure_reason=coverage.reason,
            )
            outcomes.append(record)
            continue

        if case["evaluation_mode"] == "ambiguity_handling":
            class LocalOnlyTranslator:
                def translate(self, _question: str, _schema: str):
                    raise AssertionError(
                        "capture-backed local ambiguity must stop before translation"
                    )

                def close(self) -> None:
                    pass

            selected_translator_factory = lambda _case: LocalOnlyTranslator()
        elif tier == "regression":
            selected_translator_factory = translator_factory or _fixture_translator
        else:
            if translator_factory is None:
                from .llm import ResponsesTranslator
                import os

                selected_translator_factory = lambda _case: ResponsesTranslator(
                    os.getenv("NLQ_LLM_API_KEY", ""),
                    os.getenv("NLQ_LLM_BASE_URL", "https://opencode.ai/inference/openai/v1"),
                    os.getenv("NLQ_LLM_MODEL", "gpt-6-luna"),
                )
            else:
                selected_translator_factory = translator_factory

        translator = None
        current_phase = "LLM translation"

        def set_current_phase(phase: str) -> None:
            nonlocal current_phase
            current_phase = phase

        try:
            translator = selected_translator_factory(case)
            outcome = process_question(
                case["question"], translator=translator,
                fuseki_factory=lambda: fuseki,
                schema_context=schema_context,
                supported_predicates=predicate_vocabulary,
                on_phase=set_current_phase,
            )
        except Exception as error:
            scored_mode = case["evaluation_mode"] in {
                "semantic_invariants", "ambiguity_handling",
            }
            record.update(
                evaluation="failed" if scored_mode
                else "manual_review",
                observed_outcome=(
                    "translation_failed" if current_phase == "LLM translation" else
                    "query_rejected" if current_phase == "SPARQL validation" else
                    "execution_failed"
                ),
                passed=False if scored_mode else None,
                failure_class=_failure_for_phase(current_phase, error),
                failure_reason=str(error),
            )
            outcomes.append(record)
            continue
        finally:
            if translator is not None and hasattr(translator, "close"):
                translator.close()

        record["model_interpretation"] = (
            outcome.translation.interpretation if outcome.translation else None
        )
        record["generated_sparql"] = (
            outcome.translation.sparql if outcome.translation else None
        )
        record["validated_sparql"] = outcome.validated_sparql
        record["execution_result"] = _serialize_result(outcome.result)
        record["ambiguity_outcome"] = _serialize_ambiguity(outcome.ambiguity)
        if outcome.error is not None:
            record["observed_outcome"] = (
                "translation_failed" if outcome.error_phase == "LLM translation" else
                "query_rejected" if outcome.error_phase == "SPARQL validation" else
                "execution_failed"
            )
            record["failure_reason"] = str(outcome.error)
            record["failure_class"] = _failure_for_phase(outcome.error_phase, outcome.error)
            record["error_debug"] = outcome.error.debug_output
            record["error_debug_source"] = outcome.error.debug_source
            if case["evaluation_mode"] in {"semantic_invariants", "ambiguity_handling"}:
                record.update(evaluation="failed", passed=False)
            else:
                record["evaluation"] = "manual_review"
        elif outcome.ambiguity is not None:
            record["observed_outcome"] = "ambiguous_member_reference"
            if case["evaluation_mode"] == "ambiguity_handling":
                candidate_iris = {
                    candidate.member_iri
                    for candidate in outcome.ambiguity.candidates
                }
                minimum_candidates = 2
                for probe in case["dataset_prerequisites"]["coverage_probes"]:
                    if re.search(r"\bSELECT\s+DISTINCT\s+\?member\b", probe["sparql"], re.IGNORECASE):
                        invariants = probe["expected_result"].get("invariants", {})
                        minimum_candidates = max(
                            minimum_candidates,
                            invariants.get("min_rows", invariants.get("row_count", 0)),
                        )
                question_has_reference = (
                    outcome.ambiguity.entity_reference.casefold()
                    in case["question"].casefold()
                )
                passed = bool(
                    question_has_reference and len(candidate_iris) >= minimum_candidates
                )
                record.update(
                    evaluation="passed" if passed else "failed",
                    passed=passed,
                    score_reason=(
                        f"local Member ambiguity detected with at least {minimum_candidates} "
                        "distinct capture-backed resources"
                        if passed else (
                            "ambiguity outcome did not preserve the expected distinct candidates "
                            f"(expected at least {minimum_candidates}, received {len(candidate_iris)})"
                        )
                    ),
                )
                if not passed:
                    record["failure_class"] = "entity_resolution"
                    record["failure_reason"] = record["score_reason"]
            elif case["evaluation_mode"] == "semantic_invariants":
                record.update(
                    evaluation="failed",
                    passed=False,
                    failure_class="entity_resolution",
                    failure_reason="The question resolved to an ambiguous local Member reference.",
                )
            else:
                record["evaluation"] = "manual_review"
        elif case["evaluation_mode"] == "semantic_invariants":
            record["observed_outcome"] = "query_result"
            score = score_semantic_result(case["expected_result"], outcome.result)
            record["score_reason"] = score.reason
            record["passed"] = score.passed
            record["evaluation"] = "passed" if score.passed else "failed"
            if not score.passed:
                record["failure_class"] = "semantic_result_mismatch"
                record["diagnostic_candidates"] = case.get(
                    "failure_classes_on_mismatch", []
                )
                record["failure_reason"] = score.reason
        elif case["evaluation_mode"] == "ambiguity_handling":
            record.update(
                observed_outcome="query_result",
                evaluation="failed",
                passed=False,
                failure_class="entity_resolution",
                failure_reason=(
                    "Expected local Member ambiguity, but the shared pipeline continued "
                    "to an answer query."
                ),
            )
        else:
            record["observed_outcome"] = "query_result"
            record["evaluation"] = "manual_review"
        outcomes.append(record)
    return outcomes


def dataset_association(baseline: dict, isolation: dict) -> dict:
    """Preserve both Phase 0A capture identity and this disposable instance."""
    dataset = baseline.get("dataset")
    if baseline.get("schema_version") != 1 or not isinstance(dataset, dict):
        raise ValueError("benchmark requires a valid Phase 0A dataset baseline JSON")
    return {
        "dataset_id": dataset.get("id"),
        "dataset_baseline_schema_version": baseline["schema_version"],
        "dataset_baseline": baseline,
        "isolation": isolation,
    }


def summarize_results(case_results: list[dict]) -> dict:
    """Aggregate concise category and failure-class counts for one run."""
    categories: dict[str, Counter] = defaultdict(Counter)
    failures: Counter = Counter()
    for result in case_results:
        category = categories[result["category"]]
        category["total"] += 1
        category[result["evaluation"]] += 1
        if result.get("failure_class"):
            failures[result["failure_class"]] += 1
    return {
        "total_cases": len(case_results),
        "passed": sum(result["passed"] is True for result in case_results),
        "failed": sum(result["passed"] is False for result in case_results),
        "not_scored": sum(result["passed"] is None for result in case_results),
        "by_category": {
            name: dict(sorted(counts.items())) for name, counts in sorted(categories.items())
        },
        "by_failure_class": dict(sorted(failures.items())),
        "diagnostic_candidates": dict(sorted(Counter(
            candidate
            for result in case_results
            for candidate in result.get("diagnostic_candidates", [])
        ).items())),
    }
