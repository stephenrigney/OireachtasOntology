from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oireachtas_etl.raw_captures import (load_complete_capture,
                                         load_latest_complete_capture,
                                         load_authoritative_capture)


RUN = "12345678-1234-4234-8234-123456789abc"


def _page(directory: Path, *, skip: int, limit: int, records: list[dict], total: int) -> None:
    body = json.dumps({"head": {"counts": {"partyCount": total}},
                       "results": records}, sort_keys=True).encode()
    raw = directory / f"skip-{skip:06d}.json"
    raw.write_bytes(body)
    (directory / f"skip-{skip:06d}.meta.json").write_text(json.dumps({
        "run_id": RUN, "status": 200,
        "sha256": hashlib.sha256(body).hexdigest(),
        "endpoint": "https://api.oireachtas.ie/v1/parties",
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
