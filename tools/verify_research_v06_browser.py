"""v0.6 configured model/Fuseki browser observation; no canned research output.

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


def predicate(fact):
    p = fact["proposition"]
    return p["predicate"] if isinstance(p, dict) else p[0]


async def opening_checks(page, output):
    posts = []
    page.on("request", lambda r: posts.append(r.url) if r.method == "POST" else None)
    await expect(page.get_by_role("heading", name="What would you like to find out?", exact=True)).to_be_visible()
    assert await page.locator("h1:visible").count() == 1
    assert not await page.locator("#report").is_visible()
    assert not await page.locator("#workspace-controls").is_visible()
    assert not await page.locator(".mobile-nav, .conversation, .report-pane").count()
    text = await page.locator("body").inner_text()
    for rejected in ("Living Report", "A clear brief", "Your report will take shape", "Validated findings", "freshness", "Parliamentary research note"):
        assert rejected.lower() not in text.lower(), rejected
    await expect(page.locator("#submit")).to_be_disabled()
    for width in (1440, 1024, 768, 390, 320):
        await page.set_viewport_size({"width": width, "height": 1000})
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), width
        box = await page.locator("#start-canvas").bounding_box()
        assert abs(box["x"] + box["width"] / 2 - width / 2) <= 1
        if width == 1440:
            assert 680 <= box["width"] <= 760
        await expect(page.locator("#brief")).to_be_in_viewport()
        await expect(page.locator("#submit")).to_be_in_viewport()
        await page.screenshot(path=str(output / f"opening-{width}.png"))
    await page.evaluate("document.documentElement.style.fontSize = '32px'")
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    await page.screenshot(path=str(output / "opening-text-200.png"), full_page=True)
    await page.evaluate("document.documentElement.style.fontSize = ''")
    await page.set_viewport_size({"width": 320, "height": 250})
    await page.locator("#submit").scroll_into_view_if_needed()
    assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    await page.screenshot(path=str(output / "opening-reflow-400.png"))
    await page.set_viewport_size({"width": 1440, "height": 1000})
    await page.locator("#example").click()
    assert await page.locator("#brief").input_value() == await page.locator("#example").inner_text()
    assert not posts, "Selecting an example must not dispatch research"
    await page.locator("#brief").press("End")
    await page.locator("#brief").press("Enter")
    await page.locator("#brief").press("A")
    assert "\n" in await page.locator("#brief").input_value() and not posts
    await page.locator("#brief").fill("   \n  ")
    await expect(page.locator("#submit")).to_be_disabled()
    await page.locator("#brief").fill("")
    return {"exampleWithoutSubmission": True, "enterNewline": True, "openingWidths": [1440, 1024, 768, 390, 320]}


async def verify(url, output, resume=False):
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        page.set_default_timeout(240000)
        errors, progressive = [], []
        prior_observations = output / "plan-dispatch-observations.json"
        dispatches = json.loads(prior_observations.read_text()) if resume and prior_observations.exists() else []
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def before_step(route):
            visible = await page.locator("#plan-card").is_visible()
            assert visible, "Plan must be visible before any step dispatch"
            if not dispatches:
                await expect(page.locator("#plan-interpretation")).to_be_in_viewport()
                await expect(page.locator("#plan-tasks li").first).to_be_in_viewport()
                await expect(page.locator("#original-brief")).to_have_text(R1)
                await page.screenshot(path=str(output / ("resume-plan-before-dispatch.png" if resume else "r1-plan-before-dispatch.png")))
            if await page.locator("#report").is_visible():
                progressive.append({"sections": await page.locator("#report-sections > section").count(),
                                    "focus": await page.evaluate("document.activeElement.id"),
                                    "report": await page.locator("#report-heading").inner_text()})
            dispatches.append({"planVisible": visible, "planOpen": await page.locator("#plan-disclosure").evaluate("el => el.open"),
                               "atBrowserDispatch": await page.evaluate("Date.now()"),
                               "interpretation": await page.locator("#plan-interpretation").text_content(),
                               "tasks": await page.locator("#plan-tasks").text_content()})
            if len(dispatches) == 1 and not resume:
                assert dispatches[0]["planOpen"], "Initial plan must be expanded before factual execution"
            (output / "plan-dispatch-observations.json").write_text(json.dumps(dispatches, ensure_ascii=False, indent=2))
            await route.continue_()

        await page.route("**/runs/*/step", before_step)

        async def submit(text):
            await page.locator("#brief").fill(text)
            async with page.expect_response(lambda r: r.request.method == "POST" and (r.url.endswith("/runs") or r.url.endswith("/messages"))) as pending:
                await page.locator("#brief").press("Control+Enter")
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
            await page.evaluate("state => { run = state; sectionContext = null; render(); }", archive["state"])
            return archive

        await page.goto(url)
        opening = await opening_checks(page, output)
        r1 = await restore("r1-initial") if resume else await submit(R1)
        if not resume:
            await retain("r1-initial", r1)
        assert r1["state"]["facts"] and r1["state"]["sections"], r1["state"]
        assert {e["request"]["operation"]["operation"] for e in r1["evidence"].values()} == {"sponsorship", "lifecycle"}
        assert any(a["level"] == 3 for a in r1["state"]["assertions"].values())
        displayed = {ref for s in r1["state"]["sections"] for ref in s["factRefs"]}
        displayed.update(ref for s in r1["state"]["sections"] for t in s.get("tables", []) for row in t["rows"] for ref in row["assertionRefs"])
        tables = [t for s in r1["state"]["sections"] for t in s.get("tables", []) if t["specification"]["kind"] == "bills"]
        sponsors = {ref for ref, a in r1["state"]["facts"].items() if predicate(a) == "sponsorship"}
        assert sponsors == {ref for t in tables for ref in t["specification"]["factRefs"]}, "Compact table must retain all sponsorship findings"
        assert r1["state"]["unanswered"], "Final-outcome research must remain explicitly unanswered, not disappear into a generic limitation"
        assert any(predicate(r1["state"]["facts"][ref]) == "recorded_status" for ref in displayed), "Completed briefing must show lifecycle evidence, not only interim sponsorship"
        assert any(a["level"] == 3 and any(predicate(r1["state"]["facts"][ref]) in {"recorded_status", "recorded_activity"} for ref in a["factRefs"]) for a in r1["state"]["assertions"].values()), "LLM must explain retrieved progress evidence"
        if not resume:
            assert progressive, "Report must appear before all research steps finish"
            assert all(p["focus"] == "plan-summary" for p in progressive), "Progressive findings must not steal initial focus"
            (output / "progressive-observations.json").write_text(json.dumps(progressive, ensure_ascii=False, indent=2))
        # Collapse only through an explicit user action: automatic findings never
        # close a plan the researcher may still be reading.
        await page.locator("#plan-summary").click()
        await page.locator("#original-question summary").click()
        await page.locator("#report").scroll_into_view_if_needed()
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
        indicator = page.get_by_role("button", name=re.compile(r"Evidence: (?!individual)")).first
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
        overview = r1["state"]["sections"][0]
        # Section context is carried separately; no need to copy report prose.
        await page.locator("#section-" + overview["id"]).get_by_role("button", name="Refine this section").click()
        await expect(page.locator("#brief")).to_be_focused()
        await expect(page.locator("#context-label")).to_contain_text(overview["title"])
        await page.screenshot(path=str(output / "follow-up-composer.png"))
        revision = await restore("r1-revision") if resume else await submit("Please make this section’s explanatory prose much shorter: at most 80 words in total across its narrative paragraphs. Explain why recorded status is not final outcome. Keep every factual table, Bill finding and evidence reference.")
        if not resume:
            await retain("r1-revision", revision)
        assert prior_evidence == revision["evidence"], "Editorial revision must not rerun compiler facts"
        assert r1["state"]["facts"] == revision["state"]["facts"]
        assert r1["state"]["sections"] != revision["state"]["sections"] or r1["state"]["assertions"] != revision["state"]["assertions"]
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

        await page.locator("#conversation-history summary").click()
        expected_messages = evidence_discussion["state"]["messages"]
        assert await page.locator("#conversation-log .message > div").all_text_contents() == [m["text"] for m in expected_messages]
        await expect(page.locator("#conversation-history summary")).to_be_focused()
        await page.screenshot(path=str(output / "conversation-history.png"))
        await page.locator("#conversation-history summary").click()
        await expect(page.locator("#conversation-history summary")).to_be_focused()

        layouts = []
        for width in (1440, 1024, 768, 390, 320):
            await page.set_viewport_size({"width": width, "height": 1000})
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"Overflow at {width}"
            region = page.locator(".table-scroll").first
            await region.scroll_into_view_if_needed(); await region.focus()
            if await region.evaluate("el => el.scrollWidth > el.clientWidth"):
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
        await page.locator("#reach-composer").click()
        await expect(page.locator("#brief")).to_be_focused()
        await page.locator("#brief").fill("Line one")
        await page.locator("#brief").press("Enter")
        await page.locator("#brief").press("L")
        assert "\n" in await page.locator("#brief").input_value()
        await page.locator("#brief").fill("")
        assert await page.locator("#submit").is_disabled()
        await page.screenshot(path=str(output / "follow-up-320.png"))
        await page.set_viewport_size({"width": 320, "height": 250})
        await page.locator("#brief").focus()
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        await page.screenshot(path=str(output / "report-reflow-400.png"))
        async with page.expect_download() as download:
            await page.locator("#export").click()
        await (await download.value).save_as(str(output / "browser-export.md"))
        exported = (output / "browser-export.md").read_text()
        assert "Draft — for review" in exported and "Provisional interpretation" in exported and "freshness" in exported
        assert "| Bill | Recorded sponsorship" in exported
        assert all(ref in exported for ref in revision["state"]["facts"])
        await page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        await page.locator("#copy").click()
        await expect(page.locator("#announcement")).to_have_text("Qualified report and evidence copied as Markdown.")
        assert await page.evaluate("navigator.clipboard.readText()") == exported
        await expect(page.locator("#copy")).to_have_text("Copy Markdown")
        await page.emulate_media(reduced_motion="reduce")
        assert await page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")

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
        (output / "plan-dispatch-observations.json").write_text(json.dumps(dispatches, ensure_ascii=False, indent=2))
        summary = {"kind": "actual configured model and read-only Fuseki", "planVisibleBeforeDispatch": bool(dispatches),
                   "stepDispatches": len(dispatches), "responsiveWidths": layouts, "keyboardEvidenceEscapeFocus": True,
                   "editorialEvidencePreserved": True, "sameSessionSecondaryDomain": True,
                    "markdownExportQualified": True, "javascriptErrors": errors, "humanAcceptance": "pending"}
        summary.update(initialOverviewWords=initial_words, revisedOverviewWords=revised_words, allBillRowsPresent=True,
                       allFactsExported=True, keyboardHorizontalTableScroll=True, rowAndIndividualEvidence=True,
                        resumedBrowserVerification=resume)
        summary.update(opening, progressiveReportBeforeCompletion=bool(progressive) if not resume else "Passed in the original live R1 leg before verifier interruption; see original-leg log",
                       progressiveFocusPreserved=True,
                       sectionContextRevision=True, exactConversationHistory=True, textSizePercent=200, zoomEquivalentPercent=400,
                       copyMarkdown=True, reducedMotion=True)
        if resume:
            summary["resumptionContext"] = "R1/revision/discussion snapshots are exact rendering of the same original model/Fuseki run; R3 continues that live server session. Not another R1 factual trial."
        (output / "browser-summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8010")
    parser.add_argument("--output", type=Path, default=Path("/tmp/oireachtasontology/research-v06"))
    parser.add_argument("--resume", action="store_true", help="Reuse exact retained R1 snapshots and continue the same live session after a verifier interruption")
    args = parser.parse_args()
    asyncio.run(verify(args.url.rstrip("/"), args.output, args.resume))
