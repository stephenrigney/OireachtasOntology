# Query Service completion — acceptance and recovery record

> **Historical progress snapshot.** The completion evidence report is the final
> acceptance record. This checkpoint is retained for recovery traceability and
> is not a current backlog or active implementation status.

## Current checkpoint

- Branch: `query-service-completion`; baseline: `844e51b6fc189a379003c71650e9254c71c67f88`.
- Branch HEAD at final record preparation and last tested code checkpoint:
  **`09e2afdfd5f37495c0367cdd1a2d8d566c4614fc`**, pushed. The final report
  commit is documentation-only; its exact SHA is in the handoff and Git history.
- Stages A/B/C have passed orchestrator acceptance for supported query behaviour
  and specific evidence-gap diagnostics. This does not certify source completeness.
- Final Stage C/shared integration audit: **no P1 blockers**. The separate B3
  office substitution finding is corrected at `09e2afd`; independent replay
  confirms planner/validator rejection and zero Finance queries for other offices.
- **Integration-ready for ChatGPT acceptance**, with explicit data dependencies
  below. Push the documentation-only handoff and confirm clean/matching remote;
  then stop. No master merge, force-push, ingestion or deployment.

## Acceptance matrix: all 32 numbered cases plus T01

**I** = implemented query behaviour; **P** = supported partial output plus a
specific unavailable component; **D** = tested, specifically unavailable diagnostic.
Evidence is independent: **S** = synthetic execution; **L** = existing source-backed
local evidence; **R** = reviewed mapping/capability/source boundary. L does not mean
execution against a complete live Fuseki corpus. Detailed citations are in
[`query-service-completion-evidence.md`](completion-evidence.md).

| Case | Stage | Behaviour | Evidence | Output / remaining limitation |
| --- | --- | --- | --- | --- |
| Q01 | A | I | S | Grounded Member lookup; qualified partial names retain ambiguity. |
| Q02 | A | I | S | Previous Dáil selected by dated House chronology; local service boolean. |
| Q03 | A | I | S | Union of service intervals with gaps; historical missing ends are not extended to today. |
| Q04 | A | I | S | Distinct membership-linked Dáil terms, independent of optional term metadata. |
| Q05 | A | I | S | Earliest Seanad entry; missing/conflicting starts prevent an earliest-date claim. |
| Q07 | A | I | S | As-of collection status checked against containing membership/term evidence. |
| Q08 | A | I | S | Independent status remains distinct from political-party identity. |
| Q10 | A | P | S, R | Mapped Seanad designation only; Taoiseach nomination method is unmapped and unavailable. |
| Q11 | A | I | S | Resolve current Committee owner first, then exact-IRI membership; missing roster/dates remain unavailable. |
| Q13 | A | I | S | Distinct membership-linked Committee IRIs, not repeated episodes or labels. |
| Q15 | A | I | S | Chronological Dáil term dates, distinguishing current open end from missing historical evidence. |
| Q32 | A | I | S | Same-name candidates with service/Houses context, no guessed identity. |
| Q33 | A | I | S | All exact-name Member identities with Dáil service. |
| Q34 | A | I | S | Grounded local not-found for the synthetic name; no invented record. |
| T01 | A | I | S | Exact `COUNT(DISTINCT term)` of typed Dáil terms in the selected Houses graph. |
| Q12 | B | D | S, R | Current Transport Committee resolution; no reviewed chair relation. |
| Q14 | B | D | S, L, R | Specific development Good Friday source-conflict/current-roster limitation. |
| Q18 | B | I | S | Grounded English title resolution with controlled AI expansion; candidates on ambiguity. |
| Q19 | B | I | S | Distinct Bills with any dated Published event in the requested year; legislativeYear is display-only. |
| Q20 | B | I | S | All controlled non-Enacted statuses; distinct Bill counts per status; unknown/conflicting status not guessed. |
| Q21 | B | I | S | Current process status and dated history, no predicted next step; missing process does not erase title identity. |
| Q22 | B | I | S | Every distinct sponsor Participation, including role-only; primary true/false/unknown preserved. |
| Q24A | B | I | S, L | Exact 2025/23 title/status/history/link; typed memo renditions or graph-local absence/incomplete-chain diagnostic. |
| Q25 | B | I | S, L | Exact Member-IRI office binding, any September overlap and supporting tenure dates. |
| Q26 | B | D | S, L, R | Incomplete accepted holdings cannot establish the current Finance holder. |
| Q27 | B | I | S, L | Finance holder on exactly 2021-07-01, not the entire month. |
| Q16 | C | I | S, L | Existing Houses golden/typed Fuseki transport yields **160 seats**, never a count of people. |
| Q17 | C | P | S, R | Exact-term ParliamentaryParty records; recognised ParliamentaryGroup data explicitly missing. |
| Q24 | C | D | S, L, R | Exact 2024/48 local absence plus reviewed `bill-stage/None` source issue, not nonexistence; present graph can be queried. |
| Q30 | C | D | S, L, R | PAC alias retained; no reviewed substantive-HSE evidence or coverage to establish latest hearing through asOf. |
| Q31 | C | I | S, L | Actual sitting/date/link path; pinned missing date is a local coverage diagnostic, not proof no debate occurred. |
| Q36 | C | D | S, R | Bill-linked voting unavailable; sponsorship is not voting. |
| Q37 | C | D | S, R | Transcript content unavailable; metadata/link is not speech. |

All three new test modules execute owner-scoped RDF and rendered `/ask` cases:
`tests/test_nlq_composable_stage_a.py`, `tests/test_nlq_stage_b.py`, and
`tests/test_nlq_stage_c.py`. Diagnostic cases assert no substitute answer query.
Caps and missing/conflicting identity/date evidence are tested separately.

## Verification and checkpoint history

| Checkpoint | Evidence |
| --- | --- |
| `870aefc` Stage A | Orchestrator **202 passed**, including preserved slices; count/debugger tail **8 passed, 63 deselected**. |
| `d530a58` B1 | Shared typed v2 envelope/authoritative validator; parent mutation/gate check **4 passed, 12 deselected**. |
| `c4c1e08` B2 | Parent **231 passed**; subsequent independent Q21/Q22 findings required correction before Stage B exit. |
| `ceed22b` Stage B | Parent **241 passed**; executor broader **377 passed, 1 skipped**. First parent attempt exceeded 120s; completed retry allowed 300s. |
| `5248f40` Stage C | Parent **306 passed** combined; executor C/Debate **79 passed**. |
| `5248f40` campaign full suite | **1,740 passed, 25 skipped, 23 subtests passed**, 319.16s. |
| `09e2afd` final office hardening | Parent **135 passed** (B/Q35/C/contract); executor broader **464 passed, 1 skipped**; independent office selection **11 passed**. |

The common orchestrator regression command is:

```text
.venv/bin/python -m pytest -q --disable-warnings tests/test_nlq_stage_c.py tests/test_nlq_stage_b.py tests/test_nlq_composable_stage_a.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_poc.py tests/test_nlq_human_readable.py
```

Stage B used the same command without `test_nlq_stage_c.py`; Stage A also omitted
`test_nlq_stage_b.py`. B1 focused check used `tests/test_nlq_stage_b.py -k
'shared or validator or schema or closed or gate or mutation'`.

Campaign-end commands at `5248f40`:

```text
.venv/bin/python -m pytest -q -ra --disable-warnings tests
.venv/bin/python tests/validate.py
.venv/bin/python -m tools.validation
git diff --check
```

All completed successfully: full-suite counts above; ontology **2,584 triples**,
HermiT consistency passed; active mapping integrity passed. The 25 skips require
explicit disposable Fuseki/GSP/SPARQL configuration, capture-backed acceptance,
or the separately invoked production-release gate. They are omissions, not
passes. No live/production query acceptance was substituted. Disposable log:
`/tmp/opencode/query-service-completion-full-pytest.log`.

The independent office review returned one final parser hardening after that
full run. At `09e2afd` the orchestrator reran
`.venv/bin/python -m pytest -q --disable-warnings tests/test_nlq_stage_b.py tests/test_nlq_composable_q35.py tests/test_nlq_stage_c.py tests/test_nlq_contract.py`
— **135 passed**, 152.45s. Executor combined Stage A/B/C, baseline, contract
and safety regressions: **464 passed, 1 skipped**. The full suite was not
repeated after this bounded fix; its exact pre-hardening SHA remains explicit.
Final ontology/mapping validation and compile/diff checks passed. No claim is
made that the full 1,740-test run used the later parser bytes.

Exact final executor combined command:
`.venv/bin/python -m pytest -q tests/test_nlq_stage_b.py tests/test_nlq_composable_stage_a.py tests/test_nlq_stage_c.py tests/test_nlq_composable_q06.py tests/test_nlq_composable_q09.py tests/test_nlq_composable_q23.py tests/test_nlq_composable_q35.py tests/test_nlq_composable_debates.py tests/test_nlq_contract.py tests/test_nlq_query_plan.py tests/test_nlq_plan_sparql.py tests/test_nlq_plan_sparql_fuseki.py tests/test_nlq_human_readable.py tests/test_nlq_poc.py tests/test_nlq_prefixes.py`.
Compile command:
`.venv/bin/python -m compileall -q poc/nlq/stage_b.py poc/nlq/composable_plan.py tests/test_nlq_stage_b.py`.

Q06/Q09/Q23/Q28/Q29/Q35 pass focused regressions and the full available suite.
Q28's user-facing dated Dáil lookup now shares the reviewed actual-sitting
compiler with Q31; existing readable date/link acceptance is preserved.

An executor ran a full suite early in Stage A (**1,617 passed, 25 skipped**),
before corrections. This scheduling deviation was not final acceptance evidence;
the orchestrator ran the full available suite once at campaign end as required.

## Independent review

- Stage A: all six initial P1s corrected; no blockers after review.
- Bills: Q21/Q22 fact joins originally erased title candidates. Optional fact
  joins now preserve identity; exact-tree `ceed22b` adversarial replays and
  **39 Stage B tests** independently passed, both P1s resolved.
- Final integration at `5248f40`: **no P1 blockers**; independent reruns
  **92 + 110 + 59 = 261 tests passed**, ontology validation passed. All 33
  cases, shared v2 validators, owner gates and absence of forbidden changes
  independently checked. Office-specific findings are recorded separately below.

- B3 audit cleared identity, date boundaries, conflicts and cap protections,
  but found the date-point parser discarded a captured office mention and
  substituted Finance. **Resolved at `09e2afd`**: restricted Finance parsing plus
  exact-role validator, canonical interval-first bound constraints and correctly
  Member-scoped empty-holding diagnostics. Independent exact adversarial replay
  and **11 office tests passed**; no remaining B3 blockers. This is additional
  focused evidence after, not part of, the full-suite run.

## Examples and carry-forward boundaries

- Q16: “The Houses graph records **160 seats for the 33rd Dáil**.”
- Q24A: “**Pregnancy Loss (Miscellaneous Provisions) Bill 2025**, 23/2025;
  mapped status Current; recorded Committee Stage 2025-07-09.” The preserved
  record has no relatedDocs: no memo recorded there does not prove none elsewhere.
- Q25/Q27: reviewed local tenure citations support Martin's Taoiseach interval
  from 2025-01-23 (no recorded end) and Donohoe's Finance interval
  2020-06-27–2022-12-17. Execution fixtures prove exact binding/date logic,
  not loading or currency of arbitrary live datasets.
- Q30: “PAC means Committee of Public Accounts; available metadata cannot
  establish substantive HSE examination or the latest hearing through asOf.”
- Q36/Q37: “Voting records / transcript content are unavailable”; no proxy answer.

Data/retrieval owners retain: nomination-method mapping, chair evidence, current
committee/office rosters, recognised-group instances, complete historical/date
coverage, quarantined Bill resolution, substantive hearing/topic evidence and
coverage, and future reviewed vote/transcript retrieval. None was silently
treated as delivered ingestion or retrieval infrastructure.

Deliberate query-contract extensions expose already reviewed RDF only: finite
Bill-document connectors (query 2.7.0, safety 1.1.0), then term ordinal/seat
patterns (query 2.8.0). Composable contract is 2.8.0. No ontology, mappings,
approved catalogue, source/golden fixtures, RDF ownership/IRIs, named-graph
identity, rejected query features, or safety limits changed. README additive
version guidance was reconciled with accepted finite-connector precedent.
