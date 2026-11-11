# NLQ Query Explainer — Presentation Contract

Status: **Approved design direction; implementation pending**  
Branch: `feat/query-explainer-readability`  
Scope: Existing **Interpreted → Compiled → Executed** query explainer in the NLQ dashboard  
Date: 2026-11-11

## 1. Objective and boundaries

Make the three-stage explainer understandable to a general reader while retaining diagnostic evidence for developers and ontology practitioners. This is a **presentation and explanation-formatting** change, not an expansion of NLQ capability.

The existing warm off-white/white/gold dashboard, three tabs, keyboard operation, collapsed Performance disclosure, and neutral System status treatment remain in place. Do not add a relationship explorer, new navigation, or a separate dashboard.

**Approved choice (Option A):** The Compiled tab explains the **contents and implications of the validated query plan**. It does **not** claim to reconstruct the actual chronological sequence of internal compiler decisions. No new compiler tracing or semantic instrumentation is authorised.

Out of scope: changes to query interpretation, admission, entity resolution, validation, SPARQL semantics, underlying RDF data, answer computation, or source completeness policy. If a truthful explanation requires unavailable evidence, report the gap; do not silently alter the compiler.

## 2. Information architecture

| Tab | Primary question | Default presentation | Expandable evidence |
| --- | --- | --- | --- |
| **Interpreted** | What did the system understand me to be asking? | One short natural-language statement, conditions/assumptions, expected result type and material qualifications | Further interpretation evidence and original diagnostics |
| **Compiled** | What query did the validated plan specify? | Human-readable plan components: answer target, resolved identities, required relationships, temporal/other constraints, distinctness | Validated plan JSON, IDs/IRIs, generated SPARQL where actually available |
| **Executed** | What did the database return and what does it establish? | Execution status, returned result summary, material limitations | Result rows, evidence/provenance actually returned, execution diagnostics and SPARQL where available |

Do not duplicate the entire final answer in the explainer. Keep headings distinct and describe the specific question's content rather than generic text such as “A validated plan was produced.”

### Progressive disclosure

1. **Default:** brief, accessible language; no raw JSON or SPARQL.
2. **Details:** concise condition/relationship/evidence breakdown when supported.
3. **Technical:** existing raw structured data and diagnostics, visually secondary but discoverable.

Keep the same interaction and tab accessibility conventions already established. Expansion controls must be keyboard-operable, labelled, and expose expanded/collapsed state. Do not replace useful current debug content with prose.

## 3. Stage contracts

### 3.1 Interpreted

- Start with “Your question was understood as” (or an equivalent short heading) and a one- or two-sentence interpretation.
- Identify the answer target and meaningful filters: for example party, constituency, parliamentary term, and temporal relation.
- Distinguish **explicit** user constraints from **inferred defaults** wherever the existing plan supplies that evidence. Do not present a default as if the user stated it.
- “Validated” must mean that the particular plan actually passed applicable validation; plausible draft text is not validated.
- Replace the heading “Expected answer shape” with “What the results will contain.” Describe distinctness, count/list shape and evidence qualifications in ordinary English.
- Use the existing ambiguity/refusal/unsupported states honestly; do not present a successful interpretation if none was accepted.

**Illustrative wording, not an expected answer:** “Find TDs who represented Dublin Central in the 22nd Dáil and were affiliated with Fianna Fáil during the relevant period.” Follow with condition rows, including any overlap constraint supported by the plan.

### 3.2 Compiled — Option A

Render an **explanation of the validated plan**, not an asserted timeline of runtime events.

Recommended order, omitting unavailable or inapplicable items:

1. **Answer target:** which type of entities, facts, count or boolean the query requests.
2. **Identified entities:** grounded names, selectors and resolved identities; unresolved/ambiguous values explicitly identified.
3. **Relationships:** the typed paths or joins required by the plan, translated into plain language.
4. **Conditions:** temporal scope, overlap/intersection, exclusions or other filters when represented.
5. **Result construction:** distinctness, grouping, aggregation, ordering and limits when evidenced.

The UI may number these **plan components** for readability, but must not label them “Step 1 performed”, “then resolved”, or otherwise imply an observed execution sequence. Descriptions must be driven by actual structured plan semantics and status; avoid templated claims that merely sound plausible.

**Evidence mapping to inspect and confirm during implementation:**

| Candidate source | May explain | Constraint |
| --- | --- | --- |
| `plan.family` and version | Supported query shape | Do not treat family name as an account of reasoning |
| `plan.referents`, selectors, `resolution`, `iri` | Answer target and grounded identities | Show an IRI only when actually resolved and available |
| `plan.relations` and reviewed relation definitions | Required entity relationships | Translate only known semantics; no guessed joins |
| Explicit temporal/condition fields and interpretation evidence | Date, term, interval and inferred defaults | Use exact condition semantics; distinguish term-wide from point-in-time |
| `plan.answer` | List/count/boolean, distinctness, display fields | Do not promise result evidence that the execution cannot return |
| Available compilation SPARQL/diagnostics | Technical disclosure | Do not imply SPARQL exists on pre-compilation failures |

The implemented mapping must be verified against actual emitted plans **across families**, not inferred solely from this table. Unknown/unsupported fields should receive conservative fallback text or remain in technical details; they must not be ignored if doing so materially changes the claimed meaning. Prefer shared renderers for shared semantics and narrowly scoped family-specific wording only where semantics differ.

### 3.3 Executed

- Show whether execution was **attempted** before describing a success or failure. Respect the existing explicit `execution_attempted` evidence; a pre-execution failure must leave this stage unavailable rather than invent an execution outcome.
- Report the actual returned kind and rows/count/boolean, without fabricated example results.
- Clearly separate **query executed successfully**, **matching records were found**, and **the requested historical answer is complete**. None implies the others.
- Present provenance/relationship-level evidence only if actually surfaced by the result/diagnostics. If not available, do not render an invented evidence trail.
- Treat zero results as “No matching records found in the queried data,” not proof that no historical matches exist.
- Keep result qualifiers near the result they qualify. Material incompleteness or partial-coverage information must not be hidden only in raw diagnostics.

## 4. Status and failure semantics

Treat these as distinct states, using system evidence rather than inferred labels:

| State | Presentation rule |
| --- | --- |
| No accepted interpretation / ambiguity | Explain the ambiguity or non-admission; do not claim a validated plan |
| Draft or rejected plan | Mark as unvalidated/rejected, with the available reason; do not show validated compilation |
| Validated plan, not executed | Compiled can explain its supported structure; Executed stays unavailable |
| Execution attempted, failed | Show the execution error classification and what is known, without saying the query succeeded |
| Execution succeeded, no rows | Say no matches were returned in the local dataset; avoid universal negative claims |
| Execution succeeded, partial/uncertified evidence | Show the result and separately qualify its coverage or completeness |
| Explanatory field missing | Omit unsupported detail or say “Not available from this plan”; never invent a cause or action |

Preserve the existing behaviour of stages that are inaccessible because prerequisite evidence is absent.

## 5. Language and terminology

Use short sentences and parliamentary terms where familiar. Introduce ontology or SPARQL terminology only in expandable details.

| Existing wording | Preferred default wording |
| --- | --- |
| “Validated plan” | “Interpretation validated” **only where validation evidence exists** |
| “Validated composable query plan” | “Technical query plan” |
| “Referents” | “Identified entities” |
| “Resolution: resolved” | “Matched to an ontology identity” |
| “Established interval overlap” | “The relevant periods must overlap” |
| “Expected answer shape” | “What the results will contain” |
| “Historical source completeness is not certified” | “Historical records may be incomplete” (where that is the actual caveat) |

Do not replace technically precise wording with a stronger claim. For example, “periods must overlap” describes a plan constraint, whereas “periods were confirmed to overlap” is an execution/result claim and needs corresponding evidence.

## 6. Representative acceptance examples

Use actual available plans, results and failures (including the Dáil/constituency/party example in the review screenshots), not hand-crafted expected JSON alone. At minimum test:

- A historical composition involving constituency, party affiliation, parliamentary term and overlap.
- A present-time/defaulted relationship query, including visibly distinguishing inferred `asOf` from explicit date/term.
- A different family such as Bills or offices, to demonstrate that the explainer generalises beyond the screenshot example.
- Ambiguous identity or unsupported request: no false “validated” badge.
- Validated plan followed by execution success, zero rows, and execution failure.
- Pre-execution failure: Executed remains unavailable.
- Partial or uncertified evidence, where surfaced: visible and accurately qualified.
- A plan with absent optional explanation fields: readable and truthful fallback.

Illustrative screenshot examples are **not** ground truth for compiler paths or returned results; cross-check actual contracts and runtime payloads.

## 7. Exit criteria and verification

This tranche is accepted when:

1. Each tab answers its primary question in plain English without opening JSON/SPARQL.
2. Every user-visible semantic claim is traceable to the validated plan, explicit interpretation metadata, result, or available diagnostics.
3. The Compiled explanation presents **plan structure**, never an invented compiler trace.
4. Shared patterns across multiple query families produce consistent explanations without one-off question-string rules.
5. Success, failure, unavailable, ambiguous, zero-result and incomplete-evidence cases are visibly distinguished.
6. Existing raw plan JSON, generated SPARQL (where present), result/debug data and performance disclosures remain accessible.
7. Tabs, disclosures, contrast and responsive layout remain accessible, including keyboard navigation and explicit state labels.
8. Focused presentation tests and relevant regression tests pass; browser-level interaction/accessibility checks are performed if available, otherwise documented as unverified.
9. No planner/compiler/query semantics, loaded data, or production configuration are changed.

## 8. Implementation review and escalation

Before changing presentation code, inspect `poc/nlq/app.py`, current templates and explanation formatters, emitted plan examples and `poc/specs/composable-query-plan-contract.json`. Record the **actual evidence-field mapping** in code/tests or a short appendix, noting gaps. Avoid assuming every family emits identical fields.

If the requested prose requires information not present in the validated plan/diagnostics, use a conservative UI fallback and record the gap. Escalate any proposed new compiler tracing, additional semantic fields, or behaviour changes for separate approval.

This document fixes the **presentation contract**. It does not claim that the full field mapping or browser feasibility has already been verified, and it does not authorise the UI implementation by itself.
