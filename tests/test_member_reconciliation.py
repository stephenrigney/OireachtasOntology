import json
from pathlib import Path

import pytest
from rdflib.namespace import FOAF, OWL

from oireachtas_etl.reconciliation import (ReconciliationStore, external_graph_iri,
    links_graph, load_review, reconcile_records, resolve)

ROOT = Path(__file__).resolve().parents[1]
MEMBER = json.loads((ROOT / "data/api_examples/member.json").read_text())["member"]


def _create_v3_reconciliation_database(path, payload, payload_hash):
    import sqlite3
    from oireachtas_etl.reconciliation import _hash

    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE reconciliation_schema (version INTEGER NOT NULL)")
    connection.execute("INSERT INTO reconciliation_schema VALUES (3)")
    connection.execute("""CREATE TABLE member_reconciliation (
      member_iri TEXT PRIMARY KEY, member_code TEXT NOT NULL UNIQUE, identity_hash TEXT NOT NULL,
      state TEXT NOT NULL CHECK(state IN ('accepted','rejected','ambiguous','pending')),
      method TEXT NOT NULL, evidence_json TEXT NOT NULL, service_errors_json TEXT NOT NULL,
      review_hash TEXT, review_applied INTEGER NOT NULL DEFAULT 0,
      wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT,
      checked_at TEXT NOT NULL, next_recheck_at TEXT NOT NULL,
      publication_state TEXT NOT NULL DEFAULT 'clean', published_links_hash TEXT, error TEXT,
      enrichment_status TEXT NOT NULL DEFAULT 'complete', enrichment_reason TEXT,
      pending_payload TEXT, pending_payload_hash TEXT)""")
    fingerprint = _hash({"memberCode": MEMBER["memberCode"]})
    connection.execute("""INSERT INTO member_reconciliation
      (member_iri,member_code,identity_hash,state,method,evidence_json,service_errors_json,
       review_hash,review_applied,wikidata_iri,checked_at,next_recheck_at,publication_state,
       published_links_hash,enrichment_status,pending_payload,pending_payload_hash)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (MEMBER["uri"], MEMBER["memberCode"], fingerprint, "accepted", "manual-review",
       '{"wikidata":"https://www.wikidata.org/entity/Q1"}', "[]", "review-v3", 1,
       "https://www.wikidata.org/entity/Q1", "2026-01-01T00:00:00+00:00",
       "2026-02-01T00:00:00+00:00", "dirty", "previous", "complete", payload, payload_hash))
    connection.execute("""CREATE TABLE reconciliation_attempt (
      attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, member_iri TEXT NOT NULL,
      attempted_at TEXT NOT NULL, identity_hash TEXT NOT NULL, method TEXT NOT NULL,
      state TEXT NOT NULL, evidence_json TEXT NOT NULL, errors_json TEXT NOT NULL,
      review_hash TEXT NOT NULL, review_snapshot_json TEXT, review_applied INTEGER NOT NULL,
      wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT)""")
    connection.execute("""INSERT INTO reconciliation_attempt VALUES
      (7,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (MEMBER["uri"], "2026-01-01T00:00:00+00:00", "history-v3", "manual-review",
       "accepted", '{"qid":"Q1"}', "[]", "review-v3", '{"status":"accepted"}', 1,
       "https://www.wikidata.org/entity/Q1", None, None))
    connection.execute("""CREATE TABLE publication_attempt (
      publication_id INTEGER PRIMARY KEY AUTOINCREMENT, member_iri TEXT NOT NULL,
      attempted_at TEXT NOT NULL, payload_hash TEXT NOT NULL, result TEXT NOT NULL, error TEXT)""")
    connection.execute("""INSERT INTO publication_attempt VALUES (9,?,?,?,?,?)""",
      (MEMBER["uri"], "2026-01-01T00:00:00+00:00", _hash(payload), "failure", "interrupted"))
    connection.commit()
    connection.close()


def _sqlite_database_snapshot(path):
    import sqlite3

    with sqlite3.connect(path) as connection:
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        ).fetchall()
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )]
        rows = {
            table: connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid').fetchall()
            for table in tables
        }
    return schema, rows


class WD:
    def __init__(self, candidates, entity=None): self.candidates, self.value = candidates, entity or {"entities":{"Q1":{"sitelinks":{"enwiki":{"title":"Example Person"}}}}}
    def lookup_member_code(self, code): return self.candidates
    def entity(self, qid): return self.value
class DB:
    def __init__(self, values=None): self.values=[] if values is None else values
    def resolve_wikidata(self, qid): return self.values

def test_unique_exact_identity_derives_only_permitted_links_and_graph():
    outcome = resolve(MEMBER, {}, WD(["Q1"]), DB([{"iri":"https://dbpedia.org/resource/Example_Person", "is_person":True}]))
    graph = links_graph(MEMBER, outcome)
    assert outcome.state == "accepted" and outcome.method == "wikidata-p4690-exact"
    assert (None, OWL.sameAs, None) in graph and (None, FOAF.isPrimaryTopicOf, None) in graph
    assert external_graph_iri(MEMBER).endswith("/external-links")

def test_ambiguous_rejected_and_manual_override_have_no_or_correct_links():
    assert resolve(MEMBER, {}, WD(["Q1", "Q2"]), DB()).state == "ambiguous"
    assert len(links_graph(MEMBER, resolve(MEMBER, {MEMBER["memberCode"]:{"status":"rejected"}}, WD(["Q1"]), DB()))) == 0
    accepted = resolve(MEMBER, {MEMBER["memberCode"]:{"status":"accepted","wikidata":"Q2"}}, WD(["Q1", "Q3"]), DB())
    assert accepted.wikidata.endswith("Q2") and accepted.review_applied

def test_store_persists_and_due_selection_and_clear_publication(tmp_path):
    review = tmp_path / "review.json"; review.write_text('{"version":1,"decisions":{}}')
    decisions, digest = load_review(review); store = ReconciliationStore(tmp_path / "state.sqlite")
    published=[]
    class Publisher:
        def replace(self, *args, **kwargs): published.append(args); self.payload = args[1]
    class Competency:
        def __init__(self, publisher): self.publisher = publisher
        def query(self, query):
            from rdflib import Graph
            graph = Graph().parse(data=self.publisher.payload, format="nt")
            return [{"s":{"type":"uri","value":str(s)}, "p":{"type":"uri","value":str(p)}, "o":{"type":"uri","value":str(o)}} for s,p,o in graph]
    try:
        publisher = Publisher()
        first = reconcile_records([{"member":MEMBER}], store, decisions, digest, WD(["Q1"]), DB(), all_records=True, publish=publisher, competency_client=Competency(publisher))
        assert first[0][1].state == "accepted" and published
        # A reviewed rejection replaces the owned graph with an empty payload.
        decisions = {MEMBER["memberCode"]:{"status":"rejected"}}
        publisher = Publisher()
        reconcile_records([{"member":MEMBER}], store, decisions, "changed", WD(["Q1"]), DB(), publish=publisher, competency_client=Competency(publisher))
        assert published[-1][1] == ""
    finally: store.close()

def test_offline_cli_writes_deterministic_named_graph_output(tmp_path):
    from oireachtas_etl.cli import main
    responses = {"wikidata":{"p4690":{MEMBER["memberCode"]:["Q1"]}, "entities":{"Q1":{"entities":{"Q1":{"sitelinks":{"enwiki":{"title":"Example Person"}}}}}}}, "dbpedia":{"by_wikidata":{"Q1":[]}}}
    fixture = ROOT / "data/api_examples/member.json"; response_file = tmp_path / "responses.json"; response_file.write_text(json.dumps(responses))
    review = tmp_path / "review.json"; review.write_text('{"version":1,"decisions":{}}')
    output, state = tmp_path / "links.nq", tmp_path / "state.sqlite"
    arguments = ["reconcile", "members", "--fixture", str(fixture), "--responses-file", str(response_file), "--offline", "--all", "--review-file", str(review), "--reconciliation-state-file", str(state), "--output-nq", str(output)]
    assert main(arguments) == 0
    first = output.read_text()
    assert "external-links" in first and "wikidata.org/entity/Q1" in first
    assert main(arguments) == 0 and output.read_text() == first

def test_malformed_and_service_failure_are_pending_but_manual_acceptance_survives_lookup_outage():
    assert resolve(MEMBER, {}, WD(["not-a-qid"]), DB()).state == "pending"
    assert resolve(MEMBER, {}, WD(["Q1"]), DB({"not":"a list"})).evidence["errors"]
    class Down:
        def lookup_member_code(self, code): raise OSError("down")
        def entity(self, qid): return {"entities":{"Q2":{}}}
    outcome = resolve(MEMBER, {MEMBER["memberCode"]:{"status":"accepted","wikidata":"Q2"}}, Down(), DB())
    assert outcome.state == "accepted" and outcome.wikidata.endswith("Q2") and outcome.review_applied

def test_dirty_publication_retries_and_attempt_audit_preserves_review(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    try:
        class Broken:
            def replace(self, *args, **kwargs): raise RuntimeError("put failed")
        with __import__("pytest").raises(RuntimeError):
            reconcile_records([{"member": MEMBER}], store, {}, "review", WD(["Q1"]), DB(), all_records=True, publish=Broken(), competency_client=object())
        assert store.get(MEMBER["uri"])["publication_state"] == "dirty"
        calls=[]
        class Good:
            def replace(self, *args, **kwargs): calls.append(args); self.payload = args[1]
        class Gate:
            def __init__(self, loader): self.loader=loader
            def query(self, query):
                from rdflib import Graph
                return [{"s":{"type":"uri","value":str(s)}, "p":{"type":"uri","value":str(p)}, "o":{"type":"uri","value":str(o)}} for s,p,o in Graph().parse(data=self.loader.payload, format="nt")]
        good = Good()
        reconcile_records([{"member": MEMBER}], store, {}, "review", WD(["Q1"]), DB(), publish=good, competency_client=Gate(good))
        assert calls and store.get(MEMBER["uri"])["publication_state"] == "clean"
        attempts = store.connection.execute("SELECT identity_hash, review_hash, evidence_json FROM reconciliation_attempt").fetchall()
        publications = store.connection.execute("SELECT result FROM publication_attempt").fetchall()
        assert len(attempts) == 1 and attempts[0][1] == "review" and [row[0] for row in publications] == ["failure", "success"]
    finally: store.close()

def test_whole_graph_competency_rejects_rogue_subject():
    from oireachtas_etl.reconciliation import ReconciliationError, verify_external_links_competency
    graph = links_graph(MEMBER, resolve(MEMBER, {}, WD(["Q1"]), DB()))
    class Rogue:
        def query(self, query):
            rows = [{"s":{"value":str(s)}, "p":{"value":str(p)}, "o":{"value":str(o)}} for s,p,o in graph]
            rows.append({"s":{"value":"https://evil.example/x"}, "p":{"value":str(OWL.sameAs)}, "o":{"value":"https://evil.example/y"}})
            return rows
    with __import__("pytest").raises(ReconciliationError, match="non-IRI"):
        verify_external_links_competency(Rogue(), MEMBER, graph)

def test_strict_review_rejects_invalid_and_stale_decisions_before_lookup(tmp_path):
    from oireachtas_etl.reconciliation import ReviewError
    bad = tmp_path / "bad.json"
    bad.write_text('{"version":1,"decisions":{"x":{"status":"rejected","wikidata":"Q1"}}}')
    with __import__("pytest").raises(ReviewError, match="must not contain"):
        load_review(bad)
    store = ReconciliationStore(tmp_path / "state.sqlite")
    class NoNetwork:
        def lookup_member_code(self, code): raise AssertionError("network called")
    try:
        with __import__("pytest").raises(ReviewError, match="do not match"):
            reconcile_records([{"member":MEMBER}], store, {"obsolete":{"status":"rejected"}}, "r", NoNetwork(), DB())
    finally: store.close()

def test_cli_api_mode_uses_paginated_members_input(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    from oireachtas_etl.api import ApiPage
    class Client:
        def __init__(self, *args, **kwargs): pass
        def harvest(self, *, limit):
            yield ApiPage(json.dumps({"results":[{"member":MEMBER}], "head":{"counts":{"memberCount":1}}}).encode(), 200, {})
            yield ApiPage(json.dumps({"results":[], "head":{"counts":{"memberCount":1}}}).encode(), 200, {})
    monkeypatch.setattr(cli, "ApiClient", Client)
    responses = tmp_path / "responses.json"; responses.write_text(json.dumps({"wikidata":{"p4690":{MEMBER["memberCode"]:[]},"entities":{}},"dbpedia":{"by_wikidata":{}}}))
    review = tmp_path / "review.json"; review.write_text('{"version":1,"decisions":{}}')
    assert cli.main(["reconcile", "members", "--responses-file", str(responses), "--review-file", str(review), "--reconciliation-state-file", str(tmp_path / "state.sqlite")]) == 1


def test_canonical_qids_and_strict_review_envelope(tmp_path):
    from oireachtas_etl.reconciliation import ReviewError, valid_qid
    assert valid_qid("Q1") and not valid_qid("Q01") and not valid_qid("Q0")
    for value in ('{"version":true,"decisions":{}}', '{"version":1,"decisions":{},"extra":1}', '[]'):
        path = tmp_path / "review.json"; path.write_text(value)
        with __import__("pytest").raises(ReviewError): load_review(path)


def test_schema_migrations_and_malformed_current_fail_closed(tmp_path):
    import sqlite3
    from oireachtas_etl.reconciliation import ReconciliationError, _hash
    from oireachtas_etl.serialization import ntriples
    payload = ntriples(links_graph(MEMBER, resolve(MEMBER, {}, WD(["Q1"]), DB())))
    for version in (1, 2, 3):
        path = tmp_path / (str(version) + ".sqlite")
        connection = sqlite3.connect(path)
        connection.execute("CREATE TABLE reconciliation_schema (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO reconciliation_schema VALUES (?)", (version,))
        columns = [
            "member_iri TEXT PRIMARY KEY", "member_code TEXT NOT NULL UNIQUE", "identity_hash TEXT NOT NULL",
            "state TEXT NOT NULL", "method TEXT NOT NULL", "evidence_json TEXT NOT NULL",
            "checked_at TEXT NOT NULL", "next_recheck_at TEXT NOT NULL",
            "publication_state TEXT NOT NULL DEFAULT 'clean'",
        ]
        if version >= 2:
            columns += ["review_hash TEXT", "review_applied INTEGER NOT NULL DEFAULT 0", "wikidata_iri TEXT",
                        "wikipedia_iri TEXT", "dbpedia_iri TEXT", "published_links_hash TEXT", "error TEXT",
                        "enrichment_status TEXT NOT NULL DEFAULT 'complete'", "enrichment_reason TEXT"]
        if version >= 3:
            columns += ["service_errors_json TEXT NOT NULL DEFAULT '[]'", "pending_payload TEXT", "pending_payload_hash TEXT"]
        connection.execute("CREATE TABLE member_reconciliation (" + ",".join(columns) + ")")
        insert_names = ["member_iri", "member_code", "identity_hash", "state", "method", "evidence_json",
                        "checked_at", "next_recheck_at", "publication_state"]
        fingerprint = _hash({"memberCode": MEMBER["memberCode"]})
        values = [MEMBER["uri"], MEMBER["memberCode"], fingerprint, "accepted", "manual-review",
                  '{"wikidata":"https://www.wikidata.org/entity/Q1"}', "2026-01-01T00:00:00+00:00",
                  "2026-02-01T00:00:00+00:00", "dirty"]
        if version >= 2:
            insert_names += ["review_hash", "review_applied", "wikidata_iri", "wikipedia_iri", "dbpedia_iri",
                             "published_links_hash", "error", "enrichment_status", "enrichment_reason"]
            values += ["review-v" + str(version), 1, "https://www.wikidata.org/entity/Q1", None, None,
                       "previous", None, "complete", None]
        if version >= 3:
            insert_names += ["service_errors_json", "pending_payload", "pending_payload_hash"]
            values += ["[]", payload, _hash(payload)]
        connection.execute("INSERT INTO member_reconciliation (" + ",".join(insert_names) + ") VALUES (" + ",".join("?" for _ in values) + ")", values)
        connection.execute("""CREATE TABLE reconciliation_attempt (
          attempt_id INTEGER PRIMARY KEY, member_iri TEXT NOT NULL, attempted_at TEXT NOT NULL,
          identity_hash TEXT NOT NULL, method TEXT NOT NULL, state TEXT NOT NULL,
          evidence_json TEXT NOT NULL, errors_json TEXT NOT NULL, review_hash TEXT NOT NULL,
          review_snapshot_json TEXT, review_applied INTEGER NOT NULL,
          wikidata_iri TEXT, wikipedia_iri TEXT, dbpedia_iri TEXT)""")
        connection.execute("INSERT INTO reconciliation_attempt VALUES (7,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (MEMBER["uri"], "2026-01-01T00:00:00+00:00", "history-v" + str(version),
                            "manual-review", "accepted", '{"qid":"Q1"}', "[]", "review-v" + str(version),
                            '{"status":"accepted"}', 1, "https://www.wikidata.org/entity/Q1", None, None))
        connection.execute("""CREATE TABLE publication_attempt (
          publication_id INTEGER PRIMARY KEY, member_iri TEXT NOT NULL, attempted_at TEXT NOT NULL,
          payload_hash TEXT NOT NULL, result TEXT NOT NULL, error TEXT)""")
        connection.execute("INSERT INTO publication_attempt VALUES (9,?,?,?,?,?)",
                           (MEMBER["uri"], "2026-01-01T00:00:00+00:00", _hash(payload), "failure", "interrupted"))
        connection.commit(); connection.close()
        migrated = ReconciliationStore(path)
        assert migrated.connection.execute("SELECT version FROM reconciliation_schema").fetchone()[0] == 4
        row = migrated.get_record("member", MEMBER["uri"])
        assert row["identity_hash"] == fingerprint
        assert migrated.connection.execute("SELECT attempt_id,identity_hash FROM reconciliation_attempt").fetchall()[0][:] == (7, "history-v" + str(version))
        assert migrated.connection.execute("SELECT publication_id,result,error FROM publication_attempt").fetchall()[0][:] == (9, "failure", "interrupted")
        assert migrated.connection.execute("SELECT member_code FROM member_reconciliation").fetchone()[0] == MEMBER["memberCode"]
        if version < 3:
            # v1/v2 did not store a replay payload/hash, so migration must not
            # manufacture a dirty graph identity from their state row.
            assert row["pending_payload"] is None
            assert row["pending_payload_hash"] is None
            assert row["pending_graph_iri"] is None
            assert row["publication_state"] == "dirty"
        else:
            assert row["pending_payload"] == payload and row["pending_payload_hash"] == _hash(payload)
            assert row["pending_graph_iri"] == external_graph_iri(MEMBER)
            class Publisher:
                def replace(self, graph_iri, content, **kwargs): self.graph_iri, self.payload = graph_iri, content
            class Gate:
                def __init__(self, publisher): self.publisher = publisher
                def query(self, query):
                    from rdflib import Graph
                    graph = Graph().parse(data=self.publisher.payload, format="nt")
                    return [{"s":{"type":"uri","value":str(s)}, "p":{"type":"uri","value":str(p)}, "o":{"type":"uri","value":str(o)}} for s,p,o in graph]
            class NoLookup:
                def lookup_member_code(self, code): raise AssertionError("migrated dirty payload must replay before lookup")
            publisher = Publisher()
            replay = reconcile_records([{"member": MEMBER}], migrated, {}, "review-v3", NoLookup(), DB(),
                                       publish=publisher, competency_client=Gate(publisher))
            assert publisher.graph_iri == external_graph_iri(MEMBER) and publisher.payload == payload
            assert replay[0][1].state == "accepted" and migrated.get(MEMBER["uri"])["publication_state"] == "clean"
        migrated.close()
    path = tmp_path / "bad.sqlite"; connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE reconciliation_schema (version INTEGER NOT NULL)"); connection.execute("INSERT INTO reconciliation_schema VALUES (3)"); connection.commit(); connection.close()
    with __import__("pytest").raises(ReconciliationError, match="malformed"):
        ReconciliationStore(path)
    path = tmp_path / "unknown.sqlite"; connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE reconciliation_schema (version INTEGER NOT NULL)"); connection.execute("INSERT INTO reconciliation_schema VALUES (99)"); connection.commit(); connection.close()
    with __import__("pytest").raises(ReconciliationError, match="unsupported"):
        ReconciliationStore(path)


@pytest.mark.parametrize("corruption", ["missing_hash", "corrupt_hash", "changed_payload"])
def test_v3_dirty_payload_hash_corruption_fails_without_migration_or_put(tmp_path, corruption):
    import sqlite3
    from rdflib import Graph
    from oireachtas_etl.reconciliation import ReconciliationError, _hash
    from oireachtas_etl.serialization import ntriples

    payload = ntriples(links_graph(MEMBER, resolve(MEMBER, {}, WD(["Q1"]), DB())))
    path = tmp_path / (corruption + ".sqlite")
    _create_v3_reconciliation_database(path, payload, _hash(payload))
    with sqlite3.connect(path) as connection:
        if corruption == "missing_hash":
            connection.execute("UPDATE member_reconciliation SET pending_payload_hash=NULL")
        elif corruption == "corrupt_hash":
            connection.execute("UPDATE member_reconciliation SET pending_payload_hash='corrupt'")
        else:
            # Keep the stored v3 hash while changing the pending payload.
            connection.execute("UPDATE member_reconciliation SET pending_payload=?", (payload + "\n# tampered\n",))
    before = _sqlite_database_snapshot(path)

    class Publisher:
        def __init__(self): self.calls = []; self.payload = None
        def replace(self, graph_iri, content, **kwargs):
            self.calls.append((graph_iri, content))
            self.payload = content

    class Gate:
        def query(self, query):
            graph = Graph().parse(data=publisher.payload, format="nt")
            return [{"s": {"type": "uri", "value": str(s)},
                     "p": {"type": "uri", "value": str(p)},
                     "o": {"type": "uri", "value": str(o)}} for s, p, o in graph]

    publisher = Publisher()
    store = None
    try:
        with pytest.raises(ReconciliationError, match="payload hash"):
            store = ReconciliationStore(path)
            reconcile_records([{"member": MEMBER}], store, {}, "review-v3", WD(["Q1"]), DB(),
                              publish=publisher, competency_client=Gate())
    finally:
        if store is not None:
            store.close()

    assert publisher.calls == []
    assert _sqlite_database_snapshot(path) == before


def test_unresolved_primary_preserves_existing_publication_and_dbpedia_ambiguity(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    try:
        accepted = resolve(MEMBER, {}, WD(["Q1"]), DB())
        payload = __import__("oireachtas_etl.serialization", fromlist=["ntriples"]).ntriples(links_graph(MEMBER, accepted))
        store.save(MEMBER["uri"], MEMBER["memberCode"], "same", accepted, "r", None, payload, dirty=False)
        store.connection.execute("UPDATE member_reconciliation SET published_links_hash=?, next_recheck_at=? WHERE member_iri=?", ("old", "2000-01-01T00:00:00+00:00", MEMBER["uri"])); store.connection.commit()
        calls=[]
        class Publisher:
            def replace(self, *args, **kwargs): calls.append(args)
        result = reconcile_records([{"member":MEMBER}], store, {}, "r", WD([]), DB(), publish=Publisher(), competency_client=object())
        assert result[0][1].state == "pending" and not calls and store.get(MEMBER["uri"])["publication_state"] == "clean"
        ambiguity = resolve(MEMBER, {}, WD(["Q1"]), DB([{"iri":"https://dbpedia.org/resource/A","is_person":True},{"iri":"https://dbpedia.org/resource/B","is_person":True}]))
        assert ambiguity.enrichment_status == "ambiguous" and ambiguity.dbpedia is None and ambiguity.wikidata
    finally: store.close()


def test_dirty_replay_uses_no_network_and_competency_failure_is_audited(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    try:
        resolution = resolve(MEMBER, {}, WD(["Q1"]), DB()); payload = __import__("oireachtas_etl.serialization", fromlist=["ntriples"]).ntriples(links_graph(MEMBER, resolution))
        store.save(MEMBER["uri"], MEMBER["memberCode"], __import__("hashlib").sha256(json.dumps({"memberCode":MEMBER["memberCode"]}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), resolution, "r", None, payload, dirty=True)
        class NoNetwork:
            def lookup_member_code(self, code): raise AssertionError("network")
        class Put:
            def replace(self, *args, **kwargs): self.payload=args[1]
        with __import__("pytest").raises(Exception):
            reconcile_records([{"member":MEMBER}], store, {}, "r", NoNetwork(), NoNetwork(), publish=Put(), competency_client=object())
        assert store.get(MEMBER["uri"])["publication_state"] == "dirty"
        assert store.connection.execute("SELECT result FROM publication_attempt").fetchone()[0] == "failure"
    finally: store.close()


def test_dirty_member_replays_before_changed_review_and_all_then_clears_reviewed_rejection(tmp_path):
    from oireachtas_etl.reconciliation import _hash
    from oireachtas_etl.serialization import ntriples
    store = ReconciliationStore(tmp_path / "state.sqlite")
    original = resolve(MEMBER, {}, WD(["Q1"]), DB())
    payload = ntriples(links_graph(MEMBER, original))
    fingerprint = _hash({"memberCode": MEMBER["memberCode"]})
    store.save(MEMBER["uri"], MEMBER["memberCode"], fingerprint, original, "old-review", None, payload, dirty=True)

    class Publisher:
        def __init__(self): self.calls=[]; self.payload=""
        def replace(self, graph_iri, value, **kwargs): self.calls.append((graph_iri, value)); self.payload=value
    class Gate:
        def __init__(self, publisher): self.publisher=publisher
        def query(self, query):
            from rdflib import Graph
            graph=Graph().parse(data=self.publisher.payload, format="nt")
            return [{"s":{"type":"uri","value":str(s)}, "p":{"type":"uri","value":str(p)}, "o":{"type":"uri","value":str(o)}} for s,p,o in graph]
    class NoLookup:
        def lookup_member_code(self, code): raise AssertionError("review rejection must not look up")

    try:
        publisher=Publisher()
        result=reconcile_records([{"member":MEMBER}], store, {MEMBER["memberCode"]:{"status":"rejected"}},
                                 "new-review", NoLookup(), DB(), all_records=True,
                                 publish=publisher, competency_client=Gate(publisher))
        assert [value for _, value in publisher.calls] == [payload, ""]
        assert result[0][1].state == "rejected" and len(result[0][2]) == 0
        assert store.get(MEMBER["uri"])["publication_state"] == "clean"
    finally:
        store.close()


def test_stale_member_review_fails_before_dirty_replay(tmp_path):
    from rdflib import Graph
    from oireachtas_etl.reconciliation import ReviewError, _hash
    from oireachtas_etl.serialization import ntriples

    store = ReconciliationStore(tmp_path / "state.sqlite")
    original = resolve(MEMBER, {}, WD(["Q1"]), DB())
    payload = ntriples(links_graph(MEMBER, original))
    store.save(MEMBER["uri"], MEMBER["memberCode"], _hash({"memberCode": MEMBER["memberCode"]}),
               original, "valid-review", None, payload, dirty=True)
    before = dict(store.get(MEMBER["uri"]))
    attempts_before = store.connection.execute("SELECT COUNT(*) FROM reconciliation_attempt").fetchone()[0]
    publications_before = store.connection.execute("SELECT COUNT(*) FROM publication_attempt").fetchone()[0]

    class Publisher:
        def __init__(self): self.calls = []; self.payload = ""
        def replace(self, graph_iri, value, **kwargs):
            self.calls.append((graph_iri, value))
            self.payload = value

    class Gate:
        def query(self, query):
            graph = Graph().parse(data=publisher.payload, format="nt")
            return [{"s": {"type": "uri", "value": str(s)},
                     "p": {"type": "uri", "value": str(p)},
                     "o": {"type": "uri", "value": str(o)}} for s, p, o in graph]

    class NoLookup:
        def lookup_member_code(self, code): raise AssertionError("stale review must fail before lookup")

    publisher = Publisher()
    try:
        with pytest.raises(ReviewError, match="do not match"):
            reconcile_records([{"member": MEMBER}], store, {"obsolete": {"status": "rejected"}},
                              "stale-review", NoLookup(), DB(), publish=publisher,
                              competency_client=Gate())
        assert publisher.calls == []
        assert dict(store.get(MEMBER["uri"])) == before
        assert store.get(MEMBER["uri"])["publication_state"] == "dirty"
        assert store.connection.execute("SELECT COUNT(*) FROM reconciliation_attempt").fetchone()[0] == attempts_before
        assert store.connection.execute("SELECT COUNT(*) FROM publication_attempt").fetchone()[0] == publications_before
    finally:
        store.close()


@__import__("pytest").mark.parametrize("tamper", ["hash", "boundary"])
def test_dirty_member_payload_hash_and_graph_boundary_are_checked_before_put(tmp_path, tamper):
    from rdflib import Graph
    from oireachtas_etl.reconciliation import ReconciliationError, _hash
    from oireachtas_etl.serialization import ntriples
    store = ReconciliationStore(tmp_path / "state.sqlite")
    resolution = resolve(MEMBER, {}, WD(["Q1"]), DB())
    payload = ntriples(links_graph(MEMBER, resolution))
    fingerprint = _hash({"memberCode": MEMBER["memberCode"]})
    store.save(MEMBER["uri"], MEMBER["memberCode"], fingerprint, resolution, "r", None, payload, dirty=True)
    calls=[]
    class Publisher:
        def replace(self, *args, **kwargs): calls.append(args)
    try:
        if tamper == "hash":
            store.connection.execute("UPDATE reconciliation_record SET pending_payload_hash='invalid' WHERE entity_kind='member' AND local_iri=?", (MEMBER["uri"],))
            match="payload or hash"
        else:
            malicious=ntriples(Graph().parse(data=f"<{MEMBER['uri']}> <https://evil.example/p> <https://evil.example/o> .", format="nt"))
            store.connection.execute("UPDATE reconciliation_record SET pending_payload=?,pending_payload_hash=? WHERE entity_kind='member' AND local_iri=?", (malicious, _hash(malicious), MEMBER["uri"]))
            match="boundary"
        store.connection.commit()
        with __import__("pytest").raises(ReconciliationError, match=match):
            reconcile_records([{"member":MEMBER}], store, {}, "r", WD(["Q2"]), DB(),
                              publish=Publisher(), competency_client=object())
        assert calls == []
    finally:
        store.close()


def test_member_manifest_contract_bump_republishes_unchanged_graph(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.transforms.members import member_graph_iri, source_hash
    wrapper = json.loads((ROOT / "data/api_examples/member.json").read_text())
    fixture = tmp_path / "member.json"; fixture.write_text(json.dumps(wrapper))
    identity = wrapper["member"]["uri"]
    manifest = tmp_path / "members-state.json"
    manifest.write_text(json.dumps({"version": 1, "members": {identity: {
        "source_hash": source_hash(wrapper["member"]), "published_hash": source_hash(wrapper["member"]),
        "graph_iri": member_graph_iri(wrapper["member"]), "contract_version": 1, "status": "clean"}}}))
    puts=[]
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, graph_iri, payload, **kwargs): puts.append((graph_iri, payload))
    class Client:
        def __init__(self, *args, **kwargs): pass
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", Client)
    monkeypatch.setattr(cli, "verify_member_competency", lambda *args, **kwargs: None)
    assert cli.main(["run", "members", "--fixture", str(fixture), "--state-file", str(manifest),
                     "--raw-dir", str(tmp_path / "raw"), "--fuseki-gsp-url", "https://example.test/gsp",
                     "--fuseki-sparql-url", "https://example.test/sparql"]) == 0
    result = json.loads(capsys.readouterr().out)
    saved = json.loads(manifest.read_text())["members"][identity]
    assert result["changed"] == [identity] and len(puts) == 1
    assert saved["published_hash"] == source_hash(wrapper["member"])
    assert saved["contract_version"] == 2 and saved["status"] == "clean"


def test_production_parsers_and_graph_gate_term_types(monkeypatch):
    from oireachtas_etl import reconciliation as module
    from oireachtas_etl.reconciliation import DbpediaClient, ReconciliationError, WikidataClient, verify_external_links_competency
    class Response:
        status=200
        def __init__(self, body): self.body=body
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *args): pass
    requests = []
    def wikidata_response(request, **kwargs):
        requests.append(request)
        return Response(b'{"results":{"bindings":[{"item":{"type":"uri","value":"http://www.wikidata.org/entity/Q1"}}]}}')
    monkeypatch.setattr(module, "urlopen", wikidata_response)
    assert WikidataClient().lookup_member_code("x") == ["Q1"]
    from urllib.parse import parse_qs, urlsplit
    query = parse_qs(urlsplit(requests[0].full_url).query)["query"][0]
    assert query == 'SELECT ?item WHERE { ?item wdt:P4690 "x" }'
    assert module.wikidata_iri("Q1") == "https://www.wikidata.org/entity/Q1"
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: Response(b'{"results":{"bindings":[{"person":{"type":"literal","value":"https://dbpedia.org/resource/X"}}]}}'))
    with __import__("pytest").raises(ReconciliationError): DbpediaClient().resolve_wikidata("Q1")
    graph = links_graph(MEMBER, resolve(MEMBER, {}, WD(["Q1"]), DB()))
    class LiteralGate:
        def query(self, query): return [{"s":{"type":"uri","value":MEMBER["uri"]},"p":{"type":"uri","value":str(OWL.sameAs)},"o":{"type":"literal","value":"https://www.wikidata.org/entity/Q1"}}]
    with __import__("pytest").raises(ReconciliationError): verify_external_links_competency(LiteralGate(), MEMBER, graph)


@pytest.mark.parametrize("value", [
    "http://wikidata.org/entity/Q1",
    "https://www.wikidata.org.evil.example/entity/Q1",
    "https://evil.example/entity/Q1",
    "https://www.wikidata.org:443/entity/Q1",
    "https://www.wikidata.org/entity/Q1/extra",
    "http://www.wikidata.org/entity/Q01",
])
def test_wikidata_member_sparql_rejects_noncanonical_binding_iris(monkeypatch, value):
    from oireachtas_etl import reconciliation as module
    from oireachtas_etl.reconciliation import ReconciliationError, WikidataClient

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({"results": {"bindings": [{
                "item": {"type": "uri", "value": value},
            }]}}).encode()

    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(ReconciliationError, match="item binding"):
        WikidataClient().lookup_member_code("x")


def test_offline_requires_complete_fixture_evidence_before_state(tmp_path):
    from oireachtas_etl.cli import main
    fixture = ROOT / "data/api_examples/member.json"
    review = tmp_path / "review.json"; review.write_text('{"version":1,"decisions":{"%s":{"status":"accepted","wikidata":"Q2"}}}' % MEMBER["memberCode"])
    state = tmp_path / "state.sqlite"
    with __import__("pytest").raises(ValueError, match="requires --fixture"):
        main(["reconcile", "members", "--offline"])
    responses = tmp_path / "responses.json"; responses.write_text(json.dumps({"wikidata":{"p4690":{MEMBER["memberCode"]:[]},"entities":{}},"dbpedia":{"by_wikidata":{}}}))
    with __import__("pytest").raises(ValueError, match="lacks downstream"):
        main(["reconcile", "members", "--offline", "--fixture", str(fixture), "--responses-file", str(responses), "--review-file", str(review), "--reconciliation-state-file", str(state)])
    assert not state.exists()
