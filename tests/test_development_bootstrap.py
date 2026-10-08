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
from oireachtas_etl.state import CoreStateStore, read_resource_state
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.bills import (bill_graph_iri,
                                              source_hash as bill_source_hash,
                                              transform_bill_with_report)
from oireachtas_etl.transforms.members import (member_graph_iri,
                                                source_hash as member_source_hash,
                                                transform_member_with_report)
from oireachtas_etl.transforms.parties import transform_parties
from oireachtas_etl.office_observations import extract_office_observations
from oireachtas_etl.office_reconciliation import OfficeOccurrenceStore
from oireachtas_etl.validation.bills import validate_bill
from oireachtas_etl.validation.members import validate_member


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


def _bill_variant(number: int) -> dict:
    wrapper = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
    bill = wrapper["bill"]
    old_iri = bill["uri"]
    new_iri = old_iri.rsplit("/", 1)[0] + f"/{number}"

    def replace(value):
        if isinstance(value, dict):
            for key, item in list(value.items()):
                if isinstance(item, str) and item.startswith(old_iri):
                    value[key] = new_iri + item[len(old_iri):]
                else:
                    replace(item)
        elif isinstance(value, list):
            for item in value:
                replace(item)

    replace(wrapper)
    bill["uri"] = new_iri
    bill["billNo"] = number
    return wrapper


def _publish_resource(state: CoreStateStore, endpoint: str, wrapper: dict,
                      graph: Graph, *, contract_version: int = 1,
                      run_id: str = "test-source-run") -> dict:
    resource = wrapper["bill"] if endpoint == "legislation" else wrapper["member"]
    resource_iri = resource["uri"]
    graph_iri = (bill_graph_iri(resource) if endpoint == "legislation"
                 else member_graph_iri(resource))
    source_digest = (bill_source_hash(resource) if endpoint == "legislation"
                     else member_source_hash(resource))
    state.observe_resource(endpoint, resource_iri, graph_iri, source_digest, run_id)
    payload = ntriples(graph)
    payload_hash = state.mark_publication_dirty(
        endpoint, resource_iri, source_hash=source_digest,
        graph_iri=graph_iri, payload=payload,
        contract_version=contract_version)
    state.complete_publication(
        endpoint, resource_iri, source_hash=source_digest,
        graph_iri=graph_iri, payload_hash=payload_hash,
        contract_version=contract_version)
    return state.get_resource(endpoint, resource_iri)


def _accepted_taoiseach_member(wrapper: dict) -> tuple[Graph, list[dict], dict]:
    """Build test state through the existing local reconciliation/ETL path."""
    wrapper = copy.deepcopy(wrapper)
    member = wrapper["member"]
    for membership in member["memberships"]:
        membership["membership"]["offices"] = []
    house_membership = next(
        item["membership"] for item in member["memberships"]
        if item["membership"]["house"].get("houseNo") == "34")
    house_membership["offices"] = [
        {"office": {
            "dateRange": {"start": "2025-01-23", "end": None},
            "officeName": {"showAs": "Taoiseach", "uri": None},
        }},
        {"office": {
            "dateRange": {"start": "2025-02-25", "end": "2025-06-01"},
            "officeName": {
                "showAs": "Minister of State at the Department of Agriculture, Food and the Marine and at the Department of the Environment, Climate and Communications",
                "uri": None,
            },
        }},
    ]
    pointer = {"path": "fixture/current-members.json", "sha256": "a" * 64,
               "json_pointer": "/results/0"}
    observations = extract_office_observations([(wrapper, pointer)])
    registry = json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())
    with OfficeOccurrenceStore(":memory:") as office_state:
        resolution = office_state.reconcile(
            observations, registry, {}, "b" * 64, run_id="test-bootstrap-accepted")
    current, _retained, _revoked = cli._accepted_office_ledger_rows(
        resolution["records"], observations, {}, allow_revocation=False)
    office_types = {
        str(cli.office_iri(office["key"])): office["office_type"]
        for office in registry["offices"]
    }
    records = current[member["uri"]]
    graph, _diagnostics = transform_member_with_report(
        wrapper, office_resolutions=records, office_types=office_types)
    validate_member(wrapper, graph, office_resolutions=records,
                    office_types=office_types)
    return graph, records, wrapper


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
        dataset_baseline_output=str(tmp_path / "baseline-1.json"),
    )
    assert cli._run_development_bootstrap(args) == 0
    output = capsys.readouterr().out
    assert "Local development reference bootstrap:" in output
    assert "Quarantined conflicts: 1" in output
    assert "Unresolved development references: 1" in output
    assert "Reference closure: NOT authoritative / not complete" in output
    assert "Dataset identity: sha256:" in output
    assert KNOWN_CONFLICT_COMMITTEE in output
    baseline_path = Path(args.dataset_baseline_output)
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert baseline["schema_version"] == 1
    assert baseline["dataset"]["id"].startswith("sha256:")
    assert "configured office/unit registry digest" in baseline["dataset"]["identity_method"]
    assert baseline["dataset"]["authority"] == "non-authoritative development dataset"
    assert baseline["dataset"]["authoritative_reference_closure_complete"] is False
    assert set(baseline["source_captures"]) == {
        "houses", "parties", "constituencies", "members",
    }
    assert all(item["run_id"] and item["source_url"]
               for item in baseline["source_captures"].values())
    assert baseline["source_record_counts"] == {
        endpoint: len(captures[endpoint])
        for endpoint in ("houses", "parties", "constituencies", "members")
    }
    assert [item["name"] for item in baseline["graph_families_loaded"]] == [
        "houses", "parties", "constituencies", "committees",
        "administrative-units", "offices", "members",
    ]
    assert baseline["optional_graph_families"] == [{
        "name": "bills",
        "graph_iri_pattern": "https://data.oireachtas.ie/graph/bill/{year}/{number}",
        "graph_count": 0,
        "status": "no-eligible-published-resources",
    }]
    assert baseline["rdf_resource_counts"]["members"] == 1
    assert baseline["rdf_resource_counts"]["administrative_units"] == 1
    assert baseline["rdf_resource_counts"]["named_offices"] == 3
    assert baseline["rdf_resource_counts"]["bills"] == 0
    assert baseline["source_evidence"]["bill_publications"]["eligible_resource_count"] == 0
    assert baseline["source_evidence"]["member_publications"]["exact_current_graph_count"] == 0
    assert baseline["source_evidence"]["member_office_registry_references"]["status"] == "verified"
    assert baseline["quarantined_conflict_count"] == 1
    assert baseline["quarantined_conflicted_identities"][0]["canonical_iri"] == (
        KNOWN_CONFLICT_COMMITTEE)
    assert baseline["unresolved_reference_count"] == 1
    assert baseline["reference_closure"] == "NOT authoritative / not complete"
    assert "not a live census" in baseline["scope_note"]
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
    assert upload_order[4:6] == [
        "https://data.oireachtas.ie/graph/administrative-units",
        "https://data.oireachtas.ie/graph/offices",
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
    unit_graph = uploaded["https://data.oireachtas.ie/graph/administrative-units"]
    office_graph = uploaded["https://data.oireachtas.ie/graph/offices"]
    assert any(unit_graph.subjects(RDF.type, MEMBERS.AdministrativeUnit))
    assert any(office_graph.subjects(RDF.type, MEMBERS.NamedOffice))
    finance = URIRef("https://data.oireachtas.ie/office/o-000003")
    assert (finance, MEMBERS.headsAdministrativeUnit,
            URIRef("https://data.oireachtas.ie/administrative-unit/u-000001")) in office_graph
    member_graph = next(graph for iri, graph in uploaded.items()
                        if iri.startswith("https://data.oireachtas.ie/graph/member/"))
    assert (None, MEMBERS.isCommitteeMembershipOf,
            URIRef(KNOWN_CONFLICT_COMMITTEE)) in member_graph
    assert not set(member_graph.subjects(RDF.type, MEMBERS.OfficeHolding))
    assert not set(member_graph.subjects(RDF.type, MEMBERS.CabinetMembership))

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


def test_bootstrap_reuses_accepted_member_output_and_clean_bill_publication_read_only(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import config

    raw_root = tmp_path / "raw"
    state_path = tmp_path / "core.sqlite"
    reconciliation_path = tmp_path / "reconciliation.sqlite"
    office_state_path = tmp_path / "office-occurrences.sqlite"
    captures = _records()
    accepted_graph, _accepted_records, accepted_wrapper = _accepted_taoiseach_member(
        captures["members"][0])
    assert len(set(accepted_graph.subjects(RDF.type, MEMBERS.OfficeHolding))) == 1
    assert len(set(accepted_graph.subjects(RDF.type, MEMBERS.CabinetMembership))) == 1
    assert (None, MEMBERS.heldOffice,
            URIRef("https://data.oireachtas.ie/office/o-000003")) not in accepted_graph

    bill_wrapper = _bill_variant(60)
    bill_graph, _ = transform_bill_with_report(bill_wrapper)
    validate_bill(bill_wrapper, bill_graph)
    captures["members"] = [accepted_wrapper]
    with CoreStateStore(state_path) as state:
        for endpoint in ("houses", "parties", "constituencies", "members"):
            _persist_capture(raw_root, state, endpoint, captures[endpoint])
        _publish_resource(state, "members", accepted_wrapper, accepted_graph,
                          contract_version=3, run_id="reviewed-member-source")
        _publish_resource(state, "legislation", bill_wrapper, bill_graph,
                          contract_version=1, run_id="bill-publication-source")

    for path, value in ((reconciliation_path, "reconciliation-unchanged"),
                        (office_state_path, "office-ledger-unchanged")):
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
            connection.execute("INSERT INTO marker VALUES (?)", (value,))
    core_hash = _hash(state_path)
    reconciliation_hash = _hash(reconciliation_path)
    office_hash = _hash(office_state_path)
    uploaded: dict[str, Graph] = {}

    class Loader:
        def __init__(self, *_args, **_kwargs):
            pass

        def replace(self, graph_iri, payload, *, content_type):
            assert content_type == "application/n-triples"
            uploaded[graph_iri] = Graph().parse(data=payload, format="nt")

    class Client:
        def __init__(self, *_args, **_kwargs):
            pass

    def verify(_client, graph_iri, payload):
        assert set(uploaded[graph_iri]) == set(Graph().parse(data=payload, format="nt"))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("development bootstrap must not reconcile or fetch source data")

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_core_graph", verify)
    monkeypatch.setattr(cli, "ApiClient", forbidden)
    monkeypatch.setattr(cli, "OfficeOccurrenceStore", forbidden)
    monkeypatch.setattr(cli, "ReconciliationStore", forbidden)
    monkeypatch.setattr(cli.Settings, "from_environment", lambda: config.Settings(
        raw_dir=raw_root, core_state_db_file=state_path,
        reconciliation_state_db_file=reconciliation_path,
    ))

    baseline_path = tmp_path / "published-baseline.json"
    args = Namespace(
        raw_dir=str(raw_root), state_db=str(state_path),
        fuseki_gsp_url="http://127.0.0.1:3030/houses/data",
        fuseki_sparql_url="http://127.0.0.1:3030/houses/query",
        dataset_baseline_output=str(baseline_path),
    )
    assert cli._run_development_bootstrap(args) == 0
    capsys.readouterr()

    bill_graph_name = bill_graph_iri(bill_wrapper["bill"])
    assert bill_graph_name in uploaded
    assert (URIRef(bill_wrapper["bill"]["uri"]), RDF.type,
            cli.ELIDL.DraftLegislationWork) in uploaded[bill_graph_name]
    office_holding_graph = uploaded[member_graph_iri(accepted_wrapper["member"])]
    assert len(set(office_holding_graph.subjects(RDF.type, MEMBERS.OfficeHolding))) == 1
    assert len(set(office_holding_graph.subjects(RDF.type, MEMBERS.CabinetMembership))) == 1
    # The unresolved two-department source observation remains unpromoted.
    assert set(office_holding_graph) == set(accepted_graph)

    baseline = json.loads(baseline_path.read_text())
    assert baseline["rdf_resource_counts"]["bills"] == 1
    assert baseline["rdf_resource_counts"]["office_holdings"] == 1
    assert baseline["rdf_resource_counts"]["cabinet_memberships"] == 1
    assert baseline["source_evidence"]["bill_publications"]["eligible_resource_count"] == 1
    assert baseline["source_evidence"]["bill_publications"]["source_run_ids"] == [
        "bill-publication-source",
    ]
    assert baseline["source_evidence"]["member_publications"]["exact_current_graph_count"] == 1
    assert baseline["source_evidence"]["member_office_registry_references"] == {
        "status": "verified",
        "member_graph_count": 1,
        "office_holding_count": 1,
        "distinct_held_office_count": 1,
        "registered_office_count": 3,
        "office_administrative_unit_link_count": 1,
        "registered_administrative_unit_count": 1,
    }
    assert "bills" in {item["name"] for item in baseline["graph_families_loaded"]}
    first_bytes = baseline_path.read_bytes()

    repeated_args = Namespace(**{
        **vars(args),
        "dataset_baseline_output": str(tmp_path / "published-baseline-repeat.json"),
    })
    uploaded.clear()
    assert cli._run_development_bootstrap(repeated_args) == 0
    capsys.readouterr()
    assert first_bytes == Path(repeated_args.dataset_baseline_output).read_bytes()
    assert _hash(state_path) == core_hash
    assert _hash(reconciliation_path) == reconciliation_hash
    assert _hash(office_state_path) == office_hash


def test_member_output_with_newer_observed_source_is_not_reused():
    wrapper = _records()["members"][0]
    accepted_graph, _records_, wrapper = _accepted_taoiseach_member(wrapper)
    source_digest = member_source_hash(wrapper["member"])
    payload = ntriples(accepted_graph)
    row = {
        "resource_iri": wrapper["member"]["uri"],
        "graph_iri": member_graph_iri(wrapper["member"]),
        "source_presence": "present",
        "publication_state": "clean",
        "contract_version": 3,
        "observed_source_hash": "newer-unpublished-observation",
        "published_source_hash": source_digest,
        "published_payload": payload,
        "published_payload_hash": hashlib.sha256(payload.encode()).hexdigest(),
    }

    graph, reused_publication, _payload_hash = cli._development_member_graph(wrapper, row)

    assert reused_publication is False
    assert not set(graph.subjects(RDF.type, MEMBERS.OfficeHolding))
    assert not set(graph.subjects(RDF.type, MEMBERS.CabinetMembership))


def test_development_bill_selector_reads_temp_core_state_and_skips_nonqualifying_rows(
        tmp_path):
    state_path = tmp_path / "core.sqlite"
    variants = {number: _bill_variant(number) for number in range(60, 66)}
    with CoreStateStore(state_path) as state:
        for number, wrapper in variants.items():
            graph, _ = transform_bill_with_report(wrapper)
            validate_bill(wrapper, graph)
            if number == 61:
                bill = wrapper["bill"]
                source_digest = bill_source_hash(bill)
                graph_iri = bill_graph_iri(bill)
                state.observe_resource("legislation", bill["uri"], graph_iri,
                                       source_digest, "dirty-bill-source")
                state.mark_publication_dirty(
                    "legislation", bill["uri"], source_hash=source_digest,
                    graph_iri=graph_iri, payload=ntriples(graph), contract_version=1)
            else:
                _publish_resource(state, "legislation", wrapper, graph,
                                  contract_version=2 if number == 62 else 1,
                                  run_id=f"bill-source-{number}")
        state.connection.execute(
            "UPDATE resource_state SET observed_source_hash=? "
            "WHERE endpoint='legislation' AND resource_iri=?",
            ("newer-observed-source-hash", variants[65]["bill"]["uri"]))
        state.connection.execute(
            "UPDATE resource_state SET source_presence='missing' "
            "WHERE endpoint='legislation' AND resource_iri=?",
            (variants[63]["bill"]["uri"],))
        state.connection.execute(
            "UPDATE resource_state SET published_payload=NULL "
            "WHERE endpoint='legislation' AND resource_iri=?",
            (variants[64]["bill"]["uri"],))

    state_hash = _hash(state_path)
    rows = read_resource_state(state_path, ("legislation",))["legislation"]
    selected, evidence = cli._development_bills(rows)
    assert len(selected) == 1
    assert selected[0][2]["resource_iri"] == variants[60]["bill"]["uri"]
    assert evidence["eligible_resource_count"] == 1
    assert evidence["resource_rows_examined"] == 6
    assert evidence["skipped_resource_counts"] == {
        "missing-published-payload": 1,
        "not-clean": 1,
        "not-present": 1,
        "published-source-not-current": 1,
        "unsupported-contract-version": 1,
    }
    assert _hash(state_path) == state_hash


def test_read_resource_state_supports_v4_read_only_publication_schema(tmp_path):
    state_path = tmp_path / "core-v4.sqlite"
    payload = "<urn:bill> <urn:predicate> <urn:object> .\n"
    payload_hash = hashlib.sha256(payload.encode()).hexdigest()
    with sqlite3.connect(state_path) as connection:
        connection.execute("PRAGMA user_version=4")
        connection.execute("""CREATE TABLE resource_state (
            endpoint TEXT NOT NULL, resource_iri TEXT NOT NULL, graph_iri TEXT NOT NULL,
            observed_source_hash TEXT,
            published_source_hash TEXT, published_payload_hash TEXT,
            published_payload TEXT, last_seen_run_id TEXT, publication_state TEXT,
            source_presence TEXT, contract_version INTEGER,
            PRIMARY KEY(endpoint, resource_iri))""")
        connection.execute("""INSERT INTO resource_state VALUES (
            'legislation', 'https://data.oireachtas.ie/ie/oireachtas/bill/2025/60',
            'https://data.oireachtas.ie/graph/bill/2025/60', 'source-hash',
            'source-hash', ?, ?,
            'run-v4', 'clean', 'present', 1)""", (payload_hash, payload))
    before = _hash(state_path)

    rows = read_resource_state(state_path, ("legislation",))

    assert rows["legislation"][0]["last_seen_run_id"] == "run-v4"
    assert rows["legislation"][0]["published_payload_hash"] == payload_hash
    assert _hash(state_path) == before
    with sqlite3.connect(f"file:{state_path}?mode=ro", uri=True) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4


def test_development_office_reference_check_fails_closed_for_registry_mismatch():
    member_graph = Graph()
    member_graph.add((URIRef("urn:holding"), MEMBERS.heldOffice,
                      URIRef("https://data.oireachtas.ie/office/unregistered")))

    with pytest.raises(ValueError, match="unregistered heldOffice targets"):
        cli._validate_development_office_references(
            [("urn:member-graph", member_graph)], Graph(), Graph())


@pytest.mark.parametrize("predicate", [
    MEMBERS.headsAdministrativeUnit,
    MEMBERS.assignedToAdministrativeUnit,
])
def test_development_registry_check_fails_for_unregistered_unit_target(predicate):
    office_graph = Graph()
    office_graph.add((URIRef("urn:office"), predicate,
                      URIRef("https://data.oireachtas.ie/administrative-unit/missing")))

    with pytest.raises(ValueError, match="unregistered office administrative-unit targets"):
        cli._validate_development_office_references(
            [], office_graph, Graph())


@pytest.mark.parametrize("corruption", ["graph", "hash", "rdf", "identity"])
def test_development_bill_selector_fails_closed_for_corrupt_clean_publication(
        tmp_path, corruption):
    state_path = tmp_path / "core.sqlite"
    wrapper = _bill_variant(60)
    graph, _ = transform_bill_with_report(wrapper)
    validate_bill(wrapper, graph)
    with CoreStateStore(state_path) as state:
        _publish_resource(state, "legislation", wrapper, graph,
                          contract_version=1, run_id="bill-source")
    row = read_resource_state(state_path, ("legislation",))["legislation"][0]
    if corruption == "graph":
        row["graph_iri"] = "https://data.oireachtas.ie/graph/bill/2025/999"
        error = "graph identity"
    elif corruption == "hash":
        row["published_payload_hash"] = "0" * 64
        error = "payload hash"
    elif corruption == "rdf":
        row["published_payload"] = "not valid N-Triples"
        row["published_payload_hash"] = hashlib.sha256(
            row["published_payload"].encode()).hexdigest()
        error = "cannot be parsed"
    else:
        row["published_payload"] = "<urn:subject> <urn:predicate> <urn:object> .\n"
        row["published_payload_hash"] = hashlib.sha256(
            row["published_payload"].encode()).hexdigest()
        error = "does not describe its Bill"

    with pytest.raises(ValueError, match=error):
        cli._development_bills([row])


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
