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
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from rdflib import Graph, URIRef
from rdflib.namespace import FOAF, OWL

from .serialization import ntriples
from .transforms.members import member_graph_iri

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


def external_graph_iri(member: dict) -> str:
    # Reuse the approved Member identity validation and percent-encoding.
    return member_graph_iri(member) + "/external-links"


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
    """Small transactional state store with an explicit schema version."""
    VERSION = 3
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.execute("CREATE TABLE IF NOT EXISTS reconciliation_schema (version INTEGER NOT NULL)")
            rows = self.connection.execute("SELECT version FROM reconciliation_schema").fetchall()
            if len(rows) > 1 or (rows and not isinstance(rows[0][0], int)):
                raise ReconciliationError("malformed reconciliation SQLite schema")
            version = rows[0][0] if rows else 0
            if version != self.VERSION:
                self.connection.execute("""CREATE TABLE IF NOT EXISTS member_reconciliation (
              member_iri TEXT PRIMARY KEY, member_code TEXT NOT NULL UNIQUE, identity_hash TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('accepted','rejected','ambiguous','pending')),
              method TEXT NOT NULL, evidence_json TEXT NOT NULL, service_errors_json TEXT NOT NULL,
              review_hash TEXT, review_applied INTEGER NOT NULL DEFAULT 0,
              wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT,
              checked_at TEXT NOT NULL, next_recheck_at TEXT NOT NULL,
               publication_state TEXT NOT NULL DEFAULT 'clean', published_links_hash TEXT, error TEXT)""")
                self.connection.execute("""CREATE TABLE IF NOT EXISTS reconciliation_attempt (
              attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, member_iri TEXT NOT NULL,
              attempted_at TEXT NOT NULL, identity_hash TEXT NOT NULL, method TEXT NOT NULL,
              state TEXT NOT NULL, evidence_json TEXT NOT NULL, errors_json TEXT NOT NULL,
               review_hash TEXT NOT NULL, review_snapshot_json TEXT, review_applied INTEGER NOT NULL,
               wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT)""")
                self.connection.execute("""CREATE TABLE IF NOT EXISTS publication_attempt (
              publication_id INTEGER PRIMARY KEY AUTOINCREMENT, member_iri TEXT NOT NULL,
              attempted_at TEXT NOT NULL, payload_hash TEXT NOT NULL, result TEXT NOT NULL,
              error TEXT)""")
            if version == 0:
                self._add_v3_columns()
                self.connection.execute("INSERT INTO reconciliation_schema VALUES (?)", (self.VERSION,))
            elif version == 1:
                self._add_v3_columns()
                self.connection.execute("UPDATE reconciliation_schema SET version=?", (self.VERSION,))
            elif version == 2:
                self._add_v3_columns()
                self.connection.execute("UPDATE reconciliation_schema SET version=?", (self.VERSION,))
            elif version != self.VERSION:
                raise ReconciliationError("unsupported reconciliation SQLite schema")
            self._validate_schema()

    def _columns(self, table: str) -> set[str]:
        return {row[1] for row in self.connection.execute("PRAGMA table_info(" + table + ")")}

    def _add_column(self, table: str, definition: str) -> None:
        name = definition.split()[0]
        if name not in self._columns(table):
            self.connection.execute("ALTER TABLE " + table + " ADD COLUMN " + definition)

    def _add_v3_columns(self) -> None:
        self._add_column("member_reconciliation", "enrichment_status TEXT NOT NULL DEFAULT 'complete'")
        self._add_column("member_reconciliation", "enrichment_reason TEXT")
        self._add_column("member_reconciliation", "pending_payload TEXT")
        self._add_column("member_reconciliation", "pending_payload_hash TEXT")

    def _validate_schema(self) -> None:
        expected = {
            "member_reconciliation": {"member_iri", "member_code", "identity_hash", "state", "method", "evidence_json", "service_errors_json", "review_hash", "review_applied", "wikidata_iri", "wikipedia_iri", "dbpedia_iri", "checked_at", "next_recheck_at", "publication_state", "published_links_hash", "error", "enrichment_status", "enrichment_reason", "pending_payload", "pending_payload_hash"},
            "reconciliation_attempt": {"attempt_id", "member_iri", "attempted_at", "identity_hash", "method", "state", "evidence_json", "errors_json", "review_hash", "review_snapshot_json", "review_applied", "wikidata_iri", "wikipedia_iri", "dbpedia_iri"},
            "publication_attempt": {"publication_id", "member_iri", "attempted_at", "payload_hash", "result", "error"},
        }
        for table, columns in expected.items():
            if not columns <= self._columns(table):
                raise ReconciliationError("malformed reconciliation SQLite schema: " + table)

    def get(self, member_iri: str): return self.connection.execute("SELECT * FROM member_reconciliation WHERE member_iri=?", (member_iri,)).fetchone()
    def is_due(self, row, review_hash: str) -> bool:
        return row["publication_state"] != "clean" or row["next_recheck_at"] <= _now() or row["review_hash"] != review_hash

    def save(self, member_iri: str, code: str, identity_hash: str, resolution: Resolution,
             review_hash: str, review_snapshot: dict | None, payload: str | None, *, dirty: bool,
             error: str | None = None) -> None:
        if resolution.state not in STATES: raise ValueError("invalid reconciliation state")
        days = 7 if resolution.state in {"pending", "ambiguous"} else 90
        with self.connection:
            self.connection.execute("""INSERT INTO member_reconciliation
              (member_iri,member_code,identity_hash,state,method,evidence_json,service_errors_json,review_hash,review_applied,wikidata_iri,wikipedia_iri,dbpedia_iri,checked_at,next_recheck_at,publication_state,error,enrichment_status,enrichment_reason,pending_payload,pending_payload_hash)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(member_iri) DO UPDATE SET member_code=excluded.member_code,identity_hash=excluded.identity_hash,state=excluded.state,method=excluded.method,evidence_json=excluded.evidence_json,service_errors_json=excluded.service_errors_json,review_hash=excluded.review_hash,review_applied=excluded.review_applied,wikidata_iri=excluded.wikidata_iri,wikipedia_iri=excluded.wikipedia_iri,dbpedia_iri=excluded.dbpedia_iri,checked_at=excluded.checked_at,next_recheck_at=excluded.next_recheck_at,publication_state=excluded.publication_state,error=excluded.error,enrichment_status=excluded.enrichment_status,enrichment_reason=excluded.enrichment_reason,pending_payload=excluded.pending_payload,pending_payload_hash=excluded.pending_payload_hash""",
              (member_iri, code, identity_hash, resolution.state, resolution.method, _json(resolution.evidence), _json(resolution.evidence.get("errors", [])), review_hash, int(resolution.review_applied), resolution.wikidata, resolution.wikipedia, resolution.dbpedia, _now(), (datetime.now(timezone.utc)+timedelta(days=7 if resolution.evidence.get("errors") or resolution.enrichment_status != "complete" else days)).replace(microsecond=0).isoformat(), "dirty" if dirty else "clean", error, resolution.enrichment_status, resolution.enrichment_reason, payload if dirty else None, _hash(payload) if dirty and payload is not None else None))
            self.connection.execute("""INSERT INTO reconciliation_attempt
              (member_iri,attempted_at,identity_hash,method,state,evidence_json,errors_json,review_hash,review_snapshot_json,review_applied,wikidata_iri,wikipedia_iri,dbpedia_iri)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (member_iri, _now(), identity_hash, resolution.method, resolution.state, _json(resolution.evidence), _json(resolution.evidence.get("errors", [])), review_hash, _json(review_snapshot) if review_snapshot else None, int(resolution.review_applied), resolution.wikidata, resolution.wikipedia, resolution.dbpedia))

    def mark_published(self, member_iri: str, links_hash: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE member_reconciliation SET publication_state='clean', published_links_hash=?, pending_payload=NULL, pending_payload_hash=NULL, error=NULL WHERE member_iri=?", (links_hash, member_iri))

    def publication_result(self, member_iri: str, payload_hash: str, result: str, error: str | None = None) -> None:
        with self.connection:
            self.connection.execute("INSERT INTO publication_attempt (member_iri,attempted_at,payload_hash,result,error) VALUES (?,?,?,?,?)", (member_iri, _now(), payload_hash, result, error))
            if error:
                self.connection.execute("UPDATE member_reconciliation SET error=? WHERE member_iri=?", (error, member_iri))

    def close(self): self.connection.close()


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
            value = binding.get("value") if isinstance(binding, dict) else None
            if not isinstance(binding, dict) or binding.get("type") != "uri" or not _valid_iri(value, WIKIDATA):
                raise ReconciliationError("invalid Wikidata SPARQL item binding")
            qids.append(value.rsplit("/", 1)[-1])
        return qids
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


def links_graph(member: dict, resolution: Resolution) -> Graph:
    member_graph_iri(member)
    graph = Graph(); subject = URIRef(member["uri"])
    if resolution.state != "accepted": return graph
    if resolution.wikidata: graph.add((subject, OWL.sameAs, URIRef(resolution.wikidata)))
    if resolution.dbpedia: graph.add((subject, OWL.sameAs, URIRef(resolution.dbpedia)))
    if resolution.wikipedia: graph.add((subject, FOAF.isPrimaryTopicOf, URIRef(resolution.wikipedia)))
    permitted = {(OWL.sameAs, WIKIDATA), (OWL.sameAs, DBPEDIA), (FOAF.isPrimaryTopicOf, WIKIPEDIA)}
    if any(not isinstance(s, URIRef) or not isinstance(p, URIRef) or not isinstance(o, URIRef) or s != subject or not any(p == predicate and _valid_iri(str(o), prefix) for predicate, prefix in permitted) for s,p,o in graph):
        raise ValueError("external graph boundary violation")
    return graph


def verify_external_links_competency(client, member: dict, graph: Graph) -> None:
    """Post-load exact graph gate, including the valid empty-graph case."""
    graph_iri, member_iri = external_graph_iri(member), member["uri"]
    query = "SELECT ?s ?p ?o WHERE { GRAPH <%s> { ?s ?p ?o } }" % graph_iri
    rows = client.query(query)
    actual = set()
    for row in rows:
        try:
            terms = (row["s"], row["p"], row["o"])
            if any(term.get("type") != "uri" or not isinstance(term.get("value"), str) for term in terms):
                raise ReconciliationError("external-links competency returned a non-IRI term")
            actual.add(tuple(term["value"] for term in terms))
        except (KeyError, AttributeError) as error:
            raise ReconciliationError("malformed external-links competency response") from error
    expected = {(str(s), str(p), str(o)) for s, p, o in graph}
    if actual != expected: raise ReconciliationError("external-links post-load competency verification failed")


def reconcile_records(records: list[dict], store: ReconciliationStore, review: dict[str, dict], review_hash: str, wikidata_client, dbpedia_client, *, all_records=False, publish=None, competency_client=None) -> list[tuple[dict, Resolution, Graph]]:
    codes = {wrapper.get("member", {}).get("memberCode") for wrapper in records}
    stale = sorted(code for code in review if code not in codes)
    if stale: raise ReviewError("review decisions do not match current Members input: " + ", ".join(stale))
    if publish is not None and competency_client is None:
        raise ReconciliationError("external graph publication requires a competency client")
    results=[]
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("member"), dict): raise ValueError("each Members record must contain a member object")
        member = wrapper["member"]
        member_graph_iri(member)
        iri = member["uri"]
        fingerprint = _hash({"memberCode":member.get("memberCode")})
        old = store.get(iri)
        identity_changed = old is not None and old["identity_hash"] != fingerprint
        selected = all_records or old is None or identity_changed or (old is not None and store.is_due(old, review_hash))
        if not selected: continue
        if (not all_records and old is not None and old["publication_state"] == "dirty"
                and old["identity_hash"] == fingerprint and old["review_hash"] == review_hash
                and old["pending_payload"] is not None):
            payload = old["pending_payload"]
            graph = Graph().parse(data=payload, format="nt")
            resolution = Resolution(old["state"], old["method"], json.loads(old["evidence_json"]), old["wikidata_iri"], old["wikipedia_iri"], old["dbpedia_iri"], bool(old["review_applied"]), old["enrichment_status"], old["enrichment_reason"])
            try:
                publish.replace(external_graph_iri(member), payload, content_type="application/n-triples") if publish is not None else None
                if publish is not None:
                    verify_external_links_competency(competency_client, member, graph)
                    store.publication_result(iri, old["pending_payload_hash"], "success")
                    store.mark_published(iri, old["pending_payload_hash"])
            except Exception as error:
                store.publication_result(iri, old["pending_payload_hash"], "failure", str(error))
                raise
            results.append((member, resolution, graph))
            continue
        result = resolve(member, review, wikidata_client, dbpedia_client); graph = links_graph(member, result)
        payload = ntriples(graph)
        payload_hash = _hash(payload)
        unresolved_primary = result.state in {"pending", "ambiguous"}
        explicit_rejection = result.state == "rejected" and result.review_applied
        needs_publication = (not unresolved_primary and (all_records or old is None or (old is not None and old["publication_state"] != "clean") or (old is not None and old["published_links_hash"] != payload_hash))) or explicit_rejection
        # The state change and audit attempt are committed before a PUT.  If the
        # process dies after this point, the dirty row is selected and retried.
        store.save(iri, member["memberCode"], fingerprint, result, review_hash, review.get(member["memberCode"]), payload, dirty=needs_publication)
        if publish is not None and needs_publication:
            try:
                publish.replace(external_graph_iri(member), payload, content_type="application/n-triples")
                verify_external_links_competency(competency_client, member, graph)
                store.publication_result(iri, payload_hash, "success")
                store.mark_published(iri, payload_hash)
            except Exception as error:
                store.publication_result(iri, payload_hash, "failure", str(error))
                raise
        results.append((member,result,graph))
    return results
