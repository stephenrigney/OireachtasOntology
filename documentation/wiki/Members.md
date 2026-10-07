# Members and parliamentary membership

The model separates **who a person is** from **which parliamentary service or
collection membership they held, and when**. `agents:Member` is the canonical
person class. A Member may serve in successive Dáil or Seanad terms, on
committees, and in a parliamentary collection; these are dated relationships,
not interchangeable person types.

## House service

`members:OireachtasMembership` is the record type for a Member's House service.
Its `DailMembership` and `SeanadMembership` subclasses distinguish the term
types. A record identifies the person and both the enduring House and the
numbered HouseTerm:

```text
agents:Member
  └─ members:hasMembersMembership → members:OireachtasMembership
       └─ DailMembership / SeanadMembership
            ├─ members:isMembershipOfMember → agents:Member
            ├─ members:isOireachtasMembershipOf → agents:House (enduring)
            ├─ members:inHouseTerm → agents:DailTerm / SeanadTerm
            └─ members:hasMembershipDateRange → dated service interval
```

Committee service is a separate sibling membership type:

```
agents:Member ── hasMembersMembership → members:CommitteeMembership
                                             └─ isCommitteeMembershipOf → members:Committee
```

The inverse `isMembershipOfMember` link is explicit. Dáil and Seanad
membership records are distinct subclasses and point to the corresponding
term type. A Member can have different memberships over time; the identity of
the person is not the identity of a particular term's service. For the
institution/term distinction, see [Agents](Agents.md) and the canonical
[House model](../house_model.md).

## Parties and independent collections

`members:ParliamentaryMemberCollection` is the broad class for term-scoped
collections in which Members are represented as belonging. Two current source
types are:

- `members:ParliamentaryParty` — a parliamentary collection associated with a
  registered political party for that term;
- `members:IndependentMemberCollection` — a term-scoped API collection for
  Members represented as Independent/non-party. It is **not** a political
  party and does not imply recognition as a parliamentary group.

A dated `members:ParliamentaryCollectionMembership` points to its containing
`OireachtasMembership` and to the collection:

```text
members:ParliamentaryCollectionMembership
  ├─ members:inOireachtasMembership → members:OireachtasMembership
  └─ members:memberOfCollection → ParliamentaryParty
                                 or IndependentMemberCollection
```

Party-specific membership may also use `members:PartyMembership` and
`members:isPartyMembershipOf`. An external enduring-party link, when reviewed,
is a separate reconciliation relationship; the term-scoped collection is not
the same identity as the external political-party organisation. Formal
`ParliamentaryGroup` and `TechnicalGroup` instances are not inferred from
party size, Government status, or collection membership.

## Constituencies, panels and committees

`members:Constituencies` has two distinct forms: a geographically bounded
`members:DailConstituency` and a `members:SeanadPanel`. Both are term-scoped
through `members:constituencyInHouseTerm`; a Seanad panel is not asserted to be
a geographic constituency. These identities should not be treated as one
perpetual constituency across term boundaries. A House-membership record can
link to the relevant representative body through
`members:isRepresentativeFrom`.

`members:Committee` is an `org:Organization`, not a House or HouseTerm.
Committee descriptive identity is owned separately from a Member's
`members:CommitteeMembership` service record. That record can carry dates and
an optional `members:Chair` or `members:DeputyChair` committee role. Committee
service does not make a Committee an instance of `agents:House`; see
[Agents and institutions](Agents.md#committees-are-organisations-not-houses).

## What is populated and where to go next

Member graphs contain source-backed House, collection and Committee
membership records. Constituency, party and Committee descriptions have their
own owner graphs. Identity ambiguities and absent evidence are not resolved by
guessing; some references remain quarantined or under review. Local office
tenure, where a source observation resolves to a reviewed office, is described
with the [office model](Departments.md), not by reviving legacy
`MinisterOfStateMembership` records.

For ETL ownership, mapping status and reference-coverage acceptance see the
[current system overview](../current-state.md#data-coverage-and-limits),
[mapping notes](../mapping_notes.md), and the detailed
[reference-coverage record](../etl-plan.md). The ontology declarations are
indexed in the [ontology module guide](../../ontology/README.md).
