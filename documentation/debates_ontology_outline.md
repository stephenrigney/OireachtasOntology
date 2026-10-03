# Debates Ontology — High-Level Outline

**Status: approved semantic/source contract; the Debates ontology/mapping
additions and static contract checks are verified. The Tranche 1 exit awaits
orchestrator confirmation; no runtime Debates transformer is implemented.**
The exact approved decisions are in
[`debates-semantic-review.md`](debates-semantic-review.md) and
[`debates-identity-contract.md`](debates-identity-contract.md). This outline
summarizes the approved vocabulary; static ontology/mapping verification does
not prove runtime transformation or actual RDF emission. Where historical
baseline material differs, the approved review governs.

## Design Anchors

- **FRBR document layer** — `:DebateRecord` is a `foaf:Document`; legislative connection is optional, not structural
- **Sitting as activity** maps to `eli-dl:Activity` — kept broad because a sitting may mix legislation with questions, statements, etc.
- **Legislative section** — a `:DebateSection` is *additionally* typed `eli-dl:LegislativeActivity` only when its source reference resolves to an existing legislative resource; this is the correct granularity because ELI-DL scopes that class to a bounded legislative activity, which a section matches better than a whole mixed sitting
- **Division / vote** maps to `eli-dl:Vote` + `eli-dl:Decision`
- **Speaker participation** uses the approved `:hasSpeechParticipation` relation
  to `eli-dl:Participation`; it is not a subproperty of
  `eli-dl:had_participation` and does not infer that Speech is an Activity.
- The ontology imports `events.owl`, `agents.owl`, `members.owl` and ELI-DL;
  `members.owl` supplies the existing `members:NamedOffice` target for the
  approved conditional question-recipient relation.

---

## Source files examined

| File | Lines | Notes |
|---|---|---|
| `data/debates/dail_2015-07-02.akn.xml` | 8355 | Report Stage (Resumed) with amendments and divisions; questions |
| `data/debates/dail_2026-02-26.akn.xml` | 6989 | Topical issues, statements, motions, divisions with staon (abstain) |

---

## Classes

| Class | Superclass(es) | Maps to AKN |
|---|---|---|
| `:DebateRecord` | `foaf:Document` | `FRBRWork` — the debate as a distinct intellectual work for a house/date |
| `:DebateExpression` | *(bare OWL class)* | `FRBRExpression` — language-specific version (eng / gle / mul); `rdfs:comment` notes FRBR correspondence; no superclass added to avoid FRBR import dependency |
| `:DebateSitting` | `eli-dl:Activity` | The actual non-written sitting activity that produces a `:DebateRecord`; eligible records use `eli-dl:activity_date`. A `writtens` Work gets a `:DebateRecord` and date but no `:DebateSitting`. Always `eli-dl:Activity`; never typed `eli-dl:LegislativeActivity` because a sitting may be mixed |
| `:DebateSection` | — | `debateSection` — a topic-bounded section; nests recursively; actual `@name` values in use: `debate`, `question`, `questions`, `amendment`, `division`, `ta`, `nil`, `staon`, `prelude`, `topical`, `statement`, `motion`. Sections with a resolved legislative source reference may additionally be typed `eli-dl:LegislativeActivity` (see Typing Conventions below) |
| `:Speech` | — | AKN `speech` used for oral or written-answer contributions; it is not thereby an ELI-DL Activity |
| `:Summary` | — | `summary` — narrative / procedural text not attributed to a speaker |
| `:ParliamentaryQuestion` | — | `question` — a parliamentary question (oral or written) |
| `:Division` | `eli-dl:Vote` | `debateSection[@name='division']` — a division in the chamber; three sub-sections: `ta`, `nil`, `staon` |

---

## Properties

### On `:DebateRecord`

| Property | Range | Note |
|---|---|---|
| `:recordOfHouseTerm` | `:HouseTerm` | Approved link only when `FRBRauthor/@href` resolves to an existing numbered term; derive its enduring House from `:termOf`. Do not use `:inHouse` on DebateRecord. |
| `:recordOfBody` | `org:Organization` | Approved House-or-Committee host link only when source identity resolves to an existing owner; do not type a Committee as `:House`. |
| `:debateDate` | `xsd:dateTime` | Work date from AKN `FRBRWork/FRBRdate` (including written-answer records); `xsd:dateTime` used for OWL 2 DL compatibility (HermiT does not support `xsd:date`) |
| `:debateType` | `xsd:string` | AKN `FRBRname/@value` sub-type where present (e.g. `"debate"`, `"writtens"`) |
| `:hasExpression` | `:DebateExpression` | Approved Work-to-Expression link |
| `:hasSection` | `:DebateSection` | Work-level convenience link to top-level sections; immediate source-order scope is the Expression |

### On `:DebateExpression`

| Property | Range | Note |
|---|---|---|
| `:expressionHasSection` | `:DebateSection` | Approved link to top-level sections in this Expression |
| `:expressionLanguageCode` | `xsd:string` | Exact `FRBRlanguage/@language` lexical code; never infer language from a URI suffix |

### On `:DebateSitting`

| Property | Range | Note |
|---|---|---|
| `eli-dl:activity_date` | `xsd:date` | ELI-DL activity date |
| `:relatedProcess` | `eli-dl:LegislativeProcess` | 0..* — convenience link; present when the sitting contains at least one legislative section |
| `eli-dl:had_participation` | `eli-dl:Participation` | Chair / presiding officer participation |
| `:producedRecord` | `:DebateRecord` | Links the activity to its documentary output |

### On `:DebateSection`

| Property | Range | Note |
|---|---|---|
| `:sectionName` | `xsd:string` | AKN `@name` value; see class table above for values observed in the wild |
| `:refersToEvent` | `:BillEvent` or `eli:LegalResource` | Conditional on exact resolution to an existing Bill-owned event/Work IRI; unresolved or nonmatching fragments produce no link. Add `eli-dl:LegislativeActivity` only for a resolved legislative source reference. |
| `eli-dl:occured_at_stage` | `eli-dl:ProcessStage` | Present when additionally typed `eli-dl:LegislativeActivity`; records the bill stage (e.g. Second Stage, Report Stage) |
| `eli-dl:forms_part_of` | `eli-dl:LegislativeProcess` | ELI-DL standard link from activity to process; use on legislative sections in preference to a custom property |
| `:hasSubSection` | `:DebateSection` | Nested sections; used for amendment sub-sections, division ta/nil/staon, question threads |
| `:hasSpeech` | `:Speech` | |
| `:hasSummary` | `:Summary` | |
| `:hasDivision` | `:Division` | |
| `:hasQuestion` | `:ParliamentaryQuestion` | Approved immediate containing section-to-question relation; no unsupported one-to-one written answer link |
| `:sourceOrdinal` | `xsd:integer` | Approved positive, consecutive 1-based ordinal among immediate addressable siblings across kinds, including sections and contributions; not an IRI ingredient |

### On `:Speech`

| Property | Range | Note |
|---|---|---|
| `:hasSpeechParticipation` | `eli-dl:Participation` | Approved local relation, not a subproperty of `eli-dl:had_participation`; emit only when person and/or role resolves |
| `:speaker` | `:Member` | Resolved-Member shortcut only; do not infer witness identity from context or `#` |
| `:recordedTime` | `xsd:dateTime` | Timestamp from AKN `from/recordedTime/@time`; accurate to ~5–10 min |

### On `:ParliamentaryQuestion`

| Property | Range | Note |
|---|---|---|
| `:askedBy` | `:Member` | `question/@by` → `TLCPerson`; emit only for an existing resolved Member |
| `:directedTo` | `eli-dl:ParticipationRole` | Emit only when `question/@to` resolves to an existing ParticipationRole; a `TLCRole` reference or label does not establish this identity |
| `:directedToOffice` | `members:NamedOffice` | Conditional on unique, reviewable source-role-to-existing-office resolution; do not map by label equality |

### On `:Division`

| Property | Range | Note |
|---|---|---|
| `:taCount` | `xsd:integer` | Votes in favour (`#ta`) |
| `:nilCount` | `xsd:integer` | Votes against (`#nil`) |
| `:staonCount` | `xsd:integer` | Aggregate abstentions (`#staon`) whenever supplied; a count is not an individual voter list. Current official 2015 Dáil XML has an aggregate without a Staon member subsection. |
| `:divisionOutcome` | `eli-dl:DecisionOutcome` | Emit only known `#carried`/`#lost` after the unique `@href` join; `#declared` is audited but not emitted as an outcome |
| `:refersToProposal` | `:DebateSection` or `:BillEvent` | Do not map `voting/@refersTo` under the approved initial scope; Summary targets are not proposals |
| `:votedFor` | `:Member` | Members voting Tá; from `debateSection[@name='ta']/p/person` |
| `:votedAgainst` | `:Member` | Members voting Níl; from `debateSection[@name='nil']/p/person` |
| `:abstained` | `:Member` | Members recorded Staon; from `debateSection[@name='staon']/p/person` |

---

## Named Individuals

### Decision outcomes (typed `eli-dl:DecisionOutcome`)

| Individual | AKN `TLCConcept` | IRI in 2026 data |
|---|---|---|
| `:DeclaredCarried` | `#carried` | `oireachtas#DeclaredCarried` |
| `:DeclaredLost` | `#lost` | `oireachtas#DeclaredLost` |

### Vote categories (typed `skos:Concept`; used in `count/@refersTo`)

| Individual | AKN `TLCConcept` | Note |
|---|---|---|
| `:TáVote` | `#ta` | Votes in favour |
| `:NílVote` | `#nil` | Votes against |
| `:StaonVote` | `#staon` | Abstentions |

### Participation roles (typed `eli-dl:ParticipationRole`)

| Individual | Note |
|---|---|
| `:ChairRole` | Ceann Comhairle / Cathaoirleach acting as presiding officer; from `TLCRole` `ceann_comhairle` / `cathaoirleach` |
| `:WitnessRole` | Existing role individual; do not infer/assign it from committee context, labels or `@by="#"` without reviewed resolution |

---

## Typing Conventions

| Condition | Additional type on `:DebateSection` instance |
|---|---|
| `debateSection/@refersTo` resolves exactly to an existing legislative source resource | `eli-dl:LegislativeActivity`; unresolved or nonmatching references do not trigger this type |
| No `@refersTo` present (questions, statements, topical, motion, prelude, etc.) | none — remains plain `:DebateSection` |

When a `:DebateSection` is typed `eli-dl:LegislativeActivity`, the following ELI-DL properties become applicable on that instance:
- `eli-dl:occured_at_stage` → the bill stage (e.g. Second Stage)
- `eli-dl:forms_part_of` → the `eli-dl:LegislativeProcess` for the bill
- `eli-dl:had_participation` → mover / rapporteur roles at that stage

---

## Non-legislative Debate Modelling

| Debate type | `:DebateSitting` type | Section-level `eli-dl:LegislativeActivity`? | `:relatedProcess` on sitting |
|---|---|---|---|
| Question Time, Statements, Topical Debates, Motions | `eli-dl:Activity` only | No | absent |
| Purely legislative sitting (e.g. Committee Stage only) | `eli-dl:Activity` only | Yes — on the debate section(s) | present |
| Mixed sitting (common in Dáil) | `eli-dl:Activity` only | Yes — on legislative sections only; non-legislative sections untyped | present |

---

## Open Questions

1. ~~**`DebateExpression` superclass**~~ — resolved: bare OWL class with `rdfs:comment` noting FRBR correspondence. Superclass can be added if FRBR is ever imported for another reason.
2. **`answer` element** — not observed in the reviewed fixtures, but described in the schema documentation. Hold for future data.
3. **`rollCall`** — now evidenced in a committee fixture. Attendance remains source-only in the initial RDF scope; do not map it as a Division, vote, speech or participation. A future attendance RDF model requires separate review.

---

## Deferred / Out of Scope (stub)

- Full FRBR Manifestation layer (XML file IRIs)
- Inline `entity/@refersTo` markup for amendments
- Image and table content
- Bilingual heading deduplication
