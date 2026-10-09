"""Offline tests for the Phase 2C controlled execution/evaluation path."""

from __future__ import annotations

import json
from pathlib import Path

from poc.nlq.plan_benchmark import run_phase1_comparison, run_plan_cases, summarize_plan_results
from poc.nlq.results import QueryResult
from poc.nlq.structured_planner import PlannerResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
PREDICATES = supported_predicates(ROOT / "ontology")
MEMBER = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
TERM = "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"


def _entity(entity_id, entity_type, iri, label):
    return {
        "id": entity_id, "type": entity_type, "iri": iri,
        "label": label, "resolution": "resolved",
    }


def _name_plan():
    return {
        "contractId": "https://data.oireachtas.ie/specs/query-plan-contract",
        "schemaVersion": 1,
        "contractVersion": "1.0.1",
        "intent": "member full name",
        "source": "oireachtas",
        "entities": [_entity("member", "Member", MEMBER, "Timmy Dooley")],
        "requirements": [{
            "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
        }],
        "filters": [],
        "temporalConstraints": [],
        "aggregation": None,
        "answerShape": {"kind": "fact", "target": "name"},
    }


def _term_plan():
    return {
        "contractId": "https://data.oireachtas.ie/specs/query-plan-contract",
        "schemaVersion": 1,
        "contractVersion": "1.0.1",
        "intent": "member term",
        "source": "oireachtas",
        "entities": [_entity("member", "Member", MEMBER, "Timmy Dooley")],
        "requirements": [{
            "id": "membership", "fact": "member_house_term_membership",
            "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
        }],
        "filters": [],
        "temporalConstraints": [],
        "aggregation": None,
        "answerShape": {"kind": "entities", "entityType": "DailTerm"},
    }


def _boolean_membership_plan():
    plan = _term_plan()
    plan["entities"].append(_entity("term", "DailTerm", TERM, "34th Dáil"))
    plan["requirements"][0]["object"] = {"entity": "term"}
    plan["answerShape"] = {"kind": "boolean"}
    plan["intent"] = "member in specified term"
    return plan


def _planner_case(case_id="plan.name", source_case_id="source.name"):
    return {
        "id": case_id,
        "source_case_id": source_case_id,
        "expectation": "validated_plan",
        "required_entities": [
            {"type": "Member", "label": "Timmy Dooley", "resolution": "resolved"},
        ],
        "required_requirements": [
            {"fact": "member_full_name", "subject_type": "Member", "object_type": None},
        ],
        "answer_shape": {"kind": "fact"},
    }


def _source_case(*, expected=None, question="What is the full name of Timmy Dooley?"):
    return {
        "id": "source.name",
        "question": question,
        "support_expectation": "supported",
        "evaluation_mode": "semantic_invariants",
        "expected_result": expected or {
            "kind": "select",
            "invariants": {"contains_values": ["Timmy Dooley"], "min_rows": 1},
        },
        "dataset_prerequisites": {
            "required_graph_families": ["members"],
            "required_resources": [],
            "coverage_probes": [],
            "unavailable_if": None,
        },
    }


def _benchmark(*, case=None, source_case=None):
    return (
        {
            "benchmark_id": "planner-test", "benchmark_version": "0.2.1",
            "source_benchmark": {"path": "source", "benchmark_version": "0.3.0"},
            "cases": [case or _planner_case()],
        },
        {
            "benchmark_id": "source-test", "benchmark_version": "0.3.0",
            "cases": [source_case or _source_case()],
        },
    )


def _baseline(*, members=1, houses=1):
    return {
        "schema_version": 1,
        "dataset": {"id": "sha256:" + "1" * 64},
        "graph_families_loaded": [
            {"name": name} for name, count in (("members", members), ("houses", houses)) if count
        ],
        "rdf_resource_counts": {"members": members, "house_terms": houses},
    }


class _FixedPlanner:
    def __init__(self, result):
        self.result = result
        self.generator = None

    def plan(self, _question):
        return self.result


class _QueryFuseki:
    def __init__(self, answers):
        self.answers = answers
        self.queries = []

    def query(self, query):
        self.queries.append(query)
        for marker, result in self.answers:
            if marker in query:
                if isinstance(result, Exception):
                    raise result
                return result
        return QueryResult("select", columns=("value",), rows=(("Timmy Dooley",),))


def _raw_label_result(value: str, language: str = "en") -> QueryResult:
    payload = {
        "head": {"vars": ["label"]},
        "results": {"bindings": [{"label": {
            "type": "literal", "value": value, "xml:lang": language,
        }}]},
    }
    return QueryResult(
        "select", columns=("label",), rows=((f"{value}@{language}",),),
        raw_json=json.dumps(payload),
    )


def test_end_to_end_planner_generation_execution_and_scoring():
    planner_benchmark, source_benchmark = _benchmark()
    fuseki = _QueryFuseki([
        ("foaf:name", QueryResult("select", columns=("value0",), rows=(("Timmy Dooley",),))),
    ])

    outcomes = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fuseki,
        supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_name_plan()),
        ),
    )

    [result] = outcomes
    assert result["evaluation"] == "passed"
    assert result["stage_status"] == {
        "source_data_coverage": "available",
        "planner_model": "passed",
        "plan_validation": "passed",
        "entity_binding": "passed",
        "generation": "passed",
        "sparql_safety": "passed",
        "execution": "passed",
        "result_scoring": "passed",
    }
    assert result["generation_result"]["query_form"] == "SELECT"
    assert "GRAPH ?graph_entity0" in result["generated_sparql"]
    assert len(fuseki.queries) == 1
    assert summarize_plan_results(outcomes)["passed"] == 1


def test_end_to_end_entity_results_remain_iris_and_score_via_separate_label_query():
    planner_benchmark, source_benchmark = _benchmark(
        case={
            "id": "plan.term", "source_case_id": "source.name",
            "expectation": "validated_plan", "required_entities": [],
            "required_requirements": [], "answer_shape": {"kind": "entities"},
        },
        source_case=_source_case(expected={
            "kind": "select", "invariants": {"contains_values": ["34th Dáil"], "min_rows": 1},
        }),
    )
    source_benchmark["cases"][0]["dataset_prerequisites"]["required_graph_families"] = ["members", "houses"]
    fake = _QueryFuseki([
        ("members:inHouseTerm", QueryResult("select", columns=("role0",), rows=((TERM,),))),
        ("SELECT DISTINCT ?label", _raw_label_result("34th Dáil")),
    ])

    result, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fake,
        supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_term_plan()),
        ),
    )

    assert result["evaluation"] == "passed"
    assert result["generation_result"]["generation_trace"]["answer_value_kind"] == "resource"
    assert result["execution_result"]["rows"] == [[TERM]]
    assert result["label_scoring_lookups"] == [{"resource_iri": TERM, "labels": ["34th Dáil"]}]
    assert len(fake.queries) == 2
    assert "skos:prefLabel" not in result["generated_sparql"]
    assert "skos:prefLabel" in fake.queries[1]


def test_boolean_generation_never_borrows_a_differently_scoped_coverage_probe_oracle():
    planner_case = {
        "id": "plan.boolean-membership", "source_case_id": "source.name",
        "expectation": "validated_plan",
        "required_entities": [
            {"type": "Member", "label": "Timmy Dooley", "resolution": "resolved"},
            {"type": "DailTerm", "label": "34th Dáil", "resolution": "resolved"},
        ],
        "required_requirements": [
            {"fact": "member_house_term_membership", "subject_type": "Member", "object_type": "DailTerm"},
        ],
        "answer_shape": {"kind": "boolean"},
    }
    source_case = _source_case(expected={
        "kind": "select", "invariants": {"contains_values": ["Timmy Dooley"]},
    })
    source_case["dataset_prerequisites"]["coverage_probes"] = [{
        "sparql": (
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
            f"ASK {{ GRAPH <https://data.oireachtas.ie/graph/houses> "
            f"{{ <{TERM}> rdf:type <https://data.oireachtas.ie/ontology#DailTerm> }} }}"
        ),
        "expected_result": {"kind": "ask", "boolean": False},
    }]
    planner_benchmark, source_benchmark = _benchmark(
        case=planner_case, source_case=source_case,
    )

    class _CoverageThenAsk:
        def __init__(self):
            self.queries = []

        def query(self, query):
            self.queries.append(query)
            if len(self.queries) == 1:
                return QueryResult("ask", boolean=False)
            return QueryResult("ask", boolean=True)

    fake = _CoverageThenAsk()
    result, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fake, supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_boolean_membership_plan()),
        ),
    )

    assert result["stage_status"]["execution"] == "passed"
    assert result["execution_result"]["boolean"] is True
    assert result["evaluation"] == "not_scored"
    assert result["result_oracle"] is None
    assert result["observed_outcome"] == "no_result_oracle_for_answer_shape"
    assert len(fake.queries) == 2


def test_explicit_planner_case_oracle_scores_the_generated_answer_shape():
    planner_case = {
        "id": "plan.boolean-membership", "source_case_id": "source.name",
        "expectation": "validated_plan",
        "required_entities": [
            {"type": "Member", "label": "Timmy Dooley", "resolution": "resolved"},
            {"type": "DailTerm", "label": "34th Dáil", "resolution": "resolved"},
        ],
        "required_requirements": [
            {"fact": "member_house_term_membership", "subject_type": "Member", "object_type": "DailTerm"},
        ],
        "answer_shape": {"kind": "boolean"},
        "expected_result": {"kind": "ask", "boolean": True},
    }
    planner_benchmark, source_benchmark = _benchmark(
        case=planner_case,
        source_case=_source_case(expected={
            "kind": "select", "invariants": {"contains_values": ["Timmy Dooley"]},
        }),
    )
    fake = _QueryFuseki([
        ("members:inHouseTerm", QueryResult("ask", boolean=True)),
    ])

    result, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fake, supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_boolean_membership_plan()),
        ),
    )

    assert result["evaluation"] == "passed"
    assert result["result_oracle"] == "planner_case.expected_result"
    assert result["score_reason"] == "ASK boolean matched"


def test_expected_ambiguous_plan_is_scored_without_generation_or_execution():
    ambiguous_plan = {
        "contractId": "https://data.oireachtas.ie/specs/query-plan-contract",
        "schemaVersion": 1, "contractVersion": "1.0.1", "intent": "ambiguous member",
        "source": "oireachtas",
        "entities": [{
            "id": "member", "type": "Member", "label": "Michael Collins",
            "resolution": "ambiguous", "candidates": [
                {"iri": MEMBER, "label": "Michael Collins"},
                {"iri": MEMBER + "2", "label": "Michael Collins"},
            ],
        }],
        "requirements": [{"id": "identity", "fact": "member_identity", "subject": {"entity": "member"}}],
        "filters": [], "temporalConstraints": [], "aggregation": None,
        "answerShape": {"kind": "entities", "entityType": "Member"},
    }
    planner_benchmark, source_benchmark = _benchmark(
        case={
            "id": "plan.ambiguous", "source_case_id": "source.name",
            "expectation": "clarification_required",
            "required_entities": [{
                "type": "Member", "label": "Michael Collins", "resolution": "ambiguous",
                "minimum_candidates": 2,
            }],
        },
    )
    fake = _QueryFuseki([])

    result, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fake,
        supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("clarification_required", plan=ambiguous_plan),
        ),
    )

    assert result["evaluation"] == "passed"
    assert result["stage_status"]["entity_binding"] == "blocked_expected"
    assert result["stage_status"]["generation"] == "not_run"
    assert not fake.queries


def test_planner_binding_failure_is_not_collapsed_into_generation_failure():
    planner_benchmark, source_benchmark = _benchmark()
    fake = _QueryFuseki([])

    result, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fake,
        supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult(
                "set_valued_member_identity",
                failure_stage="entity_resolution",
                failure_class="set_valued_member_identity",
                diagnostic="No singular IRI was selected.",
            ),
        ),
    )

    assert result["evaluation"] == "failed"
    assert result["failure_stage"] == "entity_binding"
    assert result["failure_class"] == "set_valued_member_identity"
    assert result["stage_status"]["generation"] == "not_run"
    assert not fake.queries


def test_generation_failure_safety_failure_execution_and_result_mismatch_are_distinct():
    planner_benchmark, source_benchmark = _benchmark()

    class UnsupportedPlanPlanner(_FixedPlanner):
        def plan(self, _question):
            plan = _name_plan()
            plan["temporalConstraints"] = [{
                "target": "name", "kind": "current",
            }]
            from poc.nlq.plan_contract import validate_query_plan
            return PlannerResult("validated_plan", plan=validate_query_plan(plan))

    unsupported, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=_QueryFuseki([]), supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: UnsupportedPlanPlanner(None),
    )
    assert unsupported["failure_stage"] == "generation"
    assert unsupported["failure_class"] == "unsupported_temporal_translation"

    execution, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=_QueryFuseki([("foaf:name", RuntimeError("Fuseki down"))]),
        supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_name_plan()),
        ),
    )
    assert execution["failure_stage"] == "execution"
    assert execution["failure_class"] == "execution"

    mismatch, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=_QueryFuseki([
            ("foaf:name", QueryResult("select", columns=("name",), rows=(("Wrong Name",),))),
        ]),
        supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_name_plan()),
        ),
    )
    assert mismatch["failure_stage"] == "result_scoring"
    assert mismatch["failure_class"] == "semantic_result_mismatch"


def test_missing_result_label_is_source_coverage_not_a_generator_failure():
    planner_benchmark, source_benchmark = _benchmark(
        case={
            "id": "plan.term", "source_case_id": "source.name",
            "expectation": "validated_plan", "required_entities": [],
            "required_requirements": [], "answer_shape": {"kind": "entities"},
        },
        source_case=_source_case(expected={
            "kind": "select", "invariants": {"contains_values": ["34th Dáil"]},
        }),
    )
    source_benchmark["cases"][0]["dataset_prerequisites"]["required_graph_families"] = ["members", "houses"]
    fake = _QueryFuseki([
        ("members:inHouseTerm", QueryResult("select", columns=("term",), rows=((TERM,),))),
        ("SELECT DISTINCT ?label", QueryResult("select", columns=("label",), rows=())),
    ])

    result, = run_plan_cases(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=fake, supported_predicates=PREDICATES,
        planner_factory=lambda _case, _fuseki: _FixedPlanner(
            PlannerResult("validated_plan", plan=_term_plan()),
        ),
    )

    assert result["evaluation"] == "not_scored"
    assert result["failure_stage"] == "source_data_coverage"
    assert result["failure_class"] == "source_data_coverage"


def test_phase1_comparison_uses_only_same_question_oracles(monkeypatch):
    from poc.nlq import plan_benchmark as module

    planner_benchmark = {
        "cases": [
            {"id": "same", "source_case_id": "source.same", "expectation": "validated_plan"},
            {"id": "override", "source_case_id": "source.same", "question": "Different question?", "expectation": "validated_plan"},
        ],
    }
    source_benchmark = {
        "benchmark_id": "source", "benchmark_version": "0.3.0",
        "cases": [{"id": "source.same", "question": "Same question?", "tiers": ["measured"]}],
    }
    captured = {}

    def fake_run(subset, *_args, **_kwargs):
        captured["case_ids"] = [case["id"] for case in subset["cases"]]
        return [{"case_id": case["id"], "passed": True, "failure_class": None}
                for case in subset["cases"]]

    monkeypatch.setattr(module, "run_phase1_cases", fake_run)
    result = run_phase1_comparison(
        planner_benchmark, source_benchmark, _baseline(),
        fuseki=object(), repository_root=ROOT,
        translator_factory=lambda _case: object(),
    )

    assert captured["case_ids"] == ["phase1-comparison-same"]
    assert result["summary"]["passed"] == 1
    assert result["comparable_case_ids"] == ["same"]
    assert result["not_compared"] == [{
        "case_id": "override",
        "reason": "question override has no matching Phase 1 result oracle",
    }]
