from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess

import httpx
import pytest

from poc.nlq.benchmark import (
    BenchmarkFormatError,
    assess_dataset_prerequisites,
    dataset_association,
    load_benchmark,
    run_cases,
    score_semantic_result,
    summarize_results,
)
from poc.nlq import benchmark_isolation
from poc.nlq.llm import Translation
from poc.nlq import pipeline as pipeline_module
from poc.nlq.pipeline import process_question
from poc.nlq.results import QueryResult, parse_results


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "poc/nlq/benchmarks/benchmark-v1.json"


def _baseline(*, quarantined=(), unresolved=(), missing=()) -> dict:
    families = ("houses", "parties", "constituencies", "committees", "members")
    counts = {
        "house_terms": 2,
        "party_owner_identities": 2,
        "constituency_panel_owner_identities": 2,
        "committee_owner_identities": 2,
        "members": 3,
    }
    loaded = [{"name": family} for family in families if family not in missing]
    for family in missing:
        counts[{"houses": "house_terms", "parties": "party_owner_identities",
                "constituencies": "constituency_panel_owner_identities",
                "committees": "committee_owner_identities", "members": "members"}.get(
                    family, "")] = 0
    return {
        "schema_version": 1,
        "dataset": {
            "id": "sha256:" + "a" * 64,
            "authority": "non-authoritative development dataset",
            "authoritative_reference_closure_complete": False,
        },
        "graph_families_loaded": loaded,
        "rdf_resource_counts": counts,
        "quarantined_conflicted_identities": [
            {"canonical_iri": iri, "reason": "conflicting source observations"}
            for iri in quarantined
        ],
        "unresolved_references": [
            {"canonical_iri": iri, "reason": "owner description omitted"}
            for iri in unresolved
        ],
    }


class _FakeFuseki:
    def __init__(self):
        self.queries: list[str] = []

    def query(self, sparql: str) -> QueryResult:
        self.queries.append(sparql)
        if "ASK {" in sparql:
            return parse_results({"head": {}, "boolean": True})
        if "?termLabel" in sparql:
            value = "33rd Dáil"
        elif "foaf:name" in sparql and "Aengus" in sparql:
            value = "Aengus Ó Snodaigh"
        elif "foaf:name" in sparql and "Timmy" in sparql:
            value = "Timmy Dooley"
        elif "?collectionLabel" in sparql:
            value = "Fianna Fáil"
        elif "?panelLabel" in sparql:
            value = "Nominated by the Taoiseach"
        elif "?committeeLabel" in sparql:
            value = "Joint Committee on Transport and Communications"
        elif "?startDate" in sparql and "Timmy-Dooley" in sparql:
            value = "2020-06-29T00:00:00"
        elif "?startDate" in sparql:
            value = "2024-11-29T00:00:00"
        elif "COUNT(" in sparql:
            value = "19"
        else:
            value = "unexpected result"
        return parse_results({
            "head": {"vars": ["arbitrary_answer_variable"]},
            "results": {"bindings": [
                {"arbitrary_answer_variable": {"type": "literal", "value": value}},
            ]},
        })


def test_benchmark_json_is_versioned_and_contains_representative_categories():
    benchmark = load_benchmark(BENCHMARK_PATH)
    schema = json.loads((ROOT / "poc/specs/nlq-benchmark.schema.json").read_text())

    assert benchmark["schema_version"] == 1
    assert schema["properties"]["schema_version"] == {"const": 1}
    assert 30 <= len(benchmark["cases"]) <= 50
    assert len({case["id"] for case in benchmark["cases"]}) == len(benchmark["cases"])
    assert {case["category"] for case in benchmark["cases"]} == {
        "simple_lookup", "house_term_membership", "parliamentary_collections",
        "constituencies_panels", "committees", "dates_temporal",
        "counts_aggregates", "joins", "ambiguous_names", "unsupported_requests",
    }
    assert {case["support_expectation"] for case in benchmark["cases"]} == {
        "supported", "ambiguous", "unsupported", "unavailable",
    }
    assert sum("regression" in case["tiers"] for case in benchmark["cases"]) == 10


@pytest.mark.parametrize("mutation, message", [
    (lambda data: data.update(schema_version=2), "unsupported benchmark schema_version"),
    (lambda data: data["cases"].append(copy.deepcopy(data["cases"][0])), "duplicate benchmark case id"),
    (lambda data: data["cases"][0].update(support_expectation="mystery"), "support_expectation is invalid"),
    (lambda data: data.update(cases=data["cases"][:29]), "between 30 and 50"),
])
def test_benchmark_loader_rejects_invalid_or_incompatible_documents(
        tmp_path, mutation, message):
    benchmark = load_benchmark(BENCHMARK_PATH)
    mutation(benchmark)
    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(benchmark), encoding="utf-8")

    with pytest.raises(BenchmarkFormatError, match=message):
        load_benchmark(path)


def test_semantic_scoring_ignores_variable_names_and_binding_order():
    expected = {
        "kind": "select",
        "invariants": {
            "row_count": 1,
            "required_rows": [["Aengus Ó Snodaigh", "33rd Dáil"]],
        },
    }
    actual = parse_results({
        "head": {"vars": ["term_label", "member_label"]},
        "results": {"bindings": [{
            "term_label": {"type": "literal", "value": "33rd Dáil", "xml:lang": "en"},
            "member_label": {"type": "literal", "value": "Aengus Ó Snodaigh"},
        }]},
    })

    score = score_semantic_result(expected, actual)

    assert score.passed
    assert score.reason == "all semantic result invariants matched"


def test_semantic_scoring_checks_aggregate_and_ask_invariants():
    aggregate = parse_results({
        "head": {"vars": ["member_count"]},
        "results": {"bindings": [{
            "member_count": {
                "type": "literal", "value": "42",
                "datatype": "http://www.w3.org/2001/XMLSchema#integer",
            },
        }]},
    })
    assert score_semantic_result({
        "kind": "select", "invariants": {"row_count": 1, "integer_scalar": True},
    }, aggregate).passed
    assert not score_semantic_result(
        {"kind": "ask", "boolean": False}, parse_results({"head": {}, "boolean": True})
    ).passed


def test_phase_0a_quarantine_is_classified_as_coverage_not_an_nlq_failure():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = next(item for item in benchmark["cases"]
                if item["id"] == "committee.quarantined-good-friday")
    committee_iri = case["dataset_prerequisites"]["unavailable_if"]["iri"]
    fuseki = _FakeFuseki()

    assessment = assess_dataset_prerequisites(
        case, _baseline(quarantined=[committee_iri]), fuseki=fuseki,
        supported_predicates=frozenset(),
    )

    assert assessment.state == "unavailable"
    assert assessment.failed_prerequisite == "source_data_coverage"
    assert "quarantined or unresolved" in assessment.reason
    assert fuseki.queries == []


def test_absent_phase_0a_graph_family_is_classified_as_source_coverage():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = next(item for item in benchmark["cases"] if item["id"] == "unavailable.bill-status")
    assessment = assess_dataset_prerequisites(
        case, _baseline(missing=["bills"]), fuseki=_FakeFuseki(),
        supported_predicates=frozenset(),
    )
    assert assessment.state == "unavailable"
    assert assessment.failed_prerequisite == "source_data_coverage"
    assert "bills" in assessment.reason


def test_deterministic_regression_runs_shared_pipeline_without_an_llm():
    benchmark = load_benchmark(BENCHMARK_PATH)
    fuseki = _FakeFuseki()
    results = run_cases(
        benchmark, _baseline(), fuseki=fuseki, tier="regression",
        repository_root=ROOT,
    )

    assert len(results) == 10
    assert all(result["passed"] is True for result in results)
    assert all(result["model_interpretation"] for result in results)
    assert all(result["generated_sparql"] for result in results)
    assert all(result["execution_result"] for result in results)
    assert all(result["failure_class"] is None for result in results)
    assert len(fuseki.queries) > len(results)  # Each selected case also had a coverage probe.
    assert summarize_results(results)["passed"] == 10


def test_known_unavailable_case_does_not_invoke_translation():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = next(item for item in benchmark["cases"]
                if item["id"] == "committee.quarantined-good-friday")
    committee_iri = case["dataset_prerequisites"]["unavailable_if"]["iri"]
    single_case = {**benchmark, "cases": [case]}

    def forbidden_translator(_case):
        raise AssertionError("coverage-unavailable cases must not be sent to the NLQ pipeline")

    result = run_cases(
        single_case, _baseline(quarantined=[committee_iri]), fuseki=_FakeFuseki(),
        tier="measured", repository_root=ROOT,
        translator_factory=forbidden_translator,
    )[0]

    assert result["evaluation"] == "coverage_unavailable"
    assert result["passed"] is None
    assert result["failure_class"] == "source_data_coverage"
    assert result["generated_sparql"] is None


def test_result_mismatch_retains_failure_candidates_and_semantic_result():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = copy.deepcopy(next(item for item in benchmark["cases"]
                              if item["id"] == "lookup.aengus-name"))
    case["regression_translation"]["sparql"] = (
        "PREFIX foaf: <http://xmlns.com/foaf/0.1/> SELECT ?name WHERE { "
        "GRAPH <https://data.oireachtas.ie/graph/member/Aengus-Ó-Snodaigh.D.2002-06-06> { "
        "<https://data.oireachtas.ie/ie/oireachtas/member/id/Aengus-Ó-Snodaigh.D.2002-06-06> "
        "foaf:name ?name } } LIMIT 10"
    )
    single_case = {**benchmark, "cases": [case]}

    class WrongValueFuseki(_FakeFuseki):
        def query(self, sparql):
            if "ASK {" in sparql:
                return parse_results({"head": {}, "boolean": True})
            self.queries.append(sparql)
            return parse_results({"head": {"vars": ["x"]}, "results": {"bindings": [
                {"x": {"type": "literal", "value": "Not the expected person"}},
            ]}})

    result = run_cases(
        single_case, _baseline(), fuseki=WrongValueFuseki(), tier="regression",
        repository_root=ROOT,
    )[0]

    assert result["evaluation"] == "failed"
    assert result["failure_class"] == "semantic_result_mismatch"
    assert "entity_resolution" in result["diagnostic_candidates"]
    assert result["execution_result"]["rows"] == [["Not the expected person"]]


def test_benchmark_classifies_unsafe_generated_sparql_and_records_it():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = copy.deepcopy(next(item for item in benchmark["cases"]
                              if item["id"] == "lookup.aengus-name"))
    unsafe_query = (
        "SELECT ?x WHERE { SERVICE <http://example.test/sparql> "
        "{ ?x <urn:p> ?o } }"
    )
    single_case = {**benchmark, "cases": [case]}

    class UnsafeTranslator:
        def translate(self, _question, _schema):
            return Translation("Attempt an update", unsafe_query)

        def close(self):
            pass

    result = run_cases(
        single_case, _baseline(), fuseki=_FakeFuseki(), tier="regression",
        repository_root=ROOT, translator_factory=lambda _case: UnsafeTranslator(),
    )[0]

    assert result["evaluation"] == "failed"
    assert result["observed_outcome"] == "query_rejected"
    assert result["generated_sparql"] == unsafe_query
    assert result["execution_result"] is None
    assert result["failure_class"] == "query_safety_validation"


def test_pipeline_is_lazy_and_reports_controlled_validation_failure():
    phases = []

    class Translator:
        def translate(self, question, _schema):
            assert question == "question"
            return Translation("unsafe", "INSERT DATA { <urn:s> <urn:p> <urn:o> }")

    def forbidden_fuseki_factory():
        raise AssertionError("validation failure must not instantiate Fuseki")

    outcome = process_question(
        "question", translator=Translator(), fuseki_factory=forbidden_fuseki_factory,
        schema_context="schema", supported_predicates=frozenset(), on_phase=phases.append,
    )

    assert outcome.error is not None
    assert outcome.error_phase == "SPARQL validation"
    assert outcome.translation.interpretation == "unsafe"
    assert outcome.result is None
    assert phases == ["LLM translation", "SPARQL validation"]


def test_pipeline_publishes_translation_before_unexpected_later_failure(monkeypatch):
    translation = Translation("Find a member", "SELECT ?x WHERE { ?x <urn:p> ?o }")
    captured = []

    class Translator:
        def translate(self, _question, _schema):
            return translation

    def unexpected_validation_failure(*_args, **_kwargs):
        raise RuntimeError("unexpected local validator error")

    monkeypatch.setattr(pipeline_module, "validate_sparql", unexpected_validation_failure)
    with pytest.raises(RuntimeError, match="unexpected local validator error"):
        process_question(
            "question", translator=Translator(), fuseki_factory=lambda: None,
            schema_context="schema", supported_predicates=frozenset(),
            on_translation=captured.append,
        )
    assert captured == [translation]


def test_dataset_baseline_is_embedded_with_physical_instance_identity():
    baseline = _baseline()
    isolation = {
        "container_id": "container-123",
        "disposable": True,
        "persistent_volume_attached": False,
    }

    associated = dataset_association(baseline, isolation)

    assert associated["dataset_id"] == baseline["dataset"]["id"]
    assert associated["dataset_baseline_schema_version"] == 1
    assert associated["dataset_baseline"] == baseline
    assert associated["isolation"] == isolation


def test_runner_bootstraps_disposable_endpoint_and_reads_phase_0a_baseline(
        tmp_path, monkeypatch):
    module_spec = importlib.util.spec_from_file_location(
        "run_nlq_benchmark", ROOT / "scripts/run-nlq-benchmark.py",
    )
    runner_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner_module)
    baseline = _baseline()
    seen = {}

    def fake_run(command, *, cwd, env, capture_output, text):
        seen.update(command=command, cwd=cwd, env=env)
        assert capture_output and text
        output_path = Path(command[command.index("--dataset-baseline-output") + 1])
        output_path.write_text(json.dumps(baseline), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="bootstrapped", stderr="")

    monkeypatch.setattr(runner_module.subprocess, "run", fake_run)
    args = type("Args", (), {
        "uv": "uv", "raw_dir": tmp_path / "preserved-captures",
        "state_db": tmp_path / "core-state.sqlite",
    })()
    instance = type("Instance", (), {
        "gsp_url": "http://127.0.0.1:45678/houses/data",
        "query_url": "http://127.0.0.1:45678/houses/query",
        "password": "disposable-secret",
    })()

    actual = runner_module._run_bootstrap(
        args, instance, tmp_path / "phase-0a-baseline.json",
    )

    assert actual == baseline
    assert seen["command"][:5] == ["uv", "run", "--locked", "oir-etl", "dev"]
    assert "bootstrap" in seen["command"]
    assert "--raw-dir" in seen["command"]
    assert "--state-db" in seen["command"]
    assert "--dataset-baseline-output" in seen["command"]
    assert "http://127.0.0.1:45678/houses/data" in seen["command"]
    assert "http://127.0.0.1:45678/houses/query" in seen["command"]
    assert seen["env"]["OIR_FUSEKI_PASSWORD"] == "disposable-secret"


def test_disposable_fuseki_uses_loopback_random_port_and_no_persistent_storage(monkeypatch):
    docker_calls = []

    def docker_runner(command, **kwargs):
        docker_calls.append(command)
        if "run" in command:
            return subprocess.CompletedProcess(command, 0, stdout="container-123\n", stderr="")
        if "port" in command:
            return subprocess.CompletedProcess(command, 0, stdout="127.0.0.1:45678\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    class ReadyHttpClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def get(self, url):
            assert url == "http://127.0.0.1:45678/$/ping"
            return httpx.Response(200)

    monkeypatch.setattr(benchmark_isolation.httpx, "Client", ReadyHttpClient)
    instance = benchmark_isolation.DisposableFuseki(runner=docker_runner)
    with instance:
        assert instance.query_url == "http://127.0.0.1:45678/houses/query"
        assert instance.gsp_url == "http://127.0.0.1:45678/houses/data"
        metadata = instance.isolation_metadata()
        assert metadata["container_id"] == "container-123"
        assert metadata["disposable"] is True
        assert metadata["persistent_volume_attached"] is False

    run_command = docker_calls[0]
    assert "--rm" in run_command
    assert "--publish" in run_command
    assert "127.0.0.1::3030" in run_command
    assert "--env" in run_command and "FUSEKI_DATASET_1=houses" in run_command
    assert not ({"--volume", "-v", "--mount"} & set(run_command))
    assert any("stop" in command for command in docker_calls)
    assert any("rm" in command and "--force" in command for command in docker_calls)


def test_disposable_fuseki_rejects_non_loopback_published_ports(monkeypatch):
    docker_calls = []
    monotonic_ticks = iter((0.0, 0.0, 11.0))
    monkeypatch.setattr(benchmark_isolation.time, "monotonic", lambda: next(monotonic_ticks))
    monkeypatch.setattr(benchmark_isolation.time, "sleep", lambda _seconds: None)

    def docker_runner(command, **kwargs):
        docker_calls.append(command)
        if "run" in command:
            return subprocess.CompletedProcess(command, 0, stdout="container-456\n", stderr="")
        if "port" in command:
            return subprocess.CompletedProcess(command, 0, stdout="0.0.0.0:3030\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    instance = benchmark_isolation.DisposableFuseki(
        runner=docker_runner, timeout=10,
    )
    with pytest.raises(RuntimeError, match="outside the loopback"):
        instance.__enter__()
    assert any("rm" in command and "--force" in command for command in docker_calls)


def test_summary_reports_category_and_failure_class_counts():
    results = [
        {"category": "joins", "evaluation": "failed", "passed": False,
         "failure_class": "semantic_result_mismatch", "diagnostic_candidates": ["schema_grounding"]},
        {"category": "joins", "evaluation": "coverage_unavailable", "passed": None,
         "failure_class": "source_data_coverage", "diagnostic_candidates": []},
        {"category": "ambiguous_names", "evaluation": "manual_review", "passed": None,
         "failure_class": None, "diagnostic_candidates": []},
    ]

    summary = summarize_results(results)

    assert summary["total_cases"] == 3
    assert summary["failed"] == 1
    assert summary["not_scored"] == 2
    assert summary["by_category"]["joins"]["total"] == 2
    assert summary["by_failure_class"] == {
        "semantic_result_mismatch": 1, "source_data_coverage": 1,
    }
    assert summary["diagnostic_candidates"] == {"schema_grounding": 1}
