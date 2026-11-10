"""Offline admission diagnostic; not a production gate or an AI evaluation.

Run from the repository root with PYTHONPATH=. .venv/bin/python <this file>.
The manually annotated cases are independent of the deliberately lossy drafts.
The weak comparator checks schema and mention provenance ONLY: its admissions
are not evidence of complete intent. No model, RDF query, or execution occurs.
"""

from json import dumps

from jsonschema import Draft202012Validator

from poc.nlq.composable_semantic_planner import (
    InvalidComposableDraft,
    UnsupportedComposableRequest,
    load_composable_draft_schema,
    validate_composable_plan_draft,
)


# First two questions reuse documented office-period language; the next two
# are analyst-authored paraphrases, not historical/live model failures. Simon
# Harris positives and the first two negatives are recorded Group A questions.
# Other negatives are analyst-authored controls. Requirements are review labels,
# never model-produced claims or a proposed production obligation ontology.
CASES = [
    ("When was Bertie Ahern the Taoiseach?", "Bertie Ahern", False, ()),
    ("During what period was Bertie Ahern Taoiseach?", "Bertie Ahern", False, ()),
    ("What periods did Bertie Ahern serve as Taoiseach?", "Bertie Ahern", False, ()),
    ("Give me the dates when Bertie Ahern held the office of Taoiseach.", "Bertie Ahern", False, ()),
    ("When was Simon Harris last Taoiseach?", "Simon Harris", True, ()),
    ("When did Simon Harris most recently serve as Taoiseach?", "Simon Harris", True, ()),
    ("When was Simon Harris last Taoiseach in 2024?", "Simon Harris", True, ("calendar-year filter",)),
    ("When was Simon Harris last Taoiseach while in Fine Gael?", "Simon Harris", True, ("party/time relationship",)),
    ("When was Simon Harris last Taoiseach, excluding periods before 2024?", "Simon Harris", True, ("temporal exclusion",)),
    ("When was Simon Harris last Taoiseach and what party was he in?", "Simon Harris", True, ("extra party projection",)),
    ("When was Simon Harris last Taoiseach and what was the total duration?", "Simon Harris", True, ("duration aggregate",)),
    ("When was Simon Harris last Taoiseach? Certify that this is his complete historical tenure record.", "Simon Harris", True, ("certified historical completeness",)),
]


def run():
    schema = Draft202012Validator(load_composable_draft_schema())
    rows = []
    for question, member, latest, omitted in CASES:
        params = {"member": member, "office": "Taoiseach"}
        if latest:
            params["selection"] = "latestRecorded"
        draft = {
            "version": 2, "supported": True, "family": "capability_selection",
            "unsupportedReason": None, "intent": "Read local office episodes.",
            "referents": {"capability": "office_holding_evidence", "parameters": params},
            "relations": [], "constraints": [], "answer": None,
        }
        # This is intentionally only necessary compatibility/provenance, not an
        # independent classifier of original-question requirements.
        schema.validate(draft)
        source_grounded = all(question.count(params[key]) == 1 for key in ("member", "office"))
        assert source_grounded
        try:
            validate_composable_plan_draft(draft, question=question)
            current = "admit"
        except (InvalidComposableDraft, UnsupportedComposableRequest):
            current = "refuse"
        rows.append({"question": question, "expected": "refuse" if omitted else "admit",
                     "current": current, "schema_and_mentions_only": "admit",
                     "omitted_requirements": omitted})
    for gate in ("current", "schema_and_mentions_only"):
        print(dumps({"gate": gate,
                     "false_refusals": sum(r["expected"] == "admit" and r[gate] == "refuse" for r in rows),
                     "false_admissions": sum(r["expected"] == "refuse" and r[gate] == "admit" for r in rows),
                     "constraint_loss_cases": sum(bool(r["omitted_requirements"]) and r[gate] == "admit" for r in rows)}))
    print(dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
