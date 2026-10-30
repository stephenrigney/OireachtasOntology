# Bills and events

**Status:** Vocabulary orientation, not a substitute for the active mapping
contract. Exact terms and axioms are in the linked OWL modules.

A Bill is represented with ELI/ELI-DL work and process resources. Its process
status, process type, submitting agent, latest activity and concrete lifecycle
activities are different facts. Controlled stage, event and status values are
not occurrences. The local `legislation.owl` module annotates reused ELI/ELI-DL
terms for Oireachtas usage; `events.owl` defines Oireachtas event concepts.

The existing `oir:BillDelivery` introduction/presentation activity links to
its Bill Work with `eli-dl:created_a_realization_of` and to its process with
`eli-dl:forms_part_of`, including application/by-application delivery methods.
Use this explicit two-edge relationship for Bill status and sponsorship;
named-graph co-ownership is not a substitute for it.

Amendment documents and amendment activities are distinct resources. A source
status or controlled stage value does not by itself assert that a particular
event occurred. Sponsoring participation and House/term references follow the
active mapping contract; see [Bill mappings](../../../mappings/bill_mapping.csv)
and [mapping notes](../../../documentation/mapping_notes.md).

- [Legislation module](../../../ontology/legislation.owl.ttl)
- [Events module](../../../ontology/events.owl.ttl)
- [Agents module](../../../ontology/agents.owl.ttl)
