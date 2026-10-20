from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oireachtas_etl.raw_captures import (load_complete_capture,
                                         load_latest_complete_capture,
                                         load_authoritative_capture,
                                         load_latest_development_capture,
                                         load_pinned_development_capture,
                                         load_pinned_development_captures)
from oireachtas_etl.state import CoreStateStore


RUN = "12345678-1234-4234-8234-123456789abc"
ROOT = Path(__file__).resolve().parents[1]
BILL_WRAPPER = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]


def _page(directory: Path, *, skip: int, limit: int, records: list[dict], total: int,
          endpoint: str = "parties", count_field: str = "partyCount",
          run_id: str = RUN) -> None:
    body = json.dumps({"head": {"counts": {count_field: total}},
                       "results": records}, sort_keys=True).encode()
    raw = directory / f"skip-{skip:06d}.json"
    raw.write_bytes(body)
    (directory / f"skip-{skip:06d}.meta.json").write_text(json.dumps({
        "run_id": run_id, "status": 200,
        "sha256": hashlib.sha256(body).hexdigest(),
        "endpoint": f"https://api.oireachtas.ie/v1/{endpoint}",
        "params": {"skip": skip, "limit": limit},
    }))


def test_capture_loader_checks_hash_count_and_complete_pagination(tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    records = [{"party": {"uri": f"https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P{i}"}}
               for i in range(3)]
    _page(directory, skip=0, limit=2, records=records[:2], total=3)
    _page(directory, skip=2, limit=2, records=records[2:], total=3)
    loaded, count = load_complete_capture(directory, "parties")
    assert loaded == records and count == 3

    (directory / "skip-000002.json").write_text("{}");
    with pytest.raises(ValueError, match="metadata/run/hash"):
        load_complete_capture(directory, "parties")


def test_capture_loader_rejects_missing_terminal_page_and_advertised_mismatch(tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    records = [{"party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P1"}},
               {"party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P2"}}]
    _page(directory, skip=0, limit=2, records=records, total=2)
    with pytest.raises(ValueError, match="terminal pagination page"):
        load_complete_capture(directory, "parties")

    _page(directory, skip=0, limit=2, records=records[:1], total=2)
    with pytest.raises(ValueError, match="unique records, not its advertised"):
        load_complete_capture(directory, "parties")
    raw_path = directory / "skip-000000.json"
    report_path = directory / "skip-000000.source-envelope-drift.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    finding = next(item for item in report["findings"]
                   if item["change"] == "advertised_count_mismatch")
    assert finding["json_pointer"] == "/head/counts/partyCount"
    assert finding["source_evidence"]["sha256"] == hashlib.sha256(
        raw_path.read_bytes()).hexdigest()


def test_capture_loader_rejects_filename_metadata_pagination_disagreement(tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    records = [{"party": {"uri": f"https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P{i}"}}
               for i in range(2)]
    _page(directory, skip=0, limit=2, records=records, total=2)
    (directory / "skip-000001.json").write_bytes(
        (directory / "skip-000000.json").read_bytes())
    (directory / "skip-000001.meta.json").write_text(
        (directory / "skip-000000.meta.json").read_text())
    with pytest.raises(ValueError, match="filename does not match pagination order"):
        load_complete_capture(directory, "parties")


def test_latest_capture_is_selected_only_from_core_successful_complete_run(tmp_path):
    directory = tmp_path / "parties" / "2026-10-05" / f"run-{RUN}"
    directory.mkdir(parents=True)
    record = {"party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P1"}}
    _page(directory, skip=0, limit=2, records=[record], total=1)

    class Store:
        def last_successful_complete_run(self, endpoint):
            assert endpoint == "parties"
            return {"run_id": RUN, "parameters": {"source": "api"}}

        def successful_complete_run(self, endpoint, run_id):
            assert endpoint == "parties" and run_id == RUN
            return {"run_id": RUN, "status": "succeeded", "is_complete": 1,
                    "parameters": {"source": "api",
                                   "api_url": "https://api.oireachtas.ie/v1/parties"}}

    loaded, evidence = load_latest_complete_capture(tmp_path, Store(), "parties")
    assert loaded == [record]
    assert evidence["run_id"] == RUN and evidence["advertised_count"] == 1

    class NoCompleteStore:
        def last_successful_complete_run(self, _endpoint):
            return None

        def successful_complete_run(self, _endpoint, _run_id):
            return None

    assert load_latest_complete_capture(tmp_path, NoCompleteStore(), "parties") is None


def test_fixture_capture_cannot_be_promoted_to_authoritative_by_matching_page_counts(tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    record = {"party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P1"}}
    _page(directory, skip=0, limit=2, records=[record], total=1)

    class FixtureRunStore:
        def successful_complete_run(self, endpoint, run_id):
            return {"run_id": run_id, "status": "succeeded", "is_complete": 1,
                    "parameters": {"source": "fixture",
                                   "api_url": "https://api.oireachtas.ie/v1/parties"}}

    with pytest.raises(ValueError, match="not a successful complete authoritative run"):
        load_authoritative_capture(directory, "parties", FixtureRunStore())


def test_members_capture_rejects_distinct_source_iris_with_one_member_graph(
        tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    records = [
        {"member": {"uri": "https://data.oireachtas.ie/ie/oireachtas/member/id/A",
                    "memberCode": "A"}},
        {"member": {"uri": "https://data.oireachtas.ie/ie/oireachtas/member/id/%41",
                    "memberCode": "A"}},
    ]
    body = json.dumps({"head": {"counts": {"memberCount": 2}},
                       "results": records}, sort_keys=True).encode()
    raw = directory / "skip-000000.json"
    raw.write_bytes(body)
    (directory / "skip-000000.meta.json").write_text(json.dumps({
        "run_id": RUN, "status": 200,
        "sha256": hashlib.sha256(body).hexdigest(),
        "endpoint": "https://api.oireachtas.ie/v1/members",
        "params": {"skip": 0, "limit": 3},
    }))

    with pytest.raises(ValueError, match="Member (memberCode|graph IRI) collision"):
        load_complete_capture(directory, "members")


def test_legislation_capture_deduplicates_with_bill_identity_and_source_hash_rules(
        tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    duplicate = json.loads(json.dumps(BILL_WRAPPER))
    _page(directory, skip=0, limit=3, records=[BILL_WRAPPER, duplicate], total=1,
          endpoint="legislation", count_field="billCount")
    loaded, count = load_complete_capture(directory, "legislation")
    assert loaded == [BILL_WRAPPER] and count == 1


def test_legislation_capture_rejects_conflicting_duplicate_bill_and_graph_alias(
        tmp_path):
    directory = tmp_path / f"run-{RUN}"
    directory.mkdir()
    changed = json.loads(json.dumps(BILL_WRAPPER))
    changed["bill"]["longTitleEn"] = "Conflicting source version"
    _page(directory, skip=0, limit=3, records=[BILL_WRAPPER, changed], total=1,
          endpoint="legislation", count_field="billCount")
    with pytest.raises(ValueError, match="conflicting duplicate Bill source identity"):
        load_complete_capture(directory, "legislation")

    aliased = json.loads(json.dumps(BILL_WRAPPER))
    aliased["bill"]["uri"] = aliased["bill"]["uri"].removesuffix("60") + "%36%30"
    _page(directory, skip=0, limit=3, records=[BILL_WRAPPER, aliased], total=2,
          endpoint="legislation", count_field="billCount")
    with pytest.raises(ValueError, match="Bill graph IRI collision"):
        load_complete_capture(directory, "legislation")


def test_development_selector_loads_successful_complete_legislation_read_only(
        tmp_path):
    state_path = tmp_path / "core.sqlite"
    raw_root = tmp_path / "raw"
    api_url = "https://api.oireachtas.ie/v1/legislation"
    with CoreStateStore(state_path) as store:
        run_id = store.start_run(
            "legislation", "complete_source_reconciliation", is_complete=True,
            parameters={"source": "api", "api_url": api_url, "limit": 2},
        )
        store.finish_run(run_id, success=True)
    directory = raw_root / "legislation" / "2026-10-12" / f"run-{run_id}"
    directory.mkdir(parents=True)
    _page(directory, skip=0, limit=2, records=[BILL_WRAPPER], total=1,
          endpoint="legislation", count_field="billCount", run_id=run_id)

    before = hashlib.sha256(state_path.read_bytes()).hexdigest()
    loaded, evidence = load_latest_development_capture(
        raw_root, state_path, "legislation")
    after = hashlib.sha256(state_path.read_bytes()).hexdigest()
    assert loaded == [BILL_WRAPPER]
    assert evidence["run_id"] == run_id and evidence["advertised_count"] == 1
    page_meta = json.loads(
        (directory / "skip-000000.meta.json").read_text(encoding="utf-8"))
    assert evidence["page_hashes"] == [{
        "skip": 0, "sha256": page_meta["sha256"],
    }]
    assert before == after


def test_pinned_development_capture_uses_page_evidence_without_a_state_database(tmp_path):
    raw_root = tmp_path / "raw"
    directory = raw_root / "parties" / "2026-10-12" / f"run-{RUN}"
    directory.mkdir(parents=True)
    record = {"party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/P1"}}
    _page(directory, skip=0, limit=2, records=[record], total=1)
    metadata = json.loads((directory / "skip-000000.meta.json").read_text())
    selected = {
        "endpoint": "parties",
        "run_id": RUN,
        "source_url": "https://api.oireachtas.ie/v1/parties",
        "record_count": 1,
        "page_limit": 2,
        "page_hash_manifest_sha256": hashlib.sha256(json.dumps(
            [{"skip": 0, "sha256": metadata["sha256"]}],
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }

    loaded, evidence = load_pinned_development_capture(raw_root, selected)

    assert loaded == [record]
    assert evidence["run_id"] == RUN
    assert evidence["advertised_count"] == 1
    assert evidence["parameters"] == {
        "source": "api", "api_url": "https://api.oireachtas.ie/v1/parties", "limit": 2,
    }
    selected["page_hash_manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="differ from the committed selection"):
        load_pinned_development_capture(raw_root, selected)


def test_committed_development_api_selection_pins_the_accepted_bills_run():
    path = ROOT / "poc/nlq/benchmarks/development-api-capture-selection.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["status"] == "accepted-complete-api-captures"
    selected = {item["endpoint"]: item for item in document["captures"]}
    assert set(selected) == {"houses", "parties", "constituencies", "members", "legislation"}
    assert {endpoint: (item["run_id"], item["record_count"])
            for endpoint, item in selected.items()} == {
        "houses": ("896630a4-9389-4a8f-bf58-65c16a05425c", 68),
        "parties": ("91255248-e348-4d60-a8d6-73a26df49f8b", 11),
        "constituencies": ("e6a472b1-b6e0-4e02-8304-9e6cfa73c44d", 8),
        "members": ("d2c089d0-5203-40f1-97b8-ae0d8285e74d", 1928),
        "legislation": ("7bab00fc-4637-463e-a42e-fdb7ce626439", 6048),
    }
    assert all(len(item["page_hash_manifest_sha256"]) == 64 for item in selected.values())


def test_development_selection_loader_rejects_missing_endpoint_pins(tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({
        "schema_version": 1,
        "status": "accepted-complete-api-captures",
        "purpose": "test",
        "constraints": ["test"],
        "captures": [],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="each supported endpoint once"):
        load_pinned_development_captures(tmp_path / "raw", selection)


def test_development_selection_loader_rejects_boolean_schema_version(tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text(json.dumps({
        "schema_version": True,
        "status": "accepted-complete-api-captures",
        "purpose": "test",
        "constraints": ["test"],
        "captures": [],
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported shape"):
        load_pinned_development_captures(tmp_path / "raw", selection)


def test_failed_complete_legislation_run_is_not_selectable(tmp_path):
    state_path = tmp_path / "core.sqlite"
    raw_root = tmp_path / "raw"
    api_url = "https://api.oireachtas.ie/v1/legislation"
    with CoreStateStore(state_path) as store:
        run_id = store.start_run(
            "legislation", "complete_source_reconciliation", is_complete=True,
            parameters={"source": "api", "api_url": api_url, "limit": 2},
        )
        store.finish_run(run_id, success=False, error="transformation failed")
    directory = raw_root / "legislation" / "2026-10-12" / f"run-{run_id}"
    directory.mkdir(parents=True)
    _page(directory, skip=0, limit=2, records=[BILL_WRAPPER], total=1,
          endpoint="legislation", count_field="billCount", run_id=run_id)

    with pytest.raises(ValueError, match="no successful complete API legislation capture"):
        load_latest_development_capture(raw_root, state_path, "legislation")
