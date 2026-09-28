"""Focused Phase 4.5 Tranche 3 institutional reconciliation coverage."""
import json
import re
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, URIRef
from rdflib.namespace import FOAF, OWL, RDFS

from oireachtas_etl.cli import main
from oireachtas_etl.config import HOUSES_GRAPH
from oireachtas_etl.reconciliation import (
    INSTITUTIONS,
    ReconciliationError,
    ReconciliationStore,
    ReviewError,
    WikidataClient,
    _hash,
    institution_external_graph_iri,
    institution_links_graph,
    load_institution_review,
    reconcile_institution_records,
    resolve_institution,
    verify_reconciliation_graph,
)
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.transforms.common import OIR
from oireachtas_etl.transforms.houses import transform_houses


ROOT = Path(__file__).resolve().parents[1]
OIREACHTAS = "https://data.oireachtas.ie/oireachtas"
DAIL = "https://data.oireachtas.ie/house/dail"
SEANAD = "https://data.oireachtas.ie/house/seanad"
WIKIDATA = "https://www.wikidata.org/entity/"
WIKIPEDIA_DAIL = "https://en.wikipedia.org/wiki/D%C3%A1il_%C3%89ireann"
LOCAL_IRIS = (OIREACHTAS, DAIL, SEANAD)


def institution(local_iri=DAIL):
    return {"institution": {"uri": local_iri}}


def candidate(
    local_iri=DAIL,
    *,
    qid="Q900001",
    labels=None,
    descriptions=None,
    matched_on=None,
    discovery_methods=None,
    entity_types=None,
    jurisdictions=None,
    relationships=None,
    negative_evidence=None,
):
    local_labels = INSTITUTIONS[local_iri]["labels"]
    label = local_labels[0]
    return {
        "qid": qid,
        "labels": list(labels if labels is not None else [label]),
        "descriptions": list(descriptions or []),
        "matched_on": list(matched_on if matched_on is not None else [label]),
        "discovery_methods": list(discovery_methods or ["exact-label"]),
        "positive_evidence": {
            "entity_types": list(entity_types or []),
            "jurisdictions": list(jurisdictions or []),
            "relationships": list(relationships or []),
            "official_sites": [],
            "inception": [],
            "dissolution": [],
        },
        "negative_evidence": list(negative_evidence or []),
    }


class Wikidata:
    def __init__(self, candidates=None, *, entities=None, error=None):
        self.candidates = [] if candidates is None else candidates
        self.entities = {} if entities is None else entities
        self.error = error
        self.lookup_calls = []
        self.entity_calls = []

    def lookup_institution_candidates(self, value):
        self.lookup_calls.append(value["uri"])
        if self.error is not None:
            raise self.error
        return self.candidates

    def entity(self, qid):
        self.entity_calls.append(qid)
        return self.entities[qid]


class NoLookup:
    def lookup_institution_candidates(self, value):
        raise AssertionError("reviewed institution must not perform candidate lookup")


class MemoryPublisher:
    def __init__(self, graphs=None):
        self.graphs = {} if graphs is None else dict(graphs)
        self.calls = []

    def replace(self, graph_iri, payload, *, content_type):
        assert content_type == "application/n-triples"
        self.calls.append((graph_iri, payload))
        self.graphs[graph_iri] = payload


class GraphGate:
    def __init__(self, publisher):
        self.publisher = publisher

    def query(self, query):
        graph_iri = re.search(r"GRAPH\s+<([^>]+)>", query).group(1)
        payload = self.publisher.graphs.get(graph_iri, "")
        graph = Graph().parse(data=payload, format="nt") if payload else Graph()
        return [
            {
                "s": {"type": "uri", "value": str(subject)},
                "p": {"type": "uri", "value": str(predicate)},
                "o": {"type": "uri", "value": str(object_)},
            }
            for subject, predicate, object_ in graph
        ]


def accepted_review(local_iri=DAIL, qid="Q651981", **extra):
    return {local_iri: {"status": "accepted", "wikidata": qid, **extra}}


def test_full_iri_review_and_exact_label_candidates_never_auto_accept(tmp_path):
    review_path = tmp_path / "institution-review.json"
    review_path.write_text(json.dumps({"version": 1, "decisions": accepted_review()}))
    decisions, digest = load_institution_review(review_path)
    assert decisions[DAIL]["wikidata"] == "Q651981" and digest

    # An exact label, the documented seed, or strong positive evidence are all
    # candidates for human review; none is itself an identity decision.
    exact = candidate(entity_types=[{"qid": "Q100", "label": "parliamentary chamber"}],
                      jurisdictions=[{"property": "P17", "qid": "Q27", "label": "Ireland"}])
    seeded = candidate(qid="Q651981", matched_on=[],
                       discovery_methods=["initial-review-candidate"])
    for raw in (exact, seeded):
        wd = Wikidata([raw])
        outcome = resolve_institution(institution(), {}, wd)
        graph = institution_links_graph(institution(), outcome)
        assert outcome.state == "pending" and not outcome.review_applied
        assert outcome.wikidata is None and len(graph) == 0

    # A label is not a review key; only the stable full local IRI is accepted.
    review_path.write_text(json.dumps({"version": 1, "decisions": {"Dáil Éireann": {"status": "rejected"}}}))
    with pytest.raises(ReviewError, match="full local IRIs"):
        load_institution_review(review_path)


@pytest.mark.parametrize(
    ("candidate_options", "expected_reason"),
    [
        ({"descriptions": ["Revolutionary parliament in Ireland"]}, "historical-predecessor"),
        ({"descriptions": ["Historical predecessor of Dáil Éireann"]}, "historical-predecessor"),
        (
            {"labels": ["Dáil Éireann", "33rd Dáil"], "matched_on": ["Dáil Éireann"]},
            "house-term-mismatch",
        ),
        (
            {"entity_types": [{"qid": "Q4167836", "label": "Wikimedia category"}]},
            "wrong-entity-level",
        ),
        (
            {"entity_types": [{"qid": "Q999999", "label": "parliamentary term"}]},
            "wrong-temporal-level",
        ),
        (
            {"jurisdictions": [{"property": "P17", "qid": "Q30", "label": "United States"}]},
            "wrong-jurisdiction",
        ),
    ],
)
def test_historical_predecessor_term_class_and_wrong_jurisdiction_candidates_are_excluded(
    candidate_options, expected_reason
):
    raw = candidate(**candidate_options)
    outcome = resolve_institution(institution(), {}, Wikidata([raw]))

    assert outcome.state == "pending"  # Candidate exclusion is not local review rejection.
    assert outcome.evidence["reason"] == "candidates-excluded-by-contradictory-evidence"
    assert outcome.evidence["candidates"] == []
    assert outcome.evidence["excluded_candidates"][0]["negative_evidence"]
    assert expected_reason in {
        item["reason"] for item in outcome.evidence["excluded_candidates"][0]["negative_evidence"]
    }
    assert len(institution_links_graph(institution(), outcome)) == 0


def test_structured_wrong_organisational_evidence_is_retained():
    relationship = {"property": "P361", "qid": "Q123456", "label": "Parliament of another jurisdiction"}
    raw = candidate(
        relationships=[relationship],
        negative_evidence=[{
            "reason": "wrong-organisational-context",
            "property": "P361",
            "value": "Q123456",
        }],
    )
    outcome = resolve_institution(institution(), {}, Wikidata([raw]))
    assert outcome.state == "pending"
    evidence = outcome.evidence["excluded_candidates"][0]["negative_evidence"]
    assert evidence == [{"reason": "wrong-organisational-context", "property": "P361", "value": "Q123456"}]


def test_wikidata_candidate_query_is_indexable_and_seed_qid_does_not_override_historical_evidence(monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    from oireachtas_etl import reconciliation

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({"results": {"bindings": [{
                "item": {"type": "uri", "value": "https://www.wikidata.org/entity/Q651981"},
                "label": {"type": "literal", "value": "Dáil Éireann", "xml:lang": "ga"},
                "discoveryMethod": {"type": "literal", "value": "initial-review-candidate"},
                "description": {
                    "type": "literal",
                    "value": "Revolutionary parliament in Ireland",
                    "xml:lang": "en",
                },
            }]}}).encode()

    requests = []

    def open_request(request, timeout):
        requests.append(request)
        return Response()

    monkeypatch.setattr(reconciliation, "urlopen", open_request)
    candidates = WikidataClient().lookup_institution_candidates(institution(DAIL))
    query = parse_qs(urlsplit(requests[0].full_url).query)["query"][0]
    assert "VALUES ?wantedLabel" in query
    assert "VALUES ?item { wd:Q651981 }" in query
    assert "?item rdfs:label ?wantedLabel" in query and "?item skos:altLabel ?wantedLabel" in query
    assert all(prop in query for prop in ("P31", "P17", "P1001", "P1365", "P1366", "P571", "P576"))
    assert "REGEX(" not in query and "CONTAINS(" not in query
    assert candidates[0]["qid"] == "Q651981"
    assert candidates[0]["negative_evidence"] == [{
        "reason": "historical-predecessor",
        "property": "description",
        "value": "Revolutionary parliament in Ireland",
    }]

    # A documented seed is still only a review candidate: its explicit
    # historical contradiction excludes it from eligible identity candidates.
    outcome = resolve_institution(institution(DAIL), {}, Wikidata(candidates))
    assert outcome.state == "pending"
    assert outcome.evidence["candidates"] == []
    assert outcome.evidence["excluded_candidates"][0]["qid"] == "Q651981"
    assert outcome.evidence["excluded_candidates"][0]["negative_evidence"] == candidates[0]["negative_evidence"]


@pytest.mark.parametrize(
    "local_iri",
    [
        "https://data.oireachtas.ie/ie/oireachtas/house/dail/33",
        "https://data.oireachtas.ie/government",
    ],
)
def test_numbered_house_terms_and_government_are_not_institution_policy_inputs(tmp_path, local_iri):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    wd = Wikidata()
    try:
        with pytest.raises(ValueError, match="outside the approved enduring-institution scope"):
            reconcile_institution_records([institution(local_iri)], store, {}, "review", wd)
        assert wd.lookup_calls == []
        assert store.connection.execute("SELECT COUNT(*) FROM reconciliation_record").fetchone()[0] == 0
    finally:
        store.close()


def test_house_term_external_link_namespace_is_separate_from_enduring_house_namespace():
    enduring_house_graph = institution_external_graph_iri(institution(DAIL))
    # The exact future term graph syntax is deliberately not fixed here; only
    # reserve a disjoint HouseTerm graph namespace from the settled institution
    # graph namespace.
    illustrative_term_graph = "https://data.oireachtas.ie/graph/house-term/dail/33/external-links"
    assert enduring_house_graph == "https://data.oireachtas.ie/graph/institution/house/dail/external-links"
    assert not enduring_house_graph.startswith("https://data.oireachtas.ie/graph/house-term/")
    assert illustrative_term_graph.startswith("https://data.oireachtas.ie/graph/house-term/")
    assert enduring_house_graph != illustrative_term_graph


def test_review_identity_survives_a_local_label_change(monkeypatch):
    # Local review identity is the persistent IRI, not a current label or alias.
    monkeypatch.setitem(INSTITUTIONS[DAIL], "labels", ["Updated Dáil display label"])
    outcome = resolve_institution(institution(DAIL), accepted_review(DAIL), NoLookup())
    assert outcome.state == "accepted" and outcome.review_applied
    assert outcome.evidence["local_iri"] == DAIL
    assert outcome.evidence["decision"]["wikidata"] == "Q651981"


def test_reviewed_wikidata_identity_and_matching_downstream_wikipedia_use_only_approved_links():
    qid = "Q651981"
    wd = Wikidata(entities={qid: {"entities": {qid: {
        "id": qid,
        "sitelinks": {"enwiki": {"title": "Dáil Éireann"}},
    }}}})
    review = accepted_review(DAIL, qid, wikipedia=WIKIPEDIA_DAIL)
    outcome = resolve_institution(institution(), review, wd)
    graph = institution_links_graph(institution(), outcome)

    assert outcome.state == "accepted" and outcome.review_applied
    assert wd.lookup_calls == [] and wd.entity_calls == [qid]
    assert set(graph) == {
        (URIRef(DAIL), OWL.sameAs, URIRef(WIKIDATA + qid)),
        (URIRef(DAIL), FOAF.isPrimaryTopicOf, URIRef(WIKIPEDIA_DAIL)),
    }
    assert not list(graph.triples((None, URIRef("http://www.w3.org/2002/07/owl#sameAs"), URIRef("https://dbpedia.org/resource/Anything"))))


def test_mismatched_reviewed_sitelink_withholds_only_wikipedia_enrichment():
    qid = "Q651981"
    wd = Wikidata(entities={qid: {"entities": {qid: {
        "id": qid,
        "sitelinks": {"enwiki": {"title": "List of Dáil terms"}},
    }}}})
    outcome = resolve_institution(
        institution(), accepted_review(DAIL, qid, wikipedia=WIKIPEDIA_DAIL), wd
    )
    graph = institution_links_graph(institution(), outcome)
    assert outcome.state == "accepted" and outcome.wikidata == WIKIDATA + qid
    assert outcome.enrichment_reason == "wikipedia-sitelink-review-mismatch"
    assert set(graph) == {(URIRef(DAIL), OWL.sameAs, URIRef(WIKIDATA + qid))}


@pytest.mark.parametrize("outcome_kind", ["unresolved", "outage"])
def test_unresolved_candidate_or_wikidata_outage_preserves_existing_accepted_graph(tmp_path, outcome_kind):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    publisher = MemoryPublisher()
    graph_iri = institution_external_graph_iri(institution())
    initial_review = accepted_review()
    try:
        first = reconcile_institution_records(
            [institution()], store, initial_review, "reviewed", NoLookup(),
            all_records=True, publish=publisher, competency_client=GraphGate(publisher),
        )
        assert first[0][1].state == "accepted"
        original_payload = publisher.graphs[graph_iri]
        original_calls = list(publisher.calls)

        if outcome_kind == "unresolved":
            wd = Wikidata([])
        else:
            wd = Wikidata(error=OSError("Wikidata unavailable"))
        pending = reconcile_institution_records(
            [institution()], store, {}, "review-removed", wd,
            publish=publisher, competency_client=GraphGate(publisher),
        )
        assert pending[0][1].state == "pending"
        assert publisher.calls == original_calls
        assert publisher.graphs[graph_iri] == original_payload
        state = store.get_record("institution", DAIL)
        assert state["publication_state"] == "clean"
    finally:
        store.close()


def test_ambiguous_candidates_preserve_an_existing_accepted_graph(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    publisher = MemoryPublisher()
    graph_iri = institution_external_graph_iri(institution())
    try:
        reconcile_institution_records(
            [institution()], store, accepted_review(), "reviewed", NoLookup(),
            all_records=True, publish=publisher, competency_client=GraphGate(publisher),
        )
        accepted_payload = publisher.graphs[graph_iri]
        calls_before_ambiguity = list(publisher.calls)

        ambiguous = reconcile_institution_records(
            [institution()], store, {}, "review-removed",
            Wikidata([candidate(qid="Q900001"), candidate(qid="Q900002")]),
            publish=publisher, competency_client=GraphGate(publisher),
        )

        assert ambiguous[0][1].state == "ambiguous"
        assert publisher.calls == calls_before_ambiguity
        assert publisher.graphs[graph_iri] == accepted_payload
        state = store.get_record("institution", DAIL)
        assert state["state"] == "ambiguous" and state["publication_state"] == "clean"
    finally:
        store.close()


def test_clean_unchanged_payload_skips_publication_unless_all_is_requested(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    publisher = MemoryPublisher()
    graph_iri = institution_external_graph_iri(institution())
    try:
        first = reconcile_institution_records(
            [institution()], store, accepted_review(), "reviewed", NoLookup(),
            publish=publisher, competency_client=GraphGate(publisher),
        )
        assert len(first) == 1 and len(publisher.calls) == 1
        payload = publisher.calls[0][1]

        unchanged = reconcile_institution_records(
            [institution()], store, accepted_review(), "reviewed", NoLookup(),
            publish=publisher, competency_client=GraphGate(publisher),
        )
        assert unchanged == []
        assert publisher.calls == [(graph_iri, payload)]

        # all_records is the shared-engine behavior requested by CLI --all.
        forced = reconcile_institution_records(
            [institution()], store, accepted_review(), "reviewed", NoLookup(),
            all_records=True, publish=publisher, competency_client=GraphGate(publisher),
        )
        assert len(forced) == 1
        assert publisher.calls == [(graph_iri, payload), (graph_iri, payload)]
    finally:
        store.close()


def test_graph_ownership_is_independent_and_reviewed_rejection_clears_only_its_graph(tmp_path):
    houses = transform_houses(json.loads((ROOT / "data/api_examples/houses.json").read_text()))
    houses_payload = ntriples(houses)
    oireachtas_graph = "https://data.oireachtas.ie/graph/oireachtas"
    oireachtas_payload = "<https://data.oireachtas.ie/oireachtas> <https://example.test/owned> <https://example.test/value> ."
    publisher = MemoryPublisher({HOUSES_GRAPH: houses_payload, oireachtas_graph: oireachtas_payload})
    authoritative_before = {HOUSES_GRAPH: houses_payload, oireachtas_graph: oireachtas_payload}
    store = ReconciliationStore(tmp_path / "state.sqlite")
    decisions = {
        OIREACHTAS: {"status": "accepted", "wikidata": "Q129821"},
        DAIL: {"status": "accepted", "wikidata": "Q651981"},
        SEANAD: {"status": "accepted", "wikidata": "Q1127591"},
    }
    records = [institution(local_iri) for local_iri in LOCAL_IRIS]
    try:
        results = reconcile_institution_records(
            records, store, decisions, "all-reviewed", NoLookup(), all_records=True,
            publish=publisher, competency_client=GraphGate(publisher),
        )
        assert len(results) == 3 and len(publisher.calls) == 3
        graph_iris = {institution_external_graph_iri(entity) for entity, _, _ in results}
        assert len(graph_iris) == 3
        accepted_payloads = {graph_iri: publisher.graphs[graph_iri] for graph_iri in graph_iris}
        for entity, _, graph in results:
            local_iri = entity["uri"]
            assert set(graph) == {(URIRef(local_iri), OWL.sameAs, URIRef(WIKIDATA + decisions[local_iri]["wikidata"]))}
            assert {subject for subject, _, _ in graph} == {URIRef(local_iri)}

        dail_graph = institution_external_graph_iri(institution(DAIL))
        calls_before_rejection = len(publisher.calls)
        rejected = reconcile_institution_records(
            [institution(DAIL)], store, {DAIL: {"status": "rejected"}}, "dail-rejected",
            NoLookup(), all_records=True, publish=publisher,
            competency_client=GraphGate(publisher),
        )
        assert rejected[0][1].state == "rejected" and rejected[0][1].review_applied
        assert len(rejected[0][2]) == 0
        assert publisher.calls[calls_before_rejection:] == [(dail_graph, "")]
        assert publisher.graphs[dail_graph] == ""
        for other_iri in graph_iris - {dail_graph}:
            assert publisher.graphs[other_iri] == accepted_payloads[other_iri]
        assert {iri: publisher.graphs[iri] for iri in authoritative_before} == authoritative_before
        assert all(graph_iri not in authoritative_before for graph_iri, _ in publisher.calls)
    finally:
        store.close()


def test_dirty_publication_replays_exact_payload_before_changed_review_and_all(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    graph_iri = institution_external_graph_iri(institution())
    accepted = accepted_review()

    class InterruptedPut:
        def replace(self, *args, **kwargs):
            raise RuntimeError("simulated interrupted institutional PUT")

    try:
        with pytest.raises(RuntimeError, match="interrupted institutional PUT"):
            reconcile_institution_records(
                [institution()], store, accepted, "old-review", NoLookup(), all_records=True,
                publish=InterruptedPut(), competency_client=object(),
            )
        dirty = store.get_record("institution", DAIL)
        assert dirty["publication_state"] == "dirty"
        exact_payload = dirty["pending_payload"]
        assert exact_payload == ntriples(institution_links_graph(
            institution(), resolve_institution(institution(), accepted, NoLookup())
        ))

        publisher = MemoryPublisher()
        # The changed reviewed decision and --all are applied only after exact
        # recovery; they cannot replace the dirty payload before it is replayed.
        result = reconcile_institution_records(
            [institution()], store, {DAIL: {"status": "rejected"}}, "new-review", NoLookup(),
            all_records=True, publish=publisher, competency_client=GraphGate(publisher),
        )
        assert publisher.calls == [(graph_iri, exact_payload), (graph_iri, "")]
        assert result[0][1].state == "rejected" and len(result[0][2]) == 0
        assert store.get_record("institution", DAIL)["publication_state"] == "clean"
    finally:
        store.close()


def test_failed_whole_graph_verification_keeps_publication_dirty_and_records_failure(tmp_path):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    publisher = MemoryPublisher()
    graph_iri = institution_external_graph_iri(institution())

    class RogueGate(GraphGate):
        def query(self, query):
            rows = super().query(query)
            rows.append({
                "s": {"type": "uri", "value": "https://example.test/rogue"},
                "p": {"type": "uri", "value": "https://example.test/predicate"},
                "o": {"type": "uri", "value": "https://example.test/object"},
            })
            return rows

    expected_payload = ntriples(institution_links_graph(
        institution(), resolve_institution(institution(), accepted_review(), NoLookup())
    ))
    try:
        with pytest.raises(ReconciliationError, match="whole-graph"):
            reconcile_institution_records(
                [institution()], store, accepted_review(), "reviewed", NoLookup(),
                all_records=True, publish=publisher, competency_client=RogueGate(publisher),
            )

        state = store.get_record("institution", DAIL)
        assert state["publication_state"] == "dirty"
        assert state["pending_payload"] == expected_payload
        assert state["pending_payload_hash"] == _hash(expected_payload)
        assert state["error"] and "whole-graph" in state["error"]
        assert publisher.graphs[graph_iri] == expected_payload
        publication = store.connection.execute(
            "SELECT payload_hash,result,error FROM publication_attempt WHERE entity_kind='institution' AND local_iri=?",
            (DAIL,),
        ).fetchone()
        assert publication[0] == _hash(expected_payload)
        assert publication[1] == "failure" and "whole-graph" in publication[2]
        reconciliation = store.connection.execute(
            "SELECT state,review_applied FROM reconciliation_attempt WHERE entity_kind='institution' AND local_iri=?",
            (DAIL,),
        ).fetchone()
        assert tuple(reconciliation) == ("accepted", 1)
    finally:
        store.close()


@pytest.mark.parametrize("corruption", ["hash", "graph", "boundary"])
def test_corrupt_or_out_of_boundary_dirty_institution_payload_fails_before_put(tmp_path, corruption):
    store = ReconciliationStore(tmp_path / "state.sqlite")
    accepted = accepted_review()
    graph_iri = institution_external_graph_iri(institution())

    class Broken:
        def replace(self, *args, **kwargs):
            raise RuntimeError("initial publication interrupted")

    try:
        with pytest.raises(RuntimeError, match="interrupted"):
            reconcile_institution_records(
                [institution()], store, accepted, "review", NoLookup(), all_records=True,
                publish=Broken(), competency_client=object(),
            )
        if corruption == "hash":
            store.connection.execute(
                "UPDATE reconciliation_record SET pending_payload_hash='invalid' WHERE entity_kind='institution' AND local_iri=?",
                (DAIL,),
            )
            match = "payload or hash"
        elif corruption == "graph":
            store.connection.execute(
                "UPDATE reconciliation_record SET pending_graph_iri=? WHERE entity_kind='institution' AND local_iri=?",
                ("https://example.test/attacker-graph", DAIL),
            )
            match = "graph boundary"
        else:
            forbidden = Graph()
            forbidden.add((URIRef(DAIL), RDFS.label, URIRef("https://example.test/not-an-approved-link")))
            payload = ntriples(forbidden)
            store.connection.execute(
                "UPDATE reconciliation_record SET pending_payload=?,pending_payload_hash=? WHERE entity_kind='institution' AND local_iri=?",
                (payload, _hash(payload), DAIL),
            )
            match = "boundary"
        store.connection.commit()

        publisher = MemoryPublisher()
        with pytest.raises(ReconciliationError, match=match):
            reconcile_institution_records(
                [institution()], store, accepted, "review", NoLookup(),
                publish=publisher, competency_client=GraphGate(publisher),
            )
        assert publisher.calls == []
        assert graph_iri not in publisher.graphs
    finally:
        store.close()


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_whole_graph_verification_rejects_missing_or_rogue_institution_triples(mutation):
    outcome = resolve_institution(institution(), accepted_review(), NoLookup())
    graph = institution_links_graph(institution(), outcome)
    graph_iri = institution_external_graph_iri(institution())
    actual = Graph()
    actual += graph
    if mutation == "missing":
        actual.remove((URIRef(DAIL), OWL.sameAs, URIRef(WIKIDATA + "Q651981")))
    else:
        actual.add((URIRef("https://example.test/rogue"), RDFS.label, URIRef("https://example.test/fact")))

    class FixedGraphClient:
        def query(self, query):
            return [
                {"s": {"type": "uri", "value": str(s)},
                 "p": {"type": "uri", "value": str(p)},
                 "o": {"type": "uri", "value": str(o)}}
                for s, p, o in actual
            ]

    with pytest.raises(ReconciliationError, match="whole-graph"):
        verify_reconciliation_graph(FixedGraphClient(), graph_iri, graph)


def test_offline_cli_publishes_reviewed_identity_and_downstream_wikipedia_deterministically(tmp_path, capsys):
    fixture = tmp_path / "institution.json"
    fixture.write_text(json.dumps({"version": 1, "institutions": [DAIL]}))
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"version": 1, "decisions": accepted_review(
        DAIL, "Q651981", wikipedia=WIKIPEDIA_DAIL,
    )}))
    responses = tmp_path / "responses.json"
    responses.write_text(json.dumps({"wikidata": {
        "institution_candidates": {},
        "entities": {"Q651981": {"entities": {"Q651981": {
            "id": "Q651981", "sitelinks": {"enwiki": {"title": "Dáil Éireann"}},
        }}}},
    }}))
    output, state = tmp_path / "institution-links.nq", tmp_path / "state.sqlite"
    args = [
        "reconcile", "institutions", "--fixture", str(fixture), "--responses-file", str(responses),
        "--offline", "--all", "--review-file", str(review), "--reconciliation-state-file", str(state),
        "--output-nq", str(output),
    ]

    assert main(args) == 0
    first = output.read_text()
    assert "owl#sameAs" in first and "foaf/0.1/isPrimaryTopicOf" in first
    assert "wikidata.org/entity/Q651981" in first and "dbpedia.org" not in first
    assert institution_external_graph_iri(institution()) in first
    assert main(args) == 0 and output.read_text() == first
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["accepted"] == 1


def test_offline_cli_fails_preflight_before_creating_state_for_missing_candidate_evidence(tmp_path):
    fixture = tmp_path / "institution.json"
    fixture.write_text(json.dumps({"version": 1, "institutions": [DAIL]}))
    review = tmp_path / "empty-review.json"
    review.write_text('{"version":1,"decisions":{}}')
    responses = tmp_path / "incomplete-responses.json"
    responses.write_text(json.dumps({"wikidata": {"institution_candidates": {}, "entities": {}}}))
    state = tmp_path / "must-not-exist.sqlite"

    with pytest.raises(ValueError, match="lacks valid institutional candidate entry"):
        main([
            "reconcile", "institutions", "--fixture", str(fixture), "--responses-file", str(responses),
            "--offline", "--review-file", str(review), "--reconciliation-state-file", str(state),
        ])
    assert not state.exists()


def test_house_term_competency_traverses_term_of_and_never_asserts_direct_external_identity():
    houses = transform_houses(json.loads((ROOT / "data/api_examples/houses.json").read_text()))
    accepted = resolve_institution(institution(), accepted_review(), NoLookup())
    external_graph = institution_links_graph(institution(), accepted)
    graph_iri = institution_external_graph_iri(institution())
    dataset = Dataset()
    houses_context = dataset.graph(URIRef(HOUSES_GRAPH))
    external_context = dataset.graph(URIRef(graph_iri))
    for triple in houses:
        houses_context.add(triple)
    for triple in external_graph:
        external_context.add(triple)

    traversal = list(dataset.query(f"""
        SELECT ?term ?house ?external WHERE {{
            GRAPH <{HOUSES_GRAPH}> {{ ?term <{OIR.termOf}> ?house . }}
            GRAPH <{graph_iri}> {{ ?house <{OWL.sameAs}> ?external . }}
        }}
    """))
    assert {(str(row.term), str(row.house), str(row.external)) for row in traversal} == {
        ("https://data.oireachtas.ie/ie/oireachtas/house/dail/33", DAIL, WIKIDATA + "Q651981"),
        ("https://data.oireachtas.ie/ie/oireachtas/house/dail/34", DAIL, WIKIDATA + "Q651981"),
    }

    direct_identity = list(dataset.query(f"""
        SELECT ?term ?external WHERE {{
            GRAPH <{HOUSES_GRAPH}> {{ ?term <{OIR.termOf}> ?house . }}
            GRAPH ?links {{ ?term <{OWL.sameAs}> ?external . }}
        }}
    """))
    assert direct_identity == []
