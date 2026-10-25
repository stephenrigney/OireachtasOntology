"""Small typed graph plans and deterministic Q09 compilation.

The browser uses this replacement plan path.  Plans contain semantic relation
IDs only; every query below is compiled from this module's reviewed mapping
table, never from question text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .contract import load_query_contract
from .errors import NLQError
from .results import QueryResult
from .safety import validate_sparql


PLAN_VERSION = 2
_PLAN_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "specs" / "composable-query-plan-contract.json"
_PLAN_CONTRACT = json.loads(_PLAN_CONTRACT_PATH.read_text(encoding="utf-8"))
_Q09_FACTS = {
    relation["id"]: (relation["subjectType"], relation["objectType"])
    for relation in _PLAN_CONTRACT["relations"]
}
_Q09_RELATION_MAPPINGS = {relation["id"]: relation for relation in _PLAN_CONTRACT["relations"]}
_PREFIXES = """PREFIX agents: <https://data.oireachtas.ie/ontology#>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
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


def _require_local_iri(value: str, what: str) -> str:
    if (not isinstance(value, str) or not value.startswith("https://data.oireachtas.ie/")
            or any(character.isspace() for character in value) or any(mark in value for mark in "<>\"{}|\\^`")):
        raise NLQError(f"Resolved {what} is not a local Oireachtas resource IRI.")
    return value


def _normalise_label(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in value).split())


def plan_question(question: str, *, as_of: date) -> dict[str, Any]:
    """Interpret the bounded previous-Dáil representation question family."""
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
    if not isinstance(plan, dict) or set(plan) != {"version", "asOf", "referents", "relations", "answer"}:
        raise PlanError("Plan must have exactly version, asOf, referents, relations, and answer.")
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
    term = refs.get("term", {})
    constituency = refs.get("constituency", {})
    if (term.get("type") != "DailTerm"
            or term.get("selector") != {"kind": "previousTerm", "house": "Dail"}
            or constituency.get("type") != "DailConstituency"
            or not isinstance(constituency.get("mention"), str)
            or not constituency["mention"].strip()):
        raise PlanError("Q09 requires a previous-Dáil selector and a named term-scoped constituency.")
    if not isinstance(plan["relations"], list) or not plan["relations"]:
        raise PlanError("relations must be a non-empty list.")
    seen = set()
    for relation in plan["relations"]:
        if not isinstance(relation, dict) or set(relation) != {"id", "fact", "from", "to"}:
            raise PlanError("Relations require exactly id, fact, from, and to.")
        if relation["id"] in seen:
            raise PlanError("Relation IDs must be unique.")
        seen.add(relation["id"])
        if relation["fact"] not in _Q09_FACTS:
            raise PlanError(f"Unsupported semantic mapping: {relation['fact']!r}.")
        if relation["from"] not in refs or relation["to"] not in refs:
            raise PlanError("Relation refers to an unknown referent.")
        subject_type, object_type = _Q09_FACTS[relation["fact"]]
        if (refs[relation["from"]]["type"], refs[relation["to"]]["type"]) != (subject_type, object_type):
            raise PlanError(f"Invalid referent types for relation {relation['fact']!r}.")
    answer = plan["answer"]
    if (not isinstance(answer, dict) or answer.get("kind") != "entities"
            or answer.get("referent") not in refs or refs[answer["referent"]]["type"] != "Member"
            or answer.get("distinctBy") != "identity" or answer.get("display") != ["name"]):
        raise PlanError("Q09 answer must return distinct Member identities with readable names.")
    return plan


def _query(text: str, supported_predicates) -> str:
    return validate_sparql(text, supported_predicates=supported_predicates)


def _reviewed_predicate(fact: str) -> str:
    mapping = _Q09_RELATION_MAPPINGS.get(fact)
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


def compile_answer_query(plan: dict[str, Any], term_iri: str, constituency_iri: str, *, supported_predicates) -> str:
    plan = validate_plan(plan)
    term_iri = _require_local_iri(term_iri, "HouseTerm")
    constituency_iri = _require_local_iri(constituency_iri, "constituency")
    refs = plan["referents"]
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


def execute_question(question: str, *, as_of: date, fuseki, supported_predicates) -> PlanOutcome:
    """Plan, resolve, validate, compile and execute the bounded Q09 capability."""
    try:
        plan = plan_question(question, as_of=as_of)
    except PlanError as error:
        return PlanOutcome("unsupported_capability", diagnostic=str(error))
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
