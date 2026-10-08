# Debates initial-production readiness assessment

Assessment date: 2026-10-08. This report completes the exact source/exception
inventory and recommends operational limits for the approved initial scope. It
does **not** authorize controlled ingestion, publish RDF, or close the human
readiness gate.

## Approved source scope and exact inventory

The approved scope is all Dáil, Seanad and committee Debate Works dated
2011-01-01 onward, excluding written answers and without a Bill-linkage filter.
Selection was reproduced from the 2011+ `/v1/debates` census, exact `main.xml`
HEAD/acquisition records and the scoped Tranche 4 assessment manifest. The
inventory is keyed by unique official `main.xml` URL. The full source hashes and
evidence paths are in
[`debates-initial-production-inventory.json`](debates-initial-production-inventory.json);
all evidence paths are relative to the configured raw root. The preserved
objects inspected in this session were under
`/var/home/stephen/.cache/oireachtas-assessment/raw`.

| Category | Listed source Works | Unique source hashes | Exact source XML bytes |
|---|---:|---:|---:|
| Dáil | 1,653 | 1,653 | 1,134,031,746 |
| Seanad | 1,408 | 1,408 | 435,398,580 |
| Committees | 7,852 | 7,852 | 1,099,806,827 |
| **Total** | **10,913** | **10,913** | **2,669,237,153 (2.486 GiB)** |

The census contains 10,913 in-scope observations and zero duplicate listing
observations or URLs in this scope. Each selected API Work URI has one listed
`main.xml` URL. Every listed object was fetched in the earlier scoped assessment;
this inventory independently verified its content-addressed XML SHA-256, URL
metadata and byte length before inspection. It ran the current Tranche 4
non-publishing path over every source with the no-owner measurement resolver.
The exact status, source identities,
failure stage/classification, review disposition, N-Triples/N-Quads size and
reference-report size for each Work are in the machine-readable inventory.
All 10,913 selected Works were inspected; zero selected Works remain
uninspected. The earlier all-years benchmark's single duplicate listing
observation was dated 2007 and is outside this scope.

The 264 quarantined rows below are assessment findings and proposed withheld
Work outcomes only. This offline inventory did not open Core State, persist
production quarantine state, or publish graphs; every exception remains pending
human review.
The quarantined source bytes total 52,803,197 B (5,010,054 B pre-2013 and
47,793,143 B from 2013 onward); the 10,649 eligible sources account for
2,616,433,956 B.

`eligible` means that the exact source passes source identity, transformation
and structural/integration validation under the no-owner measurement resolver;
it is not proof of production owner resolution or publication approval. A
single listed Expression
does not establish the complete Expression set for that Work. The inventory
therefore does not claim global Expression completeness or that any graph has
been published.

Accordingly, the exact count is an exact census of the preserved 2011+
`/v1/debates` selection, not proof that the API exposes every global Work or
Expression. Production enumeration must preserve that boundary and fail closed
on known Expression conflicts; whether this endpoint census alone is the
approved completeness boundary remains a human gate decision.

### Exception reconciliation

The previous 2026-10-04 benchmark's seven 2011–2012 failures were two duplicate
decoded eIds and five empty `debateSection/@name` validation failures. The
2026-10-06 scoped assessment added an exact eighth pre-2013 failure: a committee
object URL/FRBRExpression mismatch. The full 2011+ scan classified every listed
source using the current Tranche 4 pipeline. It confirms those eight pre-2013
exceptions and 256 post-2012 empty-section failures, for 264 exceptions total.
The earlier “approximately 301” total was a projection from a 2,000-Work random
sample (eight exact pre-2013 plus about 293 estimated later); the exact scan
replaces that estimate with 256 observed post-2012 failures. Confirmed counts by
failure category and processing stage are summarized here and detailed per Work
in the inventory:

| Failure category | Stage | Confirmed Works | Scope disposition |
|---|---|---:|---|
| Duplicate decoded eId | `debate_transform` | **2** | Quarantine; review pending; no source repair |
| Empty `sectionName` | `integration_validation` | **261** (5 pre-2013; 256 from 2013 onward) | Quarantine; review pending; no source repair |
| Source URL / FRBRExpression mismatch | `source_identity` | **1** | Quarantine; review pending; no source repair |
| Other | exact per-record stage | **0** | No other failure category was observed |
| **Total** |  | **264** | All remain withheld pending human disposition |

The exact failure split is 8 pre-2013 (2 duplicate decoded eIds, 5 empty
`sectionName` values and 1 source URL/Expression mismatch) and 256 from 2013
onward (all empty `sectionName`). The inventory reports, but does not write,
quarantine state. No source bytes were edited or repaired, and each exception
is withheld from transformation/publication under the current contract pending
human disposition.

## Resource measurements and proposed configurable limits

The [2026-10-06 scoped assessment](debates-production-resource-assessment.md)
measured the Tranche 4 path on disposable loopback Fuseki/TDB2. Its exact
acquisition and census remain applicable. Its transform, report, SQLite and
TDB2 totals are sampled/extrapolated, not exact full-production measurements.
The complete non-publishing scan measured exact transformable RDF and
no-owner reference-report totals for the 10,649 eligible Works. It produced
reports only in disposable scratch; reports were not persisted beside immutable
source evidence. A production owner snapshot may change report and RDF sizes.

| Resource | Evidence | Proposed warning | Proposed hard stop / reserved capacity |
|---|---|---:|---:|
| Fuseki/TDB2 | 1.5–2.0 kB/triple measured on a 299/449-graph disposable sample; initial scope projected at 14–19 GB, not full-scale measured | 18 GiB used | Stop at 21 GiB; reserve a 24 GiB TDB2 volume and separate rebuild headroom |
| Preserved raw AKN XML | **Exact 2,669,237,153 B (2.486 GiB)** for 10,913 Works; selected source metadata is **2,985,715 B** | 3 GiB used | Stop at 3.5 GiB; reserve 4 GiB for the initial corpus and immutable revisions |
| Immutable reference-report sidecars | **Exact no-owner reports 6,559,373,603 B (6.109 GiB)** for eligible Works, generated in scratch and not retained; prior 5.83 GiB projection used example owners | 8 GiB used | Stop at 9 GiB; reserve 10 GiB pending production-owner snapshot measurement |
| SQLite Core State | Exact serialized N-Triples payload is **2,496,554,490 B (2.325 GiB)**; prior disposable payload estimate was ~2.0 GiB; database/index/journal amplification remains unmeasured at corpus scale | 3 GiB used | Stop at 3.5 GiB; reserve 4 GiB including journal/WAL headroom |
| Temporary working space | Current inventory is one listed Work at a time; batch retention in the publication CLI is not bounded or measured | 2 GiB used | Stop at 3 GiB; provision 4 GiB and initially cap batches at 25 Works or 64 MiB of source, whichever comes first; one worker |
| Process memory | Prior one-record full-path peak RSS 434 MiB; exact full inventory peak **280,256 KiB (273.7 MiB)** over 10,913 Works | 1.5 GiB RSS | Stop at 3 GiB RSS; concurrency remains one until staged batch measurements pass |
| Host/rebuild headroom | Upper TDB2 projection plus canonical source/report/state storage and a second TDB2 during rebuild | Warn below 80 GiB free | Do not start below 65 GiB free on the ETL/Fuseki host |
| Backup/restore capacity | Exact no-owner canonical artefact total is ~10.92 GiB from raw XML, metadata, reference reports and serialized N-Triples; database amplification and production-owner report changes remain unmeasured. TDB2 is a rebuildable projection, not canonical backup | Warn below 35 GiB free on separate backup target | Reserve at least 30 GiB for a Debate full backup plus restore/staging copy; retention-growth capacity remains to be measured |

These numbers are **proposals for human approval**, not existing settings or
automatically enforced controls. Stop values leave headroom below each reserved
capacity. The backup estimate excludes unrelated ETL data and does not prove
capacity for Phase 6's 30 daily / 12 monthly recovery points; that policy uses
deduplicating/incremental backups and still needs a measured retention-growth
budget. The 65 GiB host reservation includes a second TDB2-sized working copy
for rebuild/recovery; the backup destination is separate.

The earlier scoped assessment's proposed 1,000-Work batch ceiling is not
carried forward as an approved value. The current batch path retains validated
graph candidates until publication and no 1,000-Work memory measurement exists;
25 Works / 64 MiB is a more conservative starting proposal, still subject to
staged RSS measurement and approval.

Exact transform totals for the eligible subset are 10,591,337 triples,
2,496,554,490 N-Triples bytes (2.325 GiB), and 3,413,793,734 N-Quads bytes
(3.179 GiB). The scan completed in 1,870.829 seconds (31 min 10.829 s) with a
peak RSS of 280,256 KiB. These are measurements of the non-publishing,
no-owner-resolver path, not a production-owner run or full publication test.

## Controlled-ingestion readiness

### Existing machinery sufficient for

- **Quarantine and failure reporting:** Phase 6 Tranche A persists isolated
  Debate Work failures with the source hash/path, stage, classification and
  error; unresolved records remain quarantined, and exact preserved-source
  replay drives retry. Use this shared machinery; do not create a Debates-only
  quarantine/provenance store.
- **Per-Work publication verification/recovery:** the Tranche 4 path preserves
  exact AKN bytes and reference reports, stages the exact payload as dirty in
  Core State, PUTs one complete graph, verifies the whole graph, then marks it
  clean. Failed PUT/verification remains replayable. No production state or
  graph was used for this assessment.

### Smallest missing capabilities

1. **Deterministic one-time enumeration/selection:** production CLI accepts
   explicit URLs or replay hashes only. Add a manually invoked, versioned
   selection manifest for the approved dates/types, with deterministic annual
   pagination, source-count/URL checks, unique Work handling and explicit
   written-answer exclusion. Resolve or fail closed on known multiple
   Expressions. This is not recurring scheduling.
2. **Bounded batches and restartable progress:** the current CLI has no
   enforced record/byte batch ceiling or durable selection cursor/checkpoint.
   Add deterministic chunk boundaries and replayable progress tied to the exact
   selection manifest; never infer absence from an incomplete enumeration.
3. **Resource-budget enforcement:** add preflight disk-space checks and
   configurable stop limits for source, reports, Core State, temporary work,
   process RSS and recovery headroom before any graph PUT. The proposed limits
   above need explicit approval and staged calibration before enforcement.
4. **Staged acceptance:** exercise a small bounded batch with the production
   owner snapshot against disposable Fuseki, then verify quarantine, exact graph
   replacement, clean/dirty recovery and replay under the approved budgets.
   This is not a corpus-wide benchmark and must not touch production.

Recurring schedules, unattended deployment, monitoring/alert wiring and backup
automation/restore remain Phase 6 Tranche B responsibilities. They are not part
of production enumeration and were not implemented here.

## Gate decision and outstanding approvals

**Readiness gate remains OPEN. Do not begin controlled ingestion.** Before any
authorization, a human must:

- review and disposition the exact quarantined Works without silent source
  correction or partial Work graphs;
- approve or revise the warning/stop budgets and batch caps above;
- confirm the approved source-listing/Expression-completeness behavior;
- complete the bounded disposable staging acceptance using the production
  owner snapshot and verify capacity/recovery headroom; and
- authorize the resulting operational execution plan separately from Phase 6
  Tranche B deployment/scheduling.

No ontology, mapping, identity/ownership contract, source fixture or production
Core State/Fuseki graph was changed. The work ends at this human gate.

## Reproduction

The [`tools.debates_scope_assessment inventory` command](../tools/debates_scope_assessment.py)
replays preserved bytes offline, verifies every source
hash and metadata object, runs current `run_debate_batch(..., publish=False,
store=None)`, and writes report sidecars only into disposable scratch. It neither
opens Core State nor constructs a Fuseki publisher. The exact selection is
embedded in the committed JSON and can be used for a deterministic replay:

```text
uv run --extra test python -m tools.debates_scope_assessment inventory \
  --selection-file documentation/debates-initial-production-inventory.json \
  --raw-root "$RAW_ROOT" \
  --output /tmp/oireachtasontology/debates-readiness/reproduced-inventory.json \
  --scratch-root /tmp/oireachtasontology/debates-readiness
cmp documentation/debates-initial-production-inventory.json \
  /tmp/oireachtasontology/debates-readiness/reproduced-inventory.json
```

The initial selection can also be reconstructed from the original scoped census
and acquisition outputs with `--assessment-dir DIR`. Those source XML bytes are
external immutable content-addressed evidence; the inventory records their
SHA-256 and relative paths rather than committing multi-gigabyte source files.
The census/acquisition inputs used here were at
`/var/home/stephen/.cache/oireachtas-assessment/out`.
