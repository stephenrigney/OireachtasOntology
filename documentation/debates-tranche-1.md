# Phase 7 Debates — Tranche 1 source and mapping contract

**Status: verified partial tranche; the Tranche 1 exit gate is not met.**

This tranche is governed by [phase-7-debates.md](phase-7-debates.md).
Akoma Ntoso XML, preserved byte-for-byte, is the authority for document
structure and complete source order. The authoritative RDF graph contains
structure, participation and cross-dataset links, **not transcript prose**.
Each AKN debate record/sitting owns one replaceable graph, including its
questions and divisions; other endpoint resources are referenced, never
described in that graph. Tranche 1 specifies the transformation contract but
does not implement extraction, transformation or publication.

## Representative source inventory

The detailed inventory and exact fixture provenance are in
[`debates-source-audit.md`](debates-source-audit.md). The two initially checked-in
samples are Dáil-only. Authoritative Seanad, committee and written-answer AKN
samples reveal additional forms not represented by the original outline:
`writtenAnswer(s)` sections, an outcome `#declared`, and a table-based
`rollCall`. Merely observing a construct does not approve a new RDF model.

## Corpus/resource gate

The source audit records a date-bounded API census of primary records and
separately identifies written-answer XML not enumerated by that census. The
available sample sizes and record counts do **not** establish total XML bytes
or the processing/storage multiplier for RDF generation. Do not choose a Bill-
only cutoff or assert that full production ingestion is affordable without
that measurement; the smallest required measurement is specified in the audit.

## Identifier and graph identity

See [`debates-identity-contract.md`](debates-identity-contract.md) for exact
percent-encoding, stable AKN work/expression/eId identities, a deterministic
content/context fallback, collision handling and tests. Record identity and
graph identity are derived from the Work, not the filename or expression.
An XML URL is not assumed to deliver immutable bytes: retain each acquired
version and its source hash. Multiple expressions for one Work must not be
published by replacing the same work graph from one expression in isolation.

## Source order

The proposed ordinal is one-based, an `xsd:integer` scoped to the immediate
containing resource, shared across addressable sibling kinds rather than
per-kind counters. It is never part of an IRI and cannot reconstruct the whole
XML; the XML remains authoritative. Emitting it in RDF is **blocked** until
the missing ontology property is approved (see below).

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

## Mapping and expected RDF

[`../mappings/debates_mapping.csv`](../mappings/debates_mapping.csv) follows
the repository CSV convention; its companion
[`debates-mapping.md`](debates-mapping.md) describes safe active rows,
conditions, deferred/blocking rows and Tranche 2 golden-output requirements.
This is a **partial safe mapping**, not a claim that missing predicates have
been approved. Speech, summary, question and vote transcript prose is never
emitted. Question and division resources belong only to their work graph;
foreign resources may be linked but not re-described.

## Ontology coverage and approval boundary

The current ontology covers record, expression, sitting, nested section,
speech, summary, question and division classes; section/speech/summary/division
containment; sitting and speech dates; division counts, outcome and Member
votes. This does **not** mean that every source relationship is safe to emit.

| Finding | Classification | Evidence / required review |
|---|---|---|
| Source ordinal for sections and contributions | Ontology addition proposed | No integer ordinal property exists in `debates.owl.ttl`; `eli-dl:activity_order` has an Activity domain and decimal range, so it cannot safely represent mixed structural siblings. Propose a scoped `:sourceOrdinal` datatype property with `xsd:integer` range, independent of identity. No ontology change in this tranche without explicit approval. |
| House or committee hosting | Ontology addition/change proposed | `documentation/debates_ontology_outline.md` suggests `:inHouse`, but its declared domain is `:BillEvent`; asserting it on a DebateRecord would infer a BillEvent. A committee is not an enduring House. Resolve the hosting relation and target type in semantic review. |
| Speech participation | Ontology change or mapping clarification proposed | The debate ontology's comment calls `eli-dl:had_participation` canonical on `:Speech`, but that ELI-DL predicate has `eli-dl:Activity` domain. It would infer that every such Speech is an Activity. Do not silently emit this link before review. The `:speaker` shortcut is valid only for a resolved Member, not a witness. |
| Expression-to-record and question-to-section links | Ontology addition or approved external term proposed | Classes exist but no specific connecting properties are declared; a graph that omits these links cannot answer containment queries. Record/expression language metadata also has no declared term, and the `mul@` expression URI must not be taken as evidence of `eng` or vice versa without a rule. |
| Division proposal / legislative reference target | Ontology/model discrepancy | The comments for `:refersToProposal` limit the target to DebateSection or BillEvent, whereas audited `voting/@refersTo` can point to Summary eIds; the comment for `:refersToEvent` names `:BillEvent`, while Bill ownership uses ELI-DL legislative activities. Neither property has an executable range. Preserve references without speculative coercion pending review. |
| Vote vocabulary and dates | Ontology/source discrepancy | Seanad `voting/@outcome="#declared"` is not the declared `:DeclaredCarried`/`:DeclaredLost` vocabulary. An official 2015 Dáil record has `#staon` aggregate counts without a Staon voter subsection, contradicting the ontology's “from 2026 onwards” annotation. Do not translate `#declared` into carried/lost or infer zero/absence of abstentions. |
| Written-answer response and committee rollCall | Ontology proposal / deferred review | Written-answer sections contain questions and speech responses, sometimes multiple questions per section; the response is not necessarily an oral speech and no one-to-one answer link can be assumed. A committee sample now evidences `rollCall` with a table and person references: the construct is present, but full table-content modelling remains deferred. Review the minimal structurally necessary treatment rather than silently dropping or inventing a vote entity. |
| Ministerial addressee and role identity | Mapping/implementation concern with semantic review | `:directedTo` expects an `eli-dl:ParticipationRole`, but an AKN `TLCRole` or text does not establish that identity. The parallel office-holder model's `NamedOffice` / `OfficeType` is not a ParticipationRole. Never mint an office, role or person from labels. |
| Transcript, topics, Manifestation, inline markup, images/tables, bilingual-heading deduplication and `answer` | Deferred | Explicitly outside the approved initial RDF boundary unless representative source evidence requires otherwise. The now-evidenced committee `rollCall` is instead a review question above. |

These findings are proposals, **not ontology edits**. In particular, the
missing ordinal and containment/host predicates mean a fully active mapping
cannot yet claim to implement every required relationship without a reviewed
semantic choice. Mapping-integrity validation only checks whether terms exist;
it does not protect against domain/range inference or mistaken ownership.

### Concrete semantic-review proposals (not approved mappings)

1. Add a `:sourceOrdinal` integer datatype property usable on addressable
   sections and contributions without inferring a different resource class;
   require a positive one-based value within each immediate container in
   validation, not as a global OWL functional key. The ELI-DL decimal Activity
   order is not an equivalent substitute.
2. Add a question-containment relation (provisionally `:hasQuestion`, section
   to question), and a record-to-expression relation (provisionally
   `:hasExpression`). Decide whether explicit expression-language metadata is
   required and what source field, rather than the URI suffix, controls it.
3. Approve a host-body relation that can point to an existing enduring House
   **or** Committee without `:inHouse`'s BillEvent-domain inference. Its
   precise domain/range and treatment of HouseTerm author references require
   review; do not assert a committee is a House. Review the derived
   `{work IRI}#sitting` identity and its one-sitting-per-Work assumption before
   enabling `:producedRecord` and sitting date assertions.
4. Decide whether `:Speech` is intentionally an ELI-DL Activity; otherwise
   introduce a speech-participation relation without that inference. Consider
   that AKN `speech` also occurs as a written-answer response and from
   non-Member witnesses. Do not type a `TLCRole` as a ministerial office.
5. Review division/proposal references to `Summary`, Bill-event target
   correspondence, the `#declared` outcome and 2015 Staon counts. A lexical
   `#declared` is **not** evidence of carried or lost; the source may supply
   aggregates without individual voter lists. Preserve unsupported assertions
   in the raw XML/reference report pending a correct model.
6. Review whether the table-based committee `rollCall` requires any initial
   structural RDF. Its existence removes the old *not evidenced* rationale
   for deferral, but does not justify mapping its table prose or inventing a
   parliamentary Division. Preserve it in XML until the scope is approved.

These proposed names are review handles, not executable ontology terms.
Approval must precede any active CSV row or transformer assertion depending on
them. No tests, vocabulary constraints or source fixtures should be weakened
to make the current partial mapping look complete.

## Tranche 2 handoff

**Not cleared.** The source, identifier, reference-outcome and fixture
findings can inform implementation, but the required active mapping remains
blocked by the ontology proposals above. Before a Tranche 2 executor can
implement without new semantic decisions, review and explicitly approve the
ordinal, hosting, question containment, record-expression relation and
participation semantics; decide how `#declared`, `rollCall`, written-answer
contributions, and Summary-targeted division references are represented or
deferred without misrepresenting source assertions. Verify the corpus gate
with primary **and** written-answer XML volume and a measured processing/RDF
multiplier before selecting production scope. Keep Phase 6 scheduling out of
Phase 7 and do not begin transformation under this partial contract.

Settled boundaries available for the later handoff are: exact-byte AKN rather
than filenames/API JSON as source evidence; FRBR Work/Expression source keys
and eIds over position; a single per-record/sitting replaceable authoritative
graph owning questions and divisions; reference-only links to resources owned
elsewhere; no transcript literals or text-derived topics; and no Phase 6 scan
schedule in Debates code. The mapping's safe active subset and the five
byte-checked representative AKN files are review inputs, **not permission**
to implement around the unresolved ontology/IRI questions.

## Verification boundary

Tranche 1 can verify XML fixture integrity, mapping CSV term resolution and
synthetic identifier/reference rules; it cannot honestly claim that a Debates
transformer, SHACL shapes, complete golden RDF, cross-dataset resolution,
publication/replay or the production resource gate has passed. Those remain
the phase tranches in the governing design. The existing mapping validator
does not check domain/range, transcript exclusion or graph ownership; the
mapping review and future transformation tests must cover those separately.
