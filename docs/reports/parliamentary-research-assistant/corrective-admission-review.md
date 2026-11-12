# Parliamentary Research Assistant — Corrective Admission Review

**Date:** 12 November 2026

**Branch:** `parliamentary-research-assistant`

**Investigated implementation:** `27a35a3067609a622aed90efa0f7a0ffd0af8a68`

**Disposition:** Mandatory admission-design review. Corrective application
implementation stopped; only this review, a diagnostic tool and its evidence
are delivered. The requested product/technical acceptance gate is **not met**.

## Scope and acceptance boundary

This review concerns the requested corrective LLM-led research vertical slice,
not an expansion of compiler semantics. The approved v0.3 specification and its
editorial and acceptance companions are authoritative. The existing Phase 1
application is **not** corrective product acceptance evidence.

The implementation must keep three checks separate:

1. The proposed research preserves the complete original user intent, including
   shared qualifications and subsequent authorised changes.
2. Each executed operation obtains accepted compiler evidence.
3. Every substantive report claim is supported by that evidence or an authorised
   reference source.

A typed operation, a source quotation, a successful query or a citation does not
by itself establish all three.

## Existing integration boundary

`poc/nlq/research.py::account_brief` currently accounts for the original brief by
removing model-extracted party mentions and admitting only remaining permitted
words. `ResearchRun._task` then constructs canonical party/term questions. This
is the rejected Phase 1 product behaviour, not a suitable foundation for the new
ordinary-language interface.

`poc/nlq/research_adapter.py::ResearchAdapter._execute` retains compiler
validation and actual query traces, but it validates `factualRequest`, not the
equivalence between that request and the complete parent research brief.
Replacing the word lists with a model-authored ledger cannot silently transfer
that missing authority to the LLM.

The requested two-pane interface, evidence inspection and progressive execution
can be retained. The current browser sends follow-ups only to a local fixed
message; there is no server-side dialogue continuation or report-authoring
model. Those features have not been represented as already implemented.

## Verification baseline

- Repository and requested branch match; the initial working tree was clean.
- Local configured model settings name `gpt-6-luna`; credentials and query
  configuration exist. Credentials are not included in this review.
- Python 3.13.15, pytest 9.1.1 and jsonschema are available. Playwright is not
  installed in the current `.venv`.
- `.venv/bin/python tests/validate.py` passed: 2,586 triples; HermiT executed.
- The initial six-file relevant pytest run reached its 120-second timeout with
  no reported failure. That interrupted invocation is **not** a passing suite.
  The identical command rerun with a 600-second limit completed: **255 passed**
  (17,092 existing warnings), in 231.34 seconds:

  ```sh
  .venv/bin/python -m pytest -q tests/test_research_workspace.py \
    tests/test_nlq_composable_q23.py tests/test_nlq_stage_b.py \
    tests/test_nlq_composable_stage_a.py \
    tests/test_nlq_composable_office_evidence.py \
    tests/test_nlq_latest_office_episode.py --disable-warnings
  ```

## Research-first feasibility observations

A separate read-only executor inspected the compiler and ran existing public
compiler paths against the configured local data on **12 November 2026**. These
are current compiler observations, not an independent external factual oracle,
source completeness certification or model-led product demonstration. No data
was reloaded or changed.

### R1 remains the primary factual candidate

The existing `member_bill_sponsorship` family returned 20 locally recorded Bills
for Malcolm Byrne (13 classified Primary and seven Supporting). Exact
`bill_lookup` operations for all 20 Bills returned success: 15 recorded process
statuses were Current and five Lapsed. This is enough evidence to investigate
R1 meaningfully; the stop described here is **not** a fallback caused by a
count-only or evidence-empty scenario.

The lifecycle evidence requires careful authorship. For Bill **11/2020**, the
*Seanad Electoral (University Members) (Amendment) Bill 2020*, the recorded
process status was Current, while its history included a Bill Lapsed Event on
29 January 2025 and Committee Stage on 27 March 2025. Neither the earlier lapsed
event nor the later recorded activity independently certifies a final outcome
or supplies an explanation of the intervening parliamentary procedure.

The Published-in-2025 sponsored-Bill count was unavailable because a sponsored
Bill lacked valid dated Published evidence. Substituting legislative year would
alter the question.

Relevant executable boundaries:

- `composable_plan.py::_execute_bill_sponsorship_question`: exact grounded
  Member, Bill/Participation association, bounded pagination, qualified role
  projection; sponsorship is not voting, opposition or subject filtering.
- `composable_semantic_planner.py::_validate_capability_selection_draft`:
  `bill_lookup` accepts exact Bill number/year, not a free-form query.
- `stage_b.py::execute_stage_b` and its lifecycle projectors: recorded process
  status and dated activities, with existing missing/partial evidence handling.

An identity-preserving sequence of accepted sponsored Bill identities followed
by exact number/year lookups is a bounded retrieval candidate, not permission
for arbitrary joins. These operations have **not** been added to the research
facade or advertised as available application tools.

### Second-domain evidence: bounded R3 career information

The same executor observed career-wide representation for Mary Lou McDonald:
Dublin Central in the 31st, 32nd, 33rd and 34th Dáileanna, retaining four
term-specific constituency identities. The separate recorded term count was
four. The duration operation returned 5,684 recorded service days through the
reporting date, with separate interval unions rather than a claim of continuous
service. The committee count returned missing evidence, **not zero**.

The existing named-office evidence operation requires both a Member and a named
office. R3 does not name an office; guessing offices from model memory would
not constitute a complete role-discovery operation. Historical constituency
projection also does not expose all individual service episodes by default.
This is useful partial career evidence, not a complete R3 report.

## Demonstrated admission gap

The independent executor supplied deliberately incomplete, schema-compatible
proposals through the public `execute_question` boundary. These are **injected
bad-proposal controls**, not observed errors by the configured LLM:

| Original request | Supplied proposal | Observed public result |
| --- | --- | --- |
| Which housing Bills did Malcolm Byrne sponsor? | Unfiltered sponsorship | Answer: all 20 sponsored Bills; housing restriction absent. |
| Which Bills did Malcolm Byrne oppose? | Sponsorship | Answer: the same 20 sponsorship results; requested relationship absent. |
| Entire R1 brief, including progress and outcomes | Sponsorship only | Answer: sponsorship list only. |
| Entire R3 brief, including parliamentary roles | Career constituencies only | Answer: four constituency/term rows, no roles. |
| Which constituencies did Mary Lou McDonald represent during her ministerial service? | Career constituencies only | Answer: the same unrestricted four rows. |

Draft/final-plan checks also admitted sponsorship-only proposals for requests
qualified by “became law”, “as a Senator” and “primarily”. In contrast, a
“before 2024” qualification was rejected. Existing guards are useful but do not
independently catch all material omission classes.

`composable_semantic_planner.py::_validate_existing_capability_draft` grounds mentions and
checks certain lexical conditions before constructing canonical sponsorship or
representation semantics. The observed accepts show why merely keeping that
call chain, or canonicalising a model's atomic requests before calling it, does
not establish complete parent-intent admission.

No corrective capability or independent editorial acceptance is claimed by
these checks.

## Retained reproducible evidence

The parent executor reproduced the admission controls and configured read-only
observations using [the diagnostic tool](../../../tools/diagnose_research_admission.py).
The [retained bundle](corrective-admission-live.json) contains:

- The exact original requests, injected drafts, published-schema checks and
  completed plans for **13 offline controls**: three complete proposals and ten
  deliberately incomplete proposals. **Eight of the ten incomplete proposals
  were admitted**; the two date-qualified controls were rejected.
- Five public-path incomplete-proposal executions: all returned factual answers
  while leaving the material requirement identified above unimplemented.
- Ordinary deterministic sponsorship, all 20 exact Bill lookups and five career/
  coverage observations: **31 operations / 45 actual read-only queries** in
  total, retaining every query, returned cell, plan, status and diagnostic.
- Reporting date, source revision, diagnostic-script hash and explicit unknown
  snapshot/freshness qualifications. Endpoint credentials are not retained.

Retained bundle SHA-256:
`c3c975f36be4a0c72cc55e331770a39a0917e347d39da18f969d31a3130c1c6e`.

R1 and R3 are verbatim acceptance-contract briefs. Other phrasings and omission
controls are **AI-authored diagnostics**, not independently collected researcher
requests. No model was asked to generate these proposals; there were **zero
model calls**. This is a falsification/reproduction bundle, not an LLM error
rate, a held-out research-quality evaluation or a completed research transcript.

Reproduce offline without credentials, a model or any query client:

```sh
.venv/bin/python -B tools/diagnose_research_admission.py
```

Reproduce against existing `.env.local` configuration, without data writes:

```sh
.venv/bin/python -B tools/diagnose_research_admission.py --live \
  --output /tmp/oireachtasontology/corrective-admission-reproduction.json
```

Create the output directory first if needed. **Exit code 2 is intentional:** it
means incomplete proposals were admitted, not that a safety test passed. The
tool never generates authoritative SPARQL; its live requests go through public
compiler execution and the existing read-only query client. Exact Bill follow-up
retrieval is capped at 32. Counts in this report are observations, not hardcoded
factual expectations in the tool. Subsequent data may differ; the retained file
is a finite observation, not an immutable dataset capture.

## Candidate coordinator design and unresolved authority

An independent architecture reviewer proposed an exact source-span ledger with
full text coverage, parent/child requirement dispositions, selective revision
invalidation, unchanged compiler checks, and registration-time tool semantics.
Those are useful coordinator mechanisms, and adding them does not inherently
require a compiler replacement. The reviewer correctly distinguishes bounded
fail-closed accounting from an impossible demand for universal natural-language
equivalence proof.

The proposed hard dispatch condition nevertheless needs an implementable
independent check: **how is an arbitrary quoted span verified to express only
the selected tool's semantics and parameters?** For the observed housing
counterexample, a model can cover every source character, select sponsorship,
ground the exact Member name, and classify the remaining text as already
entailed by the tool. Coverage, typed parameters and existing compiler admission
then all pass. A catalogue describing sponsorship does not establish that this
runtime classification is faithful to the question.

This is a concrete omission control, not a requirement to solve all language.
Treating a model-supplied span-to-semantic label as independently verified would
reopen the same authority gap. Conversely, requiring every span to match a fixed
collection of permissible formulations would recreate the rejected interface.

Plan-level user decisions remain appropriate for genuine material ambiguity or
assistant-proposed substitutions. They do not authorise silently treating an
omitted requirement as withdrawn, or using standing approval for future derived
queries. A second model's agreement would likewise not override failed or
insufficient deterministic admission.

The independent assessment was challenged with the actual injected controls
before choosing a disposition; its initial architectural preference is not
being presented as execution approval or empirical safety certification.
The reviewer subsequently **retracted** the catalogue-entailed-span assumption
and the sufficiency/no-escalation conclusion which depended on it.

The revised suggestion mechanically treats **all** non-parameter text as
residual, requires explicit user disposition, and caps completeness until those
decisions are recorded. That is a possible design experiment, not a demonstrated
answer to the requested interaction. It shifts interpretation authority to
users for relation words, answer shape and ordinary phrasing as well as genuine
ambiguities. The specification mandates **plan publication**, not universal
initial plan confirmation. Treating every such residual as approved would be a
blanket waiver; treating them all as decision items would impose an untested
interaction burden on initial and subsequent turns. Neither policy has been
adopted as an ordinary implementation detail.

Likewise, capping a requirement as “partial” after an unfiltered or
wrong-relationship query is not a substitute for the required **pre-dispatch**
intent check. Any independently useful supporting retrieval must retain an
explicitly different scope and cannot satisfy the original requirement by
renaming its status. The parent executor therefore retains the design-review
stop while recording the residual-disposition proposal as an unvalidated
alternative, not claiming that independent reviewers unanimously ruled out all
possible bounded designs.

## Separate authorship work, not a claim of impossibility

R1's evidence can support explanatory prose, with careful distinctions among
sponsorship, recorded status, dated events and final outcome. That does not
require inventing background or a general natural-language theorem prover.
However, Bill/career operations do not currently expose the same accepted
structured witness payload as the party facade; lifecycle activities are partly
formatted as display strings, and historical representation normally omits
membership episode/date details. Narrow evidence exposure and a controlled
authorship package would still be implementation work.

No model-authored report, claim-grounding trial or conversational refinement
sequence was run. Citation existence would not alone certify a claim such as
“all 20 Bills became law”, nor would term-level representation justify a
continuous-career claim. No automated or independent editorial acceptance is
claimed, and absence of an implemented universal prose verifier is not itself
being used as a reason to declare the requested product impossible.

## Disposition: mandatory admission-design escalation

**Stopped before corrective application implementation.** The selected
integration path plus model-authored decomposition is not sufficient to preserve
material intent on the concrete controls. The source-span alternative still
needs a genuinely independent, implementable semantic-binding check; it cannot
be declared safe from its text-coverage guarantees alone. The v0.3 §19 review
gate applies. This is **not** a finding that LLM-led parliamentary research is
impossible, nor a request to expand compiler/query semantics to answer R4/R5.

The decision requiring human review is the **admission authority for decomposed
ordinary-language requirements**. Before continuing, choose and independently
test a bounded mechanism which either:

1. preserves the complete original requirement through demonstrable
   coordinator/operation admission, including the injected wrong-relationship,
   subject, role, time and omitted-conjunct controls; or
2. converts genuinely uncertain meanings into explicit, requirement-specific
   user decisions before dispatch, keeping every unresolved original condition
   open rather than treating plan approval as blanket withdrawal.

The second option may be possible within existing clarification authority, but
its exact interaction and safeguards need review: it must not become mandatory
per-query approval, a standing waiver, or a scripted wording exercise. No new
scope-confirmation policy has been silently adopted. A narrowly scoped
admission-design/validation tranche is preferable to broad compiler remediation;
R1's demonstrated evidence remains available for the eventual product slice.

### Delivery and technical exit assessment

| Requested outcome | Actual status |
| --- | --- |
| Verify R1's existing operations/evidence before choosing a scenario | Done as read-only feasibility, with retained traces; R1 remains primary candidate. |
| Exercise a second domain | Bounded compiler-only R3 findings and explicit role-discovery gap; not an LLM-led flow. |
| Preserve existing compiler safeguards/infrastructure | No runtime/compiler/UI, schema, ontology, mappings, ETL, data, source-fixture or configuration changes. |
| Relevant regression and ontology verification | 255 tests passed; ontology/HermiT passed. No full repository pytest rerun for this diagnostic-only change. |
| Working corrective LLM-led application and dialogue | **Not delivered.** Existing Phase 1 remains unchanged. |
| New verified multi-domain application catalogue | **Not delivered.** Feasibility inventory is not advertised as application capability. |
| LLM-authored grounded reports and multi-turn evidence reuse | **Not implemented or demonstrated.** |
| R4/R5 conversational boundary demonstrations and R6 re-demonstration | **Not run** in a corrected application. Existing related regression coverage is not product acceptance. |
| Browser, accessibility, responsive and refinement verification | **Not run** for a corrected application. Existing Phase 1 browser results are not reused as v0.3 passes. |
| Representative model transcripts/reports for independent editorial review | **Not produced.** Diagnostic evidence retained instead; no self-certification. |
| Human product/editorial acceptance | **Not reached.** This is the earlier mandatory design-review stop. |

The unchanged Phase 1 application can still be launched using the existing
[development guide](../../development/parliamentary-research-assistant.md):

```sh
# Export existing local configuration as described in the guide, then:
.venv/bin/python -m uvicorn poc.nlq.research_app:app --host 127.0.0.1 --port 8010
```

This launches the **old technical prototype**, not the requested corrected
research collaborator. No further expansion or merge to `master` is proposed.
