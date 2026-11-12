# Editorial-correction review material

**Drafts for human review, not independently accepted research.** This directory
will retain the configured research/browser observations recorded in the
[correction report](../v05-editorial-correction.md).

The evaluation inputs are the unchanged user-supplied R1 and R3 briefs, followed
by the user's example shortening request. The evidence-discussion prompt and
automated browser interactions are implementation-agent-authored controls.
R4/R5 remain coverage-boundary checks, not successful factual research.

## Artefact contract

- `r1-initial.md`, `r1-revision.md`, `r3-same-session.md`: **unedited generated
  report bodies**. Only the technical assertion/source appendix is relocated to
  the review bundle for easier linear reading; no report prose is manually
  rewritten. A note identifies that relocation.
- `full-combined-export.md`: complete application Markdown response, including
  every accepted factual assertion and all source/query provenance.
- `research-review-bundle.json`: exact model inputs/outputs, short-handle maps,
  compiler evidence, fact registry and report snapshots. Earlier snapshots refer
  to the shared retained registry. Rejected structure/reference proposals remain
  visible; they are not substituted for generated application output.
  `earlierTrials` separately preserves intermediate actual outputs that exposed
  failed shortening or stale question accounting. These are not final acceptance
  demonstrations.
- `conversation-transcripts.json`: unedited user/assistant messages by snapshot.
- `screenshots/`, `browser-summary.json`: Chromium observations and automated
  checks, not independent editorial or accessibility conformance decisions.
- `additional-screenshot-context.json`: identifies the extra heading/overview
  and narrow-screen images rendered from the exact retained revision state, with
  no further model/compiler calls. The primary screenshots come from the final
  fresh configured browser trial.
- `comparison-metrics.json`, `checks/`, `injected-ui-summary.json`: reproducible
  body-length/duplication measurements and retained test logs. Injected UI checks
  are explicitly model-injected and compiler-response replay, not live research.
- `manifest.json`: implementation context and artefact hashes. It does not claim
  an immutable dataset snapshot or independently attest the serving model.

Review the untouched brief alongside each draft. Assess whether the overview
communicates the strongest warranted answer, the table is usable, the selected
developments are meaningful, and qualifications are proportionate. Inspect row
evidence as well as narrative reasoning. Check that status is not treated as
final outcome, representation as officeholding, or citations as certification of
model prose. Compare the actual initial and revised reports, not just lengths.

Retained v0.5 comparison material is unchanged in [`../v05-evidence/`](../v05-evidence/).
Human product/editorial acceptance remains pending.

The final configured trial used requested local model identifier `gpt-6-luna`
and reporting date 12 November 2026. Source freshness, dataset completeness and
immutable snapshot identity remain unknown/uncertified. The archive's model
proposals and narrative are review material, not independent certificates.
