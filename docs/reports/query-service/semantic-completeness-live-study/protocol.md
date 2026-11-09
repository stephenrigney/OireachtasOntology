# Frozen live design-study protocol

Baseline `da74faf572651882a16c404413a86857658e871a`; contract 2.29.0.
Read proposed architecture from `origin/master` at
`a74883bc51cb8e14dedb58d0fef8f9e01a3d06e8`, without merging it. Local
`master` predates that document. Executable contracts retain authority.

## Boundary and hypotheses

Read-only interpretation experiment, not implementation or acceptance. No
`/ask`, executor queries, data changes, new executable representation, or grammar
changes. Only new files in this directory. Exact grounding uses read-only local
entity lookup, then existing Stage A plan construction/validation without query
execution. New interpretation objects are disposable audit inputs, not plans.

Compare A, the existing complete grammar (given the oracle Member mention, a
best-case admission ceiling), B1, structured interpretation with same-call
self-audit, and B2, B1 plus a separate stateless semantic-verifier call. Both
model stages use the configured provider/model; a separate call is NOT a
different model or statistical independence. Do not claim different-model value.

Eight positive, ten unsupported, two ambiguity questions independently authored
from the contract. Freeze cases, scripts, prompts, schemas and scoring before
provider calls. Two full repetitions, no retries or prompt tuning. At most two
concurrent requests. Keep every first/repeated result, transport failure,
latency and available usage. No acceptance-set execution or tuning. Existing
pilot transfer evidence is development only, not relabelled fresh.

One recorded-language question preflights both schemas (two additional calls,
excluded from scores). A transport/schema error stops the study, with its record
preserved; no silent repair. Total budget: 102 provider calls. Output cap 3,000
tokens, timeout 60s, temperature/seed/reasoning omitted (provider defaults).
This is a separate live follow-up to the existing static-only
`semantic-completeness-experiment/`; none of that study's artifacts are replaced.
Its blind-reconstruction proposal is not tested here: this narrower executable
study tests its candidate-visible direct-verifier alternative and explicitly
retains the anchoring limitation.

All ten negative questions additionally receive a deliberately broken candidate:
the same well-typed unfiltered Member term-count interpretation with an all-clear
self-audit. This omits filters/outputs/targets, or alters the requested relation.
Two verifier repetitions each (20 requests). These are fault injections, NOT
observed interpreter errors. This prevents flawless primary interpretation from
making verifier safety appear established without challenge. Same-call audit is
not rerun on injections: its forged all-clear simulates correlated failure.

B1 requires closed schema, exact source spans for declared evidence/entities,
one permitted relationship, no temporal/selection/exclusion filters, exactly one
count target/output, exact unique local identity, existing canonical-plan
construction and all nine structured self-audit checks preserved. B2 also
requires all nine verifier checks preserved. A complete verdict, confidence,
support assertion or prose summary alone never suffices. Evidence substring
checks prove provenance, NOT semantic completeness. This protocol does not add
a purported deterministic proof that all original intent was captured.

## Scoring and stopping

Report reachability /8, false refusals /8, unsafe admission /10 and unsafe
identity selection /2 separately, per repetition. Clarification of duplicate
names is safe but not a count. Distinguish plan-boundary reachability from
end-to-end factual answers: no count execution or factual acceptance credit.
Report injection escapes separately /10 per repetition. Track decision and
structured-interpretation stability. Cost: calls, latency, tokens if available;
do not invent monetary prices. Errors/uncertainty fail closed, do not retry.

Before any live request, local tests check gate rejection of type, identity,
relationship, temporal, filter and projection mutations. Stop if a real compiler
or policy change is needed; shadow results cannot authorize production admission.
Afterward inspect only this study's results; preserve all previous artifacts.
Verify repository diff scope and focused existing term-count tests; no broad
acceptance campaign. Human architectural review remains the next gate.
