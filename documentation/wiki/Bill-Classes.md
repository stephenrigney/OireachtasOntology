## Bill Classes

> **2026 update:** `oir:BillSource` and `oir:Mover` have been eliminated and `metalex` superclasses replaced with ELI / ELI-DL equivalents. See the [ontology README](https://github.com/Oireachtas/ontology/blob/master/ontology/README.md) for the authoritative class reference.

| Class | Superclass(es) | Description |
|---|---|---|
| `eli:DraftLegislationWork` | `eli:LegalResource` | The Bill as a distinct intellectual creation (replaces former `oir:BillResource`); use `eli-dl:DraftLegislationWork` directly |
| `eli:LegalExpression` | — | Language-specific version (expression) of a bill; use `eli:LegalExpression` directly |
| `eli:Format` | — | Physical format (PDF, XML, HTML) of an expression; use `eli:Format` directly |
| `oir:BillVersion` | `eli:Version` | Version of Bill (see [Concept Schemes](Concept-Schemes)) |
| `oir:BillDelivery` | `eli-dl:LegislativeActivity` | The action/event by which a Bill first came before the Houses for consideration; typed via `eli-dl:had_activity_type :LegislativeDeliveryActivity` (see [Concept Schemes](Concept-Schemes)) |
| `oir:BillDeliveryOutcome` | `eli-dl:DecisionOutcome` | Outcome of `oir:BillDelivery` (see [Concept Schemes](Concept-Schemes)) |
| `oir:BillEvent` | `eli-dl:LegislativeActivity` | An event that affects the status of a Bill (see [Concept Schemes](Concept-Schemes)) |
| `oir:BillStage` | `oir:BillEvent` | A formal stage of a Bill's passage (see [Concept Schemes](Concept-Schemes)) |
| `oir:BillStatus` | `skos:Concept` | The current status of a Bill (see [Concept Schemes](Concept-Schemes)) |
| `oir:AmendingStage` | `eli-dl:LegislativeActivity`, `oir:BillStage` | A stage (committee or report) at which amendments may be made; typed via `eli-dl:had_activity_type :LegislativeModificationActivity` |
| `eli-dl:DecisionOutcome` | — | Outcome of a motion, question or amendment; use directly — replaces former `metalex:Result` |
| `eli:AmendmentToLegislationWork` | `eli:LegalResource`, `oir:BillEvent` | An amendment as simultaneously a document and a modifying event |
| `oir:AmendmentList` | — | Numbered or unnumbered list of amendments, either proposed or made (see [Concept Schemes](Concept-Schemes)) |
| `eli:LegalExpression` | — | The text of an amendment (expression of `eli:AmendmentToLegislationWork`); replaces former `oir:BillAmendmentText` |

### Eliminated classes

| Former class | Reason | Replacement |
|---|---|---|
| `oir:BillSource` | Submitter type is expressed via `eli-dl:was_submitted_by` (Process → Agent) | Use `eli-dl:was_submitted_by` on `eli-dl:LegislativeProcess` instances; see `agents:GovernmentBillSource`, `agents:PrivateMember`, `agents:PrivateSponsor` |
| `oir:Mover` | Activity-level participation is expressed via `eli-dl:Participation` + `eli-dl:ParticipationRole` | Use `eli-dl:had_participation` with `members:MoverRole` on `:JournalEvent` instances |
| `metalex:Result` | Eliminated with metalex import | Use `eli-dl:DecisionOutcome` directly |
