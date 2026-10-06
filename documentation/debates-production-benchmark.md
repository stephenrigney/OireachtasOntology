# Phase 7 Debates production resource benchmark

> **Superseded for the initial-production gate by the Tranche 4 assessment.**
> This 2026-10-04 census/benchmark used the Tranche 2 `transform_debate` path
> (no Tranche 3 integration validation, no Tranche 4 preservation/publication).
> The initial-production scope measurements through the completed Tranche 4 path
> are in
> [`debates-production-resource-assessment.md`](debates-production-resource-assessment.md).
> The exact source census here remains a useful cross-check.

Measurement date: 2026-10-04. Transformer: committed `transform_debate` at
`master` `88ba310` (`src/oireachtas_etl/transforms/debates.py`, SHA-256
`b459649e27721be976729b6d65fab370a8dcf6e404d8b9b2c591d2047951a30b`).
Measurement tool: `tools/debates_benchmark.py` (measurement-only; it does not
publish RDF and is not an ETL path).

This report records the census and benchmark required by the Phase 7
production-scope gate: full Dáil + Seanad + committees + written answers versus
Bill-debates-first. It does not select a production scope and does not change
Debates semantics. No production resource budget is defined in the repository,
so the result is **measured/extrapolated resource cost awaiting an operational
acceptability threshold**, not a pass/fail result.

## 1. Source census

The census uses only authoritative Open Data API listings and official AKN
URLs. `/v1/debates` was enumerated per calendar year with `limit=1000` and
`skip` pagination (the broad query reports a capped count, and `/v1/questions`
caps both its count and `skip` at 10,000, so written answers were enumerated in
monthly windows).

### Debate records and files (all records have an AKN `main.xml`)

| Category | Records | Unique files | XML bytes | % of debate bytes | Median | p90 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Dáil | 8,918 | 8,918 | 5,652,616,906 (5.26 GiB) | 64.9% | 523,523 | 1,100,100 | 7,131,632 |
| Seanad | 5,180 | 5,180 | 1,420,343,998 (1.32 GiB) | 16.3% | 261,022 | 434,582 | 1,162,326 |
| Committees | 12,370 | 12,369 | 1,629,404,632 (1.52 GiB) | 18.7% | 112,631 | 233,415 | 1,025,313 |
| **Total** | **26,468** | **26,467** | **8,702,365,536 (8.10 GiB)** | 100% | 218,819 | 689,034 | 7,131,632 |

- Every enumerated record had `debateType="debate"` and a non-empty XML URL;
  record dates span 1919-01-21 to 2026-10-01.
- All 26,467 unique AKN URLs returned HTTP 200 on HEAD.
- One API listing duplicate exists: `joint_committee_on_european_scrutiny`
  2007-11-20 appears twice with the same Work URI, so 26,468 records correspond
  to 26,467 documents. A per-Work keyed ingestion must not double-process it.

### Written answers

Written answers are Dáil-only (no Seanad written-answer document was observed).
`/v1/questions?qtype=written` exposes 2,159 written-answer documents for
2004-01-27 through 2026-10-01. Cross-checking every Dáil/Seanad sitting date
from 2004 onward against `…/writtens/mul@/main.xml` found 1,365 existing
whole-record files:

- 1,364 are also question-derived;
- 1 is sitting-derived only: `dail/2018-03-07/writtens` (the questions API
  returns zero questions for that date, but the file is a real, non-empty
  source with a `writtenAnswers` section and summaries);
- 795 question-derived documents (2004–2012) have **no whole-record `main.xml`**
  (HTTP 403; the object does not exist). For those dates the API points only at
  section-level AKN documents.

| Written-answer segment | Documents | Files | Bytes |
|---|---:|---:|---:|
| Whole-record `main.xml` (2012 onward; complete from 2013) | 1,364 | 1,364 | 1,843,512,920 (1.72 GiB) |
| Median / p90 / max whole-record file | | | 963,623 / 2,472,709 / 11,171,904 |
| Section-fragmented pre-2013 documents | 795 | 193,687 sections | ~5.43 GB (95% bootstrap 5.16–5.72 GB) |

The fragmented estimate comes from a systematic sample of 1,860 section files
across 93 months (all HTTP 200; mean 28,013 B, median 8,229 B). The section
files carry the whole writtens Work/Expression identity and contain one
`debateSection` each. They are **not** complete Work sources: a sample of them
either fails closed (`duplicate-eid`) or transforms into a 17-triple partial
graph under the same Work graph IRI, so they must not be ingested as whole
records. Pre-2013 written answers therefore have no transformable whole-record
source under the current contract.

### Bill-linked debates (for the Bill-debates-first option)

| Category | Records with a Bill link | Share of records | Bytes with a Bill link | Share of category bytes |
|---|---:|---:|---:|---:|
| Dáil | 7,266 | 81.5% | 4,852,082,569 | 85.8% |
| Seanad | 4,504 | 86.9% | 1,266,937,269 | 89.2% |
| Committees | 1,484 | 12.0% | 235,306,936 | 14.4% |
| **Total** | **13,254 (50.1%)** | | **6,354,326,774 (5.92 GiB)** | **73.0%** |

Using only Bill *stage* sections gives 12,006 records and 5.50 GiB (67.9% of
debate bytes). Bill-debates-first is therefore not a small pilot: it covers
about half the records and nearly three-quarters of the debate XML volume.

### Published AKN volume summary

| Scope | Bytes |
|---|---:|
| Transformable whole-record corpus (debates + writtens `main.xml`) | 10,545,878,456 (9.82 GiB) |
| Section-fragmented pre-2013 written answers (estimate) | ~5,425,745,000 (5.05 GiB) |
| All published AKN (including fragments) | ~15,971,623,848 (14.88 GiB) |

## 2. Benchmark methodology

- Exact AKN bytes fetched from the official URLs; no modification to the
  transformer, ontology, mappings or fixtures.
- Every run calls the committed `transform_debate(source_bytes, resolver=...)`
  and `validate_debates(result)`; RDF bytes are measured with the repository's
  `serialization.nquads`.
- Two resolver modes are measured:
  - **resolver none** — the Tranche 2 committed behaviour and golden-test path;
  - **members registry** — a measurement-only exact
    `TLCPerson/@href → Member IRI` registry built from `/v1/members`
    (1,928 members), used to quantify owner-link RDF volume. HouseTerm/Committee
    resolution is not implemented in Tranche 2 and remains unresolved, so this
    is a partial production-shape estimate, not an owner-resolution
    implementation.
- Repeated runs: 3 transforms per file for the stratified sample, 1 per file
  for the 240-file random sample; reported timings are minimum/median.
  `tracemalloc` allocation measurement runs in a separate pass because it
  materially distorts timings. Module import overhead measured separately at
  ~0.11 s.
- Sample design: the 5 committed fixtures; 8 size strata per category
  (p0/p10/p25/p50/p75/p90/p99/max, 32 files); 60 uniform-random files per
  category (240 files, seed 20261004); plus an exact fetch/transform scan of
  every 2004–2012 record (5,302 records).
- Host: Intel i5-1245U (12 threads), 15 GiB RAM, Fedora 44, Python 3.14.6,
  RDFLib 7.6.0. Timings were re-measured on an idle machine.
- Not measured: network download time, Fuseki/TDB2 load and disk
  amplification, SHACL/competency validation (Tranche 3), retry/quarantine
  policy overhead, and long-term persistence policy for the reference report.

## 3. Measured results

### 3.1 Committed fixtures and size-strata extremes (resolver none)

| Input | Source B | Triples | N-Quads B | NQ/source | Transform s | Validate s | Alloc peak MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| committee_public_accounts_2026-09-24 | 408,509 | 3,779 | 1,239,679 | 3.03 | 0.181 | 0.051 | 12.3 |
| dail_2015-07-02 | 927,249 | 3,600 | 923,912 | 1.00 | 0.233 | 0.052 | 17.5 |
| dail_2026-02-26 | 964,819 | 2,470 | 675,357 | 0.70 | 0.173 | 0.035 | 15.1 |
| dail_written_answers_2015-07-02 | 1,075,045 | 2,423 | 681,004 | 0.63 | 0.285 | 0.038 | 26.4 |
| seanad_2015-07-02 | 230,459 | 1,025 | 284,649 | 1.24 | 0.046 | 0.015 | 4.1 |
| Dáil 2012-01-25 (strata max) | 7,131,632 | 6,464 | 1,771,300 | 0.25 | 1.941 | 0.076 | 201.1 |
| Committee 2015-09-09 (strata max) | 1,025,313 | 10,125 | 3,829,872 | 3.74 | 0.520 | 0.110 | 32.2 |
| Seanad 2014-12-19 (strata max) | 1,162,326 | 7,682 | 2,144,796 | 1.85 | 0.409 | 0.093 | 28.2 |
| Writtens 2022 (strata max) | 11,171,904 | 43,973 | 12,393,111 | 1.11 | 10.298 | 0.599 | 221.4 |

Aggregate over the 30 successfully transformed stratified files: validation
adds ~9% of transform time (median per-file ratio 26%; small records are
proportionally more expensive to validate); N-Quads serialization adds ~2%.
Reference-report JSON ranged from 0.25× to 6.03× the source bytes (median
2.16×); it is generated in memory and is not persisted by the current
transformer.

### 3.2 Random-sample rates (60 files per category, successful files only)

| Resolver | Category | s/MiB | Triples/MiB | N-Quads ÷ source |
|---|---|---:|---:|---:|
| none | Dáil | 0.249 | 3,866 | 1.01 |
| none | Seanad | 0.155 | 3,032 | 0.80 |
| none | Committees | 0.215 | 5,282 | 1.86 |
| none | Writtens | 0.363 | 4,185 | 1.12 |
| members | Dáil | 0.292 | 7,505 | 2.09 |
| members | Seanad | 0.183 | 5,276 | 1.48 |
| members | Committees | 0.274 | 8,665 | 3.18 |
| members | Writtens | 0.391 | 5,922 | 1.64 |

Member owner resolution increases RDF volume materially (roughly +60–100%
triples; N-Quads ÷ source roughly +60–80%). It has little effect on transform
time (+10–20% in the sample).

### 3.3 Fail-closed and invalid records (exact 2004–2012 scan)

The scan fetched, transformed and validated all 5,302 records dated 2004–2012:

| Status | Records | Bytes | Cause |
|---|---:|---:|---|
| ok | 4,620 | 1,296,511,716 (1.21 GiB) | — |
| fail-closed | 677 | 598,952,061 (571.2 MiB) | duplicate decoded eId |
| validation-error | 5 | 763,447 | empty `debateSection/@name` |

Failures by year: 2004 179, 2005 165, 2006 175, 2007 135, 2008 20, 2009 1,
2010 0, 2011 2, 2012 5 validation errors. Dáil and Seanad records dated
2004–2007 are almost entirely affected (654 of 680 records, 96.2%); committee
records are unaffected by duplicate eIds. The duplicate eIds are overwhelmingly
`meta/analysis/otherAnalysis/column` elements (21,496 of 21,500 duplicates;
median 8 per failing record, maximum 115). The five validation errors are
`ValueError: sectionName must not be empty when emitted` (four committee
records and one Dáil record, all 2012) where the source carries an empty
`debateSection/@name`; the transformer emits an empty `sectionName`, which the
committed validator rejects.

The systematic random sample (240 files over all years) independently saw only
6 failures (1 Dáil, 5 Seanad), all 2004–2007, and no failures outside the
scanned era among 94 sampled pre-2004 files and 110 sampled 2013+ files. The
scanned era is the only era with observed failures at that scale; other eras
are not proven failure-free.

### 3.4 Working memory

Single-record peak RSS (including ~32 MiB interpreter/RDFLib baseline):
293 MiB for the 11.17 MB writtens file, 250 MiB for the 7.13 MB Dáil file,
75 MiB for the 1.03 MB committee file. Traced Python allocation peaks range
from 0.13 MiB (3.5 KB input) to 221 MiB (11.17 MB input) and scale with emitted
resources, not only source bytes. Concurrent record processing multiplies the
working set.

### 3.5 Era runtime cross-check

A fixed random subset of 210 successfully transformed 2004–2012 records
(126,331,838 B = 120.5 MiB) was re-measured on the idle host with transform,
validation and N-Quads serialization timed together. Measured combined
throughput was 0.394 s/MiB (47.5 s); the transform-only rate is about
0.35 s/MiB after removing the stratified-sample validation/serialization
overhead. The size-decile prediction for the same 210 files was 28.8 s
(transform only, ~0.24 s/MiB), i.e. the point estimate understates this era's
transform cost by roughly 1.5×. Predicted N-Quads volume was 108.4 MB against
118.4 MB measured (0.92×), so the RDF-volume estimate is materially closer than
the runtime estimate. The 2004–2012 cohort is somewhat more expensive per byte
than the all-years random sample; section 4 runtime figures are therefore
quoted as ranges rather than single values.

## 4. Extrapolated full-corpus cost

Method: per-category size-decile post-stratification. Median per-byte rates
from the random sample are applied within each corpus-size decile, using every
known corpus file size from the HEAD census. Fail-closed and validation-error
records are counted in source bytes but excluded from RDF and runtime
estimates (they still require raw preservation and quarantine handling). The
estimate is dominated by the measured size distribution, not by a simple mean.

**Assumptions:** linear behaviour within deciles; the sampled years are
representative of unsampled years (all 2004–2012 records are scanned exactly);
the committed transformer and resolver mode are unchanged; single-process
transformation with files already available locally; serialized N-Quads bytes
represent persistent RDF without triple-store amplification.

### 4.1 Full transformable corpus (debates + writtens `main.xml`)

| Estimate | Resolver none | Members registry |
|---|---:|---:|
| Source bytes | 9.82 GiB (incl. 571 MiB quarantined) | same |
| Records | 27,831 (682 quarantined) | same |
| Transform runtime | ~0.6–1.0 h | ~0.7–1.2 h |
| Triples | ~39.1 M | ~68.9 M |
| Serialized N-Quads | ~10.6 GiB | ~19.6 GiB |

The decile point estimates were 0.64 h / 0.73 h; the upper ends apply the ~1.5×
era under-prediction seen in section 3.5. Corroborating methods that did not
exclude failed records: aggregate per-byte rates give 0.70 h / 11.1 GiB (none)
and 0.80 h / 20.6 GiB (members); per-file log-log fits give 0.67 h / 10.4 GiB
(none) and 0.77 h / 19.2 GiB (members). The RDF-volume spread across methods is
roughly ±10%; the runtime spread is dominated by the era cross-check.

### 4.2 Bill-debates-first corpus

| Estimate | Resolver none | Members registry |
|---|---:|---:|
| Source bytes | 5.92 GiB (incl. 509.5 MiB quarantined) | same |
| Records | 13,254 (571 quarantined) | same |
| Transform runtime | ~0.4–0.6 h | ~0.4–0.7 h |
| Triples | ~22.4 M | ~41.2 M |
| Serialized N-Quads | ~5.8 GiB | ~11.3 GiB |

Bill-debates-first also inherits most of the duplicate-eId quarantine problem:
571 of the 682 quarantined records are Bill-linked.

### 4.3 Storage

| Artefact | Estimate |
|---|---:|
| Raw debate XML | 8.70 GB (8.10 GiB) |
| Raw writtens `main.xml` | 1.84 GB (1.72 GiB) |
| Raw section-fragmented writtens (if preserved) | ~5.43 GB (5.05 GiB) |
| Raw XML, debates + transformable writtens | 10.55 GB (9.82 GiB) |
| Raw XML, all published AKN | ~15.97 GB (14.88 GiB) |
| Serialized RDF (transformable corpus) | 10.6–19.6 GiB depending on resolver |
| Working set per largest record | < 300 MiB RSS (single process) |

Triple-store disk amplification, backup retention, download bandwidth and
network time are not measured here.

## 5. Limitations and discovery gaps

- **No operational budget.** No deployment resource budget or acceptance
  threshold exists in the repository, so no scope can be declared acceptable
  from this report alone.
- **Fail-closed segment.** 677 Dáil/Seanad records, overwhelmingly dated
  2004–2007 (96% of the house records in those years), fail closed on source
  duplicate eIds, and five 2012 records fail RDF validation on empty section
  names. Any production ingestion would quarantine these unless a separately
  approved source/identity remedy is adopted; that remedy is outside this
  measurement task.
- **Written answers are not a single corpus.** 2004–2012 written answers exist
  only as section-level AKN (193,687 files, ~5.43 GB) that are not complete
  Work sources; whole-record `main.xml` exists only from 2012 onward (complete
  from 2013). Written answers also need the questions API because sitting-date
  derivation alone found a whole-record file the questions API omits
  (2018-03-07).
- **API caps and incompleteness.** `/v1/questions` caps `questionCount` and
  `skip` at 10,000 (monthly enumeration used), and the broad `/v1/debates`
  count is capped (calendar-year sums used). One duplicate debate record and
  six transient fetch failures were observed and resolved. The API listing is
  not treated as a complete manifest of Work/Expression objects.
- **One fetched Expression per Work** does not prove global Expression
  completeness; the transformer's `known_expression_source_uris` fail-closed
  behaviour for multiple Expressions was not exercised across the corpus.
- **Sampling error.** Runtime/RDF rates come from 60 random files per category;
  the decile method uses all known sizes but still relies on sampled rates in
  each size band, and the era scan runtime was re-measured on an idle host.
- **Not covered:** SHACL/competency validation and cross-dataset owner
  resolution (Tranche 3), publication/Fuseki costs, retry/quarantine policy
  overhead, and persistence policy for the generated reference report.

## 6. Scope recommendation

The measurement half of the production-scope gate is complete; the gate itself
cannot be closed because no operational acceptability threshold exists yet.

- Neither **full-corpus** nor **Bill-debates-first** can be declared
  acceptable or unacceptable from measured cost alone.
- If a scope decision is taken before a threshold is defined, note that
  Bill-debates-first is not a small pilot: it is ~50% of records and ~73% of
  debate XML bytes, and it retains ~84% of the quarantined records.
- The intended full corpus also cannot be processed completely today: 682
  observed records (mostly 2004–2007 Dáil/Seanad) are quarantined by source
  duplicate eIds or empty section names, and pre-2013 written answers lack a
  transformable whole-record source.
- Full-corpus transformation itself is modest on the measured host (order of
  one hour of single-process transform for the whole transformable corpus;
  serialized RDF of ~10.6–19.6 GiB; raw XML of ~9.82–14.88 GiB depending on
  fragment retention). The material open questions are the quarantine remedy
  for 2004–2007, the written-answer fragment decision, and the operational
  budget.

The production corpus gate therefore remains **open**, pending an operational
acceptability threshold and a separately approved disposition for the
quarantined and fragment-only segments. This report does not begin Tranche 3,
implementation changes, or production ingestion.

## Reproducing

```text
.venv/bin/python -m tools.debates_benchmark census --cache /tmp/oireachtasontology/debates-census
.venv/bin/python -m tools.debates_benchmark head --cache /tmp/oireachtasontology/debates-census
.venv/bin/python -m tools.debates_benchmark fragments --cache /tmp/oireachtasontology/debates-census
.venv/bin/python -m tools.debates_benchmark sample --cache /tmp/oireachtasontology/debates-census
.venv/bin/python -m tools.debates_benchmark bench --cache /tmp/oireachtasontology/debates-census --selection strata --repeats 3
.venv/bin/python -m tools.debates_benchmark bench --cache /tmp/oireachtasontology/debates-census --selection random --members members_all.json
.venv/bin/python -m tools.debates_benchmark era --cache /tmp/oireachtasontology/debates-census --start-year 2004 --end-year 2012
.venv/bin/python -m tools.debates_benchmark report --cache /tmp/oireachtasontology/debates-census
```

`bench`/`era` record the loaded transformer file path and SHA-256 in their
output. The census and HEAD steps require network access; `bench` and `report`
are offline. `members_all.json` is the concatenation of `/v1/members` pages
(`limit=1000`, then `skip=1000`). Run `era` on an otherwise idle host when
exact per-record timing is needed (six parallel shards reproduce throughput
faster but inflate elapsed times through CPU contention; `--shard N --shards
6` from separate processes shards the scan).
