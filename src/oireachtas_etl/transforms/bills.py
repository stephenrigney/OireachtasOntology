"""Deterministic, Bill-owned legislative lifecycle transformation (Phase 4)."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import quote, unquote, urlsplit

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

from .common import ELIDL, OIR, date_literal, datetime_literal, integer, iri, string

ELI = URIRef("http://data.europa.eu/eli/ontology#")
ELI_NS = "http://data.europa.eu/eli/ontology#"
ELI_TYPE = URIRef(ELI_NS + "type_document")
ELI_TITLE = URIRef(ELI_NS + "title")
ELI_ALT_TITLE = URIRef(ELI_NS + "title_alternative")
ELI_ID = URIRef(ELI_NS + "id_local")
ELI_BASIS = URIRef(ELI_NS + "basis_for")
ELI_HAS_PART = URIRef(ELI_NS + "has_part")
ELI_REALIZED_BY = URIRef(ELI_NS + "is_realized_by")
ELI_EMBODIED_BY = URIRef(ELI_NS + "is_embodied_by")
ELI_URI_SCHEMA = URIRef(ELI_NS + "uri_schema")
ELI_VERSION = URIRef(ELI_NS + "version")
ELI_LANGUAGE = URIRef(ELI_NS + "language")
ELI_DATE = URIRef(ELI_NS + "date_document")
ELI_LEGAL_EXPRESSION = URIRef(ELI_NS + "LegalExpression")
ELI_FORMAT_CLASS = URIRef(ELI_NS + "Format")
ELI_WORK = URIRef(ELI_NS + "Work")
ELI_EXPRESSION_CLASS = URIRef(ELI_NS + "Expression")
ELI_MEDIA_TYPE = URIRef(ELI_NS + "media_type")
LANGUAGES = {
    "eng": URIRef("http://publications.europa.eu/resource/authority/language/ENG"),
    "gle": URIRef("http://publications.europa.eu/resource/authority/language/GLE"),
    "mul": URIRef("http://publications.europa.eu/resource/authority/language/MUL"),
}
MEDIA_TYPES = {
    "pdf": URIRef("https://www.iana.org/assignments/media-types/application/pdf"),
    "xml": URIRef("https://www.iana.org/assignments/media-types/application/xml"),
}

HOUSES = {"dail": URIRef("https://data.oireachtas.ie/house/dail"), "seanad": URIRef("https://data.oireachtas.ie/house/seanad")}
STAGES = {"1": OIR.FirstStage, "2": OIR.SecondStage, "3": OIR.CommitteeStage, "4": OIR.ReportStage, "5": OIR.FifthStage, "enacted": OIR.Enacted}
EVENTS = {"published": OIR.Published, "enacted": OIR.Enacted}
TYPES = {"public": OIR.PublicBill, "private": OIR.PrivateBill}
STATUSES = {"awaiting-signature": OIR.AwaitingSignatureBill, "current": OIR.CurrentBill, "defeated": OIR.DefeatedBill, "draft-heads-of-bill": OIR.DraftHeadsOfBill, "enacted": OIR.EnactedBill, "lapsed": OIR.LapsedBill, "withdrawn": OIR.WithdrawnBill}
METHODS = {"presented": OIR.Presentation, "introduced": OIR.Introduction, "application": OIR.Application}
AMENDMENT_TYPES = {"numberedList": OIR.NumberedAmendmentList, "unnumberedList": OIR.UnnumberedAmendmentList}
VERSIONS = {"initiated": OIR.AsInitiated, "ver_a": OIR.VersionA, "ver_b": OIR.VersionB, "ver_c": OIR.VersionC, "ver_d": OIR.VersionD}


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def source_hash(bill: dict) -> str:
    """Hash the complete source record; API array order is lifecycle order."""
    return hashlib.sha256(_canonical(bill)).hexdigest()


def _source(value: object, label: str) -> URIRef:
    result = iri(value)
    parsed = urlsplit(str(result))
    if parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie" or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ValueError(f"{label} must use canonical Oireachtas HTTPS origin without query or fragment")
    return result


def _path(value: URIRef) -> list[str]:
    return [item for item in urlsplit(str(value)).path.split("/") if item]


def bill_graph_iri(bill: dict) -> str:
    subject = _source(bill.get("uri"), "bill.uri")
    path, year, number = _path(subject), bill.get("billYear"), bill.get("billNo")
    if not isinstance(year, (str, int)) or not isinstance(number, (str, int)) or len(path) != 5 or path[:4] != ["ie", "oireachtas", "bill", str(year)] or unquote(path[4]) != str(number):
        raise ValueError("bill.uri must embed billYear and billNo")
    integer(year)
    return f"https://data.oireachtas.ie/graph/bill/{quote(str(year), safe='')}/{quote(str(number), safe='')}"


def _derived(parent: URIRef, kind: str, source: object) -> URIRef:
    return URIRef(f"{parent}#{kind}-{hashlib.sha256(_canonical(source)).hexdigest()}")


def _def(value: object, table: dict, label: str) -> URIRef:
    value = _source(value, label)
    key = _path(value)[-1]
    if key not in table:
        raise ValueError(f"unsupported {label}: {value}")
    return table[key]


def _house(value: object, label: str) -> URIRef:
    value = _source(value, label)
    code = _path(value)[-1]
    if code not in HOUSES:
        raise ValueError(f"unsupported {label}: {value}")
    return HOUSES[code]


def _term(value: object) -> URIRef:
    term = _source(value, "stage.house.uri")
    path = _path(term)
    if len(path) != 5 or path[:3] != ["ie", "oireachtas", "house"] or path[3] not in HOUSES or not path[4].isdigit() or int(path[4]) < 1:
        raise ValueError("stage.house.uri must be a canonical HouseTerm IRI")
    return term


def _label(graph: Graph, subject: URIRef, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError("showAs must be a non-empty string")
    graph.add((subject, RDFS.label, Literal(value)))


def _language(value: object) -> URIRef:
    if value not in LANGUAGES:
        raise ValueError(f"unsupported ELI language code: {value!r}")
    return LANGUAGES[value]


def _formats(graph: Graph, expression: URIRef, formats: object) -> None:
    if not isinstance(formats, dict):
        raise ValueError("formats must be an object")
    for name in ("pdf", "xml"):
        rendition = formats.get(name)
        if rendition is None:
            continue
        if not isinstance(rendition, dict) or rendition.get("uri") is None:
            raise ValueError(f"formats.{name} must be null or contain uri")
        format_iri = URIRef(f"{expression}#format-{name}")
        graph.add((format_iri, RDF.type, ELI_FORMAT_CLASS))
        graph.add((format_iri, ELI_URI_SCHEMA, _source(rendition["uri"], f"formats.{name}.uri")))
        graph.add((format_iri, ELI_MEDIA_TYPE, MEDIA_TYPES[name]))
        graph.add((expression, ELI_EMBODIED_BY, format_iri))


def _activity(graph: Graph, bill: URIRef, process: URIRef, event: dict, *, stage: bool) -> URIRef:
    subject = _source(event.get("uri"), "stage.uri" if stage else "event.uri")
    graph.add((subject, RDF.type, ELIDL.LegislativeActivity))
    if stage:
        graph.add((subject, RDF.type, OIR.BillStage))
        graph.add((subject, RDF.type, OIR.BillEvent))
        graph.add((subject, OIR.progressStage, Literal(int(event["progressStage"]), datatype=XSD.positiveInteger)))
        stage_concept = _def(event.get("stageURI"), STAGES, "stage.stageURI")
        graph.add((subject, ELIDL.had_activity_type, stage_concept))
        graph.add((subject, ELIDL.occured_at_stage, stage_concept))
        if not isinstance(event.get("stageCompleted"), bool):
            raise ValueError("stageCompleted must be boolean")
        if event.get("house") is not None:
            graph.add((subject, ELIDL.parliamentary_term, _term(event["house"].get("uri"))))
    else:
        graph.add((subject, RDF.type, OIR.BillEvent))
        graph.add((subject, ELIDL.had_activity_type, _def(event.get("eventURI"), EVENTS, "event.eventURI")))
    _label(graph, subject, event.get("showAs"))
    chamber = event.get("chamber")
    if chamber is not None:
        if not isinstance(chamber, dict):
            raise ValueError("event.chamber must be an object or null")
        graph.add((subject, OIR.inHouse, _house(chamber.get("uri"), "event.chamber.uri")))
    dates = event.get("dates")
    if not isinstance(dates, list) or not dates:
        raise ValueError("event.dates must be a non-empty array")
    for item in dates:
        if not isinstance(item, dict):
            raise ValueError("event date must be an object")
        graph.add((subject, ELIDL.activity_date, date_literal(item.get("date"))))
    graph.add((subject, ELIDL.forms_part_of, process))
    return subject


def transform_bill_with_report(wrapper: dict) -> tuple[Graph, list[dict]]:
    if not isinstance(wrapper, dict) or not isinstance(wrapper.get("bill"), dict):
        raise ValueError("each Legislation result must contain a bill object")
    data = wrapper["bill"]
    bill = _source(data.get("uri"), "bill.uri")
    graph_iri = bill_graph_iri(data)  # validates identity invariant
    graph, omissions = Graph(), []
    graph.bind("oir", OIR); graph.bind("eli", ELI_NS); graph.bind("eli-dl", ELIDL)
    graph.add((bill, RDF.type, ELIDL.DraftLegislationWork)); graph.add((bill, RDF.type, URIRef(ELI_NS + "LegalResource")))
    graph.add((bill, ELI_TYPE, OIR.Bill))
    graph.add((bill, OIR.legislativeYear, integer(data.get("billYear")))); graph.add((bill, ELI_ID, string(f"{data['billYear']}/{data['billNo']}")))
    for field, predicate, lang in (("shortTitleEn", ELI_TITLE, "en"), ("shortTitleGa", ELI_TITLE, "ga"), ("longTitleEn", ELI_ALT_TITLE, "en"), ("longTitleGa", ELI_ALT_TITLE, "ga")):
        if data.get(field) is not None:
            graph.add((bill, predicate, Literal(data[field], lang=lang)))
    graph.add((bill, OIR.originHouse, _house(data.get("originHouseURI"), "originHouseURI")))
    graph.add((bill, DCTERMS.modified, datetime_literal(data.get("lastUpdated"))))
    process = URIRef(f"{bill}#process")
    graph.add((process, RDF.type, ELIDL.LegislativeProcess)); graph.add((process, ELIDL.process_number, string(str(data.get("billNo")))))
    graph.add((process, ELIDL.process_type, _def(data.get("billTypeURI"), TYPES, "billTypeURI")))
    graph.add((process, ELIDL.process_status, _def(data.get("statusURI"), STATUSES, "statusURI")))
    graph.add((process, ELIDL.was_submitted_by, _source(data.get("sourceURI"), "sourceURI")))
    delivery = _derived(bill, "delivery", {"methodURI": data.get("methodURI")})
    graph.add((delivery, RDF.type, ELIDL.LegislativeActivity)); graph.add((delivery, RDF.type, OIR.BillDelivery)); graph.add((delivery, ELIDL.forms_part_of, process)); graph.add((delivery, ELIDL.had_activity_type, _def(data.get("methodURI"), METHODS, "methodURI")))
    stages = data.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("bill.stages must be a non-empty array")
    stage_by_uri, stage_by_house_number = {}, {}
    for wrapped in stages:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("stage wrapper must contain event")
        event = wrapped["event"]; activity = _activity(graph, bill, process, event, stage=True)
        stage_by_uri[str(activity)] = activity
        stage_path = _path(activity)
        if len(stage_path) >= 2:
            stage_by_house_number[(stage_path[-2], stage_path[-1])] = activity
    latest = data.get("mostRecentStage", {}).get("event") if isinstance(data.get("mostRecentStage"), dict) else None
    if not isinstance(latest, dict):
        raise ValueError("mostRecentStage.event is required")
    latest_iri = _source(latest.get("uri"), "mostRecentStage.event.uri")
    if str(latest_iri) not in stage_by_uri:
        raise ValueError("mostRecentStage must reference a generated stage")
    graph.add((process, ELIDL.latest_activity, latest_iri))
    for wrapped in data.get("events", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("event wrapper must contain event")
        _activity(graph, bill, process, wrapped["event"], stage=False)
    for wrapped in data.get("amendmentLists", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("amendmentList"), dict):
            raise ValueError("amendment list wrapper must contain amendmentList")
        item = wrapped["amendmentList"]
        amendment_identity = {"stage": item.get("stage", {}).get("uri"), "stageNo": item.get("stageNo"), "date": item.get("date"), "chamber": item.get("chamber", {}).get("uri"), "type": item.get("amendmentTypeUri", {}).get("uri")}
        amendment = _derived(bill, "amendment-list", amendment_identity)
        expression = URIRef(f"{amendment}#expression")
        graph.add((amendment, RDF.type, ELIDL.AmendmentToDraftLegislationWork)); graph.add((bill, ELI_HAS_PART, amendment))
        _label(graph, amendment, item.get("showAs"))
        graph.add((amendment, OIR.stageNo, Literal(int(item.get("stageNo")), datatype=XSD.positiveInteger)))
        graph.add((amendment, OIR.hasAmendmentListType, _def(item.get("amendmentTypeUri", {}).get("uri"), AMENDMENT_TYPES, "amendmentList.amendmentTypeUri.uri")))
        graph.add((amendment, ELI_REALIZED_BY, expression)); graph.add((expression, RDF.type, ELI_EXPRESSION_CLASS)); _formats(graph, expression, item.get("formats"))
        stage_reference = _source(item.get("stage", {}).get("uri"), "amendmentList.stage.uri")
        stage_path = _path(stage_reference)
        stage = stage_by_uri.get(str(stage_reference))
        # The API's amendment endpoint uses .../bill/{year}/{no}/{house}/{no}
        # while stages use .../bill/{year}/{no}/stage/{house}/{no}; both name
        # the same activity. Normalise the former to the owned stage IRI.
        if stage is None and len(stage_path) >= 2:
            stage = stage_by_house_number.get((stage_path[-2], stage_path[-1]))
        if stage is None:
            raise ValueError("amendment list must refer to a Bill stage")
        tabling = _derived(amendment, "tabling", amendment_identity)
        graph.add((tabling, RDF.type, ELIDL.LegislativeActivity)); graph.add((tabling, ELIDL.forms_part_of, process))
        graph.add((tabling, ELIDL.activity_date, date_literal(item.get("date"))))
        graph.add((tabling, OIR.inHouse, _house(item.get("chamber", {}).get("uri"), "amendmentList.chamber.uri")))
        stage_concepts = list(graph.objects(stage, ELIDL.occured_at_stage))
        if len(stage_concepts) != 1:
            raise ValueError("amendment stage must resolve to exactly one controlled ProcessStage")
        graph.add((tabling, ELIDL.occured_at_stage, stage_concepts[0]))
    for wrapped in data.get("relatedDocs", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("relatedDoc"), dict):
            raise ValueError("related document wrapper must contain relatedDoc")
        item = wrapped["relatedDoc"]; document = _source(item.get("uri"), "relatedDoc.uri"); work = URIRef(f"{document}#work")
        doc_types = {"errata": OIR.Errata, "gluais": OIR.Gluais, "memo": OIR.ExplanatoryMemo}
        if item.get("docType") not in doc_types:
            _unsupported_doc_type(item.get("docType"))
        graph.add((work, RDF.type, ELI_WORK)); graph.add((work, ELI_TYPE, doc_types[item["docType"]]))
        graph.add((bill, ELI_HAS_PART, work)); graph.add((work, ELI_REALIZED_BY, document)); graph.add((document, RDF.type, ELI_LEGAL_EXPRESSION))
        _label(graph, document, item.get("showAs")); graph.add((document, ELI_DATE, date_literal(item.get("date")))); graph.add((document, ELI_LANGUAGE, _language(item.get("lang")))); _formats(graph, document, item.get("formats"))
    for wrapped in data.get("versions", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("version"), dict):
            raise ValueError("version wrapper must contain version")
        item = wrapped["version"]
        if item.get("docType") == "act":
            omissions.append({"path": "bill.versions[].version", "context": str(item.get("uri", "")), "category": "ownership_deferred", "reason": "Act descriptions and expressions are owned by a later Acts ETL"}); continue
        if item.get("docType") != "bill":
            raise ValueError("unsupported version docType")
        expression = _source(item.get("uri"), "version.uri"); parts = _path(expression)
        version_key = parts[-1]
        if version_key not in VERSIONS:
            _unsupported_version(version_key)
        graph.add((expression, RDF.type, ELI_LEGAL_EXPRESSION)); graph.add((bill, ELI_REALIZED_BY, expression)); graph.add((expression, ELI_VERSION, VERSIONS[version_key]))
        _label(graph, expression, item.get("showAs")); graph.add((expression, ELI_DATE, date_literal(item.get("date")))); graph.add((expression, ELI_LANGUAGE, _language(item.get("lang")))); _formats(graph, expression, item.get("formats"))
    act = data.get("act")
    if isinstance(act, dict) and act.get("uri") is not None:
        graph.add((bill, ELI_BASIS, _source(act["uri"], "act.uri")))
        omissions.append({"path": "bill.act.*", "context": str(act["uri"]), "category": "ownership_deferred", "reason": "Act descriptions are owned by a later Acts ETL; Bill graph retains only eli:basis_for"})
    for wrapped in data.get("sponsors", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("sponsor"), dict):
            raise ValueError("sponsor wrapper must contain sponsor")
        sponsor = wrapped["sponsor"]
        sponsor_identity = {"member": sponsor.get("by", {}).get("uri"), "role": sponsor.get("as", {}).get("uri") or sponsor.get("as", {}).get("showAs"), "primary": sponsor.get("isPrimary")}
        participation = _derived(process, "sponsor", sponsor_identity)
        graph.add((participation, RDF.type, ELIDL.Participation)); graph.add((process, ELIDL.had_participation, participation))
        if sponsor.get("by", {}).get("uri") is not None:
            graph.add((participation, ELIDL.had_participant_person, _source(sponsor["by"]["uri"], "sponsor.by.uri")))
        if sponsor.get("by", {}).get("showAs") is not None:
            omissions.append({"path": "bill.sponsors[].sponsor.by.showAs", "context": str(sponsor.get("by", {}).get("uri", "")), "category": "ownership_deferred", "reason": "Member descriptions, including labels, are owned by Phase 3 Member graphs"})
        if not isinstance(sponsor.get("isPrimary"), bool):
            raise ValueError("sponsor.isPrimary must be boolean")
        graph.add((participation, OIR.isPrimarySponsor, Literal(sponsor["isPrimary"], datatype=XSD.boolean)))
        if sponsor.get("as", {}).get("showAs") is not None:
            _label(graph, participation, sponsor["as"]["showAs"])
        if sponsor.get("as", {}).get("uri") is not None:
            omissions.append({"path": "bill.sponsors[].sponsor.as.uri", "context": str(sponsor["as"]["uri"]), "category": "future_work", "reason": "ministerial role IRI strategy is deferred by the mapping"})
    for debate in data.get("debates", []):
        if isinstance(debate, dict) and isinstance(debate.get("uri"), str):
            omissions.append({"path": "bill.debates[]", "context": debate["uri"], "category": "future_work", "reason": "Debate RDF is deferred to the authoritative Debates ETL"})
    for wrapped in stages:
        event = wrapped["event"]
        if event.get("stageCompleted") is not None:
            omissions.append({"path": "bill.stages[].event.stageCompleted", "context": str(event["uri"]), "category": "future_work", "reason": "ELI-DL 3.0 declares no activity-completion boolean predicate"})
    return graph, sorted(omissions, key=lambda value: (value["category"], value["path"], value["context"]))


def _unsupported_version(value: str) -> URIRef:
    raise ValueError(f"unsupported bill version: {value!r}")


def _unsupported_doc_type(value: object) -> URIRef:
    raise ValueError(f"unsupported related document type: {value!r}")


def transform_bill(wrapper: dict) -> Graph:
    return transform_bill_with_report(wrapper)[0]
