# Query Service — Pilot Semantic-Intent Validation for Term Counts

**Pilot exit criteria NOT MET. PR #27 remains NOT ACCEPTED, draft and unmerged.**
The bounded mechanism improves admission and constraint preservation, but fresh
named-Member paraphrases still fail closed. This is a separately authorised
pilot, not repair, repetition or replacement of the original failed acceptance.
Its **6/38 (15.8%)** factual score and frozen implementation `1e97ae4` are unchanged.

## Scope and handoff

Implementation checkpoints: **`6eb109e`**, followed by the mechanical strict-schema
compatibility correction **`293ab74`**. Parent baseline: `9800cb0`. Matching repository,
branch `feat/query-service-generalisation`, and clean initial worktree were checked
before mutation. No branch/worktree switch or merge was performed.

The referenced architecture document was absent from this frozen branch. The
proposed document on the repository's `master` was read remotely without merging
or rebasing it. The user's separate authorisation bounds this implementation.

The existing v2 `capability_selection` draft now admits a typed, IRI-free
`termCountIntent` parameter block:

- `countTarget`: `DailTerm`;
- `member`: one exact grounded mention, or null for the catalogue;
- `scope`: `member_service` or `houses_catalogue`;
- `answer`: `count_distinct`;
- `exclusions`: at most one explicit terminal excluded-measure contrast.

These are **interpretation inputs, not a second canonical plan**. The new
`term_count_intent` adapter derives an independent local interpretation, compares
the model's declared roles, and immediately lowers to the same existing
`{member}` or `{}` execution parameters. Legacy proposals use the same analyser.
The inventory records this admission seam; contract version is **2.29.0**.
The capability's executable semantics string is unchanged.

**`composable_plan.py` and `stage_a.py` are byte-unchanged from `1e97ae4`.**
Existing identity resolution, ambiguity sets, distinct-term aggregation, evidence
caps, unavailable/zero handling and qualifications remain execution authority.
No ontology, ETL, mappings, source/golden fixtures, graph ownership, identifiers,
publication controls or production configuration changed. AI supplies no SPARQL,
RDF IRIs or new graph relationships.

## Independent completeness check

The old term-count residual-token gate is replaced, not merely given additional
whole-question exceptions. The new bounded grammar composes count/target noun
phrases, grounded record owners, directed service/record relationships and an
explicit catalogue scope. It requires complete ordered-clause consumption.

Only NFC normalisation, a single exact grounded Member span, terminal punctuation,
and one recognised terminal excluded-*measure* contrast are consumed outside the
grammar. No arbitrary adjective, condition, conjunction or output is discarded.
For example, excluding membership **rows as the count measure** does not exclude
any selected term. Excluding a named term, dates, parties, additional people,
relationships, alternate measures or requested list/date/IRI projections refuses.
The model's `supported=true` and its natural-language intent summary are never
proof of completeness. Three fresh failures contain correct complete typed model
proposals, yet local validation still refuses them: safety and reachability are
distinct requirements.

Tests compose independent semantic slots, then mutate constraints, directions,
bindings, measures and model-declared fields. Integrated deterministic `/ask`
checks prove equivalent requests emit identical existing executor queries; an
omitted condition triggers no query. Exact-name mismatches do not become guessed
identities, and duplicate exact names remain separate candidates.

## Focused live evidence

Owned read-only pilot service: loopback **8002**, explicitly restarted per source
checkpoint; existing services were not replaced. Model **gpt-6-luna**, existing
Responses-compatible endpoint, reference date **2026-11-06**, query endpoint
`http://localhost:3030/houses/query`. No dataset reload or mutation occurred.
The existing development collector was reused with at most two concurrent calls.
This was **31 bounded cases**, not the original production-grade acceptance set:
**63 `/ask` requests** across the two source checkpoints and one explicit repeat,
plus two direct provider transport diagnostics (one rejected schema, one accepted).

`results-6eb109e/` retains the first replay: all HTTP 200, but 29 planner failures,
one early clarification and one deterministic answer. Provider diagnostics
identified unsupported JSON Schema `uniqueItems`. Checkpoint `293ab74` removes
only that redundant keyword; `maxItems=1` and exact local comparison still reject
duplicates. A provider diagnostic accepted the corrected schema. First results
are not overwritten or credited as semantic refusals.
`provider-transport-diagnostics.json` transcribes the observed sanitised diagnostic
tool output, including the exact rejected-schema error. It is not a raw HTTP
archive; the successful diagnostic response payload was not retained.

`results-293ab74/` contains the separate corrected-source primary replay:

| Check | Result |
|---|---|
| Original previously passing development controls | **16/16**, all rendered tables identical to the final `1e97ae4` development replay |
| Member-count development equivalents P02/P08/P09 | **3/3**, count **9**, exact Micheál Martin identity and identical canonical plans |
| QD-04 wording P01, primary | Provider HTTP 400; **remains a primary failure** |
| Explicit P01 diagnostic repeat | Count **9**, same exact identity/canonical plan as P02/P08/P09; **not replacement primary credit** |
| Added party/date/projection or membership-row target P03–P06 | No simplified answer: three unsupported outcomes and one early clarification |
| Exact-name ambiguity P07 | Both Brendan Griffin RDF identities preserved, matching the direct oracle; no count/identity selected |
| Fresh independently authored positives | **1/4**: catalogue count **34**; all three named-Member paraphrases refused |
| Fresh negative mutations | **2/2** explicit unsupported outcomes, no count |
| Corrected replay transport | **31/31 HTTP 200**, no transport retries |

All returned counts matched direct evidence; no unsafe simplified count was
observed. The QD-04 diagnostic repeat is retained separately. The single
HTTP 400 after schema correction is still reported as provider noncompletion,
not a validator rejection or a repaired primary result; its underlying provider
reason was not retained by the service outcome.

`control-plan-parity.json` also checks complete rendered answer text: **16/16**
equal to the final development baseline, including qualifications. All **13/13**
available top-level v2 diagnostic plans match after ignoring only syntactic
relation IDs (their facts, endpoints, selectors, constraints and answers match).
The three office controls expose no top-level v2 diagnostic plan; no plan-parity
credit is inferred from empty diagnostic lists.

`fresh-transfer.json` was authored independently without implementation, tests,
historical questions, reports or acceptance artifacts, with direct read-only
SPARQL oracles. Source was checkpointed before its questions were read/executed;
no admission grammar was tuned afterward. These are **development transfers**,
not a new acceptance claim. The author's direct member oracles also check target
typing in Houses; that additional oracle check does not change executor semantics.

`admission-comparison.json` contrasts the frozen admission function with the new
analyser, without executing either compiler. QD-04 changes from reject to admit.
The membership-row-target trap P06 changes from admit to reject. All three fresh
Member wordings reject under both implementations; the one successful catalogue
transfer already passed the old gate. Thus **fresh transfer beyond observed
failures was not established**.

## Verification and review

- Focused capability, term-count, Stage A and compiler run: **329 passed**.
- Post-provider-correction admission/capability run: **209 passed**.
- HermiT ontology validation: **passed**, **2,586 triples**.
- Initial full suite: **2,693 passed, 4 failed, 26 skipped, 23 subtests passed**;
  all four failures were stale exact contract-version assertions. Only those
  metadata pins were updated from 2.28.0 to 2.29.0; semantic assertions unchanged.
- Final full suite: **2,697 passed, 26 skipped, 23 subtests passed** in 582.29s.
  The four corrected exact version-pin checks also pass separately. Detailed
  commands, source parity and immutable artifact checks: `verification.json`.
- Python compilation and `git diff --check`: passed.
- Independent bounded safety/architecture review: `review.md`. No unsafe admitted
  question found in its probes; it explicitly did not certify language transfer.

The reusable element is the existing-adapter pattern: typed IRI-free inputs,
independent complete-intent analysis, exact agreement, one lowering seam, and
inventory/schema/executable consistency tests. It introduces no second planner
architecture. No other capability implements this pattern here; structural
reusability is **not** demonstrated language generalisation for another family.

## Limitations and stopping boundary

The grammar remains surface-bounded. It does not independently understand a
fronted local-records qualifier, a source-data-recording/service construction, or
a topicalised Member with anaphoric possessive in the fresh set. Extending it by
adding those observed sentences would not establish transfer. Model/provider
variability remains observable. A safe nonanswer is not factual success.

Consequently this pilot **cannot be accepted as a successful replacement of
wording-dependent admission**. QD-04 reachability and safeguards improved, and
existing controls hold, but the required fresh-transfer criterion fails. The
original failed acceptance has not been repaired or reclassified.

**Stop here for human review.** No projection repairs, wider semantic dispatch,
other capability families, unrestricted composition, production acceptance rerun,
or merge is authorised by these results. Review may retain the bounded safety
pattern as experimental evidence or authorise a separately bounded approach to
the remaining admission problem. Do not infer approval to expand the parser.
