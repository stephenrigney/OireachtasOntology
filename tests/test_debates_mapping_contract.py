"""Static guardrails for the proposal-only Debates mapping, not an ETL test."""

import csv
from pathlib import Path

from tools.validation import validate_mapping_integrity


ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "mappings" / "debates_mapping.csv"


def test_debates_csv_is_well_formed_and_local_terms_resolve():
    with MAPPING.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [
            "json_path", "json_field", "ontology_term", "term_type",
            "source_file", "mapping_status", "notes",
        ]
        rows = list(reader)
    assert rows
    assert all(None not in row and None not in row.values() for row in rows)
    assert all(row["mapping_status"] in {"mapped", "implicit", "future_work"} for row in rows)
    assert all(not row["json_path"].startswith("debate/meta/") for row in rows)
    validate_mapping_integrity()


def test_debates_mapping_retains_ownership_and_no_prose_boundary():
    with MAPPING.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    active = [row for row in rows if row["mapping_status"] == "mapped"]
    active_terms = {row["ontology_term"] for row in active}
    assert {":ParliamentaryQuestion", ":Division", ":votedFor", ":votedAgainst"} <= active_terms
    assert not {":inHouse", ":directedTo", ":refersToProposal", ":refersToEvent", "eli-dl:had_participation"} & active_terms
    assert any(row["mapping_status"] == "future_work" and "text()" in row["json_field"] for row in rows)
    assert all("text()" not in row["json_field"] for row in active)
    # Class rows describe Debates-owned resources, never foreign Member/Bill/House entities.
    assert not {"agents:Member", "agents:House", "agents:HouseTerm", "members:Committee", ":BillEvent"} & active_terms
