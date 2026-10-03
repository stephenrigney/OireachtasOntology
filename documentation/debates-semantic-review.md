# Phase 7 Debates — semantic review request

**Status: proposals for explicit approval, not executable ontology or active
mapping changes.** The governing design is
[`phase-7-debates.md`](phase-7-debates.md); source evidence, current safe mapping,
and exact identity examples are in the other `debates-*` documents. No Debates
transformer or production graph mutation is authorized by this review note.

The proposals below are separate approval questions. Accepting an IRI/graph
identity does not implicitly approve a new vocabulary term, or vice versa.
Where a source reference cannot satisfy an approved predicate, retain the
immutable AKN and an auditable non-RDF outcome rather than minting an entity.

## Identity and graph questions

### I1 — Canonical public IRIs and original evidence

**Evidence:** the five checked-in records use AKN FRBR Work and Expression
`FRBRuri/@value`; the older Dáil Work URI has no `/debate` suffix, while newer
records have `/debate` or `/writtens`. The Dáil file named `2026-02-26` carries
a 2026-02-25 Work date. The source URI and eId examples in
[`debates-identity-contract.md`](debates-identity-contract.md) are testable.

**Recommendation:** approve its component-wise RFC 3986 UTF-8 percent encoding
of AKN paths and eIds, Work and Expression subject identities, eId collision
rejection, content/context fallback with fail-closed identical siblings, and
exact-byte source hash/raw XML retention. Do not identify resources by filename,
position, Member label, or a transcription of raw `&` into public IRIs. The
proposed graph URI replaces the once-encoded Work IRI path prefix
`/akn/ie/debateRecord` with `/graph/debate` without encoding any segment a
second time. The sitting IRI is `{work IRI}#sitting` only if one
Work really identifies one sitting. **Written answers need a separate check:**
the same date's `/writtens` Work is a separate record, but a publication of
written answers does not itself prove another sitting activity. Do not mint a
written-answer `DebateSitting` or equate it with the oral sitting solely from
matching House/date. Original lexical source identities stay in
the preserved XML and source-hash-linked audit report; approval of an
additional RDF identifier literal would be a separate semantic choice.

**Alternative:** reject this public IRI/graph pattern and select a different
path-safe pattern now, before any transformer/golden graph is implemented.
Do not ship both patterns under the same source Work. This is a public identity
decision, not a local code-helper choice.

**Sitting subdecision:** in the audited source, emit one `:DebateSitting` at
`{work IRI}#sitting` only if `FRBRname/@value` is absent (the older Dáil
snapshot) or exactly `debate` (the chamber/committee samples), and its Work
URI does not identify `/writtens`. Use `eli-dl:activity_date` from its Work
date and `:producedRecord` to the Work. When `FRBRname="writtens"`, emit its
distinct `:DebateRecord` and date but **no** `DebateSitting`: the written-answer
publication does not itself evidence a second activity. If type signals
disagree or an unreviewed type occurs, fail closed for sitting emission and
report it; do not infer a sitting solely from matching House/date. The host
relation proposed below must work on DebateRecord, not only on DebateSitting.

### I2 — Multiple expressions of the same Work

**Evidence:** each audited fixture contains one Expression, but the FRBR model
allows more than one Expression per Work. Phase 7 fixes **one replaceable graph
per record/sitting**, not one graph per Expression; replacing it from one
Expression in isolation could delete other valid Expression triples.

**Recommendation for the evidenced initial slice:** treat the Work as the
source/publication unit. Where more than one Expression is *known* for the
same Work, preserve each exact input but fail closed for that Work rather than
replacing its graph from one file. Do not claim that a single fetched file
proves there is only one Expression globally. This defers multi-Expression
publication until an authoritative expression-set discovery source and
completeness contract have been reviewed. Never silently pick the last
fetched Expression or change to per-Expression graphs.

**Future alternative, requiring separate approval:** assemble a complete
expression bundle keyed by canonical Work, sorted Expression identity and
exact bytes; validate and publish one whole Work graph. The source-state hash
must cover every *bundle entry's* identity and bytes. The complete discovery
source must be named before this becomes executable. EIds are unique within
each Expression, not across the bundle; expression-scoped component IRIs allow
safe co-publication. Keep transcript text out of RDF and Phase 6 scan policy
out of this contract.

**Discovery/identity risk:** the audited five XML files contain one Expression
each; `/v1/debates` does not enumerate written-answer XML and has not been
proved to enumerate every Expression of a Work. Do not treat its listing as a
complete Expression manifest. Until an authoritative complete discovery
source is evidenced, do not promise full-bundle completeness. If the
source publisher repaths a Work (the checked-in 2015 Dáil path lacks `/debate`
but its current official path includes it), the proposal creates distinct
Work and graph IRIs. Do not infer `owl:sameAs`, merge them by House/date, or
delete an old graph automatically. Flag the identity change for reviewed
replacement/retirement in Tranche 4; an already-published same-context graph
must not coexist silently with the new graph. This is an endpoint lifecycle
issue, not a Phase 6 scan-cadence choice.

## Ontology/mapping questions

### O1 — Lightweight source order

**Evidence:** a `debateSection` can nest sections, speeches, summaries and
questions in mixed AKN sibling order. The existing Debates ontology has no
ordinal; pinned `eli-dl:activity_order` has Activity domain and decimal range.

**Recommendation for approval:** add `:sourceOrdinal` as an
`owl:DatatypeProperty` with `rdfs:range xsd:integer` and no class domain or
functional-key implication. Map it on sections and addressable contributions;
validation requires a positive, unique 1-based ordinal among addressable
immediate children of each containing XML resource, across child kinds. This
is ordering metadata only, never an IRI ingredient. XML remains authoritative
for the complete document order. Addressable children include DebateSection
(including division and ta/nil/staon groups), Speech, Summary and
ParliamentaryQuestion; each nested container restarts the sequence. Activate
the currently `future_work` source-
order CSV row only after the ontology change is approved and validated.

**Alternative:** omit RDF ordering and retain XML order only. This fails the
approved Phase 7 query/order requirement and would need an explicit change to
that acceptance contract; do not treat it as an implementation shortcut.

### O2 — Record, Expression and top-level structure

**Evidence:** `:DebateRecord` and `:DebateExpression` exist, but no predicate
links them. AKN `debateBody` contains the top-level sections of the source
document described by its FRBRExpression metadata; the existing `:hasSection`
declares DebateRecord domain. An Expression URI ending
`mul@` may carry `FRBRlanguage/@language="eng"`; URI spelling is not a safe
language assertion. The multiple-Expression policy in I2 changes how top-
level section containment must be interpreted.

**Recommendation for approval:** add `:hasExpression` (ObjectProperty;
`DebateRecord` → `DebateExpression`) and `:expressionHasSection`
(ObjectProperty; `DebateExpression` → top-level `DebateSection`). Keep the
existing `:hasSection` from Work to the same top-level sections as a
Work-level convenience union; only the Expression relation defines their
immediate source-order scope. On the five single-Expression fixtures these
two links target the same top sections; if a multi-Expression Work is later
approved, the Work-level shortcut may include all its Expression sections
without claiming one global sequence. Add `:expressionLanguageCode`
(DatatypeProperty; domain `DebateExpression`; range `xsd:string`) using the
exact `FRBRlanguage/@language` lexical code; no language assertion is inferred
from the Expression URI. Activate the existing top-section and language
`future_work` CSV rows and add the two new linkage rows only after ontology
and mapping approval.

**Vocabulary alternatives:** `dct:hasPart` / `dct:isPartOf` are recognized and
have no constraining domain/range in the repository but express only generic
part-whole; `eli:is_realized_by` / `eli:realizes` carry FRBR semantics but infer
ELI Work/Expression typing, contrary to the current intentionally bare
`:DebateExpression` class. Likewise, `dct:language` or `eli:language` would
require a reviewed language-resource identity, not a URI inferred from
`mul@`. The proposed local lexical code avoids that unsupported join.

### O3 — Questions and written responses

**Evidence:** `question` nodes occur within question and `writtenAnswer`
sections. A written-answer section may contain multiple questions and a
response `<speech>`. The ontology declares `:ParliamentaryQuestion` and
`:askedBy` but no question-to-section containment; it describes Speech as
oral although written answers encode their response as `<speech>`.

**Recommendation for approval:** add `:hasQuestion` (ObjectProperty; domain
`:DebateSection`, range `:ParliamentaryQuestion`) for the immediate containing
section. Clarify the `:Speech` annotation to cover AKN `speech` used for oral
and written contributions, without making Speech an ELI-DL Activity merely
because of its name. Continue to map `writtenAnswer` as a DebateSection and
link its direct speech via existing `:hasSpeech`. Do not assert a one-to-one
question-to-answer link absent source correspondence. The question and
written-speech content remains outside RDF.

**Alternative:** use a separate written-response class/relationship only if
source evidence requires a distinct semantic entity; this expands the model
and does not justify guessing which response answers each question.

**Active-row prerequisite:** the existing CSV already marks `:Speech` and
`:hasSpeech` active for `writtenAnswer` response `<speech>` nodes, while both
ontology comments still say *oral*. Either approve the annotation clarification
before written-answer goldens/transform, or explicitly make those written
emissions conditional through an approved mapping revision. Mapping-integrity
validation cannot detect this semantic contradiction. The current fixture
has 197 response speeches under 197 writtenAnswer sections; 12 such sections
have 2–8 questions, so a direct one-to-one answer link is unsupported.
The inactive CSV row 31 also names `debateBody//writtenAnswer`, but the source
has **no** `<writtenAnswer>` element: it has
`debateSection[@name='writtenAnswer']`. Correct that path in the approved
mapping revision; do not activate the current selector.

### O4 — Host body and numbered term without BillEvent inference

**Evidence:** the outline suggests `:inHouse` on DebateRecord, but its
executable domain is `:BillEvent`, and `members:Committee` is not an enduring
House. A Work author can be a generic `#oireachtas` rather than a resolved
HouseTerm. Written-answer records still need a host query even if they do not
denote a sitting activity.

**Recommendation for approval:** add a direct record-to-existing-body relation
(provisionally `:recordOfBody`; ObjectProperty; domain `:DebateRecord`; range
`org:Organization`, broad enough for House and Committee). Assert it only when
the source record's body resolves to an authoritative House or Committee IRI;
do not mint/descriptively type a Committee from a venue slug. Add
`:recordOfHouseTerm` (ObjectProperty; domain `:DebateRecord`; range
`:HouseTerm`) only where `FRBRauthor/@href` resolves to an existing numbered
term. The numbered term must not be mistaken for the enduring host House;
derive the House from that term's existing `:termOf` target, not from the
term URI's spelling. For chamber Works, approve an explicit venue crosswalk
from the authoritative FRBR Work URI's exact venue segment `dail` or
`seanad` to the existing enduring House IRIs **only** when the author is
generic `#oireachtas` or an agreeing resolved HouseTerm. A generic Oireachtas
author or label alone is not an individual House key; the path-and-author
rule is the additional evidence. If the path disagrees with the author's
resolved term/House, emit no host and report the conflict. Do not derive a
numbered HouseTerm from venue/date alone. For Committee records, require the
official committee author IRI and approved owner-identity resolution; a
committee path slug or label alone is not an identity crosswalk.
The resolution evidence belongs in the source-hash outcome report.

**Alternative:** introduce two narrowly typed host properties, one for House
and one for Committee; this avoids a broad range but makes a unified query
less direct. Reusing `:inHouse` on DebateRecord is **not** an option without an
approved domain change that also preserves existing BillEvent semantics.

`org:Organization` is the common superclass of the existing House and
Committee classes, but would also allow unrelated organisations; later SHACL
must restrict targets to a resolved House or Committee. A union-of-House-and-
Committee OWL range is a narrower alternative, but adds an import/dependency
on `members:Committee` and a more complex OWL axiom. A source committee IRI
may be referenced without describing it in the Debates graph even when its
owning Committee dataset has not yet been published; whether that counts as
`resolved` must be decided against the actual authoritative owner registry.

**Existing ontology mismatch:** `agents.owl.ttl` describes `:House` as Dáil
and Seanad enduring institutions but also says “Committee chambers are also
instances of :House”; `members:Committee` is separately an `org:Organization`.
An AKN committee author points to a Committee IRI, not evidence of an enduring
House individual. Before approval, distinguish a *chamber* (if that notion is
actually used) from the Committee organisation; do not type a Committee as
`:House` to make `:inHouse` fit. Correcting this protected annotation is a
separate semantic-review item.

The `eli-dl:parliamentary_term` property is not a neutral substitute for the
record-to-term link: on a current bare DebateRecord it may infer ELI Work
typing. If the O2 ELI alignment alternative is chosen, review that inference
and the source term's ELI-DL typing explicitly rather than changing the
meaning of `:recordOfHouseTerm` by accident.

### O5 — Speech participation without Activity inference

**Evidence:** `eli-dl:had_participation` has Activity domain, while current
`:Speech` is not an Activity; applying it to Speech would infer Activity. AKN
`speech/@by` and optional `@as` are the source slots. The committee sample has
929 speeches, some `@by="#"` placeholders and no inspected `@as` role values;
it does **not** establish a witness individual or `:WitnessRole` for those
speeches. The written-answer sample uses `<speech>` for responses.

**Recommendation for approval:** add `:hasSpeechParticipation`
(ObjectProperty; domain `:Speech`; range `eli-dl:Participation`), **not** a
subproperty of `eli-dl:had_participation`. Use one deterministic
`{speech IRI}#participation` only when a resolved person and/or reviewed
participation role is available for that single AKN speaker; from that
Participation use pinned `eli-dl:had_participant_person` for an existing
person IRI and `eli-dl:participation_role` only for an existing role individual
of the correct type. If neither resolves, omit the Participation and report
source references; never mint a witness/person/ministerial office from a
committee context, label or `#`. Existing `:speaker` stays a resolved-Member
shortcut. CSV rows 22–23 remain `future_work` until this and the role crosswalk
are approved; no Speech becomes an Activity by inference.

**Alternative:** explicitly type Speech as ELI-DL Activity and reuse
`had_participation`; this would also type written-response speeches as
Activities and needs an independent semantic rationale. Do not infer that
simply from an XML element name.

### O6 — Question recipient and parallel office identities

**Evidence:** `:directedTo` ranges over `eli-dl:ParticipationRole`, but AKN
`question/@to` points to `TLCRole` source references, including ministerial
role labels. The parallel office model's `members:NamedOffice` is distinct from
an OfficeType concept and from an ELI ParticipationRole individual; the
current office registry is a limited bootstrap, not a blanket source-role
crosswalk.

**Recommendation for approval:** keep `:directedTo` only when the source
reference resolves to an actual existing ParticipationRole. Add a separate
`:directedToOffice` (ObjectProperty; domain `:ParliamentaryQuestion`; range
`members:NamedOffice`) only if the source role can be uniquely and
reviewably reconciled to an existing office identity. If added, declare the
Debates ontology import of `<https://data.oireachtas.ie/ontology/members>`;
this dependency needs approval together with an
attribute-specific resolution/evidence table; label equality cannot establish
the target. An unresolved, malformed or absent `@to` produces the documented
non-RDF outcome and no invented office or role. CSV row 30 remains inactive
until the specific predicate and resolution rule are approved. Do not reuse
Bill sponsor `members:reconciledSponsorOffice` on a question.
The Phase 7 question-to-role competency query remains a Tranche 3
cross-dataset acceptance check: approving a predicate here does **not** claim
that the current small office registry resolves every AKN `TLCRole`, and a
golden must distinguish resolved recipients from explicit unresolved evidence.

### O7 — Vote outcomes, targets and legislative source references

**Evidence:** the five fixtures contain 19 analysis votes. The unique
`voting/@href` → result Summary → containing Division join holds for all 19;
`voting/@refersTo` is a *different* link to what was voted on (14 Summary
targets, four TLCEvent targets, one DebateSection target). Outcomes are 12
`#carried`, six `#lost` and one Seanad `#declared`. That `#declared` division
has Tá 21 / Níl 22; neither the counts nor narrative entitle the transformer
to assert `:DeclaredLost`. Sixteen sections have `@refersTo`: eight resolve
within AKN to TLCEvents and eight 2026 Dáil fragments do not resolve to a
declared TLCEvent. None resolves to a TLCReference in these fixtures.
In the current Phase 4 transformer, supported Bill stages and events are
explicitly co-typed `:BillEvent` **and** `eli-dl:LegislativeActivity`
(`transforms/bills.py:_activity`); therefore the Debates ontology comment's
`:BillEvent` target is compatible with those owner resources. Earlier
Tranche 1 notes saying only ELI-DL event typing is available are incomplete.

**Recommended initial boundary for approval:** retain active counts/outcome
rows for source `#ta`/`#nil`/`#staon` integers and the **known**
`#carried`/`#lost` outcomes after the unique `@href` join. Preserve explicit
zero; a count is not an individual voter list. For `#declared`, emit no
`:divisionOutcome` but report the lexical outcome as unresolved controlled
vocabulary evidence. Keep CSV row 42 `future_work`; do not infer a result from
21/22. This is a **source-specific validation exception proposal**, not a
blanket weakening: a golden must assert that the `#declared` lexical value is
audited and no carried/lost triple is emitted, while supported outcome values
remain required when supplied. Keep `voting/@refersTo` row 43 `future_work`,
even for the minority of
non-Summary targets, until the target semantics are reviewed. Its current
`:refersToProposal` comment does not permit Summary and a procedural Summary
must not be silently reinterpreted as a proposal. Keep section-`@refersTo`
row 16 inactive until a resolver demonstrates identity with an existing
Bill-owned event/Work IRI; nonmatching fragments get attribute-specific
unresolved or malformed sidecar outcomes, no
BillEvent/ProcessStage minted from labels or position. No transcript text is
needed for these safeguards.

**Alternatives requiring separate approval:** a distinct named
`eli-dl:DecisionOutcome` for `#declared` only if its official meaning can be
established; a neutrally named source-target relation that accommodates
Summary, DebateSection and resolved Bill-owned event IRIs without calling all
of them proposals. Neither should be activated merely to make the 19-vote
fixture appear complete. If the existing `:refersToEvent` row is eventually
activated for Bill-linked sections, use an exact audited AKN TLCEvent →
existing Phase 4 `:BillEvent` IRI reconciliation. Do not coerce a source
fragment to a Bill event based on stage label/date; where the target is a
resolved Bill Work (`eli:LegalResource`) rather than a concrete event, keep
that distinct. Type a section as `eli-dl:LegislativeActivity` only for a
resolved legislative source reference. This is primarily a source-resolution
and owner-identity concern, not an ontology addition forced by event typing.

The **current official** 2015 Dáil XML (not the older checked-in snapshot)
also has `#staon` aggregates without a Staon member subsection. Correct the
ontology's “from 2026 onwards” annotations to “when supplied” after approval;
no vote-count property or active mapping-status change is necessary.

### O8 — Committee rollCall as attendance, not a Division

**Evidence:** the Public Accounts sample has one `<rollCall>` table with 11
unique `person/@refersTo` attendance entries and **no** division or analysis
voting. The construct is now evidenced, so the old *not observed* rationale
for deferring it is obsolete; that does not make it an AKN Division.

**Recommendation for approval:** keep attendance/rollCall source-only in the
initial RDF scope, with CSV row 44 `future_work`, because the approved initial
graph's contribution/question/division competencies do not require an
attendance claim and no attendance ontology/owner is established. Preserve
the full XML for later review and report its presence. Never assert these
eleven people voted, spoke or participated merely because they appear in the
rollCall table. **Alternative:** if attendance is required now, first approve
a distinct Debates-owned roll-call/attendance model and its evidence/quality
checks; do not reuse `:Division` or Member-vote properties.

Until approval, affected CSV rows stay `future_work`; existing active rows
remain conditional on resolving references to their established owners. In
particular, no `:inHouse` on DebateRecord, `eli-dl:had_participation` on Speech,
or mapping `#declared` to carried/lost.

## Proposed change set if approved (no edits made here)

This table makes the review actionable. It does **not** itself activate a CSV
row or grant permission to edit protected ontology/mapping files.

| Review item | Proposed ontology/contract change | CSV transition after approval |
|---|---|---|
| I1 / sitting | Approve once-encoded FRBR path/eId and Work graph formula; non-`writtens` sitting at `{work IRI}#sitting` under the mechanical metadata rule above. No new class. | Rows 46–48 become conditional `mapped` for eligible actual-sitting records; record/expression identity rows retain original lexical evidence in immutable source. |
| I2 | Fail closed on known multi-Expression Works until complete discovery/bundling is reviewed; record publisher repaths for Tranche 4 reviewed graph retirement. | No per-Expression graph row; no bundle or publication row in this tranche. |
| O1 | `debates.owl.ttl`: declare `:sourceOrdinal a owl:DatatypeProperty ; rdfs:range xsd:integer` (no domain/key). | Row 49 becomes `mapped`; validate 1-based positive, consecutive unique immediate-child ordinals across addressable sibling kinds. |
| O2 | `debates.owl.ttl`: declare `:hasExpression` (DebateRecord → DebateExpression), `:expressionHasSection` (DebateExpression → DebateSection) and `:expressionLanguageCode` (DebateExpression → `xsd:string`); preserve current `:hasSection` as Work shortcut. | Row 9 → `:hasExpression` `mapped`; row 13 `:hasSection` becomes conditional `mapped` and add `:expressionHasSection` row; row 8 → `:expressionLanguageCode` `mapped` from FRBRlanguage only. |
| O3 | `debates.owl.ttl`: declare `:hasQuestion` (DebateSection → ParliamentaryQuestion); clarify `:Speech`/`:hasSpeech` comments to include AKN written-answer response speech without implying one-to-one answer. | Add immediate section/question link row; correct row 31 path to `debateSection[@name='writtenAnswer']` but leave wrapper-only row non-active; preserve active written `:Speech`/`:hasSpeech` only after annotation approval. |
| O4 | `debates.owl.ttl`: declare `:recordOfBody` (DebateRecord → `org:Organization`) and `:recordOfHouseTerm` (DebateRecord → `:HouseTerm`); approve the exact Dáil/Seanad path-plus-author crosswalk and review `agents.owl.ttl` House annotation about committee chambers. | Leave `:inHouse` row 45 inactive; add conditional body/term rows using reviewed owner identities, no new House/Committee descriptions. |
| O5 | `debates.owl.ttl`: declare `:hasSpeechParticipation` (Speech → `eli-dl:Participation`), not an ELI-DL subproperty; approve derived `{speech IRI}#participation`. | Row 22 → conditional `mapped`; row 23 `eli-dl:participation_role` and new `eli-dl:had_participant_person` row only for correctly resolved targets. |
| O6 | `debates.owl.ttl`: declare `:directedToOffice` (ParliamentaryQuestion → `members:NamedOffice`) and import the Members ontology; do not change `:directedTo` range. | Row 30 stays inactive for unresolved TLCRoles; add conditional office row only after reviewed source-role-to-office correspondence. |
| O7 | No new outcome or proposal-target term initially; explicitly allow `#declared` as audited-but-not-emitted while preserving all supported outcome assertions; correct Staon temporal annotations in `debates.owl.ttl` after source review. | Rows 16/42/43 remain inactive pending resolution/target semantics; rows 37–41 retain supported vote/count semantics. |
| O8 | Defer committee rollCall attendance RDF, not the underlying AKN. | Row 44 remains `future_work`; negative golden prevents treating attendance as a Division or vote. |

The specific change set must pass local ontology reasoner validation, active
mapping-term resolution, source-hash/identifier tests and negative goldens for
unknown outcomes, unresolved references and transcript leakage. No source
fixture is changed to obtain a passing result.

## Resource gate and release boundary

The separate corpus gate remains open: the API census excludes written-answer
XML, total primary/written XML bytes and processing/RDF multiplier are not yet
measured. Semantic approval alone does not select full production ingestion or
Bill-only scope, clear the Tranche 1 exit gate, or start Tranche 2.
