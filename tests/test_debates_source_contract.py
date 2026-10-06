"""Static Debates source-contract regressions; these are not runtime RDF tests.

These checks bind the approved mapping rules to the immutable AKN evidence,
but do not themselves demonstrate RDF emission or non-emission. Separate
Tranche 2 runtime tests and independently specified RDF expectations prove
supported assertions and negative cases (unresolved references, ``#declared``,
``rollCall`` attendance, and transcript text) on real transforms; this file
deliberately fabricates no RDF output. The corpus/resource gate remains a
separate, unpassed production-scope decision.
"""

from __future__ import annotations

import csv
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "data" / "debates_examples"
MAPPING_PATH = ROOT / "mappings" / "debates_mapping.csv"
MAPPING_DOC = ROOT / "documentation" / "debates-mapping.md"
SEMANTIC_REVIEW = ROOT / "documentation" / "debates-semantic-review.md"
AKN_NAMESPACE = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13"
NS = {"akn": AKN_NAMESPACE}


def _mapping_rows():
    with MAPPING_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _active_rows():
    return [
        row for row in _mapping_rows()
        if row["mapping_status"] in {"mapped", "new"}
    ]


def test_unresolved_source_placeholder_is_non_rdf_evidence_not_a_member_identity():
    source = (FIXTURE_DIR / "committee_public_accounts_2026-09-24.akn.xml").read_bytes()
    root = ET.fromstring(source)
    placeholders = root.findall(".//akn:speech[@by='#']", NS)
    assert placeholders

    identity_contract = " ".join((
        ROOT / "documentation" / "debates-identity-contract.md"
    ).read_text(encoding="utf-8").split())
    assert 'speech/@by="#"' in identity_contract
    assert "report `unresolved` with reason `source-placeholder`" in identity_contract
    assert "An unresolved/malformed/absent outcome never creates a speculative RDF entity or link." in identity_contract

    rows = _mapping_rows()
    speaker_rows = [
        row for row in rows
        if row["json_path"] == "debateBody//speech/@by"
        and row["ontology_term"] == ":speaker"
    ]
    assert len(speaker_rows) == 1
    assert speaker_rows[0]["mapping_status"] == "mapped"
    assert "only on successful Member resolution" in speaker_rows[0]["notes"]
    assert "omit non-Members and unresolved references" in speaker_rows[0]["notes"]
    assert not any(
        row["ontology_term"] == "agents:Member"
        for row in _active_rows()
    )


def test_declared_vote_is_source_evidence_while_known_outcomes_remain_mapped():
    outcomes = set()
    for filename in (
        "dail_2015-07-02.akn.xml",
        "dail_2026-02-26.akn.xml",
        "seanad_2015-07-02.akn.xml",
    ):
        root = ET.parse(FIXTURE_DIR / filename).getroot()
        outcomes.update(
            voting.get("outcome")
            for voting in root.findall(".//akn:voting[@outcome]", NS)
        )
    assert {"#carried", "#lost", "#declared"} <= outcomes

    rows = _mapping_rows()
    supported = next(
        row for row in rows
        if row["json_path"] == "meta/analysis/parliamentary/voting"
        and row["json_field"] == "@outcome"
    )
    declared = next(
        row for row in rows
        if row["json_path"] == "meta/analysis/parliamentary/voting[@outcome='#declared']"
    )
    assert supported["mapping_status"] == "mapped"
    assert "map only #carried/#lost" in supported["notes"]
    assert "For #declared" in supported["notes"]
    assert "emit no outcome triple" in supported["notes"]
    assert declared["mapping_status"] == "future_work"


def test_committee_roll_call_and_people_remain_source_only_not_votes_or_attendance():
    root = ET.parse(
        FIXTURE_DIR / "committee_public_accounts_2026-09-24.akn.xml"
    ).getroot()
    table = root.find(".//akn:rollCall/akn:table", NS)
    assert table is not None
    assert table.findall(".//akn:person[@refersTo]", NS)

    rows = _mapping_rows()
    roll_call_rows = [
        row for row in rows
        if "rollCall" in row["json_path"].replace("[not(ancestor::rollCall)]", "")
    ]
    assert len(roll_call_rows) == 1
    row = roll_call_rows[0]
    assert row["mapping_status"] == "future_work"
    assert row["ontology_term"] in {"—", "-"}
    assert "do not treat attendance as a Division, vote, speech, or participation assertion" in row["notes"]
    assert not any(
        "rollCall" in row["json_path"].replace("[not(ancestor::rollCall)]", "")
        and row["mapping_status"] in {"mapped", "new"}
        for row in rows
    )


def test_written_answers_are_records_without_a_sitting_under_the_approved_identity_rule():
    root = ET.parse(
        FIXTURE_DIR / "dail_written_answers_2015-07-02.akn.xml"
    ).getroot()
    assert root.find(".//akn:FRBRname[@value='writtens']", NS) is not None
    rows = _mapping_rows()
    sitting = next(row for row in rows if row["ontology_term"] == ":DebateSitting")
    produced = next(row for row in rows if row["ontology_term"] == ":producedRecord")
    activity_date = next(
        row for row in rows if row["ontology_term"] == "eli-dl:activity_date"
    )

    assert all(row["mapping_status"] == "mapped" for row in (sitting, produced, activity_date))
    for row in (sitting, produced, activity_date):
        assert "writtens" in row["notes"]
        assert any(word in row["notes"] for word in ("Omit", "no sitting", "Never apply"))
    assert "#sitting" in sitting["notes"]


def test_tranche_two_goldens_are_required_to_check_non_emission_not_synthetic_rdf_now():
    mapping_doc = MAPPING_DOC.read_text(encoding="utf-8")
    goldens = " ".join(
        mapping_doc.split(
            "## Representative fixtures and expected RDF/negative golden contract", 1
        )[1].split()
    )
    assert "Future Tranche 2 golden outputs must be deterministic RDF datasets" in goldens
    for required_negative_case in (
        "Known multiple Expressions for one Work fail closed",
        "Mixed immediate addressable child kinds share a",
        "`writtens` receives none of those sitting/activity assertions",
        "unresolved/placeholder references create no Participation component or guessed target",
        "#declared",
        "produces no `:divisionOutcome`",
        "Do not infer a Division/vote/participation from committee attendance",
        "spoken/written transcript or other prose text appears as an RDF literal",
    ):
        assert required_negative_case in goldens


def test_approval_does_not_close_the_separate_production_resource_gate():
    review = " ".join(SEMANTIC_REVIEW.read_text(encoding="utf-8").split())
    assert "The production-scope census/benchmark remains open" in review
    assert "total in-scope XML volume, runtime and RDF output have not yet been measured" in review
    assert "This gate does **not** block Tranche 1 source-contract completion or Tranche 2 implementation" in review
    assert "before broad production ingestion" in review
    assert "do not infer a scope choice from record counts or choose an arbitrary cutoff" in review
