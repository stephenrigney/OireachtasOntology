# Parliamentary Research Assistant — General evidence interoperability

**13 November 2026 · `parliamentary-research-assistant` · implemented; human review required**

## Shared boundary

The Query Service now issues `PlanOutcome.factual_evidence` under the versioned
[accepted-evidence contract](../../specifications/query-service-evidence.md).
Typed entity, relationship, episode and measure variants preserve exact
identities/participant roles, predicates, operation scope, separate temporal
intervals, source witnesses and qualifications. Missing dates, recorded ends and
accepted open ends remain distinguishable. Approved measures retain their unit,
method and distinct input identities. The resolved plan, actual answer query and
result digest bind each envelope to its service outcome.

This is **executor-issued factual authority**, not schema-valid model JSON.
Readable rows, captions, tables and LLM prose cannot issue propositions.
Successful execution without a supported projection remains inspectable but
cannot authorise research findings. Unknown/invalid shapes fail closed.

`research_evidence` now validates one shared contract rather than interpreting
families. `research_assertions` wraps its propositions unchanged as Level 1 or
approved measures as Level 2. Actual query references, source completeness and
unknown freshness survive. Supporting retrieval still does not establish the
parent requirement; Levels 3–4 retain their existing provisional authority.

The LLM chooses report sections, explanatory emphasis, selected facts and compact
`records` table columns from compiler-owned fields. It cannot supply factual cell
values/headings, calculate new totals or join records. Full propositions remain
available per finding; qualifications need not be repeated in every cell. Existing
Bill/representation views remain compatible, but are not required for new shapes.
This is not deterministic report-template authorship or a new research catalogue.

## Code and projection coverage

- `query_evidence.py`: strict discriminated contract and service-side projections.
- `composable_plan.py`: shared result boundary and validated party-episode
  projection; history reads additionally retain exact source structural bindings.
- `representation.py`: current-point accepted payload additionally retains the
  validated membership interval, rather than losing it at display projection.
- `stage_a.py`: independently selected House-calendar holdout projection.
- `composable_semantic_planner.py`: capability guidance now explains that party
  history already returns episode dates; showing those dates is not a new date
  filter. No name-specific/phrase-specific recogniser or validation relaxation.
- `research_evidence.py`, `research_assertions.py`, `research_tools.py`: reusable
  validation, assertion wrapping and traced consumption; legacy batches preserved.
- `research_presentation.py`, `research_collaborator.py`: generic column selection
  and LLM author guidance; `research_app.py` exposes the schema; the existing
  evidence inspector adds a generic selected-proposition disclosure.

Supported shapes demonstrated: historical party episodes (including synthetic
missing-date/conflict controls), current Dáil party-Member relationships and
approved identity counts, constituency relationships/current-point episodes,
sponsorship, approved Bill cardinality, recorded lifecycle status/activities,
and House-calendar entity selections. New factual projection work is entirely
**Query Service-side**. The Research Assistant has no new family adapter for
party history or the holdout. Retained legacy-session assertions remain readable.

## Actual research observations

Full proposed plans, compiler operations, accepted evidence and generated reports
are in the [execution index](general-evidence-executions/README.md). Requested
configured model: **`gpt-6-luna`**; reporting date: **13 November 2026**.

| Case | Actual result, not source-wide certification |
|---|---|
| Donnelly timing question | One query/two reads; four Level 1 episode findings for Social Democrats and Fianna Fáil. The ordinary “and when?” request no longer hits the former unsupported-date-projection refusal. |
| Labour, then Fine Gael | Eleven Labour and 38 additional Fine Gael Member identities, each with accepted separate parliamentary/party intervals containing the reporting date; four reads per selection. Compact Member/Party/Date tables, not long assertion-sentence tables. Earlier facts/sections were preserved; no complete-roster or total comparison claim. |
| Multi-domain formulation F | Partial: four party facts/two reads; constituency proposals were rejected by the existing semantic-selection boundary. Some history proposals also hit present-scope refusals before a career-wide proposal succeeded. These are planner refusals, **not** source-data-absence findings or failed generic evidence consumption. All seven attempts remain archived. |
| Final mixed brief | Two supported relationships in one brief, six reads, five accepted facts: Donnelly episodes plus Mary Lou McDonald representing Dublin Central in the 34th Dáil on the reporting date. No inferred party/representation temporal join. |
| Independent holdout | Independently selected **House-term calendar selection** after the shared mechanism existed. One read, one Level 1 entity finding: 27th Dáil overlaps June 1994. Same consumer/report/inspection/export path, with no Research Assistant adapter; only a small service projector using already validated House-owned dates. Not proof of an actual sitting. |
| R1 Bill regression | 20 sponsored Bills, 129 direct propositions and the approved distinct-Bill count, through 22 reads. Authored sponsorship and recorded-status tables plus selected dated developments. Final-outcome retrieval refused and remained unanswered. Revision reduced relevant prose **218 → 141 words (35%)**; all 130 facts and both tables stayed exactly unchanged, with no extra reads. |
| Final exact-Bill smoke | Corrected nullable activity identities verified in fresh execution. Two reads repeated the same seven accepted status/activity observations (14 registry entries, not 14 distinct facts). The author selected six dated observations in a compact Bill/Activity/Date table. Subject-content and sponsor investigations hit selection/refusal limitations and remained unanswered; these are not evidence of source absence. |
| Unsupported speech quotation | Exact question reached admission; zero reads, zero facts, no invented quotation or weaker metadata substitute. The unsupported substantive question remains visible. |

The final fresh **browser** run used the ordinary history paraphrase, then added
Mary Lou McDonald's current constituency. Four episode facts plus one current
representation fact, six reads overall; earlier facts/sections stayed unchanged.
Plan-before-dispatch, exact assertion/interval inspection, query inspection,
qualified Markdown and 390px page containment were observed; no JavaScript errors.
[Screenshots](general-evidence-executions/final-browser/) are from actual fresh
model/Fuseki browser execution, not screenshots of canned/replayed reports.

### Actual generated writing and cells

From the final browser report (model-authored synthesis remains provisional):

> The records identify membership episodes under the Social Democrats and Fianna
> Fáil. They are separate recorded episodes, not a certified complete history:
> gaps do not establish periods of non-membership, and the recorded end dates do
> not establish current membership.

Its table uses concise accepted cells with individual evidence links:

| Party | Recorded start | Recorded end |
|---|---|---|
| Social Democrats | 15 July 2015 | 9 March 2016 |
| Social Democrats | 10 March 2016 | 4 September 2016 |
| Fianna Fáil | 2 February 2017 | 14 January 2020 |
| Fianna Fáil | 8 February 2020 | 8 November 2024 |

From the Labour report:

> The available records identify the Members in the table as Labour Party TDs on
> 13 November 2026. This is a locally recorded list, not a certified exhaustive
> roster; the records’ freshness is also unknown.

R1's authored discussion separately describes the recorded Lapsed event and
later Committee Stage for **Seanad Electoral (University Members) (Amendment)
Bill 2020**, without inventing an explanation for their coexistence with Current
status. The holdout instead needed only a short exact factual answer. These are
different report forms using the same evidence store, not per-capability authors.

## Verification and review

- Focused new-contract/general/R1 assertion tests: **70 passed**. Controls include
  unknown versions/shapes, missing execution, exact-query binding, source episode
  conflicts, missing/reversed dates, both current intervals, count/list identity
  parity, incompatible columns, successful-but-unprojected chronology retrieval,
  and refusal of additional date/office filters.
- Ontology validation: **2,586 triples; HermiT executed successfully**.
- Injected-model/exact compiler-replay v0.6 browser controls pass at
  1440/1024/768/390/320px, including revision, plan-before-dispatch, focus/evidence,
  failure retention, retry/pause, export and stable reading position. These are
  explicitly separate from genuine executions.
- Independent bounded review found no blocking authority violation. Its exact
  query matching, consistent open-end terminology, ignored-column rejection and
  current-representation coverage recommendations were implemented and tested.
- Repository suite: **2,595 passed, 26 skipped, 23 subtests passed** in 10m35s;
  warnings/skips are not passes. This preceded the final nullable lifecycle
  activity-identity correction and one added successful-unprojected-result control;
  the final **256-test verification tail passed**, covering all research suites,
  shared-contract controls, party history, House selection and Stage B, including
  those changes.
- Syntax, retained JSON parsing, staged whitespace and credential-value scans
  pass. No test, fixture or acceptance rule was weakened.

## Remaining limits and human gate

This demonstrates **bounded generalisation, not universal interoperability**.
Other successful compiler families without a service projector—such as generic
office-window, Committee roster, shared-term, full House chronology and service-duration results—remain
unavailable for established research assertions. Source absence is never repaired
from model memory; unknown freshness/common snapshots remain unknown.

Legacy Bill lifecycle evidence exposes activity type/date observations, not exact
individual activity resource identities. The shared contract now records those
unprojected identities as null rather than substituting the Bill IRI. The root
R1 archives predate that correction (rendered assertions/tables unaffected); a
final fresh exact-Bill research smoke and the final 256-test tail verify it.
The execution index records the distinct compiler content identities.

Semantic-selection reliability is still imperfect, as formulation F demonstrates.
The correction to party-history guidance is not a claim of arbitrary paraphrase
understanding. The model can still repeat limitations, choose a nonchronological
row order or produce provisional quantitative/descriptive synthesis that is not
an approved calculation. Such prose is not upgraded to Level 1/2; human editorial
review remains necessary. Known final legislative outcomes, continuous career
history, causal explanations and source-wide completeness remain unestablished.

No ontology, ETL, dataset, source/golden fixture, query semantics or read-only
safety policy was changed. No UI redesign, unrestricted SPARQL, external evidence
source or new orchestration framework was introduced.

**Stop for human review.** Assess whether the shared evidence and composition
mechanism generalises usefully and honestly; automated integration and these
finite generated samples do not constitute human product acceptance. Do not
merge to `master`.
