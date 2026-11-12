# Parliamentary Research Assistant — Phase 1: Working Research and Report Vertical Slice

**Date:** 12 November 2026 (verification uses the pinned 11 November reporting date)

**Branch:** `parliamentary-research-assistant`

**Scope:** authorised Phase 1 only; qualified local-record research, not certified rosters.

## Delivered

The [launch and verification guide](../../development/parliamentary-research-assistant.md)
describes the usable two-pane application, configuration, controls, evidence
contract and reproducible checks. Launch with:

```sh
uv sync --extra test --extra nlq
# Export your existing local configuration first if it is in .env.local:
# set -a; source .env.local; set +a
.venv/bin/python -m uvicorn poc.nlq.research_app:app --host 127.0.0.1 --port 8010
```

Implementation comprises:

- A closed current-Dáil term / named-party Member list / distinct recorded-Member
  count adapter. It retains the public compiler's preflight/error boundary and
  existing draft, plan, identity, mapping, safety, paging and temporal validation.
  No second model query planner, unrestricted SPARQL, compiler NLQ expansion,
  ontology, ETL, source-fixture or dataset change.
- Additive structured accepted witnesses at the existing temporal projector;
  untruncated actual query/page traces, exact identities and intervals, fixed
  reporting scope, process-start compiler content identity, observation context
  and explicit unknown snapshot/freshness. Errors remain non-answers.
- The authorised `selectedIRIs` schema alignment, retaining selected party
  identities and Python's existing stricter sorted/resolved-identity checks.
  The schema now limits the field to nonempty unique local IRI arrays on
  `ParliamentaryParty`. No admission rule was relaxed. The two Phase 0 positional
  debug-metadata defects were corrected without changing selection.
- One bounded research interpretation call, whole-brief requirement accounting,
  visible plan, automatic versioned execution, independent term prerequisite,
  progressive report assembly, count/list witness agreement and a deterministic
  local-result comparison. Independent failures preserve successful findings.
- Conversation/report workspace, anchored composer, independent scrolling,
  responsive views, pause/resume, keyboard-accessible activity/evidence dialog,
  status announcements, stable Member-table controls during progressive count
  updates, and qualified Markdown copy/export with retained evidence.

## Configured end-to-end observation

The genuine browser journey used the existing local Responses-compatible model
configuration and existing Fuseki dataset, with **no reload or mutation**. The
brief was the approved Fine Gael / Fianna Fáil comparison including totals,
Members and a short comparison. It was not replaced by a canned plan/answer.

At the fixed reporting date **2026-11-11**:

- House-owned catalogue evidence selected **34th Dáil**, exact IRI
  `https://data.oireachtas.ie/ie/oireachtas/house/dail/34`, recorded start
  `2024-11-29`, no recorded end.
- Fine Gael: **38** distinct accepted recorded Member identities.
- Fianna Fáil: **48** distinct accepted recorded Member identities.
- Both Member tables agreed with their compiler counts and accepted witnesses.
  The deterministic local-result difference was **10**, with Fianna Fáil's
  separately observed selection larger. This is **not** a snapshot-consistent
  claim of real-world party strength.
- Five compiler operations performed **17 actual read-only queries**; a sixth
  workspace step performed the local calculation. The model was used for brief
  interpretation only, never to generate authoritative SPARQL or facts.
- Browser interception established that the plan heading and initial task were
  in the visible conversation viewport **before dispatch**. Intermediate
  accepted sections appeared before the final report.
- In the final configured browser observation, time from run creation to first
  validated finding was **1.572 seconds** and to the qualified completed report
  **4.131 seconds**, including brief interpretation and browser dispatch
  intervals. These are observations, not a performance target.

An independently written, bounded RDF selection read **87 candidate paths**,
checked typed date ranges, required/nonconflicting starts and ends, chronology,
both active intervals and overlap, and matched **all 86 accepted Member IRIs
and display names**. This is agreement over finite, separately read local
evidence—not independent certification of source coverage or a common snapshot.

Application counts and names are retrieved, not hard-coded. Synthetic regression
also exercises another eligible reviewed party name through the same resolver.
A separate configured interaction for **Labour Party** validated all three plan
tasks and returned **11 distinct recorded Members**, with compiler count/list
agreement at the same pinned reporting date. It carries the same uncertified
coverage and unknown-freshness qualifications.

## Verification

| Check | Result |
|---|---|
| Initial focused compiler regressions: current party, temporal composition, Stage A, Stage C | **226 passed** |
| New adapter/coordinator/transport/evidence acceptance suite | **56 passed** in the final affected run |
| Final affected suite, including the existing compiler regressions above | **282 passed** |
| Repository-wide `python -m pytest -q tests --disable-warnings` | **2,490 passed, 26 skipped; 23 subtests passed** |
| `python tests/validate.py` | **Passed**, 2,586 ontology triples; HermiT executed successfully |
| Browser positive and injected independent-operation failure journeys | **Passed** using the actual compiler over synthetic RDF |
| Configured LLM/Fuseki browser journey | **Passed**, all six plan tasks validated |
| Browser viewports | **1440, 1024, 768, 390 and 320 pixels** |
| Keyboard/focus | Enter / Shift+Enter, pause/resume, mobile switching, drawer trapping / Escape / focus return, evidence controls |
| Failure/admission UI | Unsupported residual condition, missing temporal-scope clarification, preserved message on submission failure, preserved first-party findings after later execution failure |
| Export / progressive behaviour | Qualifications, incomplete states and evidence retained; independent report scrolling and prior reading position checked |
| Static checks | Python compilation, JavaScript syntax, `git diff --check` |

New tests include duplicate qualifying episodes, independently ended membership
and party intervals, malformed/missing/conflicting/reversed/wrong-datatype date
evidence, missing/ambiguous identities, missing House metadata, no matches,
unsupported date/committee/second-party conditions, future scope, page two,
pagination exhaustion, trace loss, term mismatch, list/count disagreement and
incompatible comparison inputs. Additional office wording, term/person scope
confusion and an unfulfilled single-party comparison are explicitly rejected
rather than lost during decomposition. No uncertain selection becomes zero or a
complete-looking roster. Existing RDFLib/FastAPI deprecation warnings remain;
the skipped broader tests were not represented as passes.

The repository-wide run preceded the final defensive adapter trace-retention,
content-identity and UI refinements. The final affected run above rechecked all
changed backend paths and the relevant shared compiler contracts afterwards.

Browser verification is executable in `tools/verify_research_browser.py`.
Disposable reports, query evidence, JSON summaries and screenshots are under
`/tmp/oireachtasontology/parliamentary-research-phase-1/`; they are not runtime
dependencies or invented immutable dataset captures. Observed timings are
reported by each run's `metrics`; they include preparation and browser dispatch
intervals and do not establish a latency target.

## Phase 1 exit assessment and limitations

The Phase 0 §8 gates are met for the **authorised qualified-local-record slice**:
closed guarded dispatch; differential/independent identity and witness checks;
negative/paginated evidence integrity; schema/trace retention; compatible
qualified calculation; configured end-to-end report; usable responsive workspace;
and focused plus broad verification without semantic/data mutation.

Important limits remain explicit in the application, report and export:

- Coverage is uncertified; freshness, capture identity and common snapshot are
  unknown. Exact per-row owner graphs are null where not projected.
- Brief admission is deliberately bounded and conservative. Unsupported wording,
  ambiguity, missing evidence and failures do not become inferred facts. Existing
  compiler name/intent rejections remain rejections, not rewritten requests.
- This is a local, single-worker workspace, with in-memory, bounded, one-hour
  runs. Export before expiry/restart; there is no persistent report library or
  authenticated public deployment.
- Browser checks are Chromium automation and visual inspection, not formal
  WCAG certification or a full assistive-technology / multi-browser audit.
- Full conversational clarification continuations, scope changes, approval
  workflows, section editing and state reuse are **Phase 2, not implemented or
  authorised**. Messages explain that boundary without destroying the report.

**Stop after Phase 1.** Further expansion requires human review and authorisation.
