# Parliamentary Research Assistant — General Query Service integration

**Branch:** `parliamentary-research-assistant` · **Date:** 13 November 2026  
**Status:** implemented; human research/product review required. No merge to `master`.

## Integration

The former three-tool catalogue is no longer the admission/discovery boundary.
The research LLM proposes `query(question)` with relevance and a direct,
supporting or exploratory role. `ResearchTools._query` passes that exact question
through `composable_plan.execute_question`, with the same
`create_composable_plan_generator` used by the Query Service. Existing service
contracts and `build_composable_planner_instructions` supply discovery context;
there is no second capability registry, new semantic compiler, arbitrary SPARQL,
external evidence source or dataset change.

The coordinator retains the original brief and requirement ledger. After results
or limitations, it can publish another LLM-proposed investigation before factual
dispatch: at most three continuation rounds per user turn within the existing
24-task session budget. Identical investigations are not automatically rerun.
The existing 32-Bill exact-identity lifecycle batch remains a convenience, and
legacy typed requests remain compatible with retained sessions/replay controls;
neither restricts new subject matter. Editorial turns reuse evidence.

Key paths: `poc/nlq/research_tools.py`, `research_collaborator.py`,
`research_evidence.py`, `research_assertions.py`, and the unchanged Query Service
planner/compiler/executors. The v0.6 layout is unchanged. The existing evidence
dialog additionally exposes retained general service responses, distinctly from
accepted research facts. A reusable `facts` table displays exact established
wording for accepted propositions without a specialised table; it adds no
capability-specific report mapping. The architecture contract is recorded in specification
§§12.2–12.4 and 13.

## Evidence authority

`accept_query_evidence` normalises **existing accepted evidence**, not rendered
rows or model interpretations. Existing sponsorship, Bill lifecycle and
representation projections retain exact identities, relationships and source
qualifications. Current-Dáil party Member witnesses reuse the established
`AcceptedMember` shape and ResearchAdapter's scope/list/count parity checks;
their exact separate intervals, reporting date and query references survive.
No new calculations were approved. Existing sponsorship cardinality remains
Level 2; exact source propositions remain Level 1; authored interpretations and
hypotheses retain the existing provisional Level 3/segregated Level 4 rules.

Successful execution is **not** research-question satisfaction. Clarification
candidates, unsupported semantics, missing/unaccepted evidence, validation and
execution failures remain structured. Every envelope retains the exact request,
plan, all actual resolution/answer reads, compiler content identity and dataset
observation context. Service-model proposals and research prompts/outputs are
archived. Source completeness, freshness and a common transaction/snapshot are
not inferred.

In particular, party history currently emits readable results but **no
`accepted_evidence` payload**. Its result is inspectable with separate service
success and research `missing_or_unaccepted_evidence` outcomes. No party-history
fact mapping was invented. Unknown evidence shapes also fail closed. This
deliberately leaves some valid Query Service answers unsuitable for established
research prose.

## Real validation and limitations

The [evidence index](general-query-evidence/README.md) distinguishes fresh
configured-model/Fuseki observations from synthetic/replay controls, and retains
the earlier interrupted trial rather than counting it as success.

The preflight independently verified both A and D against actual data before the
research campaign:

- **A underlying data:** reviewed Fianna Fáil and Social Democrats identities,
  with four separate dated membership episodes. Fianna Fáil records are
  2 February 2017–14 January 2020 and 8 February 2020–8 November 2024; Social
  Democrats records are 15 July 2015–9 March 2016 and 10 March–4 September 2016.
  These are retrieved source episodes, not a complete continuous timeline or
  established Research Assistant facts. No missing dates occurred in these four
  live rows; existing missing-date fixture regressions separately verify that
  parliamentary-term dates are never substituted for absent party dates.
- **D underlying data:** the existing current-Dáil Labour selection returned
  eleven distinct Member identities with accepted separate party/parliamentary
  intervals containing the reporting date. This is not a certified complete
  roster. Labour was chosen as an independent existing capability test, not
  registered or hard-coded in the integration.

### Research campaign

Configured requested model: **`gpt-6-luna`**; reporting date **13 November 2026**.

| Case | Actual observation |
|---|---|
| **A — Stephen Donnelly** | The exact timing question reached the service but its semantic planner refused the date projection, despite the underlying capability's readable episode evidence. The research LLM then explicitly proposed a narrower affiliation investigation; it executed two reads and recovered the existing party-history result. No facts were promoted because the compiler supplies no accepted-evidence payload. The original timing question remains unanswered. This is neither missing party data nor a fully answered research question. |
| **B — R1** | General sponsorship query plus the existing exact-Bill batch retained 20 Bills, 129 direct facts and the approved distinct-Bill calculation. Twenty lifecycle lookups and sponsorship used 22 reads. The 20-row table retains exact sponsorship/status/activity evidence; unsupported final-outcome/enactment questions remain open. A real editorial turn reduced narrative from 264 to 158 words (40%), with the table and all 130 facts exactly unchanged and no extra reads. |
| **C — Mary Lou McDonald** | Five subsidiary investigations across representation, term membership, role history, committee history and generic offices. Two reads produced four accepted Dublin Central/Dáil-term facts and a four-row representation table. The service refused unsupported generic historical role/committee/office enumeration; the draft preserves those gaps and does not infer continuous tenure. |
| **D — independent generalisation** | The final fresh run returned eleven accepted Labour Member facts through one general query/four reads, with a populated source-backed report. A same-session Fine Gael question added 38 accepted Member facts through four more reads and a generic exact-fact table. Earlier Labour facts and report sections stayed exactly unchanged; no total comparison was inferred. Six research-model calls covered both turns. See `final-d/`. Neither party was registered or hard-coded in the Research Assistant. |
| **E — unsupported speeches** | The exact speech/topic/year request reached service admission and was refused. Zero reads, zero accepted facts, no quotations, and no irrelevant substitute query. The model also asked for calendar-year clarification, although it could not retrieve speech content either way. |

The natural party-history paraphrase also exercised the general interface: it
encountered existing service tense/date refusals, then obtained the career-wide
party-history result through two reads. It still promoted no party-history facts.
This demonstrates a usable guarded route, **not reliable arbitrary paraphrase
recognition or a complete party-history research answer**.

The first A trial used overly technical repeated paraphrases and performed no
reads; a shell timeout then interrupted the campaign. It is preserved as a failed
trial. The general planning instruction was corrected to prefer ordinary,
unchanged concrete questions and avoid repeated refusals. The first D campaign
exposed an author/presentation mismatch, not missing data or compiler discovery:
party evidence was accepted but the model repeatedly selected a representation
table. The exact-proposition guard rejected it. The correction adds one generic
exact-fact presentation for any established proposition; it neither weakens that
guard nor fabricates a party-history evidence mapping.

### Checks

- Repository suite: **2,575 passed, 26 skipped**, 23 subtests passed, with the live
  model key disabled for deterministic tests. This ran before the final generic
  fact-table presentation correction; focused final coordinator/evidence/table
  tests are **110 passed**, covering the subsequent local correction and
  additional controls (16 general-integration tests plus 94 existing regressions).
- Ontology validation: **2,586 triples**, HermiT executed successfully.
- Existing injected-model/exact compiler-replay browser controls pass at
  1440/1024/768/390/320px, including plan-before-dispatch, nested evidence/focus,
  revisions, failure retention, pause/retry and stable reading position; no
  JavaScript errors. These are not fresh real-model browser acceptance or human
  usability assessment.
- Source syntax, JavaScript syntax, whitespace and retained credential-value
  scans pass. No existing compiler fixture/acceptance assertion was weakened.

The broad suite's warnings and skipped checks are not counted as passes. Live
records use compiler content identities at process start; later local cache,
limitation-display and generic-table corrections are covered separately rather
than misrepresenting earlier archives as executions of the final bytes.

## Remaining boundary and human gate

General question admission does not mean universal executable semantics or
universal research-fact coverage. Existing service recognition/planner refusals
and incomplete accepted-evidence interfaces remain real limitations, separately
from source-data absence. Generic parliamentary-role discovery, speech content,
certified final legislative outcomes and source-wide completeness remain
unproven/unavailable where the service cannot establish them. No compiler guard,
semantic acceptance, ontology, mapping, ETL or source fixture was weakened.

Human review must decide whether the wider-service research experience is useful
and honest against the preserved briefs. Technical integration and limited live
examples do not constitute independent editorial, factual or usability
acceptance. **Stop at human review; do not merge.**
