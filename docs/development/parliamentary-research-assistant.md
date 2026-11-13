# Parliamentary Research Assistant v0.6

A local conversational application producing **Draft — for review** research.
It does not certify exhaustive interpretation, source completeness or editorial
acceptance. Human assessment is required under the
[product](../specifications/parliamentary-research-assistant.md),
[editorial](../specifications/parliamentary-research-assistant-editorial.md) and
[acceptance](../specifications/parliamentary-research-assistant-acceptance.md)
contracts.

## Launch

```sh
uv sync --extra test --extra nlq
# Export existing local settings if kept here (do not commit credentials):
set -a; source .env.local; set +a
.venv/bin/python -m uvicorn poc.nlq.research_app:app --host 127.0.0.1 --port 8010
```

Open <http://127.0.0.1:8010>. Use **one worker**, loopback only. This is not an
authenticated public service. Restart the Python process after updating this
branch; an already-running server may still hold older coordinator code even
though the browser loads new static assets. Use another loopback port if an
existing research process must remain undisturbed. Configuration:

- `NLQ_LLM_API_KEY`, `NLQ_LLM_BASE_URL`, `NLQ_LLM_MODEL`: existing
  Responses-compatible structured-output model settings. The LLM interprets,
  plans and writes/revises reports; it never generates authoritative SPARQL.
- `NLQ_FUSEKI_QUERY_URL`, `OIR_FUSEKI_USER`, `OIR_FUSEKI_PASSWORD`: existing
  read-only query configuration; no reload, update or publication occurs.
- `OIR_NLQ_AS_OF_DATE`: optional ISO reporting/reference date, otherwise server
  date. This is **not** a source freshness date or an invented user time filter.

For example:

> Prepare a briefing on the Bills sponsored by Malcolm Byrne. What progress
> have they made, and what happened to them?

Then ask to shorten a section, explain a finding, reconsider an interpretation,
show evidence, or add a background briefing on Mary Lou McDonald's constituencies
and parliamentary roles. Names and Bill identities/counts are not hard-coded.

## Interaction and boundaries

The original brief, subsequent instructions, proposed requirements and plan
versions remain in the same run. The model proposes research questions; the UI
publishes interpretation and plan **before** automatically dispatching factual
queries. Each tool's exact narrower meaning is shown separately from model prose.
Supporting retrieval is not marked as satisfaction of the full original brief.
Known gaps appear in the main report and export. Requirement dispositions are
provisional model assessments, not an exhaustive semantic certification.

The opening canvas asks **What would you like to find out?** Select an example
to fill the field without submitting, or write your own multiline brief, then
choose **Start research**. **Enter adds a line; Ctrl/⌘+Enter submits**, on both
the opening and follow-up composers. Empty messages cannot be submitted.

Question, interpretation, plan and progressive report use one column at every
screen width. The plan is visibly published before factual dispatch and remains
available through **Research plan** / **View research plan**. It is not closed
automatically while you may be reading it. Once findings arrive the report is
the main document. **Ask a follow-up** in the compact reading navigation reaches
the composer below the report; **Conversation history** reveals all previous
exchanges. Research Activity and evidence remain contextual dialogs, not columns.

Pause stops further dispatch after an in-flight step. Follow-ups go to the server and the model, not a canned browser
response. Pure editorial turns reuse facts; factual additions retrieve affected
evidence. Existing sections remain unless returned as explicit section revisions.
New factual investigations cannot overwrite sections owned by earlier research;
section-context revisions apply only to their selected section. The research
title stays stable while new sections are appended.
Explicit revisions may change which facts are shown without deleting accepted
facts or their source links from the evidence store. Export before restart or
expiry: runs are in-memory, expire after one hour, capped at 32; each session has
a twelve-turn, 24-task budget. There is no persistent cross-session library.

### Reading and revising the report

The author chooses the report's organisation and selected developments. Detailed
Bill and representation findings can be shown in compact factual tables rather
than repeated assertion paragraphs. **Source records** in a row opens all its
individual accepted facts, including activities not selected for the table; each
fact opens its reasoning and complete source evidence. Research Activity also
retains **All individual factual assertions**. Tables scroll horizontally by
keyboard or touch on narrow screens.

Ask, for example, “Make the overview shorter and explain why recorded status is
not final outcome. Keep the Bill findings and evidence.” Editorial revisions
reuse compiler evidence and should change only the affected prose. Requirement
types separate outstanding factual questions from evidence limitations, editorial
instructions, process messages and clarification requests. These types are model
assessments for review, not an independent language-certification gate.
The author can explicitly assess a pending/partly-supported subsidiary question
as addressed **at recorded scope**, citing accepted facts and explaining the
bounded answer. This provisional ledger assessment retires stale progress
questions; it does not certify the full brief. Unsupported/unavailable questions
cannot be retired this way. Editorial omission alone cannot remove a question.

For a shortening request the model selects the existing prose target. The
coordinator supplies a budget of 65% of its previous narrative word count,
preserves its factual tables, and permits one bounded author repair if the prose
is too long. This is an editorial length constraint, not factual certification.
The model still chooses the wording and explanatory emphasis. A failed repair
retains the previous draft and reports that the revision could not be applied.

Markdown export includes the compact report and the **entire accepted factual
registry and source evidence**, even when facts are not expanded in the document.
The technical appendix is intentionally large. It is not necessary to read it
linearly to use the report.

### General guarded Query Service interface

`research_tools.py` passes concrete `query(question)` subsidiary questions
unchanged to the existing Query Service's general composable-v2 execution path.
The service's existing contracts/planner supply discovery guidance, admission,
identity resolution, validation, compilation and evidence evaluation. There is
no independently maintained research capability catalogue or unrestricted query
interface. Advertised capabilities may still be conditional, unsupported for a
particular wording/scope, or unsuitable for factual promotion.

| Tool | Parameters and supported meaning | Explicit non-answers |
|---|---|---|
| `query` | A concrete subsidiary question, relevance and direct/supporting/exploratory role; independently admitted by the existing Query Service | No model SPARQL, guessed identities, silent dropping of conditions or promotion of unsupported evidence |
| `lifecycle` | Reference to a successful sponsorship task; one exact number/year lookup per accepted Bill, at most 32 per task | Recorded process status and dated activities, **not certified final outcomes**; no guessed Bill IDs or title join |

Legacy `sponsorship`/`career` requests remain replay-compatible; new research uses
`query`, not a new subject-specific tool. Requests use public compiler execution,
identity resolution, plan validation, query safety, pagination/caps and evidence
evaluation, including its existing semantic planner when required. Only recognised
existing structured accepted evidence is normalised by `research_evidence.py`;
facts are not reconstructed from display prose. Successful service responses
without accepted research evidence (currently including party history) stay
inspectable in the evidence dialog with an explicit factual-promotion limitation.
Exact Bill identity agreement
is checked across sponsorship and lifecycle lookups. A failed/truncated/partial
compiler result produces no established assertions. Earlier independent evidence
survives. The Phase 1 party adapter remains for its existing regression suite,
but its permitted-word coordinator is not the default application's entry point.

After completed results/limitations the research LLM may publish additional
relevant investigations before dispatch, with at most three continuation rounds
per user turn and 24 tasks per session. Editorial requests reuse retained facts.

No general web source, Debate-content tool, committee/party intersection or
unrestricted query interface is advertised. Missing evidence is not zero or
proof of absence. Compiler traces retain every actual read, returned cells,
timing, graph scope, plan, source revision and failures. Freshness, loaded capture
identity and common snapshot remain unknown; coverage remains uncertified.

### Assertion and evidence-confidence contract

`research_assertions.py` retains stable assertion identity, exact text/structured
proposition, evidence references, reasoning, assumptions, conflicts, limitations,
review status, and confidence only where permitted:

1. **Directly supported:** compiler evidence projector emits the exact factual
   statement. The LLM can select its ID but cannot change its wording or level.
2. **Calculated:** approved distinct-Bill-identity cardinality over one accepted
   sponsorship enumeration. Inputs and algorithm are retained. No temporal or
   role joins, inferred outcomes, population estimates or model arithmetic.
3. **Interpretation:** LLM-authored paragraph with accepted fact references,
   provisional high/moderate/low confidence and a reviewable rationale discussing
   evidence, assumptions, gaps and conflicts. These are **not calibrated** ratings.
4. **Hypothesis:** explicitly unverified, only in a distinct further-questions
   section; no confidence rating. Prefer a research question over speculation.

The model cannot submit Level 1/2 prose or mark an assertion human-reviewed.
Tables display exact fields of accepted propositions, with assertion references
for every cell; aligning already accepted observations by exact Bill identity is
a presentation operation, not an outcome inference or a new compiler capability.
Descriptive summaries should use those presentations or the existing approved
calculation rather than automatically becoming speculative interpretations.
Free synthesis that cannot be independently grounded this way remains provisional
under the existing Level 3 contract; references alone cannot promote it.
Short model-facing fact handles resolve by exact registry lookup to stable
assertion IDs; the mapping is archived. Substantive conversational explanations
also carry exact-text Level 3 records and an evidence-inspection control.
Reference checks do **not** certify unrestricted narrative truth; Level 3/4 prose
remains a reviewable draft, not a factual verification badge. Main-text uncertainty
and gaps supplement the unobtrusive keyboard-accessible evidence indicators.
The inspector exposes sources, reasoning and qualifications. Markdown retains
draft/class labels, confidence rationale, gaps, assertion IDs and full evidence.

## Verification and artefacts

```sh
.venv/bin/python -m pytest -q tests/test_research_v05.py tests/test_research_workspace.py
# Keep legacy deterministic tests from picking up configured live-model fallback:
NLQ_LLM_API_KEY='' .venv/bin/python -m pytest -q tests
.venv/bin/python tests/validate.py
uv sync --extra test --extra nlq --extra browser-test
.venv/bin/python -m playwright install chromium
# Against the configured app above:
.venv/bin/python tools/verify_research_v06_browser.py
# Fast, explicitly injected/replayed UI controls (no model or dataset network):
.venv/bin/python tools/verify_research_v06_ui.py
```

New deterministic tests distinguish **injected model proposals** and exact saved
compiler-response replay from live research. The browser verifier exercises the
actual configured model/Fuseki interaction, saves transcripts, model proposals,
assertions, reports and screenshots under `/tmp/oireachtasontology/research-v06/`
by default, and checks R1, revisions, same-session R3, unsupported R4/R5, plan
visibility, evidence controls, keyboard focus, narrow-screen layouts and export.
The v0.6 checks also cover the writing-first opening at all five target widths,
example selection without submission, multiline shortcuts, section-context
revision, exact chronological history, retained drafts on failed submission,
interruption/retry and 200% text-size / 400% zoom-equivalent reflow. The `v05`
browser entry points forward to the current checks for compatibility; the older
Phase 1 split-pane verifier is historical, not a v0.6 acceptance command.
Use `--output` to choose an artefact directory. `/runs/{id}/archive` provides a
local JSON archive; it includes model inputs/outputs and source records, not API
credentials. Assess generated drafts before sharing.

The completion report records the actual observations and durable representative
artefacts. Browser automation is Chromium-only, not formal WCAG conformance or a
full assistive-technology audit. Human editorial/factual product acceptance remains
the final gate; passing tests does not accept this application.
