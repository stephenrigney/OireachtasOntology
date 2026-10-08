# Debates controlled-ingestion implementation and staging report

Assessment date: 2026-10-08. This report records the manifest-driven tranche;
it does **not** authorize production publication or claim production readiness.

## Implemented

- `oir-etl run debates --inventory-file PATH --batch-index N` consumes the
  preserved v1 inventory and does not contact a listing API. It validates the
  inventory scope, duplicate Work/source identities, selection/assessment
  agreement, source and metadata hashes, source byte lengths and official
  `main.xml` evidence. Written-answer and out-of-window rows fail closed.
- Batches have deterministic source-URL ordering and enforce both a maximum
  Works count (default 25) and source XML bytes (default 64 MiB); either ceiling
  can be lowered for calibration but cannot exceed the approved tranche cap. A
  single over-ceiling source produces an explicit error and
  is not silently omitted. Batch index, ceilings and exact inventory SHA-256
  are recorded in the existing Core State run parameters.
- Inventory rows marked quarantined are withheld from transformation and graph
  PUT, then recorded through Phase 6's existing quarantine callback with their
  preserved source evidence and the inventory's classification. Eligible
  siblings continue through the existing Debates pipeline. Re-running a batch
  reuses exact content-addressed source bytes and existing Core State
  dirty/verified publication behavior; there is no new publication ledger or
  deletion inference.

Example manual, offline selection check (does not publish):

```text
oir-etl run debates --inventory-file documentation/debates-initial-production-inventory.json \
  --batch-index 0 --offline --raw-dir "$RAW_ROOT" --output-nq /tmp/batch-0.nq
```

The inventory has 10,913 selected records (10,649 eligible, 264 inventoried
withheld records). The deterministic defaults produce 437 batches. Batch 0
contains 25 records / 2,867,321 source bytes. These are manifest calculations,
not publication or performance measurements. Any altered manifest has a
different run-evidence SHA-256; use the committed inventory to reproduce the
approved selection. Absence from it is not deletion evidence.

## Staging acceptance: BLOCKED, not run

No disposable-Fuseki controlled batch was run and no production-owner snapshot
was substituted. The locally available `~/.local/share/oireachtas-etl/core-state.sqlite`
is an older Core State database (only `core_metadata`, `resource_state`,
`etl_run`, and `endpoint_state` tables were observed read-only); it does not
provide the source-validated owner publications required by the current Debates
resolver. It was not opened through the migration path. The preserved evidence
used for the committed inventory is source evidence for Debate Works, not the
required complete owner snapshot. The checked-in example owner graphs and the
no-owner resolver are not acceptable substitutes.

Consequently, no actual-Fuseki staging results exist for 5/10/25-Work
calibration, graph preservation/failure injection, Core State dirty/pending
recovery, provenance/catalog consistency, quarantine retries, or performance.
No ETL RSS, Fuseki JVM/process RSS, system memory pressure, TDB2 growth, Core
State growth, retained reference-report size, temporary-space peak, or throughput
was measured by this tranche. The proposed resource budgets remain uncalibrated;
the implementation does not yet provide the requested cross-resource preflight
and runtime stop guards. Do not use the manifest CLI for a production load until
these blockers are resolved and the budgets are enforced.

## Recommendation and remaining gates

**BLOCKED — not ready for controlled-ingestion approval.** First establish a
representative, source-validated owner snapshot without unsafe state migration;
then implement and test resource preflight/runtime stop controls; run isolated
disposable Fuseki/Core State acceptance progressively at 5, 10 and 25 records
using that real owner snapshot; inject interruption/PUT/verification failures;
measure each resource in the readiness report; and retain the required recovery
and backup evidence. Existing Phase 6 backup/restore and production execution
prerequisites remain separate human/operational gates. This report does not mark
production readiness complete and does not begin publication.
