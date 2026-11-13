# Processing visibility and research outcomes

**Date:** 13 November 2026
**Branch:** `parliamentary-research-assistant`
**Status:** Implementation and deterministic verification complete; human review pending. This is not product acceptance.

## Diagnosis

Long planning, query, investigation and writing calls were synchronous and held
the per-run mutation lock. The workspace consequently had no trustworthy way to
show what was happening during a slow call, and a normal state read could wait
behind that call. At the other end of a run, task-level failure messages could
be repeated or could make a failed operation look like an empty result. A single
run-level “in progress” state also made an unrelated follow-up mark already
validated sections as still populating. Finally, a browser losing its response
could not distinguish an unconfirmed request from work that had never started.

These were processing, presentation and failure-reporting problems. This work
did not change the evidence authority, query capabilities, compiler safeguards,
ontology, source data, or what counts as accepted evidence.

## Behavior changes

- **Visible, non-blocking progress.** Initial planning now runs as a distinct
  step. `GET /runs/{id}/progress` reads an in-memory processing snapshot without
  waiting for the per-run mutation lock. The snapshot identifies the current
  phase and operation, elapsed time, observed stages, completion state and next
  operation. The workspace presents this while retaining serial, versioned
  mutations; the plan is rendered before factual dispatch.
- **Section-specific states.** A section is evaluated against its accepted
  evidence, requirement and related pending/blocked work. A validated section
  stays validated during an unrelated follow-up. States distinguish pending,
  populating, validated, incomplete, unsupported and blocked work.
- **One user-facing outcome.** Findings with unanswered questions keep the
  findings and qualifications together. No-finding outcomes are summarized once
  rather than repeated as stacked process messages. Execution failure,
  validation failure, unsupported questions, planning failure, evidence-handoff
  failure and report-writing failure have different labels and recovery advice.
  Technical details remain available in Research Activity; a transport or
  internal failure is not described as proof that no records exist.
- **Safer retries and diagnostics.** Start and follow-up requests carry
  idempotency IDs bound to their exact text. A browser retry of an unconfirmed
  submission reuses the ID; reusing an ID for different text is rejected. A
  repeated versioned step remains idempotent. The UI preserves the draft and
  report, explains that an in-flight operation may finish, and, when a run
  exists, records redacted browser/network diagnostics for Research Activity.
- **Compatibility and scope.** The original `ResearchRun` factory remains
  usable through the HTTP step route. Progress and idempotency state are
  lightweight and in memory only; no persistent queue or background worker was
  introduced.

## Verification

- `NLQ_LLM_API_KEY='' .venv/bin/python -m pytest tests -q`: **2,629 passed,
  26 skipped, 23 subtests passed**.
- `.venv/bin/python tests/validate.py`: **passed**, 2,586 ontology triples;
  HermiT executed successfully.
- Injected-model / exact compiler-response browser verification passed with no
  JavaScript errors. It observed the initial plan before dispatch, slow
  server-side planning progress, pause/resume, preservation of partial findings,
  failed and retried requests, planning failures and clarification. Summary and
  representative screenshots are retained under
  [`processing-visibility-evidence/injected/`](processing-visibility-evidence/injected/).
- A separate configured-model (`gpt-6-luna`) and read-only Fuseki browser run
  tested the frozen probe: “Which Labour Party Members represented Wexford
  during the 31st Dáil?” The plan was visible before factual dispatch; the run
  completed without browser JavaScript errors. All four Query Service responses
  reported `answer` / compiler `success`, but the application rejected each at
  the evidence handoff (`integration_unavailable`): the returned evidence shape
  was not supported by the structured factual boundary. No facts were accepted;
  the final state was “Records found — report not completed.” The full archive,
  export, browser summary, dispatch observations and screenshots are retained
  under [`processing-visibility-evidence/configured-wexford/`](processing-visibility-evidence/configured-wexford/).
  This is a reproduced evidence-handoff limitation, not a successful answer.

## Live R1 editorial result and limitations

A separate configured-model/Fuseki R1 browser leg completed with 130 accepted
facts and preserved its source evidence. Its report left the final-outcome
question unanswered, appropriately distinguishing recorded status/activity
from a certified final outcome. The initial overview was 49 words; the requested
revision was 41 words. The existing browser acceptance check requires at least
a 30% reduction (no more than 34.3 words for that baseline), so this revision
**failed**. The verifier stopped at that check; it did not treat the revision as
accepted and did not reach its embedded Wexford leg. The frozen Wexford control
above was then run independently. Word counts and exact overview text are
retained in [`configured-r1/r1-editorial-check.json`](processing-visibility-evidence/configured-r1/r1-editorial-check.json).

The exact question from the original Wexford report was not located in the
reviewed retained archives. Therefore the frozen Wexford probe does **not**
establish the original question's runtime cause. Its separate evidence-handoff
failure also does not justify changing the evidence contract or promoting the
unaccepted raw rows. Resolving that reproduced handoff shape requires a
separately reviewed contract-level change; it was not weakened here.

Other limitations: progress, deduplication and reports remain process-local and
expire after one hour; this was Chromium automation, not human acceptance, a
screen-reader audit or formal WCAG conformance. Existing local servers on ports
8010 and 8011 were not changed or stopped; the configured probe used a fresh
local server on port 8012 and read-only Fuseki access.
