# Query Service — Independent Generalisation and Overfitting Evaluation

## 1. Executive summary

**Verdict: reusable bounded execution is demonstrated; broad natural-language
generalisation is not.** The original benchmark substantially overstates
robustness to new wording. Most misses are safe refusals or validation failures
before execution, not wrong parliamentary answers or missing RDF.

- **60/60** frozen questions executed. Frozen score: **31 PASS, 1 PARTIAL,
  26 FAIL, 2 BLOCKED**. Nine PASS cases are boundary handling, not factual answers.
- Correct factual answers: **22/48 = 45.8%**, below the 85% target. Independent
  review identified three overclaimed composition scopes; excluding only those
  gives **22/45 = 48.9%**, still far below target. Frozen expectations are unchanged.
- Incorrect returned factual answers: **0 observed**; silent constraint loss on
  unsupported/ambiguous requests: **0/10**. These are descriptive sample results,
  not a population error-rate guarantee.
- Twenty questions received three fresh runs each. Factual content/answer
  availability was consistent for **19/20 (95%)**; outcome classes were consistent
  for **17/20 (85%)**, or **17/18 (94.4%)** after excluding two scope-uncertain
  compositions. Among the six questions answering at least once in the repeats,
  only **5/6** answered consistently. Stable refusals inflate aggregate consistency.
- All **16/16** original PASS regression controls retained their factual results.
- No application, prompt, ontology, mapping, ETL, fixture or Fuseki change was
  made. The user-authorized dirty-master environment and limited prior test-diff
  exposure constrain attribution and independence; both are documented below.

The strongest evidence of over-adaptation is **surface-form conditioning**, not
entity memorisation: an engine that correctly executes historical intersections
and dated joins nevertheless refuses ordinary alternatives such as “seat
complement”, “Who holds”, “current Senators”, “Who else”, and “rather than seats”.

| Proposed target | Observed | Assessment |
|---|---|---|
| Correct supported answers ≥85% | 45.8% frozen; 48.9% contract-admissible sensitivity | **Not met** |
| Incorrect factual answers ≤5% | 0/60 cases; 0/22 returned factual answers | Met descriptively; small-sample limitation |
| Unsupported requests silently dropping constraints =0 | 0/8 unsupported; 0/10 including ambiguity | Met in this sample |
| Repeated substantive consistency ≥90% | Content/availability 95%; outcome classes 85% (94.4% admissible subset) | Content target met; outcome result scope-sensitive, not uniformly robust |
| Existing 16 PASS questions: no regressions | 16/16 factual matches | Met in this replay |

## 2. Environment and exact evaluated source

- Repository: `stephenrigney/OireachtasOntology`,
  `/var/home/stephen/Projects/OireachtasOntology`, branch `master`.
- Integrated baseline: `6b38eff56aaa9062276dba0c80beb945aa59e9dc`,
  `Merge pull request #24 from stephenrigney/feat/query-service-user-coverage`.
- The user explicitly replaced the fresh-worktree/evaluation-branch requirement
  with permission to work in the existing `master` worktree. No branch switch,
  worktree creation, reset, stash, or application edit was performed.
- This is **not a clean-merge-only measurement**. Two pre-existing source changes
  were present: `poc/nlq/composable_plan.py` and `poc/nlq/member_resolution.py`
  added conservative leading-preposition handling during exact-label resolution.
  Two pre-existing test files were also dirty. They were neither changed nor
  committed by this evaluation. The source delta is preserved in
  [preexisting-source.patch](independent-generalisation/preexisting-source.patch);
  [freeze.json](independent-generalisation/freeze.json) records module/template
  SHA-256 hashes and the original dirty-file inventory.
- Existing real service: `http://127.0.0.1:8000/ask`, `mode=phase2`, Uvicorn
  application rooted in this worktree. Other running worktree services were not
  used. Configured planner: `gpt-6-luna`,
  `https://opencode.ai/inference/openai/v1`, 45-second provider timeout,
  2,000 output-token limit. No test double, planner substitution, prompt change,
  manual plan repair, model change, or retry-to-pass was used.
- Reference date: **2026-11-06**. No `OIR_NLQ_AS_OF_DATE` override was present;
  this was the service's calendar date throughout the run.
- UTC execution windows: main holdout **21:13:44–21:17:43**; original regression
  controls **21:14:29–21:16:47**; variability **21:18:13–21:25:10**. Main and
  variability each used two workers; the separate regression replay used one
  concurrent worker during part of the main run. Thus up to three `/ask` requests
  were in flight during that overlap; no provider/transport failures occurred.
- Read-only local dataset: `http://localhost:3030/houses/query`. No bootstrap,
  reload, update, graph replacement, source fetch, or Fuseki configuration change.
  Credentials were used only in memory and are absent from the artifacts.
- The local accepted-evidence projection is **not an authoritative or complete
  historical dataset**. Office samples, reviewed party identities and Bill dates
  have explicit coverage limitations. Expected answers mean matches in that
  recorded slice, not independently certified complete real-world rosters.

## 3. Holdout construction, independence and freeze

Read `AGENTS.md`, executor guidance, the public `/capabilities` catalogue,
`docs/guides/query-service.md`, the technical specification and machine-readable
query/schema contracts. The catalogue advertises bounded compiler expressibility,
not arbitrary combinations or dataset completeness. Contract version was
**2.26.0**. Built 60 questions from the supported operations and their exclusions:
alternative language, historical/current selection, exact identity intersections,
dated representation/party joins, finite constituency OR sets, anchored relations,
office windows/episodes, cross-house paths and distinct-identity aggregation.

**Independence caveat:** the initial environment check inadvertently displayed
the existing diffs in two campaign test files, including previous-Dáil
constituency examples for Dublin Central/South-Central and entity-preposition
tests. Those places/examples were excluded from the new holdout. The original
26-question scorecard, expected answers and full question-specific tests were not
read before freezing. The public guide contains examples and historical benchmark
summaries; that permitted capability exposure is not a blind capability discovery
experiment. This is an independently constructed, contract-informed holdout with
disclosed limited contamination, not a claim of perfect question-generation
blinding.

The oracle builder uses **direct, independently authored read-only SPARQL**, not
the Query Service compiler, planner, output, or imported implementation functions.
Every factual case retains its query, RDF identities, returned values and relevant
datatype/language evidence. Houses-owned chronology establishes the current 34th
Dáil, current 27th Seanad and globally previous 33rd Dáil. Member records establish
membership/representation; reviewed reference graphs establish exact parties,
constituency occurrences and offices; Bill-owned process paths establish
sponsorship. No expected answer was derived from an `/ask` response.

Two evidence limitations were identified **before** execution:

- **H10:** no recorded Mary Robinson Dáil-membership path. Absence is not a
  certified historical no-service finding.
- **H49:** Brendan Howlin's sponsored Bills include missing Published activities
  and one Published activity with conflicting dates. A filtered query's zero is
  **not** an acceptable aggregate; the guard query independently establishes why
  counting must fail closed.

These remain in the frozen set, classified separately from factual accuracy.
There are 48 factual-answer cases, eight unsupported requests, two ambiguous
requests and these two evidence-blocked cases. No failed question was replaced,
and no expectation was revised after execution.

Freeze: **2026-11-06T21:13:27.150483+00:00**, committed as `2564bc9` before the
first `/ask` request. Frozen holdout SHA-256:
`d84b9d1c954b277181702e7da44e5a77e7edb4948f1a8fc7f018f563baec5f18`.
The complete frozen questions, expected outcomes, evidence queries and results
are in [holdout.json](independent-generalisation/holdout.json). The before-run
chronology and graph inventory are in
[oracle-context.json.gz](independent-generalisation/oracle-context.json.gz);
the freeze hash applies to the decompressed original JSON bytes.

### Scoring rules

- **PASS:** every requested constraint and expected value/set is satisfied;
  required local-coverage qualifications remain visible. Boundary-case PASS means
  correct refusal/clarification, never a factual answer.
- **PARTIAL:** a correct but incomplete requested projection/qualification,
  without invented facts.
- **FAIL:** incorrect factual value/set, lost constraint, or failure/refusal on a
  supported query with independently available evidence. HTTP 200 is not success.
- **BLOCKED:** independently unavailable/invalid prerequisite evidence; excluded
  from factual-answer accuracy, not counted as a safe factual pass.

The primary denominator is the 48 evidence-backed supported questions. Boundary
handling and evidence blocking are reported separately. A one-shot success and
substantive repeatability are different measurements. Names and prose wording
alone do not establish set/count correctness: rendered identities, values,
intervals, generated plans and diagnostic evidence were inspected.

## 4. Complete holdout: expected and actual outcomes

The following is the **complete frozen question set**, not selected successes.
Expected sets are abbreviated only in this readable table; exact RDF-identity
sets and independent queries are preserved per case in `holdout.json`. Actual
rendered answers, all table cells, plans and failure diagnostics are preserved in
`main.jsonl` (compressed in the final evidence bundle). Scores here compare with
the **unchanged frozen expectations**; the three scope-admissibility caveats
H21/H22/H44 are discussed separately below and are not silently re-scored.

Constraint column: **Y** = preserved in the returned answer; **S** = no final
answer asserted, so constraints were safely not simplified into an easier answer.
Resolution/evidence queries may still have run. S does **not** make
a supported request a PASS. No case silently omitted a requested constraint.

| ID | Frozen question (verbatim) | Independently expected | Actual answer/outcome | Score; constraints |
|---|---|---|---|---|
| H01 | Find the parliamentary record for Deputy Joan Burton. | Exact local Joan Burton identity with Dáil service | Joan Burton | PASS; Y |
| H02 | Find the parliamentary record for Deputy Róisín Shortall. | Exact local Róisín Shortall identity with Dáil service | Róisín Shortall | PASS; Y |
| H03 | Which constituency does Alan Kelly represent now? | Tipperary North, 34th Dáil; active interval | Tipperary North, 34th Dáil | PASS; Y |
| H04 | In Eamon Gilmore's latest recorded Dáil term, what was his constituency? | Dún Laoghaire, 31st Dáil, House start 2011-03-09 | Exact expected occurrence/start | PASS; Y |
| H05 | List every constituency Frances Fitzgerald has represented in the Dáil, keeping the terms separate. | Dublin South-East (27,28); Dublin Mid-West (31,32) | All four exact term-scoped occurrences | PASS; Y |
| H06 | How many distinct Dáil terms appear in Brendan Howlin's membership record? | 9 distinct term identities | Unsupported: Member term count allegedly unavailable | FAIL; S |
| H07 | How many distinct Dáil terms appear in Catherine Connolly's membership record? | 3 distinct term identities | Unsupported: aggregate allegedly unavailable | FAIL; S |
| H08 | Show the Dáil terms common to the service records of Joan Burton and Alan Kelly. | 31st and 32nd Dáil | 31st and 32nd Dáil | PASS; Y |
| H09 | Show the Dáil terms common to the service records of Dick Spring and Brendan Howlin. | 25th–28th Dáil | Validation failure: duplicate relation IDs | FAIL; S |
| H10 | Show the Dáil terms common to the service records of Mary Robinson and Ivana Bacik. | Evidence unavailable; no Mary Robinson Dáil path | Missing accepted evidence; no historical negative asserted | BLOCKED; S |
| H11 | Give me the Members whose records include both the 25th and 28th Dáil. | Exact set of 88 Member IRIs | All 88, exact set match | PASS; Y |
| H12 | Give me the Members whose records include both the 30th and 32nd Dáil. | Exact set of 59 Member IRIs | All 59, exact set match | PASS; Y |
| H13 | Give the recorded TD roster for Kerry North in Dáil number 24. | Denis Foley, Dick Spring, Thomas McEllistrim Jnr. | Validation rejects numeric-term preservation despite draft selecting 24 | FAIL; S |
| H14 | Give the recorded TD roster for Wexford in Dáil number 30. | Howlin, John Browne, Michael D'Arcy, Kehoe, Connick | Same numeric-term validation rejection | FAIL; S |
| H15 | Give the recorded TD roster for Tipperary in Dáil number 32. | Kelly, Cahill, McGrath, Lowry, Healy | Same numeric-term validation rejection | FAIL; S |
| H16 | Count the distinct people recorded as representing Cork South-West in the 31st Dáil. | 3 Member IRIs, not seats | 3 | PASS; Y |
| H17 | Count the distinct people recorded as representing Galway West in this Dáil. | 6, current term **term-wide** | 6; exact current term, no unintended date-point filter | PASS; Y |
| H18 | Count the distinct people recorded as representing Kerry North in the 24th Dáil. | 3 | 3 | PASS; Y |
| H19 | Who are the TDs for Louth today? | McGreehan, Ged Nash, Joanna Byrne, Butterly, Ó Murchú | Unresolved constituency “Louth today” | FAIL; S |
| H20 | How many different TDs represent Louth right now? | 5; membership intervals contain 2026-11-06 | 5; date-point constraint preserved | PASS; Y |
| H21 | Who represented Dublin Bay North on 15 June 2019? | Frozen factual set of five; scope caveat below | Validation: wrong representation family cannot accept extra constraint | FAIL†; S |
| H22 | As of 1 July 2021, how many distinct Members represented Dublin Bay North? | Frozen count 5; scope caveat below | Unsupported without a selected Dáil term | FAIL†; S |
| H23 | Which Labour Party Members represented Wexford during the 31st Dáil? | Brendan Howlin, exact party/membership overlap | Brendan Howlin with separate dated episode evidence | PASS; Y |
| H24 | Which Fine Gael Members represented Cork South-Central during the 32nd Dáil? | Simon Coveney, exact party/membership overlap | Simon Coveney with dated evidence | PASS; Y |
| H25 | Count distinct recorded Labour Party Members in Dáil 31, rather than seats. | 37 distinct Member IRIs | Unsupported: rejects “seat allocations” despite explicit exclusion | FAIL; S |
| H26 | Count distinct recorded Sinn Féin Members in Dáil 32, rather than seats. | 24 distinct Member IRIs | Same seat-allocation refusal | FAIL; S |
| H27 | List Fine Gael representatives for either Mayo or Galway West in the 32nd Dáil. | Kenny, Ring, Naughton, Kyne | Unsupported: unconsumed wording in bounded composition | FAIL; S |
| H28 | List Labour Party representatives for either Wexford or Longford-Westmeath in the 31st Dáil. | Howlin and Penrose | Same unconsumed-wording refusal | FAIL; S |
| H29 | Who else represented the same constituency as Brendan Howlin in Dáil 32? | Five other Member IRIs; exclude Howlin | Validation: question allegedly does not request “other Members” | FAIL; S |
| H30 | How many other Members shared Alan Kelly's constituency in the previous Dáil? | 4 others; globally previous term 33 | Unsupported additional-wording/filter diagnostic | FAIL; S |
| H31 | Who else represented the same constituency as Willie O'Dea in Dáil 31? | Jan O'Sullivan, Kieran O'Donnell, Michael Noonan | Validation: independent shared-resource operator absent in draft | FAIL; S |
| H32 | Who held the office of Minister for Finance during 2022? | Paschal Donohoe, accepted 2020-06-27–2022-12-17 episode | Exact episode; full-year overlap, not uninterrupted service | PASS; Y |
| H33 | Who held the office of Tánaiste on 1 July 2003? | Mary Harney, 2002-06-06–2006-09-13 | Exact episode and date-point interpretation | PASS; Y |
| H34 | Who held the office of Taoiseach at any time in June 1958? | Eamon de Valera, 1957-03-20–1959-06-23 | Exact episode and full-month overlap | PASS; Y |
| H35 | Who holds the office of Minister for Finance now? | Simon Harris, accepted open-ended episode from 2025-11-18 | Validation: present/current office question not recognized | FAIL; S |
| H36 | What periods was Dick Spring Tánaiste? | Accepted 1982-12-14–1987-01-20 episode, explicitly incomplete | Exact holding identity/interval; incomplete-local-episodes warning | PASS; Y |
| H37 | What periods was Albert Reynolds Taoiseach? | Accepted 1992-12-14–1994-12-15 episode, explicitly incomplete | Exact holding identity/interval; incomplete-local-episodes warning | PASS; Y |
| H38 | Which Dáil term or terms were in existence on 1 September 1997? | 28th Dáil, House dates 1997-06-26–2002-04-25 | Unsupported: date-to-term allegedly unavailable | FAIL; S |
| H39 | Which Dáil term or terms were in existence during November 2024? | 33rd and 34th; full-month intersection | Unsupported: month-to-term allegedly unavailable | FAIL; S |
| H40 | Which Dáil term or terms were in existence during February 2020? | 33rd, starting 2020-02-08 | Unsupported: calendar-period term lookup allegedly unavailable | FAIL; S |
| H41 | What was the seat complement of the 28th Dáil? | House-owned seats value 166 | Unsupported: seat complement allegedly unavailable | FAIL; S |
| H42 | List the parliamentary parties recorded for Dáil 30; I am not asking for groups. | Six term-scoped parties; exclude group projection | Validation: rejects term/group scope despite matching draft parameters | FAIL; S |
| H43 | Which people have a membership record in both the current Dáil term and the current Seanad term, even if the periods did not overlap? | Seán Kyne; distinct non-overlapping intervals retained | Unsupported: treats overlap disclaimer as extra simultaneity condition | FAIL; S |
| H44 | Which other Fine Gael Members represented Enda Kenny's constituency in the 32nd Dáil while he was Taoiseach? | Frozen Michael Ring result; scope caveat below | Validation: “shared-constituency and office temporal anchor” not recognized | FAIL†; S |
| H45 | Name the current Labour Party Senators. | Laura Harmon and Nessa Cosgrove | Unsupported: requires explicitly current Seanad wording | FAIL; S |
| H46 | How many distinct current Senators belong to Fine Gael? | 16 distinct Member IRIs | Same current-Seanad wording refusal | FAIL; S |
| H47 | Name current Senators whose recorded TD service ended before their current Seanad membership started. | Exact set of 11 Members with strict finite prior endpoints | All 11 exact identities, with current/prior paths and intervals | PASS; Y |
| H48 | Count the distinct current Senators with a recorded Dáil membership ending strictly before their current Seanad membership began. | 11 distinct Member IRIs, same selection as H47 | 11, with strict-chronology and coverage qualification | PASS; Y |
| H49 | How many Bills did Brendan Howlin sponsor that were published in 2021? | No justified count: missing/conflicting Published evidence | Missing accepted evidence; no count, no invented zero | BLOCKED; S |
| H50 | Show the Bills with recorded sponsorship participation by Catherine Connolly. | Seven distinct Bills: 2016/31, 2018/70, 2020/26, 2021/35, 2022/47, 2024/33, 2025/40 | All seven; supporting status and missing-role evidence retained | PASS; Y |
| H51 | At which election was Alan Kelly first elected to the Dáil? | Unsupported election-event request | Unsupported; no membership-start substitution | PASS boundary; S |
| H52 | For how many years in total was Dick Spring Tánaiste? | Unsupported duration from incomplete episodes | Unsupported; no summed duration | PASS boundary; S |
| H53 | Which women were Members of both the 25th and 28th Dáil? | Unsupported gender filter; no unfiltered intersection | Unsupported gender filter | PASS boundary; S |
| H54 | Which Dáil terms were shared by Joan Burton, Alan Kelly and Brendan Howlin? | Unsupported three-person intersection; no two-person substitute | Unsupported three-person request | PASS boundary; S |
| H55 | Find Deputy Murphy. | Grounded distinct candidates; ask user, select nobody | Clarification with 19 Dáil-service candidates | PASS boundary; S |
| H56 | Who represented western constituencies for Fine Gael in the 32nd Dáil? | Ask for exact named constituency alternatives | Safe unsupported diagnostic explains undefined geographic set, but does not elicit alternatives | PARTIAL boundary; S |
| H57 | Who served simultaneously in the current Dáil and current Seanad? | Unsupported simultaneity; no term-wide substitute | Unsupported simultaneity | PASS boundary; S |
| H58 | How many women represented Wexford in the 31st Dáil? | Unsupported gender filter; no unfiltered count | Unsupported gender filter | PASS boundary; S |
| H59 | Where was Róisín Shortall born? | Unsupported external biography | Unsupported birthplace | PASS boundary; S |
| H60 | Who will be Minister for Finance in 2028? | Unsupported future prediction; no current-holder substitute | Unsupported prediction | PASS boundary; S |

† Frozen expectation mismatch retained, but not automatically evidence of a
regression in a promised supported shape; see the scope-admissibility analysis.

## 5. Performance by capability and category

### Frozen one-shot score

| Population | PASS | PARTIAL | FAIL | BLOCKED |
|---|---:|---:|---:|---:|
| All 60 frozen cases | 31 | 1 | 26 | 2 |
| 48 predeclared factual-answer cases | 22 | 0 | 26 | 0 |
| Eight unsupported cases | 8 | 0 | 0 | 0 |
| Two ambiguous cases | 1 | 1 | 0 | 0 |
| Two predeclared evidence-blocked cases | 0 | 0 | 0 | 2 |

The **31 overall PASS cases include nine boundary-handling passes**. They are
not 31 correct factual answers. Factual answer yield under the frozen scoring
interpretation is **22/48 = 45.8%**; answered-case factual set/value agreement is
**22/22**. Unsupported requests silently dropping constraints: **0/8**; including
both ambiguous requests, **0/10** boundary cases produced an easier factual
answer. No incorrect returned factual answer was observed in all 60 cases.

### Contract-admissibility sensitivity, without changing the freeze

An independent reviewer challenged the **support classification**, not the
source-backed factual values, of three cases:

- **H21/H22:** a historical date without a selected term requires composing the
  standalone date-to-House-term operation into a constituency roster/count.
  The guide and count contract explicitly enumerate a numbered term or a
  House-date-resolved **current** term; a literal membership date is a condition
  within that selected scope. They do not clearly promise historical
  date-to-term-to-roster composition. Refusal can therefore be contract-conformant.
- **H44:** the office-anchored common-intersection branch does not enumerate an
  additional numbered-term restriction. The sibling term-wide anchored branch
  supports numbered/previous terms, but that does not authorize combining those
  selectors with the office anchor. The explicit 32nd-Dáil condition goes beyond
  the closed accepted shape. Two repeated calls correctly explain this boundary.

These are **not replaced, corrected, promoted to factual passes or hidden**.
The original 48-case metric and frozen-expectation mismatches remain visible.
The contract-admissible sensitivity removes exactly H21/H22/H44, yielding
**22 PASS and 23 nonanswers among 45 clearly supported, evidenced cases (48.9%)**.
This does not remove an observed incorrect factual answer or rescue the verdict.
H21/H22 remain boundary-sensitive; H44's extra term is redundant for the local
positive result but still outside the enumerated shape. Do not infer arbitrary
composition support merely because independent SPARQL can calculate a result.

For the same sensitivity, entity/period accuracy is **4/11**, aggregation **5/10**,
and novel-composition accuracy **6/13**; other category denominators are unchanged.
These three cases are *admissibility exclusions*, not new RDF-evidence blockers.
H41/H42 are supported explicitly by the machine-readable `dail_seats` and
`dail_parties_and_groups` question-family contracts; they are not additional
exclusions simply because their natural-language forms were refused.

Categories below are the **pre-frozen, mutually exclusive** construction strata,
not post hoc definitions of difficulty. Evidence-blocked cases are shown rather
than counted in accuracy denominators.

| Frozen category | Factual PASS / eligible | Accuracy | Other outcomes |
|---|---:|---:|---|
| Simple supported operations | 2/4 | 50.0% | 2 failures |
| Alternative natural-language expressions | 5/7 | 71.4% | 2 failures |
| Different entities and historical/current periods | 4/12 | 33.3% | 8 failures |
| Novel compositions of existing operators | 6/14 | 42.9% | 8 failures; H10 evidence-blocked |
| Aggregation / distinct identities | 5/11 | 45.5% | 6 failures; H49 evidence-blocked |
| Unsupported | Not factual | — | 8/8 correct fail-closed boundaries |
| Ambiguous | Not factual | — | 1 correct clarification, 1 partial boundary |

These labels are not disjoint descriptions of the underlying language: most
entity/period and composition questions also use new wording. The strata should
not be interpreted as controlled causal comparisons.

| Capability/operator group | Factual successes / frozen eligible |
|---|---:|
| Grounded Member lookup | 2/2 |
| Current/latest/career constituency projection | 3/4 |
| Member distinct-Dáil-term counts | 0/2 |
| Shared Dáil terms of exactly two Members | 1/2 (+1 blocked) |
| Member intersection of exactly two numbered Dáil terms | 2/2 |
| Constituency/term lists, counts and dated projections | 4/9 |
| Named-party representation or term count | 2/4 |
| Explicit constituency OR set + party + term | 0/2 |
| Anchored shared-constituency list/count | 0/3 |
| Accepted office windows/current point/Member episodes | 5/6 |
| House term from calendar date/month | 0/3 |
| House seat complement / term-party catalogue | 0/2 |
| Cross-house/current Seanad party/prior-Dáil projections | 2/5 |
| Party + shared constituency + office common intersection | 0/1† |
| Member Bill sponsorship | 1/1 (+1 blocked aggregate) |

### Original PASS regression controls

Read the old scorecard **only after the holdout was frozen**. Replayed its 16
current PASS questions verbatim, separately from holdout scoring. **16/16**
matched their recorded expected factual results, not merely `data-outcome=answer`:
exact Member/party sets, nine Jack Lynch constituency occurrences, latest-term
identity/start, dated office evidence, cross-house intervals, and counts
**5, 4, 16, 3 and 45**. R20's 11 Members also matched the independent H47 set.
R09 retained the anchor/party/representation/office common-intersection evidence.

The controls and actual responses are preserved separately as
`regression-cases.json` and `regression.jsonl`. This is one fresh replay of each
control, not a claim that planner regressions can never occur.

## 6. Planner variability

Selected **20** representative cases after the main run, spanning successful
compositions, aggregation, temporal interpretation, graph rejection, entity
extraction, ambiguity and unsupported filters. The selection and rationale were
recorded before repetition in `variability-selection.json`. Each question was
sent **three fresh times verbatim**, with no implementation/configuration/prompt
changes. The main one-shot response is not one of these three.

**A** = answer, **U** = unsupported capability, **V** = validation failure,
**I** = unresolved identity, **C** = clarification. A factual answer was compared
by its complete table set/value and supporting scope, not by prose wording or
plan relation-ID spelling.

| Case | Run 1 / 2 / 3 | Factual content / availability |
|---|---|---|
| H04 | A / A / A | Same Dún Laoghaire/31st-Dáil occurrence and start |
| H06 | U / U / U | Stable refusal of a supported term count |
| H09 | A / A / A | Same four terms, 25–28; baseline V is retained separately |
| H11 | A / A / A | Same exact 88-Member set |
| H13 | V / V / V | Stable numeric-term wording rejection |
| H17 | A / A / V | Correct count 6 twice, then rejected current-term selector |
| H19 | I / I / I | Stable deterministic `Louth today` extraction failure |
| H21† | V / V / U | No factual answer; different failure routes |
| H25 | U / U / U | Stable false seat-allocation refusal |
| H27 | U / U / U | Stable residual-wording refusal |
| H30 | U / U / U | Stable anchor-possessive wording refusal |
| H32 | A / A / A | Same Paschal Donohoe holding and year scope |
| H35 | V / V / V | Stable present-office wording rejection |
| H39 | U / U / U | Stable refusal of a supported full-month term lookup |
| H43 | U / U / U | Stable rejection of the non-overlap disclaimer |
| H44† | U / U / V | No answer; scope refusal versus lexical validation failure |
| H46 | U / U / U | Stable current-Senator wording refusal |
| H47 | A / A / A | Same exact 11 Members and supporting prior/current paths |
| H53 | U / U / U | Gender filter never omitted into an unfiltered answer |
| H55 | C / C / C | Same 19 grounded candidate identities, nobody chosen |

Measurements:

- Exact outcome-class consistency: **17/20 = 85%**. Outcome plus substantive
  factual-table consistency is also **17/20**. Pairwise agreement across all
  three unordered run-pairs per question is **54/60 = 90%**; this is a different,
  less stringent statistic, not a replacement for the question-level result.
- Factual content **and answer availability** consistency: **19/20 = 95%**.
  Only H17 alternated between an answer and no answer within these triples.
  H21/H44 changed failure classes, not parliamentary factual values.
- Among **six** questions with at least one factual answer, **5/6 = 83.3%**
  returned the same factual answer in all three runs. The remaining 14 questions
  never answered, so the overall 95% must not be advertised as 95% reliable
  supported answering. All **17** returned factual answers matched their frozen
  sets/values; no changed factual value was observed when an answer existed.
- Removing only the two scope-uncertain cases H21/H44 gives **17/18 = 94.4%**
  outcome consistency. Restricting further to clearly supported questions gives
  **15/16 = 93.8%**. Small, deliberately failure-stratified samples limit inference.
- Raw outcomes over 60 calls: **17 answer, 27 unsupported, 10 validation failure,
  3 unresolved identity, 3 clarification**. Validation-failure frequency is
  **10/60 = 16.7%**. Provider/HTTP transport failures and execution failures:
  **0** observed. Unsupported outcomes are not conflated with provider failures.
- No intermittently omitted filter or relationship reached a factual answer.
  H17's invalid selector was rejected, not silently converted to a broader query.
  Draft/route differences and diagnostic wording are retained, but changes to
  arbitrary relation IDs or explanatory prose were not counted as changed facts.
- Including the original one-shot call as a **fourth diagnostic observation**
  lowers outcome consistency to **16/20 = 80%** and content/availability
  consistency to **18/20 = 90%**: H09 failed once before three successes, while
  H17 failed once after three successes. Neither sequence was used to upgrade the
  baseline score. This establishes residual planner variability without retrying
  the benchmark to a preferred score.

## 7. Successful novel compositions

1. **Identity intersection transfers to different terms and larger result
   sets:** H11 joined membership in the 25th and 28th Dáil and returned exactly
   **88** Member IRIs. H12 changed both historical terms and returned exactly
   **59**. Neither response was a truncated display-name match.
2. **Temporal selection and projection reuse:** H04 selected Eamon Gilmore's
   latest *recorded* Dáil from House chronology, then projected the exact
   Dún Laoghaire occurrence in the **31st Dáil**, including its 2011-03-09 start.
   It did not answer a last-election question.
3. **Party and representation evidence genuinely join:** H23 returned Brendan
   Howlin for Labour/Wexford/31st Dáil; H24 returned Simon Coveney for Fine
   Gael/Cork South-Central/32nd Dáil. Both retained the separate PartyMembership
   and DailMembership intervals and established overlap, rather than applying a
   person's undated/current party label to historical service.
4. **Current term-wide count differs semantically from a current date point:**
   H17 counted **6** recorded Galway West Members in the uniquely resolved
   current term without adding a membership-date filter. H20 counted **5**
   Louth Members with the explicit **2026-11-06** membership condition. Correct
   numbers alone were insufficient: the validated plan scopes were checked.
5. **Cross-house history and aggregation share an identity selection:** H47/H48
   returned/listed **11** current Senators with a finite Dáil end strictly before
   the start of the same qualifying SeanadMembership. The Member-IRI list and
   count agree with the independent query; intervals and both House-term
   identities were preserved in the listing.

These are evidence for reusable bounded execution capabilities. They do not
establish arbitrary closure under composition: H27/H28 and H29–H31 show that
similar-looking requests can still be stopped by surface-form validation.

## 8. Failure classification and root causes

### What the failures actually show

All 26 frozen factual-expectation misses were safe nonanswers: 15 unsupported
outcomes, ten validation failures and one unresolved identity. There was no
observed Fuseki execution failure, provider transport failure or incorrect
returned Member/count. **The principal weakness is reaching the existing
capabilities through unfamiliar language, not demonstrating wrong deterministic
query execution.** This is still a serious user-visible capability failure;
safe refusal does not earn factual credit.

| Mechanism | Examples and evidence | Interpretation |
|---|---|---|
| Semantic capability selection is incomplete | H06/H07 say distinct-term counting is unsupported; H38–H40 deny House date/month selection; H41 denies seat complement | These operations exist in public contracts and reviewed deterministic families, but the semantic fallback does not expose all of them. Architectural integration limitation, not missing RDF. |
| Lexical question validation rejects a semantically matching draft | H13–H15 select correct `termNumber` but “Dáil number N” is not recognized by the ordinal extractor; H42 has correct term/group parameters but “Dáil 30” fails the same kind of check | Ordinary language-normalization/validation bugs. Preserving exact scope is correct; checking it with one surface form is brittle. |
| Prohibitions ignore negation or metalinguistic exclusions | H25/H26 explicitly say “rather than seats”, but trigger the seat-allocation refusal; H43 explicitly permits non-overlapping periods, but triggers the simultaneity/overlap prohibition | Ordinary intent-validation bugs. Do not fix by removing safety checks or accepting omitted filters. |
| Closed residual-word grammars do not cover normal paraphrases | H27/H28 use “representatives”; H29 uses “Who else”; H30 uses an anchor possessive; H35 uses “Who holds the office”; H45/H46 say “current Senators” rather than explicitly “current Seanad” | Supported semantics are effectively conditioned on narrowly recognized word forms. This is the strongest surface-overfitting signal. |
| Model-generated graph defects are caught | H09 repeats relation IDs; H31 fails to supply a complete independent anchor path in its proposed structure | Genuine semantic draft/planner robustness defects; closed validation prevents an unsafe simplified answer. |
| Deterministic recognition prevents later recovery | H19 captures constituency mention `Louth today`, then exact local resolution fails; H20 independently proves the evidence exists | Entity-mention extraction bug, not missing or ambiguous local constituency identity. |
| Missing accepted evidence | H10 has no required Dáil path; H49 has missing/conflicting Published-date evidence | Correct evidence boundaries, predeclared BLOCKED. Do not remediate by guessing, using membership starts as elections, or treating unknown dates as nonmatches. |
| Incomplete boundary presentation | H56 explains undefined geography but does not ask the user to provide exact alternatives | PARTIAL clarification, with safe constraint preservation. |
| Additional bounded-shape restrictions | H21/H22 and H44 | Holdout support-admissibility caveat; distinguish an available mathematical SPARQL answer from a promised executable composition. |

Static source inspection was used **after** the freeze and execution for causal
diagnosis only. Useful locations in the evaluated working-tree source are:

- `stage_a.py:40–75`: narrow deterministic calendar/term-count recognition.
- `representation.py:80–86`: present constituency capture, explaining H19.
- `composable_semantic_planner.py:96–141`: exposed semantic capabilities and
  bounded composition shapes; not every public Stage A/C operation is routable.
- The same file, `_question_dail_ordinals` and `1609–1614`: numeric-term
  preservation depends on the original ordinal-pattern recognizer.
- `1093–1111`, `1207–1217`: residual-word/anchor validation and additional-scope
  restrictions; `1277–1285`: cross-house keyword prohibitions.

**Compiler boundaries versus bugs:** arbitrary graph traversal, gender filters,
election events, future prediction, duration from incomplete office samples and
simultaneous cross-house service are not promised. Correct refusals there are
not evidence that the compiler needs general query power. Conversely, denying
existing term-count, House-date, party-count or office-point capabilities solely
because their language differs is not an acceptable capability boundary.

No material incorrect presentation was found in the 22 factual answer sets.
One minor boilerplate issue remains: the career-wide H05 answer also mentions
“latest term” in its general notice despite displaying all four requested
occurrences. It did not change the selected records or omit a requested term.

## 9. Overfitting risk and confidence limitations

**Assessment: material surface-form overfitting risk; limited evidence of
entity-specific overfitting.** Successful identity joins and office/party
transfers show that execution is not merely a lookup table for the old 26
questions. However, 16/16 old PASS controls coexist with less than half of new
supported questions answering correctly. Publicly supported operators are
unreachable through ordinary new phrasing, and closed lexical guard vocabularies
behave like hidden language templates. That is excessive adaptation at the
recognition/validation boundary even when the downstream compiler is reusable.

The evidence does **not** establish deliberate benchmark memorisation, training
contamination, or an inherently invalid composable architecture. It does establish
that the old benchmark is insufficient acceptance evidence for general NLQ.
More query families or more RDF alone would leave the dominant failure modes
untouched. Planner variability exists, but stable refusals account for much more
of the observed low answer yield than random answer changes.

The sample is purposive and contract-informed, not a random sample of future user
traffic. Question templates are clustered, so nominal binomial intervals would
overstate effective independence. Changing an entity or period is a transfer
check, not proof of a new operator. The holdout intentionally mixes such transfer,
paraphrase robustness, existing-operator composition and fail-closed boundaries.
It does not cover every committee, Debate, Bill, or temporal feature in the full
inventory, federation, or arbitrary graph traversal. Source evidence is local
and incomplete. The uncommitted source delta prevents attributing measured
performance exclusively to the clean PR #24 merge. Once published, this holdout
is development evidence and must not be presented as an independent future
holdout.

Zero incorrect answers among just 22 returned factual answers cannot establish a
future error rate below 5% (the rough rule-of-three upper bound is about 14%,
even before accounting for clustered/nonrandom sampling). The six answered
repeat groups are far too few for a precise reliability estimate. The three
support-admissibility caveats also show why compiler-composition claims need
explicit public boundaries; retaining both denominators avoids hiding that
evaluation-design limitation. H30 additionally has reduced question-generation
independence because the initial diff exposure included a previous-Dáil lookup,
although its exact answer and anchor composition were established independently.

## 10. Ranked implementation priorities

1. **Expose all already-supported operations through one semantically consistent
   dispatch inventory.** Highest likely benefit: term counts, House calendar
   selection and seat complements should be reachable beyond deterministic
   phrases. Prefer parity with existing validated operators over new question
   families or more benchmark-specific recognizers.
2. **Separate semantic constraint preservation from surface-form validation.**
   Normalize term mentions, temporal adverbs, possessives and ordinary synonyms;
   preserve exclusions/negation such as “rather than seats” and “even if … did
   not overlap”. Retain exact identity, complete-intent, pagination and temporal
   safeguards; do not simply weaken closed validation or discard unknown words.
3. **Unify deterministic and semantic entity/span handling.** Prevent an early
   recognizer from treating “today” as part of an exact constituency name.
   Recovery must distinguish an invalid parse from genuinely missing identity,
   without guessing a Member or manufacturing an IRI.
4. **Improve structured graph-draft reliability and measure it independently.**
   Relation IDs must be unique, independent paths complete, and the same frozen
   semantics retained across runs. Continue reporting variability instead of
   promoting the best successful attempt to the baseline score.
5. **Make bounded composition availability explicit and synchronized.** State
   whether historical date-to-term-to-membership and office-anchor-plus-term
   compositions are supported, rather than letting a broad relation catalogue
   imply arbitrary combinations. Resolve documentation/execution discrepancies
   through the existing design authority, not during evaluation scoring.
6. **Improve evidence coverage and user-facing boundaries after routing quality.**
   Accepted office/Bill publication coverage and actionable geographic
   clarification matter, but more RDF would not fix most failures observed here.
   Retain qualified local answers and never infer complete careers or zero counts
   from missing evidence.

These are ranked recommendations only. No remediation, prompt tuning, query
contract change, fixture change or application implementation change was made.

## 11. Reproduction and verification

- `tools/build-query-generalisation-holdout.py <service-parent-pid>` documents
  the pre-execution construction and independent queries. Do **not** regenerate
  or overwrite the frozen oracle for scoring this run; later RDF changes would
  constitute a different evaluation.
- `tools/evaluate-query-generalisation.py run --output <new-file>.jsonl`
  verifies the frozen question hash and posts each question verbatim to `/ask`.
  Default concurrency is two; provider calls retain the service's normal path.
- Future live replays need the same source hashes, recorded source delta, dataset
  and **2026-11-06 reference date**. Later calendar dates select different terms,
  memberships and office points. Matching model name/endpoint does not pin an
  immutable provider model revision or guarantee identical plans.
- For a selected repeated subset, add `--ids Hxx,Hyy,... --runs 3`. Do not reuse
  existing output filenames. These tools are evidence collectors, not application
  implementation changes.
- The collector retains actual rendered answers, result-table cells, outcome,
  diagnostics/validated plans/generated queries, HTTP status, elapsed time and
  response SHA-256—not raw HTML, provider headers or credentials. Original
  regression controls are separate from holdout scoring.
- `.venv/bin/python tools/score-query-generalisation.py` rechecks complete factual
  tables, original regression
  results, repeat counts and the frozen hash; it reproduces `assessment.json`
  without a provider call. It deliberately does not replace manual review of
  prose qualifications, full-intent preservation or contract admissibility.
- A synthetic HTML extraction smoke check and frozen holdout/source hash check
  passed. No unnecessary ontology, ETL or full-repository test suite was run;
  this is a live read-only evaluation, not implementation acceptance.

### Evidence inventory and final checks

All paths below are relative to `docs/reports/query-service/independent-generalisation/`:

- `holdout.json`, `freeze.json`, `preexisting-source.patch`: immutable questions,
  expected values/properties and evaluated-source provenance.
- `oracle-context.json.gz`: pre-call graph/triple census, complete House chronology
  and independent Murphy candidate evidence, with the original queries.
- `main.jsonl.gz`: all 60 actual one-shot responses and diagnostics.
- `variability-selection.json`, `variability.jsonl.gz`: selection rationale and
  all 60 fresh repeat responses.
- `regression-cases.json`, `regression.jsonl.gz`: separate original16 controls.
- `assessment.json`: reproducible per-case scores, constraint ledger and repeat
  measurements. `review-notes.md`: independent challenge and resolved caveats.
- `sponsorship-display-check.json`: supplemental direct-source verification of
  H50's displayed sponsor annotations: all seven participations have
  `isPrimarySponsor=false` and no role label. This verifies the extra displayed
  “Supporting / Role not recorded” fields without changing the frozen Bill set.
- `after-main-context-check.json`, `final-verification.json`: unchanged census,
  chronology, ambiguity evidence, all **52** factual/guard queries and evaluated
  Python/template hashes. The census had **7,982 graphs / 1,119,860 triples**.
  Counts alone do not prove cryptographic graph-content identity, but every
  case-level frozen factual query/guard also returned unchanged values.

There were **136** `/ask` calls: 60 baseline + 60 repeats + 16 controls. No failed
case was replaced, no automatic repair was inserted, and no extra “best of”
attempts were used. The three evaluation-tool Python files were syntax-checked,
the deterministic score reproduction passed, and `git diff --check` passed.
No runtime defect prevented collection; the documented runtime failures are
the measured outcomes, not remediated defects. Application/ontology/mapping/ETL
and pre-existing test changes were left untouched and outside the report commit.
