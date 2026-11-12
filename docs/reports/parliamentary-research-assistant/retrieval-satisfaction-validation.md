# Parliamentary Research Assistant — Validate Supporting Retrieval and Requirement Satisfaction

**Date:** 12 November 2026

**Repository / branch:** `stephenrigney/OireachtasOntology` / `parliamentary-research-assistant`

**Investigated revision:** `321ff9cc1dea8cb9735b9931c0f7e86e39ff53d3`

**Recommendation: NO-GO for corrective application implementation. Stop at human design review.**

## 1. Finding and boundary

The v0.4 distinction is useful and executable: a sponsorship listing can be
retrieved as supporting research for housing Bills without pretending that the
query filters housing. Exact evidence checks can also reject a stronger typed
claim citing that listing. **Neither establishes that a model-generated ledger
preserves the whole original requirement.**

The bounded diagnostic demonstrates the remaining failure, rather than declaring
the design validated:

- A condition-conjunction gate accepts every deliberately narrowed ledger in the
  13 frozen cases, including all ten incomplete-proposal controls. It checks only
  the conditions supplied to it. Correctly identifying an unmet condition first
  makes the gate look safe; omitting that condition defeats it.
- A coordinator-owned original-intent hold prevents these unsupported parent
  closures without consulting expected-answer labels. However, it also withholds
  closure for all three complete ordinary-language controls. No independent
  mechanism for discharging that hold has been demonstrated.
- Exact typed fact/claim matching works within the small tested projections.
  Attaching a valid typed claim or citation to stronger prose does not verify
  that prose. The prototype withholds **all** free prose, including correct
  prose; that is a limitation, not a report-authoring solution.

Thus the combined exit criteria are **not met**. This is not a finding that
LLM-led research is impossible. It is a demonstrated failure of the proposed
ledger-only authority boundary, and an explicit over-blocking failure of its
smallest fail-closed fallback.

No application, UI, approved specification, compiler semantics, ontology, ETL,
source fixtures, dataset or configuration was changed. The deliverable consists
only of this report, a diagnostic tool and diagnostic tests.

## 2. Materials and method

Read the revised [v0.4 specification](../../specifications/parliamentary-research-assistant.md),
[acceptance contract](../../specifications/parliamentary-research-assistant-acceptance.md),
[editorial contract](../../specifications/parliamentary-research-assistant-editorial.md),
[corrective admission review](corrective-admission-review.md) and its
[frozen evidence](corrective-admission-live.json). The Phase 0 report and current
compiler/adapter/coordinator source supplied integration context.

The frozen bundle is pinned by SHA-256:
`c3c975f36be4a0c72cc55e331770a39a0917e347d39da18f969d31a3130c1c6e`.
The diagnostic refuses a changed bundle rather than silently rebasing controls.
It revalidates the **exact 13 saved parent questions and drafts**, including both
date refusals. It separately replays all **26 ordinary compiler operations / 35
query responses** from the bundle through public `execute_question`. Each query
must match saved text, order and hash; projected rows and outcome must match.
There is no fallback response for an unexpected query.

This reuses the earlier live investigation, not a new live observation. No model
calls, network calls, dataset reloads or data writes occurred. The five earlier
injected parent executions are retained evidence, not replayed as ordinary
questions. The parent admission results remain unchanged: three complete and
eight incomplete proposals admitted; two date-qualified proposals refused.

**Evidence categories:**

| Category | What this tranche establishes |
|---|---|
| Deliberately injected proposals | Exact frozen compiler drafts, plus AI-authored ledgers omitting every condition beyond the retrieved listing; typed claim mutations and a supplemental conjunctive request. Mechanism falsification, not observed model error. |
| Real LLM-generated proposals/reports | None. Zero model calls. The independent agent critique is a design review, not a research-model trial or semantic authority. |
| Independently prepared research questions | R1 and R3 are verbatim briefs already supplied by the acceptance contract. No new researcher-authored question collection or held-out paraphrase evaluation was conducted. Other diagnostic wording/ledgers are AI-authored. |
| Data observations | Retained 12 November compiler observations with unknown dataset snapshot/freshness and uncertified source coverage. Not a current external factual oracle. |

No general safety, reliability or model error rate follows from this controlled
set. Live model trials cannot repair the deterministic omission failure; they
remain necessary for a later candidate that passes this boundary first.

## 3. Minimum candidate mechanism and authority

Keep six distinct records, not one task marked successful:

| Record | Proposed by LLM | Independently enforceable boundary |
|---|---|---|
| Original requirement/version | Interpretation and proposed material conditions | Coordinator retains exact original and authorised changes under stable IDs; model cannot delete the original or waive its unresolved binding. |
| Subsidiary question | Purpose, dependency, supporting/direct/exploratory role | Its own operation semantics/parameters are checked, not equivalence to the whole parent. Relevance needs a defensible purpose link, not merely an executable tool or shared Member name. |
| Tool operation | Selection and typed parameters | Existing compiler grounds identity, validates plan, dates, safe queries, pagination and factual evidence. No model SPARQL/graph identities. |
| Accepted fact | Candidate use of a result | Trusted evidence boundary emits only facts actually established by that operation; relation, exact identities, scope, values and provenance stay attached. Parent qualifications are never inherited. |
| Condition support / satisfaction | Suggested links and completeness | Typed evidence may support a named condition. Conjunction over proposed conditions alone cannot certify that no condition was omitted. Original-intent hold remains unresolved without independent binding. |
| Report claim | Proposed wording and dependencies | Typed claim must match the actual fact and cited source, including scope. Free prose needs a separate binding mechanism; a typed companion, citation, span coverage or model approval is not one. |

The prototype implements only diagnostic slices of this design, not a reusable
framework or application coordinator. `Atom` and `Fact` are immutable typed test
records. `ledger_only_answered` is deliberately insufficient. `original_disposition`
always preserves an independent `original_intent_not_independently_bound` hold;
there is **no model-settable “bound” flag**. There is deliberately no function
that pretends to derive all requirements from arbitrary language.

The small fact projections are hand-inspected mappings of accepted compiler
fields, not universal row-shape semantics. They cover recorded sponsorship,
the compiler's primary-status classification, constituency/term representation,
recorded Bill status and the **opaque recorded-history field**. Other successful
operations produce no prototype facts. Lifecycle strings are not parsed into
new event/outcome predicates; historical representation is not expanded into
unexposed service episodes. Production use would need registered per-operation
payloads from the existing evidence evaluators, not a generic display parser.

### Compact housing example

```text
r1 original: “Which housing Bills did Malcolm Byrne sponsor?”
   coordinator-owned unresolved original-intent binding
   model proposal: recorded sponsorship list [housing condition omitted]
      |
s1 supporting question: “Which Bills did Malcolm Byrne sponsor?”
   purpose: establish candidate Bills for subsequent subject investigation
      |
e1 compiler result: exact Member/Bill identities, recorded sponsorship,
   primary-status fields; retained observation, uncertified source coverage
      |
c1 recorded sponsorship of Bill B       -> typed claim accepted from e1
c2 B is a housing Bill                  -> no subject evidence; rejected
c3 all listed Bills answer r1           -> parent closure withheld
```

Housing is known to the **test author/user brief**, not independently discovered
by the runtime hold. The full-inventory test supplies a subject condition as
test input; the omission test deliberately does not. The hold preserves the raw
original but cannot name every missing condition. This is a failure to establish
explicit semantic intent retention, not evidence that the condition ledger is
complete.

### Relevance is a separate, limited check

The typed dependency experiment accepts sponsorship enumeration for a sponsored-
Bill investigation; it accepts a lifecycle lookup only for a Bill in the accepted
sponsorship identities; it accepts constituency retrieval for career research.
It rejects sponsorship for an opposition objective, same-Member sponsorship for
a career objective, and an unrelated Bill lookup. No per-query approval is used.

For housing, the user's approved example itself gives a defensible candidate-
enumeration purpose. For opposition, there is **no** automatic sponsorship edge;
without a separate justified background question, skip dispatch. The tool's
replayed sponsorship result is not permission to execute it for opposition.

These checks distinguish useful dependencies from mere executability **given a
faithful typed objective**. If the LLM changes `opposition` into `sponsored_bills`,
the typed relevance check cannot independently detect that reinterpretation.
An exploratory-purpose sentence is auditable but not independent semantic
proof. Free-text purpose binding therefore shares the unresolved authority
problem; it has not been declared solved by this experiment.

## 4. Controlled results

All rows below retain the exact saved parent wording/payload in the diagnostic.
“Listing only” is a separately stated narrower question, never a replacement
for the parent. The full-condition inventories are **test oracles/inputs**, not
a hidden production admission map.

| Frozen condition | Useful narrower retrieval | Gate with explicit missing condition | Ledger that omits condition | Stronger typed claim |
|---|---|---|---|---|
| Housing subject | Sponsorship candidate listing | Open | Incorrectly closes | Subject claim rejected |
| Opposition | Skip absent separate justified context | Open | Would incorrectly close if fed sponsorship facts | Opposition claim rejected |
| Became law | Sponsored candidates, then separate legislative evidence | Open | Incorrectly closes | Enactment rejected |
| As a Senator | General sponsorship candidates only | Open | Incorrectly closes | Senator-period scope rejected |
| Primarily sponsored | Listing with recorded primary-status fields | Open for unfiltered answer | Incorrectly closes | Reclassifying Supporting as Primary rejected |
| Sponsorship before 2024 | Untimed candidate listing if useful | Open; original compiler refusal preserved | Incorrectly closes | Before-date scope rejected |
| R1 progress and outcomes | Sponsored Bills, then exact Bill lookups | Open after listing alone | Incorrectly closes | Listing does not prove lifecycle or final outcome |
| R3 parliamentary roles | Constituency/term context | Open | Incorrectly closes | Office/committee role rejected |
| During ministerial service | Career constituencies as context | Open; no approved temporal intersection | Incorrectly closes | Ministerial-period claim rejected |
| Representation before 2020 | Career-wide listing if useful | Open; original compiler refusal preserved | Incorrectly closes | Before-date scope rejected |

The independent original-intent hold blocks closure for **every** row, even with
an omitted condition. That does not redeem ledger-only satisfaction: it is the
unbound original, not discovery of the omitted meaning, doing the blocking.
The supplemental AI-authored “housing ... before 2024” conjunction has the same
result when both qualifications are omitted.

Primary sponsorship is not inherently unavailable. The retained compiler fields
contain 13 Primary and seven Supporting classifications. Individual exact
classification claims can be accepted; the entire unfiltered listing cannot
inherit “Primary”. A properly registered deterministic filtered projection could
answer a correctly bound primary-sponsor condition, but was **not implemented**
or smuggled into this experiment as a new compiler operation.

### Positive and negative authority checks

- A faithful **typed-input** requirement for the returned recorded sponsorship
  listing passes conjunction checking without clarification; exact sponsorship
  and primary-status facts pass typed claim checking.
- The three complete ordinary-language controls (sponsorship, its saved
  paraphrase and constituency history) obtain admitted compiler plans. The
  canonical sponsorship and constituency questions additionally replay factual
  answers; the paraphrase has no separate execution trace. The original-intent
  hold withholds parent satisfaction for all three. This is the required positive
  challenge **failing at the coordinator boundary**, not an ordinary-language
  acceptance pass. Typed-input success must not be substituted for it.
- Changing predicate, Member, Bill, date/scope or evidence ID prevents typed
  claim acceptance. A valid citation to sponsorship cannot establish opposition,
  housing, enactment or a Senator period. Missing/no accepted result creates no
  facts; unavailable committee/date evidence is not zero.
- A valid sponsorship atom paired with “These are all his housing Bills and
  they became law” is withheld. Correct free prose is also withheld: no general
  prose verifier was invented. A fixed rendering of typed facts could preserve
  their meaning but would not alone deliver the required LLM-authored report.

There are zero approval prompts in this offline mechanism. That is not a
measured interaction burden or a real dialogue success: the fallback stalls
parents rather than asking users to approve everything.

## 5. Meaningful R1 and R3 decomposition

### R1 — sponsorship, recorded activity, then outcomes

The saved ordinary operation identifies 20 locally recorded sponsored Bills.
All 20 exact number/year lookups replay successfully; no Bill identity is
invented or joined by title. Their recorded process statuses were 15 Current
and five Lapsed. These establish recorded status, not universal finality.

For **11/2020**, sponsorship evidence admits a sponsorship fact only. The
separate Bill lookup admits its recorded Current status and recorded history,
including a Bill Lapsed Event on **29 January 2025** and Committee Stage on
**27 March 2025**. The tests reject turning that status/history into a final-
outcome or enactment predicate. Neither the event nor the later activity supplies
a procedural explanation. The prototype retains the history field intact; it
does not manufacture a structured lifecycle witness from its display text.

This is a useful research sequence, not a count-only scenario. Sponsorship,
recorded activity/status and final outcomes are separate dependencies. Individual
documented developments can be reported at their supported granularity;
unanswered lifecycle/finality questions stay open. The earlier published-in-2025
count remains unavailable because dated Published evidence is missing; neither
legislative year nor a broader successful listing substitutes for it.

### R3 — representation/service versus other roles

The career operation replays four Dublin Central constituency/term identities
(31st–34th Dáileanna), not one undifferentiated constituency resource. The tests
accept exact representation facts and reject their conversion into ministerial
office, committee role or continuous tenure.

Separate retained operations reproduce four recorded terms and 5,684 cumulative
service days through the reporting date, with separate intervals/gaps. They are
existing compiler observations, not a continuity claim; the diagnostic does not
add an unreviewed structured duration projector. Committee count returns missing
evidence, not zero. The current named-office operation requires a named office;
guessing office names is not complete role discovery. All-career representation
does not establish representation during ministerial service.

Thus the constituency and bounded service portions are researchable. Other
roles and their discovery/coverage remain unavailable or unverified. A complete
career report or complete R3 satisfaction has not been demonstrated.

## 6. Actual authority failure and independent challenge

The failure is specifically tested **after omitting conditions from the ledger**,
not merely after correctly extracting and marking them unresolved. Runtime
gates never consult `proposalCompleteForQuestion`, the table of expected missing
predicates, or an expected answer total. Those belong solely to evaluation.

Preserving original text is necessary but does not independently bind it to a
typed condition set. Requiring all model-proposed conditions to have evidence
leaves omitted conditions invisible. Quotations, full source-span coverage,
catalogue-clause citations and a second model agreeing would not supply the
missing semantic check. Nor can an opaque “all residual resolved” flag be handed
back to the same model.

An independent read-only architecture challenge agreed that typed matching must
respect operation-certified meaning, highlighted the Current/Lapsed-event
counterexample and identified the positive-blocking problem. It proposed
coordinator-evaluated residual-to-catalogue-clause binding as a possible further
experiment, **not a demonstrated mechanism**. Merely making clause citations
more granular does not repair the previously retracted span-entailment assumption.
No independent approval or reviewer agreement is used as admission authority.

The smallest fallback has therefore been tested and its limitation exposed.
Further model trials or application work were not undertaken to conceal a
deterministic failure. No general impossibility result is claimed.

## 7. Coordinator/adapter implications and minimum next work

`research.py::account_brief` remains the rejected word-list gate;
`ResearchRun._task` still constructs canonical party/term requests. It must not
be relabelled as the validated design. `ResearchAdapter._execute` preserves the
compiler checks on `factualRequest`; a successful envelope carrying only a
`requirementId` cannot establish parent satisfaction. The party/term structured
witness facade is useful infrastructure, not a general intent/prose verifier.
Bill/career operations have not been exposed as new application tools here.

**No corrective slice is authorised by this report.** Before one, human review
must choose an independently testable intent-binding boundary. The smallest
credible alternatives are:

1. **Bounded independent binding for selected complete operations.** Test a
   deterministic, operation-specific interpretation that accounts for the whole
   input, including negation, qualifiers and conjunctions, without reusing the
   expected labels or growing a universal permissible-word list. Unknown input
   remains open while useful supporting work continues. Existing exact-string
   catalogue seams prove only their enumerated cases, not an ordinary-language
   interface. No such new binder is validated here.
2. **Selective requirement-level scope decisions.** Test explicit user decisions
   for genuinely uncertain meanings, with precise consequences. This is not
   per-query approval and must not make every original-text residual a mandatory
   confirmation. Independent detection of which meanings need disposition and
   the interaction cost still require validation; blanket approval is not an
   acceptable shortcut.
3. **Facts-only investigative fallback.** Allow clearly scoped, relevant supporting
   retrieval and typed findings while keeping original satisfaction unestablished
   and unbound prose unpublished as fact. This is a reduced-authority mode for
   human review, **not satisfaction of v0.4 or the product gate**.

After a binding mechanism passes a separately authorised validation, minimum
corrective implementation would require: versioned original/condition records;
separate subsidiary-operation, fact, satisfaction and claim dependencies;
coordinator-owned invalidation/holds; a small truthful typed tool registry with
relevance dependencies; structured accepted Bill/career evidence from existing
evaluators; and a tested factual-claim-to-visible-prose boundary. Preserve current
compiler safety and evidence semantics throughout. Neither fixture changes nor
compiler expansion is a prerequisite for the demonstrated R1 investigation.

## 8. Reproduction, verification and exit assessment

```sh
# No credentials/model/query service. Exit 2 intentionally reports the design gap.
.venv/bin/python -B tools/diagnose_retrieval_satisfaction.py

# Passing tests establish reproduction of both successes AND expected failures.
.venv/bin/python -B -m pytest -q tests/test_retrieval_satisfaction_diagnostic.py \
  --disable-warnings

# Focused neighbouring safeguards; no broad repository regression required here.
.venv/bin/python -B -m pytest -q tests/test_nlq_composable_q23.py \
  tests/test_nlq_stage_b.py tests/test_research_workspace.py --disable-warnings
```

Executed results:

- Diagnostic CLI: **exit 2**, expected; 26 operations / 35 exact saved query
  responses replayed, 13 frozen parent admissions reproduced.
- Combined focused run of the diagnostic and three neighbouring files:
  **151 passed**, 14,740 existing warnings, 151.45 seconds (27 diagnostic tests
  at that point plus 124 existing tests).
- After adding two harness-rejection tests, final diagnostic rerun:
  **29 passed**, 3.20 seconds. No application/compiler change between runs.
- `git diff --check`: passed. No live acceptance, browser/UI, full repository
  pytest or ontology reasoner rerun; those would not resolve this diagnostic-only
  semantic-authority failure. Earlier corrective verification is recorded in its
  report, not represented as a new run.

| Exit criterion | Assessment |
|---|---|
| Relevant narrower queries execute | Demonstrated at the unchanged compiler boundary; housing/R1/R3 dependencies are useful. General free-text relevance remains unbound. |
| All known incomplete controls prevented from becoming complete answers | Ledger-only **fails**. Original-intent hold blocks them but over-blocks positives. No validated combined solution. |
| Citation alone cannot admit unsupported claims | Demonstrated for exact typed projections; arbitrary prose withheld, not semantically verified. |
| Complete supported questions still answered | Compiler and typed-input positives pass; original ordinary-language satisfaction **fails** under the hold. |
| Original/unresolved intent traceable | Original text retained; explicitly enumerating omitted material conditions independently is **not established**. |
| No universal word lists, blanket approvals or model self-certification | None introduced. This does not compensate for failed positive/intent binding. |
| Limitations characterised | Yes: controlled injected set, no real-model trials, narrow payload projections, unknown data coverage, unresolved relevance/intent/prose binding, over-blocking fallback. |

**NO-GO.** Useful retrieval and bounded typed-claim checks are positive findings;
they are not validation of complete requirement satisfaction. Commit/push of this
diagnostic evidence does not authorise corrective application implementation or
a merge to `master`. **Stop at the human design-review gate.**
