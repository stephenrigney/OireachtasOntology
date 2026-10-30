# Query Service — Unseen Questions (Approved Evaluation Set)

**Status:** Approved by the user on 2026-10-30 for baseline evaluation. This is the frozen copy of all 36 cases; question wording and stated requirements are preserved from the review-branch source.
**Purpose:** Assess generalisation to previously untrained parliamentary questions after the current approved-question campaign. Questions are intentionally not copied from the approved catalogue; some require capabilities or evidence not currently available.
**Authority:** User approval for this baseline evaluation, [approved questions](query-service-questions-approved.md), [Query-plan redesign requirements](query-plan-redesign-requirements.md), and the [current Query Service contract](query-schema-contract.json). These are reference material, not evidence that any answer is historically true.
**Evidence caveat:** The first 12 are *research-style questions*, **not** questions actually solicited from external researchers. Historical answers and dataset completeness have not been verified. Requirements below are expected behaviours, not assertions of historical facts.
**Isolation:** This frozen copy is on a separate evaluation branch and is not a technically secret holdout after this run.

## Original reviewer guidance (retained as provenance)

- Review whether each question is natural, useful and genuinely distinct from the 39 approved cases. Replace contrived cases rather than expanding the set indefinitely.
- Amend the proposed required answer, data dependency or decision before ticking **Approved**. An executable result, a clarification and an honest unavailability outcome can all be legitimate, depending on the question.
- Use fixed reference dates and small fixtures for eventual planner evaluation; separately classify interpretation, capability detection, execution and evidence quality. Do not equate fixture behaviour with real-world completeness.

## Research-style questions — not collected from external users (12)

### U01 — Who represented Dublin Central in the 31st Dáil?

**Track:** Unseen evaluation — research-style

**Required answer:** Return every distinct TD representing Dublin Central during the 31st Dáil, including replacements, using an explicitly numbered Dáil term rather than a relative previous-term selector.

**Optional context:** Name the term dates and each Member's representation interval.

**Data dependency:** A trustworthy 31st-Dáil term identity, its Dublin Central constituency occurrence and complete dated Member representations.

**Decision:** The ordinal term must resolve to an actual term resource; never silently substitute the previous or current Dáil.

**Your edits / notes:**

- [x] Approved

---

### U02 — Which constituencies did Micheál Martin represent during his Dáil career?

**Track:** Unseen evaluation — research-style

**Required answer:** Return the distinct constituencies in which the resolved Member is recorded as having served as a TD, with the corresponding House terms; preserve changes of constituency identity and spelling where supported.

**Optional context:** Group consecutive Dáil terms beneath the same reviewed constituency identity.

**Data dependency:** Complete Member parliamentary-membership and constituency-representation evidence across the relevant terms; reviewed identity links if grouping constituency series.

**Decision:** Do not conflate differently scoped constituency resources merely because their labels match; disclose whether grouping is term-occurrence or reviewed enduring identity.

**Your edits / notes:**

- [x] Approved

---

### U03 — Which Members served in both the 32nd and 33rd Dáil?

**Track:** Unseen evaluation — research-style

**Required answer:** Return the intersection of distinct Member identities with accepted Dáil membership in each of the two explicitly specified terms.

**Optional context:** Show a dated service episode or official identity link for each term.

**Data dependency:** Member-term membership evidence for both Dáil terms, including identity continuity across terms.

**Decision:** Require two independently evidenced memberships of the same Member; do not infer continuity from names or assume uninterrupted service.

**Your edits / notes:**

- [x] Approved

---

### U04 — Which members of the 25th Seanad subsequently served in the 33rd Dáil?

**Track:** Unseen evaluation — research-style

**Required answer:** List distinct people evidenced as members of the specified Seanad term who also served as TDs in the specified later Dáil term.

**Optional context:** Show their relevant Seanad and Dáil service periods.

**Data dependency:** Cross-House Member identity and term-scoped Seanad and Dáil membership evidence.

**Decision:** Use the same enduring Member identity across separate House membership episodes; distinguish term membership from simultaneous officeholding.

**Your edits / notes:**

- [x] Approved

---

### U05 — Were any TDs replaced in Cork South-West during the 33rd Dáil?

**Track:** Unseen evaluation — research-style

**Required answer:** Determine whether representation of Cork South-West changed within that Dáil term and, if supported, identify outgoing and incoming Members with the relevant intervals.

**Optional context:** Give the representation timeline and explain any uncertainty over when a seat changed hands.

**Data dependency:** Complete constituency-specific dated membership and representation episodes for the 33rd Dáil.

**Decision:** A negative answer requires sufficiently complete term coverage. Do not equate a difference in party affiliation with replacement of a TD.

**Your edits / notes:**

- [x] Approved

---

### U06 — Which political parties were represented by TDs for Galway West during the 33rd Dáil?

**Track:** Unseen evaluation — research-style

**Required answer:** Return distinct enduring party identities evidenced for TDs representing Galway West during that term; distinguish Independents from parties.

**Optional context:** Name the associated TDs and the overlapping affiliation periods.

**Data dependency:** Galway West term-scoped constituency membership, dated party affiliations and reviewed enduring-party identity links.

**Decision:** Require affiliation and representation to overlap in time where dates exist; never assign a Member's present party retrospectively.

**Your edits / notes:**

- [x] Approved

---

### U07 — Which committees did Catherine Connolly serve on during the 32nd Dáil?

**Track:** Unseen evaluation — research-style

**Required answer:** Identify the distinct committee incarnations of which the resolved Member was an accepted member during the specified Dáil term.

**Optional context:** Include actual service dates and committee names where available.

**Data dependency:** Member-owned committee membership evidence, temporal scoping and term-aware Committee identities.

**Decision:** Do not merge term-specific committee incarnations by similar label or treat an unevidenced committee membership as a negative.

**Your edits / notes:**

- [x] Approved

---

### U08 — Who was Minister for Health on 1 July 2020?

**Track:** Unseen evaluation — research-style

**Required answer:** Identify the officeholder whose accepted Minister for Health holding covered that date, or report that the local evidence cannot establish the answer.

**Optional context:** Show tenure start/end dates and official Member identity.

**Data dependency:** Reviewed NamedOffice identity for Minister for Health and accepted, dated OfficeHolding records.

**Decision:** Use inclusive calendar-day point-in-time semantics; missing holdings are not evidence that the office was vacant.

**Your edits / notes:**

- [x] Approved

---

### U09 — Which people have held both Taoiseach and Minister for Finance?

**Track:** Unseen evaluation — research-style

**Required answer:** Return distinct Member identities with separately evidenced holdings of both named offices; the holdings need not overlap.

**Optional context:** Show each relevant officeholding episode and the ordering of offices.

**Data dependency:** Accepted NamedOffice identities, historical OfficeHolding records and cross-episode Member identity.

**Decision:** Treat this as intersection across officeholding evidence, not an assertion that someone concurrently held both offices; incomplete historical holdings limit completeness.

**Your edits / notes:**

- [x] Approved

---

### U10 — Which Bills were sponsored by Sinn Féin TDs in 2024?

**Track:** Unseen evaluation — research-style

**Required answer:** List distinct Bills of legislative year 2024 with explicitly recorded sponsor Participations attributable to Members who were evidenced as Sinn Féin TDs at the applicable sponsorship time.

**Optional context:** Give English Bill titles, sponsor names and recorded primary/supporting/unknown flags.

**Data dependency:** Bill sponsorship, legislative year, Member identity, dated Dáil membership and political affiliation; sponsorship timing if historical alignment is required.

**Decision:** If the sponsorship episode cannot be dated, do not silently use a Member's current party to infer their party at sponsorship.

**Your edits / notes:**

- [x] Approved

---

### U11 — What stage had Bill 23 of 2025 reached by 30 June 2026?

**Track:** Unseen evaluation — research-style

**Required answer:** Resolve the identified Bill and report the latest process state supported on or before 30 June 2026, with the source event/date; distinguish this from its present status.

**Optional context:** Provide preceding dated lifecycle events and the official Bill link.

**Data dependency:** Bill number/year identity, dated process events and sufficient lifecycle history to reconstruct point-in-time status.

**Decision:** Never use today's process status as a substitute for historical status; report missing historical evidence distinctly.

**Your edits / notes:**

- [x] Approved

---

### U12 — Did the Committee of Public Accounts hold any sittings in September 2024?

**Track:** Unseen evaluation — research-style

**Required answer:** Determine whether there is evidence of a sitting of the resolved Committee of Public Accounts during that calendar month, and provide a date/link when found.

**Optional context:** List matching sittings if the answer is affirmative.

**Data dependency:** Reviewed Committee identity/alias, dated committee DebateSitting or DebateRecord linkage and coverage of committee sittings.

**Decision:** A positive requires an actual sitting; an absence in a partial Debate slice cannot establish a historical No.

**Your edits / notes:**

- [x] Approved

---

## Capability recombinations — new joins, selectors, aggregates and temporal constraints (12)

### U13 — Which TDs represented Dublin Central in the 32nd Dáil but not the 33rd?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return distinct Members with accepted Dublin Central representation in the 32nd Dáil and no such representation in the 33rd, provided both scoped sets have adequate coverage.

**Optional context:** Give relevant 32nd-Dáil representation dates.

**Data dependency:** Both Dáil terms, their constituency occurrences and complete Member representation evidence for the two scoped sets.

**Decision:** This is set difference, not a party-change comparison; if 33rd-Dáil coverage is incomplete, avoid an asserted negative.

**Your edits / notes:**

- [x] Approved

---

### U14 — Who represented the same constituency as Micheál Martin in the 33rd Dáil?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Resolve the named Member's constituency representation in the specified term, then return distinct other Members who represented that same term-scoped constituency.

**Optional context:** Show the constituency label and each person's relevant representation period.

**Data dependency:** Member identity, term-scoped membership and constituency links, including a second Member lookup over the same constituency occurrence.

**Decision:** Use a genuine shared-constituency join; exclude the anchor Member from 'who else' results and do not match by label alone.

**Your edits / notes:**

- [x] Approved

---

### U15 — Which Dáil terms did Aengus Ó Snodaigh and Mary Lou McDonald both serve in?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return the intersection of Dáil-term identities in which each of the two separately resolved Members is evidenced to have served.

**Optional context:** List the start/end dates of those terms.

**Data dependency:** Unambiguous identities for both Members and dated Dáil-term membership episodes.

**Decision:** Keep two independent Member referents of the same type; do not accidentally unify them or infer overlapping service solely from term names.

**Your edits / notes:**

- [x] Approved

---

### U16 — Which Sinn Féin TDs represented Dublin South-Central during the 33rd Dáil?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return distinct Members whose Dublin South-Central TD representation and Sinn Féin affiliation overlap within the specified Dáil term.

**Optional context:** Give affiliation and representation intervals; preserve uncertainty when dates are incomplete.

**Data dependency:** Dáil term and constituency membership, Member party episodes and reviewed enduring Sinn Féin identity.

**Decision:** Use contemporaneous affiliations and term-scoped constituency representation, not a current party filter.

**Your edits / notes:**

- [x] Approved

---

### U17 — How many different TDs represented Dublin South-Central across the 32nd and 33rd Dáil?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Count the union of distinct Member identities representing that constituency in either specified term, counting a Member present in both only once.

**Optional context:** List the underlying Members and their terms as an audit trail.

**Data dependency:** Complete representation sets for both Dáil terms and consistent Member identity.

**Decision:** Do not sum term-specific counts without deduplication; disclose any incomplete term coverage.

**Your edits / notes:**

- [x] Approved

---

### U18 — Did Stephen Donnelly join Fianna Fáil before or after he first became a Minister?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Compare the earliest evidenced start of Fianna Fáil affiliation against the earliest evidenced accepted Minister officeholding for the resolved Member; report the ordering or insufficient evidence.

**Optional context:** Show both supporting dates and identify the actual named office.

**Data dependency:** Dated enduring-party affiliation episodes, named Minister OfficeHoldings and reliable first-event coverage.

**Decision:** Do not assume a CabinetMembership is the first ministerial holding; avoid a chronology claim when either start date is missing.

**Your edits / notes:**

- [x] Approved

---

### U19 — Who held the office of Minister for Finance immediately after Paschal Donohoe's 2022 tenure ended?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Identify the next accepted holder of the same office after the referenced tenure's actual end, if the dated holding sequence supports one unambiguously.

**Optional context:** Show both tenure intervals and any recorded vacancy or gap.

**Data dependency:** Resolved NamedOffice identity and sufficiently complete, consistent dated OfficeHolding episodes covering the transition.

**Decision:** Do not invent an explicit succession edge or assume no intervening holder; chronological adjacency is evidence-based and conditional on completeness.

**Your edits / notes:**

- [x] Approved

---

### U20 — Which Ministers for Finance also represented Dublin Central while holding that office?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return distinct Members with a Minister for Finance holding overlapping their accepted Dublin Central TD representation.

**Optional context:** Show the period of overlap and relevant House term.

**Data dependency:** OfficeHolding dates, Minister for Finance identity and term-scoped Member constituency-representation dates.

**Decision:** Intersect the actual intervals; having held the office and represented the constituency at different times is insufficient.

**Your edits / notes:**

- [x] Approved

---

### U21 — Which Bills introduced in 2024 had at least two different named sponsors?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return Bills with a dated introduction/presentation event in 2024 and Participations by at least two distinct Member IRIs; give English titles and sponsor counts.

**Optional context:** List sponsors, primary flags and official Bill links.

**Data dependency:** Dated Bill introduction/presentation events, Bill-owned sponsor participations and exact Member identities.

**Decision:** Count distinct people rather than Participation rows; do not silently replace introduction date with legislative year or publication date.

**Your edits / notes:**

- [x] Approved

---

### U22 — Which Bills sponsored by Stephen Donnelly had not been enacted by 31 December 2024?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return Bills with recorded sponsorship by the resolved Member and source-backed non-enacted status as of the specified historical date, clearly explaining when that historical state is not reconstructable.

**Optional context:** Provide Bill titles, status evidence dates and official links.

**Data dependency:** Bill sponsorship and dated lifecycle evidence sufficient to derive historical enacted/non-enacted state at the cutoff.

**Decision:** Do not apply a present-day non-enacted filter to a historical question or infer non-enactment from missing Enacted events in incomplete history.

**Your edits / notes:**

- [x] Approved

---

### U23 — Which Dáil debates took place in the first seven days after Micheál Martin first became Taoiseach?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Find the start date of the Member's first accepted Taoiseach holding, then list actual Dáil sittings during the ensuing seven calendar days if the source corpus supports them.

**Optional context:** Show sitting dates and official DebateRecord links.

**Data dependency:** Historical Taoiseach OfficeHolding with valid start date, dated Dáil DebateSittings and a bounded Debate corpus.

**Decision:** The seven-day period is anchored to the holding date, not today's date; do not substitute written answers for sittings, and qualify incomplete Debate coverage.

**Your edits / notes:**

- [x] Approved

---

### U24 — Which dates in July 2015 had both a Dáil debate and a Seanad debate?

**Track:** Unseen evaluation — capability recombination

**Required answer:** Return dates within July 2015 on which distinct actual sittings for both Houses are evidenced.

**Optional context:** Link representative records from each House for each date.

**Data dependency:** Dated Dáil/Seanad DebateSittings, chamber identity and source-backed records in the selected dataset.

**Decision:** Use a same-day intersection across Houses, not a count of DebateRecords or written-answer dates; missing dates cannot prove absence without coverage.

**Your edits / notes:**

- [x] Approved

---

## Boundary and adversarial questions — ambiguity, absent facts, false premises and safety (12)

### U25 — Which Michael Collins represented Cork South-West?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Use the constituency constraint to distinguish locally evidenced Member identities named Michael Collins, returning a unique grounded person only if the evidence does so; otherwise present candidates or explain missing evidence.

**Optional context:** Show term dates/Houses to distinguish candidates.

**Data dependency:** Member candidate identities and dated constituency-representation evidence.

**Decision:** Do not guess from the most famous name match; a useful constraint should resolve an ambiguity when authoritative local evidence permits.

**Your edits / notes:**

- [x] Approved

---

### U26 — Who chaired the Good Friday Agreement Committee in September 2026?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Resolve the relevant Committee incarnation and return an evidenced chair for the specified interval, or state precisely whether committee identity or chair evidence prevents the answer.

**Optional context:** Identify which committee identity was considered and any uncertainty.

**Data dependency:** Reviewed committee identity/reconciliation and chair role with dated coverage.

**Decision:** Do not override quarantined identity conflicts or invent a chair; distinguish conflicted identity from unsupported chair relation.

**Your edits / notes:**

- [x] Approved

---

### U27 — Did all the TDs in the 33rd Dáil vote for the Artificial Intelligence Companion Services Bill in 2026?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Recognise the requested historical Member cohort, the Bill and the voting claim; do not infer votes from sponsorship, party or attendance, and explain any date/cohort mismatch.

**Optional context:** If reviewed Bill-linked votes eventually exist, explain the exact division and voting population used.

**Data dependency:** Bill-linked division/member voting records and date-scoped 33rd-Dáil membership, neither guaranteed to be available.

**Decision:** Fail closed on missing vote data and temporal mismatch; a 2026 Bill does not justify asserting how a prior Dáil voted.

**Your edits / notes:**

- [x] Approved

---

### U28 — What did Aengus Ó Snodaigh say about housing in the Dáil last month?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Interpret 'last month' relative to a fixed as-of date and identify the requested speaker, House and topic; return attributable speech content only through a reviewed transcript retrieval path.

**Optional context:** Give dates, quoted source links and distinguish quotes from summaries if retrieval is available.

**Data dependency:** Speaker-to-speech attribution, topic retrieval and raw transcript access; transcript text is not in current RDF.

**Decision:** Do not fabricate quotes or treat meeting metadata as speech content; distinguish absent retrieval capability from lack of relevant speeches.

**Your edits / notes:**

- [x] Approved

---

### U29 — Which was enacted first, Bill 23 of 2025 or Bill 48 of 2024?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Resolve both Bill identities and compare actual dated enactment evidence only if it exists for both; otherwise report the specific coverage problem preventing comparison.

**Optional context:** Provide dated enactment evidence and official Bill links.

**Data dependency:** Bill identity, authoritative enactment events, and reviewed quarantine/coverage diagnostics for Bill 48 of 2024.

**Decision:** Do not replace a missing Bill with a similarly numbered Bill or infer enactment from legislative year.

**Your edits / notes:**

- [x] Approved

---

### U30 — How many TDs were in the 33rd Dáil, including replacements?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Distinguish the possible meanings of 'including replacements': the number of seats at a point in time versus the number of distinct people who served during the term. Clarify or explicitly present both only when properly evidenced.

**Optional context:** Explain the difference between seats and individual service episodes.

**Data dependency:** Authoritative seat complement and complete Member-term roster including by-election or replacement memberships.

**Decision:** Do not conflate the approved 160-seat complement with a larger count of distinct Members who served across the term.

**Your edits / notes:**

- [x] Approved

---

### U31 — Which Members of the 33rd Dáil never belonged to any political party?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Identify that 'never' makes a lifetime negative claim and return only identities for which comprehensive party affiliation history can support that claim; otherwise explain the evidence limitation.

**Optional context:** Offer an explicitly different question about Independent status during the 33rd Dáil.

**Data dependency:** Complete historical affiliations and explicit Independent status with trusted scope, plus full 33rd-Dáil Member roster.

**Decision:** Absence of party triples in a partial Member record cannot prove lifelong independence.

**Your edits / notes:**

- [x] Approved

---

### U32 — Which committees have never discussed the HSE?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Do not enumerate committees as never having discussed the HSE unless substantive topic evidence and comprehensive committee transcript coverage make the negative test valid.

**Optional context:** Offer to identify documented committee hearings that did discuss the HSE instead.

**Data dependency:** Comprehensive committee Debate/transcript topic evidence, alias review for HSE and committee history.

**Decision:** Treat this as a global negative requiring strong coverage, not merely a SPARQL NOT EXISTS over a partial graph.

**Your edits / notes:**

- [x] Approved

---

### U33 — What is the most recent Bill sponsored by Malcolm Byrne?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Resolve the Member and select the latest dated sponsorship-related Bill only when the date semantics and relevant source coverage support 'most recent'; otherwise explain the limitation.

**Optional context:** List candidate recent Bills with dates and uncertainty when useful.

**Data dependency:** Exact Member identity, Bill sponsor Participations, defensible event dates and sufficiently fresh/comprehensive Bill source coverage.

**Decision:** Do not equate maximum Bill number or legislative year with the latest sponsorship event; current local Member resolution may also fail.

**Your edits / notes:**

- [x] Approved

---

### U34 — Has Simon Harris been Minister for Finance throughout 2026?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Distinguish a question about the elapsed portion of 2026 from the entire calendar year, then evaluate any stated period only against accepted dated OfficeHoldings and adequate coverage.

**Optional context:** Give the as-of date and any evidenced tenure boundaries.

**Data dependency:** Current and historical Minister for Finance OfficeHoldings, as-of date and coverage through the requested endpoint.

**Decision:** Do not make claims about future days of 2026 or assume continuous service from a single incomplete open-ended holding.

**Your edits / notes:**

- [x] Approved

---

### U35 — Show me the Committee of Public Accounts hearing on 31 February 2024.

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Reject the impossible calendar date clearly before constructing or executing a query, inviting a corrected date.

**Optional context:** Keep the recognised Committee of Public Accounts identity as context, without guessing a nearby date.

**Data dependency:** Calendar validation; no RDF records are needed to diagnose the date.

**Decision:** Invalid dates are interpretation/validation failures, not 'no hearing occurred' or empty Fuseki results.

**Your edits / notes:**

- [x] Approved

---

### U36 — How much money did the Public Accounts Committee allocate to the HSE in 2024?

**Track:** Unseen evaluation — boundary/adversarial

**Required answer:** Recognise that the question assumes an allocation relationship not established for the Committee of Public Accounts; do not invent a funding amount or substitute amounts mentioned during examination.

**Optional context:** Offer an evidence-appropriate question, such as when PAC examined HSE expenditure, if supported.

**Data dependency:** An authoritative allocation decision and responsible institution would be needed for an amount; the reviewed current query mappings do not establish PAC allocations.

**Decision:** Do not confuse scrutiny of spending with allocating funds; explain the unsupported premise without claiming complete knowledge of all funding decisions.

**Your edits / notes:**

- [x] Approved

---

## Post-review evaluation notes

- Preserve a truly unseen holdout for the final assessment. Do not send these questions to the planner implementation agent during the active completion campaign. Once they are disclosed or used to tune the planner, retire them from the blind set and sample replacement questions for subsequent testing.
- Evaluate interpretation separately from available data: report *valid plan but unavailable evidence* distinctly from *planner misunderstood*, *unsupported query mapping*, *unsafe execution*, and *incorrect answer*.
- Treat the approved question set as the existing development/acceptance baseline; this draft provides additional generalisation coverage and no extra acceptance gate for the currently active campaign.
