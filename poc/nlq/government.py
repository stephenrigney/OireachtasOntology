"""Constitutional Government membership joined to contemporaneous party evidence."""

from datetime import date
import re

from rdflib import Literal, URIRef

from .composable_plan import (
    NLQError, PlanError, PlanOutcome, _PREFIXES, _date_binding,
    _display_member_interval, _interval_overlap, _mapped_member_interval, _pattern_predicate, _pattern_rdf_type, _query, _require_local_iri,
    _reviewed_pattern, _reviewed_predicate,
)
from .contract import load_query_contract
from .member_resolution import _normalise_text
from .pagination import select_pages
from .results import QueryResult


EDGES = {
    "member_has_cabinet_membership": ("member", "cabinet"),
    "cabinet_membership_of_government": ("cabinet", "government"),
    "member_party_membership": ("member", "episode"),
    "episode_in_parliamentary_party": ("episode", "party"),
    "parliamentary_party_has_affiliation_identity": ("party", "affiliation"),
}
TYPES = {"member": "Member", "cabinet": "CabinetMembership", "government": "Government",
         "episode": "PartyMembershipEpisode", "party": "ParliamentaryParty",
         "affiliation": "PoliticalAffiliationIdentity"}


def government_plan(mention, *, as_of):
    refs = {key: {"type": value} for key, value in TYPES.items()}
    refs["member"]["answer"] = True
    refs["affiliation"].update(mention=mention, resolution="unresolved")
    return {"version": 2, "asOf": as_of.isoformat(), "family": "government_party_members",
            "referents": refs,
            "relations": [{"id": fact, "fact": fact, "from": source, "to": target}
                          for fact, (source, target) in EDGES.items()],
            "constraints": [{"referent": key, "field": "interval", "operator": "on", "value": as_of.isoformat()}
                            for key in ("cabinet", "episode")],
            "answer": {"kind": "entities", "referent": "member", "distinctBy": "identity", "display": ["name"],
                       "details": [{"referent": "affiliation", "display": ["label"]},
                                   {"referent": "cabinet", "display": ["start", "end"]},
                                   {"referent": "episode", "display": ["start", "end"]}], "preserveEvidence": True}}


def plan_government_question(question, *, as_of):
    match = re.fullmatch(
        r"(?:who are|list|name) (?:the )?(?:current )?(?P<party>.+?) "
        r"(?:[Mm]embers of (?:the )?(?:current |constitutional )?[Gg]overnment|[Gg]overnment [Mm]embers)[?.!]*",
        question.strip(), re.I)
    if not match:
        match = re.fullmatch(
            r"which (?P<party>.+?) (?:members|politicians) are (?:in|members of) (?:the )?(?:current )?government[?.!]*",
            question.strip(), re.I)
    if match:
        return government_plan(match["party"].strip(), as_of=as_of)
    return None


def validate_government_plan(plan):
    refs = plan["referents"]
    if set(refs) != set(TYPES):
        raise PlanError("Government membership requires the complete Cabinet and party-affiliation paths.")
    mention = refs["affiliation"].get("mention")
    if not isinstance(mention, str) or not mention.strip():
        raise PlanError("An exact party-affiliation mention is required.")
    expected = government_plan(mention, as_of=date.fromisoformat(plan["asOf"]))
    if set(plan) != set(expected):
        raise PlanError("Unsupported Government plan fields.")
    for key, ref in refs.items():
        semantic = {k: v for k, v in ref.items() if k not in {"resolution", "iri", "label", "candidates"}}
        expected_semantic = {k: v for k, v in expected["referents"][key].items() if k != "resolution"}
        if semantic != expected_semantic or (key != "affiliation" and set(ref) != set(semantic)):
            raise PlanError("Government referents cannot add or drop identity/relationship conditions.")
        if "iri" in ref:
            _require_local_iri(ref["iri"], key)
    if plan["relations"] != expected["relations"] or plan["constraints"] != expected["constraints"] or plan["answer"] != expected["answer"]:
        raise PlanError("Government plans must preserve every Cabinet/party relationship, reference-date constraint and evidence projection.")
    return plan


def _graphs():
    return {item["id"]: item["graph"] for item in load_query_contract()["graphFamilies"]}


def affiliation_lookup_query(mention, *, supported_predicates):
    return _query(_PREFIXES + f'''SELECT DISTINCT ?identity ?label WHERE {{
  GRAPH <{_graphs()['political-affiliations']['iri']}> {{
    ?identity a members:PoliticalAffiliationIdentity ; skos:prefLabel ?label .
    FILTER(LANG(?label) = "en")
    FILTER(LCASE(STR(?label)) = LCASE(STR({Literal(mention).n3()})))
  }}
}} ORDER BY ?identity ?label LIMIT 100''', supported_predicates)


def compile_government_query(plan, *, supported_predicates):
    validate_government_plan(plan)
    affiliation = URIRef(_require_local_iri(plan["referents"]["affiliation"].get("iri"), "PoliticalAffiliationIdentity")).n3()
    graphs = _graphs()
    pattern = _reviewed_pattern("derived-cabinet-membership", "member-records")
    joins = {fact: _reviewed_predicate(fact) for fact in EDGES}
    targets = [triple[2] for triple in pattern["triples"]
               if triple[:2] == ["?cabinet", joins["cabinet_membership_of_government"]]]
    if len(targets) != 1 or not targets[0].startswith("<") or not targets[0].endswith(">"):
        raise PlanError("The Cabinet pattern must reference one fixed constitutional Government IRI.")
    target = _require_local_iri(targets[0][1:-1], "Government")
    if _pattern_predicate(pattern, "?member", "?cabinet") != joins["member_has_cabinet_membership"]:
        raise PlanError("The Cabinet relationship disagrees with the emitted Member pattern.")
    cabinet_type = _pattern_rdf_type(pattern, "?cabinet")
    role_type = _pattern_rdf_type(pattern, "?role")
    role_link = _pattern_predicate(pattern, "?cabinet", "?role")
    support_link = _pattern_predicate(pattern, "?cabinet", "?holding")
    return _query(_PREFIXES + f'''SELECT DISTINCT ?member ?name ?cabinet ?cabinetRange ?cabinetStart ?cabinetEnd
  ?episode ?partyRange ?partyStart ?partyEnd ?membership ?membershipRange ?membershipStart ?membershipEnd
  ?term ?termType ?termStart ?termEnd ?holding WHERE {{
  GRAPH ?memberGraph {{
    ?member a agents:Member ; foaf:name ?name ; {joins['member_has_cabinet_membership']} ?cabinet .
    ?cabinet a {cabinet_type} ; {joins['cabinet_membership_of_government']} <{target}> ; {role_link} ?role .
    ?role a {role_type} .
    OPTIONAL {{ ?cabinet {support_link} ?holding . }}
    OPTIONAL {{ ?cabinet members:hasMembershipDateRange ?cabinetRange .
      OPTIONAL {{ ?cabinetRange members:StartDate ?cabinetStart . }} OPTIONAL {{ ?cabinetRange members:EndDate ?cabinetEnd . }} }}
    ?member {joins['member_party_membership']} ?episode .
    ?episode a members:PartyMembership ; {joins['episode_in_parliamentary_party']} ?party ; members:inOireachtasMembership ?membership .
    ?membership a members:OireachtasMembership ; members:inHouseTerm ?term .
    OPTIONAL {{ ?episode members:hasMembershipDateRange ?partyRange .
      OPTIONAL {{ ?partyRange members:StartDate ?partyStart . }} OPTIONAL {{ ?partyRange members:EndDate ?partyEnd . }} }}
    OPTIONAL {{ ?membership members:hasMembershipDateRange ?membershipRange .
      OPTIONAL {{ ?membershipRange members:StartDate ?membershipStart . }} OPTIONAL {{ ?membershipRange members:EndDate ?membershipEnd . }} }}
  }}
  FILTER(STRSTARTS(STR(?memberGraph), "{graphs['member-records']['iriTemplate'].split('{')[0]}"))
  GRAPH <{graphs['parties']['iri']}> {{ ?party a members:ParliamentaryParty ; members:activeDuringTerm ?term . }}
  GRAPH <{graphs['political-affiliations']['iri']}> {{ ?party {joins['parliamentary_party_has_affiliation_identity']} {affiliation} . }}
  GRAPH <{graphs['houses']['iri']}> {{
    ?term a ?termType .
    OPTIONAL {{ ?term dct:temporal ?period .
      OPTIONAL {{ ?period dcat:startDate ?termStart . }} OPTIONAL {{ ?period dcat:endDate ?termEnd . }} }}
  }}
  VALUES ?termType {{ agents:DailTerm agents:SeanadTerm }}
}} ORDER BY ?member ?cabinet ?episode ?membership ?term ?termType ?name ?cabinetRange ?cabinetStart ?cabinetEnd ?partyRange ?partyStart ?partyEnd ?membershipRange ?membershipStart ?membershipEnd ?termStart ?termEnd ?holding LIMIT 100''', supported_predicates)


def _intervals(records, identity, prefix):
    values = {}
    for row in records:
        values.setdefault(row[identity], set()).add(tuple(row[prefix + part] for part in ("Range", "Start", "End")))
    return {key: _mapped_member_interval(value, label=identity) for key, value in values.items()}


def _active(interval, as_of):
    start, end = interval
    return start.date() <= as_of and (end is None or as_of <= end.date())


def execute_government(plan, *, fuseki, supported_predicates):
    ref = plan["referents"]["affiliation"]
    as_of = date.fromisoformat(plan["asOf"])
    query = None
    try:
        raw = fuseki.query(affiliation_lookup_query(ref["mention"], supported_predicates=supported_predicates))
        if raw.kind != "select" or raw.columns != ("identity", "label") or len(raw.rows) >= 100:
            raise NLQError("The bounded local political-affiliation identity lookup is incomplete.")
        candidates = {iri: label.removesuffix("@en") for iri, label in raw.rows
                      if _normalise_text(label.removesuffix("@en")) == _normalise_text(ref["mention"])}
        if len(candidates) != 1:
            status = "ambiguous" if candidates else "not_found"
            matches = tuple({"iri": iri, "label": label} for iri, label in sorted(candidates.items()))
            ref.update(resolution=status, candidates=list(matches))
            return PlanOutcome(status, plan=plan, candidates=matches, diagnostic="The party mention does not resolve to exactly one reviewed local affiliation identity; no roster was queried.")
        iri, label = next(iter(candidates.items()))
        ref.update(iri=_require_local_iri(iri, "PoliticalAffiliationIdentity"), label=label, resolution="resolved")
        query = compile_government_query(plan, supported_predicates=supported_predicates)
        raw = select_pages(query, fuseki=fuseki, supported_predicates=supported_predicates)
        records = [dict(zip(raw.columns, row)) for row in raw.rows]
        cabinets = _intervals(records, "cabinet", "cabinet")
        records = [row for row in records if _active(cabinets[row["cabinet"]], as_of)]
        parties = _intervals(records, "episode", "party")
        records = [row for row in records if _active(parties[row["episode"]], as_of)]
        memberships = _intervals(records, "membership", "membership")
        records = [row for row in records if _active(memberships[row["membership"]], as_of)]
        contemporaneous = []
        for row in records:
            overlap = _interval_overlap(cabinets[row["cabinet"]], parties[row["episode"]])
            if overlap is not None:
                overlap = _interval_overlap(overlap, memberships[row["membership"]])
            if overlap is not None and _active(overlap, as_of):
                contemporaneous.append(row)
        records = contemporaneous
        term_dates = {}
        for row in records:
            term_dates.setdefault(row["term"], set()).add((row["termStart"], row["termEnd"]))
        active_terms = set()
        for term, values in term_dates.items():
            if len(values) != 1:
                raise NLQError("Conflicting containing HouseTerm date evidence; current party affiliation is uncertain.")
            start_text, end_text = next(iter(values))
            start = _date_binding(start_text)
            end = None if end_text in {"—", ""} else _date_binding(end_text)
            if end is not None and end < start:
                raise NLQError("Invalid containing HouseTerm interval.")
            if start <= as_of and (end is None or as_of <= end):
                active_terms.add(term)
        records = [row for row in records if row["term"] in active_terms]
        if not records:
            raise NLQError("No contemporaneous CabinetMembership and party-affiliation evidence is available at the reference date. Incomplete current-office/party coverage cannot establish an empty or complete Government roster.")
        names = {}
        evidence = {}
        for row in records:
            for key in ("member", "cabinet", "episode", "membership", "term"):
                _require_local_iri(row[key], key)
            name = row["name"].removesuffix("@en")
            if name in {"—", ""}:
                raise NLQError("A Government match has no readable Member name.")
            names.setdefault(row["member"], set()).add(name)
            item = evidence.setdefault(row["member"], {"cabinets": set(), "parties": set(), "holdings": set()})
            item["cabinets"].add((row["cabinet"], _display_member_interval(cabinets[row["cabinet"]])))
            item["parties"].add((row["episode"], _display_member_interval(parties[row["episode"]])))
            if row["holding"] not in {"—", ""}:
                item["holdings"].add(_require_local_iri(row["holding"], "OfficeHolding"))
        if any(len(values) != 1 for values in names.values()):
            raise NLQError("Conflicting Member names in Government evidence; no identity was merged.")
        rows = []
        for member, item in evidence.items():
            cabinet_evidence, party_evidence = sorted(item["cabinets"]), sorted(item["parties"])
            rows.append((next(iter(names[member])), label,
                         "; ".join(interval for _iri, interval in cabinet_evidence),
                         "; ".join(interval for _iri, interval in party_evidence), member,
                         "; ".join(iri for iri, _interval in cabinet_evidence),
                         "; ".join(iri for iri, _interval in party_evidence),
                         "; ".join(sorted(item["holdings"])) or "Not recorded"))
        result = QueryResult("select", ("Member", "Political affiliation", "Government membership", "Party membership",
                                        "Member identity", "Cabinet membership identity", "Party episode identity", "Supporting office holding"),
                             tuple(sorted(rows)), raw.raw_json)
        return PlanOutcome("success", plan=plan, sparql=query, result=result,
                           diagnostic=f"Recorded constitutional Government members affiliated with {label} at {as_of.isoformat()}. Current-office and party coverage is not certified complete: this is not a complete Government roster. Minister-of-State-only holdings do not qualify.")
    except (NLQError, PlanError) as error:
        return PlanOutcome("source_data_unavailable", plan=plan, sparql=query, diagnostic=str(error))
