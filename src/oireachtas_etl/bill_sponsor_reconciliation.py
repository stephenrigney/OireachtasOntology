"""Bill-local reconciliation of sponsor Participation observations.

The Bill transformer remains the owner of source Participation RDF.  This
module records local decisions and accepted Member-holding evidence only; it
does not modify Bill core RDF, discover external identities, or publish data.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote, urlsplit
import uuid

from .office_observations import normalize_label
from .transforms.bills import bill_graph_iri
from .transforms.common import date_literal, datetime_literal
from .transforms.offices import office_iri
from .validation.offices import validate_registry_source


SPONSOR_KEY_RE = re.compile(r"^sponsor-[0-9a-f]{64}$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
MEMBER_IRI_RE = re.compile(
    r"^https://data\.oireachtas\.ie/ie/oireachtas/member/id/[^/#]+$"
)
HOLDING_IRI_RE = re.compile(
    r"^https://data\.oireachtas\.ie/ie/oireachtas/member/id/[^/#]+"
    r"#office-holding-[0-9a-f]{64}$"
)
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BillSponsorReviewError(ValueError):
    """Malformed Bill sponsor review file or decision."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _source_iri(value: object, label: str) -> str:
    if (not isinstance(value, str) or value != value.strip()
            or any(char.isspace() for char in value)):
        raise ValueError(f"{label} must be a complete local Oireachtas IRI")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"{label} must be a complete local Oireachtas IRI") from error
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie"
            or parsed.query or parsed.fragment or parsed.username or parsed.password
            or port or not parsed.path):
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    return value


def _member_iri(value: object, label: str = "sponsor.by.uri") -> str:
    result = _source_iri(value, label)
    parts = [part for part in urlsplit(result).path.split("/") if part]
    if (len(parts) != 5 or parts[:4] != ["ie", "oireachtas", "member", "id"]
            or not unquote(parts[4])):
        raise ValueError(f"{label} must identify an Oireachtas Member")
    if not MEMBER_IRI_RE.fullmatch(result):
        raise ValueError(f"{label} must identify an Oireachtas Member")
    return result


def _bill_time_contexts(bill: dict) -> list[dict]:
    """Extract only explicit dates attached to source Bill stages/events.

    ``lastUpdated`` and amendment dates are deliberately not appointment-time
    evidence.  A reviewer can select one of these source contexts for a
    holding decision; this module never chooses a sponsorship date itself.
    """
    contexts: dict[tuple[str, str], dict] = {}
    for collection in ("stages", "events"):
        records = bill.get(collection, [])
        if not isinstance(records, list):
            raise ValueError(f"bill.{collection} must be an array")
        for index, wrapped in enumerate(records):
            if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
                raise ValueError(f"bill.{collection}[{index}] must contain event")
            event = wrapped["event"]
            event_iri = _source_iri(event.get("uri"), f"bill.{collection}[{index}].event.uri")
            dates = event.get("dates")
            if not isinstance(dates, list):
                raise ValueError(f"bill.{collection}[{index}].event.dates must be an array")
            for date_index, item in enumerate(dates):
                if not isinstance(item, dict):
                    raise ValueError(f"bill.{collection}[{index}].event.dates[{date_index}] must be an object")
                value = item.get("date")
                date_literal(value)
                context = {"event_iri": event_iri, "date": value}
                contexts[(event_iri, value)] = context
    return [contexts[key] for key in sorted(contexts)]


def bill_sponsor_graph_iri(bill: dict) -> str:
    """Return the approved complete per-Bill local reconciliation graph IRI."""
    return bill_graph_iri(bill) + "/office-reconciliation"


def _participation_iri(bill_iri: str, sponsor: dict) -> str:
    role = sponsor["as"]
    by = sponsor["by"]
    identity = {
        "member": by.get("uri"),
        "role": role.get("uri") or role.get("showAs"),
        "primary": sponsor["isPrimary"],
    }
    digest = json_hash(identity)
    return f"{bill_iri}#process#sponsor-{digest}"


def extract_bill_sponsor_observations(wrapper: dict) -> list[dict]:
    """Extract source sponsors with stable list-occurrence keys and current IRIs.

    The stable reconciliation key is derived from the unchanged source
    Participation IRI, not from a mutable array position.  The position is
    retained only to diagnose a changed sponsor identity at the same source
    occurrence. Any changed source, Bill event context, registry, or relevant
    accepted holding changes the evidence fingerprint and invalidates review.
    """
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict):
        raise ValueError("each Legislation result must contain a bill object")
    bill = wrapper["bill"]
    bill_iri = _source_iri(bill.get("uri"), "bill.uri")
    bill_graph_iri(bill)
    origin_house_uri = _source_iri(bill.get("originHouseURI"), "bill.originHouseURI")
    origin_house_code = urlsplit(origin_house_uri).path.rstrip("/").rsplit("/", 1)[-1]
    if origin_house_code not in {"dail", "seanad"}:
        raise ValueError("bill.originHouseURI must identify a Dáil or Seanad")
    sponsors = bill.get("sponsors", [])
    if not isinstance(sponsors, list):
        raise ValueError("bill.sponsors must be an array")
    time_contexts = _bill_time_contexts(bill)
    bill_source_hash = json_hash(bill)
    grouped: dict[str, list[tuple[int, dict, dict, dict, str | None, str | None]]] = {}
    for index, wrapped in enumerate(sponsors):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("sponsor"), dict):
            raise ValueError(f"bill.sponsors[{index}] must contain sponsor")
        sponsor = wrapped["sponsor"]
        role, by = sponsor.get("as", {}), sponsor.get("by", {})
        if not isinstance(role, dict) or not isinstance(by, dict):
            raise ValueError(f"bill.sponsors[{index}].sponsor.as/by must be objects")
        primary = sponsor.get("isPrimary")
        if not isinstance(primary, bool):
            raise ValueError(f"bill.sponsors[{index}].sponsor.isPrimary must be boolean")
        person_iri = by.get("uri")
        if person_iri is not None:
            person_iri = _member_iri(person_iri)
        role_text = role.get("showAs")
        if role_text is not None and (not isinstance(role_text, str) or not role_text.strip()):
            raise ValueError(f"bill.sponsors[{index}].sponsor.as.showAs must be non-empty text or null")
        for label, value in (("by.showAs", by.get("showAs")), ("as.uri", role.get("uri"))):
            if value is not None and not isinstance(value, str):
                raise ValueError(f"bill.sponsors[{index}].sponsor.{label} must be text or null")
        participation_iri = _participation_iri(bill_iri, sponsor)
        grouped.setdefault(participation_iri, []).append(
            (index, sponsor, role, by, role_text, person_iri))

    observations = []
    for participation_iri, source_items in sorted(
            grouped.items(), key=lambda item: min(source[0] for source in item[1])):
        source_index, sponsor, role, by, _role_text, _person_iri = min(
            source_items, key=lambda source: source[0])
        role_texts = sorted({item[4] for item in source_items if item[4] is not None})
        person_iris = sorted({item[5] for item in source_items if item[5] is not None})
        source_conflicts = []
        if len(role_texts) > 1:
            source_conflicts.append({"kind": "duplicate-participation-role-text-conflict",
                                     "role_texts": role_texts})
        if len(person_iris) > 1:
            source_conflicts.append({"kind": "duplicate-participation-person-conflict",
                                     "person_iris": person_iris})
        role_text = role_texts[0] if len(role_texts) == 1 else None
        person_iri = person_iris[0] if len(person_iris) == 1 else None
        sponsor_variants = sorted({canonical_json(item[1]) for item in source_items})
        sponsor_values = [json.loads(item) for item in sponsor_variants]
        observation_key = "sponsor-" + json_hash({
            "kind": "bill-sponsor-observation-v1",
            "bill_iri": bill_iri,
            "participation_iri": participation_iri,
        })
        source_material = {
            "bill_iri": bill_iri,
            "bill_source_hash": bill_source_hash,
            "source_sponsors": sponsor_values,
            "participation_iri": participation_iri,
            "bill_time_contexts": time_contexts,
        }
        observations.append({
            "bill_iri": bill_iri,
            "observation_key": observation_key,
            "source_index": index,
            "participation_iri": participation_iri,
            "role_text": role_text,
            "role_uri": role.get("uri"),
            "person_iri": person_iri,
            "is_primary": sponsor["isPrimary"],
            "source_conflicts": source_conflicts,
            "source_occurrence_count": len(source_items),
            "origin_house_uri": origin_house_uri,
            "origin_house_code": origin_house_code,
            "bill_time_contexts": time_contexts,
            "source_fingerprint": json_hash(source_material),
            "source_snapshot": json.loads(canonical_json(source_material)),
        })
    return observations


def _registered_offices(registry: dict) -> dict[str, dict]:
    validate_registry_source(registry)
    return {str(office_iri(item["key"])): item for item in registry["offices"]}


def _date_range(value: object, label: str) -> dict:
    if not isinstance(value, dict) or set(value) - {"start", "end"} or "start" not in value:
        raise ValueError(f"{label} must contain a required start and optional end")
    start, end = value.get("start"), value.get("end")
    start_literal = datetime_literal(start)
    if end is not None and datetime_literal(end).toPython() < start_literal.toPython():
        raise ValueError(f"{label} has reverse dates")
    return {"start": start, "end": end}


def _holding_iri(value: object, label: str = "holding_iri") -> str:
    if not isinstance(value, str) or not HOLDING_IRI_RE.fullmatch(value):
        raise ValueError(f"{label} must be a complete Member OfficeHolding IRI")
    parent = value.split("#", 1)[0]
    _member_iri(parent, label)
    return value


def _holding_identity(occurrence_key: str, office_text: str) -> str:
    return hashlib.sha256(canonical_json({
        "kind": "office-holding-occurrence-v1",
        "occurrence_key": occurrence_key,
        "office_iri": office_text,
    }).encode("utf-8")).hexdigest()


def _holding_may_cover_bill_date(date_range: dict, bill_date: str) -> bool:
    """Conservatively detect timestamp tenure that could overlap a Bill date."""
    day_start = datetime.combine(date.fromisoformat(bill_date), datetime.min.time())
    day_end = day_start + timedelta(days=1)
    start = datetime_literal(date_range["start"]).toPython()
    end = datetime_literal(date_range["end"]).toPython() if date_range.get("end") is not None else None
    return start < day_end and (end is None or end >= day_start)


def normalize_accepted_member_holdings(records: list[dict], registry: dict) -> list[dict]:
    """Validate the current accepted Member holdings supplied to Bill review.

    Records have ``status='accepted'``, ``member_iri``, ``holding_iri``,
    ``office_iri`` and the source ``date_range``.  If occurrence correspondence
    is included, the holding IRI is checked against the established Member
    transform identity rule rather than minted here.
    """
    if not isinstance(records, list):
        raise ValueError("accepted_member_holdings must be a list")
    offices = _registered_offices(registry)
    normalized: dict[str, dict] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"accepted Member holding {index} must be an object")
        if record.get("status") != "accepted":
            raise ValueError(f"accepted Member holding {index} must have status='accepted'")
        member = _member_iri(record.get("member_iri"), f"accepted Member holding {index}.member_iri")
        holding = _holding_iri(record.get("holding_iri"), f"accepted Member holding {index}.holding_iri")
        office = _source_iri(record.get("office_iri"), f"accepted Member holding {index}.office_iri")
        if office not in offices:
            raise ValueError(f"accepted Member holding {index} targets an unregistered NamedOffice")
        if holding.split("#", 1)[0] != member:
            raise ValueError(f"accepted Member holding {index} IRI does not belong to member_iri")
        dates = _date_range(record.get("date_range"), f"accepted Member holding {index}.date_range")
        occurrence_key = record.get("occurrence_key")
        if occurrence_key is not None:
            if not isinstance(occurrence_key, str) or not re.fullmatch(r"occ-[0-9a-f]{64}", occurrence_key):
                raise ValueError(f"accepted Member holding {index}.occurrence_key is invalid")
            expected = f"{member}#office-holding-{_holding_identity(occurrence_key, office)}"
            if holding != expected:
                raise ValueError(f"accepted Member holding {index} IRI disagrees with occurrence correspondence")
        item = {
            "status": "accepted",
            "member_iri": member,
            "holding_iri": holding,
            "office_iri": office,
            "date_range": dates,
        }
        if occurrence_key is not None:
            item["occurrence_key"] = occurrence_key
        previous = normalized.get(holding)
        if previous is not None and previous != item:
            raise ValueError(f"conflicting accepted Member holding records for {holding}")
        normalized[holding] = item
    return sorted(normalized.values(), key=lambda item: item["holding_iri"])


def _validate_time_context(observation: dict, value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"event_iri", "date"}:
        raise ValueError("time_context must contain exactly event_iri and date")
    event_iri = _source_iri(value.get("event_iri"), "time_context.event_iri")
    date_value = value.get("date")
    date_literal(date_value)
    normalized = {"event_iri": event_iri, "date": date_value}
    if normalized not in observation.get("bill_time_contexts", []):
        raise ValueError("time_context must be an explicit date on a current Bill stage/event")
    return normalized


def _relevant_holdings(observation: dict, holdings: list[dict]) -> list[dict]:
    member = observation.get("person_iri")
    if member is None:
        return []
    return [item for item in holdings if item["member_iri"] == member]


def sponsor_input_fingerprint(
    observation: dict,
    registry: dict,
    accepted_member_holdings: list[dict],
    time_context: dict | None = None,
) -> str:
    """Fingerprint all source and authority evidence relevant to one decision."""
    registry = validate_registry_source(registry)
    offices = _registered_offices(registry)
    if time_context is not None:
        time_context = _validate_time_context(observation, time_context)
    holdings = normalize_accepted_member_holdings(accepted_member_holdings, registry)
    relevant = _relevant_holdings(observation, holdings)
    return json_hash({
        "kind": "bill-sponsor-evidence-v1",
        "source_fingerprint": observation["source_fingerprint"],
        "participation_iri": observation["participation_iri"],
        "time_context": time_context,
        "office_registry_hash": json_hash(registry),
        "registered_office_iris": sorted(offices),
        "member_holdings_hash": json_hash(relevant),
    })


def generate_bill_sponsor_candidates(
    observation: dict,
    registry: dict,
    accepted_member_holdings: list[dict],
    time_context: dict | None = None,
) -> dict:
    """Return exact reviewed-office and person+Bill-date holding candidates.

    Role text matches reviewed registry labels/aliases by conservative exact
    normalization.  Context-scoped aliases are used only when their scope can
    be established from this Bill.  A holding candidate requires an explicit
    person IRI, a selected source event date, and date-only Member tenure
    bounds; timestamp/date ambiguity is reported rather than guessed.
    """
    registry = validate_registry_source(registry)
    offices = _registered_offices(registry)
    holdings = normalize_accepted_member_holdings(accepted_member_holdings, registry)
    if time_context is not None:
        time_context = _validate_time_context(observation, time_context)

    text = observation.get("role_text")
    normalized_text = normalize_label(text) if isinstance(text, str) else ""
    office_candidates: dict[str, dict] = {}
    if normalized_text:
        for office_text, office in offices.items():
            matched_labels: set[str] = set()
            candidate_labels = [office["label_en"]]
            if office.get("label_ga"):
                candidate_labels.append(office["label_ga"])
            for alias in office["aliases"]:
                alias_text = alias["label"]
                if normalize_label(alias_text) != normalized_text:
                    continue
                contexts = set(alias.get("contexts", []))
                if contexts:
                    if not ({observation.get("origin_house_code"),
                             observation.get("origin_house_uri")} & contexts):
                        continue
                validity = alias.get("validity")
                if validity is not None:
                    if time_context is None:
                        continue
                    if (not _DATE_ONLY_RE.fullmatch(validity["start"])
                            or (validity.get("end") is not None
                                and not _DATE_ONLY_RE.fullmatch(validity["end"]))):
                        continue
                    current_date = date.fromisoformat(time_context["date"])
                    alias_start = date.fromisoformat(validity["start"])
                    alias_end = date.fromisoformat(validity["end"]) if validity.get("end") else None
                    if current_date < alias_start or (alias_end is not None and current_date > alias_end):
                        continue
                if alias.get("unit_keys"):
                    continue
                matched_labels.add(alias_text)
            for label in candidate_labels:
                if normalize_label(label) == normalized_text:
                    matched_labels.add(label)
            if matched_labels:
                office_candidates[office_text] = {
                    "office_iri": office_text,
                    "office_type": office["office_type"],
                    "matched_labels": sorted(matched_labels),
                }

    holding_candidates: list[dict] = []
    conflicts: list[dict] = list(observation.get("source_conflicts", []))
    if time_context is not None and observation.get("person_iri") is not None:
        event_date = date.fromisoformat(time_context["date"])
        for item in holdings:
            if item["member_iri"] != observation["person_iri"]:
                continue
            dates = item["date_range"]
            if (not _DATE_ONLY_RE.fullmatch(dates["start"])
                    or (dates.get("end") is not None
                        and not _DATE_ONLY_RE.fullmatch(dates["end"]))):
                if _holding_may_cover_bill_date(dates, time_context["date"]):
                    conflicts.append({
                        "kind": "holding-time-precision-ambiguous",
                        "holding_iri": item["holding_iri"],
                        "bill_event_date": time_context["date"],
                    })
                continue
            start = date.fromisoformat(dates["start"])
            end = date.fromisoformat(dates["end"]) if dates.get("end") is not None else None
            if event_date < start or (end is not None and event_date > end):
                continue
            holding_candidates.append({
                "holding_iri": item["holding_iri"],
                "member_iri": item["member_iri"],
                "office_iri": item["office_iri"],
                "date_range": dates,
            })
        if len(holding_candidates) > 1:
            conflicts.append({
                "kind": "ambiguous-person-time-holdings",
                "holding_iris": sorted(item["holding_iri"] for item in holding_candidates),
            })
        if len(office_candidates) == 1 and holding_candidates:
            role_office = next(iter(office_candidates))
            if any(candidate["office_iri"] != role_office for candidate in holding_candidates):
                conflicts.append({
                    "kind": "role-office-holding-conflict",
                    "role_office_iri": role_office,
                    "holding_office_iris": sorted({item["office_iri"] for item in holding_candidates}),
                })

    return {
        "office_candidates": [office_candidates[key] for key in sorted(office_candidates)],
        "holding_candidates": sorted(holding_candidates, key=lambda item: item["holding_iri"]),
        "conflicts": sorted(conflicts, key=canonical_json),
    }


def _json_object_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BillSponsorReviewError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _validate_decision_shape(key: object, decision: object,
                             offices: dict[str, dict] | None) -> dict:
    if not isinstance(key, str) or not SPONSOR_KEY_RE.fullmatch(key):
        raise BillSponsorReviewError(f"invalid Bill sponsor observation key: {key!r}")
    required = {"status", "input_fingerprint", "evidence", "reason"}
    optional = {"office_iri", "holding_iri", "time_context"}
    if (not isinstance(decision, dict) or not required <= set(decision)
            or set(decision) - required - optional):
        raise BillSponsorReviewError(f"invalid decision fields for {key}")
    status = decision["status"]
    if not isinstance(status, str) or status not in {"accepted", "rejected", "unresolved"}:
        raise BillSponsorReviewError(f"invalid decision status for {key}")
    fingerprint = decision["input_fingerprint"]
    if not isinstance(fingerprint, str) or not FINGERPRINT_RE.fullmatch(fingerprint):
        raise BillSponsorReviewError(f"invalid input_fingerprint for {key}")
    evidence, reason = decision["evidence"], decision["reason"]
    if (not isinstance(evidence, list) or not evidence
            or any(not isinstance(item, str) or not item.strip() for item in evidence)
            or len(evidence) != len(set(evidence))
            or not isinstance(reason, str) or not reason.strip()):
        raise BillSponsorReviewError(f"decision for {key} needs evidence references and a reason")
    office = decision.get("office_iri")
    holding = decision.get("holding_iri")
    context = decision.get("time_context")
    if status == "accepted":
        if office is None and holding is None:
            raise BillSponsorReviewError(f"accepted decision for {key} needs an office or holding target")
        if office is not None:
            if (not isinstance(office, str)
                    or not re.fullmatch(r"https://data\.oireachtas\.ie/office/[A-Za-z0-9][A-Za-z0-9-]*", office)):
                raise BillSponsorReviewError(f"accepted decision for {key} has an invalid local NamedOffice IRI")
            if offices is not None and office not in offices:
                raise BillSponsorReviewError(f"accepted decision for {key} targets an unregistered NamedOffice")
        if holding is not None:
            try:
                _holding_iri(holding, f"decision {key}.holding_iri")
            except ValueError as error:
                raise BillSponsorReviewError(str(error)) from error
            if not isinstance(context, dict) or set(context) != {"event_iri", "date"}:
                raise BillSponsorReviewError(f"holding decision for {key} needs a source Bill time_context")
        elif context is not None:
            raise BillSponsorReviewError(f"office-only decision for {key} cannot carry a time_context")
    elif office is not None or holding is not None or context is not None:
        raise BillSponsorReviewError(f"{status} decision for {key} cannot carry targets or time_context")
    if context is not None:
        event = context.get("event_iri") if isinstance(context, dict) else None
        try:
            _source_iri(event, f"decision {key}.time_context.event_iri")
            date_literal(context.get("date"))
        except (TypeError, ValueError) as error:
            raise BillSponsorReviewError(f"invalid time_context for {key}: {error}") from error
    return decision


def validate_bill_sponsor_decisions(decisions: object, registry: dict) -> dict[str, dict]:
    if not isinstance(decisions, dict):
        raise BillSponsorReviewError("Bill sponsor decisions must be an object")
    offices = _registered_offices(registry)
    for key, decision in decisions.items():
        _validate_decision_shape(key, decision, offices)
    return decisions


def load_bill_sponsor_review(path: Path) -> tuple[dict[str, dict], str]:
    """Load strict version-1 Bill-local review decisions and return raw hash."""
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw, object_pairs_hook=_json_object_no_duplicates)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BillSponsorReviewError(f"invalid Bill sponsor review file: {error}") from error
    if (not isinstance(value, dict) or set(value) != {"version", "decisions"}
            or type(value.get("version")) is not int or value["version"] != 1
            or not isinstance(value["decisions"], dict)):
        raise BillSponsorReviewError("Bill sponsor review file must contain only version 1 and a decisions object")
    decisions = value["decisions"]
    for key, decision in decisions.items():
        _validate_decision_shape(key, decision, None)
    return decisions, hashlib.sha256(raw).hexdigest()


def _decision_digest(decision: dict | None) -> str | None:
    return json_hash(decision) if decision is not None else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BillSponsorStore:
    """Durable per-Bill sponsor-observation state and review invalidation."""

    def __init__(self, path: Path | str):
        self._in_memory = str(path) == ":memory:"
        self.path = Path(path).expanduser() if not self._in_memory else Path(":memory:")
        if not self._in_memory:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists() and self.path.stat().st_size:
                with self.path.open("rb") as handle:
                    if handle.read(16) != b"SQLite format 3\x00":
                        raise ValueError(f"Bill sponsor state path is not SQLite: {self.path}")
        self.connection = sqlite3.connect(":memory:" if self._in_memory else self.path,
                                          timeout=30, isolation_level=None)
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
        if version not in (0, 1):
            raise ValueError(f"unsupported Bill sponsor state schema version: {version}")
        if version == 1:
            tables = {row[0] for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"bill_sponsor_observation", "bill_sponsor_attempt"} <= tables:
                raise ValueError("Bill sponsor SQLite state schema is incomplete")
            return
        self.connection.executescript("""
          BEGIN IMMEDIATE;
          CREATE TABLE bill_sponsor_observation (
            bill_iri TEXT NOT NULL,
            observation_key TEXT NOT NULL,
            source_presence TEXT NOT NULL CHECK(source_presence IN ('present','missing')),
            status TEXT NOT NULL CHECK(status IN ('accepted','rejected','unresolved','review_required')),
            current_record_json TEXT NOT NULL,
            previous_record_json TEXT,
            last_accepted_resolution_json TEXT,
            last_seen_run_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(bill_iri, observation_key)
          );
          CREATE TABLE bill_sponsor_attempt (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            bill_iri TEXT NOT NULL,
            observation_key TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('accepted','rejected','unresolved','review_required')),
            input_fingerprint TEXT,
            record_json TEXT NOT NULL
          );
          CREATE INDEX bill_sponsor_attempt_run
            ON bill_sponsor_attempt(run_id, bill_iri, observation_key);
          PRAGMA user_version=1;
          COMMIT;
        """)

    def observations(self, bill_iri: str | None = None) -> list[dict]:
        if bill_iri is None:
            rows = self.connection.execute(
                "SELECT * FROM bill_sponsor_observation ORDER BY bill_iri, observation_key").fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM bill_sponsor_observation WHERE bill_iri=? ORDER BY observation_key",
                (bill_iri,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["record"] = json.loads(item.pop("current_record_json"))
            previous = item.pop("previous_record_json")
            accepted = item.pop("last_accepted_resolution_json")
            item["previous_record"] = json.loads(previous) if previous else None
            item["last_accepted_resolution"] = json.loads(accepted) if accepted else None
            result.append(item)
        return result

    def attempts(self, bill_iri: str | None = None,
                 observation_key: str | None = None) -> list[dict]:
        where, params = [], []
        if bill_iri is not None:
            where.append("bill_iri=?"); params.append(bill_iri)
        if observation_key is not None:
            where.append("observation_key=?"); params.append(observation_key)
        query = "SELECT * FROM bill_sponsor_attempt"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY attempt_id"
        output = []
        for row in self.connection.execute(query, params):
            item = dict(row)
            item["record"] = json.loads(item.pop("record_json"))
            output.append(item)
        return output

    def reconcile(
        self,
        wrapper: dict,
        registry: dict,
        accepted_member_holdings: list[dict],
        decisions: dict[str, dict],
        review_hash: str,
        *,
        run_id: str | None = None,
    ) -> dict:
        """Reconcile all current sponsors for one Bill in one SQLite transaction."""
        registry = validate_registry_source(registry)
        decisions = validate_bill_sponsor_decisions(decisions, registry)
        holdings = normalize_accepted_member_holdings(accepted_member_holdings, registry)
        if not isinstance(review_hash, str) or not FINGERPRINT_RE.fullmatch(review_hash):
            raise ValueError("Bill sponsor review hash must be a SHA-256 digest")
        run_id = run_id or str(uuid.uuid4())
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("Bill sponsor reconciliation run_id must be non-empty")
        observations = extract_bill_sponsor_observations(wrapper)
        if observations:
            bill_iri = observations[0]["bill_iri"]
        else:
            bill = wrapper.get("bill") if isinstance(wrapper, dict) else None
            if not isinstance(bill, dict):
                raise ValueError("each Legislation result must contain a bill object")
            bill_iri = _source_iri(bill.get("uri"), "bill.uri")
            bill_graph_iri(bill)

        observation_keys = {item["observation_key"] for item in observations}
        stale_decisions = sorted(set(decisions) - observation_keys)
        now = _now()
        connection = self.connection
        records: list[dict] = []
        connection.execute("BEGIN IMMEDIATE")
        try:
            prior_rows = [dict(row) for row in connection.execute(
                "SELECT * FROM bill_sponsor_observation WHERE bill_iri=?", (bill_iri,))]
            prior_by_key = {row["observation_key"]: row for row in prior_rows}
            for observation in observations:
                key = observation["observation_key"]
                old_row = prior_by_key.get(key)
                old = json.loads(old_row["current_record_json"]) if old_row else None
                decision = decisions.get(key)
                selected_context = decision.get("time_context") if decision else None
                stale_time_context = False
                if selected_context is not None:
                    try:
                        selected_context = _validate_time_context(observation, selected_context)
                    except ValueError:
                        # A previously reviewed event may have disappeared or
                        # changed. Preserve the decision as stale evidence and
                        # quarantine it; do not fail the entire Bill scan.
                        stale_time_context = True
                        selected_context = None
                fingerprint = sponsor_input_fingerprint(
                    observation, registry, holdings, selected_context)
                candidates = generate_bill_sponsor_candidates(
                    observation, registry, holdings, selected_context)
                decision_hash = _decision_digest(decision)
                conflicts = list(candidates["conflicts"])
                prior_same_position = [
                    json.loads(row["current_record_json"])
                    for row in prior_rows
                    if row["observation_key"] != key
                    and json.loads(row["current_record_json"]).get("source_presence") == "present"
                    and json.loads(row["current_record_json"]).get("source_index") == observation["source_index"]
                ]
                identity_replaced = old is None and bool(prior_same_position)
                if identity_replaced:
                    conflicts.append({
                        "kind": "source-sponsor-identity-changed-at-prior-position",
                        "previous_participation_iris": sorted({item["participation_iri"]
                                                                 for item in prior_same_position}),
                    })
                if old and old.get("source_presence") == "missing":
                    conflicts.append({"kind": "source-sponsor-reappeared-after-absence"})
                changed = bool(old and old.get("input_fingerprint") != fingerprint)
                if changed:
                    conflicts.append({
                        "kind": "sponsor-evidence-changed",
                        "previous_input_fingerprint": old["input_fingerprint"],
                        "current_input_fingerprint": fingerprint,
                    })
                prior_decision_hash = old.get("decision_hash") if old else None
                decision_removed = bool(old and prior_decision_hash is not None and decision is None)
                if decision_removed:
                    conflicts.append({"kind": "review-decision-removed"})

                status = "unresolved"
                method = "unresolved"
                office_target = holding_target = None
                evidence: list[dict] = []
                if stale_time_context:
                    status, method = "review_required", "stale-review-time-context"
                    conflicts.append({
                        "kind": "review-time-context-no-longer-in-current-bill",
                        "reviewed_time_context": decision.get("time_context") if decision else None,
                    })
                elif decision is not None and decision["input_fingerprint"] != fingerprint:
                    status, method = "review_required", "stale-review-decision"
                    conflicts.append({
                        "kind": "review-input-fingerprint-stale",
                        "reviewed_input_fingerprint": decision["input_fingerprint"],
                        "current_input_fingerprint": fingerprint,
                    })
                elif decision is not None:
                    status, method = decision["status"], "review-file"
                    evidence = [{"kind": "review-decision",
                                 "decision": json.loads(canonical_json(decision))}]
                    if status == "accepted":
                        office_target = decision.get("office_iri")
                        holding_target = decision.get("holding_iri")
                        if holding_target is not None:
                            selected_holding = next((item for item in candidates["holding_candidates"]
                                                     if item["holding_iri"] == holding_target), None)
                            if (observation.get("person_iri") is None
                                    or len(candidates["holding_candidates"]) != 1
                                    or any(conflict["kind"] == "holding-time-precision-ambiguous"
                                           for conflict in candidates["conflicts"])
                                    or selected_holding is None):
                                status, method = "review_required", "holding-decision-not-qualified"
                                conflicts.append({
                                    "kind": ("reviewed-holding-not-unique"
                                             if len(candidates["holding_candidates"]) > 1
                                             else "reviewed-holding-not-currently-person-time-qualified"),
                                    "holding_iri": holding_target,
                                    "candidate_holding_iris": sorted(
                                        item["holding_iri"] for item in candidates["holding_candidates"]),
                                })
                                office_target = holding_target = None
                            elif (office_target is not None
                                  and selected_holding["office_iri"] != office_target):
                                status, method = "review_required", "reviewed-office-holding-conflict"
                                conflicts.append({
                                    "kind": "reviewed-office-and-holding-targets-disagree",
                                    "office_iri": office_target,
                                    "holding_office_iri": selected_holding["office_iri"],
                                })
                                office_target = holding_target = None
                elif (changed or decision_removed or identity_replaced
                      or (old and old.get("source_presence") == "missing")):
                    status, method = "review_required", "evidence-invalidated"
                elif old and old.get("status") == "review_required":
                    status, method = "review_required", "review-gate-pending"
                elif candidates["conflicts"] or len(candidates["office_candidates"]) > 1:
                    status, method = "review_required", "candidate-review-required"
                    if len(candidates["office_candidates"]) > 1:
                        conflicts.append({"kind": "ambiguous-reviewed-office-alias"})
                elif len(candidates["office_candidates"]) == 1:
                    status, method = "accepted", "unique-reviewed-office-label"
                    office_target = candidates["office_candidates"][0]["office_iri"]
                    evidence = [{"kind": "unique-reviewed-office-label",
                                 "candidate": candidates["office_candidates"][0]}]
                else:
                    status, method = "unresolved", "no-reviewed-office-match"
                    evidence = [{"kind": "no-reviewed-office-match"}]

                # A changed evidence basis always blocks an implicit/unchanged
                # resolution. A newly fingerprint-bound human decision above
                # is the sole path that can explicitly re-accept it.
                if (changed and decision is not None
                        and decision["input_fingerprint"] == fingerprint):
                    # The current decision is an explicit re-review, so retain
                    # its requested status and target after fingerprint checks.
                    pass
                elif changed and decision is None:
                    status, method = "review_required", "evidence-invalidated"
                    office_target = holding_target = None

                if status != "accepted":
                    office_target = holding_target = None
                if status == "accepted" and office_target is None and holding_target is None:
                    raise ValueError(f"accepted Bill sponsor decision {key} has no target")

                record = {
                    "bill_iri": bill_iri,
                    "observation_key": key,
                    "source_index": observation["source_index"],
                    "source_presence": "present",
                    "participation_iri": observation["participation_iri"],
                    "role_text": observation["role_text"],
                    "role_uri": observation["role_uri"],
                    "person_iri": observation["person_iri"],
                    "source_fingerprint": observation["source_fingerprint"],
                    "input_fingerprint": fingerprint,
                    "office_registry_hash": json_hash(registry),
                    "member_holdings_hash": json_hash(_relevant_holdings(observation, holdings)),
                    "review_hash": review_hash,
                    # Keep the last reviewed decision digest when its file entry
                    # disappears; otherwise a later retry could auto-accept a
                    # different alias without a new review.
                    "decision_hash": decision_hash if decision_hash is not None else prior_decision_hash,
                    "status": status,
                    "resolution_method": method,
                    "office_candidates": candidates["office_candidates"],
                    "holding_candidates": candidates["holding_candidates"],
                    "office_iri": office_target,
                    "holding_iri": holding_target,
                    "time_context": selected_context,
                    "evidence": evidence,
                    "conflicts": sorted({canonical_json(item): item for item in conflicts}.values(),
                                         key=canonical_json),
                    "source_snapshot": observation["source_snapshot"],
                }
                if status == "accepted":
                    record["accepted_resolution"] = {
                        "input_fingerprint": fingerprint,
                        "participation_iri": observation["participation_iri"],
                        "office_iri": office_target,
                        "holding_iri": holding_target,
                        "time_context": selected_context,
                        "evidence": evidence,
                        "review_hash": review_hash,
                    }
                elif old and old.get("accepted_resolution"):
                    record["accepted_resolution"] = old["accepted_resolution"]
                self._upsert(bill_iri, key, record, old, run_id, now)
                self._attempt(run_id, record, now)
                records.append(record)

            # Removed source sponsors are retained as review evidence in state,
            # but never reintroduced into the complete current Bill graph.
            for old_row in prior_rows:
                key = old_row["observation_key"]
                if key in observation_keys:
                    continue
                old = json.loads(old_row["current_record_json"])
                conflicts = list(old.get("conflicts", []))
                conflicts.append({"kind": "source-sponsor-absent"})
                if key in decisions:
                    conflicts.append({"kind": "stale-review-decision-for-absent-sponsor"})
                missing = {
                    **old,
                    "source_presence": "missing",
                    "status": "review_required",
                    "resolution_method": "review-required",
                    "review_hash": review_hash,
                    "decision_hash": (_decision_digest(decisions[key])
                                      if key in decisions else old.get("decision_hash")),
                    "office_iri": None,
                    "holding_iri": None,
                    "conflicts": sorted({canonical_json(item): item for item in conflicts}.values(),
                                        key=canonical_json),
                }
                self._upsert(bill_iri, key, missing, old, run_id, now)
                self._attempt(run_id, missing, now)
                records.append(missing)

            # A decision whose stable Participation key has never existed in
            # this Bill is durable stale-review evidence, not a reason to guess
            # which current sponsor it was intended to describe.
            for key in stale_decisions:
                if key in prior_by_key:
                    continue
                decision = decisions[key]
                stale = {
                    "bill_iri": bill_iri,
                    "observation_key": key,
                    "source_presence": "stale_decision",
                    "status": "review_required",
                    "resolution_method": "stale-review-decision",
                    "participation_iri": None,
                    "input_fingerprint": None,
                    "review_hash": review_hash,
                    "decision_hash": _decision_digest(decision),
                    "office_iri": None,
                    "holding_iri": None,
                    "time_context": decision.get("time_context"),
                    "evidence": [],
                    "conflicts": [{"kind": "stale-review-decision-without-current-sponsor"}],
                }
                self._attempt(run_id, stale, now)
                records.append(stale)

            connection.commit()
        except BaseException:
            connection.rollback()
            raise

        records.sort(key=lambda item: item["observation_key"])
        return {
            "bill_iri": bill_iri,
            "run_id": run_id,
            "records": records,
            "stale_decisions": stale_decisions,
            "counts": {status: sum(item["status"] == status and item["source_presence"] == "present"
                                    for item in records)
                       for status in ("accepted", "rejected", "unresolved", "review_required")},
        }

    def _upsert(self, bill_iri: str, key: str, record: dict, old: dict | None,
                run_id: str, now: str) -> None:
        prior_row = self.connection.execute(
            "SELECT current_record_json, last_accepted_resolution_json FROM bill_sponsor_observation "
            "WHERE bill_iri=? AND observation_key=?", (bill_iri, key)).fetchone()
        previous_json = prior_row["current_record_json"] if prior_row else None
        accepted = record.get("accepted_resolution")
        if accepted is None and prior_row and prior_row["last_accepted_resolution_json"]:
            accepted_json = prior_row["last_accepted_resolution_json"]
        elif accepted is not None:
            accepted_json = canonical_json(accepted)
        else:
            accepted_json = None
        self.connection.execute("""INSERT INTO bill_sponsor_observation
          (bill_iri,observation_key,source_presence,status,current_record_json,
           previous_record_json,last_accepted_resolution_json,last_seen_run_id,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?)
          ON CONFLICT(bill_iri,observation_key) DO UPDATE SET
           source_presence=excluded.source_presence,status=excluded.status,
           current_record_json=excluded.current_record_json,
           previous_record_json=excluded.previous_record_json,
           last_accepted_resolution_json=excluded.last_accepted_resolution_json,
           last_seen_run_id=excluded.last_seen_run_id,updated_at=excluded.updated_at""",
          (bill_iri, key, record["source_presence"], record["status"], canonical_json(record),
           previous_json, accepted_json, run_id, now))

    def _attempt(self, run_id: str, record: dict, now: str) -> None:
        self.connection.execute("""INSERT INTO bill_sponsor_attempt
          (run_id,bill_iri,observation_key,attempted_at,status,input_fingerprint,record_json)
          VALUES (?,?,?,?,?,?,?)""",
          (run_id, record["bill_iri"], record["observation_key"], now,
           record["status"], record.get("input_fingerprint"), canonical_json(record)))
