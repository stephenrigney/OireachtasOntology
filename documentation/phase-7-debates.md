# Phase 7 — Debates vertical slice

## Status

Tranches 1 and 2 are complete. The deterministic representative-fixture
transformer and independent RDF acceptance are verified; Tranche 3 may start.
The production-corpus resource benchmark required before broad ingestion has
been measured and is reported in
[`debates-production-benchmark.md`](debates-production-benchmark.md); the
production-scope choice and gate remain open pending an operational
acceptability threshold. This does not claim broad cross-dataset
reconciliation, SHACL/competency acceptance, ingestion or graph publication.

This note records the approved Phase 7 design for the Debates vertical slice.
It complements the ontology-specific material in
`documentation/debates_ontology_outline.md` and `ontology/debates.owl.ttl`.

## Scope and source

- Akoma Ntoso (AKN) XML is the authoritative source format.
- The intended corpus covers Dáil, Seanad, committees and written answers for
  Tranche 2 representative transformation.
- A separate production-scope gate does not block Tranche 1 or Tranche 2. The
  in-scope corpus (including written-answer XML) has been censused and
  benchmarked after the core transformer; see
  [`debates-production-benchmark.md`](debates-production-benchmark.md). The
  full-corpus versus Bill-debates-first choice is still pending an operational
  resource threshold, and this choice does not change the semantic design.
- The Debates slice owns parliamentary questions and divisions/votes found in
  the AKN debate record. They are not separate Phase 7 publication owners.
- Raw AKN source must be preserved so the RDF can be regenerated and source
  structure can be inspected independently of the graph.

## RDF content boundary

The graph represents debate structure and semantics, not the transcript text.

In scope are the debate record/sitting, sections, speeches as contribution
resources, summaries as structural/procedural resources, parliamentary
questions, divisions/votes, participation metadata, dates, source ordering and
cross-dataset links.

Committee `rollCall` is evidenced, but its attendance entries remain source-only
in the initial RDF scope; they are not divisions, votes or speech participation.

The spoken/written transcript text itself is not copied into RDF.

Future topic/keyword extraction from debate text is explicitly deferred. Such
derived topic assertions may later be added to the graph without making raw
transcript text part of the authoritative Debates RDF model.

## Existing ontology baseline

The existing Debates ontology remains the starting semantic model:

- `DebateRecord` / `DebateExpression`;
- `DebateSitting`;
- nested `DebateSection`;
- `Speech` and `Summary`;
- `ParliamentaryQuestion`;
- `Division`;
- ELI-DL participation, legislative-activity and vote alignment.

Written-answer Works are `DebateRecord`s with their date and structure, but do
not receive a `DebateSitting`: a written-answer publication does not itself
evidence a sitting activity. Emit a sitting only for a non-`writtens` Work when
the approved `FRBRname`/Work-path rule identifies an actual sitting; type
disagreement or an unreviewed type fails closed for sitting emission.

Representative Dáil, Seanad, committee and written-answer records have been
audited. The I1/I2/O1–O8 semantic decisions are approved, and their Debates
ontology/mapping additions pass static verification under the repository
semantic-contract boundary. Representative runtime transformation and RDF
acceptance are implemented in Tranche 2; general integration and publication
remain later work.

## Identifier policy

- Prefer stable AKN identifiers/eIds as the source of resource identity.
- Public RDF IRIs must use one documented deterministic URI-safe
  normalization/encoding rule rather than copying awkward XML identifier
  syntax directly.
- In particular, raw ampersands and other URI-problematic characters should
  not be carried verbatim into public IRIs where a stable normalized or
  percent-encoded representation can be used.
- Preserve the original AKN identifier as source evidence where required for
  traceability.
- Where no stable AKN identifier exists, use a deterministic content/context
  derived identifier or hash.
- Array/document position alone must not be the resource identity.

The approved exact Work, Expression, eId, fallback and graph formulas are in
[`debates-identity-contract.md`](debates-identity-contract.md). In brief, derive
Work and Expression IRIs from their own `FRBRuri/@value` paths by UTF-8
component-wise RFC 3986 percent encoding; derive the replaceable graph IRI by
replacing the once-encoded Work path prefix `/akn/ie/debateRecord` with
`/graph/debate` without encoding the path a second time. Use `{work IRI}#sitting`
only for an eligible actual sitting. Known multiple Expressions for one Work
fail closed for that Work rather than publishing a graph from one Expression
alone; one fetched file does not prove global Expression completeness.

## Ordering

AKN XML remains authoritative for complete document order and reconstruction.
RDF itself is unordered, so XML node order does not survive transformation
unless represented explicitly.

Where ordering is useful for graph queries, addressable debate components
should therefore carry a lightweight integer source ordinal within their
containing scope. This should cover sections and contribution-like resources
where sequence has meaning, without introducing RDF lists, linked-list
properties or a parallel reconstruction model.

The ordinal is ordering metadata, not resource identity.

## Cross-resource resolution

Where the AKN record identifies an entity already owned elsewhere in the
dataset, the Debates transformer references the existing resource rather than
re-describing it. This includes, where applicable:

- Members and parliamentary memberships;
- Houses, HouseTerms and committees;
- ministerial offices/roles;
- Bills, BillEvents, LegislativeProcesses and ProcessStages.

A source reference that cannot be resolved must not cause a speculative
placeholder entity to be invented. Preserve the unresolved source reference
and evidence in an auditable form, report it for review, and allow later
reprocessing to resolve it.

## RDF ownership and graph boundary

Use one replaceable authoritative named graph per Work/debate record. If the
source establishes an eligible sitting, it belongs in that same graph; a
written-answer Work still has a record graph but no DebateSitting. The graph
owns the debate resources derived from that AKN record, including its
questions and divisions/votes.

Cross-dataset resources remain owned by their established endpoint/vertical
slice. The Debates graph links to them by IRI only.

Complete graph replacement is preferred to triple-level mutation.

## Refresh boundary

Phase 7 Debates owns the endpoint-specific mechanics needed for safe refresh:

- stable source identity;
- immutable AKN preservation;
- source hashing/change detection;
- deterministic transformation;
- the ability to process or replay an arbitrary debate record; and
- atomic replacement of its named graph.

Phase 6 owns production refresh policy and operations, including scan cadence,
rolling windows, periodic full reconciliation, scheduling, retry policy and
deployment defaults. Those operational choices must not be hard-coded into the
Debates transformer.

## Validation and competency contract

Validation should be structural and cross-dataset rather than an attempt to
replicate the complete AKN XML schema in SHACL.

At minimum, implementation should validate:

- deterministic identity and graph ownership;
- required Work dates and, for eligible non-written records only, sitting dates
  and containment relationships;
- valid source ordinals within their containing scope;
- Member/House/HouseTerm/committee references where resolvable;
- legislative-section links to Bills/events/processes/stages;
- question ownership and participant/role references;
- division outcome, aggregate counts and recorded individual votes where the
  source supplies them;
- unresolved references are explicit/auditable rather than silently invented;
  and
- publication never leaks transcript text into the RDF dataset.

Competency queries should demonstrate at least:

- debate records/sittings for a House or committee and date;
- ordered sections/contributions within a debate;
- contributions associated with a Member;
- questions asked by a Member and the role to which they were directed;
- divisions, outcomes and recorded Member votes; and
- debate sections associated with a specified Bill or legislative event.

## Deferred work

Deferred unless source evidence shows they are structurally required for the
initial slice:

- transcript text in RDF;
- topic/keyword extraction from transcript text;
- full FRBR Manifestation modelling;
- inline amendment entity markup;
- image and table content;
- bilingual-heading deduplication;
- AKN `answer` modelling (not observed in the reviewed fixtures); committee
  `rollCall` attendance RDF, which is evidenced but deferred from the initial
  RDF scope.

## Implementation tranches

### Tranche 1 — Source contract, mapping and fixtures

- The approved semantic/source contract, mapping, exact identity/graph rules,
  source ordering and unresolved-reference outcomes are defined and statically
  checked.
- Representative Dáil, Seanad, committee and written-answer AKN sources have
  been preserved and audited; ontology/mapping changes were checked against the
  approved review.
- Representative immutable source fixtures are recorded. Expected RDF goldens
  are exercised with transformation tests in Tranche 2.

**Exit:** approved semantics are reflected in the ontology/mapping and verified;
the source, mapping, identity, ownership and reference-outcome contract is stable
enough to implement deterministically. The production resource gate is not a
Tranche 1 exit criterion.

The ontology reasoner, mapping-integrity and source/fixture checks pass, as do
the 28 focused Debates tests and the full repository suite (427 passed,
8 skipped). This verifies the Tranche 1 static contract, not runtime RDF
emission; those goldens belong to Tranche 2.

### Tranche 2 — Core debate transformation

- Implement record/expression/sitting transformation.
- Implement nested sections, speeches, summaries and lightweight source order.
- Implement questions and divisions/votes as Debates-owned resources.
- Exclude transcript text.
- Add deterministic/golden tests across representative Dáil, Seanad, committee
  and written-answer sources.

Tranche 1 tests are static contract checks over ontology terms, mapping rows and
source fixtures; they do not execute a transformer or prove RDF non-emission.
Tranche 2 goldens must inspect actual transformed RDF and assert both supported
output and required absences, including no `#declared` carried/lost outcome, no
placeholder/link for unresolved references, no Division/vote/participation from
committee `rollCall` attendance, and no transcript literals.

**Clarified 2026-10-04:** the committee `rollCall/summary[@eId='sum_2']` is
source-only too: emit no Summary or `:sourceOrdinal` for that node. The active
CSV class selector `debateBody//summary` is broader than this reviewed
source-only exception; do not silently treat that selector as permission to
emit an orphan Summary. A protected mapping-selector correction remains a
separate semantic-contract follow-up; the Tranche 2 RDF golden pins the
clarified exclusion without editing the CSV.

**Exit:** representative AKN records transform deterministically into the agreed
Debates structure without transcript text.

The Tranche 2 transformer, non-RDF source-hash/reference report, RDF-only
structural validator and independent expected-RDF subset goldens cover all five
preserved Dáil, Seanad, committee and written-answer records. Fixture tests
compare complete structural containment and order, fixed class/count/outcome
expectations, explicit source-only/unsupported absences and repeated sorted
named-graph output. Owner-link tests use checked-in Member/House owner evidence
and leave unsupported historical terms, the Committee author and question
recipients unresolved. Neither the limited example owner set nor one fetched
AKN file proves general owner or Expression-set completeness. The production
resource gate remains open before broad ingestion; Tranche 3 owns broader
cross-dataset resolution, SHACL and competency acceptance.

The census/benchmark for the full-corpus versus Bill-debates-first production
choice was run after the core transformer existed and is recorded in
[`debates-production-benchmark.md`](debates-production-benchmark.md). It
measures total in-scope XML volume (including `writtens`), runtime and RDF
output (and required working/storage volume). The scope choice has not been
made: no operational resource budget/threshold is defined in the repository,
and the measurement also found quarantine and source-fragmentation limits
(2004–2007 duplicate-eId records; pre-2013 written answers lacking a
whole-record source) that need separate disposition. This gate does not delay
Tranche 1 or representative Tranche 2 implementation. Phase 6's scan cadence,
scheduling and reconciliation policy remain unchanged.

### Tranche 3 — Cross-dataset integration and validation

- Resolve Members, Houses/HouseTerms/committees, ministerial roles and
  legislative resources to their existing IRIs.
- Implement fail-safe unresolved-reference reporting/evidence.
- Add SHACL and semantic-quality validation.
- Add competency queries and graph-boundary tests, including vote consistency
  where supported by source data.

**Exit:** debate graphs integrate safely with the existing dataset and pass the
agreed structural, semantic and ownership checks.

### Tranche 4 — Source ingestion, state and publication mechanics

- Add AKN acquisition/raw preservation through the normal ETL path.
- Persist source identity and hashes needed for change detection/replay.
- Add per-record graph replacement, idempotency and replay tests.
- Integrate CLI/run-state behaviour with the existing ETL application.
- Demonstrate reprocessing of changed supplied records without defining a
  production scanning schedule.

**Exit:** Debates can be extracted, preserved, transformed, validated and
atomically republished through the normal ETL path. Phase 6 can later apply
production scanning/scheduling policy without changing the Debates semantic
model.

## Phase 7 Debates exit criteria

The Debates slice is complete when:

- the measured production scope (full corpus or Bill-debates-first) can be
  processed within accepted resource budgets;
- AKN source is preserved and replayable;
- generated RDF is deterministic and contains no transcript text;
- questions and divisions/votes are owned by the debate graph;
- cross-resource links respect existing RDF ownership;
- unresolved references fail safe and remain auditable;
- representative Dáil, Seanad, committee and written-answer fixtures pass
  validation for Tranche 2, regardless of when the later production-scope gate
  selects full-corpus or Bill-debates-first ingestion;
- graph replacement is idempotent and removes stale debate-owned triples; and
- the agreed competency queries pass.
