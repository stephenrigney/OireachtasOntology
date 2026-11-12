"""Design falsification, not application acceptance or a hidden intent oracle.

The expected missing conditions below are TEST INPUTS/ORACLES ONLY. No mapping
from original language to these atoms is available to the diagnostic gate.
All proposals are injected by this test's author; no LLM generation is claimed.
"""
import copy
from dataclasses import replace

import pytest

from tools.diagnose_retrieval_satisfaction import (
    Atom, CAREER, ROOT, SPONSOR, Replay, accept_claim, accept_prose, diagnose,
    ledger_only_answered, load_bundle, original_disposition, project, replay,
    supporting_relevance,
)
from poc.nlq.vocabulary import supported_predicates


@pytest.fixture(scope="module")
def evidence():
    b = load_bundle()
    p = supported_predicates(ROOT / "ontology")
    records = {r["question"]: r for r in b["live"] if r["controlledProposal"] is None}
    questions = [SPONSOR, CAREER, "Tell me about Bill 11 from 2020",
                 "How many committees was Mary Lou McDonald a member of?",
                 "How many Bills did Malcolm Byrne sponsor that were published in 2025?"]
    result = {}
    for question in questions:
        outcome = replay(records[question], b["reportingDate"], p)
        result[question] = (outcome, project(outcome, question, "retained-observation-2026-11-12"))
    return result


# Indexes identify the EXACT frozen controls. The diagnostic functions do not
# read this oracle, these predicates, or proposalCompleteForQuestion labels.
MISSING = [
    (2, "recorded_opposition"),
    (3, "housing_subject_qualification"),
    (4, "enactment"),
    (5, "senator_period_sponsorship"),
    (6, "primary_filtered_sponsorship_list"),
    (7, "sponsorship_before_2024"),
    (8, "progress_and_outcomes"),
    (10, "other_parliamentary_roles"),
    (11, "representation_during_ministerial_service"),
    (12, "representation_before_2020"),
]


@pytest.mark.parametrize("index,missing_predicate", MISSING)
def test_known_conditions_block_if_present_but_omitted_ledger_falsifies_design(evidence, index, missing_predicate):
    saved = load_bundle()["offline"][index]
    question = SPONSOR if saved["draft"]["family"] == "member_bill_sponsorship" else CAREER
    outcome, facts = evidence[question]
    assert outcome.interaction == "answer"  # own narrower query can execute
    listed = facts[0].atom
    missing = Atom(missing_predicate, listed.subject, (), listed.scope)
    # Useful but INSUFFICIENT demonstration: the ledger correctly names a gap.
    assert not ledger_only_answered([listed, missing], facts)
    assert not accept_claim(missing, question, facts)  # existing citation is not proof
    # Actual omission challenge: every proposed condition passes, but intent lost.
    assert ledger_only_answered([listed], facts)
    held = original_disposition(saved["question"], [listed], facts)
    assert held["original"] == saved["question"]
    assert not held["answered"]
    assert held["unresolved"] == ["original_intent_not_independently_bound"]
    # We have NOT independently discovered/named the missing condition here.
    assert missing_predicate not in held["unresolved"]


def test_replay_frozen_parent_guards_and_supporting_semantics():
    result = diagnose()
    assert result["ordinaryOperationsReplayed"] == 26
    assert result["queryResponsesReplayed"] == 35
    assert result["modelCalls"] == result["networkCalls"] == result["datasetMutations"] == 0
    # 11 admitted parents (3 complete + 8 incomplete); both dates still refused.
    assert sum(c["frozenParentAdmitted"] for c in result["controls"]) == 11
    assert all(c["supportingCompilerOutcome"] == "answer" for c in result["controls"])
    assert all(c["ledgerOnlyAnswered"] for c in result["controls"])
    assert not any(c["guarded"]["answered"] for c in result["controls"])
    assert result["verdict"] == "NO-GO" and not result["designValidated"]


def test_positive_typed_requirement_and_ordinary_language_false_negative(evidence):
    outcome, facts = evidence[SPONSOR]
    requirement = [facts[0].atom]  # independently supplied typed input, NOT NL binding
    assert outcome.interaction == "answer"
    assert ledger_only_answered(requirement, facts)  # no confirmation step needed
    assert accept_claim(facts[1].atom, SPONSOR, facts)
    # Cannot count the typed-input positive as a complete ordinary-language pass.
    assert not original_disposition(SPONSOR, requirement, facts)["answered"]


@pytest.mark.parametrize("change", [
    {"predicate": "recorded_opposition"}, {"predicate": "housing_sponsor"},
    {"predicate": "enacted_bill"}, {"subject": "another-member"},
    {"objects": ("another-bill",)}, {"scope": "before-2024"},
    {"scope": "during-senator-service"},
])
def test_query_cannot_become_stronger_typed_claim(evidence, change):
    _, facts = evidence[SPONSOR]
    sponsor = next(f.atom for f in facts if f.atom.predicate == "recorded_sponsor")
    assert accept_claim(sponsor, SPONSOR, facts)
    assert not accept_claim(replace(sponsor, **change), SPONSOR, facts)


def test_valid_atom_plus_stronger_prose_or_wrong_citation_is_not_accepted(evidence):
    _, facts = evidence[SPONSOR]
    sponsor = facts[1].atom
    assert not accept_claim(sponsor, "invented-evidence-id", facts)
    assert not accept_prose("These are all his housing Bills and they became law.", sponsor, SPONSOR, facts)
    # The fail-closed prose gate also withholds valid free prose: not an authoring solution.
    assert not accept_prose("The records link this Bill to his sponsorship.", sponsor, SPONSOR, facts)


def test_primary_classification_is_available_but_not_inherited_by_every_bill(evidence):
    _, facts = evidence[SPONSOR]
    statuses = [f for f in facts if f.atom.predicate == "recorded_primary_status"]
    assert any(f.atom.objects[-1] == "Primary" for f in statuses)
    supporting = next(f for f in statuses if f.atom.objects[-1] == "Supporting")
    stronger = replace(supporting.atom, objects=(supporting.atom.objects[0], "Primary"))
    assert accept_claim(supporting.atom, SPONSOR, facts)
    assert not accept_claim(stronger, SPONSOR, facts)


def test_r1_separate_bill_lookup_not_a_final_outcome(evidence):
    _, sponsors = evidence[SPONSOR]
    q = "Tell me about Bill 11 from 2020"
    _, bill = evidence[q]
    history = next(f for f in bill if f.atom.predicate == "recorded_bill_history")
    status = next(f for f in bill if f.atom.predicate == "recorded_bill_status")
    assert history.atom.subject in sponsors[0].atom.objects
    assert "Bill Lapsed Event: 2025-01-29" in history.atom.objects[0]
    assert "Committee Stage: 2025-03-27" in history.atom.objects[0]
    assert status.atom.objects == ("Current",)
    assert accept_claim(history.atom, q, bill)
    assert not accept_claim(history.atom, SPONSOR, sponsors)  # sponsorship did not establish progress
    assert not accept_claim(replace(status.atom, predicate="final_outcome"), q, bill)
    assert not accept_claim(replace(status.atom, predicate="enactment"), q, bill)


def test_r3_representation_is_not_officeholding_or_continuous_tenure(evidence):
    _, facts = evidence[CAREER]
    episodes = [f for f in facts if f.atom.predicate == "recorded_representation"]
    assert len({f.atom.objects[0] for f in episodes}) == 4  # exact term-specific identities
    assert len({f.atom.objects[1] for f in episodes}) == 4
    for fact in episodes:
        assert accept_claim(fact.atom, CAREER, facts)
        for relation in ("ministerial_office", "committee_role", "continuous_tenure"):
            assert not accept_claim(replace(fact.atom, predicate=relation), CAREER, facts)


@pytest.mark.parametrize("question", [
    "How many committees was Mary Lou McDonald a member of?",
    "How many Bills did Malcolm Byrne sponsor that were published in 2025?",
])
def test_missing_is_not_zero_or_a_weaker_date_measure(evidence, question):
    outcome, facts = evidence[question]
    assert outcome.interaction == "missing_or_unaccepted_evidence"
    assert facts == ()
    assert not ledger_only_answered([], facts)


def test_relevance_needs_a_typed_dependency_not_merely_shared_identity(evidence):
    _, facts = evidence[SPONSOR]
    assert supporting_relevance("sponsored_bills", "sponsorship")  # housing candidate retrieval
    assert not supporting_relevance("opposition", "sponsorship")
    assert not supporting_relevance("parliamentary_career", "sponsorship")
    assert supporting_relevance("parliamentary_career", "career_constituencies")
    bill = facts[0].atom.objects[0]
    assert supporting_relevance("sponsored_bill_lifecycle", "bill_lookup", accepted_bills=facts[0].atom.objects, bill=bill)
    assert not supporting_relevance("sponsored_bill_lifecycle", "bill_lookup", accepted_bills=facts[0].atom.objects, bill="unrelated-bill")
    # A lying model can still select sponsored_bills for the opposition brief.
    # This unit test therefore does NOT certify free-text relevance admission.


def test_additional_conjunction_omitted_even_when_existing_condition_supported(evidence):
    _, facts = evidence[SPONSOR]
    base = facts[0].atom
    original = "Which housing Bills did Malcolm Byrne sponsor before 2024?"
    full_test_ledger = [base, Atom("housing", base.subject, (), base.scope),
                        Atom("sponsorship_before_2024", base.subject, (), base.scope)]
    assert not ledger_only_answered(full_test_ledger, facts)
    assert ledger_only_answered([base], facts)
    assert not original_disposition(original, [base], facts)["answered"]


def test_replay_is_not_a_query_independent_canned_result():
    b = load_bundle()
    queries = next(r["queries"] for r in b["live"] if r["question"] == SPONSOR)
    with pytest.raises(ValueError, match="mismatch"):
        Replay(queries).query("SELECT * WHERE { ?s ?p ?o }")
    corrupted = copy.deepcopy(queries)
    corrupted[0]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="mismatch"):
        Replay(corrupted).query(corrupted[0]["sparql"])


def test_projection_does_not_accept_success_or_citation_without_accepted_result(evidence):
    outcome, _ = evidence[SPONSOR]
    assert project(replace(outcome, result=None), "existing-citation", "scope") == ()
    assert project(replace(outcome, status="execution_failure"), "existing-citation", "scope") == ()
