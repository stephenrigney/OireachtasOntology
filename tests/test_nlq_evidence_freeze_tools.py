"""Custodian tooling checks only; these are not composition-kernel acceptance."""

import importlib.util
import json
from pathlib import Path

import pytest


def load_tool(name):
    path = Path(__file__).resolve().parents[1] / "tools" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


QUERY = "SELECT ?s WHERE { ?s a <urn:Type> } ORDER BY ?s LIMIT 100\n"


@pytest.mark.parametrize("query", [
    "DELETE WHERE { ?s ?p ?o }",
    "SELECT ?s WHERE { SERVICE <http://example.invalid/> { ?s a <urn:Type> } } ORDER BY ?s LIMIT 100",
    "SELECT ?s FROM <urn:graph> WHERE { ?s a <urn:Type> } ORDER BY ?s LIMIT 100",
    "SELECT ?s WHERE { ?s a <urn:Type> } LIMIT 100",
    "SELECT ?s WHERE { ?s a <urn:Type> } ORDER BY ?s LIMIT 101",
])
def test_capture_rejects_out_of_boundary_before_request(tmp_path, monkeypatch, query):
    tool = load_tool("nlq_freeze_capture")
    monkeypatch.setattr(tool, "urlopen", lambda *a, **k: pytest.fail("No request permitted"))
    source = tmp_path / "query.rq"
    source.write_text(query)
    with pytest.raises(Exception):
        tool.capture(source, tmp_path / "output")
    assert not (tmp_path / "output").exists()


class Response:
    status = 200

    def __init__(self, rows):
        self.raw = json.dumps({"head": {"vars": ["s"]}, "results": {"bindings": rows}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.raw[:limit]


def test_full_page_requires_charged_completion_request(tmp_path, monkeypatch):
    tool = load_tool("nlq_freeze_capture")
    calls = []

    def request(req, timeout):
        calls.append((req.data.decode(), timeout))
        rows = [{"s": {"type": "uri", "value": f"urn:{i}"}} for i in range(100)] if len(calls) == 1 else []
        return Response(rows)

    monkeypatch.setattr(tool, "urlopen", request)
    source = tmp_path / "query.rq"
    source.write_text(QUERY)
    tool.capture(source, tmp_path / "output")
    manifest = json.loads((tmp_path / "output" / "capture.json").read_text())
    assert manifest["enumeration_complete"]
    assert [p["rows"] for p in manifest["pages"]] == [100, 0]
    assert [p["offset"] for p in manifest["pages"]] == [0, 100]
    assert len(calls) == 2 and "OFFSET+100" in calls[1][0]
    assert all(timeout == 20 for _, timeout in calls)


@pytest.mark.parametrize("failure", ["oversized", "timeout"])
def test_no_completion_certificate_after_failed_capture(tmp_path, monkeypatch, failure):
    tool = load_tool("nlq_freeze_capture")

    def request(*args, **kwargs):
        if failure == "timeout":
            raise TimeoutError("mock timeout")
        return Response([{"s": {"type": "uri", "value": "urn:x"}}] * 101)

    monkeypatch.setattr(tool, "urlopen", request)
    source = tmp_path / "query.rq"
    source.write_text(QUERY)
    with pytest.raises((AssertionError, TimeoutError)):
        tool.capture(source, tmp_path / "output")
    assert not (tmp_path / "output" / "capture.json").exists()


def test_integrity_verifier_rejects_tampered_bytes(tmp_path):
    tool = load_tool("nlq_freeze_verify")
    (tmp_path / "artifact.json").write_text("changed bytes")
    (tmp_path / "manifest.json").write_text(json.dumps({"files": {"artifact.json": "0" * 64}}))
    with pytest.raises(AssertionError):
        tool.verify(tmp_path)
