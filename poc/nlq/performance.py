"""Small per-request timing collector for the NLQ browser pipeline."""

from __future__ import annotations

from collections import defaultdict
from time import perf_counter


class QueryPerformance:
    def __init__(self):
        self.started = perf_counter()
        self.stages: dict[str, float] = defaultdict(float)
        self.stage_failures: set[str] = set()
        self.llm_calls = 0
        self.llm_seconds = 0.0
        self.fuseki_requests = 0
        self.fuseki_seconds = 0.0
        self._active_stage: tuple[str, float] | None = None

    def start_stage(self, stage: str):
        self.finish_stage()
        self._active_stage = (stage, perf_counter())

    def finish_stage(self):
        if self._active_stage is not None:
            name, started = self._active_stage
            self.stages[name] += perf_counter() - started
            self._active_stage = None

    def measure(self, stage: str, operation):
        start = perf_counter()
        try:
            return operation()
        except Exception:
            self.stage_failures.add(stage)
            raise
        finally:
            self.stages[stage] += perf_counter() - start

    def llm(self, operation):
        start = perf_counter()
        self.llm_calls += 1
        try:
            return operation()
        finally:
            self.llm_seconds += perf_counter() - start

    def fuseki(self, operation):
        start = perf_counter()
        self.fuseki_requests += 1
        try:
            return operation()
        finally:
            self.fuseki_seconds += perf_counter() - start

    def diagnostics(self, outcome: str) -> dict:
        self.finish_stage()
        elapsed = perf_counter() - self.started
        stages = {
            name: {"status": "failed" if name in self.stage_failures else "completed",
                   "elapsed_ms": round(seconds * 1000, 3)}
            for name, seconds in self.stages.items()
        }
        if "query_pipeline" not in stages:
            stages["query_pipeline"] = {"status": "not_executed", "elapsed_ms": None}
        return {
            # Collected immediately before TemplateResponse construction. This
            # deliberately does not claim to include HTML rendering or network I/O.
            "elapsed_before_render_ms": round(elapsed * 1000, 3),
            "stages": stages,
            "llm": {"count": self.llm_calls, "cumulative_elapsed_ms": round(self.llm_seconds * 1000, 3),
                    "status": "completed" if self.llm_calls else "not_executed"},
            "fuseki": {"count": self.fuseki_requests, "cumulative_elapsed_ms": round(self.fuseki_seconds * 1000, 3),
                       "status": "completed" if self.fuseki_requests else "not_executed"},
            "outcome": outcome,
        }
