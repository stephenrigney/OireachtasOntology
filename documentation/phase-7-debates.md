# Phase 7 — Debates vertical slice

## Status

Tranches 1–4 are complete for the bounded representative scope. All links with
reviewed source/owner support are validated; unsupported Bill-event section
and question-recipient competencies remain explicitly deferred, with their
query contracts retained but not counted as positive acceptance. Tranche 4
supplies explicit main.xml acquisition/replay, immutable raw storage, Core
State tracking and opt-in per-Work graph publication; it does not enumerate
or schedule the production corpus.

**Initial production scope approved (2026-10-07):** Dáil, Seanad and
committee debate Works dated **2011-01-01 onward**, with written answers
excluded, without a Bill-linkage filter. The exact inventory of the preserved
2011+ `/v1/debates` census is complete and recorded in
[`debates-production-readiness.md`](debates-production-readiness.md), with its
per-Work source hashes in
[`debates-initial-production-inventory.json`](debates-initial-production-inventory.json).
The corpus benchmark is in
[`debates-production-benchmark.md`](debates-production-benchmark.md);
the separate 2026-10-06 scoped resource assessment informed the selection.
The exact scan found 264 quarantined Works; human dispositions, approval of
proposed operational limits, the completeness-boundary decision, and staged
acceptance remain pending. The inventory is limited to the preserved API census
and does not prove global Work/Expression completeness. Inventory completion
does not close the production-readiness gate or authorize ingestion or graph
publication.

The Tranche 4 scoped resource measurement (2011+ debates only versus adding
2013+ whole-record written answers) is recorded in
[`debates-production-resource-assessment.md`](debates-production-resource-assessment.md).
Its resource measurements informed the approved scope. The complete
non-publishing inventory now supersedes its sampled quarantine estimate; human
exception disposition, operational-limit approval, source-listing completeness
decision and staged operational acceptance remain open. See the
[`Debates production-readiness report`](debates-production-readiness.md) for
the exact counts, measured resource totals and remaining gate decisions.

This note records the approved Phase 7 design for the Debates vertical slice.
It complements the ontology-specific material in
`documentation/debates_ontology_outline.md` and `ontology/debates.owl.ttl`.

## Scope and source

- Akoma Ntoso (AKN) XML is the authoritative source format.
- The intended corpus covers Dáil, Seanad, committees and written answers for
  Tranche 2 representative transformation.
- The approved **first production load** includes all debate subjects for
  Dáil, Seanad and committees from 2011-01-01 onward. It excludes written
  answers, including complete 2013+ written-answer Works. Older debate Works,
  later written-answer ingestion and fragment-only pre-2013 written answers
  are separate expansion items; this does not change the semantic model.
- The all-years census/benchmark is retained in
  [`debates-production-benchmark.md`](debates-production-benchmark.md).
  The exact 2011+ scope inventory is complete (10,913 listed Works, 10,649
  eligible and 264 quarantined) in
  [`debates-production-readiness.md`](debates-production-readiness.md).
  Selecting the initial scope and completing its inventory do not authorize
  ingestion: human exception disposition, operational budgets and Phase 6
  production execution/validation acceptance remain outstanding.
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

**Clarified 2026-10-04; selector corrected 2026-10-06:** the committee
`rollCall/summary[@eId='sum_2']` is source-only too: emit no Summary or
`:sourceOrdinal` for that node. The active CSV class selector now matches that
runtime exclusion: row 25 uses `debateBody//summary[not(ancestor::rollCall)]`,
with the same exclusion on the eId selector in row 26 and the Summary clause of
the ordinal rule in row 49. Ordinary summaries remain mapped. The Tranche 2 RDF
golden independently pins the exclusion.

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
cross-dataset resolution, SHACL and competency checks, with the bounded
evidence review and explicit deferrals recorded below.

The initial all-years and Bill-linked census/benchmark was recorded in
[`debates-production-benchmark.md`](debates-production-benchmark.md).
A subsequent scoped assessment measured the Tranche 4 publication/storage
path and compared 2011+ debates with and without 2013+ complete written
answers. The approved initial selection is **2011+ debates only**, with
written answers deferred. The exact non-publishing census inventory is now
complete: it records 264 quarantined Works and exact source/RDF/report sizes.
Human exception dispositions, configurable operational budgets, accepted
source-listing completeness behavior and staged production acceptance remain
open. Historical-source and pre-2013 written-answer fragmentation findings
remain separate expansion work. Phase 6 retains scan cadence, scheduling and
reconciliation policy. See `documentation/etl-plan.md`'s Debates backlog for
required pre-ingestion actions and reopening conditions.

### Tranche 3 — Cross-dataset integration and validation

- Resolve Members, Houses/HouseTerms/committees, ministerial roles and
  legislative resources to their existing IRIs.
- Implement fail-safe unresolved-reference reporting/evidence.
- Add SHACL and semantic-quality validation.
- Add competency queries and graph-boundary tests, including vote consistency
  where supported by source data.

**Exit:** debate graphs integrate safely with the existing dataset and pass the
agreed structural, semantic and ownership checks.

#### Tranche 3 integration checkpoint (2026-10-05)

The exact-reference resolver can now index source-validated Member, Houses and
Committee owner RDF. It requires an existing, correctly typed owner subject,
uses exact AKN href/owner URI agreement, and takes a House from its HouseTerm's
owner `termOf` assertion. The Committee identity is the consolidated Members
source URI `/ie/oireachtas/committee/{houseCode}/{houseNo}/{slug}`; the former
wiki `{slug}/{term-no}` template was erroneous, not an alias. The checked-in
Committee owner example is a Dáil 33 Finance Committee, **not** the Dáil 34
Public Accounts author in the checked-in AKN example. That author remains
unresolved against this limited example owner set; only a validated owner
record of the exact identity can activate its host link.

Independent SHACL, joined-owner semantic checks and optional exact-AKN-byte
reference-inventory verification now check the Work graph, structural ordering,
owners and report/RDF coherence. Disposable named-graph tests check that
Debates-owned descriptions and complete graph replacement remain isolated from
Member, Houses, Committee, Bill and office graphs. Parameterized SPARQL
competency resources execute against loaded owner-transformer output, including
a reviewed office-holding/NamedOffice owner traversal; this does **not** imply
question-recipient reconciliation. Source-aware goldens remain necessary to
exclude transcript text hidden in permitted strings and roll-call-derived RDF.
These checks do not implement Tranche 4 publication or a production owner
snapshot, and the separate historical-corpus/resource gate remains open.

#### Tranche 3 evidence review and bounded closure (2026-10-05)

The earlier checkpoint treated the two unsupported joins below as blocked
Tranche 3 exit criteria. The subsequent evidence review confirms that these are
not missing implementations of already-resolvable links: the checked-in source
and owner examples do not establish either crosswalk. Under the bounded closure
rule for this tranche, supported links are validated and both unsupported
competencies are explicitly deferred. This closes Tranche 3 without asserting
that either query produced its intended positive result.

**Section-to-Bill evidence.** Across the five preserved AKN records there are
16 section `@refersTo` values: eight resolve only to a local AKN `TLCEvent`
element, while eight 2026 Dáil fragments have no local target. The local
`TLCEvent` nodes are source evidence, not Bill-owned RDF owners. Their six
distinct source `@href` strings contain Bill year/number path text for 2013/23,
2014/86, 2015/1, 2015/67, 2024/25 and 2026/6; this inventory is not an accepted
owner crosswalk. Of the eight locally unmatched fragments, six are
`#bill.2026.6.dail.` and two are `#bill.2024.25.dail.`. The checked-in
Bill owner example (`data/api_examples/bill.json`) is only Bill 2025/60 and
describes its own lifecycle events. No exact reviewed AKN
`TLCEvent`-to-Bill-owned event/Work identity crosswalk is present. The new
independent acceptance checks one hash-linked unresolved report row per source
section against that joined owner graph, including local-target evidence, and
asserts no `:refersToEvent` triple. The `debate-bill-event-sections.rq` query
remains unchanged; it returns no matching rows against this example dataset,
which is an explicit evidence gap, not a passing positive competency.

**Question-recipient evidence.** The five preserved AKN records contain 239
question `@to` values: ten in the 2015 Dáil record and 229 in its written-answer
record; the other three records contain no question recipients. Each present
reference resolves only to its source-local `TLCRole`. The evidence includes
`akn/ontology/role/ie/oireachtas/minister/public` and the written-answer role
hrefs `/ie/oireachtas/role/office/public`,
`/ie/oireachtas/role/office/social`, and
`/ie/oireachtas/role/office/finance`. The joined
owner examples contain only three reviewed `NamedOffice` individuals
(Taoiseach, Tánaiste and Minister for Finance) and no typed
`eli-dl:ParticipationRole` individuals. No reviewed source-reference
crosswalk connects these `TLCRole`s to either target type. Independent tests
assert a hash-linked unresolved row for each present `@to` and the absence of
both `:directedTo` and `:directedToOffice` in the five debate graphs. The
`debate-question-recipients.rq` contract remains unchanged; its directed-role
competency remains unanswered rather than being inferred from labels or
slugs.

The mapping statuses remain unchanged: section `@refersTo` (row 16) and
question `@to` (rows 30 and 56) remain `future_work`. All links supported by the
reviewed owner evidence continue to be checked by joined SHACL/quality,
source-aware report validation, competency and graph-boundary tests.

Committee `rollCall` attendance remains source-only, and the transformer,
source-aware golden and RDF checks exclude both attendance-derived RDF and the
`rollCall`-nested `sum_2` Summary/ordinal. The active CSV now matches that
runtime exclusion: the class selector in CSV row 25 is
`debateBody//summary[not(ancestor::rollCall)]`, with the same exclusion applied
to the eId selector in row 26 and the Summary clause of the ordinal rule in
row 49. The executable exclusion is independently pinned by the golden. No
ontology, source fixture or golden was changed; the protected mapping-selector
correction was applied as a bounded follow-up to this closure.

This paragraph records **Tranche 3 closure before the bounded Tranche 4
implementation recorded below**. At that earlier point Tranche 4 ingestion,
state and publication had not started. The supplied-batch mechanics are now
complete, but production-readiness acceptance remains open. The two unsupported
positive crosswalk competencies are deliberate, evidence-backed **future
reconciliation work**, not blockers to the agreed first production scope. The
later exact 2011+ inventory is recorded in
`documentation/debates-production-readiness.md`; the 2004–2007 duplicate-eId
cases and pre-2013 fragmented written answers remain separate historical/source
expansion work.

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

#### Tranche 4 implementation and acceptance record (2026-10-06)

`oir-etl run debates` accepts only a finite caller-supplied list of official
`https://data.oireachtas.ie/akn/ie/debateRecord/.../main.xml` URLs and/or
lowercase SHA-256 replay keys for previously preserved objects. It has no
debates-listing client, pagination, broad enumeration, completeness inference,
or scheduling policy. The fetched object URL must match the exact canonical
FRBRExpression path followed by `/main.xml`; section-object URLs therefore
cannot be published as Work records. A supplied batch containing multiple
known Expressions for one Work fails closed, as does a later attempt to publish
a different Expression for a Work already recorded in Core State. A single
supplied Expression does not assert global Expression-set completeness.

Exact XML bytes are stored outside SQLite at
`{raw-root}/debates/sha256/{hash-prefix}/{sha256}.xml`; immutable metadata ties
the content object to its official main.xml URL. Core State schema v5 adds the
Debates endpoint to the existing run/resource state and records the graph,
source hash, raw-object path, source URL, Expression IRI, publication state,
resolver version and owner-snapshot fingerprint. Each validated resolution
also persists its canonical UTF-8 reference-outcome JSON as an immutable
sidecar beside the raw object, keyed by source hash, resolver/owner snapshot and
report content hash, at
`{raw-root}/debates/sha256/{hash-prefix}/{source-hash}.{resolution-key}.{report-hash}.reference-report.json`.
Core State stores the report path/hash in pending and published state; it
verifies the report before a clean skip and again before marking a PUT clean.
The RDF bytes remain in the existing durable
pending/published payload fields, and XML blobs are never stored in SQLite. No
ontology, mapping, golden or source fixture was changed.

Publication is explicitly opt-in:

```text
oir-etl run debates --source-url https://data.oireachtas.ie/akn/.../main.xml
oir-etl run debates --replay <sha256> --offline
oir-etl run debates --replay <sha256> --publish
```

Without `--publish`, the command has no GSP loader, does not create/update Core
State, and may only preserve/acquire, transform, validate and write local output.
An opt-in publish requires both configured Fuseki Graph Store and SPARQL
verification endpoints. Changed records use the existing validated Debates
transformer, exact owner resolver and source-aware integration validator, then
durably mark publication dirty, PUT the complete Work graph, verify the entire
named graph, and only then mark Core State clean. Exact-source skipping requires
matching source/transform contract, resolver version and owner-snapshot hash,
plus a hash-verified reference-report sidecar and fresh whole-graph
verification. A changed owner snapshot therefore re-resolves the same source,
persists a new report version and republishes rather than silently skipping it.
Failed report verification, PUT or post-PUT graph verification never advances
dirty state to clean. Changed-source replacement removes stale Debate-owned
triples; absence from a supplied batch never marks another Work missing or
deletes its graph.

Focused acceptance covers exact-byte content addressing/replay, immutable
hash-linked reports across close/reopen and owner-snapshot changes, main.xml
versus section-object rejection, malformed XML, duplicate eIds in mixed batches,
multiple known Expressions, publication opt-in, first publish, exact replay
skip, remote-corruption repair, dirty source-revert recovery with exact repeated
PUT payloads, changed-source stale-triple removal, Core State migration, dirty
report/PUT/verification failure and retry, and owner-graph isolation. The
optional Fuseki acceptance requires both endpoints to be the same disposable
loopback dataset `/debates_t4` at `127.0.0.1:13035` before any owner graph PUT;
production graphs were not accessed or mutated. This closes the supplied-batch
publication tranche only, not the separate production resource/scope gate or
broad-ingestion acceptance.

## Phase 7 Debates exit criteria

The Debates slice is complete when:

- the approved initial 2011+ Dáil/Seanad/committee debate scope (without
  written answers) can be processed within approved operational resource
  budgets, with excluded/quarantined records inventoried and auditable;
- AKN source is preserved and replayable;
- generated RDF is deterministic and contains no transcript text;
- questions and divisions/votes are owned by the debate graph;
- cross-resource links respect existing RDF ownership;
- unresolved references fail safe and remain auditable;
- representative Dáil, Seanad, committee and written-answer fixtures pass
  Tranche 2 validation, independently of which source types are included in
  the first production load;
- graph replacement is idempotent and removes stale debate-owned triples; and
- supported competency queries pass; explicitly evidence-deferred positive
  legislative-section and question-recipient crosswalks are not asserted as
  passing or required to close the bounded initial-production slice.
