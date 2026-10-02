"""Independent validation for reviewed office/unit registry RDF graphs."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from ..transforms.common import MEMBERS


UNIT_IRI_BASE = "https://data.oireachtas.ie/administrative-unit/"
OFFICE_IRI_BASE = "https://data.oireachtas.ie/office/"
UNIT_KEY_RE = re.compile(r"^u-[0-9]{6}$")
OFFICE_KEY_RE = re.compile(r"^o-[0-9]{6}$")
OFFICE_TYPES = {
    "TaoiseachOfficeType", "TanaisteOfficeType", "MinisterOfficeType",
    "MinisterOfStateOfficeType", "CeannComhairleOfficeType",
    "CathaoirleachOfficeType", "AttorneyGeneralOfficeType",
}
UNIT_RELATIONS = {
    "headsAdministrativeUnit": "MinisterOfficeType",
    "assignedToAdministrativeUnit": "MinisterOfStateOfficeType",
}
TOP_FIELDS = {"version", "administrative_units", "offices"}
UNIT_FIELDS = {"key", "label_en", "label_ga", "aliases", "reviewer_notes", "evidence"}
OFFICE_FIELDS = UNIT_FIELDS | {"office_type", "unit_relationships"}
ALIAS_FIELDS = {"language", "label", "contexts", "validity", "unit_keys", "source_uris"}


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"registry {field} must be a non-empty string")
    return value


def _entry_fields(entry: object, required: set[str], optional: set[str], label: str) -> dict:
    if not isinstance(entry, dict):
        raise ValueError(f"each registry {label} must be an object")
    keys = set(entry)
    if required - keys:
        raise ValueError(f"registry {label} is missing fields: {sorted(required - keys)}")
    if keys - required - optional:
        raise ValueError(f"registry {label} has unsupported fields: {sorted(keys - required - optional)}")
    return entry


def _validate_common(entry: dict, label: str) -> None:
    key = _text(entry["key"], f"{label}.key")
    key_pattern = UNIT_KEY_RE if label == "administrative unit" else OFFICE_KEY_RE
    expected = "u-NNNNNN" if label == "administrative unit" else "o-NNNNNN"
    if not key_pattern.fullmatch(key):
        raise ValueError(f"registry {label}.key must be an opaque {expected} key")
    _text(entry["label_en"], f"{label}.label_en")
    if "label_ga" in entry:
        _text(entry["label_ga"], f"{label}.label_ga")
    _text(entry["reviewer_notes"], f"{label}.reviewer_notes")
    evidence = entry["evidence"]
    if (not isinstance(evidence, list) or not evidence
            or any(not isinstance(item, str) or not item.strip() for item in evidence)
            or len(set(evidence)) != len(evidence)):
        raise ValueError(f"registry {label}.evidence must be a non-empty list of unique references")
    aliases = entry["aliases"]
    if not isinstance(aliases, list):
        raise ValueError(f"registry {label}.aliases must be a list")
    seen = set()
    for alias in aliases:
        allowed_alias_fields = {"language", "label"} if label == "administrative unit" else ALIAS_FIELDS
        if (not isinstance(alias, dict) or not {"language", "label"} <= set(alias)
                or set(alias) - allowed_alias_fields):
            raise ValueError(f"each registry {label} alias must have language and label, with supported optional review scope")
        language = alias["language"]
        if not isinstance(language, str) or language not in {"en", "ga"}:
            raise ValueError(f"registry {label} alias language must be en or ga")
        text = _text(alias["label"], f"{label}.alias.label")
        pair = (language, text)
        if pair in seen:
            raise ValueError(f"registry {label} contains a duplicate alias")
        seen.add(pair)
        contexts = alias.get("contexts", [])
        if (not isinstance(contexts, list) or any(not isinstance(value, str) or not value.strip()
                                                   for value in contexts)
                or len(contexts) != len(set(contexts))):
            raise ValueError(f"registry {label} alias contexts must be unique non-empty strings")
        for context in contexts:
            if context in {"dail", "seanad"}:
                continue
            if not _local_source_iri(context):
                raise ValueError(f"registry {label} alias context must be a House code or local Oireachtas source IRI")
        source_uris = alias.get("source_uris", [])
        if (not isinstance(source_uris, list) or any(not _local_source_iri(value)
                                                     for value in source_uris)
                or len(source_uris) != len(set(source_uris))):
            raise ValueError(f"registry {label} alias source_uris must be unique local Oireachtas source IRIs")
        unit_keys = alias.get("unit_keys", [])
        if (not isinstance(unit_keys, list) or any(not isinstance(value, str)
                                                   or not re.fullmatch(r"u-[0-9]{6}", value)
                                                   for value in unit_keys)
                or len(unit_keys) != len(set(unit_keys))):
            raise ValueError(f"registry {label} alias unit_keys must be unique registered unit keys")
        validity = alias.get("validity")
        if validity is not None:
            if not isinstance(validity, dict) or set(validity) - {"start", "end"} or "start" not in validity:
                raise ValueError(f"registry {label} alias validity must have start and optional end")
            start = _instant(validity["start"], f"{label}.alias.validity.start")
            end = _instant(validity["end"], f"{label}.alias.validity.end") if validity.get("end") is not None else None
            if end is not None and end < start:
                raise ValueError(f"registry {label} alias validity has reverse dates")


def _local_source_iri(value: object) -> bool:
    if not isinstance(value, str) or value != value.strip() or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (parsed.scheme == "https" and parsed.netloc == "data.oireachtas.ie"
            and not parsed.query and not parsed.fragment and not parsed.username
            and not parsed.password and not port and bool(parsed.path))


def _instant(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"registry {label} must be an ISO date or date-time")
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"registry {label} must be an ISO date or date-time") from error
    return instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)


def validate_registry_source(registry: object) -> dict:
    """Validate registry data without consulting transformer output."""
    if not isinstance(registry, dict) or set(registry) != TOP_FIELDS:
        raise ValueError("office registry must contain exactly version, administrative_units and offices")
    if type(registry["version"]) is not int or registry["version"] != 1:
        raise ValueError("office registry version must be integer 1")
    units, offices = registry["administrative_units"], registry["offices"]
    if not isinstance(units, list) or not isinstance(offices, list):
        raise ValueError("office registry administrative_units and offices must be arrays")

    unit_keys: set[str] = set()
    for unit in units:
        _entry_fields(unit, UNIT_FIELDS - {"label_ga"}, {"label_ga"}, "administrative unit")
        _validate_common(unit, "administrative unit")
        if unit["key"] in unit_keys:
            raise ValueError(f"duplicate administrative-unit registry key: {unit['key']}")
        unit_keys.add(unit["key"])

    office_keys: set[str] = set()
    for office in offices:
        _entry_fields(office, OFFICE_FIELDS - {"label_ga"}, {"label_ga"}, "office")
        _validate_common(office, "office")
        if office["key"] in office_keys:
            raise ValueError(f"duplicate office registry key: {office['key']}")
        office_keys.add(office["key"])
        office_type = office["office_type"]
        if not isinstance(office_type, str) or office_type not in OFFICE_TYPES:
            raise ValueError(f"unsupported OfficeType concept: {office_type!r}")
        relationships = office["unit_relationships"]
        if not isinstance(relationships, list):
            raise ValueError(f"registry office {office['key']}.unit_relationships must be an array")
        seen_relationships = set()
        for relation in relationships:
            if not isinstance(relation, dict) or set(relation) != {"relationship", "unit_key"}:
                raise ValueError("each office unit relationship must have relationship and unit_key")
            predicate = relation["relationship"]
            if not isinstance(predicate, str) or UNIT_RELATIONS.get(predicate) != office_type:
                raise ValueError(f"{predicate!r} is incompatible with {office_type}")
            target = relation["unit_key"]
            if not isinstance(target, str) or target not in unit_keys:
                raise ValueError(f"office {office['key']} references unregistered AdministrativeUnit {target!r}")
            pair = (predicate, target)
            if pair in seen_relationships:
                raise ValueError(f"office {office['key']} repeats an administrative-unit relationship")
            seen_relationships.add(pair)
        for alias in office["aliases"]:
            unknown_units = sorted(set(alias.get("unit_keys", [])) - unit_keys)
            if unknown_units:
                raise ValueError(f"office {office['key']} alias references unregistered AdministrativeUnit {unknown_units[0]!r}")
    return registry


def _labels(subject: URIRef, entry: dict) -> set[tuple]:
    triples = {(subject, SKOS.prefLabel, Literal(entry["label_en"], lang="en"))}
    if "label_ga" in entry:
        triples.add((subject, SKOS.prefLabel, Literal(entry["label_ga"], lang="ga")))
    triples.update((subject, SKOS.altLabel,
                    Literal(alias["label"], lang=alias["language"])) for alias in entry["aliases"])
    return triples


def _assert_exact_graph(graph: Graph, expected: set[tuple], name: str) -> None:
    if graph is None:
        raise ValueError(f"{name} RDF graph is required")
    missing, unexpected = expected.difference(graph), set(graph).difference(expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing " + "; ".join(" ".join(term.n3() for term in triple)
                                                   for triple in sorted(missing, key=str)))
        if unexpected:
            details.append("unexpected " + "; ".join(" ".join(term.n3() for term in triple)
                                                       for triple in sorted(unexpected, key=str)))
        raise ValueError(f"{name} source-to-RDF correspondence failed: " + " | ".join(details))


def validate_administrative_units(registry: object, graph: Graph) -> None:
    """Check exact AdministrativeUnit RDF, independently of its transformer."""
    registry = validate_registry_source(registry)
    expected = set()
    for unit in registry["administrative_units"]:
        subject = URIRef(UNIT_IRI_BASE + unit["key"])
        expected.add((subject, RDF.type, MEMBERS.AdministrativeUnit))
        expected.update(_labels(subject, unit))
    _assert_exact_graph(graph, expected, "AdministrativeUnit")


def validate_offices(registry: object, graph: Graph) -> None:
    """Check exact NamedOffice RDF and its controlled types/unit references."""
    registry = validate_registry_source(registry)
    expected = set()
    for office in registry["offices"]:
        subject = URIRef(OFFICE_IRI_BASE + office["key"])
        expected.update({
            (subject, RDF.type, MEMBERS.NamedOffice),
            (subject, MEMBERS.hasRoleType, MEMBERS[office["office_type"]]),
        })
        expected.update(_labels(subject, office))
        for relation in office["unit_relationships"]:
            expected.add((subject, MEMBERS[relation["relationship"]],
                          URIRef(UNIT_IRI_BASE + relation["unit_key"])))
    _assert_exact_graph(graph, expected, "NamedOffice")
