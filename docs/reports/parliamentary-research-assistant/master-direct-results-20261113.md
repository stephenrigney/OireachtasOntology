# Master integration and direct Query Service reporting — 13 November 2026

## Scope and integration

Worktree `query-service-ui`, branch `parliamentary-research-assistant`, starting
at `82bde402ea513e4d06f5e22a30adb089772146cb`. Fetched and merged
`origin/master` at `5f7d970` in merge commit `3d6d895`. Nothing was merged into
master. The only merge conflict was in `poc/nlq/composable_plan.py`: retain both
the research branch's optional evidence fields/finalisation and master's route
identity, typed composition transport and composition execution artifacts.
Automatic merges retained both sides' planner and lifecycle improvements.

Independent read-only review found no lost compiler safeguards. It identified
the material invocation seam: current composition returns an admitted
`composition_request` and kernel `composition_report`, **not** a composable-v2
`plan`. Research now recognises that existing validation artifact instead of
falsely rejecting a successful composition answer for lacking a legacy plan.
The existing closed Phase-1 operation dispatch remains regression-covered; its
merged placement follows master's early recognisers, none of which intercept
the three closed operation questions.

Beyond integrating master's existing changes, no ontology, mappings,
source/golden fixtures, compiler capabilities, query safety checks,
pagination/budgets, RDF ownership or triple-store configuration were changed.
All live access below was read-only; no dataset bootstrap,
publication or update was performed.

## Simplified reporting contract

- `ResearchTools` still calls the public Query Service `execute_question`.
  The existing `CompositionTransport` supports both ordinary `query` and typed
  `select`; the Research Assistant's lazy client and trace delegate to it. The
  kernel retains ownership of composition validation, pagination, limits and
  timeouts. There is no research-owned alternative execution pipeline.
- A successful answer with the appropriate service validation artifact and
  completed execution produces a family-independent `queryResult`: original
  question, exact columns/rows or Boolean, plan/composition scope, route,
  reporting date, qualifications, selection status and actual query references.
  The enclosing evidence retains the original result, SPARQL, complete execution
  trace, typed composition report/ledger, optional evidence, compiler content
  identity and dataset context.
- Missing or inapplicable `factual_evidence` is an optional inspection issue,
  not a veto. Existing factual records/assertions/tables remain available and
  their own acceptance rules are unchanged. They are no longer prerequisites
  for basic reporting, including legacy-tool results.
- Successful answers are visible immediately as unchanged result tables/Boolean
  answers, independently of report-author success. The author receives stable
  `result1`, `result2`, etc. handles, organises `resultRefs` into sections, and
  writes ordinary result-linked draft `summaries`. No assertion classification,
  confidence rating, per-family adapter or new certification framework is needed.
- Returned labels/cells cannot be supplied or rewritten by the report author.
  Draft summaries and provisional comparisons are explicitly separate from
  returned information. Original conditions and subsidiary questions stay
  visible; no claim of exhaustive coverage, source freshness, common snapshot,
  or continuous service follows from a local result.
  Result-only report turns use a controlled conversational acknowledgement;
  substantive model prose belongs in the result-linked draft, not an uncited
  conversational claim about parliamentary absence.
- False, zero and an empty successful table are not execution failures. Empty
  selections retain their local-scope qualification. Failed, unsupported,
  ambiguous, unavailable and invalid queries do not produce reportable results.
  Unincorporated successful answers remain in fallback result sections; partial
  failures, follow-ups and revisions cannot silently delete them. Export and
  inspection retain the same underlying records.

The product specification and development guide record the superseding direct-
result decision. The single-column workflow and existing research/evidence
controls were not redesigned. Reports remain **AI-generated drafts for review**.

## Actual configured-model / Fuseki observations

These are fresh executions with the configured `gpt-6-luna` model and configured
local read-only Fuseki endpoint, reporting date **2026-11-13**, not injected
answers or golden replays. Runtime archives include the actual prompts,
proposals, outcomes, plans, reads, returned cells and reports. They are disposable
under `/tmp/oireachtasontology/research-direct-results/`; durable findings and
reproduction commands are recorded here. No credential values are retained.

### Kildare North

The model decomposed the original question into two term-specific subsidiary
questions. Both succeeded through `member_relationship_composition`, using six
actual reads in total. Both had **zero optional research facts** and were
nevertheless presented in separate term-labelled tables and draft prose:

| Dáil term | Returned Members |
|---|---|
| 33rd | Bernard Durkan; Catherine Murphy; James Lawless; Réada Cronin |
| 34th | Aidan Farrelly; James Lawless; Joe Neville; Naoise Ó Cearúil; Réada Cronin |

Member identities and the service qualification about exact-identity
deduplication/local historical coverage were preserved. This is not a claim of
continuous service or certified exhaustive historical coverage.

### Wexford

The exact original subsidiary question succeeded through
`member_relationship_composition` in four reads. The returned row identifies
**Brendan Howlin** with his exact Member identity, Labour Party affiliation,
separate source intervals and established overlap **2011-03-09–2016-03-09**.
`factualEvidenceStatus` was `unavailable`; the table and useful bounded draft
explanation were still produced. Source qualifications, including open-ended
ends and uncertified historical coverage, remain available.

### Donegal

The initial autonomous run produced useful **partial** research, not a completed
five-term comparison. It attempted chronology/current-term questions, several
of whose wordings the semantic selector rejected without executing queries.
It then obtained and reported the current-term Donegal affiliation selection
in three actual reads:

| Returned affiliation | Members in the returned evidence |
|---|---|
| 100% RDR | Charles Ward |
| Fianna Fáil | Charlie McConalogue; Pat the Cope Gallagher |
| Sinn Féin | Pearse Doherty; Pádraig Mac Lochlainn |

The returned representation and affiliation intervals begin 2024-11-29 and are
open-ended. The report explicitly retained the unanswered five-term question
and did not turn current-term evidence into a five-term account.

Important distinction: the service **does** answer its existing chronology
question, “When did each Dáil start and finish?” (verified separately: 34 rows).
Rejections of model-generated chronology paraphrases are language-routing/
discovery limitations, not proof that chronology is absent or unsupported in
every form. No compiler capability was added to repair them. Relative-term
selection and older Donegal constituency identity/scope still require care;
the assistant must not assume geographic continuity or silently omit terms.

One initial generated summary incorrectly said “four party affiliations” while
listing the three returned groups above. The source table was unchanged. This
illustrates the continuing need to review free model prose; references do not
certify it. This tranche does not introduce a semantic prose-certification gate.

A separate fresh run followed by an explicit request to use the exact supported
chronology question did recover: it selected terms **30–34** from the returned
chronology and retained successful Donegal Member lists for **32, 33 and 34**.
The final partial run had **four successful result records, 14 actual reads and
20 subsidiary tasks**. Combined Member-plus-party projections were rejected
because the proposed graph omitted a requested projection; weaker lists were
not passed off as those answers. Exact constituency label “Donegal” did not
resolve in terms 30/31. Further party-history wordings were refused rather than
silently weakening their scope. The report retained those gaps and produced a
provisional comparison of representation lists, not a complete five-term party
history. That generated comparison also misread one Member's presence across
the three lists, reinforcing the same free-prose review limitation; the exact
source lists remained unchanged and inspectable. This was an explicit follow-up
experiment, not a claim that the original question always decomposes successfully.

### Generic forms and composition

Additional exact subsidiary operations used the same generic consumer:

| Form / operation | Actual result |
|---|---|
| Entity lists | Kildare North's separate 33rd/34th lists above |
| Table / dated overlap | Wexford/Labour row with source intervals above |
| Dates | “When did each Dáil start and finish?” returned 34 term/date rows, including the open current term |
| Count | “How many Dáil terms are listed in the Houses data?” returned `34` |
| Current composition | “Which Fianna Fáil TDs represent Kildare North?” returned James Lawless and Naoise Ó Cearúil, as of 2026-11-13, via `current_member_composition` |
| Boolean availability probe | Timmy Dooley / Select Committee on Transport and Communications returned unavailable evidence on this live dataset, **not** a successful false answer |

Successful ASK handling was therefore verified with **real Query Service
operations over synthetic RDF**, separately from the live dataset. Injected
future-result controls cover both `true` and `false`, entity/table/date/count
outputs, zero and empty tables without any new Research Assistant adapter.
These injected controls do not establish new compiler capabilities or live
data coverage.

### Actual browser / follow-up / revision

Chromium exercised the real Research Assistant HTTP/UI, configured model and
Fuseki: initial Kildare North research, same-session Wexford addition, then an
editorial shortening without new searches. An initial execution ended with
**Findings available** on all three turns. A final-code repeat first submitted
the combined multi-term question, retained its refusal, then successfully
recovered through two term-specific questions. That repeat's overall status
remained **Findings available — some questions unanswered** because the original
failed attempt remains in task history, despite no outstanding ledger questions.
This conservative historical-task status is a remaining presentation limitation,
not loss of the recovered answer or an actual source failure on those lists.
In both executions, all three original result records remained byte-for-
byte equal across the revision, with **10 actual source queries** in total.
The evidence dialog and Markdown/archive endpoints exposed the original
results. Desktop **1280px** and narrow **320px** checks found no document-wide
horizontal overflow and no JavaScript page errors. Screenshots/archives are in
the disposable `live-browser/` directory. This is Chromium observation, not a
formal accessibility or human editorial acceptance claim.

The standalone v0.6 interaction-control browser verifier also passed with an
**injected model and exact compiler-response replay**, not live source answers.
Its selectors now address the stable authored section rather than assuming
there can be only one report section. Checks retained plan-before-dispatch,
pause/resume, modal keyboard/Escape/focus return, progressive redraw/reading
position, failed submissions, interruption/retry, same-session revisions,
slow-call progress, five opening widths and enlarged-text/reflow controls.
No JavaScript errors were observed.

## Deterministic verification

Before the reporting changes:

- Merged-code full suite: **2805 passed, 46 skipped, 23 subtests passed**.
- Ontology validation: **passed**, 2586 triples, HermiT completed successfully.

After the reporting changes:

- Focused research/result/browser/evidence interoperability regressions: **129 passed**.
- Ontology validation: **passed**, 2586 triples, HermiT completed successfully.
- Final full deterministic suite: **2831 passed, 46 skipped, 23 subtests passed**
  in 726.62 seconds. Skips remain the existing optional/opt-in cases; live
  observations above are recorded separately, not counted as deterministic tests.
- `git diff --check`: passed.

New controls exercise genuine compiler operations with optional projectors
disabled, typed composition through both the adapter and lazy HTTP client,
author failure with immediate visible results, preserved exact values/column
meanings/qualifications, source inspection/export, failed queries with misleading
result-shaped data, incomplete execution, partial failures, follow-ups, revisions
and unknown result references. Existing assertion tests now address stable
authored section IDs rather than assuming the report has no automatic result
sections; their factual-authority and revision checks remain intact. No source
or golden fixture was changed.

The first full reporting run passed 2,830 tests and exposed one additional old
interoperability expectation that successful unprojected answers must be refused.
That expectation now requires the exact original result to be reportable while
still asserting that no optional factual assertions are manufactured from rows.
The interoperability suite is included in the 129 passing focused checks above.

The follow-up independent review also prompted focused compatibility fixes:
missing exact Bill identities now block only lifecycle follow-on dispatch (the
successful Bill list remains reportable); results-only lifecycle completion can
schedule authorship; malformed legacy result shapes fail controlled; and blank
returned cells are not replaced by assertion-store vocabulary. The degraded
Bill-metadata path has a regression proving no guessed identity/read occurs.

## Reproduction

```sh
NLQ_LLM_API_KEY='' .venv/bin/python -m pytest -q tests
.venv/bin/python tests/validate.py
NLQ_LLM_API_KEY='' .venv/bin/python tools/verify_research_v06_ui.py \
  --output /tmp/oireachtasontology/research-direct-results/legacy-ui-controls
NLQ_LLM_API_KEY='' .venv/bin/python -m pytest -q \
  tests/test_research_direct_results.py \
  tests/test_research_direct_results_browser.py \
  tests/test_research_general_queries.py tests/test_research_evidence_handoff.py \
  tests/test_research_v05.py tests/test_query_evidence_interoperability.py

# Uses configured model/read-only Fuseki; outputs actual run archives and drafts:
.venv/bin/python tools/verify_research_general_queries.py \
  --output /tmp/oireachtasontology/research-direct-results/reproduction \
  --cases o-kildare-north p-wexford q-donegal

# Same service consumer, direct exact subsidiary questions, no report-author call:
.venv/bin/python tools/verify_research_general_queries.py \
  --output /tmp/oireachtasontology/research-direct-results/direct-reproduction \
  --questions 'When did each Dáil start and finish?' \
  'How many Dáil terms are listed in the Houses data?' \
  'Which Fianna Fáil TDs represent Kildare North?'
```

## Remaining boundaries

No guarantee of arbitrary wording admission, complete research decomposition,
exhaustive source coverage, dataset snapshot consistency or correctness of free
LLM prose is made. Older-term constituency geography is not inferred. Some
Boolean questions lack the required live owner/evidence records. The prototype
remains in-memory, local/single-worker and draft-only. Failed report writing
cannot remove already returned answers. Human review, not merge into master,
is the next step.
