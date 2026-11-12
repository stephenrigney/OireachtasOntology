# Independent review — composition evidence freeze protocol/control coverage

**Reviewer:** independent subagent (architecture-plan-auditor role), read-only.
**Date:** 2026-11-12. **asOf pinned:** 2026-11-11 (protocol explicitly pins the
calendar date, not machine-clock "now"; the 1-day drift is handled by design).
**Branch:** `feat/nlq-bounded-composition-kernel`, HEAD/origin
`069b483e39b613c8958df11ba467d73c64d08653` (verified). **Scope:** protocol and
control coverage only — not kernel code, not the withheld K+R package, not any
private oracle or agent-session transcript. No store contact, no kernel code,
no Git commit, no file changes other than this report.

**Review pin (hashes observed at review time):**

| Artifact | SHA-256 |
|---|---|
| `protocol.md` | `7d18e051c244f25bb945c5ad34674d6a012a768db102d74a08048120d2685536` |
| `README.md` | `fe5ba00e64a9612cc625a5873c9eec46125420de1dc70cc26b92a443d828503b` |
| `development/controls.json` (111 controls) | `426f6ecf04161edb0d44469b351ebe2bb0d83372a5060fef15f2d2daa83b465d` |
| `development/oracle.json` | `2c0375c1d1e97fc3bf12a52752a3eedc3e979b045c9791d9bc2641201483e9e5` |
| `development/scope.json` | `d0e81047517ad00c8337d093d238b24383571becfbdc73439d7f77460d852ed6` |
| `authority.json` | in `manifest.json` as of its generation (all pinned `authoritative_files` hashes re-verified against working tree: **all match**) |

**In-flight caveat:** the freeze directory was being revised concurrently during
this review (controls 109→111, oracle 787→1,665 lines, new `scope.json`,
`member-link-enumeration` / `resource-audit-additional-*` captures,
`verification/` and `development/independent-review/` artifacts). Findings below
are pinned to the hashes above; the final pre-custody step must regenerate the
manifest against final bytes and re-run verification (see B1/B2).

## Verdict

**Conditionally ready, pending bounded corrections and user custody — no
material requirement is weakened.** The frozen protocol/controls implement the
human approvals faithfully and in several places are stricter than the readiness
§6 minimum. No approval-gated semantic contract, IRI/named-graph ownership rule,
or acceptance criterion has been relaxed. The defects found are integrity
bookkeeping (stale manifest/verification record during active revision), not
semantic or coverage gaps. Custody/transfer/removal/context-exclusion remains
user-gated; readiness is not claimed by this review.

## Approval conformance (user requirements → frozen artifacts)

| Approval | Frozen implementation | Status |
|---|---|---|
| Count = distinct qualifying **recorded** Member identities with source-coverage qualification | `inputs.json` R+P `answer.unit/scope`; oracle `measure`; protocol gate 1 "never complete real-world coverage" | ✅ |
| Either independently current Dáil **or** Seanad P for K+P | `inputs.json` K+P `houses:["Dail","Seanad"]`; synthetic `either-House-independent-terms` control; protocol §Control interpretation | ✅ (synthetic-only live coverage — see residuals) |
| Independent inclusive `asOf=2026-11-11` testing **every** required path | `currentAtRoles` enumerates all roles per case (R: pm/term/episode/containingMembership/term; K: owner/term/membership + P roles); inclusive boundary positives (`inclusive-start-today`, `inclusive-end-today`) and ended-path negatives for pm, episode, committee membership, committee owner, House term, and cross-directions (ended R w/ current P, ended P w/ current R, ended K w/ current P, current K w/ ended P, current memberships w/ ended owner/term) | ✅ matrix is closed for the required paths |
| No cross K/P term equality | `inputs.json` K+P `forbiddenExtraEquality`; admission controls `KP-added-cross-term-equality`, `KP-added-cross-membership-equality` | ✅ |
| Exact pm joins / typed witnesses | exactSharedBindings; `RP-wrong-pm-binding`, `wrong-containing-pm`, `KP-wrong-containing-pm`, `missing-member-pm-link`; protocol forbids row counts/name joins/IRI substring/superclass inference | ✅ |
| Empty evidence = nonanswer | `R+P-empty-retrieval`, `K+P-empty-retrieval` (`evidence_nonanswer_not_zero_or_successful_empty_list`); protocol gate 3; ended→empty controls expect nonanswer, not zero | ✅ |
| Budgets: ≤8 SELECT / 100 rows / 20s / 100 join tuples / ≤2 relationships / ≤2 P House variants | protocol gate 5 (now also "only the three reusable R/P/K adapters overall"); negative controls 9 selects, 101 rows, 101 tuples, 3 selections, 3 House variants, 32001 chars, timeout, incomplete, page-cap at 8; **new positive inclusive-boundary controls** (`*-inclusive-budget-boundary`, layer `budget-boundary`) exercising exact ceilings | ✅ complete vs readiness §6(5) |
| Implementation SHA/harness frozen before K+R release | protocol gate 6 + custody step 4 | ✅ |
| User-held custody, no plaintext commit, confirmation before final commit | protocol §Custody 1–4; directory currently untracked in Git (verified) | ✅ pending user |

## Admission vs valid-plan separation

Adequate and explicit. `controls.json` carries a `layer` field
(`semantic-admission` 29, `valid-plan-evidence`, `evidence-invariance`,
`budget-boundary`, `resolution`); protocol gate 2 requires scoring "semantic
admission separately from valid-plan evidence evaluation and resolution
ambiguity". The strongest discriminators are present:

- `KP-dail-only`: scope narrowing must be rejected at admission even though the
  answer on frozen evidence would be identical — this is exactly the
  "well-typed weaker plans remain invalid" test.
- `RP-count-memberships-not-identities`: unit/measure mutation rejected.
- `invalid-nonqualifying-candidate`: required-evidence removal on a
  **non-qualifying** candidate (Daniel Ennis) forces resource-level inspection
  before filtering — failures may not hide behind inner joins.
- `natural-ended-committee-control`: no-op tripwire verifying ended Ardagh/
  Connolly episodes stay excluded (note: trivial mutation, no adversarial value
  beyond regression; fine to retain, do not count it as mutation coverage).

## Source/snapshot unknowns and false-readiness check

Honest. `authority.json` explicitly nulls `loaded_run_id`,
`source_raw_json_hashes`, `store_publication_validation_attestation`; snapshot is
"sequential bounded SELECT pages … not transactional isolation"; README's
**Unresolved** section enumerates run identity, raw-API hashes, SHACL
attestation, global coverage, transactional isolation, and out-of-scope
malformed paths; the `provenance-presence` capture is labelled as bounded, not a
global negative. Readiness is consistently "pending independent review and
custody"; "Independent" is defined honestly (separate derivation/review, shared
infrastructure — not blinded/statistical). No false certification found.

## Completeness

- `development/scope.json` now makes replay coverage operational: 20 seed
  Members, 375 audited subjects, 27 fixed predicates, explicit "do not turn
  missing out-of-scope facts into false or zero" limits. This resolves the
  harness-coverage requirement in a checkable way.
- Oracle verified programmatically: 5 R+P / 15 K+P dispositions; qualifying sets
  exactly equal `expectedMembers` (1 / 4); R+P count parity; every disposition
  carries interval metadata incl. graph/range/rangeType/typed endpoints; all
  R+P candidates carry `representation`; K+P carries owner interval + term;
  `currentTerms` for both houses. Control removal quads: **all 111 exist in
  `evidence.nq` (1,782 quads)**. Stability: 16/16 queries identical multiset.
- Type/predicate IRIs in controls match the pinned ontology
  (`ontology/members#*`, `ontology#Member/DailTerm/SeanadTerm`,
  `dcat:startDate` on `#term-period`) and the captured evidence predicates
  (`inOireachtasMembership`, `isPartyMembershipOf`, `inHouseTerm`,
  `committeeInHouseTerm`, etc.). Double-hash range IRIs match actual store
  patterns.
- Baseline evidence: `tests/validate.py` pass (HermiT, 2,586 triples),
  pytest 2,436 passed / 30 skipped baseline log retained; skipped are labelled
  "not passes". Custodian tools are acquisition/verify-only and guarded by 9
  dedicated tests.

## Synthetic controls validity

Valid and well-fenced: additions are in-memory-only, explicitly flagged
(`synthetic: true` on `either-House-independent-terms`), never loaded into
Fuseki, never presented as source observations; removals are verified to exist.
The either-House control is the correct way to test the approved broader scope
without pretending observed (all-Dáil) positives demonstrate it. The multiple-
episode control keeps one Member with two distinct party-episode witnesses
(`expectedAdditionalEpisode` recorded). The ambiguous-resolver controls freeze
exact additional owner quads/IRIs and forbid row-order choice.

## K+R zero-change criterion

Stronger than the readiness minimum: gate 6 now distinguishes test data /
previously approved capability configuration from logic, states that
"configuration containing new topology-specific query templates, validators or
projection assemblers counts as changed logic", and adds the prebuilt-special-
case criterion ("a prebuilt K+R special case already present in the frozen
commit also fails … zero edits after release alone do not prove generic
reuse"). Any code fix, even generic, ends zero-change credit. No party
condition or cross-path term equality in K+R. No weakening found.

## Findings

**Blockers (bounded, must be closed before custody handoff):**

1. **B1 — Stale manifest / coverage.** `manifest.json` currently hash-mismatches
   `README.md`, `development/controls.json`, `protocol.md`, and does not list
   `development/scope.json`, `verification/checks.json`, the three verification
   logs, or the four `development/independent-review/*` files. Regenerate the
   manifest as the **final** pre-custody step against final bytes and re-run
   `tools/nlq_freeze_verify.py` (it will fail as-is).
2. **B2 — Stale verification record.** `verification/checks.json` reports
   `nlq_freeze_verify` exit 0 with "109 controls"; the current tree has 111
   controls and a mismatching manifest, so that run cannot describe the final
   state. Re-execute against the final frozen bytes (or annotate as superseded
   with a pointer to the re-run). Also refresh the "109 controls" figures in
   README/checks to the final count. Any claim of verification evidence the
   package does not possess would itself be a false-readiness artifact.

**Bounded corrections / clarifications (recommend, non-blocking if handled):**

3. **C1 — Conditional rowTransform disposition.** Duplicate-based invariance
   controls resolve to over-budget expectations whenever a transformed request
   exceeds 100 raw rows; controls.json `expected` describes only the in-bounds
   disposition. Require the harness ledger to record per request which
   disposition applied (invariance vs over-budget) so gate 4 and gate 5 results
   are deterministic and auditable.
4. **C2 — `budget-boundary` padding is prose.** "equivalent duplicate rows/
   witness tuples only … count raw rows before deduplication" is implementable
   but the evaluator must show pre-dedup raw counts in the retained ledger;
   state that explicitly as retained evidence.
5. **C3 — inputs.json field asymmetry.** R+P P uses `"house"` (singular) while
   K+P uses `"houses"` (array). Harmless, but adaptation must not silently
   widen/narrow scope; one line in the adaptation guidance avoids ambiguity.
6. **C4 — `development/independent-review/*` provenance.** These artifacts
   appeared during this review and are not covered by the manifest. If any are
   labelled "independent review" but were produced by the custodian session
   itself, that label is inaccurate — independence must be documented with
   author/session identity or the artifacts renamed to what they are. (I
   deliberately did not read them, to preserve this review's independence.)
7. **C5 — pytest baseline scope.** The 2,436-passed baseline predates the nine
   custodian-tool tests; a final full-suite rerun on the frozen state (or an
   explicit annotation) closes the gap between "baseline" and "frozen state".

**Residual risks (accepted, restate at freeze):**

- Negative evidence semantics over a scoped slice are operational
  (uncovered lookup → nonanswer), not store-wide certification — consistent
  fail-closed, but zeros must never be inferred from absence.
- The approved either-House P scope is exercised only by the synthetic control;
  live-store Seanad-27 party paths are neither asserted nor certified.
- Custody/transcript-exclusion can only be verified by the user; the protocol
  correctly treats unverifiable exclusion as a custody blocker, not a pass.
- The K+R probe remains unseen here; gate 6 has not been exercised and its
  prebuilt-special-case detection relies on custodian honesty plus the frozen
  commit diff — no further control is proposed within this scope.

## Conclusion

No material requirement is weakened and no architecture change is requested.
Close B1/B2 (manifest + verification re-run on final bytes, with refreshed
counts), optionally apply C1–C5, then proceed to the user custody gate. This
review approves nothing; readiness remains pending custody and the freeze
remains a preparation artifact, not an implementation authorisation.
