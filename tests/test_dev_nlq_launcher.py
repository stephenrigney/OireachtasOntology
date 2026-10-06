"""Focused tests for ``scripts/dev-nlq.sh`` (local NLQ POC launcher).

The launcher is client-side developer convenience only. These tests exercise
configuration precedence, argument handling, the explicit ETL load path, and
the bounded Fuseki startup/reuse behaviour using stub ``uv``, ``docker`` and
``curl`` executables. No real dependency sync, container or web server starts.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "dev-nlq.sh"

DEFAULT_BASE_URL = "https://opencode.ai/inference/openai/v1"
DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_QUERY_URL = "http://localhost:3030/houses/query"
DEFAULT_GSP_URL = "http://localhost:3030/houses/data"
DEFAULT_SPARQL_URL = "http://localhost:3030/houses/query"
DEFAULT_FUSEKI_PASSWORD = "oireachtas-dev"

UV_STUB = """\
#!/usr/bin/env bash
printf 'UV:%s\\n' "$*"
sub="${1:-}"
case "$sub" in
  sync) exit 0 ;;
  run)
    shift
    while [[ "${1:-}" == --* ]]; do shift; done
    command="${1:-}"; shift || true
    case "$command" in
      oir-etl|uvicorn|python) exec "$STUB_COMMANDS/$command" "$@" ;;
      *) echo "unexpected uv command: $command" >&2; exit 64 ;;
    esac ;;
  *) echo "unexpected uv invocation: $*" >&2; exit 64 ;;
esac
"""

DOCKER_STUB = """\
#!/usr/bin/env bash
printf 'DOCKER:%s\\n' "$*"
printf 'DOCKER_ENV_FUSEKI_ADMIN_PASSWORD:%s\\n' "${FUSEKI_ADMIN_PASSWORD:-}"
case "${1:-}" in
  compose)
    shift
    case "${1:-}" in
      version) exit 0 ;;
      up) exit 0 ;;
      restart) exit 0 ;;
      exec)
        payload="$(cat)"
        printf 'DOCKER_EXEC_PAYLOAD:%s\\n' "$payload"
        if [[ "$payload" == *"awk"* ]]; then
          exit "${STUB_DOCKER_REWRITE_EXIT:-0}"
        fi
        exit "${STUB_DOCKER_EXEC_EXIT:-0}" ;;
      *) exit 0 ;;
    esac ;;
  *) exit 0 ;;
esac
"""

CURL_STUB = """\
#!/usr/bin/env bash
count_file="${STUB_CURL_COUNT_FILE:-}"
if [[ -n "$count_file" ]]; then
  n="$(cat "$count_file" 2>/dev/null || echo 0)"
  n=$((n + 1))
  printf '%s' "$n" > "$count_file"
  if (( n <= ${STUB_CURL_FAILS:-0} )); then
    exit 1
  fi
fi
exit "${STUB_CURL_EXIT:-0}"
"""

OIR_ETL_STUB = """\
#!/usr/bin/env bash
printf 'ETL:%s\\n' "$*"
printf 'ETL_ENV_OIR_FUSEKI_GSP_URL:%s\\n' "${OIR_FUSEKI_GSP_URL:-}"
printf 'ETL_ENV_OIR_FUSEKI_SPARQL_URL:%s\\n' "${OIR_FUSEKI_SPARQL_URL:-}"
if [[ -n "${STUB_ETL_FAIL_ENDPOINT:-}" && "$*" == *"$STUB_ETL_FAIL_ENDPOINT"* ]]; then
  echo "simulated ETL failure for $STUB_ETL_FAIL_ENDPOINT" >&2
  exit 7
fi
exit 0
"""

UVICORN_STUB = """\
#!/usr/bin/env bash
printf 'UVICORN:%s\\n' "$*"
for name in NLQ_LLM_API_KEY NLQ_LLM_BASE_URL NLQ_LLM_MODEL NLQ_FUSEKI_QUERY_URL \
            OIR_FUSEKI_GSP_URL OIR_FUSEKI_SPARQL_URL OIR_FUSEKI_USER \
            OIR_FUSEKI_PASSWORD FUSEKI_ADMIN_PASSWORD PYTHONPATH; do
  printf 'ENV_%s:%s\\n' "$name" "${!name:-}"
done
exit "${STUB_UVICORN_EXIT_CODE:-0}"
"""


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _launcher_tree(tmp_path: Path, env_local: str | None = None) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    launcher = scripts / "dev-nlq.sh"
    shutil.copy2(LAUNCHER, launcher)
    launcher.chmod(launcher.stat().st_mode | stat.S_IEXEC)

    if env_local is not None:
        (tmp_path / ".env.local").write_text(env_local, encoding="utf-8")

    commands = tmp_path / "commands"
    commands.mkdir()
    _write_stub(commands / "oir-etl", OIR_ETL_STUB)
    _write_stub(commands / "uvicorn", UVICORN_STUB)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_stub(bin_dir / "uv", UV_STUB)
    _write_stub(bin_dir / "docker", DOCKER_STUB)
    _write_stub(bin_dir / "curl", CURL_STUB)
    return launcher


def _run_launcher(launcher: Path, *args, extra_env=None) -> subprocess.CompletedProcess:
    tmp_path = launcher.parents[1]
    env = os.environ.copy()
    for name in list(env):
        if name.startswith(("NLQ_", "OIR_", "FUSEKI_")) or name == "PYTHONPATH":
            env.pop(name)
    # `uv run` sets UV to its own executable, which would bypass the test stub.
    env.pop("UV", None)
    env["HOME"] = str(tmp_path / "home")
    env["PATH"] = f"{tmp_path / 'bin'}:{env['PATH']}"
    env["STUB_COMMANDS"] = str(tmp_path / "commands")
    env["FUSEKI_READY_INTERVAL"] = "0"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(launcher), *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )


def _uvicorn_env(stdout: str, name: str) -> str:
    prefix = f"ENV_{name}:"
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing {prefix} in launcher output:\n{stdout}")


def _etl_env_values(stdout: str, name: str) -> list[str]:
    prefix = f"ETL_ENV_{name}:"
    return [line[len(prefix):] for line in stdout.splitlines() if line.startswith(prefix)]


def test_launcher_defaults_and_starts_uvicorn_with_reload(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher)

    assert result.returncode == 0, result.stderr
    assert "UV:sync --locked --extra nlq" in result.stdout
    assert "DOCKER:compose up -d fuseki" in result.stdout
    assert "UVICORN:poc.nlq.app:app --reload --host 127.0.0.1 --port 8000" in result.stdout
    assert _uvicorn_env(result.stdout, "NLQ_LLM_BASE_URL") == DEFAULT_BASE_URL
    assert _uvicorn_env(result.stdout, "NLQ_LLM_MODEL") == DEFAULT_MODEL
    assert _uvicorn_env(result.stdout, "NLQ_FUSEKI_QUERY_URL") == DEFAULT_QUERY_URL
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_GSP_URL") == DEFAULT_GSP_URL
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_SPARQL_URL") == DEFAULT_SPARQL_URL
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_USER") == "admin"
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_PASSWORD") == DEFAULT_FUSEKI_PASSWORD
    assert _uvicorn_env(result.stdout, "FUSEKI_ADMIN_PASSWORD") == DEFAULT_FUSEKI_PASSWORD
    assert _uvicorn_env(result.stdout, "NLQ_LLM_API_KEY") == "file-key"
    # Packaging is installed, so the launcher must not inject PYTHONPATH.
    assert _uvicorn_env(result.stdout, "PYTHONPATH") == ""
    assert "down -v" not in result.stdout
    assert "down -v" not in result.stderr


def test_explicit_environment_overrides_env_local_and_defaults(tmp_path):
    launcher = _launcher_tree(
        tmp_path,
        "NLQ_LLM_API_KEY=file-key\n"
        "NLQ_LLM_BASE_URL=https://from-file/v1\n"
        "NLQ_LLM_MODEL=file-model\n"
        "OIR_FUSEKI_PASSWORD=from-file-password\n",
    )

    result = _run_launcher(
        launcher,
        extra_env={"NLQ_LLM_BASE_URL": "https://from-env/v1"},
    )

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "NLQ_LLM_BASE_URL") == "https://from-env/v1"
    assert _uvicorn_env(result.stdout, "NLQ_LLM_MODEL") == "file-model"
    # An existing local Fuseki password is reused as the local admin password so
    # a persistent volume keeps working.
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_PASSWORD") == "from-file-password"
    assert _uvicorn_env(result.stdout, "FUSEKI_ADMIN_PASSWORD") == "from-file-password"


def test_env_local_supports_export_prefix_and_quotes(tmp_path):
    launcher = _launcher_tree(
        tmp_path,
        "export NLQ_LLM_API_KEY='quoted key'\n"
        "# a comment\n"
        "\n"
        'NLQ_LLM_MODEL="quoted model"\n',
    )

    result = _run_launcher(launcher)

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "NLQ_LLM_API_KEY") == "quoted key"
    assert _uvicorn_env(result.stdout, "NLQ_LLM_MODEL") == "quoted model"


def test_api_key_can_come_from_the_process_environment(tmp_path):
    launcher = _launcher_tree(tmp_path)

    result = _run_launcher(launcher, extra_env={"NLQ_LLM_API_KEY": "env-key"})

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "NLQ_LLM_API_KEY") == "env-key"


def test_application_dotenv_cannot_override_launcher_selected_values(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")
    # The application loads the repository-root .env with override=False. The
    # launcher does not read .env at all, so its resolved values always win.
    (tmp_path / ".env").write_text(
        "NLQ_LLM_BASE_URL=https://from-dotenv/v1\nNLQ_LLM_MODEL=dotenv-model\n",
        encoding="utf-8",
    )

    result = _run_launcher(launcher)

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "NLQ_LLM_BASE_URL") == DEFAULT_BASE_URL
    assert _uvicorn_env(result.stdout, "NLQ_LLM_MODEL") == DEFAULT_MODEL


def test_missing_api_key_fails_early_without_starting_anything(tmp_path):
    launcher = _launcher_tree(tmp_path)

    result = _run_launcher(launcher)

    assert result.returncode == 1
    assert "NLQ_LLM_API_KEY is not set" in result.stderr
    assert ".env.local.example" in result.stderr
    assert "UV:" not in result.stdout
    assert "DOCKER:" not in result.stdout
    assert "UVICORN:" not in result.stdout


def test_no_reload_omits_the_uvicorn_reload_flag(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher, "--no-reload")

    assert result.returncode == 0, result.stderr
    assert (
        "UVICORN:poc.nlq.app:app --host 127.0.0.1 --port 8000" in result.stdout
    )
    assert "--reload" not in result.stdout


def test_ordinary_startup_does_not_load_data(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher)

    assert result.returncode == 0, result.stderr
    assert "ETL:" not in result.stdout


def test_load_data_invokes_explicit_non_authoritative_development_bootstrap(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher, "--load-data")

    assert result.returncode == 0, result.stderr
    assert "ETL:dev bootstrap" in result.stdout
    assert "ETL:run " not in result.stdout
    assert "--fuseki-gsp-url" in result.stdout
    assert "--fuseki-sparql-url" in result.stdout
    assert "UVICORN:poc.nlq.app:app" in result.stdout


def test_load_data_exports_both_etl_endpoints_to_every_subprocess(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher, "--load-data")

    assert result.returncode == 0, result.stderr
    # The development bootstrap receives the same local GSP and SPARQL target.
    assert _etl_env_values(result.stdout, "OIR_FUSEKI_GSP_URL") == [DEFAULT_GSP_URL]
    assert _etl_env_values(result.stdout, "OIR_FUSEKI_SPARQL_URL") == [DEFAULT_SPARQL_URL]


def test_etl_sparql_url_defaults_to_the_resolved_nlq_query_url(tmp_path):
    launcher = _launcher_tree(
        tmp_path,
        "NLQ_LLM_API_KEY=file-key\n"
        "NLQ_FUSEKI_QUERY_URL=http://custom.example:3030/houses/query\n",
    )

    result = _run_launcher(launcher, "--load-data")

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_SPARQL_URL") == "http://custom.example:3030/houses/query"
    assert _etl_env_values(result.stdout, "OIR_FUSEKI_SPARQL_URL") == [
        "http://custom.example:3030/houses/query"
    ]


def test_env_local_can_override_the_etl_sparql_url(tmp_path):
    launcher = _launcher_tree(
        tmp_path,
        "NLQ_LLM_API_KEY=file-key\n"
        "NLQ_FUSEKI_QUERY_URL=http://custom.example:3030/houses/query\n"
        "OIR_FUSEKI_SPARQL_URL=http://from-file:3030/houses/query\n",
    )

    result = _run_launcher(launcher, "--load-data")

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_SPARQL_URL") == "http://from-file:3030/houses/query"
    assert _etl_env_values(result.stdout, "OIR_FUSEKI_SPARQL_URL") == [
        "http://from-file:3030/houses/query"
    ]


def test_explicit_environment_overrides_env_local_etl_sparql_url(tmp_path):
    launcher = _launcher_tree(
        tmp_path,
        "NLQ_LLM_API_KEY=file-key\n"
        "OIR_FUSEKI_SPARQL_URL=http://from-file:3030/houses/query\n",
    )

    result = _run_launcher(
        launcher,
        "--load-data",
        extra_env={"OIR_FUSEKI_SPARQL_URL": "http://from-env:3030/houses/query"},
    )

    assert result.returncode == 0, result.stderr
    assert _uvicorn_env(result.stdout, "OIR_FUSEKI_SPARQL_URL") == "http://from-env:3030/houses/query"
    assert _etl_env_values(result.stdout, "OIR_FUSEKI_SPARQL_URL") == [
        "http://from-env:3030/houses/query"
    ]


def test_etl_failure_stops_before_starting_the_poc(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(
        launcher,
        "--load-data",
        extra_env={"STUB_ETL_FAIL_ENDPOINT": "bootstrap"},
    )

    assert result.returncode != 0
    assert "local development data bootstrap failed" in result.stderr
    assert "the POC was not started" in result.stderr
    assert "UVICORN:" not in result.stdout


def test_matching_fuseki_password_does_not_restart_the_service(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher)

    assert result.returncode == 0, result.stderr
    assert "DOCKER:compose restart fuseki" not in result.stdout


def test_existing_volume_password_is_reconciled_without_deleting_it(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(
        launcher,
        extra_env={
            "STUB_DOCKER_EXEC_EXIT": "1",
            "STUB_DOCKER_REWRITE_EXIT": "0",
        },
    )

    assert result.returncode == 0, result.stderr
    # The mismatch triggers an in-place admin-line rewrite and a restart.
    assert "DOCKER_EXEC_PAYLOAD:" in result.stdout
    assert "admin=" in result.stdout and "awk" in result.stdout
    assert "DOCKER:compose exec" in result.stdout
    assert "DOCKER:compose restart fuseki" in result.stdout
    assert "down -v" not in result.stdout


def test_fuseki_readiness_retries_before_starting_uvicorn(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")
    count_file = tmp_path / "curl-count"

    result = _run_launcher(
        launcher,
        extra_env={
            "STUB_CURL_COUNT_FILE": str(count_file),
            "STUB_CURL_FAILS": "2",
        },
    )

    assert result.returncode == 0, result.stderr
    assert count_file.read_text() == "3"
    assert "UVICORN:poc.nlq.app:app" in result.stdout


def test_readiness_timeout_aborts_before_starting_uvicorn(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(
        launcher,
        extra_env={
            "STUB_CURL_EXIT": "1",
            "FUSEKI_READY_ATTEMPTS": "2",
        },
    )

    assert result.returncode != 0
    assert "did not become ready" in result.stderr
    assert "UVICORN:" not in result.stdout


def test_unknown_argument_is_rejected(tmp_path):
    launcher = _launcher_tree(tmp_path, "NLQ_LLM_API_KEY=file-key\n")

    result = _run_launcher(launcher, "--reset")

    assert result.returncode == 2
    assert "unknown argument" in result.stderr
    assert "UVICORN:" not in result.stdout
