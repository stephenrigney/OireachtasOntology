"""Focused Phase 6 source-contract and schema-drift tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from oireachtas_etl.source_contract import (classify_source_contract,
                                             classify_source_envelope)


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "12345678-1234-4234-8234-123456789abc"
FIXTURES = {
    "houses": ("houses.json", lambda value: value, ""),
    "parties": ("parties.json", lambda value: value["results"], "/results"),
    "constituencies": ("constituencies.json", lambda value: value, ""),
    "members": ("member.json", lambda value: [value], ""),
    "legislation": ("bill.json", lambda value: value["results"], "/results"),
}


def _fixture(endpoint: str):
    filename, unpack, pointer = FIXTURES[endpoint]
    source = json.loads((ROOT / "data/api_examples" / filename).read_text(encoding="utf-8"))
    return unpack(source), pointer


def _evidence(endpoint: str, pointer: str) -> dict[str, str]:
    filename = FIXTURES[endpoint][0]
    payload = (ROOT / "data/api_examples" / filename).read_bytes()
    return {
        "path": f"api/{endpoint}/skip-000000.json",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "json_pointer": pointer,
    }


@pytest.mark.parametrize("endpoint", sorted(FIXTURES))
def test_representative_api_examples_match_explicit_consumed_contract(endpoint):
    records, pointer = _fixture(endpoint)
    report = classify_source_contract(
        endpoint, records, run_id=RUN_ID,
        source_evidence=_evidence(endpoint, pointer),
    )

    assert report.clean
    assert report.findings == ()
    assert report.endpoint == endpoint
    assert report.run_id == RUN_ID


def test_additive_unknown_property_is_a_warning_with_immutable_source_location():
    records, pointer = _fixture("houses")
    changed = copy.deepcopy(records)
    changed[0]["house"]["newField/with~pointer"] = {"detail": "not consumed"}
    # ``uri`` is known on House records but is a new property at this path.
    changed[0]["house"]["dateRange"]["uri"] = "not part of a date range"

    report = classify_source_contract(
        "houses", changed, run_id=RUN_ID,
        source_evidence=_evidence("houses", pointer),
    )

    assert report.clean
    assert len(report.warnings) == 2
    finding = next(item for item in report.warnings
                   if item.json_pointer.endswith("newField~1with~0pointer"))
    assert finding.endpoint == "houses"
    assert finding.json_pointer == "/0/house/newField~1with~0pointer"
    assert finding.change == "unknown_property"
    assert finding.severity == "warning"
    assert finding.run_id == RUN_ID
    assert finding.source_evidence.as_dict() == {
        "path": "api/houses/skip-000000.json",
        "sha256": _evidence("houses", pointer)["sha256"],
        "json_pointer": finding.json_pointer,
    }
    assert finding.as_dict()["record_index"] == 0
    misplaced = next(item for item in report.warnings
                     if item.json_pointer.endswith("/dateRange/uri"))
    assert misplaced.change == "unknown_property"
    assert misplaced.severity == "warning"


def test_missing_and_type_changed_consumed_fields_fail_only_the_affected_records():
    records, pointer = _fixture("parties")
    changed = copy.deepcopy(records)
    del changed[0]["party"]["uri"]
    changed[1]["party"]["partyCode"] = 17

    report = classify_source_contract(
        "parties", changed, run_id=RUN_ID,
        source_evidence=_evidence("parties", pointer),
    )

    observed = {(item.json_pointer, item.change, item.severity)
                for item in report.record_failures}
    assert ("/results/0/party/uri", "missing_required_field", "record") in observed
    assert ("/results/1/party/partyCode", "type_changed", "record") in observed
    assert report.failed_record_indices == (0, 1)
    assert not report.source_failed
    assert not report.clean
    for item in report.record_failures:
        assert item.run_id == RUN_ID
        assert item.source_evidence.json_pointer == item.json_pointer
        assert item.source_evidence.sha256 == _evidence("parties", pointer)["sha256"]


def test_optional_mapped_member_fields_and_defaulted_collections_may_be_absent():
    records, pointer = _fixture("members")
    changed = copy.deepcopy(records)
    member = changed[0]["member"]
    for name in ("showAs", "fullName", "firstName", "lastName", "pId",
                 "gender", "wikiTitle", "dateOfDeath"):
        member.pop(name, None)
    membership = member["memberships"][0]["membership"]
    for name in ("represents", "parties", "committees", "offices"):
        membership.pop(name, None)

    report = classify_source_contract(
        "members", changed, run_id=RUN_ID,
        source_evidence=_evidence("members", pointer),
    )

    assert report.clean
    assert report.findings == ()


def test_optional_legislation_collections_and_titles_are_not_promoted_to_required():
    records, pointer = _fixture("legislation")
    changed = copy.deepcopy(records)
    bill = changed[0]["bill"]
    for name in ("events", "amendmentLists", "relatedDocs", "versions", "sponsors",
                 "debates", "shortTitleEn", "shortTitleGa", "longTitleEn",
                 "longTitleGa", "act"):
        bill.pop(name, None)

    report = classify_source_contract(
        "legislation", changed, run_id=RUN_ID,
        source_evidence=_evidence("legislation", pointer),
    )

    assert report.clean
    assert report.findings == ()


def test_bill_version_contract_is_conditional_on_bill_vs_deferred_act():
    records, pointer = _fixture("legislation")
    changed = copy.deepcopy(records)
    versions = changed[0]["bill"]["versions"]
    act = next(item["version"] for item in versions
               if item["version"]["docType"] == "act")
    for name in ("uri", "date", "lang", "showAs", "formats"):
        act.pop(name, None)

    report = classify_source_contract(
        "legislation", changed, run_id=RUN_ID,
        source_evidence=_evidence("legislation", pointer),
    )
    assert report.clean

    changed = copy.deepcopy(records)
    bill_version = next(item["version"] for item in changed[0]["bill"]["versions"]
                        if item["version"]["docType"] == "bill")
    bill_version.pop("formats")
    report = classify_source_contract(
        "legislation", changed, run_id=RUN_ID,
        source_evidence=_evidence("legislation", pointer),
    )
    finding = next(item for item in report.record_failures
                   if item.json_pointer.endswith("/version/formats"))
    assert finding.change == "missing_required_field"


def test_unsupported_consumed_representation_value_is_fail_closed():
    records, pointer = _fixture("constituencies")
    changed = copy.deepcopy(records)
    changed[0]["constituencyOrPanel"]["representType"] = "region"

    report = classify_source_contract(
        "constituencies", changed, run_id=RUN_ID,
        source_evidence=_evidence("constituencies", pointer),
    )

    assert len(report.record_failures) == 1
    assert report.record_failures[0].json_pointer == "/0/constituencyOrPanel/representType"
    assert report.record_failures[0].change == "incompatible_value"
    assert report.failed_record_indices == (0,)


def test_combined_house_exclusion_does_not_require_unconsumed_house_fields():
    records, pointer = _fixture("houses")
    combined = copy.deepcopy(records[:1])
    combined[0]["house"]["houseCode"] = "dail & seanad"
    for name in ("showAs", "houseNo", "seats", "dateRange"):
        combined[0]["house"].pop(name, None)

    report = classify_source_contract(
        "houses", combined, run_id=RUN_ID,
        source_evidence=_evidence("houses", pointer),
    )

    assert report.clean
    assert report.findings == ()


def test_invalid_source_container_is_a_source_failure_with_evidence():
    evidence = _evidence("houses", "")
    report = classify_source_contract(
        "houses", {"results": "not-an-array"}, run_id=RUN_ID,
        source_evidence=evidence,
    )

    assert report.source_failed
    assert len(report.source_failures) == 1
    finding = report.source_failures[0]
    assert finding.json_pointer == ""
    assert finding.change == "invalid_source_container"
    assert finding.severity == "source"
    assert finding.source_evidence.as_dict() == evidence


def test_per_record_evidence_pointers_are_supported_and_validated():
    records, _ = _fixture("houses")
    changed = copy.deepcopy(records[:1])
    changed[0]["house"]["seats"] = {"value": 174}
    per_record = [{**_evidence("houses", ""), "json_pointer": "/results/8"}]

    report = classify_source_contract(
        "houses", changed, run_id=RUN_ID, source_evidence=per_record,
    )

    finding = next(item for item in report.record_failures
                   if item.json_pointer.endswith("/house/seats"))
    assert finding.json_pointer == "/results/8/house/seats"
    assert finding.source_evidence.json_pointer == finding.json_pointer

    with pytest.raises(ValueError, match="count must match"):
        classify_source_contract("houses", changed, run_id=RUN_ID,
                                 source_evidence=[])
    with pytest.raises(ValueError, match="invalid immutable source evidence pointer"):
        classify_source_contract(
            "houses", changed, run_id=RUN_ID,
            source_evidence=[{"path": "../outside.json", "sha256": "a" * 64,
                              "json_pointer": "/results/8"}],
        )


@pytest.mark.parametrize(("envelope", "expected_pointer", "change"), [
    ({"results": []}, "/head", "missing_required_field"),
    ({"head": {"counts": {"memberCount": "credential=do-not-report"}},
      "results": []}, "/head/counts/memberCount", "type_changed"),
    ({"head": {"counts": {"memberCount": -1}}, "results": []},
     "/head/counts/memberCount", "type_changed"),
    ({"head": {"counts": {"memberCount": 2}}, "results": "not-array"},
     "/results", "type_changed"),
])
def test_consumed_api_envelope_drift_is_source_failure_with_hash_linked_evidence(
        envelope, expected_pointer, change):
    evidence = _evidence("members", "")
    report = classify_source_envelope(
        "members", envelope, run_id=RUN_ID, source_evidence=evidence,
        count_field="memberCount",
    )

    finding = next(item for item in report.source_failures
                   if item.json_pointer == expected_pointer)
    assert report.source_failed
    assert finding.change == change
    assert finding.source_evidence.sha256 == evidence["sha256"]
    assert finding.source_evidence.path == evidence["path"]
    assert "do-not-report" not in json.dumps(report.as_dict())


def test_api_envelope_classifies_changed_and_inconsistent_counts_without_raw_values():
    evidence = _evidence("parties", "")
    envelope = {"head": {"counts": {"partyCount": 17}}, "results": []}

    changed = classify_source_envelope(
        "parties", envelope, run_id=RUN_ID, source_evidence=evidence,
        count_field="partyCount", expected_count=16,
    )
    mismatch = classify_source_envelope(
        "parties", envelope, run_id=RUN_ID, source_evidence=evidence,
        count_field="partyCount", observed_record_count=0,
    )

    assert changed.source_failures[0].change == "advertised_count_changed"
    assert mismatch.source_failures[0].change == "advertised_count_mismatch"
    assert changed.source_failures[0].observed == "different integer"
