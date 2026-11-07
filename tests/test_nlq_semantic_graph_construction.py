"""Acceptance for pure, IRI-free construction of existing semantic drafts."""

from __future__ import annotations

import copy
from datetime import date
import json
import re

import pytest
from jsonschema import Draft202012Validator

from poc.nlq.composable_plan import PlanError, validate_plan
from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft,
    complete_v2_plan,
    load_composable_draft_schema,
    validate_composable_plan_draft,
)
from poc.nlq.representation import representation_plan
from poc.nlq.semantic_graphs import (
    ANCHORED_SHARED_CONSTITUENCY_EDGES,
    CONSTITUENCY_REPRESENTATION_EDGES,
    SHARED_DAIL_TERMS_EDGES,
    build_anchored_shared_constituency_draft,
    build_constituency_representation_draft,
    build_shared_dail_terms_draft,
)


AS_OF = date(2026, 10, 28)
SCHEMA = Draft202012Validator(load_composable_draft_schema())

SHARED_QUESTION = "Which Dáil terms did Micheál Martin and Mary Lou McDonald both serve in?"
SHARED_OLD_IDS = {
    edge: relation_id for edge, relation_id in zip(
        SHARED_DAIL_TERMS_EDGES,
        ("a_membership", "a_term", "b_membership", "b_term"),
        strict=True,
    )
}

ANCHORED_LIST_QUESTION = "Who were the other TDs sharing the same constituency as Aoife Byrne in the 32nd Dáil?"
ANCHORED_COUNT_QUESTION = "How many other TDs shared the same constituency as Aoife Byrne in the 32nd Dáil?"
ANCHORED_OLD_IDS = {
    edge: relation_id for edge, relation_id in zip(
        ANCHORED_SHARED_CONSTITUENCY_EDGES,
        (
            "anchor-member-membership", "anchor-membership-term",
            "anchor-membership-constituency", "answer-member-membership",
            "answer-membership-term", "answer-membership-constituency",
            "constituency-term",
        ),
        strict=True,
    )
}


def _edge(relation: dict[str, str]) -> tuple[str, str, str]:
    return relation["fact"], relation["from"], relation["to"]


def _without_relation_ids(plan: dict) -> dict:
    result = copy.deepcopy(plan)
    for relation in result["relations"]:
        relation.pop("id")
    return result


def _with_legacy_ids(draft: dict, ids_by_edge: dict[tuple[str, str, str], str]) -> dict:
    result = copy.deepcopy(draft)
    for relation in result["relations"]:
        relation["id"] = ids_by_edge[_edge(relation)]
    return result


def _validated_final_plan(draft: dict, question: str) -> dict:
    SCHEMA.validate(draft)
    semantic_plan, unsupported = validate_composable_plan_draft(draft, question=question)
    assert unsupported is None
    return validate_plan(complete_v2_plan(semantic_plan, as_of=AS_OF))


def _assert_iri_free_complete_draft(
    draft: dict,
    expected_edges: tuple[tuple[str, str, str], ...],
) -> None:
    SCHEMA.validate(draft)
    assert len(draft["relations"]) == len(expected_edges)
    assert {_edge(relation) for relation in draft["relations"]} == set(expected_edges)
    assert len({_edge(relation) for relation in draft["relations"]}) == len(expected_edges)

    ids = [relation["id"] for relation in draft["relations"]]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", relation_id) for relation_id in ids)
    assert all(relation["id"] == "edge_" + "_".join(_edge(relation))
               for relation in draft["relations"])

    serialized = json.dumps(draft, ensure_ascii=False)
    assert '"iri"' not in serialized
    assert "https://data.oireachtas.ie/" not in serialized


def test_shared_dail_terms_constructor_matches_the_existing_validated_graph():
    draft = build_shared_dail_terms_draft("Micheál Martin", "Mary Lou McDonald")
    repeated = build_shared_dail_terms_draft("Micheál Martin", "Mary Lou McDonald")

    _assert_iri_free_complete_draft(draft, SHARED_DAIL_TERMS_EDGES)
    assert draft == repeated
    assert set(draft["referents"]) == {
        "member_a", "membership_a", "member_b", "membership_b", "shared_term",
    }
    assert draft["referents"]["member_a"]["mention"] == "Micheál Martin"
    assert draft["referents"]["member_b"]["mention"] == "Mary Lou McDonald"

    generated_plan = _validated_final_plan(draft, SHARED_QUESTION)
    legacy_plan = _validated_final_plan(_with_legacy_ids(draft, SHARED_OLD_IDS), SHARED_QUESTION)
    assert _without_relation_ids(generated_plan) == _without_relation_ids(legacy_plan)


def test_anchored_shared_constituency_list_and_count_use_the_same_seven_edge_selection():
    selector = {"kind": "termNumber", "number": 32}
    listed = build_anchored_shared_constituency_draft("Aoife Byrne", selector)
    counted = build_anchored_shared_constituency_draft("Aoife Byrne", selector, count=True)

    _assert_iri_free_complete_draft(listed, ANCHORED_SHARED_CONSTITUENCY_EDGES)
    _assert_iri_free_complete_draft(counted, ANCHORED_SHARED_CONSTITUENCY_EDGES)
    assert listed["referents"]["term"]["selector"] == selector
    assert set(listed["referents"]) == {
        "member", "membership", "term", "constituency", "anchorMember", "anchorMembership",
    }
    assert not {"episode", "party", "affiliation", "holding", "office"} & set(listed["referents"])

    listed_plan = _validated_final_plan(listed, ANCHORED_LIST_QUESTION)
    counted_plan = _validated_final_plan(counted, ANCHORED_COUNT_QUESTION)
    assert listed_plan["referents"] == counted_plan["referents"]
    assert listed_plan["relations"] == counted_plan["relations"]
    assert listed_plan["constraints"] == counted_plan["constraints"] == []
    assert listed_plan["answer"] == {
        "kind": "entities", "referent": "member", "distinctBy": "identity",
        "display": ["name"], "details": [], "preserveEvidence": False,
    }
    assert counted_plan["answer"] == {
        "kind": "count", "referent": "member", "distinctBy": "identity",
    }

    legacy_plan = _validated_final_plan(_with_legacy_ids(listed, ANCHORED_OLD_IDS), ANCHORED_LIST_QUESTION)
    assert _without_relation_ids(listed_plan) == _without_relation_ids(legacy_plan)


@pytest.mark.parametrize(
    ("selector", "question"),
    [
        ("currentTerm", "Which constituency does Bertie Ahern represent?"),
        ("latestRecorded", "Which constituency did Bertie Ahern represent in his latest recorded Dáil term?"),
        (None, "What constituencies did Bertie Ahern represent?"),
    ],
)
def test_named_member_representation_reuses_the_existing_four_edge_evidence_graph(selector, question):
    draft = build_constituency_representation_draft("Bertie Ahern", selector)
    repeated = build_constituency_representation_draft("Bertie Ahern", selector)

    _assert_iri_free_complete_draft(draft, CONSTITUENCY_REPRESENTATION_EDGES)
    assert draft == repeated
    assert draft["referents"]["term"]["selector"] == selector
    assert draft["answer"] == {
        "kind": "entities", "referent": "constituency", "distinctBy": "identity",
        "display": ["label"], "details": [{"referent": "term", "display": ["label"]}],
        "preserveEvidence": True,
    }

    generated_plan = _validated_final_plan(draft, question)
    legacy_ids = {edge: edge[0] for edge in CONSTITUENCY_REPRESENTATION_EDGES}
    legacy_plan = _validated_final_plan(_with_legacy_ids(draft, legacy_ids), question)
    assert _without_relation_ids(generated_plan) == _without_relation_ids(legacy_plan)

    canonical = validate_plan(representation_plan(
        as_of=AS_OF,
        member="Bertie Ahern",
        current=selector == "currentTerm",
        latest_recorded=selector == "latestRecorded",
    ))
    assert _without_relation_ids(generated_plan) == _without_relation_ids(canonical)


def test_previous_dail_selector_is_preserved_without_changing_the_seven_edge_shape():
    question = "How many other TDs were in the same constituency as Aoife Byrne during the last Dáil?"
    draft = build_anchored_shared_constituency_draft(
        "Aoife Byrne", {"kind": "previousTerm"}, count=True,
    )

    _assert_iri_free_complete_draft(draft, ANCHORED_SHARED_CONSTITUENCY_EDGES)
    plan = _validated_final_plan(draft, question)
    assert plan["referents"]["term"]["selector"] == {"kind": "previousTerm", "house": "Dail"}
    assert plan["constraints"] == []


@pytest.mark.parametrize("constructor_and_args", [
    (build_shared_dail_terms_draft, ("", "Mary Lou McDonald")),
    (build_shared_dail_terms_draft, ("Micheál Martin", "micheál martin")),
    (build_anchored_shared_constituency_draft, ("  ", {"kind": "termNumber", "number": 32})),
    (build_anchored_shared_constituency_draft, ("Aoife Byrne", {"kind": "termNumber", "number": True})),
    (build_anchored_shared_constituency_draft, ("Aoife Byrne", {"kind": "currentTerm"})),
    (build_constituency_representation_draft, ("", "currentTerm")),
    (build_constituency_representation_draft, ("Bertie Ahern", "latest")),
    (build_constituency_representation_draft, ("Bertie Ahern", {"kind": "currentTerm"})),
])
def test_constructors_reject_invalid_semantic_slots(constructor_and_args):
    constructor, args = constructor_and_args
    with pytest.raises(ValueError):
        constructor(*args)


def test_anchored_constructor_rejects_non_boolean_count_projection():
    with pytest.raises(ValueError):
        build_anchored_shared_constituency_draft(
            "Aoife Byrne", {"kind": "termNumber", "number": 32}, count=1,
        )


def test_legacy_missing_edge_and_duplicate_relation_id_rejections_are_unchanged():
    legacy = _with_legacy_ids(
        build_shared_dail_terms_draft("Micheál Martin", "Mary Lou McDonald"),
        SHARED_OLD_IDS,
    )

    missing_edge = copy.deepcopy(legacy)
    missing_edge["relations"].pop()
    with pytest.raises(InvalidComposableDraft):
        validate_composable_plan_draft(missing_edge, question=SHARED_QUESTION)

    duplicate_id = copy.deepcopy(legacy)
    duplicate_id["relations"][1]["id"] = duplicate_id["relations"][0]["id"]
    with pytest.raises(InvalidComposableDraft):
        validate_composable_plan_draft(duplicate_id, question=SHARED_QUESTION)

    valid_legacy_plan = _validated_final_plan(legacy, SHARED_QUESTION)
    missing_final_edge = copy.deepcopy(valid_legacy_plan)
    missing_final_edge["relations"].pop()
    with pytest.raises(PlanError):
        validate_plan(missing_final_edge)

    duplicate_final_id = copy.deepcopy(valid_legacy_plan)
    duplicate_final_id["relations"][1]["id"] = duplicate_final_id["relations"][0]["id"]
    with pytest.raises(PlanError):
        validate_plan(duplicate_final_id)
