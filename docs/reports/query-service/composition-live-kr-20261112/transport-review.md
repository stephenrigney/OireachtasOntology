# Independent transport and mechanism review

Reviewer: `architecture-plan-auditor`, session `ses_e2ea4ce6affefLuXb2ual5YjVD`.
Read-only review before the first live kernel execution; no execution approval
gate or replacement for independent outcome scoring.

Verdict: **no blocking fidelity defect** in the generic live transport against
frozen kernel `e98296ef2d89a07810c3b0f3f801c99f76636ae7`.

- RDF lexical/datatype/language identity is retained with `normalize=False`;
  unsupported/malformed bindings fail closed rather than being filtered.
- The complete flag certifies a received JSON page, not the whole selection.
  A full page still forces the frozen paginator's charged completion request.
- Query text is sent unchanged. Existing 15-second operative request timeout,
  query safety, retrieval, resolution, validation, paging and budgets remain
  owned by the kernel.
- No K+R-specific precompute, filtering, compiler, validator, projector or
  assembler occurs in the live path. Role targeting in the separate saved-page
  harness is explicitly synthetic fault injection, not application logic.
- Live short-page completion relies on the endpoint honouring SELECT semantics;
  raw bodies are retained. Neither this nor the oracle is a transactional snapshot.
- HTTPX timeout is per-operation, backstopped by the unchanged kernel's elapsed
  check. The injected timeout control does not test an actual 15-second delay.

The seven planned controls exercise native frozen-kernel checks. Pre-run flags:
check every baseline page has fewer than 100 rows before duplicate padding;
unexpected harness exceptions could interrupt control-result persistence;
independently check the exhaustion ledger has eight charges, offsets 0..700.
No new join/witness-cap stress control is supplied; natural tuple counts and
the unchanged existing test suite are distinct evidence from a live boundary test.

The review initially observed 11 transport tests. A twelfth transport-only test
was subsequently added before the first live execution to explicitly check that
101 rows and ill-typed literal lexical forms are passed through, not repaired or
filtered. The adapter source itself was not changed after review.

## Independent scorer review

The same reviewer separately inspected `tools/nlq_live_kr_compare.py`: expected
required-fact/interval parity and candidate-resource/witness-pair completeness
were defensibly scorable; no masking or invented-path acceptance was found.
Its medium finding (pin the resolved target to the original requested IRI) and
endpoint/binding-kind checks were addressed before execution. The scorer does
not assume K is Dáil-scoped; the observed K owner happens to be Dáil 34. The
corrected oracle's explicit projection aliases were checked before execution;
all 20 witness comparisons then passed without post-result scorer changes.
This scorer is expected-result evaluation only, never part of the live kernel
transport, validator, compiler, binder or projector.
