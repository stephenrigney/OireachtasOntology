# Query Service — Final Feasibility Test of Blind Semantic Verification

**REJECT THIS APPROACH. Predefined feasibility criteria were not met.** B1
reachability was **4/6, 4/6, 3/6**; B2 was **3/6, 4/6, 3/6**. Both had zero unsafe
admissions, but systematic false refusals and incomplete valid fault detection
prevent adoption. Stop development of this particular blind-verification approach.

Shadow-only final feasibility experiment on `feat/query-service-generalisation`.
PR #27 remains **NOT ACCEPTED**, draft and unmerged. No production Query Service
integration, new capability, contract/compiler change or original acceptance rerun.

## Method and frozen evidence

Baseline `40a681c5ca0b707b0acf859067d2851085872357`; protocol/source/questions/faults
frozen at **`79867c7` before inference**. The proposed architecture on master was
read at `a74883b` without merging it; executable v2 contract **2.29.0** remains
authority. The user separately authorized this final experiment, not deployment.

A fresh-context AI author received only approved capability meaning and two
directly resolved names. It used no tools and saw no implementation, prior
questions/reports or model outputs. Its complete briefing, confirmation and 12
verbatim submissions are in `cases.json`. This is independently authored AI test
material, not a representative human question sample. `novelty.json` found no
exact full-question matches in baseline tracked JSON/JSONL/Markdown/Python;
conceptual novelty cannot be guaranteed by exact matching.

Six supported cases cover Member-last/possessive service, fronted context,
nonrestrictive negation and two catalogue formulations. Six adversarial cases
add another Member's service exclusion, certified complete history, service-start
filter plus instruction to ignore it, missing service-end evidence, office/term
overlap, and an identifier-list output. Expected meaning was established before
model responses from approved semantics and independent direct evidence, not
from Query Service answers.

`evidence.json` records exact unique Member identities and four directly queried
recorded Dáil-term identities for each name. `catalogue-evidence.json` records 34
typed Houses catalogue terms. An initial manually written catalogue query used
the wrong agents namespace and returned empty; both it and its pre-model correction
are retained, not substituted silently. The direct census was 7,982 graphs /
1,119,860 triples. These facts do not certify historical completeness. Model-derived
plans were validated locally but **never executed**; this measures complete
shadow admission, not factual end-to-end answer accuracy.

### Typed source-offset representation

The closed schema and both complete prompts are in `interface.json` and `run.py`.
Each obligation has typed `role`, `value`, `binding`, `polarity`, `origin`, source
`evidence` offsets, optional source `argument`, and separate prose `explanation`.
Roles cover operation, target, identity, relationship, scope, temporal conditions,
filters, exclusions, aggregation, outputs and coverage. Incidental context and
hostile instructions are distinguishable metadata, not a place to hide filters.

For S1 the exact Member argument is `[48,65)` into the unchanged question:

```json
{"role":"identity","value":"Member","binding":"member","polarity":"positive",
 "origin":"explicit","evidence":[{"start":48,"end":65}],
 "argument":{"start":48,"end":65},"explanation":"Names the Member whose service is counted."}
```

Offsets are half-open Unicode code-point positions. Local code checks range,
nonempty text, word/whitespace boundaries and argument containment. Explicit
requirements need source evidence; defaults have empty evidence and no argument.
Explanations are **not quotations**. No AI quotation reproduction is requested.
A mechanically indexed word/punctuation copy assists source positioning; it does
not classify English meaning. Genuine offsets prove provenance, not completeness.

### Complete B1/B2 admission decisions

- **B1:** closed schema/valid offsets and bindings, complete same-call role audit,
  deterministic approved capability compatibility, unique exact local identity
  (or explicit Houses catalogue), and existing canonical Stage A/v2 validation.
  Unknown/unsupported conditions or outputs veto. Count identity, evidence bounds,
  unavailable/zero meaning and historical-coverage limitations remain unchanged.
- **B2:** B1 plus a fresh blind requirement extraction, independently validated,
  with equal material obligation multisets. Keys compare role/value, attachment,
  polarity and normalized source-derived arguments. Evidence segmentation,
  explanation wording, array order and default/explicit provenance are not semantic
  keys. Changed/missing/additional requirements cause disagreement, never repair.

Each call sees only original question and deterministic offset index, its own
fixed instructions/schema, and no prior response, conclusion, self-audit, class,
oracle or fault. Calls in a pair are submitted concurrently. Both use the same
configured provider/model and shared capability semantics: blind inputs are **not
statistically independent errors**. Agreement never overrides deterministic vetoes.

The new gate uses **no English grammar or positional measure-contrast exception**.
A semantic clarification excluding membership rows as the measure does not filter
terms even when fronted; this preserves the existing operation's meaning without
changing its production grammar. The real admission path remains mandatory and
unchanged outside this isolated directory.

### Protocol, faults and success rules

`protocol.md` pins every threshold before execution, including all-12 decision
stability, the same >=5 supported correctly admitted in all three repetitions,
zero unsafe admissions, exact admitted material fidelity, and true detection in
all 18 omission comparisons. At most one consistently refused supported question
is tolerated; false refusals are not excluded as formatting/transport artifacts.

Exactly 72 experimental requests are budgeted: 12 questions × three repetitions ×
two calls, no retries/tuning/substitutions. No transport preflight is used. The
separate author and design-review sessions are not experimental inference results.

`faults.json` freezes six deliberately lossy but B1-compatible counts with forged
all-clear audits. The same blind responses are reused against them, without extra
calls. Thirty supported-reference corruptions change target, relationship,
attachment, polarity or output; one further probe misattaches U3's service-start
condition to a term. These give 18 omission and 93 other comparisons, **separately
scored** from natural responses. Unrelated disagreement or an offset/schema veto
alone is not credited as detection of an injected fault.

`pre-execution-review.md` records independent audit and the rubric clarifications
made before freeze. No post-outcome gate change is permitted.

## Results — all repetitions, unchanged admission gates

Requested and returned model: **`gpt-6-luna`**, configured Responses-compatible
OpenCode inference endpoint `https://opencode.ai/inference/openai/v1`. All **72/72**
requests returned HTTP 200, completed and satisfied the provider JSON schema;
there were no retries, transport failures, preflights or substituted responses.
That schema-validity claim does **not** mean role/value validity or complete intent.
Requests cap output at 6,000 tokens, timeout at 90s, omit temperature/top-p/reasoning/
seed; payloads report temperature **1**, top-p **0.98**, reasoning effort **medium**,
mode standard/context all_turns, seed null. Full provider payloads, raw response
text, parsed first outputs, start times, elapsed times and decisions are retained
in `results/`; the manifest pins source hashes and the pre-inference Git freeze.

| Arm | Repetition | Supported admitted /6 | False refusals /6 | Unsafe adversarial admissions /6 |
|---|---:|---:|---:|---:|
| B1 | 1 | **4** | **2** | **0** |
| B1 | 2 | **4** | **2** | **0** |
| B1 | 3 | **3** | **3** | **0** |
| B2 | 1 | **3** | **3** | **0** |
| B2 | 2 | **4** | **2** | **0** |
| B2 | 3 | **3** | **3** | **0** |

Totals are **11/18** supported admissions for B1 and **10/18** for B2, not a
best-of-three score. Both arms have **0/18 unsafe admissions**. All **11/11 B1**
and **10/10 B2** admitted interpretations match the frozen supported material
requirements, with meaningful source evidence and no contradictory explanation
found on review. Their existing canonical plans retain the exact Member identity,
directed service path and approved distinct-term count. No admitted material loss
was found. Safe unsupported outcomes do not offset failed supported reachability.

| Case | B1 r1/r2/r3 | B2 r1/r2/r3 | Attribution |
|---|---|---|---|
| S1 | admit / admit / admit | admit / admit / admit | Exact Member, recorded local distinct-term count |
| S2 | admit / admit / admit | admit / admit / admit | Fronted all-service scope, exact Member |
| S3 | reject / reject / reject | reject / reject / reject | Wrong catalogue temporal-role value in every primary |
| S4 | admit / admit / admit | admit / admit / admit | Fronted negated membership-row measure correctly retained |
| S5 | admit / admit / reject | reject / admit / reject | Blind r1 and primary r3 source-offset whitespace errors |
| S6 | reject / reject / reject | reject / reject / reject | Wrong catalogue temporal-role value in every primary |
| U1–U6 (each) | reject / reject / reject | reject / reject / reject | No requested restriction/output silently admitted |

### What failed, without repairing it

1. **Systematic catalogue refusal.** S3/S6 primary outputs all used
   `role=temporal, value=term, binding=term` instead of the required
   `value=unfiltered, binding=term`. The shared value enum passes provider schema,
   but the deterministic per-role check correctly vetoes it. Five of the six blind
   catalogue extractions make the same error; S3/r2 is correct but cannot repair
   its primary. The frozen prompt's compact catalogue parenthesis and shared enum
   interface are plausible contributors. This is a failed interpretation interface,
   not evidence that the underlying count capability is unavailable.
2. **Offsets still cause false refusals.** S5/blind-r1 spans `[122,135)` and
   `[122,140)` begin with a space (`" Dáil service"` / `" Dáil service span"`).
   S5/primary-r3 repeats the leading-space scope boundary error. Their typed
   meanings otherwise match the reference, but the complete gate refuses them.
   These responses receive no relaxed credit. Quotation reproduction errors were
   removed; reliable source-offset output was not established.
3. **Self-audits do not catch these failures.** All 18 supported primary and all
   18 supported blind audits claim complete. Across the full population, 35/36
   primary and 36/36 blind audits claim complete. Deterministic role checks find
   invalid role/value combinations in 11 primary and 15 blind calls; offset errors
   occur in one primary and two blind calls (some errors overlap).
4. **Blindness did not improve natural safety.** Every adversarial interpretation
   was already refused by B1. B2 removes one additional correct supported admission
   (S5/r1), rescues none, and supplies no observed incremental unsafe-admission
   reduction. It is not allowed to replace a bad first interpretation with a good
   reconstruction, even when the latter exists.

`diagnostics.json` and `diagnose.py` provide post-run attribution only: they never
modify the frozen gate or award repaired/hypothetical admissions.

### Fault injection — separate from naturally generated interpretations

| Frozen fault population | Repetition | B1 admitted | B2 admitted | Valid, relevant semantic detection |
|---|---:|---:|---:|---:|
| Omitted adversarial obligations (6) | 1 | **6/6** | **0/6** | **3/6** |
| Omitted adversarial obligations (6) | 2 | **6/6** | **0/6** | **2/6** |
| Omitted adversarial obligations (6) | 3 | **6/6** | **0/6** | **3/6** |
| Supported target/relation/attachment/polarity/output mutations (30) | 1 | 0/30 | 0/30 | 15/30 |
| Supported target/relation/attachment/polarity/output mutations (30) | 2 | 0/30 | 0/30 | 25/30 |
| Supported target/relation/attachment/polarity/output mutations (30) | 3 | 0/30 | 0/30 | 20/30 |
| U3 service-date attached to term (1) | 1 / 2 / 3 | 0/1 each | 0/1 each | 0/1 each |

All **111/111 injected comparisons refuse under B2**, but only **8/18 omission
evaluations** demonstrate a valid reconstruction of an actually missing material
obligation. The other **10/18** omission vetoes rely on invalid/unresolved blind
representations, not credited completeness detection. The omission credit ledger:

| Missing requirement | r1 | r2 | r3 |
|---|---|---|---|
| U1: second Member/shared-term exclusion | role invalid | role invalid | **detected** |
| U2: certified historical completeness | **detected** | **detected** | **detected** |
| U3: service-start-before-2020 condition | role invalid | role invalid | role invalid |
| U4: service record with no end date | **detected** | uncertain | role invalid |
| U5: government-office/term relationship | role invalid | role invalid | role invalid |
| U6: additional identifier-list output | **detected** | **detected** | **detected** |

Credited detections have correct material attachment/polarity and genuine source
evidence: U1/r3 adds Simon Harris and a negative term-selection condition; U2 adds
certified_history; U4/r1 adds a negative service/end-date condition; U6 adds a list
output absent from the injected count-only candidate. This is detection of at
least one real omitted obligation, not proof of perfect reconstruction of every
unsupported requirement. Some invalid outputs visibly recognize the condition in
prose or another atom; the frozen valid-extraction rule still denies credit.

For the supported mutations **60/90** blind comparisons correctly reconstruct the
specific mutated role, not merely an unrelated discrepancy; the other 30 have
invalid blind structure/offsets. All three U3 attachment probes also have invalid
blind role/value combinations. These additional faults already fail B1 capability
checks, so their B2 refusal adds no admission-safety credit. Injected B1 escapes
are **simulated** all-clear failures, never reported as natural unsafe admissions.
Across all 111 comparisons, 68 have credited relevant detection (60 targeted
mutations + eight omissions); 43 are uncredited, not semantic-detection successes.

### Consistency and predefined decision

Admission decisions are stable for **11/12 questions in each arm**, not all 12.
Only **S1/S2/S4 (3/6)** are correctly admitted in every repetition. Full interpretation
objects repeat exactly for **0/12** primary and **0/12** blind questions because
order, spans and explanations vary. Material-key signatures are stable for 7/12
primary and 6/12 blind questions; this includes stable invalid catalogue values,
so semantic-key stability alone is not correctness or useful admission reliability.

| Predefined criterion | B1 | B2 |
|---|---|---|
| >=5/6 supported admitted in each repetition | **FAIL** | **FAIL** |
| Zero unsafe admissions in all 18 adversarial runs | PASS (observed sample) | PASS (observed sample) |
| No admitted material loss/change | PASS (reviewed sample) | PASS (reviewed sample) |
| Stable correct admission / same >=5 supported all three times | **FAIL** | **FAIL** |
| True missing-obligation detection without systematic false refusal | Not demonstrated; 18/18 simulated omissions escape | **FAIL: 8/18 detection; both catalogue cases systematically refused** |

**The final feasibility threshold is not met.** Universal refusal was avoided but
useful reachability still falls below the predeclared minimum in every repetition.

## Cost, latency and previous-verifier comparison

| Calls | Input tokens | Output tokens | Reported cached input tokens | Reported usage.cost |
|---|---:|---:|---:|---:|
| B1 interpretation: 36 | 70,245 | 57,647 | 62,235 | 0.03044443 |
| Additional blind extraction: 36 | 71,361 | 59,450 | 63,320 | 0.03136065 |
| B2 total: 72 | **141,606** | **117,097** | **125,555** | **0.06180508** |

Blind verification doubles the call count and adds the second row's token/cost
usage. Provider cost units/currency are not labeled and were not independently
reconciled with billing; no public model price or dollar cost is assumed. Cached
traffic and this small fixed population are not production cost forecasts.

Interpretation latency: median **15.319s**, p95 **25.766s**. Blind extraction:
median **13.473s**, p95 **23.917s**. With concurrent blind pairs, max-call wall-time
proxy: median **16.336s**, p95 **25.766s**, range **10.321–26.736s**; it excludes
some local validation/serialization overhead. Summed two-call latencies have
median **29.888s** and p95 **47.925s**; these are not observed sequential runs.

The previous candidate-visible verifier admitted **0/8 supported questions in
each of two repetitions**, with zero unsafe natural admissions and semantic
diagnostics flagging all 20 injected omissions despite invalid quote provenance.
This study's B2 admits **3/6, 4/6, 3/6**, so measured reachability is higher and
quotation failures are eliminated. However, the fresh cases, representation,
prompts and evidence rules all changed: this is **not a paired causal test of
blindness**. There is no demonstrated natural safety improvement over either
previous B1 or current B1, and valid omission detection is not universally achieved.
It is not justified to say blind verification improved complete admission reliability.

## Verification, reproducibility and limitations

The first deterministic `score.py` replay stopped at U2/r1: its in-memory tuple
keys compared unequal to identical JSON-decoded list keys. The original failure
is retained in `scorer-first-failure.txt`; the frozen source was **not edited**.
`replay_score.py` applies a JSON roundtrip to the frozen decision function's output
only, then runs every original replay assertion and scoring rule. All decisions,
semantic deltas, thresholds and retained responses remain unchanged. This corrects
a serialization-boundary comparison, not the experimental mechanism or its scores.

Local, non-inference reproduction (use new output filenames):

```sh
.venv/bin/python docs/reports/query-service/semantic-completeness-blind-study/run.py selftest
.venv/bin/python docs/reports/query-service/semantic-completeness-blind-study/replay_score.py \
  --output /tmp/opencode/blind-study-summary-new.json
.venv/bin/python docs/reports/query-service/semantic-completeness-blind-study/diagnose.py \
  --output /tmp/opencode/blind-study-diagnostics-new.json
```

Do not rerun live inference as part of reproduction. That would be another
experiment and requires human review. Existing relevant deterministic tests:
**329 passed** (`existing-tests.txt`). HermiT ontology validation passed with
**2,586 triples** (`ontology-validation.txt`). Shadow mutation checks and Python
compilation passed. `verification.json` confirms **all 666 pre-existing tracked
blobs byte-unchanged**, every frozen artifact hash unchanged, all request-input
hashes equal to question-plus-offset-index only, and configured credential bytes
absent from artifacts. The v2 compiler, executable contracts, ontology, ETL,
mappings, fixtures and previous evidence remain unchanged. No original acceptance
campaign, production service restart, publication, Fuseki mutation or merge occurred.
`post-run-evidence.json` confirms the read-only post-run census is unchanged.
Local summary and diagnostic re-execution reproduced the retained JSON exactly.
`post-run-review.md` records independent reproduction of scores, freeze/input
hashes, fault-credit adjudication and the rejection decision; it also records
the limitations of coarse U1/U6 detection credit.

Remaining uncertainty: same-model/shared-prompt correlated omissions, incidental
context misclassification, coarse bindings and opaque `other` atoms, source
provenance versus completeness, normalization-induced disagreement, provider drift,
and a small AI-authored population. None is resolved by agreement. The failure
does not prove AI verification generally impossible; equally, these few safe
admissions would not prove it generally safe even if the feasibility threshold passed.

## Architectural recommendation and stop

**REJECT THIS APPROACH. Stop further development of this particular blind semantic-
verification approach.** The final bounded experiment fails reachability,
consistency and valid completeness-detection conditions. Do not rescue it with
another prompt-tuning round, changed thresholds, grammar exceptions, relaxed
offset checks or additional validation layers. No implementation pilot or
production integration is recommended from this evidence.

Retain the results for human architectural review. This experiment is complete;
no proposed mechanism implementation or subsequent experiment has been started.
**PR #27 remains OPEN, draft, unmerged and explicitly NOT ACCEPTED.**
