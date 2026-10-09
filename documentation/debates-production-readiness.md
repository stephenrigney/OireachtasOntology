# Debates initial-production readiness assessment

Assessment date: 2026-10-09. This report records the exact source/exception
inventory, recommends provisional operational limits for the approved initial
scope, and records source-backed representative owner staging. The
manifest-driven controlled-ingestion implementation is recorded in
[`debates-controlled-staging-report.md`](debates-controlled-staging-report.md).
It does **not** authorize controlled ingestion, publish RDF, or close the human
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

These numbers are **provisional defaults for human approval** and are now
enforced by the manifest-publication resource guard; they are not calibrated
production limits. Stop values leave headroom below each reserved capacity. The
backup estimate excludes unrelated ETL data and does not prove
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

### Original tranche requirements (historical status before implementation)

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

### 2026-10-08 implementation update (superseded by 2026-10-09 below)

Manifest selection and deterministic 25-Work/64-MiB batch calculation are now
implemented in `src/oireachtas_etl/debates_readiness.py` and manually invoked via
`oir-etl run debates --inventory-file ... --batch-index N`. Inventory-marked
exceptions are withheld through the existing Phase 6 quarantine callback. At
that date resource enforcement and disposable staging remained outstanding; the
next dated update records their completion and the remaining owner-evidence
blocker.

Recurring schedules, unattended deployment, monitoring/alert wiring and backup
automation/restore remain Phase 6 Tranche B responsibilities. They are not part
of production enumeration and were not implemented here.

### 2026-10-09 staging/resource update (superseded by owner-evidence update below)

The previously missing resource controls are now implemented in
`src/oireachtas_etl/resource_budget.py` and required for manifest-driven
publication. They check configured TDB2, raw/reference-report, Core State,
temporary, host-disk and memory thresholds before runs and around each graph
publication. Exact staged results, 5/10/25 batch measurements, deliberate
warnings/hard-stop, quarantine and recovery tests are in
[`debates-controlled-staging-report.md`](debates-controlled-staging-report.md)
and `tests/test_debates_staging_acceptance.py`.

Real disposable Fuseki/Core State staging passed against representative
validated example owner graphs, but those examples were not current source
captures. At that point source-validated owner evidence remained outstanding;
the 2026-10-09 owner-evidence update below supersedes that assessment. The
default resource thresholds remain provisional until human review; the staged
small-batch measurements do not recalibrate corpus-scale limits.

## Gate decision and outstanding approvals

**Readiness gate remains BLOCKED. Do not begin controlled ingestion.** The
source-backed owner-evidence blocker is now materially reduced by the
representative isolated staging recorded below, but that evidence is not
production authorization or proof of corpus-wide historical owner resolution.
Before any authorization, a human must:

- review and disposition the exact quarantined Works without silent source
  correction or partial Work graphs;
- approve or revise the warning/stop budgets and batch caps above;
- confirm the approved source-listing/Expression-completeness behavior;
- review the isolated source-backed owner snapshot, its exclusions and
  reference-resolution measurements, and the measured capacity/recovery
  evidence; and
- authorize the resulting operational execution plan separately from Phase 6
  Tranche B deployment/scheduling.

No ontology, mapping, identity/ownership contract, source fixture or production
Core State/Fuseki graph was changed. The work ends at this human gate.

### 2026-10-09 source-backed owner-evidence update

The remaining example-owner limitation was investigated using preserved,
complete API captures and the existing non-authoritative `oir-etl dev bootstrap`
path. The captures passed the existing run/provenance, immutable-page hash,
source-envelope and completeness checks. A disposable Fuseki dataset and an
isolated Core State copy were used for the Debates integration; the original
Core State was read-only. No production endpoint or production publication
path was used. This closes the **technical evidence gap for a representative
source-backed staging exercise**, not the overall human readiness gate.

| Owner/source | Preserved successful complete API run | Records | Capture evidence fingerprint (SHA-256) |
|---|---|---:|---|
| Members (includes nested Committee observations) | `d2c089d0-5203-40f1-97b8-ae0d8285e74d` (2026-10-04) | 1,928 | `177a0cbfe0db70e6208a3798e7ca368b1d33dadaf3865198c2f9e0a46aae65fe` |
| Houses | `896630a4-9389-4a8f-bf58-65c16a05425c` (2026-10-05) | 68 | `264e0f5d3b47a92f01cf7e82d7ac47981e38560422d3567ded802086a5f81f70` |
| Parties (census input) | `91255248-e348-4d60-a8d6-73a26df49f8b` (2026-10-04) | 11 | `b71ce8368b26594208783b6873b435008f7f967b7759763a3b2f2cb2e9f5d145` |
| Constituencies (census input) | `e6a472b1-b6e0-4e02-8304-9e6cfa73c44d` (2026-10-04) | 8 | `dbc047946a75aa8726285204970509d0a94be31e033a91183145e7943d8d6356` |

Each capture fingerprint is SHA-256 over the sorted page/metadata filenames and
their individual SHA-256 values. Members consists of 20 pages/metadata pairs;
each other capture has one page/metadata pair. The selected capture run IDs
resolve to successful, complete API runs in the read-only Core State index.
The owner captures were read from
`/var/home/stephen/Projects/OireachtasOntology/data/raw`; the source-run index
was `/var/home/stephen/.local/share/oireachtas-etl/core-state.sqlite`. The
preserved Debate XML and metadata came from
`/var/home/stephen/.cache/oireachtas-assessment/raw`. These local immutable
inputs and all disposable staging databases/reports remain outside this
worktree; only their identifying provenance and hashes are recorded here.
Normal Houses transformation/validation produced 65 numbered HouseTerms. The
Debates owner snapshot indexed 1,928 Member graphs, 65 HouseTerms and 267
Committee identities. Committee descriptions were synthesized from the nested
Committee observations in the complete Members capture using the existing
reference census/candidate builder; there is no independent Committee endpoint
in this evidence set.

The development census reported one materially conflicting Committee identity
(the Dáil 33 Select Committee on the Implementation of the Good Friday
Agreement, disagreeing on `committeeCode`, `committeeDateRange`, `committeeID`
and `committeePurposes`). The existing conflict policy excluded it from the
candidate graph and retained it as one unresolved, explicitly quarantined
reference. No values were selected, repaired or published for that identity.
The development reference closure remains explicitly **NOT authoritative / not
complete**. Consequently, this snapshot is evidence for exact existing-owner
resolution and safe conflict exclusion; it is not a declaration that every
historical or future Debate owner is covered.

Capture selection and snapshot fingerprints:

- Development dataset identity: `sha256:e250a5cfc8f0cc4973c5b677f20218267aca6039fdfaae336623bfd582b951b3`.
- Debates owner-RDF snapshot hash: `cb9863fd2aa8651e97019e2aef7a1ae27ea69466e70bc0682891d6ee48d09f0f`.
- Resolver version: `owner-rdf-registry-v1:3a9446ce66a805d28987dd04ad1a74839491e9d309fb58f562ddb95c7cf0bfe`.
- Canonical owner graph payload SHA-256: Houses `6e028f4f774437860b666a8a400b88b91cfedbe99ef59dd67583fddef9b71aaa`; Committees `96c2d3e9bae050bbdf830b95f929d48729f8136f6d50ef3882e809364d1e0d4a`.
- The 1,928 clean contract-3 Member publications were copied from a read-only
  database snapshot into disposable Core State. Every Member source identity,
  source hash, graph IRI and serialized payload hash was checked against the
  complete Members capture. Houses and Committees were validated with their
  existing RDF/SHACL/quality validation before publication. Whole-graph
  verification against disposable Fuseki passed for owner and Debate graphs.

Representative manifest-selected integration used exact preserved Debate XML
and existing `run_debate_batch` validation/publication machinery:

| Selection | Result in disposable Core State/Fuseki |
|---|---|
| Committee batch 0, 25 Works / 2,867,321 source bytes | 25 new graphs published; 0 quarantined |
| Committee batch 9, 25 Works / 6,101,138 source bytes | 24 graphs published; 1 inventory-withheld exception remained quarantined; degraded outcome, as designed |
| Dáil 2011-01-12 | 1 graph published; source SHA-256 `cf1ca86b43d6d413be773f2d2624478c1811892aed2187e5eaa3a28f676340df` |
| Seanad 2011-01-12 | 1 graph published; source SHA-256 `5daacfd7ae5c034974b1c2500304b7795f7f7ee36a18e05a86b4b95146e57300` |
| Exact replay of Committee batch 0 | 25 unchanged, 0 changed; same owner snapshot fingerprint |

The four selections covered 52 unique Works: 25 in Committee batch 0, 25 in
Committee batch 9 (24 eligible plus one withheld exception), and the two
representative House Works. They yielded 51 clean published Debate resources
and one separately quarantined Work; the quarantine did not publish a graph.
The 51 published Works yielded 51 unique reference reports, 49 of which overlap
the earlier fixture-only comparison. Exact owner and Debate payloads,
reference-report hashes, owner-snapshot fingerprints and the provenance
catalog were verified against disposable Fuseki. Debate graphs contained no Member, HouseTerm or Committee owner
descriptions. The source snapshot therefore exercised, rather than bypassed,
the existing RDF ownership boundary.

#### Resolution outcomes and interpretation

The following compares reports for the **same 49 Works** in the fixture-only
stage and source-backed stage. Counts are reference outcomes, not unique
entities. In the fixture stage, 7,670 Member-reference outcomes lacked an
owner match; with the captured source-backed Members, all 7,670 resolved.
Another 6,301 Member references were source placeholders in both runs and
remain unresolved. The earlier 42 distinct absent Member hrefs are therefore
not source-backed owner gaps in this test set.

| Outcome category (49 shared Works) | Fixture-only | Source-backed | Explanation |
|---|---:|---:|---|
| Member resolved | 0 | 7,670 | 42 previously absent exact Member hrefs now resolve |
| Member unresolved | 13,971 | 6,301 | All remaining outcomes are source placeholders, not missing owner matches |
| Committee resolved / unresolved | 0 / 49 | 18 / 31 | One observed Committee href resolves; three distinct older Committee hrefs remain unmatched |
| Non-numbered HouseTerm-author references | 49 unresolved | 49 unresolved | These source hrefs identify committee authors, not numbered HouseTerms; classified as historical/evidence-limited, not guessed |
| Participation-role crosswalk | 240 unresolved | 240 unresolved | Existing Tranche 2 crosswalk is not configured; non-owner mapping limitation |
| Malformed role fragments | 152 malformed | 152 malformed | Existing reviewed-local-NCName constraint; not modified |

The two additional Dáil/Seanad Works resolved two House owners, two numbered
HouseTerms, and 2,448 additional Member-reference outcomes (all 2,448 exact
matches); the Committee outcome totals were unchanged. Across all 51 reports,
exact outcome totals were 10,118 resolved Member
references and 6,305 source-placeholder Member references; 18 resolved and 31
unresolved Committee references (three unmatched exact hrefs); and two each
resolved House and numbered-HouseTerm references. The 49 historical
committee-author href outcomes remained unresolved as non-numbered HouseTerm
references. All outcome statuses across the 51 reports were 10,349 resolved,
8,249 unresolved, 14,876 expected absent optional attributes, and 503 malformed
role fragments. Unresolved non-owner counts/reasons were 1,144 role
crosswalk-not-configured, 713 deferred question recipients, 4 deferred vote
targets and 3 deferred Bill-event links. Malformed outcomes (342 speech-role and
161 question-recipient fragments) were all `not-a-reviewed-local-NCName-fragment`.
These are not owner-evidence failures and were neither suppressed nor rewritten.

This result supports the approved 2011+ scope as a **bounded, reviewable,
manifest-driven ingestion candidate**: exact modern owners resolve, absent
historical committee evidence remains auditable and unresolved, the known
conflict remains fail-closed, and replay/change detection is deterministic.
It does not prove complete historical owner coverage, resolve the 31 Committee
outcomes, authorize exception decisions, or calibrate corpus-scale resource
limits. Those evidence-limited outcomes are not by themselves defects or safety
blockers, but remain visible for human review. Human budget approval, inventory
exception disposition, source-listing/Expression completeness review and
separate operational authorization remain mandatory.

The operator sequence and recovery prerequisites are recorded in
[`debates-production-execution-plan.md`](debates-production-execution-plan.md).
Its final assessment is **BLOCKED** because no coordinated production backup
and restore facility has been verified; it also lists the remaining human
decisions and exact preflight criteria. This report and plan authorize no
production publication.

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
