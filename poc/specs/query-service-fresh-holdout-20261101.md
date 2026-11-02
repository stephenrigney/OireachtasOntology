# Query Service — Fresh generalisation holdout (2026-11-01)

**Status:** Frozen candidate for a first baseline run. Authored after PR #16 and after the earlier U01–U36 set had been used in development. No execution results are recorded here.

**Purpose:** Test whether unfamiliar wording and compositions can use existing query capabilities without additional per-question code. This set is distinct in wording and intended combinations from the earlier approved catalogue; it is *not* guaranteed to be statistically independent of prior development, and should not be advertised as externally sourced user questions.

**Authority:** The current Query Service and `poc/specs/query-schema-contract.json`, the approved answer semantics in `poc/specs/query-service-questions-approved.md`, and the prior U01–U36 set used only to avoid direct reuse. This holdout does **not** approve new ontology semantics or assert completeness of the local dataset.

**Baseline protocol (freeze before run):**

1. Record Git SHA, dataset URL/graph inventory or fingerprint, active service version, and fixed `asOf = 2026-11-01` (Europe/Dublin); record any inability to inject this date and the actual service reference time. Do not run or modify code while authoring this set.
2. Execute each question once through the integrated `/ask` endpoint, with normal configuration and bounded queries. Preserve raw response, rendered answer, resolution states, query/plan diagnostics and any execution error. No implementation fixes, prompt tuning, graph publication or retries during the scored pass.
3. Judge the *observable answer* against the intent/guardrail below. The expected behaviour is conditional on evidence: do not turn a missing dataset into a supposedly correct factual answer. Where necessary inspect the already published RDF or a small fixture read-only *after* recording the baseline.
4. Record separately: intent understood (Y/N), required relationships selected (Y/N/not applicable), query executed (Y/N), factual/coverage support (complete/partial/absent/unknown), final outcome (correct answer / justified limitation / incorrect answer / unjustified refusal / runtime error), and primary cause (interpretation, resolution, capability exposure, composition, temporal, execution, rendering, data coverage, or invalid request).
5. Report category-wise counts and a cause-by-case matrix; separately calculate **supported-capability generalisation** only over questions whose necessary capability and evidence are confirmed available. Show the denominator and exclude genuine unsupported/data-limited cases rather than scoring them as successes for answering.
6. This document must remain unchanged after measurement. Record observations in a separate report; repeat runs, if any, must be clearly labelled diagnostic, not a fresh holdout.

**Important:** A correctly qualified refusal is acceptable for unsupported or incomplete evidence, but not for a question whose known available relationships could answer it. A plan that validates without a correct human-readable answer does not pass.

## Paraphrase and idiomatic interpretation (P01–P12)

### P01 — Is Aengus Ó Snodaigh still serving as a TD?

**Expected behaviour / guardrail:** Interpret 'still' at frozen as-of date; return dated current Dáil membership or a qualified inability to establish it; do not treat any historical membership as current.

### P02 — Give me the parliamentary party history of Catherine Connolly.

**Expected behaviour / guardrail:** Return dated party affiliations where evidenced, distinguishing Independent collection status from enduring political-party identities; do not invent party episodes.

### P03 — Which Deputies sat for Cork South-West in the Dáil before this one?

**Expected behaviour / guardrail:** Resolve the previous Dáil from as-of term dates, then return all evidenced constituency representatives, including replacements; do not hardcode a term.

### P04 — Had Micheál Martin become Taoiseach by 1 October 2026?

**Expected behaviour / guardrail:** Answer from accepted Taoiseach OfficeHolding episode(s) at or before date; clarify temporal sense and disclose gaps rather than use current title alone.

### P05 — Find legislation listing Malcolm Byrne among its sponsors.

**Expected behaviour / guardrail:** Resolve the Member and return distinct sponsored Bills, irrespective of primary/supporting flag; show titles and only evidenced sponsor roles.

### P06 — What is the official title of the Bill numbered 23 in 2025?

**Expected behaviour / guardrail:** Resolve Bill identity by year and number and return English title when source-backed; do not mistake legislative year for a date filter.

### P07 — Where does Mary Lou McDonald sit in the current Dáil?

**Expected behaviour / guardrail:** Interpret 'where' as constituency representation in parliamentary context; return evidenced current constituency, not physical seating or an unqualified guess.

### P08 — Did Aengus Ó Snodaigh serve during Dáil 33?

**Expected behaviour / guardrail:** Resolve ordinal Dáil term and Member; answer membership yes/no only with sufficient evidence, optionally showing date bounds.

### P09 — When did Timmy Dooley first take a seat in the Seanad?

**Expected behaviour / guardrail:** Use earliest evidenced Seanad membership entry date; distinguish later episodes and do not infer it from a different House.

### P10 — Show all the constituencies associated with Bertie Ahern's time as a TD.

**Expected behaviour / guardrail:** Give term-scoped constituency occurrences over recorded career; do not collapse resources solely on matching labels.

### P11 — What happened most recently in the legislative process for Bill 23/2025?

**Expected behaviour / guardrail:** Return latest evidenced dated activity/status and distinguish missing event history from a current status label; no predicted next step.

### P12 — Which TDs speak for Dublin Central now?

**Expected behaviour / guardrail:** Interpret 'speak for' as parliamentary representation; use the date-relative current Dáil and current representation intervals.

## New relationship combinations and aggregates (C01–C12)

### C01 — Of the TDs representing Waterford now, which have recorded Fianna Fáil affiliation now?

**Expected behaviour / guardrail:** Join current term constituency representation and contemporaneous reviewed enduring-party affiliation; warn where party/roster coverage is insufficient.

### C02 — Which current TDs have previously been Senators?

**Expected behaviour / guardrail:** Intersect current Dáil membership with earlier Seanad membership for the same Member identity; 'previously' must be chronologically earlier.

### C03 — Which Bills list a sponsor who represented Dublin Central during the 34th Dáil?

**Expected behaviour / guardrail:** Join exact Member sponsor participations with term-scoped Dublin Central representation; distinguish membership-at-any-time from sponsorship-time overlap.

### C04 — Which Members held a ministerial office while serving in the 33rd Dáil?

**Expected behaviour / guardrail:** Join accepted OfficeHolding with dated 33rd-Dáil Member service and require interval overlap; name the office and avoid extending sparse office data.

### C05 — Which TDs changed their parliamentary party during the 33rd Dáil?

**Expected behaviour / guardrail:** Compare dated party-membership episodes overlapping that Dáil; distinguish party changes from consecutive term records of the same enduring party and from Independent status.

### C06 — Which constituencies in the 34th Dáil have representatives from more than one reviewed political party?

**Expected behaviour / guardrail:** Group by term-scoped constituency and count distinct reviewed enduring party identities among contemporaneous TDs; handle Independent separately.

### C07 — How many of today's TDs also served in the 32nd Dáil?

**Expected behaviour / guardrail:** Count unique Member identities in date-relative current Dáil intersected with membership of Dáil 32; only assert exact count with adequate population coverage.

### C08 — Which Bills sponsored by Mary Lou McDonald were introduced while she was a TD?

**Expected behaviour / guardrail:** Join named sponsor to Bill introduction/presentation events and dated Dáil service; do not assume every sponsorship is dated or use legislative year as event date.

### C09 — Which current Government members have also sponsored Bills?

**Expected behaviour / guardrail:** Intersect constitutional Government membership at as-of with historically recorded Bill sponsorship; show recorded matches and warn if Cabinet or Bills coverage is incomplete.

### C10 — Which Members have represented Waterford in more than one Dáil term?

**Expected behaviour / guardrail:** Group distinct Member identities across Waterford term-scoped constituency occurrences; count distinct terms, not duplicated episodes.

### C11 — Which 2025 Bills were sponsored by TDs who had previously served as Senators?

**Expected behaviour / guardrail:** Join Bill year, person sponsorship and earlier Seanad service before a justified sponsorship date; if date of sponsorship is unavailable, explain temporal limitation.

### C12 — Which Ministers for Finance were affiliated with Fianna Fáil while holding that office?

**Expected behaviour / guardrail:** Intersect dated accepted office holdings and reviewed enduring Fianna Fáil membership at overlapping periods; no inference from later party or current office.

## Ambiguity, negatives, temporal and evidence boundaries (B01–B12)

### B01 — Who represents Dublin?

**Expected behaviour / guardrail:** Recognise 'Dublin' as potentially multiple constituencies/locations; request a meaningful clarification or offer grounded choices, not a fabricated single constituency.

### B02 — Which party will Mary Lou McDonald belong to next year?

**Expected behaviour / guardrail:** Do not project future affiliation from open-ended historical RDF; distinguish future claim from evidenced status as of date.

### B03 — Which Members have never sponsored a Bill?

**Expected behaviour / guardrail:** Treat 'never' as a global negative requiring comprehensive Bills and sponsor coverage; do not interpret absence of participation triples as proof.

### B04 — Quote exactly what Catherine Connolly said about housing in the Dáil.

**Expected behaviour / guardrail:** Do not manufacture speech text from Debate metadata; explain transcript/attribution retrieval limitation if not present.

### B05 — Who is the youngest serving TD?

**Expected behaviour / guardrail:** Require authoritative birth dates, active service and comprehensive coverage; no ranking or guessed age from names.

### B06 — Who was Minister for Finance on 31 September 2024?

**Expected behaviour / guardrail:** Reject impossible date before RDF execution and offer correction; do not answer for September 30 automatically.

### B07 — Did every Fianna Fáil TD sponsor a Bill in 2025?

**Expected behaviour / guardrail:** Recognise universal quantification requiring complete dated TD/party roster and sponsorship coverage; do not claim true or false from partial data.

### B08 — How did Waterford's TDs vote on the AI Companion Services Bill?

**Expected behaviour / guardrail:** Require Bill-linked divisions and individual voting evidence, not sponsorship or party affiliation; qualify absent votes and ambiguous division.

### B09 — Which political party was Stephen Donnelly a member of on 1 January 2014?

**Expected behaviour / guardrail:** Apply point-in-time membership evidence; do not equate absence from later recorded episodes with a proven negative for 2014.

### B10 — Which Bills did John Murphy sponsor?

**Expected behaviour / guardrail:** Resolve named Member without assuming uniqueness; if multiple local candidates, ask to disambiguate and do not merge sponsorships by literal name.

### B11 — What was the final Dáil question asked yesterday?

**Expected behaviour / guardrail:** Resolve 'yesterday' relative to fixed as-of and determine whether ordered parliamentary question evidence exists; do not substitute debate date alone or invent a last item.

### B12 — Name every 34th-Dáil TD whose party affiliation is unknown.

**Expected behaviour / guardrail:** Distinguish explicitly unknown affiliation from missing/unreviewed links; only enumerate with verified completeness and a defensible unknown definition.

## Result recording template

| ID | Intent | Capability/composition | Evidence | Final outcome | Primary cause | Notes/evidence reference |
|---|---|---|---|---|---|---|
| P01 | — | — | — | Not run | — | — |
| P02 | — | — | — | Not run | — | — |
| P03 | — | — | — | Not run | — | — |
| P04 | — | — | — | Not run | — | — |
| P05 | — | — | — | Not run | — | — |
| P06 | — | — | — | Not run | — | — |
| P07 | — | — | — | Not run | — | — |
| P08 | — | — | — | Not run | — | — |
| P09 | — | — | — | Not run | — | — |
| P10 | — | — | — | Not run | — | — |
| P11 | — | — | — | Not run | — | — |
| P12 | — | — | — | Not run | — | — |
| C01 | — | — | — | Not run | — | — |
| C02 | — | — | — | Not run | — | — |
| C03 | — | — | — | Not run | — | — |
| C04 | — | — | — | Not run | — | — |
| C05 | — | — | — | Not run | — | — |
| C06 | — | — | — | Not run | — | — |
| C07 | — | — | — | Not run | — | — |
| C08 | — | — | — | Not run | — | — |
| C09 | — | — | — | Not run | — | — |
| C10 | — | — | — | Not run | — | — |
| C11 | — | — | — | Not run | — | — |
| C12 | — | — | — | Not run | — | — |
| B01 | — | — | — | Not run | — | — |
| B02 | — | — | — | Not run | — | — |
| B03 | — | — | — | Not run | — | — |
| B04 | — | — | — | Not run | — | — |
| B05 | — | — | — | Not run | — | — |
| B06 | — | — | — | Not run | — | — |
| B07 | — | — | — | Not run | — | — |
| B08 | — | — | — | Not run | — | — |
| B09 | — | — | — | Not run | — | — |
| B10 | — | — | — | Not run | — | — |
| B11 | — | — | — | Not run | — | — |
| B12 | — | — | — | Not run | — | — |

## Acceptance of benchmark as an evaluation artifact

- All 36 questions and their intent/guardrails pre-registered before the first run.
- Original questions and this holdout are not changed to accommodate observed responses.
- The resulting report identifies *generalisation failures* separately from legitimately unsupported or missing-data requests, and names common failure classes rather than prescribing 36 individual fixes.
- Any architectural recommendation is based on observed planner behaviour, not simply the raw percentage of answered questions.
