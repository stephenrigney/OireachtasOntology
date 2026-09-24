# Parliamentary member collections and parliamentary parties

## Status

This note records the Phase 4.5 Tranche 2 semantic contract agreed before implementation.
It supersedes the earlier Tranche 2 assumption that an Oireachtas term-scoped party
resource is a temporal specialization of an enduring political-party organisation.

The design deliberately separates:

1. collections of Oireachtas Members represented by the Oireachtas API;
2. parliamentary parties as collections of Members;
3. formally recognised parliamentary groups under Standing Orders; and
4. enduring political-party organisations that may be identified through external
   authorities such as Wikidata.

Ontology scope and ETL population scope are separate. A class may be included in the
ontology because it is well grounded in Standing Orders even where the current API does
not provide enough evidence to instantiate it.

## Authoritative semantic basis

The Dáil Standing Orders distinguish a parliamentary "party" from a recognised "group".
Standing Order 170 defines a group as a body of Members in Opposition, sets the minimum
number for recognition, provides that elected Members of a registered political party
are referred to as a "party", and permits technical groups subject to stated conditions.
A party can therefore exist without being a recognised group, and a technical group can
combine party and non-party Members. Parties containing a Minister or Minister of State
cannot form part of a Dáil group.

The Seanad Standing Orders use a different recognition rule: a group is one recognised
by the Cathaoirleach and consisting of at least four Senators.

These rules justify ontology classes for parliamentary parties and parliamentary groups,
but they do not justify creating group instances from the current Parties or Members API
where group recognition is not explicitly supplied.

Current sources:

- Dáil Éireann Standing Orders, consolidated March 2026:
  https://data.oireachtas.ie/ie/oireachtas/parliamentaryBusiness/standingOrders/dail/2026/2026-04-08_consolidated-dail-eireann-standing-orders-march-2026_en.pdf
- Seanad Éireann Standing Orders relative to Public Business 2025:
  https://data.oireachtas.ie/ie/oireachtas/parliamentaryBusiness/standingOrders/seanad/2025/2025-01-30_seanad-eireann-standing-orders-relative-to-public-business-2025_en.pdf

The Standing Orders are semantic authorities for the class model. The Oireachtas Open
Data API remains the authority for which instances and membership relationships are
populated by the deterministic ETL in this tranche.

## Core class model

### `members:ParliamentaryMemberCollection`

A collection of Oireachtas Members defined by a parliamentary relationship or status.
It is the general class under which both API party/non-party collections and formally
recognised parliamentary groups can be represented.

It should be modelled as a group of agents, for example as a subclass of `foaf:Group`.

### `members:ParliamentaryParty`

A `members:ParliamentaryMemberCollection` consisting of Members of the relevant House
who are represented as members of the same registered political party for parliamentary
purposes.

A ParliamentaryParty is not the enduring registered political-party organisation. It is
the parliamentary collection of Members associated with that party in the source
context.

For the current API, each non-`Independent` Parties record is a term-scoped
`members:ParliamentaryParty` and retains its authoritative source IRI, for example:

```text
https://data.oireachtas.ie/ie/oireachtas/party/dail/34/Fianna_Fáil
```

### `members:IndependentMemberCollection`

A `members:ParliamentaryMemberCollection` containing Members represented by the API as
`Independent` / non-party for the relevant House term.

The collection does not imply that those Members act together, are formally recognised
as a parliamentary group, or belong to the same technical group. It is the source-backed
collection used to represent their common non-party status.

Each API `Independent` record retains its term-scoped source IRI. No term-independent
"Independent organisation" or political party is implied.

### `members:ParliamentaryGroup`

A `members:ParliamentaryMemberCollection` formally recognised as a group under the
Standing Orders of the relevant House.

This is a procedural recognition concept, not a synonym for
`members:ParliamentaryParty`.

A collection can be both a ParliamentaryParty and a ParliamentaryGroup where the same
body satisfies both descriptions. Neither class is a subclass of the other.

The different Dáil and Seanad recognition rules should be captured in documentation and,
where useful later, validation or more specific subclasses. They should not be encoded as
current-instance assertions when the API does not supply the required recognition facts.

### `members:TechnicalGroup`

A subclass of `members:ParliamentaryGroup` for a technical group recognised under the
relevant Standing Orders.

The class is part of the ontology in this tranche, but no TechnicalGroup instances are
to be generated unless an API source explicitly provides enough evidence to identify
them.

## Enduring political parties

An enduring registered political party is a different entity from a
`members:ParliamentaryParty`.

This tranche does not require a local Oireachtas `PoliticalParty` class or locally
minted enduring party individuals. Where an external authority such as Wikidata has an
accepted identity for the enduring political-party organisation, a reviewed relationship
may point directly to that external identity.

The relationship is:

```text
term-scoped ParliamentaryParty
        |
        | members:recognisedAsParty
        v
enduring external political-party identity
```

`members:recognisedAsParty` means that the ParliamentaryParty is the parliamentary
collection constituted on the basis of Members belonging to the registered political
party denoted by the target.

It does **not** mean:

- that the ParliamentaryParty and PoliticalParty are identical;
- that the external party is a temporal version of the ParliamentaryParty; or
- that the ParliamentaryParty is recognised as a `members:ParliamentaryGroup`.

Accordingly, neither `owl:sameAs` nor `prov:specializationOf` is appropriate between a
ParliamentaryParty and the enduring political-party organisation.

The property should have `members:ParliamentaryParty` as its domain. A restrictive
local range is not required in this tranche because the target is an externally
identified entity and arbitrary external facts are not imported into the authoritative
ontology graph.

## Member-to-collection membership

The existing Member API supplies dated party records nested inside a specific
Oireachtas membership. That source structure should remain explicit.

Introduce a general membership-record class, provisionally
`members:ParliamentaryCollectionMembership`, as a subclass of the existing
`members:MembersMembership` / `org:Membership` pattern.

`members:PartyMembership` becomes a subclass of
`members:ParliamentaryCollectionMembership` and is used when the target is a
`members:ParliamentaryParty`.

An API `Independent` record uses the general
`members:ParliamentaryCollectionMembership`; it is not falsely described as membership
of a political party.

The general relationship should be explicit:

```text
Member
  |
  +-- OireachtasMembership
  |       +-- House
  |       +-- HouseTerm
  |
  +-- ParliamentaryCollectionMembership
          +-- date range
          +-- inOireachtasMembership -> OireachtasMembership
          +-- memberOfCollection -> ParliamentaryMemberCollection
```

The final property names should follow the repository's existing membership naming
pattern. The implementation should preserve the semantic requirements above even if the
exact property spelling is adjusted during the ontology edit.

For the party-specific case, the existing `members:isPartyMembershipOf` can be retained
or made a subproperty of the general collection-membership predicate, with range
`members:ParliamentaryParty`.

## Term scope and source identity

The term scope of API party resources remains significant and must not be erased.

The Parties endpoint explicitly supplies a party URI under a House term and a House
resource. The ETL should therefore continue to:

- preserve the source party URI as the RDF subject;
- link the collection to the supplied HouseTerm using the existing term relationship
  where semantically appropriate;
- preserve `partyCode` and `showAs`; and
- keep descriptive triples owned by the Parties graph.

The model change is semantic rather than an instruction to mint an enduring local party
identity. The term-scoped source resource is reclassified from the ambiguous
`PartyGrouping` model to a precise ParliamentaryMemberCollection subtype.

## API population boundary

The deterministic API ETL may create only what the API supports.

For the current Parties endpoint:

```text
partyCode != "Independent"
    -> members:ParliamentaryParty

partyCode == "Independent"
    -> members:IndependentMemberCollection
```

For the current Member endpoint:

- a dated record targeting a ParliamentaryParty becomes a
  `members:PartyMembership`;
- a dated record targeting an IndependentMemberCollection becomes a general
  ParliamentaryCollectionMembership;
- the record remains explicitly contextualised by its containing
  OireachtasMembership and date range.

This iteration must not infer or populate:

- `members:ParliamentaryGroup` instances;
- `members:TechnicalGroup` instances;
- Rural Independent, Civil Engagement or other group instances;
- group recognition status;
- group membership from debates, biographies, Standing Orders application, press
  material or other non-API evidence; or
- Government/Opposition group membership merely from party identity.

Those are later gap-analysis and source-extension questions.

## External reconciliation contract

Only `members:ParliamentaryParty` instances are candidates for enduring political-party
reconciliation.

Candidate generation may use:

- `partyCode`;
- `skos:prefLabel` / API `showAs`;
- Irish political-party context;
- external labels and aliases;
- external entity type and jurisdiction; and
- historical dates where useful to reject anachronistic candidates.

No label, normalized label or fuzzy match is sufficient for automatic acceptance.
Until a deterministic authority key is found, the first accepted external party target
requires human review.

The accepted assertion is:

```turtle
<term-scoped-parliamentary-party>
    members:recognisedAsParty <accepted-external-political-party> .
```

It is published as derived enrichment in an independently replaceable external-link
graph. External party facts are not copied into the authoritative Parties graph.

`members:IndependentMemberCollection` is excluded from political-party reconciliation.

DBpedia and Wikipedia enrichment remain a separate later decision after the Wikidata
relationship has proved useful. Member-style `foaf:isPrimaryTopicOf` should not be
copied mechanically because an article about an enduring political party is not
necessarily the primary topic of a term-scoped ParliamentaryParty.

## Reconciliation architecture

Tranche 2 should refactor the Phase 3.5 Member reconciliation implementation rather than
create a parallel party subsystem.

The reusable core owns:

- reconciliation state selection;
- review-file hashing and review precedence;
- audit trail;
- retry/recheck scheduling;
- dirty publication replay;
- exact stored-payload recovery;
- graph replacement; and
- post-publication whole-graph verification.

Entity policies own:

- local identity and source fingerprint;
- eligibility;
- candidate generation and evidence;
- accepted-link semantics;
- external graph IRI; and
- review validation.

State identity must be generic, for example `(entity_kind, local_iri)`. It must not
assume the Member subsystem's unique `memberCode`, because party codes repeat across
House terms.

Party review decisions are keyed by the full term-scoped ParliamentaryParty IRI, not by
`partyCode`. A review decision for one House term must not silently propagate to every
historical occurrence of the same party code.

Unresolved, ambiguous and lookup-failure outcomes do not clear a previously published
accepted graph. An explicit reviewed revocation/rejection may clear the graph. Dirty
state must replay the exact stored payload before new reconciliation work, preserving
the Phase 3.5 recovery guarantee.

## Legacy ontology migration

Implementation must audit, not mechanically rename, the existing party-related model.

Expected primary replacements are:

```text
members:PartyGrouping
    -> members:ParliamentaryMemberCollection

members:Party
    -> members:ParliamentaryParty
```

The existing term-independent `members:Independent` named individual should not be used
as the target for API `Independent` records. Term-scoped API Independent resources are
`members:IndependentMemberCollection` instances.

Dependent legacy terms such as `members:PartyInGovernment`,
`members:PartyInOpposition`, `members:PartiesMembership`, `members:isWhipFor`, and
their restrictions must be semantically audited during implementation. They must not be
retargeted mechanically if that would imply Standing Orders group status or enduring
political-party identity not supported by the API.

Mappings, SHACL/quality validation, golden fixtures, competency queries and Member
transform references must be updated consistently.

## Acceptance criteria

Tranche 2 model implementation is complete when:

- the ambiguous `PartyGrouping` / `Party` model has been replaced by the documented
  ParliamentaryMemberCollection model;
- non-Independent API party records are term-scoped ParliamentaryParty instances;
- API Independent records are term-scoped IndependentMemberCollection instances;
- Member API records preserve dated membership of those collections and explicit
  Oireachtas-membership context;
- ParliamentaryGroup and TechnicalGroup exist as Standing-Orders-grounded ontology
  classes but are not populated from unsupported inference;
- ParliamentaryParty is not modelled as a subclass of ParliamentaryGroup;
- no ParliamentaryParty is asserted identical to, or a PROV specialization of, an
  enduring PoliticalParty;
- reviewed external relationships use `members:recognisedAsParty`;
- IndependentMemberCollection is excluded from political-party reconciliation;
- reconciliation operational machinery is generic rather than cloned from Members;
- authoritative Parties/Member graphs remain independent of external-link publication;
  and
- all Phase 0-4 and Phase 3.5 regression/integration behaviour continues to pass.
