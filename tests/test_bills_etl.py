import json
import hashlib
from argparse import Namespace
from pathlib import Path
import re
from urllib.parse import urlsplit

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from oireachtas_etl.serialization import nquads
from oireachtas_etl.transforms.bills import (EVENTS, STAGES, STATUSES,
                                             METHODS,
                                             bill_graph_iri, bill_stage_type, source_hash,
                                             _bill_event_identity,
                                             _derived,
                                             _amendment_list_parts,
                                             transform_bill_with_report)
from oireachtas_etl.transforms.common import ELIDL, OIR
from oireachtas_etl.validation.bills import (
    known_bill_source_quarantines, validate_bill, validate_bill_source)
from oireachtas_etl.validation.vocabulary import PINS, pinned_vocabulary_graphs

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data/api_examples/bill.json").read_text())["results"][0]
BILL = URIRef(RECORD["bill"]["uri"])
ELI = "http://data.europa.eu/eli/ontology#"
STAGE_6_CAPTURE = json.loads(
    (ROOT / "tests/fixtures/bill-stage-6-source-identities.json").read_text())
DECLARED_REPUGNANT_STATUS_CAPTURE = json.loads(
    (ROOT / "tests/fixtures/bill-declared-repugnant-status-identities.json")
    .read_text())
BY_APPLICATION_METHOD_CAPTURE = json.loads(
    (ROOT / "tests/fixtures/bill-by-application-method-identities.json")
    .read_text())
STAGE_6_IDENTITIES = tuple(
    (bill_identity, house)
    for house, bill_ids in STAGE_6_CAPTURE["occurrences_by_house"].items()
    for bill_identity in bill_ids)


def copied():
    return json.loads(json.dumps(RECORD))


def copied_for_bill(year, number):
    changed = copied()
    bill = changed["bill"]
    bill["billYear"] = year
    bill["billNo"] = number
    bill["uri"] = f"https://data.oireachtas.ie/ie/oireachtas/bill/{year}/{number}"
    bill["amendmentLists"] = []
    return changed


def bill_version(uri, date, label, pdf_uri, *, lang="eng"):
    return {"version": {
        "uri": uri,
        "docType": "bill",
        "lang": lang,
        "date": date,
        "showAs": label,
        "formats": {"pdf": {"uri": pdf_uri}, "xml": None},
    }}


def _bill_1945_22_with_amendment_lists():
    changed = copied_for_bill(1945, 22)
    bill = changed["bill"]
    bill_uri = bill["uri"]
    stage_occurrence = f"{bill_uri}/stage/seanad/4"
    stage = {
        "uri": stage_occurrence,
        "progressStage": 1,
        "stageURI": "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/4",
        "showAs": "Report Stage",
        "stageCompleted": True,
        "dates": [{"date": "1945-07-12"}],
        "house": None,
        "chamber": None,
    }
    bill["stages"] = [{"event": stage}]
    bill["mostRecentStage"] = {"event": json.loads(json.dumps(stage))}
    bill["events"] = []
    bill["versions"] = []
    bill["relatedDocs"] = []

    def amendment_list(filename, *, show_as="Numbered List [Dáil]"):
        return {"amendmentList": {
            "amendmentTypeUri": {
                "uri": "https://data.oireachtas.ie/ie/oireachtas/def/amendment-type/numberedList",
            },
            "chamber": {
                "showAs": "Seanad",
                "uri": "https://data.oireachtas.ie/ie/oireachtas/def/seanad",
            },
            "date": "1945-07-12",
            "formats": {
                "pdf": {"uri": (
                    f"{bill_uri}/seanad/4/amendment/numberedList/eng/{filename}")},
                "xml": None,
            },
            "showAs": show_as,
            "stage": {
                "showAs": "Report Stage",
                "uri": f"{bill_uri}/seanad/4",
            },
            "stageNo": "4",
        }}

    bill["amendmentLists"] = [
        amendment_list("bills1945-a-kj-04.pdf"),
        amendment_list("bills1945-a-kj-05.pdf"),
    ]
    return changed


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


@pytest.mark.parametrize(("suffix", "process_type", "source_uri"), [
    ("public", OIR.PublicBill,
     "https://data.oireachtas.ie/ie/oireachtas/def/bill-source/government"),
    ("private", OIR.PrivateBill,
     "https://data.oireachtas.ie/ie/oireachtas/def/bill-source/private-member"),
    ("hybrid", OIR.HybridBill,
     "https://data.oireachtas.ie/ie/oireachtas/def/bill-source/government"),
    ("hybrid", OIR.HybridBill,
     "https://data.oireachtas.ie/ie/oireachtas/def/bill-source/private-member"),
])
def test_bill_type_suffix_maps_to_peer_process_type_independent_of_source(
        suffix, process_type, source_uri):
    changed = copied()
    bill = changed["bill"]
    bill["billTypeURI"] = (
        f"https://data.oireachtas.ie/ie/oireachtas/def/bill-type/{suffix}")
    bill["billType"] = suffix.title()
    bill["sourceURI"] = source_uri

    graph, report = transform_bill_with_report(changed)
    process = URIRef(f"{bill['uri']}#process")
    assert (process, ELIDL.process_type, process_type) in graph
    assert (process, ELIDL.was_submitted_by, URIRef(source_uri)) in graph
    assert validate_bill(changed, graph) == report


def test_bill_process_types_are_peer_controlled_individuals():
    ontology = Graph().parse(ROOT / "ontology/legislation.owl.ttl")
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    in_scheme = URIRef("http://www.w3.org/2004/02/skos/core#inScheme")
    top_concept_of = URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf")
    subclass = URIRef("http://www.w3.org/2000/01/rdf-schema#subClassOf")
    process_types = {OIR.PublicBill, OIR.PrivateBill, OIR.HybridBill}
    for term in process_types:
        assert (term, RDF.type, ELIDL.ProcessType) in ontology
        assert (term, RDF.type, named_individual) in ontology
        assert (term, in_scheme, OIR.BillTypeTable) in ontology
        assert (term, top_concept_of, OIR.BillTypeTable) in ontology
    assert not any((left, subclass, right) in ontology
                   for left in process_types for right in process_types)


EXPECTED_BILL_STATUSES = {
    "awaiting-signature": OIR.AwaitingSignatureBill,
    "current": OIR.CurrentBill,
    "published": OIR.CurrentBill,
    "defeated": OIR.DefeatedBill,
    "declared-repugnant-to-constitution":
        OIR.DeclaredRepugnantToConstitutionBill,
    "draft-heads-of-bill": OIR.DraftHeadsOfBill,
    "enacted": OIR.EnactedBill,
    "lapsed": OIR.LapsedBill,
    "rejected-at-referendum": OIR.RejectedAtReferendumBill,
    "withdrawn": OIR.WithdrawnBill,
}


def _bill_with_status(year, number, status_uri):
    changed = copied_for_bill(year, number)
    bill = changed["bill"]
    bill["statusURI"] = status_uri
    occurrence = URIRef(f"{bill['uri']}/stage/dail/1")
    first_stage = {
        "uri": str(occurrence),
        "progressStage": 1,
        "stageURI": "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/1",
        "showAs": "First Stage",
        "stageCompleted": True,
        "dates": [{"date": "2000-01-01"}],
        "house": None,
        "chamber": None,
    }
    bill["stages"] = [{"event": first_stage}]
    bill["mostRecentStage"] = {"event": json.loads(json.dumps(first_stage))}
    bill["events"] = []
    bill["versions"] = []
    bill["amendmentLists"] = []
    return changed


def _bill_with_method(year, number, method_uri, method_label):
    changed = copied_for_bill(year, number)
    bill = changed["bill"]
    bill["methodURI"] = method_uri
    bill["method"] = method_label
    occurrence = URIRef(f"{bill['uri']}/stage/dail/1")
    first_stage = {
        "uri": str(occurrence),
        "progressStage": 1,
        "stageURI": "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/1",
        "showAs": "First Stage",
        "stageCompleted": True,
        "dates": [{"date": "1950-01-01"}],
        "house": None,
        "chamber": None,
    }
    bill["stages"] = [{"event": first_stage}]
    bill["mostRecentStage"] = {"event": json.loads(json.dumps(first_stage))}
    bill["events"] = []
    bill["versions"] = []
    bill["relatedDocs"] = []
    bill["amendmentLists"] = []
    return changed


def test_bill_status_mapping_table_preserves_existing_values_and_adds_reviewed_status():
    assert STATUSES == EXPECTED_BILL_STATUSES


EXPECTED_BILL_METHODS = {
    "presented": OIR.Presentation,
    "introduced": OIR.Introduction,
    "application": OIR.Application,
    "by-application": OIR.Application,
}


def test_bill_method_mapping_preserves_existing_values_and_adds_alias():
    assert METHODS == EXPECTED_BILL_METHODS


@pytest.mark.parametrize(
    "bill_identity", BY_APPLICATION_METHOD_CAPTURE["bill_identities"],
)
def test_all_22_captured_by_application_bills_use_application_activity_type(
        bill_identity):
    year, number = bill_identity.split("/")
    changed = _bill_with_method(
        int(year), number, BY_APPLICATION_METHOD_CAPTURE["method_uri"],
        BY_APPLICATION_METHOD_CAPTURE["method"])
    bill = changed["bill"]
    graph, report = transform_bill_with_report(changed)
    delivery = next(graph.subjects(RDF.type, OIR.BillDelivery))

    assert bill["uri"].endswith(f"/{bill_identity}")
    assert (delivery, ELIDL.had_activity_type, OIR.Application) in graph
    assert list(graph.objects(delivery, ELIDL.had_activity_type)) == [
        OIR.Application]
    assert not list(graph.triples((OIR.ByApplication, None, None)))
    assert validate_bill(changed, graph) == report


def test_by_application_label_does_not_create_an_ontology_individual():
    ontology = Graph().parse(ROOT / "ontology/events.owl.ttl")
    assert METHODS["application"] == METHODS["by-application"] == OIR.Application
    assert (OIR.Application, RDF.type, ELIDL.ActivityType) in ontology
    assert not list(ontology.triples((OIR.ByApplication, None, None)))


@pytest.mark.parametrize(("suffix", "expected"), [
    ("presented", OIR.Presentation),
    ("introduced", OIR.Introduction),
    ("application", OIR.Application),
])
def test_existing_bill_method_suffixes_still_map_to_their_controlled_activity(
        suffix, expected):
    changed = _bill_with_method(
        2025, 60,
        f"https://data.oireachtas.ie/ie/oireachtas/def/bill-method/{suffix}",
        suffix.title())
    graph, report = transform_bill_with_report(changed)
    delivery = next(graph.subjects(RDF.type, OIR.BillDelivery))
    assert (delivery, ELIDL.had_activity_type, expected) in graph
    assert validate_bill(changed, graph) == report


def test_unknown_bill_method_suffix_fails_closed():
    changed = _bill_with_method(
        2025, 60,
        "https://data.oireachtas.ie/ie/oireachtas/def/bill-method/unreviewed",
        "Unreviewed")
    with pytest.raises(ValueError, match="unsupported methodURI"):
        transform_bill_with_report(changed)


@pytest.mark.parametrize(
    "bill_identity", DECLARED_REPUGNANT_STATUS_CAPTURE["bill_identities"],
)
def test_all_seven_captured_declared_repugnant_bills_use_reviewed_status(
        bill_identity):
    year, number = (int(part) for part in bill_identity.split("/"))
    changed = _bill_with_status(
        year, number, DECLARED_REPUGNANT_STATUS_CAPTURE["status_uri"])
    bill = changed["bill"]
    process = URIRef(f"{bill['uri']}#process")

    graph, report = transform_bill_with_report(changed)
    assert (process, ELIDL.process_status,
            OIR.DeclaredRepugnantToConstitutionBill) in graph
    assert OIR.DeclaredRepugnantToConstitutionBill != OIR.DefeatedBill
    assert OIR.DeclaredRepugnantToConstitutionBill != OIR.RejectedAtReferendumBill
    assert validate_bill(changed, graph) == report


def test_declared_repugnant_status_fixture_covers_all_seven_captured_bills():
    identities = DECLARED_REPUGNANT_STATUS_CAPTURE["bill_identities"]
    assert len(identities) == 7
    assert len(set(identities)) == 7


def test_declared_repugnant_bill_status_is_a_peer_controlled_process_status():
    ontology = Graph()
    ontology.parse(ROOT / "ontology/legislation.owl.ttl")
    ontology.parse(ROOT / "ontology/events.owl.ttl")
    term = OIR.DeclaredRepugnantToConstitutionBill
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    top_concept_of = URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf")
    in_scheme = URIRef("http://www.w3.org/2004/02/skos/core#inScheme")
    subclass = URIRef("http://www.w3.org/2000/01/rdf-schema#subClassOf")
    assert (term, RDF.type, ELIDL.ProcessStatus) in ontology
    assert (term, RDF.type, named_individual) in ontology
    assert (term, URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"),
            Literal("Declared repugnant to the Constitution", lang="en")) in ontology
    assert (term, in_scheme, OIR.BillStatusTable) in ontology
    assert (term, top_concept_of, OIR.BillStatusTable) in ontology
    assert term != OIR.DefeatedBill
    assert term != OIR.RejectedAtReferendumBill
    assert (term, RDF.type, OIR.BillEventOutcome) not in ontology
    assert (term, subclass, OIR.DefeatedBill) not in ontology
    assert (OIR.DefeatedBill, subclass, term) not in ontology
    assert (term, subclass, OIR.RejectedAtReferendumBill) not in ontology
    assert (OIR.RejectedAtReferendumBill, subclass, term) not in ontology


def test_bill_status_validation_matches_source_and_unknown_suffix_fails_closed():
    status_uri = DECLARED_REPUGNANT_STATUS_CAPTURE["status_uri"]
    changed = _bill_with_status(1942, 23, status_uri)
    graph, report = transform_bill_with_report(changed)
    assert validate_bill(changed, graph) == report
    process = URIRef(f"{changed['bill']['uri']}#process")
    graph.set((process, ELIDL.process_status, OIR.DefeatedBill))
    with pytest.raises(ValueError, match="source controlled status"):
        validate_bill(changed, graph)

    unknown = _bill_with_status(
        1942, 23,
        "https://data.oireachtas.ie/ie/oireachtas/def/bill-status/unreviewed")
    with pytest.raises(ValueError, match="unsupported statusURI"):
        transform_bill_with_report(unknown)


def test_unknown_bill_type_suffix_fails_closed():
    changed = copied()
    changed["bill"]["billTypeURI"] = (
        "https://data.oireachtas.ie/ie/oireachtas/def/bill-type/unreviewed")
    with pytest.raises(ValueError, match="unsupported billTypeURI"):
        transform_bill_with_report(changed)


def test_bill_stage_6_maps_from_its_exact_definition_uri():
    assert STAGES["6"] == OIR.CreamListStage
    assert bill_stage_type(STAGE_6_CAPTURE["stage_definition_uri"]) == \
        OIR.CreamListStage


@pytest.mark.parametrize(
    ("bill_identity", "house"), STAGE_6_IDENTITIES,
    ids=[f"{identity}-{house}" for identity, house in STAGE_6_IDENTITIES],
)
def test_all_92_captured_cream_list_occurrences_use_stage_6_mapping(
        bill_identity, house):
    year, number = (int(part) for part in bill_identity.split("/"))
    changed = copied_for_bill(year, number)
    bill = changed["bill"]
    occurrence = URIRef(
        f"{bill['uri']}/stage/{house}/6")
    assert str(occurrence) == (
        f"https://data.oireachtas.ie/ie/oireachtas/bill/"
        f"{bill_identity}/stage/{house}/6")
    source_stage = {
        "uri": str(occurrence),
        "progressStage": 10,
        "stageURI": STAGE_6_CAPTURE["stage_definition_uri"],
        "showAs": "Cream List",
        "stageCompleted": True,
        "dates": [{"date": "2000-01-01"}],
        "house": None,
        "chamber": None,
    }
    bill["stages"] = [{"event": source_stage}]
    bill["mostRecentStage"] = {"event": json.loads(json.dumps(source_stage))}
    bill["events"] = []
    bill["versions"] = []
    bill["amendmentLists"] = []

    graph, _ = transform_bill_with_report(changed)
    assert (occurrence, RDF.type, ELIDL.LegislativeActivity) in graph
    assert (occurrence, RDF.type, OIR.BillStage) in graph
    assert (occurrence, RDF.type, OIR.BillEvent) in graph
    assert (occurrence, ELIDL.had_activity_type, OIR.CreamListStage) in graph
    assert (occurrence, ELIDL.occured_at_stage, OIR.CreamListStage) in graph
    assert (occurrence, OIR.progressStage,
            Literal(10, datatype=XSD.positiveInteger)) in graph


def test_stage_6_occurrence_validates_against_its_source_definition():
    changed = copied_for_bill(1942, 17)
    bill = changed["bill"]
    occurrence = URIRef(f"{bill['uri']}/stage/dail/6")
    source_stage = {
        "uri": str(occurrence),
        "progressStage": 1,
        "stageURI": STAGE_6_CAPTURE["stage_definition_uri"],
        "showAs": "Cream List",
        "stageCompleted": True,
        "dates": [{"date": "1943-03-03"}],
        "house": None,
        "chamber": None,
    }
    bill["stages"] = [{"event": source_stage}]
    bill["mostRecentStage"] = {"event": json.loads(json.dumps(source_stage))}
    bill["events"] = []
    bill["versions"] = []
    bill["amendmentLists"] = []

    graph, report = transform_bill_with_report(changed)
    assert validate_bill(changed, graph) == report
    assert (occurrence, ELIDL.had_activity_type, OIR.CreamListStage) in graph
    assert (occurrence, ELIDL.occured_at_stage, OIR.CreamListStage) in graph


def test_stage_6_capture_fixture_has_92_unique_bill_identities():
    assert len(STAGE_6_IDENTITIES) == 92
    assert len(set(STAGE_6_IDENTITIES)) == 92


def test_stage_6_controlled_concept_is_distinct_from_amendment_list_type():
    ontology = Graph().parse(ROOT / "ontology/events.owl.ttl")
    ontology.parse(ROOT / "ontology/legislation.owl.ttl")
    skos_concept = URIRef("http://www.w3.org/2004/02/skos/core#Concept")
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    top_concept_of = URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf")
    in_scheme = URIRef("http://www.w3.org/2004/02/skos/core#inScheme")
    assert OIR.CreamListStage != OIR.CreamList
    assert (OIR.CreamListStage, RDF.type, ELIDL.ProcessStage) in ontology
    assert (OIR.CreamListStage, RDF.type, ELIDL.ActivityType) in ontology
    assert (OIR.CreamListStage, RDF.type, skos_concept) in ontology
    assert (OIR.CreamListStage, RDF.type, named_individual) in ontology
    assert (OIR.CreamListStage,
            URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"),
            Literal("Cream List stage", lang="en")) in ontology
    assert (OIR.CreamListStage, in_scheme, OIR.BillEventTable) in ontology
    assert (OIR.CreamListStage, top_concept_of, OIR.BillEventTable) in ontology
    assert (OIR.CreamList, top_concept_of,
            OIR.AmendmentListTypeTable) in ontology
    assert (OIR.CreamList, RDF.type, ELIDL.ProcessStage) not in ontology
    assert (OIR.CreamList, RDF.type, ELIDL.ActivityType) not in ontology


SUPREME_COURT_REFERRAL_BILLS = (
    "1940/2", "1942/23", "1961/6", "1975/11", "1976/32", "1981/44",
    "1983/12", "1987/22", "1993/32", "1995/8", "1999/34", "1999/46",
    "2004/57", "2012/78",
)
SUPREME_COURT_REFERRAL_STAGE_URI = (
    "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/"
    "referral-to-supreme-court")


@pytest.mark.parametrize("bill_identity", SUPREME_COURT_REFERRAL_BILLS)
def test_all_preserved_supreme_court_referral_stage_occurrences_map_to_article_26(
        bill_identity):
    year, number = (int(part) for part in bill_identity.split("/"))
    changed = copied_for_bill(year, number)
    bill = changed["bill"]
    occurrence = URIRef(
        f"{bill['uri']}/stage/oireachtas/referral-to-supreme-court")
    source_stage = {
        "uri": str(occurrence),
        "progressStage": 1,
        "stageURI": SUPREME_COURT_REFERRAL_STAGE_URI,
        "showAs": "Referral to Supreme Court",
        "stageCompleted": True,
        "dates": [{"date": "2000-01-01"}],
        "house": None,
        "chamber": None,
    }
    bill["stages"] = [{"event": source_stage}]
    bill["mostRecentStage"] = {"event": json.loads(json.dumps(source_stage))}
    bill["events"] = []
    bill["versions"] = []
    bill["amendmentLists"] = []

    graph, report = transform_bill_with_report(changed)
    assert (occurrence, ELIDL.had_activity_type,
            OIR.ReferralToSupremeCourtArt26) in graph
    assert (occurrence, ELIDL.occured_at_stage,
            OIR.ReferralToSupremeCourtArt26) in graph
    assert validate_bill(changed, graph) == report


def test_article_26_event_and_stage_suffixes_share_one_controlled_concept():
    assert (EVENTS["referral-to-supreme-court-art-26"]
            == STAGES["referral-to-supreme-court"]
            == OIR.ReferralToSupremeCourtArt26)
    changed = copied()
    bill = changed["bill"]
    event = {
        "uri": f"{bill['uri']}/referral-to-supreme-court-art-26",
        "eventURI": (
            "https://data.oireachtas.ie/ie/oireachtas/def/bill-event/"
            "referral-to-supreme-court-art-26"),
        "showAs": "Referral to Supreme Court under Article 26",
        "chamber": None,
        "dates": [{"date": "2024-03-07"}],
    }
    occurrence = _bill_event_identity(event)[0]
    bill.setdefault("events", []).append({"event": event})
    graph, report = transform_bill_with_report(changed)
    assert (occurrence, ELIDL.had_activity_type,
            OIR.ReferralToSupremeCourtArt26) in graph
    assert validate_bill(changed, graph) == report


@pytest.mark.parametrize("stage_uri", [
    "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/unreviewed-stage",
    "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/"
    "referral-to-supreme-court-review",
    "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/7",
    "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/42",
    "https://data.oireachtas.ie/ie/oireachtas/def/other-stage/6",
])
def test_unknown_bill_stage_uri_suffix_fails_closed(stage_uri):
    changed = copied()
    changed["bill"]["stages"][-1]["event"]["stageURI"] = stage_uri
    with pytest.raises(ValueError, match="unsupported stage.stageURI"):
        transform_bill_with_report(changed)


@pytest.mark.parametrize(("suffix", "activity_type", "show_as"), [
    ("bill-defeated", OIR.BillDefeatedEvent, "Bill Defeated"),
    ("bill-lapsed", OIR.BillLapsedEvent, "Bill Lapsed"),
    ("bill-restored", OIR.RestoreBill, "Bill Restored"),
    ("bill-withdrawn", OIR.BillWithdrawnEvent, "Bill Withdrawn"),
    ("recommittal", OIR.RecommitBill, "Recommittal"),
    ("referendum", OIR.Referendum, "Referendum"),
    ("referral-to-supreme-court-art-26", OIR.ReferralToSupremeCourtArt26,
     "Referral to Supreme Court (Art. 26)"),
])
def test_approved_procedural_event_suffixes_emit_source_occurrences(
        suffix, activity_type, show_as):
    changed = copied()
    bill = changed["bill"]
    event = {
        "uri": f"{bill['uri']}/{suffix}",
        "eventURI": f"https://data.oireachtas.ie/ie/oireachtas/def/bill-event/{suffix}",
        "showAs": show_as,
        "chamber": {"uri": "https://data.oireachtas.ie/ie/oireachtas/def/house/dail"},
        "dates": [{"date": "2024-03-07"}],
    }
    occurrence = _bill_event_identity(event)[0]
    bill.setdefault("events", []).append({"event": event})

    graph, report = transform_bill_with_report(changed)
    process = URIRef(f"{bill['uri']}#process")
    assert (occurrence, RDF.type, ELIDL.LegislativeActivity) in graph
    assert (occurrence, RDF.type, OIR.BillEvent) in graph
    assert (occurrence, ELIDL.had_activity_type, activity_type) in graph
    assert (occurrence, ELIDL.forms_part_of, process) in graph
    assert (occurrence, ELIDL.activity_date, Literal("2024-03-07", datatype=URIRef(
        "http://www.w3.org/2001/XMLSchema#date"))) in graph
    assert (occurrence, OIR.inHouse, URIRef("https://data.oireachtas.ie/house/dail")) in graph
    assert validate_bill(changed, graph) == report
    assert not any(item["category"] == "intentionally_unmodelled" for item in report)
    if suffix == "bill-lapsed":
        assert activity_type != OIR.LapsedBill
    elif suffix == "bill-defeated":
        assert activity_type != OIR.DefeatedBill
    elif suffix == "bill-withdrawn":
        assert activity_type != OIR.Withdrawn
    elif suffix == "bill-restored":
        assert activity_type == OIR.RestoreBill
    elif suffix == "recommittal":
        assert activity_type == OIR.RecommitBill


@pytest.mark.parametrize("suffix", [
    "admissibility-for-introduction",
    "approved-for-initiation",
    "other-procedural-event",
])
def test_intentionally_unmodelled_event_types_are_omitted_with_diagnostics(suffix):
    changed = copied()
    bill = changed["bill"]
    occurrence = (None if suffix == "other-procedural-event"
                  else f"{bill['uri']}/{suffix}")
    bill.setdefault("events", []).append({"event": {
        "uri": occurrence,
        "eventURI": f"https://data.oireachtas.ie/ie/oireachtas/def/bill-event/{suffix}",
        "showAs": suffix,
    }})

    graph, report = transform_bill_with_report(changed)
    diagnostic = next(item for item in report
                      if item["category"] == "intentionally_unmodelled")
    assert diagnostic == {
        "path": "bill.events[].event.eventURI",
        "category": "intentionally_unmodelled",
        "source_event_uri": f"https://data.oireachtas.ie/ie/oireachtas/def/bill-event/{suffix}",
        "occurrence_uri": occurrence,
        "bill_uri": bill["uri"],
        "context": occurrence or bill["uri"],
        "reason": "Intentionally not modelled under the accepted Bill lifecycle contract",
    }
    if occurrence:
        source_occurrence = URIRef(occurrence)
        assert not list(graph.triples((source_occurrence, None, None)))
        assert not list(graph.triples((None, None, source_occurrence)))
    assert validate_bill(changed, graph) == report


def test_unknown_bill_event_uri_and_unreviewed_uri_alias_fail_closed():
    for event_uri in (
        "https://data.oireachtas.ie/ie/oireachtas/def/bill-event/unreviewed-event",
        "https://data.oireachtas.ie/ie/oireachtas/def/other/published",
    ):
        changed = copied()
        changed["bill"].setdefault("events", []).append({"event": {
            "uri": f"{changed['bill']['uri']}/unreviewed-event",
            "eventURI": event_uri,
            "showAs": "Unreviewed",
            "chamber": None,
            "dates": [{"date": "2024-03-07"}],
        }})
        with pytest.raises(ValueError, match="unsupported event.eventURI"):
            transform_bill_with_report(changed)


@pytest.mark.parametrize(("suffix", "wrong_type"), [
    ("bill-lapsed", OIR.LapsedBill),
    ("bill-defeated", OIR.DefeatedBill),
    ("bill-withdrawn", OIR.Withdrawn),
])
def test_status_or_outcome_individuals_cannot_substitute_for_event_types(
        suffix, wrong_type):
    changed = copied()
    bill = changed["bill"]
    occurrence = URIRef(f"{bill['uri']}/{suffix}")
    bill.setdefault("events", []).append({"event": {
        "uri": str(occurrence),
        "eventURI": f"https://data.oireachtas.ie/ie/oireachtas/def/bill-event/{suffix}",
        "showAs": suffix,
        "chamber": None,
        "dates": [{"date": "2024-03-07"}],
    }})
    graph, _ = transform_bill_with_report(changed)
    graph.set((occurrence, ELIDL.had_activity_type, wrong_type))
    with pytest.raises(ValueError, match="controlled ActivityType"):
        validate_bill(changed, graph)


def test_amendments_link_to_owned_stages_and_members_remain_references():
    changed = copied()
    changed["bill"]["sponsors"][0]["sponsor"]["by"] = {"uri": "https://data.oireachtas.ie/ie/oireachtas/member/id/Example", "showAs": "Must not leak"}
    graph, _ = transform_bill_with_report(changed)
    amendments = list(graph.subjects(RDF.type, ELIDL.AmendmentToDraftLegislationWork))
    tablings = {subject for subject in graph.subjects(RDF.type, ELIDL.LegislativeActivity)
                if "%23tabling-" in str(subject)}
    assert amendments and len(tablings) == len(amendments)
    controlled_stages = {OIR.FirstStage, OIR.SecondStage, OIR.CommitteeStage,
                         OIR.ReportStage, OIR.FifthStage, OIR.Enacted,
                         OIR.CreamListStage, OIR.ReferralToSupremeCourtArt26}
    assert all(len(list(graph.objects(tabling, ELIDL.occured_at_stage))) == 1
               and graph.value(tabling, ELIDL.occured_at_stage) in controlled_stages
               for tabling in tablings)
    for stage in graph.subjects(RDF.type, OIR.BillStage):
        assert (stage, RDF.type, ELIDL.ProcessStage) not in graph
        stage_concept = graph.value(stage, ELIDL.occured_at_stage)
        assert stage_concept == graph.value(stage, ELIDL.had_activity_type)
        assert stage_concept in controlled_stages
    assert all(target not in set(graph.subjects(RDF.type, OIR.BillStage)) for target in graph.objects(None, ELIDL.occured_at_stage))
    member = URIRef(changed["bill"]["sponsors"][0]["sponsor"]["by"]["uri"])
    assert (None, ELIDL.had_participant_person, member) in graph
    assert not list(graph.triples((member, None, None)))


@pytest.mark.parametrize(("type_suffix", "amendment_type"), [
    ("creamList", OIR.CreamList),
    ("numberedList", OIR.NumberedAmendmentList),
])
@pytest.mark.parametrize("reference_route", ["seanad/6", "stage/seanad/6"])
def test_unmatched_amendment_stage_6_uses_cream_list_stage_without_minting_occurrence(
        type_suffix, amendment_type, reference_route):
    changed = copied()
    bill = changed["bill"]
    item = bill["amendmentLists"][0]["amendmentList"]
    item["amendmentTypeUri"]["uri"] = (
        f"https://data.oireachtas.ie/ie/oireachtas/def/amendment-type/{type_suffix}")
    item["stage"] = {
        "uri": f"{bill['uri']}/{reference_route}",
        "showAs": "Cream List" if type_suffix == "creamList" else "Committee Stage",
    }
    item["stageNo"] = "6"

    graph, report = transform_bill_with_report(changed)
    repeat_graph, repeat_report = transform_bill_with_report(changed)
    assert set(graph) == set(repeat_graph)
    assert report == repeat_report
    assert not any(item["category"] == "unresolved_source_reference"
                   for item in report)
    amendment = next(
        work for work in graph.subjects(
            RDF.type, ELIDL.AmendmentToDraftLegislationWork)
        if (work, OIR.hasAmendmentListType, amendment_type) in graph
        and (work, OIR.stageNo, Literal(
            6, datatype=URIRef("http://www.w3.org/2001/XMLSchema#positiveInteger")))
        in graph)
    tabling = next(subject for subject in graph.subjects(
        RDF.type, ELIDL.LegislativeActivity)
        if str(subject).startswith(f"{amendment}%23tabling-"))

    bill_uri = URIRef(bill["uri"])
    assert (bill_uri, URIRef(ELI + "has_part"), amendment) in graph
    assert (amendment, OIR.hasAmendmentListType, amendment_type) in graph
    assert (amendment, OIR.stageNo, Literal(int(item["stageNo"]),
                                             datatype=URIRef("http://www.w3.org/2001/XMLSchema#positiveInteger"))) in graph
    amendment_identity = _amendment_list_parts(
        item, URIRef(bill["uri"]))[1]
    expression = _derived(amendment, "expression", amendment_identity)
    assert (amendment, URIRef(ELI + "is_realized_by"), expression) in graph
    assert (tabling, RDF.type, ELIDL.LegislativeActivity) in graph
    assert (tabling, ELIDL.activity_date, Literal(item["date"],
                                                   datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))) in graph
    assert (tabling, OIR.inHouse, URIRef("https://data.oireachtas.ie/house/seanad")) in graph
    assert (tabling, ELIDL.occured_at_stage, OIR.CreamListStage) in graph
    missing_occurrence = URIRef(f"{bill['uri']}/stage/seanad/6")
    assert not list(graph.triples((missing_occurrence, None, None)))
    assert not list(graph.triples((None, None, missing_occurrence)))
    assert item["stage"]["uri"] == f"{bill['uri']}/{reference_route}"
    source_occurrences = {
        URIRef(stage["event"]["uri"]) for stage in bill["stages"]}
    assert set(graph.subjects(RDF.type, OIR.BillStage)) == source_occurrences
    assert validate_bill(changed, graph) == report


@pytest.mark.parametrize(("stage_code", "house"), [
    ("3", "seanad"),
    ("4", "seanad"),
    ("7", "seanad"),
    ("06", "seanad"),
])
def test_other_unmatched_amendment_stage_references_remain_unresolved(
        stage_code, house):
    changed = copied()
    bill = changed["bill"]
    first_stage = json.loads(json.dumps(bill["stages"][0]))
    bill["stages"] = [first_stage]
    bill["mostRecentStage"] = {"event": json.loads(
        json.dumps(first_stage["event"]))}
    bill["amendmentLists"] = [bill["amendmentLists"][0]]
    item = bill["amendmentLists"][0]["amendmentList"]
    item["stage"] = {
        "uri": f"{bill['uri']}/{house}/{stage_code}",
        "showAs": f"Unmatched stage {stage_code}",
    }
    item["stageNo"] = stage_code

    graph, report = transform_bill_with_report(changed)
    diagnostic = next(item for item in report
                      if item["category"] == "unresolved_source_reference")
    amendment = URIRef(diagnostic["amendment_list_uri"])
    tabling = next(subject for subject in graph.subjects(
        RDF.type, ELIDL.LegislativeActivity)
        if str(subject).startswith(f"{amendment}%23tabling-"))
    assert not list(graph.objects(tabling, ELIDL.occured_at_stage))
    assert diagnostic["source_stage_uri"] == (
        f"{bill['uri']}/{house}/{stage_code}")
    assert validate_bill(changed, graph) == report


def test_bill_1945_22_distinct_renditions_create_distinct_amendment_works():
    changed = _bill_1945_22_with_amendment_lists()
    bill = changed["bill"]
    graph, report = transform_bill_with_report(changed)
    assert validate_bill(changed, graph) == report

    works = set(graph.subjects(RDF.type, ELIDL.AmendmentToDraftLegislationWork))
    assert len(works) == 2
    realized_by = URIRef(ELI + "is_realized_by")
    embodied_by = URIRef(ELI + "is_embodied_by")
    uri_schema = URIRef(ELI + "uri_schema")
    expected_renditions = {
        f"{bill['uri']}/seanad/4/amendment/numberedList/eng/bills1945-a-kj-04.pdf",
        f"{bill['uri']}/seanad/4/amendment/numberedList/eng/bills1945-a-kj-05.pdf",
    }
    observed_renditions = set()
    for work in works:
        assert (URIRef(bill["uri"]), URIRef(ELI + "has_part"), work) in graph
        assert (work, OIR.stageNo,
                Literal(4, datatype=XSD.positiveInteger)) in graph
        assert (work, OIR.hasAmendmentListType,
                OIR.NumberedAmendmentList) in graph
        assert (work, URIRef("http://www.w3.org/2000/01/rdf-schema#label"),
                Literal("Numbered List [Dáil]")) in graph
        expressions = set(graph.objects(work, realized_by))
        assert len(expressions) == 1
        expression = next(iter(expressions))
        assert expression.count("#") == 1
        assert str(expression).startswith(str(work) + "%23expression-")
        formats = set(graph.objects(expression, embodied_by))
        assert len(formats) == 1
        rendition = next(iter(graph.objects(next(iter(formats)), uri_schema)))
        observed_renditions.add(str(rendition))
    assert observed_renditions == expected_renditions

    tablings = {
        subject for subject in graph.subjects(RDF.type, ELIDL.LegislativeActivity)
        if "%23tabling-" in str(subject)
    }
    assert len(tablings) == 2
    process = URIRef(f"{bill['uri']}#process")
    for tabling in tablings:
        assert list(graph.objects(tabling, ELIDL.forms_part_of)) == [process]
        assert list(graph.objects(tabling, ELIDL.activity_date)) == [
            Literal("1945-07-12", datatype=XSD.date)]
        assert list(graph.objects(tabling, OIR.inHouse)) == [
            URIRef("https://data.oireachtas.ie/house/seanad")]
        assert list(graph.objects(tabling, ELIDL.occured_at_stage)) == [
            OIR.ReportStage]


def test_amendment_list_array_order_does_not_change_output_identities():
    changed = _bill_1945_22_with_amendment_lists()
    graph, report = transform_bill_with_report(changed)
    reordered = json.loads(json.dumps(changed))
    reordered["bill"]["amendmentLists"].reverse()
    reordered_graph, reordered_report = transform_bill_with_report(reordered)

    assert set(graph) == set(reordered_graph)
    assert report == reordered_report
    assert nquads(graph, bill_graph_iri(changed["bill"])) == nquads(
        reordered_graph, bill_graph_iri(reordered["bill"]))
    assert validate_bill(reordered, reordered_graph) == reordered_report


def test_amendment_list_rendition_signature_order_is_canonical():
    changed = _bill_1945_22_with_amendment_lists()
    bill = changed["bill"]
    item = changed["bill"]["amendmentLists"][0]["amendmentList"]
    item["formats"]["xml"] = {"uri": item["formats"]["pdf"]["uri"] + ".xml"}
    _, identity = _amendment_list_parts(item, URIRef(bill["uri"]))
    reversed_formats = json.loads(json.dumps(item))
    reversed_formats["formats"] = {
        "xml": reversed_formats["formats"]["xml"],
        "pdf": reversed_formats["formats"]["pdf"],
    }
    _, reversed_identity = _amendment_list_parts(
        reversed_formats, URIRef(bill["uri"]))

    expected = [
        {"format": "pdf", "uri": item["formats"]["pdf"]["uri"]},
        {"format": "xml", "uri": item["formats"]["xml"]["uri"]},
    ]
    assert identity["renditions"] == expected
    assert reversed_identity == identity


def test_exact_duplicate_amendment_list_source_records_collapse():
    once = _bill_1945_22_with_amendment_lists()
    once["bill"]["amendmentLists"] = [
        once["bill"]["amendmentLists"][0]]
    once_graph, once_report = transform_bill_with_report(once)

    duplicated = json.loads(json.dumps(once))
    duplicated["bill"]["amendmentLists"].append(
        json.loads(json.dumps(duplicated["bill"]["amendmentLists"][0])))
    duplicate_graph, duplicate_report = transform_bill_with_report(duplicated)

    assert set(once_graph) == set(duplicate_graph)
    assert once_report == duplicate_report
    assert len(set(duplicate_graph.subjects(
        RDF.type, ELIDL.AmendmentToDraftLegislationWork))) == 1
    assert len({subject for subject in duplicate_graph.subjects(
        RDF.type, ELIDL.LegislativeActivity) if "%23tabling-" in str(subject)}) == 1
    assert validate_bill(duplicated, duplicate_graph) == duplicate_report


def test_amendment_list_show_as_is_not_identity_but_conflicts_fail_closed():
    changed = _bill_1945_22_with_amendment_lists()
    graph, _ = transform_bill_with_report(changed)
    original_works = set(graph.subjects(
        RDF.type, ELIDL.AmendmentToDraftLegislationWork))

    relabelled = json.loads(json.dumps(changed))
    relabelled["bill"]["amendmentLists"][0]["amendmentList"]["showAs"] = (
        "Corrected amendment list label")
    relabelled_graph, _ = transform_bill_with_report(relabelled)
    assert set(relabelled_graph.subjects(
        RDF.type, ELIDL.AmendmentToDraftLegislationWork)) == original_works

    conflict = json.loads(json.dumps(changed))
    duplicate = json.loads(json.dumps(conflict["bill"]["amendmentLists"][0]))
    duplicate["amendmentList"]["showAs"] = "Conflicting label"
    conflict["bill"]["amendmentLists"].append(duplicate)
    with pytest.raises(ValueError, match="conflicting amendment-list source content"):
        validate_bill_source(conflict)
    with pytest.raises(ValueError, match="conflicting amendment-list source content"):
        transform_bill_with_report(conflict)


def test_amendment_list_rendition_identity_requires_canonical_source_iris():
    changed = _bill_1945_22_with_amendment_lists()
    changed["bill"]["amendmentLists"][0]["amendmentList"]["formats"]["pdf"]["uri"] = (
        "https://example.org/amendment.pdf")
    with pytest.raises(ValueError, match="canonical Oireachtas HTTPS origin"):
        validate_bill_source(changed)


@pytest.mark.parametrize("stage", [
    None,
    {"uri": "not-an-absolute-iri"},
    {"showAs": "Missing URI"},
    {"uri": "https://data.oireachtas.ie/ie/oireachtas/bill/2025/60/not-a-stage"},
    {"uri": "https://data.oireachtas.ie/ie/oireachtas/bill/2025/61/stage/dail/3"},
    {"uri": "https://data.oireachtas.ie/ie/oireachtas/bill/2025/61/seanad/6"},
])
def test_malformed_amendment_stage_references_fail_closed(stage):
    changed = copied()
    changed["bill"]["amendmentLists"][0]["amendmentList"]["stage"] = stage
    with pytest.raises(ValueError):
        transform_bill_with_report(changed)


def test_cream_list_amendment_type_maps_to_controlled_concept():
    changed = copied()
    amendment_list = changed["bill"]["amendmentLists"][0]["amendmentList"]
    amendment_list["amendmentTypeUri"]["uri"] = (
        "https://data.oireachtas.ie/ie/oireachtas/def/amendment-type/creamList")

    graph, report = transform_bill_with_report(changed)
    amendment = next(
        work for work in graph.subjects(
            RDF.type, ELIDL.AmendmentToDraftLegislationWork)
        if (work, OIR.hasAmendmentListType, OIR.CreamList) in graph)

    assert (amendment, OIR.hasAmendmentListType, OIR.CreamList) in graph
    assert validate_bill(changed, graph) == report

    ontology = Graph().parse(ROOT / "ontology/legislation.owl.ttl")
    skos_concept = URIRef("http://www.w3.org/2004/02/skos/core#Concept")
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    top_concept_of = URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf")
    in_scheme = URIRef("http://www.w3.org/2004/02/skos/core#inScheme")
    assert (OIR.CreamList, RDF.type, skos_concept) in ontology
    assert (OIR.CreamList, RDF.type, named_individual) in ontology
    assert (OIR.CreamList, top_concept_of, OIR.AmendmentListTypeTable) in ontology
    assert (OIR.CreamList, in_scheme, OIR.AmendmentListTypeTable) in ontology


def test_unknown_amendment_type_uri_fails_closed():
    changed = copied()
    changed["bill"]["amendmentLists"][0]["amendmentList"]["amendmentTypeUri"]["uri"] = (
        "https://data.oireachtas.ie/ie/oireachtas/def/amendment-type/unreviewedList")
    with pytest.raises(ValueError, match="unsupported amendmentList.amendmentTypeUri.uri"):
        transform_bill_with_report(changed)


def test_ver_e_bill_version_maps_to_reviewed_version_e_individual():
    changed = copied()
    original = next(wrapped["version"] for wrapped in changed["bill"]["versions"]
                    if wrapped["version"].get("docType") == "bill")
    version = json.loads(json.dumps(original))
    version["uri"] = version["uri"].rsplit("/", 1)[0] + "/ver_e"
    version["showAs"] = "As passed by both Houses of the Oireachtas"
    changed["bill"]["versions"].append({"version": version})

    graph, report = transform_bill_with_report(changed)
    expression = next(graph.subjects(URIRef(ELI + "version"), OIR.VersionE))
    assert expression != URIRef(version["uri"])
    assert (expression, RDF.type, URIRef(ELI + "LegalExpression")) in graph
    assert (expression, URIRef(ELI + "version"), OIR.VersionE) in graph
    assert (expression, URIRef("http://www.w3.org/2000/01/rdf-schema#label"),
            Literal(version["showAs"])) in graph
    assert validate_bill(changed, graph) == report

    ontology = Graph().parse(ROOT / "ontology/legislation.owl.ttl")
    version_class = URIRef("http://data.europa.eu/eli/eli-draft-legislation-ontology#LegislativeProcessWorkVersion")
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    version_table = URIRef("http://data.europa.eu/eli/ontology#VersionTable")
    assert (OIR.VersionE, RDF.type, version_class) in ontology
    assert (OIR.VersionE, RDF.type, named_individual) in ontology
    assert (OIR.VersionE, URIRef("http://www.w3.org/2004/02/skos/core#prefLabel"),
            Literal("As passed by both Houses of the Oireachtas", lang="en")) in ontology
    assert (OIR.VersionE, URIRef("http://www.w3.org/2004/02/skos/core#inScheme"),
            version_table) in ontology
    assert (OIR.VersionE, URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf"),
            version_table) in ontology


def test_unknown_bill_version_suffix_fails_closed():
    changed = copied()
    version = next(wrapped["version"] for wrapped in changed["bill"]["versions"]
                   if wrapped["version"].get("docType") == "bill")
    version["uri"] = version["uri"].rsplit("/", 1)[0] + "/ver_f"
    with pytest.raises(ValueError, match="unsupported bill version"):
        transform_bill_with_report(changed)


def test_bill_version_uri_must_be_beneath_its_owning_bill():
    changed = copied()
    version = next(wrapped["version"] for wrapped in changed["bill"]["versions"]
                   if wrapped["version"].get("docType") == "bill")
    version["uri"] = (
        "https://data.oireachtas.ie/ie/oireachtas/bill/2024/99/eng/ver_b")
    with pytest.raises(ValueError, match="beneath its owning Bill URI"):
        transform_bill_with_report(changed)


def test_reused_bill_1927_4_version_uri_gets_three_semantic_expressions():
    changed = copied_for_bill(1927, 4)
    version_uri = "https://data.oireachtas.ie/ie/oireachtas/bill/1927/4/eng/ver_b"
    versions = [
        bill_version(version_uri, "1927-04-07", "As passed by Dáil Éireann",
                     "https://data.oireachtas.ie/ie/oireachtas/bill/1927/4/eng/ver_b/bills1926-27-1p-04.pdf"),
        bill_version(version_uri, "1927-04-06", "As passed by Dáil Éireann",
                     "https://data.oireachtas.ie/ie/oireachtas/bill/1927/4/eng/ver_b/bills1926-27-1p-03.pdf"),
        bill_version(version_uri, "1927-03-25",
                     "As amended in Committee/Select Committee [Dáil Éireann]",
                     "https://data.oireachtas.ie/ie/oireachtas/bill/1927/4/eng/ver_b/bills1926-27-1p-02.pdf"),
    ]
    changed["bill"]["versions"] = versions

    graph, report = transform_bill_with_report(changed)
    assert validate_bill(changed, graph) == report
    version_predicate = URIRef(ELI + "version")
    date_predicate = URIRef(ELI + "date_document")
    language_predicate = URIRef(ELI + "language")
    realized_by = URIRef(ELI + "is_realized_by")
    embodied_by = URIRef(ELI + "is_embodied_by")
    uri_schema = URIRef(ELI + "uri_schema")
    media_type = URIRef(ELI + "media_type")
    expected_language = URIRef(
        "http://publications.europa.eu/resource/authority/language/ENG")
    expected_expressions = set()
    for wrapped in versions:
        item = wrapped["version"]
        matching = {
            expression for expression in graph.subjects(version_predicate, OIR.VersionB)
            if (expression, date_predicate, Literal(
                    item["date"], datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))) in graph
            and (expression, URIRef(
                "http://www.w3.org/2000/01/rdf-schema#label"), Literal(item["showAs"])) in graph
        }
        assert len(matching) == 1
        expression = matching.pop()
        expected_expressions.add(expression)
        assert expression != URIRef(version_uri)
        assert (expression, RDF.type, URIRef(ELI + "LegalExpression")) in graph
        assert (URIRef(changed["bill"]["uri"]), realized_by, expression) in graph
        assert list(graph.objects(expression, date_predicate)) == [Literal(
            item["date"], datatype=URIRef("http://www.w3.org/2001/XMLSchema#date"))]
        assert list(graph.objects(expression, language_predicate)) == [expected_language]
        formats = list(graph.objects(expression, embodied_by))
        assert len(formats) == 1
        assert list(graph.objects(formats[0], uri_schema)) == [
            URIRef(item["formats"]["pdf"]["uri"])]
        assert list(graph.objects(formats[0], media_type)) == [
            URIRef("https://www.iana.org/assignments/media-types/application/pdf")]
    assert len(expected_expressions) == 3

    reordered = copied_for_bill(1927, 4)
    reordered["bill"]["versions"] = list(reversed(versions))
    reordered_graph, reordered_report = transform_bill_with_report(reordered)
    assert set(graph) == set(reordered_graph)
    assert report == reordered_report
    assert nquads(graph, bill_graph_iri(changed["bill"])) == nquads(
        reordered_graph, bill_graph_iri(reordered["bill"]))

    exact_duplicate = copied_for_bill(1927, 4)
    exact_duplicate["bill"]["versions"] = [*versions, json.loads(json.dumps(versions[0]))]
    duplicate_graph, duplicate_report = transform_bill_with_report(exact_duplicate)
    assert set(graph) == set(duplicate_graph)
    assert report == duplicate_report
    assert validate_bill(exact_duplicate, duplicate_graph) == duplicate_report


def test_same_bill_expression_metadata_with_distinct_renditions_has_distinct_formats():
    changed = copied_for_bill(1994, 1)
    version_uri = "https://data.oireachtas.ie/ie/oireachtas/bill/1994/1/eng/ver_b"
    renditions = {
        "https://data.oireachtas.ie/ie/oireachtas/bill/1994/1/eng/ver_b/bills1995-10056-04.pdf",
        "https://data.oireachtas.ie/ie/oireachtas/bill/1994/1/eng/ver_b/bills1995-10056-05.pdf",
    }
    versions = [
        bill_version(version_uri, "1995-05-31", "As passed by Dáil Éireann", uri)
        for uri in sorted(renditions)
    ]
    changed["bill"]["versions"] = versions

    graph, report = transform_bill_with_report(changed)
    assert validate_bill(changed, graph) == report
    expressions = set(graph.subjects(URIRef(ELI + "version"), OIR.VersionB))
    assert len(expressions) == 1
    expression = next(iter(expressions))
    formats = set(graph.objects(expression, URIRef(ELI + "is_embodied_by")))
    assert len(formats) == 2
    assert {next(graph.objects(format_iri, URIRef(ELI + "uri_schema")))
            for format_iri in formats} == {URIRef(uri) for uri in renditions}
    assert all(len(list(graph.objects(format_iri, URIRef(ELI + "uri_schema")))) == 1
               and len(list(graph.objects(format_iri, URIRef(ELI + "media_type")))) == 1
               and len(list(graph.subjects(URIRef(ELI + "is_embodied_by"), format_iri))) == 1
               for format_iri in formats)


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
        with pytest.raises(ValueError, match=(
                "controlled ELI language|Format requires|related-document Expression")):
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
    controlled_stages = {
        OIR.FirstStage, OIR.SecondStage, OIR.CommitteeStage, OIR.ReportStage,
        OIR.FifthStage, OIR.Enacted, OIR.CreamListStage,
        OIR.ReferralToSupremeCourtArt26,
    }
    controlled_activity_types = controlled_stages | set(EVENTS.values()) | {
        OIR.Presentation, OIR.Introduction, OIR.Application}
    assert controlled_stages <= controlled_activity_types
    assert all((term, RDF.type, ELIDL.ProcessStage) in ontology for term in controlled_stages)
    assert all((term, RDF.type, ELIDL.ActivityType) in ontology for term in controlled_activity_types)
    assert not any((term, RDF.type, OIR.BillEvent) in ontology or (term, RDF.type, OIR.BillStage) in ontology or (term, RDF.type, OIR.BillDelivery) in ontology for term in controlled_activity_types)


def test_new_bill_event_types_are_controlled_table_concepts_not_statuses_or_outcomes():
    ontology = Graph().parse(ROOT / "ontology/events.owl.ttl")
    skos_concept = URIRef("http://www.w3.org/2004/02/skos/core#Concept")
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    top_concept_of = URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf")
    in_scheme = URIRef("http://www.w3.org/2004/02/skos/core#inScheme")
    for term in (OIR.BillDefeatedEvent, OIR.BillLapsedEvent,
                 OIR.BillWithdrawnEvent, OIR.Referendum,
                 OIR.ReferralToSupremeCourtArt26):
        assert (term, RDF.type, ELIDL.ActivityType) in ontology
        assert (term, RDF.type, skos_concept) in ontology
        assert (term, RDF.type, named_individual) in ontology
        assert (term, top_concept_of, OIR.BillEventTable) in ontology
        assert (term, in_scheme, OIR.BillEventTable) in ontology
    assert (OIR.ReferralToSupremeCourtArt26, RDF.type,
            ELIDL.ProcessStage) in ontology
    assert (OIR.ReferralToSupremeCourtArt26, RDF.type, skos_concept) in ontology
    assert (OIR.ReferralToSupremeCourtArt26, RDF.type,
            named_individual) in ontology
    assert OIR.BillLapsedEvent != OIR.LapsedBill
    assert OIR.BillDefeatedEvent != OIR.DefeatedBill
    assert OIR.BillWithdrawnEvent != OIR.Withdrawn
    assert EVENTS["bill-restored"] == OIR.RestoreBill
    assert EVENTS["recommittal"] == OIR.RecommitBill


def test_controlled_stage_and_activity_type_target_mutations_fail():
    graph, _ = transform_bill_with_report(RECORD)
    stage = next(graph.subjects(RDF.type, OIR.BillStage))
    tabling = next(subject for subject in graph.subjects(ELIDL.occured_at_stage, None) if "%23tabling-" in str(subject))
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
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(tmp_path / "state.sqlite"), output_nq=None, output_ttl=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query")
    calls = []
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): calls.append(args)
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    assert cli.run_bills(args) == 0 and len(calls) == 1
    from oireachtas_etl.state import CoreStateStore
    with CoreStateStore(Path(args.state_db)) as store:
        state = store.get_resource("legislation", RECORD["bill"]["uri"])
    assert state["publication_state"] == "clean" and state["published_source_hash"] == source_hash(RECORD["bill"])
    assert state["published_payload_hash"] and state["pending_payload"] is None
    monkeypatch.setattr(cli, "transform_bill_with_report", lambda value: (_ for _ in ()).throw(AssertionError("unchanged bill transformed")))
    assert cli.run_bills(args) == 0 and len(calls) == 1


def test_bill_publication_failure_and_competency_failure_are_dirty_and_retry(tmp_path, monkeypatch):
    from oireachtas_etl import cli
    fixture = tmp_path / "bill.json"; fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}}, "results": [RECORD]}))
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"), state_db=str(tmp_path / "state.sqlite"), output_nq=None, output_ttl=None, fuseki_gsp_url="http://example.test/data", fuseki_sparql_url="http://example.test/query")
    class FailingLoader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): raise RuntimeError("PUT failed")
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", FailingLoader); monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    with pytest.raises(RuntimeError, match="PUT failed"): cli.run_bills(args)
    from oireachtas_etl.state import CoreStateStore
    with CoreStateStore(Path(args.state_db)) as store:
        entry = store.get_resource("legislation", RECORD["bill"]["uri"])
    assert entry["publication_state"] == "dirty" and entry["published_source_hash"] is None
    assert entry["pending_source_hash"] == source_hash(RECORD["bill"])
    assert entry["pending_payload"] and entry["pending_payload_hash"]
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): pass
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader); monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: (_ for _ in ()).throw(ValueError("competency failed")))
    with pytest.raises(ValueError, match="competency failed"): cli.run_bills(args)
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.get_resource("legislation", RECORD["bill"]["uri"])["publication_state"] == "dirty"
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args: None)
    assert cli.run_bills(args) == 0
    with CoreStateStore(Path(args.state_db)) as store:
        assert store.get_resource("legislation", RECORD["bill"]["uri"])["publication_state"] == "clean"


def test_bills_full_scan_replays_durable_dirty_payload_for_unobserved_bill(tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli
    from oireachtas_etl.serialization import ntriples
    from oireachtas_etl.state import CoreStateStore

    identity = "https://data.oireachtas.ie/ie/oireachtas/bill/2026/999"
    graph_iri = "https://data.oireachtas.ie/graph/bill/2026/999"
    graph = Graph()
    graph.add((URIRef(identity), RDF.type, ELIDL.DraftLegislationWork))
    payload = ntriples(graph)
    database = tmp_path / "core.sqlite"
    with CoreStateStore(database) as store:
        run_id = store.start_run("legislation", "full_refresh", is_complete=True,
                                 parameters={"seed": True})
        store.observe_resource("legislation", identity, graph_iri, "a" * 64, run_id)
        store.mark_publication_dirty("legislation", identity, source_hash="a" * 64,
                                     graph_iri=graph_iri, payload=payload, contract_version=1)
        store.finish_run(run_id, success=False, error="interrupted before verification")

    calls = []
    class Loader:
        def __init__(self, *args, **kwargs): pass
        def replace(self, *args, **kwargs): calls.append(args)
    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "verify_bill_competency", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "verify_core_graph", lambda *args: None)
    fixture = ROOT / "data/api_examples/bill.json"
    args = Namespace(fixture=str(fixture), offline=False, raw_dir=str(tmp_path / "raw"),
                     state_db=str(database), output_nq=None, output_ttl=None,
                     fuseki_gsp_url="http://example.test/data",
                     fuseki_sparql_url="http://example.test/query")
    assert cli.run_bills(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["published"] == 2
    assert (graph_iri, payload) in calls
    with CoreStateStore(database) as store:
        recovered = store.get_resource("legislation", identity)
        assert recovered["publication_state"] == "clean"
        assert recovered["published_source_hash"] == "a" * 64
        assert recovered["pending_payload"] is None


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


@pytest.mark.parametrize(("suffix", "expected"), [
    ("current", OIR.CurrentBill),
    ("published", OIR.CurrentBill),
    ("rejected-at-referendum", OIR.RejectedAtReferendumBill),
])
def test_reviewed_bill_status_aliases_map_to_distinct_controlled_statuses(
        suffix, expected):
    changed = _bill_with_status(
        2025, 60,
        f"https://data.oireachtas.ie/ie/oireachtas/def/bill-status/{suffix}")
    process = URIRef(f"{changed['bill']['uri']}#process")
    graph, report = transform_bill_with_report(changed)
    assert (process, ELIDL.process_status, expected) in graph
    assert OIR.RejectedAtReferendumBill != OIR.DefeatedBill
    assert validate_bill(changed, graph) == report


def test_referendum_stage_reuses_referendum_event_concept_as_stage_and_activity():
    changed = _bill_with_status(2025, 60,
        "https://data.oireachtas.ie/ie/oireachtas/def/bill-status/current")
    stage = changed["bill"]["stages"][0]["event"]
    stage["stageURI"] = (
        "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/referendum")
    stage["showAs"] = "Referendum"
    changed["bill"]["mostRecentStage"]["event"] = json.loads(json.dumps(stage))
    graph, report = transform_bill_with_report(changed)
    occurrence = URIRef(stage["uri"])
    assert STAGES["referendum"] == EVENTS["referendum"] == OIR.Referendum
    assert (occurrence, ELIDL.had_activity_type, OIR.Referendum) in graph
    assert (occurrence, ELIDL.occured_at_stage, OIR.Referendum) in graph
    assert validate_bill(changed, graph) == report
    ontology = Graph().parse(ROOT / "ontology/events.owl.ttl")
    assert (OIR.Referendum, RDF.type, ELIDL.ProcessStage) in ontology
    assert (OIR.Referendum, RDF.type, ELIDL.ActivityType) in ontology


def _source_event(bill_uri, *, suffix="recommittal", date="2025-01-02",
                  chamber=None, show_as="Recommittal"):
    return {
        "uri": f"{bill_uri}/reused-source-event-key",
        "eventURI": f"https://data.oireachtas.ie/ie/oireachtas/def/bill-event/{suffix}",
        "showAs": show_as,
        "chamber": (None if chamber is None else {"uri": (
            f"https://data.oireachtas.ie/ie/oireachtas/def/house/{chamber}")}),
        "dates": [{"date": date}],
    }


def test_bill_event_identity_separates_date_and_chamber_conflicts():
    changed = copied()
    bill = changed["bill"]
    same_date_null_chamber = _source_event(bill["uri"])
    different_date = _source_event(bill["uri"], date="2025-01-03")
    different_chamber = _source_event(
        bill["uri"], chamber="dail")
    bill["events"] = [{"event": event} for event in (
        same_date_null_chamber, different_date, different_chamber)]
    graph, report = transform_bill_with_report(changed)
    identities = {_bill_event_identity(event)[0] for event in (
        same_date_null_chamber, different_date, different_chamber)}
    assert len(identities) == 3
    assert all((identity, RDF.type, OIR.BillEvent) in graph
               for identity in identities)
    assert validate_bill(changed, graph) == report


def test_bill_event_identity_normalizes_date_order_and_collapses_exact_duplicates():
    changed = copied()
    bill = changed["bill"]
    first = _source_event(bill["uri"])
    first["dates"] = [{"date": "2025-01-03"}, {"date": "2025-01-02"}]
    reordered = json.loads(json.dumps(first))
    reordered["dates"].reverse()
    bill["events"] = [{"event": first}, {"event": reordered},
                      {"event": json.loads(json.dumps(first))}]
    graph, report = transform_bill_with_report(changed)
    occurrence = _bill_event_identity(first)[0]
    assert _bill_event_identity(first)[0] == _bill_event_identity(reordered)[0]
    assert len(set(graph.subjects(RDF.type, OIR.BillEvent)) -
               set(graph.subjects(RDF.type, OIR.BillStage))) >= 1
    assert len(list(graph.objects(occurrence, ELIDL.activity_date))) == 2
    assert validate_bill(changed, graph) == report
    reordered_source = copied()
    reordered_source["bill"]["events"] = list(reversed(bill["events"]))
    reordered_graph, _ = transform_bill_with_report(reordered_source)
    assert set(graph) == set(reordered_graph)


def test_bill_event_complete_identity_with_conflicting_label_fails_closed():
    changed = copied()
    bill = changed["bill"]
    first = _source_event(bill["uri"])
    conflicting = _source_event(bill["uri"], show_as="Different mapped label")
    bill["events"] = [{"event": first}, {"event": conflicting}]
    with pytest.raises(ValueError, match="conflicting mapped semantics"):
        transform_bill_with_report(changed)
    with pytest.raises(ValueError, match="conflicting mapped semantics"):
        validate_bill_source(changed)


def test_nested_derived_bill_iris_extend_one_valid_fragment():
    process = URIRef(f"{BILL}#process")
    participation = _derived(process, "sponsor", {"member": "example"})
    expression = _derived(participation, "expression", {"kind": "test"})
    assert str(participation).startswith(f"{BILL}#process%23sponsor-")
    assert str(expression).startswith(str(participation) + "%23expression-")
    assert str(participation).count("#") == str(expression).count("#") == 1

    changed = copied()
    changed["bill"]["relatedDocs"] = [
        _related_document(changed["bill"]["uri"]),
    ]
    graph, _ = transform_bill_with_report(changed)
    iri_terms = {
        term for triple in graph for term in triple if isinstance(term, URIRef)
    }
    bill_uri = str(BILL)
    bill_path = urlsplit(bill_uri).path
    owned_iris = {
        str(term) for term in iri_terms
        if str(term) == bill_uri
        or str(term).startswith((bill_uri + "#", bill_uri + "/"))
    }
    assert owned_iris
    for iri in owned_iris:
        parsed = urlsplit(iri)
        assert parsed.scheme == "https"
        assert parsed.netloc == "data.oireachtas.ie"
        assert parsed.path.startswith(bill_path)
        assert not parsed.query
        assert iri.count("#") <= 1
        assert "#" not in parsed.fragment
        assert not re.search(r'[<>"{}|\\^`\s]', iri)
        assert not re.search(r"%(?![A-Fa-f0-9]{2})", iri)


def _related_document(bill_uri, *, doc_type="memo", date="2025-01-02",
                       label="Explanatory Memorandum", pdf="first.pdf",
                       language="eng"):
    prefix = f"{bill_uri}/eng/memo"
    return {"relatedDoc": {
        "uri": prefix,
        "docType": doc_type,
        "date": date,
        "lang": language,
        "showAs": label,
        "formats": {"pdf": {"uri": f"{prefix}/{pdf}"}, "xml": None},
    }}


def test_related_document_date_conflicts_create_expressions_of_one_work():
    changed = copied()
    bill = changed["bill"]
    first = _related_document(bill["uri"])
    second = _related_document(bill["uri"], date="2025-01-03")
    bill["relatedDocs"] = [first, second]
    graph, report = transform_bill_with_report(changed)
    source_uri = URIRef(first["relatedDoc"]["uri"])
    work = URIRef(f"{source_uri}#work")
    expressions = set(graph.objects(work, URIRef(ELI + "is_realized_by")))
    assert len(expressions) == 2
    assert all((bill_uri, URIRef(ELI + "has_part"), work) in graph
               for bill_uri in (URIRef(bill["uri"]),))
    assert all((expression, RDF.type, URIRef(ELI + "LegalExpression")) in graph
               for expression in expressions)
    assert validate_bill(changed, graph) == report


def test_related_document_renditions_and_exact_duplicates_share_expression_formats():
    changed = copied()
    bill = changed["bill"]
    first = _related_document(bill["uri"])
    second = _related_document(bill["uri"], pdf="second.pdf")
    duplicate = json.loads(json.dumps(first))
    bill["relatedDocs"] = [first, second, duplicate]
    graph, report = transform_bill_with_report(changed)
    source_uri = URIRef(first["relatedDoc"]["uri"])
    work = URIRef(f"{source_uri}#work")
    expressions = set(graph.objects(work, URIRef(ELI + "is_realized_by")))
    assert len(expressions) == 1
    expression = next(iter(expressions))
    formats = set(graph.objects(expression, URIRef(ELI + "is_embodied_by")))
    assert len(formats) == 2
    assert len({next(graph.objects(item, URIRef(ELI + "uri_schema")))
                for item in formats}) == 2
    assert validate_bill(changed, graph) == report
    changed["bill"]["relatedDocs"] = [second, duplicate, first]
    reordered_graph, _ = transform_bill_with_report(changed)
    assert set(graph) == set(reordered_graph)


def test_related_document_work_rejects_incompatible_controlled_types():
    changed = copied()
    bill = changed["bill"]
    first = _related_document(bill["uri"], doc_type="memo")
    second = _related_document(bill["uri"], doc_type="digest")
    bill["relatedDocs"] = [first, second]
    with pytest.raises(ValueError, match="conflicting controlled types"):
        transform_bill_with_report(changed)


def test_bill_digest_is_a_resource_type_and_is_emitted_as_a_bill_owned_work():
    changed = copied()
    bill = changed["bill"]
    digest = _related_document(bill["uri"], doc_type="digest",
                              label="Bill Digest")
    bill["relatedDocs"] = [digest]
    graph, report = transform_bill_with_report(changed)
    source_uri = URIRef(digest["relatedDoc"]["uri"])
    work = URIRef(f"{source_uri}#work")
    assert (URIRef(bill["uri"]), URIRef(ELI + "has_part"), work) in graph
    assert (work, URIRef(ELI + "type_document"), OIR.BillDigest) in graph
    assert validate_bill(changed, graph) == report
    ontology = Graph().parse(ROOT / "ontology/legislation.owl.ttl")
    named_individual = URIRef("http://www.w3.org/2002/07/owl#NamedIndividual")
    resource_type = URIRef(ELI + "ResourceType")
    skos_pref_label = URIRef("http://www.w3.org/2004/02/skos/core#prefLabel")
    in_scheme = URIRef("http://www.w3.org/2004/02/skos/core#inScheme")
    top_concept = URIRef("http://www.w3.org/2004/02/skos/core#topConceptOf")
    table = URIRef(ELI + "ResourceTypeTable")
    assert (OIR.BillDigest, RDF.type, resource_type) in ontology
    assert (OIR.BillDigest, RDF.type, named_individual) in ontology
    assert (OIR.BillDigest, skos_pref_label, Literal("Bill Digest", lang="en")) in ontology
    assert (OIR.BillDigest, in_scheme, table) in ontology
    assert (OIR.BillDigest, top_concept, table) in ontology


def test_nullable_primary_sponsor_retains_participation_without_flag():
    changed = copied()
    changed["bill"]["sponsors"][0]["sponsor"]["isPrimary"] = None
    graph, report = transform_bill_with_report(changed)
    sponsor = changed["bill"]["sponsors"][0]["sponsor"]
    process = URIRef(f"{changed['bill']['uri']}#process")
    participation = next(graph.objects(process, ELIDL.had_participation))
    assert (participation, RDF.type, ELIDL.Participation) in graph
    assert not list(graph.objects(participation, OIR.isPrimarySponsor))
    diagnostic = next(item for item in report
                      if item["path"] == "bill.sponsors[].sponsor.isPrimary")
    assert diagnostic["category"] == "source_unknown"
    assert validate_bill(changed, graph) == report
    broken = Graph(); [broken.add(triple) for triple in graph]
    broken.add((participation, OIR.isPrimarySponsor,
                Literal(False, datatype=XSD.boolean)))
    with pytest.raises(ValueError, match="zero-or-one"):
        validate_bill(changed, broken)


def _known_quarantine_record(identity):
    year, number = identity.split("/", 1)
    changed = copied_for_bill(int(year), number)
    if identity == "2024/48":
        event = changed["bill"]["stages"][-2]["event"]
        event["stageURI"] = (
            "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/None")
        event["uri"] = f"{changed['bill']['uri']}/stage/seanad/None"
    else:
        changed["bill"]["stages"][0]["event"]["dates"][0]["date"] = None
    return changed


def test_only_reviewed_malformed_bill_source_records_are_quarantined():
    expected = {"2024/48", "1959/P3", "1965/P1", "1965/P3"}
    diagnostics = []
    for identity in sorted(expected):
        diagnostics.extend(known_bill_source_quarantines(
            _known_quarantine_record(identity)))
    assert {item["bill_identity"] for item in diagnostics} == expected
    assert all(item["category"] == "source_quarantine"
               and item["path"] and item["reason"] for item in diagnostics)
    unknown = copied_for_bill(2025, 999)
    unknown["bill"]["stages"][0]["event"]["dates"][0]["date"] = None
    assert known_bill_source_quarantines(unknown) == []


def test_bill_offline_complete_run_reports_quarantines_and_emits_no_graphs_for_them(
        tmp_path, capsys):
    from oireachtas_etl.cli import run_bills
    identities = ("2024/48", "1959/P3", "1965/P1", "1965/P3")
    records = [_known_quarantine_record(identity) for identity in identities]
    records.append(copied())
    fixture = tmp_path / "bills.json"
    fixture.write_text(json.dumps({"head": {"counts": {"billCount": len(records)}},
                                   "results": records}))
    output = tmp_path / "bills.nq"
    args = Namespace(fixture=str(fixture), offline=True,
                     raw_dir=str(tmp_path / "raw"), state_file=None,
                     output_nq=str(output), output_ttl=None,
                     fuseki_gsp_url=None, fuseki_sparql_url=None)
    assert run_bills(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source_records_observed"] == 5
    assert result["represented_bill_graphs"] == 1
    assert result["source_quarantined_bill_count"] == 4
    assert {item.split("/")[-2] + "/" + item.split("/")[-1]
            for item in result["source_quarantined_bills"]} == set(identities)
    output_text = output.read_text()
    assert output_text.strip()
    assert not any(f"graph/bill/{year}/{number}>" in output_text
                   for year, number in (value.split("/", 1)
                                        for value in identities))


def test_bill_quarantine_retains_prior_accepted_graph_without_replacement(
        tmp_path, monkeypatch, capsys):
    from oireachtas_etl import cli

    identity = "https://data.oireachtas.ie/ie/oireachtas/bill/2024/48"
    row = {
        "resource_iri": identity,
        "graph_iri": "https://data.oireachtas.ie/graph/bill/2024/48",
        "publication_state": "clean",
        "published_source_hash": "accepted-hash",
        "published_payload": "accepted-payload",
        "last_published_at": "2026-01-01T00:00:00+00:00",
    }

    class Store:
        def __init__(self):
            self.observed = []

        def get_resource(self, endpoint, resource):
            assert endpoint == "legislation" and resource == identity
            return row

        def observe_resource(self, endpoint, resource, graph_iri, digest, run_id):
            self.observed.append((resource, graph_iri, run_id))
            return row

        def resources(self, endpoint):
            assert endpoint == "legislation"
            return [row]

    fixture = tmp_path / "quarantined.json"
    fixture.write_text(json.dumps({"head": {"counts": {"billCount": 1}},
                                   "results": [_known_quarantine_record("2024/48")]}))
    replacements = []

    class Loader:
        def __init__(self, *args, **kwargs):
            pass

        def replace(self, *args, **kwargs):
            replacements.append(args)

    monkeypatch.setattr(cli, "FusekiGraphStoreLoader", Loader)
    monkeypatch.setattr(cli, "FusekiSparqlClient", lambda *args, **kwargs: object())
    args = Namespace(fixture=str(fixture), offline=False,
                     raw_dir=str(tmp_path / "raw"), output_nq=None,
                     output_ttl=None, fuseki_gsp_url="http://example.test/data",
                     fuseki_sparql_url="http://example.test/query")
    store = Store()
    assert cli._run_bills_impl(
        args, store, "12345678-1234-5678-1234-567812345678") == 0
    result = json.loads(capsys.readouterr().out)
    assert store.observed and not replacements
    assert result["source_quarantines"][0]["preservation_status"] == \
        "previous_accepted_graph_retained"
