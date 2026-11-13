"""Compact views of exact accepted propositions; no inferred outcomes or totals."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .research_adapter import ClosedModel


class FactTable(ClosedModel):
    caption: str
    kind: Literal["bills", "representation", "facts", "records"]
    factRefs: list[str] = Field(min_length=1)
    activityRefs: list[str]
    columns: list[str] | None

    @model_validator(mode="before")
    @classmethod
    def retained_table(cls, value):
        # Old saved reports predate field selection; never default a new records
        # table's factual columns. The model-facing schema still requires it.
        if isinstance(value, dict) and value.get("kind") != "records" and "columns" not in value:
            return value | {"columns": None}
        return value


def project_table(table, facts):
    """Identity is exact compiler Bill identity, not title matching or a new join.

    Each displayed cell keeps its authorising assertion. All observations for a
    selected Bill remain inspectable, including events not selected by the author.
    This is presentation of existing facts, not a new factual derivation.
    """
    rows = []
    activities = set(table["activityRefs"])
    if table["kind"] != "records" and table.get("columns") is not None:
        raise ValueError("Column selection belongs only to records tables.")
    if table["kind"] == "records":
        keys = table.get("columns")
        if not keys or len(keys) != len(set(keys)) or activities:
            raise ValueError("Records tables require unique compiler field keys and activityRefs=[].")
        labels, qualifications = None, []
        for ref in table["factRefs"]:
            a = facts[ref]
            if a["level"] not in (1, 2) or not isinstance(a["proposition"], dict):
                raise ValueError("Records tables require shared accepted propositions.")
            display = a["proposition"]["fields"]
            if any(k not in display for k in keys):
                raise ValueError("Selected field is not established for every selected fact; split incompatible shapes into separate tables.")
            headings = [display[k]["label"] for k in keys]
            if labels is not None and labels != headings:
                raise ValueError("Column meanings differ; split these facts into separate tables.")
            labels = headings
            qualifications.extend(a["proposition"]["qualifications"])
            rows.append({"cells": [{"text": display[k]["text"], "refs": [ref]} for k in keys], "assertionRefs": [ref]})
        return {"caption": table["caption"], "columns": labels, "rows": rows,
                "qualification": " ".join(dict.fromkeys(qualifications))}

    # Compatibility for previously authored specialised tables. The new author
    # can use records for any shape; these projections introduce no new authority.
    def legacy_view(a):
        p = a["proposition"]
        if not isinstance(p, dict):
            return p, a.get("display")
        predicate, w, d = p["predicate"], p["witnesses"], p["fields"]
        if predicate == "sponsorship":
            return [predicate, p["participants"]["member"]["iri"], w[0], w[1]], None
        if predicate == "recorded_status":
            return [predicate, p["participants"]["bill"]["iri"]], {"status": d["status"]["text"]}
        if predicate == "recorded_activity":
            return [predicate, p["participants"]["bill"]["iri"], w[1]], None
        if predicate == "representation":
            return [predicate], {"name": d["member"]["text"], "constituency": d["constituency"]["text"], "term": d["term"]["text"]}
        return [predicate], None

    for ref in table["factRefs"]:
        a = facts[ref]
        p, display = legacy_view(a)
        if table["kind"] == "facts":
            # Capability-independent presentation: exact established wording,
            # never model-authored labels, joins, field mappings or calculations.
            if a["level"] not in (1, 2) or activities:
                raise ValueError("Exact-fact tables require established facts and activityRefs=[].")
            rows.append({"cells": [{"text": a["text"], "refs": [ref]}], "assertionRefs": [ref]})
        elif table["kind"] == "bills":
            if p[0] != "sponsorship":
                raise ValueError("Bill table rows require exact sponsorship facts.")
            b, participation = p[2:4]
            related = [f for f in facts.values() if legacy_view(f)[0][0] in {"recorded_status", "recorded_activity"}
                       and legacy_view(f)[0][1] == b["billIri"]]
            cells = [
                {"text": " / ".join(b["titles"]) + f" ({'/'.join(b['numbers'])}/{'/'.join(b['years'])})", "refs": [ref]},
                {"text": ", ".join(participation["primaryStatus"]) + "; role: " + (", ".join(participation["roles"]) or "not recorded"), "refs": [ref]},
                {"text": "; ".join(legacy_view(f)[1]["status"] for f in related if legacy_view(f)[0][0] == "recorded_status"),
                 "refs": [f["id"] for f in related if legacy_view(f)[0][0] == "recorded_status"]},
                {"text": "; ".join(legacy_view(f)[0][2]["label"] + " · " + legacy_view(f)[0][2]["date"] for f in related if f["id"] in activities),
                 "refs": [f["id"] for f in related if f["id"] in activities]},
            ]
            rows.append({"cells": cells, "assertionRefs": [ref] + [f["id"] for f in related]})
        else:
            if p[0] != "representation":
                raise ValueError("Career table rows require exact representation facts. Use kind=facts for other accepted fact types, with activityRefs=[].")
            # The display fields are taken from the same accepted record that
            # authorised this assertion, not parsed out of model-written prose.
            d = display
            rows.append({"cells": [{"text": d[k], "refs": [ref]} for k in ("name", "constituency", "term")], "assertionRefs": [ref]})
    if activities - {ref for row in rows for ref in row["assertionRefs"] if legacy_view(facts[ref])[0][0] == "recorded_activity"}:
        raise ValueError("Selected activities must belong to the exact Bills in this table.")
    columns = {"bills": ["Bill", "Recorded sponsorship", "Recorded status", "Selected recorded developments"],
               "representation": ["Member", "Constituency", "Dáil term"], "facts": ["Recorded finding"]}
    qualifications = {
        "bills": "Recorded status and selected activities are not final outcomes or necessarily the latest developments. Full histories are available in each row's evidence.",
        "representation": "Separate term records do not establish service dates, continuous tenure or parliamentary roles.",
        "facts": "Exact accepted findings at their recorded scope; source coverage and freshness are not certified. Each row retains its evidence and qualifications."}
    return {"caption": table["caption"], "columns": columns[table["kind"]], "rows": rows,
            "qualification": qualifications[table["kind"]]}
