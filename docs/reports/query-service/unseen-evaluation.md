# Query Service — Unseen Questions Baseline Evaluation

**Evaluation date:** 2026-10-30
**Branch:** `query-service-unseen-evaluation`
**Code under test (repository SHA):** `a210e1992a1a3a30d727ae3c9e46201877468de5`
**Fixed `asOf`:** `2026-10-28`

## Approval, source and scope

The review source was retrieved directly from
`origin/query-service-unseen-questions-review` at `d1c1367848ec5c9ff5db03b6c650a28ce0e564c7`.
That branch tip still labels the file a draft and all its approval boxes were
unchecked. The user explicitly approved those exact 36 questions during this
evaluation. The evaluation branch therefore contains the separate frozen copy
[`poc/specs/query-service-unseen-questions-approved.md`](../../../poc/specs/query-service-unseen-questions-approved.md).
All 36 question headings and question sections are unchanged; only approval,
track and provenance metadata was updated.

The current technical specification is
[`poc/specs/query-service-plan.md`](../../../poc/specs/query-service-plan.md).
Redesign requirements cited by the approved-question file are archived
historical context, not the current specification.

| Artifact | Identity |
| --- | --- |
| Review-branch source file | `poc/specs/query-service-unseen-questions-draft.md` |
| Source Git blob SHA-1 | `ef3a07d2c3ace8c92a0f7ae565d3019d446df157` |
| Source file SHA-256 | `f0e8945d143d72b4055316748f13e79f06be821e9ef6540c70290f760020ab6f` |
| Frozen evaluation copy SHA-256 as evaluated | `fa41f56f81d24ae17c76cfb350a948dd0b3c8c56d938a4dbaa5c5053c1039b00` |
| Frozen evaluation copy SHA-256 after documentation-link correction | `a580ed9416b0aea6bf221623a7cdcf09e6bd00a3299db8a0d6be905d8c0f2e4e` |

This is a baseline of the unchanged Query Service, not a repair exercise. The
application, planners, compilers, query contracts, mappings, ontology, and
source fixtures were not changed. The evaluation branch was already present at
the requested name and clean at `origin/master` SHA above; the review branch
was not merged. The only additions are the frozen question copy, this report,
and a task-specific route observation script.

## Method and dataset

Every verbatim question was POSTed through the integrated FastAPI
`POST /ask` route with `mode=phase2`, using the same `create_app()` routing and
execution path as the browser. This is not a direct planner call or the Phase 1
NL-to-SPARQL path. The evaluation runner clears LLM credentials in its process;
no LLM request was made. The Phase 2 dispatch was allowed to return its normal
outcome. The question-answer execution was instrumented without changing the
application code. Fixed `OIR_NLQ_AS_OF_DATE=2026-10-28` was set for all posts.

The current read-only Fuseki readiness check returned `ready` for
`http://localhost:3030/houses/query`; it detected Houses, Parties,
Constituencies, Members, Committees, Bills, Offices, Administrative Units,
Office Holdings, and Cabinet Memberships. The running container was
`oireachtasontology-fuseki-1`, image `stain/jena-fuseki:5.1.0`. No dataset
rebuild, reload, broad inventory, or ingestion was performed.

The committed development-data evidence documents the intended non-authoritative
baseline identity as
`sha256:9da63abc5878387f991e4d4717f35cca67606850db34be589e0a8fc0cc1504e2`
(7,981 bootstrap-owned graphs and 1,119,467 triples; the accepted live run also
contained three unrelated sentinel graphs). **The exact identity of the
currently running Fuseki dataset was not verified.** The readiness endpoint
does not report that identity, and the available worktree did not contain a
local baseline artifact to match. Therefore source-selection and prior
development evidence below are not represented as a verified live-dataset
oracle.

### Common integrated-route observation (`O0`)

All 36 requests returned HTTP 200 with the same Phase 2 outcome:

```text
status: unsupported_capability
plan: none
diagnostic: This question is outside the supported previous-Dáil representation pattern.
answer SPARQL: none
question-specific query execution: not attempted
result: none
```

Each `/ask` response also performed the application's ordinary read-only
Fuseki readiness probes while rendering the page. Those are not answer queries.
Thus **zero of 36 questions generated or executed an answer query**. This
shared diagnostic and lack of plan/query are recorded as `O0` in every matrix
row. No question was ambiguously resolved, and no answer was produced with a
dropped constraint.

## Results matrix

Outcome codes are mutually exclusive primary outcomes:

- **CE — Correct execution:** supported plan executed and result correct.
- **CU — Correct unavailability/clarification:** no answer is returned where
  an essential semantic relation is not represented; fail-closed refusal is
  credited as safe. The generic diagnostic remains a quality limitation.
- **UA — Unsupported-but-answerable:** reviewed base facts/source evidence
  support answering, but the integrated planner rejected the wording or
  composition.
- **IF — Interpretation failure:** the request required a clarification,
  temporal interpretation or input validation that the observed outcome did
  not provide.
- **UI — Unsafe/incorrect answer:** an answer query ran unsafely or an answer
  silently lost an essential constraint.
- **DL — Data-limited:** known missing, quarantined or incomplete source evidence
  prevents a reliable answer; this is not scored as a planner failure.

`O0` means the common observation above: no plan, no answer query, no execution,
no result. “Mapped” distinguishes facts present in reviewed mappings/query
contracts from whether the current Phase 2 planner can compose them. `UA`
entries are potential answerability assessments based on reviewed mappings and
the documented selected data; since no answer query ran and the live dataset
identity is unverified, they are **not** claims of live result correctness.

### Research-style questions

| ID | Question (verbatim) | Intended interpretation and essential constraints | Reviewed mapping / data evidence | Observed / execution | Primary outcome and failure class |
| --- | --- | --- | --- | --- | --- |
| U01 | Who represented Dublin Central in the 31st Dáil? | All distinct Member identities representing the term-specific Dublin Central occurrence in the numbered 31st Dáil; do not substitute previous/current term. | House-term ordinal, membership-in-term, constituency-in-term and representation facts are queryable; current compiler only has a previous-term representation family. | O0 | **UA** — fixed-family/ordinal composition miss. |
| U02 | Which constituencies did Micheál Martin represent during his Dáil career? | Distinct Dáil constituency occurrences and their terms across the resolved Member's career; do not merge same-label resources without identity evidence. | Member membership, term and representation facts are mapped; the source selection includes Member history. Career-wide grouping is not a current plan family. | O0 | **UA** — mapped relationships, unsupported career-wide composition. |
| U03 | Which Members served in both the 32nd and 33rd Dáil? | Intersection of distinct Member identities with independently evidenced membership in each numbered term. | Member-to-membership and membership-to-term relations are mapped; set intersection is not a current answer shape. | O0 | **UA** — mapped facts, unsupported set operation. |
| U04 | Which members of the 25th Seanad subsequently served in the 33rd Dáil? | Same enduring people in the specified Seanad and later Dáil terms; require both term memberships. | Seanad and Dáil membership/term links are mapped; no cross-House intersection family exists. | O0 | **UA** — mapped facts, unsupported cross-House composition. |
| U05 | Were any TDs replaced in Cork South-West during the 33rd Dáil? | Detect a change in term-scoped constituency representation and identify outgoing/incoming Members with intervals; party changes are not replacement. | Dated membership and `isRepresentativeFrom` facts are mapped. No current family compares all time-bounded constituency representatives within an ordinal term. | O0 | **UA** — mapped temporal facts, unsupported replacement timeline. |
| U06 | Which political parties were represented by TDs for Galway West during the 33rd Dáil? | Distinct enduring party identities whose Member affiliation overlaps the specified constituency representation and term; do not use a current party retrospectively. | Member party episodes, reviewed party-identity links, constituency representation and term facts are mapped; the cross-join/overlap is not compiled. | O0 | **UA** — mapped relations, unsupported temporal multi-join. |
| U07 | Which committees did Catherine Connolly serve on during the 32nd Dáil? | Distinct term-specific Committee incarnations with accepted Member membership in the specified Dáil term. | Committee membership and Committee-in-term relations are mapped; the current compiler resolves a current Committee or counts memberships, not this historical join. | O0 | **UA** — mapped facts, unsupported historical Committee composition. |
| U08 | Who was Minister for Health on 1 July 2020? | Point-in-time holder of the named office on the inclusive calendar date, or a precise local-evidence limitation. | OfficeHolding is mapped, but the reviewed local office registry contains only Taoiseach, Tánaiste and Minister for Finance; Minister for Health identity/holding is absent. | O0 | **DL** — missing office identity/holding evidence. |
| U09 | Which people have held both Taoiseach and Minister for Finance? | Member-identity intersection across separate holdings of both named offices; they need not overlap in time. | Both OfficeHolding relations are mapped and both office identities are registered, but the development evidence explicitly says 22 accepted holdings across three offices are not complete historical coverage. | O0 | **DL** — historical officeholding coverage cannot certify the complete set. |
| U10 | Which Bills were sponsored by Sinn Féin TDs in 2024? | Bills with recorded sponsor Participations attributable to Members evidenced as Sinn Féin TDs at sponsorship time; require contemporaneous affiliation. | Bill→Participation→Member and dated party episodes are mapped, but a sponsorship-time relation/date is not exposed by the reviewed Query Service contract. | O0 | **CU** — safe no-answer for an unavailable temporal relationship; diagnostic does not name the missing sponsorship-time evidence. |
| U11 | What stage had Bill 23 of 2025 reached by 30 June 2026? | Resolve exact Bill and select latest source-backed event on or before the cutoff, not present status. | Bill 2025/23 is documented in the preserved capture; typed lifecycle activities and event dates are mapped. Existing Bill history route does not filter status at a historical cutoff. | O0 | **UA** — mapped lifecycle evidence, unsupported as-of selection. |
| U12 | Did the Committee of Public Accounts hold any sittings in September 2024? | Determine a positive from an actual PAC sitting in that calendar month; a partial slice cannot prove a historical No. | DebateSitting→DebateRecord/date is mapped, but the Query Service contract has no Committee→sitting relation. Pinned local Debate evidence is only 2015-07-02 Dáil/Seanad and PAC 2026-09-24, not September 2024. | O0 | **DL** — requested-period evidence is absent and Debate coverage is explicitly partial. |

### Capability recombinations

| ID | Question (verbatim) | Intended interpretation and essential constraints | Reviewed mapping / data evidence | Observed / execution | Primary outcome and failure class |
| --- | --- | --- | --- | --- | --- |
| U13 | Which TDs represented Dublin Central in the 32nd Dáil but not the 33rd? | Set difference of distinct Member identities for the same constituency in both named terms; absence requires adequate coverage. | Membership, term and representation facts are mapped; set difference across two bound terms is not an answer shape. | O0 | **UA** — mapped facts, unsupported set difference. |
| U14 | Who represented the same constituency as Micheál Martin in the 33rd Dáil? | Resolve his term-specific constituency occurrence, join other Members to that same IRI, and exclude the anchor Member. | Member membership and representation facts are mapped; the compiler does not support the independent Member referents/self-join. | O0 | **UA** — mapped facts, unsupported self-join. |
| U15 | Which Dáil terms did Aengus Ó Snodaigh and Mary Lou McDonald both serve in? | Independently resolve both Member identities and intersect their Dáil-term identities. | Member-to-membership and membership-to-term facts are mapped; two same-type referents and their intersection are not compiled. | O0 | **UA** — mapped facts, unsupported two-member composition. |
| U16 | Which Sinn Féin TDs represented Dublin South-Central during the 33rd Dáil? | Members with contemporaneous party affiliation and constituency representation in the specified term; preserve interval uncertainty. | Party episode/identity and Member membership/representation facts are mapped; no current family composes the cross-path overlap. | O0 | **UA** — mapped facts, unsupported temporal multi-join. |
| U17 | How many different TDs represented Dublin South-Central across the 32nd and 33rd Dáil? | Count the union of distinct Member identities across both terms, deduplicating Members present in both. | Membership, term and representation facts are mapped; the requested union-plus-count-distinct is not implemented. | O0 | **UA** — mapped facts, unsupported distinct union aggregate. |
| U18 | Did Stephen Donnelly join Fianna Fáil before or after he first became a Minister? | Compare first dated Fianna Fáil affiliation with first accepted Minister officeholding; do not substitute CabinetMembership or infer earliest status from incomplete history. | Party episodes and OfficeHolding are mapped, but the local registry/accepted holdings cover only three office identities and 22 incomplete holding records; a full Minister history is unavailable. | O0 | **DL** — missing first-office evidence/coverage. |
| U19 | Who held the office of Minister for Finance immediately after Paschal Donohoe's 2022 tenure ended? | Use the same office identity and dated holdings to find an evidenced chronological successor; do not invent a succession edge or assume no gap. | OfficeHolding intervals are mapped; the cited Donohoe tenure exists, but the accepted holdings do not establish a complete transition sequence. | O0 | **DL** — incomplete holding sequence prevents a reliable successor claim. |
| U20 | Which Ministers for Finance also represented Dublin Central while holding that office? | Intersect Finance holding intervals with the same Member's Dublin Central representation intervals. | Officeholding and Member representation are mapped; accepted Finance holding coverage is not complete enough to establish an exhaustive answer. | O0 | **DL** — incomplete Finance holding coverage. |
| U21 | Which Bills introduced in 2024 had at least two different named sponsors? | Select by a dated introduction/presentation event in 2024 and count distinct Member sponsors, not Participation rows or legislative year. | Sponsor Participation is mapped. The reviewed Bill mapping does not provide the required dated introduction event as a queryable lifecycle fact; `admissibility-for-introduction` is explicitly not modelled, and `methodURI` alone is not an event date. | O0 | **CU** — safe refusal where the required introduction-date capability is not represented. |
| U22 | Which Bills sponsored by Stephen Donnelly had not been enacted by 31 December 2024? | Resolve sponsor identity and derive non-enacted status at the historical cutoff from dated lifecycle evidence; never use present status or absence of an Enacted event alone. | Sponsor links, typed lifecycle events and dates are mapped. The compiler has sponsor and current-status families but no historical as-of status composition. | O0 | **UA** — mapped facts, unsupported historical status composition; sufficiency was not tested. |
| U23 | Which Dáil debates took place in the first seven days after Micheál Martin first became Taoiseach? | Anchor a seven-calendar-day window to the first accepted Taoiseach holding and list actual Dáil sittings only. | OfficeHolding and DebateSitting/date facts are mapped. The cited accepted Martin holding begins 2025-01-23; it does not establish his first tenure, and the pinned Debate slice has only three records. | O0 | **DL** — first-holding and relevant Debate evidence/coverage are insufficient. |
| U24 | Which dates in July 2015 had both a Dáil debate and a Seanad debate? | Same-day intersection of actual Dáil and Seanad sittings within July 2015; not a record count or written-answer date. | DebateSitting/date facts are mapped. The selected source evidence contains both a Dáil and a Seanad record on 2015-07-02; the route has no month-wide cross-House intersection. | O0 | **UA** — documented positive source evidence, unsupported cross-House date composition; no live result query ran. |

### Boundary and adversarial questions

| ID | Question (verbatim) | Intended interpretation and essential constraints | Reviewed mapping / data evidence | Observed / execution | Primary outcome and failure class |
| --- | --- | --- | --- | --- | --- |
| U25 | Which Michael Collins represented Cork South-West? | Use constituency service to ground the right local Member; return a unique identity only if supported, otherwise show distinguishable candidates. | Member identity and membership/representation facts are mapped; the current resolver does not compose this constraint into same-name resolution. | O0 | **UA** — mapped contextual evidence, unsupported constrained resolution. |
| U26 | Who chaired the Good Friday Agreement Committee in September 2026? | Resolve Committee incarnation and dated chair evidence separately; distinguish identity conflict from missing chair evidence. | Member source mapping contains a Chair role, but `hasCommitteeRole` is not a queryable Query Service predicate. The Good Friday identity is quarantined/conflicted and no current roster is established. | O0 | **DL** — current Committee identity/roster evidence is not available. |
| U27 | Did all the TDs in the 33rd Dáil vote for the Artificial Intelligence Companion Services Bill in 2026? | Recognize the prior-Dáil cohort, Bill and vote claim; flag the temporal mismatch and never infer votes from sponsorship/party/attendance. | No Bill-linked vote relation or voting record path is in the reviewed Query Service mapping. | O0 | **CU** — safe no-answer for genuinely unsupported voting evidence; the generic response did not explain the cohort/date mismatch. |
| U28 | What did Aengus Ó Snodaigh say about housing in the Dáil last month? | Resolve “last month” from 2026-10-28 as September 2026 and return attributable transcript text only through an approved retrieval path. | Debate metadata/link is mapped, but transcript text/speaker-topic retrieval is not in RDF or an approved Query Service path. | O0 | **CU** — safe no-answer for unavailable transcript retrieval; no quote was fabricated. |
| U29 | Which was enacted first, Bill 23 of 2025 or Bill 48 of 2024? | Resolve both exact Bill identities and compare dated Enacted events only if both are evidenced. | Bill lifecycle dates are mapped and 2025/23 is documented; the exact 2024/48 graph is quarantined/absent in the documented development dataset. | O0 | **DL** — one required Bill source graph is absent; no comparative oracle is available. |
| U30 | How many TDs were in the 33rd Dáil, including replacements? | Clarify seat complement versus distinct people who served; if presenting both, use the exact seat total and a complete replacement roster. | HouseTerm seats and Member memberships are mapped, but a seat total is not the number of distinct people. The user explicitly requires a clarification or properly evidenced distinction. | O0 | **IF** — ambiguity was not clarified; generic previous-Dáil rejection did not distinguish seats from people. |
| U31 | Which Members of the 33rd Dáil never belonged to any political party? | Treat “never” as a lifetime negative requiring a complete affiliation history and full roster; do not infer from absent triples. | Party-membership episodes are mapped, but complete historical affiliation coverage/explicit Independent scope is not certified. | O0 | **DL** — available absence cannot support this global negative. |
| U32 | Which committees have never discussed the HSE? | Do not assert a global negative without substantive topic evidence and comprehensive Committee transcript coverage. | No queryable Committee-discussed-topic relation or comprehensive transcript-content corpus is available. | O0 | **CU** — safe no-answer for unsupported global topic evidence; no NOT EXISTS query ran. |
| U33 | What is the most recent Bill sponsored by Malcolm Byrne? | Resolve Member, define sponsorship event date, and select latest only with sufficient source freshness/coverage; do not use maximum Bill number/year. | Bill sponsorship and Member identity are mapped, but Participation has no queryable sponsorship-event date and current coverage does not certify “most recent.” | O0 | **CU** — safe no-answer because latest sponsorship cannot be established from reviewed facts. |
| U34 | Has Simon Harris been Minister for Finance throughout 2026? | Distinguish elapsed time through `asOf=2026-10-28` from all of 2026, including future days; use accepted dated holdings only. | OfficeHolding is mapped, but current office coverage is explicitly incomplete. The full-year endpoint is after the fixed `asOf`. | O0 | **IF** — the temporal scope/future endpoint was neither clarified nor qualified. |
| U35 | Show me the Committee of Public Accounts hearing on 31 February 2024. | Reject the impossible date 2024-02-31 before RDF lookup and ask for a corrected date; do not guess nearby. | Calendar validation requires no RDF mapping; the integrated response did not reach a date-specific plan. | O0 | **IF** — impossible date was not detected or explained. |
| U36 | How much money did the Public Accounts Committee allocate to the HSE in 2024? | Recognize the unsupported allocation premise; distinguish scrutiny of expenditure from authority to allocate funds and do not invent an amount. | No reviewed allocation relation or PAC allocation query capability is present. A debate about spending would not establish an allocation. | O0 | **CU** — safe no-answer for an unrepresented funding relationship; the generic message did not explain the false premise. |

## Summary and measured failure classes

| Primary outcome | Count | Cases |
| --- | ---: | --- |
| Correct execution | 0 | — |
| Correct unavailability/clarification | 7 | U10, U21, U27, U28, U32, U33, U36 |
| Unsupported-but-answerable | 16 | U01–U07, U11, U13–U17, U22, U24, U25 |
| Interpretation failure | 3 | U30, U34, U35 |
| Unsafe/incorrect answer | 0 | — |
| Data-limited | 10 | U08, U09, U12, U18–U20, U23, U26, U29, U31 |
| **Total** | **36** | |

The `CU` credit is for the **fail-closed outcome** on requests whose essential
semantic relationship is not queryable; it is not evidence that the planner
understood each request. Their common message was generic and did not name the
missing relation. The same generic message was misleading for the three
interpretation failures and failed to distinguish all the data-limited cases.
No answer was returned, so no question was scored `unsafe/incorrect answer`;
there was also no executed query that silently discarded a constraint.

Principal measured failures:

1. **No unseen question reached a plan.** The runtime returned the same
   unsupported status and previous-Dáil-pattern diagnostic for all 36. It did
   not emit a draft or validated plan, so there is no observed question-specific
   interpretation, validation, compilation, or answer execution to score.
2. **Mapped facts do not generalize compositionally in the current route.**
   Examples U03/U13/U15/U17 require membership intersections, set difference,
   union or distinct aggregation; U14/U16/U20/U25 require independent
   referents, temporal joins or constraint-based entity resolution. Their base
   relations are present in the reviewed contracts, but the integrated runtime
   only recognizes finite plan families.
3. **Temporal selection/composition is a larger gap than date parsing alone.**
   U11/U22 need historical Bill state; U18–U20 need chronology or interval
   composition; U23/U24 need bounded/multi-House sitting selection. The
   underlying mapped event/interval facts do not amount to an implemented
   general temporal operator.
4. **The fallback does not classify unsupported semantics or data gaps.**
   Voting, transcript text/topic search, allocation, dated sponsorship and
   dated introduction are absent or unqueryable; the intended fail-closed
   response is appropriate, but the route supplied no capability-specific
   reason. U26/U29 and U08/U12/U18–U20/U23/U31 also have known identity,
   quarantine or coverage limits that must not be attributed to planner
   quality.
5. **Boundary recognition is not robust to held-out paraphrase/context.** U30
   requires a seat-versus-person clarification, U34 crosses the fixed `asOf`
   boundary, and U35 contains an impossible calendar date. All three received
   the same unrelated pattern diagnostic.

## Generalisation assessment

The current planner primarily recognizes **predefined linguistic patterns**,
not reusable semantic capabilities. In the browser Phase 2 route,
`execute_question()` dispatches through the finite Stage A, Stage C and Stage B
handlers, then the small fixed-pattern `plan_question()` recognizer. An
unmatched request becomes `unsupported_capability` with the previous-Dáil
fallback diagnostic. This is directly evidenced by the 36 identical `O0`
outcomes. There are reusable typed relations and deterministic query
compilation below those route families, but the request interpreter did not
compose them for this unseen set.

This evaluation does **not** establish that the data-backed queries would
return correct answers: no answer plan was generated, and the exact live
Fuseki dataset identity is unverified. In particular, the documented expected
development baseline must not be treated as proof of runtime completeness.

## Prioritized bounded recommendation

1. **Generalize within the existing closed v2 design, not by adding 36 regexes.**
   Reuse the reviewed referent/relation/constraint/answer vocabulary and the
   current queryability/ownership checks to build connected plans from already
   mapped facts. Start with one bounded Member–membership–term composition
   supporting two independently resolved Members and intersection, then a
   mapped multi-edge temporal join. Preserve every essential constraint and
   fail closed if a relation is not queryable. Validate with fresh examples
   and synthetic result oracles; this exposed question set is no longer a blind
   holdout and must not be used for tuning.
2. **Separate “pattern not understood,” “relation unsupported,” and “source
   data unavailable.”** Replace the global previous-Dáil fallback message with
   a truthful generic no-plan diagnostic, and expose the specific missing
   relation or evidence condition when the route can establish it. Keep
   invalid-date, ambiguity and future-as-of clarification distinct from both.
3. **Keep data remediation outside planner work.** Do not infer chairs, votes,
   transcript content, sponsor dates, allocations, or missing historical
   records. Resolve source/queryability and coverage issues through their
   existing review paths; no ontology or mapping change is recommended from
   this baseline alone.

## Reproduction, environment and limitations

From the repository root, with the existing local Fuseki endpoint already
available and no bootstrap/load flags:

```bash
.venv/bin/python tools/evaluate_query_service_unseen_questions.py \
  --output /tmp/opencode/query-service-unseen-evaluation/phase2-observations.jsonl
```

The runner verifies the frozen file SHA-256
(`a580ed9416b0aea6bf221623a7cdcf09e6bd00a3299db8a0d6be905d8c0f2e4e`) and
U01–U36 ordering, fixes `asOf`, removes LLM credentials for the process, and
posts every question through `/ask` with `mode=phase2`. It reads only Fuseki
query responses. It does not
start/rebuild Fuseki, load data, or call the legacy translator. Readiness can be
rechecked independently with the existing read-only `FusekiQueryClient.readiness()`
probe in `poc/nlq/fuseki.py`.

Environment used: Linux; Python 3.13.15; FastAPI 0.142.2, Starlette 1.7.0,
HTTPX 0.28.1; local Fuseki 5.1.0. A Starlette/HTTPX TestClient deprecation
warning was emitted but did not affect responses. The observation JSONL from
this run is disposable local evidence at
`/tmp/opencode/query-service-unseen-evaluation/phase2-observations.jsonl`,
SHA-256 `fa284b511c52fbac04a940dff1954d13b1efcb9963ce329821234137556f8bdb`.

Focused verification only: 36 route posts completed; all 36 were observed as
`unsupported_capability`, with no plan and zero question-answer queries.
`py_compile` for the observation runner and `git diff --check` passed. No full
suite, broad corpus scan, ingestion, Fuseki rebuild/reload, or production
operation was performed.
