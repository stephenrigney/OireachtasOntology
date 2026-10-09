# Query Service development-data evidence (2026-10-09)

## Outcome and boundary

This note records preserved local source evidence for a later Query Service
development-bootstrap expansion. It does **not** implement that expansion,
change capture selection, establish new ontology or mapping semantics, or claim
production/authoritative dataset coverage. The exact three-Work Debate selection
is in [`development-source-selection.json`](development-source-selection.json).
Raw XML and API pages remain outside Git in the immutable local raw store.

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

## Bills: acquisition failed acceptance; do not treat as a successful capture

Run `dbaf2d97-deab-477a-b359-972c769fb3e5` (2026-10-09) used the copied
evaluation Core State and reached all 61 API pages, with 6,048 records
advertised and 6,048 records harvested/deduplicated. The pages and metadata are
preserved in the local raw store at relative key
`legislation/2026-10-09/run-dbaf2d97-deab-477a-b359-972c769fb3e5`.
However, the ETL run is **failed**, not a successful complete API scan: the
transformation stopped on the official event URI
`https://data.oireachtas.ie/ie/oireachtas/def/bill-event/bill-lapsed` before
the Bill publication loop. The copied Core State contains six observed
legislation resource rows from the failed run; none has a published payload.
No Bills RDF was published.

The source has 1,491 `bill-lapsed` event occurrences. Other observed event URI
suffixes not supported by the current `transforms/bills.py` `EVENTS` table are:

| Event URI suffix | Occurrences |
| --- | ---: |
| `admissibility-for-introduction` | 333 |
| `approved-for-initiation` | 156 |
| `bill-defeated` | 293 |
| `bill-lapsed` | 1,491 |
| `bill-restored` | 217 |
| `bill-withdrawn` | 180 |
| `other-procedural-event` | 1 |
| `recommittal` | 2 |
| `referendum` | 35 |
| `referral-to-supreme-court-art-26` | 16 |

`EVENTS` currently accepts only `published` and `enacted`. The active mapping
row for `eventURI` specifies a controlled Bill-event `ActivityType`, but does not
settle the intended identities for these source event types. Semantic review of
the mapping/ontology is required; this work did not drop events, infer a
replacement, edit the transformer, or retry the Bills run. The raw acquisition
does not satisfy the requested successful-complete-capture prerequisite.

Separately, `raw_captures.py` currently defines complete/development capture
count fields only for Houses, Members, Parties and Constituencies. It does not
support the `legislation` endpoint's `billCount`, so selector acceptance for a
future Bills development bootstrap remains unverified. This note does not add
that support.

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
- The ETL run used the SQLite-backup copy at
  `~/.local/share/oireachtas-etl/query-service-evaluation/core-state.sqlite`
  (mode `0600`), not the authoritative Core State. Its Bills run is failed as
  recorded above.
- The disposable Fuseki container `oir-query-service-eval-bills`, bound only to
  `127.0.0.1:13045`, has been stopped and removed. No production Fuseki endpoint
  was configured for the Bills run. Other unrelated local service containers
  were left untouched.
- The selected Debate raw XML objects and the Bills API pages are local
  immutable evidence and are not tracked in Git.

## Deferred work / handoff

1. Obtain semantic review for the unsupported official Bill event types before
   any retry; do not reinterpret or discard them to force success.
2. In a later approved tranche, extend Bills complete-capture selection only
   after the successful-complete Core State contract is implemented and tested.
3. Decide separately whether and how the three selected Debate sources and the
   reviewed office evidence belong in a development-bootstrap dataset. No such
   bootstrap expansion is implemented or accepted here.
