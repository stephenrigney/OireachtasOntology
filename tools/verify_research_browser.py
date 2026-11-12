"""Executable Chromium checks for Phase 1. Starts only disposable app servers.

uv sync --extra test --extra nlq --extra browser-test
.venv/bin/python -m playwright install chromium
.venv/bin/python tools/verify_research_browser.py
# Also exercise a separately launched, genuinely configured LLM/Fuseki service:
.venv/bin/python tools/verify_research_browser.py --live-url http://127.0.0.1:8010
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Event
from time import monotonic
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path("/tmp/oireachtasontology/parliamentary-research-phase-1")


def start_server(failure=False):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=f"{ROOT}:{ROOT / 'tests'}", RESEARCH_BROWSER_FAILURE="1" if failure else "")
    log = (SCRATCH / ("browser-failure-server.log" if failure else "browser-server.log")).open("w")
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "test_research_workspace:create_browser_app",
                                "--factory", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=log)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("Browser test server failed; inspect disposable log.")
        try:
            if urlopen(url, timeout=1).status == 200:
                return process, log, url
        except OSError:
            Event().wait(.1)
    process.terminate()
    raise RuntimeError("Browser test server did not become ready.")


def scenario(browser, url, *, live=False, failure=False):
    """Full usable workspace journey, including export and evidence focus."""
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page = context.new_page()
    errors, dispatch_states, progress = [], [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda e: errors.append(e.text) if e.type == "error" else None)
    page.goto(url)
    expect(page.get_by_role("button", name="Start research")).to_be_disabled()
    assert page.locator(".report-pane").bounding_box()["width"] > page.locator(".conversation").bounding_box()["width"]
    page.locator("#example").click()
    def before_step(route):
        assert page.locator("#plan-card").is_visible(), "Factual dispatch before visible plan"
        if not dispatch_states:
            card = page.locator("#plan-card h2").bounding_box()
            log = page.locator("#conversation-log").bounding_box()
            assert log["y"] <= card["y"] and card["y"] + card["height"] <= log["y"] + log["height"], "Plan heading was not in the visible conversation viewport"
            first_task = page.locator("#plan-tasks li").first.bounding_box()
            assert log["y"] <= first_task["y"] and first_task["y"] + first_task["height"] <= log["y"] + log["height"], "Initial plan task was not visibly published"
        dispatch_states.append(page.locator("#plan-card").inner_text())
        if len(dispatch_states) == 3:
            page.locator("#section-party-0 td button").first.focus()
        elif len(dispatch_states) == 4:
            assert page.locator("#section-party-0 td button").first.evaluate("el => el === document.activeElement"), "Progressive count update detached the focused Member table control"
        if len(dispatch_states) == 1:
            page.screenshot(path=str(SCRATCH / ("live-plan.png" if live else "desktop-plan.png")), full_page=True)
        route.continue_()
    page.route("**/runs/*/step", before_step)
    def record(response):
        if response.url.endswith("/step") and response.status == 200:
            progress.append(response.json())
    page.on("response", record)
    page.locator("#brief").press("Shift+Enter")
    assert "\n" in page.locator("#brief").input_value()
    page.locator("#brief").press("Enter")
    expect(page.locator("#plan-card")).to_be_visible(timeout=90000)
    page.locator("#pause").click()
    expect(page.locator("#overall-state")).to_contain_text("Paused")
    page.locator("#pause").click()
    expect(page.locator("#report-status")).to_contain_text("Completed with limitations", timeout=180000)
    assert len(dispatch_states) == 6
    state = progress[-1]
    assert any(s["state"] == "Populating" for p in progress for s in p["sections"])
    assert progress[0]["sections"][0]["state"] == "Validated"
    expect(page.locator("#section-party-0 table")).to_be_visible()
    if failure:
        expect(page.locator("#section-party-1")).to_contain_text("Incomplete")
        expect(page.locator("#section-comparison")).to_contain_text("Blocked")
    else:
        expect(page.locator("#section-party-1 table")).to_be_visible()
        expect(page.locator("#section-comparison")).to_contain_text("deterministic comparison")
    assert "freshness" in page.locator("#limitations").inner_text()
    # Actual evidence retained by server, count/list identity agreement.
    evidence = []
    for eid in state["evidence"]:
        evidence.append(context.request.get(f"{url}/runs/{state['id']}/evidence/{eid}").json())
    for e in evidence:
        if e["outcome"] == "answer" and "members" in e["data"]:
            assert e["data"]["value"] == len({m["memberIri"] for m in e["data"]["members"]})
            assert all(w["queryRefs"] for m in e["data"]["members"] for w in m["witnesses"])
    # Keyboard opens drawer, focus is trapped; Escape restores opener.
    opener = page.locator("#activity")
    opener.focus(); page.keyboard.press("Enter")
    expect(page.locator("#activity-drawer")).to_be_visible()
    assert page.locator("#close-activity").evaluate("el => el === document.activeElement")
    page.keyboard.press("Shift+Tab")
    assert page.locator("#activity-drawer").evaluate("el => el.contains(document.activeElement)")
    page.keyboard.press("Escape")
    expect(opener).to_be_focused()
    first_ref = page.locator("#section-party-0 .evidence-link").first
    first_ref.click()
    expect(page.locator("#activity-content")).to_contain_text("Validation accepted: yes")
    page.locator("#activity-content summary").click()
    expect(page.locator("#activity-content pre").last).to_contain_text("queryRefs")
    page.keyboard.press("Escape")
    expect(first_ref).to_be_focused()
    # Retain report reading position through unrelated conversation messages.
    page.locator("#report-scroll").evaluate("el => el.scrollTop = 200")
    old_scroll = page.locator("#report-scroll").evaluate("el => el.scrollTop")
    assert old_scroll > 0, "Report must scroll independently inside the workspace"
    assert page.locator(".workspace").bounding_box()["height"] <= 1000
    page.locator("#brief").fill("Make this report longer")
    page.locator("#brief").press("Enter")
    assert page.locator("#report-scroll").evaluate("el => el.scrollTop") == old_scroll
    expect(page.locator("#conversation-log")).to_contain_text("Phase 2")
    with page.expect_download() as download:
        page.locator("#export").click()
    output = SCRATCH / ("live-report.md" if live else "failed-report.md" if failure else "browser-report.md")
    download.value.save_as(output)
    markdown = output.read_text()
    assert "uncertified" in markdown and "freshness" in markdown and "```json" in markdown
    if failure:
        assert "Incomplete" in markdown and "Execution failed" in markdown
        assert "Report state: Incomplete" in markdown
    else:
        assert "Report state: Qualified local findings" in markdown
    # Responsive layouts, keyboard mobile navigation, no page-level overflow.
    for width in (1440, 1024, 768, 390, 320):
        page.set_viewport_size({"width": width, "height": 1000})
        if width < 768:
            page.locator("#show-report").focus(); page.keyboard.press("Enter")
            expect(page.locator(".report-pane")).to_be_visible()
            expect(page.locator(".conversation")).not_to_be_visible()
            region = page.locator("#section-party-0 .table-scroll")
            region.evaluate("el => el.scrollLeft = 100")
            assert region.evaluate("el => el.scrollWidth <= el.clientWidth || el.scrollLeft > 0"), "Wide Member table is not inspectable"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Page overflow at {width}"
        page.locator("#report-scroll").evaluate("el => el.scrollTop = 0")
        page.screenshot(path=str(SCRATCH / f"{'live' if live else 'failure' if failure else 'workspace'}-{width}.png"), full_page=True)
        page.locator("#activity").focus(); page.keyboard.press("Enter")
        expect(page.locator("#activity-drawer")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#activity")).to_be_focused()
        if width < 768:
            page.locator("#show-conversation").click()
            expect(page.locator("#brief")).to_be_visible()
    # Zoom-equivalent reflow + enlarged text at desktop and 320px.
    page.set_viewport_size({"width": 320, "height": 800})
    page.evaluate("document.documentElement.style.fontSize = '32px'")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.evaluate("document.documentElement.style.fontSize = '16px'")
    page.set_viewport_size({"width": 320, "height": 250})  # 1280×1000 at 400% zoom-equivalent reflow
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#activity").click()
    expect(page.locator("#activity-drawer")).to_be_visible()
    page.keyboard.press("Escape")
    assert not errors, errors
    result = {"live": live, "failure": failure, "reportingDate": state["reportingDate"], "metrics": state["metrics"],
              "taskStates": [t["state"] for t in state["tasks"]], "operationCount": len(evidence),
              "actualQueryCount": sum(len(e["execution"]["queries"]) for e in evidence),
              "counts": {e["resolvedScope"]["party"]["label"]: e["data"]["value"] for e in evidence
                         if e["outcome"] == "answer" and e["request"]["operation"]["operation"].endswith("count.current")},
              "planBeforeDispatch": True, "progressive": True, "widths": [1440, 1024, 768, 390, 320], "consoleErrors": errors}
    result["zoomEquivalent"] = {"textPercent": 200, "reflowPercent": 400}
    result["keyboardFocusPreservedAcrossCountUpdate"] = True
    (SCRATCH / ("live-browser.json" if live else "failure-browser.json" if failure else "browser.json")).write_text(json.dumps(result, indent=2))
    context.close()
    return result


def negative_ui(browser, url):
    context = browser.new_context(viewport={"width": 390, "height": 900})
    page = context.new_page()
    page.goto(url)
    # Unsupported residual condition remains visible; only independent term runs.
    page.locator("#brief").fill("Compare Fine Gael and Fianna Fáil in the current Dáil including committee memberships.")
    page.locator("#brief").press("Enter")
    expect(page.locator("#report-status")).to_contain_text("Completed with limitations", timeout=30000)
    expect(page.locator("#plan-card")).to_contain_text("Unsupported")
    page.locator("#show-report").click()
    expect(page.locator("#unanswered")).to_contain_text("committee")
    assert page.locator("table").count() == 0
    context.close()
    context = browser.new_context(viewport={"width": 320, "height": 900})
    page = context.new_page(); page.goto(url)
    page.locator("#brief").fill("Report Fine Gael and Fianna Fáil membership in the Dáil")
    page.locator("#brief").press("Enter")
    expect(page.locator("#plan-card")).to_contain_text("Clarification required", timeout=30000)
    assert page.locator("#section-term").inner_text().find("Blocked") >= 0
    context.close()
    # Submission failure retains the exact composer message.
    context = browser.new_context(); page = context.new_page(); page.goto(url)
    page.route("**/runs", lambda route: route.fulfill(status=503, body="Unavailable"))
    page.locator("#brief").fill("My original research message")
    page.locator("#brief").press("Enter")
    expect(page.locator("#submission-error")).to_contain_text("preserved")
    assert page.locator("#brief").input_value() == "My original research message"
    context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-url")
    args = parser.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    processes = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for failure in (False, True):
                process, log, url = start_server(failure)
                processes.append((process, log))
                print(json.dumps(scenario(browser, url, failure=failure), indent=2))
                if not failure:
                    negative_ui(browser, url)
            if args.live_url:
                print(json.dumps(scenario(browser, args.live_url.rstrip("/"), live=True), indent=2))
            browser.close()
    finally:
        for process, log in processes:
            process.terminate()
            process.wait(timeout=15)
            log.close()


if __name__ == "__main__":
    main()
