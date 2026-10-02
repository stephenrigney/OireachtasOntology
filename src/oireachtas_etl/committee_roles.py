"""Recognized source forms for Member committee special-role evidence."""
from __future__ import annotations

from .transforms.common import datetime_literal


_SOURCE_TITLES = {
    "Cathaoirleach": "Chair",
    "Leas-Chathaoirleach": "Deputy Chair",
}
_MAPPED_ROLES = {"Chair", "Deputy Chair"}


def normalize_committee_roles(value: object) -> tuple[list[str], dict | None]:
    """Normalize a mapped role array or the observed API role object.

    The captured Members API uses an empty/string role array for ordinary
    committee memberships and a ``{title, dateRange}`` object for recorded
    Chair/Deputy Chair appointments. The title maps to the existing Member
    vocabulary; the separate role interval is returned for explicit omission
    reporting because the current mapping has no role-tenure relation.
    """
    role_date_range = None
    if isinstance(value, list):
        roles = value
    elif isinstance(value, dict):
        if set(value) != {"title", "dateRange"}:
            raise ValueError("committee role object must contain only title and dateRange")
        title = value.get("title")
        if not isinstance(title, str) or title not in _SOURCE_TITLES:
            raise ValueError(f"unsupported committee role title: {title!r}")
        role_date_range = value.get("dateRange")
        if not isinstance(role_date_range, dict) or set(role_date_range) - {"start", "end"}:
            raise ValueError("committee role.dateRange must contain start and optional end")
        if role_date_range.get("start") is None:
            raise ValueError("committee role.dateRange.start is required")
        start = datetime_literal(role_date_range["start"])
        if role_date_range.get("end") is not None:
            end = datetime_literal(role_date_range["end"])
            if end.toPython() < start.toPython():
                raise ValueError("reverse committee role date range")
        roles = [_SOURCE_TITLES[title]]
    else:
        raise ValueError("committee role must be an array or a supported role object")

    for role in roles:
        if not isinstance(role, str) or role not in _MAPPED_ROLES:
            raise ValueError(f"unsupported committee role: {role!r}")
    return roles, role_date_range
