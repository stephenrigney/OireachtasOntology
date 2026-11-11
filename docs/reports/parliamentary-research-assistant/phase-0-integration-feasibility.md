# Parliamentary Research Assistant — Phase 0: Compiler Integration Feasibility

**Date:** 11 November 2026

**Repository / branch:** `stephenrigney/OireachtasOntology` / `parliamentary-research-assistant`

**Investigated HEAD:** `1cb836f73676a4b03437270fea61c9e899482070`

**Disposition:** Report only; no adapter, application, compiler, contract, ontology, ETL, dataset or configuration changes. Phase 1 requires separate human authorisation.

## 1. Executive feasibility judgement

**CONDITIONAL GO for a separately authorised Phase 1 vertical slice.** The existing composable-v2 compiler can execute the approved single-term, named-party Member lists and distinct-Member counts without substantial compiler refactoring. A small closed operation facade and evidence-preserving output boundary are a credible integration, not a demonstrated implementation. The current HTML service is not already that API.

Current-source, read-only executions against the existing local Fuseki dataset established:

- House-owned dates selected the **34th Dáil**, exact IRI `https://data.oireachtas.ie/ie/oireachtas/house/dail/34`, starting `2024-11-29`, with no recorded end.
- At the explicitly pinned reporting date **`2026-11-11`**, Fine Gael returned **38** distinct recorded Members and Fianna Fáil **48**. Each compiler count equalled its corresponding list's distinct Member-IRI cardinality.
- An independently written bounded RDF selection matched both identity sets and their display names. This establishes agreement over the inspected local evidence, **not complete source coverage or current real-world party totals**.
- Three deliberately lossy party drafts were refused before RDF queries: an additional committee condition, an additional calendar date, and a second party. Missing party evidence was unavailable, not zero. An injected transport failure remained an execution failure.

The conditions are material:

1. Preserve the existing full validation/resolution/temporal/execution path when exposing typed dispatch; a compiler-only call is not a safe interface.
2. Resolve the observed executable-validator/final-JSON-Schema disagreement before declaring a schema-conformant API. Do not remove evidence fields or relax validation silently.
3. Retain structured evidence, all executed queries and completeness qualifications; existing display rows/debug text alone are insufficient for the full product evidence contract.
4. Obtain an explicit product decision that a **qualified report of recorded local representation**, with uncertified coverage/freshness, satisfies the initial slice. If certified complete contemporary rosters are required, that requirement is blocked by missing coverage/freshness evidence, not by a missing count operation.
5. Run the focused regression suite in an existing suitable test environment before accepting implementation. It could not run in this checkout's `.venv` because `pytest` is absent.

Phase 0 demonstrates execution feasibility, not a finished tested adapter or unconditional satisfaction of the specification's Phase 0 exit. No general NLQ remediation programme or compiler replacement is needed for this bounded assessment.

## 2. Authority, method and verification baseline

### Authority and evidence labels

The approved [product specification](../../specifications/parliamentary-research-assistant.md), especially §§12–18, governs requirements. The [Stage 2 inventory](../query-service/nlq-stage-2-executable-capability-inventory.md) and [Stage 5 evaluation](../query-service/nlq-stage-5-evidence-based-architectural-evaluation.md) supplied investigation leads, not current runtime certification. Current source, tests, composable contract **2.30.0**, and query-schema contract **2.12.0** were inspected. ETL ownership/publication boundaries remain those of `docs/architecture/etl.md`.

- **Static:** source/contract/test assertions inspected; not proof a test passed.
- **Executed:** checks performed during this investigation.
- **Proposed:** interface or implementation work not performed.
- **Unknown:** not established by these checks.

Source paths below are repository-relative. Function names accompany line ranges so references remain useful after later edits.

### Environment and execution bounds

The working directory was `/var/home/stephen/Projects/OireachtasOntology-worktrees/query-service-ui`; its directory name differs from the branch name, but Git confirmed the requested repository and branch. The initial working tree was clean. No branch/worktree was created or switched.

The local `.venv` has Python **3.13.15**, RDFLib **7.6.0**, FastAPI **0.142.2**, HTTPX **0.28.1**, but neither `pytest` nor `jsonschema`. System Python has `jsonschema`; it was used only to validate saved plan JSON. Nothing was installed.

Existing services were available at `http://127.0.0.1:8000/` and `http://localhost:3030/houses/query`. The port-8000 process's working directory is this checkout; its inherited `OIR_NLQ_AS_OF_DATE` is unset and its model setting is `gpt-6-luna`. Its imported serving revision was **not independently attested**. Direct Python executions imported the clean investigated checkout and explicitly fixed `as_of=date(2026,11,11)`. Existing local credentials were used without disclosure. The unrelated port-8001 service was not used.

Fuseki readiness returned `ready`, including Houses, Parties, Constituencies and Members. This is a **presence-only** check (`poc/nlq/fuseki.py:208–260`), not capture identity, freshness, reference closure or completeness certification. No infrastructure was started, no dataset reloaded, and no update, publication or configuration operation was performed.

### Checks actually performed

| Check | Executed observation / limitation |
|---|---|
| Focused pytest command below | Exit 1, `No module named pytest`; **no tests collected or passed**. |
| Fixed-draft public `execute_question` executions | Nine cases: one term lookup, four positive party list/count operations, three unsupported-condition controls, one nonexistent-party control. No LLM calls; the fixed generator returned JSON text. Positive party operations each made four read-only queries; controls and outcomes are detailed in §4. |
| Offline replay of those nine cases | Current source reproduced exact query text/order, outcome statuses and projected rows using captured query responses. This is deterministic replay, not a second live dataset observation or a replacement for pytest. |
| Independent hand-written RDF selection | 87 candidate rows in one `LIMIT 100` response, with actual Member graph bindings, optional names/ranges/types/dates. Validated DateRange types, required starts, dateTime hints, interval ordering and nonconflicting per-path evidence. Selected identity sets and labels matched both lists. Finite local selection only, not a global source oracle. |
| Existing HTTP `/ask`, `mode=phase2` | Term request: HTTP 200, HTML `data-outcome="answer"`, one result row, 0 LLM calls. Fine Gael list: HTTP 200, HTML answer, 38 rows, 1 LLM call. One observation, not repeated reliability or a typed-API test. |
| Final JSON Schema against saved executed plans | Term plan passed. All four successful party plans failed solely at `referents.party.selectedIRIs`, an undeclared property. Python `validate_plan` accepted all five successful plans. |
| Dependency-light negative diagnostics | Count/list mismatch, caller-supplied affiliation IRI and full two-party brief paired with a one-party draft rejected. Future date clarified without query. Injected query transport failure returned `execution_failure`. |
| Pagination result metadata diagnostic | A one-row page reproduced misplaced debug metadata: pagination's fourth positional `QueryResult` argument populates `boolean`, leaving `raw_json=None`. Live party outputs likewise had `raw_json=None`. |
| Offline pagination guard diagnostics | Synthetic query-client responses: 100+1 rows returned across two pages; changed columns refused on page two; 101 full pages exhausted the existing offset bound and returned no partial result. No network or limit changes. This tests the shared helper, not the full party executor's multi-page acceptance. |

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -p no:cacheprovider \
  tests/test_nlq_seanad_party_periods.py \
  tests/test_nlq_composable_party_temporal.py \
  tests/test_nlq_composable_stage_a.py tests/test_nlq_stage_c.py
```

Two initial diagnostic-harness mistakes were rejected before party RDF execution: returning a dictionary instead of JSON text, then using numeric-only relation IDs. The corrected fixed drafts satisfied the existing validation; these setup errors are not compiler capability failures.

Disposable diagnostic material is under `/tmp/oireachtasontology/phase-0-integration/`, not part of the deliverable or a durable evidence store. The final fixed-draft bundle `live-verification.json` has SHA-256 `c3222586cabd9995d24ee4276dfdc8adb56d751a89e10914c2186c820e559c30`; `independent-selection.json` has `b248c2305bfbf908a3146b381e3e7a8c363a670eda7058be0dbd5f695506ecdd`. These pins distinguish this finite observation, but do not freeze the dataset. Captured API input/run identity and dataset immutability were **not established**. The report retains the durable findings; disposable files must not become a dependency for Phase 1 acceptance.

An independent read-only report review checked the load-bearing source references and saved evidence, reproduced the final-schema failures and verified both artifact hashes. It found no material errors and supported the conditional judgement. This review was not a second live execution or a substitute for the unavailable regression suite.

## 3. Integration options and recommendation

| Option | Reusable entrypoint | Assessment |
|---|---|---|
| Existing natural-language `/ask` | `poc/nlq/app.py:289–360`: form `question`, `mode=phase2`; date from environment or server today | Useful smoke/experimentation route. Returns HTML, not a typed result envelope; introduces another natural-language planner after the research planner, variable routing and model availability. HTTP 200 does not imply a factual answer. Do not screen-scrape it for production evidence. Explicitly exclude optional `mode=phase1` direct LLM SPARQL. |
| Direct compiler invocation | `validate_composable_plan_draft` → `complete_v2_plan` → `validate_plan` → private `_execute_member_relationship_composition_plan` | Reuses real capabilities, but the private call alone omits public preflight and query-error normalisation. Calling `compile_member_relationship_composition_query` and executing its SPARQL also omits the temporal evaluator and safe count projection. Neither is an acceptable bypass. |
| Public pipeline with fixed draft generator | `execute_question(..., semantic_plan_generator_factory=...)` | **Executed feasibility seam.** Eliminates an LLM planning call and retains public guards. Existing tests use it. However, the question router may select another deterministic family before invoking that generator (`composable_plan.py:7267–7310`); this is not an authoritative typed-dispatch API. |
| Thin structured operation facade | **Proposed**, closed operations lowered to existing drafts/Stage A requests | Recommended product seam. Expose the existing guarded validation/completion/dispatch path behind explicit operation selection, with evidence capture. Keep compiler semantics unchanged; do not create a second compiler, generic graph API or agent framework. |

**Recommended smallest dependable implementation:** an in-process facade first, adding JSON transport only if the workspace/service deployment needs it. Make a small extraction/public boundary around the existing post-generation semantic path and shared preflight/error handling, rather than reproducing those rules in the adapter. Reject operation/request mismatches **before execution**. Retain the public fixed-draft route for differential regression checks, not as proof explicit dispatch has already been implemented. Avoid dependence on private functions as an undocumented permanent API.

The relevant existing sequence is:

```text
atomic factual request + fixed current-Dáil party draft
  → existing whole-intent/date/interpretation preflight
  → validate_composable_plan_draft(draft, question=factual_request)
  → complete_v2_plan(validated_draft, as_of=reporting_date)
  → validate_plan
  → existing member-relationship executor
  → House-date term resolution → term-scoped reviewed party resolution/gate
  → contract-driven compilation → SPARQL safety → bounded pagination
  → existing independent interval validation → Member-identity list/count
```

`execute_question` supplies the read-only query exception boundary (`composable_plan.py:7087–7122`). Semantic parsing/validation and dispatch are currently in `_execute_shared_dail_terms_question`, despite its historical name (`6456–6643`). `complete_v2_plan` merely completes the envelope; it does not substitute for admission or execution.

### Atomic requests versus the original research brief

The compiler validator still depends on **English intent and mention grounding**, not just a typed graph. The full approved Fine Gael/Fianna Fáil brief is not one supported party-only query; the diagnostic pairing that brief with a Fine-Gael-only draft was correctly rejected.

The coordinator must preserve the original brief and account for its requirements in a visible plan, producing separately identified atomic factual requests for each party/list/count. Pass each atomic request **unchanged** to compiler admission and retain its link to the original requirement. This does not establish compiler validation of the whole research brief. The coordinator's decomposition/complete-requirement accounting remains a Phase 1 acceptance obligation.

Do not rewrite a rejected factual request into easier canonical English, discard an extra condition, or present one atomic success as satisfaction of an entire brief. An operation/request mismatch, additional date/relationship or material ambiguity remains blocked/unsupported. This preserves rather than replaces the existing original-question safeguards.

## 4. Verified MVP operation inventory

### 4.1 Identify the current Dáil term

**Implemented:** `stage_a.execute_stage_a(StageARequest("house_terms", temporal_scope={"kind":"onDate","date": reporting_date}), as_of=..., fuseki=..., supported_predicates=...)`. The public verified invocation was `execute_question("Which Dáil was in office on 11 November 2026?", as_of=..., ...)`; `parse_stage_a_question` constructs that temporal request. Sources: `stage_a.py:24–59,397–418,631–754`.

The operation reads every typed Dáil term with optional House-owned label, ordinal, period/type/start/end evidence. Missing/conflicting metadata, reversed chronology, a 100-row boundary, or an unclassified open-ended historical term fails closed. It selects exact identities by inclusive day overlap; the adapter must require **one** selected term for the current-term operation. A term-date match does not establish an actual parliamentary sitting. Future scope requires clarification.

**Executed:** one matching term, 34th Dáil, exact identity and start recorded in §1; 34 raw catalogue rows, no model. Result columns are `Dáil term`, `House start`, `House end`, `Term identity`; resolved `referents.term.matches` retains IRI, label, start and nullable end. Capture the raw catalogue query result as well as the rendered row.

**Coverage inspected, not run:** `tests/test_nlq_composable_stage_a.py:496–579` covers date/month selection, transitions, missing dates, unsafe open ends, future clarification and refusal to substitute term dates for sittings; `698–767` covers plan validation/mapping checks.

### 4.2 Current Dáil Members of one named party

**Implemented:** `execute_question(question, as_of, fuseki, supported_predicates, semantic_plan_generator_factory)` with the existing current-party draft. Internally `_execute_member_relationship_composition_plan` dispatches to `_execute_member_party_temporal_composition` and `_temporal_member_party_result` (`composable_plan.py:5832–5856,5924–5974,5693–5810,5180–5444`). The private executor is not independently an approved public seam.

**Required draft:** six referents—`member:Member`, `membership:DailMembership`, `term:DailTerm` with `currentTerm`, `episode:PartyMembershipEpisode`, `party:ParliamentaryParty`, `affiliation:PoliticalAffiliationIdentity` with the party mention. No user-supplied resolved IRI, graph, Member name or hard-coded Dáil number. Seven exact edges:

```text
member_has_membership                         member → membership
membership_in_term                            membership → term
member_party_membership                       member → episode
party_episode_in_membership                   episode → membership
episode_in_parliamentary_party                episode → party
party_active_during_term                      party → term
parliamentary_party_has_affiliation_identity  party → affiliation
```

The constraint is `episode.partyEpisodeInterval overlaps membership`. For a list, use `entities/member/distinctBy=identity`, `display=[name]`, details for affiliation label and separate episode/membership start/end, and `preserveEvidence=true`. See the exact fixture constructors in `tests/test_nlq_seanad_party_periods.py:77–92,177–191` and admission in `composable_semantic_planner.py:561–837`.

**Identity validation:** the party mention must be grounded in the factual request. Resolution uses parties active in the exact selected term, one reviewed enduring `PoliticalAffiliationIdentity`, and the Stage C typed party-listing gate; the executor intersects exact party IRIs, never joins by similar labels. Missing links or conflicting labels fail; ambiguity retains candidates. Whole reviewed names can omit terminal “Party”; no arbitrary substring matching or guessed IRI. Sources: `composable_plan.py:3452–3482,4999–5100,5702–5754`; `stage_c.py:_parties_query:350–363`.

**Time:** House dates, not latest ordinal, select the current term. Both the exact parliamentary-membership interval and its linked typed PartyMembership episode must independently contain the reporting date, inclusively at calendar-day precision. Historical overlap or membership sometime in the current term is insufficient. DateRange/start uncertainty, malformed/conflicting dateTime evidence and reversed intervals fail closed. Absent end remains open-ended, not a date invented by the adapter (`composable_plan.py:5103–5154,5283–5357`). Approved unqualified present-tense defaults also exist, with locally revalidated interpretation metadata; this slice should display the explicit reporting date regardless.

**Executed:**

| Factual request | Raw membership/party evidence rows | Final distinct Members | Outcome |
|---|---:|---:|---|
| `Who are the Fine Gael Deputies in the current Dáil?` | 39 | 38 | `success` / `answer` |
| `Who are the Fianna Fáil Deputies in the current Dáil?` | 48 | 48 | `success` / `answer` |

Each fixed-draft operation performed four reads: current-term dating, affiliation resolution, Stage C party gate and temporal Member evidence. All were below the first-page boundary. The separate selection read 87 candidate paths/Member graphs; one Fine Gael path had membership and party end `2025-11-21` and correctly did not qualify at the reporting date. This is observed local RDF, not independent confirmation of a real-world departure.

**Shape/evidence:** list columns are `TD`, `Member identity`, `Established affiliation/representation overlap evidence`. Every returned Member has an exact local IRI and validated readable name. Evidence prose includes party/affiliation, membership, term and episode IRIs, separate intervals and their established overlap. First observed Members were Alan Dillon and Aindrias Moynihan respectively; no identity was inferred from the name. All 86 returned names matched the independent selection; all single-term evidence strings included the selected term.

**Completeness/failures:** affiliation resolution, party gate and Member evidence use ordered bounded pagination (`pagination.py:8–32`, page size 100, max offset 10000). Exhaustion/uncertain evidence yields no usable party count/list; a successful result is nevertheless **not a certified complete current roster**. No qualifying paths is `source_data_unavailable`, not an empty comprehensive roster or zero. Successful list rows are deduplicated by Member IRI after preserving separate qualifying episodes.

**Coverage inspected, not run:** `tests/test_nlq_seanad_party_periods.py:194–254` independently checks current Dáil list/count, duplicate episodes, ended membership/party intervals, Fianna Fáil and extra-condition refusal. `tests/test_nlq_present_time_defaults.py:41–81` checks inferred/explicit parity and tampering; `test_nlq_composable_party_temporal.py:845–1057` covers current dating, independent intervals, inclusive/open endpoints, invalid/conflicting dates and identity resolution. Historical/Seanad tests provide shared-path evidence, not direct certification of every current-Dáil edge case.

### 4.3 Distinct recorded-Member count

The **same** draft/path/temporal evaluator is used; only the answer changes to:

```json
{"kind":"count","referent":"member","distinctBy":"identity"}
```

The admission validator checks count versus list intent and rejects seat/election substitutions (`composable_semantic_planner.py:244–255,645–652`). `_temporal_member_party_result` counts its accepted Member-IRI map, not raw endpoint rows or party episodes (`composable_plan.py:5399–5442`). It returns `QueryResult(kind="select", columns=("Distinct recorded Members",), rows=(("38",),))` for Fine Gael and `(("48",),)` for Fianna Fáil in the observed dataset. Numeric cells are strings; typed normalisation should make an integer without changing its unit.

**Executed:** both counts matched their corresponding complete local selections. No current-party zero was demonstrated or authorised. Pagination beyond 100 and uncertain evidence were **not live exercised**; relevant inspected tests are `test_nlq_composable_party_temporal.py:697–754`, plus the current-Dáil test above. Counts cannot be displayed as seats, election totals or complete real-world party strength.

### 4.4 Member identities and display labels

These are already part of the party-list operation; a separate per-name lookup is unnecessary and would risk ambiguous re-resolution. Use returned Member IRIs as keys; preserve names as display data. Do not merge equal names, reconstruct IRIs, infer official profile URLs or replace an identity with an external identifier. Missing/conflicting qualifying names fail the existing projector rather than silently dropping that person (`composable_plan.py:5351–5387`). Stage A `member_lookup` is a distinct name-resolution operation, not a prerequisite for enumerating this roster.

### 4.5 Compare two parties

There is **no dedicated compiler comparison operation** verified here. The approved coordinator may perform a deterministic calculation from compatible accepted evidence, retaining both evidence references. In the observed bounded local sets, `48 − 38 = 10` describes a difference of ten **returned recorded Member identities**, not a certified real-world advantage. No application comparison implementation/test was run.

Compatibility requires the same exact Dáil IRI, reporting date, current-point semantics, unit/distinctness rule and dataset evidence context; complete bounded enumeration; accepted validation; and comparable disclosed coverage limitations. Unknown source coverage must not be promoted to complete population coverage. If source coverage differs materially or snapshot consistency cannot be established, block the substantive comparison or explicitly limit it to the separately observed query results; never silently reuse incompatible evidence. Do not claim mutual exclusivity, add a seat share or infer other parties from absence.

## 5. Proposed minimum typed adapter contract

**Illustrative design only**, not production code or a changed query-plan contract. A closed discriminated union is sufficient:

```typescript
type ResearchOperation =
  | { operation: "dail.current_term" }
  | { operation: "dail.party_members.current"; partyMention: string }
  | { operation: "dail.party_member_count.current"; partyMention: string };

type OperationRequest = {
  apiVersion: 1;
  requestId: string;
  requirementId: string;        // link into retained original brief/visible plan
  factualRequest: string;       // unchanged atomic request used for admission
  reportingDate: string;        // canonical ISO date, fixed for the research run
  operation: ResearchOperation;
};

type ComparisonRequest = {      // coordinator calculation, not a query compiler op
  operation: "compare.recorded_member_counts";
  leftEvidenceId: string;
  rightEvidenceId: string;
  calculation: "difference";
};
```

The service controls endpoint/credentials, predicate allowlist and resource bounds. Reject unknown keys/operations, invalid dates, empty/overlong mentions and contradictory operation/factual-request projections. Support **one party per query**, explicit current semantics only in this catalogue, and no arbitrary SPARQL, graph, resolved IRI, constituency, historical selector, office or committee filters. Existing full draft/plan/identity/temporal/safety validation remains authoritative. The adapter must not duplicate English interpretation or construct substitute evidence.

### Result envelope

Use a tagged outcome, not success-shaped empty data for every failure:

```typescript
type OperationEnvelope<T> = {
  apiVersion: 1;
  evidenceId: string;
  request: OperationRequest;
  outcome: "answer" | "clarification_required" | "unresolved_identity"
    | "unsupported_capability" | "missing_or_unaccepted_evidence"
    | "validation_failure" | "execution_failure";
  compilerStatus: string;       // preserve exact PlanOutcome.status
  validation: { admitted: boolean; planValidated: boolean };
  execution: {
    attempted: boolean; startedAt: string; finishedAt: string;
    compilerRevision: string; contractVersions: Record<string, string>;
    datasetContext: { endpointId: string; snapshotId: string | null };
    queries: QueryEvidenceRef[]; // every actual query/page, including resolution
  };
  resolvedScope: {
    term: { iri: string; label: string; start: string; end: string | null } | null;
    party: { affiliationIri: string; label: string; partyIris: string[] } | null;
    reportingDate: string;
    temporalMeaning: "both_membership_and_party_active_on_day" | "term_on_day";
  };
  completeness: {
    enumeration: "complete_within_query_scope" | "incomplete" | "unknown";
    sourceCoverage: "uncertified" | "unknown";
    freshness: "unknown";       // only change when actual supporting evidence exists
    limitations: string[];
  };
  data: T | null;               // only admitted, accepted output; errors below
  error: { code: string; stage: string; message: string; retryable: boolean } | null;
};
```

`QueryEvidenceRef` denotes a retained query ID/hash, query text, outcome, untruncated returned columns/rows or a durable reference, offset/page completion, and source graph scope actually queried. Preserve raw RDF binding hints where available. It is **not** an invented ETL capture reference. Record actual endpoint failures and stage separately; SPARQL presence is not proof execution happened.

Minimum payloads:

- Term: exact IRI, source label, recorded start and nullable end.
- Members: `{memberIri, displayName, witnesses[]}`. Witnesses carry existing accepted membership/episode/party/affiliation/term IRIs, separate date-range IRIs/endpoints and established overlap. Exact owner-graph bindings are nullable until actually retained; never derive them from a convenient label/IRI convention and call that observed provenance.
- Count: `{value: integer, unit: "distinct_recorded_member_iris", selectionEvidenceId}` with the accepted selection or its structured witnesses retained. A count-only one-cell result is not sufficient evidence for the report's Member table.
- Comparison: both input evidence IDs, compatibility decision and deterministic calculation, with inherited coverage qualifications. A rejected comparison does not invalidate earlier independent findings.

Example atomic request for the approved brief:

```json
{
  "apiVersion": 1,
  "requestId": "fg-members-1",
  "requirementId": "brief-1.fine-gael-members",
  "factualRequest": "Who are the Fine Gael Deputies in the current Dáil?",
  "reportingDate": "2026-11-11",
  "operation": {"operation":"dail.party_members.current","partyMention":"Fine Gael"}
}
```

A corresponding observed-result summary would say `answer`, resolved 34th-Dáil IRI, 38 returned Member identities, complete enumeration **of the accepted queried selection**, `sourceCoverage=uncertified`, `freshness=unknown`. The full evidence store, not this summary, supports individual claims. This example does not supply a fabricated snapshot ID or claim complete Irish parliamentary coverage.

### Errors and validation boundaries

Retain `PlanOutcome.interaction` categories and the exact underlying status (`composable_plan.py:65–93`). Proposed adapter error codes refine, not replace, these outcomes:

| Classification | Examples / handling |
|---|---|
| `invalid_parameter` / `operation_mismatch` | Bad date/shape or list/count mismatch; no execution. |
| `unsupported_operation_or_scope` | Extra committee/date/party condition; no weaker substitute. |
| `identity_ambiguous` | Preserve candidates; user clarification, never automatic selection. |
| `identity_unresolved` / `evidence_unavailable` | Preserve `not_found`, `missing_identity_link` or `source_data_unavailable`; nonexistent-party probe returned the latter, **not** a definitive false claim. |
| `validation_or_mapping_failure` | Invalid draft, unreviewed mapping, schema disagreement; no execution of rejected plan. |
| `incomplete_or_uncertain_evidence` | Pagination exhaustion, missing/conflicting intervals; no current-party count or partial-looking complete roster. |
| `service_unavailable` / `execution_failure` / `resource_limit` | Record actual failing stage/query; bounded equivalent retry only. Current pipeline can normalise several causes to one status, so precise subcodes need actual instrumentation, not message guessing. |
| `incompatible_evidence` | Coordinator comparison blocked; preserve previous valid results. |

Report sections can progressively consume completed envelopes; pending, unsupported or blocked operations remain explicit. Link each table/claim to evidence IDs and distinguish direct findings, deterministic calculations and LLM narrative. Compiler admission of an operation does not validate arbitrary prose about it.

## 6. Evidence and completeness assessment

| Requirement | Existing support | What must be preserved/exposed |
|---|---|---|
| Stable Member identities | Exact returned RDF Member IRI; names separately validated | Key report rows by IRI, keep labels separate, do not re-resolve by name. |
| Temporal scope/reporting date | `asOf`, current selector, resolved term/`asOfEvidence`; interval evidence in rendered strings | Fixed run date, exact term, both relationship intervals, nullable open ends, separate retrieval timestamp. `asOf` is not a dataset refresh timestamp. |
| Completeness | Fail-closed bounded paging and diagnostic warning; no complete-roster guarantee | Separate query enumeration from source coverage and freshness. Promote no count on failure. Preserve limitations in visible report and export. |
| Source provenance | Reviewed graph-scoped queries and RDF resource/episode references | Retain all queries and outputs. Main party query scopes `?memberGraph` by prefix but does not project that variable; display rows omit date-range IRIs. Exact per-row owner graphs and accepted structured witnesses need a narrow output addition if required. Do not invent raw API/run provenance. |
| Failure and unsupported outcomes | First-class `PlanOutcome.status`, interaction categories, candidates/diagnostics | Carry status plus stage, not just HTTP code or nonempty rows. Prior findings survive later failures. |
| Claim traceability | Final plan, one `sparql` field, result rows and evidence prose | Add request/requirement/evidence IDs, actual query/page trace, revision/date/context, retained accepted witnesses and calculation dependencies. Preserve plan objects, not reparsed capped HTML/debug JSON. |

**Important evidence limitations observed:**

1. `PlanOutcome.sparql` retains only one query. A party operation actually performed four, before considering additional pages. Existing `QueryResult.raw_json` is capped debug output, not a complete audit store (`results.py:11–24,51–75`). A query-client decorator can retain actual untruncated `columns/rows` and timing without changing query semantics.
2. `pagination.select_pages` passes debug JSON as the fourth positional `QueryResult` argument (`pagination.py:28–31`); that field is `boolean`, not `raw_json` (`results.py:27–33`). Stage A term output has a similar positional call (`stage_a.py:747`). Party output observed `raw_json=None`; successful paginated SELECT results can instead carry a truthy debug string in `boolean`, so consumers must not mistake it for an ASK answer. Do not parse or trust this field as the sole trace. This is an existing metadata defect, disclosed here, not repaired or required to be broadly cleaned up in Phase 0.
3. The temporal projector has structured validated identities/intervals internally but renders much of them into prose. Do not reverse-parse prose into an authoritative evidence model or reimplement temporal acceptance over raw candidate rows. Expose the existing accepted witness data at its projection boundary. Query tracing alone retains candidates, not a ready-made accepted witness graph.
4. No inspected result supplied an immutable loaded-capture/run identifier or certified refresh/completeness statement. RDF resource IRIs and local graph scope provide useful source references, but do not by themselves establish API source freshness or exhaustive current coverage. Multi-operation reads are not a dataset transaction; same endpoint/date does not prove the same snapshot.

Consequently, existing results support progressively presented **qualified local findings**, but not the entire factual evidence contract automatically. A thin adapter can bridge most metadata gaps; data coverage/freshness cannot be manufactured by an adapter.

## 7. Minimum changes, blockers, risks and unresolved decisions

### Reuse versus change

| Category | Minimum assessment |
|---|---|
| Already reusable | Current-day term selection; reviewed term-scoped party/affiliation resolution; typed exact membership/episode joins; independent current intervals; bounded paging; safety gate; distinct Member projection; names/IRIs; controlled error outcomes. |
| Small adapter/API work | Closed request types and constructor, explicit dispatch using shared guards, typed result/error envelope, fixed reporting date, all-query trace decorator, requirement/evidence IDs, evidence retention and coordinator compatibility checks. No general expression language. |
| Small backend evidence exposure | Preserve accepted projector witnesses/count support before formatting; expose pagination completion and actual execution-stage metadata. Actual Member graph bindings may need an additional projected metadata column, not a new join/meaning. Requires focused regression, not a new temporal evaluator. |
| Existing contract discrepancy | Successful runtime party plans contain `selectedIRIs`, accepted by Python validation but absent from final JSON Schema. Requires explicit reviewed disposition before claiming final-schema conformity; preserve the selected identities. No query contract was changed here. |
| Data/evidence prerequisites | Accepted local dataset; coherent House dates; reviewed party links; dated episodes; fixed report date; honest coverage/freshness/snapshot qualifications. Complete contemporary real-world totals remain unproven. |
| Not required | New ontology/ETL work, seat inference, historical/general joins, broad model capability discovery, arbitrary SPARQL, agent framework, compiler replacement or wider Stage 5 composition programme. |

### Escalations and genuinely blocking conditions

**A. Schema disagreement — blocks a declared schema-conformant operation API.** The four executed party plans failed `poc/specs/composable-query-plan.schema.json:24–47` at `selectedIRIs`; executable validation explicitly accepts the field (`composable_plan.py:599–612,5748`). This is not resolved by choosing one authority silently, dropping selected identities or weakening schema validation. Seek human approval for a narrow contract alignment/disposition outside this report's mutation boundary. The earlier Stage 2 Dáil-current-count contract discrepancy is, by contrast, resolved in current contract 2.30.0's `memberCountProjections` and present-time policy; it is not a current blocker.

**B. Current-term source-selection caveat — prevents universal fail-closed certification.** The Dáil party branch uses `previous_dail_term_query(..., include_undated=False)` followed by `resolve_current_dail` (`composable_plan.py:2346–2381,5955–5965`; `representation.py:166–189`). Despite the helper name it selects the current term, but required period/start triples can omit an undated typed term before Python sees it. Do not claim this path detects every malformed catalogue. The separately executed Stage A temporal catalogue query preserves such gaps and passed on this dataset's 34 rows. Require that operation to succeed and its selected term to agree before dependent party tasks in the vertical slice; disclose this additional evidence prerequisite. Any decision to change the resolver itself requires separately authorised focused work, not a hidden adapter workaround or silently altered temporal meaning.

**C. Evidence metadata — blocks the full inspectable evidence contract if left display-only.** Retaining final names/counts/HTML is insufficient. Trace capture and accepted witness exposure are bounded changes; silently treating capped/misplaced debug JSON as complete provenance is not acceptable. If those additions cannot be kept small while preserving the shared evaluator, stop and reassess rather than implementing an independent compiler.

**D. Coverage/freshness — blocks unqualified complete contemporary totals.** There is no evidence here certifying a complete current roster or the dataset's refresh date. Human approval is needed to proceed with explicitly qualified recorded-local findings. If that is not adequate, obtain authorised data/provenance prerequisites separately; do not infer them from readiness or “current” query execution. Comparisons must retain the same qualification and cannot erase this gap.

**E. Regression availability — blocks acceptance, not feasibility.** Focused pytest execution was unavailable. Live first-page checks do not replace pagination, ambiguity, malformed-date and failure regression. No infrastructure installation or dataset change was attempted to fill this gap.

**D8 shared-projector issue:** the Stage 5 stale-term evidence defect remains in `composable_plan.py:5249,5365`. It concerns multi-term anchored rows. This slice binds one exact term and checks each row against it, so the stale variable cannot identify a different accepted term here; all live simple-party evidence terms agreed. Count identity selection does not depend on that display string. Do not generalise this narrow observation into projector certification or expand into anchored operations; no D8 fix is proposed as an MVP prerequisite.

**Unresolved implementation assumptions:** a small guard-preserving extraction and structured witness output will suffice; coordinator decomposition can faithfully account for realistic brief wording; snapshot/coverage compatibility can be made explicit; live service behaviour is sufficiently repeatable. None has been proven by an implemented adapter. A human Phase 1 decision should bound these tasks and stop on semantic change or broader refactoring.

## 8. Proposed Phase 1 vertical slice and measurable exit criteria

**Proposal only:** use the approved Fine Gael/Fianna Fáil brief, one visible plan, two-pane research workspace and progressive evidence-linked report. Publish the plan before any factual query. Freeze the reporting date once. Establish the term, retrieve each party's accepted Members and compiler count, check parity/compatibility, then populate the comparison. Do not generate temporary factual prose without evidence. Keep failed/unsupported requirements and coverage limitations visible; preserve valid earlier sections and Markdown-export qualifications.

**Preconditions for authorisation:** human disposition of A–D above, an existing usable regression environment, and approval specifically limited to the closed facade/evidence exposure/workspace slice. Contract or compiler fixes are not implicitly authorised by this report.

Proposed measurable exits:

1. **Closed dispatch:** all three query-operation IDs have typed positive/negative contract tests. Invalid parameters, unknown fields, projection mismatches and extra unsupported conditions cause zero answer queries. No second LLM query-planning call or Phase 1 SPARQL downgrade occurs on the authoritative operation path.
2. **Differential parity:** on a pinned test dataset/date, both parties' new-facade results match existing validated fixed-draft results by Member IRI, names, accepted episode/interval witnesses and compiler count. Counts equal distinct list identities, never raw row counts. Include duplicate qualifying episodes and independently ended parliamentary/party membership.
3. **Negative evidence integrity:** tests cover missing/conflicting/reversed/wrong-datatype intervals, missing/ambiguous party identities, missing House metadata, term mismatch, no matches, an additional date/committee/party, and future date. No failed/uncertain case becomes zero or a complete roster. Verify page 2 and exhausted pagination without changing live data.
4. **Schema and trace:** every accepted operation envelope validates against its approved schema; the final-plan/schema discrepancy has an explicit approved resolution. Every factual claim has request/requirement/evidence IDs, fixed scope, revision, all executed query/page references and retained accepted witness support. A trace-loss or provenance mismatch blocks dependent claims. Unknown capture/freshness stays explicit.
5. **Comparison:** allow the deterministic difference only for compatible evidence; test mismatched term/date/unit/context, partial enumeration and differing coverage qualifications. Reject incompatible inputs without deleting valid individual-party findings. Local-only comparison wording/limitations reflect the human decision, not an LLM's assumption.
6. **End-to-end report:** one real configured-dataset run produces inspectable term, two Member tables, two recorded counts and a qualified comparison, or visibly blocks unsupported requirements. Do not hard-code today's 38/48 in production acceptance against a mutable dataset; use independently selected snapshot-specific expectations. Report time to first validated finding and completed/qualified report without claiming a latency target measured here.
7. **Workspace behaviour:** verify plan publication precedes dispatch; validated sections appear progressively; unrelated failures retain previous results; clarification/unsupported states are visible; export retains evidence references and incomplete status. Exercise desktop, tablet, 390px and 320px, keyboard/focus/table overflow per approved specification §18. Phase 2 refinements need not be fully implemented to demonstrate the initial slice.
8. **Scope/verification review:** run focused existing/new regressions and the smallest credible broader affected checks. Verify no semantic, ETL, source-fixture, data or configuration mutation and no general NLQ expansion. Stop for human review if preserving safeguards requires a new interpretation or material compiler architecture change.

### Final recommendation

**CONDITIONAL GO:** authorise a narrowly scoped Phase 1 only after explicit schema/evidence and qualified-coverage decisions, with the above gates. The useful query operations are implemented and representative current-source executions succeeded; the missing work is principally a small dependable invocation/evidence boundary and the approved workspace, not substantial compiler refactoring. **Do not authorise an unqualified complete-current-roster claim, silently bypass guards, or start Phase 1 from this report alone.**
