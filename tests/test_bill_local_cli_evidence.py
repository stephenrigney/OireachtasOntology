"""The local Bill publisher may consume only verified core-owner evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.cli import (_published_bill_sponsor_graph,
                                _published_sponsor_member_graphs,
                                _accepted_published_sponsor_holdings,
                                _resolution_records,
                                _require_published_sponsor_offices)
from oireachtas_etl.office_observations import extract_office_observations
from oireachtas_etl.office_reconciliation import OfficeOccurrenceStore
from oireachtas_etl.config import OFFICES_GRAPH
from oireachtas_etl.serialization import ntriples
from oireachtas_etl.transforms.bills import bill_graph_iri, source_hash, transform_bill_with_report
from oireachtas_etl.transforms.common import MEMBERS
from oireachtas_etl.transforms.offices import transform_offices
from oireachtas_etl.transforms.members import transform_member


ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
REGISTRY = json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())
PERSON = "https://data.oireachtas.ie/ie/oireachtas/member/id/Example"
MEMBER_GRAPH = "https://data.oireachtas.ie/graph/member/Example"


class Core:
    def __init__(self, *, legislation=None, members=None, offices=None):
        self.legislation, self.members, self.offices = legislation, members or {}, offices

    def get_resource(self, endpoint, iri):
        return self.legislation if endpoint == "legislation" else self.members.get(iri)

    def endpoint_publication(self, endpoint):
        assert endpoint == "offices"
        return self.offices


class Client:
    def __init__(self, graphs):
        self.graphs = graphs

    def query(self, sparql):
        graph_iri = sparql.split("GRAPH <", 1)[1].split(">", 1)[0]
        return [{name: {"type": "uri", "value": str(term)} if isinstance(term, URIRef)
                 else {"type": "literal", "value": str(term),
                       "datatype": str(term.datatype)} if term.datatype
                 else {"type": "literal", "value": str(term), "xml:lang": term.language}
                 for name, term in zip(("s", "p", "o"), triple)}
                for triple in self.graphs.get(graph_iri, Graph())]


def _row(graph, graph_iri, *, contract, source=None):
    payload = ntriples(graph)
    return {"publication_state": "clean", "contract_version": contract,
            "source_presence": "present",
            "graph_iri": graph_iri, "published_source_hash": source,
            "published_payload": payload,
            "published_payload_hash": hashlib.sha256(payload.encode()).hexdigest()}


def test_bill_and_office_evidence_requires_exact_published_core_graphs():
    bill = RECORD["bill"]
    bill_graph = transform_bill_with_report(RECORD)[0]
    office_graph = transform_offices(REGISTRY)
    core = Core(legislation=_row(bill_graph, bill_graph_iri(bill), contract=1,
                                 source=source_hash(bill)),
                offices=_row(office_graph, OFFICES_GRAPH, contract=1))
    client = Client({bill_graph_iri(bill): bill_graph, OFFICES_GRAPH: office_graph})
    _require_published_sponsor_offices(core, REGISTRY, client)
    assert set(_published_bill_sponsor_graph(core, RECORD, client)) == set(bill_graph)
    client.graphs[bill_graph_iri(bill)] = Graph()
    with pytest.raises(ValueError, match="mismatch"):
        _published_bill_sponsor_graph(core, RECORD, client)
    client.graphs[bill_graph_iri(bill)] = bill_graph
    core.legislation["publication_state"] = "dirty"
    with pytest.raises(ValueError, match="not published"):
        _published_bill_sponsor_graph(core, RECORD, client)
    core.legislation["publication_state"] = "clean"
    core.legislation["published_source_hash"] = "old source"
    with pytest.raises(ValueError, match="not published"):
        _published_bill_sponsor_graph(core, RECORD, client)
    client.graphs[OFFICES_GRAPH] = Graph()
    with pytest.raises(ValueError, match="mismatch"):
        _require_published_sponsor_offices(core, REGISTRY, client)


def test_only_clean_published_member_holdings_can_support_person_link():
    holding = URIRef(PERSON + "#office-holding-accepted")
    graph = Graph()
    graph.add((holding, RDF.type, MEMBERS.OfficeHolding))
    row = _row(graph, MEMBER_GRAPH, contract=3)
    core = Core(members={PERSON: row})
    client = Client({MEMBER_GRAPH: graph})
    assert (holding, RDF.type, MEMBERS.OfficeHolding) in _published_sponsor_member_graphs(
        core, {PERSON}, client)
    row["publication_state"] = "dirty"
    assert not _published_sponsor_member_graphs(core, {PERSON}, client)
    row["publication_state"] = "clean"
    row["published_payload_hash"] = "corrupt"
    with pytest.raises(ValueError, match="cannot be verified"):
        _published_sponsor_member_graphs(core, {PERSON}, client)


def test_published_holding_needs_reviewed_source_date_precision(tmp_path):
    wrapper = json.loads((ROOT / "data/api_examples/member.json").read_text())
    member = wrapper["member"]
    for item in member["memberships"]:
        item["membership"]["offices"] = []
    target = next(item["membership"] for item in member["memberships"]
                  if item["membership"]["house"].get("houseNo") == "34")
    target["offices"] = [{"office": {
        "dateRange": {"start": "2025-01-23", "end": None},
        "officeName": {"showAs": "Taoiseach", "uri": None},
    }}]
    pointer = {"path": "test/skip-000000.json", "sha256": "a" * 64,
               "json_pointer": "/results/0"}
    observations = extract_office_observations([(wrapper, pointer)])
    with OfficeOccurrenceStore(tmp_path / "offices.sqlite") as ledger:
        record = ledger.reconcile(observations, REGISTRY, {}, "b" * 64)["records"][0]
        accepted = _resolution_records(record["occurrence_key"],
                                       record["last_accepted_resolution"], retained=False)
        office_types = {"https://data.oireachtas.ie/office/o-000001": "TaoiseachOfficeType"}
        member_graph = transform_member(wrapper, office_resolutions=accepted,
                                        office_types=office_types)
        person = member["uri"]
        # The published Member graph and the reviewed occurrence ledger must
        # agree; neither source on its own may authorize Bill tenure links.
        from oireachtas_etl.transforms.members import member_graph_iri
        graph_iri = member_graph_iri(member)
        core = Core(members={person: _row(member_graph, graph_iri, contract=3)})
        client = Client({graph_iri: member_graph})
        rows = _accepted_published_sponsor_holdings(core, ledger, {person}, REGISTRY, client)
        assert len(rows) == 1
        assert rows[0]["date_range"] == {"start": "2025-01-23", "end": None}
        assert rows[0]["office_iri"] == "https://data.oireachtas.ie/office/o-000001"
        client.graphs[graph_iri] = Graph()
        with pytest.raises(ValueError, match="mismatch"):
            _accepted_published_sponsor_holdings(core, ledger, {person}, REGISTRY, client)
