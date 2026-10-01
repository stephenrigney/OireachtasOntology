"""Phase 5 legislation cursor, presence and whole-graph acceptance."""
from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef

from oireachtas_etl.api import ApiPage
from oireachtas_etl.competency import verify_core_graph
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.bills import bill_graph_iri, source_hash


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]


def _args(tmp_path, *, full=False):
    return Namespace(fixture=None, offline=False, full=full, overlap_seconds=3600,
                     raw_dir=str(tmp_path / "raw"), state_db=str(tmp_path / "core.sqlite"),
                     output_nq=None, output_ttl=None,
                     fuseki_gsp_url="http://local.test/data",
                     fuseki_sparql_url="http://local.test/query")


def _fake_online(monkeypatch, records, calls, *, fail=False):
    from oireachtas_etl import cli
    class Api:
        def __init__(self, *args, **kwargs): pass
        def harvest(self, *, limit, query_params=None):
            calls.append(("extract", dict(query_params or {})))
            selected = records()
            body = json.dumps({"head": {"counts": {"billCount": len(selected)}},
                               "results": selected}).encode()
            yield ApiPage(body, 200, {"skip": 0, "limit": limit, **(query_params or {})})
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, graph, payload, **kwargs):
            calls.append(("put", graph))
            if fail:
                raise RuntimeError("PUT failed")
    monkeypatch.setattr(cli, "ApiClient", Api)
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)


def test_incremental_fixed_boundary_overlap_dedup_and_no_missing_inference(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    calls = []
    records = [WRAPPER]
    _fake_online(monkeypatch, lambda: records, calls)
    args = _args(tmp_path)
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        first = store.incremental_cursor()
        assert first == store.status()["recent_runs"][0]["parameters"]["upper_boundary"]
    assert len([call for call in calls if call[0] == "put"]) == 1

    records[:] = [WRAPPER, WRAPPER]  # repeated identity in an overlapping page
    assert cli.run_bills(args) == 0
    assert len([call for call in calls if call[0] == "put"]) == 1
    assert calls[-1][0] == "extract" and "last_updated" in calls[-1][1]
    assert datetime.fromisoformat(calls[-1][1]["last_updated"]) < datetime.fromisoformat(first)
    pages = sorted((tmp_path / "raw" / "legislation").rglob("skip-000000.json"))
    assert len(pages) == 2 and pages[0] != pages[1]
    assert all("run-" in str(page) for page in pages)

    records.clear()
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        row = store.get_resource("legislation", WRAPPER["bill"]["uri"])
        assert row["source_presence"] == "present"
        assert row["published_source_hash"] == source_hash(WRAPPER["bill"])


def test_failed_put_and_crash_before_cursor_completion_retry_safely(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    calls = []
    _fake_online(monkeypatch, lambda: [WRAPPER], calls, fail=True)
    args = _args(tmp_path)
    with pytest.raises(RuntimeError, match="PUT failed"):
        cli.run_bills(args)
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.incremental_cursor() is None
        assert store.get_resource("legislation", WRAPPER["bill"]["uri"])["publication_state"] == "dirty"

    _fake_online(monkeypatch, lambda: [WRAPPER], calls)
    original = CoreStateStore.finish_run
    crashed = {"yes": False}
    def interrupt(self, run_id, **kwargs):
        if kwargs["success"] and not crashed["yes"]:
            crashed["yes"] = True
            raise RuntimeError("crash before cursor commit")
        return original(self, run_id, **kwargs)
    monkeypatch.setattr(CoreStateStore, "finish_run", interrupt)
    with pytest.raises(RuntimeError, match="crash before cursor commit"):
        cli.run_bills(args)
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.incremental_cursor() is None
        assert store.get_resource("legislation", WRAPPER["bill"]["uri"])["publication_state"] == "clean"
    assert cli.run_bills(args) == 0
    assert len([call for call in calls if call[0] == "put"]) == 2
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.incremental_cursor() is not None


def test_complete_reconciliation_requires_two_successful_absences_and_never_deletes(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    calls = []
    records = [WRAPPER]
    _fake_online(monkeypatch, lambda: records, calls)
    args = _args(tmp_path)
    assert cli.run_bills(args) == 0
    known = WRAPPER["bill"]["uri"]
    cursor = None
    with CoreStateStore(Path(args.state_db)) as store:
        cursor = store.incremental_cursor()
    # A genuine complete scan with an empty advertised source is sufficient to
    # observe absence once, but never authorises graph deletion.
    records.clear()
    args.full = True
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.get_resource("legislation", known)["source_presence"] == "missing"
        assert store.incremental_cursor() == cursor
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.get_resource("legislation", known)["source_presence"] == "confirmed_missing"
        assert store.get_resource("legislation", known)["published_source_hash"] is not None
    assert len([call for call in calls if call[0] == "put"]) == 1


def test_whole_graph_verification_rejects_same_count_wrong_content():
    subject, predicate = URIRef("https://example.test/s"), URIRef("https://example.test/p")
    expected = Graph(); expected.add((subject, predicate, Literal("right")))
    from oireachtas_etl.serialization import ntriples
    class Client:
        def query(self, sparql):
            return [{"s": {"type": "uri", "value": str(subject)},
                     "p": {"type": "uri", "value": str(predicate)},
                     "o": {"type": "literal", "value": "wrong"}}]
    with pytest.raises(ValueError, match="graph/state mismatch"):
        verify_core_graph(Client(), "https://data.oireachtas.ie/graph/bill/2026/1", ntriples(expected))


def test_clean_graph_mismatch_is_repaired_with_verified_whole_graph_replacement(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    from oireachtas_etl.serialization import ntriples
    calls = []
    remote = {}
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, graph_iri, payload, **kwargs):
            calls.append(graph_iri)
            remote[graph_iri] = Graph().parse(data=payload, format="nt")
    class Client:
        def __init__(self, *args, **kwargs): pass
        def query(self, query):
            graph_iri = query.split("GRAPH <", 1)[1].split(">", 1)[0]
            def binding(term):
                if isinstance(term, URIRef): return {"type": "uri", "value": str(term)}
                value = {"type": "literal", "value": str(term)}
                if term.language: value["xml:lang"] = term.language
                if term.datatype: value["datatype"] = str(term.datatype)
                return value
            return [{"s": binding(s), "p": binding(p), "o": binding(o)}
                    for s, p, o in remote.get(graph_iri, Graph())]
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: None)
    args = _args(tmp_path)
    args.fixture = str(ROOT / "data/api_examples/bill.json")
    assert cli.run_bills(args) == 0
    graph_iri = bill_graph_iri(WRAPPER["bill"])
    original = ntriples(remote[graph_iri]); count = len(remote[graph_iri])
    remote[graph_iri].remove(next(iter(remote[graph_iri])))
    remote[graph_iri].add((URIRef("https://example.test/stale"),
                           URIRef("https://example.test/p"), Literal("wrong")))
    assert len(remote[graph_iri]) == count
    assert cli.run_bills(args) == 0
    assert len(calls) == 2
    assert ntriples(remote[graph_iri]) == original
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.get_resource("legislation", WRAPPER["bill"]["uri"])["publication_state"] == "clean"


def test_incremental_upper_bound_ignores_future_bill_without_cursor_gap(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    future = json.loads(json.dumps(WRAPPER))
    future["bill"]["lastUpdated"] = "2099-01-01T00:00:00+00:00"
    calls = []
    _fake_online(monkeypatch, lambda: [future], calls)
    args = _args(tmp_path)
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.incremental_cursor() is not None
        assert store.get_resource("legislation", WRAPPER["bill"]["uri"]) is None
    assert not [call for call in calls if call[0] == "put"]


def test_partial_online_fixture_cannot_advance_source_cursor_or_establish_absence(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    calls = []
    _fake_online(monkeypatch, lambda: [], calls)
    bill_fixture = tmp_path / "bill.json"
    bill_fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}},
                                        "results": [WRAPPER]}))
    args = _args(tmp_path)
    args.fixture = str(bill_fixture)
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.incremental_cursor() is None
        assert store.get_resource("legislation", WRAPPER["bill"]["uri"])["source_presence"] == "present"
    bill_fixture.write_text(json.dumps({"head": {"counts": {"billCount": 0}}, "results": []}))
    args.full = True
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.incremental_cursor() is None
        assert store.get_resource("legislation", WRAPPER["bill"]["uri"])["source_presence"] == "present"
        assert store.status()["recent_runs"][0]["parameters"]["source"] == "fixture"
