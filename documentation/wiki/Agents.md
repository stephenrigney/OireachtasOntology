# Agents and institutions

This page explains the institutions and people around parliamentary
proceedings. `agents.owl.ttl` supplies the canonical person, ParliamentaryBody,
House and Government terms; `members.owl.ttl` supplies membership and
collection structures. See [Members](Members.md) for how dated service is
recorded.

## Oireachtas, Houses and terms

`agents:ParliamentaryBody` is the class of enduring parliamentary formal
organisations. The enduring Oireachtas resource
`<https://data.oireachtas.ie/oireachtas>` is an individual of that class, not
an OWL class or a HouseTerm. It is organisationally related to its two
continuous Houses:

```text
<.../oireachtas>  agents:ParliamentaryBody individual
  ├─ org:hasSubOrganization → <.../house/dail>   agents:House
  └─ org:hasSubOrganization → <.../house/seanad> agents:House

agents:House ── agents:hasTerm → agents:HouseTerm
                                  ├─ agents:DailTerm
                                  └─ agents:SeanadTerm
```

Dáil Éireann and Seanad Éireann are enduring institutions. A numbered Dáil or
Seanad is a time-bounded `agents:HouseTerm`, disjoint from
`agents:ParliamentaryBody`; it is not another enduring organisation. `hasTerm`
and `termOf` connect the term to its House. Term number, dates, seat count and
label describe the term. See the canonical [House model](../house_model.md).

## Government is not a House or bill source

The constitutional Government is a distinct enduring `agents:Government`
organisation (`<https://data.oireachtas.ie/government>`), responsible to the
enduring Dáil. It is not a `ParliamentaryBody`, a HouseTerm, or the
`GovernmentBillSource` concept used as a Bill submitter. The word “Government”
can also mean a wider parliamentary grouping, so the model distinguishes:

| Resource | Meaning |
|---|---|
| `agents:Government` | Constitutional Government; Cabinet-level Government membership is represented separately by dated `members:CabinetMembership` resources. |
| `members:GovernmentExecutive` | Wider executive tier including Ministers of State. It is not identical to the constitutional Government. |
| `members:GovernmentBenches` | Parliamentary whip bloc, which may include Members outside the executive. It is not a synonym for Cabinet. |

Taoiseach, Tánaiste and ministerial role vocabulary remains available for role
classification and links, but actual dated local office tenure uses
`members:NamedOffice` and `members:OfficeHolding`; see
[Departments and offices](Departments.md). Do not read the older role classes
as a substitute for a particular office identity or holding.

## Members and roles

`agents:Member` is the canonical person class (a `foaf:Person`). A person may
serve as a Deputy or Senator in different HouseTerms over a career. The
membership record, rather than a permanent person type alone, carries the
House and term context. Detailed relationships are in [Members](Members.md).

For Bill submission, `eli-dl:was_submitted_by` points to a supported submitter
resource such as `agents:GovernmentBillSource`, `agents:PrivateMember`, or a
resolved `agents:PrivateSponsor`. The Government bill-source concept is not the
constitutional Government institution. ELI-DL `Participation` resources and
role concepts such as `members:MoverRole` represent participation in supported
legislative activities.

## Committees are organisations, not Houses

`members:Committee` is an `org:Organization`, distinct from both a continuous
House and a numbered HouseTerm. A Committee has its own identity and shared
description. When source evidence associates it with a HouseTerm, that
association does not turn the Committee into a HouseTerm. Committee member
service is represented as `members:CommitteeMembership` in the relevant
Member's membership graph; the Committee's description is separately owned.

Type and purpose are distinct concept schemes: `hasCommitteeType` can point to
Select, Joint or Special Committee concepts; `hasCommitteePurpose` can point
to Policy or Shadow Department concepts. Committee URI evidence and the
conservative owner-identity boundary are recorded in the reference-coverage
and Debates integration sections of the [ETL plan](../etl-plan.md).

## Related pages

- [Members, HouseTerms and collections](Members.md)
- [Departments, NamedOffice and AdministrativeUnit](Departments.md)
- [Current system overview](../current-state.md)
- [Ontology module reference](../../ontology/README.md)

Historical terminology such as `members:Government` for the former whip-side
class, `members:Cabinet`, and `agents:Chamber` is superseded. It is not used as
current model guidance.
