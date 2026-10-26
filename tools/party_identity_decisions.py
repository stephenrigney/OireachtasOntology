#!/usr/bin/env python3
"""Generate the reviewed, complete-source-IRI political-affiliation register."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "reports/party-identity-inventory.csv"
OUTPUT = ROOT / "reports/party-identity-decisions.json"

BASE = "https://data.oireachtas.ie/ie/oireachtas/party"
IDENTITY_NAMESPACE = "https://data.oireachtas.ie/ie/oireachtas/political-affiliation/"
# The reviewed associations below apply only to this exact inventory snapshot.
# An added or edited record must be reviewed, even if its label matches a known one.
INVENTORY_SHA256 = "591a9ff0c83ec207e8368faa6c236612c949eb0add9edf58750a32923e8fa2cd"

IDENTITIES = {
    "100-rdr": {"label": "100% RDR", "aliases": []},
    "aontu": {"label": "Aontú", "aliases": []},
    "business-and-professional-group": {"label": "Business and Professional Group", "aliases": []},
    "clann-na-poblachta": {"label": "Clann na Poblachta", "aliases": []},
    "clann-na-talmhan": {"label": "Clann na Talmhan", "aliases": []},
    "cumann-na-ngaedheal": {"label": "Cumann na nGaedheal", "aliases": []},
    "democratic-left": {"label": "Democratic Left", "aliases": []},
    "democratic-socialist-party": {"label": "Democratic Socialist Party", "aliases": []},
    "farmers-party": {"label": "Farmers Party", "aliases": []},
    "fianna-fail": {"label": "Fianna Fáil", "aliases": []},
    "fine-gael": {"label": "Fine Gael", "aliases": []},
    "green-party": {"label": "Green Party", "aliases": []},
    "independent-ireland": {"label": "Independent Ireland", "aliases": []},
    "independents-4-change": {"label": "Independents 4 Change", "aliases": []},
    "irish-worker-league": {"label": "Irish Worker League", "aliases": []},
    "labour-party": {"label": "Labour Party", "aliases": []},
    "national-centre-party": {"label": "National Centre Party", "aliases": []},
    "national-labour-party": {"label": "National Labour Party", "aliases": []},
    "national-league-party": {"label": "National League Party", "aliases": []},
    "national-progressive-democrats": {"label": "National Progressive Democrats", "aliases": []},
    "people-before-profit-alliance": {"label": "People Before Profit Alliance", "aliases": []},
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
    "progressive-democrats": {"label": "Progressive Democrats", "aliases": []},
    "renua": {"label": "Renua", "aliases": []},
    "sinn-fein-pre-independence": {
        "label": "Sinn Féin (Pre-Independence)", "aliases": ["Sinn Féin"]
    },
    "sinn-fein-anti-treaty": {
        "label": "Sinn Féin (Anti-Treaty)", "aliases": ["Republican", "Sinn Féin"]
    },
    "sinn-fein-1957": {"label": "Sinn Féin (1957)", "aliases": ["Sinn Féin"]},
    "sinn-fein": {"label": "Sinn Féin", "aliases": []},
    "workers-party": {
        "label": "Workers Party", "aliases": ["Sinn Féin the Workers Party"]
    },
    "social-democrats": {"label": "Social Democrats", "aliases": []},
    "socialist-labour-party": {"label": "Socialist Labour Party", "aliases": []},
    "socialist-party": {"label": "Socialist Party", "aliases": []},
    "workers-and-unemployed-action": {"label": "Workers and Unemployed Action", "aliases": []},
}

LABEL_IDENTITIES = {
    "100% RDR": "100-rdr",
    "Aontú": "aontu",
    "Business and Professional Group": "business-and-professional-group",
    "Clann na Poblachta": "clann-na-poblachta",
    "Clann na Talmhan": "clann-na-talmhan",
    "Cumann na nGaedheal": "cumann-na-ngaedheal",
    "Democratic Left": "democratic-left",
    "Democratic Socialist Party": "democratic-socialist-party",
    "Farmers Party": "farmers-party",
    "Fianna Fáil": "fianna-fail",
    "Fine Gael": "fine-gael",
    "Green Party": "green-party",
    "Independent Ireland": "independent-ireland",
    "Independents 4 Change": "independents-4-change",
    "Irish Worker League": "irish-worker-league",
    "Labour Party": "labour-party",
    "National Centre Party": "national-centre-party",
    "National Labour Party": "national-labour-party",
    "National League Party": "national-league-party",
    "National Progressive Democrats": "national-progressive-democrats",
    "People Before Profit Alliance": "people-before-profit-alliance",
    "Progressive Democrats": "progressive-democrats",
    "Renua": "renua",
    "Social Democrats": "social-democrats",
    "Socialist Labour Party": "socialist-labour-party",
    "Socialist Party": "socialist-party",
    "Workers and Unemployed Action": "workers-and-unemployed-action",
}


def identity_for(row: dict[str, str]) -> str | None:
    """Apply decisions only to labels and source terms in the pinned review snapshot."""
    house, term, name = row["house"], int(row["house_term"]), row["show_as"]
    if name == "Sinn Féin":
        if house == "dail" and term in (1, 2, 3):
            return "sinn-fein-pre-independence"
        if house == "dail" and term in (4, 5, 6):
            return "sinn-fein-anti-treaty"
        if house == "dail" and term == 16:
            return "sinn-fein-1957"
        if (house == "dail" and term >= 28) or (house == "seanad" and 23 <= term <= 27):
            return "sinn-fein"
        return None
    if name == "Republican":
        return "sinn-fein-anti-treaty" if house == "dail" and term == 4 else None
    if name in ("Sinn Féin the Workers Party", "Workers Party"):
        return "workers-party"
    if name in ("Anti-Austerity Alliance - People Before Profit", "People Before Profit-Solidarity"):
        return "people-before-profit-solidarity"
    return LABEL_IDENTITIES.get(name)


def build() -> dict:
    raw = INVENTORY.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INVENTORY_SHA256:
        raise ValueError("Inventory changed; review new/edited source IRIs before assigning identities")
    with INVENTORY.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 315 or len({r["source_iri"] for r in rows}) != len(rows):
        raise ValueError("Reviewed inventory must contain 315 distinct source IRIs")

    records = []
    for row in sorted(rows, key=lambda r: r["source_iri"]):
        source, name = row["source_iri"], row["show_as"]
        if not source.startswith(BASE + "/"):
            raise ValueError(f"Unexpected source IRI: {source}")
        if name in ("Ceann Comhairle", "Cathaoirleach"):
            outcome, identity, reason = "excluded", None, "Parliamentary office, not a political affiliation identity"
        else:
            identity = identity_for(row)
            if identity:
                outcome = "accepted"
                reason = (
                    "Explicit user approval: 23rd–27th Seanad Sinn Féin records belong to modern Sinn Féin"
                    if name == "Sinn Féin" and row["house"] == "seanad"
                    else "Explicit user approval: Democratic Socialist Party records share one identity"
                    if name == "Democratic Socialist Party"
                    else "Approved by reports/party-identity-review.md §2 or §5"
                )
            else:
                outcome = "unresolved"
                reason = "No reviewed identity association for this source record"
        records.append({
            "source_iri": source,
            "source_label": name,
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
    identity_separations = [
        {"left_identity": left, "right_identity": right}
        for left, right in (
            ("sinn-fein-pre-independence", "sinn-fein-anti-treaty"),
            ("sinn-fein-pre-independence", "sinn-fein-1957"),
            ("sinn-fein-pre-independence", "sinn-fein"),
            ("sinn-fein-anti-treaty", "sinn-fein-1957"),
            ("sinn-fein-anti-treaty", "sinn-fein"),
            ("sinn-fein-1957", "sinn-fein"),
            ("workers-party", "sinn-fein-pre-independence"),
            ("workers-party", "sinn-fein-anti-treaty"),
            ("workers-party", "sinn-fein-1957"),
            ("workers-party", "sinn-fein"),
            ("people-before-profit-alliance", "people-before-profit-solidarity"),
            ("socialist-party", "people-before-profit-solidarity"),
        )
    ]
    return {
        "version": 1,
        "source_inventory": "party-identity-inventory.csv",
        "source_inventory_sha256": INVENTORY_SHA256,
        "source_record_count": len(records),
        "counts": counts,
        "identity_namespace_proposal": IDENTITY_NAMESPACE,
        "identities": [
            {"id": key, "iri": IDENTITY_NAMESPACE + key, **IDENTITIES[key]}
            for key in sorted({r["identity"] for r in records if r["identity"]})
        ],
        "identity_separation_constraints": identity_separations,
        "separation_constraints": separations,
        "records": records,
    }


if __name__ == "__main__":
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
