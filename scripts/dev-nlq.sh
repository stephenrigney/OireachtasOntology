#!/usr/bin/env bash
# Local development launcher for the natural-language query POC (poc/nlq).
#
# Normal use:
#     scripts/dev-nlq.sh
#
# The launcher:
#   - resolves local-development configuration with the precedence
#         explicit process environment
#             > .env.local
#             > launcher development defaults;
#   - installs the NLQ dependencies from the committed lockfile;
#   - starts (or reuses) the local Docker Compose Fuseki service and waits for
#     it to become reachable before starting the web application;
#   - configures the local Fuseki admin credentials predictably, without
#     deleting the persistent Fuseki volume or grepping container logs;
#   - optionally runs the explicitly non-authoritative local-data bootstrap;
#   - execs the FastAPI application under Uvicorn.
#
# Only this launcher reads `.env.local`. The Python application loads `.env`
# with `override=False`, so the values exported here always win over `.env`.
#
# Usage:
#   scripts/dev-nlq.sh [--no-reload] [--load-data]
#
#   --no-reload   Start Uvicorn without its autoreload watcher.
#   --load-data   Explicitly bootstrap the local Fuseki from preserved complete
#                 API captures with 'oir-etl dev bootstrap'. This is a
#                 non-authoritative development load. Ordinary startup never
#                 loads or republishes data.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEFAULT_NLQ_LLM_BASE_URL="https://opencode.ai/inference/openai/v1"
DEFAULT_NLQ_LLM_MODEL="gpt-6-luna"
DEFAULT_NLQ_FUSEKI_QUERY_URL="http://localhost:3030/houses/query"
DEFAULT_OIR_FUSEKI_GSP_URL="http://localhost:3030/houses/data"
DEFAULT_OIR_FUSEKI_USER="admin"
# Documented, non-production local-development fallback. Override through the
# process environment or .env.local; never treat it as a production credential.
DEFAULT_FUSEKI_ADMIN_PASSWORD="oireachtas-dev"
UVICORN_HOST="127.0.0.1"
UVICORN_PORT="8000"
FUSEKI_READY_ATTEMPTS="${FUSEKI_READY_ATTEMPTS:-60}"
FUSEKI_READY_INTERVAL="${FUSEKI_READY_INTERVAL:-1}"

usage() {
  cat <<'EOF'
Usage: scripts/dev-nlq.sh [--no-reload] [--load-data]

  --no-reload   Start Uvicorn without its autoreload watcher.
  --load-data   Explicitly run 'oir-etl dev bootstrap' against loopback Fuseki
                using preserved complete API captures. This local-development
                dataset is non-authoritative. Ordinary startup does not load.
EOF
}

NO_RELOAD=0
LOAD_DATA=0
for arg in "$@"; do
  case "$arg" in
    --no-reload) NO_RELOAD=1 ;;
    --load-data) LOAD_DATA=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown argument: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

# --- Local developer configuration -----------------------------------------
# Parse a simple KEY=VALUE file without sourcing or executing shell. Values
# already present in the process environment are left untouched so explicit
# exports win.
load_env_local() {
  local file="$1" line key value
  [[ -f "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"                              # tolerate CRLF
    line="${line#"${line%%[![:space:]]*}"}"            # ltrim
    line="${line%"${line##*[![:space:]]}"}"            # rtrim
    [[ -z "$line" ]] && continue
    [[ "$line" == \#* ]] && continue
    if [[ "$line" == export[[:space:]]* ]]; then
      line="${line#export}"
      line="${line#"${line%%[![:space:]]*}"}"          # ltrim after "export"
    fi
    [[ "$line" == *"="* ]] || continue
    key="${line%%=*}"
    value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"               # rtrim key
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    [[ -n "${!key+x}" ]] && continue                   # explicit env wins
    value="${value#"${value%%[![:space:]]*}"}"         # ltrim value
    value="${value%"${value##*[![:space:]]}"}"         # rtrim value
    if (( ${#value} >= 2 )); then
      case "$value" in
        \"*\") value="${value:1:${#value}-2}" ;;
        \'*\') value="${value:1:${#value}-2}" ;;
      esac
    fi
    printf -v "$key" '%s' "$value"
    export "$key"
  done < "$file"
}

load_env_local "$ROOT/.env.local"
: "${OIR_NLQ_SCRATCH_DIR:=$ROOT/var/nlq-scratch}"
export OIR_NLQ_SCRATCH_DIR

# --- Effective configuration: explicit env > .env.local > defaults ----------
: "${NLQ_LLM_BASE_URL:=$DEFAULT_NLQ_LLM_BASE_URL}"
: "${NLQ_LLM_MODEL:=$DEFAULT_NLQ_LLM_MODEL}"
: "${NLQ_FUSEKI_QUERY_URL:=$DEFAULT_NLQ_FUSEKI_QUERY_URL}"
: "${OIR_FUSEKI_GSP_URL:=$DEFAULT_OIR_FUSEKI_GSP_URL}"
# The ETL requires an explicit SPARQL endpoint for post-load whole-graph
# verification. It defaults to the resolved NLQ query URL so the ETL reads the
# same local Fuseki dataset the POC queries, while remaining overridable.
: "${OIR_FUSEKI_SPARQL_URL:=$NLQ_FUSEKI_QUERY_URL}"
: "${OIR_FUSEKI_USER:=$DEFAULT_OIR_FUSEKI_USER}"
# The local Compose Fuseki admin password. An OIR_FUSEKI_PASSWORD supplied by
# the environment or .env.local is reused as the local password so an existing
# Fuseki volume keeps working; otherwise the documented local default applies.
: "${FUSEKI_ADMIN_PASSWORD:=${OIR_FUSEKI_PASSWORD:-$DEFAULT_FUSEKI_ADMIN_PASSWORD}}"
: "${OIR_FUSEKI_PASSWORD:=$FUSEKI_ADMIN_PASSWORD}"
: "${OIR_NLQ_OFFICE_REVIEW_FILE:=$ROOT/reconciliation/office-decisions.json}"

export NLQ_LLM_BASE_URL NLQ_LLM_MODEL NLQ_FUSEKI_QUERY_URL
export OIR_FUSEKI_GSP_URL OIR_FUSEKI_SPARQL_URL OIR_FUSEKI_USER OIR_FUSEKI_PASSWORD FUSEKI_ADMIN_PASSWORD OIR_NLQ_OFFICE_REVIEW_FILE

# --- Required configuration -------------------------------------------------
if [[ -z "${NLQ_LLM_API_KEY:-}" ]]; then
  cat >&2 <<'EOF'
ERROR: NLQ_LLM_API_KEY is not set.

Set it in .env.local (copy .env.local.example first), or export it:

    export NLQ_LLM_API_KEY=...

The POC was not started.
EOF
  exit 1
fi

# --- Required tools ---------------------------------------------------------
UV="${UV:-uv}"
if ! command -v "$UV" >/dev/null 2>&1; then
  echo "ERROR: uv is required; install uv, then run 'uv sync --locked --extra nlq'." >&2
  exit 127
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is required to run the local Fuseki service." >&2
  exit 127
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: the Docker Compose plugin ('docker compose') is required." >&2
  exit 127
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required to wait for Fuseki readiness." >&2
  exit 127
fi

# --- Dependencies -----------------------------------------------------------
echo "Syncing NLQ dependencies (uv sync --locked --extra nlq)..."
"$UV" sync --locked --extra nlq

# --- Local Fuseki -----------------------------------------------------------
# Poll the anonymous status endpoint on the configured query origin. Fuseki's
# /$/ping is not authenticated, so this works before credentials are applied.
fuseki_origin() {
  local url="$1" rest
  rest="${url#*://}"
  printf '%s://%s' "${url%%://*}" "${rest%%/*}"
}

wait_for_fuseki() {
  local ping_url attempt
  ping_url="$(fuseki_origin "$NLQ_FUSEKI_QUERY_URL")/\$/ping"
  for ((attempt = 1; attempt <= FUSEKI_READY_ATTEMPTS; attempt++)); do
    if curl -fsS -o /dev/null "$ping_url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$FUSEKI_READY_INTERVAL"
  done
  return 1
}

report_fuseki_readiness_failure() {
  local health="unknown"
  if inspect_fuseki_container >/dev/null 2>&1; then
    health="$FUSEKI_HEALTH"
  fi
  if [[ "$health" == "unhealthy" ]]; then
    echo "ERROR: Docker reports that the Fuseki service is unhealthy." >&2
  else
    echo "ERROR: Fuseki did not become ready at '$(fuseki_origin "$NLQ_FUSEKI_QUERY_URL")/\$/ping' after $FUSEKI_READY_ATTEMPTS attempts (Docker health: $health)." >&2
  fi
  echo "Check 'docker compose ps fuseki' and 'docker compose logs --tail=100 fuseki'. The launcher did not stop or recreate the container." >&2
  return 1
}

# Ask Compose for the service's current container, then inspect its actual
# runtime state. In particular, the port check is against Docker's live port
# bindings rather than the Compose file: an old container can be missing the
# port publishing declared by the current configuration.
inspect_fuseki_container() {
  local container_id details
  local format='{{.State.Status}}|{{with index .State "Health"}}{{.Status}}{{else}}none{{end}}|{{range $binding := index .NetworkSettings.Ports "3030/tcp"}}{{$binding.HostIp}}:{{$binding.HostPort}} {{end}}'

  if ! container_id="$(docker compose ps -q fuseki)"; then
    echo "ERROR: Could not identify the Compose-managed Fuseki container. Check 'docker compose ps fuseki'." >&2
    return 1
  fi
  if [[ -z "$container_id" ]]; then
    echo "ERROR: Docker Compose started Fuseki but returned no container. Check 'docker compose ps fuseki'." >&2
    return 1
  fi
  if ! details="$(docker inspect --format "$format" "$container_id")"; then
    echo "ERROR: Could not inspect Fuseki container '$container_id'. Check Docker access and 'docker compose ps fuseki'." >&2
    return 1
  fi

  IFS='|' read -r FUSEKI_STATE FUSEKI_HEALTH FUSEKI_HOST_PORTS <<< "$details"
  FUSEKI_CONTAINER_ID="$container_id"
}

check_fuseki_container() {
  if ! inspect_fuseki_container; then
    return 1
  fi
  if [[ "$FUSEKI_STATE" != "running" ]]; then
    echo "ERROR: Fuseki container '$FUSEKI_CONTAINER_ID' is in Docker state '$FUSEKI_STATE', not running." >&2
    echo "Check 'docker compose ps fuseki' and 'docker compose logs --tail=100 fuseki'. The launcher did not stop or recreate the container." >&2
    return 1
  fi
  if [[ "$FUSEKI_HEALTH" == "unhealthy" ]]; then
    echo "ERROR: Docker reports that Fuseki container '$FUSEKI_CONTAINER_ID' is unhealthy." >&2
    echo "Check 'docker compose ps fuseki' and 'docker compose logs --tail=100 fuseki'. The launcher did not stop or recreate the container." >&2
    return 1
  fi
  if [[ -z "$FUSEKI_HOST_PORTS" ]]; then
    echo "ERROR: Fuseki container '$FUSEKI_CONTAINER_ID' does not publish its 3030/tcp port to the host." >&2
    echo "The Compose file declares 3030:3030, but this existing container has no live host-port binding. Check 'docker compose ps fuseki' and find any port owner with 'docker ps --filter publish=3030 --format \"table {{.ID}}\\t{{.Names}}\\t{{.Ports}}\"'." >&2
    echo "The launcher will not stop or recreate it. If no other service owns port 3030 and the 'fuseki-data' volume is correctly attached, recreate it deliberately with 'docker compose up -d --force-recreate fuseki' (never use 'down -v')." >&2
    return 1
  fi
  if [[ ! " $FUSEKI_HOST_PORTS " =~ :3030[[:space:]] ]]; then
    echo "ERROR: Fuseki container '$FUSEKI_CONTAINER_ID' publishes 3030/tcp as '$FUSEKI_HOST_PORTS', not the expected host port 3030." >&2
    echo "Check 'docker compose ps fuseki' and 'docker ps --format \"table {{.Names}}\\t{{.Ports}}\"'. The launcher will not stop or recreate the container." >&2
    return 1
  fi
  return 0
}

start_fuseki() {
  local output status lower_output
  # Compose up starts a stopped service or creates a missing one. --no-recreate
  # lets an existing container (and its named volume) be reused, while making
  # configuration drift an explicit diagnostic instead of an automatic reset.
  if output="$(docker compose up -d --no-recreate fuseki 2>&1)"; then
    [[ -z "$output" ]] || printf '%s\n' "$output"
    return 0
  else
    status=$?
  fi

  [[ -z "$output" ]] || printf '%s\n' "$output" >&2
  lower_output="${output,,}"
  if [[ "$lower_output" == *"port is already allocated"* || \
        "$lower_output" == *"address already in use"* || \
        "$lower_output" == *"failed to bind"* ]]; then
    echo "ERROR: Docker could not publish Fuseki on host port 3030; that port is already in use, likely by another Compose project." >&2
    echo "Find the owner with 'docker ps --filter publish=3030 --format \"table {{.ID}}\\t{{.Names}}\\t{{.Ports}}\"', then stop or reconfigure it yourself and rerun this launcher. No existing container was stopped or recreated." >&2
  else
    echo "ERROR: Docker Compose could not start Fuseki. Check 'docker compose ps fuseki' and 'docker compose logs --tail=100 fuseki'. No existing container was stopped or recreated." >&2
  fi
  return "$status"
}

# The image only applies ADMIN_PASSWORD to a fresh volume. Reuse of an existing
# volume therefore keeps whatever password it was first initialised with. Make
# the local admin password match the launcher configuration without deleting
# the volume: if it differs, rewrite the admin line and restart Fuseki.
fuseki_admin_password_matches() {
  docker compose exec -T -e "OIR_TARGET_PASSWORD=$FUSEKI_ADMIN_PASSWORD" \
    fuseki sh -s <<'CONTAINER'
current=$(sed -n 's/^admin=//p' /fuseki/shiro.ini | head -n1)
[ "$current" = "$OIR_TARGET_PASSWORD" ]
CONTAINER
}

set_fuseki_admin_password() {
  docker compose exec -T -e "OIR_TARGET_PASSWORD=$FUSEKI_ADMIN_PASSWORD" \
    fuseki sh -s <<'CONTAINER'
tmp=/fuseki/shiro.ini.tmp
awk -v pw="$OIR_TARGET_PASSWORD" '/^admin=/{print "admin=" pw; next} {print}' \
  /fuseki/shiro.ini > "$tmp" && mv "$tmp" /fuseki/shiro.ini
CONTAINER
}

ensure_fuseki_admin_password() {
  if fuseki_admin_password_matches >/dev/null 2>&1; then
    return 0
  fi
  echo "Applying the configured admin credential to the existing Fuseki volume..."
  set_fuseki_admin_password
  docker compose restart fuseki
  if ! wait_for_fuseki; then
    report_fuseki_readiness_failure
    return 1
  fi
  check_fuseki_container
}

echo "Starting or reusing local Fuseki (docker compose up -d --no-recreate fuseki)..."
start_fuseki
check_fuseki_container
if ! wait_for_fuseki; then
  report_fuseki_readiness_failure
  exit 1
fi
ensure_fuseki_admin_password

# --- Optional explicit local development bootstrap -------------------------
if [[ "$LOAD_DATA" -eq 1 ]]; then
  echo "Bootstrapping non-authoritative local PoC data from preserved API captures..."
  if ! "$UV" run --locked oir-etl dev bootstrap \
    --review-file "$OIR_NLQ_OFFICE_REVIEW_FILE" \
    --fuseki-gsp-url "$OIR_FUSEKI_GSP_URL" \
    --fuseki-sparql-url "$OIR_FUSEKI_SPARQL_URL"; then
    echo "ERROR: local development data bootstrap failed; the POC was not started." >&2
    exit 1
  fi
fi

# --- Start the POC ----------------------------------------------------------
echo "LLM endpoint:   $NLQ_LLM_BASE_URL (model: $NLQ_LLM_MODEL)"
echo "Fuseki query:   $NLQ_FUSEKI_QUERY_URL"
echo "Web interface:  http://${UVICORN_HOST}:${UVICORN_PORT}/"
[[ "$NO_RELOAD" -eq 0 ]] && echo "Auto-reload:    enabled (use --no-reload to disable)"

UVICORN_ARGS=(poc.nlq.app:app)
if [[ "$NO_RELOAD" -eq 0 ]]; then
  UVICORN_ARGS+=(--reload)
fi
UVICORN_ARGS+=(--host "$UVICORN_HOST" --port "$UVICORN_PORT")

exec "$UV" run --locked uvicorn "${UVICORN_ARGS[@]}"
