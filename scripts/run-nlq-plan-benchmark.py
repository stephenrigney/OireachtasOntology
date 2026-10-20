#!/usr/bin/env python3
"""Run measured Phase 2C plan generation against disposable capture-backed Fuseki."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from time import perf_counter, sleep
import uuid
from urllib.parse import urlsplit

import httpx
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.serializers.nt import _nt_row
from rdflib.store import Store

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.benchmark import (  # noqa: E402
    DEFAULT_BENCHMARK_PATH,
    dataset_association,
    load_benchmark,
    run_cases,
    summarize_results,
)
from poc.nlq.benchmark_isolation import DisposableFuseki  # noqa: E402
from poc.nlq.config import load_local_environment, resolved_llm_configuration  # noqa: E402
from poc.nlq.contract import load_query_contract  # noqa: E402
from poc.nlq.fuseki import FusekiQueryClient  # noqa: E402
from poc.nlq.plan_benchmark import (  # noqa: E402
    run_phase1_comparison,
    run_plan_cases,
    summarize_plan_results,
)
from poc.nlq.planner_benchmark import (  # noqa: E402
    load_planner_benchmark,
)
from poc.nlq.structured_planner import (  # noqa: E402
    ResponsesPlanGenerator,
    StructuredPlanner,
)
from poc.nlq.plan_contract import load_query_plan_contract  # noqa: E402
from poc.nlq.llm import ResponsesTranslator  # noqa: E402
from poc.nlq.vocabulary import supported_predicates  # noqa: E402
from oireachtas_etl.cli import (  # noqa: E402
    DEVELOPMENT_ACCEPTED_DATASET_ID,
    DEVELOPMENT_ACCEPTED_GRAPH_COUNTS,
    DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS,
    _development_graph_family,
)
from oireachtas_etl.loader import FusekiSparqlClient  # noqa: E402


def _scratch_root() -> Path:
    configured = os.getenv("OIR_NLQ_SCRATCH_DIR")
    root = Path(configured).expanduser() if configured else ROOT / "var" / "nlq-scratch"
    if not root.is_absolute():
        root = ROOT / root
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


DEFAULT_REALISTIC_PLANNER_BENCHMARK = (
    ROOT / "poc/nlq/benchmarks/realistic-phase2-planner-v1.json"
)
DEFAULT_SOURCE_BENCHMARK = ROOT / "poc/nlq/benchmarks/realistic-phase2-v1.json"
ACCEPTED_LIVE_GRAPH_INVENTORY_SHA256 = (
    "471532a10a3a6e8ecc307d78d6687a3e5abc89a2490eaa194d60d4e3fba2e117"
)
ACCEPTED_UNRELATED_SENTINEL_GRAPHS = {
    "https://data.oireachtas.ie/graph/member/stale-phase2-marker/external-links",
    "https://data.oireachtas.ie/graph/debate/not-a-debate-work",
    "urn:oir-query-service-phase2:unrelated",
}
QUARANTINED_BILL_GRAPHS = {
    "https://data.oireachtas.ie/graph/bill/1959/P3",
    "https://data.oireachtas.ie/graph/bill/1965/P1",
    "https://data.oireachtas.ie/graph/bill/1965/P3",
    "https://data.oireachtas.ie/graph/bill/2024/48",
}
EXPECTED_RDF_RESOURCE_COUNTS = {
    "house_terms": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS["houses_terms"],
    "members": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS["members"],
    "party_owner_identities": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS["parties"],
    "constituency_panel_owner_identities": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS[
        "constituencies"],
    "committee_owner_identities": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS[
        "committees"],
    "bills": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS["bills"],
    "debates": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS["debates"],
    "office_holdings": DEVELOPMENT_ACCEPTED_RESOURCE_COUNTS["office_holdings"],
}
RESOURCE_COUNT_QUERIES = {
    "house_terms": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { "
        "GRAPH <https://data.oireachtas.ie/graph/houses> { "
        "?resource rdf:type ?class . FILTER(?class IN ("
        "<https://data.oireachtas.ie/ontology#DailTerm>, "
        "<https://data.oireachtas.ie/ontology#SeanadTerm>)) } }"
    ),
    "members": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { "
        "GRAPH ?graph { ?resource rdf:type "
        "<https://data.oireachtas.ie/ontology#Member> } }"
    ),
    "party_owner_identities": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { "
        "GRAPH <https://data.oireachtas.ie/graph/parties> { ?resource rdf:type "
        "<https://data.oireachtas.ie/ontology/members#ParliamentaryMemberCollection> } }"
    ),
    "constituency_panel_owner_identities": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { "
        "GRAPH <https://data.oireachtas.ie/graph/constituencies> { ?resource rdf:type "
        "<https://data.oireachtas.ie/ontology/members#Constituencies> } }"
    ),
    "committee_owner_identities": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { "
        "GRAPH <https://data.oireachtas.ie/graph/committees> { ?resource rdf:type "
        "<https://data.oireachtas.ie/ontology/members#Committee> } }"
    ),
    "bills": (
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { GRAPH ?graph { "
        "?resource <http://data.europa.eu/eli/ontology#type_document> "
        "<https://data.oireachtas.ie/ontology#Bill> } }"
    ),
    "debates": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { GRAPH ?graph { "
        "?resource rdf:type <https://data.oireachtas.ie/ontology#DebateRecord> } }"
    ),
    "office_holdings": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { GRAPH ?graph { "
        "?resource rdf:type <https://data.oireachtas.ie/ontology/members#OfficeHolding> } }"
    ),
    "offices": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { GRAPH ?graph { "
        "?resource rdf:type <https://data.oireachtas.ie/ontology/members#NamedOffice> } }"
    ),
    "administrative_units": (
        "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> "
        "SELECT (COUNT(DISTINCT ?resource) AS ?count) WHERE { GRAPH ?graph { "
        "?resource rdf:type <https://data.oireachtas.ie/ontology/members#AdministrativeUnit> } }"
    ),
}


def _args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark", type=Path, default=DEFAULT_REALISTIC_PLANNER_BENCHMARK,
    )
    parser.add_argument("--source-benchmark", type=Path, default=DEFAULT_SOURCE_BENCHMARK)
    parser.add_argument("--regression-benchmark", type=Path, default=DEFAULT_BENCHMARK_PATH)
    parser.add_argument("--results", type=Path)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument(
        "--state-db", type=Path,
        help="optional path protected from baseline-output overwrite; not read for capture selection",
    )
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--fuseki-image", default="stain/jena-fuseki:5.1.0")
    parser.add_argument("--uv", default="uv")
    parser.add_argument(
        "--compare-phase1", action="store_true",
        help="also run Phase 1 direct generation for comparable source cases",
    )
    return parser.parse_args(argv)


def _write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_bootstrap_phase_timings(stderr: str) -> dict[str, float]:
    timings: dict[str, float] = {}
    inside = False
    for line in stderr.splitlines():
        if line.strip() == "Bootstrap phase timings:":
            inside = True
            continue
        if not inside:
            continue
        match = re.fullmatch(r"\s{4}(.+): ([0-9]+(?:\.[0-9]+)?)s", line)
        if match:
            timings[match.group(1)] = float(match.group(2))
    if "total bootstrap" not in timings:
        raise RuntimeError("development bootstrap did not report phase timings")
    return timings


def _prepare_candidate(args, baseline_path: Path, candidate_path: Path,
                       evidence_path: Path) -> tuple[dict, dict, dict]:
    """Transform, validate, and serialize offline before starting any load."""
    command = [args.uv, "run", "--locked", "oir-etl", "dev", "bootstrap"]
    if args.raw_dir:
        command.extend(["--raw-dir", str(args.raw_dir.expanduser().resolve())])
    if args.state_db:
        command.extend(["--state-db", str(args.state_db.expanduser().resolve())])
    command.extend([
        "--dataset-baseline-output", str(baseline_path),
        "--benchmark-candidate-nquads-output", str(candidate_path),
        "--benchmark-candidate-evidence-output", str(evidence_path),
    ])
    environment = os.environ.copy()
    for name in (
            "OIR_FUSEKI_GSP_URL", "OIR_FUSEKI_SPARQL_URL",
            "OIR_FUSEKI_USER", "OIR_FUSEKI_PASSWORD"):
        environment.pop(name, None)
    started = perf_counter()
    process = subprocess.run(
        command, cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    generation_wall_seconds = perf_counter() - started
    if process.returncode:
        raise RuntimeError(
            "Offline development-data candidate build failed; no dataset was loaded "
            "and no plan benchmark was run.\n"
            + (process.stdout + process.stderr)[-12000:]
        )
    for path, label in (
            (baseline_path, "dataset baseline"),
            (candidate_path, "benchmark candidate N-Quads"),
            (evidence_path, "candidate hash evidence")):
        if not path.is_file():
            raise RuntimeError(f"Development bootstrap did not write its {label}")
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Development bootstrap wrote unreadable candidate evidence: {error}") from error
    if baseline.get("schema_version") != 1:
        raise RuntimeError("Development bootstrap wrote an invalid schema-version-1 baseline")
    if baseline.get("dataset", {}).get("id") != DEVELOPMENT_ACCEPTED_DATASET_ID:
        raise RuntimeError(
            "development candidate identity differs from the accepted dataset ID; "
            "no dataset was loaded and no benchmark was run"
        )
    if evidence.get("schema_version") != 1 or evidence.get("format") != "application/n-quads":
        raise RuntimeError("Development bootstrap wrote invalid benchmark candidate evidence")

    expected_graphs = {
        row["name"]: (row["graph_count"], row["triple_count"])
        for row in baseline["graph_families_loaded"]
    }
    if expected_graphs != DEVELOPMENT_ACCEPTED_GRAPH_COUNTS:
        raise RuntimeError(f"accepted graph-family counts differ: {expected_graphs!r}")
    if baseline.get("rdf_resource_counts") != EXPECTED_RDF_RESOURCE_COUNTS:
        raise RuntimeError(
            "accepted RDF resource counts differ: "
            f"{baseline.get('rdf_resource_counts')!r}"
        )
    if baseline.get("office_registry_evidence", {}).get("office_count") != 3:
        raise RuntimeError("accepted Office resource count differs")
    if baseline.get("office_registry_evidence", {}).get("administrative_unit_count") != 1:
        raise RuntimeError("accepted AdministrativeUnit resource count differs")
    if baseline.get("bill_diagnostic_counts", {}).get("quarantined_bills") != 4:
        raise RuntimeError("accepted Bill quarantine count differs")

    inventory = evidence.get("graph_inventory")
    if not isinstance(inventory, list):
        raise RuntimeError("candidate evidence has no graph inventory")
    inventory_by_iri = {
        item.get("graph_iri"): item for item in inventory if isinstance(item, dict)
    }
    if len(inventory_by_iri) != len(inventory) or None in inventory_by_iri:
        raise RuntimeError("candidate graph inventory has missing or duplicate graph IRIs")
    if len(inventory) != sum(graphs for graphs, _triples in expected_graphs.values()):
        raise RuntimeError("candidate graph inventory count differs from accepted evidence")
    candidate_graph_counts = {}
    candidate_family_counts: dict[str, list[int]] = {}
    for graph_iri, item in inventory_by_iri.items():
        family = item.get("family")
        triple_count = item.get("triple_count")
        if (not isinstance(family, str) or type(triple_count) is not int
                or triple_count < 1 or not re.fullmatch(r"[0-9a-f]{64}",
                    item.get("rdf11_semantic_sha256", ""))):
            raise RuntimeError(f"invalid candidate graph hash evidence for {graph_iri}")
        if _development_graph_family(graph_iri) != family:
            raise RuntimeError(f"candidate graph has an unexpected family: {graph_iri}")
        candidate_graph_counts[graph_iri] = triple_count
        totals = candidate_family_counts.setdefault(family, [0, 0])
        totals[0] += 1
        totals[1] += triple_count
    if {name: tuple(values) for name, values in candidate_family_counts.items()} != expected_graphs:
        raise RuntimeError("candidate per-graph inventory differs from accepted family counts")
    if (evidence.get("graph_count") != 7981
            or evidence.get("triple_count") != 1_119_467
            or sum(candidate_graph_counts.values()) != 1_119_467):
        raise RuntimeError("candidate total graph or triple count differs from accepted evidence")
    if set(candidate_graph_counts) & QUARANTINED_BILL_GRAPHS:
        raise RuntimeError("candidate unexpectedly contains a quarantined Bill graph")

    candidate_inventory_hash = hashlib.sha256(
        "\n".join(sorted(candidate_graph_counts)).encode("utf-8")
    ).hexdigest()
    if evidence.get("graph_iri_inventory_sha256") != candidate_inventory_hash:
        raise RuntimeError("candidate graph-IRI inventory hash is inconsistent")
    accepted_inventory_hash = hashlib.sha256(
        "\n".join(sorted(set(candidate_graph_counts) | ACCEPTED_UNRELATED_SENTINEL_GRAPHS))
        .encode("utf-8")
    ).hexdigest()
    if accepted_inventory_hash != ACCEPTED_LIVE_GRAPH_INVENTORY_SHA256:
        raise RuntimeError(
            "candidate graph IRIs do not reproduce the accepted bootstrap live-inventory hash"
        )
    graph_hash_material = json.dumps(
        inventory, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    if evidence.get("graph_content_inventory_sha256") != hashlib.sha256(
            graph_hash_material).hexdigest():
        raise RuntimeError("candidate per-graph content hash inventory is inconsistent")
    if evidence.get("candidate_byte_count") != candidate_path.stat().st_size:
        raise RuntimeError("candidate N-Quads byte count differs from its evidence")
    with candidate_path.open("rb") as candidate_stream:
        candidate_sha256 = hashlib.file_digest(candidate_stream, "sha256").hexdigest()
    if evidence.get("candidate_sha256") != candidate_sha256:
        raise RuntimeError("candidate N-Quads SHA-256 differs from its evidence")

    timings = _parse_bootstrap_phase_timings(process.stderr)
    if "candidate N-Quads serialization and syntax validation" not in timings:
        raise RuntimeError("candidate build did not report full-dataset parse validation")
    return baseline, evidence, {
        "candidate_generation_wall_seconds": generation_wall_seconds,
        "etl_phase_timings_seconds": timings,
    }


def _graph_inventory(client: FusekiSparqlClient) -> dict[str, int]:
    rows = client.query(
        "SELECT ?graph (COUNT(*) AS ?tripleCount) "
        "WHERE { GRAPH ?graph { ?subject ?predicate ?object } } GROUP BY ?graph"
    )
    counts = {}
    for row in rows:
        graph = row.get("graph", {}).get("value") if isinstance(row, dict) else None
        raw_count = (row.get("tripleCount", {}).get("value")
                     if isinstance(row, dict) else None)
        if not isinstance(graph, str) or graph in counts:
            raise RuntimeError("Fuseki graph inventory returned a missing or duplicate graph IRI")
        try:
            count = int(raw_count)
        except (TypeError, ValueError) as error:
            raise RuntimeError("Fuseki graph inventory returned an invalid triple count") from error
        if count < 1:
            raise RuntimeError("Fuseki graph inventory returned an empty named graph")
        counts[graph] = count
    return counts


def _wait_for_empty_disposable_dataset(instance: DisposableFuseki):
    metadata = instance.isolation_metadata()
    if (metadata.get("disposable") is not True
            or metadata.get("container_auto_removed") is not True
            or metadata.get("persistent_volume_attached") is not False
            or not str(metadata.get("container_name", "")).startswith(
                "oireachtas-nlq-bench-")):
        raise RuntimeError("bulk loading requires the benchmark's disposable Fuseki container")
    for endpoint in (instance.gsp_url, instance.query_url):
        parsed = urlsplit(endpoint or "")
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
            raise RuntimeError("bulk loading is restricted to loopback-only Fuseki endpoints")

    origin = f"http://127.0.0.1:{instance.host_port}"
    deadline = perf_counter() + 90
    last_error = "Fuseki dataset has not finished starting"
    while perf_counter() < deadline:
        try:
            with httpx.Client(
                    auth=("admin", instance.password), timeout=5.0) as http:
                response = http.get(origin + "/$/server")
            response.raise_for_status()
            datasets = response.json().get("datasets", [])
            if datasets:
                names = [item.get("ds.name") for item in datasets]
                if names != ["/houses"]:
                    raise RuntimeError(
                        f"fresh benchmark Fuseki has unexpected datasets: {names!r}"
                    )
                break
        except (OSError, httpx.HTTPError, ValueError) as error:
            last_error = str(error)
        sleep(0.25)
    else:
        raise RuntimeError(f"disposable Fuseki did not expose its dataset: {last_error}")

    client = FusekiSparqlClient(
        instance.query_url, user="admin", password=instance.password, timeout=120,
    )
    if _graph_inventory(client):
        raise RuntimeError("benchmark bulk load refused a Fuseki dataset that is not empty")
    default_rows = client.query(
        "SELECT (COUNT(*) AS ?tripleCount) WHERE { ?subject ?predicate ?object }"
    )
    if len(default_rows) != 1 or int(default_rows[0]["tripleCount"]["value"]) != 0:
        raise RuntimeError("benchmark bulk load refused a non-empty default graph")
    return client


def _file_chunks(path: Path, chunk_size: int = 1024 * 1024):
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            yield chunk


class _NQuadsSortingStore(Store):
    """Parse N-Quads into an external-sort stream without retaining RDF terms."""

    context_aware = True
    graph_aware = True
    formula_aware = False

    def __init__(self, output):
        super().__init__()
        self.output = output
        self.graph_counts: Counter[str] = Counter()

    def add(self, triple, context, quoted=False):
        subject, predicate, obj = triple
        graph = context.identifier
        if any(isinstance(term, BNode) for term in (subject, predicate, obj, graph)):
            raise RuntimeError("Fuseki N-Quads readback contains a blank node")
        if graph == URIRef("urn:x-rdflib:default"):
            raise RuntimeError("Fuseki N-Quads readback contains a default graph triple")
        if not isinstance(graph, URIRef):
            raise RuntimeError("Fuseki N-Quads readback contains a non-IRI graph")
        if (isinstance(obj, Literal) and obj.language is None
                and obj.datatype == XSD.string):
            obj = Literal(str(obj))
        graph_iri = str(graph)
        triple_line = _nt_row((subject, predicate, obj)).rstrip("\n")
        self.output.write(f"{graph_iri}\t{triple_line}\n")
        self.graph_counts[graph_iri] += 1

    def triples(self, triple_pattern, context=None):
        return iter(())

    def __len__(self, context=None):
        return sum(self.graph_counts.values())

    def remove_graph(self, graph):
        return None


def _readback_graph_hashes(instance: DisposableFuseki, path: Path,
                           evidence: dict) -> tuple[dict, float]:
    """Read and syntax-parse once, comparing sorted per-graph semantic hashes."""
    started = perf_counter()
    try:
        with httpx.Client(
                auth=("admin", instance.password),
                timeout=httpx.Timeout(900.0, connect=15.0)) as http:
            with http.stream(
                    "GET", instance.gsp_url,
                    headers={"Accept": "application/n-quads"}) as response:
                response.raise_for_status()
                if "application/n-quads" not in response.headers.get(
                        "Content-Type", "").lower():
                    raise RuntimeError("Fuseki dataset readback was not N-Quads")
                with path.open("wb") as stream:
                    for chunk in response.iter_bytes(1024 * 1024):
                        stream.write(chunk)
    except (OSError, httpx.HTTPError) as error:
        detail = getattr(getattr(error, "response", None), "text", "")
        raise RuntimeError(f"Fuseki dataset-level N-Quads readback failed: {error}; "
                           f"{detail[:2000]}") from error

    sort_input_path = path.with_suffix(path.suffix + ".sort-input")
    readback_byte_count = path.stat().st_size
    parser = _NQuadsSortingStore
    try:
        with sort_input_path.open("w", encoding="utf-8", newline="") as sort_input:
            sink = parser(sort_input)
            Graph(store=sink).parse(source=str(path), format="nquads")
        # The syntax-checked readback has now been reduced to the canonical
        # external-sort stream; remove the redundant raw copy before sorting to
        # keep the benchmark's disposable scratch footprint bounded.
        path.unlink()
        sort_process = subprocess.Popen(
            ["sort", "--buffer-size=128M", "--temporary-directory", str(path.parent),
             "-t", "\t", "-k1,1", "-k2", str(sort_input_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8",
            env={**os.environ, "LC_ALL": "C"},
        )
    except Exception as error:
        sort_input_path.unlink(missing_ok=True)
        if isinstance(error, RuntimeError):
            raise
        raise RuntimeError(f"Fuseki dataset readback N-Quads parse/sort failed: {error}") from error

    expected_by_iri = {
        item["graph_iri"]: item for item in evidence["graph_inventory"]
    }
    remote_hashes = {}
    current_graph = None
    current_count = 0
    current_digest = None

    def finish_graph():
        if current_graph is not None:
            remote_hashes[current_graph] = {
                "triple_count": current_count,
                "rdf11_semantic_sha256": current_digest.hexdigest(),
            }

    try:
        assert sort_process.stdout is not None
        for row in sort_process.stdout:
            try:
                graph_iri, triple_line = row.rstrip("\n").split("\t", 1)
            except ValueError as error:
                raise RuntimeError(
                    f"sorted N-Quads readback row is malformed: {row[:300]!r}"
                ) from error
            if graph_iri != current_graph:
                finish_graph()
                current_graph = graph_iri
                current_count = 0
                current_digest = hashlib.sha256()
            current_count += 1
            current_digest.update((triple_line + "\n").encode("utf-8"))
        sort_stderr = sort_process.stderr.read() if sort_process.stderr is not None else ""
        sort_return_code = sort_process.wait()
    except Exception:
        sort_process.kill()
        sort_process.wait()
        sort_input_path.unlink(missing_ok=True)
        raise
    finish_graph()
    sort_input_path.unlink(missing_ok=True)
    if sort_return_code:
        raise RuntimeError(
            "sorting Fuseki dataset readback failed: "
            f"{sort_stderr.strip() or f'exit status {sort_return_code}'}"
        )

    if sink.graph_counts != Counter({
            graph: item["triple_count"] for graph, item in expected_by_iri.items()}):
        raise RuntimeError("N-Quads readback graph/count inventory differs from candidate")
    if set(remote_hashes) != set(expected_by_iri):
        missing = sorted(set(expected_by_iri) - set(remote_hashes))[:10]
        extra = sorted(set(remote_hashes) - set(expected_by_iri))[:10]
        raise RuntimeError(
            f"N-Quads readback graph inventory differs: missing={missing!r}, extra={extra!r}"
        )

    remote_hash_inventory = []
    changed = []
    for graph_iri in sorted(expected_by_iri):
        expected = expected_by_iri[graph_iri]
        actual = remote_hashes[graph_iri]
        item = {
            "graph_iri": graph_iri,
            "family": expected["family"],
            **actual,
        }
        remote_hash_inventory.append(item)
        if item != expected:
            changed.append(graph_iri)
    if changed:
        raise RuntimeError(
            "bulk-loaded RDF differs semantically from the validated candidate; "
            f"per-graph content hashes differ for {changed[:20]!r}"
        )
    inventory_bytes = json.dumps(
        remote_hash_inventory, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    inventory_sha256 = hashlib.sha256(inventory_bytes).hexdigest()
    if inventory_sha256 != evidence["graph_content_inventory_sha256"]:
        raise RuntimeError("loaded semantic graph-hash inventory digest differs from candidate")
    return {
        "readback_byte_count": readback_byte_count,
        "graph_content_inventory_sha256": inventory_sha256,
        "graph_hashes_verified": len(remote_hash_inventory),
    }, perf_counter() - started


def _verify_loaded_dataset(client: FusekiSparqlClient, baseline: dict,
                           evidence: dict, instance: DisposableFuseki,
                           readback_path: Path) -> tuple[dict, float]:
    expected_inventory = {
        item["graph_iri"]: item["triple_count"]
        for item in evidence["graph_inventory"]
    }
    actual_inventory = _graph_inventory(client)
    if actual_inventory != expected_inventory:
        missing = sorted(set(expected_inventory) - set(actual_inventory))[:10]
        extra = sorted(set(actual_inventory) - set(expected_inventory))[:10]
        changed = sorted(
            graph for graph in set(actual_inventory) & set(expected_inventory)
            if actual_inventory[graph] != expected_inventory[graph]
        )[:10]
        raise RuntimeError(
            "bulk-loaded graph inventory differs from the validated candidate: "
            f"missing={missing!r}, extra={extra!r}, changed_counts={changed!r}"
        )
    if len(actual_inventory) != 7981 or sum(actual_inventory.values()) != 1_119_467:
        raise RuntimeError("bulk-loaded dataset graph/triple totals differ from acceptance")

    family_counts: dict[str, list[int]] = {}
    for graph, triple_count in actual_inventory.items():
        family = _development_graph_family(graph)
        if family is None:
            raise RuntimeError(f"unexpected graph family in fresh benchmark dataset: {graph}")
        totals = family_counts.setdefault(family, [0, 0])
        totals[0] += 1
        totals[1] += triple_count
    expected_families = {
        row["name"]: (row["graph_count"], row["triple_count"])
        for row in baseline["graph_families_loaded"]
    }
    if {name: tuple(value) for name, value in family_counts.items()} != expected_families:
        raise RuntimeError("bulk-loaded graph-family counts differ from accepted baseline")

    resource_counts = {}
    for name, query in RESOURCE_COUNT_QUERIES.items():
        rows = client.query(query)
        if len(rows) != 1:
            raise RuntimeError(f"resource-count probe returned no scalar for {name}")
        resource_counts[name] = int(rows[0]["count"]["value"])
    loaded_rdf_resources = {
        name: resource_counts[name] for name in EXPECTED_RDF_RESOURCE_COUNTS
    }
    if loaded_rdf_resources != EXPECTED_RDF_RESOURCE_COUNTS:
        raise RuntimeError(
            "bulk-loaded RDF resource counts differ from accepted evidence: "
            f"{loaded_rdf_resources!r}"
        )
    office_evidence = baseline["office_registry_evidence"]
    if (resource_counts["offices"] != office_evidence["office_count"]
            or resource_counts["administrative_units"]
            != office_evidence["administrative_unit_count"]):
        raise RuntimeError("bulk-loaded office or administrative-unit resource counts differ")

    actual_graph_iri_hash = hashlib.sha256(
        "\n".join(sorted(actual_inventory)).encode("utf-8")
    ).hexdigest()
    if actual_graph_iri_hash != evidence["graph_iri_inventory_sha256"]:
        raise RuntimeError("loaded graph-IRI inventory hash differs from the candidate")
    for graph in sorted(QUARANTINED_BILL_GRAPHS):
        if graph in actual_inventory or client.query(
                f"SELECT ?subject WHERE {{ GRAPH <{graph}> "
                "{ ?subject ?predicate ?object } } LIMIT 1"):
            raise RuntimeError(f"quarantined Bill graph appeared after bulk load: {graph}")

    for representative in evidence["representative_resources"]:
        query = (
            "SELECT ?subject WHERE { GRAPH <" + representative["graph_iri"] + "> { "
            + representative["subject"] + " " + representative["predicate"] + " "
            + representative["object"] + " } } LIMIT 1"
        )
        if not client.query(query):
            raise RuntimeError(
                "bulk-loaded representative RDF resource is absent: "
                f"{representative['family']} {representative['subject']}"
            )

    semantic_readback, semantic_readback_seconds = _readback_graph_hashes(
        instance, readback_path, evidence)
    return {
        "graph_count": len(actual_inventory),
        "total_triples": sum(actual_inventory.values()),
        "graph_family_counts": {
            name: {"graphs": value[0], "triples": value[1]}
            for name, value in sorted(family_counts.items())
        },
        "rdf_resource_counts": loaded_rdf_resources,
        "office_resource_counts": {
            "offices": resource_counts["offices"],
            "administrative_units": resource_counts["administrative_units"],
        },
        "loaded_graph_iri_inventory_sha256": actual_graph_iri_hash,
        "semantic_readback": semantic_readback,
        "quarantined_bill_graphs_absent": sorted(QUARANTINED_BILL_GRAPHS),
        "representative_resources_verified": len(evidence["representative_resources"]),
    }, semantic_readback_seconds


def _bulk_load_and_verify(args, instance: DisposableFuseki, candidate_path: Path,
                          readback_path: Path, baseline: dict,
                          evidence: dict) -> dict:
    started = perf_counter()
    client = _wait_for_empty_disposable_dataset(instance)
    empty_check_seconds = perf_counter() - started
    started = perf_counter()
    headers = {
        "Content-Type": "application/n-quads",
        "Content-Length": str(candidate_path.stat().st_size),
    }
    try:
        with httpx.Client(
                auth=("admin", instance.password),
                timeout=httpx.Timeout(900.0, connect=15.0)) as http:
            response = http.post(
                instance.gsp_url, content=_file_chunks(candidate_path), headers=headers,
            )
        response.raise_for_status()
    except (OSError, httpx.HTTPError) as error:
        detail = getattr(getattr(error, "response", None), "text", "")
        raise RuntimeError(f"dataset-level N-Quads bulk load failed: {error}; {detail[:2000]}") from error
    load_seconds = perf_counter() - started
    try:
        load_report = response.json()
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("Fuseki bulk load returned invalid JSON") from error
    if load_report.get("quadCount") != evidence["triple_count"]:
        raise RuntimeError(
            "Fuseki bulk-load response quad count differs from candidate: "
            f"{load_report!r}"
        )

    # The candidate has been accepted by Fuseki; its content/hash evidence is
    # already in memory, so release the large temporary N-Quads file before the
    # dataset readback and semantic comparison.
    candidate_path.unlink(missing_ok=True)
    started = perf_counter()
    loaded, semantic_readback_seconds = _verify_loaded_dataset(
        client, baseline, evidence, instance, readback_path)
    verification_seconds = perf_counter() - started
    return {
        "load_response": load_report,
        "post_load_verification": loaded,
        "empty_dataset_check_seconds": empty_check_seconds,
        "bulk_load_seconds": load_seconds,
        "post_load_verification_seconds": verification_seconds,
        "semantic_readback_seconds": semantic_readback_seconds,
    }


def _reproduction_comparison(first: dict, second: dict) -> None:
    if first["baseline"] != second["baseline"]:
        raise RuntimeError("two fresh bulk-bootstrap baselines differ")
    first_evidence = first["evidence"]
    second_evidence = second["evidence"]
    for key in (
            "candidate_sha256", "candidate_byte_count", "graph_count",
            "triple_count", "graph_iri_inventory_sha256",
            "graph_content_inventory_sha256"):
        if first_evidence.get(key) != second_evidence.get(key):
            raise RuntimeError(f"two fresh candidate RDF {key} values differ")
    if first["verification"] != second["verification"]:
        raise RuntimeError("two fresh bulk-loaded dataset verification reports differ")


def _bootstrap_run_summary(iteration: int, baseline: dict, evidence: dict,
                           build_timings: dict, instance: DisposableFuseki,
                           load_result: dict, fuseki_startup_seconds: float) -> dict:
    timings = build_timings["etl_phase_timings_seconds"]
    total = (
        build_timings["candidate_generation_wall_seconds"]
        + fuseki_startup_seconds
        + load_result["empty_dataset_check_seconds"]
        + load_result["bulk_load_seconds"]
        + load_result["post_load_verification_seconds"]
    )
    return {
        "run": iteration,
        "dataset_id": baseline["dataset"]["id"],
        "graph_family_counts": {
            row["name"]: {"graphs": row["graph_count"], "triples": row["triple_count"]}
            for row in baseline["graph_families_loaded"]
        },
        "rdf_resource_counts": baseline["rdf_resource_counts"],
        "graph_count": evidence["graph_count"],
        "total_triples": evidence["triple_count"],
        "candidate_rdf": {
            "format": evidence["format"],
            "byte_count": evidence["candidate_byte_count"],
            "sha256": evidence["candidate_sha256"],
            "graph_iri_inventory_sha256": evidence["graph_iri_inventory_sha256"],
            "graph_content_inventory_sha256": evidence[
                "graph_content_inventory_sha256"],
            "accepted_live_inventory_sha256_with_prior_sentinels": (
                ACCEPTED_LIVE_GRAPH_INVENTORY_SHA256
            ),
        },
        "loaded_dataset_verification": load_result["post_load_verification"],
        "timings_seconds": {
            "candidate_generation_wall": build_timings[
                "candidate_generation_wall_seconds"],
            "etl_phases": timings,
            "disposable_fuseki_startup": fuseki_startup_seconds,
            "empty_dataset_check": load_result["empty_dataset_check_seconds"],
            "dataset_level_bulk_load": load_result["bulk_load_seconds"],
            "post_load_verification": load_result[
                "post_load_verification_seconds"],
            "semantic_dataset_readback": load_result["semantic_readback_seconds"],
            "total_setup": total,
        },
        "isolation": instance.isolation_metadata(),
    }


def main(argv: list[str] | None = None) -> int:
    args = _args(argv)
    process_environment = os.environ.copy()
    load_local_environment(ROOT)
    planner_configuration = resolved_llm_configuration(
        ROOT, process_environment=process_environment,
    )
    planner_benchmark = load_planner_benchmark(args.benchmark)
    source_benchmark = load_benchmark(args.source_benchmark)
    regression_benchmark = load_benchmark(args.regression_benchmark)
    if not os.getenv("NLQ_LLM_API_KEY"):
        raise SystemExit("NLQ_LLM_API_KEY is required for the measured plan benchmark")
    expected_dataset = source_benchmark.get("dataset_evidence", {}).get("dataset_id")
    if expected_dataset != DEVELOPMENT_ACCEPTED_DATASET_ID:
        raise SystemExit(
            "the realistic Phase 2 benchmark must pin the accepted development dataset ID"
        )

    run_id = str(uuid.uuid4())
    result_path = args.results or ROOT / "var" / "nlq-plan-benchmark" / "runs" / f"{run_id}.json"
    scratch_root = _scratch_root()
    os.environ["OIR_NLQ_SCRATCH_DIR"] = str(scratch_root)

    try:
        with tempfile.TemporaryDirectory(prefix="run-", dir=scratch_root) as work_dir:
            reproduction_runs = []
            previous = None
            result = None
            for iteration in (1, 2):
                print(
                    f"[bootstrap {iteration}/2] transforming, validating, and "
                    "serializing offline N-Quads candidate",
                    flush=True,
                )
                run_dir = Path(work_dir) / f"bulk-bootstrap-{iteration}"
                run_dir.mkdir()
                baseline, evidence, build_timings = _prepare_candidate(
                    args,
                    run_dir / "development-dataset-baseline.json",
                    run_dir / "candidate.nq",
                    run_dir / "candidate-evidence.json",
                )
                if baseline["dataset"]["id"] != expected_dataset:
                    raise RuntimeError(
                        "development dataset identity mismatch; no dataset was loaded "
                        "and no benchmark was run"
                    )
                print(
                    f"[bootstrap {iteration}/2] candidate accepted: "
                    f"{evidence['graph_count']} graphs, {evidence['triple_count']} triples, "
                    f"sha256={evidence['candidate_sha256']}",
                    flush=True,
                )

                print(f"[bootstrap {iteration}/2] starting fresh disposable Fuseki", flush=True)
                startup_started = perf_counter()
                with DisposableFuseki(
                        docker=args.docker, image=args.fuseki_image) as instance:
                    fuseki_startup_seconds = perf_counter() - startup_started
                    print(
                        f"[bootstrap {iteration}/2] bulk loading and verifying "
                        "the empty loopback dataset",
                        flush=True,
                    )
                    load_result = _bulk_load_and_verify(
                        args, instance, run_dir / "candidate.nq",
                        run_dir / "loaded-readback.nq", baseline, evidence,
                    )
                    run_summary = _bootstrap_run_summary(
                        iteration, baseline, evidence, build_timings, instance,
                        load_result, fuseki_startup_seconds,
                    )
                    print(
                        f"[bootstrap {iteration}/2] verified candidate and "
                        f"semantic readback; setup={run_summary['timings_seconds']['total_setup']:.3f}s",
                        flush=True,
                    )
                    # The accepted dataset now lives only in the disposable
                    # Fuseki. Remove large candidate/readback RDF files as soon
                    # as their hash evidence has been recorded.
                    (run_dir / "candidate.nq").unlink(missing_ok=True)
                    (run_dir / "loaded-readback.nq").unlink(missing_ok=True)
                    current = {
                        "baseline": baseline,
                        "evidence": evidence,
                        "verification": load_result["post_load_verification"],
                    }
                    if previous is not None:
                        _reproduction_comparison(previous, current)
                        reproduction_runs.append(run_summary)
                        print(
                            "[bootstrap 2/2] dataset identity, counts, candidate hashes, "
                            "graph inventory, and loaded RDF match run 1; starting benchmark",
                            flush=True,
                        )

                        client = FusekiQueryClient(
                            instance.query_url, username="admin",
                            password=instance.password,
                        )
                        predicates = supported_predicates(ROOT / "ontology")
                        query_schema_contract = load_query_contract()
                        query_plan_contract = load_query_plan_contract()
                        api_key = os.getenv("NLQ_LLM_API_KEY", "")
                        base_url = planner_configuration["base_endpoint"]["value"]
                        model = planner_configuration["model"]["value"]

                        def planner_factory(_case, fuseki):
                            draft_generator = ResponsesPlanGenerator(
                                api_key, base_url, model,
                            )
                            return StructuredPlanner(
                                draft_generator, fuseki,
                                supported_predicates=predicates,
                            )

                        try:
                            regression_results = run_cases(
                                regression_benchmark, baseline,
                                fuseki=client,
                                tier="regression",
                                repository_root=ROOT,
                            )
                            case_results = run_plan_cases(
                                planner_benchmark, source_benchmark, baseline,
                                fuseki=client,
                                supported_predicates=predicates,
                                planner_factory=planner_factory,
                            )
                            phase1_comparison = None
                            if args.compare_phase1:
                                phase1_comparison = run_phase1_comparison(
                                    planner_benchmark, source_benchmark, baseline,
                                    fuseki=client,
                                    repository_root=ROOT,
                                    translator_factory=lambda _case: ResponsesTranslator(
                                        api_key, base_url, model,
                                    ),
                                )
                        finally:
                            client.close()

                        result = {
                            "result_schema_version": 1,
                            "run_id": run_id,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            "benchmark_id": planner_benchmark["benchmark_id"],
                            "benchmark_version": planner_benchmark["benchmark_version"],
                            "benchmark_artifact": {
                                "path": str(args.benchmark.resolve()),
                                "sha256": hashlib.sha256(
                                    args.benchmark.read_bytes()).hexdigest(),
                            },
                            "source_benchmark": {
                                "benchmark_id": source_benchmark["benchmark_id"],
                                "benchmark_version": source_benchmark["benchmark_version"],
                                "path": str(args.source_benchmark.resolve()),
                                "sha256": hashlib.sha256(
                                    args.source_benchmark.read_bytes()).hexdigest(),
                            },
                            "deterministic_regression": {
                                "benchmark_id": regression_benchmark["benchmark_id"],
                                "benchmark_version": regression_benchmark[
                                    "benchmark_version"],
                                "path": str(args.regression_benchmark.resolve()),
                                "sha256": hashlib.sha256(
                                    args.regression_benchmark.read_bytes()
                                ).hexdigest(),
                                "tier": "regression",
                                "case_results": regression_results,
                                "summary": summarize_results(regression_results),
                            },
                            "tier": "measured",
                            "planner_configuration": planner_configuration,
                            "query_schema_contract": {
                                "schema_version": query_schema_contract[
                                    "schemaVersion"],
                                "contract_version": query_schema_contract[
                                    "contractVersion"],
                            },
                            "query_plan_contract": {
                                "schema_version": query_plan_contract[
                                    "schemaVersion"],
                                "contract_version": query_plan_contract[
                                    "contractVersion"],
                            },
                            "dataset_association": dataset_association(
                                baseline, instance.isolation_metadata(),
                            ),
                            "bootstrap_reproduction": {
                                "accepted_dataset_id": DEVELOPMENT_ACCEPTED_DATASET_ID,
                                "reproduced_twice": True,
                                "accepted_live_inventory_sha256": (
                                    ACCEPTED_LIVE_GRAPH_INVENTORY_SHA256
                                ),
                                "runs": reproduction_runs,
                            },
                            "case_results": case_results,
                            "summary": summarize_plan_results(case_results),
                            "phase1_comparison": phase1_comparison,
                        }
                    else:
                        previous = current
                        first_run_summary = run_summary

            if result is None:
                raise RuntimeError("both reproducibility bootstraps did not complete")
            # Run 1 is added after both runs have been independently verified;
            # order is explicit even though run 2's dataset was benchmarked.
            result["bootstrap_reproduction"]["runs"] = [
                first_run_summary, *reproduction_runs,
            ]
            _write_result(result_path, result)
    except (OSError, RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(json.dumps({
        "run_id": run_id,
        "tier": "measured",
        "benchmark": f"{planner_benchmark['benchmark_id']}@{planner_benchmark['benchmark_version']}",
        "dataset_id": result["dataset_association"]["dataset_id"],
        "query_schema_contract": result["query_schema_contract"],
        "query_plan_contract": result["query_plan_contract"],
        "deterministic_regression": result["deterministic_regression"]["summary"],
        "dataset_instance": result["dataset_association"]["isolation"]["container_id"],
        "bootstrap_reproduction": {
            "reproduced_twice": result["bootstrap_reproduction"]["reproduced_twice"],
            "candidate_rdf_sha256": [
                run["candidate_rdf"]["sha256"]
                for run in result["bootstrap_reproduction"]["runs"]
            ],
            "timings_seconds": [
                run["timings_seconds"]
                for run in result["bootstrap_reproduction"]["runs"]
            ],
        },
        "summary": result["summary"],
        "phase1_comparison": (
            result["phase1_comparison"]["summary"] if result["phase1_comparison"] else None
        ),
        "results": str(result_path),
    }, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
