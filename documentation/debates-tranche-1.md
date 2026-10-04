# Phase 7 Debates — Tranche 1 source and mapping contract

**Status: Tranche 1 complete.** I1/I2/O1–O8 semantic/source decisions, approved
ontology/mapping additions and static contract checks are verified. Tranche 2
may start against representative fixtures; no Debates transformer is included
in this tranche.

This tranche is governed by [phase-7-debates.md](phase-7-debates.md).
Akoma Ntoso XML, preserved byte-for-byte, is the authority for document
structure and complete source order. The authoritative RDF graph contains
structure, participation and cross-dataset links, **not transcript prose**.
Each AKN Work/record owns one replaceable graph, including its
questions and divisions; other endpoint resources are referenced, never
described in that graph. Tranche 1 specifies the transformation contract but
does not implement extraction, transformation or publication.

## Representative source inventory

The detailed inventory and exact fixture provenance are in
[`debates-source-audit.md`](debates-source-audit.md). The two initially checked-in
samples are Dáil-only. Authoritative Seanad, committee and written-answer AKN
samples reveal additional forms not represented by the original outline:
`writtenAnswer(s)` sections, an outcome `#declared`, and a table-based
`rollCall`. Observation alone does not define an RDF model; the approved initial
scope keeps committee rollCall attendance source-only.

## Production-scope resource gate

The current source audit records a date-bounded API census of primary records
and separately identifies written-answer XML not enumerated by that census. The
available counts do **not** establish total in-scope XML volume, runtime or RDF
output. This production-scope gate does not block Tranche 1 or Tranche 2. After
the core transformer exists and before broad production ingestion, census the
full in-scope XML (including `writtens`) and benchmark runtime, working/storage
needs and RDF output on representative records. Choose full-corpus or
Bill-debates-first production ingestion from the measured XML volume, runtime
and RDF output against deployment budgets; do not infer scope from sample size
or use an arbitrary cutoff. The post-Tranche-2 census/benchmark has since been
measured and is recorded in
[`debates-production-benchmark.md`](debates-production-benchmark.md); the scope
choice remains pending an operational threshold.

## Identifier and graph identity

See [`debates-identity-contract.md`](debates-identity-contract.md) for the
approved exact percent-encoding, stable AKN Work/Expression/eId identities, a
deterministic content/context fallback, collision handling and tests. Record
and graph identity are derived from the Work, not the filename or Expression;
the graph path replaces `/akn/ie/debateRecord` with `/graph/debate` in the
once-encoded Work IRI without a second encoding pass. An XML URL is not assumed
to deliver immutable bytes: retain each acquired version and its source hash.
Fail closed for a Work when multiple Expressions are known; do not publish or
replace its graph from one Expression in isolation. One fetched file does not
prove global Expression completeness. A `writtens` Work remains a DebateRecord
with its date, but receives no DebateSitting.

## Source order

The approved `:sourceOrdinal` is a positive, consecutive, one-based
`xsd:integer` scoped to immediate addressable children of a containing XML
resource, shared across addressable sibling kinds rather than per-kind
counters. It is never part of an IRI and cannot reconstruct the whole XML; the
XML remains authoritative. The ontology declaration and active mapping row
passed static contract checks; runtime ordinal assignment and transformed-RDF
ordering validation remain Tranche 2 work.

## Reference resolution and evidence

Use four distinct outcomes for each expected source reference: `resolved`
(assert an existing target IRI only), `unresolved` (present, syntactically
usable, no authoritative target), `malformed` (present but invalid for that
attribute), and `absent` (optional slot not supplied). A deterministic
source-hash-keyed report retains exact lexical evidence and the source node/
attribute; no unresolved or malformed source may mint a Member, office, Bill
or other placeholder. Exact status schema and attribute-specific parsing are
in the identity contract. The original AKN bytes remain the authoritative
record of source IDs. AKN ministerial role text alone does not identify an
`eli-dl:ParticipationRole` or the parallel slice's `NamedOffice`.

## Approved semantic contract and implementation status

The separate [semantic review](debates-semantic-review.md) approves I1/I2 and
O1–O8. The approved Debates ontology/mapping additions passed ontology
validation, active mapping-term checks, focused Debates tests and the full
repository suite. This completes the vocabulary, mapping and static source
contract; it does not implement or verify runtime extraction, transformation,
reference resolution or publication.

Key approved boundaries for this tranche and its handoff:

- Work and Expression identities derive from their own `FRBRuri/@value`; the
  graph URI replaces `/akn/ie/debateRecord` with `/graph/debate` in the
  once-encoded Work IRI path without re-encoding. Sitting emission is limited
  to an eligible non-`writtens` Work under the exact metadata rule in the
  identity contract. A written-answer Work has a record/date but no sitting.
- Fail closed for a Work if multiple Expressions are known; one input does not
  establish a globally complete Expression set.
- Approved additions cover mixed-sibling `:sourceOrdinal`, Work/Expression and
  question/section links, record host/HouseTerm links, local Speech
  participation, and a conditional question-to-office link, as detailed in
  the semantic review. Do not use `:inHouse` on DebateRecord or
  `eli-dl:had_participation` on Speech.
- Keep `#declared` audited but not emitted as carried/lost; keep unsupported
  division target and legislative-reference rows inactive pending exact owner
  resolution. Committee `rollCall` is evidenced but attendance remains
  source-only; never treat its people as voters, speakers or participants.
- The approved source-hash outcome-report contract distinguishes resolved,
  unresolved, malformed and absent references. No unresolved reference creates
  a placeholder.
- Transcript prose remains out of RDF. Foreign resources are linked by IRI
  only after authoritative resolution and are never re-described in the
  Debates graph.

Mapping-integrity validation alone does not protect against domain/range
inference, mistaken ownership or wrong source joins. No tests, vocabulary
constraints or source fixtures may be weakened to make the mapping appear
complete.

The current Tranche 1 identity, source, mapping and ontology tests are static
contract checks. They inspect approved terms, mapping rows and immutable source
fixtures but do not transform AKN or test RDF emission. In particular, static
negative checks do not prove that a future transformer omits triples. Tranche 2
must run deterministic transformations and inspect actual RDF golden datasets,
including negative assertions for `#declared` (no carried/lost outcome),
unresolved references (no placeholder/link), committee `rollCall` attendance
(no Division/vote/participation) and transcript text (no transcript literals),
alongside positive assertions for supported output.

## Tranche 2 handoff

**Tranche 1 exit confirmed; no production-resource gate is required to start
Tranche 2.** The approved ontology/mapping contract and its static checks have
passed. Tranche 2 covers deterministic transformation
and actual RDF golden tests for representative Dáil, Seanad, committee and
written-answer AKN sources, without transcript text. Do not start around an
unverified or partial mapping.

The full-corpus versus Bill-debates-first choice is made after the core
transformer exists and before broad production ingestion, using a complete
in-scope census (including written answers) and measured XML volume, runtime and
RDF output/working storage. This gate does not delay Tranche 1 or representative
Tranche 2 work. Phase 6 cadence, scheduling and reconciliation policy remain
unchanged.

Settled boundaries are exact-byte AKN as source evidence; Work/Expression keys
and eIds rather than filenames or position; one authoritative replaceable graph
per Work/record; reference-only links to resources owned elsewhere; no
transcript literals or text-derived topics; and no Phase 6 scan schedule in
Debates code.

## Verification boundary

Ontology reasoner validation, active mapping-term resolution, source/fixture
integrity checks, 28 focused Debates tests and the full suite (427 passed,
8 skipped) are verified. These checks do not constitute actual RDF goldens or
prove transformer non-emission. This tranche does not claim a Debates transformer, SHACL shapes,
complete golden RDF, cross-dataset runtime resolution, publication/replay or
the production-scope census/benchmark. Those remain later phase work; the
production gate is required before broad production ingestion but does not
block Tranche 1 or Tranche 2. The mapping-integrity validator alone does not
check domain/range, transcript exclusion or graph ownership; mapping review
and transformation tests must cover those separately.
