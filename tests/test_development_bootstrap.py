from __future__ import annotations

import copy
import hashlib
import json
from argparse import Namespace
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from oireachtas_etl import cli
from oireachtas_etl.config import PARTIES_GRAPH
from oireachtas_etl.config import COMMITTEES_GRAPH
from oireachtas_etl.config import CONSTITUENCIES_GRAPH
from oireachtas_etl.config import ADMINISTRATIVE_UNITS_GRAPH, OFFICES_GRAPH
from oireachtas_etl.config import Settings
from oireachtas_etl.loader import FusekiSparqlClient
from oireachtas_etl.raw import persist_raw
from oireachtas_etl.raw_captures import load_latest_development_capture
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.members import member_graph_iri
from oireachtas_etl.transforms.parties import transform_parties
from oireachtas_etl.transforms.offices import office_iri
from oireachtas_etl.office_observations import extract_office_observations


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
    "legislation": "https://api.oireachtas.ie/v1/legislation",
}
COUNT_FIELDS = {
    "houses": "housesCount", "parties": "partyCount",
    "constituencies": "constituencyCount", "members": "memberCount",
    "legislation": "billCount",
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
    member_data = member["member"]
    member_data["memberCode"] = "Bootstrap-Test-Member"
    member_data["uri"] = (
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Bootstrap-Test-Member")
    for wrapped in member_data["memberships"]:
        record = wrapped["membership"]
        house = record["house"]
        record["uri"] = (
            f"{member_data['uri']}/house/{house['houseCode']}/{house['houseNo']}")
        record["offices"] = []
        if house["houseCode"] == "dail" and str(house["houseNo"]) == "34":
            record["offices"] = [
                {"office": {"officeName": {"showAs": "Taoiseach"},
                            "dateRange": {"start": "2025-01-23", "end": None}}},
                {"office": {"officeName": {"showAs": "Unreviewed office wording"},
                            "dateRange": {"start": "2025-03-01", "end": None}}},
            ]
    membership = member_data["memberships"][0]["membership"]
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
        "legislation": _bill_records(),
    }


def _bill_records() -> list[dict]:
    base = copy.deepcopy(json.loads(
        (ROOT / "data/api_examples/bill.json").read_text())["results"][0])
    records = [base]
    for year, number in (("2024", "48"), ("1959", "P3"),
                         ("1965", "P1"), ("1965", "P3")):
        wrapper = copy.deepcopy(base)
        bill = wrapper["bill"]
        bill["billYear"], bill["billNo"] = year, number
        bill["uri"] = f"https://data.oireachtas.ie/ie/oireachtas/bill/{year}/{number}"
        event = bill["stages"][0]["event"]
        if (year, number) == ("2024", "48"):
            event["stageURI"] = "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/None"
            event["uri"] = bill["uri"] + "/stage/seanad/None"
        else:
            event["dates"][0]["date"] = None
            if (year, number) == ("1959", "P3"):
                wrapper["bill"]["stages"][1]["event"]["dates"][0]["date"] = None
        records.append(wrapper)
    return records


def _accepted_office_review(tmp_path: Path, member: dict) -> Path:
    registry = json.loads(
        (ROOT / "registries/ministerial-office-registry.json").read_text())
    body = json.dumps(member, sort_keys=True).encode("utf-8")
    observations = extract_office_observations([(
        member,
        {"path": "members/test.json", "sha256": hashlib.sha256(body).hexdigest(),
         "json_pointer": ""},
    )])
    accepted = next(item for item in observations if item["label"] == "Taoiseach")
    occurrence_key = "occ-" + accepted["identity_key"]
    review = {
        "version": 1,
        "decisions": {
            occurrence_key: {
                "status": "accepted",
                "office_iris": [str(office_iri("o-000001"))],
                "evidence": ["test-only explicit review of this synthetic observation"],
                "reason": "Exercise the accepted-only Member transformation boundary.",
                "observation_fingerprint": accepted["fingerprint"],
            },
        },
    }
    path = tmp_path / "office-decisions.json"
    path.write_text(json.dumps(review, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_debate_replay():
    manifest_bytes = cli.DEVELOPMENT_DEBATE_SELECTION.read_bytes()
    manifest = json.loads(manifest_bytes)
    outcomes = []
    evidence_sources = []
    for item in manifest["sources"]:
        graph = Graph()
        graph.add((URIRef(item["work_iri"]), RDF.type,
                   URIRef("https://example.test/DebateRecord")))
        outcomes.append(SimpleNamespace(
            source_sha256=item["source_sha256"],
            work_iri=item["work_iri"],
            graph_iri=item["graph_iri"],
            graph=graph,
        ))
        evidence_sources.append({key: item[key] for key in (
            "house_or_committee", "source_url", "source_sha256", "byte_length",
            "work_iri", "graph_iri")})
    return outcomes, {
        "selection_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "sources": sorted(evidence_sources, key=lambda item: item["graph_iri"]),
    }


def test_local_development_bootstrap_is_read_only_to_authoritative_state(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import config

    raw_root = tmp_path / "raw"
    state_path = tmp_path / "core.sqlite"
    reconciliation_path = tmp_path / "reconciliation.sqlite"
    captures = _records()
    review_path = _accepted_office_review(tmp_path, captures["members"][0])
    with CoreStateStore(state_path) as state:
        for endpoint in (
                "houses", "parties", "constituencies", "members", "legislation"):
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
    remote_graphs = {
        "https://data.oireachtas.ie/graph/member/stale-member",
        "https://data.oireachtas.ie/graph/bill/2025/999",
        "https://data.oireachtas.ie/graph/debate/dail/2020-01-01/debate",
        "https://data.oireachtas.ie/graph/member/stale-member/external-links",
        "https://data.oireachtas.ie/graph/debate/not-a-debate-work",
        "urn:unrelated:graph",
    }

    class Loader:
        def __init__(self, *_args, **_kwargs):
            pass

        def replace(self, graph_iri, payload, *, content_type):
            assert content_type == "application/n-triples"
            graph = Graph().parse(data=payload, format="nt") if payload else Graph()
            uploaded[graph_iri] = graph
            remote_graphs.add(graph_iri)
            upload_order.append(graph_iri)

        def delete(self, graph_iri):
            remote_graphs.discard(graph_iri)

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

        def query(self, _query):
            return [{"graph": {"type": "uri", "value": graph}}
                    for graph in sorted(remote_graphs)]

    verified: list[str] = []

    def verify(_client, graph_iri, payload):
        expected = Graph().parse(data=payload, format="nt") if payload else Graph()
        assert set(uploaded[graph_iri]) == set(expected)
        verified.append(graph_iri)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_core_graph", verify)
    monkeypatch.setattr(cli.Settings, "from_environment", lambda: config.Settings())
    monkeypatch.setattr(cli, "_load_development_debates",
                        lambda _raw_root, _scratch: _fake_debate_replay())
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
        review_file=str(review_path),
        dataset_baseline_output=str(tmp_path / "baseline-1.json"),
    )
    assert cli._run_development_bootstrap(args) == 0
    output = capsys.readouterr().out
    assert "Local development reference and evaluation bootstrap:" in output
    assert "Quarantined conflicts: 1" in output
    assert "Unresolved development references: 1" in output
    assert "Reference closure: NOT authoritative / not complete" in output
    assert "Dataset identity: sha256:" in output
    assert KNOWN_CONFLICT_COMMITTEE in output
    baseline_path = Path(args.dataset_baseline_output)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["schema_version"] == 1
    assert baseline["dataset"]["id"].startswith("sha256:")
    assert baseline["dataset"]["authority"] == "non-authoritative development/evaluation dataset"
    assert baseline["dataset"]["authoritative_reference_closure_complete"] is False
    assert set(baseline["source_captures"]) == {
        "houses", "parties", "constituencies", "members", "legislation",
    }
    assert all(item["run_id"] and item["source_url"]
               for item in baseline["source_captures"].values())
    assert baseline["source_record_counts"] == {
        endpoint: len(captures[endpoint])
        for endpoint in (
            "houses", "parties", "constituencies", "members", "legislation")
    }
    assert [item["name"] for item in baseline["graph_families_loaded"]] == [
        "houses", "parties", "constituencies", "committees",
        "administrative-units", "offices", "members", "bill-records", "debates",
    ]
    assert baseline["rdf_resource_counts"]["members"] == 1
    assert baseline["rdf_resource_counts"]["bills"] == 1
    assert baseline["rdf_resource_counts"]["debates"] == 3
    assert baseline["rdf_resource_counts"]["office_holdings"] == 1
    assert baseline["bill_diagnostic_counts"]["source_records"] == 5
    assert baseline["bill_diagnostic_counts"]["represented_graphs"] == 1
    assert baseline["bill_diagnostic_counts"]["quarantined_bills"] == 4
    assert baseline["bill_diagnostic_counts"]["quarantine_diagnostic_paths"] == 5
    assert "4 quarantined Bills; 5 quarantine diagnostic paths" in output
    assert baseline["accepted_holding_evidence"]["accepted_holding_count"] == 1
    assert len(baseline["debate_selection"]["sources"]) == 3
    assert baseline["quarantined_conflict_count"] == 1
    assert baseline["quarantined_conflicted_identities"][0]["canonical_iri"] == (
        KNOWN_CONFLICT_COMMITTEE)
    assert baseline["unresolved_reference_count"] == 1
    assert baseline["reference_closure"] == "NOT authoritative / not complete"
    assert "not authoritative" in baseline["scope_note"]
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
    assert all(iri not in uploaded for iri in (
        "https://data.oireachtas.ie/graph/bill/2024/48",
        "https://data.oireachtas.ie/graph/bill/1959/P3",
        "https://data.oireachtas.ie/graph/bill/1965/P1",
        "https://data.oireachtas.ie/graph/bill/1965/P3",
    ))
    assert remote_graphs == set(uploaded) | {
        "urn:unrelated:graph",
        "https://data.oireachtas.ie/graph/member/stale-member/external-links",
        "https://data.oireachtas.ie/graph/debate/not-a-debate-work",
    }
    assert "https://data.oireachtas.ie/graph/member/stale-member" not in remote_graphs
    assert "https://data.oireachtas.ie/graph/bill/2025/999" not in remote_graphs
    assert "https://data.oireachtas.ie/graph/debate/dail/2020-01-01/debate" not in remote_graphs
    assert "https://data.oireachtas.ie/graph/member/stale-member/external-links" in remote_graphs
    assert "https://data.oireachtas.ie/graph/debate/not-a-debate-work" in remote_graphs

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
    assert any(uploaded[OFFICES_GRAPH].subjects(RDF.type, MEMBERS.NamedOffice))
    assert any(uploaded[ADMINISTRATIVE_UNITS_GRAPH].subjects(
        RDF.type, MEMBERS.AdministrativeUnit))
    assert sum(1 for _ in member_graph.subjects(RDF.type, MEMBERS.OfficeHolding)) == 1
    assert any(iri.startswith("https://data.oireachtas.ie/graph/bill/")
               for iri in uploaded)
    assert len([iri for iri in uploaded
                if iri.startswith("https://data.oireachtas.ie/graph/debate/")]) == 3

    assert _hash(state_path) == state_hash
    assert _hash(reconciliation_path) == reconciliation_hash
    with CoreStateStore(state_path) as state:
        assert state.endpoint_publication("parties") == accepted_publication
        assert state.endpoint_publication("parties")["coverage_authoritative"] is True

    # Repeating the bootstrap over exactly the same preserved capture runs
    # produces byte-for-byte identical machine-readable evaluation metadata.
    repeated_args = Namespace(**{
        **vars(args),
        "dataset_baseline_output": str(tmp_path / "baseline-2.json"),
    })
    assert cli._run_development_bootstrap(repeated_args) == 0
    assert baseline_path.read_bytes() == Path(
        repeated_args.dataset_baseline_output).read_bytes()
    assert _hash(state_path) == state_hash
    assert _hash(reconciliation_path) == reconciliation_hash


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


@pytest.mark.parametrize("protected_location", ["core", "raw", "reconciliation"])
def test_development_baseline_cannot_overwrite_source_or_authority_state(
        tmp_path, monkeypatch, protected_location):
    raw_root = tmp_path / "raw"
    state_db = tmp_path / "core.sqlite"
    reconciliation_db = tmp_path / "reconciliation.sqlite"
    settings = Settings(
        raw_dir=raw_root,
        core_state_db_file=state_db,
        reconciliation_state_db_file=reconciliation_db,
    )
    monkeypatch.setattr(cli.Settings, "from_environment", lambda: settings)
    baseline_target = {
        "core": state_db,
        "raw": raw_root / "baseline.json",
        "reconciliation": reconciliation_db,
    }[protected_location]
    args = Namespace(
        raw_dir=None, state_db=None,
        fuseki_gsp_url="http://127.0.0.1:3030/houses/data",
        fuseki_sparql_url="http://127.0.0.1:3030/houses/query",
        dataset_baseline_output=str(baseline_target),
    )

    with pytest.raises(ValueError, match="outside preserved raw captures"):
        cli._run_development_bootstrap(args)
    assert not state_db.exists()
    assert not reconciliation_db.exists()
    assert not raw_root.exists()


def test_development_bootstrap_cli_accepts_dataset_baseline_output(tmp_path, monkeypatch):
    output_path = tmp_path / "dataset-baseline.json"
    received = {}

    def capture_args(args):
        received["path"] = args.dataset_baseline_output
        return 0

    monkeypatch.setattr(cli, "_run_development_bootstrap", capture_args)
    assert cli.main([
        "dev", "bootstrap", "--dataset-baseline-output", str(output_path),
    ]) == 0
    assert received["path"] == str(output_path)


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


def test_development_debates_replay_exactly_the_pinned_manifest_slice(
        tmp_path, monkeypatch):
    manifest = json.loads(cli.DEVELOPMENT_DEBATE_SELECTION.read_text())
    requested: list[str] = []
    source_by_hash = {item["source_sha256"]: item for item in manifest["sources"]}

    def load_pinned(_raw_root, digest):
        requested.append(digest)
        item = source_by_hash[digest]
        return cli.DebateRawSource(
            digest, tmp_path / "preserved" / f"{digest}.xml",
            (item["source_url"],), b"x" * item["byte_length"],
        )

    staged_sources = []

    def transform_batch(sources):
        staged_sources.extend(sources)
        outcomes = []
        for source in sources:
            item = source_by_hash[source.source_sha256]
            graph = Graph()
            graph.add((URIRef(item["work_iri"]), RDF.type,
                       URIRef("https://example.test/DebateRecord")))
            outcomes.append(SimpleNamespace(
                source_sha256=source.source_sha256,
                work_iri=item["work_iri"], graph_iri=item["graph_iri"], graph=graph))
        return outcomes

    monkeypatch.setattr(cli, "load_main_xml", load_pinned)
    monkeypatch.setattr(cli, "run_debate_batch", transform_batch)
    outcomes, evidence = cli._load_development_debates(
        tmp_path / "preserved", tmp_path / "scratch")

    assert requested == [item["source_sha256"] for item in manifest["sources"]]
    assert len(outcomes) == len(staged_sources) == 3
    assert len({item.graph_iri for item in outcomes}) == 3
    assert all(item.raw_path.is_relative_to(tmp_path / "scratch")
               for item in staged_sources)
    assert evidence["sources"] == sorted(({
        key: item[key] for key in (
            "house_or_committee", "source_url", "source_sha256", "byte_length",
            "work_iri", "graph_iri")
    } for item in manifest["sources"]), key=lambda item: item["graph_iri"])


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
    review_path = _accepted_office_review(tmp_path, captures["members"][0])
    with CoreStateStore(state_path) as state:
        for endpoint in (
                "houses", "parties", "constituencies", "members", "legislation"):
            _persist_capture(raw_root, state, endpoint, captures[endpoint])

    monkeypatch.setattr(
        cli.Settings, "from_environment",
        lambda: Settings(fuseki_user=TEST_USER, fuseki_password=TEST_PASSWORD),
    )
    monkeypatch.setattr(cli, "_load_development_debates",
                        lambda _raw_root, _scratch: _fake_debate_replay())
    assert cli.main([
        "dev", "bootstrap", "--raw-dir", str(raw_root),
        "--state-db", str(state_path), "--fuseki-gsp-url", TEST_GSP,
        "--fuseki-sparql-url", TEST_SPARQL, "--review-file", str(review_path),
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
