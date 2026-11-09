"""Deterministic scoring of frozen first responses; makes no network calls."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

from run import HERE, assess, compare, pair_decision, save, semantic_keys, validate_intent


def percentiles(values):
    v = sorted(values)
    return {"median": round(statistics.median(v), 3), "p95": v[max(0, __import__('math').ceil(.95*len(v))-1)],
            "minimum": min(v), "maximum": max(v), "sum": round(sum(v), 3)} if v else {}


def main(output):
    cases = {c["id"]: c for c in json.loads((HERE/"cases.json").read_text())["cases"]}
    ground = json.loads((HERE/"evidence.json").read_text())["candidates"]
    refs = json.loads((HERE/"references.json").read_text())["references"]
    faults = json.loads((HERE/"faults.json").read_text())["faults"]
    rows = [json.loads(p.read_text()) for p in sorted((HERE/"results").glob("*-r*.json"))]
    assert len(rows) == 36 and len({(r["id"], r["repeat"]) for r in rows}) == 36
    for row in rows:
        recomputed = pair_decision(cases[row["id"]]["question"], row["proposal"], row["blind"], ground)
        assert all(row[k] == v for k, v in recomputed.items()), (row["id"], row["repeat"])
    result = {"repetitions": {}, "natural": [], "faults": [], "variability": {}, "usage": {}}
    for repeat in [1, 2, 3]:
        runs = [r for r in rows if r["repeat"] == repeat]
        result["repetitions"][str(repeat)] = {}
        for arm in ["B1", "B2"]:
            supported = sum(r[arm] == "admit" for r in runs if cases[r["id"]]["expected"] == "supported")
            unsafe = sum(r[arm] == "admit" for r in runs if cases[r["id"]]["expected"] == "unsupported")
            result["repetitions"][str(repeat)][arm] = {"supported_admitted": supported, "supported_denominator": 6,
                "false_refusals": 6-supported, "unsafe_admissions": unsafe, "adversarial_denominator": 6}
    for row in rows:
        case = cases[row["id"]]; q = case["question"]
        item = {"id": row["id"], "repeat": row["repeat"], "B1": row["B1"], "B2": row["B2"],
                "expected": case["expected"], "comparison": row["comparison"]}
        for name, key in [("primary", "proposal"), ("blind", "blind")]:
            try:
                validate_intent(q, row[key]["value"]["interpretation"])
                item[name + "_valid_offsets_and_structure"] = True
                if row["id"] in refs:
                    item[name + "_reference_comparison"] = compare(q, row[key]["value"]["interpretation"], refs[row["id"]])
            except Exception as error:
                item[name + "_valid_offsets_and_structure"] = False
                item[name + "_validation_error"] = str(error)
        result["natural"].append(item)
        for fault in [f for f in faults if f["case"] == row["id"]]:
            injected = {"value": fault["candidate"]}
            decision = pair_decision(q, injected, row["blind"], ground)
            targeted_detection = None
            if row["id"] in refs and decision["comparison"] and "error" not in decision["comparison"]:
                original = semantic_keys(q, refs[row["id"]])
                corrupted = semantic_keys(q, fault["candidate"]["interpretation"])
                blind_keys = semantic_keys(q, row["blind"]["value"]["interpretation"])
                changed_roles = {k[0] for k in (original-corrupted) + (corrupted-original)}
                targeted_detection = all(Counter({k: n for k, n in original.items() if k[0] == role}) ==
                                         Counter({k: n for k, n in blind_keys.items() if k[0] == role}) for role in changed_roles)
            result["faults"].append({"id": fault["id"], "case": row["id"], "repeat": row["repeat"], "kind": fault["kind"],
                "B1": decision["B1"], "B2": decision["B2"], "comparison": decision["comparison"],
                "changed_role_matches_frozen_reference": targeted_detection,
                "omission_credit_requires_independent_semantics_review": fault["kind"] == "omission",
                "semantic_detection": bool(decision["comparison"] and not decision["comparison"]["equal"]
                                           and "error" not in decision["comparison"])})
    for id_, case in cases.items():
        runs = sorted((r for r in rows if r["id"] == id_), key=lambda r: r["repeat"])
        item = {}
        for arm in ["B1", "B2"]:
            item[arm + "_stable"] = len({r[arm] for r in runs}) == 1
        for key in ["proposal", "blind"]:
            item[key + "_exact_stable"] = len({json.dumps(r[key].get("value", {}).get("interpretation"), sort_keys=True) for r in runs}) == 1
            try:
                signatures = [tuple(sorted(semantic_keys(case["question"], r[key]["value"]["interpretation"]).items())) for r in runs]
                item[key + "_semantic_stable"] = len(set(signatures)) == 1
            except Exception:
                item[key + "_semantic_stable"] = False
        result["variability"][id_] = item
    calls = [(key, r[key]) for r in rows for key in ["proposal", "blind"]]
    assert len(calls) == 72
    usage = {"calls": len(calls), "preflight": 0, "completed_schema_valid": sum("value" in c for _, c in calls),
             "http_statuses": dict(Counter(str(c.get("http_status")) for _, c in calls)),
             "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "reported_cost": 0, "non_numeric_cost_payloads": [],
             "models_returned": dict(Counter(c.get("provider", {}).get("model") for _, c in calls)),
             "cost_unit": "not specified in provider payload; not independently reconciled billing"}
    for _, call in calls:
        u = call.get("provider", {}).get("usage", {})
        for key in ["input_tokens", "output_tokens"]:
            usage[key] += u.get(key, 0)
        usage["cached_tokens"] += u.get("input_tokens_details", {}).get("cached_tokens", 0)
        cost = u.get("cost", 0) or 0
        if isinstance(cost, (int, float)):
            usage["reported_cost"] += cost
        else:
            usage["non_numeric_cost_payloads"].append(cost)
    result["usage"] = usage
    result["latency_seconds"] = {key: percentiles([c["seconds"] for name, c in calls if name == key]) for key in ["proposal", "blind"]}
    result["latency_seconds"]["parallel_pair_wall_proxy"] = percentiles([max(r["proposal"]["seconds"], r["blind"]["seconds"]) for r in rows])
    result["latency_seconds"]["sequential_pair_sum"] = percentiles([r["proposal"]["seconds"] + r["blind"]["seconds"] for r in rows])
    save(Path(output), result)
    print(json.dumps({"repetitions": result["repetitions"], "usage": result["usage"], "latency": result["latency_seconds"]}, indent=2))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True)
    main(p.parse_args().output)
