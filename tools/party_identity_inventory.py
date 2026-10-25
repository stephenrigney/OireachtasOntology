#!/usr/bin/env python3
"""Generate a review-only inventory from preserved raw Member API captures."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def records(root: Path):
    found = {}
    for path in sorted(root.glob("data/raw/members/**/*.json")):
        if path.name.endswith(".meta.json"):
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for wrapper in payload.get("results", []):
            member = wrapper.get("member", {})
            for wrapped in member.get("memberships", []):
                membership = wrapped.get("membership", {})
                house = membership.get("house", {})
                for item in membership.get("parties", []):
                    party = item.get("party", {})
                    iri, code = party.get("uri"), party.get("partyCode")
                    if not iri or not code or code == "Independent":
                        continue
                    entry = found.setdefault(iri, {
                        "iri": iri, "code": code, "label": party.get("showAs", ""),
                        "house": house.get("houseCode", ""), "term": house.get("houseNo", ""),
                        "term_label": house.get("showAs", ""), "start": "", "end": "",
                        "source_files": set(), "conflicts": set(),
                    })
                    for key, value in (("code", code), ("label", party.get("showAs", "")),
                                       ("term", house.get("houseNo", ""))):
                        if entry[key] != value:
                            entry["conflicts"].add(key)
                    dates = party.get("dateRange") or {}
                    start, end = dates.get("start", ""), dates.get("end", "") or ""
                    entry["start"] = min(filter(None, (entry["start"], start)), default="")
                    entry["end"] = "" if not end or not entry["end"] else max(entry["end"], end)
                    entry["source_files"].add(str(path.relative_to(root)))
    return found


def classification(r):
    if r["code"] == "Sinn_Féin":
        if r["house"] != "dail":
            return "Modern Sinn Féin (proposed)", "Proposed; term-scoped source record"
        try:
            term = int(r["term"])
        except ValueError:
            term = -1
        if 1 <= term <= 6:
            return "Historical Sinn Féin (1st–6th Dáil; proposed)", "Separate proposed identity; no continuity within terms assumed"
        if term >= 28:
            return "Modern Sinn Féin (from 1970; proposed)", "Proposed; same name is not proof of continuity"
        return "UNRESOLVED — Sinn Féin intermediate/boundary record", "Review required; no continuity inferred"
    return f"{r['label']} (proposed)", "Provisional exact-code/name grouping; human review required"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--csv", type=Path, default=Path("reports/party-identity-inventory.csv"))
    args = parser.parse_args()
    root = args.root.resolve()
    rows = records(root)
    fields = ["review_group", "review_status", "house", "house_term", "term_label",
              "party_code", "show_as", "first_observed_start", "last_observed_end",
              "source_iri", "source_capture_count", "conflicting_fields"]
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        ordered = sorted(rows.values(), key=lambda x: (x["house"], int(x["term"] or 0), x["code"], x["iri"]))
        for r in ordered:
            group, status = classification(r)
            writer.writerow({"review_group": group, "review_status": status,
                "house": r["house"], "house_term": r["term"], "term_label": r["term_label"],
                "party_code": r["code"], "show_as": r["label"],
                "first_observed_start": r["start"], "last_observed_end": r["end"] or "open/unknown",
                "source_iri": r["iri"], "source_capture_count": len(r["source_files"]),
                "conflicting_fields": ";".join(sorted(r["conflicts"]))})
    unresolved = sum(classification(r)[0].startswith("UNRESOLVED") for r in rows.values())
    print(f"eligible={len(rows)} unresolved={unresolved} csv={args.csv}")


if __name__ == "__main__":
    main()
