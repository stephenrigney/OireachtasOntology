from __future__ import annotations

import os
from pathlib import Path
import subprocess


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
