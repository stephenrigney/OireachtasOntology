# Order papers, questions and votes — scope boundary

> **Status: not a separate current dataset/model slice.** The earlier wiki
> sketches below this topic proposed URIs and structures that are not the
> current mapping contract. Do not use those proposals to mint current RDF.

The ontology does model Bill lifecycle activities and it models supported
parliamentary questions and divisions **inside a Debate record**. That does
not imply a complete standalone Order Paper, Questions list, or vote-attendance
dataset. Committee roll-call attendance remains source-only.

| Topic | Current boundary |
|---|---|
| Bill stages and events | Current Bill lifecycle resources use ELI-DL activities and the mapped `events:BillEvent` vocabulary. See [Bills](Bills.md). |
| Parliamentary questions | Supported AKN questions are `debates:ParliamentaryQuestion` resources within Debate sections. Recipient-to-office links and answer pairing are not inferred. See [Debate structure](Debates-body.md#questions). |
| Divisions and votes | Supported AKN divisions are `debates:Division` / `eli-dl:Vote` resources within Debate sections. Roll-call attendance is not emitted as RDF. See [Debate structure](Debates-body.md#divisions-and-votes). |
| Order Papers and separate question lists | No separate current ETL ownership contract or complete ontology/mapping slice is claimed here; standalone modelling remains deferred. |

The old standalone question URI patterns and placeholder Order Paper/vote
sections have been retired from current guidance. For implemented scope and
deferred work see [Phase 7 Debates](../phase-7-debates.md),
[Bill lifecycle](../phase-4-legislative-lifecycle.md), and the
[current system overview](../current-state.md#data-coverage-and-limits).
