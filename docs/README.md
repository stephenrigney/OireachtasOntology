# Documentation

This is the main guide to the repository's human-readable documentation. Start
with a practical guide, consult current architecture and reference contracts for
implementation boundaries, and use reports only as evidence of past evaluations
and decisions. OWL files, mapping CSVs, implementation and tests remain
authoritative where applicable; historical prose does not supersede them.

## Practical guides

- [Ontology guide](guides/ontology.md)
- [Query Service: local setup and use](guides/query-service.md)
- [Fuseki user guide](guides/fuseki.md)
- [SPARQL cookbook](guides/sparql-cookbook.md)
- [Direct graph exploration](guides/graph-exploration.md)
- [Semantic-enrichment evaluation workflow](guides/semantic-enrichment-evaluation.md)

## Current architecture

- [ETL architecture and publication boundaries](architecture/etl.md)
- [Debate identity contract](architecture/debate-identities.md)
- [Parliamentary member collections](architecture/member-collections.md)
- [Party identities](architecture/party-identities.md)

## Ontology references

- [Institutions and legislation](reference/ontology/institutions-and-legislation.md)
- [Membership, parties and offices](reference/ontology/membership-parties-offices.md)
- [Bills and events](reference/ontology/bills-and-events.md)
- [Debates and controlled vocabularies](reference/ontology/debates-and-vocabularies.md)
- [OWL module index](../ontology/README.md)

## ETL and domain references

### ETL contracts and operations

The shared ETL contract is organized by purpose:

- [ETL state and refresh contract](reference/etl/state-and-refresh.md)
- [Legislation ETL reference](reference/etl/legislation.md)
- [External reconciliation refresh](reference/etl/external-reconciliation-refresh.md)
- [ETL operations](development/operations.md)
- [Houses ETL reference](reference/etl/houses-history.md)
- [Members ETL reference](reference/etl/members-history.md)
- [Bill sponsor reconciliation reference](reference/etl/bill-sponsors.md)
- [Debates mapping and implementation](reference/debates/mapping-and-implementation.md)
- [Ministerial office registry](reference/offices/registry.md)
- [Office occurrence ledger](reference/offices/occurrence-ledger.md)
- [Political-affiliation publication](reference/graph-publication-political-affiliations.md)

## Development workflows

- [Party reconciliation](development/reconciliation/parties.md)
- [Member reconciliation](development/reconciliation/members.md)
- [Institution reconciliation](development/reconciliation/institutions.md)
- [Office observation and external reconciliation](development/reconciliation/offices.md)
- [Private beta proposal](development/private-beta-proposal.md) (proposal; not deployment authorization)

Mapping meaning remains in [API mapping notes](../documentation/mapping_notes.md)
and [mapping CSVs](../mappings/). The
[ETL phase plan archive](reports/etl/etl-plan-history.md) is historical evidence,
not an active backlog. Revision-specific
[Phase 6 acceptance evidence](reports/etl/phase-6-tranche-c-acceptance.md)
records implementation acceptance, not deployment authorization.

## Reports and historical evidence

- [Query Service evaluation and completion evidence](reports/query-service/)
- [Debates implementation, source and readiness evidence](reports/debates/)
- [Ministerial offices implementation history](reports/offices/phase-7-implementation-history.md)
- [ETL historical plan and acceptance evidence](reports/etl/)
- [Party identity review](reports/identity/party-identity-review.md)
- [Member source-evidence audit](reports/members/nested-evidence-audit.md)
- [Semantic-enrichment evaluation results](reports/semantic-enrichment/)

## Authority and project records

- [Query Service technical specifications](../poc/specs/) (authoritative technical specification location)
- [Documentation reorganisation inventory](../documentation/documentation-reorganisation-inventory.md)
