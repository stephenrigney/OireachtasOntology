"""Bounded Stage C coverage-dependent Query Service routes.

Every executable lookup is compiled from the reviewed query-schema contract.
Coverage-only cases return a validated typed v2 request and never run a
substitute answer query.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from rdflib import URIRef

from .composable_plan import (
    PlanError, PlanOutcome, _PREFIXES, _pattern_predicate, _pattern_rdf_type,
    _require_local_iri, _reviewed_cross_graph_join, _reviewed_pattern,
    _reviewed_predicate, _reviewed_predicate_for_qname,
)
from .contract import load_query_contract
from .errors import NLQError
from .results import QueryResult
from .safety import validate_sparql


_C_FAMILIES = {
    "dail_seats", "dail_parties_and_groups", "bill_quarantine", "debate_lookup",
    "committee_topic_latest", "bill_votes", "debate_transcript",
}
_KNOWN_CATALOGUE = {
    "dail_seats": "Q16", "dail_parties_and_groups": "Q17",
    "bill_quarantine": "Q24", "debate_lookup": "Q31",
    "committee_topic_latest": "Q30", "bill_votes": "Q36",
    "debate_transcript": "Q37",
}
_GROUPS_GAP = "ParliamentaryGroup data is missing: records are not populated in the current queryable dataset, which does not mean no groups existed."
_ORDINAL = re.compile(r"\b(?P<number>[0-9]{1,3})(?:st|nd|rd|th)\b", re.I)
_XSD_INTEGER_CELL = re.compile(r"^(?P<lexical>[+-]?[0-9]+)\^\^<http://www\.w3\.org/2001/XMLSchema#integer>$")


class InvalidStageCRequest(ValueError):
    """A recognized Stage C request contains an invalid controlled value."""


def _ordinal_label(number: int) -> str:
    return f"{number}{_ordinal_suffix(number)} Dáil"


def _ordinal_suffix(number: int) -> str:
    return "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")


def _make_plan(family: str, as_of: date, *, ordinal: int | None = None,
               mention: str | None = None, debate_date: str | None = None) -> dict[str, Any]:
    if family == "dail_seats":
        refs = {"term": {"type": "DailTerm", "selector": {"kind": "termNumber", "number": ordinal}}}
        relations: list[dict[str, str]] = []
        projection = "dail_seats"
    elif family == "dail_parties_and_groups":
        refs = {"term": {"type": "DailTerm", "selector": {"kind": "termNumber", "number": ordinal}},
                "party": {"type": "ParliamentaryParty", "answer": True}}
        relations = [{"id": "party-active-term", "fact": "party_active_during_term", "from": "party", "to": "term"}]
        projection = "dail_parties_and_groups"
    elif family == "bill_quarantine":
        refs = {"bill": {"type": "Bill", "selector": {"kind": "numberYear", "year": 2024, "number": "48"}}}
        relations = []
        projection = family
    elif family == "debate_lookup":
        refs = {"sitting": {"type": "DebateSitting", "answer": True}, "record": {"type": "DebateRecord"}}
        relations = [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}]
        projection = family
    elif family == "committee_topic_latest":
        refs = {"committee": {"type": "Committee", "mention": "Committee of Public Accounts"},
                "hearing": {"type": "DebateRecord", "mention": "HSE"}}
        relations = []
        projection = family
    elif family == "bill_votes":
        refs = {"bill": {"type": "Bill", "mention": mention or "Artificial Intelligence Companion Services Bill"}}
        relations = []
        projection = family
    elif family == "debate_transcript":
        refs = {"sitting": {"type": "DebateSitting", "answer": True,
                            "selector": {"kind": "sittingDate", "date": "2015-07-02", "chamber": "dail"}},
                "record": {"type": "DebateRecord"}}
        relations = [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}]
        projection = family
    else:
        raise PlanError("This question is outside the supported Stage C question families.")
    answer_ref = "party" if family == "dail_parties_and_groups" else next(iter(refs))
    plan = {"version": 2, "asOf": as_of.isoformat(), "family": family,
            "referents": refs, "relations": relations,
            "answer": {"kind": "family_result", "referent": answer_ref, "projection": projection}}
    if family == "debate_lookup":
        plan["constraints"] = [
            {"referent": "sitting", "field": "date", "operator": "on", "value": debate_date or "2026-09-24"},
            {"referent": "record", "field": "chamber", "operator": "equals", "value": "dail"},
        ]
    return plan


def stage_c_request_family(question: str) -> str | None:
    text = question.strip()
    if re.search(r"\bhow\s+many\s+members\s+were\s+in\s+the\s+[0-9]{1,3}(?:st|nd|rd|th)\s+dáil\b", text, re.I):
        return "dail_seats"
    if re.search(r"\bwhat\s+are\s+the\s+groups\s+and\s+parties\s+in\s+the\s+[0-9]{1,3}(?:st|nd|rd|th)\s+dáil\b", text, re.I):
        return "dail_parties_and_groups"
    if re.search(r"\bbill\s+48\s+from\s+2024\b", text, re.I):
        return "bill_quarantine"
    if re.search(r"\bshow\s+me\s+the\s+dáil\s+debate\s+from\s+[0-9]{1,2}\s+[a-z]+\s+[0-9]{4}\b", text, re.I):
        return "debate_lookup"
    if re.search(r"\bwhen\s+did\s+PAC\s+last\s+examine\s+the\s+HSE\b", text, re.I):
        return "committee_topic_latest"
    if re.search(r"\bwhich\s+members\s+voted\s+for\s+the\s+artificial\s+intelligence\s+companion\s+services\s+bill\b", text, re.I):
        return "bill_votes"
    if re.search(r"\bwhat\s+did\s+speakers\s+say\s+in\s+the\s+dáil\s+debate\s+on\s+2\s+july\s+2015\b", text, re.I):
        return "debate_transcript"
    return None


def plan_stage_c(question: str, *, as_of: date) -> dict[str, Any] | None:
    text = question.strip()
    family = stage_c_request_family(text)
    if family == "dail_seats":
        seat = re.search(r"\b(?P<term>[0-9]{1,3}(?:st|nd|rd|th))\s+dáil\b", text, re.I)
        if seat:
            ordinal = int(_ORDINAL.search(seat.group("term")).group("number"))
            suffix = _ORDINAL.search(seat.group("term")).group(0)[len(str(ordinal)):].casefold()
            if suffix != _ordinal_suffix(ordinal):
                raise InvalidStageCRequest("Use the standard ordinal suffix for the requested Dáil term.")
            return validate_stage_c_plan(_make_plan(family, as_of, ordinal=ordinal))
    if family == "dail_parties_and_groups":
        parties = re.search(r"\b(?P<term>[0-9]{1,3}(?:st|nd|rd|th))\s+dáil\b", text, re.I)
        if parties:
            ordinal = int(_ORDINAL.search(parties.group("term")).group("number"))
            suffix = _ORDINAL.search(parties.group("term")).group(0)[len(str(ordinal)):].casefold()
            if suffix != _ordinal_suffix(ordinal):
                raise InvalidStageCRequest("Use the standard ordinal suffix for the requested Dáil term.")
            return validate_stage_c_plan(_make_plan(family, as_of, ordinal=ordinal))
    if family == "bill_quarantine":
        return validate_stage_c_plan(_make_plan(family, as_of))
    if family == "debate_lookup":
        debate = re.search(r"\bfrom\s+(?P<date>[0-9]{1,2}\s+[a-z]+\s+[0-9]{4})\b", text, re.I)
        try:
            iso_date = datetime.strptime(debate.group("date"), "%d %B %Y").date().isoformat()
        except (AttributeError, ValueError) as error:
            raise InvalidStageCRequest("The debate date must be a valid calendar date.") from error
        return validate_stage_c_plan(_make_plan(family, as_of, debate_date=iso_date))
    if family in {"committee_topic_latest", "bill_votes", "debate_transcript"}:
        return validate_stage_c_plan(_make_plan(family, as_of))
    return None


def validate_stage_c_plan(plan: dict[str, Any]) -> dict[str, Any]:
    family = plan.get("family")
    expected = _KNOWN_CATALOGUE.get(family)
    allowed_keys = {"version", "asOf", "family", "referents", "relations", "answer"}
    if family == "debate_lookup": allowed_keys.add("constraints")
    if expected is None or plan.get("version") != 2 or set(plan) != allowed_keys:
        raise PlanError("Malformed or unsupported Stage C v2 plan.")
    try:
        date.fromisoformat(plan["asOf"])
    except (TypeError, ValueError) as error:
        raise PlanError("Stage C asOf must be an ISO calendar date.") from error
    specs = {"dail_seats": ({"term": "DailTerm"}, "term", "dail_seats"),
             "dail_parties_and_groups": ({"term": "DailTerm", "party": "ParliamentaryParty"}, "party", "dail_parties_and_groups"),
             "bill_quarantine": ({"bill": "Bill"}, "bill", family),
             "debate_lookup": ({"sitting": "DebateSitting", "record": "DebateRecord"}, "sitting", family),
             "committee_topic_latest": ({"committee": "Committee", "hearing": "DebateRecord"}, "committee", family),
             "bill_votes": ({"bill": "Bill"}, "bill", family),
             "debate_transcript": ({"sitting": "DebateSitting", "record": "DebateRecord"}, "sitting", family)}
    ref_types, answer_ref, projection = specs[family]
    refs = plan.get("referents")
    if not isinstance(refs, dict) or set(refs) != set(ref_types) or any(refs[key].get("type") != kind for key, kind in ref_types.items()):
        raise PlanError(f"{family} referents do not match the reviewed typed path.")
    if plan["answer"] != {"kind": "family_result", "referent": answer_ref, "projection": projection}:
        raise PlanError(f"{family} answer projection is not the reviewed projection.")
    from .composable_plan import _PLAN_CONTRACT
    contract = _PLAN_CONTRACT
    family_contract = next((item for item in contract.get("questionFamilies", []) if item["id"] == family), None)
    if not family_contract or expected not in family_contract.get("cases", []):
        raise PlanError("Stage C family has no reviewed case contract.")
    if family == "dail_seats":
        selector = refs["term"].get("selector")
        if set(refs["term"]) != {"type", "selector"} or not isinstance(selector, dict) or set(selector) != {"kind", "number"} or selector["kind"] != "termNumber" or type(selector["number"]) is not int or not 1 <= selector["number"] <= 999:
            raise PlanError("Seat lookup requires one positive numbered Dáil term.")
    elif family == "dail_parties_and_groups":
        selector = refs["term"].get("selector")
        if set(refs["term"]) != {"type", "selector"} or not isinstance(selector, dict) or set(selector) != {"kind", "number"} or selector["kind"] != "termNumber" or type(selector["number"]) is not int or not 1 <= selector["number"] <= 999 or refs["party"] != {"type": "ParliamentaryParty", "answer": True}:
            raise PlanError("Party listing requires one numbered Dáil term and term-scoped party answer.")
    elif family == "bill_quarantine":
        if refs["bill"] != {"type": "Bill", "selector": {"kind": "numberYear", "year": 2024, "number": "48"}}:
            raise PlanError("The reviewed Bill source diagnostic is scoped only to Bill 2024/48.")
    elif family == "debate_lookup":
        if refs["sitting"] != {"type": "DebateSitting", "answer": True} or refs["record"] != {"type": "DebateRecord"}:
            raise PlanError("The missing-date Debate request requires the reviewed sitting and record referents.")
        constraints = plan.get("constraints")
        if (not isinstance(constraints, list) or len(constraints) != 2
                or any(not isinstance(item, dict) or set(item) != {"referent", "field", "operator", "value"} for item in constraints)
                or constraints[0].get("referent") != "sitting" or constraints[0].get("field") != "date"
                or constraints[0].get("operator") != "on" or constraints[1] != {"referent": "record", "field": "chamber", "operator": "equals", "value": "dail"}):
            raise PlanError("Dáil Debate lookup requires a reviewed date and Dáil graph-route chamber constraint.")
        try: date.fromisoformat(constraints[0]["value"])
        except (TypeError, ValueError) as error: raise PlanError("Debate date must be an ISO calendar date.") from error
    elif family == "committee_topic_latest":
        if refs["committee"] != {"type": "Committee", "mention": "Committee of Public Accounts"} or refs["hearing"] != {"type": "DebateRecord", "mention": "HSE"}:
            raise PlanError("PAC coverage diagnostics require the reviewed committee alias and named topic.")
    elif family == "bill_votes":
        if refs["bill"] != {"type": "Bill", "mention": "Artificial Intelligence Companion Services Bill"}:
            raise PlanError("Vote availability diagnostic is scoped to the reviewed Bill mention.")
    elif family == "debate_transcript":
        if refs["sitting"] != {"type": "DebateSitting", "answer": True,
                               "selector": {"kind": "sittingDate", "date": "2015-07-02", "chamber": "dail"}} or refs["record"] != {"type": "DebateRecord"}:
            raise PlanError("Transcript diagnostic is scoped to the approved Dáil sitting request.")
    if not isinstance(plan["relations"], list):
        raise PlanError("Stage C relations must be a list.")
    expected_relations = {
        "dail_seats": [], "dail_parties_and_groups": [{"id": "party-active-term", "fact": "party_active_during_term", "from": "party", "to": "term"}],
        "bill_quarantine": [], "debate_lookup": [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}],
        "committee_topic_latest": [], "bill_votes": [],
        "debate_transcript": [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}],
    }
    if plan["relations"] != expected_relations[family]:
        raise PlanError("Stage C relations do not match the reviewed family path.")
    for pattern_id in family_contract.get("patterns", []):
        graph = "houses" if pattern_id.startswith("house-term") else "parties" if pattern_id == "party-term-occurrence" else "debates" if pattern_id.startswith("debate-sitting") else "bill-records"
        _reviewed_pattern(pattern_id, graph)
    return plan


def _route(graph_family: str) -> tuple[str, str]:
    family = next((item for item in load_query_contract()["graphFamilies"] if item["id"] == graph_family), None)
    graph = family.get("graph", {}) if family else {}
    template = graph.get("iriTemplate")
    if graph_family == "bill-records":
        if family.get("owner") != "Bills ETL" or graph.get("kind") != "resource-pattern" or template != "https://data.oireachtas.ie/graph/bill/{year}/{number}":
            raise PlanError("Reviewed Bill owner route is absent or malformed.")
        return template, r"^https://data[.]oireachtas[.]ie/graph/bill/[0-9]{4}/[0-9]+$"
    if not family or family.get("owner") != "Debates ETL" or graph.get("kind") != "resource-pattern":
        raise PlanError("Reviewed Debate owner route is absent or malformed.")
    return template, r"^https://data[.]oireachtas[.]ie/graph/debate/[^/]+/[0-9]{4}-[0-9]{2}-[0-9]{2}/debate$"


def _fixed_owner_graph(graph_family: str, owner: str, expected_iri: str) -> str:
    family = next((item for item in load_query_contract()["graphFamilies"] if item.get("id") == graph_family), None)
    graph = family.get("graph", {}) if family else {}
    if (not family or family.get("owner") != owner
            or family.get("availability") != "published-when-loaded"
            or graph.get("kind") != "fixed" or graph.get("iri") != expected_iri):
        raise PlanError(f"Reviewed {owner} fixed graph owner route is absent or malformed.")
    return expected_iri


def _require_queryable_type(qname: str) -> None:
    contract = load_query_contract()
    if qname not in contract.get("queryableClasses", []):
        raise PlanError(f"Reviewed RDF class {qname!r} is not queryable.")


def _require_queryable_predicates(qnames: tuple[str, ...], supported_predicates) -> None:
    contract = load_query_contract()
    for qname in qnames:
        _reviewed_predicate_for_qname(qname)
        prefix, local = qname.split(":", 1)
        namespace = contract.get("namespaces", {}).get(prefix)
        if not namespace or URIRef(namespace + local) not in set(supported_predicates):
            raise PlanError(f"Reviewed query predicate {qname!r} is not allowlisted.")


def _safe_query(query: str, *, supported_predicates) -> str:
    try:
        return validate_sparql(query, supported_predicates=supported_predicates)
    except NLQError as error:
        raise PlanError(f"Stage C query failed local read-only safety validation and was not sent: {error}") from error


def _house_term_ordinal_query(ordinal: int, *, supported_predicates) -> str:
    graph = _fixed_owner_graph("houses", "Houses ETL", "https://data.oireachtas.ie/graph/houses")
    pattern = _reviewed_pattern("house-term-ordinal", "houses")
    if (_pattern_rdf_type(pattern, "?term") != "agents:DailTerm"
            or _pattern_predicate(pattern, "?term", "?ordinal") != "agents:termNo"):
        raise PlanError("Reviewed HouseTerm ordinal pattern is incomplete.")
    _require_queryable_type("agents:DailTerm")
    _require_queryable_predicates(("agents:termNo",), supported_predicates)
    query = _PREFIXES + f'''SELECT DISTINCT ?term WHERE {{
  GRAPH <{graph}> {{ ?term a agents:DailTerm ; agents:termNo "{ordinal}"^^xsd:integer . }}
}} LIMIT 100'''
    return _safe_query(query, supported_predicates=supported_predicates)


def _house_term_seats_query(ordinal: int, *, supported_predicates) -> str:
    graph = _fixed_owner_graph("houses", "Houses ETL", "https://data.oireachtas.ie/graph/houses")
    pattern = _reviewed_pattern("house-term-seat-complement", "houses")
    expected = (("?term", "agents:DailTerm"), ("?term", "?ordinal", "agents:termNo"), ("?term", "?seatCount", "agents:seats"))
    if any(_pattern_rdf_type(pattern, subject) != rdf_type for subject, rdf_type in [expected[0]]):
        raise PlanError("Reviewed seat pattern does not assert the typed DailTerm.")
    for subject, obj, predicate in expected[1:]:
        if _pattern_predicate(pattern, subject, obj) != predicate:
            raise PlanError("Reviewed seat pattern does not contain term number and seat complement.")
    _require_queryable_type("agents:DailTerm")
    _require_queryable_predicates(("agents:termNo", "agents:seats"), supported_predicates)
    query = _PREFIXES + f'''SELECT DISTINCT ?term ?seats WHERE {{
  GRAPH <{graph}> {{
    ?term a agents:DailTerm ; agents:termNo "{ordinal}"^^xsd:integer .
    OPTIONAL {{ ?term agents:seats ?seats . }}
  }}
}} LIMIT 100'''
    return _safe_query(query, supported_predicates=supported_predicates)


def _party_listing_gates(*, supported_predicates) -> tuple[str, str]:
    houses_graph = _fixed_owner_graph("houses", "Houses ETL", "https://data.oireachtas.ie/graph/houses")
    parties_graph = _fixed_owner_graph("parties", "Parties ETL", "https://data.oireachtas.ie/graph/parties")
    ordinal = _reviewed_pattern("house-term-ordinal", "houses")
    party = _reviewed_pattern("party-term-occurrence", "parties")
    if (_pattern_rdf_type(ordinal, "?term") != "agents:DailTerm"
            or _pattern_predicate(ordinal, "?term", "?ordinal") != "agents:termNo"):
        raise PlanError("Reviewed Houses term-number pattern is incomplete.")
    if (_pattern_rdf_type(party, "?party") != "members:ParliamentaryParty"
            or _pattern_predicate(party, "?party", "?term") != "members:activeDuringTerm"
            or _pattern_predicate(party, "?party", "?englishLabel") != "skos:prefLabel"):
        raise PlanError("Reviewed term-scoped ParliamentaryParty pattern or display label is incomplete.")
    _reviewed_cross_graph_join("parties", "members:activeDuringTerm", "houses")
    _reviewed_predicate("party_active_during_term")
    _require_queryable_type("members:ParliamentaryParty")
    _require_queryable_type("agents:DailTerm")
    _require_queryable_predicates(("agents:termNo", "members:activeDuringTerm", "skos:prefLabel"), supported_predicates)
    return houses_graph, parties_graph


def _parties_query(term_iri: str, *, supported_predicates) -> str:
    _houses_graph, parties_graph = _party_listing_gates(supported_predicates=supported_predicates)
    query = _PREFIXES + f'''SELECT DISTINCT ?party ?label WHERE {{
  GRAPH <{parties_graph}> {{
    ?party a members:ParliamentaryParty ; members:activeDuringTerm <{term_iri}> .
    OPTIONAL {{ ?party skos:prefLabel ?label . }}
  }}
}} ORDER BY ?party LIMIT 100'''
    return _safe_query(query, supported_predicates=supported_predicates)


def _parties_presence_query(*, supported_predicates) -> str:
    _houses_graph, graph = _party_listing_gates(supported_predicates=supported_predicates)
    pattern = _reviewed_pattern("party-term-occurrence", "parties")
    if _pattern_rdf_type(pattern, "?party") != "members:ParliamentaryParty":
        raise PlanError("Reviewed party type pattern is incomplete.")
    _require_queryable_type("members:ParliamentaryParty")
    return _safe_query(_PREFIXES + f'''ASK WHERE {{ GRAPH <{graph}> {{ ?party a members:ParliamentaryParty . }} }}''',
                       supported_predicates=supported_predicates)


def _bill_exists_query(year: int, number: str, *, supported_predicates) -> str:
    pattern = _reviewed_pattern("bill-lifecycle", "bill-records")
    if (_pattern_rdf_type(pattern, "?bill") != "eli-dl:DraftLegislationWork"
            or _pattern_predicate(pattern, "?bill", "?englishOrIrishTitle") != "dct:title"):
        raise PlanError("Reviewed Bill lifecycle pattern is missing its Bill type.")
    if not any(triple[0] == "?bill" and triple[1] == "eli:work_type" and triple[2] == "agents:Bill"
               for triple in pattern.get("triples", [])):
        raise PlanError("Reviewed Bill lifecycle pattern does not distinguish Bill documents.")
    _, route = _route("bill-records")
    bill_iri = f"https://data.oireachtas.ie/ie/oireachtas/bill/{year}/{number}"
    query = _PREFIXES + f'''ASK WHERE {{
  GRAPH ?billGraph {{ <{bill_iri}> a eli-dl:DraftLegislationWork ; eli:work_type agents:Bill . }}
  FILTER(STR(?billGraph) = "https://data.oireachtas.ie/graph/bill/{year}/{number}")
  FILTER(REGEX(STR(?billGraph), {json.dumps(route)}))
}}'''
    return validate_sparql(query, supported_predicates=supported_predicates)


def _debate_query(as_of: date, debate_date: str, *, supported_predicates) -> tuple[str, dict[str, Any]]:
    from .composable_plan import compile_debate_answer_query
    inner = {"version": 2, "asOf": as_of.isoformat(),
             "referents": {"sitting": {"type": "DebateSitting", "answer": True}, "record": {"type": "DebateRecord"}},
             "relations": [{"id": "sitting-record", "fact": "sitting_produced_record", "from": "sitting", "to": "record"}],
             "constraints": [{"referent": "sitting", "field": "date", "operator": "on", "value": debate_date},
                             {"referent": "record", "field": "chamber", "operator": "equals", "value": "dail"}],
             "answer": {"kind": "entities", "referent": "sitting", "distinctBy": "identity", "display": ["date", "officialLink"]}}
    return compile_debate_answer_query(inner, supported_predicates=supported_predicates), inner


def handle_stage_c(question: str, *, as_of: date, fuseki, supported_predicates) -> PlanOutcome | None:
    request_family = stage_c_request_family(question)
    if request_family is None:
        return None
    try:
        plan = plan_stage_c(question, as_of=as_of)
    except InvalidStageCRequest as error:
        return PlanOutcome("unsupported_capability", diagnostic=str(error), request_family=request_family)
    except PlanError as error:
        return PlanOutcome("unsupported_mapping", diagnostic=str(error), request_family=request_family)
    if plan is None:
        return PlanOutcome("unsupported_capability", diagnostic="The recognized Stage C request could not be planned.", request_family=request_family)
    family = plan["family"]
    try:
        if family == "dail_seats":
            ordinal = plan["referents"]["term"]["selector"]["number"]
            query = _house_term_seats_query(ordinal, supported_predicates=supported_predicates)
            result = fuseki.query(query)
            if result.kind != "select":
                return PlanOutcome("query_execution_failed", plan=plan, sparql=query,
                                   diagnostic="Fuseki returned an unexpected response kind for the typed seat lookup.")
            if len(result.rows) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"The {_ordinal_label(ordinal)} seat/identity lookup reached the 100-row safety cap; its term identity and seat value cannot be established as unambiguous.")
            by_term: dict[str, list[str]] = {}
            for row in result.rows:
                if len(row) < 2 or row[0] == "—":
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                       diagnostic=f"The {_ordinal_label(ordinal)} HouseTerm identity is malformed in the Houses graph.")
                if not row[0].startswith("https://data.oireachtas.ie/") or any(ch.isspace() for ch in row[0]):
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                       diagnostic=f"The {_ordinal_label(ordinal)} HouseTerm identity is not a valid local resource IRI.")
                by_term.setdefault(row[0], []).append(row[1])
            if not by_term:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"No typed HouseTerm with ordinal {_ordinal_label(ordinal)} is available in the local Houses graph.")
            if len(by_term) != 1:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"More than one typed HouseTerm has ordinal {_ordinal_label(ordinal)}; the term identity is ambiguous.")
            term_iri = next(iter(by_term))
            values = by_term[term_iri]
            if "—" in values:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"The typed {_ordinal_label(ordinal)} HouseTerm has no seat-complement value; no total was inferred from Member records.")
            if len(set(values)) != 1:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"The typed {_ordinal_label(ordinal)} HouseTerm has conflicting seat assertions.")
            binding = values[0]
            match = _XSD_INTEGER_CELL.fullmatch(binding)
            if not match:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, diagnostic=f"The {_ordinal_label(ordinal)} has an invalid typed seat-complement value; no total was inferred.")
            count = int(match.group("lexical"))
            if count <= 0:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"The {_ordinal_label(ordinal)} seat complement is not a positive xsd:integer.")
            return PlanOutcome("success", plan=plan, sparql=query,
                               result=QueryResult("select", ("Dáil term", "Seats"), ((_ordinal_label(ordinal), str(count)),)),
                               diagnostic=f"The Houses graph records {count} seats for the {_ordinal_label(ordinal)}.")
        if family == "dail_parties_and_groups":
            ordinal = plan["referents"]["term"]["selector"]["number"]
            _party_listing_gates(supported_predicates=supported_predicates)
            term_query = _house_term_ordinal_query(ordinal, supported_predicates=supported_predicates)
            terms = fuseki.query(term_query)
            if terms.kind != "select":
                return PlanOutcome("query_execution_failed", plan=plan, sparql=term_query,
                                   diagnostic="Fuseki returned an unexpected response kind while resolving the Dáil term.")
            if len(terms.rows) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=term_query,
                                   diagnostic=f"The typed HouseTerm identity lookup for {_ordinal_label(ordinal)} reached the 100-row cap; no term was selected. {_GROUPS_GAP}")
            term_ids: set[str] = set()
            for row in terms.rows:
                if not row or row[0] == "—" or not row[0].startswith("https://data.oireachtas.ie/") or any(ch.isspace() for ch in row[0]):
                    return PlanOutcome("source_data_unavailable", plan=plan, sparql=term_query,
                                       diagnostic=f"The Houses graph returned a malformed local HouseTerm identity; no party join was run. {_GROUPS_GAP}")
                term_ids.add(row[0])
            if not term_ids:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=term_query,
                                   diagnostic=f"No typed HouseTerm with ordinal {_ordinal_label(ordinal)} is available in the local Houses graph; no party list was inferred. {_GROUPS_GAP}")
            if len(term_ids) != 1:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=term_query,
                                   diagnostic=f"More than one typed HouseTerm has ordinal {_ordinal_label(ordinal)}; no party identity join was run. {_GROUPS_GAP}")
            term_iri = next(iter(term_ids))
            try:
                _require_local_iri(term_iri, "DailTerm")
            except NLQError:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=term_query,
                                   diagnostic=f"The exact Dáil term is not a safe local resource IRI; no party join was run. {_GROUPS_GAP}")
            query = _parties_query(term_iri, supported_predicates=supported_predicates)
            result = fuseki.query(query)
            if result.kind != "select":
                return PlanOutcome("query_execution_failed", plan=plan, sparql=query,
                                   diagnostic="Fuseki returned an unexpected response kind for the term-scoped party lookup.")
            if any(len(row) < 2 or row[0] == "—" or not row[0].startswith("https://data.oireachtas.ie/") or any(ch.isspace() for ch in row[0]) for row in result.rows):
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=f"A term-scoped party row has no valid local ParliamentaryParty identity; no identity was discarded. {_GROUPS_GAP}")
            display_rows = tuple((row[1].removesuffix("@en") if row[1] != "—" else "Label unavailable", row[0])
                                 for row in result.rows)
            display_result = QueryResult("select", ("Party", "Identity"), display_rows,
                                         raw_json=result.raw_json)
            if len(result.rows) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, result=display_result,
                                   diagnostic=f"Party results for the {_ordinal_label(ordinal)} reached the 100-row safety cap and may be incomplete. ParliamentaryGroup data is not populated in the current queryable dataset.")
            if not result.rows:
                presence_query = _parties_presence_query(supported_predicates=supported_predicates)
                presence = fuseki.query(presence_query)
                if presence.kind != "ask" or presence.boolean is None:
                    return PlanOutcome("query_execution_failed", plan=plan, sparql=presence_query,
                                       diagnostic="Fuseki returned an unexpected response kind while checking local party-data coverage.")
                if not presence.boolean:
                    reason = "No typed ParliamentaryParty records are queryable in the local Parties graph, so a term-scoped party list cannot be established."
                else:
                    reason = f"No ParliamentaryParty records linked to the exact {_ordinal_label(ordinal)} HouseTerm were found in the local Parties graph."
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=presence_query,
                                   diagnostic=f"{reason} This does not prove that no parties existed. {_GROUPS_GAP}")
            if any(row[1] == "—" for row in result.rows):
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, result=display_result,
                                   diagnostic=f"Some ParliamentaryParty rows for the {_ordinal_label(ordinal)} have no readable label; their exact IRIs remain listed. {_GROUPS_GAP}")
            return PlanOutcome("success", plan=plan, sparql=query, result=display_result,
                               diagnostic=f"Term-scoped ParliamentaryParty records for the {_ordinal_label(ordinal)} are listed separately. {_GROUPS_GAP}")
        if family == "bill_quarantine":
            query = _bill_exists_query(2024, "48", supported_predicates=supported_predicates)
            exists = fuseki.query(query)
            if exists.kind != "ask" or exists.boolean is None:
                return PlanOutcome("query_execution_failed", plan=plan, sparql=query,
                                   diagnostic="Fuseki returned an unexpected response kind for the exact Bill identity check.")
            if not exists.boolean:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic="The queried local dataset has no typed Bill 2024/48 at its exact Bill identity and owner-graph route, so its details are unavailable here. The reviewed development capture excludes this source record because of a `bill-stage/None` identity problem; that source-specific issue does not prove the Bill never existed or establish why any other dataset lacks it.")
            from .stage_b import handle_stage_b
            reused = handle_stage_b("Tell me about Bill 48 from 2024", as_of=as_of, fuseki=fuseki, supported_predicates=supported_predicates)
            return reused or PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                         diagnostic="The Bill 2024/48 graph is present, but the reviewed Bill lookup path did not return a result.")
        if family == "debate_lookup":
            debate_date = plan["constraints"][0]["value"]
            query, inner = _debate_query(as_of, debate_date, supported_predicates=supported_predicates)
            result = fuseki.query(query)
            if result.kind != "select":
                return PlanOutcome("query_execution_failed", plan=plan, sparql=query,
                                   diagnostic="Fuseki returned an unexpected response kind for the actual DebateSitting lookup.")
            from .composable_plan import readable_debate_result
            readable = readable_debate_result(result)
            if len(readable.rows) >= 100:
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, result=readable,
                                   diagnostic=f"The local Dáil DebateSitting result for {debate_date} reached the 100-row safety cap; the list is incomplete and cannot be presented as exact.")
            if not readable.rows:
                if debate_date == "2026-09-24":
                    absence_detail = "The reviewed pinned development capture also omits a Dáil Debate graph for 2026-09-24."
                else:
                    absence_detail = "No pinned-capture coverage conclusion is available for this date."
                return PlanOutcome("source_data_unavailable", plan=plan, sparql=query,
                                   diagnostic=(f"No matching actual Dáil DebateSitting for {debate_date} was found in the queried local dataset. {absence_detail} written-answer records do not establish a sitting, and local absence is not evidence that no debate took place."))
            return PlanOutcome("success", plan=plan, sparql=query, result=readable,
                               diagnostic="Found an actual Dáil DebateSitting and its official DebateRecord link in the local slice.")
        if family == "committee_topic_latest":
            return PlanOutcome("source_data_unavailable", plan=plan,
                                   diagnostic=f"PAC is interpreted as the Committee of Public Accounts. The pinned 24 September 2026 record supplies Debate metadata/link only; it does not establish substantive HSE examination or adequate coverage through {plan['asOf']}, so a latest-hearing date cannot be verified.")
        if family == "bill_votes":
            return PlanOutcome("source_data_unavailable", plan=plan,
                               diagnostic="Bill-linked voting records and a reviewed vote query path are not available. Bill sponsorship records are not evidence of how Members voted.")
        if family == "debate_transcript":
            return PlanOutcome("source_data_unavailable", plan=plan,
                               diagnostic="Debate transcript speech text is not queryable and no approved transcript retrieval path exists. Debate metadata or an official record link cannot establish what speakers said.")
    except PlanError as error:
        return PlanOutcome("unsupported_mapping", plan=plan, diagnostic=str(error), request_family=request_family)
    except NLQError as error:
        return PlanOutcome("query_execution_failed", plan=plan, diagnostic=f"The local query could not be executed or its response could not be parsed: {error}", request_family=request_family)
    return PlanOutcome("unsupported_capability", plan=plan, diagnostic="No reviewed Stage C execution path exists for this request.")
