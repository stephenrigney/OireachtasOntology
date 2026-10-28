# Query Service completion — recovery and progress record

## Campaign checkpoint

- Branch: `query-service-completion`; baseline at campaign start: `844e51b6fc189a379003c71650e9254c71c67f88`.
- Documentation-only campaign checkpoints: `8e08cc5`, `d7f26aa`, `24503e7`, `2ab5b02`. Stage A code checkpoint: `870aefc7bfe3172b848b034393598645cd212c69` (pushed); no master merge.
- Current branch HEAD: `2ab5b02` (Stage A checkpoint documentation only); last accepted/tested code checkpoint remains `870aefc7bfe3172b848b034393598645cd212c69`. Stage B work is uncommitted and **not accepted**: initial focused tests did not cover semantic defects found by review. Next bounded unit is B1 shared typed-plan integration, followed by B2 Bill semantics/executable fixtures and B3 exact office identity binding; Stage C has not started.
- Authority: campaign spec, approved question catalogue, composable query contracts, query schema/ownership contract, and source mappings. No ontology, ETL mapping, source fixture, production, ingestion or deployment changes.
- Preserve Q06/Q09/Q23/Q28/Q29/Q35 and their regressions. Compiler remains read-only and safety validated.

## Question matrix

Behaviour and evidence are independent; synthetic execution is not a claim of production-corpus completeness.

| Stage | Cases | Behaviour | Evidence | Work/dependency |
| --- | --- | --- | --- | --- |
| A | Q01 | Implemented: grounded Member lookup; guarded partial names are limited to title-qualified cases. | Synthetic RDF proves mechanics only; no source-completeness claim. | Ambiguity/cap is retained; no guessed identity. |
| A | Q02 | Implemented: previous Dáil service uses House chronology and member-term links. | Synthetic date evidence; arbitrary Fuseki coverage not asserted. | Missing/inconsistent chronology is unavailable, not a negative. |
| A | Q03 | Implemented: union of dated service intervals with gaps. | Synthetic dates are artificial, including membership intervals not intended as factual history. | Global House chronology rejects historical open terms/overlap; no lifetime completeness claim. |
| A | Q04 | Implemented: count distinct membership-linked term IRIs. | Synthetic service links; missing term description does not erase a link. | Exact local count only; no corpus-completeness claim. |
| A | Q05 | Implemented: earliest dated Seanad membership episodes. | Synthetic dates and representation labels; mapping inspected. | Missing/conflicting starts make earliest entry unavailable. |
| A | Q07 | Implemented: current collection status at supplied as-of date. | Synthetic collection and containing-membership evidence. | An open record without valid containing term evidence is not promoted to current. |
| A | Q08 | Implemented: Independent remains distinct from party identity. | Synthetic Independent collection. | Parliamentary status is not called a political party. |
| A | Q10 | Implemented only for mapped term-scoped representation designations; required Taoiseach nomination method unavailable. | Mapping has no election/appointment/nomination method. | No inference from panel or constituency identity. |
| A | Q11 | Implemented: resolve current Committee owner before Member lookup and require exact Committee IRI membership. | Synthetic owner and membership links. | Missing/ambiguous current owner date evidence is unavailable; roster incomplete. |
| A | Q13 | Implemented: count distinct membership-linked Committee IRIs. | Synthetic Committee membership; owner metadata optional. | Exact local identity count only; coverage incomplete. |
| A | Q15 | Implemented: House-owned Dáil dates and explicit missing ends. | Synthetic Dáil term records. | Current open term distinguished using date evidence. |
| A | Q32 | Implemented: preserve all ambiguous same-name Member identities and context. | Synthetic duplicate-name Member records. | Candidate set is explicit; no source-completeness claim. |
| A | Q33 | Implemented: return all exact-name Members with Dáil membership. | Synthetic distinct Member identities and service links. | Distinct IRIs retained, no identity merge. |
| A | Q34 | Implemented: report grounded not-found result. | Synthetic Member catalogue. | Absence is local to queried graph, not proof of external nonexistence. |
| A | T01 | Implemented: count distinct typed DáilTerm IRIs in Houses graph. | Synthetic typed House terms; labels/period metadata not required for count. | Exact local graph count only; no corpus-completeness claim. |
| B | Q12 | Implemented diagnostic: resolve dated current Committee owner first, then report missing chair relationship. | Synthetic current-owner/date graph; no chair RDF asserted. | Exact current Committee ambiguity/date failures remain explicit; no chair inferred from Member membership. |
| B | Q14 | Specific development source conflict/quarantine diagnostic. | Reviewed ID-115 decision and development limitation in etl-plan/evidence note. | Does not claim that authoritative review makes a current roster. |
| B | Q18 | Title-token lookup for Artificial Intelligence/protection/children; returns all matching identities instead of guessing. | Synthetic query-plan/compiler route only; no real title-candidate result asserted. | No result means no locally recorded matching title, not nonexistence. |
| B | Q19 | Dated Published event selection in calendar year; no legislativeYear fallback. | Contract-backed compiler route; no real Bill corpus execution. | Restricted to dated `latest_activity`; not a complete lifecycle-event inventory and is qualified as such. |
| B | Q20 | Non-Enacted status query with local grouped counts; missing/conflicting status is explicit. | Synthetic query-plan/compiler route; no real year-2026 counts asserted. | Distinct Bill graph evidence; no complete source coverage claim. |
| B | Q21 | Current mapped process status plus dated latest activity; no inferred next step. | Synthetic query-plan/compiler route; no live Fuseki coverage asserted. | Limited to the exposed latest activity. |
| B | Q22 | Reverse sponsorship query retains all Participation rows, optional primary true/false/absent, role-only evidence, and exact Member-IRI display join. | Contract-checked route; no full local AI Companion Bill sponsor assertion. | Unknown primary status remains Unknown; member label absent does not erase role-only evidence. |
| B | Q24A | Exact 2025/23 lookup, English title, mapped Current status, official IRI, dated latest activity and same-graph memo rendition. | Actual selected-source fields verified in preserved capture citation; tiny in-memory fixture tests no-memo and available memo paths. | Capture presence is not Fuseki loading or live-world currency; empty relatedDocs does not prove no memo elsewhere. |
| B | Q25 | Reuses Q35 strict accepted OfficeHolding interval route for any September overlap and exact Member filter. | Synthetic holder/date execution; accepted source-backed review citation is 2026-10-02 capture cited in evidence note. | No current roster-completeness assertion. |
| B | Q26 | Specific current-coverage diagnostic; no holder guessed from alias or stale observation. | Evidence review shows incomplete 22 accepted holdings and no accepted Simon Harris tenure. | Current Finance holder remains unavailable until complete suitable coverage is loaded. |
| B | Q27 | Reuses Q35 inclusive interval evidence constrained to the requested point date. | Synthetic Paschal Donohoe interval execution; accepted source-backed review citation is 2026-10-02 capture cited in evidence note. | Does not use office alias start as establishment date. |
| C | Q16,Q17,Q24,Q30,Q31,Q36,Q37 | not implemented in campaign | not checked here | Implement supported facts or precise coverage/capability diagnostics; never substitute seats/groups/votes/speech/latest with unrelated facts. |

## Stage A evidence boundaries

- Q10's approved wording requires the method of Seanad entry (including Taoiseach nomination). `mappings/member_mapping.csv` currently maps membership dates and the source representation resource/link/type/label; it does not map an election, appointment, or nomination method. The route does not relabel a panel/constituency as a nomination. Q10 therefore remains unavailable where the mapped RDF supplies no requested designation. This is not an ETL repair request.
- Q03 treats a missing membership end as open only when the associated HouseTerm is demonstrably current at the supplied `asOf`; a historical missing end makes the duration incomplete. Q05/Q07 retain the mapping's explicit DateRange semantics and distinguish missing required range/start evidence from an open end.
- Q11 resolves a uniquely current Committee owner incarnation from its own date range and HouseTerm before Member name resolution. Missing or ambiguous owner-date evidence is not translated to a yes/no answer. The local dataset's committee roster remains incomplete.
- Aggregate and context reads at the 100-row safety cap are reported as incomplete, not exact. Local counts do not establish historical corpus completeness.
- No preserved-source fixture was changed. Synthetic RDF verifies mechanics, not factual coverage in production or the pinned development graph.

## Verification and remaining risks

- **Stage B review correction:** the initial 349-pass result below is not Stage B acceptance. The flat sidecar plan bypassed the authoritative v2 validator; publication used only latest activity and the wrong date datatype; memo lookup did not distinguish memo Works from other documents; identity, sponsor evidence and distinct-counting paths require executable adversarial tests. Partial corrections have been made, but B1/B2/B3 must complete and be reviewed before checkpointing or advancing. The question rows below/above describing the first draft are provisional until corrected integration evidence is recorded.

- Stage B focused and preserved Query Service regressions: `.venv/bin/python -m pytest -q tests/test_nlq_stage_b.py tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_query_plan.py tests/test_nlq_plan_sparql.py tests/test_nlq_plan_sparql_fuseki.py tests/test_nlq_human_readable.py tests/test_nlq_poc.py` — **349 passed, 1 skipped**. This includes every Stage A family and all six established query slices.
- `.venv/bin/python tests/validate.py` — **passed**, 2,584 ontology triples; `.venv/bin/python -m tools.validation` — **passed**, active mapping integrity; compileall and `git diff --check` passed.
- Full test suite intentionally not run; campaign requires it at campaign end after Stage C.
- Q24A exercises the preserved source-backed Bill fields in a tiny synthetic RDF graph and separately tests a synthetic memorandum rendition; no source fixture or operational corpus was rebuilt.

- Auditor-correction focused regressions and preserved slices: `.venv/bin/python -m pytest tests/test_nlq_composable_stage_a.py tests/test_nlq_contract.py tests/test_nlq_query_plan.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_prefixes.py -q` — **271 passed**.
- Final Stage A rerun after the no-plan UI adjustment: `.venv/bin/python -m pytest tests/test_nlq_composable_stage_a.py -q` — **71 passed**.
- Query safety and presentation: `.venv/bin/python -m pytest tests/test_nlq_plan_sparql.py tests/test_nlq_plan_sparql_fuseki.py tests/test_nlq_human_readable.py -q` — **42 passed, 1 skipped**.
- `.venv/bin/python -m compileall -q poc/nlq/stage_a.py poc/nlq/app.py poc/nlq/composable_plan.py` — **passed**. `git diff --check` — **passed**.
- Warnings are existing FastAPI/httpx and RDFLib deprecations; no test failures in the stated run.
- Ontology validation: `.venv/bin/python tests/validate.py` — **passed**, 2,584 ontology triples.
- Ontology validation after the auditor corrections: `.venv/bin/python tests/validate.py` — **passed**, 2,584 ontology triples.
- Earlier full suite before the auditor-correction edits: `.venv/bin/python -m pytest tests` — **1,617 passed, 25 skipped**. As requested, the full suite was not rerun during these corrections; the exact focused checks above cover Stage A, preserved composable slices, contract and query safety.
- Stage B implementation is uncommitted on the shared branch; current HEAD remains the Stage A checkpoint `870aefc7bfe3172b848b034393598645cd212c69`. The Stage A Q10 mapping limitation remains unchanged. No commit/push/merge from this executor.

## Orchestrator Stage A integration

- `.venv/bin/python -m pytest -q tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_poc.py tests/test_nlq_human_readable.py` — **202 passed**. All six previously integrated acceptance families passed their focused regressions.
- Corrected the T01 debugger to expose the actual aggregate query executed, not a separate term listing. `.venv/bin/python -m pytest -q tests/test_nlq_composable_stage_a.py -k 't01 or count'` — **8 passed, 63 deselected**.
- `git diff --check` passed; no changes under ontology, mappings, preserved fixtures or golden outputs. Stage A exit is accepted for implemented synthetic-fixture behaviour, with Q10 nomination-method evidence explicitly unavailable. No real-data complete-history/current roster claim is made.
- Earlier premature full-suite run belongs to the pre-correction Stage A snapshot, not campaign-final verification. Final full available suite remains mandatory after B/C integration; it will not be replaced by that earlier run.
