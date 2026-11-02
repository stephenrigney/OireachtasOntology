# Query Service follow-up — Interpretation and clarification contract

## Fresh holdout (frozen before execution)

These six questions were selected after implementation and before their first
model execution. They are not recognizer examples, fixtures or tuning inputs.
Do not repair/retry failures or tune implementation against this set.

| Question | Expected capability/outcome |
| --- | --- |
| Could you identify the Deputy whose surname is O'Rourke? | Grounded, Dáil-qualified name lookup; preserve alternatives if multiple identities match. |
| List the political parties recorded for the 18th Dáil. | Existing exact-term party listing, without group warnings. |
| Who represents Wicklow at present? | Existing date-relative constituency representation with current membership evidence. |
| Give me Albert Reynolds's recorded constituencies over his career. | Existing career representation, preserving term-scoped occurrences. |
| When was Garret FitzGerald first elected as a TD? | Unsupported election-event capability; no membership-start proxy. |
| Who are the Fine Gael TDs representing Mayo? | Existing dated party/representation graph with the approved query-date default and both intervals contemporaneous. |

## Implementation and boundary

Implemented on `query-service-interpretation-clarification`, without merging.
Composable contract `2.17.0` records the interpretation evidence and the party-only
answer-scope extension. The strict draft schema, final plan schema and runtime
validators agree. Query-schema/RDF/ETL/publication contracts are unchanged.

- One shared, narrow policy admits a query-date default only for grounded,
  present-tense constituency representation. Its original question, policy ID and
  date are recorded in the plan and revalidated. Future/conditional, historical,
  election and wrong-chamber requests cannot acquire this default.
- Existing House-owned current-term selection and dated representation/party
  evaluation are reused. Both intervals must independently contain the reference
  date. Numbered historical terms keep their exact identities and overlap
  semantics; unsupported additional calendar-date filters are refused, not
  silently defaulted.
- Existing semantic capability selection now exposes Stage A Member lookup and
  Stage C numbered-term party listing. It preserves the requested chamber and
  party/group scope. Party-only results do not warn about unrequested groups.
- The candidate UI uses an opaque, single-use, ten-minute token and an index,
  never a client-supplied IRI or plan. At most 128 pending choices are retained.
  Continuation is bound to the original question/date and rechecks identities and
  service evidence through the same validated read-only execution boundary. It
  does not call the model or add conversational memory.
- Exact recorded `agents:pId` spelling can ground a name alias (user whitespace
  removed only). This rule is reused by full-name Member lookup as well as the
  existing exact Member resolver; no nickname table or identity merge was added.
- Shared interaction categories distinguish answers, clarification, unresolved
  identity, unsupported capability, missing/unaccepted evidence, validation and
  execution failure. A thin read-only execution-error boundary prevents transport
  and client-parse failures being mistaken for absent evidence. Candidate displays and echoed
  interpretations are not answer outcomes.
- A generic office-evidence boundary reuses exact Member/NamedOffice resolution.
  Absent accepted office identity cannot establish tenure. Registry presence alone
  does not add a complete-career tenure operation. Election requests remain
  unsupported; validators reject substituting entry/representation for election.

No question-specific recognizer, new relation composition, SPARQL answer compiler,
agent harness, repair loop or data ingestion was introduced. The pre-existing
partial-token Stage A matcher and exact-label resolver remain different operations;
source-identifier alias acceptance now calls the same exact resolver rather than
duplicating its rule. The office adapter is an evidence/capability diagnostic,
not an additional tenure compiler.

## Live integrated acceptance — 2026-11-02

Real Responses-compatible planner (`gpt-6-luna`,
`https://opencode.ai/inference/openai/v1`, 45-second timeout, 2,000 output tokens),
real existing local Fuseki `http://localhost:3030/houses/query`, reference date
`2026-11-02`. Credentials were loaded from local configuration into the process
only. No source fetch, bootstrap, graph load or publication was performed.
Read-only readiness was ready. Each request used the normal Phase 2 `POST /ask`
path; no retries, answer-query overrides or model-authored SPARQL were used.

| Request | Observed result |
| --- | --- |
| Which Sinn Féin TDs represent Dublin Central? | Answer: Mary Lou McDonald, exact current term selected from House dates; both source intervals contain 2026-11-02. Inferred policy/date present in validated plan and temporal qualification visible. |
| Which Sinn Féin TDs represented Dublin Central during the 33rd Dáil? | Historical answer: Mary Lou McDonald, separate 2020–2024 representation/affiliation evidence; no current default. |
| Find a Deputy called Browne | Clarification: ten distinct Dáil-qualified identities, including two John Brownes and two Patrick Brownes, each with source IRI and service context; no assumed Noel answer. |
| Browne candidate choice 0 | Answer: selected James Browne and source identity. Original lookup resumed; no second planner call. |
| What were the parties during the 12th Dáil? | Six recorded parties: Clann na Poblachta, Clann na Talmhan, Fianna Fáil, Fine Gael, Labour Party, National Labour Party. No group warning. |
| What constituencies did Jack Lynch represent? | Nine term-scoped occurrences, 13th–21st Dáil, for `John-Lynch.D.1948-02-18` only: Cork Borough, Cork City North-West and Cork City. The source graph actually contains `pId "JackLynch"`; the distinct `John-Lynch.D.1951-06-13` is not merged. |
| How long was Stephen Donnelly Minister for Health? | Missing/unaccepted evidence: no accepted local NamedOffice identity for Minister for Health. Unreviewed observations are not used to fabricate tenure. |
| When was Jack Lynch first elected to the Dáil? | Unsupported election-event capability; no membership-start proxy or answer query. |

The rendered HTML candidate form was exercised through `/ask` with real Fuseki,
including form token extraction and choice submission. Controlled fixture tests
also exercise the form and tampering/replay/expiry/date/source-change rejection.
A desktop-browser check was attempted but no browser was connected; there is no
claim of visual/accessibility or cross-browser testing.

## Untuned holdout results

All six frozen questions above reached the expected outcome on their first run:

| Case (in frozen order) | Observation |
| --- | --- |
| O'Rourke | Four Dáil-qualified alternatives: Daniel, Darren, Frank and Mary O'Rourke. |
| 18th Dáil | Five recorded party identities, no group warning. |
| Wicklow | Four date-qualified recorded representatives: Edward Timmins, Jennifer Whitmore, John Brady, Simon Harris. |
| Albert Reynolds | Eight distinct term-scoped constituency occurrences. |
| Garret FitzGerald election | Unsupported election-event capability; no inferred date. |
| Fine Gael / Mayo | Alan Dillon and Keira Keogh, both representation/party intervals contemporaneous at 2026-11-02. |

Result: **6/6 expected capability/outcome categories**. This is small positive
generalisation evidence, not a statistical accuracy estimate. No holdout failure
was used to change prompts, recognizers or compilers; subsequent review changes
addressed deterministic safety/schema gaps, not these holdout answers.

## Verification and review

- Focused slice: `.venv/bin/python -m pytest tests/test_nlq_interpretation_clarification.py -q`
  — **40 passed**, including default scoping, uncertain dates, schema/runtime
  agreement, plural/chamber scope, source aliases/duplicate identities, election
  substitution refusal, continuation tampering/replay/expiry/date/source changes,
  identity caps and endpoint-failure classification.
- Combined focused Stage A, semantic dispatch, query-contract and prior
  question-failure regressions — **166 passed**.
- Final broader regression: `.venv/bin/python -m pytest tests/test_nlq* -q`
  — **839 passed, 1 skipped** (298.54 seconds). The skipped test is the opt-in
  disposable capture-backed Fuseki replay, deliberately not enabled for this
  bounded tranche. Real existing-dataset `/ask` checks above ran separately.
  Dependency deprecation warnings and intentionally malformed-literal fixture
  warnings remain; there were no final failures.
- Latest semantic-dispatch and query-contract checks — **23 passed**.
- `compileall` and `git diff --check` passed. Final live `/ask` smoke repeated
  Browne clarification → selected James Browne/source identity and the defaulted
  Dublin Central/Mary Lou McDonald answer successfully after the safety changes.

Independent review identified future/conditional and plural/wrong-chamber policy
edges, source-alias resolver drift, schema/documentation sync and failure-category
gaps. Those were corrected with focused regressions, without expanding query
composition or weakening an acceptance safeguard. The live first-election and
source-backed alias evidence above also close the review's initially unmeasured
acceptance concerns; no bespoke election recognizer was added.

## Remaining limitations and architectural decision

- Model interpretation remains variable; one call, no autonomous repair/retry.
- Interactive continuation is limited to the bounded Member-name lookup. Other
  ambiguity requires a more precise question. Tokens are process-local; restart
  or another worker requires restarting the question, not general session state.
- Alias support requires an exact recorded source identifier or label; it does
  not promise arbitrary nickname, spelling, diacritic or Unicode-normalization
  discovery. Missing evidence and duplicate identities fail closed.
- No new election-event, complete-career office-tenure, date-window or unsupported
  relationship capability was added. Current and historical results remain
  qualified as recorded local evidence, not complete rosters/history.
- No full-corpus benchmark or production acceptance replay was performed. The
  source coverage and private-beta deployment boundaries remain unchanged.
- Legacy evidence-result shape checks and non-identity completeness caps can
  still return an evidence-unavailable category. The shared transport/parse
  failure boundary and identity-resolution cap checks do not claim a complete
  retrospective reclassification of every legacy executor diagnostic. First-
  election refusal wording remains model-authored under the strict unsupported
  proposal contract; deterministic guards prohibit proxy service-entry answers.

**Architecture remains viable without redesign for this bounded slice.** The
specified cases and fresh entity/term/paraphrase variations reused the existing
planner, resolver, validators, compilers and temporal evaluator. No further
bespoke composition or substantial orchestration was needed. Broader correctness
or capability expansion still needs its own review; this evidence does not claim
arbitrary natural-language coverage. Keep the branch unmerged for ChatGPT review.
