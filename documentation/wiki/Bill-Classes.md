# Bill and legislative-process classes

This is a short conceptual index, not a duplicate OWL API. The
[Turtle vocabulary](../../ontology/legislation.owl.ttl),
[events module](../../ontology/events.owl.ttl), and
[ontology module reference](../../ontology/README.md) are authoritative for
declarations and axioms.

| Resource/class | Conceptual role |
|---|---|
| `eli-dl:DraftLegislationWork` | The Bill as a distinct legislative work. The local ETL also types a Bill work as `eli:LegalResource`. |
| `eli-dl:LegislativeProcess` | The process associated with the Bill, with process type, number, status, submitter and latest activity. The ETL uses a deterministic `{Bill IRI}#process` resource; process activities link to it via `eli-dl:forms_part_of`. |
| `events:BillEvent` | A supported concrete procedural event/stage in the Bill lifecycle; events are activities, not the Bill work itself. |
| `eli-dl:LegislativeActivity` | ELI-DL activity vocabulary used for process occurrences, including supported stages and delivery/activity types. |
| `eli-dl:LegislativeProcessWorkVersion` | A Bill process-work version, distinct from the Bill Work and its language-specific Expression. |
| `eli-dl:AmendmentToDraftLegislationWork` | An amendment-list/work resource where represented by the source. It is not interchangeable with the activity recording the amendment. |
| `eli:LegalResource` | ELI resource class used for Bill and referenced legal-resource descriptions as appropriate. Acts are not owned/described by the Bill ETL graph. |
| `eli-dl:Participation` | A reified participation link for a person/agent and role, such as a Bill sponsor or mover, where mapped. |

The process's `eli-dl:latest_activity` points to the current latest generated
activity. Controlled values such as `eli-dl:ProcessType`, process statuses,
activity types and outcomes are individuals, not occurrence records.

## Superseded terms

Older wiki tables referred to local `BillResource`, `BillExpression`,
`BillVersion`, `BillStatus`, `AmendmentList`, `BillSource` and `Mover` classes.
These are not the current class contract. Current mappings use ELI/ELI-DL
resources and participation roles. The former `metalex:` alignment was also
removed. Do not construct RDF using the old classes; see
[Bill properties](Bill-Properties.md) and the
[legislative lifecycle design record](../phase-4-legislative-lifecycle.md).
