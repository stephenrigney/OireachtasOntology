"""Closed Phase 1 facade. Admission and factual authority remain in the compiler."""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .composable_plan import PlanOutcome, execute_question, validate_plan
from .errors import NLQError

ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)
TERM = "dail.current_term"
MEMBERS = "dail.party_members.current"
COUNT = "dail.party_member_count.current"
LIMITATIONS = [
    "Qualified local-record findings, not a certified complete parliamentary roster.",
    "Source coverage is uncertified; source freshness and loaded capture identity are unknown.",
    "Separate queries are not a transaction or an established common dataset snapshot.",
    "Counts measure distinct accepted Member IRIs, not seats or election totals.",
]


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TermOperation(ClosedModel):
    operation: Literal["dail.current_term"]


class PartyOperation(ClosedModel):
    operation: Literal["dail.party_members.current", "dail.party_member_count.current"]
    partyMention: str = Field(min_length=1, max_length=120)

    @field_validator("partyMention")
    @classmethod
    def mention(cls, value):
        if value != value.strip() or not re.fullmatch(r"[\wÀ-ž][\wÀ-ž '&’().-]*", value) or "http" in value.lower():
            raise ValueError("Use a party name mention, not an identity, query or condition.")
        return value


class OperationRequest(ClosedModel):
    apiVersion: Literal[1] = 1
    requestId: str = Field(min_length=1, max_length=100)
    requirementId: str = Field(min_length=1, max_length=100)
    factualRequest: str = Field(min_length=1, max_length=2000)
    reportingDate: str
    operation: TermOperation | PartyOperation = Field(discriminator="operation")

    @field_validator("reportingDate")
    @classmethod
    def iso_date(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Use a canonical ISO calendar date.")
        return value


class TermEvidence(ClosedModel):
    iri: str
    label: str
    start: str
    end: str | None


class IntervalEvidence(ClosedModel):
    resourceIri: str
    rangeIri: str
    start: str
    end: str | None
    sourceStart: str
    sourceEnd: str
    ownerGraph: str | None


class OverlapEvidence(ClosedModel):
    start: str
    end: str | None


class AcceptedWitness(ClosedModel):
    termIri: str
    partyIri: str
    affiliationIri: str
    membership: IntervalEvidence
    episode: IntervalEvidence
    overlap: OverlapEvidence
    queryRefs: list[str] = Field(min_length=1)


class AcceptedMember(ClosedModel):
    memberIri: str
    displayName: str = Field(min_length=1)
    witnesses: list[AcceptedWitness] = Field(min_length=1)


class TermData(ClosedModel):
    term: TermEvidence


class MemberData(ClosedModel):
    members: list[AcceptedMember] = Field(min_length=1)
    value: int = Field(ge=1)
    unit: Literal["distinct_recorded_member_iris"]


class OperationEnvelope(ClosedModel):
    apiVersion: Literal[1] = 1
    evidenceId: str
    request: OperationRequest
    outcome: Literal["answer", "clarification_required", "unresolved_identity", "unsupported_capability",
                     "missing_or_unaccepted_evidence", "validation_failure", "execution_failure"]
    compilerStatus: str
    validation: dict
    execution: dict
    resolvedScope: dict
    completeness: dict
    data: dict | None
    error: dict | None
    plan: dict | None

    @model_validator(mode="after")
    def accepted_shape(self):
        # The schema documents the closed payloads; retain plain dictionaries
        # for the report assembler rather than leaking Pydantic into evidence.
        if self.outcome == "answer":
            shape = TermData if self.request.operation.operation == TERM else MemberData
            shape.model_validate(self.data)
            if self.error is not None or not self.validation.get("accepted"):
                raise ValueError("An answer requires accepted evidence, not an error.")
        elif self.data is not None or self.error is None:
            raise ValueError("A non-answer retains an error, never success-shaped empty data.")
        return self

    @classmethod
    def model_json_schema(cls, **kwargs):
        schema = super().model_json_schema(**kwargs)
        shapes = [TermData.model_json_schema(), MemberData.model_json_schema()]
        for shape in shapes:
            schema.setdefault("$defs", {}).update(shape.pop("$defs", {}))
        schema["properties"]["data"] = {"anyOf": [*shapes, {"type": "null"}]}
        return schema


def current_party_draft(party: str, *, count=False):
    """Lower closed parameters to the existing reviewed seven-edge draft."""
    edges = [
        ("member_has_membership", "member", "membership"),
        ("membership_in_term", "membership", "term"),
        ("member_party_membership", "member", "episode"),
        ("party_episode_in_membership", "episode", "membership"),
        ("episode_in_parliamentary_party", "episode", "party"),
        ("party_active_during_term", "party", "term"),
        ("parliamentary_party_has_affiliation_identity", "party", "affiliation"),
    ]
    refs = {key: {"type": kind, "mention": None} for key, kind in [
        ("member", "Member"), ("membership", "DailMembership"), ("term", "DailTerm"),
        ("episode", "PartyMembershipEpisode"), ("party", "ParliamentaryParty"),
        ("affiliation", "PoliticalAffiliationIdentity"),
    ]}
    refs["term"]["selector"] = {"kind": "currentTerm"}
    refs["affiliation"]["mention"] = party
    return {
        "version": 2, "supported": True, "family": "member_relationship_composition",
        "unsupportedReason": None, "intent": "Current Dáil named-party Member selection",
        "referents": refs,
        "relations": [{"id": f"edge-{i}", "fact": fact, "from": left, "to": right}
                      for i, (fact, left, right) in enumerate(edges)],
        "constraints": [{"referent": "episode", "field": "partyEpisodeInterval", "operator": "overlaps", "value": "membership"}],
        "answer": ({"kind": "count", "referent": "member", "distinctBy": "identity"} if count else {
            "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
            "details": [{"referent": "affiliation", "display": ["label"]},
                        {"referent": "episode", "display": ["start", "end"]},
                        {"referent": "membership", "display": ["start", "end"]}], "preserveEvidence": True,
        }),
    }


def dispatch_current_dail(question, operation, *, as_of, fuseki, supported_predicates):
    """Compiler-owned dispatch seam, called only after its shared preflight.

    No NL router and no query-generating model. The unchanged atomic question
    still goes through the existing English intent/mention admission checks.
    """
    if isinstance(operation, TermOperation):
        from .stage_a import StageARequest, execute_stage_a
        # This catalogue promises exactly the reporting-day term. It must not
        # silently reinterpret another date, month, sitting or extra condition.
        allowed = {
            "What is the current Dáil term?", "Which Dáil is currently in office?",
            f"Which Dáil was in office on {as_of.isoformat()}?",
        }
        if question not in allowed:
            return PlanOutcome("unsupported_request", diagnostic="The current-term operation requires an unqualified reporting-day term request.")
        return execute_stage_a(StageARequest("house_terms", temporal_scope={"kind": "onDate", "date": as_of.isoformat()}),
                               as_of=as_of, fuseki=fuseki, supported_predicates=supported_predicates)
    from .composable_plan import _execute_shared_dail_terms_question
    draft = current_party_draft(operation.partyMention, count=operation.operation == COUNT)

    class FixedDraft:
        def generate(self, prompt):
            return json.dumps(draft)

    return _execute_shared_dail_terms_question(question, as_of=as_of, fuseki=fuseki,
        supported_predicates=supported_predicates, planner_generator_factory=FixedDraft)


def now():
    return datetime.now(timezone.utc).isoformat()


class QueryTrace:
    """Uncapped actual reads, including resolution, every page and failures."""
    def __init__(self, client):
        self.client, self.queries = client, []
        self.route_id = None

    def select_route(self, route_id):
        self.route_id = route_id

    def select(self, lookup, query, offset):
        """Trace the service's lossless composition transport, without rewriting.

        The kernel still owns pagination, safety, timeouts and whole-plan budgets.
        """
        from .composition_transport import typed_json
        item = {"queryId": f"q-{uuid4().hex}", "sha256": hashlib.sha256(query.encode()).hexdigest(),
                "sparql": query, "stage": "typed_composition_select", "lookupKind": lookup.kind,
                "offset": offset, "startedAt": now(), "outcome": "execution_failure", "result": None}
        self.queries.append(item)
        try:
            result = self.client.select(lookup, query, offset)
            item.update(outcome="returned", result=typed_json(result))
            return result
        except Exception as error:
            import os
            from .results import format_debug_text
            item["technicalDiagnostic"] = format_debug_text(f"{type(error).__name__}: {error}",
                secrets=tuple(os.getenv(k, "") for k in ("NLQ_LLM_API_KEY", "OIR_FUSEKI_PASSWORD")))
            raise NLQError("The configured read-only composition query failed.") from error
        finally:
            item["finishedAt"] = now()

    def query(self, sparql):
        item = {"queryId": f"q-{uuid4().hex}", "sha256": hashlib.sha256(sparql.encode()).hexdigest(),
                "sparql": sparql, "stage": "read_only_query", "startedAt": now(),
                "offset": int(m.group(1)) if (m := re.search(r"\bOFFSET (\d+)\s*$", sparql)) else 0,
                "graphScope": {"fixedGraphs": re.findall(r"GRAPH\s+<([^>]+)>", sparql),
                               "variableGraphs": re.findall(r"GRAPH\s+(\?\w+)", sparql)},
                "outcome": "execution_failure", "result": None}
        self.queries.append(item)
        try:
            result = self.client.query(sparql)
            # _cell has already retained datatype/language hints; raw_json is
            # a capped debug field and is deliberately NOT our evidence store.
            item.update(outcome="returned", result={"kind": result.kind, "columns": list(result.columns),
                        "rows": [list(row) for row in result.rows], "boolean": result.boolean if result.kind == "ask" else None})
            return result
        except Exception as error:
            # Preserve exact developer diagnostics separately from ordinary copy,
            # redacting configured credentials before any archive/disclosure.
            import os
            from .results import format_debug_text
            secrets = tuple(os.getenv(k, "") for k in ("NLQ_LLM_API_KEY", "OIR_FUSEKI_PASSWORD"))
            item["technicalDiagnostic"] = format_debug_text(f"{type(error).__name__}: {error}", secrets=secrets)
            item["debugOutput"] = format_debug_text(getattr(error, "debug_output", "") or "", secrets=secrets)
            item["error"] = "The read-only query failed."
            raise NLQError("The configured read-only query failed.") from error
        finally:
            item["finishedAt"] = now()


def compiler_context():
    # Content identity works for an uncommitted checkout too; not an ETL capture.
    paths = sorted((ROOT / "poc/nlq").glob("*.py"))
    paths += sorted((ROOT / "poc/specs").glob("*.json"))
    return {"compilerRevision": "sha256:" + hashlib.sha256(b"".join(
                p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes() + b"\0" for p in paths)).hexdigest(),
            "contractVersions": {name: json.loads((ROOT / f"poc/specs/{name}.json").read_text()).get("contractVersion")
                                 for name in ("composable-query-plan-contract", "query-schema-contract")}}


COMPILER_CONTEXT = compiler_context()  # process-start content identity, not per-request disk state


class ResearchAdapter:
    def __init__(self, client, predicates, *, endpoint_id="configured-local-query-service", context_id=None):
        self.client, self.predicates = client, predicates
        self.context = {"endpointId": endpoint_id, "snapshotId": None, "observationContextId": context_id or uuid4().hex}
        self.revision = copy.deepcopy(COMPILER_CONTEXT)

    def execute(self, request: OperationRequest):
        trace, started = QueryTrace(self.client), now()
        try:
            return self._execute(request, trace, started)
        except Exception:
            # An unexpected compiler/projection/shape error is not a successful
            # empty result. Retain even its already executed reads, without
            # exposing internal diagnostics or accepting partial witnesses.
            logger.exception("Research evidence acceptance failed for %s", request.operation.operation)
            return OperationEnvelope(
                evidenceId=f"e-{uuid4().hex}", request=request,
                outcome="validation_failure", compilerStatus="adapter_evidence_failure",
                validation={"admitted": False, "planValidated": False, "accepted": False},
                execution={"attempted": bool(trace.queries), "startedAt": started, "finishedAt": now(),
                           **self.revision, "datasetContext": self.context.copy(), "queries": trace.queries},
                resolvedScope={"term": None, "party": None, "reportingDate": request.reportingDate,
                               "temporalMeaning": "term_on_day" if request.operation.operation == TERM else "both_membership_and_party_active_on_day"},
                completeness={"enumeration": "unknown", "sourceCoverage": "uncertified", "freshness": "unknown",
                              "limitations": LIMITATIONS.copy()}, data=None, plan=None,
                error={"code": "evidence_integrity_failure", "stage": "adapter_evidence_acceptance",
                       "message": "The operation's evidence could not be retained and validated safely. No finding was accepted.",
                       "candidates": [], "retryable": False},
            )

    def _execute(self, request, trace, started):
        reporting = date.fromisoformat(request.reportingDate)
        if reporting > date.today():
            outcome = PlanOutcome("clarification_required", diagnostic="The reporting date is in the future; no query was run.")
        else:
            outcome = execute_question(request.factualRequest, as_of=reporting, fuseki=trace,
                supported_predicates=self.predicates, _current_dail_operation=request.operation)
        plan_ok = False
        if outcome.plan:
            try:
                from jsonschema import Draft202012Validator, FormatChecker
                plan_ok = validate_plan(outcome.plan) == outcome.plan
                Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text()),
                                     format_checker=FormatChecker()).validate(outcome.plan)
            except (ValueError, TypeError, KeyError):
                plan_ok = False
            except Exception:
                plan_ok = False
        refs = (outcome.plan or {}).get("referents", {})
        term, party, data = None, None, None
        failure = None
        if outcome.interaction == "answer":
            if not plan_ok or not trace.queries or any(q["outcome"] != "returned" for q in trace.queries):
                failure = "Accepted plan or complete execution trace unavailable."
            elif request.operation.operation == TERM:
                matches = refs["term"].get("matches", [])
                if len(matches) != 1:
                    failure = "The current-term operation requires one exact dated Dáil term."
                else:
                    term = matches[0]
                    data = {"term": term}
            else:
                members = (outcome.accepted_evidence or {}).get("members")
                term = {"iri": refs["term"].get("iri")}
                party = {"affiliationIri": refs["affiliation"].get("iri"), "label": refs["affiliation"].get("label"),
                         "partyIris": refs["party"].get("selectedIRIs")}
                if not members or any(not m["witnesses"] or any(w["termIri"] != term["iri"] for w in m["witnesses"]) for m in members):
                    failure = "Accepted structured Member witnesses unavailable or out of scope."
                else:
                    value = len({m["memberIri"] for m in members})
                    expected = ((str(value),),) if request.operation.operation == COUNT else None
                    if expected is not None and outcome.result.rows != expected:
                        failure = "Compiler count does not agree with accepted Member identities."
                    elif request.operation.operation == MEMBERS and {r[1]: r[0] for r in outcome.result.rows} != {m["memberIri"]: m["displayName"] for m in members}:
                        failure = "Compiler list does not agree with accepted Member identities."
                    else:
                        data = {"members": members, "value": value, "unit": "distinct_recorded_member_iris"}
        evidence_id = f"e-{uuid4().hex}"
        status = "validation_failure" if failure else outcome.interaction
        if data and "members" in data:
            for member in data["members"]:
                for witness in member["witnesses"]:
                    witness["queryRefs"] = [q["queryId"] for q in trace.queries]
        return OperationEnvelope(
            evidenceId=evidence_id, request=request, outcome=status, compilerStatus=outcome.status,
            validation={"admitted": plan_ok, "planValidated": plan_ok, "accepted": status == "answer"},
            execution={"attempted": bool(trace.queries), "startedAt": started, "finishedAt": now(),
                       **self.revision, "datasetContext": self.context.copy(), "queries": trace.queries},
            resolvedScope={"term": term, "party": party, "reportingDate": request.reportingDate,
                           "temporalMeaning": "term_on_day" if request.operation.operation == TERM else "both_membership_and_party_active_on_day"},
            completeness={"enumeration": "complete_within_query_scope" if status == "answer" else "unknown",
                          "sourceCoverage": "uncertified", "freshness": "unknown", "limitations": LIMITATIONS.copy()},
            data=data if status == "answer" else None,
            error=None if status == "answer" else {"code": failure and "evidence_integrity_failure" or outcome.status,
                "stage": "evidence_acceptance" if failure else "compiler", "message": failure or outcome.diagnostic or "No accepted evidence.",
                "candidates": list(outcome.candidates), "retryable": status == "execution_failure"},
            plan=outcome.plan,
        )
