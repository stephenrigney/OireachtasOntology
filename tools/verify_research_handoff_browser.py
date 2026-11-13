"""Fresh browser outcomes. --live uses real configured model/Fuseki.

Default controls inject a model and failure switches, but execute real compiler
fixtures. These controls are explicitly not genuine parliamentary observations.
"""
import argparse
import asyncio
import json
import re
import socket
import sys
from datetime import date
from pathlib import Path
from threading import Thread

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from poc.nlq import research_app, query_evidence
from poc.nlq.research_collaborator import create_collaborator
from poc.nlq.research_tools import ResearchTools
from test_nlq_committee_members import Fixture, Generator, draft
from test_research_evidence_handoff import CURRENT, HISTORY
from test_research_general_queries import query
from test_research_v05 import plan

EMPTY = "How many TDs represented Meath East in this Dáil on 2026-10-28?"
AMBIGUOUS = "What parties was Stephen Donnelly a member of?"


SWITCH = {"mode": "current"}


class ControlModel:
    def generate(self, phase, payload):
        if phase == "plan":
            tasks = [query(CURRENT)]
            if SWITCH["mode"] == "history":
                tasks = [query(HISTORY)]
            if SWITCH["mode"] in {"empty", "ambiguous"}:
                tasks = [query(EMPTY if SWITCH["mode"] == "empty" else AMBIGUOUS)]
            if SWITCH["mode"] == "partial":
                tasks.append(query(HISTORY, id="history"))
            p = plan(tasks)
            p.update(title="Committee membership", interpretation="Check current membership and any requested earlier membership.",
                     response="I will check the available membership records.")
            p["requirements"] = [{"kind": "research_question", "wording": t["question"], "conditions": [t["question"]],
                                  "disposition": "evidence pending", "explanation": "Check available records."} for t in tasks]
            return p
        if phase == "investigate":
            return {"tasks": [], "explanation": "No further queries are needed for this control."}
        facts = payload["facts"]
        sections = []
        if facts:
            keys = [key for key in next(iter(facts.values()))["proposition"]["fields"]
                    if all(key in f["proposition"]["fields"] for f in facts.values())]
            sections = [{"id": "findings", "title": "Recorded membership", "kind": "findings", "factRefs": [], "narrative": [],
                         "tables": [{"caption": "Members in the available records", "kind": "records", "columns": keys,
                                     "factRefs": list(facts), "activityRefs": []}]}]
        return {"response": "The report shows the available findings and any unanswered questions.", "responseNarrative": None,
                "sections": sections, "unanswered": [], "resolvedQuestions": []}


class FixtureTools(ResearchTools):
    def __init__(self, *args, **kwargs):
        class Planner:
            def generate(self, question):
                if SWITCH["mode"] == "empty":
                    from test_nlq_composable_party_temporal import _representation_member_draft
                    proposal = _representation_member_draft(constituency="Meath East")
                    proposal["constraints"] = [{"referent": "membership", "field": "membershipInterval", "operator": "on", "value": "2026-10-28"}]
                    return json.dumps(proposal)
                if "history" in question:
                    return json.dumps({"version": 2, "supported": False, "family": None,
                        "unsupportedReason": "Historical committee retrieval is not available.", "intent": HISTORY,
                        "referents": None, "relations": [], "constraints": [], "answer": None})
                return Generator(draft("Committee of Public Accounts")).generate(question)
        super().__init__(*args, **kwargs, semantic_plan_generator_factory=Planner)


def control_client():
    if SWITCH["mode"] == "empty":
        from test_nlq_composable_party_temporal import _current_term_fixture
        return _current_term_fixture(constituency_label="Meath East", membership_interval=("2024-11-29T00:00:00", "2025-12-31T00:00:00"))
    if SWITCH["mode"] == "ambiguous":
        from test_nlq_composable_q06 import Q06Fixture
        return Q06Fixture(ambiguous=True)
    if SWITCH["mode"] == "failure":
        class Broken:
            def query(self, sparql):
                raise RuntimeError("Injected browser transport diagnostic 457")
        return Broken()
    fixture = Fixture()
    fixture.member("Jane")
    fixture.member("Patrick")
    return fixture


async def verify(url, output, live, selected=None):
    output.mkdir(parents=True, exist_ok=True)
    cases = [("current", CURRENT), ("history", HISTORY),
             ("partial", CURRENT + (" Also, what did those members say about housing in Dáil debates last year?" if live
                                     else " Also, how has its membership changed since 2020?"))]
    if live:
        cases.append(("chronology", "Please list the Dáil terms with their recorded start and end dates."))
        # Separate existing-fixture formulation, frozen in the root live cases;
        # never overwrite/relabel a failed ordinary-language paraphrase.
        cases.append(("chronology-fixture", "When did each Dáil start and finish?"))
    else:
        cases += [("handoff", CURRENT), ("result-only", CURRENT), ("failure", CURRENT), ("empty", EMPTY), ("ambiguous", AMBIGUOUS)]
    if selected:
        cases = [(key, question) for key, question in cases if key in selected]
    observations = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for mode, question in cases:
            SWITCH["mode"] = mode
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            page.set_default_timeout(240000)
            errors, dispatches = [], []
            page.on("pageerror", lambda e: errors.append(str(e)))

            async def before_step(route):
                assert await page.locator("#plan-card").is_visible()
                dispatches.append({"planVisibleBeforeDispatch": True, "text": await page.locator("#plan-tasks").inner_text()})
                await route.continue_()

            await page.route("**/runs/*/step", before_step)
            await page.goto(url)
            await page.locator("#brief").fill(question)
            async with page.expect_response(lambda r: r.url.endswith("/runs") and r.request.method == "POST") as response:
                await page.locator("#submit").click()
            prepared = await (await response.value).json()
            await expect(page.locator("#overall-state")).to_have_text(re.compile(
                r"Findings available.*|Question not answered|Records found.*|Search completed.*|Research interrupted|Needs clarification|No matching records found"), timeout=900000)
            await expect(page.locator("#pause")).not_to_be_visible(timeout=900000)
            archive = await (await page.request.get(url + "/runs/" + prepared["id"] + "/archive")).json()
            state = archive["state"]
            await expect(page.locator("#research-progress")).to_have_text(state["status"])
            (output / f"{mode}.json").write_text(json.dumps({"kind": "actual configured model/Fuseki" if live else "injected model/compiler fixture control",
                **archive, "dispatches": dispatches, "javascriptErrors": errors}, ensure_ascii=False, indent=2))
            if mode in {"current", "partial", "chronology", "chronology-fixture"}:
                assert state["facts"], state
                await expect(page.locator("#report")).to_be_visible()
            elif mode in {"handoff", "result-only", "failure", "empty", "ambiguous"}:
                assert not state["facts"], state
            if mode == "history":
                assert state["unanswered"]
                assert any(t.get("researchOutcome", {}).get("kind") == "unsupported_question" for t in state["tasks"])
                # Useful current-membership supporting retrieval is permitted;
                # it must not silently answer the requested historical question.
                assert all(f["proposition"]["predicate"] == "current_committee_membership" for f in state["facts"].values())
            if mode in {"handoff", "failure"}:
                expected = "couldn't include them" if mode == "handoff" else "search couldn't be completed"
                await expect(page.locator("#latest-reply")).to_contain_text(expected)
            if mode in {"empty", "ambiguous"}:
                expected = "No matching records" if mode == "empty" else "Please clarify"
                await expect(page.locator("#latest-reply")).to_contain_text(expected)
            if mode == "result-only":
                await expect(page.locator("#latest-reply")).to_contain_text("The search completed, but")
                assert state["status"] == "Search completed — result not included"
            if mode == "partial":
                assert state["unanswered"]
            primary = await page.locator("#research-canvas").inner_text()
            for jargon in ("evidence shape", "factual boundary", "promoted fact", "compiler status", "projection", "unsupported capability"):
                assert jargon not in primary.lower(), (mode, jargon)
            await page.screenshot(path=str(output / f"{mode}-report.png"), full_page=True)
            if state["facts"]:
                await page.get_by_role("button", name=re.compile("Evidence:")).first.click()
                if await page.get_by_role("heading", name="Individual recorded facts", exact=True).count():
                    await page.locator("#activity-content button").nth(1).click()
                await expect(page.locator("#activity-content")).to_contain_text("Source records")
                await page.screenshot(path=str(output / f"{mode}-source.png"), full_page=True)
                await page.keyboard.press("Escape")
                await page.locator("#activity").click()
            else:
                await page.locator("#activity").click()
            await page.locator("#activity-content .evidence-link").first.click()
            await page.get_by_text("Advanced: plan, all SPARQL pages, returned RDF evidence & diagnostics", exact=True).click()
            advanced = await page.locator("#activity-content details").last.inner_text()
            assert "queries" in advanced
            shown = json.loads(await page.locator("#activity-content details").last.locator("pre").inner_text())
            assert shown["execution"]["queries"] == archive["evidence"][shown["evidenceId"]]["execution"]["queries"]
            if mode in {"handoff", "result-only"}:
                assert "structured factual boundary" in advanced
            if mode == "failure":
                assert "Injected browser transport diagnostic 457" in advanced
            await page.screenshot(path=str(output / f"{mode}-technical.png"), full_page=True)
            await page.keyboard.press("Escape")
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            await page.screenshot(path=str(output / f"{mode}-mobile.png"), full_page=True)
            exported = await (await page.request.get(url + "/runs/" + prepared["id"] + "/report.md")).text()
            assert "Draft — for review" in exported and "## Evidence references" in exported
            (output / f"{mode}.json").write_text(json.dumps({"kind": "actual configured model/Fuseki" if live else "injected model/compiler fixture control",
                **archive, "dispatches": dispatches, "javascriptErrors": errors}, ensure_ascii=False, indent=2))
            (output / f"{mode}.md").write_text(exported)
            observations.append({"case": mode, "facts": len(state["facts"]), "status": state["status"],
                "outcomes": [t.get("researchOutcome") for t in state["tasks"]], "planBeforeDispatch": bool(dispatches), "javascriptErrors": errors})
            assert not errors
            (output / "observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2))
            await page.close()
        await browser.close()
    (output / "observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--cases", nargs="+", choices=["current", "history", "partial", "chronology", "chronology-fixture", "handoff", "result-only", "failure", "empty", "ambiguous"])
    args = parser.parse_args()
    if not args.live:
        research_app.ResearchTools = FixtureTools
        original = query_evidence.finalize_evidence
        def finalize(outcome):
            from dataclasses import replace
            if SWITCH["mode"] in {"handoff", "result-only"}:
                outcome = replace(outcome, validated_facts=(),
                    selection_outcome=None if SWITCH["mode"] == "result-only" else outcome.selection_outcome)
            return original(outcome)
        query_evidence.finalize_evidence = finalize
    app = research_app.create_app(planner_factory=create_collaborator if args.live else ControlModel,
        client_factory=None if args.live else control_client, reporting_date=date(2026, 11, 13))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    try:
        asyncio.run(verify(f"http://127.0.0.1:{port}", args.output, args.live, args.cases))
    finally:
        server.should_exit = True
        thread.join(10)


if __name__ == "__main__":
    main()
