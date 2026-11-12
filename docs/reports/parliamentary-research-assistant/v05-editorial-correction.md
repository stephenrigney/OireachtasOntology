# Parliamentary Research Assistant — Improve Research Report Quality and Evidence Presentation

**Branch:** `parliamentary-research-assistant`  
**Implementation commit:** `85c8afb48086986592399ec2a0da74dd3b677801`  
**Status:** bounded technical verification complete; human product/editorial
acceptance pending. No independent editorial acceptance is claimed.

## Bounded correction

The retained v0.5 transcripts show the author selecting 21 sponsorship assertions
as standalone paragraphs, then selecting another 23 lifecycle assertions under
three explanatory paragraphs. Some of those same assertions also appeared in a
questions section. The editorial plan labelled “Make the overview shorter” as
needing clarification; the coordinator copied its explanatory process statement
into the unanswered list. Subsequent turns accumulated more such explanations.
This was not an evidence shortage: the retained registry already held the full
accepted sponsorship and individual lifecycle evidence.

The correction retains the LLM as author and the compiler as factual authority:

- Exact accepted fields can be presented in compact Bill/representation tables.
  The model selects organisation, headings, rows and illustrative activities.
  Each row exposes **all** associated accepted assertions, not only the selected
  activities. Full source records remain in the inspector and export.
- Ordinary factual detail need not become speculative interpretation simply
  because it describes several records: use exact table fields and the existing
  approved calculation. Genuine model reasoning remains provisional Level 3;
  ungrounded free synthesis cannot be promoted to Level 1/2. The qualitative
  confidence rubric and the four evidence levels are unchanged.
- Typed requirement kinds distinguish substantive research questions, evidence
  limitations, editorial instructions, process messages and clarification.
  Unanswered entries reference stable substantive requirement IDs instead of
  accumulating arbitrary explanatory strings.
- Editorial guidance requests substantial shortening, selective replacement and
  preservation of factual tables/unrelated sections. Rendering now notices changes
  in assertion text even when stable paragraph IDs are reused. Nested inspection
  preserves the original keyboard focus-return target.

An actual intermediate model trial still expanded its overview from **87 to 113
words** after the shortening request. It is not counted as meeting the revision
criterion. The coordinator now gives the **model-selected** shortening target a
65%-of-prior-prose word budget, preserves its factual tables and excludes unrelated
sections from that edit. The existing bounded repair handles an over-budget
proposal. This constrains length, not meaning: the LLM still chooses the useful
summary and explanation. No semantic-certification gate was introduced.

Independent technical review also caught strict-schema incompatibility in two
new defaulted fields before the first query could run. Both fields are now
required end-to-end, with a recursive model-schema regression. Endpoint/model
failures now retain credential-redacted diagnostics in the local archive rather
than silently losing them. A temporary pending question can be removed by the
next same-subject evidence assessment; editorial turns cannot delete it through
omission, and additive research preserves earlier subjects' questions.

A subsequent manual reading caught a subtler stale-entry case: the original
plan's partly-supported “What progress?” question remained open even after the
recorded progress was presented, alongside the genuinely unavailable final
outcomes. The author can now make an **explicit provisional recorded-scope
assessment** with accepted fact references; omission alone cannot remove a known
partial gap, and unsupported/unavailable questions cannot be retired this way.
The original plan and current model assessment are both inspectable. This is the
existing requirement-assessment responsibility, not independent certification of
arbitrary user language or report prose.

No ontology, ETL, dataset, compiler operation, source acceptance, semantic
certification gate or confidence authority was changed. Exact identity alignment
for a table is presentation of already accepted observations, not a new inferred
relationship or a final-outcome calculation.

## Verification and retained review material

The source correction is committed separately from this evidence/completion
record. The final representative run uses the existing configured requested model
identifier **`gpt-6-luna`**, the existing read-only Fuseki dataset and application
reporting date **12 November 2026**. This is not an independent attestation of the
serving model or an immutable dataset snapshot. No dataset reload occurred.

Independent read-only technical review found no factual-promotion path, compiler
acceptance weakening, protected-boundary change, or material authority defect in
the final question-assessment and shortening mechanisms. It independently reran
the focused coordinator tests. This was technical review, **not parliamentary or
editorial product acceptance**.

### Final configured observation

The final trial is a **fresh full configured run**, not the earlier resumed
verifier trial or a manually rewritten report. Its model output is retained
unchanged in [`v05-editorial-evidence/`](v05-editorial-evidence/README.md).

- **Initial R1:** 20 Bill rows, each with exact sponsorship classification and
  recorded status. The author selected **42 dated activity assertions** for the
  table. All **129 direct facts and one approved calculation** remain available
  individually; nothing was removed from the accepted registry. The investigation
  used **21 compiler operations / 22 actual read-only queries**.
- **Editorial revision:** narrative decreased from **173 to 112 words** (35%),
  including a lead paragraph reduced from **60 to 27 words**. The author retained
  concrete examples explaining why lapse events and later stage entries should
  not be combined into a final-outcome conclusion. The table, all 130 facts,
  source envelopes and compiler-read count were unchanged. No repair retry was
  required in this final trial.
- **Questions:** R1 leaves one substantive question open: final outcomes. The
  earlier recorded-progress question is explicitly assessed at recorded scope;
  coverage/freshness limits remain separate. Editorial and evidence-discussion
  turns neither add process statements to that list nor duplicate it.
- **Combined R1/R3:** R1 remains byte-identical at section level. A separately
  headed career section adds four term-specific Dublin Central records for Mary
  Lou McDonald, with a representation table and no inferred offices or continuous
  tenure. Parliamentary roles remain an additional substantive question. The
  combined session retains **133 direct facts + one approved calculation**,
  **22 compiler operations / 25 reads / nine model calls**.
- **Classes:** table fields retain exact Level 1 authority; the distinct-Bill
  calculation remains Level 2 in the inspector. Free narrative remains
  provisional, not upgraded by its references. No hypothesis was needed in the
  final document: final outcomes and roles appear as questions, not speculative
  explanations. Deterministic tests separately exercise segregated Level 4 and
  reject unsupported Level 1/2 promotion and numerical confidence.
- **Browser:** plan-before-dispatch, row-to-individual assertion inspection,
  source access, keyboard activation/Tab/Escape/focus return, horizontal table
  scrolling, Enter/Shift+Enter, qualified Markdown download, all-fact export,
  **1440/1024/768/390/320px**, 200% text-size and narrow reflow checks passed.
  No JavaScript errors occurred. R4/R5 remained truthful coverage boundaries
  without irrelevant compiler calls.

### Concrete comparison with retained v0.5

| Reading surface | Previous v0.5 initial R1 | Corrected initial R1 |
|---|---:|---:|
| Report-body reading words | 2,008 | 829 |
| Individual assertion paragraphs | 57 | 2 |
| Standalone direct-fact paragraphs | 51 | 0 — exact fields in the table |
| Repeated visible assertion references | 8 | 0 |
| Bill rows in the primary research table | 0 | 20 |

The corrected revised report is **768 reading words**, compared with **1,888** in
the retained v0.5 revision. Measurements exclude technical appendices, hash IDs,
class-label lines and Markdown separators; see
[`comparison-metrics.json`](v05-editorial-evidence/comparison-metrics.json).
The editorial follow-up intentionally does **not** shrink away the factual
table: its substantial reduction is in the overview, not the evidence.

The useful change is organisational, not just numerical. A reader can scan Bills,
sponsorship and recorded status across one table rather than reconcile repeated
paragraphs in sponsorship, progress and question sections. Selected developments
explain the research significance of conflicting-looking entries. The report
does not treat them as a procedural history or certified final outcome. Detailed
events not selected for the table remain one row-inspection action away, and
every individual assertion can still open its full source evidence.

The final initial/revised prose uses the correct Bill title years for the named
examples, unlike the retained intermediate error. It still uses provisional
factual synthesis where arbitrary wording cannot be compiler-authorised. Some
qualifications recur in prose, table guidance and the limitations list; they are
much less repetitive than per-assertion boilerplate, but proportionality and
editorial merit remain for the human reviewer, not a word-count test.

### Verification evidence

- Final affected coordinator/workspace checks: **94 passed**.
- Ontology validation: **passed**, 2,586 triples; HermiT executed successfully.
- Final repository suite: **2,564 passed, 26 skipped; 23 subtests passed**.
  The retained `checks/pytest-delivery.txt` is the final implementation run;
  `pytest-final.txt` is the preceding 2,563-pass run, not an extra final pass.
- Injected/replayed browser controls passed pause/resume, pre-dispatch plan
  visibility, modal keyboard/focus, retained report after independent query
  failure and single message replay. These are not actual-model observations.
- Python compilation, JavaScript syntax and `git diff --check` passed. Existing
  RDFLib/FastAPI deprecation warnings and skipped tests are not hidden or counted
  as passes.
- Archive integrity checks resolved every table/assertion reference and compared
  all **134 exact factual texts, levels and structured propositions** with the
  retained v0.5 registry: identical factual content. The shorter visible report
  did not remove or alter that research. A scan found no configured API key or
  Fuseki password in the retained artefacts.

Start human review with the [initial R1](v05-editorial-evidence/r1-initial.md),
[revised R1](v05-editorial-evidence/r1-revision.md) and
[combined R1/R3](v05-editorial-evidence/r3-same-session.md). The
[full combined export](v05-editorial-evidence/full-combined-export.md) retains the
large source appendix. The [review bundle](v05-editorial-evidence/research-review-bundle.json)
retains model transcripts, exact evidence, assessments and earlier unsuccessful
trials. Screenshots and test logs are indexed in the evidence README. Additional
table-heading/narrow-screen screenshots are explicitly labelled exact-state
rendering of the retained generated revision, not another model/Fuseki trial.

## Remaining limits and human review

- Free prose and question assessments are provisional model output. A citation
  does not verify an arbitrary synthesis. Exact table fields remain Level 1;
  only the existing distinct-Bill calculation is Level 2. Unverified synthesis
  cannot be promoted to either. Genuine interpretation retains the existing
  qualitative rubric; no new evidence level or confidence percentage was added.
- Intermediate actual trials exposed a misdated Bill reference in an overview,
  as well as the shortening and stale-question defects above. Exact-title/year
  guidance now expressly distinguishes a Bill's title year from its activity
  dates and distinguishes recorded activity from unknown later progress. Earlier
  outputs remain retained, not silently rewritten or represented as successful
  final demonstrations. Prompt guidance is not independent prose certification.
- Final outcomes, current source freshness/completeness and general parliamentary
  roles remain outside the evidence available here. No new source or compiler
  capability was added to fill those gaps.
- Question retirement is deliberately bounded to an explicit recorded-scope
  assessment during the current factual subject's author pass. A missed partial
  assessment can remain conservatively open later. Editorial turns can reopen an
  assessment but cannot silently retire prior research; other subjects cannot
  rewrite it. Detailed assessment history is in the JSON archive/UI, not the
  Markdown question list.
- The shortening budget is not a measure of editorial merit. Model target
  selection and explanatory emphasis remain reviewable; section-context
  misunderstandings can leave an intended change unapplied. An over-budget
  proposal gets one repair, not unlimited regeneration.
- Chromium checks are not formal WCAG conformance, a screen-reader audit or
  multi-browser coverage. Source-data qualifications, one-hour in-memory session
  expiry and the local single-worker deployment boundary remain unchanged.
- Activities omitted by the author from a table row remain in its inspector.
  Empty selected-activity cells currently say “No accepted value shown”; this
  means no value was selected for that cell, **not** that the source has no
  activity. The row inspector and table qualification preserve the distinction,
  but this label remains a plain-language rough edge for human review.

**Stop at human product acceptance.** Technical checks do not independently accept
the generated research or authorise capability expansion.
