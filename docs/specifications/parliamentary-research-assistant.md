# Parliamentary Research Assistant
## Product, UI and Architecture Specification — v0.5

**Project:** OireachtasOntology  
**Date:** 12 November 2026  
**Status:** Approved design decisions; implementation not authorised  
**Branch:** `parliamentary-research-assistant`  
**Companion contracts:** [Editorial and plain-language standard](parliamentary-research-assistant-editorial.md) · [Research acceptance scenarios](parliamentary-research-assistant-acceptance.md)

> **v0.5 research authority decision (12 November 2026):** The assistant produces **evidence-grounded research drafts for human review**, not independently certified exhaustive answers to arbitrary ordinary-language questions. The LLM leads research and explanatory writing; the compiler validates factual operations; approved deterministic calculations derive bounded results. Substantive assertions are classified by their distance from evidence, with provisional qualitative confidence for interpretations. Model-authored prose and the completeness of the overall investigation remain reviewable, not automatically certified. The guarded compiler and factual evidence boundaries are not relaxed. **Implementation remains subject to a separate bounded authorisation.**

> **Earlier v0.4 decision retained:** Distinguish admissible supporting retrieval from satisfying the full original research question. A correctly scoped supporting search must never be represented as establishing a stronger relationship, filter or outcome that its evidence does not show.

> **Previous product finding:** Phase 1 demonstrated guarded compiler integration and progressive UI mechanics, but user assessment found its deterministic word-list input and fixed party-count report unusable as research assistance. These remain rejected product patterns.

---

## 1. Product Definition

The Parliamentary Research Assistant is an **LLM-led, evidence-constrained research collaborator**. It works with a user to understand a useful parliamentary research question, identify subsidiary questions, obtain supported evidence, write a comprehensible report and refine that report through conversation.

- **LLM:** research dialogue, proposed questions, planning, tool selection, explanations and report authorship.
- **Coordinator:** requirement tracking, validated execution, approval limits, dependency management, assertion/evidence provenance and selective report revision; it does **not** purport to independently certify the completeness of arbitrary-language interpretation.
- **Existing compiler:** authoritative supported queries, identity resolution, temporal semantics, safe execution and factual evidence.
- **User:** authority over research aims and decisions that materially change meaning or scope; reviews the research draft and determines whether it adequately answers the brief.

It must neither generate unrestricted authoritative SPARQL nor reduce the LLM to extracting names for predetermined reports.

### 1.1 Product objectives

Users should be able to ask substantive parliamentary research questions in ordinary language; discuss scope; view an understandable plan before execution; receive validated findings automatically; read reports with narrative substance; inspect evidence; and ask follow-ups that change or improve the same report.

Partial research can be useful, provided that unanswered questions and evidence limitations are explained. Merely refusing a multi-part brief when independent portions are answerable is not sufficient research assistance.

**Product status:** A generated report is a **draft for researcher review**. Validated findings in that draft may be relied on at their stated scope, but the application must not claim that every requested question has been recognised, fully answered or independently checked as prose.

### 1.2 Research-first domain selection

Begin from real parliamentary needs, not the easiest compiler query. Expose **several domains with bounded, verified existing capabilities**: candidate areas include Members and representation, Bills and legislative progress, and parliamentary offices/careers. Availability must be verified operation by operation on the selected revision and dataset. Committee and Debate questions are useful explicit coverage-boundary tests.

The current-Dáil party-count comparison remains an integration regression, not a meaningful primary product acceptance scenario.

### 1.3 Contract hierarchy

This document governs product, UI and architecture. The [editorial contract](parliamentary-research-assistant-editorial.md) governs visible language and report content; the [acceptance contract](parliamentary-research-assistant-acceptance.md) defines research scenarios and the independent product gate. Approved compiler contracts remain authoritative for executable semantics; these documents do not create new operations.

The approved v0.2 two-pane layout, evidence access, responsiveness and accessibility requirements remain in effect unless explicitly strengthened here.

---

## 2. Agreed Interaction Model

### 2.1 Hybrid autonomy

The LLM interprets research purpose, proposes relevant subsidiary questions and plans work; the coordinator automatically invokes verified in-scope tools. Material ambiguity, assistant-proposed changes of period/relationship/measure, or a new evidence source require a user decision. Explicit user-requested changes are already authorised.

### 2.2 Visible research plan

**Approved:** The assistant publishes a concise plan before initial factual query execution. Plan items are **research questions and expected findings**, not compiler function names. The plan is updated when the user refines the brief. Routine supported operations do not require separate approval.

### 2.3 Progressive report

**Approved:** The report develops as validated findings are available. The LLM authors coherent explanatory prose from evidence; tables support the narrative rather than replace it. Pending, blocked and partially answerable requirements remain visible. Factual prose cannot precede accepted evidence.

### 2.4 Genuine ongoing conversation

The user may ask why a finding matters, what remains unknown, request clearer explanations, challenge source evidence, introduce a new scope or revise a section. The assistant responds to the research context, updates affected plan/report items and reuses unaffected accepted evidence. Editorial changes must not require re-querying facts unnecessarily.

### 2.5 Safe understanding without an exhaustive-language gate

The ordinary-language interface must not depend on a fixed list of permissible brief words. An LLM interpretation is a proposal, not semantic authority. Preserve the original brief, material conditions and subsequent changes in a requirement ledger. **Do not require every subsidiary search to express the entire original requirement.** Research often needs partial or contextual retrieval.

### 2.6 Supporting retrieval is not an answer

There are **three distinct activities**:

1. **Query admissibility:** A proposed supporting question has an explicit, accurate, bounded meaning of its own; a verified typed operation implements that meaning, with full compiler validation. Its role in the plan is labelled as *supporting*, *direct* or *exploratory*. This does not certify the parent request.
2. **Research requirement assessment:** The LLM proposes what appears to be answered, partly addressed or outstanding. Keep original wording visible and make known unresolved conditions explicit. Do not certify that the model has identified **every** semantic condition in arbitrary language. The overall report's completeness is a matter for researcher review, not a hidden all-conditions gate that blocks ordinary supported questions.
3. **Assertion classification and review:** Direct facts and approved deterministic derivations have defined trusted support. LLM explanations are clearly distinguished as provisional interpretations or hypotheses; their prose is **not** automatically certified merely by attaching a reference. Do not state an unsupported specific relationship or outcome as an established fact, even in fluent prose.

For example, retrieving all Bills sponsored by a named Member can support an investigation into **housing Bills**, but it cannot determine which concern housing. A sponsorship query does not establish **opposition**. Constituency history does not establish parliamentary **roles** or constituencies **during ministerial service** without the required relationship and time evidence. If such conditions cannot be checked, retain them explicitly as unanswered.

Relevant supporting retrieval can proceed automatically within approved scope; **no routine per-query confirmation** is required. A tool which has no defensible research relevance should not run merely because it is executable. No blanket plan approval or model-assigned “entailed” label waives unmet conditions. Ask for user input only for genuine material ambiguity, scope alteration or new evidence authority.

The coordinator must not claim universal natural-language equivalence or unrestricted prose verification. Use operation-specific evidence semantics for confirmed facts and calculations; make remaining research questions and model interpretations transparent. Failure to independently certify **full parent-intent binding** is not by itself a reason to block a useful report draft. It remains a reason **not to claim exhaustive completion**.

### 2.7 Evidence and interpretation confidence

Each substantive assertion is identified as one of four evidence classes:

1. **Level 1 — Directly supported:** A specific fact is established by an accepted compiler result or approved reference, preserving source, identity, relationship, reporting period and limitations.
2. **Level 2 — Calculated or derived:** A reproducible, approved deterministic operation derives the assertion from accepted facts with compatible scopes.
3. **Level 3 — Evidence-based interpretation:** The LLM offers a reasoned explanation based on identified findings, beyond what the records explicitly establish. Its classification and qualitative confidence (**high, moderate, low**) are **provisional**; the user may challenge or revise them.
4. **Level 4 — Hypothesis or unverified inference:** A clearly labelled possibility for further investigation, not an established finding. Show only in a distinct discussion/further-investigation area; do not assign a pseudo-precise likelihood or present unsupported speculation as substantive research.

These describe **evidential basis and distance from evidence**, not probability of truth. The presence of a direct source does not certify its completeness or freshness. Separate source coverage, recency, contradictions and scope limitations from the assertion level. No numerical self-reported LLM confidence percentages are permitted in the initial implementation.

The compiler/evidence layer, not the LLM, authorises Level 1; approved deterministic calculations authorise Level 2. The LLM proposes Levels 3–4 with explicit assumptions and evidence references; those assessments remain provisional and subject to human review. It cannot upgrade an unsupported claim to Level 1 or 2 by changing a label.

# Part A — User Interface Specification

## 3. Information Architecture

### 3.1 Primary application layout

The desktop application comprises:

**A. Application header**

Provides the application identity, current research session title, execution status and high-level controls.

**B. Conversation panel**

Used for user requests, assistant responses, research planning, clarifications and report refinement.

**C. Report panel**

A persistent report document displaying headings, factual findings, tables, narrative and supporting evidence.

**D. Research activity drawer**

An on-demand panel containing detailed research plan status, query execution history, evidence status and technical explanations.

The conversation and report are the two primary surfaces.

The research activity drawer must not permanently compete with them for horizontal space.

### 3.2 Primary navigation

The MVP is a single research workspace, not a multipage dashboard.

It should not require separate pages for planning, query execution and report writing.

The user can move between conversation, report and research activity without losing conversational or report context.

---

## 4. Desktop Screen Layout

### 4.1 Layout proportions

At desktop widths of approximately 1200 pixels or greater:

| Region | Proposed behaviour |
|---|---|
| Application header | Full width, fixed at top |
| Conversation panel | Approximately 32% of workspace |
| Report panel | Approximately 68% of workspace |
| Research activity | Slide-over or expandable drawer |
| Composer | Anchored to bottom of conversation panel |

The report should receive more horizontal space because it is the primary research output.

The conversation and report panels should scroll independently.

Where practical, users should be able to resize the division between conversation and report.

### 4.2 Header

Display:

- Parliamentary Research identity.
- Current research title.
- Overall research state.
- Research Activity control.
- Pause/Resume control when execution is active.
- Report export control when report content is available.
- New research action.

Avoid displaying raw query counts or technical service status prominently unless they materially affect the user's current work.

### 4.3 Conversation panel

The panel contains:

- User messages.
- Concise assistant messages.
- Research plan cards.
- Clarification and approval cards.
- Notices concerning unsupported requirements.
- A persistent message composer.

Messages should be visually distinguishable by speaker without large decorative chat bubbles.

Long technical details should be collapsed by default.

The conversation should not duplicate the entire report.

### 4.4 Report panel

The report panel resembles a readable document rather than a conventional dashboard.

It contains:

- Report title.
- Short description and scope.
- Report status.
- Structured sections.
- Factual tables and summaries.
- Evidence references.
- Limitations and unanswered questions.
- Section-level refinement actions.

The report remains visible while the assistant conducts further research.

---

## 5. Screen and State Specifications

### S1 — New Research

**Purpose:** Invite a useful research objective, not a database exercise.

Show a prominent multiline composer labelled **What would you like to find out?**, a **Start research** action and examples reflecting meaningful parliamentary research needs (e.g. a Member's Bills and their progress, or changes in constituency representation). Examples are research prompts, not promises that every part is supported. The report shows an understated document empty state.

### S2 — Preparing Research

The LLM interprets the brief as a research purpose, identifies subsidiary questions and distinguishes genuinely material ambiguities. The assistant summarises what it intends to investigate in plain language; it does not just extract entity names. Unsupported requirements are retained. Publish the initial plan visibly before dispatching any factual query.

### S3 — Research in Progress

Plan items address research questions, such as "Which Bills are associated with this Member?" or "What documented stages can be established?", not operation identifiers. Mark a subsidiary search as **supporting evidence** when it does not itself answer the parent question. Supported factual requests run automatically; only adequately supported claims populate answered portions of the report. The user may discuss and refine the investigation during the run. Unanswerable conditions remain visible even when useful supporting results were found.

### S4 — Clarification Required

Explain the uncertainty, why its resolution changes the evidence selected, and grounded choices. Example: "Do you want the TDs representing Dublin Central at the start of each Dáil, or anyone who served during each term?" Do not select a materially different meaning without approval. Continue independent supported tasks.

### S5 — Initial Research Completed

Once the initial research plan has finished:

- The report displays its available validated findings.
- The research status changes to Completed or Completed with limitations.
- The assistant provides a concise summary of what was achieved.
- Any unanswered requirements remain visible.
- The user can refine the report or extend the investigation.

Completion does not imply complete underlying data coverage.

### S6 — Research Interrupted or Failed

Display the reason for interruption and identify affected tasks.

Distinguish:

- The query service being unavailable.
- An operation being unsupported.
- A query returning no verified matches.
- Insufficient or incomplete evidence.
- A resource or execution limit being reached.

Valid earlier findings must remain accessible.

The user should not lose the report because a later query fails.

---

## 6. Conversation Component Specification

### 6.1 Message composer

The composer is persistent and supports multiline input.

Required behaviour:

- Enter submits a message.
- Shift+Enter inserts a line break.
- Submission is disabled for an empty message.
- The message is preserved if submission fails.
- The user can send requests during ongoing research.
- An obvious control allows the user to pause further query dispatch.

The composer should encourage ordinary conversational requests rather than require predefined command syntax.

### 6.2 Assistant messages

The assistant speaks as a helpful, impartial parliamentary research colleague. It discusses the purpose of the investigation, explains meaningful findings, asks necessary clarifications and supports follow-up questions that genuinely revise the research/report. It does not fill the conversation with query-completion notices. Advanced query details belong in Research Activity.

All user-visible messages follow [the editorial standard](parliamentary-research-assistant-editorial.md). Responses that merely say "refinement requires Phase 2" are non-compliant with the intended v0.5 experience.

### 6.3 Research plan card

The plan card contains:

- Research objective, including the material conditions in the original brief.
- Proposed subsidiary research questions and their relevance.
- A visible distinction between **supporting evidence retrieved** and **requirements answered**.
- Status of each task and unresolved requirement.
- Any explicit scope assumptions.
- A control to expand detailed plan information.

Initial plan publication should be apparent before the first result arrives.

A revised plan must identify newly added or changed research requirements.

### 6.4 Approval and clarification cards

Cards requiring decisions must have clearly labelled choices and an explanation of their consequences.

They must not use misleading default selections.

Pending decisions remain accessible until resolved or superseded by the user.

### 6.5 Conversation-to-report interaction

The user can select a report section and request refinement without manually copying its title or contents into the conversation.

Example section actions:

- Refine this section.
- Explain this finding.
- Investigate further.
- View supporting evidence.

The selected section becomes the context of the next conversational request.

---

## 7. Report Interface Specification

### 7.1 Report structure

The LLM proposes a report structure that suits the user's research purpose. Typical elements are a meaningful title, scope, answer-oriented summary where supported, thematic findings, tables/timelines where valuable, remaining questions and evidence references. A report does not have to follow one inflexible template.

**Reports need narrative substance:** explain what was investigated, what the available records establish and what those findings may mean **within the limits of the evidence**. A successful supporting search can be described as *what the records show*, but not as a full answer to an outstanding question. Separate confirmed facts and deterministic derivations from provisional interpretations, hypotheses and unresolved questions. Do not invent causal explanations or institutional background; a labelled hypothesis is not permission to manufacture a factual history. A list of Member totals and database rows, however accurate, is not an adequate research report.

The document as a whole remains a **research draft for human review**. Verified factual components are not a certificate that its LLM-authored prose is entirely correct or that the original brief has been exhaustively answered.

### 7.2 Section states

Each section has one of the following states:

| State | Display |
|---|---|
| Pending | Heading and concise awaiting-evidence message |
| Populating | Validated content available; additional work in progress |
| Validated | Specific factual evidence accepted for the section; not certification of the whole research brief or free-form prose |
| Incomplete | Partial findings with explicit qualifications |
| Blocked | Content cannot be completed, with reason |
| Unsupported | Requested operation unavailable |
| Needs revision | Existing content requires revalidation after a scope change |

A section's state must be visible through text and appropriate iconography, not colour alone. Overall report status should indicate **Draft — for review** even if every available tool step is complete. Section status and assertion evidence level are different concepts.

### 7.3 Progressive updates

Report updates must:

- Preserve existing content unless new evidence or an authorised revision changes it.
- Avoid rewriting unrelated sections.
- Preserve reading position wherever possible.
- Avoid sudden layout shifts.
- Clearly indicate when new validated findings are available.
- Never present temporary generated prose as established factual content.
- Keep claim identifiers, evidence classifications, source links and uncertainty visible across section edits; avoid silently upgrading provisional text to verified facts.

Each section should have a stable identity independent of its displayed heading.

### 7.4 Factual tables

Tables should provide:

- Meaningful column headings.
- Clearly identified units and reporting periods.
- Accessible source or evidence references.
- Appropriate handling of long names and labels.
- Consistent formatting for counts, dates and measures.

On small screens, tables may scroll horizontally rather than truncate important factual values.

The LLM must not introduce unsupported summary rows or totals.

### 7.5 Report editing

**Required conversation-led refinement:** The user can question, clarify, redirect, shorten, expand or reorganise findings and the assistant updates the same plan/report rather than requiring a new research session. Section actions may include **Explain**, **View evidence**, **Rewrite clearly** and **Investigate further**.

Factual scope changes invalidate only dependent findings and require fresh validated evidence; purely editorial revisions preserve supporting references. Distinguish user-authored text from evidence-backed claims. Direct rich-text editing remains out of scope for the next bounded slice.

### 7.6 Report export

For the MVP, provide a straightforward way to copy or export the current report as Markdown.

Export must preserve the **Draft — for review** status, factual qualifications, evidence references, material unanswered questions and any Level 3/4 interpretation or hypothesis labels. An exported copy must not imply automatic editorial or exhaustive-completeness certification.

PDF, Word, collaborative editing and formal document publication are outside the initial scope.

An incomplete report must retain its incomplete status in exported content.

---

## 8. Research Activity and Evidence Inspection

### 8.1 Activity drawer

The drawer contains three sections:

**Research plan**

The complete current plan, including task status and dependencies.

**Execution history**

Operations performed, their outcome and any relevant error or limitation.

**Evidence**

Evidence associated with factual findings, including the originating request and source provenance.

### 8.2 Query inspection

For an executed operation, users should be able to inspect:

- The factual request submitted.
- Selected operation and parameters.
- Interpretation and temporal scope.
- Validation outcome.
- Execution outcome.
- Returned result summary.
- Available provenance.

Raw plan JSON, SPARQL and diagnostics should be placed in advanced disclosures.

Where supported by the query service, existing Interpreted, Compiled and Executed explanations can be reused.

### 8.3 Evidence navigation

A factual statement or table should link to its supporting evidence.

Selecting an evidence reference opens the relevant details without navigating away from the report.

Where multiple claims rely on the same validated result, they may share an evidence reference.

The interface must distinguish direct RDF evidence, approved deterministic derivation, provisional LLM interpretation and hypothesis. Important findings should have a small, keyboard-accessible **evidence indicator** with a plain-text label and expandable evidence/reasoning details; do not clutter every sentence with coloured tags. Never rely on colour alone.

The evidence inspector should show, for a selected assertion: its exact wording or structured fact, evidence class, confidence where applicable, linked records, derivation/reasoning, assumptions, conflicts, source limitations and review state. The user can challenge its classification or ask for a clearer explanation. Hypotheses belong in a distinct **Further questions / Possible explanations** section, not among confirmed findings. If there is insufficient evidence even to motivate a hypothesis, formulate a research question instead.

### 8.4 Research limitations

The activity drawer should expose all unresolved requirements, but important limitations must also appear in the report itself.

Users must not have to inspect debugging controls to discover that a substantive research question went unanswered.

---

## 9. Visual Design System

### 9.1 Visual direction

**Professional, restrained, document-oriented and readable in the editorial tradition of Oireachtas.ie.** Preserve the approved two-pane layout, activity drawer, responsive behaviour and accessible component states. The workspace is for research reading and dialogue, not a technical developer console. Plain language is an interface requirement, not optional post-processing.

### 9.2 Colour

Proposed palette:

- Warm off-white application background.
- White document and conversation surfaces.
- Deep navy or charcoal primary text.
- Restrained gold accents for identity and selected actions.
- Neutral grey metadata and secondary controls.
- Accessible semantic colours for warnings and error states.

Gold should not be used for substantial body text or as the sole indication of status.

All combinations must meet the specified accessibility contrast requirements.

### 9.3 Typography

Use a highly legible contemporary sans-serif UI font.

Recommended minimums:

- Body text: approximately 16px.
- Secondary metadata: approximately 14px.
- Report headings: visibly differentiated but restrained.
- Comfortable line height and paragraph spacing.

Report prose should have a constrained reading width of approximately 70–85 characters per line where practical.

### 9.4 Surface treatment

Use:

- Subtle boundaries between workspace regions.
- White document surfaces against a warm background.
- Limited shadow and restrained corner rounding.
- Clear typographic hierarchy.
- Generous report whitespace.
- Compact conversational controls.

Avoid ornamental imagery, excessive status badges, animated decorations or large empty dashboard cards.

### 9.5 Icons

Icons supplement rather than replace descriptive labels.

Use consistent iconography for conversation, report, activity, evidence, pause, clarification, warning and completed work.

Meaningful status must always be conveyed through text.

---

## 10. Responsive Interface

### 10.1 Large desktop — 1200px and above

Show conversation and report simultaneously.

Prefer approximately 32:68 horizontal proportions, subject to sensible minimum widths.

Research activity is available as a drawer.

### 10.2 Compact desktop and tablet — 768px to 1199px

Retain the dual-pane layout where both panes remain usable.

Allow a more balanced split and user adjustment.

When available width becomes inadequate, switch to the single-pane interface rather than producing cramped text columns.

### 10.3 Mobile — below 768px

Provide a single primary content area with accessible navigation between:

- Conversation.
- Report.

Research activity remains accessible through a separate drawer or view.

The active conversation and report state must be preserved when switching views.

The composer remains available in Conversation.

The report remains a readable vertical document.

### 10.4 Narrow-screen requirements

The interface must remain functional at 390px and 320px widths.

Controls must not overlap, critical text must not be clipped and wide factual tables must remain inspectable.

---

## 11. Accessibility Specification

Target WCAG 2.2 AA.

Requirements include:

- Fully keyboard-operable navigation and controls.
- Visible keyboard focus.
- Correct semantic heading hierarchy.
- Accessible names for all controls.
- Appropriate focus management when opening and closing drawers.
- No essential information communicated by colour alone.
- Accessible tables with proper headings.
- Status changes announced without overwhelming assistive-technology users.
- No forced focus changes when progressive report updates arrive.
- Reduced-motion support.
- Readable content at 200% text zoom and 400% browser zoom.

Automatic research activity must not prevent the user from reading or operating the interface.

---

# Part B — Architecture and Control Contracts

## 12. Responsibilities and Components

### 12.1 Conversation and interface

Maintain the visible research plan, ongoing dialogue, stable living report, decisions and optional detailed activity/evidence inspector. Conversation should survive multiple authorised research and editorial turns within one run.

### 12.2 LLM research collaborator

The LLM interprets **the user's meaning and purpose**, not just strings naming parties. It proposes worthwhile subsidiary questions; identifies relevant candidate tools from a truthful verified catalogue; discusses results; requests material clarifications; and writes/revises report sections grounded in accepted evidence.

A single entity-extraction call followed by deterministic vocabulary admission and templated count reporting **does not satisfy this role**. The LLM must not invent factual answers, parliamentary context, capability availability, citations or graph identities.

### 12.3 Coordinator and requirement ledger

Retain the original question and subsequent authorised changes, stable requirement IDs, proposed subsidiary research questions, plan versions, approved scope, task dependencies, result statuses and claim/evidence dependencies.

For every material user requirement, preserve an explicit disposition: **answered, partly supported, evidence pending, needs clarification, unsupported, unavailable, or explicitly withdrawn by the user**. Record each condition (relationship, entity, date, subject, role, exclusion, answer shape) and what evidence, if any, addresses it. Keep parent requirement status separate from subsidiary search outcome.

Before **each query dispatch**, check that the proposed typed operation accurately expresses its **own** stated subsidiary question, satisfies normal compiler safeguards, has a defensible relevance to an authorised research objective and cannot be mistaken for a broader operation. **Do not require the supporting operation to be equivalent to the entire original brief.** Query admissibility is not an assertion that the parent requirement has been satisfied.

Before labelling any **particular assertion** as established (Level 1/2), validate its exact meaning—entities, relationship, date, scope and relevant qualifications—against accepted evidence or an approved deterministic derivation. Never use a model-generated “entailed”, “covered” or “answered” label, quotation or citation as proof. Preserve known unsupported or ambiguous conditions and keep their research tasks open, while independent supported work continues.

The coordinator may describe a **bounded finding as answered at its verified scope**, but it must not independently certify that the entire original ordinary-language brief has been exhaustively interpreted or satisfied. The LLM may offer a provisional account of what the draft addresses; the researcher reviews its adequacy against the preserved original brief. Unknown omissions are a product evaluation risk, not a pretext for blocking every supported query or producing verified-looking unsupported prose.

The coordinator enforces bounded tool budgets, safe retries, user approvals and selective evidence/report invalidation on revisions. Neither initial plan publication nor standing consent waives future requirements.

### 12.4 Typed query tools

Expose a curated catalogue of **actually executable** compiler operations, with typed parameters, supported entities/relations, approved temporal semantics, projection, error states, provenance and completeness requirements. Prefer several research domains with verified bounded operations over a larger untested catalogue.

The LLM may propose and sequence tools, but execution must reuse existing compiler identity resolution, request admission, plan validation, SPARQL safety and evidence evaluation. The LLM cannot supply arbitrary SPARQL, graph IRIs or guessed identifiers. A supporting tool may deliberately answer a **narrower subsidiary question** without replacing the parent requirement. Do not misrepresent the tool's own scope, or automatically relabel a rejected parent question as answered by a weaker selection. Verify reachability and evidence on current code/data rather than inferring capability from a catalogue title.

### 12.5 Evidence and claim store

Keep accepted results, identities, temporal context, traces, coverage/freshness qualifications, tool/requirement IDs and assertion dependencies outside the conversation transcript. Represent **supporting retrieval**, **validated factual assertion**, **provisional interpretation/hypothesis**, **research requirement assessment** and **user review state** as separate linked records. Each accepted fact retains its source operation's actual semantics; no parent condition is inherited merely because the fact contributes to that question.

For every substantive assertion, retain at minimum: stable assertion ID; exact text or structured proposition; evidence class (1–4); source evidence IDs and scope; derivation or reasoning; assumptions and contrary/missing evidence; qualitative confidence **only for Level 3**; and review status (**provisional** or **reviewed by the researcher**). The system must not mark an assertion human-reviewed without an actual review action. Level 1 and 2 must reference accepted machine-verifiable operations/calculations; Levels 3 and 4 must be distinguishable as model-authored, non-certified prose. Keep source freshness/coverage as separate attributes, not rolled into a confidence badge. For Level 4, prefer explicit uncertainty and a research question over a numeric or qualitative confidence rating.

Successful tool execution is not proof that an arbitrary sentence or the user's entire question is answered.

### 12.6 LLM report author

Author a coherent, useful **research draft** from controlled accepted facts and, where appropriate, approved institutional background sources. Level 1 and 2 assertions require the actual accepted facts or deterministic derivations, including their relationship, entity and temporal limits. A citation or LLM self-review **does not** certify that a broader prose statement is true. When the author cannot bind a stronger proposition, it must not be presented as established; the LLM may instead offer a clearly marked Level 3 interpretation with assumptions, a Level 4 hypothesis in the designated area, or an explicit unanswered question, according to the evidence.

The LLM may write readable explanatory prose without a universal independent semantic verifier. This prose remains a draft subject to human assessment; the system must **not** falsely label it verified or certify full interpretation of arbitrary user language. Do not treat model memory as a source for parliamentary history, legal procedure or contemporary facts. Editorial review may correct, qualify or reject model prose without invalidating separately accepted compiler facts.

Maintain the [editorial language contract](parliamentary-research-assistant-editorial.md) in the report and conversation. Technical provenance is available in the activity drawer, but not inserted into the primary narrative.

## 13. Tool Selection and Research Loop

**User brief → LLM interpretation → requirement ledger and subsidiary questions → visibly published plan → guarded typed tools → validated evidence → LLM-authored report → conversation/revision.** Only dependent work should rerun.

For each registered tool document its complete supported semantics, parameter schema, time policy, outcome shape, evidence/coverage metadata and known refusals. A tool-selection proposal is subject to deterministic operation/parameter admission and truthful **supporting/direct** task attribution. Separately track satisfaction of the full user requirement; do not infer that from operation success. Do not advertise missing capabilities as working. Do not use LLM-generated SPARQL or unvalidated post-hoc joins.

For unsupported substantive Debate analysis or historical composition, make the gap clear and provide useful independently supported findings where possible. A new external evidence source requires explicit authorisation.

## 14. User, Model and Compiler Authority

**Automatic:** research conversation and planning; verified in-scope tool selection/execution; supported finding explanation; evidence-grounded writing/revisions; bounded safe retries; compatible deterministic calculations.

**User decision:** material ambiguity, assistant-proposed scope/date/measure substitution, choice among conflicting meanings, access to an unapproved new source. Direct user instruction to change direction is itself approval.

**Prohibited:** dropping user qualifications, confusing supporting evidence with satisfaction of the parent question, promoting a wrong-relationship or unfiltered result into a full answer, unsupported joins, unrestricted SPARQL, invented citations/identities, missing evidence treated as evidence of absence, local-record results treated as certified complete rosters, or model self-validation overriding deterministic compiler safeguards.

## 15. Evidence, Language and Safety Integrity

Maintain three distinct responsibilities: **retain and transparently interpret the user's original research intent; validate executable factual evidence; and produce a clearly classified, reviewable report draft**. A valid narrower supporting query is permissible; a stronger established factual claim inferred from that query is not.

Do **not** require an independent proof that every material condition in arbitrary natural language has been discovered or discharged before a useful draft can be shown. Do not automatically label a complete report “verified”. Instead make the research plan, known unanswered conditions, evidence and assertion classifications available for informed researcher review.

Every substantive claim links to accepted evidence, an approved deterministic calculation or independently supported reference background. Date/term meaning, uncertainty and incomplete source coverage must survive synthesis, revisions and export. Raw IRIs, graph names, accepted witnesses, pagination and status strings belong in technical disclosures. The [editorial contract](parliamentary-research-assistant-editorial.md) and [acceptance contract](parliamentary-research-assistant-acceptance.md) are normative.

# Part C — Corrective Product Delivery

## 16. Domain and Vertical-Slice Boundary

**The existing Phase 1 party-comparison implementation is a technical prototype, not an accepted user-facing MVP.** Preserve its safe adapter, structured evidence, compiler guardrails and progressive report mechanics if they remain suitable. Redesign or retire the narrow name extractor, fixed admissible-word list, predetermined party-report assembly and technical language.

The **next corrective vertical slice** must deliver real LLM-led interpretation, relevant subsidiary questions and LLM-authored prose on at least one meaningful parliamentary research brief from [the acceptance contract](parliamentary-research-assistant-acceptance.md), with a second bounded domain exercised and explicit truthful handling of unsupported composition/content. Do not choose a count-only demonstration as the product success case.

Candidate domains include Member/constituency history, Bill sponsorship/progress and officeholding. Whether a specific requested connection is executable remains a technical verification question. The target is a useful, honest report when full evidence is unavailable, not fabricated completeness.

## 17. MVP Feature Boundary

### Required for corrective acceptance

- LLM-led conversational understanding and realistic planning rather than entity extraction alone.
- A visible plan based on research purpose and material requirement accounting.
- Bounded, typed, verified compiler tools spanning more than one domain where existing capability permits.
- Automatic safe execution and evidence retention.
- LLM-authored, readable, evidence-backed report with contextual explanation.
- Genuine follow-up conversation and section/plan revision without restarting research.
- Clear partial-answer, clarification and unsupported states.
- Existing approved two-pane responsive, accessible UI and activity/evidence inspector.
- Qualified export that preserves unsupported findings and sources.

### Outside the bounded slice

- Unrestricted graph querying, generic complex joins, broad compiler replacement.
- General autonomous external web research or unapproved data sources.
- ETL/ontology/data changes made only to satisfy a demonstration.
- Rich-text editing, collaborative document publication, cross-session report libraries.
- Unbounded agent loops or sweeping generalisation across all parliamentary subjects.

## 18. Product and Technical Acceptance

**A technically correct tool integration is necessary but insufficient.** Run the independent, realistic research scenarios in [the acceptance contract](parliamentary-research-assistant-acceptance.md), including ordinary paraphrases, partial/unsupported needs, a live multi-turn revision and human editorial/factual review.

Acceptance concerns a **useful, evidence-grounded draft** with correct classification of claims, not a machine-certified exhaustive answer to an arbitrary question.

The four independent assessment dimensions are:

1. **Language understanding:** faithful interpretation, meaningful clarification, no silently omitted conditions.
2. **Research usefulness:** intelligent subsidiary questions, helpful partial research, useful final document.
3. **Editorial quality:** Oireachtas-style plain-English explanatory conversation/report, no unexplained compiler jargon.
4. **Factual integrity:** established Level 1/2 claims have accepted support, Level 3/4 assertions are visibly provisional, appropriate uncertainty is maintained, and no unsupported join or claim is falsely presented as fact.

All four dimensions must pass. A safe refusal does not count as a successful factual report. Independent human assessment is required in addition to automated tests.

Keep the v0.2 browser and accessibility requirements: plan visible before initial dispatch; progressive updates and reading-position stability; keyboard/focus; partial/failure retention; responsive desktop/tablet/390px/320px; evidence inspection and qualified Markdown export. Existing compiler regression tests remain mandatory.

## 19. Implementation Guidance and Human Gate

- The completed [retrieval/satisfaction validation](../reports/parliamentary-research-assistant/retrieval-satisfaction-validation.md) remains evidence that ledger-only semantic completeness fails and independent original-intent holds over-block ordinary questions. **Do not repeat its impossible exhaustive-binding gate.** Retain its known omission examples as regression and human review cases for false factual promotion, while allowing useful draft research.
- First identify and register a small set of existing verified tools for the chosen realistic research briefs; do not broaden compiler semantics simply to produce an attractive demo.
- Preserve working query/evidence infrastructure when it supports v0.5, but do not build further features on the rejected word-list interpretation/product flow.
- Implement one thin meaningful research journey end-to-end, then demonstrate a second domain or honest bounded limitation.
- Verify with actual user language and model behaviour, not canned report text or a known exact string only.
- Stop for human review if guarded query admission, source-to-Level-1/2 factual grounding, uncertainty labelling or the ability to distinguish provisional interpretations from established facts cannot be maintained. Do not stop merely because exhaustive automatic natural-language comprehension or unrestricted prose certification is unavailable.
- Do not automatically treat v0.5 approval as authorisation to implement the next tranche. A separate, bounded OpenCode implementation prompt and human gate are required.

## 20. References and Decision Record

### Core repository sources

- `docs/reports/parliamentary-research-assistant/phase-0-integration-feasibility.md`
- `docs/reports/parliamentary-research-assistant/phase-1-vertical-slice.md`
- `docs/reports/parliamentary-research-assistant/corrective-admission-review.md`
- `docs/reports/parliamentary-research-assistant/corrective-admission-live.json`
- `docs/reports/parliamentary-research-assistant/retrieval-satisfaction-validation.md`
- `docs/reports/query-service/nlq-stage-2-executable-capability-inventory.md`
- `docs/reports/query-service/nlq-stage-5-evidence-based-architectural-evaluation.md`
- `poc/specs/composable-query-plan-contract.json`
- `poc/specs/composable-query-plan-draft.schema.json`
- `poc/specs/composable-query-plan.schema.json`

### Settled decisions (12 November 2026)

1. Evaluate real parliamentary research needs, not mechanically convenient database operations.
2. Give the LLM substantial initiative in interpretation, planning, dialogue and report writing; retain compiler and user authority boundaries.
3. Expose multiple verified compiler domains through bounded typed tools, not general SPARQL.
4. Adopt Oireachtas-style editorial and plain-language contract with worked examples.
5. Make ongoing conversation and revision of the same report essential.
6. Accept the application only on separate language, research usefulness, editorial and factual-integrity dimensions, using independently prepared realistic briefs.
7. Distinguish relevant supporting retrieval from factual assertion support. A successful query cannot automatically certify a complete answer.
8. Produce research **drafts for human review** rather than claim independent exhaustive natural-language completeness.
9. Use four assertion evidence classes: direct; deterministic derived; provisional interpretation; and clearly marked hypothesis.
10. Use **high / moderate / low** confidence only for provisional evidence-based interpretations, with a transparent rubric and no uncalibrated percentages.
11. Show unobtrusive, accessible evidence indicators beside substantive findings, with detail in the inspector and qualifications retained in exports.
12. Restrict hypotheses to explicitly labelled discussion/further-investigation material; unsupported speculation must instead be framed as a question.

### Unchanged v0.2 UI foundations

Two-pane desktop conversation/report; wider document pane; collapsible Research Activity drawer; visible plan before query dispatch; progressive findings; responsive mobile views; keyboard accessibility; evidence access; qualified Markdown export. These remain normative alongside the strengthened conversation and writing requirements.

**Status:** v0.5 and its two companion contracts record approved product and evidence-confidence decisions. The previous admission/satisfaction validation has concluded **NO-GO for automatic completeness certification**; that gate is retired. A bounded corrective research application tranche may be separately authorised. This document does **not** itself authorise implementation, compiler expansion, external-source access or deployment.

