# Debates local snapshot completion

This record closes the local Debates ingestion workstream. It describes a
non-production snapshot only; it does not claim authoritative completeness or
authorize publication.

## Verified snapshot

- Frozen inventory: `documentation/debates-initial-production-inventory.json`,
  SHA-256 `ae07dc7c293bcadef3d17fa52ea19e2b92db5368242a53aefd68ec8ca5f0c4d7`.
- 10,645 eligible Debate Works loaded; four additional eligible Works are
  review-required exceptions with no RDF. The 264 approved inventory
  withholdings remain separate.
- 12,575 named graphs (10,645 Debate and 1,930 owner graphs), 18,377,986
  triples; N-Quads SHA-256
  `d870fb717882340b6906ce33a7c1042d4053ef01275838a2784ede4008c85b32`.
- All 10,913 inventory source and metadata hashes were rechecked. Per-graph
  TDB2 counts and representative Dáil, Seanad and Committee Debate, Member and
  body-owner queries passed.
- Jena emitted 40,578 classified bad-IRI warnings (40,576 illegal-character
  fragment warnings and two illegal-percent-encoding warnings). All 7,307
  distinct affected IRI terms were preserved exactly in TDB2.
- Final run time: 10,503 active seconds, within the four-hour ceiling.
- Manifest SHA-256 at completion:
  `6fe6ac021b304063c8af6ac89bd920ce49b3ea4a12b9ac9d043b4978f77590fb`.
- Production publication was not performed or authorized.

## Review-required source exceptions

These source-verified same-Division opposing-vote conflicts remain isolated
snapshot exceptions; they are not approved withholdings:

| Work date | Member(s) with contradictory source votes |
|---|---|
| 2012-12-20 Seanad | David P.B. Norris |
| 2014-01-28 Seanad | Michael Mullins |
| 2015-05-26 Seanad | Feargal Quinn; Terry Leyden |
| 2018-02-21 Seanad | Paul Daly |

Source-linked diagnoses, reference reports and the exception journal are
preserved under
`/var/home/stephen/.cache/oireachtas-assessment/debates-initial-snapshot-20261025/review-required/`.
No RDF was emitted for these four Works.

## Local artifact and reconstruction evidence

The immutable N-Quads, final manifest, TDB2 load, source captures, owner-page
captures, intermediate checkpoint/journals, loader logs and query-verification
results are outside the Git worktree at:

```text
/var/home/stephen/.cache/oireachtas-assessment/debates-initial-snapshot-20261025/
/var/home/stephen/.cache/oireachtas-assessment/raw/
```

The local query endpoint is `http://127.0.0.1:13032/ds/query`. It serves an
isolated verification copy of TDB2; it does not depend on a development
worktree. The preserved loaded TDB2 is at `.../debates-initial-snapshot-20261025/tdb2/`.

The exact build, resume, exception-isolation, finalization, bulk-load and
verification scripts, with SHA-256 checksums, are preserved in:

```text
/var/home/stephen/.cache/oireachtas-assessment/debates-initial-snapshot-20261025/reconstruction/
```

The pre-existing `cli.py`/`provenance.py` optimization and its CLI test were
not needed by this snapshot integration; their exact diff is preserved as
`reconstruction/unintegrated-cli-provenance.patch` (based on worktree commit
`bd78b026250ba2042c23ca306abf3ab8bd386889`, SHA-256
`7ef84b9f8abaeee9c63736e8840418170c1ffd0e2329f9574994907ccc4fbcee`) for
separate follow-up.

The inputs are the frozen inventory above; immutable Debate XML/metadata under
`raw/debates/sha256/`; and page-hash-verified owner captures in
`raw/members/2026-10-20/run-36bad1be-cff9-45e4-ba0a-3818a2cdb8c8/` and
`raw/houses/2026-10-20/run-ecab0f37-0db6-425f-98ac-b2b26cb031dc/`. The
archived sequence is `run_full_snapshot.sh`, `resume_snapshot.sh`,
`continue_isolated.py`, `finalize_isolated.py`, `load_verify_isolated.sh`, then
`verify_loaded_isolated.sh`; `SHA256SUMS` checks the preserved scripts. They
record the exact `REPO`, `OUT`, `DEBATE_RAW`, `MEMBER_DIR`, `HOUSE_DIR` and
`PYTHONPATH` configuration, plus `stain/jena-fuseki:5.1.0`, phased
`tdbloader2`, 3-GiB/4-CPU loader limits, 20-GiB free-disk and 1.5-GiB available
memory guards, and the 14,400-second active-time ceiling. Replay scripts refuse
to overwrite the existing output; any future rebuild needs a fresh output and
TDB2 target and must point `REPO` at the integrated checkout. No further
processing was started for this integration.

The owner-context implementation in `validation/debates_integration.py`
indexes validated owner graphs once per batch and reuses that context for
Debate validation, avoiding per-Work copies/scans while retaining the
backwards-compatible full-Dataset validator path and fail-closed regression
coverage.
