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
| `/var/lib/oireachtas-etl-root/alerts` | Degraded-run alert delivery state; deliberately outside `live/` so restore activation does not replace it. |
| `/var/lib/oireachtas-fuseki` | Example persistent Fuseki/TDB2 directory, separate from canonical state and backups. |
| `/var/backups/oireachtas-etl` | Host directory mounted by ops; the configured Restic repository is `restic/` below it. |
| Dedicated drill root | Isolated temporary recovery inputs and Compose data; must not overlap production state, backups, Fuseki, secrets, or the project checkout. |

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
   Manual host operators who are not root must belong to the dedicated group
   whose GID is `OIR_CONTAINER_GID`. Pre-create `alerts/` as a setgid,
   group-writable directory so the wrapper and ETL/ops container can queue,
   read and remove notifications without runtime `chown`. Do not share this
   group with untrusted accounts. For the default GID:

    ```sh
    sudo install -d -o root -g 10001 -m 2770 /var/lib/oireachtas-etl-root/alerts
    sudo usermod -aG 10001 OPERATOR_ACCOUNT
    ```

   Start a new login session after adding operators to the group. Alert event
   files are mode `0640` and contain notification metadata, not credentials. If
   shared permissions are unavailable, a manual ETL error retains its original
   exit status and the wrapper reports that its alert could not be queued.
   Ensure Fuseki's own container can write its host data directory; the Compose
   file does not set a host-side Fuseki UID. Create the `live/raw` directory
   before the first backup. Keep Fuseki's data directory separate and persistent.
   For the example paths and default ETL/ops identity, host setup can start with:

   ```sh
   sudo install -d -o 10001 -g 10001 -m 0750 \
     /var/lib/oireachtas-etl-root /var/lib/oireachtas-etl-root/live/raw \
     /var/backups/oireachtas-etl
   sudo install -d -o root -g 10001 -m 2770 \
     /var/lib/oireachtas-etl-root/alerts
   sudo install -d -o root -g root -m 0750 /var/lib/oireachtas-etl-drills
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
5. Create a high-entropy `FUSEKI_ADMIN_PASSWORD` and a different high-entropy
   `OIR_DRILL_FUSEKI_ADMIN_PASSWORD` in that file. The production credential is
   passed at runtime to production Fuseki and ETL/ops; the drill credential is
   used only inside the disposable drill Compose project, including its Fuseki
   services and client. Neither is built into the image. Docker administrators
   can inspect container configuration, so
   restrict host/Docker access as privileged access. Create the Restic
   password separately at `OIR_RESTIC_PASSWORD_SOURCE`. It is mounted read-only
   as `/run/secrets/restic-password`; make it readable by the configured
   container UID/GID (for example, root-owned with read permission only for the
   container's dedicated group; with defaults, `root:10001` and mode `0440`),
   and not readable by other host users. Preserve these secrets through an
   approved secret-management channel. Losing the Restic password makes
   encrypted backups unusable.
   Configure `OIR_ALERT_HOOK` to an absolute, executable, root-controlled
   dispatcher path. Configure `OIR_DRILL_ROOT` as a separate provisioned
   directory, `OIR_DRILL_COMPOSE_PROJECT` as a dedicated project prefix, and
   `OIR_DRILL_FUSEKI_BIND_PORT` as a free loopback port. Provide
   `OIR_DRILL_RESTIC_PASSWORD_SOURCE` as a separately controlled protected file
   containing the password needed to read a copied recovery repository. The
   drill does not copy the production password file. Keep both drill passwords,
   the drill root, and alert program outside ordinary backup inputs and
   production paths.
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
| `OIR_ALERT_HOOK` | Absolute path to an executable, root-controlled notification program. It receives one argument: a JSON event-file path, and must return zero only after successful dispatch. Configure and test it before enabling scheduled jobs. |
| `OIR_ALERT_RECONCILIATION_DEGRADED_THRESHOLD` | Consecutive degraded attempts per reconciliation entity before notification; default `2`. |
| `OIR_DRILL_ROOT` | Existing dedicated host directory for disposable recovery drills, disjoint from every production path. |
| `OIR_DRILL_COMPOSE_PROJECT` | Dedicated lowercase Compose project-name prefix; every drill adds a unique suffix. |
| `OIR_DRILL_FUSEKI_BIND_PORT` | Unused loopback port for the disposable Fuseki service, different from the production port. The private rebuild instance has no host-published port. |
| `OIR_DRILL_RESTIC_PASSWORD_SOURCE` | Separate protected file containing the recovery-repository password; it must not be the production password file or live under the drill root. |
| `OIR_DRILL_FUSEKI_ADMIN_PASSWORD` | High-entropy Fuseki password distinct from `FUSEKI_ADMIN_PASSWORD`, used only by disposable recovery-drill Fuseki services. Keep it in the protected runtime env file. |

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
| `OIR_ALERT_DEGRADED_RUN_THRESHOLD` | `2` consecutive degraded runs per endpoint |
| `OIR_ALERT_RECONCILIATION_DEGRADED_THRESHOLD` | `2` consecutive degraded attempts per reconciliation entity |

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
- `oir-alert-check.service` and `oir-alert-check.timer`
- `oir-recovery-drill.service` and `oir-recovery-drill.timer`
- `oireachtas-ops-failure@.service`

For example, install the supplied unit files with:

```sh
sudo install -m 0644 /opt/oireachtas-etl/deployment/systemd/*.service /etc/systemd/system/
sudo install -m 0644 /opt/oireachtas-etl/deployment/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Do not enable the timers until the initial durable stores and first backup have
been checked, the alert hook has been tested, and the separate drill root,
password, project prefix, and port have been provisioned. The one-shot
ETL/reconcile/backup services are started by their timers, not enabled directly.
The supplied local times are 02:00 ETL, 03:00 reconciliation, 04:00 backup,
05:00 backup check, and 06:00 degraded-run alert evaluation. A full disposable
restore/rebuild drill runs weekly on Sunday at approximately 06:00. Timers are
persistent across downtime; ETL/reconciliation have up to 15 minutes and
backup/check/alert evaluation up to 10 minutes randomized delay (with 1-minute
accuracy); the drill has up to 15 minutes. Schedules use the host's systemd
calendar/timezone. The code does not supply a site-specific endpoint list,
notification destination, or drill paths.

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
sudo /opt/oireachtas-etl/scripts/production-compose.sh alerts-check
sudo /opt/oireachtas-etl/scripts/production-compose.sh recovery-drill
sudo systemctl enable --now oir-etl.timer oir-reconcile.timer oir-backup.timer \
  oir-backup-check.timer oir-alert-check.timer oir-recovery-drill.timer
```

`state initialize` creates/migrates all four stores under the configured
durable root. It and all configured Restic commands use the shared operation lock. `backup
init` explicitly initializes the encrypted Restic repository; it is not
implicit. A successful `backup check` is required before relying on the first
recovery point. Fuseki is started separately by systemd; the ETL wrapper also
ensures Fuseki is healthy before a normal ETL/reconciliation invocation.

## Manual operations, updates, and locking

Examples (run as an account permitted to use the Docker daemon; the supplied
systemd units run the wrapper as root). Projection cutover and recovery-drill
commands also need host permission to stop/remove Fuseki containers, rename the
data directory, and match the Fuseki UID/GID; use the documented `sudo` path.

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh run-etl houses members bills
sudo /opt/oireachtas-etl/scripts/production-compose.sh run-reconciliation members parties
sudo /opt/oireachtas-etl/scripts/production-compose.sh etl state status
sudo /opt/oireachtas-etl/scripts/production-compose.sh ops backup status
sudo /opt/oireachtas-etl/scripts/production-compose.sh alerts-check
sudo /opt/oireachtas-etl/scripts/production-compose.sh recovery-drill
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
sudo systemctl stop oir-etl.timer oir-reconcile.timer oir-backup.timer \
  oir-backup-check.timer oir-alert-check.timer oir-recovery-drill.timer
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
  oir-backup-check.timer oir-alert-check.timer oir-recovery-drill.timer
```

The build uses `docker compose build --pull`
for `etl` and `ops`; Fuseki's configured image/version is separate. Preserve
the same Compose project name, durable directories, and secrets across a
routine update. Check unit/timer state before treating the update as operational.
No automatic image-update or rollback mechanism is supplied.

The ETL CLI acquires `OIR_OPERATION_LOCK_FILE` for state-mutating `run`,
`reconcile`, and quarantine-retry commands when configured. Production Compose
sets all clients to the same host-mounted lock. Every configured Restic command
uses that lock as well: backup creation holds it across SQLite snapshots, file
capture, snapshot and retention; checks, listing and staged restore also
serialize on the repository so a drill copy cannot race another configured
Restic process. State initialization and restore activation use it. The
`rebuild-projection` wrapper holds it from before Fuseki is stopped through
private reconstruction, verification, directory cutover and Fuseki health
recovery. It is an advisory POSIX lock on one host only.

In a recovery, stop ETL/reconciliation timers and wait for active jobs before
durable-state activation and projection reconstruction. The lock prevents
overlap with a running writer, but does not prevent a new scheduled job from
starting as soon as the command releases it.
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

1. Stop ETL, reconciliation, backup, backup-check, alert-check and recovery-drill
   timers. Let any active one-shot finish; do not kill an ETL job during
   publication. Keep timers stopped until restore and projection verification
   complete. Check
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
    `oir-fuseki.service` before activation and leave it stopped until the
    verified replacement has been cut over. This avoids serving the old
    projection as if it matched the restored canonical state.

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

Use the production wrapper only:

```sh
sudo /opt/oireachtas-etl/scripts/production-compose.sh rebuild-projection \
  --confirm-offline-cutover
```

The wrapper takes the shared operation lock, stops the loopback-published
Fuseki service and removes its stopped container (preserving its data volume),
creates a new TDB2 directory beside `OIR_FUSEKI_DATA_DIR`, and starts a private
Compose Fuseki instance with **no host-published port**. The
ops container can reach this temporary service only over the Compose network.
The wrapper reconstructs and validates the full graph inventory there, stops
the private instance, preserves the previous TDB2 directory under a unique
`.previous.*` name, then renames the verified directory into the configured
Fuseki path and force-recreates the serving container so its bind mount points
at the new directory. The filesystem rename is on the
same host filesystem; this is an offline fresh-only procedure with downtime,
not a live TDB transaction or zero-downtime service. Fuseki is not exposed with
the replacement until every graph and the final graph inventory have passed.

The CLI rebuild uses exact published payloads held in Core State and saved
reconciliation state. It requires the current supported Core State schema,
reconciliation SQLite file, versioned
`registries/ministerial-office-registry.json`, and valid GSP/query endpoints
and credentials. It first requires an empty dataset, validates payload hashes
and RDF before PUTs, then replaces and whole-graph verifies each named graph
and checks the final graph inventory. There are no API/Wikidata/DBpedia calls
during reconstruction.

An empty rebuild is accepted only when Core State is a freshly initialized,
integrity-checked current schema and all source, run, quarantine, catalog,
graph-version and migration-metadata tables are empty; the reconciliation
store and Fuseki target are still validated. This supports the documented
first-start drill before the first ETL publication. An empty payload list
accompanied by any Core State history is treated as missing/corrupt evidence
and fails closed.

For authoritative graphs it uses the clean published payload, or, for a dirty
publication, the exact hash-checked pending payload as the recovery boundary.
It includes the persisted provenance catalog when present. For external-link
graphs, clean published hashes are reconstructed from the append-only
reconciliation attempts and successful publication history; a later failed or
unresolved lookup does not erase an accepted graph. Dirty external publications
use their saved pending payload. Missing/corrupt hashes or insufficient
publication history fail closed rather than inventing assertions.

After durable restore or Fuseki loss, keep ETL/reconciliation schedules stopped
and wait for active jobs. For a durable-state restore, `oir-fuseki.service`
must already have been stopped before activation; keep it stopped until the
wrapper finishes. For Fuseki-only loss, stop the service before invoking the
wrapper. The wrapper also stops the Compose Fuseki container itself, so do not
manually replace or delete `OIR_FUSEKI_DATA_DIR`, and do not use
`docker compose down -v`. The directory must exist, be a non-symlink directory,
and be writable by the Fuseki image; staging is created beside it so cutover
renames stay on one filesystem.

On success the output reports verified graph/triple counts and the preserved
previous-data path. After stopping `oir-fuseki.service` for a restore or
Fuseki-only recovery, start it after the wrapper reports success. Do not resume
ETL/reconciliation timers until that service is healthy and Core State status
and the rebuild summary have been inspected. If private reconstruction fails,
the production service remains stopped and its container absent, the old
directory stays in place, and the partial staging directory is left unserved
for diagnosis. A durable `projection-rebuild-required` marker prevents later
ETL startup wrappers from bringing Fuseki online until a rebuild has completed
and passed post-cutover verification. If the verified directory cannot be activated, the wrapper
restores the prior directory but leaves Fuseki stopped; it does not serve a
potentially stale projection. Fix the cause and rebuild into another fresh
staging directory. Direct
`production-compose.sh ops projection rebuild` is blocked; it cannot safely
perform the offline stop/build/cutover protocol by itself.

## Recovery drill

The supplied `oir-backup-check.timer` verifies Restic repository/read-data
integrity and temporarily restores the latest snapshot for manifest/hash/SQLite
checks. In addition, `oir-recovery-drill.timer` runs a full disposable recovery
drill weekly. Configure `OIR_DRILL_ROOT`, `OIR_DRILL_COMPOSE_PROJECT`,
`OIR_DRILL_FUSEKI_BIND_PORT`, and a separately managed
`OIR_DRILL_RESTIC_PASSWORD_SOURCE` before enabling it.
That file must contain the credential for the copied repository, managed as a
separate protected copy; the drill never mounts or copies the production
password file.

Each run takes a unique Compose project and work directory, copies the encrypted
production Restic repository while holding the shared operation lock, and uses
only that copy and the separate drill password. It initializes disposable
stores/raw paths, runs a full backup check on the copy, stages the latest
snapshot, activates it into the disposable durable root, rebuilds the Fuseki
projection through the private unserved service, and performs a second backup
check. The drill never calls backup creation or retention and never starts or
connects to the production Fuseki service. On success it removes the disposable
Compose project and work directory; on failure it stops the project and retains
the work directory for diagnosis. The systemd journal records the command
outputs, including the verified projection graph summary. Do not enable the
drill timer until its separate paths/password have been tested with a manual
`recovery-drill` run.

## Monitoring, troubleshooting, and limitations

- Inspect scheduled execution with `systemctl list-timers 'oir-*'`,
  `systemctl status`, and `journalctl -u UNIT`. The supplied
  `oireachtas-ops-failure@.service` dispatches a `failed_unit` JSON event to
  `OIR_ALERT_HOOK` whenever a scheduled systemd unit fails. ETL/reconciliation
  failures from manual production-wrapper invocations are dispatched as
  `failed_run` events by the wrapper; scheduled jobs leave unit-level reporting
  to `OnFailure`. The hook is a
  deployment-provided executable (not a repository-selected vendor or
  destination); it must be absolute, root-controlled, and return success only
  after delivery. A local syslog message is retained if it is missing or fails.
- `oir-alert-check.timer` evaluates persisted Core State outcomes per endpoint.
  Once the configured number of consecutive degraded runs is reached, it sends
  one `degraded_run_streak` event for that episode. The JSON event file includes
  the threshold, endpoint, run IDs and event ID. It remains pending until the
  hook succeeds and the wrapper acknowledges delivery; a failed hook is retried
  later. Hook implementations should deduplicate by `event_id`; a crash after
  delivery but before file removal/acknowledgment can result in at-least-once
  dispatch for either event type.
- The same check reads existing reconciliation attempt history. Its separate
  configurable threshold counts consecutive `pending`/`ambiguous` outcomes or
  attempts with recorded errors for the same `(entity_kind, local_iri)`; a
  successful `accepted`/`rejected` attempt ends that entity's episode. No
  second reconciliation queue or run ledger is introduced. An isolated failed
  lookup does not cross the default threshold.
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
- Projection rebuild refusal: verify the private staging directory is new and
  writable, the matching Core State schema, reconciliation database and office
  registry exist, and all persisted publication hashes/history validate. The
  wrapper intentionally leaves Fuseki stopped and preserves any partial stage
  after failure. Never point the internal rebuild command at a serving dataset.
- Recovery drill failure: inspect the `oir-recovery-drill.service` journal and
  retained run directory under `OIR_DRILL_ROOT`. Confirm that its copied Restic
  repository is complete, its separate Restic password is readable by the
  configured container UID/GID, and the drill paths and credentials are
  disjoint from production.
- Backups are local-path Restic snapshots in this Compose deployment; no
  off-host copy, RTO, or automatic full recovery orchestration is configured.
  The backup checker is not a complete disaster-recovery proof. Production
  acceptance, disposable full-stack release testing, external/production
  testing, and Debates ingestion/readiness are not claimed by this guide.

## Tranche B implementation status and deployment prerequisites

The earlier Tranche B gaps are addressed in this checkout: configurable
failed-run/unit and repeated-degraded alert dispatch is wired through the
production wrapper and systemd; a
weekly disposable encrypted-backup restore/activation/rebuild drill is
provided; and projection recovery uses an offline, unserved staging dataset
before filesystem cutover. These are implementation paths, not evidence that
the site's alert destination is configured, that the timers have been enabled,
or that a production-host drill has passed. Configure and test the hook and
drill prerequisites before enabling their timers. Do not claim the complete
Phase 6 exit: Tranche C's disposable release gate and production/external
service acceptance remain separate, and this guide does not claim Debates
production ingestion/readiness.

### Independent review finding disposition

The corrective implementation closes the five findings recorded by the
independent Tranche B review:

1. Manual failed-run alerts no longer change directory ownership at runtime;
   supported non-root operators use a pre-provisioned setgid alert directory.
   Queue/delivery failures are reported while preserving the original ETL exit
   status.
2. A fresh initialized, integrity-checked Core State with no publication,
   source, run, quarantine, catalog, graph-version or migration history proves
   a legitimate empty inventory and can rebuild/verify an empty Fuseki dataset.
   Any such persisted history with an
   empty graph inventory fails closed. Rebuilding remains offline, fresh-only
   and isolated from clients.
3. The existing alert check evaluates repeated reconciliation-attempt
   degradation from `reconciliation.sqlite`, with a separately configurable
   threshold, episode suppression and reset after a successful resolved attempt.
   Core State ETL alerts remain unchanged.
4. Recovery drills require and use `OIR_DRILL_FUSEKI_ADMIN_PASSWORD`, which must
   differ from the production Fuseki password. The private rebuild service has
   no host-published port.
5. `deployment/production.env.example` now matches the durable parent used by
   clean-host provisioning and recovery commands.

These paths have focused regression coverage. A deployment must still complete
a successful manual recovery drill with its actual protected paths and secrets
before enabling the scheduled drill timer; this guide is not a production-host
acceptance result.
