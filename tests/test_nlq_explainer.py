"""Presentation acceptance using emitted plans and existing RDF-backed executors."""

import copy
import html
import re

import pytest
from fastapi.testclient import TestClient

from poc.nlq import app as app_module
from poc.nlq.composable_plan import PlanOutcome, validate_plan
from poc.nlq.explainer import RELATIONS, explain_execution, explain_validated_plan
from poc.nlq.results import QueryResult
from poc.nlq.stage_b import plan_stage_b
from poc.nlq.stage_c import plan_stage_c
from test_nlq_composable_party_temporal import (
    ROOT, AS_OF, PartyRepresentationFixture, QUESTION_U16, _temporal_draft,
    _run, _ask, _current_term_fixture, _representation_member_draft,
)


def panel(page, name, *, default=False):
    content = re.search(rf'<div[^>]*id="panel-{name}"[^>]*>(.*?)</div>', page, re.S).group(1)
    if default:
        content = re.sub(r"<details\b.*?</details>", "", content, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", content))


def tab(page, name):
    return page.split(f'id="tab-{name}"', 1)[1].split("</button>", 1)[0]


def render_outcome(monkeypatch, outcome, question=QUESTION_U16):
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **k: PartyRepresentationFixture())
    monkeypatch.setattr(app_module, "execute_question", lambda *a, **k: outcome)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": question})
    assert response.status_code == 200
    return response.text


def emitted_history():
    outcome, _ = _run(PartyRepresentationFixture(), QUESTION_U16,
                      _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin"))
    assert outcome.status == "success", outcome.diagnostic
    return outcome


def test_historical_representation_party_and_overlap_are_readable_without_technical_disclosures(monkeypatch):
    # The screenshot's term/place/party combination runs against the existing RDF
    # fixture builder, not a hand-written supposed emitted plan.
    question = "Which Fianna Fáil TDs represented Dublin Central during the 22nd Dáil?"
    fixture = PartyRepresentationFixture(term_number=22, constituency_label="Dublin Central")
    response, _ = _ask(monkeypatch, fixture, question, _temporal_draft(
        answer_referent="member", affiliation_mention="Fianna Fáil", constituency="Dublin Central",
        term_selector={"kind": "termNumber", "number": 22},
    ))
    assert 'data-outcome="answer"' in response.text
    interpreted = panel(response.text, "interpreted", default=True)
    compiled = panel(response.text, "compiled", default=True)
    executed = panel(response.text, "executed", default=True)
    for value in ("Dublin Central", "22nd Dáil", "Fianna Fáil"):
        assert value in interpreted and value in compiled
    assert "Your question was understood as" in interpreted
    assert "recorded representation of Dublin Central in the 22nd Dáil and party affiliation with Fianna Fáil" in interpreted
    assert "What the results will contain" in interpreted
    assert "periods must overlap" in interpreted
    assert "same exact Dáil membership" in compiled
    assert "Repeated matches are combined by exact identity" in compiled
    assert "not a chronological record" in compiled
    assert "completed successfully" in executed
    assert "does not establish that the requested answer is complete" in executed
    assert "Aoife Byrne" not in executed  # Do not duplicate the final answer.
    for text in (interpreted, compiled, executed):
        assert "https://" not in text and "SELECT" not in text
        assert "established interval overlap" not in text
    assert "Technical query plan — JSON and identifiers" in response.text
    assert "Generated SPARQL" in response.text
    assert "Further interpretation evidence" in response.text
    actual = response.context["feedback_actual"]
    assert "recorded representation of Dublin Central in the 22nd Dáil" in actual
    assert "established interval overlap" not in actual  # Hidden legacy notes are not the displayed answer.


@pytest.mark.parametrize("explicit", [False, True])
def test_present_default_is_distinguished_from_explicit_current_scope(monkeypatch, explicit):
    question = f"Which Sinn Féin TDs {'currently ' if explicit else ''}represent Galway West?"
    response, _ = _ask(monkeypatch, _current_term_fixture(), question, _temporal_draft(
        answer_referent="member", affiliation_mention="Sinn Féin", term_selector={"kind": "currentTerm"},
    ))
    assert 'data-outcome="answer"' in response.text
    interpreted = panel(response.text, "interpreted", default=True)
    assert ("Explicit current-time request" if explicit else "Present-time default applied") in interpreted
    assert "independently contain 2026-10-28" in interpreted
    if explicit:
        assert "Present-time default applied" not in interpreted
    else:
        assert "Temporal assumptions" in interpreted


def test_explicit_historical_scope_does_not_acquire_present_default():
    outcome = emitted_history()
    before = copy.deepcopy(outcome.plan)
    view = explain_validated_plan(outcome.plan, question=QUESTION_U16)
    assert view["assumptions"] == []
    assert any("33rd Dáil" in text for text in view["conditions"])
    assert not any("must independently contain" in text for text in view["conditions"])
    assert outcome.plan == before


def test_current_term_wide_scope_is_not_misrepresented_as_date_point(monkeypatch):
    question = "How many TDs represented Galway West in this Dáil?"
    response, _ = _ask(monkeypatch, _current_term_fixture(), question,
                       _representation_member_draft(constituency="Galway West"))
    interpreted = panel(response.text, "interpreted", default=True)
    assert "term-wide membership" in interpreted
    assert "service on the reference date is not required" in interpreted
    assert "Present-time default applied" not in interpreted


@pytest.mark.parametrize("question,expected", [
    ("Tell me about Bill 60 from 2025", "Bill 60 of 2025"),
    ("What Bills were published in 2025?", "Published activity"),
    ("Who was Minister for Finance on 1 January 2020?", "2020-01-01"),
])
def test_other_family_builders_supply_shared_entities_relationships_and_conditions(question, expected):
    plan = plan_stage_b(question, as_of=AS_OF)
    assert plan is not None
    assert validate_plan(plan) == plan
    view = explain_validated_plan(plan, question=question)
    assert expected in repr(view)
    assert view["relationships"] and view["construction"]
    assert view["gaps"] == []
    if "Bill 60" in question:
        assert "delivery" in repr(view["relationships"])
        assert "sharing a source graph alone is not enough" in repr(view["relationships"])
        assert "where available" in view["answer_text"]


@pytest.mark.parametrize("status", ["unsupported_mapping", "source_data_unavailable"])
def test_validated_plan_without_execution_has_plan_components_but_unavailable_execution(monkeypatch, status):
    history = emitted_history()
    page = render_outcome(monkeypatch, PlanOutcome(status, plan=history.plan,
                          diagnostic="Essential source evidence unavailable.", sparql=history.sparql))
    assert "Answer target" in panel(page, "compiled", default=True)
    assert "disabled" not in tab(page, "compiled")
    assert "disabled" in tab(page, "executed")
    assert "Execution was not reached" in panel(page, "executed", default=True)
    assert "completed successfully" not in panel(page, "executed")


@pytest.mark.parametrize("status", ["unsupported_request", "validation_failure", "ambiguous"])
def test_no_plan_does_not_claim_a_validated_interpretation(monkeypatch, status):
    page = render_outcome(monkeypatch, PlanOutcome(status, diagnostic="Request not accepted."))
    assert "Interpretation validated" not in panel(page, "interpreted", default=True)
    assert "disabled" in tab(page, "executed")
    assert "disabled" in tab(page, "compiled")


def test_ambiguous_identity_can_have_valid_structure_but_not_a_success_badge(monkeypatch):
    history = emitted_history()
    plan = copy.deepcopy(history.plan)
    ref = plan["referents"]["affiliation"]
    iri = ref.pop("iri")
    label = ref.pop("label")
    ref.update(resolution="ambiguous", candidates=[{"iri": iri, "label": label},
               {"iri": iri + "-other", "label": label}])
    validate_plan(plan)
    page = render_outcome(monkeypatch, PlanOutcome("ambiguous", plan=plan, diagnostic="Multiple matches; none selected."))
    text = panel(page, "interpreted", default=True)
    assert "Interpretation validated" not in text
    assert "identity selection is incomplete" in text
    assert "Several matches; no single identity selected" in text
    assert "disabled" in tab(page, "executed")


@pytest.mark.parametrize("status,result,diagnostic,expected", [
    ("success", QueryResult("select", ("Member",), (("Recorded Member",),)), None, "Returned 1 result row"),
    ("success", QueryResult("select", ("Member",), ()), None, "No matching records found in the queried data"),
    ("execution_failure", None, "Endpoint timeout.", "attempted but failed"),
    ("source_data_unavailable", QueryResult("select", ("Member",), (("Recorded Member",),)), "Partial coverage: only accepted local records.", "returned with qualifications"),
])
def test_execution_states_and_visible_qualifiers(monkeypatch, status, result, diagnostic, expected):
    history = emitted_history()
    page = render_outcome(monkeypatch, PlanOutcome(status, plan=history.plan,
                          sparql=history.sparql, result=result, diagnostic=diagnostic))
    text = panel(page, "executed", default=True)
    assert "disabled" not in tab(page, "executed")
    assert expected in text
    if diagnostic:
        assert diagnostic in text
    if result:
        assert "does not establish that the requested answer is complete" in text
    if status != "success":
        assert "completed successfully" not in text
    assert "<details open" not in page.split('id="panel-executed"', 1)[1].split("</div>", 1)[0]


def test_actual_partial_sponsorship_result_keeps_missing_evidence_visible(monkeypatch):
    from test_nlq_composable_q23 import BillSponsorshipFixture, QUESTION
    fixture = BillSponsorshipFixture()
    fixture.add_bill(2023, "7", None, ({"primary": False},), title_ga="Teideal Gaeilge amháin")
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **k: fixture)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={"question": QUESTION})
    text = panel(response.text, "executed", default=True)
    assert "returned with qualifications" in text
    assert "English short-title" in text
    assert "does not certify complete historical coverage" in text
    assert "English short title not recorded" in response.text


def test_actual_bill_execution_reports_returned_result_and_coverage(monkeypatch):
    import json
    from oireachtas_etl.transforms.bills import bill_graph_iri, transform_bill_with_report
    from test_nlq_stage_b import TinyDataset
    from rdflib import URIRef
    record = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
    graph, _ = transform_bill_with_report(record)
    fixture = TinyDataset()
    owner_graph = fixture.dataset.graph(URIRef(bill_graph_iri(record["bill"])))
    owner_graph += graph
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **k: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post(
        "/ask", data={"question": "Tell me about Bill 60 from 2025"})
    assert 'data-outcome="answer"' in response.text
    assert "Finance Bill 2025" in response.text
    assert "completed successfully" in panel(response.text, "executed", default=True)
    assert "recorded status" in panel(response.text, "compiled", default=True)


def test_absent_optional_fields_and_untranslated_settings_are_conservative():
    plan = plan_stage_c("How many members were in the 22nd Dáil?", as_of=AS_OF)
    assert validate_plan(plan) == plan
    view = explain_validated_plan(plan)
    assert view["relationships"] == [] and view["assumptions"] == []
    assert "seat allocation" in view["answer_text"]
    # Presentation robustness for a future plan variant does not admit it.
    plan["constraints"] = [{"referent": "term", "field": "unknown", "operator": "unknown"}]
    plan["answer"]["ordering"] = "unknown"
    view = explain_validated_plan(plan)
    assert len(view["gaps"]) == 2
    assert "additional condition" in view["gaps"][1].lower()


def test_boolean_count_and_attempt_evidence_are_not_inferred_from_rows_or_sparql():
    for boolean in (True, False):
        view = explain_execution(attempted=True, result=QueryResult("ask", boolean=boolean))
        assert ("true (Yes)" if boolean else "false (No)") in view["summary"]
    view = explain_execution(attempted=True, result=QueryResult("select", ("Count",), (("0",),)),
                             plan={"answer": {"kind": "count"}})
    assert "Returned count: 0" in view["summary"]
    assert "no historical matches" not in view["summary"]
    assert "not reached" in explain_execution(attempted=False, result=QueryResult("select"))["status"]


def test_all_reviewed_relation_ids_have_shared_plain_language_translations():
    import json
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    assert {item["id"] for item in contract["relations"]} <= RELATIONS.keys()


@pytest.mark.parametrize("family", ["previous_service", "dail_duration", "current_collection", "committee_boolean"])
def test_implicit_family_reference_dates_are_visible_in_summary_and_target(family):
    from poc.nlq.stage_a import _member_outcome_plan
    plan = _member_outcome_plan("Recorded Member", AS_OF, {
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Recorded-Member": "Recorded Member",
    }, family=family)
    view = explain_validated_plan(plan)
    assert AS_OF.isoformat() in view["summary"]
    assert AS_OF.isoformat() in view["target"]


@pytest.mark.parametrize("family", ["term_count", "committee_count"])
def test_family_result_counts_report_the_value_not_just_row_total(family):
    from poc.nlq.stage_a import _member_outcome_plan
    plan = _member_outcome_plan("Recorded Member", AS_OF, {
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Recorded-Member": "Recorded Member",
    }, family=family)
    result = QueryResult("select", ("Count",), (("7",),))
    assert "Returned count: 7" in explain_execution(attempted=True, result=result, plan=plan)["summary"]


def test_member_lookup_does_not_promise_unreturned_service_context():
    from poc.nlq.stage_a import _member_outcome_plan
    plan = _member_outcome_plan("Recorded Member", AS_OF, {
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Recorded-Member": "Recorded Member",
    }, family="member_lookup")
    assert explain_validated_plan(plan)["answer_text"] == "Matching local Member identity information."


@pytest.mark.parametrize("count", [False, True])
def test_shared_constituency_retains_anchor_exclusion_and_term_wide_meaning(count):
    from test_nlq_composable_member_relationship_composition import (
        MemberRelationshipFixture, _anchored_shared_constituency_draft,
        _run as run_members, Q24_NUMBERED_AOIFE, Q24_NUMBERED_AOIFE_COUNT,
    )
    question = Q24_NUMBERED_AOIFE_COUNT if count else Q24_NUMBERED_AOIFE
    outcome, _ = run_members(MemberRelationshipFixture(), question,
                            _anchored_shared_constituency_draft(ordinal=32, count=count))
    assert outcome.status == "success", outcome.diagnostic
    view = explain_validated_plan(outcome.plan, question=question)
    assert "other Members sharing Aoife Byrne's constituency" in view["summary"]
    assert "Dublin Central" in view["summary"]
    assert "32nd Dáil" in view["summary"]
    assert "anchor Member is excluded" in view["summary"]
    assert "Exclude Aoife Byrne by exact Member identity." in view["conditions"]
    assert "not evidence of simultaneous service" in repr(view["conditions"])


def test_unknown_bill_status_can_be_returned_but_not_classified_as_non_enacted():
    from poc.nlq.stage_b import _project_bill_result
    plan = plan_stage_b("What 2024 Bills haven't been enacted", as_of=AS_OF)
    assert plan is not None
    view = explain_validated_plan(plan)
    raw = QueryResult("select", ("bill", "title", "year", "status"),
                      (("https://data.oireachtas.ie/ie/oireachtas/bill/2024/5", "Recorded Bill", "2024", "—"),))
    result, status, _ = _project_bill_result("non_enacted_bills", raw)
    assert status == "incomplete_status_evidence"
    assert "Unknown process status" in repr(result.rows)
    assert "Unclassified records may also be shown" in view["answer_text"]
    assert "may appear separately as unclassified evidence" in repr(view["conditions"])
