"""Measurement-only resource assessment for the Phase 7 Debates production gate.

This tool measures the proposed initial-production scopes:

* Scenario A - Dail + Seanad + committee debate records from 2011 onward,
  no written answers, known malformed 2011-2012 records quarantined.
* Scenario B - Scenario A plus complete whole-record written-answer
  ``main.xml`` files from 2013 onward.

It drives the *completed Tranche 4 path* (``run_debate_batch`` and, for the
publication measurements, the same Core State dirty -> GSP PUT -> whole-graph
verification -> clean order) rather than the earlier Tranche 2 transformer
benchmark.  It never mutates ontology, mappings, fixtures or production graphs.

The approved disposable publication target is the loopback Fuseki dataset used
by the Tranche 4 acceptance test.  This tool refuses to publish anywhere else.

Subcommands::

    python -m tools.debates_scope_assessment census   --out DIR [--start-year 2011]
    python -m tools.debates_scope_assessment acquire  --out DIR --raw-root DIR [--workers 8]
    python -m tools.debates_scope_assessment scan     --out DIR --raw-root DIR [--limit N]
    python -m tools.debates_scope_assessment publish  --out DIR --raw-root DIR --state-db F \
        --gsp URL --sparql URL [--sample-per-category N]

Network is required for ``census`` and ``acquire``; ``scan`` and ``publish``
replay the exact preserved objects offline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import statistics
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from oireachtas_etl import competency  # noqa: E402
from oireachtas_etl.config import COMMITTEES_GRAPH, HOUSES_GRAPH  # noqa: E402
from oireachtas_etl.debates_pipeline import run_debate_batch  # noqa: E402
from oireachtas_etl.debates_raw import (  # noqa: E402
    DebateSourceError,
    fetch_main_xml,
    load_main_xml,
    persist_main_xml,
)
from oireachtas_etl.loader import FusekiGraphStoreLoader, FusekiSparqlClient  # noqa: E402
from oireachtas_etl.serialization import nquads, ntriples  # noqa: E402
from oireachtas_etl.state import CoreStateStore  # noqa: E402
from oireachtas_etl.transforms.committees import transform_committees  # noqa: E402
from oireachtas_etl.transforms.houses import transform_houses  # noqa: E402
from oireachtas_etl.transforms.members import member_graph_iri, transform_member  # noqa: E402
from oireachtas_etl.validation.committees import validate_committees  # noqa: E402
from oireachtas_etl.validation.houses import validate_houses  # noqa: E402
from oireachtas_etl.validation.members import validate_member  # noqa: E402

DEFAULT_START_YEAR = 2011
DEFAULT_WRITTEN_START_YEAR = 2013
DEFAULT_END_YEAR = datetime.now(timezone.utc).year
API = "https://api.oireachtas.ie/v1"
USER_AGENT = "OireachtasOntology-debates-scope-assessment/1.0 (measurement-only)"
PUBLISH_HOSTS = {"127.0.0.1", "localhost", "::1"}
PUBLISH_PORT = 13035
PUBLISH_DATASET = "debates_t4"


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, sort_keys=True), encoding="utf-8")


def _read(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _api_get(path: str, *, attempts: int = 5) -> dict:
    import urllib.error
    import urllib.request

    delay = 1.0
    for attempt in range(attempts):
        request = urllib.request.Request(
            API + path, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(f"API request failed: {path}") from error
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise AssertionError("unreachable")


def _head(url: str, *, attempts: int = 4) -> dict:
    import urllib.error
    import urllib.request

    delay = 0.5
    for attempt in range(attempts):
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                length = response.headers.get("Content-Length")
                return {"url": url, "status": response.status,
                        "bytes": int(length) if length else None}
        except urllib.error.HTTPError as error:
            if error.code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                time.sleep(delay); delay = min(delay * 2, 20); continue
            return {"url": url, "status": error.code, "bytes": None}
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts - 1:
                return {"url": url, "status": -1, "bytes": None, "error": str(error)}
            time.sleep(delay); delay = min(delay * 2, 20)
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------
# census

def enumerate_debates(start_year: int, end_year: int) -> list[dict]:
    records: list[dict] = []
    for year in range(start_year, end_year + 1):
        skip = 0
        while True:
            payload = _api_get(
                f"/debates?date_start={year}-01-01&date_end={year}-12-31&limit=1000&skip={skip}")
            results = payload.get("results", [])
            for row in results:
                record = row.get("debateRecord", {})
                house = record.get("house", {}) or {}
                formats = record.get("formats") or {}
                records.append({
                    "date": record.get("date") or row.get("contextDate"),
                    "debate_type": record.get("debateType"),
                    "chamber_type": house.get("chamberType"),
                    "house_code": house.get("houseCode"),
                    "committee_code": house.get("committeeCode"),
                    "work_uri": record.get("uri"),
                    "xml_uri": (formats.get("xml") or {}).get("uri"),
                })
            if len(results) < 1000:
                break
            skip += 1000
        print(f"debates {year}: collected cumulative {len(records)}", flush=True)
    return records


def command_census(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    end = args.end_year or DEFAULT_END_YEAR
    debates = enumerate_debates(args.start_year, end)
    _write(out / "census_debates_raw.json", debates)

    # Deduplicate by exact xml_uri (one API listing duplicate is known).
    unique: dict[str, dict] = {}
    for row in debates:
        url = row.get("xml_uri")
        if url:
            unique.setdefault(url, row)
    print(f"debates unique xml_uri: {len(unique)}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        heads = list(pool.map(_head, sorted(unique)))
    _write(out / "census_debates_head.json", heads)

    # Whole-record written answers are discovered by official sitting-date
    # cross-check of the .../writtens/mul@/main.xml object, exactly as the
    # benchmark cross-check did.  The questions API caps and skip limit make a
    # questions-only enumeration incomplete (it also misses a real
    # sitting-derived file), so the authoritative AKN object existence check is
    # used as the source of truth.  Written answers are Dail-only.
    written_urls: set[str] = set()
    dail_dates = sorted({row["date"] for row in unique.values()
                         if row.get("house_code") == "dail" and row.get("date")})
    for date in dail_dates:
        if date >= f"{args.written_start_year}-01-01":
            written_urls.add(
                f"https://data.oireachtas.ie/akn/ie/debateRecord/dail/{date}/writtens/mul@/main.xml")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        written_heads = list(pool.map(_head, sorted(written_urls)))
    _write(out / "census_written_head.json", written_heads)
    present = [row for row in written_heads if row.get("status") == 200 and row.get("bytes")]
    print(f"written urls: {len(written_urls)} present whole-record: {len(present)}", flush=True)

    manifest = build_manifest(out)
    _write(out / "scenario_manifest.json", manifest)
    print(json.dumps(manifest_summary(manifest), indent=1))
    return 0


def _category(row: dict) -> str:
    return "committee" if row.get("chamber_type") == "committee" else row.get("house_code")


def build_manifest(out: Path) -> dict:
    """Derive the exact per-scenario corpus from the census."""
    records = _read(out / "census_debates_raw.json", [])
    head = {row["url"]: row.get("bytes")
            for row in (_read(out / "census_debates_head.json", []) or [])}
    unique: dict[str, dict] = {}
    for row in records:
        url = row.get("xml_uri")
        if url:
            unique.setdefault(url, row)

    scenario_a = []
    for url, row in sorted(unique.items()):
        date = row.get("date") or ""
        if date < f"{DEFAULT_START_YEAR}-01-01":
            continue
        size = head.get(url)
        if size is None:
            continue
        scenario_a.append({
            "url": url, "date": date, "category": _category(row),
            "house_code": row.get("house_code"), "bytes": size,
        })

    written = []
    for row in (_read(out / "census_written_head.json", []) or []):
        url = row.get("url")
        if row.get("status") == 200 and row.get("bytes"):
            date = url.split("/dail/")[1][:10]
            if date >= f"{DEFAULT_WRITTEN_START_YEAR}-01-01":
                written.append({"url": url, "date": date, "category": "written",
                                "bytes": row["bytes"]})

    return {"scenario_a": scenario_a, "scenario_b_written": written}


def _aggregate(rows: list[dict]) -> dict:
    by = defaultdict(lambda: {"records": 0, "bytes": 0})
    for row in rows:
        by[row["category"]]["records"] += 1
        by[row["category"]]["bytes"] += row["bytes"]
    return {
        "records": sum(v["records"] for v in by.values()),
        "bytes": sum(v["bytes"] for v in by.values()),
        "by_category": {k: dict(v) for k, v in sorted(by.items())},
    }


def manifest_summary(manifest: dict) -> dict:
    a = manifest["scenario_a"]
    w = manifest["scenario_b_written"]
    b = a + w
    return {
        "scenario_a": _aggregate(a),
        "scenario_b_written_increment": _aggregate(w),
        "scenario_b_total": _aggregate(b),
    }


# --------------------------------------------------------------------------
# acquisition

def command_acquire(args) -> int:
    out = Path(args.out)
    raw_root = Path(args.raw_root).expanduser()
    manifest = _read(out / "scenario_manifest.json")
    targets = manifest["scenario_a"] + manifest["scenario_b_written"]
    # Stable, deterministic order; owners first is irrelevant.
    rows: list[dict] = []
    started = time.perf_counter()

    def acquire(row: dict) -> dict:
        entry = dict(row)
        t0 = time.perf_counter()
        try:
            body, final_url = fetch_main_xml(row["url"], retries=3, timeout=60)
            source = persist_main_xml(raw_root, body, final_url)
            entry.update(status="ok", source_sha256=source.source_sha256,
                         raw_path=str(source.raw_path.resolve()),
                         fetched_bytes=len(body))
        except Exception as error:  # noqa: BLE001 - recorded for review
            entry.update(status="fetch-error", error=f"{type(error).__name__}: {error}")
        entry["wall_seconds"] = time.perf_counter() - t0
        return entry

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, entry in enumerate(pool.map(acquire, targets), start=1):
            rows.append(entry)
            if index % 500 == 0:
                print(f"acquire {index}/{len(targets)}", flush=True)

    _write(out / "acquisition.json", rows)
    ok = [r for r in rows if r["status"] == "ok"]
    print(json.dumps({
        "records": len(rows), "acquired": len(ok),
        "acquired_bytes": sum(r["fetched_bytes"] for r in ok),
        "wall_seconds": time.perf_counter() - started,
        "network_seconds": sum(r["wall_seconds"] for r in rows),
        "fetch_errors": Counter(r["status"] for r in rows).get("fetch-error", 0),
    }, indent=1))
    return 0


# --------------------------------------------------------------------------
# scan (Tranche 4 non-publishing path)

def _peak_rss_kib() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _select_scan_rows(rows: list[dict], per_category: int, include_before_year: int) -> list[dict]:
    """Size-stratified per-category sample plus every pre-cutoff record."""
    by: dict[str, list[dict]] = defaultdict(list)
    selected: dict[str, dict] = {}
    for row in rows:
        by[row["category"]].append(row)
        if row["date"] < f"{include_before_year}-01-01":
            selected[row["url"]] = row
    for category, group in sorted(by.items()):
        group = sorted(group, key=lambda r: (r["bytes"], r["url"]))
        n = min(per_category, len(group))
        for i in range(n):
            index = round(i * (len(group) - 1) / max(1, n - 1)) if n > 1 else 0
            selected.setdefault(group[index]["url"], group[index])
    return sorted(selected.values(), key=lambda r: r["url"])


def _random_scan_rows(rows: list[dict], per_category: int, after_year: int,
                      seed: int) -> list[dict]:
    """Every pre-cutoff record plus a uniform random post-cutoff sample."""
    import random
    rng = random.Random(seed)
    selected: dict[str, dict] = {}
    by: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["date"] < f"{after_year}-01-01":
            selected[row["url"]] = row
        else:
            by[row["category"]].append(row)
    for category, group in sorted(by.items()):
        group = sorted(group, key=lambda r: r["url"])
        for row in rng.sample(group, min(per_category, len(group))):
            selected[row["url"]] = row
    return sorted(selected.values(), key=lambda r: r["url"])


def command_scan(args) -> int:
    out = Path(args.out)
    raw_root = Path(args.raw_root).expanduser()
    rows = _read(out / "acquisition.json", [])
    rows = [r for r in rows if r.get("status") == "ok"]
    if args.select == "stratified":
        rows = _select_scan_rows(rows, args.sample_per_category, args.include_before_year)
    elif args.select == "random":
        rows = _random_scan_rows(rows, args.sample_per_category,
                                 args.include_before_year, args.sample_seed)
    if args.limit:
        rows = rows[: args.limit]
    if args.shards > 1:
        rows = rows[args.shard:: args.shards]
    results: list[dict] = []
    started = time.perf_counter()
    rss_peak = 0
    for index, row in enumerate(rows, start=1):
        source = load_main_xml(raw_root, row["source_sha256"])
        entry = {
            "url": row["url"], "date": row["date"], "category": row["category"],
            "source_bytes": row["bytes"], "source_sha256": row["source_sha256"],
        }
        t0 = time.perf_counter()
        try:
            outcomes = run_debate_batch([source])
            outcome = outcomes[0]
            graph = outcome.graph
            entry.update(status="ok", triples=len(graph))
            ser0 = time.perf_counter()
            entry["nquads_bytes"] = len(nquads(graph, outcome.graph_iri).encode("utf-8"))
            entry["ntriples_bytes"] = len(ntriples(graph).encode("utf-8"))
            entry["serialize_seconds"] = time.perf_counter() - ser0
            entry["work_iri"] = outcome.work_iri
            entry["graph_iri"] = outcome.graph_iri
            report_paths = list(source.raw_path.parent.glob(
                f"{source.source_sha256}.*.reference-report.json"))
            entry["reference_reports"] = len(report_paths)
            entry["reference_report_bytes"] = sum(p.stat().st_size for p in report_paths)
            entry["raw_xml_bytes"] = source.raw_path.stat().st_size
            meta = list(source.raw_path.parent.glob(
                f"{source.source_sha256}.*.meta.json"))
            entry["raw_meta_bytes"] = sum(p.stat().st_size for p in meta)
        except Exception as error:  # noqa: BLE001 - recorded for review
            entry.update(status="fail", error=f"{type(error).__name__}: {error}")
        entry["tranche4_seconds"] = time.perf_counter() - t0
        rss_peak = max(rss_peak, _peak_rss_kib())
        results.append(entry)
        if index % 200 == 0:
            print(f"scan {index}/{len(rows)}", flush=True)

    tag = getattr(args, "tag", "") or ""
    name = f"scan{tag}.json" if args.shards <= 1 else f"scan_shard{args.shard}{tag}.json"
    _write(out / name, results)
    print(json.dumps(scan_summary(results, time.perf_counter() - started,
                                  rss_peak, args.scenario), indent=1))
    return 0


def command_merge_scan(args) -> int:
    out = Path(args.out)
    tag = getattr(args, "tag", "") or ""
    parts = sorted(out.glob(f"scan_shard*{tag}.json"))
    if not parts:
        parts = [out / f"scan{tag}.json"] if (out / f"scan{tag}.json").exists() else []
    combined: list[dict] = []
    for part in parts:
        combined.extend(_read(part, []))
    _write(out / f"scan{tag}.json", combined)
    wall = sum(r.get("tranche4_seconds", 0.0) for r in combined if r["status"] == "ok")
    print(json.dumps(scan_summary(combined, wall, 0, args.scenario), indent=1))
    return 0


def scan_summary(results: list[dict], wall: float, rss_peak: int, scenario: str) -> dict:
    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] != "ok"]
    by = defaultdict(lambda: {"records": 0, "ok": 0, "source_bytes": 0,
                              "triples": 0, "nquads_bytes": 0,
                              "reference_report_bytes": 0,
                              "raw_xml_bytes": 0, "raw_meta_bytes": 0,
                              "tranche4_seconds": 0.0, "serialize_seconds": 0.0})
    for r in results:
        bucket = by[r["category"]]
        bucket["records"] += 1
        bucket["source_bytes"] += r.get("source_bytes") or 0
        if r["status"] == "ok":
            bucket["ok"] += 1
            for key in ("triples", "nquads_bytes", "reference_report_bytes",
                        "raw_xml_bytes", "raw_meta_bytes"):
                bucket[key] += r.get(key) or 0
            bucket["tranche4_seconds"] += r.get("tranche4_seconds") or 0
            bucket["serialize_seconds"] += r.get("serialize_seconds") or 0
    return {
        "scenario": scenario,
        "records": len(results),
        "ok": len(ok),
        "failed": len(failed),
        "failed_bytes": sum(r.get("source_bytes") or 0 for r in failed),
        "wall_seconds": wall,
        "rss_peak_kib": rss_peak,
        "confirmed_transforms": sum(r.get("triples", 0) for r in ok),
        "serialized_nquads_bytes": sum(r.get("nquads_bytes", 0) for r in ok),
        "reference_report_bytes": sum(r.get("reference_report_bytes", 0) for r in ok),
        "raw_xml_bytes": sum(r.get("raw_xml_bytes", 0) for r in ok),
        "raw_meta_bytes": sum(r.get("raw_meta_bytes", 0) for r in ok),
        "tranche4_seconds": sum(r.get("tranche4_seconds", 0.0) for r in ok),
        "serialize_seconds": sum(r.get("serialize_seconds", 0.0) for r in ok),
        "by_category": {k: dict(v) for k, v in sorted(by.items())},
        "failures": [
            {"url": r["url"], "category": r["category"], "bytes": r.get("source_bytes"),
             "error": r.get("error", "")[:160]}
            for r in failed
        ],
    }


# --------------------------------------------------------------------------
# publication (disposable Fuseki only)

def _require_disposable(gsp: str, sparql: str) -> None:
    try:
        g, q = urlsplit(gsp), urlsplit(sparql)
    except ValueError as error:
        raise ValueError("invalid disposable Fuseki endpoint URL") from error
    if (g.scheme != "http" or q.scheme != "http"
            or g.hostname not in PUBLISH_HOSTS or q.hostname not in PUBLISH_HOSTS
            or g.port != PUBLISH_PORT or q.port != PUBLISH_PORT
            or g.path != f"/{PUBLISH_DATASET}/data" or q.path != f"/{PUBLISH_DATASET}/query"
            or g.username or g.password or q.username or q.password):
        raise ValueError(
            f"assessment publication requires the loopback :{PUBLISH_PORT} "
            f"{PUBLISH_DATASET} /data and /query endpoints")


def _seed_owner_state(store: CoreStateStore, loader, client) -> dict[str, str]:
    member_source = json.loads((REPOSITORY_ROOT / "data/api_examples/member.json").read_text())
    houses_source = json.loads((REPOSITORY_ROOT / "data/api_examples/houses.json").read_text())
    committees_source = json.loads(
        (REPOSITORY_ROOT / "tests/fixtures/committee-owner.json").read_text())
    member_graph = transform_member(member_source)
    house_graph = transform_houses(houses_source)
    committee_graph = transform_committees(committees_source)
    validate_member(member_source, member_graph)
    validate_houses(houses_source, house_graph)
    validate_committees(committees_source, committee_graph)

    payloads = {}
    for endpoint, graph_iri, graph in (
            ("houses", HOUSES_GRAPH, house_graph),
            ("committees", COMMITTEES_GRAPH, committee_graph)):
        payload = ntriples(graph)
        digest = store.mark_endpoint_dirty(endpoint, graph_iri, payload)
        store.complete_endpoint_publication(endpoint, graph_iri, digest)
        loader.replace(graph_iri, payload, content_type="application/n-triples")
        competency.verify_core_graph(client, graph_iri, payload)
        payloads[graph_iri] = payload

    member = member_source["member"]
    graph_iri = member_graph_iri(member)
    run_id = store.start_run("members", "full_refresh", is_complete=False,
                             parameters={"source": "assessment-owner-example"})
    source_hash = hashlib.sha256(
        json.dumps(member, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    store.observe_resource("members", member["uri"], graph_iri, source_hash, run_id)
    payload = ntriples(member_graph)
    digest = store.mark_publication_dirty(
        "members", member["uri"], source_hash=source_hash, graph_iri=graph_iri,
        payload=payload, contract_version=3)
    store.complete_publication("members", member["uri"], source_hash=source_hash,
                               graph_iri=graph_iri, payload_hash=digest, contract_version=3)
    store.finish_run(run_id, success=True)
    loader.replace(graph_iri, payload, content_type="application/n-triples")
    competency.verify_core_graph(client, graph_iri, payload)
    payloads[graph_iri] = payload
    return payloads


def _stratified_sample(rows: list[dict], per_category: int, seed: int) -> list[dict]:
    import random
    rng = random.Random(seed)
    by: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by[row["category"]].append(row)
    selected: dict[str, dict] = {}
    for category, group in sorted(by.items()):
        group = sorted(group, key=lambda r: (r["bytes"], r["url"]))
        n = min(per_category, len(group))
        # Deterministic size-stratified selection across the category.
        for i in range(n):
            idx = round(i * (len(group) - 1) / max(1, n - 1)) if n > 1 else 0
            selected.setdefault(group[idx]["url"], group[idx])
    return sorted(selected.values(), key=lambda r: r["url"])


def command_publish(args) -> int:
    out = Path(args.out)
    raw_root = Path(args.raw_root).expanduser()
    _require_disposable(args.gsp, args.sparql)
    acquisition = {r["url"]: r for r in _read(out / "acquisition.json", [])
                   if r.get("status") == "ok"}
    manifest = _read(out / "scenario_manifest.json")
    scenario = args.scenario
    if scenario == "A":
        rows = manifest["scenario_a"]
        tag = "a"
    elif scenario == "B":
        rows = manifest["scenario_a"] + manifest["scenario_b_written"]
        tag = "b"
    elif scenario == "written":
        rows = manifest["scenario_b_written"]
        tag = "written"
    else:
        raise ValueError("scenario must be A, B or written")
    rows = [r for r in rows if r["url"] in acquisition]
    rows = _stratified_sample(rows, args.sample_per_category, args.sample_seed)
    print(f"publish sample: {len(rows)} records for scenario {scenario}")

    state_db = Path(args.state_db).expanduser()
    loader = FusekiGraphStoreLoader(args.gsp, user=args.user, password=args.password,
                                    timeout=args.timeout)
    client = FusekiSparqlClient(args.sparql, user=args.user, password=args.password,
                                timeout=args.timeout)
    results: list[dict] = []
    tdb_before = _tdb_bytes(args.container)
    with CoreStateStore(state_db) as store:
        owners = _seed_owner_state(store, loader, client)
        run_id = store.start_run("debates", "incremental_refresh", is_complete=False,
                                 parameters={"source": "assessment-sample",
                                             "scenario": scenario})
        started = time.perf_counter()
        for index, row in enumerate(rows, start=1):
            source = load_main_xml(raw_root, acquisition[row["url"]]["source_sha256"])
            entry = {"url": row["url"], "category": row["category"],
                     "date": row["date"], "source_bytes": row["bytes"]}
            t0 = time.perf_counter()
            try:
                outcome = run_debate_batch(
                    [source], store=store, run_id=run_id, publish=True,
                    loader=loader, client=client)[0]
                entry.update(status=outcome.status, triples=outcome.triples,
                             graph_iri=outcome.graph_iri)
            except Exception as error:  # noqa: BLE001 - recorded for review
                entry.update(status="error", error=f"{type(error).__name__}: {error}")
            entry["publish_seconds"] = time.perf_counter() - t0
            results.append(entry)
            if index % 50 == 0:
                print(f"publish {index}/{len(rows)}", flush=True)
        store.finish_run(run_id, success=True)
        tdb_after = _tdb_bytes(args.container)
        state_bytes = state_db.stat().st_size if state_db.exists() else 0
        db_bytes = _db_bytes(state_db)

    _write(out / f"publish_{tag}.json", {
        "scenario": scenario,
        "sample_records": len(results),
        "owner_graphs": list(owners),
        "wall_seconds": time.perf_counter() - started,
        "publish_seconds_total": sum(r.get("publish_seconds", 0) for r in results),
        "triples_total": sum(r.get("triples", 0) for r in results if r["status"] in {"new", "changed", "skipped"}),
        "tdb_before": tdb_before, "tdb_after": tdb_after,
        "tdb_marginal": tdb_after - tdb_before,
        "state_db_bytes": state_bytes, "state_db_total_bytes": db_bytes,
        "results": results,
    })
    print(json.dumps({
        "scenario": scenario, "sample_records": len(results),
        "publish_seconds_total": sum(r.get("publish_seconds", 0) for r in results),
        "triples_total": sum(r.get("triples", 0) for r in results),
        "tdb_marginal": tdb_after - tdb_before,
        "state_db_total_bytes": db_bytes,
    }, indent=1))
    return 0


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    return ordered[min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))]


def _decile_estimate(sample: list[dict], sizes: list[int], bins: int = 8) -> dict:
    """Size-decile post-stratified extrapolation from a size-stratified sample."""
    boundaries = [_percentile(sizes, index / bins) for index in range(1, bins)]
    totals = {"source_bytes": 0, "triples": 0.0, "nquads_bytes": 0.0,
              "reference_report_bytes": 0.0, "raw_meta_bytes": 0.0,
              "seconds": 0.0, "records": 0}
    detail = []
    for index in range(bins):
        low = 0 if index == 0 else boundaries[index - 1] + 1
        high = boundaries[index] if index < bins - 1 else None
        rows = [r for r in sample if r["source_bytes"] >= low
                and (high is None or r["source_bytes"] <= high)]
        in_bin = [s for s in sizes if s >= low and (high is None or s <= high)]
        if not rows or not in_bin:
            detail.append({"low": low, "high": high, "corpus_files": len(in_bin),
                           "sample_files": len(rows), "rates": None})
            continue
        # Median per-byte rates make the estimate robust to within-bin outliers.
        def rate(key):
            return statistics.median(r[key] / r["source_bytes"] for r in rows)
        rates = {"triples_per_byte": rate("triples"),
                 "nquads_bytes_per_byte": rate("nquads_bytes"),
                 "reference_report_bytes_per_byte": rate("reference_report_bytes"),
                 "raw_meta_bytes_per_byte": rate("raw_meta_bytes"),
                 "seconds_per_byte": rate("tranche4_seconds")}
        bin_bytes = sum(in_bin)
        totals["source_bytes"] += bin_bytes
        totals["records"] += len(in_bin)
        totals["triples"] += bin_bytes * rates["triples_per_byte"]
        totals["nquads_bytes"] += bin_bytes * rates["nquads_bytes_per_byte"]
        totals["reference_report_bytes"] += bin_bytes * rates["reference_report_bytes_per_byte"]
        totals["raw_meta_bytes"] += bin_bytes * rates["raw_meta_bytes_per_byte"]
        totals["seconds"] += bin_bytes * rates["seconds_per_byte"]
        detail.append({"low": low, "high": high, "corpus_files": len(in_bin),
                       "sample_files": len(rows), "corpus_bytes": bin_bytes,
                       "rates": rates})
    return {"totals": totals, "bins": detail}


def command_analyze(args) -> int:
    out = Path(args.out)
    manifest = _read(out / "scenario_manifest.json")
    acquisition = _read(out / "acquisition.json", [])
    scan = _read(out / f"{getattr(args, 'scan_name', 'scan')}.json", [])
    ok = [r for r in scan if r["status"] == "ok"]
    failures = [r for r in scan if r["status"] != "ok"]
    failed_urls = {r["url"] for r in failures}
    acq = {r["url"]: r for r in acquisition}
    acquisition_seconds = sum(r.get("wall_seconds", 0) for r in acquisition
                              if r.get("status") == "ok")

    scenarios = {
        "A": manifest["scenario_a"],
        "written": manifest["scenario_b_written"],
        "B": manifest["scenario_a"] + manifest["scenario_b_written"],
    }

    # Quarantine: records dated before the era cutoff are scanned exactly (the
    # stratified scan always includes them); post-cutoff records are estimated
    # from the uniform random sample.
    cutoff = f"{getattr(args, 'era_cutoff', 2013)}-01-01"
    quarantine_scan = _read(out / f"{args.quarantine_scan}.json", []) if args.quarantine_scan else []
    qsample: dict[str, list[bool]] = defaultdict(list)
    for row in quarantine_scan:
        if row["date"] >= cutoff:
            qsample[row["category"]].append(row["status"] == "ok")

    def quarantine_estimate(rows: list[dict]) -> dict:
        exact = [r for r in rows if r["date"] < cutoff and r["url"] in failed_urls]
        by_category = {}
        count = len(exact)
        qbytes = sum(r["bytes"] for r in exact)
        for category in sorted({r["category"] for r in rows if r["date"] >= cutoff}):
            ge = [r for r in rows if r["category"] == category and r["date"] >= cutoff]
            outcomes = qsample.get(category, [])
            rate = (1 - sum(outcomes) / len(outcomes)) if outcomes else 0.0
            est_count = rate * len(ge)
            est_bytes = rate * sum(r["bytes"] for r in ge)
            if rate:
                by_category[category] = {
                    "rate": rate, "sample": len(outcomes),
                    "estimated_records": est_count, "estimated_bytes": est_bytes,
                }
            count += est_count
            qbytes += est_bytes
        return {"count": count, "bytes": qbytes, "by_category": by_category,
                "exact_pre_cutoff": {"count": len(exact),
                                     "bytes": sum(r["bytes"] for r in exact)}}
    report: dict = {
        "acquisition": {
            "records": sum(1 for r in acquisition if r.get("status") == "ok"),
            "bytes": sum(r.get("fetched_bytes", 0) for r in acquisition
                         if r.get("status") == "ok"),
            "wall_seconds": acquisition_seconds,
            "fetch_errors": sum(1 for r in acquisition if r.get("status") != "ok"),
        },
        "scan_sample": {
            "records": len(scan), "ok": len(ok), "failed": len(failures),
            "sample_bytes": sum(r["source_bytes"] for r in ok),
            "failures": [{"url": r["url"], "date": r["date"], "category": r["category"],
                          "source_bytes": r["source_bytes"],
                          "error": r.get("error", "")[:140]} for r in failures],
        },
        "scenarios": {},
    }
    for name, rows in scenarios.items():
        q = quarantine_estimate(rows)
        by_category: dict[str, dict] = {}
        for category in sorted({r["category"] for r in rows}):
            cat_rows = [r for r in rows if r["category"] == category]
            sizes = [r["bytes"] for r in cat_rows]
            sample = [r for r in ok if r["category"] == category]
            totals = _decile_estimate(sample, sizes)["totals"]
            # Scale RDF/runtime down by the category quarantine byte fraction:
            # quarantined records are preserved but emit no RDF.
            qbytes_cat = q["by_category"].get(category, {}).get("estimated_bytes", 0.0)
            exact_cat = sum(
                r["bytes"] for r in cat_rows
                if r["date"] < cutoff and r["url"] in failed_urls)
            quarantined_cat = qbytes_cat + exact_cat
            total_cat = sum(sizes) or 1
            live_fraction = max(0.0, (total_cat - quarantined_cat) / total_cat)
            for key in ("triples", "nquads_bytes", "reference_report_bytes",
                        "raw_meta_bytes", "seconds"):
                totals[key] *= live_fraction
            by_category[category] = totals
        source_bytes = sum(r["bytes"] for r in rows)
        report["scenarios"][name] = {
            "records": len(rows),
            "source_bytes": source_bytes,
            "quarantined_records": q["count"],
            "quarantined_bytes": q["bytes"],
            "quarantine_by_category": q["by_category"],
            "exact_pre_cutoff_quarantine": q["exact_pre_cutoff"],
            "estimated_live_records": len(rows) - q["count"],
            "raw_xml_bytes": sum(r["bytes"] for r in rows),  # exact preserved bytes
            "by_category": by_category,
            "estimated_triples": sum(v["triples"] for v in by_category.values()),
            "estimated_nquads_bytes": sum(v["nquads_bytes"] for v in by_category.values()),
            "estimated_reference_report_bytes": sum(
                v["reference_report_bytes"] for v in by_category.values()),
            "estimated_tranche4_seconds": sum(v["seconds"] for v in by_category.values()),
        }
    _write(out / "analysis.json", report)
    print(json.dumps(report, indent=1))
    return 0


def _tdb_bytes(container: str) -> int:
    import subprocess
    result = subprocess.run(
        ["docker", "exec", container, "du", "-sb",
         f"/fuseki/databases/{PUBLISH_DATASET}"],
        capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return -1
    return int(result.stdout.split()[0])


def _db_bytes(state_db: Path) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = Path(str(state_db) + suffix)
        if path.exists():
            total += path.stat().st_size
    return total


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    census = sub.add_parser("census", help="enumerate and HEAD the scoped corpus")
    census.add_argument("--out", required=True)
    census.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    census.add_argument("--written-start-year", type=int, default=DEFAULT_WRITTEN_START_YEAR)
    census.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    census.add_argument("--workers", type=int, default=8)
    census.set_defaults(func=command_census)

    acquire = sub.add_parser("acquire", help="fetch and preserve exact AKN main.xml objects")
    acquire.add_argument("--out", required=True)
    acquire.add_argument("--raw-root", required=True)
    acquire.add_argument("--workers", type=int, default=8)
    acquire.set_defaults(func=command_acquire)

    scan = sub.add_parser("scan", help="Tranche 4 transform/validate/serialize over preserved objects")
    scan.add_argument("--out", required=True)
    scan.add_argument("--raw-root", required=True)
    scan.add_argument("--scenario", default="B")
    scan.add_argument("--limit", type=int, default=0)
    scan.add_argument("--select", choices=["all", "stratified", "random"], default="all")
    scan.add_argument("--sample-per-category", type=int, default=250)
    scan.add_argument("--sample-seed", type=int, default=20261006)
    scan.add_argument("--include-before-year", type=int, default=2013)
    scan.add_argument("--tag", default="")
    scan.add_argument("--shard", type=int, default=0)
    scan.add_argument("--shards", type=int, default=1)
    scan.set_defaults(func=command_scan)

    merge = sub.add_parser("merge-scan", help="combine shard scan outputs and print the summary")
    merge.add_argument("--out", required=True)
    merge.add_argument("--tag", default="")
    merge.add_argument("--scenario", default="B")
    merge.set_defaults(func=command_merge_scan)

    publish = sub.add_parser("publish", help="Tranche 4 publication sample to disposable Fuseki")
    publish.add_argument("--out", required=True)
    publish.add_argument("--raw-root", required=True)
    publish.add_argument("--state-db", required=True)
    publish.add_argument("--gsp", required=True)
    publish.add_argument("--sparql", required=True)
    publish.add_argument("--user")
    publish.add_argument("--password")
    publish.add_argument("--container", default="oir-debates-t4")
    publish.add_argument("--timeout", type=float, default=120.0)
    publish.add_argument("--scenario", choices=["A", "B", "written"], default="A")
    publish.add_argument("--sample-per-category", type=int, default=50)
    publish.add_argument("--sample-seed", type=int, default=20261006)
    publish.set_defaults(func=command_publish)

    analyze = sub.add_parser("analyze", help="extrapolate the scenarios from sample + exact census")
    analyze.add_argument("--out", required=True)
    analyze.add_argument("--scan-name", default="scan")
    analyze.add_argument("--quarantine-scan", default="")
    analyze.add_argument("--era-cutoff", type=int, default=2013)
    analyze.set_defaults(func=command_analyze)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
