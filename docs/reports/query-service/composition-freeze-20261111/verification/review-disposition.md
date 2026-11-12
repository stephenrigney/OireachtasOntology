# Independent review disposition

The protocol audit is retained unchanged in `protocol-review.md`. It inspected an
in-flight tree, as its own hashes and caveat state. These are the custodian's
bounded integration responses, not new findings attributed to the auditor.

| Finding | Disposition |
|---|---|
| B1: stale/incomplete manifest | Regenerate `manifest.json` after artifact integration; the final integrity run must cover every public file and pass before handoff/commit. |
| B2: stale verification/count record | Record the actual 111-control state in `checks.json`, rerun integrity verification, and retain `artifact-integrity.json`. No kernel/control execution pass is claimed. |
| C1: conditional duplicate-row disposition | Protocol now requires per-request pre/post-transform raw counts, join counts, and the applicable within-bounds/over-budget disposition in the future harness ledger. |
| C2: boundary padding accounting | Protocol explicitly requires retained pre-dedup counts, padding counts and intermediate witness counts. Boundary tests are counter-unit checks, not claims about naturally occurring eight-request plans. |
| C3: `house`/`houses` adaptation | Protocol explicitly preserves singular Dáil scope versus the two-House union; the notation is not a compiler schema. |
| C4: independent-review provenance | Raw oracle review was authored by a separate `executor-high` session (`ses_e34edb366ffezBaCjDfgRet78z`). Protocol audit was a separate `architecture-plan-auditor` session (`ses_e34e62b13ffevk0H5RAvM4dnyB`). The parent copied the raw checker/comparator/report, clarified the report's read-order wording to match actual code, added durable invocation paths/integration notes, and reran both scripts. No independent label is claimed for parent-authored verification summaries or protocol integration. Shared source/model infrastructure does not confer statistical or blinded independence. |
| C5: baseline test collection | `checks.json` explicitly records 2,436 existing tests passed / 30 skipped and nine new tooling tests passed separately after collection. This is not labelled a single 2,445-test full-suite run. |

Both independent raw/oracle scripts passed on 2026-11-12 at the original pinned
`asOf=2026-11-11`. The protocol review checked all 111 removal sets against the
1,782-quad base and found no weakened material requirement. Controls remain frozen
test specifications for future execution; no unbuilt kernel has passed them.

The user subsequently instructed proceeding after the explicit custody/access
check; temporary oracle/archive deletion was verified on 2026-11-12. See
`../custody.json` for the exact authorization and its limits. Transcript/access
exclusion relies on human authorization; session history was not deleted. Later
candidate-freeze/release remains locked. No semantic contract, source fixture,
dataset or compiler was changed.
