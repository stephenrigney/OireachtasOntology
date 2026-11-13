# v0.6 research-workspace review evidence

**For human usability and product review — not product acceptance.** See the
[implementation report](../v06-ui-implementation.md) and the unchanged
[acceptance contract](../../../specifications/parliamentary-research-assistant-acceptance.md).

## Actual configured research

The final browser run uses a freshly launched local application, the configured
requested model identifier `gpt-6-luna`, and existing read-only Fuseki data. No
reload, dataset update or new external source is involved. The unchanged R1/R3
briefs come from the user/acceptance contract. Browser automation, evidence
discussion and the added instruction to keep the Bill sections are
implementation-agent-authored checks, not independently collected user research.

- `r1-initial.md`, `r1-revision.md`, `r1-evidence-discussion.md`,
  `r3-same-session.md`: unedited generated report bodies, with only the technical
  appendix relocated to the review bundle for readability.
- `full-combined-export.md`: complete application Markdown including all accepted
  factual assertions, classifications, limitations and evidence.
- `research-review-bundle.json`: exact model inputs/outputs, accepted source
  envelopes, factual registry, requirement assessments and section snapshots.
  The R4/R5 boundary runs are limitations, not successful factual research.
  `earlierTrials` separately preserves the current-source R1 attempt whose model
  revision exceeded the existing narrative budget twice and was safely rejected.
  It is not counted as a successful editorial refinement.
- `conversation-transcripts.json`: exact chronological user/assistant exchanges.
- `plan-dispatch-observations.json`: browser-observed plan/interpretation/task
  state immediately before step requests; no query is manually authorised by
  the verifier. The initial planning screenshot precedes the first factual read.
- `browser-summary.json`, `screenshots/`: actual Chromium UI observations, including
  opening, planning, report, follow-up, history, row/assertion inspection and narrow
  layouts. Opening-screen images contain no generated research.
- The actual verifier resumed after a clipboard-await timing error in the test
  harness: its original live R1/revision/discussion leg is retained, then those
  exact generated snapshots were rendered again and R3 continued on the **same
  live server session**. `checks/browser-actual-original-leg.txt` records the
  interruption; `checks/browser-actual-resumed.txt` records the passed continuation.
  This is not another fresh R1 model/Fuseki trial. Initial plan/progressive-focus
  assertions passed before the verifier interruption; the plan-dispatch file
  includes the original and resumed observations.
- `additional-screenshot-context.json` identifies the `final-render-*` screenshots
  and final small UI corrections checked by exact-state rendering. They use the
  retained generated combined report with **no new model or compiler calls**;
  they are not another research trial. Source-button text no longer breaks into
  letter fragments at the far end of a narrow scrolling table.
- `manifest.json`: source context and hashes, not an immutable dataset snapshot
  or independent attestation of the serving model.

## Injected/replayed controls and regression checks

`injected-ui/` is explicitly **injected model + exact saved compiler-response
replay**, with deliberate HTTP, planning and compiler failures. It is not another
real-model trial or a model error-rate measurement. It covers Ctrl and ⌘ shortcuts,
example replacement choices, exact multiline draft retention, pause/resume,
section context, nested-source focus return, history and retained reports after
interruption/failure. `checks/` retains regression and validation logs; one
whitespace-only traceback line in `pytest.txt` has trailing spaces removed.

The first attempted live browser run used the old process already on port 8010;
its coordinator was older than this checkout. It is excluded, not substituted for
the fresh run on port 8011, and not counted as successful v0.6 evidence.

Review the complete original question, interpretation, draft, qualifications and
sources together. Compare the initial/revised R1 prose and exact retained Bill
sections after adding R3. Assess how easily a first-time researcher can start,
read, refine, inspect evidence and return to their place. Chromium automation is
not formal WCAG conformance, a screen-reader audit or human product acceptance.
