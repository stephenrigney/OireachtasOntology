"""Post-run failure attribution only. NEVER relaxes/rescores the frozen gates."""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def semantic_clear(audit):
    # Diagnostic subdecision, NOT an admission result: exact quotes still required.
    return audit["verdict"] == "complete" and all(c["status"] == "preserved" for c in audit["checks"].values())


def audit_details(question, audit):
    return {"semantic_all_clear":semantic_clear(audit),
        "flags":{role:c["status"] for role,c in audit["checks"].items() if c["status"] != "preserved"},
        "invalid_quotes":{role:c["evidence"] for role,c in audit["checks"].items()
                          if c["evidence"] and c["evidence"] not in question}}


def diagnose():
    cases = {c["id"]:c for c in json.loads((HERE/"cases.json").read_text())["cases"]}
    rows = [json.loads(p.read_text()) for p in sorted((HERE/"results").glob("HC*.json"))]
    detail = []
    calls = []
    durations = []
    for r in rows:
        q = cases[r["id"]]["question"]
        d = {k:r[k] for k in ["id","repeat","injection","expected","B1","B2"]}
        if "proposal" in r:
            d["compatibility"] = r["compatibility"]
            d["self"] = audit_details(q, r["proposal"]["value"]["self_check"])
            calls.append(("proposal",r["proposal"]))
            durations.append(r["proposal"]["seconds"] + r["verification"]["seconds"])
        d["verify"] = audit_details(q, r["verification"]["value"])
        calls.append(("verification",r["verification"]))
        detail.append(d)
    pre = json.loads((HERE/"results/preflight.json").read_text())
    calls += [("preflight",pre[k]) for k in ["proposal","verification"]]
    result = {"purpose":"Post-run attribution, not relaxed-gate admission credit", "populations":{}, "provider":{}, "detail":detail}
    for name,pop in [
            ("natural_supported",[d for d in detail if not d["injection"] and d["expected"] == "admit"]),
            ("natural_unsupported",[d for d in detail if not d["injection"] and d["expected"] == "reject"]),
            ("natural_ambiguity",[d for d in detail if not d["injection"] and d["expected"] == "clarify"]),
            ("injected",[d for d in detail if d["injection"]])]:
        result["populations"][name] = {"n":len(pop),
            "compatibility":dict(Counter(d.get("compatibility","not recorded") for d in pop)),
            "self_semantic_all_clear":sum(d.get("self",{}).get("semantic_all_clear",False) for d in pop),
            "self_invalid_quote_rows":sum(bool(d.get("self",{}).get("invalid_quotes")) for d in pop),
            "verifier_semantic_all_clear":sum(d["verify"]["semantic_all_clear"] for d in pop),
            "verifier_flagged_rows":sum(bool(d["verify"]["flags"]) for d in pop),
            "verifier_invalid_quote_rows":sum(bool(d["verify"]["invalid_quotes"]) for d in pop)}
    for kind in ["proposal","verification","preflight","all"]:
        selected = [c["provider"] for k,c in calls if kind == "all" or k == kind]
        result["provider"][kind] = {
            "n":len(selected),
            "reported_usage_cost_sum":str(sum((Decimal(str(p["usage"]["cost"])) for p in selected),Decimal(0))),
            "cost_currency":"not labelled in payload; not independently reconciled billing",
            "cached_input_tokens":sum(p["usage"].get("input_tokens_details",{}).get("cached_tokens",0) for p in selected),
            "reported_temperature":dict(Counter(str(p.get("temperature")) for p in selected)),
            "reported_top_p":dict(Counter(str(p.get("top_p")) for p in selected)),
            "reported_reasoning_effort":dict(Counter(str(p.get("reasoning",{}).get("effort")) for p in selected)),
        }
    result["natural_sequential_pair_seconds"] = {"n":len(durations),"min":min(durations),
        "median":statistics.median(durations),"max":max(durations)}
    return result


if __name__ == "__main__":
    result = diagnose()
    with (HERE/"diagnostics.json").open("x") as output:
        output.write(json.dumps(result,ensure_ascii=False,indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "detail"},indent=2))
