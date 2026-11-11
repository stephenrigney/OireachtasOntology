# Query explainer: implemented evidence mapping

The presentation contract is unchanged. `poc/nlq/explainer.py` is a read-only
view of the existing composable v2 envelope. It performs no resolution,
validation, compilation, admission or answer computation. `app.py` supplies the
actual plan only after its existing `validate_plan` check succeeds; capped
debug JSON is never reparsed as semantic evidence.

## Evidence to presentation

| Existing evidence | Presentation |
| --- | --- |
| `referents.*.type`, `answer.referent`, `answer.kind` | Answer target and list/count/boolean/value shape. |
| `referents.*.mention`, `label`, `selector` | Named entities and exact numbered/current/previous/latest-recorded term, Bill number/year, date or full-month selection. A selector is not a claim that an identity was resolved. |
| `resolution`, `iri`, `candidates`, `matches` | Resolution state; only an actual `iri` with `resolved` supports “Matched to an ontology identity”. Sets and ambiguous identities are not presented as one selected identity. IDs, candidates and match sets remain in technical JSON. |
| `relations[*].fact/from/to` | Shared, reviewed plain-language edge descriptions. Shared referents mean exact identity joins, not equal labels. The legacy Bill-process fact name does **not** mean graph co-containment: it describes the actual BillDelivery path. Memorandum links are optional display evidence. |
| `constraints[*].referent/field/operator/value` | Inclusive overlap, common intersection, date containment, exact identity exclusions, Published-activity calendar year, legislative year, known-status exclusions and coverage requirements. Unknown conditions remain visible as untranslated limitations, never silently described as unconstrained. |
| `family` plus typed selectors and shared paths | Only closed, reviewed implications: party composition in a current term requires both independent intervals at `asOf`; cross-House current-term membership is not simultaneous service; current-Seanad/prior-Dáil has finite-endpoint strict chronology; current representation tests membership's own interval. Independent anchor/answer paths sharing exact constituency and term resources exclude the anchor by Member identity; the unconstrained shared-constituency projection is term-wide, not simultaneous service. Term-wide representation is not a date-point request. |
| `interpretation.policy/question/date` | Existing validated present-time default evidence. Where legacy paths omit this object, the existing `current_scope_explanation` formatter supplies its narrowly scoped explanation; there is no new intent inference or policy. An unused top-level `asOf` alone never implies an active-date filter or a default. |
| `answer.distinctBy`, `display`, `details`, `preserveEvidence`, `preserveGaps` | Identity distinctness, requested display fields and supporting-record request, **not** a promise that execution returned those fields. |
| `answer.kind == family_result`, `answer.projection` or `family` | Closed family-specific result descriptions reviewed against Stage A/B/C builders and executors. This shape cannot truthfully be treated as a generic entity list. Unknown projections use a visible conservative fallback. |
| Explicit `execution_attempted` | Availability of Executed. SPARQL, diagnostics, performance request counts and validation are not substitutes for this flag. |
| Result kind, boolean, rows; accepted count projection | Actual boolean, returned row total, or returned count value. Rows are not equated with distinct people. Zero rows/count/false are not certified historical negatives. |
| Existing error/status, result notice, debug payload | Attempted failure, qualified results, source-coverage limitations, and expandable original diagnostics. Only a result without an error supports the successful-completion wording. Execution success never certifies answer completeness. Booleans/counts can be application projections of endpoint evidence, so their summary does not attribute them directly to the database. |

## Limits and retained technical evidence

- This is Option A: plan components, never an observed compiler timeline.
- Some successful office-evidence paths retain SPARQL/results but **no plan**.
  Their structured interpretation/plan components are unavailable; the UI says
  so, while retaining the original formatter notes, actual rows and material
  incomplete-career/tenure qualifications. No replacement plan is manufactured.
- Some validated plans retain unresolved mentions even after execution. The UI
  reports the plan's evidence, not identities inferred from result labels.
- Structural validation and accepted identity selection are distinct; an
  ambiguous plan cannot receive the successful “Interpretation validated” badge.
- `family_result` envelopes can omit selectors used internally by their closed
  executor. The UI describes only the reviewed family projection and supplied
  selectors; it does not invent a resolved term, interval or filter value.
- Plans do not provide a general compiler trace, provenance trail or source
  completeness certificate. No such trail or certificate is constructed.
- Ordering, limits or future unknown settings are not inferred from the
  generated SPARQL. Unknown plan/result settings produce a visible warning
  and remain inspectable in technical JSON.
- Existing family formatter notes remain in a collapsed, labelled disclosure.
  They are not the default explanation and are explicitly not compiler tracing.
  Raw JSON, generated SPARQL and endpoint/debug data remain accessible in
  native keyboard-operable disclosures; Performance stays collapsed.

`tests/test_nlq_explainer.py` checks emitted plans and `/ask` responses using the
existing RDF-backed historical/current composition fixtures, Bill ETL example,
partial sponsorship evidence and closed family builders, alongside controlled
execution outcomes and missing/future-field presentation robustness tests.
Source fixtures and semantic/golden acceptance are unchanged.

## Browser verification (2026-11-11)

The optional `tests/test_nlq_explainer_browser.py` checks passed in headless
Chromium at 1240, 390 and 320 CSS pixels. They exercise the real rendered
`/ask` response with RDF-backed test evidence, not a separate mock dashboard:
arrow keys, Home/End, focus/selected-panel synchronisation, skipping disabled
Executed, Tab-to-disclosure and Enter/Space operation, initially collapsed
technical/Performance disclosures, and no document overflow with technical
content open. Desktop and mobile screenshots of all three stages were also
inspected for readability. The existing off-white/white/gold styling remains.

These checks do not exercise a live LLM/Fuseki service, other browser engines,
or a physical screen reader. Native `details`/`summary` semantics and the
existing tab ARIA conventions are retained; no claim of a complete
accessibility audit is made.
