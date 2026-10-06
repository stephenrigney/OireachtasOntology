from __future__ import annotations

import copy
import hashlib
import json
from argparse import Namespace
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from oireachtas_etl import cli
from oireachtas_etl.config import PARTIES_GRAPH
from oireachtas_etl.config import COMMITTEES_GRAPH
from oireachtas_etl.config import CONSTITUENCIES_GRAPH
from oireachtas_etl.config import Settings
from oireachtas_etl.loader import FusekiSparqlClient
from oireachtas_etl.raw import persist_raw
from oireachtas_etl.raw_captures import load_latest_development_capture
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.members import member_graph_iri
from oireachtas_etl.transforms.parties import transform_parties


ROOT = Path(__file__).resolve().parents[1]
KNOWN_CONFLICT_COMMITTEE = (
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/"
    "select_committee_on_the_implementation_of_the_good_friday_agreement"
)
API_URLS = {
    "houses": "https://api.oireachtas.ie/v1/houses",
    "parties": "https://api.oireachtas.ie/v1/parties",
    "constituencies": "https://api.oireachtas.ie/v1/constituencies",
    "members": "https://api.oireachtas.ie/v1/members",
}
COUNT_FIELDS = {
    "houses": "housesCount", "parties": "partyCount",
    "constituencies": "constituencyCount", "members": "memberCount",
}


def _persist_capture(root: Path, state: CoreStateStore, endpoint: str,
                     records: list[dict]) -> None:
    run_id = state.start_run(
        endpoint, "full_refresh", is_complete=True,
        parameters={"source": "api", "api_url": API_URLS[endpoint], "limit": 100},
        started_at="2026-10-01T00:00:00+00:00",
    )
    body = json.dumps({
        "head": {"counts": {COUNT_FIELDS[endpoint]: len(records)}},
        "results": records,
    }, sort_keys=True).encode("utf-8")
    persist_raw(
        root=root, endpoint=API_URLS[endpoint],
        params={"skip": 0, "limit": 100}, body=body, status=200,
        retrieved_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        endpoint_name=endpoint, extraction_id=run_id,
    )
    state.finish_run(run_id, success=True)


def _records() -> dict[str, list[dict]]:
    houses = json.loads((ROOT / "data/api_examples/houses.json").read_text())
    parties = json.loads((ROOT / "data/api_examples/parties.json").read_text())["results"]
    constituencies = json.loads(
        (ROOT / "data/api_examples/constituencies.json").read_text())
    member = {"member": json.loads(
        (ROOT / "data/api_examples/member.json").read_text())["member"]}
    member = copy.deepcopy(member)
    membership = member["member"]["memberships"][0]["membership"]
    conflict = {
        "uri": KNOWN_CONFLICT_COMMITTEE,
        "houseCode": "dail", "houseNo": 33,
        "committeeCode": "GFA", "committeeID": 71,
        "committeeType": ["Select"],
        "committeeDateRange": {"start": "2020-01-01", "end": None},
        "committeeName": [{"dateRange": {"start": "2020-01-01", "end": None},
                            "nameEn": "Conflicting source label"}],
        "memberDateRange": {"start": "2020-01-01", "end": None},
        "role": [],
    }
    other_observation = copy.deepcopy(conflict)
    other_observation["committeeID"] = 72
    membership["committees"].extend([conflict, other_observation])
    return {
        "houses": houses,
        "parties": parties,
        "constituencies": constituencies,
        "members": [member],
    }


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_local_development_bootstrap_is_read_only_to_authoritative_state(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import config

    raw_root = tmp_path / "raw"
    state_path = tmp_path / "core.sqlite"
    reconciliation_path = tmp_path / "reconciliation.sqlite"
    captures = _records()
    with CoreStateStore(state_path) as state:
        for endpoint in ("houses", "parties", "constituencies", "members"):
            _persist_capture(raw_root, state, endpoint, captures[endpoint])
        accepted_payload = ntriples(transform_parties(captures["parties"][:1]))
        digest = state.mark_endpoint_dirty(
            "parties", PARTIES_GRAPH, accepted_payload, coverage_authoritative=True)
        state.complete_endpoint_publication(
            "parties", PARTIES_GRAPH, digest, coverage_authoritative=True)
        accepted_publication = state.endpoint_publication("parties")

    # A pre-existing external-reconciliation ledger must not be opened or
    # advanced by this local-only operation.
    with sqlite3.connect(reconciliation_path) as connection:
        connection.execute("CREATE TABLE authority_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO authority_marker VALUES ('unchanged')")
    state_hash = _hash(state_path)
    reconciliation_hash = _hash(reconciliation_path)

    uploaded: dict[str, Graph] = {}
    upload_order: list[str] = []

    class Loader:
        def __init__(self, *_args, **_kwargs):
            pass

        def replace(self, graph_iri, payload, *, content_type):
            assert content_type == "application/n-triples"
            graph = Graph().parse(data=payload, format="nt") if payload else Graph()
            uploaded[graph_iri] = graph
            upload_order.append(graph_iri)

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

    verified: list[str] = []

    def verify(_client, graph_iri, payload):
        expected = Graph().parse(data=payload, format="nt") if payload else Graph()
        assert set(uploaded[graph_iri]) == set(expected)
        verified.append(graph_iri)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_core_graph", verify)
    monkeypatch.setattr(cli.Settings, "from_environment", lambda: config.Settings())
    build_census = cli.build_reference_census
    census_reports = []

    def build_non_authoritative_census(**kwargs):
        assert kwargs["member_capture_complete"] is False
        assert kwargs["party_capture_complete"] is False
        assert kwargs["constituency_capture_complete"] is False
        result = build_census(**kwargs)
        census_reports.append(result["report"])
        return result

    monkeypatch.setattr(cli, "build_reference_census",
                        build_non_authoritative_census)

    args = Namespace(
        raw_dir=str(raw_root), state_db=str(state_path),
        fuseki_gsp_url="http://127.0.0.1:3030/houses/data",
        fuseki_sparql_url="http://127.0.0.1:3030/houses/query",
    )
    assert cli._run_development_bootstrap(args) == 0
    output = capsys.readouterr().out
    assert "Local development reference bootstrap:" in output
    assert "Quarantined conflicts: 1" in output
    assert "Unresolved development references: 1" in output
    assert "Reference closure: NOT authoritative / not complete" in output
    assert KNOWN_CONFLICT_COMMITTEE in output
    assert len(census_reports) == 1
    assert census_reports[0]["capture_completeness"] == {
        "members": False, "parties": False, "constituencies": False,
    }
    assert upload_order == verified
    assert upload_order[:4] == [
        "https://data.oireachtas.ie/graph/houses",
        "https://data.oireachtas.ie/graph/parties",
        "https://data.oireachtas.ie/graph/constituencies",
        "https://data.oireachtas.ie/graph/committees",
    ]

    party_graph = uploaded[PARTIES_GRAPH]
    assert (URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent"),
            RDF.type, MEMBERS.IndependentMemberCollection) in party_graph
    assert (URIRef("https://data.oireachtas.ie/ie/oireachtas/party/dail/30/Fianna_Fáil"),
            RDF.type, MEMBERS.ParliamentaryParty) in party_graph
    constituency_graph = uploaded[
        "https://data.oireachtas.ie/graph/constituencies"]
    assert any(constituency_graph.subjects(RDF.type, MEMBERS.SeanadPanel))
    committee_graph = uploaded["https://data.oireachtas.ie/graph/committees"]
    assert any(committee_graph.subjects(RDF.type, MEMBERS.Committee))
    assert not list(committee_graph.triples((
        URIRef(KNOWN_CONFLICT_COMMITTEE), None, None)))
    member_graph = next(graph for iri, graph in uploaded.items()
                        if iri.startswith("https://data.oireachtas.ie/graph/member/"))
    assert (None, MEMBERS.isCommitteeMembershipOf,
            URIRef(KNOWN_CONFLICT_COMMITTEE)) in member_graph

    assert _hash(state_path) == state_hash
    assert _hash(reconciliation_path) == reconciliation_hash
    with CoreStateStore(state_path) as state:
        assert state.endpoint_publication("parties") == accepted_publication
        assert state.endpoint_publication("parties")["coverage_authoritative"] is True


def test_local_development_bootstrap_refuses_non_loopback_fuseki():
    args = Namespace(
        raw_dir="missing", state_db="missing",
        fuseki_gsp_url="https://production.example/data",
        fuseki_sparql_url="http://127.0.0.1:3030/query",
    )
    try:
        cli._run_development_bootstrap(args)
    except ValueError as error:
        assert "may write only to a loopback" in str(error)
    else:
        raise AssertionError("development bootstrap accepted a non-local Fuseki URL")


def test_development_capture_selector_does_not_promote_a_fixture_or_partial_run(
        tmp_path):
    state_path = tmp_path / "core.sqlite"
    raw_root = tmp_path / "raw"
    with CoreStateStore(state_path) as state:
        fixture_run = state.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "fixture"},
        )
        state.finish_run(fixture_run, success=True)

    with pytest.raises(ValueError, match="no successful complete API members capture"):
        load_latest_development_capture(raw_root, state_path, "members")


TEST_GSP = os.getenv("OIR_TEST_FUSEKI_GSP_URL")
TEST_SPARQL = os.getenv("OIR_TEST_FUSEKI_SPARQL_URL")
TEST_USER = os.getenv("OIR_TEST_FUSEKI_USER")
TEST_PASSWORD = os.getenv("OIR_TEST_FUSEKI_PASSWORD")


@pytest.mark.skipif(
    not (TEST_GSP and TEST_SPARQL),
    reason="set OIR_TEST_FUSEKI_GSP_URL and OIR_TEST_FUSEKI_SPARQL_URL "
           "for local Fuseki development-bootstrap integration",
)
def test_loopback_fuseki_bootstrap_loads_unrelated_references_and_starts_poc(
        tmp_path, monkeypatch, capsys):
    from fastapi.testclient import TestClient
    from poc.nlq.app import create_app

    raw_root = tmp_path / "raw"
    state_path = tmp_path / "core.sqlite"
    captures = _records()
    with CoreStateStore(state_path) as state:
        for endpoint in ("houses", "parties", "constituencies", "members"):
            _persist_capture(raw_root, state, endpoint, captures[endpoint])

    monkeypatch.setattr(
        cli.Settings, "from_environment",
        lambda: Settings(fuseki_user=TEST_USER, fuseki_password=TEST_PASSWORD),
    )
    assert cli.main([
        "dev", "bootstrap", "--raw-dir", str(raw_root),
        "--state-db", str(state_path), "--fuseki-gsp-url", TEST_GSP,
        "--fuseki-sparql-url", TEST_SPARQL,
    ]) == 0
    output = capsys.readouterr().out
    assert "Quarantined conflicts: 1" in output
    assert "Reference closure: NOT authoritative / not complete" in output

    client = FusekiSparqlClient(
        TEST_SPARQL, user=TEST_USER, password=TEST_PASSWORD)
    def has_type(graph_iri: str, subject: str, class_iri) -> bool:
        rows = client.query(
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
            f"SELECT ?type WHERE {{ GRAPH <{graph_iri}> "
            f"{{ <{subject}> rdf:type ?type }} }}")
        return any(row["type"]["value"] == str(class_iri) for row in rows)

    # Historical Party, Independent, constituency/panel and valid
    # Committee owners remain queryable despite the separate quarantine.
    assert has_type(
        PARTIES_GRAPH,
        "https://data.oireachtas.ie/ie/oireachtas/party/seanad/26/Fianna_Fáil",
        MEMBERS.ParliamentaryParty,
    )
    assert has_type(
        PARTIES_GRAPH,
        "https://data.oireachtas.ie/ie/oireachtas/party/dail/31/Independent",
        MEMBERS.IndependentMemberCollection,
    )
    assert has_type(
        CONSTITUENCIES_GRAPH,
        "https://data.oireachtas.ie/ie/oireachtas/house/seanad/26/panel/Nominated-by-the-Taoiseach",
        MEMBERS.SeanadPanel,
    )
    assert has_type(
        COMMITTEES_GRAPH,
        "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/"
        "joint_committee_on_environment_and_climate_action",
        MEMBERS.Committee,
    )
    assert client.query(
        f"SELECT ?p WHERE {{ GRAPH <{COMMITTEES_GRAPH}> "
        f"{{ <{KNOWN_CONFLICT_COMMITTEE}> ?p ?o }} }}") == []
    member_iri = member_graph_iri(captures["members"][0]["member"])
    assert client.query(
        "PREFIX members: <https://data.oireachtas.ie/ontology/members#> "
        f"SELECT ?membership WHERE {{ GRAPH <{member_iri}> "
        f"{{ ?membership members:isCommitteeMembershipOf "
        f"<{KNOWN_CONFLICT_COMMITTEE}> }} }}")

    monkeypatch.setenv("NLQ_FUSEKI_QUERY_URL", TEST_SPARQL)
    if TEST_USER is not None:
        monkeypatch.setenv("OIR_FUSEKI_USER", TEST_USER)
    else:
        monkeypatch.delenv("OIR_FUSEKI_USER", raising=False)
    if TEST_PASSWORD is not None:
        monkeypatch.setenv("OIR_FUSEKI_PASSWORD", TEST_PASSWORD)
    else:
        monkeypatch.delenv("OIR_FUSEKI_PASSWORD", raising=False)
    with TestClient(create_app(repository_root=ROOT)) as poc:
        response = poc.get("/")
    assert response.status_code == 200
    assert "Oireachtas NLQ POC" in response.text
