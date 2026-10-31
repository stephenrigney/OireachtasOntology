"""Deterministic, Bill-owned legislative lifecycle transformation (Phase 4)."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import quote, unquote, urlsplit

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, XSD

from .common import ELIDL, OIR, date_literal, datetime_literal, integer, iri, string

BILLS_PUBLICATION_CONTRACT = 2

ELI = URIRef("http://data.europa.eu/eli/ontology#")
ELI_NS = "http://data.europa.eu/eli/ontology#"
ELI_TYPE = URIRef(ELI_NS + "type_document")
ELI_WORK_TYPE = URIRef(ELI_NS + "work_type")
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
BILL_STAGE_URI_PREFIX = "https://data.oireachtas.ie/ie/oireachtas/def/bill-stage/"
STAGES = {
    "1": OIR.FirstStage,
    "2": OIR.SecondStage,
    "3": OIR.CommitteeStage,
    "4": OIR.ReportStage,
    "5": OIR.FifthStage,
    "6": OIR.CreamListStage,
    "enacted": OIR.Enacted,
    "referral-to-supreme-court": OIR.ReferralToSupremeCourtArt26,
    "referendum": OIR.Referendum,
}
EVENT_URI_PREFIX = "https://data.oireachtas.ie/ie/oireachtas/def/bill-event/"
EVENTS = {
    "published": OIR.Published,
    "enacted": OIR.Enacted,
    "bill-defeated": OIR.BillDefeatedEvent,
    "bill-lapsed": OIR.BillLapsedEvent,
    "bill-restored": OIR.RestoreBill,
    "bill-withdrawn": OIR.BillWithdrawnEvent,
    "recommittal": OIR.RecommitBill,
    "referendum": OIR.Referendum,
    "referral-to-supreme-court-art-26": OIR.ReferralToSupremeCourtArt26,
}
INTENTIONALLY_UNMODELLED_EVENTS = frozenset({
    "admissibility-for-introduction",
    "approved-for-initiation",
    "other-procedural-event",
})
TYPES = {
    "public": OIR.PublicBill,
    "private": OIR.PrivateBill,
    "hybrid": OIR.HybridBill,
}
STATUSES = {
    "awaiting-signature": OIR.AwaitingSignatureBill,
    "current": OIR.CurrentBill,
    "published": OIR.CurrentBill,
    "defeated": OIR.DefeatedBill,
    "declared-repugnant-to-constitution": OIR.DeclaredRepugnantToConstitutionBill,
    "draft-heads-of-bill": OIR.DraftHeadsOfBill,
    "enacted": OIR.EnactedBill,
    "lapsed": OIR.LapsedBill,
    "withdrawn": OIR.WithdrawnBill,
    "rejected-at-referendum": OIR.RejectedAtReferendumBill,
}
METHODS = {
    "presented": OIR.Presentation,
    "introduced": OIR.Introduction,
    "application": OIR.Application,
    "by-application": OIR.Application,
}
AMENDMENT_TYPES = {
    "numberedList": OIR.NumberedAmendmentList,
    "unnumberedList": OIR.UnnumberedAmendmentList,
    "creamList": OIR.CreamList,
}
VERSIONS = {
    "initiated": OIR.AsInitiated,
    "ver_a": OIR.VersionA,
    "ver_b": OIR.VersionB,
    "ver_c": OIR.VersionC,
    "ver_d": OIR.VersionD,
    "ver_e": OIR.VersionE,
}
RELATED_DOCUMENT_TYPES = {
    "digest": OIR.BillDigest,
    "errata": OIR.Errata,
    "gluais": OIR.Gluais,
    "memo": OIR.ExplanatoryMemo,
}


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


def _amendment_stage_reference(value: object, bill: URIRef) -> URIRef:
    """Validate a source stage URI without assuming its stage was emitted."""
    reference = _source(value, "amendmentList.stage.uri")
    bill_path, path = _path(bill), _path(reference)
    if path[:5] != bill_path:
        raise ValueError("amendmentList.stage.uri must identify a stage of this Bill")
    is_amendment_route = (
        len(path) == 7 and path[5] in HOUSES
        and path[6].isdigit() and int(path[6]) > 0)
    is_stage_route = (
        len(path) == 8 and path[5] == "stage"
        and ((path[6] in HOUSES and path[7].isdigit() and int(path[7]) > 0)
             or (path[6] == "oireachtas" and path[7] == "enacted")))
    if not (is_amendment_route or is_stage_route):
        raise ValueError("amendmentList.stage.uri must use a canonical Bill stage route")
    return reference


def _amendment_stage_alias(stage: URIRef) -> URIRef | None:
    """Return the exact amendment-endpoint alias for an emitted stage IRI."""
    path = _path(stage)
    if (len(path) == 8 and path[:3] == ["ie", "oireachtas", "bill"]
            and path[5] == "stage" and path[6] in HOUSES
            and path[7].isdigit() and int(path[7]) > 0):
        return URIRef("https://data.oireachtas.ie/" + "/".join(path[:5] + path[6:]))
    return None


def _stage_reference_maps(stages: object) -> tuple[dict[str, URIRef], dict[str, URIRef]]:
    """Index emitted stage occurrences and their documented full-IRI alias."""
    if not isinstance(stages, list):
        raise ValueError("bill.stages must be an array")
    exact: dict[str, URIRef] = {}
    aliases: dict[str, URIRef] = {}
    for wrapped in stages:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("stage wrapper must contain event")
        stage = _source(wrapped["event"].get("uri"), "stage.uri")
        key = str(stage)
        if key in exact:
            raise ValueError("duplicate stage URI")
        exact[key] = stage
        alias = _amendment_stage_alias(stage)
        if alias is not None:
            alias_key = str(alias)
            if alias_key in aliases and aliases[alias_key] != stage:
                raise ValueError("amendment stage reference alias is ambiguous")
            aliases[alias_key] = stage
    return exact, aliases


def _resolve_amendment_stage(reference: URIRef, exact: dict[str, URIRef],
                             aliases: dict[str, URIRef]) -> URIRef | None:
    return exact.get(str(reference)) or aliases.get(str(reference))


def _reviewed_unemitted_amendment_stage(reference: URIRef) -> URIRef | None:
    """Resolve only the reviewed stage-6 route when no occurrence was emitted."""
    path = _path(reference)
    if path[-1:] != ["6"]:
        return None
    direct_route = (
        len(path) == 7 and path[:3] == ["ie", "oireachtas", "bill"]
        and path[5] in HOUSES)
    stage_route = (
        len(path) == 8 and path[:3] == ["ie", "oireachtas", "bill"]
        and path[5] == "stage" and path[6] in HOUSES)
    return OIR.CreamListStage if direct_route or stage_route else None


def _amendment_list_parts(item: dict, bill: URIRef) -> tuple[URIRef, dict]:
    stage = item.get("stage")
    if not isinstance(stage, dict):
        raise ValueError("amendmentList.stage must be an object")
    stage_reference = _amendment_stage_reference(stage.get("uri"), bill)
    chamber = item.get("chamber")
    amendment_type = item.get("amendmentTypeUri")
    if not isinstance(chamber, dict):
        raise ValueError("amendmentList.chamber must be an object")
    if not isinstance(amendment_type, dict):
        raise ValueError("amendmentList.amendmentTypeUri must be an object")
    formats = item.get("formats")
    if not isinstance(formats, dict):
        raise ValueError("formats must be an object")
    rendition_signature = []
    for format_name in sorted(("pdf", "xml")):
        rendition = formats.get(format_name)
        if rendition is None:
            continue
        if not isinstance(rendition, dict):
            raise ValueError(f"formats.{format_name} must be null or contain uri")
        rendition_uri = _source(
            rendition.get("uri"), f"amendmentList.formats.{format_name}.uri")
        rendition_signature.append({
            "format": format_name,
            "uri": str(rendition_uri),
        })
    identity = {
        "stage": str(stage_reference), "stageNo": item.get("stageNo"),
        "date": item.get("date"), "chamber": chamber.get("uri"),
        "type": amendment_type.get("uri"),
        "renditions": rendition_signature,
    }
    return stage_reference, identity


def _amendment_list_records(
        amendment_lists: object, bill: URIRef,
) -> list[tuple[dict, URIRef, dict]]:
    """Validate, deduplicate and deterministically order amendment-list records."""
    if not isinstance(amendment_lists, list):
        raise ValueError("bill.amendmentLists must be an array")
    records: dict[bytes, tuple[dict, URIRef, dict, bytes]] = {}
    for wrapped in amendment_lists:
        if not isinstance(wrapped, dict) or not isinstance(
                wrapped.get("amendmentList"), dict):
            raise ValueError("amendment list wrapper must contain amendmentList")
        item = wrapped["amendmentList"]
        stage_reference, identity = _amendment_list_parts(item, bill)
        identity_key = _canonical(identity)
        # showAs is mapped as an rdfs:label but is deliberately not an identity
        # input. Conflicting labels for one complete source identity are unsafe.
        content_key = _canonical({"showAs": item.get("showAs")})
        prior = records.get(identity_key)
        if prior is not None:
            if prior[3] != content_key:
                raise ValueError(
                    f"conflicting amendment-list source content for Bill {bill}")
            continue
        records[identity_key] = (item, stage_reference, identity, content_key)
    return [(item, stage_reference, identity)
            for identity_key, (item, stage_reference, identity, _content_key)
            in sorted(records.items())]


def _unresolved_amendment_stage_omission(stage_reference: URIRef,
                                         amendment: URIRef,
                                         bill: URIRef) -> dict:
    return {
        "path": "bill.amendmentLists[].amendmentList.stage.uri",
        "category": "unresolved_source_reference",
        "source_stage_uri": str(stage_reference),
        "amendment_list_uri": str(amendment),
        "bill_uri": str(bill),
        "context": str(amendment),
        "reason": "Source stage reference is absent from this Bill's emitted stage set; no ProcessStage relation is inferred",
    }


def bill_graph_iri(bill: dict) -> str:
    subject = _source(bill.get("uri"), "bill.uri")
    path, year, number = _path(subject), bill.get("billYear"), bill.get("billNo")
    if not isinstance(year, (str, int)) or not isinstance(number, (str, int)) or len(path) != 5 or path[:4] != ["ie", "oireachtas", "bill", str(year)] or unquote(path[4]) != str(number):
        raise ValueError("bill.uri must embed billYear and billNo")
    integer(year)
    return f"https://data.oireachtas.ie/graph/bill/{quote(str(year), safe='')}/{quote(str(number), safe='')}"


def _derived(parent: URIRef, kind: str, source: object) -> URIRef:
    """Append one deterministic component without creating a second fragment.

    Several Bill resources are themselves fragment IRIs (the process,
    amendment-list Work, and derived Expressions). Appending another ``#``
    would produce an invalid IRI, so nested components encode that separator
    inside the existing fragment while retaining their full parent path.
    """
    parent_text = str(parent)
    base, separator, fragment = parent_text.partition("#")
    component = f"{kind}-{hashlib.sha256(_canonical(source)).hexdigest()}"
    suffix = f"{fragment}%23{component}" if separator else component
    return URIRef(f"{base}#{suffix}")


def _bill_version_expression_identity(
        item: dict, bill: URIRef) -> tuple[URIRef, str, URIRef]:
    """Return source version key, reviewed suffix, and derived Expression IRI."""
    bill = _source(str(bill), "bill.uri")
    source_uri = _source(item.get("uri"), "version.uri")
    parts = _path(source_uri)
    bill_parts = _path(bill)
    if len(parts) <= len(bill_parts) or parts[:len(bill_parts)] != bill_parts:
        raise ValueError("version.uri must identify a resource beneath its owning Bill URI")
    if not parts:
        _unsupported_version("")
    version_key = parts[-1]
    if version_key not in VERSIONS:
        _unsupported_version(version_key)
    identity = {
        "source_version_uri": str(source_uri),
        "version_suffix": version_key,
        "docType": item.get("docType"),
        "lang": item.get("lang"),
        "date": item.get("date"),
        "showAs": item.get("showAs"),
    }
    return source_uri, version_key, _derived(source_uri, "expression", identity)


def _format_identity(expression: URIRef, media_type: URIRef,
                     rendition_uri: URIRef) -> URIRef:
    """Identify a Format by its Expression, controlled media type and rendition."""
    return _derived(expression, "format", {
        "media_type": str(media_type),
        "rendition_uri": str(rendition_uri),
    })


def _bill_event_identity(event: dict) -> tuple[URIRef, dict]:
    """Return a stable Bill-event occurrence IRI and its complete identity."""
    source_uri = _source(event.get("uri"), "event.uri")
    event_type = bill_event_type(event.get("eventURI"))
    if event_type is None:
        raise ValueError("intentionally unmodelled Bill event has no RDF identity")
    dates = event.get("dates")
    if not isinstance(dates, list) or not dates:
        raise ValueError("supported Bill event requires source dates")
    normalized_dates = set()
    for item in dates:
        if not isinstance(item, dict):
            raise ValueError("event date must be an object")
        normalized_dates.add(str(date_literal(item.get("date"))))
    chamber = event.get("chamber")
    if chamber is None:
        chamber_uri = None
    elif isinstance(chamber, dict):
        chamber_uri = str(_house(chamber.get("uri"), "event.chamber.uri"))
    else:
        raise ValueError("event.chamber must be an object or null")
    identity = {
        "source_event_uri": str(source_uri),
        "event_type": str(event_type),
        "dates": sorted(normalized_dates),
        "chamber_uri": chamber_uri,
    }
    return _derived(source_uri, "activity", identity), identity


def _bill_event_records(events: object) -> list[dict]:
    """Collapse exact event duplicates and reject residual identity conflicts."""
    if not isinstance(events, list):
        raise ValueError("bill.events must be an array")
    by_identity: dict[URIRef, tuple[dict, object]] = {}
    for wrapped in events:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("event wrapper must contain event")
        event = wrapped["event"]
        if bill_event_type(event.get("eventURI")) is None:
            continue
        occurrence, _identity = _bill_event_identity(event)
        mapped_remainder = {"showAs": event.get("showAs")}
        previous = by_identity.get(occurrence)
        if previous is not None:
            if _canonical(previous[1]) != _canonical(mapped_remainder):
                raise ValueError(
                    "Bill event occurrence identity has conflicting mapped semantics")
            continue
        by_identity[occurrence] = (event, mapped_remainder)
    return [value[0] for _, value in sorted(by_identity.items(), key=lambda row: str(row[0]))]


def _related_document_identity(item: dict) -> tuple[URIRef, URIRef, URIRef, URIRef]:
    """Return source-key Work, source-semantic Expression, and controlled type."""
    source_uri = _source(item.get("uri"), "relatedDoc.uri")
    doc_type = RELATED_DOCUMENT_TYPES.get(item.get("docType"))
    if doc_type is None:
        _unsupported_doc_type(item.get("docType"))
    # Validate all Expression-level identity inputs before deriving an IRI.
    date_literal(item.get("date"))
    language = _language(item.get("lang"))
    if not isinstance(item.get("showAs"), str) or not item["showAs"]:
        raise ValueError("showAs must be a non-empty string")
    work = URIRef(f"{source_uri}#work")
    expression = _derived(source_uri, "expression", {
        "source_related_document_uri": str(source_uri),
        "doc_type": str(doc_type),
        "language": str(language),
        "date": item.get("date"),
        "show_as": item.get("showAs"),
    })
    return source_uri, work, expression, doc_type


def _def(value: object, table: dict, label: str) -> URIRef:
    value = _source(value, label)
    key = _path(value)[-1]
    if key not in table:
        raise ValueError(f"unsupported {label}: {value}")
    return table[key]


def bill_stage_type(value: object) -> URIRef:
    """Resolve an explicitly reviewed source Bill-stage definition URI."""
    source = _source(value, "stage.stageURI")
    text = str(source)
    if not text.startswith(BILL_STAGE_URI_PREFIX):
        raise ValueError(f"unsupported stage.stageURI: {source}")
    suffix = text.removeprefix(BILL_STAGE_URI_PREFIX)
    if not suffix or "/" in suffix or text != BILL_STAGE_URI_PREFIX + suffix:
        raise ValueError(f"unsupported stage.stageURI: {source}")
    if suffix not in STAGES:
        raise ValueError(f"unsupported stage.stageURI: {source}")
    return STAGES[suffix]


def bill_event_type(value: object) -> URIRef | None:
    """Resolve an explicitly reviewed Bill event URI or its approved omission."""
    source = _source(value, "event.eventURI")
    source_text = str(source)
    if not source_text.startswith(EVENT_URI_PREFIX):
        raise ValueError(f"unsupported event.eventURI: {source}")
    suffix = source_text.removeprefix(EVENT_URI_PREFIX)
    if not suffix or "/" in suffix or source_text != EVENT_URI_PREFIX + suffix:
        raise ValueError(f"unsupported event.eventURI: {source}")
    if suffix in EVENTS:
        return EVENTS[suffix]
    if suffix in INTENTIONALLY_UNMODELLED_EVENTS:
        return None
    raise ValueError(f"unsupported event.eventURI: {source}")


def _bill_event_omission(event: dict, bill: URIRef) -> dict:
    occurrence = event.get("uri")
    if occurrence is not None:
        occurrence = str(_source(occurrence, "event.uri"))
    context = occurrence or str(bill)
    return {
        "path": "bill.events[].event.eventURI",
        "category": "intentionally_unmodelled",
        "source_event_uri": str(_source(event.get("eventURI"), "event.eventURI")),
        "occurrence_uri": occurrence,
        "bill_uri": str(bill),
        "context": context,
        "reason": "Intentionally not modelled under the accepted Bill lifecycle contract",
    }


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
        rendition_uri = _source(rendition["uri"], f"formats.{name}.uri")
        media_type = MEDIA_TYPES[name]
        format_iri = _format_identity(expression, media_type, rendition_uri)
        graph.add((format_iri, RDF.type, ELI_FORMAT_CLASS))
        graph.add((format_iri, ELI_URI_SCHEMA, rendition_uri))
        graph.add((format_iri, ELI_MEDIA_TYPE, media_type))
        graph.add((expression, ELI_EMBODIED_BY, format_iri))


def _activity(graph: Graph, bill: URIRef, process: URIRef, event: dict, *, stage: bool) -> URIRef:
    subject = (_source(event.get("uri"), "stage.uri") if stage
               else _bill_event_identity(event)[0])
    graph.add((subject, RDF.type, ELIDL.LegislativeActivity))
    if stage:
        graph.add((subject, RDF.type, OIR.BillStage))
        graph.add((subject, RDF.type, OIR.BillEvent))
        graph.add((subject, OIR.progressStage, Literal(int(event["progressStage"]), datatype=XSD.positiveInteger)))
        stage_concept = bill_stage_type(event.get("stageURI"))
        graph.add((subject, ELIDL.had_activity_type, stage_concept))
        graph.add((subject, ELIDL.occured_at_stage, stage_concept))
        if not isinstance(event.get("stageCompleted"), bool):
            raise ValueError("stageCompleted must be boolean")
        if event.get("house") is not None:
            graph.add((subject, ELIDL.parliamentary_term, _term(event["house"].get("uri"))))
    else:
        graph.add((subject, RDF.type, OIR.BillEvent))
        event_type = bill_event_type(event.get("eventURI"))
        if event_type is None:
            raise ValueError("intentionally unmodelled Bill event must not be emitted")
        graph.add((subject, ELIDL.had_activity_type, event_type))
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
    graph.add((bill, RDF.type, ELIDL.DraftLegislationWork))
    graph.add((bill, ELI_WORK_TYPE, OIR.Bill))
    graph.add((bill, OIR.legislativeYear, integer(data.get("billYear")))); graph.add((bill, DCTERMS.identifier, string(f"{data['billYear']}/{data['billNo']}")))
    for field, predicate, lang in (("shortTitleEn", DCTERMS.title, "en"), ("shortTitleGa", DCTERMS.title, "ga"), ("longTitleEn", DCTERMS.alternative, "en"), ("longTitleGa", DCTERMS.alternative, "ga")):
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
    graph.add((delivery, ELIDL.created_a_realization_of, bill))
    stages = data.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("bill.stages must be a non-empty array")
    stage_by_uri, stage_aliases = _stage_reference_maps(stages)
    for wrapped in stages:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("stage wrapper must contain event")
        event = wrapped["event"]
        activity = _activity(graph, bill, process, event, stage=True)
        if stage_by_uri.get(str(activity)) != activity:
            raise ValueError("stage occurrence does not resolve to its source Bill stage")
    latest = data.get("mostRecentStage", {}).get("event") if isinstance(data.get("mostRecentStage"), dict) else None
    if not isinstance(latest, dict):
        raise ValueError("mostRecentStage.event is required")
    latest_iri = _source(latest.get("uri"), "mostRecentStage.event.uri")
    if str(latest_iri) not in stage_by_uri:
        raise ValueError("mostRecentStage must reference a generated stage")
    graph.add((process, ELIDL.latest_activity, latest_iri))
    events = data.get("events", [])
    if not isinstance(events, list):
        raise ValueError("bill.events must be an array")
    for wrapped in events:
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("event"), dict):
            raise ValueError("event wrapper must contain event")
        event = wrapped["event"]
        if bill_event_type(event.get("eventURI")) is None:
            omissions.append(_bill_event_omission(event, bill))
    for event in _bill_event_records(events):
        _activity(graph, bill, process, event, stage=False)
    for item, stage_reference, amendment_identity in _amendment_list_records(
            data.get("amendmentLists", []), bill):
        amendment = _derived(bill, "amendment-list", amendment_identity)
        expression = _derived(amendment, "expression", amendment_identity)
        graph.add((amendment, RDF.type, ELIDL.AmendmentToDraftLegislationWork)); graph.add((bill, ELI_HAS_PART, amendment))
        _label(graph, amendment, item.get("showAs"))
        graph.add((amendment, OIR.stageNo, Literal(int(item.get("stageNo")), datatype=XSD.positiveInteger)))
        graph.add((amendment, OIR.hasAmendmentListType, _def(item.get("amendmentTypeUri", {}).get("uri"), AMENDMENT_TYPES, "amendmentList.amendmentTypeUri.uri")))
        graph.add((amendment, ELI_REALIZED_BY, expression)); graph.add((expression, RDF.type, ELI_EXPRESSION_CLASS)); _formats(graph, expression, item.get("formats"))
        stage = _resolve_amendment_stage(
            stage_reference, stage_by_uri, stage_aliases)
        tabling = _derived(amendment, "tabling", amendment_identity)
        graph.add((tabling, RDF.type, ELIDL.LegislativeActivity)); graph.add((tabling, ELIDL.forms_part_of, process))
        graph.add((tabling, ELIDL.activity_date, date_literal(item.get("date"))))
        graph.add((tabling, OIR.inHouse, _house(item.get("chamber", {}).get("uri"), "amendmentList.chamber.uri")))
        if stage is None:
            reviewed_stage = _reviewed_unemitted_amendment_stage(
                stage_reference)
            if reviewed_stage is None:
                omissions.append(_unresolved_amendment_stage_omission(
                    stage_reference, amendment, bill))
            else:
                graph.add((tabling, ELIDL.occured_at_stage, reviewed_stage))
        else:
            stage_concepts = list(graph.objects(stage, ELIDL.occured_at_stage))
            if len(stage_concepts) != 1:
                raise ValueError("amendment stage must resolve to exactly one controlled ProcessStage")
            graph.add((tabling, ELIDL.occured_at_stage, stage_concepts[0]))
    related_work_types: dict[URIRef, URIRef] = {}
    for wrapped in data.get("relatedDocs", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("relatedDoc"), dict):
            raise ValueError("related document wrapper must contain relatedDoc")
        item = wrapped["relatedDoc"]
        _source_uri, work, expression, doc_type = _related_document_identity(item)
        prior_type = related_work_types.setdefault(work, doc_type)
        if prior_type != doc_type:
            raise ValueError(
                "related-document Work identity has conflicting controlled types")
        graph.add((work, RDF.type, ELI_WORK)); graph.add((work, ELI_TYPE, doc_type))
        graph.add((bill, ELI_HAS_PART, work)); graph.add((work, ELI_REALIZED_BY, expression)); graph.add((expression, RDF.type, ELI_LEGAL_EXPRESSION))
        _label(graph, expression, item.get("showAs")); graph.add((expression, ELI_DATE, date_literal(item.get("date")))); graph.add((expression, ELI_LANGUAGE, _language(item.get("lang")))); _formats(graph, expression, item.get("formats"))
    for wrapped in data.get("versions", []):
        if not isinstance(wrapped, dict) or not isinstance(wrapped.get("version"), dict):
            raise ValueError("version wrapper must contain version")
        item = wrapped["version"]
        if item.get("docType") == "act":
            omissions.append({"path": "bill.versions[].version", "context": str(item.get("uri", "")), "category": "ownership_deferred", "reason": "Act descriptions and expressions are owned by a later Acts ETL"}); continue
        if item.get("docType") != "bill":
            raise ValueError("unsupported version docType")
        _source_version_uri, version_key, expression = \
            _bill_version_expression_identity(item, bill)
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
        if sponsor.get("isPrimary") is None:
            omissions.append({
                "path": "bill.sponsors[].sponsor.isPrimary",
                "context": str(sponsor.get("by", {}).get("uri", "")),
                "category": "source_unknown",
                "reason": "Primary-sponsor flag is null in source; Participation is retained without isPrimarySponsor",
            })
        elif not isinstance(sponsor.get("isPrimary"), bool):
            raise ValueError("sponsor.isPrimary must be boolean")
        else:
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
    return graph, sorted(omissions, key=lambda value: (
        value["category"], value["path"], value.get("context", ""),
        value.get("source_event_uri", ""),
        value.get("source_stage_uri", "")))


def _unsupported_version(value: str) -> URIRef:
    raise ValueError(f"unsupported bill version: {value!r}")


def _unsupported_doc_type(value: object) -> URIRef:
    raise ValueError(f"unsupported related document type: {value!r}")


def transform_bill(wrapper: dict) -> Graph:
    return transform_bill_with_report(wrapper)[0]
