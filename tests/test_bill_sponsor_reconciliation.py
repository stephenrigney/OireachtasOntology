from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.bill_sponsor_reconciliation import (
    BillSponsorStore,
    extract_bill_sponsor_observations,
    generate_bill_sponsor_candidates,
    sponsor_input_fingerprint,
)
from oireachtas_etl.transforms.bill_sponsors import build_bill_sponsor_graph
from oireachtas_etl.transforms.bills import transform_bill
from oireachtas_etl.transforms.common import ELIDL, MEMBERS
from oireachtas_etl.validation.bill_sponsors import validate_bill_sponsor_graph


ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / "data/api_examples/bill.json").read_text(encoding="utf-8"))["results"][0]
BILL = SOURCE["bill"]["uri"]
PERSON = "https://data.oireachtas.ie/ie/oireachtas/member/id/Synthetic.Member.2000-01-01"
OFFICE = "https://data.oireachtas.ie/office/o-000001"
REVIEW_HASH = hashlib.sha256(b"synthetic bill sponsor review").hexdigest()


def copied_source() -> dict:
    return json.loads(json.dumps(SOURCE))


def registry(*, duplicate_role_alias: bool = False, reviewer_note: str = "synthetic") -> dict:
    offices = [{
        "key": "o-000001",
        "label_en": "Minister for Finance",
        "aliases": [{"language": "en", "label": "Minister for Finance"}],
        "office_type": "MinisterOfficeType",
        "unit_relationships": [],
        "reviewer_notes": reviewer_note,
        "evidence": ["tests/test_bill_sponsor_reconciliation.py#office-1"],
    }]
    if duplicate_role_alias:
        offices.append({
            "key": "o-000002",
            "label_en": "Another reviewed office",
            "aliases": [{"language": "en", "label": "Minister for Finance"}],
            "office_type": "MinisterOfficeType",
            "unit_relationships": [],
            "reviewer_notes": "synthetic second identity",
            "evidence": ["tests/test_bill_sponsor_reconciliation.py#office-2"],
        })
    return {"version": 1, "administrative_units": [], "offices": offices}


def accepted_holding(office: str = OFFICE, *, end: str | None = None) -> dict:
    return {
        "status": "accepted",
        "member_iri": PERSON,
        "holding_iri": PERSON + "#office-holding-" + "a" * 64,
        "office_iri": office,
        "date_range": {"start": "2000-01-01", "end": end},
    }


def source_person(wrapper: dict, person: str = PERSON) -> None:
    wrapper["bill"]["sponsors"][0]["sponsor"]["by"] = {"uri": person, "showAs": None}


def review_for(wrapper: dict, office_registry: dict, holdings: list[dict], *,
               office: str | None = OFFICE, holding: str | None = None,
               time_context: dict | None = None, status: str = "accepted") -> tuple[str, dict]:
    observation = extract_bill_sponsor_observations(wrapper)[0]
    fingerprint = sponsor_input_fingerprint(observation, office_registry, holdings, time_context)
    decision = {
        "status": status,
        "input_fingerprint": fingerprint,
        "evidence": ["test:reviewed-synthetic-evidence"],
        "reason": "Synthetic decision used only by a focused unit test.",
    }
    if status == "accepted":
        if office is not None:
            decision["office_iri"] = office
        if holding is not None:
            decision["holding_iri"] = holding
            decision["time_context"] = time_context
    return observation["observation_key"], decision


def test_unique_reviewed_role_builds_only_office_link_and_preserves_bill_core():
    wrapper, offices = copied_source(), registry()
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(wrapper, offices, [], {}, REVIEW_HASH, run_id="office-only")
    record = result["records"][0]
    assert record["status"] == "accepted"
    assert record["office_iri"] == OFFICE and record["holding_iri"] is None

    local_graph = build_bill_sponsor_graph(wrapper, result["records"], offices, [])
    participation = URIRef(record["participation_iri"])
    assert set(local_graph) == {(participation, MEMBERS.reconciledSponsorOffice, URIRef(OFFICE))}
    core = transform_bill(wrapper)
    assert participation in set(core.subjects(RDF.type, ELIDL.Participation))
    assert not any(predicate in {MEMBERS.reconciledSponsorOffice,
                                MEMBERS.reconciledSponsorHolding}
                   for _, predicate, _ in core)
    validate_bill_sponsor_graph(wrapper, local_graph, result["records"], offices, [])


def test_reviewed_person_and_selected_source_event_qualify_one_holding():
    wrapper, offices = copied_source(), registry()
    source_person(wrapper)
    holding = accepted_holding()
    context = extract_bill_sponsor_observations(wrapper)[0]["bill_time_contexts"][0]
    key, decision = review_for(wrapper, offices, [holding], holding=holding["holding_iri"],
                               time_context=context)

    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(wrapper, offices, [holding], {key: decision},
                                 REVIEW_HASH, run_id="person-time")
    record = result["records"][0]
    assert record["status"] == "accepted"
    assert record["time_context"] == context
    candidates = generate_bill_sponsor_candidates(
        extract_bill_sponsor_observations(wrapper)[0], offices, [holding], context)
    assert [candidate["holding_iri"] for candidate in candidates["holding_candidates"]] == [holding["holding_iri"]]

    graph = build_bill_sponsor_graph(wrapper, result["records"], offices, [holding])
    participation = URIRef(record["participation_iri"])
    assert set(graph) == {
        (participation, MEMBERS.reconciledSponsorOffice, URIRef(OFFICE)),
        (participation, MEMBERS.reconciledSponsorHolding, URIRef(holding["holding_iri"])),
    }
    validate_bill_sponsor_graph(wrapper, graph, result["records"], offices, [holding])


def test_reviewed_holding_that_is_no_longer_applicable_is_quarantined_not_published():
    wrapper, offices = copied_source(), registry()
    source_person(wrapper)
    context = extract_bill_sponsor_observations(wrapper)[0]["bill_time_contexts"][0]
    corrected = accepted_holding(end="2020-01-01")

    with BillSponsorStore(":memory:") as store:
        # A current fingerprint alone cannot override a holding that no longer
        # covers the selected Bill event date.
        corrected_key, corrected_decision = review_for(
            wrapper, offices, [corrected], holding=corrected["holding_iri"],
            time_context=context)
        result = store.reconcile(wrapper, offices, [corrected],
                                 {corrected_key: corrected_decision}, REVIEW_HASH)
    record = result["records"][0]
    assert record["status"] == "review_required"
    assert record["holding_iri"] is None
    assert any(item["kind"] == "reviewed-holding-not-currently-person-time-qualified"
               for item in record["conflicts"])
    graph = build_bill_sponsor_graph(wrapper, result["records"], offices, [corrected])
    validate_bill_sponsor_graph(wrapper, graph, result["records"], offices, [corrected])


def test_role_only_or_unmatched_role_never_invents_person_or_holding():
    wrapper, offices = copied_source(), registry()
    source_person(wrapper)
    holding = accepted_holding()
    observation = extract_bill_sponsor_observations(wrapper)[0]
    assert generate_bill_sponsor_candidates(observation, offices, [holding])["holding_candidates"] == []
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(wrapper, offices, [holding], {}, REVIEW_HASH)
    assert result["records"][0]["status"] == "accepted"
    assert result["records"][0]["holding_iri"] is None

    wrapper["bill"]["sponsors"][0]["sponsor"]["as"]["showAs"] = "Unreviewed role wording"
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(wrapper, offices, [holding], {}, REVIEW_HASH)
    assert result["records"][0]["status"] == "unresolved"
    assert not result["records"][0]["office_iri"]
    graph = build_bill_sponsor_graph(wrapper, result["records"], offices, [holding])
    assert len(graph) == 0
    validate_bill_sponsor_graph(wrapper, graph, result["records"], offices, [holding])


@pytest.mark.parametrize("status", ["rejected", "unresolved"])
def test_explicit_nonaccepted_decisions_create_no_links(status):
    wrapper, offices = copied_source(), registry(duplicate_role_alias=True)
    key, decision = review_for(wrapper, offices, [], status=status)
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(wrapper, offices, [], {key: decision}, REVIEW_HASH)
    assert result["records"][0]["status"] == status
    assert result["records"][0]["office_iri"] is None
    graph = build_bill_sponsor_graph(wrapper, result["records"], offices, [])
    assert len(graph) == 0
    validate_bill_sponsor_graph(wrapper, graph, result["records"], offices, [])


def test_ambiguous_role_requires_review_and_manual_office_decision_is_fingerprint_bound():
    wrapper, offices = copied_source(), registry(duplicate_role_alias=True)
    with BillSponsorStore(":memory:") as store:
        first = store.reconcile(wrapper, offices, [], {}, REVIEW_HASH, run_id="ambiguous")
        record = first["records"][0]
        assert record["status"] == "review_required"
        key, decision = review_for(wrapper, offices, [], office="https://data.oireachtas.ie/office/o-000001")
        reviewed = store.reconcile(wrapper, offices, [], {key: decision}, REVIEW_HASH,
                                   run_id="reviewed")
        assert reviewed["records"][0]["status"] == "accepted"
        graph = build_bill_sponsor_graph(wrapper, reviewed["records"], offices, [])
        validate_bill_sponsor_graph(wrapper, graph, reviewed["records"], offices, [])


def test_removing_a_reviewed_decision_does_not_fall_back_to_automatic_acceptance():
    wrapper, offices = copied_source(), registry()
    key, decision = review_for(wrapper, offices, [])
    with BillSponsorStore(":memory:") as store:
        accepted = store.reconcile(wrapper, offices, [], {key: decision}, REVIEW_HASH,
                                  run_id="accepted-review")
        assert accepted["records"][0]["status"] == "accepted"
        removed = store.reconcile(wrapper, offices, [], {}, REVIEW_HASH,
                                  run_id="removed-review")
        assert removed["records"][0]["status"] == "review_required"
        retried = store.reconcile(wrapper, offices, [], {}, REVIEW_HASH,
                                  run_id="removed-review-retry")
        assert retried["records"][0]["status"] == "review_required"


def test_source_registry_and_relevant_holding_changes_invalidate_prior_resolution():
    wrapper, offices = copied_source(), registry()
    source_person(wrapper)
    original_holding = accepted_holding()
    with BillSponsorStore(":memory:") as store:
        first = store.reconcile(wrapper, offices, [original_holding], {}, REVIEW_HASH,
                                run_id="initial")
        assert first["records"][0]["status"] == "accepted"
        same = store.reconcile(wrapper, offices, [original_holding], {}, REVIEW_HASH,
                               run_id="same")
        assert same["records"][0]["status"] == "accepted"

        changed_holding = accepted_holding(end="2025-01-01")
        changed = store.reconcile(wrapper, offices, [changed_holding], {}, REVIEW_HASH,
                                  run_id="holding-change")
        assert changed["records"][0]["status"] == "review_required"
        assert changed["records"][0]["office_iri"] is None

        changed_registry = registry(reviewer_note="reviewed registry change")
        changed_again = store.reconcile(wrapper, changed_registry, [changed_holding], {},
                                        REVIEW_HASH, run_id="registry-change")
        assert changed_again["records"][0]["status"] == "review_required"

        changed_source = copied_source()
        source_person(changed_source)
        changed_source["bill"]["sponsors"][0]["sponsor"]["as"]["showAs"] = "Minister for Another Matter"
        changed_source_result = store.reconcile(changed_source, changed_registry,
                                                [changed_holding], {}, REVIEW_HASH,
                                                run_id="source-change")
        current = next(item for item in changed_source_result["records"]
                       if item["source_presence"] == "present")
        assert current["status"] == "review_required"
        repeated = store.reconcile(changed_source, changed_registry,
                                   [changed_holding], {}, REVIEW_HASH,
                                   run_id="source-change-retry")
        current_retry = next(item for item in repeated["records"]
                             if item["source_presence"] == "present")
        assert current_retry["status"] == "review_required"


def test_stale_time_context_is_quarantined_and_participation_key_ignores_array_position():
    wrapper, offices = copied_source(), registry()
    source_person(wrapper)
    holding = accepted_holding()
    observations = extract_bill_sponsor_observations(wrapper)
    first = observations[0]
    first_stage = wrapper["bill"]["stages"][0]["event"]
    context = {"event_iri": first_stage["uri"],
               "date": first_stage["dates"][0]["date"]}
    key, decision = review_for(wrapper, offices, [holding], holding=holding["holding_iri"],
                               time_context=context)
    with BillSponsorStore(":memory:") as store:
        accepted = store.reconcile(wrapper, offices, [holding], {key: decision}, REVIEW_HASH,
                                  run_id="accepted")
        assert accepted["records"][0]["status"] == "accepted"

        stale_source = copied_source()
        source_person(stale_source)
        for source_date in stale_source["bill"]["stages"][0]["event"]["dates"]:
            source_date["date"] = "1900-01-01"
        stale = store.reconcile(stale_source, offices, [holding], {key: decision},
                                REVIEW_HASH, run_id="stale-context")
        assert stale["records"][0]["status"] == "review_required"
        assert any(item["kind"] == "review-time-context-no-longer-in-current-bill"
                   for item in stale["records"][0]["conflicts"])

    two = copied_source()
    two["bill"]["sponsors"].append(copy.deepcopy(two["bill"]["sponsors"][0]))
    second_sponsor = copy.deepcopy(two["bill"]["sponsors"][0])
    second_sponsor["sponsor"]["as"]["showAs"] = "A separately identified role"
    second_sponsor["sponsor"]["isPrimary"] = False
    two["bill"]["sponsors"].append(second_sponsor)
    original_keys = {item["observation_key"] for item in extract_bill_sponsor_observations(two)}
    two["bill"]["sponsors"].reverse()
    reordered_keys = {item["observation_key"] for item in extract_bill_sponsor_observations(two)}
    assert len(original_keys) == 2
    assert original_keys == reordered_keys


def test_validator_rejects_nonlocal_or_stale_graph_content():
    wrapper, offices = copied_source(), registry()
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(wrapper, offices, [], {}, REVIEW_HASH)
    graph = build_bill_sponsor_graph(wrapper, result["records"], offices, [])
    graph.add((URIRef(BILL), URIRef("https://example.test/not-owned"), Literal("leak")))
    with pytest.raises(ValueError, match="predicates outside"):
        validate_bill_sponsor_graph(wrapper, graph, result["records"], offices, [])

    broken = Graph()
    broken.add((URIRef("https://data.oireachtas.ie/ie/oireachtas/bill/2025/60#stale"),
                MEMBERS.reconciledSponsorOffice, URIRef(OFFICE)))
    with pytest.raises(ValueError, match="source-to-RDF correspondence"):
        validate_bill_sponsor_graph(wrapper, broken, result["records"], offices, [])
