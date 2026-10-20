## Concept Schemes

| oir:BillVersion                        |
|-----------------------------------------|
| oir:AsInitiated                      |
| oir:VersionA                                |
| oir:VersionB                                |
| oir:VersionC                                |
| oir:VersionD                         |
|                                         |
| **oir:BillDelivery**                    |
| oir:Application                         |
| oir:Introduction                        |
| oir:Presentation                        |
|                                         |
| **oir:BillDeliveryOutcome**               |
| oir:Examiner |
| oir:Introduced                          |
| oir:Refused                |
| oir:Presented                           |
|                                         |
| **oir:BillStatus**                        |
| oir:CurrentBill                             |
| oir:RejectedAtReferendumBill |
| oir:LapsedBill                             |
| oir:DefeatedBill                           |
| oir:DeclaredRepugnantToConstitutionBill |
| oir:WithdrawnBill                           |
| oir:InvalidBill              |
| oir:SubjectToReferendumBill               |
| oir:AwaitingSignatureBill |
| oir:EnactedBill                         |
|                                         |
| **oir:BillStage**  |
| oir:AllStages  |
| oir:FirstStage |
| oir:SecondStage |
| oir:SecondSubStages
| oir:CommitteeStage  |
| oir:CommitteeSubStages |
| oir:ReportStage |
| oir:ReportSubStages |
| oir:FifthStage |
|    |
| **oir:AmendingStage**                         |
| oir:CommitteeStage  |
| oir:CommitteeSubStages |
| oir:ReportStage |
| oir:ReportSubStages |
|                                         |
| **oir:BillEvent**  |
| oir:BillStage  |
| oir:LapsedBillEvent |
| oir:Published |
| oir:Enacted |
| oir:BallotOrder |
| oir:BillAmendment |
| oir:BillAmendment2Amendment |
| oir:BillRecommendation |
| oir:BillRejection |
| oir:DailAmdSeanad |
| oir:DeemedPassed|
| oir:DischargeOrderSecondStage |
| oir:DischargeSecondStage |
| oir:EarlySign |
| oir:FinancialResolution |
| oir:InstrCommittee |
| oir:LapsedBillEvent |
| oir:LeaveToWithdraw |
| oir:OrderCommitteeStage |
| oir:OrderReportStage |
| oir:OrderSecondStage |
| oir:RecommitBill |
| oir:RefCommittee |
| oir:RestoredBill |
| oir:SeanadAmdDail |
| oir:VoterInfo |
|   |
| **oir:BillEventOutcome** |
| oir:Agreed |
| oir:DeclaredCarried |
| oir:DeclaredLost |
| oir:NotMoved |
| oir:Withdrawn |
| **oir:CarriedOutcome** |
| oir:Agreed |
| oir:DeclaredCarried |

> **Note (2026):** Bill classification by origin (`oir:GovernmentBill`, `oir:PublicBill`, `oir:PrivateBill`, `oir:PrivateMembersBill`) is now typed as `eli-dl:ProcessType` instances rather than members of a SKOS concept scheme. The `oir:BillSource` concept scheme has been removed.

| **oir:CommitteeType** |
|---|
| oir:SelectCommitteeType |
| oir:JointCommitteeType |
| oir:SpecialCommitteeType |

| **oir:CommitteePurpose** |
|---|
| oir:PolicyPurpose |
| oir:ShadowDepartmentPurpose |
