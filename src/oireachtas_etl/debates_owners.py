"""Build exact Debates owner lookups from validated owner RDF graphs.

The caller supplies owner graphs only after their normal source-to-RDF
validation has passed.  This module repeats the graph-level SHACL/quality
checks it can perform without source JSON, then indexes only explicitly typed
owner resources with source identities consistent with their RDF owner
contracts.  It does not resolve labels, slugs, or guessed URI variants.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import re
from types import MappingProxyType
from urllib.parse import unquote, urlsplit

from pyshacl import validate
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from .reference_coverage import committee_identity
from .transforms.common import MEMBERS, OIR
from .transforms.debates import DebateReferenceRegistry, OwnerMatch
from .validation.committees import validate_quality as validate_committee_quality
from .validation.committees import validate_shacl as validate_committee_shacl
from .validation.houses import (
    validate_quality as validate_house_quality,
    validate_rdf,
    validate_shacl as validate_house_shacl,
)
from .validation.members import RESOURCES as MEMBER_VALIDATION_RESOURCES


HOUSE_IRIS = {
    "dail": URIRef("https://data.oireachtas.ie/house/dail"),
    "seanad": URIRef("https://data.oireachtas.ie/house/seanad"),
}
HOUSE_TERM_PATH = re.compile(
    r"^/ie/oireachtas/house/(dail|seanad)/([1-9][0-9]*)$"
)


def _validate_members_graph(graph: Graph) -> None:
    """Run graph-only Member SHACL and RDF checks.

    Source correspondence is deliberately still the responsibility of the
    normal Member validator, which receives the source record.  The resolver
    must be given that already-validated output graph; this second pass makes
    sure its graph-level requirements have not been lost before indexing.
    """

    validate_rdf(graph)
    conforms, _, report = validate(
        graph,
        shacl_graph=MEMBER_VALIDATION_RESOURCES.joinpath("members.ttl").read_text(),
        shacl_graph_format="turtle",
        inference="none",
        abort_on_first=False,
    )
    if not conforms:
        raise ValueError("Member owner graph SHACL validation failed:\n" + str(report))


def _validate_owner_graphs(
    member_graph: Graph | None,
    house_graph: Graph | None,
    committee_graph: Graph | None,
) -> None:
    if member_graph is not None:
        if not isinstance(member_graph, Graph):
            raise TypeError("member_graph must be an rdflib Graph or None")
        _validate_members_graph(member_graph)
    if house_graph is not None:
        if not isinstance(house_graph, Graph):
            raise TypeError("house_graph must be an rdflib Graph or None")
        validate_rdf(house_graph)
        validate_house_shacl(house_graph)
        validate_house_quality(house_graph)
    if committee_graph is not None:
        if not isinstance(committee_graph, Graph):
            raise TypeError("committee_graph must be an rdflib Graph or None")
        validate_rdf(committee_graph)
        validate_committee_shacl(committee_graph)
        validate_committee_quality(committee_graph)


def _official_source_iri(value: URIRef, owner_kind: str):
    text = str(value)
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid {owner_kind} owner IRI: {text!r}") from error
    if (
        parsed.scheme != "https"
        or parsed.netloc != "data.oireachtas.ie"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
    ):
        raise ValueError(f"{owner_kind} owner IRI is not a canonical Oireachtas source IRI: {text!r}")
    return parsed


def _lookup_keys(source_iri: URIRef, owner_kind: str) -> tuple[str, str]:
    """Return only the exact absolute source IRI and its AKN path reference.

    AKN uses root-relative hrefs for these source identities.  Pairing that
    exact path with the official source IRI is URI-reference resolution, not
    an alternate identity rule; path segments are never decoded, reordered or
    matched by slug/label.
    """

    parsed = _official_source_iri(source_iri, owner_kind)
    return str(source_iri), parsed.path


def _member_source_iri(subject: URIRef, graph: Graph) -> URIRef:
    parsed = _official_source_iri(subject, "Member")
    # Inspect the lexical path as supplied.  Filtering empty path components
    # would normalize ``//`` and a trailing slash into a different owner IRI.
    path_parts = parsed.path.split("/")
    if (
        len(path_parts) != 6
        or path_parts[0] != ""
        or any(not segment for segment in path_parts[1:])
        or path_parts[1:5] != ["ie", "oireachtas", "member", "id"]
    ):
        raise ValueError(f"Member owner IRI does not match the Members source identity: {subject}")
    codes = list(graph.objects(subject, OIR.memberCode))
    if (
        len(codes) != 1
        or not isinstance(codes[0], Literal)
        or codes[0].datatype != XSD.string
        or codes[0].language is not None
        or not str(codes[0])
        or unquote(path_parts[-1]) != str(codes[0])
    ):
        raise ValueError(f"Member owner identity does not agree with its unique memberCode: {subject}")
    return subject


def _house_term_identity(subject: URIRef, graph: Graph) -> tuple[URIRef, URIRef]:
    parsed = _official_source_iri(subject, "HouseTerm")
    match = HOUSE_TERM_PATH.fullmatch(parsed.path)
    types = set(graph.objects(subject, RDF.type)) & {OIR.DailTerm, OIR.SeanadTerm}
    if not match or len(types) != 1:
        raise ValueError(f"HouseTerm owner identity is malformed or ambiguously typed: {subject}")
    code, number = match.groups()
    expected_type = OIR.DailTerm if code == "dail" else OIR.SeanadTerm
    if types != {expected_type}:
        raise ValueError(f"HouseTerm owner type does not agree with its source IRI: {subject}")

    house_codes = list(graph.objects(subject, OIR.houseCode))
    term_numbers = list(graph.objects(subject, OIR.termNo))
    term_houses = set(graph.objects(subject, OIR.termOf))
    expected_house = HOUSE_IRIS[code]
    if (
        len(house_codes) != 1
        or house_codes[0] != Literal(code, datatype=XSD.string)
        or len(term_numbers) != 1
        or term_numbers[0] != Literal(int(number), datatype=XSD.integer)
        or term_houses != {expected_house}
        or (expected_house, RDF.type, OIR.House) not in graph
    ):
        raise ValueError(f"HouseTerm termOf/identity does not agree with its existing House owner: {subject}")
    return subject, expected_house


def _committee_source_iri(subject: URIRef, graph: Graph) -> URIRef:
    try:
        canonical, term, _code, _number = committee_identity(str(subject))
    except ValueError as error:
        raise ValueError(f"Committee owner identity is not an approved source IRI: {subject}") from error
    if canonical != str(subject):
        raise ValueError(f"Committee owner IRI is not exact/canonical: {subject}")
    terms = set(graph.objects(subject, MEMBERS.committeeInHouseTerm))
    if terms != {URIRef(term)}:
        raise ValueError(f"Committee HouseTerm does not agree with its exact source IRI: {subject}")
    return subject


def _as_owner_match(values: set[URIRef]) -> OwnerMatch:
    ordered = tuple(sorted(values, key=str))
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    return ordered


def _index_owner_iris(
    subjects: set[URIRef],
    key_builder,
    owner_kind: str,
) -> dict[str, OwnerMatch]:
    by_key: dict[str, set[URIRef]] = defaultdict(set)
    for subject in subjects:
        if not isinstance(subject, URIRef):
            raise ValueError(f"{owner_kind} owner subjects must be IRIs")
        for key in key_builder(subject):
            by_key[key].add(subject)
    return {key: _as_owner_match(values) for key, values in sorted(by_key.items())}


def _registry_version(
    members: dict[str, OwnerMatch],
    house_terms: dict[str, OwnerMatch],
    committees: dict[str, OwnerMatch],
    houses_by_term: dict[str, OwnerMatch],
) -> str:
    def normalized(values: dict[str, OwnerMatch]) -> list[tuple[str, list[str]]]:
        result = []
        for key, value in sorted(values.items()):
            targets = () if value is None else ((value,) if isinstance(value, URIRef) else value)
            result.append((key, sorted(str(target) for target in targets)))
        return result

    payload = json.dumps(
        {
            "members": normalized(members),
            "house_terms": normalized(house_terms),
            "committees": normalized(committees),
            "houses_by_term": normalized(houses_by_term),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "owner-rdf-registry-v1:" + hashlib.sha256(payload).hexdigest()


def build_debate_reference_resolver(
    *,
    member_graph: Graph | None = None,
    house_graph: Graph | None = None,
    committee_graph: Graph | None = None,
) -> DebateReferenceRegistry:
    """Create the existing Debates resolver interface from validated owner RDF.

    ``member_graph``, ``house_graph`` and ``committee_graph`` must be output
    graphs that have passed their source-aware owner validators.  This factory
    repeats graph-only SHACL/quality checks and rejects owner identities that
    do not agree with their directly asserted owner typing/identity contracts.
    It reads no labels or descriptive values and emits no RDF itself.  Missing
    optional graphs simply leave that owner's lookup empty.
    """

    _validate_owner_graphs(member_graph, house_graph, committee_graph)

    member_subjects = (
        set(member_graph.subjects(RDF.type, OIR.Member)) if member_graph is not None else set()
    )
    house_term_subjects: set[URIRef] = set()
    houses_by_term: dict[str, OwnerMatch] = {}
    if house_graph is not None:
        house_term_subjects = set(house_graph.subjects(RDF.type, OIR.DailTerm))
        house_term_subjects.update(house_graph.subjects(RDF.type, OIR.SeanadTerm))
        for subject in house_term_subjects:
            if not isinstance(subject, URIRef):
                raise ValueError("HouseTerm owner subjects must be IRIs")
            term, house = _house_term_identity(subject, house_graph)
            houses_by_term[str(term)] = house

    committee_subjects = (
        set(committee_graph.subjects(RDF.type, MEMBERS.Committee))
        if committee_graph is not None
        else set()
    )

    members = _index_owner_iris(
        member_subjects,
        lambda subject: _lookup_keys(_member_source_iri(subject, member_graph), "Member"),
        "Member",
    )
    house_terms = _index_owner_iris(
        house_term_subjects,
        lambda subject: _lookup_keys(subject, "HouseTerm"),
        "HouseTerm",
    )
    committees = _index_owner_iris(
        committee_subjects,
        lambda subject: _lookup_keys(_committee_source_iri(subject, committee_graph), "Committee"),
        "Committee",
    )
    return DebateReferenceRegistry(
        members_by_tlc_href=MappingProxyType(members),
        house_terms_by_author_href=MappingProxyType(house_terms),
        committees_by_author_href=MappingProxyType(committees),
        houses_by_term_iri=MappingProxyType(houses_by_term),
        version=_registry_version(members, house_terms, committees, houses_by_term),
    )
