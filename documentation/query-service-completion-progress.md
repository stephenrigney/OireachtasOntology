# Query Service completion — recovery and progress record

## Campaign checkpoint

- Branch: `query-service-completion`; baseline at campaign start: `844e51b6fc189a379003c71650e9254c71c67f88`.
- Documentation-only campaign checkpoints: `8e08cc5`, `d7f26aa`, `24503e7`. Stage A code checkpoint is being recorded after orchestrator integration verification; no master merge.
- Last tested campaign checkpoint: Stage A working tree immediately following `24503e7`; exact code SHA recorded after commit. Next slice: Stage B Bills, accepted office tenure and committee diagnostics. Independent Stage A review remains advisory and any concrete correction will be checkpointed separately.
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
| B | Q12,Q14,Q18,Q19,Q20,Q21,Q22,Q24A,Q25,Q26,Q27 | not implemented in campaign | not checked here | Inspect Bill, office and committee evidence; preserve unknown sponsor status and coverage boundaries. |
| C | Q16,Q17,Q24,Q30,Q31,Q36,Q37 | not implemented in campaign | not checked here | Implement supported facts or precise coverage/capability diagnostics; never substitute seats/groups/votes/speech/latest with unrelated facts. |

## Stage A evidence boundaries

- Q10's approved wording requires the method of Seanad entry (including Taoiseach nomination). `mappings/member_mapping.csv` currently maps membership dates and the source representation resource/link/type/label; it does not map an election, appointment, or nomination method. The route does not relabel a panel/constituency as a nomination. Q10 therefore remains unavailable where the mapped RDF supplies no requested designation. This is not an ETL repair request.
- Q03 treats a missing membership end as open only when the associated HouseTerm is demonstrably current at the supplied `asOf`; a historical missing end makes the duration incomplete. Q05/Q07 retain the mapping's explicit DateRange semantics and distinguish missing required range/start evidence from an open end.
- Q11 resolves a uniquely current Committee owner incarnation from its own date range and HouseTerm before Member name resolution. Missing or ambiguous owner-date evidence is not translated to a yes/no answer. The local dataset's committee roster remains incomplete.
- Aggregate and context reads at the 100-row safety cap are reported as incomplete, not exact. Local counts do not establish historical corpus completeness.
- No preserved-source fixture was changed. Synthetic RDF verifies mechanics, not factual coverage in production or the pinned development graph.

## Verification and remaining risks

- Auditor-correction focused regressions and preserved slices: `.venv/bin/python -m pytest tests/test_nlq_composable_stage_a.py tests/test_nlq_contract.py tests/test_nlq_query_plan.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_prefixes.py -q` — **271 passed**.
- Final Stage A rerun after the no-plan UI adjustment: `.venv/bin/python -m pytest tests/test_nlq_composable_stage_a.py -q` — **71 passed**.
- Query safety and presentation: `.venv/bin/python -m pytest tests/test_nlq_plan_sparql.py tests/test_nlq_plan_sparql_fuseki.py tests/test_nlq_human_readable.py -q` — **42 passed, 1 skipped**.
- `.venv/bin/python -m compileall -q poc/nlq/stage_a.py poc/nlq/app.py poc/nlq/composable_plan.py` — **passed**. `git diff --check` — **passed**.
- Warnings are existing FastAPI/httpx and RDFLib deprecations; no test failures in the stated run.
- Ontology validation: `.venv/bin/python tests/validate.py` — **passed**, 2,584 ontology triples.
- Ontology validation after the auditor corrections: `.venv/bin/python tests/validate.py` — **passed**, 2,584 ontology triples.
- Earlier full suite before the auditor-correction edits: `.venv/bin/python -m pytest tests` — **1,617 passed, 25 skipped**. As requested, the full suite was not rerun during these corrections; the exact focused checks above cover Stage A, preserved composable slices, contract and query safety.
- Returned for reviewer/orchestrator review. Q10 remains mapping-limited and does not infer nomination method. No commit/push/merge from this executor.

## Orchestrator Stage A integration

- `.venv/bin/python -m pytest -q tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_poc.py tests/test_nlq_human_readable.py` — **202 passed**. All six previously integrated acceptance families passed their focused regressions.
- Corrected the T01 debugger to expose the actual aggregate query executed, not a separate term listing. `.venv/bin/python -m pytest -q tests/test_nlq_composable_stage_a.py -k 't01 or count'` — **8 passed, 63 deselected**.
- `git diff --check` passed; no changes under ontology, mappings, preserved fixtures or golden outputs. Stage A exit is accepted for implemented synthetic-fixture behaviour, with Q10 nomination-method evidence explicitly unavailable. No real-data complete-history/current roster claim is made.
- Earlier premature full-suite run belongs to the pre-correction Stage A snapshot, not campaign-final verification. Final full available suite remains mandatory after B/C integration; it will not be replaced by that earlier run.
