"""Faithful presentation of Query Service answers, not factual certification.

The service owns admission, validation and execution. No query-family knowledge
or reconstruction from generated prose belongs in this consumer.
"""
from __future__ import annotations

import copy


def result_record(outcome, *, question, reporting_date, queries):
    """Retain the returned cells and scope, including false, zero and empty rows."""
    if outcome.interaction != "answer" or outcome.result is None:
        raise ValueError("Only a successful Query Service answer is reportable.")
    if not queries or any(q.get("outcome") != "returned" for q in queries):
        raise ValueError("The Query Service execution did not complete.")
    result = outcome.result
    if result.kind == "ask":
        if type(result.boolean) is not bool:
            raise ValueError("Malformed Boolean result.")
    elif result.kind == "select":
        if not result.columns or any(len(row) != len(result.columns) for row in result.rows):
            raise ValueError("Malformed tabular result.")
    else:
        raise ValueError("Unrecognised Query Service result form.")
    return {
        "question": question,
        "result": {"kind": result.kind, "columns": list(result.columns),
                   "rows": [list(row) for row in result.rows],
                   "boolean": result.boolean if result.kind == "ask" else None},
        "plan": copy.deepcopy(outcome.plan),
        "routeId": outcome.route_id,
        "compositionRequest": copy.deepcopy(outcome.composition_request),
        "reportingDate": reporting_date,
        "selectionOutcome": outcome.selection_outcome,
        "empty": result.kind == "select" and not result.rows,
        "qualifications": ([outcome.diagnostic] if outcome.diagnostic else []) + (
            [outcome.composition_request["answer"]["scope"]] if outcome.composition_request else []),
        "queryRefs": [q["queryId"] for q in queries],
    }


def present_result(record, evidence_id):
    """Use service column names verbatim; never let the author relabel cells."""
    result = record["result"]
    columns, rows = result["columns"], result["rows"]
    if result["kind"] == "ask":
        columns, rows = ["Boolean answer"], [["true" if result["boolean"] else "false"]]
    return {"caption": record["question"], "columns": columns,
            "rows": [{"cells": [{"text": cell} for cell in row], "evidenceRef": evidence_id} for row in rows],
            "evidenceRef": evidence_id,
            "empty": record["empty"],
            "qualification": " ".join(record["qualifications"]),
            "scope": "Returned at the Query Service's recorded query scope; not certified exhaustive coverage."}
