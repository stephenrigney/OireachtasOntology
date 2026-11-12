# OireachtasOntology NLQ — Live K + R Composition Evaluation

> Persistence note: freeze, HEAD, working-tree and no-commit statements below
> describe the completed evaluation before the user subsequently authorised
> committing and pushing these evaluation artifacts. The implementation freeze
> remains `e98296ef2d89a07810c3b0f3f801c99f76636ae7`; the persistence commit
> adds only evaluation documentation, evidence, tools and transport tests.

**PASS — the frozen kernel correctly composed current Committee of Public
Accounts membership with current Kildare North representation at
`asOf=2026-11-11`.** Exact recorded identities: **Aidan Farrelly; Joe Neville**.
Both supporting relationship pairs and all required evidence matched the
independently acquired live RDF. No kernel changes were made.

This is a **new live-evidence evaluation**, not a repaired/passed original
withheld replay. The K+R topology was previously disclosed, not unseen.

## 1. Freeze and environment

Repository/worktree/branch matched the request; initial working tree was clean.
HEAD remains `e98296ef2d89a07810c3b0f3f801c99f76636ae7` on
`feat/nlq-bounded-composition-kernel`. All **81 recorded hash comparisons**,
Python **3.13.15**, and the exact **40-distribution** inventory matched the
frozen environment. See [environment.json](environment.json).

| Frozen artifact | SHA-256 |
|---|---|
| Kernel | `0560acf2b813fdf04f237e09522dcc02b60d99700bdc66cef410948609dd5d06` |
| Configuration | `f9e7dd750322e1b137144a56c7eb15332382b9740990bceaf3e3467189fcbe12` |
| Original replay/evaluator | `5d3909bec1058864f6f6219e6a7de3ced729971dfc9abf8b791fbc7835317947` |
| Dependency lock | `1e0c7ed9f05ee55ce64ead98fa76eff24f6de1028d5e0e9e9a209429073c9eec` |

The original offline configuration was not rewritten. The separately identified
[live transport](../../../../tools/nlq_composition_live.py) injects HTTP SELECT
and lexical typed-RDF decoding into the existing `execute` interface. It sends
queries unchanged; no expected identities, joins, compensating facts or
relationship-specific logic occur in that transport. Supplemental live settings
and pre-execution tool/oracle hashes are in the environment artifact.

## 2. Live dataset and independent oracle

Endpoint: `http://localhost:3030/houses/query`; Fuseki **5.1.0**, container
`249847a5776858b629bfca2406a279fcfd0ea37f1838dd593b95744a00b14076`, image
`sha256:b1d0c96f19adddef417520184471ac816cf36c6e72936a88ea02b29f4305929a`.
The `oireachtasontology_fuseki-data` volume contains `/fuseki/databases/houses`;
the read-only inspected [service configuration](fuseki-houses.ttl) is retained.
The fixed provenance graph contained **0 triples**: loaded source/run identity
and upstream publication completeness could not be established.

[Independent oracle](oracle/oracle.json), captured **21:01:09–21:01:10 UTC on
2026-11-12**, contains query texts, original typed responses, page/completion
certificates, resource audits and its complete acquisition ledger: **21 SELECTs,
1,003 rows**, each request <=100 rows and 15 seconds. Its diagnostic ceilings
(40 requests/5,000 rows) are separate from, and do not enlarge, kernel budgets.
The oracle tool imports no kernel helpers. Oracle SHA-256:
`1003368b9436377bcaac76de5afdd6b1be970cc539c9fe046d64a3e938e3f067`.

- All **34 typed Dáil terms** and their periods establish uniquely current Dáil
  34. All **three matching committee incarnations** were audited; only the
  requested Dáil-34 incarnation and its own owner interval/term are current.
- **K:** 15 CommitteeMembership candidates, 13 current witnesses. **R:** five
  DailMembership candidates, all five current. Candidate discovery precedes
  type/date/reverse-link validation; missing display fields cannot hide candidates.
- Their exact-Member intersection is:
  `https://data.oireachtas.ie/ie/oireachtas/member/id/Aidan-Farrelly.D.2024-11-29`
  and `https://data.oireachtas.ie/ie/oireachtas/member/id/Joe-Neville.D.2024-11-29`.
- No party condition, invented K parliamentary-containment predicate, or
  cross-path HouseTerm equality is applied. R's membership and constituency
  occurrence independently share their exact own term.

All **16 scoped query result multisets** were identical in the separate post-run
stability capture: [comparison](stability-comparison.json). Sequential stable
captures are not a transactional snapshot, complete dataset identity, source
coverage certification or real-world roster.

## 3. First execution and complete SELECT ledger

The first live run was preserved **before scoring** at **21:06:06 UTC**:
[first-execution.json](first-execution.json), SHA-256
`3d2ef191de6d51b5174b475c98ef75c5d5d67942662d41f0578677913445bf5c`.
It retains original/candidate intent, actual output, every complete query,
typed result row, raw HTTP body, source witness, timing and budget charge.
[select-ledger.json](select-ledger.json) provides request/query hashes.

| # | Lookup | Raw rows | Offset | Completion | Timeout |
|---|---|---:|---:|---|---:|
| 1 | All Dáil/Seanad terms | 65 | 0 | Short page | 15 s |
| 2 | Committee resolution | 6 | 0 | Short page | 15 s |
| 3 | K memberships | 15 | 0 | Short page | 15 s |
| 4 | Constituency resolution | 1 | 0 | Short page | 15 s |
| 5 | R memberships | 5 | 0 | Short page | 15 s |

All five requests returned HTTP 200, fully parsed Results JSON, and <100 rows
(92 raw rows total);
no completion page was needed. Maximum measured request: **0.059 seconds**;
maximum query: **1,848 characters**. Two selections; five of eight request
charges; maximum raw page 65; validated primitive sets 15/5; binding stages
**13 → 2**; final witness tuples **2**, all below the 100-tuple ceiling.

## 4. Identity, temporal, provenance and witness comparison

[Independent raw-RDF assertion scoring](comparison.json) matched **all 20
validated relationships, 387 required fact assertions and 55 intervals**, including
nonqualifying candidates. The projected answer retains **two exact K/R witness
pairs**, with **74 fact assertions and 10 intervals**. Member/relationship/term
binding kinds, exact resources, range identities, original typed endpoints and
owner graphs match; no required witness alternative is omitted.
An [independent outcome review](oracle/outcome-review.json), using the raw
captures rather than trusting the scorer, confirmed every fact occurrence,
interval and witness pair, plus pre/post stability: **PASS; no discrepancy**.

For each selected Member, let `H` be their exact Member IRI plus `/house/dail/34`.
R's relationship is `H`, with range `H#date-range`. K's relationship is
`H#committee-membership-` plus the following hash; its range appends
`#member-date-range`:

| Member | Committee episode hash | K start | R start |
|---|---|---|---|
| Aidan Farrelly | `7a2d9746a8c5bcd6f35632c508fe12088e51dce5270a016d79a9e5e5a7e9ad86` | `2025-05-07T00:00:00` | `2024-11-29T00:00:00` |
| Joe Neville | `9870c9b8b2956a07259682c60f6134c2629a885a3fabaf577e5077f7f618b22e` | `2025-05-07T00:00:00` | `2024-11-29T00:00:00` |

All are original `xsd:dateTime` values with absent ends, not invented permanent
service. Member evidence belongs to each exact `https://data.oireachtas.ie/graph/member/`
plus asserted Member code. K targets
`https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts`;
its `#committee-date-range` starts `2024-12-18T00:00:00` in `graph/committees`.
R targets
`https://data.oireachtas.ie/ie/oireachtas/house/dail/34/constituency/Kildare-North`
in `graph/constituencies`. Both observed terms are
`https://data.oireachtas.ie/ie/oireachtas/house/dail/34`, whose `#term-period`
starts `2024-11-29T00:00:00` in `graph/houses`; no end is recorded. All graph
suffixes above are under `https://data.oireachtas.ie/`. Each relationship,
committee owner and own term independently contains the pinned calendar day.

The ended committee episodes for Catherine Ardagh (`2026-05-28T00:00:00`) and
Catherine Connolly (`2025-10-25T00:00:00`) were validated then excluded, not lost
through retrieval filtering or rescued by other relationships.

## 5. Controls and verification

[Seven controls](control-summary.json) passed; full SELECT/typed-result ledgers
are in [controls.json](controls.json). These are explicitly synthetic **offline
transport controls over the new live pages**, not live RDF edits or the old
43-control replay:

- Reversed rows plus duplicates: exact structured/rendered answer, validated
  witnesses and intermediate counts unchanged; raw pages **66, 7, 16, 2, 6**.
- Missing required start, incomplete page, 101 raw rows and injected timeout:
  native kernel nonanswers, no partial factual answers.
- Eight full 100-row pages: native paginator charged offsets **0..700** and
  refused the ninth request. No budget relaxation or pre-dedup escape.
- Added K/R term equality: semantic rejection before retrieval, zero requests.

No new live 100-tuple join-cap stress test or actual 15-second delay was run.
The natural execution fits those ceilings; unchanged existing tests are separate
regression evidence, not substitute claims of new live boundary coverage.
[Verification](verification.json): ontology/HermiT **passed (2,586 triples)**;
repository suite **2,589 passed, 30 skipped**; focused transport **12 passed**.
The full suite collected before the twelfth transport-only test was added;
the focused run includes it. All 133 frozen kernel tests were in the full run.
Skipped checks remain unverified.

## 6. Limitations and evaluation corrections

Before any kernel execution, new oracle analysis errors were corrected: simple
literal/member-code handling, reversed K/R labels, and inadequate current-owner
resolution scope. The three superseded captures remain verbatim in
`oracle/attempts/`; they are not scored baselines. A preliminary revised oracle
tool also raised `NameError` before writing a capture; it was corrected before
the valid baseline. These were **new evaluator defects**, not missing live facts,
changed expected identities, original-package repairs or kernel failures.
The independent scorer's target-input pinning and projection-alias checks were
also completed before the first kernel run. No kernel failure was encountered.
The independent review also corrected its own duplicate-period row counting to
RDF fact-set semantics; neither capture bytes nor kernel results changed.

This covers one known topology/parameter set and list projection. It does not
establish unseen-topology performance, English admission, arbitrary relations,
cross-term positive behavior, scalability, complete-source answers, exhaustive
adversarial safety or production readiness. Both observed path terms happen to
be Dáil 34; inspection and the equality-mutation control establish no added
cross-path equality, not a live differently-termed positive.

## 7. Architectural conclusion

The executed path reused the frozen **K and R role-local adapters**, existing
typed exact-Member **`bind`**, and evidence-preserving **`project`**, through
ordinary experimental **`execute`**. There was **no combination-specific
compiler, validator, executor, projector, query template or primitive added**.
The parameter input and expected-result scorer are evaluation data/logic, not
candidate logic. See [source inspection](architecture-inspection.json) and
[independent transport review](transport-review.md).

The demonstrated generalisation is **bounded reusable composition of a different
pair of existing relationship primitives**, relative to development R+P and K+P,
on independently verified live RDF without kernel edits. Architectural reuse,
observed correctness and production readiness remain distinct. New post-freeze
evaluation tooling is disclosed; strict original frozen-harness/withheld credit
is not claimed. No production `/ask` integration, ontology/ETL/Fuseki mutation,
existing-test change, kernel correction, commit, merge or deployment occurred.
All retained evidence and evaluation-source commitments are indexed in
[SHA256SUMS.json](SHA256SUMS.json); post-run frozen checks are in
[final-integrity.json](final-integrity.json).
