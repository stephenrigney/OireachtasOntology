#!/usr/bin/env bash
# Explicit Phase 6 production release gate. All Compose resources are uniquely
# named and live beneath a fresh /tmp work directory; no ordinary project,
# mutable developer database, external authority, or production credential is
# selected.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: scripts/production-release-gate.sh [EVIDENCE.json]

Run the complete Phase 6 release acceptance against disposable Fuseki 5.1.0,
including ontology/HermiT and mapping validation, the repository regression
suite, mandatory real-Fuseki acceptance (including Debates), and a real
Restic backup/independent restore/fresh projection rebuild. The optional
evidence path is written only after all mandatory groups pass. The default is
documentation/evidence/phase-6-tranche-c-release-gate.json.

Requires Docker Compose v2, mise with the repository-pinned Java, the project
.venv, curl, and restic. Ports 3030 and 13035 must be free. No live external
authority is contacted. A unique Compose project and all temporary volumes are
removed on exit, including failures.
EOF
  exit 0
fi

EVIDENCE="${1:-documentation/evidence/phase-6-tranche-c-release-gate.json}"
mkdir -p "$(dirname "$EVIDENCE")" /tmp/oireachtasontology
WORK="$(mktemp -d /tmp/oireachtasontology/phase6-release-gate.XXXXXX)"
PROJECT="oir-phase6-gate-$(date +%s)-$$"
PASSWORD="gate-$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
RESTIC_PASSWORD="$WORK/restic-password"
printf '%s\n' "restic-$PASSWORD" > "$RESTIC_PASSWORD"
chmod 0600 "$RESTIC_PASSWORD"
DRILL_RESTIC_PASSWORD="$WORK/drill-restic-password"
cp -- "$RESTIC_PASSWORD" "$DRILL_RESTIC_PASSWORD"
chmod 0600 "$DRILL_RESTIC_PASSWORD"
RUNTIME_ENV="$WORK/runtime.env"
FUSEKI_DIR="$WORK/fuseki-data"
DRILL_DIR="$WORK/drill-fuseki-data"
mkdir -p "$FUSEKI_DIR" "$DRILL_DIR"
COMPOSE_FILE="$WORK/debates-compose.yml"
GROUP_LOG="$WORK/groups.tsv"
touch "$GROUP_LOG"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REVISION="$(git rev-parse HEAD)"
CONFIG_HASH=""
RESULT=BLOCKED
CLEANUP_ERROR=0

cleanup() {
  local original_status=$?
  set +e
  docker compose --project-name "$PROJECT" --file "$ROOT/compose.production.yml" \
    --env-file "$RUNTIME_ENV" down --volumes --remove-orphans \
    >"$WORK/cleanup.log" 2>&1
  local compose_status=$?
  docker compose --project-name "${PROJECT}-debates" --file "$COMPOSE_FILE" \
    --env-file "$WORK/gate.env" down --volumes --remove-orphans >>"$WORK/cleanup.log" 2>&1
  local debates_status=$?
  if [[ -d "$FUSEKI_DIR" ]]; then
    # The production Fuseki image owns files beneath its host bind mount. Use
    # that already-pulled disposable image as root to empty only the exact
    # gate-created data directory after its service has stopped.
    if [[ "$FUSEKI_DIR" != "$WORK/fuseki-data" || -L "$FUSEKI_DIR" ]]; then
      echo "refusing unsafe Fuseki cleanup path: $FUSEKI_DIR" >>"$WORK/cleanup.log"
      CLEANUP_ERROR=1
    else
      docker run --rm --network none --user 0:0 --entrypoint /bin/sh \
        --volume "$FUSEKI_DIR:/release-gate-cleanup" stain/jena-fuseki:5.1.0 \
        -c 'rm -rf /release-gate-cleanup/* /release-gate-cleanup/.[!.]* /release-gate-cleanup/..?*' \
        >>"$WORK/cleanup.log" 2>&1 || CLEANUP_ERROR=1
    fi
  fi
  if [[ $compose_status -ne 0 || $debates_status -ne 0 ]]; then
    CLEANUP_ERROR=1
    echo "BLOCKED: failed to remove disposable Compose resources; inspect $WORK/cleanup.log" >&2
  fi
  if [[ "$RESULT" == PASS && $CLEANUP_ERROR -eq 0 ]]; then
    .venv/bin/python - "$EVIDENCE" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
report = json.loads(path.read_text())
report["disposable_cleanup"] = "PASS; both Compose projects and disposable storage removed"
path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
    rm -rf -- "$WORK" || {
      CLEANUP_ERROR=1
      echo "BLOCKED: could not remove disposable work directory $WORK" >&2
    }
  else
    echo "Disposable diagnostics retained at $WORK" >&2
  fi
  if [[ $CLEANUP_ERROR -ne 0 && -f "$EVIDENCE" ]]; then
    .venv/bin/python - "$EVIDENCE" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
report = json.loads(path.read_text())
report["result"] = "BLOCKED"
report["disposable_cleanup"] = "FAILED; inspect retained cleanup diagnostics"
path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
  fi
  if [[ $original_status -ne 0 ]]; then
    exit "$original_status"
  fi
  if [[ $CLEANUP_ERROR -ne 0 ]]; then
    exit 1
  fi
}
trap cleanup EXIT

blocked() { echo "BLOCKED: $*" >&2; exit 1; }
for command in docker mise curl restic; do command -v "$command" >/dev/null || blocked "missing required command: $command"; done
[[ -x .venv/bin/python ]] || blocked "missing .venv; install the project test extra first"
docker compose version >/dev/null || blocked "Docker Compose v2 is required"
for port in 3030 13035; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    blocked "loopback port $port is already in use; gate refuses to touch an existing service"
  fi
done

cat > "$RUNTIME_ENV" <<EOF
OIR_PROJECT_DIR=$ROOT
OIR_DURABLE_PARENT=$WORK/durable
OIR_BACKUP_DIR=$WORK/backups
OIR_RESTIC_PASSWORD_SOURCE=$RESTIC_PASSWORD
OIR_FUSEKI_DATA_DIR=$FUSEKI_DIR
OIR_DRILL_ROOT=$WORK/drills
OIR_DRILL_COMPOSE_PROJECT=${PROJECT}-recovery
OIR_DRILL_FUSEKI_BIND_PORT=13036
OIR_DRILL_RESTIC_PASSWORD_SOURCE=$DRILL_RESTIC_PASSWORD
OIR_DRILL_FUSEKI_ADMIN_PASSWORD=$PASSWORD-drill
OIR_CONTAINER_UID=$(id -u)
OIR_CONTAINER_GID=$(id -g)
OIR_ETL_IMAGE_TAG=phase6-gate
OIR_COMPOSE_PROJECT=$PROJECT
OIR_DAILY_ENDPOINTS=houses
OIR_RECONCILIATION_ENDPOINTS=members
OIR_ALERT_HOOK=/bin/true
FUSEKI_ADMIN_PASSWORD=$PASSWORD
FUSEKI_BIND_PORT=3030
EOF
chmod 0600 "$RUNTIME_ENV"
mkdir -p "$WORK/durable" "$WORK/backups" "$WORK/drills"

cat > "$COMPOSE_FILE" <<'EOF'
services:
  debates-fuseki:
    image: stain/jena-fuseki:5.1.0
    environment:
      FUSEKI_DATASET_1: debates_t4
      ADMIN_PASSWORD: ${FUSEKI_ADMIN_PASSWORD:?required}
    ports:
      - "127.0.0.1:13035:3030"
    healthcheck:
      test: ["CMD-SHELL", "curl --fail --silent --user \"admin:$${ADMIN_PASSWORD}\" http://127.0.0.1:3030/$$/ping >/dev/null"]
      interval: 2s
      timeout: 3s
      retries: 30
      start_period: 10s
EOF

cat > "$WORK/gate.env" <<EOF
FUSEKI_ADMIN_PASSWORD=$PASSWORD
EOF
chmod 0600 "$WORK/gate.env"

run_group() {
  local name="$1"; shift
  local before after elapsed status
  before="$(date +%s)"
  echo "==> $name"
  if "$@" >"$WORK/$name.log" 2>&1; then status=PASS; else status=FAIL; fi
  after="$(date +%s)"; elapsed=$((after-before))
  printf '%s\t%s\t%s\n' "$name" "$status" "$elapsed" >> "$GROUP_LOG"
  cat "$WORK/$name.log"
  [[ "$status" == PASS ]] || blocked "$name failed; full output: $WORK/$name.log"
  echo "PASS: $name (${elapsed}s)"
}

echo "Phase 6 release gate revision: $REVISION"
echo "Disposable Compose project: $PROJECT"
echo "Evidence destination: $EVIDENCE"

# Explicit production Compose configuration validation plus actual startup of
# its loopback Fuseki service on disposable bind-mounted TDB2 storage.
run_group compose-production-config docker compose --project-name "$PROJECT" \
  --file "$ROOT/compose.production.yml" --env-file "$RUNTIME_ENV" config --quiet
run_group compose-production-startup docker compose --project-name "$PROJECT" \
  --file "$ROOT/compose.production.yml" --env-file "$RUNTIME_ENV" up -d --wait fuseki
run_group debates-compose-startup docker compose --project-name "${PROJECT}-debates" \
  --file "$COMPOSE_FILE" --env-file "$WORK/gate.env" up -d --wait

# The complete routine suite retains its ordinary fast/optional semantics. Do
# not let opt-in tests infer a local Fuseki target for this regression group.
unset OIR_TEST_FUSEKI_GSP_URL OIR_TEST_FUSEKI_SPARQL_URL OIR_TEST_FUSEKI_USER OIR_TEST_FUSEKI_PASSWORD
unset OIR_FUSEKI_GSP_URL OIR_FUSEKI_SPARQL_URL OIR_FUSEKI_USER OIR_FUSEKI_PASSWORD
unset OIR_RELEASE_GATE_GSP_URL OIR_RELEASE_GATE_SPARQL_URL
unset OIR_RELEASE_GATE_DEBATES_GSP_URL OIR_RELEASE_GATE_DEBATES_SPARQL_URL
unset OIR_RELEASE_GATE_FUSEKI_USER OIR_RELEASE_GATE_FUSEKI_PASSWORD OIR_RELEASE_GATE_EVIDENCE
run_group ontology-hermit-mapping mise exec -- .venv/bin/python tests/validate.py
run_group mapping-integrity mise exec -- .venv/bin/python -m tools.validation
run_group repository-regression mise exec -- .venv/bin/python -m pytest -q tests

# Mandatory real-service groups run after both disposable Fuseki instances are
# healthy. Inject credentials into the ordinary CLI configuration as well.
export OIR_TEST_FUSEKI_GSP_URL='http://127.0.0.1:3030/houses/data'
export OIR_TEST_FUSEKI_SPARQL_URL='http://127.0.0.1:3030/houses/query'
export OIR_TEST_FUSEKI_USER=admin OIR_TEST_FUSEKI_PASSWORD="$PASSWORD"
export OIR_FUSEKI_GSP_URL="$OIR_TEST_FUSEKI_GSP_URL"
export OIR_FUSEKI_SPARQL_URL="$OIR_TEST_FUSEKI_SPARQL_URL"
export OIR_FUSEKI_USER=admin OIR_FUSEKI_PASSWORD="$PASSWORD"
export OIR_RELEASE_GATE_GSP_URL="$OIR_TEST_FUSEKI_GSP_URL"
export OIR_RELEASE_GATE_SPARQL_URL="$OIR_TEST_FUSEKI_SPARQL_URL"
export OIR_RELEASE_GATE_DEBATES_GSP_URL='http://127.0.0.1:13035/debates_t4/data'
export OIR_RELEASE_GATE_DEBATES_SPARQL_URL='http://127.0.0.1:13035/debates_t4/query'
export OIR_RELEASE_GATE_FUSEKI_USER=admin OIR_RELEASE_GATE_FUSEKI_PASSWORD="$PASSWORD"
export OIR_RELEASE_GATE_EVIDENCE="$WORK/backup-recovery-evidence.json"

# These selected real-service groups are mandatory: JUnit is inspected below so
# a conditional skip cannot be reported as a release-gate pass.
FOCUSED_JUNIT="$WORK/focused-junit.xml"
run_group full-stack-acceptance mise exec -- .venv/bin/python -m pytest -q \
  tests/test_fuseki_integration.py \
  tests/test_bill_local_fuseki.py tests/test_office_external_reconciliation.py \
  tests/test_production_release_acceptance.py \
  --junitxml "$FOCUSED_JUNIT"
run_group mandatory-skip-check .venv/bin/python - "$FOCUSED_JUNIT" <<'PY'
import sys
import xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in root.iter("testsuite"))
tests = sum(int(suite.attrib.get("tests", "0")) for suite in root.iter("testsuite"))
failures = sum(int(suite.attrib.get("failures", "0")) for suite in root.iter("testsuite"))
errors = sum(int(suite.attrib.get("errors", "0")) for suite in root.iter("testsuite"))
print({"mandatory_tests": tests, "skipped": skipped, "failures": failures, "errors": errors})
if not tests or skipped or failures or errors:
    raise SystemExit("mandatory production acceptance was skipped or failed")
PY

DEBATES_JUNIT="$WORK/debates-junit.xml"
export OIR_TEST_FUSEKI_GSP_URL='http://127.0.0.1:13035/debates_t4/data'
export OIR_TEST_FUSEKI_SPARQL_URL='http://127.0.0.1:13035/debates_t4/query'
run_group debates-real-fuseki-acceptance mise exec -- .venv/bin/python -m pytest -q \
  tests/test_debates_etl.py::test_disposable_fuseki_first_replay_changed_stale_skip_and_owner_isolation \
  --junitxml "$DEBATES_JUNIT"
run_group debates-mandatory-skip-check .venv/bin/python - "$DEBATES_JUNIT" <<'PY'
import sys
import xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in root.iter("testsuite"))
tests = sum(int(suite.attrib.get("tests", "0")) for suite in root.iter("testsuite"))
if tests != 1 or skipped:
    raise SystemExit(f"mandatory Debates acceptance skipped/failed: tests={tests}, skipped={skipped}")
print({"mandatory_debates_tests": tests, "skipped": skipped})
PY

CONFIG_HASH="$(sha256sum compose.production.yml | cut -d' ' -f1)"
FINISHED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$(dirname "$EVIDENCE")"
.venv/bin/python - "$EVIDENCE" "$GROUP_LOG" "$WORK/backup-recovery-evidence.json" \
  "$REVISION" "$CONFIG_HASH" "$STARTED" "$FINISHED" "$PROJECT" <<'PY'
import json, pathlib, sys
destination, groups_path, backup_path, revision, config_hash, started, finished, project = sys.argv[1:]
groups = []
for line in pathlib.Path(groups_path).read_text().splitlines():
    name, outcome, seconds = line.split("\t")
    groups.append({"group": name, "outcome": outcome, "duration_seconds": int(seconds)})
backup = json.loads(pathlib.Path(backup_path).read_text())
report = {
    "gate": "Phase 6 Tranche C production acceptance",
    "result": "PASS",
    "revision": revision,
    "compose_production_sha256": config_hash,
    "started_utc": started,
    "finished_utc": finished,
    "infrastructure": {
        "compose_project": project,
        "fuseki_image": "stain/jena-fuseki:5.1.0",
        "datasets": ["houses", "debates_t4"],
        "external_authorities_contacted": False,
        "production_credentials_or_services_used": False,
        "disposable_compose_cleanup_required": True,
    },
    "groups": groups,
    "backup_recovery": backup,
    "mandatory_skips": 0,
    "failure_injection": backup["failure_injection"],
}
pathlib.Path(destination).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps({"result": "PASS", "evidence": destination,
                  "groups": len(groups), "revision": revision}, sort_keys=True))
PY
RESULT=PASS
echo "PASS: Phase 6 Tranche C release gate; evidence: $EVIDENCE"
