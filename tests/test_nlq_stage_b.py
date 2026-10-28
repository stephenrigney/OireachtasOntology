"""Focused Stage B acceptance over small, explicitly scoped RDF fixtures."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import unicodedata

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, XSD

from poc.nlq.results import QueryResult
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.stage_b import (_query, _readable_bill_result, _validate, execute_stage_b,
                             handle_stage_b, plan_stage_b, validate_stage_b_plan)
from poc.nlq.composable_plan import PlanError, validate_plan
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
ELI = "http://data.europa.eu/eli/ontology#"
ELIDL = "http://data.europa.eu/eli/eli-draft-legislation-ontology#"
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
AS_OF = date(2026, 10, 28)


def _binding(value):
    if value is None:
        return "—"
    if isinstance(value, Literal) and value.language:
        return f"{value}@{value.language}"
    if isinstance(value, Literal) and value.datatype:
        return f"{value}^^<{value.datatype}>"
    return str(value)


class TinyDataset:
    def __init__(self):
        self.dataset = Dataset()
        self.queries = []

    def query(self, query):
        self.queries.append(query)
        raw = self.dataset.query(query)
        if raw.type == "ASK":
            return QueryResult("ask", boolean=bool(raw.askAnswer))
        return QueryResult("select", tuple(str(v) for v in raw.vars),
                           tuple(tuple(_binding(v) for v in row) for row in raw))

    def readiness(self):
        return FusekiReadiness("ready", True, tuple((name, True) for name in
            ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")), "synthetic Stage B fixture")

    def close(self):
        pass

    def add_office_tenure(self, name, label, start, end=None):
        slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace(" ", "-")
        member = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/" + slug)
        graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/" + slug))
        office_graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/offices"))
        office = URIRef("https://data.oireachtas.ie/office/test-" + label.lower().replace(" ", "-"))
        holding = URIRef(str(member) + "#holding")
        date_range = URIRef(str(holding) + "#range")
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, URIRef("http://xmlns.com/foaf/0.1/name"), Literal(name)))
        graph.add((member, URIRef(MEMBERS + "hasOfficeHolding"), holding))
        graph.add((holding, RDF.type, URIRef(MEMBERS + "OfficeHolding")))
        graph.add((holding, URIRef(MEMBERS + "heldOffice"), office))
        graph.add((holding, URIRef(MEMBERS + "hasMembershipDateRange"), date_range))
        graph.add((date_range, RDF.type, URIRef(MEMBERS + "DateRange")))
        graph.add((date_range, URIRef(MEMBERS + "StartDate"), Literal(start, datatype=XSD.dateTime)))
        if end:
            graph.add((date_range, URIRef(MEMBERS + "EndDate"), Literal(end, datatype=XSD.dateTime)))
        office_graph.add((office, RDF.type, URIRef(MEMBERS + "NamedOffice")))
        office_graph.add((office, SKOS.prefLabel, Literal(label, lang="en")))

    def add_current_committee(self, label="Committee on Transport", code="transport"):
        committee_graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/committees"))
        houses_graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/houses"))
        committee = URIRef("https://data.oireachtas.ie/committee/" + code)
        term = URIRef("https://data.oireachtas.ie/house/dail/term/34")
        range_iri = URIRef(str(committee) + "#dates")
        period = URIRef(str(term) + "#period")
        committee_graph.add((committee, RDF.type, URIRef(MEMBERS + "Committee")))
        committee_graph.add((committee, SKOS.prefLabel, Literal(label, lang="en")))
        committee_graph.add((committee, URIRef(MEMBERS + "committeeInHouseTerm"), term))
        committee_graph.add((committee, URIRef(MEMBERS + "hasCommitteeDateRange"), range_iri))
        committee_graph.add((range_iri, RDF.type, URIRef(MEMBERS + "DateRange")))
        committee_graph.add((range_iri, URIRef(MEMBERS + "StartDate"), Literal("2025-01-23T00:00:00", datatype=XSD.dateTime)))
        houses_graph.add((term, URIRef("http://purl.org/dc/terms/temporal"), period))
        houses_graph.add((period, RDF.type, URIRef("http://purl.org/dc/terms/PeriodOfTime")))
        houses_graph.add((period, URIRef("http://www.w3.org/ns/dcat#startDate"), Literal("2025-01-23T00:00:00", datatype=XSD.dateTime)))


def add_bill(fixture, *, memo=False, status="published", title="Pregnancy Loss (Miscellaneous Provisions) Bill 2025"):
    bill = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2025/23")
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2025/23"))
    process = URIRef(str(bill) + "#process")
    graph.add((bill, RDF.type, URIRef(ELIDL + "DraftLegislationWork")))
    graph.add((bill, URIRef(ELI + "type_document"), URIRef(AGENTS + "Bill")))
    graph.add((bill, URIRef(AGENTS + "legislativeYear"), Literal(2025, datatype=XSD.integer)))
    if title:
        graph.add((bill, URIRef(ELI + "title"), Literal(title, lang="en")))
    graph.add((process, RDF.type, URIRef(ELIDL + "LegislativeProcess")))
    graph.add((process, URIRef(ELIDL + "process_number"), Literal("23")))
    if status:
        graph.add((process, URIRef(ELIDL + "process_status"), URIRef("https://data.oireachtas.ie/bill-status/" + status)))
    activity = URIRef(str(bill) + "#event")
    graph.add((process, URIRef(ELIDL + "latest_activity"), activity))
    graph.add((activity, URIRef(ELIDL + "forms_part_of"), process))
    graph.add((activity, URIRef(ELIDL + "activity_date"), Literal("2025-07-09T00:00:00", datatype=XSD.dateTime)))
    graph.add((activity, URIRef(ELIDL + "had_activity_type"), URIRef("https://data.oireachtas.ie/bill-event/committee-stage")))
    if memo:
        work, expression, form = (URIRef(str(bill) + f"#memo-{part}") for part in ("work", "expression", "format"))
        graph.add((bill, URIRef(ELI + "has_part"), work))
        graph.add((work, RDF.type, URIRef(ELI + "Work")))
        graph.add((work, URIRef(ELI + "type_document"), URIRef(AGENTS + "ExplanatoryMemo")))
        graph.add((work, URIRef(ELI + "is_realized_by"), expression))
        graph.add((expression, RDF.type, URIRef(ELI + "LegalExpression")))
        graph.add((expression, URIRef(ELI + "is_embodied_by"), form))
        graph.add((form, RDF.type, URIRef(ELI + "Format")))
        graph.add((form, URIRef(ELI + "uri_schema"), URIRef("https://data.oireachtas.ie/memo.pdf")))


def _run(fixture, question):
    return handle_stage_b(question, as_of=AS_OF, fuseki=fixture,
                           supported_predicates=supported_predicates(ROOT / "ontology"))


def test_q24a_captured_bill_fields_and_same_graph_absence_are_distinguished():
    fixture = TinyDataset()
    add_bill(fixture)
    outcome = _run(fixture, "Tell me about Bill 23 from 2025")
    assert outcome.status == "success"
    assert outcome.plan["family"] == "bill_lookup"
    assert "Pregnancy Loss (Miscellaneous Provisions) Bill 2025" in outcome.result.rows[0][0]
    assert outcome.result.rows[0][1] == "Current"
    assert outcome.result.rows[0][4] == "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23"
    assert "No explanatory memorandum is recorded" in outcome.result.rows[0][5]
    assert "does not prove none exists elsewhere" in outcome.diagnostic
    assert "Bill 2025/23" in (ROOT / "documentation/query-service-completion-evidence.md").read_text()
    assert "24dff7eaa325d649f82fb3f9b36b12c98d81aab844048cd24546f94919011ec2" in (ROOT / "documentation/query-service-completion-evidence.md").read_text()


def test_q24a_available_memo_chain_is_queryable_only_in_its_bill_graph():
    fixture = TinyDataset()
    add_bill(fixture, memo=True)
    outcome = _run(fixture, "Tell me about Bill 23 from 2025")
    assert outcome.status == "success"
    assert outcome.result.rows[0][5] == "https://data.oireachtas.ie/memo.pdf"
    query = fixture.queries[0]
    assert "GRAPH <https://data.oireachtas.ie/graph/bill/2025/23>" in query
    assert "eli:is_embodied_by" in query and "eli:uri_schema" in query


def test_q24a_missing_required_title_or_status_is_not_filled_from_other_fields():
    fixture = TinyDataset()
    add_bill(fixture, status=None)
    outcome = _run(fixture, "Tell me about Bill 23 from 2025")
    assert outcome.status == "incomplete_status_evidence"
    assert "no recorded current process status" in outcome.diagnostic

    fixture = TinyDataset()
    add_bill(fixture, title=None)
    outcome = _run(fixture, "Tell me about Bill 23 from 2025")
    assert outcome.status == "incomplete_display_evidence"
    assert "no English-title evidence" in outcome.diagnostic


def test_closed_bill_plans_and_title_resolutions_preserve_semantic_basis():
    schema = __import__("json").loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    published = plan_stage_b("What Bills were published in 2024", as_of=AS_OF)
    assert published["family"] == "bills_published"
    assert published["referents"]["activity"]["type"] == "BillActivity"
    assert next(c for c in published["constraints"] if c["field"] == "activityTypeAndDate")["value"] == 2024
    assert all(c["field"] != "legislativeYear" for c in published["constraints"])
    non_enacted = plan_stage_b("What 2026 Bills haven't been enacted", as_of=AS_OF)
    assert non_enacted["referents"]["process"]["type"] == "BillProcess"
    assert next(c for c in non_enacted["constraints"] if c["field"] == "processStatus")["value"] == "Enacted"
    ai_plan = plan_stage_b("Find the full title of the AI protection of children Bill", as_of=AS_OF)
    assert ai_plan["referents"]["bill"]["mention"] == "AI protection of children"
    for question in (
        "Tell me about Bill 23 from 2025", "What Bills were published in 2024",
        "What 2026 Bills haven't been enacted", "What is happening to the AI Companion Services Bill?",
        "Who is the sponsor of the AI Companion Services Bill?",
        "Find the full title of the AI protection of children Bill",
        "Who is the Chair of the Committee on Transport?",
        "Who are the Sinn Féin members of the Good Friday Committee?",
        "Was Micheál Martin Taoiseach in September 2026?",
        "Who is Minister for Finance?", "Who was Minister for Finance on 1 July 2021?",
    ):
        plan = plan_stage_b(question, as_of=AS_OF)
        assert validate_plan(plan) == plan
        assert Draft202012Validator(schema).is_valid(plan), question
    tampered = dict(plan_stage_b("Tell me about Bill 23 from 2025", as_of=AS_OF))
    tampered["unexpected"] = True
    try:
        _validate(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("closed Stage B validation accepted an unknown field")
    for question in ("Who are the Sinn Féin members of the Good Friday Committee?",
                     "Who is Minister for Finance?"):
        fixture = TinyDataset()
        outcome = _run(fixture, question)
        assert outcome.status == "source_data_unavailable"
        assert not fixture.queries
        assert outcome.diagnostic


def test_stage_b_authoritative_validator_rejects_mutated_roles_edges_constraints_and_projection():
    prompts = (
        "Tell me about Bill 23 from 2025", "What Bills were published in 2024",
        "What 2026 Bills haven't been enacted", "What is happening to the AI Companion Services Bill?",
        "Who is the sponsor of the AI Companion Services Bill?",
        "Find the full title of the AI protection of children Bill",
        "Who is the Chair of the Committee on Transport?",
        "Who are the Sinn Féin members of the Good Friday Committee?",
        "Was Micheál Martin Taoiseach in September 2026?", "Who is Minister for Finance?",
        "Who was Minister for Finance on 1 July 2021?",
    )
    schema = __import__("json").loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    validator = Draft202012Validator(schema)
    for prompt in prompts:
        plan = plan_stage_b(prompt, as_of=AS_OF)
        assert plan is not None
        assert not list(validator.iter_errors(plan)), prompt
        assert validate_plan(plan) == validate_stage_b_plan(plan) == plan

    base = plan_stage_b("Tell me about Bill 23 from 2025", as_of=AS_OF)
    mutations = []
    changed = __import__("copy").deepcopy(base); changed["referents"]["process"]["type"] = "Member"; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["relations"][0]["fact"] = "member_has_office_holding"; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["relations"][1]["to"] = "bill"; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["answer"]["projection"] = "bill_sponsors"; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["referents"]["bill"]["resolution"] = "resolved"; changed["referents"]["bill"]["iri"] = "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23"; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["referents"]["bill"]["selector"]["number"] = "x/24"; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["constraints"] = [{"referent": "bill", "field": "date", "operator": "on", "value": "2025-01-01"}]; mutations.append(changed)
    changed = __import__("copy").deepcopy(base); changed["answer"]["projection"] = "arbitrary_json"; mutations.append(changed)
    for plan in mutations:
        try:
            validate_plan(plan)
        except PlanError:
            pass
        else:
            raise AssertionError(f"authoritative validator accepted mutation: {plan!r}")

    pub = plan_stage_b("What Bills were published in 2024", as_of=AS_OF)
    changed = __import__("copy").deepcopy(pub); changed["constraints"][0]["field"] = "legislativeYear"
    try: validate_plan(changed)
    except PlanError: pass
    else: raise AssertionError("publication date constraint mutation was accepted")
    alternate_year = __import__("copy").deepcopy(pub); alternate_year["constraints"][0]["value"] = 2025
    assert validate_plan(alternate_year) == alternate_year

    # A different, well-formed identity remains a valid semantic parameter;
    # changing it is not confused with adding an unvalidated request field.
    other_bill = __import__("copy").deepcopy(base)
    other_bill["referents"]["bill"]["selector"]["number"] = "24"
    assert validate_plan(other_bill) == other_bill


def test_legacy_sidecar_b_plan_is_not_a_valid_shared_envelope():
    sidecar = {"version": 2, "asOf": AS_OF.isoformat(), "family": "bill_lookup",
               "bill": {"year": 2025, "number": "23"},
               "fields": ["title", "status", "link", "memorandum", "datedHistory"]}
    schema = __import__("json").loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    assert not Draft202012Validator(schema).is_valid(sidecar)
    try:
        validate_plan(sidecar)
    except PlanError:
        pass
    else:
        raise AssertionError("authoritative validator accepted a sidecar plan without typed referents")


def test_stage_b_title_mentions_are_parameters_not_fixed_question_tokens():
    plan = plan_stage_b("What is happening to the Housing Assistance Bill?", as_of=AS_OF)
    assert plan["referents"]["bill"]["mention"] == "Housing Assistance"
    query = _query(plan, supported_predicates(ROOT / "ontology"))
    assert '"housing"' in query and '"assistance"' in query
    assert "companion" not in query
    ai = plan_stage_b("Who is the sponsor of the AI Companion Services Bill?", as_of=AS_OF)
    query = _query(ai, supported_predicates(ROOT / "ontology"))
    assert '"artificial intelligence"' in query and '"companion"' in query


def test_stage_b_compiler_revalidates_and_requires_reviewed_patterns(monkeypatch):
    import poc.nlq.stage_b as stage_b
    plan = plan_stage_b("Tell me about Bill 23 from 2025", as_of=AS_OF)
    changed = __import__("copy").deepcopy(plan)
    changed["answer"]["projection"] = "non_enacted_bills"
    try:
        _query(changed, supported_predicates(ROOT / "ontology"))
    except PlanError:
        pass
    else:
        raise AssertionError("compiler accepted a mutated noncanonical plan")

    def missing_pattern(*_args):
        raise ValueError("reviewed Bill pattern removed")
    monkeypatch.setattr(stage_b, "_reviewed_pattern", missing_pattern)
    try:
        _query(plan, supported_predicates(ROOT / "ontology"))
    except ValueError as error:
        assert "reviewed Bill pattern removed" in str(error)
    else:
        raise AssertionError("compiler bypassed the reviewed pattern/owner gate")
    fixture = TinyDataset()
    outcome = execute_stage_b(plan, fuseki=fixture,
                              supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "unsupported_mapping"
    assert not fixture.queries


def test_q12_resolves_dated_current_committee_before_reporting_chair_gap():
    fixture = TinyDataset()
    fixture.add_current_committee()
    outcome = _run(fixture, "Who is the Chair of the Committee on Transport?")
    assert outcome.status == "source_data_unavailable"
    assert outcome.result.rows == (("Committee on Transport", AS_OF.isoformat()),)
    assert "no reviewed chair/office-holder relationship is queryable" in outcome.diagnostic
    assert len(fixture.queries) == 1


def test_q18_q19_q20_q21_q22_compile_only_reviewed_bounded_bill_patterns():
    questions = {
        "Find the full title of the AI protection of children Bill": ("eli:title", "protection", "children"),
        "What Bills were published in 2024": ("Published", "eventDate", "2024-01-01"),
        "What 2026 Bills haven't been enacted": ("process_status", "?status", "OPTIONAL"),
        "What is happening to the AI Companion Services Bill?": ("process_status", "activity_date", "forms_part_of"),
        "Who is the sponsor of the AI Companion Services Bill?": ("had_participation", "isPrimarySponsor", "memberGraph"),
    }
    for question, evidence in questions.items():
        query = _query(plan_stage_b(question, as_of=AS_OF), supported_predicates(ROOT / "ontology"))
        assert "SELECT DISTINCT" in query and "LIMIT 100" in query
        import re
        assert not re.search(r"\b(?:SERVICE|UPDATE|FROM\s+NAMED)\b", query, re.IGNORECASE)
        for token in evidence:
            assert token in query
    publication_query = _query(plan_stage_b("What Bills were published in 2024", as_of=AS_OF),
                               supported_predicates(ROOT / "ontology"))
    assert '"2024-01-01"^^xsd:date' in publication_query
    assert "agents:legislativeYear 2024" not in publication_query
    sponsor_query = _query(plan_stage_b("Who is the sponsor of the AI Companion Services Bill?", as_of=AS_OF),
                           supported_predicates(ROOT / "ontology"))
    assert "OPTIONAL { ?participation eli-dl:had_participant_person ?member }" in sponsor_query
    assert "OPTIONAL { ?participation rdfs:label ?role }" in sponsor_query


def test_q20_missing_and_conflicting_process_statuses_fail_closed():
    class StaticRows:
        def __init__(self, rows):
            self.rows = rows
        def query(self, query):
            return QueryResult("select", ("bill", "title", "number", "status"), self.rows)

    plan = plan_stage_b("What 2026 Bills haven't been enacted", as_of=AS_OF)
    missing = execute_stage_b(plan, fuseki=StaticRows((
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "1", "—"),)),
        supported_predicates=supported_predicates(ROOT / "ontology"))
    assert missing.status == "incomplete_status_evidence"
    conflict = execute_stage_b(plan, fuseki=StaticRows((
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "1", "https://data.oireachtas.ie/bill-status/published"),
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "1", "https://data.oireachtas.ie/bill-status/enacted"),)),
        supported_predicates=supported_predicates(ROOT / "ontology"))
    assert conflict.status == "conflicting_status_evidence"
    enacted = execute_stage_b(plan, fuseki=StaticRows((
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "1", "https://data.oireachtas.ie/ontology#EnactedBill"),)),
        supported_predicates=supported_predicates(ROOT / "ontology"))
    assert enacted.status == "source_data_unavailable"
    assert "does not prove a complete negative" in enacted.diagnostic


def test_q22_readability_preserves_primary_false_null_and_role_only_participations():
    result = QueryResult("select", ("bill", "title", "number", "status", "member", "memberName", "primary", "role"), (
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1", "AI Companion Services Bill@en", "1", "Current", "member1", "Alice Example", '"true"^^<http://www.w3.org/2001/XMLSchema#boolean>', "Primary sponsor"),
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1", "AI Companion Services Bill@en", "1", "Current", "member2", "Bob Example", '"false"^^<http://www.w3.org/2001/XMLSchema#boolean>', "Supporting sponsor"),
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1", "AI Companion Services Bill@en", "1", "Current", "—", "—", "—", "Minister for Finance"),
    ))
    readable, _notice = _readable_bill_result("bill_sponsors", result)
    assert readable.rows[0][3] == "Primary"
    assert readable.rows[1][3] == "Supporting"
    assert readable.rows[2][1] == "Unresolved sponsor (recorded role only)"
    assert readable.rows[2][2] == "Minister for Finance"


def test_stage_b_ask_content_is_specific_not_generic_unavailable(monkeypatch):
    from poc.nlq import app as app_module

    fixture = TinyDataset()
    add_bill(fixture)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Tell me about Bill 23 from 2025", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Pregnancy Loss (Miscellaneous Provisions) Bill 2025" in response.text
    assert "Current" in response.text
    assert "No explanatory memorandum is recorded" in response.text
    assert "Official Bill" in response.text
    assert "Results use locally recorded Bill-owned RDF" in response.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23" in response.text


def test_ask_does_not_present_an_invalid_stage_b_plan_as_validated(monkeypatch):
    from poc.nlq import app as app_module
    from poc.nlq.composable_plan import PlanOutcome
    sidecar = {"version": 2, "asOf": AS_OF.isoformat(), "family": "bill_lookup",
               "bill": {"year": 2025, "number": "23"}, "fields": ["title"]}
    fixture = TinyDataset()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    monkeypatch.setattr(app_module, "execute_question", lambda *args, **kwargs:
                        PlanOutcome("unsupported_capability", plan=sidecar,
                                    diagnostic="Invalid plan must not be represented as validated."))
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Tell me about Bill 23 from 2025", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Validated composable query plan" not in response.text
    assert "Invalid plan must not be represented as validated." in response.text


def test_q25_does_not_report_yes_until_named_member_iri_is_bound(monkeypatch):
    from poc.nlq import app as app_module

    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Was Micheál Martin Taoiseach in September 2026?", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "to an exact local Member IRI" in response.text
    assert "Validated composable query plan" in response.text


def test_q25_deferred_identity_binding_and_q27_uses_accepted_dated_interval():
    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "source_data_unavailable"
    assert "exact local Member IRI" in outcome.diagnostic
    assert outcome.plan["family"] == "office_overlap"

    fixture = TinyDataset()
    fixture.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2022-12-17T00:00:00")
    outcome = _run(fixture, "Who was Minister for Finance on 1 July 2021?")
    assert outcome.status == "success"
    assert outcome.plan["family"] == "office_point"
    assert outcome.result.rows[0][0] == "Paschal Donohoe"
