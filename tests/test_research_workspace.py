"""Phase 1 acceptance: real compiler + synthetic RDF, never a canned answer."""
import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError
from rdflib import URIRef, Literal
from rdflib.namespace import RDF, XSD

from poc.nlq.errors import NLQError
from poc.nlq.research_adapter import (
    ResearchAdapter, OperationRequest, OperationEnvelope, TERM, MEMBERS, COUNT, QueryTrace,
)
from poc.nlq.research import ResearchRun, BriefProposal, account_brief, compatible
from poc.nlq.research_app import create_app
from functools import partial

# Phase 1 regressions remain executable against their original coordinator.
# The default application now uses the v0.5 collaborator, tested separately.
create_app = partial(create_app, run_factory=ResearchRun)
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates
from test_nlq_seanad_party_periods import _dail_party_fixture, _run_dail
from test_nlq_composable_current_house_membership import (
    ROOT, AGENTS, MEMBERS as NS, HOUSE_GRAPH, DAIL_TERM, DAIL_TERM_33, PARTY_GRAPH,
    IDENTITY_GRAPH, FG_IDENTITY, SKOS, CurrentHouseFixture,
)

AS_OF = date(2026, 11, 11)
BRIEF = "Prepare a short report comparing Fine Gael and Fianna Fáil membership in the current Dáil, including membership totals, the Members involved and a short comparison."
PREDICATES = supported_predicates(ROOT / "ontology")


class Planner:
    def __init__(self, parties=("Fine Gael", "Fianna Fáil")):
        self.parties = parties

    def generate(self, brief):
        return json.dumps({"parties": list(self.parties)})

    def close(self):
        pass


def fixture():
    f, _ = _dail_party_fixture()
    houses = f.dataset.graph(URIRef(HOUSE_GRAPH))
    for term, label, number in [(DAIL_TERM, "34th Dáil", 34), (DAIL_TERM_33, "33rd Dáil", 33)]:
        houses.add((URIRef(term), URIRef(SKOS + "prefLabel"), Literal(label, lang="en")))
        houses.add((URIRef(term), URIRef(AGENTS + "termNo"), Literal(number, datatype=XSD.integer)))
    return f


def request(op=MEMBERS, party="Fine Gael", question=None):
    if question is None:
        question = ("What is the current Dáil term?" if op == TERM else
                    f"Who are the {party} Deputies in the current Dáil?" if op == MEMBERS else
                    f"How many {party} Deputies are in the current Dáil?")
    return OperationRequest(requestId="request-1", requirementId="requirement-1", factualRequest=question,
                            reportingDate=AS_OF.isoformat(), operation={"operation": op, **({"partyMention": party} if op != TERM else {})})


def adapter(f=None):
    return ResearchAdapter(f or fixture(), PREDICATES, context_id="test-run")


@pytest.mark.parametrize("op", [TERM, MEMBERS, COUNT])
def test_closed_positive_contract_schema_trace_and_compiler_parity(op):
    f = fixture()
    result = adapter(f).execute(request(op))
    assert result.outcome == "answer", result.error
    env = result.model_dump()
    Draft202012Validator(OperationEnvelope.model_json_schema(), format_checker=FormatChecker()).validate(env)
    Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text()),
                         format_checker=FormatChecker()).validate(env["plan"])
    assert len(env["execution"]["queries"]) == len(f.queries)
    assert [q["sparql"] for q in env["execution"]["queries"]] == f.queries
    assert all(q["outcome"] == "returned" and q["result"] for q in env["execution"]["queries"])
    assert env["execution"]["datasetContext"]["snapshotId"] is None
    if op != TERM:
        old = _run_dail(request(op).factualRequest, fixture(), count=op == COUNT)
        assert old.status == "success"
        assert env["data"]["value"] == 1
        assert {m["memberIri"] for m in env["data"]["members"]} == {"https://data.oireachtas.ie/ie/oireachtas/member/id/Current-FG"}
        assert len(env["data"]["members"][0]["witnesses"]) == 2  # duplicate qualifying episodes, one identity
        assert env["data"]["members"] == [dict(m, witnesses=[dict(w, queryRefs=[q["queryId"] for q in env["execution"]["queries"]]) for w in m["witnesses"]]) for m in old.accepted_evidence["members"]]
        for w in env["data"]["members"][0]["witnesses"]:
            assert w["termIri"] == DAIL_TERM
            assert w["membership"]["ownerGraph"] is None
            assert w["membership"]["rangeIri"] and w["episode"]["rangeIri"]
            assert "dateTime" in w["episode"]["sourceStart"]


@pytest.mark.parametrize("change", [
    {"extra": "ignored?"}, {"reportingDate": "2026-1-1"}, {"reportingDate": "never"},
    {"operation": {"operation": "sparql", "query": "SELECT"}},
    {"operation": {"operation": MEMBERS, "partyMention": "Fine Gael", "iri": FG_IDENTITY}},
    {"operation": {"operation": TERM, "partyMention": "Fine Gael"}},
    {"operation": {"operation": MEMBERS, "partyMention": ""}},
])
def test_invalid_contracts_never_dispatch(change):
    payload = request().model_dump() | change
    with pytest.raises(ValidationError):
        OperationRequest.model_validate(payload)


@pytest.mark.parametrize("op,question", [
    (MEMBERS, "Who are the Fine Gael Deputies in the current Dáil on 2026-01-01?"),
    (MEMBERS, "Who are the Fine Gael Deputies in the current Dáil who serve on a committee?"),
    (MEMBERS, "Who are the Fine Gael and Fianna Fáil Deputies in the current Dáil?"),
    (COUNT, "Who are the Fine Gael Deputies in the current Dáil?"),
    (MEMBERS, "How many Fine Gael Deputies are in the current Dáil?"),
    (TERM, "Which Dáil was in office on 2026-01-01?"),
    (TERM, "What is the current Dáil term and who sits on a committee?"),
])
def test_unchanged_atomic_request_admission_rejects_loss(op, question):
    f = fixture()
    result = adapter(f).execute(request(op, question=question))
    assert result.outcome != "answer"
    assert result.data is None
    assert f.queries == []
    assert result.request.factualRequest == question


def test_future_and_transport_and_missing_are_not_empty_answers():
    f = fixture()
    future = request().model_dump() | {"reportingDate": "2099-01-01"}
    result = adapter(f).execute(OperationRequest.model_validate(future))
    assert result.outcome == "clarification_required" and not f.queries
    missing = adapter().execute(request(party="Imaginary Absent Party"))
    assert missing.outcome == "missing_or_unaccepted_evidence" and missing.data is None

    class Broken:
        def query(self, q):
            raise NLQError("Injected transport failure")

    broken = adapter(Broken()).execute(request())
    assert broken.outcome == "execution_failure"
    assert broken.data is None
    assert broken.execution["queries"][0]["outcome"] == "execution_failure"
    assert broken.execution["queries"][0]["result"] is None


def test_non_nlq_client_failure_is_still_traced_execution_failure():
    class Broken:
        def query(self, q):
            raise RuntimeError("arbitrary transport library error")
    env = adapter(Broken()).execute(request())
    assert env.outcome == "execution_failure" and env.data is None
    assert env.execution["queries"][0]["outcome"] == "execution_failure"


def test_payload_shape_and_trace_loss_fail_closed(monkeypatch):
    from poc.nlq import research_adapter
    result = adapter().execute(request())
    original = result.model_dump()
    invalid = copy.deepcopy(original)
    invalid["data"]["members"][0]["witnesses"] = []
    with pytest.raises(ValidationError):
        OperationEnvelope.model_validate(invalid)
    with pytest.raises(Exception):
        Draft202012Validator(OperationEnvelope.model_json_schema()).validate(invalid)
    from poc.nlq.composable_plan import PlanOutcome
    monkeypatch.setattr(research_adapter, "execute_question", lambda *a, **kw: PlanOutcome(
        "success", plan=result.plan, result=QueryResult("select", ("TD", "Member identity"),
            tuple((m["displayName"], m["memberIri"]) for m in original["data"]["members"])),
        accepted_evidence={"members": original["data"]["members"]}))
    no_trace = adapter().execute(request())
    assert no_trace.outcome == "validation_failure" and no_trace.data is None
    assert no_trace.error["code"] == "evidence_integrity_failure"


def test_unexpected_projection_failure_keeps_executed_query_trace(monkeypatch):
    from poc.nlq import research_adapter
    original = research_adapter.execute_question
    def broken_projection(*args, **kwargs):
        from dataclasses import replace
        outcome = original(*args, **kwargs)
        assert outcome.status == "success"
        return replace(outcome, accepted_evidence={"members": [{"memberIri": "bad-shape"}]})
    monkeypatch.setattr(research_adapter, "execute_question", broken_projection)
    f = fixture()
    env = adapter(f).execute(request())
    assert env.outcome == "validation_failure" and env.data is None
    assert len(env.execution["queries"]) == len(f.queries) == 4
    assert all(q["outcome"] == "returned" for q in env.execution["queries"])


def test_schema_alignment_does_not_admit_nonparty_or_empty_selected_iris():
    env = adapter().execute(request()).model_dump()
    schema = Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text()),
                                 format_checker=FormatChecker())
    for field, value in [("selectedIRIs", []), ("selectedIRIs", ["not-an-iri"]), ("type", "Member")]:
        plan = copy.deepcopy(env["plan"])
        plan["referents"]["party"][field] = value
        assert not schema.is_valid(plan)


@pytest.mark.parametrize("defect", ["missing", "conflicting", "reversed", "datatype", "wrong_type"])
def test_invalid_temporal_witnesses_do_not_leak_partial_selections(defect):
    f = fixture()
    graph = f.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Current-FG"))
    episode = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/Current-FG#party-episode")
    dr = next(graph.objects(episode, URIRef(NS + "hasMembershipDateRange")))
    start = URIRef(NS + "StartDate")
    if defect == "missing":
        graph.remove((dr, start, None))
    elif defect == "conflicting":
        graph.add((dr, start, Literal("2025-02-01T00:00:00", datatype=XSD.dateTime)))
    elif defect == "reversed":
        graph.add((dr, URIRef(NS + "EndDate"), Literal("2024-01-01T00:00:00", datatype=XSD.dateTime)))
    elif defect == "datatype":
        graph.remove((dr, start, None)); graph.add((dr, start, Literal("2025-01-01", datatype=XSD.date)))
    else:
        graph.remove((dr, RDF.type, None))
    result = adapter(f).execute(request())
    assert result.outcome != "answer", result
    assert result.data is None


@pytest.mark.parametrize("defect", ["missing_house", "ambiguous_identity", "missing_identity", "no_qualifying_paths"])
def test_evidence_gaps_never_become_zero(defect):
    f = fixture()
    if defect == "missing_house":
        f.dataset.graph(URIRef(HOUSE_GRAPH)).remove((URIRef(DAIL_TERM), URIRef(SKOS + "prefLabel"), None))
        result = adapter(f).execute(request(TERM))
    else:
        if defect in {"missing_identity", "ambiguous_identity"}:
            graph = f.dataset.graph(URIRef(IDENTITY_GRAPH))
            if defect == "missing_identity":
                graph.remove((None, URIRef(NS + "hasPoliticalAffiliationIdentity"), URIRef(FG_IDENTITY)))
            else:
                other = URIRef(FG_IDENTITY + "-other")
                graph.add((other, RDF.type, URIRef(NS + "PoliticalAffiliationIdentity")))
                graph.add((other, URIRef(SKOS + "prefLabel"), Literal("Fine Gael", lang="en")))
                for party in list(graph.subjects(URIRef(NS + "hasPoliticalAffiliationIdentity"), URIRef(FG_IDENTITY))):
                    graph.add((party, URIRef(NS + "hasPoliticalAffiliationIdentity"), other))
        else:
            for graph in f.dataset.graphs():
                for episode in list(graph.subjects(RDF.type, URIRef(NS + "PartyMembership"))):
                    graph.remove((episode, URIRef(NS + "inOireachtasMembership"), None))
        result = adapter(f).execute(request(COUNT))
    assert result.outcome != "answer" and result.data is None


def test_page_two_accepted_witnesses_and_trace_retained_and_exhaustion_fails_closed():
    # Paginate actual compiler evidence with 101 distinct Members. Copies below
    # are synthetic RDF test generation, not source or golden fixture changes.
    f = fixture()
    original = f.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/Current-FG"))
    triples = list(original)
    for i in range(100):
        def rewrite(value):
            return URIRef(str(value).replace("Current-FG", f"Copy-{i:03}")) if isinstance(value, URIRef) else value
        target = f.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/Copy-{i:03}"))
        for s, p, o in triples:
            # Keep the real term-scoped party identities (not graph-owned).
            changed_o = o if isinstance(o, URIRef) and "/party/dail/" in str(o) else rewrite(o)
            target.add((rewrite(s), p, changed_o))
    env = adapter(f).execute(request(COUNT))
    assert env.outcome == "answer", env.error
    assert env.data["value"] == 101
    assert len(env.data["members"]) == 101
    assert any(q["offset"] >= 100 for q in env.execution["queries"])
    assert all(q["result"] is not None for q in env.execution["queries"])

    class Exhausted:
        def query(self, q):
            raw = f.query(re.sub(r" OFFSET \d+$", "", q))
            if "?membershipRange" in q and "?memberName" in q:
                return QueryResult("select", raw.columns, raw.rows[:100])
            return raw
    exhausted = adapter(Exhausted()).execute(request(COUNT))
    assert exhausted.outcome != "answer" and exhausted.data is None
    assert len(exhausted.execution["queries"]) >= 101


@pytest.mark.parametrize("brief,parties", [
    (BRIEF + " Include committee memberships.", ["Fine Gael", "Fianna Fáil"]),
    (BRIEF, ["Fine Gael"]),
    (BRIEF + " on 2025-01-01", ["Fine Gael", "Fianna Fáil"]),
    (BRIEF + " excluding former ministers", ["Fine Gael", "Fianna Fáil"]),
    ("Compare Fine Gael and Fianna Fáil Members with office in the current Dáil", ["Fine Gael", "Fianna Fáil"]),
    ("Who is in office in the current Dáil?", []),
    ("Report representation in the current Dáil", []),
    ("Report Fine Gael membership totals in the current Dáil and a short comparison", ["Fine Gael"]),
    ("Compare Fine Gael and Fianna Fáil in the 33rd Dáil", ["Fine Gael", "Fianna Fáil"]),
    (BRIEF, ["Fianna Fáil", "Fine Gael"]),
])
def test_original_requirement_accounting_refuses_loss(brief, parties):
    assert account_brief(brief, BriefProposal(parties=parties)) is not None
    f = fixture()
    run = ResearchRun(brief, AS_OF, adapter(f), lambda: Planner(parties))
    while any(t["state"] == "Pending" for t in run.tasks):
        run.step(run.version)
    assert not any(t.get("operation") in {MEMBERS, COUNT} for t in run.tasks)
    assert run.unanswered and run.brief == brief


def test_other_eligible_party_name_is_not_hardcoded():
    f = fixture()
    # Rename the reviewed synthetic identity label, not an application registry.
    graph = f.dataset.graph(URIRef(IDENTITY_GRAPH))
    graph.remove((URIRef(FG_IDENTITY), URIRef(SKOS + "prefLabel"), None))
    graph.add((URIRef(FG_IDENTITY), URIRef(SKOS + "prefLabel"), Literal("Labour Party", lang="en")))
    brief = "Report membership totals and Members for Labour Party in the current Dáil."
    assert account_brief(brief, BriefProposal(parties=["Labour Party"])) is None
    run = ResearchRun(brief, AS_OF, adapter(f), lambda: Planner(["Labour Party"]))
    while any(t["state"] == "Pending" for t in run.tasks):
        run.step(run.version)
    assert run._section("party-0")["state"] == "Validated"
    assert run._section("party-0")["count"] == 1


def test_explicit_term_only_brief_has_one_supported_plan_task():
    brief = "What is the current Dáil term?"
    assert account_brief(brief, BriefProposal(parties=[])) is None
    run = ResearchRun(brief, AS_OF, adapter(), lambda: Planner([]))
    assert len(run.tasks) == 1 and run.tasks[0]["operation"] == TERM
    run.step(0)
    assert run._section("term")["state"] == "Validated"
    assert not run.unanswered


def complete_run(f=None):
    run = ResearchRun(BRIEF, AS_OF, adapter(f), Planner)
    while any(t["state"] == "Pending" for t in run.tasks):
        run.step(run.version)
    return run


def test_progressive_plan_precedes_execution_export_and_idempotence():
    f = fixture()
    run = ResearchRun(BRIEF, AS_OF, adapter(f), Planner)
    initial = run.view()
    assert initial["status"] == "Plan published" and not f.queries
    assert len(initial["tasks"]) == 6 and all(t["state"] == "Pending" for t in initial["tasks"])
    run.step(0)
    assert run._section("term")["state"] == "Validated"
    count = len(f.queries)
    run.step(0)  # retransmission cannot repeat query
    assert len(f.queries) == count
    run.step(1)
    assert run._section("party-0")["members"] and run._section("party-0")["count"] is None
    assert run._section("party-1")["state"] == "Pending"
    assert "Pending" in run.markdown() and "freshness" in run.markdown()
    assert "Report state: Incomplete" in run.markdown()
    while any(t["state"] == "Pending" for t in run.tasks):
        run.step(run.version)
    assert all(t["state"] == "Validated" for t in run.tasks), run.tasks
    assert run._section("comparison")["calculation"]["differences"][0]["leftMinusRight"] == 0
    md = run.markdown()
    assert "not snapshot-consistent" in md and "uncertified" in md and "```json" in md
    assert "Report state: Qualified local findings" in md
    assert "rangeIri" in md and "sourceStart" in md
    assert all(eid in md for eid in run.evidence)


@pytest.mark.parametrize("path,value", [
    (("resolvedScope", "reportingDate"), "2025-01-01"),
    (("resolvedScope", "term"), {"iri": "https://example.org/other-term"}),
    (("execution", "datasetContext"), {"endpointId": "different"}),
    (("data", "unit"), "seats"),
    (("completeness", "enumeration"), "incomplete"),
    (("completeness", "sourceCoverage"), "different"),
    (("completeness", "limitations"), ["different qualification"]),
])
def test_incompatible_calculation_refused_without_removing_findings(path, value):
    run = complete_run()
    first = run.evidence[run.tasks[2]["evidenceRef"]]
    second = copy.deepcopy(run.evidence[run.tasks[4]["evidenceRef"]])
    second[path[0]][path[1]] = value
    assert not compatible(first, second)
    assert run._section("party-0")["count"] == run._section("party-1")["count"] == 1


def test_term_mismatch_and_independent_failure_preserve_accepted_findings():
    f = fixture()
    a = adapter(f)
    execute = a.execute
    def mismatch(req):
        env = execute(req)
        if req.requirementId.startswith("party-1") and env.outcome == "answer":
            env.resolvedScope["term"]["iri"] = DAIL_TERM_33
        return env
    a.execute = mismatch
    run = ResearchRun(BRIEF, AS_OF, a, Planner)
    while any(t["state"] == "Pending" for t in run.tasks):
        run.step(run.version)
    assert run._section("party-0")["count"] == 1
    assert run._section("party-1")["state"] == "Incomplete"
    assert run._section("comparison")["state"] == "Blocked"

    class LaterFailure:
        def query(self, q):
            if "/Current-FF>" in q:
                raise NLQError("Injected endpoint unavailable")
            return f.query(q)
    run = complete_run(LaterFailure())
    assert run._section("party-0")["state"] == "Validated"
    assert run._section("party-1")["state"] == "Incomplete"
    assert any(t["state"] == "Execution failed" for t in run.tasks)
    assert "Current Fine Gael" in run.markdown() and "Execution failed" in run.markdown()


def test_count_observation_disagreement_blocks_total_not_member_table():
    a = adapter()
    execute = a.execute
    def changed_selection(req):
        result = execute(req)
        if req.operation.operation == COUNT and req.operation.partyMention == "Fine Gael":
            result.data["members"][0]["witnesses"][0]["episode"]["resourceIri"] += "-changed"
        return result
    a.execute = changed_selection
    run = ResearchRun(BRIEF, AS_OF, a, Planner)
    while any(t["state"] == "Pending" for t in run.tasks):
        run.step(run.version)
    assert run._section("party-0")["members"]
    assert run._section("party-0")["count"] is None
    assert run._section("party-0")["state"] == "Incomplete"
    assert run._section("party-1")["state"] == "Validated"
    assert run._section("comparison")["state"] == "Blocked"


def test_http_publication_evidence_export_and_strict_transport():
    f = fixture()
    with TestClient(create_app(planner_factory=Planner, client_factory=lambda: f, reporting_date=AS_OF)) as c:
        home = c.get("/")
        assert home.status_code == 200 and 'id="report-sections"' in home.text
        assert "script-src 'self'" in home.headers["content-security-policy"]
        plan = c.post("/runs", json={"brief": BRIEF}).json()
        assert not f.queries and plan["status"] == "Plan published"
        assert c.post("/runs", json={"brief": BRIEF, "sparql": "SELECT"}).status_code == 422
        assert c.post(f"/runs/{plan['id']}/step", json={"version": 0, "force": True}).status_code == 422
        state = c.post(f"/runs/{plan['id']}/step", json={"version": 0}).json()
        eid = state["tasks"][0]["evidenceRef"]
        assert c.get(f"/runs/{plan['id']}/evidence/{eid}").json()["data"]["term"]["iri"] == DAIL_TERM
        md = c.get(f"/runs/{plan['id']}/report.md").text
        assert "Pending" in md and "uncertified" in md
        assert c.get("/runs/unknown").status_code == 404
        assert c.post("/runs", json={"brief": BRIEF}, headers={"origin": "https://untrusted.example"}).status_code == 403


def test_client_setup_failure_retains_structured_execution_failure():
    def unavailable():
        raise RuntimeError("client setup unavailable")
    with TestClient(create_app(planner_factory=Planner, client_factory=unavailable, reporting_date=AS_OF)) as c:
        plan = c.post("/runs", json={"brief": BRIEF}).json()
        response = c.post(f"/runs/{plan['id']}/step", json={"version": 0})
        assert response.status_code == 200
        state = response.json()
        assert state["tasks"][0]["state"] == "Execution failed"
        eid = state["tasks"][0]["evidenceRef"]
        assert c.get(f"/runs/{plan['id']}/evidence/{eid}").json()["outcome"] == "execution_failure"


def create_browser_app():
    """Used by tools/verify_research_browser.py; actual compiler + synthetic RDF."""
    import os
    f = fixture()
    if os.getenv("RESEARCH_BROWSER_FAILURE"):
        original = f.query
        def fail(q):
            if "/Current-FF>" in q:
                raise NLQError("Injected unavailable endpoint")
            return original(q)
        f.query = fail
    return create_app(planner_factory=Planner, client_factory=lambda: f, reporting_date=AS_OF)
