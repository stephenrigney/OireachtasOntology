# OireachtasOntology: conceptual guide

OireachtasOntology is a formal vocabulary for describing the institutions,
people, memberships, legislative processes and parliamentary records of the
Houses of the Oireachtas. It combines local OWL terms with established
vocabularies such as ORG, FOAF, SKOS, ELI and ELI-DL. Its Python ETL maps
selected Oireachtas source records into validated RDF; the ontology describes
the model, while source mappings and implementation determine which data is
currently represented.

This wiki is the approachable conceptual guide to that model. For the concise
whole-system summary, see [Current system overview](../current-state.md).
For the executable term inventory, see the
[ontology module reference](../../ontology/README.md) and the Turtle files in
[`ontology/`](../../ontology/).

## Conceptual map

```text
Oireachtas (enduring ParliamentaryBody individual)
├── Dáil Éireann (enduring House) ── numbered Dáil HouseTerms
└── Seanad Éireann (enduring House) ─ numbered Seanad HouseTerms

People ── dated OireachtasMembership ── House + HouseTerm
       ├── collection membership ───── ParliamentaryParty / IndependentMemberCollection
       ├── CommitteeMembership ───────── Committee (separately described organisation)
       └── OfficeHolding ─────────────── NamedOffice ── AdministrativeUnit
                    └── where qualifying: CabinetMembership ── Government

Bill / legislative process ── stages, events, versions and documents
Debate Work ── Expression(s) ── ordered sections ── speeches / questions / divisions
```

These are distinct resources and relationships, not synonyms or a claim that
every resource is populated in every dataset.

## Explore the ontology

| Page | What it explains |
|---|---|
| [Agents and institutions](Agents.md) | Oireachtas, ParliamentaryBody, Houses, HouseTerms, Government, Committees and committee identity |
| [Members and membership](Members.md) | Member, OireachtasMembership, constituencies/panels, committee service and term-scoped collections |
| [Departments, offices and administrative units](Departments.md) | NamedOffice, OfficeHolding, CabinetMembership and AdministrativeUnit |
| [Bills and legislative processes](Bills.md) | The ELI/ELI-DL distinction between Bill works, processes, activities and versions |
| [Bill classes](Bill-Classes.md) · [Bill properties](Bill-Properties.md) | Selected class and relationship summaries; precise declarations live in ontology sources |
| [Debates](Debates.md) · [Debate structure](Debates-body.md) | AKN Work/Expression identity and the structured content model |
| [Concept schemes](Concept-Schemes.md) | Controlled vocabularies and their uses |
| [Ordering business](Ordering-Business.md) | Boundary note for order papers, questions and votes not modelled as a separate current dataset |

## Current coverage and status

The model and ETL are not synonymous with complete published data. Houses,
reference data, Members, Bills and a bounded Debates implementation have
distinct current coverage and limitations. The Debates model is implemented
for its bounded scope, but the approved initial 2011+ production load is not
yet cleared for production. Reference identity/coverage also has unresolved
evidence. See [current coverage and limits](../current-state.md#data-coverage-and-limits)
before interpreting these pages as a completeness claim.

Some concepts exist in OWL before there are mapped or published instances.
Formal ParliamentaryGroup and TechnicalGroup recognition is not inferred from
party membership or Government status; statutory office succession and
several debate crosswalks also remain evidence-dependent or deferred.

## Try the experimental NLQ application

The experimental local NLQ application can translate questions about a limited
subset of loaded RDF into inspectable, read-only SPARQL. For example, it may be
used to ask which parliamentary collection a Member belonged to in a given
term. It is not a complete data browser and results depend on loaded coverage.
See the canonical [NLQ user and developer guide](../../poc/nlq/README.md) for
examples, supported queries, setup and limitations.

## Technical and historical references

- [Current system overview](../current-state.md) — architecture, data
  coverage, graph ownership, identifiers and repository navigation.
- [Ontology module reference](../../ontology/README.md) — module inventory and
  selected vocabulary declarations. The Turtle sources are authoritative.
- [Mapping notes](../mapping_notes.md) and [`mappings/`](../../mappings/) —
  source-field mapping meaning/status.
- [ETL plan](../etl-plan.md) — architectural decisions and dated phase/tranche
  implementation history, not a replacement for current-state documentation.
- [House model](../house_model.md), [ministerial office design](../phase-7-ministerial-offices.md),
  and [Debates design/status](../phase-7-debates.md) — detailed canonical
  conceptual and acceptance records.

Historical investigation and tranche documents are retained as evidence. Where
an older idea is not in the integrated model, the relevant topic page marks it
deferred or superseded rather than presenting it as current.
