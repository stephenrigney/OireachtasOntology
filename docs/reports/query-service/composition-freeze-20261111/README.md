# OireachtasOntology NLQ — Independent Composition Evidence Freeze

**Status: evidence and protocol independently verified; user authorised proceeding
after the custody check, and temporary oracle copies were deleted. No kernel
implemented; production contracts unchanged.**

## Reference and scope

Repository `stephenrigney/OireachtasOntology`, worktree `query-service`, branch
`feat/nlq-bounded-composition-kernel`, starting HEAD and local `origin/master`
`069b483e39b613c8958df11ba467d73c64d08653`. No fetch or branch switch was needed.
Pinned `asOf`: **2026-11-11**. The task's human approvals resolve the experimental
choices in the [readiness report](../nlq-bounded-composition-experiment-readiness.md);
they do not change production semantics or admission.

## Development evidence

Fresh manually authored, bounded read-only SELECTs at
`http://localhost:3030/houses/query`, not readiness answers or compiler output,
enumerated the complete scoped candidate selections, then audited their explicit
resource facts across named graphs. Optional type, range, endpoint and reverse
Member links expose missing/conflicting evidence instead of silently inner-joining
it away. Party acquisition also retained historical episodes for inspection.
Every query is ordered, <=32,000 characters, LIMIT 100, 20-second client timeout,
maximum 40 diagnostic pages. Completion requires a short final page. The diagnostic
acquisition is not a candidate execution or proof of eight-request budget fit.

| Case | Independently derived recorded selection |
|---|---|
| R + P: current Sinn Féin / Dublin Central | Mary Lou McDonald; **1 distinct qualifying Member identity**, not a complete real-world total |
| K + P: current Public Accounts / Fianna Fáil | Albert Dolan, Martin Daly, Paul McAuliffe, Séamus McGrath |

There are five captured Dublin Central representation identities (four current)
and fifteen committee episodes (thirteen current). Ended Paschal Donohoe
representation and Catherine Ardagh/Catherine Connolly committee episodes do not
qualify. Current party evidence does not rescue an ended committee relationship.
The unique current House-owned terms are Dáil 34 (start 2024-11-29) and Seanad 27
(start 2025-01-29); original typed endpoints and absent ends are retained, not
replaced by these abbreviated dates. All observed qualifying P witnesses are Dáil
paths; the synthetic either-House control separately tests the approved broader
scope without pretending that observed positives demonstrate it.

Direct Member-link enumeration also checked forty collection candidates, including
three Independent records that are correctly not PartyMemberships; named-party
candidates were not silently lost behind a PartyMembership type gate.
The quad slice contains **1,782 distinct audited facts**. A second complete
sequential read returned the same typed-binding multiset for all 16 development
queries. Independent expected-result verification and its exact scope are retained
with the development materials; integrity checks do not score an unbuilt kernel.

## Artifact map

All paths below are relative to this directory unless stated otherwise.

* `authority.json`: base revision, approved experimental scope, pinned authority
  hashes and explicit upstream-provenance gaps.
* `development/inputs.json`: disclosed semantic inputs, independent of future IR.
* `development/captures/*/{query.rq,capture.json,page-*.json}` and
  `development/queries/*.rq`: original queries, typed response bytes, exact hashes,
  offsets, completion certificates and UTC timing. `resource-audit-*` checks
  asserted facts for explicitly listed resources in all named graphs using fixed
  predicates; `identity-audit` verifies reviewed affiliation identity descriptions.
  Response pages retain Fuseki's original bytes, including trailing whitespace;
  do not reformat them to satisfy whitespace lint or their capture hashes change.
* `development/evidence.nq`: lossless canonical scoped quad set reconstructed from
  resource/identity audits, not an export of the entire store or protected fixture.
* `development/scope.json`: exact replay coverage—twenty seed Members, 375 audited
  subjects and 27 fixed predicates—and explicit out-of-scope absence limitations.
* `development/oracle.json`: all candidate dispositions, exact Member/membership/
  episode/range/term identities, temporal flags, graph provenance and qualifying
  relationship alternatives. R+P list/count parity is explicit.
* `development/independent-review/`: separate raw-evidence audit, independent exact
  oracle comparator and review report. Both checks passed again on 2026-11-12 with
  the original `asOf=2026-11-11`; logs are in `verification/`.
* `development/controls.json`: frozen semantic, evidence, resolution, invariance
  and budget controls, including synthetic in-memory-only quad edits.
* `development/stability.json`: repeated-read comparison and second-read hashes.
* `protocol.md`: exact control/replay semantics, all seven acceptance gates,
  limits, no-regression requirements and user-held custody/release procedure.
* `verification/checks.json` and logs: ontology validation passed (2,586 triples);
  existing full test collection **2,436 passed, 30 skipped**; nine subsequently
  added custodian-tool tests passed separately. Skipped tests are not passes.
  Offline artifact verification passed: 36 first-read requests, 2,491 typed rows,
  1,782 distinct audited quads and 111 controls. Repeated reads use another 36
  requests. These are acquisition/check counts, not per-plan experiment budgets.
* `verification/protocol-review.md` and `review-disposition.md`: independent
  challenge of the acceptance/control protocol, with bounded integration fixes
  and provenance of the independent checks. Final integrity output is retained
  in `verification/artifact-integrity.json`.
  Git whitespace checks pass for authored artifacts with only verbatim response
  pages excluded; raw pages are checked by their original byte hashes instead.
* `manifest.json`: SHA-256 of every other public artifact in this directory.
* Repository `tools/nlq_freeze_capture.py`: reproducible bounded acquisition only;
  `tools/nlq_freeze_verify.py`: offline integrity/structure verification only.

The private K+R package has now passed a separate review, an offline custodian
verifier rerun, complete internal checksums and archive readback. `custody.json`
contains only the archive/file hashes, handoff paths, limitations and release gate;
no exact withheld parameters, answers or adversarial cases are committed. Its
plaintext was never placed in Git. On 2026-11-12 the user instructed proceeding
after the explicit custody/access check; the temporary oracle directory and archive
were then deleted and both paths verified absent. Retention of the external copy
and exclusion of private conversations/tool logs from the implementation environment
rely on that human authorization, not an independent technical isolation audit.
Session history was not deleted. The implementation SHA and harness must be frozen
before the user releases the oracle; release is still locked in `custody.json`.

## Graph identities and limitations

All authoritative graph IRIs below have prefix `https://data.oireachtas.ie/graph/`:
`houses`, `constituencies`, `committees`, `parties`,
`political-affiliations/identities`, and `member/{percent-encoded-memberCode}`.
Exact Member ownership is checked from the recorded Member code, not just a graph
prefix. The finite fixed-predicate resource audits expose wrong-graph assertions
for the selected resources; they do not certify unrelated resources or arbitrary
unlisted predicates. Exact original relationship links, not graph co-containment,
establish identity and parliamentary containment. CommitteeMembership has no
invented containing-parliamentary-membership assertion.

**Unresolved:** loaded ETL run/capture identity, immutable upstream raw API JSON
hashes, store-wide publication/SHACL validation attestation, global source coverage,
transactional multi-request isolation, and malformed/orphan paths outside this
explicit subject/predicate/anchor scope. The bounded provenance-presence SELECT
found no asserted `prov:Activity`; it is not a global proof that no provenance
exists in any other form. Scoped types/dates/joins/owners are independently checked;
that does not certify the entire loaded store as ETL-validated. No source record or
store state was modified to resolve these gaps. The frozen reference is the
captured evidence, not a claim of an immutable live Fuseki dataset.

The exact K+R artifacts are procedurally withheld, not statistically independent
or confidential against the owner of this shared environment. K+R topology and
the prior Galway East/Albert Dolan primitive exemplar were already disclosed.
Development RDF and the live store may contain primitive facts useful for that
topology; withholding does not pretend those facts are unseen. Fresh implementation
context must exclude custodian/private subagent transcripts and private files.
“Independent” here means separate derivation/review against the captured RDF, with
shared infrastructure and authoritative specifications—not a blinded or externally
sampled evaluator and not statistical independence.

**Readiness:** ready to develop the approved shadow experiment over the frozen
evidence, relying on the recorded human custody authorization and required access
exclusion. Whole-plan budget fit, candidate execution and K+R zero-change reuse
remain untested. This is not production integration readiness, real-world
completeness certification or a successful kernel evaluation. Stop here: no kernel
implementation belongs to this tranche.
