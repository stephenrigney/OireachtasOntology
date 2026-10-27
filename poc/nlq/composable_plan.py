"""Small typed graph plans and deterministic Q06/Q09 compilation.

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

from rdflib import URIRef

from .contract import load_query_contract
from .errors import NLQError
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
    """Interpret the bounded Q06 affiliation and Q09 representation families."""
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


def compile_answer_query(plan: dict[str, Any], term_iri: str | None = None,
                         constituency_iri: str | None = None, *, supported_predicates) -> str:
    plan = validate_plan(plan)
    refs = plan["referents"]
    if refs[plan["answer"]["referent"]]["type"] == "PoliticalAffiliationIdentity":
        return compile_affiliation_answer_query(plan, supported_predicates=supported_predicates)
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


def execute_question(question: str, *, as_of: date, fuseki, supported_predicates) -> PlanOutcome:
    """Plan, resolve, validate, compile and execute the bounded Q06/Q09 capabilities."""
    try:
        plan = plan_question(question, as_of=as_of)
    except PlanError as error:
        return PlanOutcome("unsupported_capability", diagnostic=str(error))
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
