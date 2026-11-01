"""Date-relative and career-wide projection of the reviewed representation path."""

from datetime import date
import re

from rdflib import URIRef

from .composable_plan import (
    AmbiguousConstituency, AmbiguousMember, NLQError, PlanError, PlanOutcome,
    _PREFIXES, _date_binding, _mapped_member_interval, _query, _require_local_iri,
    _reviewed_predicate, constituency_resolution_query, member_resolution_query,
    previous_dail_term_query, resolve_constituency, resolve_member,
)
from .contract import load_query_contract
from .pagination import select_pages
from .results import QueryResult


EDGES = {
    "member_has_membership": ("member", "membership"),
    "membership_in_term": ("membership", "term"),
    "membership_represents": ("membership", "constituency"),
    "constituency_in_term": ("constituency", "term"),
}


def representation_plan(*, as_of, member=None, constituency=None, current=True):
    refs = {"member": {"type": "Member"}, "membership": {"type": "DailMembership"},
            "term": {"type": "DailTerm"}, "constituency": {"type": "DailConstituency"}}
    named = "member" if member else "constituency"
    refs[named].update(mention=member or constituency, resolution="unresolved")
    answer = "constituency" if member else "member"
    refs[answer]["answer"] = True
    if current:
        refs["term"]["selector"] = {"kind": "currentTerm", "house": "Dail"}
    plan = {"version": 2, "asOf": as_of.isoformat(), "family": "constituency_representation",
            "referents": refs,
            "relations": [{"id": fact, "fact": fact, "from": source, "to": target}
                          for fact, (source, target) in EDGES.items()],
            "answer": {"kind": "entities", "referent": answer, "distinctBy": "identity",
                       "display": ["label" if member else "name"],
                       "details": [{"referent": "term", "display": ["label"]}],
                       "preserveEvidence": True}}
    return validate_representation_plan(plan)


def plan_representation_question(question, *, as_of):
    text = question.strip().rstrip("?.!")
    match = re.fullmatch(
        r"(?:who are (?:the )?(?:current )?(?:TDs|deputies)|which (?:TDs|deputies) represent)"
        r" (?:for )?(?P<constituency>.+?)(?: in the (?:current|present) D[áa]il)?", text, re.I)
    if match:
        return representation_plan(as_of=as_of, constituency=match["constituency"])
    match = re.fullmatch(
        r"(?:what|which) constituenc(?:y|ies) (?P<tense>does|did|has) (?P<member>.+?) "
        r"(?:represent|represented)(?: (?:now|currently|in the current D[áa]il))?", text, re.I)
    if match:
        return representation_plan(as_of=as_of, member=match["member"], current=match["tense"].lower() == "does")
    return None


def validate_representation_plan(plan):
    refs = plan["referents"]
    if set(plan) != {"version", "asOf", "family", "referents", "relations", "answer"}:
        raise PlanError("Representation plans do not accept additional constraints.")
    if set(refs) != {"member", "membership", "term", "constituency"}:
        raise PlanError("Representation requires the complete membership/constituency/term path.")
    types = {"member": "Member", "membership": "DailMembership", "term": "DailTerm", "constituency": "DailConstituency"}
    for key, ref in refs.items():
        if ref.get("type") != types[key]:
            raise PlanError("Invalid representation referent type.")
        allowed = {"type", "answer", "mention", "resolution", "iri", "label", "candidates", "asOfEvidence"}
        if key == "term":
            allowed.add("selector")
        if set(ref) - allowed:
            raise PlanError("Unsupported representation referent fields.")
        if "iri" in ref:
            _require_local_iri(ref["iri"], key)
    named = [key for key in ("member", "constituency") if refs[key].get("mention")]
    if len(named) != 1 or any(not isinstance(refs[key]["mention"], str) or not refs[key]["mention"].strip() for key in named):
        raise PlanError("Exactly one Member or constituency mention is required.")
    current = "selector" in refs["term"]
    if current and refs["term"]["selector"] != {"kind": "currentTerm", "house": "Dail"}:
        raise PlanError("Representation supports only the current date-relative term selector.")
    if not current and named != ["member"]:
        raise PlanError("Career-wide representation requires a named Member.")
    expected = sorted((fact, source, target) for fact, (source, target) in EDGES.items())
    relations = plan["relations"]
    if (not isinstance(relations, list) or any(set(edge) != {"id", "fact", "from", "to"} for edge in relations)
            or len({edge["id"] for edge in relations}) != len(relations)
            or sorted((edge["fact"], edge["from"], edge["to"]) for edge in relations) != expected):
        raise PlanError("Every reviewed representation edge is required exactly once.")
    answer = "constituency" if named == ["member"] else "member"
    if plan["answer"] != {"kind": "entities", "referent": answer, "distinctBy": "identity",
                          "display": ["label" if answer == "constituency" else "name"],
                          "details": [{"referent": "term", "display": ["label"]}], "preserveEvidence": True}:
        raise PlanError("Representation answer must preserve constituency and Dáil-term evidence.")
    return plan


def resolve_current_dail(result, as_of):
    if result.kind != "select" or len(result.rows) >= 100:
        raise NLQError("House-term date lookup is incomplete; no current Dáil was selected.")
    intervals = {}
    for iri, start, end in result.rows:
        _require_local_iri(iri, "DailTerm")
        interval = (_date_binding(start), None if end in {"—", ""} else _date_binding(end))
        if interval[1] is not None and interval[1] < interval[0]:
            raise NLQError("House-term end precedes its start.")
        if iri in intervals and intervals[iri] != interval:
            raise NLQError("Conflicting House-term date evidence.")
        intervals[iri] = interval
    active = [iri for iri, (start, end) in intervals.items() if start <= as_of and (end is None or as_of <= end)]
    if len(active) != 1:
        raise NLQError("Source data does not identify exactly one current Dáil at the reference date.")
    return active[0]


def compile_representation_query(plan, *, supported_predicates):
    validate_representation_plan(plan)
    refs = plan["referents"]
    graphs = {item["id"]: item["graph"] for item in load_query_contract()["graphFamilies"]}
    joins = {fact: _reviewed_predicate(fact) for fact in EDGES}
    values = "\n".join(f"VALUES ?{key} {{ {URIRef(_require_local_iri(ref['iri'], key)).n3()} }}"
                       for key, ref in refs.items() if "iri" in ref)
    return _query(_PREFIXES + f'''SELECT DISTINCT ?member ?name ?membership ?constituency ?label ?term ?termLabel ?range ?start ?end WHERE {{
  {values}
  GRAPH ?memberGraph {{
    ?member a agents:Member ; foaf:name ?name ; {joins['member_has_membership']} ?membership .
    ?membership a members:DailMembership ; {joins['membership_in_term']} ?term ; {joins['membership_represents']} ?constituency .
    OPTIONAL {{ ?membership members:hasMembershipDateRange ?range .
      OPTIONAL {{ ?range members:StartDate ?start . }} OPTIONAL {{ ?range members:EndDate ?end . }} }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), "{graphs['member-records']['iriTemplate'].split('{')[0]}"))
  GRAPH <{graphs['constituencies']['iri']}> {{ ?constituency a members:DailConstituency ;
    skos:prefLabel ?label ; {joins['constituency_in_term']} ?term . }}
  GRAPH <{graphs['houses']['iri']}> {{ ?term a agents:DailTerm ; skos:prefLabel ?termLabel . }}
}} ORDER BY ?member ?membership ?constituency ?term ?name ?label ?termLabel ?range ?start ?end LIMIT 100''', supported_predicates)


def execute_representation(plan, *, fuseki, supported_predicates):
    refs = plan["referents"]
    as_of = date.fromisoformat(plan["asOf"])
    query = None
    try:
        current = "selector" in refs["term"]
        if current:
            term = resolve_current_dail(fuseki.query(previous_dail_term_query(as_of, supported_predicates=supported_predicates)), as_of)
            refs["term"].update(iri=term, resolution="resolved", asOfEvidence=as_of.isoformat())
        if refs["member"].get("mention"):
            mention = refs["member"]["mention"]
            iri, label = resolve_member(fuseki.query(member_resolution_query(mention, supported_predicates=supported_predicates)), mention)
            refs["member"].update(iri=iri, label=label, resolution="resolved")
        else:
            mention = refs["constituency"]["mention"]
            raw = fuseki.query(constituency_resolution_query(mention, term, supported_predicates=supported_predicates))
            if len(raw.rows) >= 100:
                raise NLQError("Constituency lookup reached its safety cap; no occurrence was selected.")
            iri, label = resolve_constituency(raw, mention, term_label="the current Dáil")
            refs["constituency"].update(iri=iri, label=label, resolution="resolved")
        query = compile_representation_query(plan, supported_predicates=supported_predicates)
        raw = select_pages(query, fuseki=fuseki, supported_predicates=supported_predicates)
        if not raw.rows:
            raise NLQError("No matching representation evidence is available; local absence does not establish a historical negative.")
        records = [dict(zip(raw.columns, row)) for row in raw.rows]
        if current:
            intervals = {}
            for row in records:
                intervals.setdefault(row["membership"], set()).add((row["range"], row["start"], row["end"]))
            active = set()
            for membership, values in intervals.items():
                start, end = _mapped_member_interval(values, label="Dáil membership")
                if start.date() <= as_of and (end is None or as_of <= end.date()):
                    active.add(membership)
            records = [row for row in records if row["membership"] in active]
            if not records:
                raise NLQError("No current representation is evidenced at the reference date.")
        rows = set()
        for row in records:
            for key in ("member", "membership", "term", "constituency"):
                _require_local_iri(row[key], key)
            rows.add((row["name"].removesuffix("@en"), row["label"].removesuffix("@en"),
                      row["termLabel"].removesuffix("@en"), row["member"], row["constituency"], row["term"]))
        result = QueryResult("select", ("Member", "Constituency", "Dáil term", "Member identity", "Constituency identity", "Term identity"),
                             tuple(sorted(rows)), raw.raw_json)
        return PlanOutcome("success", plan=plan, sparql=query, result=result,
                           diagnostic=f"Recorded representation evidence{' at ' + as_of.isoformat() if current else ' across recorded Dáil terms'}. Local source completeness is not certified.")
    except (AmbiguousMember, AmbiguousConstituency) as error:
        key = "member" if isinstance(error, AmbiguousMember) else "constituency"
        refs[key].update(resolution="ambiguous", candidates=list(error.candidates))
        return PlanOutcome("ambiguous", plan=plan, candidates=error.candidates, diagnostic=str(error))
    except NLQError as error:
        status = "not_found" if "No local Member" in str(error) or "No matching constituency" in str(error) else "source_data_unavailable"
        return PlanOutcome(status, plan=plan, sparql=query, diagnostic=str(error))
