import argparse
import hashlib
import json
from pathlib import Path

from oireachtas_etl.debates_raw import persist_main_xml
from tools.debates_scope_assessment import command_inventory


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _assessment_inputs(tmp_path: Path, fixture: Path, url: str, *, valid: bool):
    raw_root = tmp_path / "raw"
    body = fixture.read_bytes()
    source = persist_main_xml(raw_root, body, url)
    assessment = tmp_path / "assessment"
    if valid:
        date, category, house_code = "2015-07-02", "seanad", "seanad"
        work_uri = "https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate/main"
    else:
        date, category, house_code = "2015-07-02", "dail", "dail"
        work_uri = "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/main"
    row = {
        "url": url,
        "date": date,
        "category": category,
        "house_code": house_code,
        "bytes": len(body),
    }
    _write_json(assessment / "census_debates_raw.json", [{
        "date": date,
        "debate_type": "debate",
        "chamber_type": "house",
        "house_code": house_code,
        "work_uri": work_uri,
        "xml_uri": url,
    }])
    _write_json(assessment / "census_debates_head.json", [{
        "url": url, "status": 200, "bytes": len(body),
    }])
    _write_json(assessment / "scenario_manifest.json", {
        "scenario_a": [row], "scenario_b_written": [],
    })
    _write_json(assessment / "acquisition.json", [{
        **row,
        "status": "ok",
        "source_sha256": source.source_sha256,
        "raw_path": str(source.raw_path),
        "fetched_bytes": len(body),
    }])
    return raw_root, assessment, body, source


def test_exact_inventory_is_deterministic_and_does_not_write_source_sidecars(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    url = "https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate/mul@/main.xml"
    raw_root, assessment, body, source = _assessment_inputs(
        tmp_path, repo / "data/debates_examples/seanad_2015-07-02.akn.xml", url,
        valid=True,
    )
    first = tmp_path / "inventory.json"
    second = tmp_path / "inventory-replay.json"
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    command_inventory(argparse.Namespace(
        assessment_dir=str(assessment), selection_file=None,
        raw_root=str(raw_root), output=str(first), scratch_root=str(scratch),
    ))
    command_inventory(argparse.Namespace(
        assessment_dir=None, selection_file=str(first),
        raw_root=str(raw_root), output=str(second), scratch_root=str(scratch),
    ))

    assert first.read_bytes() == second.read_bytes()
    inventory = json.loads(first.read_text(encoding="utf-8"))
    assert inventory["summary"]["listed_source_records"] == 1
    assert inventory["summary"]["status_counts"] == {"eligible": 1}
    record = inventory["records"][0]
    assert record["source_sha256"] == hashlib.sha256(body).hexdigest()
    assert record["source_sha256_verified"] is True
    assert record["metadata_verified"] is True
    assert record["work_iri"].endswith("/debate")
    assert record["expression_iri"].endswith("/debate/mul%40")
    assert record["reference_report_bytes"] > 0
    assert record["reference_report_retained"] is False
    assert not list(raw_root.rglob("*.reference-report.json"))
    assert source.raw_path.read_bytes() == body


def test_exact_inventory_records_source_identity_exception_stage_and_disposition(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    url = "https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate/mul@/main.xml"
    raw_root, assessment, _body, _source = _assessment_inputs(
        tmp_path, repo / "data/debates_examples/dail_2015-07-02.akn.xml", url,
        valid=False,
    )
    output = tmp_path / "inventory.json"
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    command_inventory(argparse.Namespace(
        assessment_dir=str(assessment), selection_file=None,
        raw_root=str(raw_root), output=str(output), scratch_root=str(scratch),
    ))

    record = json.loads(output.read_text(encoding="utf-8"))["records"][0]
    assert record["status"] == "quarantined"
    assert record["failure_stage"] == "source_identity"
    assert record["failure_classification"] == "record_source_identity_failure"
    assert record["failure_category"] == "source_url_expression_mismatch"
    assert record["review_status"] == "pending"
    assert "no RDF publication" in record["disposition"]
