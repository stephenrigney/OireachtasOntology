#!/usr/bin/env python3
"""Score a first-result collection against the frozen semantic acceptance set.

The scorer does not import or inspect the query-service implementation. Its
automatic comparisons require exact RDF-identity links and header-mapped full
rows where the rendered HTML exposes them. A mandatory manual checklist covers
intent, every frozen criterion, qualification, and unsupported/ambiguity limits.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import unicodedata


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
REVIEW_STATES = {"pending", "pass", "fail", "uncertain"}
ANSWER_ROW_FIELDS = ("answerRows", "episodeRows", "evidenceRows", "candidates")
RDF_TYPES = {"uri", "literal", "bnode"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_exclusive(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_json_exclusive(path: Path, value: object) -> None:
    write_exclusive(path, (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def verify_freeze() -> tuple[dict, dict, dict[str, str]]:
    freeze_bytes = (ARTIFACT_DIR / "freeze.json").read_bytes()
    if sha256_bytes(freeze_bytes) != EXPECTED_FREEZE_JSON_SHA256:
        raise ValueError("freeze.json differs from the pinned frozen metadata")
    freeze = json.loads(freeze_bytes)
    if freeze.get("aggregateFreezeSha256") != EXPECTED_AGGREGATE_SHA256:
        raise ValueError("freeze metadata has an unexpected aggregate digest")
    if freeze.get("questionCount") != EXPECTED_QUESTION_COUNT or freeze.get("factualCount") != EXPECTED_FACTUAL_COUNT:
        raise ValueError("freeze counts differ from the pinned 44-case set")
    if freeze.get("referenceDate") != EXPECTED_REFERENCE_DATE or freeze.get("sha256") != EXPECTED_FILE_SHA256:
        raise ValueError("freeze date or artifact hashes differ from the pinned set")

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

    # Hash the compressed oracle artifact, but never need to decompress it.
    holdout = json.loads((ARTIFACT_DIR / "holdout.json").read_text(encoding="utf-8"))
    cases = holdout.get("questions")
    if not isinstance(cases, list) or len(cases) != EXPECTED_QUESTION_COUNT:
        raise ValueError("holdout does not contain the pinned 44 cases")
    if (holdout.get("questionCount") != EXPECTED_QUESTION_COUNT
            or holdout.get("factualCount") != EXPECTED_FACTUAL_COUNT
            or holdout.get("referenceDate") != EXPECTED_REFERENCE_DATE):
        raise ValueError("holdout metadata differs from the pinned frozen set")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != EXPECTED_QUESTION_COUNT or len(set(ids)) != EXPECTED_QUESTION_COUNT:
        raise ValueError("holdout case identifiers are malformed or duplicated")
    return freeze, holdout, observed


class RenderedPage(HTMLParser):
    """Minimal rendered HTML reader retaining table rows, anchor IRIs, and text."""

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
            included = (
                a.get("id") not in self.EXCLUDED_SECTION_IDS
                and "system-status" not in a.get("class", "").split()
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
            self._cell = {"tag": tag, "chunks": [], "links": []}
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
                row.append({"tag": cell["tag"], "text": " ".join("".join(cell["chunks"]).split()), "links": cell["links"]})
        elif tag == "tr" and self._table_stack:
            state = self._table_stack[-1]
            if state.get("row") is not None:
                state["rows"].append(state["row"])
                state["row"] = None
        elif tag == "table" and self._table_stack:
            self.tables.append(self._table_stack.pop()["rows"])
        elif tag == "pre" and self._pre is not None:
            self.pres.append(" ".join("".join(self._pre).split()))
            self._pre = None
        elif tag in ("section", "p") and self._section_stack and self._section_stack[-1]["tag"] == tag:
            section = self._section_stack.pop()
            text = " ".join("".join(section["chunks"]).split())
            if section["include"] and text:
                self.sections.append(text)


def normalize_label(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(ch.lower() for ch in without_marks if ch.isalnum())


def rdf_term(value: object) -> dict | None:
    if isinstance(value, dict) and value.get("type") in RDF_TYPES and isinstance(value.get("value"), str):
        return value
    return None


def term_rows(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict) and any(rdf_term(v) for v in row.values())]


def table_header_and_data(table: list[list[dict]]) -> tuple[list[str] | None, list[list[dict]]]:
    for index, row in enumerate(table):
        if row and any(cell.get("tag") == "th" for cell in row):
            headers = [cell.get("text", "") if cell.get("tag") == "th" else "" for cell in row]
            return headers, table[index + 1:]
    return None, table


def cell_matches_term(cell: dict, term: dict) -> bool:
    value = term["value"]
    if term["type"] == "uri":
        return value in cell.get("links", []) or cell.get("text", "").strip() == value
    return cell.get("text", "").strip() == value


def compare_rows(expected_rows: list[dict], tables: list[list[list[dict]]]) -> dict:
    """Compare complete expected tuples using exact column headers and row links."""
    if not expected_rows:
        return {"status": "not_applicable", "reason": "no expected answer rows"}
    fields = sorted({key for row in expected_rows for key, val in row.items() if rdf_term(val)})
    candidates = []
    for table_index, table in enumerate(tables):
        headers, data_rows = table_header_and_data(table)
        if not headers:
            continue
        normalized_headers = [normalize_label(header) for header in headers]
        columns: dict[str, int] = {}
        for field in fields:
            matches = [i for i, header in enumerate(normalized_headers) if header == normalize_label(field)]
            if len(matches) == 1:
                columns[field] = matches[0]
        if len(columns) != len(fields):
            continue

        # Ignore structural/summary rows whose projected answer columns are
        # all empty, but count every populated projected row when checking for
        # omissions, extras, duplicates, and associations.
        data_rows = [
            row for row in data_rows
            if any(
                columns[field] < len(row)
                and (row[columns[field]].get("text", "").strip() or row[columns[field]].get("links"))
                for field in fields
            )
        ]

        used: set[int] = set()
        matched_rows = 0
        for expected in expected_rows:
            expected_fields = [field for field in fields if field in expected and rdf_term(expected[field])]
            match_index = None
            for index, actual in enumerate(data_rows):
                if index in used or any(columns[field] >= len(actual) for field in expected_fields):
                    continue
                if all(cell_matches_term(actual[columns[field]], rdf_term(expected[field])) for field in expected_fields):
                    match_index = index
                    break
            if match_index is not None:
                used.add(match_index)
                matched_rows += 1
        exact = matched_rows == len(expected_rows) and len(data_rows) == len(expected_rows)
        candidates.append({
            "table_index": table_index,
            "status": "pass" if exact else "fail",
            "expected_row_count": len(expected_rows),
            "rendered_data_row_count": len(data_rows),
            "matched_full_rows": matched_rows,
            "field_columns_header_mapped": True,
            "literal_datatype_language_visible": False,
        })
    if not candidates:
        return {
            "status": "not_verifiable",
            "reason": "no rendered table has an exact header for every expected projected field",
            "expected_row_count": len(expected_rows),
        }
    passing = next((candidate for candidate in candidates if candidate["status"] == "pass"), None)
    return passing or candidates[0]


def compare_identity_set(identity_set: object, tables: list[list[list[dict]]]) -> dict:
    rows = term_rows(identity_set)
    if not rows:
        return {"status": "not_applicable", "reason": "no frozen identity set"}
    comparison = compare_rows(rows, tables)
    comparison["comparison_basis"] = "exact identity column IRIs and exact same-row associations"
    comparison["rdf_literal_metadata"] = "not represented by ordinary rendered HTML; covered by manual review"
    return comparison


def score_expected(case: dict, record: dict | None, page: RenderedPage | None) -> dict:
    expected = case["expected"]
    if record is None or page is None:
        return {
            "http": "fail",
            "identity_set": {"status": "not_verifiable", "reason": "no raw first response"},
            "answer_rows": {},
            "answer_shape": "not_verifiable",
            "manual_review_required": True,
        }

    status = record.get("http_status")
    http_result = "pass" if isinstance(status, int) and 200 <= status < 300 else "fail"
    tables = page.tables
    identity_result = compare_identity_set(expected.get("identitySet"), tables)
    row_results = {}
    for field in ANSWER_ROW_FIELDS:
        rows = term_rows(expected.get(field))
        if rows:
            row_results[field] = compare_rows(rows, tables)

    answer_kind = expected.get("answerKind")
    shape_result = "manual_only"
    if answer_kind == "count" and isinstance(expected.get("countValue"), int):
        value = str(expected["countValue"])
        count_cells = []
        for table_index, table in enumerate(tables):
            headers, data_rows = table_header_and_data(table)
            if headers is None:
                continue
            count_columns = [i for i, h in enumerate(headers) if normalize_label(h) in {"count", "countvalue", "total", "distinctcount"}]
            for row_index, row in enumerate(data_rows):
                for column in count_columns:
                    if column < len(row):
                        count_cells.append((table_index, row_index, column, row[column].get("text", "").strip()))
        if len(count_cells) == 1:
            shape_result = "pass" if count_cells[0][3] == value else "fail"
        elif len(count_cells) > 1:
            shape_result = "fail"
        else:
            shape_result = "not_verifiable"
    elif answer_kind == "boolean" and isinstance(expected.get("booleanValue"), bool):
        # Rendered prose has no stable boolean grammar; leave semantic selection
        # to the required intent/qualification review instead of guessing.
        shape_result = "manual_only"
    elif answer_kind == "value":
        shape_result = "manual_only"

    return {
        "http": http_result,
        "identity_set": identity_result,
        "answer_rows": row_results,
        "answer_shape": shape_result,
        "rendered_outcome": page.outcome,
        "manual_review_required": True,
        "manual_review_reason": "full intent, exact answer values/associations, all criteria, qualifications, RDF literal metadata, and contract boundaries require review",
    }


def _item_id(case_id: str, category: str, index: int, text: str) -> str:
    material = f"{case_id}\0{category}\0{index}\0{text}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:20]


def _review_item(case_id: str, category: str, index: int, text: str) -> dict:
    return {"item_id": _item_id(case_id, category, index, text), "text": text, "status": "pending", "notes": ""}


def make_review_template(holdout: dict, run_id: str) -> dict:
    cases = []
    for case in holdout["questions"]:
        scoring = case.get("scoring", {})
        expected = case.get("expected", {})
        criteria_text = list(scoring.get("criteria", []))
        if scoring.get("identity"):
            criteria_text.insert(0, "Identity rule: " + str(scoring["identity"]))
        criteria = [_review_item(case["id"], "criterion", i, str(text)) for i, text in enumerate(criteria_text)]
        qualifications = [
            _review_item(case["id"], "qualification", i, str(text))
            for i, text in enumerate(expected.get("qualifications", []))
        ]
        boundaries: list[dict] = []
        if expected.get("status"):
            boundaries.append(_review_item(case["id"], "boundary", len(boundaries), "Expected response boundary/status: " + str(expected["status"])))
        if expected.get("reason"):
            boundaries.append(_review_item(case["id"], "boundary", len(boundaries), "Expected boundary rationale: " + str(expected["reason"])))
        if expected.get("mustNotSelectArbitrarily") is True:
            boundaries.append(_review_item(case["id"], "boundary", len(boundaries), "Do not select an ambiguous identity arbitrarily; clarify using the complete candidate set."))
        cases.append({
            "case_id": case["id"],
            "question": case["question"],
            "full_intent": {"status": "pending", "notes": ""},
            "answer_fidelity": _review_item(
                case["id"], "answer_fidelity", 0,
                "Verify every expected answer value, exact RDF identity, and association against the first rendered response; do not infer omitted values.",
            ),
            "criteria": criteria,
            "qualifications": qualifications,
            "boundaries": boundaries,
        })
    return {
        "format_version": 1,
        "frozen_aggregate_sha256": EXPECTED_AGGREGATE_SHA256,
        "run_id": run_id,
        "review_policy": "Review every case's full intent, every criterion, every qualification, and each applicable boundary. Pending or uncertain is not a pass.",
        "cases": cases,
    }


def validate_review(template: dict, supplied: dict) -> dict[str, dict]:
    if supplied.get("format_version") != template["format_version"]:
        raise ValueError("review file format mismatch")
    if supplied.get("frozen_aggregate_sha256") != EXPECTED_AGGREGATE_SHA256 or supplied.get("run_id") != template["run_id"]:
        raise ValueError("review file is for another freeze or collection run")
    provided_cases = supplied.get("cases")
    expected_cases = template["cases"]
    if not isinstance(provided_cases, list) or {c.get("case_id") for c in provided_cases} != {c["case_id"] for c in expected_cases}:
        raise ValueError("review file must contain exactly the frozen case set")
    by_id = {c["case_id"]: c for c in provided_cases}
    validated: dict[str, dict] = {}
    for expected_case in expected_cases:
        got = by_id[expected_case["case_id"]]
        if got.get("question") != expected_case["question"]:
            raise ValueError("review file question text was altered")
        result = {"intent": got.get("full_intent", {}).get("status"), "items": [], "complete": False, "passed": False}
        if result["intent"] not in REVIEW_STATES - {"pending"}:
            result["intent"] = "pending"
        intent_notes = got.get("full_intent", {}).get("notes", "")
        if not isinstance(intent_notes, str) or (result["intent"] in {"fail", "uncertain"} and not intent_notes.strip()):
            raise ValueError("fail/uncertain full-intent review requires a note")
        all_items_pass = True
        all_items_complete = result["intent"] != "pending"
        answer_fidelity = got.get("answer_fidelity", {})
        expected_answer_fidelity = expected_case.get("answer_fidelity", {})
        if answer_fidelity.get("item_id") != expected_answer_fidelity.get("item_id") or answer_fidelity.get("text") != expected_answer_fidelity.get("text"):
            raise ValueError("answer-fidelity review item was altered")
        fidelity_state = answer_fidelity.get("status", "pending")
        fidelity_notes = answer_fidelity.get("notes", "")
        if fidelity_state not in REVIEW_STATES or not isinstance(fidelity_notes, str) or (fidelity_state in {"fail", "uncertain"} and not fidelity_notes.strip()):
            raise ValueError("invalid answer-fidelity review item")
        result["items"].append({"category": "answer_fidelity", "item_id": expected_answer_fidelity["item_id"], "status": fidelity_state})
        all_items_complete = all_items_complete and fidelity_state != "pending"
        all_items_pass = all_items_pass and fidelity_state == "pass"
        for key in ("criteria", "qualifications", "boundaries"):
            expected_items = expected_case[key]
            supplied_items = got.get(key)
            if not isinstance(supplied_items, list):
                supplied_items = []
            by_item_id = {item.get("item_id"): item for item in supplied_items if isinstance(item, dict)}
            if set(by_item_id) != {item["item_id"] for item in expected_items}:
                raise ValueError(f"review checklist items changed for {expected_case['case_id']}")
            for expected_item in expected_items:
                item = by_item_id[expected_item["item_id"]]
                if item.get("text") != expected_item["text"]:
                    raise ValueError("review checklist text was altered")
                state = item.get("status", "pending")
                if state not in REVIEW_STATES:
                    raise ValueError("invalid manual review state")
                notes = item.get("notes", "")
                if not isinstance(notes, str) or (state in {"fail", "uncertain"} and not notes.strip()):
                    raise ValueError("fail/uncertain review items require a note")
                result["items"].append({"category": key, "item_id": expected_item["item_id"], "status": state})
                all_items_complete = all_items_complete and state != "pending"
                all_items_pass = all_items_pass and state == "pass"
        result["complete"] = all_items_complete
        result["passed"] = all_items_complete and all_items_pass and result["intent"] == "pass"
        validated[expected_case["case_id"]] = result
    return validated


def load_collection(run_dir: Path, cases: list[dict]) -> tuple[dict, dict[str, dict], dict[str, RenderedPage | None]]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    completion_path = run_dir / "completion.json"
    if not completion_path.is_file():
        raise ValueError("collection has no write-once completion record; do not retry missing cases")
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    if manifest.get("frozen_aggregate_sha256") != EXPECTED_AGGREGATE_SHA256:
        raise ValueError("collection was made against a different frozen set")
    if manifest.get("freeze_json_sha256") != EXPECTED_FREEZE_JSON_SHA256:
        raise ValueError("collection freeze metadata provenance hash mismatch")
    if manifest.get("frozen_artifact_sha256") != EXPECTED_FILE_SHA256:
        raise ValueError("collection artifact provenance hashes mismatch")
    if manifest.get("question_count") != EXPECTED_QUESTION_COUNT or manifest.get("max_workers", 99) not in (1, 2):
        raise ValueError("collection count or concurrency provenance is invalid")
    if manifest.get("retry_policy") != "none; one first request per frozen case" or completion.get("retries") != 0:
        raise ValueError("collection violates the no-retry policy")
    if manifest.get("ask_calls_executed") is not True or manifest.get("mode") != "phase2" or not manifest.get("ask_endpoint"):
        raise ValueError("collection request provenance is incomplete")
    if completion.get("first_results_retained") is not True:
        raise ValueError("collection does not attest retaining first results")
    expected_ids = [case["id"] for case in cases]
    if manifest.get("case_ids") != expected_ids:
        raise ValueError("collection case sequence differs from the frozen case sequence")

    attempt_dir, result_dir = run_dir / "attempts", run_dir / "results"
    attempt_ids = {path.stem for path in attempt_dir.glob("*.json")}
    result_ids = {path.stem for path in result_dir.glob("*.json")}
    if attempt_ids != set(expected_ids) or result_ids != set(expected_ids):
        raise ValueError("collection is incomplete or contains unexpected/duplicate first-result files")

    case_by_id = {case["id"]: case for case in cases}
    records: dict[str, dict] = {}
    pages: dict[str, RenderedPage | None] = {}
    for case_id in expected_ids:
        attempt = json.loads((attempt_dir / f"{case_id}.json").read_text(encoding="utf-8"))
        if (attempt.get("case_id") != case_id or attempt.get("attempt") != 1
                or attempt.get("question_sha256") != sha256_bytes(case_by_id[case_id]["question"].encode("utf-8"))):
            raise ValueError(f"invalid first-attempt marker for {case_id}")
        record = json.loads((result_dir / f"{case_id}.json").read_text(encoding="utf-8"))
        case = case_by_id[case_id]
        if record.get("case_id") != case_id or record.get("question") != case["question"]:
            raise ValueError(f"collected question/result mismatch for {case_id}")
        if record.get("class") != case.get("class") or record.get("capability_group") != case.get("capabilityGroup"):
            raise ValueError(f"collected case classification mismatch for {case_id}")
        request = record.get("request", {})
        if request.get("method") != "POST" or request.get("mode") != "phase2" or request.get("endpoint") != manifest.get("ask_endpoint"):
            raise ValueError(f"collected request provenance mismatch for {case_id}")
        raw_rel = record.get("raw_html_path")
        if raw_rel is None:
            if record.get("http_status") is not None or not record.get("transport_error_type"):
                raise ValueError(f"missing raw response without recorded transport failure for {case_id}")
            if (run_dir / "raw" / f"{case_id}.html").exists():
                raise ValueError(f"raw response exists but is not referenced for {case_id}")
            page = None
        else:
            if raw_rel != f"raw/{case_id}.html":
                raise ValueError(f"unexpected raw response path for {case_id}")
            raw_path = run_dir / raw_rel
            raw = raw_path.read_bytes()
            if sha256_bytes(raw) != record.get("response_sha256"):
                raise ValueError(f"raw response hash mismatch for {case_id}")
            page = RenderedPage(raw.decode("utf-8", errors="replace"))
        records[case_id] = record
        pages[case_id] = page
    if completion.get("result_case_count") != EXPECTED_QUESTION_COUNT or completion.get("attempted_case_count") != EXPECTED_QUESTION_COUNT:
        raise ValueError("completion record count mismatch")
    if completion.get("manifest_sha256") != sha256_bytes((run_dir / "manifest.json").read_bytes()):
        raise ValueError("collection manifest hash mismatch")
    file_hashes = completion.get("files_sha256")
    if not isinstance(file_hashes, dict):
        raise ValueError("completion record has no output checksums")
    for case_id in expected_ids:
        for kind, rel in (("attempt", f"attempts/{case_id}.json"), ("result", f"results/{case_id}.json")):
            if file_hashes.get(f"{kind}:{case_id}") != sha256_bytes((run_dir / rel).read_bytes()):
                raise ValueError(f"collection {kind} checksum mismatch for {case_id}")
        raw_rel = f"raw/{case_id}.html"
        raw_path = run_dir / raw_rel
        raw_key = f"raw_html:{case_id}"
        if raw_path.exists() and file_hashes.get(raw_key) != sha256_bytes(raw_path.read_bytes()):
            raise ValueError(f"collection raw HTML checksum mismatch for {case_id}")
        if not raw_path.exists() and raw_key in file_hashes:
            raise ValueError(f"unexpected raw HTML checksum for {case_id}")
    expected_raw_ids = {case_id for case_id in expected_ids if (run_dir / "raw" / f"{case_id}.html").is_file()}
    observed_raw_ids = {path.stem for path in (run_dir / "raw").glob("*.html")}
    if observed_raw_ids != expected_raw_ids:
        raise ValueError("collection contains unexpected or unreferenced raw response files")
    expected_hash_keys = {f"{kind}:{case_id}" for case_id in expected_ids for kind in ("attempt", "result")}
    expected_hash_keys.update(f"raw_html:{case_id}" for case_id in expected_raw_ids)
    if set(file_hashes) != expected_hash_keys:
        raise ValueError("completion record checksum inventory is incomplete or unexpected")
    return manifest, records, pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path, help="Completed write-once collector run")
    parser.add_argument("--out", required=True, type=Path, help="New, non-existing scoring directory")
    parser.add_argument("--review-file", type=Path, help="Optional completed copy of review-template.json")
    args = parser.parse_args()

    _, holdout, artifact_hashes = verify_freeze()
    cases = holdout["questions"]
    manifest, records, pages = load_collection(args.run_dir, cases)
    if args.out.exists():
        raise FileExistsError(f"write-once scoring path already exists: {args.out}")
    if args.out.resolve().is_relative_to(ARTIFACT_DIR.resolve()):
        raise ValueError("scoring output must be outside the frozen artifact directory")

    template = make_review_template(holdout, manifest["run_id"])
    template_by_id = {case["case_id"]: case for case in template["cases"]}
    reviews = None
    if args.review_file:
        reviews = validate_review(template, json.loads(args.review_file.read_text(encoding="utf-8")))

    case_reports = []
    auto_pass_count = 0
    final_pass_count = 0
    review_complete_count = 0
    for case in cases:
        case_id = case["id"]
        automatic = score_expected(case, records.get(case_id), pages.get(case_id))
        auto_states = [automatic["http"], automatic["identity_set"].get("status")]
        auto_states.extend(value.get("status") for value in automatic["answer_rows"].values())
        auto_states.append(automatic["answer_shape"])
        auto_failure = any(state == "fail" for state in auto_states)
        auto_fully_verified = bool(auto_states) and all(state in {"pass", "not_applicable"} for state in auto_states)
        auto_no_detected_mismatch = not auto_failure
        auto_pass_count += int(auto_fully_verified)
        review = reviews.get(case_id) if reviews else None
        if review and review["complete"]:
            review_complete_count += 1
        final_pass = bool(auto_no_detected_mismatch and review and review["passed"])
        final_pass_count += int(final_pass)
        checklist = template_by_id[case_id]
        case_reports.append({
            "case_id": case_id,
            "class": case.get("class"),
            "capability_group": case.get("capabilityGroup"),
            "http_status": records[case_id].get("http_status"),
            "first_response_sha256": records[case_id].get("response_sha256"),
            "automatic": automatic,
            "automatic_fully_verified": auto_fully_verified,
            "automatic_no_detected_mismatch": auto_no_detected_mismatch,
            "manual_review": {
                "required": True,
                "complete": bool(review and review["complete"]),
                "passed": bool(review and review["passed"]),
                "intent_status": review.get("intent") if review else "pending",
                "checklist_item_count": 1 + len(checklist["criteria"]) + len(checklist["qualifications"]) + len(checklist["boundaries"]),
            },
            "final_pass": final_pass,
        })

    args.out.mkdir(parents=True, exist_ok=False)
    write_json_exclusive(args.out / "review-template.json", template)
    score_report = {
        "format_version": 1,
        "scored_at_utc": utc_now(),
        "frozen_aggregate_sha256": EXPECTED_AGGREGATE_SHA256,
        "frozen_artifact_sha256": artifact_hashes,
        "run_id": manifest["run_id"],
        "collector_script_sha256": manifest.get("collector_script_sha256"),
        "scorer_script_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "case_count": len(case_reports),
        "factual_denominator": EXPECTED_FACTUAL_COUNT,
        "automatic_fully_verified_count": auto_pass_count,
        "manual_review_complete_count": review_complete_count,
        "final_pass_count": final_pass_count,
        "overall_status": "scoring_complete" if reviews and review_complete_count == EXPECTED_QUESTION_COUNT else "awaiting_manual_full_intent_qualification_review",
        "review_policy": "No final pass without exact automatic evidence where renderable and a complete passing manual review of intent, criteria, qualifications, and boundaries.",
        "cases": case_reports,
    }
    write_json_exclusive(args.out / "score.json", score_report)
    print(json.dumps({
        "score_dir": str(args.out),
        "cases": len(case_reports),
        "automatic_fully_verified_count": auto_pass_count,
        "manual_review_complete_count": review_complete_count,
        "final_pass_count": final_pass_count,
        "overall_status": score_report["overall_status"],
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
