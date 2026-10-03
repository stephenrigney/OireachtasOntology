# Phase 7 Debates mapping — Tranche 1 partial contract

This mapping is a deliberately partial source contract for the approved
[Phase 7 design](phase-7-debates.md), not a claim that the Debates model or
Tranche 1 exit criteria are complete. The executable vocabulary remains
`ontology/debates.owl.ttl`; ontology, existing mappings, and
`documentation/mapping_notes.md` were not changed. The matching CSV is
[`mappings/debates_mapping.csv`](../mappings/debates_mapping.csv).

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

`mapped` rows are active assertions. They may have the explicit reference
resolution and source-shape conditions recorded in the row. `implicit` rows
document resource identity/class context without requesting a separate
predicate. `future_work` rows are non-active proposals or source boundary
records; they are intentionally excluded from mapping-integrity checks. No
`new` status is used: this tranche proposes no ontology additions. Passing the
repository's active-term check does not validate path syntax, OWL domain/range,
source joins, URI strategy, or graph ownership.

The class/resource rows are not permission to publish raw AKN identifiers as
public RDF IRIs. The approved URI-safe normalization, identifier evidence,
record/expression/sitting identity, and graph naming must be settled before a
transformer or stable golden graph can be implemented. In particular, use the
AKN `FRBRWork/FRBRuri` as Work identity evidence, not the manifestation-specific
`FRBRthis`; normalize eIds under one reviewed rule and never use array or XML
position as identity.

## Active mappings and emission conditions

The active rows cover only assertions whose term, source role, range, and
ownership are compatible with the current ontology:

| Source | Active mapping | Conditions |
|---|---|---|
| `meta/identification/FRBRWork` and `FRBRExpression` | `:DebateRecord` and `:DebateExpression` classes | Both source resources are Debate-owned. Their identifiers still require the approved URI-safe rule. No expression-to-record link is asserted. |
| `FRBRWork/FRBRdate[@name='#generation']/@date` | `:debateDate` (`xsd:dateTime`) | Convert the source calendar date to `YYYY-MM-DDT00:00:00` without inventing a timezone. The XML date, not a fixture filename, is authoritative. |
| `FRBRWork/FRBRname/@value` | `:debateType` (`xsd:string`) | Optional; omit if absent. |
| `debateBody//debateSection` and `@name` | `:DebateSection`; `:sectionName` | Map structural name metadata only. A `name="division"` node is also typed `:Division` using that very same source eId/resource. |
| Nested `debateSection` except a child named `division` | `:hasSubSection` | Both endpoints are DebateSections. The parent-to-division edge is instead `:hasDivision`; `ta`, `nil`, and `staon` child sections remain DebateSections. |
| Direct child `speech` / `summary` of a debateSection | `:hasSpeech` / `:hasSummary`; child classes `:Speech` / `:Summary` | These are structural links/resources only, including a speech under a `writtenAnswer` debateSection. This does not claim any one-to-one question/response link or flatten the wrapper. No prose is emitted. |
| `speech/from/recordedTime/@time` | `:recordedTime` (`xsd:dateTime`) | Applies only to the recorded-time element under a Speech's `from`; do not map `from` display text or heading times. |
| `speech/@by` | `:speaker` | Only when the AKN person reference resolves through `TLCPerson` to an existing `agents:Member`. This is a reference-only link; witnesses and other non-Members receive no `:speaker` assertion. |
| `question` and `question/@by` | `:ParliamentaryQuestion`; `:askedBy` | Question nodes are typed, including those inside `writtenAnswer`; link `askedBy` only to a resolved existing Member. Question text is excluded. |
| Direct child `debateSection[@name='division']` | `:hasDivision`; child class `:Division` | Parent is a DebateSection; target is the child division node also typed as DebateSection. Division and its children remain owned by the Debates graph. |
| `person/@refersTo` under a division's `ta`, `nil`, or `staon` section | `:votedFor`, `:votedAgainst`, `:abstained` | Resolve only to an existing Member. Emit Staon only when supplied; omit empty/unresolved references. No Member description is copied. |
| `analysis/parliamentary/voting/@outcome` | `:divisionOutcome` | Join by resolving that voting node's `@href` to one summary eId contained by exactly one `name="division"` node. Only `#carried`/`#lost` map to the existing individuals. A missing or ambiguous join emits nothing. |
| `analysis/parliamentary/voting/count[@refersTo='#ta'|'#nil'|'#staon']/@value` | `:taCount`, `:nilCount`, `:staonCount` | Use the same unique `voting/@href` → result-summary → containing-Division join; parse `xsd:integer`. Omit a missing count; preserve an explicit zero. |

`voting/@href` is the result-summary join used for outcome/count association;
it is **not** a new Summary-to-Division RDF link. Conversely,
`voting/@refersTo` identifies the voted-on target and is not assumed to be a
DebateSection or BillEvent. It can resolve to a Summary eId and is therefore
not mapped by the current `:refersToProposal` comment.
The `@href` → Summary → exactly-one-containing-Division join holds for all
analysis votes in the five checked-in fixtures (8 older Dáil, 9 newer Dáil,
2 Seanad; none in the committee/written-answer fixtures). A new source with
a missing or non-unique join must be reported rather than assigned a division
by position.

All Member, House, HouseTerm, committee, role, Bill, and event targets remain
owned by their existing verticals. A Debates graph may link to a target IRI
only after authoritative resolution; it must never emit that target's class,
label, or descriptive triples. A failed/unresolved source reference creates no
placeholder and no guessed IRI.

## Explicit non-active gaps and decisions required

These are blocking semantic or identity decisions, not omissions to be
silently filled by a transformer. The `future_work` CSV rows make them
machine-visible as non-active; they do not assert that the proposal has been
approved.

| Gap | Why it is blocked | Decision needed before activation |
|---|---|---|
| Top-level `:hasSection` and expression structure | AKN sections occur in a FRBRExpression tree, while `:hasSection` starts at DebateRecord and there is no expression-to-record property. | Decide how a language-specific expression's section tree is attached to the Work, including whether section identity/structure is expression-specific. Do not assume direct Work containment. |
| DebateSitting resource and `:producedRecord` | `DebateSitting` is required by the design, but has no AKN eId/URI; no deterministic derived identity rule or source-to-record relation is agreed. | Approve a stable sitting IRI derivation, date property placement, and record link; keep the activity broadly typed as `eli-dl:Activity`. |
| House/HouseTerm/committee host | Outline's `:inHouse` is not usable on DebateRecord or DebateSitting: executable `events.owl.ttl` declares its domain as `:BillEvent`, which would infer a false BillEvent. Work authors vary (`#oireachtas` versus a HouseTerm-like href); committees are not enduring Houses. | Review the host/term/committee relation and target type, including source resolution. Do not infer a target from a label. |
| Debate language / FRBRExpression link | `DebateExpression` has no language property or link to DebateRecord. In the 2026 Dáil fixture the FRBRExpression URI includes `mul@` while `FRBRlanguage/@language` says `eng`. | Decide expression-to-record semantics and use an authoritative language value; do not derive language from URI syntax. |
| Source order | Phase 7 requires scoped integer ordinals, but debates.owl has no source-ordinal property. ELI-DL `activity_order` has Activity domain/decimal range and cannot represent mixed section/contribution order. | Approve an ontology property and exact containing-scope/integer contract before emitting ordinals. Position is never identity. |
| Question containment and recipient | No property connects ParliamentaryQuestion to a section or to its response. `:directedTo` expects `eli-dl:ParticipationRole`; a `TLCRole` href or text label does not prove that identity. | Approve the question containment/answer model and role reconciliation. Do not mint a person, office, or role from labels. |
| Speech participation | Ontology comments call `eli-dl:had_participation` canonical on Speech, but ELI-DL declares Activity domain and Speech is not an Activity; using the term entails an extra Activity type. | Resolve the domain/typing inconsistency or approve an alternative participation link. `:speaker` is only a resolved-Member shortcut and is not a witness mapping. |
| `writtenAnswer` | Audited writtenAnswer contains both a question and a response speech. There is no wrapper class or question-to-answer relation; treating the wrapper as a question or flattening it into an answer link is unsupported. | Review the wrapper semantics after representative written-answer coverage. Current rows type child nodes only and do not link the response through the wrapper. |
| `:refersToEvent` and legislative target | Its comment says `:BillEvent` or `eli:LegalResource` and it has no executable range; current Bill mappings identify concrete lifecycle events as `eli-dl:LegislativeActivity`. | Reconcile the target with the Bill-owned event mapping, resolution/IRI contract, and required legislative-section typing before emitting the source link. |
| `:refersToProposal` | Its comment limits targets to DebateSection or BillEvent, but audited `voting/@refersTo` can identify a Summary eId. | Decide whether to widen/replace the semantic model or preserve only source evidence; no automatic coercion from Summary to another resource. |
| Seanad outcome `#declared` | Current local outcome individuals are only `:DeclaredCarried` and `:DeclaredLost`; `#declared` is not equivalent to either. | Review source semantics and an appropriate target before mapping. Do not infer carried/lost from narrative text. |
| Committee `rollCall` | The audited construct differs from the Dáil division/ta-nil-staon structure and is not represented by a reviewed source mapping. | Audit committee rollCall shape and ownership before mapping to Division or member-vote terms. |
| Unresolved-reference evidence | Phase 7 requires auditable unresolved references, but debates.owl declares no evidence property/vocabulary. | Approve the RDF/non-RDF evidence representation and retention contract. Until then, preserve raw AKN and emit a review report; do not invent a predicate. |
| Full Manifestation / transcript content | Manifestation modelling is deferred; spoken/written prose is outside the authoritative Debates RDF boundary. | No decision needed to omit transcript text; preserve source bytes separately. Never emit text from speech, question, written answer, summary, heading, `from`, or paragraph nodes. |

The vote outcome/count rows do not remove the `#declared` or proposal-target
gaps. An outcome/count joins only where one analysis voting element's
`@href` resolves to exactly one summary inside exactly one body division. The
`@refersTo` target is handled separately. On a missing, invalid, or ambiguous
join, preserve the source but emit no vote outcome/count link. In particular,
do not treat absent counts as zero.

## Representative fixtures and Tranche 2 golden contract

Existing immutable examples:

* `data/debates_examples/dail_2015-07-02.akn.xml` — Dáil questions, nested
  sections, speeches/summaries, divisions, and older analysis counts.
* `data/debates_examples/dail_2026-02-26.akn.xml` — current Dáil structure,
  recorded times, division counts/outcomes, individual votes and Staon; its
  FRBR work date is 2026-02-25, irrespective of the filename, and its expression
  URI/language fields differ (`mul@` path versus `eng` metadata).

Additional byte-preserved fixtures now present under `data/debates_examples/`
(hashes, retrieval URLs and coverage are in
[`debates-source-audit.md`](debates-source-audit.md)):

* `data/debates_examples/seanad_2015-07-02.akn.xml` — Seanad outcome containing
  `#declared`; retain as a negative/blocked mapping case until reviewed.
* `data/debates_examples/committee_public_accounts_2026-09-24.akn.xml` — committee Speech
  (including witness/non-Member participation) and `rollCall` shape.
* `data/debates_examples/dail_written_answers_2015-07-02.akn.xml` — a writtenAnswer
  wrapper with both question and response speech.

These are Tranche 2 coverage targets, not claims that the Phase 7
volume/resource gate has been measured. Do not alter source fixtures to make
a mapping pass.

After the URI, graph, and blocked semantic decisions are approved, Tranche 2
goldens must be deterministic RDF dataset outputs for the exact immutable AKN
bytes, mapping, and ontology version. They must assert all and only supported
statements in the Debates-owned graph(s), including the approved graph IRI and
stable resource IRIs. Until the identity decisions are final, do not fabricate
concrete golden IRIs or a graph naming convention. Golden checks should prove:

1. AKN FRBRWork and FRBRExpression identities/resources, Work date/type,
   section names, direct nested-section structure, Speech/Summary/Question/
   Division typing, and the active direct containment links above.
2. Member links only for successfully resolved existing Member resources;
   no Member/House/HouseTerm/committee/Bill descriptions are copied into a
   Debates graph.
3. Division groups and individual Member votes from the body tree, plus
   outcome/count values only for the unique `voting/@href` result-summary join;
   `#declared`, Summary-valued `voting/@refersTo`, missing counts, empty person
   refs, and unresolved targets do not create guessed triples.
4. Repeated transformation of the same source, ontology, and mapping produces
   the same complete dataset. Tests must not use document position as identity.
5. No transcript/prose text appears as an RDF literal; allowed source literals
   are the reviewed structural/semantic values (date, debate type, section
   name, timestamp, integer counts) only. Raw AKN remains outside RDF and is
   the replay source.
6. No source ordinal, host-house link, question containment/recipient, speaker
   participation, expression relation/language, event/proposal link, unresolved
   evidence predicate, or other future-work row appears before its decision is
   approved.

This tranche has no transformer and produces no golden RDF fixture. Mapping
integrity validates active term resolution only; it cannot certify any of the
conditions above.
