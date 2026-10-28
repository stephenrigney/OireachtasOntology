"""Reviewed, bounded member and House query primitives for campaign Stage A.

This module deliberately shares a small set of RDF patterns across question
families. It is not an ontology layer: every predicate, class and graph route
is checked against the query-schema contract before compilation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
import unicodedata

from rdflib import Literal, URIRef

from .composable_plan import PlanOutcome, _PREFIXES, _query, _require_local_iri
from .contract import load_query_contract
from .errors import NLQError
from .results import QueryResult


@dataclass(frozen=True)
class StageARequest:
    family: str
    mention: str | None = None
    house: str | None = None
    term: str | None = None
    detail: str | None = None


def parse_stage_a_question(question: str) -> StageARequest | None:
    """Recognise the approved Stage A linguistic families, not individual IDs."""
    text = question.strip().rstrip("?.! ")
    if re.match(r"^who is (?:the )?(?:current |present )?(?:chair|minister|taoiseach|tanaiste|president|secretary|leader)\b", text, re.IGNORECASE):
        return None
    patterns = (
        ("house_terms", r"when did each dáil start and finish|dates? of (?:the )?dáil terms"),
        ("term_count", r"how many dáil terms are listed in the houses data"),
        ("term_count", r"how many dáil terms has (?P<member>.+?) served(?: in)?"),
        ("previous_service", r"was (?P<member>.+?) (?:a )?td in the previous dáil term"),
        ("dail_duration", r"how long was (?P<member>.+?) (?:a )?deputy"),
        ("seanad_entry", r"when did (?P<member>.+?) become a senator"),
        ("seanad_representation", r"which (?:panel|constituency|representation) did (?P<member>.+?) represent in the (?P<term>[0-9]+(?:st|nd|rd|th) seanad)"),
        ("current_collection", r"what party is (?:senator )?(?P<member>.+?) a member of"),
        ("current_collection", r"what party does (?P<member>.+?) belong to now"),
        ("committee_boolean", r"was (?P<member>.+?) a member of the (?P<detail>.+? committee(?: on .+| .+)?)"),
        ("committee_count", r"how many committees was (?P<member>.+?) a member of"),
        ("dail_all", r"which members named (?P<member>.+?) served in the dáil"),
        ("member_lookup", r"who is (?P<member>(?:deputy |senator )?[\wÀ-ÖØ-öø-ÿ'’-]+(?: [\wÀ-ÖØ-öø-ÿ'’-]+){0,3})|find (?P<member2>.+?)'s full name(?: for me)?|find (?P<member3>.+?)'s full name for me|full name of deputy (?P<member4>.+)|what is the full name of (?P<member5>.+)"),
    )
    normalized = unicodedata.normalize("NFC", text).casefold()
    for family, expression in patterns:
        match = re.fullmatch(expression, normalized, re.IGNORECASE)
        if match:
            values = {key: value for key, value in match.groupdict().items() if value}
            # Retrieve values from original text using the case-insensitive match
            # against NFC text; the regex positions remain aligned for these forms.
            original = unicodedata.normalize("NFC", text)
            original_match = re.fullmatch(expression, original, re.IGNORECASE)
            if original_match:
                values = {key: value for key, value in original_match.groupdict().items() if value}
            mention = values.get("member") or values.get("member2") or values.get("member3") or values.get("member4") or values.get("member5")
            return StageARequest(family, mention=mention, term=values.get("term"), detail=values.get("detail"))
    return None


def _contract_parts():
    contract = load_query_contract()
    families = {item["id"]: item["graph"] for item in contract["graphFamilies"]}
    return contract, families


def _predicate(qname: str) -> str:
    contract, _ = _contract_parts()
    if qname not in contract["queryableProperties"]:
        raise NLQError(f"Reviewed predicate {qname!r} is not queryable.")
    return qname


def _type(qname: str) -> str:
    contract, _ = _contract_parts()
    if qname not in contract["queryableClasses"]:
        raise NLQError(f"Reviewed RDF type {qname!r} is not queryable.")
    return qname


def _graph(family: str) -> str:
    _, families = _contract_parts()
    graph = families.get(family)
    if not isinstance(graph, dict):
        raise NLQError(f"Reviewed graph family {family!r} is unavailable.")
    if graph.get("kind") == "fixed":
        return graph["iri"]
    raise NLQError(f"Graph family {family!r} requires its reviewed resource route.")


_STAGE_A_PATTERNS = {
    "member_lookup": ("member-description",),
    "previous_service": ("member-house-membership", "house-term-temporal-reference"),
    "dail_duration": ("member-house-membership",),
    "term_count": ("member-house-membership", "house-term-description"),
    "seanad_entry": ("member-house-membership", "constituency-term-occurrence"),
    "seanad_representation": ("member-house-membership", "representation-reference", "constituency-term-occurrence"),
    "current_collection": ("member-collection-membership", "party-term-occurrence"),
    "committee_boolean": ("committee-membership-reference", "committee-description", "house-term-temporal-reference"),
    "committee_count": ("committee-membership-reference",),
    "house_terms": ("house-term-description", "house-term-temporal-reference"),
    "dail_all": ("member-description", "member-house-membership"),
}


def _reviewed_stage_a_family(family: str) -> None:
    """Fail closed against the live queryability, emitted-pattern and join contract."""
    from .composable_plan import _RELATION_MAPPINGS

    contract = load_query_contract()
    patterns = {item.get("id"): item for item in contract.get("emittedRdfPatterns", [])}
    family_rows = {item.get("id"): item for item in contract.get("graphFamilies", [])}
    families = {key: value.get("graph") for key, value in family_rows.items()}
    qclasses, qprops = set(contract.get("queryableClasses", [])), set(contract.get("queryableProperties", []))
    for pattern_id in _STAGE_A_PATTERNS.get(family, ()):
        pattern = patterns.get(pattern_id)
        if not pattern or pattern.get("availability") != "emitted" or pattern.get("queryableInLocalNlq") is not True:
            raise NLQError(f"Reviewed Stage A pattern {pattern_id!r} is unavailable or not queryable.")
        if pattern.get("graphFamily") not in families:
            raise NLQError(f"Reviewed Stage A pattern {pattern_id!r} has no graph owner.")
        if not family_rows[pattern["graphFamily"]].get("owner") or not family_rows[pattern["graphFamily"]].get("availability"):
            raise NLQError(f"Reviewed Stage A pattern {pattern_id!r} has incomplete graph ownership metadata.")
        for triple in pattern.get("triples", []):
            for term in triple:
                if ":" not in term or term.startswith("?") or term.startswith('"'):
                    continue
                if term in {"rdf:type"}:
                    if term not in qprops:
                        raise NLQError(f"Reviewed predicate {term!r} is unavailable.")
                elif term in qprops or term in qclasses:
                    continue
                elif any(operator in term for operator in (" or ", " and ")) and all(
                        part in qclasses for part in re.split(r"\s+(?:or|and)\s+", term)):
                    continue
                else:
                    raise NLQError(f"Reviewed pattern {pattern_id!r} contains unavailable term {term!r}.")
    required_join_patterns = set(_STAGE_A_PATTERNS.get(family, ()))
    for relation in _RELATION_MAPPINGS.values():
        if relation.get("patternId") not in required_join_patterns:
            continue
        pattern = patterns.get(relation.get("patternId"))
        if not pattern or not any(len(triple) == 3 and triple[1] == relation.get("predicate")
                                  for triple in pattern.get("triples", [])):
            raise NLQError(f"Reviewed emitted pattern does not assert relation predicate for {relation.get('id')!r}.")
        if relation.get("subjectGraph") not in families or relation.get("objectGraph") not in families:
            raise NLQError(f"Reviewed relation {relation.get('id')!r} has unavailable graph ownership.")
        if relation.get("subjectGraph") == relation.get("objectGraph"):
            continue
        join = next((item for item in contract.get("crossGraphJoins", [])
                     if item.get("predicate") == relation.get("predicate")
                     and item.get("fromGraphFamily") == relation.get("subjectGraph")
                     and item.get("toGraphFamily") == relation.get("objectGraph")), None)
        if not join or not join.get("joinKey") or join.get("predicate") not in qprops:
            raise NLQError(f"Reviewed cross-graph join for {relation.get('id')!r} is unavailable.")


def _member_graph_prefix() -> str:
    _, families = _contract_parts()
    return families["member-records"]["iriTemplate"].split("{", 1)[0]


def _member_lookup_query(mention: str, *, supported_predicates) -> str:
    label = _predicate("foaf:name")
    member_type = _type("agents:Member")
    prefix = _member_graph_prefix()
    needle = Literal(mention).n3()
    query = _PREFIXES + f'''SELECT DISTINCT ?member ?name WHERE {{
  GRAPH ?memberGraph {{ ?member a {member_type} ; {label} ?name . }}
  FILTER(STRSTARTS(STR(?memberGraph), {Literal(prefix).n3()}))
  FILTER(CONTAINS(LCASE(STR(?name)), LCASE(STR({needle}))))
}} LIMIT 100'''
    return _query(query, supported_predicates)


def _member_service_query(member_iri: str, house: str, *, supported_predicates) -> str:
    member = _require_local_iri(member_iri, "Member")
    contract, families = _contract_parts()
    member_type = _type("agents:Member")
    membership_type = _type("members:DailMembership" if house == "Dail" else "members:SeanadMembership")
    has_membership = _predicate("members:hasMembersMembership")
    in_term = _predicate("members:inHouseTerm")
    term_type = _type(f"agents:{house}Term")
    term_link = _predicate("agents:termOf")
    period_link = _predicate("dct:temporal")
    start_pred = _predicate("dcat:startDate")
    end_pred = _predicate("dcat:endDate")
    term_graph = families["houses"]["iri"]
    name_pred = _predicate("foaf:name")
    representation = _predicate("members:isRepresentativeFrom")
    graph_prefix = _member_graph_prefix()
    query = _PREFIXES + f'''SELECT DISTINCT ?member ?name ?membership ?term ?termLabel ?termStart ?termEnd ?membershipStart ?membershipEnd ?representation ?representationLabel WHERE {{
  GRAPH ?memberGraph {{
    VALUES ?member {{ <{member}> }}
    ?member a {member_type} ; {name_pred} ?name ; {has_membership} ?membership .
    ?membership a {membership_type} ; {in_term} ?term .
    OPTIONAL {{ ?membership {representation} ?representation . }}
    OPTIONAL {{ ?membership members:hasMembershipDateRange ?membershipRange .
      ?membershipRange a members:DateRange .
      OPTIONAL {{ ?membershipRange members:StartDate ?membershipStart . }}
      OPTIONAL {{ ?membershipRange members:EndDate ?membershipEnd . }}
    }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {Literal(graph_prefix).n3()}))
  GRAPH <{term_graph}> {{
    ?term a {term_type} ; skos:prefLabel ?termLabel ; {term_link} ?house ; {period_link} ?period .
    ?period a dct:PeriodOfTime .
    ?period {start_pred} ?termStart . OPTIONAL {{ ?period {end_pred} ?termEnd . }}
  }}
}} ORDER BY ?membershipStart ?term'''
    return _query(query, supported_predicates)


def _member_term_count_query(member_iri: str, *, supported_predicates) -> str:
    """Count service-linked term identities without requiring descriptive metadata."""
    member = _require_local_iri(member_iri, "Member")
    prefix = _member_graph_prefix()
    graph = _predicate("members:hasMembersMembership")
    in_term = _predicate("members:inHouseTerm")
    membership_type = _type("members:DailMembership")
    member_type = _type("agents:Member")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?term WHERE {{
  GRAPH ?memberGraph {{
    <{member}> a {member_type} ; {graph} ?membership .
    ?membership a {membership_type} ; {in_term} ?term .
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {Literal(prefix).n3()}))
}}''', supported_predicates)


def _committee_count_query(member_iri: str, *, supported_predicates) -> str:
    """Count membership-linked Committee IRIs independent of owner descriptions."""
    member = _require_local_iri(member_iri, "Member")
    prefix = _member_graph_prefix()
    return _query(_PREFIXES + f'''SELECT DISTINCT ?committee WHERE {{
  GRAPH ?memberGraph {{
    <{member}> a {_type("agents:Member")} ; {_predicate("members:hasMembersMembership")} ?membership .
    ?membership a {_type("members:CommitteeMembership")} ; {_predicate("members:isCommitteeMembershipOf")} ?committee .
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {Literal(prefix).n3()}))
}}''', supported_predicates)


def _committee_query(member_iri: str, *, supported_predicates) -> str:
    member = _require_local_iri(member_iri, "Member")
    has_membership = _predicate("members:hasMembersMembership")
    member_type = _type("agents:Member")
    committee_membership_type = _type("members:CommitteeMembership")
    committee_type = _type("members:Committee")
    link = _predicate("members:isCommitteeMembershipOf")
    term_link = _predicate("members:committeeInHouseTerm")
    graph_prefix = _member_graph_prefix()
    committee_graph = _graph("committees")
    houses_graph = _graph("houses")
    committee_range = _predicate("members:hasCommitteeDateRange")
    date_range_type = _type("members:DateRange")
    membership_range = _predicate("members:hasMembershipDateRange")
    range_start = _predicate("members:StartDate")
    range_end = _predicate("members:EndDate")
    temporal = _predicate("dct:temporal")
    term_start = _predicate("dcat:startDate")
    term_end = _predicate("dcat:endDate")
    query = _PREFIXES + f'''SELECT DISTINCT ?membership ?committee ?label ?term ?start ?end ?termStart ?termEnd WHERE {{
  GRAPH ?memberGraph {{
    <{member}> a {member_type} ; {has_membership} ?membership .
    ?membership a {committee_membership_type} ; {link} ?committee .
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {Literal(graph_prefix).n3()}))
  OPTIONAL {{ GRAPH <{committee_graph}> {{
    ?committee a {committee_type} .
    OPTIONAL {{ ?committee {term_link} ?term . }}
    OPTIONAL {{ ?committee skos:prefLabel ?label . }}
    OPTIONAL {{ ?committee {committee_range} ?committeeDates . ?committeeDates a {date_range_type} ; {range_start} ?start . OPTIONAL {{ ?committeeDates {range_end} ?end . }} }}
  }} }}
  OPTIONAL {{ GRAPH <{houses_graph}> {{
    ?term a ?termType ; dct:temporal ?termDates .
    VALUES ?termType {{ agents:DailTerm agents:SeanadTerm }}
    ?termDates a dct:PeriodOfTime .
    ?termDates {term_start} ?termStart . OPTIONAL {{ ?termDates {term_end} ?termEnd . }}
  }} }}
}} ORDER BY ?term ?label ?membership'''
    return _query(query, supported_predicates)


def _committee_catalogue_query(*, supported_predicates) -> str:
    """Resolve an unscoped Committee name from owner evidence before Member matching."""
    _, families = _contract_parts()
    committee_graph = _graph("committees")
    houses_graph = _graph("houses")
    committee_type = _type("members:Committee")
    term_link = _predicate("members:committeeInHouseTerm")
    committee_range = _predicate("members:hasCommitteeDateRange")
    date_range_type = _type("members:DateRange")
    start = _predicate("members:StartDate")
    end = _predicate("members:EndDate")
    temporal = _predicate("dct:temporal")
    term_start = _predicate("dcat:startDate")
    term_end = _predicate("dcat:endDate")
    query = _PREFIXES + f'''SELECT DISTINCT ?committee ?label ?term ?start ?end ?termStart ?termEnd WHERE {{
  GRAPH <{committee_graph}> {{
    ?committee a {committee_type} .
    OPTIONAL {{ ?committee {term_link} ?term . }}
    OPTIONAL {{ ?committee skos:prefLabel ?label . }}
    OPTIONAL {{ ?committee {committee_range} ?range . ?range a {date_range_type} . OPTIONAL {{ ?range {start} ?start . }} OPTIONAL {{ ?range {end} ?end . }} }}
  }}
  OPTIONAL {{ GRAPH <{houses_graph}> {{ ?term dct:temporal ?period . ?period a dct:PeriodOfTime . OPTIONAL {{ ?period {term_start} ?termStart . }} OPTIONAL {{ ?period {term_end} ?termEnd . }} }} }}
}} ORDER BY ?label ?term'''
    return _query(query, supported_predicates)


def _collection_query(member_iri: str, *, supported_predicates) -> str:
    member = _require_local_iri(member_iri, "Member")
    contract, families = _contract_parts()
    graph_prefix = _member_graph_prefix()
    member_type = _type("agents:Member")
    member_link = _predicate("members:hasMembersMembership")
    member_of = _predicate("members:memberOfCollection")
    range_link = _predicate("members:hasMembershipDateRange")
    start = _predicate("members:StartDate")
    end = _predicate("members:EndDate")
    containing_membership = _predicate("members:inOireachtasMembership")
    in_term = _predicate("members:inHouseTerm")
    term_graph = families["houses"]["iri"]
    temporal = _predicate("dct:temporal")
    term_start = _predicate("dcat:startDate")
    term_end = _predicate("dcat:endDate")
    collection_graph = families["parties"]["iri"]
    return _query(_PREFIXES + f'''SELECT DISTINCT ?record ?collection ?collectionType ?label ?start ?end ?ownerMembership ?ownerMembershipStart ?ownerMembershipEnd ?ownerTerm ?ownerTermStart ?ownerTermEnd WHERE {{
  GRAPH ?memberGraph {{
    <{member}> a {member_type} ; {member_link} ?record .
    ?record a members:ParliamentaryCollectionMembership ; {member_of} ?collection .
    OPTIONAL {{ ?record {range_link} ?dateRange . ?dateRange a members:DateRange . OPTIONAL {{ ?dateRange {start} ?start . }} OPTIONAL {{ ?dateRange {end} ?end . }} }}
    OPTIONAL {{ ?record {containing_membership} ?ownerMembership . ?ownerMembership {in_term} ?ownerTerm . }}
    OPTIONAL {{ ?ownerMembership {range_link} ?ownerRange . ?ownerRange a members:DateRange . OPTIONAL {{ ?ownerRange {start} ?ownerMembershipStart . }} OPTIONAL {{ ?ownerRange {end} ?ownerMembershipEnd . }} }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {Literal(graph_prefix).n3()}))
  GRAPH <{collection_graph}> {{
    {{ ?collection a members:ParliamentaryParty . BIND(members:ParliamentaryParty AS ?collectionType) }}
    UNION
    {{ ?collection a members:IndependentMemberCollection . BIND(members:IndependentMemberCollection AS ?collectionType) }}
    OPTIONAL {{ ?collection skos:prefLabel ?label . FILTER(LANG(?label) = "en") }}
  }}
  OPTIONAL {{ GRAPH <{term_graph}> {{ ?ownerTerm dct:temporal ?ownerPeriod . OPTIONAL {{ ?ownerPeriod {term_start} ?ownerTermStart . }} OPTIONAL {{ ?ownerPeriod {term_end} ?ownerTermEnd . }} }} }}
}} ORDER BY ?start ?collection''', supported_predicates)


def _term_query(house: str, *, supported_predicates) -> str:
    graph = _graph("houses")
    term_type = _type(f"agents:{house}Term")
    temporal = _predicate("dct:temporal")
    start = _predicate("dcat:startDate")
    end = _predicate("dcat:endDate")
    term_no = _predicate("agents:termNo")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?term ?label ?number ?start ?end WHERE {{
  GRAPH <{graph}> {{
    ?term a {term_type} ; skos:prefLabel ?label ; {term_no} ?number ; {temporal} ?period .
    ?period a dct:PeriodOfTime .
    ?period {start} ?start . OPTIONAL {{ ?period {end} ?end . }}
  }}
}} ORDER BY ?start''', supported_predicates)


def _term_identity_count_query(house: str, *, supported_predicates) -> str:
    graph = _graph("houses")
    term_type = _type(f"agents:{house}Term")
    return _query(_PREFIXES + f'''SELECT (COUNT(DISTINCT ?term) AS ?count) WHERE {{ GRAPH <{graph}> {{ ?term a {term_type} . }} }}''', supported_predicates)


def _dail_chronology_query(*, supported_predicates) -> str:
    graph = _graph("houses")
    term_type = _type("agents:DailTerm")
    temporal, start, end = (_predicate("dct:temporal"), _predicate("dcat:startDate"), _predicate("dcat:endDate"))
    return _query(_PREFIXES + f'''SELECT DISTINCT ?term ?start ?end WHERE {{
  GRAPH <{graph}> {{
    ?term a {term_type} .
    OPTIONAL {{ ?term {temporal} ?period . OPTIONAL {{ ?period {start} ?start . }} OPTIONAL {{ ?period {end} ?end . }} }}
  }}
}}''', supported_predicates)


def _values(result: QueryResult, names: tuple[str, ...]) -> list[dict[str, str | None]]:
    if result.kind != "select" or not set(names).issubset(result.columns):
        raise NLQError("The local query returned an unexpected evidence shape.")
    indexes = {name: result.columns.index(name) for name in names}
    rows = []
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError("The local query returned a truncated evidence row.")
        rows.append({name: None if row[index] in {"—", ""} else row[index] for name, index in indexes.items()})
    return rows


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    if "^^" in value and "^^<http://www.w3.org/2001/XMLSchema#dateTime>" not in value and "^^<http://www.w3.org/2001/XMLSchema#date>" not in value:
        raise NLQError("Source date evidence has no reviewed xsd:date/dateTime datatype; no answer was selected.")
    lexical = value.split("^^", 1)[0]
    try:
        return datetime.fromisoformat(lexical.replace("Z", "+00:00")).date()
    except ValueError as error:
        raise NLQError("Source date evidence is malformed; no answer was selected.") from error


def merge_service_intervals(episodes: list[tuple[date, date]], as_of: date) -> tuple[list[tuple[date, date]], int, list[tuple[date, date]]]:
    """Return the inclusive union, actual served days, and intervening gaps."""
    clipped = sorted((start, min(end, as_of)) for start, end in episodes if start <= as_of)
    merged: list[tuple[date, date]] = []
    for start, end in clipped:
        if end < start:
            continue
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    gaps = [
        (left[1] + timedelta(days=1), right[0] - timedelta(days=1))
        for left, right in zip(merged, merged[1:])
        if right[0] > left[1] + timedelta(days=1)
    ]
    days = sum((end - start).days + 1 for start, end in merged)
    return merged, days, gaps


def _resolve_member(mention: str, fuseki, supported_predicates, *, allow_qualified_partial: bool = False):
    grounded = mention.strip()
    qualified_partial = (allow_qualified_partial
                         and bool(re.match(r"^(?:Deputy|TD|Senator)\s+", grounded, re.IGNORECASE))
                         and 1 <= len(re.findall(r"[^\W_]+", re.sub(r"^(?:Deputy|TD|Senator)\s+", "", grounded, flags=re.IGNORECASE), re.UNICODE)) <= 2)
    search_mention = re.sub(r"^(?:Deputy|TD|Senator)\s+", "", grounded, flags=re.IGNORECASE)
    raw = fuseki.query(_member_lookup_query(search_mention, supported_predicates=supported_predicates))
    rows = _values(raw, ("member", "name"))
    if len(rows) >= 100:
        raise NLQError("Member-name resolution reached the 100-row safety cap; no identity was selected.")
    tokens = [token for token in re.findall(r"[^\W_]+", search_mention, re.UNICODE)
              if token.casefold() not in {"deputy", "td", "senator", "the", "who", "is"}]
    if len(tokens) < 2 and not (qualified_partial and len(tokens) == 1):
        raise NLQError("Member resolution requires a full name or a grounded title plus family name; a single unqualified token is insufficient.")
    candidates: dict[str, str] = {}
    for row in rows:
        iri, name = row["member"], row["name"]
        if not iri or not name:
            continue
        _require_local_iri(iri, "Member")
        name_tokens = [token.casefold() for token in re.findall(r"[^\W_]+", name, re.UNICODE)]
        if ((qualified_partial and all(token.casefold() in name.casefold() for token in tokens))
                or (not qualified_partial and name_tokens == [token.casefold() for token in tokens])):
            candidates[iri] = name.removesuffix("@en")
    return candidates


def _member_outcome_plan(mention: str, as_of: date, candidates: dict[str, str], *, family: str):
    from .composable_plan import validate_plan
    resolution = "resolved" if len(candidates) == 1 else "ambiguous" if candidates else "not_found"
    ref = {"type": "Member", "mention": mention, "resolution": resolution,
           "candidates": [{"iri": iri, "label": label} for iri, label in sorted(candidates.items())]}
    if resolution == "resolved":
        iri, label = next(iter(candidates.items()))
        ref.update(iri=iri, label=label)
    refs = {"member": ref}
    relation_facts: list[tuple[str, str, str]] = []
    if family in {"previous_service", "dail_duration", "dail_all"} or family == "term_count" and len(candidates) >= 0:
        refs.update(membership={"type": "DailMembership"}, term={"type": "DailTerm"})
        relation_facts.extend([("member_has_membership", "member", "membership"), ("membership_in_term", "membership", "term")])
    elif family in {"seanad_entry", "seanad_representation"}:
        refs.update(membership={"type": "SeanadMembership"}, term={"type": "SeanadTerm"})
        relation_facts.extend([("member_has_seanad_membership", "member", "membership"), ("seanad_membership_in_term", "membership", "term")])
        if family == "seanad_representation":
            refs["representation"] = {"type": "SeanadRepresentation"}
            relation_facts.append(("seanad_membership_represents_resource", "membership", "representation"))
    elif family == "current_collection":
        refs.update(collectionMembership={"type": "ParliamentaryCollectionMembership"}, collection={"type": "ParliamentaryMemberCollection"})
        relation_facts.extend([("member_has_collection_membership", "member", "collectionMembership"), ("collection_membership_of_collection", "collectionMembership", "collection")])
    elif family in {"committee_boolean", "committee_count"}:
        refs.update(committeeMembership={"type": "CommitteeMembership"}, committee={"type": "Committee"})
        relation_facts.extend([("member_has_committee_membership", "member", "committeeMembership"), ("committee_membership_of_committee", "committeeMembership", "committee")])
        if family == "committee_boolean":
            refs["term"] = {"type": "DailTerm"}
            relation_facts.append(("committee_in_term", "committee", "term"))
    relations = [{"id": f"r{index}", "fact": fact, "from": source, "to": target}
                 for index, (fact, source, target) in enumerate(relation_facts, start=1)]
    plan = {
        "version": 2, "asOf": as_of.isoformat(), "family": family,
        "referents": refs,
        "relations": relations, "answer": {"kind": "family_result", "referent": "member"},
    }
    return validate_plan(plan)


def _validated_simple_plan(plan: dict):
    from .composable_plan import validate_plan
    return validate_plan(plan)


def _member_context(member_iri: str, house: str, fuseki, supported_predicates):
    result = fuseki.query(_member_service_query(member_iri, house, supported_predicates=supported_predicates))
    rows = _values(result, ("member", "name", "membership", "term", "termLabel", "termStart", "termEnd", "membershipStart", "membershipEnd", "representation", "representationLabel"))
    if len(rows) >= 100:
        raise NLQError("Membership evidence reached the 100-row query cap; the result is incomplete and no exact count or duration is reported.")
    representations = sorted({row["representation"] for row in rows if row["representation"]})
    labels = {}
    if representations:
        _, families = _contract_parts()
        representation_type = _type("members:Constituencies")
        values = " ".join(f"<{_require_local_iri(iri, 'Seanad representation')}>" for iri in representations)
        query = _PREFIXES + f'''SELECT DISTINCT ?representation ?representationLabel WHERE {{
  VALUES ?representation {{ {values} }}
  GRAPH <{families['constituencies']['iri']}> {{
    ?representation a {representation_type} ; skos:prefLabel ?representationLabel .
  }}
}}'''
        label_rows = _values(fuseki.query(_query(query, supported_predicates)), ("representation", "representationLabel"))
        labels = {row["representation"]: row["representationLabel"] for row in label_rows if row["representation"] and row["representationLabel"]}
    for row in rows:
        row["representationLabel"] = labels.get(row["representation"])
    return rows


def _compile_direct_query(query: str, supported_predicates) -> str:
    return _query(query, supported_predicates)


def execute_stage_a(request: StageARequest, *, as_of: date, fuseki, supported_predicates) -> PlanOutcome:
    """Run a shared typed family primitive and return a readable v2 route result."""
    try:
        _reviewed_stage_a_family(request.family)
    except NLQError as error:
        return PlanOutcome("unsupported_mapping", diagnostic=str(error))
    selected_committee = None
    if request.family == "committee_boolean":
        try:
            catalogue = _values(fuseki.query(_committee_catalogue_query(supported_predicates=supported_predicates)),
                                ("committee", "label", "term", "start", "end", "termStart", "termEnd"))
            if len(catalogue) >= 100:
                return PlanOutcome("source_data_unavailable", diagnostic="The Committee owner catalogue reached the 100-row cap; no current incarnation was selected.")
            expected = " ".join((request.detail or "").casefold().split())
            named = [row for row in catalogue if " ".join((row["label"] or "").removesuffix("@en").casefold().split()) == expected]
            if not named:
                if any(row["label"] is None for row in catalogue):
                    return PlanOutcome("source_data_unavailable", diagnostic="The Committee owner catalogue contains unlabeled Committee resources; absence cannot establish that the requested owner does not exist, and Member identities were not queried.")
                return PlanOutcome("not_found", diagnostic="No Committee owner resource exactly matches that name; Member identities were not queried.")
            current = []
            for row in named:
                if not all((row[field] is not None) for field in ("termStart",)):
                    continue
                term_start, term_end = _date(row["termStart"]), _date(row["termEnd"])
                owner_start, owner_end = _date(row["start"]), _date(row["end"])
                if (term_start and term_start <= as_of and (term_end is None or as_of <= term_end)
                        and owner_start and owner_start <= as_of and (owner_end is None or as_of <= owner_end)):
                    current.append(row)
            if not current:
                return PlanOutcome("source_data_unavailable", diagnostic="The matching Committee owner has no complete date evidence proving a current incarnation; Member identities were not queried.")
            identities = {row["committee"] for row in current}
            if len(identities) > 1:
                return PlanOutcome("ambiguous", candidates=tuple({"iri": row["committee"], "label": (row["label"] or "").removesuffix("@en")} for row in current),
                                   result=QueryResult("select", ("Current Committee incarnation",), tuple(((row["label"] or "").removesuffix("@en"),) for row in current)),
                                    diagnostic="Several distinct current Committee owner resources match; Member identities were not queried and no incarnation was selected.")
            selected_committee = current[0]
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", diagnostic=str(error))
    if request.family in {"house_terms", "term_count"} and request.family == "house_terms":
        try:
            raw = fuseki.query(_term_query("Dail", supported_predicates=supported_predicates))
            rows = _values(raw, ("term", "label", "number", "start", "end"))
            if len(rows) >= 100:
                return PlanOutcome("source_data_unavailable", diagnostic="The Dáil term listing reached the 100-row cap; a complete chronological list is not reported.")
            if not rows:
                return PlanOutcome("source_data_unavailable", diagnostic="No Dáil HouseTerm records are available to list; an empty local graph is not reported as a complete history.")
            parsed = [(item, _date(item["start"]), _date(item["end"])) for item in rows]
            term_dates = {}
            for item, start_date, end_date in parsed:
                key = item["term"]
                if key in term_dates and term_dates[key] != (start_date, end_date):
                    return PlanOutcome("source_data_unavailable", diagnostic="Conflicting date rows for a Dáil HouseTerm prevent a chronological listing.")
                term_dates[key] = (start_date, end_date)
            open_candidates = [(item, start) for item, start, end in parsed
                               if start is not None and start <= as_of and end is None]
            current_open = None
            if len(open_candidates) == 1:
                candidate, candidate_start = open_candidates[0]
                if all(end is None and item["term"] == candidate["term"] or end is not None and end < candidate_start
                       for item, _start, end in parsed):
                    current_open = candidate["term"]
            out = []
            for item, start, end in parsed:
                _require_local_iri(item["term"], "Dáil term")
                if start is None:
                    return PlanOutcome("source_data_unavailable", diagnostic="A Dáil term has no start-date evidence.")
                if end is None:
                    suffix = "Current term (open end)" if item["term"] == current_open else "No end date recorded"
                    end_text = suffix
                else:
                    end_text = end.isoformat()
                out.append((item["label"].removesuffix("@en"), start.isoformat(), end_text))
            result = QueryResult("select", ("Dáil term", "Start", "End"), tuple(out), raw.raw_json)
            plan = _validated_simple_plan({"version": 2, "asOf": as_of.isoformat(), "family": "house_terms", "referents": {"term": {"type": "DailTerm", "answer": True}}, "relations": [], "answer": {"kind": "values", "referent": "term"}})
            return PlanOutcome("success", plan=plan, sparql=_term_query("Dail", supported_predicates=supported_predicates), result=result,
                               diagnostic="House-owned term dates; absent end dates are shown explicitly and only the term spanning the supplied as-of date is called current.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", diagnostic=str(error))

    if request.family == "term_count" and request.mention is None:
        try:
            raw = fuseki.query(_term_identity_count_query("Dail", supported_predicates=supported_predicates))
            count_rows = _values(raw, ("count",))
            if len(count_rows) != 1 or count_rows[0]["count"] is None:
                return PlanOutcome("source_data_unavailable", diagnostic="The Houses count query returned incomplete aggregate evidence.")
            count_text = count_rows[0]["count"].split("^^", 1)[0]
            if not count_text.isdecimal():
                return PlanOutcome("source_data_unavailable", diagnostic="The Houses count query returned a malformed aggregate value.")
            result = QueryResult("select", ("Distinct Dáil terms",), ((str(int(count_text)),),), raw.raw_json)
            plan = _validated_simple_plan({"version": 2, "asOf": as_of.isoformat(), "family": "term_count", "referents": {"term": {"type": "DailTerm", "answer": True}}, "relations": [], "answer": {"kind": "count", "referent": "term", "distinctBy": "identity"}})
            return PlanOutcome("success", plan=plan, sparql=_term_identity_count_query("Dail", supported_predicates=supported_predicates), result=result,
                               diagnostic="Exact count of distinct Dáil-term resources in the queried Houses graph; this does not assert corpus completeness.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", diagnostic=str(error))

    if request.family == "member_lookup" and request.mention:
        # For a partial qualified name, strip title words and resolve exact
        # remaining name tokens; duplicate identities remain a candidate set.
        mention = request.mention.strip()
        try:
            candidates = _resolve_member(mention, fuseki, supported_predicates, allow_qualified_partial=True)
            grounded_mention = re.sub(r"^(?:Deputy|TD|Senator)\s+", "", mention, flags=re.IGNORECASE).strip()
            plan = _member_outcome_plan(grounded_mention, as_of, candidates, family=request.family)
            if not candidates:
                return PlanOutcome("not_found", plan=plan, diagnostic=f"No local Member matches the grounded name reference {grounded_mention!r}.")
            if len(candidates) > 1:
                context = []
                for iri, name in sorted(candidates.items()):
                    records = _member_context(iri, "Dail", fuseki, supported_predicates)
                    senate_records = _member_context(iri, "Seanad", fuseki, supported_predicates)
                    evidence = records + senate_records
                    terms = sorted({(row["termLabel"] or "").removesuffix("@en") for row in evidence})
                    dates = sorted({f"{_date(row['membershipStart']) or 'start missing'}–{_date(row['membershipEnd']) or 'end missing/open'}" for row in evidence})
                    context.append((name, "; ".join(terms + dates)))
                return PlanOutcome("ambiguous", plan=plan, candidates=tuple({"iri": iri, "label": label} for iri, label in sorted(candidates.items())),
                                    diagnostic="Several distinct local Member identities match; no candidate was selected. House service and membership dates are shown for disambiguation.",
                                    result=QueryResult("select", ("Member candidate", "House service and dates"), tuple(context)))
            iri, label = next(iter(candidates.items()))
            return PlanOutcome("success", plan=plan, result=QueryResult("select", ("Full name",), ((label,),)),
                               diagnostic="Resolved from local Member name evidence; no external identity matching was used.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", diagnostic=str(error))

    if request.mention is None:
        return PlanOutcome("unsupported_capability", diagnostic="The question does not identify a supported Stage A query family.")

    try:
        candidates = _resolve_member(request.mention, fuseki, supported_predicates)
    except NLQError as error:
        return PlanOutcome("source_data_unavailable", diagnostic=str(error))
    plan = _member_outcome_plan(request.mention, as_of, candidates, family=request.family)
    if selected_committee is not None and request.family == "committee_boolean":
        term_type = "SeanadTerm" if "/house/seanad/" in (selected_committee["term"] or "") else "DailTerm"
        plan["referents"]["committee"].update(
            mention=request.detail, resolution="resolved", iri=selected_committee["committee"],
            label=(selected_committee["label"] or "").removesuffix("@en"),
        )
        plan["referents"]["term"] = {"type": term_type, "iri": selected_committee["term"]}
        plan["relations"][2]["fact"] = "committee_in_seanad_term" if term_type == "SeanadTerm" else "committee_in_term"
        plan["relations"][2]["from"] = "committee"
        plan["relations"][2]["to"] = "term"
        plan = _validated_simple_plan(plan)
    if not candidates:
        return PlanOutcome("not_found", plan=plan, diagnostic=f"No local Member matches {request.mention!r}.")
    if len(candidates) > 1:
        if request.family == "dail_all":
            records = []
            for iri, label in sorted(candidates.items()):
                service = _member_context(iri, "Dail", fuseki, supported_predicates)
                if service:
                    terms = "; ".join(sorted({(row["termLabel"] or "").removesuffix("@en") for row in service}))
                    records.append((label, terms))
            if records:
                return PlanOutcome("success", plan=plan, result=QueryResult("select", ("Member identity", "Dáil service terms"), tuple(records)),
                                   diagnostic="Returned every distinct exact-name Member identity with DáilMembership evidence; no same-name identity was selected or merged.")
            return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="Matching Member names were found, but no DáilMembership evidence was found in the local Member graphs.")
        return PlanOutcome("ambiguous", plan=plan,
                           candidates=tuple({"iri": iri, "label": label} for iri, label in sorted(candidates.items())),
                           diagnostic="Several distinct local Member identities match; no candidate was selected.")
    member_iri, member_name = next(iter(candidates.items()))
    if request.family in {"previous_service", "dail_duration", "term_count"}:
        try:
            if request.family == "term_count":
                term_result = fuseki.query(_member_term_count_query(member_iri, supported_predicates=supported_predicates))
                term_rows = _values(term_result, ("term",))
                if len(term_rows) >= 100:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="Membership-linked Dáil term evidence reached the 100-row cap; no exact count is reported.")
                unique_terms = {row["term"] for row in term_rows if row["term"]}
                if not unique_terms:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No DáilMembership/HouseTerm evidence is available for this Member; an exact zero is not asserted.")
                return PlanOutcome("success", plan=plan, result=QueryResult("select", ("Distinct Dáil terms",), ((str(len(unique_terms)),),)),
                                   diagnostic="Counted distinct membership-linked HouseTerm IRIs; missing HouseTerm labels or period metadata do not discard service links.")
            service = _member_context(member_iri, "Dail", fuseki, supported_predicates)
            if request.family == "previous_service":
                if not service:
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="No DáilMembership records are available for this Member; absence is not a reliable negative membership answer.")
                from .composable_plan import previous_dail_term_query, resolve_previous_dail
                term_result = fuseki.query(previous_dail_term_query(as_of, supported_predicates=supported_predicates))
                previous, _current = resolve_previous_dail(term_result, as_of)
                serving = any(row["term"] == previous for row in service)
                return PlanOutcome("success", plan=plan, result=QueryResult("ask", boolean=serving),
                                   diagnostic=f"Membership-resource evidence for the previous Dáil selected from House-term dates as of {as_of.isoformat()}.")
            if request.family == "dail_duration":
                from .composable_plan import resolve_previous_dail
                timeline = fuseki.query(_dail_chronology_query(supported_predicates=supported_predicates))
                timeline_rows = _values(timeline, ("term", "start", "end"))
                if len(timeline_rows) >= 100:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="House-term chronology reached the 100-row cap; cumulative service is incomplete.")
                if any(row["start"] is None for row in timeline_rows):
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="A typed Dáil HouseTerm lacks start-date evidence; the chronology is incomplete.")
                timeline = QueryResult("select", ("term", "start", "end"),
                                       tuple((row["term"], row["start"], row["end"] or "—") for row in timeline_rows), timeline.raw_json)
                chronology = {}
                for term_iri, start_text, end_text in timeline.rows:
                    start_date, end_date = _date(start_text), _date(None if end_text in {"—", ""} else end_text)
                    if term_iri in chronology and chronology[term_iri] != (start_date, end_date):
                        return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="Conflicting HouseTerm date rows prevent a safe lifetime-duration calculation.")
                    chronology[term_iri] = (start_date, end_date)
                ordered_terms = sorted(chronology.items(), key=lambda pair: (pair[1][0], pair[0]))
                latest_started = max((term for term, (start, _end) in ordered_terms if start <= as_of),
                                     key=lambda term: (chronology[term][0], term))
                if any(term != latest_started and start <= as_of and end is None
                       for term, (start, end) in ordered_terms):
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="A historical HouseTerm has no end date despite a later distinct term; Dáil duration is incomplete.")
                _previous, globally_current = resolve_previous_dail(timeline, as_of)
                for index, (term_iri, (term_start_date, term_end_date)) in enumerate(ordered_terms):
                    if term_iri != globally_current and term_start_date <= as_of and term_end_date is None:
                        return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="A historical HouseTerm has no end date despite a later distinct term; Dáil duration is incomplete.")
                    if index and ordered_terms[index - 1][1][1] is not None and ordered_terms[index - 1][1][1] >= term_start_date:
                        return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="Overlapping HouseTerm chronology prevents a safe lifetime-duration calculation.")
            episodes = []
            for row in service:
                start, end = _date(row["membershipStart"]), _date(row["membershipEnd"])
                term_start, term_end = _date(row["termStart"]), _date(row["termEnd"])
                if start is None:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="A Dáil membership episode lacks a usable start date; cumulative service cannot be calculated safely.")
                if term_start is None or start < term_start or (term_end is not None and start > term_end):
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="A Dáil membership interval conflicts with its HouseTerm dates; service intervals are not silently clipped or intersected.")
                if end is not None and ((term_end is not None and end > term_end) or end < term_start):
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="A Dáil membership interval conflicts with its HouseTerm dates; service intervals are not silently clipped or intersected.")
                if end is None:
                    if term_end is not None and term_end < as_of:
                        return PlanOutcome("source_data_unavailable", plan=plan,
                                           diagnostic="A historical Dáil membership lacks an end date; it is not extended to today, so cumulative service is incomplete.")
                    if term_start is None or term_start > as_of:
                        continue
                    if term_end is None:
                        if row["term"] != globally_current:
                            return PlanOutcome("source_data_unavailable", plan=plan,
                                               diagnostic="A membership episode has no end date and its HouseTerm cannot be established as current; cumulative service is incomplete.")
                        end = as_of
                    else:
                        end = min(term_end, as_of)
                if end < start:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="A Dáil membership episode has an end date before its start date.")
                episodes.append((start, end))
            if not episodes:
                return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No Dáil membership episodes are present; absence is not proof of no service.")
            merged, actual_days, gaps_between = merge_service_intervals(episodes, as_of)
            if not merged:
                return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No dated Dáil service interval reaches the supplied as-of date.")
            intervals = "; ".join(f"{start.isoformat()} – {end.isoformat()}" for start, end in merged)
            gaps = "; ".join(f"{start.isoformat()} – {end.isoformat()}" for start, end in gaps_between) or "none recorded between returned episodes"
            result = QueryResult("select", ("Member", "Cumulative service (days)", "Service intervals", "Gaps"), ((member_name, str(actual_days), intervals, gaps),))
            return PlanOutcome("success", plan=plan, result=result,
                               diagnostic=f"Inclusive union of dated Dáil membership intervals through {as_of.isoformat()}; the local dataset does not certify complete lifetime history.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=str(error))

    if request.family == "current_collection":
        try:
            raw = fuseki.query(_collection_query(member_iri, supported_predicates=supported_predicates))
            rows = _values(raw, ("record", "collection", "collectionType", "label", "start", "end", "ownerMembership", "ownerMembershipStart", "ownerMembershipEnd", "ownerTerm", "ownerTermStart", "ownerTermEnd"))
            if len(rows) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic="Collection-membership evidence reached the 100-row cap; current status is not determined from a truncated result.")
            active = []
            owners_by_record: dict[str, set[str]] = {}
            for row in rows:
                if row["ownerMembership"]:
                    owners_by_record.setdefault(row["record"], set()).add(row["ownerMembership"])
            if any(len(owners) > 1 for owners in owners_by_record.values()):
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic="A collection record has conflicting containing OireachtasMembership links; current status is not inferred.")
            for row in rows:
                _require_local_iri(row["collection"], "ParliamentaryMemberCollection")
                start, end = _date(row["start"]), _date(row["end"])
                if start is None:
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="A collection-membership record lacks a start date, so current affiliation cannot be determined at the supplied as-of date.")
                if end is None:
                    term_start, term_end = _date(row["ownerTermStart"]), _date(row["ownerTermEnd"])
                    owner_start, owner_end = _date(row["ownerMembershipStart"]), _date(row["ownerMembershipEnd"])
                    if row["ownerTerm"] is None or term_start is None:
                        return PlanOutcome("source_data_unavailable", plan=plan,
                                           diagnostic="An open-ended collection record lacks containing OireachtasMembership/HouseTerm evidence; current affiliation is not inferred from a historical record.")
                    if term_end is not None and term_end < as_of:
                        continue
                    if owner_end is not None and owner_end < as_of:
                        continue
                    if owner_start is not None and owner_start > as_of:
                        continue
                    if term_start > as_of:
                        continue
                if start <= as_of and (end is None or as_of <= end):
                    active.append(row)
            if not active:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic=f"No dated collection-membership evidence establishes this Member's status on {as_of.isoformat()}; this is not evidence of no affiliation.")
            identities = {(row["collection"], row["collectionType"], row["label"]) for row in active}
            if len(identities) > 1:
                result = QueryResult("select", ("Current parliamentary collection",),
                                     tuple((row[2].removesuffix("@en") if row[2] else "Label not recorded",) for row in sorted(identities)))
                return PlanOutcome("ambiguous", plan=plan, result=result,
                                   diagnostic="Several current term-scoped collection records overlap the as-of date; none is promoted to one enduring political-party identity.")
            _iri, rdf_type, label = next(iter(identities))
            if rdf_type.endswith("IndependentMemberCollection"):
                display = f"{member_name} is an Independent (parliamentary status, not a political-party membership)."
            else:
                display = label.removesuffix("@en") if label else "Current party label not recorded"
            return PlanOutcome("success", plan=plan,
                               result=QueryResult("select", ("Current party/status",), ((display,),), raw.raw_json),
                               diagnostic=f"Current collection membership was evaluated at {as_of.isoformat()}; term-scoped collections are not merged as enduring party identities.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=str(error))

    if request.family in {"seanad_entry", "seanad_representation"}:
        try:
            service = _member_context(member_iri, "Seanad", fuseki, supported_predicates)
            if request.family == "seanad_representation" and request.term:
                service = [row for row in service if (row["termLabel"] or "").removesuffix("@en").casefold() == request.term.casefold()]
            if not service:
                return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No matching dated Seanad membership and representation evidence is available in the local dataset.")
            intervals_by_membership: dict[str, set[tuple[date | None, date | None]]] = {}
            for item in service:
                intervals_by_membership.setdefault(item["membership"], set()).add(
                    (_date(item["membershipStart"]), _date(item["membershipEnd"])))
            if any(len(values) > 1 for values in intervals_by_membership.values()):
                return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="Conflicting Seanad membership date-range evidence exists; no earliest entry was selected.")
            rows = []
            for item in service:
                membership_end = _date(item["membershipEnd"])
                term_end = _date(item["termEnd"])
                term_start = _date(item["termStart"])
                if membership_end is None and term_end is not None and term_end < as_of:
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="A historical Seanad membership has no end date; the source mapping cannot establish its duration or current/open status.")
                is_current_term = term_start is not None and term_start <= as_of and (term_end is None or as_of <= term_end)
                rows.append((member_name, (item["termLabel"] or "").removesuffix("@en"),
                (_date(item["membershipStart"]).isoformat() if _date(item["membershipStart"]) else "Start date not recorded"),
                             ("Open/current at as-of date" if is_current_term else "End date not recorded") if membership_end is None else membership_end.isoformat(),
                             (item["representationLabel"] or "No designation recorded").removesuffix("@en")))
            first = min((_date(item["membershipStart"]) for item in service if _date(item["membershipStart"]) is not None), default=None)
            if request.family == "seanad_entry" and first is None:
                return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No usable Seanad membership start date exists; an earliest entry cannot be established.")
            if request.family == "seanad_entry" and first:
                if any(_date(item["membershipStart"]) is None for item in service):
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="At least one Seanad membership episode has no usable start date; the earliest entry cannot be established safely.")
                earliest = [row for row, item in zip(rows, service) if _date(item["membershipStart"]) == first]
                later = [f"{row[1]}: {row[2]} ({row[4]})" for row, item in zip(rows, service)
                         if _date(item["membershipStart"]) is not None and _date(item["membershipStart"]) > first]
                result = QueryResult("select", ("Member", "First Seanad entry", "Term", "Source representation designation"),
                                     tuple((member_name, first.isoformat(), row[1], row[4]) for row in earliest))
                if later:
                    result = QueryResult("select", ("Member", "First Seanad entry", "Term", "Source representation designation", "Later Seanad episodes"),
                                         tuple((member_name, first.isoformat(), row[1], row[4], "; ".join(later)) for row in earliest))
                return PlanOutcome("success", plan=plan, result=result,
                                   diagnostic="First recorded Seanad membership start; later distinct terms remain separate source episodes. The representation designation is not treated as a legal election/appointment mechanism unless the source explicitly labels it.")
            if request.family == "seanad_representation" and not any(item["representationLabel"] for item in service):
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic="The mapped RDF contains no source-provided Seanad representation designation for this membership; election or nomination method cannot be inferred.")
            return PlanOutcome("success", plan=plan, result=QueryResult("select", ("Member", "Seanad term", "Start", "End", "Representation designation"), tuple(rows)),
                               diagnostic="Term-scoped Seanad membership records are shown separately; the returned representation identity can be any source-provided panel or constituency.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=str(error))

    if request.family in {"committee_count", "committee_boolean"}:
        try:
            if request.family == "committee_count":
                identity_rows = _values(fuseki.query(_committee_count_query(member_iri, supported_predicates=supported_predicates)), ("committee",))
                if len(identity_rows) >= 100:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="Committee membership evidence reached the 100-row cap; no exact committee count is reported.")
                identities = {_require_local_iri(row["committee"], "Committee") for row in identity_rows if row["committee"]}
                if not identities:
                    return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No Member CommitteeMembership evidence was returned; the local dataset does not support an exact zero committee count.")
                return PlanOutcome("success", plan=plan, result=QueryResult("select", ("Distinct committees",), ((str(len(identities)),),)),
                                   diagnostic="Counted distinct membership-linked Committee IRIs independent of optional owner labels, terms or date metadata; local coverage is not certified complete.")
            rows = _values(fuseki.query(_committee_query(member_iri, supported_predicates=supported_predicates)),
                           ("membership", "committee", "label", "term", "start", "end", "termStart", "termEnd"))
            if len(rows) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic="Committee membership evidence reached the 100-row cap; no exact committee count is reported.")
            unique = {}
            # Current incarnation is established by the Committee-owned
            # operational range when present; the HouseTerm is context, never
            # inferred from the Member's containing membership.
            for row in rows:
                committee = _require_local_iri(row["committee"], "Committee")
                if selected_committee is not None and committee != selected_committee["committee"]:
                    continue
                label = (row["label"] or "").removesuffix("@en")
                term = _require_local_iri(row["term"], "Committee HouseTerm")
                if request.family == "committee_boolean" and request.detail:
                    wanted = " ".join(request.detail.casefold().split())
                    if wanted != " ".join(label.casefold().split()):
                        continue
                unique[committee] = (label, row["membership"], row["start"], row["end"], row["termStart"], row["termEnd"])
            if request.family == "committee_count":
                if not unique:
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="No Member CommitteeMembership evidence was returned; the local dataset does not support an exact zero committee count.")
                result = QueryResult("select", ("Distinct committees",), ((str(len(unique)),),))
                return PlanOutcome("success", plan=plan, result=result,
                                   diagnostic="Counted distinct Committee resource identities; repeated CommitteeMembership records do not inflate the number.")
            if not unique:
                return PlanOutcome("source_data_unavailable", plan=plan, diagnostic="No matching Committee incarnation or Member CommitteeMembership evidence was found; local coverage is not certified complete.")
            # Refuse to claim Q11's current incarnation unless operational date
            # evidence actually distinguishes it. Committee dates are optional
            # in the mapping, so term-only references cannot prove currentness.
            if request.family == "committee_boolean":
                dated = []
                for key, (label, membership, start_text, end_text, term_start_text, term_end_text) in unique.items():
                    start, end = _date(start_text), _date(end_text)
                    term_start, term_end = _date(term_start_text), _date(term_end_text)
                    if start is None or term_start is None:
                        continue
                    if start <= as_of and (end is None or as_of <= end) and term_start <= as_of and (term_end is None or as_of <= term_end):
                        dated.append((key, label, membership))
                if len(dated) != 1:
                    if len(dated) > 1:
                        committee_ref = {
                            "type": "Committee", "mention": request.detail or "the requested Committee",
                            "resolution": "ambiguous",
                            "candidates": [{"iri": item[0], "label": item[1]} for item in dated],
                        }
                        plan["referents"]["committee"] = committee_ref
                        plan = _validated_simple_plan(plan)
                        candidates = tuple({"iri": item[0], "label": item[1]} for item in dated)
                        result = QueryResult("select", ("Current Committee incarnation", "Committee"),
                                             tuple((label, iri) for iri, label in sorted((item[0], item[1]) for item in dated)))
                        return PlanOutcome("ambiguous", plan=plan, candidates=candidates, result=result,
                                           diagnostic="More than one distinct, dated current Committee incarnation exactly matches; none was selected.")
                    return PlanOutcome("source_data_unavailable", plan=plan,
                                       diagnostic="The matching Committee record does not provide one uniquely current Committee-owned date range at the as-of date; no yes/no claim about the current incarnation is made.")
                chosen_iri, chosen_label, _membership = dated[0]
                return PlanOutcome("success", plan=plan, result=QueryResult("ask", boolean=True),
                                    diagnostic=f"Yes. {chosen_label} ({chosen_iri}) is the uniquely dated current Committee incarnation at {as_of.isoformat()}, and the Member has a membership link to that exact Committee IRI.")
            result = QueryResult("select", ("Distinct Committee resources",), ((str(len(unique)),),))
            return PlanOutcome("success", plan=plan, result=result,
                               diagnostic="Counted distinct Committee IRI identities, not repeated CommitteeMembership records; local history coverage is not certified complete.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=str(error))

    if request.family == "dail_all":
        try:
            service = _member_context(member_iri, "Dail", fuseki, supported_predicates)
            terms = sorted({(row["termLabel"] or "").removesuffix("@en") for row in service})
            result = QueryResult("select", ("Member", "Dáil service terms"), ((member_name, "; ".join(terms)),) if terms else ())
            return PlanOutcome("success" if terms else "source_data_unavailable", plan=plan, result=result,
                               diagnostic="Set-valued exact-name resolution retained distinct Member resources and filtered to those with DáilMembership records.")
        except NLQError as error:
            return PlanOutcome("source_data_unavailable", plan=plan, diagnostic=str(error))

    return PlanOutcome("unsupported_capability", plan=plan,
                       diagnostic="The reviewed RDF pattern required for this Stage A question is not executable in this route.")
