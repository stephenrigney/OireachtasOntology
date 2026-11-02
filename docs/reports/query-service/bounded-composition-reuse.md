# Query Service — bounded composition reuse

## Outcome and boundaries

Implemented the approved post-Phase-2 architectural test on 2026-11-02.
Composable contract `2.18.0` adds bounded operators to
`member_relationship_composition`; it adds **no question family**. Query-schema,
ontology, RDF, ETL, source captures, identity/graph ownership and publication are
unchanged. All live operations below were read-only against the already-loaded
loopback development dataset, at reference date **2026-11-02**; no reload or
full-corpus acceptance replay was performed.

## Reuse and safeguards

- **Identity sets:** independently resolve two to four explicit constituency
  mentions within the same selected term; compile one `VALUES` identity set.
  One shared temporal evaluator deduplicates Members by IRI and retains each
  representation/party episode. Current service checks both owned intervals
  at the reference date; House-owned dates select the term.
- **Independent paths/shared resources:** the same typed-edge compiler renders
  separate Member-owned graph blocks for anchor and answer paths. Both bind
  the same constituency **and term IRIs**, with distinct Member identities.
- **Common intersection:** the existing interval parser/overlap evaluator serves
  both the original two-interval checks and four-interval office composition.
  All starts are required; absent ends are open-ended. Missing, malformed or
  conflicting owned ranges fail closed. Office mapping/evidence compilation is
  extracted from, and shared with, the existing dated office implementation.
  Resolve affiliation from all reviewed parties in relevant exact terms, not
  just answer candidates or irrelevant historical terms.
- **Capability access:** grounded month/year parameters select the existing
  OfficeHolding plan builder, compiler and executor. June means June 1–30, not
  an invented date point. No new office reconciliation or roster authority.
- **Intent boundary:** shared compound routing keeps clauses out of singular
  entity recognizers. Unsupported election/representation aggregations reject
  the whole request before resolution. Draft normalization checks exact mentions
  and conservatively rejects unconsumed wording; the existing final graph
  validator requires all edges, operators and evidence projections. Read-only
  safety, reviewed mappings, local-only IRIs, ambiguity and 100-row evidence caps
  remain enforced. No model SPARQL or new unrestricted graph engine.

New recognition is a shared compound-intent routing guard and a generic implicit
geographic-set clarification probe, not parallel Ahern/Galway recognizers.
The latter can suggest source-grounded occurrences by label fragment but cannot
select a set. An additive operator-input normalizer delegates graph meaning to
the existing final validator. The original temporal compiler was refactored into
one typed-edge renderer, not copied into Q15/Q3 templates.

## Verification

- Focused controlled named-graph and integrated `/ask` tests cover the union of
  existing single-constituency results, exact Member deduplication, independent
  paths, same-label/different-identity exclusion, inclusive/open intervals,
  four-way intersection, missing/unaccepted office evidence, per-role missing
  starts, conflicting/malformed dates, identity ambiguity, omitted operators,
  unsupported clauses and evidence caps.
- `tests/validate.py`: passed, including HermiT (2,586 ontology triples).
- `.venv/bin/python -m pytest tests -q --tb=short`: **2,006 passed,
  25 skipped; 23 subtests passed**. A final focused tail after the additional
  office-pattern/type-registry drift guard passed **137 tests**, including
  **36 bounded-operator tests**. Metadata assertions were advanced to the
  additive contract version; existing semantic acceptance was not weakened.

### Live primary checks

Used the configured `gpt-6-luna` Responses-compatible model at the repository's
`opencode.ai` endpoint, one call per request, no repair/retry. Credentials were
loaded process-locally from `.env.local` and were not logged. Fuseki readiness
was `ready`. Requests used the integrated `POST /ask` Phase 2 route.

| Control | Result |
|---|---|
| Q15: Fine Gael TDs in Galway East and Galway West | Hildegarde Naughton, Peter Roche, Seán Kyne; one identity-set query. Independent executions of the existing single-constituency path returned Roche and Naughton/Kyne respectively; their exact Member-IRI union equals Q15. |
| Q3: other Fianna Fáil TDs sharing Bertie Ahern's constituency while Taoiseach | Cyprian Brady; shared 30th-Dáil Dublin Central identity; common intersection **2007-06-14–2008-05-07**. UI explicitly reports partial accepted-evidence coverage, not a complete historical roster. |
| Who was Taoiseach during June 1994? | Albert Reynolds; full June 1–30 window; accepted holding 1992-12-14–1994-12-15, without asserting complete 1994 coverage. |
| “the two Galway constituencies” | Clarification, not a guessed set: grounded Galway East, Galway West and Roscommon-Galway occurrences. No answer query. |
| Q15 plus first-election dates | Whole request unsupported; no entity lookup or reduced answer query. |

The first live Q3 run exposed premature party resolution in terms outside the
accepted holding interval. The shared temporal path was corrected to establish
relevant terms before term-scoped party resolution. Subsequent real-model `/ask`
acceptance returned Brady; its displayed SPARQL equals deterministic compilation.
No RDF/source workaround was used.

### Fresh untuned live holdout

These five questions were chosen after primary implementation, run once, and
not used to tune or retry the implementation. This is a small generalisation
probe, not a benchmark-wide quality claim.

| Fresh question | Measured outcome |
|---|---|
| Please list the current Fianna Fáil Deputies representing either Cork North-Central or Cork South-Central. | Answer: Micheál Martin, Pádraig O'Sullivan, Séamus McGrath. |
| Which Fine Gael TDs represented either Mayo or Sligo-Leitrim during the 33rd Dáil? | Answer: Alan Dillon, Frankie Feighan, Michael Ring. |
| Which other Fine Gael TDs shared the same constituency with Enda Kenny while he held the office of Taoiseach? | **Planner omission / validation failure:** proposed plan lacked the independent anchor operator. No simplified answer executed. |
| Name the recorded Taoiseach officeholders for November 1993. | Answer: Albert Reynolds. |
| Which Fianna Fáil TDs in Cork North-Central or Cork South-Central were first elected before 1997? | Whole-intent unsupported, as required; no answer query. |

**4/5 expected outcomes; 3/4 supported requests answered.** All successful
holdout plans validated and displayed exactly their deterministic compiler output.
A separate fixed-plan control for the Enda Kenny request successfully reused the
same compiler/evaluator and returned Michael Ring from accepted evidence; it is
not a retry or a rescored holdout success. This isolates semantic-selection
variability from operator capability and demonstrates parameterised identity reuse.

## Limits and architectural decision

The architecture remains viable **for these bounded reviewed compositions**:
shared compilation and temporal evaluation were achieved without bespoke query
families or weakened identity/authority safeguards. This does not demonstrate
arbitrary compositional NLQ. The fresh anchor-selection miss is a real residual
planner-quality limitation, not source absence or an execution success.

Conservative lexical intent checks can reject legitimate unseen wording. Sets
are limited to two–four explicit constituency alternatives; office composition
supports one named anchor and a named-party Member answer, not combinations of
all operators, arbitrary filters or aggregation. Evidence caps fail closed.
Missing accepted OfficeHolding episodes, including Ahern's earlier Taoiseach
service, remain coverage gaps; positive matches do not certify complete rosters.
All specification exclusions remain deferred. No new semantic/architecture
decision is required for this implementation; any broadening beyond this slice
requires separate human review, not automatic expansion from these results.
