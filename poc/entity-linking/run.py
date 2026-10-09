#!/usr/bin/env python3
"""Run the frozen, offline-first entity-linking evaluation PoC."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF

ROOT = Path(__file__).resolve().parents[2]
POC_DIR = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))

import entity_linking as el


DEFAULT_WORK_DIR = Path("/tmp/oireachtasontology/entity-linking-evaluation")
FUSEKI_DATASET_PATH = "/entity_linking"
FUSEKI_PASSWORD_DEFAULT = "entity-linking-local"
HOUSES_GRAPH = "https://data.oireachtas.ie/graph/houses"
COMMITTEES_GRAPH = "https://data.oireachtas.ie/graph/committees"
OFFICES_GRAPH = "https://data.oireachtas.ie/graph/offices"
UNITS_GRAPH = "https://data.oireachtas.ie/graph/administrative-units"
METHODS = (el.BASELINE_METHOD, el.CONTEXT_METHOD)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def load_config() -> tuple[dict, list[dict], dict, dict]:
    sources_doc = load_json(POC_DIR / "sources.json")
    questions_doc = load_json(POC_DIR / "questions.json")
    rubric = load_json(POC_DIR / "review-rubric.json")
    if not questions_doc.get("frozen_before_method_comparison") or not rubric.get("frozen_before_method_comparison"):
        raise ValueError("the question set and review rubric must be frozen before method comparison")
    sources = list(sources_doc["sources"])
    if sum(int(item["sample_count"]) for item in sources) != int(sources_doc["sample_size"]):
        raise ValueError("per-source sample counts do not sum to the frozen sample size")
    if int(sources_doc["sample_size"]) > min(int(sources_doc["maximum_contributions"]), el.MAX_CONTRIBUTIONS):
        raise ValueError("frozen sample exceeds the approved 1,000 contribution cap")
    work_splits: dict[str, str] = {}
    for source in sources:
        if source["split"] not in {"development", "evaluation"}:
            raise ValueError(f"unsupported source split: {source['split']}")
        if source["id"] in work_splits:
            raise ValueError(f"duplicate source ID: {source['id']}")
        work_splits[str(source["id"])] = str(source["split"])
    return sources_doc, sources, questions_doc, rubric


def source_path(source: Mapping[str, Any], work_dir: Path) -> Path:
    if source.get("fixture"):
        return ROOT / str(source["fixture"])
    return work_dir / "raw" / "akn" / str(source["cache_filename"])


def _check_file(path: Path, *, digest: str, size: int, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    data = path.read_bytes()
    actual = el.sha256_bytes(data)
    if actual != digest or len(data) != size:
        raise ValueError(
            f"{label} checksum/size mismatch: expected {digest}/{size}, found {actual}/{len(data)}"
        )
    return {"path": str(path), "sha256": actual, "bytes": len(data)}


def acquire_sources(work_dir: Path) -> dict[str, Any]:
    """Fetch only the pinned source allowlist; verify all bytes before use."""
    _, sources, _, _ = load_config()
    target_dir = work_dir / "raw" / "akn"
    target_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in sources:
        path = source_path(source, work_dir)
        if not path.exists() and not source.get("fixture"):
            temporary = path.with_suffix(path.suffix + ".part")
            request = Request(
                str(source["official_url"]),
                headers={"User-Agent": "OireachtasOntology-Entity-Linking-Evaluation/1.0"},
            )
            try:
                with urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                    while block := response.read(1024 * 1024):
                        output.write(block)
                temporary.replace(path)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        if not path.is_file():
            raise FileNotFoundError(f"missing frozen source {source['id']}: {path}")
        verified = _check_file(path, digest=str(source["sha256"]), size=int(source["bytes"]),
                                label=f"AKN source {source['id']}")
        rows.append({"id": source["id"], **verified})

    identity_rows = {}
    for key, source in load_config()[0]["identity_inputs"].items():
        path = ROOT / str(source["path"])
        identity_rows[key] = _check_file(path, digest=str(source["sha256"]), size=int(source["bytes"]),
                                         label=f"identity input {key}")
    return {"source_count": len(rows), "sources": rows, "identity_inputs": identity_rows}


def _source_ordered_graph(dataset: Dataset, graph_iri: str, source_graph: Graph) -> None:
    named = dataset.graph(URIRef(graph_iri))
    for triple in source_graph:
        named.add(triple)


def validated_owners() -> dict[str, Any]:
    """Build only source-validated examples/registry owners; never open Core State."""
    from oireachtas_etl.debates_owners import build_debate_reference_resolver
    from oireachtas_etl.transforms.bills import bill_graph_iri, transform_bill
    from oireachtas_etl.transforms.committees import transform_committees
    from oireachtas_etl.transforms.houses import transform_houses
    from oireachtas_etl.transforms.members import member_graph_iri, transform_member
    from oireachtas_etl.transforms.offices import transform_administrative_units, transform_offices
    from oireachtas_etl.validation.bills import validate_bill
    from oireachtas_etl.validation.committees import validate_committees
    from oireachtas_etl.validation.houses import validate_houses
    from oireachtas_etl.validation.members import validate_member
    from oireachtas_etl.validation.offices import (
        validate_administrative_units,
        validate_offices,
        validate_registry_source,
    )

    _, _, _, _ = load_config()
    identity_inputs = load_config()[0]["identity_inputs"]
    member_wrapper = load_json(ROOT / identity_inputs["member"]["path"])
    member_data = member_wrapper["member"]
    member_graph = transform_member(member_wrapper)
    validate_member(member_wrapper, member_graph)
    member_graph_id = member_graph_iri(member_data)

    bill_doc = load_json(ROOT / identity_inputs["bill"]["path"])
    if len(bill_doc.get("results", [])) != 1:
        raise ValueError("the frozen Bill owner input must contain exactly one Bill record")
    bill_wrapper = bill_doc["results"][0]
    bill_data = bill_wrapper["bill"]
    bill_graph = transform_bill(bill_wrapper)
    validate_bill(bill_wrapper, bill_graph)
    bill_graph_id = bill_graph_iri(bill_data)

    house_source = load_json(ROOT / identity_inputs["houses"]["path"])
    house_graph = transform_houses(house_source)
    validate_houses(house_source, house_graph)

    committee_source = load_json(ROOT / identity_inputs["committee_owner"]["path"])
    committee_graph = transform_committees(committee_source)
    validate_committees(committee_source, committee_graph)

    raw_registry = load_json(ROOT / identity_inputs["registry"]["path"])
    registry = validate_registry_source(raw_registry)
    unit_graph = transform_administrative_units(registry)
    office_graph = transform_offices(registry)
    validate_administrative_units(registry, unit_graph)
    validate_offices(registry, office_graph)

    resolver = build_debate_reference_resolver(
        member_graph=member_graph,
        house_graph=house_graph,
        committee_graph=committee_graph,
    )
    graphs = {
        HOUSES_GRAPH: house_graph,
        COMMITTEES_GRAPH: committee_graph,
        member_graph_id: member_graph,
        bill_graph_id: bill_graph,
        OFFICES_GRAPH: office_graph,
        UNITS_GRAPH: unit_graph,
    }
    return {
        "member_source": member_wrapper,
        "member_graph": member_graph,
        "member_graph_iri": member_graph_id,
        "bill_source": bill_wrapper,
        "bill_graph": bill_graph,
        "bill_graph_iri": bill_graph_id,
        "houses_graph": house_graph,
        "committee_graph": committee_graph,
        "offices_graph": office_graph,
        "units_graph": unit_graph,
        "registry": registry,
        "graphs": graphs,
        "resolver": resolver,
    }


def _speech_targets(graph: Graph, speech: URIRef) -> set[str]:
    targets = {str(value) for value in graph.objects(speech, el.OIR.speaker)}
    for participation in graph.objects(speech, el.OIR.hasSpeechParticipation):
        targets.update(str(value) for value in graph.objects(participation, el.ELIDL.had_participant_person))
    return targets


def _speeches_in_bill_linked_sections(graph: Graph, bill_graph: Graph, bill_iri: str) -> set[str]:
    process = URIRef(bill_iri + "#process")
    bill_events = set(bill_graph.subjects(el.ELIDL.forms_part_of, process))
    bill_events.add(URIRef(bill_iri))
    matched_speeches: set[str] = set()

    def walk(section: URIRef, inherited_match: bool, seen: set[URIRef]) -> None:
        if section in seen:
            return
        seen.add(section)
        own_match = inherited_match or any(target in bill_events for target in graph.objects(section, el.OIR.refersToEvent))
        if own_match:
            matched_speeches.update(str(speech) for speech in graph.objects(section, el.OIR.hasSpeech))
        for child in graph.objects(section, el.OIR.hasSubSection):
            walk(URIRef(child), own_match, seen)

    for top in graph.objects(URIRef(graph.identifier), el.OIR.hasSection):
        walk(URIRef(top), False, set())
    return matched_speeches


def read_contributions(source_xml: bytes, source: Mapping[str, Any], owners: Mapping[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    """Use the approved Debate transformer identity; text stays in process memory."""
    from oireachtas_etl.transforms.debates import transform_debate

    result = transform_debate(source_xml, resolver=owners["resolver"])
    root = ET.fromstring(source_xml)
    speeches = [element for element in root.iter() if _local_name(element) == "speech"]
    identity_rows = [
        row for row in result.reference_report.get("resource_identities", [])
        if str(row.get("expanded_qname", "")).endswith("}speech")
    ]
    identities: dict[str, dict] = {}
    for row in identity_rows:
        eid = row.get("source_eid")
        if not eid or eid in identities:
            raise ValueError(f"speech identity does not have a unique stable eId in {source['id']}")
        identities[str(eid)] = row
    if len(speeches) != int(source["expected_speeches"]) or len(identity_rows) != len(speeches):
        raise ValueError(
            f"speech count/identity mismatch for {source['id']}: source={len(speeches)}, "
            f"expected={source['expected_speeches']}, transformer-identities={len(identity_rows)}"
        )

    date_literals = list(result.graph.objects(URIRef(result.work_iri), el.OIR.debateDate))
    if len(date_literals) != 1:
        raise ValueError(f"transformed Debate Work has no unique source date: {result.work_iri}")
    work_date = str(date_literals[0])[:10]
    house_terms = list(result.graph.objects(URIRef(result.work_iri), el.OIR.recordOfHouseTerm))
    house_code = source.get("house_code")
    house_term = source.get("house_term")
    if house_code and len(house_terms) != 1:
        raise ValueError(f"validated source {source['id']} has no unique existing HouseTerm")
    if not house_code and house_terms:
        raise ValueError(f"committee source {source['id']} unexpectedly resolved a HouseTerm")
    if house_terms:
        owner_graph = owners["graphs"][HOUSES_GRAPH]
        owner_code = list(owner_graph.objects(house_terms[0], el.OIR.houseCode))
        owner_no = list(owner_graph.objects(house_terms[0], el.OIR.termNo))
        if len(owner_code) != 1 or len(owner_no) != 1:
            raise ValueError(f"HouseTerm owner does not have a unique code and term number: {house_terms[0]}")
        if str(owner_code[0]) != str(house_code) or int(owner_no[0]) != int(house_term):
            raise ValueError(f"HouseTerm does not match frozen source context for {source['id']}")

    bill_source = owners["bill_source"]
    structured_bill_speeches = _speeches_in_bill_linked_sections(
        result.graph, owners["bill_graph"], str(bill_source["bill"]["uri"])
    )
    records = []
    seen: set[str] = set()
    for speech in speeches:
        eid = speech.get("eId")
        identity = identities.get(str(eid or ""))
        if identity is None:
            raise ValueError(f"source speech eId has no approved transformed identity: {source['id']}:{eid}")
        contribution_iri = str(identity["source_node_iri"])
        if contribution_iri in seen:
            raise ValueError(f"duplicate contribution IRI in {source['id']}: {contribution_iri}")
        seen.add(contribution_iri)
        text = el.speech_text(speech)
        if not text:
            raise ValueError(f"sample source has an empty Speech text at {identity['source_pointer']}")
        speech_iri = URIRef(contribution_iri)
        records.append({
            "contribution_iri": contribution_iri,
            "work_iri": result.work_iri,
            "expression_iri": result.expression_iri,
            "graph_iri": result.graph_iri,
            "source_id": str(source["id"]),
            "source_label": str(source["label"]),
            "source_url": str(source["official_url"]),
            "source_sha256": result.source_sha256,
            "source_pointer": str(identity["source_pointer"]),
            "source_eid": str(eid),
            "date": work_date,
            "period": str(source["period"]),
            "body_kind": str(source["body_kind"]),
            "house_code": str(house_code) if house_code else None,
            "house_term": int(house_term) if house_term is not None else None,
            "split": str(source["split"]),
            "text": text,
            "text_sha256": el.sha256_bytes(text.encode("utf-8")),
            "speaker_targets": sorted(_speech_targets(result.graph, speech_iri)),
            "structured_bill_targets": [str(bill_source["bill"]["uri"])]
            if contribution_iri in structured_bill_speeches else [],
        })
    return result, records


def deterministic_sample(records: Sequence[dict[str, Any]], source: Mapping[str, Any], seed: str) -> list[dict[str, Any]]:
    count = int(source["sample_count"])
    if count < 0 or count > len(records):
        raise ValueError(f"invalid sample size for {source['id']}: {count}/{len(records)}")
    source_hash = str(records[0]["source_sha256"]) if records else str(source["sha256"])
    ranking = sorted(records, key=lambda row: hashlib.sha256(
        f"{seed}\0{source_hash}\0{row['contribution_iri']}".encode("utf-8")
    ).digest())
    selected = {row["contribution_iri"] for row in ranking[:count]}
    return [row for row in records if row["contribution_iri"] in selected]


def sample_hash(records: Sequence[Mapping[str, Any]]) -> str:
    rows = [
        (row["contribution_iri"], row["source_sha256"], row["text_sha256"], row["split"])
        for row in sorted(records, key=lambda item: str(item["contribution_iri"]))
    ]
    return el.sha256_bytes(el.canonical_json(rows))


def source_manifest_hash(sources: Sequence[Mapping[str, Any]]) -> str:
    rows = [(str(row["id"]), str(row["sha256"]), int(row["sample_count"]), str(row["split"])) for row in sources]
    return el.sha256_bytes(el.canonical_json(rows))


def load_corpus(work_dir: Path) -> dict[str, Any]:
    from oireachtas_etl.validation.debates_integration import validate_debates_integration

    source_doc, sources, _, _ = load_config()
    provenance = acquire_sources(work_dir)
    owners = validated_owners()
    sample: list[dict[str, Any]] = []
    source_rows: dict[str, dict[str, Any]] = {}
    debate_graphs: dict[str, Graph] = {}
    for source in sources:
        path = source_path(source, work_dir)
        xml_bytes = path.read_bytes()
        result, all_records = read_contributions(xml_bytes, source, owners)
        if result.source_sha256 != source["sha256"]:
            raise ValueError(f"Debate transformer checksum differs for {source['id']}")
        validation_dataset = Dataset()
        for graph_iri, owner_graph in owners["graphs"].items():
            _source_ordered_graph(validation_dataset, graph_iri, owner_graph)
        _source_ordered_graph(validation_dataset, result.graph_iri, result.graph)
        validate_debates_integration(result, validation_dataset, source_xml=xml_bytes)

        selected = deterministic_sample(all_records, source, str(source_doc["sample_seed"]))
        sample.extend(selected)
        debate_graphs[result.graph_iri] = result.graph
        source_rows[str(source["id"])] = {
            "source_id": str(source["id"]),
            "source_url": str(source["official_url"]),
            "source_sha256": result.source_sha256,
            "work_iri": result.work_iri,
            "expression_iri": result.expression_iri,
            "graph_iri": result.graph_iri,
            "input_bytes": len(xml_bytes),
            "speeches_in_source": len(all_records),
            "sampled_contributions": len(selected),
            "split": str(source["split"]),
            "owner_status": "resolved-existing-house-term" if source.get("house_code") else "committee-owner-unresolved-or-not-required",
            "reference_report_sha256": el.sha256_bytes(result.reference_report_json),
        }

    contribution_iris: set[str] = set()
    work_splits: dict[str, set[str]] = defaultdict(set)
    per_source = Counter()
    for row in sample:
        if row["contribution_iri"] in contribution_iris:
            raise ValueError(f"duplicate contribution IRI across sample: {row['contribution_iri']}")
        contribution_iris.add(row["contribution_iri"])
        work_splits[row["work_iri"]].add(row["split"])
        per_source[row["source_id"]] += 1
    if any(len(splits) != 1 for splits in work_splits.values()):
        raise ValueError("development/evaluation split leaks across Works")
    expected = {str(item["id"]): int(item["sample_count"]) for item in sources}
    if dict(per_source) != expected or len(sample) != int(source_doc["sample_size"]):
        raise ValueError(f"stratified sample mismatch: expected {expected}, got {dict(per_source)}")
    if len(sample) > el.MAX_CONTRIBUTIONS:
        raise ValueError("sample exceeds 1,000 contributions")

    all_graphs = dict(owners["graphs"])
    all_graphs.update(debate_graphs)
    candidates, identity_inventory = el.build_candidates(
        member_source=owners["member_source"], member_graph=owners["member_graph"],
        bill_source=owners["bill_source"], bill_graph=owners["bill_graph"],
        registry=owners["registry"], office_graph=owners["offices_graph"], unit_graph=owners["units_graph"],
        member_graph_iri=owners["member_graph_iri"], bill_graph_iri=owners["bill_graph_iri"],
        offices_graph_iri=OFFICES_GRAPH, units_graph_iri=UNITS_GRAPH,
    )
    return {
        "records": sample,
        "source_rows": source_rows,
        "graphs": all_graphs,
        "owners": owners,
        "candidates": candidates,
        "identity_inventory": identity_inventory,
        "provenance": provenance,
        "sample_hash": sample_hash(sample),
        "source_manifest_hash": source_manifest_hash(sources),
        "split_counts": dict(Counter(row["split"] for row in sample)),
    }


def record_metadata(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"text", "speaker_targets", "structured_bill_targets"}}


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(el.canonical_json(dict(row)).decode("utf-8") + "\n")


def _write_graph(path: Path, graph: Graph) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(el.sorted_ntriples(graph))


def blind_review_packet(records: Sequence[Mapping[str, Any]], candidates: Sequence[el.Identity]) -> dict[str, Any]:
    """Select records before method execution; packet contains no predictions or candidate IRIs."""
    evaluation = [row for row in records if row["split"] == "evaluation"]
    sources = sorted({str(row["source_id"]) for row in evaluation})
    selected: dict[str, dict[str, Any]] = {}
    for source_id in sources:
        subset = [row for row in evaluation if row["source_id"] == source_id]
        chosen = sorted(subset, key=lambda row: hashlib.sha256(
            f"entity-linking-blind-review-v1\0{row['contribution_iri']}".encode("utf-8")
        ).digest())[:4]
        for row in chosen:
            selected[str(row["contribution_iri"])] = dict(row)

    # Name-stratified opportunities are selected from the frozen source-backed
    # identity inventory, independently of resolver outcomes. The random stratum
    # above ensures the packet is not composed only of detector-positive cases.
    candidates_by_category: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in evaluation:
        detected_categories = {
            mention.category for mention in el.detect_mentions(row, candidates)
            if not mention.generic and mention.candidates
        }
        for category in detected_categories:
            candidates_by_category[category].append(row)
    category_selection = {}
    for category in ("Member", "Bill", "NamedOffice", "AdministrativeUnit"):
        chosen = sorted(candidates_by_category.get(category, []), key=lambda row: hashlib.sha256(
            f"entity-linking-blind-review-v1\0{category}\0{row['contribution_iri']}".encode("utf-8")
        ).digest())[:4]
        category_selection[category] = len(chosen)
        for row in chosen:
            selected[str(row["contribution_iri"])] = dict(row)
    ordered = sorted(selected.values(), key=lambda row: (row["source_id"], row["contribution_iri"]))[:64]
    return {
        "reviewer_instructions": (
            "Without seeing resolver output or target IRIs, annotate every explicit named entity mention in each contribution. "
            "Distinguish a speech's own speaker/participation metadata from words in its transcript. Mark generic references, "
            "office-versus-holder ambiguity, out-of-registry names, and uncertain cases explicitly. Review all four categories."
        ),
        "selection": "Four deterministic random evaluation contributions per evaluation Work plus up to four name-stratified opportunities per category; selection is before comparison and limited to 64.",
        "random_source_count": len(sources),
        "name_stratified_selected_by_category": category_selection,
        "records": [
            {
                "source_id": row["source_id"],
                "contribution_iri": row["contribution_iri"],
                "work_iri": row["work_iri"],
                "source_pointer": row["source_pointer"],
                "source_sha256": row["source_sha256"],
                "text_sha256": row["text_sha256"],
                "date": row["date"],
                "house_code": row["house_code"],
                "text": row["text"],
            }
            for row in ordered
        ],
    }


def prepare_command(work_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    corpus = load_corpus(work_dir)
    artifact_dir = work_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(artifact_dir / "sample-manifest.jsonl", [record_metadata(row) for row in corpus["records"]])
    (artifact_dir / "identity-snapshot.json").write_bytes(
        el.canonical_json(corpus["identity_inventory"]) + b"\n"
    )
    (artifact_dir / "blind-review-packet.json").write_bytes(
        el.canonical_json(blind_review_packet(corpus["records"], corpus["candidates"])) + b"\n"
    )
    graph_counts = {}
    for graph_iri, graph in sorted(corpus["graphs"].items()):
        file_key = el.sha256_bytes(graph_iri.encode("utf-8"))[:16]
        _write_graph(artifact_dir / f"input-graph-{file_key}.nt", graph)
        graph_counts[graph_iri] = len(graph)
    summary = {
        "stage": "prepared",
        "sample_size": len(corpus["records"]),
        "split_counts": corpus["split_counts"],
        "source_count": len(corpus["source_rows"]),
        "source_rows": corpus["source_rows"],
        "sample_sha256": corpus["sample_hash"],
        "source_manifest_sha256": corpus["source_manifest_hash"],
        "identity_coverage": corpus["identity_inventory"]["candidate_identities_by_category"],
        "owner_graph_counts": graph_counts,
        "blind_review_records": len(blind_review_packet(corpus["records"], corpus["candidates"])["records"]),
        "source_text_in_rdf": False,
        "transcript_review_packet_path": str(artifact_dir / "blind-review-packet.json"),
        "prepare_seconds": round(time.perf_counter() - started, 6),
    }
    (artifact_dir / "prepare-summary.json").write_bytes(el.canonical_json(summary) + b"\n")
    return summary


def local_fuseki_endpoints(base_url: str) -> tuple[str, str]:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port != 13037 or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path.rstrip("/") != FUSEKI_DATASET_PATH
    ):
        raise ValueError(
            "Fuseki must be this PoC's disposable loopback endpoint "
            "http://127.0.0.1:13037/entity_linking; production and remote endpoints are forbidden"
        )
    origin = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    return origin + "/data", origin + "/query"


def _result_value(binding: Mapping[str, Any], key: str) -> str | None:
    value = binding.get(key)
    return str(value["value"]) if isinstance(value, dict) and "value" in value else None


def _query_prefixes() -> str:
    return """PREFIX oir: <https://data.oireachtas.ie/ontology#>
PREFIX members: <https://data.oireachtas.ie/ontology/members#>
PREFIX poc: <https://data.oireachtas.ie/poc/entity-linking#>
PREFIX eli: <http://data.europa.eu/eli/ontology#>
PREFIX eli-dl: <http://data.europa.eu/eli/eli-draft-legislation-ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


def _sample_speech_values(rows: Sequence[Mapping[str, Any]]) -> str:
    return " ".join(f"<{row['contribution_iri']}>" for row in rows)


def _debate_speech_pattern(graph_iri: str) -> str:
    return f"""GRAPH <{graph_iri}> {{
    ?work oir:hasSection ?topSection .
    ?topSection (oir:hasSubSection)* ?section .
    ?section oir:hasSpeech ?speech .
  }}"""


def _relationship_pattern(question: Mapping[str, Any], owners: Mapping[str, Any]) -> tuple[str, str]:
    target = str(question["target_iri"])
    category = str(question["category"])
    if category == "Member":
        return owners["member_graph_iri"], f"""GRAPH <{owners['member_graph_iri']}> {{
    <{target}> members:hasMembersMembership ?relationship .
    ?relationship members:inHouseTerm ?related .
  }}
  GRAPH <{HOUSES_GRAPH}> {{ ?related oir:houseCode ?relatedLabel ; oir:termNo ?relatedNumber }}"""
    if category == "Bill":
        process = target + "#process"
        return owners["bill_graph_iri"], f"""GRAPH <{owners['bill_graph_iri']}> {{
    ?process eli-dl:process_status ?related ; eli-dl:latest_activity ?latestActivity .
    FILTER(?process = <{process}>)
    ?latestActivity eli-dl:activity_date ?latestActivityDate
  }}"""
    if category == "NamedOffice":
        return OFFICES_GRAPH, f"""GRAPH <{OFFICES_GRAPH}> {{
    <{target}> members:hasRoleType ?related .
    OPTIONAL {{ <{target}> members:headsAdministrativeUnit ?unit }}
  }}
  OPTIONAL {{ GRAPH <{UNITS_GRAPH}> {{ ?unit rdfs:label|skos:prefLabel ?relatedLabel }} }}"""
    if category == "AdministrativeUnit":
        return OFFICES_GRAPH, f"""GRAPH <{OFFICES_GRAPH}> {{
    ?related members:headsAdministrativeUnit <{target}> ; members:hasRoleType ?officeType .
  }}"""
    raise ValueError(f"unsupported entity category: {category}")


def build_retrieval_query(
    question: Mapping[str, Any],
    source_row: Mapping[str, Any],
    sample_rows: Sequence[Mapping[str, Any]],
    *,
    method: str,
    mention_graph_iri: str | None,
    link_graph_iri: str | None,
    owners: Mapping[str, Any],
) -> str:
    target = str(question["target_iri"])
    category = str(question["category"])
    graph_iri = str(source_row["graph_iri"])
    relevant_sample = [row for row in sample_rows if row["source_id"] == source_row["source_id"]]
    values = _sample_speech_values(relevant_sample)
    base = _debate_speech_pattern(graph_iri)
    if method == "structured-only":
        if category == "Member":
            structured = f"""GRAPH <{graph_iri}> {{
    {{ ?speech oir:speaker <{target}> }} UNION {{
      ?speech oir:hasSpeechParticipation ?participation .
      ?participation eli-dl:had_participant_person <{target}>
    }}
  }}"""
        elif category == "Bill":
            process = target + "#process"
            structured = f"""GRAPH <{graph_iri}> {{
    ?work oir:hasSection ?root .
    ?root (oir:hasSubSection)* ?linkedSection .
    ?linkedSection oir:refersToEvent ?event .
    ?linkedSection (oir:hasSubSection)* ?speechSection .
    ?speechSection oir:hasSpeech ?speech .
  }}
  GRAPH <{owners['bill_graph_iri']}> {{ ?event eli-dl:forms_part_of <{process}> }}"""
        else:
            # No structured Debate-to-office/unit mention property exists. This
            # query checks for direct source-owner links only; it does not
            # fabricate a predicate or infer an answer from the entity label.
            structured = f"""GRAPH <{graph_iri}> {{ ?speech ?existingPredicate <{target}> }}"""
        return _query_prefixes() + f"""SELECT DISTINCT ?speech ?related ?relatedLabel WHERE {{
  {base}
  VALUES ?speech {{ {values} }}
  {structured}
  OPTIONAL {{ BIND(<{target}> AS ?related) }}
}} ORDER BY ?speech"""

    if method not in METHODS or not mention_graph_iri or not link_graph_iri:
        raise ValueError("derived retrieval requires the method's mention and link graph IRIs")
    owner_graph, related = _relationship_pattern(question, owners)
    surface_literal = Literal(str(question["full_text_query"])).n3()
    return _query_prefixes() + f"""SELECT DISTINCT ?speech ?related ?relatedLabel ?latestActivity ?latestActivityDate WHERE {{
  {base}
  VALUES ?speech {{ {values} }}
  GRAPH <{mention_graph_iri}> {{
    ?mention a poc:EntityMention ; poc:contribution ?speech ; poc:entityCategory "{category}" ;
      poc:surfaceForm ?surface .
    FILTER(LCASE(STR(?surface)) = LCASE({surface_literal}))
  }}
  GRAPH <{link_graph_iri}> {{
    ?mention poc:hasResolution ?decision .
    ?decision poc:status "resolved" ; poc:resolvedEntity <{target}> .
  }}
  {related}
  }} ORDER BY ?speech"""


def mention_outcomes_for_question(
    question: Mapping[str, Any],
    rows_by_method: Mapping[str, Sequence[Mapping[str, Any]]],
    evaluation_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize exact reviewed-question surface detections, including abstentions."""
    category = str(question["category"])
    phrase_tokens = el.normalized_words(str(question["full_text_query"]))
    evaluation_ids = {str(row["contribution_iri"]) for row in evaluation_records}
    output: dict[str, Any] = {}
    for method in METHODS:
        selected = [
            row for row in rows_by_method[method]
            if str(row["contribution_iri"]) in evaluation_ids
            and row["category"] == category
            and el.normalized_words(str(row["surface"])) == phrase_tokens
        ]
        statuses = Counter(str(row["status"]) for row in selected)
        output[method] = {
            "mention_occurrences": len(selected),
            "status_counts": dict(sorted(statuses.items())),
            "contributions_by_status": {
                status: sorted({str(row["contribution_iri"]) for row in selected if row["status"] == status})
                for status in sorted(statuses)
            },
        }
    return output


def execute_fuseki(
    *,
    base_url: str,
    password: str,
    graphs: Mapping[str, Graph],
    corpus: Mapping[str, Any],
    graph_catalog: Mapping[tuple[str, str], tuple[str, str]],
    rows_by_method: Mapping[str, Sequence[Mapping[str, Any]]],
    work_dir: Path,
) -> dict[str, Any]:
    from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient

    gsp_url, query_url = local_fuseki_endpoints(base_url)
    client = FusekiSparqlClient(query_url, user="admin", password=password, timeout=120)
    loader = FusekiGraphStoreLoader(gsp_url, user="admin", password=password, timeout=120)
    existing = client.query("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")
    if existing:
        raise ValueError("entity-linking Fuseki must be empty; recreate its disposable tmpfs dataset before loading")

    triple_counts: dict[str, int] = {}
    graph_hashes: dict[str, str] = {}
    upload_seconds = 0.0
    for graph_iri, graph in sorted(graphs.items()):
        payload = el.sorted_ntriples(graph)
        start = time.perf_counter()
        loader.replace(graph_iri, payload.decode("utf-8"), content_type="application/n-triples")
        upload_seconds += time.perf_counter() - start
        count_rows = client.query(f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}")
        actual_count = int(_result_value(count_rows[0], "n")) if count_rows else -1
        if actual_count != len(graph):
            raise ValueError(f"whole-graph count mismatch for {graph_iri}: {actual_count} != {len(graph)}")
        remote = client.construct_graph(graph_iri)
        expected_hash = el.sha256_bytes(el.canonical_graph_bytes(graph))
        actual_hash = el.sha256_bytes(el.canonical_graph_bytes(remote))
        if actual_hash != expected_hash:
            raise ValueError(f"whole-graph content hash mismatch after import: {graph_iri}")
        triple_counts[graph_iri] = actual_count
        graph_hashes[graph_iri] = expected_hash

    expected_graphs = set(graphs)
    loaded_graphs = {str(_result_value(row, "g")) for row in client.query("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")}
    if loaded_graphs != expected_graphs:
        raise ValueError(f"graph isolation mismatch: extra={sorted(loaded_graphs-expected_graphs)}, missing={sorted(expected_graphs-loaded_graphs)}")

    question_doc = load_config()[2]
    source_rows = corpus["source_rows"]
    question_results: list[dict[str, Any]] = []
    query_seconds = 0.0
    evaluation_records = [row for row in corpus["records"] if row["split"] == "evaluation"]
    evaluation_ids = {row["contribution_iri"] for row in evaluation_records}
    for question in question_doc["questions"]:
        source_ids = sorted({row["source_id"] for row in evaluation_records})
        result_sets: dict[str, set[str]] = defaultdict(set)
        joined_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
        sparql_by_source: dict[str, dict[str, str]] = defaultdict(dict)
        per_query_seconds: dict[str, dict[str, float]] = defaultdict(dict)
        for source_id in source_ids:
            source = source_rows[source_id]
            for method in ("structured-only", *METHODS):
                mention_graph = link_graph = None
                if method in METHODS:
                    mention_graph, link_graph = graph_catalog[(method, "evaluation")]
                query = build_retrieval_query(
                    question, source, evaluation_records, method=method,
                    mention_graph_iri=mention_graph, link_graph_iri=link_graph,
                    owners=corpus["owners"],
                )
                started = time.perf_counter()
                bindings = client.query(query)
                elapsed = time.perf_counter() - started
                query_seconds += elapsed
                per_query_seconds[method][source_id] = round(elapsed, 6)
                sparql_by_source[method][source_id] = query
                for binding in bindings:
                    speech = _result_value(binding, "speech")
                    if not speech or speech not in evaluation_ids:
                        continue
                    result_sets[method].add(speech)
                    joined_rows[method].append({
                        key: value for key in ("speech", "related", "relatedLabel", "latestActivity", "latestActivityDate")
                        if (value := _result_value(binding, key)) is not None
                    })

        phrase = str(question["full_text_query"])
        lexical_results = {
            str(row["contribution_iri"]) for row in evaluation_records
            if el.phrase_spans(str(row["text"]), phrase)
        }
        question_results.append({
            "question_id": str(question["id"]),
            "category": str(question["category"]),
            "target_iri": str(question["target_iri"]),
            "offline_exact_phrase_search": {
                "phrase": phrase,
                "result_count": len(lexical_results),
                "contributions": sorted(lexical_results),
                "engine": "offline-normalized-whole-phrase scan over the same evaluation sample; not an Elasticsearch deployment benchmark",
            },
            "mention_outcomes": mention_outcomes_for_question(
                question, rows_by_method, evaluation_records
            ),
            "methods": {
                method: {
                    "result_count": len(result_sets[method]),
                    "contributions": sorted(result_sets[method]),
                    "joined_rows": sorted(joined_rows[method], key=lambda row: (row["speech"], row.get("related", ""))),
                    "query_seconds_by_source": per_query_seconds[method],
                    "sparql_by_source": sparql_by_source[method],
                }
                for method in ("structured-only", *METHODS)
            },
            "graph_incremental_over_structured": {
                method: sorted(result_sets[method] - result_sets["structured-only"])
                for method in METHODS
            },
            "graph_incremental_over_offline_phrase_search": {
                method: sorted(result_sets[method] - lexical_results)
                for method in METHODS
            },
            "lexical_matches_not_linked": {
                method: sorted(lexical_results - result_sets[method])
                for method in METHODS
            },
        })

    if any(not query for item in question_results for method in item["methods"].values()
           for query in method["sparql_by_source"].values()):
        raise ValueError("a frozen question did not generate executable SPARQL")
    return {
        "endpoint": base_url,
        "dataset_is_disposable_and_loopback_only": True,
        "graph_count": len(triple_counts),
        "triples_by_graph": triple_counts,
        "sha256_by_graph": graph_hashes,
        "total_triples": sum(triple_counts.values()),
        "upload_seconds": round(upload_seconds, 6),
        "query_seconds_total": round(query_seconds, 6),
        "questions": question_results,
    }


def _rss_mib() -> float:
    # Linux reports ru_maxrss in KiB; the accepted execution host is Linux.
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)


def _prediction_signature(rows: Sequence[Mapping[str, Any]]) -> list[tuple[Any, ...]]:
    return [(
        row["mention_iri"], row["category"], row["start_offset"], row["end_offset"], row["status"],
        row["target_iri"], tuple(row["candidate_iris"]), row["reason"],
    ) for row in rows]


def validate_reference(reference: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> None:
    """Fail closed on stale, text-bearing, or non-evaluation review evidence."""
    def has_transcript_field(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(
                str(key).casefold() == "text" or "transcript" in str(key).casefold()
                or has_transcript_field(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(has_transcript_field(item) for item in value)
        return False

    if has_transcript_field(reference):
        raise ValueError("provisional reference must not contain transcript text fields")
    if not reference.get("blind_to_method_outputs"):
        raise ValueError("provisional reference was not reviewed blind to method outputs")
    contributions = reference.get("contributions")
    if not isinstance(contributions, list) or len(contributions) != int(reference.get("reviewed_contributions", -1)):
        raise ValueError("provisional reference contribution count is invalid")
    if len({str(row.get("contribution_iri")) for row in contributions}) != len(contributions):
        raise ValueError("provisional reference contains duplicate contributions")
    source_records = {str(row["contribution_iri"]): row for row in records}
    valid_categories = {"Member", "Bill", "NamedOffice", "AdministrativeUnit"}
    valid_labels = {
        "explicit-identity-mention", "generic-unresolved-reference", "ambiguous-office-or-holder",
        "out-of-registry-named-entity", "uncertain", "no-in-scope-mention",
    }
    target_iris = {
        str(mention["target_iri"])
        for contribution in contributions
        for mention in contribution.get("mentions", [])
        if mention.get("target_iri")
    }
    for target in target_iris:
        # This is checked against the frozen validated identity snapshot by the caller.
        if not target.startswith("https://data.oireachtas.ie/"):
            raise ValueError(f"provisional reference contains a non-Oireachtas target IRI: {target}")
    for reviewed in contributions:
        iri = str(reviewed.get("contribution_iri", ""))
        record = source_records.get(iri)
        if record is None or record.get("split") != "evaluation":
            raise ValueError(f"provisional reference contribution is not in the evaluation sample: {iri}")
        for key in ("source_id", "work_iri", "source_pointer", "source_sha256", "text_sha256", "date"):
            if str(reviewed.get(key)) != str(record.get(key)):
                raise ValueError(f"provisional reference {key} does not match frozen contribution {iri}")
        for mention in reviewed.get("mentions", []):
            category, label = str(mention.get("category", "")), str(mention.get("label", ""))
            if category not in valid_categories or label not in valid_labels:
                raise ValueError(f"provisional reference has an unsupported category/label: {category}/{label}")
            start, end = int(mention.get("start_offset", -1)), int(mention.get("end_offset", -1))
            text = str(record["text"])
            if start < 0 or end <= start or text[start:end] != str(mention.get("surface", "")):
                raise ValueError(f"provisional reference span does not match frozen text: {iri}:{start}-{end}")


def _graph_leak_check(records: Sequence[Mapping[str, Any]], graphs: Mapping[str, Graph]) -> None:
    text_set = {str(row["text"]) for row in records if str(row["text"])}
    for graph_iri, graph in graphs.items():
        for _subject, _predicate, obj in graph:
            if isinstance(obj, Literal) and str(obj) in text_set:
                raise ValueError(f"full contribution transcript leaked into RDF graph {graph_iri}")


def run_evaluation(
    *,
    work_dir: Path,
    fuseki_base_url: str,
    fuseki_password: str,
    skip_fuseki: bool,
    reference_path: Path | None,
) -> dict[str, Any]:
    wall_started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    stage_times: dict[str, float] = {}
    start = time.perf_counter()
    corpus = load_corpus(work_dir)
    stage_times["source_acquisition_owner_validation_and_debate_transform_seconds"] = round(time.perf_counter() - start, 6)
    candidates = corpus["candidates"]
    records = corpus["records"]
    methods_rows: dict[str, list[dict[str, Any]]] = {}
    derived_graphs: dict[str, Graph] = {}
    graph_catalog: dict[tuple[str, str], tuple[str, str]] = {}
    graph_bytes_hashes: dict[str, str] = {}
    run_material = {
        "sample_sha256": corpus["sample_hash"],
        "source_manifest_sha256": corpus["source_manifest_hash"],
        "identity_inventory": corpus["identity_inventory"],
        "questions_sha256": el.sha256_bytes((POC_DIR / "questions.json").read_bytes()),
        "rubric_sha256": el.sha256_bytes((POC_DIR / "review-rubric.json").read_bytes()),
        "detector": "exact-token-span-shared-v1",
        "methods": list(METHODS),
    }
    run_id = el.sha256_bytes(el.canonical_json(run_material))[:20]
    for method in METHODS:
        start = time.perf_counter()
        rows = el.decision_rows(records, candidates, method)
        methods_rows[method] = rows
        stage_times[f"{method}_seconds"] = round(time.perf_counter() - start, 6)
        for split in ("development", "evaluation"):
            split_records = [row for row in records if row["split"] == split]
            split_rows = [row for row in rows if row["source_id"] in {item["source_id"] for item in split_records}]
            mention_iri = f"https://data.oireachtas.ie/graph/poc/entity-linking/mentions/{method}/{split}/{run_id}"
            link_iri = f"https://data.oireachtas.ie/graph/poc/entity-linking/links/{method}/{split}/{run_id}"
            mention_graph, link_graph = el.build_derived_graphs(
                split_records, split_rows, mention_graph_iri=mention_iri, link_graph_iri=link_iri,
                method=method, run_id=run_id, split=split,
                input_hash=sample_hash(split_records),
            )
            derived_graphs[mention_iri] = mention_graph
            derived_graphs[link_iri] = link_graph
            graph_catalog[(method, split)] = (mention_iri, link_iri)
            graph_bytes_hashes[mention_iri] = el.sha256_bytes(el.sorted_ntriples(mention_graph))
            graph_bytes_hashes[link_iri] = el.sha256_bytes(el.sorted_ntriples(link_graph))

    # Deterministic rerun check on every split using identical in-memory source,
    # identity, configuration and resolver inputs.
    repeatability: dict[str, Any] = {}
    for method in METHODS:
        repeated = el.decision_rows(records, candidates, method)
        stable_decisions = _prediction_signature(repeated) == _prediction_signature(methods_rows[method])
        stable_graphs = True
        for split in ("development", "evaluation"):
            mention_iri, link_iri = graph_catalog[(method, split)]
            split_records = [row for row in records if row["split"] == split]
            split_rows = [row for row in repeated if row["source_id"] in {item["source_id"] for item in split_records}]
            repeated_mentions, repeated_links = el.build_derived_graphs(
                split_records, split_rows, mention_graph_iri=mention_iri, link_graph_iri=link_iri,
                method=method, run_id=run_id, split=split, input_hash=sample_hash(split_records),
            )
            stable_graphs &= (
                el.sha256_bytes(el.sorted_ntriples(repeated_mentions)) == graph_bytes_hashes[mention_iri]
                and el.sha256_bytes(el.sorted_ntriples(repeated_links)) == graph_bytes_hashes[link_iri]
            )
        repeatability[method] = {"decisions_stable": stable_decisions, "rdf_graphs_stable": stable_graphs}
        if not stable_decisions or not stable_graphs:
            raise ValueError(f"same-input determinism check failed for {method}")

    all_graphs = dict(corpus["graphs"])
    all_graphs.update(derived_graphs)
    _graph_leak_check(records, all_graphs)
    peak_rss = _rss_mib()
    if peak_rss > 4096:
        raise MemoryError(f"linking process exceeded 4 GiB peak RSS: {peak_rss} MiB")

    for graph_iri, graph in sorted(all_graphs.items()):
        key = el.sha256_bytes(graph_iri.encode("utf-8"))[:16]
        _write_graph(work_dir / "artifacts" / "graphs" / f"{key}.nt", graph)
    artifact_dir = work_dir / "artifacts"
    write_jsonl(artifact_dir / "sample-manifest.jsonl", [record_metadata(row) for row in records])
    (artifact_dir / "identity-snapshot.json").write_bytes(el.canonical_json(corpus["identity_inventory"]) + b"\n")
    for method, rows in methods_rows.items():
        write_jsonl(artifact_dir / f"decisions-{method}.jsonl", rows)
    for graph_iri, graph in sorted(derived_graphs.items()):
        key = el.sha256_bytes(graph_iri.encode("utf-8"))[:16]
        _write_graph(artifact_dir / "graphs" / f"{key}.nt", graph)

    reference_metrics = None
    reference_evidence = None
    if reference_path is not None and reference_path.is_file():
        reference_doc = load_json(reference_path)
        validate_reference(reference_doc, records)
        packet_path = work_dir / "artifacts" / "blind-review-packet.json"
        expected_packet_hash = reference_doc.get("review_packet_sha256")
        if expected_packet_hash:
            if not packet_path.is_file() or el.sha256_bytes(packet_path.read_bytes()) != expected_packet_hash:
                raise ValueError("blind review packet does not match the provisional reference fingerprint")
        valid_targets = {candidate.iri for candidate in candidates}
        for contribution in reference_doc["contributions"]:
            for mention in contribution.get("mentions", []):
                target = mention.get("target_iri")
                if target and str(target) not in valid_targets:
                    raise ValueError(f"provisional reference target is not in the validated identity snapshot: {target}")
        reference_metrics = el.score_reference(
            reference_doc, methods_rows,
            methods=METHODS,
        )
        reference_evidence = {
            "file": reference_path.name,
            "sha256": el.sha256_bytes(reference_path.read_bytes()),
            "review_packet_sha256": expected_packet_hash,
            "reviewer_type": reference_doc.get("reviewer_type"),
            "independent_human_review": bool(reference_doc.get("independent_human_review", False)),
            "reviewed_contributions": len(reference_doc["contributions"]),
        }

    fuseki_results = None
    if not skip_fuseki:
        start = time.perf_counter()
        fuseki_results = execute_fuseki(
            base_url=fuseki_base_url,
            password=fuseki_password,
            graphs=all_graphs,
            corpus=corpus,
            graph_catalog=graph_catalog,
            rows_by_method=methods_rows,
            work_dir=work_dir,
        )
        stage_times["fuseki_import_and_sparql_seconds"] = round(time.perf_counter() - start, 6)
        (artifact_dir / "retrieval-results.json").write_bytes(el.canonical_json(fuseki_results) + b"\n")

    disk_bytes = sum(path.stat().st_size for path in artifact_dir.rglob("*") if path.is_file())
    total_triples_by_graph = {iri: len(graph) for iri, graph in sorted(all_graphs.items())}
    summary = {
        "created_at_utc": started_at,
        "status": "complete" if fuseki_results is not None else "fuseki-skipped-incomplete",
        "run_id": run_id,
        "source_count": len(corpus["source_rows"]),
        "source_speeches_total": sum(int(row["speeches_in_source"]) for row in corpus["source_rows"].values()),
        "sample_size": len(records),
        "split_counts": corpus["split_counts"],
        "sample_sha256": corpus["sample_hash"],
        "source_manifest_sha256": corpus["source_manifest_hash"],
        "source_rows": corpus["source_rows"],
        "source_acquisition": corpus["provenance"],
        "identity_inventory": corpus["identity_inventory"],
        "identity_input_fingerprint": el.sha256_bytes(el.canonical_json(corpus["provenance"]["identity_inputs"])),
        "methods": {
            method: {
                "algorithm": method,
                "version": method,
                "metrics": el.method_metrics(methods_rows[method]),
                "decision_count": len(methods_rows[method]),
                "resolved_links": sum(bool(row["target_iri"]) for row in methods_rows[method]),
                "abstentions": sum(row["status"] == "abstained" for row in methods_rows[method]),
                "ambiguous": sum(row["status"] == "ambiguous" for row in methods_rows[method]),
                "out_of_registry": sum(row["status"] == "out-of-registry" for row in methods_rows[method]),
            }
            for method in METHODS
        },
        "provisional_agent_reference_metrics": reference_metrics,
        "provisional_reference_evidence": reference_evidence,
        "repeatability": repeatability,
        "derived_graph_count": len(derived_graphs),
        "named_graph_count": len(all_graphs),
        "triples_by_graph": total_triples_by_graph,
        "total_triples": sum(total_triples_by_graph.values()),
        "derived_graph_sha256": graph_bytes_hashes,
        "graph_isolation": {
            "provisional_graphs_have_poc_namespace": all("/graph/poc/entity-linking/" in iri for iri in derived_graphs),
            "input_owner_and_debate_graphs_are_separate": set(derived_graphs).isdisjoint(corpus["graphs"]),
            "source_transcript_literals_in_rdf": False,
        },
        "resource_measurements": {
            "linking_peak_rss_mib": peak_rss,
            "runtime_wall_seconds": round(time.perf_counter() - wall_started, 6),
            "stage_seconds": stage_times,
            "artifact_bytes": disk_bytes,
            "cpu_only": True,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "fuseki": fuseki_results,
        "full_text_comparison": "Offline normalized whole-phrase scans were run on the same evaluation text. No Elasticsearch service/index was available or contacted; these are not production Elasticsearch latency/ranking measurements.",
        "warnings": [
            "All system links are provisional and belong only in disposable PoC graphs.",
            "The validated Member and Bill candidate snapshots each contain one example identity; neither is a complete registry/census.",
            "Agent-reviewed labels are provisional, not a human-reviewed gold standard.",
            "The evaluation sample is a small, source-stratified PoC and does not measure production-corpus coverage.",
        ],
    }
    (artifact_dir / "run-summary.json").write_bytes(el.canonical_json(summary) + b"\n")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    download = subparsers.add_parser("download-sources", help="acquire only the frozen Work/owner allowlist")
    download.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    prepare = subparsers.add_parser("prepare", help="verify/transform sample and write an external blind-review packet")
    prepare.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run = subparsers.add_parser("run", help="compare exact and context-aware linking in isolated Fuseki")
    run.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run.add_argument("--fuseki-base-url", default="http://127.0.0.1:13037/entity_linking")
    run.add_argument("--fuseki-password", default=os.environ.get("FUSEKI_ADMIN_PASSWORD", FUSEKI_PASSWORD_DEFAULT))
    run.add_argument("--skip-fuseki", action="store_true", help="diagnostic only; not end-to-end acceptance")
    run.add_argument("--review-reference", type=Path, default=POC_DIR / "results" / "provisional-reference.json")
    args = parser.parse_args(argv)
    try:
        if args.command == "download-sources":
            result = acquire_sources(args.work_dir)
        elif args.command == "prepare":
            result = prepare_command(args.work_dir)
        else:
            result = run_evaluation(
                work_dir=args.work_dir,
                fuseki_base_url=args.fuseki_base_url,
                fuseki_password=args.fuseki_password,
                skip_fuseki=args.skip_fuseki,
                reference_path=args.review_reference,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        print(f"entity-linking PoC failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
