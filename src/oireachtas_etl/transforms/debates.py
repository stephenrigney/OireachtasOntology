"""Deterministic, Work-owned transformation of one exact AKN debate XML file.

This is the Tranche 2 core.  It emits only Debate-owned structure and links to
owner resources returned by the explicit resolver interface below.  It does
not fetch sources, discover expression sets, validate/publish named graphs, or
copy transcript text into RDF.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Protocol, TypeAlias
from urllib.parse import quote, urlsplit
from xml.parsers import expat
from xml.sax.saxutils import quoteattr
import xml.etree.ElementTree as ET

from rdflib import Graph, URIRef
from rdflib.namespace import RDF

from .common import ELIDL, OIR, date_literal, datetime_literal, integer, midnight, string


DATA_ORIGIN = "https://data.oireachtas.ie"
AKN_ROUTE = "/akn/ie/debateRecord/"
GRAPH_ROUTE = "https://data.oireachtas.ie/graph/debate/"
REFERENCE_CONTRACT_VERSION = "debates-reference-outcomes-v1"
TRANSFORM_CONTRACT_VERSION = "debates-transformer-core-v1"

ADDRESSABLE_NAMES = frozenset({"debateSection", "speech", "summary", "question"})
VOTE_GROUPS = {
    "ta": (OIR.votedFor, OIR.taCount),
    "nil": (OIR.votedAgainst, OIR.nilCount),
    "staon": (OIR.abstained, OIR.staonCount),
}
VOTE_OUTCOMES = {"#carried": OIR.DeclaredCarried, "#lost": OIR.DeclaredLost}
APPROVED_CHAMBER_HOUSES = {
    "dail": URIRef("https://data.oireachtas.ie/house/dail"),
    "seanad": URIRef("https://data.oireachtas.ie/house/seanad"),
}


OwnerMatch: TypeAlias = str | URIRef | Iterable[str | URIRef] | None


class DebateReferenceResolver(Protocol):
    """Resolver of exact source identities to existing owner resources.

    Implementations must return only resources that already exist in the
    corresponding authoritative owner dataset.  Mapping keys are exact parsed
    AKN values, not labels or normalized aliases.  A sequence with several
    values is treated as ambiguous and never linked.

    ``house_for_term`` must reflect the existing HouseTerm ``:termOf`` link;
    the transformer never infers a House from a HouseTerm URI or author path.
    Roles, question recipients, Bills/events and other owner types are
    deliberately not part of this interface in this tranche.
    """

    version: str

    def resolve_member(self, tlc_person_href: str) -> OwnerMatch: ...

    def resolve_house_term(self, work_author_href: str) -> OwnerMatch: ...

    def resolve_committee(self, work_author_href: str) -> OwnerMatch: ...

    def house_for_term(self, house_term_iri: str) -> OwnerMatch: ...


@dataclass(frozen=True)
class DebateReferenceRegistry:
    """Simple exact-key implementation of :class:`DebateReferenceResolver`.

    Values may be a single IRI, a sequence of candidate IRIs, or ``None``.
    The mappings are intentionally owner-specific: they are not a facility for
    minting resources, label matching, or resolving deferred role/Bill links.
    """

    members_by_tlc_href: Mapping[str, OwnerMatch] = field(default_factory=dict)
    house_terms_by_author_href: Mapping[str, OwnerMatch] = field(default_factory=dict)
    committees_by_author_href: Mapping[str, OwnerMatch] = field(default_factory=dict)
    houses_by_term_iri: Mapping[str, OwnerMatch] = field(default_factory=dict)
    version: str = "unversioned"

    def resolve_member(self, tlc_person_href: str) -> OwnerMatch:
        return self.members_by_tlc_href.get(tlc_person_href)

    def resolve_house_term(self, work_author_href: str) -> OwnerMatch:
        return self.house_terms_by_author_href.get(work_author_href)

    def resolve_committee(self, work_author_href: str) -> OwnerMatch:
        return self.committees_by_author_href.get(work_author_href)

    def house_for_term(self, house_term_iri: str) -> OwnerMatch:
        return self.houses_by_term_iri.get(house_term_iri)


@dataclass(frozen=True)
class DebateTransformResult:
    """Successful transform result for one DebateRecord / replaceable graph."""

    graph: Graph
    work_iri: str
    expression_iri: str
    graph_iri: str
    source_sha256: str
    reference_report: dict

    @property
    def reference_report_json(self) -> bytes:
        """UTF-8 JSON bytes with sorted keys and deterministic compact form."""

        return _canonical_json(self.reference_report)

    @property
    def reference_report_text(self) -> str:
        return self.reference_report_json.decode("utf-8")


class DebateTransformError(ValueError):
    """Fail-closed source/identity error with source-hash-linked evidence."""

    def __init__(self, message: str, report: Mapping[str, object]):
        super().__init__(message)
        self.reference_report = dict(report)
        self.source_sha256 = self.reference_report.get("source_sha256")

    @property
    def reference_report_json(self) -> bytes:
        return _canonical_json(self.reference_report)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _local_name(element: ET.Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _expanded_qname(element: ET.Element) -> str:
    tag = element.tag
    if not isinstance(tag, str):
        return str(tag)
    if tag.startswith("{") and "}" in tag:
        namespace, local = tag[1:].split("}", 1)
        return f"{{{namespace}}}{local}"
    return tag


def _children_named(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in parent if _local_name(child) == name]


def _descendants_named(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in parent.iter() if child is not parent and _local_name(child) == name]


def _required_value_attribute(element: ET.Element, label: str) -> str:
    value = element.get("value")
    if value is None or value == "":
        raise ValueError(f"{label} must have a non-empty @value")
    return value


def _parse_source_akn_path(value: object, label: str) -> tuple[str, list[str]]:
    """Validate a Work/Expression FRBRuri source spelling and return its path."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty AKN FRBR URI")
    if "?" in value or "#" in value:
        raise ValueError(f"{label} must not contain a query or fragment")
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ValueError(f"{label} is not a valid URI/path") from error

    if parsed.scheme or parsed.netloc:
        if (
            parsed.scheme != "https"
            or parsed.netloc != "data.oireachtas.ie"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"{label} must use the exact Oireachtas HTTPS origin without query or fragment")
        try:
            if parsed.port is not None:
                raise ValueError(f"{label} must not specify a port")
        except ValueError as error:
            raise ValueError(f"{label} must use the exact Oireachtas HTTPS origin") from error
        path = parsed.path
    else:
        if parsed.query or parsed.fragment or not value.startswith("/"):
            raise ValueError(f"{label} must be an absolute AKN path or exact Oireachtas HTTPS URI")
        path = parsed.path

    if not path.startswith(AKN_ROUTE):
        raise ValueError(f"{label} must use the /akn/ie/debateRecord/ route")
    segments = path[1:].split("/")
    if any(not segment or segment in {".", ".."} for segment in segments):
        raise ValueError(f"{label} contains an empty or dot path segment")
    if any(re.search(r"%(?![0-9A-Fa-f]{2})", segment) for segment in segments):
        raise ValueError(f"{label} contains a malformed percent escape")
    return path, segments


def _encode_component(value: str) -> str:
    return quote(value, safe="-._~", encoding="utf-8", errors="strict")


def _canonical_akn_iri(value: object, label: str) -> tuple[str, str, list[str]]:
    path, segments = _parse_source_akn_path(value, label)
    encoded_path = "/".join(_encode_component(segment) for segment in segments)
    return f"{DATA_ORIGIN}/{encoded_path}", path, segments


def _debate_graph_iri(work_iri: str) -> str:
    encoded_prefix = DATA_ORIGIN + AKN_ROUTE
    if not work_iri.startswith(encoded_prefix):
        raise ValueError("canonical DebateRecord IRI does not have the approved graph route prefix")
    return GRAPH_ROUTE + work_iri[len(encoded_prefix):]


def _xml_ncname(value: str) -> bool:
    """Return whether *value* fits the XML 1.0 Fifth Edition NCName grammar."""

    start = (
        r"A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF"
        r"\u0370-\u037D\u037F-\u1FFF\u200C-\u200D"
        r"\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF"
        r"\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
    )
    char = start + r"0-9\-.\u00B7\u0300-\u036F\u203F-\u2040"
    return re.fullmatch(f"[{start}][{char}]*", value) is not None


def _local_fragment(raw: str | None) -> tuple[str, str | None]:
    """Classify an XML local-fragment reference as valid, placeholder, or bad."""

    if raw is None:
        return "absent", None
    if raw == "#":
        return "placeholder", None
    if not raw.startswith("#") or not _xml_ncname(raw[1:]):
        return "malformed", None
    return "valid", raw[1:]


def _valid_absolute_target(value: object, label: str) -> URIRef:
    if isinstance(value, URIRef):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        raise ValueError(f"{label} resolver target must be an absolute HTTP(S) IRI")
    try:
        parsed = urlsplit(text)
    except ValueError as error:
        raise ValueError(f"{label} resolver target is not a valid IRI: {text!r}") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or any(character.isspace() for character in text)
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{label} resolver target must be an absolute HTTP(S) IRI: {text!r}")
    return URIRef(text)


def _matches(value: OwnerMatch, label: str) -> list[URIRef]:
    if value is None:
        return []
    if isinstance(value, (str, URIRef)):
        values: Iterable[str | URIRef] = (value,)
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        values = tuple(value)
    else:
        raise ValueError(f"{label} resolver result must be an IRI, sequence of IRIs, or None")
    normalized = {_valid_absolute_target(item, label) for item in values}
    return sorted(normalized, key=str)


def _resolver_version(resolver: DebateReferenceResolver | None, override: str | None) -> str:
    if override is not None:
        if not isinstance(override, str) or not override:
            raise ValueError("resolver_version must be a non-empty string")
        return override
    if resolver is None:
        return "none"
    version = getattr(resolver, "version", None)
    if not isinstance(version, str) or not version:
        raise ValueError("a supplied DebateReferenceResolver must expose a non-empty version")
    return version


def _parse_spans(source_xml: bytes) -> tuple[list[dict], str]:
    """Capture exact source subtrees and in-scope namespaces for C14N fallback.

    ElementTree does not retain original namespace prefixes.  The Expat pass
    records the original byte span and namespace scope for each element so the
    fallback identity uses C14N 2.0 over the actual source subtree rather than
    a prefix-rewritten ElementTree serialization.
    """

    parser = expat.ParserCreate(namespace_separator="}")
    if source_xml.startswith(b"\xff\xfe\x00\x00") or source_xml.startswith(b"<\x00\x00\x00"):
        unit_width, byte_order = 4, "little"
    elif source_xml.startswith(b"\x00\x00\xfe\xff") or source_xml.startswith(b"\x00\x00\x00<"):
        unit_width, byte_order = 4, "big"
    elif source_xml.startswith(b"\xff\xfe") or source_xml.startswith(b"<\x00"):
        unit_width, byte_order = 2, "little"
    elif source_xml.startswith(b"\xfe\xff") or source_xml.startswith(b"\x00<"):
        unit_width, byte_order = 2, "big"
    else:
        unit_width, byte_order = 1, "little"

    def ascii_token(value: str) -> bytes:
        return ord(value).to_bytes(unit_width, byte_order)

    pending_namespaces: list[tuple[str, str | None]] = []
    scopes: list[dict[str, str | None]] = [{"xml": "http://www.w3.org/XML/1998/namespace"}]
    frames: list[dict] = []
    spans: list[dict] = []
    declared_encoding: list[str | None] = [None]

    def scan_tag_end(start: int) -> int:
        quote_token: bytes | None = None
        for index in range(start, len(source_xml), unit_width):
            token = source_xml[index:index + unit_width]
            if len(token) != unit_width:
                break
            if quote_token is not None:
                if token == quote_token:
                    quote_token = None
                continue
            if token in {ascii_token("\""), ascii_token("'")}:
                quote_token = token
            elif token == ascii_token(">"):
                return index + unit_width - 1
        raise ValueError("unterminated XML tag")

    def empty_tag(start: int, tag_end: int) -> bool:
        before_close = source_xml[start:tag_end + 1 - unit_width]
        units = [before_close[index:index + unit_width] for index in range(0, len(before_close), unit_width)]
        whitespace = {ascii_token(character) for character in " \t\r\n"}
        while units and units[-1] in whitespace:
            units.pop()
        return bool(units and units[-1] == ascii_token("/"))

    def namespace_start(prefix: str | None, namespace: str | None) -> None:
        pending_namespaces.append((prefix or "", namespace))

    def element_start(_name: str, _attributes: dict) -> None:
        start = parser.CurrentByteIndex
        scope = dict(scopes[-1])
        local_declarations = tuple(pending_namespaces)
        for prefix, namespace in local_declarations:
            if namespace is None:
                scope.pop(prefix, None)
            else:
                scope[prefix] = namespace
        pending_namespaces.clear()
        tag_end = scan_tag_end(start)
        is_empty = empty_tag(start, tag_end)
        frame = {
            "start": start,
            "tag_end": tag_end,
            "is_empty": is_empty,
            "scope": scope,
            "local_declarations": local_declarations,
        }
        frames.append(frame)
        spans.append(frame)
        scopes.append(scope)

    def element_end(_name: str) -> None:
        frame = frames.pop()
        if frame["is_empty"]:
            frame["end"] = frame["tag_end"] + 1
        else:
            frame["end"] = scan_tag_end(parser.CurrentByteIndex) + 1
        scopes.pop()

    def xml_declaration(_version: str, encoding: str | None, _standalone: int) -> None:
        declared_encoding[0] = encoding

    parser.StartNamespaceDeclHandler = namespace_start
    parser.StartElementHandler = element_start
    parser.EndElementHandler = element_end
    parser.XmlDeclHandler = xml_declaration
    parser.Parse(source_xml, True)

    if frames:
        raise ValueError("unclosed XML element while preparing C14N source spans")
    if source_xml.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    elif source_xml.startswith(b"\xff\xfe\x00\x00"):
        encoding = "utf-32-le"
    elif source_xml.startswith(b"\x00\x00\xfe\xff"):
        encoding = "utf-32-be"
    elif source_xml.startswith(b"\xff\xfe") or source_xml.startswith(b"<\x00"):
        encoding = "utf-16-le"
    elif source_xml.startswith(b"\xfe\xff") or source_xml.startswith(b"\x00<"):
        encoding = "utf-16-be"
    else:
        encoding = declared_encoding[0] or "utf-8"
    return spans, encoding


def _canonical_source_subtree(span: Mapping[str, object], source_xml: bytes, encoding: str) -> str:
    start, end = int(span["start"]), int(span["end"])
    fragment = source_xml[start:end].decode(encoding)
    # An element's own start tag may inherit namespaces from any number of
    # ancestors.  Materialize only the missing declarations on the extracted
    # subtree root; C14N then removes declarations not visibly used below it.
    local_prefixes = {prefix for prefix, _ in span["local_declarations"]}
    inherited = [
        (prefix, namespace)
        for prefix, namespace in span["scope"].items()
        if prefix not in local_prefixes and prefix != "xml" and namespace is not None
    ]
    if inherited:
        quote_char: str | None = None
        opening_end = -1
        for index, character in enumerate(fragment):
            if quote_char is not None:
                if character == quote_char:
                    quote_char = None
                continue
            if character in {"\"", "'"}:
                quote_char = character
            elif character == ">":
                opening_end = index
                break
        if opening_end < 0:
            raise ValueError("unterminated extracted XML subtree")
        insertion = opening_end
        while insertion > 0 and fragment[insertion - 1].isspace():
            insertion -= 1
        if insertion > 0 and fragment[insertion - 1] == "/":
            insertion -= 1
        declarations = "".join(
            f" xmlns{':' + prefix if prefix else ''}={quoteattr(namespace)}"
            for prefix, namespace in sorted(inherited)
        )
        fragment = fragment[:insertion] + declarations + fragment[insertion:]
    return ET.canonicalize(xml_data=fragment, with_comments=False, strip_text=False)


def _source_paths(root: ET.Element) -> tuple[dict[ET.Element, ET.Element], dict[ET.Element, str]]:
    parents: dict[ET.Element, ET.Element] = {}
    paths: dict[ET.Element, str] = {}

    def walk(parent: ET.Element, path: str) -> None:
        counters: dict[str, int] = {}
        for child in parent:
            name = _local_name(child)
            counters[name] = counters.get(name, 0) + 1
            eid = child.get("eId")
            if eid:
                segment = f"{name}[@eId={json.dumps(eid, ensure_ascii=False)}]"
            else:
                segment = f"{name}[{counters[name]}]"
            child_path = f"{path}/{segment}"
            parents[child] = parent
            paths[child] = child_path
            walk(child, child_path)

    root_name = _local_name(root)
    paths[root] = f"/{root_name}[1]"
    walk(root, paths[root])
    return parents, paths


def _is_inside(element: ET.Element, ancestor: ET.Element, parents: Mapping[ET.Element, ET.Element]) -> bool:
    current = element
    while current in parents:
        current = parents[current]
        if current is ancestor:
            return True
    return False


def _nearest_resource(
    element: ET.Element,
    *,
    parents: Mapping[ET.Element, ET.Element],
    resource_iris: Mapping[ET.Element, URIRef],
    default: URIRef,
) -> URIRef:
    current = element
    while current in parents:
        current = parents[current]
        if current in resource_iris:
            return resource_iris[current]
    return default


def _report_base(source_sha256: str, resolver_version: str) -> dict:
    return {
        "contract_version": REFERENCE_CONTRACT_VERSION,
        "transform_contract_version": TRANSFORM_CONTRACT_VERSION,
        "source_sha256": source_sha256,
        "source_format": "AKN XML exact bytes",
        "resolver_version": resolver_version,
        "expression_set_completeness": "not-asserted",
        "reference_outcomes": [],
        "resource_identities": [],
        "source_evidence": {},
        "diagnostics": [],
    }


def _raise_transform_error(
    message: str,
    *,
    report: dict,
    code: str,
    evidence: Mapping[str, object] | None = None,
) -> None:
    report.setdefault("diagnostics", []).append(
        {"code": code, "message": message, "evidence": dict(evidence or {})}
    )
    raise DebateTransformError(message, report)


def _candidate_outcome(
    *,
    target_matches: list[URIRef],
    reason_unresolved: str = "no-unique-existing-owner-match",
    evidence: Mapping[str, object] | None = None,
) -> tuple[str, dict]:
    extra = dict(evidence or {})
    if len(target_matches) == 1:
        extra["resolution_method"] = extra.get("resolution_method", "exact-owner-registry-key")
        return "resolved", {"target_iri": str(target_matches[0]), "resolution_evidence": extra}
    if len(target_matches) > 1:
        extra["reason"] = "ambiguous-existing-owner-candidates"
        return "unresolved", {
            "reason": "ambiguous-existing-owner-candidates",
            "candidate_iris": sorted(str(candidate) for candidate in target_matches),
            "resolution_evidence": extra,
        }
    return "unresolved", {"reason": reason_unresolved, "resolution_evidence": extra}


def _source_author_path(raw: str) -> tuple[str, list[str]] | None:
    """Parse only the reviewed official HouseTerm/Committee author path forms."""

    if "?" in raw or "#" in raw:
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.query or parsed.fragment or parsed.username is not None or parsed.password is not None:
        return None
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or parsed.netloc != "data.oireachtas.ie":
            return None
        try:
            if parsed.port is not None:
                return None
        except ValueError:
            return None
        path = parsed.path
    else:
        path = parsed.path
    if path.startswith("/"):
        segments = path[1:].split("/")
    else:
        segments = path.split("/")
    if not segments or any(not item or item in {".", ".."} for item in segments):
        return None
    if any(re.search(r"%(?![0-9A-Fa-f]{2})", item) for item in segments):
        return None
    return path, segments


def _sort_report(report: dict) -> None:
    report["reference_outcomes"].sort(
        key=lambda row: (
            row.get("expression_iri", ""),
            row.get("source_node_iri", ""),
            row.get("source_attribute_qname", ""),
            "" if row.get("raw_reference") is None else str(row["raw_reference"]),
            row.get("slot", ""),
            row.get("source_pointer", ""),
        )
    )
    report["resource_identities"].sort(key=lambda row: (row["source_node_iri"], row["source_pointer"]))
    report["diagnostics"].sort(key=lambda row: (row.get("code", ""), _canonical_json(row.get("evidence", {}))))


def inspect_debate_source_identity(source_xml: bytes) -> dict[str, str]:
    """Read only the approved Work/Expression identity fields from exact bytes.

    This small preflight supports supplied-batch duplicate and Expression-set
    checks, and permits Core State's exact-hash skip gate to identify its row.
    It is not source or RDF validation: every non-skipped input still passes
    through :func:`transform_debate` and the Tranche 2/3 validators.
    """
    if not isinstance(source_xml, bytes):
        raise TypeError("source_xml must be the exact AKN XML bytes")
    root = ET.fromstring(source_xml)
    if _local_name(root) != "akomaNtoso":
        raise ValueError("AKN XML root must be akomaNtoso")
    debates = _children_named(root, "debate")
    if len(debates) != 1:
        raise ValueError("AKN source must contain exactly one direct debate element")
    metas = _children_named(debates[0], "meta")
    if len(metas) != 1:
        raise ValueError("AKN debate must contain exactly one meta element")
    identifications = _children_named(metas[0], "identification")
    if len(identifications) != 1:
        raise ValueError("AKN meta must contain exactly one identification element")
    works = _children_named(identifications[0], "FRBRWork")
    expressions = _children_named(identifications[0], "FRBRExpression")
    if len(works) != 1 or len(expressions) != 1:
        raise ValueError("AKN identification must contain exactly one FRBRWork and FRBRExpression")
    work_uris = _children_named(works[0], "FRBRuri")
    expression_uris = _children_named(expressions[0], "FRBRuri")
    if len(work_uris) != 1 or len(expression_uris) != 1:
        raise ValueError("each FRBR level must contain exactly one FRBRuri")
    source_work_uri = _required_value_attribute(work_uris[0], "FRBRWork/FRBRuri")
    source_expression_uri = _required_value_attribute(
        expression_uris[0], "FRBRExpression/FRBRuri")
    work_iri, _work_path, _work_segments = _canonical_akn_iri(
        source_work_uri, "FRBRWork/FRBRuri/@value")
    expression_iri, _expression_path, _expression_segments = _canonical_akn_iri(
        source_expression_uri, "FRBRExpression/FRBRuri/@value")
    if work_iri == expression_iri:
        raise ValueError("FRBRWork and FRBRExpression canonicalize to the same public IRI")
    return {
        "work_iri": work_iri,
        "expression_iri": expression_iri,
        "source_work_uri": source_work_uri,
        "source_expression_uri": source_expression_uri,
    }


def transform_debate(
    source_xml: bytes,
    *,
    resolver: DebateReferenceResolver | None = None,
    known_expression_source_uris: Iterable[str] | None = None,
    resolver_version: str | None = None,
) -> DebateTransformResult:
    """Transform one exact AKN XML byte string into its Work-owned RDF graph.

    ``known_expression_source_uris`` is an optional external discovery result
    scoped to this Work, containing exact parsed ``FRBRExpression/FRBRuri``
    source values.  The current file is always included.  Supplying more than
    one distinct canonical Expression fails closed; omitting the parameter
    does *not* assert global Expression completeness.

    The returned graph is the Work graph content (not a Dataset or publication
    action).  ``graph_iri`` is the approved replaceable named-graph key.
    ``reference_report_json`` is source-hash-linked deterministic UTF-8 JSON.
    Failures raise :class:`DebateTransformError`, whose ``reference_report_json``
    retains the exact source hash and the failure evidence available so far.
    """

    if not isinstance(source_xml, bytes):
        raise TypeError("source_xml must be the exact AKN XML bytes")
    source_sha256 = hashlib.sha256(source_xml).hexdigest()
    try:
        resolver_version_value = _resolver_version(resolver, resolver_version)
    except ValueError as error:
        report = _report_base(source_sha256, "invalid-resolver-version")
        _raise_transform_error(str(error), report=report, code="invalid-resolver-version")
    report = _report_base(source_sha256, resolver_version_value)

    try:
        root = ET.fromstring(source_xml)
    except (ET.ParseError, ValueError) as error:
        _raise_transform_error(
            f"invalid AKN XML: {error}",
            report=report,
            code="xml-parse-error",
            evidence={"error": str(error)},
        )
    if _local_name(root) != "akomaNtoso":
        _raise_transform_error(
            "AKN XML root must be akomaNtoso",
            report=report,
            code="unexpected-root",
            evidence={"root_qname": _expanded_qname(root)},
        )
    debates = _children_named(root, "debate")
    if len(debates) != 1:
        _raise_transform_error(
            "AKN source must contain exactly one direct debate element",
            report=report,
            code="debate-cardinality",
            evidence={"count": len(debates)},
        )
    debate = debates[0]
    metas = _children_named(debate, "meta")
    bodies = _children_named(debate, "debateBody")
    if len(metas) != 1 or len(bodies) != 1:
        _raise_transform_error(
            "AKN debate must contain exactly one meta and one debateBody",
            report=report,
            code="debate-structure-cardinality",
            evidence={"meta_count": len(metas), "debate_body_count": len(bodies)},
        )
    meta, debate_body = metas[0], bodies[0]
    identifications = _children_named(meta, "identification")
    if len(identifications) != 1:
        _raise_transform_error(
            "AKN meta must contain exactly one identification element",
            report=report,
            code="identification-cardinality",
            evidence={"count": len(identifications)},
        )
    identification = identifications[0]
    works = _children_named(identification, "FRBRWork")
    expressions = _children_named(identification, "FRBRExpression")
    if len(works) != 1 or len(expressions) != 1:
        _raise_transform_error(
            "AKN identification must contain exactly one FRBRWork and FRBRExpression",
            report=report,
            code="frbr-level-cardinality",
            evidence={"work_count": len(works), "expression_count": len(expressions)},
        )
    work_element, expression_element = works[0], expressions[0]

    try:
        work_uri_element, = _children_named(work_element, "FRBRuri")
        expression_uri_element, = _children_named(expression_element, "FRBRuri")
        source_work_uri = _required_value_attribute(work_uri_element, "FRBRWork/FRBRuri")
        source_expression_uri = _required_value_attribute(expression_uri_element, "FRBRExpression/FRBRuri")
        work_iri_text, work_path, work_segments = _canonical_akn_iri(source_work_uri, "FRBRWork/FRBRuri/@value")
        expression_iri_text, _expression_path, _expression_segments = _canonical_akn_iri(
            source_expression_uri, "FRBRExpression/FRBRuri/@value"
        )
    except (ValueError, TypeError) as error:
        _raise_transform_error(
            str(error),
            report=report,
            code="frbr-identity-invalid",
            evidence={
                "work_frbruri_values": [element.get("value") for element in _children_named(work_element, "FRBRuri")],
                "expression_frbruri_values": [element.get("value") for element in _children_named(expression_element, "FRBRuri")],
            },
        )
    if work_iri_text == expression_iri_text:
        _raise_transform_error(
            "FRBRWork and FRBRExpression canonicalize to the same public IRI",
            report=report,
            code="work-expression-identity-collision",
            evidence={
                "work_frbruri": source_work_uri,
                "expression_frbruri": source_expression_uri,
                "canonical_iri": work_iri_text,
            },
        )
    graph_iri_text = _debate_graph_iri(work_iri_text)
    report.update(
        {
            "work_iri": work_iri_text,
            "expression_iri": expression_iri_text,
            "graph_iri": graph_iri_text,
            "source_identity": {
                "work_frbruri": source_work_uri,
                "expression_frbruri": source_expression_uri,
            },
        }
    )

    known_values: dict[str, set[str]] = {}
    known_iris: dict[str, str] = {}
    if isinstance(known_expression_source_uris, str):
        known_source_values: Iterable[str] = (known_expression_source_uris,)
    else:
        known_source_values = known_expression_source_uris or ()
    for source_value in [source_expression_uri, *known_source_values]:
        try:
            canonical, _path, _segments = _canonical_akn_iri(source_value, "known FRBRExpression/FRBRuri")
        except (ValueError, TypeError) as error:
            _raise_transform_error(
                str(error),
                report=report,
                code="known-expression-identity-invalid",
                evidence={"source_expression_uri": source_value},
            )
        known_values.setdefault(canonical, set()).add(source_value)
        known_iris[canonical] = canonical
    expression_set = sorted(known_iris)
    report["known_expression_iris"] = expression_set
    if len(expression_set) > 1:
        _raise_transform_error(
            "multiple known Expressions for one Work; refusing a partial Work graph",
            report=report,
            code="known-multiple-expressions",
            evidence={
                "known_expression_iris": expression_set,
                "source_values_by_iri": {key: sorted(value) for key, value in sorted(known_values.items())},
            },
        )
    conflicting_expression_evidence = {
        key: sorted(values) for key, values in known_values.items() if len(values) > 1
    }
    if conflicting_expression_evidence:
        _raise_transform_error(
            "distinct source FRBR Expression values canonicalize to the same identity",
            report=report,
            code="expression-identity-evidence-conflict",
            evidence={"source_values_by_iri": conflicting_expression_evidence},
        )

    parents, source_paths = _source_paths(root)
    try:
        spans, source_encoding = _parse_spans(source_xml)
    except (expat.ExpatError, LookupError, UnicodeError, ValueError) as error:
        _raise_transform_error(
            f"could not prepare exact XML subtree identities: {error}",
            report=report,
            code="xml-source-span-error",
            evidence={"error": str(error)},
        )
    elements = list(root.iter())
    if len(spans) != len(elements):
        _raise_transform_error(
            "XML source-span element sequence does not match parsed AKN tree",
            report=report,
            code="xml-source-span-mismatch",
            evidence={"span_count": len(spans), "element_count": len(elements)},
        )
    spans_by_element = dict(zip(elements, spans))

    # The eId index is expression-wide and covers every XML element, including
    # elements that do not produce RDF resources.
    eid_nodes: dict[str, list[ET.Element]] = {}
    for element in elements:
        eid = element.get("eId")
        if eid:
            eid_nodes.setdefault(eid, []).append(element)
    duplicates = {
        eid: [source_paths[node] for node in nodes]
        for eid, nodes in sorted(eid_nodes.items())
        if len(nodes) > 1
    }
    if duplicates:
        _raise_transform_error(
            "duplicate decoded eId in source Expression",
            report=report,
            code="duplicate-eid",
            evidence={"duplicate_eids": duplicates},
        )
    eid_index = {eid: nodes[0] for eid, nodes in eid_nodes.items()}

    expression_iri = URIRef(expression_iri_text)
    work_iri = URIRef(work_iri_text)
    resource_iris: dict[ET.Element, URIRef] = {}
    identity_rows: list[dict] = []

    # Skip all descendants of rollCall when assigning Debate-owned resources.
    roll_calls = [node for node in debate_body.iter() if node is not debate_body and _local_name(node) == "rollCall"]
    mapped_addressables = [
        node
        for node in debate_body.iter()
        if node is not debate_body
        and _local_name(node) in ADDRESSABLE_NAMES
        and not any(_is_inside(node, roll_call, parents) for roll_call in roll_calls)
    ]
    addressable_set = set(mapped_addressables)

    def assign_addressables(node: ET.Element, container_iri: URIRef) -> None:
        for child in node:
            if child not in addressable_set:
                assign_addressables(child, container_iri)
                continue
            source_eid = child.get("eId")
            fallback_evidence = None
            if source_eid:
                public_iri = URIRef(f"{expression_iri}/eid/e-{_encode_component(source_eid)}")
            else:
                span = spans_by_element[child]
                try:
                    canonical_subtree = _canonical_source_subtree(span, source_xml, source_encoding)
                except (LookupError, UnicodeError, ET.ParseError, ValueError) as error:
                    _raise_transform_error(
                        f"could not canonicalize missing-eId resource subtree: {error}",
                        report=report,
                        code="fallback-canonicalization-error",
                        evidence={"source_pointer": source_paths[child], "expanded_qname": _expanded_qname(child)},
                    )
                qname = _expanded_qname(child)
                digest_input = (
                    b"akn-eid-fallback-v1\0"
                    + str(container_iri).encode("utf-8")
                    + b"\0"
                    + qname.encode("utf-8")
                    + b"\0"
                    + canonical_subtree.encode("utf-8")
                )
                digest = hashlib.sha256(digest_input).hexdigest()
                public_iri = URIRef(f"{container_iri}/fallback/fb-{digest}")
                fallback_evidence = {
                    "container_iri": str(container_iri),
                    "expanded_qname": qname,
                    "canonical_subtree_sha256": hashlib.sha256(canonical_subtree.encode("utf-8")).hexdigest(),
                    "fallback_digest": digest,
                }
            if public_iri in resource_iris.values():
                prior = next(element for element, candidate in resource_iris.items() if candidate == public_iri)
                _raise_transform_error(
                    "duplicate proposed Debate resource IRI; refusing position-based disambiguation",
                    report=report,
                    code="duplicate-proposed-resource-iri",
                    evidence={
                        "resource_iri": str(public_iri),
                        "source_pointers": sorted((source_paths[prior], source_paths[child])),
                    },
                )
            resource_iris[child] = public_iri
            identity_row = {
                "source_node_iri": str(public_iri),
                "source_pointer": source_paths[child],
                "expanded_qname": _expanded_qname(child),
                "source_eid": source_eid,
                "identity_kind": "fallback" if fallback_evidence is not None else "eid",
            }
            if fallback_evidence is not None:
                identity_row["fallback_evidence"] = fallback_evidence
            identity_rows.append(identity_row)
            assign_addressables(child, public_iri)

    assign_addressables(debate_body, expression_iri)
    report["resource_identities"] = identity_rows

    # All reference rows are tied to exact source bytes and carry a source
    # pointer in addition to the mapped source resource IRI.
    def add_outcome(
        *,
        node: ET.Element,
        attribute: str,
        raw: str | None,
        slot: str,
        status: str,
        source_node_iri: URIRef,
        reason: str | None = None,
        target_iri: URIRef | str | None = None,
        candidate_iris: Iterable[URIRef | str] | None = None,
        resolution_evidence: Mapping[str, object] | None = None,
    ) -> None:
        if status not in {"resolved", "unresolved", "malformed", "absent"}:
            raise AssertionError(f"unsupported reference outcome status {status!r}")
        row = {
            "contract_version": REFERENCE_CONTRACT_VERSION,
            "source_sha256": source_sha256,
            "work_iri": work_iri_text,
            "expression_iri": expression_iri_text,
            "source_node_iri": str(source_node_iri),
            "source_attribute_qname": attribute,
            "raw_reference": raw,
            "status": status,
            "slot": slot,
            "source_pointer": source_paths.get(node, "/"),
            "source_eid": node.get("eId"),
        }
        if reason is not None:
            row["reason"] = reason
        if target_iri is not None:
            row["target_iri"] = str(target_iri)
        candidates = sorted({str(value) for value in (candidate_iris or ())})
        if candidates:
            row["candidate_iris"] = candidates
        if resolution_evidence:
            row["resolution_evidence"] = dict(resolution_evidence)
        report["reference_outcomes"].append(row)

    def node_subject(node: ET.Element, default: URIRef = expression_iri) -> URIRef:
        return resource_iris.get(node) or _nearest_resource(
            node, parents=parents, resource_iris=resource_iris, default=default
        )

    def resolve_owner(
        *,
        node: ET.Element,
        attribute: str,
        slot: str,
        raw: str | None,
        source_node_iri: URIRef,
        resolver_call,
        lookup_key: str | None,
        missing_reason: str,
        evidence: Mapping[str, object] | None = None,
    ) -> URIRef | None:
        if raw is None:
            add_outcome(
                node=node,
                attribute=attribute,
                raw=None,
                slot=slot,
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=source_node_iri,
            )
            return None
        if resolver is None or lookup_key is None:
            matches: list[URIRef] = []
        else:
            matches = _matches(resolver_call(lookup_key), slot)
        status, resolution = _candidate_outcome(
            target_matches=matches,
            reason_unresolved=missing_reason,
            evidence={
                **dict(evidence or {}),
                "resolver_version": resolver_version_value,
                "lookup_key": lookup_key,
            },
        )
        add_outcome(
            node=node,
            attribute=attribute,
            raw=raw,
            slot=slot,
            status=status,
            reason=resolution.get("reason"),
            target_iri=resolution.get("target_iri"),
            candidate_iris=resolution.get("candidate_iris"),
            resolution_evidence=resolution.get("resolution_evidence"),
            source_node_iri=source_node_iri,
        )
        return matches[0] if len(matches) == 1 else None

    # The report itself begins with the exact parsed identity evidence.  Source
    # URI spellings are retained here; public IRIs are separate canonical keys.
    work_dates = [
        child for child in _children_named(work_element, "FRBRdate")
        if child.get("name") == "#generation"
    ]
    if len(work_dates) != 1:
        _raise_transform_error(
            "FRBRWork must contain exactly one #generation FRBRdate",
            report=report,
            code="work-date-cardinality",
            evidence={"generation_dates": [date.get("date") for date in work_dates]},
        )
    source_date = work_dates[0].get("date")
    try:
        debate_date = midnight(source_date)
    except ValueError as error:
        _raise_transform_error(
            str(error),
            report=report,
            code="work-date-invalid",
            evidence={"source_date": source_date},
        )

    work_names = _children_named(work_element, "FRBRname")
    work_name_values = [name.get("value") for name in work_names]
    missing_name_values = [
        name for name in work_names if name.get("value") in (None, "")
    ]
    if missing_name_values:
        _raise_transform_error(
            "FRBRWork/FRBRname must have a non-empty @value when present",
            report=report,
            code="work-type-missing-value",
            evidence={
                "source_pointers": [source_paths[name] for name in missing_name_values],
                "frbr_name_values": work_name_values,
            },
        )

    graph = Graph(identifier=URIRef(graph_iri_text))
    graph.bind("oir", OIR)
    graph.bind("eli-dl", ELIDL)
    graph.add((work_iri, RDF.type, OIR.DebateRecord))
    graph.add((work_iri, OIR.debateDate, debate_date))
    for value in work_name_values:
        if value is not None:
            graph.add((work_iri, OIR.debateType, string(value)))
    if len(work_names) > 1:
        report["diagnostics"].append(
            {
                "code": "sitting-source-type-ambiguous",
                "message": "multiple FRBRWork/FRBRname source signals prevent sitting emission",
                "evidence": {"frbr_names": work_name_values},
            }
        )

    language_nodes = _children_named(expression_element, "FRBRlanguage")
    for language_node in language_nodes:
        language = language_node.get("language")
        if language is None:
            _raise_transform_error(
                "FRBRExpression/FRBRlanguage must have @language when the element is present",
                report=report,
                code="expression-language-missing",
                evidence={"source_pointer": source_paths[language_node]},
            )
        graph.add((expression_iri, OIR.expressionLanguageCode, string(language)))
    graph.add((work_iri, OIR.hasExpression, expression_iri))
    graph.add((expression_iri, RDF.type, OIR.DebateExpression))

    path_is_writtens = "writtens" in work_segments
    name_signal = work_name_values[0] if len(work_names) == 1 else None
    sitting_eligible = False
    sitting_reason = None
    if len(work_names) > 1:
        sitting_reason = "multiple-FRBRname-signals"
    elif path_is_writtens:
        if name_signal not in (None, "writtens"):
            sitting_reason = "work-path-and-FRBRname-disagree"
        else:
            sitting_reason = "work-identifies-writtens-publication"
    elif name_signal == "writtens":
        sitting_reason = "work-path-and-FRBRname-disagree"
    elif name_signal not in (None, "debate"):
        sitting_reason = "unreviewed-FRBRname-type"
    else:
        sitting_eligible = True
    if sitting_eligible:
        sitting = URIRef(f"{work_iri_text}#sitting")
        graph.add((sitting, RDF.type, OIR.DebateSitting))
        graph.add((sitting, OIR.producedRecord, work_iri))
        graph.add((sitting, ELIDL.activity_date, date_literal(source_date)))
    else:
        report["diagnostics"].append(
            {
                "code": "sitting-not-emitted",
                "message": "source type does not establish an eligible actual sitting",
                "evidence": {
                    "work_path": work_path,
                    "work_name_values": work_name_values,
                    "reason": sitting_reason,
                },
            }
        )

    # Structural resources and direct-child containment.  Speech/question/
    # summary prose, headings, and all other source text are never read into RDF.
    for node in mapped_addressables:
        subject = resource_iris[node]
        name = _local_name(node)
        if name == "debateSection":
            graph.add((subject, RDF.type, OIR.DebateSection))
            if node.get("name") is not None:
                graph.add((subject, OIR.sectionName, string(node.get("name"))))
            if node.get("name") == "division":
                graph.add((subject, RDF.type, OIR.Division))
        elif name == "speech":
            graph.add((subject, RDF.type, OIR.Speech))
        elif name == "summary":
            graph.add((subject, RDF.type, OIR.Summary))
        elif name == "question":
            graph.add((subject, RDF.type, OIR.ParliamentaryQuestion))

    # Mixed-kind source ordinals are consecutive among immediate addressable
    # siblings in each source element's own child scope.
    for containing_node in debate_body.iter():
        addressable_children = [child for child in containing_node if child in addressable_set]
        for ordinal, child in enumerate(addressable_children, start=1):
            graph.add((resource_iris[child], OIR.sourceOrdinal, integer(ordinal)))

    for section in (node for node in mapped_addressables if _local_name(node) == "debateSection"):
        section_iri = resource_iris[section]
        parent = parents.get(section)
        for child in section:
            if child not in addressable_set:
                continue
            child_name = _local_name(child)
            child_iri = resource_iris[child]
            if child_name == "debateSection":
                if child.get("name") == "division":
                    graph.add((section_iri, OIR.hasDivision, child_iri))
                else:
                    graph.add((section_iri, OIR.hasSubSection, child_iri))
            elif child_name == "speech":
                graph.add((section_iri, OIR.hasSpeech, child_iri))
            elif child_name == "summary":
                graph.add((section_iri, OIR.hasSummary, child_iri))
            elif child_name == "question":
                graph.add((section_iri, OIR.hasQuestion, child_iri))
        if parent is debate_body:
            graph.add((expression_iri, OIR.expressionHasSection, section_iri))
            graph.add((work_iri, OIR.hasSection, section_iri))

    # AKN speech/@by and question/@by resolve through a local TLCPerson eId,
    # then through that TLCPerson's exact href in the Member owner registry.
    def resolve_person_reference(
        *,
        node: ET.Element,
        raw: str | None,
        slot: str,
        predicate: URIRef,
        owner_subject: URIRef,
        source_node: URIRef,
        speech_for_participation: bool = False,
    ) -> URIRef | None:
        classification, target_eid = _local_fragment(raw)
        attribute = "by" if slot.endswith("@by") else "refersTo"
        if classification == "absent":
            add_outcome(
                node=node,
                attribute=attribute,
                raw=None,
                slot=slot,
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=source_node,
            )
            return None
        if classification == "placeholder":
            add_outcome(
                node=node,
                attribute=attribute,
                raw=raw,
                slot=slot,
                status="unresolved",
                reason="source-placeholder",
                source_node_iri=source_node,
                resolution_evidence={"resolution_path": "TLCPerson eId -> exact Member owner href"},
            )
            return None
        if classification == "malformed":
            add_outcome(
                node=node,
                attribute=attribute,
                raw=raw,
                slot=slot,
                status="malformed",
                reason="not-a-reviewed-local-NCName-fragment",
                source_node_iri=source_node,
            )
            return None
        target = eid_index.get(target_eid)
        if target is None:
            add_outcome(
                node=node,
                attribute=attribute,
                raw=raw,
                slot=slot,
                status="unresolved",
                reason="unknown-local-eid",
                source_node_iri=source_node,
                resolution_evidence={"target_eid": target_eid},
            )
            return None
        if _local_name(target) != "TLCPerson":
            add_outcome(
                node=node,
                attribute=attribute,
                raw=raw,
                slot=slot,
                status="unresolved",
                reason="local-eid-is-not-TLCPerson",
                source_node_iri=source_node,
                resolution_evidence={
                    "target_eid": target_eid,
                    "target_qname": _expanded_qname(target),
                    "target_pointer": source_paths[target],
                },
            )
            return None
        href = target.get("href")
        if href is None or href == "":
            add_outcome(
                node=node,
                attribute=attribute,
                raw=raw,
                slot=slot,
                status="unresolved",
                reason="TLCPerson-has-no-owner-href",
                source_node_iri=source_node,
                resolution_evidence={"target_eid": target_eid, "target_pointer": source_paths[target]},
            )
            return None
        member = resolve_owner(
            node=node,
            attribute=attribute,
            slot=slot,
            raw=raw,
            source_node_iri=source_node,
            resolver_call=resolver.resolve_member if resolver is not None else None,
            lookup_key=href,
            missing_reason="no-existing-Member-owner-match",
            evidence={
                "resolution_path": "local TLCPerson eId -> exact TLCPerson/@href -> existing Member",
                "target_eid": target_eid,
                "target_pointer": source_paths[target],
                "tlc_person_href": href,
            },
        )
        if member is not None:
            graph.add((owner_subject, predicate, member))
            if speech_for_participation:
                participation = URIRef(f"{owner_subject}#participation")
                graph.add((owner_subject, OIR.hasSpeechParticipation, participation))
                graph.add((participation, RDF.type, ELIDL.Participation))
                graph.add((participation, ELIDL.had_participant_person, member))
        return member

    for speech in (node for node in mapped_addressables if _local_name(node) == "speech"):
        speech_iri = resource_iris[speech]
        resolve_person_reference(
            node=speech,
            raw=speech.get("by"),
            slot="speech/@by",
            predicate=OIR.speaker,
            owner_subject=speech_iri,
            source_node=speech_iri,
            speech_for_participation=True,
        )
        role_reference = speech.get("as")
        classification, role_eid = _local_fragment(role_reference)
        if classification == "absent":
            add_outcome(
                node=speech,
                attribute="as",
                raw=None,
                slot="speech/@as->eli-dl:participation_role",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=speech_iri,
            )
        elif classification == "malformed":
            add_outcome(
                node=speech,
                attribute="as",
                raw=role_reference,
                slot="speech/@as->eli-dl:participation_role",
                status="malformed",
                reason="not-a-reviewed-local-NCName-fragment",
                source_node_iri=speech_iri,
            )
        elif classification == "placeholder":
            add_outcome(
                node=speech,
                attribute="as",
                raw=role_reference,
                slot="speech/@as->eli-dl:participation_role",
                status="unresolved",
                reason="source-placeholder",
                source_node_iri=speech_iri,
            )
        else:
            source_role = eid_index.get(role_eid)
            role_evidence: dict[str, object] = {"target_eid": role_eid}
            if source_role is None:
                reason = "unknown-local-eid"
            elif _local_name(source_role) != "TLCRole":
                reason = "local-eid-is-not-TLCRole"
                role_evidence["target_qname"] = _expanded_qname(source_role)
                role_evidence["target_pointer"] = source_paths[source_role]
            else:
                reason = "ParticipationRole-crosswalk-not-configured-in-Tranche-2"
                role_evidence["tlc_role_href"] = source_role.get("href")
                role_evidence["target_pointer"] = source_paths[source_role]
            add_outcome(
                node=speech,
                attribute="as",
                raw=role_reference,
                slot="speech/@as->eli-dl:participation_role",
                status="unresolved",
                reason=reason,
                source_node_iri=speech_iri,
                resolution_evidence=role_evidence,
            )

    for question in (node for node in mapped_addressables if _local_name(node) == "question"):
        question_iri = resource_iris[question]
        resolve_person_reference(
            node=question,
            raw=question.get("by"),
            slot="question/@by",
            predicate=OIR.askedBy,
            owner_subject=question_iri,
            source_node=question_iri,
        )
        raw_to = question.get("to")
        to_status, to_eid = _local_fragment(raw_to)
        if to_status == "absent":
            add_outcome(
                node=question,
                attribute="to",
                raw=None,
                slot="question/@to->directedTo/directedToOffice",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=question_iri,
            )
        elif to_status == "malformed":
            add_outcome(
                node=question,
                attribute="to",
                raw=raw_to,
                slot="question/@to->directedTo/directedToOffice",
                status="malformed",
                reason="not-a-reviewed-local-NCName-fragment",
                source_node_iri=question_iri,
            )
        elif to_status == "placeholder":
            add_outcome(
                node=question,
                attribute="to",
                raw=raw_to,
                slot="question/@to->directedTo/directedToOffice",
                status="unresolved",
                reason="source-placeholder",
                source_node_iri=question_iri,
            )
        else:
            role = eid_index.get(to_eid)
            evidence: dict[str, object] = {"target_eid": to_eid, "resolution_rule": "recipient-owner-crosswalk-deferred"}
            if role is not None:
                evidence["target_qname"] = _expanded_qname(role)
                evidence["target_pointer"] = source_paths[role]
                if _local_name(role) == "TLCRole":
                    evidence["tlc_role_href"] = role.get("href")
            add_outcome(
                node=question,
                attribute="to",
                raw=raw_to,
                slot="question/@to->directedTo/directedToOffice",
                status="unresolved",
                reason="question-recipient-resolution-deferred",
                source_node_iri=question_iri,
                resolution_evidence=evidence,
            )

    # Work hosts: Dáil/Seanad path mapping is approved only with the generic
    # #oireachtas author or an agreeing resolved HouseTerm. Committee identity
    # comes only from exact official author-href owner resolution.
    work_authors = _children_named(work_element, "FRBRauthor")
    if not work_authors:
        author_slots = [(work_element, None)]
    else:
        author_slots = [(author, author.get("href")) for author in work_authors]
    if len(work_authors) > 1:
        for author, raw_author in author_slots:
            for slot in ("FRBRWork/FRBRauthor/@href->recordOfHouseTerm", "FRBRWork/FRBRauthor/@href->recordOfBody"):
                add_outcome(
                    node=author,
                    attribute="href",
                    raw=raw_author,
                    slot=slot,
                    status="absent" if raw_author is None else "unresolved",
                    reason="optional-attribute-absent" if raw_author is None else "multiple-FRBRWork-authors",
                    source_node_iri=work_iri,
                )
    else:
        author, author_href = author_slots[0]
        author_source_iri = work_iri
        if author_href is None:
            add_outcome(
                node=author,
                attribute="href",
                raw=None,
                slot="FRBRWork/FRBRauthor/@href->recordOfHouseTerm",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=author_source_iri,
            )
            add_outcome(
                node=author,
                attribute="href",
                raw=None,
                slot="FRBRWork/FRBRauthor/@href->recordOfBody",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=author_source_iri,
            )
        else:
            author_path = _source_author_path(author_href)
            house_term: URIRef | None = None
            committee: URIRef | None = None
            term_lookup_kind = "not-a-numbered-HouseTerm-author-reference"
            if author_href == "#oireachtas":
                term_status = "unresolved"
                term_resolution = {"reason": "generic-Oireachtas-author-is-not-a-numbered-HouseTerm"}
            elif author_href.startswith("#"):
                author_fragment_status, _author_fragment = _local_fragment(author_href)
                if author_fragment_status == "valid":
                    term_status = "unresolved"
                    term_resolution = {"reason": "unreviewed-local-FRBRauthor-reference"}
                elif author_fragment_status == "placeholder":
                    term_status = "unresolved"
                    term_resolution = {"reason": "source-placeholder"}
                else:
                    term_status = "malformed"
                    term_resolution = {"reason": "malformed-FRBRauthor-fragment"}
            elif author_path is None:
                term_status = "malformed"
                term_resolution = {"reason": "malformed-or-unreviewed-FRBRauthor-href"}
            else:
                path, path_segments = author_path
                is_house_term = (
                    path_segments[:3] == ["ie", "oireachtas", "house"]
                    and len(path_segments) == 5
                    and path_segments[3] in {"dail", "seanad"}
                    and re.fullmatch(r"[1-9][0-9]*", path_segments[4]) is not None
                )
                if is_house_term:
                    term_lookup_kind = "HouseTerm"
                    matches = _matches(
                        resolver.resolve_house_term(author_href) if resolver is not None else None,
                        "HouseTerm",
                    )
                    term_status, term_resolution = _candidate_outcome(
                        target_matches=matches,
                        reason_unresolved="no-existing-HouseTerm-owner-match",
                        evidence={
                            "resolver_version": resolver_version_value,
                            "lookup_key": author_href,
                            "source_path": path,
                            "owner_kind": "HouseTerm",
                        },
                    )
                    if len(matches) == 1:
                        house_term = matches[0]
                else:
                    term_status = "unresolved"
                    term_resolution = {"reason": "FRBRauthor-href-does-not-identify-a-numbered-HouseTerm"}
            add_outcome(
                node=author,
                attribute="href",
                raw=author_href,
                slot="FRBRWork/FRBRauthor/@href->recordOfHouseTerm",
                status=term_status,
                reason=term_resolution.get("reason"),
                target_iri=term_resolution.get("target_iri"),
                candidate_iris=term_resolution.get("candidate_iris"),
                resolution_evidence={
                    **dict(term_resolution.get("resolution_evidence", {})),
                    "owner_kind": term_lookup_kind,
                },
                source_node_iri=author_source_iri,
            )
            if house_term is not None:
                graph.add((work_iri, OIR.recordOfHouseTerm, house_term))

            venue = work_segments[3] if len(work_segments) > 3 else None
            body: URIRef | None = None
            body_status = "unresolved"
            body_resolution: dict = {"reason": "no-approved-owner-identity-resolution"}
            body_slot_evidence: dict[str, object] = {"work_venue_segment": venue, "author_href": author_href}
            if author_href == "#oireachtas":
                if venue in APPROVED_CHAMBER_HOUSES:
                    body = APPROVED_CHAMBER_HOUSES[venue]
                    body_status = "resolved"
                    body_resolution = {
                        "target_iri": str(body),
                        "resolution_evidence": {
                            "resolution_method": "approved-Work-venue-plus-generic-Oireachtas-author-crosswalk",
                            "work_venue_segment": venue,
                            "author_href": author_href,
                        },
                    }
                else:
                    body_resolution = {"reason": "generic-author-without-approved-chamber-venue"}
            elif author_path is not None:
                path, path_segments = author_path
                is_house_term = (
                    path_segments[:3] == ["ie", "oireachtas", "house"]
                    and len(path_segments) == 5
                    and path_segments[3] in {"dail", "seanad"}
                    and re.fullmatch(r"[1-9][0-9]*", path_segments[4]) is not None
                )
                is_committee = (
                    path_segments[:3] == ["ie", "oireachtas", "committee"]
                    and len(path_segments) >= 4
                )
                if is_committee:
                    committee_matches = _matches(
                        resolver.resolve_committee(author_href) if resolver is not None else None,
                        "Committee",
                    )
                    body_status, body_resolution = _candidate_outcome(
                        target_matches=committee_matches,
                        reason_unresolved="no-existing-Committee-owner-match",
                        evidence={
                            "resolver_version": resolver_version_value,
                            "lookup_key": author_href,
                            "source_path": path,
                            "owner_kind": "Committee",
                            "resolution_method": "exact-official-Committee-author-href",
                        },
                    )
                    if len(committee_matches) == 1:
                        body = committee_matches[0]
                elif is_house_term:
                    if house_term is None:
                        body_resolution = {
                            "reason": "HouseTerm-author-not-resolved-to-existing-owner",
                            "resolution_evidence": {
                                "resolver_version": resolver_version_value,
                                "lookup_key": author_href,
                                "work_venue_segment": venue,
                            },
                        }
                    else:
                        term_house_matches = _matches(
                            resolver.house_for_term(str(house_term)) if resolver is not None else None,
                            "HouseTerm termOf House",
                        )
                        expected_house = APPROVED_CHAMBER_HOUSES.get(venue or "")
                        if expected_house is None:
                            body_resolution = {
                                "reason": "Work-venue-is-not-an-approved-chamber",
                                "resolution_evidence": {
                                    "work_venue_segment": venue,
                                    "term_iri": str(house_term),
                                },
                            }
                        elif len(term_house_matches) == 1 and term_house_matches[0] == expected_house:
                            body = expected_house
                            body_status = "resolved"
                            body_resolution = {
                                "target_iri": str(body),
                                "resolution_evidence": {
                                    "resolution_method": "Work-venue-agrees-with-existing-HouseTerm-termOf-target",
                                    "work_venue_segment": venue,
                                    "term_iri": str(house_term),
                                    "term_of_house_iri": str(term_house_matches[0]),
                                    "source_author_href": author_href,
                                },
                            }
                        elif len(term_house_matches) > 1:
                            body_resolution = {
                                "reason": "ambiguous-existing-HouseTerm-termOf-target",
                                "candidate_iris": [str(value) for value in term_house_matches],
                                "resolution_evidence": {"term_iri": str(house_term)},
                            }
                        elif len(term_house_matches) == 1:
                            body_resolution = {
                                "reason": "Work-venue-and-HouseTerm-termOf-target-conflict",
                                "resolution_evidence": {
                                    "work_venue_segment": venue,
                                    "term_iri": str(house_term),
                                    "term_of_house_iri": str(term_house_matches[0]),
                                    "expected_house_iri": str(expected_house),
                                },
                            }
                        else:
                            body_resolution = {
                                "reason": "existing-HouseTerm-has-no-resolved-termOf-House",
                                "resolution_evidence": {"term_iri": str(house_term)},
                            }
                else:
                    body_resolution = {"reason": "FRBRauthor-href-is-not-an-approved-HouseTerm-or-Committee-identity"}
            if body is not None:
                graph.add((work_iri, OIR.recordOfBody, body))
            add_outcome(
                node=author,
                attribute="href",
                raw=author_href,
                slot="FRBRWork/FRBRauthor/@href->recordOfBody",
                status="resolved" if body is not None else body_status,
                reason=body_resolution.get("reason"),
                target_iri=body if body is not None else body_resolution.get("target_iri"),
                candidate_iris=body_resolution.get("candidate_iris"),
                resolution_evidence={**body_slot_evidence, **dict(body_resolution.get("resolution_evidence", {}))},
                source_node_iri=author_source_iri,
            )

    # Deferred section-to-Bill and vote-target links are retained as explicit
    # source-hash outcomes but never emitted as speculative RDF.
    for section in (node for node in mapped_addressables if _local_name(node) == "debateSection"):
        raw = section.get("refersTo")
        status, target_eid = _local_fragment(raw)
        subject = resource_iris[section]
        if status == "absent":
            add_outcome(
                node=section,
                attribute="refersTo",
                raw=None,
                slot="debateSection/@refersTo->refersToEvent",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=subject,
            )
        elif status == "malformed":
            add_outcome(
                node=section,
                attribute="refersTo",
                raw=raw,
                slot="debateSection/@refersTo->refersToEvent",
                status="malformed",
                reason="not-a-reviewed-local-NCName-fragment",
                source_node_iri=subject,
            )
        elif status == "placeholder":
            add_outcome(
                node=section,
                attribute="refersTo",
                raw=raw,
                slot="debateSection/@refersTo->refersToEvent",
                status="unresolved",
                reason="source-placeholder",
                source_node_iri=subject,
            )
        else:
            target = eid_index.get(target_eid)
            add_outcome(
                node=section,
                attribute="refersTo",
                raw=raw,
                slot="debateSection/@refersTo->refersToEvent",
                status="unresolved",
                reason="Bill-event-owner-resolution-deferred",
                source_node_iri=subject,
                resolution_evidence={
                    "target_eid": target_eid,
                    "local_target_pointer": source_paths[target] if target is not None else None,
                    "local_target_qname": _expanded_qname(target) if target is not None else None,
                    "resolution_rule": "exact-existing-Bill-owner-identity-required",
                },
            )

    # Individual votes link only from a division's explicit ta/nil/staon
    # source groups and only to existing Members resolved through TLCPerson.
    divisions = [
        node for node in mapped_addressables
        if _local_name(node) == "debateSection" and node.get("name") == "division"
    ]
    for division in divisions:
        division_iri = resource_iris[division]
        for group in division:
            group_name = group.get("name") if _local_name(group) == "debateSection" else None
            if group_name not in VOTE_GROUPS:
                continue
            vote_predicate = VOTE_GROUPS[group_name][0]
            for person in _descendants_named(group, "person"):
                raw = person.get("refersTo")
                resolve_person_reference(
                    node=person,
                    raw=raw,
                    slot=f"division/{group_name}/person/@refersTo->{vote_predicate.split('#')[-1]}",
                    predicate=vote_predicate,
                    owner_subject=division_iri,
                    source_node=division_iri,
                )

    # Resolve voting/@href -> exact result Summary eId -> exactly one
    # containing Division.  voting/@refersTo remains semantically deferred.
    summary_divisions: dict[ET.Element, list[ET.Element]] = {}
    for summary in (node for node in mapped_addressables if _local_name(node) == "summary"):
        ancestors: list[ET.Element] = []
        current = summary
        while current in parents:
            current = parents[current]
            if _local_name(current) == "debateSection" and current.get("name") == "division":
                ancestors.append(current)
        summary_divisions[summary] = ancestors

    vote_evidence_rows: list[dict] = []
    analysis_nodes = [node for node in meta.iter() if _local_name(node) == "analysis"]
    votings = [node for analysis in analysis_nodes for node in analysis.iter() if node is not analysis and _local_name(node) == "voting"]
    for voting in votings:
        raw_href = voting.get("href")
        href_status, summary_eid = _local_fragment(raw_href)
        linked_division: ET.Element | None = None
        join_target: URIRef | None = None
        join_reason: str | None = None
        join_evidence: dict[str, object] = {}
        if href_status == "valid":
            target = eid_index.get(summary_eid)
            if target is None:
                join_reason = "unknown-result-Summary-eid"
            elif _local_name(target) != "summary" or target not in addressable_set:
                join_reason = "result-reference-does-not-identify-a-Debate-Summary"
                join_evidence["target_qname"] = _expanded_qname(target)
                join_evidence["target_pointer"] = source_paths[target]
            else:
                ancestors = summary_divisions.get(target, [])
                if len(ancestors) != 1:
                    join_reason = "result-Summary-not-contained-by-exactly-one-Division"
                    join_evidence["containing_division_count"] = len(ancestors)
                    join_evidence["summary_pointer"] = source_paths[target]
                else:
                    linked_division = ancestors[0]
                    join_target = resource_iris[linked_division]
                    join_evidence["summary_eid"] = summary_eid
                    join_evidence["summary_pointer"] = source_paths[target]
                    join_evidence["division_pointer"] = source_paths[linked_division]
        elif href_status == "placeholder":
            join_reason = "source-placeholder"
        elif href_status == "malformed":
            join_reason = "not-a-reviewed-local-NCName-fragment"
        else:
            join_reason = "optional-attribute-absent"
        vote_subject = join_target or expression_iri
        if href_status == "absent":
            add_outcome(
                node=voting,
                attribute="href",
                raw=None,
                slot="analysis/voting/@href->result-Summary-Division-join",
                status="absent",
                reason=join_reason,
                source_node_iri=vote_subject,
            )
        elif href_status == "malformed":
            add_outcome(
                node=voting,
                attribute="href",
                raw=raw_href,
                slot="analysis/voting/@href->result-Summary-Division-join",
                status="malformed",
                reason=join_reason,
                source_node_iri=vote_subject,
            )
        elif join_target is not None:
            add_outcome(
                node=voting,
                attribute="href",
                raw=raw_href,
                slot="analysis/voting/@href->result-Summary-Division-join",
                status="resolved",
                target_iri=join_target,
                source_node_iri=vote_subject,
                resolution_evidence=join_evidence,
            )
        else:
            add_outcome(
                node=voting,
                attribute="href",
                raw=raw_href,
                slot="analysis/voting/@href->result-Summary-Division-join",
                status="unresolved",
                reason=join_reason,
                source_node_iri=vote_subject,
                resolution_evidence={**join_evidence, "target_eid": summary_eid},
            )

        raw_outcome = voting.get("outcome")
        outcome_status, outcome_fragment = _local_fragment(raw_outcome)
        outcome_target = VOTE_OUTCOMES.get(raw_outcome or "")
        if outcome_status == "absent":
            add_outcome(
                node=voting,
                attribute="outcome",
                raw=None,
                slot="analysis/voting/@outcome->divisionOutcome",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=vote_subject,
            )
        elif outcome_status == "malformed":
            add_outcome(
                node=voting,
                attribute="outcome",
                raw=raw_outcome,
                slot="analysis/voting/@outcome->divisionOutcome",
                status="malformed",
                reason="not-a-reviewed-controlled-fragment",
                source_node_iri=vote_subject,
            )
        elif outcome_target is not None and join_target is not None:
            graph.add((join_target, OIR.divisionOutcome, outcome_target))
            add_outcome(
                node=voting,
                attribute="outcome",
                raw=raw_outcome,
                slot="analysis/voting/@outcome->divisionOutcome",
                status="resolved",
                target_iri=join_target,
                source_node_iri=vote_subject,
                resolution_evidence={"controlled_value": raw_outcome, **join_evidence},
            )
        elif outcome_target is not None:
            add_outcome(
                node=voting,
                attribute="outcome",
                raw=raw_outcome,
                slot="analysis/voting/@outcome->divisionOutcome",
                status="unresolved",
                reason="result-Summary-Division-join-unresolved",
                source_node_iri=vote_subject,
                resolution_evidence={"controlled_value": raw_outcome, "join_reason": join_reason},
            )
        elif outcome_status == "placeholder":
            add_outcome(
                node=voting,
                attribute="outcome",
                raw=raw_outcome,
                slot="analysis/voting/@outcome->divisionOutcome",
                status="unresolved",
                reason="source-placeholder",
                source_node_iri=vote_subject,
            )
        else:
            add_outcome(
                node=voting,
                attribute="outcome",
                raw=raw_outcome,
                slot="analysis/voting/@outcome->divisionOutcome",
                status="unresolved",
                reason="unsupported-controlled-outcome",
                source_node_iri=vote_subject,
                resolution_evidence={
                    "controlled_value": raw_outcome,
                    "known_values": sorted(VOTE_OUTCOMES),
                    "join_target_iri": str(join_target) if join_target is not None else None,
                },
            )

        raw_vote_target = voting.get("refersTo")
        target_status, target_eid = _local_fragment(raw_vote_target)
        vote_target_node = eid_index.get(target_eid) if target_eid is not None else None
        target_evidence: dict[str, object] = {
            "resolution_rule": "voting-@refersTo-semantics-deferred",
            "target_eid": target_eid,
        }
        if vote_target_node is not None:
            target_evidence.update(
                {"local_target_pointer": source_paths[vote_target_node], "local_target_qname": _expanded_qname(vote_target_node)}
            )
        if target_status == "absent":
            add_outcome(
                node=voting,
                attribute="refersTo",
                raw=None,
                slot="analysis/voting/@refersTo->refersToProposal",
                status="absent",
                reason="optional-attribute-absent",
                source_node_iri=vote_subject,
            )
        elif target_status == "malformed":
            add_outcome(
                node=voting,
                attribute="refersTo",
                raw=raw_vote_target,
                slot="analysis/voting/@refersTo->refersToProposal",
                status="malformed",
                reason="not-a-reviewed-local-NCName-fragment",
                source_node_iri=vote_subject,
            )
        elif target_status == "placeholder":
            add_outcome(
                node=voting,
                attribute="refersTo",
                raw=raw_vote_target,
                slot="analysis/voting/@refersTo->refersToProposal",
                status="unresolved",
                reason="source-placeholder",
                source_node_iri=vote_subject,
            )
        else:
            add_outcome(
                node=voting,
                attribute="refersTo",
                raw=raw_vote_target,
                slot="analysis/voting/@refersTo->refersToProposal",
                status="unresolved",
                reason="vote-target-semantics-deferred",
                source_node_iri=vote_subject,
                resolution_evidence=target_evidence,
            )

        vote_counts: list[dict] = []
        for count in _children_named(voting, "count"):
            raw_kind = count.get("refersTo")
            kind_status, _count_kind = _local_fragment(raw_kind)
            count_kind = raw_kind[1:] if raw_kind in {"#ta", "#nil", "#staon"} else None
            count_predicate = VOTE_GROUPS[count_kind][1] if count_kind is not None else None
            count_value = count.get("value")
            evidence = {
                "count_value": count_value,
                "voting_href": raw_href,
                "result_division_iri": str(join_target) if join_target is not None else None,
            }
            if kind_status == "absent":
                count_status, count_reason = "absent", "optional-attribute-absent"
            elif kind_status == "malformed":
                count_status, count_reason = "malformed", "not-a-reviewed-count-category-fragment"
            elif kind_status == "placeholder":
                count_status, count_reason = "unresolved", "source-placeholder"
            elif count_kind is None:
                count_status, count_reason = "unresolved", "unsupported-count-category"
            elif join_target is None:
                count_status, count_reason = "unresolved", "result-Summary-Division-join-unresolved"
            else:
                count_status, count_reason = "resolved", None
            add_outcome(
                node=count,
                attribute="refersTo",
                raw=raw_kind,
                slot="analysis/voting/count/@refersTo->aggregate-count-category",
                status=count_status,
                reason=count_reason,
                target_iri=join_target if count_status == "resolved" else None,
                source_node_iri=vote_subject,
                resolution_evidence={**evidence, **({"count_kind": count_kind} if count_kind else {})},
            )
            emitted = False
            if count_status == "resolved" and count_predicate is not None and count_value is not None:
                try:
                    count_literal = integer(count_value)
                except ValueError as error:
                    _raise_transform_error(
                        str(error),
                        report=report,
                        code="vote-count-invalid-integer",
                        evidence={
                            "source_pointer": source_paths[count],
                            "raw_value": count_value,
                            "count_category": raw_kind,
                            "division_iri": str(join_target),
                        },
                    )
                graph.add((join_target, count_predicate, count_literal))
                emitted = True
            elif count_value is not None and count_kind is not None and join_target is not None:
                # A recognized aggregate count value must parse even if no
                # emission can occur for an independently unresolved join; the
                # source evidence remains auditable without loosening identity.
                try:
                    integer(count_value)
                except ValueError as error:
                    _raise_transform_error(
                        str(error),
                        report=report,
                        code="vote-count-invalid-integer",
                        evidence={"source_pointer": source_paths[count], "raw_value": count_value},
                    )
            vote_counts.append(
                {
                    "source_pointer": source_paths[count],
                    "source_eid": count.get("eId"),
                    "refers_to": raw_kind,
                    "value": count_value,
                    "status": count_status,
                    "emitted": emitted,
                }
            )
        vote_evidence_rows.append(
            {
                "source_pointer": source_paths[voting],
                "source_eid": voting.get("eId"),
                "source_node_iri": str(vote_subject),
                "href": raw_href,
                "href_status": "resolved" if join_target is not None else href_status if href_status != "valid" else "unresolved",
                "division_iri": str(join_target) if join_target is not None else None,
                "outcome": raw_outcome,
                "refers_to": raw_vote_target,
                "counts": vote_counts,
            }
        )

    # recordedTime is source metadata on Speech only; surrounding from text and
    # all prose are excluded.
    for speech in (node for node in mapped_addressables if _local_name(node) == "speech"):
        speech_iri = resource_iris[speech]
        for from_element in _children_named(speech, "from"):
            for recorded in _children_named(from_element, "recordedTime"):
                time_value = recorded.get("time")
                if time_value is None:
                    _raise_transform_error(
                        "speech/from/recordedTime must have @time",
                        report=report,
                        code="recorded-time-missing",
                        evidence={"source_pointer": source_paths[recorded]},
                    )
                try:
                    graph.add((speech_iri, OIR.recordedTime, datetime_literal(time_value)))
                except ValueError as error:
                    _raise_transform_error(
                        str(error),
                        report=report,
                        code="recorded-time-invalid",
                        evidence={"source_pointer": source_paths[recorded], "source_time": time_value},
                    )

    # The count properties are FunctionalProperties in the executable
    # ontology.  Refuse a source that would put different values on one
    # Division rather than silently selecting one or producing inconsistent RDF.
    for predicate in (OIR.taCount, OIR.nilCount, OIR.staonCount):
        for division in set(graph.subjects(predicate, None)):
            values = set(graph.objects(division, predicate))
            if len(values) > 1:
                _raise_transform_error(
                    "multiple distinct source aggregate counts target a functional Division count property",
                    report=report,
                    code="duplicate-division-count-values",
                    evidence={
                        "division_iri": str(division),
                        "predicate": str(predicate),
                        "values": sorted(str(value) for value in values),
                    },
                )

    roll_call_rows = []
    for roll_call in roll_calls:
        roll_call_rows.append(
            {
                "source_pointer": source_paths[roll_call],
                "source_eid": roll_call.get("eId"),
                "containing_source_node_iri": str(node_subject(roll_call)),
            }
        )
    report["source_evidence"] = {
        "work_frbruri": source_work_uri,
        "expression_frbruri": source_expression_uri,
        "work_date": source_date,
        "work_name_values": work_name_values,
        "work_author_hrefs": [author.get("href") for author in work_authors],
        "roll_call_count": len(roll_call_rows),
        "roll_calls": roll_call_rows,
        "vote_records": vote_evidence_rows,
    }
    report["expression_set_completeness"] = "not-asserted-single-file-does-not-prove-global-completeness"
    _sort_report(report)
    return DebateTransformResult(
        graph=graph,
        work_iri=work_iri_text,
        expression_iri=expression_iri_text,
        graph_iri=graph_iri_text,
        source_sha256=source_sha256,
        reference_report=report,
    )


def transform_debate_with_report(
    source_xml: bytes,
    *,
    resolver: DebateReferenceResolver | None = None,
    known_expression_source_uris: Iterable[str] | None = None,
    resolver_version: str | None = None,
) -> DebateTransformResult:
    """Explicit report-named alias for :func:`transform_debate`."""

    return transform_debate(
        source_xml,
        resolver=resolver,
        known_expression_source_uris=known_expression_source_uris,
        resolver_version=resolver_version,
    )
