#!/usr/bin/env python3
"""Reproduce the reference-coverage census from immutable raw API captures.

Example:
  .venv/bin/python tools/reference_census.py \
    --state-db ~/.local/share/oireachtas-etl/core-state.sqlite \
    --members-capture data/raw/members/2026-10-04/run-<uuid> \
    --parties-capture data/raw/parties/2026-10-04/run-<uuid> \
    --constituencies-capture data/raw/constituencies/2026-10-04/run-<uuid> \
    --output /tmp/reference-census.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote

from oireachtas_etl.raw_captures import load_authoritative_capture
from oireachtas_etl.reference_coverage import build_reference_census
from oireachtas_etl.state import AUTHORITATIVE_COMPLETE_SOURCES


class ReadOnlyCoreRunStore:
    """Read authority evidence without triggering a Core State migration."""

    def __init__(self, path: Path):
        uri = "file:" + quote(str(path.resolve())) + "?mode=ro"
        self.connection = sqlite3.connect(uri, uri=True)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def successful_complete_run(self, endpoint: str, run_id: str) -> dict | None:
        if endpoint not in AUTHORITATIVE_COMPLETE_SOURCES:
            return None
        row = self.connection.execute(
            "SELECT * FROM etl_run WHERE run_id=? AND endpoint=? "
            "AND status='succeeded' AND is_complete=1", (run_id, endpoint),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["parameters"] = json.loads(result.pop("parameters_json"))
        if result["parameters"].get("source") != AUTHORITATIVE_COMPLETE_SOURCES[endpoint]:
            return None
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-db", type=Path, required=True,
                        help="Core State database anchoring successful complete API captures")
    parser.add_argument("--members-capture", type=Path, required=True)
    parser.add_argument("--parties-capture", type=Path)
    parser.add_argument("--constituencies-capture", type=Path)
    parser.add_argument("--output", type=Path,
                        help="write full deterministic census JSON; default writes stdout")
    args = parser.parse_args(argv)

    if not args.state_db.expanduser().is_file():
        raise ValueError(f"Core State database does not exist: {args.state_db}")
    store = ReadOnlyCoreRunStore(args.state_db.expanduser())
    try:
        members, _ = load_authoritative_capture(args.members_capture, "members", store)
        parties, _ = (load_authoritative_capture(args.parties_capture, "parties", store)
                     if args.parties_capture else ([], None))
        constituencies, _ = (
            load_authoritative_capture(args.constituencies_capture,
                                       "constituencies", store)
            if args.constituencies_capture else ([], None))
    finally:
        store.close()
    result = build_reference_census(
        member_records=members,
        party_records=parties,
        constituency_records=constituencies,
        member_capture_complete=True,
        party_capture_complete=args.parties_capture is not None,
        constituency_capture_complete=args.constituencies_capture is not None,
    )
    payload = json.dumps(result["report"], ensure_ascii=False,
                         sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.expanduser().write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
