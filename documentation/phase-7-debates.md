# Phase 7 — Debates vertical slice

## Status

Design complete. Implementation has not started.

This note records the approved Phase 7 design for the Debates vertical slice.
It complements the ontology-specific material in
`documentation/debates_ontology_outline.md` and `ontology/debates.owl.ttl`.

## Scope and source

- Akoma Ntoso (AKN) XML is the authoritative source format.
- The intended corpus covers Dáil, Seanad, committees and written answers,
  subject to an implementation-time volume/resource gate.
- The implementation must first measure realistic source volume, storage and
  processing cost. If full-corpus ingestion is disproportionate for the
  initial delivery, the first production scope may be restricted to Bill
  debates without changing the semantic design.
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

Implementation must audit representative Dáil, Seanad, committee and written
answer records against that baseline before changing ontology semantics.
Ontology changes remain subject to the repository semantic-contract approval
boundary.

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

Use one replaceable authoritative named graph per debate record/sitting. The
graph owns the debate resources derived from that AKN record, including its
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
- required debate-record/sitting dates and containment relationships;
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
- AKN `answer` and `rollCall` constructs not yet evidenced by the reviewed
  representative corpus.

## Implementation tranches

### Tranche 1 — Source contract, mapping and fixtures

- Audit representative Dáil, Seanad, committee and written-answer AKN records.
- Measure corpus volume/resource cost and apply the full-corpus versus
  Bill-debates-only implementation gate.
- Define the Debates mapping specification.
- Finalise the URI normalization rule, source-ordinal representation and
  unresolved-reference evidence representation.
- Preserve representative fixtures and expected RDF.
- Make only ontology changes demonstrated necessary by source evidence.

**Exit:** source coverage, mapping, identifiers, ownership and fixtures are
stable enough for deterministic transformation.

### Tranche 2 — Core debate transformation

- Implement record/expression/sitting transformation.
- Implement nested sections, speeches, summaries and lightweight source order.
- Implement questions and divisions/votes as Debates-owned resources.
- Exclude transcript text.
- Add deterministic/golden tests across representative source types.

**Exit:** representative AKN records transform deterministically into the agreed
Debates structure without transcript text.

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

- the agreed source scope can be processed within the accepted resource gate;
- AKN source is preserved and replayable;
- generated RDF is deterministic and contains no transcript text;
- questions and divisions/votes are owned by the debate graph;
- cross-resource links respect existing RDF ownership;
- unresolved references fail safe and remain auditable;
- representative Dáil, Seanad, committee and written-answer fixtures pass
  validation, or an explicitly recorded Bill-debates-only initial scope has
  been selected by the resource gate;
- graph replacement is idempotent and removes stale debate-owned triples; and
- the agreed competency queries pass.
