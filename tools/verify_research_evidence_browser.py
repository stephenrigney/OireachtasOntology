"""Small fresh configured-model/Fuseki browser observation, never canned output."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import socket
import sys
from pathlib import Path
from threading import Event, Thread

import uvicorn
from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from poc.nlq.research_app import create_app

QUESTION = "Could you trace Stephen Donnelly's recorded political party affiliations, showing the membership dates where available?"
FOLLOWUP = "Also tell me which constituency Mary Lou McDonald represents now, keeping Stephen Donnelly's party history unchanged."


async def verify(url, output):
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1100})
        page.set_default_timeout(240000)
        errors, dispatches = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def dispatch(route):
            assert await page.locator("#plan-card").is_visible()
            dispatches.append({"planVisibleBeforeDispatch": True,
                               "plan": await page.locator("#plan-tasks").inner_text()})
            if len(dispatches) == 1:
                await page.screenshot(path=str(output / "plan-before-execution.png"), full_page=True)
            await route.continue_()

        await page.route("**/runs/*/step", dispatch)
        await page.goto(url)

        async def submit(text, key):
            await page.locator("#brief").fill(text)
            async with page.expect_response(lambda r: r.request.method == "POST" and
                                            (r.url.endswith("/runs") or r.url.endswith("/messages"))) as pending:
                await page.locator("#brief").press("Control+Enter")
            response = await pending.value
            assert response.ok, await response.text()
            prepared = await response.json()
            await expect(page.locator("#overall-state")).to_have_text(
                re.compile(r"Findings available.*|Question not answered|Needs clarification|Records found.*|Research interrupted|Research planning interrupted"), timeout=900000)
            archive = await (await page.request.get(f"{url}/runs/{prepared['id']}/archive")).json()
            (output / f"{key}.json").write_text(json.dumps(archive, ensure_ascii=False, indent=2))
            report = await page.request.get(f"{url}/runs/{prepared['id']}/report.md")
            (output / f"{key}.md").write_text(await report.text())
            await page.screenshot(path=str(output / f"{key}-report.png"), full_page=True)
            return archive

        first = await submit(QUESTION, "party-history")
        assert first["state"]["facts"] and first["state"]["sections"], first["state"]["status"]
        assert all(f["proposition"]["predicate"] == "party_membership_episode" for f in first["state"]["facts"].values())
        await page.locator("#report-sections table button").first.click()
        await page.locator("#activity-content button.evidence-link").first.click()
        await page.get_by_text("Exact accepted proposition, intervals and witnesses", exact=True).click()
        await page.screenshot(path=str(output / "exact-episode-inspection.png"), full_page=True)
        await page.locator("#activity-content button").filter(has_text=re.compile(r"^Evidence 1")).first.click()
        await expect(page.locator("#activity-content")).to_contain_text("Validation accepted: yes")
        await page.screenshot(path=str(output / "query-evidence-inspection.png"), full_page=True)
        await page.locator("#close-activity").click()
        second = await submit(FOLLOWUP, "current-representation-added")
        assert all(second["state"]["facts"][ref] == fact for ref, fact in first["state"]["facts"].items())
        new = [f for ref, f in second["state"]["facts"].items() if ref not in first["state"]["facts"]]
        assert new and all(f["proposition"]["predicate"] == "representation" for f in new)
        assert all(f["proposition"]["scope"]["meaning"] == "membership_contains_as_of" for f in new)
        old = {s["id"]: s for s in first["state"]["sections"]}
        assert all({k: v for k, v in s.items() if k != "state"} ==
                   {k: v for k, v in old[s["id"]].items() if k != "state"}
                   for s in second["state"]["sections"] if s["id"] in old)
        await page.set_viewport_size({"width": 390, "height": 1000})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        await page.screenshot(path=str(output / "additive-report-390.png"), full_page=True)
        assert not errors, errors
        await browser.close()
        return {"kind": "fresh configured-model and read-only Fuseki browser execution", "question": QUESTION,
                "followup": FOLLOWUP, "initialFacts": len(first["state"]["facts"]), "addedFacts": len(new),
                "earlierFactsAndSectionsPreserved": True, "dispatches": dispatches,
                "javascriptErrors": errors, "humanAcceptance": "not assessed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    ready = Event()

    class Server(uvicorn.Server):
        async def startup(self, sockets=None):
            await super().startup(sockets)
            ready.set()

    server = Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error"))
    thread = Thread(target=server.run, daemon=True)
    thread.start()
    try:
        if not ready.wait(10):
            raise RuntimeError("Local observation server did not start.")
        result = asyncio.run(verify(f"http://127.0.0.1:{port}", args.output))
        (args.output / "browser-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()
