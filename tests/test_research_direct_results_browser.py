"""Chromium, real application/compiler; injected author outage, synthetic RDF."""
import pytest

from poc.nlq.research_app import create_app
from test_nlq_composition_browser import serve, browser
from test_nlq_composable_stage_a import StageAFixture
from test_research_general_queries import query, AS_OF
from test_research_v05 import plan
from test_research_direct_results import NoAuthor, without_projector, CHRONOLOGY


@pytest.mark.parametrize("width", [1280, 320])
def test_browser_direct_results_inspection_and_export_without_evidence_projector(
        monkeypatch, tmp_path, serve, browser, width):
    without_projector(monkeypatch)
    model = NoAuthor([plan([query(CHRONOLOGY)])])
    app = create_app(planner_factory=lambda: model, client_factory=StageAFixture, reporting_date=AS_OF)
    url = serve(app)
    page = browser.new_page(viewport={"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    page.locator("#brief").fill(CHRONOLOGY)
    page.get_by_role("button", name="Start research", exact=True).click()
    page.locator("#report-sections table").first.wait_for(timeout=30000)
    assert CHRONOLOGY in page.locator("#report-sections").inner_text()
    assert page.locator("#report-sections tbody tr").count() > 0
    assert "couldn't be safely included" not in page.locator("#report").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.locator("#report-sections tbody button").first.click()
    page.get_by_text("Query Service response · original returned values", exact=True).click()
    assert page.locator("#activity-content pre").first.is_visible()
    assert "columns" in page.locator("#activity-content").inner_text()
    run_id = page.evaluate("run.id")
    exported = page.request.get(url + f"/runs/{run_id}/report.md").text()
    assert CHRONOLOGY in exported and "queryServiceResult" in exported
    assert page.request.get(url + f"/runs/{run_id}/archive").json()["state"]["queryResults"]
    assert not errors
    page.screenshot(path=str(tmp_path / f"direct-results-{width}.png"), full_page=True)
    page.close()
