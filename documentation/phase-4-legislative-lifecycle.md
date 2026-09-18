# Phase 4 legislative lifecycle implementation

Bills are transformed into one Bill-owned graph named
`https://data.oireachtas.ie/graph/bill/{year}/{number}`.  A Graph Store PUT
replaces the complete graph only after source, RDF and SHACL validation pass.
Competency verification runs against the graph after PUT; a PUT or competency
failure leaves the record dirty for retry. `bills-state.json` stores a SHA-256 hash of each complete Bill source
record, so unchanged records are source-validated and skipped before RDF
transformation or publication.

The Bill is an `eli-dl:DraftLegislationWork`/`eli:LegalResource` and owns one
`{bill-uri}#process`. Stages and supported lifecycle events are owned
`eli-dl:LegislativeActivity` resources. Their source order and `:progressStage`
are retained; `eli-dl:latest_activity` points to the source stage IRI.
Delivery and sponsor participations without source IRIs use SHA-256-derived
fragment IRIs. Resolved sponsors use `eli-dl:had_participant_person`; unresolved
role text is retained only as an `rdfs:label` on the Participation.

Related-document source IRIs identify Expressions. Each has a deterministic
`#work` Work; the Bill links to it with ELI core `eli:has_part`, and the Work
uses `eli:is_realized_by` to point to the source Expression. Amendment lists
are separate derived Works, `#expression` Expressions and `#tabling`
activities. Source stage IRIs identify concrete `eli-dl:LegislativeActivity`
occurrences; `stageURI` resolves each occurrence to a controlled local value
typed both `eli-dl:ProcessStage` and `eli-dl:ActivityType`. The occurrence uses
that value for both `eli-dl:occured_at_stage` and `eli-dl:had_activity_type`.
An amendment's source stage reference resolves through its associated occurrence
to the same controlled `eli-dl:ProcessStage`. `eventURI` and `methodURI` map to
controlled `eli-dl:ActivityType` values only. PDF/XML
formats are embodied by Expressions, with controlled ELI language and IANA
media-type IRIs rather than literals.

Canonical House and HouseTerm IRIs are references only. Sponsor Member IRIs
are references only; no Member labels are emitted. The resulting Act is only
the `eli:basis_for` target; no Act triples, including `dateSigned`, are owned.
Debate source values remain in raw JSON and emit no RDF.

The vocabulary baseline is ELI 1.5 and vendored ELI-DL 3.0; pins and checksums
are recorded in `ontology/external-vocabulary-pins.md`. Validation rejects an
emitted ELI/ELI-DL term outside that audited baseline.

Amendment Work/tabling identifiers use only stage, stage number, date, chamber
and amendment type, so label and rendition changes do not churn identities.
Sponsor participations use Member or role IRIs where supplied. The API supplies
no stable identity for a role-text-only sponsor, so its role text and primary
flag remain the documented residual identity inputs.
