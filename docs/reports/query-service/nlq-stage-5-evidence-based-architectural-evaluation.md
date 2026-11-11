# OireachtasOntology NLQ — Stage 5: Evidence-Based Architectural Evaluation

## 1. Executive judgement

**Inferred — recommendation for human approval:** target a **bounded parliamentary research assistant with controlled compositional generalisation**, not unrestricted natural-language-to-SPARQL. Preserve deterministic identity resolution, reviewed RDF relations and graph ownership, compilation, temporal evidence evaluation and fail-closed execution. Prefer **Option B, a limited compositional extension within v2**, provisionally; do **not** approve a general compiler replacement on the present evidence.

This is a direction for a bounded decision-making experiment, **not a final architecture selection or implementation authorisation**. Option A can improve access to today's operations, but cannot alone meet a target that includes new combinations. Option C could make combinations cheaper, but neither that economy nor safe NL admission has been demonstrated. Existing investment is not the reason to retain the core: checked real executions establish useful reusable behaviour, whereas no alternative has equivalent comparative evidence.

Three questions must remain separate:

1. **Reachability:** can unfamiliar wording select an existing operation? Stage 3 A2 and C2 fail here for different reasons.
2. **Complete-intent admission:** does the proposed operation preserve every material requirement? A well-typed, executable plan is not sufficient evidence.
3. **Expressiveness:** can approved relations and operators form a genuinely new combination? Current v2 has no general closure under composition.

**Observed — historical/static:** Stage 3 demonstrates useful parameter, language and bounded semantic generalisation, not uniform failure. Stage 4 causally identifies A2's missing semantic exposure, C2's lexical false negative and D8's cross-row evidence annotation error. None requires replacing the compiler; none establishes that existing family boundaries will scale economically. D8 also defeats the claim that correct selected identities plus repeatability suffice for evidence integrity.

**Inferred — sufficiently supported decisions:** retain the deterministic safety/evidence obligations; reject direct LLM SPARQL as the authoritative replacement on this evidence; treat answer explanations as factual output; evaluate language admission separately from new-combination execution. **Hypothesis:** B delivers the proposed next increment at lower total risk/cost than C. **Unknown:** safe, flexible complete-intent admission and comparative extension cost. Sections 8 and 10 specify the evidence and human decisions needed before committing to either design.

## 2. Evidence baseline and limitations

### 2.1 Repository and investigation boundary

| Item | Stage 5 baseline |
|---|---|
| Repository / checkout | **Observed — Git:** `stephenrigney/OireachtasOntology`, `/var/home/stephen/Projects/OireachtasOntology` |
| Branch / full starting HEAD | **Observed — Git:** `master`, `938dad9c49d88b33b6181196fda5d989b12f6be4` |
| Initial working tree | **Observed — Git:** clean, including non-ignored untracked files |
| Remote | **Observed — Git:** `git fetch origin master` succeeded; `HEAD...origin/master` left/right counts `0 / 0` at investigation start |
| Stage 3 execution revision | `563a385173d312d33d22ca7868524714487967aa` |
| Stage 4 inspection revision | `3bdaa2b871096965ccc1b07d376b242879bc8585` |
| Revision reconciliation | **Observed — Git:** Stage 4 inspection revision → Stage 5 baseline adds only the Stage 4 report and external review; no `poc/`, tests or architecture implementation changes |
| Current relevant contracts | **Observed — static:** composable `2.30.0`; query-schema `2.12.0`; separate semantic-v1 `1.2.0` |

**Observed — investigation:** report-only reading, Git/provenance checks and retained-file integrity checks; no new application, AI, SPARQL, compiler or benchmark experiments, dependency installation, source/fixture changes, or production-data/configuration changes. All architecture and scope proposals below require approval. ETL publication and ownership boundaries in `docs/architecture/etl.md` are not reopened.

### 2.2 Evidence vocabulary and source ledger

- **Observed**: directly inspected source/contracts or retained evidence. Qualifiers distinguish static, historical execution and Stage 5 checks. A report's claim is an observed *claim*, not automatically an established result.
- **Inferred**: evidence-supported synthesis or architectural judgement, not a measured alternative.
- **Hypothesis**: a falsifiable prediction requiring further evidence.
- **Unknown**: evidence does not establish the answer.

For compact references, **R/** means `docs/reports/query-service/`, **S3/** means `docs/reports/query-service/nlq-stage-3-20261110/`, and **N/** means `poc/nlq/`. Section references identify report evidence; implementation references identify functions, not newly executed traces.

| Evidence inspected | What can be used / limitation |
|---|---|
| `R/nlq-stage-1-forensic-architecture-reconstruction.md` | Three-path reconstruction, responsibility boundaries and evidence inventory. Static reconstruction is not current runtime certification. |
| `R/nlq-stage-2-executable-capability-inventory.md` | Operations, discoverability, temporal/projection limits and inconsistencies. Test assertions were inventoried; pytest was unavailable. |
| `R/nlq-stage-3-controlled-generalisation-experiments.md`, `S3/` | Frozen 24-question, 30-request campaign, 23 actual model calls; retained drafts/plans/results, independent RDF oracles and selected repeats. Diagnostic sample, not a population benchmark. |
| `R/nlq-stage-4-causal-and-generalisation-mechanism-investigation.md` | Static comparisons and bounded offline counterfactuals localise A2/C2/D8. No current-HEAD live campaign. |
| `poc/specs/{composable-query-plan-contract,composable-query-plan-draft.schema,composable-query-plan.schema,query-schema-contract,query-plan-contract}.json` | Current admitted semantics, model surface, final envelope and RDF execution boundary. The separate v1 contract is not v2 capability evidence. |
| Human Question/Expected/Actual records and `R/user-question-regression.md` | Actual information needs; original external files under `/var/home/stephen/Documents/Scratch/`. Historical response provenance is incomplete; expanded regression cases are not 26 independent users. |
| `poc/specs/query-service-{questions-approved,unseen-questions-approved,fresh-holdout-20261101}.md` | Approved/authored requirements, not factual-answer proof. The unseen set explicitly disclaims external-researcher provenance. |
| `R/independent-generalisation-evaluation.md`, `R/independent-generalisation/` | Frozen independent AI/executor-authored holdout/oracles and retained response bundles. Different dirty source state and disclosed admissibility/independence limitations. |
| `R/{unseen-evaluation,fresh-holdout-20261101,temporal-aggregation-holdout-20261103,realistic-phase2-benchmark}.md` | Older route/compiler/provider comparison evidence. Distinct versions, configuration and scoring; not pooled with Stage 3 or treated as present reliability. |
| `R/semantic-completeness-tranche-2.md` and linked historical studies | Prior compatibility, obligation, self-audit and verifier results. Other-branch shadow studies must not be pooled with current `/ask` outcomes. |
| `R/nlq-external-architecture-review.md` | Independent second opinion on `03ee123`; not an approved ADR, fresh holdout or current runtime test. |

**Observed — Stage 5 integrity checks:** all **48** Stage 3 manifest entries match their SHA-256 values; all **seven** `baseline.json` input pins match; 30 retained JSONL responses are present. These checks establish artifact integrity, not oracle completeness or dataset immutability.

**Observed — external-review availability:** `/var/home/stephen/Documents/Scratch/NLQ-external-review.md` exists and is byte-identical to `R/nlq-external-architecture-review.md`; both SHA-256 values are `7ec05d0865f2003bd1a6961c9630a5bf341ccd33321af640dd27fee424f27e77`. Thus the separately supplied review was available, not reconstructed from assumed conclusions.

### 2.3 Critical limits, including the external review

**Observed — historical:** Stage 3's local dataset had 7,982 named graphs / 1,119,860 triples, with stable question-relevant typed bindings before/after. Loaded capture/run identity was not established. Its independent review stopped sponsorship role/primary-status scoring and full fail-closed source-selection certification: mandatory labels could hide candidates; datatype, DateRange and conflicting-interval checks were incomplete (`S3/independent-oracle-review.md`). Exact observed Bill identities/titles are usable evidence, not complete sponsorship-projection certification.

**Unknown:** current deployed factual answer rate, broader repeatability, end-to-end source coverage and complete subsidiary-query traces. Earlier missing-pytest results are not passing tests, nor a Stage 5 dependency diagnosis. No runtime suites are claimed here.

**Observed — historical:** the independent generalisation study reports 22 factual successes among 48 predeclared factual-answer cases, zero incorrect returned factual answers and 0/10 silently simplified unsupported/ambiguous requests. The 48 include exactly three disputed composition scopes; excluding those yields 22/45 clearly supported cases. That sensitivity does not remove clearly supported seats/party-catalogue misses. Its 19/20 repeated content/availability consistency includes stable refusals; only five of the six questions answered at least once answered consistently. These distinctions matter more than a pooled headline score (`R/independent-generalisation-evaluation.md`, §§5–9; `R/independent-generalisation/review-notes.md`).

**Observed — older evaluations:** `R/unseen-evaluation.md` cleared credentials and observed 36 generic nonanswers on a much older route; it is not an AI generalisation failure rate. The November 1 fresh holdout separately preserves an invalid unconfigured pass, diagnostic reruns and a valid configured baseline (five factual answers, 12 other guardrail-compliant outcomes, 19 gaps). The November 3 temporal holdout has 31 provider HTTP-400 failures among 36 requests, so those failures cannot diagnose semantic expressiveness. `R/realistic-phase2-benchmark.md` reports a historical separate semantic-v1 planner/compiler comparison: final structured results 32/37 passed, three unscored, versus 14/30 comparable Phase 1 passes, after development on that benchmark. **Inferred:** this supports caution about direct generation and the value of constrained execution, not a current A/B/C comparison or evidence that v1's capabilities are already integrated into v2. The reports' own architectural recommendations remain judgements, not decisions.

**Inferred — external review assessment:** its hybrid-compiler diagnosis and separation of discovery/admission/execution are corroborated by Stages 1–4 and current source. Its recommendation for targeted v2 change is plausible, **not independently validated by recommending it twice**. Its broad phrases such as “semantic safety after a valid plan” and “generally good” reliability need narrowing: a valid plan can still omit source intent, and D8 has incorrect provenance text after valid execution. The older independent study's 22/48 supported factual answers is evidence of that study, not a current score. The review itself discloses this, but its summary table must not override those limitations.

**Observed — static/Git:** extension history supplies contrary cost signals: `aa8268f` reuses current-party execution with small production edits, whereas `d655257` changes 12 files for bounded operators and `a2f7773` changes 12 for count support. **Inferred:** some additions are cheap and others cross-cut many layers. Diff size is not engineering time, defect risk or an A/B/C cost comparison. The review's proposed canonical constructors and shared projection benefits remain hypotheses. `docs/architecture/nlq-semantic-dispatch.md` is explicitly **Proposed**; neither it nor this evaluation confers implementation approval.

## 3. Required generalisation contract

### 3.1 Actual needs versus speculative scope

**Inferred — product target:** a researcher should be able to vary names, wording, scope and a small approved set of semantic operations without knowing compiler families or graph syntax. The system may clarify ambiguity, explicitly refuse unrepresented requirements, or report evidence unavailable. It must not silently answer a weaker question. Generalisation is measured relative to a published bounded semantic language, not the number of possible English sentences or the ability to generate arbitrary SPARQL.

| Parliamentary information need | Evidence / priority judgement |
|---|---|
| Party-filtered representation, parties in an historical Dáil, latest/previous representation, current office lookup | **Observed — human records:** examples include Sinn Féin/Dublin Central, parties in the 12th Dáil, Ahern's latest constituency and the current Taoiseach; also approved Q06–Q09/Q17. **Inferred:** essential next-increment scope. The adjacent current officeholder→constituency capability has authored Stage 3 controls, not a question in the three original human files. |
| Counts of people, distinct terms and Bills, with list/count fidelity | **Observed — recorded/approved needs:** counts occur in human regressions; approved Q04 is explicitly a technical, not priority user-facing scenario. **Inferred:** basic distinct counts matter, but not every possible aggregate. |
| Other party TDs sharing an anchor's constituency while that person held office | **Observed — human Q9 / S3 D8:** real multi-relationship/common-time need. **Inferred:** meaningful composition is already necessary; an exclusively flat lookup product undershoots actual needs. |
| Office episodes, “last” tenure, how long in office | **Observed — human records:** Stephen Donnelly/Health duration and last-office questions. **Inferred:** explaining periods versus cumulative duration is essential; answering office duration is not automatically safe or in the next supported subset. Local recorded episodes are not certified career completeness. |
| Committee rosters and party membership combined | **Observed — static:** both relations exist separately, not as an admitted combined query. **Inferred:** a realistic candidate extension. **Unknown:** frequency/priority among actual users; requires human confirmation, not attribution to the original records. |
| Three-term intersections, general Boolean trees, group/rank/average statistics | **Observed:** two-term intersections have authored approved precedents; Stage 4 uses three terms as a boundary example. **Hypothesis:** broader variants will be valuable. They are stress/longer-term candidates, not demonstrated priority human demand. |
| Votes, substantive debate topics, transcript speeches, election events | **Observed — approved questions/coverage reports:** legitimate desired information, often lacking queryable evidence or an approved retrieval path. **Inferred:** architecture must explain these gaps, not promise that a general compiler will supply missing facts. |

Original human records, approved cases, constructed diagnostics and independent AI-authored holdouts must remain separately labelled. Their occurrence establishes a need/example, not demand prevalence. **Unknown:** a representative distribution of future parliamentary questions or an agreed willingness to trade cost/latency for coverage.

**Observed — human/historical:** the three original files contain 25 Question/Expected/Actual records, scored as 26 questions after separating the Galway alternatives. The development campaign's consolidated outcome is 16 PASS / 3 PARTIAL / 7 FAIL, not 26 fully answered needs (`R/user-question-regression.md`, consolidated results/campaign closure). Original expectations include election dates and historical Agriculture Panel membership; these are genuine needs but not next-increment promises without accepted evidence/capability. A record expecting Noel Browne does not justify resolving an ambiguous surname without clarification. A single accepted Ahern tenure episode does not fulfil a complete-history request. The “Dáil sitting in June 1994” record expects a term start date: whether the user meant literal sittings rather than the term then in existence is **Unknown**, so that example is not clean evidence for either interpretation's priority.

### 3.2 Proposed next increment: bounded composition, explicit semantics

This is a **proposed target for approval**, not an amendment to existing contracts. Existing supported shapes retain their meanings; new combinations require separately approved query semantics and evidence obligations before admission.

**Observed — current contract:** eligible ordinary unqualified present-time relationships already default to configured `asOf` under the approved addendum in `R/semantic-completeness-tranche-2.md` and contract 2.30.0. That policy is settled, not an outstanding Stage 5 decision. What remains uncertain is flexible, complete admission and which additional combinations to support; no default-policy reversal is proposed.

| Dimension | Next-increment target | Explicit boundary / longer-term aspiration |
|---|---|---|
| Parameter generalisation | Ground different Members, parties, constituency occurrences, reviewed offices and numbered/current/previous terms through existing local resolvers. Preserve ambiguity and exact identity joins. | No guessed holders, manufactured IRIs, label-based cross-term merging or arbitrary fuzzy identities. Wider alias handling requires its own evidence. |
| Linguistic generalisation | Admit ordinary equivalent active/passive phrasing, term-number formulations and harmless politeness for supported semantics; explain genuine ambiguity. No requirement to memorise sample wording. | Not a promise to understand every formulation. A2/C2 are known development cases, not future held-out proof. |
| Semantic composition | Preserve existing complex shapes; add a small **explicit combination budget**, initially one selection/projection extension and one independently useful relationship combination if approved: party+constituency → distinct-Member count, and current committee roster ∩ current party membership. | These are **currently unsupported additions**, not mere bug fixes. No arbitrary pipeline of executors. Three-term intersection is a possible withheld extension-cost probe, not a committed product feature. |
| Temporal generalisation | Preserve current-at-`asOf`, historical numbered-term overlap, term-wide membership, strict prior service, latest-recorded and existing common-intersection distinctions. Independently date every relationship whose truth is time-dependent. | Do not substitute current for historical, term membership for simultaneous service, latest-recorded for current, or overlap for throughout. General historical office→representation joins and arbitrary interval algebra are later work requiring explicit meanings. |
| Filtering / negation | Approved named-party and exact-resource filters, bounded explicit constituency OR and anchor-identity exclusion. Every additional condition is represented or refused/clarified. | Identity exclusion is not global negation. No “never served”, arbitrary NOT/NOT EXISTS or inferred complement from absent local RDF. Later closed-universe set difference needs coverage authority. |
| Aggregation / projection | Selection-preserving entity lists and distinct-identity counts for approved combinations; counts identify their unit and evidence scope. Preserve separate episodes before deduplication. | No seats↔people↔episodes substitution. Office-duration, grouping, ranking, sums/averages are separately reviewed extensions, not switches added to any list. |
| Evidence / provenance | Correct row-bound identities, source graphs, intervals, selected term, selection/operator meaning, coverage status and original question/configured date. Stable internal evidence should support concise answers without losing traceability. | Positive local evidence is not a complete roster. Uncertain/capped evidence must not produce a complete count or certified absence. Presentation consistency does not mean flattening evidence into names only. |

**Inferred — acceptance meaning:** “supported” must mean the *complete* requested selection and answer form belongs to the approved language. “Evidence-backed” additionally means required RDF is accepted and adequate for that claim. A supported request may still yield an evidence nonanswer. Safe refusal counts as safety preservation, **not** successful supported-request answering. Unsupported extra requirements must invalidate/clarify the whole request rather than elicit a partial factual answer.

**Inferred — longer-term aspiration:** a larger approved relation/operator algebra, with explicit temporal scopes, projections and coverage obligations, enabling combinations without adding a family for each topology. This is bounded closure over approved operators, not unrestricted NLQ. Generic historical joins, grouped analytics and scoped negative queries become candidates only when user priority and evidence completeness justify their additional semantics.

## 4. Assessment of the current architecture

### 4.1 Strengths, defects and architectural ceilings

| Component | Observed evidence | Inferred assessment / what does not follow |
|---|---|---|
| Deterministic interpretation | `N/composable_plan.py::_execute_question`, `N/interpretation.py`, Stage A/B/C parsers; S3 A1/A3, D6, E1/E3 execute without model calls. | Efficient and repeatable on recognised forms; brittle span/scope recognition is local implementation work, not proof deterministic interpretation should be removed. |
| AI-assisted interpretation | `N/composable_semantic_planner.py::build_composable_planner_instructions`, `::validate_composable_plan_draft`; IRI-free strict drafts. S3 B2/E2 converge with deterministic controls. | Useful language mediation exists. One-call model proposals do not establish complete intent or evidence adequacy. Graph-authoring burden plausibly contributes malformed drafts, but constructors have not been comparatively validated. |
| Discovery / selection / routing | Contract catalogue, draft family/selector enums, prompt guidance, adapters and executor branches differ; `/capabilities` is relation-based. Current prompt filters generic selectors to schema-admissible IDs. | A2 is a real exposure gap; registration and truthful operation-level advertising can be improved within A. Sponsorship has a working separate graph route: it is not wholly unreachable. A recognised evidence failure must not be retried into a guessed factual answer. |
| Semantic draft / canonical plan | Closed union of graph roles/capability inputs; final typed referents/relations/constraints/selectors; some canonical adapters; `N/composable_plan.py::complete_v2_plan`. | A structured graph is useful but the envelope is not a general executable language. Model schema, Python validators and final JSON Schema do not admit identical inventories. Adding fields alone does not create execution semantics. |
| Validation / complete intent | Exact-edge and family projection checks; grounded mention/ordinal checks and lexical whole-question gates; C2 selected correctly but rejected by original wording. | Compatibility, source-intent completeness and evidence validity are different obligations. Local lexical false negatives can be fixed within A; replacing all English guards with a trustworthy semantic admission mechanism remains an unresolved cross-option problem. |
| Family versus shared compilation | `N/composable_plan.py::compile_member_relationship_composition_query`, reviewed pattern/graph mappings and family executors. D7/D8 execute multi-path selections. | Existing core is more than templates, but there is no universal v2 compiler. Closed shapes, exact admission and family execution are the real compositional ceiling. New combinations require B or C, not just better language prompts. |
| Identity / temporal evaluation | `N/member_resolution.py::resolve_local_entity_label`, House-date selectors, `_mapped_member_interval`, `_common_interval_intersection`; S3 B3/B4 exact occurrence distinction, D1–D7 checked interval fidelity. | Preserve exact identity and relationship-specific intervals. Reusable helpers do not imply interchangeable temporal meanings. Shared current-scope classifier adds a present-passive false negative; shared code is not automatically correct. |
| Evidence / count / projection | `N/pagination.py::select_pages`; caps/partial policies vary by family. S3 D5/D6 count/list agree; D8 has correct checked identity/intersection but wrong term text. | Correctness includes every explanation assertion. D8 is a stale-variable defect, not a limitation of SPARQL expressiveness. Generic aggregation must retain evidence validation and coverage obligations, not just count returned rows. |

Sources: Stage 1 §§2–7; Stage 2 §§2–6; Stage 4 §§2–8; current `N/office_representation.py::validate_request/execute_office_representation`, `N/interpretation.py::current_relationship_scope`, `N/composable_plan.py::_temporal_member_party_result` (raw-row `term_iri` at line 5249; later evidence assembly at 5365).

### 4.2 What can change without choosing a new architecture?

**Inferred:** A2 exposure/registration, C2 passive admission/scope classification, D8 row-local metadata assembly, final-schema omissions and misleading capability labels are bounded defects/inconsistencies. Fixing them does not require a general operator compiler. It does require preserving complete-intent and evidence-negative controls; simply broadening regexes or dropping guards is not sufficient verification. Stage 4's causal findings already settle their local causes; no repeat of Stage 3 is needed to decide that.

**Observed — static:** Stage 4 §3 identifies absent or rejected three-term intersections, committee+party combinations and party+constituency counts. The final envelope can store more graph material than executors admit; that is not an executable fallback. The draft lacks a general Boolean tree, stage bindings and computed-projection language. **Inferred:** A cannot provide these combinations merely through discoverability/canonicalisation. B can add controlled closure; C changes the admitted/executable language more fundamentally.

**Observed — static:** separate semantic-v1 supports some filters/grouped projections but has narrower temporal compilation and no default-browser handoff; optional Phase 1 directly generates SPARQL. **Inferred:** neither is evidence that default v2 already supplies a general query compiler. A C design should examine v1's reusable implementation and role/temporal limitations, not claim an untested migration is already solved (`N/plan_sparql.py`, Stage 2 §4).

### 4.3 Safety and evidence invariants across every option

**Inferred — non-negotiable assessment requirements, grounded in current contracts:**

- Local authoritative resolution, exact identity joins, reviewed relation/type/owner patterns, no model-controlled graph/IRI construction.
- Read-only SELECT/ASK and existing predicate/query bounds; no automatic Phase 1 downgrade. `N/safety.py::validate_sparql` is a security/resource boundary, **not** proof of faithful question interpretation.
- Explicit distinction among term selectors, active points, overlap, strict chronology and common intersection. Unknown dates/identities do not become positive or negative facts.
- Complete bounded enumeration where completeness is required, preserving existing stricter refusal policies; qualified partial results only under approved family rules. Query pagination completeness is not source-world completeness.
- Row-bound evidence and explanation accuracy, not only final entity/count equality. A valid answer may disclose incomplete local coverage; it may not conceal uncertain selection under a complete-looking total.
- Preserve original question, proposal, rejection reason, canonical/resolved plan, effective date, compiled/evidence queries, raw results and projection provenance for evaluation. Current truncated debug/one-SPARQL-field traces are not complete telemetry.

These are assessment constraints, not permission to modify production logging, publication or existing semantic acceptance. Source coverage, operator preconditions and admission completeness need separate proofs/checks; none is implied by OWL consistency alone.

## 5. Comparative architectural options matrix

### 5.1 Distinct options, not three names for hardening

- **A — Retain/harden:** align operation discovery, schemas/adapters, admission and projection policies; canonicalise existing shapes while retaining family-specific compilation. No new compositional closure is promised.
- **B — Extend within v2:** expose reusable approved semantic operations and explicitly allowed combinations, with typed inputs/temporal/evidence obligations lowered into existing v2 plans/executors. A new combination should reuse operators, not merely acquire another question-specific family. The two proposed additions in §3 test whether that distinction is real.
- **C — Constrained compositional IR/compiler:** a versioned query language with typed roles, approved relations, bounded conjunction/identity-set operations, explicit temporal scopes, filters and projections; deterministic lowering/execution with evidence/coverage obligations. Unimplemented operators remain rejected. Existing resolvers, graph mappings, evaluators and even family backends may be retained. C need not be a SPARQL-only engine or a rewrite of the data model.

All comparative advantages below are **Inferred** unless tied to observed current evidence; proposed benefits are **Hypothesis**, not results from experimental implementations.

| Criterion | A: retain/harden | B: bounded composition in v2 | C: constrained IR/compiler |
|---|---|---|---|
| Natural-language reachability | Can expose seats and normalise passive/ordinal forms; known causal gaps support this. Closed coverage remains. | Same access gains, potentially simpler operation proposals. **Hypothesis:** fewer graph-authoring failures. New combinations still need full-intent admission. | Broader representable requests; **Hypothesis:** ordinary English maps more easily to reusable operators. No evidence that broader syntax improves interpretation accuracy. |
| Complete intent / safety | Existing lexical guards retained and improved; lowest immediate migration risk, continued false-negative burden. No proof they catch every omission. | Explicit combination obligations help checking; omitted operation/qualifier can still yield a perfectly valid weaker plan. Constructors cannot recover missing intent. | Can express an obligation more precisely, but cannot prove the NL parser extracted it. Greater language increases attack/error surface; needs independently tested admission plus deterministic operator/precondition checks. |
| Compositional expressiveness | Existing shapes only. Does not meet proposed new-combination target alone. | Controlled new combinations; plausible fit for two prioritised additions without general Boolean/aggregate algebra. Danger of family enumeration disguised as operations. | Best potential fit for broad bounded closure; joins, filters, time and projection can vary independently where legally defined. Not all combinations are meaningful/allowed. |
| Semantic/factual correctness | Best existing bounded evidence, not complete certification; local defects remain. | Reuse known identity/time evaluation with new obligations and cross-operator tests. Interaction semantics must be reviewed. | Strong type/semantic checking possible; temporal scope, existential witnesses, deduplication and unknown handling must be re-established. Static correctness of IR is not source completeness. |
| Evidence / explanation integrity | D8 fix and projection-policy alignment feasible; family-dependent evidence remains. | Could share evidence-carrying selection/projection; **Hypothesis:** less duplication. Must preserve episode witnesses across each combination. | Can make provenance/coverage part of operator semantics; **Hypothesis:** more compositional explanations. Wrong lowering/association can reproduce D8 in a new framework. |
| Initial development / maintenance | Lowest structural investment; continuing coordinated family edits and lexical maintenance. | Medium expected investment and interaction testing; risk of accumulating an implicit second IR around v2. | Highest initial specification/compiler/test investment; possible lower marginal cost only after useful closure is established. No measured break-even point. |
| Cost of a new semantic combination | Generally new reviewed shape/adapters/validation/projection work; cheap if it already matches a family. | Expected lower for combinations inside a small operation grammar; expensive at its boundaries. Must measure rather than count operator names. | Expected low **inside the implemented algebra**, potentially high for a new primitive/coverage rule. Grammar expansion is not free. |
| Ontology / query infrastructure | Directly compatible with current patterns, owners and endpoint. | Compatible if lowering preserves existing contracts; no ontology change needed for proposed candidates. | Compatible in principle through approved relation/owner mappings and existing Fuseki. Cannot bypass current safety restrictions via hidden subqueries/property paths or require new data semantics silently. |
| Migration / regression | Lowest representational disruption; hardening can still alter route/default behaviour. | Can route a small approved subset and compare old/new execution. Dual-path drift and unclear operator ownership are material risks. | Versioned coexistence and differential evidence tests needed; highest regression scope. Retaining backends reduces but does not erase the risk. |
| Fit to next target / longer term | Adequate only if humans choose a curated existing-operation product. | Provisional best fit for a small, explicit expansion; not proven sustainable. | More defensible if users require broad recombination and comparative extension economics support it. Premature as a final choice now. |

### 5.2 Concrete discriminators

| Example | A | B | C / evidence limit |
|---|---|---|---|
| “How many seats did the 34th Dáil have?” / current Finance passive paraphrase | Can fix access to existing semantics; no new compiler justified. | No extra expressiveness needed. | A new IR adds no necessary capability for these failures. Stage 4 supplies the causal evidence already. |
| Count current Sinn Féin TDs for Dublin Central | Existing named-party list and unfiltered count do **not** admit this combination. | Candidate selection→count reuse, with identity/temporal/evidence parity. | Generic count over an evidence-valid selection is plausible. Both B/C predictions untested; no count or approved extension is asserted here. |
| Current members of a named committee who currently belong to a named party | No admitted combined shape. | Candidate exact-Member intersection with independently current committee incarnation/membership, containing parliamentary membership and party episode. | Typed conjunction could represent it; same witness/date/coverage obligations remain. Actual positive evidence must be independently established before testing. |
| Membership in three numbered Dáil terms | No admitted draft/executor route. | May reveal whether reusable conjunction really replaces fixed two-term topology. | Expected IR expressiveness advantage; not evidence of user demand or of cheaper implementation. |
| “Never served in the Dáil” / “held office throughout the year” | Correctly outside the corresponding existing positive/overlap capabilities. | Must remain outside unless separately reviewed. | An IR can encode NOT or throughout, but missing coverage/semantic authority still prevents a factual answer. More syntax is not more knowledge. |

**Inferred:** no alternative should receive a correctness advantage simply for having a cleaner representation. B versus C is principally a trade-off between a bounded combination language that reuses known execution and a larger explicit algebra with more up-front proof/test obligations. Complete-intent admission is a shared unresolved dependency, not C's automatic benefit or A's solved property.

## 6. Critical evaluation of later-stage AI assistance

### 6.1 Why a second AI judgement is not semantic authority

**Observed — historical:** prior semantic-completeness/verifier studies are recorded in `R/semantic-completeness-tranche-2.md`; they include well-typed incomplete plans and attempts to account for requirements through obligations, audits and verification. These are not fresh current-HEAD factual-answer measurements. Their detailed outcomes and implications are distinguished below.

| Prior study | Observed retained result | What it establishes / does not establish |
|---|---|---|
| Static completeness diagnostics | 0/7 supported admitted by the existing whole-question gate; 13/13 deliberately lossy proposals passed weak necessary checks, 0/13 full validation; no model calls. | Structural compatibility can miss material omissions. Constructed passes are not a model/verifier error rate. |
| Candidate-visible live verifier | Eight supported questions, two observations: existing gate 0/8 both times; structured interpretation+self-audit 2/8 then 0/8; with verifier 0/8 both times. 10/10 deliberately incomplete well-typed candidates passed necessary checks by design. | Tested verifier did not supply useful complete-gate admission. It semantically flagged 20/20 injection observations, but every one of 60 verifier outputs had an exact-quote-check failure. Diagnostic detection is not successful safe/flexible admission. |
| Blind reconstruction/verifier | Six supported and six adversarial questions, three observations: self-audit 11/18 supported runs admitted; verifier 10/18; both 0/18 natural unsafe admissions. All 18 injected omissions escaped the self-audit arm; only 8/18 blind comparisons received valid relevant detection credit. | No demonstrated natural safety rescue; universal refusal of injections is not universal valid omission detection. Only three of six supported questions admitted consistently. Tested approach failed its own criteria. |
| Current Tranche 2 office-period diagnostic | Fixed candidates on 12 questions: existing guard 4/6 supported admitted, 0/6 lossy negatives; schema+exact-mentions comparator 6/6 supported but also 6/6 lossy negatives admitted. | Concrete reachability/safety trade-off in one current family, not observed model error frequency or a live answer study. |

Historical source paths (read-only historical evidence, not imported code): at Git revision `d2962a6`, `R/semantic-completeness-experiment/README.md`, `R/semantic-completeness-live-study/README.md`, and `R/semantic-completeness-blind-study/README.md`, with their frozen cases/protocols/reviews. The live population froze at `1c72e7c`, the blind one at `79867c7`; questions were independently **AI-authored**, not collected from human researchers. These were other-branch shadow admission studies without factual `/ask` execution. `R/semantic-completeness-tranche-2.md` §§“Demonstrated interpretation and admission boundary”, “Part B”, and “Existing experiments reused” preserve the current assessment; its linked probe contains the office diagnostic.

**Observed — contrary historical evidence:** the separate semantic-dispatch campaign on the unmerged implementation (`1e97ae4`, not an ancestor of the Stage 5 baseline) scored 6/38 factual acceptance passes and was not accepted; it also exposed projection/candidate-preservation faults. Its gains and failures are not current-master results (`R/semantic-dispatch-interpretation.md` at `d2962a6`; external review §5.3). Thus neither “all historical failures were safe refusals” nor “a canonical-selection rewrite already succeeded” is supported.

**Inferred:** deterministic compatibility can prove that a plan belongs to an approved language, not that it is equivalent to the question. A model-produced obligation ledger may omit the same qualifier as the model-produced plan. A second model can make correlated errors; agreement is evidence to evaluate, not proof of completeness. An independently authored oracle and adversarial incomplete-candidate controls remain necessary.

| Possible assistance | Plausible benefit (**Hypothesis**) | Authority boundary / unresolved risk |
|---|---|---|
| Admission review after a rejected draft | Distinguish passive/ordinal paraphrases from genuinely extra conditions; reduce false refusals. | A “complete” verdict must not override a failed identity, evidence, temporal or unrepresented-condition gate. Any replacement of lexical completeness checks requires comparative negative-control evidence, not an extra approval bit. |
| Missing/altered-requirement detection | Compare original question with explicit selection, scope, measure and projection; flag dropped party/date/exclusion. | Must test injected omissions independently of the planner. Source spans establish grounding, not that all intent was extracted or correctly scoped. Unknown ⇒ refusal/clarification. |
| Bounded repair | Repair malformed structure or a missing reviewed edge while preserving the original question, rejection and candidate history; at most one candidate repair in the proposed study. | Must not delete a requested condition, change current↔historical/term-wide meanings, choose identities, widen the admitted language or fabricate evidence. Same deterministic checks apply again; no fallthrough to Phase 1. |
| Operator selection/composition | Select a small set of approved operations with typed arguments; local code may construct canonical plans. | Reduces graph boilerplate only if construction is correct and complete inputs exist. New expressive power comes from an approved operation language and executor, not from later model verification. |

**Inferred:** AI-assisted admission/repair can improve **access** to existing operations. It contributes to **genuine composition** only when B/C already represents, validates and executes the requested operator combination. It cannot make the unsupported committee+party or party+constituency count combination safe by approving today's weaker plan.

**Hypothesis:** local canonical plan construction reduces malformed-graph/omitted-edge failures. **Unknown:** net supported-question gain, residual omission detection, latency/cost and correlated planner/verifier failure. It is a useful hypothesis for a small paired study, not justification for removing safeguards or replacing all model graph routes now.

### 6.2 Implication of prior failures

**Inferred:** retain the safeguards unless a concrete scoped replacement both admits supported unfamiliar language and rejects material omissions. Prior studies reject the tested self-audit/span/agreement mechanisms, **not AI assistance universally**. Repeating them with new wording and scoring every refusal as safe semantic detection would not distinguish a new architectural hypothesis. A later study must isolate where completeness comes from, test independently injected candidates and count false refusals as lost capability. No new verifier study was executed in Stage 5.

## 7. Recommended direction and reasoning

**Inferred — recommendation:** approve the **bounded-composition target and deterministic-core preservation** as decision principles; adopt **B as a provisional design preference**, conditional on the narrow evidence gates in §8. Do not approve a wholesale C migration or an open-ended “harden everything first” programme.

Reasons, in order:

1. **User value:** actual human Q9 requires meaningful semantic composition already. The next increment should improve dependable access and a small explicitly approved expansion, not promise a universal research language. Committee+party and broader analytics remain demand hypotheses requiring confirmation.
2. **Observed execution assets:** exact identities, term occurrence handling, independent current intervals, common intersections and count/list parity have useful positive evidence. Retention is justified by behaviour, not sunk cost. D8 and stopped oracle facets prevent treating the core as fully certified.
3. **Known causes:** A2/C2/D8 are not a case for replacement. They identify bounded defects and safety/evidence obligations any replacement inherits.
4. **Real ceiling:** A's family hardening does not deliver a new approved combination. B is meaningful only if reusable operations reduce the need for a fresh topology-specific path. A constructor-only programme must be called A/access improvement, not B/compositional success.
5. **Unsettled economics:** current history demonstrates both cheap reuse and costly cross-layer changes. A general IR may pay off, but neither the required scale nor break-even cost has been established. B gets only a bounded evaluation budget, not indefinite preference.
6. **Independent safety gap:** no available evidence establishes reliable AI-only completeness admission. C could improve representation and still fail the same language-safety problem. Choose neither architecture by supported-answer rate alone.

**Inferred — decision boundary:** if humans want only reliable access to current curated operations, choose A explicitly and do not fund a composition compiler. If they require the limited target in §3, compare B/C on that target without first requiring a whole-system A overhaul. If they require broad lawful recombination, C becomes the stronger design candidate, but still needs admission/evidence tests. Failure of an AI admission study does not automatically favour C; it may require a smaller language or user clarification/confirmation instead.

**Unknown:** a final B/C selection on cost, maintenance or independently safe NL reachability. The defensible outcome now is a scoped architectural preference plus a discriminating gate, not a claim that alternatives were implemented or experimentally validated.

## 8. Required experiments and explicit decision criteria

**Proposed only — none executed or authorised by this report.** The numbers below are small screening gates proposed for human approval, not statistically justified production reliability targets. A zero observed unsafe-admission count does not prove a zero population rate. Stop on unclear semantics, missing positive evidence or contradictory oracles; do not reinterpret a failed request to populate a positive cell.

### 8.1 Reuse accepted evidence; do not repeat settled causes

**Observed — reusable evidence:** S3 B1/B2 and E1/E2 cross-route agreement; C1 repeated chain; D1–D7 parameter/scope/filter/count/OR controls; C3/E5 evidence nonanswers; C4/E4 supported-language boundaries; D8 annotation failure and Stage 4 counterfactuals. Carry their provenance and stopped facets forward. They are development/regression controls, **not a fresh holdout**. No new A2 sampling is required to establish its absent schema route; no repeat is needed to re-localise C2 or D8.

For any later current-revision comparison, freeze source/configuration/provider, as-of date and dataset/capture identity; preserve complete query-relevant typed evidence and all proposals/rejections/queries/projections. If a complete snapshot is unavailable, limit conclusions to stable captured selections and do not certify global completeness. Independent oracles must include unlabelled candidates, typed ranges/endpoints/conflicts and actual role/primary predicates where relevant. Never fix source fixtures or expected answers to make an implementation pass.

### 8.2 Gate L — access and complete-intent admission, not expressiveness

**Competing hypotheses:**

- **L1:** operation/argument proposals plus local canonical construction materially improve access to current semantics without reducing omission rejection.
- **L2:** graph construction is not the dominant remaining limit; original-English admission or scope interpretation dominates, so constructors alone do not deliver safe reachability.
- **L3:** later AI completeness checking can reject independently injected incomplete candidates while admitting supported paraphrases; prior poor results may persist instead.

**Smallest useful design:** select **two existing operations** with different construction burdens (e.g. current officeholder→constituency and historical party/representation). Freeze **12 new supported paraphrases** (six per operation) and **12 paired material-alteration/omission controls**, independently authored and checked against current contracts before any provider response. Include passive/ordinal variants, term-wide versus current-point meaning, extra party/date/exclusion/answer fields and unknown scope. Verify positive RDF support independently; distinguish supported-but-evidence-unavailable cases from the answerable denominator.

Use an author/custodian separate from the candidate implementer and planner/verifier contexts, with access to approved contracts but not candidate responses. Retain whether authorship is human or AI-assisted; separate contexts are not statistical independence. An independent reviewer adjudicates supported meaning and omission materiality **before** responses, and freezes the questions, candidate mutations and oracle hashes. No post-outcome denominator changes.

Compare unchanged current draft/admission with a constructor candidate **holding the semantic contract fixed**. Record fixed-candidate admission as well as real language-to-plan results so malformed construction, model selection and completeness checking are separable. Repeat each question three times with the same pinned settings. Retain Stage 3 controls as a separate regression stratum, not pooled with the 12 fresh positives.

**AI verifier arm:** only after a concrete design change explains why it might avoid the historical failure mode. Use the **same independently injected incomplete candidates**, including ones the planner did not generate, and show original question plus candidate without the oracle verdict. Evaluate in shadow first; no verifier decision may execute an otherwise rejected plan. A self-authored checklist or self-audit replay without a new independent completeness test is not a discriminating experiment.

**Proposed acceptance/rejection:**

- Zero materially incomplete/altered candidates admitted across all scheduled observations; any such admission rejects the candidate as an admission replacement.
- At least **11/12** supported paraphrases admitted in **every** repeat, at least **two more than baseline** (if baseline already meets 11/12, no demonstrated reachability need for replacement on this slice).
- Every admitted answer matches independent identities, scopes, counts and *all* scored evidence assertions; no established regression-control deterioration.
- Report supported admission /12 and per observation; unsafe admission /12 and per observation; correct answers /all admitted and /evidence-backed supported requests; all-repeat-correct fraction; selection/admission/constructor failures separately. Record provider errors, cost and latency, without relabelling them semantic failures or excluding them silently.
- For a repair arm, predeclare **one** repair maximum; require the same safety/correctness gates and at least two additional all-repeat supported successes over the no-repair candidate. No benefit or any semantic weakening ⇒ reject repair for that scope.

**Decision effect:** success supports a bounded access/construction change, **not compositional closure**. A failed verifier arm retains deterministic completeness safeguards. Poor admission does not distinguish B from C unless it is caused by their different representational interfaces.

### 8.3 Gate X — B versus C on extension economics and real composition

**Competing hypotheses:**

- **X1:** a small v2 operation grammar delivers the approved next combinations with less total work/risk than a more general IR.
- **X2:** fixed v2 shape/validator/executor boundaries force repeated cross-layer edits; a constrained IR amortises its design cost even over a small approved expansion.

Do **not** prototype every ontology relation. After humans approve the candidate semantics, use a matched, disposable **two-combination** comparison: (i) party+constituency selection→distinct-Member count; (ii) current committee+party exact-Member intersection. Existing evidence machinery may be shared in both arms. The C arm implements only the approved minimal algebra, not arbitrary negation/grouping. A's inability to admit these combinations is settled statically; no A prototype is needed.

Freeze **six evidence-backed positives per combination** covering entity/term substitutions and ordinary phrasing, plus **12 negative controls** in total, independently checked before either design is evaluated: six semantic omission/unsupported-condition candidates and six invalid/insufficient-evidence cases. Include a missing party/date/extra condition and unsupported global absence in the former; mismatched containing membership, unknown/conflicting interval, wrong term occurrence and truncated evidence in the latter. An evidence-negative may have a valid admitted plan but must not produce an unjustified factual result; do not count such plan admission as unsafe semantic admission. A dataset with no independently verified positive committee+party case stops that facet; empty results are not positive controls. Approved adversarial test inputs must not alter protected fixtures or real source data.

Test operator execution first with independently specified semantic inputs, then NL admission separately. Use three NL observations per question; deterministic execution must also be invariant to input row order/duplicates for equivalent evidence, with exact provenance witnesses checked. Use existing controls to ensure old meanings are not relabelled. Distinguish query enumeration completeness from real-world roster completeness.

**Pre-register the reuse rubric:** before either arm is built, an independent reviewer defines and freezes what counts as an operation primitive versus a topology-specific case. Hardcoded combination/family dispatch, per-combination graph-role unions, special-case lowering and combination-specific evidence assemblers count as topology-specific, even if renamed “operators”. A parameterised relation/temporal/projection primitive must state its reusable input/evidence contract and pass more than one approved combination without such a case. Do not decide that classification after seeing which arm wins.

**Extension-cost measurement:** make retained structural/change evidence primary: changed production semantic units/layers/files, new family/topology branches, test/oracle work, independent review cycles, unresolved semantics and defects. Pre-register a primary structural-change proxy and its counting rubric/weights before building (e.g. separately identifiable operation definitions, validator/compiler cases, executor branches and evidence assemblers created/changed per phase); report its components, not just a composite score. Engineering/review elapsed time and AI token/call cost are secondary, not interchangeable with human effort. Count initial grammar/compiler cost **and** marginal extension cost; do not compare a full C setup with only B's final small edit, or exclude shared review/testing costs selectively. Freeze each candidate before revealing one additional approved combination (e.g. three-term intersection if accepted as a diagnostic). An independent custodian should freeze its exact scope and oracle; the example here is not itself a secret holdout.

**Proposed acceptance and decision rules:**

1. Both arms must meet **zero unsafe semantic admissions** (report /6 and per observation), zero unjustified factual results on evidence negatives (report /6 and per observation), **100% correctness of returned scored answers/evidence**, no existing-control regression, and at least **11/12 fresh positives admitted correctly in all three observations**. Report correctness both /all returned answers and /12 evidence-backed supported requests, plus all-repeat-correct fraction. Fixed-semantic-input positives must all execute correctly. Any failure disqualifies promotion pending review; never average safety failures against additional answers.
2. **Prefer B for the next increment** if it passes, its pre-registered primary structural-change proxy and other primary cost dimensions are no worse than C's across build+verification+withheld extension, and at least one new combination reuses operations without a new topology-specific compiler/executor/projection branch under the frozen rubric. Constructors alone do not satisfy this criterion.
3. **Prefer C for a bounded migration design** if it passes, B either requires new topology-specific paths for every tested combination or fails the agreed target, and C demonstrates either at least **25% lower primary structural-change proxy** with no worse other primary cost dimensions, or a human-approved extra initial cost justified by the withheld extension needing no new compiler/validator/projection case. Report sensitivity to counting/weights and keep actual labour cost **Unknown** where not measurable. The percentage is a proposed proxy materiality threshold, not an observed saving or a promise of lower lifetime maintenance cost.
4. If both pass but cost/extension differences are smaller or inconclusive, retain the smaller deployed surface and defer permanent selection; do not manufacture a winner from tiny samples. If neither passes admission but deterministic composition works, investigate the language/admission boundary or a clarified structured interaction, not a compiler replacement by default.

**Decision effect:** only this gate tests genuine new semantic combinations and extension cost. Gate L and Gate X can be scoped independently; an exhaustive system-wide hardening programme is not a prerequisite. Human demand/semantic approval precedes both; no experiment expands current contracts by implication.

## 9. Risks, rejected alternatives and unresolved decisions

| Risk / alternative | Assessment and disposition |
|---|---|
| Removing lexical guards because they reject paraphrases | **Rejected on present evidence.** Compatibility alone can admit a weaker valid plan. Replace only a demonstrably redundant check or an independently validated scoped mechanism, never remove complete-intent protection wholesale. |
| Direct LLM-generated SPARQL as primary authority | **Inferred — reject as recommended replacement**, not a proof it can never answer correctly. Optional Phase 1 establishes existence, not superior complete-intent/temporal/provenance reliability. Predicate/read-only safety cannot detect a dropped party or wrong time scope. Equivalent deterministic protections would recreate much of the constrained compiler's burden. |
| Flat capability catalogue as complete solution | **Inferred — insufficient for the proposed target.** Useful for access, but does not supply combination semantics or avoid new-family proliferation. |
| General IR now, justified by historical low scores | **Deferred.** Old source/configuration populations and safe nonanswers do not isolate representation cost. C may still win when demand/extension evidence exists; sunk cost is not a veto. |
| Canonical constructors treated as semantic proof | **Hypothesis only.** They reduce boilerplate if inputs are complete; a perfectly constructed weaker plan remains unsafe. |
| Generic negation or absence under incomplete data | **Deferred.** Local nonmatch cannot certify “never”, no holder, a complete zero or roster complement. Needs scoped coverage authority, not an ontology redesign by default. |
| B becoming a hidden new IR plus old families | **Material risk.** Require explicit operator semantics and measured extension reuse; otherwise reconsider C rather than indefinitely adding adapters. |
| C flattening temporal/provenance distinctions | **Material risk.** Keep relationship-specific witnesses, interval and coverage obligations through lowering and projection; no universal “current” shortcut. |
| Data gaps confused with compiler inability | **Observed risk:** C3/E5. Preserve evidence-unavailable outcomes; do not infer vacancy/zero or fund a new compiler to manufacture missing facts. |
| Evaluation leakage / correlated AI oracles | **Observed provenance limitation.** Known Stage 3 and historical cases are regression evidence only. Freeze independent questions/oracles; label AI-authored versus human-origin evidence and adjudicate admissibility before outcomes. |
| Evidence text dismissed as cosmetic | **Rejected.** D8 attaches another person's term to qualifying evidence. Every factual explanation assertion is part of correctness. UI consistency/IRI placement is a human presentation choice, not permission to lose provenance. |
| Production safety inferred from small zero-error samples | **Rejected.** Screening gates do not estimate rare unsafe admission; production risk budget and monitoring/escalation remain human decisions. |

**Unknown / human judgement needed:** acceptable product coverage and refusal rate, which proposed new combinations deserve priority, office-duration expectations under incomplete records, evidence/IRI presentation, latency/cost budget for another AI call, and what independent completeness evidence would justify retiring a specific lexical guard. There is no demonstrated contradiction requiring ontology or RDF ownership changes.

## 10. Proposed architecture decision record / human approval points

**Status: Proposed for review; no decision enacted.** This section is a candidate ADR decision set, not a replacement for the existing proposed semantic-dispatch document or an approval to implement it.

| Decision point | Proposed disposition | Evidence / approval required |
|---|---|---|
| D1 — Product generalisation level | Approve §3's bounded researcher-facing target; choose explicitly between current curated operations only and the proposed small composition expansion. | Human product judgement; human Q9 supports composition, not unrestricted closure. Confirm demand for the two candidate additions. |
| D2 — Invariants | Preserve deterministic resolution, reviewed relation/owner mappings, compilation/safety, temporal/evidence validation and no silent intent loss; explanations count as factual output. | Sufficiently supported for approval by contracts and observed controls/failures. No ontology/mapping/publication changes. |
| D3 — Architecture direction | B is provisional preference for the limited target; C remains a live alternative. A is the explicit choice if expansion is not wanted. No final B/C selection yet. | Approve bounded Gate X scope/budget and criteria; do not condition C consideration on completing every A improvement. |
| D4 — Admission / later AI | No AI authority over identities, evidence validity or completeness; no wholesale guard removal. Canonical construction and optional verifier/repair are separate hypotheses. | Approve Gate L only with a concrete difference from failed prior studies, independent positives/omissions and agreed zero-unsafe screening gate. |
| D5 — New semantics | Review count unit/coverage and independent temporal witnesses for each proposed combination before testing or implementation. Leave global negation, arbitrary interval algebra and office duration deferred. | Explicit semantic/query-contract approval; this report changes none. |
| D6 — Evidence acceptance | Preserve Stage 3 checked facets without promoting stopped facets to passes. Require stronger independent role/type/conflict/coverage checks for any new certification. | Human acceptance of retained-evidence limits and proposed future oracle scope. |
| D7 — Migration / presentation / operational budget | If a candidate wins, require a separate bounded implementation/migration plan, versioned compatibility/regression checks and an evidence-display policy. | Human approval of effort/latency/risk thresholds and IRI/evidence presentation; no migration or production change authorised now. |

**Inferred — approval-ready principles:** D2, rejection of unrestricted LLM authority and separation of admission/expressiveness are supported. **Provisional preferences:** B, canonical-input construction and shared evidence-carrying projection. **Deferred final judgement:** B/C economics and replacement of completeness admission. Human approval of this report alone should not be construed as approval of all candidate semantics or follow-on work.

## 11. Stage 5 exit-criteria assessment

| Exit criterion | Assessment |
|---|---|
| Desired generalisation target explicitly defined | **Met as a proposal:** next increment, longer term, actual-human versus inferred demand and boundaries distinguished in §3. Human scope approval outstanding. |
| Options compared against target | **Met:** A/B/C and direct-generation comparison, including costs, safety, evidence and regression risks; predictions labelled. |
| Complete intent and composition evaluated separately | **Met:** §§1, 4–8; separate Gate L versus Gate X. |
| Deterministic strengths / safeguards preserved | **Met in assessment:** no relaxation or semantic changes; D8 prevents overclaiming post-plan correctness. |
| Recommendations distinguished from facts | **Met:** Observed, Inferred, Hypothesis and Unknown used with revision/provenance limits. |
| Necessary further evidence has objectives / criteria | **Met as proposed protocols:** scoped hypotheses, independent positive/negative controls, correctness/admission/repeatability measures, **bounded-scope comparative cost proxies only**, and explicit rejection/decision rules. None executed; no lifetime-cost conclusion warranted. |
| Decisions requiring human approval identified | **Met:** §10; final B/C selection explicitly outstanding. |
| Report-only boundary | **Met:** only this report is to be added; no implementation, refactoring, new experiments, contracts, fixtures or production data changed. |

### Verification and disposition

**Observed — Stage 5 checks:** correct clean starting checkout and full SHA recorded; fetched remote aligned; Stage 4→baseline code reconciliation completed; external review identity verified; 48 Stage 3 manifest files, seven baseline pins and 30 retained responses checked. Independent read-only review found no blocking issue and checked provenance/quantitative claims; its suggested denominator, authorship and pre-registered cost/reuse-rubric clarifications are incorporated. Document references and report-only diff are verified before persistence; clean-tree statements describe the starting checkout, before adding this report. Runtime/ontology validation and pytest are **not run** for this documentation-only task; no current-runtime correctness or suite pass is claimed.

**Disposition:** Stage 5 architectural evaluation is complete for human/ChatGPT review. The evidence supports preserving the deterministic core and making a bounded B-versus-C decision, not claiming either alternative has been validated. Required next actions are **human decisions**, followed only by separately authorised scoped work. **Stopped after Stage 5: no implementation or follow-on experiment begun.**
