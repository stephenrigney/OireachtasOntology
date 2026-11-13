"""Consume the Query Service contract without interpreting query families."""
from __future__ import annotations

import copy
import re

from .query_evidence import AcceptedEvidence, result_digest


def accept_query_evidence(outcome, queries):
    if not outcome.factual_evidence:
        return None, ("The Query Service's evidence shape is not supported by its structured factual boundary. "
                      "The response is retained for inspection; no research fact was promoted.")
    try:
        evidence = AcceptedEvidence.model_validate(outcome.factual_evidence)
        if (outcome.status != "success" or evidence.plan != outcome.plan
                or evidence.answerQuery != outcome.sparql or outcome.result is None
                or evidence.resultDigest != result_digest(outcome.result)):
            raise ValueError("Evidence did not agree with its compiler result.")
        if not queries or any(q.get("outcome") != "returned" for q in queries):
            raise ValueError("Evidence requires completed execution.")
        # The exact source query must have actually executed (pagination may add
        # LIMIT/OFFSET). Retain every resolution/page read, not invented refs.
        if not any(re.fullmatch(re.escape(evidence.answerQuery.strip()) + r"(?:\s+OFFSET \d+)?",
                                q["sparql"].strip()) for q in queries):
            raise ValueError("Evidence query was not executed.")
        data = copy.deepcopy(outcome.accepted_evidence or {})  # legacy batch/replay convenience only
        data["evidence"] = evidence.model_dump()
        data["queryRefs"] = [q["queryId"] for q in queries]
        return data, None
    except (ValueError, KeyError, TypeError, IndexError):
        return None, "The accepted evidence did not agree with its compiler scope or result; no research facts were promoted."
