import hashlib
import json

import pytest

from oireachtas_etl.debates_raw import persist_main_xml
from oireachtas_etl.debates_pipeline import run_debate_batch
from oireachtas_etl.debates_readiness import (
    DebateReadinessError,
    load_batch_sources,
    load_manifest,
    make_batches,
)


def _inventory(tmp_path, sizes=(10, 10)):
    raw_root = tmp_path / "raw"
    rows, assessments = [], []
    for index, size in enumerate(sizes):
        url = ("https://data.oireachtas.ie/akn/ie/debateRecord/work-"
               f"{index}/2011-01-01/debate/expression/main.xml")
        body = (b"<akn>" + b"x" * size + b"</akn>")
        source = persist_main_xml(raw_root, body, url)
        metadata_path = next(source.raw_path.parent.glob(f"{source.source_sha256}.*.meta.json"))
        rows.append({
            "url": url, "date": "2011-01-01", "category": "dail",
            "api_work_uri": f"https://data.oireachtas.ie/akn/ie/debateRecord/work-{index}",
            "source_bytes": len(body), "source_sha256": source.source_sha256,
        })
        assessments.append({
            "source_url": url, "date": "2011-01-01", "category": "dail",
            "source_bytes": len(body), "source_sha256": source.source_sha256,
            "metadata_evidence_path": str(metadata_path.relative_to(raw_root)),
            "metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
            "status": "eligible", "work_iri": f"https://data.oireachtas.ie/akn/ie/debateRecord/work-{index}",
        })
    document = {
        "schema": "debates-initial-production-inventory-v1",
        "selection": {"records": rows, "contract": {
            "census_window_start_inclusive": "2011-01-01",
            "categories": ["committee", "dail", "seanad"],
            "written_answers": "excluded", "bill_linkage_filter": "none",
            "selection_key": "unique official main.xml URL",
        }},
        "records": assessments,
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path, raw_root


def test_inventory_selection_is_deterministic_and_both_batch_limits_apply(tmp_path):
    path, _ = _inventory(tmp_path, (10, 10, 10))
    manifest = load_manifest(path)
    batches = make_batches(manifest, max_works=2, max_source_bytes=45)
    assert [batch.index for batch in batches] == [0, 1]
    assert [len(batch.records) for batch in batches] == [2, 1]
    assert [batch.source_bytes for batch in batches] == [42, 21]
    assert batches == make_batches(load_manifest(path), max_works=2, max_source_bytes=45)


def test_inventory_replays_exact_xml_and_metadata_evidence(tmp_path):
    path, raw_root = _inventory(tmp_path, (10,))
    batch = make_batches(load_manifest(path))[0]
    sources = load_batch_sources(batch, raw_root)
    assert len(sources) == 1
    assert sources[0].source_sha256 == batch.records[0].sha256


def test_oversized_source_is_explicit_not_omitted(tmp_path):
    path, _ = _inventory(tmp_path, (10, 20))
    with pytest.raises(DebateReadinessError, match="explicit operator disposition"):
        make_batches(load_manifest(path), max_works=25, max_source_bytes=15)


@pytest.mark.parametrize("mutate", [
    lambda doc: doc["selection"]["records"][0].update(category="writtens"),
    lambda doc: doc["selection"]["records"][0].update(date="2010-12-31"),
    lambda doc: doc["selection"]["records"][0].update(source_sha256="bad"),
])
def test_out_of_scope_or_invalid_selection_fails_closed(tmp_path, mutate):
    path, _ = _inventory(tmp_path, (10,))
    doc = json.loads(path.read_text())
    mutate(doc)
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(DebateReadinessError):
        load_manifest(path)


def test_metadata_hash_mismatch_fails_closed(tmp_path):
    path, raw_root = _inventory(tmp_path, (10,))
    batch = make_batches(load_manifest(path))[0]
    metadata = raw_root / batch.records[0].metadata_evidence_path
    metadata.write_bytes(metadata.read_bytes() + b" ")
    with pytest.raises(DebateReadinessError, match="metadata evidence hash differs"):
        load_batch_sources(batch, raw_root)


def test_inventory_withheld_row_is_quarantined_without_transformation_or_graph(tmp_path):
    path, raw_root = _inventory(tmp_path, (10,))
    document = json.loads(path.read_text())
    document["records"][0].update(
        status="quarantined", failure_stage="integration_validation",
        failure_classification="record_integration_validation_failure",
    )
    path.write_text(json.dumps(document), encoding="utf-8")
    batch = make_batches(load_manifest(path))[0]
    source = load_batch_sources(batch, raw_root)[0]
    record = batch.records[0]
    failures = []
    outcomes = run_debate_batch(
        [], withheld_records=[(source, record.work_iri, record.failure_stage,
                               record.failure_classification)],
        on_record_failure=failures.append,
    )
    assert len(outcomes) == 1
    assert outcomes[0].status == "quarantined"
    assert outcomes[0].failure_stage == "integration_validation"
    assert len(outcomes[0].graph) == 0
    assert failures == outcomes
