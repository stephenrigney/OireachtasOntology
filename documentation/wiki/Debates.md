# Debates and the Official Report

The Debates ontology maps supported structure from Oireachtas Akoma Ntoso
(AKN) records into resources that can connect to Members, HouseTerms,
Committees and legislative resources. A Debate is modelled as a documentary
Work with language-specific Expressions; it is not automatically a Bill or a
legislative activity.

## Work, Expression and sitting

```text
AKN FRBRWork → debates:DebateRecord
                  ├─ debates:hasExpression → debates:DebateExpression
                  │                            └─ expressionHasSection → top-level sections
                  ├─ recordOfBody → resolved House or Committee
                  ├─ recordOfHouseTerm → resolved numbered HouseTerm
                  └─ when a real non-written sitting is identified:
                       debates:DebateSitting ── producedRecord → DebateRecord
```

Work and Expression identities come from the exact AKN `FRBRuri/@value`
paths under the approved UTF-8 percent-encoding rule. They are not guessed
from labels or made from the path of a partial XML fragment. Known multiple
Expressions for one Work fail closed rather than publishing an incomplete
Work. A `writtens` Work is a record but is not by itself evidence that a
DebateSitting occurred. For exact identity and graph rules see the
[Debates identity contract](../debates-identity-contract.md).

A DebateSitting is typed as `eli-dl:Activity`, not as a
`eli-dl:LegislativeActivity`: one sitting may include questions, statements,
motions and legislative business. A section is additionally typed as a
legislative activity only when a supported event reference establishes that
relationship.

## Structured Debate content

`DebateRecord`/`DebateExpression` sections preserve document structure and
source order. Supported addressable children include:

| AKN element | Ontology resource / relation |
|---|---|
| `debateSection` | `debates:DebateSection`, with nested sections through `hasSubSection` |
| `speech` | `debates:Speech`, contained in a section; speaker may link to a resolved Member, with participation metadata represented separately |
| `summary` | `debates:Summary`, contained in a section |
| `question` | `debates:ParliamentaryQuestion`, contained in a section and linked to its asker when resolved |
| `debateSection[@name='division']` | `debates:Division` (`eli-dl:Vote`), with Tá/Níl/Staon counts and resolved voter links where supplied |

The AKN XML remains authoritative evidence. Transcript prose is not copied
into RDF. Source order is represented with lightweight ordinal data; XML is
still the complete record for document text and layout. Question recipient to
office/role links, a one-to-one written-answer relation, and unsupported
cross-resource references are not invented. Unresolved references are
reported/preserved as source outcomes, not filled with placeholder semantic
entities.

## Current implementation and limits

The bounded source, transform, validation, replay and opt-in supplied-batch
publication tranches are implemented. The approved first production scope is
Dáil, Seanad and Committee Works dated 2011-01-01 onward, excluding written
answers. **This is not yet production ingestion:** readiness remains open for
safe enumeration, exact in-scope quarantine inventory, approved operational
limits and staged operational acceptance. Earlier debates, written answers,
topic extraction, committee roll-call attendance RDF, and unreviewed Bill or
recipient crosswalks remain deferred.

The current canonical status/design record is
[Phase 7 Debates](../phase-7-debates.md); see also the
[production benchmark](../debates-production-benchmark.md),
[semantic review](../debates-semantic-review.md), and
[current system overview](../current-state.md#data-coverage-and-limits).
This page supersedes older wiki statements describing intended XML patterns
as if they were current mapped behavior.

For an approachable guide to sections, speech, questions and divisions, see
[Debate structure](Debates-body.md). The ontology declarations are in
[`ontology/debates.owl.ttl`](../../ontology/debates.owl.ttl), and field status
is in [`mappings/debates_mapping.csv`](../../mappings/debates_mapping.csv).
