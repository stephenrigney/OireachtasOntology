"""Focused Phase 7 Tranche 4 tests for external office reconciliation.

Synthetic review decisions drive lifecycle tests; one regression check exercises
the three user-approved version-controlled office decisions. Ordinary tests use
local response stubs and never call live authority services;
the optional Fuseki test is enabled only for the dedicated OIR_TEST_FUSEKI
dataset used by ``test_fuseki_integration.py``.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

from oireachtas_etl.config import OFFICES_GRAPH
from oireachtas_etl.reconciliation import (
    ReconciliationStore,
    _normalize_office_candidate_for,
    _office_candidate_negative_evidence,
    deduplicate_external_office_records,
    load_external_office_review,
    office_external_graph_iri,
    office_external_records,
    reconcile_external_office_records,
    verify_reconciliation_graph,
)
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.transforms.offices import office_iri, transform_offices
from oireachtas_etl.validation.offices import validate_registry_source


OFFICE_IRI = str(office_iri("o-000001"))
SECOND_OFFICE_IRI = str(office_iri("o-000002"))
GRAPH_IRI = "https://data.oireachtas.ie/graph/office/o-000001/external-links"
WIKIDATA = "https://www.wikidata.org/entity/"
QID = "Q900001"
REVIEW_HASH = "synthetic-office-review-v1"


def synthetic_registry() -> dict:
    """A minimal registry whose entries are explicitly test-only identities."""
    registry = {
        "version": 1,
        "administrative_units": [{
            "key": "u-000001",
            "label_en": "Synthetic Department",
            "aliases": [],
            "reviewer_notes": "Synthetic unit for external office tests; not registry evidence.",
            "evidence": ["tests/test_office_external_reconciliation.py#unit"],
        }],
        "offices": [{
            "key": "o-000001",
            "label_en": "Synthetic Minister for Example Affairs",
            "aliases": [{"language": "en", "label": "Synthetic Minister for Example Affairs"}],
            "office_type": "MinisterOfficeType",
            "unit_relationships": [{
                "relationship": "headsAdministrativeUnit", "unit_key": "u-000001",
            }],
            "reviewer_notes": "Synthetic office for external identity tests; not registry evidence.",
            "evidence": ["tests/test_office_external_reconciliation.py#office-1"],
        }, {
            "key": "o-000002",
            "label_en": "Synthetic Minister of State for Example Affairs",
            "aliases": [],
            "office_type": "MinisterOfStateOfficeType",
            "unit_relationships": [{
                "relationship": "assignedToAdministrativeUnit", "unit_key": "u-000001",
            }],
            "reviewer_notes": "Synthetic office for external identity tests; not registry evidence.",
            "evidence": ["tests/test_office_external_reconciliation.py#office-2"],
        }],
    }
    return validate_registry_source(registry)


def records_for(registry: dict | None = None) -> list[dict]:
    registry = registry or synthetic_registry()
    return deduplicate_external_office_records(office_external_records(registry))


def record_for(local_iri: str = OFFICE_IRI, registry: dict | None = None) -> dict:
    registry = registry or synthetic_registry()
    return next(record for record in records_for(registry)
                if office_external_graph_iri(record).endswith(
                    "/" + local_iri.rsplit("/", 1)[-1] + "/external-links"))


def reviewed(qid: str = QID, *, status: str = "accepted") -> dict[str, dict]:
    if status == "rejected":
        return {OFFICE_IRI: {
            "status": "rejected", "evidence": ["test:synthetic-rejection"],
            "reason": "Synthetic test rejection; not a reviewed real office identity.",
        }}
    return {OFFICE_IRI: {
        "status": "accepted", "external_iri": WIKIDATA + qid,
        "evidence": ["test:synthetic-acceptance"],
        "reason": "Synthetic test acceptance; not a reviewed real office identity.",
    }}


def candidate(
    qid: str,
    *,
    labels: list[str] | None = None,
    matched_on: list[str] | None = None,
    entity_types: list[dict] | None = None,
    relationships: list[dict] | None = None,
    descriptions: list[str] | None = None,
    negative_evidence: list[dict] | None = None,
) -> dict:
    label = "Synthetic Minister for Example Affairs"
    return {
        "qid": qid,
        "labels": list(labels if labels is not None else [label]),
        "descriptions": list(descriptions or []),
        "matched_on": list(matched_on if matched_on is not None else [label]),
        "discovery_methods": ["exact-label"],
        "positive_evidence": {
            "entity_types": list(entity_types or []),
            "jurisdictions": [],
            "relationships": list(relationships or []),
            "official_sites": [],
            "inception": [],
            "dissolution": [],
        },
        "negative_evidence": list(negative_evidence or []),
    }


class FakeWikidata:
    def __init__(self, candidates=None, *, entities=None, lookup_error=None):
        self.candidates = [] if candidates is None else candidates
        self.entities = {} if entities is None else entities
        self.lookup_error = lookup_error
        self.lookup_calls = []
        self.entity_calls = []

    def lookup_office_candidates(self, record, registry):
        self.lookup_calls.append(record["office"]["uri"])
        if self.lookup_error is not None:
            raise self.lookup_error
        return self.candidates

    def entity(self, qid):
        self.entity_calls.append(qid)
        value = self.entities.get(qid, {"entities": {qid: {"id": qid}}})
        if isinstance(value, Exception):
            raise value
        return value


class MemoryPublisher:
    """A graph-scoped replacement sink used with the real graph verifier."""

    def __init__(self, graphs: dict[str, str] | None = None):
        self.graphs = {} if graphs is None else dict(graphs)
        self.calls: list[tuple[str, str]] = []

    def replace(self, graph_iri: str, payload: str, *, content_type: str):
        assert content_type == "application/n-triples"
        self.calls.append((graph_iri, payload))
        self.graphs[graph_iri] = payload


class MemoryGraphGate:
    def __init__(self, publisher: MemoryPublisher):
        self.publisher = publisher

    def query(self, query: str) -> list[dict]:
        import re

        graph_iri = re.search(r"GRAPH\s+<([^>]+)>", query).group(1)
        payload = self.publisher.graphs.get(graph_iri, "")
        graph = Graph().parse(data=payload, format="nt") if payload else Graph()
        return [{"s": {"type": "uri", "value": str(subject)},
                 "p": {"type": "uri", "value": str(predicate)},
                 "o": {"type": "uri", "value": str(object_)}}
                for subject, predicate, object_ in graph]


def resolve(record, store, review, client, publisher=None, *, registry=None, all_records=True):
    # ``office_external_records`` carries the validated registry snapshot so
    # the entity-generic public reconciliation interface does not need a
    # parallel registry/state argument.
    if registry is not None:
        assert record["_registry"] == registry
    return reconcile_external_office_records(
        [record], store, review, REVIEW_HASH, client, all_records=all_records,
        publish=publisher,
        competency_client=MemoryGraphGate(publisher) if publisher is not None else None,
    )


def test_external_office_records_and_graph_identity_are_registry_scoped_and_deduplicated():
    registry = synthetic_registry()
    records = office_external_records(registry)
    assert {office_external_graph_iri(record) for record in records} == {
        GRAPH_IRI,
        "https://data.oireachtas.ie/graph/office/o-000002/external-links",
    }
    assert deduplicate_external_office_records(records + copy.deepcopy(records)) == records
    assert office_external_graph_iri(record_for(SECOND_OFFICE_IRI, registry)) == (
        "https://data.oireachtas.ie/graph/office/o-000002/external-links")


def test_external_office_review_uses_full_local_iri_and_accepts_only_synthetic_decision(tmp_path):
    path = tmp_path / "office-external-decisions.json"
    registry = synthetic_registry()
    payload = {"version": 1, "decisions": reviewed()}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    decisions, digest = load_external_office_review(path, registry)

    assert decisions == payload["decisions"]
    assert decisions[OFFICE_IRI]["external_iri"] == WIKIDATA + QID
    assert digest
    assert "Synthetic test acceptance" in decisions[OFFICE_IRI]["reason"]


def test_reviewed_same_office_publishes_only_sameas_in_its_replaceable_graph(tmp_path):
    record = record_for()
    authoritative = transform_offices(synthetic_registry())
    unrelated_graph = "https://data.oireachtas.ie/graph/office-external-test-unrelated"
    unrelated_payload = (
        "<https://example.test/untouched> <https://example.test/p> "
        "<https://example.test/o> .\n")
    publisher = MemoryPublisher({OFFICES_GRAPH: ntriples(authoritative),
                                 unrelated_graph: unrelated_payload})
    original_graphs = dict(publisher.graphs)
    external_graph = office_external_graph_iri(record)

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        result = resolve(record, store, reviewed(), FakeWikidata(), publisher)[0]

        assert result[1].state == "accepted" and result[1].review_applied
        expected = Graph()
        expected.add((URIRef(OFFICE_IRI), OWL.sameAs, URIRef(WIKIDATA + QID)))
        assert set(result[2]) == set(expected)
        assert publisher.calls == [(external_graph, ntriples(expected))]
        assert set(Graph().parse(data=publisher.graphs[external_graph], format="nt")) == set(expected)
        assert {key: value for key, value in publisher.graphs.items()
                if key != external_graph} == original_graphs
        verify_reconciliation_graph(MemoryGraphGate(publisher), external_graph, expected)
        row = store.get_record("office", OFFICE_IRI)
        assert row["publication_state"] == "clean"


def test_approved_registry_offices_have_distinct_reviewed_targets_and_graphs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / "registries/ministerial-office-registry.json").read_text())
    decisions, review_hash = load_external_office_review(
        root / "reconciliation/office-external-decisions.json", registry)
    expected = {
        "o-000001": "Q191827",
        "o-000002": "Q1146214",
        "o-000003": "Q4294945",
    }
    records = [item for item in office_external_records(registry)
               if item["office"]["key"] in expected]
    assert len(records) == len(expected)
    assert {item["office"]["uri"] for item in records} <= set(decisions)
    reviewed = {item["office"]["uri"]: decisions[item["office"]["uri"]]
                for item in records}

    class VerifiedTargets:
        def entity(self, qid):
            assert qid in expected.values()
            return {"entities": {qid: {"id": qid}}}

        def lookup_office_candidates(self, *args):
            raise AssertionError("human-reviewed office must not be looked up by label")

    publisher = MemoryPublisher()
    with ReconciliationStore(tmp_path / "real-review-fixture.sqlite") as store:
        results = reconcile_external_office_records(
            records, store, reviewed, review_hash, VerifiedTargets(),
            publish=publisher, competency_client=MemoryGraphGate(publisher))
    assert len(results) == 3
    for record, result, graph in results:
        key = record["_office"]["key"]
        iri = URIRef(record["uri"])
        assert result.state == "accepted" and result.review_applied
        assert set(graph) == {(iri, OWL.sameAs, URIRef(WIKIDATA + expected[key]))}
        assert publisher.graphs[office_external_graph_iri(record)] == ntriples(graph)
    assert len(publisher.calls) == len(publisher.graphs) == 3


def test_reviewed_rejection_replaces_only_the_office_external_graph_with_empty_graph(tmp_path):
    record = record_for()
    publisher = MemoryPublisher()
    external_graph = office_external_graph_iri(record)
    authoritative_payload = ntriples(transform_offices(synthetic_registry()))
    publisher.graphs[OFFICES_GRAPH] = authoritative_payload

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        resolve(record, store, reviewed(), FakeWikidata(), publisher)
        before_rejection = list(publisher.calls)
        rejected = resolve(record, store, reviewed(status="rejected"), FakeWikidata(), publisher)[0]

        assert rejected[1].state == "rejected" and rejected[1].review_applied
        assert len(rejected[2]) == 0
        assert publisher.calls == before_rejection + [(external_graph, "")]
        assert publisher.graphs[external_graph] == ""
        assert publisher.graphs[OFFICES_GRAPH] == authoritative_payload
        assert store.get_record("office", OFFICE_IRI)["state"] == "rejected"


@pytest.mark.parametrize(("qid", "label", "expected_reason"), [
    ("Q900010", "human", "wrong-entity-level"),
    ("Q900011", "office holding", "wrong-entity-level"),
    ("Q900012", "office-holder", "wrong-entity-level"),
    ("Q900013", "administrative unit", "wrong-entity-level"),
])
def test_wrong_entity_level_candidates_are_evidence_not_external_office_identity(
        tmp_path, qid, label, expected_reason):
    raw = candidate(qid, entity_types=[{"qid": qid, "label": label}])
    registry = synthetic_registry()
    normalized = _normalize_office_candidate_for(OFFICE_IRI, raw, registry)
    negative = _office_candidate_negative_evidence(normalized)

    assert any(item["reason"] == expected_reason for item in negative)
    record = record_for()
    with ReconciliationStore(tmp_path / f"{qid}.sqlite") as store:
        result = resolve(record, store, {}, FakeWikidata([raw]), registry=registry)[0]

    assert result[1].state == "pending"
    assert len(result[2]) == 0
    assert result[1].evidence["excluded_candidates"][0]["qid"] == qid
    assert any(item["reason"] == expected_reason
               for item in result[1].evidence["excluded_candidates"][0]["negative_evidence"])


def test_successor_mismatch_requires_explicit_negative_evidence_and_never_creates_identity(tmp_path):
    raw = candidate("Q900013", relationships=[{
        "property": "P1365", "qid": "Q900014", "label": "Synthetic predecessor office",
    }], negative_evidence=[{
        "reason": "historical-successor", "property": "P1365", "value": "Q900014",
    }])
    normalized = _normalize_office_candidate_for(OFFICE_IRI, raw, synthetic_registry())

    negative = _office_candidate_negative_evidence(normalized)

    assert any(item["reason"] == "historical-successor" for item in negative)

    with ReconciliationStore(tmp_path / "office-successor.sqlite") as store:
        result = resolve(record_for(), store, {}, FakeWikidata([raw]))[0]
    assert result[1].state == "pending"
    assert len(result[2]) == 0


def test_predecessor_relationship_alone_does_not_exclude_a_current_office(tmp_path):
    # The reviewed Taoiseach item Q191827 has P1365 to a distinct pre-1937
    # office. This does not make Q191827 the wrong entity for a local Taoiseach.
    raw = candidate("Q191827", relationships=[{
        "property": "P1365", "qid": "Q4376681", "label": "President of the Executive Council",
    }])
    with ReconciliationStore(tmp_path / "office-predecessor.sqlite") as store:
        result = resolve(record_for(), store, {}, FakeWikidata([raw]))[0]
    assert result[1].state == "pending"  # First acceptance still needs human review.
    assert [item["qid"] for item in result[1].evidence["candidates"]] == ["Q191827"]
    assert result[1].evidence["excluded_candidates"] == []
    assert len(result[2]) == 0


def test_ambiguous_office_candidates_remain_unresolved_without_publication(tmp_path):
    record = record_for()
    choices = [candidate("Q900020"), candidate("Q900021")]
    publisher = MemoryPublisher()

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        result = resolve(record, store, {}, FakeWikidata(choices), publisher)[0]

    assert result[1].state == "ambiguous"
    assert result[1].wikidata is None
    assert len(result[2]) == 0
    assert publisher.calls == []


def test_candidate_service_outage_is_pending_and_does_not_block_local_office_graph(tmp_path):
    record = record_for()
    publisher = MemoryPublisher({OFFICES_GRAPH: ntriples(transform_offices(synthetic_registry()))})
    authoritative_before = publisher.graphs[OFFICES_GRAPH]

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        result = resolve(record, store, {},
                        FakeWikidata(lookup_error=OSError("synthetic Wikidata outage")),
                        publisher)[0]

    assert result[1].state == "pending"
    assert result[1].enrichment_status in {"retry", "unresolved"}
    assert publisher.calls == []
    assert publisher.graphs[OFFICES_GRAPH] == authoritative_before
    assert store_record_state(tmp_path / "reconciliation.sqlite", OFFICE_IRI) == "pending"


def store_record_state(path: Path, local_iri: str) -> str:
    with ReconciliationStore(path) as store:
        return store.get_record("office", local_iri)["state"]


@pytest.mark.parametrize(("target_response", "error_code"), [
    ({"entities": {QID: {"id": QID}}, "redirects": [{"from": QID, "to": "Q900099"}]}, "redirected"),
    ({"entities": {}}, "disappeared"),
])
def test_redirected_or_disappeared_reviewed_target_retries_without_erasing_last_link(
        tmp_path, target_response, error_code):
    record = record_for()
    publisher = MemoryPublisher()
    external_graph = office_external_graph_iri(record)

    with ReconciliationStore(tmp_path / f"{error_code}.sqlite") as store:
        resolve(record, store, reviewed(), FakeWikidata(), publisher)
        accepted_payload = publisher.graphs[external_graph]
        assert accepted_payload
        row = store.get_record("office", OFFICE_IRI)
        assert store.mark_due("office", OFFICE_IRI, "o-000001",
                              row["identity_hash"], force=True)

        checked = resolve(record, store, reviewed(),
                          FakeWikidata(entities={QID: target_response}), publisher,
                          all_records=False)[0]

        assert checked[1].state == "accepted"
        assert checked[1].enrichment_status == "retry"
        assert publisher.graphs[external_graph] == accepted_payload
        assert publisher.calls == [(external_graph, accepted_payload)]
        row = store.get_record("office", OFFICE_IRI)
        errors = json.loads(row["service_errors_json"])
        assert errors[0]["code"] == error_code
        assert row["publication_state"] == "clean"


def test_due_recheck_uses_shared_store_and_clean_unchanged_graph_is_not_replaced(tmp_path):
    record = record_for()
    publisher = MemoryPublisher()
    wd = FakeWikidata()

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        first = resolve(record, store, reviewed(), wd, publisher)
        assert len(first) == 1 and len(publisher.calls) == 1
        row = store.get_record("office", OFFICE_IRI)
        assert store.mark_due("office", OFFICE_IRI, "o-000001",
                              row["identity_hash"], force=True)

        second = resolve(record, store, reviewed(), wd, publisher, all_records=False)

        assert len(second) == 1
        assert wd.entity_calls == [QID, QID]
        assert len(publisher.calls) == 1
        assert store.connection.execute(
            "SELECT COUNT(*) FROM reconciliation_attempt WHERE entity_kind='office' AND local_iri=?",
            (OFFICE_IRI,)).fetchone()[0] == 2
        assert store.get_record("office", OFFICE_IRI)["publication_state"] == "clean"


def test_dirty_external_graph_replays_exact_payload_before_changed_review(tmp_path):
    record = record_for()
    external_graph = office_external_graph_iri(record)

    class InterruptedPublisher:
        def replace(self, graph_iri, payload, *, content_type):
            raise RuntimeError("synthetic interrupted office PUT")

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        with pytest.raises(RuntimeError, match="interrupted office PUT"):
            resolve(record, store, reviewed(), FakeWikidata(), InterruptedPublisher())
        dirty = store.get_record("office", OFFICE_IRI)
        assert dirty["publication_state"] == "dirty"
        exact_payload = dirty["pending_payload"]
        expected = Graph()
        expected.add((URIRef(OFFICE_IRI), OWL.sameAs, URIRef(WIKIDATA + QID)))
        assert exact_payload == ntriples(expected)
        assert dirty["pending_graph_iri"] == external_graph

        publisher = MemoryPublisher()
        rejected = resolve(record, store, reviewed(status="rejected"),
                          FakeWikidata(), publisher)[0]

        assert publisher.calls == [(external_graph, exact_payload), (external_graph, "")]
        assert rejected[1].state == "rejected"
        assert store.get_record("office", OFFICE_IRI)["publication_state"] == "clean"


def test_stubbed_candidate_and_review_path_never_requires_live_services(tmp_path):
    record = record_for()
    registry = synthetic_registry()
    raw = candidate("Q900030")
    review_file = tmp_path / "decisions.json"
    review_file.write_text(json.dumps({"version": 1, "decisions": {}}), encoding="utf-8")
    review, review_hash = load_external_office_review(review_file, registry)

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        result = reconcile_external_office_records(
            [record], store, review, review_hash, FakeWikidata([raw]))

    assert result[0][1].state == "pending"
    assert result[0][1].wikidata is None
    assert len(result[0][2]) == 0


def test_offline_scope_and_response_fixtures_publish_no_live_service_calls(
        tmp_path, capsys, monkeypatch):
    from oireachtas_etl import cli

    monkeypatch.setattr(cli, "WikidataClient", lambda *args, **kwargs: pytest.fail(
        "offline external office fixtures must not construct a live Wikidata client"))

    registry = synthetic_registry()
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    scope_path = tmp_path / "office-scope.json"
    scope_path.write_text(json.dumps({"version": 1, "offices": [OFFICE_IRI]}),
                         encoding="utf-8")
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"version": 1, "decisions": reviewed()}),
                           encoding="utf-8")
    responses_path = tmp_path / "responses.json"
    responses_path.write_text(json.dumps({"wikidata": {
        "office_candidates": {},
        "entities": {QID: {"entities": {QID: {"id": QID}}}},
    }}), encoding="utf-8")
    preview = tmp_path / "external-links.nq"
    state = tmp_path / "reconciliation.sqlite"

    result = cli.main([
        "reconcile", "office-external", "--registry-file", str(registry_path),
        "--fixture", str(scope_path), "--responses-file", str(responses_path),
        "--review-file", str(review_path), "--reconciliation-state-file", str(state),
        "--output-nq", str(preview), "--offline",
    ])

    assert result == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["processed"] == summary["accepted"] == 1
    assert summary["scope"] == [OFFICE_IRI]
    assert summary["published"] == 0
    assert preview.read_text(encoding="utf-8").strip() == (
        f"<{OFFICE_IRI}> <{OWL.sameAs}> <{WIKIDATA + QID}> <{GRAPH_IRI}> .")


def _binding_graph(client, graph_iri: str) -> Graph:
    result = Graph()
    for row in client.query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}"):
        result.add((URIRef(row["s"]["value"]), URIRef(row["p"]["value"]),
                    URIRef(row["o"]["value"])))
    return result


@pytest.mark.skipif(
    not (os.getenv("OIR_TEST_FUSEKI_GSP_URL") and os.getenv("OIR_TEST_FUSEKI_SPARQL_URL")),
    reason="set OIR_TEST_FUSEKI_GSP_URL and OIR_TEST_FUSEKI_SPARQL_URL for the disposable local Fuseki dataset",
)
def test_external_office_graph_is_exact_and_isolated_on_disposable_fuseki(tmp_path):
    from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient

    gsp = os.environ["OIR_TEST_FUSEKI_GSP_URL"]
    sparql = os.environ["OIR_TEST_FUSEKI_SPARQL_URL"]
    user = os.getenv("OIR_TEST_FUSEKI_USER")
    password = os.getenv("OIR_TEST_FUSEKI_PASSWORD")
    if user is not None and password is None:
        pytest.fail("OIR_TEST_FUSEKI_PASSWORD is required with OIR_TEST_FUSEKI_USER")
    loader = FusekiGraphStoreLoader(gsp, user=user, password=password)
    client = FusekiSparqlClient(sparql, user=user, password=password)
    registry = synthetic_registry()
    record = record_for(registry=registry)
    local_graph = transform_offices(registry)
    other_graph = "https://data.oireachtas.ie/graph/office-external-test-unrelated"
    other = Graph()
    other.add((URIRef("https://example.test/untouched"),
               URIRef("https://example.test/p"), URIRef("https://example.test/o")))
    loader.replace(OFFICES_GRAPH, ntriples(local_graph), content_type="application/n-triples")
    loader.replace(other_graph, ntriples(other), content_type="application/n-triples")
    local_before = set(_binding_graph(client, OFFICES_GRAPH))
    other_before = set(_binding_graph(client, other_graph))
    expected = Graph()
    expected.add((URIRef(OFFICE_IRI), OWL.sameAs, URIRef(WIKIDATA + QID)))
    external_graph = office_external_graph_iri(record)

    with ReconciliationStore(tmp_path / "reconciliation.sqlite") as store:
        result = reconcile_external_office_records(
            [record], store, reviewed(), REVIEW_HASH, FakeWikidata(),
            publish=loader, competency_client=client)

    assert len(result) == 1 and result[0][1].state == "accepted"
    assert set(result[0][2]) == set(expected)
    verify_reconciliation_graph(client, external_graph, expected)
    assert set(_binding_graph(client, external_graph)) == set(expected)
    assert set(_binding_graph(client, OFFICES_GRAPH)) == local_before
    assert set(_binding_graph(client, other_graph)) == other_before
