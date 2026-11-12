"""Fast browser controls over exact recorded compiler replay and INJECTED model.

Not live-model research or editorial acceptance. No network dataset access.
"""
import asyncio
import json
import socket
import sys
from datetime import date
from pathlib import Path
from threading import Thread

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.research_app import create_app
from tools.diagnose_retrieval_satisfaction import load_bundle, Replay, SPONSOR
from tests.test_research_v05 import InjectedModel, plan, sponsor_task


async def verify(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.goto(url)
        held = asyncio.Event()
        release = asyncio.Event()
        calls = []

        async def gate(route):
            calls.append(route.request.url)
            if len(calls) == 1:
                await expect(page.locator("#plan-card h2")).to_be_in_viewport()
                held.set()
                await release.wait()
            await route.continue_()

        await page.route("**/runs/*/step", gate)
        await page.locator("#brief").fill("Injected UI control: investigate sponsorship")
        await page.locator("#submit").click()
        await asyncio.wait_for(held.wait(), 30)
        await page.locator("#pause").click()
        async with page.expect_response(lambda r: r.url.endswith("/step")):
            release.set()
        await expect(page.locator("#pause")).to_have_text("Resume research")
        # A model-free server read confirms the one in-flight step completed;
        # no author step can dispatch while the UI is paused.
        assert len(calls) == 1
        await page.locator("#pause").click()
        await expect(page.locator("#overall-state")).to_have_text("Completed with limitations")
        assert len(calls) == 2  # one compiler operation, one injected author pass
        assert await page.locator("#report-sections section").count() == 1
        evidence = page.get_by_role("button", name="Evidence:").first
        await evidence.focus(); await page.keyboard.press("Enter")
        await page.locator("#activity-drawer button").last.focus()
        await page.keyboard.press("Tab")
        assert await page.locator("#activity-drawer").evaluate("el => el.contains(document.activeElement)")
        await page.keyboard.press("Escape")
        assert await evidence.evaluate("el => el === document.activeElement")
        # Request a new task with a different name. Replay refuses the mismatched
        # query: deliberate execution failure, not missing/zero facts.
        await page.locator("#brief").fill("Injected scope change with a failing independent query")
        async with page.expect_response(lambda r: r.url.endswith("/messages")):
            await page.locator("#brief").press("Enter")
        await expect(page.locator("#plan-tasks")).to_contain_text("Unresolved Person")
        await expect(page.locator("#overall-state")).to_have_text("Completed with limitations")
        await page.locator("#activity").click()
        await expect(page.locator("#activity-content")).to_contain_text("could not be safely established")
        await page.keyboard.press("Escape")
        assert await page.locator("#report-sections section").count() >= 1
        assert await page.locator("#report-sections").get_by_role("button", name="Evidence:").count() > 0
        # User messages are server replayed once, not locally doubled.
        texts = await page.locator(".message").all_text_contents()
        assert sum("Injected UI control: investigate sponsorship" in text for text in texts) == 1
        await browser.close()
        return {"kind": "injected model + exact compiler-response replay", "planInViewportBeforeDispatch": True,
                "pauseResume": True, "modalTabEscapeFocus": True, "independentFailureRetainsReport": True,
                "singleUserMessageEcho": True, "humanAcceptance": "not assessed"}


def main():
    record = next(r for r in load_bundle()["live"] if r["question"] == SPONSOR and r["controlledProposal"] is None)
    models = lambda: InjectedModel([plan([sponsor_task()]), plan([sponsor_task() | {"id": "different", "member": "Unresolved Person"}])])
    app = create_app(planner_factory=models, client_factory=lambda: Replay(record["queries"]), reporting_date=date(2026, 11, 12))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = Thread(target=server.run, daemon=True); thread.start()
    try:
        result = asyncio.run(verify(f"http://127.0.0.1:{port}"))
        output = Path("/tmp/oireachtasontology/research-v05-ui-control.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()
