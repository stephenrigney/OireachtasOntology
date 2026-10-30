# Documentation

Start with the [practical ontology guide](guides/ontology.md) for the implemented
model and its key identity and temporal distinctions. Use the references below
to find the authoritative OWL module for each subject. OWL files and mapping
CSVs, not prose, determine vocabulary and mapping meaning.

## Ontology references

- [Institutions and legislation](reference/ontology/institutions-and-legislation.md)
- [Membership, parties and offices](reference/ontology/membership-parties-offices.md)
- [Bills and events](reference/ontology/bills-and-events.md)
- [Debates and controlled vocabularies](reference/ontology/debates-and-vocabularies.md)
- [OWL module index](../ontology/README.md)

## ETL architecture and operations

The shared ETL contract is organized by purpose:

- [ETL architecture](architecture/etl.md)
- [ETL state and refresh contract](reference/etl/state-and-refresh.md)
- [Legislation ETL reference](reference/etl/legislation.md)
- [External reconciliation refresh](reference/etl/external-reconciliation-refresh.md)
- [ETL operations](development/operations.md)

Mapping meaning remains in [API mapping notes](../documentation/mapping_notes.md)
and [mapping CSVs](../mappings/). The
[ETL phase plan archive](reports/etl/etl-plan-history.md) is historical evidence,
not an active backlog. Revision-specific
[Phase 6 acceptance evidence](reports/etl/phase-6-tranche-c-acceptance.md)
records implementation acceptance, not deployment authorization.

## Other documentation

- [SPARQL cookbook](../documentation/sparql-cookbook.md)
- [Direct graph exploration](../documentation/direct-graph-exploration.md)
- [Fuseki user guide](../documentation/fuseki-user-guide.md)
- [Documentation reorganisation inventory](../documentation/documentation-reorganisation-inventory.md)

This tranche consolidates shared ETL documentation. Query Service, Debates and
Ministerial Offices retain their existing authoritative contracts and are not
consolidated here.
