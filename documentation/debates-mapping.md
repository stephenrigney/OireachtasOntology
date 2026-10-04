# Phase 7 Debates mapping — approved Tranche 1 mapping contract

This is the approved mapping contract for the Phase 7 Debates vertical slice,
incorporating the approved identity and semantic decisions in
[`debates-semantic-review.md`](debates-semantic-review.md) and
[`debates-identity-contract.md`](debates-identity-contract.md). The Tranche 1
semantic/source contract and Tranche 2 representative RDF acceptance are
complete. The production resource gate, broad owner integration and publication
remain pending. The executable vocabulary is `ontology/debates.owl.ttl`; the
matching CSV is
[`mappings/debates_mapping.csv`](../mappings/debates_mapping.csv). Every active
local term in that CSV must resolve to one local ontology definition before
mapping-integrity validation can pass.

## Source and CSV conventions

The authority is the preserved Akoma Ntoso XML document, not an API envelope.
The CSV keeps the repository's seven columns verbatim:

```text
json_path,json_field,ontology_term,term_type,source_file,mapping_status,notes
```

Despite the legacy names, `json_path` is a namespace-agnostic, XPath-style AKN
path relative to the `<debate>` element: `/` selects a child, `//` selects a
descendant, predicates such as `[@name='division']` select source elements,
`@attribute` selects an XML attribute, and the `json_field` value identifies
the selected field or relationship. XML namespace declarations are omitted;
element names mean the AKN local names. A class row names the source element in
`json_path` and uses `json_field` for the element/subject; identity rows point
to `FRBRuri/@value` or `@eId`. Relationship rows identify the AKN parent/child
or source reference and explain any join in `notes`.

`mapped` rows are active assertions, subject to the explicit source-shape and
reference-resolution conditions in each row. `implicit` rows document
resource identity/class context without requesting a separate predicate.
`future_work` rows are non-active proposals or source-only boundaries and are
intentionally excluded from mapping-integrity checks. Active mapping integrity
does not validate path syntax, OWL domain/range, source joins, resolver
correctness, URI strategy, graph ownership, or source completeness.

The approved identity contract uses the exact XML-parsed
`FRBRWork/FRBRuri/@value` and `FRBRExpression/FRBRuri/@value` as Work and
Expression identity, with component-wise RFC 3986 UTF-8 path encoding. eIds
are expression-scoped, case-sensitive, collision-checked and component-encoded;
the approved deterministic fallback applies only to missing/empty eIds, and
identical siblings fail closed rather than receiving position-based IDs. Never
use `FRBRthis`, a file name, a label, or document position as resource identity.
The Work-keyed graph pattern and `{work IRI}#sitting` rule are approved as
specified in the identity contract. Preserve exact original AKN identifiers
and exact source bytes in immutable raw AKN and its source-hash-linked audit
report; do not invent RDF identifier literals or entities to carry unresolved
source evidence.

Under I2, the Work is the source/publication unit. If multiple Expressions for
one Work are known, fail closed for that Work rather than publishing/replacing
its graph from one Expression. A single fetched file does not prove global
Expression-set completeness; do not claim such completeness or introduce
multi-Expression bundling/per-Expression graphs without the separately reviewed
discovery and completeness contract.

## Active mappings and emission conditions

An active row requests the following RDF only under its stated source and
resolution conditions. Conditional rows are active mappings, not permission to
emit speculative targets:

| Source | Active mapping | Conditions |
|---|---|---|
| `meta/identification/FRBRWork` and `FRBRExpression` | `:DebateRecord`, `:DebateExpression`; `:hasExpression` | Both are Debate-owned resources. Link each Work to its Expression. Public resource and graph IRIs follow the approved identity contract; original FRBR identifiers remain in raw AKN and source-hash-linked audit evidence. A known multi-Expression Work fails closed (I2). |
| `FRBRWork/FRBRdate[@name='#generation']/@date` | `:debateDate` (`xsd:dateTime`) | Convert the record date to `YYYY-MM-DDT00:00:00` without adding a timezone. The XML value, not the fixture filename, is authoritative. Retain this date for written-answer DebateRecords too; a record date alone does not establish a sitting. |
| `FRBRWork/FRBRname/@value` | `:debateType` (`xsd:string`) | Optional; omit if absent. |
| `FRBRExpression/FRBRlanguage/@language` | `:expressionLanguageCode` (`xsd:string`) | Copy the exact lexical code. Do not infer language from URI spelling such as `mul@` or `eng@`. |
| Top-level `debateBody/debateSection` | `:expressionHasSection` and Work convenience `:hasSection` | Link the top section to its containing Expression; also link the DebateRecord to those same top sections. Only the Expression predicate defines their immediate-child ordering scope. A Work convenience edge does not assert one global order across Expressions. |
| `debateBody//debateSection` and `@name` | `:DebateSection`; `:sectionName` | Map structural name metadata only. A `name="division"` source node is also typed `:Division` using that same resource. Preserve original eIds in the immutable AKN and hash-linked report. |
| Addressable section/contribution children | `:sourceOrdinal` (`xsd:integer`) | Assign positive, consecutive 1-based ordinals to addressable immediate children of each containing XML resource, across mixed kinds. Addressable nodes are DebateSection (including `division`, `ta`, `nil`, and `staon`), Speech, Summary, and ParliamentaryQuestion. Each nested container restarts at 1. Ordinal is ordering metadata only, never an IRI ingredient. |
| Nested `debateSection` except a child named `division` | `:hasSubSection` | Both endpoints are DebateSections. The parent-to-division edge is instead `:hasDivision`; `ta`, `nil`, and `staon` child sections remain DebateSections. |
| Direct child `speech` / `summary` of a DebateSection | `:hasSpeech` / `:hasSummary`; child classes `:Speech` / `:Summary` | Structural links/resources only, including a response `speech` under a `writtenAnswer`-named DebateSection. Do not assert a one-to-one question/response link or flatten the containing section. No prose is emitted. |
| Direct child `question` of a DebateSection | `:hasQuestion` | Link each ParliamentaryQuestion to its immediate containing section, including `debateSection[@name='writtenAnswer']`; do not associate it with a particular response speech. |
| `speech/from/recordedTime/@time` | `:recordedTime` (`xsd:dateTime`) | Applies only to the recorded-time element under a Speech's `from`; do not map surrounding `from` display text or heading times. |
| `speech/@by` | `:speaker` | Only when the AKN person reference resolves through TLCPerson to an existing `agents:Member`. Reference-only; witnesses and other non-Members receive no `:speaker` assertion. |
| Speech `@by` and `@as` | `:hasSpeechParticipation`; `eli-dl:Participation`; `eli-dl:had_participant_person`; `eli-dl:participation_role` | Create `{speech IRI}#participation` only if `@by` resolves through TLCPerson to an existing Member IRI or `@as` resolves through a separately reviewed exact source-reference crosswalk to an existing correctly typed ParticipationRole. In the initial slice, a resolved Member IRI is the only supported `@by` participant-person target; non-Member person/witness references remain auditable unresolved pending owner/crosswalk review. No `@as` crosswalk is presumed: absent one, emit no role assertion and report the source value. Never infer a role or match by label. Do **not** use `eli-dl:had_participation` or infer that Speech is an Activity. |
| `question` and `question/@by` | `:ParliamentaryQuestion`; `:askedBy` | Type questions, including those within a `writtenAnswer`-named section; link `askedBy` only to a resolved existing Member. Question text is excluded. |
| `meta/identification/FRBRWork` plus `FRBRauthor/@href` | `:recordOfBody`; `:recordOfHouseTerm` | Conditional reference-only host links. The exact chamber venue/author agreement or official Committee-author identity must resolve to an existing House/Committee owner; an author href becomes `:recordOfHouseTerm` only if it resolves to an existing numbered HouseTerm. No targets are minted or inferred from labels/slugs/date. `:inHouse` remains inactive. |
| Eligible non-`writtens` record context and Work date | `:DebateSitting`; `:producedRecord`; `eli-dl:activity_date` | Derive `{canonical Work IRI}#sitting` only when Work URI does not identify `/writtens` and `FRBRname` is absent or exactly `debate`. If signals disagree or an unreviewed type occurs, emit no sitting and report. Link the sitting to its record and put the Work date on the sitting only when eligible. Written-answer records retain `:DebateRecord` and `:debateDate`, but get no `DebateSitting`, `:producedRecord`, or activity date. |
| Direct child `debateSection[@name='division']` | `:hasDivision`; child class `:Division` | Parent is a DebateSection; target is the child division node also typed as DebateSection. Division and its children remain owned by the Debates graph. |
| `person/@refersTo` under a division's `ta`, `nil`, or `staon` section | `:votedFor`, `:votedAgainst`, `:abstained` | Resolve only to an existing Member. Emit Staon only when supplied; omit empty/unresolved references. No Member description is copied. |
| `analysis/parliamentary/voting/@outcome` | `:divisionOutcome` | Join through `@href` to a Summary eId contained by exactly one `name="division"` node. Map only known `#carried`/`#lost` outcomes. A missing or ambiguous join emits nothing; `#declared` is retained as unresolved controlled-vocabulary evidence and emits no outcome. |
| `analysis/parliamentary/voting/count[@refersTo='#ta'|'#nil'|'#staon']/@value` | `:taCount`, `:nilCount`, `:staonCount` | Use the same unique `voting/@href` → result-Summary → containing-Division join; parse `xsd:integer`. Omit a missing count and preserve explicit zero. Counts are not individual voter lists. |

`voting/@href` is the result-Summary join used for outcome/count association;
it is **not** a Summary-to-Division RDF link. Conversely,
`voting/@refersTo` identifies the voted-on target, not the result Summary. It
may target a Summary, TLCEvent, or DebateSection and remains unmapped pending
target-semantics review. The unique `@href` → Summary → exactly-one-containing-
Division join holds for all 19 analysis votes in the five checked-in fixtures
(8 older Dáil, 9 newer Dáil, 2 Seanad; none in the committee/written-answer
fixtures). A missing or non-unique join is reported, never assigned by position.

All Member, House, HouseTerm, Committee, ParticipationRole/person, Bill, and
event targets remain owned by their existing verticals. Debates may link to a
target only after authoritative resolution; it must not emit the target's
class, label, or descriptive triples. A failed/unresolved source reference
creates no placeholder, guessed IRI, or descriptive entity; preserve its exact
raw value and source pointer in the audit report tied to the exact source-byte
SHA-256. Transcript prose is never copied into RDF.

## Explicit non-active source/semantic gaps

Approved decisions do not authorize unsupported source assertions. The
following `future_work` rows remain non-active; resolve each source reference
only under a separately reviewed exact identity rule:

| Non-active mapping | Why it remains non-active |
|---|---|
| `question/@to` → `:directedTo` | A TLCRole href or label does not prove an existing `eli-dl:ParticipationRole` identity. Keep row 30 `future_work` until recipient reconciliation resolves the exact source reference. |
| `question/@to` → `:directedToOffice` | The ontology term exists, but its mapping is deliberately inactive. No label matching; require an attribute-specific, reviewable mapping to an existing `members:NamedOffice`. |
| `debateSection/@refersTo` → `:refersToEvent` | Keep inactive until the exact AKN reference resolves under the reviewed rule to an existing Bill-owned event/Work IRI. The blocker is AKN-to-owner identity resolution, not a class mismatch: the current Bill transformer co-types concrete bill events as `:BillEvent` and `eli-dl:LegislativeActivity`. Never mint a target or resolve by label/position. |
| `voting/@refersTo` → `:refersToProposal` | Keep inactive for every target kind pending target-semantics review. The five fixtures have 19 distinct vote-target references: 14 Summary, four TLCEvent, and one DebateSection target; do not coerce any of them to a proposal. |
| `voting/@outcome='#declared'` → `:divisionOutcome` | Keep row 42 `future_work`. The Seanad fixture has `#declared` with Tá 21 / Níl 22; emit no `DeclaredCarried` or `DeclaredLost`, and do not derive the outcome from counts or narrative. Preserve the lexical value in hash-linked audit evidence. |
| Committee `rollCall` | Keep row 44 `future_work` and source-only. The committee fixture has an attendance table with 11 referenced people and no division/analysis vote; do not infer vote, Speech, or participation from attendance. |
| `FRBRauthor/@href` → `:inHouse` | Keep row 45 `future_work`; the executable domain is BillEvent, not DebateRecord or DebateSitting. Use only the approved conditional `:recordOfBody`/`:recordOfHouseTerm` rows. |
| Unresolved references as RDF | The approved reference-outcome contract is a non-RDF, source-hash-linked report. There is no approved RDF evidence predicate: preserve the original source and report raw values/context without placeholders, guessed links, or new entities. |
| AKN `answer`, full Manifestation, or transcript/prose text | No `<answer>` occurs in the five fixtures; full Manifestation is deferred and all speech, question, response, summary, heading, `from`, and paragraph prose remains outside RDF. Preserve the complete source bytes for replay. |

The Seanad source supplies `#declared` as one of 19 analysis votes; the other
18 use known `#carried`/`#lost` values. The supported count rows and those
known outcomes stay active. Outcome/count association uses only a unique
`voting/@href` → result-Summary eId → exactly-one-containing-Division join;
`voting/@refersTo` is an independent target reference. A missing/ambiguous
join emits no associated outcome or count, and an absent count is never zero.
The approved non-RDF source-hash outcome rows preserve original source
identifiers and exact reference values for later reconciliation.

## Representative fixtures and expected RDF/negative golden contract

The five immutable AKN fixtures are:

* `data/debates_examples/dail_2015-07-02.akn.xml` — Dáil questions, nested
  sections, speeches/summaries and divisions. Its Work has no `FRBRname`, an
  older Work URI without `/debate`, and a generic `#oireachtas` author.
* `data/debates_examples/dail_2026-02-26.akn.xml` — Dáil sections, recorded
  times, division counts/outcomes, individual votes and Staon. Its FRBR Work
  date is 2026-02-25 (not the filename date); Expression URI includes `mul@`
  while `FRBRlanguage/@language` is `eng`.
* `data/debates_examples/seanad_2015-07-02.akn.xml` — Seanad division with
  `#declared`, to exercise the no-outcome negative.
* `data/debates_examples/committee_public_accounts_2026-09-24.akn.xml` —
  Committee speeches (including unresolved/non-Member speakers) and a
  source-only `rollCall` attendance table.
* `data/debates_examples/dail_written_answers_2015-07-02.akn.xml` — separate
  `writtens` Work with 20 `writtenAnswers` groups, 197
  `debateSection[@name='writtenAnswer']` sections, 229 questions and 197
  response `speech` nodes. The source has **no** `<writtenAnswer>` element;
  some sections contain multiple questions.

All five original fixture files remain byte-preserved; byte counts, source
SHA-256 values, retrieval URLs and the complete source audit are in
[`debates-source-audit.md`](debates-source-audit.md). They are tranche coverage
targets, not proof that the Phase 7 volume/resource gate has passed. Do not
modify source fixtures to make a mapping pass.

The ontology and approved decisions define stable public Work, Expression,
component-eId, graph and eligible sitting IRIs. Future Tranche 2 golden outputs
must be deterministic RDF datasets for the exact immutable source bytes,
mapping and ontology version, and assert all and only supported statements in
the Debates-owned graph. No transformer or golden RDF fixture is produced by
this mapping update. Goldens and negative tests must prove at least:

1. **Identity and source evidence:** Work/Expression classes and `:hasExpression`
   use canonical IRIs under the approved identity contract. Preserve original
   lexical AKN identifiers in raw XML and source-hash-linked audit evidence;
   do not emit invented identifier literals/entities. Known multiple
   Expressions for one Work fail closed; a single file does not prove global
   Expression completeness.
2. **Expression/work structure and order:** each top-level section has
   `:expressionHasSection` and the Work convenience `:hasSection`; nested
   containment, Speech/Summary/Question/Division typing, exact
   `:expressionLanguageCode`, and positive consecutive 1-based `:sourceOrdinal`
   values are correct. Mixed immediate addressable child kinds share a
   containing-resource sequence; nested scopes restart at 1. Position is never
   used for identity.
3. **Record date, sitting and hosts:** Work dates populate `:debateDate` on
   every DebateRecord, including written-answer records. Eligible absent-name
   and `debate` Work types receive `{work IRI}#sitting`, `:producedRecord`, and
   `eli-dl:activity_date`; `writtens` receives none of those sitting/activity
   assertions. Disagreeing/unreviewed type signals fail closed. Host/HouseTerm
   links exist only for the approved exact source/owner resolution; no
   `:inHouse` and no copied foreign descriptions appear.
4. **Questions and written responses:** the immediate section gets
   `:hasQuestion`; the response Speech remains a direct `:hasSpeech` child of
   the existing `writtenAnswer`-named DebateSection. There is no additional
   wrapper resource, one-to-one question/response edge, or transcript text.
   The local name selector is `debateSection[@name='writtenAnswer']`, not a
   nonexistent `<writtenAnswer>` element.
5. **Speech participation:** only a deterministically derived Participation
   with at least one conditionally resolved component is linked by
   `:hasSpeechParticipation`. In the initial slice, `@by` can supply only an
   existing Member IRI resolved through TLCPerson; non-Member person/witness
   references remain auditable unresolved until an owner/crosswalk is reviewed.
   `@as` supplies a role only if a separately reviewed exact TLCRole-to-
   ParticipationRole crosswalk uniquely resolves to an existing correctly
   typed role. Without that crosswalk, emit no role assertion and report `@as`;
   never infer a role or match labels. Each emitted target is reference-only;
   unresolved/placeholder references create no Participation component or
   guessed target. There is no `eli-dl:had_participation` assertion and no
   Speech Activity inference. `:speaker`/`:askedBy` remain limited to resolved
   existing Members.
6. **Votes:** body groups, resolved individual Member votes, and supplied
   integer counts (including explicit zero) are preserved. `#carried`/`#lost`
   outcomes/counts associate only through the unique `voting/@href` result
   Summary and containing-Division join. The Seanad `#declared` value is
   recorded in source-hash evidence but produces no `:divisionOutcome`;
   counts never determine it. `voting/@refersTo` produces no target assertion.
7. **Non-active rows:** no triple from `:directedTo`, `:directedToOffice`,
   `:refersToEvent`, `:refersToProposal`, `:inHouse`, `rollCall`, or the
   unresolved-reference evidence placeholder is emitted. Do not infer a
   Division/vote/participation from committee attendance.
8. **Ownership and boundary:** no Member, House, HouseTerm, Committee, person,
   office, Bill or event description is copied into the Debates graph; no
   spoken/written transcript or other prose text appears as an RDF literal.
   Repeated transformation of the same exact source, ontology and mapping is
   deterministic, and the raw source remains the replay input.

Mapping-integrity validation checks active term resolution only; it does not
certify these source joins, conditional rules, RDF outputs or golden criteria.
