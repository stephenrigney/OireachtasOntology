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
    assert page.get_by_role("region", name="Composition interpretation").count() == 0
    assert page.locator(".query-outcome").count() == 0
    assert "Answer" in page.locator("#query-results").inner_text()
    assert "http://" not in page.locator("#query-results").inner_text()
    assert page.locator(".relationship-witness").count() == 2
    assert "available records may not be complete" in page.locator("#query-results").inner_text()
    assert "2026-05-01" in page.locator("#query-results").inner_text()
    assert planner.calls == 1
    page.locator("#composition-evidence > details > summary").click()
    for detail in page.locator(".relationship-witness summary").all(): detail.click()
    assert "Alice Example" in page.locator("#composition-evidence").inner_text()
    assert "Actual source graph" in page.locator("#composition-evidence").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    if shape == "count": assert "1 matching TD" in page.locator("#query-results").inner_text()
    else: assert "Alice Example" in page.locator("#query-results").inner_text()
    link = page.get_by_role("link", name="Download source evidence", exact=False).get_attribute("href")
    artifact = page.request.get(url + link).json()
    assert "confirmedRequest" not in artifact
    assert len(artifact["report"]["ledger"]) == 6
    assert {w["role"] for w in artifact["report"]["answer"]["witnesses"][0]} == set(pair)
    page.close()


@pytest.mark.parametrize("pair,shape,variation", [
    ("RP", "list", 0), ("RP", "count", 1), ("KP", "list", 5), ("KR", "list", 9),
])
@pytest.mark.parametrize("width", [1240, 320])
def test_browser_main_ask_composition_three_stage_dashboard(
        monkeypatch, tmp_path, serve, browser, pair, shape, variation, width):
    """The real /ask UI separates admitted specs, recorded SELECTs and execution evidence."""
    question, _, _ = VARIATIONS[variation]
    app, _ = make_app(monkeypatch, tmp_path, proposal(question, pair, shape))
    url = serve(app)
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.goto(url)
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Ask", exact=True).click()

    tabs = page.get_by_role("tablist", name="Query processing stages")
    assert tabs.get_by_role("tab").all_text_contents() == ["01Interpreted", "02Compiled", "03Executed"]
    assert page.locator("#panel-interpreted").is_visible()
    interpreted = page.locator("#panel-interpreted").inner_text()
    assert "Composition request admitted and validated" not in interpreted
    assert "Political party:" in interpreted if "P" in pair else True
    assert "Constituency:" in interpreted if "R" in pair else True
    assert "Committee:" in interpreted if "K" in pair else True
    assert "Kildare North" in interpreted if "R" in pair else "Public Accounts" in interpreted
    assert "Fianna Fáil" in interpreted if "P" in pair else "Kildare North" in interpreted
    assert "2026-05-01" in interpreted
    assert ("count of matching" in interpreted.lower()) == (shape == "count")
    assert "Outcome:" not in page.locator("body").inner_text()

    page.locator("#tab-interpreted").focus()
    page.keyboard.press("ArrowRight")
    assert page.locator("#tab-compiled").get_attribute("aria-selected") == "true"
    assert page.locator("#tab-compiled").evaluate("el => el === document.activeElement")
    compiled = page.locator("#panel-compiled")
    assert "application prepared a query" in compiled.inner_text().lower()
    assert "same person" in compiled.inner_text().lower()
    assert "P.parliamentaryMembership" not in compiled.inner_text()
    assert "R.parliamentaryMembership" not in compiled.inner_text()
    queries = compiled.get_by_text("Recorded generated SPARQL SELECT requests", exact=True)
    assert queries.count() == 1
    queries.click()
    assert compiled.locator("pre code").count() >= 1
    assert all("SELECT" in text.upper() for text in compiled.locator("pre code").all_text_contents())
    assert "no combined query or chronology is implied" in compiled.inner_text().lower()
    assert "technical query details" in compiled.inner_text().lower()
    compiled.get_by_text("Technical query details", exact=True).click()
    assert "Exact identity bindings" in compiled.inner_text()
    assert page.locator("#panel-executed").locator("pre code").count() == 0

    page.locator("#tab-compiled").focus()
    page.keyboard.press("ArrowRight")
    assert page.locator("#panel-executed").is_visible()
    executed = page.locator("#panel-executed").inner_text().lower()
    assert "the query completed successfully" in executed
    if shape == "count":
        assert "1 matching td" in page.locator("#query-results").inner_text().lower()
        assert "1" in page.locator("#query-results").inner_text()
    else:
        assert "alice example" in page.locator("#query-results").inner_text().lower()
    assert "available records may not be complete" in page.locator("#query-results").inner_text().lower()
    assert "http://" not in page.locator("#query-results").inner_text()
    page.locator("#composition-evidence > details > summary").click()
    assert "alice example" in page.locator("#composition-evidence").inner_text().lower()
    evidence_link = page.get_by_role("link", name="Download source evidence", exact=False)
    assert evidence_link.is_visible()
    artifact = page.request.get(url + evidence_link.get_attribute("href")).json()
    assert artifact["report"]["status"] == "answer"
    assert artifact["report"]["ledger"]
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.close()


@pytest.mark.parametrize("pair,shape,variation", [
    ("RP", "list", 0), ("RP", "count", 1), ("KP", "list", 5), ("KR", "list", 9),
])
def test_browser_composition_feedback_matches_visible_answer_and_persists(
        monkeypatch, tmp_path, serve, browser, pair, shape, variation):
    question, _, _ = VARIATIONS[variation]
    app, _ = make_app(monkeypatch, tmp_path, proposal(question, pair, shape))
    url = serve(app)
    page = browser.new_page(viewport={"width": 1240, "height": 900})
    page.goto(url)
    page.get_by_role("button", name="Start Evidence Session").click()
    page.wait_for_function("localStorage.getItem('oireachtas-nlq-evidence-session') !== null")
    session_id = page.evaluate("localStorage.getItem('oireachtas-nlq-evidence-session')")
    assert session_id

    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Ask", exact=True).click()
    answer = page.locator("#query-results")
    displayed_lines = [line.strip() for line in answer.inner_text().splitlines() if line.strip()]
    actual = page.locator('#feedback-form input[name="actual"]').input_value()
    assert actual == "\n".join(displayed_lines)
    assert "http://" not in actual
    assert "available records may not be complete" in actual
    if shape == "count":
        assert "1 matching TD" in actual
    else:
        assert "Alice Example" in actual

    page.get_by_label("Yes", exact=True).check()
    page.get_by_role("button", name="Save feedback").click()
    page.wait_for_function("document.querySelector('.feedback-message')?.textContent.length > 0")
    assert "Feedback saved immediately" in page.locator(".feedback-message").inner_text()
    saved = json.loads((tmp_path / f"{session_id}.jsonl").read_text().splitlines()[0])
    assert saved["actual"] == actual
    assert saved["question"] == question and saved["correct"] is True
    evidence_link = page.get_by_role("link", name="Download source evidence", exact=False)
    page.locator("#composition-evidence > details > summary").click()
    assert evidence_link.is_visible()
    assert page.request.get(url + evidence_link.get_attribute("href")).status == 200
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
    if fault in {"extra", "date", "negation", "boolean", "committee_count"}:
        assert page.locator("#tab-interpreted").is_enabled()
        assert page.locator("#tab-compiled").is_disabled()
        assert page.locator("#tab-executed").is_disabled()
        assert page.locator("#panel-interpreted").is_visible()
        assert "Compilation was not reached" in page.locator("#panel-compiled").inner_text()
        assert "Execution was not reached" in page.locator("#panel-executed").inner_text()
        assert page.locator("#panel-compiled details").count() == 0
    if fault == "boolean": assert "Yes/no composition is not supported" in page.get_by_role("alert").inner_text()
    if fault == "ambiguous":
        page.locator("#composition-evidence > details > summary").click()
        assert "none was selected" in page.locator("#composition-evidence").inner_text()
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
