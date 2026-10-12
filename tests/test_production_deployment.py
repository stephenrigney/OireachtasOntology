from __future__ import annotations

import os
from pathlib import Path
import subprocess
import json
import pwd


ROOT = Path(__file__).resolve().parents[1]


def test_manual_and_scheduled_etl_use_the_same_production_compose_path(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker-arguments.log"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)

    runtime_env = tmp_path / "runtime.env"
    (tmp_path / "durable").mkdir()
    runtime_env.write_text(
        "\n".join((
            f"OIR_PROJECT_DIR={ROOT}",
            "OIR_COMPOSE_PROJECT=phase6-wrapper-test",
            "OIR_DAILY_ENDPOINTS=houses",
            "FUSEKI_ADMIN_PASSWORD=disposable-test-only",
            f"OIR_DURABLE_PARENT={tmp_path / 'durable'}",
            f"OIR_BACKUP_DIR={tmp_path / 'backups'}",
            f"OIR_RESTIC_PASSWORD_SOURCE={tmp_path / 'restic-password'}",
            f"OIR_FUSEKI_DATA_DIR={tmp_path / 'fuseki-data'}",
        )) + "\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o600)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "OIR_RUNTIME_ENV_FILE": str(runtime_env),
        "FAKE_DOCKER_LOG": str(docker_log),
    }
    launcher = ROOT / "scripts" / "production-compose.sh"

    subprocess.run([str(launcher), "run-etl", "houses"], env=env, check=True)
    subprocess.run([str(launcher), "etl", "run", "houses"], env=env, check=True)

    calls = docker_log.read_text(encoding="utf-8").splitlines()
    scheduled_calls = [line for line in calls if " run --rm --no-deps etl run houses" in line]
    assert len(scheduled_calls) == 2
    assert scheduled_calls[0] == scheduled_calls[1]

    service = (ROOT / "deployment/systemd/oir-etl.service").read_text(encoding="utf-8")
    assert "ExecStart=/opt/oireachtas-etl/scripts/production-compose.sh run-etl" in service


def test_runtime_example_matches_clean_host_durable_storage_provisioning():
    example = (ROOT / "deployment/production.env.example").read_text(encoding="utf-8")
    operations = (ROOT / "documentation/production-operations.md").read_text(
        encoding="utf-8")
    durable = next(line.split("=", 1)[1] for line in example.splitlines()
                   if line.startswith("OIR_DURABLE_PARENT="))
    assert durable == "/var/lib/oireachtas-etl-root"
    assert f"{durable} /var/lib/oireachtas-etl-root/live/raw" in operations
    assert f"--target-root {durable}/live" in operations


def _runtime_env(tmp_path: Path, *, extra: tuple[str, ...] = ()) -> Path:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    durable = tmp_path / "durable"
    durable.mkdir(exist_ok=True)
    backups = tmp_path / "backups"
    backups.mkdir(exist_ok=True)
    password = tmp_path / "restic-password"
    password.write_text("disposable-restic-password\n", encoding="utf-8")
    fuseki = tmp_path / "fuseki-data"
    fuseki.mkdir(exist_ok=True)
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "\n".join((
            f"OIR_PROJECT_DIR={ROOT}",
            "OIR_COMPOSE_PROJECT=phase6-wrapper-test",
            "OIR_DAILY_ENDPOINTS=houses",
            "OIR_RECONCILIATION_ENDPOINTS=members",
            "FUSEKI_ADMIN_PASSWORD=disposable-test-only",
            f"OIR_DURABLE_PARENT={durable}",
            f"OIR_BACKUP_DIR={backups}",
            f"OIR_RESTIC_PASSWORD_SOURCE={password}",
            f"OIR_FUSEKI_DATA_DIR={fuseki}",
            f"OIR_CONTAINER_UID={os.getuid()}",
            f"OIR_CONTAINER_GID={os.getgid()}",
            *extra,
        )) + "\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o600)
    return runtime_env


def _fake_docker(tmp_path: Path, *, script: str | None = None) -> tuple[Path, Path]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    log = tmp_path / "docker-arguments.log"
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(script or "#!/bin/bash\nprintf '%s\\n' \"$*\" >> \"$FAKE_DOCKER_LOG\"\n",
                           encoding="utf-8")
    fake_docker.chmod(0o755)
    return fake_bin, log


def _launcher_env(tmp_path: Path, runtime_env: Path, fake_bin: Path, log: Path,
                  **extra: str) -> dict[str, str]:
    return {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "OIR_RUNTIME_ENV_FILE": str(runtime_env),
        "FAKE_DOCKER_LOG": str(log),
        **extra,
    }


def _unprivileged_preexec():
    if os.geteuid() != 0:
        return None
    nobody = pwd.getpwnam("nobody")

    def drop_privileges():
        os.setgroups([])
        os.setgid(nobody.pw_gid)
        os.setuid(nobody.pw_uid)

    return drop_privileges


def test_alert_dispatcher_passes_failed_unit_as_json_file_to_configured_hook(tmp_path):
    hook_log = tmp_path / "hook.json"
    hook = tmp_path / "notify-hook"
    hook.write_text(
        "#!/bin/sh\ncat \"$1\" > \"$ALERT_CAPTURE\"\n", encoding="utf-8")
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path)
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                         ALERT_CAPTURE=str(hook_log))

    subprocess.run([str(ROOT / "scripts/production-compose.sh"), "alert",
                    "failed-unit", "oir-etl.service"], env=env, check=True)

    event = json.loads(hook_log.read_text(encoding="utf-8"))
    assert event["event"] == "failed_unit"
    assert event["unit"] == "oir-etl.service"
    assert event["event_id"].startswith("failed-unit-")
    assert not docker_log.exists()
    assert not list((tmp_path / "durable" / "alerts").glob("pending-failed-unit-*.json"))


def test_failed_alert_dispatch_is_retained_and_retried_by_alert_timer(tmp_path):
    hook_log = tmp_path / "hook.json"
    hook = tmp_path / "notify-hook"
    hook.write_text(
        "#!/bin/sh\ncat \"$1\" > \"$ALERT_CAPTURE\"\n"
        "if [ \"$FAIL_ALERT\" = 1 ]; then exit 1; fi\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path)
    launcher = str(ROOT / "scripts/production-compose.sh")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                        ALERT_CAPTURE=str(hook_log), FAIL_ALERT="1")

    failed = subprocess.run([launcher, "alert", "failed-unit", "oir-etl.service"],
                            env=env, capture_output=True, text=True)
    assert failed.returncode != 0
    pending = list((tmp_path / "durable" / "alerts").glob("pending-failed-unit-*.json"))
    assert len(pending) == 1

    env["FAIL_ALERT"] = "0"
    subprocess.run([launcher, "alerts-check"], env=env, check=True)
    assert json.loads(hook_log.read_text(encoding="utf-8"))["event"] == "failed_unit"
    assert not pending[0].exists()


def test_manual_failed_etl_run_is_alerted_without_masking_failure_status(tmp_path):
    hook_log = tmp_path / "hook.json"
    hook = tmp_path / "notify-hook"
    hook.write_text("#!/bin/sh\ncat \"$1\" > \"$ALERT_CAPTURE\"\n", encoding="utf-8")
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" run --rm --no-deps etl run houses"* ]]; then exit 23; fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                        ALERT_CAPTURE=str(hook_log))

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"),
                             "run-etl", "houses"], env=env,
                            capture_output=True, text=True)

    assert result.returncode == 23
    event = json.loads(hook_log.read_text(encoding="utf-8"))
    assert event["event"] == "failed_run"
    assert event["operation"] == "run houses"
    assert not list((tmp_path / "durable" / "alerts").glob("pending-failed-run-*.json"))


def test_nonroot_manual_operator_queues_and_delivers_failed_run_alert(tmp_path):
    hook_log = tmp_path / "hook.json"
    hook = tmp_path / "notify-hook"
    hook.write_text("#!/bin/sh\ncat \"$1\" > \"$ALERT_CAPTURE\"\n", encoding="utf-8")
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" run --rm --no-deps etl run houses"* ]]; then exit 43; fi
""")
    chown_called = tmp_path / "chown-called"
    (fake_bin / "chown").write_text(
        f"#!/bin/sh\nprintf called > '{chown_called}'\nexit 99\n", encoding="utf-8")
    (fake_bin / "chown").chmod(0o755)
    tmp_path.chmod(0o755)
    (tmp_path / "durable").chmod(0o777)
    runtime_env.chmod(0o644)
    hook_log.touch(mode=0o666)
    hook_log.chmod(0o666)
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                        ALERT_CAPTURE=str(hook_log))

    result = subprocess.run(
        [str(ROOT / "scripts/production-compose.sh"), "run-etl", "houses"],
        env=env, capture_output=True, text=True, preexec_fn=_unprivileged_preexec())

    assert result.returncode == 43
    event = json.loads(hook_log.read_text(encoding="utf-8"))
    assert event["event"] == "failed_run"
    assert not chown_called.exists()
    assert not list((tmp_path / "durable" / "alerts").glob("pending-failed-run-*.json"))


def test_failed_alert_queue_reports_error_and_preserves_etl_status(tmp_path):
    runtime_env = _runtime_env(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "durable" / "alerts").symlink_to(outside, target_is_directory=True)
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" run --rm --no-deps etl run houses"* ]]; then exit 47; fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"),
                             "run-etl", "houses"], env=env,
                            capture_output=True, text=True)

    assert result.returncode == 47
    assert "failed-run alert could not be delivered or queued" in result.stderr
    assert "operational alert state path" in result.stderr


def test_manual_failed_run_hook_failure_is_reported_and_preserves_etl_status(tmp_path):
    hook = tmp_path / "notify-hook"
    hook.write_text("#!/bin/sh\nexit 19\n", encoding="utf-8")
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" run --rm --no-deps etl run houses"* ]]; then exit 49; fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"),
                             "run-etl", "houses"], env=env,
                            capture_output=True, text=True)

    assert result.returncode == 49
    assert "failed-run alert could not be delivered or queued" in result.stderr
    queued = list((tmp_path / "durable" / "alerts").glob("pending-failed-run-*.json"))
    assert len(queued) == 1


def test_scheduled_failed_etl_leaves_alert_dispatch_to_systemd_onfailure(tmp_path):
    hook_log = tmp_path / "hook.json"
    hook = tmp_path / "notify-hook"
    hook.write_text("#!/bin/sh\ncat \"$1\" > \"$ALERT_CAPTURE\"\n", encoding="utf-8")
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" run --rm --no-deps etl run houses"* ]]; then exit 23; fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                        ALERT_CAPTURE=str(hook_log), OIR_SCHEDULED_ETL="1")

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"),
                             "run-etl", "houses"], env=env,
                            capture_output=True, text=True)

    assert result.returncode == 23
    assert not hook_log.exists()
    assert not list((tmp_path / "durable" / "alerts").glob("pending-failed-run-*.json"))


def test_alert_check_dispatches_pending_event_then_acknowledges_it(tmp_path):
    hook_log = tmp_path / "hook.json"
    hook = tmp_path / "notify-hook"
    hook.write_text(
        "#!/bin/sh\ncat \"$1\" > \"$ALERT_CAPTURE\"\n", encoding="utf-8")
    hook.chmod(0o755)
    runtime_env = _runtime_env(tmp_path, extra=(f"OIR_ALERT_HOOK={hook}",))
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" ops alerts check"* ]]; then
  mkdir -p "$OIR_DURABLE_PARENT/alerts"
  printf '%s\\n' '{"event":"degraded_run_streak","event_id":"e1"}' > \
    "$OIR_DURABLE_PARENT/alerts/pending.json"
fi
if [[ "$*" == *" ops alerts delivered"* ]]; then
  rm -f "$OIR_DURABLE_PARENT/alerts/pending.json"
fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                         ALERT_CAPTURE=str(hook_log))

    subprocess.run([str(ROOT / "scripts/production-compose.sh"), "alerts-check"],
                   env=env, check=True)

    assert json.loads(hook_log.read_text(encoding="utf-8"))["event_id"] == "e1"
    calls = docker_log.read_text(encoding="utf-8")
    assert " ops alerts check" in calls
    assert " ops alerts delivered" in calls


def test_private_projection_rebuild_is_verified_before_directory_cutover(tmp_path):
    runtime_env = _runtime_env(tmp_path)
    live = tmp_path / "fuseki-data"
    (live / "old-projection.marker").write_text("old", encoding="utf-8")
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" projection rebuild "* ]]; then
  [[ "$*" == *"http://fuseki-rebuild:3030/houses/data"* ]] || exit 31
  [[ "$*" == *"http://fuseki-rebuild:3030/houses/query"* ]] || exit 32
  printf verified > "$OIR_FUSEKI_REBUILD_DATA_DIR/verified.marker"
fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    subprocess.run([str(ROOT / "scripts/production-compose.sh"), "rebuild-projection",
                    "--confirm-offline-cutover"], env=env, check=True)

    assert (live / "verified.marker").read_text(encoding="utf-8") == "verified"
    assert not (live / "old-projection.marker").exists()
    assert not (tmp_path / "durable" / "projection-rebuild-required").exists()
    previous = list(tmp_path.glob("fuseki-data.previous.*"))
    assert len(previous) == 1
    assert (previous[0] / "old-projection.marker").exists()
    calls = docker_log.read_text(encoding="utf-8")
    assert any(line.endswith(" stop fuseki") for line in calls.splitlines())
    assert "stop fuseki-rebuild" in calls
    call_lines = calls.splitlines()
    rebuild_call = next(index for index, line in enumerate(call_lines)
                        if " projection rebuild " in line)
    serving_start = next(index for index, line in enumerate(call_lines)
                         if line.endswith(" up -d --wait --force-recreate fuseki"))
    assert rebuild_call < serving_start
    assert "projection rebuild --confirm-empty-target --operation-lock-held" in calls


def test_failed_projection_rebuild_preserves_live_directory_and_never_restarts_it(tmp_path):
    runtime_env = _runtime_env(tmp_path)
    live = tmp_path / "fuseki-data"
    (live / "old-projection.marker").write_text("old", encoding="utf-8")
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" projection rebuild "* ]]; then
  printf partial > "$OIR_FUSEKI_REBUILD_DATA_DIR/partial.marker"
  exit 42
fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"),
                             "rebuild-projection", "--confirm-offline-cutover"],
                            env=env, capture_output=True, text=True)

    assert result.returncode != 0
    assert (live / "old-projection.marker").exists()
    assert (tmp_path / "durable" / "projection-rebuild-required").is_file()
    assert not list(tmp_path.glob("fuseki-data.previous.*"))
    calls = docker_log.read_text(encoding="utf-8")
    assert any(line.endswith(" stop fuseki") for line in calls.splitlines())
    assert "up -d --wait --force-recreate fuseki\n" not in calls
    partial = list(tmp_path.glob(".fuseki-data.rebuild.*"))
    assert len(partial) == 1 and (partial[0] / "partial.marker").exists()


def test_failed_projection_service_start_rolls_back_to_previous_directory(tmp_path):
    runtime_env = _runtime_env(tmp_path)
    live = tmp_path / "fuseki-data"
    (live / "old-projection.marker").write_text("old", encoding="utf-8")
    fail_once = tmp_path / "fail-normal-fuseki-once"
    fail_once.touch()
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" projection rebuild "* ]]; then
  printf verified > "$OIR_FUSEKI_REBUILD_DATA_DIR/verified.marker"
fi
if [[ "$*" == *" up -d --wait --force-recreate fuseki"* && "$*" != *"fuseki-rebuild"* \
      && -f "$FAIL_ONCE_FILE" ]]; then
  rm -f "$FAIL_ONCE_FILE"
  exit 43
fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log,
                         FAIL_ONCE_FILE=str(fail_once))

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"),
                             "rebuild-projection", "--confirm-offline-cutover"],
                            env=env, capture_output=True, text=True)

    assert result.returncode != 0
    assert (live / "old-projection.marker").read_text(encoding="utf-8") == "old"
    assert not (live / "verified.marker").exists()
    assert (tmp_path / "durable" / "projection-rebuild-required").is_file()
    assert len(list(tmp_path.glob("fuseki-data.failed.*"))) == 1
    calls = docker_log.read_text(encoding="utf-8")
    serving_starts = [line for line in calls.splitlines()
                      if line.endswith(" up -d --wait --force-recreate fuseki")]
    assert len(serving_starts) == 1  # failed candidate is never replaced by the old service


def test_recovery_drill_uses_isolated_project_and_copied_repository(tmp_path):
    runtime_env = _runtime_env(tmp_path, extra=(
        f"OIR_DRILL_ROOT={tmp_path / 'drills'}",
        "OIR_DRILL_COMPOSE_PROJECT=phase6-recovery-drill",
        "OIR_DRILL_FUSEKI_BIND_PORT=13031",
        f"OIR_DRILL_RESTIC_PASSWORD_SOURCE={tmp_path / 'drill-restic-password'}",
        "OIR_DRILL_FUSEKI_ADMIN_PASSWORD=drill-only-password",
        "OIR_CONTAINER_UID=10001",
        "OIR_CONTAINER_GID=10001",
    ))
    (tmp_path / "drills").mkdir()
    (tmp_path / "drill-restic-password").write_text(
        "separately-managed-copy\n", encoding="utf-8")
    source_repo = tmp_path / "backups" / "restic"
    source_repo.mkdir()
    (source_repo / "config").write_text("encrypted-repository-marker", encoding="utf-8")
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" ops backup check"* ]]; then
  [[ -f "$OIR_BACKUP_DIR/restic/config" ]] || exit 44
fi
if [[ "$*" == *" projection rebuild "* ]]; then
  printf verified > "$OIR_FUSEKI_REBUILD_DATA_DIR/verified.marker"
fi
if [[ "$*" == *" up -d --wait fuseki-rebuild"* ]]; then
  [[ "$FUSEKI_ADMIN_PASSWORD" == "drill-only-password" ]] || exit 45
  printf isolated > "$FUSEKI_ADMIN_PASSWORD_CAPTURE"
fi
""")
    fake_chown = fake_bin / "chown"
    fake_chown.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_chown.chmod(0o755)
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)
    env["FUSEKI_ADMIN_PASSWORD_CAPTURE"] = str(tmp_path / "drill-password-isolated")

    subprocess.run([str(ROOT / "scripts/production-compose.sh"), "recovery-drill"],
                   env=env, check=True)

    calls = docker_log.read_text(encoding="utf-8").splitlines()
    project_names = {line.split("--project-name ", 1)[1].split(" ", 1)[0]
                     for line in calls if "--project-name " in line}
    assert len(project_names) == 1
    drill_project = next(iter(project_names))
    assert drill_project.startswith("phase6-recovery-drill-")
    assert "phase6-wrapper-test" not in drill_project
    assert any("ops state initialize" in line for line in calls)
    assert any("ops backup check" in line for line in calls)
    assert any("ops backup restore-latest" in line for line in calls)
    assert any("ops state activate-restore" in line for line in calls)
    assert any("projection rebuild --confirm-empty-target --operation-lock-held" in line
               for line in calls)
    assert (source_repo / "config").read_text(encoding="utf-8") == "encrypted-repository-marker"
    assert not list((tmp_path / "drills").glob("run.*"))
    assert any(line.endswith(" down --volumes --remove-orphans") for line in calls)
    assert (tmp_path / "drill-password-isolated").read_text() == "isolated"
    assert "drill-only-password" not in "\n".join(calls)


def test_recovery_drill_rejects_production_password_reuse(tmp_path):
    runtime_env = _runtime_env(tmp_path, extra=(
        f"OIR_DRILL_ROOT={tmp_path / 'drills'}",
        "OIR_DRILL_COMPOSE_PROJECT=phase6-recovery-drill",
        "OIR_DRILL_FUSEKI_BIND_PORT=13031",
        f"OIR_DRILL_RESTIC_PASSWORD_SOURCE={tmp_path / 'drill-restic-password'}",
        "OIR_DRILL_FUSEKI_ADMIN_PASSWORD=disposable-test-only",
    ))
    (tmp_path / "drills").mkdir()
    (tmp_path / "drill-restic-password").write_text("separate\n", encoding="utf-8")
    (tmp_path / "backups" / "restic").mkdir()
    fake_bin, docker_log = _fake_docker(tmp_path)

    result = subprocess.run(
        [str(ROOT / "scripts/production-compose.sh"), "recovery-drill"],
        env=_launcher_env(tmp_path, runtime_env, fake_bin, docker_log),
        capture_output=True, text=True)

    assert result.returncode != 0
    assert "differ from the production Fuseki password" in result.stderr
    assert not docker_log.exists()


def test_recovery_drill_refuses_paths_overlapping_production(tmp_path):
    runtime_env = _runtime_env(tmp_path, extra=(
        f"OIR_DRILL_ROOT={tmp_path / 'backups' / 'drill'}",
        "OIR_DRILL_COMPOSE_PROJECT=phase6-recovery-drill",
        "OIR_DRILL_FUSEKI_BIND_PORT=13031",
        f"OIR_DRILL_RESTIC_PASSWORD_SOURCE={tmp_path / 'drill-restic-password'}",
        "OIR_DRILL_FUSEKI_ADMIN_PASSWORD=drill-only-password",
    ))
    (tmp_path / "backups" / "drill").mkdir()
    (tmp_path / "drill-restic-password").write_text("separate\n", encoding="utf-8")
    (tmp_path / "backups" / "restic").mkdir()
    fake_bin, docker_log = _fake_docker(tmp_path)
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"), "recovery-drill"],
                            env=env, capture_output=True, text=True)

    assert result.returncode != 0
    assert "must not overlap production" in result.stderr
    assert not docker_log.exists()


def test_compose_rebuild_fuseki_has_no_host_published_port():
    compose = (ROOT / "compose.production.yml").read_text(encoding="utf-8")
    rebuild_service = compose.split("  fuseki-rebuild:", 1)[1].split("\n  etl:", 1)[0]
    assert "ports:" not in rebuild_service
    assert "OIR_FUSEKI_REBUILD_DATA_DIR" in rebuild_service


def test_systemd_installs_alert_and_periodic_recovery_drill_schedules():
    assert "alerts-check" in (ROOT / "deployment/systemd/oir-alert-check.service").read_text()
    assert "OnCalendar=*-*-* 06:00:00" in (
        ROOT / "deployment/systemd/oir-alert-check.timer").read_text()
    assert "recovery-drill" in (ROOT / "deployment/systemd/oir-recovery-drill.service").read_text()
    assert "OnCalendar=Sun *-*-* 06:00:00" in (
        ROOT / "deployment/systemd/oir-recovery-drill.timer").read_text()


def test_every_onfailure_reference_resolves_to_an_installed_template():
    systemd_dir = ROOT / "deployment/systemd"
    templates = {path.name for path in systemd_dir.glob("*@.service")}
    references = []
    for unit in systemd_dir.glob("*.service"):
        for line in unit.read_text(encoding="utf-8").splitlines():
            if line.startswith("OnFailure="):
                target = line.removeprefix("OnFailure=")
                template_name = target.split("@", 1)[0] + "@.service"
                references.append((unit.name, template_name))
                assert template_name in templates, (
                    f"{unit.name} references missing systemd failure template {template_name}")
    assert references


def test_fuseki_startup_holds_shared_lock_only_for_lifecycle_operation(tmp_path):
    runtime_env = _runtime_env(tmp_path)
    fake_bin, docker_log = _fake_docker(tmp_path, script="""#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_DOCKER_LOG"
if [[ "$*" == *" up -d --wait fuseki"* ]]; then
  if flock -n "$OIR_DURABLE_PARENT/operations.lock" -c true; then exit 41; fi
elif [[ "$*" == *" run --rm --no-deps etl run houses"* ]]; then
  flock -n "$OIR_DURABLE_PARENT/operations.lock" -c true || exit 42
fi
""")
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    subprocess.run([str(ROOT / "scripts/production-compose.sh"), "run-etl", "houses"],
                   env=env, check=True)

    calls = docker_log.read_text(encoding="utf-8").splitlines()
    assert any(line.endswith(" up -d --wait fuseki") for line in calls)
    assert any(" run --rm --no-deps etl run houses" in line for line in calls)


def test_fuseki_startup_refuses_to_serve_after_an_incomplete_rebuild(tmp_path):
    runtime_env = _runtime_env(tmp_path)
    (tmp_path / "durable" / "projection-rebuild-required").write_text(
        "incomplete\n", encoding="utf-8")
    fake_bin, docker_log = _fake_docker(tmp_path)
    env = _launcher_env(tmp_path, runtime_env, fake_bin, docker_log)

    result = subprocess.run([str(ROOT / "scripts/production-compose.sh"), "up-fuseki"],
                            env=env, capture_output=True, text=True)

    assert result.returncode != 0
    assert "incomplete projection rebuild" in result.stderr
    assert not docker_log.exists()
