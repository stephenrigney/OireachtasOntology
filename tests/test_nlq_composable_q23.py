"""Synthetic RDF acceptance for the composable Query Service Q23 slice."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from poc.nlq.composable_plan import (
    PlanError,
    compile_bill_sponsorship_answer_query,
    execute_question,
    plan_question,
    validate_plan,
)
from poc.nlq.errors import NLQError
from poc.nlq.fuseki import FusekiReadiness
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 10, 28)
QUESTION = "Which bills did Malcolm Byrne sponsor?"
AGENTS = "https://data.oireachtas.ie/ontology#"
ELI = "http://data.europa.eu/eli/ontology#"
ELI_DL = "http://data.europa.eu/eli/eli-draft-legislation-ontology#"
MEMBER_IRI = "https://data.oireachtas.ie/ie/oireachtas/member/id/Malcolm-Byrne.D.2019-11-29"


def _serialize_binding(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, Literal):
        if value.language:
            return f"{value}@{value.language}"
        if value.datatype:
            return f"{value}^^<{value.datatype}>"
    return str(value)


class BillSponsorshipFixture:
    """Small named-graph fixture with exact Member references and Bill ownership."""

    def __init__(self, *, with_member: bool = True, ambiguous_member: bool = False):
        self.dataset = Dataset()
        self.queries: list[str] = []
        self.member_iris: list[str] = []
        if with_member:
            self.add_member(MEMBER_IRI, "Malcolm Byrne", "Malcolm-Byrne.D.2019-11-29")
            if ambiguous_member:
                self.add_member(
                    "https://data.oireachtas.ie/ie/oireachtas/member/id/Malcolm-Byrne.D.duplicate",
                    "Malcolm Byrne", "Malcolm-Byrne.D.duplicate",
                )

    def add_member(self, member_iri: str, name: str, graph_key: str) -> None:
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/member/{graph_key}"))
        member = URIRef(member_iri)
        graph.add((member, RDF.type, URIRef(AGENTS + "Member")))
        graph.add((member, URIRef("http://xmlns.com/foaf/0.1/name"), Literal(name)))
        self.member_iris.append(member_iri)

    def add_bill(
        self,
        year: int,
        number: str,
        title_en: str | None,
        participations: tuple[dict, ...],
        *,
        title_ga: str | None = None,
        include_process: bool = True,
        include_number: bool = True,
        include_year: bool = True,
    ) -> str:
        bill_text = f"https://data.oireachtas.ie/ie/oireachtas/bill/{year}/{number}"
        bill = URIRef(bill_text)
        graph = self.dataset.graph(URIRef(f"https://data.oireachtas.ie/graph/bill/{year}/{number}"))
        graph.add((bill, RDF.type, URIRef(ELI_DL + "DraftLegislationWork")))
        graph.add((bill, URIRef(ELI + "type_document"), URIRef(AGENTS + "Bill")))
        if include_year:
            graph.add((bill, URIRef(AGENTS + "legislativeYear"), Literal(year, datatype=XSD.integer)))
        if title_en is not None:
            graph.add((bill, URIRef(ELI + "title"), Literal(title_en, lang="en")))
        if title_ga is not None:
            graph.add((bill, URIRef(ELI + "title"), Literal(title_ga, lang="ga")))
        if include_process:
            process = URIRef(bill_text + "#process")
            graph.add((process, RDF.type, URIRef(ELI_DL + "LegislativeProcess")))
            if include_number:
                graph.add((process, URIRef(ELI_DL + "process_number"), Literal(number, datatype=XSD.string)))
            for index, evidence in enumerate(participations):
                participation = URIRef(f"{bill_text}#process%23sponsor-{index}")
                graph.add((process, URIRef(ELI_DL + "had_participation"), participation))
                graph.add((participation, RDF.type, URIRef(ELI_DL + "Participation")))
                graph.add((participation, URIRef(ELI_DL + "had_participant_person"), URIRef(evidence.get("member", MEMBER_IRI))))
                if "primary" in evidence:
                    flags = evidence["primary"]
                    if not isinstance(flags, tuple):
                        flags = (flags,)
                    for flag in flags:
                        graph.add((participation, URIRef(AGENTS + "isPrimarySponsor"), Literal(flag, datatype=XSD.boolean)))
                if evidence.get("role"):
                    graph.add((participation, RDFS.label, Literal(evidence["role"])))
        return bill_text

    def readiness(self):
        names = ("Houses", "Parties", "Constituencies", "Members", "Bills", "Offices")
        return FusekiReadiness("ready", True, tuple((name, True) for name in names), "synthetic Q23 fixture")

    def close(self):
        pass

    def query(self, query: str) -> QueryResult:
        self.queries.append(query)
        raw = self.dataset.query(query)
        if raw.type == "ASK":
            return QueryResult("ask", boolean=bool(raw.askAnswer))
        columns = tuple(str(variable) for variable in raw.vars)
        rows = tuple(tuple(_serialize_binding(value) for value in row) for row in raw)
        return QueryResult("select", columns, rows)


def _run(fixture: BillSponsorshipFixture, question: str = QUESTION):
    return execute_question(
        question, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology"),
    )


def _resolved_plan():
    plan = plan_question(QUESTION, as_of=AS_OF)
    plan["referents"]["member"].update({
        "resolution": "resolved", "iri": MEMBER_IRI, "label": "Malcolm Byrne",
    })
    return plan


def test_q23_plan_schema_and_validator_accept_only_the_typed_sponsorship_path():
    plan = plan_question(QUESTION, as_of=AS_OF)
    schema = json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    assert Draft202012Validator(schema).is_valid(plan)
    assert set(plan["referents"]) == {"member", "participation", "bill"}
    assert [item["fact"] for item in plan["relations"]] == [
        "bill_has_sponsor_participation", "participation_has_participant",
    ]
    assert plan["answer"]["preserveEvidence"] is True

    disconnected = json.loads(json.dumps(plan))
    disconnected["referents"]["orphan"] = {"type": "Bill"}
    with pytest.raises(PlanError):
        validate_plan(disconnected)
    unsupported = json.loads(json.dumps(plan))
    unsupported["relations"][1]["fact"] = "member_name_is_sponsor"
    with pytest.raises(PlanError, match="Unsupported semantic mapping"):
        validate_plan(unsupported)
    wrong_answer = json.loads(json.dumps(plan))
    wrong_answer["answer"]["display"] = ["label"]
    with pytest.raises(PlanError):
        validate_plan(wrong_answer)


def test_q23_compiler_is_deterministic_safe_and_uses_same_graph_ownership_not_a_direct_edge():
    supported = supported_predicates(ROOT / "ontology")
    plan = _resolved_plan()
    query1 = compile_bill_sponsorship_answer_query(plan, supported_predicates=supported)
    query2 = compile_bill_sponsorship_answer_query(plan, supported_predicates=supported)
    assert query1 == query2
    assert "SELECT DISTINCT ?billGraph ?bill ?participation" in query1
    assert "GRAPH ?billGraph" in query1
    assert "?process a eli-dl:LegislativeProcess ; eli-dl:had_participation ?participation" in query1
    assert "eli-dl:had_participant_person <" + MEMBER_IRI + ">" in query1
    assert "agents:isPrimarySponsor ?primaryEvidence" in query1
    assert 'FILTER(LANG(?englishTitle) = "en")' in query1
    assert "eli-dl:process_number ?billNumber" in query1
    assert "?bill eli-dl:had_participation" not in query1
    assert "SERVICE" not in query1 and "FROM NAMED" not in query1 and "UPDATE" not in query1

    with pytest.raises(NLQError, match="isPrimarySponsor"):
        compile_bill_sponsorship_answer_query(
            plan,
            supported_predicates=supported - {URIRef(AGENTS + "isPrimarySponsor")},
        )


def test_q23_mapping_contract_matches_emitted_ontology_and_bill_transform_evidence():
    contract = json.loads((ROOT / "poc/specs/query-schema-contract.json").read_text())
    assert contract["contractVersion"] == "2.7.0"
    assert "agents:isPrimarySponsor" in contract["queryableProperties"]
    pattern = next(item for item in contract["emittedRdfPatterns"] if item["id"] == "bill-sponsor-reference")
    assert ["?participation", "agents:isPrimarySponsor", "?optionalBoolean"] in pattern["triples"]
    assert "absence means unknown" in pattern["note"]
    assert "no direct Bill-to-process predicate" in pattern["note"]
    assert any(
        join["fromGraphFamily"] == "bill-records"
        and join["predicate"] == "eli-dl:had_participant_person"
        and join["toGraphFamily"] == "member-records"
        and join["joinKey"] == "same RDF resource IRI"
        for join in contract["crossGraphJoins"]
    )

    with (ROOT / "mappings/bill_mapping.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    primary = next(row for row in rows if row["json_path"] == "results[].bill.sponsors[].sponsor.isPrimary")
    assert (primary["ontology_term"], primary["mapping_status"]) == (":isPrimarySponsor", "new")
    assert "Null means unknown" in primary["notes"]


def test_q23_returns_every_matching_bill_once_and_preserves_each_participation_status_and_role():
    fixture = BillSponsorshipFixture()
    bill1 = fixture.add_bill(2026, "93", "Artificial Intelligence Companion Services (Protection of Children) Bill 2026", (
        {"primary": True, "role": "TD"},
        {"primary": False, "role": "Co-sponsor"},
    ), title_ga="Bille um Sheirbhísí Compánacha Faisnéise Saorga 2026")
    bill2 = fixture.add_bill(2024, "17", "Community Safety Bill 2024", (
        {"role": "Member"},
    ))
    fixture.add_bill(2025, "19", "Other Member's Bill 2025", (
        {"primary": True, "member": "https://data.oireachtas.ie/ie/oireachtas/member/id/Other-Member"},
    ))

    # This Bill is owned in one graph, while its process and participant facts
    # are in another; graph co-ownership must prevent a false Bill association.
    detached_bill = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/99")
    detached_graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2024/99"))
    detached_graph.add((detached_bill, RDF.type, URIRef(ELI_DL + "DraftLegislationWork")))
    detached_graph.add((detached_bill, URIRef(ELI + "type_document"), URIRef(AGENTS + "Bill")))
    detached_graph.add((detached_bill, URIRef(ELI + "title"), Literal("Detached Bill 2024", lang="en")))
    foreign_graph = fixture.dataset.graph(URIRef("https://data.oireachtas.ie/graph/bill/2024/100"))
    foreign_process = URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2024/100#process")
    foreign_participation = URIRef(str(foreign_process) + "%23sponsor-foreign")
    foreign_graph.add((foreign_process, RDF.type, URIRef(ELI_DL + "LegislativeProcess")))
    foreign_graph.add((foreign_process, URIRef(ELI_DL + "had_participation"), foreign_participation))
    foreign_graph.add((foreign_participation, RDF.type, URIRef(ELI_DL + "Participation")))
    foreign_graph.add((foreign_participation, URIRef(ELI_DL + "had_participant_person"), URIRef(MEMBER_IRI)))

    outcome = _run(fixture)
    assert outcome.status == "incomplete_primary_status_evidence", outcome.diagnostic
    assert len(outcome.result.rows) == 2
    assert {row[-1] for row in outcome.result.rows} == {bill1, bill2}
    by_link = {row[-1]: row for row in outcome.result.rows}
    assert by_link[bill1][0] == "Artificial Intelligence Companion Services (Protection of Children) Bill 2026"
    assert by_link[bill1][1] == "Primary (1 participation); Supporting (1 participation)"
    assert by_link[bill1][2:4] == ("93", "2026")
    assert "TD" in by_link[bill1][4] and "Co-sponsor" in by_link[bill1][4]
    assert by_link[bill2][1] == "Unknown (primary-status flag absent)"
    assert by_link[bill2][0] == "Community Safety Bill 2024"
    assert "does not certify complete historical" in outcome.diagnostic


def test_q23_does_not_substitute_irish_titles_and_reports_missing_english_display_evidence():
    fixture = BillSponsorshipFixture()
    bill = fixture.add_bill(2023, "7", None, ({"primary": False},), title_ga="Teideal Gaeilge amháin")
    outcome = _run(fixture)
    assert outcome.status == "incomplete_display_evidence"
    assert len(outcome.result.rows) == 1
    row = outcome.result.rows[0]
    assert row[0] == "English short title not recorded"
    assert "Teideal Gaeilge" not in repr(row)
    assert row[1] == "Supporting"
    assert row[2:4] == ("7", "2023")
    assert row[-1] == bill


def test_q23_surfaces_conflicting_flags_on_one_participation_instead_of_selecting_a_value():
    fixture = BillSponsorshipFixture()
    bill = fixture.add_bill(2026, "12", "Conflicting Evidence Bill 2026", (
        {"primary": (True, False)},
    ))
    outcome = _run(fixture)
    assert outcome.status == "conflicting_sponsorship_evidence"
    row = outcome.result.rows[0]
    assert row[-1] == bill
    assert "Conflicting primary-status values" in row[1]
    assert "Primary" in row[1] and "Supporting" in row[1]


def test_q23_resolution_is_exact_and_ambiguous_member_blocks_sponsorship_query():
    fixture = BillSponsorshipFixture(ambiguous_member=True)
    fixture.add_bill(2026, "93", "Companion Services Bill 2026", ({"primary": True},))
    outcome = _run(fixture)
    assert outcome.status == "ambiguous"
    assert len(outcome.candidates) == 2
    assert len(fixture.queries) == 1
    assert all("had_participation" not in query for query in fixture.queries)

    missing = _run(BillSponsorshipFixture(with_member=False))
    assert missing.status == "not_found"
    assert len(missing.plan["referents"]["member"]["mention"]) > 0


@pytest.mark.parametrize(("case", "expected"), [
    ("no_bills", "missing_sponsorship_evidence"),
    ("bill_no_participation", "missing_sponsorship_evidence"),
    ("other_member_participation", "source_data_unavailable"),
])
def test_q23_missing_sponsorship_evidence_is_distinct_from_member_resolution_and_not_a_negative(case, expected):
    fixture = BillSponsorshipFixture()
    if case == "bill_no_participation":
        fixture.add_bill(2026, "1", "No Participation Bill 2026", (), include_process=False)
    elif case == "other_member_participation":
        fixture.add_bill(2026, "2", "Other Member Bill 2026", ({
            "primary": False, "member": "https://data.oireachtas.ie/ie/oireachtas/member/id/Other-Member",
        },))
    outcome = _run(fixture)
    assert outcome.status == expected
    assert outcome.result is None
    assert ("not" in outcome.diagnostic.lower() or "negative" in outcome.diagnostic.lower())
    diagnostic = outcome.diagnostic.lower()
    assert (
        "confirmed" in diagnostic
        or "coverage" in diagnostic
        or "negative" in diagnostic
        or "absence is not evidence" in diagnostic
    )


def test_q23_query_allowlist_failure_is_reported_as_unsupported_mapping():
    fixture = BillSponsorshipFixture()
    fixture.add_bill(2026, "93", "Companion Services Bill 2026", ({"primary": True},))
    outcome = execute_question(
        QUESTION, as_of=AS_OF, fuseki=fixture,
        supported_predicates=supported_predicates(ROOT / "ontology") - {URIRef(AGENTS + "isPrimarySponsor")},
    )
    assert outcome.status == "unsupported_mapping"
    assert "isPrimarySponsor" in outcome.diagnostic
    assert len(fixture.queries) == 1  # identity lookup only; no answer query


def test_q23_ask_renders_readable_rows_official_link_unknown_and_coverage(monkeypatch):
    from poc.nlq import app as app_module

    fixture = BillSponsorshipFixture()
    bill = fixture.add_bill(2026, "93", "Companion Services Bill 2026", ({},))
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: fixture)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert response.status_code == 200
    assert "Companion Services Bill 2026" in response.text
    assert "Unknown (primary-status flag absent)" in response.text
    assert f'href="{bill}"' in response.text
    assert "Official Bill" in response.text
    assert "does not certify complete historical coverage" in response.text
    assert "Validated composable query plan" in response.text


def test_q23_ask_reports_unresolved_and_ambiguous_members_without_misleading_results(monkeypatch):
    from poc.nlq import app as app_module

    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    ambiguous = BillSponsorshipFixture(ambiguous_member=True)
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: ambiguous)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert "Ambiguous entity" in response.text
    assert "no Member was selected" in response.text
    assert "Possible local matches" in response.text

    missing = BillSponsorshipFixture(with_member=False)
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *args, **kwargs: missing)
    response = TestClient(app_module.create_app(repository_root=ROOT)).post("/ask", data={
        "question": QUESTION, "mode": "phase2",
    })
    assert "Entity not found" in response.text
    assert "No matching local Member record" in response.text
