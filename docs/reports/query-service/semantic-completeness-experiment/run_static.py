#!/usr/bin/env python3
"""Offline diagnostic only: no planner, execution, HTTP, or application changes.

Run from any directory with the repository Python environment. Output must be
new. The deliberately lossy proposals are fault injections, NOT model results.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "poc"))
from nlq.term_count_intent import validate_term_count_parameters  # noqa: E402

BASELINE = "42ecedaef71b769f4c8832af98db8a08d2393ebe"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def typed_compatibility_only(question, proposal, schema):
    """Necessary conditions only; explicitly NOT complete-intent admission.

    No RDF resolution or canonical-plan execution is simulated. Mention presence
    is not identity grounding. This demonstrates the gap left for a verifier.
    """
    if list(Draft202012Validator(schema).iter_errors(proposal)):
        return False
    member = proposal["member"]
    if (member is None) != (proposal["scope"] == "houses_catalogue"):
        return False
    return member is None or question.count(member) == 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite evidence; choose a new output path.")
    source_paths = [
        "poc/nlq/term_count_intent.py",
        "poc/nlq/composable_semantic_planner.py",
        "poc/nlq/composable_plan.py",
        "poc/nlq/stage_a.py",
        "poc/specs/composable-query-plan-contract.json",
        "poc/specs/composable-query-plan-draft.schema.json",
    ]
    for path in source_paths:
        frozen = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT)
        if (ROOT / path).read_bytes() != frozen:
            raise RuntimeError(f"Authoritative file changed: {path}")
    corpus = json.loads((HERE / "cases.json").read_text())
    cases = []
    for original in corpus["cases"]:
        case = {**original, "population": "new_diagnostic"}
        if original["id"] in corpus["pre_execution_adjudications"]:
            case["kind"] = corpus["pre_execution_adjudications"][original["id"]]["kind"]
        cases.append(case)
    pilot = json.loads((HERE.parent / "term-count-pilot/fresh-transfer.json").read_text())
    for original in pilot["cases"]:
        # These already-observed questions are development material, not fresh.
        member = next((name for name in ("Micheál Martin", "Brendan Howlin", "Mary Lou McDonald")
                       if name in original["question"]), None)
        cases.append({"id": original["id"], "question": original["question"],
                      "member": member, "kind": "supported" if original["kind"] == "positive" else "unsupported",
                      "population": "recorded_pilot_development"})
    cases.extend({**c, "population": "executor_authored_sanity_controls"} for c in corpus["sanity_controls"])
    assert len({c["id"] for c in cases}) == len(cases)
    schema = json.loads((ROOT / source_paths[-1]).read_text())["$defs"]["termCountIntent"]
    rows = []
    for case in cases:
        # An oracle-supplied exact mention isolates grammar reachability from
        # planner errors. Unsupported cases intentionally get an incomplete,
        # otherwise executable-looking proposal. No model authors these slots.
        proposal = {
            "countTarget": "DailTerm", "member": case["member"],
            "scope": "houses_catalogue" if case["member"] is None else "member_service",
            "answer": "count_distinct", "exclusions": case.get("exclusions", []),
        }
        try:
            parameters = validate_term_count_parameters(case["question"], proposal)
            admitted, diagnostic = True, None
        except ValueError as error:
            admitted, parameters, diagnostic = False, None, str(error)
        rows.append({
            "id": case["id"], "kind": case["kind"], "population": case["population"], "proposal": proposal,
            "grammar_admitted": admitted, "lowered_parameters": parameters,
            "grammar_diagnostic": diagnostic,
            "typed_compatibility_only": typed_compatibility_only(case["question"], proposal, schema),
            "semantic_verifier_decision": None,
        })
    # Alterations that are schema/slot incompatible are distinguishable from
    # omitted conditions that still satisfy those necessary checks.
    base = next(r for r in rows if r["kind"] == "supported" and r["proposal"]["member"])
    question = next(c["question"] for c in cases if c["id"] == base["id"])
    alterations = []
    for field, value in [
        ("countTarget", "DailMembership"), ("member", "Invented Member"),
        ("scope", "houses_catalogue"), ("answer", "list"),
        ("exclusions", ["34th Dáil"]),
    ]:
        changed = {**base["proposal"], field: value}
        alterations.append({"field": field, "value": value,
                            "typed_compatibility_only": typed_compatibility_only(question, changed, schema)})
    result = {
        "experiment": "offline admission and injected-omission diagnostics; not acceptance",
        "baseline": BASELINE,
        "cases_sha256": digest(HERE / "cases.json"),
        "script_sha256": digest(Path(__file__)),
        "source_sha256": {p: digest(ROOT / p) for p in source_paths},
        "model_calls": 0, "execution_calls": 0,
        "live_unavailability": "No NLQ_LLM_* process settings or .env in current/primary checkout at investigation time; no credential-store search or alternate provider used.",
        "summary": {},
        "rows": rows, "incompatible_alterations": alterations,
    }
    for population in dict.fromkeys(r["population"] for r in rows):
        group = [r for r in rows if r["population"] == population]
        positives = [r for r in group if r["kind"] == "supported"]
        negatives = [r for r in group if r["kind"] == "unsupported"]
        ambiguous = [r for r in group if r["kind"] == "ambiguous"]
        result["summary"][population] = {
            "supported": len(positives),
            "grammar_reachable": sum(r["grammar_admitted"] for r in positives),
            "grammar_false_refusals": sum(not r["grammar_admitted"] for r in positives),
            "unsupported": len(negatives),
            "grammar_unsafe_admissions": sum(r["grammar_admitted"] for r in negatives),
            "injected_incomplete_proposals_passing_necessary_checks": sum(r["typed_compatibility_only"] for r in negatives),
            "ambiguous_cases": len(ambiguous),
            "ambiguous_grammar_admissions_not_identity_decisions": sum(r["grammar_admitted"] for r in ambiguous),
            "semantic_verification_reachability": None,
            "semantic_verification_unsafe_admissions": None,
        }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
