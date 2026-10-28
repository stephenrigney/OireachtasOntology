# Query Service completion — recovery and progress record

## Campaign checkpoint

- Branch: `query-service-completion`; baseline at campaign start: `844e51b6fc189a379003c71650e9254c71c67f88`.
- Documentation-only campaign checkpoints: `8e08cc5`, `d7f26aa`, `24503e7`, `2ab5b02`. Stage A code checkpoint: `870aefc7bfe3172b848b034393598645cd212c69` (pushed); no master merge.
- Last stage-accepted code checkpoint remains `870aefc7bfe3172b848b034393598645cd212c69`. B1 shared typed-plan integration and bounded B2 Bill behaviour/executable named-graph fixtures are implemented and verified; **Stage B overall is not accepted**. B3 exact office Member-IRI binding remains the next bounded unit. Stage C has not started.
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
| B | Q12 | Resolves a dated current Transport Committee by grounded official-label matching; returns candidates for multiple current identities and never infers a chair. | Executable `/ask` tests over named Committee/Houses graphs cover a longer official Transport label, ambiguity, and missing-chair diagnostic. | No reviewed chair relationship exists; synthetic RDF proves mechanics, not roster coverage. |
| B | Q14 | Returns the specific Good Friday Committee source-conflict diagnostic; distinguishes the quarantined 33rd-term identity from the 34th-term resource. | Executable `/ask` diagnostic regression; evidence limitation remains documented in the campaign source review. | Does not claim a current roster or that the authoritative 34th-term resource is itself conflicted. |
| B | Q18 | Resolves parameterized official title mentions; preserves distinct Bill IRIs and returns ambiguous candidates rather than combining or guessing. | Executable `/ask` over typed Bill records, including competing identities; exact bill-owner graph regex and pre-query gates exercised. | Synthetic graphs prove query mechanics only; no production title-candidate completeness claim. |
| B | Q19 | Selects any typed `agents:Published` activity with `xsd:date` in the requested calendar year; deduplicates Bills and treats legislativeYear as display-only. | Executable `/ask` named-graph fixture covers an event older than latest activity, dates on either side of year-end, xsd:dateTime decoy, malformed graph suffix, and mismatched display year. | No real Fuseki/source-complete Bill corpus execution asserted. |
| B | Q20 | Selects mapped `legislativeYear` exactly within the exact Bill owner-graph route; classifies only exact mapped non-Enacted status IRIs, deduplicates per Bill before counts, and diagnoses missing/conflicting/unmapped status and display metadata. | Executable `/ask` named-graph coverage plus adversarial missing/conflicting/enacted rows; process/history fan-out does not inflate counts. | Counts describe local rows only; not a complete year corpus. |
| B | Q21 | Resolves title mentions before answer; reports mapped current process status and every mapped typed dated activity, without inferring a next step; multiple Bill IRIs remain ambiguous. | Executable `/ask` fixture asserts multiple dated events and current status; title ambiguity is separately exercised. | No production Fuseki coverage assertion; local result cap yields readable qualified partial output. |
| B | Q22 | Preserves each distinct Participation including role-only rows; strict `xsd:boolean` true/false/1/0 decoding, unknown/malformed/conflicting status, and Member-name join by exact Member IRI in its owner graph. | Executable `/ask` named-graph fixture includes two activities, Member label, absent participant, false flag, strict lexical cases, and 100-row partial-cap rendering. | No full local AI Companion Bill sponsor assertion; missing Member display metadata does not erase Participation. |
| B | Q24A | Exact Bill IRI and owner-graph anchor; English title, mapped process status, all typed dated history, and only Bill-linked typed ExplanatoryMemo Work → LegalExpression → Format renditions. | Executable `/ask` tests cover empty memo, unlinked typed orphan, multiple PDF/XML renditions, typed-work missing-link state, wrong document type, wrong graph and suffix decoys. Preserved capture citation remains the independent source-field evidence. | Capture presence is not Fuseki loading or live-world currency; graph-local absence does not prove no memo elsewhere. |
| B | Q25 | **B3 pending:** Q35 interval route is retained, but exact named Member-IRI binding is not yet implemented. | Existing synthetic interval regressions do not establish exact-member identity. | Do not report a yes/no until B3 binds the requested person to one exact Member IRI. |
| B | Q26 | **B3 pending:** current-coverage diagnostic remains conservative; no holder guessed from alias or stale observation. | Evidence review shows an incomplete 22-holding sample. | Current Finance holder remains unavailable until suitable coverage and B3 identity work are resolved. |
| B | Q27 | **B3 pending:** Q35 inclusive point-date interval path remains in place; no B3 acceptance claim. | Existing synthetic interval regression only. | Preserve exact office/member identity and do not use office alias start as establishment date. |
| C | Q16,Q17,Q24,Q30,Q31,Q36,Q37 | not implemented in campaign | not checked here | Implement supported facts or precise coverage/capability diagnostics; never substitute seats/groups/votes/speech/latest with unrelated facts. |

## Stage A evidence boundaries

- Q10's approved wording requires the method of Seanad entry (including Taoiseach nomination). `mappings/member_mapping.csv` currently maps membership dates and the source representation resource/link/type/label; it does not map an election, appointment, or nomination method. The route does not relabel a panel/constituency as a nomination. Q10 therefore remains unavailable where the mapped RDF supplies no requested designation. This is not an ETL repair request.
- Q03 treats a missing membership end as open only when the associated HouseTerm is demonstrably current at the supplied `asOf`; a historical missing end makes the duration incomplete. Q05/Q07 retain the mapping's explicit DateRange semantics and distinguish missing required range/start evidence from an open end.
- Q11 resolves a uniquely current Committee owner incarnation from its own date range and HouseTerm before Member name resolution. Missing or ambiguous owner-date evidence is not translated to a yes/no answer. The local dataset's committee roster remains incomplete.
- Aggregate and context reads at the 100-row safety cap are reported as incomplete, not exact. Local counts do not establish historical corpus completeness.
- No preserved-source fixture was changed. Synthetic RDF verifies mechanics, not factual coverage in production or the pinned development graph.

## Verification and remaining risks

- **Stage B review correction:** the initial 349-pass result below is not Stage B acceptance. The flat sidecar plan bypassed the authoritative v2 validator; publication used only latest activity and the wrong date datatype; memo lookup did not distinguish memo Works from other documents; identity, sponsor evidence and distinct-counting paths required executable adversarial tests. B1 and B2 are now separately implemented and verified; B3 exact office identity binding remains outstanding, so Stage B remains unaccepted.
- **B1 completed:** all Stage B families use the shared v2 referents/relations/constraints/answer envelope and authoritative `validate_plan`; a closed semantic validator rejects sidecar plans and mutated path, binding, constraint and answer shapes. Its recorded executor regression was **354 passed, 1 skipped**; the final missing-pattern gate test passed separately. The B1-focused validator command recorded **4 passed, 12 deselected**. This is typed-plan foundation evidence, not Stage B acceptance; B2 is verified separately below and B3 remains pending. No full-suite rerun.

- B2 focused acceptance: `.venv/bin/python -m pytest -q tests/test_nlq_stage_b.py` — **29 passed**. It exercises actual RDFLib named-graph execution and rendered `/ask` paths for Q18, Q19, Q20, Q21, Q22, and Q24A, plus Q12/Q14 diagnostics, owner/type/predicate gates, adversarial decoys, strict sponsor booleans, errors, and cap behaviour.
- Post-B2 preserved Query Service regression command: `.venv/bin/python -m pytest -q tests/test_nlq_stage_b.py tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_query_plan.py tests/test_nlq_plan_sparql.py tests/test_nlq_plan_sparql_fuseki.py tests/test_nlq_human_readable.py tests/test_nlq_poc.py` — **367 passed, 1 skipped**. This includes Stage A, the six established query slices, query contract and safety regressions. It is not the full suite.
- Post-B2 `.venv/bin/python -m compileall -q poc/nlq/stage_b.py tests/test_nlq_stage_b.py` and `git diff --check` — **passed**.
- `.venv/bin/python tests/validate.py` — **passed**, 2,584 ontology triples; `.venv/bin/python -m tools.validation` — **passed**, active mapping integrity; compileall and `git diff --check` passed.
- Full test suite intentionally not run; campaign requires it at campaign end after Stage C. B2 verifies local mechanics only; no live Fuseki/source-complete Q18–Q22 results are asserted. Q12/Q14 roster/identity evidence remains constrained as described above.
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

### B2 checkpoint

Bill semantics/executable fixtures corrected after B1. Orchestrator reran
`.venv/bin/python -m pytest -q tests/test_nlq_stage_b.py tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_poc.py tests/test_nlq_human_readable.py`:
**231 passed**. `git diff --check` passed; no protected ontology/mapping/fixture
changes. B2 is checkpointed for its tested Bill behaviour, not corpus completeness;
B3 exact Member binding and office interval checks still block Stage B exit.

- `.venv/bin/python -m pytest -q tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_poc.py tests/test_nlq_human_readable.py` — **202 passed**. All six previously integrated acceptance families passed their focused regressions.
- Corrected the T01 debugger to expose the actual aggregate query executed, not a separate term listing. `.venv/bin/python -m pytest -q tests/test_nlq_composable_stage_a.py -k 't01 or count'` — **8 passed, 63 deselected**.
- `git diff --check` passed; no changes under ontology, mappings, preserved fixtures or golden outputs. Stage A exit is accepted for implemented synthetic-fixture behaviour, with Q10 nomination-method evidence explicitly unavailable. No real-data complete-history/current roster claim is made.
- Earlier premature full-suite run belongs to the pre-correction Stage A snapshot, not campaign-final verification. Final full available suite remains mandatory after B/C integration; it will not be replaced by that earlier run.
