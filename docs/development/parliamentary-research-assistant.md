# Parliamentary Research Assistant v0.5

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
authenticated public service. Configuration:

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

Pause stops further dispatch after an in-flight step. Enter submits; Shift+Enter
adds a line. Follow-ups go to the server and the model, not a canned browser
response. Pure editorial turns reuse facts; factual additions retrieve affected
evidence. Existing sections remain unless returned as explicit section revisions.
New factual investigations cannot overwrite sections owned by earlier research;
section-context revisions apply only to their selected section. The research
title stays stable while new sections are appended.
Explicit revisions may change which facts are shown without deleting accepted
facts or their source links from the evidence store. Export before restart or
expiry: runs are in-memory, expire after one hour, capped at 32; each session has
a twelve-turn, 24-task budget. There is no persistent cross-session library.

### Verified tool catalogue

`research_tools.py` is deliberately a small facade, not a general agent framework.

| Tool | Parameters and supported meaning | Explicit non-answers |
|---|---|---|
| `sponsorship` | Named Member mention; recorded Bill sponsorship via validated exact Member/BillParticipation identity; recorded primary classifications and sponsor roles | No housing/other subject filtering, opposition, Senator-period intersection, before-date filter or enactment |
| `lifecycle` | Reference to a successful sponsorship task; one exact number/year lookup per accepted Bill, at most 32 per task | Recorded process status and dated activities, **not certified final outcomes**; no guessed Bill IDs or title join |
| `career` | Named Member mention; recorded constituency/Dáil-term identities across career | No complete offices/committee discovery, continuous tenure, service dates, ministerial-period relationship or arbitrary historical filter |

Requests use existing public compiler execution, fixed reviewed semantic drafts,
identity resolution, plan validation, query safety, pagination/caps and evidence
evaluation. Structured accepted evidence is exposed additively at existing
projectors, not reconstructed from display prose. Exact Bill identity agreement
is checked across sponsorship and lifecycle lookups. A failed/truncated/partial
compiler result produces no established assertions. Earlier independent evidence
survives. The Phase 1 party adapter remains for its existing regression suite,
but its permitted-word coordinator is not the default application's entry point.

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
.venv/bin/python -m pytest -q tests
.venv/bin/python tests/validate.py
uv sync --extra test --extra nlq --extra browser-test
.venv/bin/python -m playwright install chromium
# Against the configured app above:
.venv/bin/python tools/verify_research_v05_browser.py
# Fast, explicitly injected/replayed UI controls (no model or dataset network):
.venv/bin/python tools/verify_research_v05_ui.py
```

New deterministic tests distinguish **injected model proposals** and exact saved
compiler-response replay from live research. The browser verifier exercises the
actual configured model/Fuseki interaction, saves transcripts, model proposals,
assertions, reports and screenshots under `/tmp/oireachtasontology/research-v05/`
by default, and checks R1, revisions, same-session R3, unsupported R4/R5, plan
visibility, evidence controls, keyboard focus, narrow-screen layouts and export.
Use `--output` to choose an artefact directory. `/runs/{id}/archive` provides a
local JSON archive; it includes model inputs/outputs and source records, not API
credentials. Assess generated drafts before sharing.

The completion report records the actual observations and durable representative
artefacts. Browser automation is Chromium-only, not formal WCAG conformance or a
full assistive-technology audit. Human editorial/factual product acceptance remains
the final gate; passing tests does not accept this application.
