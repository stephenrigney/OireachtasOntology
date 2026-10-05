"""Live publication verification versus fixture competency regression.

The fixture-pinned competency queries (``EXPECTED``, ``PARTIES_EXPECTED``,
``CONSTITUENCIES_EXPECTED``) are regression tests: they prove that a specific
known checked-in fixture graph answers a specific public query. Live
publication of a changing authoritative API response must not require unrelated
historical or example resources to be present today. It is verified instead
against the exact validated payload that was replaced, using
``verify_core_graph``.

These tests exercise the online publication path against an in-memory Fuseki
stand-in so the real ``verify_core_graph`` implementation runs, while leaking
no network calls and no durable state outside ``tmp_path``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from rdflib import BNode, Dataset, Graph, URIRef

from oireachtas_etl import cli
from oireachtas_etl.competency import (
    QUERIES,
    verify_constituencies_competency,
    verify_houses_competency,
    verify_parties_competency,
)
from oireachtas_etl.config import CONSTITUENCIES_GRAPH, HOUSES_GRAPH, PARTIES_GRAPH
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.constituencies import transform_constituencies
from oireachtas_etl.transforms.houses import transform_houses
from oireachtas_etl.transforms.parties import transform_parties


ROOT = Path(__file__).resolve().parents[1]
HOUSES = json.loads((ROOT / "data/api_examples/houses.json").read_text())
PARTIES = json.loads((ROOT / "data/api_examples/parties.json").read_text())["results"]
CONSTITUENCIES = json.loads((ROOT / "data/api_examples/constituencies.json").read_text())


def _binding(term) -> dict:
    if isinstance(term, URIRef):
        return {"type": "uri", "value": str(term)}
    if isinstance(term, BNode):
        return {"type": "bnode", "value": str(term)}
    binding = {"type": "literal", "value": str(term)}
    if term.datatype:
        binding["datatype"] = str(term.datatype)
    if term.language:
        binding["xml:lang"] = term.language
    return binding


class _InMemoryGraphClient:
    """Executes SPARQL against an rdflib Dataset and returns Fuseki-shaped rows."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def query(self, sparql: str) -> list[dict]:
        result = self.dataset.query(sparql)
        rows = []
        for row in result:
            record = {str(name): _binding(row[name]) for name in result.vars if row[name] is not None}
            rows.append(record)
        return rows


class _InMemoryGraphStoreLoader:
    """Atomic whole-graph replacement into an rdflib Dataset."""

    def __init__(self, dataset: Dataset):
        self.dataset = dataset

    def replace(self, graph_iri: str, payload: str, *, content_type: str) -> None:
        identifier = URIRef(graph_iri)
        if identifier in set(self.dataset.graphs()):
            self.dataset.remove_graph(identifier)
        target = self.dataset.graph(identifier)
        for triple in Graph().parse(data=payload, format="nt"):
            target.add(triple)


def _patch_online_publication(monkeypatch, dataset: Dataset) -> None:
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", lambda *a, **k: _InMemoryGraphStoreLoader(dataset))
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *a, **k: _InMemoryGraphClient(dataset))


def _write(tmp_path: Path, name: str, value) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _run(endpoint: str, fixture: Path, state_db: Path, raw_dir: Path) -> int:
    return cli.main([
        "run", endpoint,
        "--fixture", str(fixture),
        "--state-db", str(state_db),
        "--raw-dir", str(raw_dir),
        "--reconciliation-state-file", str(state_db.parent / "reconciliation.sqlite"),
        "--fuseki-gsp-url", "http://fuseki.test/houses/data",
        "--fuseki-sparql-url", "http://fuseki.test/houses/query",
    ])


def _run_live(endpoint: str, records: list[dict], state_db: Path,
              raw_dir: Path, monkeypatch) -> int:
    """Exercise the authoritative API branch without making network calls."""
    from oireachtas_etl.api import ApiPage

    count_field = {"parties": "partyCount",
                   "constituencies": "constituencyCount"}[endpoint]
    envelope = {"head": {"counts": {count_field: len(records)}},
                "results": records}

    class Api:
        def __init__(self, *args, **kwargs):
            pass

        def harvest(self, *, limit):
            yield ApiPage(json.dumps(envelope).encode("utf-8"), 200,
                          {"skip": 0, "limit": limit})

    monkeypatch.setattr(cli, "ApiClient", Api)
    return cli.main([
        "run", endpoint,
        "--state-db", str(state_db),
        "--raw-dir", str(raw_dir),
        "--reconciliation-state-file", str(state_db.parent / "reconciliation.sqlite"),
        "--fuseki-gsp-url", "http://fuseki.test/houses/data",
        "--fuseki-sparql-url", "http://fuseki.test/houses/query",
    ])


def _published(dataset: Dataset, graph_iri: str) -> Graph:
    return _copy_graph(dataset.graph(URIRef(graph_iri)))


def _copy_graph(graph: Graph) -> Graph:
    result = Graph()
    for triple in graph:
        result.add(triple)
    return result


def _seed_fixture(dataset: Dataset, graph_iri: str, transform, records) -> None:
    target = dataset.graph(URIRef(graph_iri))
    for triple in transform(records):
        target.add(triple)


# --- Fixture regression: exact expectations still answer fixture graphs ------


def test_fixture_competency_queries_still_answer_their_known_fixture_graph():
    dataset = Dataset()
    _seed_fixture(dataset, HOUSES_GRAPH, transform_houses, HOUSES)
    _seed_fixture(dataset, PARTIES_GRAPH, transform_parties, PARTIES)
    _seed_fixture(dataset, CONSTITUENCIES_GRAPH, transform_constituencies, CONSTITUENCIES)
    client = _InMemoryGraphClient(dataset)

    verify_houses_competency(client)
    verify_parties_competency(client)
    verify_constituencies_competency(client)


# --- Live publication: verify exactly the validated payload -----------------


def test_live_houses_publication_verifies_exact_validated_payload(tmp_path, monkeypatch):
    fixture = _write(tmp_path, "houses.json", HOUSES)
    dataset = Dataset()
    _patch_online_publication(monkeypatch, dataset)
    state_db = tmp_path / "state.sqlite"

    assert _run("houses", fixture, state_db, tmp_path / "raw") == 0

    expected = Graph().parse(data=ntriples(transform_houses(HOUSES)), format="nt")
    assert set(_published(dataset, HOUSES_GRAPH)) == set(expected)
    with CoreStateStore(state_db) as state:
        assert state.endpoint_publication("houses")["publication_state"] == "clean"


def test_live_parties_publication_verifies_exact_validated_payload(tmp_path, monkeypatch):
    dataset = Dataset()
    _patch_online_publication(monkeypatch, dataset)
    state_db = tmp_path / "state.sqlite"

    assert _run_live("parties", PARTIES, state_db, tmp_path / "raw", monkeypatch) == 0

    expected = Graph().parse(data=ntriples(transform_parties(PARTIES)), format="nt")
    assert set(_published(dataset, PARTIES_GRAPH)) == set(expected)
    with CoreStateStore(state_db) as state:
        assert state.endpoint_publication("parties")["publication_state"] == "clean"


def test_live_constituencies_publication_verifies_exact_validated_payload(tmp_path, monkeypatch):
    dataset = Dataset()
    _patch_online_publication(monkeypatch, dataset)
    state_db = tmp_path / "state.sqlite"

    assert _run_live("constituencies", CONSTITUENCIES, state_db,
                     tmp_path / "raw", monkeypatch) == 0

    expected = Graph().parse(data=ntriples(transform_constituencies(CONSTITUENCIES)), format="nt")
    assert set(_published(dataset, CONSTITUENCIES_GRAPH)) == set(expected)
    with CoreStateStore(state_db) as state:
        assert state.endpoint_publication("constituencies")["publication_state"] == "clean"


# --- The wrong boundary: fixture examples are not live acceptance -----------


def test_pinned_fixture_expectations_are_not_required_for_live_source_data(tmp_path, monkeypatch):
    # Cork South East (9th Dáil) is a legitimate live-shaped resource that the
    # fixture-pinned representation-details.rq example set does not mention. A
    # live source response need not contain Dublin Mid-West or the Agricultural
    # Panel, so the exact fixture expectation must not gate publication.
    source = [CONSTITUENCIES[0]]
    dataset = Dataset()
    _patch_online_publication(monkeypatch, dataset)
    state_db = tmp_path / "state.sqlite"

    assert _run_live("constituencies", source, state_db,
                     tmp_path / "raw", monkeypatch) == 0

    # The exact fixture query still runs and simply finds none of its examples.
    assert list(dataset.query(QUERIES.joinpath("representation-details.rq").read_text())) == []
    assert set(_published(dataset, CONSTITUENCIES_GRAPH)) == set(
        Graph().parse(data=ntriples(transform_constituencies(source)), format="nt"))
    with CoreStateStore(state_db) as state:
        assert state.endpoint_publication("constituencies")["publication_state"] == "clean"


# --- Fail-closed durable state and verified repair --------------------------


def test_failed_live_verification_keeps_state_dirty_and_rerun_repairs(tmp_path, monkeypatch):
    dataset = Dataset()
    _patch_online_publication(monkeypatch, dataset)
    real_verify = cli.verify_core_graph
    attempts = {"count": 0}

    def flaky(client, graph_iri, payload):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("core graph/state mismatch for the first publication attempt")
        real_verify(client, graph_iri, payload)

    monkeypatch.setattr(cli, "verify_core_graph", flaky)
    state_db = tmp_path / "state.sqlite"

    with pytest.raises(ValueError, match="core graph/state mismatch"):
        _run_live("constituencies", CONSTITUENCIES, state_db,
                  tmp_path / "raw", monkeypatch)
    with CoreStateStore(state_db) as state:
        # The failed publication leaves the graph dirty; it is never marked clean.
        assert state.endpoint_publication("constituencies")["publication_state"] == "dirty"

    assert _run_live("constituencies", CONSTITUENCIES, state_db,
                     tmp_path / "raw-2", monkeypatch) == 0
    with CoreStateStore(state_db) as state:
        assert state.endpoint_publication("constituencies")["publication_state"] == "clean"
