"""Measurement-only Debates corpus census and transformer cost benchmark.

This tool exists to reproduce the Phase 7 production-scope measurements.  It
never publishes RDF, never mutates the ontology, mappings, fixtures or ETL
state, and never substitutes for the normal ETL path.  It calls the committed
Debates transformer directly to measure source volume, runtime, RDF output and
working storage over the official AKN corpus.

Typical reproduction of the 2026-10-04 benchmark:

    python -m tools.debates_benchmark census --cache /tmp/oireachtasontology/census
    python -m tools.debates_benchmark head --cache /tmp/oireachtasontology/census
    python -m tools.debates_benchmark sample --cache /tmp/oireachtasontology/census
    python -m tools.debates_benchmark bench --cache /tmp/oireachtasontology/census \
        --selection strata --repeats 3
    python -m tools.debates_benchmark bench --cache /tmp/oireachtasontology/census \
        --selection random --members MEMBERS.json
    python -m tools.debates_benchmark era --cache /tmp/oireachtasontology/census \
        --start-year 2004 --end-year 2012
    python -m tools.debates_benchmark report --cache /tmp/oireachtasontology/census

Network access is required for census, head, sample and era.  The members file
is the concatenated ``/v1/members`` API output used to measure owner-link RDF
volume; it is measurement input only, not an owner-resolution implementation.
"""
from __future__ import annotations

import argparse
import calendar
import datetime as dt
import hashlib
import json
import random
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from oireachtas_etl.serialization import nquads  # noqa: E402
from oireachtas_etl.transforms.debates import (  # noqa: E402
    DebateReferenceRegistry,
    DebateTransformError,
    transform_debate,
)
from oireachtas_etl.validation.debates import validate_debates  # noqa: E402

API = "https://api.oireachtas.ie/v1"
USER_AGENT = "OireachtasOntology-debates-benchmark/1.0 (measurement-only)"
DEFAULT_START_YEAR = 1919
DEFAULT_END_YEAR = 2026
BINS = 8


def api_get(path: str, attempts: int = 5) -> dict:
    """GET an API path with bounded retries for transient failures."""
    delay = 1.0
    for attempt in range(attempts):
        request = urllib.request.Request(
            API + path, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts - 1:
                raise RuntimeError(f"API request failed: {path}") from error
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise AssertionError("unreachable")


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def head_uri(url: str, attempts: int = 4) -> dict:
    delay = 0.5
    for attempt in range(attempts):
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                length = response.headers.get("Content-Length")
                return {"url": url, "status": response.status, "bytes": int(length) if length else None}
        except urllib.error.HTTPError as error:
            if error.code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                time.sleep(delay)
                delay = min(delay * 2, 20)
                continue
            return {"url": url, "status": error.code, "bytes": None}
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts - 1:
                return {"url": url, "status": -1, "bytes": None, "error": str(error)}
            time.sleep(delay)
            delay = min(delay * 2, 20)
    raise AssertionError("unreachable")


def head_many(urls: list[str], workers: int, label: str) -> list[dict]:
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(head_uri, url): url for url in urls}
        for index, future in enumerate(futures, start=1):
            results.append(future.result())
            if index % 1000 == 0:
                print(f"HEAD {label}: {index}/{len(urls)}", flush=True)
    return results


def derive_writtens_main_uri(sample_section_uri: str | None) -> str | None:
    if not sample_section_uri or "/writtens/" not in sample_section_uri:
        return None
    return sample_section_uri.split("/writtens/", 1)[0] + "/writtens/mul@/main.xml"


def category_of(record: dict) -> str:
    return "committee" if record.get("chamber_type") == "committee" else record["house_code"]


def read_cached(cache: Path, name: str, default=None):
    path = cache / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_cached(cache: Path, name: str, value) -> None:
    (cache / name).write_text(json.dumps(value, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------
# census


def enumerate_debates(years: list[int]) -> tuple[list[dict], dict]:
    records: list[dict] = []
    year_counts: dict[str, dict] = {}
    for year in years:
        skip = 0
        collected = 0
        reported = None
        while True:
            payload = api_get(
                f"/debates?date_start={year}-01-01&date_end={year}-12-31&limit=1000&skip={skip}"
            )
            head = payload.get("head", {}).get("counts", {})
            reported = reported if reported is not None else head.get("debateCount")
            results = payload.get("results", [])
            for row in results:
                record = row.get("debateRecord", {})
                house = record.get("house", {}) or {}
                counts = record.get("counts", {}) or {}
                sections = record.get("debateSections", []) or []
                records.append(
                    {
                        "date": record.get("date") or row.get("contextDate"),
                        "debate_type": record.get("debateType"),
                        "chamber_type": house.get("chamberType"),
                        "house_code": house.get("houseCode"),
                        "committee_code": house.get("committeeCode"),
                        "house_no": house.get("houseNo"),
                        "work_uri": record.get("uri"),
                        "xml_uri": ((record.get("formats") or {}).get("xml") or {}).get("uri"),
                        "last_updated": record.get("lastUpdated"),
                        "bill_count": counts.get("billCount"),
                        "bill_sections": sum(
                            1 for section in sections
                            if (section.get("debateSection") or {}).get("bill") is not None
                        ),
                        "bill_stage_sections": sum(
                            1 for section in sections
                            if ((section.get("debateSection") or {}).get("bill") or {})
                            .get("event", {}).get("isBillStage")
                        ),
                    }
                )
            collected += len(results)
            if len(results) < 1000:
                break
            skip += 1000
        year_counts[str(year)] = {"reported": reported, "collected": collected}
        print(f"debates {year}: reported={reported} collected={collected}", flush=True)
    return records, year_counts


def _collect_question_window(documents: dict, start: str, end: str) -> bool:
    """Return True when the window hit the API's 10,000-row cap."""
    skip = 0
    while True:
        payload = api_get(
            f"/questions?date_start={start}&date_end={end}&qtype=written&limit=1000&skip={skip}"
        )
        results = payload.get("results", [])
        for row in results:
            question = row.get("question", {})
            if question.get("questionType") != "written":
                continue
            house = question.get("house", {}) or {}
            section = question.get("debateSection", {}) or {}
            formats = section.get("formats")
            section_xml = formats.get("xml", {}).get("uri") if isinstance(formats, dict) else None
            key = (
                question.get("date"),
                house.get("chamberType"),
                house.get("houseCode"),
                house.get("committeeCode") or "",
            )
            entry = documents.setdefault(
                key,
                {
                    "date": question.get("date"),
                    "chamber_type": house.get("chamberType"),
                    "house_code": house.get("houseCode"),
                    "committee_code": house.get("committeeCode") or "",
                    "question_count": 0,
                    "sections": [],
                },
            )
            entry["question_count"] += 1
            if section.get("uri") and all(
                item["uri"] != section["uri"] for item in entry["sections"]
            ):
                entry["sections"].append({"uri": section["uri"], "xml": section_xml})
        if len(results) < 1000:
            return False
        skip += 1000
        if skip >= 10000:
            return True


def enumerate_written_documents(start_year: int, end_year: int) -> tuple[list[dict], dict]:
    """Enumerate written-answer documents month by month (API cap is 10,000)."""
    documents: dict[tuple, dict] = {}
    year_counts: dict[str, dict] = {}

    def collect(start: str, end: str) -> None:
        if _collect_question_window(documents, start, end):
            first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
            if first == last:
                raise RuntimeError(f"single-day question window truncated: {start}")
            midpoint = first + (last - first) // 2
            collect(start, midpoint.isoformat())
            collect((midpoint + dt.timedelta(days=1)).isoformat(), end)

    for year in range(start_year, end_year + 1):
        before = sum(entry["question_count"] for entry in documents.values())
        for month in range(1, 13):
            last_day = calendar.monthrange(year, month)[1]
            collect(f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last_day:02d}")
        written = sum(entry["question_count"] for entry in documents.values()) - before
        year_counts[str(year)] = {"written": written}
        print(f"questions {year}: written={written}", flush=True)
    return list(documents.values()), year_counts


def command_census(args) -> int:
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    years = list(range(args.start_year, args.end_year + 1))
    records, counts = enumerate_debates(years)
    write_cached(cache, "debates.json", records)
    write_cached(cache, "debates_year_counts.json", counts)
    documents, question_counts = enumerate_written_documents(args.start_year, args.end_year)
    write_cached(cache, "written_documents.json", documents)
    write_cached(cache, "questions_year_counts.json", question_counts)
    return 0


# --------------------------------------------------------------------------
# head measurement


def command_head(args) -> int:
    cache = Path(args.cache)
    records = read_cached(cache, "debates.json", [])
    debate_urls = sorted({record["xml_uri"] for record in records if record.get("xml_uri")})
    write_cached(cache, "head_debates.json", head_many(debate_urls, args.workers, "debates"))

    documents = read_cached(cache, "written_documents.json", [])
    written_urls = sorted(
        {
            uri
            for doc in documents
            if (uri := derive_writtens_main_uri((doc.get("sections") or [{}])[0].get("uri")))
        }
    )
    write_cached(cache, "written_urls.json", written_urls)
    write_cached(cache, "head_writtens.json", head_many(written_urls, args.workers, "writtens"))
    return 0


# --------------------------------------------------------------------------
# sampling


def command_sample(args) -> int:
    cache = Path(args.cache)
    corpus = Path(args.corpus) if args.corpus else cache / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    records = read_cached(cache, "debates.json", [])
    head = {row["url"]: row.get("bytes") for row in read_cached(cache, "head_debates.json", []) or []}
    head_written = {
        row["url"]: row.get("bytes") for row in read_cached(cache, "head_writtens.json", []) or []
    }
    entries: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for record in records:
        url = record.get("xml_uri")
        size = head.get(url)
        if not size or url in seen:
            continue
        seen.add(url)
        category = category_of(record)
        entries[category].append({"url": url, "bytes": size, "date": record["date"], "category": category})
    entries["written"] = [
        {"url": url, "bytes": size, "date": url.split("/writtens/")[0].split("/")[-1], "category": "written"}
        for url, size in head_written.items()
        if size
    ]

    def percentile(values, fraction):
        values = sorted(values)
        return values[min(len(values) - 1, max(0, round(fraction * (len(values) - 1))))]

    selected: dict[str, dict] = {}
    for category, rows in entries.items():
        rows = sorted(rows, key=lambda row: (row["bytes"], row["url"]))
        sizes = [row["bytes"] for row in rows]
        for fraction in (0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 0.99, 1.0):
            target = percentile(sizes, fraction)
            candidate = min(rows, key=lambda row: abs(row["bytes"] - target))
            selected.setdefault(candidate["url"], {**candidate, "selection": "strata"})
        rng = random.Random(args.seed)
        for row in rng.sample(rows, min(args.random_per_category, len(rows))):
            selected.setdefault(row["url"], {**row, "selection": "random"})

    manifest = []
    for index, (url, row) in enumerate(
        sorted(selected.items(), key=lambda item: (item[1]["category"], item[1]["bytes"]))
    ):
        target = corpus / f"{row['category']}_{index:03d}_{row['bytes']}B.xml"
        if not target.exists() or target.stat().st_size != row["bytes"]:
            target.write_bytes(fetch_bytes(url))
        manifest.append({**row, "local": str(target)})
    write_cached(cache, "benchmark_manifest.json", manifest)
    print(f"manifest entries: {len(manifest)}")
    return 0


# --------------------------------------------------------------------------
# transformer benchmark


def build_member_registry(members_json: dict) -> DebateReferenceRegistry:
    members = {}
    for row in members_json.get("results", []):
        member = row.get("member", {})
        if member.get("memberCode") and member.get("uri"):
            members[f"/ie/oireachtas/member/id/{member['memberCode']}"] = member["uri"]
    return DebateReferenceRegistry(
        members_by_tlc_href=members, version="members-api-registry-measurement-only"
    )


@dataclass
class Timing:
    transform: float
    validate: float
    serialize: float


def measure_record(source: bytes, resolver: ResolverChoice) -> dict:
    timings: list[Timing] = []
    rdf = None
    result = None
    try:
        for _ in range(max(1, resolver.repeats)):
            start = time.perf_counter()
            result = transform_debate(source, resolver=resolver.registry)
            transform_elapsed = time.perf_counter() - start
            validate_start = time.perf_counter()
            validate_debates(result)
            validate_elapsed = time.perf_counter() - validate_start
            serialize_start = time.perf_counter()
            rdf = nquads(result.graph, result.graph_iri)
            timings.append(Timing(transform_elapsed, validate_elapsed, time.perf_counter() - serialize_start))
    except DebateTransformError as error:
        return {
            "status": "fail-closed",
            "error": str(error),
            "source_sha256": error.reference_report.get("source_sha256"),
            "diagnostics": error.reference_report.get("diagnostics", [])[-3:],
        }
    except Exception as error:  # noqa: BLE001 - recorded for review
        return {"status": "unexpected-error", "error": f"{type(error).__name__}: {error}"}
    return {
        "status": "ok",
        "source_sha256": result.source_sha256,
        "transform_seconds_min": min(t.transform for t in timings),
        "validate_seconds_min": min(t.validate for t in timings),
        "serialization_seconds_min": min(t.serialize for t in timings),
        "rdf_triples": len(result.graph),
        "rdf_nquads_bytes": len(rdf.encode("utf-8")),
        "reference_report_bytes": len(result.reference_report_json),
        "reference_outcomes": len(result.reference_report.get("reference_outcomes", [])),
        "resource_identities": len(result.reference_report.get("resource_identities", [])),
        "work_iri": result.work_iri,
        "graph_iri": result.graph_iri,
    }


@dataclass
class ResolverChoice:
    registry: DebateReferenceRegistry | None
    repeats: int
    label: str


def command_bench(args) -> int:
    cache = Path(args.cache)
    manifest = read_cached(cache, "benchmark_manifest.json", [])
    rows = [row for row in manifest if row.get("selection") == args.selection]
    if args.members:
        members_json = json.loads(Path(args.members).read_text(encoding="utf-8"))
        choice = ResolverChoice(build_member_registry(members_json), args.repeats, "members-registry")
    else:
        choice = ResolverChoice(None, args.repeats, "resolver-none")
    results = []
    wall_start = time.perf_counter()
    for row in rows:
        result = measure_record(Path(row["local"]).read_bytes(), choice)
        result.update(
            {
                "file": Path(row["local"]).name,
                "category": row["category"],
                "date": row["date"],
                "source_bytes": Path(row["local"]).stat().st_size,
                "resolver": choice.label,
            }
        )
        results.append(result)
        status = result["status"]
        print(f"{result['file']}: {status}", flush=True)
    output = {
        "selection": args.selection,
        "resolver": choice.label,
        "transformer_sha256": hashlib.sha256(
            Path(__import__("oireachtas_etl.transforms.debates", fromlist=["x"]).__file__).read_bytes()
        ).hexdigest(),
        "rows": results,
        "wall_seconds": time.perf_counter() - wall_start,
    }
    target = Path(args.output) if args.output else cache / f"bench_{args.selection}_{choice.label}.json"
    target.write_text(json.dumps(output, indent=1), encoding="utf-8")
    return 0


def command_era(args) -> int:
    """Fetch, transform and validate every debate record in a year range."""
    cache = Path(args.cache)
    records = read_cached(cache, "debates.json", [])
    targets = [
        record
        for record in records
        if f"{args.start_year}-01-01" <= (record.get("date") or "") <= f"{args.end_year}-12-31"
        and record.get("xml_uri")
    ]
    dedup: dict[str, dict] = {}
    for record in targets:
        dedup.setdefault(record["xml_uri"], record)
    urls = sorted(dedup)
    if args.shards > 1:
        urls = [url for index, url in enumerate(urls) if index % args.shards == args.shard]
    print(
        f"era {args.start_year}-{args.end_year}: {len(urls)} records "
        f"(shard {args.shard}/{args.shards})"
    )

    rows: list[dict] = []

    def handle(url: str, future) -> None:
        record = dedup[url]
        entry = {"url": url, "category": category_of(record), "date": record["date"]}
        try:
            data = future.result()
        except Exception as error:  # noqa: BLE001
            entry.update(status="fetch-error", error=str(error))
            rows.append(entry)
            return
        entry["source_bytes"] = len(data)
        entry.update(measure_record(data, ResolverChoice(None, 1, "resolver-none")))
        rows.append(entry)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        iterator = iter(urls)
        pending = {}
        for url in iterator:
            pending[pool.submit(fetch_bytes, url)] = url
            if len(pending) >= args.workers:
                break
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                url = pending.pop(future)
                handle(url, future)
                next_url = next(iterator, None)
                if next_url is not None:
                    pending[pool.submit(fetch_bytes, next_url)] = next_url
                if len(rows) % 100 == 0:
                    print(f"era processed {len(rows)}/{len(urls)}", flush=True)
    suffix = f"_shard{args.shard}" if args.shards > 1 else ""
    write_cached(cache, f"era_scan_{args.start_year}_{args.end_year}{suffix}.json", rows)
    print(Counter(row["status"] for row in rows))
    return 0


def command_fragments(args) -> int:
    """Sample section-fragmented written-answer documents without a main.xml."""
    cache = Path(args.cache)
    documents = read_cached(cache, "written_documents.json", [])
    head_written = {
        row["url"]: row.get("status") for row in read_cached(cache, "head_writtens.json", []) or []
    }

    def main_status(date: str):
        url = f"https://data.oireachtas.ie/akn/ie/debateRecord/dail/{date}/writtens/mul@/main.xml"
        return head_written.get(url)

    fragmented: dict[str, dict] = {}
    for document in documents:
        if main_status(document["date"]) != 200:
            for section in document.get("sections", []):
                if section.get("xml"):
                    fragmented.setdefault(section["xml"], {"xml": section["xml"], "date": document["date"]})
    by_month: dict[str, list[dict]] = defaultdict(list)
    for row in fragmented.values():
        by_month[(row["date"] or "")[:7]].append(row)
    rng = random.Random(args.seed)
    sample: dict[str, dict] = {}
    for month, rows in sorted(by_month.items()):
        rows = sorted(rows, key=lambda row: row["xml"])
        step = max(1, len(rows) // args.per_month)
        for row in rows[::step][: args.per_month]:
            sample.setdefault(row["xml"], row)
    section_urls = sorted(sample)
    results = head_many(section_urls, args.workers, "fragment-sample")
    sizes = [row["bytes"] for row in results if row.get("status") == 200 and row.get("bytes")]
    means = [statistics.mean(rng.choices(sizes, k=len(sizes))) for _ in range(5000)]
    means.sort()
    output = {
        "fragmented_documents": len({document["date"] for document in documents if main_status(document["date"]) != 200}),
        "section_count": len(fragmented),
        "sampled": len(sizes),
        "mean_bytes": statistics.mean(sizes),
        "median_bytes": statistics.median(sizes),
        "estimated_total_bytes": len(fragmented) * statistics.mean(sizes),
        "bootstrap_95_low": len(fragmented) * means[int(0.025 * len(means))],
        "bootstrap_95_high": len(fragmented) * means[int(0.975 * len(means))],
    }
    write_cached(cache, "fragment_sample.json", {**output, "results": results})
    print(json.dumps(output, indent=1))
    return 0


# --------------------------------------------------------------------------
# reporting


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    return ordered[min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))]


def size_stats(values: list[int]) -> dict:
    return {
        "files": len(values),
        "bytes_total": sum(values),
        "bytes_mean": sum(values) / len(values) if values else 0,
        "bytes_min": min(values) if values else 0,
        "bytes_p25": percentile(values, 0.25),
        "bytes_median": percentile(values, 0.50),
        "bytes_p75": percentile(values, 0.75),
        "bytes_p90": percentile(values, 0.90),
        "bytes_p99": percentile(values, 0.99),
        "bytes_max": max(values) if values else 0,
    }


def decile_rates(sweep_rows: list[dict], corpus_sizes: list[int]) -> list[dict]:
    boundaries = [percentile(corpus_sizes, index / BINS) for index in range(1, BINS)]
    samples = [row for row in sweep_rows if row.get("status") == "ok"]
    bins = []
    for index in range(BINS):
        low = 0 if index == 0 else boundaries[index - 1] + 1
        high = boundaries[index] if index < BINS - 1 else None
        rows = [
            row
            for row in samples
            if row["source_bytes"] >= low and (high is None or row["source_bytes"] <= high)
        ]
        corpus_in_bin = [size for size in corpus_sizes if size >= low and (high is None or size <= high)]
        if not rows:
            bins.append({"low": low, "high": high, "corpus_files": len(corpus_in_bin), "rates": None})
            continue
        bins.append(
            {
                "low": low,
                "high": high,
                "sample_files": len(rows),
                "corpus_files": len(corpus_in_bin),
                "corpus_bytes": sum(corpus_in_bin),
                "rates": {
                    "seconds_per_byte": statistics.median(row["transform_seconds_min"] / row["source_bytes"] for row in rows),
                    "triples_per_byte": statistics.median(row["rdf_triples"] / row["source_bytes"] for row in rows),
                    "nquads_bytes_per_byte": statistics.median(row["rdf_nquads_bytes"] / row["source_bytes"] for row in rows),
                },
            }
        )
    return bins


def extrapolate(bench_rows: list[dict], sizes_by_category: dict[str, list[int]]) -> dict:
    """Size-decile post-stratified extrapolation over the measured size census."""
    results = {}
    for category, sizes in sizes_by_category.items():
        rows = [row for row in bench_rows if row.get("category") == category and row.get("status") == "ok"]
        if not rows:
            continue
        bins = decile_rates(rows, sizes)
        totals = {"source_bytes": 0, "transform_seconds": 0.0, "triples": 0.0, "nquads_bytes": 0.0}
        for size in sizes:
            for entry in bins:
                if size < entry["low"]:
                    continue
                if entry["high"] is not None and size > entry["high"]:
                    continue
                if entry["rates"]:
                    totals["source_bytes"] += size
                    totals["transform_seconds"] += size * entry["rates"]["seconds_per_byte"]
                    totals["triples"] += size * entry["rates"]["triples_per_byte"]
                    totals["nquads_bytes"] += size * entry["rates"]["nquads_bytes_per_byte"]
                break
        results[category] = {"bins": bins, **totals}
    return results


def command_report(args) -> int:
    cache = Path(args.cache)
    records = read_cached(cache, "debates.json", [])
    head = {row["url"]: row.get("bytes") for row in read_cached(cache, "head_debates.json", []) or []}
    sizes_by_category: dict[str, list[int]] = defaultdict(list)
    bill_sizes: dict[str, list[int]] = defaultdict(list)
    seen: set[str] = set()
    for record in records:
        url = record.get("xml_uri")
        if url in seen or not head.get(url):
            continue
        seen.add(url)
        category = category_of(record)
        sizes_by_category[category].append(head[url])
        if (record.get("bill_count") or 0) > 0 or record.get("bill_sections"):
            bill_sizes[category].append(head[url])
    written = [
        row["bytes"] for row in (read_cached(cache, "head_writtens.json", []) or []) if row.get("bytes")
    ]
    sizes_by_category["written"] = written
    report: dict = {
        "census": {category: size_stats(sizes) for category, sizes in sorted(sizes_by_category.items())},
        "bill_linked_debates": {
            category: size_stats(sizes) for category, sizes in sorted(bill_sizes.items())
        },
    }
    random_bench = read_cached(cache, "bench_random_resolver-none.json") or read_cached(
        cache, "bench_strata_resolver-none.json"
    )
    if random_bench:
        report["extrapolated_resolver_none"] = extrapolate(random_bench["rows"], sizes_by_category)
        report["extrapolated_bill_linked_resolver_none"] = extrapolate(random_bench["rows"], bill_sizes)
    members_bench = read_cached(cache, "bench_random_members-registry.json") or read_cached(
        cache, "bench_strata_members-registry.json"
    )
    if members_bench:
        report["extrapolated_members_registry"] = extrapolate(members_bench["rows"], sizes_by_category)
        report["extrapolated_bill_linked_members_registry"] = extrapolate(
            members_bench["rows"], bill_sizes
        )
    for bench_name in (
        "bench_strata_resolver-none",
        "bench_strata_members-registry",
        "bench_random_resolver-none",
        "bench_random_members-registry",
    ):
        payload = read_cached(cache, f"{bench_name}.json")
        if payload:
            report.setdefault("benchmarks", {})[bench_name] = {
                "wall_seconds": payload["wall_seconds"],
                "statuses": dict(Counter(row["status"] for row in payload["rows"])),
            }
    print(json.dumps(report, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    census = sub.add_parser("census", help="enumerate /v1/debates and written-answer documents")
    census.add_argument("--cache", required=True)
    census.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    census.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    census.set_defaults(func=command_census)

    head = sub.add_parser("head", help="HEAD every known AKN main.xml")
    head.add_argument("--cache", required=True)
    head.add_argument("--workers", type=int, default=8)
    head.set_defaults(func=command_head)

    sample = sub.add_parser("sample", help="select stratified/random files and download them")
    sample.add_argument("--cache", required=True)
    sample.add_argument("--corpus")
    sample.add_argument("--random-per-category", type=int, default=60)
    sample.add_argument("--seed", type=int, default=20261004)
    sample.set_defaults(func=command_sample)

    bench = sub.add_parser("bench", help="measure transform/validate/serialize per selected file")
    bench.add_argument("--cache", required=True)
    bench.add_argument("--selection", choices=["strata", "random"], default="strata")
    bench.add_argument("--members")
    bench.add_argument("--repeats", type=int, default=3)
    bench.add_argument("--output")
    bench.set_defaults(func=command_bench)

    era = sub.add_parser("era", help="exact fetch/transform scan over a year range")
    era.add_argument("--cache", required=True)
    era.add_argument("--start-year", type=int, required=True)
    era.add_argument("--end-year", type=int, required=True)
    era.add_argument("--workers", type=int, default=12)
    era.add_argument("--shard", type=int, default=0)
    era.add_argument("--shards", type=int, default=1)
    era.set_defaults(func=command_era)

    report = sub.add_parser("report", help="print census sizes and benchmark status counts")
    report.add_argument("--cache", required=True)
    report.set_defaults(func=command_report)

    fragments = sub.add_parser(
        "fragments", help="sample section-fragmented written-answer files without a main.xml"
    )
    fragments.add_argument("--cache", required=True)
    fragments.add_argument("--per-month", type=int, default=20)
    fragments.add_argument("--workers", type=int, default=8)
    fragments.add_argument("--seed", type=int, default=20261004)
    fragments.set_defaults(func=command_fragments)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
