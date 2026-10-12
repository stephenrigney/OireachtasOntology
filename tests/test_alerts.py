from __future__ import annotations

import json
from pathlib import Path

import pytest

from oireachtas_etl.alerts import (
    AlertError,
    mark_degraded_alert_delivered,
    prepare_degraded_alert,
)
from oireachtas_etl.state import CoreStateStore


def _run(store: CoreStateStore, outcome: str, completed_at: str, *,
         endpoint: str = "members") -> str:
    run_id = store.start_run(endpoint, "full_refresh", is_complete=True,
                             parameters={"test": "degraded-alert"})
    if outcome == "success":
        store.finish_run(run_id, outcome="success", completed_at=completed_at)
    else:
        store.finish_run(
            run_id, outcome=outcome, completed_at=completed_at,
            failure_scope="record" if outcome == "degraded" else "run",
            failure_classification=f"test_{outcome}", error=f"synthetic {outcome}")
    return run_id


def test_alert_requires_consecutive_degraded_runs_and_deduplicates_episode(tmp_path):
    state_db = tmp_path / "core-state.sqlite"
    alert_dir = tmp_path / "alerts"
    with CoreStateStore(state_db) as store:
        first = _run(store, "degraded", "2026-10-01T01:00:00Z")
        _run(store, "success", "2026-10-01T02:00:00Z", endpoint="houses")
        assert prepare_degraded_alert(state_db, alert_dir, threshold=2) is None
        second = _run(store, "degraded", "2026-10-02T01:00:00Z")

    pending = prepare_degraded_alert(state_db, alert_dir, threshold=2)
    assert pending is not None
    assert pending["event"] == "degraded_run_streak"
    assert pending["threshold"] == 2
    assert pending["episodes"][0]["endpoint"] == "members"
    assert pending["episodes"][0]["streak_start_run_id"] == first
    assert pending["episodes"][0]["latest_run_id"] == second
    assert pending["episodes"][0]["count"] == 2
    assert (alert_dir / "pending.json").stat().st_mode & 0o777 == 0o600

    # A notification which hasn't been delivered is retried exactly as stored.
    assert prepare_degraded_alert(state_db, alert_dir, threshold=4) == pending
    delivered = mark_degraded_alert_delivered(alert_dir)
    assert delivered["event_id"] == pending["event_id"]
    assert not (alert_dir / "pending.json").exists()
    assert prepare_degraded_alert(state_db, alert_dir, threshold=2) is None

    with CoreStateStore(state_db) as store:
        _run(store, "degraded", "2026-10-03T01:00:00Z")
        _run(store, "failed", "2026-10-04T01:00:00Z")
    assert prepare_degraded_alert(state_db, alert_dir, threshold=2) is None

    with CoreStateStore(state_db) as store:
        third = _run(store, "degraded", "2026-10-05T01:00:00Z")
        fourth = _run(store, "degraded", "2026-10-06T01:00:00Z")
    next_pending = prepare_degraded_alert(state_db, alert_dir, threshold=2)
    assert next_pending is not None
    assert next_pending["episodes"][0]["streak_start_run_id"] == third
    assert next_pending["episodes"][0]["latest_run_id"] == fourth


def test_alert_state_fails_closed_on_symlink_and_invalid_threshold(tmp_path):
    state_db = tmp_path / "core-state.sqlite"
    with CoreStateStore(state_db):
        pass
    alert_dir = tmp_path / "alerts"
    alert_dir.mkdir()
    target = tmp_path / "outside.json"
    target.write_text(json.dumps({"format": 1, "episodes": {}}), encoding="utf-8")
    (alert_dir / "state.json").symlink_to(target)

    with pytest.raises(AlertError, match="symlink"):
        prepare_degraded_alert(state_db, alert_dir, threshold=2)
    with pytest.raises(AlertError, match="at least 2"):
        prepare_degraded_alert(state_db, tmp_path / "other-alerts", threshold=1)


def test_pending_alert_delivery_rejects_corrupt_event(tmp_path):
    alert_dir = tmp_path / "alerts"
    alert_dir.mkdir()
    (alert_dir / "pending.json").write_text('{"event":"wrong"}', encoding="utf-8")
    with pytest.raises(AlertError, match="malformed"):
        mark_degraded_alert_delivered(alert_dir)
