"""Actual browser /ask navigation: direct answers, semantic refusals and live smoke."""

import json
import os

import pytest

from poc.nlq.app import create_app
from test_nlq_composition_browser import serve, browser  # existing real-server/browser fixtures
from test_nlq_main_composition import VARIATIONS, make_app, proposal, MainTransport, party_dataset, BASE
from poc.nlq.composition_kernel import graph, iri
from rdflib import Literal, URIRef


@pytest.mark.parametrize("question,pair,shape", VARIATIONS)
def test_browser_main_ask_direct_answers_and_supporting_paths(monkeypatch, tmp_path, serve, browser, question, pair, shape):
    app, planner = make_app(monkeypatch, tmp_path, proposal(question, pair, shape))
    url = serve(app)
    page = browser.new_page(viewport={"width": 390, "height": 900})
    page.goto(url)
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Ask", exact=True).click()
    assert page.locator("#query-results").is_visible()
    assert page.get_by_role("button", name="Confirm interpretation and execute").count() == 0
    assert page.get_by_role("region", name="Composition interpretation").is_visible()
    assert page.locator(".relationship-witness").count() == 2
    assert "not a certified complete roster" in page.locator("#query-results").inner_text()
    assert "2026-05-01" in page.locator("#query-results").inner_text()
    assert planner.calls == 1
    for detail in page.locator(".relationship-witness summary").all(): detail.click()
    assert "Alice Example" in page.locator("#composition-evidence").inner_text()
    assert "Actual source graph" in page.locator("#composition-evidence").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if shape == "count": assert "Distinct recorded Members" in page.locator("#query-results").inner_text()
    link = page.get_by_role("link", name="Download source evidence", exact=False).get_attribute("href")
    artifact = page.request.get(url + link).json()
    assert "confirmedRequest" not in artifact
    assert len(artifact["report"]["ledger"]) == 6
    assert {w["role"] for w in artifact["report"]["answer"]["witnesses"][0]} == set(pair)
    page.close()


@pytest.mark.parametrize("fault", ["extra", "date", "negation", "boolean", "committee_count", "ambiguous"])
def test_browser_main_ask_safe_outcomes_not_answers(monkeypatch, tmp_path, serve, browser, fault):
    q = "Which Fianna Fáil members serve on Public Accounts?"
    draft = proposal(q, "KP")
    transport = MainTransport
    if fault == "extra": q = q.rstrip("?") + " and are women?"
    if fault == "date": q = q.rstrip("?") + " as of 2024-02-30?"
    if fault == "negation": q = q.rstrip("?") + " and are not Senators?"
    if fault == "boolean":
        q = "Are there Fianna Fáil members serving on Public Accounts?"
    if fault == "committee_count":
        q = "How many Fianna Fáil members serve on Public Accounts?"
        draft["referents"]["shape"] = "count"
    if fault == "ambiguous":
        ds = party_dataset()
        owner = ds.graph(graph("committees"))
        source = URIRef(BASE + "test/committee")
        for _, p, o in list(owner.triples((source, None, None))): owner.add((URIRef(str(source) + "-other"), p, o))
        class Ambiguous(MainTransport):
            def __init__(self, *args, **kwargs): self.dataset, self.calls = ds, []
        transport = Ambiguous
    app, _ = make_app(monkeypatch, tmp_path, draft, transport=transport)
    url = serve(app)
    page = browser.new_page()
    page.goto(url)
    page.get_by_label("Your question", exact=True).fill(q)
    page.get_by_role("button", name="Ask", exact=True).click()
    assert page.get_by_role("alert").is_visible()
    assert page.locator("#query-results").count() == 0
    if fault == "boolean": assert "Yes/no composition is not supported" in page.get_by_role("alert").inner_text()
    if fault == "ambiguous": assert "none was selected" in page.locator("#composition-evidence").inner_text()
    page.close()


LIVE = [
    ("Who are the Sinn Féin TDs for Dublin Central?", {"Mary Lou McDonald"}, None),  # recorded human Q1
    ("Please identify the representatives for Dublin Central who belong to Sinn Féin.", {"Mary Lou McDonald"}, None),
    ("Tell me the number of Sinn Féin TDs representing Dublin Central.", {"Mary Lou McDonald"}, 1),
    ("Which Fine Gael TDs represent Kildare North?", {"Joe Neville"}, None),
    ("Who on the Committee of Public Accounts belongs to Fianna Fáil?", {"Albert Dolan", "Martin Daly", "Paul McAuliffe", "Séamus McGrath"}, None),
    ("Public Accounts members affiliated with Fianna Fáil: who are they?", {"Albert Dolan", "Martin Daly", "Paul McAuliffe", "Séamus McGrath"}, None),
    ("For Galway East, show me the TDs who serve on the Committee of Public Accounts.", {"Albert Dolan"}, None),
    ("Name the Roscommon-Galway representatives serving on the Joint Committee on Health.", {"Martin Daly"}, None),
]


@pytest.mark.skipif(os.getenv("OIR_RUN_COMPOSITION_LIVE") != "1", reason="Opt-in real semantic planner and existing read-only Fuseki")
@pytest.mark.parametrize("question,names,count", LIVE)
def test_live_main_ask_composition(tmp_path, serve, browser, question, names, count):
    url = serve(create_app(feedback_directory=tmp_path))
    page = browser.new_page()
    page.set_default_timeout(90000)
    page.goto(url)
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Ask", exact=True).click()
    assert page.locator("#query-results").is_visible(), page.get_by_role("alert").inner_text() if page.get_by_role("alert").count() else page.content()
    assert page.get_by_role("button", name="Confirm interpretation and execute").count() == 0
    link = page.get_by_role("link", name="Download source evidence", exact=False).get_attribute("href")
    artifact = page.request.get(url + link).json()
    report = artifact["report"]
    assert report["status"] == "answer" and set(report["names"].values()) == names
    assert report["answer"].get("distinctCount") == count
    assert len(report["ledger"]) <= 8
    assert all(interval["currentAtAsOf"] for pair in report["answer"]["witnesses"] for witness in pair for interval in witness["intervals"])
    print(json.dumps({"question": question, "answer": sorted(names), "count": count,
                      "asOf": report["answer"]["asOf"], "requests": len(report["ledger"]),
                      "interpretation": "independently admitted", "execution": "answer"}, ensure_ascii=False))
    page.close()
