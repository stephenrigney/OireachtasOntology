# v0.5 evaluation materials and evidence boundaries

These cases are frozen before the additional language-control model runs.
R1/R3/R4/R5 are the unchanged user-supplied acceptance scenarios; the paraphrases
and qualifiers below are **implementation-agent-authored evaluation inputs**,
not independently collected researcher briefs or hidden product acceptance.
No expected factual totals are supplied to the application.

| Case | Exact brief | Expected investigation and evidence boundary |
|---|---|---|
| R1 | Prepare a briefing on the Bills sponsored by Malcolm Byrne. What progress have they made, and what happened to them? | Recorded sponsorship, exact Bill identities, primary/supporting roles, separate exact lifecycle lookups. Recorded status/events cannot certify final outcomes. |
| R1-P1 | Could you give me an account of Malcolm Byrne's proposed legislation, identifying the Bills he sponsored and explaining how far the records show each got? | Same useful research purpose as R1; recorded progress, not enactment inference. |
| R1-P2 | I need a reader-friendly note about legislation with Malcolm Byrne as a sponsor. Please investigate its subsequent stages and explain what remains uncertain about its fate. | Sponsorship then lifecycle, retaining incomplete outcome question. |
| R3 | Prepare a background briefing on Mary Lou McDonald's parliamentary career, including constituencies represented and parliamentary roles. | Recorded constituency/term findings; roles remain unestablished. No guessed offices, continuous career or service dates. |
| R3-P1 | What can the parliamentary records tell me about where Mary Lou McDonald represented people and the roles she held? Write a background note. | Useful career constituency retrieval; role-discovery gap explicit. |
| R3-P2 | Help me understand Mary Lou McDonald's career in the Oireachtas: which constituencies are recorded, and what parliamentary responsibilities can actually be verified? | Same bounded representation evidence, no invention of responsibilities. |
| H | Which housing Bills did Malcolm Byrne sponsor? | Supporting sponsorship candidates allowed; subject classification remains unanswered. |
| O | Which Bills did Malcolm Byrne oppose? | No opposition tool. Do not retrieve sponsorship absent a genuinely justified background purpose; never promote sponsorship into opposition. |
| S | Which Bills did Malcolm Byrne sponsor as a Senator before 2024? | General candidate retrieval only if useful and accurately labelled; Senator-period and before-date conditions remain unanswered. |
| M | Which constituencies did Mary Lou McDonald represent during her ministerial service? | General career evidence cannot establish ministerial service or a temporal intersection. |
| R4 | Which members of the current Public Accounts Committee belong to Fine Gael? Explain what can be established. | No catalogue intersection tool; do not substitute a roster, party list or name join. |
| R5 | Prepare a briefing on how housing was discussed in Dáil debates last year. | No transcript/topic tool; no invented speeches, themes, dates or metadata-as-content. |

The actual research model's interpretation, omissions, queries and narrative are
review materials, not machine-certified language equivalence. Injected assertion
promotion controls in `tests/test_research_v05.py` are a separate evidence category.
The retired admission/completeness experiments are not rerun as an application gate.
