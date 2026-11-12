# Parliamentary Research Assistant — Research Acceptance Contract

**Version:** 1.1 · **Date:** 12 November 2026  
**Status:** Approved design contract; implementation not authorised  
**Parent:** [Parliamentary Research Assistant v0.4](parliamentary-research-assistant.md)  
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

Include adversarial but realistic material qualifiers: another date, a different House, exclusion of a Member, a different sponsor role, or request for an unsupported combined relationship. A plan that omits a material condition may still execute a **relevant, accurately scoped supporting search**, but must not mark the original requirement as answered or describe that search as satisfying the omitted condition. Include ambiguous identity, missing evidence, fail-closed query errors and a genuinely unsupported question.

## 3A. Admission versus requirement-satisfaction validation

The [corrective admission investigation](../reports/parliamentary-research-assistant/corrective-admission-review.md) showed that eight of ten intentionally incomplete proposals were accepted by existing admission checks. They were **injected proposals**, not observed real-model error frequencies. The next bounded validation must keep retrieval admission, requirement satisfaction and report-claim acceptance separately observable.

### Negative controls — no unsupported promotion

| Original intent or condition | Possible supporting retrieval | Must **not** be treated as established |
|---|---|---|
| Which **housing** Bills did Malcolm Byrne sponsor? | All recorded Bills sponsored by the Member | Housing subject classification without independent subject evidence |
| Which Bills did the Member **oppose**? | A separately justified sponsorship/background inquiry, if genuinely useful | Opposition inferred from sponsorship; absent a justified supporting purpose, skip irrelevant retrieval |
| R1: sponsored Bills **and their progress/outcomes** | Sponsorship list | Stages, enactment or final outcomes until their own evidence exists |
| R3: constituencies **and parliamentary roles** | Career constituency history | Officeholding and other roles |
| Constituencies **during ministerial service** | All career constituencies | Ministerial-service temporal intersection |
| Bills that **became law** | Recorded Bills/sponsorship | Enactment without accepted legislative evidence |
| Bills sponsored **as a Senator** | General sponsorship | Senator-specific role or period |
| Bills **primarily** sponsored | General sponsorship | Primary sponsor classification |
| Before a stated date | Untimed historical listing, if independently useful | The requested date filter |
| A second date-qualified request | A broader listing, if justified | The specified date relationship |

The exact saved control payloads and two date-refusal outcomes remain in `docs/reports/parliamentary-research-assistant/corrective-admission-live.json`. Do not replace them with easier paraphrases or infer unsupported relationships from labels.

**Pass conditions:** each accepted retrieval accurately describes its **own** verified operation and is relevant to an explicit subsidiary question; no material omitted condition is automatically closed; no resulting report claim wrongly adopts that condition; every unsupported parent condition retains a visible unmet disposition. If a tool is not genuinely relevant, declining to dispatch is a valid outcome. A blanket model-labelled “entailed” span, token coverage or a cited query result does not count as independent satisfaction proof.

### Positive controls — useful supporting research

- For **housing Bills**, a supported sponsorship listing can be admitted **as initial evidence**; housing classification remains unresolved until independently supported.
- For **R1**, validated sponsorship evidence supports a list, and separate exact Bill lifecycle lookups support individual recorded stages. Neither is treated as certifying all outcomes or complete source coverage.
- For **R3**, validated constituency/term history may support the representation portion even if discovery of other parliamentary roles remains unavailable.
- When a directly supported complete requirement is asked (e.g. an exact supported party-Member count with compatible date and unit), the answer must not be unnecessarily blocked or require a per-query confirmation.

Test ordinary wording and injected incomplete proposals separately. Measure erroneous **answer promotion** and unnecessary **user interruptions** as well as query success. A correct retrieval is not a complete research answer.

### Evidence and report gate

Require a proposed minimal, auditable representation of `research requirement → supporting operation → validated fact → claimed satisfaction/report claim`, including exact relation and time scope, evidence reference and unresolved conditions. Demonstrate that selected operation semantics and accepted result fields support the particular fact or simple approved deterministic derivation; do not rely on LLM self-verification or a citation alone. It is acceptable to withhold a conclusion when a general-language binding cannot be independently established. No universal natural-language equivalence or prose-verification theorem is required.

The next OpenCode tranche is **design validation**, not corrective app delivery: reproduce negative/positive cases, propose and evaluate a narrow mechanism, and stop at a human gate. A zero-promotion result on this small frozen set establishes only bounded feasibility, not general safety or product acceptance.

## 4. Four independent acceptance dimensions

| Dimension | Required outcome | Failing examples |
|---|---|---|
| **Language understanding** | Captures the research purpose, entities, time scope, comparison and all material qualifications across ordinary paraphrases; asks only meaningful clarifications. | Entity-name extraction only; rigid allowed-word list as normal entry point; unacknowledged dropped qualifier. |
| **Research usefulness** | Proposes relevant subsidiary questions; pursues supported work automatically; provides an informative answer where possible, and makes outstanding questions clear. | Cosmetic report made of table cells; safe but unhelpful blanket refusal when independent evidence exists. |
| **Editorial quality** | Coherent, explanatory, plain-English report and dialogue in the [editorial contract](parliamentary-research-assistant-editorial.md); parliamentary terms used accurately. | “Member IRIs”, “accepted witnesses”, internal status strings or jargon in normal report prose; meaningless comparison as primary research. |
| **Factual integrity** | Every substantive claim supported by accepted evidence/approved background; supporting retrieval is distinguished from satisfied requirements, with no unsupported joins, dates, causal claims or false completeness; limitations survive export. | A cited sponsorship list presented as answering opposition, housing, primary-sponsor or enactment questions; claiming a complete roster from uncertified local records. |

**All four dimensions must pass.** Safe refusal is positive evidence of restraint, not proof the assistant completed the research. The LLM's own confidence or self-graded evaluation does not determine acceptance.

## 5. Evaluation method

1. **Freeze the materials before running:** user/independent researcher-authored briefs where available; separately label AI-authored cases and constructed negative controls. For each, freeze intended meaning, material requirements, expected evidence type and supported/unsupported boundary based on the actual selected revision and dataset. No invented or prefilled factual answer totals.
2. **Run actual end-to-end research interactions:** real model interpretation, typed compiler calls, the evidence store and LLM report writing. Retain all proposals, clarifications, rejections, operations, results, report revisions and user-visible text.
3. **Score separately:** complete-intent preservation, factual answer validity, useful handling of gaps, editorial readability and interaction interruptions. Record per-requirement outcomes; do not pool safe refusals into factual success.
4. **Review independently:** a human evaluator assesses the report as a parliamentary reader, with source evidence available for factual checking. The implementation agent must not judge its own prose as sufficient.
5. **Verify the UI:** research plan visibly precedes initial execution; the report progresses; conversation can modify it; source details and unsupported requirements remain accessible; keyboard, responsive, export and failure states comply with the v0.4 UI contract.
6. **Keep limitations visible:** accepted findings are relative to tested revisions, model settings and available data; no claim of broad generalisation from a small set of scenarios.

## 6. Acceptance gate for the next corrective vertical slice

This is a **proposed gate**, not implementation authorisation:

- At least one substantial research brief from **R1–R3** produces a readable evidence-backed report with genuinely LLM-led interpretation, research planning and prose (not a fixed report template).
- Demonstrate **a second domain** through an independently checked research flow or a well-evidenced bounded limitation; a successful party-count comparison cannot be the only operational demonstration.
- R4 and R5 demonstrate truthful, useful treatment of unsupported composition/content needs, without invented findings or silent simplification.
- At least one real multi-turn refinement modifies an existing plan/report; unrelated accepted findings survive.
- Every material original requirement is answered, partly supported with outstanding conditions visible, explicitly pending/unsupported, or clarified; no unsafe query admission or promotion of supporting evidence into an unsupported answer.
- Independent reviewers accept editorial usefulness and comprehensibility. All required existing/new compiler safeguards and end-to-end browser checks pass.
- Record remaining deficits rather than broadening compiler/ETL scope to chase every possible question. If genuine research dialogue or grounded narrative cannot be achieved with the chosen architecture, stop for design review rather than declaring success from integration tests.

Passing the adapter test suite, R6 or a polished UI alone does **not** meet this gate.

## 7. Status and authority

Phase 1's adapter, trace preservation and progressive rendering are technical assets, not proof that the v0.4 experience is delivered. The mandatory **supporting-retrieval versus requirement-satisfaction design-validation gate** precedes a separately authorised corrective implementation. This contract also defines the later human/product acceptance gate. It does not approve a corrective app build, compiler expansion, data reload, external-source access or public deployment.
