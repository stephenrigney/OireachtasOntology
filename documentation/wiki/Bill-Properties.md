# Bill and legislative-process relationships

This page summarizes the main relationship groups for readers. It is not an
exhaustive property catalogue; consult
[`ontology/legislation.owl.ttl`](../../ontology/legislation.owl.ttl),
[`ontology/events.owl.ttl`](../../ontology/events.owl.ttl), the
[mapping CSVs](../../mappings/bill_mapping.csv), and
[mapping notes](../mapping_notes.md) for exact declarations and field status.

| Relationship | What it connects |
|---|---|
| ELI `eli:is_realized_by` / `eli:realizes` | A legislative Work and its Expression(s). The source provides language-/version-specific text expressions. |
| ELI-DL `eli-dl:forms_part_of` | A legislative activity to its LegislativeProcess. |
| ELI-DL `eli-dl:latest_activity` | A LegislativeProcess to its latest generated lifecycle activity. |
| ELI-DL `eli-dl:process_type`, `process_status`, `process_number` | Controlled Bill type, current process status and Bill number on the process. |
| ELI-DL `eli-dl:was_submitted_by` | The Bill submitter/source; the GovernmentBillSource concept is not the Government institution. |
| Oireachtas `events:inHouse` and ELI-DL `eli-dl:parliamentary_term` | The House and numbered HouseTerm for a concrete activity. They are distinct identities. |
| ELI-DL `eli-dl:had_participation` | A participation resource for a sponsor, mover or other supported role; role and person are carried on participation rather than collapsed into the Bill. |
| ELI `eli:has_part` / `eli:is_part_of` | A Bill work and related amendment-list resources where emitted. An amendment list is not the activity of tabling or considering an amendment. |
| Oireachtas `members:reconciledSponsorOffice` / `members:reconciledSponsorHolding` | Separate Bill-local, reviewed reconciliation from source participation to a NamedOffice and (only when person/time evidence supports it) an OfficeHolding. |

Bill and associated resource IRIs follow the source and deterministic ETL
contracts; see [Bill identity and lifecycle design](../phase-4-legislative-lifecycle.md).
The wiki's old exhaustive URI/property tables mixed intended patterns with
properties that are not emitted and have therefore been replaced by this
conceptual index. The complete current data/query boundary is summarized in
[Current system overview](../current-state.md).
