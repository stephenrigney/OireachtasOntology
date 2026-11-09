# Query Service — Evaluate Semantic-Intent Verification Beyond Lexical Grammars

**Recommendation: REVISE, not adopt for production.** Structured interpretation
usually captured the supported meaning, and the separate verifier detected the
injected faults, but the complete verified gate achieved **0/8 reachability in
both repetitions**. This does not demonstrate generalisation with preserved
safeguards. Human architectural review is the next gate; stop implementation here.

Live follow-up to the preserved [static design study](../semantic-completeness-experiment/README.md).
This directory is experimental evidence only, not application implementation,
acceptance evidence or authorization to replace the complete-question guard.
PR #27 remains draft, NOT ACCEPTED and unmerged.

## Method and boundary

Baseline `da74faf`; executable v2 contract **2.29.0** remains authoritative.
All user-listed authorities were reviewed, including proposed architecture on
`origin/master` at `a74883b`, without merging it. No frozen PR acceptance case
files were inspected or replayed; recorded pilot questions remain development.

Twenty questions were independently authored from the contract and two names,
without tools, implementation, prior questions/reports or model outputs: eight
supported, ten unsupported, two ambiguous. Novelty against unread corpora cannot
be guaranteed. `cases.json`, `protocol.md`, schemas/prompts in `run.py`, grounding
and scorer were committed before calls; no post-outcome tuning occurred.

- **A:** unchanged whole-question grammar given oracle Member mentions. Parse
  failures are directly measured; admission would also require exact grounding.
- **B1:** structured interpretation plus same-call nine-role self-audit, checked
  for schema/types, exact spans, capability compatibility, identity and existing
  canonical-plan construction. An audit assertion is not completeness proof.
- **B2:** B1 plus a separate candidate-visible verifier given original question
  and interpretation, not the self-audit. All nine role checks must be preserved;
  supplied quotes must be source-exact. This is not blind reconstruction,
  a different-model test or statistical independence.
- **Injections:** each negative question also receives one deliberately lossy,
  well-typed unfiltered count candidate. Assuming an all-clear self-audit, the
  deterministic gate alone supplies its B1 result; no interpreter/self-check
  call is made. These are simulated faults, not observed B1 errors.

Two repetitions, no retries, concurrency ≤2, plus a recorded-language two-schema
transport preflight. Only two read-only entity queries occurred: existing exact
resolution found one Micheál Martin identity and both Brendan Griffin identities
(`grounding.json`). Models receive no IRIs. Existing Stage A builders construct
and validate plans but never execute them; no `/ask`, count or factual-answer
accuracy was tested. **B admissions are shadow-only:** the real grammar remains
mandatory and unchanged. A valid plan does not prove complete original intent.

## Reproduction

```sh
.venv/bin/python docs/reports/query-service/semantic-completeness-live-study/run.py selftest
.venv/bin/python docs/reports/query-service/semantic-completeness-live-study/score.py \
  --output /tmp/opencode/semantic-live-summary-new.json
```

Live reproduction requires a configured service process belonging to this exact
worktree (`run.py run --provider-pid PID --output NEW_DIRECTORY`), incurs provider
cost, and must not overwrite evidence. Credentials are used only in memory and
never recorded. Prompts/schema and every sanitized provider payload, structured
decision, failure and elapsed time are retained. No credential store was searched
or changed. Existing static-study, pilot and frozen PR evidence are unchanged.

## Measured results

Protocol/source/cases freeze: **`1c72e7c`**, before the first call on 2026-11-09.
Requested and returned model: **`gpt-6-luna`**, configured Responses-compatible
OpenCode provider. Strict JSON schema, 3,000 output-token cap, 60s timeout,
temperature/top-p/reasoning/seed omitted in requests; payloads reported temperature
**1**, top-p **0.98**, reasoning effort **medium**. No seed was returned. There
were **102/102 HTTP 200 completed, schema-valid responses**, no retries or
noncompletion: 40 interpretations, 40 natural-candidate verifications, 20 injected
verifications, two preflight calls. These are not independent statistical trials.

| Arm | Supported admitted, r1 / r2 | False refusals, r1 / r2 | Unsafe unsupported admissions, r1 / r2 |
|---|---|---|---|
| A: existing grammar | **0/8 / 0/8** | **8/8 / 8/8** | **0/10 / 0/10** |
| B1: typed interpretation + self-audit | **2/8 / 0/8** | **6/8 / 8/8** | **0/10 / 0/10** |
| B2: B1 + separate verifier | **0/8 / 0/8** | **8/8 / 8/8** | **0/10 / 0/10** |

Unsafe ambiguous-identity selection: **0/2 in each repetition for every arm**.
The deterministic grounding gate retained both Brendan Griffin identities in all
four B interpretations. Final B1 clarified only HC19/r2 and otherwise refused;
B2 refused all four. Safe refusal is not successful clarification or a count.
Two recorded-language grammar sanity controls (Member and catalogue) still
parsed; they are development checks, excluded from the table.

**Fault injection, separately:** all **10/10** deliberately incomplete candidates
per repetition passed necessary checks and existing-plan construction by design.
B2 rejected **10/10 each time**, with **0/10 injected escapes**. Importantly,
all **20/20** verifier outputs explicitly flagged a material omission/alteration,
not just malformed quote evidence. This demonstrates useful fault-detection
diagnostics in this sample, not an observed B1 unsafe-admission rate or proof
that an independent call improves real-world reliability.

### Fidelity, failure attribution and variability

`summary.json` is the frozen-gate score; `diagnostics.json`/`diagnose.py` are
post-run attribution only, **not relaxed-gate credit**. No checks were changed.

- **15/16** supported proposals passed deterministic compatibility and existing
  plan construction. All 14 Member proposals preserved operation, exact Member,
  directed service relationship, unfiltered scope, distinct term aggregation and
  count-only answer, including HC05's measure contrast. HC08/r1 redundantly put
  the catalogue in `entities`, incompatible with the catalogue gate; r2 did not.
  These necessary-check passes are not complete-intent admission or factual answers.
- Self-audits called **40/40** natural proposals complete. **13/16** supported
  self-audits failed exact-quote provenance (added quotation marks, ellipses or
  prose such as “No temporal restriction is stated”). This caused 13 supported
  refusals beyond HC08/r1's compatibility refusal. No normalization/repair was
  applied. Even the preflight's successful transport did not establish semantic
  admission or quote compliance.
- **All 60** verifier outputs failed at least one exact-quote check. B2's complete
  refusal therefore cannot establish effective safety/generalisation. Separately,
  its semantic checks accepted **15/16** supported interpretations; HC01/r1
  falsely alleged the encoded recorded-local scope omitted a local-only condition.
  That semantic disagreement also vetoed one of B1's two admitted positives.
- On natural unsupported questions, the verifier flagged eight interpretations
  already rejected by compatibility. HC17 twice retained only a DailTerm target
  and generic extra `other` output for the requested election-win measure; the
  self-audit said complete, while verification challenged the missing measure.
  Deterministic extra-output checks had already prevented admission. No incremental
  natural unsafe-admission reduction was observed.
- Exact structured interpretations repeated identically for **13/20** questions.
  B1 decisions were stable **17/20**, changing for HC01, HC03 and HC19; A and B2
  were stable **20/20**, but universal refusal is not useful reliability. Injection
  reject decisions were stable **10/10**; discrepancy role/status assignments varied.

Representative cases (all full wordings and decisions are retained):

| Cases | Intent / observed issue |
|---|---|
| HC01/02 | Local-record fronting / passive membership-to-term path: correct fields, grammar refuses; verifier adds a false local-scope complaint for HC01/r1 |
| HC03/04/06 | Member-last with “not a list” / anaphora / explicit deduplication: supported, but quote compliance blocks repeatable admission |
| HC05 vs HC14 | “not membership records” is a measure contrast; excluding the 33rd Dáil changes selection and must refuse |
| HC09–13 | Party/date/constituency/second-person/selected-term conditions: all refuse; injected omissions explicitly detected |
| HC15–17 | Sponsorship instead of membership / extra IRI and start date / election-win target: not a simple term count; all refuse |
| HC18–20 | Contextual office exclusion is material; Brendan Griffin remains ambiguous, never selected by the model |

### Cost and latency

Interpretation calls: median **6.06s**, p95 **9.71s**. Verification calls including
injections: median **4.98s**, p95 **11.15s**. Natural sequential two-call pairs:
median **10.87s**, range **7.44–28.33s**. A adds no network call; B1 requires one;
B2 requires two and adds verifier latency plus failure/maintenance surface.

All 102 calls used **104,446 input / 65,990 output tokens**. The provider reported
44,958 cached interpretation input tokens; neither cost nor timing should be
extrapolated to uncached production traffic. Reported `usage.cost` totals
**0.03943759** (payload does not label currency; not independently reconciled
billing). Budget by calls and tokens, not an assumed public price or fixed dollar
cost. Provider parameters, usage and per-call timing remain in raw records.

## Architectural assessment

A offers cheap, reproducible complete ordered-clause consumption and directed
role comparison: unknown filters, negation and outputs refuse. Its grammar can
still be incorrectly specified, and correct unfamiliar wording remains unreachable.
B separates executable compatibility from original-question fidelity; a compiler
establishes the former, not the latter. Neither genuine substrings, model
confidence, support assertions nor nine-role all-clear declarations prove coverage.

Same-call audits are cheapest but share interpreter blind spots. Separate calls
can challenge drafts but retain candidate anchoring and shared model errors.
Blind reconstruction reduces anchoring but needs precise attachment/polarity/
segmentation comparison; different-model verification might diversify errors,
not certify independence. Neither is tested here. Prefer a **hybrid** design:
model agreement never overrides deterministic identity, type, capability,
evidence or compiler vetoes. Replacing the grammar changes assurance and requires
architectural review, not a claim that probabilistic checks preserve its proof.

Remaining hazards: confidently shared omissions, negation/context attachment,
measure/selection confusion, opaque `other` obligations, incomplete genuine
quotes, identity ambiguity, provider drift, prompt injection and noncompletion.
This small sample does not test historical-completeness demands or exhaust these
risks. Fail-closed reported uncertainty cannot stop confidently shared errors.

Recommended handoff: original question + versioned inventory → bounded typed
interpretation/obligations → deterministic compatibility/exact identity plus
bounded semantic discrepancy checks → existing `termCountIntent` and `{member}`/
`{}` lowering → **existing canonical v2 validators/compiler**. Never strip unknown
obligations to fit. No AI IRIs/SPARQL/graph relationships, new capabilities or
second executable plan. Preserve identity aggregation, caps, unavailable/zero
distinction and coverage qualifications; real grammar authority remains unchanged.

Shared role checks could serve other existing capabilities without new
whole-question grammars, but each needs an exact adapter and fresh evidence;
cross-capability generalisation is unmeasured. Shadow implementation is medium
complexity (planning estimate **3–5 engineer days**, excluding unestimated
production safety qualification).

## Recommendation, remaining experiment and preservation

**REVISE:** retain typed interpretation and deterministic lowering as the useful
handoff, but do not adopt this completeness gate. A separate verifier adds
**diagnostic** value (explicitly catches injected faults and HC17's incomplete
measure) while adding false refusal, cost and latency. It has not demonstrated
material improvement in final admission reliability: no unsafe natural B1 result
needed rescue, B2 admits nothing, and all verifier evidence violates provenance.
Do not reinterpret semantic all-clear counts as successful admissions, remove
quote checks after observing them, or claim that this study generalises.

Smallest warranted next step, **only after human architectural review**: an
isolated shadow-harness revision, not application integration. Freeze a total
typed obligation/binding/polarity comparison and source-offset evidence schema
that separates quotes from explanations; offsets still do not prove completeness.
Test B1 plus blind same-model reconstruction on
**12 newly independently authored questions, three repetitions** (six supported,
six adversarial restrictions/extra outputs, including contextual negation,
historical-completeness demands and prompt injection). Reuse each blind extraction
against predefined corrupted candidates without more model calls; two calls per
case/repetition gives **72 calls**, no execution or retries. The current observed
questions may be labelled development diagnostics only, never fresh evidence.
This study's direct-verifier results are a development comparator, not a paired
fresh direct-versus-blind measurement; adding that third call would cost 108 calls.
Do not add another capability or tune a grammar. Different-model diversity is
optional later research, not a mandatory unmeasured infrastructure change.

Verification: **209 existing tests passed**, 16 shadow-gate assertions passed,
Python compilation and `git diff --check` passed. All **593 pre-existing tracked
files** match baseline bytes, including the static study, pilot, frozen PR
implementation/evaluation evidence and authoritative contracts. The application,
ontology/ETL/mappings, fixtures and Fuseki data were not changed. No production
acceptance campaign, service restart, merge or production implementation occurred.
`verification.json` and `review.md` record scope checks and independent review.
**PR #27 remains OPEN, draft, unmerged and NOT ACCEPTED. Stop at architectural
review.**
