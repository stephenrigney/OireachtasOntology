"""Term-count equivalence laws and complete-intent adversarial mutations."""

import itertools
import importlib
import json

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from poc.nlq.composable_semantic_planner import validate_composable_plan_draft
from poc.nlq.term_count_intent import analyse_term_count
from tests.test_nlq_composable_semantic_capability_discovery import (
    AS_OF, ROOT, MICHEAL, CapabilityFixture, FixedPlanGenerator, _selection,
)


MEMBER = "Micheál Martin"
QD04 = f"How many distinct Dáil terms does the Member record for {MEMBER} link to?"


def proposal(member=MEMBER, exclusions=()):
    return {"countTarget": "DailTerm", "member": member,
            "scope": "member_service" if member else "houses_catalogue",
            "answer": "count_distinct", "exclusions": list(exclusions)}


def validate(question, parameters=None):
    return validate_composable_plan_draft(
        _selection("term_count", proposal() if parameters is None else parameters), question=question,
    )[0]


def test_qd04_typed_handoff_lowers_to_the_existing_operation():
    assert validate(QD04) == {
        "family": "capability_selection", "capability": "term_count", "parameters": {"member": MEMBER},
    }
    assert validate(QD04, {"member": MEMBER}) == validate(QD04)


# Metamorphic composition across independently meaningful slots, not an
# accumulating list of approved questions. Test every combination and the
# target substitution law below, including a target wording absent from the
# shared requested_measures lexicon.
@pytest.mark.parametrize(("preamble", "operator", "target", "owner", "relation"), tuple(itertools.product(
    ("", "Please give me ", "Could you report "),
    ("how many", "the number of", "a count of"),
    ("distinct Dáil terms", "different terms of the Dáil"),
    (f"{MEMBER}'s membership record", f"the Member record for {MEMBER}"),
    ("does {owner} link to", "appear in {owner}"),
)))
def test_semantic_slot_composition(preamble, operator, target, owner, relation):
    question = f"{preamble}{operator} {target} {relation.format(owner=owner)}?"
    assert validate(question)["parameters"] == {"member": MEMBER}


@pytest.mark.parametrize("suffix", (
    " as a Fianna Fáil TD", " after 2000", " on 1 March 2020", " in Dáil number 33",
    " for Cork South-Central", " while serving as Taoiseach", " except the 32nd Dáil",
    " excluding Seanad terms", " and list their start dates", " and show their exact IRIs",
    " and how many membership records", " and seats", " and Members", " only full terms",
    " that overlapped his Seanad service", " not linked to Brendan Howlin",
    " but only if the record is current", " with missing end dates", " / 2",
))
@pytest.mark.parametrize("base", (
    QD04.rstrip("?"), f"In how many distinct Dáil terms has {MEMBER} served",
))
def test_added_intent_cannot_be_lost_even_if_model_asserts_support(base, suffix):
    with pytest.raises(ValueError):
        validate(base + suffix + "?")


@pytest.mark.parametrize("question", (
    f"Which Dáil terms does the Member record for {MEMBER} link to?",
    f"How many membership records link {MEMBER} to Dáil terms?",
    f"How many Dáil terms link to the Member record for {MEMBER}?",
    f"How many Dáil terms does {MEMBER} serve the Member record for?",
    f"Served has {MEMBER} how many Dáil terms in?",
    f"How many Dáil terms has {MEMBER} and Brendan Howlin served in?",
    "How many Dáil terms are there?",
    "How many Dáil terms existed?",
    f"How many Dáil terms does the Member record for {MEMBER} not link to?",
    f"How many seats does the Member record for {MEMBER} link to?",
))
def test_direction_binding_count_target_and_scope_are_not_a_token_bag(question):
    with pytest.raises(ValueError):
        validate(question)


@pytest.mark.parametrize(("key", "value"), (
    ("countTarget", "DailMembership"), ("member", "Brendan Howlin"), ("member", None),
    ("scope", "houses_catalogue"), ("scope", "current_term"), ("answer", "entities"),
    ("exclusions", ["members"]), ("exclusions", ""), ("extra", True),
))
def test_model_semantic_claims_are_compared_not_trusted(key, value):
    with pytest.raises(ValueError):
        validate(QD04, {**proposal(), key: value})


@pytest.mark.parametrize(("phrase", "measure"), (
    ("rather than membership rows", "membership_records"),
    ("not seats", "seats"), ("instead of people", "members"),
))
def test_excluded_measure_is_explicit_and_cannot_hide_positive_requests(phrase, measure):
    question = QD04.rstrip("?") + ", " + phrase + "?"
    assert validate(question, proposal(exclusions=(measure,)))["parameters"] == {"member": MEMBER}
    with pytest.raises(ValueError):
        validate(question)  # model omission
    with pytest.raises(ValueError):
        validate(question.replace(", " + phrase, " and seats, " + phrase), proposal(exclusions=(measure,)))
    with pytest.raises(ValueError):
        validate(question.replace(", " + phrase, " after 2000, " + phrase), proposal(exclusions=(measure,)))


def test_explicit_catalogue_scope_has_same_canonical_operation():
    for question in (
        "How many distinct Dáil terms are recorded in the Houses catalogue?",
        "Please give me the number of terms of the Dáil in the Houses dataset.",
        "In the Houses graph, report the count of distinct Dáil terms.",
    ):
        assert validate(question, proposal(None)) == {
            "family": "capability_selection", "capability": "term_count", "parameters": {},
        }


def test_schema_inventory_and_analyser_agree_without_another_plan_format():
    schema = json.loads((ROOT / "poc/specs/composable-query-plan-draft.schema.json").read_text())
    # Responses strict JSON Schema rejects uniqueItems. maxItems=1 and the
    # independent exact-intent comparison already prohibit duplicates.
    assert schema["$defs"]["termCountIntent"]["properties"]["exclusions"]["maxItems"] == 1
    assert "uniqueItems" not in schema["$defs"]["termCountIntent"]["properties"]["exclusions"]
    Draft202012Validator(schema).validate(_selection("term_count", proposal()))
    assert analyse_term_count(QD04, member=MEMBER).proposal() == proposal()
    contract = json.loads((ROOT / "poc/specs/composable-query-plan-contract.json").read_text())
    entry = next(c for c in contract["semanticDispatch"]["capabilities"] if c["id"] == "term_count")
    assert entry["intentAdmission"]["draftDefinition"] in schema["$defs"]
    module, function = entry["intentAdmission"]["validator"].rsplit(".", 1)
    validator = getattr(importlib.import_module("poc.nlq." + module), function)
    assert validator(QD04, proposal()) == {"member": MEMBER}
    assert entry["handler"] == "stage_a" and entry["input"] == "member_or_house_total"


def ask(monkeypatch, question, parameters, fixture=None):
    from poc.nlq import app as app_module
    fixture = fixture or CapabilityFixture()
    generator = FixedPlanGenerator(_selection("term_count", parameters))
    monkeypatch.setenv("OIR_NLQ_AS_OF_DATE", AS_OF.isoformat())
    monkeypatch.setattr(app_module, "FusekiQueryClient", lambda *a, **kw: fixture)
    response = TestClient(app_module.create_app(
        repository_root=ROOT, semantic_plan_generator_factory=lambda: generator,
    )).post("/ask", data={"question": question, "mode": "phase2"})
    assert response.status_code == 200
    return response.text, fixture, generator


def test_integrated_ask_preserves_exact_operation_queries_and_qualifications(monkeypatch):
    legacy, legacy_fixture, _ = ask(monkeypatch, f"How many Dáil terms has {MEMBER} served in?", proposal())
    semantic, semantic_fixture, generator = ask(monkeypatch, QD04, proposal())
    assert generator.calls == [QD04]
    assert legacy_fixture.queries == semantic_fixture.queries
    for text in (legacy, semantic):
        assert "Distinct Dáil terms" in text
        assert "Counted distinct membership-linked HouseTerm IRIs" in text


@pytest.mark.parametrize("suffix", (" as a Labour TD", " after 2000", " and list their dates", " and count seats"))
def test_integrated_ask_never_queries_when_supported_draft_omits_condition(monkeypatch, suffix):
    text, fixture, _ = ask(monkeypatch, QD04.rstrip("?") + suffix + "?", proposal())
    assert not fixture.queries
    assert "Distinct Dáil terms</th>" not in text


def test_integrated_ask_duplicate_exact_names_remain_distinct_candidates(monkeypatch):
    from poc.nlq.results import QueryResult

    class Ambiguous(CapabilityFixture):
        def query(self, query):
            assert "SELECT DISTINCT ?member ?name" in query
            self.queries.append(query)
            return QueryResult("select", ("member", "name"), (
                (MICHEAL, MEMBER), (MICHEAL + "-other", MEMBER),
            ))

    text, fixture, _ = ask(monkeypatch, QD04, proposal(), Ambiguous())
    assert len(fixture.queries) == 1
    assert "Several distinct local Member identities match" in text
    assert MICHEAL in text and MICHEAL + "-other" in text


def test_integrated_ask_exact_name_cannot_be_accent_folded_or_guessed(monkeypatch):
    from poc.nlq.results import QueryResult

    class DifferentName(CapabilityFixture):
        def query(self, query):
            self.queries.append(query)
            return QueryResult("select", ("member", "name"), ((MICHEAL, "Micheal Martin"),))

    text, fixture, _ = ask(monkeypatch, QD04, proposal(), DifferentName())
    assert len(fixture.queries) == 2  # exact foaf:name, then exact source pId
    assert all("SELECT DISTINCT ?member ?name" in query for query in fixture.queries)
    assert "No local Member matches" in text
