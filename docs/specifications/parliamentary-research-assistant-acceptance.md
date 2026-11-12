# Parliamentary Research Assistant — Research Acceptance Contract

**Version:** 1.0 · **Date:** 12 November 2026  
**Status:** Approved design contract; implementation not authorised  
**Parent:** [Parliamentary Research Assistant v0.3](parliamentary-research-assistant.md)  
**Companion:** [Editorial standard](parliamentary-research-assistant-editorial.md)

## 1. Purpose

The user must obtain **useful parliamentary research**, not merely a valid database response. Automated compiler tests remain necessary but cannot establish product acceptance. Evaluate **natural-language understanding, research usefulness, editorial quality and factual integrity separately**.

All scenarios below are candidate evaluation briefs. They are *not* assertions that the current compiler can answer every part. Before an implementation test, independently establish the supported-operation inventory and freeze the expected requirements/evidence boundaries. Do not change or narrow a question after seeing the model's output.

## 2. Realistic research briefs

### R1 — Legislative progress

> “Prepare a briefing on the Bills sponsored by Malcolm Byrne. What progress have they made, and what happened to them?”

**Purpose:** Give a reader an overview of a Member's legislative activity and identify which developments can actually be established.

**Expected research questions:** Which Bills have accepted sponsorship evidence? What sponsor role is recorded? What documented legislative stages/statuses exist? Do the available records establish enactment or another outcome for each Bill? What is missing?

**Required behaviour:** Distinguish sponsorship from participation, Bill from Act, publication from introduction, last recorded stage from final outcome, and missing lifecycle evidence from proof of inactivity. Produce coherent narrative and an appropriate Bill table if verified. No invented progress.

**Coverage boundary:** Lifecycle and activity-date evidence may be incomplete; explicit partial reporting is acceptable.

### R2 — Constituency representation over time

> “How has the representation of Dublin Central changed between the previous Dáil and the current one? Prepare a short report.”

**Purpose:** Understand the named constituency's parliamentary representation across terms.

**Expected research questions:** Which exact Dáil terms are intended? How is Dublin Central identified in each? Which TDs were recorded for each term or reporting date? What changed in the verified selections?

**Required behaviour:** Clarify material difference between serving at a date and at any point during the term when needed; preserve exact constituency/term identities; avoid inventing a change from incomplete rosters. A table may support a short contextual explanation.

**Coverage boundary:** If the compiler cannot safely make the historical comparison or the necessary joins, show verified independent findings and identify the unanswered comparison.

### R3 — Parliamentary career

> “Prepare a background briefing on Mary Lou McDonald's parliamentary career, including constituencies represented and parliamentary roles.”

**Purpose:** Produce a readable, chronologically meaningful briefing.

**Expected research questions:** Identity resolution; accepted parliamentary membership and constituency episodes; any verified named offices or committee roles; what the sources cannot establish.

**Required behaviour:** Separate Dáil service from ministerial or committee responsibilities; distinguish individual episodes from continuous tenure; do not imply a complete career history from fragmentary records.

**Coverage boundary:** Not every requested role or duration may be available. State gaps, do not fill them from model memory.

### R4 — Committee and party membership (intentional composition boundary)

> “Which members of the current Public Accounts Committee belong to Fine Gael? Explain what can be established.”

**Purpose:** Investigate an intersection of two parliamentary relationships.

**Required behaviour:** Do not silently substitute an unfiltered committee roster or a party TD list for the intersection. If the required combined selection is not approved, explain the distinction, present independently supported context when useful and identify precisely what remains unverified. Do not let an LLM infer membership by matching names without an approved temporal/identity join.

### R5 — Debate topic (intentional evidence-coverage boundary)

> “Prepare a briefing on how housing was discussed in Dáil debates last year.”

**Purpose:** Understand the substance of parliamentary debate, not merely find record metadata.

**Required behaviour:** Recognise that topic analysis requires speech/transcript content and appropriate retrieval/coverage. If only dates/links or metadata can be established, do not invent what Members said or imply a topic analysis occurred. Propose an alternative investigation or request approval for an additional evidence source.

### R6 — Supporting regression, not primary demonstration

> “Compare Fine Gael and Fianna Fáil TD membership on the current reporting date.”

**Purpose:** Preserve the accepted Phase 1 integration/evidence regression.

**Required behaviour:** Verified independent list/count selection, compatible units and dates, qualified local-record wording. **Passing R6 alone cannot establish product acceptance.**

## 3. Cross-scenario language and interaction tests

For each realistically answerable research need, independently prepare at least two semantically equivalent but differently phrased briefs, including an ordinary non-technical formulation. The LLM should propose substantially equivalent **research purposes and requirements**, not merely recognise matching keywords. Do not demand identical query plans when several valid approaches exist.

Exercise a multi-turn sequence: initial question → evidence-backed finding → “Why does that matter?” → “Show me the evidence” → a material scope change → revise an affected report section. Preserve unrelated findings and distinguish changes requiring approval from user-authorised changes.

Include adversarial but realistic material qualifiers: another date, a different House, exclusion of a Member, a different sponsor role, or request for an unsupported combined relationship. A plan that omits a material condition must not execute as though complete. Include ambiguous identity, missing evidence, fail-closed query errors and a genuinely unsupported question.

## 4. Four independent acceptance dimensions

| Dimension | Required outcome | Failing examples |
|---|---|---|
| **Language understanding** | Captures the research purpose, entities, time scope, comparison and all material qualifications across ordinary paraphrases; asks only meaningful clarifications. | Entity-name extraction only; rigid allowed-word list as normal entry point; unacknowledged dropped qualifier. |
| **Research usefulness** | Proposes relevant subsidiary questions; pursues supported work automatically; provides an informative answer where possible, and makes outstanding questions clear. | Cosmetic report made of table cells; safe but unhelpful blanket refusal when independent evidence exists. |
| **Editorial quality** | Coherent, explanatory, plain-English report and dialogue in the [editorial contract](parliamentary-research-assistant-editorial.md); parliamentary terms used accurately. | “Member IRIs”, “accepted witnesses”, internal status strings or jargon in normal report prose; meaningless comparison as primary research. |
| **Factual integrity** | Every substantive claim traceable to accepted evidence/approved background; no unsupported joins, dates, causal claims or false completeness; limitations survive export. | A convincing but ungrounded report; silent downgrade to easier query; claiming a complete roster from uncertified local records. |

**All four dimensions must pass.** Safe refusal is positive evidence of restraint, not proof the assistant completed the research. The LLM's own confidence or self-graded evaluation does not determine acceptance.

## 5. Evaluation method

1. **Freeze the materials before running:** user/independent researcher-authored briefs where available; separately label AI-authored cases and constructed negative controls. For each, freeze intended meaning, material requirements, expected evidence type and supported/unsupported boundary based on the actual selected revision and dataset. No invented or prefilled factual answer totals.
2. **Run actual end-to-end research interactions:** real model interpretation, typed compiler calls, the evidence store and LLM report writing. Retain all proposals, clarifications, rejections, operations, results, report revisions and user-visible text.
3. **Score separately:** complete-intent preservation, factual answer validity, useful handling of gaps, editorial readability and interaction interruptions. Record per-requirement outcomes; do not pool safe refusals into factual success.
4. **Review independently:** a human evaluator assesses the report as a parliamentary reader, with source evidence available for factual checking. The implementation agent must not judge its own prose as sufficient.
5. **Verify the UI:** research plan visibly precedes initial execution; the report progresses; conversation can modify it; source details and unsupported requirements remain accessible; keyboard, responsive, export and failure states comply with the v0.3 UI contract.
6. **Keep limitations visible:** accepted findings are relative to tested revisions, model settings and available data; no claim of broad generalisation from a small set of scenarios.

## 6. Acceptance gate for the next corrective vertical slice

This is a **proposed gate**, not implementation authorisation:

- At least one substantial research brief from **R1–R3** produces a readable evidence-backed report with genuinely LLM-led interpretation, research planning and prose (not a fixed report template).
- Demonstrate **a second domain** through an independently checked research flow or a well-evidenced bounded limitation; a successful party-count comparison cannot be the only operational demonstration.
- R4 and R5 demonstrate truthful, useful treatment of unsupported composition/content needs, without invented findings or silent simplification.
- At least one real multi-turn refinement modifies an existing plan/report; unrelated accepted findings survive.
- Every material original requirement is answered, explicitly pending/unsupported or clarified; no unsafe admission or materially unsupported report claim.
- Independent reviewers accept editorial usefulness and comprehensibility. All required existing/new compiler safeguards and end-to-end browser checks pass.
- Record remaining deficits rather than broadening compiler/ETL scope to chase every possible question. If genuine research dialogue or grounded narrative cannot be achieved with the chosen architecture, stop for design review rather than declaring success from integration tests.

Passing the adapter test suite, R6 or a polished UI alone does **not** meet this gate.

## 7. Status and authority

Phase 1's adapter, trace preservation and progressive rendering are technical assets, not proof the v0.3 experience is delivered. This contract defines the human/product gate to be used **after** separately authorised implementation. It does not approve Phase 2, a compiler expansion, a data reload, external source access or public deployment.
