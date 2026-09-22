# Agents

The Agents section of the ontology covers the persons, roles, organisations and geographic units involved in the legislative process. It is implemented across two sub-ontologies:

- **`agents.owl`** — constitutional structures: Houses, HouseTerms, Government, Members, bill submitters
- **`members.owl`** — detailed membership, roles, party groupings, committees and constituencies

See also [Members](Members) for the full property and URI reference.

---

## Contents

1. [Constitutional Structures — Houses](#constitutional-structures--houses)
2. [Government — Three-Tier Model](#government--three-tier-model)
3. [Member Class Hierarchy](#member-class-hierarchy)
4. [Committee Structure](#committee-structure)
5. [Constituency Model](#constituency-model)
6. [Bill Submitters](#bill-submitters)
7. [Participation Roles](#participation-roles)
8. [Eliminated Classes](#eliminated-classes)

---

## Constitutional Structures — Houses

The ontology distinguishes between the *continuous constitutional institution* and a *bounded parliamentary term*.

| Class | Ontology | Superclass | Description |
|---|---|---|---|
| `:ParliamentaryBody` | `agents.owl` | `org:FormalOrganization` | Class for enduring parliamentary institutions; the Oireachtas itself is a named individual. |
| `:House` | `agents.owl` | `:ParliamentaryBody` | Dáil Éireann or Seanad Éireann as a continuous institution persisting across successive terms. Named individuals `<.../house/dail>` and `<.../house/seanad>` are the canonical instances. |
| `:HouseTerm` | `agents.owl` | —; disjoint with `:ParliamentaryBody` | A bounded parliamentary sitting period, not an enduring organisation. |
| `:DailTerm` | `agents.owl` | `:HouseTerm` | A specific numbered term of Dáil Éireann (e.g. the 33rd Dáil). Disjoint with `:SeanadTerm`. |
| `:SeanadTerm` | `agents.owl` | `:HouseTerm` | A specific numbered term of Seanad Éireann. Disjoint with `:DailTerm`. |

### House and HouseTerm URIs

```
https://data.oireachtas.ie/house/dail
https://data.oireachtas.ie/house/seanad
https://data.oireachtas.ie/ie/oireachtas/house/dail/33
https://data.oireachtas.ie/ie/oireachtas/house/seanad/27
```

### HouseTerm Datatype Properties

| Property | Range | Notes |
|---|---|---|
| `:seats` | `xsd:integer` | Number of seats in this term (e.g. 33rd Dáil: 160; 34th Dáil: 174). Corresponds to `house.seats` in the houses API. |
| `dct:temporal` | `dct:PeriodOfTime` | Links the term to a period-of-time node. The node carries `dcat:startDate` (commencement) and `dcat:endDate` (dissolution; absent for the current sitting term). |

---

## Government — Three-Tier Model

The Government is modelled in three widening tiers:

| Tier | Class | Ontology | Description |
|---|---|---|---|
| 1 — Constitutional Cabinet | `agents:Government` | `agents.owl` | The Government as defined by Article 28 of the Constitution — the collective executive body. Membership confined to holders of `members:CabinetMember` roles (Taoiseach, Tánaiste, Ministers). Also known informally as the Cabinet (`skos:altLabel "Cabinet"`). |
| 2 — Executive | `members:GovernmentExecutive` | `members.owl` | `agents:Government` plus `members:MinisterOfStateRole` role-holders. |
| 3 — Parliamentary Whip Bloc | `members:GovernmentBenches` | `members.owl` | `members:GovernmentExecutive` plus other OireachtasMembers under the Government whip. Disjoint with `members:Opposition`. Replaces the former `members:Government` (whip side). |

### Cabinet Role Classes

| Class | Superclass | Description |
|---|---|---|
| `members:CabinetMember` | `org:Role` | Abstract role in `agents:Government`. Subclasses: TaoiseachRole, TanaisteRole, MinisterRole. |
| `members:TaoiseachRole` | `:CabinetMember` | Role of Taoiseach (Head of Government). Disjoint with TanaisteRole. |
| `members:TanaisteRole` | `:CabinetMember` | Role of Tánaiste (Deputy Head of Government). Disjoint with TaoiseachRole. |
| `members:MinisterRole` | `:CabinetMember` | Ministerial office role. Person counterpart: `agents:Minister`. |
| `members:MinisterOfStateRole` | `org:Role` | Role of a Minister of State. Disjoint with CabinetMember. |

---

## Member Class Hierarchy

```
foaf:Person
└── agents:Member              — any Member of either House
    ├── agents:PrivateMember   — Member not in Government
    ├── agents:Minister        — Member holding a ministerial office (→ members:MinisterRole)
    └── (inferred via org:Role restrictions in members.owl)
        ├── members:OireachtasMember  — an elected role (≡ Deputy ∪ Senator)
        │   ├── members:Deputy        — inferred via DailMembership
        │   └── members:Senator       — inferred via SeanadMembership
```

`agents:PrivateSponsor` (`foaf:Agent`) covers non-Member persons or bodies who introduce legislation.

### Membership Record Classes

| Class | Superclass | Description |
|---|---|---|
| `members:OireachtasMembership` | `:MembersMembership` | Abstract superclass for house and committee membership records |
| `members:DailMembership` | `:OireachtasMembership` | Membership record for a specific Dáil term. Requires `inHouseTerm someValuesFrom agents:DailTerm`. Disjoint with SeanadMembership. |
| `members:SeanadMembership` | `:OireachtasMembership` | Membership record for a specific Seanad term. Requires `inHouseTerm someValuesFrom agents:SeanadTerm`. |
| `members:CabinetMembership` | `:MembersMembership` | Record of a Member holding a CabinetMember role in `agents:Government`. |
| `members:MinisterOfStateMembership` | `:MembersMembership` | Record of a Member holding a MinisterOfStateRole. |
| `members:CommitteeMembership` | `:MembersMembership` | Record of a Member's committee membership |

---

## Committee Structure

Committees are typed `members:Committee` (an `org:Organization`); they are not made enduring parliamentary bodies merely by being term-scoped committees.

### Committee Classification

Committees have two orthogonal classifications:

| Property | Range | Concept scheme | Members |
|---|---|---|---|
| `agents:hasCommitteeType` | `skos:Concept` | `agents:CommitteeTypeTable` | `:SelectCommitteeType`, `:JointCommitteeType`, `:SpecialCommitteeType` |
| `agents:hasCommitteePurpose` | `skos:Concept` | `agents:CommitteePurposeTable` | `:PolicyPurpose`, `:ShadowDepartmentPurpose` |

### Committee URIs

```
https://data.oireachtas.ie/ie/oireachtas/committee/{slug}/{term-no}
```

Where `{slug}` matches the segment in `debates[].uri` in the bill API and `{term-no}` is the Dáil/Seanad term number.

### Committee Role Classes

| Class | Superclass | Description |
|---|---|---|
| `members:Chair` | `org:Role` | Chair of a committee. Linked via `members:hasCommitteeRole` on a CommitteeMembership record. |
| `members:DeputyChair` | `org:Role` | Deputy Chair (Vice-Chair) of a committee. |

---

## Constituency Model

| Class | Superclass | Description |
|---|---|---|
| `members:Constituencies` | — | Abstract superclass for Dáil constituencies and Seanad panels. Each instance is scoped to a HouseTerm via `members:constituencyInHouseTerm`. `showAs` from the API maps to `skos:prefLabel` / `rdfs:label`. |
| `members:DailConstituency` | `:Constituencies`, `geo:SpatialThing` | A geographically bounded Dáil constituency (`representType = "constituency"`). Disjoint with SeanadPanel. URI: `…/house/dail/{houseNo}/constituency/{representCode}` |
| `members:SeanadPanel` | `:Constituencies` | A Seanad vocational or appointment panel (`representType = "panel"`). Disjoint with DailConstituency. URI: `…/house/seanad/{houseNo}/panel/{representCode}` |

---

## Bill Submitters

Bill submission is expressed via `eli-dl:was_submitted_by` on the `eli-dl:LegislativeProcess` instance, pointing to one of:

| Named individual | Type | When used |
|---|---|---|
| `<.../def/bill-source/government>` | `agents:GovernmentBillSource` | Bill introduced by the Government; controlled source concept, not a Government administration |
| `<.../def/bill-source/private-member>` | `agents:PrivateMember` | Bill introduced by a private Member |
| *(specific PrivateSponsor individual)* | `agents:PrivateSponsor` | Bill introduced by a non-Member sponsor |

The former `oir:BillSource` concept scheme and `oir:BillSource` class have been eliminated. See [Concept Schemes](Concept-Schemes) for details.

---

## Participation Roles

Activity-level participation (who moved a bill, who was rapporteur) is expressed via `eli-dl:had_participation` with a `eli-dl:Participation` individual carrying a `eli-dl:participation_role`.

| Named individual | Type | Purpose |
|---|---|---|
| `members:MoverRole` | `eli-dl:ParticipationRole` | The Member who moves a Bill, amendment, or motion. Replaces the former `agents:Mover` class. |
| `members:RapporteurRole` | `eli-dl:ParticipationRole` | A Member appointed as rapporteur. Alternatively use `eli-dl:had_responsible_person` as a shorthand. |

The boolean property `agents:isPrimarySponsor` (`xsd:boolean`) on `eli-dl:Participation` records whether a sponsor is the primary sponsor (`bill.sponsors[].sponsor.isPrimary` in the API).

---

## Eliminated Classes

| Former class | Reason | Replacement |
|---|---|---|
| `oir:BillSource` | Submitter type is expressed via `eli-dl:was_submitted_by` | `eli-dl:was_submitted_by` on `eli-dl:LegislativeProcess` |
| `oir:Mover` | Activity-level participation replaced by ELI-DL participation model | `eli-dl:had_participation` with `members:MoverRole` |
| `oir:Chamber` | Renamed to `agents:House` | `agents:House` |
| `oir:Cabinet` | Renamed / split into constitutional body + role | `agents:Government` (body) / `members:CabinetMember` (role) |
| `members:Member` | Replaced by canonical `agents:Member` | `agents:Member` |
| `members:Government` (whip side) | Renamed to avoid confusion with constitutional body | `members:GovernmentBenches` |
