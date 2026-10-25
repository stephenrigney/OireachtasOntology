#!/usr/bin/env python3
"""Generate a review-only inventory from preserved raw Member API captures."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def records(root: Path):
    found = {}
    def observe(iri, code, label, house_code, house_no, house_label):
        entry = found.setdefault(iri, {
            "iri": iri, "code": code, "label": label or "", "house": house_code or "",
            "term": str(house_no or ""), "term_label": house_label or "",
            "affiliation_ranges": set(),
            "member_starts": set(), "member_ends": set(), "member_open": False,
            "member_files": set(), "party_files": set(), "conflicts": set(), "date_flags": set(),
        })
        for key, value in (("code", code), ("label", label or ""),
                           ("term", str(house_no or "")), ("house", house_code or "")):
            if entry[key] != value:
                entry["conflicts"].add(key)
        return entry

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
                    entry = observe(iri, code, party.get("showAs"), house.get("houseCode"),
                                    house.get("houseNo"), house.get("showAs"))
                    dates, member_dates = party.get("dateRange") or {}, membership.get("dateRange") or {}
                    entry["affiliation_ranges"].add((dates.get("start", ""), dates.get("end", "") or "open"))
                    if dates.get("start") and dates.get("end") and dates["end"] < dates["start"]:
                        entry["date_flags"].add("source affiliation end precedes its start")
                    if dates.get("end") and member_dates.get("start") and dates["end"] < member_dates["start"]:
                        entry["date_flags"].add("some party dates end before associated parliamentary membership begins; verify historical source dates")
                    if member_dates.get("start"):
                        entry["member_starts"].add(member_dates["start"])
                    if member_dates.get("end"):
                        entry["member_ends"].add(member_dates["end"])
                    else:
                        entry["member_open"] = True
                    entry["member_files"].add(str(path.relative_to(root)))
    # Parties endpoint captures are separate input: account for their records and
    # compare their coverage with the party resources nested in Member histories.
    for path in sorted(root.glob("data/raw/parties/**/*.json")):
        if path.name.endswith(".meta.json"):
            continue
        for wrapped in json.loads(path.read_text(encoding="utf-8")).get("results", []):
            party, house = wrapped.get("party", {}), wrapped.get("house", {})
            if not party.get("uri") or party.get("partyCode") == "Independent":
                continue
            entry = observe(party["uri"], party.get("partyCode"), party.get("showAs"),
                            house.get("houseCode"), house.get("houseNo"), house.get("showAs"))
            entry["party_files"].add(str(path.relative_to(root)))
    return found


def classification(r):
    if r["code"] == "Ceann_Comhairle":
        return "UNRESOLVED — parliamentary office, not proposed as a party", "Category review required"
    if r["code"] == "Business_and_Professional_Group":
        return "UNRESOLVED — group, not proposed as a party", "Category review required"
    if r["code"] == "Sinn_Féin":
        if r["house"] != "dail":
            return "Modern Sinn Féin (from 1970; proposed)", "Proposed; same name is not proof of continuity"
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
              "party_code", "show_as", "observed_affiliation_start_first",
              "observed_affiliation_end_last", "observed_affiliation_dates_all",
              "member_parliamentary_period_first", "member_parliamentary_period_last",
              "source_iri", "member_capture_count", "parties_capture_count",
              "date_or_identity_flags", "conflicting_fields"]
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        ordered = sorted(rows.values(), key=lambda x: (x["house"], int(x["term"] or 0), x["code"], x["iri"]))
        for r in ordered:
            group, status = classification(r)
            ranges = sorted(r["affiliation_ranges"])
            starts = [a for a, _ in ranges if a]
            ends = [b for _, b in ranges if b != "open"]
            member_starts, member_ends = sorted(r["member_starts"]), sorted(r["member_ends"])
            flags = sorted(r["date_flags"])
            writer.writerow({"review_group": group, "review_status": status,
                "house": r["house"], "house_term": r["term"], "term_label": r["term_label"],
                "party_code": r["code"], "show_as": r["label"],
                "observed_affiliation_start_first": min(starts, default="not supplied"),
                "observed_affiliation_end_last": ("open in source" if any(b == "open" for _, b in ranges) else max(ends, default="not supplied")),
                "observed_affiliation_dates_all": ";".join(f"{a or 'start missing'} to {b}" for a, b in ranges) or "not supplied",
                "member_parliamentary_period_first": min(member_starts, default="not observed"),
                "member_parliamentary_period_last": ("open in source" if r["member_open"] else max(member_ends, default="not observed")),
                "source_iri": r["iri"], "member_capture_count": len(r["member_files"]),
                "parties_capture_count": len(r["party_files"]),
                "date_or_identity_flags": "; ".join(flags) or "none",
                "conflicting_fields": ";".join(sorted(r["conflicts"])) or "none"})
    unresolved = sum(classification(r)[0].startswith("UNRESOLVED") for r in rows.values())
    print(f"eligible={len(rows)} unresolved={unresolved} csv={args.csv}")


if __name__ == "__main__":
    main()
