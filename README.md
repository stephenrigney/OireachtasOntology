# OireachtasOntology

OireachtasOntology defines an OWL vocabulary for Houses of the Oireachtas
institutions, people, memberships, legislation and debates, together with a
deterministic Python ETL that turns source data into validated RDF. Apache
Jena Fuseki is the repository's local triple-store target.

## Start here

- [Current system overview](documentation/current-state.md) — the model,
  dataset coverage, graph ownership, identifiers, known limits and links to
  deeper material.
- [Ontology module guide](ontology/README.md) — vocabulary modules and terms.
- [Mapping specifications](documentation/mapping_notes.md) and
  [`mappings/`](mappings/) — source-field mapping contract and status.
- [ETL plan and implementation history](documentation/etl-plan.md) — design
  decisions, phase status, implementation records and deferred work. This is
  a historical/design record, not the concise current-state guide.
- [Local development and operations](documentation/fuseki-user-guide.md),
  [refresh/state contract](documentation/incremental-refresh-state.md), and
  [phase 5 operations record](documentation/phase-5-refresh-operations.md).
- [Post-merge documentation refresh checklist](documentation/post-merge-documentation-checklist.md)
  — small follow-up for the active Query Service Phase 2 and Phase 6 work.

## Data and architecture at a glance

The ETL preserves source evidence, transforms it according to the ontology and
mapping contract, validates candidate RDF, and then publishes to owner-specific
named graphs. Fixed reference graphs are used for Houses, Parties,
Constituencies, Committees and shared office registries; Member, Bill and
Debate resources use replaceable per-resource graphs. Separate graphs own
reviewed external identity links and local Bill sponsor reconciliation. The
current coverage and limitations are described in the
[current system overview](documentation/current-state.md); the authoritative
ETL design record is [documentation/etl-plan.md](documentation/etl-plan.md).

## Natural-language query application

The experimental NLQ application translates natural-language questions into
validated, read-only SPARQL for Fuseki. It is separate from ETL and does not
write to the store. [`poc/nlq/README.md`](poc/nlq/README.md) is the canonical
user and developer guide, including examples, supported patterns, limitations,
local setup and evaluation benchmarks.

## Validation and tests

The project validation fails on ontology parse/consistency problems and active
mapping terms without a recognised definition. With the pinned Java runtime
available through `mise`, run:

```bash
mise install
mise exec -- uv run --locked python tests/validate.py
uv run --locked pytest tests
```

Historical phase plans, tranche reports, benchmarks, investigations and
decision records remain available under [`documentation/`](documentation/).
They are implementation/design history; use the current-state guide above for
the present system.
