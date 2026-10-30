# Houses of the Oireachtas Ontology

This repository defines an OWL ontology and API-to-RDF mappings for Houses of
the Oireachtas data, together with a deterministic Python ETL pipeline. The OWL
modules are authoritative for vocabulary; mapping files and implementation
contracts define how source data is represented. Explanatory prose does not
override those sources.

## Documentation

- [Documentation index](docs/README.md)
- [Practical ontology guide](docs/guides/ontology.md)
- [OWL source-module index](ontology/README.md)
- [Mapping notes](documentation/mapping_notes.md) and [mapping CSVs](mappings/)

The [documentation index](docs/README.md) separates current guidance and
contracts from archived reports. ETL publication requires validated RDF; do not
publish unvalidated output.
