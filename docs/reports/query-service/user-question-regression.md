# Query Service — User-Question Regression Campaign Scorecard

## Summary

| Classification | Count |
|---|---:|
| PASS | 16 |
| PARTIAL | 3 |
| FAIL | 7 |
| BLOCKED | 0 |
| **Total** | **26** |

This is the running consolidated score as of **2026-11-06**. The iteration-1
score was **7 PASS, 2 PARTIAL, 17 FAIL, 0 BLOCKED**; the earlier pre-iteration-1
baseline was **5 PASS, 2 PARTIAL, 19 FAIL, 0 BLOCKED**. Iteration 2 raised the
score to **10 PASS, 2 PARTIAL, 14 FAIL**; iteration 3 raised it to **12 PASS,
2 PARTIAL, 12 FAIL**; iteration 4 adds Q24 for **13 PASS, 2 PARTIAL, 11 FAIL**;
iteration 5 adds Q19 and Q23 for **15 PASS, 2 PARTIAL, 9 FAIL**; iteration 6
adds Q20 for **16 PASS, 2 PARTIAL, 8 FAIL**. Iteration 7 changes Q7 from FAIL
to PARTIAL: the original question and two date/period variants return one
recorded 2007–08 episode with an explicit incomplete-local-evidence warning;
the expected complete career history remains unestablished. On the integrated
branch containing the latest fetched `origin/master`, all 26 original scorecard
entries were rechecked through the actual `/ask` route at `asOf=2026-11-06`. Q2 and
Q21a still require controlled clarification; Q12 returns Albert Reynolds but
does not establish John Bruton's 1994 service. Q4/Q5/Q8/Q14/Q15/Q17 safely
refused unsupported requests. The consolidated score remains **16 PASS, 3
PARTIAL, 7 FAIL, 0 BLOCKED**. These are conservative evidence/identity
classifications, not preference-based downgrades. This is a consolidated
26-question score; added Q7 wording/member variants are unscored. A
controlled clarification or unsupported response is not a factual pass. The
Galway alternatives remain separate cases 21a and 21b. Post-audit live checks
used the approved campaign-service runner; no credential value was printed or
copied.

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
   suite or data scan was run for the original baseline; subsequent campaign
   verification is recorded below.

## Consolidated results

“Expected” condenses the report's expected answer without changing the test
intent. “Iteration 1 actual/score” preserves that dated baseline. Every original
question in the current column was rechecked through the real service on
2026-11-06; a clarification or unsupported outcome is not a factual pass. Names
and intervals are local recorded evidence, not a completeness-certified roster.

| # | Original question (verbatim) | Expected | Iteration 1 actual | Iteration 1 score / primary cause | Current score / verification (2026-11-06) |
|---:|---|---|---|---|---|
| 1 | `Who are the Sinn Féin TDs for Dublin Central?` | Mary Lou McDonald | Mary Lou McDonald; current 34th-Dáil representation and party intervals both contain 2026-11-04. | **PASS** — current party/constituency composition resolves the present term. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 2 | `Find a Deputy called Browne` | Noel Browne | Clarification offered ten distinct source-identified Deputy candidates, including **Noel C. Browne**, with service dates; no candidate was selected and no answer was asserted. | **PARTIAL** — multiple identities require user selection; candidate presence is not a factual answer. | **PARTIAL** — actual `/ask` returned `clarification_required`, showed **Noel C. Browne** among the distinct local identities, and selected no candidate. |
| 3 | `What were the parties during the 12th Dáil?` | Parties of the 12th Dáil | Clann na Poblachta, Clann na Talmhan, Fianna Fáil, Fine Gael, Labour Party and National Labour Party. | **PASS** — term-scoped party query returns six local records. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 4 | `How long was Stephen Donnelly Minister for Health?` | Duration of tenure | Unsupported: no complete-career office-tenure-duration projection. | **FAIL** — accepted Minister for Health office identity/evidence is also absent, so no duration can safely be derived. | **FAIL** — actual `/ask` recheck returned `unsupported_capability`; no duration or partial tenure was inferred. |
| 5 | `When was Jack Lynch first elected?` | First Dáil/Seanad election date | Unsupported: election-event evidence is not queryable; membership start was not substituted. | **FAIL** — election-event capability/source evidence gap. | **FAIL** — actual `/ask` recheck returned `unsupported_capability`; no election date or service-start proxy was returned. |
| 6 | `What constituencies did Jack Lynch represent?` | Jack Lynch's represented constituencies | Nine term-scoped occurrences for the exact local identity `John-Lynch.D.1948-02-18`: Cork Borough (13th–18th Dáil), Cork City North-West (19th–20th), Cork City (21st). | **PASS** — exact source identity/alias is preserved; local historical completeness is not certified. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 7 | `When was Bertie Ahern the Taoiseach?` | Bertie Ahern's Taoiseach tenure periods (complete career history expected) | Unsupported: service has no complete-career Member/office tenure projection; dated office-overlap queries remain available. | **FAIL** — capability and accepted historical office-evidence coverage do not support a complete tenure timeline. | **PARTIAL** — actual `/ask` returned one accepted local episode, `2007-06-14–2008-05-07`, preserving its OfficeHolding identity and interval. It explicitly says this is incomplete local-recorded evidence, not a complete career/tenure history; the expected full career remains unverified. Original and two date/period variants passed live recheck at `asOf=2026-11-06`. |
| 8 | `When was Bertie Ahern elected Taoiseach` | Start dates of Taoiseach terms, or clarification | Unsupported: election-event evidence is not queryable; no membership/service start substituted. | **FAIL** — election-event capability gap. | **FAIL** — live `/ask` wording variant returned `unsupported_capability`; no election-event date was inferred. |
| 9 | `Who were the other Fianna Fáil TDs in the same constituency as Bertie Ahern while he was Taoiseach?` | Other Fianna Fáil TDs sharing his constituency during Taoiseach service | Cyprian Brady, with 14 plan relations and exact identity/time evidence joining party affiliation, Dáil representation, Bertie Ahern's Taoiseach holding, and shared Dublin Central constituency; common overlap 2007-06-14–2008-05-07. | **PASS** — final clarified prompt produced the valid plan; an initial draft omitted a required edge, so planner variability remains a caveat. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 10 | `Who is the Taoiseach?` | Micheál Martin as of the report date | Unsupported: current office-holder lookup is not supported; office query requires a dated window. | **FAIL** — current office-holder capability gap; no unsafe answer inferred. | **PASS** — live Phase 2 `/ask` returned Micheál Martin's accepted holding (2025-01-23–open) at `asOf=2026-11-06`; current-office completeness is not certified. |
| 11 | `Who is the current Taoiseach?` | Micheál Martin as of the report date | Unsupported: no current Taoiseach query without explicit date/period. | **FAIL** — current office-holder capability gap. | **PASS** — live Phase 2 `/ask` returned the same accepted holding at `asOf=2026-11-06`; current-office completeness is not certified. |
| 12 | `Who was the Taoiseach in 1994?` | Albert Reynolds and John Bruton | Albert Reynolds, holding 1992-12-14–1994-12-15; response says local data does not establish complete historical coverage. | **PARTIAL** — accepted local evidence for John Bruton is missing/incomplete. | **PARTIAL** — actual `/ask` returned Albert Reynolds (1992-12-14–1994-12-15) and explicitly disclaimed complete historical coverage; John Bruton remains unestablished. |
| 13 | `Who was the Taoiseach in June 1994?` | Albert Reynolds | Albert Reynolds, holding 1992-12-14–1994-12-15, overlapping the full June window. | **PASS** — calendar-month office overlap is compiled and executed. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 14 | `Who were the Senators on the Agriculture Panel in June 1994?` | Agriculture Panel Senators in Seanad during June 1994 | Unsupported: Seanad panel membership for a specified period is not supported. | **FAIL** — no panel-membership answer query was compiled. | **FAIL** — actual `/ask` returned `unsupported_capability`: historical Seanad panel membership for a specified month is unsupported; no answer query ran. |
| 15 | `What was the start date of the Dáil which was sitting in June 1994?` | 14 December 1992 | Unsupported: service does not identify a Dáil sitting on a calendar date and return its start. | **FAIL** — term dates alone do not establish an actual sitting; safe refusal is not a factual pass. | **FAIL** — actual `/ask` refused this sitting-to-term lookup as `unsupported_capability`; no answer query ran. |
| 16 | `How many TDs represented the Dublin Central constituency in this Dáil?` | Five TDs | Unsupported: distinct-member count required an explicitly numbered Dáil; “this Dáil” did not resolve to one. | **FAIL** — term ambiguity/aggregate capability boundary. | **PASS** — 2026-11-06 live count recheck returned 5 at `asOf=2026-11-06`; the current Dáil is House-date-resolved, with term-wide recorded memberships. |
| 17 | `Who are the TDs for Dublin Central and when were they first elected?` | Current Dublin Central TDs and their first-election dates | Unsupported: election-event evidence is not queryable; no partial answer was returned. | **FAIL** — compound request includes unsupported election dates; whole request correctly fails closed. | **FAIL** — live `/ask` recheck returned `unsupported_capability` for the whole compound request; no partial TD list or election date was returned. |
| 18 | `What constituency did Bertie Ahern represent in his last term in the Dáil?` | Dublin Central | Dublin Central, 30th Dáil, start date 2007-06-14; `latestRecorded` selector. | **PASS** — latest-recorded term selection resolved the question; local chronology is not complete-history evidence. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 19 | `Who was a Senator in the current Seanad and a Deputy in the current Dáil?` | Seán Kyne | Unsupported: current cross-house service relationship is not supported. | **FAIL** — Seanad-to-Dáil membership intersection capability gap. | **PASS** — live actual-planner query rerun at `asOf=2026-11-06` returned Seán Kyne by exact Member IRI. His 27th-Seanad interval ended 2026-05-24 and 34th-Dáil interval began 2026-05-25; displayed separately as term-wide recorded membership, not simultaneous service. |
| 20 | `What current Senators previously served in the Dáil?` | Current Senators with prior Deputy service | Unsupported: current Seanad membership combined with previous Dáil service is not supported. | **FAIL** — cross-house history capability gap. | **PASS** — live Q20 list/count at `asOf=2026-11-06` returned 11 distinct Member identities and 16 finite prior Dáil paths; each EndDate is strictly before that exact active SeanadMembership StartDate. Both membership/term identities and intervals are displayed; positive local evidence only, not a complete-history or negative claim. |
| 21a | `Who are the Fine Gael TDs in the two Galway constituencies?` | Fine Gael TDs in Galway East and Galway West | Clarification requested exact constituency alternatives; suggestions included Galway East, Galway West and Roscommon-Galway. No Member answer query ran. | **FAIL** — safe clarification, not a factual answer; the intended set is ambiguous in local data. | **FAIL** — actual `/ask` returned `clarification_required`, named Galway East, Galway West and Roscommon-Galway as possible recorded occurrences, and inferred no set or Members. |
| 21b | `Who are the Fine Gael TDs in Galway East and Galway West?` | Fine Gael TDs in Galway East and Galway West | Hildegarde Naughton, Peter Roche and Seán Kyne, with exact representation occurrences in Galway West/East and dated Fine Gael evidence. | **PASS** — explicit two-constituency set composition works. | **PASS** — live recheck passed 2026-11-06 (`asOf=2026-11-06`). |
| 22 | `How many TDs currently represent Meath East constituency?` | Count of current Meath East TDs | Planner proposed `currentTerm`; validation rejected it because the baseline count shape required an explicitly numbered Dáil. | **FAIL** — current-term count was outside the baseline validator. | **PASS** — 2026-11-06 live count recheck returned 4 at `asOf=2026-11-06`; exact current Dáil and membership intervals contain the reference date. |
| 23 | `How many Fine Gael Senators are in the current Seanad?` | Count of Fine Gael Senators | Unsupported: counting current Seanad members by party is not supported. | **FAIL** — Seanad party-membership/aggregate capability gap. | **PASS** — 2026-11-06 live count recheck returned 16 at `asOf=2026-11-06`; current roster completeness is not certified. The separately dated iteration-5 count/list check is recorded below. |
| 24 | `How many other TDs were in the same constituency as Mary Lou McDonald during the last Dáil?` | Count other TDs in her constituency during the previous Dáil | Unsupported: anchored shared-constituency count was not a supported query shape. | **FAIL** — anchored Member relationship aggregate was outside the bounded count compiler. | **PASS** — 2026-11-06 live count recheck at `asOf=2026-11-06` returned 3 other Member IRIs. Separately dated iteration-4 list, alternate-anchor and refusal checks (2026-11-05) are recorded below. |
| 25 | `How many Fine Gael TDs were in the 27th Dáil?` | Count of Fine Gael TDs in the 27th Dáil | Unsupported: bounded party/representation composition could not preserve the aggregate condition; no simplified answer ran. | **FAIL** — party-filtered term aggregate was outside the baseline count capability. | **PASS** — 2026-11-06 live count recheck returned 45 at `asOf=2026-11-06`; exact numbered term and validated party/representation evidence. |

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

## Current unresolved classifications and root causes (2026-11-06)

1. **Capability/evidence gaps — 5 FAIL** (Q4, Q5, Q8, Q14, Q17).
   These comprise office-tenure duration, election-event dates and a compound
   election request, and Seanad panel membership. Q7 now exposes only separate
   accepted local office episodes and remains PARTIAL because it cannot establish
   Bertie Ahern's complete career timeline. Q20's bounded positive cross-house
   prior-service projection does not assert complete-history coverage.
2. **Interpretation/scope — 2 FAIL** (Q15, Q21a): a Dáil term's dates do not
   prove an actual sitting, and “the two Galway constituencies” does not
   identify a unique grounded set.
3. **Evidence/identity limitations — 3 PARTIAL** (Q2, Q7, Q12): Q2 needs the
   user to select among distinct source-identified Deputies with similar names;
   Q7 has only one locally recorded accepted Ahern/Taoiseach episode and does
   not establish a full career; Q12 lacks accepted local evidence establishing
   John Bruton's 1994 service. These scores reflect unresolved identity and
   evidence limits, not preference.
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

At the end of iteration 2, anchored shared-constituency counts, Seanad counts,
seat allocations, election totals, and completeness-certified rosters remained
unsupported.

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
tenure-duration, or election-event capability. At iteration 3, Q7 remained
unsupported; iteration 7 later added only the explicitly incomplete episode
projection described below.

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

### Iteration-3 next prospect (completed in iteration 4)

Q24 was selected and implemented as the next bounded capability: resolve the globally selected
`previousTerm(asOf)`, bind Mary Lou McDonald's exact Member identity and
independent answer-Member membership paths to the same exact term and
constituency identities, exclude her by Member IRI, then count distinct other
Members only after complete selection. Keep the result term-wide recorded
co-membership; do not imply simultaneous service. This can be a narrow validated
projection reusing the existing identity joins, not a generalized compiler
redesign. The next scorecard phase should re-triage the remaining eleven FAIL
cases before selecting another operator; no additional capability is assumed
by this iteration.

## Iteration 4 — anchored shared-constituency list/count (2026-11-05)

Q24 now uses a closed anchored projection within the existing Member
relationship composition. The named anchor and answer Member have separate
DailMembership paths to the same exact selected DailTerm and DailConstituency
IRIs, and the constituency occurrence is joined to that same term. Local code
resolves the named Member uniquely and requires one accepted constituency
identity across the anchor's term-scoped membership evidence before it runs the
answer query. It excludes the anchor by exact Member IRI, deduplicates answer
Members by IRI, and uses the same fully paginated selection for list and count.
The result is term-wide recorded co-membership, not a claim of simultaneous
service or a completeness-certified roster. Party, office, election, explicit
date, simultaneity and additional filters fail closed rather than being
dropped. The previous-Dáil selector uses the globally previous House-dated term
relative to `asOf`, not the anchor's latest-recorded term or a fixed ordinal;
missing, tied, conflicting, ambiguous or capped evidence returns no answer.

The actual configured planner was exercised through Phase 2 `/ask` on the
isolated loopback service at `127.0.0.1:8001`, using the approved runner and
restart scripts with the existing read-only Fuseki service. Readiness succeeded
and the service reported its read-only notice. The exact Q24 count question
resolved `previousTerm(asOf=2026-11-05)` to the 33rd Dáil and returned **3**
other recorded Member identities. An independently worded list question using
“previous Dáil” returned the same three identities: Gary Gannon, Neasa Hourigan
and Paschal Donohoe. A varied anchor (Paschal Donohoe) and explicit 32nd Dáil
returned Mary Lou McDonald and Maureen O'Sullivan. Party-filtered,
simultaneity-filtered and office-filtered variations returned controlled
unsupported outcomes with no answer rows. These are capability diagnostics,
not additional scored cases.

All twelve prior PASS controls (Q1, Q3, Q6, Q9, Q10, Q11, Q13, Q16, Q18, Q21b,
Q22 and Q25) were rerun through the actual planner and `/ask`; each returned a
validated answer matching its recorded expected result. Q16, Q22 and Q25
remained 5, 4 and 45. The score is **13 PASS, 2 PARTIAL, 11 FAIL, 0 BLOCKED**.
Raw HTML responses, readiness and parsed plans/results are retained under
`/tmp/opencode/query-service-user-coverage/iteration-4/`.

Iteration-4 focused verification passed **149 tests** across the Member
relationship, previous-Dáil and Stage A suites. Final verification passed
`.venv/bin/python tests/validate.py` for **2,586 triples**, and
`.venv/bin/python -m pytest tests -q` reported **2,098 passed, 26 skipped, and
23 subtests passed**. Python compilation, JSON and JSON-Schema checks, resolved
Q24 final-plan schema validation, and `git diff --check` passed. No ontology or
mapping changes, protected source/golden fixture changes, production graph/data
mutation or container mutation was performed; no commit or push was made.

## Iteration 5 — current cross-house membership and Seanad party membership (2026-11-05)

Q19 now resolves the current Dáil and current Seanad independently from typed
House-owned date evidence, then intersects exact Member RDF identities across
separate DailMembership and SeanadMembership paths. The result is term-wide
recorded co-membership, not an overlap/current-service test. Each House interval
is displayed separately; Seán Kyne's local records show Seanad service through
2026-05-24 and Dáil service from 2026-05-25. Additional temporal, party,
simultaneity and other filters are refused.

Q23 now resolves the current Seanad term, the exact reviewed Fine Gael
PoliticalAffiliationIdentity and its term-scoped ParliamentaryParty, then joins
typed PartyMembership episodes to their exact SeanadMembership. Both independently
owned intervals must contain `asOf`; missing/conflicting evidence or incomplete
pagination fails closed. Count and list share the same paginated selection and
the result explicitly does not certify a complete current roster.

The live count/list returned **16** distinct Member identities. This corrects
the earlier iteration-5 working diagnosis of 17: the exact local query found 18
term-recorded Fine Gael membership paths, but only 16 satisfy both current-point
interval tests. Seán Kyne's Seanad membership/party intervals ended on
2026-05-24; Martin Conway's Fine Gael PartyMembership interval ended on
2025-02-09. Neither qualifies for the requested exact current-point identity
selection. This is a local interval-evidence result, not a completeness-certified
claim about the current roster.

The actual configured planner was exercised through Phase 2 `/ask` on the
isolated loopback service at `127.0.0.1:8001`, using the approved campaign
runner and the existing read-only Fuseki endpoint. Q19, Q23 count and Q23 list
all returned HTTP 200 validated answers. All thirteen prior PASS controls (Q1,
Q3, Q6, Q9, Q10, Q11, Q13, Q16, Q18, Q21b, Q22, Q24 and Q25) were rerun and
returned their expected identities/rows/counts; Q16, Q22 and Q25 remained 5, 4
and 45. The score is now **15 PASS, 2 PARTIAL, 9 FAIL, 0 BLOCKED**. Parsed
responses, raw HTML and readiness evidence are retained under
`/tmp/opencode/query-service-user-coverage/iteration-5/`. Fuseki was read-only;
no graph/data or container mutation was performed, and no commit or push was
made.

Iteration-5 focused verification passed the NLQ suite (**985 passed, 2
skipped**). Final repository verification passed `.venv/bin/python
tests/validate.py` for **2,586 triples** and `.venv/bin/python -m pytest -q
tests` (**2,117 passed, 26 skipped, 23 subtests passed**). `git diff --check`,
Python compilation, and edited JSON/JSON-Schema checks passed. No ontology,
mapping or protected source/golden fixture was changed.

### Iteration-5 next prospect at that checkpoint — Q20 recorded prior Dáil membership

At the close of iteration 5, the bounded follow-on was Q20 only as “current
Seanad Members with a recorded prior Dáil membership path.” The completed
iteration-6 projection below implements that request using exact current
Seanad and typed DailMembership/DailTerm identities without inferring a term
ordinal or complete career history.

### Iteration-5 independent-review disposition and follow-up

The independent review completed with **no blockers** and accepted the bounded
architecture. Its cheap denylist follow-up is implemented: Q19 current
cross-house and Q23 current-Seanad-party drafts now refuse “past,” “formerly,”
“former,” “used to,” and “no longer” contrasts rather than dropping them. The
original Q19 “was a Senator” wording remains accepted. Focused acceptance
passed (**28 passed**); the NLQ suite passed (**994 passed, 2 skipped**).

Actual-planner Phase 2 `/ask` checks through the approved runner returned Q19's
original answer (Seán Kyne, with separate intervals) and Q23 count/list parity
(**16**). Five historical/current-contrast paraphrases (two Q19, three Q23)
returned `unsupported_capability` with no answer rows. The responses are under
`/tmp/opencode/query-service-user-coverage/iteration-5/denylist-review/`.
At the close of iteration 5, the consolidated score was **15 PASS, 2 PARTIAL,
9 FAIL, 0 BLOCKED**; Q20 was deferred and the Q14 panel alias remained
unmodified. No graph/data or container mutation was performed; no commit or
push was made.

## Iteration 6 — current Seanad Members with prior Dáil membership (2026-11-06)

Q20 now resolves one current SeanadTerm uniquely from Houses-owned dates, then
joins exact Member identities through independent typed SeanadMembership and
DailMembership paths. A SeanadMembership must contain `asOf` using inclusive
calendar-day semantics. A Dáil membership qualifies only with a finite accepted
EndDate strictly earlier than the StartDate of that same SeanadMembership;
equal endpoints and open-ended Dáil intervals do not qualify. No Dáil-term
ordinal or career-wide completeness assumption is used. The list retains both
membership identities, both HouseTerm identities and both intervals; count
and list share the same complete bounded paginated selection. Missing,
conflicting or malformed evidence fails closed. Results are positive local
matches only, not proof of complete history or that anyone else never served.

Actual configured-planner Phase 2 `/ask` at `asOf=2026-11-06` returned **11
distinct Members** and **16 qualifying DailMembership paths** for the exact Q20 question. Its count
variant returned **11**, and two independently worded list variations plus a
count variation returned the same 11-member selection. The read-only
diagnostic finds 12 current Seanad-term-wide Members with a recorded Dáil
path, without a current `asOf` membership filter. The actual Q19 current Dáil
AND Seanad intersection returns one Member, Seán Kyne, whose Seanad interval
expired. The as-of-active Q20 set has 11 Members and 16 strictly prior paths.
In this local snapshot the diagnostic looser `EndDate < asOf` comparison also
yields 11/16; Q20 still implements the strict corresponding-membership
boundary. Party, simultaneity and dated-filter variations were refused with no
result rows. The Q14 panel alias was not added.

All fifteen prior PASS controls returned validated Phase 2 answers at
`asOf=2026-11-06` on the approved isolated loopback runner; Q19 returned Seán
Kyne, Q23 returned 16, and the established counts remained Q16=5, Q22=4,
Q24=3 and Q25=45. The
consolidated score is **16 PASS, 2 PARTIAL, 8 FAIL, 0 BLOCKED** (26 questions).
The dated Q20 and prior-control responses are under
`/tmp/opencode/query-service-user-coverage/iteration-6/live-checks-2026-11-06/`;
Fuseki remained read-only, with no graph/data/container mutation or source
fetch.

Iteration-6 focused acceptance passed (**44 tests** in the current-house
membership file). The related five-file contract/composition regression set was
rerun on 2026-11-06 and passed (**197 passed**). A full NLQ
run passed (**1,010 passed, 2 skipped**) before those last small refinements;
the final full-suite retry exceeded its 420-second command timeout at about
78%, so the final focused set is the completed post-refinement verification.
Ontology validation passed for **2,586 triples**; JSON/JSON-Schema checks,
Python compilation and `git diff --check` passed for the candidate. Independent
review found no code blockers and reproduced the **197-test** focused
regression set, **44-test** acceptance set, and **2,586-triple** ontology
validation. This documentation correction is acknowledged; no additional full
suite run was performed. No commit or push was made.

## Iteration 7 — incomplete local office episodes (2026-11-06)

Q7 now reuses the accepted Member-owned OfficeHolding mapping and reviewed
NamedOffice resolver to return every locally recorded episode for one exact
Member/office pair. Each distinct OfficeHolding identity and its validated
interval is retained through complete bounded pagination. Missing, malformed,
conflicting, or uncertain interval evidence fails closed for the whole list;
unreviewed observations are not used. The UI explicitly labels the rows
**INCOMPLETE LOCAL-RECORDED EPISODES**: no episode merge, career completeness,
first/final boundary, total duration, election event, or negative inference from
gaps is made. Duration, election, and additional-filter questions remain
unsupported as whole requests.

Composable plan contract version **2.25.0** pins this capability to the
`composable_office_evidence` handler with `member_and_office` input. The reviewed
unfiltered wording set also includes “When did [member] serve as [office]?” and
“During what period was [member] [office]?”; deterministic tests verify these
forms without relaxing exact Member/office grounding or the refusals above.

Actual configured-planner `/ask` on the approved isolated loopback service at
`127.0.0.1:8001` returned one Ahern/Taoiseach episode, `2007-06-14`–`2008-05-07`,
for the original Q7 and two independent date/period wordings. Each response
preserved the holding identity and clearly disclaimed complete-career coverage;
the complete expected Ahern timeline is therefore still **PARTIAL**, not PASS.
A separate Micheál Martin/Taoiseach wording also used the generic Member/office
path. Q4 duration, Q5 first election, Q8 Taoiseach election, Q17 compound
election, and added date/filter variants returned unsupported outcomes without
answers. All 16 previously PASS scorecard controls were rerun through the same
actual planner and `/ask` path and matched their expected answer checks at
`asOf=2026-11-06`.

The original Q7, wording variants, refusals, 16 controls, and parsed summaries
are retained under
`/tmp/opencode/query-service-user-coverage/iteration-7/live-checks-2026-11-06/`.
The pre-review live run was recorded as **26/26 expected outcomes/checks**. After
review, the authorized campaign runner refreshed the non-reload port-8001 app
using its existing approved planner settings and read-only Fuseki endpoint; no
data, container, permission, or service configuration was changed, and no
credential value was displayed or written to scratch. The two newly whitelisted
wordings then returned qualified answers (**2/2**). The refreshed 26-check run initially
reported 23/26 because Q18 hit a transient planner-endpoint timeout and Q19/Q20
used stale literal markers. The immediate Q18 retry passed. Q19's output used
the semantically equivalent warning “does not assert simultaneous or current
service”; Q20 correctly returned the as-of-active set, so its old Seán Kyne
marker was replaced with checks for 11 Members and 16 qualifying prior Dáil
paths (Seán Kyne's Seanad interval had ended). The consolidated refreshed
follow-up is **28/28 expected outcomes/checks** in
`iteration-7-review-followup-summary.json`. The overall score remains
**16 PASS, 3 PARTIAL, 7 FAIL, 0 BLOCKED**.

The remaining failures have concrete evidence/capability causes: Q4 lacks a
reviewed Minister for Health identity/accepted office-holding evidence and asks
for unsupported duration; Q5, Q8 and Q17 require election-event mapping rather
than service-start proxies; Q14 lacks a reviewed Seanad panel identity/alias
path and bounded month-query capability; Q15 lacks actual sitting evidence
(term dates alone are insufficient); and Q21a does not specify an unambiguous
geographic set. No further implementation is recommended without new evidence
or scope clarification.
After the final deterministic ordering adjustment, the original Q7, two
date/period variants, and generic Micheál Martin/Taoiseach variant were rerun on
the same service; all four returned the qualified answer.

The pre-review iteration-7 verification passed the focused office-evidence,
interpretation, and existing Q35 set (**73 passed**) and the broader NLQ suite
(**1,027 passed, 2 skipped**). After the review fixes, the expanded focused set
passed (**243 passed**) and the final NLQ suite passed (**1,035 passed, 2
skipped**). Python compilation, contract JSON parsing, and `git diff --check`
passed. Ontology validation was not repeated because no ontology or mapping
files changed; the previously accepted validation remains 2,586 triples. The
iteration-7 independent review found no blockers. Its contract-version,
handler/input drift checks, generic wording and safety-cap follow-ups are
included in the final candidate.

## Campaign closure and integration status (2026-11-06)

- **Result:** 16 PASS, 3 PARTIAL, 7 FAIL, 0 BLOCKED, versus the original
  5/2/19/0 baseline. Newly PASS: Q9, Q10, Q11, Q16, Q18, Q19, Q20, Q22, Q23,
  Q24 and Q25. Q7 improved to explicitly incomplete local evidence, scored
  PARTIAL. Ambiguous identity and missing historical evidence were not guessed.
- **Stopping boundary:** the remaining seven original questions cannot safely
  become factual passes through another small planner/count fix. Q4 needs
  reviewed Health-office evidence; Q5/Q8/Q17 need mapped election-event
  evidence; Q15 needs actual sitting evidence; Q21a needs an explicit geographic
  set. Q14 has a source-backed `Agricultural Panel` identity, but no accepted
  `Agriculture Panel` alias and no bounded month/panel compiler. Adding a new
  panel capability without resolving that original identity wording would not
  resolve the scored question; no alias was invented.
- **Final verification:** the post-correction full NLQ run completed:
  `.venv/bin/python -m pytest tests/test_nlq*.py -q` — **1,053 passed, 2
  skipped** in 384.93 seconds. The earlier focused integration set passed (**476
  passed, 1 skipped**); the Q7 office-evidence file passed (**23 passed**) and
  the Member-composition file passed after the current-term explanation
  correction (**57 passed**).
  All 26 original questions were sent to actual `/ask`: 26/26 HTTP 200 with no
  transport failures; 18 returned answers, two returned controlled
  clarifications (Q2/Q21a), and six returned safe unsupported outcomes
  (Q4/Q5/Q8/Q14/Q15/Q17). Outcome review preserves **16 PASS, 3 PARTIAL, 7
  FAIL, 0 BLOCKED**; Q7/Q12 are partial answers, not factual passes. A
  transient Q18 planner timeout occurred in an earlier follow-up and passed on
  retry; live observations are not a deterministic planner reliability
  guarantee. `git diff --check`, contract JSON parsing and Python compilation
  passed. Ontology validation was not repeated because no ontology or mapping
  files changed; the previously accepted validation remains 2,586 triples.
  All 26 raw HTML responses and the parsed outcome/result summary
  (`original-26-live-summary.json`) are retained under
  `/tmp/opencode/query-service-user-coverage/integration-live-2026-11-06/`.
  Live review caught a presentation mismatch on Q16/Q22: their validated plans
  selected the current 34th Dáil, but a generic fallback described the previous
  Dáil. The renderer now explains the validated selector and distinguishes
  Q16's term-wide scope from Q22's `asOf` membership-date filter. A focused
  regression test covers both; post-fix actual `/ask` retries returned Q16=5
  and Q22=4 with the corresponding current-term scopes. The underlying validated
  query selections were already current-term; this correction changes only the
  explanation shown to users.
  The separate upstream Bill-publication count smoke used the accepted
  `How many Bills did Malcolm Byrne sponsor that were published in 2024?`
  wording through actual `/ask`. It returned HTTP 200 with machine outcome
  `missing_or_unaccepted_evidence` (UI: **Source evidence unavailable**) and
  the diagnostic that at least one recorded sponsored Bill lacks a valid dated
  Published activity; no count/zero was returned. This is the expected
  fail-closed local-evidence outcome, not a planner/runtime failure or the
  original scorecard Q23. Its raw response and summary are in the same scratch
  directory as `bill-published-year-smoke.html` and
  `bill-published-year-smoke-summary.json`.
- **Scope:** no ontology, mapping, protected source/golden fixture, RDF
  ownership, identifier, named-graph, publication or Fuseki-data changes.
  Contract additions remain inside the existing bounded compiler architecture.
- **Integration/Git/PR:** `feat/query-service-user-coverage` incorporates the latest fetched
  `origin/master` (`a824851`) and preserves both the seven-commit campaign and
  upstream Bill-publication aggregation, opt-in feedback, and dashboard-design
  work. The dashboard design files remain unchanged; the composable contract
  version is integrated additively at **2.26.0**. A history-preserving merge
  retains all seven campaign commits; no rebase or wholesale ours/theirs
  selection was used. Upstream-only feedback and dashboard artifacts were
  checked byte-for-byte against `origin/master`. The authorized draft PR targets
  `master` in `stephenrigney/OireachtasOntology`, not the local `gh` default's
  upstream repository; publication details are recorded below. Upstream's Bill temporal aggregation uses a legacy benchmark
  capability ID `Q23`, not original scorecard Q23 (the current-Seanad Fine Gael
  count).
- **Human decisions:** no semantic approval is needed for the completed work.
  New event/office evidence and panel-label clarification remain separate
  follow-ups, not authority to infer missing facts. Integration, branch push and
  draft-PR publication are explicitly authorized; the PR is not to be merged.

### Integration publication

History-preserving merge commit: `ecc4516` (parents `bf979c3` and `a824851`).
The branch was pushed without force to
`origin/feat/query-service-user-coverage`. Draft PR:
[stephenrigney/OireachtasOntology#24](https://github.com/stephenrigney/OireachtasOntology/pull/24),
targeting `master`. GitHub confirmed it is open, draft and mergeable; it has
**not** been merged. Hosted routine-validation checks were still running at the
publication check; the completed local acceptance results above are independent
of those pending checks. No semantic or architectural integration issue remains
known. The documented planner variability and source/identity limitations remain
unchanged.
