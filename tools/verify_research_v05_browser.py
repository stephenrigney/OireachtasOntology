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


async def verify(url, output, resume=False):
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
                await page.screenshot(path=str(output / ("resume-plan-before-dispatch.png" if resume else "r1-plan-before-dispatch.png")))
            await route.continue_()

        await page.route("**/runs/*/step", before_step)

        async def submit(text):
            await page.locator("#brief").fill(text)
            async with page.expect_response(lambda r: r.request.method == "POST" and (r.url.endswith("/runs") or r.url.endswith("/messages"))) as pending:
                await page.locator("#brief").press("Enter")
            response = await pending.value
            assert response.ok, await response.text()
            state = await response.json()
            if state["status"] == "Research planning interrupted":
                archive_response = await page.request.get(f"{url}/runs/{state['id']}/archive")
                (output / "planning-interrupted.json").write_text(json.dumps(await archive_response.json(), ensure_ascii=False, indent=2))
                raise AssertionError("Configured planning interrupted; retained archive, no research success claimed")
            await expect(page.locator("#plan-interpretation")).to_have_text(state["interpretation"])
            await expect(page.locator("#overall-state")).to_have_text(re.compile(r"Completed with limitations|Needs clarification"), timeout=900000)
            archive_response = await page.request.get(f"{url}/runs/{state['id']}/archive")
            return await archive_response.json()

        async def retain(label, archive):
            (output / f"{label}.json").write_text(json.dumps(archive, ensure_ascii=False, indent=2))
            report = await page.request.get(f"{url}/runs/{archive['state']['id']}/report.md")
            (output / f"{label}.md").write_text(await report.text())

        async def restore(label):
            # Verifier-only resumption of exact generated state, not a saved-report
            # application feature, canned research or another factual query.
            archive = json.loads((output / f"{label}.json").read_text())
            await page.evaluate("state => { run = state; render(); }", archive["state"])
            return archive

        await page.goto(url)
        r1 = await restore("r1-initial") if resume else await submit(R1)
        if not resume:
            await retain("r1-initial", r1)
        assert r1["state"]["facts"] and r1["state"]["sections"], r1["state"]
        assert {e["request"]["operation"]["operation"] for e in r1["evidence"].values()} == {"sponsorship", "lifecycle"}
        assert any(a["level"] == 3 for a in r1["state"]["assertions"].values())
        displayed = {ref for s in r1["state"]["sections"] for ref in s["factRefs"]}
        displayed.update(ref for s in r1["state"]["sections"] for t in s.get("tables", []) for row in t["rows"] for ref in row["assertionRefs"])
        tables = [t for s in r1["state"]["sections"] for t in s.get("tables", []) if t["specification"]["kind"] == "bills"]
        sponsors = {ref for ref, a in r1["state"]["facts"].items() if a["proposition"][0] == "sponsorship"}
        assert sponsors == {ref for t in tables for ref in t["specification"]["factRefs"]}, "Compact table must retain all sponsorship findings"
        assert r1["state"]["unanswered"], "Final-outcome research must remain explicitly unanswered, not disappear into a generic limitation"
        assert any(r1["state"]["facts"][ref]["proposition"][0] == "recorded_status" for ref in displayed), "Completed briefing must show lifecycle evidence, not only interim sponsorship"
        assert any(a["level"] == 3 and any(r1["state"]["facts"][ref]["proposition"][0] in {"recorded_status", "recorded_activity"} for ref in a["factRefs"]) for a in r1["state"]["assertions"].values()), "LLM must explain retrieved progress evidence"
        await page.screenshot(path=str(output / "r1-desktop.png"))
        await page.locator(".table-scroll").first.scroll_into_view_if_needed()
        await page.screenshot(path=str(output / "r1-bill-table.png"))
        row_indicator = page.get_by_role("button", name="Evidence: individual recorded facts").first
        await row_indicator.focus(); await page.keyboard.press("Enter")
        await expect(page.locator("#activity-content")).to_contain_text("All accepted facts for this row")
        await page.screenshot(path=str(output / "bill-row-evidence.png"))
        await page.locator("#activity-content button").nth(1).click()
        await expect(page.locator("#activity-content")).to_contain_text("Reasoning")
        await page.keyboard.press("Escape")
        assert await row_indicator.evaluate("el => el === document.activeElement")
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
        revision = await restore("r1-revision") if resume else await submit("Please make the overview shorter and explain why the distinction between recorded status and final outcome matters. Keep the Bill findings and evidence.")
        if not resume:
            await retain("r1-revision", revision)
        assert prior_evidence == revision["evidence"], "Editorial revision must not rerun compiler facts"
        assert r1["state"]["facts"] == revision["state"]["facts"]
        assert r1["state"]["sections"] != revision["state"]["sections"] or r1["state"]["assertions"] != revision["state"]["assertions"]
        overview = r1["state"]["sections"][0]
        revised_overview = next(s for s in revision["state"]["sections"] if s["id"] == overview["id"])
        def prose_words(archive, section):
            return len(" ".join(archive["state"]["assertions"][ref]["text"] for ref in section["assertionRefs"]).split())
        initial_words, revised_words = prose_words(r1, overview), prose_words(revision, revised_overview)
        assert revised_words <= initial_words * .7, ("Overview must materially shorten", initial_words, revised_words)
        await expect(page.locator("#section-" + overview["id"])).to_contain_text(revision["state"]["assertions"][revised_overview["assertionRefs"][0]]["text"])
        before_tables = [t for s in r1["state"]["sections"] for t in s.get("tables", [])]
        assert before_tables == [t for s in revision["state"]["sections"] for t in s.get("tables", [])]
        assert all("editorial" not in u["reason"].lower() for u in revision["state"]["unanswered"])
        assert revision["state"]["unanswered"] == r1["state"]["unanswered"], "Editorial changes cannot lose or duplicate outstanding research"
        await page.screenshot(path=str(output / "r1-revised.png"))
        evidence_discussion = await restore("r1-evidence-discussion") if resume else await submit("Show me the evidence for the Bill with a lapsed event and a later recorded stage. What can and cannot be concluded?")
        if not resume:
            await retain("r1-evidence-discussion", evidence_discussion)

        layouts = []
        for width in (1440, 1024, 768, 390, 320):
            await page.set_viewport_size({"width": width, "height": 1000})
            if width < 768:
                await page.locator("#show-report").click()
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"Overflow at {width}"
            if width < 768:
                region = page.locator(".table-scroll").first
                await region.scroll_into_view_if_needed(); await region.focus()
                for _ in range(12):
                    await page.keyboard.press("ArrowRight")
                scroll_left = await region.evaluate("el => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(el.scrollLeft))))")
                assert scroll_left > 0, "Keyboard must scroll the factual table horizontally"
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
        assert "| Bill | Recorded sponsorship" in exported
        assert all(ref in exported for ref in revision["state"]["facts"])

        await page.set_viewport_size({"width": 1440, "height": 1000})
        # User-authorised material focus change in the SAME report/session.
        r3 = await submit(R3 + " Add this as a separate career section and retain the earlier Bill research.")
        await retain("r3-same-session", r3)
        assert set(prior_evidence) <= set(r3["evidence"])
        before_sections = {s["id"]: s for s in evidence_discussion["state"]["sections"]}
        after_sections = {s["id"]: s for s in r3["state"]["sections"]}
        assert all(after_sections[key] == value for key, value in before_sections.items()), "New career research must not rewrite unrelated Bill sections"
        assert all(u in r3["state"]["unanswered"] for u in evidence_discussion["state"]["unanswered"]), "New career research must preserve earlier substantive questions"
        assert any(e["request"]["operation"]["operation"] == "career" and e["outcome"] == "answer" for e in r3["evidence"].values())
        await page.locator("#report-sections section").last.scroll_into_view_if_needed()
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
        summary.update(initialOverviewWords=initial_words, revisedOverviewWords=revised_words, allBillRowsPresent=True,
                       allFactsExported=True, keyboardHorizontalTableScroll=True, rowAndIndividualEvidence=True,
                       resumedBrowserVerification=resume)
        (output / "browser-summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", type=Path, default=Path("/tmp/oireachtasontology/research-v05"))
    parser.add_argument("--resume", action="store_true", help="Reuse exact retained R1 snapshots and continue the same live session after a verifier interruption")
    args = parser.parse_args()
    asyncio.run(verify(args.url.rstrip("/"), args.output, args.resume))
