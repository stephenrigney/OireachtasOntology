# Term-count pilot: bounded design review

Independent read-only review examined source checkpoint `6eb109e`, the new
admission tests and existing execution seam, but not fresh-transfer questions
or frozen acceptance material. Its focused run passed **209 tests**.

Findings retained for future work:

- The new typed block is model-facing interpretation input, immediately
  lowered to the existing `{member}` or `{}` slots. It is not another canonical
  query plan. `stage_a.py` and `composable_plan.py` are unchanged.
- Complete directed-clause consumption prevents the old residual-token approach
  from admitting a reordered/inverted relationship. Independent probes found
  no silently dropped condition, negation, date, projection or count target.
- Model-declared roles must exactly match the independently derived intent.
  Legacy drafts use the same analyser but cannot declare the additional roles;
  that compatibility asymmetry is intentional.
- Only terminal excluded-*measure* contrasts are consumed. They never filter
  term identities or reach execution. Named-term/date/party exclusions refuse.
- The inventory/schema/analyser/lowering pattern is structurally reusable in
  existing capability adapters. This is not evidence that another capability
  or arbitrary natural language is supported.
- Conservative grammar coverage is a material limitation. Relative clauses,
  additional voices and the reserved `PERSON` marker have safe-refusal gaps.
  Safety review does not certify language transfer.
- Term-count compatibility failures now use the explicit unsupported-request
  exception rather than the old inconsistent malformed/unsupported split.
  This does not authorise graph repair or a retry path.
- An unused local `count_intent` assignment remains in the pre-existing selector
  function; it has no behavioural effect. Unrelated cleanup was not performed.

The live provider subsequently rejected JSON Schema `uniqueItems`. Checkpoint
`293ab74` removes only that redundant keyword: `maxItems=1` plus exact local
intent comparison still prohibit duplicate exclusions. A deterministic guard
test and a successful provider transport diagnostic cover the correction.

This review is neither execution approval nor production-grade acceptance.

## Independent evidence-accounting review

A subsequent read-only review independently reconciled 63 `/ask` requests,
16/16 controls, 13 available plans with seven relation-ID-only differences,
1/4 fresh positives, 2/2 fresh negatives, the non-credited QD-04 repeat and all
92 original artifact hashes. It confirmed that only the schema/test correction,
not the admission grammar, changed after fresh-question authorship/execution.
Its conclusion supported the explicit **NOT MET / stop for human review** outcome.

It raised two reporting issues during finalisation:

1. `verification.json` and the final suite were still pending when read. They
   have now completed: **2,697 passed, 26 skipped, 23 subtests passed**.
2. Provider-error attribution lacked an archived diagnostic. The original
   sanitised tool output is now explicitly transcribed in
   `provider-transport-diagnostics.json`, with raw-response/timestamp limitations
   stated. No new model call or retrospective response payload was fabricated.

The reviewer did not certify language generalisation or authorise more work.
