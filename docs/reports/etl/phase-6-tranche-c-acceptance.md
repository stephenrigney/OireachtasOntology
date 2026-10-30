# Phase 6 Tranche C — production acceptance and release gate

> Historical, revision-bound implementation acceptance evidence. It does not
> authorize deployment or replace current operational procedures. See the
> [ETL architecture](../../architecture/etl.md) and
> [operations guide](../../development/operations.md).

## Gate implementation

Run the opt-in, bounded full-stack release simulation from a clean checkout:

```bash
mise install
uv sync --locked --extra test
scripts/production-release-gate.sh
```

The script writes machine-readable evidence to
`documentation/evidence/phase-6-tranche-c-release-gate.json` by default; pass a
different path as its first argument to select another evidence destination.
It requires Docker Compose v2, the `mise.toml` Java runtime, `restic`, and free
loopback ports 3030 and 13035. The routine push/PR workflow deliberately runs
ontology/mapping validation and regression tests without starting the complete
simulation. The full production release workflow is explicitly dispatched in
GitHub Actions and uploads its evidence artifact.

The gate creates an unpredictable disposable Compose project, starts the
production Compose Fuseki service and a separate test-only Debates Fuseki 5.1.0
dataset, injects gate-only credentials, runs mandatory integration suites, and
removes only those named projects and their volumes. It refuses occupied
required ports and never uses developer state, the ordinary development Compose
project, live external authorities, production services, or production
credentials. A failure reports `BLOCKED`, preserves exact command logs and
cleanup diagnostics under `/tmp/oireachtasontology/phase6-release-gate.*`, and
returns non-zero. A PASS evidence file is written only after all mandatory
groups and the no-skip checks succeed. Review failed command logs and the
Compose cleanup log; do not manually remove any unrelated Docker resources.

## Acceptance coverage

- Ontology parsing, HermiT consistency, mapping integrity and the full existing
  regression suite remain mandatory in the production run.
- Real authenticated Fuseki tests cover graph replacement, Member and Bill
  publication, reconciliation graph isolation, provenance/catalog behavior,
  and representative Debate publication, replay, changed-source replacement,
  and owner-graph isolation. Existing regression coverage also exercises
  quarantine, record/source/run failure classification, incomplete-source
  protection, additive and contract-breaking source drift, external outage and
  recovery state, retries/caching, reviewed decision precedence, alert delivery
  and suppression, systemd contracts, and recovery-wrapper failure handling.
- The real-backup test uses the production `BackupEngine` and installed Restic
  binary to back up four SQLite stores and raw evidence, verify repository and
  snapshot integrity, restore to a new independent location, validate restored
  Core State, and reconstruct/verify a fresh Fuseki dataset from the restored
  durable publication evidence. It injects a graph PUT interruption, confirms
  exact dirty-payload replay, and injects a rebuild into a non-empty dataset to
  prove fail-closed behavior without damaging the verified projection.
- Compose production configuration is validated and its persistent Fuseki
  service is actually started with a disposable bind-mounted data directory.
  The existing wrapper/systemd acceptance tests compare manual and scheduled
  command paths, verify alert/hook behavior, and exercise recovery cutover
  failure/rollback guards using deterministic Docker command doubles.

The targeted real Fuseki test set emits JUnit XML and the script fails closed
when a mandatory test is skipped. The broader repository suite can report
skipped optional tests; this is not used as the mandatory integration result.

## Systemd and deployment boundary

CI does not start or enable host systemd timers: doing so would require host
service-manager privileges and could create uncontrolled scheduled work. It
validates installed unit/timer contracts and invocation wiring, not unattended
operation. A deployment host must still provision the protected runtime file,
credentials, notification destination, durable paths, timers, permissions,
and site-specific schedule; then an operator must test those services and the
recovery drill on that host before enabling recurring jobs.

This acceptance result is implementation evidence only. It is not production
host provisioning, a security review, a private-beta approval, deployment
authorization, Debates ingestion authorization, or evidence of production
source completeness. The private-beta plan's design, staging-security, launch,
and evaluation gates remain separate and unchanged. The controlled Debates
production plan remains **BLOCKED** pending its explicit human decisions,
source/owner evidence and deployment-specific prerequisites.

## Recorded result

The latest committed evidence is
[`phase-6-tranche-c-release-gate.json`](../../../documentation/evidence/phase-6-tranche-c-release-gate.json).
It records the tested revision, production Compose configuration hash, exact
test groups and durations, isolated infrastructure, backup/restore/rebuild
summary, failure injection, and zero mandatory skips. A new release candidate
must rerun the gate; do not reuse this evidence as acceptance for a different
revision or deployment configuration.

## Final implementation acceptance record — 2026-10-12

**Phase 6 implementation complete — production deployment not yet authorised.**
Tranches A, B and C are accepted and merged into `master`. The exact accepted
implementation revision is
`d9b65080efcfae0cb16b0cc6ae0e16ad97782572` (Tranche C implementation commit
`5b324a27620fea33dc3eef2602e5a267c239271b`; evidence commit
`d9b65080efcfae0cb16b0cc6ae0e16ad97782572`).

- The local disposable release gate passed on `5b324a27620fea33dc3eef2602e5a267c239271b`; its committed evidence is
  [`phase-6-tranche-c-release-gate.json`](../../../documentation/evidence/phase-6-tranche-c-release-gate.json).
- The hosted **Production release gate** passed against the merged revision in
  [GitHub Actions run 38304245816](https://github.com/stephenrigney/OireachtasOntology/actions/runs/38304245816).
  Job `disposable-full-stack-acceptance` passed all steps. The uploaded artifact
  is `phase-6-tranche-c-release-gate-d9b65080efcfae0cb16b0cc6ae0e16ad97782572`
  (artifact ID `11772055770`). Its report matches the tested revision and
  Compose hash, reports all ten groups PASS, cleanup PASS, and zero mandatory
  skips. The mandatory integrated acceptance reported 32 tests with no skips,
  failures or errors; the mandatory real-Fuseki Debates test reported one test
  with no skip. The report records four backed-up SQLite stores, independent
  restore with Core State integrity `ok`, two rebuilt/verified graphs and 283
  triples, exact dirty-payload replay, and fail-closed rejection of a non-empty
  rebuild. Both Compose projects and disposable storage were removed; no
  production credentials/services or external authorities were used.
- The routine **Validation** workflow also passed on the merged revision in
  [GitHub Actions run 38304223589](https://github.com/stephenrigney/OireachtasOntology/actions/runs/38304223589).
  Its broader optional regression suite reported 939 passed and 16 skipped;
  those optional skips do not alter the zero-skip result for mandatory release
  acceptance tests.

### Non-blocking acceptance limitations

- The release gate runs ETL tests from the host `.venv` and invokes the runner's
  installed Restic binary. It validates the production Compose configuration
  and starts real disposable Fuseki services, while wrapper/systemd invocation
  tests use deterministic Docker doubles; it does not build and run the
  production `etl`/`ops` container image. The workflow installs Restic through
  the runner package manager, whereas the production image pins Restic 0.19.1.
  The production image/runtime path therefore remains for deployment-specific
  verification.
- The script's default evidence destination is reused across invocations
  (`scripts/production-release-gate.sh:30,82-105`). A failed rerun with clean
  cleanup can leave an earlier PASS file in place, while a cleanup failure can
  rewrite an earlier result to BLOCKED without that file describing the failed
  attempt. Early preflight failures can also produce misleading Compose-cleanup
  diagnostics because cleanup is attempted before runtime env files exist
  (`scripts/production-release-gate.sh:54-81`). The accepted run is supported
  by its revision-bound hosted artifact and the committed local evidence; this
  low-severity evidence-lifecycle/diagnostic issue is a follow-up, not a reason
  to reuse a result for another revision.

### Separate deployment and beta gates

Implementation acceptance does not authorize production deployment. The
following deployment-specific prerequisites remain outstanding and must not be
treated as complete:

- provisioned production host and protected runtime configuration;
- production credentials, notification destination and backup repository;
- verified installed systemd services and timers;
- a successful deployment-specific backup/restore drill;
- production endpoint access controls and security review;
- separate private-beta deployment approval; and
- separate Debates production-ingestion authorisation, including approved
  operational budgets, corpus-completeness boundary, owner authority and
  exception dispositions.

The private-beta design, staging-security, controlled-launch and evaluation
gates in `docs/development/private-beta-proposal.md` remain separate. The
controlled Debates production plan remains blocked pending its own decisions and
evidence. No production deployment, private beta, or Debates production
ingestion is authorised by this implementation acceptance.
