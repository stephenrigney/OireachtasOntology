# Query Service — Minimum query-plan redesign requirements

**Basis:** The reviewer-approved questions Q01–Q37, Q24A and T01 in [`query-service-questions-approved.md`](query-service-questions-approved.md) (39 cases). These are **desired answer behaviours**, not claims of present data or query support. Source implementation notes were checked against the current `poc/specs/query-plan-contract.json`, `poc/nlq/plan_contract.py`, `poc/nlq/plan_sparql.py`, and `poc/specs/query-schema-contract.json`.

**Objective:** Replace the present limited intermediate plan *in place* with the smallest typed, composable semantic plan able to represent realistic parliamentary questions. Keep deterministic, reviewed-mapping SPARQL generation. Do not maintain parallel v1/v2 runtime paths.

## Required plan capabilities

### 1. Explicit typed referents and reusable roles

Identify a particular Member, Bill, committee, House term or office; separately represent independently bound/unbound variables of the *same* type. The same referent ID used in two relations means the same identity; two different referent IDs do not accidentally collapse just because their type matches. This is essential for multi-person joins and extension to questions such as “Who represented the same constituency as Bertie Ahern?”.

**Direct review cases:** Q06, Q09, Q13–Q14, Q22–Q23, Q35; extensibility stress case: same-entity-type self-joins. Current contract's type-only participants are one shared role per type.

### 2. Composable reviewed semantic relationships

Express joins of membership, representation, party affiliation, office holding, committee membership, Bill process, sponsors and activities as connected relationships. Apply approved semantic facts and graph ownership mappings. Do not let the model emit arbitrary SPARQL or invent predicates. Where the RDF does not express a needed relationship, preserve a plan-level requirement but report it unexecutable from the present dataset.

**Cases:** Q06–Q14, Q17, Q21–Q23, Q25–Q27, Q30, Q35–Q36.

### 3. Distinguish enduring identity, term occurrence, status and historical episode

A natural mention of “Fianna Fáil” can denote the enduring party; a linked `ParliamentaryParty` resource belongs to a House term; a dated person's membership is an episode. A constituency name can denote a named series, whereas a term reference can select an occurrence. “Independent” is a status, not a political-party identity. Distinguish Seanad vocational panels, nomination by the Taoiseach, and university/higher-education constituencies. Do not merge resources by label alone.

**Cases:** Q06–Q11, Q13, Q17. **Separate data/model dependency:** accepted local enduring-party identities and constituency-series links have not been established by the approved question set itself; implementing them is distinct from rewriting the plan.

### 4. Reference time and temporal operators

Preserve an explicit, injectable `as_of` reference date for “now”, “current”, “previous”, “last”, and relative House terms. Support point-in-time membership, interval overlap, first and most recent events, ordering, and dates on relationship episodes. Q03 requires a *cumulative actual service duration* computed from the union of dated intervals, preserving gaps; this may be deterministic post-query computation rather than generalised SPARQL arithmetic.

**Cases:** Q02–Q03, Q05–Q09, Q11–Q12, Q15, Q19, Q21, Q25–Q27, Q30, Q35. Missing/open ends must not silently mean continuous service forever.

### 5. Filters, controlled status logic and aggregation

Support equality/inequality on semantic values, controlled sets (e.g. **all** non-enacted statuses), House/term constraints, count distinct *entities*, grouping, and simple extrema (`latest`). Keep the meaning of “not enacted” distinct from “current” and of **seat complement** distinct from counting TD records. Never equate absence of evidence with evidence of absence.

**Cases:** Q04, Q13, Q15–Q16, Q19–Q20, Q29–Q30, Q35, T01.

### 6. Explicit answer identity, projection and presentation

Specify the answer role independently of its type; project multiple requested attributes (name/title, dates, role, status, official link), distinguish Boolean from list/count, order results and deduplicate by enduring entity where appropriate. Show one Bill per distinct Bill IRI and English short titles by default. For Q06, show each distinct enduring political party once, with membership episodes as *supporting* detail—not one answer per House-term collection.

**Cases:** Q03, Q06, Q09, Q15, Q18–Q23, Q24A, Q28–Q30, Q32–Q35.

### 7. Grounded resolution and actionable answer states

Support aliases, title abbreviations, context, qualified name matches, and a *set* of candidates when ambiguity is genuinely unresolved. Keep `not found`, `unsupported relation`, `source data missing/problem`, and `insufficient coverage for latest/current` distinguishable. User-facing responses must explain the issue without ETL jargon. No guessed identities, invented chair/office-holder, inferred votes, or invented transcript content.

**Cases:** Q01, Q08, Q10, Q12, Q14, Q18, Q24, Q28, Q30–Q34, Q36–Q37.

## What is **not** solved by a new query plan

- **Local identity work:** Enduring political parties and named constituency series need trustworthy relationships to existing term-scoped identities. Do not equate labels or require live Wikidata to answer ordinary local questions (Q06, Q09).
- **Absent ontology/source facts:** Authoritative seat totals (Q16), committee chairs and recognised groups (Q12, Q17), and complete current offices (Q26) may require additional reviewed data.
- **Data coverage:** A small debate fixture cannot establish “last PAC hearing” across the corpus (Q30). Missing/affected Bill records remain separately diagnosable (Q24). No corpus scan is a prerequisite for proving the planner/compiler logic.
- **New retrieval capabilities:** Transcript text and voting data (Q36–Q37) are not made available by changing plan syntax.
- **Procedural inference:** Ordinary next steps for a Bill are a later rule-based enhancement (Q21), not a prerequisite for this redesign.
- **Official fact validation:** Approved example names, titles, dates and officeholders must be tested with pinned source evidence, not assumed to be correct simply because the questions are approved.

## Illustrative plan shapes (semantic, not prescribed JSON)

**Q06 — Parties Stephen Donnelly belonged to**

- Referents: `donnelly: Member (resolved)`, `episode: dated party membership`, `collection: term-scoped ParliamentaryParty`, `party: enduring PoliticalParty (answer)`.
- Relationships: Donnelly → episode → collection → party.
- Answer: distinct `party` identities with names; aggregate/display supported episode dates without losing gaps. This requires a real local `collection → enduring party` relation; it cannot be fabricated by the planner.

**Q09 — TDs in Dublin South-Central in the last Dáil**

- Referents: `target_term: previous Dáil term relative to as_of`, `constituency_occurrence: term-scoped constituency`, `member: unbound Member (answer)`.
- Relationships: term identifies constituency occurrence; Member's OireachtasMembership links to that term and constituency.
- Answer: distinct Members; include replacements, optional party/date details.

**Q35 — Minister for Finance from January 2021 to December 2022**

- Referents: `office: resolved enduring NamedOffice`, `holding: dated OfficeHolding`, `member: unbound Member (answer)`.
- Constraints: each holding overlaps the supplied inclusive window.
- Answer: all distinct office-holders plus actual holding dates; do not require uninterrupted tenure throughout the range.

**Q23 — Bills sponsored by Malcolm Byrne**

- Referents: `member: resolved`, `participation`, `bill: unbound Bill (answer)`.
- Relationships: sponsorship joins Bill process through reviewed graph mapping; capture primary-sponsor evidence when it exists.
- Answer: one Bill per identity, English title, optional sponsor role and official link.

## Delivery sequence and stopping rules

1. **Design checkpoint (OpenCode; short):** Examine the current contracts/compiler against the above examples; propose a minimal replacement plan shape, deterministic compilation approach and concrete failures that cannot be solved at plan level. No additional user-question review, corpus scan or large architecture report.
2. **First running slice (OpenCode; bounded):** Implement a joined, context-scoped, distinct-entity query (prefer Q09 with fixed as-of and a tiny fixture), including readable results through the current UI. Focused tests only. Integrate if the agreed slice works.
3. **Second slice:** Demonstrate enduring/term-scoped identity composition with Q06 using a small reviewed local party example, once the minimal identity association is settled. Then add temporal overlap (Q35) and projection/role detail (Q23) based on observed failures.

**Exit for architecture:** The proposed plan can express Q06, Q09, Q23 and Q35 *without special-case syntax per question*, even where current RDF lacks supporting evidence. It can also identify plan-vs-data limitations of Q16, Q30 and Q36–Q37. No dual-runtime compatibility, production ETL, broad benchmarks or recurring full-suite runs.