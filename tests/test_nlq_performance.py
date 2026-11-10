from poc.nlq.performance import QueryPerformance
from fastapi.testclient import TestClient

from poc.nlq import app as app_module
from poc.nlq.fuseki import FusekiReadiness
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_request_metrics_accumulate_calls_and_distinguish_unexecuted_stages():
    metrics = QueryPerformance()
    assert metrics.measure("query_pipeline", lambda: "done") == "done"
    assert metrics.llm(lambda: "plan") == "plan"
    assert metrics.llm(lambda: "retry") == "retry"
    assert metrics.fuseki(lambda: "rows") == "rows"
    diagnostics = metrics.diagnostics("success")
    assert diagnostics["total_elapsed_ms"] >= diagnostics["stages"]["query_pipeline"]["elapsed_ms"]
    assert diagnostics["llm"]["count"] == 2
    assert diagnostics["llm"]["cumulative_elapsed_ms"] >= 0
    assert diagnostics["fuseki"]["count"] == 1
    assert diagnostics["stages"]["query_pipeline"]["status"] == "completed"
    assert diagnostics["stages"]["fuseki_requests"]["status"] == "completed"
    assert diagnostics["outcome"] == "success"


def test_early_exit_reports_pipeline_and_calls_as_not_executed():
    diagnostics = QueryPerformance().diagnostics("unsupported_request")
    assert diagnostics["total_elapsed_ms"] >= 0
    assert diagnostics["stages"]["query_pipeline"]["status"] == "not_executed"
    assert diagnostics["stages"]["llm_calls"]["status"] == "not_executed"
    assert diagnostics["llm"] == {"count": 0, "cumulative_elapsed_ms": 0.0}


def test_failed_stage_keeps_elapsed_time_and_is_not_reported_as_unexecuted():
    metrics = QueryPerformance()

    def fail():
        raise RuntimeError("failure")

    try:
        metrics.measure("query_pipeline", fail)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected operation failure")
    stage = metrics.diagnostics("failure")["stages"]["query_pipeline"]
    assert stage["status"] == "failed"
    assert stage["elapsed_ms"] >= 0


def test_unsupported_ask_renders_collapsed_performance_without_running_query(monkeypatch):
    class NoQueryFuseki:
        def __init__(self, *args, **kwargs):
            pass

        def readiness(self):
            return FusekiReadiness("ready", True, (), "Ready")

        def close(self):
            pass

        def query(self, _query):
            raise AssertionError("unsupported query must not execute")

    monkeypatch.setattr(app_module, "FusekiQueryClient", NoQueryFuseki)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post(
        "/ask", data={"question": "When was Jack Lynch first elected?", "mode": "phase2"}
    )
    assert response.status_code == 200
    assert 'data-outcome="unsupported_capability"' in response.text
    assert '<summary>Performance</summary>' in response.text
    assert "Total response time" in response.text
    assert "0 calls · 0.0 ms cumulative" in response.text
    assert "Not executed" in response.text
    detail = response.text.split('class="performance"', 1)[1].split(">", 1)[0]
    assert "open" not in detail
