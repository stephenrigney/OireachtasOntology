# Bills and events

**Status:** Vocabulary orientation, not a substitute for the active mapping
contract. Exact terms and axioms are in the linked OWL modules.

A Bill is represented with ELI/ELI-DL work and process resources. Its process
status, process type, submitting agent, latest activity and concrete lifecycle
activities are different facts. Controlled stage, event and status values are
not occurrences. The local `legislation.owl` module annotates reused ELI/ELI-DL
terms for Oireachtas usage; `events.owl` defines Oireachtas event concepts.

Amendment documents and amendment activities are distinct resources. A source
status or controlled stage value does not by itself assert that a particular
event occurred. Sponsoring participation and House/term references follow the
active mapping contract; see [Bill mappings](../../../mappings/bill_mapping.csv)
and [mapping notes](../../../documentation/mapping_notes.md).

- [Legislation module](../../../ontology/legislation.owl.ttl)
- [Events module](../../../ontology/events.owl.ttl)
- [Agents module](../../../ontology/agents.owl.ttl)
