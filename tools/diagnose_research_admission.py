"""Read-only omission controls, NOT product acceptance or a research interface.

Default: offline draft/plan admission only. --live additionally uses the existing
configured read-only service, never an LLM or update endpoint. Exit 2 means an
incomplete injected proposal was admitted; it is not a passing safety check.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator

from poc.nlq.composable_plan import execute_question, plan_question, validate_plan
from poc.nlq.composable_semantic_planner import complete_v2_plan, validate_composable_plan_draft
from poc.nlq.representation import representation_plan
from poc.nlq.research_adapter import QueryTrace
from poc.nlq.vocabulary import supported_predicates


R1 = ("Prepare a briefing on the Bills sponsored by Malcolm Byrne. "
      "What progress have they made, and what happened to them?")
R3 = ("Prepare a background briefing on Mary Lou McDonald's parliamentary "
      "career, including constituencies represented and parliamentary roles.")
SPONSOR_QUESTION = "Which Bills did Malcolm Byrne sponsor?"
CAREER_QUESTION = "Which constituencies did Mary Lou McDonald represent?"
# Complete means the INJECTED proposal covers the question, not data completeness.
CASES = [
    ("sponsorship", SPONSOR_QUESTION, True),
    ("sponsorship", "Find legislation listing Malcolm Byrne among its sponsors.", True),
    ("sponsorship", "Which Bills did Malcolm Byrne oppose?", False),
    ("sponsorship", "Which housing Bills did Malcolm Byrne sponsor?", False),
    ("sponsorship", "Which Bills did Malcolm Byrne sponsor that became law?", False),
    ("sponsorship", "Which Bills did Malcolm Byrne sponsor as a Senator?", False),
    ("sponsorship", "Which Bills did Malcolm Byrne primarily sponsor?", False),
    ("sponsorship", "Which Bills did Malcolm Byrne sponsor before 2024?", False),
    ("sponsorship", R1, False),
    ("representation", CAREER_QUESTION, True),
    ("representation", R3, False),
    ("representation", "Which constituencies did Mary Lou McDonald represent during her ministerial service?", False),
    ("representation", "Which constituencies did Mary Lou McDonald represent before 2020?", False),
]
PUBLIC_CASES = {CASES[i][1] for i in (2, 3, 8, 10, 11)}


def proposal(kind, as_of):
    if kind == "sponsorship":
        plan = plan_question(SPONSOR_QUESTION, as_of=as_of)
        answer = {"kind": "entities", "referent": "bill", "distinctBy": "identity",
                  "display": ["label"], "details": [], "preserveEvidence": True}
    else:
        plan = representation_plan(as_of=as_of, member="Mary Lou McDonald", current=False)
        answer = copy.deepcopy(plan["answer"])
    refs = {key: {"type": ref["type"], "mention": ref.get("mention")}
            for key, ref in plan["referents"].items()}
    if kind == "representation":
        refs["term"]["selector"] = None
    family = "member_bill_sponsorship" if kind == "sponsorship" else "constituency_representation"
    return {"version": 2, "supported": True, "family": family,
            "unsupportedReason": None, "intent": "Controlled incomplete-proposal diagnostic",
            "referents": refs, "relations": copy.deepcopy(plan["relations"]),
            "constraints": [], "answer": answer}


def fixed_factory(draft):
    class FixedProposal:
        def generate(self, question):
            return json.dumps(draft)
    return FixedProposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--reporting-date", default="2026-11-12")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    as_of = date.fromisoformat(args.reporting_date)
    schema = Draft202012Validator(json.loads(
        (ROOT / "poc/specs/composable-query-plan-draft.schema.json").read_text()))
    bundle = {
        "sourceRevision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reportingDate": as_of.isoformat(), "modelCalls": 0, "datasetMutations": 0,
        "purpose": "Injected-proposal admission diagnosis, not LLM or product acceptance",
        "datasetSnapshot": None, "sourceCoverage": "uncertified", "freshness": "unknown",
        "offline": [], "live": [],
    }
    for kind, question, complete in CASES:
        draft = proposal(kind, as_of)
        schema.validate(draft)
        record = {"question": question, "proposalCompleteForQuestion": complete,
                  "draft": draft, "schemaValid": True, "admitted": False}
        try:
            partial, reason = validate_composable_plan_draft(draft, question=question)
            if partial is not None:
                record.update(admitted=True, plan=validate_plan(complete_v2_plan(partial, as_of=as_of)))
            else:
                record["reason"] = reason
        except ValueError as error:
            record.update(exception=type(error).__name__, reason=str(error))
        bundle["offline"].append(record)

    if args.live:
        from dotenv import load_dotenv
        from poc.nlq.fuseki import FusekiQueryClient, FUSEKI_QUERY_URL_ENV
        load_dotenv(ROOT / ".env.local", override=False)
        client = FusekiQueryClient(os.environ[FUSEKI_QUERY_URL_ENV],
                                  username=os.getenv("OIR_FUSEKI_USER"),
                                  password=os.getenv("OIR_FUSEKI_PASSWORD"))
        predicates = supported_predicates(ROOT / "ontology")

        def execute(question, draft=None):
            trace = QueryTrace(client)
            kwargs = {"semantic_plan_generator_factory": fixed_factory(draft)} if draft else {}
            outcome = execute_question(question, as_of=as_of, fuseki=trace,
                                       supported_predicates=predicates, **kwargs)
            bundle["live"].append({
                "question": question, "controlledProposal": draft,
                "status": outcome.status, "interaction": outcome.interaction,
                "diagnostic": outcome.diagnostic, "plan": outcome.plan,
                "acceptedEvidence": outcome.accepted_evidence,
                "columns": list(outcome.result.columns) if outcome.result else None,
                "rows": [list(row) for row in outcome.result.rows] if outcome.result else None,
                "queries": trace.queries,
            })
            return outcome

        try:
            for kind, question, _ in CASES:
                if question in PUBLIC_CASES:
                    execute(question, proposal(kind, as_of))
            sponsored = execute(SPONSOR_QUESTION)
            # Identity-preserving exact lookup of accepted Bill links, not model
            # composition or guessed identities. No factual expected totals.
            bill_keys = set()
            if sponsored.interaction == "answer" and sponsored.result:
                for row in sponsored.result.rows:
                    match = re.fullmatch(r"https://data\.oireachtas\.ie/ie/oireachtas/bill/(\d{4})/(\d+)", row[-1])
                    if not match:
                        raise ValueError("Unexpected accepted Bill link; no follow-up identity was invented.")
                    bill_keys.add((match[1], match[2]))
            if len(bill_keys) > 32:
                raise ValueError("More than 32 Bills: diagnostic follow-up budget exceeded; no partial completeness claim.")
            for year, number in sorted(bill_keys):
                execute(f"Tell me about Bill {number} from {year}")
            for question in [
                CAREER_QUESTION,
                "How many Dáil terms has Mary Lou McDonald served in?",
                "How long was Mary Lou McDonald a Deputy?",
                "How many committees was Mary Lou McDonald a member of?",
                "How many Bills did Malcolm Byrne sponsor that were published in 2025?",
            ]:
                execute(question)
        finally:
            client.close()

    bundle["incompleteProposalsAdmitted"] = sum(
        item["admitted"] and not item["proposalCompleteForQuestion"] for item in bundle["offline"])
    content = json.dumps(bundle, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(content)
        print(f"Evidence saved: {args.output}")
    else:
        print(content, end="")
    print(f"Incomplete proposals admitted: {bundle['incompleteProposalsAdmitted']} (safety counterexamples, NOT passes)", file=sys.stderr)
    return 2 if bundle["incompleteProposalsAdmitted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
