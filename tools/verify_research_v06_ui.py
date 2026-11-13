"""Fast browser controls over exact recorded compiler replay and INJECTED model.

Not live-model research or editorial acceptance. No network dataset access.
"""
import asyncio
import argparse
import json
import re
import socket
import sys
from datetime import date
from pathlib import Path
from threading import Event, Thread

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.research_app import create_app
from tools.diagnose_retrieval_satisfaction import load_bundle, Replay, SPONSOR
from tests.test_research_v05 import InjectedModel, plan, sponsor_task
from tools.verify_research_v06_browser import opening_checks


class UIModel(InjectedModel):
    def __init__(self, plans=None, slow_gate=None):
        super().__init__(plans)
        self.slow_gate = slow_gate

    def generate(self, phase, payload):
        if phase == "plan" and payload["newMessage"].startswith("Slow progress UI control"):
            entered, release = self.slow_gate
            entered.set()
            if not release.wait(20):
                raise RuntimeError("Injected slow planning control timed out")
            return plan([sponsor_task()])
        if phase == "plan" and payload["newMessage"].startswith("Unsupported UI control"):
            p = plan()
            p["requirements"][0].update(disposition="unsupported", explanation="Speech content cannot be established by this tool.")
            p["response"] = "I cannot establish what Members said from the information this tool can check."
            return p
        if phase == "plan" and payload["newMessage"].startswith("Planning failure UI control"):
            raise RuntimeError("Injected model service interruption")
        if phase == "plan" and payload["newMessage"].startswith("Clarification UI control"):
            return plan() | {"clarification": "Which Dáil term would you like to investigate?"}
        result = super().generate(phase, payload)
        if phase == "report":
            refs = [key for key, fact in payload["facts"].items() if
                    (fact["proposition"].get("predicate") if isinstance(fact["proposition"], dict)
                     else fact["proposition"][0]) == "sponsorship"]
            result["sections"][0]["factRefs"] = []
            result["sections"][0]["tables"] = [{"caption": "Recorded Bills", "kind": "bills", "factRefs": refs, "activityRefs": []}]
        return result


async def verify(url, output, slow_gate):
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        authored = page.locator("#section-findings")
        await page.goto(url)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        opening = await opening_checks(page, output)
        # Both examples are editable, and replacement is an explicit decision.
        await page.locator("#example-career").click()
        await expect(page.locator("#brief")).to_have_value("Which constituencies has Mary Lou McDonald represented?")
        page.once("dialog", lambda d: d.dismiss())
        await page.locator("#example").click()
        assert "constituencies" in await page.locator("#brief").input_value()
        page.once("dialog", lambda d: d.accept())
        await page.locator("#example").click()
        assert "Malcolm Byrne" in await page.locator("#brief").input_value()
        # HTTP submission failure: exact multiline text and keyboard focus survive.
        await page.route("**/runs", lambda r: r.fulfill(status=503, json={"detail": "Injected planning endpoint unavailable."}))
        draft = "My original question\n\nKeep every paragraph."
        await page.locator("#brief").fill(draft)
        await page.locator("#brief").press("Control+Enter")
        await expect(page.locator("#submission-error")).to_contain_text("preserved")
        await expect(page.locator("#brief")).to_have_value(draft)
        await expect(page.locator("#brief")).to_be_focused()
        await page.unroute("**/runs")
        held = asyncio.Event()
        release = asyncio.Event()
        calls = []
        reading = {}

        async def gate(route):
            calls.append(route.request.url)
            if len(calls) == 2:
                # The first /step prepares and publishes the plan. Hold the
                # actual retrieval dispatch until the visible plan is checked.
                await expect(page.locator("#plan-interpretation")).to_contain_text("Investigate sponsorship")
                await expect(page.locator("#plan-tasks li").first).to_be_in_viewport()
                await expect(page.locator("#plan-summary")).to_be_in_viewport()
                await page.screenshot(path=str(output / "injected-plan-before-dispatch.png"))
                held.set()
                await release.wait()
            elif len(calls) == 4:
                # Read an unchanged finding while the author finishes a later,
                # failing task. Automatic updates must leave focus/position alone.
                target = authored.get_by_role("button", name="Evidence: individual recorded facts").first
                await target.focus()
                await target.scroll_into_view_if_needed()
                reading["y"] = (await target.bounding_box())["y"]
            await route.continue_()

        await page.route("**/runs/*/step", gate)
        await page.locator("#brief").fill("Injected UI control: investigate sponsorship")
        await page.locator("#brief").press("Meta+Enter")
        await asyncio.wait_for(held.wait(), 30)
        await page.locator("#pause").click()
        async with page.expect_response(lambda r: r.url.endswith("/step")):
            release.set()
        await expect(page.locator("#pause")).to_have_text("Resume research")
        # The in-flight compiler operation completed; no author step can
        # dispatch while the UI is paused.
        assert len(calls) == 2
        await page.locator("#pause").click()
        await expect(page.locator("#overall-state")).to_have_text("Completed with unanswered questions")
        assert len(calls) == 3  # planning, one compiler operation, one author pass
        await expect(authored).to_be_visible()
        assert await page.locator("#report-sections section").count() == 2  # Original result plus optional assertion draft.
        await page.locator("#plan-summary").click()
        await expect(page.locator("#plan-disclosure")).not_to_have_attribute("open", "")
        await page.locator("#reach-plan").click()
        await expect(page.locator("#plan-interpretation")).to_be_visible()
        await expect(page.locator("#plan-summary")).to_be_focused()
        evidence = authored.get_by_role("button", name="Evidence:").first
        await evidence.focus(); await page.keyboard.press("Enter")
        await page.locator("#activity-drawer button").last.focus()
        await page.keyboard.press("Tab")
        assert await page.locator("#activity-drawer").evaluate("el => el.contains(document.activeElement)")
        await page.keyboard.press("Escape")
        assert await evidence.evaluate("el => el === document.activeElement")
        # Nested row → assertion → source → Escape returns to the original row.
        row = authored.get_by_role("button", name="Evidence: individual recorded facts").first
        await row.click()
        await page.locator("#activity-content button").nth(1).click()
        await page.locator("#activity-content .evidence-link").first.click()
        await expect(page.locator("#activity-content")).to_contain_text("Validation accepted: yes")
        await page.keyboard.press("Escape")
        await expect(row).to_be_focused()
        # Constructed progressive redraw while the drawer is open. The exact
        # source/assertion stays unchanged; only its section heading changes.
        await row.click()
        await page.evaluate("""() => {
            window.originalSectionTitle = run.sections.find(s => s.id === 'findings').title;
            window.detachedOpener = opener;
            run.sections.find(s => s.id === 'findings').title += ' — updated presentation'; render();
        }""")
        assert await page.evaluate("!window.detachedOpener.isConnected")
        await page.keyboard.press("Escape")
        await expect(row).to_be_focused()
        await page.evaluate("() => { run.sections.find(s => s.id === 'findings').title = window.originalSectionTitle; render(); }")
        # Explicitly challenging a finding uses plain wording, not a hash ID.
        await evidence.click()
        await page.get_by_role("button", name="Challenge or explain this assertion").click()
        await expect(page.locator("#brief")).to_be_focused()
        value = await page.locator("#brief").input_value()
        assert value.startswith("Please explain or reconsider this finding:")
        assert "assertion " not in value
        await page.locator("#brief").fill("")
        await authored.locator("button", has_text="Refine this section").click()
        await expect(page.locator("#brief")).to_be_focused()
        await expect(page.locator("#section-context")).to_be_visible()
        await page.locator("#brief").fill("Preserve my unfinished revision")
        await page.locator("#clear-context").click()
        await expect(page.locator("#brief")).to_have_value("Preserve my unfinished revision")
        # A failed follow-up preserves the report, section context and draft.
        await authored.locator("button", has_text="Refine this section").click()
        await page.route("**/runs/*/messages", lambda r: r.fulfill(status=503, json={"detail": "Injected follow-up endpoint unavailable."}))
        prior_report = await page.locator("#report-sections").inner_text()
        await page.locator("#brief").press("Control+Enter")
        await expect(page.locator("#submission-error")).to_contain_text("preserved")
        assert await page.locator("#report-sections").inner_text() == prior_report
        await expect(page.locator("#section-context")).to_be_visible()
        await expect(page.locator("#brief")).to_have_value("Preserve my unfinished revision")
        await page.unroute("**/runs/*/messages")
        await page.locator("#clear-context").click()
        # Request a new task with a different name. Replay refuses the mismatched
        # query: deliberate execution failure, not missing/zero facts.
        await page.locator("#brief").fill("Injected scope change with a failing independent query")
        async with page.expect_response(lambda r: r.url.endswith("/messages")):
            await page.locator("#brief").press("Control+Enter")
        await expect(page.locator("#plan-tasks")).to_contain_text("Unresolved Person")
        await expect(page.locator("#overall-state")).to_have_text("Completed with unanswered questions")
        await expect(row).to_be_focused()
        assert abs((await row.bounding_box())["y"] - reading["y"]) <= 2, "Unrelated update moved the reading position"
        await page.locator("#activity").click()
        await expect(page.locator("#activity-content")).to_contain_text("records search could not be completed")
        await expect(page.locator("#activity-content")).to_contain_text("HTTP 503")
        await page.keyboard.press("Escape")
        assert await page.locator("#report-sections section").count() >= 1
        assert await page.locator("#report-sections").get_by_role("button", name="Evidence:").count() > 0
        # User messages are server replayed once, not locally doubled.
        await page.locator("#conversation-history summary").click()
        texts = await page.locator(".message").all_text_contents()
        assert sum("Injected UI control: investigate sponsorship" in text for text in texts) == 1
        await page.screenshot(path=str(output / "injected-history-and-failure.png"))
        await page.locator("#conversation-history summary").click()
        # Network step interruption is distinct from the compiler's failed read.
        # Retrying the same bounded version must not discard accepted findings.
        await page.route("**/runs/*/step", lambda r: r.fulfill(status=503, json={"detail": "Injected query service unavailable."}))
        await page.locator("#brief").fill("Shorten the explanation without changing facts")
        await page.locator("#brief").press("Control+Enter")
        await expect(page.locator("#report-outcome")).to_contain_text("resume to check the same version safely")
        await expect(page.locator("#pause")).to_have_text("Resume research")
        assert await page.locator("#report-sections section").count() >= 1
        await page.unroute("**/runs/*/step")
        # A new explicit follow-up while paused resumes automatic work, but the
        # previous interruption remains visible until a step actually succeeds.
        observed_retry = []
        retry_started = asyncio.Event()
        async def retry_gate(route):
            observed_retry.append(await page.locator("#report-outcome").inner_text())
            retry_started.set()
            await route.continue_()
        await page.route("**/runs/*/step", retry_gate)
        await page.locator("#brief").fill("Please shorten the explanation and keep the evidence")
        await page.locator("#brief").press("Control+Enter")
        await asyncio.wait_for(retry_started.wait(), 30)
        await expect(page.locator("#overall-state")).to_have_text("Completed with unanswered questions")
        assert observed_retry and "could not confirm this step" in observed_retry[0]
        await expect(page.locator("#report-outcome")).not_to_contain_text("The browser could not confirm the research step")
        # Unsupported and planning failures have no pretend report surface.
        for label, question in [("unsupported", "Unsupported UI control: what did Members say about housing?"),
                                ("planning-failure", "Planning failure UI control: preserve this exact question"),
                                ("clarification", "Clarification UI control: compare representation across terms")]:
            await page.goto(url)
            await page.locator("#brief").fill(question)
            await page.locator("#brief").press("Control+Enter")
            await expect(page.locator("#latest-reply")).to_be_visible()
            await expect(page.locator("#latest-reply")).to_contain_text({"unsupported": "cannot establish", "planning-failure": "couldn't prepare", "clarification": "Which Dáil term"}[label])
            assert not await page.locator("#report").is_visible()
            await expect(page.locator("#original-brief")).to_have_text(question)
            if label == "planning-failure":
                await expect(page.locator("#brief")).to_have_value(question)
                await expect(page.locator("#research-progress")).to_have_text("Interrupted")
                await expect(page.locator("#announcement")).to_have_text("Interrupted. Read the report and outcome summary.")
            if label == "clarification":
                await expect(page.locator("#research-progress")).to_have_text("Awaiting clarification")
                await expect(page.locator("#announcement")).to_contain_text("Clarification required")
            await page.screenshot(path=str(output / f"injected-{label}.png"))
        # A real server-side slow model call must remain inspectable through the
        # lock-independent progress endpoint, including elapsed time.
        await page.goto(url)
        await page.locator("#brief").fill("Slow progress UI control: hold planning while progress is inspected")
        await page.locator("#brief").press("Control+Enter")
        await expect(page.locator("#research-progress")).to_contain_text(
            re.compile(r"Understanding the request.*[1-9]\d*s elapsed"), timeout=10000)
        assert slow_gate[0].is_set()
        progress = await page.evaluate("serverProgress")
        assert progress["active"] and progress["elapsedSeconds"] >= 1
        await expect(page.locator("#research-progress")).to_contain_text("Understanding the request")
        await expect(page.locator("#research-progress")).to_contain_text("elapsed")
        await page.screenshot(path=str(output / "injected-slow-progress.png"))
        slow_gate[1].set()
        await expect(page.locator("#overall-state")).to_have_text("Completed with unanswered questions", timeout=30000)
        assert not errors, errors
        await browser.close()
        return opening | {"kind": "injected model + exact compiler-response replay", "planInViewportBeforeDispatch": True,
                 "pauseResume": True, "modalTabEscapeFocus": True, "independentFailureRetainsReport": True,
                 "singleUserMessageEcho": True, "controlAndMetaSubmit": True, "multilineSubmissionFailurePreserved": True,
                 "nestedSourceFocusReturn": True, "sectionContext": True, "unsupportedAndPlanningFailure": True,
                 "stepNetworkInterruptionRetry": True, "pausedFollowUpResumes": True, "interruptionRetainedUntilRetry": True,
                 "redrawnOpenerFocusReturn": True, "stableReadingPosition": True,
                 "serverProgressDuringSlowModelCall": progress,
                 "javascriptErrors": errors, "humanAcceptance": "not assessed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/tmp/oireachtasontology/research-v06-ui"))
    args = parser.parse_args()
    record = next(r for r in load_bundle()["live"] if r["question"] == SPONSOR and r["controlledProposal"] is None)
    slow_gate = (Event(), Event())
    models = lambda: UIModel([plan([sponsor_task()]), plan([sponsor_task() | {"id": "different", "member": "Unresolved Person", "question": "Which Bills did Unresolved Person sponsor?"}]), plan(revision="Shorten the explanation without changing facts"), plan(revision="Shorten the explanation without changing facts")], slow_gate)
    app = create_app(planner_factory=models, client_factory=lambda: Replay(record["queries"]), reporting_date=date(2026, 11, 12))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = Thread(target=server.run, daemon=True); thread.start()
    try:
        result = asyncio.run(verify(f"http://127.0.0.1:{port}", args.output, slow_gate))
        (args.output / "browser-summary.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()
