"""Fail-closed validation for an individual Member graph."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import timedelta
from importlib.resources import files
from urllib.parse import unquote, urlsplit

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, RDF, XSD

from ..committee_roles import normalize_committee_roles
from ..office_observations import parse_office_observation
from ..party_observations import (malformed_party_report, parse_party_identity,
                                  party_date_range_error)
from ..transforms.common import MEMBERS, OIR, datetime_literal, iri, string
from .houses import validate_rdf
from .reference import assert_expected

RESOURCES = files("oireachtas_etl.validation.resources")
HOUSE_RE = re.compile(r"^https://data\.oireachtas\.ie/ie/oireachtas/house/(dail|seanad)/([1-9][0-9]*)$")
HOUSES = {"dail": URIRef("https://data.oireachtas.ie/house/dail"), "seanad": URIRef("https://data.oireachtas.ie/house/seanad")}
ORG = Namespace("http://www.w3.org/ns/org#")
GOVERNMENT = URIRef("https://data.oireachtas.ie/government")
OFFICE_TYPE_KEYS = {
    "TaoiseachOfficeType", "TanaisteOfficeType", "MinisterOfficeType",
    "MinisterOfStateOfficeType", "CeannComhairleOfficeType",
    "CathaoirleachOfficeType", "AttorneyGeneralOfficeType",
}
CABINET_OFFICE_TYPES = {
    "TaoiseachOfficeType", "TanaisteOfficeType", "MinisterOfficeType",
}
OCCURRENCE_KEY_RE = re.compile(r"^occ-[0-9a-f]{64}$")
OFFICE_IRI_RE = re.compile(r"^https://data\.oireachtas\.ie/office/[A-Za-z0-9][A-Za-z0-9-]*$")


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
            role = committee.get("role")
            role_dates = role.get("dateRange") if isinstance(role, dict) else None
            if isinstance(role_dates, dict):
                for key in ("start", "end"):
                    if role_dates.get(key) is not None:
                        output.append({
                            "path": f"{base}.role.dateRange.{key}",
                            "context": context,
                            "reason": "Committee special-role tenure dates have no property in the current Member mapping; only the committee membership tenure is represented.",
                            "category": "future_work",
                        })
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


def _local_office(value, label):
    office = _source(value, label)
    if not OFFICE_IRI_RE.fullmatch(str(office)):
        raise ValueError(f"{label} must be a registered local /office/{{key}} IRI")
    return office


def _office_dates(value):
    if not isinstance(value, dict) or set(value) - {"start", "end"} or "start" not in value:
        raise ValueError("office resolution date_range must contain start and optional end")
    start, end = value.get("start"), value.get("end")
    start_value = datetime_literal(start)
    if end is not None and datetime_literal(end).toPython() < start_value.toPython():
        raise ValueError("office resolution date_range has reverse dates")
    return {"start": start, "end": end}


def _office_is_retained(record):
    flag = record.get("retained", record.get("missing_retained", False))
    if not isinstance(flag, bool):
        raise ValueError("office resolution retained metadata must be boolean")
    status = record.get("retention_status")
    if status is not None and status not in {"missing_retained", "conflict_retained", "accepted"}:
        raise ValueError("office resolution has an unsupported retention_status")
    return flag or status in {"missing_retained", "conflict_retained"}


def _accepted_office_records(member, observations, office_resolutions, office_types,
                             member_memberships):
    """Independent resolution contract for this expected-RDF builder."""
    records = [] if office_resolutions is None else office_resolutions
    if not isinstance(records, list):
        raise ValueError("office_resolutions must be a list")
    categories = {} if office_types is None else office_types
    if not isinstance(categories, Mapping):
        raise ValueError("office_types must map full office IRIs to category concept keys")
    categories_by_iri = {}
    for key, category in categories.items():
        office = _local_office(key, "office_types key")
        if category not in OFFICE_TYPE_KEYS:
            raise ValueError(f"office_types value is not a registered OfficeType concept key: {category!r}")
        categories_by_iri[str(office)] = category

    source_ranges = {}
    for observation in observations:
        membership = str(observation["membership_iri"])
        source_ranges.setdefault((membership, _canonical(observation["date_range"])), []).append(observation)

    by_occurrence = {}
    accepted = {}
    present_counts = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each office resolution must be an object")
        key = record.get("occurrence_key")
        if not isinstance(key, str) or not OCCURRENCE_KEY_RE.fullmatch(key):
            raise ValueError("office resolution occurrence_key must be an occ- SHA-256 key")
        status = record.get("status")
        if status is not None and status != "accepted":
            raise ValueError("only accepted office resolutions may create an OfficeHolding")
        holder = _source(record.get("member_iri"), "office resolution member_iri")
        membership = _source(record.get("membership_iri"), "office resolution membership_iri")
        office = _local_office(record.get("office_iri"), "office resolution office_iri")
        dates = _office_dates(record.get("date_range"))
        retained = _office_is_retained(record)
        if holder != member:
            raise ValueError("office resolution member_iri does not match this Member")
        if str(membership) not in member_memberships:
            raise ValueError("office resolution membership_iri is not owned by this Member")
        date_key = _canonical(dates)
        scope = (str(holder), str(membership), date_key)
        if key in by_occurrence and by_occurrence[key] != scope:
            raise ValueError("one office occurrence_key cannot identify different Member, membership, or dates")
        by_occurrence[key] = scope
        if not retained and (str(membership), date_key) not in source_ranges:
            raise ValueError("office resolution does not match a valid current office observation")
        pair = (key, str(office))
        item = {"occurrence_key": key, "member_iri": holder,
                "membership_iri": membership, "office_iri": office,
                "date_range": dates, "retained": retained,
                "office_type": categories_by_iri.get(str(office))}
        if pair in accepted:
            old = accepted[pair]
            if old["date_range"] != dates:
                raise ValueError("duplicate office resolution identity has conflicting data")
            if old["retained"] and not retained:
                accepted[pair] = item
                present_counts.setdefault((str(membership), date_key), set()).add(key)
            continue
        accepted[pair] = item
        if not retained:
            present_counts.setdefault((str(membership), date_key), set()).add(key)

    for scope, keys in present_counts.items():
        distinct_source_reports = {_canonical(report["raw_office"])
                                   for report in source_ranges[scope] }
        if len(keys) > len(distinct_source_reports):
            raise ValueError("accepted office occurrences exceed distinct current source reports")

    holdings = []
    for item in accepted.values():
        # The office component distinguishes multiple targets of one occurrence.
        seed = json.dumps({"kind": "office-holding-occurrence-v1",
                           "occurrence_key": item["occurrence_key"],
                           "office_iri": str(item["office_iri"])},
                          ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        identity = hashlib.sha256(seed).hexdigest()
        item["holding_iri"] = URIRef(f"{member}#office-holding-{identity}")
        holdings.append(item)
    holdings.sort(key=lambda item: (item["occurrence_key"], str(item["office_iri"])))

    pending = []
    for (membership_text, range_key), reports in sorted(source_ranges.items()):
        distinct = {}
        for report in reports:
            distinct.setdefault(_canonical(report["raw_office"]), report)
        matched_count = len(present_counts.get((membership_text, range_key), set()))
        for _, report in sorted(distinct.items())[matched_count:]:
            pending.append({"path": report["path"], "context": membership_text,
                            "reason": "No accepted office resolution was supplied; no OfficeHolding or role is emitted.",
                            "category": "reconciliation_pending", "status": "unresolved"})
    return holdings, pending


def _calendar_date_only(value):
    return isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None


def _inclusive_end(value):
    if value is None:
        return None
    instant = datetime_literal(value).toPython()
    if _calendar_date_only(value):
        try:
            return instant + timedelta(days=1)
        except OverflowError as error:
            raise ValueError("office date-only end cannot be advanced for inclusive continuity") from error
    return instant


def _expected_cabinet_episodes(holdings):
    candidates = [record for record in holdings
                  if record["office_type"] in CABINET_OFFICE_TYPES]
    spans = []
    for record in candidates:
        dates = record["date_range"]
        start = datetime_literal(dates["start"])
        end = datetime_literal(dates["end"]) if dates["end"] is not None else None
        spans.append({"start": start.toPython(), "start_literal": start,
                      "end": end, "raw_end": dates["end"],
                      "through": _inclusive_end(dates["end"]),
                      "holding": record["holding_iri"]})
    spans.sort(key=lambda span: (span["start"], str(span["holding"])))
    result = []
    for span in spans:
        new_episode = (not result or
                       (result[-1]["through"] is not None
                        and span["start"] > result[-1]["through"]))
        if new_episode:
            result.append({"start": span["start"],
                           "start_literal": span["start_literal"],
                           "end": span["end"], "raw_end": span["raw_end"],
                           "through": span["through"],
                           "support": {span["holding"]}})
            continue
        episode = result[-1]
        episode["support"].add(span["holding"])
        if episode["through"] is None:
            continue
        later = (span["through"] is None or span["through"] > episode["through"])
        equal_but_precise = (span["through"] == episode["through"]
                             and span["end"] is not None and episode["end"] is not None
                             and not _calendar_date_only(span["raw_end"])
                             and _calendar_date_only(episode["raw_end"]))
        if later or equal_but_precise:
            episode["end"] = span["end"]
            episode["raw_end"] = span["raw_end"]
            episode["through"] = span["through"]
    return result


def _expected_cabinet_iri(member, start_literal):
    data = {"kind": "cabinet-membership-v1", "member_iri": str(member),
            "government_iri": str(GOVERNMENT), "start": str(start_literal)}
    digest = hashlib.sha256(json.dumps(
        data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return URIRef(f"{member}#cabinet-membership-{digest}")


def _expected_office_triples(graph, member, holdings):
    for item in holdings:
        holding, office = item["holding_iri"], item["office_iri"]
        graph.add((holding, RDF.type, MEMBERS.OfficeHolding))
        graph.add((member, MEMBERS.hasMembersMembership, holding))
        graph.add((holding, MEMBERS.heldOffice, office))
        graph.add((holding, MEMBERS.officeHolder, member))
        graph.add((member, MEMBERS.hasOfficeHolding, holding))
        _range(graph, holding, "date-range", item["date_range"])

    for episode in _expected_cabinet_episodes(holdings):
        cabinet = _expected_cabinet_iri(member, episode["start_literal"])
        role = URIRef(f"{cabinet}#role")
        graph.add((cabinet, RDF.type, MEMBERS.CabinetMembership))
        graph.add((member, MEMBERS.hasMembersMembership, cabinet))
        graph.add((cabinet, MEMBERS.isCabinetMembershipOf, GOVERNMENT))
        graph.add((cabinet, MEMBERS.hasCabinetRole, role))
        graph.add((role, RDF.type, MEMBERS.CabinetMember))
        graph.add((role, ORG.heldBy, member))
        for holding in episode["support"]:
            graph.add((cabinet, MEMBERS.supportedByOfficeHolding, holding))
        _range(graph, cabinet, "date-range", {
            "start": str(episode["start_literal"]),
            "end": str(episode["end"]) if episode["end"] is not None else None})


def expected_member_graph(wrapper: dict, *, preserved_party_graph: Graph | None = None,
                          office_resolutions: list[dict] | None = None,
                          office_types: Mapping[str, str] | None = None) -> tuple[Graph, list[dict]]:
    """Independent source-to-RDF acceptance contract for Member-owned triples.

    Office resolutions and OfficeType categories have the same public data
    contract as ``transform_member_with_report`` but are validated and expanded
    here without importing or invoking that production transform.
    """
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
    valid_offices = []
    member_membership_iris = set()
    for membership_index, wrapped in enumerate(memberships):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("membership"), dict): raise ValueError("membership wrapper must contain a membership object")
        record = wrapped["membership"]; membership = _source(record.get("uri"), "membership.uri"); house = record.get("house")
        member_membership_iris.add(str(membership))
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
        parties = record.get("parties", [])
        if not isinstance(parties, list): raise ValueError("membership.parties must be an array")
        for party_index, wrapped_party in enumerate(parties):
            party, party_uri, party_code = parse_party_identity(wrapped_party, str(membership))
            party_iri = _source(party_uri, "party.uri")
            reason = party_date_range_error(party)
            if reason is not None:
                exclusions.append(malformed_party_report(
                    membership_index=membership_index, party_index=party_index,
                    membership_uri=str(membership), member_uri=str(subject),
                    party=party, party_uri=party_uri, party_code=party_code,
                    wrapped=wrapped_party, reason=reason,
                ))
                continue
            pm = _generated(membership, "party-membership", {"membership": str(membership), "party": party_iri, "dateRange": party.get("dateRange")})
            graph.add((pm, RDF.type, MEMBERS.ParliamentaryCollectionMembership))
            graph.add((subject, MEMBERS.hasMembersMembership, pm))
            graph.add((pm, MEMBERS.inOireachtasMembership, membership))
            graph.add((pm, MEMBERS.memberOfCollection, party_iri))
            if party_code != "Independent":
                graph.add((pm, RDF.type, MEMBERS.PartyMembership))
                graph.add((pm, MEMBERS.isPartyMembershipOf, party_iri))
            _range(graph, pm, "date-range", party.get("dateRange"))
        committees = record.get("committees", [])
        if not isinstance(committees, list): raise ValueError("membership.committees must be an array")
        for committee in committees:
            if not isinstance(committee, dict): raise ValueError("committee record must be an object")
            committee_iri = _source(committee.get("uri"), "committee.uri")
            raw_roles = committee.get("role", [])
            if isinstance(raw_roles, list):
                roles = raw_roles
                role_date_range = None
            elif isinstance(raw_roles, dict):
                if set(raw_roles) != {"title", "dateRange"}:
                    raise ValueError("committee role object must contain only title and dateRange")
                role_title = raw_roles.get("title")
                role_titles = {"Cathaoirleach": "Chair", "Leas-Chathaoirleach": "Deputy Chair"}
                if not isinstance(role_title, str) or role_title not in role_titles:
                    raise ValueError(f"unsupported committee role title: {role_title!r}")
                role_date_range = raw_roles.get("dateRange")
                if not isinstance(role_date_range, dict) or set(role_date_range) - {"start", "end"}:
                    raise ValueError("committee role.dateRange must contain start and optional end")
                if role_date_range.get("start") is None:
                    raise ValueError("committee role.dateRange.start is required")
                role_start = datetime_literal(role_date_range["start"])
                if role_date_range.get("end") is not None and datetime_literal(role_date_range["end"]).toPython() < role_start.toPython():
                    raise ValueError("reverse committee role date range")
                roles = [role_titles[role_title]]
            else:
                raise ValueError("committee role must be an array or a supported role object")
            for role in roles:
                if not isinstance(role, str) or role not in {"Chair", "Deputy Chair"}:
                    raise ValueError(f"unsupported committee role: {role!r}")
            cm = _generated(membership, "committee-membership", {"membership": str(membership), "committee": str(committee_iri), "memberDateRange": committee.get("memberDateRange"), "role": sorted(roles)})
            graph.add((cm, RDF.type, MEMBERS.CommitteeMembership)); graph.add((subject, MEMBERS.hasMembersMembership, cm)); graph.add((cm, MEMBERS.isCommitteeMembershipOf, committee_iri)); _range(graph, cm, "member-date-range", committee.get("memberDateRange"))
            for role in roles:
                ri = _generated(cm, "role", {"role": role}); graph.add((ri, RDF.type, MEMBERS.Chair if role == "Chair" else MEMBERS.DeputyChair)); graph.add((cm, MEMBERS.hasCommitteeRole, ri))
        offices = record.get("offices", [])
        if not isinstance(offices, list): raise ValueError("membership.offices must be an array")
        for office_index, wrapped_office in enumerate(offices):
            try:
                office_data, _name, _label, _source_uri, dates = parse_office_observation(wrapped_office)
            except ValueError as error:
                exclusions.append({
                    "path": f"member.memberships[{membership_index}].membership.offices[{office_index}]",
                    "context": str(membership),
                    "reason": str(error),
                    "category": "source_quarantine",
                    "status": "review_required",
                })
                continue
            valid_offices.append({
                "membership_iri": membership,
                "raw_office": office_data,
                "date_range": {"start": dates["start"], "end": dates.get("end")},
                "path": f"member.memberships[{membership_index}].membership.offices[{office_index}]",
            })
    holdings, pending = _accepted_office_records(
        subject, valid_offices, office_resolutions, office_types,
        member_membership_iris)
    _expected_office_triples(graph, subject, holdings)
    exclusions.extend(pending)
    exclusions.extend(extract_member_omissions(wrapper))
    if preserved_party_graph is not None:
        graph += preserved_party_graph
    return graph, sorted(exclusions, key=lambda value: (value["category"], value["path"], value["context"], value["reason"]))


def validate_member_source(wrapper: dict, *, office_resolutions: list[dict] | None = None,
                           office_types: Mapping[str, str] | None = None) -> list[dict]:
    """Cheap source-only skip gate; it deliberately never constructs RDF."""
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
        raise ValueError("each Members record must contain a member object")
    member = wrapper["member"]
    _required_text(member.get("memberCode"), "member.memberCode")
    member_iri = _source(member.get("uri"), "member.uri")
    if not isinstance(member.get("image"), bool): raise ValueError("member.image must be boolean")
    if not isinstance(member.get("memberships"), list): raise ValueError("member.memberships must be an array")
    malformed_offices = []
    malformed_parties = []
    valid_offices = []
    member_membership_iris = set()
    for membership_index, wrapped in enumerate(member["memberships"]):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("membership"), dict): raise ValueError("membership wrapper must contain a membership object")
        record = wrapped["membership"]
        membership_iri = _source(record.get("uri"), "membership.uri")
        member_membership_iris.add(str(membership_iri))
        if not isinstance(record.get("house"), dict): raise ValueError("house must be an object")
        _source(record["house"].get("uri"), "house.uri")
        date = record.get("dateRange")
        if not isinstance(date, dict): raise ValueError("membership dateRange must be an object")
        start = datetime_literal(date.get("start"))
        if date.get("end") is not None and datetime_literal(date["end"]).toPython() < start.toPython(): raise ValueError("reverse membership date range")
        parties = record.get("parties", [])
        if not isinstance(parties, list): raise ValueError("membership.parties must be an array")
        for party_index, wrapped_party in enumerate(parties):
            party, party_uri, party_code = parse_party_identity(wrapped_party, str(_source(record.get("uri"), "membership.uri")))
            reason = party_date_range_error(party)
            if reason is not None:
                malformed_parties.append(malformed_party_report(
                    membership_index=membership_index, party_index=party_index,
                    membership_uri=str(record["uri"]), member_uri=str(member["uri"]),
                    party=party, party_uri=party_uri, party_code=party_code,
                    wrapped=wrapped_party, reason=reason,
                ))
        committees = record.get("committees", [])
        if not isinstance(committees, list): raise ValueError("membership.committees must be an array")
        for committee in committees:
            if not isinstance(committee, dict): raise ValueError("committee record must be an object")
            _source(committee.get("uri"), "committee.uri")
            normalize_committee_roles(committee.get("role", []))
            committee_range = committee.get("memberDateRange")
            if not isinstance(committee_range, dict): raise ValueError("committee memberDateRange must be an object")
            committee_start = datetime_literal(committee_range.get("start"))
            if (committee_range.get("end") is not None
                    and datetime_literal(committee_range["end"]).toPython() < committee_start.toPython()):
                raise ValueError("reverse committee membership date range")
        offices = record.get("offices", [])
        if not isinstance(offices, list): raise ValueError("membership.offices must be an array")
        for office_index, wrapped_office in enumerate(offices):
            try:
                office_data, _name, _label, _source_uri, office_dates = parse_office_observation(wrapped_office)
            except ValueError as error:
                malformed_offices.append({
                    "path": f"member.memberships[{membership_index}].membership.offices[{office_index}]",
                    "context": str(record["uri"]),
                    "reason": str(error),
                    "category": "source_quarantine",
                    "status": "review_required",
                })
                continue
            valid_offices.append({
                "membership_iri": membership_iri,
                "raw_office": office_data,
                "date_range": {"start": office_dates["start"], "end": office_dates.get("end")},
                "path": f"member.memberships[{membership_index}].membership.offices[{office_index}]",
            })
    _, pending_offices = _accepted_office_records(
        member_iri, valid_offices, office_resolutions, office_types,
        member_membership_iris)
    return sorted([*extract_member_omissions(wrapper), *malformed_offices,
                   *malformed_parties, *pending_offices],
                  key=lambda value: (value["category"], value["path"], value["context"], value["reason"]))


def _validate_office_closed_world(graph: Graph,
                                  office_types: Mapping[str, str] | None) -> None:
    """Check Member-owned office structures beyond ontology inference."""
    forbidden = {
        (None, RDF.type, MEMBERS.MinisterOfStateMembership),
        (None, RDF.type, MEMBERS.MinisterOfStateRole),
        (None, MEMBERS.hasMinisterOfStateRole, None),
        (None, MEMBERS.officeNameUri, None),
    }
    if any(next(graph.triples(pattern), None) is not None for pattern in forbidden):
        raise ValueError("deprecated legacy office RDF is forbidden in Member graphs")

    type_map = {str(office): category
                for office, category in (office_types or {}).items()}
    qualifying_holdings = set()
    for holding in graph.subjects(RDF.type, MEMBERS.OfficeHolding):
        offices = list(graph.objects(holding, MEMBERS.heldOffice))
        holders = list(graph.objects(holding, MEMBERS.officeHolder))
        periods = list(graph.objects(holding, MEMBERS.hasMembershipDateRange))
        if len(offices) != 1 or len(holders) != 1 or len(periods) != 1:
            raise ValueError("OfficeHolding must have exactly one office, holder, and date range")
        person = holders[0]
        if ((person, MEMBERS.hasOfficeHolding, holding) not in graph
                or (person, MEMBERS.hasMembersMembership, holding) not in graph):
            raise ValueError("OfficeHolding holder links must be emitted in both directions")
        if type_map.get(str(offices[0])) in CABINET_OFFICE_TYPES:
            qualifying_holdings.add(holding)

    covered_holdings = {}
    cabinet_periods = []
    for cabinet in graph.subjects(RDF.type, MEMBERS.CabinetMembership):
        roles = list(graph.objects(cabinet, MEMBERS.hasCabinetRole))
        governments = list(graph.objects(cabinet, MEMBERS.isCabinetMembershipOf))
        supports = list(graph.objects(cabinet, MEMBERS.supportedByOfficeHolding))
        periods = list(graph.objects(cabinet, MEMBERS.hasMembershipDateRange))
        if (len(roles) != 1 or governments != [GOVERNMENT]
                or not supports or len(periods) != 1):
            raise ValueError("CabinetMembership requires one role, Government, date range, and supporting holding")
        role = roles[0]
        holders = list(graph.objects(role, ORG.heldBy))
        role_types = set(graph.objects(role, RDF.type))
        if (role_types != {MEMBERS.CabinetMember} or len(holders) != 1
                or (holders and (holders[0], MEMBERS.hasMembersMembership, cabinet) not in graph)):
            raise ValueError("CabinetMembership must have one generic CabinetMember role held by its Member")
        for holding in supports:
            if holding not in qualifying_holdings:
                raise ValueError("CabinetMembership may only be supported by qualifying office types")
            covered_holdings[holding] = covered_holdings.get(holding, 0) + 1
        period = periods[0]
        start_values = list(graph.objects(period, MEMBERS.StartDate))
        end_values = list(graph.objects(period, MEMBERS.EndDate))
        if len(start_values) != 1 or len(end_values) > 1:
            raise ValueError("invalid CabinetMembership date range")
        cabinet_periods.append((start_values[0].toPython(),
                                end_values[0].toPython() if end_values else None))

    if set(covered_holdings) != qualifying_holdings or any(
            count != 1 for count in covered_holdings.values()):
        raise ValueError("each qualifying OfficeHolding must support exactly one Cabinet episode")
    cabinet_periods.sort(key=lambda value: value[0])
    previous_end = None
    for index, (start, end) in enumerate(cabinet_periods):
        if index and previous_end is None:
            raise ValueError("Cabinet episodes cannot follow an open-ended episode")
        if index and start <= previous_end:
            raise ValueError("Cabinet episodes for one Member must not overlap")
        previous_end = end


def validate_member(wrapper: dict, graph: Graph, *, preserved_party_graph: Graph | None = None,
                    office_resolutions: list[dict] | None = None,
                    office_types: Mapping[str, str] | None = None) -> list[dict]:
    """Validate source shape, exact owned triples, SHACL, and temporal quality."""
    # The expected member graph is constructed from source by the independent
    # acceptance contract, never by the production transformer.
    expected, exclusions = expected_member_graph(
        wrapper, preserved_party_graph=preserved_party_graph,
        office_resolutions=office_resolutions, office_types=office_types)
    assert_expected(graph, set(expected))
    _validate_office_closed_world(graph, office_types)
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
