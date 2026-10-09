"""Fail-closed resource controls for manually invoked Debates batches.

Resource values are read locally. This is a per-process guard, not a monitor or
scheduler; durable Core State and the selected manifest remain the restart point.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import resource
import shutil
import tempfile
import time

GIB = 1024 ** 3

DEFAULT_LIMITS = {
    "tdb2_warn_bytes": 18 * GIB,
    "tdb2_stop_bytes": 21 * GIB,
    "raw_warn_bytes": 3 * GIB,
    "raw_stop_bytes": int(3.5 * GIB),
    "reference_reports_warn_bytes": 8 * GIB,
    "reference_reports_stop_bytes": 9 * GIB,
    "core_state_warn_bytes": 3 * GIB,
    "core_state_stop_bytes": int(3.5 * GIB),
    "temporary_warn_bytes": 2 * GIB,
    "temporary_stop_bytes": 3 * GIB,
    "etl_rss_warn_bytes": int(1.5 * GIB),
    "etl_rss_stop_bytes": 3 * GIB,
    "fuseki_rss_warn_bytes": 6 * GIB,
    "fuseki_rss_stop_bytes": 8 * GIB,
    "host_free_warn_bytes": 80 * GIB,
    "host_free_stop_bytes": 65 * GIB,
    "host_memory_available_warn_bytes": 3 * GIB,
    "host_memory_available_stop_bytes": int(1.5 * GIB),
    "tdb2_projection_factor": 2,
    "minimum_tdb2_free_bytes": 3 * GIB,
    "minimum_raw_free_bytes": GIB // 2,
    "minimum_state_free_bytes": GIB // 2,
    "minimum_temporary_free_bytes": GIB,
}


class ResourceBudgetError(RuntimeError):
    """A hard resource limit was reached or a required measurement was absent."""


def _required_path(paths: dict, key: str) -> Path:
    value = paths.get(key)
    if not isinstance(value, str) or not value:
        raise ResourceBudgetError(f"resource budget path {key!r} is required")
    return Path(value).expanduser().resolve()


def _directory_bytes(root: Path) -> int:
    if not root.exists():
        return 0
    if not root.is_dir():
        raise ResourceBudgetError(f"resource budget directory is not a directory: {root}")
    total = 0
    for current, _directories, files in os.walk(root):
        for name in files:
            try:
                item = Path(current, name)
                if not item.is_symlink():
                    total += item.stat().st_size
            except OSError as error:
                raise ResourceBudgetError(f"cannot measure storage under {root}: {error}") from error
    return total


def _file_family_bytes(path: Path) -> int:
    total = 0
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm"),
                      Path(str(path) + "-journal")):
        try:
            total += candidate.stat().st_size
        except FileNotFoundError:
            pass
        except OSError as error:
            raise ResourceBudgetError(f"cannot measure Core State file {candidate}: {error}") from error
    return total


def _proc_rss(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def _fuseki_rss(match: str, cgroup_match: str | None = None) -> tuple[int, list[int]]:
    values: list[tuple[int, int]] = []
    proc = Path("/proc")
    try:
        entries = list(proc.iterdir())
    except OSError as error:
        raise ResourceBudgetError(f"cannot inspect Fuseki process memory: {error}") from error
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == os.getpid():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace")
        except OSError:
            continue
        if match.casefold() not in command.casefold():
            continue
        if cgroup_match:
            try:
                cgroup = (entry / "cgroup").read_text(encoding="utf-8")
            except OSError:
                continue
            if cgroup_match.casefold() not in cgroup.casefold():
                continue
        rss = _proc_rss(pid)
        if rss is not None:
            values.append((pid, rss))
    return sum(value for _pid, value in values), [pid for pid, _value in values]


def _memory_info() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:")):
                key, raw, *_ = line.split()
                values[key.rstrip(":")] = int(raw) * 1024
    except (OSError, ValueError, IndexError) as error:
        raise ResourceBudgetError(f"cannot measure host memory pressure: {error}") from error
    if not values.get("MemTotal") or not values.get("MemAvailable"):
        raise ResourceBudgetError("host memory total/available values are missing")
    # A cgroup limit is more restrictive than host MemAvailable and is included
    # separately so container-level pressure is not confused with host pressure.
    for path in (Path("/sys/fs/cgroup/memory.max"),
                 Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")):
        try:
            raw = path.read_text().strip()
            limit = int(raw) if raw != "max" else 0
            if limit > 0 and limit < 1 << 60:
                current_path = path.with_name("memory.current")
                current = int(current_path.read_text().strip()) if current_path.exists() else 0
                values["CgroupLimit"] = limit
                values["CgroupCurrent"] = current
                values["CgroupAvailable"] = max(0, limit - current)
                break
        except (OSError, ValueError):
            continue
    return values


def _etl_rss() -> tuple[int, int]:
    current = _proc_rss(os.getpid())
    if current is None:
        raise ResourceBudgetError("cannot measure ETL process RSS")
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux reports KiB; macOS reports bytes. This code's supported runtime is Linux.
    peak *= 1024
    return current, max(current, peak)


@dataclass
class ResourceBudget:
    """Configured filesystem and memory guard with append-only observations."""
    paths: dict[str, Path]
    limits: dict[str, int]
    fuseki_process_match: str
    fuseki_cgroup_match: str | None
    observation_path: Path

    @classmethod
    def from_file(cls, path: str | Path, *, raw_root: str | Path,
                  state_db: str | Path, observation_path: str | Path | None = None
                  ) -> "ResourceBudget":
        source = Path(path).expanduser().resolve()
        try:
            config = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ResourceBudgetError(f"cannot read resource budget config {source}") from error
        if not isinstance(config, dict) or config.get("schema") != "debates-resource-budget-v1":
            raise ResourceBudgetError("unsupported Debates resource budget schema")
        configured_paths = config.get("paths")
        if not isinstance(configured_paths, dict):
            raise ResourceBudgetError("resource budget paths must be an object")
        paths = {key: _required_path(configured_paths, key)
                 for key in ("tdb2", "temporary", "host")}
        actual_temporary = Path(tempfile.gettempdir()).resolve()
        if paths["temporary"] != actual_temporary:
            raise ResourceBudgetError(
                f"configured temporary directory {paths['temporary']} differs from "
                f"the process TMPDIR {actual_temporary}; set TMPDIR before launch")
        paths["raw"] = Path(raw_root).expanduser().resolve() / "debates"
        paths["state"] = Path(state_db).expanduser().resolve()
        raw_limits = config.get("limits", {})
        if not isinstance(raw_limits, dict):
            raise ResourceBudgetError("resource budget limits must be an object")
        unknown_limits = set(raw_limits) - set(DEFAULT_LIMITS)
        if unknown_limits:
            raise ResourceBudgetError(
                "unknown resource budget limit(s): " + ", ".join(sorted(unknown_limits)))
        limits = {**DEFAULT_LIMITS, **raw_limits}
        for key, value in limits.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ResourceBudgetError(f"resource budget limit {key!r} must be a nonnegative integer")
        if limits["tdb2_projection_factor"] < 1:
            raise ResourceBudgetError("TDB2 projection factor must be at least one")
        match = config.get("fuseki_process_match", "fuseki")
        if not isinstance(match, str) or not match.strip():
            raise ResourceBudgetError("Fuseki process selector is required")
        cgroup_match = config.get("fuseki_cgroup_match")
        if cgroup_match is not None and (not isinstance(cgroup_match, str)
                                         or not cgroup_match.strip()):
            raise ResourceBudgetError("Fuseki cgroup selector must be a nonempty string")
        report_value = observation_path or config.get("observation_file")
        report = (Path(report_value).expanduser() if report_value else
                  source.with_name("resource-observations.jsonl"))
        if report_value and not report.is_absolute():
            report = source.parent / report
        report = report.resolve()
        protected = [source, paths["raw"], paths["tdb2"], paths["state"]]
        if any(report == item or item in report.parents for item in protected):
            raise ResourceBudgetError("resource observations must be outside raw, TDB2 and Core State")
        return cls(paths, limits, match, cgroup_match, report)

    def observe(self, stage: str, *, expected_payload_bytes: int = 0,
                expected_triples: int = 0) -> dict:
        """Record metrics and raise before publication when any hard stop applies."""
        tdb2 = _directory_bytes(self.paths["tdb2"])
        debates_root = self.paths["raw"]
        raw_bytes = report_bytes = 0
        if debates_root.exists():
            for current, _dirs, files in os.walk(debates_root):
                for name in files:
                    path = Path(current, name)
                    if path.is_symlink():
                        continue
                    size = path.stat().st_size
                    if name.endswith(".reference-report.json"):
                        report_bytes += size
                    else:
                        raw_bytes += size
        state_bytes = _file_family_bytes(self.paths["state"])
        temporary_bytes = _directory_bytes(self.paths["temporary"])
        tdb_usage = shutil.disk_usage(self.paths["tdb2"] if self.paths["tdb2"].exists()
                                     else self.paths["tdb2"].parent)
        raw_usage = shutil.disk_usage(self.paths["raw"].parent if self.paths["raw"].parent.exists()
                                     else self.paths["raw"].parent.parent)
        state_usage = shutil.disk_usage(self.paths["state"].parent)
        temporary_usage = shutil.disk_usage(self.paths["temporary"])
        host_usage = shutil.disk_usage(self.paths["host"])
        etl_current, etl_peak = _etl_rss()
        fuseki_rss, fuseki_pids = _fuseki_rss(
            self.fuseki_process_match, self.fuseki_cgroup_match)
        if not fuseki_pids:
            raise ResourceBudgetError(
                f"no Fuseki process matched {self.fuseki_process_match!r}; refusing staging publication")
        if len(fuseki_pids) != 1:
            raise ResourceBudgetError(
                f"{len(fuseki_pids)} Fuseki processes matched; configure a unique "
                "fuseki_cgroup_match before staging publication")
        memory = _memory_info()
        available = min(memory["MemAvailable"], memory.get("CgroupAvailable", memory["MemAvailable"]))
        projected_growth = max(
            expected_payload_bytes * self.limits["tdb2_projection_factor"],
            expected_triples * 2000,
        )
        projected_tdb2 = tdb2 + projected_growth
        projected_state = state_bytes + expected_payload_bytes + 1024 * 1024
        tdb2_free_after_projected = max(0, tdb_usage.free - projected_growth)
        state_free_after_projected = max(
            0, state_usage.free - (expected_payload_bytes + 1024 * 1024))
        measurements = {
            "stage": stage,
            "timestamp_epoch": round(time.time(), 3),
            "etl_pid": os.getpid(),
            "tdb2_bytes": tdb2,
            "tdb2_projected_bytes": projected_tdb2,
            "raw_xml_and_metadata_bytes": raw_bytes,
            "reference_report_bytes": report_bytes,
            "core_state_bytes": state_bytes,
            "core_state_projected_bytes": projected_state,
            "temporary_bytes": temporary_bytes,
            "etl_rss_current_bytes": etl_current,
            "etl_rss_peak_bytes": etl_peak,
            "fuseki_rss_bytes": fuseki_rss,
            "fuseki_pids": fuseki_pids,
            "host_memory_total_bytes": memory["MemTotal"],
            "host_memory_available_bytes": memory["MemAvailable"],
            "cgroup_memory_limit_bytes": memory.get("CgroupLimit"),
            "cgroup_memory_current_bytes": memory.get("CgroupCurrent"),
            "effective_memory_available_bytes": available,
            "host_free_bytes": host_usage.free,
            "tdb2_volume_free_bytes": tdb_usage.free,
            "tdb2_volume_free_after_projected_bytes": tdb2_free_after_projected,
            "raw_volume_free_bytes": raw_usage.free,
            "core_state_volume_free_bytes": state_usage.free,
            "core_state_volume_free_after_projected_bytes": state_free_after_projected,
            "temporary_volume_free_bytes": temporary_usage.free,
            "expected_payload_bytes": expected_payload_bytes,
            "expected_triples": expected_triples,
            "warnings": [],
        }
        hard_limits = {
            "TDB2 projected bytes": (projected_tdb2, "tdb2_stop_bytes"),
            "raw XML/metadata bytes": (raw_bytes, "raw_stop_bytes"),
            "reference-report bytes": (report_bytes, "reference_reports_stop_bytes"),
            "Core State projected bytes": (projected_state, "core_state_stop_bytes"),
            "temporary bytes": (temporary_bytes, "temporary_stop_bytes"),
            "ETL process RSS peak": (etl_peak, "etl_rss_stop_bytes"),
            "Fuseki process RSS": (fuseki_rss, "fuseki_rss_stop_bytes"),
        }
        violations = [f"{label} {value} exceeds {key}={self.limits[key]}"
                      for label, (value, key) in hard_limits.items()
                      if value >= self.limits[key]]
        free_checks = (
            ("host free space after projected writes",
             max(0, host_usage.free - projected_growth - expected_payload_bytes),
             self.limits["host_free_stop_bytes"]),
            ("TDB2 volume free space after projected write", tdb2_free_after_projected,
             self.limits["minimum_tdb2_free_bytes"]),
            ("raw volume free space", raw_usage.free, self.limits["minimum_raw_free_bytes"]),
            ("Core State volume free space after projected write", state_free_after_projected,
             self.limits["minimum_state_free_bytes"]),
            ("temporary volume free space", temporary_usage.free,
             self.limits["minimum_temporary_free_bytes"]),
            ("host effective memory available", available,
             self.limits["host_memory_available_stop_bytes"]),
        )
        violations.extend(f"{label} {value} is below hard minimum {limit}"
                          for label, value, limit in free_checks if value <= limit)
        if violations:
            measurements["hard_stop"] = violations
        warning_checks = (
            ("TDB2 projected bytes", projected_tdb2, "tdb2_warn_bytes", "above"),
            ("raw XML/metadata bytes", raw_bytes, "raw_warn_bytes", "above"),
            ("reference-report bytes", report_bytes, "reference_reports_warn_bytes", "above"),
            ("Core State projected bytes", projected_state, "core_state_warn_bytes", "above"),
            ("temporary bytes", temporary_bytes, "temporary_warn_bytes", "above"),
            ("ETL RSS peak", etl_peak, "etl_rss_warn_bytes", "above"),
            ("Fuseki RSS", fuseki_rss, "fuseki_rss_warn_bytes", "above"),
            ("host free space", host_usage.free, "host_free_warn_bytes", "below"),
            ("effective memory available", available,
             "host_memory_available_warn_bytes", "below"),
        )
        for label, value, key, relation in warning_checks:
            if (relation == "above" and value >= self.limits[key]
                    or relation == "below" and value <= self.limits[key]):
                measurements["warnings"].append(
                    f"{label} {relation} warning threshold {self.limits[key]}")
        self.observation_path.parent.mkdir(parents=True, exist_ok=True)
        with self.observation_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(measurements, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if violations:
            raise ResourceBudgetError("Debates resource hard stop: " + "; ".join(violations))
        return measurements
