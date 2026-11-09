"""Post-response attribution ONLY. Never changes frozen gates or admission credit."""
from collections import Counter
import json
from pathlib import Path

from run import HERE, VALUES, save, span_text


def main(output):
    cases = {c["id"]: c for c in json.loads((HERE/"cases.json").read_text())["cases"]}
    rows = [json.loads(p.read_text()) for p in sorted((HERE/"results").glob("*-r*.json"))]
    assert len(rows) == 36
    out = {"purpose": "Post-run failure attribution, no relaxed-gate or repaired-result credit", "calls": [], "by_stage": {}}
    for stage in ["proposal", "blind"]:
        usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reported_cost": 0,
                 "non_numeric_cost_payloads": [], "self_checks_complete": 0, "offset_invalid_calls": 0,
                 "role_value_invalid_calls": 0, "returned_parameters": Counter(), "rejection_reasons": Counter()}
        for row in rows:
            case = cases[row["id"]]; call = row[stage]; value = call.get("value", {})
            reqs = value.get("interpretation", {}).get("requirements", [])
            item = {"id": row["id"], "repeat": row["repeat"], "stage": stage, "expected": case["expected"],
                    "role_value_errors": [], "offset_errors": []}
            for i, req in enumerate(reqs):
                if req["value"] not in VALUES[req["role"]]:
                    item["role_value_errors"].append({"index": i, "role": req["role"], "value": req["value"], "binding": req["binding"]})
                for span in req["evidence"] + ([req["argument"]] if req["argument"] else []):
                    try:
                        span_text(case["question"], span)
                    except ValueError as error:
                        item["offset_errors"].append({"index": i, "role": req["role"], "span": span, "error": str(error)})
            out["calls"].append(item)
            usage["calls"] += 1
            usage["self_checks_complete"] += value.get("self_check", {}).get("verdict") == "complete"
            usage["offset_invalid_calls"] += bool(item["offset_errors"])
            usage["role_value_invalid_calls"] += bool(item["role_value_errors"])
            provider = call.get("provider", {}); u = provider.get("usage", {})
            for k in ["input_tokens", "output_tokens"]:
                usage[k] += u.get(k, 0)
            usage["cached_tokens"] += u.get("input_tokens_details", {}).get("cached_tokens", 0)
            cost = u.get("cost", 0) or 0
            if isinstance(cost, (float, int)):
                usage["reported_cost"] += cost
            else:
                usage["non_numeric_cost_payloads"].append(cost)
            parameters = {k: provider.get(k) for k in ["temperature", "top_p", "reasoning", "seed"]}
            usage["returned_parameters"][json.dumps(parameters, sort_keys=True)] += 1
            assessment = row["first_assessment" if stage == "proposal" else "blind_assessment"]
            usage["rejection_reasons"][assessment.get("compatibility", {}).get("reason", assessment.get("reason", "unknown"))] += 1
        out["by_stage"][stage] = usage
    save(Path(output), out)
    print(json.dumps(out["by_stage"], indent=2))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True)
    main(p.parse_args().output)
