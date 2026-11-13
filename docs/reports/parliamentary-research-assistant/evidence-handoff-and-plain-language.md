# Parliamentary Research Assistant — Reliable Evidence Handoff and Plain-Language Outcomes

**13 November 2026 · `parliamentary-research-assistant` · human review required**

## Implemented boundary

Query Service executors can now issue typed `validated_facts` while validating
their source evidence, before rendering. The shared `finalize_evidence` boundary
automatically binds these propositions to the existing v1 accepted-evidence
envelope: exact plan, answer query and result digest. It also checks existing
direct envelopes and preserves the reviewed legacy projections. Research
consumption, assertion wrapping, compact tables, inspection and export remain
generic. No Research Assistant capability adapter or second trust catalogue was
added; readable rows and model prose cannot issue established facts.

The **handoff is default; semantic coverage is conditional**. An executor must
issue validated propositions, an existing accepted envelope, or a reviewed legacy
payload. Other operations still need service-owned semantic projections; safe
execution alone is not factual acceptance. `factual_evidence_status` records
available/unavailable/invalid/not-applicable separately from execution success.
An optional service-owned selection assessment records matches/no-matches;
research does not infer a negative finding from missing evidence or scalar rows.

Two existing operations exercise the same new path:

- **Current committee membership:** exact Member/Committee identities, three
  independent intervals (membership, committee owner, House term), reporting date,
  raw membership/owner witnesses and source graphs. Separate episodes remain
  separate. Neither a complete roster, chairmanship nor attendance is inferred.
- **Independent generalisation — full Dáil chronology:** recorded House-owned
  term dates, exact term identities and source witnesses. Unexposed period
  identities remain null. Missing finishes stay missing; term dates are not
  sitting dates or certification of a complete history.

## Outcome and language policy

Structured research outcomes distinguish accepted findings, a completed result
not incorporated into the report, unsupported questions, valid no-match
selections, ambiguity/unresolved identity, incomplete evidence and failures.
Partial investigations retain findings prominently and leave outstanding
requirements visible. Search status and report-writing interruptions are also
separate: earlier findings survive an unsuccessful update.

Controlled descriptions replace diagnostic strings in progress, limitations and
no-evidence final responses. Authors receive those outcomes, not raw technical
causes; grounded clarification candidates remain available. A language check
rejects known implementation jargon in model-authored plans, prose, captions,
unanswered summaries and replies. This supplements—not substitutes for—the
existing evidence-linked assertion controls. Exact diagnostics, failed queries,
returned results and proposals remain inspectable, with credentials redacted.

| Situation | Before | After |
|---|---|---|
| Validated retrieval without accepted handoff | “The Query Service's evidence shape is not supported by its structured factual boundary… no research fact was promoted.” | “Relevant records were found, but the application couldn't include them in this report. This does not mean that no records exist.” |
| Unsupported historical question | Technical refusal could enter limitations unchanged | “I couldn't establish this from the available queries. This does not show that no such parliamentary records exist.” |
| Execution failure | Failure detail could become a generic unsuccessful outcome | “The search couldn't be completed. No findings were established by this search.” |
| Valid empty selection | Could be confused with missing accepted evidence | “No matching records were found in the available data. The data may be incomplete.” |
| Completed result without a service assessment that records matched | Could incorrectly say “Records found” | “Search completed — result not included”; no claim that records matched. |
| Useful partial report | “Completed with limitations” / every finished section “Incomplete” | “Findings available — some questions unanswered”; useful sections “Findings available” |

Reports no longer begin with the static “About this draft” disclaimer. Useful
findings come before table qualifications; generic source qualifications appear
once in the report rather than before every shared table. Empty sections and
empty unanswered headings are omitted. Duplicate system notices/replies are
suppressed. Exact per-fact qualifications remain in inspection and export.
The workspace/navigation/visual identity and LLM report authorship are unchanged.

## Genuine generated excerpts

From the fresh browser committee report:

> As of 13 November 2026, the available records identify the people listed below
> as members of the Committee of Public Accounts. This is a record-based list,
> not a certified complete roster; source freshness is unknown.

Its compact Member/Reporting date table includes **Aidan Farrelly, Albert Dolan,
Cathy Bennett** and the other accepted individual findings, each with a source
link. The 13 accepted findings are not described as a certified complete roster.

From the independent chronology report:

> The House-owned records give start and end dates for the 1st to 33rd Dáileanna.
> The 34th Dáil is recorded as starting on 29 November 2024, with no end date
> recorded. These are term dates, not a record of actual sittings…

From the retained Donnelly regression:

> The records identify membership episodes with the Social Democrats and Fianna
> Fáil. They report each episode separately; the recorded dates do not establish
> continuous membership or prove non-membership during gaps.

These explanations remain model-authored, provisional synthesis. The linked
table cells and exact facts retain Query Service authority. Full genuine outputs,
not edited examples, are indexed in [the execution archive](evidence-handoff-executions/README.md).

## Verification

Fresh configured-model/read-only Fuseki observations (`gpt-6-luna`, reporting date
13 November 2026), separate from injected controls:

| Case | Observed result |
|---|---|
| A: exact current committee question | 13 accepted membership episodes, readable Member names, seven actual reads, authored report and inspectable evidence. |
| B: exact committee-history question | Historical retrieval unsupported. An initial run obtained no facts; another legitimately added current-membership supporting evidence while leaving history unanswered. Neither establishes absence of earlier members. |
| C: Donnelly parties “and when?” | Four accepted separate episodes, two reads; exact recorded dates and gaps retained. |
| D: independently selected chronology | 34 accepted term-date findings, one read; identical generic consumer/table/export path. |
| Partial current/history brief | 13 accepted current findings shown, historical changes since 2020 explicitly unanswered. |
| E: multi-domain current membership plus housing speeches | Fresh browser run: 13 accepted membership findings first; speech-content and attempted supporting debate retrieval refused and explicitly unanswered. No quotations or inferred remarks. |
| Malcolm Byrne Bills and revision | 130 accepted facts, 22 reads. Revision reduced the overview from 94 to 60 words; facts and tables stayed exactly equal, with no extra reads. Final outcomes stayed unanswered. |

Browser checks cover visible plans before dispatch, readable findings, source and
exact query inspection, qualified export and 390px containment, with no JavaScript
errors. Separate injected-model/real-compiler controls exercise all seven
outcome paths, including the removed handoff, transport failure, actual dated
scalar-zero selection and ambiguous identity. The existing responsive/browser
regression suite also passes: 1440/1024/768/390/320px, focus, section revision,
source inspection, interruption/retry, pause/resume and preservation of findings.

An ordinary chronology paraphrase (“Please list the Dáil terms with their recorded
start and end dates”) was refused by existing selection. Its full genuine output
is retained. The originally frozen fixture formulation succeeds in a separate
fresh browser run. No compiler expansion or question-specific bypass was added.

Independent bounded review found no remaining blocking issue;
its name/abbreviation false-positive and zero-count outcome concerns were fixed
with explicit tests and executor-owned selection metadata.

- Ontology validation passed: **2,586 triples; HermiT executed successfully**.
- Final focused compiler/research tests: **319 passed**.
- Final broader check, `NLQ_LLM_API_KEY='' .venv/bin/python -m pytest tests -q`:
  **2,625 passed, 26 skipped, 23 subtests passed** (12m21s). Skips and dependency
  deprecation warnings are not passes. This ran after the final integrated code
  change; `.venv/bin/python tests/validate.py` then passed again.
- Python/JavaScript syntax, retained JSON parsing, whitespace and exact configured
  credential-value scans passed. No fixture or acceptance rule was weakened.
- The configured-environment broad run exposed one existing Finance-only refusal
  test/environment conflict: local model configuration enables office discovery,
  while that test expects no reads. The same isolated test fails with the unchanged
  `9148002` compiler and passes with `NLQ_LLM_API_KEY=''`. No test or office-query
  rule was altered. The final deterministic full-suite run disabled model access;
  actual configured-model/Fuseki observations above are separate and retained.
  That broad run recorded **2,624 passed, one failed, 26 skipped and 23 subtests
  passed**. The isolated current/baseline/hermetic outputs are retained in the
  execution archive; the complete hermetic run above passed all tests.

## Remaining limits and human gate

Coverage is not universal: office-window, shared-term, service-duration and other
unconverted operations still require service-owned propositions where their
semantics warrant them. No consumer may repair that gap from arbitrary rows.
Source freshness, full roster/history coverage and common observation time are
not certified. Unsupported historical/content/combined relationships remain
unanswered; model-planned supporting retrieval does not resolve them by itself.

LLM explanatory prose and overall investigation adequacy still require researcher
review. The language check covers known technical terminology, not a universal
editorial or semantic proof. The model can choose different supporting searches,
repeat a qualification, or organise prose imperfectly; retained observations are
finite evidence, not broad product certification.

No ontology, mapping, ETL, source/golden fixture, dataset, graph ownership or
read-only safety policy was changed. No new SPARQL authority or orchestration
layer was introduced. **Stop for human review; do not merge to `master`.**
