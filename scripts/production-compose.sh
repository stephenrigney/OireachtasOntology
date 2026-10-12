#!/usr/bin/env bash
set -euo pipefail

runtime_env="${OIR_RUNTIME_ENV_FILE:-/etc/oireachtas-etl/production.env}"
if [[ ! -r "$runtime_env" ]]; then
  echo "production runtime environment is unreadable: $runtime_env" >&2
  exit 2
fi
# The file is a root-controlled shell-compatible environment file (mode 0600).
# It is trusted configuration, not content from a source/API response.
set -a
# shellcheck disable=SC1090
source "$runtime_env"
set +a

project_dir="${OIR_PROJECT_DIR:?set OIR_PROJECT_DIR in $runtime_env}"
compose_file="$project_dir/compose.production.yml"
project="${OIR_COMPOSE_PROJECT:-oirechtas-etl-production}"
if [[ ! -f "$compose_file" ]]; then
  echo "production Compose file is missing: $compose_file" >&2
  exit 2
fi

compose() {
  docker compose --project-name "$project" --project-directory "$project_dir" \
    --env-file "$runtime_env" -f "$compose_file" --profile production "$@"
}

json_escape() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  value=${value//$'\t'/\\t}
  printf '%s' "$value"
}

dispatch_alert_file() {
  local event_file="$1"
  if [[ -z "${OIR_ALERT_HOOK:-}" || "$OIR_ALERT_HOOK" != /* || ! -x "$OIR_ALERT_HOOK" ]]; then
    logger --priority user.err --tag oireachtas-ops \
      "OIR_ALERT_HOOK must name an executable absolute path; alert remains undelivered" \
      2>/dev/null || true
    echo "OIR_ALERT_HOOK must name an executable absolute path; alert remains undelivered" >&2
    return 1
  fi
  if ! "$OIR_ALERT_HOOK" "$event_file"; then
    logger --priority user.err --tag oireachtas-ops \
      "configured alert hook failed; alert remains undelivered" 2>/dev/null || true
    return 1
  fi
}

queue_failed_alert() {
  local event_id="${1:?alert event ID is required}"
  local payload="${2:?alert JSON payload is required}"
  local alert_dir event_file temporary
  alert_dir="$OIR_DURABLE_PARENT/alerts"
  if ! mkdir -p "$alert_dir"; then
    echo "could not create the shared operational alert directory: $alert_dir" >&2
    return 1
  fi
  if [[ ! -d "$alert_dir" || -L "$alert_dir" ]]; then
    echo "operational alert state path is not a regular directory" >&2
    return 1
  fi
  if [[ ! -w "$alert_dir" || ! -x "$alert_dir" ]]; then
    echo "operational alert directory must be writable by this operator and the ETL group: $alert_dir" >&2
    return 1
  fi
  event_file="$alert_dir/pending-$event_id.json"
  if ! temporary="$(mktemp "$alert_dir/.pending-failure.XXXXXX")"; then
    echo "could not create the pending failed-run alert file" >&2
    return 1
  fi
  if ! chmod 0640 "$temporary"; then
    rm -f -- "$temporary"
    echo "could not set shared alert-file permissions" >&2
    return 1
  fi
  if ! printf '%s\n' "$payload" >"$temporary"; then
    rm -f -- "$temporary"
    echo "could not write the pending failed-run alert" >&2
    return 1
  fi
  if ! mv -- "$temporary" "$event_file"; then
    rm -f -- "$temporary"
    echo "could not queue the pending failed-run alert" >&2
    return 1
  fi
  if dispatch_alert_file "$event_file"; then
    rm -f -- "$event_file"
  else
    echo "alert event retained for retry at $event_file" >&2
    return 1
  fi
}

failed_unit_alert() {
  local unit="${1:?systemd unit name is required}"
  local event_id created_at escaped_unit payload
  event_id="failed-unit-$(date -u +%Y%m%dT%H%M%S%N)-$$"
  created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  escaped_unit="$(json_escape "$unit")"
  payload="{\"format\":1,\"event_id\":\"$event_id\",\"event\":\"failed_unit\",\"created_at\":\"$created_at\",\"unit\":\"$escaped_unit\"}"
  queue_failed_alert "$event_id" "$payload"
}

failed_manual_run_alert() {
  local operation="${1:?failed operation description is required}"
  local event_id created_at escaped_operation payload
  event_id="failed-run-$(date -u +%Y%m%dT%H%M%S%N)-$$"
  created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  escaped_operation="$(json_escape "$operation")"
  payload="{\"format\":1,\"event_id\":\"$event_id\",\"event\":\"failed_run\",\"created_at\":\"$created_at\",\"operation\":\"$escaped_operation\"}"
  queue_failed_alert "$event_id" "$payload"
}

run_etl_command() {
  local operation="$*" status
  if compose run --rm --no-deps etl "$@"; then
    return 0
  else
    status=$?
  fi
  # systemd's OnFailure handler emits the richer unit-level event for a
  # scheduled invocation; manual production-wrapper failures notify here.
  if [[ "${OIR_SCHEDULED_ETL:-0}" != "1" ]]; then
    if ! failed_manual_run_alert "$operation"; then
      echo "ETL operation failed with status $status; failed-run alert could not be delivered or queued" >&2
      logger --priority user.err --tag oireachtas-ops \
        "failed-run alert could not be delivered or queued for: $operation" 2>/dev/null || true
    fi
  fi
  return "$status"
}

ensure_fuseki_for_etl() {
  local operation="${1:-ETL operation}" status
  if ensure_fuseki; then
    return 0
  else
    status=$?
  fi
  if [[ "${OIR_SCHEDULED_ETL:-0}" != "1" ]]; then
    if ! failed_manual_run_alert "$operation (Fuseki startup)"; then
      echo "Fuseki startup failed with status $status; failed-run alert could not be delivered or queued" >&2
      logger --priority user.err --tag oireachtas-ops \
        "failed-run alert could not be delivered or queued for: $operation (Fuseki startup)" 2>/dev/null || true
    fi
  fi
  return "$status"
}

alerts_check() {
  local host_pending failed_event alert_lock_fd alert_lock_path
  alert_lock_path="$OIR_DURABLE_PARENT/alerts-check.lock"
  exec {alert_lock_fd}>"$alert_lock_path"
  flock -x "$alert_lock_fd"
  compose run --rm --no-deps ops alerts check
  for failed_event in "$OIR_DURABLE_PARENT"/alerts/pending-failed-*.json; do
    [[ -e "$failed_event" ]] || continue
    if [[ ! -f "$failed_event" || -L "$failed_event" ]]; then
      echo "pending failed-unit alert path is not a regular file" >&2
      return 1
    fi
    dispatch_alert_file "$failed_event"
    rm -f -- "$failed_event"
  done
  host_pending="$OIR_DURABLE_PARENT/alerts/pending.json"
  if [[ -e "$host_pending" || -L "$host_pending" ]]; then
    if [[ ! -f "$host_pending" || -L "$host_pending" ]]; then
      echo "pending alert path is not a regular file" >&2
      return 1
    fi
    dispatch_alert_file "$host_pending"
    compose run --rm --no-deps ops alerts delivered
  fi
  flock -u "$alert_lock_fd"
  exec {alert_lock_fd}>&-
}

ensure_fuseki() {
  with_shared_operation_lock ensure_fuseki_unlocked
}

ensure_fuseki_unlocked() {
  local rebuild_required="$OIR_DURABLE_PARENT/projection-rebuild-required"
  if [[ -e "$rebuild_required" || -L "$rebuild_required" ]]; then
    echo "Fuseki startup is blocked by an incomplete projection rebuild; inspect state and run rebuild-projection" >&2
    return 1
  fi
  compose up -d --wait fuseki
}

with_shared_operation_lock() {
  local lock_path="${OIR_DURABLE_PARENT:?set OIR_DURABLE_PARENT}/operations.lock"
  local lock_fd status
  if [[ ! -d "$OIR_DURABLE_PARENT" ]]; then
    echo "OIR_DURABLE_PARENT must exist before starting Fuseki" >&2
    return 2
  fi
  exec {lock_fd}>"$lock_path"
  if ! flock -x "$lock_fd"; then
    echo "could not acquire the shared ETL operation lock" >&2
    return 1
  fi
  if "$@"; then status=0; else status=$?; fi
  flock -u "$lock_fd"
  exec {lock_fd}>&-
  return "$status"
}

run_endpoints() {
  local endpoint
  local endpoints=("$@")
  if ((${#endpoints[@]} == 0)); then
    read -r -a endpoints <<< "${OIR_DAILY_ENDPOINTS:?set OIR_DAILY_ENDPOINTS in $runtime_env}"
  fi
  if ((${#endpoints[@]} == 0)); then
    echo "OIR_DAILY_ENDPOINTS must not be empty" >&2
    exit 2
  fi
  ensure_fuseki_for_etl "run ${endpoints[*]}"
  for endpoint in "${endpoints[@]}"; do
    if [[ "$endpoint" == "debates" ]]; then
      echo "Debates production ingestion is out of scope for Tranche B" >&2
      exit 2
    fi
    run_etl_command run "$endpoint"
  done
}

run_reconciliation() {
  local endpoint
  local endpoints=("$@")
  if ((${#endpoints[@]} == 0)); then
    read -r -a endpoints <<< "${OIR_RECONCILIATION_ENDPOINTS:?set OIR_RECONCILIATION_ENDPOINTS in $runtime_env}"
  fi
  ensure_fuseki_for_etl "reconcile ${endpoints[*]}"
  for endpoint in "${endpoints[@]}"; do
    run_etl_command reconcile "$endpoint" --publish
  done
}

REBUILD_STAGE_DIR=""
REBUILD_SERVICE_STARTED=0
REBUILD_LIVE_DIR=""
REBUILD_PREVIOUS_DIR=""
REBUILD_FAILED_DIR=""
REBUILD_PROMOTED=0

rebuild_projection() {
  local live parent base stage previous failed lock_file lock_fd timestamp
  if [[ "$#" -ne 1 || "${1:-}" != "--confirm-offline-cutover" ]]; then
    echo "projection recovery requires --confirm-offline-cutover" >&2
    echo "the Fuseki service will be stopped while a private fresh dataset is rebuilt and verified" >&2
    return 2
  fi
  [[ -n "${OIR_DURABLE_PARENT:-}" && -d "$OIR_DURABLE_PARENT" ]] || {
    echo "OIR_DURABLE_PARENT must be an existing host directory" >&2; return 2;
  }
  [[ -n "${OIR_FUSEKI_DATA_DIR:-}" && "$OIR_FUSEKI_DATA_DIR" == /* ]] || {
    echo "OIR_FUSEKI_DATA_DIR must be an absolute host directory" >&2; return 2;
  }
  live="$(realpath -m -- "$OIR_FUSEKI_DATA_DIR")"
  [[ -d "$live" && ! -L "$live" ]] || {
    echo "configured Fuseki data path must be an existing non-symlink directory" >&2; return 2;
  }
  parent="$(dirname -- "$live")"
  base="$(basename -- "$live")"
  stage="$(mktemp -d "$parent/.${base}.rebuild.XXXXXX")"
  REBUILD_STAGE_DIR="$stage"
  REBUILD_LIVE_DIR="$live"
  REBUILD_PREVIOUS_DIR=""
  REBUILD_FAILED_DIR=""
  REBUILD_PROMOTED=0
  REBUILD_SERVICE_STARTED=0
  if ! chmod --reference="$live" "$stage"; then
    echo "could not copy the Fuseki data-directory permissions to the private stage" >&2
    return 1
  fi
  if [[ "$(stat -c '%u:%g' "$stage")" != "$(stat -c '%u:%g' "$live")" ]]; then
    if ! chown --reference="$live" "$stage"; then
      echo "cannot match the Fuseki data-directory owner; run this operation with the required host privileges" >&2
      return 1
    fi
  fi
  lock_file="$OIR_DURABLE_PARENT/operations.lock"
  exec {lock_fd}>"$lock_file"
  if ! flock -x "$lock_fd"; then
    echo "could not acquire the shared ETL operation lock" >&2
    return 1
  fi

  # Take the serving endpoint offline before reconstruction. The replacement
  # Fuseki instance has no host-published port and is reachable only by the
  # private Compose network.
  : >"$OIR_DURABLE_PARENT/projection-rebuild-required"
  chmod 0600 "$OIR_DURABLE_PARENT/projection-rebuild-required"
  if ! compose stop fuseki; then
    echo "could not stop the serving Fuseki service; no projection was rebuilt" >&2
    return 1
  fi
  if ! compose rm -f fuseki; then
    echo "could not remove the stopped serving container; no projection was rebuilt" >&2
    return 1
  fi
  export OIR_FUSEKI_REBUILD_DATA_DIR="$stage"
  REBUILD_SERVICE_STARTED=1
  if ! compose up -d --wait fuseki-rebuild; then
    echo "private Fuseki rebuild instance did not become healthy; serving Fuseki remains stopped" >&2
    return 1
  fi
  export OIR_OPERATION_LOCK_HELD=1
  if ! compose run --rm --no-deps \
      -e OIR_FUSEKI_GSP_URL=http://fuseki-rebuild:3030/houses/data \
      -e OIR_FUSEKI_SPARQL_URL=http://fuseki-rebuild:3030/houses/query \
      -e OIR_OPERATION_LOCK_HELD=1 \
      ops projection rebuild --confirm-empty-target --operation-lock-held; then
    echo "private projection rebuild failed; serving Fuseki remains stopped and the partial staging path is unserved: $stage" >&2
    return 1
  fi
  if ! compose stop fuseki-rebuild || ! compose rm -f fuseki-rebuild; then
    echo "could not stop the private rebuild instance; serving Fuseki remains stopped" >&2
    return 1
  fi
  REBUILD_SERVICE_STARTED=0

  timestamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
  previous="$live.previous.$timestamp"
  failed="$live.failed.$timestamp"
  [[ ! -e "$previous" && ! -e "$failed" ]] || {
    echo "projection cutover preservation path already exists" >&2; return 1;
  }
  if ! mv -- "$live" "$previous"; then
    echo "could not preserve the previous Fuseki directory; serving Fuseki remains stopped" >&2
    return 1
  fi
  REBUILD_PREVIOUS_DIR="$previous"
  if ! mv -- "$stage" "$live"; then
    mv -- "$previous" "$live" || true
    REBUILD_PREVIOUS_DIR=""
    echo "could not install the verified projection; previous Fuseki directory was restored" >&2
    return 1
  fi
  REBUILD_STAGE_DIR=""
  REBUILD_FAILED_DIR="$failed"
  REBUILD_PROMOTED=1
  if ! compose up -d --wait --force-recreate fuseki; then
    echo "verified projection could not be activated; restoring the previous Fuseki directory" >&2
    return 1
  fi
  if ! compose run --rm --no-deps -e OIR_OPERATION_LOCK_HELD=1 \
      ops projection verify --operation-lock-held; then
    echo "post-cutover whole-dataset verification failed; restoring the previous directory and leaving Fuseki stopped" >&2
    return 1
  fi
  rm -f -- "$OIR_DURABLE_PARENT/projection-rebuild-required"
  REBUILD_PROMOTED=0
  echo "projection_cutover_complete post_cutover_verified=true previous_data_preserved_at=$previous"
  flock -u "$lock_fd"
  exec {lock_fd}>&-
}

path_overlaps() {
  local first="${1%/}" second="${2%/}"
  [[ "$first" == "$second" ]] && return 0
  case "$first/" in "$second/"*) return 0 ;; esac
  case "$second/" in "$first/"*) return 0 ;; esac
  return 1
}

DRILL_RUN_DIR=""
DRILL_PROJECT_ACTIVE=0

remove_disposable_run_dir() {
  local run_dir="${1:?disposable run directory is required}"
  local image="oireachtas-etl:${OIR_ETL_IMAGE_TAG:-phase6}"
  if rm -rf -- "$run_dir" 2>/dev/null; then
    return 0
  fi
  # Fuseki/TDB files are owned by the image's UID. Docker operators who run
  # the wrapper without host root can still clean only this freshly-created
  # disposable directory through the already-used ETL image.
  if ! docker run --rm --network none --user 0:0 --entrypoint python \
      -v "$run_dir:/drill:rw" "$image" -c \
      'import pathlib, shutil; root=pathlib.Path("/drill"); [shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink() for p in root.iterdir()]'; then
    return 1
  fi
  rmdir -- "$run_dir"
}

recovery_drill() {
  local drill_root prod_repository drill_project drill_port drill_pw
  local run_dir drill_durable drill_backup drill_fuseki drill_repository
  local host_lock drill_lock_fd operation_lock_fd stamp project_base path prod_password
  local container_uid container_gid drill_fuseki_password
  [[ -n "${OIR_DRILL_ROOT:-}" && "$OIR_DRILL_ROOT" == /* \
     && -d "$OIR_DRILL_ROOT" && ! -L "$OIR_DRILL_ROOT" ]] || {
    echo "OIR_DRILL_ROOT must be a provisioned, non-symlink directory" >&2; return 2;
  }
  [[ -n "${OIR_DRILL_COMPOSE_PROJECT:-}" ]] || {
    echo "OIR_DRILL_COMPOSE_PROJECT must name the isolated drill project" >&2; return 2;
  }
  [[ -n "${OIR_DRILL_RESTIC_PASSWORD_SOURCE:-}" \
      && -f "$OIR_DRILL_RESTIC_PASSWORD_SOURCE" \
      && ! -L "$OIR_DRILL_RESTIC_PASSWORD_SOURCE" ]] || {
    echo "OIR_DRILL_RESTIC_PASSWORD_SOURCE must be a separate protected password file" >&2; return 2;
  }
  [[ -n "${OIR_DRILL_FUSEKI_ADMIN_PASSWORD:-}" \
      && "$OIR_DRILL_FUSEKI_ADMIN_PASSWORD" != "${FUSEKI_ADMIN_PASSWORD:-}" ]] || {
    echo "OIR_DRILL_FUSEKI_ADMIN_PASSWORD must be set and differ from the production Fuseki password" >&2; return 2;
  }
  [[ -n "${OIR_DRILL_FUSEKI_BIND_PORT:-}" \
     && "$OIR_DRILL_FUSEKI_BIND_PORT" =~ ^[0-9]{1,5}$ \
     && "$OIR_DRILL_FUSEKI_BIND_PORT" -ge 1024 \
     && "$OIR_DRILL_FUSEKI_BIND_PORT" -le 65535 \
     && "$OIR_DRILL_FUSEKI_BIND_PORT" != "${FUSEKI_BIND_PORT:-3030}" ]] || {
    echo "OIR_DRILL_FUSEKI_BIND_PORT must be an unused non-production port from 1024 to 65535" >&2; return 2;
  }
  [[ -d "$OIR_BACKUP_DIR/restic" && ! -L "$OIR_BACKUP_DIR/restic" ]] || {
    echo "production Restic repository is unavailable for read-only cloning" >&2; return 2;
  }
  [[ -d "$OIR_DURABLE_PARENT" && -d "$OIR_FUSEKI_DATA_DIR" ]] || {
    echo "production durable and Fuseki directories must exist" >&2; return 2;
  }
  drill_root="$(realpath -m -- "$OIR_DRILL_ROOT")"
  prod_repository="$(realpath -m -- "$OIR_BACKUP_DIR/restic")"
  drill_pw="$(realpath -m -- "$OIR_DRILL_RESTIC_PASSWORD_SOURCE")"
  prod_password="$(realpath -m -- "$OIR_RESTIC_PASSWORD_SOURCE")"
  if [[ "$drill_root" != /* || "$drill_pw" == "$prod_password" \
        || "$OIR_DRILL_RESTIC_PASSWORD_SOURCE" -ef "$OIR_RESTIC_PASSWORD_SOURCE" ]]; then
    echo "drill paths must be absolute and use a separately controlled password file" >&2
    return 2
  fi
  for path in "$OIR_DURABLE_PARENT" "$OIR_BACKUP_DIR" "$OIR_FUSEKI_DATA_DIR" \
              "$project_dir" "$runtime_env" "$OIR_RESTIC_PASSWORD_SOURCE"; do
    if path_overlaps "$drill_root" "$(realpath -m -- "$path")"; then
      echo "OIR_DRILL_ROOT must not overlap production state, backup, Fuseki, secrets, or project paths" >&2
      return 2
    fi
    if path_overlaps "$drill_pw" "$(realpath -m -- "$path")"; then
      echo "the drill Restic password must not overlap production state, backup, Fuseki, secrets, or project paths" >&2
      return 2
    fi
  done
  if path_overlaps "$drill_root" "$drill_pw"; then
    echo "the drill Restic password must be stored outside OIR_DRILL_ROOT" >&2
    return 2
  fi
  project_base="$OIR_DRILL_COMPOSE_PROJECT"
  [[ "$project_base" =~ ^[a-z0-9][a-z0-9_-]{0,39}$ && "$project_base" != "$project" ]] || {
    echo "OIR_DRILL_COMPOSE_PROJECT must be a distinct lowercase Compose project prefix" >&2; return 2;
  }
  stamp="$(date -u +%Y%m%d%H%M%S)"
  drill_project="${project_base}-${stamp}-$$"
  [[ ${#drill_project} -le 63 ]] || {
    echo "drill Compose project name is too long" >&2; return 2;
  }
  exec {drill_lock_fd}>"$drill_root/recovery-drill.lock"
  if ! flock -n -x "$drill_lock_fd"; then
    echo "another disposable recovery drill is already running" >&2
    return 1
  fi
  run_dir="$(mktemp -d "$drill_root/run.XXXXXX")"
  DRILL_RUN_DIR="$run_dir"
  container_uid="${OIR_CONTAINER_UID:-10001}"
  container_gid="${OIR_CONTAINER_GID:-10001}"
  chown "$container_uid:$container_gid" "$run_dir"
  chmod 0750 "$run_dir"

  drill_durable="$run_dir/durable"
  drill_backup="$run_dir/backups"
  drill_fuseki="$run_dir/fuseki"
  drill_repository="$drill_backup/restic"
  mkdir -p "$drill_durable/live/raw" "$drill_fuseki" "$drill_backup"
  chown "$container_uid:$container_gid" "$drill_durable" "$drill_durable/live" \
    "$drill_durable/live/raw" "$drill_backup"
  chmod 0750 "$drill_durable" "$drill_durable/live" "$drill_durable/live/raw" "$drill_backup"
  chmod --reference="$OIR_FUSEKI_DATA_DIR" "$drill_fuseki"
  chown --reference="$OIR_FUSEKI_DATA_DIR" "$drill_fuseki"
  mkdir "$drill_repository"

  # Snapshot the encrypted repository while every configured backup/restore
  # operation is excluded by the same host-local writer lock.
  host_lock="$OIR_DURABLE_PARENT/operations.lock"
  exec {operation_lock_fd}>"$host_lock"
  flock -x "$operation_lock_fd"
  cp -a -- "$prod_repository/." "$drill_repository/"
  chown -R "$container_uid:$container_gid" "$drill_repository"
  flock -u "$operation_lock_fd"
  exec {operation_lock_fd}>&-

  project="$drill_project"
  drill_fuseki_password="$OIR_DRILL_FUSEKI_ADMIN_PASSWORD"
  FUSEKI_ADMIN_PASSWORD="$drill_fuseki_password"
  OIR_DURABLE_PARENT="$drill_durable"
  OIR_BACKUP_DIR="$drill_backup"
  OIR_FUSEKI_DATA_DIR="$drill_fuseki"
  OIR_RESTIC_PASSWORD_SOURCE="$drill_pw"
  FUSEKI_BIND_PORT="$OIR_DRILL_FUSEKI_BIND_PORT"
  export OIR_DURABLE_PARENT OIR_BACKUP_DIR OIR_FUSEKI_DATA_DIR
  export OIR_RESTIC_PASSWORD_SOURCE FUSEKI_BIND_PORT FUSEKI_ADMIN_PASSWORD
  DRILL_PROJECT_ACTIVE=1

  echo "recovery_drill_started project=$drill_project snapshot_source=isolated_encrypted_repository_copy"
  compose run --rm --no-deps ops state initialize
  compose run --rm --no-deps ops backup check
  compose run --rm --no-deps ops backup restore-latest \
    --destination /var/lib/oireachtas-etl-root/restore-staged
  compose run --rm --no-deps ops state activate-restore \
    --staged-root /var/lib/oireachtas-etl-root/restore-staged \
    --target-root /var/lib/oireachtas-etl-root/live \
    --confirm-replace-existing
  rebuild_projection --confirm-offline-cutover
  compose run --rm --no-deps ops backup check
}

finish_on_exit() {
  local status=$?
  trap - EXIT
  if (( REBUILD_SERVICE_STARTED )); then
    compose stop fuseki-rebuild >/dev/null 2>&1 || true
    compose rm -f fuseki-rebuild >/dev/null 2>&1 || true
  fi
  if (( status != 0 && REBUILD_PROMOTED )); then
    compose stop fuseki >/dev/null 2>&1 || true
    compose rm -f fuseki >/dev/null 2>&1 || true
    if [[ -d "$REBUILD_LIVE_DIR" && -n "$REBUILD_FAILED_DIR" \
          && ! -e "$REBUILD_FAILED_DIR" ]]; then
      mv -- "$REBUILD_LIVE_DIR" "$REBUILD_FAILED_DIR" || true
    fi
    if [[ -n "$REBUILD_PREVIOUS_DIR" && -d "$REBUILD_PREVIOUS_DIR" \
          && ! -e "$REBUILD_LIVE_DIR" ]]; then
      mv -- "$REBUILD_PREVIOUS_DIR" "$REBUILD_LIVE_DIR" || true
    fi
  fi
  if (( status != 0 )) && [[ -n "$REBUILD_STAGE_DIR" && -d "$REBUILD_STAGE_DIR" ]]; then
    echo "unserved projection staging path retained at $REBUILD_STAGE_DIR" >&2
  fi
  if (( DRILL_PROJECT_ACTIVE )); then
    if ! compose down --volumes --remove-orphans; then
      echo "could not fully stop disposable recovery-drill Compose project" >&2
      status=1
    fi
  fi
  if (( status == 0 )) && [[ -n "$DRILL_RUN_DIR" ]]; then
    if remove_disposable_run_dir "$DRILL_RUN_DIR"; then
      echo "recovery_drill_completed disposable_run_removed=true"
    else
      echo "recovery drill passed but disposable run cleanup needs host privileges: $DRILL_RUN_DIR" >&2
      status=1
    fi
  elif [[ -n "$DRILL_RUN_DIR" ]]; then
    echo "recovery_drill_failed disposable_data_preserved_at=$DRILL_RUN_DIR" >&2
  fi
  exit "$status"
}
trap finish_on_exit EXIT

command="${1:-help}"
shift || true
case "$command" in
  build)
    git_commit="$(git -C "$project_dir" rev-parse HEAD)"
    OIR_GIT_COMMIT="$git_commit" compose build --pull etl ops
    ;;
  up-fuseki)
    ensure_fuseki
    ;;
  stop-fuseki)
    with_shared_operation_lock compose stop fuseki
    ;;
  alert)
    if [[ "${1:-}" != "failed-unit" || "$#" -ne 2 ]]; then
      echo "usage: production-compose.sh alert failed-unit SYSTEMD_UNIT" >&2
      exit 2
    fi
    failed_unit_alert "$2"
    ;;
  alerts-check)
    alerts_check
    ;;
  rebuild-projection)
    rebuild_projection "$@"
    ;;
  recovery-drill)
    if [[ "$#" -ne 0 ]]; then
      echo "usage: production-compose.sh recovery-drill" >&2
      exit 2
    fi
    recovery_drill
    ;;
  run-etl)
    run_endpoints "$@"
    ;;
  run-reconciliation)
    run_reconciliation "$@"
    ;;
  etl)
    if [[ "${1:-}" == "run" && "${2:-}" == "debates" ]]; then
      echo "Debates production ingestion is out of scope for Tranche B" >&2
      exit 2
    fi
    ensure_fuseki_for_etl "etl $*"
    run_etl_command "$@"
    ;;
  ops)
    if [[ "${1:-}" == "projection" && "${2:-}" == "rebuild" ]]; then
      echo "use rebuild-projection --confirm-offline-cutover; direct graph-by-graph rebuild is disabled" >&2
      exit 2
    fi
    if [[ "${1:-}" == "alerts" ]]; then
      echo "use alerts-check so pending notifications are dispatched and acknowledged" >&2
      exit 2
    fi
    compose run --rm --no-deps ops "$@"
    ;;
  help)
    echo "usage: production-compose.sh {build|up-fuseki|stop-fuseki|run-etl [ENDPOINT ...]|run-reconciliation [ENDPOINT ...]|alerts-check|rebuild-projection --confirm-offline-cutover|recovery-drill|alert failed-unit UNIT|etl ARGS...|ops ARGS...}"
    ;;
  *)
    echo "unknown production Compose operation: $command" >&2
    exit 2
    ;;
esac
