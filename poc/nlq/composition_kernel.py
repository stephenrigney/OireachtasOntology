"""Reusable evidence-native bounded composition (not English admission).

Only R/P/K adapters, exact typed conjunction and Member projection live here.
Transport is injected; no network, production routing or oracle dependency.

Extracted from experimental_composition.py at e98296ef2d89a07810c3b0f3f801c99f76636ae7.
That frozen experiment remains unchanged. This module accepts one authoritative
structured request, explicit calendar dates, and bounded full-label resolution.
"""

from dataclasses import dataclass, field
from datetime import date
import json
import re
import unicodedata
from time import perf_counter
from urllib.parse import quote

from rdflib import Literal, URIRef
from rdflib.namespace import RDF, XSD

from .composable_plan import (
    _date_binding, _mapped_member_interval, _require_local_iri,
    _reviewed_predicate_for_qname,
)
from .contract import load_query_contract
from .errors import NLQError
from .safety import validate_sparql


CONTRACT = load_query_contract()
NS = CONTRACT["namespaces"]
GRAPHS = {x["id"]: x["graph"] for x in CONTRACT["graphFamilies"]}
LIMITS = {"selections": 2, "partyHouses": 2, "requests": 8,
          "rows": 100, "witnesses": 100, "timeout": 20}
REQUEST_TIMEOUT = min(LIMITS["timeout"], CONTRACT["localSafety"]["limits"]["fusekiTimeoutSeconds"])


def iri(qname):
    prefix, local = qname.split(":", 1)
    return URIRef(NS[prefix] + local)


def graph(family):
    return URIRef(GRAPHS[family]["iri"])


def term_json(value):
    if isinstance(value, URIRef):
        return {"type": "uri", "value": str(value)}
    if not isinstance(value, Literal):
        raise NLQError("Malformed typed RDF binding.")
    result = {"type": "literal", "value": str(value)}
    if value.datatype:
        result["datatype"] = str(value.datatype)
    if value.language:
        result["xml:lang"] = value.language
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class Fact:
    subject: URIRef
    predicate: URIRef
    object: URIRef | Literal
    graph: URIRef

    def json(self):
        return {k: term_json(getattr(self, k)) for k in ("subject", "predicate", "object", "graph")}


@dataclass(frozen=True)
class Identity:
    kind: str
    value: URIRef


@dataclass(frozen=True)
class Witness:
    role: str
    bindings: tuple[tuple[str, Identity], ...]
    facts: tuple[Fact, ...]
    intervals: tuple[tuple[str, URIRef, URIRef, Literal, Literal | None, URIRef, bool], ...]

    def get(self, key):
        return dict(self.bindings)[key]

    def json(self):
        return {"role": self.role,
                "bindings": {k: {"kind": v.kind, "iri": str(v.value)} for k, v in self.bindings},
                "facts": [f.json() for f in self.facts],
                "intervals": [{"role": role, "resource": str(resource), "range": str(range_),
                               "start": term_json(start), "end": term_json(end) if end else None,
                               "graph": str(owner), "currentAtAsOf": active}
                              for role, resource, range_, start, end, owner, active in self.intervals]}


class SemanticError(NLQError):
    pass


class AmbiguousIdentity(NLQError):
    """Several grounded current resources; no selection is authoritative."""

    def __init__(self, candidates):
        super().__init__("Ambiguous current resource identity; several grounded incarnations match. Clarify the committee or constituency; none was selected.")
        self.candidates = candidates


SIGNATURES = {
    "R": ("current Dáil constituency representation", "constituency",
          ("parliamentaryMembership", "term")),
    "P": ("current party membership", "affiliation",
          ("episode", "containingMembership", "term")),
    "K": ("current committee membership", "committee", ("owner", "term", "membership")),
}
BINDING_TYPES = {
    "Member": "Member", "R.parliamentaryMembership": "ParliamentaryMembership",
    "P.containingMembership": "ParliamentaryMembership", "R.term": "HouseTerm",
    "P.term": "HouseTerm", "K.term": "HouseTerm", "K.membership": "CommitteeMembership",
}


@dataclass(frozen=True)
class Plan:
    selections: tuple[dict, ...]
    equalities: tuple[tuple[str, str], ...]
    shape: str
    scope: str
    semantic: str


def parse_semantics(spec):
    """Check obligations independently of retrieval/executability, not English admission."""
    try:
        required = {"id", "asOf", "requiredSelections", "exactSharedBindings", "currentAtRoles",
                    "answer", "retainAllWitnesses"}
        if set(spec) - {"forbiddenExtraEquality"} != required:
            raise ValueError("Unknown or absent semantic requirement")
        validate_as_of(spec["asOf"])
        selections = spec["requiredSelections"]
        if not 1 <= len(selections) <= LIMITS["selections"]:
            raise ValueError("Relationship selection limit")
        roles = [s["role"] for s in selections]
        if len(set(roles)) != len(roles):
            raise ValueError("Duplicate role")
        obligations = []
        for s in selections:
            role = s["role"]
            relation, parameter, currents = SIGNATURES[role]
            fields = {"role", "relationship", parameter}
            if role in {"R", "P"}:
                fields.add("house" if "house" in s else "houses")
                houses = [s["house"]] if "house" in s else s["houses"]
                if (not houses or len(houses) != len(set(houses)) or len(houses) > 2
                        or set(houses) - {"Dail", "Seanad"} or (role == "R" and houses != ["Dail"])):
                    raise ValueError("Unsupported House scope")
            if set(s) != fields or s["relationship"] != relation:
                raise ValueError("Unsupported primitive requirement")
            target = s[parameter]
            if isinstance(target, dict):
                if (set(target) != {"mention"}
                        or not isinstance(target["mention"], str)
                        or not 1 <= len(target["mention"].strip()) <= 200):
                    raise ValueError("Invalid named resource requirement")
            else:
                _require_local_iri(target, parameter)
            obligations += [f"{role}.{x}" for x in currents]
        if (sorted(spec["currentAtRoles"]) != sorted(obligations)
                or spec["retainAllWitnesses"] is not True):
            raise ValueError("Missing independent current/evidence obligation")
        equalities = []
        if "Member" not in spec["exactSharedBindings"]:
            raise ValueError("Conjunction must bind exact Member")
        for binding in spec["exactSharedBindings"]:
            if binding == "Member":
                continue
            left, right = binding.split("=")
            if (left.split(".")[0] not in roles or right.split(".")[0] not in roles
                    or BINDING_TYPES[left] != BINDING_TYPES[right]):
                raise ValueError("Incompatible exact identity types")
            equalities.append((left, right))
        answer = spec["answer"]
        if (set(answer) != {"shape", "unit", "scope"} or answer["shape"] not in {"list", "count"}
                or answer["unit"] != "distinct Member IRI" or not answer["scope"]
                or (answer["shape"] == "count" and "K" in roles)):
            raise ValueError("Unsupported projection")
        return Plan(tuple(selections), tuple(equalities), answer["shape"], answer["scope"], canonical(spec))
    except (KeyError, TypeError, ValueError, NLQError) as error:
        raise SemanticError(f"Semantic obligation rejected: {error}") from error


def validate_as_of(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("asOf must be an ISO calendar date (YYYY-MM-DD).")
    return date.fromisoformat(value)


@dataclass
class Budget:
    requests: list = field(default_factory=list)
    intermediate: dict = field(default_factory=dict)

    def structure(self, selections, houses):
        if selections > LIMITS["selections"] or houses > LIMITS["partyHouses"]:
            raise NLQError("Whole-plan structural budget exceeded.")

    def request(self, query, timeout):
        if len(self.requests) >= LIMITS["requests"] or not 0 < timeout <= LIMITS["timeout"]:
            raise NLQError("Whole-plan request/timeout budget exceeded.")
        validate_sparql(query, supported_predicates=frozenset(iri(p) for p in CONTRACT["queryableProperties"]))
        record = {"query": query, "timeoutSeconds": timeout}
        self.requests.append(record)
        return record

    def rows(self, rows):
        if len(rows) > LIMITS["rows"]:
            raise NLQError("Raw response row budget exceeded before deduplication.")

    def witnesses(self, rows):
        self.intermediate["joinWitnessTuples"] = len(rows)
        if len(rows) > LIMITS["witnesses"]:
            raise NLQError("Intermediate witness budget exceeded before projection.")


@dataclass(frozen=True)
class Pattern:
    s: str | URIRef
    p: URIRef
    o: str | URIRef
    g: str
    children: tuple = ()

    def text(self):
        def value(x):
            return "?" + x if isinstance(x, str) and not isinstance(x, URIRef) else x.n3()
        return (f"GRAPH ?{self.g} {{ {value(self.s)} {self.p.n3()} {value(self.o)} . }} "
                + " ".join("OPTIONAL { " + c.text() + " }" for c in self.children))

    def flatten(self):
        return (self,) + tuple(p for c in self.children for p in c.flatten())


class Read:
    """Allocate deterministic variables and OPTIONAL facts without unbound fan-out."""
    def __init__(self):
        self.n = 0

    def p(self, s, predicate, o, *children):
        _reviewed_predicate_for_qname(predicate)
        self.n += 1
        return Pattern(s, iri(predicate), o, f"g{self.n}", tuple(children))

    def type(self, s, type_):
        if type_ not in CONTRACT["queryableClasses"]:
            raise NLQError("Unreviewed required class")
        return self.p(s, "rdf:type", iri(type_))

    def interval(self, s, key, *, house=False, committee=False):
        return self.p(s, "dct:temporal" if house else "members:hasCommitteeDateRange" if committee
                      else "members:hasMembershipDateRange", key,
                      self.type(key, "dct:PeriodOfTime" if house else "members:DateRange"),
                      self.p(key, "dcat:startDate" if house else "members:StartDate", key + "Start"),
                      self.p(key, "dcat:endDate" if house else "members:EndDate", key + "End"))


@dataclass(frozen=True)
class Lookup:
    kind: str
    patterns: tuple[Pattern, ...]
    anchor: str
    coverage: dict

    def query(self, offset=0):
        variables = set()
        for p in self.patterns:
            for item in p.flatten():
                variables.add(item.g)
                variables.update(x for x in (item.s, item.o) if type(x) is str)
        # Anchor variables are included in patterns by construction.
        columns = " ".join("?" + x for x in sorted(variables))
        text = f"SELECT DISTINCT {columns} WHERE {{ {self.anchor} "
        text += " ".join("OPTIONAL { " + p.text() + " }" for p in self.patterns)
        text += f" }} ORDER BY {columns} LIMIT 100"
        return text + (f" OFFSET {offset}" if offset else "")


def term_lookup():
    r = Read()
    anchor = (f"GRAPH {graph('houses').n3()} {{ ?term {RDF.type.n3()} ?houseType . }} "
              f"VALUES ?houseType {{ {iri('agents:DailTerm').n3()} {iri('agents:SeanadTerm').n3()} }}")
    return Lookup("terms", (r.type("term", "agents:DailTerm"), r.type("term", "agents:SeanadTerm"),
                           r.p("term", "agents:termOf", "house"), r.interval("term", "period", house=True)),
                  anchor, {"anchor": "terms"})


def owner_lookup(selection, current):
    r = Read()
    role = selection["role"]
    parameter = SIGNATURES[role][1]
    target = selection[parameter]
    family = "constituencies" if role == "R" else "committees"
    if isinstance(target, dict):
        mention = unicodedata.normalize("NFC", target["mention"])
        if role == "K":
            mention = re.sub(r"^the\s+", "", mention, count=1, flags=re.I)
        # PAC is an explicitly reviewed alias in query-service-questions-approved.md,
        # Q30. Other short names must equal a whole source-provided committee core;
        # this is not substring/fuzzy matching, and all matching IRIs survive.
        if role == "K" and mention.casefold() == "pac":
            mention = "Committee of Public Accounts"
        short_committee = role == "K" and not re.match(r"^(?:(?:joint|select)\s+)?committee\b", mention, re.I)
        anchor = "VALUES ?lookupLabel { " + Literal(mention, lang="en").n3() + " } "
    else:
        anchor = (f"GRAPH {graph(family).n3()} {{ {URIRef(target).n3()} {iri('skos:prefLabel').n3()} ?lookupLabel . }} "
                  f"FILTER(LANG(?lookupLabel) = 'en') ")
    anchor += f"GRAPH {graph(family).n3()} {{ ?owner {iri('skos:prefLabel').n3()} ?matchedLabel . "
    if isinstance(target, dict):
        anchor += "FILTER(LANG(?matchedLabel) = 'en') "
    if role == "R":
        anchor += f"?owner {iri('members:constituencyInHouseTerm').n3()} {current['Dail'].n3()} . "
    anchor += "} "
    # Match the existing resolver's source-grounded connector variants, not names
    # assembled from IRIs. Resource identities remain separate after matching.
    if role == "K":
        if isinstance(target, dict) and short_committee:
            anchor += ('FILTER(REPLACE(LCASE(STR(?matchedLabel)), "^(joint |select )?committee (on|of) (the )?", "") = '
                       'LCASE(STR(?lookupLabel)))')
        else:
            anchor += ('FILTER(REPLACE(LCASE(STR(?matchedLabel)), "^committee (on|of) ", "committee ") = '
                       'REPLACE(LCASE(STR(?lookupLabel)), "^committee (on|of) ", "committee "))')
    elif isinstance(target, dict):
        anchor += "FILTER(LCASE(STR(?matchedLabel)) = LCASE(STR(?lookupLabel)))"
    else:
        anchor += "FILTER(STR(?matchedLabel) = STR(?lookupLabel))"
    patterns = [r.p("owner", "skos:prefLabel", "label"),
                r.type("owner", "members:DailConstituency" if role == "R" else "members:Committee"),
                r.p("owner", "members:constituencyInHouseTerm" if role == "R"
                    else "members:committeeInHouseTerm", "term")]
    if role == "R":
        patterns.append(r.type("owner", "members:SeanadPanel"))
    if role == "K":
        patterns.append(r.interval("owner", "ownerRange", committee=True))
    return Lookup("owner", tuple(patterns), anchor, {"anchor": "owner", "role": role, "target": str(target)})


def affiliation_lookup(current, houses):
    """Enumerate term-scoped party identities without filtering to an answer seed."""
    r = Read()
    anchor = ("VALUES ?resolutionTerm { " + " ".join(current[h].n3() for h in sorted(houses)) + " } "
              f"GRAPH {graph('parties').n3()} {{ ?party {RDF.type.n3()} {iri('members:ParliamentaryParty').n3()} ; "
              f"{iri('members:activeDuringTerm').n3()} ?resolutionTerm . }}")
    return Lookup("affiliation", (r.type("party", "members:ParliamentaryParty"),
                  r.p("party", "skos:prefLabel", "partyLabel"),
                  r.p("party", "members:activeDuringTerm", "partyTerm"),
                  r.p("party", "members:hasPoliticalAffiliationIdentity", "affiliation",
                      r.type("affiliation", "members:PoliticalAffiliationIdentity"),
                      r.p("affiliation", "skos:prefLabel", "affiliationLabel"))),
                  anchor, {"anchor": "term-scoped political affiliation", "terms": [str(current[h]) for h in sorted(houses)]})


def resolve_affiliation(facts, rows, mention, as_of):
    # Reuse the reviewed alias register AND exact term-scoped ambiguity policy,
    # rather than globally selecting one of the historical Sinn Féin identities.
    from .composable_plan import _resolve_term_scoped_affiliation, AmbiguousPoliticalAffiliation
    from .results import QueryResult
    records = set()
    for party in {row["party"] for row in rows}:
        e = Evidence(facts, as_of)
        e.local(party)
        e.type(party, "members:ParliamentaryParty", graph("parties"))
        labels = e.values(party, "skos:prefLabel", graph("parties"))
        if any(not isinstance(v, Literal) or not str(v).strip() for v in labels):
            raise NLQError("Malformed party label evidence")
        english = {str(v) for v in labels if v.language == "en"}
        if len(english) > 1:
            raise NLQError("Conflicting English party labels")
        label = next(iter(english), "")
        identities = e.values(party, "members:hasPoliticalAffiliationIdentity", graph("political-affiliations"))
        if len(identities) > 1:
            raise NLQError("Conflicting party affiliation identity links")
        if not identities:
            records.add((str(party), label, "", ""))
        for identity in identities:
            e.local(identity)
            e.type(identity, "members:PoliticalAffiliationIdentity", graph("political-affiliations"))
            labels = e.values(identity, "skos:prefLabel", graph("political-affiliations"))
            if any(not isinstance(v, Literal) or not str(v).strip() for v in labels):
                raise NLQError("Malformed affiliation label evidence")
            preferred = {str(v) for v in labels if v.language == "en"}
            for name in preferred or {""}:
                records.add((str(party), label, str(identity), name))
    try:
        identity, _ = _resolve_term_scoped_affiliation(
            QueryResult("select", ("party", "partyLabel", "affiliation", "affiliationLabel"), tuple(sorted(records))), mention)
        return identity
    except AmbiguousPoliticalAffiliation as error:
        raise AmbiguousIdentity([item["iri"] for item in error.candidates]) from error


def relationship_lookup(selection, *, members=()):
    r = Read()
    role = selection["role"]
    reverse = r.p("member", "members:hasMembersMembership", "relationship",
                  r.type("member", "agents:Member"), r.p("member", "agents:memberCode", "code"))
    # R/K anchor in any named graph; optional reverse links expose orphan records.
    if role in {"R", "K"}:
        # The frozen candidacy certificate reverse-joins in the anchor graph.
        # Descriptive children still audit their subjects across named graphs.
        reverse = Pattern(reverse.s, reverse.p, reverse.o, "anchorGraph", reverse.children)
        target = URIRef(selection[SIGNATURES[role][1]])
        predicate = "members:isRepresentativeFrom" if role == "R" else "members:isCommitteeMembershipOf"
        anchor = f"GRAPH ?anchorGraph {{ ?relationship {iri(predicate).n3()} {target.n3()} . }}"
        patterns = [reverse, r.type("relationship", "members:DailMembership" if role == "R"
                                    else "members:CommitteeMembership"),
                    r.p("relationship", predicate, "target"), r.interval("relationship", "range")]
        if role == "R":
            patterns += [r.p("relationship", "members:inHouseTerm", "term"),
                         r.type("relationship", "members:SeanadMembership")]
        return Lookup(role, tuple(patterns), anchor, {"anchor": role, "target": str(target)})
    # Enumerate Member links before class/party filtering. Independent collections
    # remain visible; a missing PartyMembership type cannot hide a named-party path.
    anchor = ("VALUES ?member { " + " ".join(m.n3() for m in sorted(members)) + " } "
              f"GRAPH ?anchorGraph {{ ?member {iri('members:hasMembersMembership').n3()} ?relationship . }} "
              "FILTER EXISTS { GRAPH ?anchorGraph { "
              f"{{ ?relationship {RDF.type.n3()} {iri('members:PartyMembership').n3()} . }} UNION "
              f"{{ ?relationship {iri('members:isPartyMembershipOf').n3()} ?candidateParty . }} UNION "
              f"{{ ?relationship {iri('members:memberOfCollection').n3()} ?candidateCollection . }} "
              "} }")
    patterns = [reverse, r.type("relationship", "members:PartyMembership"),
                r.p("relationship", "members:memberOfCollection", "collection",
                    r.type("collection", "members:IndependentMemberCollection"),
                    r.type("collection", "members:ParliamentaryParty")),
                r.p("relationship", "members:isPartyMembershipOf", "party",
                    r.type("party", "members:ParliamentaryParty"),
                    r.type("party", "members:IndependentMemberCollection"),
                    r.p("party", "members:activeDuringTerm", "partyTerm"),
                    r.p("party", "members:hasPoliticalAffiliationIdentity", "affiliation",
                        r.type("affiliation", "members:PoliticalAffiliationIdentity"))),
                r.p("relationship", "members:inOireachtasMembership", "pm",
                    r.p("member", "members:hasMembersMembership", "pm"),
                    r.type("pm", "members:DailMembership"), r.type("pm", "members:SeanadMembership"),
                    r.p("pm", "members:inHouseTerm", "term"), r.interval("pm", "pmRange")),
                r.interval("relationship", "range")]
    return Lookup(role, tuple(patterns), anchor, {"anchor": "P", "members": [str(m) for m in sorted(members)]})


class Evidence:
    def __init__(self, facts, as_of):
        self.facts = set(facts)
        self.as_of = as_of
        self.used = set()
        self.intervals = []

    def values(self, subject, predicate, owner):
        found = {f for f in self.facts if f.subject == subject and f.predicate == iri(predicate)}
        if any(f.graph != owner for f in found):
            raise NLQError(f"Wrong owner graph for {subject} {predicate}")
        self.used.update(found)
        return {f.object for f in found}

    def one(self, subject, predicate, owner, optional=False):
        values = self.values(subject, predicate, owner)
        if optional and not values:
            return None
        if len(values) != 1:
            raise NLQError(f"Missing/conflicting resource evidence: {subject} {predicate}")
        return next(iter(values))

    def type(self, subject, type_, owner):
        # Only the exact asserted type is a proof; no subclass inference.
        required = Fact(subject, RDF.type, iri(type_), owner)
        matches = {f for f in self.facts if f.subject == subject and f.predicate == RDF.type
                   and f.object == iri(type_)}
        if matches != {required}:
            raise NLQError(f"Missing/wrong-owner asserted type {type_}: {subject}")
        # Explicit disjointness already defined in ontology/members.owl.ttl;
        # benign generic co-types are not conflicts or inferred type proofs.
        disjoint = {"members:DailMembership": "members:SeanadMembership",
                    "members:SeanadMembership": "members:DailMembership",
                    "members:DailConstituency": "members:SeanadPanel"}.get(type_)
        if disjoint and any(f.subject == subject and f.predicate == RDF.type and f.object == iri(disjoint)
                            for f in self.facts):
            raise NLQError("Conflicting explicitly disjoint resource types")
        self.used.add(required)

    def local(self, value):
        if not isinstance(value, URIRef):
            raise NLQError("Identity is not an RDF IRI")
        _require_local_iri(str(value), "identity")
        return value

    def interval(self, resource, owner, role, *, house=False, committee=False):
        range_ = self.local(self.one(resource, "dct:temporal" if house else
                                     "members:hasCommitteeDateRange" if committee else
                                     "members:hasMembershipDateRange", owner))
        self.type(range_, "dct:PeriodOfTime" if house else "members:DateRange", owner)
        start = self.one(range_, "dcat:startDate" if house else "members:StartDate", owner)
        end = self.one(range_, "dcat:endDate" if house else "members:EndDate", owner, optional=True)
        for value in (start, end):
            if value is not None and (not isinstance(value, Literal) or value.language
                                      or value.datatype not in {XSD.dateTime, XSD.date}):
                raise NLQError("Invalid endpoint RDF datatype")
        def text(value):
            return str(value) + "^^<" + str(value.datatype) + ">" if value is not None else ""
        if house:
            first, last = _date_binding(text(start)), _date_binding(text(end)) if end else None
            if last is not None and last < first:
                raise NLQError("House endpoint order is invalid")
        else:
            first_dt, last_dt = _mapped_member_interval({(str(range_), text(start), text(end))}, label=role)
            first, last = first_dt.date(), last_dt.date() if last_dt else None
        as_of = self.as_of
        active = first <= as_of and (last is None or as_of <= last)
        self.intervals.append((role, resource, range_, start, end, owner, active))
        return active

    def member(self, member):
        self.local(member)
        # Code comes from asserted owner evidence, not an IRI suffix inference.
        codes = {f.object for f in self.facts if f.subject == member and f.predicate == iri("agents:memberCode")}
        if len(codes) != 1 or not isinstance(next(iter(codes)), Literal):
            raise NLQError("Missing/conflicting Member code")
        code = str(next(iter(codes)))
        owner = URIRef(GRAPHS["member-records"]["iriTemplate"].replace("{percent-encoded-memberCode}", quote(code, safe="")))
        self.one(member, "agents:memberCode", owner)
        self.type(member, "agents:Member", owner)
        return owner

    def linked(self, member, membership, owner):
        # Member has many memberships; this edge is not globally functional.
        found = {f for f in self.facts if f.subject == member
                 and f.predicate == iri("members:hasMembersMembership") and f.object == membership}
        expected = Fact(member, iri("members:hasMembersMembership"), membership, owner)
        if found != {expected}:
            raise NLQError("Exact containing membership is not linked from this Member")
        self.used.add(expected)

    def witness(self, role, bindings):
        facts = tuple(sorted(self.used, key=lambda f: canonical(f.json())))
        return Witness(role, tuple(sorted(bindings.items())), facts, tuple(self.intervals))


def retrieve(lookup, transport, budget):
    facts, rows_all = set(), []
    columns = None
    patterns = tuple(p for root in lookup.patterns for p in root.flatten())
    for offset in range(0, 10001, 100):
        query = lookup.query(offset)
        timeout = min(transport.timeout, REQUEST_TIMEOUT)
        entry = budget.request(query, timeout)
        entry.update({"kind": lookup.kind, "coverage": lookup.coverage, "offset": offset})
        try:
            started = perf_counter()
            response = transport.select(lookup, query, offset)
            entry["elapsedSeconds"] = perf_counter() - started
            if entry["elapsedSeconds"] > timeout:
                raise TimeoutError("Required SELECT exceeded its configured timeout")
            entry.update(response)
            rows = response["rows"]
            budget.rows(rows)
            if response.get("complete") is not True:
                raise NLQError("Incomplete required enumeration")
            if columns is not None and columns != response["columns"]:
                raise NLQError("Pagination columns changed")
            columns = response["columns"]
            anchors = {"terms": ("term",), "owner": ("owner",), "affiliation": ("party",), "display": ("member",), "P": ("member", "relationship")}.get(
                lookup.kind, ("relationship",))
            if not set(anchors) <= set(columns):
                raise NLQError("Required SELECT anchor columns are absent")
            for row in rows:
                if not isinstance(row, dict) or set(row) - set(columns):
                    raise NLQError("Malformed SELECT row")
                for value in row.values():
                    term_json(value)
                if any(not isinstance(row.get(key), URIRef) for key in anchors):
                    raise NLQError("Missing or malformed typed candidacy anchor")
                for p in patterns:
                    s = row.get(p.s) if type(p.s) is str else p.s
                    o = row.get(p.o) if type(p.o) is str else p.o
                    g = row.get(p.g)
                    if g is not None:
                        # A pinned reverse OPTIONAL shares the already-bound
                        # anchor graph; that graph alone is not a fact-presence
                        # witness when its Member endpoint is legitimately absent.
                        if p.g == "anchorGraph" and (s is None or o is None):
                            continue
                        if not isinstance(s, URIRef) or not isinstance(g, URIRef) or o is None:
                            raise NLQError("Truncated typed fact")
                        facts.add(Fact(s, p.p, o, g))
            rows_all += rows
            if len(rows) < 100:
                return facts, rows_all
        except (KeyError, TypeError, ValueError, TimeoutError, NLQError) as error:
            entry["elapsedSeconds"] = perf_counter() - started
            entry["error"] = str(error)
            if isinstance(error, NLQError):
                raise
            raise NLQError(f"Required SELECT failed: {error}") from error
    raise NLQError("Pagination exhausted")


def resolve_terms(facts, rows, houses, as_of):
    result, current = {}, {}
    for resource in sorted({r["term"] for r in rows}):
        e = Evidence(facts, as_of)
        e.local(resource)
        types = [h for h in ("Dail", "Seanad") if
                 any(f.subject == resource and f.predicate == RDF.type and f.object == iri("agents:" + h + "Term")
                     for f in facts)]
        if len(types) != 1:
            raise NLQError("Conflicting HouseTerm type")
        house = types[0]
        e.type(resource, "agents:" + house + "Term", graph("houses"))
        house_owner = e.local(e.one(resource, "agents:termOf", graph("houses")))
        if house_owner != URIRef("https://data.oireachtas.ie/house/" + house.lower()):
            raise NLQError("HouseTerm has the wrong persistent House owner")
        active = e.interval(resource, graph("houses"), "term", house=True)
        result[resource] = (house, active, e)
        if active:
            current.setdefault(house, []).append(resource)
    for house in houses:
        if len(current.get(house, [])) != 1:
            raise NLQError("No unique independently current " + house + " term")
    return result, {h: current[h][0] for h in houses}


def resolve_owner(selection, facts, rows, terms, current, as_of):
    role = selection["role"]
    target = selection[SIGNATURES[role][1]]
    matches = []
    for owner in sorted({r["owner"] for r in rows}):
        e = Evidence(facts, as_of)
        e.local(owner)
        family = "constituencies" if role == "R" else "committees"
        owner_graph = graph(family)
        e.type(owner, "members:DailConstituency" if role == "R" else "members:Committee", owner_graph)
        e.values(owner, "skos:prefLabel", owner_graph)
        term = e.local(e.one(owner, "members:constituencyInHouseTerm" if role == "R"
                            else "members:committeeInHouseTerm", owner_graph))
        if term not in terms:
            raise NLQError("Uncovered owner HouseTerm")
        active = terms[term][1]
        if role == "K":
            active = e.interval(owner, owner_graph, "owner", committee=True) and active
        else:
            active = active and term == current["Dail"]
        e.used.update(terms[term][2].used)
        e.intervals.extend(terms[term][2].intervals)
        if active:
            matches.append((owner, term, e))
    if len(matches) > 1:
        raise AmbiguousIdentity([str(m[0]) for m in matches])
    if not matches or (not isinstance(target, dict) and matches[0][0] != URIRef(target)):
        raise NLQError("No unique accepted current resource identity at asOf; no committee or constituency was guessed.")
    return matches[0]


def primitive(selection, facts, rows, terms, current, owner=None, *, as_of):
    """One resource-validation pipeline; role-specific RDF contracts remain local."""
    role = selection["role"]
    all_witnesses, qualifying = [], []
    for relationship in sorted({r["relationship"] for r in rows}):
        e = Evidence(facts, as_of)
        if role == "P":
            party_facts = [f for f in facts if f.subject == relationship and
                           (f.predicate == iri("members:isPartyMembershipOf") or
                            (f.predicate == RDF.type and f.object == iri("members:PartyMembership")))]
            if not party_facts:
                # Direct nonparty records are visible, not promoted to party episodes.
                collections = {f.object for f in facts if f.subject == relationship
                               and f.predicate == iri("members:memberOfCollection")}
                if collections:
                    if len(collections) != 1:
                        raise NLQError("Conflicting nonparty collection targets")
                    e.type(next(iter(collections)), "members:IndependentMemberCollection", graph("parties"))
                continue
        members = {f.subject for f in facts if f.predicate == iri("members:hasMembersMembership")
                   and f.object == relationship}
        if len(members) != 1:
            raise NLQError("Missing/conflicting reverse Member identity")
        member = next(iter(members))
        mg = e.member(member)
        e.linked(member, relationship, mg)
        e.type(relationship, "members:" + {"R": "DailMembership", "K": "CommitteeMembership", "P": "PartyMembership"}[role], mg)
        active = e.interval(relationship, mg, "membership" if role == "K" else "parliamentaryMembership" if role == "R" else "episode")
        bindings = {"Member": Identity("Member", member)}
        if role in {"R", "K"}:
            resolved, term, oe = owner
            target = e.local(e.one(relationship, "members:isRepresentativeFrom" if role == "R"
                                  else "members:isCommitteeMembershipOf", mg))
            if target != resolved:
                raise NLQError("Conflicting relationship target")
            e.used.update(oe.used)
            e.intervals.extend(oe.intervals)
            if role == "R" and e.one(relationship, "members:inHouseTerm", mg) != term:
                raise NLQError("Representation occurrence/membership term mismatch")
            bindings.update({"parliamentaryMembership" if role == "R" else "membership":
                             Identity("ParliamentaryMembership" if role == "R" else "CommitteeMembership", relationship),
                             "term": Identity("HouseTerm", term),
                             "constituency" if role == "R" else "committee":
                             Identity("DailConstituency" if role == "R" else "Committee", target)})
        else:
            pm = e.local(e.one(relationship, "members:inOireachtasMembership", mg))
            e.linked(member, pm, mg)
            term = e.local(e.one(pm, "members:inHouseTerm", mg))
            if term not in terms:
                raise NLQError("Uncovered party membership HouseTerm")
            house, term_active, te = terms[term]
            e.type(pm, "members:" + house + "Membership", mg)
            pm_active = e.interval(pm, mg, "containingMembership")
            party = e.local(e.one(relationship, "members:isPartyMembershipOf", mg))
            e.type(party, "members:ParliamentaryParty", graph("parties"))
            if e.one(party, "members:activeDuringTerm", graph("parties")) != term:
                raise NLQError("Party occurrence/containing membership term mismatch")
            affiliation = e.local(e.one(party, "members:hasPoliticalAffiliationIdentity", graph("political-affiliations")))
            e.type(affiliation, "members:PoliticalAffiliationIdentity", graph("political-affiliations"))
            e.used.update(te.used)
            e.intervals.extend(te.intervals)
            houses = [selection["house"]] if "house" in selection else selection["houses"]
            active = (active and pm_active and term_active and house in houses and current.get(house) == term
                      and affiliation == URIRef(selection["affiliation"]))
            bindings.update({"containingMembership": Identity("ParliamentaryMembership", pm),
                             "term": Identity("HouseTerm", term), "episode": Identity("PartyMembership", relationship),
                             "party": Identity("ParliamentaryParty", party),
                             "affiliation": Identity("PoliticalAffiliationIdentity", affiliation)})
        w = e.witness(role, bindings)
        all_witnesses.append(w)
        if active:
            qualifying.append(w)
    return all_witnesses, qualifying


def bind(selections, equalities, budget):
    """Typed exact equality, independent of any relationship topology."""
    tuples = [()]
    for witnesses in selections:
        joined = []
        for prefix in tuples:
            for witness in witnesses:
                candidate = prefix + (witness,)
                if prefix and prefix[0].get("Member") != witness.get("Member"):
                    continue
                by_role = {w.role: w for w in candidate}
                valid = True
                for left, right in equalities:
                    lr, lf = left.split(".")
                    rr, rf = right.split(".")
                    if lr in by_role and rr in by_role:
                        a, b = by_role[lr].get(lf), by_role[rr].get(rf)
                        if a.kind != b.kind:
                            raise NLQError("Incompatible binding identity types")
                        valid = valid and a == b
                if valid:
                    joined.append(candidate)
                    budget.witnesses(joined)
        tuples = joined
        budget.intermediate.setdefault("bindingStages", []).append(len(tuples))
    budget.witnesses(tuples)
    return tuples


def project(plan, tuples):
    if not tuples:
        raise NLQError("No qualifying recorded evidence; not a factual zero/empty selection.")
    members = sorted({str(ws[0].get("Member").value) for ws in tuples})
    witnesses = sorted(([w.json() for w in ws] for ws in tuples), key=canonical)
    as_of = json.loads(plan.semantic)["asOf"]
    output = {"asOf": as_of, "shape": plan.shape, "unit": "distinct Member IRI",
              "scope": plan.scope, "members": members, "witnesses": witnesses}
    if plan.shape == "count":
        output["distinctCount"] = len(members)
    output["rendered"] = (f"{len(members)} distinct Member IRI(s) recorded in this evidence as of {as_of}."
                          if plan.shape == "count" else "\n".join(members) + f"\nRecorded evidence as of {as_of}; not a complete real-world roster.")
    return output


def execute(request, transport, *, budget=None):
    budget = budget if budget is not None else Budget()
    report = {"status": "nonanswer", "ledger": budget.requests, "intermediate": budget.intermediate}
    try:
        # The caller supplies ONE authoritative structured request. Natural-language
        # interpretation and explicit confirmation are outside this executor.
        plan = parse_semantics(request)
        as_of = validate_as_of(request["asOf"])
        houses = set()
        for s in plan.selections:
            houses.update([s["house"]] if "house" in s else s.get("houses", []))
        party_houses = max((len(s.get("houses", [s.get("house")])) for s in plan.selections
                            if s["role"] == "P"), default=0)
        report["structure"] = {"relationshipSelections": len(plan.selections), "partyHouseVariants": party_houses}
        budget.structure(len(plan.selections), party_houses)
        facts, rows = retrieve(term_lookup(), transport, budget)
        terms, current = resolve_terms(facts, rows, houses, as_of)
        selections = {}
        audited = {}
        # Retrieval dependencies are primitive-level, not combination-specific.
        ordered = sorted(plan.selections, key=lambda s: (s["role"] == "P", s["role"]))
        report["resolvedSelections"] = []
        for original_selection in ordered:
            s = dict(original_selection)
            owner = None
            if s["role"] in {"R", "K"}:
                facts, rows = retrieve(owner_lookup(s, current), transport, budget)
                owner = resolve_owner(s, facts, rows, terms, current, as_of)
                s[SIGNATURES[s["role"]][1]] = str(owner[0])
            if s["role"] == "P" and isinstance(s["affiliation"], dict):
                party_scope = [s["house"]] if "house" in s else s["houses"]
                facts, rows = retrieve(affiliation_lookup(current, party_scope), transport, budget)
                s["affiliation"] = resolve_affiliation(facts, rows, s["affiliation"]["mention"], as_of)
            report["resolvedSelections"].append(s)
            members = {w.get("Member").value for ws in audited.values() for w in ws}
            if s["role"] == "P" and not members:
                raise NLQError("Party primitive requires a bounded evidenced Member seed")
            facts, rows = retrieve(relationship_lookup(s, members=members), transport, budget)
            all_, selected = primitive(s, facts, rows, terms, current, owner, as_of=as_of)
            budget.intermediate[s["role"]] = {"validated": len(all_), "currentSelected": len(selected)}
            if max(len(all_), len(selected)) > LIMITS["witnesses"]:
                raise NLQError("Primitive intermediate witness budget exceeded before joining/projection")
            audited[s["role"]], selections[s["role"]] = all_, selected
        report["validatedWitnesses"] = {k: [w.json() for w in v] for k, v in sorted(audited.items())}
        tuples = bind([selections[s["role"]] for s in plan.selections], plan.equalities, budget)
        report["answer"] = project(plan, tuples)
        report["status"] = "answer"
    except AmbiguousIdentity as error:
        report.update(status="ambiguous", error=str(error), candidates=error.candidates)
    except SemanticError as error:
        report.update(status="semantic_rejection", error=str(error))
    except NLQError as error:
        report["error"] = str(error)
    return report
