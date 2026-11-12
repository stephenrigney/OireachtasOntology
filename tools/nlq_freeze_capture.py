"""Read-only custodian capture; not an NLQ compiler or experimental executor.

Usage: python tools/nlq_freeze_capture.py QUERY.rq NEW_OUTPUT_DIRECTORY
The query must be an explicitly bounded, ordered SELECT. A full final page
requires another request, including an empty completion page where necessary.
"""

import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "http://localhost:3030/houses/query"


def capture(query_path, output):
    if not __debug__:
        raise RuntimeError("Do not disable custodian assertions with Python -O")
    query = Path(query_path).read_text()
    from rdflib.plugins.sparql.parser import parseQuery

    assert parseQuery(query)[1].name == "SelectQuery"
    assert not re.search(r"\b(SERVICE|FROM|INSERT|DELETE|LOAD|CLEAR|DROP|CREATE|MOVE|COPY|ADD)\b", query, re.I)
    assert re.search(r"ORDER\s+BY", query, re.I)
    assert re.search(r"LIMIT 100\s*$", query)
    assert len(query) <= 32000
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "query.rq").write_text(query)
    pages = []
    for page in range(40):
        paged = query.rstrip() + (f" OFFSET {page * 100}" if page else "")
        start = datetime.now(timezone.utc).isoformat()
        request = Request(ENDPOINT, data=urlencode({"query": paged}).encode(),
                          headers={"Accept": "application/sparql-results+json"})
        with urlopen(request, timeout=20) as response:
            raw = response.read(8_000_001)
            assert len(raw) <= 8_000_000
            status = response.status
        parsed = json.loads(raw)
        rows = parsed["results"]["bindings"]
        assert len(rows) <= 100
        name = f"page-{page:02}.json"
        (output / name).write_bytes(raw)
        pages.append({"file": name, "offset": page * 100, "rows": len(rows),
                      "sha256": hashlib.sha256(raw).hexdigest(), "http_status": status,
                      "started": start, "finished": datetime.now(timezone.utc).isoformat()})
        if len(rows) < 100:
            break
    else:
        raise RuntimeError("Capture exhausted diagnostic page budget; NOT complete")
    manifest = {"endpoint": ENDPOINT, "asOf": "2026-11-11", "timeout_seconds": 20,
                "max_rows_per_request": 100, "max_diagnostic_pages": 40,
                "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                "enumeration_complete": True, "pages": pages,
                "snapshot": "Sequential SELECT captures, not a transactional store snapshot"}
    (output / "capture.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{output.name}: {sum(p['rows'] for p in pages)} rows / {len(pages)} requests")


if __name__ == "__main__":
    capture(*sys.argv[1:])
