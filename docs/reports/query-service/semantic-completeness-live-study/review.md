# Independent pre-live review and disposition

Reviewer: `architecture-plan-auditor`, session `ses_e3f771622ffeo19n6zHbMIVXHx`.
Read-only review, no provider calls or mutations. It reproduced the 16-assertion
selftest, confirmed existing-plan validation, 100 study-call budget, concurrency
two, no retries and no executable-path changes. The subsequent two-call transport
preflight was frozen before live execution; no prompt tuning is permitted.

Accepted cautions:

- B2 is a stricter intersection with B1 by construction. It cannot improve
  reachability over B1; its possible benefit is catching unsafe drafts. Report
  natural interpretation and injected failure probes separately.
- An escape means exactly `admit`, not any non-reject status. Clarification,
  unresolved identity and transport error are safe nonanswers, not counts.
- Empty audit evidence is allowed for implicit/absent roles. The gate checks
  exact Member/exclusion spans and nonempty audit quotes when supplied; it does
  not prove semantic completeness or quote coverage for every role.
- Audit quote matching is raw, case-sensitive substring matching. Unicode or
  punctuation differences may cause safe provenance refusals; inspect and
  disclose those rather than silently normalizing after outcomes.
- Same-model separate calls are not statistically independent.

Factual clarifications (no harness change):

- The review worried nullable `type: [string, null]` might be unsupported. The
  existing pilot's proven `termCountIntent.member` uses precisely that form in
  `composable-query-plan-draft.schema.json:235`. Retain the frozen schema and
  rely on the declared preflight; a failure stops, not silently repairs, the run.
- A is NOT an unconditional admission ceiling. The actual
  `analyse_term_count(...)` call must succeed first inside the `try`; failure
  sets A to reject. Its returned intent is also archived. Only after grammar
  success does the known baseline intent supply the grounding gate. Catalogue
  `admit` is likewise reachable only after grammar success. "Best-case ceiling"
  refers to being given the correct Member span, not skipping the grammar.
- The final frozen selftest prints 16, matching its assertions. No remaining
  15-assertion message is present.

No change to the frozen code, cases or prompts was required by this review.
This is a second perspective, not architectural or production approval.

The same reviewer subsequently confirmed both factual corrections against the
final frozen files, and confirmed the README distinguishes quote provenance from
proof and constructed injections from observed interpreter errors. It requested
precision that A's parse failures are directly measured whereas downstream
grounding is supplied; that wording is included in the report.

## Completed-run independent review

The same reviewer reproduced `summary.json` to a new disposable output with
identical parsed values, verified manifest hashes, and confirmed the headline
results, 102 completed responses, 17/20 B1 decision stability and 13/20 exact
interpretation stability. It inspected decoded structured values (not opaque
encrypted reasoning) and independently confirmed explicit semantic discrepancy
flags on **20/20** injections, irrespective of their bad quote provenance.

It supports **REVISE, not adopt**, with these retained caveats:

- Zero B2 reachability is dominated by evidence-string format violations and one
  false local-scope complaint, not established semantic disagreement or robust
  safety margins. No post-hoc relaxed admission credit is justified.
- Typed interpretation is promising but not an admission result: 15/16 supported
  candidates are compatible, with a catalogue-entity shape mismatch in HC08/r1.
  HC17's opaque `other` output fails to preserve the exact election-win measure;
  the all-clear self-audit supplies no protection. Existing extra-output refusal
  already prevents that candidate's admission.
- A genuine grammar reachability limit is measured; a separate same-model call
  is not statistical independence. One model/prompt pair, two repetitions,
  one lossy injected shape and a tiny corpus cannot establish generalisation.
- Source-span representation and per-obligation text/bindings need a newly
  frozen protocol, not repairs to current evidence or a production integration.

One numerical correction to the review narrative: not all 14 supported B1
refusals are attributable solely to quote format. **13** have bad self-audit
quotes; **HC08/r1** has valid self-audit quotes but fails the catalogue-entity
compatibility rule. The report and `diagnostics.json` retain this exact split.
Likewise, 40 all-clear self-audits are not 40 demonstrated false certificates:
many represent unsupported requests adequately; HC17 is the concrete lossy case.
