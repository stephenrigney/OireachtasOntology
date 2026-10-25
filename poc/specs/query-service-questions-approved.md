# Query Service — Approved question and answer requirements

Approved human-facing question requirements. The required answer specifies desired behaviour; optional details and data dependencies remain separate. Internal terms (such as quarantine) are for diagnostics, not user-facing explanations.

**Status:** All 37 original questions, Q24A and T01 are marked approved by the reviewer (39 cases in total). Approval covers expected behaviour, not implementation readiness, data completeness, or factual verification of fixture answers.

## Members and parliamentary history

> Review rule: An approved test may still be unavailable against the current development dataset. Keep acceptance behaviour distinct from data-coverage diagnostics.

### Q01 — Find Deputy Ó Snodaigh's full name for me.

**Track:** User acceptance

**Required answer:** Identify the person referred to as Deputy Ó Snodaigh; return full name Aengus Ó Snodaigh.

**Optional context:** Show current or last constituency and House term if useful.

**Data dependency:** A matching Member with title/name aliases or sufficiently grounded partial-name resolution.

**Decision:** resolve grounded title + partial name; if several Members match, present distinguishable candidates rather than guessing.

**Your edits / notes:**

- [x] Approved

---

### Q02 — Was Aengus Ó Snodaigh a TD in the previous Dáil term?

**Track:** User acceptance

**Required answer:** Answer yes/no for membership in the Dáil term immediately preceding the current Dáil as at the question’s reference date.

**Optional context:** Name the resolved previous Dáil term and give its dates.

**Data dependency:** Current/previous-term metadata and Member membership records.

**Decision:** compute “previous” relative to the as-of date; fixtures must fix that date, not hard-code the 33rd Dáil.

**Your edits / notes:**

- [x] Approved

---

### Q03 — How long was Micheál Martin a Deputy?

**Track:** User acceptance

**Required answer:** Calculate the total duration Micheál Martin actually served as a TD by combining dated service episodes without double-counting overlapping intervals. Identify each service interval and any gaps.

**Optional context:** Give first service date and service episode dates; optionally report elapsed calendar time separately, explicitly distinguished from actual service duration.

**Data dependency:** First verified election/membership start date, dated terms and as-of date.

**Decision:** “how long” means cumulative actual service, with gaps accounted for; do not simply subtract first date from as-of date.

**Your edits / notes:**

- [x] Approved

---

### Q04 — How many Dáil terms has Micheál Martin served in?

**Track:** Technical regression

**Required answer:** Return the exact number of Dáil terms in which Micheál Martin served.

**Optional context:** List those terms if useful.

**Data dependency:** Complete term memberships for the Member.

**Decision:** Approved as a retained technical count regression, not a priority user-facing scenario.

**Your edits / notes:**

- [x] Approved

---

### Q05 — When did Timmy Dooley become a Senator?

**Track:** User acceptance

**Required answer:** Answer when Timmy Dooley first became a Senator with a date; distinguish any separate subsequent Seanad episodes.

**Optional context:** List both Seanad terms, entry dates and appointment/election method if available.

**Data dependency:** Dated Member–Seanad term membership episodes.

**Decision:** give first Seanad entry date; show later distinct Seanad service episodes as context.

**Your edits / notes:**

- [x] Approved

---

## Parties, constituencies and representation

### Q06 — What parties was Stephen Donnelly a member of?

**Required answer:** Return the distinct enduring political parties Stephen Donnelly belonged to: Social Democrats and Fianna Fáil. Each party should appear only once, regardless of how many Dáil terms or membership records are associated with it.

**Optional context:** Show the dates of affiliation with each party, consolidating membership records across Dáil terms. Preserve any interruptions or gaps in the evidence. Independent status, where relevant, should be distinguished from political-party membership.

**Data dependency:** Dated parliamentary party membership records and a reliable association between term-scoped parliamentary parties and their enduring political-party identities.

**Design requirement:** Group results by enduring political-party identity, not by term-scoped resource or matching label. Term-scoped memberships provide historical evidence but must not generate duplicate parties in the answer. Wikidata reconciliation must not be necessary to answer this question.

**Needs decision:** None.

- [x] Approved

---

### Q07 — What party is Senator Chris Andrews a member of?

**Track:** User acceptance

**Required answer:** Identify Chris Andrews’s current party as of the stated date; do not confuse current Seanad membership with past Dáil service.

**Optional context:** Include earlier party history and corresponding Dáil terms.

**Data dependency:** Current dated Member membership, party associations and historical records.

**Decision:** current party at the as-of date is the direct answer; historical affiliations may follow as context.

**Your edits / notes:**

- [x] Approved

---

### Q08 — What party does Michael Lowry belong to now?

**Track:** User acceptance

**Required answer:** Answer naturally whether Michael Lowry currently belongs to a political party; if evidenced as Independent, say “He is an Independent” and optionally note prior Fine Gael membership.

**Optional context:** Mention earlier Fine Gael affiliation and relevant Dáil terms.

**Data dependency:** Current Member/collection status and dated historical party affiliations.

**Implementation note:** Preserve Independent as a parliamentary status, not an enduring political party. Answer naturally without requiring the user to know the ontology distinction.

**Reviewer note:** Natural user-facing treatment was subsequently agreed; model distinction remains important.

**Your edits / notes:**

- [x] Approved

---

### Q09 — Who were the TDs for Dublin South Central in the last Dáil?

**Track:** User acceptance

**Required answer:** List all distinct TDs representing Dublin South-Central in the Dáil immediately preceding the current Dáil at the as-of date, including replacements.

**Optional context:** Give party affiliation, dates and links if available.

**Data dependency:** Current term identification at as-of date and complete representation/membership records for the preceding Dáil.

**Implementation note:** Resolve “last Dáil” relative to the as-of date. Freeze an as-of date in tests; never hard-code term 33.

**Reviewer note:** User: “Last Dáil needs to be computed by reference to current Dáil, not automatically 33rd Dáil.”

**Your edits / notes:**

- [x] Approved

---

### Q10 — Which panel did Timmy Dooley represent in the 26th Seanad?

**Required answer:** Identify Timmy Dooley's method of entry to the 26th Seanad and the relevant panel, constituency or nomination category. Where the Senator was nominated by the Taoiseach, state that directly rather than incorrectly assigning a vocational panel.

**Optional context:** Give the date of election or nomination and the relevant Seanad term.

**Data dependency:** Seanad membership and representation records, including vocational panels, Taoiseach's nominees and university/higher education constituencies.

**Design requirement:** Interpret the word "panel" or "constituency" flexibly in natural-language questions. Recognise all three Seanad entry routes and return the historically correct designation. For example, "Which panel does Michael McDowell represent?" should identify the National University of Ireland constituency for his existing Seanad service, rather than reject the question because it is not technically a vocational panel.

**Needs decision:** None.

- [x] Approved

---

## Committees and parliamentary statistics

### Q11 — Was Timmy Dooley a member of the Select Committee on Transport and Communications?

**Track:** User acceptance

**Required answer:** Give yes/no for whether Timmy Dooley served on the specific Select Committee on Transport and Communications incarnation current at the as-of date; state which committee was resolved.

**Optional context:** Provide service dates/House term, if recorded.

**Data dependency:** Term-aware Committee identity, current committee determination and Member committee-membership records.

**Implementation note:** Default an otherwise unscoped committee reference to the current incarnation at the as-of date. Test the distinction between “was a member” of that incarnation and explicit historical questions about earlier incarnations.

**Reviewer note:** User: Committee is term bound; assume current committee if no temporal context.

**Your edits / notes:**

- [x] Approved

---

### Q12 — Who is the Chair of the Committee on Transport?

**Track:** User acceptance

**Required answer:** Identify the chair of the current Committee on Transport at the as-of date, or present a concise choice if multiple current committees match. Do not invent missing chair evidence.

**Optional context:** Provide office dates and official committee name.

**Data dependency:** Committee name/alias resolution and chair/office-holder evidence; chair relationship is not established as a current Phase 2 fact.

**Decision:** default to current committee; require queryable chair evidence, otherwise report the evidence gap.

**Your edits / notes:**

- [x] Approved

---

### Q13 — How many committees were Timmy Dooley a member of?

**Track:** User acceptance

**Required answer:** Return the number of distinct committees of which Timmy Dooley was a member.

**Optional context:** List committees with membership dates, separating multiple periods in the same committee.

**Data dependency:** Complete committee memberships; term-specific identity decisions for reconstituted committees.

**Decision:** count distinct committees, not repeated membership records; optionally show records and periods.

**Your edits / notes:**

- [x] Approved

---

### Q14 — Who are the Sinn Féin members of the Good Friday Committee?

**Track:** User acceptance

**Required answer:** List current Sinn Féin members of the Good Friday Agreement committee, or say exactly what cannot be verified.

**Optional context:** Give full committee name and member roles.

**Data dependency:** Committee identity is quarantined/conflicted; current membership and party affiliations must be sourced.

**Decision:** report the quarantined/conflicted source as a data-coverage failure, not as an NLQ interpretation failure.

**Your edits / notes:**

- [x] Approved

---

### Q15 — When did each Dáil start and finish?

**Track:** User acceptance

**Required answer:** List Dáil terms with their start and end dates in chronological order; indicate the current open term.

**Optional context:** Offer term number, duration and links.

**Data dependency:** Term date properties in Houses owner graph; distinguish missing from open end.

**Decision:** Approved as a user-facing dates question. Also preserve the original count-of-Dáil-terms query as a separate technical regression (T01 below).

**Reviewer note:** User also wants to keep old Dáil term count question.

**Your edits / notes:**

- [x] Approved

---

### Q16 — How many members were in the 33rd Dáil?

**Required answer:** State the total number of seats in the 33rd Dáil: 160. Do not count distinct individuals who served over the term, as replacements would inflate the result.

**Optional context:** Give the number of distinct TDs who served during the term, clearly distinguished from the number of seats.

**Data dependency:** An authoritative seat count for each Dáil term. This is not currently represented explicitly in the ontology.

**Design requirement:** Distinguish parliamentary seat counts from membership records. Do not infer vacancies or changes in seat occupancy from missing membership records or the absence of evidence that a TD signed the roll.

**Needs decision:** None.

- [x] Approved

---

### Q17 — What are the groups and parties in the 34th Dáil?

**Track:** User acceptance

**Required answer:** List political parties and any formally recognised parliamentary groups in the 34th Dáil as separate categories.

**Optional context:** Give membership counts and current status if available.

**Data dependency:** ParliamentaryParty data available; formally recognised ParliamentaryGroup instances not populated by current ETL.

**Decision:** distinguish parties from formally recognised groups; a parties-only result must clearly state that group data is missing.

**Your edits / notes:**

- [x] Approved

---

## Bills

### Q18 — Find the full title of the AI protection of children Bill

**Track:** User acceptance

**Required answer:** Resolve the abbreviated AI protection-of-children Bill reference and provide its full official English short title.

**Optional context:** Include Bill number, year and official link.

**Data dependency:** Bill titles/aliases and identity-resolution evidence.

**Decision:** resolve abbreviated Bill title; show candidates when it could refer to more than one Bill.

**Your edits / notes:**

- [x] Approved

---

### Q19 — What Bills were published in 2024

**Track:** User acceptance

**Required answer:** Return distinct Bills published in calendar year 2024, using a source-backed dated Published lifecycle event where available. If no such date is available, explicitly label any fallback selection by dated introduction/presentation rather than silently treating legislative year as publication year. Display English short title, number and year.

**Optional context:** Show publication/presentation/first-introduction dates when known.

**Data dependency:** Bill lifecycle events (including Published and `activity_date`), version/document dates, and introduction/presentation event evidence; these may not be exposed yet as Query Service facts.

**Decision:** prefer publication date if represented. Repository mapping emits dated Published events, but has no single Bill-level publication-date property. Fallback to introduction/presentation date must be disclosed, not mixed unnoticed.

**Your edits / notes:**

- [x] Approved

---

### Q20 — What 2026 Bills haven't been enacted?

**Track:** User acceptance

**Required answer:** List distinct Bills with legislative year 2026 whose process status is not Enacted, with English short titles, Bill numbers and totals grouped by status. Include current, lapsed, withdrawn, defeated and declared-repugnant Bills, plus any other non-enacted statuses present.

**Optional context:** Show total count and status breakdown, with links and as-of date where helpful.

**Data dependency:** Bill year and current lifecycle status; complete coverage for all relevant statuses.

**Decision:** include all non-enacted statuses, not only current Bills; include counts by status.

**Your edits / notes:**

- [x] Approved

---

### Q21 — What is happening to the AI companion services bill?

**Track:** User acceptance

**Required answer:** Give current process status of the identified AI Companion Services Bill and dated process history where evidence exists.

**Optional context:** Include next procedural step only when recorded, plus official Bill link.

**Data dependency:** Bill lifecycle events and dates may be incompletely mapped; current status is more broadly available.

**Decision:** Report source-backed process status and dated history; do not manufacture recorded next steps from the label “Current”.

**Future capability (not part of current acceptance):** Infer the ordinary next procedural step from the Bill's current status, completed legislative stages, House context and reviewed procedural rules. Distinguish procedural expectations from confirmed scheduled activity. Account for alternative paths, recommittal, amendments between Houses and terminal statuses. Do not imply that a procedurally possible step has been scheduled or will necessarily occur.

**Your edits / notes:**

- [x] Approved

---

### Q22 — Who is the sponsor of the AI companion services Bill?

**Track:** User acceptance

**Required answer:** Identify every explicitly recorded sponsor of the correctly resolved Bill. Clearly distinguish primary sponsors where the source provides `isPrimarySponsor`; mark unknown primary status as unknown, never invent a primary.

**Optional context:** Include sponsor roles, and an official Bill link.

**Data dependency:** Bill identity resolution, sponsor participation, and primary-sponsor flag.

**Decision:** include all sponsors and explicitly identify the primary sponsor when source-backed; preserve unknown when flag is null.

**Your edits / notes:**

- [x] Approved

---

### Q23 — Which bills did Malcolm Byrne sponsor?

**Track:** User acceptance

**Required answer:** Return one row per distinct Bill sponsored by Malcolm Byrne, with English short title and whether his sponsorship was primary or supporting where evidenced.

**Optional context:** Give Bill number, year, status and link.

**Data dependency:** Bill sponsorship RDF and readable title lookup.

**Decision:** Show whether sponsorship was primary or supporting when evidenced; preserve unknown when not evidenced.

**Reviewer note:** User: include whether he was primary or supporting sponsor.

**Your edits / notes:**

- [x] Approved

---

### Q24 — Tell me about Bill 48 from 2024.

**Track:** Coverage diagnostic

**Required answer:** Explain that Bill 2024/48 is unavailable from the present local dataset because of problems with the source data; do not substitute another Bill or imply it never existed.

**Optional context:** Summarise recent legislative activity from reviewed source.

**Data dependency:** Reviewed quarantine state and source-coverage diagnostics for Bill 2024/48.

**Decision:** Keep this as a coverage diagnostic. Q24A is the separate real-world retrieval case.

**Reviewer note:** User: use a different Bill for user acceptance, but keep quarantine/data problem separate.

**Your edits / notes:**

- [x] Approved

---

### Q24A — Tell me about Bill 23 from 2025.

**Track:** User acceptance (selected Bill example)

**Required answer:** For a source-available Bill identified by number and year, give its title, current process status, official Bill link and explanatory memorandum link if available. Clearly state when no memorandum is known.

**Optional context:** Include recent dated legislative activity if mapped and available.

**Data dependency:** Verify that Bill 23 of 2025 and the relevant metadata are available in the selected development fixture or dataset. No corpus scan is needed for plan-design testing.

**Implementation note:** Bill 23 of 2025 was chosen and the question approved. Confirm available source data during focused fixture setup; lack of data must be diagnosed separately.

- [x] Approved

---

## Ministerial offices

### Q25 — Was Micheál Martin Taoiseach in September 2026?

**Track:** User acceptance

**Required answer:** Answer whether Micheál Martin held the office of Taoiseach at any point in September 2026; give supporting tenure start date.

**Optional context:** Explain if tenure changed within that month.

**Data dependency:** Accepted OfficeHolding dates; as-of period.

**Decision:** any overlap with September 2026 counts as yes; disclose partial-month tenure where applicable.

**Your edits / notes:**

- [x] Approved

---

### Q26 — Who is Minister for Finance

**Track:** User acceptance

**Required answer:** Give the Minister for Finance as of a specified as-of date (user expects Simon Harris), with source/effective date.

**Optional context:** Mention other offices, such as Tánaiste, if verified.

**Data dependency:** Fresh/current office holdings; development RDF currently has very limited accepted holdings, not a current complete roster.

**Decision:** as-of date and suitable current office dataset are prerequisites; do not infer current Minister from an incomplete historical development capture.

**Your edits / notes:**

- [x] Approved

---

### Q27 — Who was Minister for Finance on 1 July 2021?

**Track:** User acceptance

**Required answer:** Identify who held Minister for Finance on 1 July 2021 (Paschal Donohoe) and the relevant tenure dates if available.

**Optional context:** Include predecessor/successor if source-backed.

**Data dependency:** Accepted historical OfficeHolding for office/date.

**Decision:** date-point office-holder question.

**Your edits / notes:**

- [x] Approved

---

## Debates

### Q28 — Show me the Dáil debate from 2 July 2015.

**Track:** Technical regression; realistic replacement pending

**Required answer:** If retaining the original query, display a meaningful Dáil sitting/date/link rather than a raw DebateRecord IRI.

**Optional context:** Add agenda headings if available.

**Data dependency:** A Dáil DebateRecord for 2 July 2015 is in the pinned development slice.

**Decision:** Approved as a technical DebateRecord/link regression only. A separate realistic research question can be added later; it is not an approval blocker.

**Reviewer note:** An earlier review withheld approval; the later uploaded document marked this technical regression approved.

**Your edits / notes:**

- [x] Approved

---

### Q29 — Was there a Seanad debate on 2 July 2015?

**Track:** User acceptance

**Required answer:** Answer yes/no on whether there was a Seanad debate on 2 July 2015.

**Optional context:** Provide an official sitting/debate link and date.

**Data dependency:** Seanad DebateRecord for the specified date.

**Decision:** boolean yes/no first; provide the debate link only as supporting context.

**Your edits / notes:**

- [x] Approved

---

### Q30 — When did PAC last examine the HSE?

**Track:** User acceptance

**Required answer:** Give the date and official link of the latest Committee of Public Accounts hearing that substantively examined the HSE, relative to a fixed as-of date, if sufficient source coverage exists. If not, state the coverage limitation rather than asserting a false “latest”.

**Optional context:** Include relevant session/agenda description.

**Data dependency:** Human-reviewed alias PAC → Committee of Public Accounts; hearing/date information; evidence of substantive HSE topic; adequate coverage up to as-of date to establish “latest”.

**Implementation note:** Use the reviewer-specified alias “PAC” → “Committee of Public Accounts”. Define reproducible fixture evidence for a hearing that substantively examines the HSE. A small fixture proves selection and latest-date logic but cannot establish real-world recency without sufficient coverage.

**Reviewer note:** User requests explanation of bounded fixtures and notes that aliasing needs human judgment.

**Your edits / notes:**

- [x] Approved

---

### Q31 — Show me the Dáil debate from 24 September 2026.

**Track:** Coverage diagnostic


**Required answer:** If retained, show a human-readable Dáil debate link for the requested date, or state that the local dataset does not include it.

**Optional context:** Provide agenda metadata if available.

**Data dependency:** Dáil 24 September 2026 is outside pinned development Debate slice.

**Decision:** Approved as a data-coverage diagnostic, not a priority real-world user query. Preserve the absence of a pinned development DebateRecord separately from general corpus existence.

**Your edits / notes:**

- [x] Approved

---

## Ambiguity and capability boundaries

### Q32 — Who is Michael Collins?

**Track:** User acceptance

**Required answer:** Present the distinct Michael Collins Member candidates with enough information to choose between them: service dates and Houses.

**Optional context:** Include constituency and verified ministerial roles if any.

**Data dependency:** Local Member identity candidates and historical service; ministerial coverage incomplete.

**Decision:** return a small set of distinguishable candidates with service dates/Houses. Generalise this to an entity-resolution policy, rather than special-casing Michael Collins.

**Reviewer note:** User: candidate-presentation principle is general.

**Your edits / notes:**

- [x] Approved

---

### Q33 — Which Members named Michael Collins served in the Dáil?

**Track:** Technical regression

**Required answer:** If retained, list all matching Member identities who served in the Dáil without selecting a single one.

**Optional context:** Distinguish them by dates and House.

**Data dependency:** Duplicate-name Member identities; correct set-valued resolution.

**Decision:** Approved as a technical set-valued resolution regression, despite unrealistic wording.

**Your edits / notes:**

- [x] Approved

---

### Q34 — What is the full name of Niamh Example?

**Track:** Technical regression

**Required answer:** Report that no matching Member was found; do not manufacture a record.

**Optional context:** Offer a brief spelling/identity suggestion if useful.

**Data dependency:** No matching Member for the synthetic name.

**Decision:** Approved as a synthetic negative test only.

**Your edits / notes:**

- [x] Approved

---

### Q35 — Who was Minister for Finance from January 2021 to December 2022?

**Track:** User acceptance

**Required answer:** Return every person whose tenure as Minister for Finance overlaps January 2021–December 2022, with precise start and end dates.

**Optional context:** Explain changes of office-holder inside the range.

**Data dependency:** Accepted OfficeHolding intervals and start/end data for relevant years.

**Decision:** return all office holders whose tenures overlap any part of the interval, with tenure dates and changes; not only someone who served for the entire interval.

**Your edits / notes:**

- [x] Approved

---

### Q36 — Which Members voted for the Artificial Intelligence Companion Services Bill?

**Track:** User acceptance

**Required answer:** Identify Members recorded as having voted for the Bill, or clearly state that voting data is unavailable.

**Optional context:** Give vote date and division where available.

**Data dependency:** Bill-linked votes are not currently supported in the semantic vocabulary/queryable data.

**Decision:** voting is not sponsorship; report unavailable votes until appropriate data/query capability exists.

**Your edits / notes:**

- [x] Approved

---

### Q37 — What did speakers say in the Dáil debate on 2 July 2015?

**Track:** User acceptance

**Required answer:** If speech content is available through an approved retrieval path, give attributable quotes or a faithful summary; otherwise state content unavailable.

**Optional context:** Link to relevant source transcript and speaker sections.

**Data dependency:** Raw AKN sources may be retained, but transcript speech text was intentionally excluded from the queryable RDF and no transcript-query path has been established.

**Decision:** Approved as a desired transcript-content behaviour with explicit unavailability until a reviewed transcript retrieval path exists.

**Your edits / notes:**

- [x] Approved

---

## Additional technical regression (retained from original benchmark)

### T01 — How many Dáil terms are listed in the Houses data?

**Track:** Technical regression

**Required answer:** Return the exact number of distinct Dáil-term resources in the selected dataset, not merely an integer of arbitrary value.

**Data dependency:** Houses term records, with a dataset fixture or snapshot providing the expected count.

**Decision:** Retain alongside Q15 as requested; technical validation must check the value.

- [x] Approved (retained at reviewer request)

---

## Implementation and evidence dependencies — not additional approval gates

- **Q06:** Reliable local cross-term enduring-party identity associations; membership periods remain term-scoped source evidence.
- **Q09, Q11, Q12:** Consistent as-of interpretation for “last” and “current”; committee incarnation and reviewed aliases.
- **Q10:** Represent all three Seanad entry routes without conflating nomination, vocational panel and higher-education constituency.
- **Q16:** Authoritative seat complement (160 in the approved 33rd-Dáil example) is not currently a directly modelled query attribute; do not derive it from Member record counts.
- **Q19, Q21–Q23:** Source-backed lifecycle dates, statuses and primary-sponsor flags; unknown evidence must remain unknown.
- **Q24, Q24A:** Preserve the distinction between a known local data problem and normal Bill retrieval. Bill 23 of 2025 is the selected example but its local dataset availability still needs verification.
- **Q28:** Approved technical regression only; future realistic debate research question can be added separately.
- **Q30:** Reviewed “PAC” alias, HSE-topic evidence, and sufficient coverage for any claim about the latest hearing.
- **Q36–Q37:** Voting and transcript retrieval depend on future data/query capabilities; a better plan cannot create absent evidence.

The test document does not establish complete source coverage, actual as-of answers, or that every approved question must be executable in the first implementation slice.

## Test execution discipline

- Use small fixed source-backed fixtures for planner/compiler correctness; freeze as-of dates and expected output.
- Do not claim real-world latest/current/completeness from a partial dataset.
- Prefer focused tests and browser inspection; no production corpus scanning, ingestion or broad benchmark reruns in this review exercise.
- English titles by default; unique entity identities rather than duplicate language rows.