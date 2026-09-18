import json
import hashlib
from argparse import Namespace
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF

from oireachtas_etl.serialization import nquads
from oireachtas_etl.transforms.bills import bill_graph_iri, source_hash, transform_bill_with_report
from oireachtas_etl.transforms.common import ELIDL, OIR
from oireachtas_etl.validation.bills import validate_bill
from oireachtas_etl.validation.vocabulary import PINS, pinned_vocabulary_graphs

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
BILL = URIRef(RECORD["bill"]["uri"])
ELI = "http://data.europa.eu/eli/ontology#"


def copied():
    return json.loads(json.dumps(RECORD))


def test_bill_golden_lifecycle_is_deterministic_valid_and_owned():
    graph, report = transform_bill_with_report(RECORD)
    repeat, repeat_report = transform_bill_with_report(RECORD)
    assert set(graph) == set(repeat) and report == repeat_report
    assert nquads(graph, bill_graph_iri(RECORD["bill"])) == nquads(repeat, bill_graph_iri(RECORD["bill"]))
    golden = (ROOT / "tests/expected/bills.nq.sha256").read_text().strip()
    assert hashlib.sha256(nquads(graph, bill_graph_iri(RECORD["bill"])).encode()).hexdigest() == golden
    assert set(Graph().parse(ROOT / "tests/expected/bills.ttl")) == set(graph)
    assert validate_bill(RECORD, graph) == report
    process = URIRef(str(BILL) + "#process")
    assert (process, RDF.type, ELIDL.LegislativeProcess) in graph
    assert (process, ELIDL.latest_activity, URIRef(str(BILL) + "/stage/oireachtas/enacted")) in graph
    assert (BILL, OIR.originHouse, URIRef("https://data.oireachtas.ie/house/dail")) in graph
    assert (BILL, URIRef("http://data.europa.eu/eli/ontology#basis_for"), URIRef(RECORD["bill"]["act"]["uri"])) in graph
    assert not list(graph.triples((URIRef(RECORD["bill"]["act"]["uri"]), None, None)))
    assert not any("debateRecord" in str(subject) for subject in graph.subjects())
    assert not any(item["category"] == "semantic_escalation" for item in report)


def test_amendments_link_to_owned_stages_and_members_remain_references():
    changed = copied()
    changed["bill"]["sponsors"][0]["sponsor"]["by"] = {"uri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Example", "showAs": "Must not leak"}
    graph, _ = transform_bill_with_report(changed)
    amendments = list(graph.subjects(RDF.type, ELIDL.AmendmentToDraftLegislationWork))
    tablings = [subject for subject in graph.subjects(ELIDL.occured_at_stage, None) if "#tabling-" in str(subject)]
    assert amendments and len(tablings) == len(amendments)
    for stage in graph.subjects(RDF.type, OIR.BillStage):
        assert (stage, RDF.type, ELIDL.ProcessStage) not in graph
        stage_concept = graph.value(stage, ELIDL.occured_at_stage)
        assert stage_concept == graph.value(stage, ELIDL.had_activity_type)
        assert stage_concept in {OIR.FirstStage, OIR.SecondStage, OIR.CommitteeStage, OIR.ReportStage, OIR.FifthStage, OIR.Enacted}
    assert all(target not in set(graph.subjects(RDF.type, OIR.BillStage)) for target in graph.objects(None, ELIDL.occured_at_stage))
    member = URIRef(changed["bill"]["sponsors"][0]["sponsor"]["by"]["uri"])
    assert (None, ELIDL.had_participant_person, member) in graph
    assert not list(graph.triples((member, None, None)))


def test_bill_hash_is_key_order_stable_and_lifecycle_array_order_sensitive():
    changed = copied(); reordered = copied()
    reordered["bill"]["stages"].reverse()
    assert source_hash(changed["bill"]) != source_hash(reordered["bill"])
    assert source_hash(changed["bill"]) == source_hash(json.loads(json.dumps(changed))["bill"])


def test_amendment_and_resolved_sponsor_identities_ignore_nonidentity_fields():
    changed = copied()
    changed["bill"]["amendmentLists"][0]["amendmentList"]["showAs"] = "Corrected display label"
    changed["bill"]["amendmentLists"][0]["amendmentList"]["formats"]["pdf"]["uri"] = changed["bill"]["amendmentLists"][0]["amendmentList"]["formats"]["pdf"]["uri"].replace(".pdf", "-replacement.pdf")
    changed["bill"]["sponsors"][0]["sponsor"]["by"] = {"uri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Example", "showAs": "Old name"}
    baseline, _ = transform_bill_with_report(changed)
    changed["bill"]["sponsors"][0]["sponsor"]["by"]["showAs"] = "New name"
    changed_graph, _ = transform_bill_with_report(changed)
    kind = lambda graph, type_: set(graph.subjects(RDF.type, type_))
    assert kind(baseline, ELIDL.AmendmentToDraftLegislationWork) == kind(changed_graph, ELIDL.AmendmentToDraftLegislationWork)
    assert set(baseline.subjects(ELIDL.had_participant_person, None)) == set(changed_graph.subjects(ELIDL.had_participant_person, None))


@pytest.mark.parametrize("mutate", [
    lambda value: value["bill"]["stages"][1]["event"].update({"progressStage": 1}),
    lambda value: value["bill"]["mostRecentStage"]["event"].update({"showAs": "Wrong stage"}),
    lambda value: value["bill"]["mostRecentStage"].update({"event": value["bill"]["stages"][0]["event"]}),
])
def test_source_chronology_and_latest_stage_correspondence_fail_closed(mutate):
    changed = copied(); mutate(changed)
    with pytest.raises(ValueError, match="progressStage|mostRecentStage"):
        validate_bill(changed, transform_bill_with_report(changed)[0])


def test_pinned_vocabularies_have_expected_hashes_and_cover_emitted_terms():
    assert all(path.is_file() for path in PINS)
    eli, elidl = pinned_vocabulary_graphs()
    assert len(eli) > 100 and len(elidl) > 100
    validate_bill(RECORD, transform_bill_with_report(RECORD)[0])


def test_required_work_expression_format_and_tabling_mutations_fail():
    graph, _ = transform_bill_with_report(RECORD)
    bill = BILL
    mutations = [
        (bill, URIRef("http://data.europa.eu/eli/ontology#has_part"), None),
        (None, URIRef("http://data.europa.eu/eli/ontology#is_realized_by"), None),
        (None, URIRef("http://data.europa.eu/eli/ontology#is_embodied_by"), None),
        (None, ELIDL.occured_at_stage, None),
    ]
    for pattern in mutations:
        broken = Graph(); [broken.add(triple) for triple in graph]
        broken.remove(pattern)
        with pytest.raises(ValueError): validate_bill(RECORD, broken)


def test_controlled_eli_language_and_complete_format_mutations_fail():
    graph, _ = transform_bill_with_report(RECORD)
    language = URIRef("http://data.europa.eu/eli/ontology#language")
    media_type = URIRef("http://data.europa.eu/eli/ontology#media_type")
    uri_schema = URIRef("http://data.europa.eu/eli/ontology#uri_schema")
    expression, language_iri = next(iter(graph.subject_objects(language)))
    format_iri = next(graph.subjects(RDF.type, URIRef("http://data.europa.eu/eli/ontology#Format")))
    mutations = [
        ((expression, language, language_iri), (expression, language, Literal("eng"))),
        ((format_iri, media_type, None), None),
        ((format_iri, uri_schema, None), None),
    ]
    for remove, add in mutations:
        broken = Graph(); [broken.add(triple) for triple in graph]
        broken.remove(remove)
        if add:
            broken.add(add)
        with pytest.raises(ValueError, match="controlled ELI language|Format requires"):
            validate_bill(RECORD, broken)


@pytest.mark.parametrize("resource", [
    URIRef(RECORD["bill"]["act"]["uri"]),
    URIRef("https://data.oireachtas.ie/house/dail"),
    URIRef(RECORD["bill"]["debates"][0]["uri"]),
])
def test_nonowned_reference_descriptions_fail(resource):
    graph, _ = transform_bill_with_report(RECORD)
    graph.add((resource, RDF.type, URIRef("https://example.test/LeakedDescription")))
    with pytest.raises(ValueError, match="non-owned"):
        validate_bill(RECORD, graph)


def test_controlled_stage_and_activity_type_terms_are_not_occurrences():
    ontology = Graph().parse(ROOT / "ontology/events.owl.ttl")
    controlled_stages = {OIR.FirstStage, OIR.SecondStage, OIR.CommitteeStage, OIR.ReportStage, OIR.FifthStage, OIR.Enacted}
    controlled_activity_types = controlled_stages | {OIR.Published, OIR.Presentation, OIR.Introduction, OIR.Application}
    assert all((term, RDF.type, ELIDL.ProcessStage) in ontology for term in controlled_stages)
    assert all((term, RDF.type, ELIDL.ActivityType) in ontology for term in controlled_activity_types)
    assert not any((term, RDF.type, OIR.BillEvent) in ontology or (term, RDF.type, OIR.BillStage) in ontology or (term, RDF.type, OIR.BillDelivery) in ontology for term in controlled_activity_types)


def test_controlled_stage_and_activity_type_target_mutations_fail():
    graph, _ = transform_bill_with_report(RECORD)
    stage = next(graph.subjects(RDF.type, OIR.BillStage))
    tabling = next(subject for subject in graph.subjects(ELIDL.occured_at_stage, None) if "#tabling-" in str(subject))
    broken = Graph(); [broken.add(triple) for triple in graph]
    broken.set((tabling, ELIDL.occured_at_stage, stage))
    with pytest.raises(ValueError, match="controlled ProcessStage"):
        validate_bill(RECORD, broken)
    broken = Graph(); [broken.add(triple) for triple in graph]
    broken.set((stage, ELIDL.had_activity_type, stage))
    with pytest.raises(ValueError, match="controlled ProcessStage and ActivityType"):
        validate_bill(RECORD, broken)


def test_bill_graph_identity_and_latest_stage_fail_closed():
    changed = copied(); changed["bill"]["billNo"] = "61"
    with pytest.raises(ValueError, match="bill.uri"):
        transform_bill_with_report(changed)
    changed = copied(); changed["bill"]["mostRecentStage"]["event"]["uri"] = "https://data.oireachtas.ie/ie/oireachtas/bill/2025/60/stage/dail/99"
    with pytest.raises(ValueError, match="mostRecentStage"):
        transform_bill_with_report(changed)


def test_bills_cli_offline_never_writes_state(tmp_path):
    from oireachtas_etl.cli import run_bills
    args = Namespace(fixture=str(ROOT / "data/api_examples/bill.json"), offline=True, raw_dir=str(tmp_path / "raw"), state_file=str(tmp_path / "state.json"), output_nq=str(tmp_path / "bills.nq"), output_ttl=None, fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert run_bills(args) == 0
    assert not Path(args.state_file).exists() and Path(args.output_nq).exists()


def test_online_bill_hash_skip_and_dirty_replacement_state(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    fixture = tmp_path / "bill.json"; fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}}, "results": [RECORD]}))
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_file=str(tmp_path / "state.json"), output_nq=None, output_ttl=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query")
    calls = []
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): calls.append(args)
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: None)
    assert cli.run_bills(args) == 0 and len(calls) == 1
    state = json.loads(Path(args.state_file).read_text())["bills"][RECORD["bill"]["uri"]]
    assert state["status"] == "clean" and state["published_hash"] == source_hash(RECORD["bill"])
    monkeypatch.setattr(cli, "transform_bill_with_report", lambda value: (_ for _ in ()).throw(AssertionError("unchanged bill transformed")))
    assert cli.run_bills(args) == 0 and len(calls) == 1


def test_bill_publication_failure_and_competency_failure_are_dirty_and_retry(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    fixture = tmp_path / "bill.json"; fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}}, "results": [RECORD]}))
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_file=str(tmp_path / "state.json"), output_nq=None, output_ttl=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query")
    class FailingLoader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): raise RuntimeError("PUT failed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", FailingLoader); monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    with pytest.raises(RuntimeError, match="PUT failed"): cli.run_bills(args)
    entry = json.loads(Path(args.state_file).read_text())["bills"][RECORD["bill"]["uri"]]
    assert entry["status"] == "dirty" and "published_hash" not in entry
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): pass
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader); monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    with pytest.raises(ValueError, match="competency failed"): cli.run_bills(args)
    assert json.loads(Path(args.state_file).read_text())["bills"][RECORD["bill"]["uri"]]["status"] == "dirty"
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: None)
    assert cli.run_bills(args) == 0
    assert json.loads(Path(args.state_file).read_text())["bills"][RECORD["bill"]["uri"]]["status"] == "clean"


def test_bill_competency_query_resources_execute_against_named_graph():
    from oireachtas_etl.competency import QUERIES
    dataset = Dataset(); graph = dataset.graph(URIRef(bill_graph_iri(RECORD["bill"])))
    for triple in transform_bill_with_report(RECORD)[0]: graph.add(triple)
    rows = {filename: [row.asdict() for row in dataset.query(QUERIES.joinpath(filename).read_text())] for filename in ("bill-latest-stage.rq", "bill-status.rq", "bill-origin-house.rq", "bill-stage-chronology.rq", "bill-resulting-act.rq", "bills-updated.rq")}
    assert rows["bill-latest-stage.rq"][0]["stage"] == URIRef(str(BILL) + "/stage/oireachtas/enacted")
    assert rows["bill-status.rq"][0]["status"] == OIR.EnactedBill
    assert rows["bill-origin-house.rq"][0]["house"] == URIRef("https://data.oireachtas.ie/house/dail")
    assert [int(row["order"]) for row in rows["bill-stage-chronology.rq"]] == list(range(1, 11))
    assert rows["bill-resulting-act.rq"][0]["act"] == URIRef(RECORD["bill"]["act"]["uri"])
    assert rows["bills-updated.rq"][0]["bill"] == BILL
