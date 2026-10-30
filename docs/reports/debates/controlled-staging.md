# Debates controlled-ingestion implementation and staging report

Assessment date: 2026-10-09; status reconciled 2026-10-12. This report records
implementation and disposable staging evidence. The 2026-10-09 source-backed
owner update supersedes the earlier fixture-only limitation. Subsequent
post-rebase opt-in staging acceptance and Phase 6 A–C implementation/release
acceptance also passed. None of these tests authorizes production publication
or establishes a deployed, recoverable production host. See
[Phase 6 Tranche C acceptance evidence](../etl/phase-6-tranche-c-acceptance.md).

## Implemented

- Manifest-driven selection, exact preserved-source verification, deterministic
  batches (maximum 25 Works / 64 MiB source XML), and inventory quarantine are
  implemented as described in the 2026-10-08 implementation update in
  `debates-production-readiness.md`.
- Manifest-driven publication now requires `--resource-budget-file`. The
  versioned JSON configuration supplies TDB2, temporary, host and process paths
  and may override approved warning/stop limits. Unknown or invalid settings,
  unavailable measurements and an unobservable Fuseki process fail closed.
- The existing Core State -> whole-graph PUT -> exact verification sequence is
  retained. A preflight check runs before the Debates Core State run starts;
  per-graph checks run before publication (after the reference report is
  persisted) and after graph verification. A hard stop before PUT leaves the
  graph untouched; a stop/failure after dirty state is durable leaves that
  existing pending publication available for deterministic retry. No new
  ledger, scheduler or publication state was introduced.
- Resource observations are append-only JSONL outside the protected raw, TDB2
  and Core State paths. They distinguish ETL current/peak RSS, Fuseki process
  RSS, host `MemAvailable`, cgroup available memory when exposed, per-volume
  free space, TDB2/Core State/raw/reference-report/temporary bytes, and the
  projected storage used for the next graph.

Minimal budget configuration (absolute local paths; Fuseki credentials remain
environment-only):

```json
{
  "schema": "debates-resource-budget-v1",
  "paths": {
    "tdb2": "/srv/staging/fuseki/tdb2",
    "temporary": "/srv/staging/tmp",
    "host": "/srv/staging"
  },
  "fuseki_process_match": "org.apache.jena.fuseki.cmd.FusekiCmd",
  "fuseki_cgroup_match": "oireachtas-fuseki.service",
  "observation_file": "/srv/staging/debates-resource-observations.jsonl",
  "limits": {}
}
```

`fuseki_cgroup_match` should identify exactly one target Fuseki JVM; without it,
the process selector must still resolve to exactly one process. Run parameters
record the budget/observation paths. Per-run overrides may lower or adjust the
defaults but must be reviewed as operational configuration.

The default limits encode the proposals in
`debates-production-readiness.md`: TDB2 warning/stop 18/21 GiB; source plus
metadata 3/3.5 GiB; reference reports 8/9 GiB; Core State 3/3.5 GiB; temporary
space 2/3 GiB; ETL RSS 1.5/3 GiB; Fuseki RSS 6/8 GiB; host free space warning
below 80 GiB and hard stop below 65 GiB. TDB2/Core State projections retain
volume reserve; the host threshold is the proposed rebuild headroom. These are
configurable defaults, not calibrated production limits.

## Owner evidence and scope

The pre-existing user Core State database was not opened or migrated. The
preserved `data/raw/members/2026-10-08` material was inspected: its four run
directories contain only small `skip-000000`/`skip-000100` pages, each reporting
one Member, rather than a current complete production owner publication. No
preserved complete Houses or Committee owner capture suitable for this staging
was available. No-owner resolution was not used.

For mechanics testing, the isolated staging Core State and disposable Fuseki
were bootstrapped through the existing owner transformations, source-aware
validators and publication/verification path with these checked-in owner
examples:

| Owner | Input | Input SHA-256 | Validated identities |
|---|---|---|---:|
| Houses | `data/api_examples/houses.json` | `b1f928b74526d7e5186a3ad68a7192a742f1c05eff0543503f78326cf18d21c1` | 4 HouseTerms (8 resolver lookup keys) |
| Members | `data/api_examples/member.json` | `a74c366c1a49c6b1011b76a8c994002d469c927b4e6b9456803c144a4f051d93` | 1 Member (2 resolver lookup keys) |
| Committees | `tests/fixtures/committee-owner.json` | `8a888c2dfba038bff30366b2fe25ec845af9566b59029f6481c42ea2ec0a2df0` | 1 Committee (2 resolver lookup keys) |

These are structurally/source-record validated representative development
examples, **not** current authoritative API captures or complete owner
coverage. Across 49 staged Debate reference reports the resolver exposed 42
distinct Member owner hrefs and four Committee owner hrefs it did not have.
The unresolved Member hrefs are listed below to make the coverage boundary
concrete; the 4 unresolved Committee hrefs were:

```text
/ie/oireachtas/committee/dail/31/an_fochoiste_um_an_straiteis_20_bliain_don_ghaeilge_2010-2030_agus_rudai_gaolmhara
/ie/oireachtas/committee/dail/31/an_fochoiste_um_an_straiteis_20_bliain_don_ghaeilge_2010_2030_agus_rudai_gaolmhara
/ie/oireachtas/committee/dail/31/committee_of_public_accounts
/ie/oireachtas/committee/dail/32/comhchoiste_na_gaeilge_na_gaeltachta_agus_na_noilean
```

The 42 unresolved Member owner hrefs were:

```text
/ie/oireachtas/member/id/Aengus-Ó-Snodaigh.D.2002-06-06
/ie/oireachtas/member/id/Aindrias-Moynihan.D.2016-10-03
/ie/oireachtas/member/id/Brendan-Griffin.D.2011-03-09
/ie/oireachtas/member/id/Brendan-Howlin.S.1983-02-23
/ie/oireachtas/member/id/Brian-Hayes.S.1995-12-20
/ie/oireachtas/member/id/Brian-Ó-Domhnaill.S.2007-07-23
/ie/oireachtas/member/id/Bríd-Smith.D.2016-10-03
/ie/oireachtas/member/id/Catherine-Connolly.D.2016-10-03
/ie/oireachtas/member/id/Cáit-Keane.S.2011-05-25
/ie/oireachtas/member/id/Derek-Nolan.D.2011-03-09
/ie/oireachtas/member/id/Dinny-McGinley.D.1982-03-09
/ie/oireachtas/member/id/Donnchadh-Ó-Laoghaire.D.2016-10-03
/ie/oireachtas/member/id/Eoghan-Murphy.D.2011-03-09
/ie/oireachtas/member/id/Fergus-O'Dowd.S.1997-09-17
/ie/oireachtas/member/id/Fiach-Mac-Conghail.S.2011-05-25
/ie/oireachtas/member/id/Gerald-Nash.D.2011-03-09
/ie/oireachtas/member/id/Gerry-Adams.D.2011-03-09
/ie/oireachtas/member/id/James-Browne.D.2016-10-03
/ie/oireachtas/member/id/Jim-D'Arcy.S.2011-05-25
/ie/oireachtas/member/id/Joe-O'Reilly.S.1989-10-01
/ie/oireachtas/member/id/John-Deasy.D.2002-06-06
/ie/oireachtas/member/id/John-McGuinness.D.1997-06-26
/ie/oireachtas/member/id/Kieran-O'Donnell.D.2007-06-14
/ie/oireachtas/member/id/Labhrás-Ó-Murchú.S.1997-09-17
/ie/oireachtas/member/id/Mary-Lou-McDonald.D.2011-03-09
/ie/oireachtas/member/id/Michael-McCarthy.S.2002-09-12
/ie/oireachtas/member/id/Michael-P-Kitt.D.1975-03-04
/ie/oireachtas/member/id/Micheál-Martin.D.1989-06-29
/ie/oireachtas/member/id/Niall-Ó-Donnghaile.S.2016-04-25
/ie/oireachtas/member/id/Paschal-Donohoe.S.2007-07-23
/ie/oireachtas/member/id/Pat-the-Cope-Gallagher.D.1981-06-30
/ie/oireachtas/member/id/Paul-Connaughton.D.2011-03-09
/ie/oireachtas/member/id/Peadar-Tóibín.D.2011-03-09
/ie/oireachtas/member/id/Pádraig-Ó-Céidigh.S.2016-04-25
/ie/oireachtas/member/id/Robert-Dowds.D.2011-03-09
/ie/oireachtas/member/id/Rónán-Mullen.S.2007-07-23
/ie/oireachtas/member/id/Seán-Fleming.D.1997-06-26
/ie/oireachtas/member/id/Seán-Kyne.D.2011-03-09
/ie/oireachtas/member/id/Shane-PN-Ross.S.1981-10-08
/ie/oireachtas/member/id/Simon-Harris.D.2011-03-09
/ie/oireachtas/member/id/Trevor-Ó-Clochartaigh.S.2011-05-25
/ie/oireachtas/member/id/Éamon-Ó-Cuív.D.1989-06-29
```

Staging reports also observed 6,301 source-placeholder speaker references, 240
unresolved participation-role crosswalk references, and 152 malformed role
fragments; these are report observations, not repairs or new acceptance rules.
The actual graph transform/integration/publication validators passed for the
eligible staged Works. None of these counts establish whole-corpus owner
resolution readiness.

## Disposable staging evidence

The opt-in real-Fuseki acceptance is
`tests/test_debates_staging_acceptance.py`; it requires exact environment paths
and explicit loopback GSP/SPARQL endpoints. It reset only the disposable named
dataset and TDB2 under `/tmp/oireachtasontology/debates-stage-acceptance2`, used
isolated Core State/raw/temp directories, and the local `stain/jena-fuseki:5.1.0`
image. It did not use production services or mutate the older local Core State.
Inputs were the committed inventory and exact preserved Debate XML/metadata
objects from `/var/home/stephen/.cache/oireachtas-assessment/raw`; all selected
source objects were hash-verified by the existing manifest loader. Single
worker; no source ceiling was exceeded.

| Requested batch cap | Selected Works | XML bytes | Successful run result | ETL stage duration | Throughput |
|---:|---:|---:|---|---:|---:|
| 5 | 5 | 506,471 | 5 new/published, 0 quarantine | 6.097 s | 0.82 Works/s |
| 10 | 10 | 1,085,868 | 5 unchanged + 1 recovered/changed + 4 new | 4.537 s | 2.20 Works/s |
| 25 | 25 | 2,867,321 | 10 unchanged + 1 recovered/changed + 14 new | 17.344 s | 1.44 Works/s |

The 10- and 25-Work calibration runs deliberately included interruption and
recovery, so their times are not pristine throughput benchmarks. A 25-Work
quarantine batch (6,101,138 source bytes) withheld one inventoried exception,
published 24 eligible graphs, and completed degraded in 54.980 s (0.44 Works/s).
The quarantine was retained, the eligible siblings remained published, and an
exact retry request followed by replay remained quarantined with
`retry_requested`/`retry_failed` history. Deterministic selection used inventory
batch indices 0 (5/10/25 caps) and 9 (the quarantine batch); the manifest itself
was not modified.

Recovery and preservation evidence:

- Before the 10-Work run, an intentionally lowered TDB2 stop rejected the
  projected write; no Debate graph was dirtied or changed. The failed run was
  recorded in Core State.
- A second deliberate resource stop during replay of an already dirty pending
  graph left its pending payload/hash unchanged. The subsequent normal replay
  completed it successfully.
- A controlled GSP PUT exception after Core State dirty marking left the exact
  pending payload/hash dirty; restart completed that graph and skipped its 5
  already verified siblings.
- A controlled post-PUT exact-verification exception left a dirty pending graph
  after the real GSP PUT; restart verified and cleaned the pending payload and
  skipped the 10 previously verified siblings.
- A pre-existing valid sentinel graph survived all staging and was verified at
  the end. All 49 Debate graphs present at final acceptance were clean. The
  provenance catalog was clean and its exact persisted payload verified against
  Fuseki. No Debates provenance-incomplete publication remained. The isolated
  fixture owner publication remains explicitly marked provenance-incomplete,
  as expected for non-authoritative examples.
- Warning thresholds were deliberately set to 1 byte in the first calibration;
  both ETL and Fuseki warning events were emitted. Hard-stop behavior was
  deliberately triggered as above. No accidental hard stops occurred in the
  ordinary per-graph guards.

Observed resources during this disposable run (binary units; these are actual
checkpoint observations, not production projections):

| Resource | Observed |
|---|---:|
| ETL process peak RSS | 870,928,384 B (830.4 MiB) |
| Fuseki process RSS | 432,599,040 B (412.6 MiB) |
| Host MemAvailable | minimum 5,005,955,072 B (4.66 GiB); observed range 4.66–5.25 GiB |
| TDB2 used | 201,363,628 B initial to 245,210,426 B final; +43,846,798 B |
| Core State SQLite family | 409,600 B initial to 31,477,760 B final; +31,068,160 B |
| Preserved Debate XML/metadata | 8,982,506 B at checkpoints (including staged source files) |
| Reference-report sidecars | 0 B before transformation to 32,541,431 B final (49 reports) |
| Temporary directory | 0 B at observed checkpoints |
| TDB2/raw/Core State/temp filesystem free | minimum 5,952,815,104 B (5.54 GiB) |
| Host free space | minimum 175,958,224,896 B; final 175,971,115,008 B (163.89 GiB) |
| Resource observations | 111 checkpoints; 22 deliberate warning events; 2 deliberately triggered hard stops |

The Fuseki and host memory measurements are distinct from ETL RSS. Temporary
space and storage metrics are checkpoint samples, not continuous maxima. The
measured owner reports and graph count are representative only; no full corpus
was staged and no production-scale memory/storage behavior is inferred from
these values. Detailed raw JSONL observations and the staging SQLite/TDB2 are
disposable under `/tmp`; the test records a compact summary there for review.

## Reproduction

The successful local command used the following explicit test configuration
(password shown here was disposable and is not a production credential):

```bash
stage=/tmp/oireachtasontology/debates-stage-acceptance-final2
mkdir -p "$stage/tdb2" "$stage/runtime-temp"
chmod 0777 "$stage/tdb2" # local Fuseki image runs as its unprivileged fuseki user
docker run -d --name debates-stage-acceptance-final2 \
  -p 127.0.0.1:13038:3030 -v "$stage/tdb2:/fuseki" \
  -e FUSEKI_DATASET_1=debates -e ADMIN_PASSWORD=staging-only \
  stain/jena-fuseki:5.1.0
# Wait until http://127.0.0.1:13037/debates/query is ready.
container_id=$(docker inspect debates-stage-acceptance-final2 --format '{{.Id}}')
export TMPDIR="$stage/runtime-temp"
export OIR_DEBATES_STAGE_ROOT="$stage"
export OIR_DEBATES_STAGE_TDB2="$stage/tdb2"
export OIR_DEBATES_STAGE_HOST=/var/home
export OIR_DEBATES_STAGE_GSP=http://127.0.0.1:13038/debates/data
export OIR_DEBATES_STAGE_SPARQL=http://127.0.0.1:13038/debates/query
export OIR_DEBATES_STAGE_USER=admin OIR_DEBATES_STAGE_PASSWORD=staging-only
export OIR_DEBATES_STAGE_CGROUP_MATCH="docker-${container_id}.scope"
export OIR_DEBATES_EVIDENCE_RAW=/var/home/stephen/.cache/oireachtas-assessment/raw
mise exec -- .venv/bin/python -m pytest -q -s tests/test_debates_staging_acceptance.py
docker rm -f debates-stage-acceptance-final2
```

The disposable Fuseki endpoint must already be running on loopback with an
empty-or-disposable dataset and matching `TDB2` path. For an isolated Fuseki RSS
reading, configure `OIR_DEBATES_STAGE_CGROUP_MATCH` to the target service's
unique cgroup path (the example value is specific to this disposable container
and changes on recreation). The acceptance test
explicitly deletes graphs only through its supplied disposable endpoint and
clears staging files except that TDB2 directory. Never point these variables at
production. `tests/test_debates_staging_acceptance.py` provides the full
per-run/restart/failure assertions; `tests/test_resource_budget.py` covers
independent guard behavior.

## Verification results

- Actual disposable-Fuseki acceptance command above: **1 passed**, 7,224
  rdflib/PySHACL deprecation warnings, 178.33 s. Two resource hard stops were
  deliberately injected and asserted; this is separate from default full-suite
  skips.
- `mise exec -- .venv/bin/python -m pytest -q tests`: **875 passed, 15
  skipped, 23 subtests passed**. Skips include opt-in integration tests that
  require environment-supplied services; the staging acceptance was run
  separately against the configured disposable Fuseki. The suite emitted
  upstream rdflib/PySHACL deprecation warnings; no failures.
- `mise exec -- .venv/bin/python tests/validate.py`: passed; HermiT completed,
  2,504 ontology triples.
- `.venv/bin/python tools/validation.py`: mapping-integrity validation passed
  for all active mapping terms.
- Focused resource/Debates regression run: 41 passed, 2 skipped before the
  final pending-dirty-stop assertion was added; that updated opt-in staging test
  subsequently passed against real Fuseki.

## Source-backed owner evidence (2026-10-09)

The fixture-only evidence above is superseded on owner coverage by the
source-backed isolated staging recorded in
[`debates-production-readiness.md`](production-readiness-history.md#2026-10-09-source-backed-owner-evidence-update).
That exercise used successful complete preserved API captures (1,928 Members,
68 Houses, 11 Parties and 8 Constituencies), source-derived conflict-excluded
Committee candidates, and a read-only-copy Core State snapshot. It indexed 1,928
Members, 65 HouseTerms and 267 Committees in the Debates owner resolver. The
development closure remains non-authoritative/incomplete, and the known
materially conflicting Committee identity remained quarantined and unresolved.

In disposable Fuseki/Core State, **52 unique manifest-selected Debates Works**
were exercised: 25 new Committee graphs published; a second 25-Work batch
published 24 and withheld one inventoried exception; representative 2011 Dáil
and Seanad graphs both published; and exact replay left all 25 graphs unchanged.
Thus the source-backed selections yielded 51 clean published Debate graphs and
one separate quarantine. The earlier fixture-only acceptance's 49 graphs are a
different staging run, not the source-backed publication count. Every Debate
owner snapshot fingerprint, reference report, graph payload and the provenance
catalog was checked against the isolated dataset. For the 49 Works shared with
the fixture run, 7,670 Member-reference outcomes previously
unresolved for lack of an example owner now resolved; 6,301 source-placeholder
Member outcomes remained unresolved. Committee outcomes were 18 resolved and
31 unresolved over three exact historical hrefs. These unresolved historical
references are auditable evidence limitations, not silently guessed owners or
automatic safety blockers; detailed classifications and the full comparison
are in the linked readiness assessment.

This supersedes the former claim below that the example owner inputs were the
only staging evidence. The source-backed result closes the technical
representative owner-evidence gap but does not prove corpus-wide historical
owner resolution or authorize controlled ingestion. Resource budgets remain
provisional, and inventory exception disposition, source-listing/Expression
completeness review and separate human operational authorization are still
required.

## Assessment and remaining gates

**Staging mechanics and representative source-backed owner evidence passed;
production readiness remains BLOCKED pending human decisions and an unverified
deployment-specific coordinated backup/restore prerequisite.** The disposable
Fuseki/Core State path, resource controls, bounded batches, quarantine,
warnings/hard stop, idempotent replay, dirty/pending recovery, catalog
verification and graph preservation passed. The source-backed staging confirms
exact modern Member/House/Committee owner resolution and preserves fail-closed
handling for the conflicting Committee identity. It does not establish complete
historical coverage or production-scale resource behavior. Human review of the
approved resource budgets, inventory exceptions and source completeness, plus a
separate controlled-production execution plan, remain required.

Technical completion of these staging mechanics is **not** authorization to
publish production data. This staging exercise performed no production
ingestion, source repair, ontology/mapping change or semantic acceptance
change. Phase 6 Tranches B/C were subsequently completed and verified using
disposable recovery infrastructure; the production-host gate remains open.

The operator-ready execution and recovery sequence, exact inventory pin,
production owner-snapshot pinning procedure, resource ceilings and backup/restore
go/no-go criteria are in
[`debates-production-execution-plan.md`](production-execution-plan-history.md).
That plan concludes **BLOCKED** until a coordinated backup from the intended
deployment can be restored into isolated infrastructure and all human gates
are closed. Phase 6's representative disposable restore is not that test.
This plan authorizes no production mutation.
