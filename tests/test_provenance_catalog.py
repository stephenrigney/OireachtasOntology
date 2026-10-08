from __future__ import annotations

import hashlib

import pytest
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD
from rdflib.namespace import PROV

from oireachtas_etl import provenance
from oireachtas_etl.config import COMMITTEES_GRAPH
from oireachtas_etl.state import CoreStateStore, PROVENANCE_GRAPH_IRI, run_resource_iri
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.members import member_graph_iri


RUN_ID = "catalog-run-001"
SOURCE_HASH = hashlib.sha256(b"raw source page").hexdigest()
PAYLOAD = "<https://data.oireachtas.ie/member/1> <https://example.test/p> <https://example.test/o> .\n"
PAYLOAD_HASH = hashlib.sha256(PAYLOAD.encode("utf-8")).hexdigest()
OBSERVED_AT = "2026-10-07T12:00:00+00:00"
GRAPH_IRI = "https://data.oireachtas.ie/graph/member/1"
SOURCE_IRI = provenance.source_observation_iri(SOURCE_HASH, OBSERVED_AT)
VERSION_IRI = provenance.graph_version_iri(GRAPH_IRI, PAYLOAD_HASH)


def _run(*, completed_at="2026-10-07T12:01:00Z"):
    return {
        "run_id": RUN_ID,
        "endpoint": "members",
        "run_kind": "full_refresh",
        "is_complete": 1,
        "started_at": "2026-10-07T12:00:00Z",
        "completed_at": completed_at,
        "status": "succeeded",
        "outcome": "success",
        "etl_version": "0.6.0",
        "ontology_version": "agents.owl.ttl@2026-10-07",
        "mapping_version": "member_mapping.csv@2026-10-07",
    }


def _source(*, pointer="file:///raw/members/sha256/page.json", **overrides):
    return {
        "source_hash": SOURCE_HASH,
        "observed_at": OBSERVED_AT,
        "endpoint": "members",
        "run_id": RUN_ID,
        "evidence_pointer": pointer,
        "source_url": "https://api.oireachtas.ie/v1/members",
        "request_parameters": {"limit": 100, "skip": 0},
        "versions": {
            "etl_version": "0.6.0",
            "ontology_version": "agents.owl.ttl@2026-10-07",
            "mapping_version": "member_mapping.csv@2026-10-07",
        },
        **overrides,
    }


def _version(**overrides):
    return {
        "graph_iri": GRAPH_IRI,
        "payload_hash": PAYLOAD_HASH,
        "payload": PAYLOAD,
        "endpoint": "members",
        "entity_iri": "https://data.oireachtas.ie/member/1",
        "source_hash": SOURCE_HASH,
        "first_run_id": RUN_ID,
        "created_at": "2026-10-07T12:00:30Z",
        **overrides,
    }


def _events(*, source_hash=SOURCE_HASH, include_source=True,
            source_pointer="file:///raw/members/sha256/page.json"):
    events = [
        {"event_type": "run_started", "run_id": RUN_ID},
        {
            "event_type": "entity_published",
            "run_id": RUN_ID,
            "endpoint": "members",
            "graph_iri": GRAPH_IRI,
            "payload_hash": PAYLOAD_HASH,
            "entity_iri": "https://data.oireachtas.ie/member/1",
            "source_hash": source_hash,
        },
        {"event_type": "run_finished", "run_id": RUN_ID},
    ]
    if include_source:
        events.insert(1, {
            "event_type": "source_observed",
            "run_id": RUN_ID,
            "endpoint": "members",
            "source_hash": SOURCE_HASH,
            "observed_at": OBSERVED_AT,
            "evidence_pointer": source_pointer,
        })
    return events


def _build(*, required=(), source_rows=None, event_rows=None, version_rows=None):
    return provenance.build_provenance_catalog_from_records(
        event_rows if event_rows is not None else _events(),
        version_rows if version_rows is not None else [_version()],
        [_run()],
        source_rows if source_rows is not None else [_source()],
        require_source_run_ids=required,
    )


def test_projection_is_deterministic_and_links_version_run_and_immutable_source():
    graph = _build(required=(RUN_ID,))
    replay = _build(required=(RUN_ID,))

    assert len(graph) == len(replay)
    assert provenance.ntriples(graph) == provenance.ntriples(replay)
    assert (URIRef(VERSION_IRI), RDF.type, PROV.Entity) in graph
    assert (URIRef(VERSION_IRI), PROV.specializationOf, URIRef(GRAPH_IRI)) in graph
    assert (URIRef(VERSION_IRI), PROV.wasGeneratedBy,
            URIRef(run_resource_iri(RUN_ID))) in graph
    assert (URIRef(VERSION_IRI), PROV.wasDerivedFrom, URIRef(SOURCE_IRI)) in graph
    assert (URIRef(run_resource_iri(RUN_ID)), RDF.type, PROV.Activity) in graph
    assert (URIRef(run_resource_iri(RUN_ID)), PROV.used, URIRef(SOURCE_IRI)) in graph
    assert (URIRef(SOURCE_IRI), provenance.ETL.sourceHash, Literal(SOURCE_HASH)) in graph
    assert (URIRef(SOURCE_IRI), provenance.ETL.requestParameters,
            Literal('{"limit":100,"skip":0}')) in graph
    assert (URIRef(SOURCE_IRI), provenance.ETL.sourceURL,
            URIRef("https://api.oireachtas.ie/v1/members")) in graph
    assert (URIRef(SOURCE_IRI), provenance.ETL.evidencePointer,
            Literal("file:///raw/members/sha256/page.json")) in graph
    assert (URIRef(run_resource_iri(RUN_ID)), provenance.ETL.etlVersion,
            Literal("0.6.0")) in graph
    assert (URIRef(run_resource_iri(RUN_ID)), provenance.ETL.ontologyVersion,
            Literal("agents.owl.ttl@2026-10-07")) in graph
    assert (URIRef(run_resource_iri(RUN_ID)), provenance.ETL.mappingVersion,
            Literal("member_mapping.csv@2026-10-07")) in graph
    assert (URIRef(run_resource_iri(RUN_ID)), PROV.startedAtTime,
            Literal("2026-10-07T12:00:00+00:00", datatype=XSD.dateTime)) in graph
    assert PROVENANCE_GRAPH_IRI == "https://data.oireachtas.ie/graph/provenance"


def test_source_identity_includes_hash_and_observation_time():
    later = "2026-10-07T13:00:00Z"
    assert provenance.source_observation_iri(SOURCE_HASH, OBSERVED_AT) != \
        provenance.source_observation_iri(SOURCE_HASH, later)
    assert provenance.source_observation_iri(SOURCE_HASH, OBSERVED_AT) == SOURCE_IRI

    second_source = _source(observed_at=later)
    second_event = {
        "event_type": "source_observed", "run_id": RUN_ID, "endpoint": "members",
        "source_hash": SOURCE_HASH, "observed_at": later,
        "evidence_pointer": second_source["evidence_pointer"],
    }
    catalog = _build(source_rows=[_source(), second_source],
                     event_rows=_events() + [second_event])
    assert len(list(catalog.objects(URIRef(VERSION_IRI), PROV.wasDerivedFrom))) == 2


def test_historical_missing_raw_pointer_is_not_invented_but_new_run_is_refused():
    historical = _build(source_rows=[_source(pointer=None)],
                        event_rows=_events(source_pointer=None))
    # The recorded hash+observation identity is real historical state; no raw
    # location is fabricated for the old record.
    assert (URIRef(VERSION_IRI), PROV.wasDerivedFrom, URIRef(SOURCE_IRI)) in historical
    assert (URIRef(SOURCE_IRI), provenance.ETL.evidencePointer, None) not in historical

    with pytest.raises(provenance.ProvenanceCatalogError, match="raw source pointer"):
        _build(required=(RUN_ID,), source_rows=[_source(pointer=None)],
               event_rows=_events(source_pointer=None))


def test_missing_source_observation_is_allowed_for_historical_replay_only():
    events = _events(include_source=False)
    replay = _build(event_rows=events, source_rows=[])
    assert (URIRef(VERSION_IRI), PROV.wasGeneratedBy,
            URIRef(run_resource_iri(RUN_ID))) in replay
    assert (URIRef(VERSION_IRI), PROV.wasDerivedFrom, None) not in replay

    with pytest.raises(provenance.ProvenanceCatalogError, match="no immutable source"):
        _build(required=(RUN_ID,), event_rows=events, source_rows=[])


def test_empty_committee_graph_derives_from_exact_members_capture_pages():
    publisher_run_id = "catalog-parties-empty-publisher-001"
    member_run_id = "catalog-members-capture-001"
    empty_payload = ""
    empty_hash = hashlib.sha256(empty_payload.encode()).hexdigest()
    page_sources = [
        {
            "source_hash": hashlib.sha256(b"members page zero").hexdigest(),
            "observed_at": "2026-10-07T14:00:00+00:00",
            "endpoint": "members",
            "run_id": member_run_id,
            "evidence_pointer": "file:///raw/members/run-1/skip-0.json",
            "source_url": "https://api.oireachtas.ie/v1/members",
            "request_parameters": {"limit": 100, "skip": 0},
            "versions": {
                "etl_version": "0.8.0",
                "ontology_version": "members.owl.ttl@empty-test",
                "mapping_version": "member_mapping.csv@empty-test",
            },
        },
        {
            "source_hash": hashlib.sha256(b"members page one").hexdigest(),
            "observed_at": "2026-10-07T14:00:01+00:00",
            "endpoint": "members",
            "run_id": member_run_id,
            "evidence_pointer": "file:///raw/members/run-1/skip-100.json",
            "source_url": "https://api.oireachtas.ie/v1/members",
            "request_parameters": {"limit": 100, "skip": 100},
            "versions": {
                "etl_version": "0.8.0",
                "ontology_version": "members.owl.ttl@empty-test",
                "mapping_version": "member_mapping.csv@empty-test",
            },
        },
    ]
    events = [{
        "event_type": "source_observed",
        "run_id": member_run_id,
        "endpoint": "members",
        "source_hash": source["source_hash"],
        "observed_at": source["observed_at"],
        "evidence_pointer": source["evidence_pointer"],
    } for source in page_sources]
    events.append({
        "event_type": "graph_published",
        "run_id": publisher_run_id,
        "endpoint": "committees",
        "graph_iri": COMMITTEES_GRAPH,
        "payload_hash": empty_hash,
        "entity_iri": None,
        "source_hash": None,
        "details": {"member_source_run_id": member_run_id},
    })
    runs = [
        {
            "run_id": member_run_id,
            "endpoint": "members",
            "run_kind": "full_refresh",
            "is_complete": 1,
            "started_at": "2026-10-07T13:59:00+00:00",
            "completed_at": "2026-10-07T14:01:00+00:00",
            "status": "succeeded",
            "outcome": "success",
            "parameters": {"source": "api"},
        },
        {
            "run_id": publisher_run_id,
            "endpoint": "parties",
            "run_kind": "full_refresh",
            "is_complete": 1,
            "started_at": "2026-10-07T14:02:00+00:00",
            "completed_at": "2026-10-07T14:03:00+00:00",
            "status": "succeeded",
            "outcome": "success",
            "parameters": {"source": "api"},
        },
    ]
    versions = [{
        "graph_iri": COMMITTEES_GRAPH,
        "payload_hash": empty_hash,
        "payload": empty_payload,
        "endpoint": "committees",
        "entity_iri": None,
        "source_hash": None,
        "first_run_id": publisher_run_id,
        "created_at": "2026-10-07T14:02:30+00:00",
    }]

    catalog = provenance.build_provenance_catalog_from_records(
        events, versions, runs, page_sources, require_source_run_ids=(publisher_run_id,))
    graph_version = URIRef(provenance.graph_version_iri(COMMITTEES_GRAPH, empty_hash))
    source_iris = {
        provenance.source_observation_iri(source["source_hash"], source["observed_at"])
        for source in page_sources
    }
    assert set(catalog.objects(graph_version, PROV.wasDerivedFrom)) == source_iris
    assert (graph_version, PROV.wasGeneratedBy,
            URIRef(run_resource_iri(publisher_run_id))) in catalog
    assert not list(catalog.objects(
        URIRef(run_resource_iri(publisher_run_id)), PROV.used))
    assert not any(source["endpoint"] == "committees" for source in page_sources)

    with pytest.raises(provenance.ProvenanceCatalogError,
                       match="no immutable Members capture source observations"):
        provenance.build_provenance_catalog_from_records(
            [events[-1]], versions, runs, [],
            require_source_run_ids=(publisher_run_id,))


def test_nonempty_shared_graph_still_requires_complete_entity_version_coverage():
    committee_run_id = "catalog-committee-nonempty-001"
    member_run_id = "catalog-members-capture-002"
    graph = Graph()
    committee = URIRef("https://data.oireachtas.ie/ie/oireachtas/committee/dail/1/test")
    graph.add((committee, RDF.type, MEMBERS.Committee))
    payload = provenance.ntriples(graph)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    runs = [
        {
            "run_id": member_run_id, "endpoint": "members", "is_complete": 1,
            "parameters": {"source": "api"}, "status": "succeeded", "outcome": "success",
        },
        {
            "run_id": committee_run_id, "endpoint": "committees", "is_complete": 1,
            "parameters": {"source": "members", "source_run_id": member_run_id},
        },
    ]
    version = {
        "graph_iri": COMMITTEES_GRAPH, "payload_hash": digest, "payload": payload,
        "endpoint": "committees", "entity_iri": None, "source_hash": None,
        "first_run_id": committee_run_id,
    }
    event = {
        "event_type": "graph_published", "run_id": committee_run_id,
        "endpoint": "committees", "graph_iri": COMMITTEES_GRAPH,
        "payload_hash": digest, "entity_iri": None, "source_hash": None,
    }
    with pytest.raises(provenance.ProvenanceCatalogError,
                       match="lacks immutable entity-version lineage"):
        provenance.build_provenance_catalog_from_records(
            [event], [version], runs, [],
            require_source_run_ids=(committee_run_id,))


def test_source_event_without_canonical_source_observation_fails_closed():
    with pytest.raises(provenance.ProvenanceCatalogError,
                       match="no matching immutable observation"):
        _build(source_rows=[], event_rows=_events())


@pytest.mark.parametrize("bad_metadata", [
    {"access_token": "secret-value"},
    {"headers": {"Authorization": "Bearer abcdefghijklmnop"}},
])
def test_secret_bearing_request_metadata_is_never_projected(bad_metadata):
    request = {"limit": 100, **bad_metadata}
    with pytest.raises(provenance.ProvenanceCatalogError, match="secret-bearing|authentication secret"):
        _build(source_rows=[_source(request_parameters=request)])


def test_secret_url_query_is_rejected_instead_of_being_published():
    with pytest.raises(provenance.ProvenanceCatalogError, match="secret-bearing"):
        _build(source_rows=[_source(source_url="https://api.oireachtas.ie/v1/members?access_token=secret")])


def test_tampered_graph_version_payload_is_rejected():
    with pytest.raises(provenance.ProvenanceCatalogError, match="payload is corrupt"):
        _build(version_rows=[_version(payload=PAYLOAD + "# tampered")])


def test_catalog_graph_does_not_contain_its_own_recursive_graph_version():
    self_payload = "<https://example.test/catalog> <https://example.test/p> <https://example.test/o> .\n"
    self_hash = hashlib.sha256(self_payload.encode()).hexdigest()
    versions = [_version(), {
        "graph_iri": PROVENANCE_GRAPH_IRI,
        "payload_hash": self_hash,
        "payload": self_payload,
        "endpoint": "members",
        "entity_iri": None,
        "source_hash": None,
        "first_run_id": RUN_ID,
        "created_at": "2026-10-07T12:00:30Z",
    }]
    events = _events() + [{
        "event_type": "graph_published", "run_id": RUN_ID,
        "endpoint": "members", "graph_iri": PROVENANCE_GRAPH_IRI,
        "payload_hash": self_hash, "entity_iri": None, "source_hash": None,
    }]
    graph = _build(version_rows=versions, event_rows=events)
    assert URIRef(provenance.graph_version_iri(PROVENANCE_GRAPH_IRI, self_hash)) not in set(graph.subjects())


def test_builder_reads_canonical_core_state_records_read_only(tmp_path):
    database = tmp_path / "core.sqlite"
    member_iri = "https://data.oireachtas.ie/ie/oireachtas/member/id/Test.D.2024-01-01"
    graph_iri = member_graph_iri({"uri": member_iri, "memberCode": "Test.D.2024-01-01"})
    source_hash = hashlib.sha256(b"member record").hexdigest()
    payload = (f"<{member_iri}> <https://example.test/p> "
               "<https://example.test/o> .\n")
    with CoreStateStore(database) as store:
        run_id = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api", "api_url": "https://api.oireachtas.ie/v1/members"},
            versions={
                "etl_version": "0.6.0",
                "ontology_version": "agents.owl.ttl@2026-10-07",
                "mapping_version": "member_mapping.csv@2026-10-07",
            },
        )
        store.observe_resource(
            "members", member_iri, graph_iri, source_hash, run_id,
            observed_at=OBSERVED_AT,
            evidence_pointer="file:///raw/members/sha256/member-page.json#/results/0",
            request_parameters={"skip": 0, "limit": 100},
        )
        payload_hash = store.mark_publication_dirty(
            "members", member_iri, source_hash=source_hash,
            graph_iri=graph_iri, payload=payload, contract_version=1,
        )
        store.complete_publication(
            "members", member_iri, source_hash=source_hash,
            graph_iri=graph_iri, payload_hash=payload_hash, contract_version=1,
        )
        store.finish_run(run_id, success=True)

        before = store.connection.execute(
            "SELECT COUNT(*) FROM provenance_event").fetchone()[0]
        graph = provenance.build_provenance_catalog(
            store, require_source_run_ids=(run_id,))
        after = store.connection.execute(
            "SELECT COUNT(*) FROM provenance_event").fetchone()[0]

        version_iri = provenance.graph_version_iri(graph_iri, payload_hash)
        assert (URIRef(version_iri), PROV.wasGeneratedBy,
                URIRef(run_resource_iri(run_id))) in graph
        assert len(list(graph.objects(URIRef(version_iri), PROV.wasDerivedFrom))) == 1
        assert before == after  # projection did not mutate Core State


class _Boundary:
    def __init__(self, events, *, bad_hash=False):
        self.events = events
        self.bad_hash = bad_hash

    def mark_dirty(self, graph_iri, payload):
        self.events.append(("dirty", graph_iri, payload))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return "0" * 64 if self.bad_hash else digest

    def mark_clean(self, graph_iri, payload_hash):
        self.events.append(("clean", graph_iri, payload_hash))


class _Loader:
    def __init__(self, events):
        self.events = events

    def replace(self, graph_iri, payload, *, content_type):
        self.events.append(("put", graph_iri, payload, content_type))


def test_verified_publisher_obeys_dirty_put_verify_clean_order(monkeypatch):
    events = []
    graph = _build(required=(RUN_ID,))
    loader = _Loader(events)

    def verify(_client, graph_iri, payload):
        events.append(("verify", graph_iri, payload))

    monkeypatch.setattr("oireachtas_etl.competency.verify_core_graph", verify)
    digest = provenance.publish_provenance_catalog(
        graph, publication_boundary=_Boundary(events), loader=loader, client=object())

    assert digest == hashlib.sha256(events[0][2].encode()).hexdigest()
    assert [item[0] for item in events] == ["dirty", "put", "verify", "clean"]
    assert events[0][1] == PROVENANCE_GRAPH_IRI
    assert events[1][1] == PROVENANCE_GRAPH_IRI
    assert events[1][3] == "application/n-triples"
    assert events[3] == ("clean", PROVENANCE_GRAPH_IRI, digest)


def test_verification_failure_keeps_state_dirty(monkeypatch):
    events = []
    graph = _build(required=(RUN_ID,))

    def fail_verification(_client, _graph_iri, _payload):
        events.append(("verify",))
        raise RuntimeError("remote graph mismatch")

    monkeypatch.setattr("oireachtas_etl.competency.verify_core_graph", fail_verification)
    with pytest.raises(RuntimeError, match="remote graph mismatch"):
        provenance.publish_provenance_catalog(
            graph, publication_boundary=_Boundary(events),
            loader=_Loader(events), client=object())
    assert [item[0] for item in events] == ["dirty", "put", "verify"]


def test_wrong_core_state_dirty_hash_stops_before_remote_put():
    events = []
    with pytest.raises(provenance.ProvenanceCatalogError, match="wrong catalog payload hash"):
        provenance.publish_provenance_catalog(
            _build(required=(RUN_ID,)), publication_boundary=_Boundary(events, bad_hash=True),
            loader=_Loader(events), client=object())
    assert [item[0] for item in events] == ["dirty"]


def test_validation_rejects_blank_nodes_before_marking_dirty():
    graph = Graph()
    graph.add((BNode(), URIRef("https://example.test/p"), Literal("bad")))
    events = []
    with pytest.raises(provenance.ProvenanceCatalogError, match="blank nodes"):
        provenance.publish_provenance_catalog(
            graph, publication_boundary=_Boundary(events),
            loader=_Loader(events), client=object())
    assert events == []
