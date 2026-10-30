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

    def add_office_tenure(self, name, label, start, end=None, *, code=None, holding_suffix=""):
        slug = code or unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace(" ", "-")
        member = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/" + slug)
        graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/" + slug))
        office_graph = self.dataset.graph(URIRef("https://data.oireachtas.ie/graph/offices"))
        office = URIRef("https://data.oireachtas.ie/office/test-" + label.lower().replace(" ", "-"))
        holding = URIRef(str(member) + "#holding" + holding_suffix)
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


def add_bill_record(fixture, *, year=2025, number="23", title="Pregnancy Loss (Miscellaneous Provisions) Bill 2025",
                    status="published", events=(), sponsors=(), memos=(), year_values=None,
                    bill_type=True, graph_suffix=""):
    """Build only the actual Bills ETL shape, with typed source-accurate literals."""
    bill = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/bill/{year}/{number}")
    graph = fixture.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/bill/{year}/{number}{graph_suffix}"))
    process = URIRef(str(bill) + "#process")
    delivery = URIRef(str(bill) + "#delivery")
    graph.add((delivery, RDF.type, URIRef(AGENTS + "BillDelivery")))
    graph.add((delivery, RDF.type, URIRef(ELIDL + "LegislativeActivity")))
    graph.add((delivery, URIRef(ELIDL + "created_a_realization_of"), bill))
    graph.add((delivery, URIRef(ELIDL + "forms_part_of"), process))
    if bill_type:
        graph.add((bill, RDF.type, URIRef(ELIDL + "DraftLegislationWork")))
        graph.add((bill, URIRef(ELI + "type_document"), URIRef(AGENTS + "Bill")))
    for bill_year in (year_values if year_values is not None else [year]):
        graph.add((bill, URIRef(AGENTS + "legislativeYear"), Literal(bill_year, datatype=XSD.integer)))
    if title:
        values = title if isinstance(title, (list, tuple)) else [title]
        for value in values:
            graph.add((bill, URIRef(ELI + "title"), Literal(value, lang="en")))
    graph.add((process, RDF.type, URIRef(ELIDL + "LegislativeProcess")))
    graph.add((process, URIRef(ELIDL + "process_number"), Literal(str(number))))
    status_map = {
        "awaiting-signature": "AwaitingSignatureBill", "published": "CurrentBill", "current": "CurrentBill",
        "defeated": "DefeatedBill", "repugnant": "DeclaredRepugnantToConstitutionBill",
        "draft": "DraftHeadsOfBill", "enacted": "EnactedBill", "lapsed": "LapsedBill",
        "withdrawn": "WithdrawnBill", "referendum": "RejectedAtReferendumBill",
    }
    if status:
        status_iri = status if str(status).startswith("http") else AGENTS + status_map.get(status, status)
        graph.add((process, URIRef(ELIDL + "process_status"), URIRef(status_iri)))
    latest = URIRef(str(bill) + "#latest-stage")
    graph.add((process, URIRef(ELIDL + "latest_activity"), latest))
    graph.add((latest, RDF.type, URIRef(ELIDL + "LegislativeActivity")))
    graph.add((latest, URIRef(ELIDL + "forms_part_of"), process))
    graph.add((latest, URIRef(ELIDL + "activity_date"), Literal("2025-07-09", datatype=XSD.date)))
    graph.add((latest, URIRef(ELIDL + "had_activity_type"), URIRef(AGENTS + "CommitteeStage")))
    for index, (event_date, event_type) in enumerate(events):
        activity = URIRef(str(bill) + f"#event-{index}")
        graph.add((activity, RDF.type, URIRef(ELIDL + "LegislativeActivity")))
        graph.add((activity, URIRef(ELIDL + "forms_part_of"), process))
        graph.add((activity, URIRef(ELIDL + "activity_date"), Literal(event_date, datatype=XSD.date)))
        graph.add((activity, URIRef(ELIDL + "had_activity_type"), URIRef(event_type)))
    for index, sponsor in enumerate(sponsors):
        participation = URIRef(str(process) + f"#sponsor-{index}")
        graph.add((process, URIRef(ELIDL + "had_participation"), participation))
        graph.add((participation, RDF.type, URIRef(ELIDL + "Participation")))
        if sponsor.get("member"):
            member = URIRef(sponsor["member"])
            graph.add((participation, URIRef(ELIDL + "had_participant_person"), member))
            if sponsor.get("name"):
                member_graph = fixture.dataset.graph(URIRef(sponsor.get("graph", "https://data.oireachtas.ie/graph/member/" + str(index + 1))))
                member_graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
                member_graph.add((member, URIRef("http://xmlns.com/foaf/0.1/name"), Literal(sponsor["name"])))
        if "raw_primary" in sponsor:
            graph.add((participation, URIRef(AGENTS + "isPrimarySponsor"), sponsor["raw_primary"]))
        elif "primary" in sponsor and sponsor["primary"] is not None:
            graph.add((participation, URIRef(AGENTS + "isPrimarySponsor"), Literal(sponsor["primary"], datatype=XSD.boolean)))
        if sponsor.get("role"):
            graph.add((participation, RDFS.label, Literal(sponsor["role"])))
    for memo_index, memo in enumerate(memos):
        work = URIRef(str(bill) + f"#memo-work-{memo_index}")
        graph.add((bill, URIRef(ELI + "has_part"), work))
        graph.add((work, RDF.type, URIRef(ELI + "Work")))
        graph.add((work, URIRef(ELI + "type_document"), URIRef(AGENTS + memo.get("type", "ExplanatoryMemo"))))
        expression = URIRef(str(work) + "-expression")
        if memo.get("expression", True):
            graph.add((work, URIRef(ELI + "is_realized_by"), expression))
            graph.add((expression, RDF.type, URIRef(ELI + "LegalExpression")))
            for format_index, rendition in enumerate(memo.get("renditions", [])):
                form = URIRef(str(expression) + f"-format-{format_index}")
                graph.add((expression, URIRef(ELI + "is_embodied_by"), form))
                graph.add((form, RDF.type, URIRef(ELI + "Format")))
                graph.add((form, URIRef(ELI + "uri_schema"), URIRef(rendition)))
    return bill, graph


def add_bill(fixture, *, memo=False, status="published", title="Pregnancy Loss (Miscellaneous Provisions) Bill 2025"):
    memos = [{"renditions": ["https://data.oireachtas.ie/memo.pdf"]}] if memo else []
    return add_bill_record(fixture, status=status, title=title, memos=memos,
                           events=[("2025-07-09", AGENTS + "Published")])


def test_all_stage_b_bill_process_queries_use_only_the_explicitly_linked_process():
    fixture = TinyDataset()
    own, graph = add_bill_record(
        fixture, year=2026, number="93", title="Artificial Intelligence Companion Services Bill 2026",
        status="current", sponsors=({"role": "Own sponsor"},),
        events=(("2024-01-02", AGENTS + "Published"),))
    other, other_graph = add_bill_record(
        fixture, year=2026, number="94", title="Unrelated Bill 2026",
        status="enacted", sponsors=({"role": "Other sponsor"},),
        events=(("2024-03-04", AGENTS + "Published"),))
    graph += other_graph
    other_graph.remove((None, None, None))
    questions = [
        "Tell me about Bill 93 from 2026",
        "What Bills were published in 2024",
        "What 2026 Bills haven't been enacted",
        "What is happening to the AI Companion Services Bill?",
        "Who is the sponsor of the AI Companion Services Bill?",
    ]
    for question in questions:
        plan = plan_stage_b(question, as_of=AS_OF)
        assert plan is not None
        query = _query(plan, supported_predicates(ROOT / "ontology"))
        result = fixture.query(query)
        rows = [dict(zip(result.columns, row)) for row in result.rows]
        own_rows = [row for row in rows if row["bill"] == str(own)]
        assert own_rows, question
        for row in own_rows:
            if "process" in row:
                assert row["process"] == str(own) + "#process"
            if "status" in row:
                assert row["status"] == AGENTS + "CurrentBill"
            if "number" in row:
                assert row["number"] == "93"
            if "role" in row:
                assert row["role"] == "Own sponsor"
            if "eventDate" in row:
                assert row["eventDate"] != "2024-03-04^^<http://www.w3.org/2001/XMLSchema#date>"
        # No co-ownership fallback for a Bill with missing relationship evidence.
        delivery = URIRef(str(own) + "#delivery")
        graph.remove((delivery, URIRef(ELIDL + "created_a_realization_of"), own))
        unlinked = fixture.query(query)
        for raw in unlinked.rows:
            row = dict(zip(unlinked.columns, raw))
            if row["bill"] == str(own):
                for column in ("process", "status", "number", "role", "eventDate"):
                    if column in row:
                        assert row[column] == "—"
        graph.add((delivery, URIRef(ELIDL + "created_a_realization_of"), own))


def _run(fixture, question):
    return handle_stage_b(question, as_of=AS_OF, fuseki=fixture,
                           supported_predicates=supported_predicates(ROOT / "ontology"))


def _ask(monkeypatch, fixture, question):
    from poc.nlq import app as app_module
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    return TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": question, "mode": "phase2",
    })


def test_q24a_captured_bill_fields_and_same_graph_absence_are_distinguished():
    fixture = TinyDataset()
    bill, graph = add_bill(fixture)
    # A complete typed memo chain that is not linked from this Bill must not
    # become evidence through an unbound OPTIONAL variable.
    orphan = URIRef(str(bill) + "#orphan-memo")
    expression = URIRef(str(orphan) + "-expression")
    form = URIRef(str(expression) + "-format")
    graph.add((orphan, RDF.type, URIRef(ELI + "Work")))
    graph.add((orphan, URIRef(ELI + "type_document"), URIRef(AGENTS + "ExplanatoryMemo")))
    graph.add((orphan, URIRef(ELI + "is_realized_by"), expression))
    graph.add((expression, RDF.type, URIRef(ELI + "LegalExpression")))
    graph.add((expression, URIRef(ELI + "is_embodied_by"), form))
    graph.add((form, RDF.type, URIRef(ELI + "Format")))
    graph.add((form, URIRef(ELI + "uri_schema"), URIRef("https://data.oireachtas.ie/orphan-memo.pdf")))
    outcome = _run(fixture, "Tell me about Bill 23 from 2025")
    assert outcome.status == "success"
    assert outcome.plan["family"] == "bill_lookup"
    assert "Pregnancy Loss (Miscellaneous Provisions) Bill 2025" in outcome.result.rows[0][0]
    assert outcome.result.rows[0][1] == "Current"
    assert outcome.result.rows[0][4] == "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23"
    assert "No explanatory memorandum Work is recorded" in outcome.result.rows[0][5]
    assert "orphan-memo" not in outcome.result.rows[0][5]
    assert "does not prove none exists elsewhere" in outcome.diagnostic
    assert "Bill 2025/23" in (ROOT / "docs/reports/query-service/completion-evidence.md").read_text()
    assert "24dff7eaa325d649f82fb3f9b36b12c98d81aab844048cd24546f94919011ec2" in (ROOT / "docs/reports/query-service/completion-evidence.md").read_text()


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
    assert "missing English-title evidence" in outcome.diagnostic


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


def test_q25_authoritative_validator_rejects_mutated_member_iri_office_role_and_interval():
    import copy
    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    plan = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?").plan
    assert plan["referents"]["member"]["resolution"] == "resolved"
    mutations = []
    changed = copy.deepcopy(plan)
    changed["referents"]["member"]["iri"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/other"
    mutations.append(changed)
    changed = copy.deepcopy(plan)
    changed["constraints"][1]["value"] = "https://data.oireachtas.ie/ie/oireachtas/member/id/other"
    mutations.append(changed)
    changed = copy.deepcopy(plan)
    changed["referents"]["office"]["mention"] = "Minister for Finance"
    mutations.append(changed)
    changed = copy.deepcopy(plan)
    changed["constraints"][0]["value"]["start"] = "2026-09-31"
    mutations.append(changed)
    for mutated in mutations:
        try:
            validate_plan(mutated)
        except PlanError:
            pass
        else:
            raise AssertionError(f"authoritative office validator accepted a mutated B3 plan: {mutated!r}")


def test_office_point_is_restricted_to_finance_and_authoritative_validator_rejects_role_mutation(monkeypatch):
    finance_question = "Who was Minister for Finance on 1 July 2021?"
    finance = plan_stage_b(finance_question, as_of=AS_OF)
    assert finance is not None and finance["family"] == "office_point"
    assert validate_plan(finance) == finance
    changed = __import__("copy").deepcopy(finance)
    changed["referents"]["office"]["mention"] = "Taoiseach"
    try:
        validate_plan(changed)
    except PlanError:
        pass
    else:
        raise AssertionError("office-point validator accepted a mutated role")

    for question in (
        "Who was Taoiseach on 1 July 2021?",
        "Who was Tánaiste on 1 July 2021?",
        "Who was Minister for Health on 1 July 2021?",
    ):
        fixture = TinyDataset()
        fixture.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2022-12-17T00:00:00")
        assert plan_stage_b(question, as_of=AS_OF) is None
        assert _run(fixture, question) is None
        response = _ask(monkeypatch, fixture, question)
        assert response.status_code == 200
        assert "Paschal Donohoe" not in response.text
        assert not fixture.queries


def test_bound_q35_validator_requires_canonical_constraint_order():
    import copy
    from poc.nlq.composable_plan import plan_question

    plan = plan_question("Who was Taoiseach from September 2026 to September 2026?", as_of=AS_OF)
    plan["referents"]["office"].update({
        "resolution": "resolved", "iri": "https://data.oireachtas.ie/office/taoiseach", "label": "Taoiseach",
    })
    plan["referents"]["member"] = {
        "type": "Member", "answer": True, "mention": "Micheál Martin", "resolution": "resolved",
        "iri": "https://data.oireachtas.ie/ie/oireachtas/member/id/micheal-martin", "label": "Micheál Martin",
    }
    plan["constraints"].append({
        "referent": "member", "field": "memberIdentity", "operator": "equals",
        "value": plan["referents"]["member"]["iri"],
    })
    assert validate_plan(plan) == plan

    reversed_constraints = copy.deepcopy(plan)
    reversed_constraints["constraints"] = list(reversed(reversed_constraints["constraints"]))
    try:
        validate_plan(reversed_constraints)
    except PlanError:
        pass
    else:
        raise AssertionError("bound Q35 validator accepted identity-first constraint order")


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


def test_bill_owner_and_typed_event_contract_gates_fail_before_fuseki(monkeypatch):
    import copy
    import poc.nlq.stage_b as stage_b

    predicates = supported_predicates(ROOT / "ontology")
    published = plan_stage_b("What Bills were published in 2024", as_of=AS_OF)
    fixture = TinyDataset()
    original_loader = stage_b.load_query_contract
    changed_contract = copy.deepcopy(original_loader())
    bill_family = next(item for item in changed_contract["graphFamilies"] if item["id"] == "bill-records")
    bill_family["owner"] = "unreviewed graph owner"
    with monkeypatch.context() as scoped:
        scoped.setattr(stage_b, "load_query_contract", lambda: changed_contract)
        outcome = execute_stage_b(published, fuseki=fixture, supported_predicates=predicates)
    assert outcome.status == "unsupported_mapping"
    assert not fixture.queries

    original_pattern = stage_b._reviewed_pattern
    def without_event_date(pattern_id, family_id):
        pattern = copy.deepcopy(original_pattern(pattern_id, family_id))
        if pattern_id == "bill-lifecycle":
            pattern["triples"] = [triple for triple in pattern["triples"]
                                  if triple[1] != "eli-dl:activity_date"]
        return pattern
    with monkeypatch.context() as scoped:
        scoped.setattr(stage_b, "_reviewed_pattern", without_event_date)
        outcome = execute_stage_b(published, fuseki=fixture, supported_predicates=predicates)
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
    assert "OPTIONAL { ?participation eli-dl:had_participant_person ?member ." in sponsor_query
    assert "OPTIONAL { ?participation rdfs:label ?role }" in sponsor_query


def test_q20_missing_and_conflicting_process_statuses_fail_closed():
    class StaticRows:
        def __init__(self, rows):
            self.rows = rows
        def query(self, query):
            return QueryResult("select", ("bill", "title", "year", "process", "number", "status"), self.rows)

    plan = plan_stage_b("What 2026 Bills haven't been enacted", as_of=AS_OF)
    missing = execute_stage_b(plan, fuseki=StaticRows((
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "2026", "process", "1", "—"),)),
        supported_predicates=supported_predicates(ROOT / "ontology"))
    assert missing.status == "incomplete_status_evidence"
    conflict = execute_stage_b(plan, fuseki=StaticRows((
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "2026", "process", "1", AGENTS + "CurrentBill"),
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "2026", "process", "1", AGENTS + "EnactedBill"))),
        supported_predicates=supported_predicates(ROOT / "ontology"))
    assert conflict.status == "conflicting_status_evidence"
    enacted = execute_stage_b(plan, fuseki=StaticRows((
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2026/1", "Example Bill", "2026", "process", "1", AGENTS + "EnactedBill"),)),
        supported_predicates=supported_predicates(ROOT / "ontology"))
    assert enacted.status == "source_data_unavailable"
    assert "incomplete corpus coverage prevents a complete negative" in enacted.diagnostic


def test_q22_readability_preserves_primary_false_null_and_role_only_participations():
    result = QueryResult("select", ("bill", "title", "year", "number", "status", "participation", "member", "memberName", "primary", "role"), (
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1", "AI Companion Services Bill@en", "2024", "1", AGENTS + "CurrentBill", "p1", "member1", "Alice Example", '"true"^^<http://www.w3.org/2001/XMLSchema#boolean>', "Primary sponsor"),
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1", "AI Companion Services Bill@en", "2024", "1", AGENTS + "CurrentBill", "p2", "member2", "Bob Example", '"false"^^<http://www.w3.org/2001/XMLSchema#boolean>', "Supporting sponsor"),
        ("https://data.oireachtas.ie/ie/oireachtas/bill/2024/1", "AI Companion Services Bill@en", "2024", "1", AGENTS + "CurrentBill", "p3", "—", "—", "—", "Minister for Finance"),
    ))
    readable, _notice = _readable_bill_result("bill_sponsors", result)
    assert readable.rows[0][3] == "Primary"
    assert readable.rows[1][3] == "Supporting"
    assert readable.rows[2][1] == "Unresolved sponsor (recorded role only)"
    assert readable.rows[2][2] == "Minister for Finance"


def test_q21_title_match_without_process_is_missing_process_not_missing_title(monkeypatch):
    fixture = TinyDataset()
    bill, graph = add_bill_record(fixture, year=2025, number="31", title="Artificial Intelligence Bill")
    process = URIRef(bill + "#process")
    graph.remove((process, RDF.type, URIRef(ELIDL + "LegislativeProcess")))
    outcome = _run(fixture, "What is happening to Artificial Intelligence Bill?")
    assert outcome.status == "incomplete_status_evidence"
    assert "no typed LegislativeProcess" in outcome.diagnostic
    assert "No locally recorded Bill title matches" not in outcome.diagnostic
    assert "Artificial Intelligence Bill" in outcome.result.rows[0][0]
    response = _ask(monkeypatch, fixture, "What is happening to Artificial Intelligence Bill?")
    assert "The title-matched typed Bill has no typed LegislativeProcess" in response.text
    assert "No locally recorded Bill title matches" not in response.text


def test_q22_typed_bill_without_participation_is_reported_and_stays_ambiguous_with_other_bill(monkeypatch):
    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="8",
                    title="Artificial Intelligence Companion Services Bill",
                    sponsors=[{"role": "Primary sponsor"}])
    add_bill_record(fixture, year=2025, number="9",
                    title="Artificial Intelligence Companion Services (Amendment) Bill")
    outcome = _run(fixture, "Who is the sponsor of Artificial Intelligence Companion Services Bill?")
    assert outcome.status == "ambiguous"
    assert {row[0] for row in outcome.result.rows} == {
        "Artificial Intelligence Companion Services Bill",
        "Artificial Intelligence Companion Services (Amendment) Bill",
    }
    assert len(outcome.result.rows) == 2

    fixture = TinyDataset()
    add_bill_record(fixture, year=2025, number="10", title="Artificial Intelligence Companion Services Bill")
    outcome = _run(fixture, "Who is the sponsor of Artificial Intelligence Companion Services Bill?")
    assert outcome.status == "source_data_unavailable"
    assert "no recorded sponsor Participation" in outcome.diagnostic
    assert "No locally recorded Bill title matches" not in outcome.diagnostic
    response = _ask(monkeypatch, fixture,
                    "Who is the sponsor of Artificial Intelligence Companion Services Bill?")
    assert "matching Bill has no recorded sponsor Participation" in response.text
    assert "No locally recorded Bill title matches" not in response.text


def test_stage_b_ask_content_is_specific_not_generic_unavailable(monkeypatch):
    fixture = TinyDataset()
    add_bill(fixture)
    response = _ask(monkeypatch, fixture, "Tell me about Bill 23 from 2025")
    assert response.status_code == 200
    assert "Pregnancy Loss (Miscellaneous Provisions) Bill 2025" in response.text
    assert "Current" in response.text
    assert "No explanatory memorandum Work is recorded" in response.text
    assert "Official Bill" in response.text
    assert "Results use locally recorded Bill-owned RDF" in response.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2025/23" in response.text


def test_q18_and_q21_named_graph_title_routes_execute_through_ask(monkeypatch):
    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="8",
                    title="Artificial Intelligence Protection of Children Bill 2024",
                    events=[("2024-01-15", AGENTS + "FirstStage"),
                            ("2024-03-02", AGENTS + "CommitteeStage")])
    title = _ask(monkeypatch, fixture, "Find the full title of the AI protection of children Bill")
    assert title.status_code == 200
    assert "Artificial Intelligence Protection of Children Bill 2024" in title.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2024/8" in title.text
    assert fixture.queries and all("GRAPH ?graph" in query for query in fixture.queries)

    history = _ask(monkeypatch, fixture, "What is happening to the AI protection of children Bill?")
    assert history.status_code == 200
    assert "Current" in history.text
    assert "2024-01-15" in history.text and "2024-03-02" in history.text
    assert "next step is inferred" in history.text


def test_q18_title_ambiguity_returns_separate_official_bill_candidates(monkeypatch):
    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="8", title="Artificial Intelligence Protection Bill A")
    add_bill_record(fixture, year=2025, number="9", title="Artificial Intelligence Protection Bill B")
    response = _ask(monkeypatch, fixture, "Find the full title of the AI protection Bill")
    assert "Several distinct Bill IRIs" in response.text
    assert "Artificial Intelligence Protection Bill A" in response.text
    assert "Artificial Intelligence Protection Bill B" in response.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2024/8" in response.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2025/9" in response.text
    assert len(fixture.queries) == 1
    assert "Stage A typed family result" not in response.text
    assert "Several distinct Bill IRIs" in response.text
    assert "Resolve the supplied Bill title mention" in response.text


def test_q22_asymmetric_missing_participation_identity_remains_ambiguous_in_ask(monkeypatch):
    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="8",
                    title="Artificial Intelligence Companion Services Bill",
                    sponsors=[{"role": "Primary sponsor"}])
    add_bill_record(fixture, year=2025, number="9",
                    title="Artificial Intelligence Companion Services (Amendment) Bill")
    response = _ask(monkeypatch, fixture,
                    "Who is the sponsor of Artificial Intelligence Companion Services Bill?")
    assert response.status_code == 200
    assert "Several distinct Bill IRIs" in response.text
    assert "Artificial Intelligence Companion Services Bill" in response.text
    assert "Artificial Intelligence Companion Services (Amendment) Bill" in response.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2024/8" in response.text
    assert "https://data.oireachtas.ie/ie/oireachtas/bill/2025/9" in response.text
    assert "Stage A typed family result" not in response.text


def test_q25_and_q27_adversarial_office_outcomes_are_visible_through_ask(monkeypatch):
    partial = TinyDataset()
    partial.add_office_tenure("Micheál Martin", "Taoiseach", "2026-09-20T00:00:00", "2026-10-01T00:00:00")
    response = _ask(monkeypatch, partial, "Was Micheál Martin Taoiseach in September 2026?")
    assert "Yes" in response.text and "2026-09-20" in response.text and "2026-10-01" in response.text

    unknown = TinyDataset()
    not_found = _ask(monkeypatch, unknown, "Was Micheál Martin Taoiseach in September 2026?")
    assert "No exact local Member identity matches" in not_found.text
    assert "Yes" not in not_found.text

    ambiguous = TinyDataset()
    ambiguous.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00", code="micheal-martin-a")
    ambiguous.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00", code="micheal-martin-b")
    response = _ask(monkeypatch, ambiguous, "Was Micheál Martin Taoiseach in September 2026?")
    assert "Several distinct local Member IRIs" in response.text
    assert "micheal-martin-a" in response.text and "micheal-martin-b" in response.text
    assert "Yes" not in response.text

    nonmatching = TinyDataset()
    nonmatching.add_office_tenure("Micheál Martin", "Minister for Finance", "2025-01-23T00:00:00")
    nonmatching.add_office_tenure("Other Person", "Taoiseach", "2025-01-23T00:00:00", code="other-person")
    response = _ask(monkeypatch, nonmatching, "Was Micheál Martin Taoiseach in September 2026?")
    assert "No accepted Member-owned OfficeHolding" in response.text
    assert "Yes" not in response.text

    point = TinyDataset()
    point.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2021-06-30T00:00:00")
    response = _ask(monkeypatch, point, "Who was Minister for Finance on 1 July 2021?")
    assert "No accepted local holding is recorded overlapping 2021-07-01 through 2021-07-01" in response.text
    assert '"2021-07-01T00:00:00"' in point.queries[-1]
    assert "2021-07-31" not in point.queries[-1]

    point_inclusive = TinyDataset()
    point_inclusive.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2021-07-01T00:00:00")
    response = _ask(monkeypatch, point_inclusive, "Who was Minister for Finance on 1 July 2021?")
    assert "Paschal Donohoe" in response.text
    assert "2020-06-27" in response.text and "2021-07-01" in response.text
    response = _ask(monkeypatch, point_inclusive, "Who was Minister for Finance on 2 July 2021?")
    assert "No accepted local holding is recorded overlapping 2021-07-02 through 2021-07-02" in response.text

    q26 = TinyDataset()
    q26.add_office_tenure("Finance Holder", "Minister for Finance", "2020-01-01T00:00:00")
    response = _ask(monkeypatch, q26, "Who is Minister for Finance?")
    assert "incomplete 22-holding sample" in response.text
    assert "Finance Holder" not in response.text


def test_q25_conflicting_holding_is_visible_as_unavailable_not_boolean(monkeypatch):
    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/micheal-martin"))
    range_iri = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/micheal-martin#holding#range")
    graph.add((range_iri, URIRef(MEMBERS + "StartDate"), Literal("2024-01-01T00:00:00", datatype=XSD.dateTime)))
    response = _ask(monkeypatch, fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert "conflicting Member or date evidence" in response.text
    assert "<strong>Yes</strong>" not in response.text
    assert "<strong>No</strong>" not in response.text


def test_stage_b_missing_bill_keeps_b_summary_and_does_not_claim_validation(monkeypatch):
    from poc.nlq import app as app_module
    fixture = TinyDataset()
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Tell me about Bill 23 from 2025", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Look up the exact Bill number and year" in response.text
    assert "exact typed Bill is absent" in response.text
    assert "Stage A typed family result" not in response.text
    assert "Validated composable query plan" in response.text


def test_q19_published_query_uses_any_exact_typed_dated_event_and_owner_graph(monkeypatch):
    fixture = TinyDataset()
    bill, graph = add_bill_record(fixture, year=2024, number="5", title="Dated publication Bill",
                                  year_values=[2022], events=[("2024-12-31", AGENTS + "Published"),
                                                             ("2025-01-01", AGENTS + "Published")])
    activity = URIRef(str(bill) + "#datetime-decoy")
    process = URIRef(str(bill) + "#process")
    graph.add((activity, RDF.type, URIRef(ELIDL + "LegislativeActivity")))
    graph.add((activity, URIRef(ELIDL + "forms_part_of"), process))
    graph.add((activity, URIRef(ELIDL + "activity_date"), Literal("2024-06-01T00:00:00", datatype=XSD.dateTime)))
    graph.add((activity, URIRef(ELIDL + "had_activity_type"), URIRef(AGENTS + "Published")))
    fake_published = URIRef(str(bill) + "#fake-status-published")
    graph.add((fake_published, RDF.type, URIRef(ELIDL + "LegislativeActivity")))
    graph.add((fake_published, URIRef(ELIDL + "forms_part_of"), process))
    graph.add((fake_published, URIRef(ELIDL + "activity_date"), Literal("2024-06-02", datatype=XSD.date)))
    graph.add((fake_published, URIRef(ELIDL + "had_activity_type"), URIRef("https://data.oireachtas.ie/bill-status/published")))
    decoy_graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2024/5/extra"))
    decoy = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/99")
    decoy_graph.add((decoy, RDF.type, URIRef(ELIDL + "DraftLegislationWork")))
    decoy_graph.add((decoy, URIRef(ELI + "type_document"), URIRef(AGENTS + "Bill")))
    decoy_graph.add((decoy, URIRef(ELI + "title"), Literal("Fake Bill", lang="en")))

    response = _ask(monkeypatch, fixture, "What Bills were published in 2024")
    outcome = _run(fixture, "What Bills were published in 2024")
    assert response.status_code == 200
    assert "Dated publication Bill" in response.text
    assert "2024-12-31" in response.text
    assert outcome.result.rows[0][3] == "2024-12-31"
    assert "2025-01-01" not in outcome.result.rows[0][3]
    assert "2024-06-01" not in outcome.result.rows[0][3]
    assert "2024-06-02" not in outcome.result.rows[0][3]
    assert "2022" in response.text  # legislativeYear is display-only
    assert "Fake Bill" not in response.text
    query = fixture.queries[-1]
    assert "agents:CurrentBill" not in query
    assert "agents:Published" not in query  # exact mapped event IRI is fully expanded
    assert "https://data.oireachtas.ie/ontology#Published" in query
    assert 'DATATYPE(?eventDate) = xsd:date' in query
    assert 'REGEX(STR(?graph), "^https://data[.]oireachtas[.]ie/graph/bill/[0-9]{4}/[0-9]+$")' in query


def test_q20_non_enacted_is_distinct_controlled_status_count_and_display(monkeypatch):
    fixture = TinyDataset()
    add_bill_record(fixture, year=2026, number="1", title="Current Bill", status="current",
                    events=[("2026-01-01", AGENTS + "CommitteeStage"),
                            ("2026-02-01", AGENTS + "CommitteeStage")])
    add_bill_record(fixture, year=2026, number="2", title="Enacted Bill", status="enacted")
    response = _ask(monkeypatch, fixture, "What 2026 Bills haven't been enacted")
    assert response.status_code == 200
    assert "Current Bill" in response.text
    assert "Enacted Bill" not in response.text
    assert "Current: 1" in response.text
    assert "Current Bill" in response.text
    assert "COUNT(" not in fixture.queries[-1]  # grouping/deduplication is by Bill IRI before counts
    assert "activity_date" not in fixture.queries[-1]
    assert "?bill agents:legislativeYear ?requestedYear" in fixture.queries[-1]
    assert "?requestedYear = 2026" in fixture.queries[-1]

    unknown = TinyDataset()
    add_bill_record(unknown, year=2026, number="3", title="Unmapped status Bill",
                    status="https://data.oireachtas.ie/ontology#CurrentBillExtra")
    unknown_outcome = _run(unknown, "What 2026 Bills haven't been enacted")
    assert unknown_outcome.status == "incomplete_status_evidence"
    assert "not a recognized controlled Bill status" in unknown_outcome.diagnostic
    assert unknown_outcome.result.rows[0][3] == "Unknown/unmapped process status"

    conflicting_year = TinyDataset()
    add_bill_record(conflicting_year, year=2026, number="4", title="Conflicting year Bill",
                    year_values=[2025, 2026], status="lapsed")
    conflict = _run(conflicting_year, "What 2026 Bills haven't been enacted")
    assert conflict.status == "incomplete_display_evidence"
    assert conflict.result.rows[0][2] == "Conflicting legislativeYear"
    assert "legislativeYear display metadata is conflicting" in conflict.diagnostic


def test_q20_accepts_each_mapped_non_enacted_status_only_by_exact_status_iri():
    fixture = TinyDataset()
    values = ("awaiting-signature", "published", "defeated", "repugnant", "draft",
              "enacted", "lapsed", "withdrawn", "referendum")
    for number, status in enumerate(values, 1):
        add_bill_record(fixture, year=2026, number=str(number), title=f"Status case {status}", status=status)
    outcome = _run(fixture, "What 2026 Bills haven't been enacted")
    assert outcome.status == "success"
    assert len(outcome.result.rows) == 8
    assert "Enacted: 1" not in outcome.diagnostic
    assert "Awaiting signature: 1" in outcome.diagnostic
    assert "Current: 1" in outcome.diagnostic
    assert "Declared repugnant to the Constitution: 1" in outcome.diagnostic


def test_q21_missing_status_never_uses_latest_or_history_as_a_substitute():
    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="6", title="Housing Assistance Bill 2024",
                    status=None, events=[("2024-01-15", AGENTS + "CommitteeStage")])
    outcome = _run(fixture, "What is happening to the Housing Assistance Bill?")
    assert outcome.status == "incomplete_status_evidence"
    assert outcome.result.rows[0][1] == "Unknown process status"
    assert "Committee Stage: 2024-01-15" in outcome.result.rows[0][4]
    assert "No current process status is recorded" in outcome.diagnostic


def test_q22_sponsor_ask_preserves_each_participation_and_strict_boolean(monkeypatch):
    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="4", title="Artificial Intelligence Companion Services Bill",
                    events=[("2024-01-01", AGENTS + "FirstStage"),
                            ("2024-02-01", AGENTS + "CommitteeStage")],
                    sponsors=[{"member": "https://data.oireachtas.ie/ie/oireachtas/member/code/7",
                               "name": "Alice Example", "primary": False, "role": "Supporting sponsor"},
                              {"role": "Minister for Finance", "primary": None}])
    response = _ask(monkeypatch, fixture, "Who is the sponsor of the AI Companion Services Bill?")
    assert response.status_code == 200
    assert "Alice Example" in response.text
    assert "Supporting" in response.text
    assert "Minister for Finance" in response.text
    assert "Unknown (not recorded)" in response.text
    assert "?participation eli-dl:had_participant_person ?member" in fixture.queries[-1]
    assert "GRAPH ?memberGraph" in fixture.queries[-1]
    assert "^https://data[.]oireachtas[.]ie/graph/member/[^/]+$" in fixture.queries[-1]
    # Dated history is not joined into this route, so two activities cannot multiply sponsorship.
    assert "activity_date" not in fixture.queries[-1]


def test_q24a_memo_work_requires_typed_chain_and_all_renditions_with_no_decoys(monkeypatch):
    fixture = TinyDataset()
    bill, graph = add_bill_record(fixture, memos=[{"renditions": [
        "https://data.oireachtas.ie/memo.pdf", "https://data.oireachtas.ie/memo.xml"]}])
    wrong_type = URIRef(str(bill) + "#digest")
    graph.add((bill, URIRef(ELI + "has_part"), wrong_type))
    graph.add((wrong_type, RDF.type, URIRef(ELI + "Work")))
    graph.add((wrong_type, URIRef(ELI + "type_document"), URIRef(AGENTS + "Digest")))
    wrong_graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2025/23-extra"))
    other_memo = URIRef(str(bill) + "#other-memo")
    wrong_graph.add((bill, URIRef(ELI + "has_part"), other_memo))
    wrong_graph.add((other_memo, RDF.type, URIRef(ELI + "Work")))
    wrong_graph.add((other_memo, URIRef(ELI + "type_document"), URIRef(AGENTS + "ExplanatoryMemo")))
    response = _ask(monkeypatch, fixture, "Tell me about Bill 23 from 2025")
    assert "https://data.oireachtas.ie/memo.pdf" in response.text
    assert "https://data.oireachtas.ie/memo.xml" in response.text
    assert "#digest" not in response.text
    assert "other-memo" not in response.text

    missing_link = TinyDataset()
    add_bill_record(missing_link, memos=[{"expression": False}])
    incomplete = _run(missing_link, "Tell me about Bill 23 from 2025")
    assert incomplete.status == "incomplete_document_evidence"
    assert "Work exists, but no complete typed rendition chain" in incomplete.result.rows[0][5]
    assert "not absence of memorandum work" in incomplete.diagnostic

    no_bill_type = TinyDataset()
    add_bill_record(no_bill_type, bill_type=False)
    absent = _run(no_bill_type, "Tell me about Bill 23 from 2025")
    assert absent.status == "source_data_unavailable"
    assert "exact typed Bill is absent" in absent.diagnostic


def test_q24a_missing_reviewed_document_path_is_unsupported_not_no_memo(monkeypatch):
    import poc.nlq.stage_b as stage_b
    plan = plan_stage_b("Tell me about Bill 23 from 2025", as_of=AS_OF)
    fixture = TinyDataset()
    original_pattern = stage_b._reviewed_pattern
    def remove_documents(pattern_id, family_id):
        if pattern_id == "bill-document-work-links":
            raise PlanError("document chain gate removed")
        return original_pattern(pattern_id, family_id)
    monkeypatch.setattr(stage_b, "_reviewed_pattern", remove_documents)
    outcome = execute_stage_b(plan, fuseki=fixture,
                              supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "unsupported_mapping"
    assert "document chain gate removed" in outcome.diagnostic
    assert not fixture.queries


def test_q22_boolean_decode_is_strict_and_row_cap_is_readable_partial(monkeypatch):
    from poc.nlq.stage_b import _primary_status

    assert _primary_status({'"true"^^<http://www.w3.org/2001/XMLSchema#boolean>'}) == ("Primary", None)
    assert _primary_status({'"0"^^<http://www.w3.org/2001/XMLSchema#boolean>'}) == ("Supporting", None)
    assert _primary_status({'"nottrue"^^<http://www.w3.org/2001/XMLSchema#boolean>'})[1] == "malformed"
    assert _primary_status({'"true"^^<http://example.test/boolean>'})[1] == "malformed"
    assert _primary_status({
        '"true"^^<http://www.w3.org/2001/XMLSchema#boolean>',
        '"false"^^<http://www.w3.org/2001/XMLSchema#boolean>',
    })[1] == "conflicting"

    malformed_fixture = TinyDataset()
    add_bill_record(malformed_fixture, year=2024, number="4",
                    title="Artificial Intelligence Companion Services Bill",
                    sponsors=[{"role": "Minister for Finance", "raw_primary":
                               Literal("not-a-boolean", datatype=XSD.boolean, normalize=False)}])
    malformed = _run(malformed_fixture, "Who is the sponsor of the AI Companion Services Bill?")
    assert malformed.status == "incomplete_primary_status_evidence"
    assert malformed.result.rows[0][3] == "Malformed primary flag"

    fixture = TinyDataset()
    add_bill_record(fixture, year=2024, number="4", title="Artificial Intelligence Companion Services Bill",
                    sponsors=[{"role": f"Sponsor role {index}", "primary": False} for index in range(100)])
    response = _ask(monkeypatch, fixture, "Who is the sponsor of the AI Companion Services Bill?")
    assert "100-row safety cap was reached" in response.text
    assert "Sponsor role 0" in response.text and "Sponsor role 99" in response.text


def test_stage_b_query_execution_failure_is_not_reported_as_missing_mapping():
    class BrokenQuery:
        def query(self, _query):
            raise RuntimeError("simulated read-only endpoint failure")

    plan = plan_stage_b("What Bills were published in 2024", as_of=AS_OF)
    outcome = execute_stage_b(plan, fuseki=BrokenQuery(),
                              supported_predicates=supported_predicates(ROOT / "ontology"))
    assert outcome.status == "query_execution_failed"
    assert "did not complete" in outcome.diagnostic
    assert outcome.sparql is not None


def test_q12_and_q14_ask_diagnostics_do_not_invent_chair_or_misstate_conflict(monkeypatch):
    fixture = TinyDataset()
    fixture.add_current_committee(label="Committee on Transport and Communications")
    chair = _ask(monkeypatch, fixture, "Who is the Chair of the Committee on Transport?")
    assert "Committee on Transport and Communications" in chair.text
    assert "no reviewed chair/office-holder relationship is queryable" in chair.text
    assert "no chair is inferred from membership" in chair.text

    ambiguous_fixture = TinyDataset()
    ambiguous_fixture.add_current_committee(label="Committee on Transport", code="transport-1")
    ambiguous_fixture.add_current_committee(label="Committee on Transport", code="transport-2")
    ambiguous = _run(ambiguous_fixture, "Who is the Chair of the Committee on Transport?")
    assert ambiguous.status == "ambiguous"
    assert len(ambiguous.candidates) == 2
    assert all(candidate["iri"].startswith("https://data.oireachtas.ie/committee/")
               for candidate in ambiguous.candidates)

    conflict_fixture = TinyDataset()
    conflict = _ask(monkeypatch, conflict_fixture,
                    "Who are the Sinn Féin members of the Good Friday Committee?")
    assert "33rd-term Good Friday Committee source identity is conflicted/quarantined" in conflict.text
    assert "34th-term resource itself is conflicted" in conflict.text


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


def test_q25_executable_exact_member_overlap_and_visible_evidence(monkeypatch):
    from poc.nlq import app as app_module

    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": "Was Micheál Martin Taoiseach in September 2026?", "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Yes" in response.text
    assert "Micheál Martin" in response.text
    assert "2025-01-23" in response.text
    assert "inclusive calendar window is 2026-09-01 through 2026-09-30" in response.text
    assert "Validated composable query plan" in response.text
    assert any("VALUES ?member_member" in query for query in fixture.queries)


def test_q25_overlap_is_inclusive_and_q27_uses_exact_point_day():
    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2026-09-20T00:00:00", "2026-10-01T00:00:00")
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "success"
    assert outcome.result.rows[0][0] == "Yes"
    assert outcome.result.rows[0][2:] == ("2026-09-20", "2026-10-01")
    assert outcome.plan["family"] == "office_overlap"

    fixture = TinyDataset()
    fixture.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2022-12-17T00:00:00")
    outcome = _run(fixture, "Who was Minister for Finance on 1 July 2021?")
    assert outcome.status == "success"
    assert outcome.plan["family"] == "office_point"
    assert outcome.result.rows[0][0] == "Paschal Donohoe"

    fixture = TinyDataset()
    fixture.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2021-07-01T00:00:00")
    outcome = _run(fixture, "Who was Minister for Finance on 1 July 2021?")
    assert outcome.status == "success"
    assert outcome.result.rows[0][0] == "Paschal Donohoe"

    fixture = TinyDataset()
    fixture.add_office_tenure("Paschal Donohoe", "Minister for Finance", "2020-06-27T00:00:00", "2021-06-30T00:00:00")
    outcome = _run(fixture, "Who was Minister for Finance on 1 July 2021?")
    assert outcome.status == "source_data_unavailable"
    assert "No accepted local holding is recorded overlapping 2021-07-01 through 2021-07-01" in outcome.diagnostic


def test_q25_identity_resolution_ambiguity_empty_graph_and_nonmatching_holder_are_not_yes(monkeypatch):
    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00", code="micheal-martin-a")
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00", code="micheal-martin-b")
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "ambiguous"
    assert len(outcome.candidates) == 2
    assert len(fixture.queries) == 1  # Exact name resolution only; no office identity was guessed.

    fixture = TinyDataset()
    fixture.add_office_tenure("Other Person", "Taoiseach", "2025-01-23T00:00:00")
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "not_found"

    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00", "2026-08-31T00:00:00")
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "success"
    assert outcome.result.rows[0][0] == "No"
    assert outcome.result.rows[0][2:] == ("2025-01-23", "2026-08-31")
    assert "not proof of complete historical absence" in outcome.diagnostic
    response = _ask(monkeypatch, fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert "<td>No</td>" in response.text
    assert "2025-01-23" in response.text and "2026-08-31" in response.text

    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    member_graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/micheal-martin"))
    member_iri = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/micheal-martin")
    member_graph.remove((member_iri, URIRef(MEMBERS + "hasOfficeHolding"), None))
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "source_data_unavailable"
    assert "No accepted Member-owned OfficeHolding" in outcome.diagnostic
    assert "for the exact resolved Member" in outcome.diagnostic
    assert not outcome.result
    response = _ask(monkeypatch, fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert "No accepted Member-owned OfficeHolding" in response.text
    assert "<td>No</td>" not in response.text


def test_q25_conflicting_holding_dates_and_row_cap_fail_without_yes_no(monkeypatch):
    fixture = TinyDataset()
    fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00")
    graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/member/micheal-martin"))
    range_iri = URIRef("https://data.oireachtas.ie/ie/oireachtas/member/id/micheal-martin#holding#range")
    graph.add((range_iri, URIRef(MEMBERS + "StartDate"), Literal("2024-01-01T00:00:00", datatype=XSD.dateTime)))
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "source_data_unavailable"
    assert "conflicting Member or date evidence" in outcome.diagnostic
    assert not outcome.result or "Yes" not in str(outcome.result.rows)

    fixture = TinyDataset()
    for index in range(100):
        fixture.add_office_tenure("Micheál Martin", "Taoiseach", "2025-01-23T00:00:00",
                                  code="micheal-martin", holding_suffix=str(index))
    outcome = _run(fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert outcome.status == "insufficient_holding_evidence"
    assert "100-row safety cap" in outcome.diagnostic
    assert not outcome.result
    response = _ask(monkeypatch, fixture, "Was Micheál Martin Taoiseach in September 2026?")
    assert "100-row safety cap" in response.text
    assert "<strong>Yes</strong>" not in response.text
    assert "<strong>No</strong>" not in response.text


def test_q26_remains_incomplete_current_coverage_and_never_guesses_holder():
    fixture = TinyDataset()
    fixture.add_office_tenure("Finance Holder", "Minister for Finance", "2020-01-01T00:00:00")
    outcome = _run(fixture, "Who is Minister for Finance?")
    assert outcome.status == "source_data_unavailable"
    assert "incomplete 22-holding sample" in outcome.diagnostic
    assert "Finance Holder" not in outcome.diagnostic
