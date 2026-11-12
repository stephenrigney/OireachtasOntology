# Parliamentary Research Assistant v0.5 — implementation and human review

**Branch:** `parliamentary-research-assistant`  
**Authority:** separately authorised bounded v0.5 implementation; no ontology,
ETL, mapping, dataset or production-service configuration changes.  
**Product status:** evidence-grounded **Draft — for review**; human product
acceptance pending. No independent editorial acceptance or calibrated confidence
is claimed.

## Implementation

The default application now uses `research_collaborator.py`, not the rejected
Phase 1 permitted-word coordinator. An actual configured LLM proposes an
interpretation, subsidiary research questions, relevance and a versioned plan.
The original brief and subsequent instructions remain visible. Plan publication
is separated from factual dispatch. The application automatically executes the
closed catalogue in `research_tools.py` through existing public compiler guards.

The legislative journey identifies exact recorded sponsorship and roles, then
uses accepted number/year identities for separate Bill lifecycle lookups. The
career tool retains exact Member/constituency/Dáil-term relationships without
inventing offices or continuity. Additive `accepted_evidence` projections retain
existing compiler acceptance semantics; no query selection is weakened.

The LLM selects report structure, established fact references and explanatory
paragraphs. It writes and revises a living draft, rather than filling a fixed
party-count report. Pure editorial follow-ups reuse accepted evidence; new
research adds affected tasks while retaining unrelated sections and facts.

Each factual assertion has immutable compiler-authorised text and proposition
(Level 1), or an approved reproducible distinct-Bill calculation (Level 2).
The model can select these IDs but cannot relabel arbitrary prose as established.
Its narrative is explicitly provisional Level 3, with high/moderate/low confidence
and a reviewable rationale, or unverified Level 4 in a separate further-questions
section. References alone do not verify unrestricted narrative. Source freshness
and completeness remain separate and unknown/uncertified respectively.

The two-pane responsive workspace retains automatic progressive steps,
pause/resume, Research Activity, keyboard-accessible assertion inspection,
section-context revision and qualified Markdown export. Server-side messages
replace the old canned follow-up response. Exact compiler reads and model
inputs/outputs can be archived locally for review.

See the [launch and contract guide](../../development/parliamentary-research-assistant.md)
and [frozen evaluation cases](v05-evaluation-cases.md).

## Verification categories

- **Deterministic controls:** injected proposals, exact saved compiler-response
  replay, assertion promotion/confidence controls, revision preservation and HTTP
  boundaries. These are not model error-rate measurements.
- **Actual model research:** configured LLM interpretation/report authorship and
  read-only existing Fuseki observations. No canned research prose or data reload.
- **Language controls:** actual model planning on AI-authored paraphrases and
  qualifiers, separately labelled; not independently collected researcher briefs.
- **Independent implementation review:** technical challenge, not human editorial
  or parliamentary product acceptance.

The independent read-only review found no compiler acceptance weakening or
semantic drift. It identified the report/UI defects below; follow-up reviews
found no material blockers in the applied corrections or the exact fact-handle /
conversational-assertion delta. It independently reran the focused tests. This
technical review is not an independent parliamentary/editorial product decision.

An early live run exposed a duplicate model section ID that silently displaced
the intended progress discussion. That run is **not cited as successful product
evidence**. The coordinator now rejects duplicate section/paragraph IDs and
permits one bounded structure/reference-repair retry; it never auto-renames a
hypothesis into findings. Explicit section revisions may select fewer displayed
facts, while the accepted fact/evidence store remains intact. The same review
corrected stale pending questions, main-report visibility of partly-supported
requirements, editorial title drift, duplicated chat echoes, session-budget
error handling and focus retention. These are implementation corrections, not
a revival of semantic-completeness or model self-verification gates.

Live model trials also exposed mistyped long assertion IDs. Short model-facing
fact handles now resolve by **exact** stable registry lookup; no fuzzy binding
or guessed source is accepted. The handle map is archived with each model call.
Conversational findings can carry an exact-text Level 3 assertion with the same
evidence/confidence contract and inspector as the report. A process-only response
uses no assertion. Whether the model wrongly leaves substantive text classified
as process-only remains a human-review risk, not something the application
claims to prove from arbitrary prose.

### Executed technical checks

- Initial affected adapter/compiler regressions: **181 passed**.
- Repository-wide run: **2,543 passed, 26 skipped; 23 subtests passed**. This run
  preceded the final report-structure/UI corrections; final affected checks are
  recorded separately, not represented as a second full-suite run.
- Ontology validation: **passed**, 2,586 triples, HermiT executed successfully.
- Final affected suite after the report, handle and conversational corrections:
  **207 passed**, including **26 new** injected/replay/coordinator tests and the
  relevant existing adapter, sponsorship, lifecycle and representation regressions.
- Fast browser controls over an **injected model + exact compiler-response
  replay** passed plan-in-viewport-before-dispatch, pause/resume, modal Tab /
  Escape / focus return, single user-message replay and retained report after an
  independent query failure. These are not actual-model research observations.
- Python compilation, JavaScript syntax and `git diff --check` passed during
  development. Existing RDFLib/FastAPI warnings remain; skipped tests are not
  counted as passes.

## Four product dimensions — human acceptance remains pending

| Dimension | Implementation evidence | Human assessment required |
|---|---|---|
| Language understanding | Original briefs, model interpretations, proposed requirements, plan versions and explicit known gaps retained | Faithfulness and any omitted material condition across realistic phrasing |
| Research usefulness | Sponsorship → exact lifecycle research; bounded career findings; same-session report refinement | Whether the briefing answers the research purpose usefully at its stated scope |
| Editorial quality | LLM-authored explanatory report and dialogue; draft status and visible qualifications | Readability, parliamentary language, proportionality and usefulness of the narrative |
| Factual integrity | Exact Level 1/2 source/calculation authority; provisional interpretation/hypothesis classes; inspectable reasoning and traces | Review model narrative, interpretative rationale and any unsupported stronger relationship |

### Actual model language-control observations

Two additional R1 paraphrases both proposed sponsorship followed by lifecycle
research. Two R3 paraphrases proposed career representation plus recorded Bill
sponsorship as limited responsibility-related context; neither constitutes a
complete parliamentary-role discovery operation. The housing control proposed
supporting sponsorship retrieval and identified the subject-evidence gap. The
opposition control selected no tool and explicitly distinguished sponsorship
from opposition. Senator/before-date and ministerial-period controls retained
their unestablished temporal/role conditions while proposing narrower context.

These are finite **planning observations**, not full factual research runs or an
independent language-quality score. In particular, the model's use of
“classifications” in sponsorship discussion must not be read as subject/topic
classification. Primary/Supporting concerns sponsorship only. Any such broader
claim in narrative requires human correction, not promotion through a citation.

## Limitations and remaining risks

- No universal natural-language completeness gate is reinstated. Model
  interpretation can omit conditions; preserved originals, plans and drafts are
  review materials, not an assertion that all conditions were understood.
- Free narrative remains model-authored and provisional. Structural/reference
  checks do not independently certify sentence meaning, editorial quality or
  qualitative confidence. No confidence calibration is claimed.
- Model-labelled process-only conversation is not independently checked for
  hidden factual content. Inspect the retained dialogue as well as report
  assertions. Classified conversational explanations are inspectable in the UI
  and JSON archive; Markdown report export covers report sections, not dialogue.
- Section evidence state is deliberately conservative: Populating during work,
  Incomplete afterwards. It is separate from overall draft status and individual
  Level 1/2 fact support; the application does not certify entire prose sections.
- Records do not certify complete sponsorship/career coverage, current freshness,
  common snapshots or final legislative outcomes. Recorded statuses and activity
  histories can appear inconsistent; no procedural explanation is inferred.
- No general office/committee-role discovery, ministerial-period intersection,
  subject-classified Bill search, opposition evidence, transcript analysis or
  committee-party join. No external web evidence is introduced.
- Local, single-worker, in-memory sessions; twelve turns, 24 planned tasks,
  32 lifecycle lookups per task, one-hour expiry and 32-run capacity. Export
  before restart. Not an authenticated public deployment or saved-report library.
- Chromium automation is not formal WCAG conformance, multi-browser coverage or
  a full assistive-technology audit. Human keyboard/screen-reader assessment is
  still appropriate.

**Stop at human product acceptance.** Automated success does not accept this
application and does not authorise another implementation tranche.
