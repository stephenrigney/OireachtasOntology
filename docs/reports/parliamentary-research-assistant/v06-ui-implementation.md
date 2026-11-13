# Parliamentary Research Assistant — v0.6 UI implementation

**Branch:** `parliamentary-research-assistant`

**Implementation source commit:** `5957df0`

**Status:** human usability and product acceptance pending. No merge to `master`
authorised or performed.

## Change and retained boundaries

The permanent Conversation/Report split and mobile view tabs are replaced by one
page: **Ask → Plan → Research → Report → Refine**. The 740px opening canvas has
one multiline question, **Start research**, and two labelled examples that fill
without submitting. Enter writes a newline; Ctrl/⌘+Enter submits. No empty report,
promotional slogan, fake preview or source-certification boilerplate competes
with the question.

After submission, the original question, model interpretation and plan appear in
the primary column before factual dispatch. Findings progressively populate the
920px report document. Prose has a narrower reading measure; factual tables scroll
inside keyboard-accessible regions. A compact follow-up composer sits below the
report. Section actions carry clearable context without overwriting an unfinished
message. In-flow sticky reading navigation makes follow-up and plan reachable in
a long report. Conversation history is an on-demand chronological disclosure.
The plan is not automatically closed while a researcher may be reading it.

Research Activity and row/assertion/source inspection remain modal, with keyboard
focus trapping and return to the original evidence control. New replies,
clarifications and interruptions are visible without opening the transcript.
Failed submissions retain draft text and section context; later failures retain
earlier findings. Unchanged report sections retain their DOM, focus and reading
position. Copy and qualified Markdown export use the existing server output.

**Unchanged:** LLM interpretation/planning/report authorship, automatic guarded
execution, requirement ledger, selective evidence reuse and revision, all four
evidence classifications, provisional qualitative confidence, factual tables and
row-level references, evidence/source registry, draft and limitation qualifications,
query diagnostics and bounded in-memory sessions. No coordinator, compiler,
ontology, mapping, ETL, dataset, query semantics or evidence authority was changed.

## Verification

The existing 94 focused coordinator/workspace regressions pass. Injected-model /
exact compiler-replay Chromium controls pass, including example replacement,
Ctrl and ⌘ submission, multiline draft retention, pre-dispatch plan visibility,
pause/resume, paused follow-up resumption, interruption retention until retry,
section context, nested source inspection, focus return after an originating row
was redrawn, stable reading position and unsupported/planning-failure handling.
Ontology validation passes: 2,586 triples; HermiT executed successfully.

Independent read-only technical review identified paused-follow-up, progressive
drawer focus, initial heading-shift and announcement issues. Corrections preserve
an explicitly requested Pause during submission, retain interruption reasons until
a successful step, find the equivalent evidence control after redraw, avoid
removing an in-flow planning heading on first findings, and use a single progress
announcement region. Browser-default text size is respected; copy controls retain
their descriptive label. This review is not human usability/editorial acceptance.

The configured Chromium journey passed at **1440/1024/768/390/320px**, 200%
text-size and 400% zoom-equivalent reflow, including plan-before-dispatch,
progressive presentation/focus, section-context revision, exact history,
row/assertion inspection and Escape focus return, contained keyboard-scrollable
tables, Copy Markdown, qualified download and reduced motion. No JavaScript errors
were observed. Source-palette contrast checks pass (body/metadata/link text at
least 4.5:1; focus at least 3:1). Final small announcement/focus/table-label
corrections were verified by injected controls and exact-state browser rendering.

The actual verifier resumed after a **test-harness clipboard-await timing error**;
this did not rerun or fabricate R1 research. It rendered the original generated
R1/revision/discussion states and continued R3 in the same live session. The
original interruption and successful continuation are retained and labelled.

The first repository-wide run was **2,563 passed, 26 skipped, one failed**: a
legacy Stage B no-query test picked up configured live-model fallback. That test
passes with `NLQ_LLM_API_KEY=''`; the final isolated full suite is **2,564 passed,
26 skipped**. No compiler or test assertion changed.
Existing FastAPI/RDFLib warnings and skipped checks are not counted as passes.

### Actual research observations

Configured requested model: **`gpt-6-luna`**; reporting date **12 November 2026**;
existing read-only Fuseki records, without a certified snapshot/freshness identity.

- **R1:** 20 recorded sponsored Bills, one compact table, 20 exact lifecycle
  lookups; **21 compiler operations / 22 reads**. The registry retains 129 direct
  facts and one approved distinct-Bill calculation. Recorded Current/Lapsed
  labels and dated stages are not represented as certified final outcomes.
- **Editorial follow-up:** section-context narrative shortened **150 → 85 words**
  (43%); factual tables, source evidence and all 130 facts stayed unchanged, with
  **no new compiler reads**. An evidence-discussion follow-up also reused facts.
- **Same-session R3:** one career operation added four term-specific Dublin
  Central records for Mary Lou McDonald and a separate representation table;
  earlier R1 sections stayed **exactly unchanged**. Roles/continuous tenure were
  not inferred. Combined: **22 operations / 25 reads / nine model calls**,
  133 direct facts and one calculation.
- **R4/R5:** actual-model boundary interactions dispatched **no compiler queries**
  and retained the unsupported committee/party intersection and speech-content
  questions. These are bounded limitations, not successful factual investigations.
- The actual draft uses Levels 1–3 with provisional qualitative confidence.
  Existing deterministic regressions separately preserve segregated Level 4 and
  reject unsupported Level 1/2 promotion and numerical confidence.

### Review locations

[`v06-evidence/README.md`](v06-evidence/README.md) indexes generated reports,
transcripts, model/evidence archives, plan-dispatch observations, test logs and
screenshots. Start with `r1-initial.md`, `r1-revision.md`, `r3-same-session.md`,
`screenshots/opening-1440.png`, `r1-plan-before-dispatch.png`, and the
`final-render-*` document/narrow-screen images. Actual research, exact-state
rendering, earlier unsuccessful trials and injected/replayed controls are distinct.
Updated [launch instructions](../../development/parliamentary-research-assistant.md)
describe shortcuts, navigation, restart requirements and verification commands.

The first actual-model attempt reached the pre-existing process on port 8010,
which held older coordinator code without the current table presentation fields.
It is **excluded** from v0.6 acceptance evidence. A fresh application process was
launched from this worktree on loopback port 8011; the existing process and dataset
were left undisturbed. Launch guidance now explicitly requires restarting Python
after updating the branch.

A subsequent current-source R1 trial accepted the sponsorship and lifecycle
evidence, but the model twice exceeded the existing editorial narrative budget.
The application correctly rejected the revision and retained its earlier draft
and facts. That unsuccessful revision is retained as an earlier trial, not counted
as a successful conversational edit. No guard or coordinator prompt was weakened.
The final browser brief explicitly requests a short total narrative as a normal
conversational instruction; this is not a new report template or research feature.

## Remaining boundary and human gate

This is not formal WCAG conformance, multi-browser coverage, an assistive-technology
audit or independent parliamentary/editorial acceptance. Model prose and question
assessments remain provisional; source completeness/freshness and final legislative
outcomes are not certified. General parliamentary-role discovery and other existing
capability limits remain unchanged. Sessions are local, single-worker and in memory;
export before expiry or restart.

The combined actual trial repeats the outstanding final-outcome question under
several model-created requirement IDs; this existing coordinator/editorial rough
edge is retained for human assessment, not silently deduplicated or represented
as a new UI defect fix. Device software-keyboard and non-Chromium behaviour still
need hands-on review. The plan stays expanded until the user chooses to collapse
it, deliberately avoiding automatic displacement while it is being read.

**Stop at human usability and product acceptance.** Hands-on researchers must assess
how to begin, plan/report orientation, follow-up, evidence inspection and report
usefulness. No further redesign or capability expansion is authorised by technical
test success.
