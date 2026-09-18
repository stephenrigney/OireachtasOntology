## Oireachtas Ontology — Structure and Contents

The ontology is split into six sub-ontologies, each covering one of the four declared areas of the Oireachtas ontology, plus a shared controlled vocabulary layer and a detailed membership model. A root umbrella file imports all six.

---

### File Overview

| File | Ontology IRI | Description |
|---|---|---|
| [oireachtas.owl.ttl](oireachtas.owl.ttl) | `https://data.oireachtas.ie/ontology` | Root umbrella — imports the six sub-ontologies below |
| [agents.owl.ttl](agents.owl.ttl) | `https://data.oireachtas.ie/ontology/agents` | Persons, roles and organisations |
| [events.owl.ttl](events.owl.ttl) | `https://data.oireachtas.ie/ontology/events` | Journal events, bill stages and procedural outcomes |
| [legislation.owl.ttl](legislation.owl.ttl) | `https://data.oireachtas.ie/ontology/legislation` | Legislative documents, versions and statuses |
| [members.owl.ttl](members.owl.ttl) | `https://data.oireachtas.ie/ontology/members` | Membership, roles, party groupings and government tiers |
| [vocabulary.owl.ttl](vocabulary.owl.ttl) | `https://data.oireachtas.ie/ontology/vocabulary` | SKOS controlled vocabularies (concept schemes) |
| [debates.owl.ttl](debates.owl.ttl) | `https://data.oireachtas.ie/ontology/debates` | Official Report and debates — Akoma Ntoso structure, speeches, divisions and participation |

---

### Import Chain

```
oireachtas.owl
├── agents.owl
│   └── (imports: ELI, ELI-DL, W3C org)
├── events.owl
│   └── (imports: agents.owl, ELI-DL, W3C time)
├── legislation.owl
│   └── (imports: events.owl, ELI, ELI-DL)
├── members.owl
│   └── (imports: agents.owl, ELI-DL, W3C org, FOAF)
├── vocabulary.owl
│   └── (imports: events.owl, legislation.owl)
└── debates.owl
    └── (imports: events.owl, agents.owl, ELI-DL)
```

---

### Naming Conventions

| Kind | Convention | Examples |
|---|---|---|
| Classes | UpperCamelCase | `:HouseTerm`, `:BillEvent`, `:DailMembership` |
| Object properties | lowerCamelCase | `:inHouse`, `:hasTerm`, `:isPartyMembershipOf` |
| Datatype properties | lowerCamelCase | `:memberCode`, `:progressStage`, `:legislativeYear` |
| Named individuals — concept-scheme members | UpperCamelCase | `:FirstStage`, `:EnactedBill`, `:PublicBill` |
| Named individuals — singleton instances | lowerCamelCase path segment (IRI) or UpperCamelCase local name | `<.../house/dail>`, `:MoverRole`, `:Independent` |

---

### agents.owl

**IRI:** `https://data.oireachtas.ie/ontology/agents`

Defines the organisations, roles and persons involved in the legislative process.

> **ELI-DL alignment (2026):** `eli-dl` import added. `:BillSource` class and `:Mover` class eliminated. `:Government`, `:PrivateMember` and `:PrivateSponsor` no longer subclasses of `:BillSource`. Canonical submitter linking now via `eli-dl:was_submitted_by`. Activity-level participation (e.g. who moved a bill) now via `eli-dl:had_participation` with `eli-dl:ParticipationRole` individuals defined in `members.owl`.
>
> **Namespace reconciliation (2026):** `foaf:Person` added as second superclass on `:Member` alongside `rda:C10004` (required for ELI-DL `eli:Person` range entailment via `eli:Person rdfs:subClassOf foaf:Person`).
>
> **RDA cleanup (2026):** `rda:C10005` removed as superclass of `:Oireachtas` (retains `org:FormalOrganization`). `rda:C10004` removed as superclass of `:Member` (retains `foaf:Person`, the direct superclass satisfying ELI-DL entailments). `rda:C10004` + `rda:C10005` removed from `:PrivateSponsor` (replaced with `foaf:Agent` — the common FOAF supertype covering both individual and corporate sponsors; already in the import chain via ELI-DL). The RDA namespace is no longer referenced anywhere in the ontology.
>
> **House / HouseTerm refactoring (2026):** `:Chamber` renamed to `:House` (continuous constitutional institution). Former `:House` (bounded sitting period) renamed to `:HouseTerm`. Two disjoint subclasses `:DailTerm` and `:SeanadTerm` added under `:HouseTerm`. Named individuals `<.../house/dail>` and `<.../house/seanad>` now typed `:House`. The `:hasTerm` / `:termOf` property pair updated accordingly.
>
> **Government three-tier refactoring (2026):** `:Government` gains `skos:altLabel "Cabinet"@en` and an updated `rdfs:comment` explaining the constitutional basis and three-tier structure. See `members.owl` for the new `:GovernmentBenches`, `:GovernmentExecutive` and `:MinisterOfState` classes.
>
> **bill.json alignment (2026):** Named individuals `<.../def/bill-source/government>` (typed `:Government`) and `<.../def/bill-source/private-member>` (typed `:PrivateMember`) added using the API `def/` URIs directly as IRIs, so `eli-dl:was_submitted_by` can point straight at the dereferenceable URI from the JSON. `:hasCommitteeType` object property added (domain `members:Committee`, range `skos:Concept`). Committee type individuals `:SelectCommitteeType`, `:JointCommitteeType`, `:SpecialCommitteeType` added as `eli-dl:ProcessType` + `skos:Concept` members of `:CommitteeTypeTable`. URI pattern convention for committee instances annotated on `members:Committee`.
>
> **member.json alignment (2026):** Six person-level datatype properties added on `:Member`: `:memberCode`, `:pId`, `:gender` (plain `xsd:string`), `:dateOfDeath` (`xsd:dateTime`), `:wikiTitle`, `:hasImage` (`xsd:boolean`). `:hasCommitteePurpose` object property added (domain `members:Committee`, range `skos:Concept`, range from `:CommitteePurposeTable`). Purpose concept individuals `:PolicyPurpose` and `:ShadowDepartmentPurpose` added as `skos:Concept` members of `:CommitteePurposeTable`. `members:Committee` annotation updated to reference both `:hasCommitteeType` and `:hasCommitteePurpose`.
>
> **houses.json alignment (2026):** Two new datatype properties added on `:HouseTerm`: `:seats` (`xsd:integer`, term-specific seat count) and `dct:temporal` (annotated imported property linking a `:HouseTerm` to a `dct:PeriodOfTime` node). Auxiliary class `dct:PeriodOfTime` declared; `dcat:startDate` and `dcat:endDate` (`xsd:dateTime`) declared as auxiliary datatype properties on `dct:PeriodOfTime` for the commencement and dissolution dates respectively. `dcat:endDate` is omitted when the term is the current sitting term (null `dateRange.end` in the API). `@prefix dcat:` added. `:houseCode` comment updated to note that the API's `chamberCode` and `houseType` fields are duplicates of `houseCode` and should be discarded during conversion.

#### Classes

| Class | Superclass(es) | Description |
|---|---|---|
| `:Oireachtas` | `org:FormalOrganization` | The Houses of the Oireachtas as a legislative body |
| `:House` | `:Oireachtas` | Dáil Éireann or Seanad Éireann as a continuous constitutional institution, persisting across successive terms. Named individuals `<.../house/dail>` and `<.../house/seanad>` are instances. Committee chambers are also instances. |
| `:HouseTerm` | `:Oireachtas` | A bounded parliamentary sitting period. Instances should additionally be typed as `eli-dl:ParliamentaryTerm` to enable use of `eli-dl:parliamentary_term` on activities and works. |
| `:DailTerm` | `:HouseTerm` | A specific numbered term of Dáil Éireann (e.g. the 33rd Dáil). Disjoint with `:SeanadTerm`. |
| `:SeanadTerm` | `:HouseTerm` | A specific numbered term of Seanad Éireann. |
| `:Government` | `:Oireachtas` | The Government as defined by Article 28 of the Constitution — the collective executive body with legal personality. Also known informally as the Cabinet (`skos:altLabel "Cabinet"`). Membership confined to persons holding a `members:CabinetMember` role (`members:Taoiseach`, `members:Tanaiste` or `members:Minister`). |
| `:Member` | `foaf:Person` | A Member of one of the Houses. Canonical class replacing the former `members:Member`. `foaf:Person` is the direct superclass — satisfies ELI-DL `eli:Person` range entailment via `eli:Person rdfs:subClassOf foaf:Person`. |
| `:Minister` | `:Member` | A Member who also holds a ministerial office. Cross-referenced to `members:MinisterRole` via `org:holds` / `org:heldBy` bridge axioms in `members.owl`. |
| `:PrivateMember` | `:Member` | A Member who is not a Member of Government |
| `:PrivateSponsor` | `foaf:Agent` | A non-Member person or body that introduces legislation. `foaf:Agent` is the common FOAF supertype of `foaf:Person` (individual sponsors) and `foaf:Organization` (corporate bodies). |

#### Eliminated classes

| Former class | Reason | Replacement |
|---|---|---|
| `:BillSource` | Submitter type is expressed via `eli-dl:was_submitted_by` (Process → Agent) | Use `eli-dl:was_submitted_by` on `eli-dl:LegislativeProcess` instances |
| `:Mover` | Activity-level participation is expressed via `eli-dl:Participation` + `eli-dl:ParticipationRole` | Use `eli-dl:had_participation` with `:MoverRole` (defined in `members.owl`) |

#### Object Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:hasTerm` | `:House` | `:HouseTerm` | `owl:inverseOf :termOf` |
| `:termOf` | `:HouseTerm` | `:House` | |
| `:hasCommitteeType` | `members:Committee` | `skos:Concept` | Committee structural type drawn from `:CommitteeTypeTable`; members `:SelectCommitteeType`, `:JointCommitteeType`, `:SpecialCommitteeType` |
| `:hasCommitteePurpose` | `members:Committee` | `skos:Concept` | Committee functional purpose drawn from `:CommitteePurposeTable`; members `:PolicyPurpose`, `:ShadowDepartmentPurpose` |

#### Datatype Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:isPrimarySponsor` | `eli-dl:Participation` | `xsd:boolean` | `true` for the primary bill sponsor; false/absent for secondary sponsors |
| `:memberCode` | `:Member` | `xsd:string` | Unique member code from the API (e.g. `'Timmy-Dooley.S.2002-09-12'`); typically derivable from the member IRI |
| `:pId` | `:Member` | `xsd:string` | Short parliamentary identifier slug used internally in the Oireachtas system (e.g. `'TimDooley'`) |
| `:gender` | `:Member` | `xsd:string` | Gender as reported by the API; plain string literal |
| `:dateOfDeath` | `:Member` | `xsd:dateTime` | Date of death where known; `xsd:dateTime` used for OWL 2 DL compatibility |
| `:wikiTitle` | `:Member` | `xsd:string` | Wikipedia article title; can be used to construct a Wikipedia or DBpedia URI |
| `:hasImage` | `:Member` | `xsd:boolean` | `true` if the API has an image available; presence flag only, not a URI |
| `:seats` | `:HouseTerm` | `xsd:integer` | Number of seats in this term. Term-specific (e.g. 33rd Dáil: 160; 34th Dáil: 174). Corresponds to `house.seats` in the houses API. |
| `dcat:startDate` *(auxiliary)* | `dct:PeriodOfTime` | `xsd:dateTime` | Commencement date of the term. Set on the `dct:PeriodOfTime` node linked via `dct:temporal`. `xsd:dateTime` used for OWL 2 DL compatibility. Corresponds to `house.dateRange.start`. |
| `dcat:endDate` *(auxiliary)* | `dct:PeriodOfTime` | `xsd:dateTime` | Dissolution date of the term. Absent when the term is the current sitting term (null `house.dateRange.end`). `xsd:dateTime` used for OWL 2 DL compatibility. |

#### Annotations on imported properties

| Property | Annotation |
|---|---|
| `eli:passed_by` | Range restricted to `:Oireachtas` |
| `eli-dl:was_submitted_by` | Documents that range includes `:Government`, `:PrivateMember`, `:PrivateSponsor`; replaces `:BillSource` |
| `eli-dl:had_participation` | Documents use with `:MoverRole` / `:RapporteurRole` on `:JournalEvent` activities; replaces `:Mover` |
| `members:Committee` | URI pattern for instances: `<https://data.oireachtas.ie/ie/oireachtas/committee/{slug}/{term-no}>`; `{slug}` matches the segment in `debates[].uri` in the bill API. Structural type via `:hasCommitteeType`; functional purpose via `:hasCommitteePurpose` |
| `dct:temporal` | Use on `:HouseTerm` instances to link to a `dct:PeriodOfTime` node representing the term's sitting date range. On the node use `dcat:startDate` (commencement) and `dcat:endDate` (dissolution; absent for the current term). Corresponds to `house.dateRange` in the houses API. |

#### Named Individuals

| Individual | Type | Label |
|---|---|---|
| `<.../house/dail>` | `:House` | Dáil Éireann |
| `<.../house/seanad>` | `:House` | Seanad Éireann |
| `<.../def/bill-source/government>` | `:Government` | The Government; target of `eli-dl:was_submitted_by` when `bill.sourceURI` = Government |
| `<.../def/bill-source/private-member>` | `:PrivateMember` | Private Member; target of `eli-dl:was_submitted_by` when `bill.sourceURI` = Private Member |
| `:SelectCommitteeType` | `skos:Concept` | Select Committee — member of `:CommitteeTypeTable` |
| `:JointCommitteeType` | `skos:Concept` | Joint Committee — member of `:CommitteeTypeTable` |
| `:SpecialCommitteeType` | `skos:Concept` | Special Committee — member of `:CommitteeTypeTable` |
| `:PolicyPurpose` | `skos:Concept` | Policy — member of `:CommitteePurposeTable` |
| `:ShadowDepartmentPurpose` | `skos:Concept` | Shadow Department — member of `:CommitteePurposeTable` |

---

### members.owl

**IRI:** `https://data.oireachtas.ie/ontology/members`

Defines the detailed membership, role and party structures of the Houses of the Oireachtas. Covers Deputies, Senators, Cabinet membership, committee membership, party groupings and parliamentary titles.

> **ELI-DL alignment (2026):** `eli-dl` import added. `org:Role rdfs:subClassOf :OireachtasMember` axiom corrected to `:OireachtasMember rdfs:subClassOf org:Role`. `:MoverRole` and `:RapporteurRole` added as `eli-dl:ParticipationRole` individuals.
>
> **Namespace reconciliation (2026, in progress):** `members.owl` now imports `agents.owl`. The `members:Member` class has been eliminated — all references replaced with `agents:Member` (the canonical class). `members:Government` (whip side) resolved by rename — see three-tier Government refactoring note below. `HousesOfTheOireachtas` resolved — `:House`, `:Committee` and `:GovernmentExecutive` now use `agents:Oireachtas` as their named superclass. Remaining duplicate: Minister person vs role.
>
> **House / HouseTerm refactoring (2026):** `members:Chamber` renamed to `members:House`. One-way bridge `members:House rdfs:subClassOf agents:House` added. `members:Dail` and `members:Seanad` gain `agents:DailTerm` and `agents:SeanadTerm` as additional superclasses respectively. `:DailMembership` and `:SeanadMembership` added as disjoint subclasses of `:OireachtasMembership`. `:inHouseTerm` property added (range `agents:HouseTerm`) alongside the re-ranged `:isOireachtasMembershipOf` (range `agents:House`). `Deputy owl:disjointWith Senator` removed from person level; disjointness now expressed via `DailMembership owl:disjointWith SeanadMembership`. Spurious `:Dail` and `:Seanad` superclasses removed from `:DailConstituency` and `:SeanadPanel` respectively.
>
> **Government three-tier refactoring (2026):** `members:Government` (whip side) renamed to `members:GovernmentBenches`. Former vestigial `members:Cabinet` class (incorrectly a subclass of the whip side) removed — the constitutional Cabinet is `agents:Government`. Three tiers now defined: (1) `agents:Government` — constitutional executive body, membership confined to `members:CabinetMember` role-holders (TaoiseachRole, TanaisteRole, MinisterRole); (2) `members:GovernmentExecutive` — Government plus `members:MinisterOfStateRole` role-holders; (3) `members:GovernmentBenches` — GovernmentExecutive plus other OireachtasMembers under the government whip. `members:MinisterOfStateRole` and `members:MinisterOfStateMembership` added; `MinisterOfStateRole owl:disjointWith CabinetMember`. `:isHeadOf` and `:isDeputyHeadOf` re-ranged to `agents:Government`. Four sub-properties added: `:isHeadOfExecutive`, `:isHeadOfBenches` (sub-properties of `:isHeadOf`, domain `:TaoiseachRole`) and `:isDeputyHeadOfExecutive`, `:isDeputyHeadOfBenches` (sub-properties of `:isDeputyHeadOf`, domain `:TanaisteRole`) to assert headship at each wider tier. `:PartyInGovernment` allValuesFrom updated to `members:GovernmentBenches`.
>
> **Role class rename (2026):** All four `members` role classes renamed for unambiguous person/role distinction: `members:Minister` → `members:MinisterRole`, `members:Taoiseach` → `members:TaoiseachRole`, `members:Tanaiste` → `members:TanaisteRole`, `members:MinisterOfState` → `members:MinisterOfStateRole`. `org:holds` / `org:heldBy` bridge axioms added in `members.owl` connecting `agents:Minister` (person) ↔ `members:MinisterRole` (role). `rdfs:comment` added to `agents:Minister` cross-referencing the bridge.
>
> **bill.json alignment (2026):** `:isPrimarySponsor` datatype property (`xsd:boolean`) added on `eli-dl:Participation` to capture the `sponsors[].sponsor.isPrimary` flag. Set `true` on the primary sponsor's participation instance.
>
> **member.json alignment (2026):** `:DeputyChair` class added (`org:Role` subclass, companion to `:Chair`). `:hasCommitteeRole` object property added on `:CommitteeMembership` (range `org:Role`) to record the role a member holds within a committee. `:partyCode`, `:representCode`, `:committeeCode` (all `xsd:string`) and `:committeeID` (`xsd:integer`) datatype properties added for API short-code identifiers on `:PartyGrouping`, `:Constituencies` and `:Committee` respectively. `:officeNameUri` object property added on `:MinisterOfStateMembership` to link to the dereferenceable office IRI when provided by the API.
>
> **constituencies.json alignment (2026):** `:constituencyInHouseTerm` object property added as a sub-property of `:inHouseTerm` (domain `:Constituencies`, range `agents:HouseTerm`) to reflect the term-scoped URI structure of the Oireachtas constituencies API (`constituencyOrPanel.uri` embeds the `houseNo`). `owl:disjointWith` added between `:DailConstituency` and `:SeanadPanel`, consistent with the disjointness pattern used for `:DailMembership`/`:SeanadMembership` and `agents:DailTerm`/`agents:SeanadTerm`. `rdfs:comment` added to `:Constituencies`, `:DailConstituency` and `:SeanadPanel` documenting URI patterns, `representType` → subclass mapping, and `showAs` → `skos:prefLabel` mapping.

#### Classes (selected)

| Class | Superclass(es) | Description |
|---|---|---|
| `:OireachtasMember` | `org:Role`, `agents:Member` (inferred) | An elected role — equivalentClass `Deputy ∪ Senator`; inferred as subclass of `agents:Member` via intersection expressions |
| `:Deputy` | `:OireachtasMember` | Member elected to the Dáil. Inferred for any `agents:Member` who has a `:DailMembership` record. A person may be both a Deputy and a Senator across their career. |
| `:Senator` | `:OireachtasMember` | Member of the Seanad. Inferred via `:SeanadMembership`. |
| `:MinisterRole` | `:CabinetMember` | Ministerial office role in `agents:Government`. `skos:prefLabel "Minister"`. Counterpart person class: `agents:Minister`. |
| `:TaoiseachRole` | `:CabinetMember` | Role of Taoiseach (Head of Government). `owl:disjointWith :TanaisteRole`. |
| `:TanaisteRole` | `:CabinetMember` | Role of Tánaiste (Deputy Head of Government). `owl:disjointWith :TaoiseachRole`. |
| `:CabinetMember` | `org:Role` | Abstract role in `agents:Government`. Subclasses: `:TaoiseachRole`, `:TanaisteRole`, `:MinisterRole`. Holders must be `:OireachtasMembers`. |
| `:MinisterOfStateRole` | `org:Role` | Role of a Minister of State. `owl:disjointWith :CabinetMember`. Holder must be an `:OireachtasMember`. |
| `:GovernmentExecutive` | `agents:Oireachtas` | The wider executive — `agents:Government` (TaoiseachRole, TanaisteRole, MinisterRole holders) plus MinisterOfStateRole holders. OWL restriction: `hasMembers allValuesFrom (CabinetMembership ∪ MinisterOfStateMembership)`. |
| `:GovernmentBenches` | `:SidesOfHouse` | The parliamentary whip bloc supporting the Government. Comprises `:GovernmentExecutive` members plus other OireachtasMembers under the government whip. `owl:disjointWith :Opposition`. Replaces the former `:Government` (whip side). |
| `:Opposition` | `:SidesOfHouse` | The opposition |
| `:House` | `agents:Oireachtas`, `agents:House` | equivalentClass `Dail ∪ Seanad`. Plenary houses only; committee chambers are `agents:House` instances outside this extension. One-way bridge to `agents:House`. |
| `:Dail` | `:House`, `agents:DailTerm` | Dáil Éireann as a membership container. Bridge to `agents:DailTerm` enables term-level typing. |
| `:Seanad` | `:House`, `agents:SeanadTerm` | Seanad Éireann as a membership container. |
| `:Committee` | `agents:Oireachtas` | A parliamentary committee |
| `:PartyGrouping` | `foaf:Group` | Superclass of `:Party`; `:Independent` is a separate general named individual. Term-scoped API party records retain their source IRIs and are not linked to it. |
| `:OireachtasMembership` | `:MembersMembership` | Abstract superclass for house and committee membership records |
| `:DailMembership` | `:OireachtasMembership` | Membership record for a specific Dáil term. Requires `inHouseTerm someValuesFrom agents:DailTerm`. Disjoint with `:SeanadMembership`. |
| `:SeanadMembership` | `:OireachtasMembership` | Membership record for a specific Seanad term. Requires `inHouseTerm someValuesFrom agents:SeanadTerm`. |
| `:CabinetMembership` | `:MembersMembership` | Record of an `agents:Member` holding a `:CabinetMember` role (`:TaoiseachRole`, `:TanaisteRole` or `:MinisterRole`) in `agents:Government`. Linked to role via `:hasCabinetRole`. |
| `:MinisterOfStateMembership` | `:MembersMembership` | Record of an `agents:Member` holding a `:MinisterOfStateRole`. Linked to role via `:hasMinisterOfStateRole`. |
| `:CommitteeMembership` | `:MembersMembership` | Membership of a committee |
| `:DateRange` | `:Temporal` | Temporal extent for org:Membership subclasses; start/end typed `xsd:dateTime` (note: `xsd:date` is not in the OWL 2 DL datatype map) |
| `:Chair` | `org:Role` | Role of Chair of a committee. Used via `:hasCommitteeRole` on `:CommitteeMembership` records. |
| `:DeputyChair` | `org:Role` | Role of Deputy Chair (Vice-Chair) of a committee. Used via `:hasCommitteeRole` on `:CommitteeMembership` records. |
| `:Constituencies` | — | Abstract superclass for Dáil constituencies and Seanad panels. Each instance is scoped to a specific `:HouseTerm` via `:constituencyInHouseTerm`. `showAs` from the API maps to `skos:prefLabel` / `rdfs:label`. |
| `:DailConstituency` | `:Constituencies`, `geo:SpatialThing` | A geographically bounded Dáil constituency (`representType = "constituency"`). URI pattern: `…/house/dail/{houseNo}/constituency/{representCode}`. `owl:disjointWith :SeanadPanel`. |
| `:SeanadPanel` | `:Constituencies` | A Seanad vocational or appointment panel (`representType = "panel"`; no geographic extent). URI pattern: `…/house/seanad/{houseNo}/panel/{representCode}`. `owl:disjointWith :DailConstituency`. |

#### Object Properties (selected)

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:isOireachtasMembershipOf` | `:OireachtasMembership` | `agents:House` | The continuous house (`<.../house/dail>`) |
| `:inHouseTerm` | `:OireachtasMembership` | `agents:HouseTerm` | The specific numbered term (`<.../house/dail/33>`); same individual as `eli-dl:parliamentary_term` on associated activities |
| `:constituencyInHouseTerm` | `:Constituencies` | `agents:HouseTerm` | Sub-property of `:inHouseTerm`; links a `:DailConstituency` or `:SeanadPanel` instance to the term for which it exists. Reflects the term-scoped URI structure of the constituencies API. |
| `:isHeadOf` | `:TaoiseachRole` | `agents:Government` | Links a TaoiseachRole instance to the constitutional Government it heads |
| `:isHeadOfExecutive` | `:TaoiseachRole` | `:GovernmentExecutive` | Sub-property of `:isHeadOf`; asserts headship of the wider executive (Government + Ministers of State) |
| `:isHeadOfBenches` | `:TaoiseachRole` | `:GovernmentBenches` | Sub-property of `:isHeadOf`; asserts headship of the full parliamentary whip bloc |
| `:isDeputyHeadOf` | `:TanaisteRole` | `agents:Government` | Links a TanaisteRole instance to the constitutional Government |
| `:isDeputyHeadOfExecutive` | `:TanaisteRole` | `:GovernmentExecutive` | Sub-property of `:isDeputyHeadOf`; asserts deputy headship of the GovernmentExecutive |
| `:isDeputyHeadOfBenches` | `:TanaisteRole` | `:GovernmentBenches` | Sub-property of `:isDeputyHeadOf`; asserts deputy headship of the GovernmentBenches |
| `:hasMinisterOfStateRole` | `:MinisterOfStateMembership` | `:MinisterOfStateRole` | Links a membership record to the specific MinisterOfStateRole held |
| `:hasCommitteeRole` | `:CommitteeMembership` | `org:Role` | The role held by the member within the committee (`:Chair`, `:DeputyChair`); absent when no special role |
| `:officeNameUri` | `:MinisterOfStateMembership` | (IRI) | Links to the dereferenceable IRI of the named ministerial office when provided by the API (`office.officeName.uri`) |

#### Datatype Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:partyCode` | `:PartyGrouping` | `xsd:string` | Short party code from the API (e.g. `'Fianna_Fáil'`) |
| `:representCode` | `:Constituencies` | `xsd:string` | Short constituency/panel code from the API (e.g. `'Clare'`, `'Administrative-Panel'`) |
| `:committeeCode` | `:Committee` | `xsd:string` | Short alphanumeric committee code from the API (e.g. `'CAJ'`, `'CC2'`) |
| `:committeeID` | `:Committee` | `xsd:integer` | Numeric committee identifier from the API |

#### Named Individuals — ELI-DL Participation Roles

| Individual | Type | Purpose |
|---|---|---|
| `:MoverRole` | `eli-dl:ParticipationRole` | Role of a Member who moves a Bill, amendment or motion. Set via `eli-dl:participation_role` on `eli-dl:Participation` instances. Replaces the former `agents:Mover` class. |
| `:RapporteurRole` | `eli-dl:ParticipationRole` | Role of a Member appointed as rapporteur. Set via `eli-dl:participation_role`; see also `eli-dl:had_responsible_person` for the shorthand property. |

---

### Future Work

| Item | Description |
|---|---|
| ~~RDA usage — `:PrivateSponsor`~~ | **Resolved (2026).** `rda:C10004` and `rda:C10005` replaced with `foaf:Agent` on `agents:PrivateSponsor`. The RDA namespace (`http://rdaregistry.info/Elements/c/`) is no longer referenced anywhere in the ontology. `rda:` row removed from Referenced External Schemas. |
| Named individual IRI path | Decide whether continuous-house individual IRIs use the short form `<https://data.oireachtas.ie/house/dail>` (current) or the API-path form `<https://data.oireachtas.ie/ie/oireachtas/house/dail>`. Relevant only when the data conversion layer is built. |
| Committee operational lifespan | Add `:hasCommitteeDateRange` property on `:Committee` to record the committee's own operational date range (`committee.committeeDateRange`), distinct from the member's `memberDateRange` already covered by `:hasMembershipDateRange`. |
| Committee lifecycle status | Add `CommitteeStatusTable` concept scheme with members `Active` / `Archived` / etc. to map `committee.status` and `committee.mainStatus` fields. |
| Committee expiry type | Add `CommitteeExpiryTable` concept scheme with members `Sessional` / `Special` etc. to map `committee.expiryType`. |
| Committee time-bounded names | `committee.committeeName` is an array of names each with a validity `dateRange`. Modelling this requires a reification pattern — e.g. a `:CommitteeName` class with `:nameEn`, `:nameGa` and `:hasMembershipDateRange`. Architecturally non-trivial; deferred. |
| Named ministerial office individuals | `office.officeName.uri` currently mapped via bare IRI link (`:officeNameUri`). A future extension could define typed named individuals for each ministerial office (portfolio + department), enabling richer querying. |

---

### events.owl

**IRI:** `https://data.oireachtas.ie/ontology/events`

Defines the procedural events that occur during a Bill's lifecycle, including stages, delivery methods and outcomes.

> **bill.json alignment (2026):** `:progressStage` and `:stageNo` datatype properties represent cross-house stage ordering and per-house amendment list stage number. `stageURI` maps a concrete stage occurrence to the corresponding controlled individual via both `eli-dl:occured_at_stage` and `eli-dl:had_activity_type`; those controlled stage values are `eli-dl:ProcessStage` and `eli-dl:ActivityType` concepts. `eventURI` and `methodURI` map through `eli-dl:had_activity_type` to controlled `eli-dl:ActivityType` concepts. Amendment source stage references resolve to the same controlled ProcessStage as their associated concrete stage occurrence. `:Published` and `:Enacted` are controlled values, never occurrence instances.
>
> **Correction (Feb 2026):** `:mostRecentStage` removed — duplicated `eli-dl:latest_activity`. `eli-dl:latest_activity` is now annotated in `legislation.owl` for Oireachtas usage (maps to `bill.mostRecentStage`).

#### Classes

| Class | Superclass(es) | Description |
|---|---|---|
| `:EventDate` | `time:TemporalEntity` | A date associated with an event |
| `:JournalEvent` | `eli-dl:LegislativeActivity` | Any event recorded in the Order Paper or Official Report |
| `:BillEvent` | `:JournalEvent` | A procedural event in the lifecycle of a Bill |
| `:BillStage` | `:JournalEvent` | A formal stage of the Bill's passage |
| `:AmendingStage` | `eli-dl:LegislativeActivity`, `:BillStage` | A stage at which amendments may be made |
| `:BillDelivery` | `eli-dl:LegislativeActivity` | The method by which a Bill is initiated |
| `:BillDeliveryOutcome` | `eli-dl:DecisionOutcome` | The outcome of a Bill's introduction |
| `:BillEventOutcome` | `eli-dl:DecisionOutcome` | The outcome of a motion, question or amendment |

#### Object Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:inHouse` | `:BillEvent` | `agents:House` | Renamed from `:InChamber` (2026). Applied only to concrete occurrence activities; controlled stage/event/delivery values are not `:BillEvent` instances. |
| `:commenced` | `time:TemporalEntity` | `:EventDate` | |
| `:elected` | `time:TemporalEntity` | `:EventDate` | |
| `:ended` | `time:TemporalEntity` | `:EventDate` | |

#### Datatype Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:progressStage` | `eli-dl:LegislativeActivity` | `xsd:positiveInteger` | Cross-house sequential order (1 = First Stage Dáil … 10 = Enacted) |
| `:stageNo` | `eli-dl:AmendmentToDraftLegislationWork` | `xsd:positiveInteger` | Stage within a single house at which an amendment list was tabled |

#### Controlled Individuals — Bill Stages

`FirstStage`, `SecondStage`, `OrderSecondStage`, `SecondSubStages`, `CommitteeStage`, `OrderCommitteeStage`, `CommitteeSubStages`, `ReportStage`, `OrderReportStage`, `ReportSubStages`, `FifthStage`, `AllStages`

#### Controlled Individuals — Other Bill Events

`BallotOrder`, `BillAmend`, `BillAmend2Amend`, `BillRecommendation`, `DailAmdSeanad`, `DischargeOrderSecondStage`, `DischargeSecondStage`, `EarlySign`, `FinancialResolution`, `InstrCommittee`, `LeaveToWithdraw`, `RecommitBill`, `RefCommittee`, `RestoreBill`, `SeanadAmdDail`, `VoterInfo`, `Published`, `Enacted`

#### Named Individuals — Bill Event Outcomes

`Agreed`, `DeclaredCarried`, `DeclaredLost`, `NotMoved`, `Withdrawn`

#### Controlled Individuals — Bill Delivery Methods

`Application`, `Introduction`, `Presentation`

#### Named Individuals — Bill Delivery Outcomes

`Examiner`, `Introduced`, `Presented`, `Refused`

#### Named Individuals — ELI-DL Activity Types

| Individual | Replaces | Purpose |
|---|---|---|
| `:LegislativeCreationActivity` | `metalex:LegislativeCreation` | General legislative event type; set via `eli-dl:had_activity_type` on `:JournalEvent` instances |
| `:LegislativeDeliveryActivity` | `metalex:LegislativeDelivery` | Bill delivery/initiation type; set via `eli-dl:had_activity_type` on `:BillDelivery` instances |
| `:LegislativeModificationActivity` | `metalex:LegislativeModification` | Amending activity type; set via `eli-dl:had_activity_type` on `:AmendingStage` and amendment `eli-dl:LegislativeActivity` instances |

---

### legislation.owl

**IRI:** `https://data.oireachtas.ie/ontology/legislation`

Defines the legislative documents published by the Oireachtas, including Bills, Acts, versions, expressions, formats and statuses.

> **ELI-DL migration (2026):** All local subclasses have been eliminated. Each is now replaced by the appropriate ELI-DL or ELI class used directly. The local `metalex` import has been replaced by `eli-dl`. The `:OriginalTitle` data property has been removed in favour of `dct:alternative`.
>
> **bill.json alignment (2026):** `:dateSigned` (sub-property of `eli:date_document`, `xsd:date`) added for presidential signature date. `:statuteBookURI` (sub-property of `dct:relation`) added for Irish Statute Book cross-references. `:hasAmendmentListType` property and `:NumberedAmendmentList` / `:UnnumberedAmendmentList` individuals added. `:Errata` and `:Gluais` resource type individuals added. `dct:modified` annotated for API record update timestamps.
>
> **Corrections and additions (Feb 2026):** `:hasBillType` removed — replaced by `eli-dl:process_type`; `:PublicBill` and `:PrivateBill` retyped as `eli-dl:ProcessType`. `:originHouse` object property added (domain `eli-dl:DraftLegislationWork`, range `:House`) for bill house of introduction. `:legislativeYear` datatype property added (`xsd:integer`) for the year component of `eli:id_local`. Six `eli-dl`/ELI property annotations added: `eli-dl:process_number`, `eli:id_local`, `eli-dl:process_status`, `eli:type_document`, `eli-dl:process_type`, `eli-dl:latest_activity`.

#### Eliminated local classes — use ELI-DL/ELI equivalents directly

| Former class | Direct replacement | Notes |
|---|---|---|
| `:BillResource` | `eli-dl:DraftLegislationWork` | Use `eli:type_document :Bill` to distinguish bills |
| `:BillExpression` | `eli:LegalExpression` | No Oireachtas-specific properties were defined |
| `:BillFormat` | `eli:Format` | No Oireachtas-specific properties were defined |
| `:BillVersion` | `eli-dl:LegislativeProcessWorkVersion` | Version individuals retyped accordingly |
| `:BillsBook` | `skos:OrderedCollection` | Labels belong on instances |
| `:AmendmentList` | `eli-dl:AmendmentToDraftLegislationWork` | ELI-DL supports amendment lists via `eli-dl:has_part` |
| `:BillAmendment` | `eli-dl:AmendmentToDraftLegislationWork` (document) + `eli-dl:LegislativeActivity` (event) | Linked via `eli-dl:created_a_realization_of` |
| `:BillStatus` | `eli-dl:ProcessStatus` | Status individuals retyped accordingly |

#### Annotations on ELI Properties

| Property | Annotation |
|---|---|
| `eli:title_alternative` | `rdfs:label "Long title of a Bill"` |
| `eli:title` | `rdfs:label "Short title of a Bill"` |
| `eli:basis_for` | `rdfs:comment "A Bill is the basis for an Act"` |
| `dct:modified` | Timestamp of last API record update; applied to `eli-dl:DraftLegislationWork` instances (`xsd:dateTime`) |
| `eli-dl:process_number` | For Oireachtas bills: bill/act number component of `eli:id_local` (e.g. `"60"`); maps `billNo` / `actNo` |
| `eli:id_local` | For Oireachtas bills: full compound identifier (e.g. `"2025/60"`); year via `:legislativeYear`, number via `eli-dl:process_number` |
| `eli-dl:process_status` | `stages[].stageOutcome "Enacted"` maps here as `:EnactedBill`, not a `BillEventOutcome`; `stageCompleted` remains source evidence and `eli-dl:latest_activity` identifies the latest completed activity |
| `eli:type_document` | Work-level only (`DraftLegislationWork` or `LegalResource`); `versions[].docType = "act"` signals an Act `eli:LegalResource` |
| `eli-dl:process_type` | Set to `:PublicBill` or `:PrivateBill`; replaces removed `:hasBillType` |
| `eli-dl:latest_activity` | Maps to `bill.mostRecentStage`; replaces removed `:mostRecentStage` (see `events.owl`) |

#### Object Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:hasAmendmentListType` | `eli-dl:AmendmentToDraftLegislationWork` | `skos:Concept` | Numbered or unnumbered list type, drawn from `:AmendmentListTypeTable` |
| `:originHouse` | `eli-dl:DraftLegislationWork` | `:House` | House where the Bill was first introduced; distinct from `eli-dl:was_submitted_by` (submitting agent) |
| `:statuteBookURI` | `eli:LegalResource` | `rdfs:Resource` | Cross-reference to the Irish Statute Book ELI URI; sub-property of `dct:relation` |

#### Datatype Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:dateSigned` | `eli:LegalResource` | `xsd:date` | Presidential signature date (Article 25); sub-property of `eli:date_document` |
| `:legislativeYear` | `eli-dl:DraftLegislationWork` / `eli:LegalResource` | `xsd:integer` | Year component of `eli:id_local`; covers `billYear` and `actYear` JSON fields |

#### Named Individuals — ELI Resource Types

`Act`, `Bill`, `DraftBill` (Heads of Bill), `ExplanatoryMemo`, `Errata`, `Gluais`

#### Named Individuals — ELI-DL Process Types (`:BillTypeTable`)

`:PublicBill`, `:PrivateBill` — typed `eli-dl:ProcessType`; members of `:BillTypeTable`. Used via `eli-dl:process_type` on `eli-dl:LegislativeProcess` instances.

#### Named Individuals — Amendment List Types

`NumberedAmendmentList`, `UnnumberedAmendmentList` — typed `skos:Concept`; members of `:AmendmentListTypeTable`.

#### Named Individuals — Bill Versions

Retyped as `eli-dl:LegislativeProcessWorkVersion`: `AsInitiated`, `VersionA` (2nd printing), `VersionB` (3rd), `VersionC` (4th), `VersionD` (5th)

All remain in `eli:VersionTable` via `skos:inScheme`.

#### Named Individuals — Bill Statuses

Retyped as `eli-dl:ProcessStatus`: `AwaitingSignatureBill`, `CurrentBill`, `DefeatedBill`, `DraftHeadsOfBill`, `EnactedBill`, `LapsedBill`, `RejectedAtReferendumBill`, `SubjectToReferendumBill`, `WithdrawnBill`

---

### vocabulary.owl

**IRI:** `https://data.oireachtas.ie/ontology/vocabulary`

Contains the SKOS `ConceptScheme` individuals that act as controlled vocabularies. Concept members are defined in `events.owl` and `legislative.owl` and reference their scheme via `skos:inScheme`.

| Individual | Label | Members defined in |
|---|---|---|
| `:BillEventTable` | Bill event table | `events.owl` |
| `:BillEventResultTable` | Bill event outcome table | `events.owl` |
| `:BillDeliveryTable` | Bill delivery table | `events.owl` |
| `:BillDeliveryOutcomeTable` | Bill delivery outcome table | `events.owl` |
| `:BillStatusTable` | Bill status table | `legislation.owl` |
| `:BillTypeTable` | Bill type table | `legislation.owl` — members: `:PublicBill` (ProcessType), `:PrivateBill` (ProcessType); used via `eli-dl:process_type` |
| `:AmendmentListTypeTable` | Amendment list type table | `legislation.owl` — members: `:NumberedAmendmentList`, `:UnnumberedAmendmentList` |
| `:CommitteeTypeTable` | Committee type table | `agents.owl` — members: `:SelectCommitteeType`, `:JointCommitteeType`, `:SpecialCommitteeType`; used via `:hasCommitteeType` on `members:Committee` instances |
| `:CommitteePurposeTable` | Committee purpose table | `agents.owl` — members: `:PolicyPurpose`, `:ShadowDepartmentPurpose`; used via `:hasCommitteePurpose` on `members:Committee` instances |

---

### debates.owl

**IRI:** `https://data.oireachtas.ie/ontology/debates`

Models the Official Report of Debates (Akoma Ntoso XML) as OWL classes and properties, covering the structural and semantic elements of parliamentary debates in the Dáil, Seanad and committees.

> **Implementation (2026):** Initial release. `:DebateRecord`, `:DebateExpression`, `:DebateSitting`, `:DebateSection`, `:Speech`, `:Summary`, `:ParliamentaryQuestion` and `:Division` classes defined. Full property set covering structure, participation, voting and legislative linkage. Named individuals for division outcomes, vote categories and participation roles aligned to AKN `TLCConcept` IRIs.
>
> **Key design decisions:** `:DebateRecord` is a `foaf:Document` (not a subclass of `eli-dl:LegislativeProcessWork`) because debates are not always legislative in nature. `:DebateSitting` is always typed `eli-dl:Activity` (not `eli-dl:LegislativeActivity`) because a sitting may mix legislation with questions, statements and motions. `:DebateSection` instances that carry `:refersToEvent` are additionally typed `eli-dl:LegislativeActivity` at instance level (multiple typing); `eli-dl:occured_at_stage` and `eli-dl:forms_part_of` apply on those sections.
>
> **Divisions:** `:Division` is a subclass of `eli-dl:Vote`. Three vote-count properties (`:taCount`, `:nilCount`, `:staonCount`) and three member-vote properties (`:votedFor`, `:votedAgainst`, `:abstained`) reflect the Tá / Níl / Staon structure of Oireachtas divisions; `:staonCount` and `:abstained` are present in data from 2026 onwards.
>
> **`xsd:dateTime` for dates:** `:debateDate` uses `xsd:dateTime` rather than `xsd:date` — `xsd:date` is not in the OWL 2 DL datatype map and is rejected by HermiT. This follows the same convention as the rest of the ontology.

#### Classes

| Class | Superclass(es) | Maps to AKN |
|---|---|---|
| `:DebateRecord` | `foaf:Document` | `FRBRWork` — debate as an intellectual work for a house/date |
| `:DebateExpression` | *(bare OWL class)* | `FRBRExpression` — language-specific version (eng / gle / mul); FRBR correspondence documented in `rdfs:comment` |
| `:DebateSitting` | `eli-dl:Activity` | The sitting activity that produces a `:DebateRecord`; always `eli-dl:Activity`, never `eli-dl:LegislativeActivity` |
| `:DebateSection` | — | `debateSection` — topic-bounded section; nests via `:hasSubSection`; additionally typed `eli-dl:LegislativeActivity` when `:refersToEvent` is present |
| `:Speech` | — | `speech` — oral contribution by a Member or witness |
| `:Summary` | — | `summary` — narrative or procedural text not attributed to a speaker |
| `:ParliamentaryQuestion` | — | `question` — parliamentary question (oral or written) |
| `:Division` | `eli-dl:Vote` | `debateSection[@name='division']` — division with Tá / Níl / Staon sub-sections |

#### Object Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:hasSection` | `:DebateRecord` | `:DebateSection` | Top-level sections of the record |
| `:hasSubSection` | `:DebateSection` | `:DebateSection` | Nested child sections |
| `:hasSpeech` | `:DebateSection` | `:Speech` | |
| `:hasSummary` | `:DebateSection` | `:Summary` | |
| `:hasDivision` | `:DebateSection` | `:Division` | |
| `:producedRecord` | `:DebateSitting` | `:DebateRecord` | Links the sitting activity to its documentary output |
| `:relatedProcess` | `:DebateSitting` | `eli-dl:LegislativeProcess` | Convenience flag; present when at least one section is legislative |
| `:refersToEvent` | `:DebateSection` | `:BillEvent` or `eli:LegalResource` | AKN `debateSection/@refersTo`; triggers `eli-dl:LegislativeActivity` typing |
| `:speaker` | `:Speech` | `:Member` | Shortcut; canonical path is `eli-dl:had_participation` |
| `:askedBy` | `:ParliamentaryQuestion` | `:Member` | `question/@by` → `TLCPerson` |
| `:directedTo` | `:ParliamentaryQuestion` | `eli-dl:ParticipationRole` | `question/@to` → `TLCRole` |
| `:divisionOutcome` | `:Division` | `eli-dl:DecisionOutcome` | `:DeclaredCarried` or `:DeclaredLost` |
| `:refersToProposal` | `:Division` | `:DebateSection` or `:BillEvent` | Subject of the vote; from `voting/@refersTo` |
| `:votedFor` | `:Division` | `:Member` | Members voting Tá |
| `:votedAgainst` | `:Division` | `:Member` | Members voting Níl |
| `:abstained` | `:Division` | `:Member` | Members voting Staon (2026 onwards) |

#### Datatype Properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `:debateDate` | `:DebateRecord` | `xsd:dateTime` | Sitting date; from AKN `FRBRWork/FRBRdate` |
| `:debateType` | `:DebateRecord` | `xsd:string` | AKN `FRBRname/@value` sub-type (e.g. `"debate"`, `"writtens"`) |
| `:sectionName` | `:DebateSection` | `xsd:string` | AKN `debateSection/@name` value |
| `:recordedTime` | `:Speech` | `xsd:dateTime` | AKN `from/recordedTime/@time`; accurate to ~5–10 min |
| `:taCount` | `:Division` | `xsd:integer` | Aggregate Tá votes |
| `:nilCount` | `:Division` | `xsd:integer` | Aggregate Níl votes |
| `:staonCount` | `:Division` | `xsd:integer` | Aggregate Staon votes (2026 onwards) |

#### Named Individuals

| Individual | Type | AKN `TLCConcept` |
|---|---|---|
| `:DeclaredCarried` | `eli-dl:DecisionOutcome` | `#carried` |
| `:DeclaredLost` | `eli-dl:DecisionOutcome` | `#lost` |
| `:TáVote` | `skos:Concept` | `#ta` |
| `:NílVote` | `skos:Concept` | `#nil` |
| `:StaonVote` | `skos:Concept` | `#staon` |
| `:ChairRole` | `eli-dl:ParticipationRole` | `TLCRole` `ceann_comhairle` / `cathaoirleach` |
| `:WitnessRole` | `eli-dl:ParticipationRole` | Committee witness |

#### Annotations on imported properties

| Property | Annotation |
|---|---|
| `eli-dl:had_participation` | Use on `:Speech` (speaker + role) and on legislative `:DebateSection` instances (mover / rapporteur) |
| `eli-dl:occured_at_stage` | Apply on `:DebateSection` instances additionally typed `eli-dl:LegislativeActivity` |
| `eli-dl:forms_part_of` | Apply on `:DebateSection` instances additionally typed `eli-dl:LegislativeActivity` — links section to `eli-dl:LegislativeProcess` |

---

### Referenced External Schemas

| Prefix | Namespace | Description |
|---|---|---|
| `eli:` | `http://data.europa.eu/eli/ontology#` | European Legislative Identifier |
| `eli-dl:` | `http://data.europa.eu/eli/eli-draft-legislation-ontology#` | ELI Draft Legislation ontology |
| `org:` | `http://www.w3.org/ns/org#` | W3C Organisation ontology |
| `time:` | `http://www.w3.org/2006/time#` | W3C Time ontology |
| `skos:` | `http://www.w3.org/2004/02/skos/core#` | Simple Knowledge Organisation System |
| `foaf:` | `http://xmlns.com/foaf/0.1/` | FOAF (Friend of a Friend) — persons, agents, organisations |
| `dct:` | `http://purl.org/dc/terms/` | Dublin Core Terms |

---

### JSON-to-Ontology Mapping

Field-level mappings between Oireachtas API JSON responses and ontology terms are recorded in CSV files in the `data/` directory. Each row maps one JSON field to its ontology term, with notes on IRI patterns, range types and caveats.

| File | Source JSON |
|---|---|
| `data/bill_mapping.csv` | `data/bill.json` |
| `data/member_mapping.csv` | `data/member.json` |
| `data/party_mapping.csv` | `data/parties.json` |
| `data/constituencies_mapping.csv` | `data/constituencies.json` |
| `data/houses_mapping.csv` | `data/houses.json` |

#### Columns

| Column | Description |
|---|---|
| `json_path` | Full dot-notation path to the field, using `[]` to denote array elements |
| `json_field` | Leaf field name |
| `ontology_term` | Prefixed ontology term (`eli:`, `eli-dl:`, `:`, `agents:`, `members:`, `foaf:`, `skos:`, etc.) |
| `term_type` | `Class`, `ObjectProperty`, `DatatypeProperty`, `AnnotationProperty`, or `Individual` |
| `source_file` | The `.ttl` sub-ontology file in which the term is defined |
| `mapping_status` | See status values below |
| `notes` | Mapping rationale, range types, IRI patterns and caveats |

#### Mapping status values

| Status | Meaning |
|---|---|
| `mapped` | Pre-existing ontology term; no changes required |
| `new` | Term added during the alignment work |
| `implicit` | No explicit property needed — the information is derivable from the individual's IRI or class typing |
| `future_work` | No ontology term yet; deferred |
