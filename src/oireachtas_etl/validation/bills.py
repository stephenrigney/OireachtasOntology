"""Fail-closed validation for one Bill-owned lifecycle graph."""
from __future__ import annotations

from importlib.resources import files
from urllib.parse import urlsplit

from pyshacl import validate
from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from ..transforms.bills import EVENTS, LANGUAGES, MEDIA_TYPES, METHODS, STAGES, bill_graph_iri
from ..transforms.common import ELIDL, OIR, date_literal, datetime_literal, iri
from .houses import validate_rdf
from .vocabulary import assert_phase4_vocabulary, pinned_vocabulary_graphs

RESOURCES = files("oireachtas_etl.validation.resources")
ELI = "http://data.europa.eu/eli/ontology#"


def extract_bill_omissions(wrapper: dict) -> list[dict]:
    """Return stable deferred/ownership reports without constructing RDF."""
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict):
        raise ValueError("each Legislation result must contain a bill object")
    bill = wrapper["bill"]; result = []
    act = bill.get("act")
    if isinstance(act, dict) and act.get("uri"):
        result.append({"path": "bill.act.*", "context": str(act["uri"]), "category": "ownership_deferred", "reason": "Act descriptions are owned by a later Acts ETL; Bill graph retains only eli:basis_for"})
    for wrapped in bill.get("versions", []):
        version = wrapped.get("version", {}) if isinstance(wrapped, dict) else {}
        if isinstance(version, dict) and version.get("docType") == "act":
            result.append({"path": "bill.versions[].version", "context": str(version.get("uri", "")), "category": "ownership_deferred", "reason": "Act descriptions and expressions are owned by a later Acts ETL"})
    for wrapped in bill.get("stages", []):
        event = wrapped.get("event", {}) if isinstance(wrapped, dict) else {}
        if isinstance(event, dict) and event.get("stageCompleted") is not None:
            result.append({"path": "bill.stages[].event.stageCompleted", "context": str(event.get("uri", "")), "category": "future_work", "reason": "ELI-DL 3.0 declares no activity-completion boolean predicate"})
    for wrapped in bill.get("sponsors", []):
        sponsor = wrapped.get("sponsor", {}) if isinstance(wrapped, dict) else {}
        role = sponsor.get("as", {}) if isinstance(sponsor, dict) else {}
        if isinstance(role, dict) and role.get("uri"):
            result.append({"path": "bill.sponsors[].sponsor.as.uri", "context": str(role["uri"]), "category": "future_work", "reason": "ministerial role IRI strategy is deferred by the mapping"})
        member = sponsor.get("by", {}) if isinstance(sponsor, dict) else {}
        if isinstance(member, dict) and member.get("showAs") is not None:
            result.append({"path": "bill.sponsors[].sponsor.by.showAs", "context": str(member.get("uri", "")), "category": "ownership_deferred", "reason": "Member descriptions, including labels, are owned by Phase 3 Member graphs"})
    for debate in bill.get("debates", []):
        if isinstance(debate, dict) and isinstance(debate.get("uri"), str):
            result.append({"path": "bill.debates[]", "context": debate["uri"], "category": "future_work", "reason": "Debate RDF is deferred to the authoritative Debates ETL"})
    return sorted(result, key=lambda value: (value["category"], value["path"], value["context"]))


def validate_bill_source(wrapper: dict) -> list[dict]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict):
        raise ValueError("each Legislation result must contain a bill object")
    bill = wrapper["bill"]
    bill_graph_iri(bill)
    datetime_literal(bill.get("lastUpdated"))
    if not isinstance(bill.get("stages"), list) or not bill["stages"]:
        raise ValueError("bill.stages must be a non-empty array")
    prior, by_uri = 0, {}
    for wrapped in bill["stages"]:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("stage wrapper must contain event")
        event = wrapped["event"]
        progress = event.get("progressStage")
        if isinstance(progress, bool) or not isinstance(progress, int) or progress <= prior:
            raise ValueError("stage progressStage values must be strictly increasing")
        prior = progress
        if event.get("uri") in by_uri:
            raise ValueError("duplicate stage URI")
        by_uri[event.get("uri")] = event
        if not isinstance(event.get("dates"), list) or not event["dates"]:
            raise ValueError("event.dates must be a non-empty array")
        for item in event["dates"]:
            date_literal(item.get("date"))
    latest = bill.get("mostRecentStage", {}).get("event") if isinstance(bill.get("mostRecentStage"), dict) else None
    if not isinstance(latest, dict) or latest.get("uri") not in by_uri:
        raise ValueError("mostRecentStage must identify a source stage")
    stage = by_uri[latest["uri"]]
    if stage["progressStage"] != prior:
        raise ValueError("mostRecentStage must identify the highest source stage")
    for key in ("showAs", "progressStage", "stageURI", "stageCompleted", "stageOutcome", "dates"):
        if latest.get(key) != stage.get(key):
            raise ValueError(f"mostRecentStage.{key} does not correspond to its source stage")
    for key in ("chamber", "house"):
        latest_value, stage_value = latest.get(key), stage.get(key)
        if (latest_value is None) != (stage_value is None):
            raise ValueError(f"mostRecentStage.{key} does not correspond to its source stage")
        if latest_value is not None and latest_value.get("uri") != stage_value.get("uri"):
            raise ValueError(f"mostRecentStage.{key} does not correspond to its source stage")
    return extract_bill_omissions(wrapper)


def _forbidden_descriptions(graph: Graph, wrapper: dict, bill: URIRef) -> None:
    """Only Bill lifecycle resources are owned; references never get descriptions."""
    protected = set(graph.objects(bill, URIRef(ELI + "basis_for")))
    protected.update(graph.objects(bill, OIR.originHouse))
    protected.update(graph.objects(None, ELIDL.had_participant_person))
    protected.update(graph.objects(None, ELIDL.parliamentary_term))
    protected.update(graph.objects(None, OIR.inHouse))
    for debate in wrapper["bill"].get("debates", []):
        if isinstance(debate, dict) and debate.get("uri"):
            protected.add(iri(debate["uri"]))
    for resource in protected:
        if list(graph.triples((resource, None, None))):
            raise ValueError(f"Bill graph contains a description of non-owned resource {resource}")


def validate_bill(wrapper: dict, graph: Graph) -> list[dict]:
    omissions = validate_bill_source(wrapper)
    bill = iri(wrapper["bill"]["uri"])
    process = URIRef(f"{bill}#process")
    if (bill, RDF.type, ELIDL.DraftLegislationWork) not in graph or (process, RDF.type, ELIDL.LegislativeProcess) not in graph:
        raise ValueError("Bill and deterministic LegislativeProcess are required")
    latest = list(graph.objects(process, ELIDL.latest_activity))
    if len(latest) != 1 or (latest[0], RDF.type, ELIDL.LegislativeActivity) not in graph:
        raise ValueError("latest_activity must reference exactly one generated LegislativeActivity")
    progress = []
    for stage in graph.subjects(RDF.type, OIR.BillStage):
        if (stage, RDF.type, ELIDL.ProcessStage) in graph or (stage, RDF.type, ELIDL.ActivityType) in graph:
            raise ValueError("stage occurrence must not be a controlled ProcessStage or ActivityType")
        stage_concepts = list(graph.objects(stage, ELIDL.occured_at_stage))
        activity_types = list(graph.objects(stage, ELIDL.had_activity_type))
        if len(stage_concepts) != 1 or len(activity_types) != 1 or stage_concepts[0] != activity_types[0] or stage_concepts[0] not in set(STAGES.values()):
            raise ValueError("stage occurrence must resolve to its controlled ProcessStage and ActivityType")
        values = list(graph.objects(stage, OIR.progressStage))
        if len(values) != 1:
            raise ValueError("stage requires exactly one progressStage")
        progress.append(int(values[0]))
    if len(progress) != len(set(progress)) or sorted(progress) != list(range(1, len(progress) + 1)):
        raise ValueError("stage chronology must be unique and contiguous")
    controlled_stages = set(STAGES.values())
    controlled_activity_types = controlled_stages | set(EVENTS.values()) | set(METHODS.values())
    for activity, stage_concept in graph.subject_objects(ELIDL.occured_at_stage):
        if stage_concept not in controlled_stages:
            raise ValueError("occured_at_stage must target a controlled ProcessStage")
    for activity, activity_type in graph.subject_objects(ELIDL.had_activity_type):
        if activity_type not in controlled_activity_types:
            raise ValueError("had_activity_type must target a controlled ActivityType")
    # Source-correspondence for the deliberately separate Work/Expression/
    # Format/tabling layers; SHACL alone cannot express their source identities.
    for wrapped in wrapper["bill"].get("relatedDocs", []):
        expression = iri(wrapped["relatedDoc"]["uri"]); work = URIRef(f"{expression}#work")
        if (bill, URIRef(ELI + "has_part"), work) not in graph or (work, URIRef(ELI + "is_realized_by"), expression) not in graph:
            raise ValueError("related document Work/Expression realization is required")
        if not list(graph.objects(expression, URIRef(ELI + "is_embodied_by"))):
            raise ValueError("related document Expression formats are required")
    amendments = list(graph.subjects(RDF.type, ELIDL.AmendmentToDraftLegislationWork))
    if len(amendments) != len(wrapper["bill"].get("amendmentLists", [])):
        raise ValueError("every amendment list requires exactly one Work")
    for amendment in amendments:
        expression = URIRef(f"{amendment}#expression")
        if (bill, URIRef(ELI + "has_part"), amendment) not in graph or (amendment, URIRef(ELI + "is_realized_by"), expression) not in graph or not list(graph.objects(expression, URIRef(ELI + "is_embodied_by"))):
            raise ValueError("amendment Work/Expression/Format realization is required")
    tablings = [subject for subject in graph.subjects(ELIDL.occured_at_stage, None) if "#tabling-" in str(subject)]
    if len(tablings) != len(amendments):
        raise ValueError("every amendment Work requires one tabling activity")
    language_values = set(LANGUAGES.values())
    for expression in graph.subjects(URIRef(ELI + "language"), None):
        languages = list(graph.objects(expression, URIRef(ELI + "language")))
        if len(languages) != 1 or not isinstance(languages[0], URIRef) or languages[0] not in language_values:
            raise ValueError("Expression requires exactly one controlled ELI language IRI")
    embodied_formats = set(graph.objects(None, URIRef(ELI + "is_embodied_by")))
    formats = set(graph.subjects(RDF.type, URIRef(ELI + "Format")))
    if embodied_formats != formats:
        raise ValueError("every Expression embodiment must be exactly one typed Format")
    for format_iri in formats:
        schemas = list(graph.objects(format_iri, URIRef(ELI + "uri_schema")))
        media_types = list(graph.objects(format_iri, URIRef(ELI + "media_type")))
        embodiments = list(graph.subjects(URIRef(ELI + "is_embodied_by"), format_iri))
        expected_media_type = MEDIA_TYPES.get(str(format_iri).rsplit("-", 1)[-1])
        if (not isinstance(format_iri, URIRef)
                or len(schemas) != 1 or not isinstance(schemas[0], URIRef)
                or len(media_types) != 1 or not isinstance(media_types[0], URIRef)
                or media_types[0] not in set(MEDIA_TYPES.values())
                or media_types[0] != expected_media_type
                or len(embodiments) != 1):
            raise ValueError("Format requires one IRI uri_schema, controlled IRI media_type, and one Expression embodiment")
    for activity in graph.subjects(RDF.type, ELIDL.LegislativeActivity):
        dates = list(graph.objects(activity, ELIDL.activity_date))
        if (activity, RDF.type, OIR.BillDelivery) not in graph and not dates:
            raise ValueError("legislative event/stage must have an activity date")
    _forbidden_descriptions(graph, wrapper, bill)
    eli_vendor, elidl_vendor = pinned_vocabulary_graphs()
    assert_phase4_vocabulary(graph, eli_vendor, elidl_vendor)
    validate_rdf(graph)
    conforms, _, report = validate(graph, shacl_graph=RESOURCES.joinpath("bills.ttl").read_text(), shacl_graph_format="turtle", inference="none", abort_on_first=False)
    if not conforms:
        raise ValueError("SHACL validation failed:\n" + str(report))
    return omissions
