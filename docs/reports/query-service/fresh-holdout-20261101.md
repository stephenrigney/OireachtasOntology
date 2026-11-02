# Query Service — Fresh Generalisation Benchmark

## Executive summary

The first pass was invalidated because its server lacked `NLQ_LLM_API_KEY`; its
responses and the subsequent diagnostic reruns remain preserved unchanged. This
report now includes the **first valid configured scored baseline**: all 36
questions completed through the integrated Phase 2 `/ask` endpoint with a
verified planner credential, fixed reference date, and the same live Fuseki
dataset. It produced **5 correct factual answers, 12 other guardrail-compliant
outcomes, and 19 generalisation gaps** (including 12 fail-closed composition
gaps, not hallucinations or unsafe query execution).

The semantic fallback successfully handled unfamiliar phrasings for party
history, sponsorship and constituency representation. It did not compose the
new multi-family/aggregate cases, and it declined three questions whose
single-family operations already exist in Stage A/B but are not exposed to the
fallback. The evidence supports improving capability discovery/dispatch and
then bounded composition—not redesigning planner architecture.

**Recommendation:** first expose a small set of existing validated Stage A/B
capabilities (Bill lookup and earliest Seanad membership) to semantic fallback
selection without adding question-specific rules. Then take one narrowly scoped
cross-family composition case. Address the two interpretation/resolution errors
separately. No implementation change was made during this benchmark.

## Frozen protocol, provenance, and environment

- Frozen questions/expectations: `poc/specs/query-service-fresh-holdout-20261101.md`
  (unchanged).
- Worktree branch at start: `docs/query-service-fresh-holdout-20261101`, clean;
  HEAD `82fd0235e26c8a84601de401f50ffca9c3ab699a`. PR #16 merge
  `520765fb07e063efa42859297c5630e934c2c670` is an ancestor. The initial
  responding process was the identical Query Service code at that merge SHA in
  the primary checkout; the subsequent diagnostic process ran from this
  worktree at `82fd023`.
- Reference date: **2026-11-01**. The initial server used the host date, also
  2026-11-01. The diagnostic server was explicitly started with
  `OIR_NLQ_AS_OF_DATE=2026-11-01`.
- Endpoint: `http://127.0.0.1:8000/ask`, form mode `phase2`; all 36 HTTP
  responses were 200. The existing local Fuseki endpoint was
  `http://localhost:3030/houses/query`, dataset `/houses`.
- Planner: model `gpt-6-luna`, default base endpoint
  `https://opencode.ai/inference/openai/v1`, 45-second configured request
  timeout and 2,000 output-token cap. No key material is recorded. In the
  original pass, the server process had no API key in its environment or
  repository `.env`, so every semantic-plan request requiring the model failed
  with `Set NLQ_LLM_API_KEY before requesting a structured plan.` The worktree's
  ignored `.env.local` did contain the configured key; it was loaded only for
  the diagnostic server.
- Read-only Fuseki graph inventory recorded before questions: **7,982 named
  graphs, 1,119,860 triples**. By graph family: 1,928 Member graphs (179,720
  triples), 6,044 Bill graphs (917,294), 3 Debate graphs (9,383), and one each
  for Houses (721), Constituencies (7,645), Parties (1,890), Offices (13),
  Administrative Units (2), Committees (2,799), and political-affiliation
  identities (393). Inventory fingerprint is
  `sha256:635ea538057bb3367bb335e310fc7f475b4530bc2ce41a1059d2c27a297c3e02`,
  calculated over sorted graph-IRI/triple-count pairs. The reviewed enrichment
  graph `https://data.oireachtas.ie/graph/political-affiliations/identities`
  was present (393 triples). This is an observed inventory fingerprint, not a
  bootstrap source-capture dataset ID; no stable bootstrap baseline was
  available without reloading data, which was not done.
- No Query Service code, ontology, ETL, or RDF data was changed. No retry was
  made within either pass. The original and diagnostic response files below
  preserve the full HTML response, visible text, and response SHA-256 per case.

## Initial scored baseline attempt (invalidated; preserved)

The scorer evaluates the user-visible response against the frozen guardrail;
successful plan generation alone does not pass. “Planner config” below is a
runtime failure, not an unsupported-capability result. A passing limitation is
counted only where the benchmark explicitly permits a qualified refusal.

| ID | Observable baseline | Outcome / primary cause |
|---|---|---|
| P01 | Planner setup error; no answer query | Runtime error — planner configuration |
| P02 | Planner setup error; no answer query | Runtime error — planner configuration |
| P03 | Planner setup error; no answer query | Runtime error — planner configuration |
| P04 | Planner setup error; no answer query | Runtime error — planner configuration |
| P05 | Planner setup error; no answer query | Runtime error — planner configuration |
| P06 | Planner setup error; no answer query | Runtime error — planner configuration |
| P07 | Planner setup error; no answer query | Runtime error — planner configuration |
| P08 | Planner setup error; no answer query | Runtime error — planner configuration |
| P09 | Planner setup error; no answer query | Runtime error — planner configuration |
| P10 | Planner setup error; no answer query | Runtime error — planner configuration |
| P11 | Planner setup error; no answer query | Runtime error — planner configuration |
| P12 | Planner setup error; no answer query | Runtime error — planner configuration |
| C01 | Planner setup error; no answer query | Runtime error — planner configuration |
| C02 | Planner setup error; no answer query | Runtime error — planner configuration |
| C03 | Planner setup error; no answer query | Runtime error — planner configuration |
| C04 | Planner setup error; no answer query | Runtime error — planner configuration |
| C05 | Planner setup error; no answer query | Runtime error — planner configuration |
| C06 | Refused extra party/representation aggregate; no answer query | Correctly limited — composition unsupported |
| C07 | Planner setup error; no answer query | Runtime error — planner configuration |
| C08 | Planner setup error; no answer query | Runtime error — planner configuration |
| C09 | Planner setup error; no answer query | Runtime error — planner configuration |
| C10 | Planner setup error; no answer query | Runtime error — planner configuration |
| C11 | Planner setup error; no answer query | Runtime error — planner configuration |
| C12 | Planner setup error; no answer query | Runtime error — planner configuration |
| B01 | Planner setup error; no answer query | Runtime error — planner configuration |
| B02 | Planner setup error; no answer query | Runtime error — planner configuration |
| B03 | Planner setup error; no answer query | Runtime error — planner configuration |
| B04 | Planner setup error; no answer query | Runtime error — planner configuration |
| B05 | “the youngest serving TD” treated as a Member name; no match | Incorrect — interpretation/entity resolution |
| B06 | Planner setup error; no answer query | Runtime error — planner configuration |
| B07 | Planner setup error; no answer query | Runtime error — planner configuration |
| B08 | Planner setup error; no answer query | Runtime error — planner configuration |
| B09 | Planner setup error; no answer query | Runtime error — planner configuration |
| B10 | John Murphy resolves to two distinct local Member identities; neither selected | Correct — ambiguity handling |
| B11 | Planner setup error; no answer query | Runtime error — planner configuration |
| B12 | Planner setup error; no answer query | Runtime error — planner configuration |

### Observed initial category breakdown (not a valid generalisation score)

| Category | Correct / guardrail-compliant | Incorrect | Runtime error | Total |
|---|---:|---:|---:|---:|
| Paraphrase and idiomatic interpretation (P) | 0 | 0 | 12 | 12 |
| New relationship combinations and aggregates (C) | 1 | 0 | 11 | 12 |
| Ambiguity, negatives, temporal and evidence boundaries (B) | 1 | 1 | 10 | 12 |
| **Total** | **2** | **1** | **33** | **36** |

No supported-capability generalisation rate is meaningful for this scored pass:
the planner configuration error prevented establishing which otherwise
answerable questions the service could handle. The two compliant outcomes are
not evidence of broad generalisation.

## Diagnostic reruns (not scored)

Each question was posted once more only after the original response artifact
was written. The JSON record is labelled `DIAGNOSTIC ONLY`. With configuration
available, the observable results were:

| Category | Evidenced answer | Qualified limitation | Incorrect / unjustified outcome | Details |
|---|---:|---:|---:|---|
| P | 5 | 1 | 6 | Answers P02, P05, P07, P10, P12. P11 appropriately says latest Bill event retrieval is unsupported. P01, P03, P04, P06, P08, P09 decline instead of producing the requested answer. |
| C | 0 | 12 | 0 | Every requested multi-relationship/aggregate shape was explicitly refused; no simplification or answer query ran. These are current capability/composition gaps, not successful answers. |
| B | 1 | 8 | 3 | B10 correctly preserves ambiguity. B02–04, B07–09, B11–12 give bounded limitations. B01 resolves “Dublin” as one constituency lookup and reports no match; B05 attempts to resolve a ranking phrase as a person; B06 does not reject the impossible date before describing an unsupported office query. |

The above groups classify *observable outcomes*, not an alternate scored
baseline. Limitations for C01–C12 are justified relative to the implemented
bounded plan families, but their repeated frequency is evidence that the
current composition surface is much narrower than the RDF relationships and
individual facts suggest. They are excluded from success counts. No execution
failure or missing-data result was observed in these cases because no answer
query ran.

### Diagnostic case outcomes (not scored)

| ID | Diagnostic user-facing outcome | Classification |
|---|---|---|
| P01 | Refused current TD status as unsupported | Capability discovery / interpretation gap |
| P02 | Returned Catherine Connolly's reviewed political-affiliation labels and dated supporting episodes | Answer; evidence qualified by local coverage |
| P03 | Refused selecting the Dáil before the current one | Temporal/capability discovery gap |
| P04 | Refused Taoiseach office history by a supplied date | Temporal/capability gap |
| P05 | Returned recorded Bills sponsored by Malcolm Byrne with bill titles and sponsor evidence | Answer; exact Member resolution and sponsorship query succeeded |
| P06 | Refused Bill lookup by year and number | Interpretation/capability-discovery gap |
| P07 | Returned Mary Lou McDonald's current constituency and term at 2026-11-01 | Answer; dated representation evidence |
| P08 | Refused a single Member's membership in a numbered Dáil | Capability exposure gap |
| P09 | Refused earliest Seanad entry date | Interpretation/capability-discovery gap |
| P10 | Returned term-scoped constituency occurrences for Bertie Ahern | Answer; identities and terms preserved |
| P11 | Refused latest Bill-process event retrieval | Justified limitation; event-history scope absent |
| P12 | Returned current Dublin Central representatives at 2026-11-01 | Answer; dated representation evidence |
| C01 | Refused current Waterford representation plus current reviewed affiliation | Composition capability gap; no answer query |
| C02 | Refused current TDs intersected with prior Seanad service | Composition capability gap; no answer query |
| C03 | Refused Bill sponsors intersected with term-scoped Dublin Central representation | Composition capability gap; no answer query |
| C04 | Refused ministerial-office overlap with 33rd-Dáil service | Composition capability gap; no answer query |
| C05 | Refused party changes during a specified Dáil | Composition/temporal capability gap; no answer query |
| C06 | Refused grouping 34th-Dáil constituencies by distinct reviewed parties | Aggregate/composition capability gap; no answer query |
| C07 | Refused current TDs intersected with Dáil 32 and counted | Composition/aggregate capability gap; no answer query |
| C08 | Refused Bill sponsorship intersected with introduction during Member service | Composition/temporal capability gap; no answer query |
| C09 | Refused current Government membership intersected with Bill sponsorship | Composition capability gap; no answer query |
| C10 | Refused multi-term Waterford representation aggregation | Composition/aggregate capability gap; no answer query |
| C11 | Refused 2025 Bill sponsors intersected with prior Seanad service | Composition/temporal capability gap; no answer query |
| C12 | Refused historical Finance officeholders intersected with contemporaneous Fianna Fáil affiliation | Composition/temporal capability gap; no answer query |
| B01 | Treated “Dublin” as one current constituency lookup and reported no match | Interpretation/entity-resolution failure; expected clarification |
| B02 | Refused predicting next year's party membership | Correct qualified limitation; future prediction unsupported |
| B03 | Refused inferring who has never sponsored a Bill | Correct qualified limitation; global negative unsupported |
| B04 | Refused exact speech quotation | Correct qualified limitation; verbatim speech retrieval unsupported |
| B05 | Treated “youngest serving TD” as a Member name and returned no match | Interpretation/entity-resolution failure; age/service coverage not assessed |
| B06 | Refused office-by-date lookup without identifying 31 September as invalid | Temporal validation/interpretation failure |
| B07 | Refused universal sponsorship assertion | Correct qualified limitation; completeness unsupported |
| B08 | Refused vote lookup | Correct qualified limitation; voting records unsupported |
| B09 | Refused point-in-time party lookup rather than asserting a negative | Correct qualified limitation; no unsupported negative asserted |
| B10 | Returned two John Murphy candidates and selected neither | Correct ambiguity handling |
| B11 | Refused retrieving the final Dáil question yesterday | Correct qualified limitation; question-record scope unavailable |
| B12 | Refused enumerating all unknown party affiliations | Correct qualified limitation; completeness/unknown semantics unsupported |

## First valid configured scored baseline

This pass is the scored result for the frozen benchmark. It does not overwrite
or replace the initial failed baseline or the diagnostic response file above.
Before starting it:

- The Responses planner was instantiated with the API key read in memory from
  the main `OireachtasOntology/.env.local` and successfully returned a
  structured composable-plan draft for a separate preflight request. The raw
  preflight output and key were not recorded.
- A read-only query to `http://localhost:3030/houses/query` confirmed dataset
  `/houses` and the reviewed political-affiliation graph, with 393 triples.
- The Query Service process ran from this worktree at revision `77b724f`, with
  `OIR_NLQ_AS_OF_DATE=2026-11-01`, model `gpt-6-luna`, and the configured
  Responses endpoint. The key was passed as a process-environment setting; no
  credential value appears in the result artifact. All 36 requests returned
  HTTP 200; one POST per question, no retries. The pass ran
  `2026-11-01T17:04:46Z`–`2026-11-01T17:07:11Z`.

### Per-question scored outcomes

The scoring distinction is between a correct observable answer/guardrail and a
question the implementation declined despite an expected answer path. A
fail-closed unsupported response is safe, but it does not count as generalised
composition when the benchmark asks for an existing relationship or capability
to be used. It is not thereby an architecture defect.

| ID | Configured `/ask` result | Scored outcome / primary cause |
|---|---|---|
| P01 | Says current TD service status for a named Member is not supported; no answer query | Correct qualified limitation; current-status query not established |
| P02 | Returns the reviewed political affiliation `Independents 4 Change` and its dated supporting episode | Correct factual answer; identity-based party history |
| P03 | Refuses filtering constituency representatives to Dáil terms before the current one | Generalisation gap — previous-term/constituency composition |
| P04 | Refuses determining whether Micheál Martin became Taoiseach by the date | Correct qualified limitation; targeted read-only probe found no joined local Taoiseach holding row, so no historical negative is inferred |
| P05 | Returns Malcolm Byrne's distinct sponsored Bills, including supporting participations and recorded roles | Correct factual answer; Member resolution and sponsor relationship |
| P06 | Refuses Bill lookup by number/year as unsupported | Generalisation gap — existing `bill_lookup` not selected for paraphrase; exact Bill/title evidence is present |
| P07 | Returns Mary Lou McDonald's current constituency and 34th-Dáil term at the fixed date | Correct factual answer; current representation |
| P08 | Refuses one Member's service in one numbered Dáil as unsupported query shape | Generalisation gap — existing Member/term relationships not composed into the requested boolean |
| P09 | Refuses Seanad membership/first-seat date as unsupported | Generalisation gap — existing Stage A `seanad_entry` capability not selected; two dated episodes are present, earliest starts 2002-09-12 |
| P10 | Returns Bertie Ahern's term-scoped constituency occurrences | Correct factual answer; career representation identities preserved |
| P11 | Refuses latest Bill event/status retrieval | Capability-discovery gap — existing Bill lookup/history family not selected; Bill graph exists, but dated event evidence was not independently confirmed |
| P12 | Returns the recorded current Dublin Central representatives at the fixed date | Correct factual answer; current representation |
| C01 | Refuses current Waterford representation plus current Fianna Fáil affiliation | Composition gap — current/as-of constraint across party and representation facts |
| C02 | Refuses current TDs intersected with earlier Seanad service | Composition gap — House-membership intersection |
| C03 | Refuses Bill sponsorship joined to term-scoped Dublin Central representation | Composition gap — sponsorship plus constituency/term |
| C04 | Refuses officeholding overlapping 33rd-Dáil service | Composition gap — OfficeHolding plus Member-term interval |
| C05 | Refuses detecting party changes during the 33rd Dáil | Composition/temporal gap — compare party episodes within a term |
| C06 | Refuses grouping 34th-Dáil constituencies by reviewed-party count | Aggregate extension gap — bounded party/representation plan cannot group all constituencies |
| C07 | Refuses counting current TDs who also served in Dáil 32 | Composition/aggregate gap — current filter, prior-term membership and count |
| C08 | Refuses Bill sponsorship filtered to introduction while the Member was a TD | Composition/temporal gap — Bill activity date plus Member service |
| C09 | Refuses current Government members intersected with Bill sponsors | Composition gap — Government and sponsorship families |
| C10 | Refuses Waterford representatives in more than one unspecified Dáil term | Aggregate extension gap — career-wide multi-term threshold |
| C11 | Refuses 2025 Bill sponsors intersected with prior Seanad service | Composition/temporal gap — Bill/year and cross-House membership |
| C12 | Refuses historical Finance officeholders intersected with contemporaneous Fianna Fáil affiliation | Composition/temporal gap — office and party episode overlap |
| B01 | Resolves “Dublin” as one constituency mention, reports no match, and does not ask which Dublin | Incorrect — interpretation/entity-resolution; ambiguity guardrail missed |
| B02 | Refuses predicting next year's party affiliation | Correct qualified limitation; future status not inferred |
| B03 | Refuses identifying Members who have never sponsored a Bill | Correct qualified limitation; global negative not inferred |
| B04 | Refuses exact speech quotation | Correct qualified limitation; transcript/quote retrieval unavailable |
| B05 | Treats “the youngest serving TD” as a Member name and reports no match | Incorrect — aggregate intent/entity-resolution; age and roster coverage not evaluated |
| B06 | Reports both office-date capability limitation and that 31 September is invalid; no answer query | Correct input validation; impossible date rejected before execution |
| B07 | Refuses universal sponsorship claim | Correct qualified limitation; completeness not inferred |
| B08 | Refuses vote lookup for lack of voting evidence capability | Correct qualified limitation; no vote inferred from other relations |
| B09 | Refuses point-in-time party membership lookup; makes no negative claim | Correct qualified limitation; dated-status absence is not treated as proof |
| B10 | Returns two distinct John Murphy identities and selects neither | Correct ambiguity handling |
| B11 | Refuses identifying the final Dáil question yesterday as outside local scope | Correct qualified limitation; ordered question-record evidence unavailable |
| B12 | Refuses enumerating 34th-Dáil TDs with unknown affiliation | Correct qualified limitation; missing links are not treated as known-unknown |

### Category scores and cause counts

| Category | Correct factual answer | Correct qualified/guardrail outcome | Generalisation gap | Total |
|---|---:|---:|---:|---:|
| Paraphrase and idiomatic interpretation (P) | 5 | 2 | 5 | 12 |
| New relationship combinations and aggregates (C) | 0 | 0 | 12 | 12 |
| Ambiguity, negatives, temporal and evidence boundaries (B) | 0 | 10 | 2 | 12 |
| **Total** | **5** | **12** | **19** | **36** |

The 19 gaps comprise **14 composition/shape gaps** (P03, P08, C01–C12),
**3 existing-capability discovery/dispatch gaps** (P06, P09, P11), and **2
interpretation/resolution failures** (B01, B05). There were no HTTP/runtime
errors and no demonstrated SPARQL execution failure. Unsupported plans did not
run answer queries. P02's rendered label was checked post-baseline against its
exact generated read-only query: the store returns one label, `Independents 4
Change`, with one dated episode, so it is not two affiliations accidentally
merged by the renderer. P06's exact `/graph/bill/2025/23` graph contains the
English title `Pregnancy Loss (Miscellaneous Provisions) Bill 2025`. A targeted
read-only Member-graph probe confirmed Timmy Dooley's earliest recorded Seanad
membership starts 2002-09-12, with a later episode starting 2020-06-29. The
Micheál Martin office probe found no joined Taoiseach holding evidence; this is
coverage uncertainty, not evidence that he never held the office. P11's Bill
graph is present but its exact dated-event evidence remains unverified.

Under the frozen protocol's supported-capability denominator, **5/7** cases
with the needed capability and evidence confirmed were answered correctly:
P02, P05, P06, P07, P09, P10, and P12 were confirmed as supported/evidenced;
P06 and P09 were declined. P11 is excluded because the exact event evidence
was not confirmed. P04 is excluded because the required local OfficeHolding
evidence was not found. New joins/aggregates without case-level evidence probes
are reported as composition gaps, not counted as answered or as proven data
coverage failures.

### Deterministic recognition versus semantic fallback

The integrated path checks deterministic representation, Government, Stage A,
Stage C, Stage B, and composable recognizers before invoking the semantic
fallback. The five successful P cases did not match the corresponding pure
deterministic recognizers; their results are consistent with validated
semantic-fallback plans for already supported families: party history (P02),
Bill sponsorship (P05), and constituency representation (P07/P10/P12). This is
positive evidence that semantic fallback generalises *within* its advertised
families, with correct identity resolution, bounded answer queries, and human-
readable results.

The fallback does **not** expose all existing service capabilities. The Stage A
Seanad-entry recognizer accepts a narrow “when did … become a senator” form;
the Stage B Bill-lookup recognizer accepts a narrow “tell me about Bill N from
YYYY” form. P09, P06 and P11 use unfamiliar phrasings, miss those deterministic
recognizers, and are then labelled unsupported by the semantic fallback, whose
current family instructions do not include those Stage A/B operations. This is
a capability-discovery/dispatch gap, not missing RDF for P06/P09. Separately,
all 12 C questions fail closed: the fallback understands enough intent to name
the missing relation/aggregate but cannot compose beyond its exact approved
shapes. Those are feature-scope/composition gaps; they do not imply an unsafe
planner or justify arbitrary plan acceptance.

### Current smallest justified engineering action

Do not start with an architecture redesign or broad RDF join support. Add a
bounded semantic capability-selection path for the existing validated
`bill_lookup` and `seanad_entry` handlers, keeping their current compilers,
resolution, and safety checks. Verify with fresh paraphrases rather than
question-specific regexes. Once fallback can discover existing single-family
capabilities, select one high-value C composition for a separate reviewed
extension; retain exact temporal/identity validation and evidence qualification.
Fix B01 and B05 as narrow interpretation/resolution defects in a separate
change.

## Historical analysis from the first two passes (superseded by configured results below)

1. **Measurement/configuration blocker dominates the scored pass.** The initial
   endpoint was live and Fuseki readiness was healthy, but the process came from
   the primary checkout and lacked the worktree-local planner key. The visible
   33 errors are setup failures, not natural-language or architecture evidence.
   The diagnostic pass demonstrates this distinction; it must not be silently
   substituted for the baseline.
2. **Known answer families generalise across wording.** Diagnostic answers for
   Bill sponsorship (P05), dated/current representation (P07/P12), and
   historical constituency occurrences (P10) were rendered with local
   identities and evidence. P02 returned reviewed affiliation labels and
   supporting episode dates, keeping the answer observable rather than
   counting its plan alone. Those successes are consistent with deterministic
   Stage A/B and existing bounded families; the response does not identify
   which recognizer selected each path.
3. **Composition is the repeated gap.** C01–C12 all ended in fail-closed
   unsupported responses, including combinations of current representation
   with affiliation, current and historical House service, Bill sponsorship
   with representation/service, office overlap, party changes, and
   multi-term/party aggregates. Existing documentation explicitly limits
   composable plans to narrow shapes (for example exact numbered-term and
   constituency joins, plus dated party affiliation in that same occurrence).
   The failures therefore indicate an incomplete composition capability
   surface and planner capability discovery—not evidence that arbitrary RDF
   joins should be allowed or that the architecture is defective.
4. **Narrow interpretation defects are visible.** Broad “Dublin” was treated
   as one exact constituency reference rather than surfaced as ambiguous;
   “youngest serving TD” became a Member-name lookup; and the impossible date
   was not validated as such. These are suitable narrow interpretation,
   resolution, and temporal-validation follow-ups.
5. **Evidence and unsupported scope remain separate.** The readiness panel
   observed Member, Bills, office, party, and reviewed political-affiliation
   graph families; no graph publication occurred. This establishes presence,
   not completeness. Since refused C questions did not execute, this run cannot
   claim absent RDF evidence as their cause. B05 requires age and comprehensive
   active-service evidence that readiness does not establish. B04/B08/B11
   concern speech, votes, or ordered parliamentary-question records outside
   the observed Query Service scope, not planner execution errors.
6. **No demonstrated semantic-fallback composition success.** The successful
   results are compatible with deterministic recognizers and do not expose a
   reliable per-request route trace proving that the semantic fallback
   composed new relationships. Conversely, the diagnostic refusals prove
   fail-closed behavior but do not establish whether the model failed to
   discover an exposed composition or the composition is absent from the
   validated/compiler-supported contract. Current reports/specification
   describe only bounded compositions. Thus this benchmark provides no
   evidence for replacing the planner architecture; it does motivate adding
   and explicitly exposing a small supported composition slice.

## Prior next-step recommendation (before the configured baseline; superseded)

Before engineering changes, rerun this frozen set as the scored pass with a
server explicitly launched from the Query Service worktree using its resolved
configuration, and record that run separately from this preserved baseline.
Then, if the observed C failures persist, choose one narrowly specified
composition (with exact identities, temporal semantics, data prerequisites,
and rendered-answer checks) for capability/compiler work. Keep the three
observed B defects as separate small follow-ups. A planner-architecture redesign
is not justified by the evidence collected here.

## Machine-readable evidence

- Original responses, including full HTML, visible text and per-response hashes:
  [`fresh-holdout-20261101-baseline-responses.json`](fresh-holdout-20261101-baseline-responses.json)
- Post-baseline diagnostic reruns, clearly separated from scored results:
  [`fresh-holdout-20261101-diagnostic-reruns.json`](fresh-holdout-20261101-diagnostic-reruns.json)
- First valid configured scored baseline, including all 36 complete responses,
  visible text, timestamps and hashes:
  [`fresh-holdout-20261101-configured-baseline-responses.json`](fresh-holdout-20261101-configured-baseline-responses.json)
- Frozen source questions and expected behaviour:
  [`poc/specs/query-service-fresh-holdout-20261101.md`](../../../poc/specs/query-service-fresh-holdout-20261101.md)
