# ETL state and refresh contract

## Status

This reference records the current state ownership, refresh and recovery
contract. The implementation and tests determine current behavior; the phase
history below is retained only as provenance and is not an active implementation
plan. For the overall pipeline and publication boundaries, see the
[ETL architecture](../../architecture/etl.md). Current external reconciliation
handoff behavior is described in the separate
[external refresh reference](external-reconciliation-refresh.md).

The original Phase 5 plan divided delivery into three tranches:

1. core ETL operational state;
2. legislation incremental refresh and complete source reconciliation; and
3. external-reconciliation refresh integration.

Those tranches are complete. Their labels are historical; the current contract
below is not an outstanding implementation checklist.

## 1. Scope and invariants

The implemented refresh design makes routine refresh restart-safe, idempotent,
and efficient without introducing workflow infrastructure.

The following invariants apply throughout the phase:

- immutable raw API evidence remains separate from mutable operational state;
- authoritative Oireachtas publication and external reconciliation remain
  independently recoverable;
- invalid or unverified RDF is never treated as successfully published;
- whole-graph replacement remains the publication mechanism for mutable
  resource graphs;
- operational state must be durable before a remote graph mutation;
- state becomes clean only after graph replacement and post-publication
  verification succeed;
- an incremental response that omits a known resource is not evidence that the
  resource has disappeared from the source;
- external-service failure must not roll back successful authoritative
  publication; and
- Phase 5 introduces no Airflow, Kafka, worker hierarchy, or new scheduler.

Deployment scheduling is an operations concern; see the
[deployment and operations guide](../../development/operations.md).

## 2. State ownership

Phase 5 introduces a SQLite operational-state store for the authoritative core
ETL. It is distinct from the existing schema-v4 `ReconciliationStore`.

The stores have different authorities:

| Store | Authority |
|---|---|
| Core ETL SQLite | authoritative-source runs, endpoint synchronisation, resource observation, authoritative publication and incremental cursors |
| `ReconciliationStore` | external identity decisions, evidence, review state, external-link publication recovery and external recheck scheduling |

The existing Member and Bill JSON manifests are transitional state. Tranche 1
must import them transactionally into the core SQLite store. After a successful
migration SQLite is authoritative; the ETL must not dual-write SQLite and the
legacy manifests.

External-reconciliation fields do not belong in the core ETL state schema.
Likewise, authoritative publication state does not move into
`ReconciliationStore`.

## 3. Core ETL state model

The implementation may refine table and column names, but it must preserve the
following concepts and boundaries.

### 3.1 Run state

Each execution has durable run state including:

- run identifier;
- endpoint;
- run kind;
- start and completion timestamps;
- status and error details where applicable; and
- source/query parameters needed to explain the extraction boundary.

Run kind must distinguish at least:

- full refresh;
- incremental refresh; and
- complete source reconciliation.

Completeness is explicit run metadata. It must not be inferred merely from an
endpoint name.

### 3.2 Endpoint state

Endpoint state records successful synchronisation information that is not
naturally owned by one resource, including:

- last successful run;
- last successful complete scan; and
- endpoint-level publication metadata where the endpoint owns a shared graph.

Houses, Parties, and Constituencies use complete refreshes and should not gain
artificial per-resource publication state solely for schema uniformity.

### 3.3 Resource state

For endpoints with independently replaceable resource graphs, state is keyed by
the stable local resource identity and records enough information to distinguish
observation from successful publication. It includes the concepts:

- endpoint and local resource IRI;
- graph IRI;
- most recently observed source hash;
- source hash corresponding to the successfully published graph;
- published RDF/payload hash where useful for verification;
- last-seen run/time;
- last-published time;
- publication state;
- pending source hash while publication is dirty; and
- source-presence state.

A resource is unchanged only when the current observed source hash matches the
successfully published source hash, publication state is clean, and the
applicable transformation/publication contract remains current. Dirty state
takes precedence over hash-based skipping, including when source data later
reverts to a previously published hash.

### 3.4 Incremental cursor

Incremental cursor state is endpoint-level state separate from individual Bill
publication state. A legislation cursor represents the fixed upper source-time
boundary of the last completely successful incremental run.

## 4. Publication and recovery contract

Resource publication follows this durable ordering:

1. extract and preserve source evidence;
2. validate source and deterministically transform changed/new resources;
3. validate generated RDF;
4. durably record pending/dirty publication state;
5. replace the complete remote graph;
6. verify the published graph; and
7. atomically record clean successful publication state.

A crash or failure before step 7 must leave sufficient durable state for a
rerun to retry safely. Whole-graph replacement and deterministic transformation
make retries idempotent.

Graph/state mismatch must be detected. The implementation must either repair it
through the same publication path or fail closed with actionable state; it must
not silently mark an unverified graph clean.

## 5. Endpoint refresh policy

| Endpoint | Routine Phase 5 policy |
|---|---|
| Houses | complete refresh |
| Parties | complete refresh |
| Constituencies | complete refresh |
| Members | complete scan with per-resource hashing |
| Legislation/Bills | `last_updated` incremental refresh with overlap, plus periodic complete source reconciliation |
| External identity links | existing reconciliation due/new/identity-change selection plus periodic re-verification |
| Debates | explicit supplied main.xml batches use resource publication state; routine scanning/reconciliation remains deferred |
| Votes | deferred |
| Questions | deferred |

The bounded Phase 7 Tranche 4 Debates command is not a complete or incremental
corpus scan: each publishing run records `is_complete=false`, accepts only
explicit main.xml source URLs or exact preserved-object hashes, and has no
cursor or absence/deletion behavior. Non-publishing transformations do not open
Core State. The publish path reuses this resource-publication ordering without
changing Phase 6 production refresh policy.

The Bills CLI continues to represent Bill-resource ETL over the Legislation API.

## 6. Legislation incremental refresh

### 6.1 Cursor boundary

An incremental run establishes a fixed upper source-time boundary before
processing the selected window. That boundary, not the maximum
`last_updated` value observed on an individual Bill, becomes the next cursor
after the run succeeds completely.

The cursor advances only when every required resource in the selected batch has
been safely processed and any required publication has been verified. If the
run fails, the durable cursor does not advance.

This prevents a sparse result set or a partial run from creating an unobserved
time gap.

### 6.2 Overlap and deduplication

The query starts at the previous successful cursor minus a configurable overlap.
The default overlap is one hour.

Repeated records within the overlap are deduplicated by stable Bill identity.
Per-Bill source hashes make re-observation harmless and prevent unnecessary
transformation/publication.

A retry after failure uses the unchanged cursor and therefore re-reads the
overlap. Already-clean resources are skipped; dirty resources are retried.

### 6.3 Complete source reconciliation

Legislation must periodically perform a complete extraction of the current
source dataset. Complete reconciliation uses the same resource hashing,
validation, publication, and recovery machinery as incremental refresh.

Only a successful complete scan can establish that a previously known resource
was not observed. Absence from an incremental result has no presence meaning.

## 7. Missing-resource policy

Core operational presence state distinguishes:

- `present`;
- `missing`; and
- `confirmed_missing`.

A resource first absent from a successful complete scan is recorded
non-destructively as `missing`. Confirmation requires the approved
complete-scan policy to observe the absence again; implementation must not
equate source absence with semantic deletion.

Phase 5 must not automatically erase historical RDF solely because a resource
is absent from an incremental response or a single complete extraction.
Destructive graph removal, where ever appropriate, requires an explicit
endpoint-specific policy and action. Do not use a generic `deleted` state as
a synonym for source absence.

## 8. External reconciliation boundary

Core publication and external identity refresh remain separate pipelines. The
existing reconciliation store owns external decisions, retry/publication state
and recheck scheduling; core publication does not call external services or
create a second queue. Entity-specific fingerprints determine which changes
make reconciliation due. Core source freshness and external-link freshness can
therefore differ. Current handoff, retry and failure details are in the
[external reconciliation refresh reference](external-reconciliation-refresh.md).

## Current commands and completion

Phase 5 delivery is complete. Current supported commands and flags are defined
by `oir-etl --help` and `src/oireachtas_etl/cli.py`; the principal interfaces
include `oir-etl run members`, `oir-etl run bills [--full]`,
`oir-etl state status`, and the endpoint-specific `oir-etl reconcile ...`
commands. There is no scheduler/worker subsystem in this refresh contract.

Legacy Member/Bill JSON state is an explicit one-time import input. Core State
SQLite is authoritative after successful migration; the JSON manifest is not
dual-written. Schema upgrades and unsupported-schema handling are implemented
in Core State and covered by tests, rather than prescribed by a future migration
plan here. See the
[Phase 6 operational foundation record](../../reports/etl/phase-6-tranche-a.md)
for revision-specific acceptance detail and the
[operations guide](../../development/operations.md) for scheduled operations,
backup and recovery procedures.
