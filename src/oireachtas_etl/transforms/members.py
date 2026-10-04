"""Deterministic, member-owned membership graph transformation."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import unquote, urlsplit

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, RDF, SKOS, XSD

from ..committee_roles import normalize_committee_roles
from ..office_observations import parse_office_observation
from ..party_observations import (malformed_party_report, parse_party_identity,
                                  party_date_range_error)
from .common import MEMBERS, OIR, datetime_literal, iri, string

HOUSES = {"dail": URIRef("https://data.oireachtas.ie/house/dail"), "seanad": URIRef("https://data.oireachtas.ie/house/seanad")}
MEMBERSHIP_TYPES = {"dail": MEMBERS.DailMembership, "seanad": MEMBERS.SeanadMembership}
COMMITTEE_ROLES = {"Chair": MEMBERS.Chair, "Deputy Chair": MEMBERS.DeputyChair}
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


def _party(graph: Graph, member: URIRef, membership: URIRef, value: object,
           identity: tuple[dict, str, str] | None = None) -> None:
    party, party_uri, code = identity or parse_party_identity(value, str(membership))
    party_iri = URIRef(party_uri)
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


def prior_party_membership_evidence(previous: Graph, member: URIRef,
                                    membership_iris: set[str]) -> Graph:
    """Select exact previously accepted party RDF for affected House terms.

    Party resources are parent-scoped under their containing Oireachtas
    membership. The explicit context predicates cover current payloads; the
    stable parent-scoped IRI also permits safe recovery from older accepted
    payloads predating the explicit context relation.
    """
    retained = Graph()
    for membership_text in sorted(membership_iris):
        membership = URIRef(membership_text)
        subjects = set(previous.subjects(MEMBERS.inOireachtasMembership, membership))
        prefix = membership_text + "#party-membership-"
        subjects.update(
            candidate for candidate in previous.objects(member, MEMBERS.hasMembersMembership)
            if isinstance(candidate, URIRef) and str(candidate).startswith(prefix)
        )
        for subject in subjects:
            if (member, MEMBERS.hasMembersMembership, subject) not in previous:
                continue
            if not (list(previous.objects(subject, MEMBERS.memberOfCollection))
                    or list(previous.objects(subject, MEMBERS.isPartyMembershipOf))):
                continue
            for triple in previous.triples((subject, None, None)):
                retained.add(triple)
            retained.add((member, MEMBERS.hasMembersMembership, subject))
            for period in previous.objects(subject, MEMBERS.hasMembershipDateRange):
                for triple in previous.triples((period, None, None)):
                    retained.add(triple)
    return retained


def _committee(graph: Graph, member: URIRef, membership: URIRef, record: object, exclusions: list[dict], context: str) -> None:
    if not isinstance(record, dict):
        raise ValueError("committee record must be an object")
    committee = _source_iri(record.get("uri"), label="committee.uri")
    roles, _role_date_range = normalize_committee_roles(record.get("role", []))
    identity = {"membership": str(membership), "committee": str(committee), "memberDateRange": record.get("memberDateRange"), "role": sorted(roles)}
    subject = _generated(membership, "committee-membership", identity)
    graph.add((subject, RDF.type, MEMBERS.CommitteeMembership)); graph.add((member, MEMBERS.hasMembersMembership, subject))
    graph.add((subject, MEMBERS.isCommitteeMembershipOf, committee)); _date_range(graph, subject, "member-date-range", record.get("memberDateRange"))
    for role in roles:
        role_iri = _generated(subject, "role", {"role": role})
        graph.add((role_iri, RDF.type, COMMITTEE_ROLES[role])); graph.add((subject, MEMBERS.hasCommitteeRole, role_iri))
    if _role_date_range is not None:
        for key in ("start", "end"):
            if _role_date_range.get(key) is not None:
                exclusions.append({
                    "path": f"{context}.role.dateRange.{key}",
                    "context": str(committee),
                    "reason": "Committee special-role tenure dates have no property in the current Member mapping; only the committee membership tenure is represented.",
                    "category": "future_work",
                })
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


def _office_iri(value: object, label: str) -> URIRef:
    subject = _source_iri(value, label=label)
    if not OFFICE_IRI_RE.fullmatch(str(subject)):
        raise ValueError(f"{label} must be a registered local /office/{{key}} IRI")
    return subject


def _resolution_date_range(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - {"start", "end"} or "start" not in value:
        raise ValueError("office resolution date_range must contain start and optional end")
    start = value.get("start")
    start_literal = datetime_literal(start)
    end = value.get("end")
    if end is not None and datetime_literal(end).toPython() < start_literal.toPython():
        raise ValueError("office resolution date_range has reverse dates")
    return {"start": start, "end": end}


def _retained_resolution(record: dict) -> bool:
    retained = record.get("retained", record.get("missing_retained", False))
    if not isinstance(retained, bool):
        raise ValueError("office resolution retained metadata must be boolean")
    status = record.get("retention_status")
    if status is not None and status not in {"missing_retained", "conflict_retained", "accepted"}:
        raise ValueError("office resolution has an unsupported retention_status")
    return retained or status in {"missing_retained", "conflict_retained"}


def _office_resolution_records(member: URIRef, observations: list[dict],
                               office_resolutions: list[dict] | None,
                               office_types: Mapping[str, str] | None,
                               member_memberships: set[str]) -> tuple[list[dict], list[dict]]:
    """Validate the explicit accepted-resolution boundary and deduplicate reports.

    The occurrence ledger owns review and correspondence. This transformer only
    consumes complete accepted holding records; source labels and source URIs
    never establish local office identity.
    """
    resolutions = [] if office_resolutions is None else office_resolutions
    if not isinstance(resolutions, list):
        raise ValueError("office_resolutions must be a list")
    types = {} if office_types is None else office_types
    if not isinstance(types, Mapping):
        raise ValueError("office_types must map full office IRIs to category concept keys")
    normalized_types = {}
    for office_text, type_key in types.items():
        office = _office_iri(office_text, "office_types key")
        if type_key not in OFFICE_TYPE_KEYS:
            raise ValueError(f"office_types value is not a registered OfficeType concept key: {type_key!r}")
        normalized_types[str(office)] = type_key

    by_membership_and_range: dict[tuple[str, str], list[dict]] = {}
    for observation in observations:
        membership_text = str(observation["membership_iri"])
        range_key = canonical_json(observation["date_range"])
        by_membership_and_range.setdefault((membership_text, range_key), []).append(observation)

    normalized = []
    occurrence_context: dict[str, tuple[str, str, str]] = {}
    deduplicated: dict[tuple[str, str], dict] = {}
    current_keys: dict[tuple[str, str], set[str]] = {}
    for record in resolutions:
        if not isinstance(record, dict):
            raise ValueError("each office resolution must be an object")
        occurrence_key = record.get("occurrence_key")
        if not isinstance(occurrence_key, str) or not OCCURRENCE_KEY_RE.fullmatch(occurrence_key):
            raise ValueError("office resolution occurrence_key must be an occ- SHA-256 key")
        status = record.get("status")
        if status is not None and status != "accepted":
            raise ValueError("only accepted office resolutions may create an OfficeHolding")
        resolved_member = _source_iri(record.get("member_iri"), label="office resolution member_iri")
        membership = _source_iri(record.get("membership_iri"), label="office resolution membership_iri")
        office = _office_iri(record.get("office_iri"), "office resolution office_iri")
        dates = _resolution_date_range(record.get("date_range"))
        retained = _retained_resolution(record)
        if resolved_member != member:
            raise ValueError("office resolution member_iri does not match this Member")
        if str(membership) not in member_memberships:
            raise ValueError("office resolution membership_iri is not owned by this Member")
        date_key = canonical_json(dates)
        identity_context = (str(resolved_member), str(membership), date_key)
        prior_context = occurrence_context.setdefault(occurrence_key, identity_context)
        if prior_context != identity_context:
            raise ValueError("one office occurrence_key cannot identify different Member, membership, or dates")
        if not retained and (str(membership), date_key) not in by_membership_and_range:
            raise ValueError("office resolution does not match a valid current office observation")

        composite_key = (occurrence_key, str(office))
        item = {
            "occurrence_key": occurrence_key,
            "member_iri": resolved_member,
            "membership_iri": membership,
            "office_iri": office,
            "date_range": dates,
            "retained": retained,
            "office_type": normalized_types.get(str(office)),
        }
        old = deduplicated.get(composite_key)
        if old is not None:
            if (old["date_range"] != dates or old["membership_iri"] != membership
                    or old["member_iri"] != resolved_member):
                raise ValueError("duplicate office resolution identity has conflicting data")
            # An explicit accepted current record is at least as informative as
            # a retained copy of the same occurrence/office correspondence.
            if old["retained"] and not retained:
                deduplicated[composite_key] = item
                current_keys.setdefault((str(membership), date_key), set()).add(occurrence_key)
            continue
        deduplicated[composite_key] = item
        if not retained:
            current_keys.setdefault((str(membership), date_key), set()).add(occurrence_key)

    for (membership_text, date_key), keys in current_keys.items():
        source_count = len({canonical_json(item["raw_office"])
                            for item in by_membership_and_range[(membership_text, date_key)]})
        if len(keys) > source_count:
            raise ValueError("accepted office occurrences exceed distinct current source reports")

    for item in deduplicated.values():
        # A single accepted observation may identify several enduring offices;
        # include the office target in its stable correspondence key so each
        # person–office–occurrence holding has its own deterministic subject.
        occurrence_digest = hashlib.sha256(canonical_json({
            "kind": "office-holding-occurrence-v1",
            "occurrence_key": item["occurrence_key"],
            "office_iri": str(item["office_iri"]),
        })).hexdigest()
        item["holding_iri"] = URIRef(
            f"{member}#office-holding-{occurrence_digest}")
        normalized.append(item)
    normalized.sort(key=lambda item: (item["occurrence_key"], str(item["office_iri"])))

    # Report one unresolved occurrence per distinct valid source report. Exact
    # duplicate source reports are one accepted/reviewable correspondence.
    pending = []
    consumed: dict[tuple[str, str], int] = {
        key: len(values) for key, values in current_keys.items()
    }
    for (membership_text, date_key), reports in sorted(by_membership_and_range.items()):
        unique_reports = {}
        for observation in reports:
            fingerprint = canonical_json(observation["raw_office"])
            unique_reports.setdefault(fingerprint, observation)
        resolved_count = consumed.get((membership_text, date_key), 0)
        unresolved = sorted(unique_reports.items())[resolved_count:]
        for _, observation in unresolved:
            pending.append({
                "path": observation["path"],
                "context": membership_text,
                "reason": "No accepted office resolution was supplied; no OfficeHolding or role is emitted.",
                "category": "reconciliation_pending",
                "status": "unresolved",
            })
    return normalized, pending


def _date_only(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None


def _effective_end(raw_end: object):
    if raw_end is None:
        return None
    literal = datetime_literal(raw_end)
    end = literal.toPython()
    if _date_only(raw_end):
        try:
            return end + timedelta(days=1)
        except OverflowError as error:
            raise ValueError("office date-only end cannot be advanced for inclusive continuity") from error
    return end


def _cabinet_episodes(holdings: list[dict]) -> list[dict]:
    qualifying = [item for item in holdings
                  if item["office_type"] in CABINET_OFFICE_TYPES]
    intervals = []
    for item in qualifying:
        dates = item["date_range"]
        start_literal = datetime_literal(dates["start"])
        intervals.append({
            "start": start_literal.toPython(),
            "start_literal": start_literal,
            "end": datetime_literal(dates["end"]) if dates.get("end") is not None else None,
            "raw_end": dates.get("end"),
            "effective_end": _effective_end(dates.get("end")),
            "holding_iri": item["holding_iri"],
        })
    intervals.sort(key=lambda item: (item["start"], str(item["holding_iri"])))
    episodes: list[dict] = []
    for interval in intervals:
        if (not episodes or (episodes[-1]["effective_end"] is not None
                             and interval["start"] > episodes[-1]["effective_end"])):
            episodes.append({
                "start": interval["start"],
                "start_literal": interval["start_literal"],
                "end": interval["end"],
                "raw_end": interval["raw_end"],
                "effective_end": interval["effective_end"],
                "support": {interval["holding_iri"]},
            })
            continue
        episode = episodes[-1]
        episode["support"].add(interval["holding_iri"])
        if episode["effective_end"] is None:
            continue
        if (interval["effective_end"] is None
                or interval["effective_end"] > episode["effective_end"]
                or (interval["effective_end"] == episode["effective_end"]
                    and interval["end"] is not None
                    and episode["end"] is not None
                    and not _date_only(interval["raw_end"])
                    and _date_only(episode["raw_end"]))):
            episode["end"] = interval["end"]
            episode["raw_end"] = interval["raw_end"]
            episode["effective_end"] = interval["effective_end"]
    return episodes


def _cabinet_membership_iri(member: URIRef, start_literal: Literal) -> URIRef:
    identity = {
        "kind": "cabinet-membership-v1",
        "member_iri": str(member),
        "government_iri": str(GOVERNMENT),
        "start": str(start_literal),
    }
    digest = hashlib.sha256(json.dumps(
        identity, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return URIRef(f"{member}#cabinet-membership-{digest}")


def _add_office_graph(graph: Graph, member: URIRef, holdings: list[dict]) -> None:
    for item in holdings:
        holding = item["holding_iri"]
        office = item["office_iri"]
        graph.add((holding, RDF.type, MEMBERS.OfficeHolding))
        graph.add((member, MEMBERS.hasMembersMembership, holding))
        graph.add((holding, MEMBERS.heldOffice, office))
        graph.add((holding, MEMBERS.officeHolder, member))
        graph.add((member, MEMBERS.hasOfficeHolding, holding))
        _date_range(graph, holding, "date-range", item["date_range"])

    for episode in _cabinet_episodes(holdings):
        cabinet = _cabinet_membership_iri(member, episode["start_literal"])
        role = URIRef(f"{cabinet}#role")
        graph.add((cabinet, RDF.type, MEMBERS.CabinetMembership))
        graph.add((member, MEMBERS.hasMembersMembership, cabinet))
        graph.add((cabinet, MEMBERS.isCabinetMembershipOf, GOVERNMENT))
        graph.add((cabinet, MEMBERS.hasCabinetRole, role))
        graph.add((role, RDF.type, MEMBERS.CabinetMember))
        graph.add((role, ORG.heldBy, member))
        for holding in sorted(episode["support"], key=str):
            graph.add((cabinet, MEMBERS.supportedByOfficeHolding, holding))
        date_range = {
            "start": str(episode["start_literal"]),
            "end": str(episode["end"]) if episode["end"] is not None else None,
        }
        _date_range(graph, cabinet, "date-range", date_range)


def transform_member_with_report(
        wrapper: dict, *, office_resolutions: list[dict] | None = None,
        office_types: Mapping[str, str] | None = None) -> tuple[Graph, list[dict]]:
    """Transform one Member and return source omissions/quarantine reports.

    ``office_resolutions`` is an optional list of effective accepted holding
    records with ``occurrence_key``, ``member_iri``, ``membership_iri``,
    ``office_iri`` and ``date_range``. Repeat an occurrence key for each local
    office target when one source report resolves to multiple offices. A
    retained accepted record may set ``missing_retained``/``retained`` or a
    ``retention_status`` of ``missing_retained`` or ``conflict_retained``.
    ``office_types`` maps full local office IRIs to registered OfficeType
    concept keys. With both arguments omitted, no holdings are resolved.
    """
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
    valid_office_observations: list[dict] = []
    member_memberships: set[str] = set()
    for number, wrapper_membership in enumerate(memberships):
        if not isinstance(wrapper_membership, dict) or not isinstance(wrapper_membership.get("membership"), dict): raise ValueError("membership wrapper must contain a membership object")
        record = wrapper_membership["membership"]; membership = _source_iri(record.get("uri"), label="membership.uri"); house = record.get("house")
        member_memberships.add(str(membership))
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
        parties = record.get("parties", [])
        if not isinstance(parties, list):
            raise ValueError("membership.parties must be an array")
        for party_index, wrapped_party in enumerate(parties):
            party, party_uri, party_code = parse_party_identity(wrapped_party, str(membership))
            reason = party_date_range_error(party)
            if reason is not None:
                exclusions.append(malformed_party_report(
                    membership_index=number, party_index=party_index,
                    membership_uri=str(membership), member_uri=str(subject),
                    party=party, party_uri=party_uri, party_code=party_code,
                    wrapped=wrapped_party, reason=reason,
                ))
                continue
            _party(graph, subject, membership, wrapped_party,
                   identity=(party, party_uri, party_code))
        committees = record.get("committees", [])
        if not isinstance(committees, list):
            raise ValueError("membership.committees must be an array")
        for committee in committees:
            _committee(graph, subject, membership, committee, exclusions,
                       "member.memberships[].membership.committees[]")
        offices = record.get("offices", [])
        if not isinstance(offices, list):
            raise ValueError("membership.offices must be an array")
        for office_index, office in enumerate(offices):
            try:
                office_data, _name, _label, _source_uri, dates = parse_office_observation(office)
            except ValueError as error:
                exclusions.append({
                    "path": f"member.memberships[{number}].membership.offices[{office_index}]",
                    "context": str(membership),
                    "reason": str(error),
                    "category": "source_quarantine",
                    "status": "review_required",
                })
                continue
            valid_office_observations.append({
                "membership_iri": membership,
                "raw_office": office_data,
                "date_range": {"start": dates["start"], "end": dates.get("end")},
                "path": f"member.memberships[{number}].membership.offices[{office_index}]",
            })
    holdings, pending = _office_resolution_records(
        subject, valid_office_observations, office_resolutions, office_types,
        member_memberships)
    _add_office_graph(graph, subject, holdings)
    exclusions.extend(pending)
    return graph, sorted(exclusions, key=lambda value: (value["category"], value["path"], value["context"], value["reason"]))


def transform_member(wrapper: dict, *, office_resolutions: list[dict] | None = None,
                     office_types: Mapping[str, str] | None = None) -> Graph:
    return transform_member_with_report(
        wrapper, office_resolutions=office_resolutions,
        office_types=office_types)[0]
