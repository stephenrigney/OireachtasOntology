"""Fail-closed validation for one Bill-owned lifecycle graph."""
from __future__ import annotations

from collections import defaultdict
from importlib.resources import files
from urllib.parse import urlsplit

from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from ..transforms.bills import (EVENTS, LANGUAGES, MEDIA_TYPES, METHODS, STAGES,
                                STATUSES, VERSIONS, _amendment_list_records,
                                _bill_event_omission,
                                _bill_event_identity, _bill_event_records,
                                _bill_version_expression_identity, _derived,
                                _def, _format_identity, _house, _language,
                                _related_document_identity,
                                _reviewed_unemitted_amendment_stage,
                                _resolve_amendment_stage,
                                _stage_reference_maps,
                                _unresolved_amendment_stage_omission,
                                bill_event_type, bill_graph_iri,
                                bill_stage_type)
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
        if isinstance(sponsor, dict) and sponsor.get("isPrimary") is None:
            member = sponsor.get("by") if isinstance(sponsor.get("by"), dict) else {}
            result.append({"path": "bill.sponsors[].sponsor.isPrimary",
                           "context": str(member.get("uri", "")),
                           "category": "source_unknown",
                           "reason": "Primary-sponsor flag is null in source; Participation is retained without isPrimarySponsor"})
        role = sponsor.get("as", {}) if isinstance(sponsor, dict) else {}
        if isinstance(role, dict) and role.get("uri"):
            result.append({"path": "bill.sponsors[].sponsor.as.uri", "context": str(role["uri"]), "category": "future_work", "reason": "ministerial role IRI strategy is deferred by the mapping"})
        member = sponsor.get("by", {}) if isinstance(sponsor, dict) else {}
        if isinstance(member, dict) and member.get("showAs") is not None:
            result.append({"path": "bill.sponsors[].sponsor.by.showAs", "context": str(member.get("uri", "")), "category": "ownership_deferred", "reason": "Member descriptions, including labels, are owned by Phase 3 Member graphs"})
    for debate in bill.get("debates", []):
        if isinstance(debate, dict) and isinstance(debate.get("uri"), str):
            result.append({"path": "bill.debates[]", "context": debate["uri"], "category": "future_work", "reason": "Debate RDF is deferred to the authoritative Debates ETL"})
    events = bill.get("events", [])
    if not isinstance(events, list):
        raise ValueError("bill.events must be an array")
    bill_iri = iri(bill["uri"])
    for wrapped in events:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("event wrapper must contain event")
        event = wrapped["event"]
        if bill_event_type(event.get("eventURI")) is None:
            result.append(_bill_event_omission(event, bill_iri))
    _bill_event_records(events)
    related_work_types = {}
    related_docs = bill.get("relatedDocs", [])
    if not isinstance(related_docs, list):
        raise ValueError("bill.relatedDocs must be an array")
    for wrapped in related_docs:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("relatedDoc"), dict):
            raise ValueError("related document wrapper must contain relatedDoc")
        _source_uri, work, _expression, doc_type = _related_document_identity(
            wrapped["relatedDoc"])
        if work in related_work_types and related_work_types[work] != doc_type:
            raise ValueError(
                "related-document Work identity has conflicting controlled types")
        related_work_types[work] = doc_type
    exact_stages, stage_aliases = _stage_reference_maps(bill.get("stages"))
    for item, stage_reference, identity in _amendment_list_records(
            bill.get("amendmentLists", []), bill_iri):
        if (_resolve_amendment_stage(stage_reference, exact_stages,
                                     stage_aliases) is None
                and _reviewed_unemitted_amendment_stage(stage_reference) is None):
            amendment = _derived(bill_iri, "amendment-list", identity)
            result.append(_unresolved_amendment_stage_omission(
                stage_reference, amendment, bill_iri))
    return sorted(result, key=lambda value: (
        value["category"], value["path"], value.get("context", ""),
        value.get("source_event_uri", ""),
        value.get("source_stage_uri", "")))


def known_bill_source_quarantines(wrapper: dict) -> list[dict]:
    """Identify only the specifically reviewed malformed Bill source records."""
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict):
        return []
    bill = wrapper["bill"]
    identity = f"{bill.get('billYear')}/{bill.get('billNo')}"
    bill_uri = str(bill.get("uri", ""))
    diagnostics = []
    if identity == "2024/48" and isinstance(bill.get("stages"), list):
        for stage_index, wrapped in enumerate(bill["stages"]):
            event = wrapped.get("event") if isinstance(wrapped, dict) else None
            if (not isinstance(event, dict)
                    or event.get("stageURI") !=
                    "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/None"
                    or event.get("uri") != f"{bill_uri}/stage/seanad/None"):
                continue
            diagnostics.append({
                "category": "source_quarantine",
                "bill_identity": identity,
                "bill_uri": bill_uri,
                "path": f"bill.stages[{stage_index}].event.stageURI",
                "context": str(event.get("uri")),
                "reason": "Source stage definition is bill-stage/None and its occurrence route ends /stage/seanad/None; no stage is inferred from showAs",
            })
    missing_date_bills = {"1959/P3", "1965/P1", "1965/P3"}
    if identity in missing_date_bills and isinstance(bill.get("stages"), list):
        for stage_index, wrapped in enumerate(bill["stages"]):
            event = wrapped.get("event") if isinstance(wrapped, dict) else None
            dates = event.get("dates") if isinstance(event, dict) else None
            if not isinstance(dates, list):
                continue
            for date_index, item in enumerate(dates):
                if isinstance(item, dict) and item.get("date") is None:
                    diagnostics.append({
                        "category": "source_quarantine",
                        "bill_identity": identity,
                        "bill_uri": bill_uri,
                        "path": f"bill.stages[{stage_index}].event.dates[{date_index}].date",
                        "context": str(event.get("uri", "")),
                        "reason": "Required lifecycle stage date is null in source; no date is inferred",
                    })
    return diagnostics


def validate_bill_source(wrapper: dict) -> list[dict]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict):
        raise ValueError("each Legislation result must contain a bill object")
    bill = wrapper["bill"]
    bill_graph_iri(bill)
    _def(bill.get("methodURI"), METHODS, "methodURI")
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
    delivery = _derived(bill, "delivery", {
        "methodURI": wrapper["bill"].get("methodURI")})
    expected_method = _def(wrapper["bill"].get("methodURI"), METHODS,
                           "methodURI")
    if (set(graph.subjects(RDF.type, OIR.BillDelivery)) != {delivery}
            or (delivery, RDF.type, ELIDL.LegislativeActivity) not in graph
            or list(graph.objects(delivery, ELIDL.had_activity_type)) != [expected_method]
            or list(graph.objects(delivery, ELIDL.forms_part_of)) != [process]
            or set(graph.subject_objects(ELIDL.created_a_realization_of))
               != {(delivery, bill)}):
        raise ValueError(
            "Bill delivery must preserve its deterministic source identity and method, create its Bill Work and belong to its process")
    expected_status = _def(wrapper["bill"].get("statusURI"), STATUSES,
                           "statusURI")
    if list(graph.objects(process, ELIDL.process_status)) != [expected_status]:
        raise ValueError("Bill LegislativeProcess must use its source controlled status")
    latest = list(graph.objects(process, ELIDL.latest_activity))
    if len(latest) != 1 or (latest[0], RDF.type, ELIDL.LegislativeActivity) not in graph:
        raise ValueError("latest_activity must reference exactly one generated LegislativeActivity")
    progress = []
    source_stages = {}
    for wrapped in wrapper["bill"]["stages"]:
        event = wrapped["event"]
        source_stages[iri(event.get("uri"))] = bill_stage_type(
            event.get("stageURI"))
    stage_occurrences = set(graph.subjects(RDF.type, OIR.BillStage))
    if stage_occurrences != set(source_stages):
        raise ValueError("Bill-stage RDF occurrences must match source stage identities")
    for stage in stage_occurrences:
        if (stage, RDF.type, ELIDL.ProcessStage) in graph or (stage, RDF.type, ELIDL.ActivityType) in graph:
            raise ValueError("stage occurrence must not be a controlled ProcessStage or ActivityType")
        stage_concepts = list(graph.objects(stage, ELIDL.occured_at_stage))
        activity_types = list(graph.objects(stage, ELIDL.had_activity_type))
        expected_stage = source_stages[stage]
        if (len(stage_concepts) != 1 or len(activity_types) != 1
                or stage_concepts[0] != expected_stage
                or activity_types[0] != expected_stage):
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
    # Supported Bill event source URIs are keys, not necessarily their emitted
    # occurrence IRIs. Repeated rows with one complete identity collapse; the
    # identity helper rejects conflicting remaining mapped semantics.
    supported_occurrences = set()
    source_events = wrapper["bill"].get("events", [])
    if not isinstance(source_events, list):
        raise ValueError("bill.events must be an array")
    for wrapped in source_events:
        event = wrapped["event"]
        event_type = bill_event_type(event.get("eventURI"))
        occurrence_value = event.get("uri")
        occurrence = iri(occurrence_value) if occurrence_value is not None else None
        if event_type is None:
            if occurrence is not None and (
                    any(graph.triples((occurrence, None, None)))
                    or any(graph.triples((None, None, occurrence)))):
                raise ValueError("intentionally unmodelled Bill event occurrence must not appear in RDF")
            continue
    for event in _bill_event_records(source_events):
        occurrence, _identity = _bill_event_identity(event)
        event_type = bill_event_type(event.get("eventURI"))
        supported_occurrences.add(occurrence)
        activity_types = list(graph.objects(occurrence, ELIDL.had_activity_type))
        memberships = list(graph.objects(occurrence, ELIDL.forms_part_of))
        dates = event.get("dates")
        expected_dates = {date_literal(item.get("date")) for item in dates}
        actual_dates = set(graph.objects(occurrence, ELIDL.activity_date))
        labels = list(graph.objects(occurrence, RDFS.label))
        if ((occurrence, RDF.type, ELIDL.LegislativeActivity) not in graph
                or (occurrence, RDF.type, OIR.BillEvent) not in graph
                or activity_types != [event_type]
                or memberships != [process]
                or actual_dates != expected_dates
                or labels != [Literal(event.get("showAs"))]):
            raise ValueError(
                "Bill event occurrence must preserve its derived identity, controlled type, dates, label and process membership")
        chamber = event.get("chamber")
        expected_houses = [] if chamber is None else [
            _house(chamber.get("uri"), "event.chamber.uri")]
        if list(graph.objects(occurrence, OIR.inHouse)) != expected_houses:
            raise ValueError("Bill event occurrence must preserve its derived source chamber")
    stage_occurrences = set(graph.subjects(RDF.type, OIR.BillStage))
    emitted_event_occurrences = set(graph.subjects(RDF.type, OIR.BillEvent)) - stage_occurrences
    if emitted_event_occurrences != supported_occurrences:
        raise ValueError("Bill-event RDF occurrences must match supported source event identities")
    # A related-document source URI identifies a Bill-owned Work. Expression
    # identities are source-semantic and renditions are accumulated as Formats.
    related_work_types: dict[URIRef, URIRef] = {}
    related_by_work: dict[URIRef, set[URIRef]] = defaultdict(set)
    related_by_expression: dict[URIRef, list[dict]] = defaultdict(list)
    related_expression_type = URIRef(ELI + "LegalExpression")
    related_work_type = URIRef(ELI + "Work")
    has_part = URIRef(ELI + "has_part")
    realized_by = URIRef(ELI + "is_realized_by")
    for wrapped in wrapper["bill"].get("relatedDocs", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("relatedDoc"), dict):
            raise ValueError("related document wrapper must contain relatedDoc")
        item = wrapped["relatedDoc"]
        _source_uri, work, expression, doc_type = _related_document_identity(item)
        prior_type = related_work_types.setdefault(work, doc_type)
        if prior_type != doc_type:
            raise ValueError(
                "related-document Work identity has conflicting controlled types")
        related_by_work[work].add(expression)
        related_by_expression[expression].append(item)
    actual_related_works = set(graph.subjects(RDF.type, related_work_type))
    if actual_related_works != set(related_work_types):
        raise ValueError("related-document Works must match their source identities")
    for work, doc_type in related_work_types.items():
        actual_types = list(graph.objects(work, URIRef(ELI + "type_document")))
        actual_expressions = set(graph.objects(work, realized_by))
        if ((bill, has_part, work) not in graph
                or actual_types != [doc_type]
                or actual_expressions != related_by_work[work]):
            raise ValueError(
                "related-document Work must preserve its source identity and controlled type")
    for expression, items in related_by_expression.items():
        dates = list(graph.objects(expression, URIRef(ELI + "date_document")))
        languages = list(graph.objects(expression, URIRef(ELI + "language")))
        labels = list(graph.objects(expression, RDFS.label))
        expected_formats = set()
        for item in items:
            formats_value = item.get("formats")
            if not isinstance(formats_value, dict):
                raise ValueError("formats must be an object")
            for name in ("pdf", "xml"):
                rendition = formats_value.get(name)
                if rendition is None:
                    continue
                if not isinstance(rendition, dict) or rendition.get("uri") is None:
                    raise ValueError(f"formats.{name} must be null or contain uri")
                rendition_uri = iri(rendition["uri"])
                expected_formats.add(_format_identity(
                    expression, MEDIA_TYPES[name], rendition_uri))
        if ((expression, RDF.type, related_expression_type) not in graph
                or dates != [date_literal(items[0].get("date"))]
                or languages != [_language(items[0].get("lang"))]
                or labels != [Literal(items[0].get("showAs"))]
                or not expected_formats
                or set(graph.objects(expression, URIRef(ELI + "is_embodied_by")))
                   != expected_formats):
            raise ValueError(
                "related-document Expression must preserve source semantics and renditions")
    sponsor_occurrences = set()
    for wrapped in wrapper["bill"].get("sponsors", []):
        sponsor = wrapped.get("sponsor", {}) if isinstance(wrapped, dict) else {}
        if not isinstance(sponsor, dict):
            raise ValueError("sponsor wrapper must contain sponsor")
        member = sponsor.get("by") if isinstance(sponsor.get("by"), dict) else {}
        role = sponsor.get("as") if isinstance(sponsor.get("as"), dict) else {}
        sponsor_identity = {
            "member": member.get("uri"),
            "role": role.get("uri") or role.get("showAs"),
            "primary": sponsor.get("isPrimary"),
        }
        participation = _derived(process, "sponsor", sponsor_identity)
        sponsor_occurrences.add(participation)
        primary = sponsor.get("isPrimary")
        if primary is not None and not isinstance(primary, bool):
            raise ValueError("sponsor.isPrimary must be boolean or null")
        expected_primary = ([] if primary is None else [
            Literal(primary, datatype=XSD.boolean)])
        if list(graph.objects(participation, OIR.isPrimarySponsor)) != expected_primary:
            raise ValueError(
                "Participation primary-sponsor flag must be zero-or-one and preserve nullable source value")
    actual_sponsors = set(graph.subjects(RDF.type, ELIDL.Participation))
    if actual_sponsors != sponsor_occurrences:
        raise ValueError("Bill sponsor Participations must match source identities")
    exact_stages, stage_aliases = _stage_reference_maps(wrapper["bill"]["stages"])
    expected_amendments = set()
    expected_expressions = {}
    expected_tablings = {}
    for item, stage_reference, identity in _amendment_list_records(
            wrapper["bill"].get("amendmentLists", []), bill):
        amendment = _derived(bill, "amendment-list", identity)
        expected_expressions[amendment] = _derived(
            amendment, "expression", identity)
        tabling = _derived(amendment, "tabling", identity)
        expected_amendments.add(amendment)
        expected_tablings[tabling] = (item, stage_reference)
    amendments = set(graph.subjects(RDF.type, ELIDL.AmendmentToDraftLegislationWork))
    if amendments != expected_amendments:
        raise ValueError("amendment-list Works must match their deterministic source identities")
    for amendment in expected_amendments:
        expression = expected_expressions[amendment]
        if (bill, URIRef(ELI + "has_part"), amendment) not in graph or (amendment, URIRef(ELI + "is_realized_by"), expression) not in graph or not list(graph.objects(expression, URIRef(ELI + "is_embodied_by"))):
            raise ValueError("amendment Work/Expression/Format realization is required")
    tablings = {subject for subject in graph.subjects(RDF.type, ELIDL.LegislativeActivity)
                if "%23tabling-" in str(subject)}
    if tablings != set(expected_tablings):
        raise ValueError("amendment tabling activities must match their deterministic source identities")
    for tabling, (item, stage_reference) in expected_tablings.items():
        dates = list(graph.objects(tabling, ELIDL.activity_date))
        houses = list(graph.objects(tabling, OIR.inHouse))
        memberships = list(graph.objects(tabling, ELIDL.forms_part_of))
        if ((tabling, RDF.type, ELIDL.LegislativeActivity) not in graph
                or dates != [date_literal(item.get("date"))]
                or houses != [_house(item["chamber"].get("uri"),
                                     "amendmentList.chamber.uri")]
                or memberships != [process]):
            raise ValueError("amendment tabling activity must preserve its source date, chamber and process")
        resolved_stage = _resolve_amendment_stage(
            stage_reference, exact_stages, stage_aliases)
        stage_concepts = ([] if resolved_stage is None else list(
            graph.objects(resolved_stage, ELIDL.occured_at_stage)))
        tabling_stages = list(graph.objects(tabling, ELIDL.occured_at_stage))
        if resolved_stage is None:
            reviewed_stage = _reviewed_unemitted_amendment_stage(
                stage_reference)
            if reviewed_stage is None:
                if tabling_stages:
                    raise ValueError("unresolved amendment stage reference must not emit occured_at_stage")
            elif tabling_stages != [reviewed_stage]:
                raise ValueError("unemitted stage-6 tabling must reference CreamListStage")
        elif (len(stage_concepts) != 1
              or stage_concepts[0] not in set(STAGES.values())
              or tabling_stages != stage_concepts):
            raise ValueError("resolved amendment tabling must reference its stage's single controlled ProcessStage")
    expected_bill_versions = {}
    for wrapped in wrapper["bill"].get("versions", []):
        item = wrapped.get("version", {}) if isinstance(wrapped, dict) else {}
        if not isinstance(item, dict) or item.get("docType") != "bill":
            continue
        _source_version_uri, version_key, expression = \
            _bill_version_expression_identity(item, bill)
        if expression not in expected_bill_versions:
            expected_bill_versions[expression] = ([], version_key)
        expected_bill_versions[expression][0].append(item)
    actual_bill_versions = set(graph.subjects(URIRef(ELI + "version"), None))
    if actual_bill_versions != set(expected_bill_versions):
        raise ValueError(
            "Bill-version Expressions must match deterministic source-semantic identities")
    for expression, (items, version_key) in expected_bill_versions.items():
        versions = list(graph.objects(expression, URIRef(ELI + "version")))
        dates = list(graph.objects(expression, URIRef(ELI + "date_document")))
        languages = list(graph.objects(expression, URIRef(ELI + "language")))
        labels = list(graph.objects(expression, URIRef("http://www.w3.org/2000/01/rdf-schema#label")))
        expected_dates = {date_literal(item.get("date")) for item in items}
        expected_languages = {_language(item.get("lang")) for item in items}
        expected_labels = {Literal(item.get("showAs")) for item in items}
        if ((expression, RDF.type, URIRef(ELI + "LegalExpression")) not in graph
                or (bill, URIRef(ELI + "is_realized_by"), expression) not in graph
                or versions != [VERSIONS[version_key]]
                or len(expected_dates) != 1 or set(dates) != expected_dates
                or len(expected_languages) != 1 or set(languages) != expected_languages
                or len(expected_labels) != 1 or set(labels) != expected_labels):
            raise ValueError(
                "Bill-version Expression must preserve its source semantics and Bill realization")
        expected_formats = set()
        for item in items:
            formats = item.get("formats")
            if not isinstance(formats, dict):
                raise ValueError("formats must be an object")
            for name in ("pdf", "xml"):
                rendition = formats.get(name)
                if rendition is None:
                    continue
                if not isinstance(rendition, dict) or rendition.get("uri") is None:
                    raise ValueError(f"formats.{name} must be null or contain uri")
                rendition_uri = iri(rendition["uri"])
                expected_formats.add(_format_identity(
                    expression, MEDIA_TYPES[name], rendition_uri))
        if set(graph.objects(expression, URIRef(ELI + "is_embodied_by"))) != \
                expected_formats:
            raise ValueError(
                "Bill-version Expression Formats must match its source renditions")
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
        if (not isinstance(format_iri, URIRef)
                or len(schemas) != 1 or not isinstance(schemas[0], URIRef)
                or len(media_types) != 1 or not isinstance(media_types[0], URIRef)
                or media_types[0] not in set(MEDIA_TYPES.values())
                or len(embodiments) != 1):
            raise ValueError("Format requires one IRI uri_schema, controlled IRI media_type, and one Expression embodiment")
        if format_iri != _format_identity(embodiments[0], media_types[0], schemas[0]):
            raise ValueError(
                "Format identity must be derived from Expression, media type and rendition URI")
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
