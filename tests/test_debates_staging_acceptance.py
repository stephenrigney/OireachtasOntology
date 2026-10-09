"""Real manifest/Core State/Fuseki acceptance; opt in with staging env vars.

This test is intentionally not a Fuseki double. It uses an explicitly named
loopback Fuseki dataset and an isolated Core State database.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from oireachtas_etl import cli as cli_module
from oireachtas_etl import competency
from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH
from oireachtas_etl.debates_pipeline import load_debate_owner_snapshot
from oireachtas_etl.debates_readiness import load_manifest, make_batches
from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.resource_budget import DEFAULT_LIMITS, GIB
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.common import MEMBERS, OIR
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import member_graph_iri, transform_member
from oireachtas_etl.validation.committees import validate_committees
from oireachtas_etl.validation.houses import validate_houses
from oireachtas_etl.validation.members import validate_member


ROOT = Path(__file__).resolve().parents[1]
FUSEKI_GSP = os.getenv("OIR_DEBATES_STAGE_GSP")
FUSEKI_SPARQL = os.getenv("OIR_DEBATES_STAGE_SPARQL")
STAGE_ROOT = Path(os.getenv("OIR_DEBATES_STAGE_ROOT", "/tmp/oireachtasontology/debates-stage"))
EVIDENCE_RAW = os.getenv("OIR_DEBATES_EVIDENCE_RAW")
TDB2_DIR = os.getenv("OIR_DEBATES_STAGE_TDB2")
HOST_PATH = os.getenv("OIR_DEBATES_STAGE_HOST", str(Path.home()))
SENTINEL = "https://data.oireachtas.ie/graph/debates-staging-preservation-sentinel"

pytestmark = pytest.mark.skipif(
    not (FUSEKI_GSP and FUSEKI_SPARQL and EVIDENCE_RAW and TDB2_DIR),
    reason="requires an explicitly disposable Fuseki, TDB2 path and preserved Debate evidence",
)


def _copy_batch_sources(batch, source_root: Path, raw_root: Path) -> None:
    for record in batch.records:
        xml_source = source_root / "debates" / "sha256" / record.sha256[:2] / f"{record.sha256}.xml"
        metadata_source = source_root / record.metadata_evidence_path
        for source in (xml_source, metadata_source):
            target = raw_root / source.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def _resource_config(path: Path, state_path: Path, raw_root: Path,
                     temp_root: Path, observation_path: Path,
                     limits: dict | None = None) -> Path:
    path.write_text(json.dumps({
        "schema": "debates-resource-budget-v1",
        "paths": {"tdb2": TDB2_DIR, "temporary": str(temp_root), "host": HOST_PATH},
        "fuseki_process_match": "org.apache.jena.fuseki.cmd.FusekiCmd",
        "fuseki_cgroup_match": os.getenv("OIR_DEBATES_STAGE_CGROUP_MATCH"),
        "observation_file": str(observation_path),
        "limits": limits or {},
    }, sort_keys=True), encoding="utf-8")
    return path


def _argv(*, raw_root: Path, state_path: Path, budget: Path, report: Path,
          batch_index: int, max_works: int) -> list[str]:
    return [
        "run", "debates", "--inventory-file",
        str(ROOT / "documentation/debates-initial-production-inventory.json"),
        "--batch-index", str(batch_index), "--batch-max-works", str(max_works),
        "--batch-max-source-bytes", str(64 * 1024 * 1024), "--publish",
        "--resource-budget-file", str(budget), "--resource-report", str(report),
        "--state-db", str(state_path), "--raw-dir", str(raw_root),
        "--fuseki-gsp-url", FUSEKI_GSP, "--fuseki-sparql-url", FUSEKI_SPARQL,
    ]


def _run_child(argv: list[str], *, environment: dict[str, str], expected=0) -> tuple[dict | None, str, str]:
    executable = Path(sys.executable).with_name("oir-etl")
    process = subprocess.run([str(executable), *argv], cwd=ROOT, env=environment,
                             text=True, capture_output=True, check=False)
    assert process.returncode == expected, (
        f"CLI exit={process.returncode}, expected={expected}\n"
        f"stdout={process.stdout}\nstderr={process.stderr}"
    )
    result = None
    if expected == 0:
        result = json.loads(process.stdout.strip().splitlines()[-1])
    return result, process.stdout, process.stderr


def _owner_evidence(state_path: Path, raw_root: Path, environment: dict[str, str]):
    """Publish validated representative owner fixtures through normal CLI paths."""
    executable = Path(sys.executable).with_name("oir-etl")
    common = ["--state-db", str(state_path), "--raw-dir", str(raw_root),
              "--fuseki-gsp-url", FUSEKI_GSP, "--fuseki-sparql-url", FUSEKI_SPARQL]
    for command in (
        ["run", "houses", "--fixture", str(ROOT / "data/api_examples/houses.json"), *common],
        ["run", "members", "--fixture", str(ROOT / "data/api_examples/member.json"), *common],
    ):
        process = subprocess.run([str(executable), *command], cwd=ROOT, env=environment,
                                 text=True, capture_output=True, check=False)
        assert process.returncode == 0, process.stdout + process.stderr

    member_source = json.loads((ROOT / "data/api_examples/member.json").read_text())
    houses_source = json.loads((ROOT / "data/api_examples/houses.json").read_text())
    committee_source = json.loads((ROOT / "tests/fixtures/committee-owner.json").read_text())
    member_graph = transform_member(member_source)
    house_graph = transform_houses(houses_source)
    committee_graph = transform_committees(committee_source)
    validate_member(member_source, member_graph)
    validate_houses(houses_source, house_graph)
    validate_committees(committee_source, committee_graph)
    committee_payload = ntriples(committee_graph)
    client = FusekiSparqlClient(
        FUSEKI_SPARQL, user=environment["OIR_FUSEKI_USER"],
        password=environment["OIR_FUSEKI_PASSWORD"])
    loader = FusekiGraphStoreLoader(
        FUSEKI_GSP, user=environment["OIR_FUSEKI_USER"],
        password=environment["OIR_FUSEKI_PASSWORD"])
    with CoreStateStore(state_path) as store:
        digest = store.mark_endpoint_dirty("committees", COMMITTEES_GRAPH, committee_payload)
        loader.replace(COMMITTEES_GRAPH, committee_payload,
                       content_type="application/n-triples")
        competency.verify_core_graph(client, COMMITTEES_GRAPH, committee_payload)
        store.complete_endpoint_publication("committees", COMMITTEES_GRAPH, digest)
        snapshot = load_debate_owner_snapshot(store)
        assert len(snapshot.graphs) == 3
    return {
        "sources": {
            "houses": {"path": "data/api_examples/houses.json",
                       "sha256": hashlib.sha256((ROOT / "data/api_examples/houses.json").read_bytes()).hexdigest()},
            "member": {"path": "data/api_examples/member.json",
                       "sha256": hashlib.sha256((ROOT / "data/api_examples/member.json").read_bytes()).hexdigest()},
            "committee": {"path": "tests/fixtures/committee-owner.json",
                          "sha256": hashlib.sha256((ROOT / "tests/fixtures/committee-owner.json").read_bytes()).hexdigest()},
        },
        "validated_owner_counts": {
            "members": len(set(member_graph.subjects(RDF.type, OIR.Member))),
            "house_terms": len(set(house_graph.subjects(RDF.type, OIR.DailTerm)))
            + len(set(house_graph.subjects(RDF.type, OIR.SeanadTerm))),
            "committees": len(set(committee_graph.subjects(RDF.type, MEMBERS.Committee))),
        },
        "resolver_lookup_keys": {
            "member": len(snapshot.resolver.members_by_tlc_href),
            "house_term": len(snapshot.resolver.house_terms_by_author_href),
            "committee": len(snapshot.resolver.committees_by_author_href),
        },
        "scope_note": "representative validated fixture owner evidence; not complete/current production coverage",
    }


def _clear_only_the_disposable_dataset(client, loader) -> None:
    """Empty every existing graph on the explicitly loopback staging dataset."""
    for row in client.query(
            "SELECT DISTINCT ?graph WHERE { GRAPH ?graph { ?s ?p ?o } }"):
        graph_iri = row["graph"]["value"]
        loader.replace(graph_iri, "", content_type="application/n-triples")


def _json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _expected_env(raw_root: Path, state_path: Path, temp_root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        "OIR_ETL_STATE_DB": str(state_path),
        "OIR_MEMBERS_STATE_FILE": str(STAGE_ROOT / "no-legacy-members.json"),
        "OIR_BILLS_STATE_FILE": str(STAGE_ROOT / "no-legacy-bills.json"),
        "OIR_RAW_DIR": str(raw_root),
        "OIR_FUSEKI_GSP_URL": FUSEKI_GSP,
        "OIR_FUSEKI_SPARQL_URL": FUSEKI_SPARQL,
        "OIR_FUSEKI_USER": os.getenv("OIR_DEBATES_STAGE_USER", "admin"),
        "OIR_FUSEKI_PASSWORD": os.getenv("OIR_DEBATES_STAGE_PASSWORD", "staging-only"),
        "TMPDIR": str(temp_root),
    })
    temp_root.mkdir(parents=True, exist_ok=True)
    return environment


def test_manifest_batches_resource_stops_and_actual_fuseki_recovery():
    root = STAGE_ROOT.resolve()
    assert FUSEKI_GSP.startswith("http://127.0.0.1:")
    assert FUSEKI_SPARQL.startswith("http://127.0.0.1:")
    assert Path(TDB2_DIR).resolve().is_relative_to(root)
    if root.exists():
        tdb_path = Path(TDB2_DIR).resolve()
        for child in root.iterdir():
            if child.resolve() == tdb_path:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    root.mkdir(parents=True, exist_ok=True)
    temp_root = root / "runtime-temp"
    temp_root.mkdir()
    # The guard verifies this is the actual TMPDIR before it allows publication.
    tempfile.tempdir = str(temp_root)
    os.environ["TMPDIR"] = str(temp_root)

    state_path, raw_root = root / "core.sqlite", root / "raw"
    raw_root.mkdir()
    environment = _expected_env(raw_root, state_path, temp_root)
    os.environ.update({key: value for key, value in environment.items()
                       if key.startswith("OIR_") or key == "TMPDIR"})
    client = FusekiSparqlClient(
        FUSEKI_SPARQL, user=environment["OIR_FUSEKI_USER"],
        password=environment["OIR_FUSEKI_PASSWORD"])
    loader = FusekiGraphStoreLoader(
        FUSEKI_GSP, user=environment["OIR_FUSEKI_USER"],
        password=environment["OIR_FUSEKI_PASSWORD"])
    _clear_only_the_disposable_dataset(client, loader)
    owner_report = _owner_evidence(state_path, raw_root, environment)
    sentinel_payload = "<https://example.test/debates-staging-sentinel> <https://example.test/p> <https://example.test/o> .\n"
    loader.replace(SENTINEL, sentinel_payload, content_type="application/n-triples")
    competency.verify_core_graph(client, SENTINEL, sentinel_payload)

    manifest = load_manifest(ROOT / "documentation/debates-initial-production-inventory.json")
    batches = {count: make_batches(manifest, max_works=count)[0] for count in (5, 10, 25)}
    for count, batch in batches.items():
        repeated = make_batches(manifest, max_works=count)[0]
        assert [(r.url, r.sha256) for r in batch.records] == [
            (r.url, r.sha256) for r in repeated.records]
    for batch in batches.values():
        _copy_batch_sources(batch, Path(EVIDENCE_RAW), raw_root)
    quarantine_batches = make_batches(manifest, max_works=25)
    quarantine_index = next(
        i for i, batch in enumerate(quarantine_batches)
        if any(record.status == "quarantined" for record in batch.records))
    quarantine_batch = quarantine_batches[quarantine_index]
    _copy_batch_sources(quarantine_batch, Path(EVIDENCE_RAW), raw_root)

    observations = root / "resource-observations.jsonl"
    runs: list[dict] = []
    for size in (5,):
        budget = _resource_config(root / f"budget-{size}.json", state_path,
                                  raw_root, temp_root, observations,
                                  {"etl_rss_warn_bytes": 1, "fuseki_rss_warn_bytes": 1})
        result, _stdout, stderr = _run_child(
            _argv(raw_root=raw_root, state_path=state_path, budget=budget,
                  report=observations, batch_index=0, max_works=size),
            environment=environment)
        assert result["new"] == 5 and result["quarantined"] == 0
        assert '"event": "resource_budget_warning"' in stderr
        runs.append({"batch_size": size, "result": result})

    # Intentionally set a limit just above current use; projected TDB2 growth
    # must stop before a new graph becomes dirty or any graph is PUT.
    from oireachtas_etl.resource_budget import _directory_bytes
    current_tdb = _directory_bytes(Path(TDB2_DIR))
    stop_budget = _resource_config(
        root / "budget-stop.json", state_path, raw_root, temp_root, observations,
        {"tdb2_stop_bytes": current_tdb + 1},
    )
    with CoreStateStore(state_path) as store:
        pre_stop_graphs = {row["resource_iri"]: row["published_payload_hash"]
                           for row in store.resources("debates")}
    stopped, stdout, stderr = _run_child(
        _argv(raw_root=raw_root, state_path=state_path, budget=stop_budget,
              report=observations, batch_index=0, max_works=10),
        environment=environment, expected=1)
    assert stopped is None and "resource hard stop" in stderr
    with CoreStateStore(state_path) as store:
        assert {row["resource_iri"]: row["published_payload_hash"]
                for row in store.resources("debates")} == pre_stop_graphs
        assert not any(row["publication_state"] == "dirty" for row in store.resources("debates"))
        assert store.connection.execute(
            "SELECT COUNT(*) FROM etl_run WHERE status='failed'").fetchone()[0] >= 1

    # Fail the next real GSP PUT after Core State durably marks it dirty.
    normal_budget = _resource_config(root / "budget-normal.json", state_path,
                                     raw_root, temp_root, observations)
    target_10 = next(record for record in batches[10].records
                     if record.work_iri not in pre_stop_graphs)
    original_loader = cli_module.FusekiGraphStoreLoader

    class FailDebatePutOnce(original_loader):
        failed = False

        def replace(self, graph_iri, payload, *, content_type):
            if graph_iri.startswith("https://data.oireachtas.ie/graph/debate/") and not self.failed:
                self.failed = True
                raise OSError("injected disposable Fuseki PUT interruption")
            return super().replace(graph_iri, payload, content_type=content_type)

    cli_module.FusekiGraphStoreLoader = FailDebatePutOnce
    try:
        with pytest.raises(OSError, match="injected disposable Fuseki PUT"):
            cli_module.main(_argv(raw_root=raw_root, state_path=state_path,
                                  budget=normal_budget, report=observations,
                                  batch_index=0, max_works=10))
    finally:
        cli_module.FusekiGraphStoreLoader = original_loader
    with CoreStateStore(state_path) as store:
        dirty = store.get_resource("debates", target_10.work_iri)
        assert dirty["publication_state"] == "dirty"
        assert dirty["pending_payload"] and dirty["pending_payload_hash"]
        pending_before_stop = (dirty["pending_payload"], dirty["pending_payload_hash"])
    # A resource hard stop on a replay must preserve the already-durable dirty
    # payload rather than clearing or replacing it before the next PUT.
    pending_stop_budget = _resource_config(
        root / "budget-pending-stop.json", state_path, raw_root, temp_root,
        observations, {"tdb2_stop_bytes": _directory_bytes(Path(TDB2_DIR)) + 1},
    )
    _stopped, _stdout, pending_stop_stderr = _run_child(
        _argv(raw_root=raw_root, state_path=state_path, budget=pending_stop_budget,
              report=observations, batch_index=0, max_works=10),
        environment=environment, expected=1)
    assert "resource hard stop" in pending_stop_stderr
    with CoreStateStore(state_path) as store:
        still_dirty = store.get_resource("debates", target_10.work_iri)
        assert still_dirty["publication_state"] == "dirty"
        assert (still_dirty["pending_payload"], still_dirty["pending_payload_hash"]) == pending_before_stop
    result, _stdout, _stderr = _run_child(
        _argv(raw_root=raw_root, state_path=state_path, budget=normal_budget,
              report=observations, batch_index=0, max_works=10),
        environment=environment)
    assert result["new"] + result["changed"] == 5 and result["skipped"] == 5
    runs.append({"batch_size": 10, "result": result,
                 "recovered_after": "injected PUT interruption"})

    # Exercise an actual GSP replacement followed by failed whole-graph
    # verification; restart must verify and clean the exact pending payload.
    with CoreStateStore(state_path) as store:
        prior_work = {row["resource_iri"] for row in store.resources("debates")}
    target_25 = min((record for record in batches[25].records
                     if record.work_iri not in prior_work), key=lambda row: row.work_iri)
    original_verify = competency.verify_core_graph
    injected = {"done": False}

    def fail_post_put_once(client_arg, graph_iri, payload):
        if graph_iri == target_25.work_iri.replace(
                "https://data.oireachtas.ie/akn/ie/debateRecord/",
                "https://data.oireachtas.ie/graph/debate/") and not injected["done"]:
            injected["done"] = True
            raise ValueError("injected post-PUT whole-graph verification failure")
        return original_verify(client_arg, graph_iri, payload)

    competency.verify_core_graph = fail_post_put_once
    try:
        with pytest.raises(ValueError, match="injected post-PUT"):
            cli_module.main(_argv(raw_root=raw_root, state_path=state_path,
                                  budget=normal_budget, report=observations,
                                  batch_index=0, max_works=25))
    finally:
        competency.verify_core_graph = original_verify
    with CoreStateStore(state_path) as store:
        dirty = store.get_resource("debates", target_25.work_iri)
        assert dirty["publication_state"] == "dirty"
        assert dirty["pending_payload_hash"]
    result, _stdout, _stderr = _run_child(
        _argv(raw_root=raw_root, state_path=state_path, budget=normal_budget,
              report=observations, batch_index=0, max_works=25),
        environment=environment)
    assert result["new"] + result["changed"] == 15 and result["skipped"] == 10
    runs.append({"batch_size": 25, "result": result,
                 "recovered_after": "injected post-PUT verification failure"})

    # The quarantine batch contains an inventory-withheld source and eligible
    # siblings; its failure must not stop sibling graph publication.
    qresult, _stdout, _stderr = _run_child(
        _argv(raw_root=raw_root, state_path=state_path, budget=normal_budget,
              report=observations, batch_index=quarantine_index, max_works=25),
        environment=environment)
    expected_q = [r for r in quarantine_batch.records if r.status == "quarantined"]
    assert qresult["quarantined"] == len(expected_q) > 0
    assert qresult["outcome"] == "degraded"
    assert qresult["new"] + qresult["skipped"] > 0
    with CoreStateStore(state_path) as store:
        outstanding = store.quarantine_records(endpoint="debates", status="quarantined")
        assert {row["source_hash"] for row in outstanding} >= {r.sha256 for r in expected_q}
        for record in expected_q:
            assert store.get_resource("debates", record.work_iri) is None
        catalog = store.catalog_publication()
        assert catalog and catalog["publication_state"] == "clean"
        resources = store.resources("debates")
        assert all(row["publication_state"] == "clean" for row in resources)

    # A requested quarantine retry is evidence-only until the exact source is
    # reobserved; replay remains quarantined and valid siblings remain intact.
    qrecord = next(row for row in outstanding
                   if row["source_hash"] == expected_q[0].sha256)
    executable = Path(sys.executable).with_name("oir-etl")
    retry = subprocess.run([
        str(executable), "quarantine", "retry", qrecord["quarantine_id"],
        "--requested-by", "staging-acceptance", "--reason", "exercise preserved-source retry",
        "--state-db", str(state_path),
    ], cwd=ROOT, env=environment, text=True, capture_output=True, check=False)
    assert retry.returncode == 0, retry.stdout + retry.stderr
    qagain, _stdout, _stderr = _run_child(
        _argv(raw_root=raw_root, state_path=state_path, budget=normal_budget,
              report=observations, batch_index=quarantine_index, max_works=25),
        environment=environment)
    assert qagain["quarantined"] == len(expected_q)
    assert qagain["outcome"] == "degraded"
    with CoreStateStore(state_path) as store:
        history = store.quarantine_history(qrecord["quarantine_id"])
        assert any(row["action"] == "retry_requested" for row in history)
        assert any(row["action"] == "retry_failed" for row in history)

    competency.verify_core_graph(client, SENTINEL, sentinel_payload)
    with CoreStateStore(state_path) as store:
        catalog = store.catalog_publication()
        competency.verify_core_graph(client, catalog["graph_iri"], catalog["published_payload"])
        clean_graphs = [row for row in store.resources("debates")
                        if row["publication_state"] == "clean"]
        assert len(clean_graphs) >= 25
        # Owner fixtures seed representative graphs through the existing
        # validation/publication path but are not complete source runs.
        # Their pre-existing provenance-incomplete marker is expected;
        # Debates publications must nevertheless have no such marker.
        assert not [row for row in store.provenance_incomplete_records()
                    if row["endpoint"] == "debates"]

    all_observations = _json_lines(observations)
    assert all(item["fuseki_pids"] and item["fuseki_rss_bytes"] > 0
               and item["etl_rss_peak_bytes"] > 0
               for item in all_observations)
    assert all(item["temporary_volume_free_bytes"] > 0 for item in all_observations)
    final = {
        "owner_evidence": owner_report,
        "calibration_runs": runs,
        "quarantine_batch_index": quarantine_index,
        "quarantine_record_count": len(expected_q),
        "published_debate_graphs": len(clean_graphs),
        "provenance_catalog_state": catalog["publication_state"],
        "resource_observation_count": len(all_observations),
        "resource_observations_path": str(observations),
        "resource_min_host_memory_available_bytes": min(
            item["host_memory_available_bytes"] for item in all_observations),
        "resource_peak_etl_rss_bytes": max(
            item["etl_rss_peak_bytes"] for item in all_observations),
        "resource_peak_fuseki_rss_bytes": max(
            item["fuseki_rss_bytes"] for item in all_observations),
        "resource_peak_tdb2_bytes": max(item["tdb2_bytes"] for item in all_observations),
        "resource_peak_core_state_bytes": max(item["core_state_bytes"] for item in all_observations),
        "resource_peak_reference_report_bytes": max(
            item["reference_report_bytes"] for item in all_observations),
        "resource_peak_temporary_bytes": max(item["temporary_bytes"] for item in all_observations),
        "resource_warnings": [warning for item in all_observations
                              for warning in item["warnings"]],
        "limits": DEFAULT_LIMITS,
    }
    (root / "staging-summary.json").write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
