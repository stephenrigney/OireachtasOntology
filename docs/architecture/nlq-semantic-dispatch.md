# NLQ interpretation and semantic dispatch — architecture decision

> **Status:** Proposed for human review — 2026-11-07.
> This records the intended architecture, not a description of completed
> implementation or permission to start implementation. The next gate is
> approval of this decision and the bounded Tranche 1 scope.
>
> **Scope:** Local Query Service natural-language interpretation, capability
> selection, semantic validation and handoff to existing query compilers.
> No change to the ontology, ETL, data authority or user-interface presentation.

## Context and evidence

The Query Service has reviewed, deterministic query capabilities and a bounded
composable semantic planner. The default Phase 2 path currently combines
lexically recognised handlers with an AI-assisted fallback. The model may
propose a structured v2 semantic plan, but local code must validate its
relationships, resolve exact identities and compile read-only SPARQL.

The current `composable-query-plan-contract.json` describes 37 question families,
but **a question family is not necessarily an independently executable operation**.
Its explicit `semanticDispatch.capabilities` list contains seven entries;
other reviewed operations are still reached through specialised parsers or
model-authored graph plans. One listed capability,
`member_bill_sponsorship`, is routed through a separate semantic family rather
than the generic `capability_selection` validator/executor path. Thus the
catalogue is neither a complete nor fully uniform description of semantic
dispatch.

The 2026-11-06 independent generalisation evaluation recorded 22 correct
factual answers from 48 evidence-backed supported questions (45.8%).
The 26 misses were safe nonanswers: 15 unsupported outcomes, ten validation
failures and one unresolved identity. The diagnosed classes included
unexposed existing operations, wording-sensitive validation, model-generated
graph defects and early entity-span misparsing. These observations support
improving capability reachability before broadening query coverage. They do
not establish that every failed question is supported, nor guarantee future
factual accuracy. The evaluation's dirty-working-tree attribution caveat
continues to apply.

## Decision

Adopt a **hybrid capability-/operator-oriented interpretation interface**.
Keep the current bounded, validated graph plan and execution machinery as
the compiler's internal representation. Reduce how often AI must generate
that graph by having it select an approved operation and provide grounded
semantic inputs, with local code constructing the canonical graph where a
reviewed construction exists.

This is an evolutionary design, not a wholesale planner replacement.

### 1. One reviewed executable capability inventory

Maintain a single versioned semantic-dispatch inventory aligned to the
existing query-plan contract. An advertised operation must define, or link
unambiguously to:

- a stable operation ID and owning deterministic handler/compiler;
- typed, bounded inputs and the accepted answer shape;
- the precise temporal, identity and source-evidence semantics;
- supported composition/exclusion conditions and explicit limitations;
- a validation adapter and an executable dispatch target.

Do not equate every documented question family with executable support.
Do not advertise an operation until its adapter, executable target and
contract tests are present. Existing semantic contracts and reviewed
query-schema/graph ownership remain authoritative for execution.

### 2. AI interprets intent; code constructs canonical plans

For a covered operation the semantic model should propose an operation ID
and the necessary inputs, including entity mentions, requested time scope,
answer form and explicit constraints. Where supported composition is needed,
it may select a **reviewed bounded composition operator** with typed inputs.

The model must not supply IRIs, arbitrary RDF predicates, graph names,
SPARQL, identity decisions or assertions of evidence completeness. Local
code owns canonical plan construction, validation, source/identity resolution,
SPARQL compilation and execution.

Preserve the existing v2 graph-draft route for currently reviewed
compositions until a replacement operator is implemented and verified.
Do not reinterpret this decision as approval for arbitrary operator
composition or unrestricted natural-language-to-SPARQL.

### 3. Validate complete intent, not one surface form

Separate the accepted semantic constraints from the particular words
used to express them. Normalise equivalent forms such as `24th Dáil` and
`Dáil number 24` before comparing term numbers. Preserve grounded
mentions and evidence of the original phrases.

The validator must still account for **every** requested relationship,
filter, exclusion, aggregation, answer projection and time interpretation.
Important distinctions include:

- term-wide service versus membership active at a particular date;
- exact numbered terms versus relative terms resolved against House dates;
- Member counts versus seat counts;
- negated or excluded conditions versus affirmative requests;
- independent identity paths and common time intersections where required.

Unknown or unrepresentable conditions remain explicit unsupported outcomes.
Do not address variation by merely removing lexical guards or ignoring
unconsumed question text.

### 4. Make routing failures distinguishable

Continue to use deterministic handlers for questions they interpret
unambiguously. Where an early parser produces an invalid/incomplete
interpretation (for example, capturing `today` as part of a constituency
name), permit a bounded alternative interpretation path **before** treating
that parse as authoritative.

A failed authoritative lookup or missing accepted source evidence must
not be transformed into a guessed identity or factual answer. Retain
separate diagnostics for unrecognised wording, invalid plan, unsupported
semantics, ambiguity, missing evidence and execution failure.

### 5. Preserve present safeguards

Do not loosen read-only execution, exact RDF identity, reviewed relations,
graph/source authority, date/interval correctness, complete pagination,
fail-closed uncertainty, or the rule against silently dropping constraints.
An increased answer rate is not acceptable if it introduces incorrect
answers or unjustified completeness claims.

## Options considered

| Option | Decision |
|---|---|
| Patch prompt text and per-question regexes only | Insufficient: leaves duplicate capability definitions and model-authored graph defects |
| Replace the entire planner with a flat capability catalogue | Rejected as the sole solution: would obstruct reviewed bounded composition and invite a new template explosion |
| Capability selection for existing handlers, bounded operator selection for composition, deterministic canonical graph construction | **Chosen target**: reuses accepted execution evidence while simplifying the AI handoff |

## Delivery sequence and gates

### Tranche 1 — capability discovery and dispatch parity

**Approved-for-design candidate scope, not yet implementation approval:**
inventory reviewed executable capabilities; select a small set shown
unreachable through semantic wording in the independent evaluation
(e.g. distinct Member Dáil-term counts, House date/month selection, and
Dáil seat complement), and expose them through validated dispatch adapters.
Only include an operation after confirming its actual handler, contract,
input semantics and result limitations. Reuse existing execution paths;
do not create new RDF query families to satisfy a test case.

**Exit criteria, to verify before the next gate:**

1. Every capability advertised in the selected inventory has an adapter,
   canonical plan/execution path, and a test that detects missing or
   inconsistent registrations; no dangling `capability_selection` IDs.
2. Previously unreachable selected operations answer ordinary, varied
   phrasings while preserving all requested scopes and the existing
   answer/evidence qualifications.
3. Previously correct controls remain correct; unsupported and ambiguous
   requests still fail closed, without silently omitted conditions.
4. Targeted tests and fresh, withheld paraphrases demonstrate improvements.
   Use the published 60-question evaluation for diagnosis/development,
   not as a newly independent acceptance holdout.
5. The report distinguishes newly reachable supported operations from
   genuinely missing capabilities and data-evidence failures.

**Human gate:** review the Tranche 1 evidence and confirm that capability
selection improves reachability without expanding query semantics, before
authorising Tranche 2.

### Tranche 2 — language variation and constraint preservation

Normalise term expressions, negation/exclusion, ordinary paraphrases and
entity spans through a shared semantic representation. Maintain precise
temporal and aggregation distinctions. Exit when targeted and fresh
paraphrase tests preserve the full query intent and do not weaken guards.

### Tranche 3 — bounded composition handoff

Pilot one or more existing reviewed composition shapes where AI currently
authors detailed graph edges. Let AI select the operator and inputs while
local code assembles the canonical graph. Compare graph-draft rejection
rates, repeated-answer consistency and correctness against the accepted
implementation. Retire only the verified replaced path.

Tranches 2 and 3 require their own bounded implementation scopes and
human approval; this decision does not authorise them automatically.

## Consequences and deferred details

- The canonical v2 plan remains inspectable in the Query Service.
- The proposal should reduce duplicate planner instructions and generated
  graph errors, but introduces an inventory/adapter maintenance obligation.
- An operation inventory does not imply closure under arbitrary combinations.
- The exact inventory schema, plan-input representation, migration mechanics
  and partial-parse recovery policy should be settled within bounded
  implementation design, not invented as new framework machinery now.
- Capability reachability and underlying data completeness remain distinct
  measures. A safe refusal is not an answered supported question.
- The separate user-facing compiler guide and dashboard presentation are
  outside this decision.

## Relevant authorities and evidence

- [Query Service technical specification](../../poc/specs/query-service-plan.md)
- [Composable query-plan contract](../../poc/specs/composable-query-plan-contract.json)
- [Composable draft schema](../../poc/specs/composable-query-plan-draft.schema.json)
- [Semantic planner and validators](../../poc/nlq/composable_semantic_planner.py)
- [Dispatch and execution](../../poc/nlq/composable_plan.py)
- [Interpretation rules](../../poc/nlq/interpretation.py)
- [Independent generalisation evaluation](../reports/query-service/independent-generalisation-evaluation.md)

Until an approved tranche changes them, the executable code, reviewed
contracts and tests describe actual supported behaviour; this proposed
decision describes the intended direction only.
