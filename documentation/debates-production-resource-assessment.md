# Phase 7 Debates initial-production resource assessment

Measurement date: 2026-10-06. Worktree/branch:
`debates-production-assessment`. Measurement tool:
`tools/debates_scope_assessment.py` (measurement-only; it does not change
ontology, mappings, fixtures, goldens or production graphs).

This report closes the **measurement half** of the Phase 7 Debates
production-scope/resource gate for two proposed initial-production scopes. It
does not select a scope, publish production RDF, start ingestion, or change
Debates semantics. No operational resource budget exists in the repository (see
[Phase 6 production hardening](etl-plan.md)), so this is measured/extrapolated
capacity awaiting an operational acceptability decision, not a pass/fail result.

The earlier [`debates-production-benchmark.md`](debates-production-benchmark.md)
(Tranche 2 transformer path) is retained as the pre-Tranche-4 cross-check. All
reportable footprint figures below come from the **completed Tranche 4 path**
(`run_debate_batch`: preserve exact bytes, transform, Tranche 3 integration
validation, serialize, and — for publication — Core State dirty -> GSP PUT ->
whole-graph SPARQL verification -> clean) against disposable infrastructure.

## 1. Scenarios

### Scenario A — preferred minimum

- Dáil debate records from 2011-01-01 onward
- Seanad debate records from 2011-01-01 onward
- Committee debate records from 2011-01-01 onward
- No written answers
- Known malformed pre-2013 records remain quarantined

### Scenario B — expanded

- Scenario A plus complete whole-record written answers from 2013-01-01 onward
  (`.../writtens/mul@/main.xml`)
- Fragmented pre-2013 written answers are **not** included

## 2. Method

1. **Census (exact, network).** `/v1/debates` was enumerated per calendar year
   with `limit=1000`/`skip` pagination; each record's official AKN `main.xml`
   URL was `HEAD`-measured for exact byte length. Whole-record written answers
   are Dáil-only and were discovered by official sitting-date cross-check of
   `.../dail/{date}/writtens/mul@/main.xml` (the questions API is capped and
   incomplete; the AKN object existence check is authoritative) and
   `HEAD`-measured. The census deduplicates by exact `xml_uri`.
2. **Acquisition (exact, network).** Every in-scope object was fetched and
   preserved with the Tranche 4 `persist_main_xml` content-addressed store
   (`{raw-root}/debates/sha256/{prefix}/{sha256}.xml` plus immutable
   `...meta.json`), recording wall and per-request time.
3. **Transform/validate/serialize (sampled, offline).** Preserved objects were
   replayed through the real `run_debate_batch` non-publishing path. Two samples
   were taken:
   - a **size-stratified** sample (250/category plus **every** 2011–2012 record)
     for RDF volume and the exact pre-2013 quarantine census; and
   - a **uniform random** sample (500/category, seed 20261006, n = 2,000) to
     estimate the post-2012 quarantine rate;
   - plus a small **uncontended single-process** calibration sample
     (40/category) because parallel shards materially inflate per-record time on
     this power-limited host.
   Per-byte and per-triple rates were combined with the **exact** census size
   distribution using per-category size-decile post-stratification.
4. **Publication/verification (sampled).** A size-stratified sample was
   published through the real Core State `dirty -> PUT -> verify -> clean`
   ordering into a **disposable loopback Fuseki/TDB2** dataset
   (`127.0.0.1:13035/debates_t4`, container `oir-debates-t4`,
   `stain/jena-fuseki:5.1.0`). Production graphs were never accessed or mutated.
   Owner resolution used the checked-in example owner graphs
   (`data/api_examples/member.json`, `data/api_examples/houses.json`,
   `tests/fixtures/committee-owner.json`) seeded into disposable Core State via
   the committed owner transformers; **no production owner snapshot exists** in
   this worktree (limitation, section 9). Fuseki/TDB2 disk was measured with
   `du` inside the disposable container around the load.

Measured (exact or sampled) and extrapolated figures are labelled throughout.

## 3. Tested environment

| Item | Value |
|---|---|
| Host | Intel Core i5-1245U (10 cores / 12 threads) |
| RAM | 15 GiB (`MemTotal` 16,039,620 kB) |
| OS / kernel | Fedora 44 / Bluefin 44.20260929, `7.1.10-200.fc44.x86_64` |
| Python / libraries | CPython 3.12.14, RDFLib 7.6.0, pySHACL 0.30.1 |
| Working storage | luks volume, 236 GB total / 181 GB free |
| Triple store | `stain/jena-fuseki:5.1.0` (TDB2), disposable loopback dataset |
| Network | Oireachtas Open Data API + `data.oireachtas.ie` AKN objects |

Peak single-process RSS during the uncontended scan was **434 MiB** (largest
record ~11 MB). Parallel scan shards peaked at 155–425 MiB each.

## 4. Census and raw source volume (exact)

In-scope debate records (`/v1/debates`, unique `xml_uri`):

| Category | Records | XML bytes | GiB |
|---|---:|---:|---:|
| Committee (2011+) | 7,852 | 1,099,806,827 | 1.024 |
| Dáil (2011+) | 1,653 | 1,134,031,746 | 1.056 |
| Seanad (2011+) | 1,408 | 435,398,580 | 0.405 |
| **Scenario A total** | **10,913** | **2,669,237,153** | **2.486** |
| Written answers (2013+) | 1,326 | 1,800,179,009 | 1.677 |
| **Scenario B total** | **12,239** | **4,469,416,162** | **4.162** |

Acquisition (exact, whole B corpus): 12,239 records / 4,469,416,162 B fetched
with **0 errors**; wall **218.5 s** with 12 worker threads (summed per-request
wait 2,613 s, i.e. ~0.585 network-seconds per MB). Scenario A acquisition scales
to ~130 s wall / ~1,561 s summed by bytes.

Persisted source evidence (exact): XML bytes above plus immutable metadata
JSON (~2.9 MB for A, ~0.33 MB for the written increment), plus the
source-/resolver-/owner-snapshot-linked reference-report sidecar measured in
section 6.

## 5. Quarantine census

The Tranche 4 path fails closed on two additional classes the Tranche 2
benchmark did not exercise: (a) the Tranche 3 integration validator rejects an
emitted `debateSection` with an empty `sectionName`; and (b) the source object
URL must match the exact FRBR Expression path in the XML. The result is a
**materially larger quarantine than the "2011–2012" premise** and it is recorded,
not fixed, here.

### 5.1 Pre-2013 quarantine — exact (every 2011–2012 record scanned)

8 records, 5,010,054 B (4.78 MiB):

| Date | Category | Cause | Bytes |
|---|---|---|---:|
| 2011-01-12 | committee | object URL slug ≠ FRBR Expression path | 33,947 |
| 2011-07-19 | Dáil | duplicate decoded eId | 2,567,571 |
| 2011-12-13 | Dáil | duplicate decoded eId | 1,645,089 |
| 2012-04-26 | committee | empty `sectionName` | 178,741 |
| 2012-09-27 | committee | empty `sectionName` | 163,148 |
| 2012-10-23 | committee | empty `sectionName` | 161,367 |
| 2012-11-15 | committee | empty `sectionName` | 102,120 |
| 2012-12-17 | Dáil | empty `sectionName` | 158,071 |

### 5.2 Post-2012 quarantine — estimated (uniform random sample, n = 2,000)

| Category | Sampled | Failed | Rate | 95% CI | Est. records | Est. bytes |
|---|---:|---:|---:|---|---:|---:|
| Committee 2013+ | 454 | 18 | 3.96% | 2.4–6.2% | ~283 | ~40.3 MB |
| Dáil 2013+ | 425 | 3 | 0.71% | 0.2–2.0% | ~10 | ~6.0 MB |
| Seanad 2013+ | 438 | 0 | 0% | 0–0.8% | 0 | 0 |
| Written 2013+ | 500 | 0 | 0% | 0–0.7% | 0 | 0 |

All post-2012 failures observed were empty `sectionName` (committees) or empty
`sectionName` (Dáil). **Scenario A quarantine estimate: ~301 records, ~49 MiB**
(8 exact pre-2013 + ~293 estimated 2013+). The written-answer increment shows no
observed quarantine (500/500 clean). These records remain quarantined and are
excluded from the RDF/runtime estimates below (they still require preservation).

## 6. Transform, validation and RDF volume (Tranche 4 path, sampled + extrapolated)

Uncontended single-process throughput: **0.86 s/MiB** of source across the
calibration sample (committee 1.07, Dáil 0.80, Seanad 0.64, written 0.92 s/MiB),
covering transform + Tranche 3 integration/SHACL validation + payload
serialization. Size-decile post-stratification over the exact census gives:

| Scenario | Records (live) | Triples | N-Quads | Reference reports | Transform+validate |
|---|---:|---:|---:|---:|---:|
| A | ~10,612 | ~9.6 M | 2.90 GiB | 5.83 GiB | ~36 min |
| Written increment | 1,326 | ~7.1 M | 1.85 GiB | 3.84 GiB | ~23 min |
| B | ~11,938 | ~16.7 M | 4.76 GiB | 9.67 GiB | ~58 min |

For reference, the same sample processed under 6-way parallel sharding produced
a ~3.5x higher per-record time (decile estimate ~128 min for A), which is why
the uncontended calibration is quoted as the capacity figure. The old Tranche 2
benchmark estimated ~10.6 GiB of serialized N-Quads for the **entire** historical
corpus with no owner resolution and no Tranche 3 integration validation; the new
per-MiB volume is higher because the Tranche 4 path now emits resolved owner
links and runs the integration validator.

## 7. Publication and verification (sampled + extrapolated)

Measured on the disposable loopback Fuseki/TDB2 (uncontended):

| Sample | Records | Source | Wall | Per record | Per MB |
|---|---:|---:|---:|---:|---:|
| Scenario A | 296 ok (+4 quarantined) | 117.9 MB | 275 s | 0.93 s | 2.3 s/MB |
| Written | 150 | 207.9 MB | 531 s | 3.54 s | 2.6 s/MB |

End-to-end publication (`publish_seconds` includes transform, validation,
serialization, reference-report persistence, Core State writes, GSP PUT and
whole-graph SPARQL verification), size-decile extrapolated to the exact census:

| Scenario | Publication + verification (extrapolated) | GSP PUT + verify component |
|---|---:|---:|
| A | ~135 min | ~99 min |
| Written increment | ~68 min | ~45 min |
| B | ~203 min | ~145 min |

An isolated PUT/verify measurement gave **0.165 s/MB PUT + 0.206 s/MB verify**
(≈0.6 s/record fixed overhead at small record sizes), confirming that the
publication cost is dominated by per-graph request overhead rather than bytes.

**Fuseki/TDB2 disk (measured on the disposable container):**

| Point | Graphs | Triples | `du` bytes | Marginal B/triple |
|---|---:|---:|---:|---:|
| empty baseline | 0 | 0 | 201,326,918 | — |
| after Scenario A sample | 299 | 417,846 | 1,236,318,571 | 2,477 |
| after written sample | 449 | 1,234,853 | 2,675,982,065 | 1,506 (increment) |

Combined measured marginal is **~2.0 kB per triple** (allocated, not apparent:
`du -sb` ≈ `du --block-size=1`), with near-equal incremental cost at both scales.
Extrapolating linearly (least reliable figure; flagged in section 9):

| Scenario | Extrapolated TDB2 (1.5–2.0 kB/triple) |
|---|---:|
| A | ~14–19 GB |
| Written increment | ~11–14 GB |
| B | ~25–33 GB |

**Core State SQLite** stores the full published N-Triples payload per graph,
measured at **~222 B per triple**: ~2.1 GB (A), ~1.6 GB (written), ~3.7 GB (B).

## 8. Consolidated footprint

Measured/estimated persistent storage attributable to each scenario (excludes
the rebuildable Fuseki projection unless stated):

| Artefact | A | Written increment | B |
|---|---:|---:|---:|
| Raw XML (exact) | 2.486 GiB | 1.677 GiB | 4.162 GiB |
| Raw metadata | ~2.9 MB | ~0.33 MB | ~3.2 MB |
| Reference-report sidecars | 5.83 GiB | 3.84 GiB | 9.67 GiB |
| Core State SQLite payloads | ~2.0 GiB | ~1.5 GiB | ~3.5 GiB |
| **Persistent subtotal** | **~10.3 GiB** | **~7.0 GiB** | **~17.3 GiB** |
| Fuseki/TDB2 (projection) | ~14–19 GB | ~11–14 GB | ~25–33 GB |
| **Total with store** | **~24–29 GB** | **~18–21 GB** | **~42–50 GB** |

Runtime summary:

| Phase | A | Written increment | B |
|---|---:|---:|---:|
| Acquisition (network) | ~130 s wall | ~88 s wall | 218.5 s wall |
| Transform + validation | ~36 min | ~23 min | ~58 min |
| Publication + verification | ~135 min | ~68 min | ~203 min |
| Peak RSS per process | 434 MiB | (same process class) | 434 MiB |

All figures fit the tested host comfortably (181 GB free; 15 GiB RAM). The only
working/temporary storage is transient and bounded by one record at a time:
immutable writes stage a sibling temp file before the content-addressed hard
link, the merge/scan holds a single record's graph in memory, and TDB2 writes
its own journal during a PUT. The permanent content-addressed raw store is the
source evidence, not scratch. The Fuseki JVM's own RSS was not separately
profiled (host headroom was ample); this is noted as a limitation.

## 9. Limitations

- **Sampled RDF/runtime/publication.** The exact census and acquisition are
  exhaustive; triples, N-Quads, sidecars, runtime and TDB2 are size-decile
  extrapolations from stratified/random samples. Quarantine rates carry the
  confidence intervals in section 5.2.
- **TDB2 disk is the least reliable figure.** TDB2 allocates in chunks and its
  per-triple cost may fall at larger scale; the linear extrapolation is an
  upper-bound-style estimate and should be validated by a staging load.
- **No production owner snapshot.** Owner resolution used the checked-in example
  Houses/Committee/Member graphs, so the measured resolved-link volume is a
  floor, not the production resolver output. A production owner snapshot may
  increase triples and publication time modestly.
- **New quarantine class.** The empty-`sectionName` fail-closed behaviour
  affects committees throughout 2013–2024, not only 2011–2012. This is a
  corpus/source disposition issue for separate review, not a semantic change
  made here.
- **Timing contention.** Parallel shards inflate per-record time on this
  power-limited host; the quoted transform figure uses the uncontended
  calibration. Publication timings were measured uncontended.
- **Not measured:** Phase 6 scheduling/retention, backup, SHACL beyond the
  committed path, retry/quarantine-policy overhead, and reconstruction of a
  fresh store from canonical state.

## 10. Corpus exceptions recorded (not fixed)

- **2011–2012 malformed records:** 8 records / 4.78 MiB, table in 5.1.
- **Post-2012 quarantine:** ~293 records / ~46 MiB, almost entirely committee
  empty-`sectionName`, plus a handful of Dáil records (5.2).
- **Earlier duplicate-eId records outside scope:** the 2004–2007 era remains
  out of scope (separate future corpus work).
- **Fragmented pre-2013 written answers:** ~5.43 GB of section-level AKN with no
  transformable whole-record source; excluded from Scenario B.

## 11. Assessment

**1. What written-answer inclusion adds (Scenario B − Scenario A):**

| Axis | A | Increment | B | Added % |
|---|---:|---:|---:|---:|
| Records | 10,913 | +1,326 | 12,239 | +12% |
| Raw XML | 2.486 GiB | +1.677 GiB | 4.162 GiB | +67% |
| Triples | ~9.6 M | +7.1 M | ~16.7 M | +74% |
| N-Quads | 2.90 GiB | +1.85 GiB | 4.76 GiB | +64% |
| Reference reports | 5.83 GiB | +3.84 GiB | 9.67 GiB | +66% |
| Fuseki/TDB2 | ~14–19 GB | ~11–14 GB | ~25–33 GB | ~+75% |
| Core State | ~2.0 GiB | ~1.5 GiB | ~3.5 GiB | +75% |
| Transform+validate | ~36 min | +23 min | ~58 min | +64% |
| Publication+verify | ~135 min | +68 min | ~203 min | +50% |

Written answers add **~12% of records but ~50–75% of every resource axis**,
because each whole-record written-answer file is large relative to a debate
record.

**2. Is Scenario A comfortably manageable?** Yes. On the tested host, Scenario A
is 2.5 GiB of source, ~9.6 M triples, ~36 min transform/validate, ~135 min
publication, ~10 GiB of non-store persistence and 14–19 GB of TDB2 — all well
within the 181 GB free and 15 GiB RAM, at 434 MiB peak RSS per process. No
scheduling, parallelism or sharding is required (single-process).

**3. Is Scenario B materially more demanding?** Yes, materially: it is ~1.6–1.7x
Scenario A on RDF volume, persistence, TDB2 and total load time for a 12%
increase in records. It is still feasible on the tested host, but the marginal
cost is high.

**4. Should written answers be deferred from the initial load?** The resource
evidence supports deferring them from the **initial** production load: they add
~50–75% of the RDF/storage/runtime burden for +12% records and no new ontology
coverage (questions/recipients are already in scope via debate records; the
recipient crosswalk is deferred regardless). Loading Scenario A first, then
written answers as a second scoped tranche, keeps the first load small, fast and
easy to verify. This is a scope recommendation only and requires human approval.

## 12. Operational thresholds

No explicit numeric resource/threshold budget for Debates ingestion exists in
Phase 6 or elsewhere ([Phase 6](etl-plan.md) defines configurable policy but not
values). No pass/fail budget is invented here. For separate human approval, the
following conservative **configurable** thresholds are proposed (not adopted):

- quarantine-rate alert per category > 5% of records in a run (committee 2013+
  measured at ~4%);
- per-process RSS warning at 1.5 GiB (measured peak 434 MiB);
- TDB2 volume warning at 70% of allocated store capacity (validated by a
  staging load, since the 1.5–2.0 kB/triple figure is uncertain);
- initial batch ceiling of ~1,000 records per publish run to bound dirty-state
  recovery and run duration;
- run-duration alert for a full initial load > 6 h.

## 13. Gate status and recommendation

- The **resource side of the initial-production gate is ready for human
  approval**: both scenarios are measured on the real Tranche 4 path and both
  fit the tested environment.
- **Recommended initial scope: Scenario A** (Dáil + Seanad + committee, 2011+,
  no written answers), with written answers deferred to a second load.
- The **gate remains open** pending (a) human acceptance of the operational
  threshold and scope choice, and (b) a disposition for the quarantine classes,
  which are larger than the 2011–2012 premise (section 5).
- **No ingestion was started** and no production graph was accessed or mutated.

## Reproducing

```text
OUT=/var/home/stephen/.cache/oireachtas-assessment/out

# exact census + HEAD (network)
.venv/bin/python -m tools.debates_scope_assessment census   --out "$OUT" --start-year 2011 --written-start-year 2013

# exact content-addressed acquisition (network)
.venv/bin/python -m tools.debates_scope_assessment acquire  --out "$OUT" --raw-root /var/home/stephen/.cache/oireachtas-assessment/raw --workers 12

# exact pre-2013 + size-stratified sample through the Tranche 4 path
.venv/bin/python -m tools.debates_scope_assessment scan     --out "$OUT" --raw-root ... --select stratified --sample-per-category 250 --tag strat --shards 6
.venv/bin/python -m tools.debates_scope_assessment merge-scan --out "$OUT" --tag strat
# uniform random quarantine-rate sample
.venv/bin/python -m tools.debates_scope_assessment scan     --out "$OUT" --raw-root ... --select random --sample-per-category 500 --include-before-year 1900 --tag rand --shards 6
.venv/bin/python -m tools.debates_scope_assessment merge-scan --out "$OUT" --tag rand
# uncontended transform/validation calibration
.venv/bin/python -m tools.debates_scope_assessment scan     --out "$OUT" --raw-root ... --select stratified --sample-per-category 40 --include-before-year 1900 --shards 1 --tag clean

# disposal loopback Fuseki/TDB2 publication samples
docker run -d --name oir-debates-t4 -p 127.0.0.1:13035:3030 -e FUSEKI_DATASET_1=debates_t4 -e ADMIN_PASSWORD=assessment-local stain/jena-fuseki:5.1.0
.venv/bin/python -m tools.debates_scope_assessment publish  --out "$OUT" --raw-root ... --state-db .../publish-state.sqlite \
  --gsp http://127.0.0.1:13035/debates_t4/data --sparql http://127.0.0.1:13035/debates_t4/query \
  --user admin --password assessment-local --scenario A --sample-per-category 100

# scenario extrapolation
.venv/bin/python -m tools.debates_scope_assessment analyze  --out "$OUT" --scan-name scanclean --quarantine-scan scanrand
```

The tool refuses any publication target other than the loopback `:13035`
`debates_t4` dataset.
