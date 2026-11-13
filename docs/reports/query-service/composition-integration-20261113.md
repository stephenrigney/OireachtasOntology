# OireachtasOntology NLQ — First End-to-End Composition Integration

## Outcome and workflow

An additive `/composition` page, linked from the ordinary question interface,
implements the attended K + R list slice. `/ask` admission/execution is unchanged.
Enter English → **Propose interpretation** → inspect both relationships, date
and answer form → **Confirm interpretation and execute**, or reject/edit/re-propose.
The server-held confirmed request is authoritative; confirmation makes no model
call. Names, both dated relationship witnesses and actual graph-backed RDF facts
are rendered; the full typed execution ledger is downloadable during its bounded
retention window. See the [user guide](../../guides/query-service.md#opt-in-confirmed-committee--constituency-composition).

## Provenance and repository hygiene

- Fetched base `origin/master`: `069b483e39b613c8958df11ba467d73c64d08653`.
- Continued the user-confirmed existing branch `nlq-composition-integration-slice`,
  seeded at `3168d19839d5bfe0e8efe9152372e0221c091990` (one commit above master).
- Kernel source: `e98296ef2d89a07810c3b0f3f801c99f76636ae7`.
- Live transport/evaluation source: `3a77fb2ebfce083c2645c88dabe6209b100423ba`.
- Historical full evidence remains on the experimental branch at those SHAs:
  [`composition-kernel-20261112`](https://github.com/stephenrigney/OireachtasOntology/tree/e98296ef2d89a07810c3b0f3f801c99f76636ae7/docs/reports/query-service/composition-kernel-20261112),
  [`composition-live-kr-20261112`](https://github.com/stephenrigney/OireachtasOntology/tree/3a77fb2ebfce083c2645c88dabe6209b100423ba/docs/reports/query-service/composition-live-kr-20261112),
  and the linked freeze evidence. No large raw capture trees were imported,
  branch history rewritten, merge performed, or experimental evidence changed.
- Frozen files remain byte-identical:
  `experimental_composition.py` SHA-256
  `0560acf2b813fdf04f237e09522dcc02b60d99700bdc66cef410948609dd5d06`;
  `tools/nlq_composition_live.py`
  `e57b97d60cc053e52ba9c7a15c468f584244fcfd22b04a495d00abc9b11ce1f8`.

Only the seeded implementation files were carried forward from the experimental
branch. New application modules, synthetic tests, a guide addition and this
concise report implement integration. No ontology, mapping, protected fixture,
ETL, published RDF or Fuseki configuration change was made. The integration
commit is the commit containing this report (SHA returned in the delivery).

## Implementation and safeguards

`composition_kernel.py` extracts the reusable typed R/P/K primitives, `bind` and
evidence-preserving `project`; the frozen experiment is not modified. One
authoritative structured request replaces the experiment's original/candidate
comparison. `asOf` is explicit, strictly validated, backend-controlled and held
per execution, not a changed global experiment date. Full-label named-resource
resolution shares the primitive owner/type/interval validation and plan budget.
K and R share only exact Member identity: no invented committee parliamentary
containment or cross-path term equality. Synthetic differently-termed paths
verify this independence.

`composition_workflow.py` reuses the strict Responses planner transport/parser.
The model proposes exact mentions only; independent whole-question bounded
wording and temporal checks reject residual conditions even when a willing test
model omits them. The UI explicitly says a proposal is not an independently
certified reading of English. Confirmation is not unattended NL admission.

`composition_routes.py` holds deep-copied requests under single-use random
tokens, bound to HttpOnly/SameSite-strict browser state, original question and
date. Extra/duplicate form fields, other sessions, cross-origin submissions,
expiry, replay and changed backend dates cannot execute. A new proposal attempt,
including failure, supersedes the old one; generation fencing rejects older
out-of-order model responses. Confirmation revalidates scope and dates, without
another model call. Stores have 128-entry ceilings and ten-minute expiry;
complete evidence additionally has a 32 MiB aggregate serialized ceiling, with
whole-artifact eviction rather than fact truncation.

`composition_transport.py` reuses the production client's configured HTTP(S)
`/query` URL, paired Basic credentials and client configuration, but decodes
lossless typed RDF directly, never formatted/capped debug cells. Queries go
unchanged; malformed/duplicate-key JSON, unsupported RDF bindings, non-200,
redirects, incorrect media types, timeout and >2 MiB responses fail closed.
Eight SELECTs include resolution, every page/completion probe and names; raw
rows are capped at 100 **per response**, and primitive/join witnesses at 100.
The operative HTTP timeout remains 15 seconds, not the frozen 20-second
counter-test ceiling. No K + R SPARQL template or combination-specific executor
was introduced. A successful empty list/count is not admitted.

Both `member.showAs` and `member.fullName` map to `foaf:name`: all recorded names
are retained and displayed together for the exact Member, without choosing a
preferred name or merging people. Source datatypes/languages/graphs remain in
downloaded evidence. Unicode matching normalizes canonical equivalents to NFC;
the existing IRI-target branch retains its frozen case-sensitive constituency
matching.

Independent review identified the name multiplicity, IRI matching, Unicode,
candidate visibility and retained-memory issues. All were addressed with focused
tests; the final read-only follow-up found no blocking correctness issue.

## Live browser evidence

Chromium exercised actual form navigation through the application, configured
Responses planner and read-only `http://localhost:3030/houses/query`.
Initial checks used `asOf=2026-11-12`; reviewed implementation checks used
`asOf=2026-11-13`, demonstrating no experiment-date pin. No source mutation or
bootstrap occurred. These constructed K + R questions are **not** mislabelled
recorded human questions or an unseen holdout.

**Interpretation:** all seven positive questions displayed a reviewable proposal
before any composition query. **Confirmed execution:** all seven then returned
the expected names with both source-backed witness paths and displayed date.

| Ordinary question / parameter variation | Recorded Member names | Raw rows per charged SELECT | Witness pairs |
|---|---|---|---:|
| Which members of the Committee on Public Accounts currently represent Kildare North? | Aidan Farrelly; Joe Neville | 65, 6, 15, 1, 5, 2 | 2 |
| Who currently represents Kildare North and serves on the Committee of Public Accounts? | Aidan Farrelly; Joe Neville | 65, 6, 15, 1, 5, 2 | 2 |
| Which TDs for Kildare North are members of the Committee on Public Accounts? | Aidan Farrelly; Joe Neville | 65, 6, 15, 1, 5, 2 | 2 |
| List the current members of the Committee on Public Accounts who represent Galway East. | Albert Dolan | 65, 6, 15, 1, 4, 1 | 1 |
| Which members of the Committee on Public Accounts currently represent Cork South-Central? | Séamus McGrath | 65, 6, 15, 1, 5, 1 | 1 |
| Which members of the Joint Committee on Health currently represent Roscommon-Galway? | Martin Daly | 65, 6, 14, 1, 3, 1 | 1 |
| Which members of the Committee on Budgetary Oversight currently represent Kildare North? | Joe Neville | 65, 4, 16, 1, 5, 1 | 1 |

All positives used six SELECTs: terms, K owner, K membership, R owner,
R membership, Member names; all offsets were zero with short-page completion.
Each returned pair retains five independently active intervals: K membership,
committee owner, its term, R membership, its term. For the established PAC case,
Aidan Farrelly and Joe Neville retain the historical live evaluation's exact
Member, K episode and R membership IRIs; K starts `2025-05-07T00:00:00`, R starts
`2024-11-29T00:00:00`, with no recorded ends. Dates are original typed endpoints,
not a fabricated assertion of permanent service. The actual Member-owner,
committees, constituencies and houses graph facts are available in the UI and
download. This integration verification is not a new independent raw-RDF oracle
or a source-completeness certification.

Additional real-browser live checks:

- Adding “and belong to Fine Gael” was refused before confirmation/execution;
  no easier K + R answer was substituted. Synthetic willing-model controls
  separately verify independent rejection when the proposal omits this clause.
- Joint Committee on Transport + Kildare North was interpreted and confirmed,
  then returned **no qualifying recorded evidence**, not a factual empty roster.
- Verbatim human Q1/Q17/Q2 from
  [user-question-regression.md](user-question-regression.md) exercised default
  `/ask`: Mary Lou McDonald; whole election-event request refusal; grounded
  Browne clarification including Noel C. Browne. Only Q1 is a factual answer;
  refusal/clarification are regression behaviour, not factual successes.

## Verification and reproduction

Focused tests cover whole-intent variations/extra conditions,
strict dates and inclusive boundaries, different K/R terms, names and name sets,
Unicode, frozen structured-output parity, incomplete/nonqualifying evidence,
ambiguity, raw/intermediate/page/request limits, transport errors, confirmation
tampering/replay/session/date/expiry/out-of-order state, evidence eviction,
responsive rendered witnesses, rejection and editing.

```sh
.venv/bin/python -m pytest -q tests/test_nlq_composition_integration.py \
  tests/test_nlq_composition_browser.py tests/test_nlq_explainer_browser.py
.venv/bin/python tests/validate.py
.venv/bin/python -m pytest tests
```

Install Playwright and its Chromium separately for real-browser checks; the
dependency lock was not changed. With normal planner/Fuseki environment already
configured, run live checks against the existing read-only dataset:

```sh
OIR_RUN_COMPOSITION_LIVE=1 OIR_NLQ_AS_OF_DATE=2026-11-13 \
  .venv/bin/python -m pytest -q -s tests/test_nlq_composition_browser.py -k live_
```

Reviewed live run: **12 passed, 11 deselected** (seven confirmed positive
composition examples, two safe negative composition cases, three default-path
human-question regressions). Ontology/HermiT validation: **passed, 2,586 triples**.
Repository suite: **2,520 passed, 38 skipped**. After collection, the final narrow
IRI-owner anchor tightening restored the frozen query text exactly; the final
focused run on that source passed **84 tests, 12 skipped**, including exact
K/R IRI-query parity, typed projection parity and real synthetic-data browser
coverage. The default query path did not change during this verification tail.
Skipped opt-in/environment checks are not counted as passes; the twelve live
checks above were run separately with their required environment enabled.
The original frozen replay suite requires the retained large experiment evidence
and was not imported/re-scored here; synthetic frozen-projection parity is not a
claim of repeating that historical 133-test campaign.

Local disposable logs: `/tmp/oireachtasontology/nlq-composition-integration/`
(`live-browser-reviewed.log`, `focused-reviewed.log`, `ontology.log`, `pytest-final.log`).
They are not durable raw evaluation captures or a substitute for the retained
experimental evidence; this report and executable tests retain the findings.

## Limitations and next human gate

This is one opt-in attended slice, not general English admission, a certified
roster, arbitrary composition, a source/run identity attestation, a transactional
snapshot, deployment or permission to change the default path. Full grounded
names and bounded present/current Member-list wording are required; unknown
aliases/acronyms, extra filters, counts, historical question dates and answer
fields fail closed. Date scope comes from the backend, not a browser date field.
Missing ends remain open-ended; missing required facts never become exclusion
criteria that produce an easier partial answer.

Use one worker for process-local state; restarts, expiry, eviction and worker
mismatch require a new question. TLS-terminating proxy origin/cookie handling,
rate limiting, distributed confirmation state and operational load hardening
remain outside this localhost experiment. Confirmation cannot cure semantic
omissions for unattended queries. Live tests are explicit opt-in checks, not
continuous availability promises.

**Recommended next gate:** human-review the interpretation/confirmation UX on
new ordinary parliamentary questions, including rejected and ambiguous cases,
and approve only the bounded opt-in slice for merge. Keep `/ask` unchanged;
require a separate decision for wider language coverage, combinations or
deployment. The integration branch is to be committed/pushed, not merged.
