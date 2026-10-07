# Post-merge documentation refresh checklist

Recheck only after the relevant workstream merges to `master`. Until then,
current-state claims refer to the integrated `master` snapshot; do not copy
unmerged behavior into the overview.

## After Query Service Phase 2 merges

- [ ] `poc/nlq/README.md`: recheck the newcomer-facing supported data/query
  section, high-level flow, current limitations/experimental-status section,
  and links to the merged Query Service specification/plans. In particular,
  verify whether exact local Member-name ambiguity handling has merged; it is
  in development in the inspected worktree and is not current behavior here.
  Keep this the canonical NLQ guide; do not add a parallel guide.
- [ ] `documentation/current-state.md`: recheck only the NLQ coverage row and
  the short NLQ description/navigation in “Local development, operations and
  history”. Keep application detail in its canonical guide.
- [ ] `README.md`: update its short NLQ summary/link only if the merged user
  entry point or canonical documentation location changes.

## After Phase 6 merges

- [ ] `documentation/current-state.md`: recheck “What the system contains”,
  “Data coverage and limits”, “Identifiers, reconciliation and graph
  ownership”, and the operational-documentation links. Align production
  readiness and publication/recovery claims with merged code and acceptance,
  not the Phase 6 plan alone.
- [ ] `README.md`: recheck its ETL/Fuseki summary and validation commands if
  the supported operator entry point or local developer workflow changes.
- [ ] `documentation/etl-plan.md`: update only the Phase 6 implementation/status
  record needed to preserve the phase history, and keep its design/decision
  record intact. Do not rewrite the plan as a current-state overview.
- [ ] `documentation/phase-5-refresh-operations.md` and
  `documentation/incremental-refresh-state.md`: compare any changed lifecycle,
  state, provenance or recovery contract and correct only obsolete operational
  instructions. Preserve historical verification records with dated context.

For either merge, update links/navigation if the canonical specification or
plan path changes, then run the repository-relative Markdown-link check and
`git diff --check`. Record genuinely unresolved semantic or operational
questions for their owners; do not fill gaps by inference.
