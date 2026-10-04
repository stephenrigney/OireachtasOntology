"""Member publication integration for local office acceptance and retention."""
from __future__ import annotations

from argparse import Namespace
import hashlib
import json
from pathlib import Path
import uuid

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.office_observations import extract_office_observations
from oireachtas_etl.office_reconciliation import OfficeOccurrenceStore
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.common import MEMBERS, OIR


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registries/ministerial-office-registry.json"
SOURCE = json.loads((ROOT / "data/api_examples/member.json").read_text())
TAOISEACH = "https://data.oireachtas.ie/office/o-000001"
FINANCE = "https://data.oireachtas.ie/office/o-000003"


def _member(*, office_start="2025-01-23", include_office=True, name=None):
    wrapper = json.loads(json.dumps(SOURCE))
    member = wrapper["member"]
    if name is not None:
        member["fullName"] = name
    for item in member["memberships"]:
        item["membership"]["offices"] = []
    if include_office:
        target = next(item["membership"] for item in member["memberships"]
                      if item["membership"]["house"].get("houseNo") == "34")
        target["offices"] = [{"office": {
            "dateRange": {"start": office_start, "end": None},
            "officeName": {"showAs": "Taoiseach", "uri": None},
        }}]
    return wrapper


def _observation_and_key(wrapper):
    pointer = {"path": "fixture/skip-000000.json", "sha256": "a" * 64,
               "json_pointer": "/results/0"}
    observations = extract_office_observations([(wrapper, pointer)])
    assert len(observations) == 1
    with OfficeOccurrenceStore(":memory:") as store:
        result = store.reconcile(observations, json.loads(REGISTRY.read_text()), {},
                                 "b" * 64, run_id="bootstrap")
    return observations[0], result["records"][0]["occurrence_key"]


def _write_review(path, wrapper, *, status="accepted", action=None, target=TAOISEACH):
    observation, key = _observation_and_key(wrapper)
    decision = {
        "status": status,
        "office_iris": [target] if status == "accepted" else [],
        "evidence": ["reviewed test evidence"],
        "reason": "Test review decision with source-bound evidence.",
        "observation_fingerprint": observation["fingerprint"],
    }
    if action is not None:
        decision["action"] = action
    path.write_text(json.dumps({"version": 1, "decisions": {key: decision}}, indent=2))
    return key, observation["fingerprint"]


def _fixture(path, wrapper):
    body = {"head": {"counts": {"memberCount": 1}}, "results": [wrapper]}
    path.write_text(json.dumps(body, ensure_ascii=False))
    return path


def _args(tmp_path, fixture, review_file):
    return Namespace(
        fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"),
        output_nq=None, output_ttl=None, fuseki_gsp_url="http://local.test/data",
        fuseki_sparql_url="http://local.test/query", state_db=str(tmp_path / "core.sqlite"),
        reconciliation_state_file=str(tmp_path / "external.sqlite"),
        office_state_file=str(tmp_path / "offices.sqlite"),
        registry_file=str(REGISTRY), review_file=str(review_file),
    )


def _mock_publication(monkeypatch, *, fail_verification=False, before_replace=None):
    from oireachtas_etl import cli

    calls = []

    class Loader:
        def __init__(self, *args, **kwargs):
            pass

        def replace(self, graph_iri, payload, **kwargs):
            if before_replace is not None:
                before_replace(graph_iri, payload)
            calls.append((graph_iri, payload))

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    if fail_verification:
        attempts = []

        def verify(*args):
            attempts.append(args)
            if len(attempts) == 1:
                raise ValueError("injected post-PUT competency failure")

        monkeypatch.setattr(cli, "verify_member_competency", verify)
    else:
        monkeypatch.setattr(cli, "verify_member_competency", lambda *args: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    return calls


def _graph(payload):
    return Graph().parse(data=payload, format="nt")


def _report(capsys):
    return json.loads(capsys.readouterr().out)


def _other_member():
    wrapper = json.loads(json.dumps(SOURCE))
    member = wrapper["member"]
    old = member["uri"]
    new_code = "Independent-Test-Member"
    new = f"https://data.oireachtas.ie/ie/oireachtas/member/id/{new_code}"

    def replace(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and item.startswith(old):
                    value[key] = new + item[len(old):]
                else:
                    replace(item)
        elif isinstance(value, list):
            for item in value:
                replace(item)

    replace(wrapper)
    member["uri"] = new
    member["memberCode"] = new_code
    for item in member["memberships"]:
        item["membership"].pop("offices", None)
    return wrapper


def _reconcile_office_review_out_of_band(args, wrapper, review_file):
    from oireachtas_etl.office_observations import extract_office_observations
    from oireachtas_etl.office_reconciliation import load_office_review

    registry = json.loads(Path(args.registry_file).read_text())
    decisions, review_hash = load_office_review(Path(review_file), registry)
    observations = extract_office_observations([(
        wrapper, {"path": "out-of-band/response.json", "sha256": "c" * 64,
                 "json_pointer": "/results/0"})])
    with OfficeOccurrenceStore(Path(args.office_state_file)) as office_state:
        return office_state.reconcile(observations, registry, decisions, review_hash,
                                      run_id="out-of-band-review")


def _run_reconcile_offices_command(args, review_file):
    from oireachtas_etl.cli import run_reconcile_offices

    return run_reconcile_offices(Namespace(
        offline=True, fixture=args.fixture, publish=False, responses_file=None,
        all=False, output_nq=None, fuseki_gsp_url=None, fuseki_sparql_url=None,
        registry_file=args.registry_file, review_file=str(review_file),
        raw_dir=args.raw_dir, office_state_file=args.office_state_file,
    ))


def test_offline_member_run_uses_reviewed_bootstrap_without_persistent_ledger(
        tmp_path, capsys):
    from oireachtas_etl.cli import run_members

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    output = tmp_path / "members.nq"
    args = Namespace(
        fixture=str(fixture), offline=True, raw_dir=str(tmp_path / "raw"),
        output_nq=str(output), output_ttl=None, fuseki_gsp_url=None,
        fuseki_sparql_url=None, registry_file=str(REGISTRY), review_file=str(review),
        office_state_file=str(tmp_path / "must-not-exist.sqlite"),
    )

    assert run_members(args) == 0
    report = _report(capsys)
    serialized = output.read_text()
    assert serialized.count(f"<{MEMBERS.OfficeHolding}>") == 1
    assert f"<{MEMBERS.CabinetMembership}>" in serialized
    assert report["office_reconciliation"]["ledger_updated"] is False
    assert report["office_reconciliation"]["accepted"] == 1
    assert not Path(args.office_state_file).exists()


def test_complete_member_scan_retains_missing_holding_and_blocks_without_prior_payload(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)

    assert cli.run_members(args) == 0
    first = _report(capsys)
    assert first["published"] == 1
    first_graph = _graph(calls[-1][1])
    holding = next(first_graph.subjects(RDF.type, MEMBERS.OfficeHolding))
    assert (holding, MEMBERS.heldOffice, URIRef(TAOISEACH)) in first_graph
    assert first["office_reconciliation"]["ledger_updated"] is True

    # The complete Member source changes but the nested office disappears.
    changed = _member(include_office=False, name="Changed Member")
    _fixture(fixture, changed)
    assert cli.run_members(args) == 0
    second = _report(capsys)
    assert second["published"] == 1
    assert second["office_reconciliation"]["retained_holding_records"] == 1
    retained = _graph(calls[-1][1])
    assert holding in set(retained.subjects(RDF.type, MEMBERS.OfficeHolding))

    # The ledger still remembers the acceptance, but the Member state payload
    # is the required proof of what was actually published. Do not replace it.
    with CoreStateStore(Path(args.state_db)) as core:
        core.connection.execute(
            "UPDATE resource_state SET published_payload=NULL "
            "WHERE endpoint='members' AND resource_iri=?",
            (wrapper["member"]["uri"],))
    calls_before = len(calls)
    _fixture(fixture, _member(include_office=False, name="Changed Again"))
    assert cli.run_members(args) == 0
    blocked = _report(capsys)
    assert blocked["published"] == 0 and blocked["skipped"] == 1
    assert blocked["office_preservation_blocked"]
    assert len(calls) == calls_before

    with OfficeOccurrenceStore(Path(args.office_state_file)) as office_state:
        row = next(row for row in office_state.occurrences()
                   if row["member_iri"] == wrapper["member"]["uri"])
        pointer = row["current_raw_pointers"][0]
    raw = Path(args.raw_dir) / pointer["path"]
    assert raw.exists() and hashlib.sha256(raw.read_bytes()).hexdigest() == pointer["sha256"]
    assert pointer["json_pointer"].endswith("/membership/offices/0/office")


def test_conflicted_office_change_retains_exact_prior_holding_dates(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member(office_start="2025-01-23")
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()
    first_graph = _graph(calls[-1][1])
    holding = next(first_graph.subjects(RDF.type, MEMBERS.OfficeHolding))
    first_period = next(first_graph.objects(holding, MEMBERS.hasMembershipDateRange))
    first_start = next(first_graph.objects(first_period, MEMBERS.StartDate))
    assert str(first_start).startswith("2025-01-23")

    changed = _member(office_start="2025-02-01", name="Changed Member")
    _fixture(fixture, changed)
    assert cli.run_members(args) == 0
    report = _report(capsys)
    current = _graph(calls[-1][1])
    assert holding in set(current.subjects(RDF.type, MEMBERS.OfficeHolding))
    current_period = next(current.objects(holding, MEMBERS.hasMembershipDateRange))
    current_start = next(current.objects(current_period, MEMBERS.StartDate))
    assert current_start == first_start
    assert any(item["category"] == "reconciliation_pending"
               for item in report["future_work_omitted"])
    assert report["office_reconciliation"]["review_required"] == 1


def test_only_fingerprint_bound_reviewed_revocation_removes_acceptance(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()
    assert set(_graph(calls[-1][1]).subjects(RDF.type, MEMBERS.OfficeHolding))

    # Plain rejection is not a revocation and keeps the published assertion.
    _write_review(review, wrapper, status="rejected")
    assert cli.run_members(args) == 0
    rejected = _report(capsys)
    assert set(_graph(calls[-1][1]).subjects(RDF.type, MEMBERS.OfficeHolding))
    assert rejected["office_reconciliation"]["revocations_applied"] == 0

    _write_review(review, wrapper, status="rejected", action="revoke")
    assert cli.run_members(args) == 0
    revoked = _report(capsys)
    assert not set(_graph(calls[-1][1]).subjects(RDF.type, MEMBERS.OfficeHolding))
    assert revoked["office_reconciliation"]["revocations_applied"] == 1
    with OfficeOccurrenceStore(Path(args.office_state_file)) as office_state:
        row = next(row for row in office_state.occurrences()
                   if row["member_iri"] == wrapper["member"]["uri"])
        assert row["last_accepted_resolution"]["office_iris"] == [TAOISEACH]


def test_office_post_put_failure_retries_exact_contract_three_payload(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch, fail_verification=True)
    with pytest.raises(ValueError, match="injected post-PUT"):
        cli.run_members(args)
    with CoreStateStore(Path(args.state_db)) as core:
        dirty = core.get_resource("members", wrapper["member"]["uri"])
    assert dirty["publication_state"] == "dirty"
    assert dirty["contract_version"] == 3
    exact_pending = dirty["pending_payload"]

    # The second PUT is a deterministic rebuild of exactly the validated
    # payload left dirty by the failed post-PUT verification.
    assert cli.run_members(args) == 0
    assert _report(capsys)["published"] == 1
    assert len(calls) == 2 and calls[0][1] == calls[1][1] == exact_pending
    with CoreStateStore(Path(args.state_db)) as core:
        clean = core.get_resource("members", wrapper["member"]["uri"])
    assert clean["publication_state"] == "clean"
    assert clean["contract_version"] == 3


def test_contract_two_member_is_republished_once_under_contract_three(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()

    with CoreStateStore(Path(args.state_db)) as core:
        core.connection.execute(
            "UPDATE resource_state SET contract_version=2 "
            "WHERE endpoint='members' AND resource_iri=?",
            (wrapper["member"]["uri"],))
    assert cli.run_members(args) == 0
    upgraded = _report(capsys)
    assert upgraded["changed"] == [wrapper["member"]["uri"]]
    assert len(calls) == 2
    with CoreStateStore(Path(args.state_db)) as core:
        assert core.get_resource("members", wrapper["member"]["uri"])["contract_version"] == 3

    assert cli.run_members(args) == 0
    unchanged = _report(capsys)
    assert unchanged["skipped"] == 1
    assert len(calls) == 2


def test_incomplete_online_fixture_never_reconciles_durable_office_ledger(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = tmp_path / "partial.json"
    fixture.write_text(json.dumps([wrapper]))  # no complete-scan memberCount
    args = _args(tmp_path, fixture, review)
    _mock_publication(monkeypatch)

    assert cli.run_members(args) == 0
    report = _report(capsys)
    assert report["office_reconciliation"]["complete_scan"] is False
    assert report["office_reconciliation"]["ledger_updated"] is False
    with OfficeOccurrenceStore(Path(args.office_state_file)) as office_state:
        assert office_state.occurrences() == []


def test_out_of_band_review_change_rebuilds_hash_unchanged_member_and_retries_exact_payload(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()
    first = _graph(calls[-1][1])
    assert (next(first.subjects(RDF.type, MEMBERS.OfficeHolding)),
            MEMBERS.heldOffice, URIRef(TAOISEACH)) in first

    # A separate local reconciliation run has already made this reviewed
    # outcome durable before `run members` observes the current row.
    _write_review(review, wrapper, target=FINANCE)
    assert _run_reconcile_offices_command(args, review) == 0
    capsys.readouterr()

    attempts = []

    def fail_first_verification(*_args):
        attempts.append(True)
        if len(attempts) == 1:
            raise ValueError("injected post-PUT verification failure")

    monkeypatch.setattr(cli, "verify_member_competency", fail_first_verification)
    with pytest.raises(ValueError, match="injected post-PUT"):
        cli.run_members(args)
    changed_payload = calls[-1][1]
    changed_graph = _graph(changed_payload)
    changed_holding = next(changed_graph.subjects(RDF.type, MEMBERS.OfficeHolding))
    assert (changed_holding, MEMBERS.heldOffice, URIRef(FINANCE)) in changed_graph
    assert not (changed_holding, MEMBERS.heldOffice, URIRef(TAOISEACH)) in changed_graph

    with CoreStateStore(Path(args.state_db)) as core:
        dirty = core.get_resource("members", wrapper["member"]["uri"])
    assert dirty["publication_state"] == "dirty"
    assert dirty["pending_payload"] == changed_payload

    assert cli.run_members(args) == 0
    report = _report(capsys)
    assert report["published"] == 1
    assert calls[-1][1] == changed_payload
    with CoreStateStore(Path(args.state_db)) as core:
        clean = core.get_resource("members", wrapper["member"]["uri"])
    assert clean["publication_state"] == "clean"
    assert clean["contract_version"] == 3


def test_missing_containing_house_membership_blocks_only_that_member(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    other = _other_member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = tmp_path / "members.json"
    fixture.write_text(json.dumps({"head": {"counts": {"memberCount": 2}},
                                   "results": [wrapper, other]}))
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()
    old_payload = next(payload for graph, payload in calls
                       if graph.endswith("/Timmy-Dooley.S.2002-09-12"))
    old_hash = hashlib.sha256(old_payload.encode()).hexdigest()

    changed = _member(include_office=False, name="Changed while membership disappeared")
    changed["member"]["memberships"] = [
        item for item in changed["member"]["memberships"]
        if item["membership"]["house"].get("houseNo") != "34"
    ]
    other_changed = _other_member()
    other_changed["member"]["fullName"] = "Other Member Changed"
    fixture.write_text(json.dumps({"head": {"counts": {"memberCount": 2}},
                                   "results": [changed, other_changed]}))
    before = len(calls)
    assert cli.run_members(args) == 0
    report = _report(capsys)

    assert report["published"] == 1 and report["skipped"] == 1
    blocked = report["office_preservation_blocked"]
    assert len(blocked) == 1
    assert "containing House membership" in blocked[0]["reason"]
    assert "absent from the current Member source" in blocked[0]["reason"]
    assert len(calls) == before + 1
    assert calls[-1][0].endswith("/Independent-Test-Member")
    with CoreStateStore(Path(args.state_db)) as core:
        retained = core.get_resource("members", wrapper["member"]["uri"])
    assert hashlib.sha256(retained["published_payload"].encode()).hexdigest() == old_hash
    assert set(_graph(retained["published_payload"]).subjects(RDF.type, MEMBERS.OfficeHolding))


def test_removed_registry_target_blocks_retained_holding_republication(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()
    initial_calls = len(calls)

    registry = json.loads(REGISTRY.read_text())
    registry["offices"] = [office for office in registry["offices"]
                           if office["key"] != "o-000001"]
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(registry))
    args.registry_file = str(registry_file)
    review.write_text(json.dumps({"version": 1, "decisions": {}}))

    assert cli.run_members(args) == 0
    report = _report(capsys)
    assert report["published"] == 0 and report["skipped"] == 1
    assert len(calls) == initial_calls
    assert report["office_preservation_blocked"]
    assert "absent from the currently registered office_types" in report[
        "office_preservation_blocked"][0]["reason"]
    with CoreStateStore(Path(args.state_db)) as core:
        prior = core.get_resource("members", wrapper["member"]["uri"])
    assert set(_graph(prior["published_payload"]).subjects(RDF.type, MEMBERS.OfficeHolding))


def test_ephemeral_office_store_remains_open_through_member_skip_verification(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    with CoreStateStore(Path(args.state_db)) as core:
        assert cli._run_members_impl(args, core, str(uuid.uuid4())) == 0
        capsys.readouterr()
        assert len(calls) == 1
        assert cli._run_members_impl(args, core, str(uuid.uuid4())) == 0
    report = _report(capsys)
    assert report["skipped"] == 1
    assert len(calls) == 1


def test_migration_inventory_is_written_before_contract_three_put_and_records_legacy_rdf(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.office_observations import extract_office_observations
    from oireachtas_etl.office_reconciliation import load_office_review
    from oireachtas_etl.serialization import ntriples

    wrapper = _member(include_office=False)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    review = tmp_path / "review.json"
    office_wrapper = _member()
    _write_review(review, office_wrapper)
    args = _args(tmp_path, fixture, review)
    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()

    # Inventory a historical office observation that has since disappeared.
    _reconcile_office_review_out_of_band(args, office_wrapper, review)
    registry = json.loads(REGISTRY.read_text())
    decisions, review_hash = load_office_review(review, registry)
    with OfficeOccurrenceStore(Path(args.office_state_file)) as office_state:
        missing_result = office_state.reconcile(
            [], registry, decisions, review_hash, run_id="inventory-missing-observation")
        assert missing_result["records"][0]["source_presence"] == "missing"

    # Simulate a pre-Tranche-3 verified payload, including the legacy office
    # vocabulary that the new whole-graph publication must replace.
    identity = wrapper["member"]["uri"]
    with CoreStateStore(Path(args.state_db)) as core:
        prior = core.get_resource("members", identity)
        graph = _graph(prior["published_payload"])
        graph.add((URIRef(identity), RDF.type, MEMBERS.MinisterOfStateMembership))
        graph.add((URIRef(identity), MEMBERS.officeNameUri, URIRef(TAOISEACH)))
        payload = ntriples(graph)
        payload_hash = hashlib.sha256(payload.encode()).hexdigest()
        core.connection.execute(
            "UPDATE resource_state SET contract_version=2,published_payload=?,published_payload_hash=? "
            "WHERE endpoint='members' AND resource_iri=?",
            (payload, payload_hash, identity))

    observed_inventory = []

    def inspect_before_put(_graph_iri, _payload):
        inventory_paths = list(tmp_path.glob("core.sqlite.member-migration-*.json"))
        assert len(inventory_paths) == 1
        inventory = json.loads(inventory_paths[0].read_text())
        assert inventory["basis"].startswith("verified local CoreStateStore")
        assert inventory["member_graphs"]
        assert inventory["member_graphs"][0]["published_payload"]["verified"] is True
        assert inventory["member_graphs"][0]["published_payload"]["legacy_triples"][
            "MinisterOfStateMembership"] == 1
        assert len(inventory["missing_observations"]) == 1
        assert inventory["missing_observations"][0]["has_last_accepted_resolution"] is True
        assert inventory["missing_observations"][0]["inventory_status"] == (
            "contract_predates_office_holding_publication")
        observed_inventory.append(inventory)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", lambda *args, **kwargs: type(
        "Loader", (), {"replace": lambda self, graph, payload, **kw:
                       (inspect_before_put(graph, payload), calls.append((graph, payload)))})())
    calls.clear()
    assert cli.run_members(args) == 0
    report = _report(capsys)
    assert observed_inventory
    assert report["migration_inventory"]["legacy_member_graphs"] == 1
    assert report["migration_inventory"]["sha256"]
    saved = json.loads(Path(report["migration_inventory"]["path"]).read_text())
    counts = saved["member_graphs"][0]["published_payload"]["legacy_triples"]
    assert counts["MinisterOfStateMembership"] == 1
    assert counts["officeNameUri"] == 1


def test_manifest_without_legacy_payload_records_inventory_gap_before_republish(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    wrapper = _member(include_office=False)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"version": 1, "decisions": {}}))
    args = _args(tmp_path, fixture, review)
    inventory_seen_before_put = []

    def inspect_before_put(_graph_iri, _payload):
        inventory_paths = list(tmp_path.glob("core.sqlite.member-migration-*.json"))
        assert len(inventory_paths) == 1
        inventory = json.loads(inventory_paths[0].read_text())
        entry = inventory["member_graphs"][0]
        assert entry["published_payload"] == {"verified": False, "status": "unavailable"}
        inventory_seen_before_put.append(inventory)

    calls = _mock_publication(monkeypatch)
    assert cli.run_members(args) == 0
    capsys.readouterr()

    with CoreStateStore(Path(args.state_db)) as core:
        core.connection.execute(
            "UPDATE resource_state SET contract_version=2,published_payload=NULL "
            "WHERE endpoint='members' AND resource_iri=?",
            (wrapper["member"]["uri"],))
    calls = _mock_publication(monkeypatch, before_replace=inspect_before_put)

    assert cli.run_members(args) == 0
    report = _report(capsys)
    assert report["published"] == 1 and report["skipped"] == 0
    assert report["migration_inventory"]["blocked_members"] == []
    assert report["migration_inventory"]["inventory_gaps"] == [
        wrapper["member"]["uri"]]
    assert inventory_seen_before_put and len(calls) == 1
    with CoreStateStore(Path(args.state_db)) as core:
        retained = core.get_resource("members", wrapper["member"]["uri"])
    assert retained["publication_state"] == "clean"
    assert retained["contract_version"] == 3


def test_members_and_office_reconciliation_raw_provenance_share_mapping_version(
        tmp_path, capsys):
    from oireachtas_etl import cli

    wrapper = _member()
    review = tmp_path / "review.json"
    _write_review(review, wrapper)
    fixture = _fixture(tmp_path / "members.json", wrapper)
    args = _args(tmp_path, fixture, review)
    args.offline = True
    args.office_state_file = str(tmp_path / "offline-office.sqlite")
    assert cli.run_members(args) == 0
    capsys.readouterr()

    reconcile_args = Namespace(
        offline=True, fixture=str(fixture), publish=False, responses_file=None,
        all=False, output_nq=None, fuseki_gsp_url=None, fuseki_sparql_url=None,
        registry_file=str(REGISTRY), review_file=str(review), raw_dir=str(tmp_path / "raw"),
        office_state_file=str(tmp_path / "reconcile-office.sqlite"),
    )
    cli.run_reconcile_offices(reconcile_args)
    capsys.readouterr()

    metadata = [json.loads(path.read_text()) for path in
                (tmp_path / "raw").glob("members/*/*/*.meta.json")]
    assert len(metadata) >= 2
    assert {item["mapping_version"] for item in metadata} == {
        cli.MEMBER_MAPPING_VERSION}
