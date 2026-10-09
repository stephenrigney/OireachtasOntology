# Phase 2C — deterministic local generation report

## Scope

Phase 2C introduces a callable, deterministic compiler from accepted validated
query plans to safety-validated local SELECT/ASK SPARQL, plus a separate
planner-to-Fuseki evaluation path. It does not connect the generator to the
browser pipeline, change the Phase 1 runtime, expand the ontology/query-schema
contract, or start Phase 3 source selection.

The compiler explicitly maps supported facts, filters, entity types, graph
families, and emitted RDF patterns. Unsupported or unreviewed mappings fail
closed. Member records use contract-owned per-Member graphs; HouseTerm and
owner descriptions use their fixed contract graph families. Entity answers are
resource IRIs, with label lookups confined to benchmark scoring. Reviewed
`during` joins cover Member parliamentary membership, collection membership,
and representation scoped to a resolved Dáil/Seanad term. Date windows,
`current`/`on`, HouseTerm-owned temporal references, and Committee-membership
temporal joins remain unsupported.

## Measured planner/generation run

- Run: `1f789eda-8216-4d23-8e3f-daefac70b94c`
- Planner benchmark: `oireachtas-semantic-planner@0.2.2`
- Planner benchmark SHA-256: `5417f1d5db2d21ad2f1b12a3394cbe36236e0a527f382bc9de3f419d23d01276`
- Source benchmark: `oireachtas-local-nlq@0.3.0`
- Source benchmark SHA-256: `b5936a129ee206a7b9a22963bb7d2064d28363d584dcd866a0863b68156c939f`
- Dataset: `sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`
- Dataset: isolated, disposable Phase 0A development Fuseki; reference closure
  is **NOT authoritative / not complete**. One materially conflicted Committee
  identity was quarantined, and Bills were not loaded.
- Planner: `gpt-6-luna` from repository dotenv; default
  `https://opencode.ai/inference/openai/v1` endpoint; 45-second timeout and
  2,000-token output limit.
- Outcome: 11 cases, 8 passed, 1 failed, 2 not scored.
- Six cases reached SPARQL generation, Fuseki execution, and semantic result
  scoring; all six matched their result oracle. The Boolean plan uses an
  explicit plan-case ASK oracle; coverage probes are not reused as answer
  oracles.
- The one failure was a planner semantic mismatch before SPARQL generation: the
  Seanad-panel plan used answer shape `entity`, while the accepted benchmark
  requires `entities`. This is retained as planner-quality work; neither the
  answer-shape expectation nor the compiler was broadened to make it pass.
- The two not-scored cases are unsupported-question manual review and the
  unavailable-Bill source-coverage case.

The same isolated dataset's Phase 1 direct-generation comparison passed all 7
comparable cases. The planner Boolean case has a different question from its
source case and is explicitly excluded from that comparison because the source
case's SELECT oracle does not apply to it.

## Capture-backed Fuseki acceptance

The opt-in acceptance test passed against a freshly bootstrapped disposable
Fuseki dataset from preserved complete captures:

```text
OIR_RUN_NLQ_PLAN_FUSEKI_TESTS=1
OIR_NLQ_CAPTURE_RAW_DIR=/var/home/stephen/Projects/OireachtasOntology/data/raw
.venv/bin/python -m pytest tests/test_nlq_plan_sparql_fuseki.py -q
1 passed in 408.21s
```

It executed representative Member full-name, Member-to-term, collection-in-term,
representation-in-term, Committee-code, Boolean membership, and distinct Dáil
term-count plans, then checked their semantic results. The resource-valued
collection answer was separately label-looked-up for comparison; its generated
answer query remained resource-valued.

## Verification

Run with the repository's pinned Java runtime available via `mise`:

```text
mise exec -- .venv/bin/python -m pytest tests
1015 passed, 15 skipped

mise exec -- .venv/bin/python tests/validate.py
Ontology validation passed: 2504 triples
```

The 15 skipped tests include opt-in external-service/integration cases; the
Phase 2C capture-backed Fuseki acceptance above was run separately and passed.

## Remaining Phase 2 work

The generated path remains separate from `/ask`; visible plan integration and a
realistic-question benchmark remain outstanding. This report does not claim the
Phase 2 exit criteria have been met. The measured LLM failure above remains
visible, and expected unavailable-source/manual-review cases remain unscored.
