# Phase 1C — Make Prefix Handling Deterministic

## Decision and implementation

Approach **B**, deterministic known-prefix completion, was chosen over
prompt-only enforcement. Prefix bindings are syntax, and the versioned
query/schema contract already owns their prefix-to-IRI map; prompt compliance
would remain dependent on model sampling. No prompt change was combined with
this fix.

The shared pipeline now uses RDFLib's existing SPARQL parse tree to find used
QNames before safety validation. It prepends only missing declarations for
prefixes present in `query-schema-contract.json`; declarations are
deterministically ordered. Existing bindings are left untouched. The parser
distinguishes QName nodes from variables, absolute IRIs, literals and comments.
Malformed input is left for normal validation. Unknown undeclared prefixes are
not completed and are explicitly rejected by validation in any QName position.
The completed query still passes through the existing full parser and safety
validator. No new parser, prompt tuning, predicate, or query/schema capability
was added.

Safety invariants remain unchanged: SELECT/ASK only; reject SPARQL Update,
`SERVICE`, `FROM`/`FROM NAMED`, subqueries, variable predicates and property
paths; enforce the existing predicate allowlist, 32,000-character query cap,
100-row SELECT cap and 10,000 OFFSET cap; execute only through the configured
Fuseki `/query` endpoint. The 142-predicate allowlist, local-deployment
expectation, endpoint requirements and federation-disabled policy were not
changed.

## Verification and measured result

- Exact Phase 1B generated-query snapshots: all **8** are direct graph patterns;
  without completion they fail on undeclared prefixes (the old property-path
  diagnostic was secondary). With completion, all eight pass normal safety
  validation. Tests also cover `agents:`, `members:`, `skos:`, literals,
  comments, absolute IRIs, mixed/complete declarations, unknown prefixes, and
  safety rejection after normalization.
- Browser/shared-pipeline and benchmark-path tests both confirm the same
  normalization behavior.
- Deterministic v0.2.0 regression run: `2dd2e905-5b78-48d9-9f67-d3486062fa0c`,
  **10/10 passed**.
- Full repository suite: **759 passed, 14 skipped**. Ontology validation
  passed: 2,504 triples, HermiT consistent. Focused NLQ tests: **103 passed**.
- Measured v0.2.0 run: `9a5425b3-6697-495e-aeb3-8ba0fec509e2`, created
  `2026-10-07T13:50:03Z`, model `gpt-6-luna`, using the existing `.env`,
  preserved raw captures at
  `/var/home/stephen/Projects/OireachtasOntology/data/raw`, Core State at
  `/var/home/stephen/.local/share/oireachtas-etl/core-state.sqlite`, and a
  disposable Fuseki instance. Benchmark SHA-256 remains
  `f5a5b9d50d6a534360a727ebc73ae321142ace41404228e4e6b098cb67475692`.
- Dataset ID: `sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`
  (same capture-backed dataset identity as Phase 1B; non-authoritative).
- Result artifact (ignored runtime output):
  `var/nlq-benchmark/runs/9a5425b3-6697-495e-aeb3-8ba0fec509e2.json`,
  SHA-256 `d1905bed7dbc361a73a67a5e744fdccd089bbffe2ecb161b48463e101459c045`.
- **42 cases: 32 passed, 0 failed, 10 not scored.** The 10 not scored are
  seven manual-review cases and three source-coverage outcomes. Failure-class
  summary: `source_data_coverage: 3` (all unscored); there were no scored
  failures or other failure classes.

## Phase 1B comparison and next gate

| Run | Passed | Failed | Not scored | Scored failure class |
|---|---:|---:|---:|---|
| Phase 1B baseline | 24 | 8 | 10 | 8 query-safety failures from missing prefixes |
| Phase 1C measured | 32 | 0 | 10 | None |

Phase 1B recorded 10 `query_safety_validation` tags (eight scored failures and
two manual-review outcomes) plus three unscored `source_data_coverage` tags.
Phase 1C recorded only the same three unscored `source_data_coverage` tags.

All eight corresponding Phase 1B cases passed in the Phase 1C sample. In
addition, 11 Phase 1C generated queries used contract-known prefixes without
declarations; each received the required declarations, passed safety and had no
semantic-invariant failure. No missing-known-prefix failure remained. The
eight exact prior query snapshots also pass when replayed through normalization
and validation. The measured score change alone is not causal proof because
model output is nondeterministic; the direct snapshot replays establish the
normalization fix independently of sampling.

No new scored failure mechanism was exposed after queries reached execution.
The next distinct Phase 1 quality priority is **ambiguous-name behavior**:
three cases remain manual review, and this run returned multiple candidates
(including three distinct Cathy Honan identities, three Michael Collins
identities across eight rows, and 22 Martin-prefixed names). These are not
benchmark failures because ambiguity cases are intentionally not automatically
scored. This is a recommendation for the next tranche only; it is not
implemented here.
