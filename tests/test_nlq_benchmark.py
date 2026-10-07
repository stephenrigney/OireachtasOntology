from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import httpx
import pytest
from jsonschema import Draft202012Validator

from poc.nlq.benchmark import (
    DEFAULT_BENCHMARK_PATH,
    BenchmarkFormatError,
    assess_dataset_prerequisites,
    dataset_association,
    load_benchmark,
    run_cases,
    score_semantic_result,
    summarize_results,
)
from poc.nlq import benchmark_isolation
from poc.nlq.config import resolved_llm_configuration
from poc.nlq.llm import Translation
from poc.nlq import pipeline as pipeline_module
from poc.nlq.pipeline import process_question
from poc.nlq.results import QueryResult, parse_results


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "poc/nlq/benchmarks/benchmark-v3.json"
PREVIOUS_BENCHMARK_PATH = ROOT / "poc/nlq/benchmarks/benchmark-v2.json"
HISTORICAL_BENCHMARK_PATH = ROOT / "poc/nlq/benchmarks/benchmark-v1.json"


def test_measured_translator_configuration_records_resolved_values_and_provenance(tmp_path):
    (tmp_path / ".env").write_text(
        "NLQ_LLM_MODEL=dotenv-model\n"
        "NLQ_LLM_BASE_URL=https://dotenv.example/v1/\n"
        "NLQ_LLM_API_KEY=dotenv-secret\n",
        encoding="utf-8",
    )

    dotenv_config = resolved_llm_configuration(tmp_path, process_environment={})
    assert dotenv_config == {
        "model": {"value": "dotenv-model", "source": "repository_dotenv"},
        "base_endpoint": {
            "value": "https://dotenv.example/v1", "source": "repository_dotenv",
        },
        "request_timeout_seconds": {"value": 45.0, "source": "default"},
        "max_output_tokens": {"value": 2000, "source": "default"},
    }
    defaults = tmp_path / "defaults"
    defaults.mkdir()
    default_config = resolved_llm_configuration(
        defaults, process_environment={"NLQ_LLM_API_KEY": "process-secret"},
    )
    assert default_config["model"] == {"value": "gpt-6-luna", "source": "default"}
    assert default_config["base_endpoint"] == {
        "value": "https://opencode.ai/inference/openai/v1", "source": "default",
    }

    override = resolved_llm_configuration(tmp_path, process_environment={
        "NLQ_LLM_MODEL": "override-model",
        "NLQ_LLM_BASE_URL": "https://url-secret@override.example/responses/?token=query-secret",
        "NLQ_LLM_API_KEY": "process-secret",
    })
    assert override["model"] == {
        "value": "override-model", "source": "process_environment",
    }
    assert override["base_endpoint"] == {
        "value": "https://override.example/responses", "source": "process_environment",
    }
    serialized = json.dumps([dotenv_config, default_config, override])
    assert "dotenv-secret" not in serialized
    assert "process-secret" not in serialized
    assert "url-secret" not in serialized
    assert "query-secret" not in serialized
    assert "API_KEY" not in serialized


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
        if "?question" in sparql and "foaf:name ?name" in sparql:
            return parse_results({
                "head": {"vars": ["member", "name", "memberCode"]},
                "results": {"bindings": []},
            })
        if "ASK {" in sparql:
            return parse_results({"head": {}, "boolean": True})
        if "?committeeLabel" in sparql and "26th Seanad" in sparql:
            return parse_results({
                "head": {"vars": ["committeeLabel"]},
                "results": {"bindings": [
                    {"committeeLabel": {"type": "literal", "value":
                     "Select Committee on Transport and Communications"}},
                    {"committeeLabel": {"type": "literal", "value":
                     "Select Committee on Environment and Climate Action"}},
                ]},
            })
        if "?collectionLabel" in sparql:
            value = "Fianna Fáil"
        elif "?panelLabel" in sparql:
            value = "Nominated by the Taoiseach"
        elif "?committeeLabel" in sparql:
            value = "Joint Committee on Transport and Communications"
        elif "?startDate" in sparql and "26th Seanad" in sparql:
            value = "2020-06-29T00:00:00"
        elif "?startDate" in sparql:
            value = "2024-11-29T00:00:00"
        elif "?termLabel" in sparql and '"Micheál Martin"' in sparql:
            labels = (
                "26th Dáil", "27th Dáil", "28th Dáil", "29th Dáil", "30th Dáil",
                "31st Dáil", "32nd Dáil", "33rd Dáil", "34th Dáil",
            )
            return parse_results({
                "head": {"vars": ["termLabel"]},
                "results": {"bindings": [
                    {"termLabel": {"type": "literal", "value": label}}
                    for label in labels
                ]},
            })
        elif ("?termLabel" in sparql and '"Timmy Dooley"' in sparql
              and "SeanadMembership" in sparql):
            return parse_results({
                "head": {"vars": ["termLabel"]},
                "results": {"bindings": [
                    {"termLabel": {"type": "literal", "value": label}}
                    for label in ("22nd Seanad", "26th Seanad")
                ]},
            })
        elif "?termLabel" in sparql:
            value = "33rd Dáil"
        elif "foaf:name" in sparql and "Aengus" in sparql:
            value = "Aengus Ó Snodaigh"
        elif "foaf:name" in sparql and "Timmy" in sparql:
            value = "Timmy Dooley"
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


class _CapturedAmbiguityFuseki(_FakeFuseki):
    """The exact duplicate names and context are copied from Phase 0A RDF."""

    MEMBERS = {
        "Michael Collins": (
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1919-01-21",
                "Michael-Collins.D.1919-01-21",
                ("1st Dáil", "2nd Dáil", "3rd Dáil"),
                ("Armagh", "Cork Mid, North, South, South East and West", "Cork South"),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.1997-06-26",
                "Michael-Collins.D.1997-06-26",
                ("28th Dáil", "29th Dáil"),
                ("Limerick West",),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Michael-Collins.D.2016-10-03",
                "Michael-Collins.D.2016-10-03",
                ("32nd Dáil", "33rd Dáil", "34th Dáil"),
                ("Cork South-West",),
            ),
        ),
        "Cathy Honan": (
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Cathy-Honan.S.1965-06-23",
                "Cathy-Honan.S.1965-06-23",
                ("11th Seanad", "12th Seanad"),
                ("Industrial and Commercial Panel",),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Cathy-Honan.S.1982-05-13",
                "Cathy-Honan.S.1982-05-13",
                ("16th Seanad",),
                ("Administrative Panel",),
            ),
            (
                "https://data.oireachtas.ie/ie/oireachtas/member/id/Cathy-Honan.S.1997-01-28",
                "Cathy-Honan.S.1997-01-28",
                ("20th Seanad",),
                ("Industrial and Commercial Panel",),
            ),
        ),
    }

    def query(self, sparql: str) -> QueryResult:
        self.queries.append(sparql)
        if "?question" in sparql and "foaf:name ?name" in sparql:
            label = next((name for name in self.MEMBERS if name in sparql), None)
            candidates = self.MEMBERS.get(label, ())
            return parse_results({
                "head": {"vars": ["member", "name", "memberCode"]},
                "results": {"bindings": [
                    {
                        "member": {"type": "uri", "value": iri},
                        "name": {"type": "literal", "value": label},
                        "memberCode": {"type": "literal", "value": code},
                    }
                    for iri, code, _terms, _representations in candidates
                ]},
            })
        if "VALUES ?member" in sparql:
            iri = next((candidate[0] for values in self.MEMBERS.values()
                        for candidate in values if f"<{candidate[0]}>" in sparql), None)
            candidate = next((candidate for values in self.MEMBERS.values()
                              for candidate in values if candidate[0] == iri), None)
            if candidate is None:
                raise AssertionError("unexpected local Member IRI in context query")
            terms, representations = candidate[2], candidate[3]
            rows = [
                {"contextType": {"type": "literal", "value": "house_term"},
                 "contextLabel": {"type": "literal", "xml:lang": "en", "value": label}}
                for label in terms
            ] + [
                {"contextType": {"type": "literal", "value": "representation"},
                 "contextLabel": {"type": "literal", "xml:lang": "en", "value": label}}
                for label in representations
            ]
            return parse_results({
                "head": {"vars": ["contextType", "contextLabel"]},
                "results": {"bindings": rows},
            })
        if "SELECT DISTINCT ?member WHERE" in sparql and 'foaf:name "Michael Collins"' in sparql:
            members = self.MEMBERS["Michael Collins"]
        elif "SELECT DISTINCT ?member WHERE" in sparql and 'foaf:name "Cathy Honan"' in sparql:
            members = self.MEMBERS["Cathy Honan"]
        else:
            return super().query(sparql)
        return parse_results({
            "head": {"vars": ["member"]},
            "results": {"bindings": [
                {"member": {"type": "uri", "value": candidate[0]}}
                for candidate in members
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


def test_benchmark_history_and_default_version_are_preserved():
    historical = load_benchmark(HISTORICAL_BENCHMARK_PATH)
    previous = load_benchmark(PREVIOUS_BENCHMARK_PATH)
    current = load_benchmark(BENCHMARK_PATH)

    assert historical["benchmark_version"] == "0.1.0"
    assert previous["benchmark_version"] == "0.2.0"
    assert current["benchmark_version"] == "0.3.0"
    assert DEFAULT_BENCHMARK_PATH == BENCHMARK_PATH
    assert hashlib.sha256(
        HISTORICAL_BENCHMARK_PATH.read_bytes()
    ).hexdigest() == "afaebc738c86e150e73d1bf997c2fe739df3e22226e566e4416508bdf48885c3"
    assert hashlib.sha256(
        PREVIOUS_BENCHMARK_PATH.read_bytes()
    ).hexdigest() == "f5a5b9d50d6a534360a727ebc73ae321142ace41404228e4e6b098cb67475692"


def test_benchmark_versions_validate_against_the_published_json_schema():
    schema = json.loads((ROOT / "poc/specs/nlq-benchmark.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    for path in (HISTORICAL_BENCHMARK_PATH, PREVIOUS_BENCHMARK_PATH, BENCHMARK_PATH):
        validator.validate(json.loads(path.read_text(encoding="utf-8")))


def test_v03_support_expectations_match_contract_scope_and_dataset_evidence():
    benchmark = load_benchmark(BENCHMARK_PATH)
    contract = json.loads((ROOT / "poc/specs/query-schema-contract.json").read_text())
    by_id = {case["id"]: case for case in benchmark["cases"]}

    assert "dct:temporal" not in contract["queryableProperties"]
    house_start = by_id["date.dail-34-start"]
    assert house_start["support_expectation"] == "unsupported"
    assert house_start["evaluation_mode"] == "manual_review"
    assert house_start["expected_result"] is None
    assert "regression" not in house_start["tiers"]
    interval_case = by_id["date.aengus-active-mid-2023"]
    assert interval_case["expected_result"]["kind"] == "select"
    assert interval_case["expected_result"]["invariants"]["required_rows"] == [[
        "2020-02-08T00:00:00", "2024-11-08T00:00:00",
    ]]
    assert "term.dail-34-start-date" not in by_id
    assert "term.micheal-dail-34-membership" in by_id
    assert "collection.enduring-party-unsupported" not in by_id
    assert by_id["collection.micheal-dail-34"]["support_expectation"] == "supported"

    for case in benchmark["cases"]:
        if "regression" in case["tiers"]:
            query = case["regression_translation"]["sparql"]
            assert "#term-period" not in query
            assert "dct:temporal" not in query
            assert "/ie/oireachtas/member/id/" not in query
            assert "/ie/oireachtas/house/" not in query
            assert "/graph/member/" not in query


def test_duplicate_name_cases_have_capture_backed_automated_ambiguity_assertions():
    benchmark = load_benchmark(BENCHMARK_PATH)
    by_id = {case["id"]: case for case in benchmark["cases"]}

    for case_id, minimum in (
        ("ambiguous.duplicate-michael-collins", 3),
        ("ambiguous.duplicate-cathy-honan", 3),
    ):
        case = by_id[case_id]
        assert case["support_expectation"] == "ambiguous"
        assert case["evaluation_mode"] == "ambiguity_handling"
        assert case["expected_result"] is None
        assert case["dataset_prerequisites"]["coverage_probes"]
        invariant = case["dataset_prerequisites"]["coverage_probes"][0]["expected_result"]["invariants"]
        assert invariant["min_rows"] >= minimum

    martin = by_id["ambiguous.martin"]
    assert martin["support_expectation"] == "supported"
    assert martin["evaluation_mode"] == "manual_review"
    assert martin["expected_result"] is None
    assert "set-valued" in martin["expected_interpretation"]


def test_aengus_coverage_uses_member_graph_discovery_not_unicode_graph_iri_literals():
    benchmark = load_benchmark(BENCHMARK_PATH)
    selected = {
        "lookup.aengus-name", "term.aengus-dail-33", "collection.aengus-dail-33",
        "date.aengus-active-mid-2023", "join.aengus-dail-33-collection",
        "join.aengus-dail-33-constituency",
    }
    for case in benchmark["cases"]:
        if case["id"] not in selected:
            continue
        for probe in case["dataset_prerequisites"]["coverage_probes"]:
            assert "GRAPH ?memberGraph" in probe["sparql"]
            assert "Aengus Ó Snodaigh" in probe["sparql"]
            assert "GRAPH <https://data.oireachtas.ie/graph/member/Aengus" not in probe["sparql"]


def test_committee_cases_follow_member_committee_owner_join_in_contract():
    benchmark = load_benchmark(BENCHMARK_PATH)
    by_id = {case["id"]: case for case in benchmark["cases"]}
    expected_labels = {
        "Select Committee on Transport and Communications",
        "Select Committee on Environment and Climate Action",
    }
    for case_id in (
        "committee.timmy-transport-committee", "committee.timmy-committee-count",
        "join.timmy-committee-owner",
    ):
        case = by_id[case_id]
        assert "26th Seanad" in case["expected_interpretation"]
        probes = "\n".join(
            probe["sparql"]
            for probe in case["dataset_prerequisites"]["coverage_probes"]
        )
        assert "members:CommitteeMembership" in probes
        assert "members:isCommitteeMembershipOf" in probes
        assert "members:committeeInHouseTerm" in probes
        if case_id != "committee.timmy-committee-count":
            assert all(label in probes for label in expected_labels)
        else:
            assert case["expected_result"]["invariants"]["contains_values"] == ["2"]
        assert "/member/id/Timmy-Dooley.S.2002-09-12/house/seanad/26" not in probes


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


def test_date_range_semantics_match_selected_values_without_rdf_datatype_suffixes():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = next(item for item in benchmark["cases"]
                if item["id"] == "date.aengus-active-mid-2023")
    actual = parse_results({
        "head": {"vars": ["startDate", "endDate"]},
        "results": {"bindings": [{
            "startDate": {
                "type": "literal", "value": "2020-02-08T00:00:00",
                "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
            },
            "endDate": {
                "type": "literal", "value": "2024-11-08T00:00:00",
                "datatype": "http://www.w3.org/2001/XMLSchema#dateTime",
            },
        }]},
    })

    assert score_semantic_result(case["expected_result"], actual).passed


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


@pytest.mark.parametrize("case_id", [
    "ambiguous.duplicate-michael-collins",
    "ambiguous.duplicate-cathy-honan",
])
def test_benchmark_scores_capture_backed_ambiguity_through_shared_pipeline(case_id):
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = next(item for item in benchmark["cases"] if item["id"] == case_id)
    fuseki = _CapturedAmbiguityFuseki()

    result = run_cases(
        {**benchmark, "cases": [case]},
        _baseline(),
        fuseki=fuseki,
        tier="measured",
        repository_root=ROOT,
        translator_factory=lambda _case: (_ for _ in ()).throw(
            AssertionError("ambiguity cases must stop before translation")
        ),
    )[0]

    assert result["evaluation"] == "passed"
    assert result["passed"] is True
    assert result["observed_outcome"] == "ambiguous_member_reference"
    assert result["generated_sparql"] is None
    assert result["execution_result"] is None
    ambiguity = result["ambiguity_outcome"]
    assert ambiguity["status"] == "ambiguous"
    assert ambiguity["candidate_count"] == 3
    assert len({candidate["member_iri"] for candidate in ambiguity["candidates"]}) == 3
    assert all(candidate["house_terms"] for candidate in ambiguity["candidates"])


def test_benchmark_pipeline_completes_missing_prefix_before_shared_validation():
    benchmark = load_benchmark(BENCHMARK_PATH)
    case = next(item for item in benchmark["cases"] if item["id"] == "lookup.aengus-name")
    single_case = {**benchmark, "cases": [case]}
    translation = Translation(
        "Find the exact Member name.",
        'SELECT ?name WHERE { GRAPH ?memberGraph { ?member foaf:name ?name . '
        'FILTER(?name = "Aengus Ó Snodaigh") } } LIMIT 10',
    )

    class MissingPrefixTranslator:
        def translate(self, _question, _schema):
            return translation

        def close(self):
            pass

    fuseki = _FakeFuseki()
    result = run_cases(
        single_case, _baseline(), fuseki=fuseki, tier="measured",
        repository_root=ROOT, translator_factory=lambda _case: MissingPrefixTranslator(),
    )[0]

    assert result["evaluation"] == "passed"
    assert result["generated_sparql"] == translation.sparql
    assert result["validated_sparql"].startswith(
        "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
    )
    assert fuseki.queries[-1] == result["validated_sparql"]


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
            if "?question" in sparql and "foaf:name ?name" in sparql:
                return parse_results({
                    "head": {"vars": ["member", "name", "memberCode"]},
                    "results": {"bindings": []},
                })
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


def test_pipeline_runs_local_member_resolution_then_reports_controlled_validation_failure():
    phases = []

    class Translator:
        def translate(self, question, _schema):
            assert question == "question"
            return Translation("unsafe", "INSERT DATA { <urn:s> <urn:p> <urn:o> }")

    class ResolutionOnlyFuseki:
        def query(self, sparql):
            assert "?question" in sparql
            return parse_results({
                "head": {"vars": ["member", "name", "memberCode"]},
                "results": {"bindings": []},
            })

    fuseki = ResolutionOnlyFuseki()

    outcome = process_question(
        "question", translator=Translator(), fuseki_factory=lambda: fuseki,
        schema_context="schema", supported_predicates=None, on_phase=phases.append,
    )

    assert outcome.error is not None
    assert outcome.error_phase == "SPARQL validation"
    assert outcome.translation.interpretation == "unsafe"
    assert outcome.result is None
    assert phases == ["Member name resolution", "LLM translation", "SPARQL validation"]


def test_pipeline_publishes_translation_before_unexpected_later_failure(monkeypatch):
    translation = Translation("Find a member", "SELECT ?x WHERE { ?x <urn:p> ?o }")
    captured = []

    class Translator:
        def translate(self, _question, _schema):
            return translation

    def unexpected_validation_failure(*_args, **_kwargs):
        raise RuntimeError("unexpected local validator error")

    monkeypatch.setattr(pipeline_module, "validate_sparql", unexpected_validation_failure)
    class ResolutionOnlyFuseki:
        def query(self, _sparql):
            return parse_results({
                "head": {"vars": ["member", "name", "memberCode"]},
                "results": {"bindings": []},
            })

    with pytest.raises(RuntimeError, match="unexpected local validator error"):
        process_question(
            "question", translator=Translator(), fuseki_factory=ResolutionOnlyFuseki,
            schema_context="schema", supported_predicates=None,
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
