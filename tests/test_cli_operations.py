from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from rdflib import BNode, Dataset, Graph, URIRef

from oireachtas_etl import cli
from oireachtas_etl.api import ApiPage
from oireachtas_etl.provenance import ETL, PROV
from oireachtas_etl.state import (
    CoreStateStore,
    PROVENANCE_GRAPH_IRI,
    run_resource_iri,
)


ROOT = Path(__file__).resolve().parents[1]


def _binding(term) -> dict:
    if isinstance(term, URIRef):
        return {"type": "uri", "value": str(term)}
    if isinstance(term, BNode):
        return {"type": "bnode", "value": str(term)}
    result = {"type": "literal", "value": str(term)}
    if term.datatype:
        result["datatype"] = str(term.datatype)
    if term.language:
        result["xml:lang"] = term.language
    return result


class _InMemoryFusekiClient:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def query(self, query: str) -> list[dict]:
        result = self.dataset.query(query)
        return [{str(name): _binding(row[name]) for name in result.vars
                 if row[name] is not None} for row in result]

    def construct_graph(self, graph_iri: str) -> Graph:
        result = Graph()
        for triple in self.dataset.graph(URIRef(graph_iri)):
            result.add(triple)
        return result


class _InMemoryFusekiLoader:
    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def replace(self, graph_iri: str, payload: str, *, content_type: str) -> None:
        identifier = URIRef(graph_iri)
        self.dataset.remove_graph(identifier)
        target = self.dataset.graph(identifier)
        for triple in Graph().parse(data=payload, format="nt"):
            target.add(triple)


def _patch_fuseki(monkeypatch) -> Dataset:
    dataset = Dataset()
    monkeypatch.setattr(
        cli, "FusekiGraphStoreLoader",
        lambda *args, **kwargs: _InMemoryFusekiLoader(dataset))
    monkeypatch.setattr(
        cli, "FusekiSparqlClient",
        lambda *args, **kwargs: _InMemoryFusekiClient(dataset))
    return dataset


def test_shared_source_contract_failure_persists_drift_and_fails_closed(
        tmp_path, monkeypatch, capsys):
    source = json.loads((ROOT / "data/api_examples/constituencies.json").read_text())
    source[0]["constituencyOrPanel"]["representType"] = "unexpected"
    source[0]["unusedFutureField"] = {"new": True}
    fixture = tmp_path / "constituencies.json"
    fixture.write_text(json.dumps(source), encoding="utf-8")
    loader_constructions = []

    class Loader:
        def __init__(self, *args, **kwargs):
            loader_constructions.append(True)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    state_db = tmp_path / "core.sqlite"

    try:
        cli.main([
            "run", "constituencies", "--fixture", str(fixture),
            "--state-db", str(state_db), "--raw-dir", str(tmp_path / "raw"),
            "--fuseki-gsp-url", "http://fuseki.test/data",
            "--fuseki-sparql-url", "http://fuseki.test/query",
        ])
    except ValueError as error:
        assert "unsupported representType" in str(error)
    else:
        raise AssertionError("contract-breaking shared source unexpectedly succeeded")

    events = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert {event["event"] for event in events} >= {
        "run_started", "source_page_observed", "source_drift", "run_finished"}
    assert next(event for event in events if event["event"] == "run_finished")["outcome"] == "failed"
    assert loader_constructions == []
    report_path = next((tmp_path / "raw" / "constituencies").rglob("source-drift.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["source_failed"] is False
    assert report["failed_record_indices"] == [0]
    assert any(item["change"] == "unknown_property" and item["severity"] == "warning"
               for item in report["findings"])
    assert any(item["change"] == "incompatible_value" and item["severity"] == "record"
               for item in report["findings"])
    assert all(item["source_evidence"]["path"] for item in report["findings"])

    with CoreStateStore(state_db) as store:
        run = store.status()["recent_runs"][0]
        assert run["outcome"] == "failed"
        assert run["failure_scope"] == "source"
        assert run["failure_classification"] == "source_contract_failure"
        assert store.endpoint_publication("constituencies") is None


def test_malformed_api_json_is_persisted_before_source_failure(tmp_path, monkeypatch):
    response = b'{"results": [not-json'

    class Api:
        def __init__(self, *args, **kwargs):
            pass

        def page(self, *, skip: int, limit: int):
            return ApiPage(response, 200, {"skip": skip, "limit": limit})

    monkeypatch.setattr(cli, "HousesApiClient", Api)
    raw_root = tmp_path / "raw"
    state_db = tmp_path / "core.sqlite"

    try:
        cli.main([
            "run", "houses", "--state-db", str(state_db),
            "--raw-dir", str(raw_root),
            "--fuseki-gsp-url", "http://fuseki.test/data",
            "--fuseki-sparql-url", "http://fuseki.test/query",
        ])
    except ValueError as error:
        assert "not valid JSON" in str(error)
    else:
        raise AssertionError("malformed source JSON unexpectedly succeeded")

    page = next(path for path in raw_root.rglob("skip-000000.json")
                if path.is_file())
    assert page.read_bytes() == response
    digest = hashlib.sha256(response).hexdigest()
    with CoreStateStore(state_db) as store:
        run = store.status()["recent_runs"][0]
        assert run["outcome"] == "failed"
        assert run["failure_scope"] == "source"
        assert run["summary"]["counters"]["api_requests"] == 1
        assert run["summary"]["counters"]["api_failures"] == 1
        observed = store.connection.execute(
            "SELECT source_hash,evidence_pointer FROM source_observation WHERE run_id=?",
            (run["run_id"],),
        ).fetchone()
        assert observed["source_hash"] == digest
        assert observed["evidence_pointer"].startswith("file:")


def test_consumed_api_count_envelope_drift_is_reported_against_immutable_page(
        tmp_path, monkeypatch):
    response = json.dumps({"head": {"counts": {}}, "results": []}).encode()

    class Api:
        def __init__(self, *args, **kwargs):
            pass

        def page(self, *, skip: int, limit: int):
            return ApiPage(response, 200, {"skip": skip, "limit": limit})

    monkeypatch.setattr(cli, "ApiClient", Api)
    raw_root = tmp_path / "raw"
    with pytest.raises(ValueError, match="nonnegative integer advertised count"):
        cli.main(["run", "bills", "--offline", "--raw-dir", str(raw_root)])

    raw_path = next(path for path in raw_root.rglob("skip-000000.json")
                    if path.is_file())
    report_path = raw_path.with_name(
        raw_path.name.removesuffix(".json") + ".source-envelope-drift.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    finding = next(item for item in report["findings"]
                   if item["json_pointer"] == "/head/counts/billCount")
    assert finding["change"] == "missing_required_field"
    assert finding["severity"] == "source"
    assert finding["source_evidence"] == {
        "path": raw_path.relative_to(raw_root).as_posix(),
        "sha256": hashlib.sha256(response).hexdigest(),
        "json_pointer": "/head/counts/billCount",
    }


@pytest.mark.parametrize(("endpoint", "count_field"), [
    ("members", "memberCount"),
    ("parties", "partyCount"),
])
def test_live_reconciliation_count_drift_is_preserved_and_reported(
        tmp_path, monkeypatch, endpoint, count_field):
    response = json.dumps({"head": {"counts": {}}, "results": []}).encode()

    class Api:
        def __init__(self, *args, **kwargs):
            pass

        def page(self, *, skip: int, limit: int):
            return ApiPage(response, 200, {"skip": skip, "limit": limit})

    monkeypatch.setattr(cli, "ApiClient", Api)
    raw_root = tmp_path / "raw"
    with pytest.raises(ValueError, match="nonnegative integer advertised count"):
        cli.main(["reconcile", endpoint, "--raw-dir", str(raw_root)])

    raw_path = next(path for path in raw_root.rglob("skip-000000.json")
                    if path.is_file())
    report_path = raw_path.with_name(
        raw_path.name.removesuffix(".json") + ".source-envelope-drift.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    finding = next(item for item in report["findings"]
                   if item["json_pointer"] == f"/head/counts/{count_field}")
    assert finding["endpoint"] == endpoint and finding["severity"] == "source"
    assert finding["source_evidence"]["sha256"] == hashlib.sha256(response).hexdigest()


def test_json_logs_and_immutable_reports_redact_raw_secrets(tmp_path, capsys):
    cli._json_log(
        "secret_test", request_url="https://api.example.test/items?access_token=query-secret",
        authorization="Bearer header-secret", detail="client_secret=inline-secret",
    )
    logged = capsys.readouterr().err
    for secret in ("query-secret", "header-secret", "inline-secret"):
        assert secret not in logged
    assert "[REDACTED]" in logged

    report_path = tmp_path / "report.json"
    cli._persist_immutable_json(report_path, {
        "authorization": "Bearer report-secret",
        "url": "https://api.example.test/items?api_key=url-secret",
        "details": "password=embedded-secret",
    })
    report_text = report_path.read_text(encoding="utf-8")
    for secret in ("report-secret", "url-secret", "embedded-secret"):
        assert secret not in report_text
    assert "[REDACTED]" in report_text


def test_manual_retry_is_automatically_replayed_and_fixtures_do_not_advance_authority(
        tmp_path, monkeypatch, capsys):
    dataset = _patch_fuseki(monkeypatch)
    original = json.loads((ROOT / "data/api_examples/bill.json").read_text())
    good, invalid = json.loads(json.dumps(original["results"][0])), json.loads(
        json.dumps(original["results"][0]))
    invalid["bill"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/bill/2026/998"
    invalid["bill"]["billYear"] = "2026"
    invalid["bill"]["billNo"] = "998"
    invalid["bill"]["lastUpdated"] = 42
    invalid_fixture = tmp_path / "invalid-bills.json"
    invalid_fixture.write_text(json.dumps({
        "head": {"counts": {"billCount": 2}},
        "results": [good, invalid],
    }), encoding="utf-8")
    repaired = json.loads(json.dumps(invalid))
    repaired["bill"]["lastUpdated"] = "2026-01-08T16:24:56.520000+00:00"
    repaired_fixture = tmp_path / "repaired-bills.json"
    repaired_fixture.write_text(json.dumps({
        "head": {"counts": {"billCount": 2}},
        "results": [good, repaired],
    }), encoding="utf-8")
    state_db = tmp_path / "core.sqlite"
    common = [
        "run", "bills", "--state-db", str(state_db),
        "--raw-dir", str(tmp_path / "raw"),
        "--fuseki-gsp-url", "http://fuseki.test/data",
        "--fuseki-sparql-url", "http://fuseki.test/query",
    ]

    assert cli.main([*common, "--fixture", str(invalid_fixture)]) == 0
    with CoreStateStore(state_db) as store:
        quarantined = store.quarantine_records(endpoint="legislation", status="quarantined")
        assert len(quarantined) == 1
        quarantine_id = quarantined[0]["quarantine_id"]
        first_run = store.status()["recent_runs"][0]
        assert first_run["outcome"] == "degraded"
        assert first_run["failure_scope"] == "record"
        assert first_run["summary"]["counters"]["quarantined"] == 1
        assert first_run["summary"]["counters"]["api_requests"] == 0
        assert store.incremental_cursor() is None
        assert store.last_successful_complete_run("legislation") is None

    capsys.readouterr()
    assert cli.main(["quarantine", "list", "--endpoint", "legislation",
                     "--state-db", str(state_db)]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [row["quarantine_id"] for row in listed] == [quarantine_id]
    assert cli.main(["quarantine", "show", quarantine_id,
                     "--state-db", str(state_db)]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["record"]["status"] == "quarantined"
    capsys.readouterr()
    assert cli.main([
        "quarantine", "retry", quarantine_id, "--requested-by", "test-operator",
        "--reason", "source field corrected", "--state-db", str(state_db),
    ]) == 0
    assert cli.main([*common, "--fixture", str(repaired_fixture)]) == 0

    with CoreStateStore(state_db) as store:
        record = next(item for item in store.quarantine_records(status="resolved")
                      if item["quarantine_id"] == quarantine_id)
        assert record["retry_state"] == "succeeded"
        assert record["retry_attempts"] == 1
        assert [item["action"] for item in store.quarantine_history(quarantine_id)] == [
            "quarantined", "retry_requested", "retry_started", "retry_succeeded"]
        assert store.incremental_cursor() is None
        assert store.last_successful_complete_run("legislation") is None
        success = store.status()["recent_runs"][0]
        assert success["outcome"] == "success"
        assert success["summary"]["counters"]["quarantined"] == 0

    # All candidate source graphs were validated and the fixed catalog was
    # replaced through the same verified Fuseki stand-in.
    assert len(list(dataset.graph(URIRef("https://data.oireachtas.ie/graph/provenance")))) > 0


def test_unidentified_quarantine_is_retried_only_after_matching_live_full_scan_reobservation(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl.transforms.members import source_hash

    _patch_fuseki(monkeypatch)
    wrapper = json.loads((ROOT / "data/api_examples/member.json").read_text())
    member = wrapper["member"]
    member.pop("uri")
    body = json.dumps({
        "head": {"counts": {"memberCount": 1}},
        "results": [wrapper],
    }).encode()

    class OnePageApi:
        def __init__(self, *_args, **_kwargs):
            pass

        def page(self, *, skip, limit):
            assert skip == 0
            return ApiPage(body, 200, {"skip": skip, "limit": limit})

    monkeypatch.setattr(cli, "ApiClient", OnePageApi)
    monkeypatch.delenv("OIR_FUSEKI_GSP_URL", raising=False)
    monkeypatch.delenv("OIR_FUSEKI_SPARQL_URL", raising=False)
    database = tmp_path / "state.sqlite"
    common = [
        "run", "members", "--state-db", str(database),
        "--raw-dir", str(tmp_path / "raw"),
        "--office-state-file", str(tmp_path / "office.sqlite"),
        "--fuseki-gsp-url", "http://fuseki.test/data",
        "--fuseki-sparql-url", "http://fuseki.test/query",
    ]

    assert cli.main(common) == 0
    capsys.readouterr()
    with CoreStateStore(database) as store:
        first = store.quarantine_records(endpoint="members", status="quarantined")
        assert len(first) == 1
        quarantine_id = first[0]["quarantine_id"]
        assert first[0]["resource_iri"] is None
        assert first[0]["source_hash"] == source_hash(member)
        assert first[0]["retry_attempts"] == 0
        assert store.last_successful_complete_run("members") is None

    assert cli.main(common) == 0
    capsys.readouterr()
    with CoreStateStore(database) as store:
        retried = next(row for row in store.quarantine_records(endpoint="members")
                       if row["quarantine_id"] == quarantine_id)
        assert retried["status"] == "quarantined"
        assert retried["retry_state"] == "failed"
        assert retried["retry_attempts"] == 1
        history = store.quarantine_history(quarantine_id)
        assert [event["action"] for event in history] == [
            "quarantined", "retry_started", "retry_failed"]
        assert store.last_successful_complete_run("members") is None
        assert store.resources("members") == []


@pytest.mark.parametrize("outcome", ["success", "degraded"])
def test_catalog_failure_marks_run_failed_and_dirty_payload_replays_exactly(
        tmp_path, outcome):
    database = tmp_path / f"{outcome}.sqlite"
    versions = {
        "etl_version": "0.6.0",
        "ontology_version": "2026-10-07",
        "mapping_version": "2026-10-07",
    }
    dataset = Dataset()
    client = _InMemoryFusekiClient(dataset)

    def begin_run(store, run_outcome):
        run_id = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "fixture"}, versions=versions,
        )
        args = SimpleNamespace(_etl_run_context={
            "run_id": run_id,
            "outcome": run_outcome,
            "failure_scope": "record" if run_outcome == "degraded" else None,
            "failure_classification": ("record_transform_failure"
                                       if run_outcome == "degraded" else None),
            "error": "one record was quarantined" if run_outcome == "degraded" else None,
            "safe_publication": True,
            "summary": {"counters": {"quarantined": int(run_outcome == "degraded")},
                        "timings": {}},
        })
        return run_id, args

    class UnavailableLoader:
        def __init__(self, error):
            self.error = error
            self.calls = []

        def replace(self, graph_iri, payload, *, content_type):
            assert graph_iri == PROVENANCE_GRAPH_IRI
            assert content_type == "application/n-triples"
            self.calls.append(payload)
            raise RuntimeError(self.error)

    class CapturingLoader:
        def __init__(self):
            self.calls = []
            self.loader = _InMemoryFusekiLoader(dataset)

        def replace(self, graph_iri, payload, *, content_type):
            assert graph_iri == PROVENANCE_GRAPH_IRI
            assert content_type == "application/n-triples"
            self.calls.append(payload)
            self.loader.replace(graph_iri, payload, content_type=content_type)

    with CoreStateStore(database) as store:
        first_run, first_args = begin_run(store, outcome)
        first_loader = UnavailableLoader("catalog PUT unavailable")
        with pytest.raises(RuntimeError, match="catalog PUT unavailable"):
            cli._finalize_run(
                store, first_args, run_id=first_run, endpoint="members",
                versions=versions, loader=first_loader, client=object(),
            )

        first_state = store.connection.execute(
            "SELECT status,outcome FROM etl_run WHERE run_id=?", (first_run,)
        ).fetchone()
        assert (first_state["status"], first_state["outcome"]) == ("failed", "failed")
        failed_row = store.connection.execute(
            "SELECT failure_scope,failure_classification,summary_json FROM etl_run WHERE run_id=?",
            (first_run,),
        ).fetchone()
        assert failed_row["failure_scope"] == "system"
        assert failed_row["failure_classification"] == "catalog_publication_failure"
        assert json.loads(failed_row["summary_json"])["counters"]["quarantined"] == int(
            outcome == "degraded")
        failure_event = store.provenance_events(
            event_type="run_finished", run_id=first_run)[0]["details"]
        assert failure_event["planned_outcome"] == outcome
        assert failure_event["planned_failure_classification"] == (
            "record_transform_failure" if outcome == "degraded" else None)
        assert failure_event["planned_error"] == (
            "one record was quarantined" if outcome == "degraded" else None)
        assert first_args._etl_run_context["finished"] is True
        pending = store.catalog_publication()
        assert pending["publication_state"] == "dirty"
        exact_payload = pending["pending_payload"]
        assert hashlib.sha256(exact_payload.encode("utf-8")).hexdigest() == pending["pending_payload_hash"]
        first_graph = Graph().parse(data=exact_payload, format="nt")
        activity = URIRef(run_resource_iri(first_run))
        assert str(next(first_graph.objects(activity, ETL.runOutcome))) == "failed"
        archived = store.connection.execute(
            "SELECT payload FROM catalog_publication_attempt WHERE run_id=?", (first_run,)
        ).fetchone()
        assert archived is not None
        attempted_graph = Graph().parse(data=archived["payload"], format="nt")
        assert str(next(attempted_graph.objects(activity, ETL.runOutcome))) == outcome

        # A failed exact replay must finalize the next local run without
        # replacing the older dirty evidence with a different candidate.
        replay_run, replay_args = begin_run(store, "success")
        replay_loader = UnavailableLoader("catalog replay unavailable")
        with pytest.raises(RuntimeError, match="catalog replay unavailable"):
            cli._finalize_run(
                store, replay_args, run_id=replay_run, endpoint="members",
                versions=versions, loader=replay_loader, client=object(),
            )
        replay_state = store.connection.execute(
            "SELECT outcome FROM etl_run WHERE run_id=?", (replay_run,)
        ).fetchone()
        assert replay_state["outcome"] == "failed"
        assert replay_args._etl_run_context["finished"] is True
        assert replay_loader.calls == [exact_payload]
        assert store.catalog_publication()["pending_payload"] == exact_payload

        # A later run replays that exact payload first, then publishes a fresh
        # projection that includes the newly completed local run.
        recovery_run, recovery_args = begin_run(store, "success")
        recovery_loader = CapturingLoader()
        cli._finalize_run(
            store, recovery_args, run_id=recovery_run, endpoint="members",
            versions=versions, loader=recovery_loader, client=client,
        )
        assert recovery_loader.calls[0] == exact_payload
        assert len(recovery_loader.calls) == 2
        assert recovery_loader.calls[1] != exact_payload
        expected_remote = Graph().parse(data=recovery_loader.calls[1], format="nt")
        assert set(client.construct_graph(PROVENANCE_GRAPH_IRI)) == set(expected_remote)
        assert len(dataset.graph(URIRef(PROVENANCE_GRAPH_IRI))) > 0
        final_state = store.catalog_publication()
        assert final_state["publication_state"] == "clean"
        assert final_state["published_payload"] == recovery_loader.calls[1]
        assert store.connection.execute(
            "SELECT outcome FROM etl_run WHERE run_id=?", (recovery_run,)
        ).fetchone()["outcome"] == "success"


def test_catalog_build_failure_fails_run_and_does_not_advance_authority(
        tmp_path, monkeypatch):
    database = tmp_path / "catalog-build.sqlite"
    versions = {"etl_version": "0.6.0", "ontology_version": "v1", "mapping_version": "v1"}
    with CoreStateStore(database) as store:
        run_id = store.start_run(
            "legislation", "incremental_refresh", is_complete=False,
            parameters={"source": "api"}, versions=versions,
        )
        args = SimpleNamespace(_etl_run_context={
            "run_id": run_id,
            "outcome": "success",
            "safe_publication": True,
            "incremental_cursor": "2026-10-07T12:00:00Z",
            "summary": {"counters": {"extracted": 3}, "timings": {}},
        })
        monkeypatch.setattr(
            cli, "_catalog_payload_for_final_outcome",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                ValueError("invalid provenance catalog source record")),
        )

        with pytest.raises(ValueError, match="invalid provenance catalog"):
            cli._finalize_run(
                store, args, run_id=run_id, endpoint="legislation",
                versions=versions, loader=object(), client=object(),
            )

        run = store.connection.execute(
            "SELECT status,outcome,error,failure_scope,failure_classification,summary_json "
            "FROM etl_run WHERE run_id=?", (run_id,),
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("failed", "failed")
        assert run["failure_scope"] == "system"
        assert run["failure_classification"] == "catalog_publication_failure"
        assert "invalid provenance catalog" in run["error"]
        assert json.loads(run["summary_json"])["counters"]["extracted"] == 3
        assert store.incremental_cursor() is None
        assert store.catalog_publication() is None
        assert args._etl_run_context["finished"] is True


def test_catalog_verification_failure_fails_run_and_stages_failed_projection(
        tmp_path, monkeypatch):
    database = tmp_path / "catalog-verification.sqlite"
    versions = {"etl_version": "0.6.0", "ontology_version": "v1", "mapping_version": "v1"}
    attempted = []

    class Loader:
        def replace(self, graph_iri, payload, *, content_type):
            assert graph_iri == PROVENANCE_GRAPH_IRI
            assert content_type == "application/n-triples"
            attempted.append(payload)

    def reject_verification(_client, graph_iri, payload):
        assert graph_iri == PROVENANCE_GRAPH_IRI
        assert attempted[-1] == payload
        raise RuntimeError("catalog graph verification mismatch")

    monkeypatch.setattr(cli, "verify_core_graph", reject_verification)
    with CoreStateStore(database) as store:
        run_id = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "fixture"}, versions=versions,
        )
        args = SimpleNamespace(_etl_run_context={
            "run_id": run_id, "outcome": "success", "safe_publication": True,
            "summary": {"counters": {"published_graphs": 2}, "timings": {}},
        })

        with pytest.raises(RuntimeError, match="verification mismatch"):
            cli._finalize_run(
                store, args, run_id=run_id, endpoint="members",
                versions=versions, loader=Loader(), client=object(),
            )

        run = store.connection.execute(
            "SELECT status,outcome,failure_classification,summary_json FROM etl_run WHERE run_id=?",
            (run_id,),
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("failed", "failed")
        assert run["failure_classification"] == "catalog_publication_failure"
        assert json.loads(run["summary_json"])["counters"]["published_graphs"] == 2
        pending = store.catalog_publication()
        assert pending["publication_state"] == "dirty"
        failed_graph = Graph().parse(data=pending["pending_payload"], format="nt")
        activity = URIRef(run_resource_iri(run_id))
        assert str(next(failed_graph.objects(activity, ETL.runOutcome))) == "failed"
        archived = store.connection.execute(
            "SELECT payload FROM catalog_publication_attempt WHERE run_id=?", (run_id,)
        ).fetchone()
        assert archived["payload"] == attempted[0]


@pytest.mark.parametrize("fail_catalog", [False, True])
def test_fatal_second_debate_put_persists_failed_catalog_projection_and_summary(
        tmp_path, monkeypatch, capsys, fail_catalog):
    from oireachtas_etl.debates_raw import persist_main_xml
    from tests._in_memory_fuseki import InMemoryFuseki

    def source_bytes(suffix: str) -> bytes:
        work = f"/akn/ie/debateRecord/dail/2026-10-06/cli-failure-{suffix}"
        expression = work + "/mul@"
        return (
            "<akomaNtoso><debate><meta><identification>"
            f"<FRBRWork><FRBRuri value={json.dumps(work)}/>"
            '<FRBRdate name="#generation" date="2026-10-06"/>'
            '<FRBRname value="debate"/></FRBRWork>'
            f"<FRBRExpression><FRBRuri value={json.dumps(expression)}/>"
            '<FRBRlanguage language="eng"/></FRBRExpression>'
            "</identification></meta><debateBody>"
            f'<debateSection eId="section" name="debate"><speech eId="{suffix}"/></debateSection>'
            "</debateBody></debate></akomaNtoso>"
        ).encode("utf-8")

    raw_root = tmp_path / "raw"
    sources = [
        persist_main_xml(raw_root, source_bytes(suffix),
                         f"https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-10-06/cli-failure-{suffix}/mul@/main.xml")
        for suffix in ("one", "two")
    ]
    database = tmp_path / "fatal-debates.sqlite"
    secret = "super-secret-value"
    debate_puts: list[str] = []
    catalog_payloads: list[str] = []
    fuseki = InMemoryFuseki()

    class FailSecondDebatePut:
        def __init__(self, *_args, **_kwargs):
            pass

        def replace(self, graph_iri, payload, *, content_type):
            assert content_type == "application/n-triples"
            if graph_iri == PROVENANCE_GRAPH_IRI:
                catalog_payloads.append(payload)
                if fail_catalog:
                    raise RuntimeError(f"catalog PUT failed client_secret={secret}")
                fuseki.replace(graph_iri, payload, content_type=content_type)
                return
            debate_puts.append(graph_iri)
            if len(debate_puts) == 2:
                raise RuntimeError(f"remote PUT failed client_secret={secret}")
            fuseki.replace(graph_iri, payload, content_type=content_type)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", FailSecondDebatePut)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *_args, **_kwargs: fuseki)

    command = [
        "run", "debates", "--publish", "--raw-dir", str(raw_root),
        "--state-db", str(database), "--fuseki-gsp-url", "http://fuseki.test/data",
        "--fuseki-sparql-url", "http://fuseki.test/query",
    ]
    for source in sources:
        command.extend(("--replay", source.source_sha256))

    with pytest.raises(RuntimeError, match="remote PUT failed"):
        cli.main(command)

    logged = capsys.readouterr().err
    assert secret not in logged
    with CoreStateStore(database) as store:
        run = store.connection.execute(
            "SELECT run_id,status,outcome,error,failure_classification,summary_json "
            "FROM etl_run WHERE endpoint='debates'"
        ).fetchone()
        assert (run["status"], run["outcome"]) == ("failed", "failed")
        assert secret not in run["error"]
        assert "[REDACTED]" in run["error"]
        summary = json.loads(run["summary_json"])
        counters = summary["counters"]
        assert counters["extracted"] == 2
        assert counters["published_graphs"] == 1
        assert counters["changed"] == 0
        assert counters["publication_succeeded"] == 0
        assert {
            "extracted", "changed", "unchanged", "published_graphs",
            "quarantined", "validation_failures", "api_requests", "api_failures",
            "external_requests", "external_failures", "publication_succeeded",
        } <= counters.keys()
        assert summary["timings"]["etl_stage_seconds"] >= 0
        assert run["failure_classification"] == "system_failure"

        resources = store.resources("debates")
        assert sorted(row["publication_state"] for row in resources) == ["clean", "dirty"]
        assert store.last_successful_complete_run("debates") is None
        versions = store.graph_versions()
        assert len(versions) == 1
        assert versions[0]["first_run_id"] == run["run_id"]
        assert store.incremental_cursor() is None
        finished = store.provenance_events(event_type="run_finished", run_id=run["run_id"])
        assert len(finished) == 1
        assert secret not in finished[0]["details"]["error"]

        assert len(catalog_payloads) == 1
        catalog = store.catalog_publication()
        if fail_catalog:
            assert catalog["publication_state"] == "dirty"
            exact_payload = catalog["pending_payload"]
            assert exact_payload == catalog_payloads[0]
            assert hashlib.sha256(exact_payload.encode("utf-8")).hexdigest() == (
                catalog["pending_payload_hash"])

            class ReplayLoader:
                def replace(self, graph_iri, payload, *, content_type):
                    assert graph_iri == PROVENANCE_GRAPH_IRI
                    assert content_type == "application/n-triples"
                    fuseki.replace(graph_iri, payload, content_type=content_type)
                    catalog_payloads.append(payload)

            replay = ReplayLoader()
            payload_count = len(catalog_payloads)
            assert cli._replay_pending_catalog(store, loader=replay, client=fuseki)
            assert catalog_payloads[payload_count:] == [exact_payload]
            assert store.catalog_publication()["publication_state"] == "clean"
        else:
            assert catalog["publication_state"] == "clean"
            assert catalog["pending_payload"] is None
        catalog_graph = Graph().parse(data=catalog_payloads[0], format="nt")
        activity = URIRef(run_resource_iri(run["run_id"]))
        assert str(next(catalog_graph.objects(activity, ETL.runStatus))) == "failed"
        assert str(next(catalog_graph.objects(activity, ETL.runOutcome))) == "failed"
        assert len(set(catalog_graph.subjects(PROV.wasGeneratedBy, activity))) == 1
def test_process_command_redacts_secret_bearing_traceback(tmp_path):
    """The installed command's no-argv boundary must not print raw exceptions."""
    import subprocess
    import sys

    missing = tmp_path / "api_key=CANARY_SECRET_DO_NOT_PRINT.json"
    completed = subprocess.run(
        [sys.executable, "-m", "oireachtas_etl.cli", "run", "houses",
         "--fixture", str(missing), "--offline"],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 1
    assert "CANARY_SECRET_DO_NOT_PRINT" not in completed.stderr
    assert "Traceback" not in completed.stderr
    assert '"event": "command_failed"' in completed.stderr
