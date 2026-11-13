# OireachtasOntology NLQ — Bounded Composition Experiment Readiness

> Persistence note: checkout and uncommitted-status statements below describe
> the original preparation task. The user subsequently authorised committing
> and pushing this report; `master` was fast-forwarded to the fetched origin
> before persistence. No implementation or semantic change was authorised.

## 1. Verdict and boundary

**Conditionally ready.** Positive RDF witnesses now exist for both disclosed
combinations. **Inferred recommendation:** a single minimal reusable-composition
prototype is the useful next experiment *after separate approval*, not two
artificial B/C implementations. At this bounded scope, reusable B converges on
a constrained IR inside v2. No implementation is authorised or started here.

**Current disposition: no implementation yet (Task 5 option 3); conditional
experiment: option 1.** Human approval of the proposed semantics, evidence scope,
budgets and independently frozen probe/oracles is outstanding. Positive evidence
readiness is not complete-source certification or production NLQ readiness.

**Observed — checkout:** clean `master` initially at
`52d0378b4f1c02ec3553112fc2ee93c2f3ec06d2` in the requested repository.
Fetching `origin/master` succeeded but found it four commits ahead at
`f050f1a`. The incoming changes add the query explainer, presentation contracts
and tests; the examined composition kernels/contracts are unchanged. No pull,
branch/worktree change, service startup, reload, data write, model/provider call,
prototype or new test was performed. The synchronisation condition for committing
and pushing is **not met**; this report is left uncommitted.

**Evidence labels:** **Observed** means inspected source or captured bindings;
**Inferred** means synthesis; **Proposed** means unapproved design/semantics;
**Hypothesis** requires an experiment; **Unknown** is not established.

This preparation reuses Stage 1–5, especially [Stage 4 §3](nlq-stage-4-causal-and-generalisation-mechanism-investigation.md#3-compositional-expressiveness-matrix)
and [Stage 5 §8.3](nlq-stage-5-evidence-based-architectural-evaluation.md#83-gate-x--b-versus-c-on-extension-economics-and-real-composition),
and the preceding conversational Bounded Composition Design Comparison and its
independent-review addendum. It does not repeat the forensic investigation or
enact those proposals. ETL ownership/publication boundaries remain unchanged.

## 2. RDF evidence readiness

### Method and limits

**Observed — new read-only inspection, 2026-11-11:** manually authored SPARQL
SELECTs against `http://localhost:3030/houses/query`, not the application compiler
or `/ask`, captured typed RDF bindings. Correct-owner captures began at
**13:51:22 UTC**. Each query used a deterministic order and `LIMIT 100`, a
20-second request timeout and a diagnostic maximum of four pages. All finished
on their first page: House terms **65**, committee owners **3**, Dublin Central
representation/party evidence **10**, committee memberships **15**, and party
chains for those candidate Member identities **28** rows. Multiple asserted
types explain duplicate identity paths; rows are not people.

Owner graphs were taken from `poc/specs/query-schema-contract.json`:
`graph/houses`, `graph/constituencies`, `graph/committees`, `graph/parties`,
`graph/political-affiliations/identities`, and Member-owned `graph/member/…`,
all under `https://data.oireachtas.ie/`. An initial diagnostic used the wrong
optional affiliation graph; those apparent missing links were discarded, not
treated as a data gap. Corrected captures use the authoritative `/identities`
owner. Queries preserve optional names, ranges, endpoints and identity links
for candidate paths rather than filtering on display names or current dates.

**Unknown:** loaded capture/run identity, transactional snapshot, global source
coverage, and complete absence of malformed paths outside these scoped queries.
No complete store dump, source audit or global negative certification is claimed.
Sequential binding captures are not a frozen experimental dataset. Stage 3's
[independent-oracle limitations](nlq-stage-3-20261110/independent-oracle-review.md)
remain limitations, not passes retroactively supplied by these positive checks.

### A. Sinn Féin / Dublin Central

**Observed:** one qualifying recorded identity, **Mary Lou McDonald**, at
`asOf=2026-11-11`. The current typed Dáil term is `/house/dail/34`, with
House-owned start `2024-11-29T00:00:00`, no recorded end and a typed
`dct:PeriodOfTime`. Her exact Dáil membership represents the term-34
`/constituency/Dublin-Central`; the Sinn Féin episode points to **that same
membership**, not merely the same Member. Both typed DateRanges start
`2024-11-29T00:00:00` with absent ends. The party occurrence belongs to term 34
and links to the typed reviewed `/political-affiliation/sinn-fein` identity.
This agrees with retained Stage 3 D1/D2; the filtered count is still unsupported
by current admission, not an already executed capability.

**Inferred measure:** **1 distinct qualifying recorded Member identity** in the
captured selection. This does not establish a complete real-world total. The
current endpoint also contains four active, unfiltered Dublin Central identities;
the ended Paschal Donohoe membership is not current. Neither four nor a term-wide
five-person count may substitute for the party-filtered request.

### B. Committee of Public Accounts / Fianna Fáil

**Observed:** the uniquely current matching owner is
`https://data.oireachtas.ie/ie/oireachtas/committee/dail/34/committee_of_public_accounts`,
source English label **Committee of Public Accounts**. Its typed owner DateRange
starts `2024-12-18T00:00:00`; its exact Dáil-34 HouseTerm independently contains
the reference date. Earlier matching incarnations are ended.

Among the captured candidate paths, **Albert Dolan, Martin Daly, Paul McAuliffe
and Séamus McGrath** have independently active CommitteeMembership, containing
DáilMembership and typed Fianna Fáil PartyMembership evidence. Party and
parliamentary intervals start `2024-11-29T00:00:00`; committee intervals start
`2025-05-07T00:00:00`, except Martin Daly's `2026-07-15T00:00:00`. No ends are
recorded for those witnesses. Each party occurrence targets Dáil 34 and the
typed reviewed `/political-affiliation/fianna-fail` identity. The lookup allowed
both current Dáil-34 and Seanad-27 party paths; their observed Dáil paths are
**data**, not an imposed Dáil-only answer restriction.

The 15 captured committee episodes contain 13 current Members. Catherine
Ardagh's current Fianna Fáil evidence does **not** qualify her: her committee
episode ended `2026-05-28`. Catherine Connolly's committee episode also ended.
Thus a Member's party evidence alone cannot rescue an ended committee path.
Four is an observed scoped positive set, not a certified complete roster.

### Durable exemplar witnesses

These lossless expansions retain two positive chains without turning disposable
captures into golden fixtures. Let `D=https://data.oireachtas.ie`,
`M=D/ie/oireachtas/member/id/` + Member ID, `H=M/house/dail/34`,
`E=H#party-membership-` + episode hash. Parliamentary range is `H#date-range`;
episode range is `E#date-range`. Member source graph is
`D/graph/member/` + Member ID for these ASCII examples.

| Witness | Mary Lou McDonald | Albert Dolan |
|---|---|---|
| Member ID | `Mary-Lou-McDonald.D.2011-03-09` | `Albert-Dolan.D.2024-11-29` |
| Episode hash | `b6ba1335ea2b1599fd7cbd937edf6620fa1e0c6ba0467d97a6f7541b62a927bc` | `329366f077b8cea52814a3f801b2cb4fcc96b8d00f411d80274ab46e092f963b` |
| Party IRI suffix after `D/ie/oireachtas/party/dail/34/` | `Sinn_Féin` | `Fianna_Fáil` |
| Reviewed identity suffix after `D/ie/oireachtas/political-affiliation/` | `sinn-fein` | `fianna-fail` |
| Parliamentary / party start | both `2024-11-29T00:00:00` | both `2024-11-29T00:00:00` |

Albert's CommitteeMembership is
`H#committee-membership-83ee419568331dfb794f79cd3762741bdba677951e3bbc287cdf5ef79807a3bf`,
its range is that IRI plus `#member-date-range`, start `2025-05-07T00:00:00`.
It targets the exact committee owner above. The Member, DáilMembership,
PartyMembership, CommitteeMembership and DateRange types are asserted;
relationship endpoints have `xsd:dateTime` values. The reviewed identity is typed
`members:PoliticalAffiliationIdentity`; the party owner asserts
`members:ParliamentaryParty` and `members:activeDuringTerm` for the same term.
Neither label equality nor graph co-containment supplied any identity join.

## 3. Proposed experimental semantic contracts — approval outstanding

### Shared rules

- `asOf` is one pinned configured calendar date. Use existing inclusive
  calendar-day evaluation; a known start is required, absent end is open-ended,
  not proof of permanent service. Each time-dependent relationship must qualify
  independently. Historical overlap or current-term identity alone is insufficient.
- Resolve exact local resources using current resolvers and reviewed mappings;
  ambiguity remains clarification. Party identity comes from the reviewed
  affiliation link, never names, external recognition or Independent collection
  status. Current terms come from unique House-owned dated evidence per House.
- Preserve typed bindings, relationship resources, source graph, term/period,
  range identities, original endpoints, effective date and all qualifying witness
  alternatives. Separate witnesses survive until distinct-Member projection.
- Missing/conflicting required identities, invalid types/dates, conflicting
  resource ranges or truncated/capped/incomplete required enumeration produce an
  evidence nonanswer, not a partial factual total. Inspect relevant candidates
  before filtering/deduplication; do not hide invalid inputs behind inner joins.
  Missing display fields must not silently remove candidates.
- Multiple supporting episodes are not automatically errors. Do not introduce
  a universal one-party-at-a-time rule absent semantic authority. An ambiguous
  affiliation identity for a required party resource fails closed; any broader
  cross-episode exclusivity requirement needs separate approval.
- **Recommend no successful empty list or zero in this first experiment.** A
  valid but empty selection remains an evidence nonanswer, consistent with the
  stricter existing committee/party paths. A later recorded-zero policy would
  need its own scope and uncertainty contract; complete real-world zero is not
  established by local absence. Safety/refusal cases are not positive successes.

### Contract A — party-filtered representation count

Required graph: Member → DáilMembership → exact current DailTerm;
DáilMembership → DailConstituency → that same term; Member → PartyMembership
episode → **that exact DáilMembership**; episode → ParliamentaryParty → that
same term and reviewed named affiliation identity. Both parliamentary and party
intervals independently contain `asOf`. House scope is Dáil because the question
asks for TDs and a Dáil constituency, not because of an inferred party restriction.

Return `count distinct Member IRI` only after complete valid bounded selection,
retaining drill-down witnesses and list/count parity. **Recommended measure:**
qualifying identities recorded in the frozen RDF, explicitly labelled as such.
If the user instead requires a complete real-world total, return an evidence
nonanswer unless separately accepted source-coverage authority establishes it.
Do not silently qualify a weaker count and score full intent as satisfied.

### Contract B — committee/party intersection

Required committee path: Member → CommitteeMembership → exact resolved Committee;
Committee → its dated HouseTerm. Required party path: the **same Member** → typed
PartyMembership episode → its exact containing parliamentary membership → its
HouseTerm; episode → term-scoped ParliamentaryParty → reviewed Fianna Fáil
identity. The parliamentary membership must also be linked from that Member.
Both paths retain separate membership resources and evidence roles.

**Recommend either House:** enumerate the existing typed Dáil and Seanad party
path variants at their independently current terms. Require Committee owner,
committee HouseTerm, CommitteeMembership, party episode, containing parliamentary
membership and party HouseTerm independently current at the same `asOf`.
Deduplicate the resulting union by Member identity, preserving every witness.
This is a bounded two-variant scope, not permission for arbitrary disjunction.

**Recommend no common-HouseTerm equality between the two paths.** The question
requests current committee members who belong to a party, not membership in the
committee's House or membership during its whole term. Adding equality would
introduce an unstated restriction and could discard valid differently scoped
paths. Each party occurrence must still match its **own** containing membership's
term. A Dáil-only or same-House interpretation would require explicit user scope
or separate human approval; none is inherited automatically from the Committee
IRI. Existing single-House capabilities do not already admit this combined scope.

## 4. Minimal B/C representation and execution sketches

**Proposed notation, not implemented syntax:**

```text
R(m, pm, t, c) = current representation with parliamentary-membership IRI pm
P(m, pm, t, e, p, a) = current party episode e containing parliamentary-membership IRI pm
K(m, k, cm, kt) = current committee incarnation and membership
A = CountDistinct(m, Join(R, P, shared=[m,pm,t]))
B = ListDistinct(m, Join(K, P[House=Dáil-or-Seanad], shared=[m]))
```

Each atom carries its own intervals, graph ownership and evidence obligations.
In A the shared membership binding is essential; in B the committee and
parliamentary memberships are **not** equated. Variable scoping must prevent
accidental joins between similarly named term/range fields.

| Stage | B: bounded composition inside v2 | C: minimal constrained IR/compiler |
|---|---|---|
| Structured representation | Retain v2, introduce bounded operation/binding descriptors with shared projections, not whole-topology role unions. | Versioned typed atoms, explicit bindings/conjunction, temporal obligations and projections; existing v2 graph syntax could be reused. |
| Validation | Validate complete composition and primitive preconditions, then validate native leaf plans. Closed legacy validation alone cannot validate the combination. | Validate approved atom signatures, binding types, context equality, connectivity, scope, budgets and projection preconditions uniformly. |
| RDF mapping | Lower native leaves through existing reviewed predicates/patterns/owners. | Lower atoms through the same approved registry, with deterministic variable/graph allocation. No arbitrary predicates or graph discovery. |
| Identity/time composition | Obtain structured leaf evidence, join exact bindings and evaluate each role's current interval. A may reuse its existing combined-selection backend. | Uniform binding/evidence evaluation; may also retain existing family backends as leaves. Current-at semantics stay role-specific. |
| Execution | Bounded safe SELECT retrieval plus bounded in-memory joins. No pipelines of rendered answers or rewritten easier subquestions. | Same bounds and safety gate; simple SELECTs and Python evidence validation suffice. No optimiser, general negation or arbitrary Boolean language required. |
| Projection | Shared evidence-native list/count, then render. | The same reusable projection contract; count is not an unvalidated SPARQL aggregate shortcut. |

**Observed reusable assets** under `poc/nlq/`:

- `composable_plan.py`: `_reviewed_pattern`, `_reviewed_predicate`,
  `_member_relationship_composition_mapping`,
  `compile_member_relationship_composition_query`,
  `_compile_member_party_temporal_query`, `_mapped_member_interval`,
  `_interval_overlap`, `_common_interval_intersection`, term-scoped affiliation
  resolution and existing distinct-Member selection logic.
- `committee_members.py`: `resolve_committee`, `compile_members_query`,
  `project_members`; `representation.py`: `resolve_current_house_term`,
  constituency resolution/current membership evaluation and representation query.
- `pagination.py::select_pages`, `safety.py::validate_sparql`, result/outcome
  envelopes and existing graph/query contracts. The safety contract limits query
  length to 32,000 characters, SELECT pages to 100 and offset to 10,000; it rejects
  Update, SERVICE, dataset clauses, subqueries, paths and variable predicates.
- `plan_sparql.py` supplies a separate semantic-v1 constrained-compilation example,
  not an integrated current-party/committee backend: its `on` translation is
  narrower. Do not price C as a wholesale rewrite or assume v1 already solves it.

**Observed work still required:** raw evidence must be separated from formatted
tables/strings in both designs. Existing private helpers are not already a stable
composable interface. A's count is rejected by draft/canonical projection gates
even though `_temporal_member_party_result` contains count logic. B's combined
committee/party shape has no existing admitted route. The draft, Python validator
and final-schema inventories disagree; relevant schema alignment is real B work.

**Inferred distinction:** a B implementation with typed fragments, bindings,
conjunction and shared projections **is a constrained IR within v2**. Retaining
family backends does not distinguish it from C. A materially different B would
lower each composition into closed family shapes, probably adding committee/party
validator, mapping, executor and evidence cases. That can implement two families,
but does not meet the reuse objective. A C implementation with per-combination
assemblers has the same defect. Do not create those alternatives merely to make
an A/B comparison possible. For this scope, evaluate **one common bounded kernel**;
leave unrelated families and production routing intact.

**Hypothesis:** this kernel reduces extension work. **Unknown:** actual build,
review and maintenance cost. Count representation, adapters, schema alignment,
validators, lowering, evidence/projection and verification together under one
frozen rubric; no topology work may disappear into a separate cost category.

## 5. Withheld generalisation probe

**Proposed primary probe:** current named-committee membership ∩ current named
Dáil-constituency representation, returning distinct Members. It recombines K
and R, whereas the disclosed examples use R+P and K+P. This is a different
relationship combination, not just another party parameter or projection flag.
Its membership resources join on exact Member only; each path is independently
current. The constituency's membership/occurrence share the exact Dáil term;
do not add equality with the committee's HouseTerm. No party condition belongs
in this probe. Its new combined semantics still require human approval.

**Observed primitive prerequisite, not a probe execution:** a separate bounded
representation-only SELECT at **13:53:24 UTC**, restricted to Albert Dolan's
Member identity and Dáil 34, returned four typed-binding variants of one path:
`H` → `D/ie/oireachtas/house/dail/34/constituency/Galway-East`, English label
**Galway East**, with asserted DailConstituency type, the exact constituency term
link and `H#date-range` starting `2024-11-29T00:00:00`, no end. Together with the
independently verified committee primitive, this establishes positive witness
availability for a parameter candidate. **No combined committee/representation
query, compiler plan, full intersection answer or withheld score was executed.**
An independent custodian must freeze the exact parameter selection, complete
candidate evidence and oracle before implementation; a one-person prerequisite
check is not a full roster oracle.

**Secondary option:** three numbered Dáil terms, exact-Member intersection of
recorded term memberships, with no simultaneity claim. This is homogeneous arity
extension, not a new relationship primitive. Existing graph compilation already
iterates referents/edges; current schema/validators restrict arity. Consequently
this alone could favour a small admission extension without demonstrating
cross-relationship reuse. A complete positive three-term oracle has **not** been
established here. Leave it optional; the smaller K+R probe is more discriminating
for the stated requirement.

Neither topology is secret after these reviews. Only independently frozen exact
parameters, evidence, adversarial cases and expected results can be withheld.
Do not claim an unseen topology or full evaluator independence falsely.

## 6. Smallest justified implementation experiment — proposed only

After the approvals in §7, build **one shadow deterministic vertical slice**:
R/P/K evidence-native primitive adapters, explicit exact-binding join, independent
current-at evaluation and list/distinct-Member-count projection. Support only
the approved scopes of A and B; freeze the implementation before the custodian
reveals the K+R probe inputs/oracle. No default `/ask` change, provider call,
admission repair, broad relation registry migration or production publication.

Use the two disclosed semantic inputs as minimum positive build cases. For A,
check list/count parity internally; for B, retain its list-only experimental
projection. Do not infer arbitrary committee counts from shared count code.
Use existing controls as development/regression evidence, not fresh holdouts.
Freeze all negative controls and scored evidence assertions before candidate
execution; do not change protected fixtures or source data to obtain a pass.

**Exact proposed acceptance/rejection:**

1. Both build cases and every frozen positive probe input must return **100%**
   correct identities, measure/unit, temporal scopes and **all** scored witness
   assertions. Any incorrect factual/provenance assertion rejects the candidate;
   refusing a verified supported positive is an expressiveness/capability failure,
   not successful answering.
2. Zero factual answers on fixed-intent candidates dropping party, constituency,
   committee, current scope, required membership equality or requested count; also
   reject added unsupported attendance/negation/extra-projection requirements.
   Test original approved intent against independently mutated candidates, not
   only candidates produced by the constructor. Well-typed weaker plans remain
   invalid for that request. This does **not** establish general English admission.
3. Zero unjustified answers on missing/invalid starts/range types, wrong containing
   membership/term, ambiguous identities, conflicting resource evidence, malformed
   rows or incomplete enumeration. Include ended committee/current party and
   current representation/ended party cases. Valid-plan evidence failures are
   scored separately from semantic admission failures. Empty selections follow
   §3's proposed nonanswer policy; no invented zero.
4. Exact results and witness associations must be invariant to equivalent input
   order/duplicates **within bounds**. Validate resource conflicts before member
   deduplication. Check multi-episode witnesses and correct row-local term/source
   metadata, retaining the D8 regression lesson without broad defect repair.
5. Preserve existing query/pagination limits and stricter family failures. Before
   implementation, approve and freeze whole-plan budgets: at most two relationship
   selections per plan (from three reusable R/P/K primitive adapters overall),
   at most two explicit House variants inside P, eight SELECT requests total per
   plan, and 100 retained
   raw rows per request, with 20-second request timeouts; reject exhaustion or
   oversized/intermediate results rather than partial counts. Cap binding-join
   output at 100 witness tuples. These are proposed *stricter experimental*
   ceilings, not changes to production safety. Charge leaf resolution queries and
   pagination against the same total, not just answer queries. If these ceilings
   exclude a frozen positive, the experiment fails its budget-fit criterion;
   do not relax them after observing outcomes.
6. The withheld K+R plan must execute through the frozen primitives/binder,
   validator, lowering and evidence projection with **no new topology-specific
   schema union, validator/compiler/executor branch or assembler**. New input
   data/oracle and approved capability configuration are distinguished from logic
   changes under the pre-frozen rubric. Any required generic defect fix still
   counts as changed code and ends strict zero-change reuse credit for that run.
7. No regression of existing applicable production controls. Experimental approval
   of A/B does not silently flip existing production refusal tests or advertise
   new capabilities. Preserve all queries, typed responses, failures, intermediate
   witnesses, projection and query-budget accounting in future experiment evidence.

This is smaller than the full Stage 5 Gate X proposal: **no NL/provider arm or
11/12 paraphrase threshold is claimed satisfied**. Deterministic success would
support a bounded v2-hosted composition kernel and a later separately approved
integration plan, not a general compiler replacement or safe NL admission.
Failure through repeated topology cases rejects the proposed reuse mechanism;
it does not automatically prove that a wholesale C migration is necessary.

## 7. Outstanding human decisions and disposition

1. Approve or revise §3: recorded-identity count scope, either-House party path,
   no cross-path HouseTerm equality, role-specific current tests, witnesses and
   conservative empty/uncertainty policies. Full real-world totals remain blocked
   without source-completeness authority.
2. Approve one minimal kernel experiment rather than a nominal B/C contest;
   agree representation/interface ownership and the fixed budgets in §6.
3. Approve K+R semantics and appoint an independent custodian to freeze a stable
   evidence snapshot, exact probe/oracle and negative controls. The present scoped
   captures are readiness evidence, not that complete experimental freeze.
4. Resolve checkout synchronisation separately. No commit/push is attempted from
   this behind-origin checkout; no branch/worktree change is used to bypass it.
   Future integration must include the fetched query-explainer presentation
   requirements without attributing unrecorded execution or completeness to prose.

**Readiness verdict: Conditionally ready.** The previously unknown positive
committee/Fianna Fáil evidence blocker is resolved. Semantic acceptance and the
frozen experimental protocol remain unapproved; there is no Gate L or Gate X
implementation authorisation. Stop here before implementation.

### Verification and evidence retention

**Observed:** a separate executor independently checked the corrected typed
captures and verified A's witness and B's four positive identities, including
resource-level grouping, types and intervals; it issued no endpoint requests.
These B positives have same-term Dáil witnesses and do not depend on adopting
the proposed either-House/no-common-term semantics. Read-only RDF queries,
source-reference review and Git checks only;
no runtime suite, ontology validation or benchmark pass is claimed for this
report-only preparation. Disposable query text and typed responses are under
`/tmp/oireachtasontology/nlq-composition-readiness/reviewed-owner/`; initial
diagnostics are outside that corrected subdirectory. SHA-256 of corrected JSON:

| Capture | SHA-256 |
|---|---|
| `terms.json` | `fbecd245da145ae752be83e2c18348f123b0aee2eb41420aee9ef87a3ebe1fea` |
| `committee-owners.json` | `b275b9b01be8a2fb1555b73a26aecddfc59a2774a88d2313ecb430ee8c2849fd` |
| `dublin-central.json` | `597b054b8a7c476fcf09bffbe77c1b577497c13e5986f966889f04508d898b0c` |
| `committee-members.json` | `83bce07929c2348868c4dec276a7df9b7508b61f46a9f073ab059f635e73f5d7` |
| `committee-candidate-party.json` | `80f490af85810e3d42eb6367db05515130d616f1ef43e9f6402bb81b59bbeebf` |

The parent directory's `representation-prerequisite.json` has SHA-256
`210579f6e7addaf0dc0fd3588bc6225f54c245797de6120f409965282dbae881`.
These hashes identify disposable artifacts, not immutable store/source captures.
The exact exemplar identities and witness dates above are durable findings;
future experiments must retain their own independently reviewed full oracles.
Report checks passed for the heading, local links, capture hashes/bounds, exact
exemplar IRI expansions and whitespace. Independent report review prompted an
explicit `pm` membership binding and clarified per-plan versus overall adapter
budgets. Final Git inspection found only this untracked report; `HEAD...origin/master`
remained `0 / 4`, so no commit or push was attempted.
