"""Tranche 3 SHACL and cross-dataset quality checks for Debates RDF.

``validate_debates_integration`` takes the actual result of the Debates
transform and a named :class:`rdflib.Dataset` containing that exact debate graph
plus owner graphs that have already passed their own source/RDF validators.
This module checks the joined references; it does not replace owner validation
or duplicate the production transformer.

The SHACL shapes describe RDF structure and owner-resource classes only. They
are intentionally not an AKN XML schema. RDF can reject transcript-like
predicates and unapproved literal-bearing terms, but it cannot prove that a
source-derived value placed in an otherwise permitted structural string is not
transcript prose, nor prove that votes/participations were not sourced from
``rollCall``. Those guarantees remain source-aware AKN/output checks.
"""
from __future__ import annotations

import hashlib
import json
import re
import warnings
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Mapping
from importlib.resources import files
from urllib.parse import quote, urlsplit

from pyshacl import validate
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from ..config import COMMITTEES_GRAPH, HOUSES_GRAPH
from ..transforms.common import ELIDL, MEMBERS, OIR
from .debates import validate_debates


RESOURCES = files("oireachtas_etl.validation.resources")
MEMBER_GRAPH_PREFIX = "https://data.oireachtas.ie/graph/member/"
REFERENCE_CONTRACT = "debates-reference-outcomes-v1"
TRANSFORM_CONTRACT = "debates-transformer-core-v1"
REFERENCE_STATUSES = frozenset({"resolved", "unresolved", "malformed", "absent"})
KNOWN_OUTCOMES = {
    "#carried": OIR.DeclaredCarried,
    "#lost": OIR.DeclaredLost,
}

# These source-reference slots have RDF relationships under the approved
# mapping. The report is the audit record for each emitted or omitted edge.
SIMPLE_REFERENCE_SLOTS = {
    "speech/@by": OIR.speaker,
    "question/@by": OIR.askedBy,
    "FRBRWork/FRBRauthor/@href->recordOfBody": OIR.recordOfBody,
    "FRBRWork/FRBRauthor/@href->recordOfHouseTerm": OIR.recordOfHouseTerm,
}
DEFERRED_REFERENCE_SLOTS = frozenset({
    "question/@to->directedTo/directedToOffice",
    "debateSection/@refersTo->refersToEvent",
    "analysis/voting/@refersTo->refersToProposal",
})
VOTE_SLOT = re.compile(
    r"division/(ta|nil|staon)/person/@refersTo->(votedFor|votedAgainst|abstained)\Z"
)
COUNT_PREDICATES = {
    "#ta": OIR.taCount,
    "#nil": OIR.nilCount,
    "#staon": OIR.staonCount,
}
NON_VOTE_REFERENCE_SLOTS = frozenset({
    *SIMPLE_REFERENCE_SLOTS,
    *DEFERRED_REFERENCE_SLOTS,
    "speech/@as->eli-dl:participation_role",
    "analysis/voting/@href->result-Summary-Division-join",
    "analysis/voting/@outcome->divisionOutcome",
    "analysis/voting/count/@refersTo->aggregate-count-category",
})
VOTE_PREDICATES = frozenset({OIR.votedFor, OIR.votedAgainst, OIR.abstained})
SOURCE_INVENTORY_SLOTS = frozenset({
    *NON_VOTE_REFERENCE_SLOTS,
    *(f"division/{group}/person/@refersTo->{predicate.split('#')[-1]}"
      for group, predicate in (
          ("ta", OIR.votedFor),
          ("nil", OIR.votedAgainst),
          ("staon", OIR.abstained),
      )),
})
MEMBER_REFERENCE_PREDICATES = frozenset({
    OIR.speaker,
    OIR.askedBy,
    OIR.votedFor,
    OIR.votedAgainst,
    OIR.abstained,
    ELIDL.had_participant_person,
})
REPORT_EDGE_PREDICATES = frozenset({
    *SIMPLE_REFERENCE_SLOTS.values(),
    OIR.votedFor,
    OIR.votedAgainst,
    OIR.abstained,
    OIR.divisionOutcome,
    OIR.taCount,
    OIR.nilCount,
    OIR.staonCount,
    ELIDL.had_participant_person,
    ELIDL.participation_role,
})

RDF_ONLY_LIMITATIONS = (
    "RDF checks reject prose/description predicates and literals outside mapped structural properties, but cannot identify transcript prose copied into an otherwise permitted string; source-aware comparison to the exact immutable AKN is still required.",
    "RDF checks cannot prove that a Division, individual vote, or Participation was not derived from committee rollCall attendance; source-aware AKN/output checks remain required.",
    "Without source_xml, the report is checked only for self-consistency with the result's declared source SHA-256 and for RDF/report coherence; this mode cannot recompute the digest or detect omitted reference-outcome rows.",
    "Owner graphs are treated as already validated by their owning validators; this module independently checks named-graph resolution, resource type, and HouseTerm relationships.",
)

SOURCE_AWARE_LIMITATIONS = (
    "With exact source_xml bytes, the validator inventories the source occurrences for the reference-outcome slots enumerated by this transform contract; it does not claim completeness for arbitrary AKN reference-like attributes or unsupported mapping slots.",
    "Source-aware checks independently verify occurrence identity and statuses that follow from source syntax/context, but do not repeat resolver decisions, prove resolved owner selection, or independently mint every Debate source-node IRI (including missing-eId fallback identities).",
    "Source-aware reference inventory is not an AKN schema, transcript comparison, rollCall provenance audit, or substitute for the owning transformer and validators.",
)

_XML_NCNAME_START = (
    r"A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF"
    r"\u0370-\u037D\u037F-\u1FFF\u200C-\u200D"
    r"\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF"
    r"\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
)
_XML_NCNAME_CHAR = _XML_NCNAME_START + r"0-9\-.\u00B7\u0300-\u036F\u203F-\u2040"
_XML_NCNAME = re.compile(f"[{_XML_NCNAME_START}][{_XML_NCNAME_CHAR}]*\\Z")


def _fail(message: str) -> None:
    raise ValueError(message)


def _absolute_iri(value: object, label: str) -> URIRef:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        _fail(f"{label} must be a non-empty absolute IRI")
    iri = URIRef(value)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        _fail(f"{label} must be a non-empty absolute IRI")
    return iri


def _named_graphs(dataset: Dataset) -> dict[URIRef, Graph]:
    default_id = dataset.default_graph.identifier
    graphs: dict[URIRef, Graph] = {}
    # Materialise plain Graphs once.  A Dataset context is a view backed by the
    # quad store; repeated Graph.triples calls on those views are needlessly
    # expensive (and currently trigger RDFLib's deprecated default_context
    # path).  Dataset.quads preserves the named-graph boundary directly.
    # RDFLib's Dataset.quads() uses its legacy ConjunctiveGraph view, which
    # emits one default_context deprecation warning per quad in 7.6.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Dataset.default_context is deprecated",
            category=DeprecationWarning,
        )
        quads = list(dataset.quads())
    for subject, predicate, obj, graph_iri in quads:
        if (graph_iri is None or graph_iri == default_id
                or not isinstance(graph_iri, URIRef)):
            continue
        graph = graphs.setdefault(graph_iri, Graph(identifier=graph_iri))
        graph.add((subject, predicate, obj))
    return graphs


def _member_graph(graph_iri: URIRef) -> bool:
    text = str(graph_iri)
    if not text.startswith(MEMBER_GRAPH_PREFIX):
        return False
    suffix = text[len(MEMBER_GRAPH_PREFIX):]
    parsed = urlsplit(text)
    return (bool(suffix) and "/" not in suffix and parsed.scheme == "https"
            and parsed.netloc == "data.oireachtas.ie" and not parsed.query
            and not parsed.fragment)


def _single_object(graph: Graph, subject: URIRef, predicate: URIRef,
                   label: str, *, required: bool = True):
    values = list(graph.objects(subject, predicate))
    if len(values) > 1 or (required and len(values) != 1):
        expected = "exactly one" if required else "at most one"
        _fail(f"{label} requires {expected} value")
    return values[0] if values else None


def _type_is(graph: Graph, subject: URIRef, class_iri: URIRef) -> bool:
    return (subject, RDF.type, class_iri) in graph


def _house_term(term: URIRef, houses: Graph, *, label: str) -> URIRef:
    if not isinstance(term, URIRef):
        _fail(f"{label} must target an owner HouseTerm IRI")
    term_types = set(houses.objects(term, RDF.type))
    supported = term_types & {OIR.DailTerm, OIR.SeanadTerm}
    if len(supported) != 1:
        _fail(f"{label} must target exactly one typed DailTerm or SeanadTerm in the Houses owner graph")
    house = _single_object(houses, term, OIR.termOf, f"{label} termOf")
    expected_house = (URIRef("https://data.oireachtas.ie/house/dail")
                      if next(iter(supported)) == OIR.DailTerm
                      else URIRef("https://data.oireachtas.ie/house/seanad"))
    if house != expected_house or not _type_is(houses, house, OIR.House):
        _fail(f"{label} termOf must resolve to the matching enduring House in the Houses owner graph")
    return house


def _member_owner(target: URIRef, member_graphs: Mapping[URIRef, Graph],
                  *, label: str) -> Graph:
    locations = [graph for graph in member_graphs.values()
                 if _type_is(graph, target, OIR.Member)]
    if len(locations) != 1:
        _fail(f"{label} must resolve to exactly one typed Member in a named Member owner graph")
    graph = locations[0]
    code = _single_object(graph, target, OIR.memberCode, f"{label} Member memberCode")
    if not isinstance(code, Literal) or not str(code):
        _fail(f"{label} Member owner must contain a non-empty memberCode")
    expected_graph = URIRef(MEMBER_GRAPH_PREFIX + quote(str(code), safe=""))
    if graph.identifier != expected_graph:
        _fail(f"{label} Member must be in the named graph selected by its memberCode")
    return graph


def _validate_report(result: object, graph: Graph) -> list[dict]:
    source_hash = getattr(result, "source_sha256", None)
    if not isinstance(source_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        _fail("Debates result source_sha256 must be a lowercase SHA-256 digest")
    report = getattr(result, "reference_report", None)
    if not isinstance(report, dict):
        _fail("Debates result must contain its source-hash-linked reference_report")
    if (report.get("contract_version") != REFERENCE_CONTRACT
            or report.get("transform_contract_version") != TRANSFORM_CONTRACT):
        _fail("Debates reference_report has an unsupported contract version")
    if report.get("source_sha256") != source_hash:
        _fail("Debates reference_report source hash does not match the transform result")
    rows = report.get("reference_outcomes")
    if not isinstance(rows, list):
        _fail("Debates reference_report reference_outcomes must be a list")
    owned_subjects = set(graph.subjects())
    for index, row in enumerate(rows):
        label = f"reference_outcomes[{index}]"
        if not isinstance(row, dict):
            _fail(f"{label} must be an object")
        required_text = ("contract_version", "source_sha256", "work_iri",
                         "expression_iri", "source_node_iri", "source_attribute_qname",
                         "slot", "source_pointer", "status")
        if ("raw_reference" not in row
                or any(not isinstance(row.get(key), str) or not row[key]
                       for key in required_text)):
            _fail(f"{label} is missing required source-hash-linked identity fields")
        if (row["contract_version"] != REFERENCE_CONTRACT
                or row["source_sha256"] != source_hash
                or row["work_iri"] != str(result.work_iri)
                or row["expression_iri"] != str(result.expression_iri)):
            _fail(f"{label} is not tied to this Debate Work, Expression, and source hash")
        if row["status"] not in REFERENCE_STATUSES:
            _fail(f"{label} has an unsupported reference status")
        raw = row.get("raw_reference")
        if raw is not None and not isinstance(raw, str):
            _fail(f"{label} raw_reference must be a string or null")
        if (row["status"] == "absent") != (raw is None):
            _fail(f"{label} absent status and raw_reference must agree")
        source_node = _absolute_iri(row["source_node_iri"], f"{label} source_node_iri")
        if source_node not in owned_subjects:
            _fail(f"{label} source_node_iri is not owned by this Debate graph")
        target_text = row.get("target_iri")
        if row["status"] == "resolved":
            if target_text is None:
                _fail(f"{label} resolved status requires target_iri")
            _absolute_iri(target_text, f"{label} target_iri")
        elif target_text is not None:
            _fail(f"{label} non-resolved status must not invent target_iri")
        if row["status"] != "resolved" and not isinstance(row.get("reason"), str):
            _fail(f"{label} non-resolved status requires an auditable reason")
        candidates = row.get("candidate_iris", [])
        if (not isinstance(candidates, list)
                or any(not isinstance(value, str) for value in candidates)
                or candidates != sorted(set(candidates))):
            _fail(f"{label} candidate_iris must be a sorted unique list")
        for candidate in candidates:
            _absolute_iri(candidate, f"{label} candidate_iris entry")
        if row["status"] != "unresolved" and candidates:
            _fail(f"{label} only unresolved references may retain owner candidates")
        if ("resolution_evidence" in row
                and not isinstance(row["resolution_evidence"], dict)):
            _fail(f"{label} resolution_evidence must be an object")
    return rows


def _expected_report_edges(rows: list[dict], graph: Graph) -> dict[URIRef, set[tuple]]:
    expected = {predicate: set() for predicate in REPORT_EDGE_PREDICATES}
    for row in rows:
        slot = row["slot"]
        status = row["status"]
        source = URIRef(row["source_node_iri"])
        if slot not in NON_VOTE_REFERENCE_SLOTS and VOTE_SLOT.fullmatch(slot) is None:
            _fail(f"Debates reference_report contains an unsupported source slot: {slot}")
        if slot in DEFERRED_REFERENCE_SLOTS:
            if status == "resolved":
                _fail(f"deferred Debates reference slot must not be marked resolved: {slot}")
            continue

        if slot in SIMPLE_REFERENCE_SLOTS:
            predicate = SIMPLE_REFERENCE_SLOTS[slot]
            if status == "resolved":
                target = URIRef(row["target_iri"])
                expected[predicate].add((source, predicate, target))
                if predicate == OIR.speaker:
                    participation = URIRef(str(source) + "#participation")
                    expected[ELIDL.had_participant_person].add(
                        (participation, ELIDL.had_participant_person, target))
            continue

        vote_match = VOTE_SLOT.fullmatch(slot)
        if vote_match:
            predicate = OIR[vote_match.group(2)]
            if status == "resolved":
                expected[predicate].add((source, predicate, URIRef(row["target_iri"])))
            continue

        if slot == "speech/@as->eli-dl:participation_role":
            if status == "resolved":
                participation = URIRef(str(source) + "#participation")
                expected[ELIDL.participation_role].add(
                    (participation, ELIDL.participation_role,
                     URIRef(row["target_iri"]))
                )
            continue

        if slot == "analysis/voting/@href->result-Summary-Division-join":
            if status == "resolved":
                target = URIRef(row["target_iri"])
                if source != target or not _type_is(graph, target, OIR.Division):
                    _fail("resolved voting/@href report must identify its joined Debate Division")
            continue

        if slot == "analysis/voting/@outcome->divisionOutcome":
            if status == "resolved":
                target = URIRef(row["target_iri"])
                outcome = KNOWN_OUTCOMES.get(row.get("raw_reference"))
                if source != target or outcome is None or not _type_is(graph, target, OIR.Division):
                    _fail("resolved division outcome report must identify a known result on its Division")
                expected[OIR.divisionOutcome].add((target, OIR.divisionOutcome, outcome))
            continue

        if slot == "analysis/voting/count/@refersTo->aggregate-count-category":
            if status == "resolved":
                target = URIRef(row["target_iri"])
                predicate = COUNT_PREDICATES.get(row.get("raw_reference"))
                evidence = row.get("resolution_evidence", {})
                raw_count = evidence.get("count_value") if isinstance(evidence, dict) else None
                if source != target or predicate is None or not _type_is(graph, target, OIR.Division):
                    _fail("resolved aggregate-count report must identify a supported count on its Division")
                if raw_count is not None:
                    if not isinstance(raw_count, str) or not re.fullmatch(r"[+-]?\d+", raw_count):
                        _fail("resolved aggregate count report must preserve an integer source value")
                    count = int(raw_count)
                    if count < 0:
                        _fail("resolved aggregate count report must not contain a negative value")
                    expected[predicate].add((target, predicate,
                                             Literal(count, datatype=XSD.integer)))
            continue

        # The report format records additional source evidence (including the
        # deferred vote target); it must not create an unreviewed RDF edge.

    return expected


def _validate_report_edges(rows: list[dict], graph: Graph) -> None:
    expected = _expected_report_edges(rows, graph)
    for predicate in REPORT_EDGE_PREDICATES:
        actual = set(graph.triples((None, predicate, None)))
        if actual != expected[predicate]:
            missing = sorted((str(triple) for triple in expected[predicate] - actual))
            extra = sorted((str(triple) for triple in actual - expected[predicate]))
            _fail(f"Debates RDF/reference report mismatch for {predicate}: missing={missing} extra={extra}")


def _xml_local_name(element: ET.Element) -> str:
    tag = element.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _xml_source_paths(root: ET.Element) -> tuple[dict[ET.Element, str],
                                                dict[ET.Element, ET.Element]]:
    """Build source pointers independently for matching report occurrences."""
    root_name = _xml_local_name(root)
    paths = {root: f"/{root_name}[1]"}
    parents: dict[ET.Element, ET.Element] = {}

    def walk(parent: ET.Element, parent_path: str) -> None:
        sibling_counts: dict[str, int] = {}
        for child in parent:
            name = _xml_local_name(child)
            sibling_counts[name] = sibling_counts.get(name, 0) + 1
            eid = child.get("eId")
            segment = (f"{name}[@eId={json.dumps(eid, ensure_ascii=False)}]"
                       if eid else f"{name}[{sibling_counts[name]}]")
            paths[child] = f"{parent_path}/{segment}"
            parents[child] = parent
            walk(child, paths[child])

    walk(root, paths[root])
    return paths, parents


def _source_children(parent: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in parent if _xml_local_name(child) == name]


def _source_reference_shape(raw: str | None) -> tuple[str, str | None]:
    """Classify reviewed local fragments without calling transformer helpers."""
    if raw is None:
        return "absent", None
    if raw == "#":
        return "placeholder", None
    if not raw.startswith("#") or _XML_NCNAME.fullmatch(raw[1:]) is None:
        return "malformed", None
    return "valid", raw[1:]


def _source_reference_statuses(raw: str | None, *, valid: set[str] | None = None) -> frozenset[str]:
    shape, _ = _source_reference_shape(raw)
    if shape == "absent":
        return frozenset({"absent"})
    if shape == "malformed":
        return frozenset({"malformed"})
    if shape == "placeholder":
        return frozenset({"unresolved"})
    return frozenset(valid or {"unresolved"})


def _source_author_path(raw: str) -> list[str] | None:
    """Recognize only the source path forms accepted for FRBRauthor/@href."""
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
    segments = path[1:].split("/") if path.startswith("/") else path.split("/")
    if (not segments or any(not part or part in {".", ".."} for part in segments)
            or any(re.search(r"%(?![0-9A-Fa-f]{2})", part) for part in segments)):
        return None
    return segments


def _source_author_term_statuses(raw: str | None, *, multiple_authors: bool) -> frozenset[str]:
    if raw is None:
        return frozenset({"absent"})
    if multiple_authors:
        return frozenset({"unresolved"})
    if raw.startswith("#"):
        shape, _ = _source_reference_shape(raw)
        return frozenset({"malformed"}) if shape == "malformed" else frozenset({"unresolved"})
    segments = _source_author_path(raw)
    if segments is None:
        return frozenset({"malformed"})
    numbered_house_term = (
        segments[:3] == ["ie", "oireachtas", "house"]
        and len(segments) == 5
        and segments[3] in {"dail", "seanad"}
        and re.fullmatch(r"[1-9][0-9]*", segments[4]) is not None
    )
    # Whether a syntactically approved HouseTerm has an existing owner is a
    # resolver decision and is deliberately not recomputed here.
    return (frozenset({"resolved", "unresolved"}) if numbered_house_term
            else frozenset({"unresolved"}))


def _source_inventory(source_xml: bytes) -> list[dict]:
    """Inventory the currently contracted source slots, not arbitrary AKN links."""
    try:
        root = ET.fromstring(source_xml)
    except (ET.ParseError, ValueError) as error:
        _fail(f"source-aware validation could not parse exact AKN XML bytes: {error}")
    if _xml_local_name(root) != "akomaNtoso":
        _fail("source-aware validation expected an akomaNtoso document root")
    debates = _source_children(root, "debate")
    if len(debates) != 1:
        _fail("source-aware inventory requires exactly one direct debate element")
    debate = debates[0]
    metas = _source_children(debate, "meta")
    bodies = _source_children(debate, "debateBody")
    if len(metas) != 1 or len(bodies) != 1:
        _fail("source-aware inventory requires one meta and one debateBody")
    meta, debate_body = metas[0], bodies[0]
    identifications = _source_children(meta, "identification")
    if len(identifications) != 1:
        _fail("source-aware inventory requires one meta/identification")
    works = _source_children(identifications[0], "FRBRWork")
    if len(works) != 1:
        _fail("source-aware inventory requires one identification/FRBRWork")
    work = works[0]

    paths, parents = _xml_source_paths(root)
    elements = list(root.iter())
    elements_by_eid: dict[str, list[ET.Element]] = {}
    for element in elements:
        eid = element.get("eId")
        if eid:
            elements_by_eid.setdefault(eid, []).append(element)

    roll_calls = {
        element for element in debate_body.iter()
        if element is not debate_body and _xml_local_name(element) == "rollCall"
    }

    def is_inside_roll_call(element: ET.Element) -> bool:
        current = element
        while current in parents:
            current = parents[current]
            if current in roll_calls:
                return True
        return False

    addressable_names = {"debateSection", "speech", "summary", "question"}
    addressable_nodes = [
        element for element in debate_body.iter()
        if element is not debate_body
        and _xml_local_name(element) in addressable_names
        and not is_inside_roll_call(element)
    ]
    addressables = set(addressable_nodes)
    inventory: list[dict] = []

    def add(node: ET.Element, attribute: str, slot: str,
            statuses: frozenset[str]) -> None:
        inventory.append({
            "key": (slot, paths[node], attribute, node.get(attribute), node.get("eId")),
            "statuses": statuses,
        })

    for node in addressable_nodes:
        name = _xml_local_name(node)
        if name == "speech":
            add(node, "by", "speech/@by",
                _source_person_statuses(node.get("by"), elements_by_eid))
            role_shape, _ = _source_reference_shape(node.get("as"))
            role_status = {"absent": "absent", "malformed": "malformed"}.get(
                role_shape, "unresolved",
            )
            add(node, "as", "speech/@as->eli-dl:participation_role",
                frozenset({role_status}))
        elif name == "question":
            add(node, "by", "question/@by",
                _source_person_statuses(node.get("by"), elements_by_eid))
            add(node, "to", "question/@to->directedTo/directedToOffice",
                _source_reference_statuses(node.get("to")))
        elif name == "debateSection":
            add(node, "refersTo", "debateSection/@refersTo->refersToEvent",
                _source_reference_statuses(node.get("refersTo")))

    work_authors = _source_children(work, "FRBRauthor")
    author_nodes = work_authors or [work]
    multiple_authors = len(work_authors) > 1
    for author in author_nodes:
        raw = author.get("href")
        add(author, "href", "FRBRWork/FRBRauthor/@href->recordOfHouseTerm",
            _source_author_term_statuses(raw, multiple_authors=multiple_authors))
        body_statuses = (frozenset({"absent"}) if raw is None else
                         frozenset({"unresolved", "resolved"}))
        add(author, "href", "FRBRWork/FRBRauthor/@href->recordOfBody", body_statuses)

    divisions = [
        section for section in addressable_nodes
        if _xml_local_name(section) == "debateSection" and section.get("name") == "division"
    ]
    for division in divisions:
        for group in division:
            group_name = group.get("name") if _xml_local_name(group) == "debateSection" else None
            if group_name not in {"ta", "nil", "staon"}:
                continue
            predicate_name = {"ta": "votedFor", "nil": "votedAgainst", "staon": "abstained"}[group_name]
            for person in group.iter():
                if person is group or _xml_local_name(person) != "person":
                    continue
                add(person, "refersTo",
                    f"division/{group_name}/person/@refersTo->{predicate_name}",
                    _source_person_statuses(person.get("refersTo"), elements_by_eid))

    def voting_join_status(voting: ET.Element) -> str:
        shape, target_eid = _source_reference_shape(voting.get("href"))
        if shape == "absent":
            return "absent"
        if shape == "malformed":
            return "malformed"
        if shape == "placeholder":
            return "unresolved"
        targets = elements_by_eid.get(target_eid or "", [])
        if len(targets) != 1 or _xml_local_name(targets[0]) != "summary" or targets[0] not in addressables:
            return "unresolved"
        ancestors: list[ET.Element] = []
        current = targets[0]
        while current in parents:
            current = parents[current]
            if (_xml_local_name(current) == "debateSection"
                    and current.get("name") == "division"):
                ancestors.append(current)
        return "resolved" if len(ancestors) == 1 else "unresolved"

    analysis_nodes = [node for node in meta.iter() if _xml_local_name(node) == "analysis"]
    # Preserve the transformer contract's occurrence contexts: every voting
    # descendant of each Analysis is inventoried, but voting/@refersTo remains
    # deferred and is never promoted to an RDF relationship here.
    for analysis in analysis_nodes:
        for voting in analysis.iter():
            if voting is analysis or _xml_local_name(voting) != "voting":
                continue
            href_status = voting_join_status(voting)
            add(voting, "href", "analysis/voting/@href->result-Summary-Division-join",
                frozenset({href_status}))

            outcome = voting.get("outcome")
            outcome_shape, _ = _source_reference_shape(outcome)
            if outcome_shape == "absent":
                outcome_status = "absent"
            elif outcome_shape == "malformed":
                outcome_status = "malformed"
            elif outcome_shape == "placeholder":
                outcome_status = "unresolved"
            elif outcome in {"#carried", "#lost"} and href_status == "resolved":
                outcome_status = "resolved"
            else:
                outcome_status = "unresolved"
            add(voting, "outcome", "analysis/voting/@outcome->divisionOutcome",
                frozenset({outcome_status}))

            add(voting, "refersTo", "analysis/voting/@refersTo->refersToProposal",
                _source_reference_statuses(voting.get("refersTo")))

            for count in _source_children(voting, "count"):
                raw_kind = count.get("refersTo")
                kind_shape, _ = _source_reference_shape(raw_kind)
                if kind_shape == "absent":
                    count_status = "absent"
                elif kind_shape == "malformed":
                    count_status = "malformed"
                elif kind_shape == "placeholder":
                    count_status = "unresolved"
                elif raw_kind in {"#ta", "#nil", "#staon"} and href_status == "resolved":
                    count_status = "resolved"
                else:
                    count_status = "unresolved"
                add(count, "refersTo",
                    "analysis/voting/count/@refersTo->aggregate-count-category",
                    frozenset({count_status}))

    return inventory


def _source_person_statuses(raw: str | None,
                            elements_by_eid: Mapping[str, list[ET.Element]]) -> frozenset[str]:
    shape, target_eid = _source_reference_shape(raw)
    if shape == "absent":
        return frozenset({"absent"})
    if shape == "malformed":
        return frozenset({"malformed"})
    if shape == "placeholder":
        return frozenset({"unresolved"})
    targets = elements_by_eid.get(target_eid or "", [])
    if (len(targets) == 1 and _xml_local_name(targets[0]) == "TLCPerson"
            and targets[0].get("href") not in (None, "")):
        # Exact Member owner lookup depends on the transform's supplied resolver.
        return frozenset({"resolved", "unresolved"})
    return frozenset({"unresolved"})


def _validate_source_inventory(result: object, source_xml: bytes,
                               rows: list[dict]) -> None:
    source_hash = hashlib.sha256(source_xml).hexdigest()
    if source_hash != getattr(result, "source_sha256", None):
        _fail("exact source XML bytes SHA-256 does not match the Debate transform result")

    inventory = _source_inventory(source_xml)
    expected = Counter(item["key"] for item in inventory)
    actual = Counter(
        (row["slot"], row["source_pointer"], row["source_attribute_qname"],
         row["raw_reference"], row.get("source_eid"))
        for row in rows if row["slot"] in SOURCE_INVENTORY_SLOTS
    )
    if actual != expected:
        missing = sorted((repr(key), count) for key, count in (expected - actual).items())
        extra = sorted((repr(key), count) for key, count in (actual - expected).items())
        _fail("source inventory/reference report mismatch: "
              f"missing={missing} extra={extra}")

    allowed_statuses: dict[tuple, set[str]] = {}
    for item in inventory:
        allowed_statuses.setdefault(item["key"], set()).update(item["statuses"])
    for index, row in enumerate(rows):
        if row["slot"] not in SOURCE_INVENTORY_SLOTS:
            continue
        key = (row["slot"], row["source_pointer"], row["source_attribute_qname"],
               row["raw_reference"], row.get("source_eid"))
        allowed = allowed_statuses[key]
        if row["status"] not in allowed:
            _fail(f"reference_outcomes[{index}] status {row['status']!r} is inconsistent "
                  f"with its source slot; expected one of {sorted(allowed)}")


def _check_member_links(graph: Graph, member_graphs: Mapping[URIRef, Graph]) -> None:
    for predicate in MEMBER_REFERENCE_PREDICATES:
        for subject, target in graph.subject_objects(predicate):
            if not isinstance(target, URIRef):
                _fail(f"Member reference {predicate} must target an IRI")
            _absolute_iri(str(target), f"Member reference {predicate} target")
            _member_owner(target, member_graphs, label=str(predicate))


def _check_institutional_links(graph: Graph, houses: Graph, committees: Graph) -> None:
    work = next(graph.subjects(RDF.type, OIR.DebateRecord))
    body = _single_object(graph, work, OIR.recordOfBody,
                          "DebateRecord recordOfBody", required=False)
    term = _single_object(graph, work, OIR.recordOfHouseTerm,
                          "DebateRecord recordOfHouseTerm", required=False)
    house_term_house = _house_term(term, houses, label="recordOfHouseTerm") if term is not None else None

    if body is not None:
        if not isinstance(body, URIRef):
            _fail("recordOfBody must target an owner IRI")
        is_house = _type_is(houses, body, OIR.House)
        is_committee = _type_is(committees, body, MEMBERS.Committee)
        if is_house == is_committee:
            _fail("recordOfBody must resolve to exactly one House or Committee owner resource")
        if is_house:
            if body not in {
                URIRef("https://data.oireachtas.ie/house/dail"),
                URIRef("https://data.oireachtas.ie/house/seanad"),
            }:
                _fail("recordOfBody House target is not an established enduring House")
            if term is not None and body != house_term_house:
                _fail("recordOfBody House must agree with recordOfHouseTerm termOf")
        else:
            committee_term = _single_object(
                committees, body, MEMBERS.committeeInHouseTerm,
                "Committee committeeInHouseTerm",
            )
            committee_house = _house_term(
                committee_term, houses, label="Committee committeeInHouseTerm",
            )
            if term is not None and committee_term != term:
                _fail("recordOfHouseTerm must agree with the referenced Committee's owner HouseTerm")
            if not _type_is(houses, committee_house, OIR.House):
                _fail("Committee HouseTerm must resolve to an owner House")


def _validate_named_graph_ownership(result: object, dataset: Dataset,
                                    debate: Graph) -> tuple[Graph, Graph, dict[URIRef, Graph]]:
    if not isinstance(dataset, Dataset):
        _fail("validated owner data must be supplied as a named RDFLib Dataset")
    named = _named_graphs(dataset)
    debate_iri = URIRef(str(result.graph_iri))
    named_debate = named.get(debate_iri)
    if named_debate is None:
        _fail("named Dataset is missing the result's Work-owned Debate graph")
    if set(named_debate) != set(debate):
        _fail("named Debate graph must exactly equal the actual transform result graph")
    if getattr(debate, "identifier", None) != debate_iri:
        _fail("Debates transform result graph identifier must match graph_iri")

    houses = named.get(URIRef(HOUSES_GRAPH))
    committees = named.get(URIRef(COMMITTEES_GRAPH))
    if houses is None:
        houses = Graph(identifier=URIRef(HOUSES_GRAPH))
    if committees is None:
        committees = Graph(identifier=URIRef(COMMITTEES_GRAPH))
    member_graphs = {name: owner for name, owner in named.items() if _member_graph(name)}
    return houses, committees, member_graphs


def _validate_shacl(debate: Graph, owner_graphs: tuple[Graph, Graph,
                                                       Mapping[URIRef, Graph]]) -> None:
    houses, committees, member_graphs = owner_graphs
    joined = Graph()
    for source in (debate, houses, committees, *member_graphs.values()):
        for triple in source:
            joined.add(triple)
    # pySHACL 0.30 currently walks a Dataset through RDFLib's deprecated
    # ``default_context`` compatibility property for each SHACL lookup.  Keep
    # that dependency warning from flooding validation of larger Debate graphs;
    # all SHACL results and failures are still handled normally.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Dataset.default_context is deprecated",
            category=DeprecationWarning,
        )
        conforms, _, report = validate(
            joined,
            shacl_graph=RESOURCES.joinpath("debates-integration.ttl").read_text(),
            shacl_graph_format="turtle",
            inference="none",
            abort_on_first=False,
        )
    if not conforms:
        _fail("Debates integration SHACL validation failed:\n" + str(report))


def _validate_vote_quality(graph: Graph) -> None:
    for division in graph.subjects(RDF.type, OIR.Division):
        groups = [set(graph.objects(division, predicate)) for predicate in VOTE_PREDICATES]
        if any(groups[left] & groups[right]
               for left in range(len(groups)) for right in range(left + 1, len(groups))):
            _fail(f"a Member cannot have conflicting individual vote outcomes in one Division: {division}")


def validate_debates_integration(result: object, validated_dataset: Dataset, *,
                                 source_xml: bytes | None = None) -> None:
    """Validate one actual Debate graph against joined, validated owner graphs.

    ``validated_dataset`` must contain the exact result graph under
    ``result.graph_iri``, the Houses graph under the settled Houses graph IRI,
    the shared Committees graph under its settled IRI, and zero or more named
    Member graphs using their established ``/graph/member/{memberCode}``
    identities. A missing owner type fails closed for every RDF reference that
    needs that owner. The owner graphs are expected to have passed their
    respective source-to-RDF, datatype, SHACL, and quality validators already.

    When supplied, ``source_xml`` must be the exact immutable AKN byte string
    transformed into ``result``. The source-aware pass recomputes its SHA-256,
    inventories the currently contracted source-reference slots, and checks
    source-determinable outcome statuses. If omitted, validation is limited to
    the result's declared digest and the report/RDF coherence; it cannot detect
    missing report rows or prove that the declared digest matches source bytes.
    """
    if source_xml is not None and not isinstance(source_xml, bytes):
        _fail("source_xml must be the exact AKN XML bytes or None")
    try:
        debate = result.graph
    except AttributeError as error:
        raise ValueError("Debates transform result must expose graph") from error
    if not isinstance(debate, Graph):
        _fail("Debates transform result graph must be an RDFLib Graph")

    # Keep Tranche 2's independent graph-structure boundary as the first gate.
    validate_debates(result)
    owners = _validate_named_graph_ownership(result, validated_dataset, debate)
    _validate_shacl(debate, owners)
    _check_member_links(debate, owners[2])
    _check_institutional_links(debate, owners[0], owners[1])
    rows = _validate_report(result, debate)
    _validate_report_edges(rows, debate)
    if source_xml is not None:
        _validate_source_inventory(result, source_xml, rows)
    _validate_vote_quality(debate)
