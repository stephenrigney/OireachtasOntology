# ETL architecture

This is the canonical overview of the implemented ETL architecture and its
accepted boundaries. The Python implementation and tests are executable
authority; OWL and mapping CSVs define vocabulary and field meaning. See the
[mapping notes](../../documentation/mapping_notes.md),
[refresh/state contract](../reference/etl/state-and-refresh.md),
[legislation contract](../reference/etl/legislation.md), and
[operations guide](../development/operations.md) for their distinct detail.
The former phase plan is retained as [historical evidence](../reports/etl/etl-plan-history.md),
not an active backlog or current architecture authority.

## Data flow and ownership

```text
Oireachtas API / reviewed local inputs
    -> immutable raw evidence
    -> endpoint transformation and deterministic RDF serialization
    -> source, RDF, SHACL and endpoint-quality validation
    -> durable publication intent in Core State
    -> whole named-graph replacement and remote verification
    -> verified run/catalog finalization
```

Raw captures and operational state are outside the semantic RDF dataset.
Source bytes are retained so transformations can be reproduced; transformation
does not redefine ontology or mapping meaning. The same inputs and versioned
contracts must yield deterministic RDF and identifiers.

Each publisher owns descriptive triples for its resources. Other publishers may
reference those IRIs, but do not duplicate their descriptions. Current owner
boundaries are implemented in the endpoint transformers and publication code;
the table below is a high-level guide, not an exhaustive resource inventory.

| Source/publisher | Principal ownership |
|---|---|
| Houses | House and HouseTerm descriptions |
| Parties | Party and parliamentary collection descriptions |
| Constituencies | Constituency and panel descriptions |
| Members | Member, membership and Member-owned nested descriptions; shared reference-owner candidates are handled by their own publication boundary |
| Legislation/Bills | Bill-owned legislative lifecycle and related resources |
| Explicit Debates batches | Work-owned graphs only; this is not a corpus scan or routine refresh policy |

Office registries, reconciliation decisions and other versioned local inputs
remain separate inputs with their own ownership contracts. See the focused
contracts linked from the [documentation index](../README.md); this overview
does not redefine them.

Shared reference-owner graphs are consolidated from their standalone endpoint
and source-grounded nested observations in a complete Members capture. Candidate
owner graphs require validation and reference closure before publication; an
incomplete or quarantined Members scan is not evidence to replace a shared
owner graph. Absence from incremental input does not authorize destructive
removal.

One accepted exception is deliberately evidence-bound: for Committee IRI
`https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_committee_on_the_implementation_of_the_good_friday_agreement`,
owner consolidation accepts the thirteen observations with Committee ID/code
`115` and excludes the single conflicting ID/code `156` observation only when
the complete authoritative observation set matches SHA-256
`06fb58595b879dc206e2bb50aa95014c41718275f1e251d3a5696a1830ccbdb2`. The
exception changes only the Committee owner description: it does not delete or
reinterpret the conflicting Member-owned membership/role evidence. Any changed
evidence or any other conflicting Committee identity fails closed pending
review. The full recorded decision and evidence context remain in the
[historical plan record](../reports/etl/etl-plan-history.md#project-owner-decision--accept-id-115-for-this-exact-reviewed-evidence).

## Validation and publication

Candidate source and RDF are validated before publication. The applicable
pipeline includes RDF syntax/datatype, SHACL and endpoint-specific semantic or
competency checks. The validated candidate is serialized deterministically.
Core State records the exact pending payload before remote mutation; publication
uses a whole-graph Graph Store Protocol `PUT`, followed by whole-graph
verification. Only verified graphs are marked clean. A failed or interrupted
publication remains dirty and is recovered by replaying its exact saved payload
and verifying it, not by resuming an in-memory run.

One named graph is the atomic publication unit. A multi-graph run is not a
transaction: already verified graph replacements are not rolled back if a later
graph or provenance catalog fails. The versioned provenance/catalog graph and
Core State finalization provide the run-level completion boundary. Core State is
canonical operational state; the Fuseki/TDB2 dataset is a replaceable
projection. External identity reconciliation has independent durable state and
publication; an external-service failure does not undo authoritative ETL
publication.

Invalid or unverified RDF is never reported as successfully published. A
complete source view is required before absence/missing evidence is recorded;
incremental observations alone do not establish source deletion. No invalid
publication is permitted as a recovery shortcut.

## Refresh boundaries

Routine refresh policy is endpoint-specific: Houses, Parties and
Constituencies use complete refreshes; Members use a complete scan with
per-resource change detection; Bills use `last_updated` incremental extraction
with overlap and separate complete-source reconciliation. External identity
refresh uses the reconciliation store's own due/review policy. Debates remains
explicit-input batch publication without a cursor, completeness claim or
absence/deletion behavior. Other unimplemented source coverage remains deferred.

The details of cursors, complete scans, state ownership, dirty recovery and
publication are in the [state and refresh reference](../reference/etl/state-and-refresh.md).
Operational host provisioning, scheduled jobs, backup/restore, incident handling
and the deployment authorization boundary are in the
[operations guide](../development/operations.md).
