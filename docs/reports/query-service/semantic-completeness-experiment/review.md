# Independent review and disposition

Independent reviewer: `architecture-plan-auditor`, session
`ses_e40a4ef59ffeKL45UYMPSkmtpW`. This was design review, not acceptance or an
approval gate. It inspected the script, cases, protocol, term-count adapter and
schema, and reproduced `static-results.json` **byte-for-byte** in a disposable
output. It did not inspect frozen PR #27 acceptance questions or pilot question
text directly. No production changes were made.

## Accepted findings

- **Same-model call is not statistical independence.** Relabel B2 as a
  fresh-context same-model reconstruction/consistency arm. Blindness means no
  access to the first proposal; shared weights, biases, provider behaviour and
  caching remain. Agreement is consistency evidence, not completeness proof.
- **The 13/13 omission-check result is constructed.** The injected proposals
  intentionally preserve the fields checked by the weak necessary-check
  function. This illustrates insufficiency; it is not an empirical semantic
  verifier miss rate. B1 and B2 remain completely unmeasured.
- **The proposed comparison is not an executable specification.** A strict
  obligation-ledger schema and total comparison specification, including
  materiality, bindings, segmentation and refusal behaviour, must be frozen and
  reviewed before live testing. Human judgement must not masquerade as an
  automatic gate.
- **Small diagnostic corpus and flat diagnostics limit inference.** The 0/7
  result establishes a coverage gap on these questions, not a language-population
  rate. The generic refusal message does not establish which role failed.
  NEW-TC-21 also contains an unfamiliar clause, so its refusal cannot isolate the
  excluded-measure mechanism.
- The pilot replay derives oracle mentions from three fixed names. That is a
  disclosed development-only convenience, not a reusable grounding mechanism.
  These rows must not establish entity-resolution correctness.

These caveats are incorporated into README/protocol. The frozen cases, script
and measured static results are unchanged. Revisions to the future, unexecuted
protocol are review clarifications, not tuning against model outcomes.

## Factual corrections / timing qualifications

- The reviewer stated the **case author** could read `term_count_intent.py`.
  The author task explicitly prohibited implementation access; its returned
  provenance states no implementation was read. The **reviewer**, not the
  author, was allowed that file. The actual independence limitation is the
  disclosed contract metadata exposure (Q04/T01), not known grammar access.
  Independent authorship remains qualified, not acceptance-certified.
- The case labels were authored before execution. Only NEW-TC-02 has a separate
  pre-run scope correction, acknowledged by its author; labels were not
  post-hoc adjustments to observed results.
- There are **30 rows per run**, not 39. The retained result and byte-identical
  reproduction determine the count.
- README/results were untracked when review began, but were committed in
  `f14b7d5` before handoff. The review's initial file scope excluded README; its
  conclusions were not independent review of the narrative report.
- The executor checked dotenv presence in **both** current and primary checkouts
  (both absent), plus current process settings. The review independently checked
  only its current worktree. Neither observation establishes provider availability
  elsewhere or at a later time. Transport defaults were read from tracked
  `poc/nlq/config.py` and still need revalidation at live preflight.
- The static runner pins six authority files, but the separate integrity check
  in `verification.json` compared **all 586 baseline tracked files** byte-for-byte.
  The broader unchanged-file claim does not rest on the runner's six hashes.

## Outcome

The reviewer supports **revise, not adopt for production**, with the caveats
above. It found no approval-boundary violation or change to acceptance criteria,
identifiers, fixtures or contracts. Remaining assurance risks are unresolved;
human architectural review remains the next gate.

Follow-up: the same reviewer subsequently inspected the revised README,
protocol and this disposition. It accepted all factual corrections above,
confirmed the F1/F2/F4 caveats, and found no remaining overclaim blocking the
static-only recommendation. This follow-up reviewed narrative/design only;
the initial independent byte-identical reproduction remains the replay evidence.
No approval for live execution or production implementation was given.
