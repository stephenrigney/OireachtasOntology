# Query Service — Regression Test Original User Questions

## Summary

| Classification | Count |
|---|---:|
| PASS | 5 |
| PARTIAL | 2 |
| FAIL | 19 |
| BLOCKED | 0 |
| **Total** | **26** |

All 26 scored requests reached the live local Phase 2 `POST /ask` service and
Fuseki was ready. A controlled clarification or unsupported response is not
counted as a factual pass. The Galway report entry contains two alternative
verbatim questions; these were scored separately (21a and 21b). The combined
slash-separated line was also tried once as an additional diagnostic, not
scored as a separate test.

## Protocol and environment

- Repository commit tested: `4a64367dc2f1584d996b2ded8a25fda6fc7ed171`
  (`master`, 2026-11-04).
- Original reports: `/var/home/stephen/Documents/Scratch/questions-2.md`,
  `questions-3.md`, and `question-report.md`. The prompt's first filename,
  `question-report(1).md`, is not present; the similarly named `question-report.md`
  was present and contains six Question/Expected/Actual cases. The entry counts
  are six, fifteen, and four; the Galway slash-separated alternatives account
  for the stated 26 individual questions.
- Service: current checkout, launched with `scripts/dev-nlq.sh --no-reload`;
  integrated Phase 2 `POST http://127.0.0.1:8000/ask`, `mode=phase2`.
- Dataset: existing read-only local Fuseki dataset at
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

## Results

“Expected” condenses the report's expected answer without changing the test
intent. Actual names and intervals are local recorded evidence; current-result
coverage is not certified complete.

| # | Original question (verbatim) | Expected | Actual | Result and primary cause |
|---:|---|---|---|---|
| 1 | `Who are the Sinn Féin TDs for Dublin Central?` | Mary Lou McDonald | Mary Lou McDonald; current 34th-Dáil representation and party intervals both contain 2026-11-04. | **PASS** — current party/constituency composition now resolves the present term. |
| 2 | `Find a Deputy called Browne` | Noel Browne | Clarification offered ten distinct source-identified Deputy candidates, including **Noel C. Browne**, with service dates; no candidate was selected and no answer was asserted. | **PARTIAL** — name lookup/clarification capability is improved, but multiple identities require user selection. Candidate presence is not a factual answer. |
| 3 | `What were the parties during the 12th Dáil?` | Parties of the 12th Dáil | Clann na Poblachta, Clann na Talmhan, Fianna Fáil, Fine Gael, Labour Party and National Labour Party. | **PASS** — term-scoped party query returns the six local records. |
| 4 | `How long was Stephen Donnelly Minister for Health?` | Duration of tenure | Unsupported: no complete-career office-tenure-duration projection. | **FAIL** — capability gap; accepted Minister for Health office identity/evidence is also absent, so no duration can safely be derived. |
| 5 | `When was Jack Lynch first elected?` | First Dáil/Seanad election date | Unsupported: election-event evidence is not queryable; membership start was not substituted. | **FAIL** — election-event capability/source evidence gap. |
| 6 | `What constituencies did Jack Lynch represent?` | Jack Lynch's represented constituencies | Nine term-scoped occurrences for the exact local identity `John-Lynch.D.1948-02-18`: Cork Borough (13th–18th Dáil), Cork City North-West (19th–20th), Cork City (21st). | **PASS** — career representation projection works; exact source identity/alias is preserved and local historical completeness is not certified. |
| 7 | `When was Bertie Ahern the Taoiseach?` | Taoiseach tenure period | Unsupported: service has no complete-career Member/office tenure projection; dated office-overlap queries remain available. | **FAIL** — capability and accepted historical office-evidence coverage do not support a complete tenure timeline. |
| 8 | `When was Bertie Ahern elected Taoiseach` | Start dates of Taoiseach terms, or clarification | Unsupported: election-event evidence is not queryable; no membership/service start substituted. | **FAIL** — election-event capability gap. |
| 9 | `Who were the other Fianna Fáil TDs in the same constituency as Bertie Ahern while he was Taoiseach?` | Other Fianna Fáil TDs sharing his constituency during Taoiseach service | No answer query. Planner draft selected the relationship-composition family but omitted its independent Member/shared-constituency operator; validation rejected it. | **FAIL** — planner selection/plan-construction defect. The bounded capability exists and returned Cyprian Brady in an earlier integrated acceptance, but this current run did not answer. |
| 10 | `Who is the Taoiseach?` | Micheál Martin as of the report date | Unsupported: current office-holder lookup is not supported; office query requires a dated window. | **FAIL** — current office-holder capability gap; no unsafe answer inferred. |
| 11 | `Who is the current Taoiseach?` | Micheál Martin as of the report date | Unsupported: no current Taoiseach query without explicit date/period. | **FAIL** — current office-holder capability gap. |
| 12 | `Who was the Taoiseach in 1994?` | Albert Reynolds and John Bruton | Albert Reynolds, holding 1992-12-14–1994-12-15; response says the local dataset does not establish complete historical coverage. | **PARTIAL** — year-overlap query runs, but accepted local evidence for John Bruton is missing/incomplete. This is data/evidence coverage, not a query compilation failure. |
| 13 | `Who was the Taoiseach in June 1994?` | Albert Reynolds | Albert Reynolds, holding 1992-12-14–1994-12-15, overlapping the full June window. | **PASS** — calendar-month office overlap is compiled and executed. |
| 14 | `Who were the Senators on the Agriculture Panel in June 1994?` | Agriculture Panel Senators in Seanad during June 1994 | Unsupported: Seanad panel membership for a specified period is not supported. | **FAIL** — capability coverage gap; no panel-membership answer query was compiled. |
| 15 | `What was the start date of the Dáil which was sitting in June 1994?` | 14 December 1992 | Unsupported: service does not identify a Dáil sitting on a calendar date and return its start. | **FAIL** — no sitting-event evidence is queryable. Term dates alone do not establish that the Dáil actually sat in June; the safe refusal is not a factual pass. |
| 16 | `How many TDs represented the Dublin Central constituency in this Dáil?` | Five TDs | Unsupported: distinct-member count requires an explicitly numbered Dáil; “this Dáil” did not resolve to one. | **FAIL** — term ambiguity/aggregate capability boundary. |
| 17 | `Who are the TDs for Dublin Central and when were they first elected?` | Current Dublin Central TDs and their first-election dates | Unsupported: election-event evidence is not queryable; no partial answer was returned. | **FAIL** — compound request includes unsupported election dates; whole request correctly fails closed. |
| 18 | `What constituency did Bertie Ahern represent in his last term in the Dáil?` | Dublin Central | No answer query. Planner emitted `latestRecorded`; the validator's lexical gate did not recognize “last term” as an explicit latest-recorded scope. | **FAIL** — planner/validation intent-phrase mismatch. Latest-recorded term capability is implemented, but this wording did not reach the compiler. |
| 19 | `Who was a Senator in the current Seanad and a Deputy in the current Dáil?` | Seán Kyne | Unsupported: current cross-house service relationship is not supported. | **FAIL** — capability gap (Seanad-to-Dáil membership intersection). |
| 20 | `What current Senators previously served in the Dáil?` | Current Senators with prior Deputy service | Unsupported: current Seanad membership combined with previous Dáil service is not supported. | **FAIL** — capability gap (cross-house history). |
| 21a | `Who are the Fine Gael TDs in the two Galway constituencies?` | Fine Gael TDs in Galway East and Galway West | Clarification requested exact constituency alternatives; suggestions included Galway East, Galway West and Roscommon-Galway. No Member answer query ran. | **FAIL** — safe clarification, not a factual answer; “two Galway constituencies” does not identify an unambiguous set in the local data. |
| 21b | `Who are the Fine Gael TDs in Galway East and Galway West?` | Fine Gael TDs in Galway East and Galway West | Hildegarde Naughton, Peter Roche and Seán Kyne, with exact representation occurrences in Galway West/East and dated Fine Gael evidence. | **PASS** — explicit two-constituency set composition works. |
| 22 | `How many TDs currently represent Meath East constituency?` | Count of current Meath East TDs | Planner proposed a count with `currentTerm`; validation rejected it because this count shape requires an explicitly numbered Dáil. | **FAIL** — bounded count capability/validator accepts numbered terms, not current-term count. |
| 23 | `How many Fine Gael Senators are in the current Seanad?` | Count of Fine Gael Senators | Unsupported: counting current Seanad members by party is not supported. | **FAIL** — Seanad party-membership/aggregate capability gap. |
| 24 | `How many other TDs were in the same constituency as Mary Lou McDonald during the last Dáil?` | Count other TDs in her constituency during the previous Dáil | Unsupported: anchored shared-constituency count is not a supported query shape. | **FAIL** — aggregate over an anchored Member relationship is outside the bounded count compiler. |
| 25 | `How many Fine Gael TDs were in the 27th Dáil?` | Count of Fine Gael TDs in the 27th Dáil | Unsupported: bounded party/representation composition cannot preserve the aggregate condition; no simplified answer ran. | **FAIL** — party-filtered term aggregate is not covered by the count capability. |

## Comparison with the original failures

### Resolved in this run

- **Sinn Féin / Dublin Central:** now returns Mary Lou McDonald for the
  reference date rather than requiring an explicitly numbered term.
- **12th Dáil parties:** now returns all six term-scoped party identities.
- **Jack Lynch constituencies:** now returns constituency occurrences and
  their terms; source identity `John Lynch` is kept distinct rather than
  silently merging records.
- **Taoiseach in June 1994:** full-month office overlap returns Albert Reynolds.
- **Fine Gael in Galway East and Galway West:** the explicit two-name version
  returns the three local TD identities.

### Improved, but not fully resolved

- **Deputy called Browne:** partial-surname lookup now returns source-grounded
  candidates including Noel C. Browne, but the service correctly asks the user
  to choose among ten identities. It does not yet answer “Noel Browne” alone.
- **Taoiseach in 1994:** calendar-year overlap now returns Albert Reynolds,
  but not expected John Bruton; accepted historical evidence is incomplete.
- **“Two Galway constituencies”:** the vague variant produces a safe grounded
  clarification; only the explicit Galway East/West variant is answered.

### Capability added, but current planner/validation still fails

- **Ahern's shared-constituency party query:** bounded independent-member
  composition was implemented and prior live acceptance returned Cyprian Brady;
  this run's planner omitted the required operator and validation prevented
  execution.
- **Ahern's last Dáil term:** latest-recorded term selection is implemented,
  but this run's “last term” wording failed the validator's latest-recorded
  lexical gate before query compilation.

The remaining original failures in current live execution are not evidence that
the relevant records are necessarily absent. Unsupported requests (for example
current office-holder, Seanad cross-house history, election dates and compound
counts) stop before an answer query. The year-1994 gap is explicitly a local
accepted-evidence completeness limitation. The Ahern and latest-term failures
are planner/validation defects despite their controlled or earlier live
capability evidence.

## Remaining failures grouped by root cause

1. **Planner selection / plan validation — 2 failures (9, 18).** The planner
   omitted the shared-member operator for the accepted Ahern composition, and
   the validator did not accept “last term” as the explicit latest-recorded
   scope for a supported selector. These should be addressed before adding new
   query families.
2. **Capability/evidence limitations — 15 failures (4, 5, 7, 8, 10, 11, 14,
   16, 17, 19, 20, 22, 23, 24, 25).** These include
   election-event dates, current office-holder lookup, Seanad panel/party and
   cross-house relationships, unqualified-term/party aggregates, and anchored
   aggregate composition. Question 17 is a compound form of the election-event
   gap. Question 16 also has unresolved term scope.
3. **Evidence/coverage — 1 partial (12), with a related unsupported tenure
   case (7).** The year query executes but only has accepted evidence for Albert
   Reynolds; the service does not certify complete office history. Full Ahern
   tenure is likewise not projected from incomplete career office evidence.
4. **Question interpretation / scope — 2 failures (15, 21a).** The June 1994
   question asks for an actual sitting, which term start/end dates alone cannot
   prove; the vague Galway-set wording prompts for grounded alternatives. Both
   responses are safe, but neither supplies the expected factual answer.
Counts above group related causes and are not additive across rows; the
case-level table is authoritative. The capability/evidence group includes Q22's
current-term count selector, which the existing bounded count accepts only for
a numbered Dáil.

## Recommended next bounded implementation tranche

1. **Repair planner/validator interoperability for existing operators (highest
   immediate return: 2 original answers).** Accept “last term” only as a
   validated synonym for the already-supported `latestRecorded` scope, and
   improve plan selection for the already-accepted independent-member/shared-
   constituency operator. Add exact-question regressions for Q9 and Q18; retain
   fail-closed behavior.
2. **Add a narrowly defined numbered-term party count (potentially 1 direct
   case, Q25).** Reuse the existing exact Dáil/party/representation selection
   and identity deduplication; only count if existing contracts and evidence
   support the same query without dropping filters. This should not imply
   election-seat counts or complete historical coverage.
3. **Evaluate current-term bounded counts (Q22) as a separate extension.**
   Specify whether current term is an allowed selector for the existing count
   operator before changing validation; do not loosen the current explicit-term
   safeguard without that decision.
4. **Investigate accepted-data completeness for John Bruton (Q12) and historical
   office holdings (Q7).** First establish whether authoritative captured and
   reviewed evidence exists; do not infer holdings from labels or tenure dates.
5. **Keep election events, Seanad panel/cross-house and office-holder lookup
   separate from this low-risk tranche.** They need explicit evidence sources
   and bounded semantics before implementation. For Q15, either obtain actual
   sitting evidence or continue clarifying that term dates do not prove a
   sitting; do not answer the sitting question from term dates alone.

No Query Service implementation was changed for this evaluation. The report is
the sole repository deliverable.
