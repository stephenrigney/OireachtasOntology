"""Durable local per-Bill graph replacement, replay and ownership isolation."""
from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest
from rdflib import Graph, URIRef

from oireachtas_etl.bill_sponsor_publication import BillSponsorPublication
from oireachtas_etl.bill_sponsor_reconciliation import BillSponsorStore, bill_sponsor_graph_iri
from oireachtas_etl.transforms.common import MEMBERS


ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
BILL = RECORD["bill"]["uri"]
LOCAL = bill_sponsor_graph_iri(RECORD["bill"])
PART = URIRef(BILL + "#process#sponsor-old")
OFFICE = URIRef("https://data.oireachtas.ie/office/o-000003")


def graph(part=PART):
    result = Graph()
    result.add((part, MEMBERS.reconciledSponsorOffice, OFFICE))
    return result


class Loader:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.graphs = {}
        self.calls = []

    def replace(self, iri, payload, **_kwargs):
        self.calls.append(iri)
        if self.fail:
            raise RuntimeError("injected PUT interruption")
        self.graphs[iri] = Graph().parse(data=payload, format="nt")


class Client:
    def __init__(self, loader):
        self.loader = loader

    def query(self, sparql):
        iri = sparql.split("GRAPH <", 1)[1].split(">", 1)[0]
        return [{key: {"type": "uri", "value": str(term)}
                 for key, term in zip(("s", "p", "o"), triple)}
                for triple in self.loader.graphs.get(iri, Graph())]


def test_dirty_replay_and_complete_local_graph_replacement(tmp_path):
    path = tmp_path / "sponsor.sqlite"
    loader = Loader(fail=True)
    client = Client(loader)
    with BillSponsorStore(path) as store:
        publication = BillSponsorPublication(store)
        with pytest.raises(RuntimeError, match="interruption"):
            publication.publish(BILL, LOCAL, graph(), "evidence-1", loader, client)
        assert publication.row(BILL)["state"] == "dirty"
        assert publication.row(BILL)["pending_payload"]
    loader.fail = False
    with BillSponsorStore(path) as store:
        publication = BillSponsorPublication(store)
        assert publication.replay_missing(set(), loader, client) == [BILL]
        assert publication.row(BILL)["state"] == "clean"
        assert not publication.publish(BILL, LOCAL, graph(), "evidence-1", loader, client)
        changed = graph(URIRef(BILL + "#process#sponsor-new"))
        assert publication.publish(BILL, LOCAL, changed, "evidence-2", loader, client)
        assert set(loader.graphs[LOCAL]) == set(changed)
        assert not list(loader.graphs[LOCAL].triples((PART, None, None)))
        assert publication.publish(BILL, LOCAL, Graph(), "evidence-3", loader, client)
        assert len(loader.graphs[LOCAL]) == 0


def test_unrelated_graph_and_corrupt_replay_are_never_replaced(tmp_path):
    with BillSponsorStore(tmp_path / "sponsor.sqlite") as store:
        publication = BillSponsorPublication(store)
        loader = Loader()
        client = Client(loader)
        other = "https://data.oireachtas.ie/graph/bill/2025/61/office-reconciliation"
        loader.graphs[other] = graph()
        assert publication.publish(BILL, LOCAL, graph(), "evidence", loader, client)
        assert set(loader.graphs[other]) == set(graph())
        with pytest.raises(ValueError, match="identity"):
            publication.mark_dirty(BILL, other, graph(), "wrong")
        publication.mark_dirty(BILL, LOCAL, graph(), "changed")
        store.connection.execute("UPDATE bill_sponsor_publication SET pending_hash=? WHERE bill_iri=?",
                                 ("tampered", BILL))
        with pytest.raises(ValueError, match="intact"):
            publication.replay_missing(set(), loader, client)
        assert set(loader.graphs[other]) == set(graph())


def test_complete_absence_is_reported_without_clearing_prior_local_state(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    fixture = tmp_path / "bill.json"
    fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}},
                                   "results": [RECORD]}))
    args = Namespace(offline=True, publish=False, fixture=str(fixture),
                     raw_dir=str(tmp_path / "raw"), registry_file=None,
                     review_file=None, bill_state_file=str(tmp_path / "bill-local.sqlite"),
                     state_db=None, office_state_file=None, responses_file=None,
                     output_nq=None, fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert cli.run_reconcile_bills_local(args) == 0
    capsys.readouterr()
    with BillSponsorStore(args.bill_state_file) as store:
        publication = BillSponsorPublication(store)
        prior = store.observations(BILL)
        publication.mark_dirty(BILL, LOCAL, graph(), "pending-before-absence")
    args.offline = False
    args.fixture = None
    monkeypatch.setattr(cli, "_local_sponsor_source", lambda *_: ([], True))
    assert cli.run_reconcile_bills_local(args) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["missing_retained_review_required"] == [BILL]
    with BillSponsorStore(args.bill_state_file) as store:
        assert store.observations(BILL) == prior
        assert BillSponsorPublication(store).row(BILL)["state"] == "dirty"
        assert dict(store.connection.execute(
            "SELECT source_presence, review_required FROM bill_sponsor_presence WHERE bill_iri=?",
            (BILL,)).fetchone()) == {"source_presence": "missing", "review_required": 1}


def test_local_cli_dispatch_never_uses_member_external_reconciliation(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    fixture = tmp_path / "bill.json"
    fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}},
                                   "results": [RECORD]}))
    monkeypatch.setattr(cli, "run_reconcile_members",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Member external dispatch")))
    assert cli.main(["reconcile", "bills-local", "--offline", "--fixture", str(fixture),
                     "--raw-dir", str(tmp_path / "raw"),
                     "--bill-state-file", str(tmp_path / "local.sqlite")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["bills"][0]["counts"]["accepted"] == 1
