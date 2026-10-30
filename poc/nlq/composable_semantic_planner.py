"""Strict semantic interpretation for the bounded composable v2 slice.

The model proposes only v2 referents, reviewed relation IDs, and an answer
role. Local validation owns relation authority, identity resolution, graph
ownership, SPARQL generation, and execution.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from .config import DEFAULT_LLM_BASE_URL, DEFAULT_LLM_MODEL
from .structured_planner import (
    ResponsesPlanGenerator,
    _label_position,
    _reject_model_ir_is,
    parse_draft_json,
)


_ROOT = Path(__file__).resolve().parents[1]
DRAFT_SCHEMA_PATH = _ROOT / "specs" / "composable-query-plan-draft.schema.json"
_PLAN_CONTRACT_PATH = _ROOT / "specs" / "composable-query-plan-contract.json"
_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class InvalidComposableDraft(ValueError):
    """A model proposal is incomplete, malformed, or internally inconsistent."""


class InvalidComposableOutput(ValueError):
    """The planner did not return one parseable strict-JSON document."""


class UnsupportedComposableRequest(ValueError):
    """The requested semantics are outside the reviewed v2 slice."""


def _plan_contract() -> dict[str, Any]:
    return json.loads(_PLAN_CONTRACT_PATH.read_text(encoding="utf-8"))


def load_composable_draft_schema() -> dict[str, Any]:
    return json.loads(DRAFT_SCHEMA_PATH.read_text(encoding="utf-8"))


def build_composable_planner_instructions() -> str:
    """Render planner context from the existing v2 semantic contract."""
    contract = _plan_contract()
    family = next(
        item for item in contract["questionFamilies"]
        if item["id"] == "shared_dail_terms"
    )
    relations = {item["id"]: item for item in contract["relations"]}
    relation_guidance = "\n".join(
        f"- {fact}: {relations[fact]['subjectType']} to {relations[fact]['objectType']}"
        for fact in ("member_has_membership", "membership_in_term")
    )
    return f"""Interpret one user question as a semantic proposal for composable query plan v2.

Scope: {family['semantics']}

Use the existing semantic relationship identifiers below; these are proposals, not authority decisions:
{relation_guidance}

For a supported request, provide the fixed referent object keys member_a, membership_a, member_b, membership_b, and shared_term. The Member entries use exact user-supplied labels; the other entries have null mentions. Provide the complete Member → DailMembership → shared DailTerm path for each Member. The shared DailTerm referent expresses intersection by RDF identity. Do not merge the Member referents even if labels look alike. The only supported answer is the distinct DailTerm identity set.

If the question asks for a different relationship, extra filter, temporal restriction, a different answer, or anything outside this exact composition, return supported=false with a concise unsupportedReason, null referents, empty relations, and null answer. Do not simplify an unsupported request to this path.

Semantic interpretation only. Never output SPARQL, predicates, graph names, variables, endpoints, URLs, IRIs, candidates, or resolution decisions. Do not decide whether a mapping is authoritative; local code checks all proposed relation IDs against the reviewed v2 and query-schema contracts. Do not add assumptions about source completeness.

Return only the JSON object required by the strict composable-plan-v2 draft schema. All schema fields are required; unsupportedReason and answer are null when not applicable."""


def create_composable_plan_generator() -> ResponsesPlanGenerator:
    """Create the existing one-call Responses transport for a v2 draft schema."""
    return ResponsesPlanGenerator(
        os.getenv("NLQ_LLM_API_KEY", ""),
        os.getenv("NLQ_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        os.getenv("NLQ_LLM_MODEL", DEFAULT_LLM_MODEL),
        output_schema=load_composable_draft_schema(),
        schema_name="composable_query_plan_v2_draft",
        instructions=build_composable_planner_instructions(),
    )


def _identifier(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise InvalidComposableDraft(f"{where} must be a semantic identifier.")
    return value


def validate_composable_plan_draft(
    value: Any,
    *,
    question: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate a model proposal and return a final-envelope-ready v2 plan.

    The supported projection is intentionally exact. This is what prevents a
    missing participant, relationship edge, or shared term identity from being
    silently simplified into a weaker query.
    """
    try:
        _reject_model_ir_is(value)
    except ValueError as error:
        raise InvalidComposableDraft(str(error)) from error

    required = {
        "version", "supported", "unsupportedReason", "intent",
        "referents", "relations", "answer",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise InvalidComposableDraft(
            "The composable v2 proposal must contain exactly version, support state, intent, referents, relations, and answer."
        )
    if type(value["version"]) is not int or value["version"] != 2:
        raise InvalidComposableDraft("The semantic proposal must use composable plan version 2.")
    if not isinstance(value["intent"], str) or not value["intent"].strip():
        raise InvalidComposableDraft("The semantic proposal requires a non-empty interpretation.")
    if type(value["supported"]) is not bool:
        raise InvalidComposableDraft("The semantic support state must be Boolean.")
    if not isinstance(value["relations"], list):
        raise InvalidComposableDraft("Relations must be an array.")

    if value["supported"] is False:
        reason = value["unsupportedReason"]
        if (not isinstance(reason, str) or not reason.strip()
                or value["referents"] is not None or value["relations"] or value["answer"] is not None):
            raise InvalidComposableDraft(
                "An unsupported proposal must provide a reason and no executable semantic plan."
            )
        return None, reason.strip()
    if value["unsupportedReason"] is not None:
        raise InvalidComposableDraft("A supported proposal cannot also carry an unsupported reason.")

    referent_roles = {
        "member_a": "Member",
        "membership_a": "DailMembership",
        "member_b": "Member",
        "membership_b": "DailMembership",
        "shared_term": "DailTerm",
    }
    if not isinstance(value["referents"], dict) or set(value["referents"]) != set(referent_roles):
        raise InvalidComposableDraft(
            "A supported shared-Dáil-term proposal requires the fixed member_a, membership_a, member_b, membership_b, and shared_term referents."
        )
    referents: dict[str, dict[str, Any]] = {}
    for referent_id, expected_type in referent_roles.items():
        item = value["referents"][referent_id]
        if not isinstance(item, dict) or set(item) != {"type", "mention"}:
            raise InvalidComposableDraft(
                f"Referent {referent_id!r} must contain exactly type and mention."
            )
        if not isinstance(item["type"], str) or item["type"] != expected_type:
            raise UnsupportedComposableRequest(
                f"Referent {referent_id!r} must have reviewed type {expected_type!r}."
            )
        mention = item["mention"]
        if referent_id in {"member_a", "member_b"}:
            if not isinstance(mention, str) or not mention.strip():
                raise InvalidComposableDraft("Member referents require non-empty user-supplied labels.")
            referents[referent_id] = {"type": expected_type, "mention": mention.strip()}
        else:
            if mention is not None:
                raise InvalidComposableDraft("Only the two Member referents may carry user-supplied labels.")
            referents[referent_id] = {"type": expected_type}

    member_ids = ["member_a", "member_b"]
    membership_ids = ["membership_a", "membership_b"]
    term_ids = ["shared_term"]
    for referent_id in member_ids:
        mention = referents[referent_id].get("mention")
        if not isinstance(mention, str) or _label_position(question, mention) is None:
            raise InvalidComposableDraft(
                f"Member referent {referent_id!r} must be an exact user-supplied name mention."
            )
    normalized_mentions = [
        unicodedata.normalize("NFC", referents[key]["mention"]).casefold()
        for key in member_ids
    ]
    if normalized_mentions[0] == normalized_mentions[1]:
        raise InvalidComposableDraft(
            "The two Member referents must be independently named, not repeated copies of one name."
        )
    if len(value["relations"]) != 4:
        raise InvalidComposableDraft(
            "Both Members require a complete Member → DailMembership → shared DailTerm path."
        )
    actual_edges: list[tuple[str, str, str]] = []
    relation_ids: set[str] = set()
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        if relation_id in relation_ids:
            raise InvalidComposableDraft("Relation IDs must be unique.")
        relation_ids.add(relation_id)
        fact = relation["fact"]
        if (not isinstance(fact, str)
                or fact not in {"member_has_membership", "membership_in_term"}):
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the reviewed shared-Dáil-term composition."
            )
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        if source not in referents or target not in referents:
            raise InvalidComposableDraft("Every relationship endpoint must name a declared referent.")
        actual_edges.append((fact, source, target))

    term_id = term_ids[0]
    expected_edges: list[tuple[str, str, str]] = []
    seen_memberships: set[str] = set()
    for member_id in member_ids:
        linked = [
            edge for edge in actual_edges
            if edge[0] == "member_has_membership" and edge[1] == member_id
        ]
        if len(linked) != 1 or referents[linked[0][2]]["type"] != "DailMembership":
            raise InvalidComposableDraft(
                f"Member referent {member_id!r} must have exactly one typed DailMembership relationship."
            )
        membership_id = linked[0][2]
        if membership_id in seen_memberships:
            raise InvalidComposableDraft("Each Member requires an independent DailMembership referent.")
        seen_memberships.add(membership_id)
        expected_edges.extend([
            ("member_has_membership", member_id, membership_id),
            ("membership_in_term", membership_id, term_id),
        ])
    if sorted(actual_edges) != sorted(expected_edges):
        raise InvalidComposableDraft(
            "Every DailMembership must link to the same answer DailTerm identity; disconnected or extra edges are not supported."
        )

    expected_answer = {
        "kind": "entities", "referent": term_id,
        "distinctBy": "identity", "display": ["label"],
    }
    if value["answer"] != expected_answer:
        raise InvalidComposableDraft(
            "The answer must be the distinct shared DailTerm identity set with its mapped label."
        )

    plan_referents: dict[str, dict[str, Any]] = {}
    for referent_id, item in referents.items():
        final = {"type": item["type"]}
        if "mention" in item:
            final["mention"] = item["mention"]
            final["resolution"] = "unresolved"
        if referent_id == term_id:
            final["answer"] = True
        plan_referents[referent_id] = final

    return {
        "family": "shared_dail_terms",
        "referents": plan_referents,
        "relations": [dict(item) for item in value["relations"]],
        "answer": dict(value["answer"]),
    }, None


def complete_v2_plan(draft_plan: dict[str, Any], *, as_of: date) -> dict[str, Any]:
    """Add only deterministic composable-v2 envelope metadata to a draft."""
    return {"version": 2, "asOf": as_of.isoformat(), **draft_plan}


def parse_composable_plan_output(output: str) -> Any:
    """Use the shared strict JSON parser for duplicate-key/NaN rejection."""
    try:
        return parse_draft_json(output)
    except ValueError as error:
        raise InvalidComposableOutput(str(error)) from error
