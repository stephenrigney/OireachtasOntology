"""Bounded, disposable EuroVoc enrichment experiment.

This module deliberately sits outside the production ETL package. It reuses
the existing Debates transformer and validated Houses owner graph, but writes
all topic suggestions to independent PoC graphs and never writes transcripts
to RDF.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Iterable, Mapping, Sequence

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD


OIR = Namespace("https://data.oireachtas.ie/ontology#")
POC = Namespace("https://data.oireachtas.ie/poc/semantic-enrichment#")
PROV = Namespace("http://www.w3.org/ns/prov#")
EUROVOC = "http://eurovoc.europa.eu/"
MAX_CONTRIBUTIONS = 1_000
SEMANTIC_MODEL = "BAAI/bge-small-en-v1.5"
SEMANTIC_THRESHOLD = 0.54
MAX_SUGGESTIONS = 5
BASELINE_VERSION = "whole-label-match-v1"
SEMANTIC_VERSION = "fastembed-cosine-max-v1"
DEFAULT_REVIEW_COUNTS = 8

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
SKOSXL_NS = "http://www.w3.org/2008/05/skos-xl#"
EUVOC_NS = "http://publications.europa.eu/ontology/euvoc#"
XML_NS = "http://www.w3.org/XML/1998/namespace"
RDF_Q = "{" + RDF_NS + "}"
SKOS_Q = "{" + SKOS_NS + "}"
SKOSXL_Q = "{" + SKOSXL_NS + "}"
EUVOC_Q = "{" + EUVOC_NS + "}"
XML_Q = "{" + XML_NS + "}"


@dataclass(frozen=True)
class Concept:
    uri: str
    preferred_labels: tuple[str, ...]
    alternative_labels: tuple[str, ...]
    broader: tuple[str, ...]
    narrower: tuple[str, ...]
    status: str = "CURRENT"

    @property
    def labels(self) -> tuple[tuple[str, str], ...]:
        return tuple((label, "preferred") for label in self.preferred_labels) + tuple(
            (label, "alternative") for label in self.alternative_labels
        )


@dataclass(frozen=True)
class Contribution:
    contribution_iri: str
    work_iri: str
    expression_iri: str
    graph_iri: str
    source_id: str
    source_label: str
    source_url: str
    source_sha256: str
    source_pointer: str
    source_eid: str
    date: str
    period: str
    body_kind: str
    house_code: str | None
    house_term: int | None
    split: str
    text: str
    text_sha256: str

    def metadata(self) -> dict:
        """Return the reproducible, transcript-free record form."""
        item = asdict(self)
        item.pop("text")
        return item


@dataclass(frozen=True)
class Suggestion:
    concept_uri: str
    evidence_label: str
    evidence_kind: str
    rank: int
    score: float | None = None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _english(language: str | None) -> bool:
    return bool(language) and language.lower().split("-", 1)[0] == "en"


def parse_taxonomy(path: Path) -> tuple[dict[str, Concept], dict[str, int]]:
    """Stream the RDF/XML release into an English-label/hierarchy projection.

    The released RDF uses SKOS-XL label resources as well as direct SKOS
    literals. Only one top-level RDF subject is retained at a time; the small
    English label table and concept projection are the only accumulated state.
    Deprecated concepts are counted for provenance but excluded from model
    candidates and the Fuseki projection.
    """
    concepts_raw: dict[str, dict] = {}
    english_xl_labels: dict[str, str] = {}
    counts: Counter[str] = Counter()
    depth = 0
    root: ET.Element | None = None

    for event, element in ET.iterparse(path, events=("start", "end")):
        if event == "start":
            depth += 1
            if depth == 1:
                root = element
            continue

        if depth == 2:
            subject = element.get(RDF_Q + "about")
            is_concept = element.tag == SKOS_Q + "Concept"
            is_xl_label = False
            status = "UNSPECIFIED"
            preferred: set[str] = set()
            alternative: set[str] = set()
            preferred_refs: set[str] = set()
            alternative_refs: set[str] = set()
            broader: set[str] = set()
            narrower: set[str] = set()

            for child in element:
                if child.tag == RDF_Q + "type":
                    object_uri = child.get(RDF_Q + "resource")
                    is_concept |= object_uri == SKOS_NS + "Concept"
                    is_xl_label |= object_uri == SKOSXL_NS + "Label"
                elif child.tag == EUVOC_Q + "status":
                    status_uri = child.get(RDF_Q + "resource", "")
                    status = status_uri.rsplit("/", 1)[-1] or "UNSPECIFIED"

                if child.tag in (SKOS_Q + "prefLabel", SKOS_Q + "altLabel"):
                    if _english(child.get(XML_Q + "lang")) and child.text:
                        label = " ".join(child.text.split())
                        (preferred if child.tag == SKOS_Q + "prefLabel" else alternative).add(label)
                elif child.tag in (SKOSXL_Q + "prefLabel", SKOSXL_Q + "altLabel"):
                    label_uri = child.get(RDF_Q + "resource")
                    if label_uri:
                        (preferred_refs if child.tag == SKOSXL_Q + "prefLabel" else alternative_refs).add(label_uri)
                elif child.tag == SKOSXL_Q + "literalForm":
                    if subject and _english(child.get(XML_Q + "lang")) and child.text:
                        english_xl_labels[subject] = " ".join(child.text.split())
                elif child.tag in (SKOS_Q + "broader", SKOS_Q + "narrower"):
                    target = child.get(RDF_Q + "resource")
                    if target:
                        (broader if child.tag == SKOS_Q + "broader" else narrower).add(target)

            if subject and is_xl_label and subject in english_xl_labels:
                counts["english_xl_label_resources"] += 1
            if subject and is_concept:
                counts["concepts_total"] += 1
                counts["concept_status_" + status.lower()] += 1
                concepts_raw[subject] = {
                    "status": status,
                    "preferred": preferred,
                    "alternative": alternative,
                    "preferred_refs": preferred_refs,
                    "alternative_refs": alternative_refs,
                    "broader": broader,
                    "narrower": narrower,
                }
            if root is not None:
                element.clear()
                # All RDF subjects are direct children of rdf:RDF. Clearing the
                # root prevents ElementTree from retaining 481k empty nodes.
                root.clear()
        depth -= 1

    concepts: dict[str, Concept] = {}
    for uri, raw in concepts_raw.items():
        preferred = set(raw["preferred"])
        alternative = set(raw["alternative"])
        preferred.update(english_xl_labels[label] for label in raw["preferred_refs"] if label in english_xl_labels)
        alternative.update(english_xl_labels[label] for label in raw["alternative_refs"] if label in english_xl_labels)
        if raw["status"] != "CURRENT":
            continue
        if not preferred:
            counts["current_concepts_without_english_preferred_label"] += 1
            continue
        if not uri.startswith(EUROVOC):
            raise ValueError(f"unexpected EuroVoc concept IRI: {uri}")
        concepts[uri] = Concept(
            uri=uri,
            preferred_labels=tuple(sorted(preferred, key=str.casefold)),
            alternative_labels=tuple(sorted(alternative, key=str.casefold)),
            broader=tuple(sorted(raw["broader"])),
            narrower=tuple(sorted(raw["narrower"])),
        )

    counts["projected_current_concepts"] = len(concepts)
    counts["projected_preferred_labels"] = sum(len(c.preferred_labels) for c in concepts.values())
    counts["projected_alternative_labels"] = sum(len(c.alternative_labels) for c in concepts.values())
    counts["projected_broader_links"] = sum(
        1 for c in concepts.values() for target in c.broader if target in concepts
    )
    counts["projected_narrower_links"] = sum(
        1 for c in concepts.values() for target in c.narrower if target in concepts
    )
    if not concepts:
        raise ValueError("the official taxonomy yielded no current English concepts")
    return concepts, dict(sorted(counts.items()))


def build_taxonomy_graph(
    concepts: Mapping[str, Concept], *, graph_iri: str, taxonomy: Mapping[str, object], counts: Mapping[str, int]
) -> Graph:
    graph = Graph(identifier=URIRef(graph_iri))
    for uri, concept in sorted(concepts.items()):
        subject = URIRef(uri)
        graph.add((subject, RDF.type, SKOS.Concept))
        for label in concept.preferred_labels:
            graph.add((subject, SKOS.prefLabel, Literal(label, lang="en")))
        for label in concept.alternative_labels:
            graph.add((subject, SKOS.altLabel, Literal(label, lang="en")))
        for parent in concept.broader:
            if parent in concepts:
                graph.add((subject, SKOS.broader, URIRef(parent)))
        for child in concept.narrower:
            if child in concepts:
                graph.add((subject, SKOS.narrower, URIRef(child)))

    release = URIRef(graph_iri + "/release")
    graph.add((release, RDF.type, POC.TaxonomyProjection))
    graph.add((release, POC.taxonomyVersion, Literal(str(taxonomy["version"]))))
    graph.add((release, POC.releaseIdentifier, Literal(str(taxonomy["release_identifier"]))))
    graph.add((release, POC.sourceDataset, URIRef(str(taxonomy["dataset_iri"]))))
    graph.add((release, POC.sourceUrl, URIRef(str(taxonomy["source_url"]))))
    graph.add((release, POC.sourceChecksum, Literal(str(taxonomy["sha256"]))))
    graph.add((release, POC.license, URIRef(str(taxonomy["license"]))))
    graph.add((release, POC.language, Literal("en")))
    graph.add((release, POC.projectionDescription, Literal(str(taxonomy["projection"]))))
    graph.add((release, POC.projectedConceptCount, Literal(int(counts["projected_current_concepts"]), datatype=XSD.integer)))
    return graph


def normalized_words(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return tuple(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def _element_text(element: ET.Element) -> str:
    return " ".join("".join(element.itertext()).split())


def _speech_text(speech: ET.Element) -> str:
    paragraphs = [
        _element_text(element)
        for element in speech.iter()
        if _local_name(element) == "p" and _element_text(element)
    ]
    # AKN paragraph markup can include inline elements; itertext retains its
    # prose while excluding speaker/header metadata outside paragraph nodes.
    return " ".join(paragraphs)


def read_contributions(
    source_xml: bytes,
    source: Mapping[str, object],
    *,
    resolver,
) -> tuple[object, list[dict]]:
    """Transform an exact source and pair each speech with its approved IRI."""
    from oireachtas_etl.transforms.debates import transform_debate

    result = transform_debate(source_xml, resolver=resolver)
    root = ET.fromstring(source_xml)
    speech_elements = [element for element in root.iter() if _local_name(element) == "speech"]
    identity_rows = [
        row for row in result.reference_report.get("resource_identities", [])
        if row.get("expanded_qname", "").endswith("}speech")
    ]
    identities_by_eid = {
        row.get("source_eid"): row for row in identity_rows if row.get("source_eid")
    }
    if len(identities_by_eid) != len(identity_rows):
        raise ValueError(f"speech identities lack a unique source eId in {source['id']}")
    if len(speech_elements) != int(source["expected_speeches"]):
        raise ValueError(
            f"source speech count changed for {source['id']}: "
            f"expected {source['expected_speeches']}, found {len(speech_elements)}"
        )

    records: list[dict] = []
    seen: set[str] = set()
    for speech in speech_elements:
        eid = speech.get("eId")
        identity = identities_by_eid.get(eid or "")
        if identity is None:
            raise ValueError(f"source speech eId {eid!r} has no transformer identity in {source['id']}")
        iri = str(identity["source_node_iri"])
        if iri in seen:
            raise ValueError(f"duplicate transformed speech IRI: {iri}")
        seen.add(iri)
        text = _speech_text(speech)
        records.append({
            "contribution_iri": iri,
            "work_iri": result.work_iri,
            "expression_iri": result.expression_iri,
            "graph_iri": result.graph_iri,
            "source_id": str(source["id"]),
            "source_label": str(source["label"]),
            "source_url": str(source["official_url"]),
            "source_sha256": result.source_sha256,
            "source_pointer": str(identity["source_pointer"]),
            "source_eid": str(eid),
            "date": str(source["label"]).rsplit(", ", 1)[-1],
            "period": str(source["period"]),
            "body_kind": str(source["body_kind"]),
            "house_code": source.get("house_code"),
            "house_term": source.get("house_term"),
            "split": str(source["split"]),
            "text": text,
            "text_sha256": sha256_bytes(text.encode("utf-8")),
        })
    return result, records


def deterministic_sample(
    records: Sequence[dict], *, source: Mapping[str, object], seed: str
) -> list[dict]:
    count = int(source["sample_count"])
    if count < 0 or count > len(records):
        raise ValueError(f"invalid sample count for {source['id']}: {count}/{len(records)}")
    source_hash = str(records[0]["source_sha256"]) if records else str(source["sha256"])
    ranked = sorted(
        records,
        key=lambda record: hashlib.sha256(
            f"{seed}\0{source_hash}\0{record['contribution_iri']}".encode("utf-8")
        ).digest(),
    )
    selected_iris = {record["contribution_iri"] for record in ranked[:count]}
    return [record for record in records if record["contribution_iri"] in selected_iris]


def validate_split(records: Sequence[dict], sources: Sequence[Mapping[str, object]]) -> None:
    work_splits: dict[str, set[str]] = defaultdict(set)
    contribution_iris: set[str] = set()
    per_source: Counter[str] = Counter()
    for record in records:
        work_splits[record["work_iri"]].add(record["split"])
        per_source[record["source_id"]] += 1
        if record["contribution_iri"] in contribution_iris:
            raise ValueError(f"duplicate contribution IRI across sample: {record['contribution_iri']}")
        contribution_iris.add(record["contribution_iri"])
    leaked = [work for work, splits in work_splits.items() if len(splits) > 1]
    if leaked:
        raise ValueError(f"development/evaluation leakage across Works: {leaked[:3]}")
    expected = {str(source["id"]): int(source["sample_count"]) for source in sources}
    if dict(per_source) != expected:
        raise ValueError(f"stratified source sample mismatch: expected={expected}, actual={dict(per_source)}")
    if len(records) > MAX_CONTRIBUTIONS:
        raise ValueError(f"sample exceeds approved maximum of {MAX_CONTRIBUTIONS}")


def label_baseline(
    records: Sequence[dict], concepts: Mapping[str, Concept], *, max_suggestions: int = MAX_SUGGESTIONS
) -> dict[str, list[Suggestion]]:
    """Match preferred/alternative English labels on Unicode whole-word spans.

    One-word labels shorter than seven characters are excluded as too generic
    for this deliberately simple baseline. At most five distinct concepts are
    retained, ranked by preferred-label match, phrase length, then concept IRI.
    """
    by_first: dict[str, list[tuple[tuple[str, ...], str, str, str]]] = defaultdict(list)
    for uri, concept in concepts.items():
        for label, kind in concept.labels:
            words = normalized_words(label)
            if not words or (len(words) == 1 and len(words[0]) < 7):
                continue
            by_first[words[0]].append((words, uri, label, kind))
    for values in by_first.values():
        values.sort(key=lambda item: (-len(item[0]), item[1], item[2].casefold()))

    predictions: dict[str, list[Suggestion]] = {}
    for record in records:
        words = normalized_words(record["text"])
        best: dict[str, tuple[tuple[int, int, int], str, str]] = {}
        for position, first in enumerate(words):
            for phrase, uri, label, kind in by_first.get(first, ()):
                stop = position + len(phrase)
                if stop > len(words) or words[position:stop] != phrase:
                    continue
                rank_key = (1 if kind == "preferred" else 0, len(phrase), len(" ".join(phrase)))
                previous = best.get(uri)
                if previous is None or rank_key > previous[0] or (
                    rank_key == previous[0] and label.casefold() < previous[1].casefold()
                ):
                    best[uri] = (rank_key, label, kind)
        ordered = sorted(
            best.items(),
            key=lambda item: (-item[1][0][0], -item[1][0][1], -item[1][0][2], item[0]),
        )[:max_suggestions]
        predictions[record["contribution_iri"]] = [
            Suggestion(uri, evidence[1], evidence[2], rank, None)
            for rank, (uri, evidence) in enumerate(ordered, start=1)
        ]
    return predictions


def sample_hash(records: Sequence[dict]) -> str:
    identity_rows = [
        (r["contribution_iri"], r["source_sha256"], r["text_sha256"], r["split"])
        for r in sorted(records, key=lambda item: item["contribution_iri"])
    ]
    return sha256_bytes(canonical_json(identity_rows))


def source_manifest_hash(sources: Sequence[Mapping[str, object]]) -> str:
    rows = [
        (str(s["id"]), str(s["sha256"]), int(s["sample_count"]), str(s["split"]))
        for s in sources
    ]
    return sha256_bytes(canonical_json(rows))


def _text_chunks(text: str, words_per_chunk: int = 180) -> list[str]:
    words = text.split()
    return [" ".join(words[start : start + words_per_chunk]) for start in range(0, len(words), words_per_chunk)]


def _normalize_rows(matrix):
    import numpy as np

    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class SemanticMatcher:
    """CPU-only FastEmbed candidate matcher with bounded text/chunk batches."""

    def __init__(self, concepts: Mapping[str, Concept], *, cache_dir: Path, threads: int = 2):
        from fastembed import TextEmbedding

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = TextEmbedding(
            model_name=SEMANTIC_MODEL,
            cache_dir=str(cache_dir),
            threads=threads,
            providers=["CPUExecutionProvider"],
            lazy_load=False,
        )
        self.concept_uris: list[str] = []
        self.label_texts: list[str] = []
        self.label_concept_indices: list[int] = []
        for uri, concept in sorted(concepts.items()):
            concept_index = len(self.concept_uris)
            self.concept_uris.append(uri)
            for label, _kind in concept.labels:
                self.label_texts.append(label)
                self.label_concept_indices.append(concept_index)
        if not self.label_texts:
            raise ValueError("no English EuroVoc candidate labels to embed")
        encoded_labels = list(self.model.embed(self.label_texts, batch_size=64, parallel=1))
        self.label_vectors = _normalize_rows(encoded_labels)
        if self.label_vectors.shape[0] != len(self.label_texts):
            raise ValueError("FastEmbed returned an unexpected number of label vectors")

    def predict(
        self,
        records: Sequence[dict],
        *,
        threshold: float = SEMANTIC_THRESHOLD,
        max_suggestions: int = MAX_SUGGESTIONS,
    ) -> dict[str, list[Suggestion]]:
        import numpy as np

        predictions: dict[str, list[Suggestion]] = {}
        concept_indices = np.asarray(self.label_concept_indices, dtype=np.int32)
        for record in records:
            chunks = _text_chunks(record["text"])
            if not chunks:
                predictions[record["contribution_iri"]] = []
                continue
            query_vectors = _normalize_rows(list(self.model.query_embed(chunks)))
            # Chunk and label limits keep the temporary cosine matrix far below
            # the 4 GB process ceiling even if the sample size is raised.
            label_scores = np.full(len(self.label_texts), -1.0, dtype=np.float32)
            for start in range(0, len(self.label_texts), 4096):
                stop = min(start + 4096, len(self.label_texts))
                similarities = query_vectors @ self.label_vectors[start:stop].T
                label_scores[start:stop] = similarities.max(axis=0)
            concept_scores = np.full(len(self.concept_uris), -1.0, dtype=np.float32)
            best_labels = np.full(len(self.concept_uris), -1, dtype=np.int32)
            for label_index, score in enumerate(label_scores):
                concept_index = int(concept_indices[label_index])
                if score > concept_scores[concept_index]:
                    concept_scores[concept_index] = score
                    best_labels[concept_index] = label_index
            ordered_indices = sorted(
                range(len(self.concept_uris)),
                key=lambda index: (-float(concept_scores[index]), self.concept_uris[index]),
            )
            selected: list[Suggestion] = []
            for index in ordered_indices:
                score = float(concept_scores[index])
                if score < threshold:
                    break
                if len(selected) >= max_suggestions:
                    break
                label_index = int(best_labels[index])
                if label_index < 0:
                    continue
                selected.append(
                    Suggestion(
                        concept_uri=self.concept_uris[index],
                        evidence_label=self.label_texts[label_index],
                        evidence_kind="embedding-nearest-label",
                        rank=len(selected) + 1,
                        score=round(score, 8),
                    )
                )
            predictions[record["contribution_iri"]] = selected
        return predictions


def _suggestion_iri(graph_iri: str, contribution_iri: str, concept_uri: str) -> URIRef:
    key = sha256_bytes(f"{contribution_iri}\0{concept_uri}".encode("utf-8"))
    return URIRef(f"{graph_iri}/suggestion/{key}")


def build_enrichment_graph(
    records: Sequence[dict],
    predictions: Mapping[str, Sequence[Suggestion]],
    *,
    graph_iri: str,
    method: str,
    method_version: str,
    taxonomy: Mapping[str, object],
    input_hash: str,
    model_sha256: str | None,
    settings: Mapping[str, object],
) -> Graph:
    """Write only provisional suggestions and source-linked assessment data."""
    graph = Graph(identifier=URIRef(graph_iri))
    run_iri = URIRef(graph_iri + "/run")
    graph.add((run_iri, RDF.type, POC.ClassificationRun))
    graph.add((run_iri, POC.method, Literal(method)))
    graph.add((run_iri, POC.classifierVersion, Literal(method_version)))
    graph.add((run_iri, POC.taxonomyVersion, Literal(str(taxonomy["version"]))))
    graph.add((run_iri, POC.taxonomyReleaseIdentifier, Literal(str(taxonomy["release_identifier"]))))
    graph.add((run_iri, POC.taxonomyChecksum, Literal(str(taxonomy["sha256"]))))
    graph.add((run_iri, POC.inputSampleChecksum, Literal(input_hash)))
    graph.add((run_iri, POC.runIdentifier, Literal(graph_iri.rsplit("/", 1)[-1])))
    graph.add((run_iri, POC.settings, Literal(canonical_json(dict(settings)).decode("utf-8"), datatype=RDF.JSON)))
    if model_sha256:
        graph.add((run_iri, POC.modelIdentifier, Literal(SEMANTIC_MODEL)))
        graph.add((run_iri, POC.modelChecksum, Literal(model_sha256)))

    for record in records:
        contribution_iri = str(record["contribution_iri"])
        suggestions = list(predictions.get(contribution_iri, ()))
        assessment_key = sha256_bytes(contribution_iri.encode("utf-8"))
        assessment = URIRef(f"{graph_iri}/assessment/{assessment_key}")
        graph.add((assessment, RDF.type, POC.ContributionAssessment))
        graph.add((assessment, POC.contribution, URIRef(contribution_iri)))
        graph.add((assessment, POC.sourceChecksum, Literal(str(record["source_sha256"]))))
        graph.add((assessment, POC.textChecksum, Literal(str(record["text_sha256"]))))
        graph.add((assessment, POC.sourcePointer, Literal(str(record["source_pointer"]))))
        graph.add((assessment, POC.assignmentStatus, Literal("provisional" if suggestions else "abstained")))
        graph.add((assessment, PROV.wasGeneratedBy, run_iri))
        for suggestion in suggestions:
            node = _suggestion_iri(graph_iri, contribution_iri, suggestion.concept_uri)
            graph.add((assessment, POC.hasSuggestion, node))
            graph.add((node, RDF.type, POC.SubjectSuggestion))
            graph.add((node, POC.concept, URIRef(suggestion.concept_uri)))
            graph.add((node, POC.assignmentStatus, Literal("provisional-unreviewed")))
            graph.add((node, POC.evidenceLabel, Literal(suggestion.evidence_label, lang="en")))
            graph.add((node, POC.evidenceKind, Literal(suggestion.evidence_kind)))
            graph.add((node, POC.rank, Literal(suggestion.rank, datatype=XSD.integer)))
            if suggestion.score is not None:
                graph.add((node, POC.similarity, Literal(suggestion.score, datatype=XSD.decimal)))
            graph.add((node, PROV.wasGeneratedBy, run_iri))
    return graph


def sorted_ntriples(graph: Graph) -> bytes:
    lines = sorted(
        f"{subject.n3()} {predicate.n3()} {obj.n3()} ."
        for subject, predicate, obj in graph
    )
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def graph_counts(graphs: Mapping[str, Graph]) -> dict[str, int]:
    return {iri: len(graph) for iri, graph in sorted(graphs.items())}


def model_cache_inventory(path: Path) -> dict[str, object]:
    """Hash the cached model files without including transient lock files."""
    file_rows = []
    total_bytes = 0
    for item in sorted(path.rglob("*")):
        if not item.is_file() or ".locks" in item.parts or item.name.endswith(".lock"):
            continue
        try:
            size = item.stat().st_size
            digest = sha256_file(item)
        except OSError:
            continue
        total_bytes += size
        file_rows.append((item.relative_to(path).as_posix(), size, digest))
    combined = sha256_bytes(canonical_json(file_rows)) if file_rows else ""
    return {"sha256": combined, "bytes": total_bytes, "files": len(file_rows)}


def file_manifest_hash(root: Path, files: Iterable[Path]) -> str:
    entries = []
    for path in sorted(files, key=lambda item: str(item)):
        entries.append((path.relative_to(root).as_posix(), path.stat().st_size, sha256_file(path)))
    return sha256_bytes(canonical_json(entries))
