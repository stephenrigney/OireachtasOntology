# Production operations — Phase 6 Tranche B

This is an operations guide to the implementation currently in this checkout.
It describes the initial single-host Compose deployment, systemd jobs, backup
and restore commands, and Fuseki projection reconstruction. It is not a
production acceptance result: Tranche C's disposable release gate and
production/ external-service testing are not claimed here. Debates production
ingestion is explicitly out of scope.

## Operating boundaries

- Core State, reconciliation state, the other two application SQLite stores,
  preserved raw evidence, versioned review/registry inputs, and the deployed
  code/configuration are the reproducibility boundary. They are the backup and
  recovery inputs; Fuseki/TDB2 is a replaceable projection, not canonical ETL
  state.
- Each ETL publication is validated and whole-graph verified. A multi-graph run
  is not one remote transaction. A dirty publication is recovered from its
  exact saved payload, not by guessing or resuming the interrupted process.
- External lookups/reconciliation are independent of authoritative ETL
  publication. External HTTP caches are process-local; the reconciliation
  SQLite store holds durable due/review/publication history.
- Use the `scripts/production-compose.sh` wrapper for manual production
  commands. It reads the same protected runtime environment and Compose project
  used by systemd. Do not run an unconfigured container or `oir-etl` directly
  against production state.
- The configured operation lock is host-local advisory `flock` coordination,
  not a distributed lock. Keep all state writers, backups, restore activation,
  and projection reconstruction on this host and on the same mounted lock path.

## Single-host layout

The Compose file is `compose.production.yml`; the local-development Compose
file is separate. The ETL and operations images are built from `Dockerfile`.
Fuseki 5.1.0 is the persistent service, published only on
`127.0.0.1:${FUSEKI_BIND_PORT:-3030}`. ETL and operations containers are
short-lived `compose run --rm` jobs, run as UID/GID 10001 by default, with a
read-only container root, dropped Linux capabilities, and a bounded `/tmp`
tmpfs (4 GiB by default). The Fuseki data volume named `fuseki-data` binds to
the explicit host directory `OIR_FUSEKI_DATA_DIR`.

Example host-side locations (the values are deployment choices):

| Host path | Purpose |
|---|---|
| `/opt/oireachtas-etl` | Versioned project checkout; the systemd units use this fixed path. |
| `/etc/oireachtas-etl/production.env` | Root-controlled, shell-compatible runtime configuration and Fuseki password. |
| `/etc/oireachtas-etl/restic-password` | Restic encryption password file, mounted read-only into the ops container. |
| `/var/lib/oireachtas-etl-root` | Durable ETL state parent and shared `operations.lock`; Compose mounts it at `/var/lib/oireachtas-etl-root`. |
| `/var/lib/oireachtas-etl-root/live` | Four live SQLite stores and `raw/` evidence. |
| `/var/lib/oireachtas-fuseki` | Example persistent Fuseki/TDB2 directory, separate from canonical state and backups. |
| `/var/backups/oireachtas-etl` | Host directory mounted by ops; the configured Restic repository is `restic/` below it. |

Keep the durable state, Fuseki data, Restic repository, and runtime secrets in
separate protected locations. `OIR_BACKUP_DIR` must not be inside the ETL
backup source roots. The Compose configuration uses a local host path for the
Restic repository; it does not replicate that repository off-host. A failure
of the host or its storage can therefore destroy both primary data and the
local recovery points unless the host storage layer separately protects or
replicates them.

The ETL backup explicitly snapshots these SQLite stores: `core-state.sqlite`,
`reconciliation.sqlite`, `office-occurrences.sqlite`, and
`bill-sponsors.sqlite`. It uses SQLite's online backup API while holding the
operation lock. It also backs up the configured raw-evidence root and explicit
project roots for source, ontology, mappings, reconciliation reviews,
registries, the production Compose launcher, deployment, and selected project
configuration. Human documentation and development scripts are excluded; they
are version-controlled release material and may contain intentionally
disposable credentials in examples.
SQLite files are rejected from ordinary file roots. Fuseki/TDB paths are not
backup inputs. Secret-named files, `.env*`, private-key files, development
directories, and selected metadata sidecars are excluded; secret-like content
in included configuration is rejected. The host runtime env file and Restic
password are not part of the ordinary backup. Keep a protected, recoverable
copy of required runtime settings and credentials outside that backup.

## Clean-host provisioning

1. Provision a Linux host with systemd, Git, Docker Engine and the Docker Compose
   v2 plugin. The host does not need the Python project environment; the image
   supplies Python, the pinned project dependencies and Restic. Provide enough
   host capacity for Fuseki/TDB2, raw evidence, the Restic repository, and the
   default 4 GiB ETL/ops tmpfs. The host must be able to pull the Docker build
   base images and the Fuseki image.
2. Check out the intended reviewed release at `/opt/oireachtas-etl` as a Git
   working tree. `production-compose.sh build` records the current Git `HEAD`
   for `BUILD_INFO`; it fails if this directory is not a Git checkout, but it
   does not reject uncommitted changes. Verify the checkout is clean and
   reviewed before building. The source tree is copied
   into the image; `.dockerignore` excludes Git metadata, local environments,
   tests and the `data/` tree.
3. Create the host directories named by the runtime file below. The ETL/ops
   container UID/GID must be able to write the durable parent and backup
   directory. With defaults, that is `10001:10001`; if changing
   `OIR_CONTAINER_UID`/`OIR_CONTAINER_GID`, make host ownership/access agree.
   Ensure Fuseki's own container can write its host data directory; the Compose
   file does not set a host-side Fuseki UID. Create the `live/raw` directory
   before the first backup. Keep Fuseki's data directory separate and persistent.
   For the example paths and default ETL/ops identity, host setup can start with:

   ```sh
   sudo install -d -o 10001 -g 10001 -m 0750 \
     /var/lib/oireachtas-etl-root /var/lib/oireachtas-etl-root/live/raw \
     /var/backups/oireachtas-etl
   sudo install -d -m 0750 /var/lib/oireachtas-fuseki
   ```

   Adjust the ETL/ops owner/group if configured UID/GID differs. Set the
   Fuseki data-directory access according to the selected Fuseki image's
   runtime identity; that identity is not fixed in this Compose file.
4. Create `/etc/oireachtas-etl/production.env`, owned by root and mode `0600`.
   It is sourced by Bash and also passed to Docker Compose as an env file, so
   use assignments valid for both parsers. It is trusted configuration, not
   source/API content. Do not put it in the project checkout or ordinary
   backup.
   For example, create the protected location/file before editing it with the
   complete settings:

   ```sh
   sudo install -d -o root -g root -m 0750 /etc/oireachtas-etl
   sudo touch /etc/oireachtas-etl/production.env
   sudo chown root:root /etc/oireachtas-etl/production.env
   sudo chmod 0600 /etc/oireachtas-etl/production.env
   sudoedit /etc/oireachtas-etl/production.env
   ```
5. Create a high-entropy `FUSEKI_ADMIN_PASSWORD` in that file. This same
   credential is passed at runtime to Fuseki and ETL/ops; it is not built into
   the image. Docker administrators can inspect container configuration, so
   restrict host/Docker access as privileged access. Create the Restic
   password separately at `OIR_RESTIC_PASSWORD_SOURCE`. It is mounted read-only
   as `/run/secrets/restic-password`; make it readable by the configured
   container UID/GID (for example, root-owned with read permission only for the
   container's dedicated group; with defaults, `root:10001` and mode `0440`),
    and not readable by other host users. Preserve both secrets through an
    approved secret-management channel. Losing the Restic password makes
    encrypted backups unusable.
6. Install the systemd files listed below, then initialize durable stores and
   the Restic repository before enabling timers. Follow the first-start
   sequence in the next section.

### Runtime environment

The default file is `/etc/oireachtas-etl/production.env`; the wrapper can read a
different file when `OIR_RUNTIME_ENV_FILE` is set. The installed systemd units
set the default path explicitly. Required host-side settings are:

| Setting | Required value/meaning |
|---|---|
| `OIR_PROJECT_DIR` | Absolute project checkout path; use `/opt/oireachtas-etl` with the supplied units. |
| `OIR_DURABLE_PARENT` | Existing host directory bind-mounted at `/var/lib/oireachtas-etl-root`; contains `live/` and `operations.lock`. |
| `OIR_BACKUP_DIR` | Existing host directory for the local encrypted repository, mounted at `/var/backups/oireachtas-etl`. |
| `OIR_RESTIC_PASSWORD_SOURCE` | Existing protected host password file, mounted read-only into ops. |
| `OIR_FUSEKI_DATA_DIR` | Existing host directory used as the bind source for the persistent `fuseki-data` volume. |
| `FUSEKI_ADMIN_PASSWORD` | Non-empty Fuseki admin password; also used by ETL/ops. |
| `OIR_DAILY_ENDPOINTS` | Non-empty, whitespace-separated endpoint tokens for the scheduled `oir-etl run` invocations. Choose and review the deployment set; do not include `debates`. |
| `OIR_RECONCILIATION_ENDPOINTS` | Non-empty, whitespace-separated endpoint tokens for scheduled `oir-etl reconcile ENDPOINT --publish` invocations. Choose and review the set. |

The supported `run` endpoint tokens include `houses`, `parties`,
`constituencies`, `committees`, `administrative-units`, `offices`, `members`,
and `bills`; the wrapper explicitly rejects `debates`. Reconciliation tokens
are `members`, `parties`, `institutions`, `offices`, `office-external`, and
`bills-local`. The implementation does not prescribe a site-specific value
for either endpoint list. Values are split on whitespace, not commas.

Compose/runtime defaults which may be overridden in the same file:

| Setting | Default |
|---|---:|
| `OIR_COMPOSE_PROJECT` | `oirechtas-etl-production` |
| `OIR_ETL_IMAGE_TAG` | `phase6` |
| `OIR_CONTAINER_UID` / `OIR_CONTAINER_GID` | `10001` / `10001` |
| `OIR_TMPFS_SIZE` | `4g` |
| `FUSEKI_BIND_PORT` | `3030` (still bound to loopback only) |
| `OIR_API_LIMIT` / `OIR_API_RETRIES` / `OIR_API_TIMEOUT` | `100` / `3` / `30` seconds |
| `OIR_BILLS_CURSOR_OVERLAP_SECONDS` | `3600` |
| `OIR_BACKUP_KEEP_DAILY` / `OIR_BACKUP_KEEP_MONTHLY` | `30` / `12` |
| `OIR_BACKUP_RPO_HOURS` | `24` |

Compose fixes the in-container paths: operation lock at
`/var/lib/oireachtas-etl-root/operations.lock`, the four SQLite stores and
`raw/` below `/var/lib/oireachtas-etl-root/live`, Restic repository at
`/var/backups/oireachtas-etl/restic`, Restic password at
`/run/secrets/restic-password`, and Fuseki endpoints at
`http://fuseki:3030/houses/{data,query}`. The Fuseki admin username is `admin`.

### Systemd installation

Install these files into `/etc/systemd/system/`:

- `oir-fuseki.service`
- `oir-etl.service` and `oir-etl.timer`
- `oir-reconcile.service` and `oir-reconcile.timer`
- `oir-backup.service` and `oir-backup.timer`
- `oir-backup-check.service` and `oir-backup-check.timer`
- `oirechtas-ops-failure@.service`

For example, install the supplied unit files with:

```sh
sudo install -m 0644 /opt/oireachtas-etl/deployment/systemd/*.service /etc/systemd/system/
sudo install -m 0644 /opt/oireachtas-etl/deployment/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Do not enable the timers until the initial durable stores and first backup have
been checked. The one-shot ETL/reconcile/backup services are started by their
timers, not enabled directly. The supplied local times are
02:00 ETL, 03:00 reconciliation, 04:00 backup, and 05:00 backup check. Timers
are persistent across downtime; ETL/reconciliation have up to 15 minutes and
backup/check up to 10 minutes randomized delay (with 1-minute accuracy).
Schedules use the host's systemd calendar/timezone. The code does not provide a
site-specific endpoint list or alert threshold.

### First start

After creating the directories/env file and installing the unit files,
initialize state and seed/verify the first backup before enabling the scheduled
jobs:

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh build
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops state initialize
sudo systemctl enable --now oir-fuseki.service
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup init
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup create
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup check
sudo systemctl enable --now oir-etl.timer oir-reconcile.timer oir-backup.timer \
  oir-backup-check.timer
```

`state initialize` creates/migrates all four stores under the configured
durable root. It and backup creation use the shared operation lock. `backup
init` explicitly initializes the encrypted Restic repository; it is not
implicit. A successful `backup check` is required before relying on the first
recovery point. Fuseki is started separately by systemd; the ETL wrapper also
ensures Fuseki is healthy before a normal ETL/reconciliation invocation.

## Manual operations, updates, and locking

Examples (run as an account permitted to use the Docker daemon; the supplied
systemd units run the wrapper as root):

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh run-etl houses members bills
sudo /opt/oireachtas-etl/scripts/production-compose.sh run-reconciliation members parties
sudo /opt/oireachtas-etl/scripts/production-compose.sh etl state status
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup status
```

With no explicit endpoint arguments, `run-etl` and `run-reconciliation` use
their corresponding env-file endpoint lists. `run-etl` invokes endpoints in
sequence as separate ETL commands; it is not a cross-endpoint transaction.
For a one-off supported application command use `etl ARGS...` or `ops ARGS...`
through the same wrapper. Do not use its `etl` route to run Debates; the wrapper
blocks `oir-etl run debates` as well as `run-etl debates`.

The supplied units use these same wrapper paths: `oir-etl.service` calls
`run-etl`, `oir-reconcile.service` calls `run-reconciliation`, backup calls
`ops backup create`, and the check calls `ops backup check`. Thus manual and
scheduled ETL/reconciliation share the same container image, environment and
CLI path.

To update, stop the timers first so no new job starts; let any active one-shot
finish rather than killing it mid-publication:

```sh
sudo systemctl stop oir-etl.timer oir-reconcile.timer oir-backup.timer oir-backup-check.timer
sudo systemctl list-jobs
```

Wait until active one-shot services finish. Update `/opt/oireachtas-etl` to the
intended reviewed Git release, install changed units if applicable, run
`systemctl daemon-reload`, and rebuild with
`scripts/production-compose.sh build`. Start the Fuseki unit if it was stopped,
check the backup repository, and run any site-approved manual ETL check through
the wrapper before re-enabling timers:

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup check
# If approved for this release window, run the configured endpoint set:
sudo /opt/oireachtas-etl/scripts/production-compose.sh run-etl
sudo systemctl enable --now oir-etl.timer oir-reconcile.timer oir-backup.timer \
  oir-backup-check.timer
```

The build uses `docker compose build --pull`
for `etl` and `ops`; Fuseki's configured image/version is separate. Preserve
the same Compose project name, durable directories, and secrets across a
routine update. Check unit/timer state before treating the update as operational.
No automatic image-update or rollback mechanism is supplied.

The ETL CLI acquires `OIR_OPERATION_LOCK_FILE` for state-mutating `run`,
`reconcile`, and quarantine-retry commands when configured. Production Compose
sets all these clients to the same host-mounted lock. `oir-ops backup create`
holds that lock across SQLite snapshots, file capture, Restic snapshot and
retention. State initialization and restore activation also use it. This
prevents a coordinated writer from changing inputs during the backup and
serializes activation and projection reconstruction with an active writer.
Projection reconstruction holds it from the consistent SQLite read through
the final graph verification. It is an advisory POSIX lock on one host only.
Keep schedules stopped through a restore and projection verification: taking
the lock does not prevent a timer from starting a new run immediately after it
is released.

Not every ops command takes the lock: snapshot listing/status/check and staged
`backup restore` do not change live state. In a recovery, stop
ETL/reconciliation timers and wait for active jobs before activation and
reconstruction. The lock prevents overlap with a running writer, but does not
prevent a new scheduled job from starting as soon as the command releases it.
Do not add a second host or run writers outside the wrapper and expect this lock
to coordinate them.

## External-service resilience and state

Compose passes these controls into the ETL container (defaults match the
Phase 5 operations note):

| Setting | Default | Effect |
|---|---:|---|
| `OIR_WIKIDATA_CACHE_TTL_SECONDS` | `300` | In-memory successful Wikidata response TTL; `0` disables cache. |
| `OIR_WIKIDATA_CACHE_MAX_ENTRIES` | `256` | Maximum cached Wikidata responses in one command. |
| `OIR_WIKIDATA_REQUESTS_PER_SECOND` | `2` | Wikidata API/SPARQL network rate; `0` disables throttling. |
| `OIR_DBPEDIA_CACHE_TTL_SECONDS` | `300` | In-memory successful DBpedia response TTL; `0` disables cache. |
| `OIR_DBPEDIA_CACHE_MAX_ENTRIES` | `128` | Maximum cached DBpedia responses in one command. |
| `OIR_DBPEDIA_REQUESTS_PER_SECOND` | `1` | DBpedia network rate; `0` disables throttling. |
| `OIR_EXTERNAL_HTTP_RETRIES` | `3` | Retries after the initial request (bounded to 0–10). |
| `OIR_EXTERNAL_HTTP_BACKOFF_BASE_SECONDS` | `0.5` | Exponential backoff base with full jitter. |
| `OIR_EXTERNAL_HTTP_BACKOFF_MAX_SECONDS` | `8` | Maximum retry delay. |

The response cache is command-scoped and in-memory; there is no second durable
queue/cache. Due/stale/degraded and publication history belongs to
`/var/lib/oireachtas-etl-root/live/reconciliation.sqlite`; human review
decisions remain in the versioned files under `reconciliation/`. A
reconciliation outage does not invalidate an otherwise successful authoritative
publication; the next applicable complete-source reconciliation can rediscover
work that was not durably marked due. External lookup failure does not silently replace
human-reviewed identities or erase a previously accepted graph. Inspect the
reconciliation command's JSON `run_summary` and journal output for selected,
overdue, unresolved/dirty/degraded, coverage/review and recovered-payload
counters; those request/cache counts describe that command only. Projection
rebuild reads durable state/history and the saved office registry; it makes no
external network calls.

## Backups, retention, integrity, and RPO

The scheduled backup runs daily at approximately 04:00. `backup create` holds
the lock and uses SQLite online snapshots, hashes an explicit file manifest,
and writes an encrypted Restic snapshot to
`/var/backups/oireachtas-etl/restic` using the mounted password file. It then
applies Restic `forget --prune` retention for the `oireachtas-etl` tag and
fixed `oireachtas-etl` host identifier: 30 daily plus 12 monthly recovery
points by default. The
repository should be monitored for space and host-disk capacity; retention is
applied after the snapshot operation and a retention failure can make the
service fail even if a snapshot was already created.

The daily check is ordered after the backup service in systemd (ordering does
not require the backup service to have succeeded) and defaults to a full
`restic check --read-data` plus a temporary restore/hash/SQLite
validation of the latest snapshot. It also checks that the newest snapshot is
not in the future and is no older than `OIR_BACKUP_RPO_HOURS` (24 by default).
`oir-ops backup status` and `oir-ops backup check` output JSON; the default
commands return non-zero unless RPO age, repository integrity, and latest
snapshot integrity all pass. A check with no snapshots is unhealthy. Optional
`--skip-integrity-check` and `--skip-snapshot-restore-check` switches are for
deliberately lighter manual probes, not the scheduled check. `backup list`
shows retained IDs and times. RPO here is backup age; it is not an ETL/source
freshness measurement. No RTO is defined.

Useful commands:

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup list
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup check
sudo systemctl list-timers 'oir-*'
sudo systemctl status oir-backup.service oir-backup-check.service
sudo journalctl -u oir-backup.service -u oir-backup-check.service --since today
```

If the check fails, preserve its JSON/journal output, inspect repository
availability, password-file readability, host disk space, last snapshot time,
and integrity result. Do not treat a configured timer or a snapshot listing as
proof of a usable restore; resolve the failure and require a passing full check.

## Operator-triggered durable-state restore

Restoration is staged and explicit. It never overwrites live files as part of
`backup restore`; the selected snapshot ID is mandatory, the destination must
be new, and the staged manifest, content hashes and SQLite integrity are
validated before the destination is created.

1. Stop the ETL, reconciliation, backup and backup-check timers. Let any active
   one-shot finish; do not kill an ETL job during publication. Keep timers
   stopped until restore and projection verification complete. Check
   `backup check` and choose the intended explicit snapshot with `backup list`.
2. Stage it at a unique path under the durable parent but **outside** `live/`;
   the command path is inside the ops container and maps to the host bind mount:

   ```sh
   sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup restore \
     SNAPSHOT_ID --destination /var/lib/oireachtas-etl-root/restore-2026-10-09
   ```

   Do not reuse an existing stage directory. Inspect the command's
   `backup_restored_to_staging` result and retain the stage until recovery is
   verified. The stage includes backup file roots as well as four SQLite
   snapshots and raw evidence; activation installs only the four stores and
   `raw/` into the configured live root.
3. If a configured live SQLite file or raw root is missing, `backup restore`
    currently cannot resolve its configured backup inputs. With all writers
    stopped, preserve the damaged `live/` directory under a unique name if it
    exists, create an empty `live/raw`, and use `ops state initialize` to create
    all four configured stores. Then retry staging to a new destination. This
    prepares the resolver only; it is not the restored state. If the stores
    exist but are corrupt, staging can still validate the repository copy;
    activation preserves the old live directory rather than deleting it.
4. After reviewing the chosen snapshot and stopping scheduled ETL, activate it
    with both the explicit configured target and the confirmation flag. Stop
    `oir-fuseki.service` before activation and keep it stopped until the restored
    canonical state has been projected into a fresh dataset. This avoids serving
    the old projection as if it matched the restored state.

    ```sh
    sudo /opt/oireachtas-etl/scripts/production-compose.sh ops state activate-restore \
      --staged-root /var/lib/oireachtas-etl-root/restore-2026-10-09 \
      --target-root /var/lib/oireachtas-etl-root/live \
      --confirm-replace-existing
    ```

    Activation takes the operation lock, revalidates all staged files and the
    four supported application schemas, requires the target to equal the parent
    of the configured Core State database, and renames the existing live
    directory aside before installing the restored one (with rollback of the
    first rename if the second fails). It reports the preserved previous-state
    path. It does not restore credentials, the image, Fuseki/TDB2, or host
    runtime configuration. It does not resume schedules. Do not delete the old
    live directory or stage until the restored system is accepted. The activator
    requires database schemas supported by the current release and does not
    migrate a restored schema during activation. If a snapshot has a different
    schema, it refuses; use only a compatible release and supported migration
    path, and do not bypass validation.

If only Fuseki/TDB2 is lost or suspect and durable state is sound, do not roll
back canonical SQLite state just to recover the projection. Use the fresh-store
reconstruction procedure below.

## Fresh Fuseki projection reconstruction

`oir-ops projection rebuild --confirm-empty-target` rebuilds from the exact
published payloads held in Core State and the saved reconciliation state. It
requires the current supported Core State schema, the reconciliation SQLite
file, the versioned `registries/ministerial-office-registry.json`, and valid
Fuseki GSP/query endpoints and credentials. It first requires an empty Fuseki
dataset. It validates payload hashes and RDF before PUTs, then replaces and
whole-graph verifies each named graph and checks the final graph inventory.
There are no API/Wikidata/DBpedia calls during reconstruction.

For authoritative graphs it uses the clean published payload, or, for a dirty
publication, the exact hash-checked pending payload as the recovery boundary.
It includes the persisted provenance catalog when present. For external-link
graphs, clean published hashes are reconstructed from the append-only
reconciliation attempts and successful publication history; a later failed or
unresolved lookup does not erase an accepted graph. Dirty external publications
use their saved pending payload. Missing/corrupt hashes or insufficient
publication history fail closed rather than inventing assertions.

After durable restore or Fuseki loss, keep ETL/reconciliation schedules stopped
and ensure the target is a fresh empty TDB2 directory. The configured data
directory is the host path `OIR_FUSEKI_DATA_DIR`; preserve any old directory
under a unique name rather than deleting it or using `docker compose down -v`.
With `oir-fuseki.service` stopped, move the failed/old directory aside, create
an empty directory at the configured host path with write access for the
Fuseki image, and start the service. Confirm its Compose health check, then run:

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops projection rebuild \
  --confirm-empty-target
```

Success reports verified graph and triple counts and whether the provenance
graph was present. If it fails after any PUT, it may have left a partial
projection. Do not resume ETL or treat that dataset as rebuilt; stop Fuseki,
preserve the partial data directory, make another fresh empty directory at the
configured path, and retry after diagnosing the failure. Only resume schedules
after the rebuild command succeeds and the operator has inspected its result,
Core State status and systemd/journal health.

**Important recovery limitation:** reconstruction writes graph-by-graph into
the empty dataset; there is no whole-dataset transaction, separate staging
Fuseki, or atomic cutover command. The Compose Fuseki port is loopback-bound,
but local clients can still observe a rebuild in progress. Therefore this tool
is not a safe atomic replacement of a live non-empty production dataset. If
production requires uninterrupted/atomic serving during recovery, stop and
obtain an approved cutover design rather than inventing one with these
commands.

## Recovery drill

The supplied `oir-backup-check.timer` verifies Restic repository/read-data
integrity and restores the latest snapshot to a temporary directory for
manifest/hash/SQLite checks. It does **not** activate a restore or rebuild a
Fuseki dataset. There is no supplied automated restore/rebuild drill timer.
Phase 6 calls for periodic disposable restore/rebuild verification; until that
is implemented and accepted, arrange a separately approved manual drill
cadence and record its results.

Run a drill only against disposable state, backup-repository and TDB paths and
a distinct `OIR_COMPOSE_PROJECT`; use the same reviewed application release.
Use a separately controlled copy of an encrypted recovery repository and its
password—never let a drill run backup creation/retention against the production
repository. Set a non-conflicting loopback `FUSEKI_BIND_PORT`. Initialize
empty disposable stores and `raw/` first, because staged restore currently
requires the configured source paths to exist; stage a selected snapshot,
activate to that disposable `live/`, create a fresh disposable Fuseki data
directory, and run the same projection rebuild command. Verify its graph
summary, backup check against the drill repository, and captured journal
output. Do not install/enable production systemd timers in the drill project.

## Monitoring, troubleshooting, and limitations

- Inspect scheduled execution with `systemctl list-timers 'oir-*'`,
  `systemctl status`, and `journalctl -u UNIT`. The supplied
  `oirechtas-ops-failure@.service` writes a local syslog error on systemd unit
  failure, with a pointer to the journal and backup check. It does not send
  email, page an operator, or call an external alert service.
- ETL emits structured JSON Lines to stderr and persists run summaries/outcomes
  in Core State. Use `scripts/production-compose.sh etl state status` and inspect
  its run, dirty/missing publication, quarantine, catalog and
  provenance-incomplete fields. A failed
  systemd job is not the only condition to inspect; review degraded outcomes
  and repeated source/external failures in the run/reconciliation output.
- Repeated ETL publication errors: inspect the specific run outcome, source
  drift/quarantine, Fuseki health, and dirty graph/catalog state. Do not clear
  dirty markers or manually edit SQLite; rerun the applicable operation only
  through its normal CLI recovery path.
- Fuseki unavailable: inspect `oir-fuseki.service`, Docker's container status
  and the Fuseki container logs; check host directory permissions, disk capacity,
  loopback port collision, and the admin password. The Compose health check is
  an authenticated ping, not a graph completeness check.
- Backup failures: inspect journal/JSON output, mount and password-file
  readability for UID/GID 10001 (or configured values), repository storage,
  disk capacity, source roots, and `ops backup check`. Do not include SQLite
  files as ordinary roots or place the Restic repository inside a backup source
  tree.
- Restore activation refusal: verify the staged manifest, exact snapshot,
  current code/schema compatibility, all four staged stores, and that
  `--target-root` is precisely the configured Core State directory. The
  confirmation flag is mandatory; it is not a substitute for stopping timers.
- Projection rebuild refusal: verify the dataset is truly empty, the matching
  Core State schema, reconciliation database and office registry exist, and
  all persisted publication hashes/history validate. Never point the command
  at a non-empty production dataset to “repair” it.
- Backups are local-path Restic snapshots in this Compose deployment; no
  off-host copy, RTO, or automatic full recovery orchestration is configured.
  The backup checker is not a complete disaster-recovery proof. Production
  acceptance, disposable full-stack release testing, external/production
  testing, and Debates ingestion/readiness are not claimed by this guide.

## Contract gaps to resolve before production acceptance

The implementation is documented as-is above. These gaps should be reviewed;
this guide does not invent a substitute behavior:

1. Phase 6 requires failed-run alerting and alerting for persistent/repeated
   degraded runs. Current `OnFailure` handling only writes a local syslog entry
   when systemd sees a failed unit. It has no notification transport or
   persistent-degradation threshold; degraded ETL outcomes are persisted/logged
   but are not necessarily systemd failures. An operator monitoring/alert
   policy is still needed.
2. Phase 6 calls for periodic disposable restore/rebuild verification. Current
   systemd units only check Restic integrity and temporary latest-snapshot
   restoration; no automated fresh Fuseki rebuild drill is scheduled.
3. Phase 6's publication-safety contract says a failed build must not leave
   Fuseki partially updated. `projection rebuild` targets an empty dataset but
   PUTs and verifies graphs sequentially; interruption can leave that new
   dataset partially populated, and no atomic whole-dataset activation exists.
   The procedure above makes that limitation explicit rather than claiming an
   atomic cutover.
