"""Deterministic, auditable consolidation of owner references in Members.

This module deliberately does not own RDF transformation.  It validates and
consolidates source observations into the existing Party and Constituency
logical-record contracts, and into the initial Committee owner contract.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from .transforms.common import datetime_literal


MEMBER_REFERENCE_KINDS = ("party", "representation", "committee")
REFERENCE_TO_ENDPOINT = {
    "party": "parties",
    "representation": "constituencies",
    "committee": "committees",
}
PARTY_PATH = ("ie", "oireachtas", "party")
REPRESENTATION_PATH = ("ie", "oireachtas", "house")
COMMITTEE_PATH = ("ie", "oireachtas", "committee")
HOUSE_TERM_RE = re.compile(r"^https://data\.oireachtas\.ie/ie/oireachtas/house/(dail|seanad)/([1-9][0-9]*)$")

COMMITTEE_TYPES = {"Select", "Joint", "Special"}
COMMITTEE_PURPOSES = {"Policy", "Shadow Department"}


def _source_iri(value: object) -> str:
    if not isinstance(value, str) or any(character.isspace() for character in value):
        raise ValueError("source IRI must be a canonical Oireachtas HTTPS IRI")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("source IRI must be a canonical Oireachtas HTTPS IRI") from error
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or port or not parsed.path):
        raise ValueError("source IRI must be a canonical Oireachtas HTTPS IRI")
    return value


def _path(iri: str) -> list[str]:
    raw = urlsplit(iri).path
    parts = raw.split("/")
    if len(parts) < 2 or parts[0] != "" or any(not part for part in parts[1:]):
        raise ValueError("source IRI path must not contain empty segments")
    return parts[1:]


def _normal_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("value must be a non-empty string")
    return unicodedata.normalize("NFC", value.strip())


def _normal_number(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("value must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value):
        return int(value)
    raise ValueError("value must be an integer")


def _normal_datetime(value: object) -> str:
    literal = datetime_literal(value)
    parsed = literal.toPython()
    if isinstance(parsed, datetime) and parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat(timespec="seconds")


def _term_context(house: object) -> tuple[str, str, str]:
    if not isinstance(house, dict):
        raise ValueError("membership house context must be an object")
    term = _source_iri(house.get("uri"))
    match = HOUSE_TERM_RE.fullmatch(term)
    code, number = house.get("houseCode"), house.get("houseNo")
    if (not match or code not in {"dail", "seanad"}
            or match.group(1) != code or match.group(2) != str(number)):
        raise ValueError("membership house context must identify its canonical HouseTerm")
    return term, code, str(number)


def committee_identity(value: object, *, house_code: object = None,
                       house_no: object = None) -> tuple[str, str, str, str]:
    """Return (canonical IRI, HouseTerm IRI, houseCode, houseNo)."""
    iri = _source_iri(value)
    parts = _path(iri)
    if len(parts) != 6 or tuple(parts[:3]) != COMMITTEE_PATH:
        raise ValueError("Committee IRI must match /ie/oireachtas/committee/{houseCode}/{houseNo}/{slug}")
    _root, _oireachtas, _committee, code, number, slug = parts
    if (code not in {"dail", "seanad"} or not re.fullmatch(r"[1-9][0-9]*", number)
            or not slug or "/" in unquote(slug)):
        raise ValueError("Committee IRI must match /ie/oireachtas/committee/{houseCode}/{houseNo}/{slug}")
    if house_code is not None and _normal_string(house_code) != code:
        raise ValueError("committee.houseCode must agree with the Committee IRI")
    if house_no is not None and str(_normal_number(house_no)) != number:
        raise ValueError("committee.houseNo must agree with the Committee IRI")
    term = f"https://data.oireachtas.ie/ie/oireachtas/house/{code}/{number}"
    return iri, term, code, number


def _owner_fields(kind: str, value: dict) -> dict:
    if kind == "party":
        names = ("partyCode", "showAs")
    elif kind == "representation":
        names = ("representType", "representCode", "showAs")
    else:
        names = ("committeeCode", "committeeID", "committeeType",
                 "committeeDateRange", "committeeName", "houseCode", "houseNo")
    return {name: value[name] for name in names if name in value}


def _observation(*, kind: str, uri: object, source: str, member_iri: str | None,
                 source_record: str, source_path: str, house_context: str | None,
                 fields: dict, raw: dict, complete: bool) -> dict:
    try:
        canonical = _source_iri(uri)
        identity_error = None
    except ValueError as error:
        canonical = None
        identity_error = str(error)
    return {
        "reference_kind": kind,
        "canonical_iri": canonical,
        "raw_iri": uri,
        "member_iri": member_iri,
        "source_record": source_record,
        "json_pointer": source_path,
        "house_term_context": house_context,
        "owner_relevant_fields": fields,
        "source_fields": raw,
        "normalized_comparison_values": {},
        "observation_source": source,
        "source_capture_complete_authoritative": bool(complete),
        "identity_error": identity_error,
    }


def extract_member_observations(records: list[dict], *, complete: bool) -> list[dict]:
    """Extract every nested Party, representation and Committee reference."""
    result: list[dict] = []
    for record_index, wrapper in enumerate(records):
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
            raise ValueError(f"Members record {record_index} must contain a member object")
        member = wrapper["member"]
        member_iri = member.get("uri")
        try:
            member_iri = _source_iri(member_iri)
        except ValueError:
            member_iri = str(member_iri) if member_iri is not None else None
        memberships = member.get("memberships", [])
        if not isinstance(memberships, list):
            raise ValueError(f"Members record {record_index} memberships must be an array")
        for membership_index, wrapped in enumerate(memberships):
            if not isinstance(wrapped, dict) or not isinstance(wrapped.get("membership"), dict):
                raise ValueError(f"Members record {record_index} membership must contain a membership object")
            membership = wrapped["membership"]
            membership_iri = membership.get("uri")
            try:
                membership_iri = _source_iri(membership_iri)
            except ValueError:
                membership_iri = str(membership_iri) if membership_iri is not None else ""
            house = membership.get("house")
            try:
                house_term = _term_context(house)[0]
            except ValueError:
                house_term = None
            base = f"/results/{record_index}/member/memberships/{membership_index}/membership"

            parties = membership.get("parties", [])
            if not isinstance(parties, list):
                raise ValueError(f"{base}/parties must be an array")
            for item_index, wrapped_party in enumerate(parties):
                party = wrapped_party.get("party") if isinstance(wrapped_party, dict) else None
                if not isinstance(party, dict):
                    party = {}
                result.append(_observation(
                    kind="party", uri=party.get("uri"), source="members",
                    member_iri=member_iri, source_record=membership_iri,
                    source_path=f"{base}/parties/{item_index}/party",
                    house_context=house_term, fields=_owner_fields("party", party),
                    raw=party, complete=complete,
                ))

            representations = membership.get("represents", [])
            if not isinstance(representations, list):
                raise ValueError(f"{base}/represents must be an array")
            for item_index, wrapped_representation in enumerate(representations):
                representation = (wrapped_representation.get("represent")
                                  if isinstance(wrapped_representation, dict) else None)
                if not isinstance(representation, dict):
                    representation = {}
                result.append(_observation(
                    kind="representation", uri=representation.get("uri"), source="members",
                    member_iri=member_iri, source_record=membership_iri,
                    source_path=f"{base}/represents/{item_index}/represent",
                    house_context=house_term,
                    fields=_owner_fields("representation", representation),
                    raw=representation, complete=complete,
                ))

            committees = membership.get("committees", [])
            if not isinstance(committees, list):
                raise ValueError(f"{base}/committees must be an array")
            for item_index, committee in enumerate(committees):
                raw = committee if isinstance(committee, dict) else {}
                # Keep relationship evidence in the census, but never feed it
                # to the Committee owner transformer.
                result.append(_observation(
                    kind="committee", uri=raw.get("uri"), source="members",
                    member_iri=member_iri, source_record=membership_iri,
                    source_path=f"{base}/committees/{item_index}",
                    house_context=house_term, fields=_owner_fields("committee", raw),
                    raw=raw, complete=complete,
                ))
    return result


def extract_endpoint_observations(records: list[dict], *, endpoint: str,
                                  complete: bool = True) -> list[dict]:
    if endpoint == "parties":
        kind, object_key = "party", "party"
    elif endpoint == "constituencies":
        kind, object_key = "representation", "constituencyOrPanel"
    else:
        raise ValueError(f"unsupported reference observation source: {endpoint}")
    result = []
    for index, wrapper in enumerate(records):
        value = wrapper.get(object_key) if isinstance(wrapper, dict) else None
        if not isinstance(value, dict):
            value = {}
        house = wrapper.get("house") if isinstance(wrapper, dict) else None
        try:
            term = _term_context(house)[0]
        except ValueError:
            term = None
        result.append(_observation(
            kind=kind, uri=value.get("uri"), source=endpoint,
            member_iri=None, source_record=str(value.get("uri") or f"{endpoint}[{index}]"),
            source_path=f"/results/{index}/{object_key}", house_context=term,
            fields=_owner_fields(kind, value), raw=value, complete=complete,
        ))
    return result


def _base_validation(observation: dict) -> tuple[str, dict]:
    if observation.get("identity_error") or not observation.get("canonical_iri"):
        raise ValueError(observation.get("identity_error") or "reference IRI is missing")
    kind, iri = observation["reference_kind"], observation["canonical_iri"]
    fields = observation["owner_relevant_fields"]
    values: dict = {"source_iri": iri}
    if kind == "party":
        house_term = observation.get("house_term_context")
        if not isinstance(house_term, str):
            raise ValueError("Party observation lacks a valid HouseTerm context")
        match = HOUSE_TERM_RE.fullmatch(house_term)
        if not match:
            raise ValueError("Party observation lacks a valid HouseTerm context")
        path = _path(iri)
        if (len(path) != 6 or tuple(path[:3]) != PARTY_PATH
                or path[3] != match.group(1) or path[4] != match.group(2)):
            raise ValueError("party.uri must embed its observed HouseTerm")
        code = fields.get("partyCode")
        if not isinstance(code, str) or not code or unquote(path[5]) != code:
            raise ValueError("party.uri must match partyCode")
        values.update({"partyCode": _normal_string(code), "houseTerm": house_term})
        if fields.get("showAs") is not None:
            values["showAs"] = _normal_string(fields["showAs"])
    elif kind == "representation":
        house_term = observation.get("house_term_context")
        match = HOUSE_TERM_RE.fullmatch(house_term) if isinstance(house_term, str) else None
        if not match:
            raise ValueError("representation observation lacks a valid HouseTerm context")
        path = _path(iri)
        represent_type, code = fields.get("representType"), fields.get("representCode")
        expected_house = "dail" if represent_type == "constituency" else "seanad" if represent_type == "panel" else None
        if expected_house is None or expected_house != match.group(1):
            raise ValueError("representation type is incompatible with its observed HouseTerm")
        if (len(path) != 7 or tuple(path[:5]) != tuple(_path(house_term))
                or path[5] != represent_type or not isinstance(code, str)
                or not code or unquote(path[6]) != code):
            raise ValueError("constituencyOrPanel.uri must match HouseTerm, representType and representCode")
        values.update({"representType": represent_type,
                       "representCode": _normal_string(code),
                       "houseTerm": house_term})
        if fields.get("showAs") is not None:
            values["showAs"] = _normal_string(fields["showAs"])
    else:
        try:
            iri, term, code, number = committee_identity(
                iri, house_code=fields.get("houseCode"), house_no=fields.get("houseNo"))
        except ValueError as error:
            for field, normalizer in (("houseCode", _normal_string),
                                      ("houseNo", _normal_number)):
                if fields.get(field) is None:
                    continue
                try:
                    normalizer(fields[field])
                except ValueError as field_error:
                    _mark_uncomparable_field(observation, field, field_error)
            raise error
        values.update({"houseTerm": term, "houseCode": code, "houseNo": number})
        if fields.get("committeeCode") is not None:
            try:
                values["committeeCode"] = _normal_string(fields["committeeCode"])
            except ValueError as error:
                _mark_uncomparable_field(observation, "committeeCode", error)
        if fields.get("committeeID") is not None:
            try:
                values["committeeID"] = _normal_number(fields["committeeID"])
            except ValueError as error:
                _mark_uncomparable_field(observation, "committeeID", error)
        raw_types = fields.get("committeeType")
        if raw_types is not None:
            type_values: set[str] = set()
            purpose_values: set[str] = set()
            unsupported: set[str] = set()
            if not isinstance(raw_types, list):
                _mark_uncomparable_field(
                    observation, "committeeType",
                    ValueError("committeeType must be an array of strings"))
            else:
                for index, raw_type in enumerate(raw_types):
                    try:
                        value = _normal_string(raw_type)
                    except ValueError as error:
                        _mark_uncomparable_field(
                            observation, "committeeType", error,
                            suffix=f"/{index}")
                        continue
                    if value in COMMITTEE_TYPES:
                        type_values.add(value)
                    elif value in COMMITTEE_PURPOSES:
                        purpose_values.add(value)
                    else:
                        unsupported.add(value)
            type_values = sorted(type_values)
            purpose_values = sorted(purpose_values)
            unsupported = sorted(unsupported)
            if type_values:
                values["committeeTypes"] = type_values
            if purpose_values:
                values["committeePurposes"] = purpose_values
            if unsupported:
                observation.setdefault("diagnostics", []).append({
                    "category": "unsupported_committee_classification",
                    "path": observation["json_pointer"] + "/committeeType",
                    "values": unsupported,
                    "reason": "No existing controlled Committee type/purpose concept maps this source value.",
                })
        range_value = fields.get("committeeDateRange")
        if range_value is not None:
            try:
                if not isinstance(range_value, dict):
                    raise ValueError("committeeDateRange must be an object")
                if range_value.get("start") is None:
                    raise ValueError("committeeDateRange.start is required")
                start = _normal_datetime(range_value["start"])
                end = (_normal_datetime(range_value["end"])
                       if range_value.get("end") is not None else None)
                if end is not None and datetime.fromisoformat(end) < datetime.fromisoformat(start):
                    raise ValueError("committeeDateRange has reverse dates")
                values["committeeDateRange.start"] = start
                if end is not None:
                    values["committeeDateRange.end"] = end
            except (TypeError, ValueError) as error:
                _mark_uncomparable_field(observation, "committeeDateRange", error)
        # Name intervals are accumulated and compared by validity below. They
        # are not flattened encounter-order values.
    observation["normalized_comparison_values"] = values
    return iri, values


def _mark_uncomparable_field(observation: dict, field: str,
                             error: ValueError, *, suffix: str = "") -> None:
    """Retain malformed non-null field evidence without discarding the identity."""
    raw = observation["owner_relevant_fields"].get(field)
    observation.setdefault("uncomparable_owner_fields", {}).setdefault(field, []).append(raw)
    observation.setdefault("diagnostics", []).append({
        "category": "malformed_observation",
        "path": observation["json_pointer"] + "/" + field + suffix,
        "reason": str(error),
    })


def _partial_comparison_values(observation: dict) -> dict:
    """Safely compare valid owner fields on an otherwise malformed observation.

    These values can reveal a conflict, but are never used to construct an RDF
    owner record. The full observation must pass ``_base_validation`` to do so.
    """
    if observation.get("reference_kind") != "committee":
        return {}
    fields = observation["owner_relevant_fields"]
    try:
        _identity, term, code, number = committee_identity(
            observation.get("canonical_iri"))
    except ValueError:
        return {}
    values = {"houseTerm": term}
    for field, normalizer in (("houseCode", _normal_string),
                              ("houseNo", _normal_number),
                              ("committeeCode", _normal_string),
                              ("committeeID", _normal_number)):
        raw = fields.get(field)
        if raw is None:
            if field == "houseCode":
                values[field] = code
            elif field == "houseNo":
                values[field] = number
            continue
        try:
            values[field] = normalizer(raw)
        except ValueError:
            continue
    raw_types = fields.get("committeeType")
    if isinstance(raw_types, list):
        types: set[str] = set()
        purposes: set[str] = set()
        for raw in raw_types:
            try:
                value = _normal_string(raw)
            except ValueError:
                continue
            if value in COMMITTEE_TYPES:
                types.add(value)
            elif value in COMMITTEE_PURPOSES:
                purposes.add(value)
        if types:
            values["committeeTypes"] = sorted(types)
        if purposes:
            values["committeePurposes"] = sorted(purposes)
    range_value = fields.get("committeeDateRange")
    if isinstance(range_value, dict) and range_value.get("start") is not None:
        try:
            start = _normal_datetime(range_value["start"])
            end = (_normal_datetime(range_value["end"])
                   if range_value.get("end") is not None else None)
            if end is None or datetime.fromisoformat(end) >= datetime.fromisoformat(start):
                values["committeeDateRange.start"] = start
                if end is not None:
                    values["committeeDateRange.end"] = end
        except (TypeError, ValueError):
            pass
    return values


def _committee_name_entries(observation: dict) -> list[dict]:
    names = observation["owner_relevant_fields"].get("committeeName")
    if names is None:
        return []
    if not isinstance(names, list):
        observation.setdefault("diagnostics", []).append({
            "category": "malformed_observation",
            "path": observation["json_pointer"] + "/committeeName",
            "reason": "committeeName must be an array",
        })
        return []
    result = []
    for index, name in enumerate(names):
        path = f"{observation['json_pointer']}/committeeName/{index}"
        if not isinstance(name, dict):
            observation.setdefault("diagnostics", []).append({
                "category": "malformed_observation", "path": path,
                "reason": "Committee name entry must be an object",
            })
            continue
        validity = name.get("dateRange")
        if not isinstance(validity, dict) or validity.get("start") is None:
            observation.setdefault("diagnostics", []).append({
                "category": "committee_name_ambiguity", "path": path,
                "reason": "Committee name has no valid start date, so its latest/current status cannot be established.",
            })
            continue
        try:
            start = _normal_datetime(validity["start"])
            end = _normal_datetime(validity["end"]) if validity.get("end") is not None else None
            if end is not None and datetime.fromisoformat(end) < datetime.fromisoformat(start):
                raise ValueError("Committee name dateRange has reverse dates")
        except (TypeError, ValueError) as error:
            observation.setdefault("diagnostics", []).append({
                "category": "committee_name_ambiguity", "path": path,
                "reason": str(error),
            })
            continue
        entry = {"start": start, "end": end, "path": path}
        for field, language in (("nameEn", "en"), ("nameGa", "ga")):
            raw = name.get(field)
            if raw is None:
                continue
            try:
                entry[language] = {"lexical": raw, "normalized": _normal_string(raw)}
            except ValueError as error:
                observation.setdefault("diagnostics", []).append({
                    "category": "committee_name_ambiguity",
                    "path": path + "/" + field, "reason": str(error),
                })
        result.append(entry)
    return result


def _latest_name(entries: list[dict], language: str) -> tuple[str | None, dict | None]:
    candidates = [entry for entry in entries if language in entry]
    if not candidates:
        return None, None
    # Open-ended intervals are the source's current-name evidence. If none is
    # open-ended, the latest valid interval is the defensible historical name.
    current = [entry for entry in candidates if entry["end"] is None]
    pool = current or candidates
    latest = max(entry["start"] for entry in pool)
    selected = [entry for entry in pool if entry["start"] == latest]
    values = {entry[language]["normalized"] for entry in selected}
    if len(values) != 1:
        return None, {
            "category": "committee_name_ambiguity",
            "language": language,
            "valid_from": latest,
            "values": sorted(values),
            "paths": sorted(entry["path"] for entry in selected),
            "reason": "There is no unique latest/current Committee name for this language.",
        }
    normalized = next(iter(values))
    # Equivalent source lexical forms collapse independently of encounter order.
    lexical = min(entry[language]["lexical"] for entry in selected
                  if entry[language]["normalized"] == normalized)
    return lexical, None


def build_reference_census(*, member_records: list[dict],
                           party_records: list[dict] | None = None,
                           constituency_records: list[dict] | None = None,
                           member_capture_complete: bool,
                           party_capture_complete: bool = False,
                           constituency_capture_complete: bool = False) -> dict:
    """Build deterministic per-observation evidence and consolidated records."""
    observations = extract_member_observations(
        member_records, complete=member_capture_complete)
    observations.extend(extract_endpoint_observations(
        party_records or [], endpoint="parties", complete=party_capture_complete))
    observations.extend(extract_endpoint_observations(
        constituency_records or [], endpoint="constituencies",
        complete=constituency_capture_complete))

    by_identity: dict[tuple[str, str], list[dict]] = defaultdict(list)
    invalid: list[dict] = []
    for item in observations:
        if not item.get("canonical_iri"):
            item["consolidation_result"] = "malformed_observation"
            item["diagnostics"] = [{
                "category": "malformed_observation",
                "path": item["json_pointer"],
                "reason": item.get("identity_error") or "reference IRI is missing",
            }]
            invalid.append(item)
            continue
        by_identity[(item["reference_kind"], item["canonical_iri"])].append(item)

    consolidated = {"parties": [], "constituencies": [], "committees": []}
    insufficient: list[dict] = []
    conflicts: list[dict] = []
    ambiguities: list[dict] = []
    malformed: list[dict] = list(invalid)
    identity_results: list[dict] = []

    for (kind, identity), group in sorted(by_identity.items()):
        group.sort(key=lambda item: (item["observation_source"],
                                     item.get("member_iri") or "",
                                     item["json_pointer"],
                                     json.dumps(item["source_fields"], ensure_ascii=False,
                                                sort_keys=True, separators=(",", ":"))))
        valid: list[tuple[dict, dict]] = []
        partial: list[tuple[dict, dict]] = []
        for item in group:
            try:
                _, normalized = _base_validation(item)
                valid.append((item, normalized))
            except (TypeError, ValueError) as error:
                normalized = _partial_comparison_values(item)
                item["normalized_comparison_values"] = normalized
                if normalized:
                    partial.append((item, normalized))
                diagnostic = {
                    "category": "malformed_observation",
                    "reference_kind": kind,
                    "canonical_iri": identity,
                    "observation_source": item["observation_source"],
                    "member_iri": item.get("member_iri"),
                    "path": item["json_pointer"],
                    "reason": str(error),
                }
                item.setdefault("diagnostics", []).append(diagnostic)
                malformed.append(diagnostic)
        comparable = valid + partial
        sources = sorted({item["observation_source"] for item, _ in comparable})
        field_values: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for item, normalized in comparable:
            for field, value in normalized.items():
                if value is None or field == "source_iri":
                    continue
                canonical_value = json.dumps(value, ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":"))
                field_values[field][canonical_value].append(item)

        identity_conflicts = []
        for field, values in sorted(field_values.items()):
            if len(values) <= 1:
                continue
            competing = []
            for normalized_value, evidence in sorted(values.items()):
                competing.append({
                    "normalized_value": json.loads(normalized_value),
                    "observations": [{
                        "source": item["observation_source"],
                        "member_iri": item.get("member_iri"),
                        "path": item["json_pointer"],
                        "value": item["owner_relevant_fields"].get(field),
                        "owner_relevant_fields": item["owner_relevant_fields"],
                    } for item in evidence],
                })
            identity_conflicts.append({"field": field, "evidence": competing})

        # A malformed value cannot be silently ignored when another observation
        # supplies a comparable value for that same mapped owner field. Preserve
        # it as competing, explicitly uncomparable evidence instead.
        conflict_fields = {item["field"] for item in identity_conflicts}
        field_aliases = {
            "committeeType": ("committeeTypes", "committeePurposes"),
            "committeeDateRange": (
                "committeeDateRange.start", "committeeDateRange.end"),
        }
        for item in group:
            for field, raw_values in sorted(
                    item.get("uncomparable_owner_fields", {}).items()):
                if field in conflict_fields:
                    continue
                comparable_fields = field_aliases.get(field, (field,))
                values = {name: field_values.get(name, {})
                          for name in comparable_fields
                          if field_values.get(name)}
                if not values:
                    continue
                evidence = []
                for name in sorted(values):
                    for normalized_value, observations_for_value in sorted(
                            values[name].items()):
                        evidence.append({
                            "normalized_value": {name: json.loads(normalized_value)},
                            "observations": [{
                                "source": other["observation_source"],
                                "member_iri": other.get("member_iri"),
                                "path": other["json_pointer"],
                                "value": other["owner_relevant_fields"].get(field),
                                "owner_relevant_fields": other["owner_relevant_fields"],
                            } for other in observations_for_value],
                        })
                evidence.append({
                    "normalized_value": {"uncomparable": True},
                    "observations": [{
                        "source": item["observation_source"],
                        "member_iri": item.get("member_iri"),
                        "path": item["json_pointer"],
                        "value": raw_value,
                        "owner_relevant_fields": item["owner_relevant_fields"],
                        "diagnostics": [diagnostic for diagnostic in
                                        item.get("diagnostics", [])
                                        if diagnostic.get("category") == "malformed_observation"],
                    } for raw_value in raw_values],
                })
                identity_conflicts.append({"field": field, "evidence": evidence})
                conflict_fields.add(field)

        name_entries: list[dict] = []
        if kind == "committee":
            for item, _ in valid:
                name_entries.extend(_committee_name_entries(item))
                for diagnostic in item.get("diagnostics", []):
                    if diagnostic.get("category") == "committee_name_ambiguity":
                        ambiguities.append({
                            "category": "committee_name_ambiguity",
                            "reference_kind": kind,
                            "canonical_iri": identity,
                            "observation_source": item["observation_source"],
                            "member_iri": item.get("member_iri"),
                            **diagnostic,
                        })
            en_name, en_ambiguity = _latest_name(name_entries, "en")
            ga_name, ga_ambiguity = _latest_name(name_entries, "ga")
            for ambiguity in (en_ambiguity, ga_ambiguity):
                if ambiguity:
                    ambiguity.update({"reference_kind": kind,
                                      "canonical_iri": identity})
                    ambiguities.append(ambiguity)

        for item, _ in valid:
            for diagnostic in item.get("diagnostics", []):
                if diagnostic.get("category") == "malformed_observation":
                    malformed.append({
                        "reference_kind": kind,
                        "canonical_iri": identity,
                        "observation_source": item["observation_source"],
                        "member_iri": item.get("member_iri"),
                        **diagnostic,
                    })

        required = ({"partyCode", "showAs", "houseTerm"} if kind == "party" else
                    {"representType", "representCode", "showAs", "houseTerm"}
                    if kind == "representation" else {"houseTerm"})
        selected: dict = {}
        for field in sorted(required | (set().union(*(set(n) for _, n in valid)) if valid else set())):
            if field == "source_iri":
                continue
            choices = [(item, normalized[field]) for item, normalized in valid
                       if field in normalized and normalized[field] is not None]
            if not choices:
                continue
            # Prefer endpoint lexical values for Party/Constituency fields when
            # safe normalization proved the values equivalent.
            choices.sort(key=lambda pair: (
                0 if pair[0]["observation_source"] in {"parties", "constituencies"} else 1,
                pair[0].get("member_iri") or "", pair[0]["json_pointer"],
                json.dumps(pair[0]["owner_relevant_fields"], ensure_ascii=False,
                           sort_keys=True, separators=(",", ":")),
            ))
            selected[field] = choices[0][1]

        missing = sorted(field for field in required if field not in selected)
        if kind == "committee" and valid:
            selected["committeeNameEn"] = en_name
            selected["committeeNameGa"] = ga_name
        is_conflict = bool(identity_conflicts)
        closable = bool(valid) and not missing
        if is_conflict:
            result = ("overlap/conflicting" if "members" in sources and len(sources) > 1
                      else "members-conflicting" if "members" in sources
                      else "endpoint-conflicting")
        elif not closable:
            result = "insufficient-evidence"
        elif "members" in sources and any(source != "members" for source in sources):
            result = "overlap/concordant"
        elif sources == ["members"]:
            result = "members-only"
        else:
            result = "endpoint-only"

        identity_entry = {
            "reference_kind": kind,
            "canonical_iri": identity,
            "sources": sources,
            "observation_count": len(group),
            "valid_observation_count": len(valid),
            "coverage_class": result,
            "consolidation_result": "conflicting" if is_conflict else
                                    "resolved" if closable else "insufficient_evidence",
            "closable": closable and not is_conflict,
            "missing_owner_fields": missing,
            "conflicts": identity_conflicts,
        }
        identity_results.append(identity_entry)
        for item in group:
            item["consolidation_result"] = identity_entry["consolidation_result"]
            item["coverage_class"] = result
            item.setdefault("diagnostics", [])
        if is_conflict:
            conflict_entry = {**identity_entry,
                              "diagnostics": identity_conflicts}
            conflicts.append(conflict_entry)
        if not closable:
            insufficient.append({**identity_entry,
                                 "reason": "Required owner evidence is missing or every observation is malformed."})

        if not closable or is_conflict:
            continue
        if kind == "party":
            # Code/label lexical forms are selected from source observations;
            # normalized values are used only for comparison.
            lexical = {}
            for field in ("partyCode", "showAs"):
                candidates = [(item, item["owner_relevant_fields"].get(field))
                              for item, normalized in valid
                              if normalized.get(field) is not None]
                if candidates:
                    candidates.sort(key=lambda pair: (
                        0 if pair[0]["observation_source"] == "parties" else 1,
                        pair[0].get("member_iri") or "", pair[0]["json_pointer"],
                        str(pair[1]),
                    ))
                    lexical[field] = candidates[0][1]
            house = _house_from_term(selected["houseTerm"])
            consolidated["parties"].append({
                "party": {"uri": identity, "partyCode": lexical["partyCode"],
                          "showAs": lexical["showAs"]},
                "house": house,
            })
        elif kind == "representation":
            lexical = {}
            for field in ("representType", "representCode", "showAs"):
                candidates = [(item, item["owner_relevant_fields"].get(field))
                              for item, normalized in valid
                              if normalized.get(field) is not None]
                candidates.sort(key=lambda pair: (
                    0 if pair[0]["observation_source"] == "constituencies" else 1,
                    pair[0].get("member_iri") or "", pair[0]["json_pointer"],
                    str(pair[1]),
                ))
                lexical[field] = candidates[0][1]
            consolidated["constituencies"].append({
                "constituencyOrPanel": {"uri": identity,
                                         "representType": lexical["representType"],
                                         "representCode": lexical["representCode"],
                                         "showAs": lexical["showAs"]},
                "house": _house_from_term(selected["houseTerm"]),
            })
        else:
            committee = {"uri": identity}
            for field in ("committeeCode", "committeeID"):
                choices = [(item, item["owner_relevant_fields"].get(field))
                           for item, normalized in valid if normalized.get(field) is not None]
                if choices:
                    choices.sort(key=lambda pair: (pair[0].get("member_iri") or "",
                                                   pair[0]["json_pointer"], str(pair[1])))
                    committee[field] = choices[0][1]
            known_types = selected.get("committeeTypes", [])
            known_purposes = selected.get("committeePurposes", [])
            committee["committeeType"] = sorted(set(known_types) | set(known_purposes))
            if selected.get("committeeDateRange.start"):
                committee["committeeDateRange"] = {
                    "start": selected["committeeDateRange.start"],
                    "end": selected.get("committeeDateRange.end"),
                }
            committee["committeeName"] = _serialize_latest_names(
                name_entries, identity, ambiguities)
            consolidated["committees"].append(committee)

    observations.sort(key=lambda item: (
        item["reference_kind"], item.get("canonical_iri") or "",
        item["observation_source"], item.get("member_iri") or "",
        item["json_pointer"],
        json.dumps(item["owner_relevant_fields"], ensure_ascii=False,
                   sort_keys=True, separators=(",", ":")),
    ))
    identity_results.sort(key=lambda item: (item["reference_kind"], item["canonical_iri"]))
    for values in consolidated.values():
        values.sort(key=lambda item: item.get("party", item.get(
            "constituencyOrPanel", item)).get("uri", ""))

    coverage_counts = {}
    for kind in MEMBER_REFERENCE_KINDS:
        counts = Counter(item["coverage_class"] for item in identity_results
                         if item["reference_kind"] == kind)
        coverage_counts[kind] = {name: counts.get(name, 0) for name in (
            "endpoint-only", "members-only", "overlap/concordant",
            "overlap/conflicting", "members-conflicting",
            "endpoint-conflicting", "insufficient-evidence")}
    report = {
        "schema_version": 1,
        "capture_completeness": {
            "members": bool(member_capture_complete),
            "parties": bool(party_capture_complete),
            "constituencies": bool(constituency_capture_complete),
        },
        "totals": {
            "observations": len(observations),
            "distinct_identities": len(identity_results),
            "identities_by_kind": {
                kind: sum(entry["reference_kind"] == kind for entry in identity_results)
                for kind in MEMBER_REFERENCE_KINDS
            },
            "observations_by_kind": {
                kind: sum(item["reference_kind"] == kind for item in observations)
                for kind in MEMBER_REFERENCE_KINDS
            },
        },
        "coverage_counts_by_kind": coverage_counts,
        "coverage_counts_total": dict(sorted(Counter(
            item["coverage_class"] for item in identity_results).items())),
        "closable_identities": sum(bool(item["closable"]) for item in identity_results),
        "conflicting_identities": len(conflicts),
        "insufficient_evidence_identities": len(insufficient),
        "malformed_observation_count": len(malformed),
        "committee_name_ambiguity_count": len(ambiguities),
        "observations": observations,
        "identities": identity_results,
        "conflicts": sorted(conflicts, key=lambda item: (
            item["reference_kind"], item["canonical_iri"])),
        "insufficient_evidence": sorted(insufficient, key=lambda item: (
            item["reference_kind"], item["canonical_iri"])),
        "malformed_observations": sorted(malformed, key=lambda item: (
            item.get("reference_kind", ""), item.get("canonical_iri") or "",
            item.get("path", ""), item.get("reason", ""))),
        "committee_name_ambiguities": sorted(ambiguities, key=lambda item: (
            item.get("canonical_iri", ""), item.get("language", ""),
            item.get("valid_from", ""))),
    }
    return {"report": report, "records": consolidated}


def _house_from_term(term: str) -> dict:
    match = HOUSE_TERM_RE.fullmatch(term)
    if not match:
        raise ValueError("consolidated owner record has an invalid HouseTerm")
    return {"uri": term, "houseCode": match.group(1), "houseNo": match.group(2)}


def _serialize_latest_names(entries: list[dict], identity: str,
                            diagnostics: list[dict]) -> list[dict]:
    result = []
    for field, language in (("nameEn", "en"), ("nameGa", "ga")):
        value, ambiguity = _latest_name(entries, language)
        if ambiguity:
            ambiguity.update({"reference_kind": "committee",
                              "canonical_iri": identity})
            if ambiguity not in diagnostics:
                diagnostics.append(ambiguity)
        if value is not None:
            if not result:
                result.append({})
            result[0][field] = value
    return result


def summary(report: dict) -> dict:
    """Small stable stdout form; the full report remains available to audit."""
    keys = ("totals", "coverage_counts_by_kind", "coverage_counts_total",
            "closable_identities", "conflicting_identities",
            "insufficient_evidence_identities", "malformed_observation_count",
            "committee_name_ambiguity_count", "capture_completeness")
    return {key: report[key] for key in keys}
