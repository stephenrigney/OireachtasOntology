"""Real browser -> application routes -> typed RDF execution.

Synthetic checks run with Playwright installed. Live checks additionally require
OIR_RUN_COMPOSITION_LIVE=1 and configured normal planner/Fuseki credentials.
No bootstrap, source publication or triple-store mutation is performed.
"""

import os
import json
import socket
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn

from poc.nlq.app import create_app
from test_nlq_composition_integration import DatasetTransport, Proposer, QUESTION, synthetic_dataset, BASE
from poc.nlq.composition_kernel import graph, iri
from rdflib import URIRef


@pytest.fixture
def serve():
    servers = []

    def start(app):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        servers.append((server, thread, sock))
        deadline = monotonic() + 5
        while not server.started and thread.is_alive() and monotonic() < deadline:
            sleep(.01)
        assert server.started
        return f"http://127.0.0.1:{port}"

    yield start
    for server, thread, sock in servers:
        server.should_exit = True
        thread.join(10)
        sock.close()


@pytest.fixture
def browser():
    api = pytest.importorskip("playwright.sync_api")
    with api.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        yield browser
        browser.close()


@pytest.mark.parametrize("question", [
    QUESTION,
    "Who currently represents Kildare North and serves on the Committee on Public Accounts?",
    "Which TDs for Kildare North are members of the Committee on Public Accounts?",
    "List the current members of the Committee on Public Accounts who represent Kildare North.",
])
def test_browser_inspect_confirm_names_and_witnesses(monkeypatch, tmp_path, serve, browser, question):
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-05-01")
    class Counting(DatasetTransport):
        count = 0

        def select(self, *args):
            type(self).count += 1
            return super().select(*args)
    app = create_app(feedback_directory=tmp_path, composition_proposer_factory=Proposer, composition_transport_factory=Counting)
    url = serve(app)
    page = browser.new_page(viewport={"width": 390, "height": 900})
    page.goto(url + "/composition")
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    text = page.locator("#confirmed-interpretation").inner_text()
    assert "2026-05-01" in text and "Committee on Public Accounts" in text and "Kildare North" in text
    assert Counting.count == 0
    assert page.locator("#query-results").count() == 0
    page.get_by_role("button", name="Confirm interpretation and execute", exact=True).click()
    assert "Alice Example" in page.locator("#query-results").inner_text()
    assert Counting.count == 6
    assert "not a certified complete roster" in page.locator("#query-results").inner_text()
    summaries = page.locator(".relationship-witness summary")
    assert summaries.count() == 2
    for summary in summaries.all():
        summary.click()
    assert "open-ended (no end recorded)" in page.locator("#composition-evidence").inner_text()
    assert "2026-06-30T00:00:00" in page.locator("#composition-evidence").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    link = page.get_by_role("link", name="Download source evidence", exact=False).get_attribute("href")
    artifact = page.request.get(url + link).json()
    assert artifact["confirmedRequest"]["asOf"] == "2026-05-01"
    assert len(artifact["report"]["answer"]["witnesses"]) == 1
    assert artifact["report"]["displayEvidence"]
    page.close()


@pytest.mark.parametrize("fault,expected", [
    ("additional", "Additional conditions"),
    ("date", "ISO calendar date"),
    ("incomplete", "Incomplete required enumeration"),
    ("budget", "budget"),
    ("ambiguous", "Ambiguous"),
    ("missing", "Missing/conflicting"),
])
def test_browser_failure_messages_no_partial_answer(monkeypatch, tmp_path, serve, browser, fault, expected):
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "invalid" if fault == "date" else "2026-05-01")
    ds = synthetic_dataset()
    if fault == "ambiguous":
        resource = URIRef(BASE + "test/committee")
        for s, p, o in list(ds.graph(graph("committees"))):
            if s == resource:
                ds.graph(graph("committees")).add((URIRef(str(resource) + "-other"), p, o))
    if fault == "missing":
        ds.graph(URIRef(BASE + "graph/member/Bob")).remove((None, iri("members:StartDate"), None))

    class Fault(DatasetTransport):
        def __init__(self, *a, **k):
            super().__init__(dataset=ds)

        def select(self, *args):
            if fault == "budget":
                return dict(columns=["term"], rows=[{"term": URIRef(BASE + "test")}]*100, complete=True)
            result = super().select(*args)
            if fault == "incomplete": result["complete"] = False
            return result

    url = serve(create_app(feedback_directory=tmp_path, composition_proposer_factory=Proposer, composition_transport_factory=Fault))
    page = browser.new_page()
    page.goto(url + "/composition")
    page.get_by_label("Your question", exact=True).fill(QUESTION.rstrip("?") + " and belong to Fine Gael?" if fault == "additional" else QUESTION)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    if fault not in {"additional", "date"}:
        page.get_by_role("button", name="Confirm interpretation and execute", exact=True).click()
    assert expected in page.get_by_role("alert").inner_text()
    assert page.locator("#query-results").count() == 0
    if fault == "ambiguous":
        candidates = page.get_by_role("list", name="Grounded identity candidates")
        assert candidates.locator("li").count() == 2
        assert BASE + "test/committee-other" in candidates.inner_text()
    page.close()


def test_browser_reject_edit_then_repropose(monkeypatch, tmp_path, serve, browser):
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-05-01")
    url = serve(create_app(feedback_directory=tmp_path, composition_proposer_factory=Proposer, composition_transport_factory=DatasetTransport))
    page = browser.new_page()
    page.goto(url + "/composition")
    page.get_by_label("Your question", exact=True).fill(QUESTION)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    page.get_by_role("button", name="Reject interpretation", exact=True).click()
    assert "nothing was executed" in page.get_by_role("status").filter(has_text="Interpretation rejected").inner_text()
    assert page.locator("#query-results").count() == 0
    page.get_by_label("Your question", exact=True).fill(QUESTION)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    assert page.locator("#confirmed-interpretation").is_visible()
    page.close()


@pytest.mark.skipif(os.getenv("OIR_RUN_COMPOSITION_LIVE") != "1", reason="Opt-in existing live Fuseki and semantic planner")
@pytest.mark.parametrize("question,names", [
    (QUESTION, {"Aidan Farrelly", "Joe Neville"}),
    ("Who currently represents Kildare North and serves on the Committee of Public Accounts?", {"Aidan Farrelly", "Joe Neville"}),
    ("Which TDs for Kildare North are members of the Committee on Public Accounts?", {"Aidan Farrelly", "Joe Neville"}),
    ("List the current members of the Committee on Public Accounts who represent Galway East.", {"Albert Dolan"}),
    ("Which members of the Committee on Public Accounts currently represent Cork South-Central?", {"Séamus McGrath"}),
    ("Which members of the Joint Committee on Health currently represent Roscommon-Galway?", {"Martin Daly"}),
    ("Which members of the Committee on Budgetary Oversight currently represent Kildare North?", {"Joe Neville"}),
])
def test_live_browser_english_proposal_then_confirmed_execution(tmp_path, serve, browser, question, names):
    """Constructed variants; interpretation and confirmed execution are separate assertions."""
    url = serve(create_app(feedback_directory=tmp_path))
    page = browser.new_page()
    page.set_default_timeout(90000)
    page.goto(url + "/composition")
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    assert page.locator("#confirmed-interpretation").is_visible(), page.content()
    assert page.locator("#query-results").count() == 0
    page.get_by_role("button", name="Confirm interpretation and execute", exact=True).click()
    result = page.locator("#query-results")
    assert result.is_visible(), page.content()
    assert set(result.locator("tbody tr td:first-child").all_inner_texts()) == names
    assert "not a certified complete roster" in result.inner_text()
    assert page.locator(".relationship-witness").count() == 2 * len(names)
    link = page.get_by_role("link", name="Download source evidence", exact=False).get_attribute("href")
    artifact = page.request.get(url + link).json()
    report = artifact["report"]
    print(json.dumps({"question": question, "asOf": artifact["confirmedRequest"]["asOf"],
                      "interpretation": "proposed and displayed before confirmation",
                      "execution": report["status"], "names": report["names"],
                      "requests": [{"kind": r["kind"], "offset": r["offset"], "rows": len(r["rows"])} for r in report["ledger"]],
                      "witnesses": [[{"role": w["role"], "bindings": w["bindings"], "intervals": w["intervals"]} for w in pair] for pair in report["answer"]["witnesses"]]}, ensure_ascii=False))
    page.close()


@pytest.mark.skipif(os.getenv("OIR_RUN_COMPOSITION_LIVE") != "1", reason="Opt-in existing live Fuseki and semantic planner")
@pytest.mark.parametrize("question,expected,answer", [
    ("Who are the Sinn Féin TDs for Dublin Central?", "Mary Lou McDonald", True),
    ("Who are the TDs for Dublin Central and when were they first elected?", "Election-event", False),
    ("Find a Deputy called Browne", "Noel C. Browne", False),
])
def test_live_default_recorded_human_question_regression(tmp_path, serve, browser, question, expected, answer):
    """Verbatim Q1/Q17/Q2 from user-question-regression.md; no new success claim for refusals."""
    url = serve(create_app(feedback_directory=tmp_path))
    page = browser.new_page()
    page.set_default_timeout(90000)
    page.goto(url)
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Ask", exact=True).click()
    assert expected.lower() in page.locator("body").inner_text().lower()
    assert bool(page.locator("#query-results").count()) == answer
    print(json.dumps({"recordedHumanQuestion": question, "defaultPath": "/ask", "factualAnswer": answer,
                      "expectedTextPresent": expected}, ensure_ascii=False))
    page.close()


@pytest.mark.skipif(os.getenv("OIR_RUN_COMPOSITION_LIVE") != "1", reason="Opt-in existing live Fuseki and semantic planner")
def test_live_unsupported_additional_condition_never_reaches_confirmation(tmp_path, serve, browser):
    question = QUESTION.rstrip("?") + " and belong to Fine Gael?"
    url = serve(create_app(feedback_directory=tmp_path))
    page = browser.new_page()
    page.set_default_timeout(90000)
    page.goto(url + "/composition")
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    assert page.get_by_role("alert").is_visible()
    assert page.locator("#confirmed-interpretation").count() == page.locator("#query-results").count() == 0
    print(json.dumps({"question": question, "interpretation": "refused; no confirmation or execution", "message": page.get_by_role("alert").inner_text()}))
    page.close()


@pytest.mark.skipif(os.getenv("OIR_RUN_COMPOSITION_LIVE") != "1", reason="Opt-in existing live Fuseki and semantic planner")
def test_live_empty_recorded_intersection_is_nonanswer_not_zero(tmp_path, serve, browser):
    question = "Which members of the Joint Committee on Transport currently represent Kildare North?"
    url = serve(create_app(feedback_directory=tmp_path))
    page = browser.new_page()
    page.set_default_timeout(90000)
    page.goto(url + "/composition")
    page.get_by_label("Your question", exact=True).fill(question)
    page.get_by_role("button", name="Propose interpretation", exact=True).click()
    assert page.locator("#confirmed-interpretation").is_visible()
    page.get_by_role("button", name="Confirm interpretation and execute", exact=True).click()
    assert "No qualifying recorded evidence" in page.get_by_role("alert").inner_text()
    assert page.locator("#query-results").count() == 0
    print(json.dumps({"question": question, "interpretation": "proposed and confirmed", "execution": "nonanswer; not a factual empty roster"}))
    page.close()
