"""Tranche 4 exact-source, Core State and graph-publication acceptance."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import uuid

import pytest
from rdflib import Graph, URIRef

from oireachtas_etl import competency, debates_pipeline
from oireachtas_etl import cli as etl_cli
from oireachtas_etl.cli import main
from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH
from oireachtas_etl.debates_pipeline import run_debate_batch
from oireachtas_etl.debates_raw import (
    DebateSourceError,
    fetch_main_xml,
    load_main_xml,
    persist_main_xml,
    validate_main_xml_url,
    validate_source_expression_url,
    verify_reference_report,
)
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateError, CoreStateStore, expected_graph_iri
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.debates import inspect_debate_source_identity
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.members import member_graph_iri, transform_member
from oireachtas_etl.transforms.common import OIR
from oireachtas_etl.validation.committees import validate_committees
from oireachtas_etl.validation.houses import validate_houses
from oireachtas_etl.validation.members import validate_member


ROOT = Path(__file__).resolve().parents[1]
DEBATE_DIR = ROOT / "data" / "debates_examples"
MEMBER_HREF = "/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12"
DAIL_34_HREF = "/ie/oireachtas/house/dail/34"


def _source(*, work="/akn/ie/debateRecord/dail/2026-10-06/tranche-4-test",
            expression=None, speech="old") -> bytes:
    expression = expression or work + "/mul@"
    return (
        "<akomaNtoso><debate><meta><identification>"
        f"<FRBRWork><FRBRuri value={json.dumps(work)}/>"
        '<FRBRdate name="#generation" date="2026-10-06"/>'
        '<FRBRname value="debate"/></FRBRWork>'
        f"<FRBRExpression><FRBRuri value={json.dumps(expression)}/>"
        '<FRBRlanguage language="eng"/></FRBRExpression>'
        "</identification></meta><debateBody>"
        f'<debateSection eId="section" name="debate"><speech eId="{speech}"/></debateSection>'
        "</debateBody></debate></akomaNtoso>"
    ).encode("utf-8")


def _source_url(source: bytes) -> str:
    expression = inspect_debate_source_identity(source)["expression_iri"]
    return expression + "/main.xml"


def _preserved_source(raw_root: Path, source: bytes, url: str | None = None):
    return persist_main_xml(raw_root, source, url or _source_url(source))


def _seed_owners(store: CoreStateStore, remote: dict[str, Graph] | None = None) -> dict[str, Graph]:
    member_source = json.loads((ROOT / "data/api_examples/member.json").read_text())
    houses_source = json.loads((ROOT / "data/api_examples/houses.json").read_text())
    committees_source = json.loads((ROOT / "tests/fixtures/committee-owner.json").read_text())
    member_graph = transform_member(member_source)
    house_graph = transform_houses(houses_source)
    committee_graph = transform_committees(committees_source)
    validate_member(member_source, member_graph)
    validate_houses(houses_source, house_graph)
    validate_committees(committees_source, committee_graph)

    owners = {
        HOUSES_GRAPH: house_graph,
        COMMITTEES_GRAPH: committee_graph,
        member_graph_iri(member_source["member"]): member_graph,
    }
    if remote is not None:
        for graph_iri, graph in owners.items():
            remote[graph_iri] = Graph(identifier=URIRef(graph_iri))
            for triple in graph:
                remote[graph_iri].add(triple)

    for endpoint, graph_iri, graph in (
        ("houses", HOUSES_GRAPH, house_graph),
        ("committees", COMMITTEES_GRAPH, committee_graph),
    ):
        payload = ntriples(graph)
        digest = store.mark_endpoint_dirty(endpoint, graph_iri, payload)
        store.complete_endpoint_publication(endpoint, graph_iri, digest)

    member = member_source["member"]
    run_id = store.start_run("members", "full_refresh", is_complete=False,
                             parameters={"source": "test-fixture"})
    identity = member["uri"]
    graph_iri = member_graph_iri(member)
    member_source_hash = hashlib.sha256(
        json.dumps(member, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    store.observe_resource("members", identity, graph_iri, member_source_hash, run_id)
    payload = ntriples(member_graph)
    digest = store.mark_publication_dirty(
        "members", identity, source_hash=member_source_hash,
        graph_iri=graph_iri, payload=payload, contract_version=3)
    store.complete_publication(
        "members", identity, source_hash=member_source_hash, graph_iri=graph_iri,
        payload_hash=digest, contract_version=3)
    store.finish_run(run_id, success=True)
    return owners


def _run(store, sources, remote, *, loader=None, client=object()):
    run_id = store.start_run(
        "debates", "incremental_refresh", is_complete=False,
        parameters={"source": "test-supplied-main-xml"},
    )
    loader = loader or _MemoryLoader(remote)
    try:
        result = run_debate_batch(
            sources, store=store, run_id=run_id, publish=True,
            loader=loader, client=client,
        )
    except Exception as error:
        store.finish_run(run_id, success=False,
                         error=f"{type(error).__name__}: {error}")
        raise
    store.finish_run(run_id, success=True)
    return result


class _MemoryLoader:
    def __init__(self, remote: dict[str, Graph], *, fail=False):
        self.remote = remote
        self.fail = fail
        self.puts: list[str] = []
        self.payloads: list[str] = []

    def replace(self, graph_iri: str, payload: str, *, content_type: str):
        assert content_type == "application/n-triples"
        self.puts.append(graph_iri)
        self.payloads.append(payload)
        if self.fail:
            raise RuntimeError("injected GSP PUT failure")
        graph = Graph(identifier=URIRef(graph_iri))
        graph.parse(data=payload, format="nt")
        self.remote[graph_iri] = graph


def _memory_verify(remote: dict[str, Graph]):
    def verify(_client, graph_iri: str, payload: str):
        expected = Graph()
        expected.parse(data=payload, format="nt")
        actual = remote.get(graph_iri, Graph())
        if set(expected) != set(actual):
            raise ValueError(f"core graph/state mismatch for {graph_iri}")
    return verify


def test_content_addressed_raw_xml_is_exact_immutable_and_replayable(tmp_path):
    source = _source()
    source_url = _source_url(source)
    captured = _preserved_source(tmp_path / "raw", source, source_url)
    expected = hashlib.sha256(source).hexdigest()
    assert captured.source_sha256 == expected
    assert captured.raw_path.name == expected + ".xml"
    assert captured.raw_path.read_bytes() == source
    assert load_main_xml(tmp_path / "raw", expected).body == source
    same = _preserved_source(tmp_path / "raw", source, source_url)
    assert same.raw_path == captured.raw_path
    captured.raw_path.write_bytes(source + b" ")
    with pytest.raises(DebateSourceError, match="content hash"):
        load_main_xml(tmp_path / "raw", expected)


def test_acquisition_requires_main_xml_and_exact_expression_object_path():
    source = _source()
    identity = inspect_debate_source_identity(source)
    good = _source_url(source)
    validate_main_xml_url(good)
    validate_source_expression_url(good, identity["expression_iri"])
    with pytest.raises(DebateSourceError, match="main.xml"):
        validate_main_xml_url(good.removesuffix("main.xml") + "section-1.xml")
    section_url = good.replace("/mul%40/", "/section-1/mul%40/")
    validate_main_xml_url(section_url)
    with pytest.raises(DebateSourceError, match="exact FRBRExpression"):
        validate_source_expression_url(section_url, identity["expression_iri"])


def test_fetch_uses_only_supplied_main_xml_and_rejects_nonofficial_redirect(monkeypatch):
    import oireachtas_etl.debates_raw as raw_module

    source = _source()
    source_url = _source_url(source)
    requested: list[tuple[str, str | None]] = []
    final_url = source_url

    class Response:
        status = 200

        def geturl(self):
            return final_url

        def read(self):
            return source

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_urlopen(request, *, timeout):
        requested.append((request.full_url, request.get_header("Accept")))
        assert timeout == 2
        return Response()

    monkeypatch.setattr(raw_module, "urlopen", fake_urlopen)
    body, fetched_url = fetch_main_xml(source_url, retries=0, timeout=2)
    assert body == source and fetched_url == source_url
    assert requested == [(source_url, "application/xml, text/xml")]

    final_url = "https://attacker.example/akn/ie/debateRecord/dail/x/main.xml"
    with pytest.raises(DebateSourceError, match="official /akn/ie/debateRecord"):
        fetch_main_xml(source_url, retries=0, timeout=2)


def test_debates_graph_identity_is_exact_and_only_work_paths_are_accepted():
    source = _source()
    identity = inspect_debate_source_identity(source)
    assert expected_graph_iri("debates", identity["work_iri"]) == (
        "https://data.oireachtas.ie/graph/debate/dail/2026-10-06/tranche-4-test")
    for bad in (
        "https://data.oireachtas.ie/akn/ie/debateRecord/dail//work",
        "https://data.oireachtas.ie/akn/ie/debateRecord/dail/%2f/work",
        "https://data.oireachtas.ie/akn/ie/debateRecord/dail/../work",
        "https://data.oireachtas.ie/akn/ie/debateRecord/dail/work?x=1",
    ):
        with pytest.raises(CoreStateError):
            expected_graph_iri("debates", bad)


@pytest.mark.parametrize("offline", [False, True])
def test_unpublished_cli_replay_never_opens_publisher_or_core_state(
        tmp_path, monkeypatch, capsys, offline):
    source = _source()
    preserved = _preserved_source(tmp_path / "raw", source)
    monkeypatch.setenv("OIR_FUSEKI_GSP_URL", "http://127.0.0.1:13035/debates_t4/data")

    class ForbiddenLoader:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("unpublished Debates invocation must not construct a GSP publisher")

    class ForbiddenState:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("unpublished Debates invocation must not open Core State")

    monkeypatch.setattr(etl_cli, "FusekiGraphStoreLoader", ForbiddenLoader)
    monkeypatch.setattr(etl_cli, "CoreStateStore", ForbiddenState)
    command = ["run", "debates", "--raw-dir", str(tmp_path / "raw"),
               "--replay", preserved.source_sha256, "--state-db",
               str(tmp_path / "must-not-exist.sqlite")]
    if offline:
        command.append("--offline")
    assert main(command) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["published"] is False and report["run_id"] is None
    assert report["work_records"][0]["status"] == "new"
    assert not (tmp_path / "must-not-exist.sqlite").exists()


def test_published_debates_run_persists_hash_identified_ontology_and_mapping_versions(
        tmp_path, monkeypatch, capsys):
    import hashlib

    from oireachtas_etl.state import CoreStateStore

    preserved = _preserved_source(tmp_path / "raw", _source())
    database = tmp_path / "published.sqlite"
    monkeypatch.setattr(etl_cli, "FusekiGraphStoreLoader", lambda *_a, **_k: object())
    monkeypatch.setattr(etl_cli, "FusekiSparqlClient", lambda *_a, **_k: object())
    monkeypatch.setattr(etl_cli, "run_debate_batch", lambda *_a, **_k: [])

    def finalize(store, _args, *, run_id, **_kwargs):
        store.finish_run(run_id, success=True)

    monkeypatch.setattr(etl_cli, "_finalize_run", finalize)
    assert main([
        "run", "debates", "--publish", "--replay", preserved.source_sha256,
        "--raw-dir", str(tmp_path / "raw"), "--state-db", str(database),
        "--fuseki-gsp-url", "http://fuseki.test/data",
        "--fuseki-sparql-url", "http://fuseki.test/query",
    ]) == 0
    capsys.readouterr()

    expected_ontology = "debates.owl.ttl@sha256:" + hashlib.sha256(
        (ROOT / "ontology" / "debates.owl.ttl").read_bytes()).hexdigest()
    expected_mapping = "debates_mapping.csv@sha256:" + hashlib.sha256(
        (ROOT / "mappings" / "debates_mapping.csv").read_bytes()).hexdigest()
    with CoreStateStore(database) as store:
        run = store.status()["recent_runs"][0]
    assert run["endpoint"] == "debates" and run["outcome"] == "success"
    assert run["ontology_version"] == expected_ontology
    assert run["mapping_version"] == expected_mapping


def test_first_replay_skip_changed_replacement_and_owner_isolation(tmp_path, monkeypatch):
    from oireachtas_etl.state import CoreStateStore

    remote: dict[str, Graph] = {}
    database = tmp_path / "state.sqlite"
    source = _source()
    first_input = _preserved_source(tmp_path / "raw", source)
    with CoreStateStore(database) as store:
        owners = _seed_owners(store, remote)
        owner_before = {key: frozenset(graph) for key, graph in remote.items()}
        loader = _MemoryLoader(remote)
        monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))

        first = _run(store, [first_input], remote, loader=loader)
        assert first[0].status == "new" and loader.puts == [first[0].graph_iri]
        state = store.get_resource("debates", first[0].work_iri)
        assert state["publication_state"] == "clean"
        assert state["published_source_hash"] == first_input.source_sha256
        assert state["raw_source_path"] == str(first_input.raw_path.resolve())
        assert state["source_url"] == _source_url(source)
        assert state["published_resolver_version"].startswith("owner-rdf-registry-v1:")
        assert state["published_owner_snapshot_hash"]
        assert state["published_reference_report_path"]
        report_path = Path(state["published_reference_report_path"])
        report_bytes = report_path.read_bytes()
        assert hashlib.sha256(report_bytes).hexdigest() == state["published_reference_report_hash"]
        assert json.loads(report_bytes.decode("utf-8"))["source_sha256"] == first_input.source_sha256
        verify_reference_report(
            report_path, state["published_reference_report_hash"],
            source_sha256=first_input.source_sha256,
            resolver_version=state["published_resolver_version"],
            owner_snapshot_hash=state["published_owner_snapshot_hash"],
        )
        assert b"<akomaNtoso" not in repr(state).encode("utf-8")

        transform_calls = 0
        original_transform = debates_pipeline.transform_debate

        def counted_transform(*args, **kwargs):
            nonlocal transform_calls
            transform_calls += 1
            return original_transform(*args, **kwargs)

        monkeypatch.setattr(debates_pipeline, "transform_debate", counted_transform)
        replay = load_main_xml(tmp_path / "raw", first_input.source_sha256)
        second = _run(store, [replay], remote, loader=loader)
        assert second[0].status == "skipped"
        assert transform_calls == 0
        assert loader.puts == [first[0].graph_iri]

        changed_source = _source(speech="new")
        changed_input = _preserved_source(tmp_path / "raw", changed_source)
        changed = _run(store, [changed_input], remote, loader=loader)
        assert changed[0].status == "changed"
        assert loader.puts == [first[0].graph_iri, first[0].graph_iri]
        expression_iri = inspect_debate_source_identity(source)["expression_iri"]
        assert URIRef(expression_iri + "/eid/e-old") not in set(remote[first[0].graph_iri].subjects())
        assert URIRef(expression_iri + "/eid/e-new") in set(remote[first[0].graph_iri].subjects())
        clean = store.get_resource("debates", first[0].work_iri)
        assert clean["publication_state"] == "clean"
        assert clean["published_source_hash"] == changed_input.source_sha256
        assert {key: frozenset(remote[key]) for key in owners} == owner_before

        distinct_expression = _source(
            work=inspect_debate_source_identity(source)["source_work_uri"],
            expression="/akn/ie/debateRecord/dail/2026-10-06/tranche-4-test/ga@",
            speech="alternate-expression",
        )
        alternate_input = _preserved_source(tmp_path / "raw", distinct_expression)
        with pytest.raises(DebateSourceError, match="multiple known Expressions"):
            _run(store, [alternate_input], remote, loader=loader)
        after_rejection = store.get_resource("debates", first[0].work_iri)
        assert after_rejection["expression_iri"] == expression_iri
        assert after_rejection["published_source_hash"] == changed_input.source_sha256
        assert loader.puts == [first[0].graph_iri, first[0].graph_iri]


def test_reference_report_survives_close_reopen_and_clean_skip(tmp_path, monkeypatch):
    remote: dict[str, Graph] = {}
    database = tmp_path / "state.sqlite"
    source = _source()
    preserved = _preserved_source(tmp_path / "raw", source)
    loader = _MemoryLoader(remote)
    monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))

    with CoreStateStore(database) as store:
        _seed_owners(store, remote)
        first = _run(store, [preserved], remote, loader=loader)[0]
        published = store.get_resource("debates", first.work_iri)
        report_path = Path(published["published_reference_report_path"])
        report_hash = published["published_reference_report_hash"]
        report_bytes = report_path.read_bytes()

    with CoreStateStore(database) as reopened:
        replay = load_main_xml(tmp_path / "raw", preserved.source_sha256)
        second = _run(reopened, [replay], remote, loader=loader)[0]
        current = reopened.get_resource("debates", first.work_iri)
        assert second.status == "skipped"
        assert loader.puts == [first.graph_iri]
        assert current["published_reference_report_path"] == str(report_path)
        assert current["published_reference_report_hash"] == report_hash
        assert report_path.read_bytes() == report_bytes
        verify_reference_report(
            report_path, report_hash, source_sha256=preserved.source_sha256,
            resolver_version=current["published_resolver_version"],
            owner_snapshot_hash=current["published_owner_snapshot_hash"],
        )


def test_same_source_replay_repairs_remote_graph_corruption(tmp_path, monkeypatch):
    remote: dict[str, Graph] = {}
    source = _source()
    preserved = _preserved_source(tmp_path / "raw", source)
    loader = _MemoryLoader(remote)
    monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))

    with CoreStateStore(tmp_path / "state.sqlite") as store:
        _seed_owners(store, remote)
        first = _run(store, [preserved], remote, loader=loader)[0]
        expected_payload = ntriples(first.graph)
        remote[first.graph_iri].add((
            URIRef("https://data.oireachtas.ie/corrupt-debate-subject"),
            URIRef("https://example.test/corrupt-predicate"),
            URIRef("https://example.test/corrupt-object"),
        ))

        replay = _run(
            store, [load_main_xml(tmp_path / "raw", preserved.source_sha256)],
            remote, loader=loader,
        )[0]
        assert replay.status == "changed"
        assert loader.puts == [first.graph_iri, first.graph_iri]
        assert loader.payloads == [expected_payload, expected_payload]
        assert set(remote[first.graph_iri]) == set(first.graph)
        assert store.get_resource("debates", first.work_iri)["publication_state"] == "clean"


def test_dirty_put_failure_and_verification_failure_remain_dirty_then_retry(tmp_path, monkeypatch):
    remote: dict[str, Graph] = {}
    source = _source()
    preserved = _preserved_source(tmp_path / "raw", source)
    monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        _seed_owners(store)
        failing = _MemoryLoader(remote, fail=True)
        with pytest.raises(RuntimeError, match="injected GSP PUT failure"):
            _run(store, [preserved], remote, loader=failing)
        work = inspect_debate_source_identity(source)["work_iri"]
        dirty = store.get_resource("debates", work)
        assert dirty["publication_state"] == "dirty"
        assert dirty["pending_source_hash"] == preserved.source_sha256
        assert dirty["pending_payload"] and dirty["pending_payload_hash"]
        assert dirty["pending_reference_report_path"]
        assert dirty["pending_reference_report_hash"]
        assert dirty["raw_source_path"] == str(preserved.raw_path.resolve())

        def failed_verification(*_args):
            raise ValueError("injected post-PUT verification failure")

        monkeypatch.setattr(competency, "verify_core_graph", failed_verification)
        verification_loader = _MemoryLoader(remote)
        with pytest.raises(ValueError, match="post-PUT verification"):
            _run(store, [preserved], remote, loader=verification_loader)
        assert store.get_resource("debates", work)["publication_state"] == "dirty"

        monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))
        retry_loader = _MemoryLoader(remote)
        retried = _run(store, [load_main_xml(tmp_path / "raw", preserved.source_sha256)],
                       remote, loader=retry_loader)
        assert retried[0].status == "changed"
        assert (failing.payloads[0] == verification_loader.payloads[0]
                == retry_loader.payloads[0])
        recovered = store.get_resource("debates", work)
        assert recovered["publication_state"] == "clean"
        assert recovered["pending_payload"] is None
        assert recovered["pending_reference_report_path"] is None
        assert recovered["published_reference_report_path"]
        assert recovered["published_source_hash"] == preserved.source_sha256


def test_dirty_publication_overrides_matching_published_hash_after_reopen_and_revert(
        tmp_path, monkeypatch):
    database = tmp_path / "state.sqlite"
    raw_root = tmp_path / "raw"
    remote: dict[str, Graph] = {}
    source_a = _source(speech="source-a")
    source_b = _source(speech="source-b")
    input_a = _preserved_source(raw_root, source_a)
    input_b = _preserved_source(raw_root, source_b)
    monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))

    with CoreStateStore(database) as store:
        first_loader = _MemoryLoader(remote)
        first = _run(store, [input_a], remote, loader=first_loader)[0]
        first_state = store.get_resource("debates", first.work_iri)
        payload_a = first_loader.payloads[0]
        report_a = first_state["published_reference_report_path"]

        failed_loader = _MemoryLoader(remote, fail=True)
        with pytest.raises(RuntimeError, match="injected GSP PUT failure"):
            _run(store, [input_b], remote, loader=failed_loader)
        dirty = store.get_resource("debates", first.work_iri)
        assert dirty["publication_state"] == "dirty"
        assert dirty["published_source_hash"] == input_a.source_sha256
        assert dirty["pending_source_hash"] == input_b.source_sha256
        report_b = dirty["pending_reference_report_path"]

    with CoreStateStore(database) as reopened:
        revert_loader = _MemoryLoader(remote)
        reverted = _run(
            reopened, [load_main_xml(raw_root, input_a.source_sha256)],
            remote, loader=revert_loader,
        )[0]
        clean = reopened.get_resource("debates", first.work_iri)
        assert reverted.status == "changed"
        assert clean["publication_state"] == "clean"
        assert clean["published_source_hash"] == input_a.source_sha256
        assert clean["published_reference_report_path"] == report_a
        assert clean["pending_source_hash"] is None
        assert revert_loader.payloads == [payload_a]
        assert set(remote[first.graph_iri]) == set(first.graph)
        assert Path(report_a).exists() and Path(report_b).exists()


def test_post_put_reference_report_verification_failure_never_marks_clean(
        tmp_path, monkeypatch):
    remote: dict[str, Graph] = {}
    source = _source()
    preserved = _preserved_source(tmp_path / "raw", source)
    monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))

    class CorruptingLoader(_MemoryLoader):
        def __init__(self, target, store):
            super().__init__(target)
            self.store = store

        def replace(self, graph_iri, payload, *, content_type):
            super().replace(graph_iri, payload, content_type=content_type)
            row = next(item for item in self.store.resources("debates")
                       if item["graph_iri"] == graph_iri)
            Path(row["pending_reference_report_path"]).write_bytes(b"corrupt report")

    with CoreStateStore(tmp_path / "state.sqlite") as store:
        loader = CorruptingLoader(remote, store)
        with pytest.raises(CoreStateError, match="reference report verification failed"):
            _run(store, [preserved], remote, loader=loader)
        identity = inspect_debate_source_identity(source)["work_iri"]
        dirty = store.get_resource("debates", identity)
        assert dirty["publication_state"] == "dirty"
        assert dirty["published_source_hash"] is None
        assert dirty["pending_source_hash"] == preserved.source_sha256
        assert dirty["pending_reference_report_path"]
        assert dirty["pending_reference_report_hash"]


def test_reference_report_persistence_failure_precedes_resource_state_and_put(
        tmp_path, monkeypatch):
    remote: dict[str, Graph] = {}
    source = _source()
    preserved = _preserved_source(tmp_path / "raw", source)
    loader = _MemoryLoader(remote)

    def fail_report_write(*_args, **_kwargs):
        raise DebateSourceError("injected report persistence failure")

    monkeypatch.setattr(debates_pipeline, "persist_reference_report", fail_report_write)
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        with pytest.raises(DebateSourceError, match="report persistence"):
            _run(store, [preserved], remote, loader=loader)
        assert store.resources("debates") == []
        assert loader.puts == [] and remote == {}


def test_invalid_xml_and_multiple_expressions_fail_before_publication(tmp_path):
    bad_url = "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2026-10-06/mul%40/main.xml"
    invalid = persist_main_xml(tmp_path / "raw", b"<akomaNtoso><debate>", bad_url)
    with pytest.raises(ValueError, match="invalid AKN XML"):
        run_debate_batch([invalid])

    one = _source()
    two = _source(expression="/akn/ie/debateRecord/dail/2026-10-06/tranche-4-test/ga@",
                  speech="second")
    first_input = _preserved_source(tmp_path / "raw", one)
    second_input = _preserved_source(tmp_path / "raw", two)
    remote: dict[str, Graph] = {}
    with CoreStateStore(tmp_path / "multi.sqlite") as store:
        run_id = store.start_run("debates", "incremental_refresh", is_complete=False,
                                 parameters={"source": "test"})
        with pytest.raises(Exception, match="multiple known Expressions"):
            run_debate_batch([first_input, second_input], store=store, run_id=run_id,
                             publish=True, loader=_MemoryLoader(remote), client=object())
        assert not remote
        assert store.resources("debates") == []
        store.finish_run(run_id, success=False, error="multiple expressions")


def test_mixed_valid_and_duplicate_eid_batch_fails_before_any_put_or_state(tmp_path):
    raw_root = tmp_path / "raw"
    valid = _preserved_source(
        raw_root,
        _source(work="/akn/ie/debateRecord/dail/2026-10-06/valid-batch-item"),
    )
    duplicate = _preserved_source(
        raw_root,
        _source(work="/akn/ie/debateRecord/dail/2026-10-06/duplicate-eid-item",
                speech="section"),
    )
    remote: dict[str, Graph] = {}
    loader = _MemoryLoader(remote)
    with CoreStateStore(tmp_path / "state.sqlite") as store:
        run_id = store.start_run(
            "debates", "incremental_refresh", is_complete=False,
            parameters={"source": "mixed-valid-and-invalid-test"},
        )
        with pytest.raises(ValueError, match="duplicate decoded eId"):
            run_debate_batch([valid, duplicate], store=store, run_id=run_id,
                             publish=True, loader=loader, client=object())
        assert loader.puts == [] and loader.payloads == []
        assert remote == {}
        assert store.resources("debates") == []
        store.finish_run(run_id, success=False, error="duplicate decoded eId")


def test_owner_snapshot_change_forces_reresolution_even_if_lookup_version_is_same(tmp_path, monkeypatch):
    remote: dict[str, Graph] = {}
    source = (DEBATE_DIR / "dail_2026-02-26.akn.xml").read_bytes()
    preserved = _preserved_source(tmp_path / "raw", source)
    database = tmp_path / "state.sqlite"
    monkeypatch.setattr(competency, "verify_core_graph", _memory_verify(remote))
    loader = _MemoryLoader(remote)
    with CoreStateStore(database) as store:
        owners = _seed_owners(store, remote)
        first = _run(store, [preserved], remote, loader=loader)[0]
        prior = store.get_resource("debates", first.work_iri)
        old_registry_version = prior["published_resolver_version"]
        old_owner_hash = prior["published_owner_snapshot_hash"]
        old_report_path = Path(prior["published_reference_report_path"])
        old_report_bytes = old_report_path.read_bytes()

        house_source = json.loads((ROOT / "data/api_examples/houses.json").read_text())
        changed_house_source = copy.deepcopy(house_source)
        next(record["house"] for record in changed_house_source
             if record["house"]["houseNo"] == "34")["showAs"] = "Changed owner label"
        changed_house_graph = transform_houses(changed_house_source)
        validate_houses(changed_house_source, changed_house_graph)
        house_payload = ntriples(changed_house_graph)
        house_hash = store.mark_endpoint_dirty("houses", HOUSES_GRAPH, house_payload)
        remote[HOUSES_GRAPH] = changed_house_graph
        store.complete_endpoint_publication("houses", HOUSES_GRAPH, house_hash)

    # A new process must derive the updated resolver snapshot and retain its
    # report as a distinct immutable resolution version.
    with CoreStateStore(database) as store:
        replay = load_main_xml(tmp_path / "raw", preserved.source_sha256)
        second = _run(store, [replay], remote, loader=loader)[0]
        current = store.get_resource("debates", first.work_iri)
        assert second.status == "changed"
        assert len(loader.puts) == 2
        assert current["published_resolver_version"] == old_registry_version
        assert current["published_owner_snapshot_hash"] != old_owner_hash
        new_report_path = Path(current["published_reference_report_path"])
        assert new_report_path != old_report_path
        assert old_report_path.read_bytes() == old_report_bytes
        assert old_report_path.exists() and new_report_path.exists()
        verify_reference_report(
            old_report_path, hashlib.sha256(old_report_bytes).hexdigest(),
            source_sha256=preserved.source_sha256,
            resolver_version=old_registry_version,
            owner_snapshot_hash=old_owner_hash,
        )
        verify_reference_report(
            new_report_path, current["published_reference_report_hash"],
            source_sha256=preserved.source_sha256,
            resolver_version=current["published_resolver_version"],
            owner_snapshot_hash=current["published_owner_snapshot_hash"],
        )
        assert set(remote[first.graph_iri]) == set(first.graph)


def test_core_state_v4_migration_preserves_publication_history_and_adds_debates(tmp_path):
    database = tmp_path / "v4.sqlite"
    member = json.loads((ROOT / "data/api_examples/member.json").read_text())["member"]
    identity = member["uri"]
    graph_iri = member_graph_iri(member)
    with __import__("sqlite3").connect(database) as connection:
        connection.executescript("""
            CREATE TABLE core_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE etl_run (
              run_id TEXT PRIMARY KEY,
              endpoint TEXT NOT NULL CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','administrative-units','offices')),
              run_kind TEXT NOT NULL CHECK(run_kind IN ('full_refresh','incremental_refresh','complete_source_reconciliation')),
              is_complete INTEGER NOT NULL CHECK(is_complete IN (0,1)), started_at TEXT NOT NULL,
              completed_at TEXT, status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
              error TEXT, parameters_json TEXT NOT NULL);
            CREATE INDEX etl_run_endpoint_started ON etl_run(endpoint,started_at);
            CREATE TABLE endpoint_state (
              endpoint TEXT PRIMARY KEY CHECK(endpoint IN ('houses','parties','constituencies','committees','members','legislation','administrative-units','offices')),
              last_successful_run_id TEXT,last_successful_complete_run_id TEXT,
              incremental_cursor TEXT,publication_metadata_json TEXT,updated_at TEXT NOT NULL);
            CREATE TABLE resource_state (
              endpoint TEXT NOT NULL CHECK(endpoint IN ('members','legislation')),
              resource_iri TEXT NOT NULL,graph_iri TEXT NOT NULL,observed_source_hash TEXT,
              published_source_hash TEXT,published_payload_hash TEXT,published_payload TEXT,
              last_seen_at TEXT,last_seen_run_id TEXT,last_published_at TEXT,
              last_missing_run_id TEXT,last_missing_at TEXT,missing_scan_count INTEGER NOT NULL DEFAULT 0,
              publication_state TEXT NOT NULL CHECK(publication_state IN ('clean','dirty')),
              pending_source_hash TEXT,pending_graph_iri TEXT,pending_payload TEXT,pending_payload_hash TEXT,
              source_presence TEXT NOT NULL DEFAULT 'present',contract_version INTEGER,
              PRIMARY KEY(endpoint,resource_iri));
            CREATE INDEX resource_state_publication ON resource_state(endpoint,publication_state);
            PRAGMA user_version=4;
        """)
        connection.execute("""INSERT INTO resource_state
            (endpoint,resource_iri,graph_iri,observed_source_hash,published_source_hash,
             published_payload_hash,published_payload,publication_state,source_presence,contract_version)
            VALUES ('members',?,?,?,?,'payload-hash','payload','clean','present',3)""",
            (identity, graph_iri, "a"*64, "b"*64))
        connection.execute("""INSERT INTO etl_run
            VALUES ('kept-run','members','full_refresh',0,'2026-10-01T00:00:00+00:00',
                    '2026-10-01T00:00:01+00:00','succeeded',NULL,'{}')""")
    with CoreStateStore(database) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 8
        resource_columns = {row[1] for row in store.connection.execute(
            "PRAGMA table_info(resource_state)")}
        assert {
            "published_reference_report_path", "published_reference_report_hash",
            "pending_reference_report_path", "pending_reference_report_hash",
        } <= resource_columns
        prior = store.get_resource("members", identity)
        assert prior["published_source_hash"] == "b"*64
        assert prior["published_payload"] == "payload"
        assert prior["published_reference_report_path"] is None
        assert prior["pending_reference_report_path"] is None
        resource_schema = store.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='resource_state'").fetchone()[0]
        assert "published_reference_report_path IS NULL) = (published_reference_report_hash IS NULL" in resource_schema
        assert "pending_reference_report_path IS NULL) = (pending_reference_report_hash IS NULL" in resource_schema
        assert store.connection.execute("SELECT status FROM etl_run WHERE run_id='kept-run'").fetchone()[0] == "succeeded"
        run = store.start_run("debates", "incremental_refresh", is_complete=False,
                              parameters={"source": "explicit"})
        store.finish_run(run, success=True)
        with pytest.raises(CoreStateError, match="explicit-batch incremental"):
            store.start_run("debates", "complete_source_reconciliation", is_complete=True,
                            parameters={"source": "must-not-assert-completeness"})


TEST_GSP = os.getenv("OIR_TEST_FUSEKI_GSP_URL")
TEST_SPARQL = os.getenv("OIR_TEST_FUSEKI_SPARQL_URL")
TEST_USER = os.getenv("OIR_TEST_FUSEKI_USER")
TEST_PASSWORD = os.getenv("OIR_TEST_FUSEKI_PASSWORD")
pytestmark_fuseki = pytest.mark.skipif(
    not (TEST_GSP and TEST_SPARQL),
    reason="set OIR_TEST_FUSEKI_GSP_URL and OIR_TEST_FUSEKI_SPARQL_URL for local Debates Fuseki acceptance",
)


def _require_disposable_debates_dataset(gsp_url: str, sparql_url: str) -> None:
    """Allow graph mutation only against the dedicated local T4 dataset."""
    try:
        gsp, query = urlsplit(gsp_url), urlsplit(sparql_url)
        same_origin = (gsp.scheme, gsp.netloc) == (query.scheme, query.netloc)
        gsp_port, query_port = gsp.port, query.port
    except (TypeError, ValueError) as error:
        raise ValueError("invalid disposable Debates Fuseki endpoint URL") from error
    if (not same_origin
            or gsp.scheme != "http"
            or gsp.hostname not in {"127.0.0.1", "localhost", "::1"}
            or query.hostname not in {"127.0.0.1", "localhost", "::1"}
            or gsp_port != 13035 or query_port != 13035
            or gsp.path != "/debates_t4/data"
            or query.path != "/debates_t4/query"
            or gsp.username is not None or gsp.password is not None
            or query.username is not None or query.password is not None
            or gsp.query or gsp.fragment or query.query or query.fragment):
        raise ValueError(
            "Debates Fuseki acceptance requires the same loopback :13035 "
            "debates_t4 /data and /query endpoints")


@pytest.mark.parametrize(("gsp", "sparql"), [
    ("http://127.0.0.1:13035/data", "http://127.0.0.1:13035/query"),
    ("http://127.0.0.1:13035/debates_t4/data",
     "http://127.0.0.1:13035/other/query"),
    ("http://127.0.0.1:13035/debates_t4/data",
     "http://localhost:13035/debates_t4/query"),
    ("http://example.test:13035/debates_t4/data",
     "http://example.test:13035/debates_t4/query"),
    ("http://127.0.0.1:13036/debates_t4/data",
     "http://127.0.0.1:13036/debates_t4/query"),
])
def test_disposable_fuseki_guard_rejects_non_t4_or_non_loopback_targets(gsp, sparql):
    with pytest.raises(ValueError, match="same loopback :13035 debates_t4"):
        _require_disposable_debates_dataset(gsp, sparql)


def test_disposable_fuseki_guard_accepts_exact_same_t4_dataset():
    _require_disposable_debates_dataset(
        "http://127.0.0.1:13035/debates_t4/data",
        "http://127.0.0.1:13035/debates_t4/query",
    )


@pytestmark_fuseki
def test_disposable_fuseki_first_replay_changed_stale_skip_and_owner_isolation(
        tmp_path):
    from oireachtas_etl.competency import verify_core_graph
    from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient

    if TEST_USER and not TEST_PASSWORD:
        pytest.fail("OIR_TEST_FUSEKI_PASSWORD is required when OIR_TEST_FUSEKI_USER is set")
    # Exact dataset, path, loopback host and port checks precede construction
    # and every owner graph PUT. This cannot target another local dataset.
    _require_disposable_debates_dataset(TEST_GSP, TEST_SPARQL)

    state_path = tmp_path / "core.sqlite"
    raw_root = tmp_path / "raw"
    loader = FusekiGraphStoreLoader(TEST_GSP, user=TEST_USER, password=TEST_PASSWORD)
    client = FusekiSparqlClient(TEST_SPARQL, user=TEST_USER, password=TEST_PASSWORD)
    source = _source(work=f"/akn/ie/debateRecord/dail/2026-10-06/fuseki-{uuid.uuid4().hex}")
    source_input = _preserved_source(raw_root, source)

    with CoreStateStore(state_path) as store:
        owners = _seed_owners(store)
        owner_payloads = {name: ntriples(graph) for name, graph in owners.items()}
        for name, payload in owner_payloads.items():
            loader.replace(name, payload, content_type="application/n-triples")
            verify_core_graph(client, name, payload)

        first = _run(store, [source_input], {}, loader=loader, client=client)[0]
        assert first.status == "new"
        first_payload = ntriples(first.graph)
        verify_core_graph(client, first.graph_iri, first_payload)

        replayed = _run(
            store, [load_main_xml(raw_root, source_input.source_sha256)], {},
            loader=loader, client=client,
        )[0]
        assert replayed.status == "skipped"

        changed = _source(
            work=inspect_debate_source_identity(source)["source_work_uri"],
            expression=inspect_debate_source_identity(source)["source_expression_uri"],
            speech="replacement",
        )
        changed_input = _preserved_source(raw_root, changed)
        replaced = _run(store, [changed_input], {}, loader=loader, client=client)[0]
        assert replaced.status == "changed"
        changed_payload = ntriples(replaced.graph)
        verify_core_graph(client, replaced.graph_iri, changed_payload)
        expression_iri = inspect_debate_source_identity(changed)["expression_iri"]
        old_speech = URIRef(expression_iri + "/eid/e-old")
        new_speech = URIRef(expression_iri + "/eid/e-replacement")
        assert not list(replaced.graph.triples((old_speech, None, None)))
        assert list(replaced.graph.triples((new_speech, None, None)))

        for name, payload in owner_payloads.items():
            verify_core_graph(client, name, payload)
