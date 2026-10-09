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

ensure_fuseki() {
  compose up -d --wait fuseki
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
  ensure_fuseki
  for endpoint in "${endpoints[@]}"; do
    if [[ "$endpoint" == "debates" ]]; then
      echo "Debates production ingestion is out of scope for Tranche B" >&2
      exit 2
    fi
    compose run --rm --no-deps etl run "$endpoint"
  done
}

run_reconciliation() {
  local endpoint
  local endpoints=("$@")
  if ((${#endpoints[@]} == 0)); then
    read -r -a endpoints <<< "${OIR_RECONCILIATION_ENDPOINTS:?set OIR_RECONCILIATION_ENDPOINTS in $runtime_env}"
  fi
  ensure_fuseki
  for endpoint in "${endpoints[@]}"; do
    compose run --rm --no-deps etl reconcile "$endpoint" --publish
  done
}

command="${1:-help}"
shift || true
case "$command" in
  build)
    git_commit="$(git -C "$project_dir" rev-parse HEAD)"
    OIR_GIT_COMMIT="$git_commit" compose build --pull etl ops
    ;;
  up-fuseki)
    compose up -d --wait fuseki
    ;;
  stop-fuseki)
    compose stop fuseki
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
    ensure_fuseki
    compose run --rm --no-deps etl "$@"
    ;;
  ops)
    compose run --rm --no-deps ops "$@"
    ;;
  help)
    echo "usage: production-compose.sh {build|up-fuseki|stop-fuseki|run-etl [ENDPOINT ...]|run-reconciliation [ENDPOINT ...]|etl ARGS...|ops ARGS...}"
    ;;
  *)
    echo "unknown production Compose operation: $command" >&2
    exit 2
    ;;
esac
