# OireachtasOntology NLQ — Stage 3: Controlled Generalisation Experiments

## 1. Baseline and experimental environment

Evidence labels: **Observed** means directly inspected source, retained evidence
or this experiment's execution (qualified below); **Inferred** means an
evidence-supported reconstruction; **Hypothesis** is untested; **Unknown** means
not established. Historical results are not counted as new executions.

### Scope and invariants

The outcome sought is a bounded diagnosis of generalisation, not improvement.
No implementation, semantic contract, expected answer, source fixture or
production configuration is changed. Only read-only SPARQL query requests are
made to the existing local dataset. No launcher, bootstrap, publication, source
acquisition, dependency installation or data reload is used. Stage 4 is outside
scope. Missing environment, traceability or expected semantics stops the
affected inference rather than becoming a compiler failure.

### Baseline

**Observed—execution:** repository `stephenrigney/OireachtasOntology`, branch
`master`, HEAD `563a385173d312d33d22ca7868524714487967aa`, exactly the Stage 1/2
reference. Initially no tracked changes; the two pre-existing untracked files
were the authoritative Stage 1/2 reports. No fetch was performed. Their hashes,
the lockfile hash and reviewed office-decision hash are in
[`baseline.json`](nlq-stage-3-20261110/baseline.json).

**Observed—execution:** Python 3.12.14; RDFLib 7.6.0, FastAPI 0.142.2, HTTPX
0.28.1, Starlette 1.7.0, Jinja2 3.1.6, multipart 0.0.32, dotenv 1.2.4, Uvicorn
0.54.0. `pytest`, `jsonschema` and the OpenAI Python package are absent.
The application uses HTTPX directly for Responses requests; the missing OpenAI
package is not an application blocker. The focused pytest attempt exits 1,
`No module named pytest`; no acceptance tests ran. A fresh real application
instance returns HTTP 200 and readiness `ready`. TestClient emits a Starlette
HTTPX-deprecation warning, not an application failure.

**Observed—execution:** this experiment imports the exact current checkout into
a new process and exercises FastAPI's real **POST `/ask`**, omitting `mode` so its
default `phase2`/composable-v2 applies. It does not rely on the serving revision
of a pre-existing Uvicorn process. Configuration is inherited, without printing
secrets, from same-checkout development service PID 3489018. This process alone
pins `OIR_NLQ_AS_OF_DATE=2026-11-10`. Model: `gpt-6-luna`; Responses-compatible
provider base: `https://opencode.ai/inference/openai/v1`; ordinary generator
timeout 45 seconds and maximum output 2,000 tokens. Provider-selected backend
revision/seed and sampling defaults are **Unknown**. Local query endpoint:
`http://localhost:3030/houses/query`. No other-worktree service is used.

### Dataset identity and reusable evidence

**Observed—execution:** initial inventory contains **7,982 named graphs and
1,119,860 triples**. All readiness families are present. Full graph IRIs/counts
are retained in `graph_inventory-before.json`. A bounded catalogue/provenance
graph query returns no rows. Therefore exact loaded capture/run provenance is
**Unknown**; graph counts are not a cryptographic dataset-content identity.
The independent question-relevant RDF bindings are retained in
`oracle-before.json`, including source graphs, resource identities and typed
literal metadata; their hash is frozen before requests. Conclusions are about
this observed local RDF, not a completeness-certified real-world dataset or a
proven replay of the development capture manifest.

**Observed—static/historical:** genuine human Question/Expected/Actual records
remain available in `/var/home/stephen/Documents/Scratch/{question-report.md,
questions-2.md,questions-3.md}`. The campaign's Q1, Q3 and Q9 are reused verbatim.
Existing human-response HTML, Group A/B and sponsorship investigations remain
available and are not overwritten. Historical answers guide selection, not
current scoring. The committed development API/source manifests identify
genuine-data capture selections, but do not prove those exact captures are
loaded now. Existing local RDF suffices for independent positive-evidence
oracles without substituting synthetic fixtures or reloading captures.

### Trace boundary

**Observed—execution/design:** reuse of the existing
`/tmp/oireachtasontology/tranche-2/live.py` transparent `RecordingGenerator`
and final `record_execute` pattern records the real model output and
`PlanOutcome`, alongside complete rendered HTML and template-context fields.
No fixed drafts, manual repairs, alternate compiler, query substitution or
permanent instrumentation is introduced. Scratch harnesses reside in
`/tmp/oireachtasontology/nlq-stage3-20261110/`; durable evidence resides in the
new sibling [`nlq-stage-3-20261110/`](nlq-stage-3-20261110/) directory.

**Unknown:** exact full branch timeline and subsidiary resolution/evidence
SPARQL, except where already exposed in existing debug output. One
`PlanOutcome.sparql` field is not a complete query log; UI execution flags are
derived state. No claim of “zero RDF queries” follows from “no answer”. Routing
claims below use observed model-call counts, draft selections, final family and
plans; finer branch reconstructions are explicitly inferred from source.
Existing debug strings can truncate at 50,000 characters. Independent oracle
queries use direct read-only HTTPX transport to retain uncapped RDF JSON.

## 2. Capability and question selection

The fixed sample contains **five families, 24 distinct questions, 30 scheduled
requests**. C1, D8 and E2 each have three total observations. The matrix and
expected RDF evidence were frozen before the first `/ask` request, in
[`questions.json`](nlq-stage-3-20261110/questions.json) and
[`freeze.json`](nlq-stage-3-20261110/freeze.json). No adaptive campaign expansion
or answer-based oracle adjustment is permitted.

| Family | Selection rationale | What this family cannot establish |
|---|---|---|
| A: recorded Dáil seats | Straightforward deterministic Stage C operation; familiar and explicit-seat phrasings test reachability beyond one recognition pattern | Member cardinality, election totals or a general aggregate compiler |
| B: Dáil parties/groups | Human Q3 plus deterministic groups/parties form and semantic paraphrase; exact term substitution and narrower party-only projection | Arbitrary party filters or complete historical group evidence |
| C: current officeholder→constituency | Model-dependent closed chain; Finance positive control and historically evidence-blocked Tánaiste; explicit unsupported historical control | General historical office/representation joins, counts or party filtering |
| D: dated party/constituency composition | Human Q1 and complex Q9; language, constituency identity, historical scope, filter removal, supported count and finite OR | Arbitrary composition; Q9 is a separate complex reference, not a minimal pair with Q1 |
| E: Member-sponsored Bills | Separate graph implementation versus advertised-but-unadapted generic selector; list paraphrase, entity substitution, unsupported unqualified count and evidence-limited Published-year count | Generic Bill analytics, voting or legislativeYear-as-publication inference |

**Observed—static selection boundary:** the unresolved contract/code disagreement
about constituency-free current-Dáil party counts (Stage 2 §5) is excluded.
Party-filtered constituency counts are also not forced into this sample:
`composable_plan.py:831–834` restricts temporal party counts. D5 instead compares
the supported unfiltered active-constituency count with D6's list.
For E, a count-only variation is unsupported; the supported count requires a
Published-year restriction. No artificial claim of a projection-only pair is
made. Boolean projections are not supported for these selected closed lists;
unsupported dimensions are boundaries, not factual failures.

**Inferred—sampling limit:** these are deliberately selected diagnostic cases,
not a random sample, independent holdout or capability census. Some paraphrases
and entities occurred in prior evaluations. Sample frequencies cannot estimate
an overall NLQ/compiler success rate or unseen-question reliability.

## 3. Complete question matrix and independent expectations

The exact questions, provenance, controlled comparisons, supported status and
expected meaning are in `questions.json` (all 24 rows). Expected identity sets,
intervals and source paths are in `expected-answers.json`; the separate
handwritten evidence queries and unmodified RDF responses are in
`oracle-before.json`. Expected answers were established without application
compiler output. Results and classifications follow below.

Provenance: **H** = verbatim genuine human record; **R** = existing authored
evaluation/template, not a human record; **C** = constructed diagnostic. Every
row below links to its first-run raw response; full proposals, validation
diagnostics, plans, generated SPARQL, results and presentation fields are also
in `responses.jsonl`, keyed by `id` and `run`.

| ID / provenance | Exact question | Controlled meaning / independent expectation | Observed result |
|---|---|---|---|
| [A1](nlq-stage-3-20261110/A1-r1.html) R/C | How many members were in the 34th Dáil? | Approved seats reference, not people-count: 174 | 174 seats; no model call |
| [A2](nlq-stage-3-20261110/A2-r1.html) C | How many seats did the 34th Dáil have? | Intended same recorded-seat operation as A1: 174 | Model declares seats unsupported; no selection/answer |
| [A3](nlq-stage-3-20261110/A3-r1.html) R/C | How many members were in the 33rd Dáil? | Change exact term: 160 seats | 160; no model call |
| [B1](nlq-stage-3-20261110/B1-r1.html) R/C | What are the groups and parties in the 12th Dáil? | Six term-12 parties; group evidence unavailable | Six exact party identities, explicit missing-group qualification; no model |
| [B2](nlq-stage-3-20261110/B2-r1.html) C | Which parties and parliamentary groups were recorded in the 12th Dáil? | Linguistic equivalent of B1 | Same identities/qualification; model selects correct capability |
| [B3](nlq-stage-3-20261110/B3-r1.html) H/Q3 | What were the parties during the 12th Dáil? | Restrict projection to parties; same six identities | Correct parties; `includeGroups=false`, no irrelevant group warning |
| [B4](nlq-stage-3-20261110/B4-r1.html) C | What were the parties during the 13th Dáil? | Substitute term 13; six distinct term-13 identities | Correct identities, not reused term-12 IRIs |
| [C1](nlq-stage-3-20261110/C1-r1.html) R | What constituency does the Minister for Finance represent? | Exact current holding→Simon Harris→active Wicklow/Dáil 34 | Correct recorded chain; three identical answer projections |
| [C2](nlq-stage-3-20261110/C2-r1.html) C | Which constituency is represented by the current Minister for Finance? | Linguistic equivalent of C1 | Correct capability proposal rejected by local request validation |
| [C3](nlq-stage-3-20261110/C3-r1.html) R | What constituency does the Tánaiste represent? | Change office; no accepted current holding in observed evidence | Selected; source-evidence nonanswer, no substituted holder/constituency |
| [C4](nlq-stage-3-20261110/C4-r1.html) C | What constituency did the Minister for Finance represent in the 33rd Dáil? | Historical extension unsupported by current-only chain | Controlled unsupported response; not a factual failure |
| [D1](nlq-stage-3-20261110/D1-r1.html) H/Q1 | Who are the Sinn Féin TDs for Dublin Central? | Present default; Mary Lou McDonald, both intervals active | Correct identity and independent source intervals |
| [D2](nlq-stage-3-20261110/D2-r1.html) C | Which Sinn Féin Deputies currently represent Dublin Central? | Equivalent explicit current wording | Same Member and temporal selection |
| [D3](nlq-stage-3-20261110/D3-r1.html) C | Who are the Sinn Féin TDs for Dublin West? | Substitute constituency; Paul Donnelly | Correct exact Member/constituency/party paths |
| [D4](nlq-stage-3-20261110/D4-r1.html) C | Who were the Sinn Féin TDs for Dublin Central in the 33rd Dáil? | Historical membership/party overlap, not current point; Mary Lou McDonald | Correct term-33 paths and 2020–2024 intervals |
| [D5](nlq-stage-3-20261110/D5-r1.html) C | How many TDs currently represent Dublin Central? | Count projection of D6's active selection: 4 | 4 distinct Members; model route |
| [D6](nlq-stage-3-20261110/D6-r1.html) C | Who are the TDs for Dublin Central? | Remove D1's party restriction; four active Members | Daniel Ennis, Gary Gannon, Marie Sherlock, Mary Lou McDonald; no model |
| [D7](nlq-stage-3-20261110/D7-r1.html) C | Who are the Sinn Féin TDs for Dublin Central and Dublin West? | Add explicit constituency OR; retain current party/membership checks | Mary Lou McDonald and Paul Donnelly, exact identity union |
| [D8](nlq-stage-3-20261110/D8-r1.html) H/Q9 | Who were the other Fianna Fáil TDs in the same constituency as Bertie Ahern while he was Taoiseach? | Separate complex reference: Cyprian Brady; four-way common interval 2007-06-14–2008-05-07; term 30; partial accepted coverage | Expected Member/interval, but contradictory term `/25` in displayed evidence alongside `/30`; repeated identically |
| [E1](nlq-stage-3-20261110/E1-r1.html) R | Which Bills did Malcolm Byrne sponsor? | Distinct local Bill set via explicit delivery/process/Participation: 20 | Exact observed 20-identity/title match; no model |
| [E2](nlq-stage-3-20261110/E2-r1.html) R | Please list the Bills sponsored by Malcolm Byrne. | Linguistic equivalent of E1; graph versus generic-selector probe | Model chooses working graph family; same 20 Bills in all three runs |
| [E3](nlq-stage-3-20261110/E3-r1.html) C | Which Bills did Ivana Bacik sponsor? | Substitute Member: 40 distinct observed Bill identities | Exact observed 40-identity/title match; no model |
| [E4](nlq-stage-3-20261110/E4-r1.html) C | How many Bills did Malcolm Byrne sponsor? | Count-only change unsupported; reviewed count requires Published year | Controlled unsupported response |
| [E5](nlq-stage-3-20261110/E5-r1.html) R | How many Bills did Malcolm Byrne sponsor that were published in 2025? | Add required Published-year restriction; supported but dates unavailable | Validated count selection; evidence failure, not zero; no model |

**Observed—independent RDF:** the six B-party labels are Clann na Poblachta,
Clann na Talmhan, Fianna Fáil, Fine Gael, Labour Party and National Labour Party.
Term-12 and term-13 IRIs are different despite identical labels. D6's four
active identities exclude the recorded ended Paschal Donohoe membership; thus
D5=4 is not the term-wide five-Member answer. E's complete observed identity and
title lists are in `expected-answers.json`, not abbreviated into an inferred
count from output rows.

### Independent expectation review and stopped facets

**Observed—independent review:** a separate context reviewed the frozen oracle
against contracts without inspecting responses. Its retained findings are in
[`independent-oracle-review.md`](nlq-stage-3-20261110/independent-oracle-review.md).
No wrong expected identity or numeric answer was demonstrated, but:

- The sponsorship oracle does not query the emitted role-label and primary
  predicates. **Unknown/stopped:** primary/supporting/unknown status and role
  preservation. E1–E3 establish observed Bill identity/title agreement only.
- Mandatory English titles/Member names and incomplete independent datatype,
  DateRange-type/conflict checks prevent **complete fail-closed selection
  certification**. No hidden unlabelled candidate or interval conflict was
  demonstrated; nor is their absence independently certified. C1's recorded
  chain and E's observed sets are verified, not exhaustive executor-safety
  certifications. No additional requests or modified expectations were used
  to erase this limitation.
- A1/A3's “members were in” is the approved seat interpretation. A2 tests that
  intended operation with explicit seat language, not a claim that people and
  seats are universally synonymous.

## 4. Results and repeatability

**Observed—execution:** 30 scheduled `/ask` requests ran from
`2026-11-10T22:18:42Z` to approximately `22:20:43Z`, including **23 genuine
model calls**. All returned HTTP 200; provider outputs were received and parsed.
No provider HTTP error, timeout, invalid JSON or SPARQL transport failure was
observed. HTTP status and internal `success` are not factual scores.
`execution-log.txt` records every request's status, model-call count and final
row count. `assessments.json` records exact checked properties, not a general
correctness percentage.

**Observed—execution:** the five independent evidence queries were rerun after
the fixed campaign; all returned exactly the same typed bindings. Full named
graph names/counts were also unchanged (7,982 / 1,119,860). See
`oracle-after.json`, `graph_inventory-after.json` and `stability.json`.
**Unknown:** transactional isolation or equal-size mutations outside the
queried evidence. The experiment itself issued no mutation requests.

The repeat subset was selected before results: a closed semantic chain (C1),
the complex historical composition (D8), and the known sponsorship selector
discrepancy probe (E2). Three observations means the first plus two additional
requests, not three extra runs.

| Question | Observed selection in all three runs | Factual/evidence repeatability |
|---|---|---|
| C1 | `capability_selection` → `current_office_constituency`; same final plan | Identical Simon Harris/Wicklow chain, holding/membership identities and dates; correct for checked recorded evidence |
| D8 | `member_relationship_composition`; same final plan | Identical correct Cyprian Brady/common interval **and identical erroneous `/25` evidence text**; not an unqualified repeatable-correct answer |
| E2 | `member_bill_sponsorship` graph draft; same final canonical plan | Identical 20 Bill identities/titles and projected rows; role/primary correctness unscored |

**Observed:** the raw draft strings vary, while these final plans and result
rows are equal. Thus model text is not byte-deterministic even when the checked
factual result is stable. None of the three repeated questions refused; no
“consistent refusal” is counted as reliable factual answering. Refusal
repeatability for A2/C2/C4/E4 is **Unknown**, because they were not in the
preselected repeat subset. There were no outcome-changing repeats in this
small subset; this is not a model-variability rate.

## 5. Failure-stage classification and trace references

Trace notation `ID/rN` identifies a JSONL record and the corresponding
`ID-rN.html`. Capture includes actual draft text, not just an inference from
the final answer.

| Classification | Observed case / first observable divergence | Boundary and limitation |
|---|---|---|
| **Implemented but not selected** | A2/r1: model emits `supported=false`, intent “Count the seats in the 34th Dáil”, and says seats unsupported; A1/r1 independently executes `dail_seats`=174 | AI interpretation/capability-selection outcome; no invalid SPARQL or execution was observed. **Inferred** deterministic recognition did not admit A2 and semantic fallback was used, from one actual model call plus dispatcher source |
| **Selected but rejected by validation** | C2/r1: `supported=true`, `capability_selection`, `current_office_constituency`, office `Minister for Finance`; local diagnostic says only current office→Member→current-Dáil path supported, despite current-only question | Actual rejection is `UnsupportedComposableRequest`/public `unsupported_capability`, not a provider refusal. Source boundary: `composable_semantic_planner.py:859–869`. No final plan or answer. Underlying exact causal condition not investigated |
| **Selected and executed with incorrect evidence projection** | D8/r1–r3: expected Member and intersection match; retained raw qualifying Cyprian binding says `term=/30`; final text additionally says `term=/25` before later correctly stating shared constituency/term `/30` | First **observed** mismatch is raw-evidence→projected evidence text. **Inferred** downstream evidence evaluation/projection, not an incorrect model-selected Member. Full debug is truncated; exact origin of `/25` is **Unknown** |
| **Executed correctly for checked selection but source-evidence limited** | B1/B2: parties correct, groups unavailable; C3: seven recorded Tánaiste holdings end before asOf; E5: no valid Published-date evidence for Malcolm Byrne's selected Bills | Missing evidence is not a false negative, vacancy, zero or compiler defect. C3/E5 stop without a factual result; their final plans and diagnostics, not “execution attempted” UI flags, establish evidence-boundary handling |
| **Correct and repeatable in checked facets** | C1 and E2 across r1–r3 | Exact known chain or Bill identity/title set and same projection; source-safety and sponsorship-role limits above remain |
| **Unsupported by implemented contract** | C4 historical chain; E4 unqualified all-time sponsorship count | Correct bounded refusals, not implemented-capability generalisation failures |
| **Indeterminate because evidence unavailable** | Sponsorship role/primary preservation; complete alternate/unlabelled source selection; full subsidiary-query timeline; loaded capture provenance; refusal repeatability | No claim of complete correctness or precise causal location is made for these facets |

**Observed—negative findings within this sample:** no identity-resolution
ambiguity, unresolved named identity, invalid-draft syntax, unsafe query,
SPARQL execution error or provider failure was exposed. This is not evidence
that those stages generalise outside the selected cases.

## 6. Within-capability and cross-capability findings

- **A — Observed:** same deterministic template tolerates term substitution
  (174→160); explicit-seat paraphrase loses answer availability. **Inferred:**
  implementation existence and semantic-route discoverability differ here.
- **B — Observed:** deterministic B1 and model-mediated B2 converge on the
  same operation, exact identities and group-coverage qualification. Party-only
  restriction and term substitution also preserve meaning. The unavailable
  group portion remains partial, not an invented empty roster.
- **C — Observed:** one semantic chain answers repeatedly, while an equivalent
  passive phrasing selects it but is locally rejected. Different-office evidence
  shortage and unsupported historical scope produce distinct nonanswers. This
  separates validation reachability from source availability.
- **D — Observed:** controlled language, entity, historical-scope, filter-removal,
  count and explicit-OR forms preserve their independently checked selections.
  The same person in D1/D4 is supported by different current/historical paths;
  equal labels alone were not credited as temporal fidelity. Complex D8's
  correct person and intersection coexist with an incorrect term assertion.
- **E — Observed:** deterministic E1 and semantic E2 converge on the checked
  Bill set; Member substitution works for the observed set. E2 uses the working
  graph route in all three trials, **not** the unusable generic selector.
  **Unknown:** frequency/impact of the advertised adapter discrepancy beyond
  those trials. E4/E5 distinguish unsupported projection from supported but
  evidence-blocked count; neither is a numerical answer.

**Inferred—cross-capability:** failures are not confined to a single stage:
declined selection (A2), local rejection after correct selection (C2), and
post-query evidence inconsistency (D8) are distinguishable. Conversely, two
deterministic/semantic pairs converge correctly on their checked selections.
Neither uniform generalisation failure nor an architectural defect follows.
Stable final output also does not imply stable-correct evidence, as D8 shows.

## 7. Competing explanations, not causal conclusions

| Observation | Evidence-supported explanation | Competing explanation / remaining uncertainty |
|---|---|---|
| A2 declined while A1 answers | **Observed:** no seat capability selected by the model; Stage 2 found seats outside the generic semantic catalogue | **Hypothesis:** model uncertainty/instruction interpretation versus absence of a suitable exposed model draft route. One request cannot establish stable behavior or distinguish these causes |
| C2 correct selection rejected | **Observed:** rejection occurs at the local question-validation boundary, not provider generation | **Hypothesis:** a surface-form admission limitation versus an unrecorded semantic concern in that boundary. The selected draft and current-only question narrow the possibilities; the specific condition is uninvestigated |
| D8 correct person, conflicting term | **Observed:** retained qualifying binding and independent oracle agree on term 30; projected text includes 25 | **Hypothesis:** cross-row metadata association or later text assembly versus some unseen evidence transformation. RDF inconsistency elsewhere is not exhaustively excluded; the retained qualifying row itself does not contain the wrong term |
| C3/E5 lack answers | **Observed:** required accepted-current holding / dated Published evidence is absent in inspected selections | **Unknown:** source coverage and capture lineage. A real-world absence, vacancy or zero is not established; a compiler defect is not required to explain these outcomes |
| E2 never uses broken generic selector | **Observed:** three graph-family selections work | **Hypothesis:** prompt/draft-schema guidance favors the graph route versus ordinary model sampling. No frequency claim or conclusion that the catalogue discrepancy is harmless is justified |

## 8. Unresolved causal questions reserved for Stage 4

1. Which boundary determines A2's inability to reach the implemented seat
   operation: model interpretation, model-exposed capability surface, or route
   admission—and is the refusal stable? **Unknown.**
2. Which exact local condition rejects C2 after the right capability was
   selected, and does that condition distinguish semantics or only wording?
   **Unknown.**
3. Where is term `/25` introduced between D8's retained qualifying `/30`
   binding and final evidence text, and which displayed assertions share its
   origin? **Unknown.**
4. Under what inputs does the generic sponsorship selector appear rather than
   the working graph draft, if any, on this baseline? **Unknown.**
5. What loaded-source provenance and unlabelled/uncertain evidence would be
   needed to adjudicate the currently stopped completeness/role facets?
   **Unknown.** This is an evidence question, not permission for data changes.

These questions are recorded for review only. No causal probes, expanded
question set, implementation investigation into the specific defects, remedies
or Stage 4 work are undertaken here.

## 9. Stage 3 exit-criteria assessment

| Criterion | Assessment |
|---|---|
| Requested baseline and working-tree differences recorded | **Met**; source unchanged, Stage 1/2 inputs preserved |
| Meaningful real application/provider/RDF execution established | **Met** for this local environment; no synthetic substitutes |
| Dataset identity and source provenance | **Partial**: endpoint, complete graph inventory and stable question-relevant typed bindings pinned; loaded capture identity unknown |
| Five justified families and bounded controlled matrix | **Met**; 24 frozen questions, unsupported dimensions explicit |
| Independent expected semantics and RDF support | **Met for checked facets / partial overall**; stopped role and complete fail-closed source-selection adjudication disclosed |
| Complete scheduled run and selected three-run subset | **Met**; 30 requests/23 real model calls; no expansion |
| Proposal/validation/plan/query/result evidence captured where available | **Met with limits**; subsidiary-query timeline unavailable and D8 debug truncated; no hidden-decision claims |
| Unexpected outcomes inspected and first observable divergence classified | **Met within retained evidence**; A2, C2 and D8 distinguished from data gaps and unsupported semantics |
| Whole-output factual reliability or overall compiler success rate | **Not established**, and not inferred from the sample |
| No fixes, semantic changes, production writes or Stage 4 | **Met** |

**Disposition:** the bounded Stage 3 experiment is completed and submitted to
ChatGPT for evidence review. **Unqualified exit acceptance is not claimed**:
dataset lineage, stopped oracle facets and trace limits require an explicit
review decision. The observed results do not warrant either an architectural
defect conclusion or a blanket generalisation certification.

### Evidence preservation and verification

New evidence is under `docs/reports/query-service/nlq-stage-3-20261110/`:

- `baseline.json`, `freeze.json`, `questions.json`: revision/configuration and
  immutable experimental definition;
- `oracle-before.json`, `expected-answers.json`, `oracle-after.json`,
  `stability.json`: independent RDF queries, raw typed bindings and stability;
- `graph_inventory-{before,after}.json`, `catalog_identity-before.json`,
  `readiness.html`, `application-preflight.json`: environment/data diagnostics;
- `responses.jsonl` and all 30 `ID-rN.html` files: real proposals, final
  outcomes/plans/SPARQL and complete rendered responses;
- `assessments.json`, `execution-log.txt`, `independent-oracle-review.md`:
  checked properties, actual execution log and independent limitations;
- `verification.json` and `sha256-manifest.json`: final integrity/state checks.

Historical evidence is untouched. Existing debug strings are preserved even
when truncated; they are not silently represented as complete endpoint JSON.
Scratch code/logs are not the sole retention location for findings or responses.
Frozen question/oracle hashes and response HTML hashes are checked, every
scheduled record is present, and matched RDF identity/count properties are
asserted. Focused pytest remains blocked by missing pytest. No source or
ontology changes require a speculative full-suite success claim.

**Stopped after Stage 3.**
