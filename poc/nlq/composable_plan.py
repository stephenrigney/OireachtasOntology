"""Small typed graph plans and deterministic bounded query compilation.

The browser uses this replacement plan path.  Plans contain semantic relation
IDs only; every query below is compiled from this module's reviewed mapping
table, never from question text.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
from .results import QueryResult
from .safety import validate_sparql


PLAN_VERSION = 2
_PLAN_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "specs" / "composable-query-plan-contract.json"
_PLAN_CONTRACT = json.loads(_PLAN_CONTRACT_PATH.read_text(encoding="utf-8"))
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


@dataclass(frozen=True)
class PlanOutcome:
    status: str
    plan: dict[str, Any] | None = None
    diagnostic: str | None = None
    candidates: tuple[dict[str, str], ...] = ()
    sparql: str | None = None
    result: QueryResult | None = None


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
    if refs["member"] != {"type": "Member", "answer": True}:
        raise PlanError("Q35 must return Member identities as its answer referent.")
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
    if not isinstance(constraints, list) or len(constraints) != 1:
        raise PlanError("Q35 requires exactly one inclusive office-holding overlap constraint.")
    constraint = constraints[0]
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
        raise PlanError("This question is outside the supported previous-Dáil representation pattern.")
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
    """Resolve Q23's two reviewed edges without inventing a Bill→process edge."""
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
    if (ownership.get("association") != "same_named_graph_co_ownership"
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


def resolve_constituency(result: QueryResult, mention: str) -> tuple[str, str]:
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
        raise NLQError(f"No matching constituency was found in the previous Dáil for “{mention}”.")
    if len(candidates) != 1:
        raise AmbiguousConstituency(mention, tuple({"iri": iri, "label": candidates[iri]} for iri in sorted(candidates)))
    iri = next(iter(candidates))
    return iri, candidates[iri]


class AmbiguousConstituency(NLQError):
    def __init__(self, mention: str, candidates: tuple[dict[str, str], ...]):
        super().__init__(f"Several constituencies named “{mention}” exist in the previous Dáil.")
        self.candidates = candidates


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
    query = _PREFIXES + f'''SELECT DISTINCT ?member_member ?memberName ?holding_holding ?holdingStart ?holdingEnd WHERE {{
  GRAPH ?memberGraph {{
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
    query = _PREFIXES + f'''SELECT DISTINCT ?member_member ?memberName ?holding_holding ?holdingDateRange ?holdingStart ?holdingEnd WHERE {{
  GRAPH ?memberGraph {{
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
        has_evidence, overlapping_holdings, evidence_issues = inspect_office_holding_evidence(
            evidence_result, plan,
        )
    except NLQError as error:
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=f"Accepted local holding evidence could not be checked: {error}",
        )
    if not has_evidence:
        return PlanOutcome(
            "source_data_unavailable", plan=plan,
            diagnostic=("No accepted Member-owned OfficeHolding record for this reviewed office "
                        "is present in the local dataset; historical tenure cannot be determined."),
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
        return PlanOutcome(
            "source_data_unavailable", plan=plan, sparql=answer_query,
            diagnostic=(f"No accepted local holding is recorded overlapping {start} through {end}. "
                        "The dataset does not certify complete historical office coverage, so this is not "
                        "a confirmed historical negative."),
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


def execute_question(question: str, *, as_of: date, fuseki, supported_predicates) -> PlanOutcome:
    """Plan, resolve, validate, compile and execute bounded composable slices."""
    from .stage_a import execute_stage_a, parse_stage_a_question

    stage_a_request = parse_stage_a_question(question)
    if stage_a_request is not None:
        return execute_stage_a(
            stage_a_request, as_of=as_of, fuseki=fuseki,
            supported_predicates=supported_predicates,
        )
    from .stage_b import handle_stage_b
    stage_b_outcome = handle_stage_b(
        question, as_of=as_of, fuseki=fuseki,
        supported_predicates=supported_predicates,
    )
    if stage_b_outcome is not None:
        return stage_b_outcome
    try:
        plan = plan_question(question, as_of=as_of)
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
