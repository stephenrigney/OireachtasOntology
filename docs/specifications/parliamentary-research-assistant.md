# Parliamentary Research Assistant
## Product, UI and Architecture Specification — v0.2

**Project:** OireachtasOntology  
**Date:** 11 November 2026  
**Status:** Approved specification; implementation not yet authorised  
**Branch:** `parliamentary-research-assistant`

---

## 1. Product Definition

The Parliamentary Research Assistant is a conversational application for investigating parliamentary information and producing evidence-backed research reports.

The application uses:

- An LLM to understand research objectives, guide conversations, organise investigations and draft reports.
- A deterministic research coordinator to track requirements, control execution and enforce approval boundaries.
- The existing OireachtasOntology compiler and query service to retrieve validated factual information.
- A persistent report workspace that progressively displays findings as they become available.

The application is not intended to replace the compiler with unrestricted LLM-generated SPARQL.

### 1.1 Product objectives

The user should be able to:

1. Describe a research objective in ordinary language.
2. See what the assistant intends to investigate.
3. Obtain results without supervising every query.
4. Read and refine a progressively generated report.
5. Inspect the evidence supporting factual statements.
6. Understand which questions could not be answered.
7. Change the research direction conversationally.

The interface should make research activities understandable without requiring knowledge of RDF, SPARQL or compiler internals.

---

## 2. Agreed Interaction Model

### 2.1 Hybrid autonomy

The assistant automatically executes supported research requests within the user's agreed objective.

Material ambiguity, assistant-proposed scope changes and changes in factual interpretation require user approval.

A change explicitly requested by the user is already authorised and should not trigger redundant approval.

### 2.2 Research plan visibility

**Approved:** The research plan appears in the user interface before initial query execution.

The user does not need to approve routine supported queries.

The application must publish the initial plan before dispatching its operations. Subsequent plan changes must remain visible.

### 2.3 Progressive report generation

**Approved:** The report develops progressively as findings are validated.

Validated sections become available immediately. Other sections remain pending, blocked or unsupported, with their status clearly indicated.

The interface must not imply that a partial report is complete.

---

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

**Purpose:** Allow the user to start a research task.

Display a prominent input area with:

- A short invitation to describe a research objective.
- An expandable multiline composer.
- A primary action labelled **Start research**.
- A few optional examples illustrating the types of supported research.

The report panel initially contains an understated empty state explaining that the report will appear as research progresses.

Do not display a conventional dashboard of technical capabilities on the opening screen.

### S2 — Preparing Research

**Trigger:** The user submits an initial research objective.

The assistant interprets the request and prepares a proposed research plan.

The UI displays:

- The original research request.
- A concise indication that the assistant is preparing the plan.
- Any material clarification required before proceeding.

Once ready, the plan card appears.

No initial factual queries are dispatched before the plan has been published.

### S3 — Research in Progress

This is the principal working state.

The conversation displays the research plan with short, human-readable tasks.

Example:

**Research plan — Party representation**

- Identify the relevant Dáil term.
- Retrieve current Fine Gael membership.
- Retrieve current Fianna Fáil membership.
- Compare the verified membership figures.
- Prepare the report and disclose limitations.

Each item displays its progress state.

Supported operations proceed automatically.

The report panel begins displaying the report structure and progressively populated sections.

The user can continue the conversation while research is underway.

### S4 — Clarification Required

**Trigger:** A material ambiguity or proposed semantic change requires a decision.

Display a clarification card within the conversation.

The card must explain:

- What needs to be decided.
- Why the distinction matters.
- The available choices.
- Which research tasks depend on the decision.

Example:

**Which membership period should I use?**

- Membership at the current reporting date.
- Membership at any point during the parliamentary term.

These meanings can produce different results.

The card offers explicit choices rather than accepting an automatically selected assumption.

Only affected research tasks are blocked. Independent authorised tasks may continue.

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

Assistant responses should be concise and action-oriented.

Typical messages include:

- Interpretation of the research objective.
- Notice that the plan has been published.
- Explanation of a necessary clarification.
- Summary of newly validated findings.
- Notice of incomplete or unsupported work.
- Confirmation that a requested report revision has been applied.

Routine query completion should not generate excessive conversational messages.

Detailed execution progress belongs primarily in the research activity interface.

### 6.3 Research plan card

The plan card contains:

- Research objective.
- A short list of proposed tasks.
- Status of each task.
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

The report has a consistent document hierarchy:

1. Title and research scope.
2. Executive summary or overview.
3. Findings organised into sections.
4. Tables and comparisons where supported.
5. Limitations and unanswered questions.
6. Evidence references.

The LLM may propose different report structures appropriate to the research objective.

The interface must not force all reports into one fixed template.

### 7.2 Section states

Each section has one of the following states:

| State | Display |
|---|---|
| Pending | Heading and concise awaiting-evidence message |
| Populating | Validated content available; additional work in progress |
| Validated | Required findings accepted |
| Incomplete | Partial findings with explicit qualifications |
| Blocked | Content cannot be completed, with reason |
| Unsupported | Requested operation unavailable |
| Needs revision | Existing content requires revalidation after a scope change |

A section's state must be visible through text and appropriate iconography, not colour alone.

### 7.3 Progressive updates

Report updates must:

- Preserve existing content unless new evidence or an authorised revision changes it.
- Avoid rewriting unrelated sections.
- Preserve reading position wherever possible.
- Avoid sudden layout shifts.
- Clearly indicate when new validated findings are available.
- Never present temporary generated prose as established factual content.

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

**MVP behaviour:** conversational report editing, with section-specific refinement actions.

Direct rich-text editing is deferred initially to avoid ambiguity between user-authored prose and evidence-backed findings.

Users can request stylistic changes, changes to structure or further factual investigation through the conversation.

Later iterations may support direct editing with explicit treatment of manually modified factual claims.

### 7.6 Report export

For the MVP, provide a straightforward way to copy or export the current report as Markdown.

Export must preserve factual qualifications and evidence references where available.

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

The interface must distinguish direct RDF evidence from an LLM's explanatory synthesis.

### 8.4 Research limitations

The activity drawer should expose all unresolved requirements, but important limitations must also appear in the report itself.

Users must not have to inspect debugging controls to discover that a substantive research question went unanswered.

---

## 9. Visual Design System

### 9.1 Visual direction

The intended appearance is:

**Professional, restrained, document-oriented and suitable for parliamentary research.**

The design should feel closer to an interactive research document than a technical developer console.

It should be visually compatible with the OireachtasOntology application's established professional identity, without mechanically reproducing the NLQ debugging dashboard.

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

## 12. Application Components

The application comprises six logical components.

### 12.1 Conversational interface

Manages conversation rendering, user input, plan presentation, clarifications and report refinement actions.

### 12.2 LLM research planner

Interprets the user's research brief, identifies material factual requirements, proposes supported operations and generates readable report text.

LLM proposals are not authoritative query instructions.

### 12.3 Research coordinator

Maintains the research brief, plan, task dependencies, approved scope and execution state.

It enforces approval boundaries, schedules bounded operations and coordinates progressive report updates.

### 12.4 Query service adapter

Provides a typed interface to verified compiler operations.

It validates parameters, invokes the existing service and normalises returned evidence.

It must not bypass existing identity resolution, temporal semantics, query safety or evidence checks.

### 12.5 Evidence store

Retains validated results, originating requests, operation details, time scope, provenance and completeness qualifications.

### 12.6 Report assembler

Maintains stable report sections, associates findings with evidence and applies authorised content revisions.

The conversation transcript must not be the sole authoritative store for research requirements or factual findings.

---

## 13. Compiler Integration

The preferred architecture uses a small catalogue of supported, typed query operations.

Each operation requires:

- Identifier and purpose.
- Valid parameters.
- Supported relationships and temporal meanings.
- Expected result type.
- Validation requirements.
- Completeness rules.
- Known limitations.
- Regression verification.

The catalogue must represent executable capability rather than merely advertised ontology relationships.

The existing `/ask` interface may be useful for early experimentation but adds a second natural-language interpretation stage.

The first technical feasibility exercise must establish which current query-service operations can be safely invoked through a thin structured adapter.

No unrestricted LLM-generated SPARQL is permitted as the authoritative execution path.

---

## 14. Authority and Approval Boundaries

### Automatically permitted

- Interpret routine wording within the existing brief.
- Select and execute supported operations.
- Retry equivalent requests within resource bounds.
- Summarise validated findings.
- Prepare report sections and tables.
- Perform approved deterministic calculations from complete, compatible evidence.
- Make editorial revisions that preserve factual meaning.

### Requires user decision

- Material ambiguity of person, relationship or period.
- Assistant-proposed changes to research scope.
- Changes to the intended measure or relationship.
- Unauthorised evidence sources.
- Interpretations that would change the factual meaning of the report.

### Prohibited

- Silently weakening a research requirement.
- Treating partial results as comprehensive.
- Inventing facts or source provenance.
- Using missing data as proof of absence.
- Unsupported joins or temporal intersections.
- Bypassing compiler validation.
- Presenting LLM agreement or self-verification as factual proof.

An unresolved decision blocks only dependent tasks.

---

## 15. Factual Evidence Contract

Every factual finding must retain:

- Its originating research requirement.
- The selected and executed operation.
- Validated parameters and entity identities.
- Relevant temporal scope.
- Returned values and source references.
- Validation outcome.
- Completeness and uncertainty qualifications.

The report assembler must distinguish direct findings, validated calculations and explanatory narrative.

A successfully executed query does not, by itself, validate every statement in an LLM-generated report.

Comparisons must use compatible measures, time periods and evidence coverage.

A report section that depends on unavailable or unsupported evidence must remain visibly incomplete or unsupported.

---

# Part C — Bounded MVP

## 16. Initial Research Domain

**Approved initial proposal:** Contemporary Dáil party representation.

The first version should support a complete conversational report-building journey using a small set of verified existing query capabilities.

Example brief:

> Prepare a short report comparing Fine Gael and Fianna Fáil membership in the current Dáil, including membership totals, the Members involved and a short comparison.

The application should:

1. Establish and display the research plan.
2. Execute supported operations automatically.
3. Validate the membership evidence.
4. Populate the report progressively.
5. Show factual tables and qualified summaries.
6. Permit conversational refinements.
7. Preserve evidence and report limitations.

Actual factual results must come from the query service.

---

## 17. MVP Feature Boundary

### Included

- One research workspace.
- Conversation panel.
- Persistent report panel.
- Research activity drawer.
- Visible research plan.
- Hybrid approval and clarification controls.
- Bounded automatic query execution.
- Progressive report sections.
- Evidence references and inspection.
- Conversational report refinement.
- Basic compatible comparisons.
- Copy or Markdown export.
- Responsive and keyboard-accessible interface.

### Excluded

- Arbitrary SPARQL generation.
- General autonomous web research.
- Unrestricted cross-capability composition.
- General historical joins and unsupported statistical analysis.
- Rich-text document editing.
- Cross-session report libraries.
- Collaborative document workflows.
- Formal Word or PDF publishing.
- Broad compiler redesign.

The first version should not depend on completing the wider NLQ architectural generalisation programme.

---

## 18. UI Verification and Acceptance

### 18.1 Required browser checks

Test the new-research, planning, execution, clarification, partial-report, completed-report and failure states.

Verify at desktop, tablet, 390px and 320px viewport widths.

Check keyboard navigation, focus behaviour, screen-reader-relevant state updates, report scrolling, table overflow and activity-drawer operation.

### 18.2 Required behavioural checks

Verify that:

1. The research plan is published before initial query dispatch.
2. Supported queries proceed without redundant approval.
3. Material ambiguities produce explicit clarification cards.
4. Independent tasks continue when another task requires clarification.
5. Only validated findings populate factual report sections.
6. Unsupported requirements remain visible.
7. Progressive updates preserve reading position where possible.
8. Section refinement affects only relevant content and evidence.
9. Previously validated findings survive unrelated operation failures.
10. Export preserves evidence qualifications and incomplete status.

### 18.3 Research quality checks

Evaluate with realistic independently prepared research briefs.

Measure factual accuracy, material omissions, unsupported-operation handling, unnecessary interruptions, query success, time to first validated finding and time to a usable report.

Safe refusal and factual success must be scored separately.

---

## 19. Proposed Delivery Sequence

### Phase 0 — Integration feasibility

Identify verified compiler operations and establish a viable structured adapter.

**Exit:** Selected operations have tested parameter, execution and evidence contracts.

### Phase 1 — Research workspace and vertical slice

Implement the two-pane interface, visible plan, bounded automatic querying and progressively populated report for one coherent research brief.

**Exit:** A complete end-to-end report can be generated and inspected.

### Phase 2 — Hybrid decisions and refinement

Implement clarification, approval, report-section refinement, state reuse and robust failure presentation.

**Exit:** Users can conduct multi-turn research without losing scope, evidence or validated content.

### Phase 3 — User assessment

Evaluate varied real-world research briefs and compare the experience with direct NLQ query use.

**Exit:** Demonstrated user value and an evidence-based decision on expansion.

---

## 20. References and Design Decisions

### Existing repository references

- `docs/reports/query-service/nlq-stage-2-executable-capability-inventory.md`
- `docs/reports/query-service/nlq-stage-5-evidence-based-architectural-evaluation.md`
- `poc/specs/composable-query-plan-contract.json`
- `poc/specs/composable-query-plan-draft.schema.json`
- `poc/specs/composable-query-plan.schema.json`

### Approved product and UI decisions

- Hybrid conversational autonomy.
- Research plan visible before query execution.
- Automatic supported queries.
- Progressive report generation.
- User authority over material scope and semantic decisions.
- Two-pane desktop workspace.
- Conversation as the research control surface.
- Report as the principal reading surface.
- Research activity in an on-demand drawer.
- Section-level report refinement.
- Conversation-led editing rather than direct rich-text editing for MVP.
- Responsive single-pane mobile interface.
- Restrained parliamentary visual identity.
- Markdown export in the initial release.

### Implementation status

Approval of this specification does **not** authorise implementation.

The next technical step is a bounded assessment of the existing query service's suitability for a structured research-operation adapter, followed by implementation of the approved first vertical slice only when separately authorised.

The overall design objective remains to provide a **useful, evidence-backed research workspace**, not merely another interface for submitting individual natural-language queries.
