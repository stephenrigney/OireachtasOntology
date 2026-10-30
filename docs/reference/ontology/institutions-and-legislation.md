# Institutions and legislation

**Status:** Describes current OWL terms; consult the linked modules for exact
axioms and the mapping CSVs for fields actually emitted by the ETL.

## Institutions

`agents:ParliamentaryBody` is the class of enduring parliamentary institutions.
The Oireachtas, Dáil and Seanad are represented by individuals; `agents:House`
denotes an enduring House, while `agents:HouseTerm` denotes a bounded numbered
parliamentary term. A House and its terms are related with `agents:hasTerm` /
`agents:termOf`. Do not treat a term as the continuing institution.

The constitutional `agents:Government` is distinct from the generic Government
Bill submitter concept. The model also distinguishes Members as people from
roles and participation in events. These distinctions are defined in
[`agents.owl.ttl`](../../../ontology/agents.owl.ttl) and
[`members.owl.ttl`](../../../ontology/members.owl.ttl).

## Legislative documents

The legislation module reuses ELI and ELI-DL resource and process classes rather
than parallel local Bill Work/Expression/Format classes. Bill processes,
versions, statuses and amendment-list types are described in
[`legislation.owl.ttl`](../../../ontology/legislation.owl.ttl). Events and
controlled stage values are in [`events.owl.ttl`](../../../ontology/events.owl.ttl).

The older local wiki's Departments page was explicitly a draft and proposed URI
patterns that are not an ontology specification. Current ministerial office
and administrative-unit concepts are in `members.owl`; accepted identities
come from the reviewed registry and are not minted from labels alone. Unmapped
department lifecycle and historical-name concepts should not be inferred from
the legacy page.
