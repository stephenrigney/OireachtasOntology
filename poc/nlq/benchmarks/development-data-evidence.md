# Query Service development-data evidence (updated 2026-10-16)

## Outcome and boundary

This note records local source evidence for a later Query Service
development-bootstrap decision. The Bills section documents the accepted ETL
lifecycle correction and complete-capture selector; neither it nor the Debate
evidence expands the development bootstrap or claims production/authoritative
dataset coverage. The exact three-Work Debate selection is in
[`development-source-selection.json`](development-source-selection.json). Raw
XML and API pages remain outside Git in the immutable local raw store.

## Debates: preserved and replayed

The three official AKN `main.xml` objects in the selection manifest were
available locally and were replayed with `--offline --replay` in two independent
batch runs. The emitted N-Quads were byte-identical; both had SHA-256
`9ba5fa87067e819c5dc01a5049f21f7f99d1f385d631bbb509f5c0c933591cdb`.
Their raw-object hashes, byte lengths, Work IRIs and graph IRIs are pinned in
the manifest. Each reference report explicitly leaves global Expression-set
completeness unasserted: one fetched Expression does not prove that a Work has
no other Expressions.

This is a small evidence selection (Dáil and Seanad records from 2015 and a
committee record from 2026), not a complete or date-representative corpus. The
objects can be replayed when present in the local raw store, for example:

```text
oir-etl run debates --replay 720bf72e40ed824c9d01efc8a919713e524e6b058794e75fab56c20b6858fff5 --offline
```

## Bills: lifecycle correction accepted (2026-10-14; fresh capture 2026-10-13)

The original ETL run `dbaf2d97-deab-477a-b359-972c769fb3e5` (2026-10-09)
remains recorded as failed: before the lifecycle correction, transformation
stopped on the then-unsupported `bill-lapsed` event URI. Its complete raw API
capture is still valid immutable source evidence. After the approved Bills
lifecycle correction, both that preserved capture and a fresh complete capture
passed replay and publication acceptance under Bills publication contract v1.
This acceptance does not infer `stageOutcome` or an amendment-list
`ProcessStage` relation for unresolved stage references.

### Preserved capture

The 2026-10-09 capture contains 6,048 records across all 61 pages, at local raw
store key
`legislation/2026-10-09/run-dbaf2d97-deab-477a-b359-972c769fb3e5`. Two offline
replays matched byte-for-byte. The deterministic N-Quads output parsed as
917,254 quads in 6,044 named graphs; its SHA-256 is
`ca575065fc2bc44db2403f1c03f6d4d776ca594b1deb88312a08a3600c2a1202`.
There were four reviewed source quarantines, 26 diagnostic-only unresolved
stage-reference occurrences, and no unexplained transformation or validation
failures.

### Fresh complete capture and preflight

The fresh API capture is run `7bab00fc-4637-463e-a42e-fdb7ce626439`
(2026-10-13), preserved at
`legislation/2026-10-13/run-7bab00fc-4637-463e-a42e-fdb7ce626439`. It contains
the advertised 6,048 records across 61 pages. Preflight found no added or
removed Bill identities, no structural-path/type delta, no unsupported
vocabulary, and no unexplained validation failures. The same four reviewed
source records were quarantined; all other 6,044 Bill graphs were represented.

The fresh capture contains 28 unresolved amendment-list stage-reference
occurrences. Two are additional occurrences for Bills `2026/54` (`/dail/4`)
and `2026/95` (`/dail/3`); both match the existing diagnostic-only pattern.
They remain diagnostics only: no `ProcessStage` relation or `stageOutcome` is
inferred.

### Publication and deterministic replay

All 6,044 represented graphs were published to an empty, disposable Fuseki
dataset and passed per-graph Bill competency and whole-graph verification. The
fresh dataset contains 6,044 named graphs and 917,294 triples. The disposable
Core State records a successful complete legislation run, 6,044 clean rows at
contract version 1, and zero dirty or pending rows. The complete-capture
selector accepts this exact run and all 6,048 source records.

Two fresh offline replays matched byte-for-byte. The N-Quads output is
246,585,209 bytes, parses as 917,294 quads in 6,044 graphs, and has SHA-256
`d884884c08a328a374e402578fc92f57525439a66eb3d6b36cf74d05a064bc66`. Parsing
validated 145,635 unique Bill-owned IRIs against the one-literal-`#` contract.
The four quarantined Bills have neither a Core State row nor a Fuseki graph.
N-Triples/N-Quads serialization now uses RDFLib output with deterministic sorted
lines; other endpoints may consequently produce different payload bytes/hashes
when next republished, without a change to their RDF meaning. No other endpoint
was republished as part of this acceptance.

## Office evidence availability

Reviewed local office evidence was available when inspected read-only:

- the ministerial-office registry contains three offices and one administrative
  unit;
- the office decisions contain three accepted and two unresolved decisions;
- `office-occurrences.sqlite` passed SQLite integrity checking and contains
  1,142 observations and 3,446 attempts.

These are availability facts only. They do not establish new office semantics,
claim full office coverage, or select office evidence for bootstrap publication.
No write to office reconciliation/occurrence state was part of this workflow.
The current timestamps of `member-reconciliation.sqlite` and
`office-occurrences.sqlite` predate the Bills run, but no pre-run
reconciliation-database hash baseline was recorded; therefore a bytewise
before/after comparison for those databases cannot be claimed.

## Isolation and verification record

- The authoritative Core State was opened read-only after the run. Its SHA-256
  remains `edc08ab4d2195269372fd6a184b356d7bd77d589754c0e6f1781f499ff315214`,
  equal to the pre-run value. SQLite integrity is `ok`; it still has 20 runs
  and zero legislation runs/resources.
- Bills acceptance used disposable Core State copies under
  `/tmp/oireachtasontology/bills-complete-capture-20261013/`, not the
  authoritative Core State.
- Fresh publication used the isolated Fuseki container
  `oir-bills-acceptance-run3-20261013`, bound only to `127.0.0.1:13050`. No
  production Fuseki endpoint was configured or modified.
- The selected Debate raw XML objects and the Bills API pages are local
  immutable evidence and are not tracked in Git.

## Deferred work / handoff

1. Decide separately whether and how the three selected Debate sources and the
   reviewed office evidence belong in a development-bootstrap dataset. No such
   bootstrap expansion is implemented or accepted here.
2. This Bills acceptance establishes mapping, publication, and complete-capture
   selector behavior; it does not claim production dataset coverage or expand
   Query Service bootstrap semantics.
