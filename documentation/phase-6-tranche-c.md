# Phase 6 Tranche C — production acceptance and release gate

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
[`evidence/phase-6-tranche-c-release-gate.json`](evidence/phase-6-tranche-c-release-gate.json).
It records the tested revision, production Compose configuration hash, exact
test groups and durations, isolated infrastructure, backup/restore/rebuild
summary, failure injection, and zero mandatory skips. A new release candidate
must rerun the gate; do not reuse this evidence as acceptance for a different
revision or deployment configuration.
