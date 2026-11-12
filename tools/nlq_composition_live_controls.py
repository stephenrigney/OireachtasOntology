"""Small evaluation-only controls over saved live SELECT pages (no live writes).

These are explicitly synthetic transport faults/equivalent row transformations,
not independent live observations or a repair of the previous withheld replay.
"""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from poc.nlq.experimental_composition import execute
from tools.nlq_composition_live import decode_select, typed_json


class SavedPages:
    timeout = 15

    def __init__(self, exchanges, fault):
        self.exchanges = exchanges
        self.fault = fault
        self.transformations = []

    def select(self, lookup, query, offset):
        matches = [item for item in self.exchanges if item["query"] == query]
        if self.fault == "full-pages" and lookup.kind == "terms":
            # Native paginator still generates each OFFSET and charges each request.
            matches = [item for item in self.exchanges if item["query"] == lookup.query(0)]
        if len(matches) != 1:
            raise AssertionError("Control attempted an uncaptured query")
        columns, rows = decode_select(json.loads(matches[0]["body"]))
        before = len(rows)
        if self.fault == "duplicates-and-order":
            rows.reverse()
            if rows:
                rows.append(deepcopy(rows[0]))
            if len(rows) > 100:
                raise AssertionError("Within-bounds duplicate control became over budget")
        elif self.fault == "missing-start" and lookup.kind in {"K", "R"}:
            rows[0].pop("rangeStart")
        elif self.fault == "raw-101" and lookup.kind in {"K", "R"}:
            rows += [deepcopy(rows[0]) for _ in range(101 - len(rows))]
        elif self.fault == "full-pages" and lookup.kind == "terms":
            rows += [deepcopy(rows[0]) for _ in range(100 - len(rows))]
        elif self.fault == "timeout" and lookup.kind in {"K", "R"}:
            raise TimeoutError("Synthetic required SELECT timeout")
        complete = not (self.fault == "incomplete" and lookup.kind in {"K", "R"})
        self.transformations.append({"kind": lookup.kind, "offset": offset,
                                     "beforeRows": before, "afterRows": len(rows),
                                     "complete": complete})
        return {"columns": columns, "rows": rows, "complete": complete,
                "control": self.fault, "source": "saved live HTTP page; explicitly transformed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    if baseline["report"]["status"] != "answer":
        raise SystemExit("Positive baseline required; do not mask a kernel failure")
    original = baseline["original"]
    cases = [("duplicates-and-order", None), ("missing-start", "Truncated typed fact"),
             ("incomplete", "Incomplete required enumeration"),
             ("raw-101", "Raw response row budget exceeded"),
             ("full-pages", "Whole-plan request/timeout budget exceeded"),
             ("timeout", "Synthetic required SELECT timeout"),
             ("added-term-equality", "Candidate changes the fixed original semantic requirements")]
    artifact = {"baselineSHA256": hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
                "mode": "offline transport controls over newly captured live pages; not old withheld replay",
                "controls": []}
    with args.output.open("x") as saved:
        for name, expected_error in cases:
            candidate = deepcopy(original)
            if name == "added-term-equality":
                candidate["exactSharedBindings"].append("K.term=R.term")
            transport = SavedPages(baseline["exchanges"], name)
            report = execute(original, candidate, transport)
            if expected_error is None:
                passed = (report.get("answer") == baseline["report"]["answer"]
                          and report.get("validatedWitnesses") == baseline["report"]["validatedWitnesses"]
                          and report["intermediate"] == baseline["report"]["intermediate"])
            else:
                passed = (report["status"] in {"nonanswer", "semantic_rejection"}
                          and "answer" not in report and expected_error in report.get("error", ""))
            artifact["controls"].append({"id": name, "candidate": candidate, "passed": passed,
                                         "transformations": transport.transformations, "report": report})
            if not passed:
                break  # Preserve first control failure; no repairs/reruns.
        json.dump(typed_json(artifact), saved, indent=2, ensure_ascii=False)
        saved.write("\n")
    print(json.dumps({"controls": len(artifact["controls"]),
                      "passed": sum(item["passed"] for item in artifact["controls"])}))
    return 0 if len(artifact["controls"]) == len(cases) and all(item["passed"] for item in artifact["controls"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
