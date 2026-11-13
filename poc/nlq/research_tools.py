"""Guarded subsidiary questions through the existing Query Service.

Legacy typed requests remain compatible with retained sessions/replay controls;
they are not the admission boundary for new research.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from .composable_plan import PlanOutcome, execute_question, plan_question, validate_plan
from .representation import representation_plan
from .research_adapter import ClosedModel, QueryTrace, COMPILER_CONTEXT, now
from .composable_semantic_planner import create_composable_plan_generator, build_composable_planner_instructions
from .research_outcomes import classify, describe
from .results import format_debug_text

LIMITATIONS = [
    "These are findings from the available parliamentary records, not a certified complete account.",
    "The records' last update is unknown. Separate searches may reflect different updates to the data.",
    "Recorded Bill statuses and dated activities do not by themselves establish a final outcome.",
    "Representation in separate Dáil terms does not establish continuous service or other parliamentary roles.",
]
CATALOGUE = """Research interface (read-only local Query Service; freshness unknown):
query(question): propose a concrete subsidiary question in ordinary language. It is passed UNCHANGED to the existing Query Service, which independently selects capabilities, resolves identities, validates and executes. member=null, sourceTask=null. Discovery guidance is supplied from the Query Service itself, not a Research Assistant capability catalogue. Advertisements are not guarantees of executable or promotable evidence.
lifecycle(sourceTask): retained batch convenience ONLY for recorded status/activities of exact Bills from an accepted sponsorship enumeration. member=null. At most 32 Bills; every lookup independently passes the Query Service. This is not final-outcome certification.
Use query for all other research, including sponsorship and constituency history. Do not supply plans, IRIs, SPARQL or guessed identities. Missing dates remain missing; separate episodes never imply continuous membership.
After a limitation you may propose a different RELEVANT investigation, with its narrower scope explicit. Never silently remove material conditions or query irrelevant substitutes. Successful Query Service answers are available directly as queryResults, including tables, dates, counts and Boolean answers. Optional factual evidence is not required for reporting them faithfully.
"""


def discovery_context():
    """Single source of discovery guidance, identical to the service planner's."""
    from .composable_semantic_planner import _plan_contract
    return {"questionFamilies": _plan_contract()["questionFamilies"],
            "semanticPlannerGuidance": build_composable_planner_instructions()}


class ToolTask(ClosedModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")
    question: str = Field(min_length=1, max_length=500)
    relevance: str = Field(min_length=1, max_length=500)
    role: Literal["direct", "supporting", "exploratory"]
    tool: Literal["query", "sponsorship", "lifecycle", "career"]
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
    def __init__(self, client, predicates, *, context_id, endpoint_id,
                 semantic_plan_generator_factory=create_composable_plan_generator):
        self.client, self.predicates = client, predicates
        self.context = {"observationContextId": context_id, "endpointId": endpoint_id, "snapshotId": None}
        self.planner_factory = semantic_plan_generator_factory

    def execute(self, task, reporting_date, bill=None):
        env = self._execute(task, reporting_date, bill)
        if "researchOutcome" not in env:
            env["researchOutcome"] = classify(PlanOutcome(env["compilerStatus"]),
                accepted=env["outcome"] == "answer", plan_validated=False, execution_completed=False)
            if env.get("error"):
                env["error"]["technicalMessage"] = env["error"]["message"]
                env["error"]["message"] = env["researchOutcome"]["description"]
        return env

    def _execute(self, task, reporting_date, bill=None):
        """Canonical request is the tool's own exact question, never a rewritten rejected brief."""
        as_of = date.fromisoformat(reporting_date)
        if task["tool"] == "query":
            return self._query(task, reporting_date)
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
                        and bool(trace.queries)
                        and all(q["outcome"] == "returned" for q in trace.queries))
            if bill is not None:
                accepted = accepted and {x["billIri"] for x in (outcome.accepted_evidence or {}).get("lifecycle", [])} == {bill["billIri"]}
        except (ValueError, KeyError, TypeError):
            accepted = False
        data, result_problem = None, None
        if accepted:
            from .research_evidence import accept_query_evidence
            from .research_results import result_record
            data, _ = accept_query_evidence(outcome, trace.queries)
            data = data or {}
            try:
                data["queryResult"] = result_record(outcome, question=question, reporting_date=reporting_date, queries=trace.queries)
            except (ValueError, KeyError, TypeError) as error:
                accepted, data, result_problem = False, None, str(error)
        status = "answer" if accepted else (outcome.interaction if outcome.interaction != "answer" else "validation_failure")
        research_outcome = classify(PlanOutcome(status) if result_problem else outcome,
            accepted=accepted, plan_validated=accepted, execution_completed=bool(trace.queries) and all(q["outcome"] == "returned" for q in trace.queries))
        return {"evidenceId": "e-" + uuid4().hex, "request": {"factualRequest": question,
                    "subsidiaryQuestion": task.get("question", question),
                    "requirementId": task["requirementId"], "operation": {"operation": task["tool"]}},
                "outcome": status, "researchOutcome": research_outcome,
                "compilerStatus": outcome.status, "validation": {"accepted": accepted},
                "data": data, "plan": outcome.plan, "routeId": outcome.route_id, "sparql": outcome.sparql,
                "queryServiceResult": data["queryResult"]["result"] if accepted else None,
                "execution": {**COMPILER_CONTEXT, "datasetContext": self.context, "startedAt": start,
                              "finishedAt": now(), "queries": trace.queries},
                "resolvedScope": {"reportingDate": reporting_date, "temporalMeaning": "recorded_history_not_continuous_or_current_status"},
                "completeness": {"enumeration": "bounded_query_completed" if accepted else "unknown",
                                 "sourceCoverage": "uncertified", "freshness": "unknown", "limitations": LIMITATIONS},
                "error": None if accepted else {"message": research_outcome["description"], "technicalMessage": result_problem or outcome.diagnostic,
                                                "code": outcome.status}, "diagnostic": outcome.diagnostic}

    def _query(self, task, reporting_date):
        """No rewriting, fixed drafts, direct compiler calls or Phase-1 fallback."""
        trace, start, proposals = QueryTrace(self.client), now(), []

        def planner():
            generator = self.planner_factory()

            class TracedPlanner:
                def generate(self, prompt):
                    record = {"prompt": prompt, "output": None}
                    proposals.append(record)
                    output = generator.generate(prompt)
                    record["output"] = output
                    return output

                def close(self):
                    close = getattr(generator, "close", None)
                    if close:
                        close()

            return TracedPlanner()

        try:
            outcome = execute_question(task["question"], as_of=date.fromisoformat(reporting_date),
                fuseki=trace, supported_predicates=self.predicates, semantic_plan_generator_factory=planner)
        except Exception as error:
            # Retain even already-completed reads on unexpected planner/projection
            # failure. Never convert a failed projection to success-shaped data.
            import os
            failure = "execution_failure" if any(q["outcome"] == "execution_failure" for q in trace.queries) else "validation_failure"
            outcome = PlanOutcome(failure, diagnostic=format_debug_text(
                f"{type(error).__name__}: {error}", secrets=tuple(os.getenv(k, "") for k in ("NLQ_LLM_API_KEY", "OIR_FUSEKI_PASSWORD"))))
        plan_ok = False
        try:
            plan_ok = outcome.plan is not None and validate_plan(outcome.plan) == outcome.plan
        except (ValueError, KeyError, TypeError):
            pass
        # Current composition deliberately has no composable-v2 plan. Its own
        # admitted request and kernel report are the service's validation/result
        # artifacts, not a reason to reject an otherwise successful answer.
        composition_ok = (outcome.composition_request is not None
                          and (outcome.composition_report or {}).get("status") == "answer")
        service_validated = plan_ok or composition_ok
        executed = bool(trace.queries) and all(q["outcome"] == "returned" for q in trace.queries)
        data, limitation, record = None, None, None
        if outcome.interaction == "answer" and service_validated and executed:
            from .research_results import result_record
            try:
                record = result_record(outcome, question=task["question"], reporting_date=reporting_date,
                                       queries=trace.queries)
            except (ValueError, KeyError, TypeError) as error:
                limitation = str(error)
            # Preserve useful optional evidence and legacy batch data. A missing
            # or inapplicable projector must not veto a successful service answer.
            from .research_evidence import accept_query_evidence
            data, evidence_limitation = accept_query_evidence(outcome, trace.queries)
            data = data or {}
            if record is not None:
                data["queryResult"] = record
        else:
            evidence_limitation = None
        accepted = record is not None
        status = outcome.interaction
        if status == "answer" and not accepted:
            status = "validation_failure"
        message = None if accepted else (limitation or outcome.diagnostic or "No accepted research evidence was established.")
        research_outcome = classify(outcome, accepted=accepted, plan_validated=service_validated, execution_completed=executed)
        # A thrown semantic-planner call leaves a traced proposal with no output;
        # distinguish that from a returned plan rejected by normal validation.
        if (not accepted and outcome.interaction == "validation_failure" and proposals
                and proposals[-1].get("output") is None):
            research_outcome = describe("planner_failure")
        return {"evidenceId": "e-" + uuid4().hex,
            "request": {"factualRequest": task["question"], "requirementId": task["requirementId"],
                        "operation": {"operation": "query"}},
            "outcome": status, "queryServiceOutcome": outcome.interaction,
            "compilerStatus": outcome.status,
            "researchOutcome": research_outcome, "factualEvidenceStatus": outcome.factual_evidence_status,
            "selectionOutcome": outcome.selection_outcome,
            "validation": {"planValidated": plan_ok, "compositionValidated": composition_ok,
                           "serviceValidated": service_validated, "executionCompleted": executed, "accepted": accepted},
            "data": data if accepted else None, "plan": copy.deepcopy(outcome.plan),
            "routeId": outcome.route_id, "sparql": outcome.sparql,
            "compositionRequest": copy.deepcopy(outcome.composition_request),
            "compositionReport": copy.deepcopy(outcome.composition_report),
            "optionalEvidenceIssue": evidence_limitation,
            "queryServiceResult": ({"kind": outcome.result.kind, "columns": list(outcome.result.columns),
                                    "rows": [list(r) for r in outcome.result.rows],
                                    "boolean": outcome.result.boolean if outcome.result.kind == "ask" else None}
                                   if outcome.result is not None else None),
            "execution": {**COMPILER_CONTEXT, "datasetContext": self.context, "startedAt": start,
                          "finishedAt": now(), "queries": trace.queries, "plannerProposals": proposals},
            "resolvedScope": {"reportingDate": reporting_date, "temporalMeaning": "compiler_plan_scope_only",
                              "intent": (outcome.plan or {}).get("intent"), "parentRequirementSatisfied": False},
            "completeness": {"enumeration": "bounded_query_completed" if accepted else "unknown",
                             "sourceCoverage": "uncertified", "freshness": "unknown",
                              "limitations": LIMITATIONS[:2] + ([research_outcome["description"]] if message else [])},
            "error": None if accepted else {"code": "research_evidence_unavailable" if limitation else outcome.status,
                "message": research_outcome["description"], "technicalMessage": message,
                "candidates": list(outcome.candidates), "clarification": outcome.clarification},
            "diagnostic": outcome.diagnostic, "debugOutput": outcome.debug_output, "debugSource": outcome.debug_source}
