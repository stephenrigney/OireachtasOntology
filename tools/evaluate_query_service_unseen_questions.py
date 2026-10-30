"""Replay the frozen unseen questions through the integrated Phase 2 /ask route.

This is a task-specific observation runner, not a benchmark/scoring framework.
It records the current route outcome and any question-answer query execution;
it never creates a dataset or calls the legacy Phase 1 translator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
QUESTION_SET = ROOT / "poc/specs/query-service-unseen-questions-approved.md"
QUESTION_SET_SHA256 = "a580ed9416b0aea6bf221623a7cdcf09e6bd00a3299db8a0d6be905d8c0f2e4e"
AS_OF = date(2026, 10, 28)
DEFAULT_OUTPUT = Path("/tmp/opencode/query-service-unseen-evaluation/phase2-observations.jsonl")


def _questions() -> list[dict[str, str]]:
    payload = QUESTION_SET.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != QUESTION_SET_SHA256:
        raise SystemExit(
            f"Frozen question-set SHA-256 mismatch: expected {QUESTION_SET_SHA256}, got {digest}."
        )
    text = payload.decode("utf-8")
    questions = []
    for line in text.splitlines():
        match = re.fullmatch(r"### (U\d{2}) — (.+)", line)
        if match:
            questions.append({"id": match.group(1), "question": match.group(2)})
    expected = [f"U{number:02d}" for number in range(1, 37)]
    if [question["id"] for question in questions] != expected:
        raise SystemExit("Frozen catalogue must contain exactly U01–U36 in order.")
    return questions


def _configure_local_fuseki() -> None:
    """Mirror only launcher Fuseki settings; deliberately do not load the LLM key."""
    local = dotenv_values(ROOT / ".env.local", encoding="utf-8")
    for name in ("NLQ_FUSEKI_QUERY_URL", "OIR_FUSEKI_USER", "OIR_FUSEKI_PASSWORD"):
        value = local.get(name)
        if value is not None:
            os.environ.setdefault(name, value)
    os.environ["OIR_NLQ_AS_OF_DATE"] = AS_OF.isoformat()
    for name in ("NLQ_LLM_API_KEY", "NLQ_LLM_BASE_URL", "NLQ_LLM_MODEL"):
        os.environ.pop(name, None)


def _query_result(result) -> dict[str, Any]:
    return {
        "kind": result.kind,
        "columns": list(result.columns),
        "rows": [list(row) for row in result.rows],
        "boolean": result.boolean,
    }


def run(output: Path) -> int:
    _configure_local_fuseki()
    sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient
    from poc.nlq import app as app_module
    from poc.nlq.fuseki import FusekiQueryClient

    query_events: list[dict[str, Any]] = []
    route_observations: list[dict[str, Any]] = []
    original_query = FusekiQueryClient.query
    original_execute = app_module.execute_question

    def observe_query(self, sparql: str):
        try:
            result = original_query(self, sparql)
        except Exception as error:
            query_events.append({
                "query": sparql,
                "error": f"{type(error).__name__}: {error}",
            })
            raise
        query_events.append({"query": sparql, **_query_result(result)})
        return result

    def observe_execute(question: str, **kwargs):
        first_event = len(query_events)
        outcome = None
        error = None
        try:
            outcome = original_execute(question, **kwargs)
            return outcome
        except Exception as caught:
            error = f"{type(caught).__name__}: {caught}"
            raise
        finally:
            route_observations.append({
                "query_events": query_events[first_event:],
                "outcome": None if outcome is None else {
                    "status": outcome.status,
                    "request_family": outcome.request_family,
                    "plan": outcome.plan,
                    "diagnostic": outcome.diagnostic,
                    "candidates": list(outcome.candidates),
                    "sparql": outcome.sparql,
                    "result": None if outcome.result is None else _query_result(outcome.result),
                },
                "exception": error,
            })

    FusekiQueryClient.query = observe_query
    app_module.execute_question = observe_execute

    questions = _questions()
    output.parent.mkdir(parents=True, exist_ok=True)
    with TestClient(app_module.create_app(repository_root=ROOT)) as client, output.open(
        "w", encoding="utf-8"
    ) as stream:
        for question in questions:
            query_events.clear()
            before = len(route_observations)
            response = client.post(
                "/ask",
                data={"question": question["question"], "mode": "phase2"},
            )
            observation = route_observations[-1] if len(route_observations) == before + 1 else None
            record = {
                **question,
                "mode": "phase2",
                "asOf": AS_OF.isoformat(),
                "http_status": response.status_code,
                "observation": observation,
                "response_sha256": hashlib.sha256(response.content).hexdigest(),
                "page_markers": {
                    "validated_plan": "Validated composable query plan" in response.text,
                    "proposed_plan": "Proposed composable query plan" in response.text,
                    "error": 'role="alert"' in response.text,
                },
            }
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()

    statuses = {}
    for row in map(json.loads, output.read_text(encoding="utf-8").splitlines()):
        outcome = (row.get("observation") or {}).get("outcome") or {}
        status = outcome.get("status", "no_outcome")
        statuses[status] = statuses.get(status, 0) + 1
    print(json.dumps({
        "question_set_sha256": QUESTION_SET_SHA256,
        "asOf": AS_OF.isoformat(),
        "questions": len(questions),
        "outcomes": statuses,
        "observations": str(output),
    }, sort_keys=True))
    return 0 if len(questions) == 36 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    return run(args.output)


if __name__ == "__main__":
    raise SystemExit(main())
