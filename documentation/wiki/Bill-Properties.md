## Bill Properties

> **2026 update:** Several properties have been eliminated, renamed or replaced following the ELI-DL migration. `oir:hasBillType` is replaced by `eli-dl:process_type`; `oir:originalTitle` by `dct:alternative`; `oir:source` by `eli-dl:was_submitted_by`; `oir:inChamber` renamed to `events:inHouse`; `metalex:` properties removed. New properties added for API alignment. See the [ontology README](https://github.com/Oireachtas/ontology/blob/master/ontology/README.md) for the authoritative property reference.

### Document properties (FRBR / ELI)

| Property | Domain | Range | Notes |
|---|---|---|---|
| `eli:is_part_of` | Bill work | Bills book | |
| `eli:has_part` | Bills book | Bill work | |
| `eli:is_realized_by` | `eli:DraftLegislationWork` | `eli:LegalExpression` | |
| `eli:realizes` | `eli:LegalExpression` | `eli:DraftLegislationWork` | |
| `eli:is_embodied_by` | `eli:LegalExpression` | `eli:Format` | |
| `eli:embodies` | `eli:Format` | `eli:LegalExpression` | |
| `eli:id_local` | Bill work / expression / format | `xsd:string` | Bill identifier, e.g. `{year}/{no}` |
| `eli:type_document` | Bill work | `eli:ResourceType` | E.g. Bill, Act, Explanatory Memorandum |
| `eli:passed_by` | Bill work (final stage) | `agents:ParliamentaryBody` | |
| `eli:date_document` | Bill work | `xsd:date` | Date of President's signature |
| `:dateSigned` | Bill work | `xsd:date` | Sub-property of `eli:date_document`; presidential signature date |
| `eli:related_to` | Bill work / expression | `owl:Thing` | Relate to draft/heads of Bills, explanatory memos |
| `eli:language` | Bill expression | `lang:ENG`, `lang:GLE` or `lang:MUL` | |
| `eli:title` | Bill expression | `xsd:string` (lang en or ga) | Short title; used for versions (LegalExpression) |
| `eli:published_in` | Bill format | e.g. `https://oireachtas.ie/legislative_observatory` | Publication in which legal resource is published |
| `eli:description` | Bill work / expression | `xsd:string` (lang en or ga) | Bill long title |
| `eli:publisher` | Bill expression / format | `xsd:string` | "Houses of the Oireachtas Service" |
| `eli:format` | Bill format | e.g. `iana:text/xml`, `iana:application/pdf` | |
| `eli:version` | Bill expression | e.g. `oir:AsInitiated` | See [Concept Schemes](Concept-Schemes) |
| `eli:version_date` | Bill expression | `xsd:date` | Date presented, passed or ordered to be printed |
| `eli:rightsholder` | Bill format | `xsd:anyURI` | Enduring Oireachtas IRI `<https://data.oireachtas.ie/oireachtas>` |
| `eli:licence` | Bill format | `xsd:anyURI` | e.g. `https://oireachtas.ie/licence` |
| `eli:legal_value` | Bill format | `eli:LegalValue` | Probably `eli:LegalValue-authoritative` |
| `dct:title` | Bill work | `xsd:string` (lang en or ga) | Short title for the work (LegalResource) |
| `dct:alternative` | Bill work | `xsd:string` (lang en or ga) | Short title as initiated (replaces former `oir:originalTitle`) |
| `dct:modified` | Bill work / expression | `xsd:dateTime` | API record update timestamp |
| `:statuteBookURI` | Bill work | `xsd:anyURI` | Sub-property of `dct:relation`; Irish Statute Book cross-reference |
| `:legislativeYear` | `eli-dl:DraftLegislationWork` | `xsd:integer` | Year component of `eli:id_local` |

### Legislative process properties (ELI-DL)

| Property | Domain | Range | Notes |
|---|---|---|---|
| `eli-dl:process_type` | `eli-dl:LegislativeProcess` | `eli-dl:ProcessType` | Bill type: `:PublicBill` or `:PrivateBill`; replaces former `oir:hasBillType` |
| `eli-dl:process_number` | `eli-dl:LegislativeProcess` | `xsd:string` | Bill number within the legislative year |
| `eli-dl:process_status` | `eli-dl:LegislativeProcess` | `skos:Concept` | Current bill status (see [Concept Schemes](Concept-Schemes)) |
| `eli-dl:latest_activity` | `eli-dl:LegislativeProcess` | `eli-dl:LegislativeActivity` | Most recent bill stage/event; replaces former `oir:mostRecentStage` |
| `eli-dl:was_submitted_by` | `eli-dl:LegislativeProcess` | `foaf:Agent` | Bill source: `agents:GovernmentBillSource`, `agents:PrivateMember` or `agents:PrivateSponsor`; the Government source is a controlled concept, not the constitutional Government institution |
| `:originHouse` | `eli-dl:DraftLegislationWork` | `agents:House` | House of introduction (Dáil or Seanad) |
| `eli-dl:parliamentary_term` | `eli-dl:LegislativeActivity` | `agents:HouseTerm` | The Dáil or Seanad term in which the activity occurs |
| `eli-dl:had_activity_type` | `eli-dl:LegislativeActivity` | `eli-dl:ActivityType` | E.g. `:LegislativeCreationActivity`, `:LegislativeDeliveryActivity`, `:LegislativeModificationActivity` |

### Bill event properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `events:inHouse` | `oir:BillEvent` | `agents:House` | The House/committee in which a bill event occurs; renamed from former `oir:inChamber` |
| `oir:progressStage` | `eli-dl:LegislativeActivity` | `xsd:positiveInteger` | Cross-house sequential order (1 = First Stage Dáil … 10 = Enacted) |
| `oir:stageNo` | `eli-dl:AmendmentToDraftLegislationWork` | `xsd:positiveInteger` | Stage within a single house at which an amendment list was tabled |
| `:commenced` | `oir:BillEvent` | `xsd:dateTime` | Date on which the event commenced |
| `:ended` | `oir:BillEvent` | `xsd:dateTime` | Date on which the event concluded |

### Participation and amendment properties

| Property | Domain | Range | Notes |
|---|---|---|---|
| `eli-dl:had_participation` | `eli-dl:LegislativeActivity` | `eli-dl:Participation` | Speaker / mover / rapporteur participation; `eli-dl:participation_role` on the participation node carries `members:MoverRole` or `members:RapporteurRole` |
| `:isPrimarySponsor` | `eli-dl:Participation` | `xsd:boolean` | `true` for the primary bill sponsor; false/absent for secondary sponsors |
| `oir:amends` | `eli:AmendmentToLegislationWork` | `eli:LegalExpression` | The version (expression) of the Bill which an amendment modifies (aligns with `eli:changes`) |
| `oir:amended_by` | `eli:LegalExpression` | `eli:AmendmentToLegislationWork` | The version created on foot of an amendment (aligns with `eli:changed_by`) |
| `:hasAmendmentListType` | `oir:AmendmentList` | `skos:Concept` | Type of amendment list: `:NumberedAmendmentList` or `:UnnumberedAmendmentList` |

### Eliminated properties

| Former property | Reason | Replacement |
|---|---|---|
| `oir:hasBillType` | Removed | `eli-dl:process_type` with `eli-dl:ProcessType` individual |
| `oir:originalTitle` | Removed | `dct:alternative` |
| `oir:source` | Removed | `eli-dl:was_submitted_by` |
| `oir:inChamber` | Renamed | `events:inHouse` |
| `oir:mostRecentStage` | Removed — duplicated `eli-dl:latest_activity` | `eli-dl:latest_activity` |
| `metalex:agent` | Eliminated with metalex import | `eli-dl:had_participation` |
| `metalex:result` | Eliminated with metalex import | `eli-dl:DecisionOutcome` as range of `oir:divisionOutcome` |
| `metalex:predecessor` | Eliminated with metalex import | `eli:is_related_to` or ordering by `eli:version_date` |
| `metalex:successor` | Eliminated with metalex import | as above |
