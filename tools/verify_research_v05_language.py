"""Actual model planning observations, NOT complete research or semantic certification."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.research_collaborator import ResearchRun

CASES = {
    "r1-p1": "Could you give me an account of Malcolm Byrne's proposed legislation, identifying the Bills he sponsored and explaining how far the records show each got?",
    "r1-p2": "I need a reader-friendly note about legislation with Malcolm Byrne as a sponsor. Please investigate its subsequent stages and explain what remains uncertain about its fate.",
    "r3-p1": "What can the parliamentary records tell me about where Mary Lou McDonald represented people and the roles she held? Write a background note.",
    "r3-p2": "Help me understand Mary Lou McDonald's career in the Oireachtas: which constituencies are recorded, and what parliamentary responsibilities can actually be verified?",
    "housing": "Which housing Bills did Malcolm Byrne sponsor?",
    "opposition": "Which Bills did Malcolm Byrne oppose?",
    "senator-before": "Which Bills did Malcolm Byrne sponsor as a Senator before 2024?",
    "ministerial-period": "Which constituencies did Mary Lou McDonald represent during her ministerial service?",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/tmp/oireachtasontology/research-v05/language"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for key, brief in CASES.items():
        run = ResearchRun(brief, date(2026, 11, 12))
        record = {"kind": "actual configured model planning only; no factual queries", "caseOrigin": "AI-authored evaluation input",
                  "state": run.view(), "modelCalls": run.modelCalls}
        (args.output / f"{key}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
        summaries.append({"case": key, "status": run.status, "tools": [t["tool"] for t in run.tasks],
                          "interpretation": run.interpretation, "unanswered": run.unanswered})
    (args.output / "summary.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
