"""Fresh configured LLM/read-only Fuseki observations, not human acceptance.

Archives contain real prompts, service proposals/plans, all reads and reports.
No endpoint mutation, reference answers, semantic repairs or question exceptions.
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.config import load_local_environment
from poc.nlq.fuseki import FusekiQueryClient, FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL
from poc.nlq.research_collaborator import ResearchRun, PLAN_INSTRUCTIONS, AUTHOR_INSTRUCTIONS
from poc.nlq.research_tools import ResearchTools, discovery_context
from poc.nlq.vocabulary import supported_predicates

CASES = {
    "j-committee-current": "Who are the current members of the Committee of Public Accounts?",
    "k-committee-history": "What is the membership history of the Committee of Public Accounts?",
    "l-chronology-independent": "When did each Dáil start and finish?",
    "m-partial-committee": "Who are the current members of the Committee of Public Accounts, and how has its membership changed since 2020?",
    "n-partial-multi-domain": "Who are the current members of the Committee of Public Accounts? Also, what did those members say about housing in Dáil debates last year?",
    "a-party-history": "What parties was Stephen Donnelly a member of, and when?",
    "b-r1": "Prepare a briefing on the Bills sponsored by Malcolm Byrne. What progress have they made, and what happened to them?",
    "c-career": "Prepare a background briefing on Mary Lou McDonald's parliamentary career, including constituencies represented and parliamentary roles.",
    # Frozen independent capability choice, not implemented for this tranche.
    "d-party-members": "Who are the Labour Deputies in the current Dáil?",
    "e-unsupported": "What did Mary Lou McDonald say about housing in Dáil debates last year? Quote her speeches.",
    "a-paraphrase": "Could you trace Stephen Donnelly's recorded political party affiliations, showing the membership dates where available?",
    "f-multi-domain": "Give me a short account of Stephen Donnelly's recorded party affiliations with dates, and the constituencies he represented. Keep those separate relationships clear; do not infer that every party episode coincided with an entire Dáil term.",
    "g-calendar-holdout": "Which Dáil was in office during June 1994?",
    "h-mixed-relationships": "What parties was Stephen Donnelly a member of, and when? Also, what constituency does Mary Lou McDonald represent?",
    "i-bill-evidence-smoke": "Tell me about Bill 11 from 2020",
}


def archive(run, output, key):
    (output / f"{key}.json").write_text(json.dumps({"kind": "actual configured LLM and read-only Fuseki",
        "model": os.getenv("NLQ_LLM_MODEL"), "state": run.view(), "evidence": run.evidence,
        "modelCalls": run.modelCalls}, ensure_ascii=False, indent=2))
    (output / f"{key}.md").write_text(run.markdown())


def drain(run, output, key):
    for _ in range(160):
        archive(run, output, key)  # retain partial observations even on interruption
        if not run.has_work():
            break
        run.step(run.version)
    archive(run, output, key)
    print(json.dumps({"case": key, "status": run.status, "tasks": [(t["question"], t["state"]) for t in run.tasks],
        "facts": len(run.facts), "reads": sum(len(e["execution"]["queries"]) for e in run.evidence.values()),
        "modelCalls": len(run.modelCalls)}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", choices=list(CASES), default=list(CASES))
    parser.add_argument("--underlying", action="store_true")
    parser.add_argument("--followups", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    load_local_environment(ROOT)
    client = FusekiQueryClient(os.getenv(FUSEKI_QUERY_URL_ENV, DEFAULT_FUSEKI_QUERY_URL),
        username=os.getenv("OIR_FUSEKI_USER"), password=os.getenv("OIR_FUSEKI_PASSWORD"))
    reporting = date.fromisoformat(os.getenv("OIR_NLQ_AS_OF_DATE", date.today().isoformat()))
    adapter = ResearchTools(client, supported_predicates(ROOT / "ontology"),
        context_id="general-integration-validation", endpoint_id="configured-read-only-fuseki")
    (args.output / "instructions.json").write_text(json.dumps({"plan": PLAN_INSTRUCTIONS,
        "author": AUTHOR_INSTRUCTIONS, "queryServiceDiscovery": discovery_context()}, ensure_ascii=False, indent=2))
    try:
        if args.underlying:
            for key, question in {"a": "What parties was Stephen Donnelly a member of?",
                                  "d": CASES["d-party-members"]}.items():
                env = adapter.execute({"tool": "query", "question": question, "requirementId": "underlying"}, reporting.isoformat())
                (args.output / f"underlying-{key}.json").write_text(json.dumps(env, ensure_ascii=False, indent=2))
                print(json.dumps({"underlying": key, "outcome": env["outcome"], "compilerStatus": env["compilerStatus"],
                    "result": env["queryServiceResult"], "error": env["error"]}, ensure_ascii=False), flush=True)
            return
        for key in args.cases:
            run = ResearchRun(CASES[key], reporting, adapter)
            drain(run, args.output, key)
            if args.followups and key == "d-party-members":
                run.message("Also identify the current Fine Gael TDs, retaining the Labour findings separately. Do not compare totals.")
                drain(run, args.output, key + "-additional-evidence")
            if args.followups and key == "b-r1":
                run.message("Shorten the overview substantially. Keep the factual tables and other findings unchanged.")
                drain(run, args.output, key + "-revision")
    finally:
        client.close()


if __name__ == "__main__":
    main()
