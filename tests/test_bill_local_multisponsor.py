"""Multi-sponsor source correspondence must not inherit the final loop index."""
from __future__ import annotations

from argparse import Namespace
import copy
import hashlib
import json
from pathlib import Path
from rdflib.namespace import RDF, RDFS

from oireachtas_etl.bill_sponsor_reconciliation import (
    BillSponsorStore, extract_bill_sponsor_observations)
from oireachtas_etl.cli import run_reconcile_bills_local
from oireachtas_etl.transforms.bill_sponsors import build_bill_sponsor_graph
from oireachtas_etl.transforms.bills import transform_bill_with_report
from oireachtas_etl.transforms.common import ELIDL, MEMBERS
from oireachtas_etl.validation.bill_sponsors import validate_bill_sponsor_graph


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())
SOURCE = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]


def multi_sponsor():
    record = copy.deepcopy(SOURCE)
    other = copy.deepcopy(record["bill"]["sponsors"][0])
    other["sponsor"]["as"]["showAs"] = "Unreviewed sponsor role"
    other["sponsor"]["isPrimary"] = False
    record["bill"]["sponsors"].append(other)
    return record


def test_each_source_index_reconstructs_its_own_participation_and_graph():
    record = multi_sponsor()
    observations = extract_bill_sponsor_observations(record)
    assert [item["source_index"] for item in observations] == [0, 1]
    assert len({item["participation_iri"] for item in observations}) == 2
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(record, REGISTRY, [], {}, hashlib.sha256(b"review").hexdigest())
    assert result["counts"] == {"accepted": 1, "rejected": 0,
                                "unresolved": 1, "review_required": 0}
    graph = build_bill_sponsor_graph(record, result["records"], REGISTRY, [])
    validate_bill_sponsor_graph(record, graph, result["records"], REGISTRY, [])
    assert len(graph) == 1
    assert next(iter(graph))[1] == MEMBERS.reconciledSponsorOffice
    reordered = copy.deepcopy(record)
    reordered["bill"]["sponsors"].reverse()
    assert {item["observation_key"] for item in extract_bill_sponsor_observations(reordered)} == {
        item["observation_key"] for item in observations}
    with BillSponsorStore(":memory:") as store:
        rechecked = store.reconcile(reordered, REGISTRY, [], {}, hashlib.sha256(b"review").hexdigest())
    validate_bill_sponsor_graph(
        reordered, build_bill_sponsor_graph(reordered, rechecked["records"], REGISTRY, []),
        rechecked["records"], REGISTRY, [])


def test_offline_local_cli_handles_two_sponsors_without_member_external_calls(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    fixture = tmp_path / "bills.json"
    fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}},
                                   "results": [multi_sponsor()]}))
    monkeypatch.setattr(cli, "run_reconcile_members",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Member external dispatch")))
    args = Namespace(offline=True, publish=False, fixture=str(fixture),
                     raw_dir=str(tmp_path / "raw"), registry_file=None, review_file=None,
                     bill_state_file=str(tmp_path / "bill-local.sqlite"), state_db=None,
                     office_state_file=None, responses_file=None,
                     output_nq=None, fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert run_reconcile_bills_local(args) == 1  # unreviewed second role is unresolved
    report = json.loads(capsys.readouterr().out)
    assert report["bills"][0]["triples"] == 1
    assert report["bills"][0]["counts"]["accepted"] == 1
    assert report["bills"][0]["counts"]["unresolved"] == 1
    core = transform_bill_with_report(multi_sponsor())[0]
    assert len(set(core.subjects(RDF.type, ELIDL.Participation))) == 2
    assert {str(label) for label in core.objects(None, RDFS.label)} >= {
        "Minister for Finance", "Unreviewed sponsor role"}


def test_grouped_sponsor_uses_representative_index_for_identity_change_gate():
    prior = copy.deepcopy(SOURCE)
    prior["bill"]["sponsors"].append(copy.deepcopy(prior["bill"]["sponsors"][0]))
    observations = extract_bill_sponsor_observations(prior)
    assert len(observations) == 1
    assert observations[0]["source_index"] == 0

    changed = copy.deepcopy(SOURCE)
    changed["bill"]["sponsors"][0]["sponsor"]["isPrimary"] = False
    with BillSponsorStore(":memory:") as store:
        first = store.reconcile(
            prior, REGISTRY, [], {}, hashlib.sha256(b"review").hexdigest())
        assert first["records"][0]["status"] == "accepted"
        second = store.reconcile(
            changed, REGISTRY, [], {}, hashlib.sha256(b"review").hexdigest())

    current = next(item for item in second["records"]
                   if item["source_presence"] == "present")
    assert current["source_index"] == 0
    assert current["status"] == "review_required"
    assert any(conflict["kind"] == "source-sponsor-identity-changed-at-prior-position"
               for conflict in current["conflicts"])
