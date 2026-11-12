"""Frozen disclosed development experiment only; no withheld input is accessed."""

from copy import deepcopy
from pathlib import Path

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from poc.nlq.experimental_composition import (
    Budget, Evidence, Fact, Identity, NLQError, SemanticError, Witness,
    admit, bind, execute, graph, iri, parse_semantics, relationship_lookup,
)
from tools.nlq_composition_replay import PUBLIC, Replay, assert_provenance, evaluate, load_json, patch_semantic


DEVELOPMENT = PUBLIC / "development"
INPUTS = load_json(DEVELOPMENT / "inputs.json")["cases"]
CONTROLS = load_json(DEVELOPMENT / "controls.json")["controls"]


@pytest.fixture(scope="module")
def scored():
    return evaluate()


@pytest.mark.parametrize("case", ["R+P", "K+P"])
def test_frozen_development_positive(scored, case):
    report = scored["baselines"][case]
    assert report["outcome"] == "pass", report.get("assertions")
    assert len(report["ledger"]) == 4
    assert [r["preTransformRows"] for r in report["ledger"]] == (
        [65, 1, 5, 14] if case == "R+P" else [65, 6, 15, 26])
    assert all(r["coverageProof"]["allRequiredSubjectsAndPredicatesCovered"] for r in report["ledger"])
    assert report["intermediate"]["joinWitnessTuples"] == (1 if case == "R+P" else 4)


@pytest.mark.parametrize("control_id", [c["id"] for c in CONTROLS])
def test_every_frozen_development_control(scored, control_id):
    report = next(r for r in scored["controls"] if r["id"] == control_id)
    assert report["outcome"] == "pass", report.get("assertionFailure", report.get("error"))


def test_summary_is_conjunctive(scored):
    assert scored["summary"] == {"positivesPassed": 2, "controlsPassed": 111, "controlsTotal": 111}


def test_projection_cannot_rewrite_primary_witness_metadata(scored):
    report = deepcopy(scored["baselines"]["R+P"])
    report["answer"]["witnesses"][0][0]["intervals"][0]["start"]["value"] = "1900-01-01T00:00:00"
    with pytest.raises(AssertionError, match="Projection changed"):
        assert_provenance(report, Replay(DEVELOPMENT))


def test_only_inclusive_boundary_controls_use_counter_only_scoring(scored):
    for report in scored["controls"]:
        control = next(c for c in CONTROLS if c["id"] == report["id"])
        if control["layer"] == "budget-boundary":
            assert report["counterLevel"] is True
        elif control.get("retrievalOverride"):
            assert not report.get("counterLevel", False)
            assert report["faultInjection"]["executedCandidate"] is True
            if "nine-selects" in report["id"] or "page-cap" in report["id"]:
                assert report["faultInjection"]["attemptedRequests"] == 9
                assert len(report["ledger"]) == 8
            if "101-witnesses" in report["id"]:
                assert report["faultInjection"]["retainedWitnessTuples"] == 101


@pytest.mark.parametrize("case", INPUTS)
def test_uncovered_anchor_is_nonanswer_not_zero(case):
    spec = deepcopy(INPUTS[case])
    selection = spec["requiredSelections"][0]
    parameter = "constituency" if case == "R+P" else "committee"
    selection[parameter] += "-outside-frozen-scope"
    report = execute(spec, spec, Replay(DEVELOPMENT))
    assert report["status"] == "nonanswer"
    assert "Uncovered" in report["error"]
    assert "answer" not in report


def test_uncovered_required_subject_fails_even_if_optional_fact_is_absent():
    replay = Replay(DEVELOPMENT)
    selection = INPUTS["R+P"]["requiredSelections"][0]
    member = load_json(DEVELOPMENT / "oracle.json")["R+P"]["expectedMembers"][0]
    replay.covered.remove(member)
    lookup = relationship_lookup(selection)
    with pytest.raises(NLQError, match="Uncovered required subject"):
        replay.select(lookup, lookup.query(), 0)


@pytest.mark.parametrize("case", INPUTS)
def test_reverse_anchor_scope_matches_its_frozen_completion_certificate(case):
    lookup = relationship_lookup(INPUTS[case]["requiredSelections"][0])
    assert lookup.patterns[0].g == "anchorGraph"


def test_enumerated_orphan_fails_whole_selection_not_partial_count():
    oracle = load_json(DEVELOPMENT / "oracle.json")
    nonqualifying = next(c for c in oracle["R+P"]["candidateDispositions"] if not c["qualifies"])
    member = URIRef(nonqualifying["member"])
    membership = URIRef(nonqualifying["representation"]["membership"])
    owner = URIRef(nonqualifying["memberGraph"])
    replay = Replay(DEVELOPMENT, {"removeQuads": [
        f"{member.n3()} {iri('members:hasMembersMembership').n3()} {membership.n3()} {owner.n3()} ."]})
    # Fresh in-memory adversarial edit only; no protected source fixture changes.
    spec = INPUTS["R+P"]
    report = execute(spec, spec, replay)
    assert report["status"] == "nonanswer" and "answer" not in report
    assert "reverse Member" in report["error"]


def test_ledger_charges_full_page_completion():
    # A complete page has exactly 100 valid duplicate rows. Eight pages consume
    # all eight requests; a ninth completion probe must fail before transport.
    from poc.nlq.experimental_composition import retrieve, term_lookup

    class FullPages:
        timeout = 15
        calls = 0

        def select(self, lookup, query, offset):
            self.calls += 1
            return {"columns": ["term"], "rows": [{"term": URIRef("https://data.oireachtas.ie/example")}] * 100,
                    "complete": True}

    transport, budget = FullPages(), Budget()
    with pytest.raises(NLQError, match="request/timeout budget"):
        retrieve(term_lookup(), transport, budget)
    assert transport.calls == len(budget.requests) == 8
    assert [r["offset"] for r in budget.requests] == list(range(0, 800, 100))


def test_exact_counter_ceilings():
    budget = Budget()
    query = "SELECT ?s WHERE { VALUES ?s { <https://data.oireachtas.ie/example> } } LIMIT 100"
    budget.structure(2, 2)
    for _ in range(8):
        budget.request(query, 20)
    budget.rows([{}] * 100)
    budget.witnesses([()] * 100)
    with pytest.raises(NLQError):
        budget.request(query, 20)
    with pytest.raises(NLQError):
        budget.rows([{}] * 101)
    with pytest.raises(NLQError):
        budget.witnesses([()] * 101)


def test_leaf_witnesses_cannot_exceed_budget_before_a_selective_join(monkeypatch):
    from poc.nlq import experimental_composition as kernel

    real = kernel.primitive

    def oversized(*args, **kwargs):
        all_, selected = real(*args, **kwargs)
        return [all_[0]] * 101, selected

    monkeypatch.setattr(kernel, "primitive", oversized)
    spec = INPUTS["R+P"]
    report = execute(spec, spec, Replay(DEVELOPMENT))
    assert report["status"] == "nonanswer" and "answer" not in report
    assert report["intermediate"]["R"]["validated"] == 101
    assert "Primitive intermediate" in report["error"]


def test_type_checks_are_asserted_not_inferred():
    resource = URIRef("https://data.oireachtas.ie/example")
    e = Evidence({Fact(resource, iri("rdf:type"), iri("members:OireachtasMembership"), graph("houses"))})
    with pytest.raises(NLQError, match="asserted type"):
        e.type(resource, "members:DailMembership", graph("houses"))


def test_explicitly_disjoint_membership_types_fail_closed():
    resource = URIRef("https://data.oireachtas.ie/example")
    e = Evidence({Fact(resource, iri("rdf:type"), iri("members:DailMembership"), graph("houses")),
                  Fact(resource, iri("rdf:type"), iri("members:SeanadMembership"), graph("houses"))})
    with pytest.raises(NLQError, match="disjoint"):
        e.type(resource, "members:DailMembership", graph("houses"))


def test_unbound_candidacy_anchor_is_structured_nonanswer():
    class BrokenTransport:
        timeout = 15

        def select(self, lookup, query, offset):
            return {"columns": ["term"], "rows": [{}], "complete": True}

    spec = INPUTS["R+P"]
    report = execute(spec, spec, BrokenTransport())
    assert report["status"] == "nonanswer" and "answer" not in report
    assert "anchor" in report["error"]


def test_conflicting_endpoint_cannot_be_canonicalised_away():
    resource = URIRef("https://data.oireachtas.ie/example")
    p = iri("members:StartDate")
    g = graph("houses")
    e = Evidence({Fact(resource, p, Literal("2026-11-10T00:00:00", datatype=XSD.dateTime), g),
                  Fact(resource, p, Literal("2026-11-11T00:00:00", datatype=XSD.dateTime), g)})
    with pytest.raises(NLQError, match="conflicting"):
        e.one(resource, "members:StartDate", g)


def test_binder_is_typed_exact_not_display_equality():
    member = Identity("Member", URIRef("https://data.oireachtas.ie/member/one"))
    pm1 = Identity("ParliamentaryMembership", URIRef("https://data.oireachtas.ie/pm/one"))
    pm2 = Identity("ParliamentaryMembership", URIRef("https://data.oireachtas.ie/pm/two"))
    first = Witness("R", (("Member", member), ("parliamentaryMembership", pm1)), (), ())
    second = Witness("P", (("Member", member), ("containingMembership", pm2)), (), ())
    assert len(bind([[first], [second]], [], Budget())) == 1
    assert bind([[first], [second]], [("R.parliamentaryMembership", "P.containingMembership")], Budget()) == []
    wrong_kind = Witness("P", (("Member", member), ("containingMembership", Identity("CommitteeMembership", pm1.value))), (), ())
    with pytest.raises(NLQError, match="Incompatible binding"):
        bind([[first], [wrong_kind]], [("R.parliamentaryMembership", "P.containingMembership")], Budget())


def test_all_independent_semantic_mutations_rejected_without_execution():
    for control in CONTROLS:
        if control["layer"] == "semantic-admission":
            original = INPUTS[control["case"]]
            candidate = patch_semantic(original, control["candidateSemanticPatches"])
            with pytest.raises(SemanticError):
                admit(original, candidate)


def test_shared_projection_does_not_admit_committee_counts():
    spec = deepcopy(INPUTS["K+P"])
    spec["answer"]["shape"] = "count"
    with pytest.raises(SemanticError):
        parse_semantics(spec)


def test_production_route_has_no_experimental_import():
    root = Path(__file__).resolve().parents[1] / "poc/nlq"
    for name in ("app.py", "pipeline.py", "plan_pipeline.py", "composable_plan.py"):
        path = root / name
        assert path.is_file(), f"Missing production entrypoint: {path}"
        assert "experimental_composition" not in path.read_text()
