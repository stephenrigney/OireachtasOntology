"""Contract acceptance through the actual /ask boundary and safe RDF queries."""

import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD
from jsonschema import Draft202012Validator

from poc.nlq.composable_plan import PlanError, execute_question, validate_plan
from poc.nlq.composable_semantic_planner import InvalidComposableDraft, complete_v2_plan, validate_composable_plan_draft
from poc.nlq.results import QueryResult
from poc.nlq.errors import NLQError
from poc.nlq.vocabulary import supported_predicates
from test_nlq_composable_party_temporal import (
    PartyRepresentationFixture, FixedPlanGenerator, _temporal_draft, _binding,
    _current_term_fixture, MEMBER, CURRENT_CONSTITUENCY, FOAF, SKOS,
)
from test_nlq_composable_semantic_capability_discovery import _selection


ROOT = Path(__file__).resolve().parents[1]
AS_OF = date(2026, 11, 2)
PREDICATES = supported_predicates(ROOT / "ontology")
BASE = "https://data.oireachtas.ie/"
A = Namespace(BASE + "ontology#")
M = Namespace(BASE + "ontology/members#")
S = Namespace(SKOS)
F = Namespace(FOAF)
DCT = Namespace("http://purl.org/dc/terms/")
DCAT = Namespace("http://www.w3.org/ns/dcat#")


def client(monkeypatch, fixture, draft):
    from poc.nlq import app as app_module
    generator = FixedPlanGenerator(draft)
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **kw: fixture)
    return TestClient(app_module.create_app(repository_root=ROOT, semantic_plan_generator_factory=lambda: generator)), generator


def test_default_current_party_representation_is_explicit_and_contemporaneous(monkeypatch):
    fixture = _current_term_fixture()
    fixture.dataset.graph(URIRef(BASE + "graph/constituencies")).set((URIRef(CURRENT_CONSTITUENCY), S.prefLabel, Literal("Dublin Central", lang="en")))
    fixture.dataset.graph(URIRef(BASE + "graph/member/Aoife-Byrne")).set((URIRef(MEMBER), F.name, Literal("Mary Lou McDonald")))
    draft = _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", constituency="Dublin Central", term_selector={"kind": "currentTerm"})
    c, _ = client(monkeypatch, fixture, draft)
    response = c.post("/ask", data={"question": "Which Sinn Féin TDs represent Dublin Central?"})
    assert 'data-outcome="answer"' in response.text
    assert "Mary Lou McDonald" in response.text
    assert "2026-11-02" in response.text and "present_constituency_as_of" in response.text
    # The compiler uses the same contemporaneous episode checks as explicit now.
    assert "membership" in fixture.queries[-1] and "episode" in fixture.queries[-1]


@pytest.mark.parametrize("question", [
    "Which Sinn Féin TDs represented Dublin Central?",
    "Which Sinn Féin TDs represented Dublin Central during the 12th Dáil?",
    "Which Sinn Féin TDs were elected for Dublin Central?",
    "Which Sinn Féin TDs will represent Dublin Central?",
    "Which Sinn Féin TDs might represent Dublin Central?",
    "Who should be representing Dublin Central for Sinn Féin?",
    "Who is planned to represent Dublin Central for Sinn Féin?",
])
def test_default_guard_cannot_be_used_for_history_or_elections(question):
    draft = _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", constituency="Dublin Central", term_selector={"kind": "currentTerm"})
    with pytest.raises(InvalidComposableDraft):
        validate_composable_plan_draft(draft, question=question)


def test_dail_composition_cannot_replace_a_seanad_request():
    draft = _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", constituency="Dublin Central", term_selector={"kind": "currentTerm"})
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question="Which Sinn Féin senators currently represent Dublin Central?")


def test_default_evidence_revalidated_not_a_validator_bypass():
    draft = _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", term_selector={"kind": "currentTerm"})
    plan, _ = validate_composable_plan_draft(draft, question="Which Sinn Féin TDs represent Galway West?")
    plan = complete_v2_plan(plan, as_of=AS_OF)
    assert validate_plan(plan) == plan
    Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text())).validate(plan)
    for key, bad in (("date", "2000-01-01"), ("question", "Which TDs were elected in Galway West?"), ("policy", "anything")):
        corrupt = copy.deepcopy(plan)
        corrupt["interpretation"][key] = bad
        with pytest.raises(PlanError):
            validate_plan(corrupt)


@pytest.mark.parametrize("fixture", [
    lambda: _current_term_fixture(party_interval=("2020-01-01T00:00:00", "2020-12-31T00:00:00")),
    lambda: _current_term_fixture(membership_interval=("2020-01-01T00:00:00", "2020-12-31T00:00:00")),
    lambda: _current_term_fixture(term_dates=("not-a-date", None)),
])
def test_default_does_not_turn_historical_or_uncertain_evidence_current(monkeypatch, fixture):
    draft = _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", term_selector={"kind": "currentTerm"})
    c, _ = client(monkeypatch, fixture(), draft)
    response = c.post("/ask", data={"question": "Which Sinn Féin TDs represent Galway West?"})
    assert 'data-outcome="answer"' not in response.text


class IdentityFixture(PartyRepresentationFixture):
    def __init__(self):
        self.dataset = Dataset()
        self.queries = []
        self.houses = self.dataset.graph(URIRef(BASE + "graph/houses"))
        self.constituencies = self.dataset.graph(URIRef(BASE + "graph/constituencies"))
        for n in range(12, 22):
            term = URIRef(BASE + f"ie/oireachtas/houseTerm/dail/{n}")
            period = URIRef(str(term) + "#dates")
            for triple in ((term, RDF.type, A.DailTerm), (term, A.termNo, Literal(n)),
                           (term, S.prefLabel, Literal(f"{n}th Dáil", lang="en")), (term, A.termOf, URIRef(BASE + "ie/oireachtas/house/dail")),
                           (term, DCT.temporal, period), (period, RDF.type, DCT.PeriodOfTime),
                           (period, DCAT.startDate, Literal(f"{1900+n}-01-01", datatype=XSD.date))):
                self.houses.add(triple)
        self.add_member("Noel-Browne", "Noel Browne", [12])
        self.add_member("James-Browne", "James Browne", [13])
        self.add_member("Senator-Browne", "Senator Browne", [])
        self.jack = self.add_member("John-Lynch-1948", "John Lynch", list(range(13, 22)), source_id="JackLynch")
        self.other_john = self.add_member("John-Lynch-1951", "John Lynch", [14])
        self.add_member("Stephen-Donnelly", "Stephen Donnelly", [21])
        parties = self.dataset.graph(URIRef(BASE + "graph/parties"))
        for n in range(6):
            party = URIRef(BASE + f"ie/oireachtas/party/dail/12/{n}")
            parties.add((party, RDF.type, M.ParliamentaryParty))
            parties.add((party, M.activeDuringTerm, URIRef(BASE + "ie/oireachtas/houseTerm/dail/12")))
            parties.add((party, S.prefLabel, Literal(f"Recorded party {n}", lang="en")))

    def add_member(self, key, name, terms, source_id=None):
        member = URIRef(BASE + "ie/oireachtas/member/id/" + key)
        g = self.dataset.graph(URIRef(BASE + "graph/member/" + key))
        g.add((member, RDF.type, A.Member)); g.add((member, F.name, Literal(name)))
        if source_id:
            g.add((member, A.pId, Literal(source_id)))
        for n in terms:
            term = URIRef(BASE + f"ie/oireachtas/houseTerm/dail/{n}")
            membership = URIRef(str(member) + f"#dail-{n}")
            constituency = URIRef(BASE + f"ie/oireachtas/constituency/dail/Cork-{key}-{n}")
            g.add((member, M.hasMembersMembership, membership)); g.add((membership, RDF.type, M.DailMembership))
            g.add((membership, M.inHouseTerm, term)); g.add((membership, M.isRepresentativeFrom, constituency))
            self.constituencies.add((constituency, RDF.type, M.DailConstituency))
            self.constituencies.add((constituency, M.constituencyInHouseTerm, term))
            self.constituencies.add((constituency, S.prefLabel, Literal("Cork", lang="en")))
        return str(member)


def test_grounded_deputy_choice_continues_original_lookup_and_rejects_replay(monkeypatch):
    fixture = IdentityFixture()
    c, generator = client(monkeypatch, fixture, _selection("member_lookup", {"member": "Browne", "house": "Dail"}))
    question = "Find a Deputy called Browne"
    response = c.post("/ask", data={"question": question})
    assert 'data-outcome="clarification_required"' in response.text
    assert "Noel Browne" in response.text and "James Browne" in response.text
    assert "Senator Browne" not in response.text
    assert 'name="choice"' in response.text and "12th Dáil" in response.text
    token = re.search(r'name="continuation" value="([^"]+)"', response.text)[1]
    continued = c.post("/ask", data={"question": question, "continuation": token, "choice": "0"})
    assert 'data-outcome="answer"' in continued.text and "James Browne" in continued.text
    assert "Source identity" in continued.text
    assert generator.calls == [question]  # no conversational replanning
    replay = c.post("/ask", data={"question": question, "continuation": token, "choice": "0"})
    assert 'data-outcome="validation_failure"' in replay.text


@pytest.mark.parametrize("question", ["Find TDs called Browne", "Identify Deputies called Browne"])
def test_plural_deputy_paraphrases_preserve_service_scope(monkeypatch, question):
    c, _ = client(monkeypatch, IdentityFixture(), _selection("member_lookup", {"member": "Browne", "house": "Dail"}))
    response = c.post("/ask", data={"question": question})
    assert 'data-outcome="clarification_required"' in response.text
    assert "Noel Browne" in response.text and "James Browne" in response.text
    assert "Senator Browne" not in response.text


@pytest.mark.parametrize("choice", ["-1", "999", "0" * 5000, BASE + "ie/oireachtas/member/id/Noel-Browne"])
def test_candidate_form_never_accepts_arbitrary_identity(monkeypatch, choice):
    c, _ = client(monkeypatch, IdentityFixture(), _selection("member_lookup", {"member": "Browne", "house": "Dail"}))
    question = "Find a Deputy called Browne"
    response = c.post("/ask", data={"question": question})
    token = re.search(r'name="continuation" value="([^"]+)"', response.text)[1]
    response = c.post("/ask", data={"question": question, "continuation": token, "choice": choice})
    assert 'data-outcome="validation_failure"' in response.text


@pytest.mark.parametrize("change", ["question", "date", "expiry", "source"])
def test_continuation_is_bound_to_intent_date_and_rechecked_source(monkeypatch, change):
    from poc.nlq import app as app_module
    fixture = IdentityFixture()
    c, generator = client(monkeypatch, fixture, _selection("member_lookup", {"member": "Browne", "house": "Dail"}))
    question = "Find a Deputy called Browne"
    response = c.post("/ask", data={"question": question})
    token = re.search(r'name="continuation" value="([^"]+)"', response.text)[1]
    if change == "question":
        question = "Find a Deputy called Lynch"
    elif change == "date":
        monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", "2026-11-03")
    elif change == "expiry":
        clock = app_module.monotonic()
        monkeypatch.setattr(app_module, "monotonic", lambda: clock + 601)
    else:
        fixture.dataset.graph(URIRef(BASE + "graph/member/James-Browne")).remove((None, None, None))
    response = c.post("/ask", data={"question": question, "continuation": token, "choice": "0"})
    assert 'data-outcome="validation_failure"' in response.text
    assert len(generator.calls) == 1


def test_party_only_dispatch_uses_existing_compiler_without_group_warning(monkeypatch):
    c, _ = client(monkeypatch, IdentityFixture(), _selection("dail_parties_and_groups", {"termNumber": 12, "includeGroups": False}))
    response = c.post("/ask", data={"question": "What were the parties during the 12th Dáil?"})
    assert 'data-outcome="answer"' in response.text
    assert all(f"Recorded party {i}" in response.text for i in range(6))
    assert "ParliamentaryGroup" not in response.text


def test_source_identifier_alias_keeps_nine_occurrences_and_separate_johns(monkeypatch):
    fixture = IdentityFixture()
    c, _ = client(monkeypatch, fixture, None)
    response = c.post("/ask", data={"question": "What constituencies did Jack Lynch represent?"})
    assert 'data-outcome="answer"' in response.text
    assert all(f"{n}th Dáil" in response.text for n in range(13, 22))
    assert fixture.other_john not in response.text
    response = c.post("/ask", data={"question": "What constituencies did John Lynch represent?"})
    assert 'data-outcome="clarification_required"' in response.text
    assert fixture.jack in response.text and fixture.other_john in response.text


def test_source_alias_is_not_nickname_guessing_or_identity_merging(monkeypatch):
    fixture = IdentityFixture()
    fixture.dataset.graph(URIRef(BASE + "graph/member/John-Lynch-1948")).remove((None, A.pId, None))
    c, _ = client(monkeypatch, fixture, None)
    response = c.post("/ask", data={"question": "What constituencies did Jack Lynch represent?"})
    assert 'data-outcome="unresolved_identity"' in response.text
    fixture.dataset.graph(URIRef(BASE + "graph/member/John-Lynch-1948")).add((URIRef(fixture.jack), A.pId, Literal("JackLynch")))
    fixture.dataset.graph(URIRef(BASE + "graph/member/John-Lynch-1951")).add((URIRef(fixture.other_john), A.pId, Literal("JackLynch")))
    response = c.post("/ask", data={"question": "What constituencies did Jack Lynch represent?"})
    assert 'data-outcome="clarification_required"' in response.text


def test_member_lookup_reuses_source_identifier_alias_rule(monkeypatch):
    fixture = IdentityFixture()
    c, _ = client(monkeypatch, fixture, _selection("member_lookup", {"member": "Jack Lynch", "house": "Dail"}))
    response = c.post("/ask", data={"question": "Find a Deputy called Jack Lynch"})
    assert 'data-outcome="answer"' in response.text
    assert "John Lynch" in response.text and fixture.other_john not in response.text


def test_absent_accepted_office_is_evidence_boundary_not_tenure_answer(monkeypatch):
    draft = _selection("office_holding_evidence", {"member": "Stephen Donnelly", "office": "Minister for Health"})
    c, _ = client(monkeypatch, IdentityFixture(), draft)
    response = c.post("/ask", data={"question": "When was Stephen Donnelly the Minister for Health?"})
    assert 'data-outcome="missing_or_unaccepted_evidence"' in response.text
    assert "Unreviewed ministerial observations" in response.text
    assert "<h2>Results</h2>" not in response.text


def test_office_duration_remains_unsupported_as_a_whole(monkeypatch):
    draft = _selection("office_holding_evidence", {"member": "Stephen Donnelly", "office": "Minister for Health"})
    fixture = IdentityFixture()
    c, _ = client(monkeypatch, fixture, draft)
    response = c.post("/ask", data={"question": "How long was Stephen Donnelly the Minister for Health?"})
    assert 'data-outcome="unsupported_capability"' in response.text
    assert not fixture.queries


@pytest.mark.parametrize(("question", "draft"), [
    ("Find a Deputy called Browne who sponsored Bills", _selection("member_lookup", {"member": "Browne", "house": "Dail"})),
    ("Find a Deputy called Browne and list his committees", _selection("member_lookup", {"member": "Browne", "house": "Dail"})),
    ("List only the parties with TDs in the 12th Dáil", _selection("dail_parties_and_groups", {"termNumber": 12, "includeGroups": False})),
    ("What parties were in the 12th Dáil excluding Labour?", _selection("dail_parties_and_groups", {"termNumber": 12, "includeGroups": False})),
])
def test_semantic_dispatch_does_not_drop_an_extra_condition(question, draft):
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question=question)


def test_first_election_is_unsupported_not_membership_start(monkeypatch):
    draft = {"version": 2, "supported": False, "family": None,
             "unsupportedReason": "Election-event evidence is not queryable; a membership start is not an election date.",
             "intent": "First election date", "referents": None, "relations": [], "constraints": [], "answer": None}
    fixture = IdentityFixture()
    c, _ = client(monkeypatch, fixture, draft)
    response = c.post("/ask", data={"question": "When was Jack Lynch first elected to the Dáil?"})
    assert 'data-outcome="unsupported_capability"' in response.text
    assert not fixture.queries


def test_election_cannot_be_substituted_by_service_entry_or_constituency():
    with pytest.raises(ValueError):
        validate_composable_plan_draft(_selection("seanad_entry", {"member": "Jack Lynch"}),
                                       question="When was Jack Lynch first elected to the Seanad?")
    from poc.nlq.representation import representation_plan
    base = representation_plan(as_of=AS_OF, member="Jack Lynch", current=False)
    draft = {"version": 2, "supported": True, "family": "constituency_representation",
             "unsupportedReason": None, "intent": "Constituencies", "constraints": [],
             "referents": {key: {"type": ref["type"], "mention": ref.get("mention"),
                                  **({"selector": None} if key == "term" else {})}
                           for key, ref in base["referents"].items()},
             "relations": base["relations"], "answer": base["answer"]}
    with pytest.raises(ValueError):
        validate_composable_plan_draft(draft, question="When was Jack Lynch first elected to the Dáil?")


def test_party_scope_schema_and_runtime_are_synchronized():
    from poc.nlq.stage_c import _make_plan
    plan = _make_plan("dail_parties_and_groups", AS_OF, ordinal=12)
    plan["answer"]["includeGroups"] = False
    assert validate_plan(plan) == plan
    schema = Draft202012Validator(json.loads((ROOT / "poc/specs/composable-query-plan.schema.json").read_text()))
    schema.validate(plan)
    plan["answer"]["includeGroups"] = "false"
    assert list(schema.iter_errors(plan))
    with pytest.raises(PlanError):
        validate_plan(plan)


@pytest.mark.parametrize(("question", "draft"), [
    ("Find a Deputy called Browne", _selection("member_lookup", {"member": "Browne", "house": "Dail"})),
    ("Which Sinn Féin TDs represent Galway West?", _temporal_draft(answer_referent="member", affiliation_mention="Sinn Féin", term_selector={"kind": "currentTerm"})),
    ("What constituencies did Jack Lynch represent?", None),
])
def test_transport_failure_is_never_missing_evidence(monkeypatch, question, draft):
    class Broken(IdentityFixture):
        def query(self, query):
            raise NLQError("Endpoint timed out")
    c, _ = client(monkeypatch, Broken(), draft)
    response = c.post("/ask", data={"question": question})
    assert 'data-outcome="execution_failure"' in response.text
    assert "<h2>Results</h2>" not in response.text


def test_member_identity_safety_cap_is_validation_not_missing_evidence(monkeypatch):
    class Capped(IdentityFixture):
        def query(self, query):
            return QueryResult("select", ("member", "name"), tuple((BASE + f"ie/oireachtas/member/id/browne-{n}", "Browne") for n in range(100)))
    c, _ = client(monkeypatch, Capped(), _selection("member_lookup", {"member": "Browne", "house": "Dail"}))
    response = c.post("/ask", data={"question": "Find a Deputy called Browne"})
    assert 'data-outcome="validation_failure"' in response.text
