# Query Service — Generalise Semantic Dispatch and Query Interpretation

## Scope and baseline

Campaign branch: `feat/query-service-generalisation`, dedicated worktree
`query-service-user-coverage`, based on integrated `master` **df35d44**. The
initial working tree was clean; local and remote `master` matched. The existing
four-role harness and permissions were reviewed and left unchanged. No branch
switch, worktree creation, ontology/mapping/ETL/source-fixture change, dataset
reload, container operation, or Fuseki mutation was performed.

The read-only local evaluation endpoint is `http://localhost:3030/houses/query`;
the owned actual-planner `/ask` service is loopback port **8001**, rooted in this
worktree. Planner: `gpt-6-luna`, Responses-compatible OpenCode inference endpoint.
Reference date: **2026-11-06**. Initial independent census: **7,982 graphs,
1,119,860 triples**, matching the published evaluation. Presence and this census
do not certify complete or authoritative historical evidence.

| Development population | Published baseline | Fresh pre-remediation replay |
|---|---:|---:|
| Published 60: PASS / PARTIAL / FAIL / BLOCKED | 31 / 1 / 26 / 2 | 32 / 1 / 25 / 2 |
| Supported factual answers (frozen denominator 48) | 22/48 (45.8%) | 23/48 (47.9%) |
| Contract-admissible sensitivity (45) | 22/45 | 23/45 |
| Original 26: PASS / PARTIAL / FAIL / BLOCKED | 16 / 3 / 7 / 0 | 14 / 3 / 9 / 0 |
| Original 16 previously passing controls | 16/16 | 14/16 |

The fresh replay sent all **86** questions verbatim, one request per case, at
most two concurrently. H09 answered where its published first run failed.
R18 omitted its named participant; R24 omitted an independent anchor edge.
Both failed validation before answering. These baseline differences demonstrate
planner variability, not factual regressions attributable to remediation.
The pre-remediation replay used the already-running, non-reload service; its
loaded interpreter was not independently source-hash pinned. Final replays use
an explicitly refreshed owned service and recorded candidate commits.

Both published sets are **development material**, not independent acceptance.
Frozen questions/oracles and the 48-case denominator remain unchanged, including
H21/H22/H44's documented support-admissibility caveats. Their historical
date-to-roster and office-anchor-plus-term shapes are not newly authorized.

## Development evidence and scoring

`tools/collect-query-dispatch-development.py` validates the published freeze,
extracts all 26 original verbatim questions and checks the 16 frozen control
questions for parity. It retains complete rendered tables, diagnostic plans,
HTTP outcomes, timing and provenance without credentials. Output directories
must be new. `tools/score-query-dispatch-development.py` reuses the published
table checks and adds exact checks for previously unanswered seat, calendar,
party-catalogue and current-office outputs. It reproduces the published baseline.

Original factual requests that still require clarification or unavailable
capabilities remain PARTIAL/FAIL as originally defined; safe refusal is not a
factual pass. Machine table checks never establish full-intent preservation on
their own: plan scopes, qualifications and candidate boundaries require review.
Partial office evidence is not promoted to complete-career credit.

All **50** published factual evidence queries and both independent evidence
guard queries were rerun directly against the read-only endpoint during the
campaign; all **52** returned unchanged value/identity sets. No expected answer
was obtained from the Query Service itself.

The same 52 direct queries were repeated during final integration and remained
unchanged. A separate direct identity check for original control R18 also pins
the exact Member/constituency/term association; the scorer now rejects matching
labels paired with incorrect resource identities. Scoring-tool tests: **12
passed**, including reproduction of both published baselines.

## Changes and verification (campaign in progress)

### Current-point entity spans

Commit **d964490** separates trailing current-point modifiers from the exact
constituency mention in the existing deterministic present-representation
grammar. It does not strip arbitrary unknown modifiers or perform fuzzy
identity recovery. The same House-date-resolved current term and mapped
membership-date evaluator still determine the answer.

Focused entity/evidence tests: **32 passed**. Existing question-failure tests
also passed (**33 passed, 1 skipped**, separately from the new span tests).
Actual `/ask` H19/H20/H03: **3/3 factual table matches**. New Waterford and Clare
"Which deputies represent … today?" requests matched independently executed
direct-SPARQL Member identity sets. Expired synthetic membership evidence is
excluded in deterministic testing. Additional gender and age conditions returned
unresolved/unsupported outcomes, never a simplified Member answer.

Ontology validation passed: **2,586 triples**, including successful HermiT
execution. No semantic-contract areas were changed.

The broader non-NLQ regression run completed independently of the in-flight
query implementation: **1,134 passed, 24 skipped, 23 subtests passed**
(`python -m pytest tests -q --ignore-glob='tests/test_nlq*.py'`). Final query
integration checks are recorded separately; this subset is not described as a
completed full-suite run.

This subset was repeated during integration: the first 120-second execution
timed out without a completed result; the longer-limit rerun passed with the
same **1,134 passed, 24 skipped, 23 subtests passed** in 156.59 seconds. Ontology
validation was repeated successfully with HermiT and **2,586 triples**.

## Independent acceptance

A separately contextualized executor constructed a new contract-informed
holdout and fresh direct-SPARQL oracles without access to remediation code,
tests, published evaluation questions or failure reports. Its question/oracle
artifacts were committed as **a7bca64** before any acceptance `/ask` execution;
the implementation orchestrator committed them without reading their contents.
Execution awaits implementation freeze. Until independent execution and scoring
finish, **campaign acceptance is not established**. No implementation will be
tuned against its results.

The independent freeze contains **44 cases**: **38 factual**, one ambiguity
control and five unsupported controls, all pinned to **2026-11-06**. Only these
aggregate counts and artifact hashes were returned to implementation review.
An exploratory candidate with unusable direct joined evidence was excluded
before freeze, not replaced after observing a service result.

The first proposed author stopped before constructing any cases after reading
an explicitly excluded prior-question corpus. Its work is not acceptance
evidence. A fresh-context replacement was restricted to machine-readable public
contracts and direct RDF queries, excluding the guide's historical benchmark
summaries as well as prior questions, remediation source and tests.

## Safeguards and deliberate boundaries

Independent architecture review found that routing existing operations through
the existing capability-selection mechanism does not require a new query engine
or a change to RDF semantics. It specifically challenged measure substitution,
unconsumed filters and the distinction between graph validation and validation
of the original question. A complete graph alone cannot establish that a
question's entire intent was preserved.

An intermediate, uncommitted adapter draft passed deterministic tests but still
required canonical whole-question wording. Review rejected that draft as
insufficient generalisation; a green suite is not used as a substitute for
actual service and independent language-transfer evidence.

Forced supported-draft probes also exposed latent original-question validation
gaps: shared-term and representation graphs could omit an extra requested
condition/output, and the positive current-Seanad/prior-Dáil graph accepted
negation, gender and age-output additions. These were validator-only probes,
**not observed live factual errors**. They are retained as development evidence;
graph construction remains unwired until the relevant guards are integrated.

The existing single-partially-overlapping-month House-term guard is retained.
H40's frozen factual expectation does not override the technical specification's
full-interval/supported-transition restriction. It remains in the original
48-case scoring denominator rather than being silently removed. Likewise,
H21/H22/H44 retain their published scope caveats and frozen factual expectations;
refusals still score FAIL against that freeze. No historical date-to-roster or
office-anchor-plus-numbered-term operator is being added.

## Integration status

Work remains on the campaign branch; no automatic merge is authorized. Final
results, remaining limitations, commits and draft-PR status will be recorded
here at campaign closure.
