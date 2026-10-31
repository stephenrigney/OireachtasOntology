"""Small typed graph plans and deterministic bounded query compilation.

The browser uses this replacement plan path.  Plans contain semantic relation
IDs only; every query below is compiled from this module's reviewed mapping
table, never from question text.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

from rdflib import URIRef

from .contract import load_query_contract
from .errors import NLQError
from .member_resolution import UnsupportedLocalEntityType, resolve_local_entity_label
from .results import QueryResult, format_debug_payload
from .safety import validate_sparql


PLAN_VERSION = 2
_PLAN_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "specs" / "composable-query-plan-contract.json"
_PLAN_CONTRACT = json.loads(_PLAN_CONTRACT_PATH.read_text(encoding="utf-8"))
_AFFILIATION_DECISIONS_PATH = Path(__file__).resolve().parents[2] / "reports" / "party-identity-decisions.json"
_RELATION_TYPES = {
    relation["id"]: (relation["subjectType"], relation["objectType"])
    for relation in _PLAN_CONTRACT["relations"]
}
_RELATION_MAPPINGS = {relation["id"]: relation for relation in _PLAN_CONTRACT["relations"]}
_CONSTRAINT_MAPPINGS = {constraint["field"]: constraint for constraint in _PLAN_CONTRACT.get("constraints", [])}
_PREFIXES = """PREFIX agents: <https://data.oireachtas.ie/ontology#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


class PlanError(ValueError):
    """A draft plan is invalid or names an unsupported semantic relation."""


class UnrecognizedQuestion(PlanError):
    """No deterministic family recognized the question's surface form."""


@dataclass(frozen=True)
class PlanOutcome:
    status: str
    plan: dict[str, Any] | None = None
    diagnostic: str | None = None
    candidates: tuple[dict[str, str], ...] = ()
    sparql: str | None = None
    result: QueryResult | None = None
    request_family: str | None = None
    debug_output: str | None = None
    debug_source: str | None = None


@dataclass(frozen=True)
class BillSponsorshipProjection:
    """Readable one-row-per-Bill projection with participation evidence retained."""

    result: QueryResult
    missing_primary_status: bool = False
    incomplete_display: bool = False
    conflicting_evidence: bool = False
    diagnostics: tuple[str, ...] = ()


def _validate_debate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    refs = plan["referents"]
    if set(refs) != {"sitting", "record"} or refs["sitting"].get("type") != "DebateSitting" or refs["record"].get("type") != "DebateRecord":
        raise PlanError("Debate plans require one DebateSitting and its DebateRecord referents.")
    supported_referent_fields = {"sitting": {"type", "answer"}, "record": {"type"}}
    for referent_id, supported_fields in supported_referent_fields.items():
        if set(refs[referent_id]) != supported_fields:
            raise PlanError(
                f"Debate referent {referent_id!r} contains unsupported or missing attributes; "
                "only the reviewed type and sitting answer declaration are supported."
            )
    if plan["relations"] != [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}]:
        raise PlanError("Debate plans require the reviewed sitting-to-produced-record relationship.")
    if _RELATION_TYPES.get("sitting_produced_record") != (refs["sitting"]["type"], refs["record"]["type"]):
        raise PlanError("Reviewed Debate relationship type signature does not match its referents.")
    constraints = plan.get("constraints")
    if not isinstance(constraints, list) or any(not isinstance(item, dict) for item in constraints):
        raise PlanError("Debate constraints must be controlled constraint objects.")
    if len(constraints) != 2:
        raise PlanError("Debate plans require exactly one date and one chamber constraint.")
    date_mapping = _CONSTRAINT_MAPPINGS.get("date", {})
    chamber_mapping = _CONSTRAINT_MAPPINGS.get("chamber", {})
    date_constraints = [item for item in constraints if set(item) == {"referent", "field", "operator", "value"}
                        and item.get("referent") == "sitting" and item.get("field") == "date"
                        and item.get("operator") == date_mapping.get("operator")]
    chamber_constraints = [item for item in constraints if set(item) == {"referent", "field", "operator", "value"}
                           and item.get("referent") == "record" and item.get("field") == "chamber"
                           and item.get("operator") == chamber_mapping.get("operator")
                           and item.get("value") in {value["id"] for value in chamber_mapping.get("allowedValues", [])}]
    if (date_mapping.get("referentType") != refs["sitting"]["type"]
            or chamber_mapping.get("referentType") != refs["record"]["type"]
            or date_mapping.get("valueKind") != "date"
            or chamber_mapping.get("valueKind") != "controlled_route"
            or date_mapping.get("graphFamily") != "debates"
            or chamber_mapping.get("graphFamily") != "debates"):
        raise PlanError("Reviewed Debate constraint vocabulary is missing or inconsistent.")
    if len(date_constraints) != 1 or len(chamber_constraints) != 1:
        raise PlanError("Debate plan constraints must select an ISO date and a supported Dáil/Seanad route.")
    try:
        date.fromisoformat(date_constraints[0]["value"])
    except (TypeError, ValueError) as error:
        raise PlanError("Debate date constraint must be an ISO calendar date.") from error
    answer = plan["answer"]
    if answer == {"kind": "boolean", "referent": "sitting"}:
        if refs["sitting"].get("answer") is not True:
            raise PlanError("Boolean Debate answer must identify the DebateSitting referent as the answer.")
    elif answer == {"kind": "entities", "referent": "sitting", "distinctBy": "identity", "display": ["date", "officialLink"]}:
        if refs["sitting"].get("answer") is not True:
            raise PlanError("Debate entity answer must identify the DebateSitting referent as the answer.")
    else:
        raise PlanError("Debate answer must be a boolean or a readable sitting/date/link entity result.")
    return plan


def _validate_office_plan(plan: dict[str, Any]) -> dict[str, Any]:
    refs = plan["referents"]
    if set(refs) != {"member", "holding", "office"}:
        raise PlanError("Q35 requires exactly Member, OfficeHolding, and NamedOffice referents.")
    member = refs["member"]
    if not isinstance(member, dict) or member.get("type") != "Member" or member.get("answer") is not True:
        raise PlanError("Q35 must return Member identities as its answer referent.")
    member_bound = set(member) != {"type", "answer"}
    if member_bound:
        if (set(member) != {"type", "answer", "mention", "resolution", "iri", "label"}
                or member.get("resolution") != "resolved"
                or not isinstance(member.get("mention"), str) or not member["mention"].strip()
                or not isinstance(member.get("label"), str) or not member["label"].strip()):
            raise PlanError("A bound Q35 Member must be an exactly resolved person identity with a display-only label.")
        _require_local_iri(member["iri"], "Member")
    if refs["holding"] != {"type": "OfficeHolding"}:
        raise PlanError("Q35 requires a plain OfficeHolding evidence referent.")
    office = refs["office"]
    if not isinstance(office, dict) or office.get("type") != "NamedOffice":
        raise PlanError("Q35 office referent must be a resolved NamedOffice.")
    allowed_office_fields = {
        "unresolved": {"type", "mention", "resolution"},
        "resolved": {"type", "mention", "resolution", "iri", "label"},
        "ambiguous": {"type", "mention", "resolution", "candidates"},
        "not_found": {"type", "mention", "resolution"},
        "source_data_unavailable": {"type", "mention", "resolution"},
        "unsupported_mapping": {"type", "mention", "resolution"},
    }
    resolution = office.get("resolution")
    if (not isinstance(resolution, str) or resolution not in allowed_office_fields
            or set(office) != allowed_office_fields[resolution]):
        raise PlanError("Q35 office referent contains unsupported or missing resolution attributes.")
    if not isinstance(office.get("mention"), str) or not office["mention"].strip():
        raise PlanError("Q35 requires a named office mention.")
    if resolution == "resolved":
        _require_local_iri(office["iri"], "NamedOffice")
        if not isinstance(office["label"], str) or not office["label"].strip():
            raise PlanError("A resolved Q35 office requires its reviewed local label.")
    if resolution == "ambiguous":
        candidates = office["candidates"]
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise PlanError("An ambiguous Q35 office requires at least two local candidates.")
        for candidate in candidates:
            if (not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}
                    or not isinstance(candidate["label"], str) or not candidate["label"].strip()):
                raise PlanError("Q35 office candidates must contain only a local IRI and readable label.")
            _require_local_iri(candidate["iri"], "NamedOffice candidate")

    expected_relations = {
        "member_has_office_holding": ("member", "holding"),
        "office_holding_of_office": ("holding", "office"),
    }
    if not isinstance(plan["relations"], list) or len(plan["relations"]) != len(expected_relations):
        raise PlanError("Q35 requires exactly the reviewed Member → OfficeHolding → NamedOffice path.")
    relation_ids = set()
    for relation in plan["relations"]:
        if (not isinstance(relation, dict)
                or set(relation) != {"id", "fact", "from", "to"}
                or any(not isinstance(relation[field], str) or not relation[field]
                       for field in ("id", "fact", "from", "to"))):
            raise PlanError("Q35 relations require non-empty IDs, reviewed facts, and referent IDs only.")
        if relation["id"] in relation_ids:
            raise PlanError("Q35 relation IDs must be unique.")
        relation_ids.add(relation["id"])
    actual_relations = {
        item["fact"]: (item["from"], item["to"])
        for item in plan["relations"]
    }
    if actual_relations != expected_relations:
        raise PlanError("Q35 relations must follow the reviewed Member → OfficeHolding → NamedOffice path.")

    constraints = plan["constraints"]
    expected_constraint_count = 2 if member_bound else 1
    if not isinstance(constraints, list) or len(constraints) != expected_constraint_count:
        raise PlanError("Q35 requires one inclusive interval and, only for person-bound routes, one exact Member-identity constraint.")
    interval_constraints = [item for item in constraints if isinstance(item, dict) and item.get("field") == "interval"]
    identity_constraints = [item for item in constraints if isinstance(item, dict) and item.get("field") == "memberIdentity"]
    if len(interval_constraints) != 1 or len(identity_constraints) != (1 if member_bound else 0):
        raise PlanError("Q35 constraints must contain exactly the interval and reviewed Member-identity binding.")
    if (constraints[0] is not interval_constraints[0]
            or member_bound and constraints[1] is not identity_constraints[0]):
        raise PlanError("Q35 constraints must be ordered as interval first, followed by exact Member identity when present.")
    constraint = interval_constraints[0]
    if (not isinstance(constraint, dict)
            or set(constraint) != {"referent", "field", "operator", "value"}
            or constraint.get("referent") != "holding"
            or constraint.get("field") != "interval"
            or constraint.get("operator") != "overlaps"):
        raise PlanError("Q35 constraint must apply inclusive overlap to the OfficeHolding interval.")
    interval = constraint.get("value")
    if (not isinstance(interval, dict) or set(interval) != {"start", "end", "inclusive"}
            or interval.get("inclusive") is not True):
        raise PlanError("Q35 requires an explicitly inclusive calendar-date interval.")
    try:
        if (not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", interval["start"])
                or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", interval["end"])):
            raise ValueError("not a YYYY-MM-DD calendar date")
        start = date.fromisoformat(interval["start"])
        end = date.fromisoformat(interval["end"])
    except (TypeError, ValueError) as error:
        raise PlanError("Q35 interval boundaries must be valid ISO calendar dates.") from error
    if start > end:
        raise PlanError("Q35 interval start must be on or before its end.")
    if member_bound:
        identity = identity_constraints[0]
        definition = _CONSTRAINT_MAPPINGS.get("memberIdentity", {})
        if (definition.get("referentType") != "Member"
                or definition.get("operator") != "equals"
                or definition.get("valueKind") != "local_resource_iri"
                or definition.get("graphFamily") != "member-records"
                or not isinstance(identity, dict)
                or set(identity) != {"referent", "field", "operator", "value"}
                or identity.get("referent") != "member"
                or identity.get("operator") != "equals"
                or identity.get("value") != member["iri"]):
            raise PlanError("Q35 exact Member binding must match the resolved person-role Member IRI.")
        _require_local_iri(identity["value"], "Member identity constraint")

    expected_answer = {
        "kind": "entities", "referent": "member", "distinctBy": "identity",
        "display": ["name"],
        "details": [{"referent": "holding", "display": ["start", "end"]}],
        "preserveEpisodes": True,
    }
    if plan["answer"] != expected_answer:
        raise PlanError("Q35 answer must return distinct Members with each separate holding's start and end dates.")
    return plan


def _validate_bill_sponsorship_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate only the approved Member → BillParticipation → Bill path."""
    refs = plan["referents"]
    if set(refs) != {"member", "participation", "bill"}:
        raise PlanError("Q23 requires exactly Member, BillParticipation, and Bill referents.")

    member = refs["member"]
    if not isinstance(member, dict) or member.get("type") != "Member":
        raise PlanError("Q23 requires a named Member referent.")
    allowed_member_fields = {
        "unresolved": {"type", "mention", "resolution"},
        "resolved": {"type", "mention", "resolution", "iri", "label"},
        "ambiguous": {"type", "mention", "resolution", "candidates"},
        "not_found": {"type", "mention", "resolution"},
        "source_data_unavailable": {"type", "mention", "resolution"},
        "unsupported_mapping": {"type", "mention", "resolution"},
    }
    resolution = member.get("resolution")
    if (not isinstance(resolution, str) or resolution not in allowed_member_fields
            or set(member) != allowed_member_fields[resolution]):
        raise PlanError("Q23 Member referent contains unsupported or missing resolution attributes.")
    if not isinstance(member.get("mention"), str) or not member["mention"].strip():
        raise PlanError("Q23 requires a non-empty Member mention.")
    if resolution == "resolved":
        _require_local_iri(member["iri"], "Member")
        if not isinstance(member["label"], str) or not member["label"].strip():
            raise PlanError("A resolved Q23 Member requires its reviewed local label.")
    elif resolution == "ambiguous":
        candidates = member["candidates"]
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise PlanError("An ambiguous Q23 Member requires at least two local candidates.")
        for candidate in candidates:
            if (not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}
                    or not isinstance(candidate["label"], str) or not candidate["label"].strip()):
                raise PlanError("Q23 Member candidates must contain only a local IRI and readable label.")
            _require_local_iri(candidate["iri"], "Member candidate")

    if refs["participation"] != {"type": "BillParticipation"}:
        raise PlanError("Q23 requires a plain BillParticipation evidence referent.")
    if refs["bill"] != {"type": "Bill", "answer": True}:
        raise PlanError("Q23 must return Bill identities as its answer referent.")

    expected_relations = {
        "bill_has_sponsor_participation": ("bill", "participation"),
        "participation_has_participant": ("participation", "member"),
    }
    relations = plan["relations"]
    if not isinstance(relations, list) or len(relations) != len(expected_relations):
        raise PlanError("Q23 requires exactly the reviewed Bill sponsorship and participant relationships.")
    relation_ids: set[str] = set()
    actual_relations: dict[str, tuple[str, str]] = {}
    for relation in relations:
        if (not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}
                or any(not isinstance(relation[field], str) or not relation[field]
                       for field in ("id", "fact", "from", "to"))):
            raise PlanError("Q23 relations require non-empty IDs, reviewed facts, and referent IDs only.")
        if relation["id"] in relation_ids or relation["fact"] in actual_relations:
            raise PlanError("Q23 relationship IDs and reviewed facts must be unique.")
        relation_ids.add(relation["id"])
        if relation["fact"] not in _RELATION_TYPES:
            raise PlanError(f"Unsupported semantic mapping: {relation['fact']!r}.")
        if relation["from"] not in refs or relation["to"] not in refs:
            raise PlanError("Q23 relationship refers to an unknown referent.")
        subject_type, object_type = _RELATION_TYPES[relation["fact"]]
        if (refs[relation["from"]]["type"], refs[relation["to"]]["type"]) != (subject_type, object_type):
            raise PlanError(f"Invalid referent types for relationship {relation['fact']!r}.")
        actual_relations[relation["fact"]] = (relation["from"], relation["to"])
    if actual_relations != expected_relations:
        raise PlanError("Q23 relations must follow Bill → sponsor participation → Member.")

    expected_answer = {
        "kind": "entities", "referent": "bill", "distinctBy": "identity",
        "display": ["englishTitle", "billNumber", "year", "officialLink"],
        "details": [{"referent": "participation", "display": ["role", "primaryEvidence"]}],
        "order": ["year", "billNumber"], "preserveEvidence": True,
    }
    if plan["answer"] != expected_answer:
        raise PlanError(
            "Q23 must return distinct Bills with English title and optional metadata, "
            "preserving each participation's role and primary-status evidence."
        )
    return plan


def _validate_shared_dail_terms_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate the exact v2 two-Member/shared-Dáil-term composition."""
    if set(plan) != {"version", "asOf", "family", "referents", "relations", "answer"}:
        raise PlanError(
            "The shared-Dáil-term family does not accept filters, constraints, or extra plan fields."
        )
    if plan.get("family") != "shared_dail_terms":
        raise PlanError("Unsupported shared-term plan family.")
    if not isinstance(plan.get("referents"), dict):
        raise PlanError("Shared-Dáil-term referents must be an object.")

    refs = plan["referents"]
    member_ids = [key for key, value in refs.items()
                  if isinstance(value, dict) and value.get("type") == "Member"]
    membership_ids = [key for key, value in refs.items()
                      if isinstance(value, dict) and value.get("type") == "DailMembership"]
    term_ids = [key for key, value in refs.items()
                if isinstance(value, dict) and value.get("type") == "DailTerm"]
    if (len(refs) != 5 or len(member_ids) != 2
            or len(membership_ids) != 2 or len(term_ids) != 1):
        raise PlanError(
            "Shared-Dáil-term plans require exactly two Member, two DailMembership, and one DailTerm referent."
        )

    member_mentions: list[str] = []
    for member_id in member_ids:
        member = refs[member_id]
        if not isinstance(member_id, str) or not member_id or not isinstance(member, dict):
            raise PlanError("Member referent IDs and values must be valid.")
        resolution = member.get("resolution")
        allowed_fields = {
            "unresolved": {"type", "mention", "resolution"},
            "resolved": {"type", "mention", "resolution", "iri", "label"},
            "ambiguous": {"type", "mention", "resolution", "candidates"},
            "not_found": {"type", "mention", "resolution"},
            "source_data_unavailable": {"type", "mention", "resolution"},
            "unsupported_mapping": {"type", "mention", "resolution"},
        }
        if (not isinstance(resolution, str) or resolution not in allowed_fields
                or set(member) != allowed_fields[resolution]):
            raise PlanError(f"Member referent {member_id!r} has invalid resolution fields.")
        mention = member.get("mention")
        if not isinstance(mention, str) or not mention.strip():
            raise PlanError("Each shared-term Member requires its exact name mention.")
        member_mentions.append(unicodedata.normalize("NFC", mention).casefold())
        if resolution == "resolved":
            _require_local_iri(member["iri"], "Member")
            if not isinstance(member["label"], str) or not member["label"].strip():
                raise PlanError("A resolved Member requires its local display label.")
        elif resolution == "ambiguous":
            candidates = member["candidates"]
            if not isinstance(candidates, list) or len(candidates) < 2:
                raise PlanError("An ambiguous Member requires at least two local candidates.")
            if any(
                not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}
                or not isinstance(candidate["label"], str) or not candidate["label"].strip()
                for candidate in candidates
            ):
                raise PlanError("Ambiguous Member candidates must contain local IRIs and labels.")
            for candidate in candidates:
                _require_local_iri(candidate["iri"], "Member candidate")
            if len({candidate["iri"] for candidate in candidates}) != len(candidates):
                raise PlanError("Ambiguous Member candidates must have distinct RDF identities.")
        elif "iri" in member or "candidates" in member:
            raise PlanError("An unresolved Member cannot carry a selected or candidate IRI.")
    if member_mentions[0] == member_mentions[1]:
        raise PlanError("The two Member referents must be independently named.")

    for membership_id in membership_ids:
        if not isinstance(membership_id, str) or not membership_id or refs[membership_id] != {"type": "DailMembership"}:
            raise PlanError("Each DailMembership referent must be a plain typed evidence role.")
    term_id = term_ids[0]
    if (not isinstance(term_id, str) or not term_id
            or refs[term_id] != {"type": "DailTerm", "answer": True}):
        raise PlanError("The shared DailTerm must be the typed answer referent.")

    if not isinstance(plan.get("relations"), list) or len(plan["relations"]) != 4:
        raise PlanError("Both Members require a complete typed path to the shared DailTerm.")
    actual_edges: list[tuple[str, str, str]] = []
    relation_ids: set[str] = set()
    for relation in plan["relations"]:
        if (not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}
                or any(not isinstance(relation.get(field), str) or not relation[field]
                       for field in ("id", "fact", "from", "to"))):
            raise PlanError("Shared-term relationships require non-empty v2 relation fields only.")
        if relation["id"] in relation_ids:
            raise PlanError("Shared-term relation IDs must be unique.")
        relation_ids.add(relation["id"])
        fact = relation["fact"]
        if fact not in _RELATION_TYPES:
            raise PlanError(f"Unsupported semantic mapping: {fact!r}.")
        if fact not in {"member_has_membership", "membership_in_term"}:
            raise PlanError(f"Relationship {fact!r} is outside the shared-Dáil-term family.")
        source, target = relation["from"], relation["to"]
        if source not in refs or target not in refs:
            raise PlanError("Shared-term relationship references an undeclared referent.")
        if (refs[source]["type"], refs[target]["type"]) != _RELATION_TYPES[fact]:
            raise PlanError(f"Relationship {fact!r} has incompatible typed referents.")
        actual_edges.append((fact, source, target))

    expected_edges: list[tuple[str, str, str]] = []
    used_memberships: set[str] = set()
    for member_id in member_ids:
        linked = [edge for edge in actual_edges
                  if edge[0] == "member_has_membership" and edge[1] == member_id]
        if len(linked) != 1:
            raise PlanError(f"Member {member_id!r} must have exactly one independent membership edge.")
        membership_id = linked[0][2]
        if refs[membership_id]["type"] != "DailMembership" or membership_id in used_memberships:
            raise PlanError("Each Member requires a separate DailMembership referent.")
        used_memberships.add(membership_id)
        expected_edges.extend([
            ("member_has_membership", member_id, membership_id),
            ("membership_in_term", membership_id, term_id),
        ])
    if sorted(actual_edges) != sorted(expected_edges):
        raise PlanError(
            "Both membership paths must converge on the same answer DailTerm resource identity."
        )

    expected_answer = {
        "kind": "entities", "referent": term_id, "distinctBy": "identity",
        "display": ["label"],
    }
    if plan.get("answer") != expected_answer:
        raise PlanError("Shared-Dáil-term answers must return distinct DailTerm identities and labels.")
    return plan


def _validate_member_party_composition_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate the shared term/constituency/party episode temporal graph."""
    if set(plan) != {"version", "asOf", "family", "referents", "relations", "constraints", "answer"}:
        raise PlanError("Dated party/representation composition requires its fixed temporal constraint and no extra fields.")
    refs = plan.get("referents")
    expected_types = {
        "member": "Member", "membership": "DailMembership", "term": "DailTerm",
        "constituency": "DailConstituency", "episode": "PartyMembershipEpisode",
        "party": "ParliamentaryParty", "affiliation": "PoliticalAffiliationIdentity",
    }
    if not isinstance(refs, dict) or set(refs) != set(expected_types):
        raise PlanError("Dated party/representation composition requires exactly seven reviewed referents.")
    answer = plan.get("answer")
    if not isinstance(answer, dict) or answer.get("kind") != "entities":
        raise PlanError("Dated party/representation composition requires an entity answer.")
    answer_ref = answer.get("referent")
    party_answer = answer_ref == "affiliation"
    if answer_ref not in {"member", "affiliation"}:
        raise PlanError("The composition must answer either Member identities or reviewed political-affiliation identities.")

    for key, semantic_type in expected_types.items():
        ref = refs[key]
        if not isinstance(ref, dict) or ref.get("type") != semantic_type:
            raise PlanError(f"Referent {key!r} must have reviewed type {semantic_type!r}.")
    expected_member = {"type": "Member"} if party_answer else {"type": "Member", "answer": True}
    if refs["member"] != expected_member:
        raise PlanError("The Member answer role does not match the selected composition projection.")
    for key in ("membership", "episode", "party"):
        if refs[key] != {"type": expected_types[key]}:
            raise PlanError(f"Referent {key!r} must be a plain typed evidence role.")

    term = refs["term"]
    selector = term.get("selector")
    if (not isinstance(selector, dict)
            or selector != {"kind": "termNumber", "number": selector.get("number")}
            or type(selector.get("number")) is not int or not 1 <= selector["number"] <= 999):
        raise PlanError("The DailTerm must use one reviewed numeric term selector.")
    term_resolution = term.get("resolution")
    if term_resolution is None:
        if set(term) != {"type", "selector"}:
            raise PlanError("An unresolved DailTerm contains unsupported fields.")
    elif term_resolution == "resolved":
        if set(term) != {"type", "selector", "resolution", "iri"}:
            raise PlanError("A resolved DailTerm must carry its exact local identity only.")
        _require_local_iri(term["iri"], "DailTerm")
    elif term_resolution in {"ambiguous", "not_found", "source_data_unavailable", "unsupported_mapping"}:
        if term_resolution == "ambiguous":
            if set(term) != {"type", "selector", "resolution", "candidates"} or not isinstance(term["candidates"], list) or len(term["candidates"]) < 2:
                raise PlanError("An ambiguous DailTerm requires distinct local identity candidates.")
            for candidate in term["candidates"]:
                if not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}:
                    raise PlanError("DailTerm candidates must contain local identities and labels.")
                _require_local_iri(candidate["iri"], "DailTerm candidate")
        elif set(term) != {"type", "selector", "resolution"}:
            raise PlanError("Unavailable DailTerm resolution contains unsupported identity fields.")
    else:
        raise PlanError("DailTerm resolution state is outside the reviewed outcomes.")

    constituency = refs["constituency"]
    constituency_states = {
        "unresolved": {"type", "mention", "resolution"},
        "resolved": {"type", "mention", "resolution", "iri", "label"},
        "ambiguous": {"type", "mention", "resolution", "candidates"},
        "not_found": {"type", "mention", "resolution"},
        "source_data_unavailable": {"type", "mention", "resolution"},
        "unsupported_mapping": {"type", "mention", "resolution"},
    }
    state = constituency.get("resolution")
    if (state not in constituency_states or set(constituency) != constituency_states[state]
            or not isinstance(constituency.get("mention"), str) or not constituency["mention"].strip()):
        raise PlanError("DailConstituency resolution fields or exact mention are invalid.")
    if state == "resolved":
        _require_local_iri(constituency["iri"], "DailConstituency")
        if not isinstance(constituency["label"], str) or not constituency["label"].strip():
            raise PlanError("A resolved DailConstituency requires its local label.")
    if state == "ambiguous":
        candidates = constituency["candidates"]
        if not isinstance(candidates, list) or len(candidates) < 2:
            raise PlanError("Ambiguous constituency resolution requires distinct candidates.")
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}:
                raise PlanError("Constituency candidates must contain local identities and labels.")
            _require_local_iri(candidate["iri"], "DailConstituency candidate")

    affiliation = refs["affiliation"]
    if party_answer:
        if affiliation != {"type": "PoliticalAffiliationIdentity", "answer": True}:
            raise PlanError("A party-list answer must return distinct reviewed affiliation identities.")
    else:
        affiliation_states = {
            "unresolved": {"type", "mention", "resolution"},
            "resolved": {"type", "mention", "resolution", "iri", "label"},
            "ambiguous": {"type", "mention", "resolution", "candidates"},
            "not_found": {"type", "mention", "resolution"},
            "source_data_unavailable": {"type", "mention", "resolution"},
            "unsupported_mapping": {"type", "mention", "resolution"},
        }
        affiliation_state = affiliation.get("resolution")
        if (affiliation_state not in affiliation_states
                or set(affiliation) != affiliation_states[affiliation_state]
                or not isinstance(affiliation.get("mention"), str) or not affiliation["mention"].strip()):
            raise PlanError("The named PoliticalAffiliationIdentity requires a valid resolution state and mention.")
        if affiliation_state == "resolved":
            _require_local_iri(affiliation["iri"], "PoliticalAffiliationIdentity")
            if not isinstance(affiliation["label"], str) or not affiliation["label"].strip():
                raise PlanError("A resolved PoliticalAffiliationIdentity requires its reviewed local label.")
        if affiliation_state == "ambiguous":
            candidates = affiliation["candidates"]
            if not isinstance(candidates, list) or len(candidates) < 2:
                raise PlanError("Ambiguous affiliation resolution requires distinct identity candidates.")
            for candidate in candidates:
                if not isinstance(candidate, dict) or set(candidate) != {"iri", "label"}:
                    raise PlanError("Affiliation candidates must contain local identities and labels.")
                _require_local_iri(candidate["iri"], "PoliticalAffiliationIdentity candidate")

    relations = plan.get("relations")
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
    if not isinstance(relations, list) or len(relations) != len(expected_edges):
        raise PlanError("The temporal party composition requires every reviewed relation exactly once.")
    relation_defs = {item["id"]: item for item in _PLAN_CONTRACT["relations"]}
    actual_edges: dict[str, tuple[str, str]] = {}
    relation_ids: set[str] = set()
    for relation in relations:
        if (not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}
                or any(not isinstance(relation.get(field), str) or not relation[field]
                       for field in ("id", "fact", "from", "to"))):
            raise PlanError("Temporal composition relations require non-empty IDs and typed endpoints.")
        if relation["id"] in relation_ids or relation["fact"] in actual_edges:
            raise PlanError("Temporal composition relation IDs and facts must be unique.")
        relation_ids.add(relation["id"])
        fact = relation["fact"]
        if fact not in _RELATION_TYPES:
            raise PlanError(f"Unsupported semantic mapping: {fact!r}.")
        edge = (relation["from"], relation["to"])
        if fact not in expected_edges or edge != expected_edges[fact]:
            raise PlanError(f"Relationship {fact!r} is outside the exact party/representation composition.")
        if (expected_types[edge[0]], expected_types[edge[1]]) != _RELATION_TYPES[fact]:
            raise PlanError(f"Relationship {fact!r} has incompatible typed referents.")
        actual_edges[fact] = edge
    if actual_edges != expected_edges:
        raise PlanError("The temporal party graph is disconnected or missing an essential relationship.")

    constraint_mapping = _CONSTRAINT_MAPPINGS.get("partyEpisodeInterval")
    expected_constraint = {
        "referent": "episode", "field": "partyEpisodeInterval", "operator": "overlaps", "value": "membership",
    }
    if (constraint_mapping is None
            or constraint_mapping.get("referentType") != "PartyMembershipEpisode"
            or constraint_mapping.get("otherReferentType") != "DailMembership"
            or constraint_mapping.get("valueKind") != "referent_interval"
            or constraint_mapping.get("dateDatatype") != "xsd:dateTime"
            or constraint_mapping.get("startRequiredByMapping") is not True
            or constraint_mapping.get("endAbsentMeans") != "open-ended"
            or constraint_mapping.get("rangeOrStartAbsentMeans") != "uncertain"
            or constraint_mapping.get("boundary") != "inclusive_endpoint"
            or plan.get("constraints") != [expected_constraint]):
        raise PlanError("The required inclusive PartyMembershipEpisode/DailMembership interval-overlap constraint is absent or inconsistent.")

    if answer == {
        "kind": "entities", "referent": "affiliation", "distinctBy": "identity", "display": ["label"],
        "details": [
            {"referent": "member", "display": ["name"]},
            {"referent": "episode", "display": ["start", "end"]},
            {"referent": "membership", "display": ["start", "end"]},
        ],
        "preserveEvidence": True,
    }:
        if not party_answer:
            raise PlanError("Party-list answers must target PoliticalAffiliationIdentity.")
    elif answer == {
        "kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
        "details": [
            {"referent": "affiliation", "display": ["label"]},
            {"referent": "episode", "display": ["start", "end"]},
            {"referent": "membership", "display": ["start", "end"]},
        ],
        "preserveEvidence": True,
    }:
        if party_answer:
            raise PlanError("Named-party Member answers must preserve the exact affiliation filter.")
    else:
        raise PlanError("Temporal party answers must preserve exact identity and separate interval evidence.")
    return plan


def _validate_member_relationship_composition_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate the bounded Member–membership–Dáil-term graph projections."""
    if "constraints" in plan and any(
        isinstance(ref, dict) and ref.get("type") == "PartyMembershipEpisode"
        for ref in (plan.get("referents", {}).values() if isinstance(plan.get("referents"), dict) else ())
    ):
        return _validate_member_party_composition_plan(plan)
    allowed_fields = {
        frozenset({"version", "asOf", "family", "referents", "relations", "answer"}),
        frozenset({"version", "asOf", "family", "referents", "relations", "constraints", "answer"}),
    }
    if frozenset(plan) not in allowed_fields:
        raise PlanError("Member relationship composition does not accept extra constraints or plan fields.")
    if "constraints" in plan and plan["constraints"] != []:
        raise PlanError("Non-party Member relationship composition does not accept extra constraints.")
    if plan.get("family") != "member_relationship_composition":
        raise PlanError("Unsupported Member relationship composition family.")
    refs = plan.get("referents")
    if not isinstance(refs, dict) or not 4 <= len(refs) <= 5:
        raise PlanError("Member relationship composition requires one Member and a complete supported graph.")

    members: list[str] = []
    memberships: list[str] = []
    terms: list[str] = []
    constituencies: list[str] = []
    for referent_id, ref in refs.items():
        if (not isinstance(referent_id, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", referent_id)
                or not isinstance(ref, dict) or not isinstance(ref.get("type"), str)):
            raise PlanError("Every Member composition referent requires a safe ID and controlled type.")
        semantic_type = ref["type"]
        if semantic_type == "Member":
            if ref != {"type": "Member", "answer": True}:
                raise PlanError("The composition must return one set-valued Member answer referent.")
            members.append(referent_id)
        elif semantic_type == "DailMembership":
            if ref != {"type": "DailMembership"}:
                raise PlanError("DailMembership referents are plain relationship evidence roles.")
            memberships.append(referent_id)
        elif semantic_type == "DailTerm":
            selector = ref.get("selector")
            if (not isinstance(selector, dict)
                    or selector != {"kind": "termNumber", "number": selector.get("number")}
                    or type(selector.get("number")) is not int
                    or not 1 <= selector["number"] <= 999):
                raise PlanError("Each DailTerm must use one reviewed numeric term selector.")
            resolution = ref.get("resolution")
            if resolution is None:
                if set(ref) != {"type", "selector"}:
                    raise PlanError("An unresolved DailTerm contains unsupported fields.")
            elif resolution == "resolved":
                if set(ref) != {"type", "selector", "resolution", "iri"}:
                    raise PlanError("A resolved DailTerm requires only its exact selector and local IRI.")
                _require_local_iri(ref["iri"], "DailTerm")
            elif resolution in {"ambiguous", "not_found", "source_data_unavailable", "unsupported_mapping"}:
                if resolution == "ambiguous":
                    if set(ref) != {"type", "selector", "resolution", "candidates"}:
                        raise PlanError("An ambiguous DailTerm requires explicit local identity candidates.")
                    candidates = ref["candidates"]
                    if (not isinstance(candidates, list) or len(candidates) < 2
                            or any(not isinstance(item, dict) or set(item) != {"iri", "label"}
                                   or not isinstance(item["label"], str) or not item["label"].strip()
                                   for item in candidates)):
                        raise PlanError("DailTerm candidates must preserve distinct local identities and labels.")
                    for item in candidates:
                        _require_local_iri(item["iri"], "DailTerm candidate")
                elif set(ref) != {"type", "selector", "resolution"}:
                    raise PlanError("An unavailable DailTerm contains unsupported identity fields.")
            else:
                raise PlanError("DailTerm resolution state is outside the reviewed outcomes.")
            terms.append(referent_id)
        elif semantic_type == "DailConstituency":
            resolution = ref.get("resolution")
            allowed_fields = {
                "unresolved": {"type", "mention", "resolution"},
                "resolved": {"type", "mention", "resolution", "iri", "label"},
                "ambiguous": {"type", "mention", "resolution", "candidates"},
                "not_found": {"type", "mention", "resolution"},
                "source_data_unavailable": {"type", "mention", "resolution"},
                "unsupported_mapping": {"type", "mention", "resolution"},
            }
            if (not isinstance(resolution, str) or resolution not in allowed_fields
                    or set(ref) != allowed_fields[resolution]
                    or not isinstance(ref.get("mention"), str) or not ref["mention"].strip()):
                raise PlanError("DailConstituency referent has invalid resolution fields or mention.")
            if resolution == "resolved":
                _require_local_iri(ref["iri"], "DailConstituency")
                if not isinstance(ref["label"], str) or not ref["label"].strip():
                    raise PlanError("A resolved DailConstituency requires its local display label.")
            if resolution == "ambiguous":
                candidates = ref["candidates"]
                if (not isinstance(candidates, list) or len(candidates) < 2
                        or any(not isinstance(item, dict) or set(item) != {"iri", "label"}
                               or not isinstance(item["label"], str) or not item["label"].strip()
                               for item in candidates)):
                    raise PlanError("Ambiguous constituency candidates must preserve local identities and labels.")
                for item in candidates:
                    _require_local_iri(item["iri"], "DailConstituency candidate")
            constituencies.append(referent_id)
        else:
            raise PlanError(f"Referent type {semantic_type!r} is outside Member relationship composition.")

    if len(members) != 1:
        raise PlanError("Member relationship composition requires exactly one Member answer referent.")
    ordinals = [refs[term_id]["selector"]["number"] for term_id in terms]
    if len(set(ordinals)) != len(ordinals):
        raise PlanError("Distinct DailTerm referents must select distinct term ordinals.")
    if not isinstance(plan.get("relations"), list):
        raise PlanError("Member composition relations must be a list.")
    relation_ids: set[str] = set()
    actual_edges: list[tuple[str, str, str]] = []
    for relation in plan["relations"]:
        if (not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}
                or any(not isinstance(relation[field], str) or not relation[field]
                       for field in ("id", "fact", "from", "to"))):
            raise PlanError("Member composition relations require controlled IDs and endpoints.")
        if relation["id"] in relation_ids:
            raise PlanError("Member composition relation IDs must be unique.")
        relation_ids.add(relation["id"])
        fact = relation["fact"]
        if fact not in _RELATION_TYPES:
            raise PlanError(f"Unsupported semantic mapping: {fact!r}.")
        if fact not in {
            "member_has_membership", "membership_in_term",
            "membership_represents", "constituency_in_term",
        }:
            raise PlanError(f"Relationship {fact!r} is outside Member relationship composition.")
        source, target = relation["from"], relation["to"]
        if source not in refs or target not in refs:
            raise PlanError("Member composition relation references an undeclared referent.")
        if (refs[source]["type"], refs[target]["type"]) != _RELATION_TYPES[fact]:
            raise PlanError(f"Relationship {fact!r} has incompatible typed referents.")
        actual_edges.append((fact, source, target))

    expected_edges: list[tuple[str, str, str]] = []
    member_id = members[0]
    if len(terms) == 2 and len(memberships) == 2 and not constituencies:
        expected_edges.extend(
            ("member_has_membership", member_id, membership_id)
            for membership_id in memberships
        )
        paths: dict[str, str] = {}
        for fact, source, target in actual_edges:
            if fact == "membership_in_term":
                if source in paths:
                    raise PlanError("Each DailMembership must link to exactly one selected DailTerm.")
                paths[source] = target
        if set(paths) != set(memberships) or set(paths.values()) != set(terms):
            raise PlanError("Each independent membership must link to a different selected DailTerm.")
        expected_edges.extend(("membership_in_term", membership, term) for membership, term in paths.items())
    elif len(terms) == 1 and len(memberships) == 1 and len(constituencies) == 1:
        membership, term, constituency = memberships[0], terms[0], constituencies[0]
        expected_edges = [
            ("member_has_membership", member_id, membership),
            ("membership_in_term", membership, term),
            ("membership_represents", membership, constituency),
            ("constituency_in_term", constituency, term),
        ]
    else:
        raise PlanError("Plan must be one Member in two terms or one term-scoped constituency representation graph.")
    if sorted(actual_edges) != sorted(expected_edges):
        raise PlanError("The Member relationship graph is disconnected, incomplete, or contains extra edges.")

    answer = plan.get("answer")
    if answer != {
        "kind": "entities", "referent": member_id,
        "distinctBy": "identity", "display": ["name"],
    }:
        raise PlanError("The composition must return distinct Member identities with their local names.")

    resolved_term_iris = [refs[term_id].get("iri") for term_id in terms
                          if refs[term_id].get("resolution") == "resolved"]
    if resolved_term_iris and len(resolved_term_iris) != len(terms):
        raise PlanError("DailTerm identities must be resolved consistently before compilation.")
    if len(set(resolved_term_iris)) != len(resolved_term_iris):
        raise PlanError("Different selected term ordinals cannot resolve to the same DailTerm identity.")
    return plan


def _require_local_iri(value: str, what: str) -> str:
    if (not isinstance(value, str) or not value.startswith("https://data.oireachtas.ie/")
            or any(character.isspace() for character in value) or any(mark in value for mark in "<>\"{}|\\^`")):
        raise NLQError(f"Resolved {what} is not a local Oireachtas resource IRI.")
    return value


def _normalise_label(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in value).split())


def plan_question(question: str, *, as_of: date) -> dict[str, Any]:
    """Interpret the bounded composable query question families."""
    bill_sponsorship = re.search(
        r"\bwhich\s+bills?\s+did\s+(?P<member>.+?)\s+sponsor\s*[?.!]*$",
        question.strip(), re.IGNORECASE,
    )
    if bill_sponsorship:
        member_name = re.sub(r"[?.!]+$", "", bill_sponsorship.group("member")).strip()
        if not member_name:
            raise PlanError("A Member name is required for the Bill sponsorship question.")
        return validate_plan({
            "version": PLAN_VERSION,
            "asOf": as_of.isoformat(),
            "referents": {
                "member": {"type": "Member", "mention": member_name, "resolution": "unresolved"},
                "participation": {"type": "BillParticipation"},
                "bill": {"type": "Bill", "answer": True},
            },
            "relations": [
                {"id": "bill-sponsorship", "fact": "bill_has_sponsor_participation",
                 "from": "bill", "to": "participation"},
                {"id": "participation-member", "fact": "participation_has_participant",
                 "from": "participation", "to": "member"},
            ],
            "answer": {
                "kind": "entities", "referent": "bill", "distinctBy": "identity",
                "display": ["englishTitle", "billNumber", "year", "officialLink"],
                "details": [{"referent": "participation", "display": ["role", "primaryEvidence"]}],
                "order": ["year", "billNumber"], "preserveEvidence": True,
            },
        })

    office_window = re.search(
        r"\bwho\s+was\s+(?P<office>.+?)\s+from\s+"
        r"(?P<start_month>[a-z]+)\s+(?P<start_year>[0-9]{4})\s+to\s+"
        r"(?P<end_month>[a-z]+)\s+(?P<end_year>[0-9]{4})\s*[?.!]*$",
        question.strip(), re.IGNORECASE,
    )
    if office_window:
        office = office_window.group("office").strip()
        try:
            start_month = datetime.strptime(office_window.group("start_month"), "%B").month
            end_month = datetime.strptime(office_window.group("end_month"), "%B").month
            start = date(int(office_window.group("start_year")), start_month, 1)
            end = date(
                int(office_window.group("end_year")), end_month,
                calendar.monthrange(int(office_window.group("end_year")), end_month)[1],
            )
        except (ValueError, OverflowError) as error:
            raise PlanError("The requested office interval must use valid English month and year values.") from error
        if not office:
            raise PlanError("A reviewed office name is required.")
        if start > end:
            raise PlanError("The requested office interval must start on or before it ends.")
        return validate_plan({
            "version": PLAN_VERSION,
            "asOf": as_of.isoformat(),
            "referents": {
                "member": {"type": "Member", "answer": True},
                "holding": {"type": "OfficeHolding"},
                "office": {"type": "NamedOffice", "mention": office, "resolution": "unresolved"},
            },
            "relations": [
                {"id": "member-holding", "fact": "member_has_office_holding", "from": "member", "to": "holding"},
                {"id": "holding-office", "fact": "office_holding_of_office", "from": "holding", "to": "office"},
            ],
            "constraints": [{
                "referent": "holding", "field": "interval", "operator": "overlaps",
                "value": {"start": start.isoformat(), "end": end.isoformat(), "inclusive": True},
            }],
            "answer": {
                "kind": "entities", "referent": "member", "distinctBy": "identity",
                "display": ["name"],
                "details": [{"referent": "holding", "display": ["start", "end"]}],
                "preserveEpisodes": True,
            },
        })
    debate = re.search(
        r"\b(?P<boolean>was\s+there\s+a\s+)?(?P<chamber>dáil|dail|seanad)\s+debate\s+(?:on|from)\s+(?P<date>[0-9]{1,2}\s+[a-z]+\s+[0-9]{4})\s*[?.!]*$",
        question.strip(), re.IGNORECASE,
    )
    if debate:
        try:
            debate_date = datetime.strptime(debate.group("date"), "%d %B %Y").date().isoformat()
        except ValueError as error:
            raise PlanError("The debate date must be a valid calendar date.") from error
        chamber = "seanad" if debate.group("chamber").casefold() == "seanad" else "dail"
        return validate_plan({
            "version": PLAN_VERSION,
            "asOf": as_of.isoformat(),
            "referents": {
                "sitting": {"type": "DebateSitting", "answer": True},
                "record": {"type": "DebateRecord"},
            },
            "relations": [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}],
            "constraints": [
                {"referent": "sitting", "field": "date", "operator": "on", "value": debate_date},
                {"referent": "record", "field": "chamber", "operator": "equals", "value": chamber},
            ],
            "answer": ({"kind": "boolean", "referent": "sitting"} if debate.group("boolean") else
                       {"kind": "entities", "referent": "sitting", "distinctBy": "identity", "display": ["date", "officialLink"]}),
        })
    affiliation = re.search(
        r"\bwhat\s+parties\s+was\s+(.+?)\s+a\s+member\s+of\s*[?.!]*$",
        question.strip(), re.IGNORECASE,
    )
    if affiliation:
        member_name = re.sub(r"[?.!]+$", "", affiliation.group(1)).strip()
        if not member_name:
            raise PlanError("A Member name is required for the party-membership question.")
        return validate_plan({
            "version": PLAN_VERSION,
            "asOf": as_of.isoformat(),
            "referents": {
                "member": {"type": "Member", "mention": member_name, "resolution": "unresolved"},
                "episode": {"type": "PartyMembershipEpisode"},
                "party": {"type": "ParliamentaryParty"},
                "affiliation": {"type": "PoliticalAffiliationIdentity", "answer": True},
            },
            "relations": [
                {"id": "member-party-episode", "fact": "member_party_membership", "from": "member", "to": "episode"},
                {"id": "episode-party", "fact": "episode_in_parliamentary_party", "from": "episode", "to": "party"},
                {"id": "party-affiliation", "fact": "parliamentary_party_has_affiliation_identity", "from": "party", "to": "affiliation"},
            ],
            "answer": {"kind": "entities", "referent": "affiliation", "distinctBy": "identity", "display": ["label"],
                       "details": [{"referent": "episode", "display": ["start", "end"]}], "preserveGaps": True},
        })
    match = re.search(
        r"\b(?:tds?\s+for|represented)\s+(.+?)\s+in\s+the\s+"
        r"(?:last|previous)\s+dáil\b",
        question.strip(), re.IGNORECASE,
    )
    if not match:
        raise UnrecognizedQuestion("No deterministic composable family recognized this question.")
    constituency = re.sub(r"[?.!]+$", "", match.group(1)).strip()
    if not constituency:
        raise PlanError("A constituency name is required.")
    return validate_plan({
        "version": PLAN_VERSION,
        "asOf": as_of.isoformat(),
        "referents": {
            "term": {"type": "DailTerm", "selector": {"kind": "previousTerm", "house": "Dail"}},
            "constituency": {"type": "DailConstituency", "mention": constituency},
            "membership": {"type": "DailMembership"},
            "member": {"type": "Member", "answer": True},
        },
        "relations": [
            {"id": "constituency-term", "fact": "constituency_in_term", "from": "constituency", "to": "term"},
            {"id": "member-membership", "fact": "member_has_membership", "from": "member", "to": "membership"},
            {"id": "membership-term", "fact": "membership_in_term", "from": "membership", "to": "term"},
            {"id": "membership-constituency", "fact": "membership_represents", "from": "membership", "to": "constituency"},
        ],
        "answer": {"kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"]},
    })


def validate_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict) or set(plan) not in ({"version", "asOf", "referents", "relations", "answer"},
                                                       {"version", "asOf", "referents", "relations", "constraints", "answer"},
                                                       {"version", "asOf", "family", "referents", "relations", "answer"},
                                                       {"version", "asOf", "family", "referents", "relations", "constraints", "answer"}):
        raise PlanError("Plan must have exactly version, asOf, referents, relations, optional constraints, and answer.")
    if plan["version"] != PLAN_VERSION:
        raise PlanError("Unsupported composable plan version.")
    try:
        date.fromisoformat(plan["asOf"])
    except (TypeError, ValueError) as error:
        raise PlanError("asOf must be an ISO calendar date.") from error
    refs = plan["referents"]
    if not isinstance(refs, dict) or not refs:
        raise PlanError("referents must be a non-empty object.")
    for key, ref in refs.items():
        if not isinstance(key, str) or not key or not isinstance(ref, dict) or not isinstance(ref.get("type"), str):
            raise PlanError("Every referent requires an ID and controlled type.")
        if ref["type"] not in _PLAN_CONTRACT["entityTypes"]:
            raise PlanError(f"Unsupported referent type {ref['type']!r}.")
    if "family" in plan:
        if not isinstance(plan["family"], str):
            raise PlanError("Query family must be a controlled string identifier.")
        from .stage_b import _B_FAMILIES, validate_stage_b_plan
        if plan["family"] in _B_FAMILIES:
            return validate_stage_b_plan(plan)
        from .stage_c import _C_FAMILIES, validate_stage_c_plan
        if plan["family"] in _C_FAMILIES:
            return validate_stage_c_plan(plan)
        if plan["family"] == "shared_dail_terms":
            return _validate_shared_dail_terms_plan(plan)
        if plan["family"] == "member_relationship_composition":
            return _validate_member_relationship_composition_plan(plan)
        return _validate_stage_a_plan(plan)
    if any(ref.get("type") in {"DebateRecord", "DebateSitting"} for ref in refs.values()):
        return _validate_debate_plan(plan)
    if "constraints" in plan:
        return _validate_office_plan(plan)
    if any(ref.get("type") in {"Bill", "BillParticipation"} for ref in refs.values()):
        return _validate_bill_sponsorship_plan(plan)
    term = refs.get("term", {})
    constituency = refs.get("constituency", {})
    is_q09 = "term" in refs or "constituency" in refs
    if is_q09 and (term.get("type") != "DailTerm"
            or term.get("selector") != {"kind": "previousTerm", "house": "Dail"}
            or constituency.get("type") != "DailConstituency"
            or not isinstance(constituency.get("mention"), str)
            or not constituency["mention"].strip()):
        raise PlanError("Q09 requires a previous-Dáil selector and a named term-scoped constituency.")
    if not is_q09 and (
        refs.get("member", {}).get("type") != "Member"
        or not refs.get("member", {}).get("mention")
        or refs.get("episode", {}).get("type") != "PartyMembershipEpisode"
        or refs.get("party", {}).get("type") != "ParliamentaryParty"
        or refs.get("affiliation", {}).get("type") != "PoliticalAffiliationIdentity"
    ):
        raise PlanError("Q06 requires a named Member, dated membership episode, parliamentary party and enduring affiliation identity.")
    if not isinstance(plan["relations"], list) or not plan["relations"]:
        raise PlanError("relations must be a non-empty list.")
    seen = set()
    for relation in plan["relations"]:
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise PlanError("Relations require exactly id, fact, from, and to.")
        if any(not isinstance(relation[field], str) or not relation[field]
               for field in ("id", "fact", "from", "to")):
            raise PlanError("Relation IDs, facts, and referent IDs must be non-empty strings.")
        if relation["id"] in seen:
            raise PlanError("Relation IDs must be unique.")
        seen.add(relation["id"])
        if relation["fact"] not in _RELATION_TYPES:
            raise PlanError(f"Unsupported semantic mapping: {relation['fact']!r}.")
        if relation["from"] not in refs or relation["to"] not in refs:
            raise PlanError("Relation refers to an unknown referent.")
        subject_type, object_type = _RELATION_TYPES[relation["fact"]]
        if (refs[relation["from"]]["type"], refs[relation["to"]]["type"]) != (subject_type, object_type):
            raise PlanError(f"Invalid referent types for relation {relation['fact']!r}.")
    q09_relations = {
        "constituency_in_term": ("constituency", "term"),
        "member_has_membership": ("member", "membership"),
        "membership_in_term": ("membership", "term"),
        "membership_represents": ("membership", "constituency"),
    }
    q06_relations = {
        "member_party_membership": ("member", "episode"),
        "episode_in_parliamentary_party": ("episode", "party"),
        "parliamentary_party_has_affiliation_identity": ("party", "affiliation"),
    }
    actual_relations = {relation["fact"]: (relation["from"], relation["to"])
                        for relation in plan["relations"]}
    answer = plan["answer"]
    if actual_relations == q09_relations:
        if len(plan["relations"]) != len(q09_relations):
            raise PlanError("Q09 compiler cannot faithfully compile additional or repeated relationships.")
        if (not isinstance(answer, dict) or answer.get("kind") != "entities"
                or answer.get("referent") not in refs or refs[answer["referent"]]["type"] != "Member"
                or answer.get("distinctBy") != "identity" or answer.get("display") != ["name"]):
            raise PlanError("Q09 answer must return distinct Member identities with readable names.")
    elif actual_relations == q06_relations:
        if len(plan["relations"]) != len(q06_relations):
            raise PlanError("Q06 compiler cannot faithfully compile additional or repeated relationships.")
        if set(refs) != {"member", "episode", "party", "affiliation"}:
            raise PlanError("Q06 compiler cannot faithfully compile unconnected or additional referents.")
        if (not isinstance(answer, dict) or answer.get("kind") != "entities"
                or answer.get("referent") != "affiliation" or refs["affiliation"]["type"] != "PoliticalAffiliationIdentity"
                or answer.get("distinctBy") != "identity" or answer.get("display") != ["label"]
                or answer.get("preserveGaps") is not True
                or set(answer) != {"kind", "referent", "distinctBy", "display", "details", "preserveGaps"}
                or answer.get("details") != [{"referent": "episode", "display": ["start", "end"]}]):
            raise PlanError("Q06 answer must return distinct reviewed affiliation identities and preserve episode gaps.")
    elif is_q09:
        expected = q09_relations
        if len(plan["relations"]) != len(expected):
            raise PlanError("Q09 compiler cannot faithfully compile additional or repeated relationships.")
        raise PlanError("Q09 compiler cannot faithfully compile disconnected or non-Q09 relationships.")
    else:
        if len(plan["relations"]) != len(q06_relations):
            raise PlanError("Q06 compiler cannot faithfully compile additional or repeated relationships.")
        raise PlanError("Accepted plan relations do not match a complete supported Q06 or Q09 path.")
    return plan


def _validate_stage_a_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Closed validation for Stage A family plans before any query executes."""
    families = {
        "member_lookup": ({"member"}, "Member", {"family_result"}),
        "previous_service": ({"member"}, "Member", {"family_result"}),
        "dail_duration": ({"member"}, "Member", {"family_result"}),
        "term_count": ({"member", "term"}, "DailTerm", {"count", "family_result"}),
        "seanad_entry": ({"member"}, "Member", {"family_result"}),
        "seanad_representation": ({"member"}, "Member", {"family_result"}),
        "current_collection": ({"member"}, "Member", {"family_result"}),
        "committee_boolean": ({"member"}, "Member", {"family_result"}),
        "committee_count": ({"member"}, "Member", {"family_result"}),
        "house_terms": ({"term"}, "DailTerm", {"values"}),
        "dail_all": ({"member"}, "Member", {"family_result"}),
    }
    family = plan.get("family")
    if family not in families:
        raise PlanError("Unsupported closed Stage A query family.")
    required_refs, required_type, answer_kinds = families[family]
    refs = plan["referents"]
    optional_committee = family in {"committee_boolean", "committee_count"} and set(refs) in (
        {"member", "committeeMembership", "committee"},
        {"member", "committeeMembership", "committee", "term"},
    )
    term_count_member = family == "term_count" and refs.get("member", {}).get("type") == "Member"
    term_count_total = family == "term_count" and set(refs) == {"term"}
    member_paths = {
        "previous_service": {"member", "membership", "term"},
        "dail_duration": {"member", "membership", "term"},
        "dail_all": {"member", "membership", "term"},
        "seanad_entry": {"member", "membership", "term"},
        "seanad_representation": {"member", "membership", "term", "representation"},
        "current_collection": {"member", "collectionMembership", "collection"},
    }
    supported_member_path = family in member_paths and set(refs) == member_paths[family]
    if family == "term_count":
        supported_member_path = term_count_member and set(refs) == {"member", "membership", "term"}
    if set(refs) != required_refs and not optional_committee and not supported_member_path and not term_count_member and not term_count_total:
        raise PlanError("Stage A family contains missing or unrelated referents.")
    exact_types = {
        "previous_service": {"member": "Member", "membership": "DailMembership", "term": "DailTerm"},
        "dail_duration": {"member": "Member", "membership": "DailMembership", "term": "DailTerm"},
        "dail_all": {"member": "Member", "membership": "DailMembership", "term": "DailTerm"},
        "term_count_member": {"member": "Member", "membership": "DailMembership", "term": "DailTerm"},
        "seanad_entry": {"member": "Member", "membership": "SeanadMembership", "term": "SeanadTerm"},
        "seanad_representation": {"member": "Member", "membership": "SeanadMembership", "term": "SeanadTerm", "representation": "SeanadRepresentation"},
        "current_collection": {"member": "Member", "collectionMembership": "ParliamentaryCollectionMembership", "collection": "ParliamentaryMemberCollection"},
        "committee_count": {"member": "Member", "committeeMembership": "CommitteeMembership", "committee": "Committee"},
        "committee_boolean": {"member": "Member", "committeeMembership": "CommitteeMembership", "committee": "Committee"},
    }
    expected_types = exact_types.get("term_count_member" if term_count_member else family)
    if family == "committee_boolean" and "term" in refs:
        expected_types = {**expected_types, "term": refs["term"].get("type")}
        if expected_types["term"] not in {"DailTerm", "SeanadTerm"}:
            raise PlanError("Committee term must be a reviewed HouseTerm type.")
    if expected_types and (set(refs) != set(expected_types) or any(refs[key].get("type") != value for key, value in expected_types.items())):
        raise PlanError("Stage A family referents do not match the exact reviewed path types.")
    primary_key = "member" if "member" in refs else "term"
    primary = refs[primary_key]
    if set(primary) - {"type", "mention", "answer", "resolution", "iri", "label", "asOfEvidence", "candidates"}:
        raise PlanError("Stage A referent contains unsupported identity fields.")
    if primary.get("type") != ("Member" if term_count_member else required_type):
        raise PlanError("Stage A referent has the wrong reviewed entity type.")
    for key, ref in refs.items():
        if key == primary_key:
            continue
        if not isinstance(ref, dict) or set(ref) - {"type", "iri", "label", "mention", "resolution", "candidates", "answer", "selector"}:
            raise PlanError("Stage A auxiliary referent contains unsupported fields.")
        if not isinstance(ref.get("type"), str) or ref["type"] not in _PLAN_CONTRACT["entityTypes"]:
            raise PlanError("Stage A auxiliary referent type is not reviewed.")
        if "iri" in ref:
            _require_local_iri(ref["iri"], "Stage A referent")
        if "label" in ref and not isinstance(ref["label"], str):
            raise PlanError("Stage A referent label must be a string.")
    if "member" in refs:
        if not isinstance(primary.get("mention"), str) or not primary["mention"].strip():
            raise PlanError("Stage A Member referent requires a grounded mention.")
        if primary.get("resolution") not in {"resolved", "ambiguous", "not_found", "source_data_unavailable", "unsupported_mapping"}:
            raise PlanError("Stage A Member resolution outcome is invalid.")
        candidates = primary.get("candidates", [])
        if not isinstance(candidates, list) or any(not isinstance(item, dict) or set(item) != {"iri", "label"}
                or not isinstance(item["iri"], str) or not isinstance(item["label"], str) for item in candidates):
            raise PlanError("Stage A candidate set is malformed.")
        if len({item["iri"] for item in candidates}) != len(candidates):
            raise PlanError("Stage A candidates must have distinct RDF identities.")
        for item in candidates:
            _require_local_iri(item["iri"], "Stage A entity candidate")
        if primary["resolution"] == "resolved" and (len(candidates) != 1 or primary.get("iri") != candidates[0]["iri"]):
            raise PlanError("Resolved Stage A identity must retain exactly its one candidate IRI.")
        if primary["resolution"] == "ambiguous" and len(candidates) < 2:
            raise PlanError("Ambiguous Stage A identity requires at least two candidates.")
        if primary["resolution"] == "ambiguous" and "iri" in primary:
            raise PlanError("Ambiguous Stage A identity cannot carry a singular selected IRI.")
        if primary["resolution"] in {"not_found", "source_data_unavailable", "unsupported_mapping"} and (candidates or "iri" in primary):
            raise PlanError("Unresolved Stage A identity cannot carry a selected or candidate IRI.")
    if optional_committee:
        committee = refs["committee"]
        if set(committee) - {"type", "mention", "resolution", "iri", "label", "candidates"} or committee.get("type") != "Committee":
            raise PlanError("Committee referent contains unsupported or inconsistent fields.")
        if committee.get("resolution") not in {None, "resolved", "ambiguous", "not_found", "source_data_unavailable"}:
            raise PlanError("Committee resolution outcome is invalid.")
        committee_candidates = committee.get("candidates", [])
        if (not isinstance(committee_candidates, list)
                or any(not isinstance(item, dict) or set(item) != {"iri", "label"}
                       or not isinstance(item["iri"], str) or not isinstance(item["label"], str)
                       for item in committee_candidates)
                or len({item["iri"] for item in committee_candidates}) != len(committee_candidates)):
            raise PlanError("Committee candidate set is malformed or contains duplicate identities.")
        for item in committee_candidates:
            _require_local_iri(item["iri"], "Committee candidate")
        if committee.get("resolution") == "ambiguous" and (len(committee_candidates) < 2 or "iri" in committee):
            raise PlanError("Ambiguous Committee resolution requires candidates and cannot select one IRI.")
        if committee.get("resolution") == "resolved" and (not isinstance(committee.get("iri"), str) or not isinstance(committee.get("label"), str)):
            raise PlanError("Resolved Committee referent must retain its owner IRI and label.")
        if committee.get("resolution") == "resolved":
            _require_local_iri(committee["iri"], "Committee")
        elif committee.get("resolution") in {"ambiguous", "not_found", "source_data_unavailable"} and "iri" in committee:
            raise PlanError("Unresolved Committee identity cannot carry a selected IRI.")
    facts = []
    if not isinstance(plan["relations"], list):
            raise PlanError("Stage A relations must be a closed list.")
    if plan["relations"]:
        seen_ids = set()
        for relation in plan["relations"]:
            if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
                raise PlanError("Stage A relation edges require exactly id, fact, from, and to.")
            if not all(isinstance(relation[key], str) and relation[key] for key in relation):
                raise PlanError("Stage A relation fields must be non-empty strings.")
            if relation["id"] in seen_ids or relation["from"] not in refs or relation["to"] not in refs:
                raise PlanError("Stage A relation IDs must be unique and endpoints must exist.")
            seen_ids.add(relation["id"])
            mapping = _RELATION_MAPPINGS.get(relation["fact"])
            if mapping is None or (refs[relation["from"]]["type"], refs[relation["to"]]["type"]) != _RELATION_TYPES[relation["fact"]]:
                raise PlanError("Stage A relation does not match its reviewed typed mapping.")
            facts.append(relation["fact"])
    expected_facts = {
        "member_lookup": [], "dail_all": ["member_has_membership", "membership_in_term"],
        "previous_service": ["member_has_membership", "membership_in_term"],
        "dail_duration": ["member_has_membership", "membership_in_term"],
        "term_count": (["member_has_membership", "membership_in_term"] if term_count_member else []),
        "seanad_entry": ["member_has_seanad_membership", "seanad_membership_in_term"],
        "seanad_representation": ["member_has_seanad_membership", "seanad_membership_in_term", "seanad_membership_represents_resource"],
        "current_collection": ["member_has_collection_membership", "collection_membership_of_collection"],
        "committee_boolean": ["member_has_committee_membership", "committee_membership_of_committee", "committee_in_term"],
        "committee_count": ["member_has_committee_membership", "committee_membership_of_committee"],
        "house_terms": [],
    }
    if family == "committee_boolean" and refs.get("term", {}).get("type") == "SeanadTerm":
        expected_facts[family] = ["member_has_committee_membership", "committee_membership_of_committee", "committee_in_seanad_term"]
    if facts != expected_facts[family]:
        raise PlanError("Stage A family relation path does not match the closed reviewed pattern.")
    if len(facts) != len(set(facts)):
        raise PlanError("Stage A relation paths cannot repeat an edge.")
    expected_endpoints = {
        "member_has_membership": ("member", "membership"),
        "membership_in_term": ("membership", "term"),
        "member_has_seanad_membership": ("member", "membership"),
        "seanad_membership_in_term": ("membership", "term"),
        "seanad_membership_represents_resource": ("membership", "representation"),
        "member_has_collection_membership": ("member", "collectionMembership"),
        "collection_membership_of_collection": ("collectionMembership", "collection"),
        "member_has_committee_membership": ("member", "committeeMembership"),
        "committee_membership_of_committee": ("committeeMembership", "committee"),
        "committee_in_term": ("committee", "term"),
        "committee_in_seanad_term": ("committee", "term"),
    }
    for relation in plan["relations"]:
        if (relation["from"], relation["to"]) != expected_endpoints[relation["fact"]]:
            raise PlanError("Stage A relation endpoints do not form the reviewed family path.")
    declared_families = {item["id"]: item for item in _PLAN_CONTRACT.get("questionFamilies", [])}
    family_contract = declared_families.get(family)
    if family_contract is None:
        raise PlanError("Stage A family has no reviewed question-family contract entry.")
    for fact in facts:
        relation_mapping = _RELATION_MAPPINGS[fact]
        if relation_mapping.get("patternId") not in family_contract["patterns"]:
            raise PlanError("Stage A relation is not covered by the family's reviewed emitted patterns.")
    if "constraints" in plan:
        raise PlanError("Stage A family plans do not accept free-form constraints.")
    answer = plan["answer"]
    if not isinstance(answer, dict) or answer.get("kind") not in answer_kinds or set(answer) != {"kind", "referent"}:
        if not (family == "term_count" and answer == {"kind": "count", "referent": "term", "distinctBy": "identity"}):
            if not (family == "house_terms" and answer == {"kind": "values", "referent": "term"}):
                raise PlanError("Stage A answer shape does not match its closed family contract.")
    expected_ref = "member" if "member" in refs else "term"
    if answer.get("referent") != expected_ref:
        raise PlanError("Stage A answer must target its family referent.")
    return plan


def _query(text: str, supported_predicates) -> str:
    return validate_sparql(text, supported_predicates=supported_predicates)


def _reviewed_predicate(fact: str) -> str:
    mapping = _RELATION_MAPPINGS.get(fact)
    if mapping is None:
        raise PlanError(f"No reviewed relation mapping exists for {fact!r}.")
    contract = load_query_contract()
    if mapping["predicate"] not in contract["queryableProperties"]:
        raise PlanError(f"Reviewed predicate {mapping['predicate']!r} is not queryable in the contract.")
    graph_families = {family["id"] for family in contract["graphFamilies"]}
    if mapping["subjectGraph"] not in graph_families or mapping["objectGraph"] not in graph_families:
        raise PlanError(f"Relation {fact!r} names an unknown graph owner.")
    if mapping["subjectGraph"] != mapping["objectGraph"] and not any(
        item["fromGraphFamily"] == mapping["subjectGraph"]
        and item["toGraphFamily"] == mapping["objectGraph"]
        and item["predicate"] == mapping["predicate"]
        for item in contract["crossGraphJoins"]
    ):
        raise PlanError(f"Relation {fact!r} has no reviewed cross-graph join.")
    return mapping["predicate"]


def _reviewed_predicate_for_qname(predicate: str) -> str:
    if predicate not in load_query_contract()["queryableProperties"]:
        raise PlanError(f"Reviewed predicate {predicate!r} is not queryable in the contract.")
    return predicate


def _reviewed_pattern(pattern_id: str, family_id: str) -> dict[str, Any]:
    contract = load_query_contract()
    pattern = next((item for item in contract["emittedRdfPatterns"] if item["id"] == pattern_id), None)
    if (pattern is None or pattern.get("graphFamily") != family_id
            or pattern.get("availability") != "emitted"
            or pattern.get("queryableInLocalNlq") is not True):
        raise PlanError(f"Reviewed queryable RDF pattern {pattern_id!r} is absent or unavailable.")
    return pattern


def _pattern_predicate(pattern: dict[str, Any], subject: str, object_: str) -> str:
    predicate = next((triple[1] for triple in pattern.get("triples", [])
                      if triple[0] == subject and triple[2] == object_), None)
    if not isinstance(predicate, str):
        raise PlanError(f"Reviewed pattern {pattern.get('id')!r} has no requested relationship.")
    if predicate != "rdf:type":
        _reviewed_predicate_for_qname(predicate)
    return predicate


def _pattern_rdf_type(pattern: dict[str, Any], subject: str) -> str:
    rdf_type = next((triple[2] for triple in pattern.get("triples", [])
                     if triple[0] == subject and triple[1] == "rdf:type"), None)
    if not isinstance(rdf_type, str):
        raise PlanError(f"Reviewed pattern {pattern.get('id')!r} has no asserted type for {subject!r}.")
    if rdf_type not in load_query_contract()["queryableClasses"]:
        raise PlanError(f"Reviewed RDF type {rdf_type!r} is not queryable.")
    return rdf_type


def _reviewed_cross_graph_join(from_family: str, predicate: str, to_family: str) -> None:
    contract = load_query_contract()
    if not any(item["fromGraphFamily"] == from_family and item["predicate"] == predicate
               and item["toGraphFamily"] == to_family for item in contract["crossGraphJoins"]):
        raise PlanError(f"No reviewed {from_family} to {to_family} cross-graph join exists for {predicate!r}.")


def _bill_sponsorship_query_mapping(plan: dict[str, Any]) -> dict[str, str]:
    """Resolve Q23 sponsorship through the explicit BillDelivery/Work/process path."""
    plan = validate_plan(plan)
    if not any(ref.get("type") == "BillParticipation" for ref in plan["referents"].values()):
        raise PlanError("Bill sponsorship compilation requires a validated Q23 plan.")
    member = plan["referents"]["member"]
    if member.get("resolution") != "resolved":
        raise PlanError("Bill sponsorship compilation requires one resolved local Member identity.")
    member_iri = _require_local_iri(member.get("iri"), "Member")

    relation_mappings = {item["id"]: item for item in _PLAN_CONTRACT["relations"]}
    ownership = relation_mappings.get("bill_has_sponsor_participation", {})
    participant_join = relation_mappings.get("participation_has_participant", {})
    if (ownership.get("association") != "bill_delivery_process_path"
            or ownership.get("viaType") != "eli-dl:LegislativeProcess"
            or ownership.get("patternId") != "bill-sponsor-reference"
            or ownership.get("subjectGraph") != "bill-records"
            or ownership.get("objectGraph") != "bill-records"
            or participant_join.get("patternId") != "bill-sponsor-reference"
            or participant_join.get("predicate") != "eli-dl:had_participant_person"
            or participant_join.get("subjectGraph") != "bill-records"
            or participant_join.get("objectGraph") != "member-records"
            or participant_join.get("joinKey") != "same RDF resource IRI"):
        raise PlanError("Q23 sponsorship relations disagree with the reviewed graph-ownership mapping.")

    contract = load_query_contract()
    bill_family = next((item for item in contract["graphFamilies"] if item["id"] == "bill-records"), None)
    if (not bill_family or bill_family["graph"].get("kind") != "resource-pattern"
            or bill_family["graph"].get("iriTemplate") !=
            "https://data.oireachtas.ie/graph/bill/{year}/{number}"):
        raise PlanError("Q23 requires the reviewed one-Bill named-graph route.")
    route_pattern = "^" + re.escape(bill_family["graph"]["iriTemplate"]) + "$"
    route_pattern = route_pattern.replace(re.escape("{year}"), r"[0-9]{4}")
    route_pattern = route_pattern.replace(re.escape("{number}"), r"[^/]+")

    lifecycle = _reviewed_pattern("bill-lifecycle", "bill-records")
    sponsor = _reviewed_pattern("bill-sponsor-reference", "bill-records")
    member_pattern = _reviewed_pattern("member-description", "member-records")
    rdf_types = _PLAN_CONTRACT["entityTypeRdfTypes"]
    bill_type = _pattern_rdf_type(lifecycle, "?bill")
    process_type = _pattern_rdf_type(sponsor, "?process")
    delivery_type = _pattern_rdf_type(sponsor, "?delivery")
    delivery_work = _pattern_predicate(sponsor, "?delivery", "?bill")
    delivery_process = _pattern_predicate(sponsor, "?delivery", "?process")
    if (delivery_type != "agents:BillDelivery"
            or delivery_work != "eli-dl:created_a_realization_of"
            or delivery_process != "eli-dl:forms_part_of"):
        raise PlanError("Q23 requires the explicit BillDelivery Work/process relationship.")
    participation_type = _pattern_rdf_type(sponsor, "?participation")
    member_type = _pattern_rdf_type(member_pattern, "?member")
    for semantic_type, actual in (
        ("Bill", bill_type), ("BillParticipation", participation_type), ("Member", member_type),
    ):
        if rdf_types.get(semantic_type) != actual or actual not in contract["queryableClasses"]:
            raise PlanError(f"Reviewed RDF type for {semantic_type!r} is absent or inconsistent.")
    if process_type != "eli-dl:LegislativeProcess" or process_type not in contract["queryableClasses"]:
        raise PlanError("The reviewed sponsorship process type is absent or inconsistent.")

    bill_kind = _pattern_predicate(lifecycle, "?bill", "agents:Bill")
    bill_year = _pattern_predicate(lifecycle, "?bill", "?year")
    bill_title = _pattern_predicate(lifecycle, "?bill", "?englishOrIrishTitle")
    process_number = _pattern_predicate(lifecycle, "?process", "?processNumber")
    process_participation = _pattern_predicate(sponsor, "?process", "?participation")
    participant = _pattern_predicate(sponsor, "?participation", "?member")
    primary_status = _pattern_predicate(sponsor, "?participation", "?optionalBoolean")
    participation_role = _pattern_predicate(sponsor, "?participation", "?optionalRoleLabel")
    if bill_kind != "eli:type_document" or primary_status != "agents:isPrimarySponsor":
        raise PlanError("Q23 Bill-kind or primary-sponsor mappings disagree with the emitted RDF contract.")
    if _reviewed_predicate("participation_has_participant") != participant:
        raise PlanError("The participant identity join disagrees with the emitted Bill sponsorship pattern.")
    _reviewed_cross_graph_join("bill-records", participant, "member-records")

    labels = contract["labelsByEntityType"].get("Bill", {})
    if (labels.get("predicate") != bill_title or "en" not in labels.get("languages", [])
            or bill_title != "eli:title"):
        raise PlanError("Q23 requires the reviewed English Bill short-title mapping.")
    for predicate in (bill_year, process_number, primary_status, participation_role):
        _reviewed_predicate_for_qname(predicate)

    query_relations = {item["fact"]: (item["from"], item["to"]) for item in plan["relations"]}
    if query_relations != {
        "bill_has_sponsor_participation": ("bill", "participation"),
        "participation_has_participant": ("participation", "member"),
    }:
        raise PlanError("Q23 compilation requires the complete Bill sponsorship path.")
    return {
        "member_iri": member_iri,
        "bill_type": bill_type,
        "bill_kind": bill_kind,
        "process_type": process_type,
        "delivery_type": delivery_type,
        "delivery_work": delivery_work,
        "delivery_process": delivery_process,
        "process_participation": process_participation,
        "participation_type": participation_type,
        "participant": participant,
        "primary_status": primary_status,
        "participation_role": participation_role,
        "bill_title": bill_title,
        "bill_number": process_number,
        "bill_year": bill_year,
        "bill_graph_route": route_pattern,
    }


def compile_bill_sponsorship_answer_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Compile the reviewed Bill-graph sponsorship evidence for one Member IRI."""
    mapping = _bill_sponsorship_query_mapping(plan)
    member_iri = URIRef(mapping["member_iri"]).n3()
    query = _PREFIXES + f'''SELECT DISTINCT ?billGraph ?bill ?participation ?primaryEvidence ?participationRole ?englishTitle ?billNumber ?billYear WHERE {{
  GRAPH ?billGraph {{
    ?bill a {mapping["bill_type"]} ; {mapping["bill_kind"]} agents:Bill .
    ?delivery a {mapping["delivery_type"]} ; {mapping["delivery_work"]} ?bill ; {mapping["delivery_process"]} ?process .
    ?process a {mapping["process_type"]} ; {mapping["process_participation"]} ?participation .
    ?participation a {mapping["participation_type"]} ; {mapping["participant"]} {member_iri} .
    OPTIONAL {{ ?participation {mapping["primary_status"]} ?primaryEvidence . }}
    OPTIONAL {{ ?participation {mapping["participation_role"]} ?participationRole . }}
    OPTIONAL {{ ?bill {mapping["bill_title"]} ?englishTitle . FILTER(LANG(?englishTitle) = "en") }}
    OPTIONAL {{ ?process {mapping["bill_number"]} ?billNumber . }}
    OPTIONAL {{ ?bill {mapping["bill_year"]} ?billYear . }}
  }}
  FILTER(REGEX(STR(?billGraph), {json.dumps(mapping["bill_graph_route"])}))
}} ORDER BY ?billYear ?billNumber ?bill ?participation ?primaryEvidence ?participationRole ?englishTitle'''
    return _query(query, supported_predicates)


def compile_bill_sponsorship_coverage_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Distinguish absent Bill sponsorship evidence from no match for this Member."""
    mapping = _bill_sponsorship_query_mapping(plan)
    query = _PREFIXES + f'''SELECT (COUNT(DISTINCT ?bill) AS ?billCount) (COUNT(DISTINCT ?participation) AS ?participationCount) WHERE {{
  GRAPH ?billGraph {{
    ?bill a {mapping["bill_type"]} ; {mapping["bill_kind"]} agents:Bill .
    OPTIONAL {{
      ?delivery a {mapping["delivery_type"]} ; {mapping["delivery_work"]} ?bill ; {mapping["delivery_process"]} ?process .
      ?process a {mapping["process_type"]} ; {mapping["process_participation"]} ?participation .
      ?participation a {mapping["participation_type"]} .
    }}
  }}
  FILTER(REGEX(STR(?billGraph), {json.dumps(mapping["bill_graph_route"])}))
}}'''
    return _query(query, supported_predicates)


def previous_dail_term_query(as_of: date, *, supported_predicates) -> str:
    """Select term/date evidence; ordering and previous-term selection are Python semantics."""
    contract = load_query_contract()
    temporal = _PLAN_CONTRACT["relativeTerm"]["dateMapping"]
    graph = next(item["graph"]["iri"] for item in contract["graphFamilies"]
                 if item["id"] == temporal["graphFamily"])
    period_link = _reviewed_predicate_for_qname(temporal["periodLinkPredicate"])
    start_predicate = _reviewed_predicate_for_qname(temporal["startPredicate"])
    end_predicate = _reviewed_predicate_for_qname(temporal["endPredicate"])
    query = _PREFIXES + f'''SELECT ?term ?start ?end WHERE {{
  GRAPH <{graph}> {{
    ?term a agents:DailTerm ; {period_link} ?period .
    ?period {start_predicate} ?start .
    OPTIONAL {{ ?period {end_predicate} ?end . }}
  }}
}}'''
    return _query(query, supported_predicates)


def _date_binding(value: str) -> date:
    if "^^" in value and "^^<http://www.w3.org/2001/XMLSchema#dateTime>" not in value and "^^<http://www.w3.org/2001/XMLSchema#date>" not in value:
        raise NLQError("House-term date evidence has no reviewed xsd:date/dateTime datatype; no term was selected.")
    try:
        lexical = value.split("^^", 1)[0]
        if "@" in lexical:
            lexical = lexical.rsplit("@", 1)[0]
        return datetime.fromisoformat(lexical.replace("Z", "+00:00")).date()
    except ValueError as error:
        raise NLQError("House-term date evidence is malformed; no term was selected.") from error


def resolve_previous_dail(result: QueryResult, as_of: date) -> tuple[str, str]:
    rows: dict[str, tuple[date, date | None]] = {}
    for row in result.rows:
        if len(row) < 3:
            raise NLQError("House-term query returned malformed date evidence.")
        iri, start_text, end_text = row[:3]
        _require_local_iri(iri, "HouseTerm")
        start = _date_binding(start_text)
        end = _date_binding(end_text) if end_text not in {"—", ""} else None
        if iri in rows and rows[iri] != (start, end):
            raise NLQError("Conflicting House-term date evidence; no term was selected.")
        rows[iri] = (start, end)
    active = [iri for iri, (start, end) in rows.items() if start <= as_of and (end is None or as_of <= end)]
    if len(active) != 1:
        raise NLQError("Source data does not identify exactly one current Dáil term for the supplied as-of date.")
    current_start = rows[active[0]][0]
    earlier = [(start, iri, end) for iri, (start, end) in rows.items() if start < current_start]
    if not earlier:
        raise NLQError("Source data does not include a previous Dáil term.")
    start, iri, end = max(earlier, key=lambda item: (item[0], item[1]))
    if end is None or end >= current_start:
        raise NLQError("House-term dates overlap or are incomplete; previous Dáil cannot be determined safely.")
    return iri, active[0]


def constituency_resolution_query(mention: str, term_iri: str, *, supported_predicates) -> str:
    if not term_iri.startswith("https://data.oireachtas.ie/"):
        raise NLQError("Resolved term IRI is outside the local Oireachtas namespace.")
    # Resolve in the requested term, not against an enduring series or labels alone.
    graph = next(item["graph"]["iri"] for item in load_query_contract()["graphFamilies"]
                 if item["id"] == "constituencies")
    occurrence_predicate = _reviewed_predicate("constituency_in_term")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?constituency ?label WHERE {{
  GRAPH <{graph}> {{
    ?constituency a members:DailConstituency ; skos:prefLabel ?label ;
      {occurrence_predicate} <{term_iri}> .
  }}
}}''', supported_predicates)


def resolve_constituency(
    result: QueryResult,
    mention: str,
    *,
    term_label: str = "the previous Dáil",
) -> tuple[str, str]:
    wanted = _normalise_label(mention)
    candidates: dict[str, str] = {}
    for row in result.rows:
        if len(row) < 2:
            continue
        iri, label = row[:2]
        _require_local_iri(iri, "constituency")
        label = label.removesuffix("@en")
        if _normalise_label(label) == wanted:
            candidates[iri] = label
    if not candidates:
        raise NLQError(f"No matching constituency was found in {term_label} for “{mention}”.")
    if len(candidates) != 1:
        raise AmbiguousConstituency(
            mention,
            tuple({"iri": iri, "label": candidates[iri]} for iri in sorted(candidates)),
            term_label=term_label,
        )
    iri = next(iter(candidates))
    return iri, candidates[iri]


class AmbiguousConstituency(NLQError):
    def __init__(
        self,
        mention: str,
        candidates: tuple[dict[str, str], ...],
        *,
        term_label: str = "the previous Dáil",
    ):
        super().__init__(f"Several constituencies named “{mention}” exist in {term_label}.")
        self.candidates = candidates


def dail_term_ordinal_resolution_query(ordinal: int, *, supported_predicates) -> str:
    """Resolve one typed DailTerm using the reviewed HouseTerm ordinal pattern."""
    if type(ordinal) is not int or not 1 <= ordinal <= 999:
        raise PlanError("Dáil term ordinal must be an integer from 1 through 999.")
    contract = load_query_contract()
    family = next(
        (item for item in contract["graphFamilies"] if item.get("id") == "houses"), None,
    )
    graph = family.get("graph", {}) if family else {}
    if (not family or family.get("owner") != "Houses ETL"
            or graph.get("kind") != "fixed" or graph.get("iri") != "https://data.oireachtas.ie/graph/houses"):
        raise PlanError("Reviewed Houses graph ownership is unavailable for Dáil term resolution.")
    pattern = _reviewed_pattern("house-term-ordinal", "houses")
    rdf_type = _pattern_rdf_type(pattern, "?term")
    ordinal_predicate = _pattern_predicate(pattern, "?term", "?ordinal")
    reviewed_type = _PLAN_CONTRACT["entityTypeRdfTypes"]["DailTerm"]
    if rdf_type != reviewed_type or ordinal_predicate != "agents:termNo":
        raise PlanError("Reviewed HouseTerm ordinal pattern disagrees with DailTerm semantics.")
    if reviewed_type not in contract["queryableClasses"]:
        raise PlanError("DailTerm is not queryable under the reviewed query contract.")
    number_predicate = _reviewed_predicate_for_qname(ordinal_predicate)
    query = _PREFIXES + f'''SELECT DISTINCT ?term WHERE {{
  GRAPH <{graph["iri"]}> {{
    ?term a {reviewed_type} ; {number_predicate} "{ordinal}"^^xsd:integer .
  }}
}} LIMIT 100'''
    return _query(query, supported_predicates)


def _member_relationship_composition_mapping(
    plan: dict[str, Any],
    *,
    supported_predicates,
) -> dict[str, Any]:
    """Cross-check the reusable Member graph composition against both contracts."""
    plan = validate_plan(plan)
    if plan.get("family") != "member_relationship_composition":
        raise PlanError("Member relationship compilation requires its validated v2 family.")
    temporal = any(
        ref.get("type") == "PartyMembershipEpisode"
        for ref in plan.get("referents", {}).values()
    )
    query_contract = load_query_contract()
    families = {item["id"]: item for item in query_contract["graphFamilies"]}
    member_graph = families.get("member-records", {}).get("graph", {})
    houses_graph = families.get("houses", {}).get("graph", {})
    constituency_graph = families.get("constituencies", {}).get("graph", {})
    party_graph = families.get("parties", {}).get("graph", {})
    identity_graph = families.get("political-affiliations", {}).get("graph", {})
    if (member_graph.get("kind") != "resource-pattern"
            or not isinstance(member_graph.get("iriTemplate"), str)
            or "{" not in member_graph["iriTemplate"]
            or houses_graph.get("kind") != "fixed"
            or constituency_graph.get("kind") != "fixed"):
        raise PlanError("Reviewed Member, Houses, or constituency graph ownership is unavailable.")
    member_prefix = member_graph["iriTemplate"].split("{", 1)[0]
    for family_id, graph, owner in (
        ("houses", houses_graph, "Houses ETL"),
        ("constituencies", constituency_graph, "Constituencies ETL"),
    ):
        family = families.get(family_id, {})
        if family.get("owner") != owner or not isinstance(graph.get("iri"), str):
            raise PlanError(f"Reviewed {owner} graph ownership is malformed.")

    if temporal:
        for family_id, graph, owner in (
            ("parties", party_graph, "Parties ETL"),
            ("political-affiliations", identity_graph, "Reviewed political-affiliation identity enrichment publication"),
        ):
            family = families.get(family_id, {})
            if family.get("owner") != owner or graph.get("kind") != "fixed" or not isinstance(graph.get("iri"), str):
                raise PlanError(f"Reviewed {owner} graph ownership is malformed or unavailable.")

    patterns = {
        "member": _reviewed_pattern("member-description", "member-records"),
        "membership": _reviewed_pattern("member-house-membership", "member-records"),
        "representation": _reviewed_pattern("representation-reference", "member-records"),
        "term": _reviewed_pattern("house-term-ordinal", "houses"),
        "constituency": _reviewed_pattern("constituency-term-occurrence", "constituencies"),
    }
    if temporal:
        patterns.update({
            "party_episode": _reviewed_pattern("party-membership-episode", "member-records"),
            "party_term": _reviewed_pattern("party-term-occurrence", "parties"),
            "identity": _reviewed_pattern("reviewed-political-affiliation-identities", "political-affiliations"),
        })
    rdf_types = _PLAN_CONTRACT["entityTypeRdfTypes"]
    member_type = _pattern_rdf_type(patterns["member"], "?member")
    member_name = _pattern_predicate(patterns["member"], "?member", "?plainLiteralName")
    membership_member_link = _pattern_predicate(patterns["membership"], "?member", "?membership")
    membership_term_link = _pattern_predicate(patterns["membership"], "?membership", "?term")
    representation_link = _pattern_predicate(patterns["representation"], "?membership", "?representation")
    constituency_term_link = _pattern_predicate(patterns["constituency"], "?constituency", "?term")
    term_number_link = _pattern_predicate(patterns["term"], "?term", "?ordinal")
    party_episode_membership = None
    member_party_link = None
    episode_party_link = None
    party_term_link = None
    party_identity_link = None
    if temporal:
        member_party_link = _pattern_predicate(
            patterns["party_episode"], "?member", "?partyEpisode",
        )
        party_episode_membership = _pattern_predicate(
            patterns["party_episode"], "?partyEpisode", "?oireachtasMembership",
        )
        episode_party_link = _pattern_predicate(
            patterns["party_episode"], "?partyEpisode", "?parliamentaryParty",
        )
        party_term_link = _pattern_predicate(patterns["party_term"], "?party", "?term")
        party_identity_link = _pattern_predicate(patterns["identity"], "?party", "?identity")
    constituency_type_candidates = [
        triple[2].split(" and ") for triple in patterns["constituency"].get("triples", [])
        if triple[0] == "?constituency" and triple[1] == "rdf:type"
    ]
    membership_type_candidates = [
        triple[2].split(" or ") for triple in patterns["membership"].get("triples", [])
        if triple[0] == "?membership" and triple[1] == "rdf:type"
    ]
    if (member_type != rdf_types["Member"]
            or member_name != query_contract["labelsByEntityType"]["Member"].get("predicate")
            or membership_member_link != _reviewed_predicate("member_has_membership")
            or membership_term_link != _reviewed_predicate("membership_in_term")
            or representation_link != _reviewed_predicate("membership_represents")
            or constituency_term_link != _reviewed_predicate("constituency_in_term")
            or term_number_link != "agents:termNo"
            or not any(rdf_types["DailMembership"] in items for items in membership_type_candidates)
            or not any(rdf_types["DailConstituency"] in items for items in constituency_type_candidates)
            or _pattern_rdf_type(patterns["term"], "?term") != rdf_types["DailTerm"]):
        raise PlanError("Reviewed RDF patterns disagree with the Member relationship registry.")
    if temporal:
        party_episode_types = [
            triple[2].split(" or ") for triple in patterns["party_episode"].get("triples", [])
            if triple[0] == "?partyEpisode" and triple[1] == "rdf:type"
        ]
        if (not any(rdf_types["PartyMembershipEpisode"] in values for values in party_episode_types)
                or _pattern_rdf_type(patterns["party_term"], "?party") != rdf_types["ParliamentaryParty"]
                or _pattern_rdf_type(patterns["identity"], "?identity") != rdf_types["PoliticalAffiliationIdentity"]
                or member_party_link != _reviewed_predicate("member_party_membership")
                or party_episode_membership != _reviewed_predicate("party_episode_in_membership")
                or episode_party_link != _reviewed_predicate("episode_in_parliamentary_party")
                or party_term_link != _reviewed_predicate("party_active_during_term")
                or party_identity_link != _reviewed_predicate("parliamentary_party_has_affiliation_identity")):
            raise PlanError("Reviewed PartyMembership, term-party, or affiliation-identity patterns disagree with the v2 relation registry.")
    types_to_check = ["Member", "DailMembership", "DailTerm", "DailConstituency"]
    if temporal:
        types_to_check.extend(("PartyMembershipEpisode", "ParliamentaryParty", "PoliticalAffiliationIdentity"))
    for semantic_type in types_to_check:
        if rdf_types[semantic_type] not in query_contract["queryableClasses"]:
            raise PlanError(f"Reviewed RDF type for {semantic_type!r} is not queryable.")
    if member_name not in query_contract["queryableProperties"]:
        raise PlanError("The reviewed Member display-name predicate is not queryable.")

    type_graph = {
        "Member": "member-records",
        "DailMembership": "member-records",
        "DailTerm": "houses",
        "DailConstituency": "constituencies",
    }
    if temporal:
        type_graph.update({
            "PartyMembershipEpisode": "member-records",
            "ParliamentaryParty": "parties",
            "PoliticalAffiliationIdentity": "political-affiliations",
        })
    relations = {item["id"]: item for item in _PLAN_CONTRACT["relations"]}
    for relation in plan["relations"]:
        definition = relations.get(relation["fact"])
        if definition is None:
            raise PlanError(f"No reviewed relationship mapping exists for {relation['fact']!r}.")
        if (definition["subjectGraph"] != type_graph[plan["referents"][relation["from"]]["type"]]
                or definition["objectGraph"] != type_graph[plan["referents"][relation["to"]]["type"]]):
            raise PlanError(f"Relationship {relation['fact']!r} disagrees with referent graph ownership.")
        _reviewed_predicate(relation["fact"])
    expected_predicates = {
        "member_has_membership": membership_member_link,
        "membership_in_term": membership_term_link,
        "membership_represents": representation_link,
        "constituency_in_term": constituency_term_link,
    }
    if temporal:
        expected_predicates.update({
            "member_party_membership": member_party_link,
            "party_episode_in_membership": party_episode_membership,
            "episode_in_parliamentary_party": episode_party_link,
            "party_active_during_term": party_term_link,
            "parliamentary_party_has_affiliation_identity": party_identity_link,
        })
    if any(relations[fact].get("predicate") != predicate for fact, predicate in expected_predicates.items()):
        raise PlanError("Member relationship predicates disagree with the reviewed emitted RDF patterns.")
    for from_family, predicate, to_family in (
        ("member-records", membership_term_link, "houses"),
        ("member-records", representation_link, "constituencies"),
        ("constituencies", constituency_term_link, "houses"),
    ):
        _reviewed_cross_graph_join(from_family, predicate, to_family)

    if temporal:
        for from_family, predicate, to_family in (
            ("parties", party_term_link, "houses"),
            ("parties", party_identity_link, "political-affiliations"),
        ):
            _reviewed_cross_graph_join(from_family, predicate, to_family)
        constraint = _CONSTRAINT_MAPPINGS.get("partyEpisodeInterval")
        party_pattern = patterns["party_episode"]
        membership_range = _pattern_predicate(patterns["membership"], "?membership", "?dateRange")
        member_start = _pattern_predicate(patterns["membership"], "?dateRange", "?startDate")
        member_end = _pattern_predicate(patterns["membership"], "?dateRange", "?endDate (optional)")
        party_range = _pattern_predicate(party_pattern, "?partyEpisode", "?partyDateRange (optional for query projection)")
        party_start = _pattern_predicate(party_pattern, "?partyDateRange", "?affiliationStart (optional)")
        party_end = _pattern_predicate(party_pattern, "?partyDateRange", "?affiliationEnd (optional)")
        member_range_type = _pattern_rdf_type(patterns["membership"], "?dateRange")
        party_range_type = _pattern_rdf_type(party_pattern, "?partyDateRange")
        party_label = _pattern_predicate(patterns["party_term"], "?party", "?englishLabel")
        affiliation_label = _pattern_predicate(patterns["identity"], "?identity", "?englishPreferredLabel")
        affiliation_label_language = query_contract["labelsByEntityType"].get("PoliticalAffiliationIdentity", {}).get("language")
        if (constraint is None or constraint.get("referentType") != "PartyMembershipEpisode"
                or constraint.get("otherReferentType") != "DailMembership"
                or constraint.get("valueKind") != "referent_interval"
                or constraint.get("dateDatatype") != "xsd:dateTime"
                or constraint.get("startRequiredByMapping") is not True
                or constraint.get("dateRangePredicate") != membership_range
                or constraint.get("dateRangePredicate") != party_range
                or constraint.get("startPredicate") not in {member_start, party_start}
                or constraint.get("endPredicate") not in {member_end, party_end}
                or constraint.get("endAbsentMeans") != "open-ended"
                or constraint.get("rangeOrStartAbsentMeans") != "uncertain"
                or constraint.get("boundary") != "inclusive_endpoint"):
            raise PlanError("Reviewed mapped date-range predicates do not support the required party/member temporal distinction.")
        if (member_range_type != "members:DateRange"
                or party_range_type != "members:DateRange"
                or affiliation_label != query_contract["labelsByEntityType"]["PoliticalAffiliationIdentity"].get("predicate")
                or affiliation_label_language != "en"):
            raise PlanError("Reviewed interval types or affiliation labels disagree with the query-schema contract.")

    return {
        "member_prefix": member_prefix,
        "member_graph": member_graph,
        "houses_graph": houses_graph["iri"],
        "constituency_graph": constituency_graph["iri"],
        "party_graph": party_graph.get("iri") if temporal else None,
        "identity_graph": identity_graph.get("iri") if temporal else None,
        "rdf_types": rdf_types,
        "member_name": member_name,
        "term_number": term_number_link,
        "relations": relations,
        "type_graph": type_graph,
        "temporal": temporal,
        "party_episode_membership": party_episode_membership,
        "member_party_link": member_party_link,
        "episode_party_link": episode_party_link,
        "party_term_link": party_term_link,
        "party_identity_link": party_identity_link,
        "member_range": membership_range if temporal else None,
        "member_range_type": member_range_type if temporal else None,
        "member_start": member_start if temporal else None,
        "member_end": member_end if temporal else None,
        "party_range": party_range if temporal else None,
        "party_range_type": party_range_type if temporal else None,
        "party_start": party_start if temporal else None,
        "party_end": party_end if temporal else None,
        "party_label": party_label if temporal else None,
        "affiliation_label": affiliation_label if temporal else None,
        "affiliation_label_language": affiliation_label_language if temporal else None,
    }


def compile_member_relationship_composition_query(
    plan: dict[str, Any],
    *,
    supported_predicates,
) -> str:
    """Compile a connected relation graph from reviewed predicates/owners only."""
    mapping = _member_relationship_composition_mapping(
        plan, supported_predicates=supported_predicates,
    )
    if mapping["temporal"]:
        return _compile_member_party_temporal_query(
            plan, mapping, supported_predicates=supported_predicates,
        )
    refs = plan["referents"]
    member_id = plan["answer"]["referent"]
    graph_contents: dict[str, list[str]] = {
        "member-records": [], "houses": [], "constituencies": [],
    }
    for referent_id, referent in refs.items():
        semantic_type = referent["type"]
        variable = f"?{referent_id}"
        graph_family = mapping["type_graph"][semantic_type]
        rdf_type = mapping["rdf_types"][semantic_type]
        graph_contents[graph_family].append(f"{variable} a {rdf_type} .")
        if semantic_type == "Member":
            graph_contents[graph_family].append(
                f"OPTIONAL {{ {variable} {mapping['member_name']} ?memberName . }}"
            )
        elif semantic_type == "DailTerm":
            if referent.get("resolution") != "resolved":
                raise PlanError("Every selected DailTerm must resolve uniquely before compilation.")
            term_iri = URIRef(_require_local_iri(referent.get("iri"), "DailTerm")).n3()
            number = referent["selector"]["number"]
            graph_contents[graph_family].append(f"VALUES {variable} {{ {term_iri} }}")
            graph_contents[graph_family].append(
                f'{variable} {mapping["term_number"]} "{number}"^^xsd:integer .'
            )
        elif semantic_type == "DailConstituency":
            if referent.get("resolution") != "resolved":
                raise PlanError("The requested DailConstituency must resolve within its selected term.")
            constituency_iri = URIRef(
                _require_local_iri(referent.get("iri"), "DailConstituency")
            ).n3()
            graph_contents[graph_family].append(f"VALUES {variable} {{ {constituency_iri} }}")

    for relation in plan["relations"]:
        definition = mapping["relations"][relation["fact"]]
        predicate = _reviewed_predicate(relation["fact"])
        graph_contents[definition["subjectGraph"]].append(
            f"?{relation['from']} {predicate} ?{relation['to']} ."
        )

    member_body = "\n    ".join(graph_contents["member-records"])
    houses_body = "\n    ".join(graph_contents["houses"])
    constituency_body = "\n    ".join(graph_contents["constituencies"])
    member_graph = f'''GRAPH ?memberGraph {{
    {member_body}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {json.dumps(mapping['member_prefix'])}))'''
    houses = f'''GRAPH <{mapping['houses_graph']}> {{
    {houses_body}
  }}'''
    constituencies = (
        f'''GRAPH <{mapping['constituency_graph']}> {{
    {constituency_body}
  }}'''
        if constituency_body else ""
    )
    blocks = "\n  ".join(block for block in (member_graph, houses, constituencies) if block)
    membership_ids = [
        referent_id for referent_id, referent in refs.items()
        if referent["type"] == "DailMembership"
    ]
    distinct_memberships = "\n  ".join(
        f"FILTER(?{first} != ?{second})"
        for index, first in enumerate(membership_ids)
        for second in membership_ids[index + 1:]
    )
    if distinct_memberships:
        blocks = f"{blocks}\n  {distinct_memberships}"
    query = _PREFIXES + f'''SELECT DISTINCT ?{member_id} ?memberName WHERE {{
  {blocks}
}} ORDER BY ?memberName ?{member_id} LIMIT 100'''
    return _query(query, supported_predicates)


def _compile_member_party_temporal_query(plan: dict[str, Any], mapping: dict[str, Any], *, supported_predicates) -> str:
    """Compile the single validated party/representation interval composition."""
    refs = plan["referents"]
    term = refs["term"]
    constituency = refs["constituency"]
    if term.get("resolution") != "resolved" or constituency.get("resolution") != "resolved":
        raise PlanError("The exact DailTerm and constituency occurrence must resolve before temporal composition.")
    if plan["answer"].get("referent") == "member":
        affiliation = refs["affiliation"]
        if affiliation.get("resolution") != "resolved":
            raise PlanError("A named-party answer requires the exact resolved affiliation identity before compilation.")
        _require_local_iri(affiliation.get("iri"), "PoliticalAffiliationIdentity")
    term_iri = URIRef(_require_local_iri(term.get("iri"), "DailTerm")).n3()
    constituency_iri = URIRef(_require_local_iri(constituency.get("iri"), "DailConstituency")).n3()
    term_number = term["selector"]["number"]
    types = mapping["rdf_types"]
    relations = mapping["relations"]
    facts = {item["fact"]: item for item in plan["relations"]}
    subject = lambda fact: f"?{facts[fact]['from']}"
    object_ = lambda fact: f"?{facts[fact]['to']}"
    required_patterns = (
        ("member_has_membership", "member", "membership"),
        ("membership_in_term", "membership", "term"),
        ("membership_represents", "membership", "constituency"),
        ("constituency_in_term", "constituency", "term"),
        ("member_party_membership", "member", "episode"),
        ("party_episode_in_membership", "episode", "membership"),
        ("episode_in_parliamentary_party", "episode", "party"),
        ("party_active_during_term", "party", "term"),
        ("parliamentary_party_has_affiliation_identity", "party", "affiliation"),
    )
    for fact, expected_from, expected_to in required_patterns:
        edge = facts.get(fact)
        if edge is None or (edge["from"], edge["to"]) != (expected_from, expected_to):
            raise PlanError(f"Temporal composition compiler cannot bind the reviewed {fact!r} edge.")
        definition = relations.get(fact)
        if definition is None or definition["predicate"] != _reviewed_predicate(fact):
            raise PlanError(f"Temporal composition relation {fact!r} disagrees with its reviewed predicate.")

    member = subject("member_has_membership")
    membership = object_("member_has_membership")
    term_variable = object_("membership_in_term")
    constituency_variable = object_("membership_represents")
    episode = object_("member_party_membership")
    party = object_("episode_in_parliamentary_party")
    affiliation = object_("parliamentary_party_has_affiliation_identity")
    predicates = {
        fact: _reviewed_predicate(fact) for fact, _source, _target in required_patterns
    }
    query = _PREFIXES + f'''SELECT DISTINCT ?member ?memberName ?membership ?membershipRange ?membershipStart ?membershipEnd
  ?episode ?party ?partyLabel ?partyRange ?partyStart ?partyEnd ?affiliation ?affiliationLabel WHERE {{
  GRAPH ?memberGraph {{
    {member} a {types['Member']} ;
      {predicates['member_has_membership']} {membership}, {episode} .
    OPTIONAL {{ {member} {mapping['member_name']} ?memberName . }}
    {membership} a {types['DailMembership']} ;
      {predicates['membership_in_term']} {term_variable} ;
      {predicates['membership_represents']} {constituency_variable} .
    {episode} a {types['PartyMembershipEpisode']} ;
      {predicates['party_episode_in_membership']} {membership} ;
      {predicates['episode_in_parliamentary_party']} {party} .
    OPTIONAL {{
      {membership} {mapping['member_range']} ?membershipRange .
      ?membershipRange a {mapping['member_range_type']} .
      OPTIONAL {{ ?membershipRange {mapping['member_start']} ?membershipStart . }}
      OPTIONAL {{ ?membershipRange {mapping['member_end']} ?membershipEnd . }}
    }}
    OPTIONAL {{
      {episode} {mapping['party_range']} ?partyRange .
      ?partyRange a {mapping['party_range_type']} .
      OPTIONAL {{ ?partyRange {mapping['party_start']} ?partyStart . }}
      OPTIONAL {{ ?partyRange {mapping['party_end']} ?partyEnd . }}
    }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {json.dumps(mapping['member_prefix'])}))
  GRAPH <{mapping['houses_graph']}> {{
    VALUES {term_variable} {{ {term_iri} }}
    {term_variable} a {types['DailTerm']} ; {mapping['term_number']} "{term_number}"^^xsd:integer .
  }}
  GRAPH <{mapping['constituency_graph']}> {{
    VALUES {constituency_variable} {{ {constituency_iri} }}
    {constituency_variable} a {types['DailConstituency']} ; {predicates['constituency_in_term']} {term_variable} .
  }}
  GRAPH <{mapping['party_graph']}> {{
    {party} a {types['ParliamentaryParty']} ; {predicates['party_active_during_term']} {term_variable} .
    OPTIONAL {{ {party} {mapping['party_label']} ?partyLabel . FILTER(LANG(?partyLabel) = "en") }}
  }}
  OPTIONAL {{ GRAPH <{mapping['identity_graph']}> {{
    {party} {predicates['parliamentary_party_has_affiliation_identity']} {affiliation} .
    {affiliation} a {types['PoliticalAffiliationIdentity']} .
    OPTIONAL {{ {affiliation} {mapping['affiliation_label']} ?affiliationLabel . FILTER(LANG(?affiliationLabel) = "{mapping['affiliation_label_language']}") }}
  }} }}
}} ORDER BY ?affiliationLabel ?memberName ?partyStart ?membershipStart ?episode ?membership LIMIT 100'''
    return _query(query, supported_predicates)


def compile_party_affiliation_resolution_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """List reviewed affiliations only among party occurrences in the selected term."""
    plan = validate_plan(plan)
    mapping = _member_relationship_composition_mapping(plan, supported_predicates=supported_predicates)
    if not mapping["temporal"]:
        raise PlanError("Affiliation identity resolution requires the dated party composition.")
    term = plan["referents"]["term"]
    if term.get("resolution") != "resolved":
        raise PlanError("Affiliation resolution requires the exact selected DailTerm identity.")
    term_iri = URIRef(_require_local_iri(term.get("iri"), "DailTerm")).n3()
    party_type = mapping["rdf_types"]["ParliamentaryParty"]
    identity_type = mapping["rdf_types"]["PoliticalAffiliationIdentity"]
    query = _PREFIXES + f'''SELECT DISTINCT ?party ?partyLabel ?affiliation ?affiliationLabel WHERE {{
  GRAPH <{mapping['party_graph']}> {{
    ?party a {party_type} ; {mapping['party_term_link']} {term_iri} .
    OPTIONAL {{ ?party {mapping['party_label']} ?partyLabel . FILTER(LANG(?partyLabel) = "en") }}
  }}
  OPTIONAL {{ GRAPH <{mapping['identity_graph']}> {{
    ?party {mapping['party_identity_link']} ?affiliation .
    ?affiliation a {identity_type} .
    OPTIONAL {{ ?affiliation {mapping['affiliation_label']} ?affiliationLabel . FILTER(LANG(?affiliationLabel) = "en") }}
  }} }}
}} ORDER BY ?affiliationLabel ?partyLabel ?party ?affiliation LIMIT 100'''
    return _query(query, supported_predicates)


def _shared_dail_terms_mapping(plan: dict[str, Any]) -> dict[str, Any]:
    """Cross-check the v2 slice against the currently queryable RDF contracts."""
    plan = validate_plan(plan)
    if plan.get("family") != "shared_dail_terms":
        raise PlanError("Shared-term query compilation requires the validated v2 family.")
    member_refs = sorted(
        (
            (referent_id, referent)
            for referent_id, referent in plan["referents"].items()
            if referent.get("type") == "Member"
        ),
        key=lambda item: (item[1]["mention"].casefold(), item[1]["mention"], item[0]),
    )
    if any(ref.get("resolution") != "resolved" for _referent_id, ref in member_refs):
        raise PlanError("Shared-term compilation requires two independently resolved Member identities.")
    member_iris = tuple(
        _require_local_iri(ref["iri"], "Member") for _referent_id, ref in member_refs
    )
    if len(set(member_iris)) != 2:
        raise PlanError(
            "The two Member referents resolve to the same RDF identity; an intersection needs two distinct identities."
        )

    query_contract = load_query_contract()
    families = {item["id"]: item["graph"] for item in query_contract["graphFamilies"]}
    member_graph = families.get("member-records", {})
    houses_graph = families.get("houses", {})
    if (member_graph.get("kind") != "resource-pattern"
            or not isinstance(member_graph.get("iriTemplate"), str)
            or "{" not in member_graph["iriTemplate"]
            or houses_graph.get("kind") != "fixed"
            or not isinstance(houses_graph.get("iri"), str)):
        raise PlanError("Reviewed Member and Houses graph ownership is unavailable.")
    member_graph_prefix = member_graph["iriTemplate"].split("{", 1)[0]

    membership_pattern = _reviewed_pattern("member-house-membership", "member-records")
    member_pattern = _reviewed_pattern("member-description", "member-records")
    term_pattern = _reviewed_pattern("house-term-description", "houses")
    ordinal_pattern = _reviewed_pattern("house-term-ordinal", "houses")
    member_type = _pattern_rdf_type(member_pattern, "?member")
    membership_type = _pattern_rdf_type(membership_pattern, "?membership")
    membership_types = [
        triple[2] for triple in membership_pattern.get("triples", [])
        if triple[0] == "?membership" and triple[1] == "rdf:type"
    ]
    dail_membership_type = _PLAN_CONTRACT["entityTypeRdfTypes"]["DailMembership"]
    if (member_type != _PLAN_CONTRACT["entityTypeRdfTypes"]["Member"]
            or membership_type != "members:OireachtasMembership"
            or not any(dail_membership_type in item.split(" or ") for item in membership_types)
            or dail_membership_type not in query_contract["queryableClasses"]):
        raise PlanError("Reviewed Member/DailMembership types disagree with the emitted pattern.")
    term_types = [
        triple[2] for triple in term_pattern.get("triples", [])
        if triple[0] == "?term" and triple[1] == "rdf:type"
    ]
    dail_term_type = _PLAN_CONTRACT["entityTypeRdfTypes"]["DailTerm"]
    if (not any(dail_term_type in item.split(" or ") for item in term_types)
            or dail_term_type not in query_contract["queryableClasses"]):
        raise PlanError("The Houses pattern does not expose the reviewed DailTerm type.")

    member_link = _pattern_predicate(membership_pattern, "?member", "?membership")
    term_link = _pattern_predicate(membership_pattern, "?membership", "?term")
    term_label = _pattern_predicate(term_pattern, "?term", "?englishLabel")
    term_number = _pattern_predicate(ordinal_pattern, "?term", "?ordinal")
    if (_reviewed_predicate("member_has_membership") != member_link
            or _reviewed_predicate("membership_in_term") != term_link):
        raise PlanError("Shared-term predicates disagree with the reviewed v2 relation registry.")
    _reviewed_cross_graph_join("member-records", term_link, "houses")
    if term_label != query_contract["labelsByEntityType"]["DailTerm"].get("predicate"):
        raise PlanError("DailTerm display labels disagree with the reviewed owner-label mapping.")
    if term_label not in query_contract["queryableProperties"]:
        raise PlanError("The DailTerm display label is not queryable.")
    if term_number not in query_contract["queryableProperties"]:
        raise PlanError("The DailTerm ordinal is not queryable.")

    return {
        "member_iris": member_iris,
        "member_type": member_type,
        "member_link": member_link,
        "membership_type": membership_type,
        "dail_membership_type": dail_membership_type,
        "term_link": term_link,
        "term_type": dail_term_type,
        "term_label": term_label,
        "term_number": term_number,
        "member_graph_prefix": member_graph_prefix,
        "houses_graph": houses_graph["iri"],
    }


def compile_shared_dail_terms_answer_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Compile an identity intersection on the same asserted DailTerm IRI."""
    mapping = _shared_dail_terms_mapping(plan)
    first_member, second_member = (URIRef(value).n3() for value in mapping["member_iris"])
    query = _PREFIXES + f'''SELECT DISTINCT ?term ?termLabel ?termNo WHERE {{
  VALUES ?memberA {{ {first_member} }}
  GRAPH ?memberGraphA {{
    ?memberA a {mapping['member_type']} ; {mapping['member_link']} ?membershipA .
    ?membershipA a {mapping['membership_type']}, {mapping['dail_membership_type']} ;
      {mapping['term_link']} ?term .
  }}
  FILTER(STRSTARTS(STR(?memberGraphA), {json.dumps(mapping['member_graph_prefix'])}))
  VALUES ?memberB {{ {second_member} }}
  GRAPH ?memberGraphB {{
    ?memberB a {mapping['member_type']} ; {mapping['member_link']} ?membershipB .
    ?membershipB a {mapping['membership_type']}, {mapping['dail_membership_type']} ;
      {mapping['term_link']} ?term .
  }}
  FILTER(STRSTARTS(STR(?memberGraphB), {json.dumps(mapping['member_graph_prefix'])}))
  GRAPH <{mapping['houses_graph']}> {{
    ?term a {mapping['term_type']} ; {mapping['term_label']} ?termLabel ;
      {mapping['term_number']} ?termNo .
  }}
  FILTER(LANG(?termLabel) = "en")
}} ORDER BY ?termNo ?termLabel ?term LIMIT 100'''
    return _query(query, supported_predicates)


def compile_shared_dail_terms_evidence_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Check for recorded Dáil-term membership evidence for each resolved Member."""
    mapping = _shared_dail_terms_mapping(plan)
    member_values = " ".join(URIRef(value).n3() for value in mapping["member_iris"])
    query = _PREFIXES + f'''SELECT DISTINCT ?member ?term WHERE {{
  VALUES ?member {{ {member_values} }}
  GRAPH ?memberGraph {{
    ?member a {mapping['member_type']} ; {mapping['member_link']} ?membership .
    ?membership a {mapping['membership_type']}, {mapping['dail_membership_type']} ;
      {mapping['term_link']} ?term .
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {json.dumps(mapping['member_graph_prefix'])}))
  GRAPH <{mapping['houses_graph']}> {{ ?term a {mapping['term_type']} . }}
}} LIMIT 100'''
    return _query(query, supported_predicates)


def compile_answer_query(plan: dict[str, Any], term_iri: str | None = None,
                         constituency_iri: str | None = None, *, supported_predicates) -> str:
    plan = validate_plan(plan)
    refs = plan["referents"]
    if refs.get("sitting", {}).get("type") == "DebateSitting":
        return compile_debate_answer_query(plan, supported_predicates=supported_predicates)
    if refs[plan["answer"]["referent"]]["type"] == "PoliticalAffiliationIdentity":
        return compile_affiliation_answer_query(plan, supported_predicates=supported_predicates)
    if refs.get("holding", {}).get("type") == "OfficeHolding":
        return compile_office_answer_query(plan, supported_predicates=supported_predicates)
    term_iri = _require_local_iri(term_iri, "HouseTerm")
    constituency_iri = _require_local_iri(constituency_iri, "constituency")
    # The relation registry is intentionally the only source of predicates and
    # owner graphs. It composes all four Q09 joins and preserves referent IDs.
    relation_map = {item["fact"]: item for item in plan["relations"]}
    required = {"constituency_in_term", "member_has_membership", "membership_in_term", "membership_represents"}
    if not required.issubset(relation_map):
        raise PlanError("The answer path is disconnected from membership and representation evidence.")
    member_ref = plan["answer"]["referent"]
    constituency_ref = "constituency"
    term_ref = "term"
    membership_ref = relation_map["member_has_membership"]["to"]
    expected_edges = {
        "constituency_in_term": (constituency_ref, term_ref),
        "member_has_membership": (member_ref, membership_ref),
        "membership_in_term": (membership_ref, term_ref),
        "membership_represents": (membership_ref, constituency_ref),
    }
    for fact, expected in expected_edges.items():
        edge = relation_map[fact]
        if (edge["from"], edge["to"]) != expected:
            raise PlanError(f"Relation {fact!r} is not joined to the selected referent identities.")
    member_var = "?member_" + member_ref
    membership_var = "?membership_" + membership_ref
    member_link = _reviewed_predicate("member_has_membership")
    term_link = _reviewed_predicate("membership_in_term")
    representation_link = _reviewed_predicate("membership_represents")
    member_name = load_query_contract()["labelsByEntityType"]["Member"]["predicate"]
    query = _PREFIXES + f'''SELECT DISTINCT {member_var} ?memberName WHERE {{
  GRAPH ?memberGraph {{
    {member_var} a agents:Member ; {member_name} ?memberName ;
      {member_link} {membership_var} .
    {membership_var} a members:DailMembership ;
      {term_link} <{term_iri}> ;
      {representation_link} <{constituency_iri}> .
  }}
}} ORDER BY ?memberName'''
    return _query(query, supported_predicates)


def compile_debate_answer_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Compile the reviewed sitting→record path and constrained graph route."""
    plan = _validate_debate_plan(plan)
    contract = load_query_contract()
    pattern = _reviewed_pattern("debate-sitting-record", "debates")
    mapped_predicate = _reviewed_predicate("sitting_produced_record")
    graph_family = next(item for item in contract["graphFamilies"] if item["id"] == "debates")
    graph_prefix = graph_family["graph"].get("iriTemplate", "").split("{", 1)[0]
    if not graph_prefix or not graph_prefix.startswith("https://data.oireachtas.ie/graph/debate/"):
        raise PlanError("Reviewed Debate graph route mapping is absent.")
    date_constraint = next(item for item in plan["constraints"] if item["field"] == "date")
    chamber_constraint = next(item for item in plan["constraints"] if item["field"] == "chamber")
    date_mapping = _CONSTRAINT_MAPPINGS["date"]
    chamber_mapping = _CONSTRAINT_MAPPINGS["chamber"]
    date_value = date_constraint["value"]
    chamber = next(item["route"] for item in chamber_mapping["allowedValues"]
                   if item["id"] == chamber_constraint["value"])
    route_pattern = "^" + re.escape(graph_prefix + chamber + "/" + date_value + "/debate") + "$"
    supported = set(supported_predicates)
    predicates = (
        _pattern_predicate(pattern, "?sitting", "?debate"),
        _pattern_predicate(pattern, "?sitting", "?date"),
    )
    if predicates[1] != date_mapping.get("predicate"):
        raise PlanError("Debate date constraint mapping disagrees with the emitted RDF pattern.")
    if predicates[0] != mapped_predicate:
        raise PlanError("Debate relation mapping disagrees with the reviewed emitted RDF pattern.")
    for predicate in predicates:
        qname = predicate.split(":", 1)[0]
        if qname not in contract["namespaces"] or predicate not in contract["queryableProperties"]:
            raise PlanError(f"Debate mapping predicate {predicate!r} is not queryable.")
        uri = URIRef(contract["namespaces"][qname] + predicate.split(":", 1)[1])
        if uri not in supported:
            raise PlanError(f"Debate mapping predicate {predicate!r} is not allowlisted.")
    for semantic_type in ("DebateSitting", "DebateRecord"):
        rdf_type = _PLAN_CONTRACT["entityTypeRdfTypes"][semantic_type]
        if rdf_type not in contract["queryableClasses"]:
            raise PlanError(f"Debate entity type {semantic_type!r} is not queryable.")
    types = {key: _PLAN_CONTRACT["entityTypeRdfTypes"][key] for key in ("DebateSitting", "DebateRecord")}
    where = f'''GRAPH ?debateGraph {{
    ?sitting a {types['DebateSitting']} ; {predicates[0]} ?record ; {predicates[1]} ?date .
    ?record a {types['DebateRecord']} .
  }}
  FILTER(REGEX(STR(?debateGraph), {json.dumps(route_pattern)}))
  FILTER(?date = "{date_value}"^^xsd:date)'''
    if plan["answer"]["kind"] == "boolean":
        query = _PREFIXES + f"ASK WHERE {{\n  {where}\n}}"
    else:
        query = _PREFIXES + f"SELECT DISTINCT ?sitting ?date ?record WHERE {{\n  {where}\n}} ORDER BY ?date ?record"
    return _query(query, supported_predicates)


def _office_query_mapping(plan: dict[str, Any]) -> dict[str, str]:
    """Read and cross-check the reviewed Member → holding → office mapping."""
    plan = _validate_office_plan(plan)
    if plan["referents"]["office"]["resolution"] != "resolved":
        raise PlanError("Q35 compilation requires one resolved local NamedOffice identity.")
    relation_facts = {item["fact"]: item for item in plan["relations"]}
    expected = {
        "member_has_office_holding": ("member", "holding"),
        "office_holding_of_office": ("holding", "office"),
    }
    if len(relation_facts) != len(expected) or any(
        (relation_facts.get(fact, {}).get("from"), relation_facts.get(fact, {}).get("to")) != edge
        for fact, edge in expected.items()
    ):
        raise PlanError("Q35 compilation requires the complete reviewed holding path.")

    member_pattern = _reviewed_pattern("member-description", "member-records")
    holding_pattern = _reviewed_pattern("conditionally-resolved-office-holdings", "member-records")
    office_pattern = _reviewed_pattern("named-office-description", "offices")
    member_type = _pattern_rdf_type(member_pattern, "?member")
    holding_type = _pattern_rdf_type(holding_pattern, "?holding")
    office_type = _pattern_rdf_type(office_pattern, "?office")
    member_name = _pattern_predicate(member_pattern, "?member", "?plainLiteralName")
    member_holding = _pattern_predicate(holding_pattern, "?member", "?holding")
    holding_office = _pattern_predicate(holding_pattern, "?holding", "?office")
    holding_range = _pattern_predicate(holding_pattern, "?holding", "?dateRange")
    range_type = _pattern_rdf_type(holding_pattern, "?dateRange")
    range_start = _pattern_predicate(holding_pattern, "?dateRange", "?startDate")
    range_end = _pattern_predicate(holding_pattern, "?dateRange", "?endDate (optional)")
    office_label = _pattern_predicate(office_pattern, "?office", "?englishOrIrishLabel")

    for fact, predicate in (
        ("member_has_office_holding", member_holding),
        ("office_holding_of_office", holding_office),
    ):
        if _reviewed_predicate(fact) != predicate:
            raise PlanError(f"Q35 relation {fact!r} disagrees with the accepted Member RDF mapping.")
    contract = load_query_contract()
    member_family = next((item for item in contract["graphFamilies"] if item["id"] == "member-records"), None)
    office_family = next((item for item in contract["graphFamilies"] if item["id"] == "offices"), None)
    if (not member_family or member_family["graph"].get("kind") != "resource-pattern"
            or not office_family or office_family["graph"].get("kind") != "fixed"):
        raise PlanError("Q35 requires the reviewed Member-owned and fixed office graph owners.")
    member_graph_prefix = member_family["graph"].get("iriTemplate", "").split("{", 1)[0]
    office_graph = office_family["graph"].get("iri")
    if (not member_graph_prefix.startswith("https://data.oireachtas.ie/graph/member/")
            or not isinstance(office_graph, str)):
        raise PlanError("Q35 graph ownership does not match the reviewed Member/offices contract.")
    member_binding = next((item["value"] for item in plan["constraints"]
                           if item.get("field") == "memberIdentity"), None)
    return {
        "member_type": member_type,
        "holding_type": holding_type,
        "office_type": office_type,
        "member_name": member_name,
        "member_holding": member_holding,
        "holding_office": holding_office,
        "holding_range": holding_range,
        "range_type": range_type,
        "range_start": range_start,
        "range_end": range_end,
        "office_label": office_label,
        "member_graph_prefix": member_graph_prefix,
        "office_graph": office_graph,
        "office_iri": _require_local_iri(plan["referents"]["office"]["iri"], "NamedOffice"),
        "member_iri": (_require_local_iri(member_binding, "Member identity constraint")
                       if member_binding is not None else None),
    }


def _office_interval_bounds(plan: dict[str, Any]) -> tuple[date, date, date]:
    value = plan["constraints"][0]["value"]
    start = date.fromisoformat(value["start"])
    end = date.fromisoformat(value["end"])
    try:
        end_exclusive = end + timedelta(days=1)
    except OverflowError as error:
        raise PlanError("Q35 interval end must leave room for the next calendar-day boundary.") from error
    return start, end, end_exclusive


def compile_office_answer_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Compile inclusive calendar-day overlap over accepted Member holdings."""
    plan = validate_plan(plan)
    mapping = _office_query_mapping(plan)
    start, _end, end_exclusive = _office_interval_bounds(plan)
    start_boundary = f'"{start.isoformat()}T00:00:00"^^xsd:dateTime'
    end_boundary_exclusive = f'"{end_exclusive.isoformat()}T00:00:00"^^xsd:dateTime'
    member_prefix = json.dumps(mapping["member_graph_prefix"])
    office_iri = f'<{mapping["office_iri"]}>'
    member_values = f'VALUES ?member_member {{ <{mapping["member_iri"]}> }}' if mapping["member_iri"] else ""
    query = _PREFIXES + f'''SELECT DISTINCT ?member_member ?memberName ?holding_holding ?holdingStart ?holdingEnd WHERE {{
  GRAPH ?memberGraph {{
    {member_values}
    ?member_member a {mapping["member_type"]} ; {mapping["member_name"]} ?memberName ;
      {mapping["member_holding"]} ?holding_holding .
    ?holding_holding a {mapping["holding_type"]} ;
      {mapping["holding_office"]} {office_iri} ;
      {mapping["holding_range"]} ?holdingDateRange .
    ?holdingDateRange a {mapping["range_type"]} ; {mapping["range_start"]} ?holdingStart .
    OPTIONAL {{ ?holdingDateRange {mapping["range_end"]} ?holdingEnd . }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {member_prefix}))
  GRAPH <{mapping["office_graph"]}> {{ {office_iri} a {mapping["office_type"]} ; {mapping["office_label"]} ?officeLabel . }}
  FILTER(DATATYPE(?holdingStart) = xsd:dateTime)
  FILTER(?holdingStart < {end_boundary_exclusive})
  FILTER(!BOUND(?holdingEnd) || (DATATYPE(?holdingEnd) = xsd:dateTime && ?holdingEnd >= {start_boundary}))
}} ORDER BY ?holdingStart ?memberName ?holding_holding'''
    return _query(query, supported_predicates)


def compile_office_evidence_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Inspect all accepted local holding records, including incomplete dates."""
    plan = validate_plan(plan)
    mapping = _office_query_mapping(plan)
    member_prefix = json.dumps(mapping["member_graph_prefix"])
    office_iri = f'<{mapping["office_iri"]}>'
    member_values = f'VALUES ?member_member {{ <{mapping["member_iri"]}> }}' if mapping["member_iri"] else ""
    query = _PREFIXES + f'''SELECT DISTINCT ?member_member ?memberName ?holding_holding ?holdingDateRange ?holdingStart ?holdingEnd WHERE {{
  GRAPH ?memberGraph {{
    {member_values}
    ?member_member a {mapping["member_type"]} ; {mapping["member_name"]} ?memberName ;
      {mapping["member_holding"]} ?holding_holding .
    ?holding_holding a {mapping["holding_type"]} ; {mapping["holding_office"]} {office_iri} .
    OPTIONAL {{
      ?holding_holding {mapping["holding_range"]} ?holdingDateRange .
      ?holdingDateRange a {mapping["range_type"]} .
      OPTIONAL {{ ?holdingDateRange {mapping["range_start"]} ?holdingStart . }}
      OPTIONAL {{ ?holdingDateRange {mapping["range_end"]} ?holdingEnd . }}
    }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {member_prefix}))
  GRAPH <{mapping["office_graph"]}> {{ {office_iri} a {mapping["office_type"]} ; {mapping["office_label"]} ?officeLabel . }}
}} ORDER BY ?memberName ?holding_holding ?holdingStart ?holdingEnd'''
    return _query(query, supported_predicates)


_XSD_DATETIME_IRI = "http://www.w3.org/2001/XMLSchema#dateTime"


def _office_datetime_binding(value: str) -> tuple[datetime | None, str | None]:
    if value in {"—", ""}:
        return None, None
    lexical, separator, datatype = value.rpartition("^^")
    if not separator:
        return None, "the RDF datatype was not returned"
    if datatype.strip("<>") != _XSD_DATETIME_IRI:
        return None, "the RDF datatype is not xsd:dateTime"
    if "T" not in lexical:
        return None, "the xsd:dateTime lexical value is malformed"
    try:
        parsed = datetime.fromisoformat(lexical.replace("Z", "+00:00"))
    except ValueError:
        return None, "the xsd:dateTime lexical value is malformed"
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed, None


def _display_office_datetime(value: datetime) -> str:
    if value.time().isoformat() == "00:00:00":
        return value.date().isoformat()
    return value.isoformat(sep=" ")


def readable_office_holding_result(result: QueryResult, plan: dict[str, Any]) -> QueryResult:
    """Keep one readable row per accepted holding, even for repeated Members."""
    if result.kind != "select":
        raise NLQError("Office-holding answer query returned an unexpected result kind.")
    expected_columns = ("member_member", "memberName", "holding_holding", "holdingStart", "holdingEnd")
    if not set(expected_columns).issubset(result.columns):
        raise NLQError("Office-holding answer query omitted Member or dated holding evidence.")
    indexes = {name: result.columns.index(name) for name in expected_columns}
    interval_start, _interval_end, interval_end_exclusive = _office_interval_bounds(plan)
    lower = datetime.combine(interval_start, datetime.min.time())
    upper = datetime.combine(interval_end_exclusive, datetime.min.time())
    by_holding: dict[str, tuple[str, str, datetime, datetime | None]] = {}
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError("Office-holding answer query returned a truncated evidence row.")
        member_iri = _require_local_iri(row[indexes["member_member"]], "Member")
        holding_iri = _require_local_iri(row[indexes["holding_holding"]], "OfficeHolding")
        name = row[indexes["memberName"]].removesuffix("@en")
        start, start_error = _office_datetime_binding(row[indexes["holdingStart"]])
        end, end_error = _office_datetime_binding(row[indexes["holdingEnd"]])
        if start_error or start is None:
            raise NLQError(f"Office-holding result has insufficient start-date evidence: {start_error or 'missing start date'}.")
        if end_error:
            raise NLQError(f"Office-holding result has an unsupported end-date value: {end_error}.")
        if end is not None and end < start:
            raise NLQError("Office-holding result has an end date before its start date.")
        if not (start < upper and (end is None or end >= lower)):
            raise NLQError("The compiled office-overlap query returned a holding outside the requested interval.")
        evidence = (member_iri, name, start, end)
        previous = by_holding.get(holding_iri)
        if previous is not None and previous != evidence:
            raise NLQError("One OfficeHolding has conflicting Member or date evidence in the local dataset.")
        by_holding[holding_iri] = evidence
    rows = [
        (name, _display_office_datetime(start),
         _display_office_datetime(end) if end is not None else "Open-ended (no end date recorded)")
        for _member_iri, name, start, end in by_holding.values()
    ]
    rows.sort(key=lambda row: (row[1], row[0].casefold(), row[0]))
    return QueryResult(
        "select", ("Member", "Holding start", "Holding end"), tuple(rows), result.raw_json,
    )


def inspect_office_holding_evidence(
    result: QueryResult, plan: dict[str, Any],
) -> tuple[bool, frozenset[str], tuple[str, ...]]:
    """Check accepted holding evidence and identify date gaps without inference."""
    if result.kind != "select":
        raise NLQError("Office-holding evidence query returned an unexpected result kind.")
    required = {"member_member", "memberName", "holding_holding", "holdingDateRange", "holdingStart", "holdingEnd"}
    if not required.issubset(result.columns):
        raise NLQError("Office-holding evidence query omitted required identity or date bindings.")
    indexes = {name: result.columns.index(name) for name in required}
    interval_start, _interval_end, interval_end_exclusive = _office_interval_bounds(plan)
    lower = datetime.combine(interval_start, datetime.min.time())
    upper = datetime.combine(interval_end_exclusive, datetime.min.time())
    seen_holding_evidence: dict[str, tuple[str, str, str, str, str]] = {}
    overlapping: set[str] = set()
    issues: set[str] = set()
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError("Office-holding evidence query returned a truncated row.")
        member_iri = _require_local_iri(row[indexes["member_member"]], "Member")
        holding_iri = _require_local_iri(row[indexes["holding_holding"]], "OfficeHolding")
        name = row[indexes["memberName"]].removesuffix("@en")
        range_iri = row[indexes["holdingDateRange"]]
        start_text = row[indexes["holdingStart"]]
        end_text = row[indexes["holdingEnd"]]
        evidence_key = (member_iri, name, range_iri, start_text, end_text)
        previous = seen_holding_evidence.get(holding_iri)
        if previous is not None and previous != evidence_key:
            issues.add("one accepted holding has conflicting Member or date evidence")
        seen_holding_evidence[holding_iri] = evidence_key
        if range_iri in {"—", ""}:
            issues.add("a holding has no typed date range")
            continue
        start, start_error = _office_datetime_binding(start_text)
        if start_error or start is None:
            issues.add("a holding has no valid xsd:dateTime start evidence")
            continue
        # A valid start after the requested period proves non-overlap regardless
        # of an absent or malformed end date.
        if start >= upper:
            continue
        end, end_error = _office_datetime_binding(end_text)
        if end_error:
            issues.add("a potentially overlapping holding has invalid end-date evidence")
            continue
        if end is not None and end < start:
            issues.add("a holding has an end date before its start date")
            continue
        if end is None or end >= lower:
            overlapping.add(holding_iri)
    return bool(result.rows), frozenset(overlapping), tuple(sorted(issues))


def readable_member_result(result: QueryResult) -> QueryResult:
    """Deduplicate per RDF Member identity and hide internal identity bindings."""
    if result.kind != "select":
        raise NLQError("Member answer query returned an unexpected result kind.")
    try:
        member_index = result.columns.index("member_member")
    except ValueError:
        member_index = 0
    try:
        name_index = result.columns.index("memberName")
    except ValueError as error:
        raise NLQError("Member answer query did not return display names.") from error
    by_member: dict[str, str] = {}
    for row in result.rows:
        if max(member_index, name_index) >= len(row):
            continue
        by_member.setdefault(row[member_index], row[name_index].removesuffix("@en"))
    rows = tuple((name,) for _, name in sorted(by_member.items(), key=lambda item: (item[1].casefold(), item[0])))
    return QueryResult(kind="select", columns=("Member",), rows=rows, raw_json=result.raw_json)


def readable_debate_result(result: QueryResult) -> QueryResult:
    if result.kind != "select":
        raise NLQError("Debate answer query returned an unexpected result kind.")
    try:
        indexes = {name: result.columns.index(name) for name in ("date", "record")}
    except ValueError as error:
        raise NLQError("Debate answer query omitted its date or official record identifier.") from error
    rows: dict[str, tuple[str, str]] = {}
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            continue
        raw_date, record = row[indexes["date"]], row[indexes["record"]]
        if not record.startswith("https://data.oireachtas.ie/akn/ie/debateRecord/"):
            raise NLQError("Debate result did not contain a supported official Work identifier.")
        try:
            parsed = datetime.fromisoformat(raw_date.split("^^", 1)[0].removesuffix("Z"))
            display_date = parsed.strftime("%A %-d %B %Y")
        except ValueError as error:
            raise NLQError("Debate result contains a malformed source date.") from error
        rows[record] = (display_date, record)
    display_rows = tuple(rows[key] for key in sorted(rows))
    return QueryResult("select", ("Sitting date", "Official debate"), display_rows, result.raw_json)


_XSD_BOOLEAN_IRI = "http://www.w3.org/2001/XMLSchema#boolean"
_XSD_INTEGER_IRI = "http://www.w3.org/2001/XMLSchema#integer"
_XSD_STRING_IRI = "http://www.w3.org/2001/XMLSchema#string"
_CANONICAL_BILL_IRI = re.compile(
    r"^https://data\.oireachtas\.ie/ie/oireachtas/bill/(?P<year>[0-9]{4})/(?P<number>[^/?#]+)$"
)


def _rdf_literal_parts(value: str) -> tuple[str | None, str | None, str | None]:
    """Split the compact binding representation while retaining RDF datatype/language."""
    if value in {"—", ""}:
        return None, None, None
    lexical, marker, datatype = value.rpartition("^^<")
    if marker and datatype.endswith(">"):
        return lexical, None, datatype[:-1]
    language_match = re.fullmatch(r"(.*)@([A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*)", value)
    if language_match:
        return language_match.group(1), language_match.group(2).lower(), None
    return value, None, None


def _primary_status_from_binding(value: str) -> tuple[str | None, str | None]:
    lexical, _language, datatype = _rdf_literal_parts(value)
    if lexical is None:
        return None, None
    if datatype != _XSD_BOOLEAN_IRI:
        return None, value
    normalized = lexical.strip().lower()
    if normalized in {"true", "1"}:
        return "Primary", None
    if normalized in {"false", "0"}:
        return "Supporting", None
    return None, value


def _bill_identity_route(bill_iri: str) -> tuple[str, str, str] | None:
    match = _CANONICAL_BILL_IRI.fullmatch(bill_iri)
    if not match:
        return None
    year, encoded_number = match.group("year"), match.group("number")
    number = unquote(encoded_number)
    if not number or any(character in number for character in "/?#"):
        return None
    graph_template = next(
        item["graph"]["iriTemplate"] for item in load_query_contract()["graphFamilies"]
        if item["id"] == "bill-records"
    )
    graph_iri = graph_template.replace("{year}", quote(year, safe="")).replace(
        "{number}", quote(number, safe=""),
    )
    return year, number, graph_iri


def _display_counts(counts: dict[str, int], *, total: int) -> str:
    labels = []
    for status in ("Primary", "Supporting", "Unknown"):
        count = counts.get(status, 0)
        if not count:
            continue
        if status == "Unknown":
            labels.append(
                "Unknown (primary-status flag absent)" if count == 1 else
                f"Unknown (flag absent on {count} participations)"
            )
        elif total == 1:
            labels.append(status)
        else:
            labels.append(f"{status} ({count} participation{'s' if count != 1 else ''})")
    return "; ".join(labels)


def readable_bill_sponsorship_result(result: QueryResult) -> BillSponsorshipProjection:
    """Deduplicate by Bill IRI only after preserving all participation evidence."""
    if result.kind != "select":
        raise NLQError("Bill sponsorship answer query returned an unexpected result kind.")
    expected_columns = (
        "billGraph", "bill", "participation", "primaryEvidence", "participationRole",
        "englishTitle", "billNumber", "billYear",
    )
    if not set(expected_columns).issubset(result.columns):
        raise NLQError("Bill sponsorship answer query omitted Bill or participation evidence.")
    indexes = {name: result.columns.index(name) for name in expected_columns}
    bills: dict[str, dict[str, Any]] = {}
    participation_owners: dict[str, str] = {}
    diagnostics: set[str] = set()
    missing_primary_status = False
    incomplete_display = False
    conflicting_evidence = False

    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError("Bill sponsorship answer query returned a truncated evidence row.")
        bill_iri = _require_local_iri(row[indexes["bill"]], "Bill")
        bill_graph = _require_local_iri(row[indexes["billGraph"]], "Bill named graph")
        participation_iri = _require_local_iri(row[indexes["participation"]], "BillParticipation")
        identity_route = _bill_identity_route(bill_iri)
        if identity_route is not None and bill_graph != identity_route[2]:
            raise NLQError("Bill identity and named graph disagree with the reviewed ownership route.")
        if participation_iri in participation_owners and participation_owners[participation_iri] != bill_iri:
            raise NLQError("One BillParticipation is co-owned by conflicting Bill identities.")
        participation_owners[participation_iri] = bill_iri
        bill = bills.setdefault(bill_iri, {
            "graph": bill_graph, "titles": set(), "numbers": set(), "years": set(), "participations": {},
        })
        if bill["graph"] != bill_graph:
            raise NLQError("One Bill identity appears in multiple Bill-owned named graphs.")

        title, language, _datatype = _rdf_literal_parts(row[indexes["englishTitle"]])
        if title is not None:
            if language != "en" or not title.strip():
                diagnostics.add("An English short-title binding was not a non-empty @en literal.")
                incomplete_display = True
            else:
                bill["titles"].add(title.strip())

        raw_number = row[indexes["billNumber"]]
        number, _language, number_datatype = _rdf_literal_parts(raw_number)
        if number is not None:
            if number_datatype not in {None, _XSD_STRING_IRI} or not number.strip():
                diagnostics.add("A Bill process number had an unsupported RDF literal datatype or value.")
                conflicting_evidence = True
            else:
                bill["numbers"].add(number.strip())

        raw_year = row[indexes["billYear"]]
        year, _language, year_datatype = _rdf_literal_parts(raw_year)
        if year is not None:
            if year_datatype != _XSD_INTEGER_IRI or not re.fullmatch(r"[0-9]{4}", year.strip()):
                diagnostics.add("A Bill legislative year had an unsupported RDF literal datatype or value.")
                conflicting_evidence = True
            else:
                bill["years"].add(year.strip())

        participation = bill["participations"].setdefault(participation_iri, {
            "statuses": set(), "unknown": False, "invalid_statuses": set(), "roles": set(),
        })
        status, invalid_status = _primary_status_from_binding(row[indexes["primaryEvidence"]])
        if status is None and invalid_status is None:
            participation["unknown"] = True
            missing_primary_status = True
        elif invalid_status is not None:
            participation["invalid_statuses"].add(invalid_status)
        else:
            participation["statuses"].add(status)

        role, _role_language, _role_datatype = _rdf_literal_parts(row[indexes["participationRole"]])
        if role is not None and role.strip():
            participation["roles"].add(role.strip())

    rows: list[tuple[tuple[Any, ...], tuple[str, ...]]] = []
    for bill_iri, bill in bills.items():
        identity_route = _bill_identity_route(bill_iri)
        path_year, path_number = identity_route[:2] if identity_route else (None, None)
        titles = sorted(bill["titles"], key=lambda value: (value.casefold(), value))
        if not titles:
            title_display = "English short title not recorded"
            diagnostics.add(f"Bill {bill_iri} has no mapped English short title.")
            incomplete_display = True
        elif len(titles) > 1:
            title_display = "Conflicting English short-title evidence: " + " / ".join(titles)
            diagnostics.add(f"Bill {bill_iri} has conflicting English short-title values.")
            incomplete_display = True
            conflicting_evidence = True
        else:
            title_display = titles[0]

        source_numbers = sorted(bill["numbers"], key=lambda value: (value.casefold(), value))
        if not source_numbers:
            number_display = "Not recorded"
        elif len(source_numbers) > 1:
            number_display = "Conflicting Bill-number evidence: " + " / ".join(source_numbers)
            diagnostics.add(f"Bill {bill_iri} has conflicting process-number values.")
            conflicting_evidence = True
        elif path_number is not None and source_numbers[0] != path_number:
            number_display = f"Conflicting Bill number: source {source_numbers[0]}, identity {path_number}"
            diagnostics.add(f"Bill {bill_iri} process number disagrees with its Bill identity.")
            conflicting_evidence = True
        else:
            number_display = source_numbers[0]

        source_years = sorted(bill["years"])
        if not source_years:
            year_display = "Not recorded"
        elif len(source_years) > 1:
            year_display = "Conflicting legislative-year evidence: " + " / ".join(source_years)
            diagnostics.add(f"Bill {bill_iri} has conflicting legislative-year values.")
            conflicting_evidence = True
        elif path_year is not None and source_years[0] != path_year:
            year_display = f"Conflicting Bill year: source {source_years[0]}, identity {path_year}"
            diagnostics.add(f"Bill {bill_iri} legislative year disagrees with its Bill identity.")
            conflicting_evidence = True
        else:
            year_display = source_years[0]

        status_counts: dict[str, int] = {}
        role_counts: dict[str, int] = {}
        roles_missing = 0
        status_conflicts: list[str] = []
        invalid_status_participations = 0
        for participation_iri, evidence in bill["participations"].items():
            statuses = set(evidence["statuses"])
            if evidence["unknown"]:
                statuses.add("Unknown")
            if len(statuses) > 1:
                status_conflicts.append(" + ".join(sorted(statuses)))
                conflicting_evidence = True
            elif statuses:
                only_status = next(iter(statuses))
                status_counts[only_status] = status_counts.get(only_status, 0) + 1
            if evidence["invalid_statuses"]:
                invalid_status_participations += 1
                conflicting_evidence = True
            roles = sorted(evidence["roles"], key=lambda value: (value.casefold(), value))
            if len(roles) > 1:
                role_counts["Conflicting role labels: " + " / ".join(roles)] = role_counts.get(
                    "Conflicting role labels: " + " / ".join(roles), 0,
                ) + 1
                diagnostics.add(f"BillParticipation {participation_iri} has conflicting role labels.")
                conflicting_evidence = True
            elif roles:
                role_counts[roles[0]] = role_counts.get(roles[0], 0) + 1
            else:
                roles_missing += 1

        participation_count = len(bill["participations"])
        status_parts = []
        status_summary = _display_counts(status_counts, total=participation_count)
        if status_summary:
            status_parts.append(status_summary)
        if status_conflicts:
            conflict_summary = sorted(set(status_conflicts), key=lambda value: (value.casefold(), value))
            status_parts.append("Conflicting primary-status values on participation(s): " + "; ".join(conflict_summary))
            diagnostics.add(f"Bill {bill_iri} has conflicting primary-status values on a single participation.")
        if invalid_status_participations:
            status_parts.append(
                f"Uninterpretable primary-status evidence on {invalid_status_participations} participation"
                f"{'s' if invalid_status_participations != 1 else ''}"
            )
            diagnostics.add(f"Bill {bill_iri} has invalid primary-status evidence.")
        for evidence in bill["participations"].values():
            for invalid in evidence["invalid_statuses"]:
                status_parts.append(f"unrecognized value {invalid!r}")
        status_display = "; ".join(status_parts) if status_parts else "Unknown (primary-status flag not recorded)"

        role_parts = []
        for role, count in sorted(role_counts.items(), key=lambda item: (item[0].casefold(), item[0])):
            role_parts.append(role if participation_count == 1 else
                              f"{role} ({count} participation{'s' if count != 1 else ''})")
        if roles_missing:
            role_parts.append(
                "Role not recorded" if participation_count == 1 else
                f"Role not recorded ({roles_missing} participation{'s' if roles_missing != 1 else ''})"
            )
        role_display = "; ".join(role_parts) if role_parts else "Not recorded"
        official_link = bill_iri if identity_route is not None else "Official link unavailable"
        if identity_route is None:
            diagnostics.add(f"Bill {bill_iri} does not have a canonical official Bill IRI for linking.")

        number_sort = (0, int(path_number)) if path_number and path_number.isdigit() else (1, (path_number or "").casefold())
        sort_key = (
            int(path_year) if path_year else 9999,
            number_sort,
            bill_iri,
        )
        rows.append((sort_key, (
            title_display, status_display, number_display, year_display, role_display, official_link,
        )))

    rows.sort(key=lambda item: item[0])
    readable = QueryResult(
        "select",
        ("English short title", "Sponsorship status", "Bill number", "Year", "Recorded sponsor roles", "Official Bill"),
        tuple(row for _sort_key, row in rows),
        result.raw_json,
    )
    if missing_primary_status:
        diagnostics.add("At least one Participation lacks isPrimarySponsor; that evidence is shown as Unknown.")
    return BillSponsorshipProjection(
        readable,
        missing_primary_status=missing_primary_status,
        incomplete_display=incomplete_display,
        conflicting_evidence=conflicting_evidence,
        diagnostics=tuple(sorted(diagnostics, key=lambda value: (value.casefold(), value))),
    )


class AmbiguousMember(NLQError):
    """A Member name resolves to more than one local Member resource."""

    def __init__(self, mention: str, candidates: tuple[dict[str, str], ...]):
        super().__init__(f"Several local Member records match “{mention}”; none was selected.")
        self.candidates = candidates


def member_resolution_query(*, supported_predicates) -> str:
    member_graph = next(item["graph"]["iriTemplate"].split("{", 1)[0]
                        for item in load_query_contract()["graphFamilies"]
                        if item["id"] == "member-records")
    name = load_query_contract()["labelsByEntityType"]["Member"]["predicate"]
    return _query(_PREFIXES + f'''SELECT DISTINCT ?member ?name WHERE {{
  GRAPH ?memberGraph {{ ?member a agents:Member ; {name} ?name . }}
  FILTER(STRSTARTS(STR(?memberGraph), "{member_graph}"))
}}''', supported_predicates)


def resolve_member(result: QueryResult, mention: str) -> tuple[str, str]:
    wanted = _normalise_label(mention)
    candidates: dict[str, str] = {}
    for row in result.rows:
        if len(row) < 2:
            continue
        iri, label = row[:2]
        _require_local_iri(iri, "Member")
        label = label.removesuffix("@en")
        if _normalise_label(label) == wanted:
            candidates[iri] = label
    if not candidates:
        raise NLQError(f"No local Member record was found for “{mention}”.")
    if len(candidates) > 1:
        raise AmbiguousMember(mention, tuple({"iri": iri, "label": candidates[iri]} for iri in sorted(candidates)))
    iri = next(iter(candidates))
    return iri, candidates[iri]


def compile_affiliation_answer_query(plan: dict[str, Any], *, supported_predicates) -> str:
    """Compile the reviewed Member → episode → term party → local identity path."""
    plan = validate_plan(plan)
    refs = plan["referents"]
    member_iri = _require_local_iri(refs["member"].get("iri"), "Member")
    relation_map = {item["fact"]: item for item in plan["relations"]}
    expected = {
        "member_party_membership": ("member", "episode"),
        "episode_in_parliamentary_party": ("episode", "party"),
        "parliamentary_party_has_affiliation_identity": ("party", "affiliation"),
    }
    if len(relation_map) != len(expected) or any(
        (relation_map.get(fact, {}).get("from"), relation_map.get(fact, {}).get("to")) != edge
        for fact, edge in expected.items()
    ):
        raise PlanError("Q06 compiler requires every reviewed Member/episode/party/identity edge.")
    for fact in expected:
        _reviewed_predicate(fact)
    contract = load_query_contract()
    family_graphs = {family["id"]: family["graph"] for family in contract["graphFamilies"]}
    identity_graph = family_graphs.get("political-affiliations", {}).get("iri")
    party_graph = family_graphs.get("parties", {}).get("iri")
    houses_graph = family_graphs.get("houses", {}).get("iri")
    if not identity_graph or not party_graph or not houses_graph:
        raise PlanError("Reviewed Parties, Houses or political-affiliation graph ownership is absent from the query contract.")
    supported = set(supported_predicates)
    identity_qname = _reviewed_predicate("parliamentary_party_has_affiliation_identity")
    identity_prefix, identity_local = identity_qname.split(":", 1)
    identity_uri = URIRef(contract["namespaces"][identity_prefix] + identity_local)
    if identity_uri not in supported:
        raise PlanError("The reviewed political-affiliation identity predicate is not allowlisted.")
    party_membership = _reviewed_predicate("episode_in_parliamentary_party")
    member_membership = _reviewed_predicate("member_party_membership")
    episode_pattern = _reviewed_pattern("party-membership-episode", "member-records")
    membership_pattern = _reviewed_pattern("member-house-membership", "member-records")
    identity_pattern = _reviewed_pattern("reviewed-political-affiliation-identities", "political-affiliations")
    party_term_pattern = _reviewed_pattern("party-term-occurrence", "parties")
    rdf_types = _PLAN_CONTRACT["entityTypeRdfTypes"]
    for semantic_type in ("Member", "PartyMembershipEpisode", "ParliamentaryParty", "PoliticalAffiliationIdentity"):
        if rdf_types[semantic_type] not in contract["queryableClasses"]:
            raise PlanError(f"Reviewed RDF type for {semantic_type!r} is absent from the query contract.")
    episode_type = rdf_types["PartyMembershipEpisode"]
    party_type = rdf_types["ParliamentaryParty"]
    identity_type = rdf_types["PoliticalAffiliationIdentity"]
    member_type = rdf_types["Member"]
    term_types = (rdf_types["DailTerm"], rdf_types["SeanadTerm"])
    if any(term_type not in contract["queryableClasses"] for term_type in term_types):
        raise PlanError("Reviewed HouseTerm RDF types are absent from the query contract.")
    membership_term = _pattern_predicate(membership_pattern, "?membership", "?term")
    date_range = _pattern_predicate(episode_pattern, "?partyEpisode", "?partyDateRange (optional for query projection)")
    date_range_type = _pattern_rdf_type(episode_pattern, "?partyDateRange")
    start = _pattern_predicate(episode_pattern, "?partyDateRange", "?affiliationStart (optional)")
    end = _pattern_predicate(episode_pattern, "?partyDateRange", "?affiliationEnd (optional)")
    linked_membership = _pattern_predicate(episode_pattern, "?partyEpisode", "?oireachtasMembership")
    party_term = _pattern_predicate(party_term_pattern, "?party", "?term")
    _reviewed_cross_graph_join("parties", party_term, "houses")
    label_entry = contract["labelsByEntityType"].get("PoliticalAffiliationIdentity", {})
    label = label_entry.get("predicate")
    label_language = label_entry.get("language")
    if not label or label not in contract["queryableProperties"]:
        raise PlanError("No reviewed preferred-label mapping exists for political-affiliation identities.")
    if label_language != "en":
        raise PlanError("Political-affiliation answers require the reviewed English preferred label.")
    identity_link = _pattern_predicate(identity_pattern, "?party", "?identity")
    preferred_label = _pattern_predicate(identity_pattern, "?identity", "?englishPreferredLabel")
    if preferred_label != label:
        raise PlanError("Political-affiliation preferred-label mappings disagree across reviewed contracts.")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?member ?episode ?identity ?affiliationLabel ?start ?end WHERE {{
  GRAPH ?memberGraph {{
    <{member_iri}> a {member_type} ; {member_membership} ?episode .
    ?episode a {episode_type} ; {linked_membership} ?membership ; {party_membership} ?party .
    ?membership {membership_term} ?term .
    OPTIONAL {{ ?episode {date_range} ?dateRange .
      ?dateRange a {date_range_type} .
      OPTIONAL {{ ?dateRange {start} ?start . }}
      OPTIONAL {{ ?dateRange {end} ?end . }}
    }}
  }}
  GRAPH <{party_graph}> {{ ?party a {party_type} ; {party_term} ?term . }}
  GRAPH <{houses_graph}> {{ ?term a ?termType . }}
  VALUES ?termType {{ {term_types[0]} {term_types[1]} }}
  OPTIONAL {{ GRAPH <{identity_graph}> {{
    ?party {identity_link} ?identity .
    ?identity a {identity_type} .
    OPTIONAL {{ ?identity {preferred_label} ?affiliationLabel . FILTER(LANG(?affiliationLabel) = "{label_language}") }}
  }} }}
}} ORDER BY ?affiliationLabel ?start ?end''', supported_predicates)


def readable_affiliation_result(result: QueryResult) -> QueryResult:
    """Group episode rows by reviewed identity; retain each dated episode separately."""
    if result.kind != "select":
        raise NLQError("Political-affiliation answer query returned an unexpected result kind.")
    indexes = {name: result.columns.index(name) for name in ("episode", "identity", "affiliationLabel", "start", "end")
               if name in result.columns}
    if not {"episode", "identity", "affiliationLabel", "start", "end"}.issubset(indexes):
        raise NLQError("Political-affiliation answer query omitted identity or episode evidence.")
    grouped: dict[str, tuple[str, dict[str, tuple[str, str]]]] = {}
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            continue
        identity = row[indexes["identity"]]
        episode_iri = row[indexes["episode"]]
        label = row[indexes["affiliationLabel"]].removesuffix("@en")
        if identity in {"—", ""} or not label:
            continue
        _require_local_iri(identity, "PoliticalAffiliationIdentity")
        _require_local_iri(episode_iri, "PartyMembershipEpisode")
        starts = row[indexes["start"]]
        ends = row[indexes["end"]]
        episode = (starts.removesuffix("^^http://www.w3.org/2001/XMLSchema#date"),
                   ends.removesuffix("^^http://www.w3.org/2001/XMLSchema#date"))
        grouped.setdefault(identity, (label, {}))[1][episode_iri] = episode
    rows = []
    for identity, (label, episodes) in sorted(grouped.items(), key=lambda item: (item[1][0].casefold(), item[0])):
        dated = []
        for start, end in sorted(episodes.values()):
            if start in {"—", ""} and end in {"—", ""}:
                dated.append("membership episode (dates not recorded)")
            else:
                dated.append(f"{start or 'start date not recorded'} – {end or 'end date not recorded'}")
        rows.append((label, "; ".join(dated)))
    return QueryResult("select", ("Political affiliation", "Supporting membership episodes"), tuple(rows), result.raw_json)


def _execute_office_question(plan: dict[str, Any], *, fuseki, supported_predicates) -> PlanOutcome:
    office_ref = plan["referents"]["office"]
    mention = office_ref["mention"]
    try:
        resolution = resolve_local_entity_label(
            "NamedOffice", mention, fuseki, supported_predicates=supported_predicates,
        )
    except UnsupportedLocalEntityType as error:
        office_ref["resolution"] = "unsupported_mapping"
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    except NLQError as error:
        office_ref["resolution"] = "source_data_unavailable"
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=f"The reviewed local office registry could not be read: {error}",
        )
    if resolution.state == "unresolved":
        office_ref["resolution"] = "not_found"
        return PlanOutcome(
            "not_found", plan=plan,
            diagnostic=f'No reviewed local NamedOffice exactly matches “{mention}”.',
        )
    if resolution.state == "ambiguous":
        candidates = tuple({"iri": item.iri, "label": item.label} for item in resolution.candidates)
        office_ref.update({"resolution": "ambiguous", "candidates": list(candidates)})
        return PlanOutcome(
            "ambiguous", plan=plan,
            diagnostic=f'Several reviewed local NamedOffice records match “{mention}”; none was selected.',
            candidates=candidates,
        )
    if resolution.state != "resolved" or len(resolution.candidates) != 1:
        office_ref["resolution"] = "source_data_unavailable"
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic="The local office resolver did not return one usable reviewed identity.",
        )
    candidate = resolution.candidates[0]
    office_ref.update({"resolution": "resolved", "iri": candidate.iri, "label": candidate.label})
    try:
        plan = validate_plan(plan)
        evidence_query = compile_office_evidence_query(plan, supported_predicates=supported_predicates)
    except (PlanError, NLQError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    try:
        evidence_result = fuseki.query(evidence_query)
        if evidence_result.kind != "select":
            raise NLQError("Office-holding evidence query returned an unexpected result kind.")
        if len(evidence_result.rows) >= 100:
            return PlanOutcome(
                "insufficient_holding_evidence", plan=plan, sparql=evidence_query,
                diagnostic="The office-holding evidence query reached the 100-row safety cap; no yes/no or complete interval result was inferred.",
            )
        has_evidence, overlapping_holdings, evidence_issues = inspect_office_holding_evidence(
            evidence_result, plan,
        )
    except NLQError as error:
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=f"Accepted local holding evidence could not be checked: {error}",
        )
    if not has_evidence:
        member_bound = any(item.get("field") == "memberIdentity" for item in plan["constraints"])
        if member_bound:
            diagnostic = ("No accepted Member-owned OfficeHolding record for this reviewed office is present "
                          "for the exact resolved Member in the local dataset; historical tenure cannot be determined.")
        else:
            diagnostic = ("No accepted Member-owned OfficeHolding record for this reviewed office "
                          "is present in the local dataset; historical tenure cannot be determined.")
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=diagnostic,
        )

    try:
        answer_query = compile_office_answer_query(plan, supported_predicates=supported_predicates)
    except (PlanError, NLQError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    try:
        raw_result = fuseki.query(answer_query)
        if raw_result.kind != "select":
            raise NLQError("Office-holding answer query returned an unexpected result kind.")
        if not {"member_member", "holding_holding"}.issubset(raw_result.columns):
            raise NLQError("Office-holding answer query omitted Member/holding identity evidence.")
        if len(raw_result.rows) >= 100:
            return PlanOutcome(
                "insufficient_holding_evidence", plan=plan, sparql=answer_query,
                diagnostic="The office-holding answer query reached the 100-row safety cap; no complete interval answer was inferred.",
            )
        holding_index = raw_result.columns.index("holding_holding")
        answer_holding_ids = {
            _require_local_iri(row[holding_index], "OfficeHolding")
            for row in raw_result.rows
        }
        if answer_holding_ids != set(overlapping_holdings):
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic=("The local typed holding-date evidence and generated overlap query disagree; "
                            "no historical answer was returned."),
            )
        result = readable_office_holding_result(raw_result, plan) if raw_result.rows else None
    except NLQError as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query, diagnostic=str(error))

    start = plan["constraints"][0]["value"]["start"]
    end = plan["constraints"][0]["value"]["end"]
    if evidence_issues:
        return PlanOutcome(
            "insufficient_holding_evidence", plan=plan, sparql=answer_query, result=result,
            diagnostic=(f"Some accepted local holdings have insufficient or conflicting date evidence "
                        f"({'; '.join(evidence_issues)}). Any displayed rows are only the holdings whose "
                        "dates can be verified; the local dataset is not historically complete."),
        )
    if result is None:
        negative_evidence = None
        if any(item.get("field") == "memberIdentity" for item in plan["constraints"]):
            indexes = {name: evidence_result.columns.index(name) for name in
                       ("member_member", "memberName", "holding_holding", "holdingStart", "holdingEnd")}
            rows_by_holding: dict[str, tuple[str, str, str]] = {}
            for row in evidence_result.rows:
                member_iri = _require_local_iri(row[indexes["member_member"]], "Member")
                if member_iri != plan["referents"]["member"]["iri"]:
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                                       diagnostic="Office negative evidence contains a nonmatching Member identity; no yes/no answer was produced.")
                holding = _require_local_iri(row[indexes["holding_holding"]], "OfficeHolding")
                start_value, start_error = _office_datetime_binding(row[indexes["holdingStart"]])
                end_value, end_error = _office_datetime_binding(row[indexes["holdingEnd"]])
                if start_error or start_value is None or end_error:
                    return PlanOutcome("insufficient_holding_evidence", plan=plan, sparql=answer_query,
                                       diagnostic="A nonoverlapping office holding has incomplete or malformed date evidence; no negative result was produced.")
                rows_by_holding[holding] = (
                    row[indexes["memberName"]].removesuffix("@en"),
                    _display_office_datetime(start_value),
                    _display_office_datetime(end_value) if end_value is not None else "Open-ended (no end date recorded)",
                )
            negative_evidence = QueryResult(
                "select", ("Member", "Holding start", "Holding end"),
                tuple(rows_by_holding[key] for key in sorted(rows_by_holding)),
            )
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=(f"No accepted local holding is recorded overlapping {start} through {end}. "
                        "The dataset does not certify complete historical office coverage, so this is not "
                        "a confirmed historical negative."), result=negative_evidence,
        )
    return PlanOutcome(
        "success", plan=plan, sparql=answer_query, result=result,
        diagnostic=(f"Displayed every locally evidenced accepted holding overlapping {start} through {end}; "
                    "historical completeness is not certified."),
    )


def _bill_sponsorship_coverage_counts(result: QueryResult) -> tuple[int, int]:
    if (result.kind != "select" or not {"billCount", "participationCount"}.issubset(result.columns)
            or len(result.rows) != 1):
        raise NLQError("Bill sponsorship coverage query returned an unexpected aggregate result.")
    indexes = {name: result.columns.index(name) for name in ("billCount", "participationCount")}
    counts = []
    for name in ("billCount", "participationCount"):
        raw = result.rows[0][indexes[name]]
        lexical, _language, datatype = _rdf_literal_parts(raw)
        if datatype != _XSD_INTEGER_IRI or lexical is None or not re.fullmatch(r"[0-9]+", lexical):
            raise NLQError("Bill sponsorship coverage query returned a non-integer count.")
        counts.append(int(lexical))
    return counts[0], counts[1]


def _execute_bill_sponsorship_question(
    plan: dict[str, Any], *, fuseki, supported_predicates,
) -> PlanOutcome:
    member_ref = plan["referents"]["member"]
    mention = member_ref["mention"]
    try:
        resolution_query = member_resolution_query(supported_predicates=supported_predicates)
    except (PlanError, NLQError) as error:
        member_ref["resolution"] = "unsupported_mapping"
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    try:
        resolution_result = fuseki.query(resolution_query)
        if (resolution_result.kind != "select"
                or not {"member", "name"}.issubset(resolution_result.columns)):
            raise NLQError("Member resolution query returned an unexpected result shape.")
        member_iri, member_label = resolve_member(resolution_result, mention)
    except AmbiguousMember as error:
        member_ref.update({"resolution": "ambiguous", "candidates": list(error.candidates)})
        return PlanOutcome("ambiguous", plan=plan, diagnostic=str(error), candidates=error.candidates)
    except NLQError as error:
        state = "not_found" if "No local Member" in str(error) else "source_data_unavailable"
        member_ref["resolution"] = state
        return PlanOutcome(state, plan=plan, diagnostic=str(error))
    member_ref.update({"resolution": "resolved", "iri": member_iri, "label": member_label})

    try:
        plan = validate_plan(plan)
        answer_query = compile_bill_sponsorship_answer_query(
            plan, supported_predicates=supported_predicates,
        )
    except (PlanError, NLQError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    try:
        raw_result = fuseki.query(answer_query)
        if raw_result.kind != "select":
            raise NLQError("Bill sponsorship answer query returned an unexpected result kind.")
    except NLQError as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query, diagnostic=str(error))

    if not raw_result.rows:
        try:
            coverage_query = compile_bill_sponsorship_coverage_query(
                plan, supported_predicates=supported_predicates,
            )
            coverage_result = fuseki.query(coverage_query)
            bill_count, participation_count = _bill_sponsorship_coverage_counts(coverage_result)
        except (PlanError, NLQError) as error:
            return PlanOutcome("unsupported_mapping", plan=plan, sparql=answer_query, diagnostic=str(error))
        if bill_count == 0:
            return PlanOutcome(
                "missing_sponsorship_evidence", plan=plan, sparql=answer_query,
                diagnostic=("No local Bill records are available to establish sponsorship evidence. "
                            "This absence is not evidence that the Member sponsored no Bills."),
            )
        if participation_count == 0:
            return PlanOutcome(
                "missing_sponsorship_evidence", plan=plan, sparql=answer_query,
                diagnostic=("Local Bill records exist, but no LegislativeProcess sponsorship Participation "
                            "evidence is available. No negative sponsorship claim can be made."),
            )
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=("No recorded Bill sponsorship Participation in the local dataset references this "
                        "resolved Member IRI. The loaded Bill data does not certify complete historical coverage."),
        )

    try:
        projection = readable_bill_sponsorship_result(raw_result)
    except NLQError as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query, diagnostic=str(error))
    diagnostics = list(projection.diagnostics)
    truncated = len(raw_result.rows) >= 100
    if truncated:
        diagnostics.append(
            "The local query result reached the 100-row safety cap; additional participation evidence may be omitted."
        )
    if projection.conflicting_evidence:
        status = "conflicting_sponsorship_evidence"
    elif truncated:
        status = "incomplete_sponsorship_evidence"
    elif projection.incomplete_display:
        status = "incomplete_display_evidence"
    elif projection.missing_primary_status:
        status = "incomplete_primary_status_evidence"
    else:
        status = "success"
    diagnostics.append(
        "Bill graphs are optional and the local dataset does not certify complete historical sponsorship coverage."
    )
    return PlanOutcome(
        status, plan=plan, sparql=answer_query, result=projection.result,
        diagnostic=" ".join(diagnostics),
    )


def _dail_ordinal_label(number: int) -> str:
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix} Dáil"


class AmbiguousPoliticalAffiliation(NLQError):
    def __init__(self, mention: str, candidates: tuple[dict[str, str], ...]):
        super().__init__(f"Several reviewed term-scoped political-affiliation identities match “{mention}”; none was selected.")
        self.candidates = candidates


@lru_cache(maxsize=1)
def _reviewed_affiliation_labels() -> dict[str, frozenset[str]]:
    """Load preferred names and reviewed aliases keyed by exact identity IRI."""
    try:
        document = json.loads(_AFFILIATION_DECISIONS_PATH.read_text(encoding="utf-8"))
        identities = document["identities"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise NLQError("The reviewed political-affiliation identity register is unavailable or malformed.") from error
    if not isinstance(identities, list):
        raise NLQError("The reviewed political-affiliation identity register has an invalid identity list.")
    labels_by_iri: dict[str, frozenset[str]] = {}
    for item in identities:
        if (not isinstance(item, dict) or not isinstance(item.get("iri"), str)
                or not item["iri"].startswith("https://data.oireachtas.ie/ie/oireachtas/political-affiliation/")
                or not isinstance(item.get("label"), str) or not item["label"].strip()
                or not isinstance(item.get("aliases"), list)
                or any(not isinstance(alias, str) or not alias.strip() for alias in item["aliases"])):
            raise NLQError("The reviewed political-affiliation identity register contains a malformed identity.")
        iri = item["iri"]
        if iri in labels_by_iri:
            raise NLQError("The reviewed political-affiliation identity register repeats an identity IRI.")
        labels_by_iri[iri] = frozenset((item["label"], *item["aliases"]))
    return labels_by_iri


def _resolve_term_scoped_affiliation(
    result: QueryResult,
    mention: str,
) -> tuple[str, str]:
    if result.kind != "select" or not {"party", "partyLabel", "affiliation", "affiliationLabel"}.issubset(result.columns):
        raise NLQError("The term-scoped affiliation resolver returned an unexpected result shape.")
    if len(result.rows) >= 100:
        raise NLQError("The selected Dáil's party-identity lookup reached the 100-row safety cap.")
    indexes = {name: result.columns.index(name) for name in ("party", "partyLabel", "affiliation", "affiliationLabel")}
    wanted = _normalise_label(mention)
    labels_by_iri = _reviewed_affiliation_labels()
    identities: dict[str, set[str]] = {}
    unlinked_matching_parties: set[str] = set()
    unlabeled_matching_identities: set[str] = set()
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError("The term-scoped affiliation resolver returned a truncated row.")
        party = row[indexes["party"]]
        party_label = row[indexes["partyLabel"]].removesuffix("@en")
        identity = row[indexes["affiliation"]]
        identity_label = row[indexes["affiliationLabel"]].removesuffix("@en")
        _require_local_iri(party, "ParliamentaryParty")
        if identity not in {"—", ""}:
            _require_local_iri(identity, "PoliticalAffiliationIdentity")
            reviewed_labels = labels_by_iri.get(identity)
            if reviewed_labels is None:
                raise NLQError("A term-scoped party links to an identity absent from the reviewed identity register.")
            alias_matches = wanted in {_normalise_label(label) for label in reviewed_labels}
            if identity_label in {"—", ""}:
                if alias_matches or party_label and _normalise_label(party_label) == wanted:
                    unlabeled_matching_identities.add(identity)
            elif _normalise_label(identity_label) == wanted or alias_matches:
                identities.setdefault(identity, set()).add(identity_label)
        elif party_label and _normalise_label(party_label) == wanted:
            unlinked_matching_parties.add(party)

    if len(identities) > 1:
        candidates = tuple(
            {"iri": iri, "label": sorted(labels, key=lambda item: (item.casefold(), item))[0]}
            for iri, labels in sorted(identities.items())
        )
        raise AmbiguousPoliticalAffiliation(mention, candidates)
    if unlinked_matching_parties:
        raise NLQError(
            "A term-scoped ParliamentaryParty label matches the request, but no reviewed PoliticalAffiliationIdentity link is present."
        )
    if unlabeled_matching_identities:
        raise NLQError(
            "A term-scoped party links to a matching reviewed identity, but its English preferred label is missing."
        )
    if identities:
        iri, labels = next(iter(identities.items()))
        if len(labels) != 1:
            raise NLQError("The matching reviewed affiliation identity has conflicting preferred labels.")
        return iri, next(iter(labels))
    if not result.rows:
        raise NLQError("No term-scoped ParliamentaryParty/identity evidence is available for the selected Dáil.")
    raise NLQError(
        f"No reviewed PoliticalAffiliationIdentity matching “{mention}” is linked from a party active in the selected Dáil."
    )


def _parse_member_datetime(value: str, *, what: str) -> datetime:
    datatype = "http://www.w3.org/2001/XMLSchema#dateTime"
    lexical, marker, type_text = value.rpartition("^^<")
    if marker != "^^<" or not type_text.endswith(">") or type_text[:-1] != datatype:
        raise NLQError(f"{what} must be a mapped xsd:dateTime value.")
    if not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})?",
        lexical,
    ):
        raise NLQError(f"{what} is not a valid xsd:dateTime lexical form; temporal overlap is uncertain.")
    try:
        parsed = datetime.fromisoformat(lexical.replace("Z", "+00:00"))
    except ValueError as error:
        raise NLQError(f"{what} is malformed; temporal overlap is uncertain.") from error
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _mapped_member_interval(
    values: set[tuple[str, str, str]],
    *,
    label: str,
) -> tuple[datetime, datetime | None]:
    if len(values) != 1:
        raise NLQError(f"{label} has missing or conflicting date-range evidence; interval overlap is uncertain.")
    range_iri, start_text, end_text = next(iter(values))
    if range_iri in {"—", ""} or start_text in {"—", ""}:
        raise NLQError(f"{label} has no mapped date-range/start; interval overlap is uncertain (not an open start).")
    _require_local_iri(range_iri, "DateRange")
    start = _parse_member_datetime(start_text, what=f"{label} StartDate")
    end = None if end_text in {"—", ""} else _parse_member_datetime(end_text, what=f"{label} EndDate")
    if end is not None and end < start:
        raise NLQError(f"{label} has an EndDate before its StartDate; interval overlap is uncertain.")
    return start, end


def _interval_overlap(
    first: tuple[datetime, datetime | None],
    second: tuple[datetime, datetime | None],
) -> tuple[datetime, datetime | None] | None:
    first_start, first_end = first
    second_start, second_end = second
    if ((first_end is not None and second_start > first_end)
            or (second_end is not None and first_start > second_end)):
        return None
    overlap_start = max(first_start, second_start)
    finite_ends = [end for end in (first_end, second_end) if end is not None]
    overlap_end = min(finite_ends) if finite_ends else None
    if overlap_end is not None and overlap_start > overlap_end:
        return None
    return overlap_start, overlap_end


def _display_member_interval(value: tuple[datetime, datetime | None]) -> str:
    start, end = value
    return f"{start.isoformat()} – {end.isoformat() if end is not None else 'open-ended'}"


def _temporal_member_party_result(
    raw_result: QueryResult,
    plan: dict[str, Any],
    *,
    answer_query: str,
) -> PlanOutcome:
    columns = (
        "member", "memberName", "membership", "membershipRange", "membershipStart", "membershipEnd",
        "episode", "party", "partyLabel", "partyRange", "partyStart", "partyEnd",
        "affiliation", "affiliationLabel",
    )
    if raw_result.kind != "select" or not set(columns).issubset(raw_result.columns):
        return PlanOutcome("execution_failure", plan=plan, sparql=answer_query,
                           diagnostic="The temporal party/representation query returned an unexpected result shape.",
                           request_family="member_relationship_composition")
    if len(raw_result.rows) >= 100:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                           diagnostic="The temporal party/representation query reached the 100-row cap; evidence may be incomplete.",
                           request_family="member_relationship_composition")
    index = {name: raw_result.columns.index(name) for name in columns}
    records: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in raw_result.rows:
        if len(row) <= max(index.values()):
            return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                               diagnostic="A temporal composition row was truncated; overlap cannot be established.",
                               request_family="member_relationship_composition")
        try:
            member_iri = _require_local_iri(row[index["member"]], "Member")
            membership_iri = _require_local_iri(row[index["membership"]], "DailMembership")
            episode_iri = _require_local_iri(row[index["episode"]], "PartyMembershipEpisode")
            party_iri = _require_local_iri(row[index["party"]], "ParliamentaryParty")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                               diagnostic=f"A temporal composition row contains an invalid relationship identity: {error}",
                               request_family="member_relationship_composition")
        key = (member_iri, membership_iri, episode_iri, party_iri)
        entry = records.setdefault(key, {
            "names": set(), "party_labels": set(), "affiliations": {},
            "missing_affiliation": False, "membership_ranges": set(), "party_ranges": set(),
        })
        name = row[index["memberName"]].removesuffix("@en").strip()
        if name not in {"—", ""}:
            entry["names"].add(name)
        party_label = row[index["partyLabel"]].removesuffix("@en").strip()
        if party_label not in {"—", ""}:
            entry["party_labels"].add(party_label)
        identity = row[index["affiliation"]]
        identity_label = row[index["affiliationLabel"]].removesuffix("@en").strip()
        if identity in {"—", ""}:
            entry["missing_affiliation"] = True
        else:
            try:
                _require_local_iri(identity, "PoliticalAffiliationIdentity")
            except NLQError as error:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                                   diagnostic=f"A party record contains an invalid reviewed affiliation identity: {error}",
                                   request_family="member_relationship_composition")
            entry["affiliations"].setdefault(identity, set())
            if identity_label not in {"—", ""}:
                entry["affiliations"][identity].add(identity_label)
        entry["membership_ranges"].add((
            row[index["membershipRange"]], row[index["membershipStart"]], row[index["membershipEnd"]],
        ))
        entry["party_ranges"].add((
            row[index["partyRange"]], row[index["partyStart"]], row[index["partyEnd"]],
        ))

    if not records:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=("No local PartyMembership episode was joined to a DailMembership representing the selected "
                        "constituency occurrence in the selected term. This absence does not establish complete coverage."),
            request_family="member_relationship_composition",
        )

    party_answer = plan["answer"]["referent"] == "affiliation"
    selected_identity = None if party_answer else plan["referents"]["affiliation"].get("iri")
    evidence_by_identity: dict[str, dict[str, Any]] = {}
    evidence_by_member: dict[str, dict[str, Any]] = {}
    for (member_iri, _membership_iri, episode_iri, party_iri), entry in records.items():
        known_identities = set(entry["affiliations"])
        if not party_answer and known_identities and selected_identity not in known_identities:
            continue
        try:
            membership_interval = _mapped_member_interval(
                entry["membership_ranges"], label=f"DailMembership {member_iri}",
            )
            party_interval = _mapped_member_interval(
                entry["party_ranges"], label=f"PartyMembership episode {episode_iri}",
            )
        except NLQError as error:
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic=f"Temporal overlap is uncertain: {error}",
                request_family="member_relationship_composition",
            )
        overlap = _interval_overlap(membership_interval, party_interval)
        if overlap is None:
            continue
        if not known_identities:
            return PlanOutcome(
                "missing_identity_link", plan=plan, sparql=answer_query,
                diagnostic=(f"PartyMembership episode {episode_iri} has an established overlap with representation, "
                            "but no reviewed PoliticalAffiliationIdentity link; no party or filtered Member answer was returned."),
                request_family="member_relationship_composition",
            )
        relevant_identities = {selected_identity} if selected_identity else known_identities
        for identity in relevant_identities:
            labels = entry["affiliations"].get(identity, set())
            if len(labels) != 1:
                return PlanOutcome(
                    "source_data_unavailable", plan=plan, sparql=answer_query,
                    diagnostic=(f"An overlapping reviewed identity {identity} has missing or conflicting English label evidence; "
                                "no partial answer was returned."),
                    request_family="member_relationship_composition",
                )
            names = entry["names"]
            if len(names) != 1:
                return PlanOutcome(
                    "source_data_unavailable", plan=plan, sparql=answer_query,
                    diagnostic=(f"Overlapping Member {member_iri} has missing or conflicting local name evidence; "
                                "no partial answer was returned."),
                    request_family="member_relationship_composition",
                )
            identity_label = next(iter(labels))
            member_name = next(iter(names))
            evidence = (
                f"{member_name} ({member_iri}); affiliation {_display_member_interval(party_interval)}; "
                f"Dáil representation {_display_member_interval(membership_interval)}; "
                f"established overlap {_display_member_interval(overlap)}; episode {episode_iri}; party {party_iri}"
            )
            if party_answer:
                record = evidence_by_identity.setdefault(identity, {"label": identity_label, "evidence": set()})
                if record["label"] != identity_label:
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                                       diagnostic="A reviewed PoliticalAffiliationIdentity has conflicting display labels.",
                                       request_family="member_relationship_composition")
                record["evidence"].add(evidence)
            else:
                record = evidence_by_member.setdefault(member_iri, {"name": member_name, "evidence": set()})
                if record["name"] != member_name:
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=answer_query,
                                       diagnostic="A local Member identity has conflicting display names.",
                                       request_family="member_relationship_composition")
                record["evidence"].add(f"{identity_label}; {evidence}")

    if party_answer and evidence_by_identity:
        result = QueryResult(
            "select", ("Political party", "Political-affiliation identity", "Established overlapping TD evidence"),
            tuple(
                (value["label"], identity, "; ".join(sorted(value["evidence"], key=lambda item: (item.casefold(), item))))
                for identity, value in sorted(evidence_by_identity.items(), key=lambda item: (item[1]["label"].casefold(), item[0]))
            ), raw_result.raw_json,
        )
    elif not party_answer and evidence_by_member:
        result = QueryResult(
            "select", ("TD", "Member identity", "Established affiliation/representation overlap evidence"),
            tuple(
                (value["name"], member_iri, "; ".join(sorted(value["evidence"], key=lambda item: (item.casefold(), item))))
                for member_iri, value in sorted(evidence_by_member.items(), key=lambda item: (item[1]["name"].casefold(), item[0]))
            ), raw_result.raw_json,
        )
    else:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=("No local PartyMembership interval has an established inclusive overlap with the selected "
                        "DailMembership interval for this term/constituency/identity. This does not establish a complete historical negative."),
            request_family="member_relationship_composition",
        )
    return PlanOutcome(
        "success", plan=plan, sparql=answer_query, result=result,
        diagnostic=("Only established inclusive endpoint overlaps are reported. An absent EndDate is preserved as open-ended; "
                    "missing date ranges/starts never count as overlap. PartyMembership and DailMembership retain their separate "
                    "source intervals; local historical source completeness is not certified."),
        request_family="member_relationship_composition",
    )


def _execute_member_party_temporal_composition(
    plan: dict[str, Any],
    *,
    fuseki,
    supported_predicates,
) -> PlanOutcome:
    affiliation = plan["referents"]["affiliation"]
    if "mention" in affiliation:
        try:
            identity_query = compile_party_affiliation_resolution_query(
                plan, supported_predicates=supported_predicates,
            )
        except (PlanError, NLQError) as error:
            affiliation["resolution"] = "unsupported_mapping"
            return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error),
                               request_family="member_relationship_composition")
        try:
            identity_result = fuseki.query(identity_query)
            identity_iri, identity_label = _resolve_term_scoped_affiliation(
                identity_result, affiliation["mention"],
            )
        except AmbiguousPoliticalAffiliation as error:
            affiliation.update({"resolution": "ambiguous", "candidates": list(error.candidates)})
            plan = validate_plan(plan)
            return PlanOutcome("ambiguous", plan=plan, diagnostic=str(error),
                               candidates=error.candidates,
                               request_family="member_relationship_composition")
        except NLQError as error:
            affiliation["resolution"] = "source_data_unavailable"
            plan = validate_plan(plan)
            status = "missing_identity_link" if "no reviewed PoliticalAffiliationIdentity link" in str(error) else "source_data_unavailable"
            return PlanOutcome(status, plan=plan, diagnostic=str(error),
                               request_family="member_relationship_composition")
        affiliation.update({"resolution": "resolved", "iri": identity_iri, "label": identity_label})

    try:
        plan = validate_plan(plan)
        answer_query = compile_member_relationship_composition_query(
            plan, supported_predicates=supported_predicates,
        )
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error),
                           request_family="member_relationship_composition")
    try:
        raw_result = fuseki.query(answer_query)
    except NLQError as error:
        return PlanOutcome("execution_failure", plan=plan, sparql=answer_query,
                           diagnostic=f"The validated temporal party query could not be executed: {error}",
                           request_family="member_relationship_composition")
    return _temporal_member_party_result(raw_result, plan, answer_query=answer_query)


def _execute_member_relationship_composition_plan(
    plan: dict[str, Any],
    *,
    fuseki,
    supported_predicates,
) -> PlanOutcome:
    """Resolve exact term/constituency identities, then execute one graph composition."""
    try:
        mapping = _member_relationship_composition_mapping(
            plan, supported_predicates=supported_predicates,
        )
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome(
            "unsupported_mapping", plan=plan, diagnostic=str(error),
            request_family="member_relationship_composition",
        )
    term_referents = [
        (referent_id, referent)
        for referent_id, referent in plan["referents"].items()
        if referent["type"] == "DailTerm"
    ]
    ambiguous_candidates: list[dict[str, str]] = []
    resolution_failures: list[tuple[str, str]] = []
    for _referent_id, referent in term_referents:
        ordinal = referent["selector"]["number"]
        try:
            query = dail_term_ordinal_resolution_query(
                ordinal, supported_predicates=supported_predicates,
            )
        except (PlanError, NLQError) as error:
            referent["resolution"] = "unsupported_mapping"
            resolution_failures.append(("unsupported_mapping", str(error)))
            continue
        try:
            result = fuseki.query(query)
        except NLQError as error:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append(("source_data_unavailable", str(error)))
            continue
        if result.kind != "select" or "term" not in result.columns:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append((
                "source_data_unavailable",
                f"The local Houses graph returned an unexpected identity response for {_dail_ordinal_label(ordinal)}.",
            ))
            continue
        if len(result.rows) >= 100:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append((
                "source_data_unavailable",
                f"The typed identity lookup for {_dail_ordinal_label(ordinal)} reached the 100-row safety cap.",
            ))
            continue
        term_iris: set[str] = set()
        malformed = False
        for row in result.rows:
            if len(row) <= result.columns.index("term"):
                malformed = True
                break
            try:
                term_iris.add(_require_local_iri(row[result.columns.index("term")], "DailTerm"))
            except NLQError:
                malformed = True
                break
        if malformed:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append((
                "source_data_unavailable",
                f"The Houses graph returned a malformed identity for {_dail_ordinal_label(ordinal)}.",
            ))
        elif not term_iris:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append((
                "source_data_unavailable",
                f"No typed local DailTerm with ordinal {ordinal} is available in the Houses graph.",
            ))
        elif len(term_iris) > 1:
            candidates = [
                {"iri": iri, "label": _dail_ordinal_label(ordinal)}
                for iri in sorted(term_iris)
            ]
            referent.update({"resolution": "ambiguous", "candidates": candidates})
            ambiguous_candidates.extend(candidates)
            resolution_failures.append((
                "ambiguous",
                f"More than one local DailTerm has ordinal {ordinal}; none was selected.",
            ))
        else:
            referent.update({"resolution": "resolved", "iri": next(iter(term_iris))})

    try:
        plan = validate_plan(plan)
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome(
            "validation_failure", plan=plan,
            diagnostic=f"Resolved Member composition was rejected: {error}",
            request_family="member_relationship_composition",
        )
    if any(status == "ambiguous" for status, _diagnostic in resolution_failures):
        return PlanOutcome(
            "ambiguous", plan=plan,
            diagnostic=" ".join(text for status, text in resolution_failures if status == "ambiguous"),
            candidates=tuple(ambiguous_candidates),
            request_family="member_relationship_composition",
        )
    if any(status == "unsupported_mapping" for status, _diagnostic in resolution_failures):
        return PlanOutcome(
            "unsupported_mapping", plan=plan,
            diagnostic=" ".join(text for _status, text in resolution_failures),
            request_family="member_relationship_composition",
        )
    if resolution_failures:
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=" ".join(text for _status, text in resolution_failures),
            request_family="member_relationship_composition",
        )

    resolved_term_iris = [referent["iri"] for _key, referent in term_referents]
    if len(set(resolved_term_iris)) != len(resolved_term_iris):
        for _referent_id, referent in term_referents:
            referent.pop("iri", None)
            referent["resolution"] = "source_data_unavailable"
        plan = validate_plan(plan)
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic="Different requested Dáil ordinals resolved to the same local DailTerm identity; no answer query was run.",
            request_family="member_relationship_composition",
        )

    constituency_refs = [
        (referent_id, referent)
        for referent_id, referent in plan["referents"].items()
        if referent["type"] == "DailConstituency"
    ]
    if constituency_refs:
        constituency_id, constituency = constituency_refs[0]
        relation = next(
            item for item in plan["relations"]
            if item["fact"] == "constituency_in_term" and item["from"] == constituency_id
        )
        term_ref = plan["referents"][relation["to"]]
        ordinal = term_ref["selector"]["number"]
        term_label = _dail_ordinal_label(ordinal)
        try:
            query = constituency_resolution_query(
                constituency["mention"], term_ref["iri"],
                supported_predicates=supported_predicates,
            )
            result = fuseki.query(query)
            if (result.kind != "select"
                    or not {"constituency", "label"}.issubset(result.columns)):
                raise NLQError("The local constituency resolver returned an unexpected response shape.")
            if len(result.rows) >= 100:
                raise NLQError("The term-scoped constituency lookup reached its 100-row safety cap; no identity was selected.")
            constituency_iri, constituency_label = resolve_constituency(
                result, constituency["mention"], term_label=term_label,
            )
        except AmbiguousConstituency as error:
            constituency.update({
                "resolution": "ambiguous", "candidates": list(error.candidates),
            })
            plan = validate_plan(plan)
            return PlanOutcome(
                "ambiguous", plan=plan, diagnostic=str(error),
                candidates=error.candidates,
                request_family="member_relationship_composition",
            )
        except NLQError as error:
            if str(error).startswith("No matching constituency was found"):
                constituency["resolution"] = "not_found"
                plan = validate_plan(plan)
                return PlanOutcome(
                    "not_found", plan=plan, diagnostic=str(error),
                    request_family="member_relationship_composition",
                )
            constituency["resolution"] = "source_data_unavailable"
            plan = validate_plan(plan)
            return PlanOutcome(
                "source_data_unavailable", plan=plan,
                diagnostic=f"The exact constituency identity could not be established: {error}",
                request_family="member_relationship_composition",
            )
        except (PlanError, TypeError, KeyError) as error:
            return PlanOutcome(
                "unsupported_mapping", plan=plan, diagnostic=str(error),
                request_family="member_relationship_composition",
            )
        constituency.update({
            "resolution": "resolved", "iri": constituency_iri,
            "label": constituency_label,
        })

    if mapping["temporal"]:
        try:
            plan = validate_plan(plan)
        except (PlanError, NLQError, TypeError, KeyError) as error:
            return PlanOutcome("validation_failure", plan=plan, diagnostic=str(error),
                               request_family="member_relationship_composition")
        return _execute_member_party_temporal_composition(
            plan, fuseki=fuseki, supported_predicates=supported_predicates,
        )

    try:
        plan = validate_plan(plan)
        answer_query = compile_member_relationship_composition_query(
            plan, supported_predicates=supported_predicates,
        )
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome(
            "unsupported_mapping", plan=plan, diagnostic=str(error),
            request_family="member_relationship_composition",
        )
    try:
        raw_result = fuseki.query(answer_query)
    except NLQError as error:
        return PlanOutcome(
            "execution_failure", plan=plan, sparql=answer_query,
            diagnostic=f"The validated Member relationship query could not be executed: {error}",
            request_family="member_relationship_composition",
        )
    member_id = plan["answer"]["referent"]
    if (raw_result.kind != "select"
            or not {member_id, "memberName"}.issubset(raw_result.columns)):
        return PlanOutcome(
            "execution_failure", plan=plan, sparql=answer_query,
            diagnostic="The Member relationship answer query returned an unexpected result shape.",
            request_family="member_relationship_composition",
        )
    if len(raw_result.rows) >= 100:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic="The Member relationship answer reached the 100-row safety cap; the local result may be incomplete.",
            request_family="member_relationship_composition",
        )
    name_index = raw_result.columns.index("memberName")
    member_index = raw_result.columns.index(member_id)
    names_by_member: dict[str, set[str]] = {}
    for row in raw_result.rows:
        if len(row) <= max(name_index, member_index):
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic="The Member relationship query returned a truncated identity/name row.",
                request_family="member_relationship_composition",
            )
        try:
            member_iri = _require_local_iri(row[member_index], "Member")
        except NLQError as error:
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic=f"The Member relationship query returned an invalid local Member identity: {error}",
                request_family="member_relationship_composition",
            )
        label = row[name_index].removesuffix("@en").strip()
        if label in {"", "—"}:
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic="A Member matching the requested relationship has no readable local name; no partial answer was returned.",
                request_family="member_relationship_composition",
            )
        names_by_member.setdefault(member_iri, set()).add(label)
    if not names_by_member:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=("No matching Member relationship records were returned from the local dataset. "
                        "This absence does not establish a complete historical negative."),
            request_family="member_relationship_composition",
        )
    if any(len(labels) != 1 for labels in names_by_member.values()):
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic="A matching Member identity has conflicting local name evidence; no identity was merged or hidden.",
            request_family="member_relationship_composition",
        )
    rows = tuple(
        (next(iter(names_by_member[iri])), iri)
        for iri in sorted(names_by_member, key=lambda item: (
            next(iter(names_by_member[item])).casefold(), item,
        ))
    )
    result = QueryResult(
        "select", ("Member", "Member identity"), rows, raw_result.raw_json,
    )
    return PlanOutcome(
        "success", plan=plan, sparql=answer_query, result=result,
        diagnostic=("Members are deduplicated by exact RDF identity and matched through the complete selected "
                    "membership/term/constituency graph. Results reflect local records; historical source completeness is not certified."),
        request_family="member_relationship_composition",
    )


def _execute_shared_dail_terms_question(
    question: str,
    *,
    as_of: date,
    fuseki,
    supported_predicates,
    planner_generator_factory,
) -> PlanOutcome:
    """Interpret a closed composable-v2 proposal and dispatch to its reviewed execution path."""
    from .composable_semantic_planner import (
        InvalidComposableDraft,
        InvalidComposableOutput,
        UnsupportedComposableRequest,
        complete_v2_plan,
        parse_composable_plan_output,
        validate_composable_plan_draft,
    )

    family = "composable_semantic"
    generator = None
    try:
        generator = planner_generator_factory()
        output = generator.generate(question)
    except Exception as error:
        return PlanOutcome(
            "planner_failure",
            diagnostic=f"The composable semantic planner could not produce a plan: {error}",
            request_family=family,
            debug_output=format_debug_payload({
                "stage": "semantic planning", "error_type": type(error).__name__,
                "diagnostic": str(error),
            }),
            debug_source="Composable semantic planner",
        )
    finally:
        if generator is not None:
            close = getattr(generator, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    try:
        draft = parse_composable_plan_output(output)
        draft_plan, unsupported_reason = validate_composable_plan_draft(
            draft, question=question,
        )
    except UnsupportedComposableRequest as error:
        return PlanOutcome(
            "unsupported_request", diagnostic=str(error), request_family=family,
            debug_output=format_debug_payload({"draft": output, "diagnostic": str(error)}),
            debug_source="Composable semantic planner",
        )
    except InvalidComposableOutput as error:
        return PlanOutcome(
            "planner_failure", diagnostic=f"The composable planner returned invalid JSON: {error}",
            request_family=family,
            debug_output=format_debug_payload({"diagnostic": str(error)}),
            debug_source="Composable semantic planner",
        )
    except InvalidComposableDraft as error:
        return PlanOutcome(
            "validation_failure", diagnostic=f"The semantic proposal was rejected: {error}",
            request_family=family,
            debug_output=format_debug_payload({"draft": output, "diagnostic": str(error)}),
            debug_source="Composable plan validation",
        )
    except Exception as error:
        return PlanOutcome(
            "planner_failure", diagnostic=f"The composable semantic planner response failed validation: {error}",
            request_family=family,
            debug_output=format_debug_payload({
                "stage": "semantic draft parsing", "error_type": type(error).__name__,
                "diagnostic": str(error),
            }),
            debug_source="Composable semantic planner",
        )

    if draft_plan is None:
        return PlanOutcome(
            "unsupported_request", diagnostic=unsupported_reason,
            request_family=family,
        )
    try:
        plan = complete_v2_plan(draft_plan, as_of=as_of)
        plan = validate_plan(plan)
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome(
            "validation_failure", diagnostic=f"The v2 semantic plan was rejected: {error}",
            request_family=family,
            debug_output=format_debug_payload({"plan": draft_plan, "diagnostic": str(error)}),
            debug_source="Composable plan validation",
        )

    family = plan["family"]
    if family == "member_relationship_composition":
        return _execute_member_relationship_composition_plan(
            plan, fuseki=fuseki, supported_predicates=supported_predicates,
        )

    # Resolve each named Member independently. Whole-question contextual
    # narrowing is deliberately disabled: this family contains no Member-level
    # term/constituency filter that could safely disambiguate either identity.
    resolution_failures: list[tuple[str, str, str]] = []
    ambiguous_candidates: list[dict[str, str]] = []
    member_referents = [
        (referent_id, referent)
        for referent_id, referent in plan["referents"].items()
        if referent["type"] == "Member"
    ]
    for referent_id, referent in member_referents:
        mention = referent["mention"]
        try:
            resolution = resolve_local_entity_label(
                "Member", mention, fuseki,
                supported_predicates=supported_predicates,
            )
        except UnsupportedLocalEntityType as error:
            referent["resolution"] = "unsupported_mapping"
            resolution_failures.append(("unsupported_mapping", mention, str(error)))
            continue
        except NLQError as error:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append(("source_data_unavailable", mention, str(error)))
            continue

        if resolution.state == "unresolved":
            referent["resolution"] = "not_found"
            resolution_failures.append(("not_found", mention, f'No exact local Member identity matches “{mention}”.'))
        elif resolution.state == "ambiguous":
            candidates = [
                {"iri": item.iri, "label": item.label}
                for item in resolution.candidates
            ]
            referent.update({"resolution": "ambiguous", "candidates": candidates})
            ambiguous_candidates.extend(candidates)
            resolution_failures.append((
                "ambiguous", mention,
                f'Several local Member identities match “{mention}”; none was selected.',
            ))
        elif resolution.state == "resolved" and len(resolution.candidates) == 1:
            candidate = resolution.candidates[0]
            referent.update({
                "resolution": "resolved", "iri": candidate.iri,
                "label": candidate.label,
            })
        else:
            referent["resolution"] = "source_data_unavailable"
            resolution_failures.append((
                "source_data_unavailable", mention,
                "The local Member resolver returned an inconsistent identity state.",
            ))

    try:
        plan = validate_plan(plan)
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome(
            "validation_failure", plan=plan,
            diagnostic=f"The resolved v2 semantic plan was rejected: {error}",
            request_family=family,
            debug_output=format_debug_payload({"diagnostic": str(error)}),
            debug_source="Composable plan validation",
        )
    if any(status == "ambiguous" for status, _mention, _diagnostic in resolution_failures):
        return PlanOutcome(
            "ambiguous", plan=plan,
            diagnostic=" ".join(item[2] for item in resolution_failures if item[0] == "ambiguous"),
            candidates=tuple(ambiguous_candidates), request_family=family,
        )
    if any(status == "unsupported_mapping" for status, _mention, _diagnostic in resolution_failures):
        return PlanOutcome(
            "unsupported_mapping", plan=plan,
            diagnostic=" ".join(item[2] for item in resolution_failures),
            request_family=family,
        )
    if any(status == "source_data_unavailable" for status, _mention, _diagnostic in resolution_failures):
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=" ".join(item[2] for item in resolution_failures),
            request_family=family,
        )
    if any(status == "not_found" for status, _mention, _diagnostic in resolution_failures):
        return PlanOutcome(
            "not_found", plan=plan,
            diagnostic=" ".join(item[2] for item in resolution_failures if item[0] == "not_found"),
            request_family=family,
        )

    resolved_iris = [referent["iri"] for _key, referent in member_referents]
    if len(set(resolved_iris)) != 2:
        return PlanOutcome(
            "identity_collision", plan=plan,
            diagnostic=("The two independently resolved Member mentions identify the same local RDF resource; "
                        "no two-Member intersection query was run."),
            request_family=family,
        )

    try:
        answer_query = compile_shared_dail_terms_answer_query(
            plan, supported_predicates=supported_predicates,
        )
        evidence_query = compile_shared_dail_terms_evidence_query(
            plan, supported_predicates=supported_predicates,
        )
    except (PlanError, NLQError, TypeError, KeyError) as error:
        return PlanOutcome(
            "unsupported_mapping", plan=plan, diagnostic=str(error),
            request_family=family,
        )

    try:
        evidence = fuseki.query(evidence_query)
        if (evidence.kind != "select"
                or not {"member", "term"}.issubset(evidence.columns)):
            raise NLQError("Member-term evidence query returned an unexpected result shape.")
        if len(evidence.rows) >= 100:
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic=("The bounded Member-term evidence check reached the 100-row safety cap; "
                            "the intersection cannot be certified from this response."),
                request_family=family,
            )
        evidence_by_member: dict[str, set[str]] = {iri: set() for iri in resolved_iris}
        for row in evidence.rows:
            if len(row) < 2:
                raise NLQError("Member-term evidence query returned a truncated row.")
            member_iri = _require_local_iri(row[evidence.columns.index("member")], "Member")
            term_iri = _require_local_iri(row[evidence.columns.index("term")], "DailTerm")
            if member_iri not in evidence_by_member:
                raise NLQError("Member-term evidence query returned an unrequested Member identity.")
            evidence_by_member[member_iri].add(term_iri)
    except NLQError as error:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=f"Local Dáil-membership evidence could not be established: {error}",
            request_family=family,
        )

    missing_evidence = [
        referent["label"] for _referent_id, referent in member_referents
        if not evidence_by_member[referent["iri"]]
    ]
    if missing_evidence:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=("No queryable recorded DailMembership-to-DailTerm evidence was returned for "
                        + ", ".join(missing_evidence)
                        + ". This absence is not a confirmed no-service finding."),
            request_family=family,
        )

    try:
        raw_result = fuseki.query(answer_query)
    except NLQError as error:
        return PlanOutcome(
            "execution_failure", plan=plan, sparql=answer_query,
            diagnostic=f"The validated shared-term query could not be executed: {error}",
            request_family=family,
        )
    if (raw_result.kind != "select"
            or not {"term", "termLabel", "termNo"}.issubset(raw_result.columns)):
        return PlanOutcome(
            "execution_failure", plan=plan, sparql=answer_query,
            diagnostic="The shared-term answer query returned an unexpected result shape.",
            request_family=family,
        )
    if len(raw_result.rows) >= 100:
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=("The shared-term answer reached the 100-row safety cap; "
                        "the result may be incomplete."),
            request_family=family,
        )

    shared_evidence = evidence_by_member[resolved_iris[0]] & evidence_by_member[resolved_iris[1]]
    labels_by_term: dict[str, str] = {}
    for row in raw_result.rows:
        if len(row) <= max(raw_result.columns.index(name) for name in ("term", "termLabel", "termNo")):
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic="The shared-term answer query returned a truncated evidence row.",
                request_family=family,
            )
        term_iri = _require_local_iri(row[raw_result.columns.index("term")], "DailTerm")
        label_binding = row[raw_result.columns.index("termLabel")]
        label = label_binding.removesuffix("@en")
        if not label.strip() or term_iri not in shared_evidence:
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic=("The answer query did not reconcile to the independently checked shared-term "
                            "identity evidence; no answer was returned."),
                request_family=family,
            )
        previous_label = labels_by_term.get(term_iri)
        if previous_label is not None and previous_label != label:
            return PlanOutcome(
                "source_data_unavailable", plan=plan, sparql=answer_query,
                diagnostic="A DailTerm has conflicting English label evidence.",
                request_family=family,
            )
        labels_by_term[term_iri] = label

    display_rows = tuple(
        (label,) for _iri, label in sorted(
            labels_by_term.items(), key=lambda item: (item[1].casefold(), item[0]),
        )
    )
    result = QueryResult(
        "select", ("Shared Dáil term",), display_rows, raw_result.raw_json,
    )
    diagnostic = (
        "No shared recorded Dáil terms were found. This intersection reflects local membership records only; "
        "historical source completeness is not certified."
        if not display_rows else
        "Returned distinct Dáil terms joined by the same DailTerm RDF identity in both Members' recorded membership paths. "
        "This reflects local recorded memberships; historical source completeness is not certified."
    )
    return PlanOutcome(
        "success", plan=plan, sparql=answer_query, result=result,
        diagnostic=diagnostic, request_family=family,
    )


_MONTHS = {
    name.casefold(): number for number, names in enumerate((
        ("January", "Jan"), ("February", "Feb"), ("March", "Mar"),
        ("April", "Apr"), ("May",), ("June", "Jun"), ("July", "Jul"),
        ("August", "Aug"), ("September", "Sep", "Sept"),
        ("October", "Oct"), ("November", "Nov"), ("December", "Dec"),
    ), start=1) for name in names
}
_TEXT_DATE = re.compile(
    r"\b(?P<day>[0-9]{1,2})(?:st|nd|rd|th)?\s+(?P<month>January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(?P<year>[0-9]{4})\b"
    r"|\b(?P<month_first>January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(?P<day_first>[0-9]{1,2})(?:st|nd|rd|th)?,?\s+(?P<year_first>[0-9]{4})\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"(?<![0-9])(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})(?![0-9])")
_PARTY_REPRESENTATION_INTENT = re.compile(
    r"\b(?:party|parties|political affiliation|affiliated|independent|parliamentary group)\b", re.IGNORECASE,
)
_UNSUPPORTED_PARTY_COMPOSITION_CONDITIONS = re.compile(
    r"\b(?:currently|current|as of|before|after|since|until|between|throughout|"
    r"last month|last year|next month|next year|never|ever|count|how many|at least|"
    r"more than|fewer than|except|excluding|also|committee|minister|office|bill|vote|"
    r"sponsor|independent|parliamentary group)\b"
    r"|\bfrom\s+(?:[0-9]{1,2}\s|(?:19|20)[0-9]{2}\b|January\b|February\b|March\b|April\b|May\b|June\b|July\b|August\b|September\b|October\b|November\b|December\b)"
    r"|\bwhile\s+(?:serving|holding|being|also|a\s+member)\b",
    re.IGNORECASE,
)


def _question_calendar_dates(question: str) -> tuple[list[date], str | None]:
    """Parse only common explicit calendar-date forms; reject impossible dates."""
    found: list[date] = []
    for match in _ISO_DATE.finditer(question):
        try:
            found.append(date(int(match["year"]), int(match["month"]), int(match["day"])))
        except ValueError:
            return found, match.group(0)
    for match in _TEXT_DATE.finditer(question):
        month_text = (match.group("month") or match.group("month_first") or "").casefold()
        year_text = match.group("year") or match.group("year_first")
        day_text = match.group("day") or match.group("day_first")
        month = _MONTHS.get(month_text)
        try:
            if month is None:
                raise ValueError
            found.append(date(int(year_text), month, int(day_text)))
        except (TypeError, ValueError):
            return found, match.group(0)
    return found, None


def _reviewed_affiliation_mention_matches(question: str) -> bool:
    for labels in _reviewed_affiliation_labels().values():
        for label in labels:
            if re.search(r"(?<!\w)" + re.escape(label) + r"(?!\w)", question, re.IGNORECASE):
                return True
    return False


def _without_reviewed_affiliation_mentions(question: str) -> str:
    masked = question
    labels = sorted(
        {label for values in _reviewed_affiliation_labels().values() for label in values},
        key=lambda value: (-len(value), value.casefold()),
    )
    for label in labels:
        masked = re.sub(
            r"(?<!\w)" + re.escape(label) + r"(?!\w)", " ", masked,
            flags=re.IGNORECASE,
        )
    return masked


def _composable_interpretation_preflight(question: str, as_of: date) -> PlanOutcome | None:
    has_representation_scope = bool(
        re.search(r"\b(?:represent(?:ed|s|ing)?|representation|tds?|constituenc(?:y|ies))\b", question, re.IGNORECASE)
        and re.search(r"\b(?:dáil|dail)\b", question, re.IGNORECASE)
    )
    if not has_representation_scope:
        return None
    try:
        has_party_scope = bool(_PARTY_REPRESENTATION_INTENT.search(question)
                               or _reviewed_affiliation_mention_matches(question))
    except NLQError as error:
        return PlanOutcome(
            "unsupported_mapping", diagnostic=str(error), request_family="composable_semantic",
        )
    if not has_party_scope:
        return None

    dates, invalid_date = _question_calendar_dates(question)
    if invalid_date is not None:
        return PlanOutcome(
            "clarification_required",
            diagnostic=f"{invalid_date} is not a valid calendar date. Please provide a real date; no answer query was run.",
            request_family="composable_semantic",
        )
    future_dates = sorted({item for item in dates if item > as_of})
    if future_dates:
        return PlanOutcome(
            "clarification_required",
            diagnostic=(f"The requested date {future_dates[0].isoformat()} is after the configured as-of date "
                        f"{as_of.isoformat()}; clarify whether you intend a future period or an elapsed period. No answer query was run."),
            request_family="composable_semantic",
        )
    if dates:
        return PlanOutcome(
            "unsupported_request",
            diagnostic=("This composition does not support an additional calendar-date filter; no simplified answer was run."),
            request_family="composable_semantic",
        )
    if re.search(r"\b(?:throughout|the whole of|all of|the entire)\s+(?P<year>[0-9]{4})\b", question, re.IGNORECASE):
        year = int(re.search(r"\b(?:throughout|the whole of|all of|the entire)\s+(?P<year>[0-9]{4})\b", question, re.IGNORECASE)["year"])
        try:
            end_of_year = date(year, 12, 31)
        except ValueError:
            end_of_year = as_of
        if end_of_year > as_of:
            return PlanOutcome(
                "clarification_required",
                diagnostic=(f"The requested full-year interval ends after the configured as-of date {as_of.isoformat()}. "
                            "Clarify whether you mean only elapsed days or the whole future-spanning year; no answer query was run."),
                request_family="composable_semantic",
            )
    try:
        from .composable_semantic_planner import _question_dail_ordinals
        ordinals = _question_dail_ordinals(question)
    except ValueError as error:
        return PlanOutcome(
            "clarification_required", diagnostic=f"The Dáil term selector is invalid: {error} No answer query was run.",
            request_family="composable_semantic",
        )
    if not ordinals:
        return PlanOutcome(
            "clarification_required",
            diagnostic="Please specify which numbered Dáil term you mean; this composition does not guess a current or relative term.",
            request_family="composable_semantic",
        )
    if len(ordinals) != 1:
        return PlanOutcome(
            "unsupported_request",
            diagnostic="This composition supports one numbered Dáil term; a multi-term condition cannot be dropped or simplified.",
            request_family="composable_semantic",
        )
    condition_text = _without_reviewed_affiliation_mentions(question)
    if re.search(r"\b(?:independent|parliamentary group)\b", condition_text, re.IGNORECASE):
        return PlanOutcome(
            "unsupported_request",
            diagnostic=("Independent collections and parliamentary groups are not dated ParliamentaryParty affiliation evidence; "
                        "no simplified answer was run."),
            request_family="composable_semantic",
        )
    if _UNSUPPORTED_PARTY_COMPOSITION_CONDITIONS.search(condition_text):
        return PlanOutcome(
            "unsupported_request",
            diagnostic=("The question contains an additional date, temporal, aggregate, or relationship condition that this "
                        "bounded party/representation composition cannot preserve. No simplified answer was run."),
            request_family="composable_semantic",
        )
    return None


def execute_question(
    question: str,
    *,
    as_of: date,
    fuseki,
    supported_predicates,
    semantic_plan_generator_factory=None,
) -> PlanOutcome:
    """Plan, resolve, validate, compile and execute bounded composable slices."""
    from .stage_a import execute_stage_a, parse_stage_a_question

    preflight = _composable_interpretation_preflight(question, as_of)
    if preflight is not None:
        return preflight

    stage_a_request = parse_stage_a_question(question)
    if stage_a_request is not None:
        return execute_stage_a(
            stage_a_request, as_of=as_of, fuseki=fuseki,
            supported_predicates=supported_predicates,
        )
    from .stage_c import handle_stage_c
    stage_c_outcome = handle_stage_c(question, as_of=as_of, fuseki=fuseki,
                                     supported_predicates=supported_predicates)
    if stage_c_outcome is not None:
        return stage_c_outcome
    from .stage_b import handle_stage_b
    stage_b_outcome = handle_stage_b(
        question, as_of=as_of, fuseki=fuseki,
        supported_predicates=supported_predicates,
    )
    if stage_b_outcome is not None:
        return stage_b_outcome
    try:
        plan = plan_question(question, as_of=as_of)
    except UnrecognizedQuestion as error:
        if semantic_plan_generator_factory is None:
            return PlanOutcome("unsupported_capability", diagnostic=str(error))
        return _execute_shared_dail_terms_question(
            question, as_of=as_of, fuseki=fuseki,
            supported_predicates=supported_predicates,
            planner_generator_factory=semantic_plan_generator_factory,
        )
    except PlanError as error:
        return PlanOutcome("unsupported_capability", diagnostic=str(error))
    if plan["referents"].get("participation", {}).get("type") == "BillParticipation":
        return _execute_bill_sponsorship_question(
            plan, fuseki=fuseki, supported_predicates=supported_predicates,
        )
    if plan["referents"].get("holding", {}).get("type") == "OfficeHolding":
        return _execute_office_question(plan, fuseki=fuseki, supported_predicates=supported_predicates)
    if plan["referents"].get("sitting", {}).get("type") == "DebateSitting":
        try:
            query = compile_debate_answer_query(plan, supported_predicates=supported_predicates)
            raw_result = fuseki.query(query)
            if plan["answer"]["kind"] == "boolean":
                if raw_result.kind != "ask":
                    raise NLQError("Debate existence query returned an unexpected result kind.")
                if not raw_result.boolean:
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                       diagnostic="No Seanad sitting was found, but local Debate coverage is not certified complete; absence is not proof of a negative.")
                result = raw_result
            else:
                result = readable_debate_result(raw_result)
                if not result.rows:
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                       diagnostic="No matching actual DebateSitting was found in the local dataset; written-answer records do not establish a sitting and coverage is not certified complete.")
        except (PlanError, NLQError) as error:
            return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
        return PlanOutcome("success", plan=plan, sparql=query, result=result,
                           diagnostic="Matched an actual DebateSitting through its produced DebateRecord and reviewed graph-route chamber identity.")
    if plan["answer"]["referent"] == "affiliation":
        mention = plan["referents"]["member"]["mention"]
        try:
            resolution = fuseki.query(member_resolution_query(supported_predicates=supported_predicates))
            member_iri, member_label = resolve_member(resolution, mention)
        except AmbiguousMember as error:
            plan["referents"]["member"].update({"resolution": "ambiguous", "candidates": list(error.candidates)})
            return PlanOutcome("ambiguous", plan=plan, diagnostic=str(error), candidates=error.candidates)
        except NLQError as error:
            state = "not_found" if "No local Member" in str(error) else "source_data_unavailable"
            plan["referents"]["member"]["resolution"] = state
            return PlanOutcome(state, plan=plan, diagnostic=str(error))
        plan["referents"]["member"].update({"resolution": "resolved", "iri": member_iri, "label": member_label})
        try:
            query = compile_answer_query(plan, supported_predicates=supported_predicates)
            raw_result = fuseki.query(query)
            if not raw_result.rows:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic="No dated parliamentary party-membership evidence was found for this Member in the local dataset.")
            identity_index = raw_result.columns.index("identity")
            label_index = raw_result.columns.index("affiliationLabel")
            if any(len(row) <= identity_index or row[identity_index] in {"—", ""} for row in raw_result.rows):
                return PlanOutcome("missing_identity_link", plan=plan,
                                   diagnostic="Party-membership evidence exists, but no reviewed local affiliation-identity link is present.")
            if any(len(row) <= label_index or row[label_index] in {"—", ""} for row in raw_result.rows):
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic="A reviewed affiliation identity is present, but its preferred label is missing.")
            result = readable_affiliation_result(raw_result)
        except (PlanError, NLQError) as error:
            return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
        return PlanOutcome("success", plan=plan, sparql=query, result=result,
                           diagnostic="Affiliations are grouped by reviewed local identity; dated source episodes remain separate.")
    try:
        term_result = fuseki.query(previous_dail_term_query(as_of, supported_predicates=supported_predicates))
        previous_term, current_term = resolve_previous_dail(term_result, as_of)
    except NLQError as error:
        return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=str(error))
    plan["referents"]["term"]["resolution"] = "resolved"
    plan["referents"]["term"]["iri"] = previous_term
    plan["referents"]["term"]["asOfEvidence"] = as_of.isoformat()
    try:
        constituency_result = fuseki.query(constituency_resolution_query(
            plan["referents"]["constituency"]["mention"], previous_term,
            supported_predicates=supported_predicates,
        ))
        constituency, label = resolve_constituency(
            constituency_result, plan["referents"]["constituency"]["mention"],
        )
    except AmbiguousConstituency as error:
        plan["referents"]["constituency"]["resolution"] = "ambiguous"
        plan["referents"]["constituency"]["candidates"] = list(error.candidates)
        return PlanOutcome("ambiguous", plan=plan, diagnostic=str(error), candidates=error.candidates)
    except NLQError as error:
        plan["referents"]["constituency"]["resolution"] = "not_found"
        return PlanOutcome("not_found", plan=plan, diagnostic=str(error))
    plan["referents"]["constituency"].update({"resolution": "resolved", "iri": constituency, "label": label})
    try:
        query = compile_answer_query(
            plan, previous_term, constituency, supported_predicates=supported_predicates,
        )
        raw_result = fuseki.query(query)
        result = readable_member_result(raw_result)
    except (PlanError, NLQError) as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error))
    return PlanOutcome(
        "success", plan=plan, sparql=query, result=result,
        diagnostic=f"Resolved previous Dáil {previous_term}; current Dáil {current_term}.",
    )
