"""Deterministic, member-owned membership graph transformation."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import unquote, urlsplit

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF, SKOS, XSD

from .common import MEMBERS, OIR, datetime_literal, iri, string

HOUSES = {"dail": URIRef("https://data.oireachtas.ie/house/dail"), "seanad": URIRef("https://data.oireachtas.ie/house/seanad")}
MEMBERSHIP_TYPES = {"dail": MEMBERS.DailMembership, "seanad": MEMBERS.SeanadMembership}
COMMITTEE_ROLES = {"Chair": MEMBERS.Chair, "Deputy Chair": MEMBERS.DeputyChair}
HOUSE_TERM_RE = re.compile(r"^https://data\.oireachtas\.ie/ie/oireachtas/house/(dail|seanad)/([1-9][0-9]*)$")
FUTURE_COMMITTEE_FIELDS = {
    "committeeDateRange": "committee operational lifespan is deferred pending a Committee owner",
    "committeeName": "time-bounded committee names are deferred pending a Committee owner",
    "expiryType": "committee expiry type is deferred pending a Committee owner",
    "mainStatus": "committee lifecycle status is deferred pending a Committee owner",
    "status": "committee lifecycle status is deferred pending a Committee owner",
    "serviceUnit": "committee service unit is deferred pending a Committee owner",
}
OWNERSHIP_DEFERRED_FIELDS = {"committeeCode": "Committee descriptions are owned by a future Committee endpoint", "committeeID": "Committee descriptions are owned by a future Committee endpoint", "committeeType": "Committee descriptions are owned by a future Committee endpoint"}
UNORDERED_ARRAY_PATHS = {
    ("memberships",), ("memberships", "membership", "represents"), ("memberships", "membership", "parties"),
    ("memberships", "membership", "committees"), ("memberships", "membership", "offices"),
    ("memberships", "membership", "committees", "role"), ("memberships", "membership", "committees", "committeeType"), ("memberships", "membership", "committees", "committeeName"),
}


def _normalise(value, *, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        return {name: _normalise(value[name], path=path + (name,)) for name in sorted(value)}
    if isinstance(value, list):
        normal = [_normalise(item, path=path) for item in value]
        return sorted(normal, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) if path in UNORDERED_ARRAY_PATHS else normal
    return value


def canonical_json(value: object) -> bytes:
    return json.dumps(_normalise(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def source_hash(member: dict) -> str:
    return hashlib.sha256(canonical_json(member)).hexdigest()


def _generated(parent: URIRef, kind: str, identity: object) -> URIRef:
    digest = hashlib.sha256(canonical_json(identity)).hexdigest()
    return URIRef(f"{parent}#{kind}-{digest}")


def _source_iri(value: object, *, label: str) -> URIRef:
    subject = iri(value); parsed = urlsplit(str(subject))
    if parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie" or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    return subject


def _date_range(graph: Graph, parent: URIRef, fragment: str, value: object) -> URIRef:
    if not isinstance(value, dict) or value.get("start") is None:
        raise ValueError("membership dateRange.start is required")
    subject = URIRef(f"{parent}#{fragment}")
    start = datetime_literal(value["start"])
    graph.add((subject, RDF.type, MEMBERS.DateRange))
    graph.add((subject, MEMBERS.StartDate, start))
    if value.get("end") is not None:
        end = datetime_literal(value["end"])
        if end.toPython() < start.toPython():
            raise ValueError("reverse membership date range")
        graph.add((subject, MEMBERS.EndDate, end))
    graph.add((parent, MEMBERS.hasMembershipDateRange, subject))
    return subject


def member_graph_iri(member: dict) -> str:
    from urllib.parse import quote
    code = member.get("memberCode")
    subject = _source_iri(member.get("uri"), label="member.uri")
    path = [part for part in urlsplit(str(subject)).path.split("/") if part]
    if not isinstance(code, str) or not code or len(path) != 5 or path[:4] != ["ie", "oireachtas", "member", "id"] or unquote(path[-1]) != code:
        raise ValueError("memberCode must match the final member.uri path segment")
    return "https://data.oireachtas.ie/graph/member/" + quote(code, safe="")


def _member_identity(member: dict) -> URIRef:
    member_graph_iri(member)  # also validates source identity invariant
    return _source_iri(member["uri"], label="member.uri")


def _house_term_iri(house: object) -> URIRef:
    if not isinstance(house, dict): raise ValueError("house must be an object")
    code, number = house.get("houseCode"), house.get("houseNo")
    term = _source_iri(house.get("uri"), label="house.uri"); match = HOUSE_TERM_RE.fullmatch(str(term))
    if code not in HOUSES or not match or match.group(1) != code or match.group(2) != str(number):
        raise ValueError("house.uri must be the direct IRI for its houseCode and houseNo")
    return term


def _reference_representation(record: dict, term: URIRef, house_code: str) -> URIRef:
    kind = record.get("representType")
    if kind not in {"constituency", "panel"}:
        raise ValueError(f"unsupported representType: {kind!r}")
    expected = "dail" if kind == "constituency" else "seanad"
    if expected != house_code:
        raise ValueError("representation type is incompatible with membership house")
    subject = _source_iri(record.get("uri"), label="representation.uri"); term_path = [part for part in urlsplit(str(term)).path.split("/") if part]
    path = [part for part in urlsplit(str(subject)).path.split("/") if part]
    code = record.get("representCode")
    if not isinstance(code, str) or len(path) != 7 or path[:5] != term_path or path[5] != kind or unquote(path[6]) != code:
        raise ValueError("representation.uri must match membership HouseTerm, representType and representCode")
    return subject


def _party(graph: Graph, member: URIRef, membership: URIRef, value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("party wrapper must contain a party object")
    party = value.get("party")
    if not isinstance(party, dict):
        raise ValueError("party wrapper must contain a party object")
    code = party.get("partyCode")
    if not isinstance(code, str) or not code:
        raise ValueError("party.partyCode must be a non-empty string")
    party_iri = _source_iri(party.get("uri"), label="party.uri"); membership_path = [part for part in urlsplit(str(membership)).path.split("/") if part]
    party_path = [part for part in urlsplit(str(party_iri)).path.split("/") if part]
    if len(membership_path) != 8 or len(party_path) != 6 or party_path[:3] != ["ie", "oireachtas", "party"] or party_path[3:5] != membership_path[6:8] or unquote(party_path[5]) != code:
        raise ValueError("party.uri must be the term-scoped Party source IRI")
    identity = {"membership": str(membership), "party": party_iri, "dateRange": party.get("dateRange")}
    subject = _generated(membership, "party-membership", identity)
    graph.add((subject, RDF.type, MEMBERS.ParliamentaryCollectionMembership))
    graph.add((member, MEMBERS.hasMembersMembership, subject))
    graph.add((subject, MEMBERS.inOireachtasMembership, membership))
    graph.add((subject, MEMBERS.memberOfCollection, party_iri))
    if code != "Independent":
        graph.add((subject, RDF.type, MEMBERS.PartyMembership))
        graph.add((subject, MEMBERS.isPartyMembershipOf, party_iri))
    _date_range(graph, subject, "date-range", party.get("dateRange"))


def _committee(graph: Graph, member: URIRef, membership: URIRef, record: object, exclusions: list[dict], context: str) -> None:
    if not isinstance(record, dict):
        raise ValueError("committee record must be an object")
    committee = _source_iri(record.get("uri"), label="committee.uri")
    roles = record.get("role", [])
    if not isinstance(roles, list):
        raise ValueError("committee role must be an array")
    identity = {"membership": str(membership), "committee": str(committee), "memberDateRange": record.get("memberDateRange"), "role": sorted(roles)}
    subject = _generated(membership, "committee-membership", identity)
    graph.add((subject, RDF.type, MEMBERS.CommitteeMembership)); graph.add((member, MEMBERS.hasMembersMembership, subject))
    graph.add((subject, MEMBERS.isCommitteeMembershipOf, committee)); _date_range(graph, subject, "member-date-range", record.get("memberDateRange"))
    for role in roles:
        if role not in COMMITTEE_ROLES:
            raise ValueError(f"unsupported committee role: {role!r}")
        role_iri = _generated(subject, "role", {"role": role})
        graph.add((role_iri, RDF.type, COMMITTEE_ROLES[role])); graph.add((subject, MEMBERS.hasCommitteeRole, role_iri))
    for key, reason in FUTURE_COMMITTEE_FIELDS.items():
        if key in record and record[key] not in (None, [], ""):
            exclusions.append({"path": f"{context}.{key}", "context": str(committee), "reason": reason, "category": "future_work"})
    for key, reason in OWNERSHIP_DEFERRED_FIELDS.items():
        if key in record and record[key] not in (None, [], ""):
            exclusions.append({"path": f"{context}.{key}", "context": str(committee), "reason": reason, "category": "ownership_deferred"})
    dates = record.get("committeeDateRange")
    if isinstance(dates, dict):
        for key in ("start", "end"):
            if dates.get(key) is not None:
                exclusions.append({"path": f"{context}.committeeDateRange.{key}", "context": str(committee), "reason": FUTURE_COMMITTEE_FIELDS["committeeDateRange"], "category": "future_work"})
    names = record.get("committeeName")
    if isinstance(names, list):
        for name in names:
            if not isinstance(name, dict): continue
            for key in ("nameEn", "nameGa"):
                if name.get(key) is not None:
                    exclusions.append({"path": f"{context}.committeeName[].{key}", "context": str(committee), "reason": FUTURE_COMMITTEE_FIELDS["committeeName"], "category": "future_work"})


def _office(graph: Graph, member: URIRef, membership: URIRef, wrapper: object) -> None:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("office"), dict):
        raise ValueError("office wrapper must contain an office object")
    office = wrapper["office"]
    name = office.get("officeName")
    if not isinstance(name, dict):
        raise ValueError("office.officeName must be an object")
    label = name.get("showAs")
    if not isinstance(label, str) or not label:
        raise ValueError("office.officeName.showAs is required")
    subject = _generated(membership, "minister-of-state-membership", {"membership": str(membership), "office": office})
    role = URIRef(f"{subject}#role")
    graph.add((subject, RDF.type, MEMBERS.MinisterOfStateMembership)); graph.add((member, MEMBERS.hasMembersMembership, subject))
    graph.add((role, RDF.type, MEMBERS.MinisterOfStateRole)); graph.add((role, SKOS.prefLabel, Literal(label)))
    graph.add((subject, MEMBERS.hasMinisterOfStateRole, role)); _date_range(graph, subject, "date-range", office.get("dateRange"))
    if name.get("uri") is not None:
        graph.add((subject, MEMBERS.officeNameUri, _source_iri(name["uri"], label="officeName.uri")))


def transform_member_with_report(wrapper: dict) -> tuple[Graph, list[dict]]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
        raise ValueError("each Members record must contain a member object")
    data = wrapper["member"]; subject = _member_identity(data); graph = Graph(); exclusions: list[dict] = []
    graph.bind("", OIR); graph.bind("skos", SKOS)
    graph.add((subject, RDF.type, OIR.Member))
    for field, predicate in (("showAs", FOAF.name), ("fullName", FOAF.name), ("firstName", FOAF.firstName), ("lastName", FOAF.familyName)):
        if data.get(field) is not None: graph.add((subject, predicate, Literal(data[field])))
    for field, predicate in (("memberCode", OIR.memberCode), ("pId", OIR.pId), ("gender", OIR.gender), ("wikiTitle", OIR.wikiTitle)):
        if data.get(field) is not None: graph.add((subject, predicate, string(data[field])))
    if data.get("dateOfDeath") is not None: graph.add((subject, OIR.dateOfDeath, datetime_literal(data["dateOfDeath"])))
    if not isinstance(data.get("image"), bool): raise ValueError("member.image must be boolean")
    graph.add((subject, OIR.hasImage, Literal(data["image"], datatype=XSD.boolean)))
    memberships = data.get("memberships")
    if not isinstance(memberships, list): raise ValueError("member.memberships must be an array")
    for number, wrapper_membership in enumerate(memberships):
        if not isinstance(wrapper_membership, dict) or not isinstance(wrapper_membership.get("membership"), dict): raise ValueError("membership wrapper must contain a membership object")
        record = wrapper_membership["membership"]; membership = _source_iri(record.get("uri"), label="membership.uri"); house = record.get("house")
        term = _house_term_iri(house); code = house["houseCode"]
        membership_path = [part for part in urlsplit(str(membership)).path.split("/") if part]
        member_code = data["memberCode"]
        if len(membership_path) != 8 or membership_path[:4] != ["ie", "oireachtas", "member", "id"] or unquote(membership_path[4]) != member_code or membership_path[5:] != ["house", code, str(house["houseNo"])]:
            raise ValueError("membership.uri must be the Member HouseTerm source IRI")
        graph.add((membership, RDF.type, MEMBERS.OireachtasMembership)); graph.add((membership, RDF.type, MEMBERSHIP_TYPES[code])); graph.add((subject, MEMBERS.hasMembersMembership, membership))
        graph.add((membership, MEMBERS.inHouseTerm, term)); graph.add((membership, MEMBERS.isOireachtasMembershipOf, HOUSES[code])); _date_range(graph, membership, "date-range", record.get("dateRange"))
        representations = record.get("represents", [])
        if not isinstance(representations, list): raise ValueError("membership.represents must be an array")
        for representation in representations:
            if not isinstance(representation, dict) or not isinstance(representation.get("represent"), dict): raise ValueError("representation wrapper must contain a represent object")
            graph.add((membership, MEMBERS.isRepresentativeFrom, _reference_representation(representation["represent"], term, code)))
        for party in record.get("parties", []): _party(graph, subject, membership, party)
        for committee in record.get("committees", []): _committee(graph, subject, membership, committee, exclusions, "member.memberships[].membership.committees[]")
        for office in record.get("offices", []): _office(graph, subject, membership, office)
    return graph, sorted(exclusions, key=lambda value: (value["category"], value["path"], value["context"], value["reason"]))


def transform_member(wrapper: dict) -> Graph:
    return transform_member_with_report(wrapper)[0]
