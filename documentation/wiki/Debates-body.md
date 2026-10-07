# Debate structure

This page explains the structured RDF view of an AKN Debate body. AKN XML
contains more content than the ETL currently publishes: full text, formatting,
paragraphs, tables and committee attendance remain in the preserved source, not
in the RDF graph.

## Sections, speeches and summaries

The `DebateExpression` records its immediate top-level sections and their
source order. Nested sections use `debates:hasSubSection`; the Work may also
link to top-level sections for convenience. Each section may contain supported
resources:

```text
DebateExpression
  └─ expressionHasSection → DebateSection
       ├─ hasSubSection → DebateSection
       ├─ hasSpeech → Speech
       ├─ hasSummary → Summary
       ├─ hasQuestion → ParliamentaryQuestion
       └─ hasDivision → Division
```

`Speech` is a structural contribution, not an Activity. A resolved Member may
be linked as speaker; participation metadata is a separate Participation
resource. A `Summary` describes procedural or narrative content not directly
attributed to a speaker. Neither resource stores the transcript text in RDF.

## Questions

`ParliamentaryQuestion` represents a source question, and `askedBy` links to a
resolved Member where the AKN reference supports it. A Minister's label or
question `@to` text does not identify a historically correct office. The
recipient-role and recipient-to-`NamedOffice` mappings are deferred pending
reviewed source-role reconciliation. Nor does containment assert an exact
one-to-one question-to-answer relation.

Questions and written answers are represented as Debate content when present
in the source. This does not mean the approved initial production scope
includes written-answer Works; the current bounded load scope excludes them.
See [Debates](Debates.md#current-implementation-and-limits).

## Divisions and votes

A `Division` is an `eli-dl:Vote` represented by a division section. Where the
source supplies them, the structured model includes aggregate Tá, Níl and
Staon counts and resolved Member links for votes for, against and abstentions.
Source `#carried` and `#lost` values map to supported outcomes; `#declared` is
not silently converted into an outcome. Committee `rollCall` remains
source-only: it is not treated as a division, vote, speech or attendance RDF
model.

The source order and supported structure are documented in the
[Debates identity/status guide](Debates.md) and the
[canonical ontology/mapping](../../ontology/debates.owl.ttl) ·
[`mappings/debates_mapping.csv`](../../mappings/debates_mapping.csv).
Detailed source observations and acceptance decisions remain in the
[Debates semantic review](../debates-semantic-review.md) and
[phase record](../phase-7-debates.md).
