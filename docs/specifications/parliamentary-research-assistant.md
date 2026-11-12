# Parliamentary Research Assistant
## Product, UI and Architecture Specification — v0.6

**Project:** OireachtasOntology  
**Date:** 12 November 2026  
**Status:** Approved v0.6 interaction/UI design; not yet implemented; v0.5 product acceptance remains pending  
**Branch:** `parliamentary-research-assistant`  
**Companion contracts:** [Editorial and plain-language standard](parliamentary-research-assistant-editorial.md) · [Research acceptance scenarios](parliamentary-research-assistant-acceptance.md)

> **v0.6 UI decision (12 November 2026):** Replace the permanent two-pane workspace with a **single-column, writing-first research journey**, drawing on Drafter's interaction pattern rather than its drafting logic. The initial question occupies the central canvas; after submission, planning and then the research report become the primary content. A compact follow-up composer sits below the report, conversation history is available on demand, and research/evidence detail remains contextual in a drawer or dialog. Remove abstract promotional text and developer-facing disclaimers from the start screen. The existing v0.5 compiler, research, evidence-confidence and human-review authority contracts are unchanged. **This is a specification approval, not implementation or product acceptance.**

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

**UI precedence:** The v0.6 single-column interaction and its companion editorial/browser contracts **supersede** the previous v0.2–v0.5 desktop two-pane layout and mobile conversation/report switching. All other accepted requirements for evidence access, progressive research, responsiveness, accessibility and qualified export remain applicable.

---

## 2. Agreed Interaction Model

### 2.1 Hybrid autonomy

The LLM interprets research purpose, proposes relevant subsidiary questions and plans work; the coordinator automatically invokes verified in-scope tools. Material ambiguity, assistant-proposed changes of period/relationship/measure, or a new evidence source require a user decision. Explicit user-requested changes are already authorised.

### 2.2 Visible research plan

**Approved:** After submission, the assistant publishes a concise, readable research plan **in the primary column before initial factual query execution**. Plan items are **research questions and expected findings**, not compiler function names. The plan is updated when the user refines the brief; once results are available it may reduce to a compact progress summary, with the full plan accessible on demand. Routine supported operations do not require separate approval.

### 2.3 Progressive report

**Approved:** The report takes over the **primary single-column reading canvas** as validated findings arrive. The LLM authors coherent explanatory prose from evidence; tables support the narrative rather than replace it. Pending, blocked and partially answerable requirements remain visible, and relevant updates do not displace the reader's position. Factual prose cannot precede accepted evidence.

### 2.4 Genuine ongoing conversation

The user may ask why a finding matters, what remains unknown, request clearer explanations, challenge source evidence, introduce a new scope or revise a section. A **compact follow-up composer below the report** remains available; previous conversation can be expanded on demand without losing any turns. The assistant responds to the research context, updates affected plan/report items and reuses unaffected accepted evidence. Editorial changes must not require re-querying facts unnecessarily.

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

The MVP is a **single-column research workspace**, not a split-screen chat/dashboard.

**A. Application header:** restrained identity, current research title when established, and contextual New research / Research Activity / Pause / Export controls. Do not display inactive report controls or developer status prominently on the empty start screen.

**B. Starting canvas:** a centred, generous multiline field asking **“What would you like to find out?”**, one prominent **Start research** action, and one or two clearly labelled example questions. This is the primary interaction; there is **no empty report pane** alongside it.

**C. Planning and progress canvas:** after submission, show the preserved original question, the LLM's plain-language interpretation and a **visible research plan before the first factual query**. Research progress and clarifications use the same column.

**D. Report canvas:** once findings arrive, the evidence-grounded report is the main content in a document-oriented reading area. Tables may occupy the available document width while prose retains comfortable line lengths. A compact follow-up composer appears **below the report**; prior exchanges are available via an on-demand conversation-history disclosure, not a permanently visible chat column.

**E. Research Activity and evidence:** contextual drawer/dialog opened from the header, a plan item, or an evidence indicator. Preserve all existing source inspection and query tracing; these are not separate dashboard columns.

### 3.2 Primary navigation and source-of-truth behaviour

Move naturally through **Ask → Plan → Research → Report → Refine** within one continuous workspace, retaining scroll position and state where practical. This is a presentation progression, not separate mandatory pages or a fixed research sequence.

The report becomes the dominant reading surface after the initial plan; the plan remains retrievable. Keep the complete original question, research dialogue and accepted evidence available without forcing the user to navigate away or restart. Earlier exchanges may be collapsed but must never be discarded.

Contextual evidence inspection and clarifications must not obstruct independent research or permanently consume document width. On all screen sizes, provide **one primary content column** rather than reinstating a split-screen layout.

---

## 4. Single-Column Screen Composition

### 4.1 Layout and widths

On desktop, centre the **starting writing canvas** in a generous editorial column (approximately **680–760px maximum**). Do not surround it with blank report cards or large dashboard panels. Let the question field take visual priority, with comfortable whitespace.

After submission, the **report canvas** may use a wider working document area (approximately **850–950px maximum**) for factual tables and evidence links. Keep long prose lines to the readable measure defined in §9.3, even when the document itself is wider. Tables may scroll within their own containers when necessary.

The header spans the viewport; document content scrolls as **one coherent main page**. Research Activity/evidence opens as a contextual drawer/dialog. Do not place the report and conversation in independently scrolling side-by-side panes or introduce a resizable divider.

The compact follow-up composer belongs **under the current report**, not anchored in a separate conversation panel. Previous exchanges are in a collapsible/expandable history area. When the report is long, provide a convenient, keyboard-accessible way to reach the composer without obstructing report reading.

### 4.2 Header

Display **Parliamentary Research** identity and restrained contextual actions: New research, Research Activity, Pause/Resume during execution, and copy/export when a report exists. Show the current research title and state when meaningful. Keep the starting screen sparse and do not give technical availability, query counts or unsupported-source disclaimers prominent header space.

### 4.3 Starting writing canvas

Use a single prominent question: **“What would you like to find out?”** with a real multiline composer and one clear **Start research** action. A short supporting line may say: **“Ask a question about the Oireachtas. Explore the findings and refine your report as you go.”**

Provide one or two realistic, **explicitly labelled example questions**. Selecting an example **populates the question field without starting research**, so the researcher can edit it. Example:

> What happened to the Bills sponsored by Malcolm Byrne?

Examples illustrate possible questions; they are not named templates or guarantees that every question is fully answerable. Do not display the technical wording “Drafts for human review. Source coverage and freshness are not certified” here. Meaningful qualifications belong with the findings they affect.

Optional **View an example report** may be offered as a secondary action **only** if backed by a genuine, read-only, appropriately reviewed illustrative report. This must not become a fixed template or displace the question composer. Do not create a fake preview as a prerequisite for launch.

### 4.4 Report and follow-up canvas

Display the research report as the primary document: a purposeful title, short scope or answer-oriented summary, structured findings, factual tables, evidence indicators, unanswered questions and section-level refinement actions.

After or within the final report context, provide a labelled, compact follow-up input such as **“Ask a follow-up or request a change”**. Typical uses include asking about a Bill, explaining a finding or rewriting part of the report; these are examples, not restricted command phrases.

Prior exchanges and assistant replies remain available through an on-demand **Conversation history** disclosure; the user may inspect, expand and return to the report without losing any work. A selected report section can supply context to the follow-up composer. Keep the report as the primary surface during further research instead of reverting to a permanent chat/report split.

---

## 5. Screen and State Specifications

### S1 — New Research

**Purpose:** Invite a useful research objective, not a database exercise.

Show **only the centred, writing-first research canvas** with the question field, a prominent **Start research** action and one or two labelled, selectable example questions that fill (but do not submit) the field. No empty report panel or competing “report coming soon” placeholder appears. Do not duplicate the question heading as a separate prominent label elsewhere; preserve an accessible name.

Do not use **“Living Report”**, **“A clear brief. A traceable report”**, **“Parliamentary research note”** as an opening label, **“Your report will take shape here”**, **“Validated findings appear as research progresses”**, **“Prepare a briefing on a Member's Bills”** as an unexplained pseudo-template, or introductory **“source coverage/freshness not certified”** boilerplate. Prefer direct, institutional language explaining what the user can ask and what the output will be.

### S2 — Preparing Research

In the same primary column, retain the original question and show the LLM's proposed interpretation, relevant subsidiary questions and any material ambiguity. The assistant summarises what it intends to investigate in plain language; it does not just extract entity names. Unsupported requirements are retained. **Publish the initial plan visibly before dispatching any factual query**. A blank report placeholder is not required during planning.

### S3 — Research in Progress

Plan items address research questions, such as “Which Bills are associated with this Member?” or “What documented stages can be established?”, not operation identifiers. Mark a subsidiary search as **supporting evidence** when it does not itself answer the parent question. Supported factual requests run automatically; accepted factual findings progressively populate the **same main report column**. The user can read without being pushed to another pane or losing position. Keep an accessible way to ask a follow-up or clarification during work. Unanswerable conditions remain visible even when useful supporting results were found.

### S4 — Clarification Required

Explain the uncertainty, why its resolution changes the evidence selected, and grounded choices. Example: "Do you want the TDs representing Dublin Central at the start of each Dáil, or anyone who served during each term?" Do not select a materially different meaning without approval. Continue independent supported tasks.

### S5 — Initial Research Completed

Once the initial research plan has finished:

- The **report is the primary reading document**, with scope, source-qualified findings and accessible evidence details.
- The research status changes to Completed or Completed with limitations; the document still says **Draft — for review**.
- The assistant provides a concise summary of what was achieved, without duplicating the report as chat messages.
- Any unanswered requirements remain visible next to the relevant findings or in the report's limitations section.
- The compact follow-up composer is available **beneath the report**; earlier messages and the plan can be opened on demand.

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

The initial question composer is the **dominant starting control**; the follow-up composer is compact and contextual below the report. Both accept free-form multiline writing.

Required behaviour:

- **Enter** creates a new line; **Ctrl/⌘+Enter** submits, following Drafter's writing-first pattern. A visible, descriptive **Start research** button initiates the initial question; the follow-up button sends the next request. Do not silently submit a multi-paragraph brief when the user presses Enter to write.
- An accessible hint explains the shortcut without requiring knowledge of it; the button remains the obvious primary action.
- Submission is disabled for an empty/whitespace-only message.
- The user's text survives a failed submission; preserve draft text and focus where practical.
- Examples populate the initial composer without dispatching a request or overwriting already written text without an explicit user action.
- During research, the user can provide clarifications and follow-ups without abandoning the report, and Pause remains accessible while further operations are in flight.

The composer must encourage ordinary conversational research requests rather than predefined command syntax. Do not introduce rich-text editing or attachments solely to emulate Drafter; borrow the focused input interaction, not unrelated features.

### 6.2 Assistant messages and history

The assistant speaks as a helpful, impartial parliamentary research colleague. It discusses the purpose of the investigation, explains meaningful findings, asks necessary clarifications and supports follow-up questions that genuinely revise the research/report. It does not fill the conversation with query-completion notices or repeat the full report. Advanced query details belong in Research Activity.

Earlier messages must be **preserved and accessible on demand** through a labelled Conversation history disclosure, with speakers and chronology understandable. A new reply, material clarification or failure must be discoverable without reopening the full transcript every time; use concise contextual cues. Neither history expansion nor new progress messages should steal focus or displace the main report.

All user-visible messages follow [the editorial standard](parliamentary-research-assistant-editorial.md). Responses that merely say "refinement requires Phase 2" are non-compliant with the intended research experience.

### 6.3 Research plan presentation

Show the plan as a **readable primary-column step** before execution, then collapse or summarise its history after findings arrive while keeping it fully inspectable. The plan contains:

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

The user can select a report section and request refinement through the compact follow-up composer without manually copying its title or contents into a separate conversation panel.

Example section actions:

- Refine this section.
- Explain this finding.
- Investigate further.
- View supporting evidence.

The selected section becomes the context of the next conversational request. Show that context near the composer and allow the user to clear it. Preserve report reading position after a targeted revision unless the user chooses to jump to the changed section.

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

**Professional, restrained, document-oriented and readable in the editorial tradition of Oireachtas.ie.** The approved experience is a **single-column editorial canvas**, with a Drafter-like writing-first start and a report-first continuation. Preserve the activity/evidence drawer, responsive behaviour and accessible component states. Use the project's existing professional palette rather than importing Drafter's colour scheme or drafting workflow. The workspace is for research reading and dialogue, not a technical developer console. Plain language is an interface requirement, not optional post-processing.

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

Keep the **single main column**: a centred writing canvas before submission, then a wider but readable report canvas. No side-by-side conversation pane, permanent report placeholder, resizable divider or independent pane scrolling. The on-demand activity/evidence dialog may overlay the page without destroying its state.

### 10.2 Compact desktop and tablet — 768px to 1199px

Use the same single-column hierarchy with fluid margins, scalable document width and contextual controls. Do **not** resurrect a two-column layout at intermediate breakpoints. Avoid cramped or clipped tables; support table-contained scrolling.

### 10.3 Mobile — below 768px

Keep the question, plan, report and contextual follow-up in a **single vertically readable flow**. No mandatory Conversation/Report tabs or view switcher. Research activity and evidence use an accessible drawer or dialog. Previous exchanges remain available on demand. Keyboard and software-keyboard interaction must not obscure the composer or leave essential actions unreachable.

### 10.4 Narrow-screen requirements

Check 390px and 320px widths, plus 200% text-size and 400% zoom-equivalent reflow. Preserve readable report paragraphs, a practical multiline question field, accessible example selection, non-overlapping actions, keyboard reachability of conversation history and source inspection, and horizontal scroll only **inside** wide factual tables as necessary. Never require horizontal page scrolling to read the main research narrative.

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
- Clearly labelled initial and follow-up composers, with correct multiline behaviour (Enter newline, Ctrl/⌘+Enter submit) and accessible shortcut hints; initial example selection does not trigger submission.
- Main-column keyboard focus progression through question → plan → report → follow-up and, on demand, conversation history and evidence.
- Collapsible history and plan preserve accessible names, expanded state, chronological order and focus on return to the report.
- Reduced-motion support.
- Readable content at 200% text zoom and 400% browser zoom.

Automatic research activity must not prevent the user from reading or operating the interface.

---

# Part B — Architecture and Control Contracts

## 12. Responsibilities and Components

### 12.1 Conversation and interface

Maintain the visible research plan, ongoing dialogue, stable **research report**, decisions and optional detailed activity/evidence inspector. Present these in one primary column with contextual history and follow-up composition. Conversation should survive multiple authorised research and editorial turns within one run.

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

**The original Phase 1 party-comparison implementation was a technical prototype, not an accepted user-facing MVP.** Preserve its safe adapter, structured evidence, compiler guardrails and progressive report mechanics if they remain suitable. Redesign or retire the narrow name extractor, fixed admissible-word list, predetermined party-report assembly and technical language.

The **v0.5 research vertical slice** has already delivered live LLM-led interpretation, subsidiary research, LLM-authored prose and a second bounded domain, with independent human product acceptance still pending. The **v0.6 design update** addresses the observed usability of the start screen and workspace flow; it does not reopen the capability or factual-authority architecture. Do not use a count-only demonstration as product success evidence.

Candidate domains include Member/constituency history, Bill sponsorship/progress and officeholding. Whether a specific requested connection is executable remains a technical verification question. The target remains a useful, honest report when full evidence is unavailable, not fabricated completeness. No new research domain or compiler operation is required by this UI update.

## 17. MVP Feature Boundary

### Required for corrective acceptance

- LLM-led conversational understanding and realistic planning rather than entity extraction alone.
- A visible plan based on research purpose and material requirement accounting.
- Bounded, typed, verified compiler tools spanning more than one domain where existing capability permits.
- Automatic safe execution and evidence retention.
- LLM-authored, readable, evidence-backed report with contextual explanation.
- Genuine follow-up conversation and section/plan revision without restarting research.
- Clear partial-answer, clarification and unsupported states.
- Approved v0.6 single-column, responsive, accessible writing-first UI; report-first continuation with contextual conversation and activity/evidence inspector.
- Qualified export that preserves unsupported findings and sources.

### Outside the bounded slice

- Unrestricted graph querying, generic complex joins, broad compiler replacement.
- General autonomous external web research or unapproved data sources.
- ETL/ontology/data changes made only to satisfy a demonstration.
- Rich-text editing, collaborative document publication, cross-session report libraries.
- Unbounded agent loops or sweeping generalisation across all parliamentary subjects.

## 18. Product and Technical Acceptance

**A technically correct tool integration and an attractive interface are necessary but insufficient.** Run the independent, realistic research scenarios in [the acceptance contract](parliamentary-research-assistant-acceptance.md), including ordinary paraphrases, partial/unsupported needs, a live multi-turn revision and human editorial/factual review.

Acceptance concerns a **useful, evidence-grounded draft** with correct classification of claims, not a machine-certified exhaustive answer to an arbitrary question.

The four independent assessment dimensions are:

1. **Language understanding:** faithful interpretation, meaningful clarification, no silently omitted conditions.
2. **Research usefulness:** intelligent subsidiary questions, helpful partial research, useful final document.
3. **Editorial quality:** Oireachtas-style plain-English explanatory conversation/report, no unexplained compiler jargon.
4. **Factual integrity:** established Level 1/2 claims have accepted support, Level 3/4 assertions are visibly provisional, appropriate uncertainty is maintained, and no unsupported join or claim is falsely presented as fact.

All four dimensions must pass. A safe refusal does not count as a successful factual report. Independent human assessment is required in addition to automated tests.

Keep existing browser and accessibility safeguards while **replacing the layout-specific expectations**: plan visible before initial dispatch; progressive report updates and reading-position stability; keyboard/focus; partial/failure retention; a single primary column at desktop/tablet/390px/320px; contextual history/evidence inspection; functional multiline shortcut and example selection; qualified Markdown export. Existing compiler regression tests remain mandatory.

## 19. Implementation Guidance and Human Gate

- The completed [retrieval/satisfaction validation](../reports/parliamentary-research-assistant/retrieval-satisfaction-validation.md) remains evidence that ledger-only semantic completeness fails and independent original-intent holds over-block ordinary questions. **Do not repeat its impossible exhaustive-binding gate.** Retain its known omission examples as regression and human review cases for false factual promotion, while allowing useful draft research.
- First identify and register a small set of existing verified tools for the chosen realistic research briefs; do not broaden compiler semantics simply to produce an attractive demo.
- Preserve the working v0.5 query/evidence/report infrastructure; limit any subsequent v0.6 implementation to the approved interaction/presentation change and do not build on the rejected word-list interpretation/product flow.
- Preserve and browser-test the existing R1 research journey, real multi-turn revision and R3 addition through the revised UI; do not rebuild the already-working research engine or create extra orchestration.
- Verify with actual user language and model behaviour, not canned report text or a known exact string only.
- Stop for human review if guarded query admission, source-to-Level-1/2 factual grounding, uncertainty labelling or the ability to distinguish provisional interpretations from established facts cannot be maintained. Do not stop merely because exhaustive automatic natural-language comprehension or unrestricted prose certification is unavailable.
- Do not automatically treat this v0.6 UI specification approval as authorisation to implement. A separate, bounded OpenCode implementation prompt and human usability gate are required.

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

### v0.6 UI decision (12 November 2026) and retained safeguards

13. Replace the v0.2–v0.5 two-pane conversation/report design with a **single-column, writing-first** canvas across starting, planning, findings and refinement.
14. Begin with one prominent multiline question, clear **Start research** action and one or two labelled, selectable examples that fill the field without submitting. Remove empty report placeholders, slogans and technical caveats from the first view.
15. Use **Enter for a newline** and **Ctrl/⌘+Enter for submission**, with visible controls and shortcut guidance.
16. Make the **research plan visible before first factual execution**; then make the report the primary reading surface, with a compact follow-up composer below and earlier conversation accessible on demand.
17. Retain Research Activity and evidence inspection in contextual drawer/dialog surfaces, with keyboard focus management, responsive tables, qualified export and unchanged factual authority boundaries.

**Superseded:** permanent two-pane desktop split, split resizing, independent conversation/report scrolling, empty report panel on first load, mandatory mobile view toggles, and technical/motto copy on the welcome screen. These are **not** normative acceptance requirements. Retained: accessible source evidence, progressive findings, original question/plan preservation, responsive reflow and human-reviewed research drafts.

**Status:** v0.6 updates the **UI/interaction contract only**. v0.5 research authority, evidence classification and qualitative confidence remain settled. The v0.5 implementation and bounded editorial correction have been completed on this branch, but **human product acceptance is pending**. This specification does **not** itself authorise the v0.6 UI implementation, merge to `master`, compiler expansion, external-source access or deployment.

