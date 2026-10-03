"""Static contract checks for the approved Debates mapping, not an ETL test."""

import csv
from pathlib import Path
import re

from tools.validation import validate_mapping_integrity


ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "mappings" / "debates_mapping.csv"
MAPPING_FIELDS = [
    "json_path", "json_field", "ontology_term", "term_type",
    "source_file", "mapping_status", "notes",
]
ACTIVE_STATUSES = {"mapped", "new"}

# This exact set is the active vocabulary approved for the initial Debates
# mapping. Future-work ontology terms and terms from other vertical owners must
# not become active merely because they are declared in an ontology.
APPROVED_ACTIVE_TERMS = {
    ":DebateExpression",
    ":DebateRecord",
    ":DebateSection",
    ":DebateSitting",
    ":Division",
    ":ParliamentaryQuestion",
    ":Speech",
    ":Summary",
    ":abstained",
    ":askedBy",
    ":debateDate",
    ":debateType",
    ":divisionOutcome",
    ":expressionHasSection",
    ":expressionLanguageCode",
    ":hasDivision",
    ":hasExpression",
    ":hasQuestion",
    ":hasSection",
    ":hasSpeech",
    ":hasSpeechParticipation",
    ":hasSubSection",
    ":hasSummary",
    ":nilCount",
    ":producedRecord",
    ":recordOfBody",
    ":recordOfHouseTerm",
    ":recordedTime",
    ":sectionName",
    ":sourceOrdinal",
    ":speaker",
    ":staonCount",
    ":taCount",
    ":votedAgainst",
    ":votedFor",
    "eli-dl:Participation",
    "eli-dl:activity_date",
    "eli-dl:had_participant_person",
    "eli-dl:participation_role",
}


def _mapping_rows():
    with MAPPING.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _is_text_selector(row):
    """Whether a CSV row selects transcript/prose text rather than structure."""

    source = f"{row['json_path']} {row['json_field']}".lower()
    return (
        "text()" in source
        or "element text" in source
        or re.search(r"(?:^|[;/])(?:speech|question)/p(?:$|[;/])", source) is not None
        or re.search(r"(?:^|[;/])heading(?:$|[;/])", source) is not None
    )


def test_debates_csv_is_well_formed_and_local_terms_resolve():
    with MAPPING.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == MAPPING_FIELDS
        rows = list(reader)
    assert rows
    assert all(None not in row and None not in row.values() for row in rows)
    assert all(set(row) == set(MAPPING_FIELDS) for row in rows)
    assert all(all(value != "" for value in row.values()) for row in rows)
    assert all(
        row["mapping_status"] in {"mapped", "new", "implicit", "future_work"}
        for row in rows
    )
    assert all(not row["json_path"].startswith("debate/meta/") for row in rows)
    validate_mapping_integrity()


def test_debates_mapping_retains_ownership_and_no_prose_boundary():
    rows = _mapping_rows()
    active = [row for row in rows if row["mapping_status"] in ACTIVE_STATUSES]
    active_terms = {row["ontology_term"] for row in active}
    assert {":ParliamentaryQuestion", ":Division", ":votedFor", ":votedAgainst"} <= active_terms
    assert active_terms == APPROVED_ACTIVE_TERMS
    assert not {":inHouse", ":directedTo", ":refersToProposal", ":refersToEvent", "eli-dl:had_participation"} & active_terms
    assert any(
        row["mapping_status"] == "future_work" and _is_text_selector(row)
        for row in rows
    )
    assert all(not _is_text_selector(row) for row in active)
    # Class rows describe Debates-owned resources, never foreign Member/Bill/House entities.
    assert not {"agents:Member", "agents:House", "agents:HouseTerm", "members:Committee", ":BillEvent"} & active_terms


def test_source_ordinal_mapping_is_positive_mixed_sibling_and_container_scoped():
    rows = _mapping_rows()
    ordinal_rows = [row for row in rows if row["ontology_term"] == ":sourceOrdinal"]
    assert len(ordinal_rows) == 1
    row = ordinal_rows[0]
    assert row["mapping_status"] == "mapped"
    assert row["term_type"] == "DatatypeProperty"
    notes = " ".join(row["notes"].split())
    for approved_rule in (
        "positive 1-based integer ordinal",
        "DebateSection",
        "Speech, Summary, and ParliamentaryQuestion",
        "addressable immediate XML children",
        "across child kinds",
        "nested container restarts at 1",
        "never identity",
    ):
        assert approved_rule in notes
    assert "eli-dl:activity_order" in notes


def test_unresolved_source_references_never_mint_placeholder_identities():
    identity_contract = " ".join((
        ROOT / "documentation" / "debates-identity-contract.md"
    ).read_text(encoding="utf-8").split())
    rows = _mapping_rows()
    active = [row for row in rows if row["mapping_status"] in ACTIVE_STATUSES]

    assert "An unresolved/malformed/absent outcome never creates a speculative RDF entity or link." in identity_contract
    assert 'speech/@by="#"' in identity_contract
    assert "report `unresolved` with reason `source-placeholder`" in identity_contract
    assert "never mint a target, evidence predicate, or descriptive entity" in next(
        row["notes"] for row in rows if row["json_path"] == "AKN unresolved href/eId/fragment"
    ).casefold()

    speaker = next(row for row in active if row["ontology_term"] == ":speaker")
    assert "existing agents:Member" in speaker["notes"]
    assert "omit non-Members and unresolved references" in speaker["notes"]
    participation_link = next(
        row for row in active if row["ontology_term"] == ":hasSpeechParticipation"
    )
    assert "only if at least one of @by or @as resolves" in participation_link["notes"]
    assert "never match by label or mint a target" in participation_link["notes"]
    person_link = next(
        row for row in active if row["ontology_term"] == "eli-dl:had_participant_person"
    )
    assert "existing person IRI after authoritative source-reference resolution" in person_link["notes"]
    assert "creates no person description" in person_link["notes"]


def test_known_division_outcomes_are_mapped_but_declared_is_not():
    rows = _mapping_rows()
    generic_outcome = next(
        row for row in rows
        if row["json_path"] == "meta/analysis/parliamentary/voting"
        and row["json_field"] == "@outcome"
    )
    declared_outcome = next(
        row for row in rows
        if row["json_path"] == "meta/analysis/parliamentary/voting[@outcome='#declared']"
    )

    assert generic_outcome["mapping_status"] == "mapped"
    assert generic_outcome["ontology_term"] == ":divisionOutcome"
    assert "map only #carried/#lost" in generic_outcome["notes"]
    assert "For #declared" in generic_outcome["notes"]
    assert "emit no outcome triple" in generic_outcome["notes"]
    assert declared_outcome["mapping_status"] == "future_work"
    assert declared_outcome["ontology_term"] == ":divisionOutcome"


def test_roll_call_remains_source_only_and_cannot_become_votes_or_attendance():
    rows = _mapping_rows()
    roll_call_rows = [row for row in rows if "rollCall" in row["json_path"]]
    assert len(roll_call_rows) == 1
    roll_call = roll_call_rows[0]
    assert roll_call["mapping_status"] == "future_work"
    assert roll_call["ontology_term"] in {"—", "-"}
    for prohibited_conflation in (
        "not treat attendance as a Division",
        "vote",
        "speech",
        "participation assertion",
    ):
        assert prohibited_conflation in roll_call["notes"]
    active_roll_call_rows = [
        row for row in rows
        if row["mapping_status"] in ACTIVE_STATUSES
        and "rollCall" in row["json_path"]
    ]
    assert active_roll_call_rows == []
    assert not {":RollCall", ":Attendance", ":attended", ":hasAttendance"} & {
        row["ontology_term"] for row in rows if row["mapping_status"] in ACTIVE_STATUSES
    }


def test_transcript_and_prose_text_selectors_are_never_active():
    rows = _mapping_rows()
    text_selectors = [row for row in rows if _is_text_selector(row)]
    assert text_selectors
    assert all(row["mapping_status"] == "future_work" for row in text_selectors)
    selector_text = " ".join(row["json_path"] for row in text_selectors)
    for source_selector in ("speech/p", "question/p", "summary", "heading"):
        assert source_selector in selector_text
    assert all(
        row["mapping_status"] not in ACTIVE_STATUSES
        for row in rows if _is_text_selector(row)
    )
