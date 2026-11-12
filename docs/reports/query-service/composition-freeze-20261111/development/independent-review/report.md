# Independent review: composition-freeze evidence (2026-11-11)

## Finding

The regenerated `oracle.json` agrees with an independent derivation from the captured raw RDF for every candidate disposition, interval, exclusion reason, party witness, and examined current-term witness in the frozen cases. This is a **raw-evidence/oracle comparison only**; no kernel was run and this is not a kernel pass.

## Evidence and candidate derivation

- `evidence.nq` parses to 1,782 quads (1,782 distinct triples) and exactly equals the unique quads in the finite resource/identity audit captures: 1,791 result rows collapse to 1,782 quads, with no missing or extra quads.
- The first read is 16 queries, 36 paged requests, and 2,491 typed binding rows. All 16 sequential repeat-query checks report the same typed binding multiset; every repeated page hash matches its primary page hash. This confirms repeatability and serialized ordering for these bounded SELECT reads, not a transaction or source completeness.
- The corrected seed count is confirmed: the query has 20 unique Member VALUES, exactly the disjoint union of the 5 Dublin Central representation identities and 15 committee-member identities. The direct-member enumeration returns all 20, across 309 rows and four pages.
- That enumeration yields 233 unique Member→membership records and 40 records with a collection link. The 40 partition exactly into the 37 typed/party-linked records and three additional Catherine Connolly Independent collection records; no other collection-linked record is hidden outside the PartyMembership/`isPartyMembershipOf` candidate set.
- The three extras are explicitly `ParliamentaryCollectionMembership` records, not `PartyMembership`, and have no `isPartyMembershipOf` relation. Their owner graph, Member link, Independent collection, parent OireachtasMembership, and typed date ranges are explicit:
  - Dáil 32: 2016-03-10–2016-05-30.
  - Dáil 33: 2020-02-08–2024-11-08.
  - Dáil 34: 2024-11-29–2025-10-25.
  All ended before the as-of date. This establishes the finite-slice distinction without asserting a general `memberOfCollection` exclusivity rule. In `controls.json`, that property appears in the constructive multiple-witness and Seanad-alternate controls, not as a general exclusivity requirement.
- The current recorded terms are Dáil 34 (start 2024-11-29) and Seanad 27 (start 2025-01-29), both open-ended. The current Committee of Public Accounts owner is Dáil 34, starting 2024-12-18. Member code/owner-graph checks passed for 20 Member resources; 93 membership DateRange resources had no grouped missing/conflicting date/type/owner evidence.

## Oracle comparison

The independent raw checker (`check.py`) derives the candidate evidence without reading the oracle. The separate comparator loads the oracle for comparison, but derives candidate sets and witness objects solely from `evidence.nq` and the frozen raw captures, not oracle selections. It compared arrays in captured query order—without sorting oracle output to conceal order differences—and compared rendered names with explicit owner-graph `foaf:name` values. This wording was clarified during parent integration to match the scripts' actual read order.

- **K+P:** all 15 committee candidates and dispositions match, in raw query order. Thirteen committee membership intervals are current; Catherine Ardagh (ended 2026-05-28) and Catherine Connolly (ended 2025-10-25) are inactive. The four qualifying distinct Members are **Albert Dolan, Martin Daly, Paul McAuliffe, Séamus McGrath**. Catherine Ardagh has a current Fianna Fáil witness but is excluded by her ended committee interval.
- **R+P:** all five Dublin Central candidate dispositions match, in raw query order. Four representation intervals are current; Paschal Donohoe's ended 2025-11-21. The one qualifying Member is **Mary Lou McDonald**, with the exact shared Member, ParliamentaryMembership, and Dáil 34 term. The other current representation candidates (Daniel Ennis, Gary Gannon, Marie Sherlock) have no qualifying Sinn Féin episode on that exact membership.
- Every oracle interval, status, reason, party/identity graph link, witness object, and `examinedCurrentTermPartyWitnesses` array matched the raw owner-graph facts. The `expectedMembers` lists also match the qualifying candidates in source-capture order. Current witness arrays have at most one item per candidate, so the live source evidence does not exercise multi-witness ordering.

The frozen semantics remain R+P exact Member + exact shared parliamentary membership + exact term, and K+P exact Member only (no committee-term or containment equality). All observed qualifying K+P witnesses happen to use Dáil 34, so the source capture by itself does not distinguish Member-only joining from an accidental cross-term equality. The current `controls.json` has 109 control definitions, including `either-House-independent-terms`, the ambiguous-resolver, endpoint-inclusivity, and inclusive-budget-boundary cases. I verified those definitions are present, but did not execute them or verify parent-reported control outcomes.

## Determinism, scope, and remaining limits

The oracle's candidate-disposition order matches the frozen candidate query order, and the rendered candidate names match the explicit Member labels. The repeated page hashes also preserve the exact raw-query order across the two sequential reads. However, no kernel candidate output or renderer was executed or compared; stable kernel output ordering/rendering remains unverified. The current evidence also has no multi-item witness array to test that ordering path.

These captures are sequential, finite `VALUES`/predicate slices, not a transactional snapshot or proof that the source contains every real-world candidate. The bounded provenance-presence query returned zero rows. In particular, the 20-member enumeration establishes coverage only for the frozen R∪K seed set, not global Member coverage. No ontology, repository, kernel, or production-store changes were made; no new captures or agent work were initiated.

## Reproducible review artifacts

- `check.py` — independent raw-capture/quads/date/ownership/seed/collection audit; deliberately does not read the oracle.
- `compare_oracle.py` — post-derivation exact oracle comparison, including candidate and witness ordering.
- `check.log` — successful raw-evidence run.

The original review artifacts were under `/tmp/oireachtasontology/nlq-evidence-freeze/dev-independent-review/`. Durable copies are beside this report; run from the repository root:

```sh
.venv/bin/python docs/reports/query-service/composition-freeze-20261111/development/independent-review/check.py .
.venv/bin/python docs/reports/query-service/composition-freeze-20261111/development/independent-review/compare_oracle.py .
```

Parent integration reran both scripts successfully on 2026-11-12, still pinned to `asOf=2026-11-11`; logs are under `../../verification/`. The review above inspected the then-current 109 control definitions. Two subsequent controls cover ended independent party HouseTerm evidence and an ended containing parliamentary membership in K+P; those additions do not change the source evidence or positive oracles. No control is claimed to have passed a kernel execution.
