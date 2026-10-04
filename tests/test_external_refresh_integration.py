"""Phase 5 Tranche 3: core-to-reconciliation handoff and independent freshness."""
from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

from oireachtas_etl import cli
from oireachtas_etl.reconciliation import (
    ReconciliationStore,
    institution_links_graph,
    party_external_graph_iri,
    party_links_graph,
    reconcile_party_records,
    reconcile_records,
    resolve,
    resolve_institution,
    resolve_party,
)
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.transforms.common import MEMBERS


ROOT = Path(__file__).resolve().parents[1]
MEMBER = json.loads((ROOT / "data/api_examples/member.json").read_text())
PARTY = next(
    row for row in json.loads((ROOT / "data/api_examples/parties.json").read_text())["results"]
    if row["party"]["partyCode"] == "Fine_Gael"
)
DAIL = "https://data.oireachtas.ie/house/dail"
QID = "Q832321"


class _FusekiLoader:
    def __init__(self, calls):
        self.calls = calls

    def replace(self, graph_iri, payload, **_kwargs):
        self.calls.append((graph_iri, payload))


class _NoopClient:
    def __init__(self, *_args, **_kwargs):
        pass


def _mock_core_publication(monkeypatch, calls):
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", lambda *a, **k: _FusekiLoader(calls))
    monkeypatch.setattr(cli, "FusekiSparqlClient", _NoopClient)
    monkeypatch.setattr(cli, "verify_member_competency", lambda *_: None)
    monkeypatch.setattr(cli, "verify_parties_competency", lambda *_: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *_: None)
    party_policy = cli.REFERENCE_ENDPOINTS["parties"]
    monkeypatch.setitem(cli.REFERENCE_ENDPOINTS, "parties",
                        (*party_policy[:4], lambda *_: None, *party_policy[5:]))


def _member_args(tmp_path, fixture=None):
    return Namespace(
        fixture=str(fixture or ROOT / "data/api_examples/member.json"), offline=False,
        raw_dir=str(tmp_path / "raw"), output_nq=None, output_ttl=None,
        fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query",
        state_db=str(tmp_path / "core.sqlite"),
        reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"),
        office_state_file=str(tmp_path / "offices.sqlite"),
    )


def _party_args(tmp_path, fixture):
    return Namespace(
        endpoint="parties", fixture=str(fixture), offline=False,
        raw_dir=str(tmp_path / "raw"), output_nq=None, output_ttl=None,
        fuseki_gsp_url="http://local.test/data", fuseki_sparql_url="http://local.test/query",
        state_db=str(tmp_path / "core.sqlite"),
        reconciliation_state_file=str(tmp_path / "reconciliation.sqlite"),
    )


class _ExternalPublisher:
    def __init__(self):
        self.calls = []
        self.graphs = {}

    def replace(self, graph_iri, payload, **_kwargs):
        self.calls.append((graph_iri, payload))
        self.graphs[graph_iri] = payload


class _ExternalGate:
    def __init__(self, publisher):
        self.publisher = publisher

    def query(self, query):
        graph_iri = query.split("GRAPH <", 1)[1].split(">", 1)[0]
        payload = self.publisher.graphs.get(graph_iri, "")
        graph = Graph().parse(data=payload, format="nt") if payload else Graph()
        return [{
            "s": {"type": "uri", "value": str(s)},
            "p": {"type": "uri", "value": str(p)},
            "o": {"type": "uri", "value": str(o)},
        } for s, p, o in graph]


class _MemberWikidata:
    def __init__(self, qid=QID, *, error=None, target=None):
        self.qid, self.error, self.target = qid, error, target
        self.lookup_calls = 0
        self.entity_calls = 0

    def lookup_member_code(self, _code):
        self.lookup_calls += 1
        if self.error:
            raise self.error
        return [self.qid]

    def entity(self, qid):
        self.entity_calls += 1
        if self.error:
            raise self.error
        return self.target or {"entities": {qid: {"id": qid}}}


class _PartyWikidata:
    def __init__(self, *, target=None):
        self.target = target
        self.entity_calls = []

    def lookup_party_candidates(self, _record):
        raise AssertionError("an accepted review must not run candidate discovery")

    def entity(self, qid):
        self.entity_calls.append(qid)
        return self.target or {"entities": {qid: {"id": qid}}}


class _EmptyDbpedia:
    def resolve_wikidata(self, _qid):
        return []


def test_member_core_publication_hands_off_due_and_external_retry_is_independent(
    tmp_path, monkeypatch, capsys,
):
    core_calls = []
    _mock_core_publication(monkeypatch, core_calls)
    args = _member_args(tmp_path)
    assert cli.run_members(args) == 0
    capsys.readouterr()

    identity = MEMBER["member"]["uri"]
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        due = store.get_record("member", identity)
        assert due is not None and due["state"] == "pending"
        assert due["next_recheck_at"] <= datetime.now(timezone.utc).isoformat()
        assert due["identity_hash"] == ""  # no external resolution has been attempted

    with CoreStateStore(Path(args.state_db)) as state:
        published_before = state.get_resource("members", identity)
        assert published_before["publication_state"] == "clean"
        source_hash_before = published_before["published_source_hash"]

    # Core ETL did no Wikidata/DBpedia work: a subsequent external outage
    # becomes a reconciliation retry and does not dirty or republish core RDF.
    class Down:
        def lookup_member_code(self, _code):
            raise OSError("Wikidata unavailable")

    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        pending = reconcile_records([MEMBER], store, {}, "review-v1", Down(), _EmptyDbpedia())
        assert pending[0][1].state == "pending"
        retry_deadline = store.get_record("member", identity)["next_recheck_at"]
        assert retry_deadline > datetime.now(timezone.utc).isoformat()

    # Re-reading unchanged core data neither resets the external retry cadence
    # nor transforms/publishes the authoritative graph again.
    assert cli.run_members(args) == 0
    capsys.readouterr()
    assert len(core_calls) == 1
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        assert store.get_record("member", identity)["next_recheck_at"] == retry_deadline

    # Once the independent retry is due, reconciliation can restore links
    # without requiring authoritative graph generation or publication.
    recovered = _MemberWikidata()
    publisher = _ExternalPublisher()
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        store.connection.execute(
            "UPDATE reconciliation_record SET next_recheck_at='2000-01-01T00:00:00+00:00' "
            "WHERE entity_kind='member' AND local_iri=?", (identity,),
        )
        store.connection.commit()
        result = reconcile_records(
            [MEMBER], store, {}, "review-v1", recovered, _EmptyDbpedia(),
            publish=publisher, competency_client=_ExternalGate(publisher),
        )
        row = store.get_record("member", identity)
        assert result[0][1].state == "accepted"
        assert row["publication_state"] == "clean"
        assert row["next_recheck_at"] > (datetime.now(timezone.utc) + timedelta(days=89)).isoformat()
    assert recovered.lookup_calls == 1 and recovered.entity_calls == 1
    assert len(publisher.calls) == 1
    assert len(core_calls) == 1
    with CoreStateStore(Path(args.state_db)) as state:
        current = state.get_resource("members", identity)
        assert current["publication_state"] == "clean"
        assert current["published_source_hash"] == source_hash_before


def test_parties_core_handoff_uses_policy_fingerprint_and_preserves_recheck_cadence(
    tmp_path, monkeypatch, capsys,
):
    core_calls = []
    _mock_core_publication(monkeypatch, core_calls)
    source = tmp_path / "party.json"
    source.write_text(json.dumps([PARTY]))
    args = _party_args(tmp_path, source)
    assert cli.run_reference(args) == 0
    capsys.readouterr()

    local_iri = PARTY["party"]["uri"]
    decisions = {local_iri: {"status": "accepted", "wikidata": QID}}
    external_publisher = _ExternalPublisher()
    wd = _PartyWikidata()
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        due = store.get_record("party", local_iri)
        assert due is not None and due["next_recheck_at"] <= datetime.now(timezone.utc).isoformat()
        accepted = reconcile_party_records(
            [PARTY], store, decisions, "review-v1", wd,
            publish=external_publisher, competency_client=_ExternalGate(external_publisher),
        )
        assert accepted[0][1].state == "accepted"
        next_check = store.get_record("party", local_iri)["next_recheck_at"]
        assert next_check > (datetime.now(timezone.utc) + timedelta(days=89)).isoformat()
    assert wd.entity_calls == [QID]

    # House display labels are outside the existing Party identity fingerprint.
    irrelevant = json.loads(json.dumps(PARTY))
    irrelevant["house"]["showAs"] = "a label that the external-identity policy ignores"
    source.write_text(json.dumps([irrelevant]))
    assert cli.run_reference(args) == 0
    capsys.readouterr()
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        assert store.get_record("party", local_iri)["next_recheck_at"] == next_check

    # Party showAs is identity-relevant under the settled policy; only its
    # existing fingerprint, not the full core source hash, forces a recheck.
    relevant = json.loads(json.dumps(irrelevant))
    relevant["party"]["showAs"] += " revised"
    source.write_text(json.dumps([relevant]))
    assert cli.run_reference(args) == 0
    capsys.readouterr()
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        row = store.get_record("party", local_iri)
        assert row["next_recheck_at"] <= datetime.now(timezone.utc).isoformat()

        # Reconciliation resolves the invalidation and retains the prior graph
        # because the human-approved QID itself did not change.
        reconcile_party_records(
            [relevant], store, decisions, "review-v1", _PartyWikidata(),
            publish=external_publisher, competency_client=_ExternalGate(external_publisher),
        )
        periodic_deadline = store.get_record("party", local_iri)["next_recheck_at"]
        assert periodic_deadline > (datetime.now(timezone.utc) + timedelta(days=89)).isoformat()

        # Accepted rows are selected at their real scheduled recheck. A redirect
        # records a structured retry while preserving the reviewed QID graph.
        store.connection.execute(
            "UPDATE reconciliation_record SET next_recheck_at='2000-01-01T00:00:00+00:00' "
            "WHERE entity_kind='party' AND local_iri=?", (local_iri,),
        )
        store.connection.commit()
        redirect = {"redirects": [{"from": QID, "to": "Q12345"}],
                    "entities": {QID: {"id": "Q12345"}}}
        before_external_puts = len(external_publisher.calls)
        checked = reconcile_party_records(
            [relevant], store, decisions, "review-v1",
            _PartyWikidata(target=redirect), publish=external_publisher,
            competency_client=_ExternalGate(external_publisher),
        )
        retry_row = store.get_record("party", local_iri)
        assert checked[0][1].state == "accepted"
        assert checked[0][1].enrichment_status == "retry"
        errors = json.loads(retry_row["service_errors_json"])
        assert errors[0]["code"] == "redirected"
        assert retry_row["next_recheck_at"] > datetime.now(timezone.utc).isoformat()
        assert len(external_publisher.calls) == before_external_puts
        retained = Graph().parse(data=external_publisher.graphs[party_external_graph_iri(relevant)], format="nt")
        assert set(retained) == {
            (URIRef(local_iri), MEMBERS.recognisedAsParty, URIRef("https://www.wikidata.org/entity/" + QID))
        }

    # Freshness is independent: later external recovery does not regenerate
    # the authoritative Party graph.
    core_puts_before_recovery = len(core_calls)
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        store.connection.execute(
            "UPDATE reconciliation_record SET next_recheck_at='2000-01-01T00:00:00+00:00' "
            "WHERE entity_kind='party' AND local_iri=?", (local_iri,),
        )
        store.connection.commit()
        recovered_wd = _PartyWikidata()
        reconcile_party_records(
            [relevant], store, decisions, "review-v1", recovered_wd,
            publish=external_publisher, competency_client=_ExternalGate(external_publisher),
        )
        assert store.get_record("party", local_iri)["enrichment_status"] == "complete"
        assert store.get_record("party", local_iri)["next_recheck_at"] > (
            datetime.now(timezone.utc) + timedelta(days=89)
        ).isoformat()
        assert recovered_wd.entity_calls == [QID]
    assert len(core_calls) == core_puts_before_recovery


@pytest.mark.parametrize("endpoint", ["members", "parties"])
@pytest.mark.parametrize("failure", ["construction", "mark_due"])
def test_reconciliation_handoff_failure_does_not_fail_core_publication(
    endpoint, failure, tmp_path, monkeypatch, capsys,
):
    """External freshness may lag; core publication and state stay authoritative."""
    core_calls = []
    _mock_core_publication(monkeypatch, core_calls)

    if endpoint == "members":
        args = _member_args(tmp_path)
        identity = MEMBER["member"]["uri"]
        kind = "members"
    else:
        source = tmp_path / "party.json"
        source.write_text(json.dumps([PARTY]))
        args = _party_args(tmp_path, source)
        identity = PARTY["party"]["uri"]
        kind = "parties"

    if failure == "construction":
        def unavailable_store(*_args, **_kwargs):
            raise OSError("reconciliation state unavailable")

        monkeypatch.setattr(cli, "ReconciliationStore", unavailable_store)
    else:
        original = ReconciliationStore.mark_due

        def unavailable_mark_due(self, *args, **kwargs):
            raise OSError("reconciliation handoff unavailable")

        monkeypatch.setattr(ReconciliationStore, "mark_due", unavailable_mark_due)

    # Reconciliation is an independent best-effort handoff. Its failure must
    # neither fail the run nor leave authoritative resource/endpoint state dirty.
    assert (cli.run_members(args) if endpoint == "members" else cli.run_reference(args)) == 0
    capsys.readouterr()
    assert len(core_calls) == 1
    with CoreStateStore(Path(args.state_db)) as state:
        if kind == "members":
            assert state.get_resource(kind, identity)["publication_state"] == "clean"
        else:
            assert state.endpoint_publication("parties")["publication_state"] == "clean"

    # Restore the store interface and reconcile directly from the complete
    # source. This exercises recovery of a missed handoff without rerunning the
    # authoritative refresh (Parties intentionally republishes on every scan).
    monkeypatch.setattr(cli, "ReconciliationStore", ReconciliationStore)
    monkeypatch.setattr(ReconciliationStore, "mark_due", original if failure == "mark_due" else ReconciliationStore.mark_due)
    publisher = _ExternalPublisher()
    decisions = (
        {MEMBER["member"]["memberCode"]: {"status": "accepted", "wikidata": QID}}
        if endpoint == "members"
        else {identity: {"status": "accepted", "wikidata": QID}}
    )
    with ReconciliationStore(Path(args.reconciliation_state_file)) as store:
        if endpoint == "members":
            results = reconcile_records(
                [MEMBER], store, decisions, "review-v1", _MemberWikidata(), _EmptyDbpedia(),
                publish=publisher, competency_client=_ExternalGate(publisher),
            )
        else:
            results = reconcile_party_records(
                [PARTY], store, decisions, "review-v1", _PartyWikidata(),
                publish=publisher, competency_client=_ExternalGate(publisher),
            )
        assert results and results[0][1].state == "accepted"
        row = store.get_record("member" if endpoint == "members" else "party", identity)
        assert row is not None
        assert row["publication_state"] == "clean"
        assert row["next_recheck_at"] > datetime.now(timezone.utc).isoformat()
    assert len(publisher.calls) == 1
    assert len(core_calls) == 1


@pytest.mark.parametrize(
    ("target_state", "expected_code"),
    [
        ("redirected", "redirected"),
        ("missing", "missing"),
        ("disappeared", "disappeared"),
        ("retired", "retired"),
        ("unavailable", "unavailable"),
    ],
)
@pytest.mark.parametrize("entity_kind", ["member", "party", "institution"])
def test_reviewed_targets_retry_structurally_without_replacing_or_clearing_identity(
    entity_kind, target_state, expected_code,
):
    qid = "Q651981" if entity_kind == "institution" else QID
    if target_state == "redirected":
        target = {"redirects": [{"from": qid, "to": "Q12345"}],
                  "entities": {qid: {"id": "Q12345"}}}
    elif target_state == "missing":
        target = {"entities": {qid: {"id": qid, "missing": ""}}}
    elif target_state == "disappeared":
        target = {"entities": {}}
    elif target_state == "retired":
        # The requested identifier resolves to a different current identifier
        # without a redirect record; do not silently adopt the replacement.
        target = {"entities": {qid: {"id": "Q12345"}}}
    else:
        target = None

    class TargetClient:
        def lookup_member_code(self, _code):
            raise AssertionError("a reviewed identity must not run candidate discovery")

        def lookup_party_candidates(self, _record):
            raise AssertionError("a reviewed identity must not run candidate discovery")

        def lookup_institution_candidates(self, _entity):
            raise AssertionError("a reviewed identity must not run candidate discovery")

        def entity(self, _qid):
            if target_state == "unavailable":
                raise OSError("Wikidata unavailable")
            return target

    client = TargetClient()
    if entity_kind == "member":
        wrapper = MEMBER
        decision = {wrapper["member"]["memberCode"]: {"status": "accepted", "wikidata": qid}}
        resolution = resolve(wrapper["member"], decision, client, _EmptyDbpedia())
        from oireachtas_etl.reconciliation import links_graph
        links = links_graph(wrapper["member"], resolution)
        expected_subject = URIRef(wrapper["member"]["uri"])
        expected_predicate = OWL.sameAs
    elif entity_kind == "party":
        wrapper = PARTY
        decision = {wrapper["party"]["uri"]: {"status": "accepted", "wikidata": qid}}
        resolution = resolve_party(wrapper, decision, client)
        links = party_links_graph(wrapper, resolution)
        expected_subject = URIRef(wrapper["party"]["uri"])
        expected_predicate = MEMBERS.recognisedAsParty
    else:
        wrapper = {"institution": {"uri": DAIL}}
        decision = {DAIL: {"status": "accepted", "wikidata": qid}}
        resolution = resolve_institution(wrapper, decision, client)
        links = institution_links_graph(wrapper, resolution)
        expected_subject = URIRef(DAIL)
        expected_predicate = OWL.sameAs

    assert resolution.state == "accepted" and resolution.review_applied
    assert resolution.enrichment_status == "retry"
    assert resolution.evidence["errors"][0]["service"] == "wikidata"
    assert resolution.evidence["errors"][0]["operation"] == "accepted-target-verification"
    assert resolution.evidence["errors"][0]["code"] == expected_code
    assert resolution.evidence["target_verification"]["status"] == "retry"
    assert set(links) == {
        (expected_subject, expected_predicate, URIRef("https://www.wikidata.org/entity/" + qid))
    }


def test_institution_reviewed_identity_checks_target_even_without_optional_wikipedia():
    class Client:
        def __init__(self):
            self.calls = []

        def lookup_institution_candidates(self, _entity):
            raise AssertionError("reviewed identity must not run candidate discovery")

        def entity(self, qid):
            self.calls.append(qid)
            return {"entities": {qid: {"id": qid}}}

    client = Client()
    result = resolve_institution(
        {"institution": {"uri": DAIL}},
        {DAIL: {"status": "accepted", "wikidata": "Q651981"}},
        client,
    )
    assert result.state == "accepted" and result.enrichment_status == "complete"
    assert result.evidence["target_verification"] == {"status": "verified", "qid": "Q651981"}
    assert client.calls == ["Q651981"]
