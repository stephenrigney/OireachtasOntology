"""Bounded offline falsification; NOT a coordinator or natural-language verifier.

Replays the retained read-only responses through the unchanged public compiler.
No model, credentials, network client, dataset or application mutation. Exit 2
means the original-intent authority gap remains, even when pytest passes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poc.nlq.composable_plan import execute_question, validate_plan
from poc.nlq.composable_semantic_planner import complete_v2_plan, validate_composable_plan_draft
from poc.nlq.results import QueryResult
from poc.nlq.vocabulary import supported_predicates

BUNDLE = ROOT / "docs/reports/parliamentary-research-assistant/corrective-admission-live.json"
BUNDLE_SHA256 = "c3c975f36be4a0c72cc55e331770a39a0917e347d39da18f969d31a3130c1c6e"
SPONSOR = "Which Bills did Malcolm Byrne sponsor?"
CAREER = "Which constituencies did Mary Lou McDonald represent?"


def load_bundle():
    content = BUNDLE.read_bytes()
    if hashlib.sha256(content).hexdigest() != BUNDLE_SHA256:
        raise ValueError("Frozen evidence changed; review rather than silently rebaseline.")
    return json.loads(content)


class Replay:
    """Exact ordered query matching, never canned answers to arbitrary queries."""

    def __init__(self, queries):
        self.queries = queries
        self.position = 0

    def query(self, sparql):
        if self.position >= len(self.queries):
            raise ValueError("Unexpected extra compiler query")
        saved = self.queries[self.position]
        if (saved["sparql"] != sparql or saved["outcome"] != "returned"
                or hashlib.sha256(sparql.encode()).hexdigest() != saved["sha256"]):
            raise ValueError("Replay query/order/hash mismatch")
        self.position += 1
        result = saved["result"]
        return QueryResult(result["kind"], tuple(result["columns"]),
                           tuple(tuple(row) for row in result["rows"]), result["boolean"])


def replay(record, reporting_date, predicates):
    client = Replay(record["queries"])
    # Only ordinary compiler paths are replayed, not the five injected parent
    # executions. Their original exact payloads remain available in the bundle.
    outcome = execute_question(record["question"], as_of=date.fromisoformat(reporting_date),
                               fuseki=client, supported_predicates=predicates)
    if client.position != len(client.queries):
        raise ValueError("Unconsumed saved queries")
    if outcome.status != record["status"] or outcome.interaction != record["interaction"]:
        raise ValueError("Compiler outcome changed")
    actual = [list(row) for row in outcome.result.rows] if outcome.result else None
    if actual != record["rows"]:
        raise ValueError("Compiler projection changed")
    if outcome.plan:
        validate_plan(outcome.plan)
    return outcome


@dataclass(frozen=True)
class Atom:
    predicate: str
    subject: str
    objects: tuple[str, ...]
    scope: str


@dataclass(frozen=True)
class Fact:
    atom: Atom
    evidence: str


def project(outcome, evidence_id, scope):
    """Small diagnostic projections of ACCEPTED compiler fields, not new joins.

    Scope is a retained observation, NOT sponsorship date/current office tenure.
    History stays opaque: no natural-language parsing into final outcomes.
    """
    if outcome.interaction != "answer" or outcome.status != "success" or not outcome.result:
        return ()
    plan = validate_plan(outcome.plan)
    refs = plan["referents"]
    rows = outcome.result.rows
    facts = []

    def add(predicate, subject, *objects):
        facts.append(Fact(Atom(predicate, subject, tuple(objects), scope), evidence_id))

    columns = outcome.result.columns
    if columns == ("English short title", "Sponsorship status", "Bill number", "Year",
                   "Recorded sponsor roles", "Official Bill"):
        member = refs["member"]["iri"]
        add("recorded_sponsorship_list", member, *(row[5] for row in rows))
        for row in rows:
            add("recorded_sponsor", member, row[5])
            # Exact compiler classification, not title/name/LLM inference.
            add("recorded_primary_status", member, row[5], row[1])
    elif plan.get("family") == "constituency_representation":
        member = refs["member"]["iri"]
        add("recorded_constituency_list", member, *(row[4] for row in rows))
        for row in rows:
            add("recorded_representation", row[3], row[4], row[5])
    elif plan.get("family") == "bill_lookup":
        for row in rows:
            add("recorded_bill_status", row[4], row[1])
            add("recorded_bill_history", row[4], row[3])
    # Fail closed for other projections; their success alone creates no facts.
    return tuple(facts)


def accept_claim(atom, citation, facts):
    """Typed claim acceptance only. No arbitrary prose-to-atom certification."""
    return any(fact.atom == atom and fact.evidence == citation for fact in facts)


def accept_prose(_text, _atom, _citation, _facts):
    # Attaching a valid atom to stronger prose does not bind that prose.
    return False


def ledger_only_answered(conditions, facts):
    """Deliberately insufficient candidate: omitting a condition defeats this."""
    return bool(conditions) and all(any(f.atom == c for f in facts) for c in conditions)


def original_disposition(original, proposed_conditions, facts):
    """Coordinator-owned guard: an LLM cannot discharge the original-text hold.

    No independent ordinary-language binding is implemented or pretended here.
    The cost is that complete ordinary questions also remain unresolved.
    """
    return {"original": original, "answered": False,
            "unresolved": ["original_intent_not_independently_bound"],
            "proposedConditionsSupported": ledger_only_answered(proposed_conditions, facts)}


def supporting_relevance(objective, operation, *, accepted_bills=(), bill=None):
    """Typed dependency experiment, NOT a binding of free-text user intent.

    Caller-provided objective is untrusted if model-generated. Same Member name
    is not enough: opposition has no automatic edge to sponsorship.
    """
    if operation == "sponsorship":
        return objective in {"sponsored_bills", "sponsored_bill_lifecycle"}
    if operation == "career_constituencies":
        return objective in {"constituency_history", "parliamentary_career"}
    if operation == "bill_lookup":
        return objective == "sponsored_bill_lifecycle" and bill in accepted_bills
    return False


def diagnose():
    bundle = load_bundle()
    predicates = supported_predicates(ROOT / "ontology")
    reporting = bundle["reportingDate"]
    scope = f"retained-local-observation:{reporting};coverage=uncertified;freshness=unknown"
    # Reuse all 26 ordinary observations; do not repeat any live acceptance run.
    ordinary = [r for r in bundle["live"] if r["controlledProposal"] is None]
    outcomes = {r["question"]: replay(r, reporting, predicates) for r in ordinary}
    evidence_ids = {r["question"]: f"frozen-live-{bundle['live'].index(r)}" for r in ordinary}
    facts = {q: project(o, evidence_ids[q], scope) for q, o in outcomes.items()}
    controls = []
    for saved in bundle["offline"]:
        # Exact frozen parent + draft, no easier paraphrase and no expected-label
        # access in the candidate admission/satisfaction functions.
        try:
            partial, _reason = validate_composable_plan_draft(saved["draft"], question=saved["question"])
            admitted = partial is not None
            if partial is not None:
                validate_plan(complete_v2_plan(partial, as_of=date.fromisoformat(reporting)))
        except ValueError:
            admitted = False
        if admitted != saved["admitted"]:
            raise ValueError("Frozen parent admission changed")
        own_question = SPONSOR if saved["draft"]["family"] == "member_bill_sponsorship" else CAREER
        own_facts = facts[own_question]
        # Inject a ledger that omits EVERYTHING beyond the returned listing.
        proposed = [own_facts[0].atom]
        controls.append({"original": saved["question"], "frozenParentAdmitted": admitted,
                         "supportingQuestion": own_question,
                         "supportingCompilerOutcome": outcomes[own_question].interaction,
                         "relevanceAuthority": "not established by compiler or generated ledger",
                         "injectedLedger": [asdict(c) for c in proposed],
                         "ledgerOnlyAnswered": ledger_only_answered(proposed, own_facts),
                         "guarded": original_disposition(saved["question"], proposed, own_facts)})
    return {"verdict": "NO-GO", "designValidated": False,
            "frozenEvidenceSha256": BUNDLE_SHA256,
            "modelCalls": 0, "networkCalls": 0, "datasetMutations": 0,
            "ordinaryOperationsReplayed": len(ordinary),
            "queryResponsesReplayed": sum(len(r["queries"]) for r in ordinary),
            "controls": controls,
            "limitation": "Ledger-only accepts omissions; original-intent hold also blocks complete ordinary questions."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(diagnose(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")
    return 2  # Demonstrated design gap, not a successful admission design.


if __name__ == "__main__":
    raise SystemExit(main())
