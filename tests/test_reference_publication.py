from __future__ import annotations

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

import pytest

from oireachtas_etl.reference_coverage import build_reference_census
from oireachtas_etl.reference_publication import (ReferencePublicationError,
                                                  build_development_reference_candidates,
                                                  build_reference_candidates)
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.committees import transform_committees
from oireachtas_etl.transforms.parties import transform_parties


MEMBER_IRI = "https://data.oireachtas.ie/ie/oireachtas/member/id/Current"
CURRENT_PARTY = {
    "party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/35/Example",
              "partyCode": "Example", "showAs": "Current party"},
    "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35",
              "houseCode": "dail", "houseNo": "35"},
}
CURRENT_COMMITTEE = {
    "uri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/current",
    "committeeCode": "C1", "committeeID": 1,
    "committeeDateRange": {"start": "2020-01-01", "end": None},
    "committeeName": [{"nameEn": "Current Committee"}],
}
KNOWN_CONFLICT_COMMITTEE = (
    "https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/"
    "select_committee_on_the_implementation_of_the_good_friday_agreement"
)


def _member(committee: dict | None = None) -> dict:
    return {"member": {"uri": MEMBER_IRI, "memberships": [{"membership": {
        "uri": MEMBER_IRI + "/membership/1",
        "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35",
                  "houseCode": "dail", "houseNo": "35"},
        "parties": [{"party": dict(CURRENT_PARTY["party"])}],
        "represents": [],
        "committees": [dict(committee or CURRENT_COMMITTEE)],
    }}]}}


def test_candidate_graphs_retain_absent_history_and_replace_current_subjects_cleanly():
    historical_party = {
        "party": {"uri": "https://data.oireachtas.ie/ie/oireachtas/party/dail/30/Old",
                  "partyCode": "Old", "showAs": "Historical party"},
        "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/30",
                  "houseCode": "dail", "houseNo": "30"},
    }
    previous_party_graph = transform_parties([historical_party, {
        **CURRENT_PARTY,
        "party": {**CURRENT_PARTY["party"], "showAs": "Stale party label"},
    }])
    old_committee = {
        "uri": "https://data.oireachtas.ie/ie/oireachtas/committee/dail/30/old_committee",
        "committeeCode": "OLD", "committeeID": 9,
        "committeeDateRange": {"start": "2016-01-01", "end": "2020-01-01"},
        "committeeName": [{"nameEn": "Historical committee"}],
    }
    previous_committee_graph = transform_committees([old_committee])

    census = build_reference_census(
        member_records=[_member()], party_records=[CURRENT_PARTY],
        member_capture_complete=True, party_capture_complete=True,
    )
    member_graph = Graph()
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.memberOfCollection,
                      URIRef(CURRENT_PARTY["party"]["uri"])))
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.isCommitteeMembershipOf,
                      URIRef(CURRENT_COMMITTEE["uri"])))

    result = build_reference_candidates(
        census, member_graph=member_graph,
        previous_graphs={"parties": previous_party_graph,
                         "committees": previous_committee_graph},
    )
    party_graph, committee_graph = result["graphs"]["parties"], result["graphs"]["committees"]
    current_party = URIRef(CURRENT_PARTY["party"]["uri"])
    historical = URIRef(historical_party["party"]["uri"])
    assert (historical, SKOS.prefLabel, None) in party_graph
    assert (current_party, SKOS.prefLabel, None) in party_graph
    assert (current_party, SKOS.prefLabel, Literal("Stale party label", lang="en")) not in party_graph
    assert (URIRef(old_committee["uri"]), RDF.type, MEMBERS.Committee) in committee_graph
    assert result["closure"]["closed"] == 2


def test_material_conflict_fails_before_candidate_graphs_are_returned():
    first, second = _member(), _member()
    second["member"]["memberships"][0]["membership"]["committees"][0]["committeeID"] = 2
    census = build_reference_census(
        member_records=[first, second], member_capture_complete=True,
    )
    with pytest.raises(ReferencePublicationError, match="census conflicts block publication"):
        build_reference_candidates(census, member_graph=Graph())


def test_known_committee_conflict_blocks_authoritative_candidates_but_is_quarantined_for_dev():
    first_committee = {**CURRENT_COMMITTEE, "uri": KNOWN_CONFLICT_COMMITTEE}
    second_committee = {**first_committee, "committeeID": 2}
    source_members = [
        _member(),
        _member(committee=first_committee),
        _member(committee=second_committee),
    ]
    party = dict(CURRENT_PARTY)
    representation = {
        "constituencyOrPanel": {
            "uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35/constituency/Example",
            "representType": "constituency", "representCode": "Example",
            "showAs": "Example constituency",
        },
        "house": {"uri": "https://data.oireachtas.ie/ie/oireachtas/house/dail/35",
                  "houseCode": "dail", "houseNo": "35"},
    }
    census = build_reference_census(
        member_records=source_members, party_records=[party],
        constituency_records=[representation], member_capture_complete=True,
        party_capture_complete=True, constituency_capture_complete=True,
    )
    # The development boundary independently removes conflicted identities
    # even if a future/custom census producer accidentally includes a record.
    census["records"]["committees"].append(first_committee)
    member_graph = Graph()
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.memberOfCollection,
                      URIRef(CURRENT_PARTY["party"]["uri"])))
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.isRepresentativeFrom,
                      URIRef(representation["constituencyOrPanel"]["uri"])))
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.isCommitteeMembershipOf,
                      URIRef(CURRENT_COMMITTEE["uri"])))
    member_graph.add((URIRef(MEMBER_IRI), MEMBERS.isCommitteeMembershipOf,
                      URIRef(KNOWN_CONFLICT_COMMITTEE)))

    # The existing authoritative API remains global fail-closed.
    with pytest.raises(ReferencePublicationError,
                       match="reference census conflicts block publication"):
        build_reference_candidates(census, member_graph=member_graph)

    result = build_development_reference_candidates(census, member_graph=member_graph)
    parties = result["graphs"]["parties"]
    constituencies = result["graphs"]["constituencies"]
    committees = result["graphs"]["committees"]
    party_iri = URIRef(CURRENT_PARTY["party"]["uri"])
    representation_iri = URIRef(representation["constituencyOrPanel"]["uri"])
    assert (party_iri, RDF.type, MEMBERS.ParliamentaryParty) in parties
    assert (representation_iri, RDF.type, MEMBERS.DailConstituency) in constituencies
    assert (URIRef(CURRENT_COMMITTEE["uri"]), RDF.type, MEMBERS.Committee) in committees
    assert not list(committees.triples((URIRef(KNOWN_CONFLICT_COMMITTEE), None, None)))
    # Quarantine applies only to the owner graph; source Member references remain.
    assert (URIRef(MEMBER_IRI), MEMBERS.isCommitteeMembershipOf,
            URIRef(KNOWN_CONFLICT_COMMITTEE)) in member_graph
    status = result["development_status"]
    assert status["authoritative"] is False
    assert status["reference_closure"] == "NOT authoritative / not complete"
    assert status["quarantined_conflict_count"] == 1
    assert status["quarantined_conflicts"][0]["canonical_iri"] == KNOWN_CONFLICT_COMMITTEE
    assert "committeeID" in status["quarantined_conflicts"][0]["reason"]
    assert status["unresolved_reference_count"] == 1
    assert status["unresolved_references"][0]["canonical_iri"] == KNOWN_CONFLICT_COMMITTEE


def test_dirty_shared_reference_graph_replays_the_exact_hash_verified_payload(
        tmp_path, monkeypatch):
    import hashlib
    import json

    from oireachtas_etl import cli
    from oireachtas_etl.config import PARTIES_GRAPH
    from oireachtas_etl.serialization import ntriples
    from oireachtas_etl.state import CoreStateStore

    graph = transform_parties([CURRENT_PARTY])
    payload = ntriples(graph)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    replacements = []
    verifications = []

    class Loader:
        def replace(self, graph_iri, raw, *, content_type):
            replacements.append((graph_iri, raw, content_type))

    class Client:
        def construct_graph(self, graph_iri):
            assert graph_iri != PARTIES_GRAPH
            return Graph()

    monkeypatch.setattr(
        cli, "verify_core_graph",
        lambda client, graph_iri, raw: verifications.append((graph_iri, raw)))
    with CoreStateStore(tmp_path / "core.sqlite") as store:
        assert store.mark_endpoint_dirty(
            "parties", PARTIES_GRAPH, payload,
            coverage_authoritative=True) == digest
        previous = cli._previous_reference_graphs(store, Client(), Loader())
        metadata = store.endpoint_publication("parties")
        assert metadata["publication_state"] == "clean"
        assert metadata["published_payload"] == payload
        assert metadata["coverage_authoritative"] is True
        assert set(previous["parties"]) == set(graph)
    assert replacements == [(PARTIES_GRAPH, payload, "application/n-triples")]
    assert verifications == [(PARTIES_GRAPH, payload)]


def test_legacy_clean_reference_state_recovers_remote_graph_by_payload_hash(
        tmp_path, monkeypatch):
    import json

    from oireachtas_etl import cli
    from oireachtas_etl.config import PARTIES_GRAPH
    from oireachtas_etl.serialization import ntriples
    from oireachtas_etl.state import CoreStateStore

    graph = transform_parties([CURRENT_PARTY])
    payload = ntriples(graph)

    class Loader:
        def replace(self, *_args, **_kwargs):
            raise AssertionError("a clean legacy graph must not be replaced during recovery")

    class Client:
        def construct_graph(self, graph_iri):
            if graph_iri == PARTIES_GRAPH:
                return graph
            return Graph()

    with CoreStateStore(tmp_path / "core.sqlite") as store:
        digest = store.mark_endpoint_dirty("parties", PARTIES_GRAPH, payload)
        store.complete_endpoint_publication("parties", PARTIES_GRAPH, digest)
        metadata = store.endpoint_publication("parties")
        metadata.pop("published_payload")
        store.connection.execute(
            "UPDATE endpoint_state SET publication_metadata_json=? WHERE endpoint='parties'",
            (json.dumps(metadata, sort_keys=True),))
        monkeypatch.setattr(cli, "verify_core_graph", lambda *_args: None)
        previous = cli._previous_reference_graphs(store, Client(), Loader())
        assert set(previous["parties"]) == set(graph)


def test_identical_graph_can_gain_complete_member_coverage_after_verification(
        tmp_path, monkeypatch):
    from oireachtas_etl import cli
    from oireachtas_etl.config import PARTIES_GRAPH
    from oireachtas_etl.serialization import ntriples
    from oireachtas_etl.state import CoreStateStore

    graph = transform_parties([CURRENT_PARTY])
    payload = ntriples(graph)
    puts = []

    class Loader:
        def replace(self, graph_iri, raw, **kwargs):
            puts.append((graph_iri, raw))

    monkeypatch.setattr(cli, "verify_core_graph", lambda *_args: None)
    with CoreStateStore(tmp_path / "core.sqlite") as store:
        digest = store.mark_endpoint_dirty(
            "parties", PARTIES_GRAPH, payload, coverage_authoritative=False)
        store.complete_endpoint_publication(
            "parties", PARTIES_GRAPH, digest, coverage_authoritative=False)
        count = cli._publish_reference_graphs(
            {"parties": graph}, store=store, loader=Loader(), client=object(),
            coverage_authoritative=True, endpoints=("parties",))
        assert count == 1 and puts == [(PARTIES_GRAPH, payload)]
        assert store.endpoint_publication("parties")["coverage_authoritative"] is True

        # A fixture that produces byte-identical RDF cannot invalidate the
        # already accepted complete-source evidence or cause needless PUTs.
        count = cli._publish_reference_graphs(
            {"parties": graph}, store=store, loader=Loader(), client=object(),
            coverage_authoritative=False, endpoints=("parties",))
        assert count == 0 and len(puts) == 1
        assert store.endpoint_publication("parties")["coverage_authoritative"] is True


def test_older_member_capture_cannot_regress_owner_graph_after_failed_run(
        tmp_path, monkeypatch):
    from oireachtas_etl import cli
    from oireachtas_etl.config import PARTIES_GRAPH
    from oireachtas_etl.serialization import ntriples
    from oireachtas_etl.state import CoreStateStore

    graph = transform_parties([CURRENT_PARTY])
    payload = ntriples(graph)
    puts = []

    class Loader:
        def replace(self, graph_iri, raw, **kwargs):
            puts.append((graph_iri, raw))

    monkeypatch.setattr(cli, "verify_core_graph", lambda *_args: None)
    with CoreStateStore(tmp_path / "core.sqlite") as store:
        first = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api"},
            started_at="2026-10-01T00:00:00+00:00")
        store.finish_run(first, success=True)
        newer_failed = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api"},
            started_at="2026-10-02T00:00:00+00:00")
        digest = store.mark_endpoint_dirty(
            "parties", PARTIES_GRAPH, payload, coverage_authoritative=True,
            member_source_run_id=newer_failed)
        store.complete_endpoint_publication(
            "parties", PARTIES_GRAPH, digest, coverage_authoritative=True)
        store.finish_run(newer_failed, success=False, error="Member graph PUT failed")

        with pytest.raises(ValueError, match="older Members run"):
            cli._publish_reference_graphs(
                {"parties": graph}, store=store, loader=Loader(), client=object(),
                coverage_authoritative=True, endpoints=("parties",),
                member_source_run_id=first)
        assert puts == []
        assert store.endpoint_publication("parties")["member_source_run_id"] == newer_failed

        newest = store.start_run(
            "members", "full_refresh", is_complete=True,
            parameters={"source": "api"},
            started_at="2026-10-03T00:00:00+00:00")
        count = cli._publish_reference_graphs(
            {"parties": graph}, store=store, loader=Loader(), client=object(),
            coverage_authoritative=True, endpoints=("parties",),
            member_source_run_id=newest)
        assert count == 0 and puts == []
        assert store.endpoint_publication("parties")["member_source_run_id"] == newest
        store.finish_run(newest, success=True)
