"""Source-to-RDF completeness and Phase 2 graph-boundary checks."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS

from ..transforms.common import MEMBERS, english, iri, string

HOUSE_TERM_RE = re.compile(r"^https://data\.oireachtas\.ie/ie/oireachtas/house/(dail|seanad)/([1-9][0-9]*)$")
SOURCE_NETLOC = "data.oireachtas.ie"


def house_term_iri(house: dict, *, expected_house: str | None = None) -> URIRef:
    if not isinstance(house, dict):
        raise ValueError("house must be an object")
    code, number = house.get("houseCode"), house.get("houseNo")
    if code not in {"dail", "seanad"}:
        raise ValueError(f"unsupported houseCode: {code!r}")
    if expected_house is not None and code != expected_house:
        raise ValueError(f"representation requires houseCode {expected_house!r}")
    term = iri(house.get("uri"))
    match = HOUSE_TERM_RE.fullmatch(str(term))
    if not match or match.group(1) != code or match.group(2) != str(number):
        raise ValueError("house.uri must be the direct IRI for its houseCode and houseNo")
    return term


def _source_path(value: URIRef) -> list[str]:
    parsed = urlsplit(str(value))
    if parsed.scheme != "https" or parsed.netloc != SOURCE_NETLOC or parsed.query or parsed.fragment:
        raise ValueError("source URI must use the canonical Oireachtas HTTPS origin")
    return [part for part in parsed.path.split("/") if part]


def _slug_matches(segment: str, code: object, *, name: str) -> bool:
    if not isinstance(code, str) or not code or "/" in code:
        return False
    # API source IRIs may contain either literal Unicode or percent-encoded
    # Unicode; both denote the same direct source path segment.
    return unquote(segment) == code and "/" not in unquote(segment)


def validate_party_iri(subject: URIRef, term: URIRef, code: object) -> None:
    term_path, path = _source_path(term), _source_path(subject)
    if len(term_path) != 5 or len(path) != 6 or term_path[:3] != ["ie", "oireachtas", "house"] or path[:3] != ["ie", "oireachtas", "party"]:
        raise ValueError("party.uri must use the term-scoped party source path")
    if path[3:5] != term_path[3:5] or not _slug_matches(path[5], code, name="partyCode"):
        raise ValueError("party.uri must embed its house term and partyCode")


def validate_representation_iri(subject: URIRef, term: URIRef, code: object, represent_type: str) -> None:
    term_path, path = _source_path(term), _source_path(subject)
    if len(term_path) != 5 or len(path) != 7 or term_path[:3] != ["ie", "oireachtas", "house"] or path[:5] != term_path:
        raise ValueError("constituencyOrPanel.uri must embed its HouseTerm source path")
    if path[5] != represent_type or not _slug_matches(path[6], code, name="representCode"):
        raise ValueError("constituencyOrPanel.uri must match representType and representCode")


def assert_expected(graph: Graph, expected: set[tuple]) -> None:
    missing = expected.difference(graph)
    unexpected = set(graph).difference(expected)
    if missing or unexpected:
        details = []
        if missing:
            details.append("missing " + "; ".join(" ".join(term.n3() for term in triple) for triple in sorted(missing, key=str)))
        if unexpected:
            details.append("unexpected " + "; ".join(" ".join(term.n3() for term in triple) for triple in sorted(unexpected, key=str)))
        raise ValueError("source-to-RDF correspondence failed: " + " | ".join(details))


def validate_parties_correspondence(records: list[dict], graph: Graph | None) -> None:
    expected = set()
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("party"), dict) or not isinstance(wrapper.get("house"), dict):
            raise ValueError("each Parties record must contain party and house objects")
        party = wrapper["party"]
        subject, term = iri(party.get("uri")), house_term_iri(wrapper["house"])
        code = party.get("partyCode")
        validate_party_iri(subject, term, code)
        expected.update({
            (subject, RDF.type, MEMBERS.ParliamentaryMemberCollection),
            (subject, MEMBERS.partyCode, string(code)),
            (subject, SKOS.prefLabel, english(party.get("showAs"))),
            (subject, MEMBERS.activeDuringTerm, term),
        })
        expected.add((subject, RDF.type, MEMBERS.IndependentMemberCollection if code == "Independent" else MEMBERS.ParliamentaryParty))
    if graph is not None:
        assert_expected(graph, expected)


def validate_constituencies_correspondence(records: list[dict], graph: Graph | None, represent_types: dict) -> None:
    expected = set()
    for wrapper in records:
        if not isinstance(wrapper, dict) or not isinstance(wrapper.get("constituencyOrPanel"), dict) or not isinstance(wrapper.get("house"), dict):
            raise ValueError("each Constituencies record must contain constituencyOrPanel and house objects")
        representation = wrapper["constituencyOrPanel"]
        represent_type = representation.get("representType")
        if represent_type not in represent_types:
            raise ValueError(f"unsupported representType: {represent_type!r}")
        class_, house_code = represent_types[represent_type]
        subject, term = iri(representation.get("uri")), house_term_iri(wrapper["house"], expected_house=house_code)
        validate_representation_iri(subject, term, representation.get("representCode"), represent_type)
        expected.update({
            (subject, RDF.type, MEMBERS.Constituencies),
            (subject, RDF.type, class_),
            (subject, MEMBERS.representCode, string(representation.get("representCode"))),
            (subject, SKOS.prefLabel, english(representation.get("showAs"))),
            (subject, MEMBERS.constituencyInHouseTerm, term),
        })
    if graph is not None:
        assert_expected(graph, expected)
