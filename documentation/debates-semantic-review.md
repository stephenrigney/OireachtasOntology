# Phase 7 Debates — approved semantic contract

**Status: I1, I2 and O1–O8 decisions implemented and verified for the Tranche 1
semantic/source contract; Tranche 2 representative transformation is complete.**
This note records the approved semantic contract and its historical Tranche 1
implementation checklist; it does not claim that Tranche 3 cross-dataset
resolution or Tranche 4 ingestion/publication is complete.
The governing design is
[`phase-7-debates.md`](phase-7-debates.md); source evidence, mapping status and
exact identity examples are in the other `debates-*` documents. No Debates
transformer work is authorized before the orchestrator confirms the Tranche 1
exit. The production-scope gate applies later, before broad production
ingestion, and does not block Tranche 2.

The decisions were approved separately: accepting IRI/graph identity did not
implicitly approve vocabulary terms, or vice versa. Where a source reference
cannot satisfy an approved predicate, retain the immutable AKN and an auditable
non-RDF outcome rather than minting an entity.

## Identity and graph decisions

### I1 — Canonical public IRIs and original evidence

**Evidence:** the five checked-in records use AKN FRBR Work and Expression
`FRBRuri/@value`; the older Dáil Work URI has no `/debate` suffix, while newer
records have `/debate` or `/writtens`. The Dáil file named `2026-02-26` carries
a 2026-02-25 Work date. The source URI and eId examples in
[`debates-identity-contract.md`](debates-identity-contract.md) are testable.

**Approved decision:** use component-wise RFC 3986 UTF-8 percent encoding
of AKN paths and eIds, Work and Expression subject identities, eId collision
rejection, content/context fallback with fail-closed identical siblings, and
exact-byte source hash/raw XML retention. Do not identify resources by filename,
position, Member label, or a transcription of raw `&` into public IRIs. The
approved graph URI replaces the once-encoded Work IRI path prefix
`/akn/ie/debateRecord` with `/graph/debate` without encoding any segment a
second time. The approved sitting rule emits `{work IRI}#sitting` only when
`FRBRname/@value` is absent or exactly `debate`, the Work does not identify
`/writtens`, and source-type signals do not conflict. Use the Work date for
`eli-dl:activity_date` and link `:producedRecord` to the Work. A `writtens` Work
still has its distinct `DebateRecord` and date but no `DebateSitting`;
publication of written answers does not evidence another activity. A type
disagreement or unreviewed type fails closed for sitting emission and is
reported. Matching House/date alone is not evidence of a sitting. Original
lexical source identities stay in
the preserved XML and source-hash-linked audit report; approval of an
additional RDF identifier literal would be a separate semantic choice.

**Alternative not selected:** reject this public IRI/graph pattern and select a different
path-safe pattern now, before any transformer/golden graph is implemented.
Do not ship both patterns under the same source Work. This is a public identity
decision, not a local code-helper choice.

### I2 — Multiple expressions of the same Work

**Evidence:** each audited fixture contains one Expression, but the FRBR model
allows more than one Expression per Work. Phase 7 fixes **one replaceable graph
per Work/record**, not one graph per Expression; replacing it from one
Expression in isolation could delete other valid Expression triples.

**Approved initial policy:** treat the Work as the
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
but its current official path includes it), the approved path rule creates distinct
Work and graph IRIs. Do not infer `owl:sameAs`, merge them by House/date, or
delete an old graph automatically. Flag the identity change for reviewed
replacement/retirement in Tranche 4; an already-published same-context graph
must not coexist silently with the new graph. This is an endpoint lifecycle
issue, not a Phase 6 scan-cadence choice.

## Ontology/mapping decisions

The findings in this section distinguish the audited source from the
ontology/mapping baseline reviewed before approval. The approved Debates
ontology/mapping additions have since passed local ontology validation,
active-term checks and static contract tests. This does not verify runtime
transformation or cross-resource resolution; see the Tranche 1 exit and Tranche
2 boundary below.

### O1 — Lightweight source order

**Baseline evidence:** a `debateSection` can nest sections, speeches, summaries
and questions in mixed AKN sibling order. The reviewed ontology baseline had no
ordinal; pinned `eli-dl:activity_order` has Activity domain and decimal range.

**Approved decision:** add `:sourceOrdinal` as an
`owl:DatatypeProperty` with `rdfs:range xsd:integer` and no class domain or
functional-key implication. Map it on sections and addressable contributions;
validation requires a positive, consecutive, unique 1-based ordinal among addressable
immediate children of each containing XML resource, across child kinds. This
is ordering metadata only, never an IRI ingredient. XML remains authoritative
for the complete document order. Addressable children include DebateSection
(including division and ta/nil/staon groups), Speech, Summary and
ParliamentaryQuestion; each nested container restarts the sequence. The active
source-order mapping row and ontology declaration pass static contract and
ontology validation. Runtime ordinal assignment and emitted-RDF ordering remain
Tranche 2 work.

**Alternative not selected:** omit RDF ordering and retain XML order only. This fails the
approved Phase 7 query/order requirement and would need an explicit change to
that acceptance contract; do not treat it as an implementation shortcut.

### O2 — Record, Expression and top-level structure

**Baseline evidence:** `:DebateRecord` and `:DebateExpression` existed, but no
predicate linked them. AKN `debateBody` contains the top-level sections of the
source document described by its FRBRExpression metadata; the baseline
`:hasSection` declared DebateRecord domain. An Expression URI ending
`mul@` may carry `FRBRlanguage/@language="eng"`; URI spelling is not a safe
language assertion. The multiple-Expression policy in I2 changes how top-
level section containment must be interpreted.

**Approved decision:** add `:hasExpression` (ObjectProperty;
`DebateRecord` → `DebateExpression`) and `:expressionHasSection`
(ObjectProperty; `DebateExpression` → top-level `DebateSection`). Keep the
existing `:hasSection` from Work to the same top-level sections as a
Work-level convenience union; only the Expression relation defines their
immediate source-order scope. On the five single-Expression fixtures these
two links target the same top sections; if complete multi-Expression publication
is separately approved in the future, the Work-level shortcut may include all
its Expression sections without claiming one global sequence. Add `:expressionLanguageCode`
(DatatypeProperty; domain `DebateExpression`; range `xsd:string`) using the
exact `FRBRlanguage/@language` lexical code; no language assertion is inferred
from the Expression URI. The corresponding Work/Expression and language rows
are active and pass the static mapping and ontology checks. Runtime linking and
language-value emission remain Tranche 2 work.

**Alternatives not selected:** `dct:hasPart` / `dct:isPartOf` are recognized and
have no constraining domain/range in the repository but express only generic
part-whole; `eli:is_realized_by` / `eli:realizes` carry FRBR semantics but infer
ELI Work/Expression typing, contrary to the current intentionally bare
`:DebateExpression` class. Likewise, `dct:language` or `eli:language` would
require a reviewed language-resource identity, not a URI inferred from
`mul@`. The approved local lexical code avoids that unsupported join.

### O3 — Questions and written responses

**Baseline evidence:** `question` nodes occur within question and `writtenAnswer`
sections. A written-answer section may contain multiple questions and a
response `<speech>`. The reviewed ontology baseline lacked question-to-section
containment and described Speech as oral although written answers encode their
response as `<speech>`.

**Approved decision:** add `:hasQuestion` (ObjectProperty; domain
`:DebateSection`, range `:ParliamentaryQuestion`) for the immediate containing
section. Clarify the `:Speech` annotation to cover AKN `speech` used for oral
and written contributions, without making Speech an ELI-DL Activity merely
because of its name. Continue to map `writtenAnswer` as a DebateSection and
link its direct speech via existing `:hasSpeech`. Do not assert a one-to-one
question-to-answer link absent source correspondence. The question and
written-speech content remains outside RDF.

**Alternative not selected:** use a separate written-response class/relationship only if
source evidence requires a distinct semantic entity; this expands the model
and does not justify guessing which response answers each question.

**Implementation note:** the CSV marks `:Speech` and `:hasSpeech` active for
`writtenAnswer` response `<speech>` nodes. The approved `:Speech` annotation
clarification and `:hasQuestion` declaration are present and pass ontology and
static mapping checks. Do not treat these emissions as oral-only or create a
one-to-one answer link. Mapping-integrity validation alone cannot detect a
semantic contradiction. The current fixture has 197 response speeches under
197 writtenAnswer sections; 12 such sections have 2–8 questions, so a direct
one-to-one answer link is unsupported.

**Historical selector correction:** an earlier version of mapping row 31 used
`debateBody//writtenAnswer`, but the source has no `<writtenAnswer>` element;
it has `debateSection[@name='writtenAnswer']`. The current non-active row 31
uses the corrected selector and documents that no wrapper-specific entity or
relation is emitted. The general active rows map the source section, its direct
question and its response speech individually.

### O4 — Host body and numbered term without BillEvent inference

**Evidence:** the outline suggests `:inHouse` on DebateRecord, but its
executable domain is `:BillEvent`, and `members:Committee` is not an enduring
House. A Work author can be a generic `#oireachtas` rather than a resolved
HouseTerm. Written-answer records still need a host query even if they do not
denote a sitting activity.

**Approved decision:** add a direct record-to-existing-body relation
(`:recordOfBody`; ObjectProperty; domain `:DebateRecord`; range
`org:Organization`, retaining the approved broad range). Assert it only when
the source record's body resolves to an authoritative House or Committee IRI;
the required target restriction is specified below. Do not mint/descriptively
type a Committee from a venue slug. Add
`:recordOfHouseTerm` (ObjectProperty; domain `:DebateRecord`; range
`:HouseTerm`) only where `FRBRauthor/@href` resolves to an existing numbered
term. The numbered term must not be mistaken for the enduring host House;
derive the House from that term's existing `:termOf` target, not from the
term URI's spelling. For chamber Works, use the approved explicit venue crosswalk
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

**Alternative not selected:** introduce two narrowly typed host properties, one for House
and one for Committee; this avoids a broad range but makes a unified query
less direct. Reusing `:inHouse` on DebateRecord is **not** an option without an
approved domain change that also preserves existing BillEvent semantics.

The loaded axioms do not entail `org:Organization` as a common superclass of
the House and Committee classes. `members:Committee` is a subclass of
`org:Organization`, while `members:House` is a subclass of `agents:House`,
which is a subclass of `agents:ParliamentaryBody`, itself a subclass of
`org:FormalOrganization`; no `org:FormalOrganization` to
`org:Organization` subclass axiom is asserted. Keep the approved broad
`org:Organization` range on `:recordOfBody` unchanged. That range is not an
identity whitelist: SHACL/runtime target validation must still restrict links
to an existing resolved House or Committee. A source committee IRI may be
referenced without describing it in the Debates graph even when its owning
Committee dataset has not yet been published; determine resolution against the
actual authoritative owner registry, not from the source path or label alone.

**Existing ontology mismatch:** the `agents.owl.ttl` comment describes
`agents:House` as Dáil and Seanad enduring institutions but also says
“Committee chambers are also instances of :House.” That comment is not an OWL
subclass axiom connecting `members:Committee` to `agents:House`; the loaded
class axioms keep `members:Committee` under `org:Organization`. An AKN
committee author points to a Committee IRI, not evidence for typing it as an
enduring House. The approved record-host model distinguishes a *chamber* (if
that notion is actually used) from the Committee organisation; do not type a
Committee as `:House` to make `:inHouse` fit. Any proposed change to the
separate House annotation or class hierarchy requires separate semantic
review; neither is changed by O4.

The `eli-dl:parliamentary_term` property is not a neutral substitute for the
approved `:recordOfHouseTerm` link: on a current bare DebateRecord it may infer
ELI Work typing. Keep the local approved relation's meaning explicit; do not
change it to ELI-DL parliamentary-term semantics by accident.

### O5 — Speech participation without Activity inference

**Evidence:** `eli-dl:had_participation` has Activity domain, while current
`:Speech` is not an Activity; applying it to Speech would infer Activity. AKN
`speech/@by` and optional `@as` are the source slots. The committee sample has
929 speeches, some `@by="#"` placeholders and no inspected `@as` role values;
it does **not** establish a witness individual or `:WitnessRole` for those
speeches. The written-answer sample uses `<speech>` for responses.

**Approved decision:** add `:hasSpeechParticipation`
(ObjectProperty; domain `:Speech`; range `eli-dl:Participation`), **not** a
subproperty of `eli-dl:had_participation`. Use one deterministic
`{speech IRI}#participation` only when a resolved person and/or reviewed
participation role is available for that single AKN speaker; from that
Participation use pinned `eli-dl:had_participant_person` for an existing
person IRI and `eli-dl:participation_role` only for an existing role individual
of the correct type. If neither resolves, omit the Participation and report
source references; never mint a witness/person/ministerial office from a
committee context, label or `#`. Existing `:speaker` stays a resolved-Member
shortcut. CSV rows 22–23 are active and statically verified with conditional
target-resolution requirements. Runtime role resolution and participation
emission remain Tranche 2/3 work; no Speech becomes an Activity by inference.

**Alternative not selected:** explicitly type Speech as ELI-DL Activity and reuse
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

**Approved decision:** keep `:directedTo` only when the source
reference resolves to an actual existing ParticipationRole. Add a separate
`:directedToOffice` (ObjectProperty; domain `:ParliamentaryQuestion`; range
`members:NamedOffice`) only if the source role can be uniquely and
reviewably reconciled to an existing office identity. The property declaration
and Members ontology import pass ontology and static contract checks. Retain an attribute-specific
resolution/evidence table; each role-to-office match must be uniquely and
reviewably reconciled, and label equality cannot establish the target. An
unresolved, malformed or absent `@to` produces the documented
non-RDF outcome and no invented office or role. CSV row 30 remains inactive for
unresolved TLCRoles and is conditional on verified unique resolution. Do not reuse
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

**Approved initial boundary:** retain active counts/outcome
rows for source `#ta`/`#nil`/`#staon` integers and the **known**
`#carried`/`#lost` outcomes after the unique `@href` join. Preserve explicit
zero; a count is not an individual voter list. For `#declared`, emit no
`:divisionOutcome` but report the lexical outcome as unresolved controlled
vocabulary evidence. Keep CSV row 42 `future_work`; do not infer a result from
21/22. This is an **approved source-specific validation exception**, not a
blanket weakening: a golden must assert that the `#declared` lexical value is
audited and no carried/lost triple is emitted, while supported outcome values
remain required when supplied. Keep `voting/@refersTo` row 43 `future_work`
under this approved initial boundary, even for the minority of non-Summary
targets. Its current
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
also has `#staon` aggregates without a Staon member subsection. The approved
annotation correction to “when supplied” is present in `debates.owl.ttl` and
passes ontology validation. No vote-count property or active mapping-status
change is necessary. Actual omission of an outcome for `#declared` still needs
an RDF-level Tranche 2 golden; static mapping tests do not prove non-emission.

### O8 — Committee rollCall as attendance, not a Division

**Evidence:** the Public Accounts sample has one `<rollCall>` table with 11
unique `person/@refersTo` attendance entries and **no** division or analysis
voting. The construct is now evidenced, so the old *not observed* rationale
for deferring it is obsolete; that does not make it an AKN Division.

**Approved decision:** keep attendance/rollCall source-only in the
initial RDF scope, with CSV row 44 `future_work`, because the approved initial
graph's contribution/question/division competencies do not require an
attendance claim and no attendance ontology/owner is established. Preserve
the full XML for later review and report its presence. Never assert these
eleven people voted, spoke or participated merely because they appear in the
rollCall table. **Alternative not selected:** if attendance is required in a
future scope, first approve
a distinct Debates-owned roll-call/attendance model and its evidence/quality
checks; do not reuse `:Division` or Member-vote properties.

The approved ontology/mapping additions implementing these decisions pass
ontology validation, active mapping-term resolution and static Debates
contract tests. Rows remain non-active where the approved boundary says so or
until their conditional owner-resolution requirements are met; active rows
remain conditional on resolving references to their established owners.
Tranche 2 implements conditional reference resolution and RDF output against
representative fixtures; broad owner integration remains Tranche 3 work. In
particular, do not use `:inHouse` on DebateRecord,
`eli-dl:had_participation` on Speech, or map `#declared` to carried/lost.

## Approved change set and implementation checklist

The decisions below are approved. The Debates ontology/mapping changes listed
here pass ontology reasoner validation, mapping-integrity checks and focused
static contract tests. These checks do not verify a Debates transformer or
actual RDF emission. A previously noted separate `agents.owl.ttl`
House-annotation edit was present during earlier repository validation but is
no longer present in the current worktree; it was outside O4 approval and is
not part of the approved Debates change set.

| Review item | Approved ontology/contract change | Mapping implementation condition |
|---|---|---|
| I1 / sitting | Use component-wise encoded Work/Expression/eId IRIs; replace `/akn/ie/debateRecord` with `/graph/debate` in the once-encoded Work IRI path without re-encoding. Emit `{work IRI}#sitting` only when `FRBRname` is absent or `debate`, the Work does not identify `/writtens`, and signals agree. No sitting for written-answer Works. | Rows 46–48 are conditional `mapped` only for eligible actual sittings; preserve original lexical identity evidence in immutable source. |
| I2 | Fail closed per Work when multiple Expressions are known; no graph from one Expression in isolation and no claim that one fetched file proves global completeness. Record publisher repaths for Tranche 4 reviewed graph retirement. | No per-Expression graph, bundle or publication row in this tranche. |
| O1 | `debates.owl.ttl`: declare `:sourceOrdinal a owl:DatatypeProperty ; rdfs:range xsd:integer` (no domain/key). | Row 49 is active and statically verified; runtime must assign positive, consecutive, unique 1-based ordinals among immediate addressable siblings across kinds. |
| O2 | `debates.owl.ttl`: declare `:hasExpression` (DebateRecord → DebateExpression), `:expressionHasSection` (DebateExpression → DebateSection) and `:expressionLanguageCode` (DebateExpression → `xsd:string`); preserve current `:hasSection` as Work shortcut. | Work/Expression, top-section and language mapping rows are active and statically verified; runtime linking and language emission remain Tranche 2 work. |
| O3 | `debates.owl.ttl`: declare `:hasQuestion` (DebateSection → ParliamentaryQuestion); clarify `:Speech`/`:hasSpeech` comments to include AKN written-answer response speech without implying one-to-one answer. | Current row 31 uses `debateSection[@name='writtenAnswer']` but remains non-active for wrapper-specific modeling; general active rows cover section, question and direct response speech without a one-to-one answer relation. |
| O4 | `debates.owl.ttl`: declare `:recordOfBody` (DebateRecord → `org:Organization`) and `:recordOfHouseTerm` (DebateRecord → `:HouseTerm`); use the approved Dáil/Seanad path-plus-author crosswalk. No `:inHouse` on DebateRecord and no committee-as-House inference. | Conditional body/term mapping rows are active and statically verified; runtime resolution must use reviewed owner identities, never new House/Committee descriptions. The separate `agents.owl.ttl` annotation correction is not part of this approval. |
| O5 | `debates.owl.ttl`: declare `:hasSpeechParticipation` (Speech → `eli-dl:Participation`), not an ELI-DL subproperty; derive `{speech IRI}#participation` only with a resolved person and/or reviewed role. | Rows 22–23 are active and statically verified, conditional on correctly resolved existing targets; never infer a witness or type Speech as Activity. |
| O6 | `debates.owl.ttl`: declare `:directedToOffice` (ParliamentaryQuestion → `members:NamedOffice`) and import the Members ontology; do not change `:directedTo` range. | Row 30 remains inactive for unresolved TLCRoles; assert only conditional, uniquely and reviewably resolved office matches. |
| O7 | No new outcome or proposal-target term initially; `#declared` is audited but not emitted as an outcome; correct Staon temporal annotations in `debates.owl.ttl` to “when supplied”. | Row 42 remains `future_work`; row 43 stays inactive under the approved boundary; row 16 stays inactive until exact existing Bill-owned identity resolution. Rows 37–41 retain supported vote/count semantics. |
| O8 | Defer committee rollCall attendance RDF, not the underlying AKN. | Row 44 remains `future_work`; Tranche 2's RDF-level negative golden must prevent treating attendance as a Division, vote or participation. |

The ontology/mapping change set has passed local ontology reasoner validation,
active mapping-term resolution, source-hash/identifier checks, 28 focused
Debates tests and the full suite (427 passed, 8 skipped). This closes the
Tranche 1 static contract, not runtime RDF verification. Tranche 2 must execute actual transformations and
assert both positive output and RDF-level non-emission for unknown outcomes,
unresolved references, `rollCall` attendance and transcript leakage. Static
negative contract tests do not prove that triples are omitted from transformed
RDF. No source fixture is changed to obtain a passing result.

Verification used the project Java runtime through `mise exec --`: run
`mise exec -- .venv/bin/python tests/validate.py`,
`mise exec -- .venv/bin/python -m pytest tests/test_debates*.py -q` and
`mise exec -- .venv/bin/python -m pytest tests`.

## Resource gate and release boundary

The production-scope census/benchmark remains open; the API census excludes
written-answer XML, and total in-scope XML volume, runtime and RDF output have
not yet been measured. This gate does **not** block Tranche 1 source-contract
completion or Tranche 2 implementation and representative-fixture tests. Tranche
2 follows the completed Tranche 1 contract and must cover
representative Dáil, Seanad, committee and written-answer records.

After the core transformer exists and before broad production ingestion,
enumerate the full in-scope corpus including `writtens`, measure XML volume, and
benchmark elapsed runtime, working/storage needs and RDF output on representative
records. Decide full-corpus versus Bill-debates-first production ingestion from
the measured XML volume, runtime and RDF output against deployment budgets; do
not infer a scope choice from record counts or choose an arbitrary cutoff.
Phase 6 scan cadence, scheduling and reconciliation policy remains unchanged.
