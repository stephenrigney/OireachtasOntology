# Query Service — Intermediate Query Plan Redesign

## Decision

Replace the Phase 2 plan in place with a small typed graph-shaped semantic
plan. A plan describes referents, reviewed relations connecting them,
constraints on those relations, and the requested answer. It is neither a
general query language nor executable SPARQL. The interpreter may use an LLM
to draft this closed structure, but deterministic application code resolves
entities, validates all semantics, and compiles only reviewed mappings to
SPARQL. No compatibility runtime or LLM-generated SPARQL is retained.

## Proposed plan model

Illustrative JSON shape (IDs are local references, not RDF variables):

```json
{
  "version": 2,
  "asOf": "2026-10-25",
  "referents": {
    "member": {"type": "Member", "mention": "Stephen Donnelly",
                "resolution": "resolved"},
    "episode": {"type": "PartyMembershipEpisode"},
    "collection": {"type": "ParliamentaryMemberCollection"},
    "party": {"type": "PoliticalParty", "answer": true}
  },
  "relations": [
    {"id": "r1", "fact": "member_party_membership",
     "from": "member", "to": "episode"},
    {"id": "r2", "fact": "episode_in_collection",
     "from": "episode", "to": "collection"},
    {"id": "r3", "fact": "collection_represents_party",
     "from": "collection", "to": "party"}
  ],
  "constraints": [],
  "answer": {"kind": "entities", "referent": "party",
    "distinctBy": "identity", "display": ["label"], "order": ["label"],
    "details": [{"relation": "r1", "project": ["start", "end"]}]}
}
```

Semantics:

* Every referent has an independent ID and controlled entity type. Reusing an
  ID means same identity; different IDs remain independent even with the same
  type. A relation is a typed edge from one referent to another. Multiple
  edges compose as joins; only registered facts, direction, type signatures,
  ownership and query mappings can compile.
* A mention is unresolved input, not an RDF binding. Resolution carries
  aliases, context and evidence and can return `resolved`, `ambiguous` with a
  candidate set, or `not_found`. Candidate sets are never silently reduced to
  a singular identity. `asOf` is explicit and injectable for relative terms
  and “current/last/previous”; all date-window operators state inclusive or
  exclusive boundaries.
* Constraints attach to a relation or referent: typed equality/set filters,
  `on`, `before`, `after`, `overlaps`, `duringTerm` (including
  `previousTerm(house, asOf)`), and existence. Open interval ends are
  explicit, not assumed to continue indefinitely. Relative term resolution
  is deterministic using reviewed HouseTerm date/order metadata.
* Answer kinds are `boolean`, `entities`, `values`, `count`, and `grouped`.
  They explicitly name their source referent/relation, distinct identity
  policy, projected display fields, optional relationship details, grouping
  and ordering. Aggregations include count-distinct and simple extrema; union
  of dated intervals for cumulative service is a named deterministic
  post-query operation, not arbitrary arithmetic. English titles are the
  default display for Bills. Distinct answer identity is separate from
  repeated evidence/detail rows.
* Plan execution has distinct outcomes: `unsupported_capability` (no reviewed
  semantic/compiler support), `source_data_unavailable` (fact absent,
  quarantined, or incomplete coverage), `not_found`, and `ambiguous` (with
  candidates). Missing evidence never proves a negative. Validation reports
  these states rather than weakening or dropping constraints.

The semantic vocabulary is small and repository-controlled, not user/model
extensible. The JSON wire schema is closed; the version-2 contract supersedes
the existing version without dual runtime support.

## Reusable plan demonstrations

These use the same referent/relation/constraint/answer constructs above.
`{...}` abbreviates ordinary metadata; relation fact names are proposed
controlled semantic IDs, not claims that the present RDF already has them.

### Q06 — Stephen Donnelly's distinct enduring parties

```yaml
asOf: 2026-10-25
referents: {member: Member(mention: "Stephen Donnelly"),
  episode: PartyMembershipEpisode, collection: ParliamentaryMemberCollection,
  party: PoliticalParty}
relations: [member --party_membership--> episode,
  episode --in_term_collection--> collection,
  collection --identity_of--> party]
answer: entities(party, distinctBy: identity, display: [label],
  details: [episode.start, episode.end], preserveGaps: true)
```

The answer groups multiple term-scoped collections under one enduring party;
Independent status is not a PoliticalParty. It requires a reviewed local
`collection -> party` identity association; matching labels or Wikidata are
not substitutes. Evidence dates remain episode-scoped, preserving breaks.

### Q09 — TDs for Dublin South-Central in the previous Dáil

```yaml
asOf: 2026-10-25  # frozen in acceptance fixture
referents: {term: DailTerm, constituency: DailConstituencySeries,
  occurrence: DailConstituency, member: Member, service: DailMembership}
relations: [term --has_constituency_occurrence--> occurrence,
  occurrence --member_of_series--> constituency,
  member --has_membership--> service,
  service --in_term--> term,
  service --represents--> occurrence]
constraints: [term = previousTerm(Dail, asOf),
  constituency = resolve("Dublin South-Central")]
answer: entities(member, distinctBy: identity, display: [name],
  optionalDetails: [party, service.start, service.end], order: [name])
```

Members are selected through membership/representation in the resolved
previous term and named occurrence; replacements are included and each Member
appears once. The query does not assume term 33.

### Q23 — Bills sponsored by Malcolm Byrne

```yaml
referents: {member: Member(mention: "Malcolm Byrne"),
  participation: BillParticipation, bill: Bill}
relations: [bill --has_sponsor_participation--> participation,
  participation --participant--> member]
constraints: [participation.role in [primary_sponsor, supporting_sponsor]]
answer: entities(bill, distinctBy: identity,
  display: [englishTitle, billNumber, year, officialLink],
  details: [participation.role, participation.primaryEvidence], order: [year, billNumber])
```

Unknown primary status stays unknown; this plan does not infer primary from
ordering or absence. Source-backed sponsorship joins are reusable for Q22.

### Q35 — Finance Ministers overlapping a supplied interval

```yaml
referents: {office: NamedOffice(mention: "Minister for Finance"),
  holding: OfficeHolding, member: Member}
relations: [member --has_holding--> holding, holding --of_office--> office]
constraints: [holding.interval overlaps inclusive("2021-01-01", "2022-12-31")]
answer: entities(member, distinctBy: identity, display: [name],
  details: [holding.start, holding.end], order: [holding.start])
```

Overlap returns every holder whose tenure intersects any part of the window,
not just a person continuously in office throughout it. The holding records
remain separate evidence if one person has multiple episodes.

## Pipeline responsibilities and reuse

* **Planner:** interpret question into typed referents, controlled relation
  IDs, temporal semantics and answer projection only. It cannot invent facts,
  predicates, graph names, SPARQL or identities. Reuse the structured
  Responses planner's strict-schema/draft-then-validate pattern and prompt
  grounding, replacing its version-1 vocabulary and single-role assumptions.
* **Entity resolver:** resolve each mention independently using aliases,
  type, question context and local evidence. Reuse exact-label lookups,
  contextual Member disambiguation and safety behavior in
  `member_resolution.py`; generalize to other reviewed types and return true
  candidate sets rather than arbitrary picks.
* **Validator:** check referent IDs/types, relation signatures, connectedness
  of answer paths, allowed operators and date semantics, set-valued resolution,
  answer projection, and executable mapping/graph ownership. Distinguish plan
  rejection from unsupported relation and data/coverage diagnosis. Reuse
  closed JSON validation, contract loading, fail-closed compilation checks,
  query-schema graph-family/pattern allowlists and `safety.py` read-only
  SPARQL validation.
* **Compiler:** deterministically lower validated relation paths to
  parameterized patterns using reviewed query-schema mappings and owned named
  graphs. Generate safe SELECT/ASK forms, stable joins, date overlap and
  distinct/group/order clauses. Never derive predicates or graphs from model
  text. The current explicit mapping tables and graph-fragment compiler in
  `plan_sparql.py` are a useful base, but its fact-specific dispatch must
  compile arbitrary connected paths from the approved vocabulary.
* **Answer renderer:** format answer kind, display attributes and evidence
  details; deduplicate by requested identity; render dates, roles and links;
  explain ambiguity, unsupported capabilities, missing source facts and
  incomplete “latest/current” coverage distinctly. Reuse result/presentation
  helpers where their contract fits, but do not expose raw IRIs as normal
  display values.

Reusable contract assets: `query-schema-contract.json` namespaces, graph
families, owners, emitted RDF patterns, queryable predicates and labels;
`query-plan-contract.json`'s controlled vocabulary concepts and
`plan_sparql.py` reviewed mapping discipline; `structured_planner.py` strict
JSON-generation/validation boundary; `member_resolution.py` exact/contextual
resolution; `safety.py` read-only query checks. Existing Phase 1 direct
NL-to-SPARQL path is not the target execution path.

## Dependencies distinct from plan work

* Q06 needs trusted local enduring PoliticalParty identities and an explicit
  association from term-scoped party collections to them. This is identity
  data/modeling, not a plan feature; never merge by label or rely on
  Wikidata.
* Q09 needs a trustworthy cross-term constituency series-to-occurrence link
  where the source uses term-scoped constituency resources, plus complete
  member/representation records and date/order data for `previousTerm`.
* Q23 needs the Bill sponsorship participation mapping plus readable English
  title/number/link. Primary/supporting requires source evidence such as
  `isPrimarySponsor` to be exposed through a reviewed query mapping; null is
  unknown.
* Q35 needs accepted OfficeHolding records with dated/open-ended intervals
  and complete enough coverage for the requested period. The plan cannot
  supply missing office data.
* More generally, Q16 seat complements, Q12 committee chairs, Q17 recognised
  groups, Q36 voting and Q37 transcript content require absent or additional
  reviewed facts/retrieval. Q30 “latest” needs sufficient coverage and
  reviewed PAC alias/topic evidence. A design can classify these as
  unsupported or unavailable, not create answers.

These are data/ontology/mapping dependencies; this document proposes no
ontology or mapping edits.

## Minimal implementation sequence

1. Replace the v1 plan contract/validator and planner draft with version 2
   typed referents, relation IDs, date/as-of and answer projection. Define a
   small mapping registry against existing query-schema pattern/ownership
   records. Do not retain a v1 runtime.
2. **First end-to-end vertical slice: Q09** with fixed `asOf`, a tiny
   source-backed fixture, term and constituency resolution, joins across
   term/membership/representation graphs, distinct Member display through
   the current UI. If constituency-series identity is not represented in
   fixture/mapping evidence, use the same bounded existing term occurrence
   route only if it semantically answers the approved question; otherwise
   stop for that concrete dependency, not a hard-coded plan workaround.
3. Exit criteria: same-type distinct referents validate independently;
   relative previous Dáil resolves from fixed as-of input; generated SPARQL
   is deterministic, read-only and uses only reviewed graph/predicate
   mappings; fixture returns all distinct representatives including
   replacements; rendered names are readable; focused tests cover wrong
   relation/type, ambiguity, absent mapping and missing data as distinct
   outcomes. No full-suite or corpus run is required.
4. Add Q06 after local enduring-party identity association is settled; then
   Q35 interval-overlap and Q23 sponsor-role projection as separate focused
   slices. Extend the same primitives rather than adding question-specific
   syntax.

## Risks and human decisions

The v2 contract is intentionally breaking and retires the current format; the
owner should confirm the versioning/deployment cutover before runtime work.
Q06 party identity and Q09 constituency-series identity are semantic data
decisions and require reviewed evidence/approval before mappings are added.
Confirm the inclusive date-window convention for natural-language month/year
ranges and the representation of open-ended intervals before implementing
temporal comparisons. Primary/supporting sponsorship depends on evidence
semantics, not merely a plan field. Do not resolve these by broadening the
compiler or inferring facts. If existing ontology/source mappings materially
contradict a demonstrated relation, pause for semantic review.
