"""Boots the real `harness serve` CLI as a subprocess against a clean install.

Everything else in the suite talks to the FastAPI app in-process; this test is the
one place that proves the actual `harness serve` entrypoint (used in DEPLOYMENT.md)
works end to end, including argument parsing, uvicorn startup, and real SQLite I/O.

Plain sync test (not async): it spawns a subprocess and polls it, which are blocking
operations that don't belong on the event loop of an async test.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_clean_boot(tmp_path: Path) -> None:
    port = _free_port()
    env = {**os.environ, "HARNESS_DATA_DIR": str(tmp_path)}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "harness.cli",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + 10
        last_error: Exception | None = None
        with httpx.Client() as client:
            while time.monotonic() < deadline:
                try:
                    resp = client.get(f"http://127.0.0.1:{port}/api/v1/health", timeout=1)
                    if resp.status_code == 200:
                        assert resp.json() == {"status": "ok"}
                        break
                except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                    last_error = exc
                time.sleep(0.1)
            else:
                raise AssertionError(f"server never became healthy: {last_error}")

        assert (tmp_path / "harness.sqlite3").exists()
        assert (tmp_path / "api_token").exists()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
