"""A bounded research run, not a general agent or semantic composition engine."""
from __future__ import annotations

import copy
import json
import os
import re
from datetime import date
from time import monotonic
from uuid import uuid4

from pydantic import Field

from .config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL
from .research_adapter import (ClosedModel, OperationRequest, ResearchAdapter, TERM, MEMBERS, COUNT, LIMITATIONS)
from .structured_planner import ResponsesPlanGenerator, PlannerModelError, parse_draft_json


class BriefProposal(ClosedModel):
    parties: list[str] = Field(max_length=4)


def create_research_planner():
    return ResponsesPlanGenerator(
        os.getenv("NLQ_LLM_API_KEY", ""), os.getenv("NLQ_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        os.getenv("NLQ_LLM_MODEL", DEFAULT_LLM_MODEL), output_schema=BriefProposal.model_json_schema(),
        schema_name="parliamentary_research_brief", instructions="""Interpret a bounded research brief about contemporary Dáil party representation.
Return every named party as an EXACT VERBATIM contiguous mention from the brief, once each, in mention order.
Do not return Members, constituencies, conditions, prose, identities or facts. Do not remove conditions to make a request supported.
The application accounts for the ENTIRE original brief independently and refuses unsupported residual requirements.
Return an empty parties array for a term-only request or when no party is named. No SPARQL or query planning.""",
    )


# This is deliberately a small research-language admission boundary, not an
# expansion of compiler NLQ. Every non-party token must be accounted for. A
# lossy model extraction can therefore never silently erase a material filter.
# Unknown wording is visible as unsupported and requires a fresh bounded brief.
_BRIEF_WORDS = set("""prepare write produce give me a an the short brief report comparing compare comparison
and with to of in on for about current contemporary dáil dail membership memberships
including include totals total counts count number numbers members member names name
involved their who are is how many which deputies tds party parties representation
please list show summary overview between versus vs recorded local involved what term terms currently""".split())
_TERM_WORDS = set("""prepare write produce give me a an the short brief report please list show summary overview
what which is are in on of for about current contemporary dáil dail term terms currently""".split())


def account_brief(brief: str, proposal: BriefProposal):
    remainder = brief
    previous_end = -1
    for party in proposal.parties:
        if not party or party.strip() != party or len(party) > 120:
            return "The planner did not preserve usable party mentions."
        match = re.search(r"(?<!\w)" + re.escape(party) + r"(?!\w)", brief)
        if not match or match.start() <= previous_end:
            return "Party mentions must be verbatim, distinct and in original brief order."
        previous_end = match.end() - 1
        remainder = re.sub(r"(?<!\w)" + re.escape(party) + r"(?!\w)", " ", remainder)
    tokens = re.findall(r"\w+", remainder.casefold())
    # Generic report words cannot license extra conditions (notably an
    # office-holding filter). Likewise party-domain
    # vocabulary must not turn a person/representation request into a term lookup.
    allowed = _BRIEF_WORDS if proposal.parties else _TERM_WORDS
    unknown = sorted(set(tokens) - allowed)
    if unknown or re.search(r"[^\w\s,.?!:;()'’\-]", remainder):
        return "Unsupported or unaccounted brief wording: " + (", ".join(unknown) or "additional symbols") + ". No party request will be weakened or dispatched."
    # Mentions are NOT identities. The compiler must still admit the atomic
    # request and resolve the WHOLE mention to a reviewed party identity. Do
    # not ban words inside genuine party names (e.g. People Before Profit).
    if not re.search(r"\b(?:current|contemporary)\b", brief, re.I):
        return "Clarification required: this slice needs explicit current Dáil scope at the fixed reporting date. Submit a new brief with that scope."
    if not re.search(r"\bd[áa]il\b", brief, re.I):
        return "Clarification required: name the Dáil explicitly; no chamber was assumed."
    if re.search(r"\b(?:compare|comparing|comparison|between|versus|vs)\b", remainder, re.I) and len(proposal.parties) < 2:
        return "Clarification required: a comparison needs at least two explicitly named parties; no comparison requirement was discarded."
    if not proposal.parties and re.search(r"\b(?:members?|membership|totals?|counts?|compar\w*|parties|party)\b", brief, re.I):
        return "Clarification required: name each party. An unfiltered Dáil roster is not supported."
    if not proposal.parties and not re.search(r"\bterms?\b", brief, re.I):
        return "Clarification required: ask explicitly for the current Dáil term, or name the parties whose membership you want to investigate."
    return None


def selection_signature(data):
    members = copy.deepcopy(data["members"])
    for member in members:
        for witness in member["witnesses"]:
            witness.pop("queryRefs", None)
        member["witnesses"].sort(key=lambda w: json.dumps(w, sort_keys=True))
    return sorted(members, key=lambda m: m["memberIri"])


def compatible(left, right):
    if left["outcome"] != "answer" or right["outcome"] != "answer":
        return False
    for path in [("resolvedScope", "reportingDate"), ("resolvedScope", "temporalMeaning"),
                 ("execution", "datasetContext"), ("execution", "compilerRevision"),
                 ("completeness", "sourceCoverage"), ("completeness", "freshness"),
                 ("completeness", "limitations")]:
        if left[path[0]][path[1]] != right[path[0]][path[1]]:
            return False
    return (left["validation"]["accepted"] and right["validation"]["accepted"]
            and left["resolvedScope"]["term"]["iri"] == right["resolvedScope"]["term"]["iri"]
            and left["data"].get("unit") == right["data"].get("unit") == "distinct_recorded_member_iris"
            and left["completeness"]["enumeration"] == right["completeness"]["enumeration"] == "complete_within_query_scope")


class ResearchRun:
    def __init__(self, brief, reporting_date, adapter: ResearchAdapter, planner_factory=create_research_planner):
        self.id = uuid4().hex
        self.created = self.clock = monotonic()
        self.brief, self.date, self.adapter = brief, reporting_date.isoformat(), adapter
        self.evidence, self.tasks, self.sections = {}, [], []
        self.parties, self.unanswered = [], []
        self.version = 0
        self.metrics = {"firstValidatedSeconds": None, "completedSeconds": None}
        self.status = "Plan published"
        planner = None
        planning_failed = False
        try:
            planner = planner_factory()
            self.proposal = BriefProposal.model_validate(parse_draft_json(planner.generate(brief)))
            reason = account_brief(brief, self.proposal)
            self.parties = self.proposal.parties if reason is None else []
        except PlannerModelError as error:
            self.proposal = None
            planning_failed = True
            reason = f"Research planning failed: {error} Your original brief is retained; no party query was dispatched."
        except Exception:
            self.proposal = None
            planning_failed = True
            reason = "The research planner failed or returned an invalid proposal. Your original brief is retained; no party query was dispatched."
        finally:
            if planner is not None:
                planner.close()
        if reason:
            self.unanswered.append({"requirement": brief, "reason": reason,
                                    "state": "Planning failed" if planning_failed else "Clarification required" if "Clarification" in reason else "Unsupported"})
        self._task("term", "Identify the current Dáil from House-owned dates", TERM)
        self.sections.append({"id": "term", "title": "Reporting scope", "state": "Pending", "evidenceRefs": []})
        if reason and not re.search(r"\b(?:current|contemporary)\s+d[áa]il\b", brief, re.I):
            self.tasks[0].update(state="Blocked", reason="No independent explicit current Dáil requirement was established.")
            self.sections[0].update(state="Blocked", reason=self.tasks[0]["reason"])
            self.status = "Completed with limitations"
        for i, party in enumerate(self.parties):
            key = f"party-{i}"
            self._task(key + "-members", f"Retrieve accepted {party} Members", MEMBERS, party, ["term"])
            self._task(key + "-count", f"Verify the distinct recorded-Member count for {party}", COUNT, party, ["term"])
            self.sections.append({"id": key, "title": party, "state": "Pending", "evidenceRefs": [], "members": [], "count": None})
        if len(self.parties) >= 2:
            self.tasks.append({"id": "comparison", "title": "Compare compatible validated local results", "state": "Pending",
                               "dependencies": [t["id"] for t in self.tasks if t["id"] != "term"], "operation": "compare.recorded_member_counts"})
            self.sections.append({"id": "comparison", "title": "Short comparison", "state": "Pending", "evidenceRefs": []})

    def _task(self, key, title, operation, party=None, dependencies=None):
        factual = "What is the current Dáil term?" if operation == TERM else (
            f"Who are the {party} Deputies in the current Dáil?" if operation == MEMBERS
            else f"How many {party} Deputies are in the current Dáil?")
        self.tasks.append({"id": key, "title": title, "state": "Pending", "dependencies": dependencies or [],
                           "operation": operation, "request": OperationRequest(
                               requestId=f"{self.id}.{key}", requirementId=key, factualRequest=factual, reportingDate=self.date,
                               operation={"operation": operation, **({"partyMention": party} if party else {})}).model_dump()})

    def _section(self, key):
        return next(s for s in self.sections if s["id"] == key)

    def step(self, version):
        """One bounded automatic dispatch. Client has already published the plan.

        Version checks + per-run HTTP lock make repeated clicks/retries
        idempotent. A failed task does not replace any accepted evidence.
        """
        if version != self.version:
            return self.view()
        task = next((t for t in self.tasks if t["state"] == "Pending"), None)
        if task is None:
            return self.view()
        task["state"] = "Running"
        if any(next(t for t in self.tasks if t["id"] == dep)["state"] != "Validated" for dep in task["dependencies"]):
            task.update(state="Blocked", reason="Required evidence was not validated; independent findings are preserved.")
        elif task["id"] == "comparison":
            self._compare(task)
        else:
            try:
                env = self.adapter.execute(OperationRequest.model_validate(task["request"])).model_dump()
                self.evidence[env["evidenceId"]] = env
                task["evidenceRef"] = env["evidenceId"]
                if env["outcome"] == "answer" and task["id"] != "term":
                    term = self._section("term")["term"]
                    if env["resolvedScope"]["term"]["iri"] != term["iri"]:
                        task.update(state="Blocked", reason="Party result disagrees with the independently validated exact Dáil term.")
                    else:
                        task["state"] = "Validated"
                elif env["outcome"] == "answer":
                    task["state"] = "Validated"
                else:
                    task.update(state={"unsupported_capability": "Unsupported", "clarification_required": "Clarification required",
                                       "execution_failure": "Execution failed", "validation_failure": "Validation failed",
                                       "unresolved_identity": "Unresolved identity"}.get(env["outcome"], "Missing or unaccepted evidence"),
                                reason=env["error"]["message"])
            except Exception:
                # Internal errors are not empty selections; prior sections remain.
                task.update(state="Execution failed", reason="The operation could not be completed. No finding was accepted.")
        self._assemble(task)
        self.version += 1
        if task["state"] == "Validated" and self.metrics["firstValidatedSeconds"] is None:
            self.metrics["firstValidatedSeconds"] = round(monotonic() - self.clock, 3)
        if not any(t["state"] == "Pending" for t in self.tasks):
            self.status = "Completed with limitations"
            self.metrics["completedSeconds"] = round(monotonic() - self.clock, 3)
        else:
            self.status = "Research in progress"
        return self.view()

    def _compare(self, task):
        counts = [self.evidence[next(t for t in self.tasks if t["id"] == f"party-{i}-count")["evidenceRef"]]
                  for i in range(len(self.parties))]
        sections = [self._section(f"party-{i}") for i in range(len(self.parties))]
        if any(s["state"] != "Validated" for s in sections) or any(not compatible(counts[0], other) for other in counts[1:]):
            task.update(state="Blocked", reason="The count/list evidence is not compatible. Individual findings remain available.")
            return
        # Explicitly a comparison of separately observed local selections, NOT
        # a snapshot-consistent substantive claim about real-world party strength.
        task.update(state="Validated", calculation={
            "kind": "deterministic_calculation", "meaning": "difference_between_separately_observed_local_results",
            "evidenceRefs": [c["evidenceId"] for c in counts],
            "differences": [{"left": self.parties[0], "right": self.parties[i],
                             "leftMinusRight": counts[0]["data"]["value"] - counts[i]["data"]["value"]}
                            for i in range(1, len(counts))],
        })

    def _assemble(self, task):
        if task["id"] == "comparison":
            section = self._section("comparison")
            section.update(state=task["state"], reason=task.get("reason"))
            if task["state"] == "Validated":
                section.update(calculation=task["calculation"], evidenceRefs=task["calculation"]["evidenceRefs"])
            return
        if task["id"] == "term":
            section = self._section("term")
            section.update(state=task["state"], reason=task.get("reason"))
            if task["state"] == "Validated":
                env = self.evidence[task["evidenceRef"]]
                section.update(term=env["data"]["term"], evidenceRefs=[env["evidenceId"]])
            return
        key = task["id"].rsplit("-", 1)[0]
        section = self._section(key)
        if task["state"] != "Validated":
            section.update(state="Incomplete", reason=task.get("reason"))
            return
        env = self.evidence[task["evidenceRef"]]
        section["evidenceRefs"].append(env["evidenceId"])
        if task["operation"] == MEMBERS:
            section.update(members=env["data"]["members"], state="Populating")
        else:
            list_task = next(t for t in self.tasks if t["id"] == key + "-members")
            list_env = self.evidence.get(list_task.get("evidenceRef"))
            if (list_task["state"] != "Validated" or not compatible(list_env, env)
                    or selection_signature(list_env["data"]) != selection_signature(env["data"])):
                task.update(state="Blocked", reason="Compiler count and list observations disagree; no verified report total or comparison.")
                section.update(state="Incomplete", reason=task["reason"])
            else:
                section.update(count=env["data"]["value"], state="Validated")

    def view(self):
        return copy.deepcopy({"id": self.id, "brief": self.brief, "reportingDate": self.date,
            "title": "Current Dáil · recorded party representation" if self.parties else "Current Dáil research",
            "status": self.status, "version": self.version, "tasks": self.tasks,
            "sections": self.sections, "unanswered": self.unanswered,
            "limitations": LIMITATIONS, "metrics": self.metrics,
            "evidence": {eid: {"evidenceId": eid, "outcome": e["outcome"], "request": e["request"],
                                "compilerStatus": e["compilerStatus"], "error": e["error"],
                                "queryCount": len(e["execution"]["queries"])} for eid, e in self.evidence.items()}})

    def markdown(self):
        def text(value):
            return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")
        lines = [f"# {self.view()['title']}", "", f"**{self.status}** · reporting date {self.date}",
                 "", "Original brief: " + text(self.brief), "", "## Overview",
                 "Qualified findings from validated local RDF queries. No complete real-world roster or source freshness is certified."]
        incomplete = bool(self.unanswered) or any(t["state"] != "Validated" for t in self.tasks)
        lines[4:4] = ["Report state: Incomplete — pending, blocked or unanswered requirements remain."
                      if incomplete else "Report state: Qualified local findings — source completeness is not certified.", ""]
        for section in self.sections:
            lines += ["", "## " + text(section["title"]), "", "Status: " + section["state"]]
            if section.get("term"):
                term = section["term"]
                lines += [f"{text(term['label'])} — {term['iri']}; recorded start {term['start']}; end {term['end'] or 'not recorded (open-ended)' }."]
            if section.get("members"):
                lines += [f"Distinct recorded Members: {section['count']} (compiler count/list agreement)." if section["count"] is not None
                          else "Member list available; compiler total not yet verified.", "", "| Member | Member IRI |", "| --- | --- |"]
                lines += [f"| {text(m['displayName'])} | {m['memberIri']} |" for m in section["members"]]
            if section.get("calculation"):
                lines += ["Deterministic comparison of separately observed local results, not snapshot-consistent real-world party strength."]
                lines += [f"{text(d['left'])} minus {text(d['right'])}: {d['leftMinusRight']} distinct recorded Member IRIs."
                          for d in section["calculation"]["differences"]]
            if section.get("reason"):
                lines += [text(section["reason"])]
            lines += ["Evidence: " + ", ".join(f"[{eid}](#{eid})" for eid in section["evidenceRefs"])]
        lines += ["", "## Limitations and unanswered requirements", ""] + ["- " + item for item in LIMITATIONS]
        lines += [f"- {item['state']}: {text(item['requirement'])} — {text(item['reason'])}" for item in self.unanswered]
        lines += [f"- {text(t['title'])}: {t['state']} — {text(t.get('reason', 'Awaiting validated evidence.'))}"
                  for t in self.tasks if t["state"] != "Validated"]
        lines += ["", "## Evidence references", ""]
        for eid, env in self.evidence.items():
            lines += [f"### {eid}", "", "```json", json.dumps(env, ensure_ascii=False, indent=2), "```"]
        return "\n".join(lines) + "\n"
