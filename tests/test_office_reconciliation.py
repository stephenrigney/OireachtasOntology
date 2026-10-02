from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

import pytest

from oireachtas_etl.cli import main
from oireachtas_etl.office_observations import canonical_json, extract_office_observations, json_hash
from oireachtas_etl.office_reconciliation import (
    OfficeOccurrenceStore,
    OfficeReviewError,
    generate_office_candidates,
    load_office_review,
    pattern_hints,
)
from oireachtas_etl.transforms.offices import office_iri
from oireachtas_etl.validation.offices import validate_registry_source


MEMBER_IRI = "https://data.oireachtas.ie/ie/oireachtas/member/id/Synthetic.Member.2000-01-01"
MEMBERSHIP_IRI = MEMBER_IRI + "/house/dail/34"
HOUSE_IRI = "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
RAW_HASH = hashlib.sha256(b"immutable raw response").hexdigest()
REVIEW_HASH = hashlib.sha256(b"review-file-version-1").hexdigest()


def wrapper(label: str = "Minister for Synthetic Affairs", *, start="2024-01-01",
            end=None, source_uri=None) -> dict:
    return {"member": {
        "memberCode": "Synthetic.Member.2000-01-01",
        "uri": MEMBER_IRI,
        "image": False,
        "memberships": [{"membership": {
            "uri": MEMBERSHIP_IRI,
            "house": {"houseCode": "dail", "houseNo": "34", "uri": HOUSE_IRI},
            "dateRange": {"start": "2020-02-08", "end": None},
            "offices": [{"office": {
                "officeName": {"showAs": label, "uri": source_uri},
                "dateRange": {"start": start, "end": end},
            }}],
        }}],
    }}


def pointer(path="members/test.json", json_pointer="/results/0"):
    return {"path": path, "sha256": RAW_HASH, "json_pointer": json_pointer}


def observations_for(source: dict, *, json_pointer="/results/0") -> list[dict]:
    return extract_office_observations([(source, pointer(json_pointer=json_pointer))])


def empty_registry() -> dict:
    return {"version": 1, "administrative_units": [], "offices": []}


def synthetic_registry(*, two_units: bool = False) -> dict:
    units = []
    offices = []
    if two_units:
        units = [
            {"key": "u-000001", "label_en": "Department Alpha", "aliases": [],
             "reviewer_notes": "Synthetic test unit; not registry evidence.",
             "evidence": ["tests/test_office_reconciliation.py#alpha"]},
            {"key": "u-000002", "label_en": "Department Beta", "aliases": [],
             "reviewer_notes": "Synthetic test unit; not registry evidence.",
             "evidence": ["tests/test_office_reconciliation.py#beta"]},
        ]
        label = "Minister of State at Department Alpha and at Department Beta"
        for number, unit_key in ((1, "u-000001"), (2, "u-000002")):
            offices.append({
                "key": f"o-{number:06d}",
                "label_en": f"Minister of State at Department {'Alpha' if number == 1 else 'Beta'}",
                "aliases": [{"language": "en", "label": label, "contexts": ["dail"],
                             "unit_keys": [unit_key],
                             "validity": {"start": "2020-01-01", "end": None}}],
                "office_type": "MinisterOfStateOfficeType",
                "unit_relationships": [{"relationship": "assignedToAdministrativeUnit",
                                         "unit_key": unit_key}],
                "reviewer_notes": "Synthetic test office; not registry evidence.",
                "evidence": [f"tests/test_office_reconciliation.py#office-{number}"],
            })
    else:
        offices = [{
            "key": "o-000001",
            "label_en": "Synthetic ministerial office",
            "aliases": [{"language": "en", "label": "Minister for Synthetic Affairs",
                         "contexts": ["dail"],
                         "validity": {"start": "2020-01-01", "end": None},
                         "source_uris": ["https://data.oireachtas.ie/ie/oireachtas/office/synthetic"],
                         "unit_keys": []}],
            "office_type": "MinisterOfficeType",
            "unit_relationships": [],
            "reviewer_notes": "Synthetic test office; not registry evidence.",
            "evidence": ["tests/test_office_reconciliation.py#office"],
        }]
    registry = {"version": 1, "administrative_units": units, "offices": offices}
    validate_registry_source(registry)
    return registry


def write_review(path: Path, decisions: dict) -> str:
    value = {"version": 1, "decisions": decisions}
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(raw, encoding="utf-8")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_source_extractor_captures_every_generic_observation_and_exact_raw_evidence():
    root = Path(__file__).resolve().parents[1]
    sample = json.loads((root / "data/api_examples/member.json").read_text(encoding="utf-8"))
    extracted = extract_office_observations([(sample, pointer(json_pointer=""))])
    source_offices = [wrapped["office"] for wrapped_membership in sample["member"]["memberships"]
                      for wrapped in wrapped_membership["membership"].get("offices", [])]
    assert len(extracted) == len(source_offices) == 2
    assert {item["membership_iri"] for item in extracted} == {
        "https://data.oireachtas.ie/ie/oireachtas/member/id/Timmy-Dooley.S.2002-09-12/house/dail/34"
    }
    assert {item["house_context"]["house_term_iri"] for item in extracted} == {
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/34"
    }
    assert [item["date_range"] for item in extracted] == [
        {"start": "2025-02-25", "end": "2025-06-01"},
        {"start": "2025-06-02", "end": None},
    ]
    assert all(item["source_office_uri"] is None for item in extracted)
    assert all(item["snapshot"]["raw_office"]["officeName"]["showAs"] == item["label"]
               for item in extracted)
    assert [item["raw_pointers"][0]["json_pointer"] for item in extracted] == [
        "/member/memberships/3/membership/offices/0/office",
        "/member/memberships/3/membership/offices/1/office",
    ]


@pytest.mark.parametrize("mutation, message", [
    (lambda value: value["member"]["memberships"][0]["membership"]["offices"][0]["office"]["dateRange"].update(start="not-a-date"), "office.dateRange contains invalid date evidence"),
    (lambda value: value["member"]["memberships"][0]["membership"]["offices"][0]["office"]["officeName"].update(uri="https://evil.example/office"), "office.officeName.uri must use canonical"),
    (lambda value: value["member"]["memberships"][0]["membership"]["house"].update(uri="https://data.oireachtas.ie/ie/oireachtas/house/seanad/34"), "house.uri must match"),
])
def test_source_extractor_fails_closed_on_invalid_office_or_containing_house_evidence(mutation, message):
    broken = wrapper()
    mutation(broken)
    with pytest.raises(ValueError, match=message):
        observations_for(broken)


def test_reviewed_alias_context_date_unit_and_source_uri_only_generate_registered_candidates():
    registry = synthetic_registry()
    good = wrapper(source_uri="https://data.oireachtas.ie/ie/oireachtas/office/synthetic")
    result = generate_office_candidates(observations_for(good)[0], registry)
    assert result["candidate_iris"] == [str(office_iri("o-000001"))]
    assert result["auto_accept"] is True
    assert result["candidates"][0]["matched_by"] == ["exact-reviewed-alias", "reviewed-source-uri"]

    uri_only = wrapper(label="Unfamiliar but URI-reviewed wording",
                       source_uri="https://data.oireachtas.ie/ie/oireachtas/office/synthetic")
    assert generate_office_candidates(observations_for(uri_only)[0], registry)["candidate_iris"] == [
        str(office_iri("o-000001"))
    ]

    wrong_date = wrapper(start="2019-01-01", end="2019-12-31")
    scoped = generate_office_candidates(observations_for(wrong_date)[0], registry)
    assert scoped["candidate_iris"] == []
    assert any(item["kind"] == "date-scope-mismatch" for item in scoped["conflicts"])

    wrong_context = observations_for(good)[0]
    wrong_context["house_context"]["house_code"] = "seanad"
    scoped = generate_office_candidates(wrong_context, registry)
    assert scoped["candidate_iris"] == []
    assert any(item["kind"] == "context-scope-mismatch" for item in scoped["conflicts"])


def test_department_wording_without_reviewed_unit_scope_never_auto_accepts():
    unit = {"key": "u-000001", "label_en": "Department Alpha", "aliases": [],
            "reviewer_notes": "Synthetic unit; not registry evidence.",
            "evidence": ["tests/test_office_reconciliation.py#unit-scope"]}
    office = {"key": "o-000001", "label_en": "Minister of State at Department Alpha",
              "aliases": [{"language": "en", "label": "Minister of State at Department Alpha"}],
              "office_type": "MinisterOfStateOfficeType", "unit_relationships": [],
              "reviewer_notes": "Synthetic office; not registry evidence.",
              "evidence": ["tests/test_office_reconciliation.py#unit-scope-office"]}
    registry = {"version": 1, "administrative_units": [unit], "offices": [office]}
    result = generate_office_candidates(observations_for(wrapper(office["label_en"]))[0], registry)
    assert result["candidate_iris"] == [str(office_iri("o-000001"))]
    assert result["auto_accept"] is False
    assert any(item["kind"] == "unit-scope-unreviewed" for item in result["conflicts"])


def test_multi_department_candidates_are_registry_only_and_require_reviewed_multi_target_decision(tmp_path):
    registry = synthetic_registry(two_units=True)
    label = "Minister of State at Department Alpha and at Department Beta"
    obs = observations_for(wrapper(label))[0]
    candidates = generate_office_candidates(obs, registry)
    targets = [str(office_iri("o-000001")), str(office_iri("o-000002"))]
    assert candidates["candidate_iris"] == targets
    assert candidates["multi_department"] is True
    assert "MinisterOfStateOfficeType" in candidates["type_hints"]
    assert candidates["auto_accept"] is False

    key = "occ-" + obs["identity_key"]
    review_path = tmp_path / "office-decisions.json"
    review_hash = write_review(review_path, {key: {
        "status": "accepted", "office_iris": targets,
        "evidence": ["review:simultaneous-department-appointments"],
        "reason": "Synthetic test evidence establishes both local offices.",
        "observation_fingerprint": obs["fingerprint"],
    }})
    decisions, loaded_hash = load_office_review(review_path, registry)
    assert loaded_hash == review_hash
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        result = store.reconcile([obs], registry, decisions, loaded_hash)
        record = result["records"][0]
        assert record["status"] == "accepted"
        assert record["office_iris"] == targets
        assert all(target in {str(office_iri(entry["key"])) for entry in registry["offices"]}
                   for target in record["office_iris"])


def test_wording_patterns_are_hints_not_created_office_identities():
    examples = {
        "Taoiseach": "TaoiseachOfficeType",
        "Tánaiste": "TanaisteOfficeType",
        "Minister for Finance": "MinisterOfficeType",
        "Minister of State at Department Alpha": "MinisterOfStateOfficeType",
        "MoS at Department Alpha": "MinisterOfStateOfficeType",
        "Ceann Comhairle": "CeannComhairleOfficeType",
        "Cathaoirleach": "CathaoirleachOfficeType",
        "Attorney General": "AttorneyGeneralOfficeType",
        "AG": "AttorneyGeneralOfficeType",
    }
    for label, hint in examples.items():
        assert hint in pattern_hints(label)
        candidates = generate_office_candidates(observations_for(wrapper(label))[0], empty_registry())
        assert candidates["candidate_iris"] == []
        assert candidates["candidates"] == []
    assert "historical-wording" in pattern_hints("Former Minister for Finance")


def test_identifiable_date_correction_preserves_key_and_both_raw_snapshots(tmp_path):
    registry = synthetic_registry()
    before = observations_for(wrapper())
    after = observations_for(wrapper(start="2024-01-02"), json_pointer="/results/1")
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        first = store.reconcile(before, registry, {}, REVIEW_HASH, run_id=str(uuid.uuid4()))
        first_record = first["records"][0]
        assert first_record["status"] == "accepted"
        second = store.reconcile(after, registry, {}, REVIEW_HASH, run_id=str(uuid.uuid4()))
        record = second["records"][0]
        assert record["occurrence_key"] == first_record["occurrence_key"]
        assert record["status"] == "review_required"
        conflict = next(item for item in record["conflicts"] if item["kind"] == "source-observation-changed")
        assert conflict["date_only"] is True
        state = store.occurrences()[0]
        assert state["previous_fingerprint"] == before[0]["fingerprint"]
        assert state["current_fingerprint"] == after[0]["fingerprint"]
        assert state["previous_snapshot"]["date_range"]["start"] == "2024-01-01"
        assert state["current_snapshot"]["date_range"]["start"] == "2024-01-02"
        assert state["previous_raw_pointers"][0]["json_pointer"].endswith("offices/0/office")
        assert state["current_raw_pointers"][0]["json_pointer"].endswith("offices/0/office")
        attempts = store.attempts(record["occurrence_key"])
        assert len(attempts) == 2
        assert attempts[-1]["previous_snapshot"]["date_range"]["start"] == "2024-01-01"


def test_last_accepted_resolution_survives_correction_absence_and_reappearance_then_rereview_updates(
        tmp_path):
    registry = synthetic_registry()
    target = str(office_iri("o-000001"))
    before = observations_for(wrapper(), json_pointer="/results/0")[0]
    corrected = observations_for(wrapper(start="2024-01-02"), json_pointer="/results/1")[0]
    key = "occ-" + before["identity_key"]
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        initial = store.reconcile([before], registry, {}, REVIEW_HASH)
        assert initial["records"][0]["status"] == "accepted"
        accepted = initial["records"][0]["last_accepted_resolution"]
        assert accepted["office_iris"] == [target]
        assert accepted["snapshot"]["date_range"]["start"] == "2024-01-01"
        assert accepted["raw_pointers"][0]["json_pointer"].startswith("/results/0/")
        assert accepted["acceptance_evidence"]["kind"] == "unique-reviewed-registry-match"
        assert accepted["review_hash"] == REVIEW_HASH

        changed = store.reconcile([corrected], registry, {}, REVIEW_HASH)
        assert changed["records"][0]["status"] == "review_required"
        assert changed["records"][0]["last_accepted_resolution"] == accepted
        assert store.occurrences()[0]["last_accepted_resolution"] == accepted

        missing = store.reconcile([], registry, {}, REVIEW_HASH)
        assert missing["records"][0]["status"] == "review_required"
        assert missing["records"][0]["last_accepted_resolution"] == accepted
        assert store.occurrences()[0]["last_accepted_resolution"] == accepted

        reappeared = store.reconcile([corrected], registry, {}, REVIEW_HASH)
        assert reappeared["records"][0]["status"] == "review_required"
        assert reappeared["records"][0]["last_accepted_resolution"] == accepted

        rereview = {
            "status": "accepted", "office_iris": [target],
            "evidence": ["review:corrected-source-snapshot"],
            "reason": "The corrected date was reviewed against the source response.",
            "observation_fingerprint": corrected["fingerprint"],
        }
        new_review_hash = hashlib.sha256(b"reviewed corrected occurrence").hexdigest()
        accepted_again = store.reconcile([corrected], registry, {key: rereview}, new_review_hash)
        assert accepted_again["records"][0]["status"] == "accepted"
        updated = accepted_again["records"][0]["last_accepted_resolution"]
        assert updated["office_iris"] == [target]
        assert updated["snapshot"]["date_range"]["start"] == "2024-01-02"
        assert updated["raw_pointers"][0]["json_pointer"].startswith("/results/1/")
        assert updated["decision"] == rereview
        assert updated["acceptance_evidence"] == {"kind": "review-decision", "decision": rereview}
        assert updated["review_hash"] == new_review_hash
        assert updated != accepted

        # A rejection is a current review outcome, not a revocation operation.
        rejected = {"status": "rejected", "office_iris": [],
                    "evidence": ["review:identity-not-supported"],
                    "reason": "The current observation was rejected for identity review."}
        rejected_result = store.reconcile([corrected], registry, {key: rejected},
                                          hashlib.sha256(b"rejection decision").hexdigest())
        assert rejected_result["records"][0]["status"] == "rejected"
        assert rejected_result["records"][0]["last_accepted_resolution"] == updated

        attempts = store.attempts(key)
        assert attempts[0]["last_accepted_resolution"] == accepted
        assert attempts[1]["last_accepted_resolution"] == accepted
        assert attempts[2]["last_accepted_resolution"] == accepted
        assert attempts[3]["last_accepted_resolution"] == accepted
        assert attempts[4]["last_accepted_resolution"] == updated
        assert attempts[5]["last_accepted_resolution"] == updated


def test_reconcile_failure_rolls_back_occurrence_and_attempt_acceptance_evidence(tmp_path, monkeypatch):
    registry = synthetic_registry()
    before = observations_for(wrapper())[0]
    corrected = observations_for(wrapper(start="2024-03-01"), json_pointer="/results/1")[0]
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        store.reconcile([before], registry, {}, REVIEW_HASH)
        before_rows, before_attempts = store.occurrences(), store.attempts()

        def fail_after_upsert(*_args, **_kwargs):
            raise RuntimeError("synthetic attempt insert failure")

        monkeypatch.setattr(store, "_attempt", fail_after_upsert)
        with pytest.raises(RuntimeError, match="synthetic attempt insert failure"):
            store.reconcile([corrected], registry, {}, REVIEW_HASH)
        assert store.occurrences() == before_rows
        assert store.attempts() == before_attempts


def _create_v1_office_state(path: Path, observation: dict, registry: dict, *, method: str) -> None:
    candidate_info = generate_office_candidates(observation, registry)
    now = "2026-01-02T03:04:05+00:00"
    registry_hash = json_hash(registry)
    decision_hash = json_hash({"legacy": "decision contents unavailable"}) if method == "review-file" else None
    key = "occ-" + observation["identity_key"]
    with sqlite3.connect(path) as connection:
        connection.executescript("""
          CREATE TABLE office_occurrence (
            occurrence_key TEXT PRIMARY KEY, identity_key TEXT NOT NULL,
            member_iri TEXT NOT NULL, membership_iri TEXT NOT NULL,
            source_presence TEXT NOT NULL CHECK(source_presence IN ('present','missing')),
            status TEXT NOT NULL CHECK(status IN ('accepted','rejected','unresolved','review_required')),
            resolution_method TEXT NOT NULL, current_fingerprint TEXT NOT NULL,
            previous_fingerprint TEXT, current_snapshot_json TEXT NOT NULL,
            previous_snapshot_json TEXT, current_candidates_json TEXT NOT NULL,
            previous_candidates_json TEXT, current_raw_pointers_json TEXT NOT NULL,
            previous_raw_pointers_json TEXT, conflicts_json TEXT NOT NULL,
            review_hash TEXT NOT NULL, registry_hash TEXT NOT NULL, decision_hash TEXT,
            last_seen_run_id TEXT NOT NULL, updated_at TEXT NOT NULL
          );
          CREATE INDEX office_occurrence_identity ON office_occurrence(identity_key, source_presence);
          CREATE TABLE office_occurrence_attempt (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            occurrence_key TEXT NOT NULL, attempted_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('accepted','rejected','unresolved','review_required')),
            resolution_method TEXT NOT NULL, fingerprint TEXT, previous_fingerprint TEXT,
            source_snapshot_json TEXT, previous_snapshot_json TEXT, candidates_json TEXT NOT NULL,
            previous_candidates_json TEXT, raw_pointers_json TEXT NOT NULL,
            previous_raw_pointers_json TEXT, conflicts_json TEXT NOT NULL,
            review_hash TEXT NOT NULL, registry_hash TEXT NOT NULL
          );
          CREATE INDEX office_occurrence_attempt_run ON office_occurrence_attempt(run_id, occurrence_key);
          PRAGMA user_version=1;
        """)
        connection.execute("""INSERT INTO office_occurrence (
          occurrence_key,identity_key,member_iri,membership_iri,source_presence,status,
          resolution_method,current_fingerprint,previous_fingerprint,current_snapshot_json,
          previous_snapshot_json,current_candidates_json,previous_candidates_json,
          current_raw_pointers_json,previous_raw_pointers_json,conflicts_json,review_hash,
          registry_hash,decision_hash,last_seen_run_id,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (key, observation["identity_key"], observation["member_iri"], observation["membership_iri"],
           "present", "accepted", method, observation["fingerprint"], None,
           canonical_json(observation["snapshot"]), None, canonical_json(candidate_info["candidates"]),
           None, canonical_json(observation["raw_pointers"]), None, "[]", REVIEW_HASH,
           registry_hash, decision_hash, "legacy-run", now))
        connection.execute("""INSERT INTO office_occurrence_attempt (
          run_id,occurrence_key,attempted_at,status,resolution_method,fingerprint,previous_fingerprint,
          source_snapshot_json,previous_snapshot_json,candidates_json,previous_candidates_json,
          raw_pointers_json,previous_raw_pointers_json,conflicts_json,review_hash,registry_hash)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ("legacy-run", key, now, "accepted", method, observation["fingerprint"], None,
           canonical_json(observation["snapshot"]), None, canonical_json(candidate_info["candidates"]),
           None, canonical_json(observation["raw_pointers"]), None, "[]", REVIEW_HASH, registry_hash))


def test_schema_v1_migration_recovers_only_unambiguous_automatic_acceptance(tmp_path):
    registry = synthetic_registry()
    observation = observations_for(wrapper(), json_pointer="/legacy/0")[0]
    automatic_state = tmp_path / "automatic-v1.sqlite"
    _create_v1_office_state(automatic_state, observation, registry,
                            method="unique-reviewed-registry-match")
    # Model the diagnosed v1 defect: the occurrence row now says review-required,
    # although an earlier automatic acceptance remains in the attempt history.
    with sqlite3.connect(automatic_state) as connection:
        connection.execute("UPDATE office_occurrence SET status='review_required',"
                           "resolution_method='review-required'")
        connection.execute("""INSERT INTO office_occurrence_attempt (
          run_id,occurrence_key,attempted_at,status,resolution_method,fingerprint,
          previous_fingerprint,source_snapshot_json,previous_snapshot_json,candidates_json,
          previous_candidates_json,raw_pointers_json,previous_raw_pointers_json,conflicts_json,
          review_hash,registry_hash)
          SELECT 'correction-run',occurrence_key,'2026-01-03T03:04:05+00:00',
          'review_required','review-required',current_fingerprint,current_fingerprint,
          current_snapshot_json,current_snapshot_json,current_candidates_json,current_candidates_json,
          current_raw_pointers_json,current_raw_pointers_json,'[]',review_hash,registry_hash
          FROM office_occurrence""")
    target = str(office_iri("o-000001"))

    with OfficeOccurrenceStore(automatic_state) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        row = store.occurrences()[0]
        accepted = row["last_accepted_resolution"]
        assert row["status"] == "review_required"
        assert accepted["office_iris"] == [target]
        assert accepted["snapshot"] == observation["snapshot"]
        assert accepted["raw_pointers"] == observation["raw_pointers"]
        assert accepted["review_hash"] == REVIEW_HASH
        assert accepted["acceptance_evidence"]["kind"] == "legacy-auto-acceptance-recovered"
        assert store.attempts()[0]["last_accepted_resolution"] == accepted
        assert store.attempts()[1]["last_accepted_resolution"] == accepted

    # V1 retained only a decision digest, not its target set or evidence. Even
    # with one candidate available, migration must not invent the reviewed IRI.
    explicit_state = tmp_path / "explicit-v1.sqlite"
    _create_v1_office_state(explicit_state, observation, registry, method="review-file")
    with OfficeOccurrenceStore(explicit_state) as store:
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert store.occurrences()[0]["last_accepted_resolution"] is None
        assert store.attempts()[0]["last_accepted_resolution"] is None


def test_unchanged_review_decision_becomes_stale_after_a_source_correction(tmp_path):
    registry = synthetic_registry()
    before = observations_for(wrapper())
    after = observations_for(wrapper(start="2024-02-01"), json_pointer="/results/1")
    key = "occ-" + before[0]["identity_key"]
    decision = {"status": "accepted", "office_iris": [str(office_iri("o-000001"))],
                "evidence": ["review:synthetic-identity"], "reason": "Synthetic reviewed identity."}
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        first = store.reconcile(before, registry, {key: decision}, REVIEW_HASH)
        assert first["records"][0]["status"] == "accepted"
        second = store.reconcile(after, registry, {key: decision}, REVIEW_HASH)
        record = second["records"][0]
        assert record["occurrence_key"] == key
        assert record["status"] == "review_required"
        assert any(item["kind"] == "review-decision-stale-after-source-change"
                   for item in record["conflicts"])
        refreshed = dict(decision, reason="Reviewed again after the source date correction.",
                         observation_fingerprint=after[0]["fingerprint"])
        result = store.reconcile(after, registry, {key: refreshed},
                                 hashlib.sha256(b"updated review file").hexdigest())
        assert result["records"][0]["status"] == "accepted"
        removed = store.reconcile(after, registry, {},
                                  hashlib.sha256(b"decision removed").hexdigest())
        assert removed["records"][0]["status"] == "review_required"
        assert any(item["kind"] == "review-decision-removed"
                   for item in removed["records"][0]["conflicts"])
        later = store.reconcile(after, registry, {},
                                hashlib.sha256(b"decision still absent").hexdigest())
        assert later["records"][0]["status"] == "review_required"


@pytest.mark.parametrize("status", ["rejected", "unresolved"])
def test_explicit_nonacceptance_decisions_are_distinct_from_missing_decisions(tmp_path, status):
    observation = observations_for(wrapper())[0]
    key = "occ-" + observation["identity_key"]
    decision = {"status": status, "office_iris": [], "evidence": ["review:synthetic"],
                "reason": "Synthetic explicit non-acceptance."}
    with OfficeOccurrenceStore(tmp_path / f"{status}.sqlite") as store:
        result = store.reconcile([observation], empty_registry(), {key: decision}, REVIEW_HASH)
        assert result["records"][0]["status"] == status


def test_duplicate_source_reports_share_occurrence_and_retain_all_raw_pointers(tmp_path):
    source = wrapper()
    observations = extract_office_observations([
        (source, pointer(json_pointer="/results/0")),
        (copy.deepcopy(source), pointer(json_pointer="/results/1")),
    ])
    assert len(observations) == 2
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        result = store.reconcile(observations, empty_registry(), {}, REVIEW_HASH)
        assert result["processed"] == 1
        assert len(result["records"]) == 1
        assert result["records"][0]["status"] == "review_required"
        row = store.occurrences()[0]
        assert len(row["current_raw_pointers"]) == 2
        assert {pointer["json_pointer"].split("/member")[0]
                for pointer in row["current_raw_pointers"]} == {"/results/0", "/results/1"}


def test_occurrence_keys_do_not_depend_on_source_office_array_order(tmp_path):
    source = wrapper()
    membership = source["member"]["memberships"][0]["membership"]
    second = copy.deepcopy(membership["offices"][0])
    second["office"]["officeName"]["showAs"] = "Ceann Comhairle"
    membership["offices"].append(second)
    first_scan = observations_for(source)
    reordered = copy.deepcopy(source)
    reordered["member"]["memberships"][0]["membership"]["offices"].reverse()
    second_scan = observations_for(reordered, json_pointer="/results/1")
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        first = store.reconcile(first_scan, empty_registry(), {}, REVIEW_HASH)
        first_keys = {item["occurrence_key"] for item in first["records"]}
        second_result = store.reconcile(second_scan, empty_registry(), {}, REVIEW_HASH)
        assert {item["occurrence_key"] for item in second_result["records"]} == first_keys
        assert all(item["status"] == "review_required" for item in second_result["records"])


def test_ambiguous_changed_reports_get_review_required_not_guessed_correspondence(tmp_path):
    registry = synthetic_registry()
    initial = observations_for(wrapper(source_uri="https://data.oireachtas.ie/ie/oireachtas/office/synthetic"))
    changed_a = observations_for(wrapper(start="2025-01-01", source_uri="https://data.oireachtas.ie/ie/oireachtas/office/synthetic"), json_pointer="/results/0")
    changed_b = observations_for(wrapper(start="2026-01-01", source_uri="https://data.oireachtas.ie/ie/oireachtas/office/synthetic"), json_pointer="/results/1")
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        first = store.reconcile(initial, registry, {}, REVIEW_HASH)
        old_key = first["records"][0]["occurrence_key"]
        result = store.reconcile(changed_a + changed_b, registry, {}, REVIEW_HASH)
        current = [item for item in result["records"] if item["source_presence"] == "present"]
        assert len(current) == 2
        assert all(item["status"] == "review_required" for item in current)
        assert all(any(conflict["kind"] == "occurrence-correspondence-ambiguous"
                       for conflict in item["conflicts"]) for item in current)
        assert all(item["occurrence_key"] != old_key for item in current)
        old = next(item for item in result["records"] if item["occurrence_key"] == old_key)
        assert old["source_presence"] == "missing"
        assert any(item["kind"] == "source-observation-absent" for item in old["conflicts"])


def test_registry_candidate_set_change_rechecks_prior_automatic_acceptance(tmp_path):
    registry = synthetic_registry()
    observation = observations_for(wrapper())[0]
    changed_registry = copy.deepcopy(registry)
    second = copy.deepcopy(registry["offices"][0])
    second["key"] = "o-000002"
    second["label_en"] = "Second synthetic office"
    second["reviewer_notes"] = "Synthetic second office; not registry evidence."
    second["evidence"] = ["tests/test_office_reconciliation.py#second-office"]
    changed_registry["offices"].append(second)
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        first = store.reconcile([observation], registry, {}, REVIEW_HASH)
        key = first["records"][0]["occurrence_key"]
        assert first["records"][0]["status"] == "accepted"
        current = store.reconcile([observation], changed_registry, {}, REVIEW_HASH)
        record = current["records"][0]
        assert record["occurrence_key"] == key
        assert record["status"] == "review_required"
        assert len(record["candidate_iris"]) == 2
        assert record["last_accepted_resolution"]["office_iris"] == first["records"][0]["office_iris"]
        assert any(item["kind"] == "candidate-set-changed" for item in record["conflicts"])


def test_missing_stale_and_unknown_decisions_are_retained_as_review_evidence(tmp_path):
    observation = observations_for(wrapper())[0]
    key = "occ-" + observation["identity_key"]
    with OfficeOccurrenceStore(tmp_path / "office.sqlite") as store:
        first = store.reconcile([observation], empty_registry(), {}, REVIEW_HASH)
        assert first["records"][0]["status"] == "review_required"
        assert any(item["kind"] == "missing-review-decision"
                   for item in first["records"][0]["conflicts"])

        explicit_unresolved = {"status": "unresolved", "office_iris": [],
                               "evidence": ["review:no-positive-identity"],
                               "reason": "No office identity is supported."}
        absent = store.reconcile([], empty_registry(), {key: explicit_unresolved},
                                 hashlib.sha256(b"review with old decision").hexdigest())
        assert key in absent["stale_decisions"]
        missing = next(item for item in absent["records"] if item["occurrence_key"] == key)
        assert missing["source_presence"] == "missing"
        assert missing["status"] == "review_required"
        assert {item["kind"] for item in missing["conflicts"]} >= {
            "source-observation-absent", "stale-review-decision"}
        assert missing["current_snapshot"]["office_label"] == observation["label"]

        unknown_key = "occ-" + "f" * 64
        unknown = {"status": "rejected", "office_iris": [],
                   "evidence": ["review:unknown-test"], "reason": "Synthetic stale key."}
        result = store.reconcile([], empty_registry(), {unknown_key: unknown}, REVIEW_HASH)
        assert result["stale_decisions"] == [unknown_key]
        assert any(attempt["occurrence_key"] == unknown_key
                   and attempt["status"] == "review_required" for attempt in store.attempts())


def test_review_rejects_unregistered_targets_and_invalid_shapes(tmp_path):
    registry = synthetic_registry()
    key = "occ-" + "a" * 64
    path = tmp_path / "review.json"
    write_review(path, {key: {"status": "accepted", "office_iris": [
        "https://data.oireachtas.ie/office/o-999999"], "evidence": ["review:test"],
        "reason": "Not registered."}})
    with pytest.raises(OfficeReviewError, match="registered full office IRIs"):
        load_office_review(path, registry)
    observation = observations_for(wrapper())[0]
    invalid = {key: {"status": "accepted", "office_iris": [
        "https://data.oireachtas.ie/office/o-999999"], "evidence": ["review:test"],
        "reason": "Not registered."}}
    with OfficeOccurrenceStore(tmp_path / "invalid-state.sqlite") as store:
        with pytest.raises(OfficeReviewError, match="registered full office IRIs"):
            store.reconcile([observation], empty_registry(), invalid, REVIEW_HASH)
        assert store.occurrences() == []
        assert store.attempts() == []
    write_review(path, {key: {"status": "accepted", "office_iris": [],
                             "evidence": ["review:test"], "reason": "Missing target."}})
    with pytest.raises(OfficeReviewError, match="registered full office IRIs"):
        load_office_review(path, registry)


def test_cli_persists_immutable_raw_response_and_reports_fixture_offices_unresolved(tmp_path, capsys):
    root = Path(__file__).resolve().parents[1]
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(empty_registry()), encoding="utf-8")
    review_file = tmp_path / "office-decisions.json"
    write_review(review_file, {})
    raw_root = tmp_path / "raw"
    state_file = tmp_path / "office.sqlite"
    result = main([
        "reconcile", "offices", "--fixture", str(root / "data/api_examples/member.json"),
        "--offline", "--registry-file", str(registry_file), "--review-file", str(review_file),
        "--office-state-file", str(state_file), "--raw-dir", str(raw_root),
    ])
    assert result == 1
    report = json.loads(capsys.readouterr().out)
    assert report["processed"] == 2
    assert report["review_required"] == 2
    assert report["stale_decisions"] == []
    assert all(item["candidate_iris"] == [] and item["office_iris"] == []
               for item in report["records"])
    assert all("MinisterOfStateOfficeType" in item["pattern_hints"]
               for item in report["records"])
    with OfficeOccurrenceStore(state_file) as store:
        rows = store.occurrences()
        assert len(rows) == 2
        for row in rows:
            raw_pointer = row["current_raw_pointers"][0]
            raw_path = raw_root / raw_pointer["path"]
            body = raw_path.read_bytes()
            assert hashlib.sha256(body).hexdigest() == raw_pointer["sha256"]
            assert raw_pointer["json_pointer"].endswith("/office")
            parsed = json.loads(body)
            target = parsed
            for component in raw_pointer["json_pointer"].split("/")[1:]:
                component = component.replace("~1", "/").replace("~0", "~")
                target = target[int(component)] if isinstance(target, list) else target[component]
            assert target["officeName"]["showAs"] == row["current_snapshot"]["office_label"]


def test_failed_source_scan_keeps_raw_evidence_but_does_not_partially_update_ledger(tmp_path):
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps(empty_registry()), encoding="utf-8")
    review_file = tmp_path / "office-decisions.json"
    write_review(review_file, {})
    fixture = tmp_path / "members.json"
    original = wrapper()
    fixture.write_text(json.dumps([original]), encoding="utf-8")
    raw_root, state_file = tmp_path / "raw", tmp_path / "office.sqlite"
    args = ["reconcile", "offices", "--fixture", str(fixture), "--offline",
            "--registry-file", str(registry_file), "--review-file", str(review_file),
            "--office-state-file", str(state_file), "--raw-dir", str(raw_root)]
    assert main(args) == 1
    with OfficeOccurrenceStore(state_file) as store:
        before_rows, before_attempts = store.occurrences(), store.attempts()
    broken = copy.deepcopy(original)
    broken["member"]["memberships"][0]["membership"]["offices"][0]["office"]["dateRange"]["start"] = "invalid"
    fixture.write_text(json.dumps([broken]), encoding="utf-8")
    with pytest.raises(ValueError, match="office.dateRange contains invalid date evidence"):
        main(args)
    with OfficeOccurrenceStore(state_file) as store:
        assert store.occurrences() == before_rows
        assert store.attempts() == before_attempts
    assert len(list(raw_root.glob("members/*/run-*/skip-000000.json"))) == 2
