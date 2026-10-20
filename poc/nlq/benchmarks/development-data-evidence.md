# Query Service development-data evidence (updated 2026-10-19)

## Outcome and boundary

This note records the accepted, non-authoritative Query Service development
data surface. The bootstrap selects preserved complete API captures from
[`development-api-capture-selection.json`](development-api-capture-selection.json),
reads the reviewed office inputs, and replays exactly the three Debate sources
pinned in [`development-source-selection.json`](development-source-selection.json).
The machine-readable API pins remove the dependency on a surviving Core State
capture-index snapshot. The bootstrap does not acquire source data, alter Bills
publication contract v1, or claim
production/authoritative coverage. Raw XML and API pages remain outside Git in
the immutable local raw store.

## Phase 2 development-bootstrap acceptance (2026-10-18)

Both acceptance runs used the same preserved inputs and a fresh disposable
Fuseki 5.1.0 dataset bound only to loopback for each run. Each run produced
baseline schema version 1, dataset ID
`sha256:9da63abc5878387f991e4d4717f35cca67606850db34be589e0a8fc0cc1504e2`,
identical source identities and graph/resource counts. The two baseline JSON
files and live-stat summaries matched byte-for-byte. Each live dataset
contained 7,984 graphs and 1,119,470 triples, including the three unrelated
sentinel graphs; the 7,981 bootstrap-owned graphs contained 1,119,467 triples.
The live graph inventory SHA-256 was
`471532a10a3a6e8ecc307d78d6687a3e5abc89a2490eaa194d60d4e3fba2e117` in both
runs.

### Selected API captures

| Endpoint | Successful complete run | Source records |
|---|---|---:|
| Houses | `896630a4-9389-4a8f-bf58-65c16a05425c` | 68 |
| Parties | `91255248-e348-4d60-a8d6-73a26df49f8b` | 11 |
| Constituencies | `e6a472b1-b6e0-4e02-8304-9e6cfa73c44d` | 8 |
| Members | `d2c089d0-5203-40f1-97b8-ae0d8285e74d` | 1,928 |
| Legislation | `7bab00fc-4637-463e-a42e-fdb7ce626439` | 6,048 |

All selected API page hashes are captured in the baseline identity. The office
registry and review inputs were SHA-256
`00f9cc73f8e82fe2560e931b9ac07a605ad27e0f41186017f828db9b381f1d5a` and
`99a2e9f6bc987a53d149e2035c77f31589d553dfb141e4fb43fb8ff56f200ea1`,
respectively.

The committed API selection pins each accepted run ID, official endpoint,
advertised source count, page limit, and a SHA-256 digest over the ordered
`{skip, sha256}` page-hash list. Bootstrap independently verifies raw-page
status, run ID, URL, pagination, body digests, and source-record counts before
use. These pins preserve the accepted complete-capture selection; they do not
promote the development data to authoritative status or write Core State.

### Repeated-bootstrap validation boundary (2026-10-19)

For the exact accepted dataset identity above, the bootstrap reuses the full
per-resource Member/Bill RDF acceptance already recorded by the 2026-10-18
development runs and the Bills publication acceptance below. It still verifies
every raw page and accepted run pin, runs Member/Bill source checks and
deterministic transforms, replays the pinned Debate slice, parses every emitted
N-Triples payload locally, and checks the accepted graph-family, resource,
quarantine, and unresolved-reference counts before publication. After whole-graph
PUTs it verifies each remote graph against its serialized RDF payload and checks
Fuseki's per-graph triple counts and inventory. No generated RDF is cached.

This shortcut is identity-gated: a different dataset ID retains the full
per-resource `validate_member` and `validate_bill` checks. The authoritative ETL
publication paths are unchanged, and the full validators remain exercised by
the ETL test/acceptance suites. The shortcut is only for repeated setup of this
exact local benchmark dataset; it is not a relaxation of source, mapping, RDF,
or production publication acceptance. Offline benchmark-candidate generation
does not use this shortcut and runs the full per-resource validators.

### Realistic-query benchmark bulk-load exception (2026-10-19)

The realistic-query benchmark runner has an explicitly approved, benchmark-only
dataset-level load path. It first performs the pinned-source checks, deterministic
transforms, full per-resource Member/Bill RDF acceptance, accepted-identity/output
checks, deterministic N-Quads serialization, and a full local N-Quads parse. Only
then does it create a new `stain/jena-fuseki:5.1.0` disposable instance bound to
loopback, verify that its sole dataset is empty, and POST the complete N-Quads
dataset once. After loading,
the runner compares the exact remote graph inventory and per-graph triple counts
to candidate evidence, verifies family/resource totals and representative RDF
resources, checks all four quarantined Bill graphs are absent, and reads the
dataset back once to compare every graph's canonical RDF 1.1 semantic hash,
including plain/explicit `xsd:string` equivalence.
The accepted previous live graph-inventory hash is also reproduced by adding the
three known unrelated sentinel graph IRIs to the candidate-owned graph set.

This exception is confined to the realistic benchmark harness and new empty
disposable datasets. Candidate/readback RDF lives only under a temporary
directory. It does not change the normal bootstrap's whole-graph GSP PUT path,
graph identities/ownership, or the atomic whole-graph rule for authoritative
publication. Dataset identity remains derived solely from accepted source and
review evidence, independently of the load transport.

### Loaded graphs and resources

| Graph family | Graphs | Triples |
|---|---:|---:|
| Houses | 1 | 721 |
| Parties | 1 | 1,890 |
| Constituencies | 1 | 7,645 |
| Committees | 1 | 2,799 |
| Administrative units | 1 | 2 |
| Offices | 1 | 13 |
| Members | 1,928 | 179,720 |
| Bills | 6,044 | 917,294 |
| Debates | 3 | 9,383 |
| **Total bootstrap-owned graphs/triples** | **7,981** | **1,119,467** |

The registry contributes three NamedOffice resources and one AdministrativeUnit;
the Member graphs contain 22 accepted OfficeHolding resources. The fixed office
and administrative-unit registry graphs are both present.

The 6,048-record Bills capture produced 6,044 graphs. Four distinct Bills were
quarantined and have no graph: `1959/P3`, `1965/P1`, `1965/P3`, and `2024/48`.
Their reviewed diagnostics contain 28 paths total (9, 9, 9, and 1
respectively). The 28 unresolved amendment-stage references remain diagnostics
only; no stage relationship is inferred.

### Pinned Debate source and graph identities

| Chamber/body and date | Source SHA-256 | Debate Work | Named graph |
|---|---|---|---|
| Dáil, 2015-07-02 | `720bf72e40ed824c9d01efc8a919713e524e6b058794e75fab56c20b6858fff5` | `https://data.oireachtas.ie/akn/ie/debateRecord/dail/2015-07-02/debate` | `https://data.oireachtas.ie/graph/debate/dail/2015-07-02/debate` |
| Seanad, 2015-07-02 | `6e2920af4b97aa0f692162f9fcd94324a18a1c26495399e8600a5ca450d762c0` | `https://data.oireachtas.ie/akn/ie/debateRecord/seanad/2015-07-02/debate` | `https://data.oireachtas.ie/graph/debate/seanad/2015-07-02/debate` |
| Committee of Public Accounts, 2026-09-24 | `690dada15afa1cb76ece7dd8387b973b00b43804023521b9ffb821d8944ff60e` | `https://data.oireachtas.ie/akn/ie/debateRecord/committee_of_public_accounts/2026-09-24/debate` | `https://data.oireachtas.ie/graph/debate/committee_of_public_accounts/2026-09-24/debate` |

Known development-data limitation: offline replay uses an empty owner snapshot,
so source references to Members, Committees, Houses, or HouseTerms remain
unresolved rather than linking to loaded owner graphs. No owner identities are
invented. The three validated Debate graphs do not establish complete Debate or
cross-dataset owner-link coverage. Transcript speech text is not included.

Stale bootstrap-owned Member, Bill, and Debate graphs were removed in each run;
test-only unrelated graphs were preserved. The Core State, reconciliation
databases, registry/review inputs, and complete raw-store hash manifest were
byte-identical before and after. The Fuseki instances were isolated disposable
containers bound to `127.0.0.1:13062`; Docker's anonymous `/fuseki` volumes were
removed with the containers. The before/after non-disposable container inventory
matched. The protected-input manifest SHA-256 was
`ea44744fbd12e0daaa67c778bc9a1b94edd16ca75bd32fa2dc982f988f092c3d`, the raw
store manifest SHA-256 was
`1caac2cf88c331679aa245f81a8229c6851559ad4704dc4d713592ff1721ced1`, and the
non-disposable container inventory SHA-256 was
`460befe53f8df78a5b60a37851bcc8d74eaa78f1c208306eb26c21ffa7506bea`. No
production service was targeted.

## Debates: preserved, replayed, and selected for development

The three official AKN `main.xml` objects in the selection manifest are also
the exact three sources used by the development bootstrap. They were available
locally and were replayed with `--offline --replay` in two independent batch
runs. The emitted N-Quads were byte-identical; both had SHA-256
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

## Office registry and review evidence

Reviewed local office evidence was read without changing its reconciliation
state:

- the ministerial-office registry contains three offices and one administrative
  unit;
- the office decisions contain three accepted and two unresolved decisions;
- bootstrap validation emits 22 current accepted OfficeHolding resources; raw
  unresolved observations do not produce holdings;
- `office-occurrences.sqlite` passed SQLite integrity checking and contains
  1,142 observations and 3,446 attempts.

These facts do not establish full office coverage or authoritative publication.
No write to office reconciliation/occurrence state was part of this workflow.
Unlike the earlier Bills acceptance, this bootstrap acceptance recorded
before/after hashes for Core State, both reconciliation databases, the selected
capture-index copy, office registry/review inputs, and the complete raw store;
the before/after manifests matched.

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

1. Broader Debate coverage and resolution of cross-dataset Debate owner
   references remain deferred. This three-Work slice is only development data.
2. The Bills acceptance establishes mapping, publication, and complete-capture
   selector behavior; it does not claim production dataset coverage or expand
   Query Service bootstrap semantics.
