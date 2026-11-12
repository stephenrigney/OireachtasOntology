"""Compact views of exact accepted propositions; no inferred outcomes or totals."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .research_adapter import ClosedModel


class FactTable(ClosedModel):
    caption: str
    kind: Literal["bills", "representation"]
    factRefs: list[str] = Field(min_length=1)
    activityRefs: list[str]


def project_table(table, facts):
    """Identity is exact compiler Bill identity, not title matching or a new join.

    Each displayed cell keeps its authorising assertion. All observations for a
    selected Bill remain inspectable, including events not selected by the author.
    This is presentation of existing facts, not a new factual derivation.
    """
    rows = []
    activities = set(table["activityRefs"])
    for ref in table["factRefs"]:
        a = facts[ref]
        p = a["proposition"]
        if table["kind"] == "bills":
            if p[0] != "sponsorship":
                raise ValueError("Bill table rows require exact sponsorship facts.")
            b, participation = p[2:4]
            related = [f for f in facts.values() if f["proposition"][0] in {"recorded_status", "recorded_activity"}
                       and f["proposition"][1] == b["billIri"]]
            cells = [
                {"text": " / ".join(b["titles"]) + f" ({'/'.join(b['numbers'])}/{'/'.join(b['years'])})", "refs": [ref]},
                {"text": ", ".join(participation["primaryStatus"]) + "; role: " + (", ".join(participation["roles"]) or "not recorded"), "refs": [ref]},
                {"text": "; ".join(f["display"]["status"] for f in related if f["proposition"][0] == "recorded_status"),
                 "refs": [f["id"] for f in related if f["proposition"][0] == "recorded_status"]},
                {"text": "; ".join(f["proposition"][2]["label"] + " · " + f["proposition"][2]["date"] for f in related if f["id"] in activities),
                 "refs": [f["id"] for f in related if f["id"] in activities]},
            ]
            rows.append({"cells": cells, "assertionRefs": [ref] + [f["id"] for f in related]})
        else:
            if p[0] != "representation":
                raise ValueError("Career table rows require exact representation facts.")
            # The display fields are taken from the same accepted record that
            # authorised this assertion, not parsed out of model-written prose.
            d = a["display"]
            rows.append({"cells": [{"text": d[k], "refs": [ref]} for k in ("name", "constituency", "term")], "assertionRefs": [ref]})
    if activities - {ref for row in rows for ref in row["assertionRefs"] if facts[ref]["proposition"][0] == "recorded_activity"}:
        raise ValueError("Selected activities must belong to the exact Bills in this table.")
    return {"caption": table["caption"], "columns": (["Bill", "Recorded sponsorship", "Recorded status", "Selected recorded developments"]
            if table["kind"] == "bills" else ["Member", "Constituency", "Dáil term"]), "rows": rows,
            "qualification": ("Recorded status and selected activities are not final outcomes or necessarily the latest developments. Full histories are available in each row's evidence."
                              if table["kind"] == "bills" else "Separate term records do not establish service dates, continuous tenure or parliamentary roles.")}
