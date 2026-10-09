#!/usr/bin/env python3
"""Reproduce the isolated EuroVoc semantic-enrichment evaluation."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
from typing import Mapping, Sequence
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF

ROOT = Path(__file__).resolve().parents[2]
POC_DIR = Path(__file__).resolve().parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))

import semantic_enrichment as se


DEFAULT_WORK_DIR = Path("/tmp/oireachtasontology/eurovoc-evaluation")
DEFAULT_TAXONOMY = DEFAULT_WORK_DIR / "taxonomy" / "eurovoc-skos-ap-act.rdf"
FUSEKI_DATASET_SUFFIX = "/semantic_enrichment"
FUSEKI_PASSWORD_DEFAULT = "semantic-enrichment-local"
HOUSES_GRAPH = "https://data.oireachtas.ie/graph/houses"
COMMITTEES_GRAPH = "https://data.oireachtas.ie/graph/committees"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> tuple[dict, list[dict], dict]:
    sources_doc = _load_json(POC_DIR / "sources.json")
    questions_doc = _load_json(POC_DIR / "questions.json")
    if not questions_doc.get("frozen_before_method_comparison"):
        raise ValueError("retrieval questions are not frozen")
    sources = sources_doc["sources"]
    if sum(int(item["sample_count"]) for item in sources) != int(sources_doc["sample_size"]):
        raise ValueError("per-source sample counts do not sum to the frozen sample size")
    return sources_doc, sources, questions_doc


def source_path(source: Mapping[str, object], work_dir: Path) -> Path:
    fixture = source.get("fixture")
    if fixture:
        return ROOT / str(fixture)
    return work_dir / "raw" / "akn" / str(source["cache_filename"])


def download_sources(work_dir: Path) -> dict[str, object]:
    """Fetch only the seven frozen source objects; never enumerate the API."""
    _, sources, _ = load_config()
    target_dir = work_dir / "raw" / "akn"
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for source in sources:
        if source.get("fixture"):
            path = source_path(source, work_dir)
        else:
            path = target_dir / str(source["cache_filename"])
            if not path.exists():
                request = Request(
                    str(source["official_url"]),
                    headers={"User-Agent": "OireachtasOntology-EuroVoc-Evaluation/1.0"},
                )
                temporary = path.with_suffix(path.suffix + ".part")
                try:
                    with urlopen(request, timeout=90) as response, temporary.open("wb") as output:
                        while block := response.read(1024 * 1024):
                            output.write(block)
                    temporary.replace(path)
                except Exception:
                    temporary.unlink(missing_ok=True)
                    raise
        if not path.is_file():
            raise FileNotFoundError(
                f"missing selected AKN source {source['id']}: {path}; "
                "run `python poc/semantic-enrichment/run.py download-sources`"
            )
        digest = se.sha256_file(path)
        if digest != source["sha256"] or path.stat().st_size != int(source["bytes"]):
            raise ValueError(
                f"source checksum/size mismatch for {source['id']}: "
                f"sha256={digest}, bytes={path.stat().st_size}"
            )
        results.append({"id": source["id"], "path": str(path), "sha256": digest, "bytes": path.stat().st_size})
    return {"source_count": len(results), "sources": results}


def validated_owners() -> tuple[Graph, Graph, object]:
    """Transform and validate existing House/Committee owners; mint none."""
    from oireachtas_etl.debates_owners import build_debate_reference_resolver
    from oireachtas_etl.transforms.committees import transform_committees
    from oireachtas_etl.transforms.houses import transform_houses
    from oireachtas_etl.validation.committees import validate_committees
    from oireachtas_etl.validation.houses import validate_houses

    houses_source = _load_json(ROOT / "data/api_examples/houses.json")
    house_graph = transform_houses(houses_source)
    validate_houses(houses_source, house_graph)

    # This checked owner example is Dáil 33 Finance. It intentionally does not
    # resolve the Dáil 34 committee identities in the selected AKN documents.
    committees_source = _load_json(ROOT / "tests/fixtures/committee-owner.json")
    committee_graph = transform_committees(committees_source)
    validate_committees(committees_source, committee_graph)

    resolver = build_debate_reference_resolver(
        house_graph=house_graph,
        committee_graph=committee_graph,
    )
    return house_graph, committee_graph, resolver


def load_sample(work_dir: Path) -> tuple[list[dict], dict[str, Graph], dict[str, dict]]:
    from oireachtas_etl.validation.debates_integration import validate_debates_integration

    sources_doc, sources, _ = load_config()
    house_graph, committee_graph, resolver = validated_owners()
    debate_graphs: dict[str, Graph] = {}
    source_rows: dict[str, dict] = {}
    sampled: list[dict] = []
    owners_dataset = Dataset()
    for graph_iri, graph in ((HOUSES_GRAPH, house_graph), (COMMITTEES_GRAPH, committee_graph)):
        named = owners_dataset.graph(URIRef(graph_iri))
        for triple in graph:
            named.add(triple)

    for source in sources:
        path = source_path(source, work_dir)
        if not path.is_file():
            raise FileNotFoundError(f"selected source {source['id']} is missing at {path}")
        source_bytes = path.read_bytes()
        if len(source_bytes) != int(source["bytes"]) or se.sha256_bytes(source_bytes) != source["sha256"]:
            raise ValueError(f"source bytes do not match frozen provenance: {source['id']}")
        result, records = se.read_contributions(source_bytes, source, resolver=resolver)
        if result.source_sha256 != source["sha256"]:
            raise ValueError(f"transformer source checksum differs for {source['id']}")
        validate_dataset = Dataset()
        for owner_iri, owner_graph in ((HOUSES_GRAPH, house_graph), (COMMITTEES_GRAPH, committee_graph)):
            target = validate_dataset.graph(URIRef(owner_iri))
            for triple in owner_graph:
                target.add(triple)
        named_debate = validate_dataset.graph(URIRef(result.graph_iri))
        for triple in result.graph:
            named_debate.add(triple)
        validate_debates_integration(result, validate_dataset, source_xml=source_bytes)

        linked_terms = list(result.graph.objects(URIRef(result.work_iri), se.OIR.recordOfHouseTerm))
        if source.get("house_code") and len(linked_terms) != 1:
            raise ValueError(f"validated {source['id']} has no unique existing HouseTerm link")
        if not source.get("house_code") and linked_terms:
            raise ValueError(f"unsupported committee HouseTerm was emitted for {source['id']}")

        selected = se.deterministic_sample(records, source=source, seed=str(sources_doc["sample_seed"]))
        sampled.extend(selected)
        debate_graphs[result.graph_iri] = result.graph
        source_rows[str(source["id"])] = {
            "source_id": str(source["id"]),
            "work_iri": result.work_iri,
            "expression_iri": result.expression_iri,
            "graph_iri": result.graph_iri,
            "source_sha256": result.source_sha256,
            "input_bytes": len(source_bytes),
            "speeches_in_source": len(records),
            "sampled_contributions": len(selected),
            "split": str(source["split"]),
            "owner_status": "resolved-existing-house-term" if linked_terms else "unresolved-no-matching-owner",
            "reference_report_sha256": se.sha256_bytes(result.reference_report_json),
        }
    se.validate_split(sampled, sources)
    return sampled, {HOUSES_GRAPH: house_graph, COMMITTEES_GRAPH: committee_graph, **debate_graphs}, source_rows


def review_packet(records: Sequence[dict], questions: Mapping[str, object]) -> dict:
    """Select a source-stratified blind review packet without classifier output."""
    evaluation_by_source: dict[str, list[dict]] = {}
    for record in records:
        if record["split"] == "evaluation":
            evaluation_by_source.setdefault(record["source_id"], []).append(record)
    selected: list[dict] = []
    for source_id, rows in sorted(evaluation_by_source.items()):
        chosen = sorted(
            rows,
            key=lambda row: hashlib.sha256(
                f"blind-agent-review-v1\0{row['contribution_iri']}".encode("utf-8")
            ).digest(),
        )[:se.DEFAULT_REVIEW_COUNTS]
        selected.extend(chosen)
    question_items = questions["questions"]
    packet_rows = []
    for row in sorted(selected, key=lambda item: (item["source_id"], item["contribution_iri"])):
        applicable = [
            {
                "id": question["id"],
                "question": question["question"],
                "criteria": question["review_criteria"],
            }
            for question in question_items
            if row["source_id"] in question["source_ids"] and question["mode"] == "subject"
        ]
        packet_rows.append({
            "source_id": row["source_id"],
            "contribution_iri": row["contribution_iri"],
            "source_pointer": row["source_pointer"],
            "date": row["date"],
            "applicable_questions": applicable,
            "text": row["text"],
        })
    return {
        "reviewer_instructions": (
            "Blind provisional relevance review. Judge each contribution against only the frozen question and criteria. "
            "Do not infer a EuroVoc assignment or method output. Use relevant, irrelevant, or uncertain; give one short reason."
        ),
        "selection": "Eight deterministic hash-selected evaluation contributions per evaluation source; chosen before classifier execution.",
        "records": packet_rows,
    }


def prepare_command(work_dir: Path) -> dict:
    _, sources, questions_doc = load_config()
    provenance = download_sources(work_dir)
    records, graphs, source_rows = load_sample(work_dir)
    output_dir = work_dir / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_rows = [record_metadata(r) for r in records]
    write_jsonl(output_dir / "sample-manifest.jsonl", metadata_rows)
    (output_dir / "blind-review-packet.json").write_bytes(se.canonical_json(review_packet(records, questions_doc)) + b"\n")
    for graph_iri, graph in sorted(graphs.items()):
        if graph_iri == HOUSES_GRAPH or graph_iri == COMMITTEES_GRAPH or graph_iri.startswith("https://data.oireachtas.ie/graph/debate/"):
            filename = "structure-" + se.sha256_bytes(graph_iri.encode("utf-8"))[:16] + ".nt"
            (output_dir / filename).write_bytes(se.sorted_ntriples(graph))
    return {
        "stage": "prepare",
        "sample_size": len(records),
        "split_counts": dict(Counter(record["split"] for record in records)),
        "source_provenance": provenance,
        "sources": source_rows,
        "sample_sha256": se.sample_hash(records),
        "blind_review_records": len(review_packet(records, questions_doc)["records"]),
        "transcript_text_written_to_rdf": False,
    }


def record_metadata(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "text"}


def write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(se.canonical_json(dict(row)).decode("utf-8") + "\n")


def prediction_rows(records: Sequence[dict], predictions: Mapping[str, Sequence[se.Suggestion]]) -> list[dict]:
    rows = []
    for record in records:
        suggestions = predictions.get(record["contribution_iri"], ())
        rows.append({
            "contribution_iri": record["contribution_iri"],
            "source_id": record["source_id"],
            "source_sha256": record["source_sha256"],
            "text_sha256": record["text_sha256"],
            "split": record["split"],
            "status": "provisional" if suggestions else "abstained",
            "suggestions": [
                {
                    "concept_uri": item.concept_uri,
                    "evidence_label": item.evidence_label,
                    "evidence_kind": item.evidence_kind,
                    "rank": item.rank,
                    "score": item.score,
                }
                for item in suggestions
            ],
        })
    return rows


def prediction_signature(predictions: Mapping[str, Sequence[se.Suggestion]]) -> dict[str, tuple]:
    return {
        iri: tuple(
            (item.concept_uri, item.evidence_label, item.evidence_kind, item.rank,
             None if item.score is None else round(item.score, 8))
            for item in predictions.get(iri, ())
        )
        for iri in sorted(predictions)
    }


def method_metrics(records: Sequence[dict], predictions: Mapping[str, Sequence[se.Suggestion]]) -> dict:
    result = {}
    for split in ("development", "evaluation"):
        rows = [row for row in records if row["split"] == split]
        assigned = [row for row in rows if predictions.get(row["contribution_iri"])]
        suggestion_count = sum(len(predictions.get(row["contribution_iri"], ())) for row in rows)
        result[split] = {
            "contributions": len(rows),
            "with_suggestions": len(assigned),
            "abstentions": len(rows) - len(assigned),
            "coverage": round(len(assigned) / len(rows), 6) if rows else 0,
            "assignment_density": round(suggestion_count / len(rows), 6) if rows else 0,
            "total_suggestions": suggestion_count,
            "per_source": {
                source_id: {
                    "contributions": sum(row["source_id"] == source_id for row in rows),
                    "with_suggestions": sum(
                        row["source_id"] == source_id and bool(predictions.get(row["contribution_iri"]))
                        for row in rows
                    ),
                }
                for source_id in sorted({row["source_id"] for row in rows})
            },
        }
    return result


def make_graph_iri(method: str, split: str, run_id: str) -> str:
    return f"https://data.oireachtas.ie/graph/poc/semantic-enrichment/{method}/{split}/{run_id}"


def build_query(question: Mapping[str, object], *, method_graph: str | None, taxonomy_graph: str,
                source_rows: Mapping[str, Mapping[str, object]]) -> str:
    prefixes = """PREFIX oir: <https://data.oireachtas.ie/ontology#>
PREFIX poc: <https://data.oireachtas.ie/poc/semantic-enrichment#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
    works = [str(source_rows[source_id]["work_iri"]) for source_id in question["source_ids"]]
    values = " ".join(f"<{work}>" for work in works)
    if question["mode"] == "structured-only":
        select = "SELECT DISTINCT ?speech ?work ?date"
        enrichment = ""
        ordering = "ORDER BY ?work ?speech"
    else:
        if not method_graph:
            raise ValueError("subject retrieval requires a method enrichment graph")
        select = "SELECT DISTINCT ?speech ?work ?date ?assigned ?score ?evidence"
        enrichment = f"""
  GRAPH <{method_graph}> {{
    ?assessment poc:contribution ?speech ; poc:hasSuggestion ?suggestion .
    ?suggestion poc:concept ?assigned ; poc:evidenceLabel ?evidence .
    OPTIONAL {{ ?suggestion poc:similarity ?score }}
  }}
"""
        concept = str(question["concept_uri"])
        if question.get("include_narrower"):
            enrichment += f"  GRAPH <{taxonomy_graph}> {{ ?assigned skos:broader* <{concept}> }}\n"
        else:
            enrichment += f"  FILTER(?assigned = <{concept}>)\n"
        ordering = "ORDER BY ?work ?speech ?assigned"

    blocks = []
    for source_id in question["source_ids"]:
        source = source_rows[source_id]
        graph_iri = str(source["graph_iri"])
        blocks.append(f"""GRAPH <{graph_iri}> {{
    VALUES ?work {{ <{source['work_iri']}> }}
    ?work a oir:DebateRecord ; oir:debateDate ?date ; oir:hasSection ?topSection .
    ?topSection (oir:hasSubSection)* ?section .
    ?section oir:hasSpeech ?speech .
  }}""")
    if len(blocks) > 1:
        # SPARQL UNION takes two GroupGraphPatternSub operands. Wrapping each
        # graph block is required; bare GRAPH clauses separated by UNION are
        # rejected by Fuseki's parser.
        structural = "{\n  " + "\n} UNION {\n  ".join(blocks) + "\n}"
    else:
        structural = blocks[0]
    house = question.get("house")
    if house:
        owner_joins = "\n  ".join(
            f"GRAPH <{source_rows[source_id]['graph_iri']}> {{ ?work oir:recordOfHouseTerm ?houseTerm }}"
            for source_id in question["source_ids"]
        )
        house_filter = f"""
  {owner_joins}
  GRAPH <{HOUSES_GRAPH}> {{
    ?houseTerm oir:houseCode \"{house['code']}\" ; oir:termNo {int(house['term'])} .
  }}
"""
    else:
        house_filter = ""
    date = question.get("date")
    date_filter = f'  FILTER(STRSTARTS(STR(?date), "{date}"))\n' if date else ""
    return (
        prefixes + select + " WHERE {\n  " + structural + "\n"
        + enrichment + house_filter + date_filter + "}\n" + ordering
    )


def local_fuseki_endpoints(base_url: str) -> tuple[str, str]:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.port != 13036
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.path.rstrip("/") != FUSEKI_DATASET_SUFFIX
    ):
        raise ValueError(
            "Fuseki must be the dedicated disposable loopback dataset at "
            "http://127.0.0.1:13036/semantic_enrichment; remote endpoints are forbidden"
        )
    origin = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
    return origin + "/data", origin + "/query"


def _result_value(binding: Mapping[str, object], key: str):
    item = binding.get(key)
    return item.get("value") if isinstance(item, dict) else None


def execute_fuseki(
    base_url: str,
    password: str,
    graphs: Mapping[str, Graph],
    query_specs: Sequence[tuple[str, str, str | None]],
    *,
    taxonomy_graph_iri: str,
    source_rows: Mapping[str, Mapping[str, object]],
    output_dir: Path,
) -> dict:
    from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient

    gsp_url, query_url = local_fuseki_endpoints(base_url)
    client = FusekiSparqlClient(query_url, user="admin", password=password, timeout=120)
    loader = FusekiGraphStoreLoader(gsp_url, user="admin", password=password, timeout=120)
    preexisting = client.query("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")
    if preexisting:
        raise ValueError(
            "the disposable Fuseki dataset is not empty; stop it and recreate it with "
            "the PoC compose file before loading (no existing graph will be overwritten)"
        )

    counts = {}
    upload_seconds = 0.0
    for graph_iri, graph in sorted(graphs.items()):
        payload = se.sorted_ntriples(graph).decode("utf-8")
        started = time.perf_counter()
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        upload_seconds += time.perf_counter() - started
        count_rows = client.query(
            f"SELECT (COUNT(*) AS ?n) WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}"
        )
        actual = int(_result_value(count_rows[0], "n")) if count_rows else -1
        if actual != len(graph):
            raise ValueError(f"Fuseki whole-graph verification failed for {graph_iri}: {actual} != {len(graph)}")
        counts[graph_iri] = actual

    all_graph_rows = client.query("SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }")
    if len(all_graph_rows) != len(graphs):
        raise ValueError(f"unexpected Fuseki graph count: {len(all_graph_rows)} != {len(graphs)}")

    query_results = []
    for question_id, mode, method_graph in query_specs:
        question = next(item for item in load_config()[2]["questions"] if item["id"] == question_id)
        sparql = build_query(question, method_graph=method_graph, taxonomy_graph=taxonomy_graph_iri,
                             source_rows=source_rows)
        started = time.perf_counter()
        bindings = client.query(sparql)
        elapsed = time.perf_counter() - started
        rows = []
        for binding in bindings:
            rows.append({key: _result_value(binding, key) for key in
                         ("speech", "work", "date", "assigned", "score", "evidence")
                         if _result_value(binding, key) is not None})
        query_results.append({
            "question_id": question_id,
            "method": mode,
            "method_graph": method_graph,
            "query_seconds": round(elapsed, 6),
            "result_count": len(rows),
            "rows": rows,
            "sparql": sparql,
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "fuseki-queries.json").write_bytes(se.canonical_json(query_results) + b"\n")
    return {
        "graph_count": len(counts),
        "triples_by_graph": counts,
        "total_triples": sum(counts.values()),
        "upload_seconds": round(upload_seconds, 6),
        "queries": query_results,
    }


def _transcript_leak_check(records: Sequence[dict], graphs: Mapping[str, Graph]) -> None:
    source_texts = {
        record["text"] for record in records
        if len(record["text"]) >= 40
    }
    if not source_texts:
        return
    for graph_iri, graph in graphs.items():
        for _subject, _predicate, obj in graph:
            if isinstance(obj, Literal) and str(obj) in source_texts:
                raise ValueError(f"speech transcript literal leaked into RDF graph {graph_iri}")


def _question_predictions(
    question: Mapping[str, object],
    records_by_iri: Mapping[str, dict],
    predictions: Mapping[str, Sequence[se.Suggestion]],
    concepts: Mapping[str, se.Concept],
) -> dict[str, bool]:
    parent = str(question["concept_uri"])
    broader = {uri: set(concept.broader) for uri, concept in concepts.items()}

    def matches(uri: str) -> bool:
        if uri == parent:
            return True
        if not question.get("include_narrower"):
            return False
        pending = list(broader.get(uri, ()))
        seen = set()
        while pending:
            candidate = pending.pop()
            if candidate == parent:
                return True
            if candidate not in seen:
                seen.add(candidate)
                pending.extend(broader.get(candidate, ()))
        return False

    allowed_sources = set(question["source_ids"])
    return {
        iri: any(matches(item.concept_uri) for item in predictions.get(iri, ()))
        for iri, record in records_by_iri.items()
        if record["split"] == "evaluation" and record["source_id"] in allowed_sources
    }


def provisional_reference_metrics(
    reference_path: Path | None,
    questions_doc: Mapping[str, object],
    records: Sequence[dict],
    baseline: Mapping[str, Sequence[se.Suggestion]],
    semantic: Mapping[str, Sequence[se.Suggestion]],
    concepts: Mapping[str, se.Concept],
) -> dict | None:
    if reference_path is None or not reference_path.is_file():
        return None
    reference = _load_json(reference_path)
    judgments = reference.get("judgments", [])
    by_source_eid = {
        (str(record["source_id"]), str(record["source_eid"])): str(record["contribution_iri"])
        for record in records
    }
    by_question: dict[str, list[dict]] = {}
    for row in judgments:
        normalized = dict(row)
        if not normalized.get("contribution_iri"):
            key = (str(normalized.get("source_id", "")), str(normalized.get("source_eid", "")))
            if key not in by_source_eid:
                raise ValueError(f"blind-review record is not in the frozen sample: {key}")
            normalized["contribution_iri"] = by_source_eid[key]
        by_question.setdefault(str(normalized["question_id"]), []).append(normalized)
    records_by_iri = {row["contribution_iri"]: row for row in records}
    output = {}
    for question in questions_doc["questions"]:
        if question["mode"] != "subject":
            continue
        question_id = str(question["id"])
        review_rows = by_question.get(question_id, [])
        if not review_rows:
            continue
        output[question_id] = {}
        for method, predictions in (("label-baseline", baseline), ("semantic", semantic)):
            predicted = _question_predictions(question, records_by_iri, predictions, concepts)
            counts = Counter()
            for row in review_rows:
                judgment = str(row["judgment"])
                if judgment == "uncertain":
                    counts["uncertain"] += 1
                    continue
                if judgment not in {"relevant", "irrelevant"}:
                    raise ValueError(f"invalid provisional reference judgment {judgment!r}")
                is_predicted = predicted.get(str(row["contribution_iri"]), False)
                if judgment == "relevant" and is_predicted:
                    counts["true_positive"] += 1
                elif judgment == "irrelevant" and is_predicted:
                    counts["false_positive"] += 1
                elif judgment == "relevant":
                    counts["false_negative"] += 1
                else:
                    counts["true_negative"] += 1
            tp, fp, fn = counts["true_positive"], counts["false_positive"], counts["false_negative"]
            output[question_id][method] = {
                "reviewed": len(review_rows),
                "uncertain": counts["uncertain"],
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "true_negative": counts["true_negative"],
                "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                "recall": round(tp / (tp + fn), 4) if tp + fn else None,
            }
    return {
        "reviewer_type": reference.get("reviewer_type", "unspecified"),
        "blind_to_methods": bool(reference.get("blind_to_methods")),
        "sample_selection": reference.get("sample_selection"),
        "rubric": reference.get("rubric"),
        "judgments": output,
    }


def _write_graph(path: Path, graph: Graph) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(se.sorted_ntriples(graph))


def _safe_rss_megabytes() -> float:
    # Linux reports ru_maxrss in KiB. The PoC and its measured host are Linux.
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)


def run_evaluation(
    *,
    work_dir: Path,
    taxonomy_path: Path,
    fuseki_base_url: str,
    fuseki_password: str,
    skip_fuseki: bool,
    review_reference: Path | None,
    model_threads: int,
) -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    wall_started = time.perf_counter()
    stage_times: dict[str, float] = {}

    stage = time.perf_counter()
    sources_doc, sources, questions_doc = load_config()
    source_provenance = download_sources(work_dir)
    records, input_graphs, source_rows = load_sample(work_dir)
    stage_times["source_transform_and_validation_seconds"] = round(time.perf_counter() - stage, 6)
    _transcript_leak_check(records, input_graphs)

    taxonomy = sources_doc["taxonomy"]
    if not taxonomy_path.is_file():
        raise FileNotFoundError(
            f"missing pinned EuroVoc RDF/XML at {taxonomy_path}; download the 4.24 SKOS-AP-ACT RDF/XML "
            "from the Publications Office EuroVoc page and place it at this path"
        )
    taxonomy_digest = se.sha256_file(taxonomy_path)
    if taxonomy_digest != taxonomy["sha256"] or taxonomy_path.stat().st_size != int(taxonomy["bytes"]):
        raise ValueError(
            "EuroVoc source mismatch: expected the frozen 4.24 RDF/XML checksum "
            f"{taxonomy['sha256']} ({taxonomy['bytes']} bytes), found {taxonomy_digest} ({taxonomy_path.stat().st_size} bytes)"
        )
    stage = time.perf_counter()
    concepts, taxonomy_counts = se.parse_taxonomy(taxonomy_path)
    taxonomy_graph_iri = f"https://data.oireachtas.ie/graph/poc/eurovoc/{taxonomy['version']}/{taxonomy_digest[:16]}"
    taxonomy_graph = se.build_taxonomy_graph(
        concepts, graph_iri=taxonomy_graph_iri, taxonomy=taxonomy, counts=taxonomy_counts
    )
    stage_times["taxonomy_stream_parse_and_projection_seconds"] = round(time.perf_counter() - stage, 6)

    input_hash = se.sample_hash(records)
    manifest_hash = se.source_manifest_hash(sources)
    baseline_settings = {
        "version": se.BASELINE_VERSION,
        "one_token_min_characters": 7,
        "maximum_suggestions": se.MAX_SUGGESTIONS,
        "preferred_label_precedes_alternative": True,
        "confidence": "not-calibrated; exact whole-label match and rank are evidence only",
    }
    semantic_settings = {
        "version": se.SEMANTIC_VERSION,
        "model": se.SEMANTIC_MODEL,
        "similarity": "cosine; max across 180-word contribution chunks and English preferred/alternative label vectors",
        "threshold": se.SEMANTIC_THRESHOLD,
        "maximum_suggestions": se.MAX_SUGGESTIONS,
        "cpu_only": True,
        "confidence": "raw similarity, not a calibrated probability",
    }

    stage = time.perf_counter()
    baseline_predictions = se.label_baseline(records, concepts)
    stage_times["baseline_classification_seconds"] = round(time.perf_counter() - stage, 6)

    model_cache = work_dir / "models" / "fastembed"
    stage = time.perf_counter()
    matcher = se.SemanticMatcher(concepts, cache_dir=model_cache, threads=model_threads)
    model_cache_inventory = se.model_cache_inventory(model_cache)
    stage_times["model_load_and_candidate_embedding_seconds"] = round(time.perf_counter() - stage, 6)
    stage = time.perf_counter()
    semantic_predictions = matcher.predict(records)
    stage_times["semantic_classification_seconds"] = round(time.perf_counter() - stage, 6)

    if not model_cache_inventory["sha256"]:
        raise ValueError("FastEmbed model cache has no hashable model files")
    repeat_records = []
    evaluation_by_source: dict[str, list[dict]] = {}
    for record in records:
        if record["split"] == "evaluation":
            evaluation_by_source.setdefault(record["source_id"], []).append(record)
    for source_id, source_records in sorted(evaluation_by_source.items()):
        repeat_records.extend(sorted(
            source_records,
            key=lambda row: hashlib.sha256(
                f"semantic-enrichment-repeat-v1\0{row['contribution_iri']}".encode("utf-8")
            ).digest(),
        )[:4])
    if not repeat_records:
        raise ValueError("repeatability sample is empty")
    stage = time.perf_counter()
    repeated_baseline = se.label_baseline(repeat_records, concepts)
    repeated_semantic = matcher.predict(repeat_records)
    stage_times["repeatability_seconds"] = round(time.perf_counter() - stage, 6)
    baseline_initial_sample = {
        row["contribution_iri"]: baseline_predictions[row["contribution_iri"]]
        for row in repeat_records
    }
    semantic_initial_sample = {
        row["contribution_iri"]: semantic_predictions[row["contribution_iri"]]
        for row in repeat_records
    }
    repeatability = {
        "representative_contributions": len(repeat_records),
        "source_ids": sorted({row["source_id"] for row in repeat_records}),
        "baseline_stable": prediction_signature(repeated_baseline)
        == prediction_signature(baseline_initial_sample),
        "semantic_stable": prediction_signature(repeated_semantic)
        == prediction_signature(semantic_initial_sample),
    }
    if not repeatability["baseline_stable"] or not repeatability["semantic_stable"]:
        raise ValueError(f"identical-input classifier repeatability check failed: {repeatability}")

    artifact_dir = work_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_graph(artifact_dir / "eurovoc-english-projection.nt", taxonomy_graph)
    graphs_to_load: dict[str, Graph] = dict(input_graphs)
    graphs_to_load[taxonomy_graph_iri] = taxonomy_graph
    run_ids: dict[tuple[str, str], str] = {}
    enrichment_graphs: dict[tuple[str, str], Graph] = {}
    prediction_by_method = {
        "label-baseline": baseline_predictions,
        "semantic": semantic_predictions,
    }
    settings_by_method = {
        "label-baseline": (se.BASELINE_VERSION, baseline_settings, None),
        "semantic": (se.SEMANTIC_VERSION, semantic_settings, str(model_cache_inventory["sha256"])),
    }
    for method, predictions in prediction_by_method.items():
        method_version, settings, model_hash = settings_by_method[method]
        run_material = {
            "source_manifest_sha256": manifest_hash,
            "input_sample_sha256": input_hash,
            "taxonomy_sha256": taxonomy_digest,
            "method": method,
            "settings": settings,
            "model_sha256": model_hash,
        }
        run_id = se.sha256_bytes(se.canonical_json(run_material))[:20]
        for split in ("development", "evaluation"):
            subset = [row for row in records if row["split"] == split]
            graph_iri = make_graph_iri(method, split, run_id)
            graph = se.build_enrichment_graph(
                subset,
                predictions,
                graph_iri=graph_iri,
                method=method,
                method_version=method_version,
                taxonomy=taxonomy,
                input_hash=se.sample_hash(subset),
                model_sha256=model_hash,
                settings=settings,
            )
            run_ids[(method, split)] = graph_iri
            enrichment_graphs[(method, split)] = graph
            graphs_to_load[graph_iri] = graph
            _write_graph(artifact_dir / f"enrichment-{method}-{split}.nt", graph)
            write_jsonl(
                artifact_dir / f"predictions-{method}-{split}.jsonl",
                prediction_rows(subset, predictions),
            )

    for graph_iri, graph in sorted(input_graphs.items()):
        _write_graph(artifact_dir / ("graph-" + se.sha256_bytes(graph_iri.encode("utf-8"))[:16] + ".nt"), graph)
    if not repeatability["semantic_stable"] or not repeatability["baseline_stable"]:
        raise ValueError("repeatability failed after graph generation")

    stage_times["classification_total_seconds"] = round(
        stage_times["baseline_classification_seconds"]
        + stage_times["model_load_and_candidate_embedding_seconds"]
        + stage_times["semantic_classification_seconds"], 6
    )
    peak_rss_mb = _safe_rss_megabytes()
    if peak_rss_mb > 4096:
        raise MemoryError(f"classification process peak RSS exceeded 4 GiB: {peak_rss_mb:.2f} MiB")

    query_results = None
    if not skip_fuseki:
        query_specs: list[tuple[str, str, str | None]] = []
        for question in questions_doc["questions"]:
            if question["mode"] == "structured-only":
                query_specs.append((str(question["id"]), "structured-only", None))
            else:
                for method in ("label-baseline", "semantic"):
                    query_specs.append((str(question["id"]), method, run_ids[(method, "evaluation")]))
        fuseki_result = execute_fuseki(
            fuseki_base_url,
            fuseki_password,
            graphs_to_load,
            query_specs,
            taxonomy_graph_iri=taxonomy_graph_iri,
            source_rows=source_rows,
            output_dir=artifact_dir,
        )
        query_results = fuseki_result
        stage_times["fuseki_upload_and_queries_seconds"] = round(
            fuseki_result["upload_seconds"] + sum(row["query_seconds"] for row in fuseki_result["queries"]), 6
        )

    reference_metrics = provisional_reference_metrics(
        review_reference,
        questions_doc,
        records,
        baseline_predictions,
        semantic_predictions,
        concepts,
    )
    disk = {
        "taxonomy_bytes": taxonomy_path.stat().st_size,
        "source_bytes": sum(int(source["bytes"]) for source in sources),
        "model_cache_bytes": model_cache_inventory["bytes"],
        "artifact_bytes": sum(path.stat().st_size for path in artifact_dir.rglob("*") if path.is_file()),
    }
    summary = {
        "created_at_utc": started_at,
        "status": "complete" if query_results is not None else "classification-complete-fuseki-skipped",
        "sample_size": len(records),
        "sample_sha256": input_hash,
        "source_manifest_sha256": manifest_hash,
        "sources": source_rows,
        "source_acquisition": source_provenance,
        "taxonomy": {
            **taxonomy,
            "observed_counts": taxonomy_counts,
            "projected_graph_iri": taxonomy_graph_iri,
            "projected_triples": len(taxonomy_graph),
            "raw_bytes": taxonomy_path.stat().st_size,
        },
        "methods": {
            "label-baseline": method_metrics(records, baseline_predictions),
            "semantic": method_metrics(records, semantic_predictions),
        },
        "classifier_parameters": {
            "label-baseline": baseline_settings,
            "semantic": {**semantic_settings, "model_artifact_sha256": model_cache_inventory["sha256"]},
        },
        "model_cache": model_cache_inventory,
        "repeatability": repeatability,
        "provisional_reference_metrics": reference_metrics,
        "classification_peak_rss_mib": peak_rss_mb,
        "disk_bytes": disk,
        "timings_seconds": stage_times,
        "fuseki": query_results,
        "transcript_text_in_rdf": False,
        "warning": "Agent-reviewed judgments are provisional; no human-validated gold standard or calibrated probability is claimed.",
    }
    summary["total_wall_seconds"] = round(time.perf_counter() - wall_started, 6)
    (artifact_dir / "run-summary.json").write_bytes(se.canonical_json(summary) + b"\n")
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    download_parser = subparsers.add_parser("download-sources", help="fetch only the frozen AKN source allowlist")
    download_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    prepare_parser = subparsers.add_parser("prepare", help="validate sources and write a blind review packet before classifiers run")
    prepare_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run_parser = subparsers.add_parser("run", help="classify and optionally load/query isolated loopback Fuseki")
    run_parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    run_parser.add_argument("--taxonomy-path", type=Path, default=DEFAULT_TAXONOMY)
    run_parser.add_argument("--fuseki-base-url", default="http://127.0.0.1:13036/semantic_enrichment")
    run_parser.add_argument("--fuseki-password", default=os.environ.get("FUSEKI_ADMIN_PASSWORD", FUSEKI_PASSWORD_DEFAULT))
    run_parser.add_argument("--skip-fuseki", action="store_true", help="classification-only diagnostic; not end-to-end acceptance")
    run_parser.add_argument(
        "--review-reference", type=Path,
        default=POC_DIR / "results" / "provisional-review.json",
    )
    run_parser.add_argument("--model-threads", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if args.command == "download-sources":
            result = download_sources(args.work_dir)
        elif args.command == "prepare":
            result = prepare_command(args.work_dir)
        else:
            if args.model_threads < 1 or args.model_threads > 8:
                raise ValueError("--model-threads must be between 1 and 8")
            result = run_evaluation(
                work_dir=args.work_dir,
                taxonomy_path=args.taxonomy_path,
                fuseki_base_url=args.fuseki_base_url,
                fuseki_password=args.fuseki_password,
                skip_fuseki=args.skip_fuseki,
                review_reference=args.review_reference,
                model_threads=args.model_threads,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        print(f"semantic-enrichment PoC failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
