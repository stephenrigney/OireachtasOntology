import json

import pytest

from oireachtas_etl import resource_budget
from oireachtas_etl.resource_budget import ResourceBudget, ResourceBudgetError


def _budget_file(tmp_path, monkeypatch, limits=None):
    for name in ("tdb", "raw", "temporary", "host", "state"):
        (tmp_path / name).mkdir(exist_ok=True)
    path = tmp_path / "budget.json"
    path.write_text(json.dumps({
        "schema": "debates-resource-budget-v1",
        "paths": {"tdb2": str(tmp_path / "tdb"),
                  "temporary": str(tmp_path / "temporary"),
                  "host": str(tmp_path / "host")},
        "fuseki_process_match": "fuseki-test-process",
        "observation_file": str(tmp_path / "metrics.jsonl"),
        "limits": limits or {},
    }), encoding="utf-8")
    monkeypatch.setattr(resource_budget.tempfile, "tempdir", str(tmp_path / "temporary"))
    return path, tmp_path / "raw", tmp_path / "state" / "core.sqlite"


def _stable_measurements(monkeypatch):
    monkeypatch.setattr(resource_budget, "_etl_rss", lambda: (100, 200))
    monkeypatch.setattr(resource_budget, "_fuseki_rss", lambda _match, _cgroup=None: (300, [456]))
    monkeypatch.setattr(resource_budget, "_memory_info", lambda: {
        "MemTotal": 16 * resource_budget.GIB,
        "MemAvailable": 8 * resource_budget.GIB,
    })


def test_resource_guard_records_distinct_etl_fuseki_and_host_metrics(tmp_path, monkeypatch):
    _stable_measurements(monkeypatch)
    config, raw_root, state_path = _budget_file(tmp_path, monkeypatch, {
        "host_free_warn_bytes": 0,
        "host_free_stop_bytes": 0,
        "minimum_tdb2_free_bytes": 0,
        "minimum_raw_free_bytes": 0,
        "minimum_state_free_bytes": 0,
        "minimum_temporary_free_bytes": 0,
        "host_memory_available_warn_bytes": 0,
        "host_memory_available_stop_bytes": 0,
    })
    budget = ResourceBudget.from_file(config, raw_root=raw_root, state_db=state_path)
    seen = budget.observe("test", expected_payload_bytes=10, expected_triples=1)
    assert seen["etl_rss_current_bytes"] == 100
    assert seen["etl_rss_peak_bytes"] == 200
    assert seen["fuseki_rss_bytes"] == 300
    assert seen["host_memory_available_bytes"] == 8 * resource_budget.GIB
    row = json.loads(budget.observation_path.read_text().splitlines()[0])
    assert row == seen


def test_resource_guard_hard_stop_is_durable_and_fails_closed(tmp_path, monkeypatch):
    _stable_measurements(monkeypatch)
    config, raw_root, state_path = _budget_file(tmp_path, monkeypatch, {
        "core_state_stop_bytes": 1,
        "host_free_warn_bytes": 0,
        "host_free_stop_bytes": 0,
        "minimum_tdb2_free_bytes": 0,
        "minimum_raw_free_bytes": 0,
        "minimum_state_free_bytes": 0,
        "minimum_temporary_free_bytes": 0,
        "host_memory_available_warn_bytes": 0,
        "host_memory_available_stop_bytes": 0,
    })
    budget = ResourceBudget.from_file(config, raw_root=raw_root, state_db=state_path)
    with pytest.raises(ResourceBudgetError, match="Core State projected bytes"):
        budget.observe("before_graph_put", expected_payload_bytes=4)
    measurement = json.loads(budget.observation_path.read_text().splitlines()[0])
    assert measurement["hard_stop"]


def test_resource_guard_refuses_to_publish_without_observable_fuseki(tmp_path, monkeypatch):
    monkeypatch.setattr(resource_budget, "_etl_rss", lambda: (100, 100))
    monkeypatch.setattr(resource_budget, "_fuseki_rss", lambda _match, _cgroup=None: (0, []))
    config, raw_root, state_path = _budget_file(tmp_path, monkeypatch)
    budget = ResourceBudget.from_file(config, raw_root=raw_root, state_db=state_path)
    with pytest.raises(ResourceBudgetError, match="no Fuseki process matched"):
        budget.observe("preflight")


def test_resource_guard_refuses_ambiguous_fuseki_process_measurement(tmp_path, monkeypatch):
    monkeypatch.setattr(resource_budget, "_etl_rss", lambda: (100, 100))
    monkeypatch.setattr(resource_budget, "_fuseki_rss", lambda _match, _cgroup=None: (300, [456, 789]))
    config, raw_root, state_path = _budget_file(tmp_path, monkeypatch)
    budget = ResourceBudget.from_file(config, raw_root=raw_root, state_db=state_path)
    with pytest.raises(ResourceBudgetError, match="configure a unique fuseki_cgroup_match"):
        budget.observe("preflight")


def test_resource_guard_rejects_unknown_limits_and_protected_observation_paths(
        tmp_path, monkeypatch):
    config, raw_root, state_path = _budget_file(tmp_path, monkeypatch, {
        "typo_stop_bytes": 10,
    })
    with pytest.raises(ResourceBudgetError, match="unknown resource budget limit"):
        ResourceBudget.from_file(config, raw_root=raw_root, state_db=state_path)

    config, raw_root, state_path = _budget_file(tmp_path, monkeypatch)
    with pytest.raises(ResourceBudgetError, match="observations must be outside"):
        ResourceBudget.from_file(config, raw_root=raw_root, state_db=state_path,
                                 observation_path=config)
