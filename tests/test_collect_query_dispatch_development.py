import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "collect_query_dispatch_development", ROOT / "tools/collect-query-dispatch-development.py"
)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


def test_manifest_contains_frozen_holdout_and_exact_original_table_questions():
    manifest = campaign.load_manifest()
    assert len(manifest) == 86
    assert len([case for case in manifest if case["source"] == "holdout60"]) == 60
    original = [case for case in manifest if case["source"] == "original26"]
    assert len(original) == 26
    assert {case["id"] for case in original} == {
        *(f"R{i:02d}" for i in range(1, 21)), *(f"R{i:02d}" for i in range(22, 26)),
        "R21a", "R21b"
    }


def test_collection_rejects_unknown_ids_and_existing_output(tmp_path):
    destination = tmp_path / "new"
    try:
        campaign.collect([], destination, "http://127.0.0.1:8001", ids=["NOPE"])
    except ValueError as error:
        assert "Unknown case IDs" in str(error)
    else:
        raise AssertionError("unknown selection was accepted")

    destination.mkdir()
    try:
        campaign.collect([], destination, "http://127.0.0.1:8001")
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing output directory was accepted")
