# Independent post-run evidence review

Reviewer: `architecture-plan-auditor`, session
`ses_e3ed79a92ffexahzX9kChS58b3`, continuing the independent pre-execution audit.
Read-only review; no files modified, provider calls, further experiments or external
PR requests. The reviewer did not rely on the then-incomplete report prose.

Independently confirmed from retained raw outputs and frozen code:

- All 15 frozen files match their `79867c7` blobs, run manifest and working tree;
  all 666 baseline blobs remain unchanged. All 72 question-only input hashes and
  all 72 frozen prompt hashes match. There are 72 HTTP-200/schema-valid completed
  outputs, zero call errors, and one configured model.
- B1 supported reachability is **4/6, 4/6, 3/6**; B2 is **3/6, 4/6, 3/6**;
  natural unsafe admissions are **0/18 for both**. Decisions are stable for 11/12
  cases; only three supported cases admit throughout. The independent summary
  recomputation exactly matches `summary.json`.
- The first deterministic scoring failure is reproducibly a tuple/list JSON
  boundary mismatch at U2/r1. The replay wrapper changes serialization only;
  all original assertions execute and every stored decision/delta reproduces
  through the unchanged frozen gate. It is not a rescue or relaxed scoring rule.
- All 18 lossy omission candidates admit under B1 and refuse under B2. Only
  **8/18** have credited valid material detection: U2 all three, U6 all three,
  U1/r3 and U4/r1. The remaining ten use invalid blind representations and are
  correctly uncredited. All 111 injected comparisons refuse, but only **68**
  demonstrate credited detection (60 targeted supported-role mutations + eight
  omissions); 43 comparisons are uncredited.
- All 21 reviewed admitted extractions (11 B1 primary + ten B2 blind) have material
  keys exactly equal to the supported references, valid offsets and no context/
  instruction atoms. The main executor reviewed all their source evidence and
  explanations; the independent reviewer also sampled explanatory consistency.
- Catalogue temporal-role errors and S5 whitespace-boundary errors account for
  the supported refusals exactly as reported. No transport error was reclassified
  as a semantic refusal.

Credit limitations: U6's blind extra output is often `term_list`, not the finer
`identity` output value; U1/r3's filter binding is coarse. Under the frozen rubric
these detect at least one real missing material requirement, not necessarily
perfectly reconstruct every detail. More conservative granularity credit could
only lower detection and would not change the rejection recommendation.

**Independent conclusion: REJECT THIS APPROACH.** Reachability, consistency,
valid completeness detection and no-systematic-false-refusal conditions fail.
Observed safety and admitted fidelity do not override the failed conditions.
Stop this particular blind-verification approach; no rescue round is recommended.
