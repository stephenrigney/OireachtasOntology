# Membership, parties and offices

**Status:** Current vocabulary reference. It does not assert that every
ontology class is populated by the ETL; mappings and implementation define
population.

## Membership

`agents:Member` identifies the person. `members:OireachtasMembership` and its
House- and committee-membership subtypes represent dated relationships. A
membership points to both an enduring `agents:House` and a numbered
`agents:HouseTerm`; these are not interchangeable. Dáil constituencies and
Seanad panels are distinct term-scoped resources.

## Parliamentary collections and parties

`members:ParliamentaryParty` is a term-scoped parliamentary collection, not an
enduring external party organization. `members:IndependentMemberCollection`
does not imply a party or recognized group. A dated
`members:ParliamentaryCollectionMembership` records the Member-to-collection
relationship in its membership context. `members:ParliamentaryGroup` and
`members:TechnicalGroup` are separate concepts; current Parties/Members data
does not by itself establish group instances. Reviewed local affiliation and
external party reconciliation are distinct links and identities; see the
[identity](../../../documentation/political-affiliation-identity.md) and
[publication](../../../documentation/political-affiliation-publication.md)
contracts.

## Roles and offices

The OWL separates a person, an OWL role, an enduring `members:NamedOffice`, an
`members:AdministrativeUnit`, and a dated `members:OfficeHolding`.
`members:OfficeType` is a controlled SKOS category, not an OWL role. Constitutional
Government, `members:GovernmentExecutive`, and `members:GovernmentBenches` are
also distinct; avoid interpreting one as another.

Some legacy declarations remain deprecated for migration compatibility. Consult
the module's annotations and active Member mappings rather than using a
deprecated term as a current target. Office and membership axioms are in
[`members.owl.ttl`](../../../ontology/members.owl.ttl); reviewed population
constraints are documented in the [office registry guide](../../../documentation/ministerial-office-registry.md).
