"""Bounded current named-Committee roster over accepted membership evidence."""

from datetime import date
import re
import unicodedata

from rdflib import URIRef

from .composable_plan import (
    PlanError, PlanOutcome, _PREFIXES, _date_binding, _mapped_member_interval,
    _query, _require_local_iri, _reviewed_predicate,
)
from .contract import load_query_contract
from .errors import NLQError
from .pagination import select_pages
from .results import QueryResult
from .stage_a import _committee_catalogue_query


FAMILY = "current_committee_members"
EDGES = {
    "member_has_committee_membership": ("member", "membership"),
    "committee_membership_of_committee": ("membership", "committee"),
}


def validate_request(question, mention):
    """A closed projection; every word outside the grounded name is accounted for."""
    text = re.sub(re.escape(mention), "committee", question, flags=re.I)
    if text == question or not re.fullmatch(
        r"\s*(?:who\s+are\s+(?:the\s+)?(?:current\s+)?members\s+of\s+(?:the\s+)?committee|"
        r"which\s+members\s+(?:currently\s+)?(?:serve|sit)\s+on\s+(?:the\s+)?committee|"
        r"(?:list|show)(?:\s+me)?\s+(?:the\s+)?(?:current\s+)?members\s+of\s+(?:the\s+)?committee)"
        r"(?:\s+(?:currently|now|today))?\s*[?.!]?\s*", text, re.I,
    ):
        raise ValueError("Current committee Member listing cannot discard historical dates, extra conditions or other answer fields.")


def _name_key(value):
    value = " ".join(unicodedata.normalize("NFC", value).casefold().split())
    # Only the generic connector varies; the whole source-backed name must match.
    # Distinct matching owner IRIs remain distinct, never merged by this key.
    return re.sub(r"^committee (?:on|of) ", "committee ", value)


def make_plan(mention, as_of):
    return {
        "version": 2, "asOf": as_of.isoformat(), "family": FAMILY,
        "referents": {"member": {"type": "Member"},
                      "membership": {"type": "CommitteeMembership"},
                      "committee": {"type": "Committee", "mention": mention}},
        "relations": [{"id": fact, "fact": fact, "from": source, "to": target}
                      for fact, (source, target) in EDGES.items()],
        "constraints": [{"referent": ref, "field": "interval", "operator": "currentAt", "value": as_of.isoformat()}
                        for ref in ("committee", "membership")],
        "answer": {"kind": "entities", "referent": "member", "distinctBy": "identity",
                   "display": ["name"], "preserveEvidence": True},
    }


def validate_committee_plan(plan):
    try:
        expected = make_plan(plan["referents"]["committee"]["mention"], date.fromisoformat(plan["asOf"]))
        if (not isinstance(expected["referents"]["committee"]["mention"], str)
                or not expected["referents"]["committee"]["mention"].strip() or plan != expected):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise PlanError("Current committee listing requires its complete closed membership graph and both asOf constraints.") from None
    return plan


def _records(result, columns):
    if result.kind != "select" or not set(columns).issubset(result.columns):
        raise NLQError("Committee evidence returned an incomplete SELECT shape.")
    if any(len(row) != len(result.columns) or not all(isinstance(cell, str) for cell in row) for row in result.rows):
        raise NLQError("Committee evidence returned a truncated or malformed row.")
    return [dict(zip(result.columns, row)) for row in result.rows]


def resolve_committee(result, mention, as_of):
    records = _records(result, ("committee", "label", "term", "range", "period", "termType", "start", "end", "termStart", "termEnd"))
    matches = {}
    for row in records:
        label = row["label"].removesuffix("@en")
        if _name_key(label) != _name_key(mention):
            continue
        iri = _require_local_iri(row["committee"], "Committee")
        entry = matches.setdefault(iri, {"labels": set(), "owners": set(), "terms": set()})
        entry["labels"].add(label)
        entry["owners"].add((row["range"], row["start"], row["end"]))
        entry["terms"].add(tuple(row[k] for k in ("term", "termType", "period", "termStart", "termEnd")))
    if not matches:
        raise NLQError("No accepted Committee owner has a complete matching name; no Committee identity was guessed.")
    current = []
    for iri, entry in matches.items():
        owner_start, owner_end = _mapped_member_interval(entry["owners"], label="Committee owner")
        if len(entry["terms"]) != 1 or len(entry["labels"]) != 1:
            raise NLQError("Conflicting Committee owner term or name evidence; no incarnation was selected.")
        term, term_type, period, ts, te = next(iter(entry["terms"]))
        _require_local_iri(term, "HouseTerm")
        _require_local_iri(period, "HouseTerm period")
        if term_type not in {"https://data.oireachtas.ie/ontology#DailTerm", "https://data.oireachtas.ie/ontology#SeanadTerm"}:
            raise NLQError("Committee owner has no typed HouseTerm date evidence.")
        term_start = _date_binding(ts)
        term_end = None if te in {"—", ""} else _date_binding(te)
        if term_end is not None and term_end < term_start:
            raise NLQError("Committee HouseTerm end precedes its start.")
        if (owner_start.date() <= as_of and (owner_end is None or as_of <= owner_end.date())
                and term_start <= as_of and (term_end is None or as_of <= term_end)):
            current.append({"iri": iri, "label": next(iter(entry["labels"])),
                            "range": next(iter(entry["owners"]))[0], "start": owner_start.isoformat(),
                            "end": owner_end.isoformat() if owner_end else "open-ended",
                            "term": term, "period": period, "termStart": term_start.isoformat(),
                            "termEnd": term_end.isoformat() if term_end else "open-ended"})
    return current


def compile_members_query(committee, *, supported_predicates):
    graphs = {item["id"]: item["graph"] for item in load_query_contract()["graphFamilies"]}
    iri = URIRef(_require_local_iri(committee, "Committee")).n3()
    member_link = _reviewed_predicate("member_has_committee_membership")
    committee_link = _reviewed_predicate("committee_membership_of_committee")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?memberGraph ?member ?name ?membership ?committee ?range ?start ?end WHERE {{
  GRAPH ?memberGraph {{
    ?member a agents:Member ; {member_link} ?membership .
    OPTIONAL {{ ?member foaf:name ?name . }}
    ?membership a members:CommitteeMembership ; {committee_link} {iri} ; {committee_link} ?committee .
    OPTIONAL {{ ?membership members:hasMembershipDateRange ?range .
      OPTIONAL {{ ?range members:StartDate ?start . }} OPTIONAL {{ ?range members:EndDate ?end . }} }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), "{graphs['member-records']['iriTemplate'].split('{')[0]}"))
}} ORDER BY ?member ?membership ?committee ?range ?start ?end ?name ?memberGraph LIMIT 100''', supported_predicates)


def project_members(raw, owner, as_of):
    records = _records(raw, ("memberGraph", "member", "name", "membership", "committee", "range", "start", "end"))
    memberships = {}
    for row in records:
        for key in ("memberGraph", "member", "membership", "committee"):
            _require_local_iri(row[key], key)
        if row["committee"] != owner["iri"]:
            raise NLQError("A CommitteeMembership has conflicting Committee targets.")
        entry = memberships.setdefault(row["membership"], {"members": set(), "names": set(), "ranges": set(), "graphs": set()})
        entry["members"].add(row["member"])
        entry["names"].add(row["name"].removesuffix("@en"))
        entry["graphs"].add(row["memberGraph"])
        entry["ranges"].add((row["range"], row["start"], row["end"]))
    members = {}
    for membership, entry in memberships.items():
        start, end = _mapped_member_interval(entry["ranges"], label="CommitteeMembership")
        if any(len(entry[k]) != 1 for k in ("members", "names", "graphs")) or entry["names"] & {"—", ""}:
            raise NLQError("CommitteeMembership Member identity/name or source graph is missing or conflicting.")
        if start.date() <= as_of and (end is None or as_of <= end.date()):
            member = next(iter(entry["members"]))
            name = next(iter(entry["names"]))
            item = members.setdefault(member, {"names": set(), "evidence": set()})
            item["names"].add(name)
            item["evidence"].add(f"{membership} | {next(iter(entry['ranges']))[0]} | {start.isoformat()} – {end.isoformat() if end else 'open-ended'} | source graph: {next(iter(entry['graphs']))}")
    if not members:
        raise NLQError("No current CommitteeMembership is locally evidenced; this is not a certified empty roster.")
    rows = []
    for member, item in members.items():
        if len(item["names"]) != 1:
            raise NLQError("A Member has conflicting committee-roster display names.")
        rows.append((next(iter(item["names"])), member, owner["label"], owner["iri"],
                     "\n".join(sorted(item["evidence"])), owner["range"], owner["start"], owner["end"],
                     owner["term"], owner["period"], owner["termStart"], owner["termEnd"], as_of.isoformat()))
    return QueryResult("select", ("Member", "Member identity", "Committee", "Committee identity", "Membership evidence",
                                  "Committee date range", "Committee start", "Committee end", "HouseTerm identity",
                                  "HouseTerm period", "HouseTerm start", "HouseTerm end", "As of"), tuple(sorted(rows)), raw.raw_json)


def execute_committee_members(mention, *, as_of, fuseki, supported_predicates):
    plan = make_plan(mention, as_of)
    validate_committee_plan(plan)
    query = None
    try:
        query = _committee_catalogue_query(supported_predicates=supported_predicates, preserve_evidence=True)
        catalogue = select_pages(query, fuseki=fuseki, supported_predicates=supported_predicates)
        current = resolve_committee(catalogue, mention, as_of)
        if len(current) > 1:
            return PlanOutcome("ambiguous", plan=plan, sparql=query, candidates=tuple({"iri": c["iri"], "label": c["label"]} for c in current),
                               diagnostic="Several current Committee incarnations match; none was selected.")
        if not current:
            raise NLQError("No uniquely evidenced current Committee incarnation exists at asOf.")
        query = compile_members_query(current[0]["iri"], supported_predicates=supported_predicates)
        raw = select_pages(query, fuseki=fuseki, supported_predicates=supported_predicates)
        result = project_members(raw, current[0], as_of)
        return PlanOutcome("success", plan=plan, sparql=query, result=result, request_family=FAMILY,
                           diagnostic=f"Locally recorded CommitteeMemberships active at {as_of.isoformat()}; not a certified complete current roster. "
                                      "The Committee and its HouseTerm independently contain asOf. Membership does not establish chairmanship or attendance; missing end dates remain open-ended.")
    except NLQError as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, diagnostic=str(error), request_family=FAMILY)
