"""Bounded mention detection and conservative entity resolution for the PoC.

This module contains no production ETL behavior. It consumes text extracted
offline from hash-pinned AKN Works and identity candidates built only from
validated local owner/registry data. The generated RDF is always provisional.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import html
import json
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
import xml.etree.ElementTree as ET

from rdflib import Dataset, Graph, Literal, Namespace, URIRef
from rdflib.compare import to_canonical_graph
from rdflib.namespace import FOAF, PROV, RDF, RDFS, SKOS, XSD


OIR = Namespace("https://data.oireachtas.ie/ontology#")
MEMBERS = Namespace("https://data.oireachtas.ie/ontology/members#")
ELI = Namespace("http://data.europa.eu/eli/ontology#")
ELIDL = Namespace("http://data.europa.eu/eli/eli-draft-legislation-ontology#")
POC = Namespace("https://data.oireachtas.ie/poc/entity-linking#")
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
HTML_TAG_RE = re.compile(r"<[^>]*>")
MAX_CONTRIBUTIONS = 1_000
BASELINE_METHOD = "exact-name-identifier-v1"
CONTEXT_METHOD = "context-aware-conservative-v1"
GENERIC_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "Member": (re.compile(r"(?<!\w)(?:the|a|an)\s+(?:Deputy|Senator)\b", re.I),),
    "Bill": (re.compile(r"(?<!\w)(?:the|this|that)\s+Bill\b", re.I),),
    "NamedOffice": (re.compile(r"(?<!\w)(?:the|a|an)\s+Minister(?:\s+of\s+State)?\b", re.I),),
    "AdministrativeUnit": (re.compile(r"(?<!\w)(?:the|this|that)\s+Department\b", re.I),),
}
OFFICE_CONTEXT_RE = re.compile(
    r"\b(?:office|post|position)\b",
    re.I,
)
SENTENCE_BREAK_RE = re.compile(r"[.!?](?:[\"'’”\])}]*)\s+|\n+")
OUT_OF_REGISTRY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    # These intentionally recognise only explicit, title-led forms. They do
    # not attempt general NER or infer an identity from topic/context.
    "Member": (
        re.compile(
            r"\b(?:Deputy|Senator)\s+(?!(?:Speaker|Chair|Chairperson|Leader|"
            r"Taoiseach|Tánaiste|Minister|President)\b)"
            r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’\-]*(?:\s+[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’\-]*){0,3}"
        ),
    ),
    "Bill": (
        re.compile(
            r"\b(?!(?i:the|this|that|a|an)\s+)[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’&\-]*(?:\s+(?:(?:and|of|for|the)\s+)?"
            r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’&\-]*){0,5}\s+Bill(?:\s+\d{4})?\b"
        ),
    ),
    "NamedOffice": (
        re.compile(
            r"\b(?:Minister\s+(?:for|at|of(?!\s+State\b))|"
            r"Minister\s+of\s+State\s+(?:for|of|at))\s+(?:the\s+)?"
            r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’&\-]*(?:\s+(?:(?:and|of|for|the)\s+)?"
            r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’&\-]*){0,5}"
        ),
    ),
    "AdministrativeUnit": (
        re.compile(
            r"\b(?:Department|Dept\.?|Ministry)\s+(?:of|for)\s+(?:the\s+)?"
            r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’&\-]*(?:\s+(?:(?:and|of|for|the)\s+)?"
            r"[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-Þ'’&\-]*){0,5}"
        ),
    ),
}


@dataclass(frozen=True)
class Alias:
    text: str
    kind: str = "name"
    valid_from: str | None = None
    valid_to: str | None = None


@dataclass(frozen=True)
class Identity:
    iri: str
    category: str
    aliases: tuple[Alias, ...]
    source_graph: str
    validity: tuple[tuple[str, str | None, str | None, str | None, int | None], ...] = ()
    valid_from: str | None = None
    valid_to: str | None = None
    bill_first_event: str | None = None


@dataclass(frozen=True)
class Token:
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class Detection:
    mention_iri: str
    contribution_iri: str
    category: str
    start: int
    end: int
    surface: str
    candidates: tuple[str, ...]
    matched_aliases: tuple[tuple[str, str, str], ...]
    generic: bool = False


@dataclass(frozen=True)
class Decision:
    detection: Detection
    status: str
    target_iri: str | None
    candidate_iris: tuple[str, ...]
    reason: str
    evidence: str
    speaker_overlap: bool
    structured_bill_overlap: bool


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sorted_ntriples(graph: Graph) -> bytes:
    rows = sorted(f"{s.n3()} {p.n3()} {o.n3()} ." for s, p, o in graph)
    return ("\n".join(rows) + ("\n" if rows else "")).encode("utf-8")


def canonical_graph_bytes(graph: Graph) -> bytes:
    """Serialize graph content canonically across RDF 1.1 string spellings.

    Fuseki/Jena serializes ``xsd:string`` literals as simple literals. Those
    are equivalent in RDF 1.1; normalize that spelling and blank-node labels
    for integrity comparison without changing the stored RDF graph.
    """
    normalized = Graph()
    for subject, predicate, obj in graph:
        if isinstance(obj, Literal) and obj.datatype == XSD.string and obj.language is None:
            obj = Literal(str(obj))
        normalized.add((subject, predicate, obj))
    return sorted_ntriples(to_canonical_graph(normalized))


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _element_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def speech_text(speech: ET.Element) -> str:
    """Extract only spoken paragraph content; never serialize this to RDF."""
    paragraphs = [_element_text(node) for node in speech.iter() if _local_name(node) == "p"]
    return " ".join(text for text in paragraphs if text)


def _tokens(text: str) -> tuple[Token, ...]:
    return tuple(
        Token(unicodedata.normalize("NFKC", match.group()).casefold(), match.start(), match.end())
        for match in TOKEN_RE.finditer(text)
    )


def normalized_words(text: str) -> tuple[str, ...]:
    return tuple(token.value for token in _tokens(text))


def phrase_spans(text: str, phrase: str) -> list[tuple[int, int]]:
    """Find contiguous whole-word matches while retaining source code-point offsets."""
    source_tokens = _tokens(text)
    phrase_tokens = normalized_words(phrase)
    if not phrase_tokens or len(phrase_tokens) > len(source_tokens):
        return []
    hits: list[tuple[int, int]] = []
    width = len(phrase_tokens)
    for offset in range(len(source_tokens) - width + 1):
        if tuple(token.value for token in source_tokens[offset : offset + width]) == phrase_tokens:
            hits.append((source_tokens[offset].start, source_tokens[offset + width - 1].end))
    return hits


def _strip_html(value: object) -> str:
    return " ".join(html.unescape(HTML_TAG_RE.sub(" ", str(value or ""))).split())


def build_candidates(
    *,
    member_source: Mapping[str, Any],
    member_graph: Graph,
    bill_source: Mapping[str, Any],
    bill_graph: Graph,
    registry: Mapping[str, Any],
    office_graph: Graph,
    unit_graph: Graph,
    member_graph_iri: str,
    bill_graph_iri: str,
    offices_graph_iri: str,
    units_graph_iri: str,
) -> tuple[list[Identity], dict[str, Any]]:
    """Build candidates from already-validated exact local owner data."""
    data = member_source["member"]
    member_iri = str(data["uri"])
    member_labels = {str(value) for value in member_graph.objects(URIRef(member_iri), FOAF.name)}
    member_labels.update({str(data.get(key, "")).strip() for key in ("showAs", "fullName") if data.get(key)})
    member_aliases = tuple(Alias(value) for value in sorted(member_labels) if value)
    member_aliases += tuple(
        Alias(str(data[key]), "identifier")
        for key in ("memberCode", "pId")
        if data.get(key)
    )
    membership_rows: list[tuple[str, str | None, str | None, str | None, int | None]] = []
    for wrapped in data.get("memberships", []):
        membership = wrapped["membership"]
        house = membership.get("house", {})
        dates = membership.get("dateRange", {})
        start = str(dates.get("start", ""))[:10] or None
        end = str(dates["end"])[:10] if dates.get("end") else None
        membership_rows.append((str(house.get("houseCode", "")), start, end,
                                str(house.get("houseNo", "")) or None,
                                int(house["houseNo"]) if str(house.get("houseNo", "")).isdigit() else None))

    bill_data = bill_source["bill"]
    bill_iri = str(bill_data["uri"])
    bill_aliases: list[Alias] = []
    for key in ("shortTitleEn", "shortTitleGa", "longTitleEn", "longTitleGa"):
        value = _strip_html(bill_data.get(key))
        if value and Alias(value) not in bill_aliases:
            bill_aliases.append(Alias(value))
    bill_year, bill_number = str(bill_data["billYear"]), str(bill_data["billNo"])
    bill_aliases.append(Alias(f"Bill {bill_year}/{bill_number}", "identifier"))
    bill_aliases.append(Alias(f"{bill_year}/{bill_number}", "identifier"))
    bill_dates = [
        str(date.get("date", ""))[:10]
        for stage in bill_data.get("stages", [])
        for date in stage.get("event", {}).get("dates", [])
        if date.get("date")
    ]
    first_bill_event = min(bill_dates) if bill_dates else None

    candidates: list[Identity] = [
        Identity(member_iri, "Member", member_aliases, member_graph_iri,
                 validity=tuple(membership_rows)),
        Identity(bill_iri, "Bill", tuple(bill_aliases), bill_graph_iri,
                 bill_first_event=first_bill_event),
    ]

    for unit in registry["administrative_units"]:
        iri = f"https://data.oireachtas.ie/administrative-unit/{unit['key']}"
        if (URIRef(iri), RDF.type, Namespace("https://data.oireachtas.ie/ontology/members#").AdministrativeUnit) not in unit_graph:
            raise ValueError(f"registered AdministrativeUnit lacks a typed owner description: {iri}")
        aliases: dict[str, Alias] = {}
        for label in (unit.get("label_en"), unit.get("label_ga")):
            if label:
                aliases[str(label)] = Alias(str(label))
        for alias in unit.get("aliases", []):
            label = str(alias.get("label", "")).strip()
            if label:
                aliases[label] = Alias(label)
        candidates.append(Identity(iri, "AdministrativeUnit", tuple(aliases[key] for key in sorted(aliases)), units_graph_iri))

    for office in registry["offices"]:
        iri = f"https://data.oireachtas.ie/office/{office['key']}"
        if (URIRef(iri), RDF.type, Namespace("https://data.oireachtas.ie/ontology/members#").NamedOffice) not in office_graph:
            raise ValueError(f"registered NamedOffice lacks a typed owner description: {iri}")
        aliases: dict[str, Alias] = {}
        source_aliases = list(office.get("aliases", []))
        alias_labels = {str(item.get("label", "")).strip() for item in source_aliases}
        for label in (office.get("label_en"), office.get("label_ga")):
            if label and str(label).strip() not in alias_labels:
                aliases[str(label).strip()] = Alias(str(label).strip())
        for alias in source_aliases:
            label = str(alias.get("label", "")).strip()
            validity = alias.get("validity", {})
            if label:
                aliases[label] = Alias(
                    label, "name",
                    str(validity.get("start"))[:10] if validity.get("start") else None,
                    str(validity.get("end"))[:10] if validity.get("end") else None,
                )
        candidates.append(Identity(iri, "NamedOffice", tuple(aliases[key] for key in sorted(aliases)), offices_graph_iri))

    if not candidates or any(not candidate.aliases for candidate in candidates):
        raise ValueError("every PoC identity requires at least one source-backed name/identifier")
    for candidate in candidates:
        if candidate.category == "Member" and (URIRef(candidate.iri), RDF.type, OIR.Member) not in member_graph:
            raise ValueError(f"Member candidate is not an existing validated Member: {candidate.iri}")
        if candidate.category == "Bill" and not any(subject == URIRef(candidate.iri) for subject in bill_graph.subjects(RDF.type, None)):
            raise ValueError(f"Bill candidate is not described in its validated Bill graph: {candidate.iri}")

    count_by_category = Counter(item.category for item in candidates)
    inventory = {
        "candidate_identities_by_category": dict(sorted(count_by_category.items())),
        "candidates": [
            {
                "iri": item.iri,
                "category": item.category,
                "source_graph": item.source_graph,
                "aliases": [asdict(alias) for alias in item.aliases],
                "membership_intervals": [list(row) for row in item.validity],
                "valid_from": item.valid_from,
                "bill_first_event": item.bill_first_event,
            }
            for item in sorted(candidates, key=lambda value: (value.category, value.iri))
        ],
    }
    return candidates, inventory


def _mention_iri(contribution_iri: str, category: str, start: int, end: int, surface: str) -> str:
    key = sha256_bytes(f"{contribution_iri}\0{category}\0{start}\0{end}\0{surface}".encode("utf-8"))
    return f"https://data.oireachtas.ie/poc/entity-linking/mention/{key}"


def detect_mentions(record: Mapping[str, Any], candidates: Sequence[Identity]) -> list[Detection]:
    """Shared, exact whole-token detector; candidate retrieval remains typed."""
    text = str(record["text"])
    grouped: dict[tuple[str, int, int], dict[str, Alias]] = defaultdict(dict)
    for candidate in candidates:
        for alias in candidate.aliases:
            for start, end in phrase_spans(text, alias.text):
                # Identifier-only hits are accepted only where the raw source
                # also makes their category explicit, not for incidental dates.
                if alias.kind == "identifier" and candidate.category == "Bill" \
                        and re.fullmatch(r"\d{4}/\d{1,3}", alias.text) and not re.search(
                            r"\bBill(?:\s+(?:No\.?\s*)?)?\s*$",
                            text[max(0, start - 16) : start], flags=re.I
                        ):
                    continue
                grouped[(candidate.category, start, end)][candidate.iri] = alias

    detections: list[Detection] = []
    for (category, start, end), aliases_by_identity in grouped.items():
        surface = text[start:end]
        identities = tuple(sorted(aliases_by_identity))
        matched = tuple(sorted(
            (iri, aliases_by_identity[iri].text, aliases_by_identity[iri].kind)
            for iri in identities
        ))
        detections.append(Detection(
            _mention_iri(str(record["contribution_iri"]), category, start, end, surface),
            str(record["contribution_iri"]), category, start, end, surface,
            identities, matched, False,
        ))

    # Recognise a small set of title-led names outside this deliberately tiny
    # identity inventory. This is evidence of an unsupported named surface,
    # not permission to create a target IRI.
    for category, patterns in OUT_OF_REGISTRY_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                start, end = match.span()
                if any(
                    category == item.category and start < item.end and end > item.start
                    for item in detections
                ):
                    continue
                surface = text[start:end]
                detections.append(Detection(
                    _mention_iri(str(record["contribution_iri"]), category, start, end, surface),
                    str(record["contribution_iri"]), category, start, end, surface,
                    (), (), False,
                ))

    # Record generic/anaphoric cues as mentions, but never attach a candidate
    # without an explicit, unique source-local antecedent. Suppress a shorter
    # generic token sequence contained in a more specific named mention.
    specific = {(item.category, item.start, item.end) for item in detections}
    for category, patterns in GENERIC_PATTERNS.items():
        for pattern in patterns:
            for match in pattern.finditer(text):
                start, end = match.span()
                overlaps_specific = any(
                    category == item.category
                    and start <= item.end
                    and end >= item.start
                    and item.start <= end + 1
                    for item in detections
                )
                if overlaps_specific:
                    continue
                surface = text[start:end]
                detections.append(Detection(
                    _mention_iri(str(record["contribution_iri"]), category, start, end, surface),
                    str(record["contribution_iri"]), category, start, end, surface,
                    (), (), True,
                ))
    return sorted(detections, key=lambda item: (item.category, item.start, item.end, item.mention_iri))


def _member_valid_at(candidate: Identity, date: str | None) -> tuple[bool, str]:
    if not date:
        return False, "contribution_date_unavailable"
    for _house, start, end, _house_no_text, _house_no in candidate.validity:
        if start and start <= date and (not end or date <= end):
            return True, "member_membership_interval"
    return False, "outside_valid_member_membership"


def _office_context(text: str, start: int, end: int) -> bool:
    """Require explicit office wording in the same sentence and nearby."""
    sentence_start = 0
    for match in SENTENCE_BREAK_RE.finditer(text, 0, start):
        sentence_start = match.end()
    sentence_end = len(text)
    match = SENTENCE_BREAK_RE.search(text, end)
    if match:
        sentence_end = match.start()
    context = text[sentence_start:sentence_end]
    for cue in OFFICE_CONTEXT_RE.finditer(context):
        cue_start, cue_end = sentence_start + cue.start(), sentence_start + cue.end()
        distance = start - cue_end if cue_end <= start else cue_start - end if cue_start >= end else 0
        if distance <= 80:
            return True
    return False


def resolve_detection(
    detection: Detection,
    record: Mapping[str, Any],
    candidates_by_iri: Mapping[str, Identity],
    method: str,
) -> Decision:
    speaker_overlap = any(target in detection.candidates for target in record.get("speaker_targets", ()))
    structured_bill_overlap = any(
        target in record.get("structured_bill_targets", ()) for target in detection.candidates
    )
    if detection.generic:
        return Decision(detection, "abstained", None, (), "generic_reference_no_unique_antecedent",
                        "generic-anaphoric-reference", speaker_overlap, structured_bill_overlap)

    if not detection.candidates:
        return Decision(detection, "out-of-registry", None, (), "no_validated_candidate",
                        "exact-surface-without-owner", speaker_overlap, structured_bill_overlap)

    if method == BASELINE_METHOD:
        if len(detection.candidates) != 1:
            return Decision(detection, "ambiguous", None, detection.candidates,
                            "multiple_exact_name_candidates", "unique-exact-name-or-identifier-required",
                            speaker_overlap, structured_bill_overlap)
        target = detection.candidates[0]
        return Decision(detection, "resolved", target, detection.candidates,
                        "unique_exact_name_or_identifier", "exact-normalized-surface-match",
                        speaker_overlap, structured_bill_overlap)

    if method != CONTEXT_METHOD:
        raise ValueError(f"unknown entity-linking method: {method}")

    text = str(record["text"])
    date = str(record.get("date", ""))[:10] or None
    eligible: list[str] = []
    rejection_reasons: list[str] = []
    for candidate_iri in detection.candidates:
        candidate = candidates_by_iri[candidate_iri]
        matched_aliases = [row for row in detection.matched_aliases if row[0] == candidate_iri]
        aliases = [next(alias for alias in candidate.aliases if alias.text == row[1]) for row in matched_aliases]
        if candidate.category == "Member":
            valid, reason = _member_valid_at(candidate, date)
            if not valid:
                rejection_reasons.append(reason)
                continue
        elif candidate.category == "Bill":
            if candidate.bill_first_event and date and date < candidate.bill_first_event:
                rejection_reasons.append("contribution_predates_first_bill_event")
                continue
        elif candidate.category == "NamedOffice":
            alias_valid = any(
                (not alias.valid_from or not date or date >= alias.valid_from)
                and (not alias.valid_to or not date or date <= alias.valid_to)
                for alias in aliases
            )
            if not alias_valid:
                rejection_reasons.append("outside_reviewed_alias_validity")
                continue
            if not _office_context(text, detection.start, detection.end):
                rejection_reasons.append("officeholder_vs_office_ambiguous")
                continue
        eligible.append(candidate_iri)

    if len(eligible) == 1:
        target = eligible[0]
        candidate = candidates_by_iri[target]
        if candidate.category == "Member":
            evidence = "exact-member-name-and-valid-membership-period"
        elif candidate.category == "Bill":
            evidence = "exact-bill-title-or-identifier-after-first-source-event"
        elif candidate.category == "NamedOffice":
            evidence = "exact-reviewed-office-alias-validity-and-explicit-office-context"
        else:
            evidence = "exact-reviewed-administrative-unit-name"
        return Decision(detection, "resolved", target, tuple(eligible), "contextual-evidence-unique",
                        evidence, speaker_overlap, structured_bill_overlap)
    if len(eligible) > 1:
        return Decision(detection, "ambiguous", None, tuple(sorted(eligible)),
                        "context_left_multiple_candidates", "context-did-not-disambiguate",
                        speaker_overlap, structured_bill_overlap)
    reason = rejection_reasons[0] if rejection_reasons else "no_context_supported_candidate"
    status = "ambiguous" if any("ambiguous" in value for value in rejection_reasons) else "abstained"
    return Decision(detection, status, None, detection.candidates, reason,
                    "conservative-context-rule", speaker_overlap, structured_bill_overlap)


def decision_rows(
    records: Sequence[Mapping[str, Any]], candidates: Sequence[Identity], method: str
) -> list[dict[str, Any]]:
    by_iri = {candidate.iri: candidate for candidate in candidates}
    rows: list[dict[str, Any]] = []
    for record in records:
        for detection in detect_mentions(record, candidates):
            decision = resolve_detection(detection, record, by_iri, method)
            rows.append({
                "mention_iri": detection.mention_iri,
                "contribution_iri": detection.contribution_iri,
                "work_iri": record["work_iri"],
                "source_id": record["source_id"],
                "source_sha256": record["source_sha256"],
                "source_pointer": record["source_pointer"],
                "text_sha256": record["text_sha256"],
                "category": detection.category,
                "start_offset": detection.start,
                "end_offset": detection.end,
                "surface": detection.surface,
                "generic_reference": detection.generic,
                "matched_aliases": [list(value) for value in detection.matched_aliases],
                "candidate_iris": list(decision.candidate_iris),
                "status": decision.status,
                "target_iri": decision.target_iri,
                "reason": decision.reason,
                "evidence": decision.evidence,
                "speaker_overlap": decision.speaker_overlap,
                "structured_bill_overlap": decision.structured_bill_overlap,
                "method": method,
            })
    return sorted(rows, key=lambda row: (row["source_id"], row["contribution_iri"], row["start_offset"], row["category"]))


def build_derived_graphs(
    records: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    *,
    mention_graph_iri: str,
    link_graph_iri: str,
    method: str,
    run_id: str,
    split: str,
    input_hash: str,
) -> tuple[Graph, Graph]:
    mentions = Graph(identifier=URIRef(mention_graph_iri))
    links = Graph(identifier=URIRef(link_graph_iri))
    run_iri = URIRef(f"https://data.oireachtas.ie/poc/entity-linking/run/{run_id}/{method}/{split}")
    for graph in (mentions, links):
        graph.add((run_iri, RDF.type, POC.EntityLinkingRun))
        graph.add((run_iri, POC.method, Literal(method)))
        graph.add((run_iri, POC.methodVersion, Literal(method)))
        graph.add((run_iri, POC.inputSampleChecksum, Literal(input_hash)))
        graph.add((run_iri, POC.runIdentifier, Literal(run_id)))
        graph.add((run_iri, POC.provisionalStatus, Literal("provisional")))

    record_by_iri = {str(record["contribution_iri"]): record for record in records}
    for row in rows:
        mention = URIRef(str(row["mention_iri"]))
        decision = URIRef(link_graph_iri + "/decision/" + sha256_bytes(str(row["mention_iri"]).encode("utf-8")))
        record = record_by_iri[str(row["contribution_iri"])]
        mentions.add((mention, RDF.type, POC.EntityMention))
        mentions.add((mention, POC.contribution, URIRef(str(row["contribution_iri"]))))
        mentions.add((mention, POC.work, URIRef(str(row["work_iri"]))))
        mentions.add((mention, POC.entityCategory, Literal(str(row["category"]))))
        mentions.add((mention, POC.surfaceForm, Literal(str(row["surface"]))))
        mentions.add((mention, POC.startOffset, Literal(int(row["start_offset"]), datatype=XSD.integer)))
        mentions.add((mention, POC.endOffset, Literal(int(row["end_offset"]), datatype=XSD.integer)))
        mentions.add((mention, POC.sourcePointer, Literal(str(row["source_pointer"]))))
        mentions.add((mention, POC.sourceChecksum, Literal(str(row["source_sha256"]))))
        mentions.add((mention, POC.textChecksum, Literal(str(row["text_sha256"]))))
        mentions.add((mention, PROV.wasGeneratedBy, run_iri))

        links.add((mention, POC.hasResolution, decision))
        links.add((decision, RDF.type, POC.EntityLinkDecision))
        links.add((decision, POC.forMention, mention))
        links.add((decision, POC.status, Literal(str(row["status"]))))
        links.add((decision, POC.method, Literal(method)))
        links.add((decision, POC.methodVersion, Literal(method)))
        links.add((decision, POC.evidence, Literal(str(row["evidence"]))))
        links.add((decision, POC.reason, Literal(str(row["reason"]))))
        links.add((decision, POC.sourceChecksum, Literal(str(row["source_sha256"]))))
        links.add((decision, POC.textChecksum, Literal(str(row["text_sha256"]))))
        links.add((decision, POC.runIdentifier, Literal(run_id)))
        links.add((decision, PROV.wasGeneratedBy, run_iri))
        links.add((decision, POC.overlapsStructuredSpeaker,
                   Literal(bool(row["speaker_overlap"]), datatype=XSD.boolean)))
        links.add((decision, POC.overlapsStructuredBillReference,
                   Literal(bool(row["structured_bill_overlap"]), datatype=XSD.boolean)))
        for candidate in row["candidate_iris"]:
            links.add((decision, POC.candidateEntity, URIRef(str(candidate))))
        if row["target_iri"]:
            target = URIRef(str(row["target_iri"]))
            links.add((decision, POC.resolvedEntity, target))
            links.add((decision, POC.provisionalLink, Literal(True, datatype=XSD.boolean)))
        if row["status"] in {"ambiguous", "abstained", "out-of-registry"}:
            links.add((decision, POC.provisionalLink, Literal(False, datatype=XSD.boolean)))
        if record.get("speaker_targets"):
            links.add((decision, POC.structuredSpeakerCount,
                       Literal(len(record["speaker_targets"]), datatype=XSD.integer)))
    return mentions, links


def score_reference(
    reference: Mapping[str, Any],
    prediction_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    methods: Sequence[str],
) -> dict[str, Any]:
    """Compare exact annotated spans and supported targets; never extrapolate."""
    if not reference.get("blind_to_method_outputs"):
        raise ValueError("reference set is not marked blind to method outputs")
    rows = reference.get("contributions", [])
    known = {str(row["contribution_iri"]) for row in rows}
    positive_labels = {
        "explicit-identity-mention",
        "generic-unresolved-reference",
        "ambiguous-office-or-holder",
        "out-of-registry-named-entity",
    }
    output: dict[str, Any] = {
        "reviewer_type": reference.get("reviewer_type", "unspecified"),
        "independent_human_review": bool(reference.get("independent_human_review", False)),
        "reviewed_contributions": len(rows),
        "judgments": {},
    }
    for method in methods:
        predicted = [
            row for row in prediction_rows[method]
            if str(row["contribution_iri"]) in known
        ]
        method_result: dict[str, Any] = {}
        for category in ("Member", "Bill", "NamedOffice", "AdministrativeUnit"):
            refs_by_span: dict[tuple[str, int, int], list[Mapping[str, Any]]] = defaultdict(list)
            uncertain_spans: set[tuple[str, int, int]] = set()
            for row in rows:
                contribution_iri = str(row["contribution_iri"])
                for mention in row.get("mentions", []):
                    if mention.get("category") != category:
                        continue
                    key = (contribution_iri, int(mention["start_offset"]), int(mention["end_offset"]))
                    if mention.get("label") in positive_labels:
                        refs_by_span[key].append(mention)
                    elif mention.get("label") == "uncertain":
                        uncertain_spans.add(key)
            if set(refs_by_span) & uncertain_spans:
                raise ValueError("a reference span cannot be both positive and uncertain")
            all_category_predictions = [row for row in predicted if row["category"] == category]
            uncertain_prediction_indices = {
                index for index, prediction in enumerate(all_category_predictions)
                if any(
                    str(prediction["contribution_iri"]) == contribution
                    and int(prediction["start_offset"]) < uncertain_end
                    and int(prediction["end_offset"]) > uncertain_start
                    for contribution, uncertain_start, uncertain_end in uncertain_spans
                )
            }
            category_predictions = [
                row for index, row in enumerate(all_category_predictions)
                if index not in uncertain_prediction_indices
            ]
            pred_by_span = {
                (str(row["contribution_iri"]), int(row["start_offset"]), int(row["end_offset"])): row
                for row in category_predictions
            }
            true_positive = sum(key in pred_by_span for key in refs_by_span)
            false_positive = sum(key not in refs_by_span for key in pred_by_span)
            missed = sum(key not in pred_by_span for key in refs_by_span)
            label_counts: dict[str, dict[str, int]] = {}
            for label in sorted(positive_labels):
                label_keys = {
                    key for key, mentions in refs_by_span.items()
                    if any(mention.get("label") == label for mention in mentions)
                }
                label_counts[label] = {
                    "reference_spans": len(label_keys),
                    "detected_spans": sum(key in pred_by_span for key in label_keys),
                    "missed_spans": sum(key not in pred_by_span for key in label_keys),
                }

            supported_refs = [
                (key, mention)
                for key, mentions in refs_by_span.items()
                for mention in mentions
                if mention.get("label") == "explicit-identity-mention" and mention.get("target_iri")
            ]
            supported_targets = {key: str(mention["target_iri"]) for key, mention in supported_refs}
            if len(supported_targets) != len(supported_refs):
                raise ValueError("duplicate supported reference spans make resolution scoring ambiguous")
            correct_targets = wrong_targets = unsupported_resolved = 0
            ambiguous = out_of_registry = abstained = missed_detection = 0
            boundary_mismatch_alignment = alignment_ambiguous = 0
            aligned_predictions: dict[tuple[str, int, int], tuple[int, Mapping[str, Any]] | None] = {}
            used_prediction_indices: set[int] = set()
            for key, _mention in sorted(supported_refs, key=lambda item: item[0]):
                contribution_iri, ref_start, ref_end = key
                candidates: list[tuple[tuple[int, int, int], int, Mapping[str, Any]]] = []
                for index, prediction in enumerate(category_predictions):
                    if index in used_prediction_indices or str(prediction["contribution_iri"]) != contribution_iri:
                        continue
                    pred_start, pred_end = int(prediction["start_offset"]), int(prediction["end_offset"])
                    contains = (
                        (pred_start <= ref_start and pred_end >= ref_end)
                        or (ref_start <= pred_start and ref_end >= pred_end)
                    )
                    if not contains:
                        continue
                    overlap = min(pred_end, ref_end) - max(pred_start, ref_start)
                    score = (int(pred_start == ref_start and pred_end == ref_end), overlap,
                             -abs((pred_end - pred_start) - (ref_end - ref_start)))
                    candidates.append((score, index, prediction))
                if not candidates:
                    aligned_predictions[key] = None
                    continue
                best_score = max(candidate[0] for candidate in candidates)
                best = [candidate for candidate in candidates if candidate[0] == best_score]
                if len(best) != 1:
                    aligned_predictions[key] = None
                    alignment_ambiguous += 1
                    continue
                _, index, prediction = best[0]
                used_prediction_indices.add(index)
                aligned_predictions[key] = (index, prediction)
                if (int(prediction["start_offset"]), int(prediction["end_offset"])) != (ref_start, ref_end):
                    boundary_mismatch_alignment += 1

            accepted_predictions = [
                (index, prediction) for index, prediction in enumerate(category_predictions)
                if prediction.get("target_iri")
            ]
            aligned_target_by_index = {
                index: supported_targets[key]
                for key, aligned in aligned_predictions.items()
                if aligned is not None
                for index in (aligned[0],)
            }
            for index, prediction in accepted_predictions:
                expected_target = aligned_target_by_index.get(index)
                if expected_target and prediction.get("target_iri") == expected_target:
                    correct_targets += 1
                elif expected_target:
                    wrong_targets += 1
                else:
                    unsupported_resolved += 1
            for key, mention in supported_refs:
                aligned = aligned_predictions.get(key)
                if aligned is None:
                    missed_detection += 1
                    continue
                _index, prediction = aligned
                if prediction.get("target_iri"):
                    continue
                elif prediction.get("status") == "ambiguous":
                    ambiguous += 1
                elif prediction.get("status") == "out-of-registry":
                    out_of_registry += 1
                else:
                    abstained += 1

            resolved = sum(
                1 for row in category_predictions
                if row["category"] == category and row.get("target_iri")
            )
            precision_denominator = len(accepted_predictions)
            method_result[category] = {
                "detection": {
                    "reference_spans": len(refs_by_span),
                    "uncertain_reference_spans": len(uncertain_spans),
                    "predictions_excluded_by_uncertainty": len(uncertain_prediction_indices),
                    "predicted_spans": len(pred_by_span),
                    "true_positive": true_positive,
                    "false_positive": false_positive,
                    "missed_reference_spans": missed,
                    "precision": round(true_positive / (true_positive + false_positive), 4)
                    if true_positive + false_positive else None,
                    "recall": round(true_positive / len(refs_by_span), 4) if refs_by_span else None,
                    "by_reference_label": label_counts,
                },
                "resolution": {
                    "eligible_supported_explicit_mentions": len(supported_refs),
                    "correct_target": correct_targets,
                    "wrong_target": wrong_targets,
                    "unsupported_resolved_prediction": unsupported_resolved,
                    "ambiguous": ambiguous,
                    "out_of_registry": out_of_registry,
                    "abstained": abstained,
                    "missed_detection": missed_detection,
                    "boundary_mismatch_alignment": boundary_mismatch_alignment,
                    "ambiguous_alignment": alignment_ambiguous,
                    "resolved_predictions_in_reviewed_contributions": resolved,
                    "precision_on_accepted_links": round(correct_targets / precision_denominator, 4)
                    if precision_denominator else None,
                    "coverage_of_eligible_mentions": round(
                        (correct_targets + wrong_targets) / len(supported_refs), 4
                    ) if supported_refs else None,
                },
            }
        output["judgments"][method] = method_result
    return output


def method_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_category: dict[str, Counter[str]] = defaultdict(Counter)
    source_category: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        category = str(row["category"])
        status = str(row["status"])
        by_category[category][status] += 1
        by_category[category]["mentions"] += 1
        source_category[str(row["source_id"])][category][status] += 1
        source_category[str(row["source_id"])][category]["mentions"] += 1
        if row.get("generic_reference"):
            by_category[category]["generic_references"] += 1
            source_category[str(row["source_id"])][category]["generic_references"] += 1
        elif row.get("target_iri"):
            by_category[category]["named_resolved"] += 1
            source_category[str(row["source_id"])][category]["named_resolved"] += 1
        if row.get("speaker_overlap"):
            by_category[category]["structured_speaker_overlap"] += 1
        if row.get("structured_bill_overlap"):
            by_category[category]["structured_bill_overlap"] += 1
    return {
        "by_category": {key: dict(sorted(value.items())) for key, value in sorted(by_category.items())},
        "by_source_category": {
            source: {category: dict(sorted(counts.items())) for category, counts in sorted(categories.items())}
            for source, categories in sorted(source_category.items())
        },
    }
