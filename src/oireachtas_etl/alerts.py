"""Configurable operational alerts for repeated degraded ETL runs.

The alert ledger is deliberately separate from canonical ETL and reconciliation
state.  It only suppresses repeat notifications for the same consecutive
degradation episode; the durable run outcomes remain the source of truth.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile


class AlertError(RuntimeError):
    """Alert state or durable run history is invalid."""


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict | None:
    if path.is_symlink():
        raise AlertError("alert state files must not be symlinks")
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AlertError("alert state file is unreadable or malformed") from error
    if not isinstance(value, dict):
        raise AlertError("alert state file has an unsupported structure")
    return value


def _write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    if path.parent.is_symlink() or path.is_symlink():
        raise AlertError("alert state paths must not be symlinks")
    payload = _canonical_json(value)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=path.parent, prefix=f".{path.name}.",
                delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        raise AlertError("could not persist operational alert state") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_episode_state(path: Path) -> dict[str, str]:
    value = _read_json(path)
    if value is None:
        return {}
    if set(value) != {"format", "episodes"} or value.get("format") != 1:
        raise AlertError("alert delivery state has an unsupported format")
    episodes = value.get("episodes")
    if (not isinstance(episodes, dict)
            or any(not isinstance(key, str) or not isinstance(item, str)
                   for key, item in episodes.items())):
        raise AlertError("alert delivery state is malformed")
    return episodes


def _latest_degraded_episodes(state_db: Path, threshold: int) -> list[dict]:
    path = state_db.expanduser().resolve()
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("BEGIN")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "etl_run" not in tables:
            raise AlertError("Core State has no persisted ETL run history")
        rows = connection.execute("""SELECT run_id, endpoint, outcome, completed_at, started_at
          FROM etl_run WHERE outcome <> 'running' AND completed_at IS NOT NULL
          ORDER BY endpoint, completed_at DESC, started_at DESC, run_id DESC""").fetchall()
        connection.commit()
    except AlertError:
        raise
    except (sqlite3.Error, OSError, ValueError) as error:
        raise AlertError("could not read persisted ETL run outcomes") from error
    finally:
        if "connection" in locals():
            connection.close()

    by_endpoint: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_endpoint.setdefault(str(row["endpoint"]), []).append(row)

    result = []
    for endpoint, history in sorted(by_endpoint.items()):
        streak = []
        for row in history:
            if row["outcome"] != "degraded":
                break
            streak.append(row)
        if len(streak) < threshold:
            continue
        # ``streak`` is newest-first; its final member identifies the episode
        # even as further degraded runs extend it.
        result.append({
            "endpoint": endpoint,
            "count": len(streak),
            "streak_start_run_id": str(streak[-1]["run_id"]),
            "latest_run_id": str(streak[0]["run_id"]),
            "run_ids": [str(row["run_id"]) for row in streak],
            "latest_completed_at": str(streak[0]["completed_at"]),
        })
    return result


def prepare_degraded_alert(state_db: str | Path, state_dir: str | Path, *,
                           threshold: int) -> dict | None:
    """Create or return one pending notification for a repeated degraded streak.

    Delivery is intentionally a separate host-side step.  The wrapper invokes
    the configured notification program with the pending JSON file and then
    calls :func:`mark_degraded_alert_delivered`; a failed hook leaves the exact
    event pending for retry.
    """
    if (isinstance(threshold, bool) or not isinstance(threshold, int)
            or threshold < 2):
        raise AlertError("degraded-run alert threshold must be an integer of at least 2")
    directory = Path(state_dir).expanduser()
    if directory.is_symlink():
        raise AlertError("alert state directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o750)
    state_path = directory / "state.json"
    pending_path = directory / "pending.json"
    pending = _read_json(pending_path)
    if pending is not None:
        _validate_pending(pending)
        return pending

    alerted = _read_episode_state(state_path)
    candidates = [episode for episode in _latest_degraded_episodes(
        Path(state_db), threshold)
        if alerted.get(episode["endpoint"]) != episode["streak_start_run_id"]]
    if not candidates:
        return None
    created_at = datetime.now(timezone.utc).isoformat()
    identity = {"threshold": threshold, "episodes": candidates}
    event_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
    pending = {
        "format": 1,
        "event_id": event_id,
        "event": "degraded_run_streak",
        "created_at": created_at,
        "threshold": threshold,
        "episodes": candidates,
    }
    _write_atomic(pending_path, pending)
    return pending


def _validate_pending(value: dict) -> None:
    if (set(value) != {"format", "event_id", "event", "created_at", "threshold", "episodes"}
            or value.get("format") != 1
            or not isinstance(value.get("event_id"), str)
            or len(value["event_id"]) != 64
            or value.get("event") != "degraded_run_streak"
            or not isinstance(value.get("created_at"), str)
            or isinstance(value.get("threshold"), bool)
            or not isinstance(value.get("threshold"), int)
            or value["threshold"] < 2
            or not isinstance(value.get("episodes"), list)
            or not value["episodes"]):
        raise AlertError("pending alert event is malformed")
    for episode in value["episodes"]:
        if (not isinstance(episode, dict)
                or not isinstance(episode.get("endpoint"), str)
                or not isinstance(episode.get("streak_start_run_id"), str)
                or not isinstance(episode.get("run_ids"), list)
                or any(not isinstance(run_id, str) for run_id in episode["run_ids"])):
            raise AlertError("pending alert event is malformed")


def mark_degraded_alert_delivered(state_dir: str | Path) -> dict:
    """Record successful dispatch and remove the pending notification."""
    directory = Path(state_dir).expanduser()
    if directory.is_symlink() or not directory.is_dir():
        raise AlertError("alert state directory is unavailable or unsafe")
    pending_path = directory / "pending.json"
    pending = _read_json(pending_path)
    if pending is None:
        raise AlertError("there is no pending degraded-run alert to acknowledge")
    _validate_pending(pending)
    state_path = directory / "state.json"
    episodes = _read_episode_state(state_path)
    for episode in pending["episodes"]:
        episodes[episode["endpoint"]] = episode["streak_start_run_id"]
    _write_atomic(state_path, {"format": 1, "episodes": episodes})
    try:
        pending_path.unlink()
    except OSError as error:
        raise AlertError("alert was recorded but pending notification could not be removed") from error
    return {"event_id": pending["event_id"], "episodes": len(pending["episodes"])}
