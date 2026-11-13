# Parliamentary Research Assistant — Lessons Learned from the Early Tranches

**Date:** 13 November 2026  
**Repository/branch:** `stephenrigney/OireachtasOntology` / `parliamentary-research-assistant`  
**Status:** Retrospective findings and input to a further specification review; **not** an amendment to the approved contracts or a claim of product acceptance.

## Executive conclusion

The Research Assistant was intended to be an **LLM-led parliamentary research collaborator**: understand an objective, devise subsidiary investigations, use the existing Query Service, draw together findings and produce a readable draft for human review. The implementation has not yet reliably met that goal.

An important cause was **over-specification of the research and reporting controls**, followed by implementation choices that compounded their effects. The specifications delegated research and writing to the LLM but simultaneously mandated detailed assertion classification, evidence approval, dependency tracking and confidence assessments. These requirements created friction between an answer that the Query Service could return and an answer that the Research Assistant was permitted to report.

The subsequent correction allowing successful Query Service results to be reported directly fixed a demonstrable integration failure. It did **not** by itself fix weak multi-step investigations, mistaken draft comparisons or poor presentation. We should now evaluate the assistant primarily as a *research product*, while retaining the Query Service's independent query-safety and semantic authority.

## 1. Intended service and what was actually specified

The original product objectives were sound: natural-language research, useful subsidiary questions, progressive reports, follow-up dialogue, source inspection, honest partial answers and human-reviewed drafts. The [product specification](../../specifications/parliamentary-research-assistant.md) expressly rejects a fixed report template and assigns report structure and explanatory writing to the LLM (§§1, 2 and 7.1).

But the same specification contained substantial prescribed machinery:

| Specification stage | Explicit requirement | Lesson |
|---|---|---|
| Phase 1 | Closed, narrow operations and a substantially deterministic comparison/report flow | Proved guarded execution and interaction mechanics, not broad research usefulness; the fixed party-comparison product was rejected |
| v0.4 | Distinguish a useful supporting query from complete satisfaction of the user's brief | **Retain the distinction.** It need not prevent showing the supporting answer |
| v0.5 | Four assertion classes; compiler-authorised direct facts; approved deterministic derivations; provisional interpretation confidence; an assertion/evidence store with dependencies and review states | These were **design requirements**, not merely OpenCode inventions. Their operational cost and value were not established before adoption |
| v0.6 | A writing-first, single-column experience while retaining v0.5 research authority and evidence controls | Improved the interaction design but did not resolve the underlying research/reporting tension |
| 13 November direct-result decision | Successful validated Query Service answers reportable irrespective of optional `factual_evidence` | Corrected the most obvious reporting veto, but left older machinery and some contradictory historical wording in the contracts |

In particular, the earlier §12.4 evidence rule said that successfully returned rows lacking recognised research evidence could be inspected but not used as factual authority. The §12.5 claim store and the [acceptance contract](../../specifications/parliamentary-research-assistant-acceptance.md) (§3A) required assertion-level classification and checks. Those choices explain why the first generic Query Service integration did not translate into generic *reporting*.

The editorial specification, by contrast, already required readable findings first, intelligible tables, non-technical language and useful partial reports ([editorial contract](../../specifications/parliamentary-research-assistant-editorial.md), §§2 and 4). Poor presentation was therefore **contrary to**, rather than demanded by, the editorial design.

## 2. Observed failures and corrections

The following cases are from recorded implementation runs or human testing; they are not estimates of general error frequency.

| Observation | What it demonstrates | Present status |
|---|---|---|
| Phase 1 party-count prototype | Technically correct deterministic integration did not constitute a convincing research collaborator | Superseded by LLM-led planning/authorship |
| Committee of Public Accounts and historical Wexford investigations | Query Service results could be retrieved but excluded from the report because their optional structured evidence was not recognised | Evidence handoff was improved; later direct-result reporting removed the mandatory projection gate |
| Kildare North, 33rd and 34th Dáileanna | The assistant formulated two appropriate term-specific questions, but originally withheld successful Member selections | Corrected and demonstrated with live results after the direct-result change |
| Donegal across five Dáileanna | The assistant could return some findings yet struggled with subsidiary-question formulation, historical scope and complete comparison | Still only partial; some Query Service selection limitations belong in the separate compiler workstream |
| Dublin Central, 30th–32nd Dáileanna | Human testing still yielded an unexplained failure rather than useful research | Not yet causally diagnosed from an execution archive |
| Wexford report display | A correct finding was accompanied by huge Member identifiers and concatenated technical evidence in the principal table | Presentation defect remains |
| Donegal draft comparisons | Model prose miscounted affiliation groups and incorrectly interpreted a Member's presence across returned lists | **Demonstrated** synthesis-error risk; original result tables remained intact |
| Processing and failure messages | “Populating”, “Search interrupted” and prominent internal stage histories made it difficult to distinguish work, failure and completion | Progress visibility improved, but user-facing explanation and stage-history placement still need work |

See [Phase 1 verification](phase-1-vertical-slice.md), [v0.5 implementation](v05-implementation.md), [evidence handoff review](evidence-handoff-and-plain-language.md), and [master integration/direct-results report](master-direct-results-20261113.md).

The direct-results integration at commit `01a3580d` demonstrated that **Kildare North and Wexford answers could be presented without optional factual projections**, with exact values and inspection retained. It also reported **2,831 passing tests**, which are evidence of technical regression coverage, **not** a substitute for human acceptance of research quality.

## 3. Design rigidity versus implementation defects

We should not attribute every shortcoming to the specifications or every shortcoming to the agent.

- **Specified rigidity:** Four evidence classes, confidence rubric, controlled assertion promotion, detailed requirement ledger, dependencies and review states. These made a relatively heavyweight research authority model normative for an early prototype.
- **Amplified by implementation:** Requiring recognised structured `factual_evidence` before displaying a successfully validated Query Service selection; elaborate structured author payloads; and presentation of raw query columns as the default main report table. The first item has since been corrected.
- **Failures not explained by the evidence gate:** Weak or repetitive subsidiary-question selection; inability to recover from some failed formulations; inaccurate comparisons in authored prose; misleading final statuses; and unreadable report tables. These need direct product investigation, not automatic expansion of compiler capabilities.

The specifications themselves contained countervailing instructions: they rejected universal semantic certification as a prerequisite for useful drafts, required independent assessment of research usefulness, and warned that a safe refusal did not count as product success. Those principles were not given enough practical weight.

## 4. Python-controlled content versus agent discretion

**Python is valuable for** session and tool execution, bounded resource use, recording exact Query Service responses, preserving original values/identities/scope, stable source references, report persistence/export and UI operation. Deterministic calculations can also be useful where they have a demonstrated purpose.

**Excessive Python control over report content** yields predictable structures and easier exact tests, but tends to duplicate the Query Service's authority, require additional plumbing as capabilities expand, constrain the agent's editorial choices and expose raw technical data in the report.

**Greater agent discretion** over question selection, investigation, synthesis and report organisation allows more useful and adaptable work across unfamiliar briefs. It also brings risks of incorrect counts, omitted records and unwarranted conclusions. The Donegal prose errors are **observed**, so should be measured and addressed. Their existence does not establish that an assertion-by-assertion certification framework is the right remedy.

For this stage, the proportionate distinction is:

- The **Query Service** controls the meaning, admissibility, execution and returned results of its queries.
- The **Research Assistant** chooses relevant queries and constructs a research **draft**, including appropriate comparisons and explanations.
- **Python/UI infrastructure** preserves the exact returns, makes them inspectable and supports reliable follow-up/revision.
- The **researcher** checks whether the draft addresses the brief and whether its interpretations are persuasive and accurate.

Presenting an unchanged, validated Query Service answer should not require another factual authorisation layer. Additional interpretation should be identifiable as the agent's account, not masquerade as a returned database fact.

## 5. Lessons for sequencing and acceptance

1. **Put usable research in front of a researcher earlier.** Verify multi-step research and document usefulness before elaborating evidence governance.
2. **Evaluate at the product level.** A passing compiler suite and successful browser controls do not establish that the assistant produces a useful or accurate report.
3. **Test ordinary research questions, not only demonstration-friendly operations.** Include multi-term comparisons, substantive follow-ups, partial results, and unfamiliar questions.
4. **Separate the three failure locations.** (a) Research Agent planning/decomposition; (b) Query Service admission/execution/coverage; (c) Research Agent use, comparison and presentation of returned results. Do not broaden compiler work in response to a reporting defect.
5. **Keep the result, make the report readable.** Source cells, RDF identifiers and diagnostic traces belong in inspection controls unless a specific technical field is substantively needed.
6. **Introduce controls in response to measured problems.** The demonstrated prose-comparison mistakes warrant testing and focused correction; hypothetical risks alone do not justify suppressing useful results.
7. **Preserve what worked.** Read-only guarded querying, exact result retention, source inspection, bounded operation budgets, visible progress, partial-answer handling and draft/human-review status have clear value.

## 6. Implications for the next specification revision

The next discussion should establish a **simpler, outcome-oriented Research Assistant contract**, rather than immediately commissioning another collection of incremental patches.

Proposed areas for review (not decisions enacted by this report):

- **Retain:** Research purpose and autonomy; Query Service authority; faithful source-result retention; material scope/uncertainty; human-reviewed draft status; accessible source inspection and follow-up.
- **Simplify or defer:** Mandatory four-level classification for all prose; subjective high/moderate/low confidence rubric; assertion-by-assertion certification and approval; intricate dependency/invalidation rules without a demonstrated user need.
- **Clarify:** The agent's discretion over reports and comparison; whether Python renders exact source tables as *optional detail* rather than default narrative; what useful partial research must look like.
- **Measure:** Quality of subsidiary questions, recovery after query refusal, inclusion of successful results, factual accuracy of comparisons, readability, and human-rated usefulness.
- **Keep workstreams separate:** Research Assistant behaviour is in scope here; new Query Service semantics remain the responsibility of its separate compiler workstream.

### Suggested product-level exit criteria

A researcher can give the assistant a realistic multi-part parliamentary brief and receive a coherent, readable draft that (1) makes effective use of successful Query Service results, (2) explains meaningful findings and genuine remaining gaps, (3) can be reviewed against the original returned sources, and (4) supports purposeful follow-up without losing existing work. Tests should include actual model/Fuseki runs and independent human review, with separate accounting for planning, retrieval and reporting errors.

**This retrospective does not authorise changes to compiler semantics or the current approved specifications.** It records why a specification simplification should be considered before further implementation.
