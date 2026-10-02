"""Source validation and lossless extraction for generic Member office reports.

This module does not create RDF or infer office identities.  It preserves the
source observation, its containing Member/House membership and a locator into
the immutable raw response so Tranche 3 can consume reviewed resolutions.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from .transforms.common import datetime_literal


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _source_iri(value: object, label: str) -> str:
    if not isinstance(value, str) or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{label} must be a complete local Oireachtas IRI")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{label} must be a complete local Oireachtas IRI") from error
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.query or parsed.fragment or parsed.username or parsed.password or port
            or not parsed.path):
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    return value


def _date_range(value: object, label: str) -> dict:
    if not isinstance(value, dict) or "start" not in value:
        raise ValueError(f"{label} must be an object with a required start")
    start = value.get("start")
    try:
        datetime_literal(start)
        end = value.get("end")
        if end is not None:
            datetime_literal(end)
            if datetime_literal(end).toPython() < datetime_literal(start).toPython():
                raise ValueError(f"{label} has reverse dates")
    except (TypeError, ValueError) as error:
        if str(error).startswith(label):
            raise
        raise ValueError(f"{label} contains invalid date evidence: {error}") from error
    return {"start": start, "end": end}


def parse_office_observation(wrapped_office: object) -> tuple[dict, dict, str, str | None, dict]:
    """Validate one nested office report and return its source fields.

    Callers may quarantine a ``ValueError`` from this function at the individual
    ``offices[]`` boundary.  Containing Member and House-membership validation
    remains separate and fail-closed.
    """
    if not isinstance(wrapped_office, dict) or not isinstance(wrapped_office.get("office"), dict):
        raise ValueError("each membership.offices item must contain an office object")
    office = wrapped_office["office"]
    name = office.get("officeName")
    if not isinstance(name, dict):
        raise ValueError("office.officeName must be an object")
    label = name.get("showAs")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("office.officeName.showAs must be a non-empty string")
    source_uri = name.get("uri")
    if source_uri is not None:
        source_uri = _source_iri(source_uri, "office.officeName.uri")
    dates = _date_range(office.get("dateRange"), "office.dateRange")
    return office, name, label, source_uri, dates


def normalize_label(value: str) -> str:
    """Conservative text normalisation used only for reviewed alias matching."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _member_and_membership(wrapper: object) -> tuple[dict, str, list]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
        raise ValueError("each Members record must contain a member object")
    member = wrapper["member"]
    code = member.get("memberCode")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("member.memberCode must be a non-empty string")
    member_iri = _source_iri(member.get("uri"), "member.uri")
    member_path = [part for part in urlsplit(member_iri).path.split("/") if part]
    if (len(member_path) != 5 or member_path[:4] != ["ie", "oireachtas", "member", "id"]
            or unquote(member_path[4]) != code):
        raise ValueError("memberCode must match the final member.uri path segment")
    memberships = member.get("memberships")
    if not isinstance(memberships, list):
        raise ValueError("member.memberships must be an array")
    return member, member_iri, memberships


def _membership_context(member_iri: str, member: dict, wrapper: object) -> tuple[str, dict]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("membership"), dict):
        raise ValueError("membership wrapper must contain a membership object")
    record = wrapper["membership"]
    membership_iri = _source_iri(record.get("uri"), "membership.uri")
    house = record.get("house")
    if not isinstance(house, dict):
        raise ValueError("membership.house must be an object")
    house_code, house_number = house.get("houseCode"), house.get("houseNo")
    if house_code not in {"dail", "seanad"} or isinstance(house_number, bool) or not isinstance(house_number, (int, str)):
        raise ValueError("membership.house must identify a Dáil or Seanad HouseTerm")
    house_number = str(house_number)
    if not re.fullmatch(r"[1-9][0-9]*", house_number):
        raise ValueError("membership.house.houseNo must be a positive HouseTerm number")
    house_iri = _source_iri(house.get("uri"), "membership.house.uri")
    house_match = re.fullmatch(rf"https://data\.oireachtas\.ie/ie/oireachtas/house/{house_code}/([1-9][0-9]*)", house_iri)
    if not house_match or house_match.group(1) != house_number:
        raise ValueError("membership.house.uri must match houseCode and houseNo")
    member_code = member["memberCode"]
    membership_path = [part for part in urlsplit(membership_iri).path.split("/") if part]
    if (len(membership_path) != 8
            or membership_path[:4] != ["ie", "oireachtas", "member", "id"]
            or unquote(membership_path[4]) != member_code
            or membership_path[5:] != ["house", house_code, house_number]
            or membership_iri.rsplit("/house/", 1)[0] != member_iri):
        raise ValueError("membership.uri must be the containing Member HouseTerm source IRI")
    member_dates = _date_range(record.get("dateRange"), "membership.dateRange")
    return membership_iri, {
        "house_code": house_code,
        "house_number": house_number,
        "house_term_iri": house_iri,
        "membership_date_range": member_dates,
    }


def _raw_pointer(pointer: object) -> dict:
    if not isinstance(pointer, dict) or set(pointer) != {"path", "sha256", "json_pointer"}:
        raise ValueError("raw response pointer must contain path, sha256 and json_pointer")
    path, digest, json_pointer = pointer["path"], pointer["sha256"], pointer["json_pointer"]
    if (not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/")
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            or not isinstance(json_pointer, str) or (json_pointer and not json_pointer.startswith("/"))):
        raise ValueError("invalid immutable raw response pointer")
    return dict(pointer)


def extract_office_observations(records: list[tuple[object, dict]]) -> list[dict]:
    """Validate and extract every nested office observation from source records.

    ``records`` contains ``(Member wrapper, raw response pointer to wrapper)``.
    Duplicate observations are deliberately retained here; the reconciliation
    ledger deduplicates identical reports while preserving all raw pointers.
    """
    extracted: list[dict] = []
    for wrapped_member, raw_pointer in records:
        pointer = _raw_pointer(raw_pointer)
        member, member_iri, memberships = _member_and_membership(wrapped_member)
        record_pointer = pointer["json_pointer"]
        for membership_index, wrapped_membership in enumerate(memberships):
            membership_iri, house_context = _membership_context(member_iri, member, wrapped_membership)
            membership = wrapped_membership["membership"]
            offices = membership.get("offices", [])
            if not isinstance(offices, list):
                raise ValueError("membership.offices must be an array")
            for office_index, wrapped_office in enumerate(offices):
                malformed_reason = None
                try:
                    office, _name, label, source_uri, dates = parse_office_observation(wrapped_office)
                except ValueError as error:
                    # The Member and its containing House-membership have already
                    # passed their fail-closed checks. Isolate only this nested
                    # office payload so an invalid appointment cannot hide other
                    # valid observations from the same Member.
                    malformed_reason = str(error)
                    office = (wrapped_office.get("office")
                              if isinstance(wrapped_office, dict) else None)
                    name = office.get("officeName") if isinstance(office, dict) else None
                    label = name.get("showAs") if isinstance(name, dict) else None
                    if not isinstance(label, str):
                        label = None
                    source_uri = None
                    if isinstance(name, dict) and name.get("uri") is not None:
                        try:
                            source_uri = _source_iri(name["uri"], "office.officeName.uri")
                        except ValueError:
                            # Invalid source identity evidence is retained in the
                            # raw office snapshot, never used as a local identity.
                            pass
                    dates = office.get("dateRange") if isinstance(office, dict) else None

                office_pointer = dict(pointer)
                office_pointer["json_pointer"] = (
                    f"{record_pointer}/member/memberships/{membership_index}/membership/offices/"
                    f"{office_index}/office"
                )

                if malformed_reason is None:
                    snapshot = {
                        "member_iri": member_iri,
                        "membership_iri": membership_iri,
                        "house": dict(house_context),
                        "office_label": label,
                        "source_office_uri": source_uri,
                        "date_range": dates,
                        "raw_office": office,
                    }
                    identity_subject = ({"source_office_uri": source_uri} if source_uri is not None
                                        else {"normalized_label": normalize_label(label)})
                else:
                    # Keep malformed values verbatim in the snapshot. In
                    # particular, reversed dates are evidence, not values to
                    # swap, clip or normalize.
                    snapshot = {
                        "member_iri": member_iri,
                        "membership_iri": membership_iri,
                        "house": dict(house_context),
                        "office_label": label,
                        "source_office_uri": source_uri,
                        "date_range": dates,
                        "raw_office": office,
                        "malformed_reason": malformed_reason,
                    }
                    if (not isinstance(wrapped_office, dict)
                            or not isinstance(wrapped_office.get("office"), dict)):
                        snapshot["raw_observation"] = wrapped_office
                    identity_subject = ({"source_office_uri": source_uri} if source_uri is not None
                                        else {"normalized_label": normalize_label(label)} if label
                                        else {"malformed_observation": wrapped_office})

                identity_key = json_hash({"member_iri": member_iri,
                                          "membership_iri": membership_iri,
                                          **identity_subject})
                observation = {
                    "identity_key": identity_key,
                    "fingerprint": json_hash(snapshot),
                    "member_iri": member_iri,
                    "membership_iri": membership_iri,
                    "house_context": dict(house_context),
                    "label": label,
                    "normalized_label": normalize_label(label) if label else "",
                    "source_office_uri": source_uri,
                    "date_range": dates,
                    "snapshot": snapshot,
                    "raw_pointers": [office_pointer],
                }
                if malformed_reason is not None:
                    observation["malformed_reason"] = malformed_reason
                extracted.append(observation)
    return extracted
