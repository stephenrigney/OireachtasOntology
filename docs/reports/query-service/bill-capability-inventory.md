# Query Service — Bill Capability Inventory and Focused Structural Review

**Baseline:** `master` (2026-11-03). Read-only investigation; no Query Service
or semantic-contract changes. Coverage is implemented query capability, not
corpus completeness. Bill graphs are optional.

## 1. Capability coverage

| Question family | Coverage | Evidence and cause |
|---|---|---|
| Exact Bill number/year lookup; title, status, official link, recorded memo rendition | Supported | `bill_lookup`; `stage_b.py`; finite Bill graph route and typed memo chain. Q24A evidence distinguishes empty relatedDocs from global absence (`completion-evidence.md`). |
| Title search / abbreviated-title resolution | Supported, bounded | `bill_title_search` (Q18); candidate identities retained, no guess among matches. Token matching and Bill normalization in `member_resolution.py`; not general alias inference. |
| Bills published in calendar year | Supported | `bills_published` (Q19) selects dated Published activity, not Bill legislative year. Existing contract/tests and phase-2 report. Missing dates are not inferred. |
| Non-enacted Bills by legislative year; current status | Supported | `non_enacted_bills`; controlled statuses. Completeness depends on loaded graph/data, not established by a result. |
| Named Bill status and dated process history | Supported, evidence-limited | `bill_status_history` (Q21), traversing BillDelivery → LegislativeProcess and dated activities. Next procedural step explicitly deferred in approved catalogue. |
| Sponsors of a named Bill, roles and primary flag | Supported | `bill_sponsors` (Q22); Bill-owned Participation and Member label via exact IRI. Unknown primary status/role-only evidence preserved. |
| Bills sponsored by a named Member | Partial / route-dependent | Approved Q23; reverse `bill_sponsor` exists in legacy structured compiler, but Stage B's family and integrated composable acceptance are named-Bill direction. Similar vocabulary is not integrated capability. |
| Exact known quarantined Bill diagnostic (2024/48) | Supported, special case | `bill_quarantine` and reviewed diagnostic. Does not generalize to missing graph = nonexistent. |
| Non-enacted Bills grouped by status / local totals (Q20) | Supported, bounded | Explicit `non_enacted_bills` contract requests grouped local counts and fail-closed missing/conflicting statuses. This is a family-specific implementation, not a general Bill aggregation operator; composable bounded-count acceptance remains Member-specific. |
| Bill source/type filters and sponsor + date/status combinations | Unsupported as integrated capability | Mapping emits controlled source/type and event facts, but no general selectable Bill filter/composition. Primarily service planner/compiler gap, conditional on emitted data. |
| Bill-linked votes (Q36) | Unsupported | Approved question and contract explicitly say no reviewed voting path; sponsorship is not voting. Relationship/data evidence is missing/deferred, not a compiler-only issue (`completion-evidence.md`). |
| Predict next procedural step | Deferred by decision | Q21 explicitly excludes inference; requires procedural authority and distinction between possible and scheduled activity. |
| Versions, amendments, long/Irish titles, Bill-debate event links | Partial/unsupported | Ontology/mapping describe these, but only finite approved facts are queryable. Debate mapping defers exact Bill-event resolution; mapping alone does not establish service capability. |

Ordinary Bill type/status/process/history semantics are present in the reviewed
ontology/mapping; they are not ontology gaps. Data gaps include optional/missing
graphs, quarantined records, absent source facts and incomplete historical
captures. Service gaps include reverse sponsor integration, type/source filters
and Bills-wide aggregation. Votes and some Bill/debate links need reviewed
relationships; they must not be invented in query code.

Approved temporal-selection and bounded-aggregation work (`temporal-aggregation-
holdout-20261103.md`) supplies reusable interval/date, exact identity projection,
pagination and fail-closed count techniques, accepted for Member/office paths.
It does not supply Bill temporal semantics. Bill activity dates must remain
distinct from legislative year and version/document date. It cannot solve data
coverage.

## 2. Reuse and responsibility boundaries

**Genuinely reusable:** reviewed contract/graph-route loading; validated-plan
and typed-relation patterns; read-only SPARQL validation/execution; exact-IRI
joins; pagination and truncation failure; identity deduplication; compatible
date evaluation; bounded count projection; result/error envelopes. The
bounded-composition report demonstrates actual shared typed-edge rendering and
date evaluation on Member paths.

**Not actual reuse:** Stage A/B fixed recognizers, Bill-specific gates, query
branches and `_project_bill_result` differ from Stage C's composable
planner/validator/compiler. `plan_sparql.py` has another requirement compiler
and Bill fact renderer. Shared safety/result types do not unify capability
coverage; adding a capability to one route does not make it available on the
other.

**Legitimately Bill-specific:** Bill graph identity/route, Bill Work type,
BillDelivery-to-process traversal, controlled lifecycle/status, sponsor
Participation/primary flag, memo rendition chain, title ambiguity and Bill
diagnostics. Their semantics differ from generic entity relationships.

The composable path has clearer boundaries between draft, closed-plan
validation, compilation, execution and presentation. The consequential coupling
is duplicate Bill capability logic across routes and metadata plus hard-coded
family gates. This is a maintenance cost, not evidence requiring redesign.
Resolution should produce candidates; the final plan must preserve exact
identity and every requested constraint. Presentation should not absorb RDF
semantics for the sake of fewer files.

## 3. Declarative validation opportunities

Good metadata candidates: allowed families/referent types, required facts and
relations, answer projections, operators/value types, controlled status/type
IDs, graph-family ownership, required pattern IDs and cardinality bounds. A
generic validator can enforce these closed declarations instead of duplicating
membership/shape conditionals.

Keep procedural/semantic checks in code: date parsing and normalization; exact
Bill URI and graph-route validation; SPARQL syntax/read-only/safety enforcement;
title grounding and ambiguity; conditional exact-IRI cross-graph joins;
checking emitted RDF paths; malformed/conflicting result handling; and refusing
truncated aggregates. Metadata cannot establish source presence or make a
relationship true. Any extraction must fail closed on unknown/malformed
metadata and preserve adversarial-plan tests.

## 4. Marginal implementation cost

Estimates assume approved meaning and composable route; not authorization.
Lines include tests.

| Representative gap | Estimated changes | Acceptance needs |
|---|---|---|
| **Straightforward:** list Government-source Bills for a given legislative year, filtering the reviewed controlled source identity | ~3–4 files; 100–170 LOC: contract/capability, planner validation, Bill compiler filter, tests. Reuse Bill graph route, controlled-resource filtering, identity projection and presentation. No new query family if existing bounded Bill-list shape can express it; otherwise additive family. | Confirm queryable/emitted predicate and exact IRI; never label-match. Test no results vs unavailable graph, deduplication, and fail-closed plan/query safety. |
| **Temporal + composition:** count distinct Bills sponsored by a named Member with a Published activity in a requested year | ~5–7 files; 220–360 LOC: plan constraints/projection, planner validation, Bill sponsor+activity compiler path, count/list executor/presentation and tests. Reuse exact identity joins, activity date windows, bounded count. Likely needs a Bill-specific composed shape, not a generic SPARQL engine. | Synthetic adversarial graph plus source-backed control if available; count/list identity parity; Published activity date (not legislative/version year); exact Member IRI; duplicate activities, missing/malformed dates, ambiguous identity, unavailable graph and cap/truncation fail closed. |

One-time infrastructure: express Bill referents with temporal constraints and
answer projections in the closed plan, then add a reviewed Bill lifecycle/sponsor
path. Later filters on that shape: roughly 2–3 files and 40–90 LOC plus tests.
New relationship semantics incur the larger cost again. Estimates are
engineering approximations.

## 5. Priorities and exit criteria

1. Resolve Q23's route discrepancy and integrate acceptance before claiming
   reverse sponsorship supported; clarify which route owns it.
2. Add one controlled Bill-list filter (source/type or another approved emitted
   fact) using confirmed data and explicit user value.
3. Add a narrow Bill event-date selector and bounded count/list parity; consider
   Q20 status grouping only if aggregate semantics and pagination safeguards
   support grouped counts.
4. Defer voting, inferred next steps and unreviewed Bill/debate links until
   relationship authority exists. Keep data-unavailable distinct from
   unsupported semantics.

**Next-tranche exit:** approved exact semantics and evidence authority; validated
plan retains all requested constraints; generated query is deterministic and
restricted to Bill-owned graph plus reviewed joins; tests cover positive,
missing/unavailable evidence, ambiguity, malformed dates, duplicates and cap
behavior as applicable; aggregate count agrees with untruncated identity list;
no semantic/ownership/IRI/safety-boundary changes without approval; focused tests
and ontology/mapping validation pass.

## 6. Recommendation

**Continue unchanged structurally; make targeted simplifications only when a
capability demonstrates duplicated validation or a concrete defect.** Shared
identity, temporal and bounded-operator components show viable reuse; the finite
Bill route remains useful. The dominant practical cost is capabilities diverging
between routes, not a demonstrated architectural failure. Clarify Q23 ownership
and prove the first Bill temporal/aggregate slice before a separate structural
task. No finding requires reopening ontology, graph ownership, IRI or publication
decisions. Holdout planner HTTP 400s are runtime failures, not Bill semantic
evidence.

## Evidence index

- `poc/specs/composable-query-plan-contract.json`; `poc/nlq/stage_b.py`,
  `plan_sparql.py`, `composable_semantic_planner.py`.
- `poc/specs/query-service-questions-approved.md` (Q18–Q24A, Q36),
  `poc/specs/query-plan-contract.json`.
- `tests/test_nlq_contract.py`, Bill-specific Query Service tests,
  `tests/test_nlq_plan_benchmark.py` (compiler/contract behavior; ETL tests are
  not query-service acceptance).
- `mappings/bill_mapping.csv`, `ontology/legislation.owl.ttl`,
  `docs/reference/etl/legislation.md`.
- Reports: `phase-2-capability-expansion.md`, `completion-evidence.md`,
  `bounded-composition-reuse.md`, `temporal-aggregation-holdout-20261103.md`,
  `q06-political-affiliation-evidence.md`.
