"""Optional exact graph replacement against an explicitly selected disposable Fuseki."""
from __future__ import annotations

from argparse import Namespace
import copy
import json
import os
from pathlib import Path

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, XSD

from oireachtas_etl.cli import (run_bills, run_members, run_office_registry,
                                run_reconcile_bills_local, _accepted_published_sponsor_holdings)
from oireachtas_etl.bill_sponsor_reconciliation import (extract_bill_sponsor_observations,
                                                        sponsor_input_fingerprint)
from oireachtas_etl.office_reconciliation import OfficeOccurrenceStore
from oireachtas_etl.state import CoreStateStore
from oireachtas_etl.config import OFFICES_GRAPH, ADMINISTRATIVE_UNITS_GRAPH
from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient
from oireachtas_etl.reconciliation import verify_reconciliation_graph
from oireachtas_etl.transforms.bills import bill_graph_iri, transform_bill_with_report
from oireachtas_etl.bill_sponsor_reconciliation import bill_sponsor_graph_iri
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.serialization import ntriples


GSP = os.getenv("OIR_TEST_FUSEKI_GSP_URL")
SPARQL = os.getenv("OIR_TEST_FUSEKI_SPARQL_URL")
USER = os.getenv("OIR_TEST_FUSEKI_USER")
PASSWORD = os.getenv("OIR_TEST_FUSEKI_PASSWORD")
pytestmark = pytest.mark.skipif(not (GSP and SPARQL),
                                reason="requires explicit disposable OIR_TEST_FUSEKI dataset")
ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]


def _args(tmp, fixture=None, **extra):
    return Namespace(fixture=str(fixture) if fixture else None, offline=False,
                     publish=False, output_nq=None, output_ttl=None,
                     raw_dir=str(tmp / "raw"), state_db=str(tmp / "core.sqlite"),
                     office_state_file=str(tmp / "offices.sqlite"),
                     bill_state_file=str(tmp / "bill-local.sqlite"),
                     registry_file=str(ROOT / "registries/ministerial-office-registry.json"),
                     review_file=str(ROOT / "reconciliation/bill-sponsor-decisions.json"),
                     reconciliation_state_file=str(tmp / "external.sqlite"),
                     responses_file=None, all=False, legacy_state_file=None,
                     fuseki_gsp_url=GSP, fuseki_sparql_url=SPARQL,
                     endpoint=extra.get("endpoint"), **{k: v for k, v in extra.items() if k != "endpoint"})


def _fixture(path, record):
    path.write_text(json.dumps({"head": {"counts": {"billCount": 1}},
                                "results": [record]}, ensure_ascii=False))
    return path


def _cli_credentials(monkeypatch):
    if USER is None:
        monkeypatch.delenv("OIR_FUSEKI_USER", raising=False)
        monkeypatch.delenv("OIR_FUSEKI_PASSWORD", raising=False)
    else:
        if PASSWORD is None:
            raise ValueError("OIR_TEST_FUSEKI_PASSWORD is required with OIR_TEST_FUSEKI_USER")
        monkeypatch.setenv("OIR_FUSEKI_USER", USER)
        monkeypatch.setenv("OIR_FUSEKI_PASSWORD", PASSWORD)


def test_local_bill_put_exact_isolated_and_stale_subject_removed(tmp_path, monkeypatch):
    _cli_credentials(monkeypatch)
    loader = FusekiGraphStoreLoader(GSP, user=USER, password=PASSWORD)
    client = FusekiSparqlClient(SPARQL, user=USER, password=PASSWORD)
    first = _fixture(tmp_path / "bill-first.json", RECORD)
    for endpoint in ("administrative-units", "offices"):
        assert run_office_registry(_args(tmp_path, endpoint=endpoint)) == 0
    args = _args(tmp_path, fixture=first)
    assert run_bills(args) == 0
    bill_graph = bill_graph_iri(RECORD["bill"])
    local_graph = bill_sponsor_graph_iri(RECORD["bill"])
    snapshots = {iri: set(client.construct_graph(iri)) for iri in
                 (bill_graph, OFFICES_GRAPH, ADMINISTRATIVE_UNITS_GRAPH)}
    unrelated = "https://data.oireachtas.ie/graph/bill/2025/61/office-reconciliation"
    untouched = Graph()
    untouched.add((URIRef("https://example.test/other"), MEMBERS.reconciledSponsorOffice,
                   URIRef("https://data.oireachtas.ie/office/o-000001")))
    loader.replace(unrelated, ntriples(untouched), content_type="application/n-triples")
    member_graph = "https://data.oireachtas.ie/graph/member/tranche5-isolation"
    debate_graph = "https://data.oireachtas.ie/graph/debate/tranche5-isolation"
    office_external_graph = "https://data.oireachtas.ie/graph/office/o-000001/external-links"
    for iri in (member_graph, debate_graph, office_external_graph):
        loader.replace(iri, ntriples(untouched), content_type="application/n-triples")
    args.publish = True
    assert run_reconcile_bills_local(args) == 0
    original = client.construct_graph(local_graph)
    assert len(original) == 1
    verify_reconciliation_graph(client, local_graph, original)
    assert all(set(client.construct_graph(iri)) == snapshot for iri, snapshot in snapshots.items())
    assert set(client.construct_graph(unrelated)) == set(untouched)
    assert all(set(client.construct_graph(iri)) == set(untouched)
               for iri in (member_graph, debate_graph, office_external_graph))

    changed = copy.deepcopy(RECORD)
    changed["bill"]["sponsors"][0]["sponsor"]["as"]["showAs"] = "Unknown sponsor office"
    second = _fixture(tmp_path / "bill-second.json", changed)
    args.fixture = str(second)
    assert run_bills(args) == 0
    changed_core = transform_bill_with_report(changed)[0]
    def canonical(graph):
        return {tuple(Literal(str(term)) if isinstance(term, Literal) and
                      term.language is None and term.datatype in (None, XSD.string)
                      else term for term in triple) for triple in graph}

    assert canonical(client.construct_graph(bill_graph)) == canonical(changed_core)
    assert not list(changed_core.objects(None, MEMBERS.reconciledSponsorOffice))
    assert any(str(label) == "Unknown sponsor office" for label in changed_core.objects(None, RDFS.label))
    assert run_reconcile_bills_local(args) == 1  # review required, still clears stale local link
    assert len(client.construct_graph(local_graph)) == 0
    assert canonical(client.construct_graph(bill_graph)) == canonical(changed_core)
    assert set(client.construct_graph(unrelated)) == set(untouched)
    assert all(set(client.construct_graph(iri)) == set(untouched)
               for iri in (member_graph, debate_graph, office_external_graph))
    assert set(client.construct_graph(OFFICES_GRAPH)) == snapshots[OFFICES_GRAPH]
    assert set(client.construct_graph(ADMINISTRATIVE_UNITS_GRAPH)) == snapshots[ADMINISTRATIVE_UNITS_GRAPH]


def test_reviewed_holding_put_needs_published_person_and_bill_event(tmp_path, monkeypatch):
    _cli_credentials(monkeypatch)
    client = FusekiSparqlClient(SPARQL, user=USER, password=PASSWORD)
    registry = json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())
    for endpoint in ("administrative-units", "offices"):
        assert run_office_registry(_args(tmp_path, endpoint=endpoint)) == 0
    member = json.loads((ROOT / "data/api_examples/member.json").read_text())
    for item in member["member"]["memberships"]:
        item["membership"]["offices"] = []
    target = next(item["membership"] for item in member["member"]["memberships"]
                  if item["membership"]["house"].get("houseNo") == "34")
    target["offices"] = [{"office": {"dateRange": {"start": "2025-01-23", "end": None},
                                     "officeName": {"showAs": "Taoiseach", "uri": None}}}]
    member_fixture = tmp_path / "member.json"
    member_fixture.write_text(json.dumps({"head": {"counts": {"memberCount": 1}},
                                          "results": [member]}))
    member_args = _args(tmp_path, fixture=member_fixture)
    assert run_members(member_args) == 0
    from oireachtas_etl.transforms.members import member_graph_iri
    member_graph = member_graph_iri(member["member"])
    original_member_graph = set(client.construct_graph(member_graph))
    source = copy.deepcopy(RECORD)
    source["bill"]["sponsors"][0]["sponsor"]["as"]["showAs"] = "Taoiseach"
    source["bill"]["sponsors"][0]["sponsor"]["by"]["uri"] = member["member"]["uri"]
    bill_fixture = _fixture(tmp_path / "bill.json", source)
    args = _args(tmp_path, fixture=bill_fixture)
    assert run_bills(args) == 0
    with (CoreStateStore(Path(args.state_db)) as core,
          OfficeOccurrenceStore(Path(args.office_state_file)) as office_store):
        holdings = _accepted_published_sponsor_holdings(
            core, office_store, {member["member"]["uri"]}, registry, client)
    assert len(holdings) == 1
    observation = extract_bill_sponsor_observations(source)[0]
    event = observation["bill_time_contexts"][0]
    assert event["date"] >= "2025-01-23"
    decision = {"status": "accepted", "office_iri": holdings[0]["office_iri"],
                "holding_iri": holdings[0]["holding_iri"], "time_context": event,
                "input_fingerprint": sponsor_input_fingerprint(observation, registry, holdings, event),
                "evidence": ["fixture Bill stage date and verified Member OfficeHolding"],
                "reason": "Synthetic reviewed person, office and Bill event for Tranche 5 test."}
    review = tmp_path / "bill-sponsor-review.json"
    review.write_text(json.dumps({"version": 1,
                                  "decisions": {observation["observation_key"]: decision}}))
    args.review_file = str(review)
    args.publish = True
    assert run_reconcile_bills_local(args) == 0
    local = client.construct_graph(bill_sponsor_graph_iri(source["bill"]))
    assert (URIRef(observation["participation_iri"]), MEMBERS.reconciledSponsorOffice,
            URIRef(holdings[0]["office_iri"])) in local
    assert (URIRef(observation["participation_iri"]), MEMBERS.reconciledSponsorHolding,
            URIRef(holdings[0]["holding_iri"])) in local
    assert len(local) == 2
    verify_reconciliation_graph(client, bill_sponsor_graph_iri(source["bill"]), local)
    assert set(client.construct_graph(member_graph)) == original_member_graph
