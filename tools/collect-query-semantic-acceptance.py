#!/usr/bin/env python3
"""Collect the first rendered /ask response for each frozen semantic case.

This utility has no query-service implementation imports. It refuses to run
unless the caller explicitly enables /ask and acknowledges authorization.
Every request is marked before dispatch, is issued once, and is never retried.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "docs/reports/query-service/semantic-dispatch-acceptance"
EXPECTED_AGGREGATE_SHA256 = "42309c5da7903f0d5a20cf0dca347eae8d89ac47bdb6f1eab7a1f270e21d60cd"
EXPECTED_FREEZE_JSON_SHA256 = "10d27f536c496fefbba32e701e39bfee60fb32df6942c70b207ace9fa65c74f0"
EXPECTED_FILE_SHA256 = {
    "holdout.json": "2059007220719da7413ecf45a8576554761ba73bee07648c790d155e624a6235",
    "oracle-context.json.gz": "2c3e9dcdbd1b20e95d02d70e2fb680b63d213b3e7ca1b0fbd76933292d3da7e6",
    "methodology.md": "c34144774fb729e772f399f282c0f185657cc5412ca7b47f8f4893ef107201c9",
}
EXPECTED_QUESTION_COUNT = 44
EXPECTED_FACTUAL_COUNT = 38
EXPECTED_REFERENCE_DATE = "2026-11-06"
MODE = "phase2"
HTTP_TIMEOUT_SECONDS = 180
SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_exclusive(path: Path, data: bytes) -> None:
    """Create a file exactly once and flush it before returning."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json_exclusive(path: Path, value: object) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_exclusive(path, data)


def verify_freeze() -> tuple[dict, dict, dict[str, str]]:
    """Fail closed unless the original frozen 44-case set is byte-identical."""
    freeze_path = ARTIFACT_DIR / "freeze.json"
    freeze_bytes = freeze_path.read_bytes()
    freeze_hash = sha256_bytes(freeze_bytes)
    if freeze_hash != EXPECTED_FREEZE_JSON_SHA256:
        raise ValueError("freeze.json differs from the pinned frozen metadata")

    freeze = json.loads(freeze_bytes)
    if freeze.get("aggregateFreezeSha256") != EXPECTED_AGGREGATE_SHA256:
        raise ValueError("freeze metadata has an unexpected aggregate digest")
    if freeze.get("questionCount") != EXPECTED_QUESTION_COUNT:
        raise ValueError("unexpected frozen question count")
    if freeze.get("factualCount") != EXPECTED_FACTUAL_COUNT:
        raise ValueError("unexpected frozen factual denominator")
    if freeze.get("referenceDate") != EXPECTED_REFERENCE_DATE:
        raise ValueError("unexpected frozen reference date")
    if freeze.get("sha256") != EXPECTED_FILE_SHA256:
        raise ValueError("freeze metadata artifact hashes differ from the pinned set")

    aggregate = hashlib.sha256()
    observed: dict[str, str] = {}
    for name in ("holdout.json", "oracle-context.json.gz", "methodology.md"):
        data = (ARTIFACT_DIR / name).read_bytes()
        observed[name] = sha256_bytes(data)
        if observed[name] != EXPECTED_FILE_SHA256[name]:
            raise ValueError(f"frozen artifact hash mismatch: {name}")
        aggregate.update(name.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(data)
        aggregate.update(b"\0")
    if aggregate.hexdigest() != EXPECTED_AGGREGATE_SHA256:
        raise ValueError("aggregate freeze digest mismatch")

    # The compressed oracle is checked byte-for-byte, but deliberately not read
    # or interpreted by the collector.
    holdout = json.loads((ARTIFACT_DIR / "holdout.json").read_text(encoding="utf-8"))
    cases = holdout.get("questions")
    if not isinstance(cases, list) or len(cases) != EXPECTED_QUESTION_COUNT:
        raise ValueError("holdout does not contain the pinned 44 cases")
    if holdout.get("questionCount") != EXPECTED_QUESTION_COUNT:
        raise ValueError("holdout questionCount metadata mismatch")
    if holdout.get("factualCount") != EXPECTED_FACTUAL_COUNT:
        raise ValueError("holdout factualCount metadata mismatch")
    if holdout.get("referenceDate") != EXPECTED_REFERENCE_DATE:
        raise ValueError("holdout referenceDate metadata mismatch")

    ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or not SAFE_ID.fullmatch(str(case.get("id", ""))):
            raise ValueError("holdout contains a malformed case record")
        if not isinstance(case.get("question"), str) or not isinstance(case.get("expected"), dict):
            raise ValueError("holdout contains a malformed case record")
        ids.append(case["id"])
    if len(set(ids)) != EXPECTED_QUESTION_COUNT:
        raise ValueError("holdout case identifiers are not unique")
    return freeze, holdout, observed


class RenderedPage(HTMLParser):
    """Small read-only HTML capture: sections, tables, links, outcome, and pre."""

    EXCLUDED_SECTION_IDS = {"query-processing", "answer-feedback"}

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.sections: list[str] = []
        self.tables: list[list[list[dict]]] = []
        self.pres: list[str] = []
        self.outcome: str | None = None
        self._section_stack: list[dict] = []
        self._table_stack: list[dict] = []
        self._cell: dict | None = None
        self._pre: list[str] | None = None
        self.feed(text)
        self.close()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {key: value or "" for key, value in attrs}
        if a.get("data-outcome"):
            self.outcome = a["data-outcome"]
        if tag == "section":
            classes = a.get("class", "").split()
            included = (
                a.get("id") not in self.EXCLUDED_SECTION_IDS
                and "system-status" not in classes
                and a.get("aria-label") != "Optional evidence collection"
            )
            self._section_stack.append({"tag": tag, "include": included, "chunks": []})
        elif tag == "p" and a.get("role") == "alert":
            self._section_stack.append({"tag": tag, "include": True, "chunks": []})
        if tag == "pre":
            self._pre = []
        if tag == "table":
            self._table_stack.append({"rows": [], "row": None})
        elif tag == "tr" and self._table_stack:
            self._table_stack[-1]["row"] = []
        elif tag in ("td", "th") and self._table_stack:
            self._cell = {"tag": tag, "attrs": a, "chunks": [], "links": []}
        elif tag == "a" and self._cell is not None and a.get("href"):
            self._cell["links"].append(a["href"])

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["chunks"].append(data)
        if self._pre is not None:
            self._pre.append(data)
        for section in self._section_stack:
            section["chunks"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._table_stack:
            cell = self._cell
            self._cell = None
            row = self._table_stack[-1].get("row")
            if row is not None:
                row.append({
                    "tag": cell["tag"],
                    "text": " ".join("".join(cell["chunks"]).split()),
                    "links": cell["links"],
                })
        elif tag == "tr" and self._table_stack:
            state = self._table_stack[-1]
            if state.get("row") is not None:
                state["rows"].append(state["row"])
                state["row"] = None
        elif tag == "table" and self._table_stack:
            state = self._table_stack.pop()
            self.tables.append(state["rows"])
        elif tag == "pre" and self._pre is not None:
            self.pres.append(" ".join("".join(self._pre).split()))
            self._pre = None
        elif tag in ("section", "p") and self._section_stack and self._section_stack[-1]["tag"] == tag:
            section = self._section_stack.pop()
            if section["include"]:
                text = " ".join("".join(section["chunks"]).split())
                if text:
                    self.sections.append(text)

    def result(self) -> dict:
        return {
            "outcome": self.outcome,
            "sections": self.sections,
            "tables": self.tables,
            "diagnostics": self.pres,
        }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward a question POST to a redirected host or route."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def endpoint_for(base_url: str, ask_path: str) -> str:
    base = urllib.parse.urlsplit(base_url)
    if base.scheme not in {"http", "https"} or not base.netloc:
        raise ValueError("base URL must be an absolute HTTP(S) URL")
    if base.username or base.password or base.query or base.fragment:
        raise ValueError("base URL must not include credentials, query, or fragment")
    route = urllib.parse.urlsplit(ask_path)
    if route.scheme or route.netloc or route.query or route.fragment:
        raise ValueError("ask path must be a path only, without query or fragment")
    path = ask_path if ask_path.startswith("/") else "/" + ask_path
    return urllib.parse.urlunsplit((base.scheme, base.netloc, base.path.rstrip("/") + path, "", ""))


def collect_one(case: dict, endpoint: str, run_dir: Path, opener) -> dict:
    case_id = case["id"]
    attempt = {
        "case_id": case_id,
        "attempt": 1,
        "marked_at_utc": utc_now(),
        "question_sha256": sha256_bytes(case["question"].encode("utf-8")),
        "policy": "one request only; no retries",
    }
    write_json_exclusive(run_dir / "attempts" / f"{case_id}.json", attempt)

    started = utc_now()
    form = urllib.parse.urlencode({"question": case["question"], "mode": MODE}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "text/html"},
        method="POST",
    )
    body: bytes | None = None
    status: int | None = None
    content_type: str | None = None
    transport_error: str | None = None
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            status = response.status
            content_type = response.headers.get("Content-Type")
            body = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        content_type = exc.headers.get("Content-Type") if exc.headers else None
        body = exc.read()
    except Exception as exc:  # first transport failure is retained; never retried
        transport_error = type(exc).__name__

    raw_path: str | None = None
    parsed = {"outcome": None, "sections": [], "tables": [], "diagnostics": []}
    response_hash: str | None = None
    if body is not None:
        raw_path = f"raw/{case_id}.html"
        write_exclusive(run_dir / raw_path, body)
        response_hash = sha256_bytes(body)
        parsed = RenderedPage(body.decode("utf-8", errors="replace")).result()

    record = {
        "case_id": case_id,
        "question": case["question"],
        "class": case.get("class"),
        "capability_group": case.get("capabilityGroup"),
        "request": {"method": "POST", "mode": MODE, "endpoint": endpoint},
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "http_status": status,
        "content_type": content_type,
        "transport_error_type": transport_error,
        "response_sha256": response_hash,
        "raw_html_path": raw_path,
        "rendered": parsed,
    }
    write_json_exclusive(run_dir / "results" / f"{case_id}.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Base URL of the rendered query service, e.g. http://localhost:8000")
    parser.add_argument("--out", required=True, type=Path, help="New, non-existing run directory; results are write-once")
    parser.add_argument("--ask-path", default="/ask", help="Rendered ask route (default: /ask)")
    parser.add_argument("--max-workers", type=int, choices=(1, 2), default=1, help="At most two concurrent first requests")
    parser.add_argument("--service-revision", help="Optional revision supplied by the authorized evaluator; never probed")
    parser.add_argument("--execute-ask", action="store_true", help="Enable network requests (must be separately authorized)")
    parser.add_argument("--acknowledge-authorization", action="store_true", help="Confirm a later explicit authorization to execute /ask")
    args = parser.parse_args()

    if not (args.execute_ask and args.acknowledge_authorization):
        parser.error("no request is made unless both --execute-ask and --acknowledge-authorization are supplied")

    freeze, holdout, artifact_hashes = verify_freeze()
    endpoint = endpoint_for(args.base_url, args.ask_path)
    if args.out.exists():
        raise FileExistsError(f"write-once output path already exists: {args.out}")
    if args.out.resolve().is_relative_to(ARTIFACT_DIR.resolve()):
        raise ValueError("collector output must be outside the frozen artifact directory")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=False)
    for name in ("attempts", "raw", "results"):
        (args.out / name).mkdir()

    cases = holdout["questions"]
    manifest = {
        "format_version": 1,
        "run_id": str(uuid.uuid4()),
        "created_at_utc": utc_now(),
        "frozen_aggregate_sha256": EXPECTED_AGGREGATE_SHA256,
        "freeze_json_sha256": EXPECTED_FREEZE_JSON_SHA256,
        "frozen_artifact_sha256": artifact_hashes,
        "question_count": len(cases),
        "factual_denominator": EXPECTED_FACTUAL_COUNT,
        "reference_date": EXPECTED_REFERENCE_DATE,
        "case_ids": [case["id"] for case in cases],
        "service_base_url": args.base_url,
        "ask_endpoint": endpoint,
        "mode": MODE,
        "max_workers": args.max_workers,
        "timeout_seconds": HTTP_TIMEOUT_SECONDS,
        "retry_policy": "none; one first request per frozen case",
        "redirect_policy": "disabled",
        "service_revision": args.service_revision or "unspecified_not_probed",
        "collector_script_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "ask_calls_executed": True,
        "freeze_status_at_collection": freeze.get("status"),
    }
    write_json_exclusive(args.out / "manifest.json", manifest)

    opener = urllib.request.build_opener(NoRedirect)
    records: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [pool.submit(collect_one, case, endpoint, args.out, opener) for case in cases]
        for future in futures:
            records.append(future.result())

    status_counts: dict[str, int] = {}
    for record in records:
        key = str(record["http_status"]) if record["http_status"] is not None else "transport_error"
        status_counts[key] = status_counts.get(key, 0) + 1
    completion = {
        "completed_at_utc": utc_now(),
        "attempted_case_count": len(records),
        "result_case_count": len(records),
        "http_status_counts": status_counts,
        "transport_error_count": sum(record["http_status"] is None for record in records),
        "first_results_retained": True,
        "retries": 0,
        "manifest_sha256": sha256_bytes((args.out / "manifest.json").read_bytes()),
        "files_sha256": {},
    }
    for case in cases:
        case_id = case["id"]
        for kind, rel in (
            ("attempt", f"attempts/{case_id}.json"),
            ("result", f"results/{case_id}.json"),
            ("raw_html", f"raw/{case_id}.html"),
        ):
            path = args.out / rel
            if path.is_file():
                completion["files_sha256"][f"{kind}:{case_id}"] = sha256_bytes(path.read_bytes())
    write_json_exclusive(args.out / "completion.json", completion)
    print(json.dumps({"run_dir": str(args.out), "cases": len(records), "http_status_counts": status_counts, "retries": 0}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
