# OireachtasOntology NLQ — Bounded Composition Kernel Implementation

Experimental development-only vertical slice, pinned `asOf=2026-11-11`.
No withheld K + R input, oracle, private file, conversation or custodian tool log
was accessed. No K + R execution was performed. Release remains separately gated.
This report does not claim withheld reuse success or production readiness.

## Design and isolation

`poc/nlq/experimental_composition.py` is an isolated module with an injected
transport, not an `/ask` family. It supplies only three relationship adapters,
typed exact-identity conjunction, independent current-at checks, and shared
evidence-native distinct-Member projection. There are no combination-specific
query templates, validators, executors or evidence assemblers in the kernel.
The independently supplied original structured intent is compared to independently
mutated candidates before retrieval; this is not general English admission.

The R adapter retains the exact Dáil membership, constituency occurrence and
term. P retains its exact Member-linked containing parliamentary membership,
episode, party occurrence, reviewed affiliation identity and own term. K retains
its exact Committee incarnation, owner interval, owner term and membership;
it invents no parliamentary containment. Every interval is evaluated independently
using inclusive calendar days. Ended paths exclude only their own valid witnesses.
Missing/conflicting required resource evidence fails the whole selection, including
nonqualifying candidates, before Member projection. Member identities are not names.

All descriptive facts retain typed RDF objects and their actual graph IRIs.
Optional graph-witnessed facts expose missing types, endpoints, targets and links
instead of losing candidates through inner joins. Exact required asserted types
are retrieved without multiplying rows by benign generic co-types. They are not
inferred from superclasses. Distinct episodes survive projection. Stable ordering
is produced by the kernel itself, not imposed by the scorer.

Shared assets reused: versioned query-schema namespace/property/class/owner
registry, `_reviewed_predicate_for_qname`, `_require_local_iri`,
`_mapped_member_interval`, `_date_binding`, and `validate_sparql`. The existing
committee resolver's source-grounded on/of connector equivalence is retained.
The old family result/projector interfaces contain formatted strings, so they
are not composed. A small typed paginator is necessary to retain RDF bindings
and charge resolution, every page and completion to one budget. It preserves
the existing stricter **15-second** request timeout; 20 seconds is only the
frozen counter-test ceiling. No production contract, route, source, fixture,
ontology, ETL, Fuseki data or capability inventory was changed. No AI is involved.

## Replay mapping and limits

`tools/nlq_composition_replay.py` executes the generated SELECT text in RDFLib
over a fresh in-memory reconstruction of the disclosed audited N-Quads. It
preserves original lexical/datatype/language identity. It never contacts Fuseki.
The evaluation loop names only the two disclosed development cases.

Each generated lookup must match an approved scoped anchor and a recorded
short-page completion certificate: House terms → `terms`; constituency/Committee
resolution → `constituency`/`committee-owners`; R/K candidate enumeration →
`representation`/`committee-members`; P seeds → `member-link-enumeration`.
Every required OPTIONAL subject/predicate lookup must also fall within the
resource audit coverage. Explicit synthetic controls extend only their fresh
in-memory variant's audited subjects; the original artifacts never change.
An uncovered anchor or subject is an evidence nonanswer, not false or zero.
Party enumeration retains typed or explicitly linked party/collection candidates
before party/date filtering; unrelated membership families are not promoted to P.
R/K reverse Member links remain OPTIONAL in the same graph as the certified
relationship anchor, exactly matching their captured candidacy enumeration;
descriptive children retain independent graph witnesses. Missing required Member
identity/containment evidence fails the whole selection under the already frozen
missing-evidence rule, never silently excludes an orphan to obtain a partial count.

This is a scoped replay certificate, not store-wide closure, a transactional
snapshot, proof of upstream source completeness, or an ETL publication attestation.
Owner-resolution anchors retain the original captured owner graph and selection
scope; descriptive resource facts are checked across named graphs. No live result
or live HTTP latency/availability claim follows from the replay.

Whole-plan ceilings: two relationship selections, two P House variants,
eight SELECT requests, 100 raw rows per response (duplicates charged), 100
binding-join tuples, 32,000 query characters, and existing query-safety restrictions.
Primitive intermediate witness sets are also bounded before selective binding.
Completion probes are charged. Exactly equivalent RDF facts are sets; conflicting
values are retained for resource validation. Distinct relationship witnesses are
never discarded to fit a bound. A successful empty list/zero is not admitted.
K + P remains list-only; the count helper does not admit Committee counts.

## Reproduction and retained evidence

From the repository root:

```sh
.venv/bin/python tools/nlq_freeze_verify.py docs/reports/query-service/composition-freeze-20261111
.venv/bin/python -m pytest -q tests/test_nlq_experimental_composition.py
.venv/bin/python tools/nlq_composition_replay.py /tmp/oireachtasontology/nlq-composition-kernel/replay.json.gz
.venv/bin/python tests/validate.py
.venv/bin/python -m pytest tests
```

`results.json.gz` retains original/mutated candidates, semantic dispositions,
SELECTs, typed responses, coverage certificates, complete replay request ledgers,
pre/post-transform raw counts, validated witnesses, binding stages, projections
and assertion scores. Query elapsed times are volatile diagnostics, not part of
the deterministic answer. Equivalent duplicate transformations are applied only
to responses that remain within 100 rows; larger responses are explicitly marked
ineligible rather than truncated. Independent over-limit controls still test 101.

Only the two inclusive budget-boundary controls are counter-level tests using
actual frozen-equivalent typed rows/witnesses, not claims that a natural plan
made eight requests. All negative transport/ledger overrides run the actual
candidate executor with injected budget/transport faults. Nine-request cases
charge equivalent duplicate resolution requests before the native cap refuses
the ninth request; full-page cap cases exercise the real paginator; join-cap
cases pad actual joined structured tuples before the native budget check.
Padding counts, raw rows, retained witness tuples and complete ledgers are kept.
The pagination completion cap is additionally exercised by an eight-full-page
unit transport test. Supported positive refusal is scored as
a capability failure, never as safety credit. Assertions cannot be disabled with
Python `-O`.

Independent review identified the reverse-graph certificate alignment and the
initially over-broad counter-only routing as verification gaps; both were corrected
before the final reruns/freeze. The frozen 20-second inclusive counter test is
retained unchanged and explicitly distinguished from operative 15-second execution.
Original endpoint/current flags are independently rescored from source quads for
every positive evidence variant, including nonqualifying validated relationships.
The route isolation test asserts real production entrypoints exist rather than
silently skipping missing paths. No acceptance threshold or frozen control changed.

The development-oracle adapter necessarily reads the published oracle's differing
R/P and K/P field layouts; that is expected-result scoring only, not candidate
composition or projection. Its full implementation cost is included. No private
oracle-format compatibility, live execution or zero-change withheld success is
claimed before release and separate evaluation.

`environment.json` freezes source/harness/configuration/public-evidence hashes,
the dependency lock hash and installed dependency versions. The full implementation
commit SHA is the commit containing these artifacts and is recorded in the final
handoff; it cannot be embedded in its own committed content. No code change after
that commit receives strict zero-change reuse credit.

## Verification outcome

Final measured outcomes and limitations are recorded in `verification.json`.
Final candidate checks: **133 focused tests passed; full repository 2,578 passed,
30 skipped; ontology validation passed with 2,586 triples**. Skipped integration/
environment checks remain unverified, not passes. Relevant existing compiler
regressions separately recorded **402 passed, 1 skipped**. There are no outstanding
development control failures. Withheld evaluation and live Fuseki execution remain
unperformed; no production-support or complete-source claim follows.

| Disclosed plan | Recorded result | SELECT replays | Raw rows per request | Validated / selected primitives | Binding stages |
|---|---|---:|---|---|---|
| R + P | **1** distinct Member: Mary Lou McDonald | 4 | 65, 1, 5, 14 | R 5 / 4; P 14 / 1 | 4 → 1 |
| K + P | Albert Dolan; Martin Daly; Paul McAuliffe; Séamus McGrath | 4 | 65, 6, 15, 26 | K 15 / 13; P 23 / 5 | 13 → 4 |

These are qualifying identities in the scoped captured RDF, not certified
real-world totals or rosters. Both positives passed exact identity, containment,
term, original endpoint, current-flag and graph assertions. R + P list/count parity
holds; K + P exposes no count projection. Baseline oracle scores retain 171 and
688 assertion records respectively, plus 52 and 114 independently recomputed
source-local interval assertions across all validated relationships.

All **111 / 111** frozen controls pass: 29 semantic rejections, 67 evidence
nonanswers and 15 supported answers (including the two explicitly counter-only
inclusive boundaries). Only those two are counter-only; negative budgets run
the candidate. The complete artifact has 267 recorded SELECT budget charges
across all baselines/controls, including 10 marked mock duplicate requests and
16 inclusive-boundary unit charges; these are not 267 live HTTP calls. Actual
Fuseki HTTP calls: **zero**. Maximum natural request size: 65 rows; maximum
natural query length: 5,650 characters; operative request timeout: 15 seconds.

Inclusive boundary controls retain eight charges, 100 raw rows (35 exact duplicate
padding rows) and 100 join tuples. R + P witness padding is 99; K + P padding is 96.
Nine-request and full-page exhaustion controls each show eight charged requests
and a refused ninth attempt; 101-witness controls retain 101 padded actual joined
tuples and no factual answer. The two declared negative budget shapes are tested
at native budget entrypoints; separate semantic mutation controls for a third
selection/House were not added to the frozen inventory. Per-primitive and per-stage
tuple ceilings are enforced, not a cumulative sum across unrelated primitive sets.

The first shell-limited focused/full attempts timed out at 120 seconds and are not
passes. During review correction, an added orphan test also failed on the diagnostic
(`Truncated typed fact` instead of missing reverse Member): the anchor graph was
already bound despite the OPTIONAL Member being absent. Fact extraction now treats
that as absent required evidence and still refuses the whole selection. The test
was not weakened. A subsequent **133-test focused run passed** on the frozen source;
final full-suite and ontology outcomes are in `verification.json`. The malformed
date negative control deliberately emits RDFLib's `not-a-date` conversion diagnostic;
the evaluator correctly reports a nonanswer and exits successfully overall.

The baseline checkout was clean at `6fdf597f1eaf3ff18caa0c99ab7fd82af04373aa`.
The authority's starting revision `069b483e39b613c8958df11ba467d73c64d08653`
is an ancestor. All pinned authoritative and custodian-tool hashes matched before
implementation; public artifact integrity passed (1,782 quads, 2,491 captured
typed rows, 36 acquisition requests, 111 controls). Acquisition requests are not
candidate budget counts.

Neither successful development verification nor generic source structure proves
withheld generalisation. Freeze and stop here; do not infer or execute a withheld
answer, integrate production routing, or start another tranche.
