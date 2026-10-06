"""Disposable Docker-backed Fuseki used only by benchmark automation."""

from __future__ import annotations

import secrets
import subprocess
import time
from urllib.parse import urlsplit

import httpx


class DisposableFuseki:
    """Start one fresh Fuseki container with no bind/named volumes.

    The container's writable layer is private to this run and Docker removes it
    on stop.  Publishing only a random port on loopback keeps the existing
    development bootstrap's loopback-only write guard in force.
    """

    def __init__(self, *, docker: str = "docker", image: str = "stain/jena-fuseki:5.1.0",
                 timeout: float = 90.0, runner=subprocess.run):
        self.docker = docker
        self.image = image
        self.timeout = timeout
        self.runner = runner
        self.name = "oireachtas-nlq-bench-" + secrets.token_hex(6)
        self.password = secrets.token_urlsafe(32)
        self.container_id: str | None = None
        self.query_url: str | None = None
        self.gsp_url: str | None = None
        self.host_port: int | None = None

    def _run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
        return self.runner(
            [self.docker, *args], check=check, capture_output=True, text=True,
        )

    def __enter__(self) -> "DisposableFuseki":
        process = self._run([
            "run", "--detach", "--rm", "--name", self.name,
            "--publish", "127.0.0.1::3030",
            "--env", "FUSEKI_DATASET_1=houses",
            "--env", f"ADMIN_PASSWORD={self.password}",
            self.image,
        ])
        self.container_id = process.stdout.strip()
        if not self.container_id:
            raise RuntimeError("Docker did not return an ID for the disposable Fuseki container")

        deadline = time.monotonic() + self.timeout
        last_error = "Fuseki has not started"
        while time.monotonic() < deadline:
            try:
                port_process = self._run(["port", self.container_id, "3030/tcp"])
                published = port_process.stdout.strip().splitlines()[0].strip()
                parsed = urlsplit("http://" + published)
                if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
                    raise RuntimeError("Docker published Fuseki outside the loopback interface")
                self.host_port = parsed.port
                origin = f"http://127.0.0.1:{self.host_port}"
                with httpx.Client(timeout=2.0) as client:
                    response = client.get(origin + "/$/ping")
                if response.is_success:
                    self.query_url = origin + "/houses/query"
                    self.gsp_url = origin + "/houses/data"
                    return self
                last_error = f"Fuseki readiness returned HTTP {response.status_code}"
            except (IndexError, OSError, RuntimeError, httpx.HTTPError,
                    subprocess.CalledProcessError) as error:
                last_error = str(error)
            time.sleep(0.5)
        self._cleanup()
        raise RuntimeError(f"disposable Fuseki did not become ready: {last_error}")

    def _cleanup(self) -> None:
        if self.container_id is None:
            return
        try:
            self._run(["stop", "--time", "5", self.container_id], check=False)
        finally:
            # --rm removes the container on stop; this handles a failed stop
            # without ever touching volumes or another Fuseki instance.
            self._run(["rm", "--force", self.container_id], check=False)
            self.container_id = None

    def __exit__(self, *_exc_info) -> None:
        self._cleanup()

    def isolation_metadata(self) -> dict:
        if not self.container_id or not self.host_port:
            raise RuntimeError("disposable Fuseki is not running")
        return {
            "container_id": self.container_id,
            "container_name": self.name,
            "dataset_name": "houses",
            "query_endpoint": self.query_url,
            "disposable": True,
            "container_auto_removed": True,
            "persistent_volume_attached": False,
            "host_binding": "127.0.0.1",
            "image": self.image,
        }
