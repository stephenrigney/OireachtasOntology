"""Optional real-browser checks; no live LLM or triple store is contacted.

Run with Playwright and its Chromium installed, for example:
uv run --locked --extra test --extra nlq --with playwright python -m pytest tests/test_nlq_explainer_browser.py
"""

import pytest

from test_nlq_explainer import emitted_history, render_outcome
from poc.nlq.composable_plan import PlanOutcome


@pytest.mark.parametrize("width", [1240, 390, 320])
def test_tabs_disclosures_focus_and_responsive_layout(monkeypatch, width):
    playwright = pytest.importorskip("playwright.sync_api")
    page_html = render_outcome(monkeypatch, emitted_history())
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.set_content(page_html)
        assert page.locator("#panel-interpreted").is_visible()
        assert not page.locator("#panel-compiled").is_visible()
        assert page.locator(".performance").get_attribute("open") is None
        assert page.locator("#system-status").get_attribute("open") is None
        page.locator("#tab-interpreted").focus()
        page.keyboard.press("ArrowRight")
        assert page.locator("#tab-compiled").get_attribute("aria-selected") == "true"
        assert page.locator("#tab-compiled").evaluate("el => el === document.activeElement")
        assert page.locator("#panel-compiled").is_visible()
        assert not page.locator("#panel-interpreted").is_visible()
        assert "not a chronological record" in page.locator("#panel-compiled").inner_text()
        assert not page.locator("#panel-compiled pre").first.is_visible()
        page.keyboard.press("Tab")
        summary = page.locator("#panel-compiled details summary").first
        assert summary.evaluate("el => el === document.activeElement")
        page.keyboard.press("Enter")
        assert page.locator("#panel-compiled details").first.get_attribute("open") is not None
        assert page.locator("#panel-compiled pre").first.is_visible()
        page.keyboard.press("Space")
        assert page.locator("#panel-compiled details").first.get_attribute("open") is None
        page.locator("#tab-compiled").focus()
        page.keyboard.press("End")
        assert page.locator("#panel-executed").is_visible()
        assert "completed successfully" in page.locator("#panel-executed").inner_text()
        assert page.locator("#panel-executed details[open]").count() == 0
        page.keyboard.press("Home")
        assert page.locator("#panel-interpreted").is_visible()
        # Long IRIs and wide result rows must not widen the document, even when open.
        for stage in ("interpreted", "compiled", "executed"):
            page.locator(f"#tab-{stage}").click()
            for detail in page.locator(f"#panel-{stage} details").all():
                detail.evaluate("el => el.open = true")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()


def test_keyboard_skips_unavailable_execution(monkeypatch):
    playwright = pytest.importorskip("playwright.sync_api")
    history = emitted_history()
    page_html = render_outcome(monkeypatch, PlanOutcome(
        "unsupported_mapping", plan=history.plan, sparql=history.sparql,
        diagnostic="Essential evidence unavailable.",
    ))
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page()
        page.set_content(page_html)
        assert page.locator("#tab-executed").is_disabled()
        page.locator("#tab-interpreted").focus()
        page.keyboard.press("End")
        assert page.locator("#tab-compiled").get_attribute("aria-selected") == "true"
        page.keyboard.press("ArrowRight")
        assert page.locator("#tab-interpreted").get_attribute("aria-selected") == "true"
        browser.close()
