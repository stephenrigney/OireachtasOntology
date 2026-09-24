import json
from pathlib import Path
from urllib.parse import quote

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

from oireachtas_etl.reconciliation import (
    ReconciliationError,
    ReconciliationStore,
    Resolution,
    ReviewError,
    _hash,
    deduplicate_party_records,
    load_party_review,
    party_external_graph_iri,
    party_links_graph,
    reconcile_party_records,
    resolve_party,
    verify_reconciliation_graph,
)
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.transforms.common import MEMBERS

ROOT = Path(__file__).resolve().parents[1]
PARTIES = json.loads((ROOT / "data/api_examples/parties.json").read_text())["results"]
PARTY = next(row for row in PARTIES if row["party"]["partyCode"] == "Fine_Gael")
INDEPENDENT = next(row for row in PARTIES if row["party"]["partyCode"] == "Independent")


def term_party(code="Fine_Gael", label="Fine Gael", house_code="dail", house_no="31", *, dates=None):
    house = {"uri": f"https://data.oireachtas.ie/ie/oireachtas/house/{house_code}/{house_no}",
             "houseCode": house_code, "houseNo": house_no}
    if dates is not None:
        house["dateRange"] = dates
    return {"party": {"uri": f"https://data.oireachtas.ie/ie/oireachtas/party/{house_code}/{house_no}/{quote(code, safe='_')}",
                       "partyCode": code, "showAs": label}, "house": house}


def candidate(qid="Q832321", label="Fine Gael", *, inception="1933"):
    return {"qid": qid, "labels": [label], "matched_on": [label], "types": ["Q7278"],
            "instance_types": ["Q7278"], "jurisdictions": ["Q27"],
            "inception": [inception] if inception else [], "dissolution": []}


class PartyWD:
    def __init__(self, candidates=None):
        self.candidates = [] if candidates is None else candidates
        self.calls = []

    def lookup_party_candidates(self, record):
        self.calls.append(record["party"]["uri"])
        return self.candidates


class Publisher:
    def __init__(self):
        self.calls = []
        self.graphs = {}

    def replace(self, graph_iri, payload, *, content_type):
        assert content_type == "application/n-triples"
        self.calls.append((graph_iri, payload))
        self.graphs[graph_iri] = payload


class Gate:
    def __init__(self, publisher):
        self.publisher = publisher

    def query(self, query):
        graph_iri = query.split("GRAPH <", 1)[1].split(">", 1)[0]
        graph = Graph().parse(data=self.publisher.graphs[graph_iri], format="nt")
        return [{"s": {"type": "uri", "value": str(s)},
                 "p": {"type": "uri", "value": str(p)},
                 "o": {"type": "uri", "value": str(o)}} for s, p, o in graph]


def review_file(path, decisions):
    path.write_text(json.dumps({"version": 1, "decisions": decisions}, sort_keys=True))
    return path


def test_party_graph_uses_approved_term_scoped_percent_encoded_iri():
    party = term_party("Sinn_Féin", "Sinn Féin", house_no="34")
    assert party_external_graph_iri(party) == (
        "https://data.oireachtas.ie/graph/party/dail/34/Sinn_F%C3%A9in/external-links"
    )
    assert party_external_graph_iri(PARTY).endswith("/party/dail/31/Fine_Gael/external-links")


def test_party_review_is_strict_version_one_and_uses_full_party_iri(tmp_path):
    local_iri = PARTY["party"]["uri"]
    path = review_file(tmp_path / "review.json", {local_iri: {"status": "accepted", "wikidata": "Q832321"}})
    decisions, digest = load_party_review(path)
    assert decisions[local_iri]["wikidata"] == "Q832321" and digest
    for content in (
        '{"version":true,"decisions":{}}',
        '{"version":1,"decisions":{"Fine_Gael":{"status":"rejected"}}}',
        json.dumps({"version": 1, "decisions": {local_iri: {"status": "accepted", "wikidata": "Q01"}}}),
        json.dumps({"version": 1, "decisions": {INDEPENDENT["party"]["uri"]: {"status": "rejected"}}}),
    ):
        path.write_text(content)
        with pytest.raises(ReviewError):
            load_party_review(path)


def test_party_candidates_are_evidence_only_and_historical_mismatch_is_retained():
    record = term_party(dates={"start": "2020-01-01", "end": "2024-12-31"})
    outcome = resolve_party(record, {}, PartyWD([candidate(inception="2030")]))
    graph = party_links_graph(record, outcome)
    assert outcome.state == "pending" and outcome.method == "wikidata-party-candidate-review"
    assert outcome.evidence["candidates"][0]["historical_conflicts"] == ["party-inception-after-house-term"]
    assert len(graph) == 0


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_wikidata_candidate_query_uses_party_context_and_parses_historical_evidence(monkeypatch, scheme):
    from urllib.parse import parse_qs, urlsplit
    from oireachtas_etl import reconciliation

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({"results": {"bindings": [{
                "item": {"type": "uri", "value": f"{scheme}://www.wikidata.org/entity/Q832321"},
                "label": {"type": "literal", "value": "Fine Gael", "xml:lang": "en"},
                "instanceType": {"type": "uri", "value": f"{scheme}://www.wikidata.org/entity/Q7278"},
                "jurisdiction": {"type": "uri", "value": f"{scheme}://www.wikidata.org/entity/Q27"},
                "inception": {"type": "literal", "value": "+1933-09-08T00:00:00Z"},
            }]}}).encode()

    requests = []
    def open_request(request, timeout):
        requests.append(request)
        return Response()
    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    candidates = reconciliation.WikidataClient().lookup_party_candidates(PARTY)
    query = parse_qs(urlsplit(requests[0].full_url).query)["query"][0]
    assert '"Fine Gael"' in query and "P31" in query and "P279" in query
    assert "P17" in query and "P1001" in query and "Q27" in query and "P571" in query and "P576" in query
    assert candidates[0]["qid"] == "Q832321" and candidates[0]["inception"] == ["1933-09-08"]
    outcome = resolve_party(PARTY, {}, PartyWD(candidates))
    assert outcome.state == "pending" and len(party_links_graph(PARTY, outcome)) == 0


@pytest.mark.parametrize(("field", "value"), [
    ("item", "http://wikidata.org/entity/Q832321"),
    ("item", "http://www.wikidata.org.evil.example/entity/Q832321"),
    ("item", "https://evil.example/entity/Q832321"),
    ("item", "https://www.wikidata.org:443/entity/Q832321"),
    ("item", "https://www.wikidata.org/entity/Q832321/extra"),
    ("item", "http://www.wikidata.org/entity/Q01"),
    ("instanceType", "http://www.wikidata.org.evil.example/entity/Q7278"),
    ("jurisdiction", "http://www.wikidata.org.evil.example/entity/Q27"),
])
def test_wikidata_party_sparql_rejects_noncanonical_binding_iris(monkeypatch, field, value):
    from oireachtas_etl import reconciliation

    row = {
        "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q832321"},
        "label": {"type": "literal", "value": "Fine Gael"},
        "instanceType": {"type": "uri", "value": "http://www.wikidata.org/entity/Q7278"},
        "jurisdiction": {"type": "uri", "value": "http://www.wikidata.org/entity/Q27"},
    }
    row[field] = {"type": "uri", "value": value}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return json.dumps({"results": {"bindings": [row]}}).encode()

    monkeypatch.setattr(reconciliation, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(ReconciliationError):
        reconciliation.WikidataClient().lookup_party_candidates(PARTY)


def test_party_review_rejection_and_candidate_history_remain_in_operational_evidence(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    local = PARTY["party"]["uri"]
    prior_candidate = {**candidate(), "historical_conflicts": ["party-dissolved-before-house-term"]}
    prior = Resolution("rejected", "manual-review", {"decision": {"status": "rejected"},
                                                         "previous_candidates": [prior_candidate]},
                       review_applied=True)
    try:
        store.save_record("party", local, "Fine_Gael", "fingerprint", prior, "review-rejected",
                          {"status": "rejected"}, "", party_external_graph_iri(PARTY), dirty=False)
        outcome = resolve_party(PARTY, {}, PartyWD([candidate()]), previous=store.get_record("party", local))
        assert outcome.evidence["previous_review_decision"] == {"status": "rejected"}
        assert outcome.evidence["previous_candidates"] == [prior_candidate]
    finally:
        store.close()


def test_only_reviewed_party_qid_emits_recognised_as_party_and_same_code_terms_are_isolated(tmp_path):
    first, second = term_party(house_no="31"), term_party(house_no="32")
    store = ReconciliationStore(tmp_path / "state.sqlite")
    try:
        decisions = {first["party"]["uri"]: {"status": "accepted", "wikidata": "Q832321"},
                     second["party"]["uri"]: {"status": "accepted", "wikidata": "Q12345"}}
        results = reconcile_party_records([first, second], store, decisions, "review", PartyWD(), all_records=True)
        assert len(results) == 2
        for record, outcome, graph in results:
            assert outcome.state == "accepted" and outcome.review_applied
            assert len(graph) == 1
            assert (URIRef(record["party"]["uri"]), MEMBERS.recognisedAsParty, URIRef(outcome.wikidata)) in graph
            assert not list(graph.triples((None, OWL.sameAs, None)))
            assert not list(graph.triples((None, URIRef("http://www.w3.org/ns/prov#specializationOf"), None)))
        rows = store.connection.execute("SELECT entity_kind,entity_key,COUNT(*) FROM reconciliation_record GROUP BY entity_kind,entity_key").fetchall()
        assert [(row[0], row[1], row[2]) for row in rows] == [("party", "Fine_Gael", 2)]
        assert party_external_graph_iri(first) != party_external_graph_iri(second)
    finally:
        store.close()


def test_independent_is_skipped_and_unresolved_candidate_or_outage_never_clears_link(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    publisher = Publisher()
    try:
        local = PARTY["party"]["uri"]
        accepted = {local: {"status": "accepted", "wikidata": "Q832321"}}
        first = reconcile_party_records([PARTY, INDEPENDENT], store, accepted, "accepted", PartyWD(),
                                        all_records=True, publish=publisher, competency_client=Gate(publisher))
        assert len(first) == 1 and publisher.calls
        assert len(Graph().parse(data=publisher.graphs[party_external_graph_iri(PARTY)], format="nt")) == 1
        before = list(publisher.calls)
        pending = reconcile_party_records([PARTY, INDEPENDENT], store, {}, "changed-review", PartyWD([]),
                                          publish=publisher, competency_client=Gate(publisher))
        assert len(pending) == 1 and pending[0][1].state == "pending"
        assert publisher.calls == before
        state = store.get_record("party", local)
        assert state["state"] == "pending" and state["publication_state"] == "clean"
        assert len(Graph().parse(data=publisher.graphs[party_external_graph_iri(PARTY)], format="nt")) == 1
    finally:
        store.close()


def test_party_dirty_replay_precedes_changed_review_source_and_all(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    local = PARTY["party"]["uri"]
    accepted = {local: {"status": "accepted", "wikidata": "Q832321"}}
    expected = ntriples(party_links_graph(PARTY, resolve_party(PARTY, accepted, PartyWD())))

    class Broken:
        def replace(self, *args, **kwargs):
            raise RuntimeError("simulated interrupted PUT")

    try:
        with pytest.raises(RuntimeError, match="interrupted"):
            reconcile_party_records([PARTY], store, accepted, "accepted", PartyWD(), all_records=True,
                                    publish=Broken(), competency_client=object())
        dirty = store.get_record("party", local)
        assert dirty["publication_state"] == "dirty" and dirty["pending_payload"] == expected

        changed_source = json.loads(json.dumps(PARTY))
        changed_source["party"]["showAs"] = "Fine Gael revised"
        publisher = Publisher()
        reject = {local: {"status": "rejected"}}
        calls_to_lookup = PartyWD()
        results = reconcile_party_records([changed_source], store, reject, "rejected", calls_to_lookup,
                                          all_records=True, publish=publisher, competency_client=Gate(publisher))
        graph_iri = party_external_graph_iri(PARTY)
        assert [call for call, _ in publisher.calls] == [graph_iri, graph_iri]
        assert publisher.calls[0][1] == expected
        assert publisher.calls[1][1] == ""
        assert not calls_to_lookup.calls
        assert results[0][1].state == "rejected" and len(results[0][2]) == 0
        assert store.get_record("party", local)["publication_state"] == "clean"
    finally:
        store.close()


def test_stale_party_review_fails_before_dirty_replay(tmp_path):
    local = PARTY["party"]["uri"]
    accepted = {local: {"status": "accepted", "wikidata": "Q832321"}}
    resolution = resolve_party(PARTY, accepted, PartyWD())
    payload = ntriples(party_links_graph(PARTY, resolution))
    store = ReconciliationStore(tmp_path / "state.sqlite")
    store.save_record("party", local, PARTY["party"]["partyCode"], "fingerprint", resolution,
                      "valid-review", accepted[local], payload, party_external_graph_iri(PARTY), dirty=True)
    before = dict(store.get_record("party", local))
    attempts_before = store.connection.execute("SELECT COUNT(*) FROM reconciliation_attempt").fetchone()[0]
    publications_before = store.connection.execute("SELECT COUNT(*) FROM publication_attempt").fetchone()[0]
    publisher = Publisher()

    class NoLookup:
        def lookup_party_candidates(self, record): raise AssertionError("stale review must fail before lookup")

    stale_key = term_party("Obsolete", "Obsolete")["party"]["uri"]
    try:
        with pytest.raises(ReviewError, match="do not match"):
            reconcile_party_records([PARTY], store, {stale_key: {"status": "rejected"}},
                                    "stale-review", NoLookup(), publish=publisher,
                                    competency_client=Gate(publisher))
        assert publisher.calls == []
        assert dict(store.get_record("party", local)) == before
        assert store.get_record("party", local)["publication_state"] == "dirty"
        assert store.connection.execute("SELECT COUNT(*) FROM reconciliation_attempt").fetchone()[0] == attempts_before
        assert store.connection.execute("SELECT COUNT(*) FROM publication_attempt").fetchone()[0] == publications_before
    finally:
        store.close()


@pytest.mark.parametrize("tamper", ["hash", "boundary"])
def test_dirty_party_payload_fails_closed_before_put(tmp_path, tamper):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    local = PARTY["party"]["uri"]
    accepted = {local: {"status": "accepted", "wikidata": "Q832321"}}

    class Broken:
        def replace(self, *args, **kwargs):
            raise AssertionError("invalid dirty data must not reach PUT")

    try:
        with pytest.raises(AssertionError):
            reconcile_party_records([PARTY], store, accepted, "r", PartyWD(), all_records=True,
                                    publish=Broken(), competency_client=object())
        if tamper == "hash":
            store.connection.execute("UPDATE reconciliation_record SET pending_payload_hash='wrong' WHERE entity_kind='party' AND local_iri=?", (local,))
            match = "payload or hash"
        else:
            malicious = ntriples(Graph().parse(data=f"<{local}> <https://evil.example/p> <https://evil.example/o> .", format="nt"))
            store.connection.execute("UPDATE reconciliation_record SET pending_payload=?,pending_payload_hash=? WHERE entity_kind='party' AND local_iri=?", (malicious, _hash(malicious), local))
            match = "boundary"
        store.connection.commit()
        with pytest.raises(ReconciliationError, match=match):
            reconcile_party_records([PARTY], store, accepted, "r", PartyWD(),
                                    publish=Broken(), competency_client=object())
    finally:
        store.close()


def test_party_inputs_deduplicate_identically_and_reject_conflicts_and_graph_collisions():
    assert len(deduplicate_party_records([PARTY, json.loads(json.dumps(PARTY))])) == 1
    conflict = json.loads(json.dumps(PARTY))
    conflict["party"]["showAs"] = "different label"
    with pytest.raises(ValueError, match="conflicting duplicate"):
        deduplicate_party_records([PARTY, conflict])
    encoded = term_party("Páirtí", "Páirtí")
    alias = json.loads(json.dumps(encoded))
    alias["party"]["uri"] = alias["party"]["uri"].replace("P%C3%A1irt%C3%AD", "Páirtí")
    assert alias["party"]["uri"] != encoded["party"]["uri"]
    with pytest.raises(ValueError, match="graph IRI collision"):
        deduplicate_party_records([encoded, alias])


def test_party_whole_graph_gate_rejects_extra_triples():
    graph = party_links_graph(PARTY, resolve_party(PARTY, {PARTY["party"]["uri"]: {"status": "accepted", "wikidata": "Q832321"}}, PartyWD()))

    class Rogue:
        def query(self, query):
            return [{"s": {"type": "uri", "value": str(s)}, "p": {"type": "uri", "value": str(p)}, "o": {"type": "uri", "value": str(o)}} for s, p, o in graph] + [
                {"s": {"type": "uri", "value": "https://evil.example/s"}, "p": {"type": "uri", "value": "https://evil.example/p"}, "o": {"type": "uri", "value": "https://evil.example/o"}}]

    with pytest.raises(ReconciliationError, match="whole-graph"):
        verify_reconciliation_graph(Rogue(), party_external_graph_iri(PARTY), graph)


def test_party_cli_offline_reviewed_run_is_deterministic_and_preflights_fixture(tmp_path, capsys):
    from oireachtas_etl.cli import main

    source = tmp_path / "parties.json"
    source.write_text(json.dumps([PARTY, INDEPENDENT]))
    responses = tmp_path / "responses.json"
    responses.write_text(json.dumps({"wikidata": {"party_candidates": {}}}))
    review = review_file(tmp_path / "review.json", {PARTY["party"]["uri"]: {"status": "accepted", "wikidata": "Q832321"}})
    output, state = tmp_path / "links.nq", tmp_path / "state.sqlite"
    args = ["reconcile", "parties", "--fixture", str(source), "--responses-file", str(responses), "--offline", "--all",
            "--review-file", str(review), "--reconciliation-state-file", str(state), "--output-nq", str(output)]
    assert main(args) == 0
    first = output.read_text()
    assert "graph/party/dail/31/Fine_Gael/external-links" in first
    assert "recognisedAsParty" in first and "owl#sameAs" not in first and "specializationOf" not in first
    assert main(args) == 0 and output.read_text() == first
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["excluded_independent"] == 1

    bad_responses = tmp_path / "bad-responses.json"
    bad_responses.write_text(json.dumps({"wikidata": {"party_candidates": {}}}))
    no_review = review_file(tmp_path / "no-review.json", {})
    no_state = tmp_path / "not-created.sqlite"
    with pytest.raises(ValueError, match="lacks valid Party candidate"):
        main(["reconcile", "parties", "--fixture", str(source), "--responses-file", str(bad_responses), "--offline",
              "--review-file", str(no_review), "--reconciliation-state-file", str(no_state)])
    assert not no_state.exists()
