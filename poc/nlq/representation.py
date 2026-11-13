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
from .errors import IdentityNotFound, QueryLimitError


EDGES = {
    "member_has_membership": ("member", "membership"),
    "membership_in_term": ("membership", "term"),
    "membership_represents": ("membership", "constituency"),
    "constituency_in_term": ("constituency", "term"),
}


def representation_plan(*, as_of, member=None, constituency=None, current=True, latest_recorded=False):
    if current and latest_recorded:
        raise PlanError("Current and latest-recorded Dáil selection are distinct temporal scopes.")
    refs = {"member": {"type": "Member"}, "membership": {"type": "DailMembership"},
            "term": {"type": "DailTerm"}, "constituency": {"type": "DailConstituency"}}
    named = "member" if member else "constituency"
    refs[named].update(mention=member or constituency, resolution="unresolved")
    answer = "constituency" if member else "member"
    refs[answer]["answer"] = True
    if current:
        refs["term"]["selector"] = {"kind": "currentTerm", "house": "Dail"}
    elif latest_recorded:
        if not member:
            raise PlanError("Latest-recorded Dáil selection requires a named Member.")
        refs["term"]["selector"] = {"kind": "latestRecorded"}
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
    latest = re.fullmatch(
        r"(?:what|which)\s+(?:was\s+)?(?:the\s+)?(?:latest\s+recorded\s+d[áa]il\s+term\s+and\s+)?"
        r"constituenc(?:y|ies)\s+(?:did\s+)?(?P<member>.+?)\s+(?:represent|represented|serve(?:d)?)\s+"
        r"(?:in\s+(?:(?:his|her|their|the)\s+)?(?:latest\s+recorded|most\s+recent)\s+d[áa]il\s+term|"
        r"(?:as\s+)?(?:their\s+)?latest\s+recorded\s+d[áa]il\s+term)", text, re.I,
    )
    if latest:
        return representation_plan(as_of=as_of, member=latest["member"], current=False,
                                   latest_recorded=True)
    latest_for = re.fullmatch(
        r"what\s+was\s+(?:the\s+)?(?:latest\s+recorded\s+)?d[áa]il\s+term\s+and\s+"
        r"constituenc(?:y|ies)\s+(?:for|of)\s+(?P<member>.+?)\s*", text, re.I,
    )
    if latest_for and re.search(r"\b(?:latest|most recent)\b", text, re.I):
        return representation_plan(as_of=as_of, member=latest_for["member"], current=False,
                                   latest_recorded=True)
    latest_served = re.fullmatch(
        r"(?:which|what)\s+d[áa]il\s+term\s+and\s+constituenc(?:y|ies)\s+did\s+"
        r"(?P<member>.+?)\s+serve\s+(?:most\s+recently|in\s+(?:their\s+)?latest\s+recorded\s+d[áa]il\s+term)",
        text, re.I,
    )
    if latest_served:
        return representation_plan(as_of=as_of, member=latest_served["member"], current=False,
                                   latest_recorded=True)
    match = re.fullmatch(
        r"(?:who are (?:the )?(?:current )?(?:TDs|deputies)|which (?:TDs|deputies) represent)"
        r" (?:(?:for|representing) )?(?P<constituency>.+?)(?: in the (?:current|present) D[áa]il)?", text, re.I)
    if match:
        plan = representation_plan(as_of=as_of, constituency=match["constituency"])
        from .interpretation import current_relationship_scope, default_evidence, present_constituency_default
        if (present_constituency_default(question, match["constituency"])
                and current_relationship_scope(question, match["constituency"]) == "inferred"):
            plan["interpretation"] = default_evidence(question, as_of)
        return validate_representation_plan(plan)
    match = re.fullmatch(
        r"(?:what|which) constituenc(?:y|ies) (?P<tense>does|did|has) (?P<member>.+?) "
        r"(?:represent|represented)(?: (?:now|currently|in the current D[áa]il))?", text, re.I)
    if match:
        return representation_plan(as_of=as_of, member=match["member"], current=match["tense"].lower() == "does")
    return None


def validate_representation_plan(plan):
    refs = plan["referents"]
    if set(plan) - {"interpretation"} != {"version", "asOf", "family", "referents", "relations", "answer"}:
        raise PlanError("Representation plans do not accept additional constraints.")
    if set(refs) != {"member", "membership", "term", "constituency"}:
        raise PlanError("Representation requires the complete membership/constituency/term path.")
    types = {"member": "Member", "membership": "DailMembership", "term": "DailTerm", "constituency": "DailConstituency"}
    for key, ref in refs.items():
        if ref.get("type") != types[key]:
            raise PlanError("Invalid representation referent type.")
        allowed = {"type", "answer", "mention", "resolution", "iri", "label", "candidates", "asOfEvidence", "termStart"}
        if key == "term":
            allowed.add("selector")
        if set(ref) - allowed:
            raise PlanError("Unsupported representation referent fields.")
        if "iri" in ref:
            _require_local_iri(ref["iri"], key)
    named = [key for key in ("member", "constituency") if refs[key].get("mention")]
    if len(named) != 1 or any(not isinstance(refs[key]["mention"], str) or not refs[key]["mention"].strip() for key in named):
        raise PlanError("Exactly one Member or constituency mention is required.")
    selector = refs["term"].get("selector")
    current = selector == {"kind": "currentTerm", "house": "Dail"}
    latest_recorded = selector == {"kind": "latestRecorded"}
    from .interpretation import validate_default
    try:
        validate_default(plan, constituency=refs["constituency"].get("mention", ""), current=current)
    except ValueError as error:
        raise PlanError(str(error)) from error
    if selector is not None and not (current or latest_recorded):
        raise PlanError("Representation supports only current or latest-recorded Dáil term selectors.")
    if latest_recorded and named != ["member"]:
        raise PlanError("Latest-recorded term selection requires a named Member.")
    if "termStart" in refs["term"]:
        try:
            recorded_start = date.fromisoformat(refs["term"]["termStart"])
        except (TypeError, ValueError) as error:
            raise PlanError("Latest-recorded term start must be a valid House-owned calendar date.") from error
        if recorded_start.isoformat() != refs["term"]["termStart"]:
            raise PlanError("Latest-recorded term start must use canonical ISO calendar spelling.")
        if not latest_recorded or refs["term"].get("resolution") != "resolved" or "iri" not in refs["term"]:
            raise PlanError("House-owned latest-term date evidence requires the exact resolved term identity.")
    if current and "resolution" in refs["term"]:
        if (refs["term"].get("resolution") != "resolved"
                or set(refs["term"]) != {"type", "selector", "resolution", "iri", "asOfEvidence"}
                or refs["term"].get("asOfEvidence") != plan["asOf"]):
            raise PlanError("Resolved current-term selection must preserve its asOf evidence and exact identity.")
    elif latest_recorded and "resolution" in refs["term"]:
        if (set(refs["term"]) != {"type", "selector", "resolution", "iri", "termStart"}
                or refs["term"].get("resolution") != "resolved"):
            raise PlanError("Resolved latest-term selection must preserve House-owned chronology and exact identity.")
    elif not (current or latest_recorded) and set(refs["term"]) != {"type"}:
        raise PlanError("Career-wide representation cannot carry a selected term identity.")
    if not current and not latest_recorded and named != ["member"]:
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
    required_columns = {"term", "start", "end"}
    if (result.kind != "select" or not required_columns.issubset(result.columns)
            or len(result.rows) >= 100):
        raise NLQError("House-term date lookup is incomplete; no current Dáil was selected.")
    indexes = {name: result.columns.index(name) for name in required_columns}
    intervals = {}
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError("House-term date lookup returned a truncated row; no current Dáil was selected.")
        iri, start, end = (row[indexes[name]] for name in ("term", "start", "end"))
        if not all(isinstance(value, str) for value in (iri, start, end)):
            raise NLQError("House-term date lookup returned malformed values; no current Dáil was selected.")
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


def resolve_current_house_term(result, as_of, *, term_type):
    """Resolve one typed current HouseTerm from its House-owned date interval."""
    if term_type not in {"DailTerm", "SeanadTerm"}:
        raise NLQError("Current HouseTerm selection requires an exact reviewed Dáil or Seanad type.")
    required_columns = {"term", "start", "end"}
    house = "Dáil" if term_type == "DailTerm" else "Seanad"
    if (result.kind != "select" or not required_columns.issubset(result.columns)
            or len(result.rows) >= 100):
        raise NLQError(f"House-term date lookup is incomplete; no current {house} was selected.")
    indexes = {name: result.columns.index(name) for name in required_columns}
    intervals = {}
    for row in result.rows:
        if len(row) <= max(indexes.values()):
            raise NLQError(f"House-term date lookup returned a truncated row; no current {house} was selected.")
        iri, start, end = (row[indexes[name]] for name in ("term", "start", "end"))
        if not all(isinstance(value, str) for value in (iri, start, end)):
            raise NLQError(f"House-term date lookup returned malformed values; no current {house} was selected.")
        _require_local_iri(iri, term_type)
        if start in {"—", ""}:
            raise NLQError(f"A typed {house} term has no recorded House-owned start date.")
        interval = (_date_binding(start), None if end in {"—", ""} else _date_binding(end))
        if interval[1] is not None and interval[1] < interval[0]:
            raise NLQError("House-term end precedes its start.")
        if iri in intervals and intervals[iri] != interval:
            raise NLQError("Conflicting House-term date evidence.")
        intervals[iri] = interval
    active = [iri for iri, (start, end) in intervals.items()
              if start <= as_of and (end is None or as_of <= end)]
    if len(active) != 1:
        raise NLQError(f"Source data does not identify exactly one current {house} at the reference date.")
    return active[0]


def compile_representation_query(plan, *, supported_predicates, preserve_unlabelled=False):
    validate_representation_plan(plan)
    refs = plan["referents"]
    graphs = {item["id"]: item["graph"] for item in load_query_contract()["graphFamilies"]}
    joins = {fact: _reviewed_predicate(fact) for fact in EDGES}
    values = "\n".join(f"VALUES ?{key} {{ {URIRef(_require_local_iri(ref['iri'], key)).n3()} }}"
                       for key, ref in refs.items() if "iri" in ref)
    label_pattern = "?constituency skos:prefLabel ?label ."
    term_label_pattern = "?term skos:prefLabel ?termLabel ."
    if preserve_unlabelled:
        label_pattern = f"OPTIONAL {{ {label_pattern} }}"
        term_label_pattern = f"OPTIONAL {{ {term_label_pattern} }}"
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
    {joins['constituency_in_term']} ?term . {label_pattern} }}
  GRAPH <{graphs['houses']['iri']}> {{ ?term a agents:DailTerm . {term_label_pattern} }}
}} ORDER BY ?member ?membership ?constituency ?term ?name ?label ?termLabel ?range ?start ?end LIMIT 100''', supported_predicates)


def compile_member_dail_terms_query(member_iri, *, supported_predicates):
    """Read every recorded Member→DailMembership→DailTerm identity path."""
    member = URIRef(_require_local_iri(member_iri, "Member")).n3()
    graphs = {item["id"]: item["graph"] for item in load_query_contract()["graphFamilies"]}
    member_prefix = graphs["member-records"]["iriTemplate"].split("{")[0]
    houses_graph = graphs["houses"]["iri"]
    member_link = _reviewed_predicate("member_has_membership")
    term_link = _reviewed_predicate("membership_in_term")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?membership ?term WHERE {{
  GRAPH ?memberGraph {{
    {member} a agents:Member ; {member_link} ?membership .
    ?membership a members:DailMembership ; {term_link} ?term .
  }}
  FILTER(STRSTARTS(STR(?memberGraph), {repr(member_prefix)}))
  GRAPH <{houses_graph}> {{ ?term a agents:DailTerm . }}
}} ORDER BY ?term ?membership LIMIT 100''', supported_predicates)


def execute_representation(plan, *, fuseki, supported_predicates, resolved_member=None, preserve_membership_evidence=False):
    """Execute the reviewed path; a local relationship adapter may bind an exact Member.

    ``resolved_member`` is never model input. It avoids re-resolving an officeholder
    by display name and can only bind the named-Member current representation path.
    """
    validate_representation_plan(plan)
    refs = plan["referents"]
    as_of = date.fromisoformat(plan["asOf"])
    query = None
    try:
        selector = refs["term"].get("selector")
        current = selector == {"kind": "currentTerm", "house": "Dail"}
        latest_recorded = selector == {"kind": "latestRecorded"}
        if current:
            term = resolve_current_dail(fuseki.query(previous_dail_term_query(as_of, supported_predicates=supported_predicates)), as_of)
            refs["term"].update(iri=term, resolution="resolved", asOfEvidence=as_of.isoformat())
        if resolved_member is not None:
            if (not current or not refs["member"].get("mention") or refs["constituency"].get("mention")
                    or not isinstance(resolved_member, tuple) or len(resolved_member) != 2):
                raise NLQError("An exact relationship-bound Member requires current named-Member representation.")
            iri, label = resolved_member
            _require_local_iri(iri, "Member")
            if not isinstance(label, str) or label == "—" or not label.strip():
                raise NLQError("The relationship-bound Member has no usable display name.")
            refs["member"].update(iri=iri, label=label, resolution="resolved")
        elif refs["member"].get("mention"):
            mention = refs["member"]["mention"]
            iri, label = resolve_member(fuseki.query(member_resolution_query(mention, supported_predicates=supported_predicates)), mention)
            refs["member"].update(iri=iri, label=label, resolution="resolved")
        if latest_recorded:
            member_iri = refs["member"]["iri"]
            service_result = fuseki.query(
                compile_member_dail_terms_query(member_iri, supported_predicates=supported_predicates),
            )
            if (service_result.kind != "select"
                    or not {"membership", "term"}.issubset(service_result.columns)
                    or len(service_result.rows) >= 100):
                raise NLQError("The Member DailMembership-to-DailTerm evidence is incomplete; no latest recorded term was selected.")
            service_indexes = {name: service_result.columns.index(name) for name in ("membership", "term")}
            terms_by_membership = {}
            service_terms = set()
            for row in service_result.rows:
                if len(row) <= max(service_indexes.values()):
                    raise NLQError("The Member DailMembership query returned a truncated identity row.")
                membership_iri = _require_local_iri(row[service_indexes["membership"]], "DailMembership")
                term_iri = _require_local_iri(row[service_indexes["term"]], "DailTerm")
                terms_by_membership.setdefault(membership_iri, set()).add(term_iri)
                service_terms.add(term_iri)
            if not service_terms:
                raise NLQError("No accepted DailMembership-to-DailTerm path is recorded for this Member.")
            if any(len(terms) != 1 for terms in terms_by_membership.values()):
                raise NLQError("A recorded DailMembership links to conflicting DailTerm identities.")

            timeline = fuseki.query(previous_dail_term_query(as_of, supported_predicates=supported_predicates))
            if (timeline.kind != "select" or not {"term", "start", "end"}.issubset(timeline.columns)
                    or len(timeline.rows) >= 100):
                raise NLQError("House-term chronology is incomplete; no latest recorded Dáil was selected.")
            timeline_indexes = {name: timeline.columns.index(name) for name in ("term", "start", "end")}
            chronology_rows: dict[str, set[tuple[str, str]]] = {}
            for row in timeline.rows:
                if len(row) <= max(timeline_indexes.values()):
                    raise NLQError("House-term chronology returned a truncated row.")
                term_iri = _require_local_iri(row[timeline_indexes["term"]], "DailTerm")
                if term_iri not in service_terms:
                    continue
                chronology_rows.setdefault(term_iri, set()).add(
                    (row[timeline_indexes["start"]], row[timeline_indexes["end"]]),
                )
            missing_terms = service_terms - set(chronology_rows)
            if missing_terms:
                raise NLQError("A recorded Member DailTerm is missing House-owned chronology evidence; no latest term was guessed.")
            chronology = {}
            for term_iri in service_terms:
                evidence = chronology_rows[term_iri]
                if len(evidence) != 1:
                    raise NLQError("Conflicting House-owned dates prevent latest-term selection.")
                start_text, end_text = next(iter(evidence))
                start = _date_binding(start_text)
                end = None if end_text in {"—", ""} else _date_binding(end_text)
                if end is not None and end < start:
                    raise NLQError("House-term chronology contains an end date before its start.")
                chronology[term_iri] = (start, end)
            ordered = sorted((chronology[term][0], term) for term in service_terms)
            if len({start for start, _term in ordered}) != len(ordered):
                raise NLQError("Two recorded Member terms have tied House-owned start dates; latest-term selection is ambiguous.")
            for (_previous_start, previous_term), (next_start, _next_term) in zip(ordered, ordered[1:]):
                previous_end = chronology[previous_term][1]
                if previous_end is None or previous_end >= next_start:
                    raise NLQError("Recorded Member terms have conflicting or incomplete House-owned chronology.")
            latest_start, latest_term = ordered[-1]
            refs["term"].update(iri=latest_term, resolution="resolved", termStart=latest_start.isoformat())
        elif refs["constituency"].get("mention"):
            mention = refs["constituency"]["mention"]
            raw = fuseki.query(constituency_resolution_query(mention, term, supported_predicates=supported_predicates))
            if len(raw.rows) >= 100:
                raise NLQError("Constituency lookup reached its safety cap; no occurrence was selected.")
            iri, label = resolve_constituency(raw, mention, term_label="the current Dáil")
            refs["constituency"].update(iri=iri, label=label, resolution="resolved")
        query = compile_representation_query(plan, supported_predicates=supported_predicates,
                                             preserve_unlabelled=resolved_member is not None)
        raw = select_pages(query, fuseki=fuseki, supported_predicates=supported_predicates)
        if not raw.rows:
            raise NLQError("No matching representation evidence is available; local absence does not establish a historical negative.")
        if resolved_member is not None:
            required = {"member", "name", "membership", "constituency", "label", "term", "termLabel", "range", "start", "end"}
            if (raw.kind != "select" or not required.issubset(raw.columns)
                    or any(len(row) != len(raw.columns) or not all(isinstance(cell, str) for cell in row) for row in raw.rows)):
                raise NLQError("Relationship-bound representation returned missing or truncated identity/date evidence.")
        records = [dict(zip(raw.columns, row)) for row in raw.rows]
        if resolved_member is not None and any(row.get("member") != resolved_member[0] for row in records):
            raise NLQError("Representation evidence escaped the exact relationship-bound Member identity.")
        if resolved_member is not None and any(row[key] == "—" or not row[key].strip() for row in records for key in ("name", "label", "termLabel")):
            raise NLQError("Relationship-bound representation has missing Member, constituency or term display evidence; no path was silently excluded.")
        latest_start = None
        if latest_recorded:
            latest_start = date.fromisoformat(refs["term"]["termStart"])
            records = [row for row in records if row["term"] == latest_term]
            representation_ids = {row["constituency"] for row in records}
            if records and len(representation_ids) != 1:
                raise NLQError("The latest recorded Member term has conflicting constituency identities.")
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
            base = (row["name"].removesuffix("@en"), row["label"].removesuffix("@en"),
                    row["termLabel"].removesuffix("@en"), row["member"], row["constituency"], row["term"])
            if preserve_membership_evidence:
                _require_local_iri(row["range"], "DateRange")
                base += (row["membership"], row["range"], row["start"],
                         "open-ended" if row["end"] in {"—", ""} else row["end"], as_of.isoformat())
            rows.add((*base[:3], latest_start.isoformat(), *base[3:]) if latest_recorded else base)
        if latest_recorded:
            columns = ("Member", "Constituency", "Dáil term", "Term start", "Member identity", "Constituency identity", "Term identity")
        else:
            columns = ("Member", "Constituency", "Dáil term", "Member identity", "Constituency identity", "Term identity")
        if preserve_membership_evidence:
            columns += ("Membership identity", "Membership date range", "Membership start", "Membership end", "As of")
        result = QueryResult("select", columns, tuple(sorted(rows)), raw_json=raw.raw_json)
        return PlanOutcome("success", plan=plan, sparql=query, result=result,
                           accepted_evidence={"representation": [
                                {key: row[key] for key in ("member", "membership", "constituency", "term")}
                                | {key: row[key].removesuffix("@en") for key in ("name", "label", "termLabel")}
                                | ({key: row[key] for key in ("range", "start", "end")} if current else {})
                                for row in records]},
                           diagnostic=(f"Recorded representation evidence{' at ' + as_of.isoformat() if current else ' in the latest House-dated Dáil term' if latest_recorded else ' across recorded Dáil terms'}. "
                                       "The latest term is selected by exact HouseTerm identity and House-owned start dates; local source completeness is not certified."))
    except (AmbiguousMember, AmbiguousConstituency) as error:
        key = "member" if isinstance(error, AmbiguousMember) else "constituency"
        refs[key].update(resolution="ambiguous", candidates=list(error.candidates))
        return PlanOutcome("ambiguous", plan=plan, candidates=error.candidates, diagnostic=str(error))
    except NLQError as error:
        status = ("validation_failure" if isinstance(error, QueryLimitError) else
                  "not_found" if isinstance(error, IdentityNotFound) else "source_data_unavailable")
        return PlanOutcome(status, plan=plan, sparql=query, diagnostic=str(error))
