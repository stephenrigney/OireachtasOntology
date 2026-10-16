# Debates initial-production readiness assessment

Assessment date: 2026-10-09. This report records the exact source/exception
inventory, recommends provisional operational limits for the approved initial
scope, and records source-backed representative owner staging. The
manifest-driven controlled-ingestion implementation is recorded in
[`debates-controlled-staging-report.md`](debates-controlled-staging-report.md).
It does **not** authorize controlled ingestion, publish RDF, or close the human
readiness gate.

**Status reconciliation (2026-10-12):** Phase 6 Tranches A–C are implemented
and accepted, including a successful hosted disposable release gate with real
Restic backup, independent restore and fresh Fuseki reconstruction. The
manifest-driven Debates resource guards and representative source-backed
staging are also complete, and the post-rebase opt-in staging test passed.
The operational **production-host** recovery/credentials/container verification
and the remaining Debates deployment/authorisation gates remain open.
Owner policy positions A–C were recorded on 2026-10-13 below. Generic Phase 6 recovery
acceptance is not a verified backup of the intended production dataset. See
[Phase 6 Tranche C](phase-6-tranche-c.md) and the
[Debates execution plan](debates-production-execution-plan.md).

**Latest D/E/F reassessment (2026-10-16):** Decision D remains blocked by a
Committee 217 provenance gap; the approved Committee ID 115 exception remains
settled. Decision E's private-beta target is not provisioned or launch-ready,
and Decision F remains **NO-GO**. See the dated assessments and consolidated
readiness summary below.

## Owner policy decision record — 2026-10-13

The project owner explicitly recorded the following positions after reviewing
the initial-production decision pack. These are policy decisions, **not**
production deployment, production mutation, or ingestion authorisation.

| Decision | Owner position | Scope and qualification |
|---|---|---|
| **A — 264 exceptions** | **Approved** | Withhold all 264 inventoried Works from the initial publication (261 empty `sectionName`, two duplicate decoded eIds, one URL/FRBRExpression mismatch). Category-level withholding is accepted; preserve per-Work source/hash, classification and audit trace. No source repair, semantic compatibility rule, partial invalid Work graph, blanket retry, or permanent exclusion is approved. |
| **B — census completeness** | **Approved** | Accept the frozen hash-identified 2011+ `/v1/debates` selection of 10,913 Dáil, Seanad and committee Works, excluding written answers, as the bounded initial-ingestion selection. Approval does not assert global Work or Expression completeness, resolve multiple-Expression conflicts, or authorise a changed manifest without review. |
| **C — resources and batches** | **Provisionally approved** | Adopt the currently documented configurable warning/hard-stop limits and one publication worker, capped at **25 Works or 64 MiB of source XML per batch**, with controlled 5-, 10-, then 25-Work progression. Host capacity, production-owner-driven report/RDF size, container memory, backup/rebuild headroom and real batch observations must be verified before operational use or widening. No relaxation of guards is approved. |

The specific frozen inventory is
[`debates-initial-production-inventory.json`](debates-initial-production-inventory.json)
(SHA-256 `ae07dc7c293bcadef3d17fa52ea19e2b92db5368242a53aefd68ec8ca5f0c4d7`).
Approval of A permits **explicit initial withholding** of the 264 known
exceptions, not publication of invalid Works. New or materially different
exceptions still require review. The completion reconciliation must account
for all 10,913 selected Works, distinguish 10,649 inventory-eligible candidates
from the 264 withheld, and report any additional runtime failures separately.
The eligible count is not a promise that all candidates will pass production
owner resolution.

**Still open at this 2026-10-13 baseline — D, E and F:** establish authoritative
production owner captures, published owner graphs, conflict/exclusion policy
and fingerprint; verify the
intended deployment's secured runtime and capacity plus a protected, coordinated
canonical-state backup and independent full restore/rebuild; and obtain an
explicit, separate owner go/no-go for the first five-Work production publication.
Progression to 10 and 25 Works requires review of the preceding batch's clean
graph verification, quarantine, provenance, warnings, resources and recovery
evidence. Freeze/pin the approved inventory and owner fingerprint, stop on
material mismatch or guard breach, and never treat this record as permission
to initiate ingestion.

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

The 264 rows below originated as offline assessment findings. The project owner
approved withholding all of them from the initial ingestion on 2026-10-13;
source repair or later publication has **not** been approved. The offline
inventory did not open Core State, persist production quarantine state or
publish graphs. Approved withholding must still be applied and reconciled by
the eventual controlled production run.
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
on known Expression conflicts. The owner accepted this **bounded census**
as the initial selection on 2026-10-13; that acceptance is not a claim of
global Work or Expression completeness.

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
| Duplicate decoded eId | `debate_transform` | **2** | Initial withholding approved; no source repair |
| Empty `sectionName` | `integration_validation` | **261** (5 pre-2013; 256 from 2013 onward) | Initial withholding approved; no source repair |
| Source URL / FRBRExpression mismatch | `source_identity` | **1** | Initial withholding approved; no source repair |
| Other | exact per-record stage | **0** | No other failure category was observed |
| **Total** |  | **264** | All withheld under approved initial policy |

The exact failure split is 8 pre-2013 (2 duplicate decoded eIds, 5 empty
`sectionName` values and 1 source URL/Expression mismatch) and 256 from 2013
onward (all empty `sectionName`). The inventory reports, but does not write,
quarantine state. No source bytes were edited or repaired; each exception
remains withheld from transformation/publication under the approved initial
policy. Any later repair, mapping reinterpretation or publication needs a
separate evidence-backed disposition.

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

That 2026-10-08 selection tranche did not implement recurring scheduling,
monitoring, alerts or backup/restore. Phase 6 Tranches B/C subsequently
implemented and accepted that generic operational functionality on 2026-10-12.
Actual production-host configuration, timer operation and recovery acceptance
remain separately unverified; Debates is excluded from unattended scheduled
endpoint lists pending explicit ingestion approval.

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

**Readiness gate remains BLOCKED. Do not begin controlled ingestion.**
Owner policy decisions A and B are approved, and C is provisionally approved
as recorded above. Representative source-backed owner staging and Phase 6
implementation acceptance have passed, but staging is non-authoritative
and does not prove production readiness. Before publication a human must:

- ensure the frozen inventory, approved 264-Work withholding and bounded
  completeness policy are applied unchanged, with no silent correction;
- verify provisional warning/stop budgets and batch ceilings against the
  target environment and revise them only with explicit approval;
- accept authoritative production owner graph publication, provenance,
  conflict exclusions, reference outcomes and an exact owner fingerprint;
- accept the deployment-specific secure runtime, protected coordinated backup,
  independent complete-state restore/rebuild and capacity evidence; and
- separately authorise the first five-Work publication and subsequent
  progression gates on observed results.

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
blockers, but remain visible for human review. Owner decisions on the exception-withholding and bounded-completeness policies
were subsequently approved, and the resource policy provisionally approved,
on 2026-10-13 (see decision record above). Deployment verification and separate
operational authorisation remain mandatory.

The operator sequence and recovery prerequisites are recorded in
[`debates-production-execution-plan.md`](debates-production-execution-plan.md).
Its final assessment remains **BLOCKED** because the intended host has no
verified coordinated production backup and isolated restore, despite Phase 6's
successful disposable implementation recovery test. It also lists the remaining
human decisions, authoritative owner approval and exact preflight criteria.
This report and plan authorize no production publication.

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

## Decision D evidence and readiness assessment — 2026-10-16

**Decision D remains blocked; do not accept or publish this owner candidate yet.**
The source-backed candidate census is reproducible and its reference-closure
counts pass, but the existing source-lineage builder cannot attribute one
Committee candidate to an exact source record. This is a production-provenance
gap. It concerns Committee 217, **not** the separately approved and settled
Dáil 33 Committee ID 115 resolution.

### Existing acceptance evidence versus new verification

The earlier 2026-10-09 source-backed staging is existing acceptance evidence
for representative, disposable owner/Debates integration only. It used complete
preserved captures and validated candidate graphs, but its owner snapshot was
explicitly development-only/incomplete, its Committee conflict was then
excluded, and it did not establish authoritative publication or a current
production owner fingerprint. The Phase 6 Tranche C backup/restore/rebuild
acceptance is likewise existing disposable implementation evidence, not a
recovery test of the intended production dataset.

New verification on 2026-10-16 used copies of the indexed complete source
captures and source-run database under disposable temporary storage. The
existing `tools/reference_census.py` passed complete-run, page-hash, pagination,
advertised-count and source-URL checks for the Members, Parties and
Constituencies runs. A second census was byte-identical; both reports have
SHA-256
`a9d714c7d1c236aecba7ae8454c73b188fa0b5bbb084294e25d3a64f41c1f9f3`, matching
the prior report record. Verified source capture fingerprints are also the
fingerprints recorded in the source-backed staging evidence above:

| Capture | Indexed complete run | Records | Capture fingerprint |
|---|---|---:|---|
| Members | `d2c089d0-5203-40f1-97b8-ae0d8285e74d` | 1,928 | `177a0cbfe0db70e6208a3798e7ca368b1d33dadaf3865198c2f9e0a46aae65fe` |
| Houses | `896630a4-9389-4a8f-bf58-65c16a05425c` | 68 | `264e0f5d3b47a92f01cf7e82d7ac47981e38560422d3567ded802086a5f81f70` |
| Parties | `91255248-e348-4d60-a8d6-73a26df49f8b` | 11 | `b71ce8368b26594208783b6873b435008f7f967b7759763a3b2f2cb2e9f5d145` |
| Constituencies | `e6a472b1-b6e0-4e02-8304-9e6cfa73c44d` | 8 | `dbc047946a75aa8726285204970509d0a94be31e033a91183145e7943d8d6356` |

The current candidate builders and validators produced 721 Houses, 1,890
Parties, 7,645 Constituencies and 2,810 Committees triples. All 65 HouseTerms
referenced by Members exist in the Houses candidate. Census totals are 17,557
observations across 2,175 identities: 378 Party/collection, 1,529
constituency/panel and 268 Committee identities. Candidate closure reports
2,488/2,488 closed and zero unresolved closable references, with zero candidate
Member-description leaks. These are source-census/candidate-closure results,
not proof that a publishable, provenance-complete graph set exists. The census
still reports 18 malformed observations and 24 Committee-name ambiguities;
those diagnostics remain visible and are not accepted or silently repaired.

The source-lineage helper check found exact source pointers for all 378 Party
and 1,529 Constituency candidates, but only 267 of 268 Committee candidates.
For a historical sample, the earlier 51-Work Debate staging reported 18
resolved and 31 unresolved Committee-reference outcomes (including three
distinct unmatched older Committee hrefs). That sample is not a new full-corpus
unresolved-reference report. A current owner snapshot and full manifest-aligned
unresolved-reference report remain outstanding.

### Settled Committee ID 115 verification — not reopened

The census reproduced approved observation fingerprint
`06fb58595b879dc206e2bb50aa95014c41718275f1e251d3a5696a1830ccbdb2` for the
exact Dáil 33 Committee identity: 13 `committeeID`/code 115 observations and
one ID/code 156 observation. The candidate graph retains ID/code 115, the Dáil
33 term and the reviewed `Shadow Department` purpose. All 13 selected source
pointers passed exact raw-page/hash/pointer verification; the excluded 156
observation is not included in owner lineage. The Member transform continues
to emit both Committee-membership edges to this identity, preserving their
separate source date ranges. No contradictory evidence about the approved
ID 115 resolution was found. **This decision remains settled.**

### Escalation — Committee 217 source lineage

The affected candidate is the Dáil 33 `joint_committee_on_remit_oversight`
Committee identity (`committeeID`/code 217). Its 17 observations identify the
same Committee, but each has `committeeDateRange.start = null` (end
`2024-11-08`) and is reported as a malformed observation. In
`src/oireachtas_etl/cli.py`, `_reference_inputs` omits observations with a
`malformed_observation` diagnostic when it builds entity source pointers
(around lines 1225–1230). Consequently the candidate census has no exact
source-record lineage pointer for this Committee. Calling the existing
`_build_shared_entity_lineage` fails closed before publication with:

> `cannot safely establish source attribution for shared committees entity … joint_committee_on_remit_oversight: no exact source record pointer is available`

**Issue:** candidate closure succeeds while source lineage for Committee 217
does not. **Impact:** the owner dataset cannot satisfy required provenance and
must not be treated as publishable or accepted for Debates resolution until
this gap has an authorized disposition. **Evidence:** the 17 source observations,
the omission in `_reference_inputs`, and the lineage-builder failure described
above. **Options for review:** determine whether the exact immutable raw-record
pointer can be retained under the existing provenance contract without
interpreting the malformed date; if not, obtain an explicitly reviewed source
disposition (such as withholding that owner identity) or approve a new complete
authoritative capture and rerun the coverage checks. Any option that changes
source scope or publication treatment requires human approval. **Recommendation:**
keep Decision D and publication blocked; preserve the existing source bytes and
the approved ID 115 outcome, and obtain provenance/authority review for
Committee 217 before changing the lineage builder, excluding an owner or
publishing any candidate.

No RDF publication rehearsal was attempted after the lineage precondition
failed. The read-only census source index was schema 4; its SQLite backup was
migrated only in a temporary copy for the schema-8 owner-snapshot tool. That
diagnostic snapshot fingerprint is
`17bf0d2016517d193668f7d0580990988249f780e0d4bb2b711c4b52f10bae2e`, but it has
no Committee graph, reports `coverage_authoritative=false` for Houses and
pending legacy provenance gaps; the Debates snapshot tool also does not cover
Parties or Constituencies. **It is not a D-acceptance or production fingerprint.**
A later raw Members directory from 2026-10-09 has no matching successful
complete-run record in the copied index and was not substituted for the
reviewed indexed capture.

The current in-memory owner candidates therefore have no publication payload
hashes or whole-graph/Fuseki verification, and their exact publication replay
and recovery have not been exercised. Existing source-backed staging did verify
an exact replay of its earlier Committee batch, and Phase 6 passed its separate
disposable backup/restore/fresh-projection gate; neither substitutes for a
deterministic publication and recovery rehearsal of a provenance-complete D
owner set. Do not treat either historical result or the diagnostic local
snapshot as the missing D fingerprint.

New focused checks passed: 125 reference-publication/Core State/provenance
tests, five mapping-integrity tests, and `tests/validate.py` (HermiT and ontology
validation at 2,504 triples). These checks do not close the Committee 217
lineage gap. No production endpoint or Graph Store was accessed, no production
Core State was opened or changed, and no source data or repository code was
modified by the verification.

## Decision E environment-readiness assessment — 2026-10-16

**Assessment: not ready for a private-beta launch.** Repository evidence verifies
an ETL operational baseline and a successful hosted disposable Phase 6 release
gate; it does not verify a provisioned or secured beta environment. The
[private-beta plan](private-beta-deployment-plan.md) remains a proposed baseline:
no hosting provider, access gateway, production database or institutional
integration has been selected. It explicitly prohibits external access until
its staged security gate passes. This assessment selects no provider, gateway,
store or topology, and does not authorize deployment.

### Existing accepted implementation evidence

- The accepted Phase 6 Tranche C revision is
  `d9b65080efcfae0cb16b0cc6ae0e16ad97782572`. The hosted disposable release
  gate (run `38304245816`) passed ten
  groups with zero mandatory skips. Its revision-bound evidence records an
  independent restore of four SQLite stores and a fresh projection of two
  graphs / 283 triples, with Core State integrity `ok` and failure injection.
- The production ETL/operations path documents non-root ETL/ops containers,
  read-only container roots, dropped Linux capabilities, bounded temporary
  storage, loopback-only Fuseki binding, protected runtime configuration, and
  backup/restore/rebuild tooling. These are implementation/configuration checks,
  not deployed-host security or cloud access evidence.
- Phase 6 recovery defines canonical SQLite state and preserved source/evidence
  as the recovery boundary and treats Fuseki/TDB2 as a rebuildable projection.
  Its release gate is representative disposable evidence; it did not establish
  the intended host's complete recovery or execute the production ETL/ops image
  and host systemd timers.

### New verification performed for this assessment

- The current code revision is a descendant of the accepted Phase 6 revision,
  and `compose.production.yml` still has SHA-256
  `b28cb1e7e07bd12797028c6fed83f2f311f7eb251987994e0a0d85be32f155e0`.
- `tests/test_production_deployment.py` passed (21 tests). These wrapper tests
  use a Docker command double; they do not exercise a deployed host or cloud
  security controls.

### Outstanding environment and owner gates

| Area | Verified now | Still required before private-beta launch |
|---|---|---|
| Runtime/configuration | Versioned ETL/ops Compose, wrapper and systemd implementation; example configuration only. | Provision the protected target runtime file, credentials, notification destination, dataset/application configuration and actual units; verify the deployed image/runtime and permissions. |
| Cloud security/access | The plan defines HTTPS, individual invited identities, MFA where supported, private store/admin/publication endpoints and gateway protection. | Select provider/region and identity-aware gateway; provision network isolation, TLS, firewall/IAM, secret management, account invitation/revocation/session expiry and operator separation; test unauthenticated, revoked-user and direct-origin bypass cases. |
| Application/query security | The NLQ POC has bounded read-only query checks and tests for forbidden operations. The ETL Compose stack is loopback-bound and injects Fuseki's admin credential into ETL/ops. | The POC has no application authentication or production hardening, and read-only queries are not a complete cost sandbox. The Compose configuration does not establish a separate read-only NLQ backend identity. Keep the POC local/isolated until the deployed gateway, private endpoints and independently read-only backend permissions pass adversarial staging tests. Add/verify query concurrency, resource and abuse controls; review diagnostics and model-provider data handling. |
| Capacity | Debates ETL guard thresholds and corpus estimates exist; they are not an NLQ beta workload benchmark. | Owner must decide cohort, duration, expected concurrency, budget/cost ceiling and alerts; test application, query, model-call and storage capacity on the chosen target. |
| Canonical backup | Restic, coordinated SQLite backup, isolated restore/activation and fresh-projection rebuild mechanisms are implemented; disposable acceptance passed. | Choose and provision separately protected off-host recovery storage and retention; protect runtime credentials/configuration separately; define whether the beta snapshot, ETL stores or both are canonical and assign refresh/recovery ownership. |
| Restore/operations | A host-local advisory `flock` coordinates documented single-host operations; recovery tooling and procedures are tested in disposable infrastructure. | If beta and ETL are separate, decide and test their publication/snapshot handoff and writer coordination. Restore/rebuild the complete intended dataset on the target in isolation, compare the graph inventory/hashes, test alerts/timers and assign incident, suspension, rollback and teardown owners. |

The deployment is not provisioned or authorized by these findings. The actual
target's capacity, off-host backup, complete-state recovery, access control,
security scan and deployed adversarial evidence remain unverified. Before
provisioning, the beta sponsor must close Gate 1 decisions on cohort, duration,
hosting region, budget, dataset snapshot/authority and refresh policy, enabled
features/model provider, participant notice and data handling, logs/retention,
rollback and stop conditions. Platform, identity, application/security, privacy
and operations owners must then close the Gate 2 controls in the table, including
deployment tests and recovery evidence. An independent security review and
explicit Gate 3 launch approval remain separate. In particular, exposing the
unauthenticated POC without the independently enforced gateway and
origin-isolation controls would be unsafe; no external beta access should be
enabled before the deployed security gate passes.

## Decision F handover check — 2026-10-16

This is an operational handover, not approval to ingest or publish Debates.
Decisions A and B remain approved, Decision C remains provisional, and the
frozen initial inventory remains the only approved selection. The complete
preflight, stop/recovery procedure and separate progression approvals remain in
the [controlled-production execution plan](debates-production-execution-plan.md).

The current worktree's inventory hash was checked against the approved
`ae07dc7c293bcadef3d17fa52ea19e2b92db5368242a53aefd68ec8ca5f0c4d7`. Its
manifest loader reports 10,913 records: 10,649 inventory-eligible and 264
withheld. Recomputing deterministic batches with the 64 MiB ceiling gives:

| Work cap | Deterministic batches | Largest computed batch (source XML) |
|---:|---:|---:|
| 5 | 2,183 | 12,496,743 B |
| 10 | 1,092 | 18,743,211 B |
| 25 | 437 | 40,924,626 B |

All computed batches remain below the 64 MiB ceiling; these are calculations
from the frozen manifest, not production resource measurements. Changing the
Work cap changes batch boundaries; restart at index 0 for each approved cap and
reconcile progress by Work IRI/source hash, as described in the execution plan.
The publication CLI also enforces the 25-Work/64-MiB maximum and requires a
resource-budget file for manifest-driven publication. Publication was not run.

Focused checks passed: `tests/test_debates_readiness.py`,
`tests/test_resource_budget.py` and `tests/test_debates_owner_snapshot_tool.py`
(15 tests total). This verifies selection/batch and read-only owner-snapshot
mechanics; it does not verify any production host, owner dataset, backup or
publication.

F's direct Decision D dependency is a human-accepted, source-backed, clean and
verified owner graph set with complete provenance, accepted Committee 217
lineage treatment, the reviewed unresolved-reference report and an exact owner
fingerprint. That prerequisite is **not met**. Its Decision E dependency is the
secured, capacity-checked ETL/Fuseki/Core State target that will ingest and
retain the dataset, plus a protected coordinated recovery point and successful
target-specific isolated restore/rebuild. If that target is separate from the
private-beta NLQ service, the owner must approve and test the dataset
publication/snapshot handoff; neither target's readiness can be inferred from
the other's. A private-beta Gate 3 launch approval is separate from Debates
ingestion and is not granted by this handover.

Only after D and the relevant E ingestion-environment gates pass may a human
separately authorize the exact first five-Work production publication. Review of
that result is required before a separate decision to progress to 10 Works, and
again before 25 Works. Progression is never automatic.

## Consolidated D/E/F readiness summary — 2026-10-16

| Workstream | Completed evidence | Current status / blocker | Human approval still required |
|---|---|---|---|
| **D — authoritative owners** | Indexed complete capture provenance reproduced; candidate graph validation and 2,488/2,488 closure checks pass; approved Committee ID 115 outcome independently corroborated, with no contradiction. | **Blocked, not accepted.** Committee 217 has no exact source-lineage pointer under the current builder; no owner publication rehearsal, authoritative owner fingerprint or current full-corpus unresolved-reference report exists. | Provenance/authority disposition for Committee 217; then accept the exact owner capture set, candidate payloads/fingerprint, visible diagnostics/exclusions and unresolved-reference outcomes. Do not reopen ID 115. |
| **E — private-beta environment** | Phase 6 disposable restore/rebuild and implementation checks pass; production deployment wrapper tests pass (21); the private-beta plan and staged security gates are documented. | **Not ready for launch.** No provider/gateway/target runtime is selected or provisioned; beta access control, deployed security, actual capacity, off-host canonical backup and target-specific full recovery are unverified. The POC remains unauthenticated and must not be exposed. | Gate 1 design approvals before provisioning; Gate 2 deployed security/operations and independent review; explicit Gate 3 beta launch decision. Separately accept the secure ETL ingestion runtime and its coordinated recovery evidence. |
| **F — controlled Debates ingestion** | Frozen manifest/hash and A/B/C positions retained; deterministic 5/10/25 batch boundaries rechecked; existing controlled-staging and recovery mechanisms are documented. | **NO-GO.** Direct D and ingestion-environment E prerequisites are unmet; no Debates has been ingested or published. | After D/E prerequisites, separate explicit go/no-go for the exact five-Work batch; review that result before separate approvals to progress to 10 and 25 Works. |

**What can proceed now:** human provenance review of Committee 217, review of the
Decision D evidence, private-beta Gate 1 design decisions, and non-publishing
preflight/operational preparation. **What remains blocked:** acceptance or
publication of the current owner candidate, private-beta exposure, and any
production Debates ingestion. The next human decision is the authorized
provenance disposition for Committee 217; it must preserve the settled ID 115
resolution and cannot itself approve D, E, F or production publication.
