import json
from pathlib import Path

from rdflib.namespace import FOAF, OWL

from oireachtas_etl.reconciliation import (ReconciliationStore, external_graph_iri,
    links_graph, load_review, reconcile_records, resolve)

ROOT = Path(__file__).resolve().parents[1]
MEMBER = json.loads((ROOT / "data/api_examples/member.json").read_text())["member"]

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
    from oireachtas_etl.reconciliation import ReconciliationError
    for version in (1, 2):
        path = tmp_path / (str(version) + ".sqlite")
        store = ReconciliationStore(path); store.connection.execute("UPDATE reconciliation_schema SET version=?", (version,)); store.connection.commit(); store.close()
        migrated = ReconciliationStore(path)
        assert migrated.connection.execute("SELECT version FROM reconciliation_schema").fetchone()[0] == 3
        migrated.close()
    path = tmp_path / "bad.sqlite"; connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE reconciliation_schema (version INTEGER NOT NULL)"); connection.execute("INSERT INTO reconciliation_schema VALUES (3)"); connection.commit(); connection.close()
    with __import__("pytest").raises(ReconciliationError, match="malformed"):
        ReconciliationStore(path)
    path = tmp_path / "unknown.sqlite"; connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE reconciliation_schema (version INTEGER NOT NULL)"); connection.execute("INSERT INTO reconciliation_schema VALUES (99)"); connection.commit(); connection.close()
    with __import__("pytest").raises(ReconciliationError, match="unsupported"):
        ReconciliationStore(path)


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


def test_production_parsers_and_graph_gate_term_types(monkeypatch):
    from oireachtas_etl import reconciliation as module
    from oireachtas_etl.reconciliation import DbpediaClient, ReconciliationError, WikidataClient, verify_external_links_competency
    class Response:
        status=200
        def __init__(self, body): self.body=body
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: Response(b'{"results":{"bindings":[{"item":{"type":"uri","value":"https://www.wikidata.org/entity/Q1"}}]}}'))
    assert WikidataClient().lookup_member_code("x") == ["Q1"]
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: Response(b'{"results":{"bindings":[{"person":{"type":"literal","value":"https://dbpedia.org/resource/X"}}]}}'))
    with __import__("pytest").raises(ReconciliationError): DbpediaClient().resolve_wikidata("Q1")
    graph = links_graph(MEMBER, resolve(MEMBER, {}, WD(["Q1"]), DB()))
    class LiteralGate:
        def query(self, query): return [{"s":{"type":"uri","value":MEMBER["uri"]},"p":{"type":"uri","value":str(OWL.sameAs)},"o":{"type":"literal","value":"https://www.wikidata.org/entity/Q1"}}]
    with __import__("pytest").raises(ReconciliationError): verify_external_links_competency(LiteralGate(), MEMBER, graph)


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
