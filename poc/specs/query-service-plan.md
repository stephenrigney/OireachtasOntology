# Query Service Roadmap

## 1. Objective

Develop the current natural-language-to-SPARQL proof of concept into a reliable
query service over the Oireachtas RDF dataset, with a later path to controlled
federated querying of Wikidata and other linked-data sources.

The immediate goal is not a polished user interface. During development the
service should continue to expose its interpretation, query plan and generated
SPARQL so that failures can be diagnosed directly.

The roadmap deliberately separates:

1. local Oireachtas query quality;
2. query interpretation and planning;
3. source selection and provenance;
4. controlled external querying;
5. service extraction from this repository; and
6. later SPARQL federation.

The current implementation remains under `poc/nlq/` until the service boundary
is stable enough to extract into a separate repository.

## 2. Current baseline

The proof of concept currently provides:

- a natural-language question input;
- repository-schema grounding;
- an LLM translation step using an OpenAI Responses-compatible endpoint;
- read-only SPARQL validation;
- direct querying of the local Fuseki dataset;
- a visible "Understood as" interpretation;
- visible generated SPARQL;
- result rendering and debug information;
- a one-command development launcher under `scripts/dev-nlq.sh`;
- an explicit non-authoritative local bootstrap for Houses, reference owners
  and Members from preserved complete API captures; and
- an explicit prohibition on `SERVICE`, `FROM` and `FROM NAMED` in
  generated queries.

This is a useful development baseline, but it is still a direct translation
architecture:

```text
natural-language question
        |
        v
schema-grounded LLM
        |
        v
SPARQL
        |
        v
local Fuseki
        |
        v
result
```

The main architectural direction of this roadmap is to insert an explicit,
validated query plan and source-selection layer before adding federation.

## 3. Relationship to OireachtasOntology

### 3.1 Why the POC stays here initially

The query service is currently discovering and exercising contracts that are
still close to the ontology and ETL implementation:

- RDF classes and properties;
- graph ownership;
- source identity;
- graph naming;
- external identity links;
- reference-data coverage;
- query-safety rules; and
- competency expectations.

Keeping the proof of concept in this repository allows those assumptions to be
verified and corrected without prematurely creating a cross-repository API.

### 3.2 Intended later split

A production query service should eventually become a separate repository and
deployment unit. Its expected long-term boundary is:

```text
OireachtasOntology
    ontology
    mappings
    ETL
    reconciliation
    validation
    published RDF
    query/schema contract
          |
          v
Query service
    interpretation
    query planning
    source selection
    SPARQL generation
    execution
    federation
    provenance
    API
```

The query service should not permanently depend on importing private
`oireachtas_etl` implementation modules. Before extraction, this repository
must expose a stable machine-readable query/schema contract that a separate
service can consume.

### 3.3 Local PoC reference-data bootstrap contract

`scripts/dev-nlq.sh --load-data` invokes the explicitly named
`oir-etl dev bootstrap` command. This is a development-environment mechanism
for a disposable, loopback Fuseki dataset, not partial production publication.
It reads preserved successful complete API captures, validates and loads
Houses/HouseTerms, Member graphs and valid Party, Independent collection,
constituency/panel and Committee owner descriptions. It does not fetch source
data or write Core State or external-reconciliation state.

The local path reuses the source census and owner transformations, but
materially conflicted identities are quarantined: no observation is selected,
no vote or placeholder is used, the canonical IRI is unchanged, and the
conflicted owner description is omitted. Member references may still point to
that unresolved IRI. The bootstrap reports the conflicted IRIs and reasons,
quarantined-identity and unresolved-reference counts, and always labels
reference closure **NOT authoritative / not complete**.

Authoritative reference publication remains globally fail-closed. A material
conflict in any reference identity still blocks the authoritative candidate set
and does not advance coverage/publication authority. In particular, the known
Committee source conflict at
`https://data.oireachtas.ie/ie/oireachtas/committee/dail/33/select_committee_on_the_implementation_of_the_good_friday_agreement`
still blocks authoritative reference-coverage acceptance. Local development
output must not be described or reused as
authoritative, accepted or production-ready RDF.

## 4. Development principles

### 4.1 Local correctness before federation

Do not use Wikidata or another external source to compensate for gaps or
ambiguity in the local Oireachtas dataset. Local reference coverage, query
quality and source ownership should be understood first.

The historical reference-coverage work for constituencies/panels,
parliamentary collections and committees is therefore an important dependency
for broad local NLQ evaluation, even though it is implemented as ontology/ETL
work rather than in this service.

### 4.2 Make planning explicit before execution becomes federated

The service should not jump directly from:

```text
question -> generated federated SPARQL
```

Instead it should evolve toward:

```text
question
    |
    v
structured interpretation / query plan
    |
    v
source selection
    |
    +--> local Fuseki query
    |
    +--> controlled external query
    |
    v
join / provenance
    |
    v
result
```

This lets the service distinguish:

- what the user asked;
- which entities and relations were inferred;
- which source should answer each part;
- which identifiers join the sources;
- which query was generated for each source; and
- which source supplied each returned fact.

### 4.3 Prefer constrained capability over arbitrary query power

External querying should begin with a small supported set of entity types,
properties and endpoints. Arbitrary generated remote endpoints or arbitrary
`SERVICE` clauses are not an initial federation target.

### 4.4 Keep query formation visible

Until query behaviour is stable, development output should expose at least:

- interpreted intent;
- structured query plan;
- selected source(s);
- generated local SPARQL;
- generated external SPARQL where applicable;
- execution result;
- provenance; and
- validation/debug failures.

A polished UI is deliberately deferred.

### 4.5 Treat evaluation as a product requirement

Every major architectural change should be evaluated against a stable benchmark
rather than judged only from ad-hoc examples.

Failures should be classified rather than treated as a single "bad answer"
category.

Recommended failure classes include:

- question interpretation;
- schema grounding;
- entity resolution;
- temporal interpretation;
- query planning;
- source selection;
- SPARQL generation;
- query safety/validation;
- execution;
- source-data coverage;
- external reconciliation/join;
- remote-source failure; and
- result/provenance composition.

### 4.6 Preserve authority and provenance

The query service must distinguish an Oireachtas fact from an externally
sourced fact.

For example:

- parliamentary membership belongs to authoritative Oireachtas RDF;
- an accepted Oireachtas-to-Wikidata identity link is derived reconciliation;
- place of birth obtained from Wikidata is a Wikidata fact.

Federation must not erase those distinctions.

## 5. Delivery model

Use a phased roadmap with small implementation tranches inside each phase.

The phase defines the architectural milestone. The exact order of backlog items
within a phase may change in response to benchmark evidence.

A tranche should normally:

- have one architectural purpose;
- leave the service runnable;
- have focused automated tests;
- produce evidence needed for the next design decision; and
- avoid combining unrelated architectural changes.

A suitable tranche can usually contain one to three tightly related
capabilities. For example:

```text
structured query-plan schema
+ planner prompt
+ plan validation
+ display alongside generated SPARQL
+ focused tests
```

is a reasonable single tranche.

The following is deliberately too broad for one implementation task:

```text
query planning
+ source selection
+ Wikidata execution
+ federation
+ provenance
+ caching
+ repository extraction
```

The governing rule is:

> Build enough in each tranche to answer the next architectural question.

## 6. Phase 0 — Baseline, contracts and evaluation

### Outcome

Establish a measured local-query baseline and remove accidental dependencies on
ETL implementation details before changing the query architecture.

### Backlog

#### Dataset readiness

- [x] Record which Oireachtas graph families the POC requires for each benchmark
      category.
- [x] Treat historical reference-coverage closure as an external prerequisite
      for benchmark questions that depend on those references.
- [x] Distinguish source-data coverage failures from NLQ failures in all
      evaluation output.
- [x] Define a repeatable local Fuseki test dataset or fixture strategy.

#### Query/schema contract

- [x] Inventory the classes, properties, graph ownership rules and graph
      patterns currently assembled by `poc/nlq/schema.py`.
- [x] Define a versioned, machine-readable query/schema contract rather than
      relying indefinitely on imports from `oireachtas_etl.config`.
- [x] Include named graph families and ownership information in that contract.
- [x] Include externally joinable identity predicates such as reviewed
      Wikidata links where supported.
- [x] Define contract versioning and compatibility rules.

#### Evaluation benchmark

- [x] Create an initial benchmark of approximately 30-50 natural-language
      questions.
- [x] Cover simple lookup, HouseTerm membership, parliamentary collections,
      constituencies/panels, committees, dates, counts, aggregates, joins,
      ambiguous names and unsupported requests.
- [x] Record expected interpretation and expected result or invariant.
- [x] Capture generated SPARQL and actual results.
- [x] Classify each failure using the agreed taxonomy.
- [x] Preserve a regression subset suitable for automated execution.

#### Safety baseline

- [x] Preserve read-only SELECT/ASK enforcement.
- [x] Preserve endpoint-local restrictions on `SERVICE`, `FROM` and
      `FROM NAMED`.
- [x] Record current LIMIT/OFFSET limits and other query-complexity controls.
- [x] Define the safety boundary that later federation must explicitly extend.

Phase 0C records this baseline in `poc/specs/query-schema-contract.json`
(contract `1.0.0`, schema `1`) and
`poc/specs/query-schema-contract.schema.json`. The NLQ grounding path scopes
ontology detail to the contract and no longer imports private
`oireachtas_etl.config` graph constants. Contract-compatible additions may use
the same major; changes to existing graph ownership, query patterns, identity
meaning, reasoning assumptions, or safety capability require a contract major
bump. Consumers reject unsupported schema, contract-major, and local-safety
major versions. The current local safety baseline remains SELECT/ASK only,
without Update, `SERVICE`, `FROM`/`FROM NAMED`, subqueries, variable predicates,
or property paths; exact limits and endpoint caveats are in the artifact and
`poc/nlq/README.md`. Federation remains disabled.

### Exit criteria

- A repeatable benchmark exists.
- Local query failures can be classified consistently.
- The query service has an explicit versioned schema/graph contract.
- No essential POC dependency requires importing arbitrary ETL implementation
  internals.
- The local read-only safety contract is documented and tested.

### Status

Phase 0 is complete and has passed its completion gate. Dataset readiness, the
evaluation benchmark/framework, the query/schema contract, and the local safety
baseline are all complete. The measured local NLQ quality baseline remains
Phase 1 work.

## 7. Phase 1 — Local NLQ quality

### Outcome

Make Fuseki-only natural-language querying reliable enough that later source
selection and federation can be evaluated independently.

### Backlog

#### Benchmark execution

- [x] Run the complete benchmark against a capture-backed Phase 0A
      development dataset.
- [x] Record baseline success rates by question category.
- [x] Record failures separately for interpretation, grounding, entity
      resolution, SPARQL and source coverage.

Phase 1A measured the complete 42-case benchmark against an isolated,
capture-backed Phase 0A development dataset. Results, configuration, coverage
outcomes and diagnostic limitations are recorded in
[`poc/nlq/benchmarks/phase-1a-baseline.md`](../nlq/benchmarks/phase-1a-baseline.md).

Phase 1B corrected benchmark contract and capture-coverage defects without
changing NLQ behavior. The versioned v0.2.0 baseline and the case-by-case
validity decisions are recorded in
[`poc/nlq/benchmarks/phase-1b-baseline.md`](../nlq/benchmarks/phase-1b-baseline.md).

#### Schema grounding

- [x] Remove redundant or misleading schema context.
- [x] Ensure every supported query pattern is grounded in actual emitted RDF,
      not ontology-only possibilities.
- [x] Add concise graph-ownership guidance where cross-graph joins are needed.
- [x] Add targeted examples only where benchmark failures demonstrate value.
- [x] Prevent prompt growth from becoming the default response to every failure.

Phase 1E audit: the translator guidance distinguishes the Member-owned graphs
from HouseTerm and owner graphs and describes their shared-resource joins; the
machine-readable contract and capture-backed v0.3.0 probes cover emitted local
patterns. Phase 1C addressed the measured prefix defect through contract-known
prefix completion, and Phase 1D added local duplicate-name context. The v0.3.0
benchmark has adequate temporal, aggregation, join and ambiguity evidence for
this phase. No redundant context or further prompt change was justified by the
remaining evidence; prompt growth is not the default remedy.

#### Entity resolution

- [x] Measure name-resolution failures independently from query-generation
      failures.
- [x] Support label/code matching appropriate to each local entity type.
- [x] Define behaviour for ambiguous names and multiple historical identities.
- [x] Prefer query-time resolution over manufactured instance IRIs.

Phase 1E audit: the measured result retains failure stage/class and semantic
mismatches separately, while source-data coverage is assessed before NLQ
scoring. Current query patterns use local labels and contract predicates;
deterministic regression queries do not manufacture instance IRIs. This is
sufficient for the benchmarked Phase 1 patterns, not a general label/code
resolver: the local pre-translation Member resolver uses exact names, and
code-driven resolution is not independently benchmarked. Exact duplicate Member
names produce a local clarification outcome with distinct captured candidate
IRIs and contextual narrowing. Broad/set-valued cases remain manual review.
**Context-resolved Member IRIs are not mechanically bound into the generated
answer SPARQL; defer this explicitly to Phase 2 validated structured query
planning/entity binding.** This is an accepted Phase 1 limitation, not a reason
for ad-hoc SPARQL rewriting or broader resolver work here.

#### Temporal and aggregation behaviour

- [x] Add benchmark coverage for "at a date", "during a term", "current",
      counts and grouped results.
- [x] Ensure temporal semantics are explicit rather than inferred from labels.
- [x] Validate aggregate queries and LIMIT behaviour.

Phase 1E audit: benchmark v0.3.0 supplies supported interval/current and term
membership/date evidence, count and grouped-result cases, plus an explicit
manual-review/unsupported HouseTerm start-date case because its temporal link is
not queryable under the current contract. Aggregate shape, result invariants,
and SELECT row limits are covered by safety tests and benchmark execution. This
is sufficient Phase 1 coverage; it does not broaden the schema contract or
claim unsupported temporal predicates.

#### Regression gate

- [x] Promote stable benchmark cases to automated tests where practical.
- [x] Require future planner/federation changes not to regress the agreed local
      baseline without an explicit contract change.

The Phase 1E gate is the deterministic v0.3.0 regression tier and offline
pipeline/safety/entity-resolution tests described in
[`poc/nlq/README.md`](../nlq/README.md) and
[`poc/nlq/benchmarks/phase-1-completion.md`](../nlq/benchmarks/phase-1-completion.md).
Measured full-benchmark LLM runs are diagnostic evidence, not byte-for-byte CI
fixtures; missing source prerequisites stay separately classified as coverage.
Planner/federation work must preserve this local deterministic tier, known-prefix
completion, fail-closed read-only safety, exact duplicate-name ambiguity, and
case-level source-coverage separation unless an explicit contract change is
approved and documented.

### Exit criteria

- Local NLQ quality is measured rather than anecdotal.
- Major failure categories are understood.
- The service can resolve the common supported local entity/query patterns.
- A regression gate exists for subsequent architectural work.

### Phase 1 status

Phase 1 is complete and passes its exit gate as of Phase 1E. The durable audit,
measured v0.3.0 result, known limitations, and regression policy are recorded in
[`poc/nlq/benchmarks/phase-1-completion.md`](../nlq/benchmarks/phase-1-completion.md).
The direct NL-to-SPARQL path remains in place until Phase 2. Mechanical binding
of context-resolved entities is explicitly deferred to Phase 2 query planning.

## 8. Phase 2 — Explicit query planning

### Outcome

Separate question interpretation from executable SPARQL generation.

### Initial plan shape

The initial semantic contract is defined by
[`poc/specs/query-plan-contract.json`](query-plan-contract.json), with its
manifest schema, plan-instance schema, runtime validator, and representative
plans. It is local Oireachtas-only and deliberately contains no SPARQL or graph
implementation details. Source selection remains Phase 3 work.

### Backlog

- [x] Define the versioned query-plan contract and plan JSON Schema.
- [x] Represent entities, requested relations/facts, filters, temporal
      constraints, aggregation, answer shape, and local Oireachtas source scope.
- [x] Represent resolved, ambiguous, and unresolved entity state explicitly.
- [x] Add deterministic contract/plan loading and validation, examples, and
      focused tests.
- [x] Validate model-produced plans before SPARQL generation.
- [x] Split planner and SPARQL-generator responsibilities.
- [x] Generate local SPARQL from the validated plan.
- [ ] Show the plan alongside the interpretation and generated query.
- [x] Compare planned generation against the Phase 1 direct-generation
      baseline.
- [ ] Keep a simple fallback/debug path during migration if useful.

Phase 2A is complete as a contract-only tranche. The artifact and examples are
under `poc/specs/query-plan-*`; `poc.nlq.plan_contract` loads and validates them.
No plan production or validation is connected to the live NLQ path, and no
SPARQL generation is implemented. Facts and filter fields use controlled,
fact-specific semantic identifiers defined by the contract manifest and
mirrored by the plan schema; unknown identifiers fail validation. The current
entity-type vocabulary remains controlled by the artifact. Adding a reviewed
supported entity type is an additive contract-major-1 extension when existing
meanings and validation behavior are unchanged. This does not predeclare Bill,
office, or Debate semantics; their data-surface evaluation remains future work.

Phase 2B is complete as the first separate model-produced planning path. The
draft JSON Schema at `poc/specs/query-plan-draft.schema.json` constrains the model
to semantic facts, filters, temporal meaning, aggregation, answer shape and
`{id, type, label}` entity mentions, with no model-supplied entity IRIs. The
Responses-compatible planner uses strict JSON Schema output and performs one
model call without automatic repair/retry. Deterministic local exact-label
resolution reuses the Phase 1 Unicode/case-insensitive behavior, preserves
distinct same-name resources, and produces resolved, ambiguous or unresolved
entities. A converted final plan is accepted only after Phase 2A validation.
For duplicate Member labels, exact local HouseTerm/constituency context also
reuses Phase 1 narrowing: one contextual match resolves, multiple matches remain
ambiguous, and no match preserves the original ambiguous candidate set. The
pre-2C Member-binding safety tranche reuses Phase 1's explicit set-valued
Member-reference detector and returns a non-accepted
`set_valued_member_identity` result when a named Member is requested as a set;
the schema-v1 semantic plan remains unchanged and no singular IRI is selected.
Ordinary singular duplicate-name resolution remains deterministic and exact.
The planner result now carries application-layer `binding_evidence` for
context-checked duplicates, including the initial candidates, each candidate's
matched local context labels, the rule and decision, and a selected IRI only
when exactly one candidate matched. This evidence is generated locally, not by
the model, and is not part of the semantic plan. The live Phase 1 query path
remains unchanged.

The Phase 2B corrective tranche aligned the strict draft schema and local
normalizer on participant XOR, kind-specific answer fields, filter values,
temporal variants, and aggregation structure. The Responses endpoint accepted
the corrected schema. It rejects a top-level `anyOf`, so cross-field
aggregation/answer consistency remains fail-closed in the deterministic local
validator; no semantic values are inferred or repaired. Measured run
`d4c0f433-eebd-42bf-ba2d-f5534c21b38b` used
`oireachtas-semantic-planner@0.1.0`, dataset
`sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`,
model `gpt-6-luna` (repository dotenv), and the default
`https://opencode.ai/inference/openai/v1` endpoint (45-second timeout and
2,000-token output limit, both defaults): 3 passed, 6 failed, and 2 not scored.
Failures were 5 `semantic_plan_mismatch`, 1
`invalid_draft_semantics`, and 1 `source_data_coverage`; no model-output
structural failures remained. The run provides usable planner evidence, while
the remaining semantic failures are retained as planner-quality work rather
than changing benchmark expectations.

The Phase 2B semantic-quality tranche adds reviewed answer-shape descriptions,
entity-mention/filter guidance, and term-scoping guidance to query-plan contract
version `1.0.1`. `build_planner_instructions` renders this guidance from the
contract, while Phase 2A validation and deterministic entity resolution remain
unchanged. The planner is grounded to distinguish entity resources from their
display labels and from fact values, to scope a time-dependent fact itself to a
named term, and not to repeat a resolved entity mention as a name filter.

The planner benchmark is now `oireachtas-semantic-planner@0.2.0`. Its Aengus / 33rd
Dáil membership case requires the `member_house_term_membership` fact to link
Aengus Ó Snodaigh directly to the referenced Dáil entity; it no longer requires
a separate `during` constraint on that same fact. This is a contract-based
expectation correction: the HouseTerm object already expresses the membership
period, so the extra temporal constraint was redundant, not a requirement
removed to accommodate a model result. This does not generalize to other
time-dependent facts; collection membership and representation remain
explicitly scoped to their requested term. The benchmark artifact SHA-256 is
`e6091586b98047b940373bf10e898e913c663080711c94af8f3dd0dca841b9ad`.

The measured rerun `bd580949-fc87-40c8-aa37-2fe38278f2ad` used
`oireachtas-semantic-planner@0.2.0`, the benchmark artifact above, dataset
`sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`,
model `gpt-6-luna` (repository dotenv), and the default
`https://opencode.ai/inference/openai/v1` endpoint (45-second timeout and
2,000-token output limit): 7 passed, 2 failed, and 2 not scored. No structural
output failures remained. The Aengus full-name and term cases, collection and
representation answer shapes, Committee code, aggregate, and duplicate-Michael
ambiguity case passed. The two scored failures were
`plan.collection.timmy-dail-34` and
`plan.representation.timmy-seanad-26-panel`: both plans correctly selected the
requested fact, answer shape, and term-scoped temporal constraint, but omitted
the separately benchmark-required `member_house_term_membership` requirement.
This is a repeated requirement-omission class, not an answer-shape or temporal
scoping failure. Determining whether those extra membership requirements are
semantically mandatory or over-constrained requires review; no further
benchmark expectation had been changed at that point. The unavailable-Bill case
remained expected source-coverage-not-scored, and the unsupported-question case
remained manual-review-not-scored. This `0.2.0` result is an interim run and was
followed by the semantic review and corrections below.

Semantic review approved that a HouseTerm used only as the temporal scope of
another requested fact does not automatically require a separate
`member_house_term_membership` requirement. That fact remains required when
service in the term is itself asked about or independently needed to express
the question. Accordingly, planner benchmark `0.2.1` removes that redundant
requirement from the collection-membership and Seanad-representation cases,
while retaining each requested fact, its `during` constraint on the requested
fact, and its entity answer shape. Direct questions about whether a Member
served in a term continue to require `member_house_term_membership`, as in the
Aengus / 33rd Dáil case. These are semantic benchmark corrections, not
score-driven changes; no other temporal expectation is removed. Version `0.2.1`
has SHA-256
`140a6055a83a710f85188985c41ec81d53c160217eb3390dc463aafd1b9c0c85`.

Measured acceptance rerun `7e90554a-e527-4f7d-88b9-78021c30f24e` used
`oireachtas-semantic-planner@0.2.1`, dataset
`sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`,
model `gpt-6-luna` (repository dotenv), and the default
`https://opencode.ai/inference/openai/v1` endpoint (45-second timeout and
2,000-token output limit): 9 passed, 0 failed, and 2 not scored. All scored
cases passed, including collection membership, Seanad representation, direct
Member-term membership, and duplicate-Michael ambiguity; there were no
structural-output failures. The two not-scored cases remain the expected
unsupported-question manual review and unavailable-Bill source-coverage case.
This accepts the Phase 2B semantic-quality tranche against the controlled
benchmark. The pre-2C Member-binding safety tranche documented above closes the
known set-valued binding and contextual-evidence gaps. Phase 2C plan-to-SPARQL
generation is implemented in a separate deterministic compiler; the Phase 1
runtime remains untouched.

### Phase 2C — deterministic local SPARQL generation

Phase 2C adds `poc.nlq.plan_sparql.PlanSparqlGenerator`, a separate deterministic
compiler that accepts only a `PlannerResult` with `validated_plan` status,
revalidates it, and either returns safety-validated local SELECT/ASK SPARQL with
a mapping trace or a structured fail-closed outcome. The compiler has explicit
fact, entity-type, graph-family and filter dispatch grounded in the current
query-schema contract and active predicate allowlist. It preserves named-graph
ownership, binds resolved local entity IRIs only, and does not change ontology,
mapping, graph, or IRI semantics. Ambiguous, unresolved, set-valued, unsupported,
or incompatible plans do not produce executable SPARQL.

Reviewed `during` translations use a referenced Dáil/Seanad term on Member
parliamentary membership, collection membership, or representation. The
membership term type is kept consistent with the referenced HouseTerm type.
Date-window, `current`/`on`, HouseTerm-owned temporal-reference, and
Committee-membership temporal translations remain unsupported; the compiler
does not infer `dct:temporal` or unreviewed cross-fact joins. Resource answer
shapes return IRIs without presentation-label joins. A separate contract-based
label lookup is used only by the evaluator to compare resource answers with
existing label-valued benchmark invariants.

`poc.nlq.plan_benchmark` evaluates planner, final validation, entity binding,
generation, SPARQL safety, Fuseki execution, and result scoring separately. It
does not borrow coverage probes as answer oracles; the 33rd Dáil Boolean plan
has an explicit ASK oracle in planner-benchmark version `0.2.2`. Phase 1 direct
generation is compared only for cases whose question exactly matches the source
benchmark oracle. The generator and evaluator remain outside the browser path.
Phase 1 direct generation is unchanged and remains available during migration.

Measured run `1f789eda-8216-4d23-8e3f-daefac70b94c` used
`oireachtas-semantic-planner@0.2.2` (artifact SHA-256
`5417f1d5db2d21ad2f1b12a3394cbe36236e0a527f382bc9de3f419d23d01276`), source
benchmark `0.3.0`, dataset
`sha256:1d849ec68168b6c456a38756ea812a23a218644204eb44d9bc55ddb3992b814d`,
`gpt-6-luna` (repository dotenv), and the default Responses-compatible endpoint
`https://opencode.ai/inference/openai/v1` (45-second timeout; 2,000-token
output limit). The 11 planner cases resulted in 8 passed, 1 failed, and 2 not
scored. Six cases reached generated-query execution and result scoring; all six
matched their result oracle. One planner case failed before generation because
the model returned answer shape `entity` where the benchmark requires
`entities` for the Seanad-panel question. This remains a planner semantic
mismatch; the compiler and benchmark expectation were not broadened to hide it.
The unsupported-question manual-review and unavailable-Bill source-coverage
cases remain not scored.

The same run's Phase 1 direct-generation comparison passed all 7 comparable
cases. The Boolean planner case has an intentional question override and is not
included in the Phase 1 comparison. The opt-in capture-backed Phase 0A Fuseki
acceptance exercises representative Member, HouseTerm, collection,
representation, Committee, Boolean, and count plans; see
[`poc/nlq/benchmarks/phase-2c-report.md`](../nlq/benchmarks/phase-2c-report.md)
for the run record and limitations. This completes the Phase 2C compiler and
controlled-evaluation tranche, not the Phase 2 exit gate: visible plan
integration and the realistic-question benchmark remain outstanding.

Planner evaluation is a separate controlled path in
`poc/nlq/planner_benchmark.py` using selected Phase 1 cases, semantic plan
invariants, and the existing source-coverage checks. That Phase 2B path scores
planning only. The separate Phase 2C path adds generation and execution without
being wired into normal browser requests. Unsupported requests remain
unscored/manual review because the Phase 2A contract has no explicit
unsupported-question state. Phase 2C does not complete visible plan integration,
the realistic-question benchmark, data-surface expansion or the Phase 2 exit
criteria.
The deterministic unsupported-request test injects a supported draft and checks
only that the manual-review case remains unscored; it does not test whether a
model recognizes unsupported wording.

#### Realistic-question evaluation

- [ ] Add a separate realistic-question benchmark after an initial planner path
      exists and before the Phase 2 exit gate. Preserve the Phase 1 controlled
      benchmark as the capability and regression suite rather than replacing it.
- [ ] Include user-like wording that does not mirror ontology terminology,
      including implicit or colloquial references, ambiguous phrasing,
      temporal language, plural/set-valued questions, multi-hop relationships,
      and questions combining multiple constraints.
- [ ] Use the realistic benchmark to distinguish interpretation/planning
      failures from SPARQL-generation failures.
- [ ] Compare the planned architecture with the Phase 1 direct-generation
      baseline on realistic questions as well as on the controlled benchmark.
- [ ] Treat success on the controlled benchmark as necessary but insufficient
      evidence of good real-user query experience.

### Exit criteria

- Every supported query has a validated structured plan before execution.
- SPARQL generation no longer has to infer the complete user intent directly
  from prose.
- The visible plan makes planning errors distinguishable from SPARQL errors.
- Local controlled-benchmark quality is at least comparable with the Phase 1
  baseline.
- A separate realistic-question benchmark exists and provides evidence that
  the planner handles representative user-like questions; Phase 2 is not
  considered successful solely from the controlled capability benchmark.

## 9. Phase 3 — Source selection and provenance

### Outcome

Make the planner capable of deciding where a requested fact should come from
without yet executing arbitrary external federation.

### Dataset/capability catalogue

Introduce a machine-readable catalogue describing, at minimum:

- source identifier;
- endpoint/query mechanism;
- entity types supported;
- facts/properties supported;
- authority status;
- available join identifiers;
- local graph ownership where applicable;
- freshness/retrieval characteristics; and
- whether the source is allowed for automatic execution.

Initial sources should be:

1. local Oireachtas Fuseki; and
2. Wikidata as a controlled external source.

### Backlog

- [ ] Define the dataset/capability catalogue format.
- [ ] Encode the Oireachtas/Fuseki capabilities used by the benchmark.
- [ ] Encode an intentionally small initial Wikidata capability set.
- [ ] Define source-selection rules for facts available from multiple sources.
- [ ] Prefer authoritative Oireachtas data for Oireachtas parliamentary facts.
- [ ] Define how reviewed Oireachtas-to-Wikidata identities participate in
      cross-source joins.
- [ ] Extend the query plan with explicit selected source(s).
- [ ] Define provenance records for each result field or result contribution.
- [ ] Display source selection and provenance in the development interface.
- [ ] Reject plans requiring unsupported or unapproved sources.

### Exit criteria

- The service can explain why a requested fact is local or external.
- Source selection is explicit and validated.
- Oireachtas authority is not displaced by external enrichment.
- Provenance can represent mixed-source answers before external execution is
  enabled.

## 10. Phase 4 — Controlled Wikidata application-layer federation

### Outcome

Answer a constrained class of mixed Oireachtas/Wikidata questions by executing
separate local and remote queries and joining them inside the application.

This phase deliberately does **not** enable arbitrary generated SPARQL
`SERVICE` clauses.

### Initial target

Members are the preferred first entity type because the repository already has
a mature reviewed Member-to-Wikidata reconciliation path.

A first supported flow may be:

```text
question
   |
   v
query plan
   |
   +--> local Fuseki:
   |       resolve Member
   |       obtain accepted Wikidata identity
   |
   +--> Wikidata:
           query one allowlisted property for that QID
   |
   v
application join
   |
   v
result + per-source provenance
```

### Backlog

#### External identity prerequisite

- [ ] Ensure accepted Wikidata links required by the initial scenarios are
      published/queryable in the development dataset.
- [ ] Define behaviour when no accepted identity exists.
- [ ] Never replace reviewed identity with an ad-hoc fuzzy match during query
      execution.

#### Wikidata query generation

- [ ] Define the initial allowed entity types and Wikidata properties.
- [ ] Generate Wikidata SPARQL from a validated external sub-plan.
- [ ] Restrict execution to the configured Wikidata endpoint.
- [ ] Enforce result limits and query complexity constraints.
- [ ] Show generated Wikidata SPARQL in the development interface.

#### Execution

- [ ] Implement explicit timeout and retry behaviour.
- [ ] Distinguish remote unavailability from "no matching fact".
- [ ] Handle Wikidata rate limiting without corrupting local results.
- [ ] Add bounded caching where measurement shows it is useful.
- [ ] Join remote rows to local entities only through accepted identifiers.
- [ ] Preserve source attribution through the join.

#### Evaluation

- [ ] Add mixed-source benchmark questions.
- [ ] Measure planning, identity-join, external-query and composition failures
      separately.
- [ ] Compare application-layer federation with equivalent manually written
      queries.

### Exit criteria

- A constrained set of mixed local/Wikidata questions works end to end.
- Both local and external queries are visible and independently testable.
- Remote failure does not make local source state unreliable.
- All external joins use approved identity mechanisms.
- Provenance identifies which source supplied each fact.

## 11. Phase 5 — Service boundary and repository extraction

### Outcome

Extract the query service from OireachtasOntology once its inputs and behaviour
are stable enough to define a genuine interface.

Do not split solely for directory tidiness. Split when the service has an
independent lifecycle.

### Preconditions

The split should normally wait until:

- the query/schema contract is versioned;
- the query-plan schema is stable enough for independent development;
- source selection exists;
- at least one controlled external-query path works;
- service-specific dependencies no longer belong naturally in the ETL
  environment; and
- the service has its own meaningful deployment/testing lifecycle.

### Backlog

- [ ] Define the exported Oireachtas query/schema contract artifact.
- [ ] Remove remaining private imports from `oireachtas_etl`.
- [ ] Decide contract distribution/versioning mechanism.
- [ ] Establish a new query-service repository/package.
- [ ] Move NLQ/planner/execution code without changing semantic behaviour.
- [ ] Preserve benchmark fixtures and regression tests.
- [ ] Add compatibility testing against supported OireachtasOntology contract
      versions.
- [ ] Define independent configuration for LLM providers, Fuseki and external
      sources.
- [ ] Define deployment and observability boundaries.

### Exit criteria

- The query service can be built, tested and run without importing private ETL
  code.
- Supported OireachtasOntology versions are explicit.
- The move causes no benchmark regression.
- OireachtasOntology remains responsible for data production and semantic
  contracts; the new repository owns query interpretation and execution.

## 12. Phase 6 — Controlled SPARQL federation

### Outcome

Evaluate and, where justified, enable a constrained subset of true federated
SPARQL using `SERVICE`.

Application-layer federation remains valid and should not be removed merely
because SPARQL federation becomes available.

### Backlog

- [ ] Identify query patterns where `SERVICE` provides a material advantage
      over application-layer joins.
- [ ] Extend safety validation with an explicit federation mode.
- [ ] Allow only configured remote endpoints.
- [ ] Constrain allowed remote graph patterns/properties.
- [ ] Preserve SELECT/ASK-only behaviour.
- [ ] Retain strict LIMIT and complexity controls.
- [ ] Add execution timeouts and cancellation.
- [ ] Prevent user/model-supplied arbitrary endpoint IRIs.
- [ ] Measure performance and reliability against the equivalent
      application-layer query.
- [ ] Preserve provenance even when one federated query performs both parts.
- [ ] Keep application-layer fallback for remote-service limitations.

### Exit criteria

- Federated SPARQL is enabled only for reviewed query classes.
- The safety boundary is explicit and testable.
- Performance/reliability is demonstrably acceptable for supported patterns.
- Provenance remains visible.
- Arbitrary remote endpoint execution remains impossible.

## 13. Phase 7 — Broader query service

### Outcome

Expand only after the local, planning and federation foundations are reliable.

### Candidate backlog

These are candidates, not committed sequence:

- [ ] broaden Wikidata entity/property coverage;
- [ ] evaluate additional linked-data sources where they provide distinct
      value;
- [ ] add result and entity caches based on measured need;
- [ ] add query-cost and latency telemetry;
- [ ] add richer provenance/explanation output;
- [ ] add query-history/debug tooling;
- [ ] expose a stable service API;
- [ ] add production authentication/rate limits if required;
- [ ] improve user-facing result presentation;
- [ ] evaluate conversational query refinement;
- [ ] evaluate semantic retrieval or text search for Debates/Acts where SPARQL
      alone is not the right retrieval mechanism.

### Exit criteria

Defined per selected delivery. Phase 7 is intentionally a rolling product
backlog rather than a fixed architectural sequence.

## 14. Recommended near-term sequence

The advised implementation order from the current baseline is:

1. complete the separate historical reference-coverage tranche sufficiently
   for representative local NLQ evaluation;
2. implement Phase 0 benchmark and query/schema contract;
3. run Phase 1 local-quality work based on measured failures;
4. implement Phase 2 structured query planning;
5. implement Phase 3 source selection/provenance;
6. implement Phase 4 controlled Wikidata application-layer federation;
7. reassess the repository boundary and perform Phase 5 extraction when the
   contract is stable;
8. consider true SPARQL federation only after the controlled external-query
   path has proved useful.

The ordering after Phase 0 is evidence-sensitive. For example, if the benchmark
shows that entity resolution dominates failures, address that before spending
time on aggregation improvements.

## 15. Deferred work

The roadmap does not currently require:

- a polished UI;
- transcript text in RDF;
- arbitrary RAG;
- a vector database;
- persistent conversational memory;
- arbitrary user-supplied SPARQL;
- unrestricted external endpoints;
- general-purpose Wikidata access;
- copying large portions of Wikidata into local Fuseki; or
- immediate extraction into another repository.

Those may become useful later, but none is a prerequisite for validating the
query-service architecture.

## 16. Open decisions

The following should be resolved by the phase that first needs them rather than
up front:

- exact query-plan JSON schema;
- cross-repository query/schema contract distribution mechanism;
- benchmark scoring method and required success thresholds;
- initial Wikidata property/entity allowlist;
- provenance representation returned by the service;
- caching policy and TTLs;
- criteria for choosing application-layer versus SPARQL federation;
- repository/package name for the extracted service;
- production API shape; and
- production UI.

The roadmap should be updated when those decisions become evidence-backed
contracts rather than speculative design choices.
