# Phase 1 — Local NLQ quality completion

## Progression and final measured result

| Tranche | Change and evidence |
|---|---|
| 1A | Initial measured v0.1.0 baseline: 15 passed, 8 failed, 19 not scored. |
| 1B | Corrected benchmark validity/coverage and published v0.2.0; measured 24 passed, 8 failed, 10 not scored. |
| 1C | Contract-known prefix completion made deterministic; v0.2.0 measured 32 passed, 0 failed, 10 not scored; regression tier 10/10. |
| 1D | Local exact-duplicate Member ambiguity handling and benchmark v0.3.0; measured 34 passed, 0 failed, 8 not scored; regression tier 10/10. |
| 1E | Resolved non-secret translator configuration provenance, backlog audit, and durable regression gate. Final v0.3.0 measured result is recorded below. |

Phase 1E final measured run:

- Run ID: `586caa0b-13e5-4cba-a5cd-7d86831a60f7`.
- Benchmark: `oireachtas-local-nlq` v`0.3.0`, SHA-256
  `b5936a129ee206a7b9a22963bb7d2064d28363d584dcd866a0863b68156c939f`.
- Dataset ID: `sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`.
- Result artifact: `var/nlq-benchmark/runs/586caa0b-13e5-4cba-a5cd-7d86831a60f7.json`,
  SHA-256 `550dfc04f2343e5a4df863790c1f0b9cde737960d5dfe0888d0f75c2b289bba3`.
- Resolved translator metadata: model `gpt-6-luna` (repository `.env`), base
  endpoint `https://opencode.ai/inference/openai/v1` (default), fixed request
  timeout `45.0` seconds and max output `2000` tokens (both defaults). The
  translator appends `/responses`. No credential or authorization value is
  present in the artifact.
- Outcomes: **42 total; 32 passed, 2 failed, 8 not scored**. Not scored: five
  manual-review and three source-data-coverage outcomes.
- Categories: ambiguous names 2 passed/1 manual; committees 3 passed/1 coverage;
  constituencies/panels 4 passed; counts/aggregates 3 passed/1 failed;
  dates/temporal 2 passed/1 failed/1 manual; HouseTerm membership 5 passed;
  joins 4 passed; parliamentary collections 5 passed; simple lookup 4 passed;
  unsupported requests 3 manual/2 coverage.
- Coverage outcomes: quarantined Good Friday Committee, Bills absent from the
  Phase 0A bootstrap, and Debates absent from the Phase 0A bootstrap.
- Manual-review cases: `unsupported.member-favourite-colour`,
  `date.dail-34-start`, `ambiguous.martin`,
  `unsupported.member-birthplace`, `unsupported.member-home-address`.
- The two scored failures were `date.aengus-active-mid-2023` and
  `aggregate.dail-34-collection-counts`, both semantic-result mismatches with
  zero rows. The aggregate query sampled an extra Member-to-collection-membership
  link not present in the frozen regression pattern; the date query used a
  contract-known date-range pattern but failed to retrieve the captured interval.
  Both cases passed in the immediately preceding measured v0.3.0 sample
  (`40c51421-6e72-4ab9-941e-74614c81f75f`), demonstrating output variation, not
  reproducibility. They are instances of the already understood generation /
  semantic-mismatch category, not a new reproducible failure class. They are
  retained as failures; no prompt change was justified from these samples.

The artifact contains all 42 benchmark case IDs exactly once. A secret scan
checked the configured credential and authorization material; neither is
serialized. The benchmark run used the preserved captures at
`/var/home/stephen/Projects/OireachtasOntology/data/raw`, Core State at
`/var/home/stephen/.local/share/oireachtas-etl/core-state.sqlite`, and disposable
loopback Fuseki with the existing Phase 0A bootstrap model. The dataset is
non-authoritative and incomplete.

## Remaining Phase 1 backlog audit

- **Schema grounding — satisfied.** Existing contract and prompt guidance cover
  emitted cross-graph query patterns and graph ownership; v0.3.0 coverage probes
  exercise representative actual data. Phase 1C fixed the measured known-prefix
  issue deterministically. Benchmark evidence did not justify more examples or
  prompt growth, so no prompt-tuning campaign was started.
- **Entity resolution — satisfied sufficiently for Phase 1, with limitations.**
  Benchmark outcomes separate source coverage, query stages and semantic
  mismatch. Current query patterns use contract-grounded labels and predicates;
  the exact-name Member resolver exposes codes as candidate metadata but does
  not independently resolve by code, and code-driven resolution is not
  separately benchmarked. There is no general local resolver expansion. Exact
  duplicate Member names receive deterministic local ambiguity handling,
  contextual narrowing and distinct candidate reporting. Broad/set-valued
  requests remain manual review. **Mechanical binding of a context-resolved
  Member IRI into generated answer SPARQL is explicitly deferred to Phase 2
  validated structured plans and entity binding.** No ad-hoc SPARQL rewriting
  was introduced.
- **Temporal and aggregation behaviour — satisfied for Phase 1, bounded by the
  contract.** v0.3.0 covers term/current/interval and date interpretations,
  counts and grouped results; safety and scoring tests exercise aggregate shape
  and LIMIT behavior. The HouseTerm start-date path remains manual/unsupported
  because its temporal relation is not queryable under the current contract.
  These findings do not authorize broader schema capability.
- **Regression gate — established.** Ten deterministic v0.3.0 cases replay
  frozen translation inputs through the shared pipeline. Exact duplicate Member
  ambiguity cases and stable semantic results are covered in the deterministic
  tests. Future planner/federation work must preserve those behaviors,
  contract-known prefix completion, fail-closed safety, and the separation of
  source-data coverage from NLQ failures unless an explicit contract change is
  approved and documented.

## Supported behaviour and limitations

The local NLQ service can reliably handle the benchmarked local Member lookup,
HouseTerm membership, collection, constituency/panel, committee, join, date /
interval, count and grouped-result patterns when their capture-backed data
prerequisites are present. It grounds generated SPARQL in the versioned local
schema contract, completes known prefixes deterministically, validates queries
fail-closed, and reports exact duplicate Member names as ambiguity before
translation/execution. Measured LLM output remains nondeterministic and can
still produce scored semantic mismatches, as the final run demonstrates.

Known limitations:

- The Phase 0A development dataset is non-authoritative and incomplete.
- Bills and Debates are absent from the Phase 0A bootstrap.
- The quarantined Committee identity remains unavailable due to source conflict.
- Broad/set-valued ambiguity cases may require manual review.
- Contextual Member narrowing does not mechanically bind the resolved IRI into
  generated answer SPARQL; defer explicit entity binding to Phase 2 structured
  query planning.
- Direct NL-to-SPARQL generation remains in place until Phase 2.
- Measured LLM output is nondeterministic; the final sample's failures do
  not invalidate the deterministic regression gate or establish a reproducible
  class by itself.

## Regression policy

Ordinary offline CI must run the deterministic test suite, including the NLQ
benchmark, prefix, ambiguity, pipeline and safety tests. It requires no live LLM
and verifies frozen translations, supported deterministic semantic-result
cases, safety fail-closed behavior and exact duplicate-name ambiguity. The
capture-backed `--tier regression` runner provides an additional deterministic
10-case Fuseki integration gate (Docker and preserved local captures required).
The full `--tier measured` benchmark is nondeterministic diagnostic evidence;
it must retain run/configuration provenance and must not be treated as
byte-for-byte CI output. Coverage-unavailable cases remain separately
classified, never NLQ failures. Future planner and federation changes must
continue to satisfy the deterministic local gate and make any accepted
regression explicit in the contract and evaluation record.

## Phase 1 exit decision

1. **Local NLQ quality is measured rather than anecdotal — PASS.** Versioned
   benchmarks v0.1.0 through v0.3.0 have preserved run records, category
   outcomes and dataset coverage separation.
2. **Major failure categories are understood — PASS.** Prefix generation,
   contract/benchmark scope, source coverage, ambiguity and semantic result
   mismatches have distinct evidence and treatment. The final date/aggregate
   mismatches are visible; the preceding sample passed both, so their variation
   is recorded rather than hidden or promoted to a reproducible class.
3. **Common supported local entity/query patterns resolve — PASS, bounded.** The
   final sample passes 32 cases and has 32/34 scored cases pass; both mismatches
   are recorded above. Exact duplicates clarify locally, while contextual
   IRI binding and broad set-valued review remain explicit Phase 2/manual-review
   limits.
4. **A regression gate exists for subsequent architectural work — PASS.** The
   ten-case deterministic benchmark tier and offline safety/pipeline/entity
   tests do not require live LLM access.

**Phase 1 decision: PASS.** All four roadmap exit criteria are supported by the
measured evidence and deterministic gate. This closes Phase 1 only; Phase 2
structured query planning has not begun.

## Verification

- Resolved-configuration tests cover process-environment overrides, repository
  `.env`, defaults, provenance labels and secret non-serialization.
- Focused NLQ benchmark/pipeline/prefix/ambiguity tests: **103 passed**.
- Deterministic capture-backed v0.3.0 regression run
  `10466ee6-2d18-43f6-a712-48718ac27a26`: **10 passed, 0 failed**.
- Final measured run: all **42** expected case IDs occurred exactly once;
  secret scan passed.
- Full repository tests under the project `mise` Java environment: **771
  passed, 14 skipped**.
- Ontology validation under `mise`: **passed**, 2,504 triples; HermiT completed.
- `git diff --check`: required before commit.
