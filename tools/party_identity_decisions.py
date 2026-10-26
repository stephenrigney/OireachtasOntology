#!/usr/bin/env python3
"""Build the reviewed, source-IRI-keyed political-affiliation decision register."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "reports/party-identity-inventory.csv"
OUTPUT = ROOT / "reports/party-identity-decisions.json"

BASE = "https://data.oireachtas.ie/ie/oireachtas/party"
IDENTITY_NAMESPACE = "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/"
IDENTITIES = {
    "sinn-fein-pre-independence": {
        "label": "Sinn Féin (Pre-Independence)",
        "aliases": ["Sinn Féin"],
    },
    "sinn-fein-anti-treaty": {
        "label": "Sinn Féin (Anti-Treaty)",
        "aliases": ["Republican", "Sinn Féin"],
    },
    "sinn-fein-1957": {
        "label": "Sinn Féin (1957)",
        "aliases": ["Sinn Féin"],
    },
    "sinn-fein": {"label": "Sinn Féin", "aliases": []},
    "workers-party": {
        "label": "Workers Party",
        "aliases": ["Sinn Féin the Workers Party"],
    },
    "people-before-profit-solidarity": {
        "label": "People Before Profit–Solidarity affiliation",
        "aliases": [
            "People Before Profit – Solidarity",
            "Solidarity – People Before Profit",
            "Solidarity – PBP",
            "PBP – Solidarity",
            "AAA – PBP",
            "Anti-Austerity Alliance – People Before Profit",
            "Anti-Austerity Alliance - People Before Profit",
            "People Before Profit-Solidarity",
        ],
    },
    "people-before-profit-alliance": {
        "label": "People Before Profit Alliance",
        "aliases": [],
    },
    "business-and-professional-group": {
        "label": "Business and Professional Group",
        "aliases": [],
    },
}


def identity_for(row: dict[str, str]) -> str | None:
    """Return only assignments explicitly settled in the user review."""
    house, term, name = row["house"], int(row["house_term"]), row["show_as"]
    if name == "Sinn Féin":
        if house == "dail" and term in (1, 2, 3):
            return "sinn-fein-pre-independence"
        if house == "dail" and term in (4, 5, 6):
            return "sinn-fein-anti-treaty"
        if house == "dail" and term == 16:
            return "sinn-fein-1957"
        if house == "dail" and term >= 28:
            return "sinn-fein"
    if name == "Republican" and house == "dail" and term == 4:
        return "sinn-fein-anti-treaty"
    if name in ("Sinn Féin the Workers Party", "Workers Party"):
        return "workers-party"
    if name in (
        "Anti-Austerity Alliance - People Before Profit",
        "People Before Profit-Solidarity",
    ):
        return "people-before-profit-solidarity"
    if name == "People Before Profit Alliance":
        return "people-before-profit-alliance"
    if name == "Business and Professional Group":
        return "business-and-professional-group"
    return None


def unresolved_reason(row: dict[str, str]) -> str:
    if row["house"] == "seanad" and row["show_as"] == "Sinn Féin":
        return "Review §5 leaves Seanad term assignment blank; do not infer from the Dáil-period decision"
    return "Identity association not settled; do not infer from a matching name"


def build() -> dict:
    with INVENTORY.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 315 or len({r["source_iri"] for r in rows}) != len(rows):
        raise ValueError("Inventory must contain 315 distinct source IRIs")

    records = []
    for row in sorted(rows, key=lambda r: r["source_iri"]):
        source = row["source_iri"]
        if not source.startswith(BASE + "/"):
            raise ValueError(f"Unexpected source IRI: {source}")
        if row["show_as"] in ("Ceann Comhairle", "Cathaoirleach"):
            outcome, identity, reason = "excluded", None, "Parliamentary office, not a political affiliation identity"
        else:
            identity = identity_for(row)
            if identity:
                outcome, reason = "accepted", "Explicitly settled by reports/party-identity-review.md §5"
            else:
                outcome, reason = "unresolved", unresolved_reason(row)
        records.append({
            "source_iri": source,
            "source_label": row["show_as"],
            "outcome": outcome,
            "identity": identity,
            "reason": reason,
        })

    counts = {key: sum(r["outcome"] == key for r in records) for key in ("accepted", "unresolved", "excluded")}
    by_label: dict[str, list[str]] = {}
    for row in rows:
        by_label.setdefault(row["show_as"], []).append(row["source_iri"])
    separations = [
        {
            "decision": "distinct identities; no same-identity assertion",
            "left_source_iris": sorted(by_label[left]),
            "right_source_iris": sorted(by_label[right]),
        }
        for left, right in (
            ("Cumann na nGaedheal", "Fine Gael"),
            ("National Progressive Democrats", "Progressive Democrats"),
            ("Democratic Left", "Labour Party"),
            ("National Labour Party", "Labour Party"),
            ("Sinn Féin the Workers Party", "Sinn Féin"),
            ("People Before Profit Alliance", "Anti-Austerity Alliance - People Before Profit"),
            ("People Before Profit Alliance", "People Before Profit-Solidarity"),
            ("Socialist Party", "Anti-Austerity Alliance - People Before Profit"),
            ("Socialist Party", "People Before Profit-Solidarity"),
        )
    ]
    return {
        "version": 1,
        "source_inventory": "party-identity-inventory.csv",
        "source_record_count": len(records),
        "counts": counts,
        "identity_namespace_proposal": IDENTITY_NAMESPACE,
        "identities": [
            {"id": key, "iri": IDENTITY_NAMESPACE + key, **IDENTITIES[key]}
            for key in sorted({r["identity"] for r in records if r["identity"]})
        ],
        "separation_constraints": separations,
        "records": records,
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
