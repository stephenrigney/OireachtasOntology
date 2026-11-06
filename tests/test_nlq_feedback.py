"""Opt-in NLQ evidence-session persistence and route tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from poc.nlq import app as app_module
from poc.nlq import feedback as feedback_module
from poc.nlq.app import _displayed_answer_text
from poc.nlq.member_resolution import MemberAmbiguity, MemberCandidate
from poc.nlq.results import QueryResult


ROOT = app_module.ROOT


def _app(directory):
    return app_module.create_app(repository_root=ROOT, feedback_directory=directory)


def test_actual_feedback_includes_ambiguity_candidates_and_warnings_without_debug_output():
    ambiguity = MemberAmbiguity(
        entity_reference="Alex Murphy",
        candidates=(
            MemberCandidate("urn:member:1", "Alex Murphy", house_terms=("33rd Dáil",),
                            representations=("Dublin Central",)),
            MemberCandidate("urn:member:2", "Alex Murphy", house_terms=("34th Dáil",)),
        ),
    )
    actual = _displayed_answer_text(
        error="The request is ambiguous.", ambiguity=ambiguity,
        result=QueryResult("select", columns=("Member",), rows=(("Alex Murphy",),)),
        result_notice="The local source coverage is incomplete.",
        entity_outcomes=({"resolution": "ambiguous", "candidates": [
            {"label": "Candidate A", "iri": "urn:candidate:a"},
        ]},),
    )
    assert "The request is ambiguous." in actual
    assert "Alex Murphy" in actual
    assert "33rd Dáil" in actual and "Dublin Central" in actual
    assert "34th Dáil" in actual
    assert "Candidate A — urn:candidate:a" in actual
    assert "The local source coverage is incomplete." in actual


def test_feedback_form_locks_after_success_and_keeps_values_on_failure():
    template = (app_module.TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert 'if (form.dataset.saved === "true") return;' in template
    assert 'form.dataset.saved = "true";' in template
    assert 'form.querySelectorAll("input, textarea, button").forEach(control => { control.disabled = true; });' in template
    assert 'finally { if (!saved) submit.disabled = false; }' in template
    assert 'catch (error) { message.textContent = `${error.message} Please retry; the record was not confirmed saved.`; }' in template
    assert "form.reset()" not in template


def test_feedback_session_lifecycle_persists_records_across_app_restart(tmp_path):
    storage = tmp_path / "local-feedback"
    with TestClient(_app(storage)) as client:
        started = client.post("/feedback/sessions")
        assert started.status_code == 200
        session_id = started.json()["session_id"]
        assert client.get(f"/feedback/sessions/{session_id}").json()["active"] is True

        yes = {"session_id": session_id, "question": "Is this correct?", "expected": "",
               "actual": "Yes", "correct": True}
        no = {"session_id": session_id, "question": "Who held office?", "expected": "A. Person",
              "actual": "The result is partial.", "correct": False}
        assert client.post("/feedback", json=yes).status_code == 201
        assert client.post("/feedback", json=no).status_code == 201

        feedback_file = storage / f"{session_id}.jsonl"
        lines = feedback_file.read_text(encoding="utf-8").splitlines()
        saved = [json.loads(line) for line in lines]
        assert saved == [
            {"question": yes["question"], "expected": "", "actual": "Yes", "correct": True},
            {"question": no["question"], "expected": "A. Person", "actual": "The result is partial.", "correct": False},
        ]
        assert all(type(row["correct"]) is bool for row in saved)

        # An application restart does not orphan an active browser session;
        # the same stream can continue after reopening the app.
        with TestClient(_app(storage)) as restarted_app:
            assert restarted_app.get(f"/feedback/sessions/{session_id}").json()["active"] is True
            continued = {"session_id": session_id, "question": "Another question?", "expected": "",
                         "actual": "No", "correct": True}
            assert restarted_app.post("/feedback", json=continued).status_code == 201
        lines = feedback_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3

        stopped = client.post(f"/feedback/sessions/{session_id}/stop")
        assert stopped.status_code == 200 and stopped.json()["active"] is False
        assert client.post("/feedback", json=yes).status_code == 400
        assert feedback_file.read_text(encoding="utf-8").splitlines() == lines

    # A fresh app instance consults persisted state; it does not erase or
    # reactivate the stopped session. A new Start creates a distinct stream.
    with TestClient(_app(storage)) as client:
        assert client.get(f"/feedback/sessions/{session_id}").json()["active"] is False
        restarted = client.post("/feedback/sessions").json()["session_id"]
        assert restarted != session_id
        assert client.get(f"/feedback/sessions/{restarted}").json()["active"] is True
        assert len((storage / f"{session_id}.jsonl").read_text().splitlines()) == 3


def test_feedback_validation_and_persistence_failure_are_reported_without_acknowledging(tmp_path, monkeypatch):
    storage = tmp_path / "feedback"
    with TestClient(_app(storage)) as client:
        session_id = client.post("/feedback/sessions").json()["session_id"]
        base = {"session_id": session_id, "question": "Question", "actual": "Unsupported outcome",
                "expected": "Expected result", "correct": False}
        assert client.post("/feedback", json={**base, "correct": "false"}).status_code == 400
        assert client.post("/feedback", json={**base, "expected": " "}).status_code == 400

        original_open = feedback_module.os.open

        def failed_open(path, flags, *args, **kwargs):
            if str(path).endswith(".jsonl"):
                raise OSError("disk unavailable")
            return original_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(feedback_module.os, "open", failed_open)
        failed = client.post("/feedback", json=base)
        assert failed.status_code == 500
        assert failed.json()["detail"] == "Could not save feedback. Your record was not confirmed saved."
        assert (storage / f"{session_id}.jsonl").read_text() == ""


def test_feedback_controls_are_opt_in_and_form_carries_rendered_answer(tmp_path, monkeypatch):
    app = _app(tmp_path / "feedback")
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Start Evidence Session" in page.text
        assert 'class="session-start"' in page.text and 'class="session-stop"' in page.text
        assert 'id="answer-feedback"' not in page.text

        session_id = client.post("/feedback/sessions").json()["session_id"]
        client.cookies.set("oireachtas_nlq_feedback_session", session_id)
        # A stable unsupported result exercises the same displayed-outcome
        # capture path without involving an LLM or the graph store.
        from poc.nlq.composable_plan import PlanOutcome
        monkeypatch.setattr(app_module, "execute_question", lambda *args, **kwargs: PlanOutcome(
            status="unsupported_request", diagnostic="This question is unsupported."
        ))
        response = client.post("/ask", data={"question": "Unsupported question", "mode": "phase2"})
        assert 'id="answer-feedback"' in response.text
        assert "This question is unsupported." in response.text
        assert "No answer query was executed after this resolution failure." in response.text
        actual_value = response.text.split('name="actual" value="', 1)[1].split('"', 1)[0]
        assert actual_value == "This question is unsupported."
        assert "No answer query was executed after this resolution failure." not in actual_value
        assert 'type="radio" name="correct" value="yes"' in response.text
        assert 'type="radio" name="correct" value="no"' in response.text


def test_dashboard_initial_state_and_stage_accessibility(tmp_path):
    with TestClient(_app(tmp_path / "feedback")) as client:
        page = client.get("/").text
    assert "Natural language queries" in page
    assert "OIREACHTAS ONTOLOGY" in page
    assert "#F6F3EA" in page and "--card:#fff" in page
    assert "id=\"query-processing\"" not in page
    assert "id=\"answer-feedback\"" not in page
    template = (app_module.TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert 'class="stage-tabs" role="tablist" aria-label="Query processing stages"' in template
    assert 'ArrowLeft' in template and 'ArrowRight' in template
    assert 'name="correct"' in template
    assert "html { min-height:100%; background:var(--page); }" in template
    assert "background:transparent;" in template
    assert "{% set compiled_ready = sparql or plan_json %}" in template


def test_blocked_query_stage_does_not_claim_compilation_or_execution(tmp_path, monkeypatch):
    app = _app(tmp_path / "feedback")
    from poc.nlq.composable_plan import PlanOutcome
    monkeypatch.setattr(app_module, "execute_question", lambda *args, **kwargs: PlanOutcome(
        status="unsupported_request", diagnostic="This question is unsupported."
    ))
    with TestClient(app) as client:
        page = client.post("/ask", data={"question": "Unsupported question", "mode": "phase2"}).text
    assert 'id="tab-interpreted"' in page
    assert 'id="tab-compiled"' in page and 'aria-controls="panel-compiled"' in page and 'disabled><span class="stage-num">02' in page
    assert 'id="tab-executed" aria-controls="panel-executed" aria-selected="false"' in page
    assert "Compilation was not reached; no validated plan or SPARQL was produced." in page
    assert "No answer query was executed after this resolution failure." in page
    assert "Resolution diagnostics" in page or "No answer query was executed after this resolution failure." in page
    assert "<details open>" not in page


def test_stage_explanations_and_diagnostics_are_scoped_to_their_tab(tmp_path):
    template = (app_module.TEMPLATES / "index.html").read_text(encoding="utf-8")
    interpreted = template.split('id="panel-interpreted"', 1)[1].split('id="panel-compiled"', 1)[0]
    compiled = template.split('id="panel-compiled"', 1)[1].split('id="panel-executed"', 1)[0]
    executed = template.split('id="panel-executed"', 1)[1].split('</div>', 1)[0]
    assert "plan_json" not in interpreted and "resolution diagnostics" in interpreted.lower()
    assert "plan_json" in compiled and "SPARQL compilation did not produce a query" in compiled
    assert "debug_output" in executed and "Raw {{ debug_source or \"endpoint\" }} response payload" in executed
    assert "execution_failure" in executed and "Execution outcome is unavailable" in executed
    assert '<details{% if executed_ready and (error or debug_message) %} open{% endif %}>' in executed


def test_feedback_retry_does_not_clear_user_answers():
    template = (app_module.TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert 'catch (error) { message.textContent = `${error.message} Please retry; the record was not confirmed saved.`; }' in template
    assert 'finally { if (!saved) submit.disabled = false; }' in template
    assert "form.reset()" not in template
    assert 'expected.value' in template


def test_dashboard_control_labels_colours_and_query_mode_toggle(tmp_path):
    with TestClient(_app(tmp_path / "feedback")) as client:
        page = client.get("/").text
    template = (app_module.TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert "<h2>Evidence session</h2>" not in page
    assert "Your Oireachtas question" not in page
    assert 'id="question" name="question"' in page
    assert 'type="radio" name="mode" value="phase2" checked' in page
    assert 'type="radio" name="mode" value="phase1"' in page
    assert '<select id="mode"' not in page
    assert page.index("Development Query Path") < page.index('type="submit">Ask')
    assert "background:#2E8B57" in template
    assert "background:#C0392B" in template
    assert "th { background:var(--page); }" in template
    assert ".readiness { padding: .75rem; border:0;" in template


def test_unexpected_pre_execution_failure_keeps_executed_stage_unavailable(tmp_path, monkeypatch):
    from poc.nlq import app as app_module

    def fail_before_execution(*_args, **_kwargs):
        raise RuntimeError("planner failed before query dispatch")

    monkeypatch.setattr(app_module, "execute_question", fail_before_execution)
    with TestClient(_app(tmp_path / "feedback")) as client:
        page = client.post("/ask", data={"question": "Count some records", "mode": "phase2"}).text
    executed_tab = page.split('id="tab-executed"', 1)[1].split("</button>", 1)[0]
    assert "disabled" in executed_tab
    assert "Execution was not reached" in page


def test_executed_stage_requires_recorded_database_attempt(tmp_path, monkeypatch):
    from poc.nlq import app as app_module
    from poc.nlq.composable_plan import PlanOutcome

    cases = (
        (PlanOutcome(status="success", sparql="SELECT * WHERE {}",
                     result=QueryResult("select", columns=("item",), rows=(("one",),))), True),
        (PlanOutcome(status="execution_failure", sparql="SELECT * WHERE {}",
                     diagnostic="Fuseki query failed."), True),
    )
    for outcome, reached in cases:
        monkeypatch.setattr(app_module, "execute_question", lambda *args, **kwargs: outcome)
        with TestClient(_app(tmp_path / str(reached))) as client:
            page = client.post("/ask", data={"question": "Count some records", "mode": "phase2"}).text
        executed_tab = page.split('id="tab-executed"', 1)[1].split("</button>", 1)[0]
        assert ("disabled" not in executed_tab) is reached
