#!/usr/bin/env python3
"""Read-only evaluation evidence collector; never imports the query implementation.

Use the existing service PID only to obtain its configured local query credentials.
No credentials, cookies, raw provider headers or authorization material are saved.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/reports/query-service/independent-generalisation"


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def environment(pid):
    return dict(x.split("=", 1) for x in Path(f"/proc/{pid}/environ").read_text().split("\0") if "=" in x)


def query(env, sparql):
    assert sparql.lstrip().startswith(("PREFIX", "SELECT", "ASK"))
    with httpx.Client(timeout=120, auth=(env["OIR_FUSEKI_USER"], env["OIR_FUSEKI_PASSWORD"]) if env.get("OIR_FUSEKI_USER") else None) as client:
        r = client.post(env.get("NLQ_FUSEKI_QUERY_URL", "http://localhost:3030/houses/query"), data={"query": sparql}, headers={"Accept": "application/sparql-results+json"})
        r.raise_for_status()
        return r.json()


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.stack = []
        self.sections = []
        self.tables = []
        self.pres = []
        self.outcome = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("data-outcome"):
            self.outcome = a["data-outcome"]
        if tag in ("section", "div", "p", "h2", "h3", "table", "tr", "td", "th", "pre"):
            self.stack.append([tag, a, []])

    def handle_data(self, data):
        for _, _, texts in self.stack:
            texts.append(data)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1][0] != tag:
            return
        _, attrs, texts = self.stack.pop()
        text = "".join(texts).strip()
        if tag == "pre":
            self.pres.append(text)
        if tag in ("td", "th"):
            if not hasattr(self, "cells"):
                self.cells = []
            self.cells.append(text)
        if tag == "tr":
            if not hasattr(self, "rows"):
                self.rows = []
            self.rows.append(self.cells)
            self.cells = []
        if tag == "table":
            self.tables.append(self.rows)
            self.rows = []
        if tag == "section" and attrs.get("id") not in ("query-processing", "answer-feedback") and "system-status" not in attrs.get("class", "") and attrs.get("aria-label") != "Optional evidence collection":
            self.sections.append(text)
        if tag == "p" and attrs.get("role") == "alert":
            self.sections.append(text)


def ask(case, run, url):
    start = time.monotonic()
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        r = httpx.post(url + "/ask", data={"question": case["question"], "mode": "phase2"}, timeout=180)
        page = Page(r.text)
        return {"id": case["id"], "run": run, "question": case["question"], "timestamp": timestamp,
                "seconds": round(time.monotonic() - start, 3), "http_status": r.status_code,
                "outcome": page.outcome, "rendered_answer": "\n\n".join(page.sections),
                "tables": page.tables, "diagnostics": page.pres,
                "response_sha256": hashlib.sha256(r.content).hexdigest()}
    except httpx.HTTPError as exc:
        return {"id": case["id"], "run": run, "question": case["question"], "timestamp": timestamp,
                "seconds": round(time.monotonic() - start, 3), "transport_error": str(exc)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("snapshot", "run"))
    p.add_argument("--pid", type=int)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--ids", default="")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--output", required=True)
    p.add_argument("--queries")
    args = p.parse_args()
    if args.action == "snapshot":
        env = environment(args.pid)
        queries = json.loads(Path(args.queries).read_text())
        save(args.output, {"timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
                           "queries": {key: {"sparql": q, "response": query(env, q)} for key, q in queries.items()}})
    else:
        frozen = OUT / "holdout.json"
        manifest = json.loads((OUT / "freeze.json").read_text())
        assert hashlib.sha256(frozen.read_bytes()).hexdigest() == manifest["holdout_sha256"]
        cases = json.loads(frozen.read_text())["cases"]
        if args.ids:
            ids = set(args.ids.split(","))
            cases = [c for c in cases if c["id"] in ids]
            assert len(cases) == len(ids)
        output = OUT / args.output
        if output.exists():
            raise FileExistsError(output)
        with output.open("x") as stream, concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(ask, case, run, args.url) for run in range(1, args.runs + 1) for case in cases]
            for f in concurrent.futures.as_completed(futures):
                row = f.result()
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(row["id"], row["run"], row.get("outcome", row.get("transport_error")), row["seconds"], flush=True)


if __name__ == "__main__":
    main()
