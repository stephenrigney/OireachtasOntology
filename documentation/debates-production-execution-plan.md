# Debates controlled-production execution and recovery plan

Assessment date: 2026-10-09. This is an operator procedure for the approved
initial corpus, not an authorization to publish. The final decision is
**BLOCKED** until the explicit prerequisites and human decisions below are
closed. No production operation was performed to prepare this plan.

## Scope and acceptance evidence

Use the versioned inventory
[`debates-initial-production-inventory.json`](debates-initial-production-inventory.json)
only: 10,913 Dáil, Seanad and Committee Works dated 2011-01-01 onward; written
answers excluded; 10,649 currently inventory-eligible, 264 quarantined. Its
SHA-256 is
`ae07dc7c293bcadef3d17fa52ea19e2b92db5368242a53aefd68ec8ca5f0c4d7`.
The exact source XML total is 2,669,237,153 bytes (2.486 GiB). The census is a
bounded selection snapshot, **not** evidence of global Work or Expression
completeness. The full hashes, categories, source sizes and relative raw-evidence
paths are in the inventory and the [readiness assessment](debates-production-readiness.md).

The reported staging counts described two different exercises. The earlier
fixture-only acceptance left 49 Debate graphs; it is not the source-backed
owner-staging publication total. In source-backed staging, the four selections
contained **52 unique Works**: batch 0 (25), batch 9 (25: 24 eligible and one
inventory-withheld exception), and two representative House Works. They yielded
**51 published/clean Debate graphs and one separately quarantined Work**. Exact
replay of batch 0 changed none of its 25 graphs. The 51 published Works had
reference reports; 49 overlap the earlier fixture-only comparison. This
reconciles the stale “51 selected, 49 published, one quarantined” shorthand:
49 was the earlier fixture-only graph count; 51 source-backed Works published,
plus one quarantined, equals 52 unique selected Works. No exception was
silently repaired. See the detailed [staging report](debates-controlled-staging-report.md)
and [owner-resolution outcomes](debates-production-readiness.md#2026-10-09-source-backed-owner-evidence-update).

Source-backed staging used complete preserved API evidence, including 1,928
Members, 65 HouseTerms and 267 Committee resolver identities. The owner snapshot
was `cb9863fd2aa8651e97019e2aef7a1ae27ea69466e70bc0682891d6ee48d09f0f`; the
materially conflicting Committee identity remained excluded. This snapshot is
development evidence, explicitly non-authoritative and incomplete. **Do not
copy or publish that bootstrap snapshot as production authority.** In production,
Debates resolves only from the current clean Houses, Committees and Member graph
payloads retained in Core State. Production owner captures/graph publication
must independently pass their normal source-contract, completeness, validation
and provenance checks before this plan can proceed.

The tested path persists immutable source XML and reference-report sidecars,
stages a whole validated Work graph dirty in Core State, replaces one named
graph, verifies the complete graph, then marks it clean. A stop before PUT leaves
the graph untouched; a failure after dirty marking remains deterministically
replayable. Multi-graph runs are not atomic: already verified graphs stay
published after a later failure. There is no complete-corpus rollback command.

## Exact production inputs and pinning

Before execution, the operator must provide and record exact absolute paths for:

1. The checked-out approved code revision and the inventory above; do not edit
   the inventory in place. Check its SHA-256 against the value above.
2. `RAW_ROOT`, containing every inventory-referenced immutable XML object and
   metadata sidecar. `load_manifest` checks inventory structure/scope; each
   selected batch verifies metadata hash, XML hash/length, and source URL against
   the inventory before transformation. Missing or differing evidence is a
   no-go; do not fetch replacements or rewrite metadata.
3. `STATE_DB`, the current production Core State database, with schema 8 and no
   dirty publications, pending catalog, unresolved provenance-incomplete
   blocker, or unreviewed Debate quarantine from a prior run.
4. The configured production Fuseki Graph Store and SPARQL endpoints, target
   dataset, TDB2 path, and one uniquely observable Fuseki process/cgroup.
   Credentials are supplied only through the existing environment variables;
   never place credentials in this plan, budget file, command history, or
   reports.
5. A versioned `debates-resource-budget-v1` JSON file with absolute `tdb2`,
   `temporary`, and `host` paths; an exact Fuseki process/cgroup selector; and
   an append-only `observation_file` outside protected storage. Its paths must
   name the production resources actually monitored. The tested schema and
   defaults are in the staging report; the proposed limits are summarized
   below.
6. A separately protected backup destination and a verified recovery point for
   both production Fuseki and Core State, described under “Backup gate.” Raw XML,
   metadata and reference reports must remain immutable and independently
   protected.

Set `OIR_RAW_DIR`, `OIR_ETL_STATE_DB`, `OIR_FUSEKI_GSP_URL`,
`OIR_FUSEKI_SPARQL_URL`, `OIR_FUSEKI_USER` and `OIR_FUSEKI_PASSWORD` in the
operator's protected environment. `--raw-dir`, `--state-db`, and the budget
file must agree with these paths. Do not include secrets in environment dumps.

Immediately before the first batch, compute and review the owner fingerprint
from the production Core State and retain the tool output in the protected run
record:

```bash
sha256sum documentation/debates-initial-production-inventory.json
python tools/debates_owner_snapshot.py --state-db "$STATE_DB" \
  > "$RUN_DIR/owner-snapshot.json"
```

The tool opens SQLite strictly read-only, uses the same clean owner payloads as
the Debates resolver, reports source/publication provenance, dirty graph and
catalog state, pending provenance-incomplete items and unresolved Debates
quarantines, and computes the exact publisher fingerprint. Record the reported
`owner_snapshot_sha256` as `PINNED_OWNER_SHA256` in the protected run record.
Before **every** batch, require the tool's fingerprint to equal this pin. After
every batch compare again. Any mismatch, dirty owner graph, source/provenance
gap, or remote exact-graph disagreement is a stop: do not proceed until the
owner publication is reviewed and a new fingerprint is explicitly approved.
The CLI has no expected-owner-hash flag; pin enforcement is therefore this
operator pre/post check plus the run's recorded per-graph owner hash. Keep all
owner publishers stopped for the duration of the Debates load, including while
a batch process is active. Never accept the development snapshot hash merely
because it appears in staging evidence.

The tool is bounded verification tooling, not an owner-data promotion or repair
command. It also supports exact remote graph verification through
`--fuseki-sparql-url`; this issues one read-only query per owner graph (about
1,930 requests for the staged-sized snapshot). Treat that as an additional
capacity-planned check, not a cheap default preflight. Otherwise require the
Core State provenance to show the owner graphs were previously whole-graph
verified and ensure there has been no out-of-band Fuseki mutation. Production
execution needs source-backed, clean, policy-accepted owner publications; a
clean status alone does not make development/bootstrap data authoritative.

## Backup gate and recovery

Phase 6 defines SQLite/Core State as canonical operational state and Fuseki as a
rebuildable projection. Phase 6 Tranche B backup scheduling, retention,
monitoring and restore automation are not implemented. No production backup
or restore facility was verified for this task. This is a **production blocker**:
before authorization, the operator must supply and test an approved recovery
mechanism, not merely run ad-hoc commands or assume TDB2 files are a backup.

The minimum acceptable controlled recovery point, taken during a maintenance
window with all ETL/owner writers stopped, must preserve:

- the complete live Fuseki dataset/graphs, including the pre-existing
  provenance catalog and all unrelated owner graphs;
- Core State plus SQLite WAL/journal state using a transactionally consistent
  SQLite backup (do not copy a live database file alone);
- the immutable Debate XML objects, their metadata, and all retained reference
  report sidecars, with hashes and their configured raw root;
- the exact inventory and SHA-256, approved budget/configuration, code revision,
  Fuseki dataset/configuration identity, and protected credential references.

Store the recovery point on a separate protected target with at least 30 GiB
free before backup and at least 35 GiB free as the warning threshold. Capacity
and retention growth beyond this one-run recovery point remain unmeasured.
Restrict credentials and backup access. Record inventory, SQLite backup,
Fuseki snapshot and raw/report checksums; verify the backup is readable. Then
restore to isolated Fuseki and Core State resources, compare the graph inventory
and exact graph hashes, inspect state with the read-only snapshot tool, and prove that the
restored Core State agrees with restored Fuseki, including the provenance
catalog. Only a successful isolated restore test closes this gate.

At present, no repository CLI or documented deployment facility performs this
coordinated production backup/restore, and no restore has been proven. Operator
must identify the actual approved storage/snapshot mechanism and demonstrate
the isolated restore before publication; otherwise stop. Do not introduce
Tranche B automation as part of this task.

Rollback means restoring the **whole coordinated recovery point**, not deleting
Debate graphs, reversing only the last graph, or copying TDB2 internals while
Fuseki is live. Freeze writers; preserve failed-run logs/observations and dirty
Core State for diagnosis; restore Core State and the complete Fuseki projection
from the same recovery point; verify graph hashes and catalog; then resume only
after human approval. Because graph publication is per-Work and not a corpus
transaction, a partial load is expected and remains recoverable only through
this tested restore procedure plus deterministic replay.

The staging suite **did** verify a different, narrower capability: dirty graph
replay after interruption, PUT/verification failures, unchanged replay,
quarantine retention, and provenance-catalog verification against disposable
Fuseki/Core State. That is not backup or whole-store restoration evidence.

## Resource limits and monitoring

Retain the implemented defaults as provisional controlled-execution ceilings;
do not relax them based on the small staging samples. Obtain human approval and
record the selected values in the budget file before execution:

| Measure | Warn | Stop / prerequisite |
|---|---:|---:|
| TDB2 used / capacity | 18 GiB | stop at 21 GiB; provision at least 24 GiB TDB2 volume |
| Raw XML + metadata | 3 GiB | stop at 3.5 GiB; provision 4 GiB |
| Reference-report sidecars | 8 GiB | stop at 9 GiB; provision 10 GiB |
| Core State | 3 GiB | stop at 3.5 GiB; provision 4 GiB including WAL/journal |
| Temporary space | 2 GiB | stop at 3 GiB; provision 4 GiB |
| ETL RSS | 1.5 GiB | stop at 3 GiB |
| Fuseki JVM RSS | 6 GiB | stop at 8 GiB |
| Host available memory | warn below 3 GiB | stop below 1.5 GiB; do not start a batch below 3 GiB |
| Host free disk | warn below 80 GiB | do not start below 65 GiB; reserve a second TDB2-sized rebuild copy |
| Separate backup destination | warn below 35 GiB | at least 30 GiB available for protected backup/restore copy |
| Batch | one worker | maximum 25 Works or 64 MiB XML, whichever comes first |

The benchmark's 2.486 GiB XML, 6.109 GiB no-owner reports, 2.325 GiB serialized
Core State payload, and 14–19 GB TDB2 projection are measured/extrapolated in
the readiness report; they are not a production measurement. Source-backed
staging observed ETL peak RSS up to 1.30 GiB, Fuseki RSS up to 2.03 GiB, and
available memory as low as 2.65 GiB, with repeated 3 GiB warnings. Therefore
keep separate ETL and JVM controls, require >=3 GiB available memory at start,
and pause/review warnings. Stop immediately on any hard-stop, unavailable
measurement, unobservable/multiple Fuseki process, storage forecast that breaks
the required reserve, or resource-observation write failure. Do not increase
workers or batch ceilings.

Preflight every volume against actual path placement: raw, reports, Core State,
TDB2, temp, host and separate backup may be distinct mounts. A single filesystem
must not be counted repeatedly as independent free capacity. Resource guard
measurements are point-in-time checks, not continuous monitoring; assign an
operator to observe the append-only JSONL report and host/Fuseki health during
each run.

## Operator sequence

### 1. Preflight: go/no-go

Use a protected run directory outside raw, TDB2 and Core State. Record operator,
approval reference, code revision, manifest hash, paths (not credentials),
owner fingerprint, budget hash, backup ID, and start/stop time. Then:

```bash
test "$(sha256sum documentation/debates-initial-production-inventory.json | cut -d' ' -f1)" = \
  ae07dc7c293bcadef3d17fa52ea19e2b92db5368242a53aefd68ec8ca5f0c4d7
.venv/bin/python - "$RAW_ROOT" <<'PY'
import sys
from oireachtas_etl.debates_readiness import load_manifest, make_batches, load_batch_sources
manifest = load_manifest("documentation/debates-initial-production-inventory.json")
batches = make_batches(manifest)
for batch in batches:
    load_batch_sources(batch, sys.argv[1])  # hash/length/URL check; no transform or write
print({"manifest_sha256": manifest.sha256, "works": len(manifest.records),
       "batches": len(batches), "eligible": sum(r.status == "eligible" for r in manifest.records),
       "quarantined": sum(r.status == "quarantined" for r in manifest.records)})
PY
python tools/debates_owner_snapshot.py --state-db "$STATE_DB" \
  > "$RUN_DIR/owner-before.json"
```

Go only when each of the following is objectively true:

- written human approval covers the exact manifest/hash, 264-exception policy,
  completeness boundary, provisional limits, and this plan;
- the required protected backup exists and isolated restore has passed;
- every inventory source and metadata object is present and hash-verified under
  `RAW_ROOT`; no replacement, repair or manifest drift;
- the owner-snapshot tool reports schema 8, no dirty owner/Debate resources, no
  dirty or pending provenance catalog/finalization, and no pending
  provenance-incomplete records for Houses, Members, Committees or Debates;
  unrelated endpoint findings are retained and reviewed without being treated
  as an automatic blocker. Any pre-existing Debate quarantine is reviewed;
- the pinned owner snapshot is source-backed and reviewed, all required owner
  graphs are clean and verified, and none is non-authoritative bootstrap data;
- Fuseki target, Core State, and configured resource paths are the intended
  production targets; process identity is unique and observable;
- resources meet the limits above, initial host MemAvailable is >=3 GiB, volume
  reserves and separate backup space are met, budget is approved, and the
  observer is present;
- no other ETL, owner publisher, Fuseki maintenance or deployment is active.

Any failed or unknown criterion is **NO-GO**. In particular, the backup gate is
currently unverified, so execution cannot start.

### 2. Publish progressively

Only after all gates are closed, use the actual manifest-driven interface. The
initial 5-Work batch is a deliberately smaller first publication; then expand to
10 and finally the approved 25-Work ceiling. The byte ceiling remains 64 MiB.
Changing cap changes deterministic batch indices, so record the cap/index pairs
and reconcile by Work IRI and manifest hash rather than assuming a cursor.
Reprocessing a previously clean Work is expected to be idempotent.

Before and after each invocation, recompute the owner snapshot and require the
pinned hash; the tool returns nonzero on a mismatch:

```bash
python tools/debates_owner_snapshot.py --state-db "$STATE_DB" \
  --expected-sha256 "$PINNED_OWNER_SHA256" > "$RUN_DIR/owner-pre-batch.json"
```

Then use the actual Debates CLI; set `BUDGET` to the approved JSON file:

```bash
oir-etl run debates --publish --inventory-file documentation/debates-initial-production-inventory.json \
  --batch-index 0 --batch-max-works 5 --batch-max-source-bytes 67108864 \
  --resource-budget-file "$BUDGET" --resource-report "$RUN_DIR/resources.jsonl" \
  --raw-dir "$RAW_ROOT" --state-db "$STATE_DB"
```

After the first batch, stop and inspect the CLI JSON, run summary, resource
observations, per-Work graph states, exact named-graph contents, reference
reports and provenance catalog before approving expansion. Continue at the next
unprocessed index only after exact reconciliation:

1. cap 5; start at index 0 and advance, with review after index 0;
2. cap 10; restart at index 0 using the newly computed deterministic boundaries,
   then advance through those indices, with review after the first cap-10 batch;
3. cap 25; restart at index 0 using the approved 25/64-MiB boundaries, then
   advance through all indices to the end, one process/worker.

Each cap change deliberately re-presents some already processed Works. The
publisher must verify and skip unchanged graphs; reconcile by unique Work IRI
and source hash, never sum batch invocation counts as unique selected Works.

The approved byte cap also governs every individual source; any source larger
than 64 MiB is a stop for explicit human disposition, not a reason to raise the
cap. Before/after each batch run the owner-fingerprint tool against the pin; its
read-only state report includes dirty/catalog state and unresolved quarantine
evidence. Save command output and append-only
resource observations under the protected run directory. Require successful
whole-graph verification for each eligible Work; inventory exceptions remain
withheld/quarantined. A `degraded` run is expected when the selected batch
contains an inventory exception or previously recorded inventory quarantines
remain unresolved. Continue only when every degraded/quarantined Work matches
the frozen manifest's explicit quarantine disposition and every eligible Work
in that batch is clean and verified. Any other degraded cause, any failed run,
unexpected quarantine, nonzero exit, hash/provenance mismatch, graph
verification failure, unexpected source, resource warning requiring operator
intervention, or owner fingerprint change stops expansion.

### 3. Interrupt, restart and retry

On interruption or any stop: do not kill/repair Core State manually; stop new
batches, preserve logs and the exact manifest/budget/source hashes, and rerun
the read-only owner-snapshot tool to inspect Core State dirty/catalog/quarantine
state without opening Core State through the migration-capable status command.
If Core State reports a dirty Debate publication or catalog, keep the owner
snapshot and production endpoints stable and rerun the same exact manifest,
batch index, caps and source evidence. The implemented path reuses and verifies
the pending payload before proceeding. Do not switch the owner snapshot while a
dirty publication is pending. If state is ambiguous or endpoint hashes differ,
stop and use the tested backup/restore process after it has been approved; do
not manually PUT/DELETE graphs.

Inventory quarantines remain withheld. A quarantine retry is a separate
operator decision: inspect the exact quarantine evidence from the read-only
snapshot report and inventory, then, only after review,
`oir-etl quarantine retry ID --requested-by OPERATOR --reason TEXT`; reobserve
the exact immutable input with the supported Debates command (`--replay SHA256`)
so the original evidence is revalidated. `state status` and quarantine read
commands open Core State through the normal migration-capable store; do not use
them for production inspection under this no-mutation plan. The approved retry
command is an explicit state mutation and is outside initial-load authorization.
No source bytes are changed and a failed retry remains quarantined. Do not
batch-retry the 264 exceptions as part of the initial load.

### 4. Final reconciliation and completion boundary

Recheck every deterministic manifest batch under the pinned manifest and owner
hash. Produce an operator reconciliation keyed by Work IRI/source SHA-256 with
exactly one status: **published and graph-verified**, **inventory-withheld /
quarantined**, **failed**, or **pending**. Count totals must reconcile to 10,913;
an eligible Work is not counted as published without clean Core State and
verified exact Fuseki graph. The 264 inventory exceptions remain withheld
unless separately dispositioned. Require zero unexplained failed/pending Works,
and review every new runtime quarantine. Verify graph names/payload hashes,
publication provenance and the exact provenance-catalog payload against
Fuseki; verify all batch run outcomes and resource observations. Do not delete
graphs absent from a batch or treat partial work as a complete source scan.

The batch CLI records explicit Debates observations; it does not enumerate a
complete source on each run. **Absence is not deletion.** No partial or failed
run may set complete-source/absence evidence, advance another endpoint's cursor,
or assert that the global Work/Expression corpus is complete. The outcome is
only the committed selection snapshot and verified graph set.

## Remaining gates and decision

Verified: frozen inventory identity/scope; per-batch preserved-source
hash-checking; deterministic bounded batches; fail-closed inventory quarantine;
representative source-backed owner integration; no-owner-description boundary;
resource guard behavior; disposable Fuseki graph/catalog verification;
interruption, dirty replay, quarantine retention and exact replay evidence.

Still requiring operator/human verification: disposition/review of the 264
exceptions; acceptance of the census/Expression-completeness boundary; approval
of budgets and current host capacity; the production source-backed owner graph
and its authority/provenance; target/configuration/credential setup; a current
owner fingerprint pin; and a coordinated production backup with successful
isolated restore. No production backup or restore facility was verified; that
is the immediate technical blocker. No production ingestion, production Core
State mutation, production RDF publication, ontology/mapping change or Tranche
B work is approved by this plan.

**Decision: BLOCKED.** Do not publish until the backup/restore capability is
demonstrated and all go/no-go items and human approvals are recorded. Production
publication requires separate explicit human authorization after those gates;
this document is not that authorization.
