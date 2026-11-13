"""Synthetic RDF and HTTP/browser integration; no frozen/source fixtures changed."""

from copy import deepcopy
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import XSD

from poc.nlq.app import create_app
from poc.nlq.composition_kernel import Budget, graph, iri, retrieve, term_lookup
from poc.nlq.composition_transport import CompositionTransport, decode_select
from poc.nlq.composition_workflow import execute_confirmed, propose, validate_scope
from poc.nlq.errors import NLQError


QUESTION = "Which members of the Committee on Public Accounts currently represent Kildare North?"
NAMES = ("Committee on Public Accounts", "Kildare North")
BASE = "https://data.oireachtas.ie/"


class Proposer:
    calls = 0

    def generate(self, question):
        type(self).calls += 1
        return json.dumps(dict(supported=True, committee=NAMES[0], constituency=NAMES[1], reason=None))

    def close(self):
        pass


def spec(as_of="2026-05-01"):
    return propose(QUESTION, as_of, Proposer)


def synthetic_dataset():
    """New synthetic data only. Deliberately different K/R HouseTerms."""
    ds = Dataset()

    def add(owner, subject, predicate, object_):
        ds.graph(owner).add((subject, iri(predicate), object_))

    dail, seanad = URIRef(BASE + "test/dail"), URIRef(BASE + "test/seanad")
    for term, house in ((dail, "Dail"), (seanad, "Seanad")):
        add(graph("houses"), term, "rdf:type", iri("agents:" + house + "Term"))
        add(graph("houses"), term, "agents:termOf", URIRef(BASE + "house/" + house.lower()))
        period = URIRef(str(term) + "#period")
        add(graph("houses"), term, "dct:temporal", period)
        add(graph("houses"), period, "rdf:type", iri("dct:PeriodOfTime"))
        add(graph("houses"), period, "dcat:startDate", Literal("2024-01-01", datatype=XSD.date))
    committee, constituency = URIRef(BASE + "test/committee"), URIRef(BASE + "test/constituency")

    def interval(owner, resource, start, end=None, committee=False):
        range_ = URIRef(str(resource) + "#range")
        add(owner, resource, "members:hasCommitteeDateRange" if committee else "members:hasMembershipDateRange", range_)
        add(owner, range_, "rdf:type", iri("members:DateRange"))
        add(owner, range_, "members:StartDate", Literal(start + "T00:00:00", datatype=XSD.dateTime, normalize=False))
        if end:
            add(owner, range_, "members:EndDate", Literal(end + "T00:00:00", datatype=XSD.dateTime, normalize=False))

    for resource, family, type_, label, term in (
        (committee, "committees", "Committee", "Committee of Public Accounts", seanad),
        (constituency, "constituencies", "DailConstituency", NAMES[1], dail),
    ):
        add(graph(family), resource, "rdf:type", iri("members:" + type_))
        add(graph(family), resource, "skos:prefLabel", Literal(label, lang="en"))
        add(graph(family), resource, "members:committeeInHouseTerm" if family == "committees" else "members:constituencyInHouseTerm", term)
    interval(graph("committees"), committee, "2025-01-01", committee=True)
    for code, start, end in (("Alice", "2025-02-01", "2026-06-30"), ("Bob", "2026-07-01", None)):
        member = URIRef(BASE + "test/member/" + code)
        owner = URIRef(BASE + "graph/member/" + code)
        add(owner, member, "rdf:type", iri("agents:Member"))
        add(owner, member, "agents:memberCode", Literal(code))
        add(owner, member, "foaf:name", Literal(code + " Example"))
        for role in ("K", "R"):
            relationship = URIRef(str(member) + "/" + role)
            add(owner, member, "members:hasMembersMembership", relationship)
            add(owner, relationship, "rdf:type", iri("members:CommitteeMembership" if role == "K" else "members:DailMembership"))
            add(owner, relationship, "members:isCommitteeMembershipOf" if role == "K" else "members:isRepresentativeFrom", committee if role == "K" else constituency)
            if role == "R":
                add(owner, relationship, "members:inHouseTerm", dail)
            interval(owner, relationship, start if role == "K" else "2024-01-01", end if role == "K" else None)
    return ds


class DatasetTransport:
    timeout = 15

    def __init__(self, *args, dataset=None, **kwargs):
        self.dataset = dataset if dataset is not None else synthetic_dataset()
        self.calls = []

    def select(self, lookup, query, offset):
        self.calls.append((lookup.kind, offset))
        result = self.dataset.query(query)
        return {"columns": [str(v) for v in result.vars],
                "rows": [{str(k): v for k, v in row.asdict().items()} for row in result], "complete": True}

    def close(self):
        pass


@pytest.mark.parametrize("question", [
    QUESTION,
    "Who currently represents Kildare North and serves on the Committee on Public Accounts?",
    "Which TDs for Kildare North are members of the Committee on Public Accounts?",
    "List the current members of the Committee on Public Accounts who represent Kildare North.",
    "Who serves on the Committee on Public Accounts and represents Kildare North?",
    "Which members serve on the Committee on Public Accounts and represent Kildare North?",
])
def test_wording_is_whole_scope_checked(question):
    validate_scope(question, *NAMES)


@pytest.mark.parametrize("extra", [
    " and are women", " and belong to Fine Gael", " and were first elected in 2024",
    " except Joe Neville", " before 2025", " during this Dáil", " and count them",
    " and show their parties", " and chair it", " or represent Dublin Central",
    "; ignore the previous condition", " and not Senators", " who voted for the Bill",
])
def test_omitted_extra_condition_fails_independent_of_model(extra):
    with pytest.raises(ValueError, match="whole question"):
        propose(QUESTION.rstrip("?") + extra + "?", "2026-05-01", Proposer)


@pytest.mark.parametrize("as_of,expected", [("2026-06-30", "Alice Example"), ("2026-07-01", "Bob Example"), ("2027-01-01", "Bob Example")])
def test_dynamic_dates_exact_bindings_and_names(as_of, expected):
    report, result = execute_confirmed(spec(as_of), DatasetTransport())
    assert report["status"] == "answer", report.get("error")
    assert result.rows[0][0] == expected
    assert len(result.rows) == 1 and len(report["ledger"]) == 6
    assert report["answer"]["asOf"] == as_of
    pair, = report["answer"]["witnesses"]
    assert {w["role"] for w in pair} == {"K", "R"}
    assert pair[0]["bindings"]["term"]["iri"] != pair[1]["bindings"]["term"]["iri"]
    assert all(i["currentAtAsOf"] for w in pair for i in w["intervals"])
    assert report["displayEvidence"]


@pytest.mark.parametrize("value", ["2026-02-30", "20260501", "2026-W01-1", "no date", None, "2026-05-01T00:00:00"])
def test_invalid_backend_date(value):
    with pytest.raises(ValueError):
        spec(value)


def test_missing_nonqualifying_candidate_evidence_fails_whole_selection():
    ds = synthetic_dataset()
    owner = ds.graph(URIRef(BASE + "graph/member/Bob"))
    owner.remove((URIRef(BASE + "test/member/Bob/K#range"), iri("members:StartDate"), None))
    report, result = execute_confirmed(spec(), DatasetTransport(dataset=ds))
    assert report["status"] == "nonanswer" and result is None and "answer" not in report
    assert "Missing/conflicting" in report["error"]


def test_ambiguous_current_committee_does_not_select_identity():
    ds = synthetic_dataset()
    source = URIRef(BASE + "test/committee")
    for s, p, o in list(ds.graph(graph("committees"))):
        if s == source:
            ds.graph(graph("committees")).add((URIRef(str(source) + "-other"), p, o))
    report, result = execute_confirmed(spec(), DatasetTransport(dataset=ds))
    assert result is None and "Ambiguous" in report["error"]


def test_missing_name_cannot_be_inferred_from_member_iri():
    ds = synthetic_dataset()
    ds.graph(URIRef(BASE + "graph/member/Alice")).remove((None, iri("foaf:name"), None))
    report, result = execute_confirmed(spec(), DatasetTransport(dataset=ds))
    assert result is None and "answer" not in report and report["status"] == "nonanswer"


def test_all_recorded_member_names_are_preserved_without_selecting_a_winner():
    ds = synthetic_dataset()
    ds.graph(URIRef(BASE + "graph/member/Alice")).add((URIRef(BASE + "test/member/Alice"), iri("foaf:name"), Literal("Alice Alternative")))
    report, result = execute_confirmed(spec(), DatasetTransport(dataset=ds))
    member = BASE + "test/member/Alice"
    assert report["status"] == "answer"
    assert report["recordedNames"][member] == ["Alice Alternative", "Alice Example"]
    assert result.rows[0][0] == "Alice Alternative / Alice Example"
    assert {f["object"]["value"] for f in report["displayEvidence"]} == {"Alice Alternative", "Alice Example"}


def test_canonically_equivalent_unicode_names_reach_grounded_identity():
    ds = synthetic_dataset()
    owner = ds.graph(graph("constituencies"))
    resource = URIRef(BASE + "test/constituency")
    owner.set((resource, iri("skos:prefLabel"), Literal("Dún Laoghaire", lang="en")))
    decomposed = "Du\u0301n Laoghaire"
    question = QUESTION.replace("Kildare North", decomposed)
    validate_scope(question, NAMES[0], "Dún Laoghaire")
    request = spec()
    request["requiredSelections"][1]["constituency"]["mention"] = decomposed
    report, result = execute_confirmed(request, DatasetTransport(dataset=ds))
    assert report["status"] == "answer" and result.rows[0][0] == "Alice Example"


def test_empty_is_nonanswer_not_certified_empty_roster():
    report, result = execute_confirmed(spec("2024-05-01"), DatasetTransport())
    assert result is None and report["status"] == "nonanswer" and "answer" not in report


def test_display_lookup_uses_same_whole_plan_budget():
    budget = Budget()
    dummy = "SELECT ?s WHERE { VALUES ?s { <https://data.oireachtas.ie/test> } } LIMIT 100"
    for _ in range(3):
        budget.request(dummy, 15)
    report, result = execute_confirmed(spec(), DatasetTransport(), budget=budget)
    assert result is None and "answer" not in report and len(budget.requests) == 8
    assert "budget" in report["error"]


def test_completion_pages_charged_and_budget_exhaustion_fails_closed():
    class Full:
        timeout = 15
        calls = 0

        def select(self, *args):
            self.calls += 1
            return dict(columns=["term"], rows=[{"term": URIRef(BASE + "test")}]*100, complete=True)
    transport, budget = Full(), Budget()
    with pytest.raises(NLQError, match="budget"):
        retrieve(term_lookup(), transport, budget)
    assert transport.calls == len(budget.requests) == 8
    assert [r["offset"] for r in budget.requests] == list(range(0, 800, 100))


def test_whole_plan_raw_and_intermediate_limits_are_not_relaxed():
    budget = Budget()
    budget.rows([{}] * 100)
    budget.witnesses([()] * 100)
    with pytest.raises(NLQError): budget.rows([{}] * 101)
    with pytest.raises(NLQError): budget.witnesses([()] * 101)


def test_extracted_kernel_preserves_frozen_typed_projection_at_original_date():
    from poc.nlq.experimental_composition import execute as frozen_execute
    from poc.nlq.experimental_composition import owner_lookup as frozen_owner_lookup
    from poc.nlq.composition_kernel import execute, owner_lookup
    request = spec("2026-11-11")
    request["requiredSelections"][0]["committee"] = BASE + "test/committee"
    request["requiredSelections"][1]["constituency"] = BASE + "test/constituency"
    for selection in request["requiredSelections"]:
        current = {"Dail": URIRef(BASE + "test/dail")}
        assert owner_lookup(selection, current).query() == frozen_owner_lookup(selection, current).query()
    expected = frozen_execute(request, request, DatasetTransport())
    actual = execute(request, DatasetTransport())
    assert expected["status"] == actual["status"] == "answer"
    for field in ("answer", "validatedWitnesses", "structure", "intermediate"):
        assert actual[field] == expected[field]


def test_iri_target_preserves_frozen_case_sensitive_constituency_matching():
    from poc.nlq.experimental_composition import execute as frozen_execute
    from poc.nlq.composition_kernel import execute
    ds = synthetic_dataset()
    original, other = URIRef(BASE + "test/constituency"), URIRef(BASE + "test/OTHER")
    owner = ds.graph(graph("constituencies"))
    for _, p, o in list(owner.triples((original, None, None))):
        owner.add((other, p, Literal("KILDARE NORTH", lang="en") if p == iri("skos:prefLabel") else o))
    request = spec("2026-11-11")
    request["requiredSelections"][0]["committee"] = BASE + "test/committee"
    request["requiredSelections"][1]["constituency"] = str(original)
    expected = frozen_execute(request, request, DatasetTransport(dataset=ds))
    actual = execute(request, DatasetTransport(dataset=ds))
    assert actual["status"] == expected["status"] == "answer"
    assert actual["answer"] == expected["answer"]


@pytest.mark.parametrize("mutation", ["count", "missing_interval", "third_selection", "incompatible_binding"])
def test_semantic_obligation_changes_refused_before_transport(mutation):
    request = spec()
    if mutation == "count": request["answer"]["shape"] = "count"
    elif mutation == "missing_interval": request["currentAtRoles"].pop()
    elif mutation == "third_selection": request["requiredSelections"].append(deepcopy(request["requiredSelections"][0]))
    elif mutation == "incompatible_binding": request["exactSharedBindings"].append("K.membership=R.parliamentaryMembership")
    from poc.nlq.composition_kernel import execute
    transport = DatasetTransport()
    report = execute(request, transport)
    assert report["status"] == "semantic_rejection" and transport.calls == []


def test_incomplete_page_is_not_a_short_complete_page():
    class Incomplete(DatasetTransport):
        def select(self, *args):
            return {**super().select(*args), "complete": False}
    report, result = execute_confirmed(spec(), Incomplete())
    assert result is None and "Incomplete" in report["error"]


def client(monkeypatch, tmp_path, *, transport=DatasetTransport):
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-05-01")
    return TestClient(create_app(feedback_directory=tmp_path, composition_proposer_factory=Proposer,
                                 composition_transport_factory=transport))


def proposal_token(client):
    response = client.post("/composition/propose", data={"question": QUESTION})
    assert response.status_code == 200 and "Inspect the interpretation" in response.text
    return re.search(r'name="token" value="([^"]+)"', response.text)[1]


def test_explicit_confirmation_no_second_model_call_and_evidence(monkeypatch, tmp_path):
    c = client(monkeypatch, tmp_path)
    before = Proposer.calls
    token = proposal_token(c)
    assert Proposer.calls == before + 1
    response = c.post("/composition/confirm", data={"token": token, "decision": "confirm"})
    assert Proposer.calls == before + 1
    assert "Alice Example" in response.text and "Dáil constituency representation" in response.text
    assert "not a certified complete roster" in response.text and "2026-05-01" in response.text
    link = re.search(r'href="(/composition/evidence/[^"]+)"', response.text)[1]
    artifact = c.get(link).json()
    assert artifact["question"] == QUESTION and artifact["confirmedRequest"]["asOf"] == "2026-05-01"
    assert len(artifact["report"]["ledger"]) == 6
    assert "already used" in c.post("/composition/confirm", data={"token": token, "decision": "confirm"}).text
    other = TestClient(c.app)
    assert other.get(link).status_code == 404


@pytest.mark.parametrize("change", ["reject", "question", "date", "session", "newer", "expired", "extra", "duplicate"])
def test_confirmation_binding_and_rejection(monkeypatch, tmp_path, change):
    class NoExecution:
        def __init__(self, *a, **k):
            pytest.fail("Altered/stale/rejected interpretation must never execute")
    c = client(monkeypatch, tmp_path, transport=NoExecution)
    token = proposal_token(c)
    form = {"token": token, "decision": "confirm"}
    if change == "reject": form["decision"] = "reject"
    elif change == "question": form["question"] = "Different question"
    elif change == "date": monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-05-02")
    elif change == "session": c.cookies.clear()
    elif change == "newer": proposal_token(c)
    elif change == "expired":
        from poc.nlq import composition_routes
        now = composition_routes.monotonic()
        monkeypatch.setattr(composition_routes, "monotonic", lambda: now + 601)
    elif change == "extra": form["plan"] = "{}"
    elif change == "duplicate":
        response = c.post("/composition/confirm", content=f"token={token}&decision=confirm&decision=reject", headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert "Altered" in response.text
        return
    response = c.post("/composition/confirm", data=form)
    assert any(word in response.text for word in ("rejected", "Altered", "changed", "expired"))


def test_cross_origin_confirmation_refused(monkeypatch, tmp_path):
    c = client(monkeypatch, tmp_path)
    token = proposal_token(c)
    assert c.post("/composition/confirm", data={"token": token, "decision": "confirm"}, headers={"Origin": "https://attacker.invalid"}).status_code == 403


def test_failed_new_question_invalidates_old_confirmation(monkeypatch, tmp_path):
    c = client(monkeypatch, tmp_path)
    token = proposal_token(c)
    c.post("/composition/propose", data={"question": QUESTION.rstrip("?") + " and belong to Fine Gael?"})
    response = c.post("/composition/confirm", data={"token": token, "decision": "confirm"})
    assert "expired or already used" in response.text and "Alice Example" not in response.text


def test_evidence_byte_cap_never_silently_truncates_answer(monkeypatch, tmp_path):
    from poc.nlq import composition_routes
    c = client(monkeypatch, tmp_path)
    token = proposal_token(c)
    monkeypatch.setattr(composition_routes, "MAX_EVIDENCE_BYTES", 1)
    response = c.post("/composition/confirm", data={"token": token, "decision": "confirm"})
    assert "Evidence storage byte budget exceeded" in response.text and 'id="query-results"' not in response.text


def test_evidence_storage_evicts_whole_old_artifacts_not_facts(monkeypatch, tmp_path):
    from poc.nlq import composition_routes
    c = client(monkeypatch, tmp_path)
    def run():
        response = c.post("/composition/confirm", data={"token": proposal_token(c), "decision": "confirm"})
        return re.search(r'href="(/composition/evidence/[^"]+)"', response.text)[1]
    first = run()
    artifact = c.get(first).json()
    monkeypatch.setattr(composition_routes, "MAX_EVIDENCE_BYTES", int(len(json.dumps(artifact, ensure_ascii=False).encode("utf-8")) * 1.5))
    second = run()
    assert c.get(first).status_code == 404
    assert c.get(second).json()["report"]["answer"]["witnesses"] == artifact["report"]["answer"]["witnesses"]


def test_out_of_order_model_responses_cannot_restore_stale_interpretation(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    c = client(monkeypatch, tmp_path)
    proposal_token(c)  # Establish the browser's HttpOnly session cookie.
    entered, release = Event(), Event()
    real_generate = Proposer.generate

    def generate(self, question):
        if question == QUESTION:
            entered.set()
            assert release.wait(10)
        return real_generate(self, question)
    monkeypatch.setattr(Proposer, "generate", generate)
    with ThreadPoolExecutor() as pool:
        older = pool.submit(c.post, "/composition/propose", data={"question": QUESTION})
        assert entered.wait(10)
        try:
            newer = c.post("/composition/propose", data={"question": "Who currently represents Kildare North and serves on the Committee on Public Accounts?"})
            token = re.search(r'name="token" value="([^"]+)"', newer.text)[1]
        finally:
            release.set()
        assert "newer question superseded" in older.result().text
        response = c.post("/composition/confirm", data={"token": token, "decision": "confirm"})
        assert "Alice Example" in response.text


@pytest.mark.parametrize("failure,expected", [("timeout", "timed out"), ("redirect", "HTTP 302"),
                                             ("content", "SPARQL Results JSON"), ("json", "unreadable"),
                                             ("duplicate", "unreadable"), ("bytes", "byte budget")])
def test_transport_failures_never_supply_complete_partial_page(failure, expected):
    def handler(request):
        if failure == "timeout": raise httpx.ReadTimeout("test timeout")
        if failure == "redirect": return httpx.Response(302, headers={"location": "https://other.invalid/query"})
        if failure == "content": return httpx.Response(200, text="[]")
        body = b'{"head":{"vars":[]},"results":{"bindings":[]}}'
        if failure == "json": body = body[:-1]
        elif failure == "duplicate": body = b'{"head":{"vars":[]},"head":{"vars":[]},"results":{"bindings":[]}}'
        elif failure == "bytes": body = b" " * (2 * 1024 * 1024 + 1)
        return httpx.Response(200, content=body, headers={"content-type": "application/sparql-results+json"})
    transport = CompositionTransport("http://fuseki.example/dataset/query", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(NLQError, match=expected): transport.select(None, "SELECT ?x WHERE {} LIMIT 100", 0)
    finally:
        transport.close()


def test_transport_sends_unchanged_query_with_configured_auth():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, headers={"content-type": "application/sparql-results+json"}, json={
            "head": {"vars": ["x"]}, "results": {"bindings": [{"x": {"type": "literal", "value": "2026-05-01T00:00:00", "datatype": str(XSD.dateTime)}}]}})
    transport = CompositionTransport("https://fuseki.example/dataset/query", username="user", password="password", transport=httpx.MockTransport(handler))
    try:
        query = "SELECT ?x WHERE { VALUES ?x { 1 } } LIMIT 100"
        response = transport.select(None, query, 0)
        assert response["complete"] is True
        assert str(response["rows"][0]["x"]) == "2026-05-01T00:00:00"
        from urllib.parse import parse_qs
        assert parse_qs(requests[0].content.decode()) == {"query": [query]}
        assert requests[0].headers["authorization"].startswith("Basic ")
        assert requests[0].extensions["timeout"]["read"] == 15
    finally:
        transport.close()


@pytest.mark.parametrize("bad", [
    {"head": {"vars": ["x"]}, "results": {"bindings": [{"x": {"type": "bnode", "value": "a"}}]}},
    {"head": {"vars": ["x", "x"]}, "results": {"bindings": []}},
    {"head": {"vars": ["x"]}, "results": {"bindings": [{}] * 101}},
    {"head": {"vars": ["x"]}, "results": {"bindings": [{"x": {"type": "literal", "value": "x", "datatype": str(XSD.string), "xml:lang": "en"}}]}},
])
def test_malformed_typed_transport_fails_closed(bad):
    with pytest.raises(NLQError):
        decode_select(bad)
