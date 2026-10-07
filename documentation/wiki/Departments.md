# Departments, offices and administrative units

The current model distinguishes an enduring **particular office**, the
**person's dated tenure in it**, and the administrative institution with which
the office is associated. The ontology does not treat a changing title or a
department label as sufficient evidence that an office or institution is the
same identity over time.

## Three different resources

| Resource | Meaning |
|---|---|
| `members:NamedOffice` | One particular enduring institutional office, independent of its holder, label, associated unit or responsibilities. Its category is represented with `members:hasRoleType` to an `members:OfficeType` **concept individual**, not an OWL role class. |
| `members:OfficeHolding` | A dated relationship between a person and one NamedOffice. It links the office with `members:heldOffice` and the person through `members:officeHolder` / `members:hasOfficeHolding`. It is a tenure record, not the office itself. |
| `members:AdministrativeUnit` | A distinct, locally controlled enduring administrative institution (for example, a reviewed department identity). It is not a NamedOffice or a ministerial responsibility/portfolio. |

```text
agents:Member ── holds via members:OfficeHolding ── members:NamedOffice
                                                        ├─ hasRoleType → OfficeType concept
                                                        ├─ headsAdministrativeUnit → AdministrativeUnit
                                                        └─ assignedToAdministrativeUnit → AdministrativeUnit
```

Departmental Minister offices can be linked as heading an AdministrativeUnit.
Minister-of-State offices can be assigned to a unit; assignment does not mean
headship. The model does not create one office for every portfolio or delegated
function. Office succession is asserted only when positively reviewed; a
changed label, identifier or Department boundary does not by itself prove
office succession.

## Government and Cabinet membership

Where qualifying office holdings represent Taoiseach, Tánaiste or Minister
office types, the ETL derives a time-bounded `members:CabinetMembership`
episode in the constitutional `agents:Government`. It links back to the
supporting `members:OfficeHolding` records with
`members:supportedByOfficeHolding`. Overlapping or continuous qualifying
holdings are combined so concurrent offices do not create duplicate episodes.

Minister-of-State holdings do not create constitutional Cabinet membership;
they belong to the wider `members:GovernmentExecutive` tier. The parliamentary
whip bloc is `members:GovernmentBenches`, a separate concept. See
[Agents and institutions](Agents.md#government-is-not-a-house-or-bill-source).

## Current coverage and deferred detail

The office and administrative-unit registry is a reviewed, limited bootstrap,
not a comprehensive catalogue of every historical office, Department,
function, responsibility or portfolio. Accepted local identities are distinct
from source labels and external identifiers; unresolved observations do not
emit guessed holdings. Detailed delegated functions, temporal unit assignments,
complete statutory grounding and unsupported historical successions remain
deferred or evidence-dependent.

For resolution rules, migration, registry status and validation, see the
canonical [ministerial office design and tranche record](../phase-7-ministerial-offices.md),
[office registry](../ministerial-office-registry.md), and
[office observation reconciliation](../office-observation-reconciliation.md).
The RDF vocabulary is in `ontology/members.owl.ttl` and the ETL mapping status
is in [mapping notes](../mapping_notes.md). This page replaces the former
function/URI proposal in this wiki; that proposal is not an implemented
Department ontology or identifier policy.
