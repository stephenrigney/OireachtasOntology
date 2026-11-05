# Query Service — User-Question Regression Campaign Scorecard

## Summary

| Classification | Count |
|---|---:|
| PASS | 10 |
| PARTIAL | 2 |
| FAIL | 14 |
| BLOCKED | 0 |
| **Total** | **26** |

This is the running consolidated score as of **2026-11-05**. The iteration-1
score was **7 PASS, 2 PARTIAL, 17 FAIL, 0 BLOCKED**; the earlier pre-iteration-1
baseline was **5 PASS, 2 PARTIAL, 19 FAIL, 0 BLOCKED**. Iteration 2 changed Q16,
Q22 and Q25 from FAIL to PASS. All seven iteration-1 PASS cases were rechecked
live during iteration 2 and passed. The other 16 cases were not rerun; their iteration-1
classifications are carried forward explicitly in the table, so this is a
consolidated running score, not a fresh 26-question execution. A controlled
clarification or unsupported response is not a factual pass. The Galway
alternatives remain separate cases 21a and 21b. The later audit follow-up did
not change any scored question's scope; its new wording variants are unscored.
Post-audit live checks used the approved campaign-service runner and completed;
no credential value was printed or copied.

## Protocol and environment

- Baseline run: repository commit `4a64367dc2f1584d996b2ded8a25fda6fc7ed171`
  (`master`, 2026-11-04), service port 8000, reference date `2026-11-04`.
- Iteration-1 recheck: current campaign checkout, live service at
  `http://127.0.0.1:8001/ask`, existing read-only local Fuseki at
  `http://localhost:3030/houses/query`, reference date `2026-11-05`; actual
  configured planner and service path, with no test double, manual plan repair,
  or answer-query substitution. Assessment:
  `/tmp/opencode/query-service-user-coverage/iteration-1/postchange-live-evaluation-assessment.json`;
  raw JSON and rendered HTML responses are alongside it in that directory.
- Original reports: `/var/home/stephen/Documents/Scratch/questions-2.md`,
  `questions-3.md`, and `question-report.md`. The prompt's first filename,
  `question-report(1).md`, is not present; the similarly named `question-report.md`
  was present and contains six Question/Expected/Actual cases. The entry counts
  are six, fifteen, and four; the Galway slash-separated alternatives account
  for the stated 26 individual questions.
- Baseline service: the checkout at the commit noted above, launched with
  `scripts/dev-nlq.sh --no-reload`; integrated Phase 2
  `POST http://127.0.0.1:8000/ask`, `mode=phase2`.
- Baseline dataset: existing read-only local Fuseki dataset at
  `http://localhost:3030/houses/query`. Readiness reported Houses, Parties,
  Constituencies, Members, Committees, Bills, Offices, Administrative Units,
  Office Holdings and Cabinet Memberships present. No data bootstrap, graph
  reload, source fetch or publication was performed. Reference date was
  `2026-11-04` (the service's local date).
- Planner: configured `gpt-6-luna` at
  `https://opencode.ai/inference/openai/v1`; API key was present in ignored
  `.env.local` and is intentionally not recorded. Requests used the normal
  service path; no manual plan repair or answer-query substitution was made.
- Evidence: each response was inspected for its rendered answer, outcome,
  clarification/unsupported diagnostic, and—where available—validated plan
  and Fuseki result. HTTP 200 alone was not treated as success. No broad test
  suite or data scan was run.

## Consolidated results

“Expected” condenses the report's expected answer without changing the test
intent. “Iteration 1 actual/score” preserves that dated baseline. The current
column records either a live recheck on 2026-11-05 or an explicit carry-forward;
carried-forward cases were not rerun. Names and intervals are local recorded
evidence, not a completeness-certified roster.

| # | Original question (verbatim) | Expected | Iteration 1 actual | Iteration 1 score / primary cause | Current score / verification (2026-11-05) |
|---:|---|---|---|---|---|
| 1 | `Who are the Sinn Féin TDs for Dublin Central?` | Mary Lou McDonald | Mary Lou McDonald; current 34th-Dáil representation and party intervals both contain 2026-11-04. | **PASS** — current party/constituency composition resolves the present term. | **PASS** — live recheck passed 2026-11-05. |
| 2 | `Find a Deputy called Browne` | Noel Browne | Clarification offered ten distinct source-identified Deputy candidates, including **Noel C. Browne**, with service dates; no candidate was selected and no answer was asserted. | **PARTIAL** — multiple identities require user selection; candidate presence is not a factual answer. | **PARTIAL carried forward** — not rerun 2026-11-05. |
| 3 | `What were the parties during the 12th Dáil?` | Parties of the 12th Dáil | Clann na Poblachta, Clann na Talmhan, Fianna Fáil, Fine Gael, Labour Party and National Labour Party. | **PASS** — term-scoped party query returns six local records. | **PASS** — live recheck passed 2026-11-05. |
| 4 | `How long was Stephen Donnelly Minister for Health?` | Duration of tenure | Unsupported: no complete-career office-tenure-duration projection. | **FAIL** — accepted Minister for Health office identity/evidence is also absent, so no duration can safely be derived. | **FAIL carried forward** — not rerun 2026-11-05. |
| 5 | `When was Jack Lynch first elected?` | First Dáil/Seanad election date | Unsupported: election-event evidence is not queryable; membership start was not substituted. | **FAIL** — election-event capability/source evidence gap. | **FAIL carried forward** — not rerun 2026-11-05. |
| 6 | `What constituencies did Jack Lynch represent?` | Jack Lynch's represented constituencies | Nine term-scoped occurrences for the exact local identity `John-Lynch.D.1948-02-18`: Cork Borough (13th–18th Dáil), Cork City North-West (19th–20th), Cork City (21st). | **PASS** — exact source identity/alias is preserved; local historical completeness is not certified. | **PASS** — live recheck passed 2026-11-05. |
| 7 | `When was Bertie Ahern the Taoiseach?` | Taoiseach tenure period | Unsupported: service has no complete-career Member/office tenure projection; dated office-overlap queries remain available. | **FAIL** — capability and accepted historical office-evidence coverage do not support a complete tenure timeline. | **FAIL carried forward** — not rerun 2026-11-05. |
| 8 | `When was Bertie Ahern elected Taoiseach` | Start dates of Taoiseach terms, or clarification | Unsupported: election-event evidence is not queryable; no membership/service start substituted. | **FAIL** — election-event capability gap. | **FAIL carried forward** — not rerun 2026-11-05. |
| 9 | `Who were the other Fianna Fáil TDs in the same constituency as Bertie Ahern while he was Taoiseach?` | Other Fianna Fáil TDs sharing his constituency during Taoiseach service | Cyprian Brady, with 14 plan relations and exact identity/time evidence joining party affiliation, Dáil representation, Bertie Ahern's Taoiseach holding, and shared Dublin Central constituency; common overlap 2007-06-14–2008-05-07. | **PASS** — final clarified prompt produced the valid plan; an initial draft omitted a required edge, so planner variability remains a caveat. | **PASS** — live recheck passed 2026-11-05. |
| 10 | `Who is the Taoiseach?` | Micheál Martin as of the report date | Unsupported: current office-holder lookup is not supported; office query requires a dated window. | **FAIL** — current office-holder capability gap; no unsafe answer inferred. | **PASS** — live Phase 2 `/ask` returned Micheál Martin's accepted holding (2025-01-23–open) at configured `asOf` 2026-11-05; current-office completeness is not certified. |
| 11 | `Who is the current Taoiseach?` | Micheál Martin as of the report date | Unsupported: no current Taoiseach query without explicit date/period. | **FAIL** — current office-holder capability gap. | **PASS** — live Phase 2 `/ask` returned the same accepted holding at configured `asOf` 2026-11-05; current-office completeness is not certified. |
| 12 | `Who was the Taoiseach in 1994?` | Albert Reynolds and John Bruton | Albert Reynolds, holding 1992-12-14–1994-12-15; response says local data does not establish complete historical coverage. | **PARTIAL** — accepted local evidence for John Bruton is missing/incomplete. | **PARTIAL carried forward** — not rerun 2026-11-05. |
| 13 | `Who was the Taoiseach in June 1994?` | Albert Reynolds | Albert Reynolds, holding 1992-12-14–1994-12-15, overlapping the full June window. | **PASS** — calendar-month office overlap is compiled and executed. | **PASS** — live recheck passed 2026-11-05. |
| 14 | `Who were the Senators on the Agriculture Panel in June 1994?` | Agriculture Panel Senators in Seanad during June 1994 | Unsupported: Seanad panel membership for a specified period is not supported. | **FAIL** — no panel-membership answer query was compiled. | **FAIL carried forward** — not rerun 2026-11-05. |
| 15 | `What was the start date of the Dáil which was sitting in June 1994?` | 14 December 1992 | Unsupported: service does not identify a Dáil sitting on a calendar date and return its start. | **FAIL** — term dates alone do not establish an actual sitting; safe refusal is not a factual pass. | **FAIL carried forward** — not rerun 2026-11-05. |
| 16 | `How many TDs represented the Dublin Central constituency in this Dáil?` | Five TDs | Unsupported: distinct-member count required an explicitly numbered Dáil; “this Dáil” did not resolve to one. | **FAIL** — term ambiguity/aggregate capability boundary. | **PASS** — live count/list parity verified 2026-11-05: 5 distinct Member IRIs; current House-date-resolved Dáil, term-wide recorded memberships. |
| 17 | `Who are the TDs for Dublin Central and when were they first elected?` | Current Dublin Central TDs and their first-election dates | Unsupported: election-event evidence is not queryable; no partial answer was returned. | **FAIL** — compound request includes unsupported election dates; whole request correctly fails closed. | **FAIL carried forward** — not rerun 2026-11-05. |
| 18 | `What constituency did Bertie Ahern represent in his last term in the Dáil?` | Dublin Central | Dublin Central, 30th Dáil, start date 2007-06-14; `latestRecorded` selector. | **PASS** — latest-recorded term selection resolved the question; local chronology is not complete-history evidence. | **PASS** — live recheck passed 2026-11-05. |
| 19 | `Who was a Senator in the current Seanad and a Deputy in the current Dáil?` | Seán Kyne | Unsupported: current cross-house service relationship is not supported. | **FAIL** — Seanad-to-Dáil membership intersection capability gap. | **FAIL carried forward** — not rerun 2026-11-05. |
| 20 | `What current Senators previously served in the Dáil?` | Current Senators with prior Deputy service | Unsupported: current Seanad membership combined with previous Dáil service is not supported. | **FAIL** — cross-house history capability gap. | **FAIL carried forward** — not rerun 2026-11-05. |
| 21a | `Who are the Fine Gael TDs in the two Galway constituencies?` | Fine Gael TDs in Galway East and Galway West | Clarification requested exact constituency alternatives; suggestions included Galway East, Galway West and Roscommon-Galway. No Member answer query ran. | **FAIL** — safe clarification, not a factual answer; the intended set is ambiguous in local data. | **FAIL carried forward** — not rerun 2026-11-05. |
| 21b | `Who are the Fine Gael TDs in Galway East and Galway West?` | Fine Gael TDs in Galway East and Galway West | Hildegarde Naughton, Peter Roche and Seán Kyne, with exact representation occurrences in Galway West/East and dated Fine Gael evidence. | **PASS** — explicit two-constituency set composition works. | **PASS** — live recheck passed 2026-11-05. |
| 22 | `How many TDs currently represent Meath East constituency?` | Count of current Meath East TDs | Planner proposed `currentTerm`; validation rejected it because the baseline count shape required an explicitly numbered Dáil. | **FAIL** — current-term count was outside the baseline validator. | **PASS** — live count/list parity verified 2026-11-05: 4 distinct Member IRIs; exact current Dáil and membership intervals containing the reference date. |
| 23 | `How many Fine Gael Senators are in the current Seanad?` | Count of Fine Gael Senators | Unsupported: counting current Seanad members by party is not supported. | **FAIL** — Seanad party-membership/aggregate capability gap. | **FAIL carried forward** — not rerun 2026-11-05. |
| 24 | `How many other TDs were in the same constituency as Mary Lou McDonald during the last Dáil?` | Count other TDs in her constituency during the previous Dáil | Unsupported: anchored shared-constituency count was not a supported query shape. | **FAIL** — anchored Member relationship aggregate was outside the bounded count compiler. | **FAIL carried forward** — not rerun 2026-11-05. |
| 25 | `How many Fine Gael TDs were in the 27th Dáil?` | Count of Fine Gael TDs in the 27th Dáil | Unsupported: bounded party/representation composition could not preserve the aggregate condition; no simplified answer ran. | **FAIL** — party-filtered term aggregate was outside the baseline count capability. | **PASS** — live count/list parity verified 2026-11-05: 45 distinct Member IRIs; exact numbered term and validated party/representation evidence. |

## Iteration 1 — comparison with the original baseline (historical)

### Passes retained and gained in iteration 1

- **Sinn Féin / Dublin Central:** now returns Mary Lou McDonald for the
  reference date rather than requiring an explicitly numbered term.
- **12th Dáil parties:** now returns all six term-scoped party identities.
- **Jack Lynch constituencies:** now returns constituency occurrences and
  their terms; source identity `John Lynch` is kept distinct rather than
  silently merging records.
- **Taoiseach in June 1994:** full-month office overlap returns Albert Reynolds.
- **Fine Gael in Galway East and Galway West:** the explicit two-name version
  returns the three local TD identities.
- **Ahern shared-constituency party query (Q9):** final prompt clarification
  returned Cyprian Brady with exact identity and temporal joins. The initial
  post-change draft still omitted a required edge; model/planner variability
  remains explicit, and one successful generation does not establish
  deterministic robustness.
- **Ahern last Dáil term (Q18):** exact original wording returned Dublin Central
  in the 30th Dáil using latest-recorded local chronology.

### Improved, but not fully resolved

- **Deputy called Browne:** partial-surname lookup now returns source-grounded
  candidates including Noel C. Browne, but the service correctly asks the user
  to choose among ten identities. It does not yet answer “Noel Browne” alone.
- **Taoiseach in 1994:** calendar-year overlap now returns Albert Reynolds,
  but not expected John Bruton; accepted historical evidence is incomplete.
- **“Two Galway constituencies”:** the vague variant produces a safe grounded
  clarification; only the explicit Galway East/West variant is answered.

At iteration 1, the remaining failures in that live execution were not evidence
that relevant records were necessarily absent. Unsupported requests (including
current office-holder, Seanad cross-house history, election dates and compound
counts) stopped before an answer query. The 1994 gap was an accepted-evidence
completeness limitation. The initial Q9 draft demonstrated residual
planner/model variability despite its final successful attempt. These are
historical iteration-1 observations; the current per-case state is in the
consolidated results table above.

## Current unresolved classifications and root causes (2026-11-05)

1. **Capability/evidence gaps — 10 FAIL** (Q4, Q5, Q7, Q8, Q14, Q17, Q19,
   Q20, Q23, Q24). These comprise office-tenure duration and complete-career
   history, election-event dates and a compound election request, Seanad panel
   and party counts, cross-house histories, and Q24's anchored shared-constituency
   aggregate. Q24 is retained as the next bounded design candidate.
2. **Interpretation/scope — 2 FAIL** (Q15, Q21a): a Dáil term's dates do not
   prove an actual sitting, and “the two Galway constituencies” does not
   identify a unique grounded set.
3. **Evidence/identity limitations — 2 PARTIAL** (Q2, Q12): Q2 needs the user
   to select among distinct people with similar names; Q12 lacks accepted
   complete evidence for John Bruton.
4. **Planner robustness — no current failed case; residual risk at Q9.** Q9
   passed its live recheck, but an earlier draft omitted a required edge. Keep
   that variability as a regression risk, not as a current FAIL.

Counts use mutually exclusive current scorecard statuses; root-cause notes
describe those cases and do not add extra cases.

## Prior bounded design diagnosis — Q24 (iteration 1)

Q24 appears feasible as a **low-to-medium complexity, bounded projection**
using the existing typed identity joins, but it is not an already supported
query shape. Select the globally previous Dáil with the reviewed
`previousTerm(asOf)` House-date resolver; do not substitute Mary Lou
McDonald's member-specific `latestRecorded` term. Bind her exact Member identity
to an anchor DailMembership and bind the answer Members through independent
DailMembership paths to the **same exact DailTerm and DailConstituency IRIs**.
Exclude the anchor by Member IRI, then count distinct other Member IRIs only
after the bounded selection is complete.

The contract already describes the shared-resource identity join, and the
existing office/party-anchored composition demonstrates typed independent
membership paths. However, its executable validator/compiler is tied to extra
office, PartyMembership, and common-interval evidence; the simpler Q24 shape is
not supported by merely enabling that answer mode. A narrowly closed anchored
co-membership plan/query branch, with count/list parity and fail-closed
resolution/pagination tests, is the likely minimum. This interpretation is
term-wide recorded co-membership in the previous Dáil, not necessarily
simultaneous service; a simultaneous-only reading would require a separate
membership-interval intersection rule. No code or semantics were changed during
this iteration-1 diagnosis.

Iteration-1 verification note: the focused suite passed (84 tests). The broader
NLQ suite timed out after 300 seconds at 78%; this was not a passing result.
Those results remain the historical iteration-1 record. Iteration 2 below has
its own final focused, broader, and live verification.

## Iteration 2 — distinct Member count projection (2026-11-05)

The iteration-1 baseline is preserved per row in the consolidated table above;
the three changed classifications are dated live updates, while all other
iteration-1 classifications are explicitly carried forward. The count
projection reuses typed Member/membership/term selections and counts distinct
Member RDF identities only after selection and evidence validation. It does not
count seats or elections or certify roster completeness. All three updated
count results matched their corresponding Member-identity list results; the
per-case rows record the counts and temporal scopes.

The Q16 list variation initially returned a rejected draft because the planner
used the `currentTerm` string instead of the required selector object. The
closed validator was not loosened: the planner instruction was clarified, then
the exact list question was rechecked live and returned five identities. This
one correction/retry is retained as a planner-robustness caveat.

### Rechecks and additional variations

- All seven iteration-1 PASS controls were rechecked live and passed; the
  per-case current-score column records them. Three selected unseen variants
  (shared constituency, latest recorded term, and party history) also answered.
  These checks do not re-score the remaining campaign.
- The Fine Gael 26th-Dáil count variation returned 55; a current Dublin Central
  count returned 4; and a date-qualified 30th-Dáil constituency count returned
  4. Each is a separate live diagnostic, not an added scorecard case.
- `How many Sinn Féin TDs were in the 27th Dáil?` returned
  `missing_or_unaccepted_evidence` because no reviewed matching affiliation
  identity was linked from a party active in that term; no count was returned.
  This is recorded as a safe refusal, not a factual pass or a zero.

### Iteration 2 verification and evidence

- These results describe the initial iteration-2 verification, before the
  audit follow-up below.
- Focused selection: **158 passed** across the temporal-party, Member
  composition, bounded-composition, contract, and shared-term tests.
- Scoped broader NLQ suite (`.venv/bin/python -m pytest tests/test_nlq*.py -q`):
  **917 passed, 2 skipped**.
- Live Phase 2 `/ask` on `127.0.0.1:8001` at reference date `2026-11-05`:
  service/Fuseki readiness was successful and read-only. The actual configured
  planner was used with no test double, manual plan repair, or answer-query
  substitution. Counts and list variants were compared by distinct Member IRI.
- Assessment JSON, raw live responses, and the Q16 follow-up are retained under
  `/tmp/opencode/query-service-user-coverage/iteration-2/`, including
  `postchange-live-evaluation-assessment.json` and `live-evaluation.json`.
  No data was mutated and no commit was made.

Anchored shared-constituency counts, Seanad counts, seat allocations, election
totals, and completeness-certified rosters remain unsupported.

## Independent audit follow-up (2026-11-05)

The independent reviewer found **no blocking defect** and reproduced the
bounded-architecture NLQ result of **917 passed, 2 skipped**. The three low-cost
follow-ups were addressed without changing ontology semantics or the 26-case
score:

- For the non-party one-term Member/constituency list/count, unqualified
  “in this Dáil” is now explicit term-wide scope regardless of “represent” vs
  “represented”; explicit current-point wording still adds its membership-date
  test, and a literal date remains exact. Numbered, other dated, election, and
  party-filtered scopes are unchanged.
- Contract wording now permits a recorded zero only after a complete valid
  bounded membership-date query with no uncertain/conflicting evidence, and
  explicitly denies that this proves a historical negative.
- The final plan validator explicitly rejects an affiliation answer for a
  party-only Member-count/list plan, with direct regression coverage.

Follow-up verification: **132 focused tests passed** across party temporal,
Member composition, and interpretation tests; the broader NLQ suite now reports
**929 passed, 2 skipped** (the twelve additional regression cases are included).
The independent review's 917+2 run is preserved as its separate acceptance
result.

Post-fix real `/ask` verification was completed with the existing campaign
runner/restart on its owned loopback service at `127.0.0.1:8001`. The runner
reads only the three planner settings from the approved external configuration
in memory; no credential was copied or printed. Fuseki readiness and service
readiness succeeded, with Fuseki used read-only. An earlier ad hoc attempt
without this approved planner environment was invalid/inconclusive and is
superseded; it was a harness configuration mistake, not a remaining service
blocker.

All **17** post-audit `/ask` requests returned HTTP 200 with validated answer
outcomes. The new present-tense term-wide question returned 4 distinct Members
with the exact House-date-resolved 34th Dáil, no membership-date constraint and
no as-of interpretation. Its “currently represent” counterpart also returned
4, but its validated plan independently applies the DailMembership interval at
`2026-11-05`; the corresponding term-wide and current lists returned the same
four Member IRIs. Thus the local cardinalities happen to match, while the
validated temporal scopes demonstrably differ. A past-tense term-wide variant
also returned 4; explicit `2026-10-28` and “as of today” variants preserved
their respective exact-date and current-date membership constraints.

The scored count cases were rechecked live: Q16 **5**, Q22 **4**, and Q25
**45**, with their expected current-term/date/numbered-term selections. All
seven iteration-1 PASS controls (Q1, Q3, Q6, Q9, Q13, Q18 and Q21b) were also
rerun and matched their expected answer identities/rows. The score therefore
remains **10 PASS, 2 PARTIAL, 14 FAIL, 0 BLOCKED**; the added wording variants
are unscored. Raw HTML responses and parsed plan/result evidence are retained
under `/tmp/opencode/query-service-user-coverage/post-audit-approved-config/`.
No graph/data or container mutation was performed, and no commit was made.

## Iteration 3 — current named-office point lookup (2026-11-05)

Q10/Q11 now use the existing accepted OfficeHolding date-window resolver. For a
date-less present/current named-office question, validated planner selection
contains only the exact office mention; deterministic local code injects the
configured `asOf` as an inclusive one-day point. The answer retains exact
accepted holding intervals and explicitly disclaims a complete current roster.
Missing, conflicting, uncertain, or absent evidence does not produce a holder
list or a no-holder/vacancy conclusion. This is not a complete tenure-history,
tenure-duration, or election-event capability; Q7 remains unsupported.

The actual configured planner was exercised through Phase 2 `/ask` on the
isolated loopback service at `127.0.0.1:8001`, using the approved runner and
restart scripts. Both Q10 and Q11 returned HTTP 200 validated answers for
Micheál Martin with the accepted interval `2025-01-23`–open-ended and a distinct
plan scope of `2026-11-05` through `2026-11-05`; the planner did not supply that
date. Supplementary actual `/ask` variants also returned Micheál Martin for
“Who currently is the Taoiseach?”; the current Tánaiste lookup returned no
overlapping holding without inferring a vacancy; and the current Minister for
Finance lookup resolved its own registered identity and returned Simon Harris
(2025-11-18–open). An explicit 2021 Taoiseach date remained a date-point query
and did not borrow `asOf`; its absent match was qualified as incomplete
historical evidence. “Who was the Taoiseach?” remained unsupported without a
period. Deterministic fixtures containing only ended Mary Harney/Tánaiste and
Paschal Donohoe/Finance holdings verify that past episodes do not become
current holders; missing/conflicting interval cases also fail closed. The
generic resolver does not hardcode Taoiseach as an office identity.

All ten previously passing controls (Q1, Q3, Q6, Q9, Q13, Q16, Q18, Q21b, Q22,
and Q25) were rechecked through the same actual planner and `/ask` service and
returned validated answers; Q16, Q22, and Q25 remained 5, 4, and 45. The score
is now **12 PASS, 2 PARTIAL, 12 FAIL, 0 BLOCKED**. Raw HTML and parsed plans and
results are retained under
`/tmp/opencode/query-service-user-coverage/iteration-3/`; readiness succeeded
and Fuseki was read-only. No graph/data was mutated and no commit was made.

Iteration-3 verification: **188 focused tests passed** across bounded office,
planner, contract, and related Stage B/composition tests; the full NLQ suite
reported **949 passed, 2 skipped**. The full repository suite reported
**2,081 passed, 26 skipped, and 23 subtests passed**; ontology validation passed
for 2,586 triples. JSON specification parsing and `git diff --check` passed.

### Next credible bounded improvement

Q24 remains a credible next capability: resolve the globally selected
`previousTerm(asOf)`, bind Mary Lou McDonald's exact Member identity and
independent answer-Member membership paths to the same exact term and
constituency identities, exclude her by Member IRI, then count distinct other
Members only after complete selection. Keep the result term-wide recorded
co-membership; do not imply simultaneous service. This can be a narrow validated
projection reusing the existing identity joins, not a generalized compiler
redesign. A bounded, source-backed Seanad capability is an alternative if its
temporal evidence is selected first.
