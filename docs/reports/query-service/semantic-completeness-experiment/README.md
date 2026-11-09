# Query Service — Evaluate Semantic-Intent Verification Beyond Lexical Grammars

**Recommendation: REVISE; do not adopt a model-based completeness gate into the
production query path on this evidence.** A typed, source-grounded interpretation
plus blind independent reconstruction is worth a bounded **shadow** experiment,
but model agreement is not proof of completeness. Keeping the grammar as a veto
preserves its assurance and also preserves its reachability ceiling. Replacing
it changes the assurance basis and requires explicit architectural review.

**PR #27 remains draft, NOT ACCEPTED and unmerged.** Its failed acceptance and
all pilot artifacts are unchanged. This is design evidence, not remediation or
an acceptance campaign. Stop here for human architectural review.

## Authorities and method

Baseline: `42ecedaef71b769f4c8832af98db8a08d2393ebe`, branch
`feat/query-service-generalisation`. Read the proposed architecture on remote
`master` at **a74883bc51cb8e14dedb58d0fef8f9e01a3d06e8** (blob
`e9775ac1ad8e23c75b4ac4a68c306f2594128049`); local `master` lacks it.
The executable v2 compiler, Stage A and contract **2.29.0**, not that proposed
architecture, remain execution authority. Also reviewed the semantic-dispatch
interpretation report, pilot README/fresh-transfer, planner and draft schema.
No frozen PR #27 acceptance case files were read or replayed for this experiment.

`cases.json` contains 21 independently authored diagnostic questions, frozen
with the script/protocol in **ad7ef73** before execution. The author did not read
implementation, tests, reports or previous question text. Its contract extraction
did expose Q04/T01 **metadata identifiers**, not questions: independence is
qualified, and this is not a clean acceptance holdout. One original author label
was too broad: the years-of-service excluded-measure contrast in NEW-TC-02 is
outside the approved enum. The author acknowledged its separate **pre-run**
unsupported adjudication; original wording/label is preserved, not silently
replaced. NEW-TC-21 adds an approved membership-record measure contrast.

The offline runner invokes the **unchanged** typed parameter validator, supplying
oracle Member mentions to isolate whole-question admission from AI/entity errors.
It separately injects deliberately incomplete, schema-compatible interpretations
of unsupported questions. Those necessary-check passes are **not B admissions**.
Six already-observed pilot questions are replayed as development material, and
three executor-authored canonical controls check the harness. Populations are
not pooled. No prompts or grammar were tuned after results.

**Live testing unavailable:** no `NLQ_LLM_*` process configuration, no `.env` in
this worktree or primary checkout. No credential stores were searched and no
alternate model was substituted. Thus **zero model calls**, no requested/returned
model or measured model parameters, latency, tokens, dollar cost, variability or
completeness-verifier decisions. The repository default is `gpt-6-luna` via the
Responses-compatible OpenCode endpoint; that does not establish runtime access.
No live `/ask`, SPARQL, Fuseki or data mutation calls were made; focused tests
use their existing mocked in-process service clients.

## Measured results — admission layer only

| Population | Supported admitted | False refusals | Unsupported admitted | Ambiguity |
|---|---:|---:|---:|---|
| New diagnostic questions | **0/7** | **7/7** | **0/13** | 1 refused by grammar, not resolved |
| Recorded pilot development | **1/4** | **3/4** | **0/2** | Not sampled |
| Canonical sanity controls | **2/2** | **0/2** | Not sampled | 1 grammar admission; identity decision still required |

Three executor offline runs were byte-identical: **90 question-validator evaluations**.
That establishes deterministic replay, not model or end-to-end consistency.
**No unsafe admission by A was observed in these unsupported samples.** No
answer accuracy or runtime ambiguity-candidate completeness was newly tested.
The recorded pilot previously preserved both Brendan Griffin identities; that
is historical evidence, not a new resolver measurement.

All **13/13** deliberately incomplete new negative proposals pass schema,
scope/member consistency and exact-mention-presence checks; **0/13** pass A's
whole-question validation. Both recorded negative injections likewise pass the
necessary checks and fail A. Five deliberately incompatible field alterations
(target, absent name, member/catalogue scope, answer, excluded term) are rejected
**5/5** by necessary checks. Exact mention presence is **not exact RDF identity
grounding**, and these easy alteration probes are not semantic-verifier results.
The experiment demonstrates the omission gap, not that B would fill it.
The necessary-check passes are **guaranteed by construction**, not a measured
semantic-verifier failure rate. The small authored corpus is directional
coverage evidence, not a population estimate. A's generic refusal diagnostic
does not identify which semantic role failed. In particular, NEW-TC-21 does not
isolate exclusion handling: its otherwise unfamiliar clause also fails grammar.

**B reachability, unsafe admissions and incremental independent-verifier value:
NOT MEASURED**, not zero. No generalisation improvement is established.

Representative cases (full wording and per-case diagnostics retained):

| Case | Material intent | A result / significance |
|---|---|---|
| NEW-TC-05 | Passive: terms represented by records held for Micheál Martin | False refusal despite complete supported intent |
| NEW-TC-06 | Fronted terms in Brendan Howlin's service; asks their count | False refusal; not a missing capability |
| NEW-TC-21 | Count terms, **not membership records** | False refusal; approved measure contrast, not a term filter |
| NEW-TC-08/09/10/11 | Party/date/constituency/additional-person condition | Safe refusals; lossy typed proposal drops the condition |
| NEW-TC-12/13 | Change count to membership records / also return names | Safe refusals; target conflict and extra projection matter |
| NEW-TC-14/15 | Never served / exclude first term | Safe refusals; complement/exclusion cannot become positive service |
| NEW-TC-16/17 | “Unfiltered” label hides office filter / contextual date eligibility | Safe refusals; context labels do not cancel operative conditions |
| NEW-TC-19 | Include terms missing from recorded data | Safe refusal; no historical-completeness claim allowed |
| CONTROL-AMBIGUITY | Canonical count for Brendan Griffin | Grammar admits syntax only; must not choose a Member identity |

## A versus B

**A — deterministic admission:** full ordered-clause consumption, exact grounded
span, directed relationship parsing and comparison of every typed input. It
does not trust `supported=true`, confidence or a prose summary. Unknown modifiers,
extra conditions and unrecognised projections refuse. It is cheap, reproducible
and explainable within its bounded vocabulary. Nevertheless, correctness within
its grammar is not universal natural-language correctness; an incorrectly
specified grammar could still admit the wrong meaning. Supported language is
surface-bounded. The pilot's three correct typed Member interpretations were
refused, and the new diagnostic paraphrases remain unreachable. Adding their
wordings would be tuning, not transfer evidence.

**B — structured interpretation plus completeness verification:** expose all
material roles and unsupported obligations, check typed compatibility and exact
identity locally, and lower only accepted inputs through existing v2/Stage A.
The compiler can prove the plan matches its inputs, **not** that those inputs
exhaust the original question. A separate semantic check must find omitted or
altered relationships, polarity, time, exclusions and answer requirements. The
offline injections show why schema validity and a correctly constructed plan
cannot substitute for that check. See `protocol.md` for a bounded proposal.

| Completeness mechanism | Assessment |
|---|---|
| Same-call model self-check | Cheapest; useful diagnostics, but interpreter and checker share the same blind spots and framing. No independent evidence. |
| Fresh call, same model, sees proposed plan | More opportunity to detect mistakes; still candidate anchoring and correlated model errors. A separate call is not statistical independence. |
| Fresh-context same-model reconstruction + local comparison | Preferred experimental arm, blind to the first proposal, not statistically independent. Agreement is consistency evidence. Differing segmentation/attachment can increase false refusals; both calls can omit the same demand. |
| Different model family | Potential error diversity, not assured independence; unconfigured and unmeasured here. Not justified as mandatory infrastructure. |
| Hybrid | Retain deterministic type, grounding, inventory, compiler and fail-closed vetoes; add bounded source-grounded semantic verification only in shadow pending review. Known-risk lexical vetoes can help, but absence of flagged words cannot prove completeness. |

**Does an independent call materially improve reliability? Unknown.** It adds a
distinct opportunity to catch omissions, not a demonstrated benefit in this
experiment. Do not describe two agreeing model outputs as a completeness proof.

Specific weaknesses: shared omissions; attachment and negation scope mistakes;
misclassifying a condition as incidental context; source spans that are genuine
but incomplete; invented or ambiguous identity; conflating membership rows with
term identities; missing extra output; instruction-following attacks in the
question; correlated provider failures; noncompletion; and disagreement that
raises false refusals. Complete token coverage can still assign the wrong roles.
A verifier seeing only the extracted intent cannot check omitted question text.
Failing closed on reported uncertainty does not stop confidently shared errors.

## Handoff, cost and next gate

Recommended **design**, not implemented: original question + versioned inventory
→ bounded typed interpretation/obligation ledger; independently reconstruct from
the original question, blind to the first result → strict local role comparison,
capability checks and existing exact RDF resolution → existing `termCountIntent`
projection → existing `{member}` / `{}` lowering → existing canonical v2
construction, final validation and Stage A execution. No AI IRIs, SPARQL, new
graph relationships, executable operators or second canonical plan. Unsupported,
ambiguous, conflicting, missing, unknown, malformed or incomplete inputs execute
nothing. Preserve recorded-evidence qualifications, count identity and caps.

Relative cost: A adds no network calls. B1 needs one interpretation call; B2
needs two total, roughly doubling model-call/token budget, not necessarily dollar
cost. Blind calls can run concurrently (latency roughly their maximum); serial
verification adds latency roughly equal to its call. Current transport defaults
are 2,000 output tokens and 45-second timeout per call, not measured latency.
Pricing and input lengths must be recorded before a dollar estimate. Additional
schemas, span validation, role comparison, diagnostics, model-version pinning and
safe noncompletion handling are **medium complexity**: approximately 3–5 engineer
days for a shadow harness and fixtures, excluding safety qualification. This is a
planning estimate, not measured effort or approval for production work.

The semantic envelope could reuse operation-independent role checks for other
**existing** capabilities without a whole-question grammar per capability. Each
still needs an exact semantic adapter, capability restrictions and independent
evidence; cross-capability transfer is untested. The obligation comparison itself
could become a new hidden grammar unless kept typed and explicitly bounded.

**Smallest additional experiment:** after architectural review and provider
availability, freeze strict schemas/prompts **and a total role/obligation comparison
specification** (including materiality and segmentation rules) for these 21 questions, make three
repetitions of B1 and blind B2 (**126 calls**, no execution/retries), and test
forced omissions/alterations against the independent extraction. Compare safety,
false refusals, per-role fidelity, variability, tokens and latency separately;
any unsafe shadow admission blocks the preservation claim. No production
implementation, acceptance campaign or PR merge is authorised by this report.
The current protocol deliberately does not define that executable comparison;
completing and reviewing it is a prerequisite, not a live-run implementation detail.

## Reproduction and preservation

```sh
.venv/bin/python docs/reports/query-service/semantic-completeness-experiment/run_static.py \
  --output /tmp/opencode/semantic-completeness-new-output.json
.venv/bin/python -m pytest tests/test_nlq_term_count_intent.py \
  tests/test_nlq_composable_semantic_capability_discovery.py -q
```

Output paths must be new. `static-results.json` pins cases, script and six
authoritative source hashes. `verification.json` records focused checks, replay
parity and the baseline tracked-file integrity check: **209 tests passed**, three
byte-identical static runs, all **586 original tracked files unchanged**. Only this new report
directory is added; application, contracts, ontology, ETL, mappings, fixtures,
frozen implementation/evaluation evidence and pilot artifacts remain unchanged.
`review.md` records independent static reproduction, caveats and factual
corrections to the review; no experimental outcomes were tuned or replaced.
