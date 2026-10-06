# Phase 5 — Incremental Refresh and ETL State

## Status

This document is the authoritative design for Phase 5. The architecture is
approved. Phase 5 implementation must preserve the ontology, mapping, RDF
ownership, graph-identity, and external-reconciliation decisions established in
earlier phases.

Phase 5 has three gated implementation tranches:

1. core ETL operational state;
2. legislation incremental refresh and complete source reconciliation; and
3. external-reconciliation refresh integration.

A tranche must satisfy its acceptance checks before implementation proceeds to
the next tranche.

## 1. Scope and invariants

Phase 5 makes routine refresh restart-safe, idempotent, and efficient without
introducing workflow infrastructure.

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

Deployment scheduling remains a Phase 6 concern.

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

## 8. External reconciliation integration

Core publication and external identity refresh remain separate pipelines.

Phase 5 must not introduce a second reconciliation queue or duplicate periodic
scheduler. The existing schema-v4 `ReconciliationStore` remains authoritative
for reconciliation state, dirty publication recovery, retry information, and
`next_recheck_at` scheduling.

Successful core processing must make external reconciliation due when:

- a reconcilable entity is new; or
- an identity-relevant source fingerprint changes.

A change to an identity-irrelevant field must not force external
reconciliation. Existing entity-specific reconciliation policy fingerprints
remain the boundary for deciding relevance.

The handoff/invalidation mechanism may be implemented through the existing
reconciliation API/state, but it must be durable and must not couple successful
core publication to availability of an external service. It must not create a
parallel scheduling authority.

Accepted identities continue to be periodically re-verified using the existing
reconciliation scheduling model. Redirects, retired identifiers, disappeared
external targets, and transient external failures are handled by the
reconciliation subsystem. Core source freshness and external-link freshness
remain independent.

## 9. CLI direction

Keep the existing command vocabulary and extend it minimally. The intended
shape is:

```text
oir-etl run members
oir-etl run bills
oir-etl run bills --full
oir-etl reconcile members|parties|institutions [--all]
oir-etl state status
```

Exact option spelling may follow existing CLI conventions, but Phase 5 should
not introduce scheduler, worker, queue-consumer, or orchestration commands.

The existing core-state file option should be migrated deliberately rather than
silently interpreting a legacy JSON file as SQLite. Backward compatibility,
deprecation, or a renamed SQLite option may be selected during Tranche 1
implementation provided migration is explicit, tested, and unambiguous.

## 10. Migration

When legacy Member or Bill manifest state is present and the corresponding core
SQLite state has not yet been established, Tranche 1 must provide a
transactional one-time import.

Migration must:

- preserve clean versus dirty publication meaning;
- preserve published and pending source hashes;
- validate imported identities and graph IRIs;
- fail without partially establishing authoritative SQLite state if input is
  invalid;
- record the state/schema version needed for future migrations; and
- stop writing the legacy JSON manifest after SQLite becomes authoritative.

The existing reconciliation schema-v1-to-v4 migration path is unchanged.

## 11. Implementation tranches

### Tranche 1 — Core ETL operational state

Implement the core SQLite schema and state API, migration of Member and Bill
manifest state, durable publication recovery, graph/publication hash tracking,
run and endpoint state, and state inspection. Port current Member and Bill
full-scan behavior to the new store without changing their semantic output.

Exit requires the existing Member/Bill behavior to pass against SQLite,
including unchanged skipping, dirty recovery, failed publication recovery, and
legacy-state migration.

### Tranche 2 — Legislation incremental refresh and complete reconciliation

Add parameterised legislation extraction, `last_updated` cursor semantics,
fixed run upper boundary, overlap, deduplication, safe cursor advancement,
periodic complete extraction, missing-resource detection, and graph/state
mismatch handling.

Exit requires an interrupted run to be safely rerunnable without lost updates
or duplicate publication; incremental absence must never imply missingness; and
a complete reconciliation must detect known resources omitted by the complete
source result.

### Tranche 3 — External reconciliation refresh integration

Integrate core entity changes with the existing reconciliation subsystem using
identity-relevant fingerprints and the existing due/recheck model. Add handling
and tests for new entities, identity-relevant changes, periodic accepted-link
verification, redirects/retired/disappeared targets, independent retry, and
independent core/external freshness.

Exit requires authoritative core publication to succeed while reconciliation
may independently be stale, pending, or failed, and for later reconciliation
to restore external-link freshness without regenerating authoritative graphs.

## 12. Verification and Phase 5 exit criteria

At minimum, automated acceptance must demonstrate:

- unchanged Member and Bill resources do not transform or publish again;
- new and changed resources publish exactly as required;
- dirty resources retry regardless of hash equality;
- crashes before completion, graph PUT failures, and post-PUT verification
  failures are recoverable;
- an incremental cursor never advances past an incomplete run;
- a successful cursor advances to the fixed run boundary;
- overlap does not cause duplicate graph publication;
- incremental absence never marks a resource missing;
- complete reconciliation can detect missing resources;
- missing state does not automatically erase historical RDF;
- graph/state mismatch is repaired through verified publication or fails
  closed;
- legacy manifest migration preserves clean/dirty meaning;
- core publication succeeds independently of external-service availability;
- identity-relevant changes make reconciliation due while irrelevant changes do
  not;
- existing periodic reconciliation scheduling continues to operate;
- accepted external identities can be periodically re-verified; and
- all Phase 0–4.5 regression tests remain green.

Phase 5 is complete when routine core refresh is restart-safe and idempotent,
the legislation cursor cannot advance past unprocessed source time, periodic
complete reconciliation detects missed or disappeared source resources,
authoritative and external-link state can fail and recover independently, and
no destructive action is inferred solely from absence in an incremental
response.
