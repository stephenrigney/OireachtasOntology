# Query Service — Temporal Selection and Bounded Aggregation Holdout Run

## Summary

The approved temporal-selection/count tranche was tested once against the
frozen 36-question holdout after implementation commit
`5966a42587937ca730abca7aa50ec12d736345f8`. The frozen question file was not
changed, and no code or prompt was tuned during or after the scored pass.

All 36 requests reached the integrated Phase 2 `/ask` endpoint and returned
HTTP 200. However, **31 responses were planner runtime failures**: the
Responses-compatible planner endpoint returned HTTP 400 before a plan or answer
query was produced. Consequently this run does **not** measure semantic
generalisation for those questions and is not evidence that the new capabilities
failed their controlled acceptance tests. The remaining five cases produced
three guardrail-safe limitations/clarifications, one weak clarification, and
one incorrect interpretation.

| Observable outcome | Cases | Count |
|---|---|---:|
| Correct factual answer | — | 0 |
| Guardrail-safe limitation or clarification | C06, B06, B10 | 3 |
| Weak/unjustified clarification | B07 | 1 |
| Incorrect interpretation/resolution | B05 | 1 |
| Planner runtime error (HTTP 400) | Other 31 cases | 31 |

**Supported-capability generalisation:** not assessable (`0/0` confirmed cases).
Most requests failed before local semantic plan validation. The other responses
were an unsupported composition, an invalid date, a scope clarification, an
ambiguous Member identity, and a mistaken entity lookup; none completed a
supported factual answer query. This is not a claim that no holdout item could
have been answered; it records that no item had both capability and
case-specific evidence confirmed by an executed answer path in this run.

## Protocol and environment

- Frozen questions and expected guardrails:
  [`query-service-fresh-holdout-20261101.md`](../../../poc/specs/query-service-fresh-holdout-20261101.md)
  (unchanged).
- Code revision: `5966a42587937ca730abca7aa50ec12d736345f8`.
- Fixed `asOf`: **2026-11-01**, injected through `OIR_NLQ_AS_OF_DATE`.
- Integrated endpoint: `http://127.0.0.1:8001/ask`, mode `phase2`. Port 8000
  was already occupied, so the branch's committed app was started on loopback
  port 8001. Exactly one POST was made for each frozen question; no retries.
- Planner model/base URL: configured local defaults `gpt-6-luna` and
  `https://opencode.ai/inference/openai/v1`. An API key was configured in the
  ignored `.env.local`; no key material is included here or in the response
  artifact. The app reported HTTP 400 from the planner endpoint for 31 cases;
  the provider's underlying error body was not exposed.
- Read-only local Fuseki dataset: `http://localhost:3030/houses/query`.
  Inventory: **7,982 named graphs, 1,119,860 triples**. Graph families were
  1,928 Member graphs (179,720 triples), 6,044 Bill graphs (917,294), 3 Debate
  graphs (9,383), Houses (721), Constituencies (7,645), Parties (1,890),
  Offices (13), Administrative Units (2), Committees (2,799), and political
  affiliation identities (393). Inventory SHA-256:
  `5ea5c6525d32991c053810b61706fda282dc3280a5a0ef8e74d56f49fe65bd2f`, computed
  over sorted `{graph, triples}` records serialized as compact, sorted-key JSON.
  This is an observed inventory fingerprint, not a source-capture identity.
- Full HTML responses, per-response SHA-256, outcome, status, timestamps and
  graph inventory are preserved in
  [`temporal-aggregation-holdout-20261103-responses.json`](temporal-aggregation-holdout-20261103-responses.json).

## Cause-by-case matrix

| Case(s) | Intent / observable result | Query executed? | Outcome and primary cause |
|---|---|---|---|
| P01–P12 | Planner returned HTTP 400; no semantic plan | No answer query | Runtime error — planner endpoint |
| C01–C05, C07–C12 | Planner returned HTTP 400; no semantic plan | No answer query | Runtime error — planner endpoint |
| C06 | Requested cross-constituency party-group aggregate refused | No | Guardrail-safe limitation — unsupported aggregate/composition |
| B01–B04, B08–B09, B11–B12 | Planner returned HTTP 400; no semantic plan | No answer query | Runtime error — planner endpoint |
| B05 | “the youngest serving TD” was treated as a literal Member name and not found | Member resolution only | Incorrect interpretation — ranking/birth-date intent was not recognized |
| B06 | Impossible date (31 September 2024) rejected | No RDF query | Correct clarification — invalid temporal input |
| B07 | Asked for a numbered Dáil term instead of explaining the unsupported universal/completeness condition | No answer query | Weak/unjustified clarification — temporal/capability interpretation |
| B10 | Two distinct John Murphy identities offered for disambiguation | Member resolution only | Correct clarification — identity ambiguity preserved |

No planner HTTP 400 was counted as an unsupported semantic request or a correct
refusal. Those are execution failures, not evidence about the requested
relationships or local coverage. The failed requests therefore remain
unscorable for factual support. The supported-capability denominator cannot be
established from this pass because no matching answer query ran for those cases.

## Verification and interpretation

Controlled acceptance tests cover the new date/month HouseTerm selection,
accepted OfficeHolding date/month/year overlap, latest-recorded Member term,
membership-date evaluation, list/count identity parity, and bounded-page failure
behavior. The repository suite passed **2,036 tests, 25 skipped, and 23
subtests**; ontology validation passed. The holdout's planner HTTP 400 failures
are an independent runtime limitation and were not retried or used to tune the
implementation.

The bounded architecture remains viable for the approved tranche: controlled
tests exercise the shared validated selector/evaluator and deterministic count
projection, with exact identities and fail-closed pagination. The holdout pass
does not establish unfamiliar-language generalisation until the configured
planner endpoint can complete structured requests. Adjacent cross-family,
ranking and universal-coverage questions remain outside this tranche.
