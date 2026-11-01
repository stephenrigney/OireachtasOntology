# Query Service — Fresh Generalisation Benchmark

## Executive summary

All 36 frozen questions were sent once to the integrated Phase 2 `POST /ask`
endpoint for the original pass. The endpoint and local Fuseki were reachable,
but the active server had no `NLQ_LLM_API_KEY`; 33 requests consequently stopped
at semantic-planner setup instead of testing generalisation. The original
responses are preserved and remain the scored baseline. Its observable score is
**2/36 guardrail-compliant, 1/36 unjustified answer/refusal, and 33/36 runtime
planner-configuration failures**. This is not a valid estimate of planner
generalisation.

After freezing that baseline, a separately labelled diagnostic pass used the
worktree's configured key and the same live dataset. It returned 5 evidenced
answers, 12 unsupported-composition limitations, 9 other justified limitations,
and 10 failures/incorrect refusals. These reruns are diagnostic only and do not
replace or alter the score. They show repeated capability-discovery and
composition gaps, not evidence that a new planner architecture is needed.

**Recommendation:** first make the benchmark launch/configuration path reliably
load the worktree's existing configuration, then take a properly configured
scored baseline. The smallest likely engineering slice after that is a bounded
capability-composition expansion, with narrow fixes for broad-place ambiguity,
aggregate-vs-entity interpretation, and impossible-date validation. Do not
redesign planner architecture based on this run.

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

## Original scored baseline

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

### Scored category breakdown

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

## Failure analysis and planner behaviour

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

## Smallest justified next step

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
- Frozen source questions and expected behaviour:
  [`poc/specs/query-service-fresh-holdout-20261101.md`](../../../poc/specs/query-service-fresh-holdout-20261101.md)
