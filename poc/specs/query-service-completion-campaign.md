# Query Service — Remaining Questions Completion Campaign

**Status:** Approved execution plan; one OpenCode campaign, three autonomous internal stages, one normal human acceptance/integration gate.
**Repository:** stephenrigney/OireachtasOntology.
**Baseline:** Version-2 composable Query Service with Q06, Q09, Q23, Q28, Q29 and Q35 integrated on master. The remaining inventory is **32 numbered questions plus T01**.
**Execution:** Sol orchestrator with bounded Luna High implementation executors, operating on a dedicated campaign branch. No automatic merge to master.

## Objective and authority

Deliver correct, user-readable version-2 /ask behaviour for the remaining approved question cases, using only evidence and relationships the repository actually supports. Implement executable queries where reviewed RDF permits; identify precise, truthful unavailable outcomes where it does not. Preserve the six existing slices and their regressions. The objective is Query Service capability, **not** historical corpus completeness.

Read rather than reproduce these authorities:

1. [Approved question catalogue](query-service-questions-approved.md) — exact Q01–Q37, Q24A and T01 answer requirements and individual decisions.
2. [Query-plan requirements](query-plan-redesign-requirements.md) and [design](query-plan-redesign-design.md) — typed referents, time, identity, joins, projection and safeguards. Apply subsequent accepted implementation decisions where the design's earlier illustrative/general compiler ideas differ from the already integrated bounded compiler architecture.
3. [Composable plan contract](composable-query-plan-contract.json), [plan schema](composable-query-plan.schema.json), [query schema/ownership contract](query-schema-contract.json), and source-backed ontology, ETL mappings and tests — what is actually emitted, queryable and safe.
4. Existing working code under poc/nlq/ and the focused Q06/Q09/Q23/Q28–Q29/Q35 tests — regression baseline. Relevant source documentation supplies evidence, not permission to infer missing facts.

The approved question catalogue defines the desired meaning. RDF/mapping contracts and preserved source evidence determine what can be answered now. A mismatch is not permission to invent a predicate, resource, identity, datum or semantic shortcut.

## Scope: three autonomous stages

The stages allocate every outstanding question **once**. The orchestrator may reorder independent internal slices within a stage to maximise reuse. Do not require ChatGPT approval between stages.

| Stage | Question IDs | Count | Capability and intended outcome |
| --- | --- | ---: | --- |
| **A — People and parliamentary membership** | Q01–Q05, Q07–Q08, Q10–Q11, Q13, Q15, Q32–Q34; T01 | 14 + T01 | Qualified/ambiguous Member resolution; dated Dáil and Seanad service, durations with gaps, current party/Independent distinctions, Seanad entry route, committee membership, House term dates and counts. Build on Q06/Q09. |
| **B — Bills, offices and remaining committee questions** | Q12, Q14, Q18–Q22, Q24A, Q25–Q27 | 11 | Bill identity, status/history and reverse sponsorship, source-backed Bill retrieval, office point/interval/current queries, committee chair/identity outcomes. Reuse Q23/Q35 and Stage A. |
| **C — Coverage-dependent questions and diagnostics** | Q16, Q17, Q24, Q30, Q31, Q36–Q37 | 7 | Seat complement, recognised groups, quarantined Bill, missing Debate date, PAC/HSE latest-hearing evidence, Bill-linked voting and transcript retrieval. Implement supported capability and specific truthful diagnostics; do not manufacture unsupported answers. |

**Stage A exit:** Each assigned question and T01 has a tested /ask route with approved semantics, or an explicit, evidence-grounded blocker. Include Member ambiguity, distinct-identity counting, as-of handling, gaps and differing Seanad entry routes in fixtures; pass existing-slice regressions.

**Stage B exit:** Each assigned question has a tested route or evidence-grounded blocker; reuse reviewed Bill and office patterns, preserve optional primary-sponsor status, do not infer missing officeholders/chairs, and distinguish Bill lookup failure from missing source records. Pass Stages A and baseline regressions.

**Stage C exit:** Each assigned question has a tested supported path or a specific, honest unsupported/coverage outcome. Do not count replacement Members as seats (Q16), parties as recognised groups (Q17), incomplete corpus coverage as proof of latest (Q30), sponsorship as voting (Q36), or Debate metadata as speech content (Q37). Pass prior-stage regressions.

The question IDs are **acceptance cases**, not instructions to add one hardcoded parser/query per question. Generalise only when implementation evidence warrants it. Reuse the existing bounded typed-plan, resolver, reviewed-mapping compiler, read-only SPARQL and /ask patterns. Do not launch a speculative general-purpose compiler rewrite.

## Orchestration and autonomy

- One Sol orchestration session owns the campaign, its sequencing, checkpoint commits, test evidence and final report. Delegate bounded coding/testing tasks to Luna High executors. Prefer a single writer for shared files such as composable_plan.py, plan schemas/contracts and the /ask renderer; parallelise only genuinely independent work.
- Start a dedicated campaign branch from up-to-date master in a clean worktree. Make small, self-contained commits at working internal slice boundaries; verify before advancing. Push recoverable campaign checkpoints, **not** master. Short-lived executor branches/worktrees should be integrated into the campaign branch and retired when safe.
- Sol may fix routine implementation defects, choose the order of independent slices, add focused fixtures, make narrowly justified contract extensions and run tests without another human gate. Preserve reviewed source ownership, provenance, source-safe behaviour, deterministic compilation and fail-closed validation.
- An implementation that cannot produce a real-data answer because the local dataset is incomplete is not automatically a software failure. Likewise, merely returning a generic “unavailable” response for an executable approved question is not implementation success. Distinguish the two with a tested contract and specific reason.
- Do not absorb corpus ingestion, historical data reconciliation, ontology redesign, production deployment, new vote/transcript retrieval infrastructure or unrelated workstreams. If a genuinely missing authoritative fact blocks a question, record the dependency and continue independent questions.
- Use the existing safety restrictions: read-only queries, approved named-graph ownership and predicate allowlists, bounded result sizes, exact/set-valued identity resolution, injectable as-of dates, and explicit coverage qualifications. Never claim a current/latest/negative historical result without sufficient source coverage.

## Evidence, verification and recovery

After each bounded internal slice: run relevant focused tests, contract/mapping validation, safety checks and previously affected regression cases. Before completing each stage, run the applicable combined regression set. At campaign end, run the relevant full available test suite once, unless a concrete environmental/resource blocker prevents it; record the precise commands, results and omissions. Avoid repeated corpus scans, production-grade acceptance, graph publication and changes to preserved/nonproduction snapshots.

Use small synthetic RDF fixtures to establish semantics and safe compilation. Reuse existing preserved source-backed local evidence when available and relevant, **without mutating or rebuilding it**. Do not present fixture coverage as proof of historical completeness. Preserve finite dates versus open ends, current/previous as-of meaning, missing optional evidence and conflict diagnostics.

Maintain a concise, mutable checkpoint report at **documentation/query-service-completion-progress.md** (create it when execution begins), containing:

- Current campaign branch/head, last tested checkpoint SHA and next intended internal slice.
- Question matrix for the 32 IDs plus T01: implemented output, fixture tests, source-backed evidence where available, specific data limitations, or blocking decision.
- Per-stage test commands/results, known regressions, incomplete evidence and work left to perform.

Use separate dimensions for **behaviour** (implemented / specifically unavailable / blocked / not implemented) and **evidence** (synthetic fixture / source-backed local / insufficient / not checked). A specifically unavailable result may satisfy a question's current diagnostic behaviour, but **must not** be described as actual vote, transcript, current-office or complete-history retrieval. Reconcile this record with Git commits/tests before resuming a restarted session. Do not modify the approved question catalogue merely to make a test pass.

## Escalation and stop conditions

Proceed autonomously through mechanical issues, mapping/fixture omissions that can be resolved from already reviewed authority, and independent remaining questions. Escalate to the human **only** for:

- Contradictory or absent semantic/identity authority requiring a new decision;
- A proposed ontology/source ownership or acceptance-meaning change;
- Unsafe, irreversible, production-affecting, or unrelated data operations;
- A material architecture change beyond the bounded model, supported by concrete evidence that no smaller remedy works.

If such a blocker affects only one question, mark that question blocked and continue unaffected work; do not hold the entire campaign hostage. If a blocker threatens shared correctness or prevents safe further work, stop and report exact evidence and options. Do not silently weaken a test, change a user-approved answer, or mark a blocker complete.

## Campaign completion and human gate

Stop before merging to master. Deliver an **integration-ready** campaign branch with working tree clean, small reviewable commits, stage checkpoint evidence and one consolidated report. Include:

1. All 32 outstanding IDs plus T01, with per-question implemented/diagnostic/blocked status and exact evidence level.
2. Answer examples for implemented families; unsupported results with precise reasons, not guesses.
3. Verification commands and counts, regressions, any incomplete tests, and any deviations from the approved plan.
4. Existing six integrated questions' regression status and the final campaign commit SHA.
5. Residual data/retrieval dependencies handed back to their own owners, not silently treated as delivered features.

**Only normal human gate:** ChatGPT reviews the consolidated evidence and decides acceptance/integration. If some cases remain legitimately blocked by missing source authority/data, report them explicitly and propose a bounded carry-forward; do not pursue indefinite perfection. No campaign merge or force-push without that approval.
