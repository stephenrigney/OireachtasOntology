"""Small verified research catalogue; no model-generated plans, IRIs or SPARQL."""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from .composable_plan import execute_question, plan_question, validate_plan
from .representation import representation_plan
from .research_adapter import ClosedModel, QueryTrace, COMPILER_CONTEXT, now

LIMITATIONS = [
    "These are findings from the available parliamentary records, not a certified complete account.",
    "The source's last update and completeness are not established. Retrieval time is not source freshness.",
    "Recorded Bill statuses and dated activities do not by themselves establish a final outcome.",
    "Representation in separate Dáil terms does not establish continuous service or other parliamentary roles.",
]
CATALOGUE = """Verified tools (all read-only; bounded local records, freshness unknown):
sponsorship(member): all recorded Bills with exact Member sponsorship, Primary/Supporting sponsorship flags (NOT subject classifications) and any separately recorded sponsor roles. No subject, opposition, Senator-period, before-date or enactment filter.
lifecycle(sourceTask): exact number/year lookups ONLY for Bills accepted from that sponsorship task. Recorded process status and dated activities, not certified final outcomes. At most 32 Bills per turn; retained identities must agree.
career(member): recorded constituency and Dáil-term identities across the named Member's recorded career. No service dates, continuous tenure, offices, committee roles, or ministerial-period intersection.
No debate-content, committee/party intersection or general role-discovery tool exists. Partial supporting research is allowed; missing conditions remain unanswered. Do not query irrelevant tools.
"""


class ToolTask(ClosedModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")
    question: str = Field(min_length=1, max_length=500)
    relevance: str = Field(min_length=1, max_length=500)
    role: Literal["direct", "supporting", "exploratory"]
    tool: Literal["sponsorship", "lifecycle", "career"]
    member: str | None
    sourceTask: str | None

    @field_validator("member")
    @classmethod
    def name(cls, value):
        if value is not None and (len(value) > 120 or not re.fullmatch(r"[\wÀ-ž][\wÀ-ž '’().-]*", value)):
            raise ValueError("A name mention is required, not an identifier or query.")
        return value


def draft_for(tool, member, as_of):
    question = f"Which Bills did {member} sponsor?" if tool == "sponsorship" else f"Which constituencies did {member} represent?"
    plan = (plan_question(question, as_of=as_of) if tool == "sponsorship"
            else representation_plan(as_of=as_of, member=member, current=False))
    refs = {key: {"type": r["type"], "mention": r.get("mention")} for key, r in plan["referents"].items()}
    if tool == "career":
        refs["term"]["selector"] = None
    answer = ({"kind": "entities", "referent": "bill", "distinctBy": "identity", "display": ["label"],
               "details": [], "preserveEvidence": True} if tool == "sponsorship" else copy.deepcopy(plan["answer"]))
    return question, {"version": 2, "supported": True,
        "family": "member_bill_sponsorship" if tool == "sponsorship" else "constituency_representation",
        "unsupportedReason": None, "intent": question, "referents": refs,
        "relations": copy.deepcopy(plan["relations"]), "constraints": [], "answer": answer}


class ResearchTools:
    def __init__(self, client, predicates, *, context_id, endpoint_id):
        self.client, self.predicates = client, predicates
        self.context = {"observationContextId": context_id, "endpointId": endpoint_id, "snapshotId": None}

    def execute(self, task, reporting_date, bill=None):
        """Canonical request is the tool's own exact question, never a rewritten rejected brief."""
        as_of = date.fromisoformat(reporting_date)
        if task["tool"] == "lifecycle":
            if bill is None or len(bill["numbers"]) != 1 or len(bill["years"]) != 1:
                raise ValueError("Exact accepted Bill number/year required.")
            number, year = bill["numbers"][0], bill["years"][0]
            question = f"Tell me about Bill {number} from {year}"
            draft = {"version": 2, "supported": True, "family": "capability_selection", "unsupportedReason": None,
                     "intent": question, "referents": {"capability": "bill_lookup", "parameters": {"billNumber": number, "billYear": int(year)}},
                     "relations": [], "constraints": [], "answer": None}
        else:
            question, draft = draft_for(task["tool"], task["member"], as_of)

        class Fixed:
            def generate(self, prompt):
                return json.dumps(draft)

        trace, start = QueryTrace(self.client), now()
        outcome = execute_question(question, as_of=as_of, fuseki=trace,
            supported_predicates=self.predicates, semantic_plan_generator_factory=Fixed)
        accepted = False
        try:
            accepted = (outcome.status == "success" and outcome.interaction == "answer"
                        and outcome.plan is not None and validate_plan(outcome.plan) == outcome.plan
                        and bool(outcome.accepted_evidence) and bool(trace.queries)
                        and all(q["outcome"] == "returned" for q in trace.queries))
            if bill is not None:
                accepted = accepted and {x["billIri"] for x in (outcome.accepted_evidence or {}).get("lifecycle", [])} == {bill["billIri"]}
        except (ValueError, KeyError, TypeError):
            accepted = False
        return {"evidenceId": "e-" + uuid4().hex, "request": {"factualRequest": question,
                    "requirementId": task["requirementId"], "operation": {"operation": task["tool"]}},
                "outcome": "answer" if accepted else (outcome.interaction if outcome.interaction != "answer" else "validation_failure"),
                "compilerStatus": outcome.status, "validation": {"accepted": accepted},
                "data": copy.deepcopy(outcome.accepted_evidence) if accepted else None, "plan": outcome.plan,
                "execution": {**COMPILER_CONTEXT, "datasetContext": self.context, "startedAt": start,
                              "finishedAt": now(), "queries": trace.queries},
                "resolvedScope": {"reportingDate": reporting_date, "temporalMeaning": "recorded_history_not_continuous_or_current_status"},
                "completeness": {"enumeration": "bounded_query_completed" if accepted else "unknown",
                                 "sourceCoverage": "uncertified", "freshness": "unknown", "limitations": LIMITATIONS},
                "error": None if accepted else {"message": "The requested records could not be safely established. This is not evidence that no such records exist.",
                                                "code": outcome.status}, "diagnostic": outcome.diagnostic}
