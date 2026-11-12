#!/usr/bin/env python3
"""Independent, bounded, read-only live RDF oracle for the K+R probe.

This tool does not import or execute Query Service/kernel code. It queries exact
resource paths, preserves untyped/absent evidence, and writes a separate capture
for each run. It uses only SPARQL SELECT requests against the configured local
Fuseki endpoint; no update or Graph Store request is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORACLE_DIR = ROOT / "docs/reports/query-service/composition-live-kr-20261112/oracle"
ENDPOINT = "http://localhost:3030/houses/query"
AS_OF = date(2026, 11, 11)
PAGE_SIZE = 100
REQUEST_TIMEOUT_SECONDS = 15
MAX_DIAGNOSTIC_REQUESTS = 40
MAX_DIAGNOSTIC_ROWS = 5000

KILDARE_NORTH = (
    "https://data.oireachtas.ie/ie/oireachtas/house/dail/34/"
    "constituency/Kildare-North"
)
COMMITTEE = (
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/"
    "committee_of_public_accounts"
)

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
FOAF_NAME = "http://xmlns.com/foaf/0.1/name"
SKOS_PREF_LABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
AGENTS = "https://data.oireachtas.ie/ontology#"
MEMBERS = "https://data.oireachtas.ie/ontology/members#"
XSD = "http://www.w3.org/2001/XMLSchema#"
DCT_TEMPORAL = "http://purl.org/dc/terms/temporal"
DCAT_START = "http://www.w3.org/ns/dcat#startDate"
DCAT_END = "http://www.w3.org/ns/dcat#endDate"

HOUSES_GRAPH = "https://data.oireachtas.ie/graph/houses"
CONSTITUENCIES_GRAPH = "https://data.oireachtas.ie/graph/constituencies"
COMMITTEES_GRAPH = "https://data.oireachtas.ie/graph/committees"
PROVENANCE_GRAPH = "https://data.oireachtas.ie/graph/provenance"
MEMBER_GRAPH_PREFIX = "https://data.oireachtas.ie/graph/member/"

PREFIXES = """\
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX agents: <https://data.oireachtas.ie/ontology#>
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def iri(value: str) -> str:
    if not value.startswith("https://") or any(c in value for c in "<>\"{}|\\^`"):
        raise ValueError(f"Unsafe IRI for VALUES clause: {value!r}")
    return f"<{value}>"


class ReadOnlyFuseki:
    def __init__(self) -> None:
        self.request_count = 0
        self.row_count = 0
        self.ledger: list[dict[str, Any]] = []
        self.bound_exceeded: str | None = None

    def select(self, label: str, ordered_select: str) -> dict[str, Any]:
        """Run an ORDER BY SELECT as deterministic LIMIT/OFFSET pages."""
        result: dict[str, Any] = {
            "label": label,
            "query_without_page_clause": ordered_select,
            "page_size": PAGE_SIZE,
            "complete": False,
            "completion_reason": None,
            "row_count": 0,
            "pages": [],
        }
        offset = 0
        while True:
            if self.request_count >= MAX_DIAGNOSTIC_REQUESTS:
                result["completion_reason"] = "diagnostic request bound reached"
                self.bound_exceeded = result["completion_reason"]
                break
            if self.row_count >= MAX_DIAGNOSTIC_ROWS:
                result["completion_reason"] = "diagnostic row bound reached"
                self.bound_exceeded = result["completion_reason"]
                break

            page_limit = min(PAGE_SIZE, MAX_DIAGNOSTIC_ROWS - self.row_count)
            query = f"{ordered_select}\nLIMIT {page_limit} OFFSET {offset}"
            started = utc_now()
            self.request_count += 1
            entry: dict[str, Any] = {
                "request_number": self.request_count,
                "section": label,
                "offset": offset,
                "limit": page_limit,
                "started_at": started,
                "completed_at": None,
                "http_status": None,
                "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
                "query": query,
                "row_count": None,
                "status": "in_progress",
            }
            page: dict[str, Any] = {
                "offset": offset,
                "request_number": self.request_count,
                "query": query,
                "query_sha256": entry["query_sha256"],
                "raw_response_text": None,
                "raw_typed_response": None,
                "error": None,
            }
            try:
                payload = urllib.parse.urlencode({"query": query}).encode("utf-8")
                request = urllib.request.Request(
                    ENDPOINT,
                    data=payload,
                    method="POST",
                    headers={
                        "Accept": "application/sparql-results+json",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "User-Agent": "nlq-live-kr-independent-oracle/1.0",
                    },
                )
                with urllib.request.urlopen(
                    request, timeout=REQUEST_TIMEOUT_SECONDS
                ) as response:
                    status = response.status
                    raw_bytes = response.read()
                raw_text = raw_bytes.decode("utf-8")
                typed_response = json.loads(raw_text)
                bindings = typed_response.get("results", {}).get("bindings")
                if not isinstance(bindings, list):
                    raise ValueError("SPARQL JSON response has no results.bindings list")
                page_rows = len(bindings)
                page["raw_response_text"] = raw_text
                page["raw_typed_response"] = typed_response
                entry["http_status"] = status
                entry["row_count"] = page_rows
                entry["status"] = "complete"
                self.row_count += page_rows
                result["row_count"] += page_rows
                result["pages"].append(page)
                entry["completed_at"] = utc_now()
                self.ledger.append(entry)

                if page_rows < page_limit:
                    result["complete"] = True
                    result["completion_reason"] = "final page returned fewer than 100 rows"
                    break
                if page_limit < PAGE_SIZE:
                    result["completion_reason"] = (
                        "diagnostic row bound reached before completion could be proven"
                    )
                    self.bound_exceeded = result["completion_reason"]
                    break
                offset += page_limit
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                entry["http_status"] = exc.code
                entry["status"] = "http_error"
                entry["error"] = str(exc)
                entry["completed_at"] = utc_now()
                page["error"] = {"message": str(exc), "body": body}
                result["pages"].append(page)
                self.ledger.append(entry)
                result["completion_reason"] = "HTTP error"
                break
            except Exception as exc:  # preserve a diagnostic instead of hiding partial evidence
                entry["status"] = "request_or_decode_error"
                entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["completed_at"] = utc_now()
                page["error"] = {"message": f"{type(exc).__name__}: {exc}"}
                result["pages"].append(page)
                self.ledger.append(entry)
                result["completion_reason"] = "request or response decode error"
                break
        return result


def rows(section: dict[str, Any] | None) -> list[dict[str, dict[str, str]]]:
    if not section:
        return []
    output: list[dict[str, dict[str, str]]] = []
    for page in section.get("pages", []):
        response = page.get("raw_typed_response") or {}
        output.extend(response.get("results", {}).get("bindings", []))
    return output


def value(binding: dict[str, Any] | None) -> str | None:
    return binding.get("value") if binding else None


def binding_dict(binding: dict[str, Any] | None) -> dict[str, str] | None:
    if not binding:
        return None
    return {key: str(val) for key, val in binding.items()}


def is_xsd_string(binding: dict[str, str]) -> bool:
    """RDF 1.1 simple literals have xsd:string value semantics."""
    return (
        binding.get("type") == "literal"
        and not binding.get("xml:lang")
        and binding.get("datatype") in (None, XSD + "string")
    )


def subject_facts(
    fact_rows: list[dict[str, dict[str, str]]],
    subject_var: str,
    predicate_var: str,
    object_var: str,
) -> dict[str, dict[str, list[dict[str, str]]]]:
    grouped: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in fact_rows:
        subject = value(row.get(subject_var))
        predicate = value(row.get(predicate_var))
        obj = binding_dict(row.get(object_var))
        if subject and predicate and obj and obj not in grouped[subject][predicate]:
            grouped[subject][predicate].append(obj)
    for predicates in grouped.values():
        for objects in predicates.values():
            objects.sort(key=lambda x: (x.get("type", ""), x.get("value", ""), x.get("datatype", ""), x.get("xml:lang", "")))
    return grouped


def graph_facts(
    fact_rows: list[dict[str, dict[str, str]]],
    graph_var: str,
    subject_var: str,
    predicate_var: str,
    object_var: str,
) -> dict[tuple[str, str], dict[str, list[dict[str, str]]]]:
    grouped: dict[tuple[str, str], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in fact_rows:
        graph = value(row.get(graph_var))
        subject = value(row.get(subject_var))
        predicate = value(row.get(predicate_var))
        obj = binding_dict(row.get(object_var))
        if graph and subject and predicate and obj and obj not in grouped[(graph, subject)][predicate]:
            grouped[(graph, subject)][predicate].append(obj)
    return grouped


def related_resource_iris(
    target_facts: list[dict[str, dict[str, str]]],
    term_facts: list[dict[str, dict[str, str]]],
) -> list[str]:
    wanted_predicates = {
        MEMBERS + "constituencyInHouseTerm",
        MEMBERS + "committeeInHouseTerm",
        DCT_TEMPORAL,
    }
    related: set[str] = set()
    for row in [*target_facts, *term_facts]:
        if value(row.get("predicate")) in wanted_predicates:
            obj = row.get("object", {})
            if obj.get("type") == "uri" and value(obj):
                related.add(value(obj) or "")
    return sorted(x for x in related if x)


def date_value(binding: dict[str, str]) -> tuple[date | None, str | None]:
    lexical = binding.get("value", "")
    if binding.get("type") != "literal" or binding.get("datatype") != XSD + "dateTime":
        return None, "expected a literal explicitly typed xsd:dateTime"
    if "T" not in lexical:
        return None, "xsd:dateTime lexical form has no T separator"
    try:
        parsed = datetime.fromisoformat(lexical.replace("Z", "+00:00"))
    except ValueError as exc:
        return None, f"invalid xsd:dateTime lexical form: {exc}"
    # asOf is date precision and source membership dates are dateTime. Keep the
    # source's local calendar date; do not invent a timezone for timezone-less RDF.
    return parsed.date(), None


def interval_status(
    range_facts: dict[str, list[dict[str, str]]] | None,
) -> dict[str, Any]:
    facts = range_facts or {}
    types = facts.get(RDF_TYPE, [])
    starts = facts.get(MEMBERS + "StartDate", [])
    ends = facts.get(MEMBERS + "EndDate", [])
    type_ok = any(
        x.get("type") == "uri" and x.get("value") == MEMBERS + "DateRange"
        for x in types
    )
    out: dict[str, Any] = {
        "range_types": types,
        "explicit_members_DateRange_type": type_ok,
        "start_values": starts,
        "end_values": ends,
        "as_of": AS_OF.isoformat(),
        "as_of_interpretation": "inclusive date-grain containment: compare the source xsd:dateTime calendar date to 2026-11-11; no time-of-day or timezone conversion",
        "status": "uncertain",
        "reasons": [],
    }
    if len(starts) != 1:
        out["reasons"].append("exactly one StartDate is required; missing or multiple values are uncertain")
        return out
    if len(ends) > 1:
        out["reasons"].append("multiple EndDate values are uncertain")
        return out
    start_date, start_error = date_value(starts[0])
    if start_error:
        out["reasons"].append(start_error)
        return out
    end_date: date | None = None
    if ends:
        end_date, end_error = date_value(ends[0])
        if end_error:
            out["reasons"].append(end_error)
            return out
    out["parsed_start_calendar_date"] = start_date.isoformat() if start_date else None
    out["parsed_end_calendar_date"] = end_date.isoformat() if end_date else None
    if start_date and start_date > AS_OF:
        out["status"] = "inactive"
        out["reasons"].append("StartDate is after the asOf calendar date")
        return out
    if end_date and end_date < AS_OF:
        out["status"] = "inactive"
        out["reasons"].append("EndDate is before the asOf calendar date")
        return out
    if not type_ok:
        out["reasons"].append("range lacks explicit members:DateRange type")
        return out
    out["status"] = "active"
    if not ends:
        out["reasons"].append("EndDate is absent; treated as open-ended per membership mapping")
    else:
        out["reasons"].append("inclusive date-point containment from explicit range endpoints")
    return out


def query_target_facts() -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?resource ?graph ?predicate ?object
WHERE {{
  VALUES ?resource {{ {iri(KILDARE_NORTH)} {iri(COMMITTEE)} }}
  GRAPH ?graph {{ ?resource ?predicate ?object }}
}}
ORDER BY ?resource ?graph ?predicate ?object"""


def query_all_dail_term_facts() -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?typeGraph ?graph ?term ?predicate ?object
WHERE {{
  GRAPH ?typeGraph {{ ?term rdf:type agents:DailTerm }}
  GRAPH ?graph {{ ?term ?predicate ?object }}
}}
ORDER BY ?typeGraph ?graph ?term ?predicate ?object"""


def query_committee_candidates() -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?committee ?predicate ?object
WHERE {{
  GRAPH {iri(COMMITTEES_GRAPH)} {{
    ?committee rdf:type members:Committee ; ?predicate ?object .
    FILTER(
        REGEX(STR(?committee), "(?i)public[_-]+accounts")
        || (
          ?predicate IN (rdfs:label, skos:prefLabel, foaf:name)
        && isLiteral(?object)
        && REGEX(STR(?object), "(?i)public[ ]+accounts")
        )
    )
  }}
}}
ORDER BY ?committee ?predicate ?object"""


def query_path_facts(path_predicate: str, target: str) -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?pathGraph ?graph ?membership ?predicate ?object
WHERE {{
  {{
    SELECT DISTINCT ?pathGraph ?membership
    WHERE {{ GRAPH ?pathGraph {{ ?membership <{path_predicate}> {iri(target)} }} }}
  }}
  GRAPH ?graph {{ ?membership ?predicate ?object }}
}}
ORDER BY ?pathGraph ?graph ?membership ?predicate ?object"""


def query_reverse_links(path_predicate: str, target: str) -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?membershipGraph ?memberGraph ?member ?membership
WHERE {{
  GRAPH ?membershipGraph {{ ?membership <{path_predicate}> {iri(target)} }}
  GRAPH ?memberGraph {{ ?member members:hasMembersMembership ?membership }}
}}
ORDER BY ?membershipGraph ?memberGraph ?member ?membership"""


def query_member_facts(path_predicate: str, target: str) -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?graph ?member ?predicate ?object
WHERE {{
  {{
    SELECT DISTINCT ?member
    WHERE {{
      GRAPH ?membershipGraph {{ ?membership <{path_predicate}> {iri(target)} }}
      GRAPH ?memberGraph {{ ?member members:hasMembersMembership ?membership }}
    }}
  }}
  GRAPH ?graph {{ ?member ?predicate ?object }}
}}
ORDER BY ?graph ?member ?predicate ?object"""


def query_membership_ranges(path_predicate: str, target: str) -> str:
    return PREFIXES + f"""\
SELECT DISTINCT ?membershipGraph ?rangeLinkGraph ?rangeGraph ?membership ?range ?predicate ?object
WHERE {{
  GRAPH ?membershipGraph {{ ?membership <{path_predicate}> {iri(target)} }}
  GRAPH ?rangeLinkGraph {{ ?membership members:hasMembershipDateRange ?range }}
  GRAPH ?rangeGraph {{ ?range ?predicate ?object }}
}}
ORDER BY ?membershipGraph ?rangeLinkGraph ?rangeGraph ?membership ?range ?predicate ?object"""


def query_related_resource_facts(resources: list[str]) -> str | None:
    if not resources:
        return None
    values = " ".join(iri(resource) for resource in resources)
    return PREFIXES + f"""\
SELECT DISTINCT ?resource ?graph ?predicate ?object
WHERE {{
  VALUES ?resource {{ {values} }}
  GRAPH ?graph {{ ?resource ?predicate ?object }}
}}
ORDER BY ?resource ?graph ?predicate ?object"""


def query_committee_ranges(committees: list[str]) -> str | None:
    if not committees:
        return None
    values = " ".join(iri(committee) for committee in committees)
    return PREFIXES + f"""\
SELECT DISTINCT ?committee ?rangeLinkGraph ?range ?rangeGraph ?predicate ?object
WHERE {{
  VALUES ?committee {{ {values} }}
  GRAPH ?rangeLinkGraph {{ ?committee members:hasCommitteeDateRange ?range }}
  OPTIONAL {{ GRAPH ?rangeGraph {{ ?range ?predicate ?object }} }}
}}
ORDER BY ?committee ?rangeLinkGraph ?range ?rangeGraph ?predicate ?object"""


def range_index(
    range_rows: list[dict[str, dict[str, str]]],
    membership_graph_var: str,
    membership_var: str,
    range_var: str,
    predicate_var: str,
    object_var: str,
) -> dict[tuple[str, str, str], dict[str, list[dict[str, str]]]]:
    result: dict[tuple[str, str, str], dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in range_rows:
        membership_graph = value(row.get(membership_graph_var))
        membership = value(row.get(membership_var))
        range_iri = value(row.get(range_var))
        predicate = value(row.get(predicate_var))
        obj = binding_dict(row.get(object_var))
        if membership_graph and membership and range_iri and predicate and obj:
            key = (membership_graph, membership, range_iri)
            if obj not in result[key][predicate]:
                result[key][predicate].append(obj)
    return result


def candidate_records(
    path_name: str,
    path_predicate: str,
    target: str,
    membership_rows: list[dict[str, dict[str, str]]],
    reverse_rows: list[dict[str, dict[str, str]]],
    member_rows: list[dict[str, dict[str, str]]],
    range_rows: list[dict[str, dict[str, str]]],
    required_membership_type: str,
    required_term: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_path_membership: dict[tuple[str, str], list[dict[str, dict[str, str]]]] = defaultdict(list)
    path_keys: set[tuple[str, str]] = set()
    for row in membership_rows:
        path_graph = value(row.get("pathGraph"))
        membership = value(row.get("membership"))
        fact_graph = value(row.get("graph"))
        if not path_graph or not membership or not fact_graph:
            continue
        key = (path_graph, membership)
        rows_by_path_membership[key].append(row)
        if (
            path_graph == fact_graph
            and value(row.get("predicate")) == path_predicate
            and value(row.get("object")) == target
        ):
            path_keys.add(key)

    by_graph_membership: dict[
        tuple[str, str], dict[str, list[dict[str, str]]]
    ] = defaultdict(lambda: defaultdict(list))
    membership_graphs_by_candidate: dict[tuple[str, str], set[str]] = defaultdict(set)
    membership_facts_by_graph: dict[
        tuple[str, str], dict[str, dict[str, list[dict[str, str]]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for key, fact_rows in rows_by_path_membership.items():
        for row in fact_rows:
            fact_graph = value(row.get("graph"))
            predicate = value(row.get("predicate"))
            obj = binding_dict(row.get("object"))
            if not fact_graph or not predicate or not obj:
                continue
            membership_graphs_by_candidate[key].add(fact_graph)
            if obj not in by_graph_membership[key][predicate]:
                by_graph_membership[key][predicate].append(obj)
            if obj not in membership_facts_by_graph[key][fact_graph][predicate]:
                membership_facts_by_graph[key][fact_graph][predicate].append(obj)

    members_by_graph = graph_facts(member_rows, "graph", "member", "predicate", "object")
    members_by_subject: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    member_fact_graphs: dict[str, set[str]] = defaultdict(set)
    for (member_graph, member), properties in members_by_graph.items():
        member_fact_graphs[member].add(member_graph)
        for predicate, objects in properties.items():
            for obj in objects:
                if obj not in members_by_subject[member][predicate]:
                    members_by_subject[member][predicate].append(obj)
    ranges = range_index(
        range_rows,
        "membershipGraph",
        "membership",
        "range",
        "predicate",
        "object",
    )

    reverse_links: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in reverse_rows:
        membership_graph = value(row.get("membershipGraph"))
        membership = value(row.get("membership"))
        if membership_graph and membership:
            reverse_links[(membership_graph, membership)].append(
                {
                    "membership_graph": membership_graph,
                    "member_graph": value(row.get("memberGraph")) or "",
                    "member": value(row.get("member")) or "",
                }
            )

    candidates: list[dict[str, Any]] = []
    qualifying: list[dict[str, Any]] = []
    for (graph, membership), facts in sorted(by_graph_membership.items()):
        if (graph, membership) not in path_keys:
            continue
        membership_description_graphs = sorted(
            membership_graphs_by_candidate.get((graph, membership), set())
        )
        facts_by_graph = {
            owner_graph: dict(properties)
            for owner_graph, properties in membership_facts_by_graph[(graph, membership)].items()
        }
        linked_members = reverse_links.get((graph, membership), [])
        membership_types = facts.get(RDF_TYPE, [])
        membership_type_ok = any(
            obj.get("type") == "uri" and obj.get("value") == required_membership_type
            for obj in membership_types
        )
        membership_terms = facts.get(MEMBERS + "inHouseTerm", [])
        term_ok = (
            required_term is None
            or (
                len(membership_terms) == 1
                and membership_terms[0].get("type") == "uri"
                and membership_terms[0].get("value") == required_term
            )
        )
        member_info: list[dict[str, Any]] = []
        for link in linked_members:
            member = link["member"]
            member_graph = link["member_graph"]
            member_facts = members_by_subject.get(member, {})
            member_description_graphs = sorted(member_fact_graphs.get(member, set()))
            member_assertions_by_graph = {
                fact_graph: dict(properties)
                for (fact_graph, subject), properties in members_by_graph.items()
                if subject == member
            }
            codes = member_facts.get(AGENTS + "memberCode", [])
            types = member_facts.get(RDF_TYPE, [])
            names = member_facts.get(FOAF_NAME, []) or member_facts.get(RDFS_LABEL, [])
            expected_graphs = [
                MEMBER_GRAPH_PREFIX + urllib.parse.quote(code["value"], safe="-._~")
                for code in codes
                if is_xsd_string(code)
                and code.get("value")
            ]
            unique_code = len(codes) == 1 and is_xsd_string(codes[0])
            member_info.append(
                {
                    "member_iri": member,
                    "member_graph": member_graph,
                    "membership_graph": link["membership_graph"],
                    "member_description_graphs": member_description_graphs,
                    "unique_member_owner_graph": member_description_graphs == [member_graph],
                    "all_member_facts_by_graph": member_assertions_by_graph,
                    "member_code_values": codes,
                    "member_types": types,
                    "member_names": names,
                    "expected_owner_graphs_from_memberCode": sorted(set(expected_graphs)),
                    "unique_xsd_string_memberCode": unique_code,
                    "owner_graph_matches_memberCode": member_graph in expected_graphs,
                    "explicit_agents_Member_type": any(
                        x.get("type") == "uri" and x.get("value") == AGENTS + "Member"
                        for x in types
                    ),
                    "reverse_link": {
                        "predicate": MEMBERS + "hasMembersMembership",
                        "member": member,
                        "membership": membership,
                        "member_graph": member_graph,
                        "membership_graph": link["membership_graph"],
                    },
                }
            )

        ranges_for_membership: list[dict[str, Any]] = []
        date_range_links = facts.get(MEMBERS + "hasMembershipDateRange", [])
        non_uri_range_links = [
            obj for obj in date_range_links if obj.get("type") != "uri"
        ]
        range_iris = [
            obj.get("value")
            for obj in date_range_links
            if obj.get("type") == "uri" and obj.get("value")
        ]
        for range_iri in sorted(set(range_iris)):
            range_data = ranges.get((graph, membership, range_iri), {})
            status = interval_status(range_data)
            range_graphs = sorted(
                {
                    value(row.get("rangeGraph")) or ""
                    for row in range_rows
                    if value(row.get("membershipGraph")) == graph
                    and value(row.get("membership")) == membership
                    and value(row.get("range")) == range_iri
                }
            )
            range_link_graphs = sorted(
                {
                    value(row.get("rangeLinkGraph")) or ""
                    for row in range_rows
                    if value(row.get("membershipGraph")) == graph
                    and value(row.get("membership")) == membership
                    and value(row.get("range")) == range_iri
                }
            )
            owner_graph_matches_membership = (
                range_graphs == [graph] and range_link_graphs == [graph]
            )
            if not owner_graph_matches_membership:
                status["status"] = "uncertain"
                status["reasons"].append(
                    "DateRange is not described uniquely in the membership owner graph"
                )
            ranges_for_membership.append(
                {
                    "range_iri": range_iri,
                    "range_graphs": range_graphs,
                    "range_link_graphs": range_link_graphs,
                    "owner_graph_matches_membership": owner_graph_matches_membership,
                    "facts_by_predicate": dict(range_data),
                    **status,
                }
            )

        active_ranges = [x for x in ranges_for_membership if x["status"] == "active"]
        graph_member_links = [x for x in member_info if x["member_graph"] == graph]
        membership_owner_ok = membership_description_graphs == [graph]
        owner_ok_member = membership_owner_ok and len(linked_members) == 1 and any(
            x["owner_graph_matches_memberCode"]
            and x["unique_xsd_string_memberCode"]
            and x["explicit_agents_Member_type"]
            and x["unique_member_owner_graph"]
            and x["membership_graph"] == graph
            for x in graph_member_links
        )
        qualified = bool(
            membership_type_ok
            and term_ok
            and active_ranges
            and owner_ok_member
        )
        reasons: list[str] = []
        if not membership_type_ok:
            reasons.append(f"missing explicit required type {required_membership_type}")
        if required_term is not None and not term_ok:
            reasons.append("inHouseTerm does not contain the constituency's exact HouseTerm IRI")
        if not date_range_links:
            reasons.append("no members:hasMembershipDateRange resource is linked")
        elif non_uri_range_links:
            reasons.append("non-URI DateRange link cannot be deterministically followed across separate query responses")
        if date_range_links and not ranges_for_membership:
            reasons.append("no URI-valued DateRange facts were available for a positive witness")
        elif not active_ranges:
            reasons.append("no explicitly typed, parseable membership range contains asOf")
        if not linked_members:
            reasons.append("no reverse Member hasMembersMembership link was found in named graphs")
        if not membership_owner_ok:
            reasons.append("membership subject is not uniquely described in the path assertion's Member owner graph")
        if not owner_ok_member:
            reasons.append("no same-owner reverse-linked explicitly typed Member matches graph/memberCode")
        record = {
            "path": path_name,
            "target_resource": target,
            "membership_iri": membership,
            "membership_graph": graph,
            "membership_description_graphs": membership_description_graphs,
            "unique_membership_owner_graph": membership_owner_ok,
            "membership_types": membership_types,
            "required_membership_type": required_membership_type,
            "explicit_required_membership_type": membership_type_ok,
            "membership_term_values": membership_terms,
            "required_term_iri": required_term,
            "exact_required_term_match": term_ok,
            "target_relation": {
                "predicate": path_predicate,
                "object": target,
            },
            "membership_date_range_links": date_range_links,
            "unfollowed_non_uri_date_range_links": non_uri_range_links,
            "ranges": ranges_for_membership,
            "reverse_linked_members": member_info,
            "qualifies_for_independent_expected_set": qualified,
            "qualification_reasons": reasons,
            "all_membership_facts_by_predicate": dict(facts),
            "all_membership_facts_by_graph": facts_by_graph,
        }
        candidates.append(record)
        if qualified:
            for member in graph_member_links:
                qualifying.append(
                    {
                        "member_iri": member["member_iri"],
                        "member_code_values": member["member_code_values"],
                        "member_graph": member["member_graph"],
                        "membership_graph": graph,
                        "membership_description_graphs": membership_description_graphs,
                        "membership_iri": membership,
                        "target_resource": target,
                        "membership_type": required_membership_type,
                        "term_constraint": required_term,
                        "active_date_range_witnesses": [
                            {
                                "range_iri": date_range["range_iri"],
                                "start_values": date_range["start_values"],
                                "end_values": date_range["end_values"],
                                "range_types": date_range["range_types"],
                                "range_graphs": date_range["range_graphs"],
                                "range_link_graphs": date_range["range_link_graphs"],
                                "facts_by_predicate": date_range["facts_by_predicate"],
                            }
                            for date_range in active_ranges
                        ],
                        "membership_assertions": dict(facts),
                        "membership_assertions_by_graph": facts_by_graph,
                        "member_types": member["member_types"],
                        "member_names": member["member_names"],
                        "member_assertions_by_graph": member["all_member_facts_by_graph"],
                        "member_reverse_assertion": member["reverse_link"],
                    }
                )

    candidates.sort(key=lambda item: (item["membership_graph"], item["membership_iri"]))
    qualifying.sort(key=lambda item: (item["member_iri"], item["membership_graph"], item["membership_iri"]))
    return candidates, qualifying


def target_summary(
    resource: str,
    expected_owner: str,
    required_type: str,
    target_rows: list[dict[str, dict[str, str]]],
) -> dict[str, Any]:
    facts = graph_facts(target_rows, "graph", "resource", "predicate", "object")
    owner_graphs = sorted(graph for graph, subject in facts if subject == resource)
    predicate_facts: dict[str, list[dict[str, str]]] = defaultdict(list)
    for (graph, subject), props in facts.items():
        if subject == resource:
            for predicate, objects in props.items():
                predicate_facts[predicate].extend(
                    {"graph": graph, **obj}
                    for obj in objects
                )
    type_values = predicate_facts.get(RDF_TYPE, [])
    return {
        "resource": resource,
        "expected_owner_graph": expected_owner,
        "observed_subject_graphs": owner_graphs,
        "observed_owner_graphs": [g for g in owner_graphs if g == expected_owner],
        "unique_subject_graph": len(owner_graphs) == 1,
        "unique_expected_owner": owner_graphs == [expected_owner],
        "types": type_values,
        "required_explicit_type": required_type,
        "explicit_required_type_present": any(
            x.get("type") == "uri" and x.get("value") == required_type
            for x in type_values
        ),
        "facts_by_predicate": dict(predicate_facts),
    }


def committee_incarnation_summary(
    discovery_rows: list[dict[str, dict[str, str]]],
    committee_rows: list[dict[str, dict[str, str]]],
    range_rows: list[dict[str, dict[str, str]]],
    terms: dict[str, Any],
) -> dict[str, Any]:
    discovery_facts: dict[str, list[dict[str, str]]] = defaultdict(list)
    candidate_iris = sorted(
        {
            value(row.get("committee"))
            for row in discovery_rows
            if value(row.get("committee"))
        }
    )
    for row in discovery_rows:
        committee = value(row.get("committee"))
        predicate = value(row.get("predicate"))
        obj = binding_dict(row.get("object"))
        if committee and predicate and obj and obj not in discovery_facts[committee]:
            discovery_facts[committee].append(obj)

    by_graph = graph_facts(committee_rows, "graph", "resource", "predicate", "object")
    facts_by_committee: dict[str, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    owner_graphs_by_committee: dict[str, set[str]] = defaultdict(set)
    facts_by_committee_graph: dict[
        str, dict[str, dict[str, list[dict[str, str]]]]
    ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for (graph, committee), predicates in by_graph.items():
        owner_graphs_by_committee[committee].add(graph)
        for predicate, objects in predicates.items():
            for obj in objects:
                if obj not in facts_by_committee[committee][predicate]:
                    facts_by_committee[committee][predicate].append(obj)
                if obj not in facts_by_committee_graph[committee][graph][predicate]:
                    facts_by_committee_graph[committee][graph][predicate].append(obj)

    range_rows_by_committee: dict[str, list[dict[str, dict[str, str]]]] = defaultdict(list)
    for row in range_rows:
        committee = value(row.get("committee"))
        if committee:
            range_rows_by_committee[committee].append(row)

    term_records = {item["term_iri"]: item for item in terms["term_resources"]}
    unique_current_term = (
        terms["current_dail_term_iris"][0]
        if terms["unique_current_dail_term"]
        else None
    )
    records: list[dict[str, Any]] = []

    for committee in candidate_iris:
        facts = facts_by_committee.get(committee, {})
        owner_graphs = sorted(owner_graphs_by_committee.get(committee, set()))
        facts_by_graph_for_committee = {
            graph: dict(predicates)
            for graph, predicates in facts_by_committee_graph.get(committee, {}).items()
        }
        types = facts.get(RDF_TYPE, [])
        owner_type_facts = facts_by_graph_for_committee.get(COMMITTEES_GRAPH, {}).get(RDF_TYPE, [])
        explicit_committee_type = any(
            x.get("type") == "uri" and x.get("value") == MEMBERS + "Committee"
            for x in types
        )
        explicit_owner_committee_type = any(
            x.get("type") == "uri" and x.get("value") == MEMBERS + "Committee"
            for x in owner_type_facts
        )
        house_term_values = facts.get(MEMBERS + "committeeInHouseTerm", [])
        house_term_iris = sorted(
            {
                x.get("value")
                for x in house_term_values
                if x.get("type") == "uri" and x.get("value")
            }
        )
        term_record = term_records.get(house_term_iris[0]) if len(house_term_iris) == 1 else None
        term_link_unique = len(house_term_values) == 1 and len(house_term_iris) == 1
        house_term_is_auditable_dail_term = bool(
            term_record
            and term_record["is_typed_dail_term_from_complete_typed_inventory"]
            and term_record["all_required_term_facts_auditable"]
        )
        house_term_matches_current = bool(
            unique_current_term
            and term_link_unique
            and house_term_iris[0] == unique_current_term
        )

        range_links = facts.get(MEMBERS + "hasCommitteeDateRange", [])
        uri_range_links = sorted(
            {
                x.get("value")
                for x in range_links
                if x.get("type") == "uri" and x.get("value")
            }
        )
        date_ranges: list[dict[str, Any]] = []
        candidate_range_rows = range_rows_by_committee.get(committee, [])
        for range_iri in uri_range_links:
            matching_rows = [
                row for row in candidate_range_rows
                if row.get("range", {}).get("type") == "uri"
                and value(row.get("range")) == range_iri
            ]
            range_link_graphs = sorted(
                {
                    value(row.get("rangeLinkGraph")) or ""
                    for row in matching_rows
                    if value(row.get("rangeLinkGraph"))
                }
            )
            range_graphs = sorted(
                {
                    value(row.get("rangeGraph")) or ""
                    for row in matching_rows
                    if value(row.get("rangeGraph"))
                }
            )
            range_facts: dict[str, list[dict[str, str]]] = defaultdict(list)
            for row in matching_rows:
                if value(row.get("rangeGraph")) != COMMITTEES_GRAPH:
                    continue
                predicate = value(row.get("predicate"))
                obj = binding_dict(row.get("object"))
                if predicate and obj and obj not in range_facts[predicate]:
                    range_facts[predicate].append(obj)
            status = interval_status(range_facts)
            range_owner_ok = (
                range_link_graphs == [COMMITTEES_GRAPH]
                and range_graphs == [COMMITTEES_GRAPH]
            )
            if not range_owner_ok:
                status["status"] = "uncertain"
                status["reasons"].append(
                    "Committee DateRange link and description are not both uniquely owned by the committees graph"
                )
            date_ranges.append(
                {
                    "range_iri": range_iri,
                    "range_link_graphs": range_link_graphs,
                    "range_graphs": range_graphs,
                    "owner_graph_matches_committee": range_owner_ok,
                    "facts_by_predicate": dict(range_facts),
                    **status,
                }
            )

        non_uri_range_links = [x for x in range_links if x.get("type") != "uri"]
        range_link_unique = len(range_links) == 1 and len(uri_range_links) == 1
        active_ranges = [x for x in date_ranges if x["status"] == "active"]
        owner_ok = owner_graphs == [COMMITTEES_GRAPH]
        committee_identity_auditable = bool(
            owner_ok
            and explicit_committee_type
            and explicit_owner_committee_type
            and term_link_unique
            and house_term_is_auditable_dail_term
            and range_link_unique
            and not non_uri_range_links
            and len(date_ranges) == 1
            and date_ranges[0]["status"] in {"active", "inactive"}
            and date_ranges[0]["owner_graph_matches_committee"]
        )
        is_current = bool(
            committee_identity_auditable
            and house_term_matches_current
            and len(active_ranges) == 1
        )
        iri_slug_match = "public_accounts" in committee.lower() or "public-accounts" in committee.lower()
        label_match_facts = [
            {"predicate": predicate, **obj}
            for predicate, objects in facts.items()
            if predicate in {RDFS_LABEL, SKOS_PREF_LABEL, FOAF_NAME}
            for obj in objects
            if "public accounts" in obj.get("value", "").lower()
        ]
        records.append(
            {
                "committee_iri": committee,
                "matching_evidence": {
                    "iri_contains_public_accounts_slug": iri_slug_match,
                    "label_matches_public_accounts": label_match_facts,
                    "discovery_facts": discovery_facts.get(committee, []),
                },
                "owner_graphs": owner_graphs,
                "unique_committees_graph_owner": owner_ok,
                "types": types,
                "explicit_members_Committee_type_present": explicit_committee_type,
                "explicit_members_Committee_type_in_owner_graph": explicit_owner_committee_type,
                "committee_house_term_values": house_term_values,
                "committee_house_term_iris": house_term_iris,
                "unique_committee_house_term_link": term_link_unique,
                "house_term_audited_as_dail_term": house_term_is_auditable_dail_term,
                "house_term_matches_unique_current_dail_term": house_term_matches_current,
                "house_term_audit": term_record,
                "committee_date_range_links": range_links,
                "unfollowed_non_uri_date_range_links": non_uri_range_links,
                "date_ranges": date_ranges,
                "unique_active_committee_owner_range": len(active_ranges) == 1 and range_link_unique,
                "all_required_committee_facts_auditable": committee_identity_auditable,
                "is_current_matching_committee_incarnation": is_current,
                "facts_by_predicate": dict(facts),
                "facts_by_graph": facts_by_graph_for_committee,
            }
        )

    current_iris = sorted(
        record["committee_iri"]
        for record in records
        if record["is_current_matching_committee_incarnation"]
    )
    all_candidates_auditable = bool(records) and all(
        record["all_required_committee_facts_auditable"] for record in records
    )
    return {
        "candidate_selection": {
            "owner_graph": COMMITTEES_GRAPH,
            "required_type": MEMBERS + "Committee",
            "match_rule": "typed Committee IRI contains public_accounts/public-accounts slug, or rdfs:label/skos:prefLabel/foaf:name contains the phrase Public Accounts (case-insensitive)",
            "candidate_count": len(candidate_iris),
        },
        "matching_committee_candidates": records,
        "all_matching_committee_candidates_auditable": all_candidates_auditable,
        "current_matching_committee_iris": current_iris,
        "unique_current_matching_committee": len(current_iris) == 1 and all_candidates_auditable,
        "unique_current_matching_committee_is_requested_resource": (
            len(current_iris) == 1 and current_iris[0] == COMMITTEE and all_candidates_auditable
        ),
        "requested_resource": COMMITTEE,
    }


def term_summary(
    term_rows: list[dict[str, dict[str, str]]],
    related_rows: list[dict[str, dict[str, str]]],
    target_facts: list[dict[str, dict[str, str]]],
    committee_rows: list[dict[str, dict[str, str]]],
) -> dict[str, Any]:
    related_facts = graph_facts(related_rows, "graph", "resource", "predicate", "object")
    target_props = subject_facts(target_facts, "resource", "predicate", "object")
    committee_props = subject_facts(committee_rows, "resource", "predicate", "object")
    target_term_links: dict[str, list[str]] = {
        KILDARE_NORTH: [],
        COMMITTEE: [],
    }
    target_term_bindings: dict[str, list[dict[str, str]]] = {
        KILDARE_NORTH: [],
        COMMITTEE: [],
    }
    for target, pred in (
        (KILDARE_NORTH, MEMBERS + "constituencyInHouseTerm"),
        (COMMITTEE, MEMBERS + "committeeInHouseTerm"),
    ):
        target_term_bindings[target] = target_props.get(target, {}).get(pred, [])
        target_term_links[target] = sorted(
            obj["value"]
            for obj in target_term_bindings[target]
            if obj.get("type") == "uri"
        )

    typed_term_subjects = {
        value(row.get("term")) for row in term_rows if value(row.get("term"))
    }
    term_subjects = set(typed_term_subjects)
    term_subjects.update(target_term_links[KILDARE_NORTH])
    term_subjects.update(target_term_links[COMMITTEE])
    term_subjects.update(
        obj["value"]
        for props in committee_props.values()
        for obj in props.get(MEMBERS + "committeeInHouseTerm", [])
        if obj.get("type") == "uri"
    )

    typed_graphs_by_term: dict[str, set[str]] = defaultdict(set)
    for row in term_rows:
        term = value(row.get("term"))
        type_graph = value(row.get("typeGraph"))
        if term and type_graph:
            typed_graphs_by_term[term].add(type_graph)

    normalized_term_rows: list[dict[str, dict[str, str]]] = []
    for row in term_rows:
        normalized_term_rows.append(
            {
                "graph": row["graph"],
                "term": row["term"],
                "predicate": row["predicate"],
                "object": row["object"],
            }
        )
    for row in related_rows:
        if value(row.get("resource")) in term_subjects:
            normalized_term_rows.append(
                {
                    "graph": row["graph"],
                    "term": row["resource"],
                    "predicate": row["predicate"],
                    "object": row["object"],
                }
            )
    term_facts = graph_facts(
        normalized_term_rows, "graph", "term", "predicate", "object"
    )
    candidates: list[dict[str, Any]] = []
    all_subjects = sorted(x for x in term_subjects if x)
    for term in all_subjects:
        graph_props: dict[str, list[dict[str, str]]] = defaultdict(list)
        for (graph, subject), props in term_facts.items():
            if subject == term:
                for pred, objects in props.items():
                    graph_props[pred].extend({"graph": graph, **obj} for obj in objects)
        owner_graphs = sorted(graph for graph, subject in term_facts if subject == term)
        type_graphs = sorted(typed_graphs_by_term.get(term, set()))
        candidate = {
            "term_iri": term,
            "is_typed_dail_term_from_complete_typed_inventory": term in typed_term_subjects,
            "typed_assertion_graphs": type_graphs,
            "graphs": owner_graphs,
            "unique_houses_graph_owner": owner_graphs == [HOUSES_GRAPH],
            "types": graph_props.get(RDF_TYPE, []),
            "termNo_values": graph_props.get(AGENTS + "termNo", []),
            "houseCode_values": graph_props.get(AGENTS + "houseCode", []),
            "labels": graph_props.get(SKOS_PREF_LABEL, []) or graph_props.get(RDFS_LABEL, []),
            "facts_by_predicate": dict(graph_props),
            "is_current_dail_term_candidate": False,
            "current_status": "not established until all typed-term temporal facts are audited",
        }
        term_types = {x.get("value") for x in candidate["types"]}
        explicit_dail_type = AGENTS + "DailTerm" in term_types
        term_owner_ok = owner_graphs == [HOUSES_GRAPH] and type_graphs == [HOUSES_GRAPH]
        number_values = [
            x for x in candidate["termNo_values"]
            if x.get("type") == "literal" and x.get("datatype") == XSD + "integer"
        ]
        number_identity = {
            (x.get("type"), x.get("value"), x.get("datatype"), x.get("xml:lang"))
            for x in number_values
        }
        number_ok = len(number_identity) == 1
        code_values = [x for x in candidate["houseCode_values"] if is_xsd_string(x)]
        code_identity = {
            (x.get("type"), x.get("value"), x.get("datatype"), x.get("xml:lang"))
            for x in code_values
        }
        code_ok = len(code_identity) == 1 and next(iter(code_identity))[1] == "dail"
        temporal_values = candidate["facts_by_predicate"].get(DCT_TEMPORAL, [])
        temporal_identity = {
            (x.get("type"), x.get("value"), x.get("datatype"), x.get("xml:lang"))
            for x in temporal_values
        }
        temporal_links = [x for x in temporal_values if x.get("type") == "uri"]
        temporal_intervals: list[dict[str, Any]] = []
        period_link_ok = len(temporal_identity) == 1 and len(temporal_links) == 1
        for period in sorted({x.get("value") for x in temporal_links if x.get("value")}):
            period_graphs = sorted(
                graph for graph, subject in related_facts if subject == period
            )
            props = related_facts.get((HOUSES_GRAPH, period), {})
            starts = props.get(DCAT_START, [])
            ends = props.get(DCAT_END, [])
            period_types = props.get(RDF_TYPE, [])
            start_date = None
            end_date = None
            if len(starts) == 1:
                start_date, _ = date_value(starts[0])
            if len(ends) == 1:
                end_date, _ = date_value(ends[0])
            period_type_ok = any(
                x.get("type") == "uri"
                and x.get("value") == "http://purl.org/dc/terms/PeriodOfTime"
                for x in period_types
            )
            date_shape_ok = (
                len(starts) == 1
                and starts[0].get("datatype") == XSD + "dateTime"
                and len(ends) <= 1
                and (not ends or ends[0].get("datatype") == XSD + "dateTime")
                and start_date is not None
                and (not ends or end_date is not None)
                and (end_date is None or start_date <= end_date)
            )
            period_owner_ok = period_graphs == [HOUSES_GRAPH]
            if not period_owner_ok or not period_type_ok or not date_shape_ok:
                temporal_status = "uncertain"
            elif start_date > AS_OF or (end_date is not None and end_date < AS_OF):
                temporal_status = "inactive"
            elif end_date is None:
                temporal_status = "current"
            else:
                temporal_status = "active_with_explicit_end_date"
            temporal_intervals.append(
                {
                    "period_iri": period,
                    "period_graphs": period_graphs,
                    "unique_houses_graph_owner": period_owner_ok,
                    "period_facts_by_predicate": dict(props),
                    "period_types": period_types,
                    "explicit_dct_PeriodOfTime_type": period_type_ok,
                    "start_values": starts,
                    "end_values": ends,
                    "parsed_start_calendar_date": start_date.isoformat() if start_date else None,
                    "parsed_end_calendar_date": end_date.isoformat() if end_date else None,
                    "status_at_asOf": temporal_status,
                    "current_at_asOf_under_open_end_rule": temporal_status == "current",
                }
            )
        temporal_audit_ok = (
            period_link_ok
            and len(temporal_intervals) == 1
            and temporal_intervals[0]["status_at_asOf"] in {"current", "inactive"}
        )
        candidate_auditable = (
            term in typed_term_subjects
            and explicit_dail_type
            and term_owner_ok
            and number_ok
            and code_ok
            and temporal_audit_ok
        )
        current = bool(
            candidate_auditable
            and temporal_intervals[0]["status_at_asOf"] == "current"
        )
        candidate["temporal_intervals"] = temporal_intervals
        candidate["explicit_dail_term_type_present"] = explicit_dail_type
        candidate["unique_xsd_integer_termNo"] = number_ok
        candidate["unique_dail_xsd_string_houseCode"] = code_ok
        candidate["unique_temporal_link"] = period_link_ok
        candidate["temporal_audit_complete"] = temporal_audit_ok
        candidate["all_required_term_facts_auditable"] = candidate_auditable
        candidate["is_current_dail_term_candidate"] = current
        candidate["current_status"] = (
            "current under unique explicit DailTerm identity and active open-ended PeriodOfTime"
            if current
            else "not established as the unique current Dáil term"
        )
        candidates.append(candidate)

    typed_candidates = [
        x for x in candidates if x["is_typed_dail_term_from_complete_typed_inventory"]
    ]
    current_candidates = [x["term_iri"] for x in typed_candidates if x["is_current_dail_term_candidate"]]
    all_typed_terms_auditable = bool(typed_candidates) and all(
        x["all_required_term_facts_auditable"] for x in typed_candidates
    )
    return {
        "selector": {
            "house_code": "dail",
            "asOf": AS_OF.isoformat(),
            "constraints": [
                "all explicitly typed agents:DailTerm resources are inventoried, without termNo restriction",
                "one unique agents:termNo xsd:integer and agents:houseCode dail xsd:string per term",
                "one linked dct:PeriodOfTime with unique houses-graph ownership and dateTime endpoints",
                "current interval contains asOf and has no dcat:endDate, per the HouseTerm ontology convention",
            ],
        },
        "typed_dail_term_count": len(typed_candidates),
        "all_typed_dail_terms_auditable": all_typed_terms_auditable,
        "typed_dail_terms_with_uncertain_facts": [
            x["term_iri"] for x in typed_candidates if not x["all_required_term_facts_auditable"]
        ],
        "term_resources": candidates,
        "current_dail_term_iris": current_candidates,
        "unique_current_dail_term": len(current_candidates) == 1 and all_typed_terms_auditable,
        "target_term_links": target_term_links,
        "target_term_link_bindings": target_term_bindings,
        "target_kildare_term_matches_unique_current_term": (
            len(target_term_bindings[KILDARE_NORTH]) == 1
            and target_term_bindings[KILDARE_NORTH][0].get("type") == "uri"
            and len(current_candidates) == 1
            and target_term_links[KILDARE_NORTH][0] == current_candidates[0]
        ),
        "target_committee_term_matches_unique_current_term": (
            len(target_term_bindings[COMMITTEE]) == 1
            and target_term_bindings[COMMITTEE][0].get("type") == "uri"
            and len(current_candidates) == 1
            and target_term_links[COMMITTEE][0] == current_candidates[0]
        ),
        "committee_candidate_term_links": {
            subject: sorted(
                obj["value"]
                for obj in props.get(MEMBERS + "committeeInHouseTerm", [])
                if obj.get("type") == "uri"
            )
            for subject, props in sorted(committee_props.items())
        },
        "cross_path_term_equality_applied": False,
    }


def env_provenance() -> dict[str, Any]:
    # Sanitized, independently checked `docker inspect` values. The full inspect
    # output is intentionally not retained (it included unrelated credentials).
    return {
        "fuseki_container_id": "249847a5776858b629bfca2406a279fcfd0ea37f1838dd593b95744a00b14076",
        "container_name": "/oireachtasontology-fuseki-1",
        "container_started_at": "2026-11-01T15:07:21.601411161Z",
        "image": "stain/jena-fuseki:5.1.0",
        "image_digest": "sha256:b1d0c96f19adddef417520184471ac816cf36c6e72936a88ea02b29f4305929a",
        "compose_project": "oireachtasontology",
        "compose_service": "fuseki",
        "dataset_env_selector": "houses",
        "volume_name": "oireachtasontology_fuseki-data",
        "volume_mount_destination": "/fuseki",
        "volume_host_source": "/var/lib/docker/volumes/oireachtasontology_fuseki-data/_data",
        "dataset_path_reported_by_requester": "/fuseki/databases/houses",
        "mount_and_image_verified_by_read_only_docker_inspect": True,
        "reported_houses_config_path": "docs/reports/query-service/composition-live-kr-20261112/fuseki-houses.ttl (main repository)",
        "config_file_read_by_oracle": False,
    }


def build_capture(mode: str) -> dict[str, Any]:
    client = ReadOnlyFuseki()
    started_at = utc_now()
    sections: dict[str, dict[str, Any]] = {}
    queries: list[tuple[str, str]] = [
        (
            "owner_and_provenance_graph_presence",
            PREFIXES
            + f"""\
SELECT ?graph (COUNT(?subject) AS ?triples)
WHERE {{
  VALUES ?graph {{
    {iri(HOUSES_GRAPH)}
    {iri(CONSTITUENCIES_GRAPH)}
    {iri(COMMITTEES_GRAPH)}
    {iri(PROVENANCE_GRAPH)}
  }}
  OPTIONAL {{ GRAPH ?graph {{ ?subject ?predicate ?object }} }}
}}
GROUP BY ?graph
ORDER BY ?graph""",
        ),
        ("exact_target_resource_quads", query_target_facts()),
        ("all_typed_DailTerm_facts", query_all_dail_term_facts()),
        ("matching_Public_Accounts_committee_candidate_discovery", query_committee_candidates()),
        (
            "K_candidate_membership_facts",
            query_path_facts(MEMBERS + "isCommitteeMembershipOf", COMMITTEE),
        ),
        (
            "K_reverse_member_links",
            query_reverse_links(MEMBERS + "isCommitteeMembershipOf", COMMITTEE),
        ),
        (
            "K_reverse_linked_member_facts",
            query_member_facts(MEMBERS + "isCommitteeMembershipOf", COMMITTEE),
        ),
        (
            "K_membership_date_range_quads",
            query_membership_ranges(MEMBERS + "isCommitteeMembershipOf", COMMITTEE),
        ),
        (
            "R_candidate_membership_facts",
            query_path_facts(MEMBERS + "isRepresentativeFrom", KILDARE_NORTH),
        ),
        (
            "R_reverse_member_links",
            query_reverse_links(MEMBERS + "isRepresentativeFrom", KILDARE_NORTH),
        ),
        (
            "R_reverse_linked_member_facts",
            query_member_facts(MEMBERS + "isRepresentativeFrom", KILDARE_NORTH),
        ),
        (
            "R_membership_date_range_quads",
            query_membership_ranges(MEMBERS + "isRepresentativeFrom", KILDARE_NORTH),
        ),
    ]
    for label, query in queries:
        sections[label] = client.select(label, query)

    target_rows = rows(sections.get("exact_target_resource_quads"))
    term_rows = rows(sections.get("all_typed_DailTerm_facts"))
    committee_discovery_rows = rows(
        sections.get("matching_Public_Accounts_committee_candidate_discovery")
    )
    committee_iris = sorted(
        {
            value(row.get("committee"))
            for row in committee_discovery_rows
            if value(row.get("committee"))
        }
    )
    committee_facts_query = query_related_resource_facts(committee_iris)
    if committee_facts_query:
        sections["matching_Public_Accounts_committee_full_facts"] = client.select(
            "matching_Public_Accounts_committee_full_facts", committee_facts_query
        )
    else:
        sections["matching_Public_Accounts_committee_full_facts"] = {
            "label": "matching_Public_Accounts_committee_full_facts",
            "query_without_page_clause": None,
            "page_size": PAGE_SIZE,
            "complete": True,
            "completion_reason": "no matching typed Public Accounts Committee candidates were discovered",
            "row_count": 0,
            "pages": [],
        }
    committee_rows = rows(sections.get("matching_Public_Accounts_committee_full_facts"))
    committee_range_query = query_committee_ranges(committee_iris)
    if committee_range_query:
        sections["matching_Public_Accounts_committee_operational_range_quads"] = client.select(
            "matching_Public_Accounts_committee_operational_range_quads",
            committee_range_query,
        )
    else:
        sections["matching_Public_Accounts_committee_operational_range_quads"] = {
            "label": "matching_Public_Accounts_committee_operational_range_quads",
            "query_without_page_clause": None,
            "page_size": PAGE_SIZE,
            "complete": True,
            "completion_reason": "no matching typed Public Accounts Committee candidates were discovered",
            "row_count": 0,
            "pages": [],
        }

    related_resources = related_resource_iris([*target_rows, *committee_rows], term_rows)
    related_query = query_related_resource_facts(related_resources)
    if related_query:
        sections["linked_house_term_and_period_facts"] = client.select(
            "linked_house_term_and_period_facts", related_query
        )
    else:
        sections["linked_house_term_and_period_facts"] = {
            "label": "linked_house_term_and_period_facts",
            "query_without_page_clause": None,
            "page_size": PAGE_SIZE,
            "complete": True,
            "completion_reason": "no URI-valued linked HouseTerm/Committee range resources were present to follow",
            "row_count": 0,
            "pages": [],
        }

    linked_rows = rows(sections.get("linked_house_term_and_period_facts"))
    term_periods = related_resource_iris([], linked_rows)
    temporal_query = query_related_resource_facts(term_periods)
    if temporal_query:
        sections["linked_house_term_temporal_range_facts"] = client.select(
            "linked_house_term_temporal_range_facts", temporal_query
        )
    else:
        sections["linked_house_term_temporal_range_facts"] = {
            "label": "linked_house_term_temporal_range_facts",
            "query_without_page_clause": None,
            "page_size": PAGE_SIZE,
            "complete": True,
            "completion_reason": "no URI-valued temporal range resources were present to follow",
            "row_count": 0,
            "pages": [],
        }

    k_membership_rows = rows(sections.get("K_candidate_membership_facts"))
    k_reverse_rows = rows(sections.get("K_reverse_member_links"))
    k_member_rows = rows(sections.get("K_reverse_linked_member_facts"))
    k_range_rows = rows(sections.get("K_membership_date_range_quads"))
    r_membership_rows = rows(sections.get("R_candidate_membership_facts"))
    r_reverse_rows = rows(sections.get("R_reverse_member_links"))
    r_member_rows = rows(sections.get("R_reverse_linked_member_facts"))
    r_range_rows = rows(sections.get("R_membership_date_range_quads"))
    linked_rows = rows(sections.get("linked_house_term_and_period_facts"))
    temporal_rows = rows(sections.get("linked_house_term_temporal_range_facts"))

    terms = term_summary(
        term_rows,
        [*linked_rows, *temporal_rows],
        target_rows,
        committee_rows,
    )
    constituency_term = (
        terms["target_term_links"][KILDARE_NORTH][0]
        if len(terms["target_term_links"][KILDARE_NORTH]) == 1
        else None
    )
    committees = committee_incarnation_summary(
        committee_discovery_rows,
        committee_rows,
        rows(sections.get("matching_Public_Accounts_committee_operational_range_quads")),
        terms,
    )

    k_candidates, k_witnesses = candidate_records(
        "K",
        MEMBERS + "isCommitteeMembershipOf",
        COMMITTEE,
        k_membership_rows,
        k_reverse_rows,
        k_member_rows,
        k_range_rows,
        MEMBERS + "CommitteeMembership",
        None,
    )
    r_candidates, r_witnesses = candidate_records(
        "R",
        MEMBERS + "isRepresentativeFrom",
        KILDARE_NORTH,
        r_membership_rows,
        r_reverse_rows,
        r_member_rows,
        r_range_rows,
        MEMBERS + "DailMembership",
        constituency_term,
    )

    k_members = sorted({w["member_iri"] for w in k_witnesses})
    r_members = sorted({w["member_iri"] for w in r_witnesses})
    intersection = sorted(set(k_members) & set(r_members))
    witness_sets = []
    for member in intersection:
        witness_sets.append(
            {
                "member_iri": member,
                "K_witnesses": [x for x in k_witnesses if x["member_iri"] == member],
                "R_witnesses": [x for x in r_witnesses if x["member_iri"] == member],
                "join_key": "exact Member IRI",
                "cross_path_term_equality_applied": False,
                "party_condition_applied": False,
            }
        )

    resource_facts = target_summary(
        KILDARE_NORTH,
        CONSTITUENCIES_GRAPH,
        MEMBERS + "DailConstituency",
        target_rows,
    )
    requested_committee_facts = target_summary(
        COMMITTEE,
        COMMITTEES_GRAPH,
        MEMBERS + "Committee",
        target_rows,
    )
    graph_presence_rows = rows(sections.get("owner_and_provenance_graph_presence"))
    graph_presence = []
    for row in graph_presence_rows:
        graph_presence.append(
            {
                "graph": binding_dict(row.get("graph")),
                "triple_count": binding_dict(row.get("triples")),
            }
        )

    all_sections_complete = all(section.get("complete", False) for section in sections.values())
    target_evidence_complete = bool(
        sections.get("exact_target_resource_quads", {}).get("complete")
        and sections.get("all_typed_DailTerm_facts", {}).get("complete")
        and sections.get("matching_Public_Accounts_committee_candidate_discovery", {}).get("complete")
        and sections.get("matching_Public_Accounts_committee_full_facts", {}).get("complete")
        and sections.get("matching_Public_Accounts_committee_operational_range_quads", {}).get("complete")
        and sections.get("K_candidate_membership_facts", {}).get("complete")
        and sections.get("K_reverse_member_links", {}).get("complete")
        and sections.get("K_reverse_linked_member_facts", {}).get("complete")
        and sections.get("K_membership_date_range_quads", {}).get("complete")
        and sections.get("R_candidate_membership_facts", {}).get("complete")
        and sections.get("R_reverse_member_links", {}).get("complete")
        and sections.get("R_reverse_linked_member_facts", {}).get("complete")
        and sections.get("R_membership_date_range_quads", {}).get("complete")
        and sections.get("linked_house_term_and_period_facts", {}).get("complete")
        and sections.get("linked_house_term_temporal_range_facts", {}).get("complete")
    )
    evidence_gate = bool(
        all_sections_complete
        and target_evidence_complete
        and resource_facts["unique_expected_owner"]
        and resource_facts["explicit_required_type_present"]
        and requested_committee_facts["unique_expected_owner"]
        and requested_committee_facts["explicit_required_type_present"]
        and terms["unique_current_dail_term"]
        and terms["all_typed_dail_terms_auditable"]
        and terms["target_kildare_term_matches_unique_current_term"]
        and terms["target_committee_term_matches_unique_current_term"]
        and committees["unique_current_matching_committee"]
        and committees["unique_current_matching_committee_is_requested_resource"]
        and bool(k_witnesses)
        and bool(r_witnesses)
        and bool(intersection)
    )
    output_path = (
        ORACLE_DIR / "oracle.json"
        if mode == "baseline"
        else ORACLE_DIR / "stability" / f"oracle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    return {
        "schema": "nlq-live-kr-independent-rdf-oracle/v2",
        "capture_identity": "corrected K=Committee/R=representation with all-Dail-term and current Public Accounts incarnation audit",
        "capture_mode": mode,
        "capture_started_at": started_at,
        "capture_completed_at": utc_now(),
        "repository": {
            "branch": "feat/nlq-bounded-composition-kernel",
            "head": "e98296ef2d89a07810c3b0f3f801c99f76636ae7",
        },
        "oracle_tool": {
            "path": "tools/nlq_live_kr_oracle.py",
            "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "endpoint": ENDPOINT,
        "read_only_method": "HTTP POST application/x-www-form-urlencoded containing SELECT only; no update/query mutation",
        "parameters": {
            "committee_resource": COMMITTEE,
            "constituency_resource": KILDARE_NORTH,
            "asOf": AS_OF.isoformat(),
            "cross_path_term_equality": False,
            "party_condition": False,
        },
        "independent_oracle_method": {
            "candidate_discovery": "all named-graph subjects with the exact asserted K/R path predicate/object; full outgoing candidate membership quads are independently audited across all named graphs, without rdf:type, term, date, reverse-link, or owner filters",
            "K_path": "members:isCommitteeMembershipOf the exact dynamically verified current Committee of Public Accounts; qualify explicit CommitteeMembership, reverse-linked same-owner Member, and explicit active membership DateRange; additionally require the Committee itself to have one active owner DateRange and its own HouseTerm independently identified as the unique current DailTerm",
            "R_path": "members:isRepresentativeFrom exact Kildare North resource; qualify explicit DailMembership, reverse-linked same-owner Member, active membership DateRange, and exactly one inHouseTerm URI equal to the constituency's unique current HouseTerm",
            "current_term_selection": "Inventory every explicitly typed agents:DailTerm without termNo filtering; independently audit owner, termNo/houseCode, dct:temporal, and every linked dct:PeriodOfTime interval at asOf; fail closed on uncertain typed terms",
            "committee_incarnation_selection": "Inventory every committees-graph typed members:Committee whose URI slug or English label matches Public Accounts; audit all owner descriptions, each committeeInHouseTerm link, and each committees-owner operational DateRange; current incarnation must match the independently unique current DailTerm and have an active owner range",
            "intersection": "exact Member IRI set intersection of independently qualifying K and R witnesses",
            "date_policy": "Inclusive date-grain containment using each source xsd:dateTime calendar date against 2026-11-11; absent EndDate is open-ended; missing/malformed/multiple StartDate or EndDate, missing range type, and absent range are not positive witnesses",
            "simple_string_datatypes": "RDF 1.1 simple literals without xml:lang are treated as xsd:string where the authoritative property range is xsd:string; raw SPARQL JSON datatype omission is retained",
            "member_owner_graph": "Member graph derived from the single xsd:string/RDF 1.1 simple-literal agents:memberCode using UTF-8 percent-encoding in the graph URI path, then checked against the observed graph name",
            "data_scope": "Only exact target resources, matching exact membership paths, reverse-linked Member owner graphs, their membership ranges, and relevant current-term/provenance graph checks; not a full-store snapshot or completeness claim",
        },
        "query_limits": {
            "per_request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
            "per_select_limit_max": PAGE_SIZE,
            "pagination": "ORDER BY all projected RDF terms, LIMIT up to 100 OFFSET 0,100,... until final page has fewer rows than its request limit; a diagnostic-bound stop remains incomplete",
            "maximum_total_sparql_requests": MAX_DIAGNOSTIC_REQUESTS,
            "maximum_total_result_rows": MAX_DIAGNOSTIC_ROWS,
            "bound_exceeded": client.bound_exceeded,
            "request_count": client.request_count,
            "result_row_count": client.row_count,
            "kernel_request_budget_relationship": "Independent oracle diagnostic bound; not the kernel's 8-request budget",
        },
        "endpoint_provenance": env_provenance(),
        "graph_presence": graph_presence,
        "target_verification": {
            "constituency": resource_facts,
            "requested_committee_resource": requested_committee_facts,
            "matching_committee_incarnations": committees,
            "current_term": terms,
            "matching_committee_operational_range_quads": rows(
                sections.get("matching_Public_Accounts_committee_operational_range_quads")
            ),
        },
        "candidates": {
            "K_all_exact_path_candidates": k_candidates,
            "R_all_exact_path_candidates": r_candidates,
            "K_positive_witnesses": k_witnesses,
            "R_positive_witnesses": r_witnesses,
            "K_qualifying_members": k_members,
            "R_qualifying_members": r_members,
            "observed_candidate_intersection": intersection,
            "expected_members_intersection": intersection if evidence_gate else None,
            "expected_witness_fact_sets": witness_sets if evidence_gate else None,
            "observed_candidate_witness_fact_sets": witness_sets,
            "candidate_discovery_complete": target_evidence_complete,
            "positive_evidence_gate_satisfied": evidence_gate,
        },
        "sections": sections,
        "request_ledger": client.ledger,
        "completion": {
            "all_sections_complete": all_sections_complete,
            "target_evidence_complete": target_evidence_complete,
            "positive_evidence_gate_satisfied": evidence_gate,
            "does_not_claim_transactional_snapshot": True,
            "does_not_claim_source_or_dataset_completeness": True,
            "kernel_was_run": False,
        },
        "post_kernel_stability_instructions": {
            "command": "./.venv/bin/python tools/nlq_live_kr_oracle.py --mode stability",
            "output": "docs/reports/query-service/composition-live-kr-20261112/oracle/stability/oracle-<UTC timestamp>.json",
            "behavior": "Repeats the same exact-scoped read-only SELECT set and writes a new timestamped file; never overwrites oracle.json. Run only after the kernel run has completed.",
            "comparison_scope": "Compare K=Committee and R=representation candidate path rows, all typed DailTerm/PeriodOfTime facts, all matching Public Accounts Committee incarnations and owner ranges, target identity facts, Member owner/code/type/reverse links, and membership interval quads only. This is scoped evidence stability, not a transactional snapshot or full-store delta.",
        },
        "limitations": [
            "The captures are sequential requests, not a transactional dataset snapshot.",
            "No claim is made that local Fuseki contains the complete Oireachtas source corpus.",
            "As-of date-grain semantics are explicit in this independent oracle and are not asserted to reconstruct kernel behavior.",
            "No cross-path equality between constituency-member HouseTerm and Committee HouseTerm is applied.",
            "No party collection or affiliation evidence is queried or used.",
        ],
        "suggested_output_path": str(output_path.relative_to(ROOT)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("baseline", "stability"),
        default="baseline",
        help="baseline writes the frozen pre-kernel oracle.json; stability writes a new timestamped capture under oracle/stability/",
    )
    args = parser.parse_args()
    output_path = (
        ORACLE_DIR / "oracle.json"
        if args.mode == "baseline"
        else ORACLE_DIR / "stability" / f"oracle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    if args.mode == "baseline" and output_path.exists():
        print(f"Refusing to overwrite baseline oracle: {output_path}", file=sys.stderr)
        return 2

    capture: dict[str, Any]
    try:
        capture = build_capture(args.mode)
        # Resolve output path from the capture's generated timestamp; baseline is fixed,
        # stability is always a separate timestamped file.
        output_path = ROOT / capture["suggested_output_path"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("x", encoding="utf-8") as output:
            output.write(json.dumps(capture, indent=2, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"Oracle capture failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    complete = capture["completion"]["all_sections_complete"]
    positive = capture["completion"]["positive_evidence_gate_satisfied"]
    print(f"capture={output_path}")
    print(f"complete={complete} positive_evidence_gate={positive}")
    print(f"requests={capture['query_limits']['request_count']} rows={capture['query_limits']['result_row_count']}")
    print(
        "intersection_members="
        f"{len(capture['candidates']['observed_candidate_intersection'])}"
    )
    return 0 if complete and positive else 1


if __name__ == "__main__":
    raise SystemExit(main())
