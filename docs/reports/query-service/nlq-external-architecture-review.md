# OireachtasOntology NLQ — Independent Architecture Second Opinion

## 1. Executive judgement

**Assessment:** the current implementation is a **hybrid bounded-capability compiler with a genuinely reusable deterministic execution core**, not a predominantly free-form NLQ compiler and not merely a collection of unrelated SPARQL templates.

Its strongest property is **semantic safety after a valid plan has been admitted**: controlled RDF relations, exact identity resolution, graph-ownership checks, deterministic SPARQL, read-only validation, bounded pagination, temporal-evidence evaluation, and explicit unsupported/evidence outcomes.

Its weakest property is **natural-language reachability**. Three different mechanisms can reject a question before that execution core is used:

1. deterministic surface-form recognizers;
2. model capability selection or model-authored graph construction;
3. a second, deterministic lexical interpretation of the original English performed during admission.

That architecture is appropriate for a **curated, fail-closed parliamentary query service with explicitly reviewed operations**. It is not, by itself, sufficient for a flexible general NLQ interface in which independently supported entities, relationships, temporal scopes, filters, and answer projections are expected to recombine naturally.

**Confidence:**

- **High** about the implemented architecture and its principal limitation, based on direct code paths and current read-only diagnostics.
- **Medium-high** about the causes of the historical failures.
- **Low-to-medium** about the current branch’s broad natural-language success rate. There is no fresh, independent generalisation holdout for HEAD. The latest live evidence is useful but curated and relatively small.

The review covered HEAD **`03ee123`** on `query-service-semantic-completeness`. I did not alter files, invoke live LLM queries, execute a benchmark, or rerun the full suite. The worktree remained clean.

---

## 2. Implemented architecture

### 2.1 The actual default `/ask` path

The default browser mode is `phase2`, which calls:

```text
app.ask
  → composable_plan.execute_question
  → _execute_question
  → deterministic preflight and recognizers, or semantic planner
  → draft and final-plan validation
  → exact entity/term resolution
  → deterministic SPARQL compilation
  → SPARQL safety validation and bounded execution
  → family-specific result projection
  → generic HTML table rendering
```

The implementation is more complicated than the architecture document’s high-level description.

#### A. Deterministic interpretation happens before the LLM

`poc/nlq/composable_plan.py::_execute_question` performs, in order:

- `unsupported_whole_intent` checks;
- explicit/future calendar-date handling;
- `_composable_interpretation_preflight`;
- a source-grounded current-office lookup;
- implicit constituency-set clarification;
- the broad `semantic_composition_scope` routing check;
- deterministic representation, Government, Stage A, Stage C, Stage B, office-calendar, and legacy Q06/Q09 recognizers.

Only after those paths does it invoke `_execute_shared_dail_terms_question`, which is the general semantic-planner entry point despite its narrow historical name.

Consequently, the LLM does **not** see every question. Some questions are answered deterministically, and others are refused or sent to clarification before a model call.

#### B. The model produces strict semantic JSON, not SPARQL

`create_composable_plan_generator` in `poc/nlq/composable_semantic_planner.py` uses the shared `ResponsesPlanGenerator` transport with:

- `composable-query-plan-draft.schema.json`;
- a large prompt rendered from the contract plus extensive hand-written family instructions;
- one model call, with no repair or retry loop.

A supported model response can be:

- `capability_selection`, naming an existing operation and parameters;
- a detailed graph proposal for `shared_dail_terms`;
- a `member_relationship_composition`;
- one of the separate families such as `constituency_representation`, `member_party_history`, `member_bill_sponsorship`, or `government_party_members`;
- `supported=false`.

For graph proposals, the model supplies referent roles, reviewed relation IDs, constraints, selectors, and answer shapes. It is instructed not to supply IRIs, predicates, graph names, SPARQL, or identity decisions.

The `intent` field is free text. It is **not** a structured, exhaustive record of all semantic obligations in the source question.

#### C. Local code reinterprets the original English during admission

Validation is not limited to JSON Schema and graph compatibility.

Examples include:

- exact source-span checks for Member, office, party, and constituency mentions;
- `_question_dail_ordinals`;
- allowed residual-word sets;
- explicit-current and present-default checks;
- additional-date and relationship denylists;
- exact word-tuple matching for office-period questions;
- whole-intent seat/election/sitting checks;
- count/list compatibility checks.

These appear principally in:

- `composable_semantic_planner.py::validate_composable_plan_draft`;
- `_validate_capability_selection_draft`;
- `_validate_member_relationship_draft`;
- `_validate_member_party_composition_draft`;
- `_validate_bounded_composition_draft`;
- `interpretation.py`;
- `composable_plan.py::_composable_interpretation_preflight`.

Thus the model is authoritative for proposing an interpretation, but **not** for determining whether its language interpretation is admitted.

#### D. Plan construction is only partly canonical

There are three distinct construction styles:

1. **Operation-to-canonical-handler:** generic `capability_selection` adapters invoke existing Stage A/B/C or specialised handlers.
2. **Model graph → canonical closed shape:** validators normalize the proposal and add `version`, `asOf`, and selected policy evidence.
3. **Deterministic direct plans:** Stage A/B/C and legacy recognizers construct plans directly from regex captures.

`complete_v2_plan` adds limited envelope metadata and selected current-date constraints. It does not generally construct the graph for the model.

#### E. Deterministic compilation and execution are substantial and reusable

The strongest shared implementation is in `composable_plan.py`:

- typed relation and graph-ownership validation;
- reviewed RDF-pattern checks against the query-schema contract;
- `_member_relationship_composition_mapping`;
- generic non-temporal graph compilation;
- temporal party/representation compilation;
- current and previous House-term resolution;
- exact constituency and affiliation resolution;
- interval evaluation and common-intersection logic;
- complete bounded pagination and distinct-identity aggregation.

Every executed query passes `safety.validate_sparql`, which enforces read-only SELECT/ASK, direct allowlisted predicates, no SERVICE/FROM/subqueries/property paths, and row/offset bounds. `pagination.select_pages` refuses to return a truncated answer as complete.

#### F. RDF results use specialised answer projections

`results.parse_results` creates a generic `QueryResult`, but most capabilities subsequently construct their own display `QueryResult`.

Examples:

- previous-Dáil representation: `readable_member_result`;
- current Member composition: `_execute_member_relationship_composition_plan`;
- representation: `execute_representation`;
- office episodes: `readable_member_office_evidence_result`;
- committee roster: `project_members`;
- sponsorship: `readable_bill_sponsorship_result`.

`app.py` also contains a large family-classification and explanation block. The final template renders every resulting column generically; it does not hide URIs or provide a common answer-schema policy.

### 2.2 Other paths that should not be confused with the default

- **Phase 1:** `pipeline.process_question` performs direct LLM-to-SPARQL translation, guarded by Member ambiguity resolution and syntactic/safety validation.
- **Older structured Phase 2B:** `plan_pipeline.process_planned_question`, `StructuredPlanner`, and `PlanSparqlGenerator` form a separate semantic-plan path. They are not called by the current browser `/ask` implementation.
- **Older presentation helper:** `presentation.capability_catalogue` describes the older query-plan contract and is not what `/capabilities` uses.

---

## 3. Capability generalisation

The five states must be assessed separately.

| Dimension | Implemented | Discoverable | Reachable | Correct | Reliable |
|---|---|---|---|---|---|
| Exact deterministic question forms | Yes | Through recognizers and public examples | Yes | Strong fixture and live evidence for many | Generally good for the exact recognized forms |
| Paraphrases within advertised semantic families | Yes | Through planner instructions | Variable | Often correct once a valid plan is reached | Not established broadly |
| Entity substitutions | Typed mentions and exact resolvers | Yes within each family | Usually, when mention extraction succeeds | Strong evidence for Member, party, constituency, term, and office substitutions | Good within tested substitutions, not for arbitrary aliases or spans |
| Houses, terms, and temporal scope | Shared House-date and interval machinery | Family-specific | Only enumerated scopes | Strong for reviewed numbered/current/previous/latest and overlap cases | Shape-specific, not a general temporal algebra |
| Filters, conjunction, and negation | Only reviewed constraints and graphs | Limited | Many ordinary combinations are refused | Safe refusal is generally correct | No general support |
| Lists and counts | Several list/count pairs reuse the same selection | Family-specific | Yes in reviewed shapes | Strong identity/count evidence in those shapes | Good within those shapes, but display is inconsistent |
| Boolean and specialised answers | Stage/family-specific | Often outside generic dispatch | Variable | Strong in several deterministic families | Family-specific |
| Composition of existing relationships | Bounded graph shapes and three declared operators | Prompt enumerates shapes | No closure under arbitrary recombination | Good when the exact shape is supported | New combinations usually require new admission work |

### Demonstrated strengths

The historical independent evaluation provides real evidence of reusable execution rather than fixture memorisation:

- H11/H12 changed both Dáil terms and returned exact 88- and 59-Member intersections.
- H23/H24 transferred party/constituency/term joins to different entities.
- H17 distinguished current term-wide counting from H20’s explicit current-date count.
- H47/H48 reused the same current-Seanad/prior-Dáil selection for list and count.
- Sixteen original passing controls were retained in that run.

See `docs/reports/query-service/independent-generalisation-evaluation.md`, especially §§5–8.

The current branch adds further useful reuse:

- shared House-date resolution;
- shared party temporal scope across Dáil and Seanad;
- list/count selection parity;
- canonical dispatch into existing Stage A/B/C handlers;
- current committee and officeholder-to-constituency adapters that reuse existing evidence evaluators.

### Limitations

A natural-language question is successful only if it passes the **product** of these conditions:

```text
recognized or discovered
× admitted by source-English guards
× valid model graph, where required
× sufficient accepted RDF evidence
× compatible answer projection
```

A passing compiler test covers mainly the final two conditions. It does not establish the first three.

The same independent evaluation found only **22 correct factual answers from 48 supported, evidence-backed questions**. Most misses were safe nonanswers, not incorrect SPARQL results. This is evidence for a language/admission problem, but it is not a measurement of the current HEAD.

The latest Tranche 2 addendum reports 21 successful answers from 30 curated live requests, with one malformed-model-plan refusal. That is encouraging current evidence, but it is neither an independent holdout nor a population-level reliability estimate.

---

## 4. Architectural consistency

### A. Fragmentation versus reusable semantic operations

There is meaningful reuse at three levels:

1. the shared typed v2 plan envelope;
2. reviewed relation and RDF-pattern registries;
3. shared graph compilation, temporal evaluators, identity resolution, and pagination.

However, the semantic surface is still organised around **closed graph families**, not general operator composition.

Concrete examples:

- `_validate_member_relationship_draft` accepts only two non-party topologies: two numbered terms or one term/constituency path.
- Its count/date projection is restricted to the one-term/one-constituency case.
- `_validate_member_party_composition_draft` rejects counts for party-plus-constituency while allowing counts for party-only selection.
- Cross-House paths have their own validators and result functions.
- Office, sponsorship, representation, committee, Government, and Stage A/B/C answers have separate projections and explanation branches.

The model is explicitly instructed to return `supported=false` for anything outside those shapes.

Therefore, a new combination of already mapped relationships does not compose merely because each relation resolves successfully. It must match a pre-approved schema `anyOf` shape, prompt shape, draft validator, final validator, compiler, executor, and often presentation branch.

### B. Interpretation and admission: two language authorities

The deterministic checks are not accidental. They address a real safety gap:

- A well-typed graph can omit a requested party, date, exclusion, extra person, or answer measure.
- The plan contains no exhaustive semantic-obligation ledger against which completeness can be proved.

The Tranche 2 report preserves historical evidence that **10/10 deliberately incomplete, well-typed candidates passed compatibility-only checks**. Simply removing the lexical guards would therefore weaken safety.

But those guards also produce false refusals because they are a second, narrower English parser. Examples include:

- closed residual vocabularies;
- one ordinal spelling;
- exact accepted word tuples for office periods;
- metalinguistic phrases such as “rather than seats” being treated as a positive seat request;
- “even if periods did not overlap” being treated as a simultaneity requirement.

This is both:

- a **necessary safeguard against an incomplete structured interpretation**, and
- an **architectural limitation created by splitting semantic interpretation between the model and repeated local grammars**.

The failed historical experiments do not show that model-authored obligations, self-audit, or another LLM verifier solve this problem. Tranche 2 explicitly records poor supported-request admission and omission-detection results on the other branch.

### C. Capability discovery and layer consistency

There is no single authoritative runtime registry connecting all capabilities.

The relevant layers are:

- `semanticDispatch.capabilities`: nine entries;
- generic draft-schema selection enum: eight entries;
- sponsorship as a separate family rather than generic selection;
- `questionFamilies`: 39 descriptive entries, not all independently executable;
- manual planner instructions for other graph families;
- adapter `if/elif` validation;
- a second executor `if` chain;
- public `/capabilities`, which instead lists 32 RDF relation entries with one generic status string.

Commit `30a611c` correctly fixed one concrete mismatch by filtering generic instructions through the schema’s capability enum. The associated test now establishes generic prompt/schema parity and confirms sponsorship remains separately discoverable.

That fix does **not** provide full inventory parity. Current HEAD still has no generic semantic-selection entries for existing operations such as:

- `term_count`;
- `house_terms`;
- `dail_seats`;
- several other Stage A/C operations.

Their executors exist, but unfamiliar wording cannot reliably select them through the semantic fallback.

#### Controlled contract finding

`composable-query-plan.schema.json` omits both:

- `current_committee_members`;
- `current_office_constituency`.

Read-only validation of the plans returned by `committee_members.make_plan` and `office_representation.make_plan` produced one family-enum error for each.

This does not currently block execution because runtime uses Python `validate_plan` and family validators rather than this JSON Schema. It does demonstrate that the contract layers disagree and that the UI’s “Validated composable query plan” label means Python validation, not full JSON-Schema conformance.

### D. Answer consistency: last versus current Dáil

The reported Dublin Central difference is caused by **server-side answer projection**, not by SPARQL alone or by a template defect.

#### Last Dáil

The deterministic Q09 path:

- matches `represented … in the last|previous Dáil` in `plan_question`;
- compiles raw `?member_member ?memberName` output;
- calls `readable_member_result`;
- deliberately returns only `("Member",)`, discarding the Member URI from the visible table.

`tests/test_nlq_composable_q09.py` explicitly verifies the name-only UI behavior.

#### Current Dáil

The exact wording requires semantic planning because neither deterministic recognizer owns it.

Under the planner-preferred `member_relationship_composition` route:

- current term and constituency are resolved;
- active membership intervals are evaluated;
- `_execute_member_relationship_composition_plan` returns `("Member", "Member identity")`.

A valid alternative `constituency_representation` route returns an even richer set of Member, constituency, term, and identity columns.

The template simply renders all supplied columns.

**Conclusion:** this is a projection-policy inconsistency, not evidence that the current query compiler fabricated URIs. The exact live family choice for the current wording was not rerun in this review, so the model-preferred path and the alternative representation path should remain distinguished.

### E. Extension cost

Recent diffs show both low-cost reuse and substantial cross-layer expansion.

| Change | Actual implementation evidence | Assessment |
|---|---|---|
| `aa8268f` current Dáil party selection | Eight production lines in `composable_plan.py`, 26 in the semantic planner, and expanded regressions | Strong reuse of an existing graph, resolver, temporal evaluator, and projection |
| `30a611c` sponsorship discovery | Eleven planner-instruction lines plus focused discovery tests | Small, well-targeted registry-alignment correction |
| `03ee123` shared present defaults | Shared `current_relationship_scope`, party/default helpers, family edits, UI explanations, and 168 lines of new focused tests | Useful shared policy extraction, but still requires per-family admission and explanation updates |
| `d655257` bounded operators | New draft/contract operator shapes and prompt rules, `_validate_bounded_composition_draft`, major compiler/executor work, and a new 406-line test module | Real reusable `identitySet`, `sharedResource`, and `commonIntersection` semantics, but high cross-layer implementation cost |
| `351ae2f` current committee roster | New 193-line `committee_members.py`, planner/executor adapters, schema/contract changes, app summary, and 217 test lines | Reuses Member evidence primitives, but remains a new capability module and routing path |
| `0ebc9bc` officeholder constituency | New 118-line `office_representation.py`, reused representation executor, adapters, and new tests | Good relational reuse, with another family-specific plan and presentation |
| `a2f7773` distinct Member counts | Hundreds of production changes across compiler, semantic validator, interpretation, and per-family projections | Counting is not a generic flag over arbitrary selections; it is admitted shape by shape |

The general pattern is not “every feature is a new SPARQL template.” Rather:

> RDF and temporal primitives are increasingly shared, but each new semantic shape still tends to add coordinated prompt, schema, validator, routing, execution, presentation, and fixed-draft test work.

That is the maintainability limitation.

---

## 5. Root-cause assessment

### 5.1 Recurring failure classes

| Failure class | Demonstrated mechanism | Classification |
|---|---|---|
| Existing operation not selected | Generic dispatch omits operations whose deterministic handlers exist | Incomplete capability integration/discovery |
| Correct draft rejected by wording | Original English is rechecked with narrow grammars | Interpretation/admission defect caused by the dual-authority design |
| Model graph omitted an edge or repeated an ID | Model must author detailed graphs for several families | Planner robustness problem increased by graph-authoring burden |
| Early recognizer captures the wrong entity span | Deterministic parser commits before semantic recovery | Local parser defect plus routing limitation |
| Combination of existing relationships refused | Closed schemas and validators enumerate permitted graph topologies | Deliberate bounded-composition boundary |
| Missing election, office, sponsorship-date, vote, panel, or career evidence | Required RDF/evidence/coverage is absent or not accepted | Missing capability or evidence, not compiler architecture |
| Different answer columns for similar questions | Separate `QueryResult` projections | Presentation inconsistency |
| Valid Python plan invalid under published JSON Schema | Schema family enum drifts from newer handlers | Contract-maintenance defect |
| Count from incomplete/uncertain evidence | Pagination, interval, and coverage guards stop the answer | Correct fail-closed safeguard |

### 5.2 Current controlled observations

A few read-only diagnostics confirm that older failure mechanisms are still present in HEAD:

1. **“Dáil number 24” admission**

   A forced, otherwise valid `termNumber: 24` constituency draft was rejected because `_question_dail_ordinals` recognizes only ordinal-suffix forms. This reproduces the mechanism behind historical H13–H15/H42; it is not a new model-reliability measurement.

2. **Unqualified present-time non-party composition**

   For “Name the Deputies who represent Mayo.”, a forced `member_relationship_composition` draft with `currentTerm` was rejected because `_validate_member_relationship_draft` still requires explicit current wording before `member_relationship_as_of_default` is considered.

   This is an internal admission inconsistency following the new present-default policy. The actual Tranche 2 live run took a different failing route: the model selected `constituency_representation` with an object selector whose schema requires a string.

3. **Early entity span capture**

   `plan_representation_question("Who are the TDs for Louth today?")` still produces constituency mention **`Louth today`**, while the unqualified form produces `Louth`. The earlier H19 deterministic-resolution failure therefore remains structurally possible.

4. **Schema mismatch**

   The two new current-family plans fail the published complete-plan JSON Schema as described above.

These are local, deterministic findings, not a new benchmark.

### 5.3 Provenance and contrary evidence

The evidence populations are not interchangeable:

- **Human-question feedback:** the 26 original cases in `user-question-regression.md` came from preserved user question reports. They provide the best evidence of actual user expectations, including ambiguous and currently unanswerable cases.
- **Approved requirements:** the 39 approved cases and U01–U36 are reviewer-approved evaluation artifacts, but the unseen document explicitly says its first 12 were not collected from external researchers.
- **Independent 60-question evaluation:** an independently constructed, contract-informed, AI/executor-authored holdout. It evaluated a dirty master state based on `6b38eff`, not current HEAD. Its contamination and dataset limitations are documented.
- **Semantic-dispatch campaign:** `semantic-dispatch-interpretation.md` is on `origin/feat/query-service-generalisation`; implementation froze at `1e97ae4`, which is not an ancestor of current HEAD. Its independent AI/executor-authored acceptance set scored 6/38 factual passes and the campaign was explicitly not accepted.
- **Semantic-completeness studies:** historical shadow studies on that branch were also AI-authored. They did not execute factual `/ask` answers and should not be represented as human-language reliability measurements.
- **Current Tranche 2:** genuine model and live-RDF checks, but curated development evidence rather than a fresh independent holdout.

Contrary evidence matters:

- The 60-question study observed no incorrect answer among its 22 factual successes.
- The failed generalisation campaign did observe projection and candidate-preservation defects on its historical implementation.
- Some failures labelled “unsupported” are appropriate because the requested operation or adequate evidence was never promised.
- Data-backed refusal is not evidence for redesign, and a passing fixed draft is not evidence for natural-language reliability.

### 5.4 Independent judgement on causation

The recurring failures have a **common structural contributor**, but not one universal cause.

The common contributor is the separation between:

```text
what deterministic execution can do
and
what the language/admission layers permit a user to reach
```

Within that contributor are four distinguishable mechanisms:

1. incomplete capability exposure;
2. duplicated English interpretation during admission;
3. detailed model graph authoring;
4. family-specific answer construction.

Other failures are independent: missing RDF evidence, deliberately unsupported global negation, model transport failures, and presentation choices.

---

## 6. Architectural options

| Option | Correctness and semantic safety | Flexibility | Maintainability and cost | Judgement |
|---|---|---|---|---|
| **Retain and incrementally harden** | Highest confidence for existing covered shapes | Improves paraphrases and exposure, but limited composition | Lowest initial cost; continuing cross-layer duplication | Appropriate for the current curated service |
| **Targeted structural change within v2** | Keeps deterministic graph validation, identity resolution, SPARQL, and evidence rules | Better reachability and lower model graph error; composition still bounded | Medium cost; requires inventory and adapter consolidation | Best risk/benefit next step |
| **General constrained operator graph compiler** | Potentially strong, but only with explicit semantic-obligation and evidence-coverage mechanisms | Supports much broader joins, filters, negation, aggregation, and projections | High design/test cost and substantial new semantic risk | Justified only if broader recombination is a firm requirement |
| **Direct LLM-generated SPARQL as the primary path** | Syntax and predicate safety can be retained, but complete-intent, identity, temporal, and coverage correctness become harder to establish | Superficially high | Small initial implementation, large hidden semantic-verification cost | Not recommended as the authoritative replacement |

### Why targeted structural change is the strongest current option

The existing v2 graph should remain the internal executable representation. Around it:

- advertise operations as typed inputs rather than detailed graph incantations;
- construct canonical graphs locally for every covered family;
- make registration tests cover prompt, schema, adapter, executor, final schema, and public catalogue;
- share list/count/projection policy where semantics truly match;
- retain source-English safeguards until a safer replacement is independently demonstrated.

This follows the direction in `docs/architecture/nlq-semantic-dispatch.md`, while recognizing that document remains a proposal rather than an accurate description of the present system.

### What would justify a substantially different compiler?

Redesign would be justified by observable evidence such as:

1. Inventory parity, canonical constructors, and shared projections are complete, yet independent failures remain dominated by valid new combinations rather than isolated wording bugs.
2. Each new combination still requires coordinated changes across prompt, schema, validator, compiler, and UI despite no new RDF relationship being introduced.
3. A controlled admission study shows that the existing dual lexical/model approach cannot simultaneously achieve acceptable supported-request reachability and omission rejection.
4. Required questions systematically demand set difference, general negation, arbitrary conjunction, historical composition, and projections not representable in the current family schema.
5. Those requirements are frequent and important enough to justify new semantic proof, coverage, and testing obligations.

The historical scores alone do not establish those conditions.

---

## 7. Recommendations

### Priority 1 — Establish one executable capability ledger

**Impact: high. Risk: low. Confidence: high.**

Create a review artifact, not another assumed registry, that records for every operation:

- deterministic handler;
- semantic-discovery route;
- schema representation;
- draft/final validators;
- compiler/executor;
- answer projection;
- supported temporal scopes and filters;
- natural-language and repeated-run evidence.

Immediately reconcile the confirmed final-schema omissions and distinguish descriptive `questionFamilies` from executable operations.

### Priority 2 — Prefer canonical plan constructors over more wording patches

**Impact: high. Risk: medium-low. Confidence: medium-high.**

Pilot local graph construction on one or two bounded families, using the model only for operation ID, grounded mentions, temporal scope, constraints, and answer projection.

Measure:

- supported-question admission;
- malformed graph rates;
- duplicate relation/omitted-edge rates;
- omission negative controls;
- repeated-run answer consistency;
- exact RDF results.

This is more likely to generalise than adding more example-specific graph instructions.

### Priority 3 — Treat complete-intent admission as a separate safety problem

**Impact: high. Risk: high if oversimplified. Confidence: high that the problem exists; low about the solution.**

Do not remove lexical guards merely because they cause false refusals. Equally, do not continue expanding them indefinitely and call the result semantic generalisation.

Before adopting model-authored obligations, source spans, self-audit, or a second LLM verifier, require an independent test that demonstrates both:

- improved admission of supported paraphrases;
- rejection of materially incomplete candidates.

The historical studies show that structural compatibility alone is insufficient and that model agreement is not independent proof.

### Priority 4 — Consolidate answer projection policy

**Impact: medium-high. Risk: low. Confidence: high.**

Define explicit display semantics for equivalent answers:

- default human-readable Member list;
- whether identity columns are primary evidence or optional debug detail;
- separate interval and source evidence;
- shared deduplication and pagination requirements.

Preserve the richer evidence where required, but do not let implementation family determine whether an equivalent Member list unexpectedly displays URIs.

### Priority 5 — Improve evaluation before expanding composition

**Impact: high. Risk: low. Confidence: high.**

A new evaluation should be frozen against current HEAD and should include:

- actual human questions kept separate from AI/analyst cases;
- unseen paraphrases of already supported operations;
- entity and term substitutions;
- meaningful new combinations;
- repeated runs;
- negative and metalinguistic controls;
- factual RDF oracles independent of application compilers.

Report Implemented/Discoverable/Reachable/Correct/Reliable separately. Do not use thousands of fixed-draft tests as a substitute for this measurement.

### Priority 6 — Defer a general graph-compiler decision until that evidence exists

**Impact: avoids unnecessary redesign. Risk: low. Confidence: medium-high.**

If targeted construction and inventory work resolve most failures, wholesale replacement is unnecessary. If failures then concentrate on genuinely unrepresentable combinations, a constrained operator-graph architecture becomes a defensible next investment.

Deterministic SPARQL compilation should be retained in either case.

---

## 8. Outstanding questions and evidence classification

| Classification | Finding or question |
|---|---|
| **Verified** | The default system is a hybrid of deterministic recognizers, model semantic proposals, lexical admission, and deterministic execution. |
| **Verified** | Reusable graph compilation and temporal/identity evaluation exist and produce correct results in several independently checked bounded cases. |
| **Verified** | Generic semantic dispatch does not expose all existing Stage A/C operations. |
| **Verified** | Original English is independently interpreted before and after model planning; this is both a safeguard and a source of false refusals. |
| **Verified** | “Dáil number N”, an unqualified present-time non-party current draft, and the `Louth today` span still fail or misparse in controlled current-code checks. |
| **Verified** | The two current-family plans do not conform to the published complete-plan JSON Schema’s family enum. |
| **Verified** | Last- and current-Dáil Member lists differ because their server projections differ, not because the HTML template selectively adds URIs. |
| **Verified** | The 6/38 failed acceptance campaign and semantic-completeness studies belong to a different historical implementation and must not be presented as current scores. |
| **Plausible hypothesis** | Canonical local graph constructors will materially reduce model graph defects and the prompt/extension burden. |
| **Plausible hypothesis** | A single registration mechanism would reduce discovery/schema/executor drift, but it would not by itself solve complete-intent admission. |
| **Plausible hypothesis** | Shared answer projections would reduce extension cost and user-visible inconsistency. |
| **Unresolved** | What fraction of current-user questions needs arbitrary recombination rather than robust access to a curated capability set? |
| **Unresolved** | What independent mechanism can establish complete source intent without reintroducing either brittle English grammars or unsafe model self-certification? |
| **Unresolved** | What is current HEAD’s factual answer rate and repeated-run reliability on fresh human and independently authored questions? |
| **Unresolved** | Should Member IRIs be part of ordinary answer presentation, optional evidence, or debug output? |
| **Unresolved** | After inventory and canonical-constructor improvements, will remaining requirements justify a general constrained operator graph? |

**Bottom line:** retain the deterministic execution and evidence architecture. The evidence supports substantial improvement through inventory parity, canonical plan construction, shared presentation, and better independent evaluation. It does not yet justify replacing that core with direct LLM SPARQL or committing to a general graph-compiler redesign. The decisive unanswered problem is not SPARQL generation; it is how to admit complete natural-language intent safely and flexibly without maintaining a second collection of narrow English grammars.