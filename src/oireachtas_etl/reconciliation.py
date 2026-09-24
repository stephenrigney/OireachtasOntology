"""Phase 3.5 Member external-identity reconciliation.

This module deliberately has no dependency on the authoritative Members ETL
manifest.  Its SQLite database is operational evidence, not RDF provenance.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

from rdflib import Graph, URIRef
from rdflib.namespace import FOAF, OWL

from .serialization import ntriples
from .transforms.common import MEMBERS, iri as source_iri
from .transforms.members import member_graph_iri
from .validation.reference import house_term_iri, validate_party_iri

WIKIDATA = "https://www.wikidata.org/entity/"
WIKIPEDIA = "https://en.wikipedia.org/wiki/"
DBPEDIA = "https://dbpedia.org/resource/"
STATES = frozenset(("accepted", "rejected", "ambiguous", "pending"))


class ReconciliationError(RuntimeError): pass
class ReviewError(ReconciliationError): pass
class FixtureResponseError(ReconciliationError): pass


def _now() -> str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _json(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"))
def _hash(value: object) -> str: return hashlib.sha256(_json(value).encode()).hexdigest()


def valid_qid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"Q[1-9][0-9]*", value) is not None


def _wikidata_qid_from_sparql_binding(binding: object) -> str | None:
    """Extract a QID from a canonical Wikidata entity-IRI SPARQL binding.

    WDQS commonly serializes entity IRIs with the HTTP scheme, while published
    reconciliation links deliberately use the HTTPS ``WIKIDATA`` namespace.
    Keep this relaxed scheme handling local to parsing SPARQL bindings.
    """
    if not isinstance(binding, dict) or binding.get("type") != "uri":
        return None
    value = binding.get("value")
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)", value)
    return match.group(1) if match is not None else None


def _valid_iri(value: object, prefix: str) -> bool:
    if not isinstance(value, str) or value != value.strip() or any(char.isspace() for char in value): return False
    parsed = urlsplit(value)
    expected = urlsplit(prefix)
    if parsed.scheme != "https" or parsed.netloc != expected.netloc or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        return False
    if not parsed.path.startswith(expected.path): return False
    suffix = parsed.path[len(expected.path):]
    if not suffix or "/" in suffix or suffix in {".", ".."}: return False
    if prefix == WIKIDATA: return valid_qid(suffix)
    return True


def wikidata_iri(qid: str) -> str:
    if not valid_qid(qid): raise ValueError("invalid Wikidata QID")
    return WIKIDATA + qid


def _wikidata_year_or_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\+?(\d{4})(?:-(\d{2})-(\d{2})(?:T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?)?", value)
    if not match:
        return None
    year, month, day = match.groups()
    if month is None:
        return year
    try:
        datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
    except ValueError:
        return None
    return f"{year}-{month}-{day}"


def normalize_party_candidate(value: object) -> dict:
    """Validate the compact, deterministic candidate-evidence contract."""
    keys = {"qid", "labels", "matched_on", "types", "instance_types", "jurisdictions", "inception", "dissolution"}
    if not isinstance(value, dict) or set(value) != keys or not valid_qid(value.get("qid")):
        raise ReconciliationError("malformed Wikidata Party candidate")
    result = {"qid": value["qid"]}
    for field in ("labels", "matched_on", "types", "instance_types", "jurisdictions", "inception", "dissolution"):
        values = value[field]
        if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
            raise ReconciliationError("malformed Wikidata Party candidate " + field)
        result[field] = sorted(set(values))
    if not result["labels"] or not result["matched_on"] or "Q7278" not in result["types"] or not result["instance_types"] or "Q27" not in result["jurisdictions"]:
        raise ReconciliationError("Wikidata Party candidate lacks Irish political-party evidence")
    for field in ("types", "instance_types", "jurisdictions"):
        if any(not valid_qid(item) for item in result[field]):
            raise ReconciliationError("malformed Wikidata Party candidate " + field)
    for field in ("inception", "dissolution"):
        if any(_wikidata_year_or_date(item) != item for item in result[field]):
            raise ReconciliationError("malformed Wikidata Party candidate historical date")
    return result


def external_graph_iri(member: dict) -> str:
    # Reuse the approved Member identity validation and percent-encoding.
    return member_graph_iri(member) + "/external-links"


def _party_components(local_iri: object) -> tuple[str, str, str]:
    """Validate and decompose a complete term-scoped Parties API IRI."""
    if not isinstance(local_iri, str) or local_iri != local_iri.strip() or any(c.isspace() for c in local_iri):
        raise ValueError("Party identity must be a complete source IRI")
    parsed = urlsplit(local_iri)
    path = parsed.path.split("/")
    if (parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie" or parsed.username
            or parsed.password or parsed.port or parsed.query or parsed.fragment or len(path) != 7
            or path[:4] != ["", "ie", "oireachtas", "party"]):
        raise ValueError("Party identity must be a complete term-scoped Oireachtas source IRI")
    house_code, house_no, encoded_code = path[4], path[5], path[6]
    if house_code not in {"dail", "seanad"} or re.fullmatch(r"[1-9][0-9]*", house_no) is None or not encoded_code:
        raise ValueError("Party identity has an invalid House term path")
    if re.search(r"%(?![0-9A-Fa-f]{2})", encoded_code):
        raise ValueError("Party identity has invalid percent encoding")
    try:
        party_code = unquote(encoded_code, errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("Party identity has invalid percent-encoded code") from error
    if not party_code or party_code in {".", ".."} or "/" in party_code or "\\" in party_code:
        raise ValueError("Party identity has an invalid party-code path segment")
    return house_code, house_no, party_code


def _party_entity(wrapper: object) -> tuple[dict, dict, str]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("party"), dict) or not isinstance(wrapper.get("house"), dict):
        raise ValueError("each Parties record must contain party and house objects")
    party, house = wrapper["party"], wrapper["house"]
    local = source_iri(party.get("uri"))
    term = house_term_iri(house)
    code, label = party.get("partyCode"), party.get("showAs")
    if not isinstance(code, str) or not code or code != code.strip() or not isinstance(label, str) or not label or label != label.strip():
        raise ValueError("Party records require non-empty partyCode and showAs values")
    validate_party_iri(local, term, code)
    house_code, house_no, iri_code = _party_components(str(local))
    if iri_code != code or house_code != house.get("houseCode") or house_no != str(house.get("houseNo")):
        raise ValueError("Party source IRI must match its partyCode and House term")
    return party, house, str(local)


def party_external_graph_iri(record: dict) -> str:
    """External-link graph for one term-scoped ParliamentaryParty source IRI."""
    if isinstance(record, dict) and isinstance(record.get("party"), dict):
        party, house, local = _party_entity(record)
        code = party["partyCode"]
        house_code, house_no = house["houseCode"], str(house["houseNo"])
    else:
        local = record.get("uri") if isinstance(record, dict) else None
        house_code, house_no, code = _party_components(local)
    # The source identity, not partyCode by itself, scopes both state and graph.
    if _party_components(local) != (house_code, house_no, code):
        raise ValueError("Party graph identity does not match its source IRI")
    return "https://data.oireachtas.ie/graph/party/" + house_code + "/" + house_no + "/" + quote(code, safe="") + "/external-links"


def _validate_party_review_iri(value: object) -> str:
    try:
        components = _party_components(value)
    except (TypeError, ValueError) as error:
        raise ReviewError("Party review keys must be complete term-scoped source IRIs") from error
    house_code, house_no, code = components
    term = URIRef(f"https://data.oireachtas.ie/ie/oireachtas/house/{house_code}/{house_no}")
    try:
        validate_party_iri(source_iri(value), term, code)
    except (TypeError, ValueError) as error:
        raise ReviewError("Party review keys must be complete term-scoped source IRIs") from error
    return str(value)


def load_party_review(path: Path) -> tuple[dict[str, dict], str]:
    """Load strict version-1 Party decisions keyed by the complete source IRI."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReviewError(f"invalid Party review file: {error}") from error
    if not isinstance(value, dict) or set(value) != {"version", "decisions"} or type(value.get("version")) is not int or value["version"] != 1 or not isinstance(value.get("decisions"), dict):
        raise ReviewError("Party review file must contain only version 1 and a decisions object")
    decisions = value["decisions"]
    for local_iri, decision in decisions.items():
        _validate_party_review_iri(local_iri)
        if _party_components(local_iri)[2] == "Independent":
            raise ReviewError("Independent collections cannot have Party reconciliation decisions")
        if not isinstance(decision, dict) or not isinstance(decision.get("status"), str) or decision["status"] not in {"accepted", "rejected"}:
            raise ReviewError(f"invalid Party decision for {local_iri!r}")
        if decision["status"] == "accepted" and not valid_qid(decision.get("wikidata")):
            raise ReviewError(f"accepted Party decision for {local_iri!r} needs a Wikidata QID")
        if decision["status"] == "rejected" and "wikidata" in decision:
            raise ReviewError(f"rejected Party decision for {local_iri!r} must not contain Wikidata")
        if "note" in decision and not isinstance(decision["note"], str):
            raise ReviewError(f"Party review note for {local_iri!r} must be a string")
        if set(decision) - {"status", "wikidata", "note"}:
            raise ReviewError(f"unknown Party decision fields for {local_iri!r}")
    return decisions, _hash(value)


def deduplicate_party_records(records: list[dict], advertised: int | None = None) -> list[dict]:
    """Validate a complete Parties input before any reconciliation state is touched."""
    if not isinstance(records, list) or not records:
        raise ValueError("Parties reconciliation input must be a non-empty list")
    unique: dict[str, dict] = {}
    graphs: dict[str, str] = {}
    for wrapper in records:
        _, _, local_iri = _party_entity(wrapper)
        graph_iri = party_external_graph_iri(wrapper)
        if graph_iri in graphs and graphs[graph_iri] != local_iri:
            raise ValueError(f"Party external graph IRI collision: {graph_iri}")
        graphs[graph_iri] = local_iri
        if local_iri in unique:
            if _hash(unique[local_iri]) != _hash(wrapper):
                raise ValueError(f"conflicting duplicate Party source identity: {local_iri}")
            continue
        unique[local_iri] = wrapper
    if advertised is not None and (isinstance(advertised, bool) or not isinstance(advertised, int) or advertised != len(unique)):
        raise ValueError(f"Parties unique count {len(unique)} does not match advertised count {advertised!r}")
    return [unique[key] for key in sorted(unique)]


@dataclass(frozen=True)
class Resolution:
    state: str
    method: str
    evidence: dict
    wikidata: str | None = None
    wikipedia: str | None = None
    dbpedia: str | None = None
    review_applied: bool = False
    enrichment_status: str = "complete"
    enrichment_reason: str | None = None


class ReconciliationStore:
    """Transactional, entity-generic SQLite state store (schema version 4)."""

    VERSION = 4

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _object_type(self, name: str) -> str | None:
        row = self.connection.execute("SELECT type FROM sqlite_master WHERE name=?", (name,)).fetchone()
        return row[0] if row else None

    def _columns(self, table: str) -> set[str]:
        if self._object_type(table) != "table":
            return set()
        return {row[1] for row in self.connection.execute("PRAGMA table_info(" + table + ")")}

    def _add_column(self, table: str, definition: str) -> None:
        name = definition.split()[0]
        if name not in self._columns(table):
            self.connection.execute("ALTER TABLE " + table + " ADD COLUMN " + definition)

    def _initialize(self) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute("CREATE TABLE IF NOT EXISTS reconciliation_schema (version INTEGER NOT NULL)")
            rows = self.connection.execute("SELECT version FROM reconciliation_schema").fetchall()
            if len(rows) > 1 or (rows and (type(rows[0][0]) is not int)):
                raise ReconciliationError("malformed reconciliation SQLite schema")
            version = rows[0][0] if rows else 0
            if version == self.VERSION:
                self._validate_schema()
            elif version in {0, 1, 2, 3}:
                if version == 0:
                    if any(self._object_type(name) for name in ("member_reconciliation", "reconciliation_attempt", "publication_attempt", "reconciliation_record")):
                        raise ReconciliationError("malformed unversioned reconciliation SQLite schema")
                    self._create_generic_tables()
                else:
                    self._migrate_member_schema(version)
                if version == 0:
                    self.connection.execute("INSERT INTO reconciliation_schema VALUES (?)", (self.VERSION,))
                else:
                    self.connection.execute("UPDATE reconciliation_schema SET version=?", (self.VERSION,))
                self._create_member_compatibility_view()
                self._validate_schema()
            else:
                raise ReconciliationError("unsupported reconciliation SQLite schema")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _create_generic_tables(self) -> None:
        self.connection.execute("""CREATE TABLE reconciliation_record (
          entity_kind TEXT NOT NULL, local_iri TEXT NOT NULL, entity_key TEXT NOT NULL,
          identity_hash TEXT NOT NULL,
          state TEXT NOT NULL CHECK(state IN ('accepted','rejected','ambiguous','pending')),
          method TEXT NOT NULL, evidence_json TEXT NOT NULL, service_errors_json TEXT NOT NULL,
          review_hash TEXT NOT NULL, review_applied INTEGER NOT NULL DEFAULT 0,
          wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT,
          checked_at TEXT NOT NULL, next_recheck_at TEXT NOT NULL,
          publication_state TEXT NOT NULL DEFAULT 'clean', published_links_hash TEXT, error TEXT,
          enrichment_status TEXT NOT NULL DEFAULT 'complete', enrichment_reason TEXT,
          pending_payload TEXT, pending_payload_hash TEXT, pending_graph_iri TEXT,
          PRIMARY KEY(entity_kind, local_iri))""")
        self.connection.execute("""CREATE TABLE reconciliation_attempt (
          attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_kind TEXT NOT NULL, local_iri TEXT NOT NULL,
          attempted_at TEXT NOT NULL, identity_hash TEXT NOT NULL, method TEXT NOT NULL,
          state TEXT NOT NULL, evidence_json TEXT NOT NULL, errors_json TEXT NOT NULL,
          review_hash TEXT NOT NULL, review_snapshot_json TEXT, review_applied INTEGER NOT NULL,
          wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT)""")
        self.connection.execute("""CREATE TABLE publication_attempt (
          publication_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_kind TEXT NOT NULL, local_iri TEXT NOT NULL,
          attempted_at TEXT NOT NULL, payload_hash TEXT NOT NULL, result TEXT NOT NULL, error TEXT)""")
        self.connection.execute("CREATE INDEX reconciliation_due ON reconciliation_record(entity_kind, next_recheck_at)")
        self.connection.execute("CREATE INDEX reconciliation_attempt_entity ON reconciliation_attempt(entity_kind, local_iri, attempt_id)")
        self.connection.execute("CREATE INDEX publication_attempt_entity ON publication_attempt(entity_kind, local_iri, publication_id)")

    def _migrate_member_schema(self, version: int) -> None:
        if self._object_type("member_reconciliation") != "table":
            raise ReconciliationError("malformed reconciliation SQLite schema: member_reconciliation")
        required = {"member_iri", "member_code", "identity_hash", "state", "method", "evidence_json", "checked_at", "next_recheck_at"}
        legacy_columns = self._columns("member_reconciliation")
        if not required <= legacy_columns:
            raise ReconciliationError("malformed reconciliation SQLite schema: member_reconciliation")
        if version == 3:
            if not {"pending_payload", "pending_payload_hash"} <= legacy_columns:
                raise ReconciliationError("malformed reconciliation SQLite schema: member_reconciliation")
            for row in self.connection.execute(
                    "SELECT publication_state,pending_payload,pending_payload_hash FROM member_reconciliation"):
                if row[0] != "clean" and row[1] is not None:
                    if not isinstance(row[1], str) or not isinstance(row[2], str) or _hash(row[1]) != row[2]:
                        raise ReconciliationError("malformed dirty Member payload hash during migration")
        # Versions 1 and 2 predate these enrichment/recovery columns. ALTER is
        # in-place so the original rows remain present until the generic copy
        # and schema-version update commit atomically.
        self._add_column("member_reconciliation", "service_errors_json TEXT NOT NULL DEFAULT '[]'")
        self._add_column("member_reconciliation", "review_hash TEXT")
        self._add_column("member_reconciliation", "review_applied INTEGER NOT NULL DEFAULT 0")
        self._add_column("member_reconciliation", "wikidata_iri TEXT")
        self._add_column("member_reconciliation", "wikipedia_iri TEXT")
        self._add_column("member_reconciliation", "dbpedia_iri TEXT")
        self._add_column("member_reconciliation", "publication_state TEXT NOT NULL DEFAULT 'clean'")
        self._add_column("member_reconciliation", "published_links_hash TEXT")
        self._add_column("member_reconciliation", "error TEXT")
        self._add_column("member_reconciliation", "enrichment_status TEXT NOT NULL DEFAULT 'complete'")
        self._add_column("member_reconciliation", "enrichment_reason TEXT")
        self._add_column("member_reconciliation", "pending_payload TEXT")
        self._add_column("member_reconciliation", "pending_payload_hash TEXT")
        legacy_tables = ("member_reconciliation", "reconciliation_attempt", "publication_attempt")
        for name in legacy_tables:
            if self._object_type(name) == "table":
                legacy = "_v3_legacy_" + name
                if self._object_type(legacy):
                    raise ReconciliationError("malformed reconciliation SQLite migration state")
                self.connection.execute(f'ALTER TABLE "{name}" RENAME TO "{legacy}"')
        self._create_generic_tables()
        legacy_member = "_v3_legacy_member_reconciliation"
        for row in self.connection.execute(f'SELECT * FROM "{legacy_member}"').fetchall():
            item = dict(row)
            local_iri = item["member_iri"]
            # Only v3 defined recovery payloads and their exact stored hashes.
            # Older dirty rows have no safely replayable payload or graph link.
            pending_payload = item.get("pending_payload") if version == 3 else None
            pending_hash = item.get("pending_payload_hash") if version == 3 else None
            pending_graph = None
            wikidata_iri = item.get("wikidata_iri")
            wikipedia_iri = item.get("wikipedia_iri")
            dbpedia_iri = item.get("dbpedia_iri")
            if version == 3 and pending_payload is not None and item.get("publication_state", "clean") != "clean":
                try:
                    pending_graph = external_graph_iri({"uri": local_iri, "memberCode": item["member_code"]})
                except (ValueError, TypeError) as error:
                    raise ReconciliationError("malformed dirty Member graph identity during migration") from error
                # Older schema rows may predate one or more output-IRI columns.
                # Recover those fields from the immutable accepted payload so
                # the exact payload can still be checked against saved outcome
                # metadata when it is replayed after migration.
                try:
                    pending_graph_data = Graph().parse(data=pending_payload, format="nt")
                except Exception:
                    pending_graph_data = Graph()
                for subject, predicate, object_ in pending_graph_data:
                    if subject != URIRef(local_iri) or not isinstance(object_, URIRef):
                        continue
                    if predicate == OWL.sameAs and _valid_iri(str(object_), WIKIDATA) and wikidata_iri is None:
                        wikidata_iri = str(object_)
                    elif predicate == OWL.sameAs and _valid_iri(str(object_), DBPEDIA) and dbpedia_iri is None:
                        dbpedia_iri = str(object_)
                    elif predicate == FOAF.isPrimaryTopicOf and _valid_iri(str(object_), WIKIPEDIA) and wikipedia_iri is None:
                        wikipedia_iri = str(object_)
            if wikidata_iri is None:
                try:
                    evidence = json.loads(item.get("evidence_json") or "{}")
                    candidate = evidence.get("wikidata") if isinstance(evidence, dict) else None
                    if _valid_iri(candidate, WIKIDATA):
                        wikidata_iri = candidate
                except (TypeError, json.JSONDecodeError):
                    pass
            values = (
                "member", local_iri, item["member_code"], item["identity_hash"], item["state"], item["method"],
                item.get("evidence_json") or "{}", item.get("service_errors_json") or "[]",
                item.get("review_hash") or "", int(item.get("review_applied") or 0), wikidata_iri,
                wikipedia_iri, dbpedia_iri, item.get("checked_at") or _now(),
                item.get("next_recheck_at") or _now(), item.get("publication_state") or "clean",
                item.get("published_links_hash"), item.get("error"), item.get("enrichment_status") or "complete",
                item.get("enrichment_reason"), pending_payload, pending_hash, pending_graph,
            )
            self.connection.execute("""INSERT INTO reconciliation_record
              (entity_kind,local_iri,entity_key,identity_hash,state,method,evidence_json,service_errors_json,
               review_hash,review_applied,wikidata_iri,wikipedia_iri,dbpedia_iri,checked_at,next_recheck_at,
               publication_state,published_links_hash,error,enrichment_status,enrichment_reason,pending_payload,
               pending_payload_hash,pending_graph_iri) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)
        self._migrate_history("_v3_legacy_reconciliation_attempt", "reconciliation_attempt")
        self._migrate_history("_v3_legacy_publication_attempt", "publication_attempt")
        for name in legacy_tables:
            legacy = "_v3_legacy_" + name
            if self._object_type(legacy) == "table":
                self.connection.execute(f'DROP TABLE "{legacy}"')

    def _migrate_history(self, old_table: str, new_table: str) -> None:
        if self._object_type(old_table) != "table":
            return
        for row in self.connection.execute(f'SELECT * FROM "{old_table}"').fetchall():
            item = dict(row)
            local_iri = item.get("member_iri")
            if not isinstance(local_iri, str) or not local_iri:
                raise ReconciliationError("malformed reconciliation history identity")
            if new_table == "reconciliation_attempt":
                columns = ("attempt_id", "entity_kind", "local_iri", "attempted_at", "identity_hash", "method", "state", "evidence_json", "errors_json", "review_hash", "review_snapshot_json", "review_applied", "wikidata_iri", "wikipedia_iri", "dbpedia_iri")
                values = (item.get("attempt_id"), "member", local_iri, item.get("attempted_at") or _now(), item.get("identity_hash") or "", item.get("method") or "", item.get("state") or "pending", item.get("evidence_json") or "{}", item.get("errors_json") or "[]", item.get("review_hash") or "", item.get("review_snapshot_json"), int(item.get("review_applied") or 0), item.get("wikidata_iri"), item.get("wikipedia_iri"), item.get("dbpedia_iri"))
            else:
                columns = ("publication_id", "entity_kind", "local_iri", "attempted_at", "payload_hash", "result", "error")
                values = (item.get("publication_id"), "member", local_iri, item.get("attempted_at") or _now(), item.get("payload_hash") or "", item.get("result") or "failure", item.get("error"))
            names = ",".join(columns)
            marks = ",".join("?" for _ in columns)
            self.connection.execute(f"INSERT INTO {new_table} ({names}) VALUES ({marks})", values)

    def _create_member_compatibility_view(self) -> None:
        self.connection.execute("""CREATE VIEW member_reconciliation AS
          SELECT local_iri AS member_iri, entity_key AS member_code, identity_hash, state, method,
                 evidence_json, service_errors_json, review_hash, review_applied, wikidata_iri,
                 wikipedia_iri, dbpedia_iri, checked_at, next_recheck_at, publication_state,
                 published_links_hash, error, enrichment_status, enrichment_reason, pending_payload,
                 pending_payload_hash, pending_graph_iri
          FROM reconciliation_record WHERE entity_kind='member'""")
        self.connection.execute("""CREATE TRIGGER member_reconciliation_update INSTEAD OF UPDATE ON member_reconciliation
          BEGIN UPDATE reconciliation_record SET entity_key=NEW.member_code,identity_hash=NEW.identity_hash,
            state=NEW.state,method=NEW.method,evidence_json=NEW.evidence_json,
            service_errors_json=NEW.service_errors_json,review_hash=NEW.review_hash,
            review_applied=NEW.review_applied,wikidata_iri=NEW.wikidata_iri,wikipedia_iri=NEW.wikipedia_iri,
            dbpedia_iri=NEW.dbpedia_iri,checked_at=NEW.checked_at,next_recheck_at=NEW.next_recheck_at,
            publication_state=NEW.publication_state,published_links_hash=NEW.published_links_hash,error=NEW.error,
            enrichment_status=NEW.enrichment_status,enrichment_reason=NEW.enrichment_reason,
            pending_payload=NEW.pending_payload,pending_payload_hash=NEW.pending_payload_hash,
            pending_graph_iri=NEW.pending_graph_iri
            WHERE entity_kind='member' AND local_iri=OLD.member_iri; END""")

    def _validate_schema(self) -> None:
        expected = {
            "reconciliation_record": {"entity_kind", "local_iri", "entity_key", "identity_hash", "state", "method", "evidence_json", "service_errors_json", "review_hash", "review_applied", "wikidata_iri", "wikipedia_iri", "dbpedia_iri", "checked_at", "next_recheck_at", "publication_state", "published_links_hash", "error", "enrichment_status", "enrichment_reason", "pending_payload", "pending_payload_hash", "pending_graph_iri"},
            "reconciliation_attempt": {"attempt_id", "entity_kind", "local_iri", "attempted_at", "identity_hash", "method", "state", "evidence_json", "errors_json", "review_hash", "review_snapshot_json", "review_applied", "wikidata_iri", "wikipedia_iri", "dbpedia_iri"},
            "publication_attempt": {"publication_id", "entity_kind", "local_iri", "attempted_at", "payload_hash", "result", "error"},
        }
        for table, columns in expected.items():
            if self._object_type(table) != "table" or not columns <= self._columns(table):
                raise ReconciliationError("malformed reconciliation SQLite schema: " + table)
        if self._object_type("member_reconciliation") != "view":
            raise ReconciliationError("malformed reconciliation SQLite schema: member compatibility view")

    def get_record(self, entity_kind: str, local_iri: str):
        return self.connection.execute("SELECT * FROM reconciliation_record WHERE entity_kind=? AND local_iri=?", (entity_kind, local_iri)).fetchone()

    def get(self, member_iri: str):
        return self.connection.execute("""SELECT *, local_iri AS member_iri, entity_key AS member_code
          FROM reconciliation_record WHERE entity_kind='member' AND local_iri=?""", (member_iri,)).fetchone()

    def is_due(self, row, review_hash: str) -> bool:
        return row["publication_state"] != "clean" or row["next_recheck_at"] <= _now() or row["review_hash"] != review_hash

    def save_record(self, entity_kind: str, local_iri: str, entity_key: str, identity_hash: str,
                    resolution: Resolution, review_hash: str, review_snapshot: dict | None,
                    payload: str | None, graph_iri: str | None, *, dirty: bool,
                    error: str | None = None) -> None:
        if resolution.state not in STATES:
            raise ValueError("invalid reconciliation state")
        days = 7 if resolution.state in {"pending", "ambiguous"} else 90
        checked_at = _now()
        next_recheck = (datetime.now(timezone.utc) + timedelta(days=7 if resolution.evidence.get("errors") or resolution.enrichment_status != "complete" else days)).replace(microsecond=0).isoformat()
        with self.connection:
            self.connection.execute("""INSERT INTO reconciliation_record
              (entity_kind,local_iri,entity_key,identity_hash,state,method,evidence_json,service_errors_json,
               review_hash,review_applied,wikidata_iri,wikipedia_iri,dbpedia_iri,checked_at,next_recheck_at,
               publication_state,error,enrichment_status,enrichment_reason,pending_payload,pending_payload_hash,pending_graph_iri)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(entity_kind,local_iri) DO UPDATE SET entity_key=excluded.entity_key,
               identity_hash=excluded.identity_hash,state=excluded.state,method=excluded.method,
               evidence_json=excluded.evidence_json,service_errors_json=excluded.service_errors_json,
               review_hash=excluded.review_hash,review_applied=excluded.review_applied,
               wikidata_iri=excluded.wikidata_iri,wikipedia_iri=excluded.wikipedia_iri,dbpedia_iri=excluded.dbpedia_iri,
               checked_at=excluded.checked_at,next_recheck_at=excluded.next_recheck_at,
               publication_state=excluded.publication_state,error=excluded.error,
               enrichment_status=excluded.enrichment_status,enrichment_reason=excluded.enrichment_reason,
               pending_payload=excluded.pending_payload,pending_payload_hash=excluded.pending_payload_hash,
               pending_graph_iri=excluded.pending_graph_iri""",
              (entity_kind, local_iri, entity_key, identity_hash, resolution.state, resolution.method,
               _json(resolution.evidence), _json(resolution.evidence.get("errors", [])), review_hash,
               int(resolution.review_applied), resolution.wikidata, resolution.wikipedia, resolution.dbpedia,
               checked_at, next_recheck, "dirty" if dirty else "clean", error, resolution.enrichment_status,
               resolution.enrichment_reason, payload if dirty else None,
               _hash(payload) if dirty and payload is not None else None, graph_iri if dirty else None))
            self.connection.execute("""INSERT INTO reconciliation_attempt
              (entity_kind,local_iri,attempted_at,identity_hash,method,state,evidence_json,errors_json,
               review_hash,review_snapshot_json,review_applied,wikidata_iri,wikipedia_iri,dbpedia_iri)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (entity_kind, local_iri, checked_at, identity_hash, resolution.method, resolution.state,
               _json(resolution.evidence), _json(resolution.evidence.get("errors", [])), review_hash,
               _json(review_snapshot) if review_snapshot else None, int(resolution.review_applied),
               resolution.wikidata, resolution.wikipedia, resolution.dbpedia))

    def save(self, member_iri: str, code: str, identity_hash: str, resolution: Resolution,
             review_hash: str, review_snapshot: dict | None, payload: str | None, *, dirty: bool,
             error: str | None = None) -> None:
        graph_iri = external_graph_iri({"uri": member_iri, "memberCode": code}) if dirty else None
        self.save_record("member", member_iri, code, identity_hash, resolution, review_hash,
                         review_snapshot, payload, graph_iri, dirty=dirty, error=error)

    def mark_record_published(self, entity_kind: str, local_iri: str, links_hash: str) -> None:
        with self.connection:
            self.connection.execute("""UPDATE reconciliation_record SET publication_state='clean',
              published_links_hash=?,pending_payload=NULL,pending_payload_hash=NULL,pending_graph_iri=NULL,error=NULL
              WHERE entity_kind=? AND local_iri=?""", (links_hash, entity_kind, local_iri))

    def mark_published(self, member_iri: str, links_hash: str) -> None:
        self.mark_record_published("member", member_iri, links_hash)

    def record_publication_result(self, entity_kind: str, local_iri: str, payload_hash: str,
                                  result: str, error: str | None = None) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO publication_attempt (entity_kind,local_iri,attempted_at,payload_hash,result,error) VALUES (?,?,?,?,?,?)", (entity_kind, local_iri, _now(), payload_hash, result, error))
            if error:
                self.connection.execute("UPDATE reconciliation_record SET error=? WHERE entity_kind=? AND local_iri=?", (error, entity_kind, local_iri))

    def publication_result(self, member_iri: str, payload_hash: str, result: str, error: str | None = None) -> None:
        self.record_publication_result("member", member_iri, payload_hash, result, error)

    def close(self):
        self.connection.close()


def load_review(path: Path) -> tuple[dict[str, dict], str]:
    """Load the deliberately small, version-controlled JSON decision file."""
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise ReviewError(f"invalid review file: {error}") from error
    if not isinstance(value, dict) or set(value) != {"version", "decisions"} or type(value.get("version")) is not int or value["version"] != 1 or not isinstance(value.get("decisions"), dict): raise ReviewError("review file must contain only version 1 and a decisions object")
    decisions = value["decisions"]
    for code, decision in decisions.items():
        if not isinstance(code, str) or not code or not isinstance(decision, dict) or decision.get("status") not in {"accepted", "rejected"}: raise ReviewError(f"invalid decision for {code!r}")
        if decision["status"] == "accepted" and not valid_qid(decision.get("wikidata")): raise ReviewError(f"accepted decision for {code!r} needs a QID")
        if decision["status"] == "rejected" and "wikidata" in decision: raise ReviewError(f"rejected decision for {code!r} must not contain Wikidata")
        if "note" in decision and not isinstance(decision["note"], str): raise ReviewError(f"review note for {code!r} must be a string")
        if set(decision) - {"status", "wikidata", "note"}: raise ReviewError(f"unknown decision fields for {code!r}")
    return decisions, _hash(value)


class WikidataClient:
    """Mockable stdlib client; production calls use Wikidata's entity API."""
    def __init__(self, endpoint="https://www.wikidata.org/w/api.php", lookup_endpoint="https://query.wikidata.org/sparql", timeout=20): self.endpoint, self.lookup_endpoint, self.timeout = endpoint, lookup_endpoint, timeout
    def _get(self, params):
        from urllib.parse import urlencode
        with urlopen(Request(self.endpoint + "?" + urlencode(params), headers={"Accept":"application/json"}), timeout=self.timeout) as response: return json.loads(response.read())
    def lookup_member_code(self, member_code: str) -> list[str]:
        from urllib.parse import urlencode
        query = "SELECT ?item WHERE { ?item wdt:P4690 " + json.dumps(member_code) + " }"
        request = Request(self.lookup_endpoint + "?" + urlencode({"query": query, "format": "json"}), headers={"Accept":"application/sparql-results+json", "User-Agent":"oireachtas-etl/phase-3.5"})
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read())
        try: bindings = payload["results"]["bindings"]
        except (KeyError, TypeError) as error: raise ReconciliationError("malformed Wikidata SPARQL response") from error
        if not isinstance(bindings, list): raise ReconciliationError("malformed Wikidata SPARQL response")
        qids = []
        for row in bindings:
            try: binding = row["item"]
            except (KeyError, TypeError) as error: raise ReconciliationError("malformed Wikidata SPARQL binding") from error
            qid = _wikidata_qid_from_sparql_binding(binding)
            if qid is None:
                raise ReconciliationError("invalid Wikidata SPARQL item binding")
            qids.append(qid)
        return qids

    def lookup_party_candidates(self, record: dict) -> list[dict]:
        """Return exact-label Irish political-party candidates as review evidence.

        The result is deliberately a candidate set, never an identity decision.
        Both an Irish political-party type and an Ireland jurisdiction assertion
        are required in the query; labels/code only discover review candidates.
        """
        party, house, _ = _party_entity(record)
        terms = sorted({party["partyCode"], party["partyCode"].replace("_", " "), party["showAs"]})
        values = " ".join(json.dumps(value, ensure_ascii=False) for value in terms)
        query = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT DISTINCT ?item ?label ?instanceType ?jurisdiction ?inception ?dissolution WHERE {
  VALUES ?wantedLabel { %s }
  ?item (rdfs:label|skos:altLabel) ?label .
  FILTER(LCASE(STR(?label)) = LCASE(?wantedLabel))
  ?item wdt:P31 ?instanceType .
  ?instanceType wdt:P279* wd:Q7278 .
  { ?item wdt:P17 wd:Q27 . BIND(wd:Q27 AS ?jurisdiction) }
  UNION
  { ?item wdt:P1001 wd:Q27 . BIND(wd:Q27 AS ?jurisdiction) }
  OPTIONAL { ?item wdt:P571 ?inception }
  OPTIONAL { ?item wdt:P576 ?dissolution }
}""" % values
        from urllib.parse import urlencode
        request = Request(self.lookup_endpoint + "?" + urlencode({"query": query, "format": "json"}),
                          headers={"Accept": "application/sparql-results+json", "User-Agent": "oireachtas-etl/phase-4.5"})
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read())
        try:
            rows = payload["results"]["bindings"]
        except (KeyError, TypeError) as error:
            raise ReconciliationError("malformed Wikidata Party candidate response") from error
        if not isinstance(rows, list):
            raise ReconciliationError("malformed Wikidata Party candidate response")
        local_terms = {value.casefold(): value for value in terms}
        candidates: dict[str, dict] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ReconciliationError("malformed Wikidata Party candidate binding")
            item = row.get("item", {})
            qid = _wikidata_qid_from_sparql_binding(item)
            if qid is None:
                raise ReconciliationError("invalid Wikidata Party candidate item")
            label = row.get("label", {})
            label_value = label.get("value") if isinstance(label, dict) and label.get("type") == "literal" else None
            if not isinstance(label_value, str) or not label_value:
                raise ReconciliationError("invalid Wikidata Party candidate label")
            instance = row.get("instanceType", {})
            instance_qid = _wikidata_qid_from_sparql_binding(instance)
            if instance_qid is None:
                raise ReconciliationError("invalid Wikidata Party candidate type")
            jurisdiction = row.get("jurisdiction", {})
            jurisdiction_qid = _wikidata_qid_from_sparql_binding(jurisdiction)
            if jurisdiction_qid != "Q27":
                raise ReconciliationError("invalid Wikidata Party candidate jurisdiction")
            candidate = candidates.setdefault(qid, {"qid": qid, "labels": [], "matched_on": [], "types": ["Q7278"], "instance_types": [], "jurisdictions": ["Q27"], "inception": [], "dissolution": []})
            candidate["labels"].append(label_value)
            matched = local_terms.get(label_value.casefold())
            if matched is not None:
                candidate["matched_on"].append(matched)
            candidate["instance_types"].append(instance_qid)
            for name in ("inception", "dissolution"):
                binding = row.get(name)
                if binding is None:
                    continue
                value = binding.get("value") if isinstance(binding, dict) else None
                if not isinstance(binding, dict) or binding.get("type") != "literal":
                    raise ReconciliationError("invalid Wikidata Party historical date binding")
                normalized = _wikidata_year_or_date(value)
                if normalized is None:
                    raise ReconciliationError("invalid Wikidata Party historical date")
                candidate[name].append(normalized)
        return [normalize_party_candidate(candidate) for _, candidate in sorted(candidates.items())]
    def entity(self, qid: str) -> dict: return self._get({"action":"wbgetentities", "ids":qid, "format":"json"})


class DbpediaClient:
    def __init__(self, endpoint="https://dbpedia.org/sparql", timeout=20): self.endpoint, self.timeout = endpoint, timeout
    def resolve_wikidata(self, qid: str) -> list[dict]:
        from urllib.parse import urlencode
        # Both linkage and person typing are required; title similarity is never used.
        wd = wikidata_iri(qid)
        query = """SELECT DISTINCT ?person WHERE {
          ?person <http://www.w3.org/2002/07/owl#sameAs> <%s> ;
                  a ?type . FILTER(?type IN (<http://xmlns.com/foaf/0.1/Person>, <http://dbpedia.org/ontology/Person>))
        }""" % wd
        request = Request(self.endpoint + "?" + urlencode({"query":query,"format":"json"}), headers={"Accept":"application/sparql-results+json", "User-Agent":"oireachtas-etl/phase-3.5"})
        with urlopen(request, timeout=self.timeout) as response: payload = json.loads(response.read())
        try: rows = payload["results"]["bindings"]
        except (KeyError, TypeError) as error: raise ReconciliationError("malformed DBpedia SPARQL response") from error
        if not isinstance(rows, list): raise ReconciliationError("malformed DBpedia SPARQL response")
        people = []
        for row in rows:
            binding = row.get("person") if isinstance(row, dict) else None
            value = binding.get("value") if isinstance(binding, dict) else None
            if not isinstance(binding, dict) or binding.get("type") != "uri" or not _valid_iri(value, DBPEDIA):
                raise ReconciliationError("invalid DBpedia SPARQL person binding")
            people.append({"iri": value, "is_person": True})
        return people


def _enwiki(entity: dict) -> str | None:
    # The caller passes only the accepted QID. Never use an arbitrary entity.
    try: title = entity["sitelinks"]["enwiki"]["title"]
    except (KeyError, TypeError): return None
    if not isinstance(title, str) or not title: raise ReconciliationError("malformed Wikidata enwiki sitelink")
    value = WIKIPEDIA + quote(str(title).replace(" ", "_"), safe="()_,-.")
    return value if _valid_iri(value, WIKIPEDIA) else None


def resolve(member: dict, review: dict[str, dict], wikidata_client, dbpedia_client) -> Resolution:
    member_graph_iri(member)  # Phase 3 canonical Member identity validation.
    code = member.get("memberCode")
    if not isinstance(code, str) or not code: raise ValueError("memberCode is required")
    decision = review.get(code)
    if decision and decision["status"] == "rejected":
        return Resolution("rejected", "manual-review", {"decision": decision}, review_applied=True)
    if decision:
        # Human acceptance is authoritative and does not depend on the
        # availability or current output of the automated P4690 lookup.
        candidates = []
        qid, method = decision["wikidata"], "manual-review"
    else:
        try:
            raw_candidates = wikidata_client.lookup_member_code(code)
            if not isinstance(raw_candidates, list) or any(not valid_qid(q) for q in raw_candidates):
                raise ReconciliationError("malformed Wikidata P4690 candidate response")
            candidates = sorted(set(raw_candidates))
        except FixtureResponseError:
            raise
        except Exception as error:
            return Resolution("pending", "wikidata-p4690-outage", {"errors":[str(error)], "reason":"lookup-error"}, enrichment_status="unresolved", enrichment_reason="lookup-error")
        if len(candidates) == 0:
            return Resolution("pending", "wikidata-p4690-no-match", {"memberCode":code,"candidates":[],"reason":"no-exact-p4690-match"}, enrichment_status="unresolved", enrichment_reason="no-match")
        if len(candidates) != 1:
            return Resolution("ambiguous", "wikidata-p4690-ambiguous", {"memberCode":code,"candidates":candidates,"reason":"multiple-exact-p4690-matches"}, enrichment_status="unresolved", enrichment_reason="primary-ambiguity")
        qid, method = candidates[0], "wikidata-p4690-exact"
    wd = wikidata_iri(qid)
    evidence = {"memberCode": code, "wikidata": wd, "candidates": candidates,
                "query_method": "Wikidata P4690 exact memberCode"}
    if decision: evidence["decision"] = decision
    wikipedia = dbpedia = None
    enrichment_status, enrichment_reason = "complete", None
    try:
        response = wikidata_client.entity(qid)
        if (not isinstance(response, dict) or response.get("redirects") or not isinstance(response.get("entities"), dict)
                or not isinstance(response["entities"].get(qid), dict)
                or response["entities"][qid].get("missing") is not None
                or response["entities"][qid].get("id", qid) != qid):
            raise ReconciliationError("malformed Wikidata entity response for accepted QID")
        wikipedia = _enwiki(response["entities"][qid])
    except FixtureResponseError:
        raise
    except Exception as error:
        evidence.setdefault("errors", []).append("Wikidata entity: " + str(error))
        enrichment_status, enrichment_reason = "retry", "wikidata-entity-error"
    try:
        raw_people = dbpedia_client.resolve_wikidata(qid)
        if not isinstance(raw_people, list) or any(not isinstance(r, dict) or set(r) != {"iri", "is_person"} or not isinstance(r["iri"], str) or not isinstance(r["is_person"], bool) or not _valid_iri(r["iri"], DBPEDIA) for r in raw_people):
            raise ReconciliationError("malformed DBpedia exact-identity response")
        people = [r["iri"] for r in raw_people if r["is_person"]]
        people = sorted(set(people))
        if len(people) == 1: dbpedia = people[0]
        elif len(people) > 1:
            evidence["dbpedia_candidates"] = people
            enrichment_status, enrichment_reason = "ambiguous", "dbpedia-multiple-exact-persons"
    except FixtureResponseError:
        raise
    except Exception as error:
        evidence.setdefault("errors", []).append("DBpedia: " + str(error))
        enrichment_status, enrichment_reason = "retry", "dbpedia-error"
    return Resolution("accepted", method, evidence, wd, wikipedia, dbpedia, bool(decision), enrichment_status, enrichment_reason)


def _party_term_period(house: dict) -> dict | None:
    period = house.get("dateRange")
    if period is None:
        return None
    if not isinstance(period, dict) or set(period) - {"start", "end"}:
        raise ValueError("Party House dateRange must contain start and optional end")
    values = {}
    for key in ("start", "end"):
        value = period.get(key)
        if value is None:
            values[key] = None
            continue
        if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
            raise ValueError("Party House dateRange values must be ISO dates")
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError("Party House dateRange values must be valid ISO dates") from error
        values[key] = value
    if values["start"] is None:
        raise ValueError("Party House dateRange.start is required when dateRange is supplied")
    if values["end"] is not None and values["end"] < values["start"]:
        raise ValueError("Party House dateRange is reversed")
    return values


def _candidate_historical_conflicts(candidate: dict, period: dict | None) -> list[str]:
    if period is None:
        return []
    conflicts = []
    start, end = period["start"], period["end"]
    if candidate["inception"] and end is not None and min(candidate["inception"]) > end:
        conflicts.append("party-inception-after-house-term")
    if candidate["dissolution"] and max(candidate["dissolution"]) < start:
        conflicts.append("party-dissolved-before-house-term")
    return conflicts


def _previous_party_context(previous) -> tuple[list, dict | None]:
    if previous is None:
        return [], None
    try:
        evidence = json.loads(previous["evidence_json"])
    except (TypeError, json.JSONDecodeError):
        return [], None
    if not isinstance(evidence, dict):
        return [], None
    candidates = evidence.get("candidates") or evidence.get("previous_candidates") or []
    previous_decision = evidence.get("decision")
    if not isinstance(previous_decision, dict) or previous_decision.get("status") != "rejected":
        previous_decision = evidence.get("previous_review_decision")
    if not isinstance(previous_decision, dict) or previous_decision.get("status") != "rejected":
        previous_decision = None
    return (candidates if isinstance(candidates, list) else [], previous_decision)


def resolve_party(record: dict, review: dict[str, dict], wikidata_client, *, previous=None) -> Resolution:
    """Generate review candidates for an eligible term-scoped Party only."""
    party, house, local_iri = _party_entity(record)
    if party["partyCode"] == "Independent":
        raise ValueError("IndependentMemberCollection is excluded from Party reconciliation")
    decision = review.get(local_iri)
    previous_candidates, previous_rejection = _previous_party_context(previous)
    if decision and decision["status"] == "rejected":
        evidence = {"local_iri": local_iri, "decision": decision, "previous_candidates": previous_candidates,
                    "previous_review_decision": previous_rejection}
        return Resolution("rejected", "manual-review", evidence, review_applied=True)
    if decision:
        qid = decision["wikidata"]
        return Resolution("accepted", "manual-review", {
            "local_iri": local_iri, "partyCode": party["partyCode"], "showAs": party["showAs"],
            "wikidata": wikidata_iri(qid), "decision": decision,
            "previous_candidates": previous_candidates, "previous_review_decision": previous_rejection,
        }, wikidata_iri(qid), review_applied=True)
    query_terms = sorted({party["partyCode"], party["partyCode"].replace("_", " "), party["showAs"]})
    period = _party_term_period(house)
    try:
        raw_candidates = wikidata_client.lookup_party_candidates(record)
        if not isinstance(raw_candidates, list):
            raise ReconciliationError("malformed Wikidata Party candidate response")
        candidates_by_qid = {}
        for raw in raw_candidates:
            candidate = normalize_party_candidate(raw)
            if not set(candidate["matched_on"]) <= set(query_terms):
                raise ReconciliationError("Wikidata Party candidate matched an unknown local label")
            candidate_labels = {label.casefold() for label in candidate["labels"]}
            if any(matched.casefold() not in candidate_labels for matched in candidate["matched_on"]):
                raise ReconciliationError("Wikidata Party candidate does not contain its matched label")
            if candidate["qid"] in candidates_by_qid:
                raise ReconciliationError("duplicate Wikidata Party candidate QID")
            candidates_by_qid[candidate["qid"]] = {
                **candidate,
                "historical_conflicts": _candidate_historical_conflicts(candidate, period),
            }
        candidates = [candidates_by_qid[qid] for qid in sorted(candidates_by_qid)]
    except FixtureResponseError:
        raise
    except Exception as error:
        evidence = {"local_iri": local_iri, "partyCode": party["partyCode"], "showAs": party["showAs"],
                    "houseCode": house["houseCode"], "houseNo": str(house["houseNo"]),
                    "query_terms": query_terms, "candidates": [], "previous_candidates": previous_candidates,
                    "previous_review_decision": previous_rejection,
                    "errors": [str(error)], "reason": "lookup-error"}
        return Resolution("pending", "wikidata-party-candidate-outage", evidence,
                          enrichment_status="unresolved", enrichment_reason="lookup-error")
    evidence = {"local_iri": local_iri, "partyCode": party["partyCode"], "showAs": party["showAs"],
                "houseCode": house["houseCode"], "houseNo": str(house["houseNo"]),
                "query_terms": query_terms, "house_period": period, "candidates": candidates,
                "previous_candidates": previous_candidates, "previous_review_decision": previous_rejection,
                "candidate_policy": "exact-label; Wikidata political-party type and Ireland jurisdiction; human review required"}
    if not candidates:
        evidence["reason"] = "no-eligible-wikidata-candidate"
        return Resolution("pending", "wikidata-party-no-candidate", evidence,
                          enrichment_status="unresolved", enrichment_reason="no-candidate")
    evidence["reason"] = "human-review-required"
    state = "ambiguous" if len(candidates) > 1 else "pending"
    return Resolution(state, "wikidata-party-candidate-review", evidence,
                      enrichment_status="unresolved", enrichment_reason="human-review-required")


def party_links_graph(record: dict, resolution: Resolution) -> Graph:
    party, _, local_iri = _party_entity(record)
    graph = Graph()
    if resolution.state == "accepted":
        if not resolution.review_applied or not resolution.wikidata or not _valid_iri(resolution.wikidata, WIKIDATA):
            raise ValueError("accepted Party identity requires an explicit reviewed Wikidata QID")
        graph.add((URIRef(local_iri), MEMBERS.recognisedAsParty, URIRef(resolution.wikidata)))
    _validate_party_graph(local_iri, graph)
    return graph


def _validate_member_graph(member: dict, graph: Graph) -> None:
    member_graph_iri(member)
    subject = URIRef(member["uri"])
    permitted = {(OWL.sameAs, WIKIDATA), (OWL.sameAs, DBPEDIA), (FOAF.isPrimaryTopicOf, WIKIPEDIA)}
    if any(not isinstance(s, URIRef) or not isinstance(p, URIRef) or not isinstance(o, URIRef)
           or s != subject or not any(p == predicate and _valid_iri(str(o), prefix) for predicate, prefix in permitted)
           for s, p, o in graph):
        raise ReconciliationError("Member external graph boundary violation")


def links_graph(member: dict, resolution: Resolution) -> Graph:
    member_graph_iri(member)
    graph = Graph()
    subject = URIRef(member["uri"])
    if resolution.state == "accepted":
        if resolution.wikidata:
            graph.add((subject, OWL.sameAs, URIRef(resolution.wikidata)))
        if resolution.dbpedia:
            graph.add((subject, OWL.sameAs, URIRef(resolution.dbpedia)))
        if resolution.wikipedia:
            graph.add((subject, FOAF.isPrimaryTopicOf, URIRef(resolution.wikipedia)))
    _validate_member_graph(member, graph)
    return graph


def _validate_party_graph(local_iri: str, graph: Graph) -> None:
    _validate_party_review_iri(local_iri)
    subject = URIRef(local_iri)
    if any(not isinstance(s, URIRef) or not isinstance(p, URIRef) or not isinstance(o, URIRef)
           or s != subject or p != MEMBERS.recognisedAsParty or not _valid_iri(str(o), WIKIDATA)
           for s, p, o in graph):
        raise ReconciliationError("Party external graph boundary violation")
    if len(graph) > 1:
        raise ReconciliationError("Party external graph may contain only one reviewed recognisedAsParty link")


def verify_reconciliation_graph(client, graph_iri: str, graph: Graph) -> None:
    """Post-load exact whole-graph gate, including the valid empty-graph case."""
    query = "SELECT ?s ?p ?o WHERE { GRAPH <%s> { ?s ?p ?o } }" % graph_iri
    rows = client.query(query)
    actual = set()
    for row in rows:
        try:
            terms = (row["s"], row["p"], row["o"])
            if any(not isinstance(term, dict) or term.get("type") != "uri" or not isinstance(term.get("value"), str) for term in terms):
                raise ReconciliationError("external-links competency returned a non-IRI term")
            actual.add(tuple(term["value"] for term in terms))
        except (KeyError, AttributeError, TypeError) as error:
            raise ReconciliationError("malformed external-links competency response") from error
    expected = {(str(s), str(p), str(o)) for s, p, o in graph}
    if actual != expected:
        raise ReconciliationError("external-links post-load whole-graph verification failed")


def verify_external_links_competency(client, member: dict, graph: Graph) -> None:
    verify_reconciliation_graph(client, external_graph_iri(member), graph)


class _MemberPolicy:
    entity_kind = "member"

    def extract(self, wrapper):
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict):
            raise ValueError("each Members record must contain a member object")
        return wrapper["member"]

    def validate(self, entity):
        member_graph_iri(entity)

    def local_iri(self, entity):
        return entity["uri"]

    def entity_key(self, entity):
        return entity["memberCode"]

    def review_key(self, entity):
        return entity["memberCode"]

    def fingerprint(self, entity):
        # Preserve the Phase 3.5 Member identity fingerprint and public behavior.
        return _hash({"memberCode": entity.get("memberCode")})

    def eligible(self, entity):
        return True

    def graph_iri(self, entity):
        return external_graph_iri(entity)

    def stored_graph_iri(self, local_iri, entity_key):
        return external_graph_iri({"uri": local_iri, "memberCode": entity_key})

    def resolve(self, entity, review, wikidata_client, dbpedia_client, previous):
        return resolve(entity, review, wikidata_client, dbpedia_client)

    def links_graph(self, entity, resolution):
        return links_graph(entity, resolution)

    def validate_stored_graph(self, local_iri, entity_key, graph, resolution):
        member = {"uri": local_iri, "memberCode": entity_key}
        _validate_member_graph(member, graph)
        expected = links_graph(member, resolution) if resolution.state == "accepted" else Graph()
        if set(graph) != set(expected):
            raise ReconciliationError("Member dirty payload does not match its saved reconciliation outcome")


class _PartyPolicy:
    entity_kind = "party"

    def extract(self, wrapper):
        _party_entity(wrapper)
        return wrapper

    def validate(self, entity):
        _party_entity(entity)

    def local_iri(self, entity):
        return _party_entity(entity)[2]

    def entity_key(self, entity):
        return _party_entity(entity)[0]["partyCode"]

    def review_key(self, entity):
        return self.local_iri(entity)

    def fingerprint(self, entity):
        party, house, local_iri = _party_entity(entity)
        return _hash({"uri": local_iri, "partyCode": party["partyCode"], "showAs": party["showAs"],
                      "houseCode": house["houseCode"], "houseNo": str(house["houseNo"]),
                      "houseUri": house["uri"], "dateRange": house.get("dateRange")})

    def eligible(self, entity):
        return _party_entity(entity)[0]["partyCode"] != "Independent"

    def graph_iri(self, entity):
        return party_external_graph_iri(entity)

    def stored_graph_iri(self, local_iri, entity_key):
        graph_iri = party_external_graph_iri({"uri": local_iri})
        if _party_components(local_iri)[2] != entity_key:
            raise ReconciliationError("stored Party key does not match its complete source IRI")
        return graph_iri

    def resolve(self, entity, review, wikidata_client, dbpedia_client, previous):
        return resolve_party(entity, review, wikidata_client, previous=previous)

    def links_graph(self, entity, resolution):
        return party_links_graph(entity, resolution)

    def validate_stored_graph(self, local_iri, entity_key, graph, resolution):
        _validate_party_graph(local_iri, graph)
        expected = Graph()
        if resolution.state == "accepted":
            if not resolution.review_applied or not resolution.wikidata or not _valid_iri(resolution.wikidata, WIKIDATA):
                raise ReconciliationError("accepted Party dirty state lacks explicit reviewed identity")
            expected.add((URIRef(local_iri), MEMBERS.recognisedAsParty, URIRef(resolution.wikidata)))
        if set(graph) != set(expected):
            raise ReconciliationError("Party dirty payload does not match its saved reconciliation outcome")


def _stored_resolution(row) -> Resolution:
    try:
        evidence = json.loads(row["evidence_json"])
    except (TypeError, json.JSONDecodeError) as error:
        raise ReconciliationError("dirty reconciliation evidence is malformed") from error
    if not isinstance(evidence, dict) or row["state"] not in STATES:
        raise ReconciliationError("dirty reconciliation state is malformed")
    return Resolution(row["state"], row["method"], evidence, row["wikidata_iri"], row["wikipedia_iri"],
                      row["dbpedia_iri"], bool(row["review_applied"]), row["enrichment_status"], row["enrichment_reason"])


def _replay_pending(row, policy, publish, competency_client, store):
    payload, payload_hash = row["pending_payload"], row["pending_payload_hash"]
    if not isinstance(payload, str) or not isinstance(payload_hash, str) or _hash(payload) != payload_hash:
        raise ReconciliationError("dirty reconciliation payload or hash is missing/invalid")
    try:
        graph = Graph().parse(data=payload, format="nt")
        graph_iri = policy.stored_graph_iri(row["local_iri"], row["entity_key"])
    except Exception as error:
        raise ReconciliationError("dirty reconciliation payload or graph identity is malformed") from error
    if row["pending_graph_iri"] != graph_iri:
        raise ReconciliationError("dirty reconciliation graph boundary does not match stored identity")
    resolution = _stored_resolution(row)
    policy.validate_stored_graph(row["local_iri"], row["entity_key"], graph, resolution)
    if publish is not None:
        try:
            publish.replace(graph_iri, payload, content_type="application/n-triples")
            verify_reconciliation_graph(competency_client, graph_iri, graph)
            store.record_publication_result(policy.entity_kind, row["local_iri"], payload_hash, "success")
            store.mark_record_published(policy.entity_kind, row["local_iri"], payload_hash)
        except Exception as error:
            store.record_publication_result(policy.entity_kind, row["local_iri"], payload_hash, "failure", str(error))
            raise
    return graph_iri, payload, graph, resolution


def reconcile_entities(records: list[dict], store: ReconciliationStore, review: dict[str, dict], review_hash: str,
                       wikidata_client, dbpedia_client=None, *, policy, all_records=False, publish=None,
                       competency_client=None) -> list[tuple[object, Resolution, Graph]]:
    """Shared state, audit, scheduling and publication engine for entity policies."""
    if publish is not None and competency_client is None:
        raise ReconciliationError("external graph publication requires a competency client")
    entities, seen = [], set()
    reviewable_keys = set()
    for wrapper in records:
        entity = policy.extract(wrapper)
        policy.validate(entity)
        local_iri = policy.local_iri(entity)
        if local_iri in seen:
            raise ValueError(f"duplicate {policy.entity_kind} reconciliation identity: {local_iri}")
        seen.add(local_iri)
        if policy.eligible(entity):
            reviewable_keys.add(policy.review_key(entity))
        entities.append(entity)
    stale = sorted(set(review) - reviewable_keys)
    if stale:
        noun = "Members" if policy.entity_kind == "member" else "Parties"
        raise ReviewError("review decisions do not match current " + noun + " input: " + ", ".join(stale))
    # Once the review file has passed its input-membership gate, recover dirty
    # graphs before any new reconciliation or lookup. Every stored payload is
    # validated before a PUT.
    recovered = {}
    for entity in entities:
        if not policy.eligible(entity):
            continue
        local_iri = policy.local_iri(entity)
        old = store.get_record(policy.entity_kind, local_iri)
        if old is not None and old["publication_state"] == "dirty":
            _, _, replay_graph, replay_resolution = _replay_pending(old, policy, publish, competency_client, store)
            recovered[local_iri] = (replay_resolution, replay_graph)
    results = []
    for entity in entities:
        if not policy.eligible(entity):
            continue
        local_iri = policy.local_iri(entity)
        entity_key = policy.entity_key(entity)
        fingerprint = policy.fingerprint(entity)
        old = store.get_record(policy.entity_kind, local_iri)
        if local_iri in recovered:
            replay_resolution, replay_graph = recovered[local_iri]
            if publish is None:
                results.append((entity, replay_resolution, replay_graph))
                continue
            if old["identity_hash"] == fingerprint and old["review_hash"] == review_hash and not all_records:
                results.append((entity, replay_resolution, replay_graph))
                continue
        selected = all_records or old is None or old["identity_hash"] != fingerprint or store.is_due(old, review_hash)
        if not selected:
            continue
        result = policy.resolve(entity, review, wikidata_client, dbpedia_client, old)
        graph = policy.links_graph(entity, result)
        payload = ntriples(graph)
        payload_hash = _hash(payload)
        unresolved = result.state in {"pending", "ambiguous"}
        explicit_rejection = result.state == "rejected" and result.review_applied
        needs_publication = (not unresolved and (all_records or old is None or old["publication_state"] != "clean" or old["published_links_hash"] != payload_hash)) or explicit_rejection
        # The dirty marker and exact payload are durable before any graph PUT.
        store.save_record(policy.entity_kind, local_iri, entity_key, fingerprint, result, review_hash,
                          review.get(policy.review_key(entity)), payload, policy.graph_iri(entity), dirty=needs_publication)
        if publish is not None and needs_publication:
            try:
                publish.replace(policy.graph_iri(entity), payload, content_type="application/n-triples")
                verify_reconciliation_graph(competency_client, policy.graph_iri(entity), graph)
                store.record_publication_result(policy.entity_kind, local_iri, payload_hash, "success")
                store.mark_record_published(policy.entity_kind, local_iri, payload_hash)
            except Exception as error:
                store.record_publication_result(policy.entity_kind, local_iri, payload_hash, "failure", str(error))
                raise
        results.append((entity, result, graph))
    return results


def reconcile_records(records: list[dict], store: ReconciliationStore, review: dict[str, dict], review_hash: str,
                      wikidata_client, dbpedia_client, *, all_records=False, publish=None,
                      competency_client=None) -> list[tuple[dict, Resolution, Graph]]:
    """Backward-compatible Member policy entry point."""
    return reconcile_entities(records, store, review, review_hash, wikidata_client, dbpedia_client,
                              policy=_MemberPolicy(), all_records=all_records, publish=publish,
                              competency_client=competency_client)


def reconcile_party_records(records: list[dict], store: ReconciliationStore, review: dict[str, dict], review_hash: str,
                            wikidata_client, *, all_records=False, publish=None,
                            competency_client=None) -> list[tuple[dict, Resolution, Graph]]:
    """Reconcile only API-derived ParliamentaryParty instances; Independent is excluded."""
    validated = deduplicate_party_records(records)
    return reconcile_entities(validated, store, review, review_hash, wikidata_client,
                              policy=_PartyPolicy(), all_records=all_records, publish=publish,
                              competency_client=competency_client)
