# Query Service Phase 2 — Realistic Benchmark

## Final follow-up run

The final measured run evaluates the bounded Phase 2 planner/resolver fixes
against the unchanged 37-case benchmark, with the same accepted, non-authoritative
development dataset and the retained Phase 1 comparison. No question, oracle,
coverage prerequisite, or acceptance criterion was changed.

- Run: `3b425bb9-c94e-4619-847a-8ed16fc1737a`
- Created: `2026-10-20T13:45:56.537012+00:00`
- Planner benchmark: `oireachtas-semantic-planner-realistic@1.0.0`, SHA-256
  `a97b94730f5fc9cd77939051827f34758052740378a78759e3928e862e077862`
- Source benchmark: `oireachtas-query-service-phase-2-realistic@1.0.0`, SHA-256
  `b6033abc421f443b0d93eafe31fcad818d5e518d384cace54dd45494a3554ad4`
- Result JSON: `/tmp/oireachtasontology/query-service-phase-2/realistic-phase2-final-result.json`,
  SHA-256 `a0fda272625fe7e53c7674b6c168e1bcb2c83f69e125d04aeaf2d44fd4ae33fa`
- Planner configuration: `gpt-6-luna`,
  `https://opencode.ai/inference/openai/v1`, 45-second timeout, 2,000 output
  tokens. The model came from repository dotenv; endpoint and limits used
  defaults.
- Query schema contract: `2.0.0`; query-plan contract: `1.2.0`.

**Outcome:** Phase 2 passed 32 cases, failed 2, and did not score 3. This is
16 more passes and 16 fewer failures than the original measured baseline below;
the 3 source-coverage exclusions are unchanged. All three expected fail-closed
cases passed, including Bill voting and Debate transcript requests. The
deterministic Phase 1 regression benchmark passed 10/10. On the 30 comparable
Phase 1 cases, Phase 1 passed 14 and failed 16; this measured LLM comparison is
nondeterministic and is not a byte-for-byte or latency gate.

The two remaining Phase 2 failures are:

- `aggregate.dail-term-count`: the planner claimed the supported count was not
  represented, then emitted a count answer without an aggregation, so draft
  validation rejected it.
- `debate.committee-sep24`: the plan returned a date fact, while the unchanged
  oracle requires the DebateRecord identity.

The three unscored cases still require data absent from this pinned slice: the
quarantined Committee and Bill, and a Dáil debate outside the selected Debate
slice. Benchmark artifact comparisons and detailed case outcomes remain in the
result JSON.

### Reproduction and timings

Two independent offline candidate builds reproduced dataset ID
`sha256:9da63abc5878387f991e4d4717f35cca67606850db34be589e0a8fc0cc1504e2`,
7,981 graphs, and 1,119,467 triples. Both candidates had the same N-Quads
SHA-256, `d30f6842a6cf9519c72e7cddfaa396080a3a3a1077a34407cdc14d98be3a4e38`,
and the same graph inventory and per-graph semantic hashes documented in the
baseline section. Each loaded dataset was independently verified in a fresh,
loopback-only disposable Fuseki instance; all 7,981 graph hashes matched on
readback.

| Setup phase | Run 1 | Run 2 |
|---|---:|---:|
| Offline candidate generation and validation | 1,178.550 s | 1,123.300 s |
| Disposable Fuseki startup | 4.071 s | 4.323 s |
| Empty-dataset check | 1.601 s | 1.530 s |
| Dataset-level N-Quads load | 31.205 s | 25.598 s |
| Post-load verification | 41.638 s | 42.143 s |
| **Total setup** | **1,257.064 s** | **1,196.894 s** |

The Phase 1 comparison was 14/30 passed and 16/30 failed (9 execution
failures, 6 semantic-result mismatches, and 1 interpretation failure). Across
the comparable cases, both phases passed 13; Phase 2 alone passed 15; Phase 1
alone passed 1; both failed 1. These counts are measured outcomes, not a
claim that Phase 1 behavior regressed.

The final run's large candidate/readback scratch files were redirected to the
ignored worktree `var/nlq-plan-benchmark/scratch` area because `/tmp` has a
6,266 MB per-user quota. The filesystem still had free space, but the earlier
candidate build hit the user quota while writing. This scratch relocation did
not change the benchmark, dataset, or query execution path.

During implementation, a benchmark invocation also exposed a missing
`_normalise_label` import in the set-valued scoring branch; the import and a
regression test were added. Intermediate measured run
`f0d3d990-2ee2-4f72-9022-e77cc3930691` scored 27/37 before the final
set-valued and unsupported-request fixes and is superseded by this run.

**Readiness at benchmark-run time (before the subsequent UI integration):** not
ready for UI integration. The browser remained on the Phase 1 path; the two
measured planner failures remained, and no approved browser interaction contract
existed for clarification, fail-closed, unresolved-entity, or plan-preview
outcomes. The later UI integration and final Phase 2 status are recorded below.

### Final verification

- `mise exec -- .venv/bin/python tests/validate.py` — passed; HermiT completed,
  ontology validation passed for 2,577 triples.
- `mise exec -- .venv/bin/python -m pytest tests` — 1,292 passed, 15 skipped.
- Focused query-plan/planner/compiler/benchmark tests — 274 passed.
- `git diff --check` — passed.

## Initial baseline run

### Scope and result

This measured run evaluated the accepted 37-case Phase 2 planner benchmark
against the retained Phase 1 direct-generation path on one reproduced,
non-authoritative development dataset. It did not start or integrate the browser
UI. The planner/compiler remained in the isolated benchmark path.

- Run: `d2f47864-4dc5-4ceb-b3ae-953174bc857b`
- Created: `2026-10-20T06:14:19.874171+00:00`
- Planner benchmark: `oireachtas-semantic-planner-realistic@1.0.0`, SHA-256
  `a97b94730f5fc9cd77939051827f34758052740378a78759e3928e862e077862`
- Source benchmark: `oireachtas-query-service-phase-2-realistic@1.0.0`, SHA-256
  `b6033abc421f443b0d93eafe31fcad818d5e518d384cace54dd45494a3554ad4`
- Result JSON SHA-256: `f32f98bad9b90f1739ea1bfdf6821ff6b3d911f5ed7bb2c7969993025280b7cd`
- Planner configuration: `gpt-6-luna`,
  `https://opencode.ai/inference/openai/v1`, 45-second timeout, 2,000 output
  tokens. The model came from repository dotenv; endpoint and limits used
  defaults.
- Query schema contract: `2.0.0`; query-plan contract: `1.1.0`.

**Outcome:** Phase 2 scored 16 passed, 18 failed, and 3 not scored across 37
cases. The separate deterministic Phase 1 regression suite passed 10/10. On the
30 cases with a matching Phase 1 question/result oracle, Phase 1 passed 19 and
failed 11. The Phase 2 planner therefore did not meet a readiness bar for UI
integration; detailed outcomes and differences follow.

### Dataset reproduction and load verification

Both independent offline candidate builds reproduced dataset ID
`sha256:9da63abc5878387f991e4d4717f35cca67606850db34be589e0a8fc0cc1504e2`,
7,981 named graphs, and 1,119,467 triples. Each candidate ran the pinned-source
checks, full per-resource Member/Bill RDF acceptance, accepted identity/count
guards, deterministic N-Quads serialization, and a full local syntax parse.
Candidate N-Quads were then POSTed once to a newly created, empty,
loopback-bound disposable Fuseki instance for each run.

| Evidence | Run 1 | Run 2 |
|---|---:|---:|
| Candidate N-Quads SHA-256 | `d30f6842a6cf9519c72e7cddfaa396080a3a3a1077a34407cdc14d98be3a4e38` | same |
| Candidate bytes | 315,198,979 | 315,198,979 |
| Graph IRI inventory SHA-256 | `d909a6756c83a855c0f00ae7da9fc58731e9feb60dbc19a63d7f48d88532ebd0` | same |
| Per-graph content inventory SHA-256 | `1af1489975268260e313e15b98d739e56f25005fa177315658e705d329d3e755` | same |
| Loaded graph hashes verified | 7,981 | 7,981 |
| Loaded triples | 1,119,467 | 1,119,467 |
| Setup time | 840.804 s | 855.650 s |

The dataset-level semantic readback matched every candidate graph under RDF 1.1
simple/`xsd:string` normalization. Each load also matched the exact graph
inventory and family/resource counts, verified nine representative typed
resources, and confirmed that quarantined Bill graphs `1959/P3`, `1965/P1`,
`1965/P3`, and `2024/48` were absent. Adding the three recorded unrelated
sentinel graph IRIs reproduced the accepted previous live inventory hash
`471532a10a3a6e8ecc307d78d6687a3e5abc89a2490eaa194d60d4e3fba2e117`.

Accepted RDF inventory by family:

| Family | Graphs | Triples |
|---|---:|---:|
| Houses | 1 | 721 |
| Parties | 1 | 1,890 |
| Constituencies | 1 | 7,645 |
| Committees | 1 | 2,799 |
| Administrative units | 1 | 2 |
| Offices | 1 | 13 |
| Members | 1,928 | 179,720 |
| Bill records | 6,044 | 917,294 |
| Debates | 3 | 9,383 |

Resource counts were 65 HouseTerms, 378 parties, 1,529 constituency/panel
identities, 267 committee identities, 1,928 Members, 3 offices, 1
administrative unit, 22 OfficeHoldings, 6,044 Bills, and 3 Debates. The dataset
remains a development/evaluation slice, not authoritative complete reference
closure.

### Timings

| Phase | Run 1 | Run 2 | Mean |
|---|---:|---:|---:|
| Offline candidate generation (including full Member/Bill validation) | 791.463 s | 806.541 s | 799.002 s |
| Disposable Fuseki startup | 2.051 s | 1.920 s | 1.986 s |
| Empty-dataset check | 1.175 s | 0.929 s | 1.052 s |
| Dataset-level N-Quads load | 17.560 s | 18.187 s | 17.873 s |
| Post-load inventory/resource verification | 28.555 s | 28.073 s | 28.314 s |
| Semantic dataset readback | 27.346 s | 26.700 s | 27.023 s |
| **Total setup** | **840.804 s** | **855.650 s** | **848.227 s** |

The combined evaluation window (deterministic regression, Phase 2 measured
cases, and Phase 1 comparison) was 823.866 seconds. The runner records this
combined wall time, not per-case or per-architecture latency, so no Phase 1 vs
Phase 2 latency or speedup claim is made.

### Outcomes and case differences

The Phase 2 result was 16/37 passed, 18/37 failed, and 3/37 not scored. Of the
16 passes, 14 reached query generation, SPARQL safety, Fuseki execution, and
semantic result scoring; one expected clarification and one expected
fail-closed outcome passed without executing a query. The 18 failures were
classified as 16 semantic-plan mismatches, one question-interpretation failure,
and one unsupported entity-resolution failure. The three unscored cases require
data absent from this pinned slice: the quarantined Committee and Bill, and a
Dáil debate outside the selected Debate slice.

Phase 1 comparison included 30 cases whose questions and result oracles matched
the Phase 2 cases. The seven exclusions were the three unavailable-source
cases, three unsupported-request cases for which Phase 1 has no equivalent
fail-closed contract, and one unresolved-entity case without a matching result
oracle. Phase 1's 11 failures comprised five LLM translation timeouts, five
semantic result mismatches, and one question-interpretation failure.

| Comparison outcome | Cases |
|---|---:|
| Both Phase 2 and Phase 1 passed | 11 |
| Phase 2 passed; Phase 1 failed | 4 |
| Phase 1 passed; Phase 2 failed | 8 |
| Both failed | 7 |

- **Both passed:** `member.count-micheal-terms`, `representation.timmy-panel`,
  `committee.timmy-transport`, `committee.count-timmy`,
  `aggregate.dail-term-count`, `aggregate.dail33-member-count`,
  `aggregate.dail34-collection-counts`, `bill.by-sponsor`,
  `office.named-holder`, `debate.dail-jul02`, `negative.ambiguous-michael`.
- **Phase 2 passed, Phase 1 failed:** `member.aengus-dail33`,
  `member.micheal-terms`, `collection.lowry-independent`,
  `office.member-holding-date`. Three Phase 1 failures were LLM timeouts; the
  remaining case returned zero rows against its oracle.
- **Phase 1 passed, Phase 2 failed:** `member.aengus-name`,
  `member.timmy-seanad-start`, `collection.aengus-sf`,
  `representation.aengus-constituency`, `committee.transport-code`,
  `bill.year-list-2024`, `bill.named-sponsor`, `office.finance-holder-date`.
  Phase 2 failures were planner semantic mismatches: answer-shape mismatches,
  missing collection-membership/temporal requirements, a clarification instead
  of a validated representation plan, missing Bill-title relations, unresolved
  sponsor resolution, and a wrong Member answer shape.
- **Both failed:** `collection.timmy-ff`, `bill.title-lookup`,
  `bill.current-from-year`, `bill.status-lookup`, `debate.seanad-jul02`,
  `debate.committee-sep24`, `negative.set-valued-michael`. Causes included
  Phase 1 timeouts or result mismatches and Phase 2 semantic-plan/entity
  resolution mismatches. In particular, Phase 2 has no deterministic local
  resolver for a DebateRecord entity, and the set-valued Michael Collins case
  did not preserve the expected Member mention.

The deterministic regression benchmark `oireachtas-local-nlq@0.3.0` passed
10/10 cases. These outcomes are retained as measured; no benchmark oracle or
acceptance criterion was changed to improve the score.

### UI readiness at initial baseline-run time

**Not ready for UI integration at this initial baseline; no UI integration had
been started.** The browser
application still uses the Phase 1 `ResponsesTranslator` / `process_question`
path. The Phase 2 structured planner and deterministic SPARQL generator are
exercised by the benchmark path only. The observed semantic-plan and entity
resolution failures need review, and there is no approved browser interaction
contract here for clarification, fail-closed, unresolved-entity, or plan-preview
outcomes. This benchmark establishes backend experimental evidence, not a UI
readiness or Phase 2 completion claim.

### Verification

`mise exec` was required to expose the pinned Java runtime in this environment:

- `mise exec -- .venv/bin/python tests/validate.py` — passed; HermiT completed,
  ontology validation passed for 2,577 triples.
- `mise exec -- .venv/bin/python -m pytest tests` — 1,270 passed, 15 skipped.
- Python compilation and `git diff --check` — passed.

## Phase 2 close-out after UI integration

Following the bounded planner fixes in commit `00c2d15` and the minimal UI
integration in commit `f8768ab`, Phase 2 is complete. The accepted structured
local-query path is:

```text
question → semantic planner → deterministic resolution → validated query plan
         → deterministic SPARQL → local Fuseki → rendered result
```

`POST /ask` defaults to this Phase 2 path in the development browser. The Phase 1
direct NL→SPARQL path remains available for comparison/debugging. The final
realistic result above remains **32 passed, 2 failed, 3 not scored**; the retained
Phase 1 comparison is **14/30**, and deterministic regression is **10/10**. Phase
2 substantially outperformed the retained Phase 1 comparison. The two remaining
scored failures are bounded planner defects, not evidence of architectural
failure; the benchmark results and oracles were not reinterpreted for this
close-out.

The UI represents success, ambiguity, unresolved identity, unsupported requests,
planner/validation failures, and execution failures distinctly. Failed or
unresolved plans do not execute answer queries; accepted plans and generated
SPARQL are inspectable in the development UI. A live smoke test exercised real
Fuseki with a fixed planner test double.

### Carried-forward Phase 2 limitations

These limitations are recorded for the Phase 3 handoff and are not reopened in
Phase 2:

- `aggregate.dail-term-count`: the planner can emit an invalid count draft,
  rejected by draft validation.
- `debate.committee-sep24`: the planner selects a date fact rather than the
  expected DebateRecord answer.
- Development Debate coverage remains limited to the three pinned
  representative graphs.
- Quarantined and unavailable source cases remain data-coverage limitations,
  separately classified from planner failures.
- Planner/model variability remains; no repair/retry loop was added.
- Broader source selection, federation, and external querying remain deferred.

### Delivery retrospective

Phase 2 took longer than the core structured-query change warranted. The
principal delay came from adjacent work needed to make evaluation reproducible:
Bills/data-surface corrections, bootstrap and capture-state recovery, benchmark
setup, and later branch integration. The planner → resolver → compiler
architecture itself did not require repeated redesign. The delivery lesson for
later phases is to isolate adjacent prerequisites unless they genuinely block
the phase, reuse accepted evidence cheaply, keep implementation branches
short-lived, put a thin usable slice in the UI earlier, and fix measured failure
classes rather than broadening scope. Once predefined exit criteria are met,
bounded residual limitations should be carried forward rather than holding the
phase open.

Phase 3 therefore begins from this accepted Phase 2 state. Its existing
source-selection and provenance boundary is the next architectural area, rather
than further Phase 2 local-query work; this close-out does not design or
implement Phase 3.
