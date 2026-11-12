# Parliamentary Research Assistant — Research Acceptance Contract

**Version:** 1.2 · **Date:** 12 November 2026  
**Status:** Approved design contract; implementation not authorised  
**Parent:** [Parliamentary Research Assistant v0.5](parliamentary-research-assistant.md)  
**Companion:** [Editorial standard](parliamentary-research-assistant-editorial.md)

## 1. Purpose

The user must obtain **useful parliamentary research**, not merely a valid database response. Automated compiler tests remain necessary but cannot establish product acceptance. Evaluate **natural-language understanding, research usefulness, editorial quality and factual integrity separately**.

The generated report is an **evidence-grounded draft for researcher review**, not a machine-certified proof that every condition in arbitrary language has been captured and fully answered. The system must preserve the user's original brief, show its interpretation, and clearly distinguish **direct facts, deterministic derivations, provisional interpretations and hypotheses**. Its established factual claims must not exceed accepted evidence; automatic certification of unrestricted prose is not required or claimed.

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

The [corrective admission investigation](../reports/parliamentary-research-assistant/corrective-admission-review.md) showed that eight of ten intentionally incomplete proposals were accepted by existing admission checks. They were **injected proposals**, not observed real-model error frequencies. The subsequent [retrieval/satisfaction validation](../reports/parliamentary-research-assistant/retrieval-satisfaction-validation.md) established that ledger-only completeness missed omitted conditions, while an independent original-intent hold prevented even ordinary complete questions from being closed. **That automatic exhaustive-certification gate is retired** in v0.5. Preserve the controls to test whether a draft presents unsupported assertions as established facts, and measure omissions during independent human evaluation—not as a demand for a universal semantic binder.

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

**Pass conditions:** each accepted retrieval accurately describes its **own** verified operation and has a defensible subsidiary purpose. The report must not claim that a missing relationship, filter, temporal condition or outcome was established by that result. Known unsupported conditions should remain visible; independently reviewed omissions are recorded as language-understanding/research-quality failures, not treated as automatically discovered or waived. A model-labelled “entailed” span, token coverage, claim badge or cited query result is not independent proof of a stronger factual assertion. If an operation is irrelevant, declining to dispatch is appropriate.

### Positive controls — useful supporting research

- For **housing Bills**, a supported sponsorship listing can be admitted **as initial evidence**; housing classification remains unresolved until independently supported.
- For **R1**, validated sponsorship evidence supports a list, and separate exact Bill lifecycle lookups support individual recorded stages. Neither is treated as certifying all outcomes or complete source coverage.
- For **R3**, validated constituency/term history may support the representation portion even if discovery of other parliamentary roles remains unavailable.
- When a directly supported complete requirement is asked (e.g. an exact supported party-Member count with compatible date and unit), the answer must not be unnecessarily blocked or require a per-query confirmation.

Test ordinary wording and injected incomplete proposals separately. Measure erroneous **answer promotion** and unnecessary **user interruptions** as well as query success. A correct retrieval is not a complete research answer.

### Evidence and report gate

The application must expose a minimal, auditable relationship among `original brief → proposed subsidiary question → accepted operation/fact → assertion → evidence class/reasoning/limitations → report draft`. Every Level 1 statement of fact needs an actual accepted source-supported proposition; every Level 2 statement needs a reproducible approved calculation. A reference is insufficient if its evidence does not establish the *asserted* relationship or date. Model-authored Level 3/4 prose remains provisional and human-reviewable; it must not be falsely marked verified.

**Do not require a universal semantic binder** to certify complete original-language interpretation or unbounded free prose before useful research can be shown. A missing material requirement discovered by an independent reviewer is nevertheless an evaluation failure, to be recorded and corrected in the measured class. The withheld design failures remain valid cautionary evidence, not an automatic veto on an evidence-grounded draft.

### Evidence and Interpretation Confidence checks

| Level | Acceptance test | Failure |
|---|---|---|
| **1 — Directly supported** | Exact assertion matches accepted fact semantics: entity, predicate, dates, source and scope. | LLM labels a sponsorship result as opposition or a recorded Bill status as enactment. |
| **2 — Calculated/derived** | Reproducible approved calculation uses compatible accepted facts, scope and units. | An unapproved join, conflated time periods or unsupported arithmetic claim. |
| **3 — Evidence-based interpretation** | LLM provides evidence refs, assumptions, limitations and **provisional** high/moderate/low confidence with a reviewable rationale. | Treating interpretation or its confidence as machine-verified truth, ignoring contradictory evidence, or giving an unsupported “high” rating. |
| **4 — Hypothesis** | Clearly labelled unverified possibility appears only in a designated discussion/further-investigation section; if unmotivated, it is a research question instead. | Hypothesis mixed with established findings, invented causal history, or a probability/confidence presented as evidence. |

Evaluate high/moderate/low using the editorial rubric (directness, independent corroboration, contradictions, source gaps and assumptions). No numerical confidence percentages unless separately calibrated and authorised. Source quality, freshness and completeness must remain **distinct** from both evidence class and interpretation confidence.

### Display and lifecycle checks

- Substantive findings have unobtrusive, keyboard-accessible evidence indicators; a reader can open the source, reasoning, assumptions, class, confidence if applicable, limitations and provisional/reviewed status.
- Main prose contains natural uncertainty language; an indicator alone is insufficient. No technical classification is required beside every sentence.
- Export retains draft status, evidence references, interpretation/hypothesis labels and material qualifications.
- Conversation/section revisions retain source links and assertion identities, invalidate changed dependencies and **do not silently promote** Level 3/4 prose to Level 1/2.
- Human review must be able to challenge or reclassify a provisional interpretation without changing accepted source facts.

## 4. Four independent acceptance dimensions

| Dimension | Required outcome | Failing examples |
|---|---|---|
| **Language understanding** | Captures the research purpose, entities, time scope, comparison and all material qualifications across ordinary paraphrases; asks only meaningful clarifications. | Entity-name extraction only; rigid allowed-word list as normal entry point; unacknowledged dropped qualifier. |
| **Research usefulness** | Proposes relevant subsidiary questions; pursues supported work automatically; provides an informative answer where possible, and makes outstanding questions clear. | Cosmetic report made of table cells; safe but unhelpful blanket refusal when independent evidence exists. |
| **Editorial quality** | Coherent, explanatory, plain-English report and dialogue in the [editorial contract](parliamentary-research-assistant-editorial.md); parliamentary terms used accurately. | “Member IRIs”, “accepted witnesses”, internal status strings or jargon in normal report prose; meaningless comparison as primary research. |
| **Factual integrity** | Established Level 1/2 claims have verified support; Level 3/4 language is clearly provisional, appropriately supported as interpretation or unverified speculation; missing relationships, dates and completeness are not presented as facts; limitations survive export. | A cited sponsorship list presented as opposition, housing or enactment evidence; an LLM-generated label claiming machine verification of an interpretation; a hypothesis presented as a historical fact. |

**All four dimensions must pass.** Safe refusal is positive evidence of restraint, not proof the assistant completed the research. The LLM's own confidence or self-graded evaluation does not determine acceptance. A coherent **research draft** can pass without independently certified exhaustive interpretation, provided its established facts are properly supported, its provisional prose is clearly identified and independent reviewers find it useful and not misleading.

## 5. Evaluation method

1. **Freeze the materials before running:** user/independent researcher-authored briefs where available; separately label AI-authored cases and constructed negative controls. For each, freeze intended meaning, material requirements, expected evidence type and supported/unsupported boundary based on the actual selected revision and dataset. No invented or prefilled factual answer totals.
2. **Run actual end-to-end research interactions:** real model interpretation, typed compiler calls, the evidence store and LLM report writing. Retain all proposals, clarifications, rejections, operations, results, report revisions and user-visible text.
3. **Score separately:** ordinary-language interpretation fidelity (including known or independently discovered omissions), established factual assertion validity, classification correctness, interpretation-confidence calibration plausibility, handling of gaps, editorial readability and interaction interruptions. Record per-requirement outcomes; do not pool safe refusals into factual success.
4. **Review independently:** a human evaluator assesses the report as a parliamentary reader, compares it with the untouched original brief, and checks material factual assertions, provisional interpretation and hypotheses against the linked evidence. The implementation agent must not judge its own prose or confidence labels as sufficient.
5. **Verify the UI:** research plan visibly precedes initial execution; the report progresses; conversation can modify it; unobtrusive evidence indicators and qualifications remain accessible; keyboard, responsive, export and failure states comply with the v0.5 UI contract.
6. **Keep limitations visible:** accepted findings are relative to tested revisions, model settings and available data; no claim of broad generalisation from a small set of scenarios.

## 6. Acceptance gate for the next corrective vertical slice

This is a **proposed gate**, not implementation authorisation:

- At least one substantial research brief from **R1–R3** produces a readable evidence-backed report with genuinely LLM-led interpretation, research planning and prose (not a fixed report template).
- Demonstrate **a second domain** through an independently checked research flow or a well-evidenced bounded limitation; a successful party-count comparison cannot be the only operational demonstration.
- R4 and R5 demonstrate truthful, useful treatment of unsupported composition/content needs, without invented findings or silent simplification.
- At least one real multi-turn refinement modifies an existing plan/report; unrelated accepted findings survive.
- The original brief, proposed interpretation and known unanswered requirements remain visible; independent evaluation records any missing material requirements. **No claim of exhaustive automatic intent certification** is made. Supporting evidence is not promoted to an unsupported established factual assertion.
- The report is labelled **Draft — for review**. Level 1/2 facts are traceable and accurately scoped; Level 3 confidence is qualitative, provisional and reviewable; Level 4 hypotheses appear only in the designated area. Qualifications, evidence indicators and assertion class survive export and revision.
- Independent reviewers accept editorial usefulness, accuracy of factual claims, appropriate treatment of provisional reasoning, and comprehensibility. All required existing/new compiler safeguards and end-to-end browser checks pass.
- Record remaining deficits rather than broadening compiler/ETL scope to chase every possible question. If genuine research dialogue, compiler-verified factual components or honest assertion classification cannot be achieved, stop for design review rather than declaring success from integration tests. **Do not stop only because a universal arbitrary-language or free-prose completeness proof is unavailable.**

Passing the adapter test suite, R6 or a polished UI alone does **not** meet this gate.

## 7. Status and authority

Phase 1's adapter, trace preservation and progressive rendering are technical assets, not proof the v0.5 research experience is delivered. The admission/satisfaction design-validation tranche concluded **NO-GO for automatic exhaustive completeness certification**; that gate is retired for the **evidence-grounded, human-reviewed research draft** product model. The above assertion-level tests and independent product/editorial review are now the acceptance criteria. This specification does not itself approve a corrective app build, compiler expansion, data reload, external-source access or public deployment.
