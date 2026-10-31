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
_DAIL_ORDINAL = re.compile(r"\b(?P<number>[0-9]{1,3})(?P<suffix>st|nd|rd|th)\b", re.IGNORECASE)


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
    shared_terms = next(
        item for item in contract["questionFamilies"]
        if item["id"] == "shared_dail_terms"
    )
    member_composition = next(
        item for item in contract["questionFamilies"]
        if item["id"] == "member_relationship_composition"
    )
    relations = {item["id"]: item for item in contract["relations"]}
    relation_guidance = "\n".join(
        f"- {fact}: {relations[fact]['subjectType']} to {relations[fact]['objectType']}"
        for fact in (
            "member_has_membership", "membership_in_term",
            "membership_represents", "constituency_in_term",
            "member_party_membership", "party_episode_in_membership",
            "episode_in_parliamentary_party", "party_active_during_term",
            "parliamentary_party_has_affiliation_identity",
        )
    )
    return f"""Interpret one user question as a semantic proposal for composable query plan v2.

Existing shared-term capability: {shared_terms['semantics']}

Reusable Member relationship capability: {member_composition['semantics']}

Use the existing semantic relationship identifiers below; these are proposals, not authority decisions:
{relation_guidance}

For the existing shared-term capability, use family "shared_dail_terms" and fixed referent keys member_a, membership_a, member_b, membership_b, and shared_term. Member entries use exact user-supplied labels. Each Member has an independent DailMembership path to the same shared DailTerm identity; set "constraints": [] and set "answer" to exactly {{"kind":"entities","referent":"shared_term","distinctBy":"identity","display":["label"],"details":[],"preserveEvidence":false}}.

For the reusable Member relationship capability, use family "member_relationship_composition" and one Member answer referent with a null mention. Every DailTerm referent must carry selector {{"kind":"termNumber","number":N}} for an explicitly requested numeric Dáil ordinal. Use one of these complete typed graph shapes only:
- keys member, membership_a, term_a, membership_b, and term_b: two distinct selected DailTerms, each reached from the same answer Member through a separate DailMembership; this returns Members with recorded membership in both exact term identities;
- keys member, membership, term, and constituency: one selected DailTerm and one exact user-mentioned DailConstituency, where the same DailMembership links the Member to that term and constituency, and the constituency occurrence links to that same term identity.
Use distinct referent IDs for separate membership/term resources. Do not substitute matching labels for RDF identity joins. Preserve every selected term and the constituency when required. For either of these non-temporal shapes, set "constraints": [] and use exactly this answer value: {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[],"preserveEvidence":false}}.

For a dated political-party/constituency composition, use family "member_relationship_composition" and exactly the referents member, membership, term, constituency, episode, party, and affiliation. Connect member→membership→term, membership→constituency, constituency→term, member→episode, episode→membership, episode→party, party→term, and party→affiliation using their exact reviewed fact IDs. The episode must point to the exact same DailMembership that represents the constituency in the selected term. Set "constraints" to exactly [{{"referent":"episode","field":"partyEpisodeInterval","operator":"overlaps","value":"membership"}}] (inclusive xsd:dateTime endpoints; an absent end is open-ended; missing interval/start means uncertain, never a positive or negative match). Only typed PartyMembership records count; Independent is not a party. For "which parties" questions, use a null affiliation mention and set "answer" to exactly {{"kind":"entities","referent":"affiliation","distinctBy":"identity","display":["label"],"details":[{{"referent":"member","display":["name"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}. For a named-party TD question, keep the exact named affiliation mention as a required identity filter and set "answer" to exactly {{"kind":"entities","referent":"member","distinctBy":"identity","display":["name"],"details":[{{"referent":"affiliation","display":["label"]}},{{"referent":"episode","display":["start","end"]}},{{"referent":"membership","display":["start","end"]}}],"preserveEvidence":true}}. Never use current party state, party-label equality, or term context as a substitute for the dated episode and exact identity links.

If a question asks for any other relationship, more or fewer terms than the supported shapes, an extra filter, temporal restriction, different answer, or anything outside these capabilities, return supported=false with a concise unsupportedReason, null family, null referents, empty relations, "constraints": [], and null answer. Never simplify an unsupported request by dropping an essential relation or constraint.

Semantic interpretation only. Never output SPARQL, predicates, graph names, variables, endpoints, URLs, IRIs, candidates, or resolution decisions. Do not decide whether a mapping is authoritative; local code checks all proposed relation IDs against the reviewed v2 and query-schema contracts. Do not add assumptions about source completeness.

Return only the JSON object required by the strict composable-plan-v2 draft schema. All schema fields are required; family, unsupportedReason, referents, and answer are null when not applicable."""


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
        "version", "supported", "family", "unsupportedReason", "intent",
        "referents", "relations", "constraints", "answer",
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
    if not isinstance(value["relations"], list) or not isinstance(value["constraints"], list):
        raise InvalidComposableDraft("Relations and constraints must be arrays.")

    if value["supported"] is False:
        reason = value["unsupportedReason"]
        if (not isinstance(reason, str) or not reason.strip()
                or value["family"] is not None or value["referents"] is not None
                or value["relations"] or value["constraints"] or value["answer"] is not None):
            raise InvalidComposableDraft(
                "An unsupported proposal must provide a reason and no executable semantic plan."
            )
        return None, reason.strip()
    if value["unsupportedReason"] is not None:
        raise InvalidComposableDraft("A supported proposal cannot also carry an unsupported reason.")

    if value["family"] == "member_relationship_composition":
        return _validate_member_relationship_draft(value, question=question), None
    if value["family"] != "shared_dail_terms":
        raise UnsupportedComposableRequest(
            f"Composable semantic family {value['family']!r} is not supported."
        )

    referent_roles = {
        "member_a": "Member",
        "membership_a": "DailMembership",
        "member_b": "Member",
        "membership_b": "DailMembership",
        "shared_term": "DailTerm",
    }
    if value["constraints"]:
        raise InvalidComposableDraft("Shared-Dáil-term plans do not accept temporal or extra constraints.")
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
    if value["answer"] != {
        **expected_answer, "details": [], "preserveEvidence": False,
    }:
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
        "answer": expected_answer,
    }, None


def _ordinal_suffix(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _validate_member_party_composition_draft(
    value: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    """Validate the one shared graph and temporal operator used by U06/U16."""
    referents = value["referents"]
    expected_types = {
        "member": "Member",
        "membership": "DailMembership",
        "term": "DailTerm",
        "constituency": "DailConstituency",
        "episode": "PartyMembershipEpisode",
        "party": "ParliamentaryParty",
        "affiliation": "PoliticalAffiliationIdentity",
    }
    if not isinstance(referents, dict) or set(referents) != set(expected_types):
        raise InvalidComposableDraft(
            "Dated party/representation composition requires exactly Member, membership, term, constituency, episode, party, and affiliation referents."
        )

    normalized: dict[str, dict[str, Any]] = {}
    for key, semantic_type in expected_types.items():
        item = referents[key]
        if not isinstance(item, dict) or item.get("type") != semantic_type:
            raise InvalidComposableDraft(f"Referent {key!r} must have reviewed type {semantic_type!r}.")
        if key in {"member", "membership", "episode", "party"}:
            if set(item) != {"type", "mention"} or item["mention"] is not None:
                raise InvalidComposableDraft(f"Referent {key!r} is a typed relationship role, not a name filter.")
            normalized[key] = {"type": semantic_type}
        elif key == "term":
            selector = item.get("selector")
            if (set(item) != {"type", "mention", "selector"}
                    or item["mention"] is not None
                    or not isinstance(selector, dict)
                    or set(selector) != {"kind", "number"}
                    or selector.get("kind") != "termNumber"
                    or type(selector.get("number")) is not int
                    or not 1 <= selector["number"] <= 999):
                raise InvalidComposableDraft("The term must be one explicitly numbered DailTerm.")
            normalized[key] = {"type": semantic_type, "selector": selector}
        elif key == "constituency":
            mention = item.get("mention")
            if (set(item) != {"type", "mention"} or not isinstance(mention, str)
                    or not mention.strip() or _label_position(question, mention) is None):
                raise InvalidComposableDraft("The DailConstituency must preserve an exact user-supplied name mention.")
            normalized[key] = {"type": semantic_type, "mention": mention.strip()}
        else:
            mention = item.get("mention")
            if set(item) != {"type", "mention"} or (mention is not None and (
                not isinstance(mention, str) or not mention.strip()
                or _label_position(question, mention) is None
            )):
                raise InvalidComposableDraft("The affiliation must be either a null all-parties selector or an exact named-party mention.")
            normalized[key] = {"type": semantic_type, "mention": mention.strip() if isinstance(mention, str) else None}

    term_numbers = _question_dail_ordinals(question)
    if len(term_numbers) != 1 or term_numbers[0] != normalized["term"]["selector"]["number"]:
        raise InvalidComposableDraft("The plan must preserve exactly one explicitly requested numeric Dáil term.")

    party_list_question = bool(re.search(
        r"\b(?:which|what)\s+(?:political\s+)?part(?:y|ies)\b", question, re.IGNORECASE,
    ))
    affiliation_mention = normalized["affiliation"]["mention"]
    if party_list_question and affiliation_mention is not None:
        raise InvalidComposableDraft("An all-parties answer cannot silently add a named affiliation filter.")
    if not party_list_question and affiliation_mention is None:
        raise InvalidComposableDraft("A named-party Member answer must retain its party identity filter.")

    contract = _plan_contract()
    relation_defs = {item["id"]: item for item in contract["relations"]}
    expected_edges = {
        "member_has_membership": ("member", "membership"),
        "membership_in_term": ("membership", "term"),
        "membership_represents": ("membership", "constituency"),
        "constituency_in_term": ("constituency", "term"),
        "member_party_membership": ("member", "episode"),
        "party_episode_in_membership": ("episode", "membership"),
        "episode_in_parliamentary_party": ("episode", "party"),
        "party_active_during_term": ("party", "term"),
        "parliamentary_party_has_affiliation_identity": ("party", "affiliation"),
    }
    actual_edges: dict[str, tuple[str, str]] = {}
    relation_ids: set[str] = set()
    if not isinstance(value["relations"], list):
        raise InvalidComposableDraft("Dated party/representation relationships must be an array.")
    for index, relation in enumerate(value["relations"]):
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise InvalidComposableDraft(f"Relation {index} contains unsupported or missing fields.")
        relation_id = _identifier(relation["id"], f"relations[{index}].id")
        fact = relation["fact"]
        if not isinstance(fact, str) or fact not in expected_edges:
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the exact reviewed party/representation composition."
            )
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        if relation_id in relation_ids or fact in actual_edges:
            raise InvalidComposableDraft("Dated composition relation IDs and facts must be unique.")
        relation_ids.add(relation_id)
        if (source, target) != expected_edges[fact]:
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the exact reviewed party/representation composition."
            )
        if fact not in relation_defs:
            raise UnsupportedComposableRequest(f"Relationship {fact!r} has no reviewed v2 relation mapping.")
        actual_edges[fact] = (source, target)
    if len(value["relations"]) != len(expected_edges):
        raise InvalidComposableDraft("Every dated party/representation relationship edge is required exactly once.")
    if actual_edges != expected_edges:
        raise InvalidComposableDraft(
            "The party episode, DailMembership, term, constituency, party, and affiliation paths must be connected by exact referent identity."
        )
    for fact, (source, target) in expected_edges.items():
        definition = relation_defs[fact]
        if (expected_types[source], expected_types[target]) != (definition["subjectType"], definition["objectType"]):
            raise UnsupportedComposableRequest(f"Reviewed relationship {fact!r} has incompatible entity types.")

    interval_constraint = {
        "referent": "episode", "field": "partyEpisodeInterval", "operator": "overlaps", "value": "membership",
    }
    if value["constraints"] != [interval_constraint]:
        raise InvalidComposableDraft(
            "The plan must preserve the required PartyMembershipEpisode/DailMembership interval-overlap constraint and no extra constraints."
        )

    if party_list_question:
        answer = {
            "kind": "entities", "referent": "affiliation", "distinctBy": "identity", "display": ["label"],
            "details": [
                {"referent": "member", "display": ["name"]},
                {"referent": "episode", "display": ["start", "end"]},
                {"referent": "membership", "display": ["start", "end"]},
            ],
            "preserveEvidence": True,
        }
        if value["answer"] != answer:
            raise InvalidComposableDraft("A party-list question must return distinct reviewed identity resources with separate Member/interval evidence.")
    else:
        answer = {
            "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
            "details": [
                {"referent": "affiliation", "display": ["label"]},
                {"referent": "episode", "display": ["start", "end"]},
                {"referent": "membership", "display": ["start", "end"]},
            ],
            "preserveEvidence": True,
        }
        if value["answer"] != answer:
            raise InvalidComposableDraft("A named-party question must return distinct Member identities and preserve the affiliation/date evidence.")

    final_referents: dict[str, dict[str, Any]] = {}
    for key, semantic_type in expected_types.items():
        if key == "member":
            final_referents[key] = {"type": semantic_type, **({"answer": True} if not party_list_question else {})}
        elif key == "term":
            final_referents[key] = {"type": semantic_type, "selector": dict(normalized[key]["selector"])}
        elif key == "constituency":
            final_referents[key] = {"type": semantic_type, "mention": normalized[key]["mention"], "resolution": "unresolved"}
        elif key == "affiliation" and party_list_question:
            final_referents[key] = {"type": semantic_type, "answer": True}
        elif key == "affiliation":
            final_referents[key] = {"type": semantic_type, "mention": affiliation_mention, "resolution": "unresolved"}
        else:
            final_referents[key] = {"type": semantic_type}

    return {
        "family": "member_relationship_composition",
        "referents": final_referents,
        "relations": [dict(item) for item in value["relations"]],
        "constraints": [dict(item) for item in value["constraints"]],
        "answer": answer,
    }


def _question_dail_ordinals(question: str) -> list[int]:
    values: list[int] = []
    for match in _DAIL_ORDINAL.finditer(question):
        number = int(match.group("number"))
        if match.group("suffix").casefold() != _ordinal_suffix(number):
            raise InvalidComposableDraft("A Dáil term ordinal in the question is malformed.")
        values.append(number)
    return values


def _validate_member_relationship_draft(
    value: dict[str, Any],
    *,
    question: str,
) -> dict[str, Any]:
    """Validate only the two closed relationship projections using v2 edges."""
    referents = value["referents"]
    if isinstance(referents, dict) and any(
        isinstance(item, dict) and item.get("type") == "PartyMembershipEpisode"
        for item in referents.values()
    ):
        return _validate_member_party_composition_draft(value, question=question)
    if value["constraints"]:
        raise InvalidComposableDraft("The non-party Member composition shapes do not accept extra constraints.")
    if re.search(r"\b(?:party|political affiliation|Sinn Féin|Fianna Fáil|Fine Gael|Labour|Green Party)\b", question, re.IGNORECASE):
        raise UnsupportedComposableRequest(
            "The question includes a party-affiliation condition that is absent from the proposed relationship graph."
        )
    if not isinstance(referents, dict) or not 4 <= len(referents) <= 5:
        raise InvalidComposableDraft(
            "Member relationship composition requires one Member and a complete supported membership graph."
        )

    typed: dict[str, str] = {}
    term_numbers: dict[str, int] = {}
    constituency_mentions: dict[str, str] = {}
    for referent_id, item in referents.items():
        _identifier(referent_id, "referent ID")
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            raise InvalidComposableDraft("Every composition referent requires a controlled type.")
        semantic_type = item["type"]
        if semantic_type == "Member":
            if set(item) != {"type", "mention"} or item["mention"] is not None:
                raise InvalidComposableDraft(
                    "The Member referent is the set-valued answer and cannot bind a named person."
                )
        elif semantic_type == "DailMembership":
            if set(item) != {"type", "mention"} or item["mention"] is not None:
                raise InvalidComposableDraft("DailMembership referents are relationship evidence, not named entities.")
        elif semantic_type == "DailTerm":
            selector = item.get("selector")
            if (set(item) != {"type", "mention", "selector"}
                    or item["mention"] is not None
                    or not isinstance(selector, dict)
                    or set(selector) != {"kind", "number"}
                    or selector.get("kind") != "termNumber"
                    or type(selector.get("number")) is not int
                    or not 1 <= selector["number"] <= 999):
                raise InvalidComposableDraft(
                    "Each DailTerm requires an explicitly selected numeric term ordinal."
                )
            term_numbers[referent_id] = selector["number"]
        elif semantic_type == "DailConstituency":
            mention = item.get("mention")
            if (set(item) != {"type", "mention"}
                    or not isinstance(mention, str) or not mention.strip()
                    or _label_position(question, mention) is None):
                raise InvalidComposableDraft(
                    "The DailConstituency must use an exact user-supplied name mention."
                )
            constituency_mentions[referent_id] = mention.strip()
        else:
            raise UnsupportedComposableRequest(
                f"Referent type {semantic_type!r} is outside the reviewed Member relationship composition."
            )
        typed[referent_id] = semantic_type

    members = [key for key, value_type in typed.items() if value_type == "Member"]
    memberships = [key for key, value_type in typed.items() if value_type == "DailMembership"]
    terms = [key for key, value_type in typed.items() if value_type == "DailTerm"]
    constituencies = [key for key, value_type in typed.items() if value_type == "DailConstituency"]
    if len(members) != 1:
        raise InvalidComposableDraft("The supported composition has exactly one set-valued Member answer.")
    mentioned_ordinals = _question_dail_ordinals(question)
    if (len(term_numbers) != len(mentioned_ordinals)
            or sorted(term_numbers.values()) != sorted(mentioned_ordinals)
            or len(set(term_numbers.values())) != len(term_numbers)):
        raise InvalidComposableDraft(
            "The plan must preserve every distinct numeric Dáil term explicitly requested in the question."
        )

    relation_defs = {item["id"]: item for item in _plan_contract()["relations"]}
    relation_types = {
        fact: (definition["subjectType"], definition["objectType"])
        for fact, definition in relation_defs.items()
    }
    if not isinstance(value["relations"], list):
        raise InvalidComposableDraft("Relations must be an array.")
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
        if not isinstance(fact, str) or fact not in {
            "member_has_membership", "membership_in_term",
            "membership_represents", "constituency_in_term",
        }:
            raise UnsupportedComposableRequest(
                f"Relationship {fact!r} is outside the reviewed Member relationship composition."
            )
        source = _identifier(relation["from"], f"relations[{index}].from")
        target = _identifier(relation["to"], f"relations[{index}].to")
        if source not in typed or target not in typed:
            raise InvalidComposableDraft("Every relationship endpoint must name a declared referent.")
        if (typed[source], typed[target]) != relation_types[fact]:
            raise InvalidComposableDraft(f"Relationship {fact!r} has incompatible typed referents.")
        actual_edges.append((fact, source, target))

    member_id = members[0]
    expected_edges: list[tuple[str, str, str]] = []
    if len(terms) == 2 and len(memberships) == 2 and not constituencies:
        expected_edges.extend(
            ("member_has_membership", member_id, membership_id)
            for membership_id in memberships
        )
        membership_to_term: dict[str, str] = {}
        for fact, source, target in actual_edges:
            if fact == "membership_in_term":
                if source in membership_to_term:
                    raise InvalidComposableDraft("Each DailMembership must identify exactly one requested term.")
                membership_to_term[source] = target
        if set(membership_to_term) != set(memberships) or set(membership_to_term.values()) != set(terms):
            raise InvalidComposableDraft(
                "Each independent membership must link to a different explicitly requested DailTerm."
            )
        expected_edges.extend(
            ("membership_in_term", membership_id, membership_to_term[membership_id])
            for membership_id in memberships
        )
    elif len(terms) == 1 and len(memberships) == 1 and len(constituencies) == 1:
        membership_id, term_id, constituency_id = memberships[0], terms[0], constituencies[0]
        expected_edges = [
            ("member_has_membership", member_id, membership_id),
            ("membership_in_term", membership_id, term_id),
            ("membership_represents", membership_id, constituency_id),
            ("constituency_in_term", constituency_id, term_id),
        ]
    else:
        raise InvalidComposableDraft(
            "The plan must be either one Member in two numbered Dáil terms or one term-scoped constituency representation path."
        )
    if sorted(actual_edges) != sorted(expected_edges):
        raise InvalidComposableDraft(
            "The relationship graph is disconnected, incomplete, or contains an extra semantic edge."
        )

    expected_answer = {
        "kind": "entities", "referent": member_id,
        "distinctBy": "identity", "display": ["name"],
    }
    if value["answer"] != {**expected_answer, "details": [], "preserveEvidence": False}:
        raise InvalidComposableDraft("The answer must return distinct Member identities by local name.")

    final_referents: dict[str, dict[str, Any]] = {}
    for referent_id, semantic_type in typed.items():
        if semantic_type == "Member":
            final_referents[referent_id] = {"type": semantic_type, "answer": True}
        elif semantic_type == "DailMembership":
            final_referents[referent_id] = {"type": semantic_type}
        elif semantic_type == "DailTerm":
            final_referents[referent_id] = {
                "type": semantic_type,
                "selector": {"kind": "termNumber", "number": term_numbers[referent_id]},
            }
        else:
            final_referents[referent_id] = {
                "type": semantic_type,
                "mention": constituency_mentions[referent_id],
                "resolution": "unresolved",
            }
    return {
        "family": "member_relationship_composition",
        "referents": final_referents,
        "relations": [dict(item) for item in value["relations"]],
        "constraints": [],
        "answer": expected_answer,
    }


def complete_v2_plan(draft_plan: dict[str, Any], *, as_of: date) -> dict[str, Any]:
    """Add only deterministic composable-v2 envelope metadata to a draft."""
    return {"version": 2, "asOf": as_of.isoformat(), **draft_plan}


def parse_composable_plan_output(output: str) -> Any:
    """Use the shared strict JSON parser for duplicate-key/NaN rejection."""
    try:
        return parse_draft_json(output)
    except ValueError as error:
        raise InvalidComposableOutput(str(error)) from error
