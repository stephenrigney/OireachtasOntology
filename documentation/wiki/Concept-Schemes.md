# Concept schemes and controlled values

Concept schemes provide reusable classifications and values. A controlled
concept is not itself an occurrence: for example, the concept `:CommitteeStage`
can identify a stage type, while a particular Bill's committee-stage activity
is a separately identified resource. The module guide and Turtle sources give
the authoritative types, definitions and memberships.

## Current local schemes

| Scheme | Example members / use |
|---|---|
| `:BillEventTable` | Procedural Bill-event types, such as `:BallotOrder`, `:BillAmend`, `:CommitteeStage`-related events, `:LeaveToWithdraw` and `:RefCommittee`. The concrete activities are separate resources. |
| `:BillEventResultTable` | Event outcomes such as `:Agreed`, `:DeclaredCarried`, `:DeclaredLost`, `:NotMoved` and `:Withdrawn`. |
| `:BillDeliveryTable` / `:BillDeliveryOutcomeTable` | Controlled Bill delivery types and delivery outcomes. |
| `:BillStatusTable` | Bill process statuses such as `:CurrentBill`, `:LapsedBill`, `:EnactedBill`, `:WithdrawnBill` and `:AwaitingSignatureBill`. |
| `:BillTypeTable` | `:PublicBill` and `:PrivateBill`, typed as ELI-DL ProcessType individuals and used via `eli-dl:process_type`. |
| `:AmendmentListTypeTable` | `:NumberedAmendmentList` and `:UnnumberedAmendmentList`. |
| `:CommitteeTypeTable` | `:SelectCommitteeType`, `:JointCommitteeType`, `:SpecialCommitteeType`; used for Committee classification. |
| `:CommitteePurposeTable` | `:PolicyPurpose` and `:ShadowDepartmentPurpose`; purpose is distinct from committee type. |
| `members:OfficeTypeTable` | Controlled office categories (including Taoiseach, Tánaiste, Minister, Minister of State, Ceann Comhairle and Cathaoirleach office types). A `NamedOffice` points to a concept; the concept is not an office instance or role class. |

ELI's external version scheme supplies Bill version individuals including
`:AsInitiated` and `:VersionA` through `:VersionD`. Legislative activities
also use ELI-DL activity types, process stages and decision outcomes where
specified. Debate divisions use the vote concepts `:TáVote`, `:NílVote` and
`:StaonVote`; only source-supported carried/lost decisions are assigned their
corresponding outcome values.

## Important distinctions

- `:PublicBill` and `:PrivateBill` are process-type individuals, not classes
  that classify a person's identity.
- Select/Joint/Special Committee type and committee purpose are independent
  dimensions.
- A `members:OfficeType` concept classifies an enduring `members:NamedOffice`;
  it is not an OWL role class and does not identify a particular tenure.
- Historical concepts such as `:InvalidBill`, `:BillSource`,
  `:PartyGrouping`, and an old `:CarriedOutcome` scheme should not be assumed
  to be members of current schemes. Consult the current Turtle before reusing
  older lists.

For the exact scheme inventory, see
[`ontology/vocabulary.owl.ttl`](../../ontology/vocabulary.owl.ttl),
[`ontology/events.owl.ttl`](../../ontology/events.owl.ttl),
[`ontology/legislation.owl.ttl`](../../ontology/legislation.owl.ttl),
[`ontology/agents.owl.ttl`](../../ontology/agents.owl.ttl), and
[`ontology/members.owl.ttl`](../../ontology/members.owl.ttl).
