"""No review may turn ambiguous person-and-time tenure into a guessed holding."""
import copy
import json
from pathlib import Path

from oireachtas_etl.bill_sponsor_reconciliation import (
    BillSponsorStore, extract_bill_sponsor_observations, sponsor_input_fingerprint)
from oireachtas_etl.transforms.bill_sponsors import build_bill_sponsor_graph
from oireachtas_etl.transforms.common import MEMBERS


ROOT = Path(__file__).resolve().parents[1]


def test_overlapping_same_office_holdings_do_not_establish_unique_holding():
    source = copy.deepcopy(json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0])
    registry = json.loads((ROOT / "registries/ministerial-office-registry.json").read_text())
    person = "https://data.oireachtas.ie/ie/oireachtas/member/id/Example"
    office = "https://data.oireachtas.ie/office/o-000003"
    sponsor = source["bill"]["sponsors"][0]["sponsor"]
    sponsor["by"]["uri"] = person
    holdings = [{"status": "accepted", "member_iri": person,
                 "holding_iri": person + "#office-holding-" + letter * 64,
                 "office_iri": office,
                 "date_range": {"start": "2025-01-01", "end": None}}
                for letter in ("a", "b")]
    observation = extract_bill_sponsor_observations(source)[0]
    context = observation["bill_time_contexts"][0]
    decision = {"status": "accepted", "office_iri": office,
                "holding_iri": holdings[0]["holding_iri"],
                "time_context": context,
                "input_fingerprint": sponsor_input_fingerprint(observation, registry, holdings, context),
                "evidence": ["test:two simultaneous same-office holdings"],
                "reason": "Cannot decide which holding was intended from source person and date."}
    with BillSponsorStore(":memory:") as store:
        result = store.reconcile(source, registry, holdings,
                                 {observation["observation_key"]: decision}, "c" * 64)
    record = result["records"][0]
    assert record["status"] == "review_required"
    assert record["holding_iri"] is None
    graph = build_bill_sponsor_graph(source, result["records"], registry, holdings)
    assert not list(graph.triples((None, MEMBERS.reconciledSponsorHolding, None)))
