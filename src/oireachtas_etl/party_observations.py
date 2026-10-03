"""Validation helpers for nested Member party-membership observations."""
from __future__ import annotations

from urllib.parse import unquote, urlsplit

from .transforms.common import datetime_literal


def _source_iri(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment") from error
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or port or not parsed.path):
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    return value


def parse_party_identity(wrapped: object, membership_uri: str) -> tuple[dict, str, str]:
    """Validate the party identity needed to isolate its date-range evidence."""
    if not isinstance(wrapped, dict) or not isinstance(wrapped.get("party"), dict):
        raise ValueError("party wrapper must contain a party object")
    party = wrapped["party"]
    code = party.get("partyCode")
    if not isinstance(code, str) or not code:
        raise ValueError("party.partyCode must be a non-empty string")
    party_iri = _source_iri(party.get("uri"), "party.uri")
    membership_path = [part for part in urlsplit(membership_uri).path.split("/") if part]
    party_path = [part for part in urlsplit(party_iri).path.split("/") if part]
    if (len(membership_path) != 8 or len(party_path) != 6
            or party_path[:3] != ["ie", "oireachtas", "party"]
            or party_path[3:5] != membership_path[6:8]
            or unquote(party_path[5]) != code):
        raise ValueError("party.uri must be the term-scoped Party source IRI")
    return party, party_iri, code


def party_date_range_error(party: dict) -> str | None:
    """Return why a source party date range is unusable, without altering it."""
    dates = party.get("dateRange")
    if not isinstance(dates, dict):
        return "party.dateRange must be an object with a required start"
    if dates.get("start") is None:
        return "party.dateRange.start is required"
    try:
        start = datetime_literal(dates["start"])
        if dates.get("end") is not None:
            end = datetime_literal(dates["end"])
            if end.toPython() < start.toPython():
                return "party.dateRange has reverse dates"
    except (TypeError, ValueError) as error:
        return f"party.dateRange contains invalid date evidence: {error}"
    return None


def malformed_party_report(*, membership_index: int, party_index: int,
                            membership_uri: str, member_uri: str,
                            party: dict, party_uri: str, party_code: str,
                            wrapped: object, reason: str) -> dict:
    """Create a lossless, wrapper-relative quarantine record."""
    pointer = (f"/member/memberships/{membership_index}/membership/parties/"
               f"{party_index}/party/dateRange")
    return {
        "path": f"member.memberships[{membership_index}].membership.parties[{party_index}].party.dateRange",
        "json_pointer": pointer,
        "json_pointer_scope": "Member wrapper",
        "context": membership_uri,
        "member_uri": member_uri,
        "party_uri": party_uri,
        "party_code": party_code,
        "date_range": party.get("dateRange"),
        "raw_observation": wrapped,
        "reason": reason,
        "category": "source_quarantine",
        "status": "review_required",
    }
