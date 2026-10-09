"""Opt-in execution acceptance against fresh Phase 0A capture-backed Fuseki."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

from poc.nlq.benchmark_isolation import DisposableFuseki
from poc.nlq.fuseki import FusekiQueryClient
from poc.nlq.plan_sparql import PlanSparqlGenerator, build_label_lookup_query
from poc.nlq.plan_contract import validate_query_plan
from poc.nlq.structured_planner import PlannerResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
RUN_FUSEKI = os.getenv("OIR_RUN_NLQ_PLAN_FUSEKI_TESTS") == "1"
pytestmark = pytest.mark.skipif(
    not RUN_FUSEKI,
    reason="set OIR_RUN_NLQ_PLAN_FUSEKI_TESTS=1 to run disposable capture-backed Fuseki acceptance",
)

_AENGUS = "https://data.oireachtas.ie/ie/oireachtas/member/id/Aengus-Ó-Snodaigh.D.2002-06-06"
_TIMMY = "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
_DAIL_33 = "https://data.oireachtas.ie/ie/oireachtas/house/dail/33"
_DAIL_34 = "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
_SEANAD_26 = "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26"
_COLLECTION = "https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_Fáil"
_PANEL = "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26/panel/Nominated-by-the-Taoiseach"
_COMMITTEE = (
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/"
    "joint_committee_on_transport_and_communications"
)


def _entity(entity_id: str, entity_type: str, iri: str, label: str) -> dict:
    return {
        "id": entity_id, "type": entity_type, "iri": iri,
        "label": label, "resolution": "resolved",
    }


def _plan(*, entities=(), requirements=(), temporal=(), aggregation=None, answer):
    return validate_query_plan({
        "contractId": "https://data.oireachtas.ie/specs/query-plan-contract",
        "schemaVersion": 1, "contractVersion": "1.0.1",
        "intent": "capture-backed deterministic generator acceptance",
        "source": "oireachtas",
        "entities": list(entities),
        "requirements": list(requirements),
        "filters": [],
        "temporalConstraints": list(temporal),
        "aggregation": aggregation,
        "answerShape": answer,
    })


def _lexical_values(result) -> tuple[str, ...]:
    if result.raw_json:
        payload = json.loads(result.raw_json)
        return tuple(
            binding["value"]
            for row in payload.get("results", {}).get("bindings", [])
            for binding in row.values()
            if isinstance(binding, dict) and isinstance(binding.get("value"), str)
        )
    return tuple(value for row in result.rows for value in row)


def _bootstrap(instance: DisposableFuseki, baseline_path: Path) -> None:
    raw_dir = Path(os.getenv(
        "OIR_NLQ_CAPTURE_RAW_DIR",
        str(ROOT.parents[1] / "OireachtasOntology" / "data" / "raw"),
    )).expanduser()
    if not raw_dir.is_dir():
        pytest.skip("preserved Phase 0A capture directory is unavailable")
    uv = os.getenv("UV", shutil.which("uv") or "uv")
    command = [
        uv, "run", "--locked", "oir-etl", "dev", "bootstrap",
        "--raw-dir", str(raw_dir.resolve()),
        "--fuseki-gsp-url", instance.gsp_url,
        "--fuseki-sparql-url", instance.query_url,
        "--dataset-baseline-output", str(baseline_path),
    ]
    environment = os.environ.copy()
    environment.update({
        "OIR_FUSEKI_GSP_URL": instance.gsp_url,
        "OIR_FUSEKI_SPARQL_URL": instance.query_url,
        "OIR_FUSEKI_USER": "admin",
        "OIR_FUSEKI_PASSWORD": instance.password,
    })
    completed = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    assert completed.returncode == 0, (
        "Phase 0A capture bootstrap failed; no generated query was executed.\n"
        + (completed.stdout + completed.stderr)[-12000:]
    )


def test_representative_validated_plans_execute_correctly_on_disposable_fuseki():
    scratch = Path("/tmp/opencode/oireachtasontology/nlq-plan-fuseki")
    scratch.mkdir(parents=True, exist_ok=True)
    with DisposableFuseki() as instance, tempfile.TemporaryDirectory(
        prefix="acceptance-", dir=scratch,
    ) as directory:
        _bootstrap(instance, Path(directory) / "dataset-baseline.json")
        client = FusekiQueryClient(
            instance.query_url, username="admin", password=instance.password,
        )
        generator = PlanSparqlGenerator(
            supported_predicates=supported_predicates(ROOT / "ontology"),
        )
        try:
            plans = {
                "member_full_name": _plan(
                    entities=[_entity("member", "Member", _AENGUS, "Aengus Ó Snodaigh")],
                    requirements=[{
                        "id": "name", "fact": "member_full_name", "subject": {"entity": "member"},
                    }],
                    answer={"kind": "fact", "target": "name"},
                ),
                "member_to_dail_term": _plan(
                    entities=[_entity("member", "Member", _AENGUS, "Aengus Ó Snodaigh")],
                    requirements=[{
                        "id": "membership", "fact": "member_house_term_membership",
                        "subject": {"entity": "member"}, "object": {"type": "DailTerm"},
                    }],
                    answer={"kind": "entities", "entityType": "DailTerm"},
                ),
                "collection_during_dail": _plan(
                    entities=[
                        _entity("member", "Member", _TIMMY, "Timmy Dooley"),
                        _entity("term", "DailTerm", _DAIL_34, "34th Dáil"),
                    ],
                    requirements=[{
                        "id": "membership", "fact": "member_collection_membership",
                        "subject": {"entity": "member"},
                        "object": {"type": "ParliamentaryMemberCollection"},
                    }],
                    temporal=[{
                        "target": "membership", "kind": "during", "period": {"entity": "term"},
                    }],
                    answer={"kind": "entities", "entityType": "ParliamentaryMemberCollection"},
                ),
                "representation_during_seanad": _plan(
                    entities=[
                        _entity("member", "Member", _TIMMY, "Timmy Dooley"),
                        _entity("term", "SeanadTerm", _SEANAD_26, "26th Seanad"),
                    ],
                    requirements=[{
                        "id": "representation", "fact": "member_constituency_representation",
                        "subject": {"entity": "member"}, "object": {"type": "SeanadPanel"},
                    }],
                    temporal=[{
                        "target": "representation", "kind": "during", "period": {"entity": "term"},
                    }],
                    answer={"kind": "entities", "entityType": "SeanadPanel"},
                ),
                "committee_code": _plan(
                    entities=[_entity(
                        "committee", "Committee", _COMMITTEE,
                        "Joint Committee on Transport and Communications",
                    )],
                    requirements=[{
                        "id": "code", "fact": "committee_code", "subject": {"entity": "committee"},
                    }],
                    answer={"kind": "fact", "target": "code"},
                ),
                "boolean_member_term": _plan(
                    entities=[
                        _entity("member", "Member", _AENGUS, "Aengus Ó Snodaigh"),
                        _entity("term", "DailTerm", _DAIL_33, "33rd Dáil"),
                    ],
                    requirements=[{
                        "id": "membership", "fact": "member_house_term_membership",
                        "subject": {"entity": "member"}, "object": {"entity": "term"},
                    }],
                    answer={"kind": "boolean"},
                ),
                "count_dail_terms": _plan(
                    requirements=[{
                        "id": "term-label", "fact": "parliamentary_term_label",
                        "subject": {"type": "DailTerm"},
                    }],
                    aggregation={
                        "operation": "count",
                        "target": {"requirement": "term-label", "participant": "subject"},
                        "groupBy": [],
                    },
                    answer={"kind": "count", "target": "aggregation"},
                ),
            }
            results = {}
            for name, plan in plans.items():
                generated = generator.generate(PlannerResult("validated_plan", plan=plan))
                assert generated.generated, (name, generated.as_dict())
                results[name] = client.query(generated.sparql)

            assert results["member_full_name"].kind == "select"
            assert "Aengus Ó Snodaigh" in _lexical_values(results["member_full_name"])
            assert results["member_to_dail_term"].kind == "select"
            assert _DAIL_33 in _lexical_values(results["member_to_dail_term"])
            assert _COLLECTION in _lexical_values(results["collection_during_dail"])
            assert _PANEL in _lexical_values(results["representation_during_seanad"])
            assert "TRJ" in _lexical_values(results["committee_code"])
            assert results["boolean_member_term"].kind == "ask"
            assert results["boolean_member_term"].boolean is True
            assert results["count_dail_terms"].kind == "select"
            count_values = _lexical_values(results["count_dail_terms"])
            assert len(count_values) == 1 and int(count_values[0]) > 1

            # The resource-valued answer query itself has no presentation-label join.
            label_query = build_label_lookup_query(
                "ParliamentaryMemberCollection", _COLLECTION,
                supported_predicates=supported_predicates(ROOT / "ontology"),
            )
            labels = client.query(label_query)
            assert "Fianna Fáil" in _lexical_values(labels)
        finally:
            client.close()
