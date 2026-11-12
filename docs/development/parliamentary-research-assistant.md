# Parliamentary Research Assistant — Phase 1

The local workspace implements the initial current-Dáil research journey from
the [approved specification](../specifications/parliamentary-research-assistant.md).
It does not implement Phase 2 conversational refinement or change the dataset.

## Launch

From the repository root:

```sh
uv sync --extra test --extra nlq
# If your existing local settings are in .env.local, export them first:
# set -a; source .env.local; set +a
.venv/bin/python -m uvicorn poc.nlq.research_app:app --host 127.0.0.1 --port 8010
```

Open <http://127.0.0.1:8010>. This is a **single-process local research tool**,
not an authenticated public deployment. Use one worker. Existing `.env.local`
configuration can be exported as above. The existing query-service loader
automatically reads `.env` (not `.env.local`); process settings take precedence:

- `NLQ_LLM_API_KEY`, `NLQ_LLM_BASE_URL`, `NLQ_LLM_MODEL`: the existing
  Responses-compatible planner configuration. One bounded interpretation call
  per new brief; no model-generated SPARQL or second query-planning call.
- `NLQ_FUSEKI_QUERY_URL`, `OIR_FUSEKI_USER`, `OIR_FUSEKI_PASSWORD`: existing
  read-only query configuration. No update, reload or publication is performed.
- `OIR_NLQ_AS_OF_DATE`: optional ISO reporting date; otherwise the server's
  calendar date. Frozen once per run. Future reporting dates are refused.

For example, ask:

> Prepare a short report comparing Fine Gael and Fianna Fáil membership in the
> current Dáil, including membership totals, the Members involved and a short
> comparison.

Other eligible named parties work through the same compiler identity resolver;
the example names and observed counts are not application facts. A single-party
list/count or a current-term-only brief also works. The bounded brief-language
admission is intentionally conservative: unknown wording, missing explicit
current/chamber scope, extra dates, relationships or conditions stay visible as
unanswered rather than silently producing an easier report. Existing compiler
name/intent guards remain authoritative; rejected wording is not rewritten.
Comparison briefs need at least two named parties. A term-only brief must ask
explicitly for the current Dáil term; person/office/representation wording is
not silently converted into a term lookup.

## Using the workspace

- The initial plan is returned without opening a query client, brought into the
  conversation viewport, and painted before the browser automatically dispatches
  its first execution step. No per-query approvals are required.
- The report receives the independently validated term, each Member list, each
  compiler-verified total, and finally a compatible deterministic comparison.
  Lists can remain available if count verification or another party fails.
- **Pause research** stops further dispatch; an in-flight read may finish.
  **Resume research** continues the same versioned plan. A transport retry cannot
  replay an already committed step.
- **Research Activity** opens a keyboard-trapped dialog with plan status and
  actual execution history. Evidence buttons open accepted identities, temporal
  witnesses, original requests, plans and every executed query/page. Advanced
  technical material is collapsed by default.
- **Copy Markdown** / **Export .md** retains limitations, pending/failed states,
  evidence references and complete retained evidence JSON. Export before closing
  or restarting the server. Runs are in memory, capped at 32 and expire after an
  hour. Browser reload does not restore a report library.
- Mobile navigation switches between Conversation and Report without replacing
  their state. Tables have independently scrollable regions. Enter sends;
  Shift+Enter adds a line. All controls work with a keyboard.
- Messages during a run are retained and explain the Phase 1 boundary. They do
  not change the original objective or replace findings. Use **New research**
  for a fresh brief. Section-context explanation is available; editing, approval
  continuations and multi-turn scope/refinement workflows require Phase 2.

## Evidence and authority

`research_adapter.py` exposes only:

1. `dail.current_term`
2. `dail.party_members.current`
3. `dail.party_member_count.current`

`OperationRequest` rejects unknown fields, unknown operations, caller-supplied
IRIs and invalid parameter shapes. `/contracts` exposes its JSON Schema and the
accepted envelope schema. The in-process facade is `ResearchAdapter.execute`;
there is deliberately no unrestricted query endpoint in this application.

The explicit dispatch seam runs **after the existing compiler's shared
whole-intent/date/interpretation preflight**, inside its existing read-only error
boundary. Party drafts still pass existing admission, completion, final-plan
validation, term/identity resolution, Stage C party cross-check, mapping/safety
checks, bounded pagination and independent temporal evaluation. The adapter
does not interpret raw candidate rows or reverse-parse rendered evidence.

The temporal projector additively retains accepted structured witnesses for
the current single-term Dáil party shape, including count support. It does not
change temporal selection. `selectedIRIs` is now declared in the final plan
schema as a nonempty unique local-IRI list on `ParliamentaryParty` only, matching
the existing executable validator; its stricter sorted/resolved-identity guards
remain in Python. Selected identities are never dropped to obtain conformity.
The two positional `QueryResult` debug-metadata errors identified in Phase 0
are corrected without changing query semantics.

The coordinator independently requires a successful Stage A catalogue selection
and exact term agreement before using party findings. Compiler counts and lists
must agree by accepted Member identity **and witnesses**, not just raw row count.
Comparison requires compatible dates, exact term, unit, validation, complete
bounded enumeration, observation context, compiler content identity and coverage
qualifications. A failed comparison does not invalidate independent findings.

No loaded snapshot identity is available. Comparisons are explicitly limited
to **separately observed local query results**, not snapshot-consistent statements
of real-world party strength. Coverage is uncertified; freshness is unknown.
Per-row owner graphs remain null where not actually projected. Query traces
retain actual fixed/variable graph scopes, untruncated returned cells (including
datatype/language hints), timing, offsets and failures; they are not invented
ETL capture provenance. A missing accepted witness or execution trace blocks
dependent claims. No-match party evidence remains unavailable, never zero.

## Verification

```sh
.venv/bin/python -m pytest tests/test_research_workspace.py
.venv/bin/python -m pytest tests
.venv/bin/python tests/validate.py

uv sync --extra test --extra nlq --extra browser-test
.venv/bin/python -m playwright install chromium
.venv/bin/python tools/verify_research_browser.py
# With the configured application above already running:
.venv/bin/python tools/verify_research_browser.py --live-url http://127.0.0.1:8010
```

The browser check uses a disposable synthetic-RDF service with the **actual
compiler**, exercises independent-operation failure and admission states, then
optionally runs the genuine configured LLM/Fuseki journey. It checks visible
plan-before-dispatch, progressive updates, table/count evidence, export,
desktop/tablet/390px/320px layouts, independent report scrolling, keyboard/focus,
dialog trapping and zoom-equivalent reflow. Disposable screenshots, reports and
summaries are written under
`/tmp/oireachtasontology/parliamentary-research-phase-1/`.

These automated checks are not a formal WCAG certification or a multi-browser /
assistive-technology audit. Query results are finite observations against the
configured local dataset, never a certification of source completeness.
