"""Offline integrity/structure checks for custodian evidence, not a kernel scorer."""

import hashlib
import json
from pathlib import Path
import sys

from rdflib import Dataset, Literal, URIRef


def rdf_term(binding):
    if binding["type"] == "uri":
        return URIRef(binding["value"])
    assert binding["type"] == "literal", binding
    return Literal(binding["value"], lang=binding.get("xml:lang"),
                   datatype=URIRef(binding["datatype"]) if "datatype" in binding else None,
                   normalize=False)


def verify(root):
    if not __debug__:
        raise RuntimeError("Do not disable custodian assertions with Python -O")
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    actual = {str(p.relative_to(root)) for p in root.rglob("*")
              if p.is_file() and p.name != "manifest.json"}
    assert set(manifest["files"]) == actual, "Manifest must cover every public artifact"
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name
    development = root / "development"
    captured_quads = set()
    requests = rows_total = 0
    for folder in sorted((development / "captures").iterdir()):
        meta = json.loads((folder / "capture.json").read_text())
        query = (folder / "query.rq").read_bytes()
        assert hashlib.sha256(query).hexdigest() == meta["query_sha256"]
        assert query == (development / "queries" / (folder.name + ".rq")).read_bytes()
        assert meta["enumeration_complete"] and meta["asOf"] == "2026-11-11"
        assert meta["max_rows_per_request"] == 100 and meta["timeout_seconds"] <= 20
        assert 0 < len(meta["pages"]) <= meta["max_diagnostic_pages"] == 40
        for i, page in enumerate(meta["pages"]):
            assert page["offset"] == 100 * i
            raw = (folder / page["file"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == page["sha256"]
            response = json.loads(raw)
            rows = response["results"]["bindings"]
            assert len(rows) == page["rows"] <= 100 and page["http_status"] == 200
            assert (len(rows) == 100 if i < len(meta["pages"]) - 1 else len(rows) < 100)
            assert all(set(row) <= set(response["head"]["vars"]) for row in rows)
            requests += 1
            rows_total += len(rows)
            if folder.name.startswith("resource-audit-") or folder.name == "identity-audit":
                for row in rows:
                    captured_quads.add(tuple(rdf_term(row[k]) for k in ("s", "p", "o", "g")))
    snapshot = Dataset()
    snapshot.parse(development / "evidence.nq", format="nquads")
    reconstructed = set(snapshot.quads())
    assert reconstructed == captured_quads, "Quad slice must losslessly match raw audits"
    controls = json.loads((development / "controls.json").read_text())["controls"]
    assert len({c["id"] for c in controls}) == len(controls)
    # Each edit is independent. Never apply malformed controls to the base store.
    for control in controls:
        for text in control.get("removeQuads", []):
            removal = Dataset().parse(data=text, format="nquads")
            assert set(removal.quads()) <= reconstructed, control["id"]
    oracle = json.loads((development / "oracle.json").read_text())
    assert oracle["asOf"] == "2026-11-11"
    for case in ("R+P", "K+P"):
        qualifying = {r["member"] for r in oracle[case]["candidateDispositions"] if r["qualifies"]}
        assert sorted(qualifying) == oracle[case]["expectedMembers"]
    assert oracle["R+P"]["count"] == len(oracle["R+P"]["expectedMembers"])
    stability = json.loads((development / "stability.json").read_text())
    assert all(c["same_typed_binding_multiset"] for c in stability["checks"])
    assert {Path(c["query"]).stem for c in stability["checks"]} == {
        p.stem for p in (development / "queries").glob("*.rq")}
    print(json.dumps({"integrity": "pass", "first_capture_requests": requests,
                      "typed_binding_rows": rows_total, "audited_quads": len(reconstructed),
                      "development_controls": len(controls)}, sort_keys=True))


if __name__ == "__main__":
    verify(sys.argv[1])
