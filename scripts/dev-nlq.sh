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
#   - optionally loads reference/Member data through the existing ETL;
#   - execs the FastAPI application under Uvicorn.
#
# Only this launcher reads `.env.local`. The Python application loads `.env`
# with `override=False`, so the values exported here always win over `.env`.
#
# Usage:
#   scripts/dev-nlq.sh [--no-reload] [--load-data]
#
#   --no-reload   Start Uvicorn without its autoreload watcher.
#   --load-data   Explicitly publish Houses, Parties, Constituencies and
#                 Members to the local Fuseki dataset through the existing ETL
#                 before starting the POC. Ordinary startup never loads or
#                 republishes data.
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
  --load-data   Explicitly publish Houses, Parties, Constituencies and Members
                to the local Fuseki dataset through the existing ETL before
                starting the POC. Ordinary startup never loads or republishes.
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

export NLQ_LLM_BASE_URL NLQ_LLM_MODEL NLQ_FUSEKI_QUERY_URL
export OIR_FUSEKI_GSP_URL OIR_FUSEKI_SPARQL_URL OIR_FUSEKI_USER OIR_FUSEKI_PASSWORD FUSEKI_ADMIN_PASSWORD

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
  echo "ERROR: Fuseki did not become ready at '$ping_url' after $FUSEKI_READY_ATTEMPTS attempts." >&2
  return 1
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
  wait_for_fuseki
}

echo "Starting local Fuseki (docker compose up -d fuseki)..."
docker compose up -d fuseki
wait_for_fuseki
ensure_fuseki_admin_password

# --- Optional explicit ETL load --------------------------------------------
load_endpoint() {
  local endpoint="$1"
  echo "Loading '$endpoint' into $OIR_FUSEKI_GSP_URL ..."
  if ! "$UV" run --locked oir-etl run "$endpoint"; then
    echo "ERROR: ETL load of '$endpoint' failed; the POC was not started." >&2
    exit 1
  fi
}

if [[ "$LOAD_DATA" -eq 1 ]]; then
  load_endpoint houses
  load_endpoint parties
  load_endpoint constituencies
  load_endpoint members
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
