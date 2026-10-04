"""Local ministerial-office candidate review and durable occurrence ledger.

This is deliberately independent of the external-identity scheduler. It never
calls Wikidata/DBpedia, changes Member RDF, or allocates NamedOffice IRIs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid

from .office_observations import canonical_json, json_hash, normalize_label
from .transforms.offices import office_iri
from .validation.offices import validate_registry_source


OCCURRENCE_KEY_RE = re.compile(r"^occ-[0-9a-f]{64}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")

_CATEGORY_PATTERNS = (
    ("TaoiseachOfficeType", (r"\btaoiseach\b",)),
    ("TanaisteOfficeType", (r"\btánaiste\b", r"\btanaiste\b", r"\bdeputy prime minister\b")),
    ("MinisterOfStateOfficeType", (r"\bminister of state\b", r"\bjunior minister\b")),
    ("MinisterOfficeType", (r"\bminister\b",)),
    ("CeannComhairleOfficeType", (r"\bceann comhairle\b",)),
    ("CathaoirleachOfficeType", (r"\bcathaoirleach\b",)),
    ("AttorneyGeneralOfficeType", (r"\battorney general\b", r"(?<!\w)a\.g\.(?!\w)")),
)
_HISTORICAL_PATTERN = re.compile(r"\b(former|historical|historic|ex-|formerly|retired)\b")
_MULTI_DEPARTMENT_PATTERN = re.compile(
    r"\bdepartment\b.*\b(and|&|also)\b.*\bdepartment\b", re.IGNORECASE
)


class OfficeReviewError(ValueError):
    """Malformed versioned local office review file or decision."""


def _instant(value: str) -> datetime:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _registry_offices(registry: dict) -> dict[str, dict]:
    validate_registry_source(registry)
    return {str(office_iri(office["key"])): office for office in registry["offices"]}


def _unit_aliases(registry: dict) -> list[tuple[str, str]]:
    entries = []
    for unit in registry["administrative_units"]:
        labels = [unit["label_en"]]
        if unit.get("label_ga"):
            labels.append(unit["label_ga"])
        labels.extend(alias["label"] for alias in unit["aliases"])
        entries.extend((normalize_label(label), unit["key"]) for label in labels if len(normalize_label(label)) >= 4)
    return sorted(set(entries))


def _unit_mentions(label: str, registry: dict) -> list[str]:
    text = normalize_label(label)
    found = set()
    for alias, key in _unit_aliases(registry):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
            found.add(key)
    return sorted(found)


def pattern_hints(label: str) -> list[str]:
    """Return cautious wording hints; these are never office identities."""
    text = normalize_label(label)
    hints = [category for category, patterns in _CATEGORY_PATTERNS
             if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)]
    if re.search(r"(?<!\w)AG(?!\w)", label) or re.search(r"(?<!\w)A\.G\.(?!\w)", label):
        hints.append("AttorneyGeneralOfficeType")
    if re.search(r"(?<!\w)MoS(?!\w)", label):
        hints.append("MinisterOfStateOfficeType")
    if _HISTORICAL_PATTERN.search(text):
        hints.append("historical-wording")
    if (_MULTI_DEPARTMENT_PATTERN.search(label)
            or (text.count("department") > 1 and re.search(r"\b(and|&|also)\b", text))):
        hints.append("multi-department-wording")
    return sorted(set(hints))


def _observation_interval(observation: dict) -> tuple[datetime, datetime | None]:
    dates = observation["date_range"]
    start = _instant(dates["start"])
    end = _instant(dates["end"]) if dates.get("end") is not None else None
    return start, end


def _validity_overlaps(validity: dict | None, observation: dict) -> bool:
    if validity is None:
        return True
    source_start, source_end = _observation_interval(observation)
    alias_start = _instant(validity["start"])
    alias_end = _instant(validity["end"]) if validity.get("end") is not None else None
    # A scoped alias is usable only if it covers the complete appointment
    # interval. Partial overlap is evidence of a possible historical rename,
    # not enough to identify the whole source observation.
    return (source_start >= alias_start
            and (alias_end is None or (source_end is not None and source_end <= alias_end)))


def generate_office_candidates(observation: dict, registry: dict) -> dict:
    """Generate local registry-only candidates and structured conflict hints."""
    offices = _registry_offices(registry)
    label = observation["label"]
    normalized = normalize_label(label)
    source_uri = observation.get("source_office_uri")
    context = observation["house_context"]
    mentioned_units = _unit_mentions(label, registry)
    hints = pattern_hints(label)
    type_hints = sorted(set(hint for hint in hints if hint in {
        "TaoiseachOfficeType", "TanaisteOfficeType", "MinisterOfficeType",
        "MinisterOfStateOfficeType", "CeannComhairleOfficeType",
        "CathaoirleachOfficeType", "AttorneyGeneralOfficeType",
    }))
    if "MinisterOfStateOfficeType" in type_hints:
        type_hints = [hint for hint in type_hints if hint != "MinisterOfficeType"]
    conflicts: list[dict] = []
    source_start, source_end = _observation_interval(observation)
    membership_range = context["membership_date_range"]
    membership_start = _instant(membership_range["start"])
    membership_end = _instant(membership_range["end"]) if membership_range.get("end") is not None else None
    if (source_start < membership_start
            or (membership_end is not None and (source_end is None or source_end > membership_end))):
        conflicts.append({"kind": "office-dates-outside-membership-context",
                          "office_date_range": observation["date_range"],
                          "membership_date_range": membership_range})
    candidates: dict[str, dict] = {}
    source_uri_candidates: set[str] = set()
    label_candidates: set[str] = set()

    for office_iri_value, office in offices.items():
        matched_aliases = []
        alias_methods: set[str] = set()
        for alias in office["aliases"]:
            alias_match = normalize_label(alias["label"]) == normalized
            uri_match = source_uri is not None and source_uri in alias.get("source_uris", [])
            if not alias_match and not uri_match:
                continue
            methods = set()
            if alias_match:
                methods.add("exact-reviewed-alias")
            if uri_match:
                methods.add("reviewed-source-uri")

            alias_contexts = alias.get("contexts", [])
            observed_contexts = {context["house_code"], context["house_term_iri"],
                                 observation["membership_iri"], observation["member_iri"],
                                 f"https://data.oireachtas.ie/house/{context['house_code']}"}
            if alias_contexts and not observed_contexts.intersection(alias_contexts):
                conflicts.append({"kind": "context-scope-mismatch", "office_iri": office_iri_value,
                                  "alias": alias["label"], "observed": sorted(observed_contexts),
                                  "reviewed": sorted(alias_contexts)})
                continue
            if not _validity_overlaps(alias.get("validity"), observation):
                conflicts.append({"kind": "date-scope-mismatch", "office_iri": office_iri_value,
                                  "alias": alias["label"], "date_range": observation["date_range"],
                                  "validity": alias["validity"]})
                continue
            alias_units = set(alias.get("unit_keys", []))
            office_units = {relation["unit_key"] for relation in office["unit_relationships"]}
            if mentioned_units:
                applicable_units = alias_units or office_units
                if not applicable_units:
                    conflicts.append({"kind": "unit-scope-unreviewed", "office_iri": office_iri_value,
                                      "mentioned_unit_keys": mentioned_units})
                elif not (set(mentioned_units) & applicable_units):
                    conflicts.append({"kind": "unit-scope-mismatch", "office_iri": office_iri_value,
                                      "mentioned_unit_keys": mentioned_units,
                                      "reviewed_unit_keys": sorted(applicable_units)})
                    continue
            alias_methods.update(methods)
            matched_aliases.append(alias["label"])
        if not alias_methods:
            continue
        if type_hints and office["office_type"] not in type_hints:
            conflicts.append({"kind": "office-type-hint-conflict", "office_iri": office_iri_value,
                              "registered_type": office["office_type"], "wording_hints": type_hints})
            continue
        if mentioned_units:
            relation_units = {relation["unit_key"] for relation in office["unit_relationships"]}
            if relation_units and not (set(mentioned_units) & relation_units):
                conflicts.append({"kind": "unit-scope-mismatch", "office_iri": office_iri_value,
                                  "mentioned_unit_keys": mentioned_units,
                                  "reviewed_unit_keys": sorted(relation_units)})
                continue
        candidates[office_iri_value] = {
            "office_iri": office_iri_value,
            "office_type": office["office_type"],
            "registry_key": office["key"],
            "matched_aliases": sorted(set(matched_aliases)),
            "matched_by": sorted(alias_methods),
            "unit_keys": sorted({relation["unit_key"] for relation in office["unit_relationships"]}),
        }
        if "reviewed-source-uri" in alias_methods:
            source_uri_candidates.add(office_iri_value)
        if "exact-reviewed-alias" in alias_methods:
            label_candidates.add(office_iri_value)

    if source_uri_candidates and label_candidates and source_uri_candidates != label_candidates:
        conflicts.append({"kind": "source-uri-label-conflict",
                          "source_uri_candidates": sorted(source_uri_candidates),
                          "label_candidates": sorted(label_candidates)})
    multiple_units = len(mentioned_units) > 1
    multi_department = multiple_units or "multi-department-wording" in hints
    return {
        "candidates": [candidates[key] for key in sorted(candidates)],
        "candidate_iris": sorted(candidates),
        "pattern_hints": hints,
        "type_hints": type_hints,
        "mentioned_unit_keys": mentioned_units,
        "multi_department": multi_department,
        "conflicts": sorted(conflicts, key=canonical_json),
        "auto_accept": (len(candidates) == 1 and not conflicts and not multi_department
                        and "historical-wording" not in hints
                        and bool(candidates[next(iter(candidates))]["matched_by"])),
    }


def _candidate_info(observation: dict, registry: dict) -> dict:
    """Return no candidates for an observation quarantined by source validation."""
    malformed_reason = observation.get("malformed_reason")
    if malformed_reason is None:
        return generate_office_candidates(observation, registry)
    label = observation.get("label")
    hints = pattern_hints(label) if isinstance(label, str) else []
    type_hints = sorted(set(hint for hint in hints if hint in {
        "TaoiseachOfficeType", "TanaisteOfficeType", "MinisterOfficeType",
        "MinisterOfStateOfficeType", "CeannComhairleOfficeType",
        "CathaoirleachOfficeType", "AttorneyGeneralOfficeType",
    }))
    return {
        "candidates": [],
        "candidate_iris": [],
        "pattern_hints": hints,
        "type_hints": type_hints,
        "mentioned_unit_keys": [],
        "multi_department": False,
        "conflicts": [{"kind": "malformed-office-observation", "reason": malformed_reason}],
        "auto_accept": False,
    }


def _json_object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OfficeReviewError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _validate_office_decisions(decisions: object, offices: dict[str, dict]) -> dict[str, dict]:
    if not isinstance(decisions, dict):
        raise OfficeReviewError("office decisions must be an object")
    for occurrence_key, decision in decisions.items():
        if not isinstance(occurrence_key, str) or not OCCURRENCE_KEY_RE.fullmatch(occurrence_key):
            raise OfficeReviewError(f"invalid office occurrence key: {occurrence_key!r}")
        required = {"status", "office_iris", "evidence", "reason"}
        optional = {"observation_fingerprint", "action"}
        if (not isinstance(decision, dict) or not required <= set(decision)
                or set(decision) - required - optional):
            raise OfficeReviewError(f"invalid decision fields for {occurrence_key}")
        status = decision["status"]
        if not isinstance(status, str) or status not in {"accepted", "rejected", "unresolved"}:
            raise OfficeReviewError(f"invalid status for {occurrence_key}")
        action = decision.get("action")
        if action is not None and action != "revoke":
            raise OfficeReviewError(f"invalid action for {occurrence_key}")
        if action == "revoke" and (status != "rejected"
                                    or decision.get("observation_fingerprint") is None):
            raise OfficeReviewError(
                f"revocation for {occurrence_key} must be rejected and bound to an observation_fingerprint")
        targets = decision["office_iris"]
        if (not isinstance(targets, list) or any(not isinstance(target, str) for target in targets)
                or len(targets) != len(set(targets))):
            raise OfficeReviewError(f"office_iris for {occurrence_key} must be a unique list")
        if status == "accepted":
            if not targets or any(target not in offices for target in targets):
                raise OfficeReviewError(f"accepted decision for {occurrence_key} needs registered full office IRIs")
        elif targets:
            raise OfficeReviewError(f"{status} decision for {occurrence_key} must have an empty office_iris list")
        evidence, reason = decision["evidence"], decision["reason"]
        if (not isinstance(evidence, list) or not evidence
                or any(not isinstance(item, str) or not item.strip() for item in evidence)
                or len(evidence) != len(set(evidence))
                or not isinstance(reason, str) or not reason.strip()):
            raise OfficeReviewError(f"decision for {occurrence_key} needs evidence references and a reason")
        fingerprint = decision.get("observation_fingerprint")
        if fingerprint is not None and (not isinstance(fingerprint, str)
                                        or not FINGERPRINT_RE.fullmatch(fingerprint)):
            raise OfficeReviewError(f"invalid observation_fingerprint for {occurrence_key}")
    return decisions


def load_office_review(path: Path, registry: dict) -> tuple[dict[str, dict], str]:
    """Load strict version-1 local decisions and validate every target IRI."""
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw, object_pairs_hook=_json_object_no_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OfficeReviewError(f"invalid office review file: {error}") from error
    if (not isinstance(value, dict) or set(value) != {"version", "decisions"}
            or type(value.get("version")) is not int or value["version"] != 1
            or not isinstance(value["decisions"], dict)):
        raise OfficeReviewError("office review file must contain only version 1 and a decisions object")
    offices = _registry_offices(registry)
    decisions = _validate_office_decisions(value["decisions"], offices)
    return decisions, hashlib.sha256(raw).hexdigest()


def _deduplicate_observations(observations: list[dict]) -> list[dict]:
    by_pair: dict[tuple[str, str], dict] = {}
    for observation in observations:
        key = (observation["identity_key"], observation["fingerprint"])
        if key not in by_pair:
            by_pair[key] = {**observation, "raw_pointers": list(observation["raw_pointers"])}
        else:
            by_pair[key]["raw_pointers"].extend(observation["raw_pointers"])
    for observation in by_pair.values():
        observation["raw_pointers"] = sorted(
            {canonical_json(pointer): pointer for pointer in observation["raw_pointers"]}.values(),
            key=canonical_json)
    return sorted(by_pair.values(), key=lambda item: (item["identity_key"], item["fingerprint"]))


def _date_only_changed(previous: object, current: object) -> bool:
    if not isinstance(previous, dict) or not isinstance(current, dict):
        return False
    old, new = json.loads(canonical_json(previous)), json.loads(canonical_json(current))
    old_range, new_range = old.get("date_range"), new.get("date_range")
    old.pop("date_range", None); new.pop("date_range", None)
    for value in (old, new):
        raw_office = value.get("raw_office")
        if isinstance(raw_office, dict):
            raw_office.pop("dateRange", None)
    return old == new and old_range != new_range


def _decision_digest(decision: dict | None) -> str | None:
    return json_hash(decision) if decision is not None else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _legacy_auto_acceptance(row: dict, *, attempt: bool) -> dict | None:
    """Recover only v1 automatic acceptances whose target is unambiguous.

    V1 did not persist reviewed decision contents or accepted target IRIs. An
    explicit review-file acceptance therefore cannot be reconstructed safely.
    """
    if row["status"] != "accepted" or row["resolution_method"] != "unique-reviewed-registry-match":
        return None
    candidates_field = "candidates_json" if attempt else "current_candidates_json"
    snapshot_field = "source_snapshot_json" if attempt else "current_snapshot_json"
    pointers_field = "raw_pointers_json" if attempt else "current_raw_pointers_json"
    fingerprint_field = "fingerprint" if attempt else "current_fingerprint"
    timestamp_field = "attempted_at" if attempt else "updated_at"
    candidates = json.loads(row[candidates_field]) if row[candidates_field] else None
    snapshot = json.loads(row[snapshot_field]) if row[snapshot_field] else None
    pointers = json.loads(row[pointers_field]) if row[pointers_field] else None
    if (not isinstance(candidates, list) or len(candidates) != 1
            or not isinstance(candidates[0], dict)
            or not isinstance(candidates[0].get("office_iri"), str)
            or not isinstance(snapshot, dict) or not isinstance(pointers, list)):
        return None
    candidate = candidates[0]
    return {
        "office_iris": [candidate["office_iri"]],
        "fingerprint": row[fingerprint_field],
        "snapshot": snapshot,
        "raw_pointers": pointers,
        "candidates": candidates,
        "decision": None,
        "decision_hash": None,
        "review_hash": row["review_hash"],
        "registry_hash": row["registry_hash"],
        "resolution_method": "unique-reviewed-registry-match",
        "acceptance_evidence": {
            "kind": "legacy-auto-acceptance-recovered",
            "candidate": candidate,
        },
        "accepted_at": row[timestamp_field],
    }


def _accepted_resolution(observation: dict, candidates: list[dict], targets: list[str],
                         decision: dict | None, decision_hash: str | None,
                         review_hash: str, registry_hash: str, method: str,
                         accepted_at: str) -> dict:
    if decision is None:
        evidence = {"kind": "unique-reviewed-registry-match", "candidate": candidates[0]}
    else:
        evidence = {"kind": "review-decision", "decision": decision}
    return {
        "office_iris": sorted(targets),
        "fingerprint": observation["fingerprint"],
        "snapshot": observation["snapshot"],
        "raw_pointers": observation["raw_pointers"],
        "candidates": candidates,
        "decision": decision,
        "decision_hash": decision_hash,
        "review_hash": review_hash,
        "registry_hash": registry_hash,
        "resolution_method": method,
        "acceptance_evidence": evidence,
        "accepted_at": accepted_at,
    }


class OfficeOccurrenceStore:
    """Atomic durable evidence and correspondence ledger for office reports."""

    def __init__(self, path: Path | str):
        self._in_memory = str(path) == ":memory:"
        self.path = Path(path).expanduser() if not self._in_memory else Path(":memory:")
        if not self._in_memory:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._in_memory and self.path.exists() and self.path.stat().st_size:
            with self.path.open("rb") as handle:
                if handle.read(16) != b"SQLite format 3\x00":
                    raise ValueError(f"office occurrence state path is not SQLite: {self.path}")
        database = ":memory:" if self._in_memory else self.path
        self.connection = sqlite3.connect(database, timeout=30, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self.connection.execute("PRAGMA synchronous=FULL")
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _initialize(self) -> None:
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise ValueError(f"unsupported office occurrence state schema version: {version}")
        if version == 1:
            self._migrate_v1()
        elif version == 2:
            tables = {row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"office_occurrence", "office_occurrence_attempt"} <= tables:
                raise ValueError("office occurrence SQLite state schema is incomplete")
            columns = {table: {row[1] for row in self.connection.execute(
                f"PRAGMA table_info({table})")} for table in (
                    "office_occurrence", "office_occurrence_attempt")}
            if any("last_accepted_resolution_json" not in columns[table] for table in columns):
                raise ValueError("office occurrence SQLite state schema is incomplete")
        else:
            self.connection.executescript("""
              BEGIN IMMEDIATE;
              CREATE TABLE office_occurrence (
                occurrence_key TEXT PRIMARY KEY,
                identity_key TEXT NOT NULL,
                member_iri TEXT NOT NULL,
                membership_iri TEXT NOT NULL,
                source_presence TEXT NOT NULL CHECK(source_presence IN ('present','missing')),
                status TEXT NOT NULL CHECK(status IN ('accepted','rejected','unresolved','review_required')),
                resolution_method TEXT NOT NULL,
                current_fingerprint TEXT NOT NULL,
                previous_fingerprint TEXT,
                current_snapshot_json TEXT NOT NULL,
                previous_snapshot_json TEXT,
                current_candidates_json TEXT NOT NULL,
                previous_candidates_json TEXT,
                current_raw_pointers_json TEXT NOT NULL,
                previous_raw_pointers_json TEXT,
                conflicts_json TEXT NOT NULL,
                review_hash TEXT NOT NULL,
                registry_hash TEXT NOT NULL,
                decision_hash TEXT,
                last_seen_run_id TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_accepted_resolution_json TEXT
              );
              CREATE INDEX office_occurrence_identity ON office_occurrence(identity_key, source_presence);
              CREATE TABLE office_occurrence_attempt (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                occurrence_key TEXT NOT NULL,
                attempted_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('accepted','rejected','unresolved','review_required')),
                resolution_method TEXT NOT NULL,
                fingerprint TEXT,
                previous_fingerprint TEXT,
                source_snapshot_json TEXT,
                previous_snapshot_json TEXT,
                candidates_json TEXT NOT NULL,
                previous_candidates_json TEXT,
                raw_pointers_json TEXT NOT NULL,
                previous_raw_pointers_json TEXT,
                conflicts_json TEXT NOT NULL,
                review_hash TEXT NOT NULL,
                registry_hash TEXT NOT NULL,
                last_accepted_resolution_json TEXT
              );
              CREATE INDEX office_occurrence_attempt_run ON office_occurrence_attempt(run_id, occurrence_key);
              PRAGMA user_version=2;
              COMMIT;
            """)

    def _migrate_v1(self) -> None:
        """Add accepted-resolution state without guessing unavailable decisions."""
        connection = self.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"office_occurrence", "office_occurrence_attempt"} <= tables:
                raise ValueError("office occurrence SQLite state schema is incomplete")
            for table in ("office_occurrence", "office_occurrence_attempt"):
                columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                if "last_accepted_resolution_json" in columns:
                    raise ValueError("office occurrence SQLite v1 schema is incomplete")
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN last_accepted_resolution_json TEXT")

            latest_by_occurrence: dict[str, dict | None] = {}
            attempt_rows = connection.execute(
                "SELECT * FROM office_occurrence_attempt ORDER BY attempt_id").fetchall()
            for row in attempt_rows:
                attempt = dict(row)
                key = attempt["occurrence_key"]
                if attempt["status"] == "accepted":
                    # An unrecoverable explicit acceptance supersedes any older
                    # recoverable automatic one; do not resurrect stale targets.
                    latest_by_occurrence[key] = _legacy_auto_acceptance(attempt, attempt=True)
                current = latest_by_occurrence.get(key)
                connection.execute(
                    "UPDATE office_occurrence_attempt SET last_accepted_resolution_json=? WHERE attempt_id=?",
                    (canonical_json(current) if current is not None else None, attempt["attempt_id"]))

            for row in connection.execute("SELECT * FROM office_occurrence").fetchall():
                occurrence = dict(row)
                key = occurrence["occurrence_key"]
                if key in latest_by_occurrence:
                    resolution = latest_by_occurrence[key]
                elif occurrence["status"] == "accepted":
                    resolution = _legacy_auto_acceptance(occurrence, attempt=False)
                else:
                    resolution = None
                connection.execute(
                    "UPDATE office_occurrence SET last_accepted_resolution_json=? WHERE occurrence_key=?",
                    (canonical_json(resolution) if resolution is not None else None, key))
            connection.execute("PRAGMA user_version=2")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

    def occurrences(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM office_occurrence ORDER BY occurrence_key").fetchall()
        output = []
        for row in rows:
            item = dict(row)
            for field in ("current_snapshot_json", "previous_snapshot_json", "current_candidates_json",
                          "previous_candidates_json", "current_raw_pointers_json",
                          "previous_raw_pointers_json", "conflicts_json",
                          "last_accepted_resolution_json"):
                value = item.pop(field)
                item[field.removesuffix("_json")] = json.loads(value) if value is not None else None
            output.append(item)
        return output

    def attempts(self, occurrence_key: str | None = None) -> list[dict]:
        if occurrence_key is None:
            rows = self.connection.execute(
                "SELECT * FROM office_occurrence_attempt ORDER BY attempt_id").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM office_occurrence_attempt WHERE occurrence_key=? ORDER BY attempt_id",
                (occurrence_key,)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            for field in ("source_snapshot_json", "previous_snapshot_json", "candidates_json",
                          "previous_candidates_json", "raw_pointers_json", "previous_raw_pointers_json",
                          "conflicts_json", "last_accepted_resolution_json"):
                value = item.pop(field)
                item[field.removesuffix("_json")] = json.loads(value) if value is not None else None
            output.append(item)
        return output

    def reconcile(self, observations: list[dict], registry: dict, decisions: dict[str, dict],
                  review_hash: str, *, run_id: str | None = None) -> dict:
        """Atomically reconcile a complete local source scan and review snapshot."""
        registry = validate_registry_source(registry)
        registered_offices = _registry_offices(registry)
        decisions = _validate_office_decisions(decisions, registered_offices)
        registry_hash = json_hash(registry)
        if not isinstance(review_hash, str) or not FINGERPRINT_RE.fullmatch(review_hash):
            raise ValueError("office review hash must be a SHA-256 digest")
        current = _deduplicate_observations(observations)
        prepared = [(observation, _candidate_info(observation, registry))
                    for observation in current]
        run_id = run_id or str(uuid.uuid4())
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("office reconciliation run_id must be non-empty")
        connection = self.connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            prior_rows = [dict(row) for row in connection.execute("SELECT * FROM office_occurrence")]
            by_identity: dict[str, list[dict]] = {}
            for row in prior_rows:
                by_identity.setdefault(row["identity_key"], []).append(row)
            current_groups: dict[str, list[tuple[dict, dict]]] = {}
            for item in prepared:
                current_groups.setdefault(item[0]["identity_key"], []).append(item)

            assigned: dict[str, list[tuple[dict, dict, dict | None, str, bool, bool]]] = {}
            matched_keys: set[str] = set()
            for identity_key, group in sorted(current_groups.items()):
                old_group = sorted(by_identity.get(identity_key, []), key=lambda item: item["occurrence_key"])
                pending_current = list(group)
                pending_old = list(old_group)
                matched: list[tuple[dict, dict, dict | None, str, bool, bool]] = []
                # Exact source snapshots retain their occurrence keys regardless
                # of duplicate API reports or raw page locations.
                for current_pair in list(pending_current):
                    exact = [row for row in pending_old
                             if row["current_fingerprint"] == current_pair[0]["fingerprint"]]
                    if len(exact) == 1:
                        old = exact[0]
                        pending_old.remove(old); pending_current.remove(current_pair)
                        matched.append((current_pair[0], current_pair[1], old,
                                        old["occurrence_key"], False, False))
                    elif len(exact) > 1:
                        # Duplicate historical keys for one exact observation is
                        # an inconsistent ledger, not a place to choose by order.
                        raise ValueError(f"ambiguous duplicate occurrence ledger rows for {identity_key}")
                correspondence_ambiguous = bool(
                    pending_old and pending_current
                    and not (len(pending_old) == 1 and len(pending_current) == 1)
                )
                if len(pending_old) == 1 and len(pending_current) == 1:
                    old, current_pair = pending_old[0], pending_current[0]
                    pending_old.clear(); pending_current.clear()
                    matched.append((current_pair[0], current_pair[1], old,
                                    old["occurrence_key"], True, False))
                else:
                    for current_pair in pending_current:
                        identity_material = {"identity_key": identity_key,
                                             "fingerprint": current_pair[0]["fingerprint"]}
                        occurrence_key = "occ-" + json_hash(identity_material)
                        if len(group) == 1 and not old_group:
                            occurrence_key = "occ-" + identity_key
                        matched.append((current_pair[0], current_pair[1], None,
                                        occurrence_key, False, correspondence_ambiguous))
                for item in matched:
                    if item[3] in matched_keys:
                        raise ValueError(f"office occurrence key collision: {item[3]}")
                    matched_keys.add(item[3])
                assigned[identity_key] = matched

            current_keys = {item[3] for group in assigned.values() for item in group}
            unknown_decisions = sorted(set(decisions) - current_keys - {row["occurrence_key"] for row in prior_rows})
            stale_decisions = sorted(set(decisions) - current_keys)
            current_scopes = {(item[0]["member_iri"], item[0]["membership_iri"])
                              for group in assigned.values() for item in group}
            current_identity_scopes = {(item[0]["identity_key"], item[0]["member_iri"],
                                        item[0]["membership_iri"])
                                       for group in assigned.values() for item in group}
            uncertain_scope_changes = {
                (identity_key, member_iri, membership_iri)
                for row in prior_rows
                if row["occurrence_key"] not in current_keys
                and (row["member_iri"], row["membership_iri"]) in current_scopes
                for identity_key, member_iri, membership_iri in current_identity_scopes
                if member_iri == row["member_iri"] and membership_iri == row["membership_iri"]
                and identity_key != row["identity_key"]
            }
            now = _now()
            records: list[dict] = []

            for identity_key in sorted(assigned):
                group = assigned[identity_key]
                group_has_multiple_distinct = len(group) > 1
                for observation, candidate_info, old, occurrence_key, source_changed, correspondence_ambiguous in group:
                    decision = decisions.get(occurrence_key)
                    old_decision_hash = old["decision_hash"] if old else None
                    decision_hash = _decision_digest(decision)
                    previous_snapshot = json.loads(old["current_snapshot_json"]) if old else None
                    previous_candidates = json.loads(old["current_candidates_json"]) if old else None
                    previous_pointers = json.loads(old["current_raw_pointers_json"]) if old else None
                    candidate_iris = candidate_info["candidate_iris"]
                    candidate_changed = bool(old and previous_candidates != candidate_info["candidates"])
                    conflicts = list(candidate_info["conflicts"])
                    if source_changed:
                        conflicts.append({"kind": "source-observation-changed",
                                          "date_only": _date_only_changed(previous_snapshot,
                                                                          observation["snapshot"]),
                                          "previous_fingerprint": old["current_fingerprint"],
                                          "current_fingerprint": observation["fingerprint"]})
                    reappeared = bool(old and old["source_presence"] == "missing")
                    if reappeared:
                        conflicts.append({"kind": "source-observation-reappeared-after-absence"})
                    if candidate_changed:
                        conflicts.append({"kind": "candidate-set-changed",
                                          "previous_candidates": previous_candidates,
                                          "current_candidates": candidate_info["candidates"]})
                    if correspondence_ambiguous:
                        conflicts.append({"kind": "occurrence-correspondence-ambiguous",
                                          "possible_previous_keys": sorted(row["occurrence_key"]
                                                                            for row in by_identity.get(identity_key, []))})
                    if group_has_multiple_distinct:
                        conflicts.append({"kind": "same-identity-multiple-observations",
                                          "current_fingerprints": sorted(item[0]["fingerprint"]
                                                                          for item in group)})
                    if candidate_info["multi_department"]:
                        conflicts.append({"kind": "multi-department-observation",
                                          "mentioned_unit_keys": candidate_info["mentioned_unit_keys"]})
                    if (old is None and (identity_key, observation["member_iri"],
                                         observation["membership_iri"]) in uncertain_scope_changes):
                        conflicts.append({"kind": "possible-same-scope-source-change"})
                    if decision and decision.get("observation_fingerprint") not in (None, observation["fingerprint"]):
                        conflicts.append({"kind": "review-fingerprint-stale",
                                          "reviewed_fingerprint": decision["observation_fingerprint"],
                                          "current_fingerprint": observation["fingerprint"]})
                    malformed_reason = observation.get("malformed_reason")
                    if malformed_reason is not None and decision is not None:
                        conflicts.append({"kind": "review-decision-not-applied-to-malformed-observation",
                                          "decision_status": decision["status"]})
                    same_decision_as_before = bool(old and old_decision_hash == decision_hash)
                    decision_removed = bool(old and old_decision_hash is not None and decision is None)
                    if decision_removed:
                        conflicts.append({"kind": "review-decision-removed"})
                    if decision and source_changed and same_decision_as_before:
                        conflicts.append({"kind": "review-decision-stale-after-source-change"})
                    if decision and candidate_changed and same_decision_as_before:
                        conflicts.append({"kind": "review-decision-stale-after-candidate-change"})
                    if decision and reappeared and same_decision_as_before:
                        conflicts.append({"kind": "review-decision-stale-after-absence"})

                    hard_correspondence_conflict = correspondence_ambiguous
                    stale_review = any(item["kind"] in {
                        "review-fingerprint-stale", "review-decision-stale-after-source-change",
                        "review-decision-stale-after-candidate-change", "review-decision-stale-after-absence",
                        "review-decision-removed",
                    } for item in conflicts)
                    if malformed_reason is not None:
                        status, method = "review_required", "malformed-source-quarantine"
                    elif hard_correspondence_conflict or stale_review or (reappeared and decision is None):
                        status, method = "review_required", "review-required"
                    elif decision is not None:
                        status, method = decision["status"], "review-file"
                    elif (candidate_info["auto_accept"] and not group_has_multiple_distinct
                          and not source_changed and not candidate_changed and not reappeared
                          and (identity_key, observation["member_iri"],
                               observation["membership_iri"]) not in uncertain_scope_changes):
                        status, method = "accepted", "unique-reviewed-registry-match"
                    else:
                        status, method = "review_required", "candidate-review-required"
                        if not candidate_info["candidates"]:
                            conflicts.append({"kind": "no-registered-candidate"})
                        if decision is None:
                            conflicts.append({"kind": "missing-review-decision"})

                    accepted_targets = (sorted(decision["office_iris"]) if status == "accepted" and decision
                                        else candidate_iris if status == "accepted" else [])
                    last_accepted_resolution = (
                        json.loads(old["last_accepted_resolution_json"])
                        if old and old["last_accepted_resolution_json"] else None
                    )
                    if status == "accepted":
                        last_accepted_resolution = _accepted_resolution(
                            observation, candidate_info["candidates"], accepted_targets,
                            decision, decision_hash, review_hash, registry_hash, method, now)

                    record = {
                        "occurrence_key": occurrence_key,
                        "identity_key": identity_key,
                        "member_iri": observation["member_iri"],
                        "membership_iri": observation["membership_iri"],
                        "source_presence": "present",
                        "status": status,
                        "resolution_method": method,
                        "current_fingerprint": observation["fingerprint"],
                        "previous_fingerprint": old["current_fingerprint"] if source_changed and old else (old["previous_fingerprint"] if old else None),
                        "current_snapshot": observation["snapshot"],
                        "previous_snapshot": previous_snapshot if source_changed else (json.loads(old["previous_snapshot_json"]) if old and old["previous_snapshot_json"] else None),
                        "current_candidates": candidate_info["candidates"],
                        "previous_candidates": previous_candidates if candidate_changed else (json.loads(old["previous_candidates_json"]) if old and old["previous_candidates_json"] else None),
                        "current_raw_pointers": observation["raw_pointers"],
                        "previous_raw_pointers": previous_pointers if source_changed else (json.loads(old["previous_raw_pointers_json"]) if old and old["previous_raw_pointers_json"] else None),
                        "conflicts": sorted(conflicts, key=canonical_json),
                        "review_hash": review_hash,
                        "registry_hash": registry_hash,
                        # Retain the last explicit decision digest when an entry
                        # disappears, so later scans cannot silently fall back
                        # to an automatic alias match.
                        "decision_hash": decision_hash if decision_hash is not None else old_decision_hash,
                        "last_seen_run_id": run_id,
                        "updated_at": now,
                        "office_iris": accepted_targets,
                        "last_accepted_resolution": last_accepted_resolution,
                        "candidate_iris": candidate_iris,
                        "label": observation["label"],
                        "date_range": observation["date_range"],
                        "pattern_hints": candidate_info["pattern_hints"],
                    }
                    if malformed_reason is not None:
                        record["malformed_reason"] = malformed_reason
                    self._upsert(record)
                    self._attempt(record, observation["fingerprint"], previous_snapshot,
                                  candidate_info["candidates"], previous_candidates,
                                  observation["raw_pointers"], previous_pointers)
                    records.append(record)

            # Absence and stale decisions are review evidence, never a deletion.
            for old in prior_rows:
                if old["occurrence_key"] in current_keys:
                    continue
                stale_decision = decisions.get(old["occurrence_key"])
                absences = [{"kind": "source-observation-absent"}]
                if stale_decision is not None:
                    absences.append({"kind": "stale-review-decision",
                                     "decision_status": stale_decision["status"]})
                old_conflicts = json.loads(old["conflicts_json"])
                conflicts = sorted({canonical_json(item): item for item in [*old_conflicts, *absences]}.values(),
                                   key=canonical_json)
                connection.execute("""UPDATE office_occurrence SET source_presence='missing',
                  status='review_required',resolution_method='review-required',conflicts_json=?,
                  review_hash=?,registry_hash=?,decision_hash=?,updated_at=? WHERE occurrence_key=?""",
                  (canonical_json(conflicts), review_hash, registry_hash,
                   _decision_digest(stale_decision) or old["decision_hash"], now, old["occurrence_key"]))
                record = {
                    "occurrence_key": old["occurrence_key"], "identity_key": old["identity_key"],
                    "member_iri": old["member_iri"], "membership_iri": old["membership_iri"],
                    "source_presence": "missing", "status": "review_required",
                    "resolution_method": "review-required", "current_fingerprint": old["current_fingerprint"],
                    "previous_fingerprint": old["previous_fingerprint"],
                    "current_snapshot": json.loads(old["current_snapshot_json"]),
                    "previous_snapshot": json.loads(old["previous_snapshot_json"]) if old["previous_snapshot_json"] else None,
                    "current_candidates": json.loads(old["current_candidates_json"]),
                    "previous_candidates": json.loads(old["previous_candidates_json"]) if old["previous_candidates_json"] else None,
                    "current_raw_pointers": json.loads(old["current_raw_pointers_json"]),
                    "previous_raw_pointers": json.loads(old["previous_raw_pointers_json"]) if old["previous_raw_pointers_json"] else None,
                    "conflicts": conflicts, "review_hash": review_hash, "registry_hash": registry_hash,
                    "decision_hash": _decision_digest(stale_decision) or old["decision_hash"],
                    "last_accepted_resolution": (json.loads(old["last_accepted_resolution_json"])
                                                  if old["last_accepted_resolution_json"] else None),
                    "last_seen_run_id": old["last_seen_run_id"],
                    "updated_at": now, "office_iris": [], "candidate_iris": [],
                    "label": json.loads(old["current_snapshot_json"])["office_label"],
                    "date_range": json.loads(old["current_snapshot_json"])["date_range"],
                    "pattern_hints": [],
                }
                self._attempt(record, None, record["current_snapshot"], record["current_candidates"],
                              record["previous_candidates"], [], record["current_raw_pointers"],
                              attempt_run_id=run_id)
                records.append(record)

            for occurrence_key in unknown_decisions:
                decision = decisions[occurrence_key]
                conflicts = [{"kind": "stale-review-decision-without-ledger-occurrence",
                              "decision_status": decision["status"]}]
                connection.execute("""INSERT INTO office_occurrence_attempt
                  (run_id,occurrence_key,attempted_at,status,resolution_method,fingerprint,
                   previous_fingerprint,source_snapshot_json,previous_snapshot_json,candidates_json,
                   previous_candidates_json,raw_pointers_json,previous_raw_pointers_json,conflicts_json,
                   review_hash,registry_hash)
                  VALUES (?,?,?,'review_required','review-required',NULL,NULL,NULL,NULL,'[]',NULL,'[]',NULL,?,?,?)""",
                  (run_id, occurrence_key, now, canonical_json(conflicts), review_hash, registry_hash))
                records.append({"occurrence_key": occurrence_key, "status": "review_required",
                                "resolution_method": "review-required", "office_iris": [],
                                "candidate_iris": [], "label": None, "date_range": None,
                                "source_presence": "stale_decision", "conflicts": conflicts,
                                "current_candidates": [], "current_raw_pointers": []})
            connection.commit()
        except BaseException:
            connection.rollback()
            raise

        records.sort(key=lambda item: item["occurrence_key"])
        return {"run_id": run_id, "processed": len(current), "records": records,
                "accepted": sum(item["status"] == "accepted" for item in records),
                "rejected": sum(item["status"] == "rejected" for item in records),
                "unresolved": sum(item["status"] == "unresolved" for item in records),
                "review_required": sum(item["status"] == "review_required" for item in records),
                "stale_decisions": stale_decisions}

    def _upsert(self, record: dict) -> None:
        connection = self.connection
        values = (
            record["occurrence_key"], record["identity_key"], record["member_iri"],
            record["membership_iri"], record["source_presence"], record["status"],
            record["resolution_method"], record["current_fingerprint"], record["previous_fingerprint"],
            canonical_json(record["current_snapshot"]),
            canonical_json(record["previous_snapshot"]) if record["previous_snapshot"] is not None else None,
            canonical_json(record["current_candidates"]),
            canonical_json(record["previous_candidates"]) if record["previous_candidates"] is not None else None,
            canonical_json(record["current_raw_pointers"]),
            canonical_json(record["previous_raw_pointers"]) if record["previous_raw_pointers"] is not None else None,
            canonical_json(record["conflicts"]), record["review_hash"], record["registry_hash"],
            record["decision_hash"], record["last_seen_run_id"], record["updated_at"],
            (canonical_json(record["last_accepted_resolution"])
             if record["last_accepted_resolution"] is not None else None),
        )
        connection.execute("""INSERT INTO office_occurrence (
          occurrence_key,identity_key,member_iri,membership_iri,source_presence,status,
          resolution_method,current_fingerprint,previous_fingerprint,current_snapshot_json,
          previous_snapshot_json,current_candidates_json,previous_candidates_json,
          current_raw_pointers_json,previous_raw_pointers_json,conflicts_json,review_hash,
          registry_hash,decision_hash,last_seen_run_id,updated_at,last_accepted_resolution_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(occurrence_key) DO UPDATE SET identity_key=excluded.identity_key,
          member_iri=excluded.member_iri,membership_iri=excluded.membership_iri,
          source_presence='present',status=excluded.status,resolution_method=excluded.resolution_method,
          previous_fingerprint=excluded.previous_fingerprint,current_fingerprint=excluded.current_fingerprint,
          previous_snapshot_json=excluded.previous_snapshot_json,current_snapshot_json=excluded.current_snapshot_json,
          previous_candidates_json=excluded.previous_candidates_json,current_candidates_json=excluded.current_candidates_json,
          previous_raw_pointers_json=excluded.previous_raw_pointers_json,current_raw_pointers_json=excluded.current_raw_pointers_json,
          conflicts_json=excluded.conflicts_json,review_hash=excluded.review_hash,registry_hash=excluded.registry_hash,
          decision_hash=excluded.decision_hash,last_seen_run_id=excluded.last_seen_run_id,updated_at=excluded.updated_at,
          last_accepted_resolution_json=excluded.last_accepted_resolution_json""",
           values)

    def _attempt(self, record: dict, fingerprint: str | None, previous_snapshot: dict | None,
                 candidates: list, previous_candidates: list | None, raw_pointers: list,
                 previous_raw_pointers: list | None, *, attempt_run_id: str | None = None) -> None:
        self.connection.execute("""INSERT INTO office_occurrence_attempt
          (run_id,occurrence_key,attempted_at,status,resolution_method,fingerprint,previous_fingerprint,
           source_snapshot_json,previous_snapshot_json,candidates_json,previous_candidates_json,
           raw_pointers_json,previous_raw_pointers_json,conflicts_json,review_hash,registry_hash,
           last_accepted_resolution_json)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (attempt_run_id or record["last_seen_run_id"], record["occurrence_key"], record["updated_at"],
           record["status"], record["resolution_method"], fingerprint,
           record.get("previous_fingerprint"),
           canonical_json(record["current_snapshot"]) if fingerprint is not None and record.get("current_snapshot") is not None else None,
           canonical_json(previous_snapshot) if previous_snapshot is not None else None,
            canonical_json(candidates),
            canonical_json(previous_candidates) if previous_candidates is not None else None,
           canonical_json(raw_pointers),
           canonical_json(previous_raw_pointers) if previous_raw_pointers is not None else None,
           canonical_json(record["conflicts"]), record["review_hash"], record["registry_hash"],
           (canonical_json(record["last_accepted_resolution"])
            if record.get("last_accepted_resolution") is not None else None)))
