"""Fail-closed validation for an individual Member graph."""
from __future__ import annotations

import hashlib
import json
import re
from importlib.resources import files
from urllib.parse import quote, unquote, urlsplit

from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF, SKOS, XSD

from ..transforms.common import MEMBERS, OIR, datetime_literal, iri, string
from .houses import validate_rdf
from .reference import assert_expected

RESOURCES = files("oireachtas_etl.validation.resources")
HOUSE_RE = re.compile(r"^https://data\.oireachtas\.ie/ie/oireachtas/house/(dail|seanad)/([1-9][0-9]*)$")
HOUSES = {"dail": URIRef("https://data.oireachtas.ie/house/dail"), "seanad": URIRef("https://data.oireachtas.ie/house/seanad")}


def extract_member_omissions(wrapper: dict) -> list[dict]:
    """Source-only, stable report of mapped fields not owned by Member graphs."""
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
        raise ValueError("each Members record must contain a member object")
    output = []
    reasons = {
        "committeeDateRange": ("future_work", "committee operational lifespan is deferred pending a Committee owner"),
        "committeeName": ("future_work", "time-bounded committee names are deferred pending a Committee owner"),
        "expiryType": ("future_work", "committee expiry type is deferred pending a Committee owner"),
        "mainStatus": ("future_work", "committee lifecycle status is deferred pending a Committee owner"),
        "status": ("future_work", "committee lifecycle status is deferred pending a Committee owner"),
        "serviceUnit": ("future_work", "committee service unit is deferred pending a Committee owner"),
        "committeeCode": ("ownership_deferred", "Committee descriptions are owned by a future Committee endpoint"),
        "committeeID": ("ownership_deferred", "Committee descriptions are owned by a future Committee endpoint"),
        "committeeType": ("ownership_deferred", "Committee descriptions are owned by a future Committee endpoint"),
    }
    for membership in wrapper["member"].get("memberships", []):
        record = membership.get("membership", {}) if isinstance(membership, dict) else {}
        for committee in record.get("committees", []) if isinstance(record, dict) else []:
            if not isinstance(committee, dict): continue
            context = str(committee.get("uri", "")); base = "member.memberships[].membership.committees[]"
            for key, (category, reason) in reasons.items():
                if committee.get(key) not in (None, [], ""):
                    output.append({"path": f"{base}.{key}", "context": context, "reason": reason, "category": category})
            dates = committee.get("committeeDateRange")
            if isinstance(dates, dict):
                for key in ("start", "end"):
                    if dates.get(key) is not None: output.append({"path": f"{base}.committeeDateRange.{key}", "context": context, "reason": reasons["committeeDateRange"][1], "category": "future_work"})
            for name in committee.get("committeeName", []) if isinstance(committee.get("committeeName", []), list) else []:
                if isinstance(name, dict):
                    for key in ("nameEn", "nameGa"):
                        if name.get(key) is not None: output.append({"path": f"{base}.committeeName[].{key}", "context": context, "reason": reasons["committeeName"][1], "category": "future_work"})
    return sorted(output, key=lambda value: (value["category"], value["path"], value["context"], value["reason"]))


def _normalise(value, path=()):
    unordered = {("memberships",), ("memberships", "membership", "committees"), ("memberships", "membership", "parties"), ("memberships", "membership", "represents"), ("memberships", "membership", "offices"), ("memberships", "membership", "committees", "role"), ("memberships", "membership", "committees", "committeeType"), ("memberships", "membership", "committees", "committeeName")}
    if isinstance(value, dict):
        return {key: _normalise(value[key], path + (key,)) for key in sorted(value)}
    if isinstance(value, list):
        values = [_normalise(item, path) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) if path in unordered else values
    return value


def _canonical(value):
    return json.dumps(_normalise(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _generated(parent, kind, identity):
    return URIRef(f"{parent}#{kind}-{hashlib.sha256(_canonical(identity)).hexdigest()}")


def _source(value, label):
    result = iri(value); parsed = urlsplit(str(result))
    if parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie" or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    return result


def _required_text(value, label):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _range(graph, parent, fragment, value):
    if not isinstance(value, dict): raise ValueError("membership dateRange must be an object")
    start = datetime_literal(value.get("start"))
    subject = URIRef(f"{parent}#{fragment}")
    graph.add((subject, RDF.type, MEMBERS.DateRange)); graph.add((subject, MEMBERS.StartDate, start))
    if value.get("end") is not None:
        end = datetime_literal(value["end"])
        if end.toPython() < start.toPython(): raise ValueError("reverse membership date range")
        graph.add((subject, MEMBERS.EndDate, end))
    graph.add((parent, MEMBERS.hasMembershipDateRange, subject))


def expected_member_graph(wrapper: dict) -> tuple[Graph, list[dict]]:
    """Independent source-to-RDF acceptance contract for Member-owned triples."""
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict): raise ValueError("each Members record must contain a member object")
    data = wrapper["member"]
    code = _required_text(data.get("memberCode"), "member.memberCode")
    subject = _source(data.get("uri"), "member.uri")
    path = [part for part in urlsplit(str(subject)).path.split("/") if part]
    if len(path) != 5 or path[:4] != ["ie", "oireachtas", "member", "id"] or unquote(path[-1]) != code: raise ValueError("memberCode must match the final member.uri path segment")
    graph, exclusions = Graph(), []
    graph.add((subject, RDF.type, OIR.Member))
    for field, predicate in (("showAs", FOAF.name), ("fullName", FOAF.name), ("firstName", FOAF.firstName), ("lastName", FOAF.familyName)):
        if data.get(field) is not None: graph.add((subject, predicate, Literal(_required_text(data[field], f"member.{field}"))))
    for field, predicate in (("memberCode", OIR.memberCode), ("pId", OIR.pId), ("gender", OIR.gender), ("wikiTitle", OIR.wikiTitle)):
        if data.get(field) is not None:
            if not isinstance(data[field], str): raise ValueError(f"member.{field} must be a string")
            graph.add((subject, predicate, string(data[field])))
    if data.get("dateOfDeath") is not None: graph.add((subject, OIR.dateOfDeath, datetime_literal(data["dateOfDeath"])))
    if not isinstance(data.get("image"), bool): raise ValueError("member.image must be boolean")
    graph.add((subject, OIR.hasImage, Literal(data["image"], datatype=XSD.boolean)))
    memberships = data.get("memberships")
    if not isinstance(memberships, list): raise ValueError("member.memberships must be an array")
    for wrapped in memberships:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("membership"), dict): raise ValueError("membership wrapper must contain a membership object")
        record = wrapped["membership"]; membership = _source(record.get("uri"), "membership.uri"); house = record.get("house")
        if not isinstance(house, dict) or house.get("houseCode") not in HOUSES: raise ValueError("house must be a supported object")
        term = _source(house.get("uri"), "house.uri"); match = HOUSE_RE.fullmatch(str(term)); house_code = house["houseCode"]
        if not match or match.group(1) != house_code or match.group(2) != str(house.get("houseNo")): raise ValueError("house.uri must be the direct IRI for its houseCode and houseNo")
        mp = [part for part in urlsplit(str(membership)).path.split("/") if part]
        if len(mp) != 8 or mp[:4] != ["ie", "oireachtas", "member", "id"] or unquote(mp[4]) != code or mp[5:] != ["house", house_code, str(house["houseNo"])]: raise ValueError("membership.uri must be the Member HouseTerm source IRI")
        graph.add((membership, RDF.type, MEMBERS.OireachtasMembership)); graph.add((membership, RDF.type, MEMBERS.DailMembership if house_code == "dail" else MEMBERS.SeanadMembership)); graph.add((subject, MEMBERS.hasMembersMembership, membership)); graph.add((membership, MEMBERS.inHouseTerm, term)); graph.add((membership, MEMBERS.isOireachtasMembershipOf, HOUSES[house_code])); _range(graph, membership, "date-range", record.get("dateRange"))
        for wrapped_rep in record.get("represents", []):
            if not isinstance(wrapped_rep, dict) or not isinstance(wrapped_rep.get("represent"), dict): raise ValueError("representation wrapper must contain a represent object")
            rep = wrapped_rep["represent"]; kind = rep.get("representType"); rep_iri = _source(rep.get("uri"), "representation.uri")
            if kind not in {"constituency", "panel"} or (kind == "constituency") != (house_code == "dail"): raise ValueError("representation type is incompatible with membership house")
            rp, tp = [p for p in urlsplit(str(rep_iri)).path.split("/") if p], [p for p in urlsplit(str(term)).path.split("/") if p]
            if len(rp) != 7 or rp[:5] != tp or rp[5] != kind or unquote(rp[6]) != _required_text(rep.get("representCode"), "representation.representCode"): raise ValueError("representation.uri must match membership HouseTerm, representType and representCode")
            graph.add((membership, MEMBERS.isRepresentativeFrom, rep_iri))
        for wrapped_party in record.get("parties", []):
            if not isinstance(wrapped_party, dict) or not isinstance(wrapped_party.get("party"), dict): raise ValueError("party wrapper must contain a party object")
            party = wrapped_party["party"]; party_iri = _source(party.get("uri"), "party.uri"); pp = [p for p in urlsplit(str(party_iri)).path.split("/") if p]
            if len(pp) != 6 or pp[:3] != ["ie", "oireachtas", "party"] or pp[3:5] != mp[6:8] or unquote(pp[5]) != _required_text(party.get("partyCode"), "party.partyCode"): raise ValueError("party.uri must be the term-scoped Party source IRI")
            pm = _generated(membership, "party-membership", {"membership": str(membership), "party": party_iri, "dateRange": party.get("dateRange")})
            graph.add((pm, RDF.type, MEMBERS.PartyMembership)); graph.add((subject, MEMBERS.hasMembersMembership, pm)); graph.add((pm, MEMBERS.isPartyMembershipOf, party_iri)); _range(graph, pm, "date-range", party.get("dateRange"))
        for committee in record.get("committees", []):
            if not isinstance(committee, dict): raise ValueError("committee record must be an object")
            committee_iri = _source(committee.get("uri"), "committee.uri"); roles = committee.get("role", [])
            if not isinstance(roles, list): raise ValueError("committee role must be an array")
            cm = _generated(membership, "committee-membership", {"membership": str(membership), "committee": str(committee_iri), "memberDateRange": committee.get("memberDateRange"), "role": sorted(roles)})
            graph.add((cm, RDF.type, MEMBERS.CommitteeMembership)); graph.add((subject, MEMBERS.hasMembersMembership, cm)); graph.add((cm, MEMBERS.isCommitteeMembershipOf, committee_iri)); _range(graph, cm, "member-date-range", committee.get("memberDateRange"))
            for role in roles:
                if role not in {"Chair", "Deputy Chair"}: raise ValueError(f"unsupported committee role: {role!r}")
                ri = _generated(cm, "role", {"role": role}); graph.add((ri, RDF.type, MEMBERS.Chair if role == "Chair" else MEMBERS.DeputyChair)); graph.add((cm, MEMBERS.hasCommitteeRole, ri))
        for wrapped_office in record.get("offices", []):
            if not isinstance(wrapped_office, dict) or not isinstance(wrapped_office.get("office"), dict): raise ValueError("office wrapper must contain an office object")
            office = wrapped_office["office"]; name = office.get("officeName")
            if not isinstance(name, dict): raise ValueError("office.officeName must be an object")
            om = _generated(membership, "minister-of-state-membership", {"membership": str(membership), "office": office}); role = URIRef(f"{om}#role")
            graph.add((om, RDF.type, MEMBERS.MinisterOfStateMembership)); graph.add((subject, MEMBERS.hasMembersMembership, om)); graph.add((role, RDF.type, MEMBERS.MinisterOfStateRole)); graph.add((role, SKOS.prefLabel, Literal(_required_text(name.get("showAs"), "office.officeName.showAs")))); graph.add((om, MEMBERS.hasMinisterOfStateRole, role)); _range(graph, om, "date-range", office.get("dateRange"))
            if name.get("uri") is not None: graph.add((om, MEMBERS.officeNameUri, _source(name["uri"], "officeName.uri")))
    return graph, extract_member_omissions(wrapper)


def validate_member_source(wrapper: dict) -> list[dict]:
    """Cheap source-only skip gate; it deliberately never constructs RDF."""
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
        raise ValueError("each Members record must contain a member object")
    member = wrapper["member"]
    _required_text(member.get("memberCode"), "member.memberCode")
    _source(member.get("uri"), "member.uri")
    if not isinstance(member.get("image"), bool): raise ValueError("member.image must be boolean")
    if not isinstance(member.get("memberships"), list): raise ValueError("member.memberships must be an array")
    for wrapped in member["memberships"]:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("membership"), dict): raise ValueError("membership wrapper must contain a membership object")
        record = wrapped["membership"]
        _source(record.get("uri"), "membership.uri")
        if not isinstance(record.get("house"), dict): raise ValueError("house must be an object")
        _source(record["house"].get("uri"), "house.uri")
        date = record.get("dateRange")
        if not isinstance(date, dict): raise ValueError("membership dateRange must be an object")
        start = datetime_literal(date.get("start"))
        if date.get("end") is not None and datetime_literal(date["end"]).toPython() < start.toPython(): raise ValueError("reverse membership date range")
    return extract_member_omissions(wrapper)


def validate_member(wrapper: dict, graph: Graph) -> list[dict]:
    """Validate source shape, exact owned triples, SHACL, and temporal quality."""
    # The expected member graph is constructed from source by the independent
    # acceptance contract, never by the production transformer.
    expected, exclusions = expected_member_graph(wrapper)
    assert_expected(graph, set(expected))
    validate_rdf(graph)
    conforms, _, report = validate(
        graph, shacl_graph=RESOURCES.joinpath("members.ttl").read_text(),
        shacl_graph_format="turtle", inference="none", abort_on_first=False,
    )
    if not conforms:
        raise ValueError("SHACL validation failed:\n" + str(report))
    for period in graph.subjects(RDF.type, MEMBERS.DateRange):
        starts = list(graph.objects(period, MEMBERS.StartDate)); ends = list(graph.objects(period, MEMBERS.EndDate))
        if len(starts) != 1 or len(ends) > 1:
            raise ValueError("invalid membership date range")
        if ends and ends[0].toPython() < starts[0].toPython():
            raise ValueError("reverse membership date range")
    return exclusions
