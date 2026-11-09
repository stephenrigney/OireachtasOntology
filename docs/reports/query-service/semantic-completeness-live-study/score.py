"""Summarize this isolated design study; no provider or application calls."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def summarize(directory):
    rows = [json.loads(p.read_text()) for p in sorted(directory.glob("HC*.json"))]
    if len(rows) != 60 or len({(r["id"],r["repeat"],r["injection"]) for r in rows}) != 60:
        raise ValueError("Incomplete/duplicate population: require 40 natural and 20 injected rows")
    result = {"natural":{}, "injected":{}, "stability":{}, "calls":{}}
    for injection, population in [(False,"natural"), (True,"injected")]:
        for rep in [1,2]:
            subset = [r for r in rows if r["repeat"] == rep and r["injection"] == injection]
            expected_counts = Counter(r["expected"] for r in subset)
            if expected_counts != (Counter(reject=10) if injection else Counter(admit=8,reject=10,clarify=2)):
                raise ValueError("Population denominator changed")
            arms = ["B1","B2"] if injection else ["A","B1","B2"]
            result[population][str(rep)] = {}
            for arm in arms:
                stats = {}
                for expected in ["admit","reject","clarify"]:
                    group = [r for r in subset if r["expected"] == expected]
                    if group:
                        stats[expected] = {"n":len(group), "outcomes":dict(Counter(r[arm] for r in group))}
                result[population][str(rep)][arm] = stats
    natural = [r for r in rows if not r["injection"]]
    by_id = {id:[r for r in natural if r["id"] == id] for id in sorted({r["id"] for r in natural})}
    for arm in ["A","B1","B2"]:
        changed = [id for id,rs in by_id.items() if rs[0][arm] != rs[1][arm]]
        result["stability"][arm] = {"identical_decisions":20-len(changed), "n":20, "changed":changed}
    exact_changed = []
    for id, rs in by_id.items():
        if any("value" not in r.get("proposal",{}) for r in rs):
            exact_changed.append(id)
        elif rs[0]["proposal"]["value"]["interpretation"] != rs[1]["proposal"]["value"]["interpretation"]:
            exact_changed.append(id)
    result["stability"]["exact_interpretations"] = {"identical":20-len(exact_changed), "n":20, "changed":exact_changed}
    all_calls = []
    for row in rows:
        for key in ["proposal", "verification"]:
            if key in row:
                all_calls.append((key, row[key]))
    preflight = json.loads((directory/"preflight.json").read_text())
    for key in ["proposal", "verification"]:
        if key in preflight:
            all_calls.append(("preflight",preflight[key]))
    for kind in ["proposal", "verification", "preflight"]:
        calls = [c for k,c in all_calls if k == kind]
        durations = sorted(c["seconds"] for c in calls)
        usage = Counter()
        for call in calls:
            for k,v in call.get("provider",{}).get("usage",{}).items():
                if isinstance(v,int): usage[k] += v
        result["calls"][kind] = {"n":len(calls), "completed":sum("value" in c for c in calls),
            "errors":[c.get("error") for c in calls if "error" in c],
            "returned_models":dict(Counter(c.get("provider",{}).get("model","not returned") for c in calls)),
            "usage_totals":dict(usage), "usage_missing":sum("usage" not in c.get("provider",{}) for c in calls),
            "seconds":{"min":min(durations), "median":statistics.median(durations),
                       "p95_nearest_rank":durations[math.ceil(.95*len(durations))-1], "max":max(durations)}}
    result["per_case"] = [{k:r.get(k) for k in ["id","repeat","injection","expected","A","B1","B2","compatibility"]} for r in rows]
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=HERE/"results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = summarize(args.directory)
    with args.output.open("x") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in value.items() if k != "per_case"}, indent=2))
