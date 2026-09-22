## Ontology of Houses, Constituencies, Parties, Members and Member Roles

> **2026 update:** Substantial refactoring. `agents:Chamber` renamed to `agents:House`; `members:Cabinet` eliminated; three-tier Government model introduced; member class hierarchy restructured; `metalex:` and `rda:` superclasses removed. See the [ontology README](https://github.com/Oireachtas/ontology/blob/master/ontology/README.md) for the authoritative class and property reference. Further detail on the House/HouseTerm split is in [house_model.md](../house_model.md).
>
> For constitutional structures (Houses, Government tiers, Committees) and bill submitter/participation roles see also [Agents](Agents).

The [Organisation](https://www.w3.org/TR/vocab-org/) ontology is extensively reused to model the organisational and temporal components of the Houses of the Oireachtas, Members of the Houses and the roles they play, including in ministerial and committee positions.

### [Houses of the Oireachtas](#houses)

The modelling deliberately separates two distinct concepts of a "House":

- **The permanent institution** (`agents:House`) — Dáil Éireann or Seanad Éireann as a continuous constitutional body persisting across elections. Named individuals `<https://data.oireachtas.ie/house/dail>` and `<https://data.oireachtas.ie/house/seanad>` are the identifiers. Parliamentary committees are also `agents:House` instances.
- **A numbered sitting** (`agents:HouseTerm`) — a bounded parliamentary period, e.g. the 33rd Dáil (2020–2025). Subclasses `agents:DailTerm` and `agents:SeanadTerm` exist. Each `HouseTerm` is additionally typed `eli-dl:ParliamentaryTerm` so it can be referenced via `eli-dl:parliamentary_term` on activities and works.

The temporal date range (commencement and dissolution) is modelled via `dct:temporal` / `dct:PeriodOfTime` with `dcat:startDate` and `dcat:endDate`. See [mapping_notes.md](../mapping_notes.md) for a worked example.

#### [House URI patterns](#house-uri)

```
https://data.oireachtas.ie/house/dail                          — permanent Dáil institution
https://data.oireachtas.ie/house/seanad                        — permanent Seanad institution
https://data.oireachtas.ie/ie/oireachtas/house/dail/{no}       — a numbered Dáil term
https://data.oireachtas.ie/ie/oireachtas/house/seanad/{no}     — a numbered Seanad term
```

| Class | Example IRI | Describes |
|---|---|---|
| `agents:House` | `/house/dail` | Dáil Éireann as a continuous constitutional institution |
| `agents:House` | `/house/seanad` | Seanad Éireann as a continuous constitutional institution |
| `agents:DailTerm` | `/ie/oireachtas/house/dail/34` | The 34th Dáil |
| `agents:SeanadTerm` | `/ie/oireachtas/house/seanad/27` | The 27th Seanad |

#### [House and HouseTerm classes](#house-class)

| Class | Superclass(es) | Description |
|---|---|---|
| `agents:ParliamentaryBody` | `org:FormalOrganization` | Class of enduring parliamentary institutions; `<https://data.oireachtas.ie/oireachtas>` is the Oireachtas individual |
| `agents:House` | `agents:ParliamentaryBody` | Dáil or Seanad as a continuous constitutional institution |
| `agents:HouseTerm` | —; disjoint with `agents:ParliamentaryBody` | A bounded parliamentary sitting period, not an enduring organisation |
| `agents:DailTerm` | `agents:HouseTerm` | A specific numbered term of Dáil Éireann |
| `agents:SeanadTerm` | `agents:HouseTerm` | A specific numbered term of Seanad Éireann |
| `members:House` | `agents:House` | The two plenary houses as membership containers (`equivalentClass Dail ∪ Seanad`); excludes committees |
| `members:Dail` | `members:House` | Dáil membership-container class; not a Dáil term |
| `members:Seanad` | `members:House` | Seanad membership-container class; not a Seanad term |
| `members:Committee` | `org:Organization` | A parliamentary committee. URI pattern: `<https://data.oireachtas.ie/ie/oireachtas/committee/{slug}/{term-no}>` |

#### [House properties](#house-property)

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:hasTerm` | `agents:House` | `agents:HouseTerm` | `owl:inverseOf :termOf` |
| `:termOf` | `agents:HouseTerm` | `agents:House` | Links a term back to its persistent house |
| `:termNo` | `agents:HouseTerm` | `xsd:integer` | Sequential number (e.g. `34`) |
| `:houseCode` | `agents:HouseTerm` | `xsd:string` | E.g. `"dail"`, `"seanad"` |
| `:seats` | `agents:HouseTerm` | `xsd:integer` | Seat count for this term |
| `dct:temporal` | `agents:HouseTerm` | `dct:PeriodOfTime` | Links to a date range node with `dcat:startDate` / `dcat:endDate` |
| `skos:prefLabel` | `agents:HouseTerm` | `xsd:string` | E.g. `"34th Dáil"@en` |

### [Government structure](#government)

The Government is modelled across three tiers to reflect both constitutional and parliamentary realities:

| Tier | Class | Description |
|---|---|---|
| 1 | `agents:Government` | The constitutional executive body (Article 28). Membership confined to `members:CabinetMember` role-holders (Taoiseach, Tánaiste, Ministers). |
| 2 | `members:GovernmentExecutive` | `agents:Government` plus `members:MinisterOfStateRole` holders. |
| 3 | `members:GovernmentBenches` | `members:GovernmentExecutive` plus other OireachtasMembers under the government whip. Replaces the former `members:Government` (whip side). |

The former `members:Cabinet` class (a subclass of the whip side — architecturally incorrect) has been eliminated. Use `agents:Government` for the constitutional Cabinet.

Enduring Government URI: `<https://data.oireachtas.ie/government>` — typed `agents:Government`, accountable to enduring Dáil. The separate `<https://data.oireachtas.ie/ie/oireachtas/def/bill-source/government>` is `agents:GovernmentBillSource`.

#### Role classes

| Class | Superclass(es) | Description |
|---|---|---|
| `members:CabinetMember` | `org:Role` | Abstract role in `agents:Government`; subclasses below |
| `members:TaoiseachRole` | `members:CabinetMember` | Role of Taoiseach |
| `members:TanaisteRole` | `members:CabinetMember` | Role of Tánaiste. `owl:disjointWith TaoiseachRole` |
| `members:MinisterRole` | `members:CabinetMember` | Ministerial office role. Counterpart person class: `agents:Minister` |
| `members:MinisterOfStateRole` | `org:Role` | Role of Minister of State. `owl:disjointWith CabinetMember` |

### [Members of the Oireachtas](#members)

Members of the Oireachtas are modelled using `foaf:Person` for biographical details and the Organisation ontology for temporal roles such as Deputy or Senator, minister or committee member.

#### [Member URI patterns](#member-uri)

```
https://data.oireachtas.ie/ie/oireachtas/member/{firstname}-{opt middle name}-{last name}.{D|S}.{xs:date}
```

| Class | Example IRI | Describes |
|---|---|---|
| `agents:Member` | `/ie/oireachtas/member/Enda-Kenny.D.1975-11-12` | Enda Kenny, Member of the Oireachtas |
| `members:DailMembership` | `/ie/oireachtas/member/Enda-Kenny.D.1975-11-12/dail/31` | Enda Kenny's membership of the 31st Dáil |
| `members:CabinetMembership` | `member/Enda-Kenny.D.1975-11-12/cabinet/dail/31` | Enda Kenny's Cabinet membership (31st Dáil) |

#### [Member Classes](#member-class)

| Class | Superclass(es) | Description |
|---|---|---|
| `agents:Member` | `foaf:Person` | Any person who is or was a Member of the Oireachtas |
| `agents:Minister` | `agents:Member` | A Member who also holds a ministerial office. Linked to `members:MinisterRole` via `org:holds` / `org:heldBy` |
| `agents:PrivateMember` | `agents:Member` | A Member who is not a Member of Government |
| `agents:PrivateSponsor` | `foaf:Agent` | A non-Member person or body that introduces legislation |
| `members:OireachtasMember` | `org:Role` | An elected  role — `equivalentClass Deputy ∪ Senator` |
| `members:Deputy` | `members:OireachtasMember` | Member elected to the Dáil |
| `members:Senator` | `members:OireachtasMember` | Member of the Seanad |
| `members:GovernmentBenches` | `members:SidesOfHouse` | The parliamentary whip bloc supporting the Government; `owl:disjointWith Opposition` |
| `members:Opposition` | `members:SidesOfHouse` | The opposition |

#### [Membership Classes](#membership-class)

| Class | Superclass(es) | Description |
|---|---|---|
| `members:OireachtasMembership` | `members:MembersMembership` | Abstract superclass for house and committee membership records |
| `members:DailMembership` | `members:OireachtasMembership` | Membership record for a specific Dáil term. `owl:disjointWith SeanadMembership` |
| `members:SeanadMembership` | `members:OireachtasMembership` | Membership record for a specific Seanad term |
| `members:CabinetMembership` | `members:MembersMembership` | Record of holding a `members:CabinetMember` role in the enduring constitutional Government; its holder must also have an OireachtasMembership |
| `members:MinisterOfStateMembership` | `members:MembersMembership` | Record of holding a `members:MinisterOfStateRole` |
| `members:CommitteeMembership` | `members:MembersMembership` | Membership of a committee |

#### [Constituency Classes](#constituency-class)

| Class | Superclass(es) | Description |
|---|---|---|
| `members:Constituencies` | — | Abstract superclass for Dáil constituencies and Seanad panels |
| `members:DailConstituency` | `members:Constituencies`, `geo:SpatialThing` | A geographically bounded Dáil constituency. URI: `…/house/dail/{no}/constituency/{representCode}`. `owl:disjointWith SeanadPanel` |
| `members:SeanadPanel` | `members:Constituencies` | A Seanad vocational or appointment panel. URI: `…/house/seanad/{no}/panel/{representCode}` |

#### [Member properties](#member-property)

| Property | Domain | Range | Notes |
|---|---|---|---|
| `foaf:familyName` | `agents:Member` | `xsd:string` | |
| `foaf:firstName` | `agents:Member` | `xsd:string` | |
| `foaf:name` | `agents:Member` | `xsd:string` | |
| `:memberCode` | `agents:Member` | `xsd:string` | Unique member code from the API, e.g. `'Timmy-Dooley.S.2002-09-12'` |
| `:pId` | `agents:Member` | `xsd:string` | Short parliamentary identifier slug, e.g. `'TimDooley'` |
| `:gender` | `agents:Member` | `xsd:string` | Gender as reported by the API |
| `:dateOfDeath` | `agents:Member` | `xsd:dateTime` | Date of death where known |
| `:wikiTitle` | `agents:Member` | `xsd:string` | Wikipedia article title |
| `:hasImage` | `agents:Member` | `xsd:boolean` | `true` if the API has an image available |
| `:elected` | `time:TemporalEntity` | `:EventDate` | Date of election |
| `:isOireachtasMembershipOf` | `members:OireachtasMembership` | `agents:House` | The continuous house (`<.../house/dail>`) |
| `:inHouseTerm` | `members:OireachtasMembership` | `agents:HouseTerm` | The specific numbered term |
| `members:constituencyInHouseTerm` | `members:Constituencies` | `agents:HouseTerm` | Sub-property of `members:inHouseTerm`; links constituency/panel to its term |
| `members:partyCode` | `members:PartyGrouping` | `xsd:string` | Short party code from the API, e.g. `'Fianna_Fáil'` |
| `members:representCode` | `members:Constituencies` | `xsd:string` | Short constituency/panel code, e.g. `'Clare'`, `'Administrative-Panel'` |
| `:committeeCode` | `members:Committee` | `xsd:string` | Short alphanumeric committee code, e.g. `'CAJ'` |
| `:committeeID` | `members:Committee` | `xsd:integer` | Numeric committee identifier |
| `:hasCommitteeRole` | `members:CommitteeMembership` | `org:Role` | Role held within the committee (`:Chair`, `:DeputyChair`); absent when no special role |
| `:officeNameUri` | `members:MinisterOfStateMembership` | IRI | Dereferenceable IRI of the ministerial office name from the API |
