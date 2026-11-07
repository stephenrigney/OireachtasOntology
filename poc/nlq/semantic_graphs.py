"""Pure constructors for complete drafts of already-supported NLQ graph shapes.

The constructors accept semantic slots that a caller has already validated;
they do not inspect or authorize a question, resolve identities, execute a
query, or accept a model-authored graph as authority. Callers must validate the
slots against the *original question's full intent*, pass the generated draft
through ``validate_composable_plan_draft(..., question=original_question)``,
and run the existing final ``validate_plan`` graph validator before use. A
rejected legacy/model draft must remain rejected; these constructors are not a
repair or fallback path for one.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import unicodedata
from typing import Any

from .representation import EDGES as _REPRESENTATION_EDGES
from .representation import representation_plan


# Canonical semantic edge tuples are (fact, source referent, target referent).
# Keep them available for callers that want to share graph-shape expectations
# with future validation code rather than restating relation authority.
SHARED_DAIL_TERMS_EDGES: tuple[tuple[str, str, str], ...] = (
    ("member_has_membership", "member_a", "membership_a"),
    ("membership_in_term", "membership_a", "shared_term"),
    ("member_has_membership", "member_b", "membership_b"),
    ("membership_in_term", "membership_b", "shared_term"),
)

ANCHORED_SHARED_CONSTITUENCY_EDGES: tuple[tuple[str, str, str], ...] = (
    ("member_has_membership", "anchorMember", "anchorMembership"),
    ("membership_in_term", "anchorMembership", "term"),
    ("membership_represents", "anchorMembership", "constituency"),
    ("member_has_membership", "member", "membership"),
    ("membership_in_term", "membership", "term"),
    ("membership_represents", "membership", "constituency"),
    ("constituency_in_term", "constituency", "term"),
)

CONSTITUENCY_REPRESENTATION_EDGES: tuple[tuple[str, str, str], ...] = tuple(
    (fact, source, target)
    for fact, (source, target) in _REPRESENTATION_EDGES.items()
)

__all__ = [
    "ANCHORED_SHARED_CONSTITUENCY_EDGES",
    "CONSTITUENCY_REPRESENTATION_EDGES",
    "SHARED_DAIL_TERMS_EDGES",
    "build_anchored_shared_constituency_draft",
    "build_constituency_representation_draft",
    "build_shared_dail_terms_draft",
]


def _mention(value: Any, *, role: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{role} must be a non-empty exact mention.")
    return value.strip()


def _relation_id(edge: tuple[str, str, str]) -> str:
    """Create a stable, schema-safe ID from the complete semantic edge tuple."""
    return "edge_" + "_".join(edge)


def _relations(edges: tuple[tuple[str, str, str], ...]) -> list[dict[str, str]]:
    relations = [
        {"id": _relation_id(edge), "fact": edge[0], "from": edge[1], "to": edge[2]}
        for edge in edges
    ]
    ids = [relation["id"] for relation in relations]
    if len(ids) != len(set(ids)):
        raise ValueError("The canonical graph shape does not have unique relation identifiers.")
    return relations


def _draft(*, family: str, intent: str, referents: dict[str, Any],
           edges: tuple[tuple[str, str, str], ...], answer: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 2,
        "supported": True,
        "family": family,
        "unsupportedReason": None,
        "intent": intent,
        "referents": referents,
        "relations": _relations(edges),
        "constraints": [],
        "answer": answer,
    }


def build_shared_dail_terms_draft(member_a: str, member_b: str) -> dict[str, Any]:
    """Build the exact two-named-Member intersection over shared Dáil terms.

    ``member_a`` and ``member_b`` must already be validated mentions from the
    original question. This function preserves both independent membership
    paths to one shared DailTerm answer identity.
    """
    first = _mention(member_a, role="member_a")
    second = _mention(member_b, role="member_b")
    normalized = [unicodedata.normalize("NFC", value).casefold() for value in (first, second)]
    if normalized[0] == normalized[1]:
        raise ValueError("The two Member mentions must identify independently named people.")

    return _draft(
        family="shared_dail_terms",
        intent="Find the exact Dáil terms shared by the two named Members.",
        referents={
            "member_a": {"type": "Member", "mention": first},
            "membership_a": {"type": "DailMembership", "mention": None},
            "member_b": {"type": "Member", "mention": second},
            "membership_b": {"type": "DailMembership", "mention": None},
            "shared_term": {"type": "DailTerm", "mention": None},
        },
        edges=SHARED_DAIL_TERMS_EDGES,
        answer={
            "kind": "entities", "referent": "shared_term", "distinctBy": "identity",
            "display": ["label"], "details": [], "preserveEvidence": False,
        },
    )


def _shared_constituency_selector(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("The DailTerm selector must be a reviewed selector object.")
    selector = dict(value)
    if (set(selector) == {"kind", "number"} and selector.get("kind") == "termNumber"
            and type(selector.get("number")) is int and 1 <= selector["number"] <= 999):
        return selector
    if selector == {"kind": "previousTerm"}:
        return selector
    raise ValueError("Use one exact termNumber or previousTerm Dáil selector.")


def build_anchored_shared_constituency_draft(
    anchor_member: str,
    term_selector: Mapping[str, Any],
    *,
    count: bool = False,
) -> dict[str, Any]:
    """Build the term-wide seven-edge shared-constituency Member selection.

    The named anchor and term selector are already-authorized semantic slots;
    ``count`` changes only the projection, never the selected graph. The shape
    intentionally has no party, office, date, or current-point role/filter.
    """
    anchor = _mention(anchor_member, role="anchorMember")
    selector = _shared_constituency_selector(term_selector)
    if type(count) is not bool:
        raise ValueError("count must be a Boolean projection choice.")

    answer = (
        {"kind": "count", "referent": "member", "distinctBy": "identity"}
        if count else {
            "kind": "entities", "referent": "member", "distinctBy": "identity",
            "display": ["name"], "details": [], "preserveEvidence": False,
        }
    )
    return _draft(
        family="member_relationship_composition",
        intent=("Count other Members" if count else "List other Members")
        + " in the anchor's exact constituency and selected Dáil term.",
        referents={
            "member": {"type": "Member", "mention": None},
            "membership": {"type": "DailMembership", "mention": None},
            "term": {"type": "DailTerm", "mention": None, "selector": selector},
            "constituency": {"type": "DailConstituency", "mention": None},
            "anchorMember": {"type": "Member", "mention": anchor},
            "anchorMembership": {"type": "DailMembership", "mention": None},
        },
        edges=ANCHORED_SHARED_CONSTITUENCY_EDGES,
        answer=answer,
    )


def build_constituency_representation_draft(
    member: str,
    selector: str | None,
) -> dict[str, Any]:
    """Build the existing named-Member constituency representation draft.

    ``selector`` is exactly ``"currentTerm"``, ``"latestRecorded"``, or
    ``None`` for the existing career-wide representation shape. The reviewed
    ``representation_plan`` supplies the canonical evidence-preserving answer;
    its four edge facts are reused through ``representation.EDGES``.
    """
    mention = _mention(member, role="member")
    if selector not in ("currentTerm", "latestRecorded", None) or (
        selector is not None and not isinstance(selector, str)
    ):
        raise ValueError("Use currentTerm, latestRecorded, or null for representation scope.")

    # representation_plan is a pure graph constructor/validator. This fixed
    # date supplies only its required envelope metadata and is discarded below;
    # no current term is selected or resolved in this module.
    canonical = representation_plan(
        as_of=date(2000, 1, 1),
        member=mention,
        current=selector == "currentTerm",
        latest_recorded=selector == "latestRecorded",
    )
    referents = {
        "member": {"type": "Member", "mention": mention},
        "membership": {"type": "DailMembership", "mention": None},
        "term": {"type": "DailTerm", "mention": None, "selector": selector},
        "constituency": {"type": "DailConstituency", "mention": None},
    }
    return _draft(
        family="constituency_representation",
        intent="Return the named Member's constituency evidence in the requested Dáil-term scope.",
        referents=referents,
        edges=CONSTITUENCY_REPRESENTATION_EDGES,
        answer=canonical["answer"],
    )
