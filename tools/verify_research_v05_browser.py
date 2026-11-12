"""Configured model/Fuseki browser observation; no canned research output.

Run a single-worker local app first. Artefacts contain parliamentary source data,
model proposals and drafts, never credentials. This is not human acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright, expect

R1 = "Prepare a briefing on the Bills sponsored by Malcolm Byrne. What progress have they made, and what happened to them?"
R3 = "Prepare a background briefing on Mary Lou McDonald's parliamentary career, including constituencies represented and parliamentary roles."


async def verify(url, output):
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page.set_default_timeout(240000)
        errors, dispatches = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def before_step(route):
            visible = await page.locator("#plan-card").is_visible()
            assert visible, "Plan must be visible before any step dispatch"
            dispatches.append({"planVisible": visible, "plan": await page.locator("#plan-card").inner_text()})
            if len(dispatches) == 1:
                await page.screenshot(path=str(output / "r1-plan-before-dispatch.png"))
            await route.continue_()

        await page.route("**/runs/*/step", before_step)

        async def submit(text):
            await page.locator("#brief").fill(text)
            async with page.expect_response(lambda r: r.request.method == "POST" and (r.url.endswith("/runs") or r.url.endswith("/messages"))) as pending:
                await page.locator("#brief").press("Enter")
            response = await pending.value
            assert response.ok, await response.text()
            state = await response.json()
            await expect(page.locator("#plan-interpretation")).to_have_text(state["interpretation"])
            await expect(page.locator("#overall-state")).to_have_text(re.compile(r"Completed with limitations|Needs clarification"), timeout=900000)
            archive_response = await page.request.get(f"{url}/runs/{state['id']}/archive")
            return await archive_response.json()

        async def retain(label, archive):
            (output / f"{label}.json").write_text(json.dumps(archive, ensure_ascii=False, indent=2))
            report = await page.request.get(f"{url}/runs/{archive['state']['id']}/report.md")
            (output / f"{label}.md").write_text(await report.text())

        await page.goto(url)
        r1 = await submit(R1)
        await retain("r1-initial", r1)
        assert r1["state"]["facts"] and r1["state"]["sections"], r1["state"]
        assert {e["request"]["operation"]["operation"] for e in r1["evidence"].values()} == {"sponsorship", "lifecycle"}
        assert any(a["level"] == 3 for a in r1["state"]["assertions"].values())
        displayed = {ref for s in r1["state"]["sections"] for ref in s["factRefs"]}
        assert any(r1["state"]["facts"][ref]["proposition"][0] == "recorded_status" for ref in displayed), "Completed briefing must show lifecycle evidence, not only interim sponsorship"
        assert any(a["level"] == 3 and any(r1["state"]["facts"][ref]["proposition"][0] in {"recorded_status", "recorded_activity"} for ref in a["factRefs"]) for a in r1["state"]["assertions"].values()), "LLM must explain retrieved progress evidence"
        await page.screenshot(path=str(output / "r1-desktop.png"))
        indicator = page.get_by_role("button", name="Evidence:").first
        await indicator.focus(); await page.keyboard.press("Enter")
        assert await page.locator("#activity-drawer").is_visible()
        assert "Reasoning" in await page.locator("#activity-content").inner_text()
        await page.locator("#activity-drawer button").last.focus()
        await page.keyboard.press("Tab")
        assert await page.locator("#activity-drawer").evaluate("el => el.contains(document.activeElement)"), "Focus must remain in the modal"
        await page.screenshot(path=str(output / "assertion-inspector.png"))
        await page.keyboard.press("Escape")
        assert await indicator.evaluate("el => el === document.activeElement")

        prior_evidence = r1["evidence"]
        revision = await submit("Please make the overview shorter and explain why the distinction between recorded status and final outcome matters. Keep the Bill findings and evidence.")
        await retain("r1-revision", revision)
        assert prior_evidence == revision["evidence"], "Editorial revision must not rerun compiler facts"
        assert r1["state"]["facts"] == revision["state"]["facts"]
        assert r1["state"]["sections"] != revision["state"]["sections"] or r1["state"]["assertions"] != revision["state"]["assertions"]
        await page.screenshot(path=str(output / "r1-revised.png"))
        evidence_discussion = await submit("Show me the evidence for the Bill with a lapsed event and a later recorded stage. What can and cannot be concluded?")
        await retain("r1-evidence-discussion", evidence_discussion)

        layouts = []
        for width in (1440, 1024, 768, 390, 320):
            await page.set_viewport_size({"width": width, "height": 1000})
            if width < 768:
                await page.locator("#show-report").click()
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"Overflow at {width}"
            await page.screenshot(path=str(output / f"layout-{width}.png"))
            layouts.append(width)
        # Text zoom plus narrow-width reflow are repeatable zoom-equivalent checks,
        # not a formal browser/assistive-technology conformance claim.
        await page.set_viewport_size({"width": 1024, "height": 1000})
        await page.evaluate("document.documentElement.style.fontSize = '32px'")
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        await page.screenshot(path=str(output / "text-zoom-200.png"))
        await page.evaluate("document.documentElement.style.fontSize = ''")
        await page.set_viewport_size({"width": 320, "height": 1000})
        await page.locator("#show-conversation").click()
        await page.locator("#brief").fill("Line one")
        await page.locator("#brief").press("Shift+Enter")
        await page.locator("#brief").press("L")
        assert "\n" in await page.locator("#brief").input_value()
        await page.locator("#brief").fill("")
        assert await page.locator("#submit").is_disabled()
        await page.locator("#show-report").click()
        async with page.expect_download() as download:
            await page.locator("#export").click()
        await (await download.value).save_as(str(output / "browser-export.md"))
        exported = (output / "browser-export.md").read_text()
        assert "Draft — for review" in exported and "Provisional interpretation" in exported and "freshness" in exported

        await page.set_viewport_size({"width": 1440, "height": 1000})
        # User-authorised material focus change in the SAME report/session.
        r3 = await submit(R3 + " Add this as a separate career section and retain the earlier Bill research.")
        await retain("r3-same-session", r3)
        assert set(prior_evidence) <= set(r3["evidence"])
        assert any(e["request"]["operation"]["operation"] == "career" and e["outcome"] == "answer" for e in r3["evidence"].values())
        await page.screenshot(path=str(output / "r3-career.png"))
        for label, brief in [
            ("r4-boundary", "Which members of the current Public Accounts Committee belong to Fine Gael? Explain what can be established."),
            ("r5-boundary", "Prepare a briefing on how housing was discussed in Dáil debates last year."),
        ]:
            # Separate fresh workspace; unsupported questions should not dispatch irrelevant tools.
            await page.goto(url)
            archive = await submit(brief)
            await retain(label, archive)
            assert not archive["evidence"], "No supported tool for these content/intersection questions"
        assert not errors, errors
        summary = {"kind": "actual configured model and read-only Fuseki", "planVisibleBeforeDispatch": bool(dispatches),
                   "stepDispatches": len(dispatches), "responsiveWidths": layouts, "keyboardEvidenceEscapeFocus": True,
                   "editorialEvidencePreserved": True, "sameSessionSecondaryDomain": True,
                   "markdownExportQualified": True, "javascriptErrors": errors, "humanAcceptance": "pending"}
        (output / "browser-summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", type=Path, default=Path("/tmp/oireachtasontology/research-v05"))
    args = parser.parse_args()
    asyncio.run(verify(args.url.rstrip("/"), args.output))
